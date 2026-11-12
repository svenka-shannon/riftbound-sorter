#!/usr/bin/env python3
"""
Riftbound Card Sorter — Main Loop
==================================
Run on Raspberry Pi Zero 2W.

Usage:
  python main.py                 # normal run
  python main.py --calibrate     # calibrate the cradle load cell (5.000 g US nickel by default)
  python main.py --calibrate --mass 10.0   # ... with another known reference mass
  python main.py --build-db      # rebuild card hash DB
  python main.py --dry-run       # identify cards, send every card to the reject bin
  python main.py --web-only      # start web UI without sorting
  python main.py --empty-bin N   # reset bin N's card count after emptying it
  python main.py --empty-all     # reset every bin count
  python main.py --confirm-clear # operator: machine checked and clear after an unclean stop
  python main.py --web-token     # print the web UI token (created on first use)

One card (cards are raw and valuable: when in doubt, do the thing that can't
damage a card — reject it, or stop):
  1. elevator.raise_to_pick()          False → hopper empty / stuck: STOP
  2. arm_to_pick, pump_on, seal, arm_to_drop (card flat 3 mm above the belt at
     X −95), vacuum.release() (pump off + vent valve pulse), lift the arm
     SLOWLY ~10 mm, arm_park
  3. belt runs until card_detect sees the card centred under the lens (X +5),
     then brakes. Never seen → STOP ("card may still be on the cup"); lost → STOP
  4. capture + identify (failure / ambiguous → reject, normal flow)
  5. belt runs for the exit distance at the MEASURED belt speed (+ margin):
     card leaves the belt end (X 85) onto the cradle (home, level). The card
     must weigh in fully on the LEVEL cradle before it is tipped to HOLD;
     a card whose tail is still on the belt / in the hood → STOP, not tipped
  6. shuttle.hold, settle, weigh: double / unknown / unidentified → reject (bin 9)
  7. target bin full → PAUSE with the card held on the cradle in hold until
     the bin is emptied (web UI or --empty-bin), then route it
  8. shuttle.route(bin) tips + verifies the cradle emptied; ShuttleError → STOP
  9. count the card into the bin; hold, check empty, tare, level for the next card

Stopping (audit B4):
  * SIGINT / SIGTERM / SIGHUP (or the web UI's Stop) only set a flag: the card
    in progress is finished, then the loop ends at a card boundary. A SECOND
    signal raises Shutdown immediately; the cycle's handler makes the hardware
    safe without ever moving the carriage. A card on the cup is either left
    on the stack or carried to the belt, never dropped mid-arc: while it is
    being carried (_make_safe) a second signal is DEFERRED until the card is
    down, and an error during the carry keeps the pump ON (card held).
  * All teardown happens once, in main()'s finally (teardown()). The shuttle
    is NOT homed: it stays where it is.
  * Teardown pose (decided, audit minor + M7): teardown parks the arm and
    brings a tipped cradle back to HOLD, then switches every servo channel
    OFF and sleeps the PCA9685 — the servos are LIMP where they stand. The
    clean-stop record (rest_pose "home_level") therefore means "de-energized
    at rest, may have sagged a little"; the next start re-asserts that pose
    with one write per channel (a small snap back, never a sweep) and ramps
    from there. Any other stop records no rest pose: nothing is assumed.
  * data/machine_state.json records whether the stop was clean (no card in
    the machine, arm parked, shuttle home + level, cradle empty). After an
    unclean stop NOTHING on PCA9685 ch0/ch1/ch2 is commanded — no arm park,
    no shuttle homing — until the operator confirms the machine is clear
    (web UI "Machine clear" or --confirm-clear) (audit M7).
  * At EVERY start-up — confirmed or not — the cradle's raw load is compared
    with the stored empty-cradle reference BEFORE taring: a card left on it
    stops the start-up ("card on cradle — remove it") instead of being tared
    away (audit M1). Which tares may update that reference: hardware/loadcell.py.
  * systemd: the unit has WatchdogSec; the main loop pings it (sd_notify
    WATCHDOG=1) via _beat(). A hung main loop is killed (SIGABRT) and the
    unit's ExecStopPost (scripts/safe_outputs.py) makes the outputs safe.

Operator controls / web state machine (audit M2): can_pause() / can_resume() /
can_stop() / can_confirm_clear() / can_empty_bin() below gate every mutating web
endpoint and CLI command; prepare_machine() sets "starting" before anything moves.

Hardware:
  - Pi Zero 2W + Pi Camera Module 3 (mounted rotated 180°)
  - PCA9685 (I2C 0x40): ch0 pick arm (servos.py), ch1 tilt + ch2 shuttle (shuttle.py)
  - HX711 load cell under the cradle (GPIO 5/6)
  - 2-ch 5V relay: 12V vacuum pump (GPIO 17), 12V NC vent valve (GPIO 27)
  - L9110S belt motors (GPIO 23-26), 28BYJ-48 hopper elevator (GPIO 16-21, 12, 13)
"""

import os
import sys
import time
import json
import argparse
import hashlib
import hmac
import secrets
import signal
import tempfile
import threading
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import datetime

try:
    import fcntl
except ImportError:          # non-POSIX dev machine
    fcntl = None

# `python main.py` runs this file as __main__; web/app.py does `import main`.
# Without this alias that import would load a SECOND copy of this module with
# its own (never updated) _status, so the web UI would show stale data.
if __name__ == "__main__":
    sys.modules.setdefault("main", sys.modules[__name__])

MOCK_HARDWARE = os.environ.get("MOCK_HARDWARE", "0") == "1"

# Validate config/machine.json BEFORE any hardware module applies it (audit M6):
# a bad file stops the program with a list of the bad keys, it never falls back.
try:
    from hardware import machine_config     # (the package import applies the config too)
    machine_config.load()
except Exception as _exc:
    _mc = sys.modules.get("hardware.machine_config")
    if __name__ == "__main__" and _mc is not None and isinstance(_exc, _mc.MachineConfigError):
        print(f"[config] ERROR: {_exc}", file=sys.stderr)
        sys.exit(_mc.EX_CONFIG)
    raise

from hardware import servos, vacuum, loadcell, camera, conveyor, elevator, shuttle, card_detect
from hardware.shuttle import ShuttleError
from hardware.loadcell import LoadCellError
from vision.identify import build_hash_db, identify
import vision.identify as identify_mod
from api import riftcodex, inventory
from sorter.rules_engine import RulesEngine

ROOT = Path(__file__).resolve().parent

# ── Config ────────────────────────────────────────────────────────────────────
RULES_FILE         = str(ROOT / "config" / "rules.json")
BIN_COUNTS_FILE    = ROOT / "data" / "bin_counts.json"       # runtime counts
BIN_LIMITS_FILE    = ROOT / "config" / "bin_limits.json"     # optional {"0": 40, ..., "9": 35}
MACHINE_STATE_FILE = ROOT / "data" / "machine_state.json"    # clean-shutdown marker
WEB_CONFIG_FILE    = ROOT / "config" / "web.json"            # {"token": ...} (generated)
INSTANCE_LOCK_FILE = ROOT / "data" / "sorter.lock"           # held while a sorter process runs
if MOCK_HARDWARE:   # a mock run must not touch the real machine's clean-shutdown record
    MACHINE_STATE_FILE = MACHINE_STATE_FILE.with_name("machine_state.mock.json")
    INSTANCE_LOCK_FILE = INSTANCE_LOCK_FILE.with_name("sorter.mock.lock")

REJECT_BIN = shuttle.REJECT_BIN                          # 9 (physical reject bin)
SORT_BINS  = tuple(range(8))
# Cards per slot before the machine pauses ("bin N full — empty it").
# Conservative defaults from the slide simulation (cad/shuttle_check.py slide):
#   upper floor 4-7: IN up to a 4 mm pile at μ 0.35, SHORT at 8 mm, JAM at 4 mm
#     with μ 0.45 → 12 cards (≈ 4 mm loose pile).
#   lower floor 0-3: 50 cards (16.5 mm) left < 1 mm margin to the 18 mm case →
#     40 cards (≈ 13 mm).
#   reject (cad/reject_bin.scad): floor Z 6.5, cards slide in over the lane lip at
#   Z 23.9 → 17.4 mm of pile before a card can't clear the lip; 35 × 0.33 mm =
#   11.6 mm, leaving room for a loose, uneven pile.
# Raise them per bin in config/bin_limits.json once tested on the machine.
DEFAULT_BIN_LIMITS = {0: 40, 1: 40, 2: 40, 3: 40, 4: 12, 5: 12, 6: 12, 7: 12, REJECT_BIN: 35}

