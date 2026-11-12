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
    from hardware import loadcell
    from api import riftcodex
    monkeypatch.setattr(loadcell, "_CALIBRATION_FILE", tmp_path / "loadcell_calibration.json")
    monkeypatch.setattr(loadcell, "_empty_offset", None)
    monkeypatch.setattr(loadcell, "_mock_fail_reads", 0)
    monkeypatch.setattr(main, "MACHINE_STATE_FILE", tmp_path / "machine_state.json")
    monkeypatch.setattr(main, "WEB_CONFIG_FILE", tmp_path / "web.json")
    monkeypatch.setattr(main, "_marker_armed", False)
    monkeypatch.setattr(main, "_tearing_down", False)
    monkeypatch.setattr(main, "_signals", 0)
    monkeypatch.setattr(main, "_running", True)
    monkeypatch.setattr(main, "_card_at", None)
    monkeypatch.setattr(main, "_control", {"pause": False, "stop": False, "resume": False,
                                           "reload_rules": False})
    monkeypatch.setattr(riftcodex, "CACHE_FILE", tmp_path / "cards.json")
    monkeypatch.setattr(riftcodex, "_card_cache", {})
    monkeypatch.setattr(riftcodex, "_last_fetch", 0)
    yield
