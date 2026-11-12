# Changelog

All notable changes to the Riftbound Card Sorter are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [2.0.0] — 2026-11-11 — v2 redesign (branch `audit-fixes`)

The whole card path is redesigned for **valuable raw (unsleeved) cards**: no friction feeding, no gates that slide a card sideways, and every card weighed at rest. The pre-build audit fixes ship in the same release. Build guide: `docs/ASSEMBLY.md`. Parts and power: `BOM.md`.

### Changed: machine
- **Hopper**
  - Before: bottom-feed gravity hopper (exit slot, separation wedge, gravity sled).
  - Now: a **motor-raised floor**. A 28BYJ-48 + ULN2003 turns a T8×8 lead screw that lifts a carriage on 2 × LM8UU.
  - A light printed feeler flag with a conjugate cam trips a microswitch when the top card reaches pick height. A second switch homes the floor.
  - An empty plate passes under the flag through a notch, so the soft top limit reports "hopper empty".
  - Code: `hardware/elevator.py` (GPIO 16/19/20/21, switches 12/13). CAD: `cad/hopper.scad`, `cad/hopper_elevator.scad`.
- **Pick arm**
  - Before: vertical-axis swing arm on an undesigned post.
  - Now: a **single MG996R (ch0) with a crank and two phased followers** (triple parallelogram). The suction cup stays vertical and the card stays flat, lifting straight up and lowering straight down.
  - The cup sits on a spring slider. SMC ZPT16BS-B5 bellows pad. The vacuum tube runs through the hollow pivot.
  - Pick at X −215, drop at X −95. Servo moves are cosine-ramped.
  - Files: `cad/suction_arm.scad`, `cad/pick_arm_check.py`.
- **Conveyor**
  - Before: rollers with #010 O-rings.
  - Now: a **60 mm riser**; 608ZZ bearing housings; **4 × 135 × 3 mm O-ring round belts** over a slide bed; both rollers direct-driven by N20s through 3 → 8 mm couplings (`cad/riser.scad`, `conveyor_rail.scad`, `conveyor_roller.scad`, `motor_mount.scad`, `slide_bed.scad`).
- **Scan station**
  - Light-tight hood with **LED strips** instead of a ring (no glare spot on foils).
  - Side guides narrow the channel to 66.4 mm.
  - The camera bracket stands on the front rail feet and holds the lens 100 mm above the card.
  - The camera axis moved to X +5 to clear the arm's drop zone.
  - 500 mm SC1130 ribbon; the Pi's CSI connector faces +X.
- **Sorter**
  - Before: 2 flat gate levers.
  - Now: a **cradle shuttle**. The card leaves the belt onto a cradle on the TAL221 load cell and is weighed at rest in HOLD.
  - ch2 (slider-crank) moves it to one of 4 columns or the reject position. ch1 (D-shaft crank) tips it into the upper slot, or down a fixed ramp into the lower slot or the reject bin.
  - The cradle needs PTFE tape.
  - Files: `cad/shuttle.scad`, `shuttle_geom.scad`, `shuttle_check.py`, `lower_ramp.scad`, `reject_bin.scad`.
- **Tray**
  - The 2-floor tray moved to X 178..276.
  - New separate reject bin.
- **Assembly**
  - `cad/machine_frame.scad` is the single source of truth for the card path.
  - `cad/assembly.scad` builds the machine from `asm_*` modules with poses.
  - `cad/assembly-steps.yaml` has 11 build steps.
- **Electronics tray:** added 3 cable slots in the −X wall for the shorter (≈0.8 m) harness route round the hopper.

### Changed: software
- **New sort cycle in `main.py`:**
  1. elevator raise;
  2. suction pick and drop;
  3. belt runs until the camera sees the card centred (`hardware/card_detect.py`);
  4. capture (flipped 180°, 16:9) and identify;
  5. cradle weigh;
  6. route.
  - Empty, unknown and double weights all go to the reject bin.
  - Jams, a lost card and an empty hopper stop the machine safely.
