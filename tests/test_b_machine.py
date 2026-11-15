"""
Option B (turntable picker) in MOCK mode: drivers, safety rules and the sort
cycle on the simulated machine (hardware/b_mock.py). main.py's generic loop is
driven with sorter_b's hooks installed (sorter_b.install with monkeypatch, so
the v2 tests in the same session are unaffected).
"""

import json
import os
import sys
import time
from pathlib import Path

os.environ["MOCK_HARDWARE"] = "1"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest

import main
import sorter_b
from hardware import b_calibration as cal
from hardware import b_geometry as geo
from hardware import b_mock, lift, loadcell, machine_config, touch, vacuum, yaw

AUTH = {"X-Auth-Token": "t"}


class FakeEngine:
    reject_bin = 9

    def __init__(self, bin_num=2):
        self.bin_num = bin_num

    def assign_bin(self, card):
        return card.get("bin", self.bin_num)

    def describe_bin(self, b):
        return "Reject" if b == 9 else f"Bin {b}"


@pytest.fixture
def rig(monkeypatch, tmp_path):
    """Machine B installed into main, hardware initialised, nothing homed yet."""
    monkeypatch.setattr(time, "sleep", lambda s: None)
    sorter_b.install(main, monkeypatch.setattr)
    monkeypatch.setattr(main, "_bins", main.BinCounts(tmp_path / "bin_counts.json",
                                                      tmp_path / "bin_limits.json",
                                                      main.B_DEFAULT_BIN_LIMITS))
    monkeypatch.setattr(vacuum, "VENT_PIN", None)
    world = b_mock.reset(hopper_cards=10)
    rec = {"recorded": [], "card": {"name": "Jinx", "bin": 2}, "card_id": "rb_001"}
    monkeypatch.setattr(main, "identify", lambda jpeg: (rec["card_id"], 0.95))
    monkeypatch.setattr(main.riftcodex, "get_card", lambda cid: rec["card"])
    monkeypatch.setattr(main.inventory, "record_scan", lambda *a: rec["recorded"].append(a))
    main.init_hardware()
    for k in main._stats:
        main._stats[k] = 0
    world.rec = rec
    yield world
    yaw.deinit()


@pytest.fixture
def ready(rig):
    """Homed, bed checked + tared, touch self-test passed, arm at the hopper."""
    main.prepare_machine(confirmed=True)
    main._set_state("running")
    return rig


def _no_hazards(world):
    assert world.hazards() == [], world.hazards()


# ── the cycle ────────────────────────────────────────────────────────────────
def test_prepare_homes_and_ends_at_hopper(ready):
    assert yaw.homed()
    assert abs(yaw.position_deg() - cal.station_yaw("hopper")) < yaw.deg_per_step()
    assert abs(ready.yaw - 10.0) < 2 * yaw.deg_per_step()          # the real arm too
    assert lift.at_full_lift() and not vacuum.pump_is_on()
    _no_hazards(ready)


def test_full_cycle_into_a_bin(ready):
    assert main.sort_one_card(FakeEngine()) == 2
    assert main._bins.count(2) == 1
    assert ready.bins["bin2"] == [b_mock.SINGLE_G] and ready.bed == [] and ready.cup == []
    assert len(ready.hopper) == 9
    assert ready.rec["recorded"] and ready.rec["recorded"][0][2] == 2
    assert main._card_at is None and not vacuum.pump_is_on()
    assert abs(loadcell.read_grams()) < 0.01                         # bed re-tared, empty
    assert abs(yaw.position_deg() - cal.station_yaw("hopper")) < yaw.deg_per_step()  # back at the hopper
    assert main._status["last_weight_g"] == pytest.approx(1.75, abs=0.01)
    _no_hazards(ready)


def test_several_cards_and_edge_check(ready, monkeypatch):
    monkeypatch.setattr(sorter_b, "EDGE_CHECK_EVERY", 2)
    for _ in range(5):
        main.sort_one_card(FakeEngine())
    assert len(ready.bins["bin2"]) == 5 and main._bins.count(2) == 5
    _no_hazards(ready)


def test_double_goes_to_reject(ready):
    ready.hopper[-1] = b_mock.DOUBLE_G
    assert main.sort_one_card(FakeEngine()) == main.REJECT_BIN
    assert ready.bins["reject"] == [b_mock.DOUBLE_G]
    assert main._stats["double_picks"] == 1 and main._bins.count(9) == 1
    assert ready.rec["recorded"] == []            # rejects are not recorded as sorted
    _no_hazards(ready)


