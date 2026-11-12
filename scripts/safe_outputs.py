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

Usage: safe_outputs.py [--dry-run]
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


def gpio_commands(tool: str = "pinctrl") -> list[list[str]]:
    return [[tool, "set", str(pin), "op", "dh" if SAFE_LEVELS[pin] else "dl"] for pin in ORDER]


def set_pins(dry_run: bool = False) -> list[str]:
    errors = []
    tool = gpio_tool() or ("pinctrl" if dry_run else None)
    if tool is None:
        return ["neither pinctrl nor raspi-gpio found (apt install raspi-utils)"]
    for cmd in gpio_commands(tool):
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
    args = ap.parse_args(argv)
    errors = set_pins(args.dry_run) + pca_sleep(args.dry_run)
    for e in errors:
        print(f"[safe_outputs] {e}", file=sys.stderr)
    if not args.dry_run:
        print("[safe_outputs] outputs driven safe" + (" (with errors)" if errors else ""))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
