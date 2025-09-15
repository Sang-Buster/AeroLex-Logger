# ASR Pipeline - Local Speech Recognition Service

A robust, cross-platform automatic speech recognition (ASR) pipeline designed for continuous audio monitoring and transcription. Built for deployment on RTX 3090 equipped systems with local Whisper large-v3-turbo inference.

## 🎯 Features

- **Local Processing**: No cloud API calls - everything runs locally
- **Real-time VAD**: Voice Activity Detection using WebRTC VAD or Silero VAD
- **GPU Acceleration**: Whisper large-v3-turbo with CUDA support on RTX 3090
- **Cross-Platform**: Works on both Windows and Linux
- **Persistent Service**: Auto-start and auto-restart capabilities
- **Robust Audio Capture**: Automatic microphone failover and recovery
- **JSON Logging**: Structured output with timestamps and confidence scores
- **Easy Deployment**: Simple setup for mass deployment across multiple systems

## 🏗️ Architecture

```
Microphone → Audio Buffer → VAD Engine → Whisper large-v3-turbo → JSON Logs
     ↓            ↓             ↓              ↓                    ↓
  16kHz Mono   Real-time    Speech/Silence   GPU Inference    Structured Output
                           (WebRTC/Silero)
```

## 📁 Project Structure

```
asr-pipeline/
├── asr_service.py          # Main service script
├── download_model.py       # Model download and verification
├── requirements.txt        # Python dependencies
├── asr.service            # Linux systemd unit file
├── install_service.bat    # Windows service installer
├── README.md              # This file
└── logs/                  # Log output directory
    ├── asr_results.jsonl  # Transcription results
    ├── asr.out           # Service stdout logs
    └── asr.err           # Service error logs
```

## 🚀 Quick Start

### Prerequisites

- **Hardware**: RTX 3090 or compatible NVIDIA GPU
- **OS**: Windows 10/11 or Linux (Ubuntu 20.04+ recommended)
- **Python**: 3.10 (automatically managed by uv)
- **Package Manager**: uv (automatically installed by setup scripts)
- **CUDA**: 11.8 or newer (for GPU acceleration)
- **Audio**: Working microphone input

### 1. Clone and Setup

```bash
# Clone or copy the asr-pipeline directory to your target location
cd asr-pipeline

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv -p 3.10
uv pip install -r requirements.txt

# Download and verify Whisper model
uv run download_model.py

# Test installation
uv run test_installation.py
```

### 2. Test Installation

```bash
# Test the service manually (Ctrl+C to stop)
uv run asr_service.py

# Or with debug mode to see VAD activity
ASR_DEBUG=1 uv run asr_service.py

# Or switch to Silero VAD
ASR_VAD=silero ASR_DEBUG=1 uv run asr_service.py
```

The service should start capturing audio and display VAD engine information. Speak into your microphone and check `logs/asr_results.jsonl` for transcription results.

### 3. Install as Service

#### Linux (systemd)

```bash
# Copy service file to systemd directory
sudo cp asr.service /etc/systemd/system/

# Create service user and directories
sudo useradd -r -s /bin/false asr
sudo mkdir -p /opt/asr
sudo cp -r . /opt/asr/
sudo chown -R asr:asr /opt/asr

# Install uv and setup environment
curl -LsSf https://astral.sh/uv/install.sh | sh
sudo -u asr uv venv /opt/asr/venv -p 3.10
sudo -u asr uv pip install -r /opt/asr/requirements.txt --python /opt/asr/venv/bin/python

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable asr.service
sudo systemctl start asr.service

# Check status
sudo systemctl status asr.service
```

#### Windows (Task Scheduler)

```batch
# Run as Administrator
install_service.bat
```

The installer will:
- Create a scheduled task that runs on user logon
- Configure automatic restart on failure
- Set up proper working directory and permissions

## 📊 Output Format

Transcription results are saved to `logs/asr_results.jsonl` in JSON Lines format:

```json
{"start": 12.4, "end": 16.8, "transcript": "Tower Cessna 123 ready for takeoff", "confidence": 0.91, "timestamp": "2025-09-15T10:30:45.123456", "vad_engine": "webrtc"}
{"start": 20.1, "end": 23.7, "transcript": "Roger Cessna 123 cleared for takeoff runway 07", "confidence": 0.94, "timestamp": "2025-09-15T10:30:48.789012", "vad_engine": "webrtc"}
```

