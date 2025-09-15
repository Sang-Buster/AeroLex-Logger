#!/usr/bin/env python3
"""
ASR Pipeline Installation Test Script
Verifies all dependencies and components are working correctly.
"""

import importlib
import sys
from pathlib import Path


def test_python_version():
    """Test Python version compatibility."""
    print("Testing Python version...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro} is compatible")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor}.{version.micro} is too old (need 3.8+)")
        return False

def test_dependencies():
    """Test required Python packages."""
    print("\nTesting Python dependencies...")
    
    required_packages = [
        ('torch', 'PyTorch'),
        ('numpy', 'NumPy'),
        ('sounddevice', 'SoundDevice'),
        ('faster_whisper', 'Faster Whisper'),
        ('jsonlines', 'JSON Lines'),
    ]
    
    optional_packages = [
        ('webrtcvad', 'WebRTC VAD'),
        ('silero_vad', 'Silero VAD'),
    ]
    
    all_good = True
    
    # Test required packages
    for package, name in required_packages:
        try:
            importlib.import_module(package)
            print(f"✓ {name} is installed")
        except ImportError:
            print(f"✗ {name} is missing - install with: pip install {package}")
            all_good = False
    
    # Test optional packages (VAD engines)
    vad_available = False
    for package, name in optional_packages:
        try:
            importlib.import_module(package)
            print(f"✓ {name} is available")
            vad_available = True
        except ImportError:
            print(f"○ {name} not available (optional)")
    
    if not vad_available:
        print("⚠ No VAD engines found - install at least one: webrtcvad, silero-vad")
        all_good = False
    
    return all_good

def test_cuda():
    """Test CUDA availability."""
    print("\nTesting CUDA availability...")
    
    try:
        import torch
        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            device_name = torch.cuda.get_device_name(0) if device_count > 0 else "Unknown"
            print(f"✓ CUDA available: {device_count} device(s)")
            print(f"  Primary GPU: {device_name}")
            
            # Test GPU memory
            if device_count > 0:
                memory_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
                print(f"  GPU Memory: {memory_gb:.1f} GB")
                
                if memory_gb >= 20:  # RTX 3090 has 24GB
                    print("✓ Sufficient GPU memory for large-v3-turbo")
                else:
                    print("⚠ Limited GPU memory - consider using smaller model")
            
            return True
        else:
            print("✗ CUDA not available - will use CPU (slower)")
            return False
    except ImportError:
        print("✗ PyTorch not installed")
        return False

def test_audio_devices():
    """Test audio input devices."""
    print("\nTesting audio devices...")
    
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        
        input_devices = [d for d in devices if d['max_input_channels'] > 0]
        
        if input_devices:
            print(f"✓ Found {len(input_devices)} audio input device(s):")
            for i, device in enumerate(input_devices[:3]):  # Show first 3
                print(f"  {device['name']} ({device['max_input_channels']} channels)")
            return True
        else:
            print("✗ No audio input devices found")
            return False
            
    except ImportError:
        print("○ SoundDevice not available, trying PyAudio...")
        
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            
            input_devices = []
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    input_devices.append(info)
            
            p.terminate()
            
            if input_devices:
                print(f"✓ Found {len(input_devices)} audio input device(s) via PyAudio")
                return True
            else:
                print("✗ No audio input devices found via PyAudio")
                return False
                
        except ImportError:
            print("✗ No audio libraries available")
            return False