def test_unidentified_goes_to_reject(ready):
    ready.rec["card_id"] = None
    assert main.sort_one_card(FakeEngine()) == main.REJECT_BIN
    assert ready.bins["reject"] == [b_mock.SINGLE_G]


def test_hopper_empty_with_floor_hole(ready):
    ready.hopper.clear()
    with pytest.raises(main.HopperEmpty):
        main.sort_one_card(FakeEngine())
    assert ready.cup == [] and not vacuum.pump_is_on() and main._card_at is None
    assert lift.at_full_lift()
    _no_hazards(ready)


def test_hopper_empty_run_sorter_state(ready):
    ready.hopper[:] = [b_mock.SINGLE_G]
    assert main.run_sorter(engine=FakeEngine()) == "hopper_empty"
    assert main._bins.count(2) == 1
    assert main._assess_clean()[0]


def test_hopper_empty_without_floor_hole_needs_confirm(rig):
    rig.floor_hole = False
    main.prepare_machine(confirmed=True)
    rig.hopper.clear()
    with pytest.raises(sorter_b.HopperProbablyEmpty):
        main.sort_one_card(FakeEngine())
    assert main._card_at == "unknown"
    assert main._assess_clean()[0] is False


def test_pick_failure_stops(ready):
    ready.seal_fail = 1
    with pytest.raises(sorter_b.PickFailed):
        main.sort_one_card(FakeEngine())
    assert len(ready.hopper) == 10 and ready.bed == []
    assert main._assess_clean()[0] is False
    _no_hazards(ready)


def test_repick_failure_puts_card_back_on_bed(ready, monkeypatch):
    real = ready.on_pump
    calls = {"n": 0}

    def on_pump(on):
        if on:
            calls["n"] += 1
            if calls["n"] == 2:            # the re-pick from the bed
                ready.seal_fail = 1
        real(on)
    monkeypatch.setattr(ready, "on_pump", on_pump)
    with pytest.raises(sorter_b.PickFailed):
        main.sort_one_card(FakeEngine())
    assert ready.bed == [b_mock.SINGLE_G] and ready.cup == []
    assert main._card_at == "bed" and main._bins.count(2) == 0
    _no_hazards(ready)


def test_bin_full_waits_on_bed_then_routes(ready):
    main._bins.limits[2] = 1
    main.sort_one_card(FakeEngine())
    with pytest.raises(main.BinFull) as ei:
        main.sort_one_card(FakeEngine())
    assert ready.bed == [b_mock.SINGLE_G] and main._card_at == "bed"
    assert not vacuum.pump_is_on() and lift.at_full_lift()
    main.empty_bin(2)
    assert main._route_pending(ei.value.pending) == 2
    assert ready.bed == [] and len(ready.bins["bin2"]) == 2 and main._bins.count(2) == 1
    _no_hazards(ready)


def test_card_never_dropped_mid_swing(ready, monkeypatch):
    """A yaw failure while carrying: the card stays HELD (pump on), never dropped."""
    be = yaw.backend()
    real = be.run
    calls = {"n": 0}

    def run(direction, intervals, tick=None):
        calls["n"] += 1
        if calls["n"] == 1:              # first yaw move of the cycle: hopper → scan, card on cup
            raise RuntimeError("pigpio connection lost")
        return real(direction, intervals, tick)
    monkeypatch.setattr(be, "run", run)
    with pytest.raises(sorter_b.YawFault):
        main.sort_one_card(FakeEngine())
    assert ready.cup == [b_mock.SINGLE_G] and vacuum.pump_is_on()
    assert main._card_at == "cup" and not yaw.homed()
    assert main._cup_hold_since is not None          # the operator wait times the hold
    _no_hazards(ready)


def test_card_put_back_at_station_when_lift_fails(ready, monkeypatch):
    """Error right after the seal at the hopper: the card goes back on the stack."""
    real = lift.to_full
    calls = {"n": 0}

    def to_full():
        calls["n"] += 1
        if calls["n"] == 1:
            raise lift.LiftError("I2C error")
        return real()
    monkeypatch.setattr(lift, "to_full", to_full)
    with pytest.raises(sorter_b.LiftFault):
        main.sort_one_card(FakeEngine())
    assert ready.cup == [] and len(ready.hopper) == 10 and main._card_at is None
    _no_hazards(ready)


