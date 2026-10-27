#!/usr/bin/env -S uv run --script
"""
Hardware Test Suite for Riftbound Card Sorter
==============================================

Tests each hardware component individually without running the full sorter.
Logs pass/fail results to /tmp/hardware_test_results.txt.

Usage:
    python scripts/test_hardware.py           # mock mode (default)
    python scripts/test_hardware.py --no-mock # real hardware
"""

import argparse
import datetime
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RESULTS_FILE = Path("/tmp/hardware_test_results.txt")
TEST_CAPTURE = Path("/tmp/test_capture.jpg")

# Servo channel assignments
CH_PICKUP_ARM = 0
CH_DEFLECT_GATE = 1
CH_BIN_SELECT = 2

# Servo angle presets (degrees, 0-180)
ARM_UP = 30
ARM_DOWN = 150

GATE_LEFT = 30
GATE_CENTER = 90
GATE_RIGHT = 150

# 8 bin positions spread evenly across 0-180 degrees
BIN_ANGLES = [round(i * (180 / 7)) for i in range(8)]  # 0, 26, 51, 77, 103, 128, 154, 180

VACUUM_ON_DURATION = 2.0   # seconds
CONVEYOR_RUN_DURATION = 3.0  # seconds
WEIGHT_READINGS = 10

# ---------------------------------------------------------------------------
# Hardware / mock state
# ---------------------------------------------------------------------------

_MOCK = True
_pca = None
_servos: dict = {}
_vacuum_pin = None
_conveyor_pin = None
_load_cell = None
_camera = None


def init_hardware(mock: bool) -> None:
    global _pca, _servos, _vacuum_pin, _conveyor_pin, _load_cell, _camera, _MOCK
    _MOCK = mock
    if mock:
        print("[test] Running in MOCK mode — no real hardware moves will occur.")
        return

    errors = []

    # PCA9685 + servos
    try:
        import board
        import busio
        from adafruit_motor import servo as adafruit_servo
        from adafruit_pca9685 import PCA9685

        i2c = busio.I2C(board.SCL, board.SDA)
        _pca = PCA9685(i2c, address=0x40)
        _pca.frequency = 50
        for ch in (CH_PICKUP_ARM, CH_DEFLECT_GATE, CH_BIN_SELECT):
            _servos[ch] = adafruit_servo.Servo(
                _pca.channels[ch], min_pulse=500, max_pulse=2500
            )
        print("[test] PCA9685 initialized on I2C 0x40")
    except Exception as exc:
        errors.append(f"PCA9685/servo init: {exc}")

    # Vacuum pump GPIO (GPIO 17 by default — adjust if needed)
    try:
        import RPi.GPIO as GPIO

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(17, GPIO.OUT, initial=GPIO.LOW)
        _vacuum_pin = 17
        print("[test] Vacuum GPIO 17 ready")
    except Exception as exc:
        errors.append(f"Vacuum GPIO init: {exc}")

    # Conveyor motor GPIO (GPIO 27 by default — adjust if needed)
    try:
        import RPi.GPIO as GPIO  # noqa: F811 (already imported above; harmless)

        GPIO.setup(27, GPIO.OUT, initial=GPIO.LOW)
        _conveyor_pin = 27
        print("[test] Conveyor GPIO 27 ready")
    except Exception as exc:
        errors.append(f"Conveyor GPIO init: {exc}")

    # Load cell (HX711)
    try:
        import RPi.HX711 as HX711  # type: ignore

        _load_cell = HX711.HX711(dout_pin=5, pd_sck_pin=6)
        _load_cell.set_reading_format("MSB", "MSB")
        _load_cell.reset()
        _load_cell.tare()
        print("[test] HX711 load cell initialized (tared)")
    except Exception as exc:
        try:
            from hx711 import HX711 as HX711Alt  # type: ignore

            _load_cell = HX711Alt(dout=5, pd_sck=6)
            _load_cell.reset()
            _load_cell.tare()
            print("[test] HX711 load cell initialized via hx711 library (tared)")
        except Exception as exc2:
            errors.append(f"Load cell init: {exc} / {exc2}")

    # Camera (picamera2 preferred, fallback to picamera)
    try:
        from picamera2 import Picamera2  # type: ignore

        _camera = Picamera2()
        print("[test] Picamera2 camera ready")
    except Exception as exc:
        try:
            import picamera  # type: ignore

            _camera = picamera.PiCamera()
            print("[test] picamera (legacy) camera ready")
        except Exception as exc2:
            errors.append(f"Camera init: {exc} / {exc2}")

    if errors:
        print("\n[test] WARNING — some hardware failed to initialize:")
        for e in errors:
            print(f"  • {e}")
        print("[test] Affected tests will run in MOCK mode.\n")


# ---------------------------------------------------------------------------
# Low-level hardware helpers
# ---------------------------------------------------------------------------

def move_servo(channel: int, angle: float, label: str = "") -> None:
    tag = f" ({label})" if label else ""
    if _MOCK or channel not in _servos:
        print(f"  [MOCK] servo ch={channel} → {angle:.0f}°{tag}")
        time.sleep(0.3)
        return
    _servos[channel].angle = angle
    time.sleep(0.4)
    print(f"  servo ch={channel} → {angle:.0f}°{tag}")