CARD_WEIGHT_G      = 1.75   # one raw Riftbound card (nominal; NOT used for calibration)
CALIBRATION_MASS_G = 5.000  # load-cell calibration reference: a US nickel (5.000 g)

# Pick & place (step 2)
SEAL_S         = 0.3    # pump on, cup on the card → vacuum seals before lifting
DROP_SETTLE_S  = 0.1    # arm at the drop pose: let it stop swaying before releasing
ARM_LIFT_DEG   = 10.0   # first lift after release: ≈ 10 mm of cup travel near the drop pose
ARM_LIFT_S     = 0.6    # ... done slowly, so a card still stuck to the cup peels off
# Belt exit (step 5): centred card trailing edge X 5−44 = −39 must pass the belt
# end X 85 (124 mm) plus ~20 mm to land on the cradle = EXIT_TRAVEL_MM, run at the
# belt speed measured during centring (never assumed faster than nominal).
EXIT_TRAVEL_MM   = 144.0
EXIT_TIME_MARGIN = 1.25  # × the computed time
EXIT_MIN_S       = 0.6
EXIT_MAX_S       = 3.0   # cap (a belt slower than ~60 mm/s is a fault anyway)
EXIT_EXTRA_S     = 0.4   # one extra belt burst if the card is only partly on the cradle
# Cradle (steps 5, 6 and 9)
WEIGH_SETTLE_S = 0.2    # pose reached → card at rest before weighing
TARE_SETTLE_S  = 0.3    # empty cradle in hold → before checking / taring
# Pause for a full bin (step 7) / operator waits
BIN_POLL_S       = 0.5
RESUME_DELAY_S   = 2.0  # bin reset → hands clear of the tray before the shuttle moves
OPERATOR_POLL_S  = 0.5
CARD_DATA_RETRY_S = 60.0
SECURE_CARRY_TRIES = 3   # attempts to carry a card on the cup to the drop pose
WATCHDOG_PING_S  = 1.0   # at most one sd_notify WATCHDOG=1 per this many seconds
WEB_PORT = int(os.environ.get("RIFTBOUND_WEB_PORT", "5000"))

machine_config.apply(sys.modules[__name__], "sort", (
    "EXIT_TRAVEL_MM", "EXIT_TIME_MARGIN", "EXIT_MIN_S", "EXIT_MAX_S", "EXIT_EXTRA_S",
    "SEAL_S", "DROP_SETTLE_S", "ARM_LIFT_DEG", "ARM_LIFT_S", "WEIGH_SETTLE_S", "TARE_SETTLE_S",
    "RESUME_DELAY_S", "CALIBRATION_MASS_G"))

_running        = True     # process alive; False after a shutdown signal
_signals        = 0
_tearing_down   = False
_hw_initialised = False
_marker_armed   = False    # mark_running() was called: teardown() writes the marker
_control        = {"pause": False, "stop": False, "resume": False, "reload_rules": False}
_resume_event   = threading.Event()   # a Resume click not yet acted on (never cleared on entry)
_defer_depth    = 0        # >0: inside a "card on the cup" critical section
_shutdown_pending = False  # a second signal arrived inside the critical section
_active_depth   = 0        # >0: prepare_machine() / run_sorter() in progress
_card_at        = None     # where the card in progress is: None | "cup" | "belt" | "cradle"
_engine         = None
_stats          = {"total": 0, "sorted": 0, "rejects": 0, "errors": 0, "jams": 0,
                   "double_picks": 0, "weight_unknown": 0, "unknowns": 0, "total_today": 0}
_status         = {"state": "starting", "message": "", "hopper_empty": False, "jam": False,
                   "paused_bin": None, "cards_remaining_estimate": 0,
                   "cards_per_minute": 0.0, "total_today": 0,
                   "last_card": None, "last_weight_g": None, "last_offset_mm": None,
                   "bin_counts": {}, "bin_limits": {}, "pause_requested": False,
                   "stop_requested": False, "card_at": None}
_session_start  = time.time()
_recent_scans   = deque(maxlen=60)   # timestamps of the last 60 cards routed
_today_midnight = 0.0                # Unix timestamp of today's midnight; set in main()

# States in which nothing moves and an operator may reach into the bins.
# ("starting" and "running" are NOT idle: prepare_machine homes the elevator,
#  tilts the cradle and may home the shuttle.)
IDLE_STATES = ("paused", "stopped", "jam", "hopper_empty", "error", "idle", "needs_confirm")
# "Machine clear" (confirm) — only once the machine has halted and no run is in
# progress. Never while paused (a card may be held on the cradle mid-run) or
# starting (the start-up checks are running).
CONFIRM_STATES = ("needs_confirm", "jam", "error", "stopped")


# ── Outcomes ──────────────────────────────────────────────────────────────────
class StopMachine(Exception):
    """Stop the loop: the operator has to look at the machine."""
    state = "stopped"
    hold_cradle = True      # _make_safe may tip the cradle to HOLD


class Jam(StopMachine):
    state = "jam"


class CardNotOnCradle(Jam):
    """The card's tail is still on the belt / in the hood: do NOT tip to hold."""
    hold_cradle = False


class HopperEmpty(StopMachine):
    state = "hopper_empty"


class LoadCellFault(StopMachine):
    state = "error"


class StopRequested(StopMachine):
    state = "stopped"


class NeedsConfirm(StopMachine):
    """Start-up refused until the operator confirms the machine is clear."""
    state = "needs_confirm"


class ElevatorFault(StopMachine):
    """A hopper switch reading only a wiring fault explains (audit M8)."""
    state = "error"


class CameraFault(StopMachine):
    """The camera stopped delivering frames (audit M5); belt braked."""
    state = "error"


class CupNotSecured(RuntimeError):
    """The arm could not carry the card on the cup to the drop pose; the pump
    stays ON so the card is held instead of dropped mid-arc."""


class Shutdown(BaseException):
    """Raised by the signal handler on the SECOND stop signal: stop now.
    BaseException, so `except Exception` never swallows it."""


@dataclass
class PendingCard:
    """A card weighed on the cradle and assigned a bin, not yet routed."""
    bin_num: int
    card_id: str | None
    card_name: str
    confidence: float
    weight_g: float
    weight_class: str
    reason: str          # why it goes to this bin ("rule", "double weight", ...)
    record: bool         # log to inventory after routing (never in a dry run)
    record_bin: int      # bin recorded in inventory


class BinFull(Exception):
    """Pause: the target bin is full; the card waits on the cradle in hold."""

    def __init__(self, pending: PendingCard):
        super().__init__(f"bin {pending.bin_num} full — empty it")
        self.pending = pending


