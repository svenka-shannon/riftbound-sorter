"""2.3.2: the centring offset for 270° servos (geometric 0–180° in the middle of
the servo's travel, applied only at the PWM write) and the calibrate tool's
bare-servo travel test (menu 't')."""

import json
import math
import time

import pytest

from conftest import ROOT
from hardware import servos, shuttle

CH0, CH1, CH2 = servos.CH_PICKUP_ARM, shuttle.CH_TILT, shuttle.CH_SHUTTLE
OFFSET = {180: 0.0, 270: 45.0}
# A 270° servo keeps its whole 45° of spare travel at each end: geometric 0 / 180
# are 833 / 2167 µs, never nearer than this to a pulse limit.
MARGIN_270_US = 2000.0 * 45.0 / 270.0          # 333.3 µs


class FakeServo:
    """Stands in for adafruit_motor.servo.Servo: records every PWM angle written."""

    def __init__(self, actuation_range):
        self.actuation_range = actuation_range
        self.writes = []

    @property
    def angle(self):
        return self.writes[-1] if self.writes else None

    @angle.setter
    def angle(self, a):
        assert 0.0 <= a <= self.actuation_range, a       # Adafruit raises outside the range
        self.writes.append(a)

    def pulses(self):
        return [500.0 + 2000.0 * a / self.actuation_range for a in self.writes]


def _pulse(a, rng):
    return 500.0 + 2000.0 * a / rng


# ── offset maths ──────────────────────────────────────────────────────────────
def test_offset_derived_from_range():
    assert servos.centring_offset(180) == 0.0 and servos.centring_offset(270) == 45.0
    assert servos.geometric_limits(180) == (0.0, 180.0)
    assert servos.geometric_limits(270) == (-45.0, 225.0)
    assert math.copysign(1.0, servos.geometric_limits(180)[0]) == 1.0      # +0, not −0 in messages
    # not a config key: machine.json only knows ARM_ACTUATION_RANGE, shuttle only actuation_range
    assert "centring_offset" not in shuttle.CAL_SECTIONS
    _, problems = shuttle.validate_calibration({"centring_offset": {"2": 45}})
    assert any("unknown section" in p for p in problems)


@pytest.fixture
def arm_pwm(monkeypatch):
    """ch0 real write path (_MOCK off) into a fake servo; no real sleeps."""
    fake = FakeServo(servos.ARM_ACTUATION_RANGE)
    monkeypatch.setattr(servos, "_MOCK", False)
    monkeypatch.setattr(servos, "_servos", {CH0: fake})
    monkeypatch.setattr(servos, "_arm_angle", None)
    monkeypatch.setattr(time, "sleep", lambda s: None)

    def set_range(rng):
        monkeypatch.setattr(servos, "ARM_ACTUATION_RANGE", rng)
        fake.actuation_range = rng
    fake.set_range = set_range
    return fake


@pytest.mark.parametrize("rng", [180, 270])
def test_arm_mapping_both_ends(arm_pwm, rng):
    arm_pwm.set_range(rng)
    off = OFFSET[rng]
    for a, us in ((0.0, _pulse(off, rng)), (90.0, 1500.0), (180.0, _pulse(180 + off, rng))):
        assert servos.arm_pwm_angle(a) == pytest.approx(a + off)
        assert servos.arm_pulse_us(a) == pytest.approx(us)
        servos._arm_write(a)
        assert servos.arm_angle() == a                        # tracked angle stays geometric
        assert arm_pwm.angle == pytest.approx(a + off)        # PWM gets the offset
    if rng == 180:
        assert servos.arm_pulse_us(0.0) == 500.0 and servos.arm_pulse_us(180.0) == 2500.0
    else:
        assert servos.arm_pulse_us(0.0) == pytest.approx(833.33, abs=0.01)
        assert servos.arm_pulse_us(180.0) == pytest.approx(2166.67, abs=0.01)
    # PARK 90° is mid-pulse on either range: the crank is fitted at the same commanded pose
    assert servos.arm_pulse_us(90.0) == 1500.0


