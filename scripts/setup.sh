#!/bin/bash
# Riftbound Card Sorter — Pi Zero 2W setup script
# Run once after flashing Pi OS Lite (64-bit)

set -e
echo "=== Riftbound Card Sorter Setup ==="

# Enable I2C and Camera
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_camera 0

# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install system deps
sudo apt-get install -y \
    python3-pip python3-venv python3-picamera2 python3-numpy \
    i2c-tools git libatlas-base-dev \
    libopenjp2-7 libtiff5 libavcodec-dev libavformat-dev libswscale-dev \
    avahi-daemon

# Create venv and install Python deps
# Use uv if available (faster); fall back to standard pip+venv.
# On Raspberry Pi OS Lite, uv may not be pre-installed — pip is the reliable default.
if command -v uv &>/dev/null; then
    echo "uv found — using uv for faster installs"
    uv venv venv
    source venv/bin/activate
    uv pip install -r requirements.txt
else
    echo "uv not found — using pip (install uv via 'pip install uv' for faster future installs)"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

# Verify I2C
echo "I2C devices:"
sudo i2cdetect -y 1

# Create data dirs
mkdir -p cache data

# Make all scripts executable (including dev runner scripts)
chmod +x scripts/*.sh

# Set hostname
sudo hostnamectl set-hostname riftbound-sorter

# Install and enable the systemd service
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
sudo cp "$SCRIPT_DIR/riftbound-sorter.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable riftbound-sorter

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. source venv/bin/activate && python main.py --build-db"
echo "  2. python scripts/calibrate_camera.py    # first-time camera crop calibration"
echo "  3. sudo systemctl start riftbound-sorter"
echo ""
echo "Web UI: http://riftbound-sorter.local:5000  (or http://$(hostname -I | awk '{print $1}'):5000)"
echo "Logs:   journalctl -u riftbound-sorter -f"