# ── Bin capacity tracking ─────────────────────────────────────────────────────
class BinCounts:
    """Cards in each bin, persisted to BIN_COUNTS_FILE. Thread-safe (the web UI
    resets bins) and process-safe (`main.py --empty-bin N` while the sorter
    runs): every read-modify-write holds an flock on a sidecar lock file, the
    file is written via a UNIQUE temp file + os.replace, and a change is
    detected by a content hash (+ a version counter), not by mtime alone."""

    def __init__(self, counts_file: Path, limits_file: Path, default_limits: dict):
        self._lock = threading.RLock()
        self.counts_file = Path(counts_file)
        self.limits_file = Path(limits_file)
        self.limits = dict(default_limits)
        if self.limits_file.exists():
            try:
                for k, v in json.loads(self.limits_file.read_text()).items():
                    if str(k).isdigit() and int(k) in self.limits:
                        self.limits[int(k)] = int(v)
            except Exception as exc:
                print(f"[bins] Warning: could not read {self.limits_file}: {exc}")
        self.counts = {b: 0 for b in self.limits}
        self.version = 0
        self._hash = None
        self._refresh()

    @contextmanager
    def _file_lock(self):
        if fcntl is None:
            yield
            return
        self.counts_file.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.counts_file.with_name(self.counts_file.name + ".lock")
        with open(lock_path, "a+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def _refresh(self):
        try:
            raw = self.counts_file.read_bytes()
        except FileNotFoundError:
            return
        except OSError as exc:
            print(f"[bins] Warning: could not read {self.counts_file}: {exc}")
            return
        digest = hashlib.sha256(raw).hexdigest()
        if digest == self._hash:
            return
        try:
            data = json.loads(raw)
            for k, v in data.get("counts", {}).items():
                if str(k).isdigit() and int(k) in self.counts:
                    self.counts[int(k)] = int(v)
            self.version = int(data.get("version", 0))
            self._hash = digest
        except Exception as exc:
            print(f"[bins] Warning: could not parse {self.counts_file}: {exc}")

    def _save(self):
        self.counts_file.parent.mkdir(parents=True, exist_ok=True)
        self.version += 1
        payload = json.dumps({"counts": {str(b): n for b, n in sorted(self.counts.items())},
                              "version": self.version, "updated": time.time()},
                             indent=2).encode()
        fd, tmp = tempfile.mkstemp(prefix=f".{self.counts_file.name}.", suffix=".tmp",
                                   dir=self.counts_file.parent)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
            os.replace(tmp, self.counts_file)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        self._hash = hashlib.sha256(payload).hexdigest()

    def _check(self, bin_num: int):
        if bin_num not in self.limits:
            raise ValueError(f"unknown bin {bin_num}; valid: {sorted(self.limits)}")

    def count(self, bin_num: int) -> int:
        with self._lock:
            self._refresh()
            return self.counts[bin_num]

    def is_full(self, bin_num: int) -> bool:
        with self._lock:
            self._check(bin_num)
            self._refresh()
            return self.counts[bin_num] >= self.limits[bin_num]

    def increment(self, bin_num: int):
        with self._lock, self._file_lock():
            self._check(bin_num)
            self._refresh()
            self.counts[bin_num] += 1
            self._save()

    def empty(self, bin_num: int):
        with self._lock, self._file_lock():
            self._check(bin_num)
            self._refresh()
            self.counts[bin_num] = 0
            self._save()

    def empty_all(self):
        with self._lock, self._file_lock():
            self._refresh()
            for b in self.counts:
                self.counts[b] = 0
            self._save()

    def snapshot(self) -> dict:
        with self._lock:
            self._refresh()
            return {"counts": {str(b): n for b, n in sorted(self.counts.items())},
                    "limits": {str(b): n for b, n in sorted(self.limits.items())}}


_bins = BinCounts(BIN_COUNTS_FILE, BIN_LIMITS_FILE, DEFAULT_BIN_LIMITS)


def _publish_bins():
    snap = _bins.snapshot()
    _status["bin_counts"] = snap["counts"]
    _status["bin_limits"] = snap["limits"]


def can_empty_bin(bin_num: int | None = None) -> tuple[bool, str]:
    """Is it safe for the operator to reach into the bins right now?
    A single bin: if it is the bin the machine is paused on, or the machine is
    in an idle state. All bins (bin_num None): only in an idle state. Never
    while "starting" or "running"."""
    state = _status.get("state")
    if state in IDLE_STATES:
        return True, ""
    if bin_num is not None and _status.get("paused_bin") == bin_num:
        return True, ""
    what = f"bin {bin_num}" if bin_num is not None else "all bins"
    return False, (f"machine is {state}: pause or stop it before emptying {what} "
                   "(the shuttle may be moving)")


def run_in_progress() -> bool:
    """prepare_machine() or run_sorter() is executing (the machine may move)."""
    return _active_depth > 0


@contextmanager
def _machine_active():
    global _active_depth
    _active_depth += 1
    try:
        yield
    finally:
        _active_depth -= 1


# Operator controls allowed per state (audit M2). Every mutating web endpoint
# and CLI command goes through these.
def can_pause() -> tuple[bool, str]:
    state = _status.get("state")
    if state in ("running", "starting", "paused"):
        return True, ""
    return False, f"machine is {state}: nothing to pause"


def can_resume() -> tuple[bool, str]:
    state = _status.get("state")
    if state in ("paused", "stopped", "hopper_empty"):
        return True, ""
    if state in ("running", "starting") and (_control["pause"] or _control["stop"]):
        return True, ""                       # cancels a pending pause / stop
    if state in ("needs_confirm", "jam", "error"):
        return False, f"machine is {state}: check it and press 'Machine clear' instead"
    return False, f"machine is {state}: nothing to resume"


def can_stop() -> tuple[bool, str]:
    state = _status.get("state")
    if state in ("running", "starting", "paused"):
        return True, ""
    return False, f"machine is {state}: already stopped"


def can_confirm_clear() -> tuple[bool, str]:
    state = _status.get("state")
    if state not in CONFIRM_STATES:
        return False, (f"machine is {state}: 'Machine clear' is only accepted once it has "
                       f"halted ({', '.join(CONFIRM_STATES)}) — stop it first")
    if run_in_progress():
        return False, "a run is still in progress — wait for it to halt"
    return True, ""


def empty_bin(bin_num: int):
    """Reset a bin's count after the operator emptied it (web UI / CLI)."""
    _bins.empty(bin_num)
    _publish_bins()
    print(f"[bins] bin {bin_num} emptied")


def empty_all_bins():
    _bins.empty_all()
    _publish_bins()
    print("[bins] all bins emptied")


# ── Operator controls (web UI) ────────────────────────────────────────────────
def request_pause():
    """Pause at the next card boundary (the card in progress is finished)."""
    _control["pause"] = True
    _status["pause_requested"] = True


def request_resume():
    """Resume after a pause / operator stop / empty hopper. The click is kept
    (an Event, not a flag cleared on entry) until a waiting loop acts on it,
    so a click that lands while the machine is still halting is not lost."""
    _control["pause"] = False
    _control["stop"] = False
    _control["resume"] = True
    _status["pause_requested"] = False
    _status["stop_requested"] = False
    _resume_event.set()


def request_stop():
    """Stop sorting at the next card boundary; the process and web UI stay up."""
    _control["stop"] = True
    _status["stop_requested"] = True


def request_rules_reload():
    """Reload config/rules.json before the next card."""
    _control["reload_rules"] = True


def _stop_wanted() -> bool:
    _beat()                      # called from every long loop (elevator steps, waits)
    return not _running or _control["stop"]


# ── systemd watchdog (audit M5) ───────────────────────────────────────────────
_last_ping = 0.0


def _sd_notify(message: str) -> bool:
    """sd_notify(3) without a dependency: one datagram to $NOTIFY_SOCKET.
    No-op (False) when not running under systemd."""
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return False
    import socket
    if addr.startswith("@"):
        addr = "\0" + addr[1:]            # abstract namespace
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(addr)
            sock.sendall(message.encode())
        return True
    except OSError:
        return False


def _beat():
    """Main loop is alive: ping the systemd watchdog (rate-limited). Only the
    main thread pings, so a hung main loop really does stop the pings."""
    global _last_ping
    if threading.current_thread() is not threading.main_thread():
        return
    now = time.monotonic()
    if now - _last_ping >= WATCHDOG_PING_S:
        _last_ping = now
        _sd_notify("WATCHDOG=1")


# ── Machine state marker (clean shutdown) ─────────────────────────────────────
def read_machine_state() -> dict:
    try:
        data = json.loads(MACHINE_STATE_FILE.read_text())
        if isinstance(data, dict):
            return data
    except FileNotFoundError:
        return {"clean": False, "confirmed": False,
                "reason": "no record of a previous clean shutdown (first start?)"}
    except Exception as exc:
        return {"clean": False, "confirmed": False, "reason": f"machine state file unreadable: {exc}"}
    return {"clean": False, "confirmed": False, "reason": "machine state file invalid"}


def _write_machine_state(**fields):
    data = {"clean": False, "confirmed": False, "reason": "", "ts": time.time(), **fields}
    MACHINE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{MACHINE_STATE_FILE.name}.", suffix=".tmp",
                               dir=MACHINE_STATE_FILE.parent)
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(data, indent=2))
    os.replace(tmp, MACHINE_STATE_FILE)
    _status["machine_state"] = data


def confirm_clear(source: str = "cli"):
    """Operator: the arm, belt and cradle are clear (any card removed). Lets the
    sorter start after an unclean stop / jam. Callers check can_confirm_clear()
    first (the web endpoint; the CLI goes through the web endpoint whenever a
    sorter process is running). The start-up cradle check still compares the
    cradle with the stored empty reference afterwards (audit M1)."""
    st = read_machine_state()
    _write_machine_state(clean=bool(st.get("clean")), confirmed=True,
                         reason=st.get("reason", ""), confirmed_by=source,
                         rest_pose=st.get("rest_pose"))
    print(f"[main] machine confirmed clear ({source})")


def mark_running():
    """From here on, a crash / power loss / kill leaves an unclean marker."""
    global _marker_armed
    _marker_armed = True
    _write_machine_state(clean=False, confirmed=False,
                         reason="the sorter was running and did not shut down cleanly "
                                "(crash, power loss or kill)")


