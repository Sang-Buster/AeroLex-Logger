# ASR Pipeline - Local Speech Recognition Service

A robust, cross-platform automatic speech recognition (ASR) pipeline designed for continuous audio monitoring and transcription. Built for deployment on any system (CPU or GPU) with local Whisper large-v3-turbo inference. Optimized for NVIDIA GPU acceleration when available.

## 🎯 Features

- **Local Processing**: No cloud API calls - everything runs locally
- **Real-time VAD**: Voice Activity Detection using Silero VAD
- **GPU Acceleration**: Whisper large-v3-turbo with optional CUDA support (CPU mode also available)
- **Cross-Platform**: Works on Windows, Linux, and macOS
- **Persistent Service**: Auto-start and auto-restart capabilities
- **Robust Audio Capture**: Automatic microphone failover and recovery
- **JSON Logging**: Structured output with timestamps and confidence scores
- **ASR Evaluation**: Built-in tools for accuracy assessment with ground truth data
- **Easy Deployment**: Simple setup for mass deployment across multiple systems
- **Circular Buffer Recording**: Control+Backtick push-to-talk with 5s pre/post buffering (see [README_VR_TRAINING.md](README_VR_TRAINING.md))

## 🏗️ Architecture

```
Microphone → Audio Buffer → Silero VAD → Whisper large-v3-turbo → JSON Logs + Audio Files
     ↓            ↓             ↓              ↓                    ↓
  16kHz Mono   Real-time    Speech/Silence   GPU Inference    Structured Output + WAV
                           (ML-based)
```

## 📁 Project Structure

```
📦aerolex-logger
 ┣ 📂audios                             # Saved audio segments (WAV files)
 ┣ 📂backend                            # FastAPI backend
 ┃ ┣ 📂api                              # API routes
 ┃ ┣ 📂database                         # Database models and connection
 ┃ ┣ 📂services                         # Business logic services
 ┃ ┣ 📂static                           # Static files served by backend
 ┃ ┗ 📄main.py                          # Backend server entry point
 ┣ 📂data                               # Application data directory
 ┃ ┣ 📂asr_sessions                     # ASR session data
 ┃ ┣ 📂ground_truth                     # Ground truth data files
 ┃ ┣ 📄ground_truth.txt                 # Ground truth text for evaluation
 ┃ ┗ 📄vr_training.db                   # SQLite database for VR training
 ┣ 📂logs                               # Log output directory
 ┣ 📂models                             # Whisper models (auto-downloaded)
 ┣ 📂src                                # Core Python scripts
 ┃ ┣ 📄asr_evaluate.py                  # ASR evaluation and accuracy metrics
 ┃ ┣ 📄asr_service.py                   # ASR service script
 ┃ ┣ 📄asr_service_buffered.py          # ASR with circular buffer
 ┃ ┣ 📄asr_service_vr.py                # ASR service for VR training
 ┃ ┣ 📄download_model.py                # Model download and verification
 ┃ ┣ 📄test_audio.py                    # Audio debugging utilities
 ┃ ┣ 📄test_backend.py                  # Backend testing utilities
 ┃ ┣ 📄test_cleanup_videos_names.py     # Video filename cleanup utility
 ┃ ┗ 📄test_installation.py             # Installation verification
 ┣ 📂videos                             # Video files directory
 ┣ 📂web                                # Web interface
 ┃ ┣ 📂assets                           # Web assets
 ┃ ┃ ┣ 📂css                            # Stylesheets
 ┃ ┃ ┣ 📂img                            # Images
 ┃ ┃ ┗ 📂js                             # JavaScript files
 ┃ ┗ 📄index.html                       # Main web page
 ┣ 📄.env.example                       # Example environment variables
 ┣ 📄.gitignore                         # Git ignore file
 ┣ 📄.pre-commit-config.yaml            # Pre-commit configuration
 ┣ 📄.python-version                    # Python version
 ┣ 📄README.md                          # Project documentation
 ┣ 📄asr_config.ini                     # ASR Configuration
 ┣ 📄asr.service                        # Linux systemd unit file
 ┣ 📄asr.service.bat                    # Windows service runner
 ┣ 📄install_linux.sh                   # Linux installation script
 ┣ 📄install_windows.bat                # Windows installation script
 ┣ 📄pyproject.toml                     # Python project configuration and dependencies
 ┣ 📄start_backend.py                   # Backend startup script
 ┣ 📄start_vr_asr.py                    # VR ASR service startup script
 ┗ 📄uv.lock                            # uv lock file
```

