"""
Regression tests for the fifth (confirmation) audit:
  MJ-A  arm (ch0) windows vs MG996R gain, with the 93° crank-fit procedure
  MJ-B  carriage (ch2) ±12° windows + the column 2 − column 3 ≥ 12° gap
  m1    ch1 coupler residual ≤ 1.2° (25T × hex = 2.4° lattice)
  m2    bin counts file: 0644 + data/'s owner, unreadable → exit 78, CLI exit 78
  m3    calibrate jog clamped to the per-pose window; order / gap rules at save
  m4    config_txt_line.py: missing / non-UTF-8 --file → clean error

The gain models: a servo with gain g = 1 + e turns (cmd − 90°)·g from where
the crank was fitted at 90°. Crank angles from cad/suction_arm.scad
(th_pick 178°, th_mid 93.02° at servo 90°, th_drop = 2·th_mid − th_pick) and
hardware/shuttle.py (ch2 servo angle = crank ψ, fitted at home 75.5°).

Run:
  uv run --python 3.11 --with pytest --with pillow --with numpy --with requests \
         --with flask --with imagehash pytest -q tests/
"""

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

import main
from conftest import ROOT
from hardware import instance, servos, shuttle

TH_MID = 93.02            # crank angle at servo 90° (th_mid, cad/suction_arm.scad)
TH_PICK = 178.0
TH_DROP = 2 * TH_MID - TH_PICK
SPLINE_TOOTH = 360 / 25   # 14.4°
GAINS = [round(-0.10 + 0.005 * i, 3) for i in range(41)]          # −10 % … +10 %