# ── Web token ─────────────────────────────────────────────────────────────────
def load_or_create_web_token() -> str:
    """Shared secret for the web UI's mutating endpoints, from config/web.json.
    Generated on first use. Never printed here (it would end up in the
    journal): only `main.py --web-token` prints it."""
    try:
        tok = json.loads(WEB_CONFIG_FILE.read_text()).get("token")
        if tok:
            return str(tok)
    except FileNotFoundError:
        pass
    except Exception as exc:
        print(f"[web] Warning: could not read {WEB_CONFIG_FILE}: {exc} — generating a new token")
    tok = secrets.token_urlsafe(12)
    WEB_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    WEB_CONFIG_FILE.write_text(json.dumps({"token": tok}, indent=2))
    try:
        os.chmod(WEB_CONFIG_FILE, 0o600)
    except OSError:
        pass
    print(f"[web] Generated a new web UI token (saved in {WEB_CONFIG_FILE}); "
          "show it with `main.py --web-token`")
    return tok


def check_web_token(given: str | None, expected: str) -> bool:
    return bool(given) and hmac.compare_digest(str(given), str(expected))


# ── Helpers ───────────────────────────────────────────────────────────────────
def _midnight_today() -> float:
    """Return Unix timestamp of today's midnight (local time)."""
    today = datetime.date.today()
    return time.mktime(datetime.datetime(today.year, today.month, today.day).timetuple())


def _get_cards_per_minute() -> float:
    """Rolling CPM calculated over the span of the last ≤60 scan timestamps."""
    n = len(_recent_scans)
    if n == 0:
        return 0.0
    now = time.time()
    time_span = now - _recent_scans[0]
    if time_span <= 0:
        return 0.0
    return round(n / (time_span / 60.0), 1)


def _set_state(state: str, message: str = ""):
    _status["state"] = state
    _status["message"] = message
    _status["jam"] = state == "jam"
    _status["hopper_empty"] = state == "hopper_empty"
    if state != "paused":
        _status["paused_bin"] = None
    if message:
        print(f"[main] {state.upper()}: {message}")


def _set_card_at(where):
    global _card_at
    _card_at = where
    _status["card_at"] = where


def _try(fn, *args):
    """Call a safety action; never let one failure skip the others."""
    try:
        fn(*args)
    except Exception as exc:
        print(f"[main] safety action {getattr(fn, '__name__', fn)} failed: {exc!r}")


@contextmanager
def _no_shutdown():
    """Critical section: a second stop signal inside it does not raise; the
    Shutdown is raised when the (outermost) section ends — also if the body
    raised, in which case Shutdown replaces that exception."""
    global _defer_depth, _shutdown_pending
    _defer_depth += 1
    try:
        yield
    finally:
        _defer_depth -= 1
        if _defer_depth == 0 and _shutdown_pending:
            _shutdown_pending = False
            raise Shutdown("second stop signal (deferred until the machine was made safe)")


def _secure_cup():
    """A card on the cup is never dropped mid-arc:
      cup still at the pick pose → release there, the card stays on the stack;
      anywhere else             → carry it to the drop pose (pump still on),
                                  then release it onto the (stopped) belt.
    The carry runs inside _no_shutdown() (a second signal waits until the card
    is down) and is retried SECURE_CARRY_TRIES times on an error (e.g. a
    transient PCA9685 I2C error). If the arm still cannot get there the pump
    is left ON — card held — and CupNotSecured is raised."""
    if _card_at != "cup":
        vacuum.pump_off()
        return
    a = servos.arm_angle()
    if a is not None and abs(a - servos.ARM_PICK) <= 2.0:
        try:
            vacuum.release()
        finally:
            _set_card_at(None)
        print("[main] card released back onto the hopper stack")
        return
    with _no_shutdown():
        last = None
        for attempt in range(1, SECURE_CARRY_TRIES + 1):
            try:
                servos.move_arm_smooth(servos.ARM_DROP)
                time.sleep(DROP_SETTLE_S)
                last = None
                break
            except Exception as exc:
                last = exc
                print(f"[main] carrying the card to the drop pose failed "
                      f"(attempt {attempt}/{SECURE_CARRY_TRIES}): {exc!r}")
        if last is not None:
            raise CupNotSecured(f"card held on the cup at {servos.arm_angle()}° — the arm could not "
                                "reach the drop pose; pump left ON so the card is not dropped") from last
        try:
            vacuum.release()
        finally:
            _set_card_at("belt")
    print("[main] card carried to the drop pose and released onto the belt")


def _make_safe(hold_cradle: bool = True):
    """Card off the cup safely, pump off, belt stopped, arm parked; the cradle in
    hold (hold_cradle) or only brought back from an unknown / tipped pose.
    Each step is independent. Never moves the carriage, and never commands a
    servo whose position is unknown (audit M7: no blind jumps). The pump stays
    ON only while a card is still held on the cup (CupNotSecured). A second
    stop signal during all this is deferred to the end."""
    with _no_shutdown():
        _try(_secure_cup)
        if _card_at != "cup":
            _try(vacuum.pump_off)
        _try(conveyor.stop)
        if servos.arm_angle() is not None:
            _try(servos.arm_park)
        _try(shuttle.hold_if_known if hold_cradle else shuttle.make_safe)


def _mock_cradle_receives_card():
    """MOCK only: the card that just left the belt lands on the simulated cradle."""
    if MOCK_HARDWARE:
        loadcell.mock_set_load(loadcell.MOCK_CARD_G)


def _weigh(what: str = "weighing the card") -> float:
    try:
        return loadcell.read_grams()
    except LoadCellError as exc:
        raise LoadCellFault(f"load cell failed {what}: {exc} — check the HX711 wiring") from exc


def _prepare_cradle(first: bool = False, anchored: bool = False):
    """Empty cradle in HOLD → check it is empty → tare → LEVEL for the next card.

    Runs at the end of every cycle: shuttle.route() just proved the cradle
    emptied by weight drop (back to ≤ WEIGHT_EMPTY_MAX, and not below
    -NEGATIVE_FAULT_G) against the previous tare, so a card can never be tared
    away. That tare is stored as the new empty reference ONLY if the previous
    tare was anchored (loadcell persistence rule). first=True: start-up — the
    caller already checked the cradle; anchored says whether that check was
    against the stored reference.
    """
    shuttle.hold()
    time.sleep(TARE_SETTLE_S)
    if first:
        persist = False
    else:
        anchored = loadcell.tare_anchored()
        persist = anchored
        w = _weigh("checking the cradle is empty")
        if not loadcell.is_empty(w):
            raise Jam(f"cradle not empty before tare ({w:.2f} g) — remove the card")
    try:
        loadcell.tare(anchored=anchored, persist=persist)
    except LoadCellError as exc:
        raise LoadCellFault(f"load cell tare failed: {exc}") from exc
    shuttle.level()


def _startup_cradle_check(confirmed: bool):
    """Audit M1: before the first tare, ALWAYS compare the raw load with the
    stored empty-cradle reference — also after the operator confirmed the
    machine clear (a confirmation is not a measurement).
      above the reference by > STARTUP_EMPTY_MAX_G → NeedsConfirm (card on it)
      below it by more                             → LoadCellFault
      no reference stored: unconfirmed → NeedsConfirm; confirmed → tare, but
      that zero is NOT anchored (nothing is persisted until --calibrate)."""
    shuttle.hold()
    time.sleep(TARE_SETTLE_S)
    try:
        w = loadcell.grams_vs_empty_reference()
    except LoadCellError as exc:
        raise LoadCellFault(f"load cell failed at start-up: {exc}") from exc
    if w is None:
        if not confirmed:
            raise NeedsConfirm("no stored empty-cradle reference (first start or old calibration) "
                               "— run `main.py --calibrate`, or check the cradle is EMPTY and confirm")
        print("[main] WARNING: no stored empty-cradle reference — taring on the operator's word; "
              "run `main.py --calibrate` so start-up can check the cradle by weight")
        _prepare_cradle(first=True, anchored=False)
        return
    if w > loadcell.STARTUP_EMPTY_MAX_G:
        raise NeedsConfirm(f"card on cradle — remove it ({w:.2f} g above the empty-cradle "
                           "reference), then confirm")
    if w < -loadcell.STARTUP_EMPTY_MAX_G:
        raise LoadCellFault(f"cradle reads {w:.2f} g BELOW the stored empty-cradle reference — "
                            "load cell fault or zero drift; check it, then re-run "
                            "`main.py --calibrate`")
    _prepare_cradle(first=True, anchored=True)


def _ensure_cradle_ready():
    """Cradle must be at home and level before a card leaves the belt."""
    target, tilt, _ = shuttle.state()
    if target != "home" or tilt != "level":
        shuttle.home()


