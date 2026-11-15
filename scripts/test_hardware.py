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

Sorter interlock (audit 3 M2): the tool takes the sorter's instance lock
(data/sorter.lock — refuses to run while the sorter service or another tool
runs: `sudo systemctl stop riftbound-sorter` first) and, BEFORE anything
moves, records the machine as NOT clean in data/machine_state.json
("tool ran: ..."). It never records it clean again — the tool may stop
anywhere (crash, Ctrl-C, power cut) with the carriage at a column, the
cradle tipped or a card in the machine — so the next sorter start always
asks for "Machine clear" (web UI or `main.py --confirm-clear`). MOCK runs use
the mock files (machine_state.mock.json, sorter.mock.lock).

Option B (config/machine.json "machine": "b"): a separate menu tests each B
part on its own — home switch and touch contact live (motor OFF, turn / lift
by hand: do these FIRST, before any homing), lift sweep, TMC2209 UART config +
holding torque, homing + station tour, yaw jog, touch-down probe, pump + bleed,
bed load cell noise, camera. Same instance lock and "not clean" marker.

Config errors: an invalid config/machine.json, config/servo_calibration.json
or config/shuttle_calibration.json stops the tool (exit 78, EX_CONFIG — the
same status for every config error, in every tool and main.py) with the list
of bad keys, exactly like the sorter — nothing moves. An instance lock / data/
this user cannot open (left root-owned by a run with sudo — never run the tools
with sudo) also exits 78, naming the file and the chown fix.
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
_lock = None                 # instance lock handle, held for the life of the tool
EX_CONFIG = 78


def claim_machine(mock: bool) -> None:
    """Instance lock + "not clean" marker before anything moves (audit 3 M2).
    Exits 1 if the sorter (or another tool) is running."""
    global _lock
    from hardware import instance
    try:
        _lock = instance.claim_for_tool("scripts/test_hardware.py", mock)
    except instance.LockBusy as exc:
        sys.exit(f"[test] ERROR: {exc}")
    except instance.LockFileError as exc:          # root-owned lock / data/ (sudo run)
        print(f"[test] ERROR: {exc}", file=sys.stderr)
        sys.exit(EX_CONFIG)
    print(f"[test] machine recorded as NOT clean ({instance.state_file(mock)}): the next sorter "
          "start asks for 'Machine clear'")


def init_hardware(mock: bool) -> None:
    global servos, vacuum, loadcell, camera, conveyor, elevator, shuttle, card_detect, _MOCK
    _MOCK = mock
    os.environ["MOCK_HARDWARE"] = "1" if mock else "0"
    sys.path.insert(0, str(ROOT))
    try:
        from hardware import (servos as _s, vacuum as _v, loadcell as _l, camera as _c,
                              conveyor as _cv, elevator as _e, shuttle as _sh, card_detect as _cd)
    except Exception as exc:
        if type(exc).__name__ == "MachineConfigError":
            # every config error exits 78 (EX_CONFIG), like main.py; message lists the keys
            print(f"[test] ERROR: {exc}", file=sys.stderr)
            sys.exit(EX_CONFIG)
        raise
    servos, vacuum, loadcell, camera, conveyor, elevator, shuttle, card_detect = \
        _s, _v, _l, _c, _cv, _e, _sh, _cd
    print(f"[test] {'MOCK mode — no real hardware moves' if mock else 'REAL hardware'}")
    claim_machine(mock)

    # Same order as main.init_hardware(): pump off first, PCA9685 before the shuttle.
    # Like the sorter, nothing on ch0-ch2 moves until the operator says the
    # machine is clear (the pose is unknown: the first moves are direct jumps).
    errors = []
    for name, fn in (("vacuum", vacuum.init), ("conveyor", conveyor.init),
                     ("servos", servos.init), ("shuttle", shuttle.init),
                     ("loadcell", loadcell.init), ("camera", camera.init),
                     ("elevator", elevator.init)):
        try:
            fn()
        except (servos.ServoConfigError, shuttle.ShuttleConfigError) as exc:
            # same contract as the sorter: a bad calibration file never reaches a servo
            print(f"[test] ERROR: {exc}", file=sys.stderr)
            for safe in (vacuum.pump_off, conveyor.stop):
                try:
                    safe()
                except Exception:
                    pass
            sys.exit(EX_CONFIG)
        except Exception as exc:
            errors.append(f"{name}: {exc!r}")
    if not mock:
        wait_for_enter("[test] Arm, belt and cradle clear? The arm parks and the shuttle homes "
                       "(direct moves) — press Enter...")
    for name, fn in (("arm park", servos.arm_park), ("shuttle home", shuttle.home)):
        try:
            fn()
        except Exception as exc:
            errors.append(f"{name}: {exc!r}")
    if errors:
        print("\n[test] WARNING — some hardware failed to initialize:")
        for e in errors:
            print(f"  • {e}")
        print("[test] Tests that use it will fail.\n")
    if not mock:
        print(f"[test] camera read-back: {camera.SENSOR_INFO}")


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
        for mod, name in ((vacuum, "pump_off"), (vacuum, "vent_close"), (conveyor, "stop")):
            if mod is None:                   # option B has no conveyor
                continue
            try:
                getattr(mod, name)()
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


