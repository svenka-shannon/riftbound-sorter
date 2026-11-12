#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy"]
# ///
"""
Hardware Test Suite for Riftbound Card Sorter
==============================================

Exercises each subsystem through the SAME hardware/ modules the sorter uses
(pins, channels, angles and calibration files are their single source of truth).
Logs pass/fail results to /tmp/hardware_test_results.txt.

Usage:
    uv run scripts/test_hardware.py              # mock mode (default), anywhere
    venv/bin/python scripts/test_hardware.py --no-mock
        # real hardware: run with the Pi's project venv (scripts/setup.sh), which
        # has RPi.GPIO / picamera2 / adafruit libraries; a uv script env does not

Run each test with NO card in the machine unless the prompt asks for one.
"""

import argparse
import datetime
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_FILE = Path("/tmp/hardware_test_results.txt")
TEST_FULL = Path("/tmp/test_capture_full.jpg")
TEST_CARD = Path("/tmp/test_capture_card.jpg")

VACUUM_ON_DURATION = 2.0     # seconds
CONVEYOR_RUN_DURATION = 3.0  # seconds
WEIGHT_READINGS = 10
DETECT_WATCH_S = 10.0

# Populated by init_hardware() — the env var must be set before import.
servos = vacuum = loadcell = camera = conveyor = elevator = shuttle = card_detect = None
_MOCK = True


def init_hardware(mock: bool) -> None:
    global servos, vacuum, loadcell, camera, conveyor, elevator, shuttle, card_detect, _MOCK
    _MOCK = mock
    os.environ["MOCK_HARDWARE"] = "1" if mock else "0"
    sys.path.insert(0, str(ROOT))
    from hardware import (servos as _s, vacuum as _v, loadcell as _l, camera as _c,
                          conveyor as _cv, elevator as _e, shuttle as _sh, card_detect as _cd)
    servos, vacuum, loadcell, camera, conveyor, elevator, shuttle, card_detect = \
        _s, _v, _l, _c, _cv, _e, _sh, _cd
    print(f"[test] {'MOCK mode — no real hardware moves' if mock else 'REAL hardware'}")

    # Same order as main.init_hardware(): pump off first, PCA9685 before the shuttle.
    errors = []
    for name, fn in (("vacuum", vacuum.init), ("conveyor", conveyor.init),
                     ("servos", servos.init), ("arm park", servos.arm_park),
                     ("shuttle", shuttle.init), ("loadcell", loadcell.init),
                     ("camera", camera.init), ("elevator", elevator.init)):
        try:
            fn()
        except Exception as exc:
            errors.append(f"{name}: {exc!r}")
    if errors:
        print("\n[test] WARNING — some hardware failed to initialize:")
        for e in errors:
            print(f"  • {e}")
        print("[test] Tests that use it will fail.\n")


# ---------------------------------------------------------------------------
# Result logging / interaction
# ---------------------------------------------------------------------------

_results: list[dict] = []


def log_result(test_name: str, passed: bool) -> None:
    _results.append({"test": test_name, "passed": passed,
                     "time": datetime.datetime.now().isoformat(timespec="seconds")})


def flush_results() -> None:
    if not _results:
        return
    with RESULTS_FILE.open("a") as f:
        f.write(f"\n--- Session: {datetime.datetime.now().isoformat(timespec='seconds')} "
                f"({'mock' if _MOCK else 'hardware'}) ---\n")
        for r in _results:
            f.write(f"  [{'PASS' if r['passed'] else 'FAIL'}] {r['test']}  @ {r['time']}\n")
    print(f"\nResults appended to {RESULTS_FILE}")


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
    print(f"\n{'=' * 60}\n  {title}\n{'=' * 60}")


def _run(test_name: str, body) -> None:
    """Run a test body; any exception is a FAIL, and the machine is made safe."""
    try:
        body()
        passed = ask_pass_fail(test_name)
    except Exception as exc:
        print(f"  ERROR: {exc!r}")
        passed = False
    finally:
        for fn in (vacuum.pump_off, conveyor.stop):
            try:
                fn()
            except Exception:
                pass
    log_result(test_name, passed)


# ---------------------------------------------------------------------------
# Individual tests
# ---------------------------------------------------------------------------

