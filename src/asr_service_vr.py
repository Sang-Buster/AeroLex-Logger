#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ASR Service VR - Enhanced for VR Training with Circular Buffer
Integrates with VR training backend with student sessions
Uses 5-second circular buffer to prevent speech cutoffs
"""

import configparser
import io
import json
import logging
import os
import queue
import signal
import sys
import threading
import time
import wave
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Fix Windows console encoding to support emojis
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )
    except (AttributeError, io.UnsupportedOperation):
        # If stdout/stderr don't have a buffer (e.g., in some IDEs), ignore
        pass

import jsonlines
import numpy as np
from faster_whisper import WhisperModel
from scipy import signal as scipy_signal

# Audio imports
try:
    import sounddevice as sd
except ImportError:
    print("ERROR: sounddevice not found. Install with: pip install sounddevice")
    sys.exit(1)

# VAD imports
try:
    import torch
    from silero_vad import get_speech_timestamps, load_silero_vad

    VAD_ENGINE = "silero"
    print("🔧 Using Silero VAD")
except ImportError:
    print("ERROR: Silero VAD not found. Install with: pip install silero-vad torch")
    sys.exit(1)


def detect_best_sample_rate(device_id=None):
    """Detect the best supported sample rate for the audio device."""
    preferred_rates = [48000, 44100, 22050, 16000, 8000]

    for rate in preferred_rates:
        try:
            with sd.InputStream(
                samplerate=rate,
                channels=1,
                dtype=np.float32,
                device=device_id,
                blocksize=512,
                callback=lambda *args: None,
            ):
                print(f"✓ Using sample rate: {rate} Hz")
                return rate
        except Exception:
            continue

    try:
        device_info = sd.query_devices(device_id)
        default_rate = int(device_info["default_samplerate"])
        print(f"✓ Using device default sample rate: {default_rate} Hz")
        return default_rate
    except Exception:
        print("⚠️  Could not detect sample rate, using 44100 Hz as fallback")
        return 44100


def resample_audio(audio_data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample audio from original sample rate to target sample rate."""
    if orig_sr == target_sr:
        return audio_data

    num_samples = int(len(audio_data) * target_sr / orig_sr)
    return scipy_signal.resample(audio_data, num_samples).astype(np.float32)


def load_config() -> configparser.ConfigParser:
    """Load ASR configuration from file."""
    config = configparser.ConfigParser()
    config_file = Path(__file__).parent.parent / "asr_config.ini"

    if config_file.exists():
        config.read(config_file)
        print(f"✅ Loaded config from: {config_file}")
    else:
        print(f"⚠️  Config file not found: {config_file}, using defaults")

    return config


# Configuration for VR Training
class VRConfig:
    # Load configuration file
    _config = load_config()

    # Audio settings
    SAMPLE_RATE = None  # Detected at runtime
    WHISPER_SAMPLE_RATE = 16000
    CHANNELS = 1
    CHUNK_SIZE = 1024
    DTYPE = np.float32

    # Circular buffer settings
    USE_CIRCULAR_BUFFER = _config.getboolean(
        "BUFFER_SETTINGS", "USE_CIRCULAR_BUFFER", fallback=True
    )
    BUFFER_DURATION = _config.getfloat(
        "BUFFER_SETTINGS", "BUFFER_DURATION", fallback=5.0
    )

    # VAD settings
    SPEECH_TIMEOUT = _config.getfloat("BUFFER_SETTINGS", "SPEECH_TIMEOUT", fallback=1.0)
    MIN_SPEECH_DURATION = _config.getfloat(
        "BUFFER_SETTINGS", "MIN_SPEECH_DURATION", fallback=0.5
    )
    OVERLAP_DURATION = 0.3

    # VAD thresholds (for Silero)
    VAD_THRESHOLD = _config.getfloat("VAD_SETTINGS", "VAD_THRESHOLD", fallback=0.6)
    VAD_MIN_SPEECH_DURATION_MS = _config.getint(
        "VAD_SETTINGS", "MIN_SPEECH_DURATION_MS", fallback=400
    )
    VAD_MIN_SILENCE_DURATION_MS = _config.getint(
        "VAD_SETTINGS", "MIN_SILENCE_DURATION_MS", fallback=300
    )
    VAD_SPEECH_PAD_MS = _config.getint("VAD_SETTINGS", "SPEECH_PAD_MS", fallback=100)

    # Whisper settings
    MODEL_NAME = _config.get("MODEL_SETTINGS", "MODEL_NAME", fallback="large-v3-turbo")
    DEVICE = _config.get("MODEL_SETTINGS", "DEVICE", fallback="cuda")
    COMPUTE_TYPE = _config.get("MODEL_SETTINGS", "COMPUTE_TYPE", fallback="float16")

    # Quality thresholds for noise filtering
    MIN_CONFIDENCE = _config.getfloat("ASR_QUALITY", "MIN_CONFIDENCE", fallback=0.55)
    MIN_TRANSCRIPT_LENGTH = _config.getint(
        "ASR_QUALITY", "MIN_TRANSCRIPT_LENGTH", fallback=10
    )
    MIN_WORD_COUNT = _config.getint("ASR_QUALITY", "MIN_WORD_COUNT", fallback=3)

    # Session settings
    STUDENT_ID = None
    VIDEO_ID = None
    SESSION_ID = None
    AUDIO_DIR = None
    LOGS_DIR = None

    # Debug settings
    SHOW_VAD_ACTIVITY = os.environ.get("ASR_DEBUG", "").lower() in ["1", "true", "yes"]


