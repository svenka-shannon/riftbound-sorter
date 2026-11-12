"""
Full sort cycle in MOCK_HARDWARE=1 with monkeypatched sensors.

Run:
  uv run --with pytest --with pillow --with numpy --with requests --with flask \
         --with imagehash pytest -q tests/
"""

import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

os.environ["MOCK_HARDWARE"] = "1"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pytest

import main
from hardware import camera, card_detect, conveyor, elevator, loadcell, servos, shuttle, vacuum


class FakeEngine:
    reject_bin = 9

    def assign_bin(self, card):
        return card.get("bin", 2)

    def describe_bin(self, b):
        return "Reject" if b == 9 else f"Bin {b}"


@pytest.fixture
def rig(monkeypatch, tmp_path):
    """Machine in its start-of-cycle state, with recorders on the actuators."""
    rec = SimpleNamespace(belt=False, pump=False, events=[], recorded=[],
                          card_id="rb_001", conf=0.95, card={"name": "Jinx", "bin": 2},
                          sleep_hook=None)

    def fake_sleep(s):
        if rec.sleep_hook:
            rec.sleep_hook()
    monkeypatch.setattr(time, "sleep", fake_sleep)

    # isolated bin counts
    monkeypatch.setattr(main, "_bins", main.BinCounts(tmp_path / "bin_counts.json",
                                                      tmp_path / "bin_limits.json",
                                                      main.DEFAULT_BIN_LIMITS))
    # identify / lookup / inventory
    monkeypatch.setattr(main, "identify", lambda jpeg: (rec.card_id, rec.conf))
    monkeypatch.setattr(main.riftcodex, "get_card", lambda cid: rec.card)
    monkeypatch.setattr(main.inventory, "record_scan", lambda *a: rec.recorded.append(a))

    # actuators
    def belt(state, name):
        def f(*a, **k):
            rec.belt = state
            rec.events.append(name)
        return f
    monkeypatch.setattr(conveyor, "run", belt(True, "run"))
    monkeypatch.setattr(conveyor, "brake", belt(False, "brake"))
    monkeypatch.setattr(conveyor, "stop", belt(False, "stop"))

    def pump(state):
        def f():
            rec.pump = state
            rec.events.append("pump_on" if state else "pump_off")
        return f
    monkeypatch.setattr(vacuum, "pump_on", pump(True))
    monkeypatch.setattr(vacuum, "pump_off", pump(False))

    # simulated world
    monkeypatch.setattr(loadcell, "MOCK_CARD_G", 1.75)
    loadcell.mock_set_load(0.0)
    loadcell.tare()
    s = card_detect.MOCK_SCENE
    s.card_x_mm, s.auto_card, s.visible, s.running = None, True, True, False
    s.speed_mm_s = card_detect.BELT_SPEED_MM_S * 1.1
    elevator.mock_set_cards(150)

    servos.init()
    servos.arm_park()
    shuttle.init()
    elevator.init()
    assert elevator.home()
    main._prepare_cradle(first=True)

    main._running = True
    main._set_state("running")
    for k in main._stats:
        main._stats[k] = 0
    rec.events.clear()
    yield rec
    main._running = True


def _assert_safe(rec):
    assert rec.pump is False, "pump left on"
    assert rec.belt is False, "belt left running"
    assert servos.arm_angle() == servos.ARM_PARK, "arm not parked"


# ── the cycle ────────────────────────────────────────────────────────────────
def test_single_card_routed_to_its_bin(rig):
    assert main.sort_one_card(FakeEngine()) == 2
    assert main._bins.count(2) == 1
    assert rig.recorded and rig.recorded[0][2] == 2
    # cycle order: pump on → pump off → belt run (centre) → brake → run (exit) → stop
    ev = rig.events
    assert ev.index("pump_on") < ev.index("pump_off") < ev.index("run") < ev.index("brake")
    assert ev[-2:] == ["run", "stop"]
    _assert_safe(rig)
    # ready for the next card: home, level, re-tared with the empty cradle
    assert shuttle.state()[:2] == ("home", "level")
    assert abs(loadcell.read_grams()) < 0.01
    assert abs(main._status["last_offset_mm"]) <= card_detect.CENTER_TOL_MM
    # a second card goes through too
    assert main.sort_one_card(FakeEngine()) == 2
    assert main._bins.count(2) == 2


def test_double_weight_goes_to_reject(rig, monkeypatch):
    monkeypatch.setattr(loadcell, "MOCK_CARD_G", 3.5)
    assert main.sort_one_card(FakeEngine()) == main.REJECT_BIN
    assert main._bins.count(9) == 1 and main._bins.count(2) == 0
    assert main._stats["double_picks"] == 1
    assert rig.recorded == []
    _assert_safe(rig)