def test_pick_arm() -> None:
    section("Test 1 — Pick arm (ch0): park → pick → drop → park")
    print(f"  ARM_PARK {servos.ARM_PARK}°, ARM_PICK {servos.ARM_PICK}°, ARM_DROP {servos.ARM_DROP}°")
    print("  Cup should touch the top card in the hopper at PICK and hover 3 mm over the")
    print("  belt at X -95 at DROP. No suction in this test.")
    wait_for_enter()

    def body():
        for label, fn in (("park", servos.arm_park), ("pick", servos.arm_to_pick),
                          ("park", servos.arm_park), ("drop", servos.arm_to_drop),
                          ("park", servos.arm_park)):
            print(f"  → {label}")
            fn()
            time.sleep(0.5)
    _run("Pick arm park/pick/drop", body)


def test_vacuum_pump() -> None:
    section(f"Test 2 — Vacuum pump: ON for {VACUUM_ON_DURATION:.0f}s then OFF")
    wait_for_enter()

    def body():
        vacuum.pump_on()
        print("  pump ON")
        time.sleep(VACUUM_ON_DURATION)
        vacuum.pump_off()
        print("  pump OFF")
    _run("Vacuum pump 2s cycle", body)


def test_pick_and_place() -> None:
    section("Test 3 — Pick and place one card onto the belt")
    print("  Put ONE card on the hopper stack at pick height. The arm picks it, carries it")
    print("  to the belt (X -95), releases it and parks. The belt does not move.")
    wait_for_enter()

    def body():
        servos.arm_to_pick()
        vacuum.pump_on()
        time.sleep(0.3)
        servos.arm_to_drop()
        time.sleep(0.1)
        vacuum.pump_off()
        time.sleep(0.3)
        servos.arm_park()
    _run("Pick and place onto belt", body)


def test_shuttle() -> None:
    section("Test 4 — Shuttle (ch1 tilt, ch2 carriage): every column, both floors, reject")
    print("  Cradle EMPTY. Visits columns 0-3 (tips lower then upper) and reject, then home.")
    wait_for_enter()

    def body():
        for col in (0, 1, 2, 3, "reject"):
            print(f"  → column {col}")
            shuttle.to_column(col)
            shuttle.tip_lower()
            time.sleep(0.3)
            shuttle.hold()
            if col != "reject":
                shuttle.tip_upper()
                time.sleep(0.3)
                shuttle.hold()
        shuttle.home()
        print(f"  state: {shuttle.state()}")
    _run("Shuttle columns + tips", body)


def test_load_cell() -> None:
    section("Test 5 — Cradle load cell: tare empty in HOLD, then readings")
    wait_for_enter("  Cradle EMPTY? Press Enter to tare...")

    def body():
        shuttle.hold()
        time.sleep(0.3)
        loadcell.tare()
        wait_for_enter("  Place ONE card on the cradle (or leave empty), then Enter...")
        for i in range(1, WEIGHT_READINGS + 1):
            w = loadcell.read_grams()
            print(f"    Reading {i:2d}: {w:6.3f} g  ({loadcell.classify(w)})")
            time.sleep(0.2)
        wait_for_enter("  Remove the card, then Enter...")
        shuttle.level()
    _run("Load cell tare + readings", body)


def test_camera() -> None:
    section("Test 6 — Camera: full frame + card crop (both flipped 180°)")
    print(f"  Saves {TEST_FULL} and {TEST_CARD}. A card centred under the lens should be")
    print("  upright in the crop. Belt travel should run along the full frame's width.")
    wait_for_enter()

    def body():
        TEST_FULL.write_bytes(camera.capture_full_jpeg())
        TEST_CARD.write_bytes(camera.capture_card_jpeg())
        print(f"  saved {TEST_FULL} ({TEST_FULL.stat().st_size} B), {TEST_CARD} ({TEST_CARD.stat().st_size} B)")
        print(f"  crop {camera.CARD_CROP} in {camera.CAPTURE_RESOLUTION}")
    _run("Camera capture + crop", body)