def test_vent_valve() -> None:
    section(f"Test 3 — Vent valve (GPIO {vacuum.VENT_PIN}): pump on, then release()")
    print("  Hold the cup on a card (or your finger) while the pump runs. release() switches")
    print(f"  the pump off and opens the NC vent valve for {vacuum.VENT_S:.1f} s: you should hear")
    print("  the valve click and the suction should vanish at once (not slowly leak away).")
    wait_for_enter()

    def body():
        vacuum.pump_on()
        print("  pump ON (vent closed)")
        time.sleep(VACUUM_ON_DURATION)
        vacuum.release()
        print(f"  pump OFF, vent open {vacuum.VENT_S:.1f} s, vent closed again "
              f"(vent now {'OPEN' if vacuum.vent_is_open() else 'closed'})")
    _run("Vent valve release", body)


def test_pick_and_place() -> None:
    section("Test 4 — Pick and place one card onto the belt")
    print("  Put ONE card on the hopper stack at pick height. The arm picks it, carries it")
    print("  to the belt (X -95), releases it and parks. The belt does not move.")
    wait_for_enter()

    def body():
        servos.arm_to_pick()
        vacuum.pump_on()
        time.sleep(0.3)
        servos.arm_to_drop()
        time.sleep(0.1)
        vacuum.release()                       # pump off + vent pulse
        lift = 10.0 if servos.ARM_PARK >= servos.ARM_DROP else -10.0
        servos.move_arm_smooth(servos.ARM_DROP + lift, duration_s=0.6)   # slow first lift
        servos.arm_park()
    _run("Pick and place onto belt", body)


def test_shuttle() -> None:
    section("Test 5 — Shuttle (ch1 tilt, ch2 carriage): every column, both floors, reject")
    print("  Cradle EMPTY. Visits columns 0-3 (tips lower then upper) and reject, then home.")
    wait_for_enter()

    def body():
        for col in (0, 1, 2, 3, "reject"):
            print(f"  → column {col}")
            shuttle.hold()                     # the carriage only moves in HOLD
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
    section("Test 6 — Cradle load cell: tare empty in HOLD, then readings (median of 7)")
    wait_for_enter("  Cradle EMPTY? Press Enter to tare...")

    def body():
        shuttle.hold()
        time.sleep(0.3)
        loadcell.tare()                    # diagnostic tare: never stored as the empty reference
        wait_for_enter("  Place ONE card on the cradle (or leave empty), then Enter...")
        for i in range(1, WEIGHT_READINGS + 1):
            w = loadcell.read_grams_unchecked()
            print(f"    Reading {i:2d}: {w:6.3f} g  ({loadcell.classify(w)})")
            time.sleep(0.2)
        wait_for_enter("  Remove the card, then Enter...")
        shuttle.level()
    _run("Load cell tare + readings", body)


def test_camera() -> None:
    section("Test 7 — Camera: full frame + card crop (both flipped 180°)")
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
    section(f"Test 8 — Card detection: live offset for {DETECT_WATCH_S:.0f}s (belt off)")
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
    section(f"Test 9 — Conveyor: runs {CONVEYOR_RUN_DURATION:.0f}s, then brakes")
    wait_for_enter()

    def body():
        conveyor.run()
        time.sleep(CONVEYOR_RUN_DURATION)
        conveyor.brake()
    _run("Conveyor run + brake", body)