@pytest.mark.parametrize("mode", ["no_match", "raises", "no_card_data"])
def test_identify_failure_goes_to_reject(rig, monkeypatch, mode):
    if mode == "no_match":
        rig.card_id, rig.conf = None, 0.41
    elif mode == "raises":
        def boom(jpeg):
            raise RuntimeError("hash db corrupt")
        monkeypatch.setattr(main, "identify", boom)
    else:
        rig.card = None
    assert main.sort_one_card(FakeEngine()) == main.REJECT_BIN
    assert main._bins.count(9) == 1
    assert main._status["state"] == "running"
    _assert_safe(rig)


def test_hopper_empty_stops(rig):
    elevator.mock_set_cards(0)
    assert main.run_sorter(engine=FakeEngine(), max_cycles=5) == "hopper_empty"
    assert main._status["hopper_empty"] is True
    assert "pump_on" not in rig.events            # never tried to pick
    _assert_safe(rig)


def test_card_never_seen_stops_with_belt_stopped(rig):
    card_detect.MOCK_SCENE.auto_card = False     # pick "succeeded" but nothing on the belt
    assert main.run_sorter(engine=FakeEngine(), max_cycles=5) == "jam"
    assert main._status["jam"] is True
    assert "timeout" in main._status["message"]
    assert rig.events.count("run") == 1           # belt ran once, never restarted
    assert rig.events[-1] in ("brake", "stop")
    assert main._stats["total"] == 0
    _assert_safe(rig)


def test_card_lost_between_belt_and_cradle_stops(rig, monkeypatch):
    monkeypatch.setattr(loadcell, "MOCK_CARD_G", 0.0)
    assert main.run_sorter(engine=FakeEngine(), max_cycles=5) == "jam"
    assert "cradle" in main._status["message"]
    _assert_safe(rig)


def test_cradle_still_loaded_after_tip_stops(rig, monkeypatch):
    monkeypatch.setattr(loadcell, "read_grams", lambda samples=5: 1.75)   # card never leaves
    assert main.run_sorter(engine=FakeEngine(), max_cycles=5) == "jam"
    assert "stuck on the cradle" in main._status["message"]
    assert main._bins.count(2) == 0                # not counted
    assert shuttle.state()[1] == "hold"            # cradle not levelled with a card on it
    assert main._stats["total"] == 0
    _assert_safe(rig)


def test_bin_full_pauses_with_card_held_then_resumes(rig):
    main._bins.limits[2] = 1
    main._bins.increment(2)                        # bin 2 already holds its limit
    seen = {}

    def on_sleep():
        if main._status["state"] == "paused" and not seen:
            seen["status"] = dict(main._status)
            seen["shuttle"] = shuttle.state()[:2]
            seen["load"] = loadcell.read_grams()
            seen["count"] = main._bins.count(2)
            seen["safe"] = (rig.pump, rig.belt, servos.arm_angle())
            main.empty_bin(2)                      # operator empties it (web UI / CLI)
    rig.sleep_hook = on_sleep

    assert main.run_sorter(engine=FakeEngine(), max_cycles=1) == "stopped"
    assert seen, "machine never paused"
    assert seen["status"]["message"] == "bin 2 full — empty it"
    assert seen["status"]["paused_bin"] == 2
    assert seen["shuttle"] == ("home", "hold")     # card held on the cradle
    assert seen["load"] == pytest.approx(1.75)
    assert seen["count"] == 1                      # not overfilled
    assert seen["safe"] == (False, False, servos.ARM_PARK)
    # resumed: the held card went into the emptied bin
    assert main._bins.count(2) == 1
    assert shuttle.state()[:2] == ("home", "level")


def test_bin_full_pause_without_reset_never_routes(rig):
    main._bins.limits[2] = 0
    with pytest.raises(main.BinFull):
        main.sort_one_card(FakeEngine())
    assert main._bins.count(2) == 0
    assert shuttle.state()[:2] == ("home", "hold")
    assert loadcell.read_grams() == pytest.approx(1.75)
    _assert_safe(rig)