@pytest.mark.parametrize("rng", [180, 270])
def test_arm_clamps_to_geometric_reach(arm_pwm, rng):
    arm_pwm.set_range(rng)
    lo, hi = servos.geometric_limits(rng)
    assert servos.arm_pwm_angle(hi + 50) == rng and servos.arm_pwm_angle(lo - 50) == 0.0
    servos.move_arm_smooth(hi + 50)                           # unknown pose: straight there, clamped
    assert servos.arm_angle() == hi and arm_pwm.angle == rng
    servos.move_arm_smooth(lo - 50)
    assert servos.arm_angle() == lo and arm_pwm.angle == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("rng", [180, 270])
def test_arm_cycle_pulses_in_range(arm_pwm, rng):
    """Park → pick → park → drop → park, and the rest-pose write in init(): every
    pulse in 500–2500 µs; on a 270° servo ≥ 333 µs from either limit."""
    arm_pwm.set_range(rng)
    servos.arm_park()
    for fn in (servos.arm_to_pick, servos.arm_park, servos.arm_to_drop, servos.arm_park):
        fn()
    assert len(arm_pwm.writes) > 20
    lo_us = 500.0 + (MARGIN_270_US if rng == 270 else 0.0) - 1e-6
    hi_us = 2500.0 - (MARGIN_270_US if rng == 270 else 0.0) + 1e-6
    assert all(lo_us <= us <= hi_us for us in arm_pwm.pulses())
    assert arm_pwm.writes[-1] == pytest.approx(90.0 + OFFSET[rng])


def test_arm_init_rest_write_has_offset(monkeypatch):
    """init(assume_parked=True) re-asserts PARK through the same mapping."""
    import types
    fake = FakeServo(270)
    monkeypatch.setattr(servos, "ARM_ACTUATION_RANGE", 270)
    monkeypatch.setattr(servos, "_MOCK", False)
    monkeypatch.setattr(servos, "_pca", None)                  # restored to None afterwards
    monkeypatch.setattr(servos, "_servos", {})
    monkeypatch.setattr(servos, "_arm_angle", None)
    pca = types.SimpleNamespace(frequency=0, channels=[object()] * 16)
    monkeypatch.setattr(servos, "board", types.SimpleNamespace(SCL=0, SDA=1), raising=False)
    monkeypatch.setattr(servos, "busio", types.SimpleNamespace(I2C=lambda *a: None), raising=False)
    monkeypatch.setattr(servos, "PCA9685", lambda i2c, address: pca, raising=False)
    monkeypatch.setattr(servos, "adafruit_servo", types.SimpleNamespace(Servo=lambda ch, **kw: fake),
                        raising=False)
    servos.init(assume_parked=True)
    assert servos.arm_angle() == servos.ARM_PARK == 90.0
    assert fake.writes == [pytest.approx(135.0)]               # 90 + 45 → 1500 µs
    assert fake.pulses() == [pytest.approx(1500.0)]


@pytest.fixture
def pwm(monkeypatch):
    """ch1/ch2 real write path (_MOCK off) into fake servos; no real sleeps."""
    monkeypatch.setattr(shuttle, "_MOCK", False)
    monkeypatch.setattr(shuttle, "_sleep", lambda s: None)
    fakes = {ch: FakeServo(shuttle.SHUTTLE_ACTUATION_RANGE[ch]) for ch in (CH1, CH2)}
    monkeypatch.setattr(shuttle, "_servos", fakes)

    def set_range(ch, rng):
        shuttle.SHUTTLE_ACTUATION_RANGE[ch] = rng
        fakes[ch].actuation_range = rng
    fakes["set_range"] = set_range
    yield fakes
    shuttle._pos[CH1] = shuttle._pos[CH2] = None


