#!/usr/bin/env python3
"""
ASR Service - Local Speech Recognition Pipeline
Mic → Silero VAD → Whisper large-v3-turbo → JSON logs

Continuously captures audio, detects speech with VAD, and transcribes using Whisper.
Cross-platform compatible (Windows/Linux) with robust error handling.
"""

import logging
import os
import queue
import signal
import sys
import threading
import time
import wave
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import jsonlines
import numpy as np
from faster_whisper import WhisperModel
from scipy import signal as scipy_signal

# Audio and ML imports
try:
    import sounddevice as sd
except ImportError:
    print("ERROR: sounddevice not found. Install with: pip install sounddevice")
    sys.exit(1)

# VAD imports - try multiple options
VAD_ENGINE = None

# Check for VAD engine override first
if os.environ.get("ASR_VAD", "").lower() == "silero":
    try:
        import torch
        from silero_vad import get_speech_timestamps, load_silero_vad

        VAD_ENGINE = "silero"
        print("🔧 Using Silero VAD (override)")
    except ImportError:
        print(
            "ERROR: Silero VAD requested but not available. Install with: pip install silero-vad"
        )
        sys.exit(1)
else:
    # Using Silero VAD only (WebRTC VAD removed due to Windows compilation issues)
    try:
        import torch
        from silero_vad import get_speech_timestamps, load_silero_vad

        VAD_ENGINE = "silero"
        print("🔧 Using Silero VAD")
    except ImportError:
        print(
            "ERROR: Silero VAD not found. Install with: pip install silero-vad torch"
        )
        print("Make sure you have run install_windows.bat to set up dependencies.")
        sys.exit(1)


def detect_best_sample_rate(device_id=None):
    """Detect the best supported sample rate for the audio device."""
    # Preferred sample rates in order of preference
    preferred_rates = [48000, 44100, 22050, 16000, 8000]
    
    for rate in preferred_rates:
        try:
            # Test if this sample rate works with the device
            with sd.InputStream(
                samplerate=rate,
                channels=1,
                dtype=np.float32,
                device=device_id,
                blocksize=512,
                callback=lambda *args: None  # Dummy callback
            ):
                print(f"✓ Using sample rate: {rate} Hz")
                return rate
        except Exception:
            continue
    
    # If nothing works, fall back to querying device info
    try:
        device_info = sd.query_devices(device_id)
        default_rate = int(device_info['default_samplerate'])
        print(f"✓ Using device default sample rate: {default_rate} Hz")
        return default_rate
    except Exception:
        print("⚠️  Could not detect sample rate, using 44100 Hz as fallback")
        return 44100


# Configuration
class Config:
    # Audio settings - will be set dynamically
    SAMPLE_RATE = None  # Will be detected at runtime
    WHISPER_SAMPLE_RATE = 16000  # Whisper expects 16kHz
    CHANNELS = 1
    CHUNK_SIZE = 1024  # Adjustable buffer size
    DTYPE = np.float32

    # VAD settings
    VAD_FRAME_DURATION_MS = 30  # Frame duration (legacy setting)
    VAD_AGGRESSIVENESS = 3  # 0-3, higher = more aggressive
    SPEECH_TIMEOUT = 1.0  # Seconds of silence to end speech segment
    MIN_SPEECH_DURATION = 0.5  # Minimum speech duration to process
    OVERLAP_DURATION = 0.3  # Overlap between segments

    # Debug settings
    SHOW_VAD_ACTIVITY = os.environ.get("ASR_DEBUG", "").lower() in ["1", "true", "yes"]

    # VAD Engine (using Silero VAD only)
    VAD_ENGINE_OVERRIDE = os.environ.get("ASR_VAD", "").lower()

    # Whisper settings
    MODEL_NAME = "large-v3-turbo"
    DEVICE = "cuda"  # Will fallback to CPU if CUDA unavailable
    COMPUTE_TYPE = "float16"

    # Logging
    LOG_FILE = "logs/asr_results.jsonl"
    SERVICE_LOG = "logs/asr.out"
    ERROR_LOG = "logs/asr.err"

    # Audio storage
    SAVE_AUDIO_SEGMENTS = True  # Set to False to disable audio saving
    AUDIO_DIR = "audios"


