#!/bin/bash
# Riftbound Card Sorter — Raspberry Pi setup script
# Run once after flashing Raspberry Pi OS Lite (64-bit, Bookworm or trixie),
# from anywhere:  bash scripts/setup.sh
#
# Camera / GPIO Python libraries come from apt (python3-picamera2,
# python3-libcamera, python3-rpi-lgpio) and the venv is created with
# --system-site-packages so it can import them; pip only installs what apt
# does not provide (requirements.txt).

set -euo pipefail
trap 'echo "setup.sh: FAILED at line $LINENO: $BASH_COMMAND" >&2' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"
RUN_USER="${SUDO_USER:-$(id -un)}"

echo "=== Riftbound Card Sorter Setup ($PROJECT_DIR, user $RUN_USER) ==="

# Enable I2C. (The camera needs no raspi-config step on Bookworm/trixie:
# libcamera auto-detects the Camera Module 3 via camera_auto_detect=1.)
sudo raspi-config nonint do_i2c 0

# Update system
sudo apt-get update
sudo apt-get upgrade -y

# System packages. libtiff5 / libatlas-base-dev are gone from current Raspberry
# Pi OS (trixie); Pillow, numpy and scipy come prebuilt from apt.
sudo apt-get install -y \
    python3-pip python3-venv \
    python3-picamera2 python3-libcamera \
    python3-numpy python3-scipy python3-pywt python3-pil \
    i2c-tools git \
    libopenjp2-7 libtiff6 \
    avahi-daemon

# RPi.GPIO API: rpi-lgpio is the drop-in for current Raspberry Pi OS (works on
# every Pi model incl. Pi 5, replaces python3-rpi.gpio). Fall back to the
# classic RPi.GPIO package if the archive does not have it.
if ! sudo apt-get install -y python3-rpi-lgpio; then
    echo "python3-rpi-lgpio not available — installing python3-rpi.gpio instead"
    sudo apt-get install -y python3-rpi.gpio
fi

# Venv WITH the system site-packages (picamera2 / libcamera / GPIO / numpy).
if [ ! -x venv/bin/python ]; then
    python3 -m venv --system-site-packages venv
elif ! grep -q "include-system-site-packages = true" venv/pyvenv.cfg; then
    echo "existing venv lacks --system-site-packages — recreating it"
    rm -rf venv
    python3 -m venv --system-site-packages venv
fi
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -r requirements.txt

# Check the venv sees the apt-provided modules
venv/bin/python - <<'PY'
import importlib, sys
missing = []
for mod in ("picamera2", "libcamera", "RPi.GPIO", "numpy", "PIL", "imagehash", "flask", "board"):
    try:
        importlib.import_module(mod)
    except Exception as exc:
        missing.append(f"{mod} ({exc})")
if missing:
    sys.exit("venv cannot import: " + ", ".join(missing))
print("venv imports OK")
PY

# Verify I2C (PCA9685 should show up at 0x40)
echo "I2C devices:"
sudo i2cdetect -y 1 || echo "i2cdetect failed — is I2C enabled and the PCA9685 wired?"

# Create data dirs
mkdir -p cache data

# Make all scripts executable (including dev runner scripts)
chmod +x scripts/*.sh

# Set hostname
sudo hostnamectl set-hostname riftbound-sorter

# Install and enable the systemd service, pointing at THIS checkout and user
sed -e "s#/opt/riftbound-sorter#$PROJECT_DIR#g" -e "s#^User=pi#User=$RUN_USER#" \
    "$SCRIPT_DIR/riftbound-sorter.service" | sudo tee /etc/systemd/system/riftbound-sorter.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable riftbound-sorter

# Web UI token (generated on first use, stored in config/web.json)
TOKEN="$(venv/bin/python main.py --web-token | tail -n 1)"

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. venv/bin/python main.py --build-db                          # card list + hash DB (needs internet)"
echo "  2. venv/bin/python scripts/calibrate_camera.py --no-mock      # first-time camera crop calibration"
echo "  3. venv/bin/python scripts/calibrate_servos.py --no-mock      # arm, tilt, shuttle angles"
echo "  4. venv/bin/python main.py --calibrate                         # load cell: 5.000 g US nickel (or --mass G)"
echo "  5. sudo systemctl start riftbound-sorter"
echo "     First start: confirm the machine is clear in the web UI ('Machine clear')"
echo "     or with: venv/bin/python main.py --confirm-clear"
echo ""
echo "Web UI: http://riftbound-sorter.local:5000  (or http://$(hostname -I | awk '{print $1}'):5000)"
echo "Web UI token (for Pause / Stop / bins / rules): $TOKEN"
echo "Logs:   journalctl -u riftbound-sorter -f"
