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

# Which machine: config/machine.json "machine" ("v2" default, or "b" = option B
# turntable picker, cad_b/). Read with the system python3's standard library.
MACHINE="$(python3 - "$PROJECT_DIR/config/machine.json" <<'PY'
import json, sys
try:
    m = json.load(open(sys.argv[1])).get("machine", "v2")
except FileNotFoundError:
    m = "v2"
except Exception as exc:
    sys.exit(f"config/machine.json unreadable: {exc}")
print(m if m in ("v2", "b") else sys.exit(f"unknown machine {m!r}"))
PY
)"
echo "Machine: $MACHINE"

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
if [ "$MACHINE" = "b" ]; then
    # Option B (cad_b/README.md "Pin map (option B)"):
    #   GPIO 17 KY-019 relay, ACTIVE-HIGH: pull-DOWN at boot = pump OFF
    #   GPIO 25 TMC2209 EN (active low): pull-UP at boot = motor OFF
    #   GPIO 16 touch contact, GPIO 22 home switch: inputs with pull-ups
    sudo python3 "$SCRIPT_DIR/config_txt_line.py" "gpio=17=ip,pd" \
        --comment "riftbound-sorter (B): KY-019 pump relay IN pulled down at boot (relay OFF)"
    sudo python3 "$SCRIPT_DIR/config_txt_line.py" "gpio=25=ip,pu" \
        --comment "riftbound-sorter (B): TMC2209 EN pulled up at boot (yaw motor OFF)"
    sudo python3 "$SCRIPT_DIR/config_txt_line.py" "gpio=16,22=ip,pu" \
        --comment "riftbound-sorter (B): touch contact + home switch inputs, pull-up"
    # Write-only UART to the TMC2209 on GPIO 14: PL011 on the header, Bluetooth
    # off, no serial console (it would send boot text to the driver).
    sudo python3 "$SCRIPT_DIR/config_txt_line.py" "enable_uart=1" \
        --comment "riftbound-sorter (B): UART TX to the TMC2209 PDN_UART"
    sudo python3 "$SCRIPT_DIR/config_txt_line.py" "dtoverlay=disable-bt" \
        --comment "riftbound-sorter (B): PL011 UART on GPIO 14/15 (Bluetooth off)"
    # WS2812 ring on GPIO 18 (PWM0): analogue audio must stay off
    sudo python3 "$SCRIPT_DIR/config_txt_line.py" "dtparam=audio=off" \
        --comment "riftbound-sorter (B): PWM free for the WS2812 ring"
    sudo raspi-config nonint do_serial_cons 1     # no login console on the UART
    sudo raspi-config nonint do_serial_hw 0       # UART hardware on
    sudo systemctl disable --now hciuart 2>/dev/null || true
else
    sudo python3 "$SCRIPT_DIR/config_txt_line.py" "gpio=17,27=ip,pu" \
        --comment "riftbound-sorter: pump / vent relay IN pulled up at boot (relay OFF)"
fi

# RPi.GPIO API: rpi-lgpio is the drop-in for current Raspberry Pi OS (works on
# every Pi model incl. Pi 5, replaces python3-rpi.gpio). Fall back to the
# classic RPi.GPIO package if the archive does not have it.
if ! sudo apt-get install -y python3-rpi-lgpio; then
    echo "python3-rpi-lgpio not available — installing python3-rpi.gpio instead"
    sudo apt-get install -y python3-rpi.gpio
fi

# Option B: pigpio daemon (DMA step waveforms + the UART for the TMC2209).
# Raspberry Pi OS ships it as apt packages on Bookworm; if the archive lacks
# them (trixie), build it from source. The daemon runs with -l (localhost only)
# and -t 1 (PCM clock: the PWM peripheral stays free for the WS2812 ring).
if [ "$MACHINE" = "b" ]; then
    if ! sudo apt-get install -y pigpio python3-pigpio; then
        echo "pigpio not in the apt archive — building it from source (github.com/joan2937/pigpio)"
        sudo apt-get install -y build-essential unzip wget
        tmp="$(mktemp -d)"
        wget -qO "$tmp/pigpio.zip" https://github.com/joan2937/pigpio/archive/master.zip
        unzip -q "$tmp/pigpio.zip" -d "$tmp"
        make -C "$tmp/pigpio-master"
        sudo make -C "$tmp/pigpio-master" install
        rm -rf "$tmp"
    fi
    PIGPIOD="$(command -v pigpiod || echo /usr/bin/pigpiod)"
    if [ ! -f /lib/systemd/system/pigpiod.service ] && [ ! -f /etc/systemd/system/pigpiod.service ]; then
        printf '[Unit]\nDescription=pigpio daemon\n\n[Service]\nType=forking\nExecStart=%s -l -t 1\n\n[Install]\nWantedBy=multi-user.target\n' \
            "$PIGPIOD" | sudo tee /etc/systemd/system/pigpiod.service >/dev/null
    else
        sudo mkdir -p /etc/systemd/system/pigpiod.service.d
        printf '[Service]\nExecStart=\nExecStart=%s -l -t 1\n' "$PIGPIOD" \
            | sudo tee /etc/systemd/system/pigpiod.service.d/riftbound.conf >/dev/null
    fi
    sudo systemctl daemon-reload
    sudo systemctl enable --now pigpiod
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
MACHINE="$MACHINE" venv/bin/python - <<'PY'
import importlib, os, sys
missing = []
mods = ["picamera2", "libcamera", "RPi.GPIO", "numpy", "PIL", "imagehash", "flask",
        "board", "busio", "adafruit_pca9685", "adafruit_motor.servo"]
if os.environ.get("MACHINE") == "b":
    mods.append("pigpio")
for mod in mods:
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
if [ "$MACHINE" = "b" ]; then
echo "Option B: after the reboot check 'pinctrl get 16,17,22,25' (17 pd, 16/22/25 pu), that"
echo "  /dev/serial0 -> ttyAMA0, and that EN reads > 2.5 V with the sorter stopped. Then bench-test"
echo "  each part with: venv/bin/python scripts/test_hardware.py --no-mock   (B menu: home switch"
echo "  watch FIRST, then touch, lift, UART + yaw, homing, pump, load cell, camera). Calibrate"
echo "  stations / lift heights through the /api/b/... endpoints (web/app.py docstring)."
fi
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
