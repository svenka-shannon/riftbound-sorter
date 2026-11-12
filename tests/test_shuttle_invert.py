"""Per-channel servo invert for the shuttle (config "invert": {"1": .., "2": ..}),
its config validation, and the calibrate tool's direction check that writes it."""

import json

import pytest

from conftest import ROOT
from hardware import shuttle

CH1, CH2 = shuttle.CH_TILT, shuttle.CH_SHUTTLE


class FakeServo:
    """Stands in for adafruit_motor.servo.Servo: records every angle written."""

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


@pytest.fixture
def pwm(monkeypatch):
    """Real write path (_MOCK off) into fake servos; no real sleeps."""
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


def write_cal(data):
    shuttle._CALIBRATION_FILE.write_text(json.dumps(data) if not isinstance(data, str) else data)


# ── invert maths ──────────────────────────────────────────────────────────────
def test_default_not_inverted(pwm):
    assert shuttle.SHUTTLE_INVERT == {CH1: False, CH2: False}
    shuttle._write(CH1, 97.0)
    shuttle._write(CH2, 75.5)
    assert pwm[CH1].angle == 97.0 and pwm[CH2].angle == 75.5


@pytest.mark.parametrize("rng", [180, 270])
def test_inverted_write_is_range_minus_angle(pwm, rng):
    pwm["set_range"](CH2, rng)
    shuttle.SHUTTLE_INVERT[CH2] = True
    for a in (0.0, 2.0, 45.0, 75.5, 87.3, 178.0, rng / 2, float(rng)):
        shuttle._write(CH2, a)
        assert shuttle._pos[CH2] == a                         # tracked angle stays geometric
        assert pwm[CH2].angle == pytest.approx(rng - a)       # PWM gets the mirror
        assert shuttle.pwm_angle(CH2, a) == pytest.approx(rng - a)
        assert shuttle.pulse_us(CH2, a) == pytest.approx(500 + 2000 * (rng - a) / rng)
    # ch1 untouched by ch2's invert
    shuttle._write(CH1, 97.0)
    assert pwm[CH1].angle == 97.0


@pytest.mark.parametrize("rng", [180, 270])
def test_inverted_write_clamps_before_mirroring(pwm, rng):
    pwm["set_range"](CH1, rng)
    shuttle.SHUTTLE_INVERT[CH1] = True
    shuttle._write(CH1, rng + 40.0)
    assert shuttle._pos[CH1] == rng and pwm[CH1].angle == 0.0
    shuttle._write(CH1, -10.0)
    assert shuttle._pos[CH1] == 0.0 and pwm[CH1].angle == rng
    assert shuttle.pulse_us(CH1, 0.0) == 2500.0 and shuttle.pulse_us(CH1, rng) == 500.0


def _sort_cycle_writes(pwm):
    """home + a lower and an upper sort; returns the physical writes per channel."""
    for f in (CH1, CH2):
        pwm[f].writes.clear()
    shuttle._pos[CH1] = shuttle._pos[CH2] = None             # what init() does (no hardware here)
    shuttle._tilt_state = shuttle._target = shuttle._jammed = None
    shuttle.home()
    shuttle.route(2)          # column 2, lower
    shuttle.route(5)          # column 1, upper
    shuttle.route(shuttle.REJECT_BIN)
    return {ch: list(pwm[ch].writes) for ch in (CH1, CH2)}, shuttle.state()


@pytest.mark.parametrize("rng", [180, 270])
def test_full_cycle_inverted_is_exact_mirror(pwm, rng):
    """Same moves, same ramps and interlocks: an inverted channel's PWM stream is
    the mirror (range − a) of the non-inverted one, the module state identical."""
    pwm["set_range"](CH2, rng)
    plain, state_plain = _sort_cycle_writes(pwm)
    shuttle.SHUTTLE_INVERT.update({CH1: True, CH2: True})
    inv, state_inv = _sort_cycle_writes(pwm)
    assert state_inv == state_plain                           # geometric angles / poses unchanged
    for ch, r in ((CH1, 180), (CH2, rng)):
        assert len(inv[ch]) == len(plain[ch]) > 10            # ramped: many small steps
        assert inv[ch] == pytest.approx([r - a for a in plain[ch]])
    final = state_inv[2]
    assert final[CH1] == shuttle.TILT_ANGLES["level"] and final[CH2] == shuttle.SHUTTLE_ANGLES["home"]