def test_card_detect_watch() -> None:
    section(f"Test 7 — Card detection: live offset for {DETECT_WATCH_S:.0f}s (belt off)")
    print("  Station EMPTY for the reference, then slide a card along the belt by hand.")
    print("  Offset should read ~0 mm with the card centred under the lens, + when past it.")
    wait_for_enter("  Station empty? Press Enter to take the reference...")

    def body():
        source = card_detect.default_source()
        ref = card_detect.capture_reference(source)
        if _MOCK:
            card_detect.MOCK_SCENE.card_x_mm = card_detect.CAM_X_MM - 30
        wait_for_enter("  Reference taken. Press Enter to start watching...")
        t_end = source.now() + DETECT_WATCH_S
        last = 0.0
        while source.now() < t_end:
            det = card_detect.measure(source.grab(), ref)
            if source.now() - last >= 0.25:
                last = source.now()
                if det.centre_mm is None:
                    print("    no card" if not det.found else "    card seen, no usable edge")
                else:
                    print(f"    offset {det.centre_mm:+6.1f} mm  lead {det.lead_mm}  trail {det.trail_mm}")
            if _MOCK:
                card_detect.MOCK_SCENE.card_x_mm += 0.5
    _run("Card detection live offset", body)


def test_conveyor() -> None:
    section(f"Test 8 — Conveyor: runs {CONVEYOR_RUN_DURATION:.0f}s, then brakes")
    wait_for_enter()

    def body():
        conveyor.run()
        time.sleep(CONVEYOR_RUN_DURATION)
        conveyor.brake()
    _run("Conveyor run + brake", body)


def test_centring() -> None:
    section("Test 9 — Belt centring: card from the drop zone to the lens")
    print("  Takes the empty-station reference, then you place a card on the belt at")
    print("  the arm drop zone (X -95). The belt runs until the card is centred.")
    wait_for_enter("  Station and belt EMPTY? Press Enter...")

    def body():
        ref = card_detect.capture_reference()
        wait_for_enter("  Place a card at the drop zone, then Enter...")
        res = card_detect.centre_card(ref, conveyor.run, conveyor.brake, conveyor.stop)
        print(f"  result: {res}")
        if res.ok:
            TEST_CARD.write_bytes(camera.capture_card_jpeg(
                shift_px=card_detect.crop_shift_px(res.offset_mm or 0.0)))
            print(f"  card crop saved to {TEST_CARD}")
    _run("Belt centring", body)


def test_elevator() -> None:
    section("Test 10 — Hopper elevator: home, then raise to pick height")
    print("  Lowers the floor to the home switch (up to ~60 s), then raises the stack")
    print("  until the top card trips the feeler. Arm must be parked.")
    wait_for_enter()

    def body():
        servos.arm_park()
        print(f"  home: {elevator.home()}")
        print(f"  raise_to_pick: {elevator.raise_to_pick()}  "
              f"(position {elevator.position_mm():.1f} mm, ~{elevator.cards_remaining_estimate()} cards)")
    _run("Elevator home + raise", body)


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

TESTS = [
    ("Pick arm (ch0) park / pick / drop", test_pick_arm),
    ("Vacuum pump 2 s", test_vacuum_pump),
    ("Pick and place one card onto the belt", test_pick_and_place),
    ("Shuttle columns + tips (ch1/ch2)", test_shuttle),
    ("Cradle load cell", test_load_cell),
    ("Camera full frame + card crop", test_camera),
    ("Card detection live offset (belt off)", test_card_detect_watch),
    ("Conveyor run + brake", test_conveyor),
    ("Belt centring (drop zone → lens)", test_centring),
    ("Hopper elevator home + raise", test_elevator),
]


def run_all() -> None:
    print("\nRunning all tests in sequence...\n")
    for _, fn in TESTS:
        fn()
    print("\nAll tests complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Hardware test suite for Riftbound card sorter")
    parser.add_argument("--no-mock", dest="mock", action="store_false", default=True,
                        help="Use real hardware instead of mock mode")
    args = parser.parse_args()

    init_hardware(mock=args.mock)
    menu = "\n".join(f"[{i}] {label}" for i, (label, _) in enumerate(TESTS, 1))
    menu = f"Hardware Test Suite\n===================\n{menu}\n[A] Run all\n[Q] Quit\n"
    try:
        while True:
            print(f"\n{menu}")
            try:
                choice = input("Select test: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nInterrupted.")
                break
            if choice == "q":
                break
            if choice == "a":
                run_all()
            elif choice.isdigit() and 1 <= int(choice) <= len(TESTS):
                TESTS[int(choice) - 1][1]()
            else:
                print(f"  Unknown option: {choice!r}")
    finally:
        flush_results()
        for fn in (vacuum.pump_off, conveyor.stop, servos.arm_park, conveyor.deinit,
                   shuttle.deinit, elevator.deinit, servos.deinit, vacuum.deinit, camera.deinit):
            try:
                fn()
            except Exception:
                pass


if __name__ == "__main__":
    main()