class VRAudioBuffer:
    """Enhanced audio buffer with circular buffer for VR training."""

    def __init__(self, sample_rate: int = 44100, session_info: Dict[str, str] = None):
        self.sample_rate = sample_rate
        self.whisper_sample_rate = VRConfig.WHISPER_SAMPLE_RATE
        self.session_info = session_info or {}
        self.buffer = []
        self.is_speech = False
        self.speech_start_time = None
        self.silence_start_time = None
        self.lock = threading.Lock()

        # Circular buffer for extra context
        if VRConfig.USE_CIRCULAR_BUFFER:
            max_samples = int(VRConfig.BUFFER_DURATION * sample_rate)
            self.circular_buffer = deque(maxlen=max_samples)
        else:
            self.circular_buffer = None

        # Initialize VAD
        self.vad = load_silero_vad()
        self.silero_buffer = []
        self.silero_buffer_duration = 1.0

    def _detect_speech_silero(self, audio_chunk: np.ndarray) -> bool:
        """Detect speech using Silero VAD with configurable thresholds."""
        self.silero_buffer.extend(audio_chunk)

        required_samples = int(self.silero_buffer_duration * self.sample_rate)

        if len(self.silero_buffer) < required_samples:
            return False

        vad_audio = resample_audio(
            np.array(self.silero_buffer, dtype=np.float32), self.sample_rate, 16000
        )

        audio_tensor = torch.from_numpy(vad_audio)

        # Use configurable VAD parameters to reduce false positives
        speech_timestamps = get_speech_timestamps(
            audio_tensor,
            self.vad,
            threshold=VRConfig.VAD_THRESHOLD,
            min_speech_duration_ms=VRConfig.VAD_MIN_SPEECH_DURATION_MS,
            min_silence_duration_ms=VRConfig.VAD_MIN_SILENCE_DURATION_MS,
            speech_pad_ms=VRConfig.VAD_SPEECH_PAD_MS,
        )

        max_buffer_samples = int(self.silero_buffer_duration * 1.5 * self.sample_rate)
        if len(self.silero_buffer) > max_buffer_samples:
            self.silero_buffer = self.silero_buffer[-max_buffer_samples:]

        return len(speech_timestamps) > 0

    def detect_speech(self, audio_chunk: np.ndarray) -> bool:
        """Detect speech in audio chunk."""
        try:
            audio_level = np.sqrt(np.mean(audio_chunk**2))
            is_speech = self._detect_speech_silero(audio_chunk)

            if VRConfig.SHOW_VAD_ACTIVITY and is_speech:
                print(
                    f"🟢SPEECH | Level: {audio_level:.4f} | Session: {self.session_info.get('session_id', 'N/A')}"
                )

            return is_speech

        except Exception as e:
            logging.warning(f"VAD detection failed: {e}")
            return False

    def add_audio(
        self, audio_chunk: np.ndarray, timestamp: float
    ) -> Optional[Tuple[np.ndarray, float, float]]:
        """Add audio chunk and return complete speech segment if ready."""
        with self.lock:
            # Always add to circular buffer
            if self.circular_buffer is not None:
                for sample in audio_chunk:
                    self.circular_buffer.append(sample)

            is_speech = self.detect_speech(audio_chunk)
            current_time = timestamp

            if is_speech:
                if not self.is_speech:
                    # Speech started
                    self.is_speech = True
                    self.speech_start_time = current_time
                    if VRConfig.SHOW_VAD_ACTIVITY:
                        print(
                            f"🟢 Speech started | Student: {self.session_info.get('student_id', 'N/A')}"
                        )

                    # Include circular buffer content for extra context!
                    if self.circular_buffer is not None:
                        self.buffer = list(self.circular_buffer)
                    else:
                        overlap_samples = int(
                            VRConfig.OVERLAP_DURATION * self.sample_rate
                        )
                        if len(self.buffer) > overlap_samples:
                            self.buffer = self.buffer[-overlap_samples:]
                        else:
                            self.buffer = []

                self.buffer.extend(audio_chunk)
                self.silence_start_time = None

            else:
                if self.is_speech:
                    if self.silence_start_time is None:
                        self.silence_start_time = current_time

                    self.buffer.extend(audio_chunk)

                    if (
                        current_time - self.silence_start_time
                        >= VRConfig.SPEECH_TIMEOUT
                    ):
                        # Speech segment ended
                        speech_duration = current_time - self.speech_start_time

                        if VRConfig.SHOW_VAD_ACTIVITY:
                            print(f"🔴 Speech ended ({speech_duration:.1f}s)")

                        if speech_duration >= VRConfig.MIN_SPEECH_DURATION:
                            audio_data = np.array(self.buffer, dtype=VRConfig.DTYPE)

                            whisper_audio = resample_audio(
                                audio_data, self.sample_rate, self.whisper_sample_rate
                            )

                            start_time = self.speech_start_time
                            end_time = current_time

                            self._reset()
                            return whisper_audio, start_time, end_time
                        else:
                            if VRConfig.SHOW_VAD_ACTIVITY:
                                print(
                                    f"⏭️  Speech too short ({speech_duration:.1f}s), discarding"
                                )
                            self._reset()
                else:
                    if self.circular_buffer is None:
                        overlap_samples = int(
                            VRConfig.OVERLAP_DURATION * self.sample_rate
                        )
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
        if hasattr(self, "silero_buffer"):
            self.silero_buffer = []