# ── config: load + validation ─────────────────────────────────────────────────
def test_config_invert_loaded(pwm):
    write_cal({"invert": {"1": False, "2": True}, "actuation_range": {"2": 270}})
    shuttle._load_calibration()
    assert shuttle.SHUTTLE_INVERT == {CH1: False, CH2: True}
    assert shuttle.SHUTTLE_ACTUATION_RANGE[CH2] == 270
    pwm[CH2].actuation_range = 270
    shuttle._write(CH2, 178.0)
    assert pwm[CH2].angle == pytest.approx(92.0)


def test_config_invert_absent_resets_to_false():
    write_cal({"invert": {"1": True}})
    shuttle._load_calibration()
    assert shuttle.SHUTTLE_INVERT == {CH1: True, CH2: False}
    write_cal({"tilt": {"hold": 97.0}})                       # invert key removed
    shuttle._load_calibration()
    assert shuttle.SHUTTLE_INVERT == {CH1: False, CH2: False}
    write_cal({"invert": {"1": True}})
    shuttle._load_calibration()
    shuttle._CALIBRATION_FILE.unlink()                        # whole file removed
    shuttle._load_calibration()
    assert shuttle.SHUTTLE_INVERT == {CH1: False, CH2: False}


@pytest.mark.parametrize("invert, needle", [
    ({"1": "true"}, "invert.1: must be true or false"),
    ({"2": "false"}, "invert.2: must be true or false"),
    ({"1": 1}, "invert.1: must be true or false"),
    ({"2": 0}, "invert.2: must be true or false"),
    ({"1": None}, "invert.1: must be true or false"),
    ({"0": True}, "invert.0: unknown channel"),
    ({"3": False}, "invert.3: unknown channel"),
    ({"tilt": True}, "invert.tilt: unknown channel"),
    ({"01": True}, "invert.01: unknown channel"),
    (True, '"invert" must be an object'),
    ([True, False], '"invert" must be an object'),
])
def test_config_invert_rejected(invert, needle):
    write_cal({"tilt": {"hold": 99.0}, "invert": invert})
    hold = shuttle.TILT_ANGLES["hold"]
    with pytest.raises(shuttle.ShuttleConfigError, match="refusing to start") as ei:
        shuttle._load_calibration()
    assert needle in str(ei.value)
    assert shuttle.TILT_ANGLES["hold"] == hold                # nothing applied
    assert shuttle.SHUTTLE_INVERT == {CH1: False, CH2: False}


def test_config_invert_lists_every_problem():
    write_cal({"invert": {"1": "yes", "2": True, "5": False}})
    with pytest.raises(shuttle.ShuttleConfigError) as ei:
        shuttle._load_calibration()
    msg = str(ei.value)
    assert "invert.1" in msg and "invert.5" in msg and "invert.2" not in msg
    assert isinstance(ei.value, shuttle.ShuttleError)
    assert shuttle.SHUTTLE_INVERT[CH2] is False               # the good entry is not half-applied


def test_init_refuses_bad_or_unreadable_file():
    write_cal({"invert": {"2": "true"}})
    with pytest.raises(shuttle.ShuttleConfigError):
        shuttle.init()
    write_cal('{"invert": {"2": tru')                         # broken JSON: no silent defaults
    with pytest.raises(shuttle.ShuttleConfigError, match="could not read"):
        shuttle.init()
    write_cal("[1, 2]")
    with pytest.raises(shuttle.ShuttleConfigError, match="JSON object"):
        shuttle.init()


