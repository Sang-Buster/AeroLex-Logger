#!/bin/bash
# ASR Pipeline Linux Installation Script
# Automates the complete setup process for systemd service

set -e  # Exit on any error

echo "============================================"
echo "ASR Pipeline Linux Installation"
echo "============================================"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "ERROR: This script should not be run as root"
   echo "Run as regular user with sudo access"
   exit 1
fi

# Check if sudo is available
if ! command -v sudo &> /dev/null; then
    echo "ERROR: sudo is required but not installed"
    exit 1
fi

# Get current directory
ASR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "ASR Directory: $ASR_DIR"

# Check if required files exist
if [[ ! -f "$ASR_DIR/asr_service.py" ]]; then
    echo "ERROR: asr_service.py not found in $ASR_DIR"
    exit 1
fi

if [[ ! -f "$ASR_DIR/requirements.txt" ]]; then
    echo "ERROR: requirements.txt not found in $ASR_DIR"
    exit 1
fi

# Check if uv is installed
echo "Checking uv installation..."
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
    
    # Check if installation succeeded
    if ! command -v uv &> /dev/null; then
        echo "ERROR: Failed to install uv"
        echo "Please install manually: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
fi

echo "✓ uv is available"

# Check Python version through uv
echo "Setting up Python 3.10 environment..."
if ! uv python list | grep -q "3.10"; then
    echo "Installing Python 3.10..."
    uv python install 3.10
fi

echo "✓ Python 3.10 is available"

# Create ASR user
echo "Creating ASR service user..."
if id "asr" &>/dev/null; then
    echo "User 'asr' already exists"
else
    sudo useradd -r -s /bin/false -d /opt/asr asr
    echo "✓ Created user 'asr'"
fi

# Create directories
echo "Setting up directories..."
sudo mkdir -p /opt/asr/logs
sudo mkdir -p /opt/asr/models

# Copy files
echo "Copying ASR pipeline files..."
sudo cp -r "$ASR_DIR"/* /opt/asr/
sudo chown -R asr:asr /opt/asr
echo "✓ Files copied to /opt/asr"

# Create virtual environment with uv
echo "Creating Python virtual environment with uv..."
sudo -u asr uv venv /opt/asr/venv -p 3.10
echo "✓ Virtual environment created"

# Install dependencies
echo "Installing Python dependencies with uv..."
echo "This may take several minutes..."
sudo -u asr uv pip install -r /opt/asr/requirements.txt --python /opt/asr/venv/bin/python
echo "✓ Dependencies installed"

# Download Whisper model
echo "Downloading Whisper model..."
echo "This may take several minutes depending on internet connection..."
sudo -u asr /opt/asr/venv/bin/python /opt/asr/download_model.py
if [[ $? -eq 0 ]]; then
    echo "✓ Whisper model downloaded and verified"
else
    echo "WARNING: Model download may have failed. Check manually."
fi

# Run installation test
echo "Running installation test..."
sudo -u asr /opt/asr/venv/bin/python /opt/asr/test_installation.py
if [[ $? -eq 0 ]]; then
    echo "✓ Installation test passed"
else
    echo "WARNING: Installation test had issues. Check manually."
fi

# Install systemd service
echo "Installing systemd service..."
sudo cp /opt/asr/asr.service /etc/systemd/system/
sudo systemctl daemon-reload
echo "✓ Systemd service installed"

# Enable service
echo "Enabling ASR service..."
sudo systemctl enable asr.service
echo "✓ Service enabled for auto-start"

# Test service
echo "Testing service startup..."
sudo systemctl start asr.service
sleep 5

if sudo systemctl is-active --quiet asr.service; then
    echo "✓ Service started successfully"
else
    echo "WARNING: Service may not have started properly"
    echo "Check logs with: sudo journalctl -u asr.service -f"
fi

# Set up log rotation
echo "Setting up log rotation..."
sudo tee /etc/logrotate.d/asr > /dev/null << 'EOF'
/opt/asr/logs/*.log /opt/asr/logs/*.out /opt/asr/logs/*.err {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 asr asr
    postrotate
        systemctl reload asr.service > /dev/null 2>&1 || true
    endscript
}

/opt/asr/logs/*.jsonl {
    daily
    rotate 90
    compress
    delaycompress
    missingok
    notifempty
    create 644 asr asr
    copytruncate
}
EOF
echo "✓ Log rotation configured"

# Add user to audio group (if needed)
if groups asr | grep -q audio; then
    echo "✓ User 'asr' already in audio group"
else
    sudo usermod -a -G audio asr
    echo "✓ Added user 'asr' to audio group"
    echo "NOTE: Service restart may be required for audio group changes"
fi

echo ""
echo "============================================"
echo "Installation completed successfully!"
echo "============================================"
echo ""
echo "Service Status:"
sudo systemctl status asr.service --no-pager -l
echo ""
echo "Management Commands:"
echo "  Start:   sudo systemctl start asr.service"
echo "  Stop:    sudo systemctl stop asr.service"
echo "  Restart: sudo systemctl restart asr.service"
echo "  Status:  sudo systemctl status asr.service"
echo "  Logs:    sudo journalctl -u asr.service -f"
echo ""
echo "Log Files:"
echo "  Service: /opt/asr/logs/asr.out"
echo "  Errors:  /opt/asr/logs/asr.err"
echo "  Results: /opt/asr/logs/asr_results.jsonl"
echo ""
echo "To view live transcriptions:"
echo "  tail -f /opt/asr/logs/asr_results.jsonl | jq '.transcript'"
echo ""

# Check if service is running properly
sleep 2
if sudo systemctl is-active --quiet asr.service; then
    echo "✅ ASR Pipeline is running successfully!"
else
    echo "⚠️  Service may need attention. Check logs for details."
fi

echo "Installation complete."