def _load_script(name):
    spec = importlib.util.spec_from_file_location(f"_audit5_{name}", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def cs():
    mod = _load_script("calibrate_servos")
    mod.load_modules(mock=True)
    yield mod
    if mod._lock not in (None, True):
        mod._lock.close()


def _frange(lo, hi, n):
    return [lo + (hi - lo) * i / (n - 1) for i in range(n)]


# ══ MJ-A: arm crank fit and windows ═══════════════════════════════════════════
def _nearest_fit(phase: float, target: float = TH_MID) -> float:
    """Crank angle closest to `target` over 25 spline teeth × 4 horn slots,
    for a spline whose tooth 0 / slot 0 lands at `phase`."""
    cands = [(phase + SPLINE_TOOTH * k + 90.0 * j) % 360 for k in range(25) for j in range(4)]
    return min(cands, key=lambda c: abs(c - target))


def test_tooth_times_slot_lattice_is_3_6_deg():
    for phase in _frange(0.0, SPLINE_TOOTH, 721):
        assert abs(_nearest_fit(phase) - TH_MID) <= 1.8 + 1e-9, phase
    # the documented fine step: 6 teeth one way + one slot the other way = 3.6°
    assert abs((90.0 - 6 * SPLINE_TOOTH) - 3.6) < 1e-9


def _arm_required(x: float, e: float, trim_pick=0.0, trim_drop=0.0, park_theta=TH_MID):
    """Servo angles a build needs: crank fitted at TH_MID + x (servo 90°), gain 1 + e."""
    g = 1.0 + e
    return {"ARM_PICK": 90 + (TH_PICK - TH_MID - x) / g + trim_pick,
            "ARM_DROP": 90 + (TH_DROP - TH_MID - x) / g + trim_drop,
            "ARM_PARK": 90 + (park_theta - TH_MID - x) / g}


def _arm_ok(vals) -> list:
    return servos.validate_calibration({"pickup_arm": {k: round(v, 2) for k, v in vals.items()}})[1]


@pytest.mark.parametrize("e", GAINS)
def test_arm_every_reachable_build_passes(e):
    """New procedure (crank within 1.8° of 93°): every build the servo can
    reach passes, whatever the trim and whether PARK was left at 90° or jogged
    to a vertical crank; one that cannot reach (gain below about −3.6 %: a 180°
    servo needs ≥ 87° each side of 90°, docs §19.1) is accepted at the servo's
    end stops with PARK left at 90°."""
    reachable = 0
    for x in _frange(-1.8, 1.8, 19):
        for tp in (-2.0, 0.0, 2.0):            # slider compression trim at PICK
            for td in (-1.0, 0.0, 1.0):        # DROP height trim
                for park in (TH_MID, 90.0):    # PARK at the fit pose, or jogged vertical
                    req = _arm_required(x, e, tp, td, park)
                    reach = all(0.0 <= v <= 180.0 for v in req.values())
                    if reach:
                        reachable += (tp, td) == (0.0, 0.0)
                        assert _arm_ok(req) == [], (x, e, tp, td, park, req)
                    elif park == TH_MID:   # can't work on a 180° servo anyway (§19.1)
                        clamped = {k: min(180.0, max(0.0, v)) for k, v in req.items()}
                        assert _arm_ok(clamped) == [], (x, e, tp, td, park, clamped)
                    if reach or park == TH_MID:
                        mirrored = {k: 180.0 - min(180.0, max(0.0, v)) for k, v in req.items()}
                        assert _arm_ok(mirrored) == [], ("mirrored", x, e, mirrored)
    if e >= -0.03:      # a 180° servo reaches both ends (untrimmed) down to −3 % (docs §19.1)
        assert reachable == 19 * 2


@pytest.mark.parametrize("e", [0.0, 0.05, 0.08, 0.10])
def test_arm_nominal_trim_builds_pass_100_percent_up_to_10_percent_gain(e):
    xs = _frange(-1.8, 1.8, 73)
    assert all(_arm_ok(_arm_required(x, e)) == [] for x in xs)


def test_arm_old_procedure_would_have_failed():
    """The round-4 docs (crank vertical, nearest tooth ±7.2°) need values the
    round-4 windows refused — and PICK > 180 / DROP < 0 at 0 % gain."""
    def old_ok(v):
        wins = {"ARM_PICK": (165, 180), "ARM_DROP": (0, 15), "ARM_PARK": (80, 100)}
        return all(wins[k][0] <= v[k] <= wins[k][1] for k in v)
    us = _frange(-7.2, 7.2, 289)
    frac = sum(old_ok(_arm_required(u, 0.10)) for u in us) / len(us)     # audit model, no bias
    assert 0.30 < frac < 0.40
    unreachable = sum(not all(0 <= v <= 180 for v in _arm_required(u - 3.02, 0.0).values()) for u in us)
    assert unreachable / len(us) > 0.25


ARM_TYPOS = {
    "pick_157": {"ARM_PICK": 157},                   # 175 → 157 (inside the window: symmetry)
    "pick_154": {"ARM_PICK": 154},
    "drop_50": {"ARM_DROP": 50},
    "drop_26": {"ARM_DROP": 26},
    "park_9": {"ARM_PARK": 9},
    "park_101": {"ARM_PARK": 101},
    "pick_past_end": {"ARM_PICK": 181},
    "lopsided": {"ARM_PICK": 175, "ARM_DROP": 25},   # each in its window, half-arcs 85 / 65°
    "same_side": {"ARM_PICK": 175, "ARM_DROP": 175},
}


@pytest.mark.parametrize("case", list(ARM_TYPOS))
def test_arm_typos_rejected(case):
    assert _arm_ok(ARM_TYPOS[case]), case


def test_arm_pick_157_fails_on_symmetry():
    problems = _arm_ok({"ARM_PICK": 157})
    assert len(problems) == 1 and "differ by 18°" in problems[0]


def test_arm_windows():
    assert servos.sanity_window("ARM_PICK", 160.0) == (155.0, 180.0)
    assert servos.sanity_window("ARM_DROP", 20.0) == (0.0, 25.0)
    assert servos.sanity_window("ARM_DROP", 170.0) == (155.0, 180.0)      # mirrored
    assert _arm_ok({"ARM_PICK": 165.6, "ARM_DROP": 14.4, "ARM_PARK": 90}) == []   # +10 % gain


# ══ MJ-B: carriage windows and gaps ═══════════════════════════════════════════
def _ch2_values(x: float, e: float, trim=0.0) -> dict:
    """What a builder saves: crank fitted at home within ±7.2° (x), gain 1 + e.
    Columns 1-3 / home exactly; the dead-centre stops (reject, column 0) where
    the window / the tool's 2–178° limit stops the jog."""
    g = 1.0 + e
    vals = {}
    for k, n in shuttle.NOMINAL_SHUTTLE_ANGLES.items():
        geo = {0: 180.0, "reject": 0.0}.get(k, n)
        v = 75.5 + (geo - 75.5 - x) / g + (trim if k not in (0, "reject") else 0.0)
        if k in (0, "reject"):
            lo, hi = shuttle.sanity_window("shuttle", k)
            v = min(max(v, lo, 2.0), hi, 178.0)
        vals[str(k)] = round(v, 2)
    return vals


@pytest.mark.parametrize("e", GAINS)
def test_carriage_every_build_passes(e):
    for x in _frange(-7.2, 7.2, 49):
        for trim in (-0.5, 0.0, 0.5):
            vals = _ch2_values(x, e, trim)
            assert shuttle.validate_calibration({"shuttle": vals})[1] == [], (x, e, vals)


def test_carriage_old_window_failed_at_8_percent():
    xs = _frange(-7.2, 7.2, 289)
    fails = sum(any(abs(float(v) - shuttle.NOMINAL_SHUTTLE_ANGLES[k]) > 8.0
                    for k, v in ((shuttle._shuttle_key(k), v) for k, v in _ch2_values(x, 0.08).items())
                    if k not in (0, "reject")) for x in xs)
    assert 0.05 < fails / len(xs) < 0.09                    # audit: ~7 %


CARRIAGE_TYPOS = {
    "col3_54": {"3": 54.0},          # 45 → 54: col2 − col3 = 11.2 < 12
    "col2_56.2": {"2": 56.2},        # 65.2 → 56.2: 11.2 < 12
    "col1_78.3": {"1": 78.3},        # 87.3 → 78.3: 2.8° above home
    "home_57.5": {"home": 57.5},     # 75.5 → 57.5: outside ±12
    "reject_20": {"reject": 20.0},   # outside 0–14
}


@pytest.mark.parametrize("case", list(CARRIAGE_TYPOS))
def test_carriage_typos_rejected(case):
    assert shuttle.validate_calibration({"shuttle": CARRIAGE_TYPOS[case]})[1], case


def test_carriage_gap_rule_message():
    problems = shuttle.validate_calibration({"shuttle": {"3": 54.0}})[1]
    assert problems == [p for p in problems if "shuttle.2 − shuttle.3 = 11.2° must be at least 12°" in p]
    assert shuttle.allowed_range("shuttle", 3)[1] == pytest.approx(65.2 - 12.0)


@pytest.mark.parametrize("e", GAINS)
def test_tilt_8_deg_still_covers_gain(e):
    """ch1 keeps ±8°: coupler residual ≤ 1.2°, gain round HOLD (97°)."""
    for x in _frange(-1.2, 1.2, 13):
        vals = {k: round(97.0 + (n - 97.0 - x) / (1.0 + e), 2)
                for k, n in shuttle.NOMINAL_TILT_ANGLES.items()}
        assert shuttle.validate_calibration({"tilt": vals})[1] == [], (x, e, vals)


# ══ m1: ch1 residual text ═════════════════════════════════════════════════════
def test_coupler_residual_is_1_2_everywhere():
    assert abs(SPLINE_TOOTH - 6 * 2.4) < 1e-9 and 60.0 / 2.4 == 25.0
    for path in (ROOT / "hardware" / "shuttle.py", ROOT / "docs" / "ASSEMBLY.md"):
        text = path.read_text()
        assert "0.6° residual" not in text and "≤ 0.6°" not in text and "within 0.6°" not in text \
            and "within **0.6°**" not in text, path
    assert "±25°" not in (ROOT / "docs" / "ASSEMBLY.md").read_text()
    assert "±25°" not in (ROOT / "README.md").read_text()


# ══ m3: jog clamped to the per-pose window, rules checked at save ═════════════
def _scripted(cs, monkeypatch, answers):
    it = iter(answers)
    monkeypatch.setattr(cs, "ask", lambda prompt="": next(it))
    monkeypatch.setattr(time, "sleep", lambda s: None)


@pytest.mark.parametrize("offset", [7.5, -7.5])
def test_carriage_offset_build_calibrates_in_one_pass(cs, monkeypatch, offset):
    """Every stop 7.5° off nominal (a crank one tooth-half off): one pass of
    menu 3 saves them all. Round 4 clamped the jog to the order rules against
    the old neighbours, so home could not reach 83° until column 1 moved."""
    true = {k: n + offset for k, n in shuttle.NOMINAL_SHUTTLE_ANGLES.items()}
    sign = "+" if offset > 0 else "-"
    answers = ["n", ""]                                # no direction check; Enter to home
    for _ in cs.COLUMN_STEPS:
        answers += [f"{sign}5", f"{sign}2.5", "s"]
    _scripted(cs, monkeypatch, answers)
    cs.init_base()
    cs.section_columns()
    saved = json.loads(shuttle._CALIBRATION_FILE.read_text())["shuttle"]
    for k, v in true.items():
        want = min(max(v, 2.0), 178.0)                 # the tool's carriage limits
        assert saved[str(k)] == pytest.approx(want), (k, saved)
        assert shuttle.SHUTTLE_ANGLES[k] == pytest.approx(want)
    assert cs._held["shuttle"] == {}
    assert shuttle.validate_calibration(json.loads(shuttle._CALIBRATION_FILE.read_text()))[1] == []


def test_arm_held_until_the_other_pose_follows(cs):
    assert cs.save_arm("ARM_PICK", 163.0) is True      # 73 vs 85: asymmetric by 12 → held
    assert not servos._CALIBRATION_FILE.exists() and cs._held["arm"] == {"ARM_PICK": 163.0}
    assert servos.ARM_PICK == 163.0                     # the moves of this menu use it
    assert cs.save_arm("ARM_DROP", 17.0) is True       # now symmetric: both written
    assert json.loads(servos._CALIBRATION_FILE.read_text())["pickup_arm"] == {
        "ARM_PICK": 163.0, "ARM_DROP": 17.0}
    assert cs._held["arm"] == {}


def test_held_pose_dropped_at_menu_end(cs, capsys):
    assert cs.save_shuttle("shuttle", "home", 83.0) is True     # 4.3° below column 1: held
    cs.finish_held("shuttle")
    out = capsys.readouterr().out
    assert "HELD" in out and "NOT saved: home 83°" in out
    assert not shuttle._CALIBRATION_FILE.exists() and shuttle.SHUTTLE_ANGLES["home"] == 75.5


def test_quit_mid_menu_drops_held_poses(cs, monkeypatch):
    _scripted(cs, monkeypatch, ["n", "", "+5", "+2.5", "s", "q"])    # home 83 held, then quit
    cs.init_base()
    with pytest.raises(cs.Quit):
        cs.section_columns()
    assert not shuttle._CALIBRATION_FILE.exists() and shuttle.SHUTTLE_ANGLES["home"] == 75.5


def test_jog_clamped_to_own_window_only(cs, monkeypatch):
    seen = {}

    def jog(title, *, lo, hi, **k):
        seen[title] = (lo, hi)
        return None
    monkeypatch.setattr(cs, "jog", jog)
    _scripted(cs, monkeypatch, ["n", ""])
    monkeypatch.setitem(shuttle.SHUTTLE_ANGLES, 1, 80.6)        # a neighbour already moved
    cs.init_base()
    cs.section_columns()
    assert seen["carriage home"] == (pytest.approx(63.5), pytest.approx(87.5))


# ══ m2: bin counts file ownership / mode / unreadable ═════════════════════════
def test_bin_counts_written_0644(tmp_path):
    old = os.umask(0o077)
    try:
        b = main.BinCounts(tmp_path / "bin_counts.json", tmp_path / "l.json", main.DEFAULT_BIN_LIMITS)
        b.increment(3)
    finally:
        os.umask(old)
    assert stat.S_IMODE((tmp_path / "bin_counts.json").stat().st_mode) == 0o644


def test_bin_counts_root_run_gives_files_to_data_owner(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(os, "chown", lambda p, u, g: calls.append((Path(p).name, u, g)))
    real_stat = Path.stat

    def fake_stat(self, *a, **k):
        st = real_stat(self, *a, **k)
        if self == tmp_path:
            return os.stat_result((st.st_mode, st.st_ino, st.st_dev, st.st_nlink, 1000, 1000,
                                   st.st_size, st.st_atime, st.st_mtime, st.st_ctime))
        return st
    monkeypatch.setattr(Path, "stat", fake_stat)
    b = main.BinCounts(tmp_path / "bin_counts.json", tmp_path / "l.json", main.DEFAULT_BIN_LIMITS)
    b.empty_all()
    assert ("bin_counts.json.lock", 1000, 1000) in calls
    assert any(n.startswith(".bin_counts.json.") and u == 1000 for n, u, g in calls)


@pytest.fixture
def not_root():
    if os.geteuid() == 0:
        pytest.skip("root ignores file modes")


def test_unreadable_counts_refused_not_zeroed(tmp_path, not_root):
    f = tmp_path / "bin_counts.json"
    f.write_text(json.dumps({"counts": {"4": 14, "0": 39}, "version": 3}))
    os.chmod(f, 0)
    try:
        with pytest.raises(main.BinCountsError) as ei:
            main.BinCounts(f, tmp_path / "l.json", main.DEFAULT_BIN_LIMITS)
    finally:
        os.chmod(f, 0o644)
    msg = str(ei.value)
    assert str(f) in msg and "sudo chown -R" in msg and "overfill" in msg


def test_corrupt_counts_refused(tmp_path):
    f = tmp_path / "bin_counts.json"
    f.write_text('{"counts": {"4": 1')
    with pytest.raises(main.BinCountsError, match="not a valid bin counts file"):
        main.BinCounts(f, tmp_path / "l.json", main.DEFAULT_BIN_LIMITS)


def test_unreadable_counts_while_running_keeps_counts(tmp_path, not_root, capsys):
    f = tmp_path / "bin_counts.json"
    b = main.BinCounts(f, tmp_path / "l.json", main.DEFAULT_BIN_LIMITS)
    b.increment(4)
    os.chmod(f, 0)
    try:
        assert b.count(4) == 1
    finally:
        os.chmod(f, 0o644)
    assert "could not read" in capsys.readouterr().out


def test_data_dir_problems_cover_bin_counts(tmp_path, not_root):
    lock = tmp_path / "sorter.lock"
    counts = tmp_path / "bin_counts.json"
    counts.write_text("{}")
    side = tmp_path / "bin_counts.json.lock"
    side.write_text("")
    assert instance.data_dir_problems(lock) == []
    os.chmod(counts, 0o200)
    os.chmod(side, 0o444)
    try:
        problems = instance.data_dir_problems(lock)
    finally:
        os.chmod(counts, 0o644)
        os.chmod(side, 0o644)
    assert len(problems) == 2
    assert any(str(counts) in p and "not readable" in p for p in problems)
    assert any(str(side) in p and "not writable" in p for p in problems)
    assert all(f"sudo chown -R" in p and str(tmp_path) in p for p in problems)


@pytest.mark.parametrize("flag", ["--empty-all", "--confirm-clear", "--empty-bin"])
def test_cli_unwritable_data_dir_exits_78(tmp_path, monkeypatch, capsys, not_root, flag):
    d = tmp_path / "data"
    d.mkdir()
    b = main.BinCounts(d / "bin_counts.json", tmp_path / "l.json", main.DEFAULT_BIN_LIMITS)
    b.increment(2)
    monkeypatch.setattr(main, "_bins", b)
    monkeypatch.setattr(main, "INSTANCE_LOCK_FILE", d / "sorter.lock")
    monkeypatch.setattr(main, "MACHINE_STATE_FILE", d / "machine_state.json")
    monkeypatch.setattr(sys, "argv", ["main.py", flag] + (["2"] if flag == "--empty-bin" else []))
    os.chmod(d, 0o555)
    try:
        with pytest.raises(SystemExit) as ei:
            main.main()
    finally:
        os.chmod(d, 0o755)
    assert ei.value.code == 78
    err = capsys.readouterr().err
    assert "not writable" in err and "sudo chown -R" in err and "Traceback" not in err
    assert json.loads((d / "bin_counts.json").read_text())["counts"]["2"] == 1   # unchanged


def test_cli_permission_error_mid_way_exits_78(tmp_path, monkeypatch, capsys):
    b = main.BinCounts(tmp_path / "bin_counts.json", tmp_path / "l.json", main.DEFAULT_BIN_LIMITS)
    monkeypatch.setattr(main, "_bins", b)

    def denied(*a, **k):
        raise PermissionError(13, "Permission denied", str(tmp_path / "x.tmp"))
    monkeypatch.setattr(b, "empty_all", denied)
    monkeypatch.setattr(sys, "argv", ["main.py", "--empty-all"])
    with pytest.raises(SystemExit) as ei:
        main.main()
    assert ei.value.code == 78 and "sudo chown -R" in capsys.readouterr().err


def _app_copy(tmp_path) -> Path:
    """main.py + its packages in a fresh directory (its own data/)."""
    w = tmp_path / "app"
    w.mkdir()
    ignore = shutil.ignore_patterns("__pycache__")
    for d in ("hardware", "vision", "api", "sorter", "web", "config"):
        shutil.copytree(ROOT / d, w / d, ignore=ignore)
    shutil.copy2(ROOT / "main.py", w / "main.py")
    (w / "data").mkdir()
    return w


@pytest.mark.parametrize("args", [[], ["--empty-all"], ["--web-only"]])
def test_main_unreadable_counts_exits_78(tmp_path, not_root, args):
    w = _app_copy(tmp_path)
    f = w / "data" / "bin_counts.json"
    f.write_text(json.dumps({"counts": {"4": 14}, "version": 1}))
    os.chmod(f, 0)
    env = dict(os.environ, MOCK_HARDWARE="1")
    env.pop("RIFTBOUND_BIN_LIMITS", None)
    try:
        r = subprocess.run([sys.executable, "main.py", *args], cwd=w, env=env, capture_output=True,
                           text=True, timeout=120, stdin=subprocess.DEVNULL)
    finally:
        os.chmod(f, 0o644)
    assert r.returncode == 78, (r.returncode, r.stdout[-800:], r.stderr[-2000:])
    assert "cannot read" in r.stderr and "sudo chown -R" in r.stderr and "Traceback" not in r.stderr
    assert json.loads(f.read_text())["counts"] == {"4": 14}


# ══ m4: config_txt_line.py clean errors ═══════════════════════════════════════
def test_config_txt_line_missing_file(tmp_path, capsys):
    ct = _load_script("config_txt_line")
    assert ct.main(["gpio=17,27=ip,pu", "--file", str(tmp_path / "nope.txt")]) == 1
    assert "no such file" in capsys.readouterr().err
    assert ct.main(["gpio=17,27=ip,pu", "--file", str(tmp_path)]) == 1
    assert "not a regular file" in capsys.readouterr().err


def test_config_txt_line_non_utf8(tmp_path, capsys):
    ct = _load_script("config_txt_line")
    f = tmp_path / "config.txt"
    f.write_bytes(b"dtparam=audio=on\n\xff\xfe\n")
    assert ct.main(["gpio=17,27=ip,pu", "--file", str(f)]) == 1
    assert "not UTF-8" in capsys.readouterr().err
    assert f.read_bytes() == b"dtparam=audio=on\n\xff\xfe\n"
    assert not (tmp_path / "config.txt.riftbound.bak").exists()


def test_config_txt_line_cli_no_traceback(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "config_txt_line.py"), "gpio=17,27=ip,pu",
                        "--file", str(tmp_path / "missing.txt")], capture_output=True, text=True)
    assert r.returncode == 1 and "Traceback" not in r.stderr and "no such file" in r.stderr