## 🚀 Quick Start

### Prerequisites

- **Hardware**: NVIDIA GPU (optional but recommended for best performance), CPU-only mode supported
- **OS**: Windows 10/11, Linux (Ubuntu 20.04+ recommended), or macOS
- **Python**: 3.10+ (automatically managed by uv)
- **Package Manager**: uv (automatically installed by setup scripts)
- **Project Management**: Uses `pyproject.toml` for modern Python dependency management
- **CUDA**: 12.1 or newer (optional, for GPU acceleration on Windows/Linux)
- **Audio**: Working microphone input

### 1. Clone and Setup

```bash
# Clone or copy the asr-pipeline directory to your target location
cd asr-pipeline

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies and create virtual environment (uses pyproject.toml)
# This automatically creates a virtual environment and installs all dependencies
uv sync

# Download and verify Whisper model
uv run src/download_model.py

# Test installation
uv run src/test_installation.py
```

### Optional: GPU Acceleration (Windows/Linux with NVIDIA GPU)

By default, PyTorch installs with CPU support for cross-platform compatibility. If you have an NVIDIA GPU and want to enable GPU acceleration:

```bash
# Reinstall PyTorch with CUDA support on Linux/Mac
uv pip install  --reinstall torch torchaudio torchvision
# Verify GPU is available:
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}')"
```

**Platform Notes:**

- **Windows/Linux with NVIDIA GPU**: Follow the steps above for GPU acceleration (recommended for best performance)
- **Mac**: CPU or Metal acceleration is automatically configured, no additional steps needed
- **Linux without NVIDIA GPU**: CPU-only installation works out of the box

**Performance Impact:**

- **CPU**: ~5-10x slower inference, but works everywhere
- **GPU**: Optimized for real-time transcription on NVIDIA GPUs (CUDA 12.1 recommended)

### 2. Test Installation

```bash
# Test the service manually (Ctrl+C to stop)
uv run src/asr_service.py

# Or with debug mode to see VAD activity
ASR_DEBUG=1 uv run src/asr_service.py
```

The service should start capturing audio and display VAD engine information. Speak into your microphone and check `logs/asr_results.jsonl` for transcription results.

### 3. Install as Service

#### Linux (systemd)

```bash
# Use the automated installer
chmod +x install_linux.sh
./install_linux.sh
```

This approach:

- ✅ Runs from current directory (no file copying)
- ✅ Uses your current user account
- ✅ Uses `.venv/bin/python` directly
- ✅ Simple to maintain and update
- ✅ Logs stored in your local `./logs/` directory

**Service Management:**

```bash
# Start/Stop/Status
sudo systemctl start asr.service
sudo systemctl stop asr.service
sudo systemctl status asr.service
sudo journalctl -u asr.service -f

# View live transcriptions
tail -f logs/asr_results.jsonl | jq '.transcript'
```

#### Windows (Task Scheduler)

```batch
# Run as Administrator (one-time setup)
install_windows.bat
```

The installer will:

- Install dependencies and create virtual environment
- Download Whisper model
- Create a system-level scheduled task that runs on user logon
- Configure automatic restart on failure
- Set up proper working directory and permissions
- Run with elevated privileges for hardware access

After installation, the service runs automatically. To manually start/stop:

```batch
# Start service
schtasks /run /tn "ASR_Pipeline"

# Stop service
taskkill /f /im python.exe

# Check logs
type logs\asr.out
```

## 📊 Output Format

Transcription results are saved to `logs/asr_results.jsonl` in JSON Lines format:

```json
{"start": 12.4, "end": 16.8, "transcript": "Tower Cessna 123 ready for takeoff", "confidence": 0.91, "timestamp": "2025-09-15T10:30:45.123456", "vad_engine": "silero", "audio_file": "audios/speech_2025-09-15T10-30-45_123456.wav"}
{"start": 20.1, "end": 23.7, "transcript": "Roger Cessna 123 cleared for takeoff runway 07", "confidence": 0.94, "timestamp": "2025-09-15T10:30:48.789012", "vad_engine": "silero", "audio_file": "audios/speech_2025-09-15T10-30-48_789012.wav"}
```

### Fields

- `start`: Speech segment start time (seconds since service start)
- `end`: Speech segment end time (seconds since service start)
- `transcript`: Transcribed text
- `confidence`: Confidence score (0.0-1.0, higher is better)
- `timestamp`: ISO format timestamp when transcription completed
- `vad_engine`: VAD engine used (silero)
- `audio_file`: Path to saved WAV file containing the audio segment