@pytest.mark.parametrize("where", ["camera", "arm_drop", "shuttle_route"])
def test_exception_mid_cycle_makes_hardware_safe(rig, monkeypatch, where):
    def boom(*a, **k):
        raise RuntimeError(f"{where} exploded")
    if where == "camera":
        monkeypatch.setattr(camera, "capture_card_jpeg", boom)
    elif where == "arm_drop":
        monkeypatch.setattr(servos, "arm_to_drop", boom)          # pump is ON here
    else:
        monkeypatch.setattr(shuttle, "route", boom)
    assert main.run_sorter(engine=FakeEngine(), max_cycles=5) == "error"
    assert main._status["state"] == "error"
    assert main._stats["errors"] == 1
    _assert_safe(rig)
    assert shuttle.state()[1] == "hold"


def test_dry_run_sends_everything_to_reject(rig):
    assert main.sort_one_card(FakeEngine(), dry_run=True) == main.REJECT_BIN
    assert main._bins.count(2) == 0 and main._bins.count(9) == 1


# ── bin counts, CLI and web ──────────────────────────────────────────────────
def test_bin_counts_persist_and_cli_reset(rig, monkeypatch, capsys):
    main._bins.increment(4)
    main._bins.increment(4)
    again = main.BinCounts(main._bins.counts_file, main._bins.limits_file, main.DEFAULT_BIN_LIMITS)
    assert again.count(4) == 2
    monkeypatch.setattr(sys, "argv", ["main.py", "--empty-bin", "4"])
    with pytest.raises(SystemExit) as ex:
        main.main()
    assert ex.value.code == 0
    assert main._bins.count(4) == 0
    main._bins.increment(1)
    monkeypatch.setattr(sys, "argv", ["main.py", "--empty-all"])
    with pytest.raises(SystemExit):
        main.main()
    assert main._bins.count(1) == 0


def test_bin_limits_configurable(tmp_path):
    (tmp_path / "limits.json").write_text('{"4": 10, "9": 20}')
    b = main.BinCounts(tmp_path / "c.json", tmp_path / "limits.json", main.DEFAULT_BIN_LIMITS)
    assert b.limits[4] == 10 and b.limits[9] == 20 and b.limits[0] == 50


def test_web_reset_bin(rig):
    from web.app import create_app
    client = create_app().test_client()
    main._bins.increment(3)
    st = client.get("/api/status").get_json()
    assert st["bin_counts"]["3"] == 1 and st["bin_limits"]["9"] == 35
    r = client.post("/api/bins/3/empty")
    assert r.status_code == 200 and r.get_json()["counts"]["3"] == 0
    assert client.post("/api/bins/8/empty").status_code == 400
    main._bins.increment(5)
    assert client.post("/api/bins/empty-all").get_json()["counts"]["5"] == 0


# ── card detection ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("speed", [80, 150, 220, 350])
def test_centring_accuracy(speed):
    scene = card_detect.MockScene(seed=speed)
    scene.speed_mm_s = speed
    src = card_detect.MockSource(scene)
    ref = card_detect.capture_reference(src)
    res = card_detect.centre_card(ref, lambda: None, lambda: None, lambda: None, source=src)
    assert res.ok and res.reason == "centred"
    true_offset = scene.card_x_mm - card_detect.CAM_X_MM
    assert abs(true_offset) <= card_detect.CENTER_TOL_MM
    assert abs(res.offset_mm - true_offset) < 1.0      # measurement vs truth
    assert not scene.running


def test_measure_partial_card_uses_leading_edge():
    scene = card_detect.MockScene(seed=3)
    ref = scene.render(with_card=False)
    scene.card_x_mm = card_detect.CAM_X_MM - 30        # trailing edge hidden by the hood
    det = card_detect.measure(scene.render(), ref)
    assert det.found and det.trail_mm is None and det.lead_mm is not None
    assert det.centre_mm == pytest.approx(-30, abs=1.0)


def test_measure_empty_station():
    scene = card_detect.MockScene(seed=4)
    ref = scene.render(with_card=False)
    assert not card_detect.measure(scene.render(with_card=False), ref).found


def test_camera_flip_rotates_180():
    arr = np.arange(12).reshape(3, 4)
    flipped = camera._flip(arr)
    assert flipped[0, 0] == arr[-1, -1] and flipped[-1, -1] == arr[0, 0]


def test_legacy_crop_file_is_rotated(tmp_path, monkeypatch):
    f = tmp_path / "camera_crop.json"
    w, h = camera.CAPTURE_RESOLUTION
    f.write_text(f'{{"left": 10, "top": 20, "right": 300, "bottom": 200, "resolution": [{w}, {h}]}}')
    monkeypatch.setattr(camera, "_CROP_FILE", f)
    monkeypatch.setattr(camera, "CARD_CROP", camera.CARD_CROP)
    camera.load_crop_config()
    assert camera.CARD_CROP == (w - 300, h - 200, w - 10, h - 20)
