#!/usr/bin/env python3
"""
Drive every sorter output to its SAFE level and put the PCA9685 to sleep.

Run by the systemd unit as ExecStopPost (as root, "+" prefix), i.e. after the
sorter process has exited for ANY reason — clean stop, crash, SIGKILL, or the
systemd watchdog's SIGABRT. Needed because Raspberry Pi kernels keep a GPIO
output driven at its last level when the process holding it dies
(pinctrl-bcm2835 persist_gpio_outputs, default on): a pump relay or belt
input left ON would stay ON (audit M9). setup.sh also turns that persistence
off on the kernel command line; this script covers the time before the
reboot and any other kernel.

Deliberately standalone: standard library only, imports nothing from the
project (works with the system python3 even if the venv or the machine
config is broken), never raises — every step is attempted.

GPIO: `pinctrl` (raspi-utils-core: Raspberry Pi OS Bookworm and trixie),
falling back to `raspi-gpio` (Bookworm only). Both write the pin registers
directly, so the level persists after this script exits. Syntax for both:
`<tool> set <gpio> op dh|dl` (output, drive high / low).

PCA9685 (I2C bus 1, 0x40): ALL_LED_OFF_H full-off bit (every channel off,
servos limp), then MODE1 = SLEEP (oscillator stopped), via the Linux i2c-dev
ioctl interface.

Machines (config/machine.json "machine", read with the standard library):
  v2 (default, also when there is no config file): SAFE_LEVELS below.
  b  (option B, cad_b/): pump relay GPIO 17 LOW (the KY-019 is active-HIGH),
     TMC2209 EN GPIO 25 HIGH (motor off), STEP 23 / DIR 24 LOW. First
     `pigs wvhlt`: pigpiod owns the STEP waveform and keeps sending it after
     the sorter died, so it is halted before the pins are set.
  unreadable config: the relay pin is only switched back to an INPUT, no level
     driven — config.txt set its boot pull for this machine (v2 "pu", B "pd"),
     which is OFF for both relays; driving a level could turn one pump ON.
Pin numbers / levels must match config/machine.json if it moves pins (the
tests check the defaults against hardware/*.py).

Usage: safe_outputs.py [--dry-run] [--machine v2|b]
"""

import argparse
import os
import shutil
import subprocess
import sys

# BCM pin → safe level. Keep in sync with hardware/*.py (tests/ check this).
SAFE_LEVELS = {
    17: 1,   # vacuum pump relay, active LOW  → HIGH = pump OFF   (hardware/vacuum.py)
    27: 1,   # vent valve relay, active LOW   → HIGH = valve shut (hardware/vacuum.py)
    23: 0, 24: 0, 25: 0, 26: 0,      # L9110S belt inputs → all LOW (hardware/conveyor.py)
    16: 0, 19: 0, 20: 0, 21: 0,      # ULN2003 stepper inputs → coils off (hardware/elevator.py)
}
# Order matters: the pump first (a held card / running pump), then the belt, then the rest.
ORDER = (17, 27, 23, 24, 25, 26, 16, 19, 20, 21)

# Option B (hardware/vacuum.py B defaults, hardware/yaw.py)
SAFE_LEVELS_B = {
    17: 0,   # pump relay, KY-019 active HIGH → LOW = pump OFF
    25: 1,   # TMC2209 EN (ENN), active LOW → HIGH = motor off
    23: 0,   # STEP
    24: 0,   # DIR
}
ORDER_B = (17, 25, 23, 24)
UNKNOWN_INPUTS = (17,)       # unreadable config: relay pin back to an input only

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "config", "machine.json")


def detect_machine(path=CONFIG_FILE) -> str:
    """"v2" / "b" from config/machine.json; "v2" without a file; "unknown" if unreadable."""
    import json
    try:
        with open(path) as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return "v2"
    except Exception:
        return "unknown"
    m = data.get("machine", "v2") if isinstance(data, dict) else None
    return m if m in ("v2", "b") else "unknown"