def vacuum_set(on: bool) -> None:
    state = "ON" if on else "OFF"
    if _MOCK or _vacuum_pin is None:
        print(f"  [MOCK] vacuum pump → {state}")
        return
    import RPi.GPIO as GPIO

    GPIO.output(_vacuum_pin, GPIO.HIGH if on else GPIO.LOW)
    print(f"  vacuum pump → {state}")


def conveyor_set(on: bool) -> None:
    state = "ON" if on else "OFF"
    if _MOCK or _conveyor_pin is None:
        print(f"  [MOCK] conveyor → {state}")
        return
    import RPi.GPIO as GPIO

    GPIO.output(_conveyor_pin, GPIO.HIGH if on else GPIO.LOW)
    print(f"  conveyor → {state}")


def read_weight_once() -> float:
    if _MOCK or _load_cell is None:
        import random

        return round(random.uniform(0.0, 5.0), 3)
    try:
        val = _load_cell.get_weight(5)
        return round(float(val), 3)
    except Exception:
        return float("nan")


def capture_jpeg(path: Path) -> bool:
    if _MOCK or _camera is None:
        path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 16 + b"\xff\xd9")  # minimal JPEG stub
        print(f"  [MOCK] wrote stub JPEG to {path}")
        return True
    try:
        # picamera2 path
        if hasattr(_camera, "start"):
            _camera.start()
            time.sleep(0.5)
            _camera.capture_file(str(path))
            _camera.stop()
        else:
            # legacy picamera
            _camera.capture(str(path))
        print(f"  captured → {path}  ({path.stat().st_size} bytes)")
        return True
    except Exception as exc:
        print(f"  capture failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Result logging
# ---------------------------------------------------------------------------

_results: list[dict] = []


def log_result(test_name: str, passed: bool) -> None:
    _results.append(
        {
            "test": test_name,
            "passed": passed,
            "time": datetime.datetime.now().isoformat(timespec="seconds"),
        }
    )


def flush_results() -> None:
    if not _results:
        return
    with RESULTS_FILE.open("a") as f:
        f.write(f"\n--- Session: {datetime.datetime.now().isoformat(timespec='seconds')} ---\n")
        for r in _results:
            status = "PASS" if r["passed"] else "FAIL"
            f.write(f"  [{status}] {r['test']}  @ {r['time']}\n")
    print(f"\nResults appended to {RESULTS_FILE}")


# ---------------------------------------------------------------------------
# Interaction helpers
# ---------------------------------------------------------------------------

def wait_for_enter(prompt: str = "  Press Enter to proceed...") -> None:
    try:
        input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()


def ask_pass_fail(test_name: str) -> bool:
    while True:
        try:
            ans = input("  Did this test PASS? [y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"
        if ans in ("y", "yes"):
            print(f"  Logged: PASS — {test_name}")
            return True
        if ans in ("n", "no"):
            print(f"  Logged: FAIL — {test_name}")
            return False
        print("  Please enter y or n.")


def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# Individual tests
# ---------------------------------------------------------------------------

def test_servo_pickup_arm() -> None:
    section("Test 1 — Servo 0 (pickup arm): UP then DOWN")
    print("  Will move pickup arm servo to ARM_UP position, pause, then ARM_DOWN.")
    wait_for_enter()

    print(f"  Moving to ARM_UP ({ARM_UP}°)...")
    move_servo(CH_PICKUP_ARM, ARM_UP, "ARM_UP")
    time.sleep(0.8)

    print(f"  Moving to ARM_DOWN ({ARM_DOWN}°)...")
    move_servo(CH_PICKUP_ARM, ARM_DOWN, "ARM_DOWN")
    time.sleep(0.8)

    print(f"  Returning to ARM_UP ({ARM_UP}°)...")
    move_servo(CH_PICKUP_ARM, ARM_UP, "ARM_UP")

    passed = ask_pass_fail("Servo 0 (pickup arm)")
    log_result("Servo 0 (pickup arm) UP/DOWN", passed)


def test_servo_deflect_gate() -> None:
    section("Test 2 — Servo 1 (deflect gate): LEFT, CENTER, RIGHT")
    print("  Will move deflect gate servo through LEFT → CENTER → RIGHT.")
    wait_for_enter()

    for angle, label in (
        (GATE_LEFT, "GATE_LEFT"),
        (GATE_CENTER, "GATE_CENTER"),
        (GATE_RIGHT, "GATE_RIGHT"),
    ):
        print(f"  Moving to {label} ({angle}°)...")
        move_servo(CH_DEFLECT_GATE, angle, label)
        time.sleep(0.6)

    print(f"  Returning to GATE_CENTER ({GATE_CENTER}°)...")
    move_servo(CH_DEFLECT_GATE, GATE_CENTER, "GATE_CENTER")

    passed = ask_pass_fail("Servo 1 (deflect gate)")
    log_result("Servo 1 (deflect gate) LEFT/CENTER/RIGHT", passed)


def test_servo_bin_select() -> None:
    section("Test 3 — Servo 2 (bin select): cycles through all 8 bin positions")
    print(f"  Will cycle through bin positions: {BIN_ANGLES}")
    wait_for_enter()

    for i, angle in enumerate(BIN_ANGLES):
        print(f"  Bin {i} → {angle}°")
        move_servo(CH_BIN_SELECT, angle, f"BIN_{i}")
        time.sleep(0.5)

    passed = ask_pass_fail("Servo 2 (bin select)")
    log_result("Servo 2 (bin select) all 8 positions", passed)


def test_vacuum_pump() -> None:
    section("Test 4 — Vacuum pump: ON for 2s then OFF")
    print(f"  Will turn vacuum pump ON for {VACUUM_ON_DURATION}s, then OFF.")
    wait_for_enter()

    print("  Turning vacuum pump ON...")
    vacuum_set(True)
    time.sleep(VACUUM_ON_DURATION)

    print("  Turning vacuum pump OFF...")
    vacuum_set(False)

    passed = ask_pass_fail("Vacuum pump ON/OFF")
    log_result("Vacuum pump 2s cycle", passed)


def test_load_cell() -> None:
    section("Test 5 — Load cell: 10 weight readings")
    print(f"  Will print {WEIGHT_READINGS} consecutive weight readings.")
    wait_for_enter()

    print("  Reading weights:")
    for i in range(1, WEIGHT_READINGS + 1):
        w = read_weight_once()
        print(f"    Reading {i:2d}: {w:.3f} g")
        time.sleep(0.2)

    passed = ask_pass_fail("Load cell readings")
    log_result("Load cell 10 readings", passed)


def test_camera() -> None:
    section("Test 6 — Camera: capture JPEG")
    print(f"  Will capture a single JPEG and save to {TEST_CAPTURE}.")
    wait_for_enter()

    ok = capture_jpeg(TEST_CAPTURE)
    if ok and TEST_CAPTURE.exists():
        size = TEST_CAPTURE.stat().st_size
        print(f"  File saved: {TEST_CAPTURE}  ({size} bytes)")
    else:
        print("  Capture failed or file not found.")

    passed = ask_pass_fail("Camera JPEG capture")
    log_result("Camera JPEG capture", passed)


def test_conveyor() -> None:
    section("Test 7 — Conveyor: runs for 3 seconds")
    print(f"  Will turn conveyor ON for {CONVEYOR_RUN_DURATION}s, then OFF.")
    wait_for_enter()

    print("  Starting conveyor...")
    conveyor_set(True)
    time.sleep(CONVEYOR_RUN_DURATION)

    print("  Stopping conveyor...")
    conveyor_set(False)

    passed = ask_pass_fail("Conveyor 3s run")
    log_result("Conveyor 3s run", passed)


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

MENU = """\
Hardware Test Suite for Riftbound Card Sorter
============================================
[1] Test servo 0 (pickup arm)  - moves UP then DOWN
[2] Test servo 1 (deflect gate) - moves LEFT, CENTER, RIGHT
[3] Test servo 2 (bin select)  - cycles through all 8 bin positions
[4] Test vacuum pump           - turns on for 2s, then off
[5] Test load cell             - prints 10 weight readings
[6] Test camera                - captures a JPEG and saves to /tmp/test_capture.jpg
[7] Test conveyor              - runs for 3 seconds
[8] Run all tests in sequence
[Q] Quit
"""

TESTS = [
    test_servo_pickup_arm,
    test_servo_deflect_gate,
    test_servo_bin_select,
    test_vacuum_pump,
    test_load_cell,
    test_camera,
    test_conveyor,
]


def run_all() -> None:
    print("\nRunning all tests in sequence...\n")
    for fn in TESTS:
        fn()
    print("\nAll tests complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Hardware test suite for Riftbound card sorter")
    parser.add_argument(
        "--no-mock",
        dest="mock",
        action="store_false",
        default=True,
        help="Use real hardware instead of mock mode",
    )
    args = parser.parse_args()

    init_hardware(mock=args.mock)

    try:
        while True:
            print(f"\n{MENU}")
            try:
                choice = input("Select test: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nInterrupted.")
                break

            if choice == "q":
                print("Exiting test suite.")
                break
            elif choice == "1":
                test_servo_pickup_arm()
            elif choice == "2":
                test_servo_deflect_gate()
            elif choice == "3":
                test_servo_bin_select()
            elif choice == "4":
                test_vacuum_pump()
            elif choice == "5":
                test_load_cell()
            elif choice == "6":
                test_camera()
            elif choice == "7":
                test_conveyor()
            elif choice == "8":
                run_all()
            else:
                print(f"  Unknown option: {choice!r}")
    finally:
        flush_results()

        # Clean up GPIO if we initialized it
        if not args.mock:
            try:
                import RPi.GPIO as GPIO

                GPIO.cleanup()
                print("[test] GPIO cleanup done.")
            except Exception:
                pass


if __name__ == "__main__":
    main()