# ── lost steps / homing ──────────────────────────────────────────────────────
def test_lost_steps_detected_at_hopper_check(ready):
    yaw.move_to(90.0)
    ready.slip_next_deg = -12.0          # the arm ends up 12 deg lower than tracked
    with pytest.raises(sorter_b.LostStepsStop):
        main.sort_one_card(FakeEngine())
    assert not yaw.homed() and ready.cup == [] and not vacuum.pump_is_on()
    with pytest.raises(yaw.YawNotHomed):
        yaw.move_to(30.0)


def test_edge_check_catches_upward_slip(ready):
    yaw.move_to(90.0)
    ready.slip_next_deg = +5.0           # arm higher than tracked: hopper check cannot see it
    with pytest.raises(yaw.LostSteps):
        yaw.verify_edge()


@pytest.mark.parametrize("start", [100.0, 40.0, -5.0, -40.0, -70.0])
def test_homing_from_both_sides(rig, start):
    lift.to_full()
    rig.yaw = start
    yaw.home()
    assert yaw.homed() and yaw.position_deg() == 0.0
    assert -yaw.deg_per_step() - 1e-9 <= rig.yaw <= 1e-9       # the real press edge
    assert rig.home_pressed()
    _no_hazards(rig)


def test_homing_broken_wire_refused(rig):
    lift.to_full()
    rig.home_wire_broken = True
    with pytest.raises(yaw.HomingError):
        yaw.home()
    assert not yaw.homed()


def test_homing_needs_full_lift(rig):
    lift.move_to(0.0)
    with pytest.raises(yaw.YawInterlockError):
        yaw.home()


# ── interlock, limits, approach ──────────────────────────────────────────────
def test_yaw_refused_when_not_at_full_lift(ready):
    before = ready.yaw
    lift.move_to(5.0)
    with pytest.raises(yaw.YawInterlockError):
        yaw.move_to(50.0)
    assert ready.yaw == before
    lift.to_full()
    lift.release()                       # limp servo: not "at full lift" either
    with pytest.raises(yaw.YawInterlockError):
        yaw.move_to(50.0)
    _no_hazards(ready)


def test_yaw_refused_when_cup_rests_on_something(ready, monkeypatch):
    monkeypatch.setattr(touch, "is_closed", lambda: False)
    with pytest.raises(yaw.YawInterlockError, match="touch contact OPEN"):
        yaw.move_to(50.0)


def test_yaw_refused_without_interlock(ready):
    yaw.set_interlock(None)
    with pytest.raises(yaw.YawInterlockError):
        yaw.move_to(50.0)


@pytest.mark.parametrize("target", [175.5, 180.0, -80.5, -95.0])
def test_yaw_limits(ready, target):
    before, runs = ready.yaw, len(yaw.backend().runs)
    with pytest.raises(yaw.YawLimitError):
        yaw.move_to(target)
    assert ready.yaw == before and len(yaw.backend().runs) == runs


def test_approach_detour_must_respect_limits(ready):
    with pytest.raises(yaw.YawLimitError):
        yaw.move_to(-79.0, approach=True)


def test_same_direction_approach(ready):
    be = yaw.backend()
    yaw.move_to(90.0)
    n = len(be.runs)
    yaw.move_to(50.0, approach=True)           # below: undershoot, then up
    dirs = [r[0] for r in be.runs[n:]]
    assert dirs == [-1, +1]
    assert be.runs[-1][1] == yaw.deg_to_steps(50.0) - yaw.deg_to_steps(50.0 - yaw.APPROACH_UNDERSHOOT_DEG)
    assert yaw.position_deg() == pytest.approx(50.0, abs=yaw.deg_per_step())
    n = len(be.runs)
    yaw.move_to(70.0, approach=True)           # above: straight up
    assert [r[0] for r in be.runs[n:]] == [+1]
    n = len(be.runs)
    yaw.move_to(70.0, approach=True)           # already there, arrived moving up: nothing
    assert len(be.runs) == n


def test_every_station_reached_moving_up_in_a_cycle(ready, monkeypatch):
    be = yaw.backend()
    arrivals = []
    real = yaw.move_to

    def spy(target, approach=False, tick=None, settle=True):
        out = real(target, approach, tick, settle)
        if approach:
            arrivals.append(be.runs[-1][0] if be.runs else 0)
        return out
    monkeypatch.setattr(yaw, "move_to", spy)
    main.sort_one_card(FakeEngine())
    assert arrivals and all(d == +1 for d in arrivals)