@pytest.mark.parametrize("rng", [180, 270])
@pytest.mark.parametrize("invert", [False, True])
@pytest.mark.parametrize("ch", [CH1, CH2])
def test_shuttle_mapping_both_ends(pwm, ch, rng, invert):
    pwm["set_range"](ch, rng)
    shuttle.SHUTTLE_INVERT[ch] = invert
    off = OFFSET[rng]
    for a in (0.0, 90.0, 180.0):
        want = (rng - off - a) if invert else (a + off)
        shuttle._write(ch, a)
        assert shuttle._pos[ch] == a                          # geometric
        assert pwm[ch].angle == pytest.approx(want)
        assert shuttle.pwm_angle(ch, a) == pytest.approx(want)
        assert shuttle.pulse_us(ch, a) == pytest.approx(_pulse(want, rng))
    assert shuttle.pulse_us(ch, 90.0) == pytest.approx(1500.0)   # ψ 90 / mid: same pulse on any range
    ends = sorted([shuttle.pulse_us(ch, 0.0), shuttle.pulse_us(ch, 180.0)])
    if rng == 180:
        assert ends == [500.0, 2500.0]
    else:
        assert ends == [pytest.approx(500 + MARGIN_270_US), pytest.approx(2500 - MARGIN_270_US)]


@pytest.mark.parametrize("rng", [180, 270])
@pytest.mark.parametrize("invert", [False, True])
def test_shuttle_sort_cycle_pulses_in_range(pwm, rng, invert):
    """home + every column on both floors + reject: every pulse inside 500–2500 µs,
    and on a 270° servo inside it by the full 45° margin."""
    for ch in (CH1, CH2):
        pwm["set_range"](ch, rng)
        shuttle.SHUTTLE_INVERT[ch] = invert
        pwm[ch].writes.clear()
    shuttle._pos[CH1] = shuttle._pos[CH2] = None
    shuttle._tilt_state = shuttle._target = shuttle._jammed = None
    shuttle.home()
    for b in (0, 1, 2, 3, 4, 5, 6, 7, shuttle.REJECT_BIN):
        shuttle.route(b)
    m = MARGIN_270_US if rng == 270 else 0.0
    for ch in (CH1, CH2):
        assert len(pwm[ch].writes) > 50
        assert all(500.0 + m - 1e-6 <= us <= 2500.0 - m + 1e-6 for us in pwm[ch].pulses()), ch


def test_shuttle_270_extra_travel_reachable(pwm):
    """A geometric angle past 0° / 180° (a low-gain servo's reject / column 0)
    is a real command on a 270° servo, clamped only at its reach."""
    pwm["set_range"](CH2, 270)
    shuttle._write(CH2, -5.0)
    assert shuttle._pos[CH2] == -5.0 and pwm[CH2].angle == pytest.approx(40.0)
    shuttle._write(CH2, 230.0)
    assert shuttle._pos[CH2] == 225.0 and pwm[CH2].angle == pytest.approx(270.0)
    pwm["set_range"](CH2, 180)
    shuttle._write(CH2, -5.0)
    assert shuttle._pos[CH2] == 0.0 and pwm[CH2].angle == 0.0


# ── validation stays geometric ────────────────────────────────────────────────
def test_arm_windows_on_270():
    assert servos.sanity_window("ARM_PICK", 175.0, 270) == (155.0, 185.0)
    assert servos.sanity_window("ARM_DROP", 5.0, 270) == (-5.0, 25.0)
    assert servos.sanity_window("ARM_PARK", 90.0, 270) == (80.0, 100.0)
    assert servos.sanity_window("ARM_DROP", 175.0, 270) == (155.0, 185.0)     # mirrored
    assert servos.sanity_window("ARM_DROP", 5.0, 180) == (0.0, 25.0)
    # 255° DS3218 (gain −5.6 %), crank fitted 1.8° off: needs PICK ≈ 181.9, DROP ≈ −1.9
    k = 255.0 / 270.0
    cal = {"pickup_arm": {"ARM_PICK": round(90 + 86.8 / k, 2), "ARM_DROP": round(90 - 86.8 / k, 2),
                          "ARM_PARK": 90.0}}
    assert servos.validate_calibration(cal, 270)[1] == []
    problems = servos.validate_calibration(cal, 180)[1]
    assert any("ARM_PICK" in p and "outside the servo range [0, 180]" in p for p in problems)
    assert any("ARM_DROP" in p and "outside the servo range [0, 180]" in p for p in problems)
    # the typo guards still hold on 270
    for bad in ({"ARM_DROP": 50.0}, {"ARM_PICK": 157.0}, {"ARM_DROP": -10.0}, {"ARM_PICK": 230.0}):
        assert servos.validate_calibration({"pickup_arm": bad}, 270)[1], bad
    assert "[-45, 225]" in servos.validate_calibration({"pickup_arm": {"ARM_PICK": 230.0}}, 270)[1][0]


