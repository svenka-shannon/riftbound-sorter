#!/usr/bin/env python3
"""
Riftbound Card Sorter — Main Loop
==================================
Run on Raspberry Pi Zero 2W.

Usage:
  python main.py                 # normal run
  python main.py --calibrate     # calibrate the cradle load cell
  python main.py --build-db      # rebuild card hash DB
  python main.py --dry-run       # identify cards, send every card to the reject bin
  python main.py --web-only      # start web UI without sorting
  python main.py --empty-bin N   # reset bin N's card count after emptying it
  python main.py --empty-all     # reset every bin count

One card (cards are raw and valuable: when in doubt, do the thing that can't
damage a card — reject it, or stop):
  1. elevator.raise_to_pick()          False → hopper empty / stuck: STOP
  2. arm_to_pick, pump_on, seal, arm_to_drop (card flat 3 mm above the belt at
     X −95), pump_off, release, arm_park
  3. belt runs until card_detect sees the card centred under the lens (X +5),
     then brakes. Not seen / lost → belt stopped, STOP (jam)
  4. capture + identify (failure → reject, normal flow)
  5. belt runs EXIT_TRAVEL_S: card leaves the belt end (X 85) onto the cradle
     (home, level)
  6. shuttle.hold, settle, weigh: empty → STOP (jam); double / unknown /
     unidentified → reject (bin 9)
  7. target bin full → PAUSE with the card held on the cradle in hold until
     the bin is emptied (web UI or --empty-bin), then route it
  8. shuttle.route(bin) tips + verifies the cradle emptied; ShuttleError → STOP
  9. count the card into the bin; hold, check empty, tare, level for the next card

Hardware:
  - Pi Zero 2W + Pi Camera Module 3 (mounted rotated 180°)
  - PCA9685 (I2C 0x40): ch0 pick arm (servos.py), ch1 tilt + ch2 shuttle (shuttle.py)
  - HX711 load cell under the cradle (GPIO 5/6)
  - 5V relay → 12V vacuum pump (GPIO 17)
  - L9110S belt motors (GPIO 23-26), 28BYJ-48 hopper elevator (GPIO 16-21, 12, 13)
"""

import os
import sys
import time
import json
import argparse
import signal
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
import datetime

# `python main.py` runs this file as __main__; web/app.py does `import main`.
# Without this alias that import would load a SECOND copy of this module with
# its own (never updated) _status, so the web UI would show stale data.
if __name__ == "__main__":
    sys.modules.setdefault("main", sys.modules[__name__])

MOCK_HARDWARE = os.environ.get("MOCK_HARDWARE", "0") == "1"

from hardware import servos, vacuum, loadcell, camera, conveyor, elevator, shuttle, card_detect
from hardware.shuttle import ShuttleError
from vision.identify import build_hash_db, identify
from api import riftcodex, inventory
from sorter.rules_engine import RulesEngine

ROOT = Path(__file__).resolve().parent

# ── Config ────────────────────────────────────────────────────────────────────
RULES_FILE       = str(ROOT / "config" / "rules.json")
BIN_COUNTS_FILE  = ROOT / "data" / "bin_counts.json"     # runtime counts
BIN_LIMITS_FILE  = ROOT / "config" / "bin_limits.json"   # optional {"0": 50, ..., "9": 35}

REJECT_BIN = shuttle.REJECT_BIN                          # 9 (physical reject bin)
SORT_BINS  = tuple(range(8))
# Cards per slot before the machine pauses ("bin N full — empty it").
#   lower floor 0-3: ~50 raw cards; upper floor 4-7: ~24 (its slot entry is lower).
#   reject (cad/reject_bin.scad): floor Z 6.5, cards slide in over the lane lip at
#   Z 23.9 (sg_ramp_exit_z) → 17.4 mm of pile before a card can't clear the lip;
#   35 × 0.33 mm = 11.6 mm, leaving room for a loose, uneven pile.
DEFAULT_BIN_LIMITS = {0: 50, 1: 50, 2: 50, 3: 50, 4: 24, 5: 24, 6: 24, 7: 24, REJECT_BIN: 35}

CARD_WEIGHT_G = 1.75    # one raw Riftbound card (load-cell calibration weight)

