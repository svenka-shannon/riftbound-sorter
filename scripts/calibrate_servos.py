#!/usr/bin/env -S uv run --script
"""
Servo angle calibration tool for the Riftbound card sorter.

Interactively moves each servo to a desired angle, lets you label
the position (e.g. "ARM_UP"), and saves all labeled positions to
config/servo_calibration.json.  At the end it prints ready-to-paste
Python constants for hardware/servos.py.

Usage:
    python scripts/calibrate_servos.py
    # or with real hardware:
    python scripts/calibrate_servos.py --no-mock
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
CONFIG_DIR = REPO_ROOT / "config"
CALIBRATION_FILE = CONFIG_DIR / "servo_calibration.json"

# ---------------------------------------------------------------------------
# Servo channel map
# ---------------------------------------------------------------------------
SERVO_NAMES = {0: "pickup_arm", 1: "gate", 2: "bin_select"}

# Canonical label sets per servo (informational only — user can type anything)
LABEL_HINTS = {
    0: ["ARM_UP", "ARM_DOWN"],
    1: ["GATE_LEFT", "GATE_CENTER", "GATE_RIGHT"],
    2: [f"BIN_{i}" for i in range(8)] + ["BIN_9_REJECT"],
}

# ---------------------------------------------------------------------------
# Hardware / mock init
# ---------------------------------------------------------------------------
_pca = None
_servos: dict = {}
_MOCK = True


def init_hardware(mock: bool) -> None:
    global _pca, _servos, _MOCK
    _MOCK = mock
    if mock:
        print("[calibrate] Running in MOCK mode — no hardware moves will occur.")
        return
    try:
        import board
        import busio
        from adafruit_motor import servo as adafruit_servo
        from adafruit_pca9685 import PCA9685

        i2c = busio.I2C(board.SCL, board.SDA)
        _pca = PCA9685(i2c, address=0x40)
        _pca.frequency = 50
        for ch in range(3):
            _servos[ch] = adafruit_servo.Servo(
                _pca.channels[ch], min_pulse=500, max_pulse=2500
            )
        print("[calibrate] PCA9685 initialized on I2C 0x40")
    except Exception as exc:
        print(f"[calibrate] Hardware init failed: {exc}")
        print("[calibrate] Falling back to MOCK mode.")
        _MOCK = True


def move_servo(channel: int, angle: float) -> None:
    """Move servo on *channel* to *angle* degrees (0-180)."""
    if _MOCK:
        print(f"  [MOCK] servo channel={channel} → {angle}°")
        return
    _servos[channel].angle = angle
    time.sleep(0.3)


# ---------------------------------------------------------------------------
# Calibration data helpers
# ---------------------------------------------------------------------------

def load_calibration() -> dict:
    if CALIBRATION_FILE.exists():
        with open(CALIBRATION_FILE) as f:
            return json.load(f)
    return {}


def save_calibration(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CALIBRATION_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved → {CALIBRATION_FILE}")


# ---------------------------------------------------------------------------
# Pretty-print final constants
# ---------------------------------------------------------------------------

def print_python_constants(data: dict) -> None:
    arm = data.get("pickup_arm", {})
    gate = data.get("gate", {})
    bin_sel = data.get("bin_select", {})

    lines = [
        "",
        "# ── Copy these into hardware/servos.py ──────────────────────────",
    ]

    if arm:
        lines.append(f"PICKUP_ARM_UP   = {arm.get('ARM_UP',   '???')}  # resting position")
        lines.append(f"PICKUP_ARM_DOWN = {arm.get('ARM_DOWN', '???')}  # card pickup position")

    if gate:
        lines.append(f"GATE_LEFT   = {gate.get('GATE_LEFT',   '???')}  # route to bin group A (bins 0-3)")
        lines.append(f"GATE_CENTER = {gate.get('GATE_CENTER', '???')}  # card passes straight")
        lines.append(f"GATE_RIGHT  = {gate.get('GATE_RIGHT',  '???')}  # route to bin group B (bins 4-7)")

    if bin_sel:
        # Build the dict in key order
        entries = []
        for k, v in sorted(bin_sel.items(), key=lambda kv: int(kv[0])):
            entries.append(f"    {k}: {v}")
        lines.append("BIN_SELECT_ANGLES = {")
        lines.append(",\n".join(entries) + ",")
        lines.append("}")

    lines.append("# ─────────────────────────────────────────────────────────────────")
    print("\n".join(lines))


# ---------------------------------------------------------------------------
# Interactive calibration loop
# ---------------------------------------------------------------------------

def calibrate_servo(channel: int, data: dict) -> None:
    name = SERVO_NAMES[channel]
    hints = LABEL_HINTS[channel]
    print(f"\n=== Calibrating servo {channel}: {name} ===")
    print(f"  Suggested labels: {hints}")
    print("  Commands: <angle>  |  label <NAME>  |  done")

    servo_data: dict = data.setdefault(name, {})
    current_angle: float | None = None

    while True:
        try:
            raw = input(f"  [{name}] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue

        if raw.lower() == "done":
            break

        if raw.lower().startswith("label "):
            label = raw[6:].strip()
            if current_angle is None:
                print("  Move to an angle first before labeling.")
            else:
                servo_data[label] = current_angle
                print(f"  Labeled {label} = {current_angle}°")
                save_calibration(data)
            continue

        # Try to parse as an angle
        try:
            angle = float(raw)
        except ValueError:
            print("  Enter a number (angle in degrees), 'label <NAME>', or 'done'.")
            continue

        if not 0 <= angle <= 180:
            print("  Angle must be 0–180.")
            continue

        move_servo(channel, angle)
        current_angle = angle
        print(f"  Moved to {angle}°")


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Servo angle calibration tool")
    parser.add_argument(
        "--no-mock",
        action="store_true",
        help="Use real PCA9685 hardware instead of mock mode",
    )
    args = parser.parse_args()

    init_hardware(mock=not args.no_mock)

    data = load_calibration()
    if data:
        print(f"Loaded existing calibration from {CALIBRATION_FILE}")

    while True:
        print("\n=== Servo Calibration Menu ===")
        print("  0 - Pickup arm   (ARM_UP, ARM_DOWN)")
        print("  1 - Deflect gate (GATE_LEFT, GATE_CENTER, GATE_RIGHT)")
        print("  2 - Bin select   (BIN_0 … BIN_7, BIN_9_REJECT)")
        print("  p - Print Python constants")
        print("  q - Quit")

        try:
            choice = input("\nChoose [0/1/2/p/q]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if choice == "q":
            break
        elif choice == "p":
            print_python_constants(data)
        elif choice in ("0", "1", "2"):
            calibrate_servo(int(choice), data)
        else:
            print("  Invalid choice.")

    # Final summary
    if data:
        print_python_constants(data)
        print(f"\nCalibration file: {CALIBRATION_FILE}")

    if _pca is not None:
        try:
            _pca.deinit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