## 📈 ASR Evaluation

The pipeline includes built-in evaluation tools to assess transcription accuracy against ground truth data.

### Features

- **Levenshtein Distance**: Character-level edit distance
- **Word Error Rate (WER)**: Industry standard for speech recognition
- **Character Error Rate (CER)**: Character-level accuracy
- **Text Alignment**: Fuzzy matching for multiple text segments
- **Batch Processing**: Process entire ASR result files
- **Detailed Analysis**: Error breakdowns and unmatched segments

### Usage

#### 1. Batch Evaluation (Recommended)

Compare your ASR results against ground truth:

```bash
# Basic evaluation
uv run src/asr_evaluate.py data/ground_truth.txt logs/asr_results.jsonl

# With detailed output and custom threshold
uv run src/asr_evaluate.py data/ground_truth.txt logs/asr_results.jsonl -o detailed_results.json -t 0.4
```

#### 2. Direct Text Comparison

Compare two specific texts:

```bash
uv run src/asr_evaluate.py --compare "Hello world" "Hello word"
```

### Ground Truth File Formats

#### Text File (.txt)

```
Hello world
This is a test
Aviation communication
```

#### JSON File (.json)

```json
{
  "ground_truth": ["Hello world", "This is a test", "Aviation communication"]
}
```

Or simple list:

```json
["Hello world", "This is a test", "Aviation communication"]
```

### Evaluation Metrics

- **WER (Word Error Rate)**: Percentage of words that are wrong
- **CER (Character Error Rate)**: Percentage of characters that are wrong
- **Word/Character Accuracy**: 1 - Error Rate
- **Similarity Score**: Overall text similarity (0-1)
- **Match Rate**: Percentage of transcriptions matched to ground truth
- **Coverage Rate**: Percentage of ground truth covered by transcriptions

### Example Evaluation Output

```
📊 ASR EVALUATION SUMMARY
============================================================
Total ASR Results:        6
Total Ground Truth:       10
Matched Transcriptions:   5
Unmatched Transcriptions: 1
Unmatched Ground Truth:   5

Match Rate:               83.3%
Coverage Rate:            50.0%

ACCURACY METRICS (for matched transcriptions):
Average Word Error Rate:  15.2%
Average Char Error Rate:  8.1%
Average Word Accuracy:    84.8%
Average Character Accuracy: 91.9%
Average Similarity:       87.4%
```

### Evaluation Parameters

- `-t, --threshold`: Similarity threshold for matching (0.0-1.0, default: 0.3)
- `-o, --output`: Save detailed results to JSON file
- `--compare`: Direct comparison mode for two texts

### How Matching Works

The evaluation script uses fuzzy matching to align ASR transcriptions with ground truth segments:

1. **Normalization**: Removes punctuation, converts to lowercase
2. **Similarity Calculation**: Uses SequenceMatcher for text similarity
3. **Threshold Matching**: Only matches above similarity threshold
4. **Best Match Selection**: Finds highest similarity ground truth for each transcription

This handles cases where users speak segments in different order or with variations.

## ⚙️ Configuration

### Audio Settings

Edit `src/asr_service.py` to modify audio capture parameters:

```python
class Config:
    SAMPLE_RATE = 16000      # Audio sample rate
    CHANNELS = 1             # Mono audio
    CHUNK_SIZE = 1024        # Buffer size (adjust for performance)

    # VAD settings
    SPEECH_TIMEOUT = 1.0     # Silence duration to end speech segment
    MIN_SPEECH_DURATION = 0.5 # Minimum speech length to process
    OVERLAP_DURATION = 0.3   # Overlap between segments

    # Audio storage
    SAVE_AUDIO_SEGMENTS = True  # Set to False to disable audio saving
    AUDIO_DIR = "../audios"     # Directory for saved audio files
```

### VAD Engine

The service uses Silero VAD, a machine learning-based Voice Activity Detection engine that provides:

- **High Accuracy**: ML-based detection works well in noisy environments
- **Robust Performance**: Better handling of various audio conditions
- **No Compilation Issues**: Pure Python implementation with PyTorch
- **Real-time Processing**: Optimized for continuous audio streams

Silero VAD automatically adapts to different audio conditions and provides more reliable speech detection compared to traditional signal processing approaches.

### GPU Settings

The service automatically detects CUDA availability. To force CPU usage:

```bash
CUDA_VISIBLE_DEVICES="" uv run src/asr_service.py
```

## 🔧 Troubleshooting

### Common Issues

#### No Audio Input