def _identify(jpeg: bytes):
    """(card_id | None, confidence, card dict | None). Never raises: an identify
    or lookup failure just means the card goes to the reject bin."""
    try:
        card_id, confidence = identify(jpeg)
    except Exception as exc:
        print(f"[main] identify failed: {exc!r} — card will be rejected")
        return None, 0.0, None
    card = None
    if card_id is not None:
        try:
            card = riftcodex.get_card(card_id)
        except Exception as exc:
            print(f"[main] card lookup failed for {card_id}: {exc!r} — card will be rejected")
    return card_id, confidence, card


def _decide(engine, card_id, confidence, card, weight_g, weight_class, dry_run) -> PendingCard:
    name = (card.get("name", card_id) if card else card_id) or "unidentified"
    rule_bin = None
    if weight_class != "single":
        reason = f"{weight_class} weight ({weight_g:.2f} g)"
    elif card_id is None:
        reason = f"not identified (confidence {confidence:.2f})"
    elif card is None:
        reason = "no card data"
    else:
        rule_bin = engine.assign_bin(card)
        if rule_bin == engine.reject_bin:
            rule_bin = REJECT_BIN
        if rule_bin not in SORT_BINS and rule_bin != REJECT_BIN:
            reason = f"rule gave invalid bin {rule_bin!r}"
            rule_bin = None
        else:
            reason = "rule"
    target = rule_bin if rule_bin is not None else REJECT_BIN
    record = rule_bin is not None
    if dry_run:
        # Dry run: the card physically goes to the reject bin, so it is NOT
        # recorded in the inventory (which would say it sits in its rule bin).
        target = REJECT_BIN
        record = False
        reason = f"dry run (rule bin {rule_bin})" if rule_bin is not None else f"dry run, {reason}"
    return PendingCard(target, card_id, name, confidence, weight_g, weight_class, reason,
                       record, rule_bin if rule_bin is not None else REJECT_BIN)


def _route_and_record(p: PendingCard):
    """Route the card on the cradle, count it, re-tare. Card must be in HOLD at home."""
    if _bins.is_full(p.bin_num):
        raise BinFull(p)
    try:
        shuttle.route(p.bin_num, read_grams=lambda: loadcell.read_grams())
    except ShuttleError as exc:
        raise Jam(f"card stuck on the cradle routing to bin {p.bin_num}: {exc}") from exc
    except LoadCellError as exc:
        raise LoadCellFault(f"load cell failed checking the cradle emptied at bin {p.bin_num}: "
                            f"{exc} — carriage locked; check the cradle") from exc
    _set_card_at(None)
    _bins.increment(p.bin_num)
    _publish_bins()

    _stats["total"] += 1
    if p.bin_num == REJECT_BIN:
        _stats["rejects"] += 1
    else:
        _stats["sorted"] += 1
    if p.record:
        inventory.record_scan(p.card_id, p.card_name, p.record_bin, p.confidence)
    _status["last_card"] = {"name": p.card_name, "card_id": p.card_id, "bin": p.bin_num,
                            "confidence": round(p.confidence, 3), "reason": p.reason,
                            "weight_g": round(p.weight_g, 2)}

    # Throughput tracking
    global _today_midnight
    now_ts = time.time()
    _recent_scans.append(now_ts)
    if now_ts >= _today_midnight + 86400:
        _today_midnight = _midnight_today()
        _stats["total_today"] = 0
    _stats["total_today"] += 1
    _status["cards_per_minute"] = _get_cards_per_minute()
    _status["total_today"] = _stats["total_today"]

    _prepare_cradle()


def _lift_from_drop():
    """First ~10 mm up from the drop pose, slowly: a card that is still stuck to
    the cup peels off onto the belt instead of being carried away."""
    direction = 1.0 if servos.ARM_PARK >= servos.ARM_DROP else -1.0
    servos.move_arm_smooth(servos.ARM_DROP + direction * ARM_LIFT_DEG, duration_s=ARM_LIFT_S)


def exit_run_s(speed_mm_s) -> float:
    """Belt run time to carry a centred card fully onto the cradle: exit
    distance at the measured speed (never assumed faster than nominal) × margin,
    clamped to [EXIT_MIN_S, EXIT_MAX_S]."""
    v = card_detect.BELT_SPEED_MM_S
    if speed_mm_s and speed_mm_s > 0:
        v = min(v, float(speed_mm_s))
    t = EXIT_TRAVEL_MM / v * EXIT_TIME_MARGIN
    if t > EXIT_MAX_S:
        print(f"[main] warning: belt at {v:.0f} mm/s needs {t:.1f} s to clear the hood; capped at "
              f"{EXIT_MAX_S:.1f} s (the cradle weight check catches a short run)")
    return max(EXIT_MIN_S, min(EXIT_MAX_S, t))


def _exit_to_cradle(speed_mm_s):
    """Step 5: belt the centred card onto the LEVEL cradle and prove it is fully
    on (weight ≥ a single card's minimum) before anything tips it."""
    _ensure_cradle_ready()
    conveyor.run()
    try:
        time.sleep(exit_run_s(speed_mm_s))
    finally:
        conveyor.stop()
    _mock_cradle_receives_card()
    _set_card_at("cradle")
    time.sleep(WEIGH_SETTLE_S)
    w = _weigh("checking the card reached the cradle")
    if loadcell.classify(w) == "empty":
        raise Jam(f"no card on the cradle ({w:.2f} g) — lost between the belt end and the "
                  "cradle (or still on the belt)")
    if w < loadcell.WEIGHT_SINGLE_MIN:
        # partly on the cradle: the tail still rests on the belt end / in the hood
        conveyor.run()
        try:
            time.sleep(EXIT_EXTRA_S)
        finally:
            conveyor.stop()
        time.sleep(WEIGH_SETTLE_S)
        w = _weigh("checking the card reached the cradle")
        if w < loadcell.WEIGHT_SINGLE_MIN:
            raise CardNotOnCradle(f"card not fully on the cradle ({w:.2f} g on it) — its tail may "
                                  "still be on the belt / in the hood exit; cradle NOT tipped. "
                                  "Lift the card off by hand")


# ── One card ──────────────────────────────────────────────────────────────────
def sort_one_card(engine: RulesEngine, dry_run: bool = False) -> int:
    """
    Full pick → centre → scan → cradle → weigh → route cycle for one card.
    Returns the bin the card went to.
    Raises HopperEmpty / Jam / StopRequested (stop), BinFull (pause, card held
    on the cradle), Shutdown, or any unexpected exception (caller stops). On
    ANY exception a card on the cup is secured, the pump is off, the belt
    stopped, the arm parked and the cradle in hold (unless a card hangs off
    the belt end, see CardNotOnCradle).
    """
    # Precondition: cradle empty, tared, level at home; belt clear; arm parked.
    try:
        reference = card_detect.capture_reference()      # empty station, before the drop
    except camera.CameraTimeout as exc:
        raise CameraFault(f"{exc} — no card was picked") from exc

    try:
        raised = elevator.raise_to_pick(abort=_stop_wanted)
    except elevator.ElevatorError as exc:
        raise ElevatorFault(str(exc)) from exc
    if not raised:
        if _stop_wanted():
            raise StopRequested("stop requested")
        raise HopperEmpty("hopper empty (or elevator stuck) — refill and restart")
    _status["cards_remaining_estimate"] = elevator.cards_remaining_estimate()

    try:
        # 2. Pick and place onto the belt
        servos.arm_to_pick()
        vacuum.pump_on()
        _set_card_at("cup")
        time.sleep(SEAL_S)
        servos.arm_to_drop()
        time.sleep(DROP_SETTLE_S)
        vacuum.release()                                 # pump off + vent pulse
        _set_card_at("belt")
        _lift_from_drop()
        servos.arm_park()

        # 3. Belt until the card is centred under the lens
        res = card_detect.centre_card(reference, conveyor.run, conveyor.brake, conveyor.stop)
        _status["last_offset_mm"] = None if res.offset_mm is None else round(res.offset_mm, 2)
        if res.reason == "camera":
            raise CameraFault("camera stopped delivering frames while centring — belt braked. The "
                              "card is on the belt between the arm and the scanner; check the "
                              "camera cable, remove the card, then confirm")
        if res.jam:
            if res.reason == "timeout" and not res.seen:
                raise Jam(f"card never seen at the scanner (timeout after {res.elapsed_s:.2f} s) — "
                          "belt stopped. The card may still be on the cup — check the arm, then "
                          "the belt between the arm and the scanner")
            raise Jam(f"card {res.reason} at the scanner after {res.elapsed_s:.2f} s — belt stopped; "
                      "check the belt between the arm and the scanner")
        if not res.ok:
            print(f"[main] card stopped {res.offset_mm:+.1f} mm off centre — capturing anyway")

        # 4. Capture + identify (failure → reject, normal flow)
        try:
            jpeg = camera.capture_card_jpeg(shift_px=card_detect.crop_shift_px(res.offset_mm or 0.0))
        except camera.CameraTimeout as exc:
            raise CameraFault(f"{exc} — the card is under the scanner; remove it, then "
                              "confirm") from exc
        card_id, confidence, card = _identify(jpeg)

        # 5. Off the belt end onto the LEVEL cradle; verified fully on before tipping
        _exit_to_cradle(res.speed_mm_s)

        # 6. Weigh at rest in hold
        shuttle.hold()
        time.sleep(WEIGH_SETTLE_S)
        weight_g = _weigh()
        weight_class = loadcell.classify(weight_g)
        _status["last_weight_g"] = round(weight_g, 2)
        if weight_class == "empty":
            raise Jam(f"no card on the cradle ({weight_g:.2f} g) — lost between the belt end and "
                      "the cradle")
        if weight_class == "double":
            _stats["double_picks"] += 1
        elif weight_class == "unknown":
            _stats["weight_unknown"] += 1
        elif card_id is None or card is None:
            _stats["unknowns"] += 1

        pending = _decide(engine, card_id, confidence, card, weight_g, weight_class, dry_run)
        print(f"[main] {pending.card_name} ({confidence:.0%}, {weight_g:.2f} g) → bin "
              f"{pending.bin_num} [{engine.describe_bin(pending.bin_num)}; {pending.reason}]")

        # 7-9. Capacity check, route, count, re-tare
        _route_and_record(pending)
        return pending.bin_num
    except BinFull:
        _make_safe()
        raise
    except BaseException as exc:
        _make_safe(hold_cradle=getattr(exc, "hold_cradle", True))
        raise