def test_trapezoid_profile():
    iv = yaw.trapezoid_intervals(1422)          # 160 deg
    assert len(iv) == 1422
    vmax = yaw.deg_per_step() / min(iv)
    assert vmax <= yaw.MAX_SPEED_DEG_S * 1.01
    assert iv[0] == pytest.approx(iv[-1], rel=0.01) and iv[1] == pytest.approx(iv[-2], rel=0.01)
    assert 1.4 < sum(iv) < 2.0                              # README: 160 deg in ~1.7 s
    short = yaw.trapezoid_intervals(10)
    assert yaw.deg_per_step() / min(short) < yaw.MAX_SPEED_DEG_S  # triangle


def test_tmc_registers_and_datagrams():
    cs, vsense = yaw.current_setting(0.7, 0.11)
    assert vsense and cs == 22
    regs = yaw.driver_registers()
    assert (regs[yaw.REG_CHOPCONF] >> 24) & 0xF == 4          # MRES 16 microsteps
    assert regs[yaw.REG_IHOLD_IRUN] & 0x1F == (regs[yaw.REG_IHOLD_IRUN] >> 8) & 0x1F   # IHOLD = IRUN
    assert regs[yaw.REG_GCONF] & (1 << 6) and regs[yaw.REG_GCONF] & (1 << 7)
    dgs = yaw.driver_datagrams()
    assert len(dgs) == 12 and {d[1] for d in dgs} == {0, 1, 2, 3}     # every slave address
    for d in dgs:
        assert len(d) == 8 and d[0] == 0x05 and d[2] & 0x80 and d[7] == yaw.tmc_crc8(d[:7])


# ── touch-down ───────────────────────────────────────────────────────────────
def test_touch_down_stops_and_overtravel_is_bounded(ready):
    yaw.move_to(cal.station_yaw("hopper"), approach=True)
    st = cal.station("hopper")
    res = lift.lower_until_touch(st["approach_th"], st["limit_th"], 50.0)   # asks for 50 mm
    assert res.touched
    dz = geo.lip_z(res.th_touch) - geo.lip_z(res.th_end)
    assert dz <= lift.MAX_OVERTRAVEL_MM + 1e-6
    lift.to_full()
    _no_hazards(ready)


def test_touch_open_before_lowering_is_a_fault(ready, monkeypatch):
    monkeypatch.setattr(touch, "is_closed", lambda: False)
    with pytest.raises(lift.TouchFault):
        lift.lower_until_touch(4.0, -4.0)


def test_lift_refuses_out_of_range(ready):
    with pytest.raises(lift.LiftLimitError):
        lift.move_to(geo.TH_FULL + 1)
    with pytest.raises(lift.LiftLimitError):
        lift.move_to(geo.TH_MIN - 1)


def test_startup_selftest_catches_stuck_contact(rig):
    rig.touch_stuck_closed = True
    with pytest.raises(sorter_b.LiftFault, match="self-test"):
        main.prepare_machine(confirmed=True)


def test_startup_refuses_card_on_bed(rig):
    loadcell.tare(calibration=True)           # stored empty-bed reference
    rig.bed.append(b_mock.SINGLE_G)
    with pytest.raises(main.NeedsConfirm, match="card on the scan bed"):
        main.prepare_machine(confirmed=True)


def test_prepare_needs_confirm_when_pose_unknown(rig):
    with pytest.raises(main.NeedsConfirm):
        main.prepare_machine(confirmed=False)
    assert rig.events == []


# ── pause / stop at a card boundary ──────────────────────────────────────────
def test_stop_at_card_boundary(ready, monkeypatch):
    def ident(jpeg):
        main.request_stop()                   # mid-card
        return "rb_001", 0.95
    monkeypatch.setattr(main, "identify", ident)
    assert main.run_sorter(engine=FakeEngine(), max_cycles=5) == "stopped"
    assert main._bins.count(2) == 1 and ready.bins["bin2"] == [b_mock.SINGLE_G]
    assert ready.cup == [] and ready.bed == [] and main._card_at is None
    assert main._assess_clean()[0]
    _no_hazards(ready)


