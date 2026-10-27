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
    python3-pip python3-venv python3-picamera2 \
    i2c-tools git libatlas-base-dev \
    libopenjp2-7 libtiff5 libavcodec-dev libavformat-dev libswscale-dev

# Create venv and install Python deps
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Verify I2C
echo "I2C devices:"
sudo i2cdetect -y 1

# Create data dirs
mkdir -p cache data

# Set hostname
sudo hostnamectl set-hostname riftbound-sorter

echo ""
echo "=== Setup complete ==="
echo "Run: source venv/bin/activate && python main.py --build-db"
echo "Web UI will be at: http://riftbound-sorter.local:5000"