# Pick & place (step 2)
SEAL_S         = 0.3    # pump on, cup on the card → vacuum seals before lifting
DROP_SETTLE_S  = 0.1    # arm at the drop pose: let it stop swaying before cutting suction
RELEASE_S      = 0.3    # after pump_off: the relay only cuts the pump (no vent valve),
                        # the cup leaks down — wait before lifting away
# Belt exit (step 5): centred card trailing edge X 5−44 = −39 must pass the belt end
# X 85 (124 mm) plus ~20 mm to land on the cradle: 144 mm / ~150 mm/s. Calibrate.
EXIT_TRAVEL_S  = 1.0
# Cradle (steps 6 and 9)
WEIGH_SETTLE_S = 0.2    # hold pose reached → card at rest before weighing
TARE_SETTLE_S  = 0.3    # empty cradle in hold → before checking / taring
# Pause for a full bin (step 7)
BIN_POLL_S     = 0.5
RESUME_DELAY_S = 2.0    # bin reset → hands clear of the tray before the shuttle moves

_running        = True
_stats          = {"total": 0, "sorted": 0, "rejects": 0, "errors": 0, "jams": 0,
                   "double_picks": 0, "weight_unknown": 0, "unknowns": 0, "total_today": 0}
_status         = {"state": "starting", "message": "", "hopper_empty": False, "jam": False,
                   "paused_bin": None, "cards_remaining_estimate": 0,
                   "cards_per_minute": 0.0, "total_today": 0,
                   "last_card": None, "last_weight_g": None, "last_offset_mm": None,
                   "bin_counts": {}, "bin_limits": {}}
_session_start  = time.time()
_recent_scans   = deque(maxlen=60)   # timestamps of the last 60 cards routed
_today_midnight = 0.0                # Unix timestamp of today's midnight; set in main()


# ── Outcomes ──────────────────────────────────────────────────────────────────
class StopMachine(Exception):
    """Stop the loop: the operator has to look at the machine."""
    state = "stopped"


class Jam(StopMachine):
    state = "jam"


class HopperEmpty(StopMachine):
    state = "hopper_empty"


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
    record: bool         # log to inventory after routing
    record_bin: int      # bin recorded in inventory (the rule's bin in dry-run)


class BinFull(Exception):
    """Pause: the target bin is full; the card waits on the cradle in hold."""

    def __init__(self, pending: PendingCard):
        super().__init__(f"bin {pending.bin_num} full — empty it")
        self.pending = pending


# ── Bin capacity tracking ─────────────────────────────────────────────────────
class BinCounts:
    """Cards in each bin, persisted to BIN_COUNTS_FILE. Thread-safe (the web UI
    resets bins), and re-reads the file if another process changed it
    (`main.py --empty-bin N` while the sorter runs)."""

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
        self._mtime = None
        self._load()

    def _load(self):
        if not self.counts_file.exists():
            return
        try:
            data = json.loads(self.counts_file.read_text())
            for k, v in data.get("counts", {}).items():
                if str(k).isdigit() and int(k) in self.counts:
                    self.counts[int(k)] = int(v)
            self._mtime = self.counts_file.stat().st_mtime_ns
        except Exception as exc:
            print(f"[bins] Warning: could not read {self.counts_file}: {exc}")

    def _refresh(self):
        try:
            mtime = self.counts_file.stat().st_mtime_ns
        except FileNotFoundError:
            return
        if mtime != self._mtime:
            self._load()

    def _save(self):
        self.counts_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.counts_file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"counts": {str(b): n for b, n in sorted(self.counts.items())},
                                   "updated": time.time()}, indent=2))
        os.replace(tmp, self.counts_file)
        self._mtime = self.counts_file.stat().st_mtime_ns

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
        with self._lock:
            self._check(bin_num)
            self._refresh()
            self.counts[bin_num] += 1
            self._save()

    def empty(self, bin_num: int):
        with self._lock:
            self._check(bin_num)
            self._refresh()
            self.counts[bin_num] = 0
            self._save()

    def empty_all(self):
        with self._lock:
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