- **Bin capacity.** Per-bin counts with limits (lower 50, upper 24, reject 35). A full bin **pauses with the card held on the cradle** until it is reset from the web UI, `--empty-bin N` or `--empty-all`.
- **Module ownership.** `hardware/servos.py` owns only ch0 (arm). `hardware/shuttle.py` owns ch1 (tilt) and ch2 (carriage), each with ramped moves and interlocks.
- **Load cell.** `hardware/loadcell.py` uses `zero()`, detects failed reads and saves its calibration to `config/loadcell_calibration.json`.
- **Calibration tools.**
  - `scripts/calibrate_servos.py`: arm, tilt and columns, with jog keys and `--verify`.
  - `scripts/calibrate_camera.py`: empty-station reference + centred card → crop.
- **Tests.** `scripts/test_hardware.py` has 10 subsystem tests. `tests/test_cycle_mock.py` has 26 mock tests, including every safety path.

### Fixed (pre-build audit)
- **Firmware**
  - Pump-off and arm-park now run in `finally`.
  - The session survives per-card errors.
  - A double pick no longer re-fires the pump.
  - Load-cell calibration uses tared counts.
  - The relay polarity and presets in the test script now match `servos.py` and `vacuum.py`.
- **L9110S brake** was driving both motors in reverse at full power for 50 ms; it is now a true brake (both inputs HIGH).
- **Weights** outside the bands are rejected, and the belt stops after routing.
- **CAD**
  - Real 608ZZ pockets (the boss used to be solid).
  - The roller key no longer slots the whole roller.
  - Sorting-tray joins and screws go into solid bosses.
  - The camera bracket uses the real Pi Cam 3 hole pattern.
  - The hopper is now fastened down; the arm post exists.
- **Electrical: from the independent audit, documented in BOM.md / ASSEMBLY.md §14**
  - **12 V 5 A** supply. The arm-move peak is ≈ 3.2 A, over the 3 A adapter.
  - **Three** fixed 5 V regulators: logic, servo, and a new motor rail for the N20s and the stepper, which were on the Pi's regulator.
  - 1000 µF on the servo and motor rails and at PCA9685 V+.
  - Flyback diode across the pump.
  - **10 kΩ pull-downs on the L9110S inputs** (GPIO 23–26 float after `cleanup()`), plus the existing 10 kΩ pull-up on the relay input (GPIO 17).
  - **PCA9685 VCC on 3.3 V** (the old schematic had 5 V, which pulls the Pi's I²C pins to 5 V).
  - HX711 DOUT = GPIO 5 and SCK = GPIO 6 (the old SVG had them swapped).

### Documentation
- **`BOM.md`** rewritten for v2:
  - one de-duplicated BOM with have / verify / buy status and totals;
  - still to buy ≈ $552;
  - power budget, printed-parts table, fastener counts.
- **`docs/ASSEMBLY.md`** rewritten:
  - print list; all 34 heat-set inserts;
  - 11 mechanical steps with screws and checks;
  - GPIO and PCA9685 tables, power rails, harness, ribbon, tube and load-cell routing;
  - software setup and calibration order;
  - first run, troubleshooting, known risks, and a list of code/CAD disagreements.
- **`README.md`** updated to the v2 design. The L9110S is plain GPIO, not I²C 0x60. The rules format is the real `match` format.
- **`docs/wiring_diagram.svg`** redrawn for the v2 pinout. **`riftbound_sorter.kicad_sch`** text updated to match. **`docs/assembly-guide.html`** marked as superseded (v1 design).

### Removed
- Sort-gate levers (`sort_gate_lever.scad` no longer printed).
- Hopper gate, gravity sled and exit slot.
- Old swing arm and arm post.
- #010 O-rings.
- LED ring.
- Separate weigh platform.
- 9 printed output bins (`output_bin.scad`).
- LM2596 bucks.
- Short CSI adapter cable.

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
