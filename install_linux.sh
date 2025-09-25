#!/bin/bash
# ASR Pipeline Linux Installation Script
# Installs and runs the service from the current directory (no copying to /opt)

set -e  # Exit on any error

echo "============================================"
echo "ASR Pipeline Linux Installation"
echo "============================================"

# Get current directory and user
ASR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER="$(whoami)"

echo "ASR Directory: $ASR_DIR"
echo "Current User: $CURRENT_USER"

# Check if required files exist
if [[ ! -f "$ASR_DIR/src/asr_service.py" ]]; then
    echo "ERROR: src/asr_service.py not found in $ASR_DIR"
    exit 1
fi

if [[ ! -f "$ASR_DIR/pyproject.toml" ]]; then
    echo "ERROR: pyproject.toml not found in $ASR_DIR"
    exit 1
fi

# Check if uv is installed
echo "Checking uv installation..."
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
    
    # Check if installation succeeded
    if ! command -v uv &> /dev/null; then
        echo "ERROR: Failed to install uv"
        echo "Please install manually: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
fi

echo "✓ uv is available"

# Create necessary directories
echo "Creating directories..."
mkdir -p "$ASR_DIR/logs"
mkdir -p "$ASR_DIR/models"
mkdir -p "$ASR_DIR/audios"
echo "✓ Directories created"

# Sync dependencies with uv
echo "Installing dependencies..."
echo "This may take several minutes..."
cd "$ASR_DIR"
uv sync
echo "✓ Dependencies installed and virtual environment created"

# Download Whisper model
echo "Downloading Whisper model..."
echo "This may take several minutes depending on internet connection..."
uv run src/download_model.py
if [[ $? -eq 0 ]]; then
    echo "✓ Whisper model downloaded and verified"
else
    echo "WARNING: Model download may have failed. Check manually."
fi

# Run installation test
echo "Running installation test..."
uv run src/test_installation.py
if [[ $? -eq 0 ]]; then
    echo "✓ Installation test passed"
else
    echo "WARNING: Installation test had issues. Check manually."
fi

# Process asr.service template with current paths
echo "Processing systemd service file..."
SERVICE_FILE="$ASR_DIR/asr.service"
TEMP_SERVICE_FILE="/tmp/asr.service"

if [[ ! -f "$SERVICE_FILE" ]]; then
    echo "ERROR: asr.service file not found in $ASR_DIR"
    echo "Please ensure asr.service exists with proper configuration"
    exit 1
fi

# Replace placeholders with actual paths and user
sed -e "s|@ASR_DIR@|$ASR_DIR|g" -e "s|@CURRENT_USER@|$CURRENT_USER|g" "$SERVICE_FILE" > "$TEMP_SERVICE_FILE"
echo "✓ Processed service file with current paths"

# Install systemd service
echo "Installing systemd service..."
sudo cp "$TEMP_SERVICE_FILE" /etc/systemd/system/asr.service
rm "$TEMP_SERVICE_FILE"  # Clean up temp file
sudo systemctl daemon-reload
echo "✓ Systemd service installed"

# Enable service
echo "Enabling ASR service..."
sudo systemctl enable asr.service
echo "✓ Service enabled for auto-start"

# Add user to audio group (if needed)
if groups "$CURRENT_USER" | grep -q audio; then
    echo "✓ User '$CURRENT_USER' already in audio group"
else
    echo "Adding user '$CURRENT_USER' to audio group..."
    sudo usermod -a -G audio "$CURRENT_USER"
    echo "✓ Added user '$CURRENT_USER' to audio group"
    echo "NOTE: You may need to log out and back in for audio group changes to take effect"
fi

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
echo "  Service: $ASR_DIR/logs/asr.out"
echo "  Errors:  $ASR_DIR/logs/asr.err"
echo "  Results: $ASR_DIR/logs/asr_results.jsonl"
echo "  Audio:   $ASR_DIR/audios/"
echo ""
echo "To view live transcriptions:"
echo "  tail -f $ASR_DIR/logs/asr_results.jsonl | jq '.transcript'"
echo ""

# Check if service is running properly
sleep 2
if sudo systemctl is-active --quiet asr.service; then
    echo "✅ ASR Pipeline is running successfully from $ASR_DIR!"
else
    echo "⚠️  Service may need attention. Check logs for details."
fi

echo "Installation complete."