# ── calibrate_servos.py direction check ───────────────────────────────────────
def _load_script(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def cal(monkeypatch):
    cs = _load_script("calibrate_servos")
    cs.load_modules(mock=True)
    assert cs.shuttle is shuttle
    monkeypatch.setattr(cs, "_shuttle_ready", False)
    writes = []
    real_write = shuttle._write

    def rec(ch, a):
        writes.append((ch, float(a)))
        real_write(ch, a)
    monkeypatch.setattr(shuttle, "_write", rec)

    def run(ch, answers):
        it = iter(answers)
        monkeypatch.setattr(cs, "ask", lambda prompt="": next(it))
        result = cs.direction_check(ch)
        assert next(it, None) is None, "unused scripted answers"
        return result
    cs.run, cs.writes = run, writes
    yield cs
    shuttle._pos[CH1] = shuttle._pos[CH2] = None


def _assert_ramped_sweep(writes, ch):
    angles = [a for c, a in writes if c == ch]
    assert all(c == ch for c, _ in writes)                    # only the checked channel moved
    assert angles[0] == 80.0                                  # unknown pose → one step to 80
    assert max(angles) == pytest.approx(100.0) and angles[-1] == pytest.approx(80.0)
    steps = [abs(b - a) for a, b in zip(angles, angles[1:])]
    assert len(steps) > 40 and max(steps) < 1.0               # 80 ↔ 100 ramped in small steps


@pytest.mark.parametrize("ch", [CH1, CH2])
def test_direction_wrong_writes_invert_true(cal, ch):
    write_cal({"tilt": {"hold": 97.5}, "_note": "keep me"})
    # Enter (bare, move) · Enter (sweep) · "n" wrong way · "n" no re-check
    assert cal.run(ch, ["", "", "n", "n"]) is False
    data = json.loads(shuttle._CALIBRATION_FILE.read_text())
    assert data["invert"] == {str(ch): True}
    assert data["tilt"] == {"hold": 97.5} and data["_note"] == "keep me"   # rest of the file kept
    assert shuttle.SHUTTLE_INVERT[ch] is True
    _assert_ramped_sweep(cal.writes, ch)
    shuttle._load_calibration()                               # the written file validates
    assert shuttle.SHUTTLE_INVERT[ch] is True


def test_direction_ok_writes_nothing(cal):
    write_cal({"invert": {"1": False}})
    before = shuttle._CALIBRATION_FILE.read_text()
    assert cal.run(CH2, ["", "", "y"]) is True
    assert shuttle._CALIBRATION_FILE.read_text() == before
    assert shuttle.SHUTTLE_INVERT[CH2] is False
    _assert_ramped_sweep(cal.writes, CH2)


def test_direction_recheck_after_flip(cal):
    """Wrong → invert written → re-check (Enter) runs with the new invert → OK."""
    assert cal.run(CH2, ["", "", "n", "", "", "", "y"]) is True
    assert json.loads(shuttle._CALIBRATION_FILE.read_text())["invert"] == {"2": True}
    assert shuttle.SHUTTLE_INVERT[CH2] is True


def test_direction_flips_an_existing_true_back(cal):
    write_cal({"invert": {"1": True, "2": True}})
    cal.run(CH1, ["", "", "no", "n"])
    assert json.loads(shuttle._CALIBRATION_FILE.read_text())["invert"] == {"1": False, "2": True}


def test_direction_again_repeats_sweep(cal):
    assert cal.run(CH1, ["", "", "a", "", "y"]) is True
    angles = [a for _, a in cal.writes]
    assert sum(1 for a, b in zip(angles, angles[1:]) if a < 100.0 <= b + 1e-9) == 2   # swept twice


def test_direction_skip_and_refusals(cal, monkeypatch):
    assert cal.run(CH2, ["n"]) is False                       # declined: nothing moves
    assert cal.writes == [] and not shuttle._CALIBRATION_FILE.exists()
    monkeypatch.setattr(cal, "_shuttle_ready", True)          # mechanism attached: refuse
    assert cal.run(CH2, []) is False
    assert cal.writes == []
    cal.offer_direction_check(CH2)                            # not even offered (ask() not called)


def test_offer_before_sections(cal, monkeypatch):
    seen = []
    monkeypatch.setattr(cal, "direction_check", lambda ch: seen.append(ch))
    monkeypatch.setattr(cal, "ask", lambda prompt="": "y")
    cal.offer_direction_check(CH1)
    monkeypatch.setattr(cal, "ask", lambda prompt="": "")      # default: no
    cal.offer_direction_check(CH2)
    assert seen == [CH1]