def test_whisper_model():
    """Test Whisper model loading and download if needed."""
    print("\nTesting Whisper model...")
    
    try:
        from faster_whisper import WhisperModel
        
        # Check if model directory exists
        models_dir = Path("models")
        if models_dir.exists():
            print(f"✓ Models directory exists: {models_dir}")
        else:
            print("○ Models directory will be created on first run")
        
        # Try to load the model (this will download if not present)
        print("Loading Whisper large-v3-turbo...")
        print("  (This may take several minutes on first run to download ~1.6GB model)")
        
        model = WhisperModel(
            "large-v3-turbo",
            device="cpu",  # Use CPU for test to avoid GPU memory issues
            compute_type="int8",
            download_root=str(models_dir) if models_dir.exists() else None
        )
        
        print("✓ Whisper model loaded successfully")
        
        # Test with dummy audio
        import numpy as np
        test_audio = np.zeros(16000, dtype=np.float32)  # 1 second of silence
        
        print("  Running inference test...")
        segments, info = model.transcribe(test_audio)
        print(f"✓ Model inference test passed (detected language: {info.language})")
        
        # Check model size on disk
        if models_dir.exists():
            total_size = sum(f.stat().st_size for f in models_dir.rglob('*') if f.is_file())
            size_mb = total_size / (1024 * 1024)
            print(f"  Model size on disk: {size_mb:.1f} MB")
        
        return True
        
    except Exception as e:
        print(f"✗ Whisper model test failed: {e}")
        print("  This might be due to:")
        print("    - Network connection issues during download")
        print("    - Insufficient disk space")
        print("    - Missing dependencies")
        print("  Try running: python download_model.py")
        return False

def test_vad_engines():
    """Test available VAD engines."""
    print("\nTesting VAD engines...")
    
    vad_engines = [
        ('webrtcvad', 'WebRTC VAD'),
        ('silero_vad', 'Silero VAD'),
    ]
    
    available_engines = []
    
    for package, name in vad_engines:
        try:
            if package == 'webrtcvad':
                import webrtcvad
                # Test basic functionality
                webrtcvad.Vad(3)  # Just test creation
                print(f"✓ {name} is working")
                available_engines.append(name)
            elif package == 'silero_vad':
                from silero_vad import load_silero_vad
                # Test basic functionality
                load_silero_vad()  # Just test loading
                print(f"✓ {name} is working")
                available_engines.append(name)
        except ImportError:
            print(f"○ {name} not available")
        except Exception as e:
            print(f"⚠ {name} installed but not working: {e}")
    
    if available_engines:
        print(f"✓ Available VAD engines: {', '.join(available_engines)}")
        return True
    else:
        print("✗ No working VAD engines found")
        print("  Install with: pip install webrtcvad silero-vad")
        return False

def test_file_structure():
    """Test required files are present."""
    print("\nTesting file structure...")
    
    base_dir = Path(__file__).parent
    required_files = [
        'asr_service.py',
        'download_model.py',
        'requirements.txt',
        'README.md',
        'asr.service',
        'install_service.bat',
        'install_linux.sh'
    ]
    
    all_present = True
    for filename in required_files:
        filepath = base_dir / filename
        if filepath.exists():
            print(f"✓ {filename} present")
        else:
            print(f"✗ {filename} missing")
            all_present = False
    
    # Check logs directory
    logs_dir = base_dir / 'logs'
    if logs_dir.exists():
        print("✓ logs/ directory present")
    else:
        print("○ logs/ directory will be created on first run")
    
    return all_present

def main():
    """Run all tests."""
    print("ASR Pipeline Installation Test")
    print("=" * 50)
    
    tests = [
        ("Python Version", test_python_version),
        ("Dependencies", test_dependencies),
        ("CUDA Support", test_cuda),
        ("Audio Devices", test_audio_devices),
        ("VAD Engines", test_vad_engines),
        ("File Structure", test_file_structure),
        ("Whisper Model", test_whisper_model),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * len(test_name))
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"{test_name:20} {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! ASR Pipeline is ready to use.")
        print("\nNext steps:")
        print("1. Run: python asr_service.py (for manual testing)")
        print("2. Linux: ./install_linux.sh (for service installation)")
        print("3. Windows: install_service.bat (for service installation)")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please address issues before deployment.")
        
        if not results.get("Dependencies", False):
            print("\n💡 Try: pip install -r requirements.txt")
        
        if not results.get("Whisper Model", False):
            print("💡 Try: python download_model.py")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