def _route_pending(p: PendingCard) -> int:
    """Route a card that waited on the cradle for its bin to be emptied."""
    try:
        _route_and_record(p)
        return p.bin_num
    except BaseException as exc:
        _make_safe(hold_cradle=getattr(exc, "hold_cradle", True))
        raise


def _wait_for_bin_space(p: PendingCard) -> bool:
    """Paused: card held on the cradle in HOLD until bin p.bin_num is emptied.
    Nothing moves while waiting (audit M3). Honours stop (returns False) and
    the operator's Pause: if Pause was pressed (before or during the wait),
    emptying the bin is not enough — routing waits for an explicit Resume.
    After the bin is emptied (and no pause) it waits RESUME_DELAY_S for the
    operator's hands to leave the tray, re-checks stop / pause / the bin, and
    only then returns True (the caller routes the card)."""
    shown = None
    while True:
        if _stop_wanted():
            return False
        full = _bins.is_full(p.bin_num)
        paused = _control["pause"]
        if not full and not paused:
            print(f"[main] bin {p.bin_num} emptied — resuming in {RESUME_DELAY_S:.0f} s")
            time.sleep(RESUME_DELAY_S)
            if _stop_wanted():
                return False
            if _control["pause"] or _bins.is_full(p.bin_num):
                continue
            _set_state("running")
            return True
        if paused:
            msg = (f"paused by operator — card held on the cradle for bin {p.bin_num} "
                   + ("(bin still full — empty it, then press Resume)" if full
                      else "(bin emptied) — press Resume to route it"))
        else:
            msg = f"bin {p.bin_num} full — empty it"
        if msg != shown:
            _set_state("paused", msg)
            _status["paused_bin"] = p.bin_num
            if not paused:
                print(f"[main] reset bin {p.bin_num} in the web UI or with `main.py --empty-bin "
                      f"{p.bin_num}` once it is empty. Card held on the cradle.")
            shown = msg
        time.sleep(BIN_POLL_S)


def _wait_while_paused() -> bool:
    """Operator pause at a card boundary. Returns False if stopping."""
    _set_state("paused", "paused by operator — resume in the web UI")
    while _control["pause"] and not _stop_wanted():
        time.sleep(BIN_POLL_S)
    _status["pause_requested"] = False
    if _stop_wanted():
        return False
    _set_state("running")
    return True


def _halt(state: str, message: str) -> str:
    _set_state(state, message)
    return state


def _reload_rules(engine):
    _control["reload_rules"] = False
    if hasattr(engine, "load"):
        try:
            engine.load()
            print("[main] rules reloaded")
        except Exception as exc:
            print(f"[main] rules reload failed ({exc!r}) — keeping the previous rules")


def run_sorter(dry_run: bool = False, engine=None, max_cycles: int | None = None) -> str:
    """Main sorting loop. Returns the final state:
      "stopped"       shutdown / stop requested or max_cycles reached
      "jam"           card stuck / lost / not seen — clear it and confirm
      "hopper_empty"  refill and resume
      "error"         unexpected exception — card position unknown, check and confirm
    A full bin pauses (card held) and resumes once the bin is emptied. Operator
    pause / stop / rules reload are honoured between cards.
    """
    with _machine_active():
        return _run_sorter(dry_run, engine, max_cycles)


def _run_sorter(dry_run, engine, max_cycles) -> str:
    global _engine
    engine = engine or RulesEngine(RULES_FILE)
    _engine = engine
    _publish_bins()
    _set_state("running")
    _resume_event.clear()           # running: any earlier Resume click has been acted on
    print(f"[main] Ready — {'DRY RUN (all cards → reject bin)' if dry_run else 'SORTING'}. Ctrl+C to stop.")

    pending = None
    cycles = 0
    while not _stop_wanted() and (pending is not None or max_cycles is None or cycles < max_cycles):
        _resume_event.clear()       # still running at a card boundary: a click was a no-op
        try:
            if _control["reload_rules"]:
                _reload_rules(engine)
            if pending is not None:
                if not _wait_for_bin_space(pending):
                    break
                p, pending = pending, None
                _route_pending(p)
            else:
                if _control["pause"]:
                    if not _wait_while_paused():
                        break
                    continue
                cycles += 1
                sort_one_card(engine, dry_run=dry_run)
        except BinFull as exc:
            pending = exc.pending
            continue
        except StopRequested:
            break
        except StopMachine as exc:
            if isinstance(exc, Jam):
                _stats["jams"] += 1
            return _halt(exc.state, str(exc))
        except Exception as exc:
            # The card could be anywhere (arm, belt, cradle): never feed another
            # card on top of it. Hardware was made safe by sort_one_card.
            _stats["errors"] += 1
            return _halt("error", f"unexpected error {exc!r} — card position unknown; "
                                  "check the belt and cradle, then confirm")
        time.sleep(0.05)  # small gap between cards
    if not _running:
        _set_state("stopped", "shutdown")
    elif _control["stop"]:
        _set_state("stopped", "stopped by operator — resume in the web UI")
    else:
        _set_state("stopped", "")
    return "stopped"


# ── Start-up / shutdown ───────────────────────────────────────────────────────
def init_hardware(assume_rest: bool = False):
    """Pump off first, then belt, PCA9685 (arm), shuttle (shares the PCA9685),
    load cell, camera, elevator. Nothing MOVES here (audit M7):
      assume_rest=True  (last stop clean, rest pose recorded): the arm's park
                        angle and the shuttle's home + level are re-asserted
                        with one write each (limp servos may have sagged a
                        little), later moves ramp from there.
      assume_rest=False: ch0 / ch1 / ch2 get no command at all; the pose is
                        unknown until prepare_machine() — which only runs
                        after the operator's confirmation — brings it to rest."""
    global _hw_initialised
    _hw_initialised = True
    vacuum.init()
    conveyor.init()
    servos.init(assume_parked=assume_rest)
    shuttle.init(assume_rest=assume_rest)    # never homes
    loadcell.init()            # no tare: _startup_cradle_check() looks for a card first
    camera.init()
    elevator.init()


def _pose_at_rest() -> bool:
    return servos.arm_angle() == servos.ARM_PARK and shuttle.at_rest()


