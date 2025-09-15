#!/usr/bin/env python3
"""
Audio Debug Script for ASR Pipeline
Helps diagnose audio input and VAD issues, especially with Bluetooth devices.
"""

import time

import numpy as np
import sounddevice as sd
import torch
from silero_vad import get_speech_timestamps, load_silero_vad


def list_audio_devices():
    """List all available audio devices."""
    print("🎧 Available Audio Devices:")
    print("=" * 50)

    devices = sd.query_devices()
    input_devices = []

    for i, device in enumerate(devices):
        if device["max_input_channels"] > 0:
            input_devices.append((i, device))
            status = "📍 DEFAULT" if i == sd.default.device[0] else "  "
            print(f"{status} [{i:2d}] {device['name']}")
            print(
                f"      Channels: {device['max_input_channels']}, Sample Rate: {device['default_samplerate']}"
            )

    print(f"\nFound {len(input_devices)} input device(s)")
    return input_devices


def test_audio_levels(device_id=None, duration=5):
    """Test audio input levels from specified device."""
    print(f"\n🔊 Testing Audio Levels (Device: {device_id or 'default'})")
    print("=" * 50)
    print("Speak into your microphone for 5 seconds...")
    print("You should see audio levels if the microphone is working.")
    print()

    sample_rate = 16000
    chunk_size = 1024
    audio_data = []

    def audio_callback(indata, frames, time, status):
        if status:
            print(f"Audio status: {status}")

        # Convert to mono
        if indata.shape[1] > 1:
            mono_data = np.mean(indata, axis=1)
        else:
            mono_data = indata[:, 0]

        audio_data.extend(mono_data)

        # Calculate and display level
        level = np.sqrt(np.mean(mono_data**2))
        if level > 0.001:  # Only show if there's some audio
            bar_length = int(level * 50)
            bar = "█" * bar_length + "░" * (20 - bar_length)
            print(f"\rLevel: {level:.4f} |{bar[:20]}|", end="", flush=True)

    try:
        with sd.InputStream(
            device=device_id,
            samplerate=sample_rate,
            channels=1,
            dtype=np.float32,
            blocksize=chunk_size,
            callback=audio_callback,
        ):
            time.sleep(duration)

        print("\n")

        if audio_data:
            total_level = np.sqrt(np.mean(np.array(audio_data) ** 2))
            print(f"Average audio level: {total_level:.4f}")

            if total_level < 0.001:
                print("⚠️  Very low audio levels detected!")
                print("   - Check microphone volume/gain")
                print("   - Ensure microphone is not muted")
                print("   - For Bluetooth: check connection quality")
            else:
                print("✅ Audio input is working!")

            return np.array(audio_data, dtype=np.float32)
        else:
            print("❌ No audio data captured")
            return None

    except Exception as e:
        print(f"\n❌ Audio test failed: {e}")
        return None


def test_vad_engine(audio_data):
    """Test Silero VAD engine on captured audio."""
    if audio_data is None or len(audio_data) == 0:
        print("No audio data to test VAD engine")
        return

    print(f"\n🤖 Testing Silero VAD on {len(audio_data) / 16000:.1f}s of audio")
    print("=" * 50)

    # Test Silero VAD
    try:
        model = load_silero_vad()
        audio_tensor = torch.from_numpy(audio_data)

        speech_timestamps = get_speech_timestamps(audio_tensor, model)

        if speech_timestamps:
            total_speech_time = sum([(end - start) for start, end in speech_timestamps])
            total_time = len(audio_data)
            speech_percentage = (total_speech_time / total_time) * 100
            print(
                f"Silero VAD: {len(speech_timestamps)} speech segments, {speech_percentage:.1f}% speech"
            )
            
            # Show individual segments
            for i, (start, end) in enumerate(speech_timestamps[:5]):  # Show first 5
                duration = (end - start) / 16000  # Convert samples to seconds
                start_time = start / 16000
                print(f"  Segment {i+1}: {start_time:.2f}s - {start_time + duration:.2f}s ({duration:.2f}s)")
            
            if len(speech_timestamps) > 5:
                print(f"  ... and {len(speech_timestamps) - 5} more segments")
        else:
            print("Silero VAD: No speech detected")

    except Exception as e:
        print(f"Silero VAD failed: {e}")
        print("Make sure you have torch and silero-vad installed:")


def main():
    """Main debug function."""
    print("🐛 ASR Pipeline Audio Debug Tool")
    print("=" * 50)

    # List devices
    input_devices = list_audio_devices()

    if not input_devices:
        print("❌ No audio input devices found!")
        return

    # Ask user to select device or use default
    print("\nOptions:")
    print("1. Test default device")
    print("2. Select specific device")
    print("3. Test all input devices")

    try:
        choice = input("\nEnter choice (1-3): ").strip()

        if choice == "1":
            # Test default device
            audio_data = test_audio_levels()
            test_vad_engine(audio_data)

        elif choice == "2":
            # Select specific device
            device_id = int(input("Enter device ID: "))
            audio_data = test_audio_levels(device_id)
            test_vad_engine(audio_data)

        elif choice == "3":
            # Test all devices
            for device_id, device_info in input_devices:
                print(f"\n{'=' * 60}")
                print(f"Testing Device [{device_id}]: {device_info['name']}")
                print(f"{'=' * 60}")
                audio_data = test_audio_levels(device_id, duration=3)
                test_vad_engine(audio_data)

        else:
            print("Invalid choice")

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")

    print("\n💡 Troubleshooting Tips:")
    print("- If audio levels are very low, check microphone gain/volume")
    print("- For Bluetooth devices, try reconnecting or check codec compatibility")
    print("- Silero VAD works best with clear speech and minimal background noise")
    print("- Use: ASR_DEBUG=1 uv run asr_service.py to see VAD activity")


if __name__ == "__main__":
    main()