class VRWhisperTranscriber:
    """Enhanced Whisper transcriber with session context."""

    def __init__(self, session_info: Dict[str, str] = None):
        self.session_info = session_info or {}
        self.model = None
        self.model_lock = threading.Lock()
        self._load_model()

    def _load_model(self):
        """Load Whisper model."""
        try:
            models_dir = Path("models")

            device = VRConfig.DEVICE
            try:
                if not torch.cuda.is_available():
                    device = "cpu"
                    logging.warning("CUDA not available, using CPU")
            except ImportError:
                device = "cpu"

            logging.info(f"Loading Whisper {VRConfig.MODEL_NAME} on {device}")

            self.model = WhisperModel(
                VRConfig.MODEL_NAME,
                device=device,
                compute_type=VRConfig.COMPUTE_TYPE if device == "cuda" else "int8",
                download_root=str(models_dir) if models_dir.exists() else None,
            )

            logging.info("Whisper model loaded successfully")

        except Exception as e:
            logging.error(f"Failed to load Whisper model: {e}")
            raise

    def transcribe(self, audio_data: np.ndarray) -> Tuple[str, float]:
        """Transcribe audio data."""
        with self.model_lock:
            try:
                segments, info = self.model.transcribe(
                    audio_data,
                    language="en",
                    vad_filter=False,
                    word_timestamps=True,
                )

                transcript_parts = []
                log_probs = []

                for segment in segments:
                    transcript_parts.append(segment.text.strip())
                    if hasattr(segment, "avg_logprob"):
                        log_probs.append(segment.avg_logprob)

                transcript = " ".join(transcript_parts).strip()

                if log_probs:
                    avg_log_prob = sum(log_probs) / len(log_probs)
                    confidence = np.exp(avg_log_prob)
                else:
                    confidence = 0.0

                return transcript, confidence

            except Exception as e:
                logging.error(f"Transcription failed: {e}")
                return "", 0.0


