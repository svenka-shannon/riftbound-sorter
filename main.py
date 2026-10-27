#!/usr/bin/env python3
"""
Riftbound Card Sorter — Main Loop
==================================
Run on Raspberry Pi Zero 2W.

Usage:
  python main.py              # normal run
  python main.py --calibrate  # calibrate load cell
  python main.py --build-db   # rebuild card hash DB
  python main.py --dry-run    # identify cards without sorting
  python main.py --web-only   # start web UI without sorting

Hardware:
  - Pi Zero 2W + Pi Camera Module 3
  - PCA9685 servo driver (I2C 0x40)
  - HX711 load cell amp (GPIO 5/6)
  - 5V relay → 12V vacuum pump (GPIO 17)
"""

import sys
import time
import argparse
import signal
import threading

from hardware import servos, vacuum, loadcell, camera, conveyor
from vision.identify import build_hash_db, identify
from api import riftcodex, inventory
from sorter.rules_engine import RulesEngine

# ── Config ────────────────────────────────────────────────────────────────────
RULES_FILE         = "config/rules.json"
PICKUP_RETRY_MAX   = 3
CONVEYOR_TRAVEL_S  = 1.2   # seconds for card to reach scanner from pickup
SORT_TRAVEL_S      = 0.8   # seconds from scanner to sort gate

_running       = True
_stats         = {"total": 0, "errors": 0, "double_picks": 0, "unknowns": 0}
_status        = {"state": "running", "hopper_empty": False, "cards_remaining_estimate": 0}
_empty_counter = 0
_session_start = time.time()


def shutdown(sig=None, frame=None):
    global _running
    print("\n[main] Shutting down...")
    _running = False
    vacuum.pump_off()
    conveyor.deinit()
    servos.reset_all()
    servos.deinit()
    vacuum.deinit()
    sys.exit(0)


def sort_one_card(engine: RulesEngine, dry_run: bool = False) -> bool:
    """
    Full pick-scan-sort cycle for one card.
    Returns True on success, False on error/skip.
    """
    global _empty_counter

    # 1. Lower arm + activate pump
    servos.pickup_arm_down()
    vacuum.pump_on()
    time.sleep(0.25)

    # 2. Check load cell — verify single card
    weight_g = loadcell.read_grams()
    result   = loadcell.classify(weight_g)

    if result == "empty":
        vacuum.pump_off()
        servos.pickup_arm_up()
        _empty_counter += 1
        if _empty_counter >= 3 and not _status["hopper_empty"]:
            print(f"[main] HOPPER EMPTY — {_empty_counter} consecutive empty picks. Please refill.")
            _status["hopper_empty"] = True
        else:
            print("[main] No card detected — hopper empty?")
        return False

    if result == "double":
        print(f"[main] Double pick ({weight_g:.1f}g) — releasing extra")
        vacuum.pump_off()
        time.sleep(0.1)
        vacuum.pulse(0.2)   # brief burst to drop extra card
        servos.pickup_arm_up()
        # A double pick still means the hopper has cards
        _empty_counter = 0
        if _status["hopper_empty"]:
            print("[main] Card detected — hopper refilled, resuming.")
            _status["hopper_empty"] = False
        _stats["double_picks"] += 1
        return False

    # Card confirmed present — reset hopper-empty state
    _empty_counter = 0
    if _status["hopper_empty"]:
        print("[main] Card detected — hopper refilled, resuming.")
        _status["hopper_empty"] = False

    # 3. Lift card + transport to scanner
    servos.pickup_arm_up()
    conveyor.transport_card(CONVEYOR_TRAVEL_S)
    vacuum.pump_off()    # release card at scanner station

    # 3a. Pause conveyor briefly so card is stationary during capture
    conveyor.stop()
    time.sleep(0.3)

    # 4. Capture + identify
    jpeg = camera.capture_card_jpeg()

    # Resume conveyor to carry card toward sort gate
    conveyor.run()
    card_id, confidence = identify(jpeg)

    if card_id is None:
        print(f"[main] Card not identified (confidence {confidence:.2f}) — rejecting")
        if not dry_run:
            servos.route_card(engine.reject_bin)
        _stats["unknowns"] += 1
        time.sleep(SORT_TRAVEL_S)
        return True

    card = riftcodex.get_card(card_id)
    card_name = card.get("name", card_id) if card else card_id

    # 5. Apply rules engine
    bin_num   = engine.assign_bin(card) if card else engine.reject_bin
    bin_label = engine.describe_bin(bin_num)

    print(f"[main] {card_name} ({confidence:.0%}) → {bin_label} (bin {bin_num})")

    # 6. Route card
    if not dry_run:
        servos.route_card(bin_num)
        time.sleep(SORT_TRAVEL_S)

    # 7. Log to inventory
    inventory.record_scan(card_id, card_name, bin_num, confidence)
    _stats["total"] += 1
    return True


def run_sorter(dry_run: bool = False):
    """Main sorting loop."""
    engine = RulesEngine(RULES_FILE)

    print(f"[main] Ready — {'DRY RUN' if dry_run else 'SORTING'}. Ctrl+C to stop.")
    idle_count = 0

    while _running:
        success = sort_one_card(engine, dry_run=dry_run)
        if not success:
            idle_count += 1
            if idle_count >= 10:
                print("[main] 10 consecutive misses — check hopper. Sleeping 5s.")
                time.sleep(5)
                idle_count = 0
        else:
            idle_count = 0
        time.sleep(0.05)  # small gap between cards


def main():
    parser = argparse.ArgumentParser(description="Riftbound Card Sorter")
    parser.add_argument("--calibrate",  action="store_true", help="Calibrate load cell")
    parser.add_argument("--build-db",   action="store_true", help="Rebuild card hash DB")
    parser.add_argument("--dry-run",    action="store_true", help="Identify only, no sorting")
    parser.add_argument("--web-only",   action="store_true", help="Web UI only")
    args = parser.parse_args()

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Pre-load Riftcodex card data (network, no hardware needed)
    cards = riftcodex.fetch_all_cards()

    if args.build_db:
        # Build-only: no hardware needed; just ensure data/ dir exists
        inventory.init()
        build_hash_db(cards, force=True)
        sys.exit(0)

    # Initialize hardware (all other modes need it)
    servos.init()
    vacuum.init()
    loadcell.init()
    camera.init()
    conveyor.init()
    inventory.init()

    if args.calibrate:
        print("Place a single Riftbound card on the load cell and press Enter...")
        input()
        loadcell.calibrate(known_weight_g=1.75)
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
        print("[main] Web-only mode. Ctrl+C to exit.")
        web_thread.join()
        return

    run_sorter(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