def empty_bin(bin_num: int):
    """Reset a bin's count after the operator emptied it (web UI / CLI)."""
    _bins.empty(bin_num)
    _publish_bins()
    print(f"[bins] bin {bin_num} emptied")


def empty_all_bins():
    _bins.empty_all()
    _publish_bins()
    print("[bins] all bins emptied")


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


def _try(fn, *args):
    """Call a safety action; never let one failure skip the others."""
    try:
        fn(*args)
    except Exception as exc:
        print(f"[main] safety action {getattr(fn, '__name__', fn)} failed: {exc!r}")


def _make_safe():
    """Pump off, belt stopped, arm parked, cradle in hold. Each step independent."""
    _try(vacuum.pump_off)
    _try(conveyor.stop)
    _try(servos.arm_park)
    _try(shuttle.hold)


def _mock_cradle_receives_card():
    """MOCK only: the card that just left the belt lands on the simulated cradle."""
    if MOCK_HARDWARE:
        loadcell.mock_set_load(loadcell.MOCK_CARD_G)


def _prepare_cradle(first: bool = False):
    """Empty cradle in HOLD → check it is empty → tare → LEVEL for the next card.

    Runs at the end of every cycle (shuttle.route() just proved the cradle empty
    against the previous tare), so a card can never be tared away. At start-up
    (first=True) there is no previous tare: the cradle must be empty.
    """
    shuttle.hold()
    time.sleep(TARE_SETTLE_S)
    if not first:
        w = loadcell.read_grams()
        if w >= shuttle.EMPTY_MAX_G:
            raise Jam(f"cradle not empty before tare ({w:.2f} g) — remove the card")
    loadcell.tare()
    shuttle.level()


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
        target = REJECT_BIN
        reason = f"dry run (rule bin {rule_bin})" if rule_bin is not None else f"dry run, {reason}"
    return PendingCard(target, card_id, name, confidence, weight_g, weight_class, reason,
                       record, rule_bin if rule_bin is not None else REJECT_BIN)


def _route_and_record(p: PendingCard):
    """Route the card on the cradle, count it, re-tare. Card must be in HOLD at home."""
    if _bins.is_full(p.bin_num):
        raise BinFull(p)
    try:
        shuttle.route(p.bin_num, read_grams=loadcell.read_grams)
    except ShuttleError as exc:
        raise Jam(f"card stuck on the cradle routing to bin {p.bin_num}: {exc}") from exc
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


# ── One card ──────────────────────────────────────────────────────────────────
def sort_one_card(engine: RulesEngine, dry_run: bool = False) -> int:
    """
    Full pick → centre → scan → cradle → weigh → route cycle for one card.
    Returns the bin the card went to.
    Raises HopperEmpty / Jam (stop), BinFull (pause, card held on the cradle),
    or any unexpected exception (caller stops). On ANY exception the pump is
    off, the belt stopped, the arm parked and the cradle in hold.
    """
    # Precondition: cradle empty, tared, level at home; belt clear; arm parked.
    reference = card_detect.capture_reference()          # empty station, before the drop

    if not elevator.raise_to_pick():
        raise HopperEmpty("hopper empty (or elevator stuck) — refill and restart")
    _status["cards_remaining_estimate"] = elevator.cards_remaining_estimate()

    try:
        # 2. Pick and place onto the belt
        servos.arm_to_pick()
        vacuum.pump_on()
        time.sleep(SEAL_S)
        servos.arm_to_drop()
        time.sleep(DROP_SETTLE_S)
        vacuum.pump_off()
        time.sleep(RELEASE_S)
        servos.arm_park()

        # 3. Belt until the card is centred under the lens
        res = card_detect.centre_card(reference, conveyor.run, conveyor.brake, conveyor.stop)
        _status["last_offset_mm"] = None if res.offset_mm is None else round(res.offset_mm, 2)
        if res.jam:
            raise Jam(f"card {res.reason} at the scanner after {res.elapsed_s:.2f} s — belt stopped; "
                      "check the belt between the arm and the scanner")
        if not res.ok:
            print(f"[main] card stopped {res.offset_mm:+.1f} mm off centre — capturing anyway")

        # 4. Capture + identify (failure → reject, normal flow)
        jpeg = camera.capture_card_jpeg(shift_px=card_detect.crop_shift_px(res.offset_mm or 0.0))
        card_id, confidence, card = _identify(jpeg)

        # 5. Off the belt end onto the cradle (home, level)
        _ensure_cradle_ready()
        conveyor.run()
        time.sleep(EXIT_TRAVEL_S)
        conveyor.stop()
        _mock_cradle_receives_card()

        # 6. Weigh at rest in hold
        shuttle.hold()
        time.sleep(WEIGH_SETTLE_S)
        weight_g = loadcell.read_grams()
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
    except BaseException:
        _make_safe()
        raise