def test_pause_at_card_boundary_parks_then_stop(ready, monkeypatch):
    def ident(jpeg):
        main.request_pause()
        return "rb_001", 0.95
    monkeypatch.setattr(main, "identify", ident)
    seen = {}

    def sleep(s):
        if main._status["state"] == "paused" and "card" not in seen:
            seen["card"] = list(ready.bins["bin2"])
            main.request_stop()
    monkeypatch.setattr(time, "sleep", sleep)
    assert main.run_sorter(engine=FakeEngine(), max_cycles=5) == "stopped"
    assert seen["card"] == [b_mock.SINGLE_G]                     # the card was finished first
    assert main._bins.count(2) == 1                              # ... and no second card started
    assert ready.yaw == pytest.approx(cal.park_yaw(), abs=0.2)   # parked while paused
    assert ready.home_pressed()
    _no_hazards(ready)


def test_teardown_parks_and_records_clean(ready, monkeypatch, tmp_path):
    monkeypatch.setattr(main, "_marker_armed", True)
    main.sort_one_card(FakeEngine())
    main._set_state("stopped")
    main.teardown()
    st = main.read_machine_state()
    assert st["clean"] is True and st["rest_pose"] == "parked"
    assert ready.yaw == pytest.approx(cal.park_yaw(), abs=0.2) and not ready.yaw_enabled
    _no_hazards(ready)


def test_full_operate_loop_until_hopper_empty(rig, monkeypatch):
    """main._operate on B: confirm → home → sort the hopper → hopper_empty → wait."""
    rig.hopper[:] = [b_mock.SINGLE_G] * 3
    monkeypatch.setattr(main, "RulesEngine", lambda path: FakeEngine())
    main.confirm_clear("test")
    waits = []

    def await_operator(needs_confirm):
        waits.append((main._status["state"], needs_confirm))
        return False
    monkeypatch.setattr(main, "_await_operator", await_operator)
    main._operate(dry_run=False)
    assert main._bins.count(2) == 3 and len(rig.bins["bin2"]) == 3
    assert waits == [("hopper_empty", False)]
    assert rig.yaw == pytest.approx(cal.park_yaw(), abs=0.2)     # parked while idle
    _no_hazards(rig)


# ── calibration store / config ───────────────────────────────────────────────
def test_calibration_defaults_valid_and_typos_refused():
    _, problems = cal.validate({})
    assert problems == []
    for bad, what in [({"stations": {"bin3": {"yaw": 150.0}}}, "bin3.yaw"),
                      ({"stations": {"hopper": {"yaw": 2.0}}}, "hopper.yaw"),
                      ({"stations": {"scan": {"limit_th": 9.0}}}, "limit_th"),
                      ({"stations": {"bin9": {}}}, "unknown station"),
                      ({"park_yaw": 5.0}, "park_yaw"),
                      ({"clear_yaw": 33.0}, "clear_yaw"),
                      ({"servo_map": [[-6, 84], [10, 200]]}, "servo_map"),
                      ({"stations": {"hopper": {"yaw": "10"}}}, "finite number")]:
        _, problems = cal.validate(bad)
        assert any(what in p for p in problems), (bad, problems)


def test_machine_switch_validated():
    _, problems = machine_config.validate({"machine": "c"})
    assert any("machine" in p for p in problems)
    _, problems = machine_config.validate({"machine": "b", "yaw": {"STEP_PIN": 23, "EN_PIN": 23}})
    assert any("both GPIO 23" in p for p in problems)
    _, problems = machine_config.validate({"yaw": {"HOME_SWITCH_NC": False}})
    assert any("HOME_SWITCH_NC" in p for p in problems)


def test_b_example_config_validates():
    ex = json.loads((ROOT / "config" / "machine.b.example.json").read_text())
    cfg, problems = machine_config.validate(ex)
    assert problems == [] and ex["machine"] == "b"
    for k, v in cfg["yaw"].items():
        assert getattr(yaw, k) == (pytest.approx(v) if isinstance(v, float) else v), k
    for k, v in cfg["lift"].items():
        mod = geo if k in ("LINK_MM", "PIVOT_Z_MM", "HAND_DROP_MM", "TH_MIN", "TH_FULL") else lift
        assert getattr(mod, k) == pytest.approx(v), k
    for k, v in cfg["b_sort"].items():
        assert getattr(sorter_b, k) == (pytest.approx(v) if isinstance(v, float) else v), k
    assert cfg["touch"]["PIN"] == touch.PIN