### Fields

- `start`: Speech segment start time (seconds since service start)
- `end`: Speech segment end time (seconds since service start)
- `transcript`: Transcribed text
- `confidence`: Confidence score (0.0-1.0, higher is better)
- `timestamp`: ISO format timestamp when transcription completed
- `vad_engine`: VAD engine used (webrtc or silero)

## ⚙️ Configuration

### Audio Settings

Edit `asr_service.py` to modify audio capture parameters:

```python
class Config:
    SAMPLE_RATE = 16000      # Audio sample rate
    CHANNELS = 1             # Mono audio
    CHUNK_SIZE = 1024        # Buffer size (adjust for performance)
    
    # VAD settings
    SPEECH_TIMEOUT = 1.0     # Silence duration to end speech segment
    MIN_SPEECH_DURATION = 0.5 # Minimum speech length to process
    OVERLAP_DURATION = 0.3   # Overlap between segments
```

### VAD Engine Selection

The service uses WebRTC VAD by default. To switch to Silero VAD:

```bash
# Use Silero VAD instead of WebRTC
ASR_VAD=silero uv run asr_service.py

# Or set as environment variable
export ASR_VAD=silero
uv run asr_service.py
```

**VAD Engine Comparison:**
- **WebRTC VAD**: Lightweight, fast, good for clear audio
- **Silero VAD**: ML-based, better for noisy environments, slightly slower

### GPU Settings

The service automatically detects CUDA availability. To force CPU usage:

```bash
CUDA_VISIBLE_DEVICES="" uv run asr_service.py
```

## 🔧 Troubleshooting

### Common Issues

#### No Audio Input
```bash
# Linux: Check audio devices
arecord -l

# Windows: Check Windows Sound settings
# Ensure microphone is set as default recording device
```

#### CUDA Not Available
```bash
# Check NVIDIA driver
nvidia-smi

# Check PyTorch CUDA
python -c "import torch; print(torch.cuda.is_available())"
```

#### VAD Engine Not Found
The service tries multiple VAD engines in order:
1. WebRTC VAD (preferred, lightweight and reliable)
2. Silero VAD (ML-based fallback)

Install VAD engines:
```bash
pip install webrtcvad silero-vad
```

#### Service Won't Start

**Linux:**
```bash
# Check service logs
sudo journalctl -u asr.service -f

# Check file permissions
sudo chown -R asr:asr /opt/asr
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

## 🚢 Mass Deployment

### For 20 Identical RTX 3090 Systems

1. **Prepare Master Image**:
   ```bash
   # Setup one system completely
   # Test thoroughly
   # Create deployment package
   ```

2. **Deployment Script** (Linux):
   ```bash
   #!/bin/bash
   # deploy_asr.sh
   
   # Copy files
   sudo cp -r asr-pipeline /opt/asr
   sudo chown -R asr:asr /opt/asr
   
   # Install dependencies
   sudo -u asr /opt/asr/venv/bin/pip install -r /opt/asr/requirements.txt
   
   # Download model
   sudo -u asr /opt/asr/venv/bin/python /opt/asr/download_model.py
   
   # Install service
   sudo cp /opt/asr/asr.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable asr.service
   sudo systemctl start asr.service
   ```

3. **Verification**:
   ```bash
   # Check all systems
   for host in host1 host2 host3; do
     ssh $host "systemctl is-active asr.service"
   done
   ```

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

## 🔒 Security Considerations

- Service runs with minimal privileges
- No network connections required
- Audio data processed locally only
- Consider disk encryption for sensitive environments
- Regular log rotation recommended

## 🆘 Support

### Logs Location

- **Linux**: `/opt/asr/logs/`
- **Windows**: `<installation-directory>\logs\`

### Performance Metrics

Monitor these files for service health:
- `asr.out`: Service status and info messages
- `asr.err`: Error messages and warnings
- `asr_results.jsonl`: Transcription output

### Getting Help

1. Check service logs first
2. Verify hardware requirements
3. Test with `python asr_service.py` manually
4. Check microphone permissions and hardware

---

**Note**: This pipeline is optimized for aviation communication transcription but works for any English speech recognition task. For other languages, modify the `language="en"` parameter in the Whisper transcription call.