def resample_audio(audio_data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample audio from original sample rate to target sample rate."""
    if orig_sr == target_sr:
        return audio_data
    
    # Calculate resampling ratio
    num_samples = int(len(audio_data) * target_sr / orig_sr)
    
    # Use scipy's resample function
    return scipy_signal.resample(audio_data, num_samples).astype(np.float32)


class AudioBuffer:
    """Thread-safe audio buffer with VAD integration."""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.whisper_sample_rate = Config.WHISPER_SAMPLE_RATE
        self.buffer = []
        self.is_speech = False
        self.speech_start_time = None
        self.silence_start_time = None
        self.lock = threading.Lock()

        # Initialize VAD
        self.vad = self._init_vad()

        # VAD engine specific buffers
        if VAD_ENGINE == "silero":
            self.silero_buffer = []
            self.silero_buffer_duration = 1.0  # Seconds of audio to accumulate for VAD
        # WebRTC VAD removed - using Silero VAD only

    def _init_vad(self):
        """Initialize the VAD engine (Silero VAD only)."""
        if VAD_ENGINE == "silero":
            return load_silero_vad()
        else:
            raise RuntimeError("No VAD engine available")

    # WebRTC VAD detection method removed - using Silero VAD only

    def _detect_speech_silero(self, audio_chunk: np.ndarray) -> bool:
        """Detect speech using Silero VAD."""
        # Accumulate audio chunks for Silero VAD (needs longer context)
        self.silero_buffer.extend(audio_chunk)

        # Calculate required buffer size
        required_samples = int(self.silero_buffer_duration * self.sample_rate)

        # Only run VAD when we have enough audio
        if len(self.silero_buffer) < required_samples:
            return False  # Not enough audio yet, assume no speech

        # Resample for Silero VAD (it expects 16kHz)
        vad_audio = resample_audio(
            np.array(self.silero_buffer, dtype=np.float32),
            self.sample_rate,
            16000
        )
        
        # Convert to torch tensor and run VAD on resampled audio
        audio_tensor = torch.from_numpy(vad_audio)
        speech_timestamps = get_speech_timestamps(audio_tensor, self.vad)

        # Keep only recent audio in buffer (sliding window)
        # Keep 1.5x the buffer duration to provide overlap
        max_buffer_samples = int(self.silero_buffer_duration * 1.5 * self.sample_rate)
        if len(self.silero_buffer) > max_buffer_samples:
            self.silero_buffer = self.silero_buffer[-max_buffer_samples:]

        # Return True if any speech detected in the recent audio
        return len(speech_timestamps) > 0

    def detect_speech(self, audio_chunk: np.ndarray) -> bool:
        """Detect speech in audio chunk using available VAD engine."""
        try:
            # Calculate audio level for debugging
            audio_level = np.sqrt(np.mean(audio_chunk**2))

            if VAD_ENGINE == "silero":
                is_speech = self._detect_speech_silero(audio_chunk)
            else:
                return False

            # Debug output for audio levels and VAD decisions (only show speech, not constant silence)
            if Config.SHOW_VAD_ACTIVITY and is_speech:
                print(f"🟢SPEECH | Level: {audio_level:.4f}")

            return is_speech

        except Exception as e:
            logging.warning(f"VAD detection failed: {e}")
            return False

    def add_audio(
        self, audio_chunk: np.ndarray, timestamp: float
    ) -> Optional[Tuple[np.ndarray, float, float]]:
        """
        Add audio chunk and return complete speech segment if ready.
        Returns: (audio_data, start_time, end_time) or None
        """
        with self.lock:
            is_speech = self.detect_speech(audio_chunk)
            current_time = timestamp

            if is_speech:
                if not self.is_speech:
                    # Speech started
                    self.is_speech = True
                    self.speech_start_time = current_time
                    if Config.SHOW_VAD_ACTIVITY:
                        print("🟢 Speech started")
                    # Add some overlap from before speech started
                    overlap_samples = int(Config.OVERLAP_DURATION * self.sample_rate)
                    if len(self.buffer) > overlap_samples:
                        self.buffer = self.buffer[-overlap_samples:]
                    else:
                        self.buffer = []

                self.buffer.extend(audio_chunk)
                self.silence_start_time = None

            else:
                if self.is_speech:
                    # Potential end of speech
                    if self.silence_start_time is None:
                        self.silence_start_time = current_time

                    # Continue buffering during silence timeout
                    self.buffer.extend(audio_chunk)

                    # Check if silence timeout exceeded
                    if current_time - self.silence_start_time >= Config.SPEECH_TIMEOUT:
                        # Speech segment ended
                        speech_duration = current_time - self.speech_start_time

                        if Config.SHOW_VAD_ACTIVITY:
                            print(f"🔴 Speech ended ({speech_duration:.1f}s)")

                        if speech_duration >= Config.MIN_SPEECH_DURATION:
                            # Return the speech segment - resample for Whisper
                            audio_data = np.array(self.buffer, dtype=Config.DTYPE)
                            
                            # Resample to Whisper's expected sample rate (16kHz)
                            whisper_audio = resample_audio(
                                audio_data, 
                                self.sample_rate, 
                                self.whisper_sample_rate
                            )
                            
                            start_time = self.speech_start_time
                            end_time = current_time

                            # Reset for next segment
                            self._reset()

                            return whisper_audio, start_time, end_time
                        else:
                            # Too short, discard
                            if Config.SHOW_VAD_ACTIVITY:
                                print(
                                    f"⏭️  Speech too short ({speech_duration:.1f}s), discarding"
                                )
                            self._reset()
                else:
                    # Not in speech, keep a small buffer for overlap
                    overlap_samples = int(Config.OVERLAP_DURATION * self.sample_rate)
                    self.buffer.extend(audio_chunk)
                    if len(self.buffer) > overlap_samples:
                        self.buffer = self.buffer[-overlap_samples:]

            return None

    def _reset(self):
        """Reset buffer state."""
        self.buffer = []
        self.is_speech = False
        self.speech_start_time = None
        self.silence_start_time = None

        # Reset VAD engine specific buffers
        if VAD_ENGINE == "silero" and hasattr(self, "silero_buffer"):
            self.silero_buffer = []
        # WebRTC VAD cleanup removed - using Silero VAD only


class WhisperTranscriber:
    """Whisper model wrapper for transcription."""

    def __init__(self):
        self.model = None
        self.model_lock = threading.Lock()
        self._load_model()

    def _load_model(self):
        """Load Whisper model with error handling."""
        try:
            # Check if model exists locally
            models_dir = Path("models")

            # Try CUDA first, fallback to CPU
            device = Config.DEVICE
            try:
                import torch

                if not torch.cuda.is_available():
                    device = "cpu"
                    logging.warning("CUDA not available, using CPU")
            except ImportError:
                device = "cpu"

            logging.info(f"Loading Whisper {Config.MODEL_NAME} on {device}")

            self.model = WhisperModel(
                Config.MODEL_NAME,
                device=device,
                compute_type=Config.COMPUTE_TYPE if device == "cuda" else "int8",
                download_root=str(models_dir) if models_dir.exists() else None,
            )

            logging.info("Whisper model loaded successfully")

        except Exception as e:
            logging.error(f"Failed to load Whisper model: {e}")
            raise

    def transcribe(self, audio_data: np.ndarray) -> Tuple[str, float]:
        """
        Transcribe audio data.
        Returns: (transcript, confidence)
        """
        with self.model_lock:
            try:
                segments, info = self.model.transcribe(
                    audio_data,
                    language="en",  # Assuming English for aviation
                    vad_filter=False,  # We already did VAD
                    word_timestamps=True,
                )

                # Collect all segments
                transcript_parts = []
                log_probs = []

                for segment in segments:
                    transcript_parts.append(segment.text.strip())
                    if hasattr(segment, "avg_logprob"):
                        log_probs.append(segment.avg_logprob)

                transcript = " ".join(transcript_parts).strip()

                # Calculate confidence from average log probability
                if log_probs:
                    avg_log_prob = sum(log_probs) / len(log_probs)
                    confidence = np.exp(avg_log_prob)  # Convert log prob to probability
                else:
                    confidence = 0.0

                return transcript, confidence

            except Exception as e:
                logging.error(f"Transcription failed: {e}")
                return "", 0.0


class ASRService:
    """Main ASR service orchestrating audio capture, VAD, and transcription."""

    def __init__(self, audio_device_id=None):
        self.running = False
        self.audio_device_id = audio_device_id
        
        # Detect and set the best sample rate for the audio device
        if Config.SAMPLE_RATE is None:
            Config.SAMPLE_RATE = detect_best_sample_rate(audio_device_id)
        
        # Now initialize components that depend on Config.SAMPLE_RATE
        self.audio_buffer = AudioBuffer(sample_rate=Config.SAMPLE_RATE)
        self.transcriber = WhisperTranscriber()
        self.audio_queue = queue.Queue()

        # Setup logging
        self._setup_logging()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _setup_logging(self):
        """Setup logging configuration."""
        # Create logs directory
        Path("logs").mkdir(exist_ok=True)

        # Create audios directory if audio saving is enabled
        if Config.SAVE_AUDIO_SEGMENTS:
            Path(Config.AUDIO_DIR).mkdir(exist_ok=True)

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(Config.SERVICE_LOG),
                logging.StreamHandler(sys.stdout),
            ],
        )

        # Setup error logging
        error_handler = logging.FileHandler(Config.ERROR_LOG)
        error_handler.setLevel(logging.ERROR)
        logging.getLogger().addHandler(error_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logging.info(f"Received signal {signum}, shutting down...")
        self.stop()

    def _audio_callback(self, indata, frames, time_info, status):
        """Audio input callback."""
        if status:
            logging.warning(f"Audio input status: {status}")

        # Convert to mono if needed
        if indata.shape[1] > 1:
            audio_data = np.mean(indata, axis=1)
        else:
            audio_data = indata[:, 0]

        # Add timestamp
        timestamp = time.time()
        self.audio_queue.put((audio_data.copy(), timestamp))

    def _process_audio(self):
        """Process audio from queue."""
        while self.running:
            try:
                # Get audio chunk with timeout
                audio_chunk, timestamp = self.audio_queue.get(timeout=1.0)

                # Process through VAD buffer
                result = self.audio_buffer.add_audio(audio_chunk, timestamp)

                if result is not None:
                    audio_data, start_time, end_time = result

                    # Show speech detection feedback
                    duration = end_time - start_time
                    print(
                        f"🎯 Speech detected: {duration:.1f}s segment, transcribing..."
                    )

                    # Transcribe in separate thread to avoid blocking
                    threading.Thread(
                        target=self._transcribe_and_log,
                        args=(audio_data, start_time, end_time),
                        daemon=True,
                    ).start()

            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"Error processing audio: {e}")

    def _save_audio_segment(
        self, audio_data: np.ndarray, timestamp: str, sample_rate: int = None
    ) -> Optional[str]:
        """Save audio segment as WAV file."""
        if not Config.SAVE_AUDIO_SEGMENTS:
            return None

        try:
            # Generate filename with timestamp
            filename = f"speech_{timestamp.replace(':', '-').replace('.', '_')}.wav"
            filepath = Path(Config.AUDIO_DIR) / filename

            # Convert float32 to int16 for WAV file
            audio_int16 = (audio_data * 32767).astype(np.int16)
            
            # Use provided sample rate or default to Whisper sample rate
            save_sample_rate = sample_rate or Config.WHISPER_SAMPLE_RATE

            # Write WAV file
            with wave.open(str(filepath), "wb") as wav_file:
                wav_file.setnchannels(Config.CHANNELS)
                wav_file.setsampwidth(2)  # 16-bit = 2 bytes
                wav_file.setframerate(save_sample_rate)
                wav_file.writeframes(audio_int16.tobytes())

            return str(filepath)

        except Exception as e:
            logging.error(f"Failed to save audio segment: {e}")
            return None

    def _transcribe_and_log(
        self, audio_data: np.ndarray, start_time: float, end_time: float
    ):
        """Transcribe audio and log results."""
        try:
            transcript, confidence = self.transcriber.transcribe(audio_data)

            if transcript:  # Only log if we got a transcript
                # Save audio segment if enabled
                timestamp_str = datetime.now().isoformat()
                # Save with Whisper sample rate since audio_data is resampled
                audio_file = self._save_audio_segment(audio_data, timestamp_str, Config.WHISPER_SAMPLE_RATE)

                # Create log entry
                log_entry = {
                    "start": round(start_time, 2),
                    "end": round(end_time, 2),
                    "transcript": transcript,
                    "confidence": round(confidence, 3),
                    "timestamp": timestamp_str,
                    "vad_engine": VAD_ENGINE,
                }

                # Add audio file path if saved
                if audio_file:
                    log_entry["audio_file"] = audio_file

                # Write to JSONL file
                with jsonlines.open(Config.LOG_FILE, mode="a") as writer:
                    writer.write(log_entry)

                # Show transcription result
                audio_info = f" (saved: {audio_file})" if audio_file else ""
                print(f"📝 [{confidence:.3f}] {transcript}{audio_info}")
                logging.info(
                    f"Transcribed ({confidence:.3f}): {transcript}{audio_info}"
                )
            else:
                print("🤐 No speech detected in audio segment")

        except Exception as e:
            logging.error(f"Error in transcription: {e}")

    def start(self):
        """Start the ASR service."""
        print("🎤 Starting ASR Service...")
        print(f"📊 VAD Engine: {VAD_ENGINE}")
        print(f"🔊 Sample Rate: {Config.SAMPLE_RATE} Hz")
        print(f"🖥️  Device: {Config.DEVICE}")
        print("📁 Log files:")
        print(f"   - Results: {Config.LOG_FILE}")
        print(f"   - Service: {Config.SERVICE_LOG}")
        print(f"   - Errors:  {Config.ERROR_LOG}")
        if Config.SAVE_AUDIO_SEGMENTS:
            print(f"🎵 Audio segments: {Config.AUDIO_DIR}/")
        if Config.SHOW_VAD_ACTIVITY:
            print("🐛 Debug mode: ON (showing VAD activity)")
        else:
            print("💡 Tip: Set ASR_DEBUG=1 to see VAD activity")

        # VAD info
        print("🧠 Using Silero VAD (ML-based)")
        print()

        logging.info("Starting ASR Service...")
        logging.info(f"VAD Engine: {VAD_ENGINE}")
        logging.info(f"Sample Rate: {Config.SAMPLE_RATE} Hz")
        logging.info(f"Device: {Config.DEVICE}")

        self.running = True

        # Start audio processing thread
        audio_thread = threading.Thread(target=self._process_audio, daemon=True)
        audio_thread.start()

        # Start audio capture
        try:
            print("🎧 Initializing audio capture (sounddevice)...")

            # List available audio devices
            devices = sd.query_devices()
            input_devices = [d for d in devices if d["max_input_channels"] > 0]
            if input_devices:
                device_to_use = self.audio_device_id if self.audio_device_id is not None else sd.default.device[0]
                device_info = sd.query_devices(device_to_use)
                print(f"🎙️  Using audio device: {device_info['name']} (Sample Rate: {Config.SAMPLE_RATE} Hz)")
            else:
                print("⚠️  No audio input devices found!")

            with sd.InputStream(
                samplerate=Config.SAMPLE_RATE,
                channels=Config.CHANNELS,
                dtype=Config.DTYPE,
                blocksize=Config.CHUNK_SIZE,
                device=self.audio_device_id,
                callback=self._audio_callback,
            ):
                print("✅ Audio capture started successfully!")
                print("🗣️  Listening for speech... (Ctrl+C to stop)")
                print("💡 Speak into your microphone to test transcription")
                print()

                logging.info("Audio capture started (sounddevice)")
                while self.running:
                    time.sleep(0.1)

        except Exception as e:
            logging.error(f"Audio capture failed: {e}")
            self.running = False


    def stop(self):
        """Stop the ASR service."""
        logging.info("Stopping ASR Service...")
        self.running = False


def main():
    """Main entry point."""
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="ASR Service - Local Speech Recognition Pipeline"
    )
    parser.add_argument(
        "--vad",
        choices=["silero"],
        help="Force specific VAD engine (overrides ASR_VAD env var)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (equivalent to ASR_DEBUG=1)",
    )
    parser.add_argument(
        "--device",
        type=int,
        help="Audio input device ID (use test_audio.py to list devices)",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available audio devices and exit",
    )
    args = parser.parse_args()

    # List devices if requested
    if args.list_devices:
        print("🎧 Available Audio Input Devices:")
        print("=" * 50)
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if device["max_input_channels"] > 0:
                status = "📍 DEFAULT" if i == sd.default.device[0] else "  "
                print(f"{status} [{i:2d}] {device['name']}")
                print(f"      Channels: {device['max_input_channels']}, Sample Rate: {device['default_samplerate']}")
        return

    # Override environment variables with command line args
    if args.vad:
        os.environ["ASR_VAD"] = args.vad
        print(f"🔧 VAD engine set to: {args.vad}")

    if args.debug:
        os.environ["ASR_DEBUG"] = "1"
        print("🐛 Debug mode enabled")

    if args.device is not None:
        print(f"🎙️  Audio device set to: {args.device}")

    # Create logs directory
    Path("logs").mkdir(exist_ok=True)

    # Create audios directory if audio saving is enabled
    if Config.SAVE_AUDIO_SEGMENTS:
        Path(Config.AUDIO_DIR).mkdir(exist_ok=True)

    # Initialize and start service
    service = ASRService(audio_device_id=args.device)

    try:
        service.start()
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
    except Exception as e:
        logging.error(f"Service error: {e}")
    finally:
        service.stop()


if __name__ == "__main__":
    main()