def _route_pending(p: PendingCard) -> int:
    """Route a card that waited on the cradle for its bin to be emptied."""
    try:
        _route_and_record(p)
        return p.bin_num
    except BaseException:
        _make_safe()
        raise


def _wait_for_bin_space(p: PendingCard) -> bool:
    """Paused: card held on the cradle in HOLD until bin p.bin_num is emptied.
    Returns False if the sorter is shutting down."""
    _status["paused_bin"] = p.bin_num
    _status["state"] = "paused"
    _status["message"] = f"bin {p.bin_num} full — empty it"
    print(f"[main] PAUSED: bin {p.bin_num} full — empty it, then reset it in the web UI or with "
          f"`main.py --empty-bin {p.bin_num}`. Card held on the cradle.")
    while _running:
        if not _bins.is_full(p.bin_num):
            print(f"[main] bin {p.bin_num} emptied — resuming in {RESUME_DELAY_S:.0f} s")
            time.sleep(RESUME_DELAY_S)
            _set_state("running")
            return True
        time.sleep(BIN_POLL_S)
    return False


def _halt(state: str, message: str) -> str:
    _set_state(state, message)
    return state


def run_sorter(dry_run: bool = False, engine=None, max_cycles: int | None = None) -> str:
    """Main sorting loop. Returns the final state:
      "stopped"       shutdown requested or max_cycles reached
      "jam"           card stuck / lost / not seen — clear it and restart
      "hopper_empty"  refill and restart
      "error"         unexpected exception — card position unknown, check and restart
    A full bin pauses (card held) and resumes once the bin is emptied.
    """
    engine = engine or RulesEngine(RULES_FILE)
    _publish_bins()
    _set_state("running")
    print(f"[main] Ready — {'DRY RUN (all cards → reject bin)' if dry_run else 'SORTING'}. Ctrl+C to stop.")

    pending = None
    cycles = 0
    while _running and (pending is not None or max_cycles is None or cycles < max_cycles):
        try:
            if pending is not None:
                if not _wait_for_bin_space(pending):
                    break
                p, pending = pending, None
                _route_pending(p)
            else:
                cycles += 1
                sort_one_card(engine, dry_run=dry_run)
        except BinFull as exc:
            pending = exc.pending
            continue
        except StopMachine as exc:
            if isinstance(exc, Jam):
                _stats["jams"] += 1
            return _halt(exc.state, str(exc))
        except Exception as exc:
            # The card could be anywhere (arm, belt, cradle): never feed another
            # card on top of it. Hardware was made safe by sort_one_card.
            _stats["errors"] += 1
            return _halt("error", f"unexpected error {exc!r} — card position unknown; "
                                  "check the belt and cradle, then restart")
        time.sleep(0.05)  # small gap between cards
    _set_state("stopped", "" if _running else "shutdown")
    return "stopped"


# ── Start-up / shutdown ───────────────────────────────────────────────────────
def init_hardware():
    """Pump off first, then belt, PCA9685 (arm), shuttle (shares the PCA9685),
    load cell, camera, elevator."""
    vacuum.init()
    conveyor.init()
    servos.init()
    servos.arm_park()          # first move is direct: cup must be empty here
    shuttle.init()             # homes: hold → home → level
    loadcell.init()
    camera.init()
    elevator.init()


def prepare_machine():
    """Before sorting: belt stopped, arm parked, elevator homed, cradle tared."""
    conveyor.stop()
    servos.arm_park()
    print("[main] Homing the hopper elevator...")
    if not elevator.home():
        raise Jam("hopper elevator did not reach its home switch")
    print("[main] Taring the cradle — it must be EMPTY")
    _prepare_cradle(first=True)