def prepare_machine(confirmed: bool = False):
    """Before sorting: state "starting"; belt stopped, pump off; arm and
    shuttle at rest — if their pose is not known to be the rest pose, that
    needs the operator's confirmation first (NeedsConfirm), then they go
    there directly (audit M7); elevator homed; cradle checked for a left-over
    card against the stored empty reference (always, audit M1), tared, level."""
    with _machine_active():
        _set_state("starting", "checking the machine")
        conveyor.stop()
        vacuum.pump_off()          # confirmed: any card held on the cup has been removed
        if not _pose_at_rest():
            target, tilt, _ = shuttle.state()
            if not confirmed:
                raise NeedsConfirm(f"arm / shuttle pose not known to be at rest (arm "
                                   f"{servos.arm_angle()!r}, shuttle {target!r} / {tilt!r}) — check "
                                   "the arm, belt and cradle are clear, then confirm; they will "
                                   "then move straight to their rest pose")
            servos.arm_park()
            if not shuttle.at_rest():
                shuttle.home()
        print("[main] Homing the hopper elevator...")
        try:
            homed = elevator.home(abort=_stop_wanted)
        except elevator.ElevatorError as exc:
            raise ElevatorFault(str(exc)) from exc
        if not homed:
            if _stop_wanted():
                raise StopRequested("stop requested")
            raise Jam("hopper elevator did not reach its home switch")
        print("[main] Checking the cradle is EMPTY, then taring")
        _startup_cradle_check(confirmed)


def _assess_clean() -> tuple[bool, str]:
    """Is the machine in its clean rest state (nothing to check at restart)?"""
    if _card_at is not None:
        where = {"cup": "on the cup", "belt": "on the belt (drop zone / scanner)",
                 "cradle": "on the cradle"}.get(_card_at, _card_at)
        return False, f"a card was left {where}"
    if _status.get("state") in ("jam", "error"):
        return False, f"stopped on {_status['state']}: {_status.get('message', '')}"
    if vacuum.pump_is_on():
        return False, "vacuum pump still on"
    if servos.arm_angle() != servos.ARM_PARK:
        return False, f"arm not parked ({servos.arm_angle()!r})"
    if shuttle.jammed():
        return False, f"shuttle jammed: {shuttle.jammed()}"
    target, tilt, _ = shuttle.state()
    if (target, tilt) != ("home", "level"):
        return False, f"shuttle not at home + level ({target!r}, {tilt!r})"
    try:
        w = loadcell.read_grams()
    except Exception as exc:
        return False, f"could not verify the cradle is empty: {exc}"
    if not loadcell.is_empty(w):
        return False, f"cradle not empty ({w:.2f} g)"
    return True, "clean shutdown: shuttle home + level, cradle empty, no card in the machine"


def teardown():
    """Bring the machine to rest ONCE (called from main()'s finally): secure a
    card on the cup, pump off, belt stopped, arm parked, tilt back from an
    unknown / tipped pose (never moves the carriage, never homes), record
    whether the stop was clean, then release every driver: servos LIMP in
    place (see "Teardown pose" in the module docstring), pins freed, and
    after the process exits the unit's ExecStopPost drives every output safe."""
    global _tearing_down
    if _tearing_down:
        return
    _tearing_down = True
    print("\n[main] Shutting down...")
    _make_safe(hold_cradle=False)
    if _marker_armed:
        try:
            clean, reason = _assess_clean()
            _write_machine_state(clean=clean, confirmed=False, reason=reason,
                                 rest_pose="home_level" if clean else None)
            print(f"[main] {'clean' if clean else 'UNCLEAN'} stop: {reason}")
        except Exception as exc:
            print(f"[main] could not record the machine state: {exc!r}")
    _try(conveyor.deinit)
    _try(shuttle.deinit)        # ch1/ch2 off; before servos releases the shared PCA9685
    _try(elevator.deinit)
    _try(servos.deinit)         # all channels off, PCA9685 deinit + sleep
    _try(vacuum.deinit)
    _try(loadcell.deinit)
    _try(camera.deinit)


def _on_signal(sig=None, frame=None):
    """SIGINT / SIGTERM / SIGHUP. Only sets flags (first signal: finish the
    current card, then stop) or raises Shutdown (second signal: stop now —
    deferred while a card on the cup is being carried, see _no_shutdown()).
    Teardown is done once by main()'s finally, never here."""
    global _running, _signals, _shutdown_pending
    _signals += 1
    _running = False
    if _tearing_down or _signals > 2:
        print("\n[main] already shutting down — please wait")
        return
    if _signals == 1:
        print("\n[main] stop requested — finishing the current card safely "
              "(send the signal again to stop immediately)")
        return
    if _defer_depth > 0:
        _shutdown_pending = True
        print("\n[main] stopping as soon as the card on the cup is put down safely")
        return
    raise Shutdown("second stop signal")


shutdown = _on_signal    # old name


def calibrate_loadcell(mass_g: float | None = None):
    """Scale factor from a KNOWN reference mass (default: a US nickel, 5.000 g).
    Also stores the empty-cradle reference used by the start-up card check —
    one of only two places allowed to (see hardware/loadcell.py)."""
    mass_g = float(mass_g or CALIBRATION_MASS_G)
    if not _pose_at_rest():
        input("Arm / shuttle pose unknown. Check the arm, belt and cradle are clear (they will "
              "move straight to their rest pose), then press Enter...")
        servos.arm_park()
        if not shuttle.at_rest():
            shuttle.home()
    shuttle.hold()
    time.sleep(TARE_SETTLE_S)
    input("Make sure the cradle is EMPTY (it is in hold), then press Enter to tare...")
    loadcell.tare(calibration=True)
    input(f"Place the {mass_g:.3f} g reference mass (default: a US 5-cent nickel) flat in the "
          "middle of the cradle, then press Enter...")
    time.sleep(WEIGH_SETTLE_S)
    factor = loadcell.calibrate(known_weight_g=mass_g)
    loadcell.save_calibration(factor)
    w = loadcell.read_grams()
    print(f"[main] Check: reference reads {w:.3f} g (should be {mass_g:.3f} g)")
    input("Remove the reference mass from the cradle, then press Enter...")
    time.sleep(TARE_SETTLE_S)
    w = loadcell.read_grams_unchecked()
    print(f"[main] Empty cradle reads {w:.3f} g ({loadcell.classify(w)})")
    if loadcell.is_empty(w):
        loadcell.tare(calibration=True)
    else:
        print("[main] WARNING: the cradle did not return to its empty reading — re-run the "
              "calibration")
    shuttle.level()


def _wait_interruptible(seconds: float):
    end = time.monotonic() + seconds
    while _running and time.monotonic() < end:
        _beat()
        time.sleep(min(0.5, max(0.0, end - time.monotonic())))


def _load_cards_with_retry():
    """Card list from the API or the (possibly stale) cache. With neither, stay
    up (web UI shows the reason) and retry instead of exiting into a
    systemd crash loop. Returns None if shut down while waiting."""
    while _running:
        try:
            return riftcodex.fetch_all_cards()
        except riftcodex.CardDataUnavailable as exc:
            _set_state("error", f"{exc} — retrying every {CARD_DATA_RETRY_S:.0f} s")
            _wait_interruptible(CARD_DATA_RETRY_S)
    return None


def _await_operator(needs_confirm: bool) -> bool:
    """Wait for the operator: needs_confirm → 'Machine clear' (web / CLI);
    otherwise Resume or 'Machine clear'. False if shutting down. A Resume
    click that arrived while the machine was still halting is honoured (the
    event is consumed here, never cleared on entry)."""
    while _running:
        _beat()
        if read_machine_state().get("confirmed"):
            _resume_event.clear()
            return True
        if not needs_confirm and _resume_event.is_set():
            _resume_event.clear()
            return True
        time.sleep(OPERATOR_POLL_S)
    return False


def _operate(dry_run: bool):
    """Start → sort → (pause / stop / halt → operator) → start again, until shutdown."""
    while _running:
        ms = read_machine_state()
        if not ms.get("clean") and not ms.get("confirmed"):
            _set_state("needs_confirm",
                       f"unclean stop: {ms.get('reason', 'unknown')} — check the arm, belt and "
                       "cradle, remove any card, then confirm (web UI 'Machine clear' or "
                       "`main.py --confirm-clear`)")
            if not _await_operator(needs_confirm=True):
                return
            continue
        confirmed = bool(ms.get("confirmed"))
        _control["stop"] = _control["pause"] = False
        _status["stop_requested"] = _status["pause_requested"] = False
        _set_state("starting", "checking the machine")   # before anything moves (audit M2)
        try:
            if confirmed:
                shuttle.clear_jam()
                _set_card_at(None)
            prepare_machine(confirmed)
            mark_running()
            state = run_sorter(dry_run=dry_run)
        except NeedsConfirm as exc:
            _make_safe()
            _write_machine_state(clean=False, confirmed=False, reason=str(exc))
            continue
        except StopRequested:
            state = _halt("stopped", "")
        except StopMachine as exc:
            _make_safe(hold_cradle=getattr(exc, "hold_cradle", True))
            state = _halt(exc.state, str(exc))
        except Exception as exc:
            _make_safe()
            state = _halt("error", f"start-up failed: {exc!r}")
        if not _running:
            return
        clean, reason = _assess_clean()
        _write_machine_state(clean=clean, confirmed=False, reason=reason if not clean else
                             f"{state}: {_status.get('message', '')}".strip(": "),
                             rest_pose="home_level" if clean else None)
        print(f"[main] Machine {state}. Web UI stays up; "
              f"{'resume' if clean else 'clear the machine and confirm'} to continue. Ctrl+C to exit.")
        if not _await_operator(needs_confirm=not clean):
            return


