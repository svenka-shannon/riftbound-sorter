#!/bin/bash
# Riftbound Card Sorter — Raspberry Pi setup script
# Run once after flashing Raspberry Pi OS Lite (64-bit, Bookworm or trixie),
# from anywhere:  bash scripts/setup.sh
#
# Camera / GPIO Python libraries come from apt (python3-picamera2,
# python3-libcamera, python3-rpi-lgpio, numpy, Pillow, scipy, PyWavelets) and
# the venv is created with --system-site-packages so it can import them; pip
# installs only the exact, hash-pinned set in requirements.lock (--no-deps:
# it never replaces an apt package).
#
# Re-running this script is safe (every step is idempotent).

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

# pinctrl (scripts/safe_outputs.py, the unit's ExecStopPost) lives in
# raspi-utils-core on Bookworm and trixie (normally preinstalled).
if ! command -v pinctrl >/dev/null 2>&1; then
    sudo apt-get install -y raspi-utils-core || sudo apt-get install -y raspi-utils
fi
command -v pinctrl >/dev/null 2>&1 || command -v raspi-gpio >/dev/null 2>&1 \
    || { echo "neither pinctrl nor raspi-gpio is installed — safe_outputs.py cannot work" >&2; exit 1; }

# Freed GPIO outputs must NOT stay driven when the process dies (audit M9):
# the pinctrl-bcm2835 driver keeps them by default (persist_gpio_outputs=1).
# Idempotent; handles /boot/firmware/cmdline.txt and /boot/cmdline.txt.
# Takes effect after the next reboot.
sudo python3 "$SCRIPT_DIR/cmdline_param.py" pinctrl_bcm2835.persist_gpio_outputs=0

# Relay inputs at boot (audit 4 m9): GPIO 17 (pump) / 27 (vent) reset to inputs
# with the SoC's ~50 kOhm pull-DOWN against the board's 10 kOhm pull-up, so IN
# sits at ~2.75 V until the sorter drives it. The firmware's config.txt `gpio`
# directive switches their internal pull to UP (IN ~3.3 V = relay released) a
# few seconds after power-on, before Linux. Idempotent (own [all] section,
# added once); handles /boot/firmware/config.txt and /boot/config.txt.
# Takes effect after the next reboot.
sudo python3 "$SCRIPT_DIR/config_txt_line.py" "gpio=17,27=ip,pu" \
    --comment "riftbound-sorter: pump / vent relay IN pulled up at boot (relay OFF)"

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
# Exact versions + sha256 hashes, no dependency resolution (see requirements.lock)
venv/bin/python -m pip install --no-deps --require-hashes -r requirements.lock
venv/bin/python -m pip check || echo "WARNING: pip check reported problems (often Debian packaging metadata) — see above"

# Check the venv sees the apt-provided modules, and that Blinka really works on
# this Pi: `import board, busio, adafruit_pca9685` must succeed (Blinka 10.x
# without gpiod would fail right here).
venv/bin/python - <<'PY'
import importlib, sys
missing = []
for mod in ("picamera2", "libcamera", "RPi.GPIO", "numpy", "PIL", "imagehash", "flask",
            "board", "busio", "adafruit_pca9685", "adafruit_motor.servo"):
    try:
        importlib.import_module(mod)
    except Exception as exc:
        missing.append(f"{mod} ({exc!r})")
if missing:
    sys.exit("venv cannot import: " + ", ".join(missing))
import board, busio, adafruit_pca9685  # noqa: E401  (the exact check from the audit)
print("venv imports OK (board, busio, adafruit_pca9685 included)")
PY

# The machine config must validate before the service is enabled
if [ -f config/machine.json ]; then
    venv/bin/python -c "from hardware import machine_config; machine_config.load(); print('config/machine.json OK')"
fi

# Verify I2C (PCA9685 should show up at 0x40)
echo "I2C devices:"
sudo i2cdetect -y 1 || echo "i2cdetect failed — is I2C enabled and the PCA9685 wired?"

# Create data dirs — data/, cache/ and config/ owned by the service user. A tool or main.py run with
# sudo leaves root-owned files there (data/sorter.lock, machine_state.json),
# which the service then refuses to start on (exit 78, audit 4 m2); re-running
# setup gives them back. Never run the tools or main.py with sudo.
mkdir -p cache data
sudo chown -R "$RUN_USER": cache data config

# Make all scripts executable (including dev runner scripts)
chmod +x scripts/*.sh

# Set hostname
sudo hostnamectl set-hostname riftbound-sorter

# Install and enable the systemd service, pointing at THIS checkout and user.
# The unit has the systemd watchdog (WatchdogSec + NotifyAccess=main; main.py
# pings it) and ExecStopPost=scripts/safe_outputs.py (outputs safe after ANY exit).
sed -e "s#/opt/riftbound-sorter#$PROJECT_DIR#g" -e "s#^User=pi#User=$RUN_USER#" \
    "$SCRIPT_DIR/riftbound-sorter.service" | sudo tee /etc/systemd/system/riftbound-sorter.service >/dev/null
sudo systemd-analyze verify /etc/systemd/system/riftbound-sorter.service || true
sudo systemctl daemon-reload
sudo systemctl enable riftbound-sorter

# Make sure every output is safe right now (also exercises the script)
sudo python3 "$SCRIPT_DIR/safe_outputs.py" || echo "safe_outputs.py reported problems (see above)"

# Web UI token (generated on first use, stored in config/web.json; shown only
# by --web-token, never in the journal)
TOKEN="$(venv/bin/python main.py --web-token | tail -n 1)"

echo ""
echo "=== Setup complete ==="
echo "Next steps (docs/ASSEMBLY.md §15.1, §16):"
echo "  1. sudo reboot     # FIRST: applies pinctrl_bcm2835.persist_gpio_outputs=0 (cmdline.txt)"
echo "     and gpio=17,27=ip,pu (config.txt). After the reboot: cat /proc/cmdline must contain"
echo "     pinctrl_bcm2835.persist_gpio_outputs=0, and 'pinctrl get 17,27' must show pu."
echo "     The service starts by itself and waits in needs_confirm."
echo "  2. sudo systemctl stop riftbound-sorter    # free the hardware for the steps below"
echo "  3. venv/bin/python main.py --build-db                          # card list + hash DB (needs internet)"
echo "  4. Calibrate, in this order (§16):"
echo "     venv/bin/python main.py --calibrate                         # load cell: 5.000 g US nickel (or --mass G)"
echo "     venv/bin/python scripts/calibrate_servos.py --no-mock      # menu 1: arm (§16.2)"
echo "     venv/bin/python scripts/test_hardware.py --no-mock         # test 11: elevator trip height (§16.3)"
echo "     venv/bin/python scripts/calibrate_servos.py --no-mock      # menus 2, 3: tilt and columns (§16.4)"
echo "     venv/bin/python scripts/calibrate_camera.py --no-mock      # camera crop (§16.5)"
echo "  5. sudo systemctl start riftbound-sorter"
echo "     First start: confirm the machine is clear in the web UI ('Machine clear')"
echo "     or with: venv/bin/python main.py --confirm-clear"
echo ""
echo "Web UI: http://riftbound-sorter.local:5000  (or http://$(hostname -I | awk '{print $1}'):5000)"
echo "Web UI token (for Pause / Stop / bins / rules): $TOKEN"
echo "Logs:   journalctl -u riftbound-sorter -f"
