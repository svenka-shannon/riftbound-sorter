"""Shared test setup: MOCK hardware, and every file the code persists redirected
into a per-test tmp dir so tests never touch config/ or data/ in the repo."""

import os
import sys
from pathlib import Path

os.environ["MOCK_HARDWARE"] = "1"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest


@pytest.fixture(autouse=True)
def _isolated_files(monkeypatch, tmp_path):
    import main
    from hardware import elevator, instance, loadcell, servos, shuttle
    from api import riftcodex
    # hardware tools' lock / marker (hardware/instance.py) → tmp
    monkeypatch.setattr(instance, "DATA_DIR", tmp_path)
    # servo_calibration.json → tmp; the arm angles it sets are restored after the test
    monkeypatch.setattr(servos, "_CALIBRATION_FILE", tmp_path / "servo_calibration.json")
    for name in ("ARM_PICK", "ARM_DROP", "ARM_PARK", "PICKUP_ARM_UP", "PICKUP_ARM_DOWN"):
        monkeypatch.setattr(servos, name, getattr(servos, name))
    monkeypatch.setattr(servos, "_arm_released", False)
    monkeypatch.setattr(shuttle, "_released", set())
    # shuttle_calibration.json → tmp; every dict _load_calibration() mutates is a per-test copy
    monkeypatch.setattr(shuttle, "_CALIBRATION_FILE", tmp_path / "shuttle_calibration.json")
    for name in ("TILT_ANGLES", "SHUTTLE_ANGLES", "TIMING", "SHUTTLE_ACTUATION_RANGE", "SHUTTLE_INVERT"):
        monkeypatch.setattr(shuttle, name, dict(getattr(shuttle, name)))
    monkeypatch.setattr(loadcell, "_CALIBRATION_FILE", tmp_path / "loadcell_calibration.json")
    monkeypatch.setattr(loadcell, "_empty_offset", None)
    monkeypatch.setattr(loadcell, "_cal_empty_offset", None)
    monkeypatch.setattr(loadcell, "_offset", 0)
    monkeypatch.setattr(loadcell, "_offset_valid", False)
    monkeypatch.setattr(loadcell, "_tare_anchored", False)
    monkeypatch.setattr(loadcell, "SCALE_FACTOR", loadcell.SCALE_FACTOR)
    monkeypatch.setattr(loadcell, "_mock_fail_reads", 0)
    monkeypatch.setattr(loadcell, "_mock_load_g", 0.0)
    monkeypatch.setattr(elevator, "_mock_wire_broken", {"top": False, "bottom": False})
    monkeypatch.setattr(elevator, "_raised_since_home", False)
    monkeypatch.setattr(main, "MACHINE_STATE_FILE", tmp_path / "machine_state.json")
    monkeypatch.setattr(main, "WEB_CONFIG_FILE", tmp_path / "web.json")
    monkeypatch.setattr(main, "_marker_armed", False)
    monkeypatch.setattr(main, "_tearing_down", False)
    monkeypatch.setattr(main, "_signals", 0)
    monkeypatch.setattr(main, "_running", True)
    monkeypatch.setattr(main, "_card_at", None)
    monkeypatch.setattr(main, "_cup_hold_since", None)
    monkeypatch.setattr(main, "_shutdown_raises", True)
    monkeypatch.setattr(main, "_control", {"pause": False, "stop": False, "resume": False,
                                           "reload_rules": False})
    monkeypatch.setattr(main, "INSTANCE_LOCK_FILE", tmp_path / "sorter.lock")
    monkeypatch.setattr(main, "_defer_depth", 0)
    monkeypatch.setattr(main, "_shutdown_pending", False)
    monkeypatch.setattr(main, "_active_depth", 0)
    main._resume_event.clear()
    monkeypatch.setitem(main._status, "state", "starting")
    monkeypatch.setitem(main._status, "paused_bin", None)
    monkeypatch.setattr(riftcodex, "CACHE_FILE", tmp_path / "cards.json")
    monkeypatch.setattr(riftcodex, "_card_cache", {})
    monkeypatch.setattr(riftcodex, "_last_fetch", 0)
    yield