def test_shuttle_windows_on_270():
    assert shuttle.sanity_window("shuttle", "reject", 270) == (-10.0, 14.0)
    assert shuttle.sanity_window("shuttle", 0, 270) == (166.0, 190.0)
    assert shuttle.sanity_window("shuttle", "reject", 180) == (0.0, 14.0)
    assert shuttle.sanity_window("shuttle", 0, 180) == (166.0, 180.0)
    ok = {"actuation_range": {"2": 270}, "shuttle": {"reject": -3.0, "0": 183.0}}
    assert shuttle.validate_calibration(ok)[1] == []
    bad = {"shuttle": {"reject": -3.0, "0": 183.0}}            # same on a 180° servo
    problems = shuttle.validate_calibration(bad)[1]
    assert sum("outside the servo range [0, 180]" in p for p in problems) == 2


def test_documented_270_example_still_valid():
    """§16.4's example file (nominal angles + actuation_range 270) passes."""
    cal = {"tilt": {"hold": 97.0, "level": 93.1, "upper": 112.2, "lower": 41.5},
           "shuttle": {"home": 75.5, "0": 178.0, "1": 87.3, "2": 65.2, "3": 45.0, "reject": 2.0},
           "invert": {"1": False, "2": False}, "actuation_range": {"2": 270}}
    assert shuttle.validate_calibration(cal)[1] == []