```bash
# Linux: Check audio devices
arecord -l

# Test audio with debug script
uv run src/test_audio.py

# Windows: Check Windows Sound settings
# Ensure microphone is set as default recording device and not muted
```

#### CUDA Not Available

```bash
# Check NVIDIA driver
nvidia-smi

# Check PyTorch CUDA
python -c "import torch; print(torch.cuda.is_available())"
```

#### VAD Engine Not Found

The service uses Silero VAD for voice activity detection.

Install VAD engine:

```bash
pip install silero-vad torch
```

#### Service Won't Start

**Linux:**

```bash
# Check service logs
sudo journalctl -u asr.service -f

# Check file permissions (if needed)
ls -la logs/ models/ audios/
```

**Windows:**

```batch
# Check scheduled task
schtasks /query /tn "ASR_Pipeline" /v

# Check if Python is in system PATH
where python
```

### Performance Tuning

#### For RTX 3090 Optimization

1. **Memory**: Service uses ~4-6GB GPU memory with large-v3-turbo
2. **CPU**: VAD processing is CPU-bound, ensure adequate CPU resources
3. **Disk**: Fast SSD recommended for model loading and log writing

#### Batch Processing

For higher throughput, consider adjusting:

- `CHUNK_SIZE`: Larger chunks reduce CPU overhead
- `SPEECH_TIMEOUT`: Longer timeout captures more complete sentences
- Multiple instances with different audio inputs

## 📈 Monitoring

### Service Health

**Linux:**

```bash
# Service status
sudo systemctl status asr.service

# Live logs
sudo journalctl -u asr.service -f

# Resource usage
htop -p $(pgrep -f asr_service.py)
```

**Windows:**

```batch
# Task status
schtasks /query /tn "ASR_Pipeline"

# Process monitoring
tasklist | findstr python.exe

# Event logs
eventvwr.msc (check Task Scheduler logs)
```

### Log Analysis

```bash
# Count transcriptions per hour
grep $(date +%Y-%m-%d) logs/asr_results.jsonl | wc -l

# Average confidence scores
jq '.confidence' logs/asr_results.jsonl | awk '{sum+=$1} END {print sum/NR}'

# Recent transcriptions
tail -f logs/asr_results.jsonl | jq '.transcript'
```

### Evaluation Monitoring

```bash
# Regular accuracy assessment
uv run src/asr_evaluate.py data/ground_truth.txt logs/asr_results.jsonl -o daily_eval.json

# Track accuracy over time
for file in logs/asr_results_*.jsonl; do
  echo "Evaluating $file"
  uv run src/asr_evaluate.py data/ground_truth.txt "$file"
done
```

## 🥽 VR Headset Setup

To use the 360° VR training videos with a VR headset, you need to enable HTTPS (required by WebXR):

### Quick Setup

```bash
# 1. Generate SSL certificate (one-time setup)
python3 generate_cert.py

# 2. Start backend with HTTPS
python3 start_backend.py

# 3. Find your computer's IP
ifconfig | grep 'inet ' | grep -v '127.0.0.1'  # Linux/Mac
ipconfig | findstr "IPv4"                       # Windows

# 4. Open in VR headset browser
# https://YOUR_IP:8000/static
```

### Entering VR Mode

1. Open a 360° video in the web interface
2. Look for the **VR button** (🥽 icon) in the bottom-right corner
3. Click it to enter immersive VR mode
4. Grant permission when prompted to access your VR headset

**📖 For detailed instructions, troubleshooting, and supported headsets, see [VR_SETUP_GUIDE.md](VR_SETUP_GUIDE.md)**

## 🔒 Security Considerations

- Service runs with minimal privileges
- No network connections required
- Audio data processed locally only
- Consider disk encryption for sensitive environments
- Regular log rotation recommended
- Self-signed SSL certificates are for local development only

## 🆘 Support

### Logs Location

- **Linux**: `<your-asr-directory>/logs/`
- **Windows**: `<installation-directory>\logs\`

### Performance Metrics

Monitor these files for service health:

- `asr.out`: Service status and info messages
- `asr.err`: Error messages and warnings
- `asr_results.jsonl`: Transcription output

### Getting Help

1. Check service logs first
2. Verify hardware requirements
3. Test with `python src/asr_service.py` manually
4. Check microphone permissions and hardware
5. Run evaluation tools to assess accuracy
6. Use `uv run src/test_audio.py` for audio debugging

---

**Note**: This pipeline is optimized for aviation communication transcription but works for any English speech recognition task. For other languages, modify the `language="en"` parameter in the Whisper transcription call.