# ── Single instance + CLI commands that must respect the running sorter ──────
_instance_lock_fh = None


def acquire_instance_lock() -> bool:
    """Hold an flock on INSTANCE_LOCK_FILE for the life of this process (one
    sorter at a time; the CLI uses it to find a running sorter)."""
    global _instance_lock_fh
    if fcntl is None:
        return True
    INSTANCE_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    fh = open(INSTANCE_LOCK_FILE, "a+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return False
    fh.seek(0)
    fh.truncate()
    fh.write(f"{os.getpid()}\n")
    fh.flush()
    _instance_lock_fh = fh
    return True


def sorter_running() -> bool:
    """Is a sorter process (main loop / web-only / calibrate) holding the lock?"""
    if fcntl is None or not INSTANCE_LOCK_FILE.exists():
        return False
    with open(INSTANCE_LOCK_FILE, "a+") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        fcntl.flock(fh, fcntl.LOCK_UN)
    return False


def _web_post(path: str) -> tuple[int, dict]:
    """POST to the running sorter's own web API (which applies the state
    gating). Raises OSError if it cannot be reached."""
    import urllib.error
    import urllib.request
    req = urllib.request.Request(f"http://127.0.0.1:{WEB_PORT}{path}", data=b"", method="POST",
                                 headers={"X-Auth-Token": load_or_create_web_token()})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read()
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            data = json.loads(body) if body else {}
        except ValueError:
            data = {"error": body.decode(errors="replace")}
        return exc.code, data


def _via_running_sorter(paths: list[str]) -> int:
    for path in paths:
        try:
            code, body = _web_post(path)
        except OSError as exc:
            print(f"[main] a sorter process is running but its web UI on port {WEB_PORT} is not "
                  f"reachable ({exc}) — use the web UI, or stop the service first")
            return 1
        if code != 200:
            print(f"[main] refused by the running sorter ({code}): {body.get('error', body)}")
            return 1
    return 0


def cli_empty_bins(bins: list[int], all_bins: bool) -> int:
    """--empty-bin / --empty-all. With a sorter running, the reset goes through
    its web API so can_empty_bin() applies (never while starting / running);
    otherwise nothing can move and the counts are reset directly."""
    for n in bins:
        if n not in _bins.limits:
            print(f"[bins] unknown bin {n}; valid: {sorted(_bins.limits)}")
            return 2
    if sorter_running():
        paths = (["/api/bins/empty-all"] if all_bins else []) + [f"/api/bins/{n}/empty" for n in bins]
        rc = _via_running_sorter(paths)
        if rc:
            return rc
    else:
        if all_bins:
            empty_all_bins()
        for n in bins:
            empty_bin(n)
    print(json.dumps(_bins.snapshot(), indent=2))
    return 0


def cli_confirm_clear() -> int:
    """--confirm-clear: through the running sorter's web API if there is one
    (can_confirm_clear() applies), else straight into the state file."""
    if sorter_running():
        return _via_running_sorter(["/api/confirm-clear"])
    confirm_clear("cli")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Riftbound Card Sorter")
    parser.add_argument("--calibrate",  action="store_true", help="Calibrate the cradle load cell")
    parser.add_argument("--mass", type=float, default=None, metavar="G",
                        help=f"Calibration reference mass in grams (default {CALIBRATION_MASS_G} = US nickel)")
    parser.add_argument("--build-db",   action="store_true", help="Rebuild card hash DB")
    parser.add_argument("--dry-run",    action="store_true", help="Identify only; every card → reject bin")
    parser.add_argument("--web-only",   action="store_true", help="Web UI only")
    parser.add_argument("--empty-bin",  type=int, metavar="N", action="append",
                        help="Reset bin N's count after emptying it (repeatable)")
    parser.add_argument("--empty-all",  action="store_true", help="Reset every bin count")
    parser.add_argument("--confirm-clear", action="store_true",
                        help="Operator: arm, belt and cradle checked and clear (after an unclean stop / jam)")
    parser.add_argument("--web-token", action="store_true", help="Print the web UI token")
    args = parser.parse_args()

    if args.empty_all or args.empty_bin:
        sys.exit(cli_empty_bins(args.empty_bin or [], args.empty_all))
    if args.confirm_clear:
        sys.exit(cli_confirm_clear())
    if args.web_token:
        print(load_or_create_web_token())
        sys.exit(0)

    if not args.build_db and not acquire_instance_lock():
        print(f"[main] ERROR: another sorter process is running ({INSTANCE_LOCK_FILE} is locked)")
        sys.exit(1)

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, _on_signal)

    try:
        _main(args)
    except Shutdown:
        print("[main] stopping now")
    finally:
        if _hw_initialised:
            teardown()


def _ensure_hash_db(cards, dry_run: bool) -> bool:
    """Audit M10: refuse to sort while the hash DB misses more than
    identify.MAX_MISSING_FRACTION of the card list (retrying the missing
    downloads every CARD_DATA_RETRY_S); a dry run only warns. False if shut
    down while waiting."""
    while _running:
        report = build_hash_db(cards, force=False, progress=_beat)
        _status["hash_db"] = {k: report[k] for k in ("total", "hashed", "missing_fraction")}
        _status["hash_db"]["missing"] = len(report["missing"])
        if report["ok"] or dry_run:
            return True
        _set_state("error", f"hash DB incomplete: {len(report['missing'])} of {report['total']} "
                            "cards missing — run `main.py --build-db` (retrying every "
                            f"{CARD_DATA_RETRY_S:.0f} s)")
        _wait_interruptible(CARD_DATA_RETRY_S)
    return False


def _main(args):
    global _today_midnight
    _beat()
    if MOCK_HARDWARE:
        print("=" * 60)
        print("  DEVELOPMENT MODE (no hardware)")
        print("  All GPIO / camera / servo calls are stubbed.")
        print("  Set MOCK_HARDWARE=0 to use real hardware.")
        print("=" * 60)

    if args.build_db:
        # Build-only: no hardware needed; just ensure data/ dir exists
        try:
            cards = riftcodex.fetch_all_cards()
        except riftcodex.CardDataUnavailable as exc:
            print(f"[main] ERROR: {exc}")
            sys.exit(1)
        inventory.init()
        report = build_hash_db(cards, force=True)
        if not report["ok"]:
            sys.exit(1)
        return

    # Hardware first: the pump relay and belt get driven to OFF immediately.
    ms = read_machine_state()
    assume_rest = bool(ms.get("clean")) and ms.get("rest_pose") == "home_level"
    try:
        init_hardware(assume_rest=assume_rest)
    except Exception as exc:
        if MOCK_HARDWARE:
            print(f"[main] Hardware init skipped in mock mode ({exc})")
        else:
            print(
                f"[main] ERROR: Hardware init failed: {exc}\n"
                "       Are you running on a Raspberry Pi with the correct wiring?\n"
                "       To run without hardware: export MOCK_HARDWARE=1"
            )
            _make_safe()
            sys.exit(1)
    inventory.init()
    _publish_bins()
    _today_midnight = _midnight_today()

    if args.calibrate:
        calibrate_loadcell(args.mass)
        return

    # Web UI early, so a missing card list / unclean stop is visible there
    from web.app import create_app
    app = create_app(token=load_or_create_web_token())
    web_thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=WEB_PORT, debug=False, use_reloader=False),
        daemon=True
    )
    web_thread.start()
    print(f"[main] Web UI running at http://riftbound-sorter.local:{WEB_PORT}  (or http://<pi-ip>:{WEB_PORT}); "
          "token: `main.py --web-token`")

    cards = _load_cards_with_retry()
    if cards is None:
        return

    if args.web_only:
        build_hash_db(cards, force=False, progress=_beat)
        _set_state("idle", "web-only mode")
        print("[main] Web-only mode. Ctrl+C to exit.")
        while _running:
            _beat()
            time.sleep(0.5)
        return

    if not _ensure_hash_db(cards, args.dry_run):
        return

    _operate(args.dry_run)


if __name__ == "__main__":
    main()