# ── calibrate_servos.py: readout, windows, travel test ─────────────────────────
def _load_script(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def cs(monkeypatch):
    mod = _load_script("calibrate_servos")
    mod.load_modules(mock=True)
    assert mod.servos is servos and mod.shuttle is shuttle
    monkeypatch.setattr(mod, "_arm_ready", False)
    monkeypatch.setattr(mod, "_shuttle_ready", False)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    monkeypatch.setattr(servos, "_arm_angle", None)
    yield mod
    shuttle._pos[CH1] = shuttle._pos[CH2] = None


def test_readout_pulse_includes_offset(cs, monkeypatch, capsys):
    monkeypatch.setattr(servos, "ARM_ACTUATION_RANGE", 270)
    monkeypatch.setattr(cs, "ask", lambda prompt="": "n")
    cs.jog("ARM_PARK", start=90.0, stored=90.0, nominal=90.0, lo=80.0, hi=100.0, pulse_range=270,
           move=lambda a: None, save=lambda a: True, pulse_us=servos.arm_pulse_us)
    assert "90.0°  (1500 µs)" in capsys.readouterr().out
    cs.jog("x", start=0.0, stored=0.0, nominal=0.0, lo=-5.0, hi=25.0, pulse_range=270,
           move=lambda a: None, save=lambda a: True)           # fallback formula: offset too
    assert "0.0°  ( 833 µs)" in capsys.readouterr().out
    shuttle.SHUTTLE_ACTUATION_RANGE[CH2] = 270
    shuttle.SHUTTLE_INVERT[CH2] = True
    cs.jog("carriage reject", start=2.0, stored=2.0, nominal=2.0, lo=-10.0, hi=14.0, pulse_range=270,
           move=lambda a: None, save=lambda a: True, pulse_us=lambda a: shuttle.pulse_us(CH2, a))
    assert f"({_pulse(270 - 45 - 2.0, 270):4.0f} µs)" in capsys.readouterr().out


def test_jog_windows_on_270(cs, monkeypatch):
    assert cs.window(5.0, 270, servos.sanity_window("ARM_DROP", 5.0, 270)) == (-5.0, 25.0)
    assert cs.window(175.0, 270, servos.sanity_window("ARM_PICK", 175.0, 270)) == (155.0, 185.0)
    assert cs.window(5.0, 180, servos.sanity_window("ARM_DROP", 5.0, 180)) == (0.0, 25.0)
    assert cs.carriage_limits(180) == (2.0, 178.0)
    assert cs.carriage_limits(270) == (-43.0, 223.0)
    # menu 3 on a 270° ch2: the ±12° windows are the limit, not 2 / 178
    shuttle.SHUTTLE_ACTUATION_RANGE[CH2] = 270
    seen = {}
    monkeypatch.setattr(cs, "ask", lambda prompt="": "n")

    def jog(title, *, lo, hi, **k):
        seen[title] = (lo, hi)
        return None
    monkeypatch.setattr(cs, "jog", jog)
    monkeypatch.setattr(cs, "_shuttle_ready", True)            # skip homing / direction offer
    cs._column_steps()
    assert seen["carriage reject"] == (-10.0, 14.0)
    assert seen["carriage 0"] == (166.0, 190.0)


def test_menu_lists_travel_test(cs):
    assert "t  Travel test (ch0/ch1/ch2" in cs.MENU


def test_travel_required(cs):
    assert cs.travel_required(CH0) == (87.0, 87.0)
    assert cs.travel_required(CH2) == (88.0, 88.0)
    below, above = cs.travel_required(CH1)
    assert below == pytest.approx(90 - (41.5 - 8))             # lower 41.5 − 8° window → 56.5
    assert above == pytest.approx(112.2 + 8 - 90)              # upper 112.2 + 8° window → 30.2
    assert below + above == pytest.approx(86.7)


@pytest.mark.parametrize("ch, below, above, rng, ok", [
    (CH0, 87.0, 87.0, 180, True),
    (CH0, 90.0, 90.0, 180, True),
    (CH0, 86.5, 90.0, 180, False),           # 180° servo: short is short
    (CH0, 90.0, 86.0, 180, False),
    (CH0, 85.0, 85.0, 270, True),            # 255° DS3218: needs ≈ −2.1 / 182.1, windows allow −5 / 185
    (CH0, 82.0, 85.0, 270, False),           # needs ≈ −5.5 < −5
    (CH2, 88.0, 88.0, 180, True),
    (CH2, 87.5, 89.0, 180, False),
    (CH2, 85.0, 85.0, 270, True),            # needs ≈ −3.2 / 183.2 within −10 / 190
    (CH2, 75.0, 90.0, 270, False),           # needs ≈ −15.6 < −10
    (CH1, 57.0, 31.0, 180, True),
    (CH1, 56.0, 31.0, 180, False),
    (CH1, 56.0, 31.0, 270, False),           # ch1's need already sits on its window edge
])
def test_travel_verdict(cs, monkeypatch, ch, below, above, rng, ok):
    if ch == CH0:
        monkeypatch.setattr(servos, "ARM_ACTUATION_RANGE", rng)
    else:
        shuttle.SHUTTLE_ACTUATION_RANGE[ch] = rng
    passed, lines = cs.travel_verdict(ch, below, above)
    assert passed is ok, lines
    assert len(lines) == 3 and lines[2].startswith("total")
    assert ("SHORT" in " ".join(lines)) == (below < cs.travel_required(ch)[0]
                                           or above < cs.travel_required(ch)[1])


def _run_travel(cs, monkeypatch, ch, answers):
    it = iter(answers)
    prompts = []

    def ask(prompt=""):
        prompts.append(prompt)
        return next(it)
    monkeypatch.setattr(cs, "ask", ask)
    result = cs.travel_test(ch)
    assert next(it, None) is None, "unused scripted answers"
    return result, prompts


def _assert_travel_sweep(angles):
    assert angles[0] == 90.0                                   # unknown pose → one step to 90
    assert min(angles) == pytest.approx(0.0) and max(angles) == pytest.approx(180.0)
    assert angles[-1] == pytest.approx(90.0)
    i0 = angles.index(min(angles))
    i180 = angles.index(max(angles))
    assert 0 < i0 < i180                                       # 90 → 0 → 180 → 90
    steps = [abs(b - a) for a, b in zip(angles[1:], angles[2:])]
    assert len(steps) > 100 and max(steps) < 1.5               # slow ramps, never a jump after the first


@pytest.mark.parametrize("ch", [CH1, CH2])
@pytest.mark.parametrize("rng", [180, 270])
def test_travel_test_shuttle_channel(cs, monkeypatch, ch, rng):
    write = {"actuation_range": {str(ch): rng}}
    shuttle._CALIBRATION_FILE.write_text(json.dumps(write))
    writes = []
    real = shuttle._write
    monkeypatch.setattr(shuttle, "_write", lambda c, a: (writes.append((c, float(a))), real(c, a)))
    pulses = []
    real_pulse = shuttle.pulse_us
    monkeypatch.setattr(shuttle, "_ramp", _wrap_ramp(shuttle._ramp, pulses, lambda a: real_pulse(ch, a)))
    req = cs.travel_required(ch)
    ok, prompts = _run_travel(cs, monkeypatch, ch,
                              ["", "", "", "", str(req[0] + 0.5), str(req[1] + 0.5)])
    assert ok is True
    assert all(c == ch for c, _ in writes)                     # only the tested channel moved
    _assert_travel_sweep([a for _, a in writes])
    m = MARGIN_270_US if rng == 270 else 0.0
    assert pulses[1] == pytest.approx(500 + m) or pulses[1] == pytest.approx(2500 - m)   # geometric 0
    assert all(500 + m - 1e-6 <= p <= 2500 - m + 1e-6 for p in pulses)
    deinits = []
    monkeypatch.setattr(shuttle, "deinit", lambda: deinits.append(1))
    _run_travel(cs, monkeypatch, ch, ["", "", "", "", ""])       # measured: Enter skips the verdict
    assert deinits == [1]                                       # ch1/ch2 switched off after the sweep
    assert sum("Mark the horn" in p for p in prompts) == 3


def _wrap_ramp(real_ramp, pulses, pulse_of):
    def ramp(ch, target, s_per_deg, min_s):
        pulses.append(pulse_of(target))
        return real_ramp(ch, target, s_per_deg, min_s)
    return ramp


@pytest.mark.parametrize("rng", [180, 270])
def test_travel_test_arm(cs, monkeypatch, rng):
    monkeypatch.setattr(servos, "ARM_ACTUATION_RANGE", rng)
    writes = []
    real = servos._arm_write
    monkeypatch.setattr(servos, "_arm_write", lambda a: (writes.append(float(a)), real(a)))
    ok, _ = _run_travel(cs, monkeypatch, CH0, ["", "", "", "", "86", "88"])
    assert ok is (rng == 270)                                   # 86° short on 180; reachable on 270
    _assert_travel_sweep(writes)
    assert all(0.0 <= servos.arm_pwm_angle(a) <= rng for a in writes)
    assert servos.arm_angle() is None and servos.arm_released()  # limp and forgotten afterwards


def test_travel_test_refused_when_homed(cs, monkeypatch):
    for flag in ("_arm_ready", "_shuttle_ready"):
        monkeypatch.setattr(cs, "_arm_ready", flag == "_arm_ready")
        monkeypatch.setattr(cs, "_shuttle_ready", flag == "_shuttle_ready")
        for ch in (CH0, CH1, CH2):
            writes = []
            monkeypatch.setattr(shuttle, "_ramp", lambda *a: writes.append(a))
            monkeypatch.setattr(servos, "move_arm_smooth", lambda *a, **k: writes.append(a))
            result, prompts = _run_travel(cs, monkeypatch, ch, [])
            assert result is None and writes == [] and prompts == []


def test_travel_test_skip_and_bad_input(cs, monkeypatch, capsys):
    writes = []
    real = shuttle._write
    monkeypatch.setattr(shuttle, "_write", lambda c, a: (writes.append(a), real(c, a)))
    assert _run_travel(cs, monkeypatch, CH2, ["n"])[0] is None   # declined: nothing moves
    assert writes == []
    # bad measurements are asked again; Enter skips the verdict
    result, _ = _run_travel(cs, monkeypatch, CH2, ["", "", "", "", "abc", "-3", "400", "nan", "88", ""])
    assert result is None
    assert capsys.readouterr().out.count("a number of degrees") == 4
    result, _ = _run_travel(cs, monkeypatch, CH2, ["", "", "", "", "87", "89"])
    out = capsys.readouterr().out
    assert result is False and "SHORT by 1.0°" in out and "DS3218MG-270" in out