class VRASRService:
    """Enhanced ASR service for VR training with circular buffer."""

    def __init__(self, audio_device_id=None, session_config: Dict[str, str] = None):
        self.running = False
        self.audio_device_id = audio_device_id
        self.session_config = session_config or {}

        # Setup configuration from session
        self._setup_session_config()

        # Detect sample rate
        if VRConfig.SAMPLE_RATE is None:
            VRConfig.SAMPLE_RATE = detect_best_sample_rate(audio_device_id)

        # Initialize components with session context
        self.audio_buffer = VRAudioBuffer(
            sample_rate=VRConfig.SAMPLE_RATE, session_info=self.session_config
        )
        self.transcriber = VRWhisperTranscriber(session_info=self.session_config)
        self.audio_queue = queue.Queue()

        # Setup logging
        self._setup_logging()

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _setup_session_config(self):
        """Setup configuration from session data."""
        if self.session_config:
            VRConfig.STUDENT_ID = self.session_config.get("student_id")
            VRConfig.VIDEO_ID = self.session_config.get("video_id")
            VRConfig.SESSION_ID = self.session_config.get("session_id")
            VRConfig.AUDIO_DIR = self.session_config.get("audio_dir")
            VRConfig.LOGS_DIR = self.session_config.get("logs_dir")

    def _setup_logging(self):
        """Setup session-aware logging."""
        # Create student-specific directories
        if VRConfig.LOGS_DIR:
            Path(VRConfig.LOGS_DIR).mkdir(parents=True, exist_ok=True)
        if VRConfig.AUDIO_DIR:
            Path(VRConfig.AUDIO_DIR).mkdir(parents=True, exist_ok=True)

        # Setup log file paths
        if VRConfig.LOGS_DIR:
            log_file = Path(VRConfig.LOGS_DIR) / "asr_results.jsonl"
            service_log = Path(VRConfig.LOGS_DIR) / "asr.out"
            error_log = Path(VRConfig.LOGS_DIR) / "asr.err"
            self.stop_flag_file = Path(VRConfig.LOGS_DIR) / ".asr_stop_recording"
        else:
            # Fallback to default logs
            Path("logs").mkdir(exist_ok=True)
            log_file = Path("logs/asr_results.jsonl")
            service_log = Path("logs/asr.out")
            error_log = Path("logs/asr.err")
            self.stop_flag_file = Path("logs/.asr_stop_recording")

        self.log_file = str(log_file)

        # Remove any existing stop flag from previous session
        if self.stop_flag_file.exists():
            self.stop_flag_file.unlink()
            logging.info("Removed previous stop flag")

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(service_log),
                logging.StreamHandler(sys.stdout),
            ],
        )

        error_handler = logging.FileHandler(error_log)
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

        timestamp = time.time()
        self.audio_queue.put((audio_data.copy(), timestamp))

    def _process_audio(self):
        """Process audio from queue."""
        while self.running:
            try:
                audio_chunk, timestamp = self.audio_queue.get(timeout=1.0)

                result = self.audio_buffer.add_audio(audio_chunk, timestamp)

                if result is not None:
                    audio_data, start_time, end_time = result

                    duration = end_time - start_time
                    buffer_info = (
                        " (with circular buffer)"
                        if VRConfig.USE_CIRCULAR_BUFFER
                        else ""
                    )
                    print(
                        f"🎯 Speech detected: {duration:.1f}s{buffer_info} | Student: {VRConfig.STUDENT_ID} | Video: {VRConfig.VIDEO_ID}"
                    )

                    # Transcribe in separate thread
                    threading.Thread(
                        target=self._transcribe_and_submit,
                        args=(audio_data, start_time, end_time),
                        daemon=True,
                    ).start()

            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"Error processing audio: {e}")

    def _save_audio_segment(
        self, audio_data: np.ndarray, timestamp: str
    ) -> Optional[str]:
        """Save audio segment with student context."""
        if not VRConfig.AUDIO_DIR:
            return None

        try:
            filename = f"speech_{timestamp.replace(':', '-').replace('.', '_')}.wav"
            filepath = Path(VRConfig.AUDIO_DIR) / filename

            # Convert to int16
            audio_int16 = (audio_data * 32767).astype(np.int16)

            with wave.open(str(filepath), "wb") as wav_file:
                wav_file.setnchannels(VRConfig.CHANNELS)
                wav_file.setsampwidth(2)
                wav_file.setframerate(VRConfig.WHISPER_SAMPLE_RATE)
                wav_file.writeframes(audio_int16.tobytes())

            return str(filepath)

        except Exception as e:
            logging.error(f"Failed to save audio segment: {e}")
            return None

    def _transcribe_and_submit(
        self, audio_data: np.ndarray, start_time: float, end_time: float
    ):
        """Transcribe audio and submit to backend."""
        try:
            # Check if recording has been stopped
            if self.stop_flag_file.exists():
                print("🛑 Stop recording flag detected - skipping transcription")
                logging.info("Stop recording flag detected - skipping transcription")
                return

            transcript, confidence = self.transcriber.transcribe(audio_data)

            if transcript:
                # Apply quality filters to reduce noise and false positives
                word_count = len(transcript.split())
                transcript_length = len(transcript.strip())

                # Filter 1: Check confidence threshold
                if confidence < VRConfig.MIN_CONFIDENCE:
                    print(
                        f"🔇 Low confidence ({confidence:.3f} < {VRConfig.MIN_CONFIDENCE}) - skipping: '{transcript[:50]}...'"
                    )
                    logging.info(
                        f"Filtered low confidence ({confidence:.3f}): {transcript}"
                    )
                    return

                # Filter 2: Check minimum transcript length
                if transcript_length < VRConfig.MIN_TRANSCRIPT_LENGTH:
                    print(
                        f"🔇 Too short ({transcript_length} chars < {VRConfig.MIN_TRANSCRIPT_LENGTH}) - skipping: '{transcript}'"
                    )
                    logging.info(f"Filtered short transcript: {transcript}")
                    return

                # Filter 3: Check minimum word count
                if word_count < VRConfig.MIN_WORD_COUNT:
                    print(
                        f"🔇 Too few words ({word_count} < {VRConfig.MIN_WORD_COUNT}) - skipping: '{transcript}'"
                    )
                    logging.info(f"Filtered few-word transcript: {transcript}")
                    return

                # Double-check flag before writing (in case it was set during transcription)
                if self.stop_flag_file.exists():
                    print("🛑 Stop recording flag detected - not writing to log")
                    logging.info("Stop recording flag detected - not writing to log")
                    return

                timestamp_str = datetime.now().isoformat()
                audio_file = self._save_audio_segment(audio_data, timestamp_str)

                # Create log entry for local storage
                log_entry = {
                    "start": round(start_time, 2),
                    "end": round(end_time, 2),
                    "transcript": transcript,
                    "confidence": round(confidence, 3),
                    "timestamp": timestamp_str,
                    "vad_engine": VAD_ENGINE,
                    "circular_buffer": VRConfig.USE_CIRCULAR_BUFFER,
                    "student_id": VRConfig.STUDENT_ID,
                    "video_id": VRConfig.VIDEO_ID,
                    "session_id": VRConfig.SESSION_ID,
                }

                if audio_file:
                    log_entry["audio_file"] = audio_file

                # Write to local JSONL file
                with jsonlines.open(self.log_file, mode="a") as writer:
                    writer.write(log_entry)

                # Submit to backend API for evaluation and database storage
                self._submit_to_backend(
                    transcript, confidence, audio_file, timestamp_str
                )

                # Print result
                print(f"📝 [{confidence:.3f}] {transcript}")
                logging.info(f"Transcribed ({confidence:.3f}): {transcript}")
            else:
                print("🤐 No speech detected in audio segment")

        except Exception as e:
            logging.error(f"Error in transcription: {e}")

    def _submit_to_backend(
        self,
        transcript: str,
        confidence: float,
        audio_file: Optional[str],
        timestamp: str,
    ):
        """Submit transcription result to backend API for evaluation"""
        try:
            import requests

            # Only submit if we have session info
            if (
                not VRConfig.SESSION_ID
                or not VRConfig.STUDENT_ID
                or not VRConfig.VIDEO_ID
            ):
                return

            api_url = "http://127.0.0.1:8000/api/v1/asr/submit-result"

            payload = {
                "session_id": VRConfig.SESSION_ID,
                "student_id": VRConfig.STUDENT_ID,
                "video_id": VRConfig.VIDEO_ID,
                "transcript": transcript,
                "confidence": confidence,
                "audio_file_path": audio_file,
            }

            # Submit asynchronously (don't block transcription)
            response = requests.post(api_url, json=payload, timeout=2)

            if response.status_code == 200:
                result = response.json()
                if result.get("evaluation"):
                    eval_data = result["evaluation"]
                    similarity = eval_data.get("similarity", 0)
                    wer = eval_data.get("wer", 0)
                    matched_ground_truth = eval_data.get("matched_ground_truth", "")
                    print(
                        f"📊 Evaluation: {round(similarity * 100)}% similarity, {round(wer * 100)}% WER"
                    )

                    # Update the JSONL with evaluation results
                    self._update_jsonl_with_evaluation(
                        timestamp, similarity, wer, matched_ground_truth
                    )
            else:
                logging.warning(f"Failed to submit to backend: {response.status_code}")

        except Exception as e:
            # Don't fail if API submission fails
            logging.warning(f"Could not submit to backend API: {e}")

    def _update_jsonl_with_evaluation(
        self,
        timestamp: str,
        similarity: float,
        wer: float,
        matched_ground_truth: str = "",
    ):
        """Update the JSONL entry with evaluation results"""
        try:
            print(f"🔄 Updating JSONL for timestamp: {timestamp}")
            # Read all entries
            entries = []
            with jsonlines.open(self.log_file, mode="r") as reader:
                for entry in reader:
                    entries.append(entry)

            print(f"📖 Read {len(entries)} entries from JSONL")

            # Update the entry with matching timestamp
            updated = False
            for entry in entries:
                if entry.get("timestamp") == timestamp:
                    entry["similarity_score"] = round(similarity, 4)
                    entry["wer"] = round(wer, 4)
                    if matched_ground_truth:
                        entry["matched_ground_truth"] = matched_ground_truth
                    updated = True
                    print(
                        f"✅ Updated entry: similarity={round(similarity, 4)}, wer={round(wer, 4)}"
                    )
                    break

            if not updated:
                print(f"⚠️ No entry found with timestamp: {timestamp}")
                print(
                    f"Available timestamps: {[e.get('timestamp') for e in entries[-3:]]}"
                )

            # Rewrite the file if we updated an entry
            if updated:
                with jsonlines.open(self.log_file, mode="w") as writer:
                    for entry in entries:
                        writer.write(entry)
                print("💾 JSONL file updated with evaluation scores")
                logging.info(
                    f"Updated JSONL with evaluation: {round(similarity * 100)}% similarity"
                )

        except Exception as e:
            print(f"❌ Error updating JSONL: {e}")
            logging.warning(f"Could not update JSONL with evaluation: {e}")

    def start(self):
        """Start the VR ASR service."""
        print("🎤 Starting VR Flight Training ASR Service...")
        print(f"👤 Student: {VRConfig.STUDENT_ID}")
        print(f"🎬 Video: {VRConfig.VIDEO_ID}")
        print(f"📊 VAD Engine: {VAD_ENGINE}")
        print(f"🔊 Sample Rate: {VRConfig.SAMPLE_RATE} Hz")
        print(f"🖥️  Device: {VRConfig.DEVICE}")

        if VRConfig.USE_CIRCULAR_BUFFER:
            print(
                f"🔄 Circular Buffer: {VRConfig.BUFFER_DURATION}s (prevents speech cutoffs)"
            )

        if VRConfig.AUDIO_DIR:
            print(f"🎵 Audio: {VRConfig.AUDIO_DIR}")
        if VRConfig.LOGS_DIR:
            print(f"📁 Logs: {VRConfig.LOGS_DIR}")

        if VRConfig.SHOW_VAD_ACTIVITY:
            print("🐛 Debug mode: ON")

        logging.info("Starting VR ASR Service...")
        logging.info(f"Student: {VRConfig.STUDENT_ID}, Video: {VRConfig.VIDEO_ID}")
        logging.info(
            f"VAD Engine: {VAD_ENGINE}, Sample Rate: {VRConfig.SAMPLE_RATE} Hz"
        )
        logging.info(f"Circular Buffer: {VRConfig.USE_CIRCULAR_BUFFER}")

        self.running = True

        # Start audio processing thread
        audio_thread = threading.Thread(target=self._process_audio, daemon=True)
        audio_thread.start()

        # Start audio capture
        try:
            print("🎧 Initializing audio capture...")

            devices = sd.query_devices()
            input_devices = [d for d in devices if d["max_input_channels"] > 0]
            if input_devices:
                device_to_use = (
                    self.audio_device_id
                    if self.audio_device_id is not None
                    else sd.default.device[0]
                )
                device_info = sd.query_devices(device_to_use)
                print(f"🎙️  Using: {device_info['name']} ({VRConfig.SAMPLE_RATE} Hz)")
            else:
                print("⚠️  No audio input devices found!")

            with sd.InputStream(
                samplerate=VRConfig.SAMPLE_RATE,
                channels=VRConfig.CHANNELS,
                dtype=VRConfig.DTYPE,
                blocksize=VRConfig.CHUNK_SIZE,
                device=self.audio_device_id,
                callback=self._audio_callback,
            ):
                print("✅ Audio capture started successfully!")
                print("🗣️  Listening for speech... (Ctrl+C to stop)")
                if VRConfig.USE_CIRCULAR_BUFFER:
                    print(
                        f"💡 Circular buffer capturing {VRConfig.BUFFER_DURATION}s of extra context!"
                    )
                print()

                logging.info("VR ASR Service started successfully")
                while self.running:
                    time.sleep(0.1)

        except Exception as e:
            logging.error(f"Audio capture failed: {e}")
            self.running = False

    def stop(self):
        """Stop the VR ASR service."""
        logging.info("Stopping VR ASR Service...")
        self.running = False