def test_b_pin_map_has_no_clashes():
    used = {"I2C SDA": 2, "I2C SCL": 3, "UART TX": 14, "UART RX (reserved)": 15,
            "WS2812": 18, "HX711 DOUT": loadcell.DOUT_PIN, "HX711 SCK": loadcell.SCK_PIN,
            "relay": vacuum.RELAY_PIN, "STEP": yaw.STEP_PIN, "DIR": yaw.DIR_PIN, "EN": yaw.EN_PIN,
            "home": yaw.HOME_PIN, "touch": touch.PIN}
    assert len(set(used.values())) == len(used), used
    readme = (ROOT / "cad_b" / "README.md").read_text()
    assert "Pin map (option B)" in readme
    for name, pin in used.items():
        assert f"GPIO {pin}" in readme, name


def test_safe_outputs_b_levels(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("so", ROOT / "scripts" / "safe_outputs.py")
    so = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(so)
    f = tmp_path / "machine.json"
    f.write_text(json.dumps({"machine": "b"}))
    assert so.detect_machine(f) == "b"
    assert so.detect_machine(tmp_path / "missing.json") == "v2"
    levels, order = so.levels_for("b")
    assert levels[17] == 0 and levels[yaw.EN_PIN] == 1 and order[0] == 17
    assert levels[yaw.STEP_PIN] == 0 and levels[yaw.DIR_PIN] == 0
    f.write_text("{broken")
    assert so.detect_machine(f) == "unknown"
    levels, _ = so.levels_for("unknown")
    assert levels == {}


# ── manual / calibration API + web endpoints ─────────────────────────────────
@pytest.fixture
def client(rig):
    from web.app import create_app
    return create_app(token="t").test_client()


def test_web_b_endpoints(client, rig):
    main._set_state("needs_confirm")
    assert client.get("/api/b/status").status_code == 200
    assert client.post("/api/b/home").status_code == 401                 # token
    r = client.post("/api/b/home", headers=AUTH)
    assert r.status_code == 200 and r.get_json()["homed"]
    r = client.post("/api/b/goto", json={"station": "bin1"}, headers=AUTH)
    assert r.status_code == 200 and r.get_json()["station"] == "bin1"
    r = client.post("/api/b/jog", json={"deg": 1.5}, headers=AUTH)
    assert r.get_json()["yaw_deg"] == pytest.approx(71.5, abs=0.1)
    assert client.post("/api/b/jog", json={"deg": 40}, headers=AUTH).status_code == 400
    r = client.post("/api/b/save/station-yaw", json={"station": "bin1"}, headers=AUTH)
    assert r.status_code == 200
    assert json.loads(cal.CAL_FILE.read_text())["stations"]["bin1"]["yaw"] == pytest.approx(71.5, abs=0.1)
    assert cal.station_yaw("bin1") == pytest.approx(71.5, abs=0.1)
    r = client.post("/api/b/lift", json={"th": 3.0}, headers=AUTH)
    assert r.get_json()["lift_th"] == 3.0
    r = client.post("/api/b/goto", json={"station": "bin2"}, headers=AUTH)
    assert r.status_code == 500 and "lift not at full height" in r.get_json()["error"]
    r = client.post("/api/b/pump", json={"on": True}, headers=AUTH)
    assert r.get_json()["pump"] is True
    client.post("/api/b/pump", json={"on": False}, headers=AUTH)
    st = main.read_machine_state()
    assert st["clean"] is False and "manual control" in st["reason"]
    _no_hazards(rig)


def test_web_b_refused_while_running(client, monkeypatch):
    monkeypatch.setattr(main, "_active_depth", 1)
    main._set_state("paused")
    r = client.post("/api/b/home", headers=AUTH)
    assert r.status_code == 409 and "run is in progress" in r.get_json()["error"]


def test_web_b_404_on_v2(monkeypatch):
    monkeypatch.setattr(main, "MACHINE", "v2")
    from web.app import create_app
    c = create_app(token="t").test_client()
    assert c.post("/api/b/home", headers=AUTH).status_code == 404
    assert c.get("/api/b/status").status_code == 404


def test_rules_validation_uses_b_bins(rig):
    from web.app import validate_rules
    rules = {"_reject_bin": 9, "_bin_count": 6, "rules": [{"bin": 5, "match": {"type": "Spell"}}]}
    assert validate_rules(rules, set(main.SORT_BINS) | {9}) == []
    rules["rules"][0]["bin"] = 7
    assert validate_rules(rules, set(main.SORT_BINS) | {9})
    assert main.sort_one_card is sorter_b.sort_one_card


def test_status_api_reports_machine_b(client):
    r = client.get("/api/status")
    assert r.status_code == 200 and r.get_json()["machine"] == "b"