def levels_for(machine: str):
    """(pin → level, order) for a machine; ({}, ()) when unknown."""
    if machine == "b":
        return SAFE_LEVELS_B, ORDER_B
    if machine == "v2":
        return SAFE_LEVELS, ORDER
    return {}, ()

I2C_BUS = 1
PCA9685_ADDR = 0x40
I2C_SLAVE = 0x0703          # linux/i2c-dev.h
PCA_MODE1 = 0x00
PCA_ALL_LED_OFF_H = 0xFD
PCA_FULL_OFF = 0x10         # bit 4 of ALL_LED_OFF_H
PCA_SLEEP = 0x10            # bit 4 of MODE1


def gpio_tool():
    for name in ("pinctrl", "raspi-gpio"):
        path = shutil.which(name)
        if path:
            return path
    return None


def gpio_commands(tool: str = "pinctrl", machine: str = "v2") -> list[list[str]]:
    if machine == "unknown":
        return [[tool, "set", str(pin), "ip"] for pin in UNKNOWN_INPUTS]
    levels, order = levels_for(machine)
    return [[tool, "set", str(pin), "op", "dh" if levels[pin] else "dl"] for pin in order]


def halt_pigpio_waves(dry_run: bool = False) -> list[str]:
    """Option B: stop any STEP waveform pigpiod is still sending (best effort)."""
    pigs = shutil.which("pigs")
    if dry_run:
        print("pigs wvhlt")
        return []
    if pigs is None:
        return []
    try:
        subprocess.run([pigs, "wvhlt"], check=False, capture_output=True, timeout=5)
    except Exception as exc:
        return [f"pigs wvhlt: {exc}"]
    return []


def set_pins(dry_run: bool = False, machine: str = "v2") -> list[str]:
    errors = []
    tool = gpio_tool() or ("pinctrl" if dry_run else None)
    if tool is None:
        return ["neither pinctrl nor raspi-gpio found (apt install raspi-utils)"]
    if machine == "unknown":
        errors.append("config/machine.json unreadable: machine unknown — relay pin only set to "
                      "input (boot pull keeps it off); no other pin touched")
    for cmd in gpio_commands(tool, machine):
        if dry_run:
            print(" ".join(cmd))
            continue
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=5)
        except Exception as exc:
            errors.append(f"{' '.join(cmd)}: {exc}")
    return errors


def pca_writes() -> list[bytes]:
    return [bytes([PCA_ALL_LED_OFF_H, PCA_FULL_OFF]), bytes([PCA_MODE1, PCA_SLEEP])]


def pca_sleep(dry_run: bool = False, bus: int = I2C_BUS, addr: int = PCA9685_ADDR) -> list[str]:
    if dry_run:
        for w in pca_writes():
            print(f"i2c-{bus} 0x{addr:02x} <- {w.hex(' ')}")
        return []
    try:
        import fcntl
        fd = os.open(f"/dev/i2c-{bus}", os.O_RDWR)
    except Exception as exc:
        return [f"/dev/i2c-{bus}: {exc}"]
    errors = []
    try:
        fcntl.ioctl(fd, I2C_SLAVE, addr)
        for w in pca_writes():
            try:
                os.write(fd, w)
            except OSError as exc:
                errors.append(f"PCA9685 write {w.hex(' ')}: {exc}")
    except Exception as exc:
        errors.append(f"PCA9685 at 0x{addr:02x}: {exc}")
    finally:
        os.close(fd)
    return errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="print what would be done")
    ap.add_argument("--machine", choices=("v2", "b"), help="default: config/machine.json")
    args = ap.parse_args(argv)
    machine = args.machine or detect_machine()
    errors = []
    if machine != "v2":
        errors += halt_pigpio_waves(args.dry_run)
    errors += set_pins(args.dry_run, machine) + pca_sleep(args.dry_run)
    for e in errors:
        print(f"[safe_outputs] {e}", file=sys.stderr)
    if not args.dry_run:
        print("[safe_outputs] outputs driven safe" + (" (with errors)" if errors else ""))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