def test_centring() -> None:
    section("Test 10 — Belt centring: card from the drop zone to the lens")
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
    section("Test 11 — Hopper elevator: home, then raise to pick height")
    print("  Lowers the floor to the home switch (up to ~60 s), then raises the stack")
    print("  until the top card trips the feeler. Arm must be parked.")
    wait_for_enter()

    def body():
        servos.arm_park()
        print(f"  home: {elevator.home()}")
        print(f"  switches: top {'NC' if elevator.TOP_SWITCH_NC else 'NO'}, bottom "
              f"{'NC' if elevator.BOTTOM_SWITCH_NC else 'NO'} (config/machine.json \"elevator\")")
        print(f"  raise_to_pick: {elevator.raise_to_pick()}  "
              f"(position {elevator.position_mm():.1f} mm, ~{elevator.cards_remaining_estimate()} cards)")
    _run("Elevator home + raise", body)


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

TESTS = [
    ("Pick arm (ch0) park / pick / drop", test_pick_arm),
    ("Vacuum pump 2 s", test_vacuum_pump),
    ("Vent valve release (pump off + vent pulse)", test_vent_valve),
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


# ---------------------------------------------------------------------------
# Option B (turntable picker)
# ---------------------------------------------------------------------------

B = {}                       # hardware modules for B, set by init_b()
B_WATCH_S = 15.0


def init_b(mock: bool) -> None:
    global vacuum, loadcell, camera
    from hardware import (b_calibration, b_geometry, camera as _c, lift, loadcell as _l, touch,
                          vacuum as _v, yaw)
    vacuum, loadcell, camera = _v, _l, _c
    B.update(cal=b_calibration, geo=b_geometry, lift=lift, touch=touch, yaw=yaw)
    print(f"[test] option B — {'MOCK mode' if mock else 'REAL hardware'}")
    claim_machine(mock)
    try:
        b_calibration.load(lift.ACTUATION_RANGE)
    except b_calibration.BCalibrationError as exc:
        print(f"[test] ERROR: {exc}", file=sys.stderr)
        sys.exit(EX_CONFIG)
    errors = []
    for name, fn in (("vacuum", vacuum.init), ("touch", touch.init), ("lift", lift.init),
                     ("yaw", yaw.init), ("loadcell", loadcell.init), ("camera", camera.init)):
        try:
            fn()
        except Exception as exc:
            errors.append(f"{name}: {exc!r}")
    yaw.set_interlock(lift.yaw_permitted)
    if mock:
        from hardware import b_mock
        b_mock.attach()
    for e in errors:
        print(f"  • {e}")
    print("[test] the yaw motor is OFF (EN high) until a test enables it; the lift is not commanded yet")


def _b_lift_full() -> None:
    wait_for_enter("  The lift goes STRAIGHT to full height (fast). Arm clear above? Enter...")
    B["lift"].to_full()


def b_test_home_switch() -> None:
    section(f"B1 — Home switch live for {B_WATCH_S:.0f} s (motor OFF: turn the arm by hand)")
    print("  Pressed for arm angles 0 .. -72 (cam rim), released from ~+8 up. Turn the arm slowly")
    print("  through home in both directions: the edge must be crisp and in the same place.")
    wait_for_enter()

    def body():
        B["yaw"].disable(distrust=True)           # arm turned by hand: saved position no longer valid
        end, last = time.monotonic() + B_WATCH_S, None
        while time.monotonic() < end:
            st = B["yaw"].home_pressed()
            if st != last:
                print(f"    {'PRESSED' if st else 'released'}")
                last = st
            time.sleep(0.02)
    _run("B home switch", body)


def b_test_touch() -> None:
    section(f"B2 — Touch contact live for {B_WATCH_S:.0f} s (lift the cup by hand)")
    print("  Resting = CLOSED; push the cup up a few mm = OPEN. It must re-close every time.")
    wait_for_enter()

    def body():
        end, last = time.monotonic() + B_WATCH_S, None
        while time.monotonic() < end:
            st = B["touch"].raw_open()
            if st != last:
                print(f"    {'OPEN (touching)' if st else 'closed (resting)'}")
                last = st
            time.sleep(0.01)
    _run("B touch contact", body)


def b_test_lift() -> None:
    geo = B["geo"]
    section("B3 — Lift sweep: full → th 0 → full (over an EMPTY spot: park the arm by hand at ~-10)")
    print(f"  servo map {B['cal'].servo_map()}; full lift th {geo.TH_FULL:g} = lip {geo.lip_z(geo.TH_FULL):.0f} mm, "
          f"th 0 = lip {geo.lip_z(0):.0f} mm")
    _b_lift_full()

    def body():
        for th in (0.0, geo.TH_FULL):
            print(f"  → th {th:g}")
            B["lift"].move_to(th)
            time.sleep(0.8)
        B["lift"].to_full()
    _run("B lift sweep", body)


def b_test_uart_hold() -> None:
    yaw = B["yaw"]
    section("B4 — TMC2209: write the UART config, then hold for 5 s")
    regs = yaw.driver_registers()
    print(f"  {len(yaw.driver_datagrams())} datagrams (all addresses), IHOLD_IRUN 0x{regs[yaw.REG_IHOLD_IRUN]:08x}, "
          f"CHOPCONF 0x{regs[yaw.REG_CHOPCONF]:08x}; RUN {yaw.RUN_CURRENT_A} A")
    print("  With the motor enabled, the arm must be stiff (hard to turn by hand); off again after.")
    wait_for_enter()

    def body():
        yaw.configure_driver()
        yaw.enable()
        time.sleep(5.0)
        yaw.disable()
    _run("B TMC2209 config + hold", body)


def b_test_home_tour() -> None:
    yaw, cal = B["yaw"], B["cal"]
    section("B5 — Home the yaw, then visit every station at full lift, then park")
    print("  Run B1 first. The arm moves; nothing in the bins / on the bed matters (full lift).")
    hint = yaw.load_hint()
    print(f"  saved position hint: {hint if hint else 'none / untrusted'}")
    if hint is None:
        print(f"  Homing only searches {yaw.NOHINT_SEARCH_DEG:g} deg without a trusted position. Turn the")
        print(f"  arm by hand (motor off) to the park pose, ~{cal.park_yaw():g} deg: just past home, switch")
        print("  PRESSED (check with B1).")
        try:
            ok = input("  Arm at the park pose now? [y/N]: ").strip().lower() in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            ok = False
        if ok:
            yaw.save_hint(cal.park_yaw() - yaw.HINT_MARGIN_DEG, cal.park_yaw() + yaw.HINT_MARGIN_DEG)
    _b_lift_full()

    def body():
        yaw.home()
        print("  homed")
        for name in B["geo"].STATIONS:
            yaw.move_to(cal.station_yaw(name), approach=True)
            print(f"  {name:7s} yaw {yaw.position_deg():7.2f}  switch "
                  f"{'PRESSED' if yaw.home_pressed() else 'released'}")
            time.sleep(0.4)
        yaw.verify_edge()
        yaw.move_to(cal.park_yaw())
        print(f"  parked at {yaw.position_deg():.2f} (switch {'PRESSED' if yaw.home_pressed() else 'released'})")
    _run("B homing + station tour", body)


def b_test_jog() -> None:
    yaw = B["yaw"]
    section("B6 — Yaw jog (needs B5 first): type +/-degrees, empty line to stop")

    def body():
        if not yaw.homed():
            raise RuntimeError("not homed — run B5 first")
        while True:
            try:
                txt = input(f"  yaw {yaw.position_deg():.3f} deg — jog by: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not txt:
                break
            yaw.move_by(max(-30.0, min(30.0, float(txt))))
    _run("B yaw jog", body)


def b_test_probe() -> None:
    yaw, cal, lift = B["yaw"], B["cal"], B["lift"]
    section("B7 — Touch-down probe on the EMPTY scan bed (needs B5)")

    def body():
        if not yaw.homed():
            raise RuntimeError("not homed — run B5 first")
        yaw.move_to(cal.station_yaw("scan"), approach=True)
        st = cal.station("scan")
        res = lift.lower_until_touch(st["approach_th"], st["limit_th"], 0.0)
        print(f"  touched {res.touched} at th {res.th_touch} (calibrated touch_th {st['touch_th']}); "
              f"bed reads {loadcell.read_grams_unchecked():.2f} g with the cup resting")
        lift.to_full()
    _run("B touch-down probe", body)


def b_test_pump() -> None:
    section(f"B8 — Pump on 2 s, then off: the bleed must let go within {vacuum.RELEASE_FALLBACK_S:.1f} s")
    print("  Hold a card against the cup; after 'pump OFF' it must drop within the bleed time.")
    wait_for_enter()

    def body():
        vacuum.pump_on()
        print("  pump ON")
        time.sleep(VACUUM_ON_DURATION)
        t = time.monotonic()
        vacuum.pump_off()
        print("  pump OFF — press Enter the moment the card drops")
        wait_for_enter("")
        print(f"  released after {time.monotonic() - t:.2f} s")
    _run("B pump + bleed", body)


def b_test_loadcell() -> None:
    section("B9 — Bed load cell: tare empty, noise, then one card")
    print("  Arm OFF the bed. The empty-bed noise must stay well under 0.3 g for the single /")
    print("  double split (5 kg cell). Not stored as the empty reference (main.py --calibrate does).")
    wait_for_enter("  Bed EMPTY? Enter to tare...")

    def body():
        import statistics
        loadcell.tare()
        vals = [loadcell.read_grams_unchecked() for _ in range(WEIGHT_READINGS)]
        print(f"    empty: mean {statistics.mean(vals):+.3f} g, stdev {statistics.pstdev(vals):.3f} g, "
              f"span {max(vals) - min(vals):.3f} g")
        wait_for_enter("  Put ONE card on the bed, then Enter...")
        vals = [loadcell.read_grams_unchecked() for _ in range(WEIGHT_READINGS)]
        print(f"    card: mean {statistics.mean(vals):.3f} g ({loadcell.classify(statistics.mean(vals))}), "
              f"stdev {statistics.pstdev(vals):.3f} g")
    _run("B bed load cell", body)


def b_test_camera() -> None:
    section("B10 — Camera over the bed (arm out of view): full frame + card crop")
    wait_for_enter("  Card on the bed, arm away from it? Enter...")

    def body():
        TEST_FULL.write_bytes(camera.capture_full_jpeg())
        TEST_CARD.write_bytes(camera.capture_card_jpeg())
        print(f"  saved {TEST_FULL}, {TEST_CARD}; FOV {camera.FOV_X_MM:.0f} × {camera.FOV_Y_MM:.0f} mm, "
              f"crop {camera.CARD_CROP}")
    _run("B camera", body)


B_TESTS = [
    ("Home switch live (motor off, turn by hand) — FIRST", b_test_home_switch),
    ("Touch contact live (lift the cup by hand)", b_test_touch),
    ("Lift sweep full → 0 → full", b_test_lift),
    ("TMC2209 UART config + holding torque", b_test_uart_hold),
    ("Yaw homing + station tour + park", b_test_home_tour),
    ("Yaw jog", b_test_jog),
    ("Touch-down probe on the empty bed", b_test_probe),
    ("Pump + bleed release time", b_test_pump),
    ("Bed load cell noise + one card", b_test_loadcell),
    ("Camera over the bed", b_test_camera),
]


def run_b_menu() -> None:
    menu = "\n".join(f"[{i}] {label}" for i, (label, _) in enumerate(B_TESTS, 1))
    menu = f"Option B Hardware Tests\n=======================\n{menu}\n[Q] Quit\n"
    try:
        while True:
            print(f"\n{menu}")
            try:
                choice = input("Select test: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                break
            if choice == "q":
                break
            if choice.isdigit() and 1 <= int(choice) <= len(B_TESTS):
                B_TESTS[int(choice) - 1][1]()
            else:
                print(f"  Unknown option: {choice!r}")
    finally:
        flush_results()
        for fn in (vacuum.pump_off, B["yaw"].deinit, B["lift"].deinit, vacuum.deinit,
                   B["touch"].deinit, loadcell.deinit, camera.deinit):
            try:
                fn()
            except Exception:
                pass


def _machine(mock: bool) -> str:
    os.environ["MOCK_HARDWARE"] = "1" if mock else "0"
    sys.path.insert(0, str(ROOT))
    try:
        from hardware import machine_config
        return machine_config.machine()
    except Exception as exc:
        if type(exc).__name__ == "MachineConfigError":
            print(f"[test] ERROR: {exc}", file=sys.stderr)
            sys.exit(EX_CONFIG)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Hardware test suite for Riftbound card sorter")
    parser.add_argument("--no-mock", dest="mock", action="store_false", default=True,
                        help="Use real hardware instead of mock mode")
    args = parser.parse_args()

    if _machine(args.mock) == "b":
        global _MOCK
        _MOCK = args.mock
        init_b(args.mock)
        run_b_menu()
        return
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
        # shuttle.deinit() no longer homes (it leaves the shuttle where it is,
        # de-energized), so home it explicitly while the PCA9685 is still up.
        for fn in (vacuum.pump_off, conveyor.stop, servos.arm_park, shuttle.home, conveyor.deinit,
                   shuttle.deinit, elevator.deinit, servos.deinit, vacuum.deinit,
                   loadcell.deinit, camera.deinit):
            try:
                fn()
            except Exception:
                pass


if __name__ == "__main__":
    main()