def shutdown(sig=None, frame=None):
    global _running
    print("\n[main] Shutting down...")
    _running = False
    _try(vacuum.pump_off)
    _try(conveyor.stop)
    _try(servos.arm_park)
    _try(conveyor.deinit)
    _try(shuttle.deinit)        # cradle level at home (before servos releases the PCA)
    _try(elevator.deinit)
    _try(servos.deinit)
    _try(vacuum.deinit)
    _try(camera.deinit)
    sys.exit(0)


def calibrate_loadcell():
    shuttle.hold()
    time.sleep(TARE_SETTLE_S)
    input("Make sure the cradle is EMPTY (it is in hold), then press Enter to tare...")
    loadcell.tare()
    input("Place ONE Riftbound card flat on the cradle, then press Enter...")
    time.sleep(WEIGH_SETTLE_S)
    factor = loadcell.calibrate(known_weight_g=CARD_WEIGHT_G)
    loadcell.save_calibration(factor)
    w = loadcell.read_grams()
    print(f"[main] Check: card reads {w:.2f} g ({loadcell.classify(w)})")
    input("Remove the card from the cradle, then press Enter...")


def main():
    parser = argparse.ArgumentParser(description="Riftbound Card Sorter")
    parser.add_argument("--calibrate",  action="store_true", help="Calibrate the cradle load cell")
    parser.add_argument("--build-db",   action="store_true", help="Rebuild card hash DB")
    parser.add_argument("--dry-run",    action="store_true", help="Identify only; every card → reject bin")
    parser.add_argument("--web-only",   action="store_true", help="Web UI only")
    parser.add_argument("--empty-bin",  type=int, metavar="N", action="append",
                        help="Reset bin N's count after emptying it (repeatable)")
    parser.add_argument("--empty-all",  action="store_true", help="Reset every bin count")
    args = parser.parse_args()

    if args.empty_all or args.empty_bin:
        if args.empty_all:
            empty_all_bins()
        for n in args.empty_bin or []:
            try:
                empty_bin(n)
            except ValueError as exc:
                print(f"[bins] {exc}")
                sys.exit(2)
        print(json.dumps(_bins.snapshot(), indent=2))
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    if MOCK_HARDWARE:
        print("=" * 60)
        print("  DEVELOPMENT MODE (no hardware)")
        print("  All GPIO / camera / servo calls are stubbed.")
        print("  Set MOCK_HARDWARE=0 to use real hardware.")
        print("=" * 60)

    # Pre-load Riftcodex card data (network, no hardware needed)
    cards = riftcodex.fetch_all_cards()

    if args.build_db:
        # Build-only: no hardware needed; just ensure data/ dir exists
        inventory.init()
        build_hash_db(cards, force=True)
        sys.exit(0)

    # Initialize hardware (all other modes need it)
    try:
        init_hardware()
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

    global _today_midnight
    _today_midnight = _midnight_today()

    if args.calibrate:
        calibrate_loadcell()
        shutdown()

    # Load hash DB
    build_hash_db(cards, force=False)

    # Start web UI in background thread
    from web.app import create_app
    app = create_app()
    web_thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=5000, debug=False),
        daemon=True
    )
    web_thread.start()
    print("[main] Web UI running at http://riftbound-sorter.local:5000  (or http://<pi-ip>:5000)")

    if args.web_only:
        _set_state("idle", "web-only mode")
        print("[main] Web-only mode. Ctrl+C to exit.")
        web_thread.join()
        return

    try:
        prepare_machine()
        state = run_sorter(dry_run=args.dry_run)
    except StopMachine as exc:
        _make_safe()
        state = _halt(exc.state, str(exc))
    except Exception as exc:
        _make_safe()
        state = _halt("error", f"start-up failed: {exc!r}")
    if state != "stopped":
        # Stopped for the operator: hardware is safe; keep the web UI up with the
        # reason until Ctrl+C / systemctl stop.
        print(f"[main] Machine stopped ({state}). Web UI stays up. Ctrl+C to exit.")
        while _running:
            time.sleep(1)


if __name__ == "__main__":
    main()
