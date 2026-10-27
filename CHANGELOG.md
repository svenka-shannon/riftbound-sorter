# Changelog

All notable changes to the Riftbound Card Sorter are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.1.0] — 2024-10

Initial hardware prototype and software stack.

### Added

**Hardware drivers (`hardware/`)**
- `conveyor.py` — L9110S dual-motor driver for card transport rollers; software PWM via RPi.GPIO; forward/stop/brake modes
- `servos.py` — PCA9685 I2C servo controller (0x40, 50 Hz); pickup arm, deflect gate, and bin-select channels; angle presets for 8-bin + reject layout
- `vacuum.py` — Active-LOW relay control of 12V vacuum pump on GPIO 17; pulse helper for card release
- `loadcell.py` — HX711 load-cell reader (GPIO 5/6); classifies weight as empty / single / double pick; calibration helper
- `camera.py` — Pi Camera Module 3 via picamera2; JPEG capture with configurable crop region; loads `config/camera_crop.json` at startup if present

**Vision (`vision/`)**
- `identify.py` — Perceptual hash (pHash, 16x16) card identification; parallel image download and hash DB build via ThreadPoolExecutor; returns (card_id, confidence) with 0.75 minimum threshold; DB cached at `cache/hash_db.json`

**API layer (`api/`)**
- `riftcodex.py` — Riftcodex API client; fetches all card metadata with 24-hour disk cache at `cache/cards.json`; lookup by ID or name
- `inventory.py` — SQLite inventory (`data/inventory.db`); WAL mode; `scans` and `inventory` tables; session stats and CSV export

**Sorting logic (`sorter/`)**
- `rules_engine.py` — JSON-driven rules engine; top-to-bottom evaluation; supports exact-match and list-match on any card field; default catch-all rule; runtime reload

**Web UI (`web/`)**
- `app.py` — Flask dashboard on port 5000; live stats (cards/min, hopper-empty banner) polled every 3–5 s; inventory table; in-browser rules editor with save; CSV export endpoint

**Main loop (`main.py`)**
- Full pick-scan-sort cycle: arm down, vacuum on, weight check, arm up, conveyor transport, camera capture, card identification, rules engine bin assignment, servo routing, inventory log
- Hopper-empty detection after 3 consecutive empty picks with auto-resume on refill
- Double-pick detection with vacuum pulse recovery
- CLI flags: `--calibrate`, `--build-db`, `--dry-run`, `--web-only`
- Clean shutdown on SIGINT/SIGTERM

**Scripts & deployment (`scripts/`)**
- `calibrate_camera.py` — Interactive crop calibration; auto-detects card edges via column/row variance; saves `config/camera_crop.json`
- `setup.sh` — Pi setup script (dependencies, systemd service install)
- `riftbound-sorter.service` — systemd unit for auto-start on boot

**CAD models (`cad/`)**
- Baseplate tile, conveyor rail, conveyor roller, electronics tray, hopper, output bin, scanner hood, sort gate lever, suction arm (OpenSCAD `.scad` sources)

**Configuration**
- `config/rules.json` — Default 8-bin sort rules: Champions, Spells, Followers, Equipment, Legendary/Epic, Rare, Common/Basic, Default
- `config/rules.example.json` — Committed example so the real rules can be machine-local

**KiCad schematic**
- `riftbound_sorter.kicad_sch` — Pi Zero 2W + PCA9685 + HX711 + relay + camera wiring

### Notes
- `concurrent.futures` and `sqlite3` are Python stdlib — no pip entry required
- `adafruit-blinka` is required for `import board` and `import busio` used by the CircuitPython servo driver
- `config/camera_crop.json` is machine-specific and gitignored; run `scripts/calibrate_camera.py` after physical assembly