def load_session_config(student_id: str = None) -> Optional[Dict[str, Any]]:
    """Load session configuration from file or environment."""
    # Try to load from session file first
    if student_id:
        config_dir = Path("data/asr_sessions")
        config_file = config_dir / f"session_{student_id}.json"

        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    config = json.load(f)
                    print(f"📄 Loaded session config for student: {student_id}")
                    return config
            except Exception as e:
                print(f"⚠️  Error loading session config: {e}")

    # Fallback to environment variables or default
    return {
        "student_id": os.environ.get("VR_STUDENT_ID", student_id),
        "video_id": os.environ.get("VR_VIDEO_ID"),
        "session_id": os.environ.get("VR_SESSION_ID"),
        "audio_dir": os.environ.get("VR_AUDIO_DIR"),
        "logs_dir": os.environ.get("VR_LOGS_DIR"),
    }


def main():
    """Main entry point for VR ASR service."""
    import argparse

    parser = argparse.ArgumentParser(
        description="VR Flight Training ASR Service with Circular Buffer"
    )
    parser.add_argument("--student-id", help="Student ID for session context")
    parser.add_argument("--video-id", help="Video ID for session context")
    parser.add_argument("--session-id", help="Session ID for backend integration")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--device", type=int, help="Audio input device ID")

    args = parser.parse_args()

    # Load session configuration
    session_config = load_session_config(args.student_id)

    # Override with command line arguments
    if args.student_id:
        session_config["student_id"] = args.student_id
    if args.video_id:
        session_config["video_id"] = args.video_id
    if args.session_id:
        session_config["session_id"] = args.session_id

    if args.debug:
        os.environ["ASR_DEBUG"] = "1"
        VRConfig.SHOW_VAD_ACTIVITY = True

    # Validate session config
    if not session_config.get("student_id"):
        print("❌ Error: Student ID is required")
        print("Use --student-id or set VR_STUDENT_ID environment variable")
        sys.exit(1)

    print("🚀 Starting VR ASR Service with Circular Buffer")
    print(f"👤 Student ID: {session_config.get('student_id')}")
    print(f"🎬 Video ID: {session_config.get('video_id', 'N/A')}")

    # Initialize and start service
    service = VRASRService(audio_device_id=args.device, session_config=session_config)

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
