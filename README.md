# Riftbound Sorter

![Status: Work in Progress](https://img.shields.io/badge/Status-Work%20in%20Progress-yellow)

A DIY sorting machine for Riftbound (League of Legends TCG) cards. It identifies each card with a Pi camera (perceptual hashing, no cloud) and weighs it on a load cell. It then drops the card into one of 8 tray slots (2 floors × 4 columns) or a reject bin, according to JSON sort rules.

The machine handles **raw, unsleeved, valuable cards**. Every card is lifted by suction from the top of the stack, laid flat on the belt, and dropped short distances by gravity. Nothing rubs, pinches or friction-feeds a card. When in doubt the machine rejects the card or stops.

Machine footprint: 570 × 540 mm baseplate (3 × 3 printed tiles, keyed together, on a backing board). Every printed part fits a 256 × 256 mm bed (Bambu P1S).

- **Build guide:** [`docs/ASSEMBLY.md`](docs/ASSEMBLY.md)
- **Parts, costs, power budget and cost-down options:** [`BOM.md`](BOM.md)
- **Wiring:** [`docs/wiring_diagram.svg`](docs/wiring_diagram.svg)
- **History:** [`CHANGELOG.md`](CHANGELOG.md)

---

## How it works (v2)

```
 hopper ──► suction arm ──► belt ──► camera stop ──► cradle (weigh) ──► shuttle ──► tray slot / reject
 (raised     (one servo,     (4 round   (card centred     (load cell,      (column 0–3,   (upper or
  floor)      parallelogram)  belts)     at X +5)          at rest)         or reject)     lower floor)
```

1. **Hopper elevator.** A 28BYJ-48 stepper turns a T8 lead screw and raises the hopper floor until a light feeler flag on the top card trips a microswitch. The top card is then at pick height, level with the belt. When the floor plate reaches the top without tripping the flag, the hopper is empty.
2. **Pick arm (PCA9685 ch0).** One MG996R drives a crank with two phased followers (a triple parallelogram). The suction cup always points straight down. It comes down onto the card, lifts it vertically, carries it over a ~170° arc and lowers it flat onto the belt, 3 mm above it at X −95. A spring slider under the cup takes up height errors.
   - Vacuum comes from a 12 V diaphragm pump on relay channel 1 (GPIO 17).
   - To release the card, the pump goes off and a **12 V normally-closed vent valve**, teed into the vacuum line, opens for 0.4 s (relay channel 2, GPIO 27). The arm then lifts slowly so a card still stuck to the cup peels off onto the belt.
3. **Conveyor.** The conveyor sits on a 60 mm printed riser so cards can later *fall* into both tray floors.
   - Two N20 gear motors drive the two rollers directly. They are run by an L9110S on plain GPIO 23–26.
   - Four 135 × 3 mm O-ring round belts carry the card over a slide bed.
   - Side guides keep it square.
4. **Scan station.** A light-tight hood holds two LED strips (no ring, so foils show no hotspot). A Pi Camera Module 3 looks down from 100 mm, fixed-focused at the card, in its full-field 2304 × 1296 mode at 50 fps. The belt runs until the camera's low-res stream sees the card **centred under the lens**, then brakes, and the frame is captured. The image is flipped 180° for the bracket and identified against a local hash DB.
5. **Cradle shuttle.** The belt carries the card onto a cradle mounted on a 50 g TAL221 load cell.
   - **ch1** tips the cradle 10° nose-down (HOLD). The card is weighed **at rest, alone**: empty, single, double pick or unknown.
   - **ch2** slides the carriage to one of 4 columns or the reject position.
   - ch1 then tips the card forward into the **upper** slot, or swings the cradle down onto a fixed ramp into the **lower** slot (or the reject bin).
   - The cradle is checked empty and re-tared for the next card.
6. **Bin capacity.** The software counts cards per bin. The default limits are conservative: lower floor 40, upper floor 12, reject 35 (raise them in `config/bin_limits.json` once tested). When a bin is full it **pauses with the card held on the cradle** until you empty the bin and reset it.

Unidentified cards, double or unknown weights all go to the reject bin. Jams, lost cards and an empty hopper stop the machine safely: pump off, belt stopped, arm parked, cradle in HOLD.

---

## Hardware summary

| Subsystem | Parts | Interface |
|---|---|---|
| Brain | Raspberry Pi Zero 2 W | — |
| Camera | Pi Camera Module 3 (standard), 500 mm SC1130 ribbon | CSI |
| Servos | 3 × MG996R on a PCA9685: ch0 pick arm, ch1 cradle tilt, ch2 shuttle carriage | I²C 0x40 (GPIO 2/3) |
| Load cell | TAL221 50 g + HX711, under the cradle | GPIO 5 (DOUT), 6 (SCK) |
| Vacuum | 12 V R385 diaphragm pump + 12 V normally-closed vent valve, via a **2-channel** active-LOW relay (10 kΩ pull-ups = off when floating) | GPIO 17 (pump), GPIO 27 (vent) |
| Belt | 2 × N20 6 V 200 rpm via L9110S, both rollers driven | **plain GPIO** 23/24 (A), 25/26 (B), not I²C |
| Hopper | 28BYJ-48 + ULN2003, T8×8 lead screw; feeler-flag switch + home switch | GPIO 16/19/20/21; switches GPIO 12 (top), 13 (home) |
| Power | **12 V 5 A** adapter → three fixed 5 V Pololu bucks: D24V22F5 logic (Pi, LEDs, relay), D24V50F5 servos (PCA9685 V+), D36V28F5 motors (L9110S, ULN2003) | PCA9685 VCC = Pi 3.3 V |

Total ≈ $796, of which ≈ $609 is still to buy; the optional cost-downs in [`BOM.md`](BOM.md) bring that to ≈ $549 without changing the design (≈ $495 with all of them). About 4 kg of filament.

---

## Quick start

### 1. Build the machine

Follow [`docs/ASSEMBLY.md`](docs/ASSEMBLY.md): print list, heat-set inserts, 11 mechanical steps, wiring, calibration. Read its **Known risks / test first** section before printing.

### 2. Set up the Pi

Use Raspberry Pi OS Lite 64-bit, **Bookworm or trixie**.

```bash
git clone https://github.com/svenka-shannon/riftbound-sorter
cd riftbound-sorter
bash scripts/setup.sh
```

This enables I²C and installs the system packages from apt: `python3-picamera2`, `python3-libcamera`, numpy/scipy/Pillow, `libtiff6`, `i2c-tools`, and **`python3-rpi-lgpio`** (the `RPi.GPIO` drop-in for current Raspberry Pi OS). It creates `venv/` **with `--system-site-packages`** so the venv sees those modules, installs `requirements.txt`, sets the hostname to `riftbound-sorter`, installs the systemd service and prints the web UI token. The gandalf15 HX711 library is **vendored** in `hardware/vendor/`: don't pip-install a package called `hx711` (that PyPI name is a different library). Check with `venv/bin/python -c "import picamera2, board"` (ASSEMBLY.md §15).

**Always run hardware scripts with the Pi venv's Python** (`venv/bin/python …`). A plain `python` or a `uv run` script environment has no GPIO, camera or PCA9685 libraries.

### 3. Build the card database

```bash
venv/bin/python main.py --build-db
```

This downloads card data and images from Riftcodex and builds the local perceptual-hash index. It needs internet and takes about 10–20 minutes. Later runs fall back to the cached card list if the API is down.

### 4. Test and calibrate

Follow ASSEMBLY.md §16 for the full order (load cell → arm → elevator trip → shuttle → camera → centring and other tunables).

```bash
venv/bin/python scripts/test_hardware.py --no-mock       # menu of 11 subsystem tests
venv/bin/python main.py --calibrate                      # load cell: 5.000 g US nickel (or --mass G)
venv/bin/python scripts/calibrate_servos.py --no-mock    # 1 arm, 2 cradle tilt, 3 shuttle columns
venv/bin/python scripts/calibrate_camera.py --no-mock    # empty station, then a centred card → crop
cp config/machine.example.json config/machine.json       # belt centring, focus, exit run, … (§16.6)
```

Calibration files are written to `config/`:
- `servo_calibration.json`, `shuttle_calibration.json` (servo angles; ch2 actuation range)
- `loadcell_calibration.json` (scale factor + empty-cradle reference)
- `camera_crop.json`
- `machine.json` (per-machine tunables, every key optional)
- `bin_limits.json` (optional, to raise bin limits)

### 5. Run (bulk commons first)

```bash
sudo systemctl start riftbound-sorter        # or: venv/bin/python main.py
venv/bin/python main.py --confirm-clear      # first start / after an unclean stop (or "Machine clear" in the web UI)
venv/bin/python main.py --dry-run            # identify + weigh; every card goes to the reject bin
venv/bin/python main.py --empty-bin 4        # reset bin 4's count after emptying it (also --empty-all); machine paused or stopped
venv/bin/python main.py --web-token          # show the web UI token
```

- The web UI runs at `http://riftbound-sorter.local:5000` (`RIFTBOUND_WEB_PORT` changes the port).
- **First start, or any start after an unclean stop:** the sorter waits until you confirm the machine is clear (web UI **Machine clear** or `--confirm-clear`).
- **It refuses to start with a card on the cradle:** it compares the cradle with the stored empty-cradle reference before taring.
- <!-- PENDING code round 2: teardown --> **Stopping:** the first stop signal (`systemctl stop`, Ctrl-C) finishes the current card; a second one stops immediately. Shutdown leaves the shuttle where it is, with its servos limp. Stop the service before unplugging.

### Development (any machine)

`MOCK_HARDWARE=1` stubs all GPIO, camera and I²C calls and simulates the stack, cradle and belt:

```bash
MOCK_HARDWARE=1 python main.py --dry-run
MOCK_HARDWARE=1 python main.py --web-only
uv run scripts/test_hardware.py            # mock by default
uv run scripts/calibrate_servos.py         # mock by default (still writes config/)
python -m pytest tests/                    # mock tests of the sort cycle, its safety paths and the audit fixes
```

---

## Wiring overview

```
Pi Zero 2 W
├── GPIO 2/3 (I²C) ── PCA9685 @0x40 ── ch0 MG996R pick arm
│                                    ├─ ch1 MG996R cradle tilt
│                                    └─ ch2 MG996R shuttle carriage
├── GPIO 5/6 ──────── HX711 ── TAL221 50 g (under the cradle)
├── GPIO 17 ───────── relay IN1 (active LOW, 10 kΩ pull-up to 3.3 V) ── 12 V pump
├── GPIO 27 ───────── relay IN2 (active LOW, 10 kΩ pull-up to 3.3 V) ── 12 V NC vent valve
├── GPIO 23/24/25/26  L9110S (plain GPIO) ── N20 A + N20 B (belt rollers)
├── GPIO 16/19/20/21  ULN2003 ── 28BYJ-48 (hopper lead screw)
├── GPIO 12 / 13 ──── top-of-stack switch / home switch (C to GND, internal pull-ups; NO/NC per elevator.py)
└── CSI (faces +X) ── 500 mm SC1130 ── Camera Module 3

12 V 5 A ─┬─ Pololu D24V22F5 → 5 V logic: Pi, LEDs, relay
          ├─ Pololu D24V50F5 → 5 V servo: PCA9685 V+ only (+ 1000 µF)
          ├─ Pololu D36V28F5 → 5 V motor: L9110S (N20s), ULN2003 (28BYJ-48)
          ├─ relay COM1 → NO1 → pump (flyback diode across it)
          └─ relay COM2 → NO2 → vent valve (flyback diode across it)
PCA9685 VCC = Pi 3.3 V · 10 kΩ pull-ups GPIO 17, 27 · 10 kΩ pull-downs GPIO 23–26
```

There is only one I²C device (the PCA9685 at 0x40). The relay module must switch off with a 3.3 V input; ASSEMBLY.md §14.1 has the bench check. The full pin tables are in ASSEMBLY.md §14 and in [`docs/wiring_diagram.svg`](docs/wiring_diagram.svg). `riftbound_sorter.kicad_sch` is a text-only sheet that mirrors the same tables.

---

## Rules engine

Sort logic lives in `config/rules.json`. Rules are evaluated top to bottom and the first match wins. Each rule has a `match` object of `field: value` pairs, all of which must match; a list means "any of". `{"default": true}` matches everything. Bins:
- 0–3: lower floor, columns 0–3.
- 4–7: upper floor, columns 0–3.
- 9: reject bin.

The lower-floor slots hold more than three times as many cards as the upper ones (default limits 40 vs 12), so put the big categories on bins 0–3.

```json
{
  "_bin_count": 8,
  "_reject_bin": 9,
  "rules": [
    { "name": "Champions",      "match": {"type": "Champion"},                    "bin": 0 },
    { "name": "Legendary/Epic", "match": {"rarity": ["Legendary", "Epic"]},      "bin": 4 },
    { "name": "Default",        "match": {"default": true},                       "bin": 7 }
  ]
}
```

Card fields come from the Riftcodex API (`type`, `rarity`, `domain`, `set`, `name`, …). You can edit rules in the web UI; they are validated before saving and reloaded before the next card.

---

## Web UI

Flask on port 5000 (`RIFTBOUND_WEB_PORT`). Anything that changes state needs the **web UI token**, stored in `config/web.json` and shown by `main.py --web-token`. The browser asks for it once and remembers it; API clients send it as an `X-Auth-Token` header.

| Page | Path | Description |
|---|---|---|
| Dashboard | `/` | Live state, sort rate, bin counts and limits, hopper-empty / jam / bin-full banners; **Pause**, **Resume**, **Stop** and **Machine clear** buttons |
| Inventory | `/inventory` | Sorted-card log with search and bin filter |
| Rules editor | `/rules` | Edit and save `rules.json` (token) |
| Export | `/export`, `/export/tcgplayer` | Inventory CSV, TCGPlayer import CSV |
| Read-only API | `/api/status`, `/api/bins`, `/api/stats`, `/api/sessions`, `/api/throughput` | Status, bin counts and limits |
| Control API (token) | `POST /api/pause`, `/api/resume`, `/api/stop`, `/api/confirm-clear`, `/api/bins/<n>/empty`, `/api/bins/empty-all` | Same as the dashboard buttons |

- **Pause** finishes the card in progress and waits; **Resume** continues. **Stop** stops sorting at the next card boundary but keeps the process and the web UI up.
- **Machine clear** confirms the arm, belt and cradle are clear after an unclean stop or a jam.
- **Bins can only be emptied while the machine is paused or stopped**, or the one bin it is paused on because it is full.

---

## Project structure

```
riftbound-sorter/
├── main.py                 # sort cycle, CLI (--calibrate [--mass G], --build-db, --dry-run, --web-only,
│                           #   --empty-bin, --empty-all, --confirm-clear, --web-token)
├── hardware/               # servos (arm), shuttle (ch1/ch2), elevator, conveyor, vacuum (pump + vent),
│                           #   loadcell, camera, card_detect, machine_config; vendor/hx711.py (gandalf15)
├── vision/identify.py      # perceptual-hash identification
├── api/                    # Riftcodex client (with offline cache), SQLite inventory
├── sorter/rules_engine.py  # JSON rules → bin
├── web/app.py              # Flask UI + JSON API
├── scripts/                # setup.sh, test_hardware.py, calibrate_servos.py, calibrate_camera.py, systemd unit
├── tests/                  # mock-hardware tests
├── config/                 # rules.json, machine.example.json, calibration JSON files (machine.json, web.json are local)
├── cad/                    # OpenSCAD parts, assembly.scad, assembly-steps.yaml, collision checks
├── docs/                   # ASSEMBLY.md, wiring_diagram.svg, assembly videos
└── riftbound_sorter.kicad_sch
```

---

## Development status

- [x] Card identification via perceptual hashing; Riftcodex sync with offline cache
- [x] v2 sort cycle: elevator → suction pick → vent release → camera-centred scan → weigh on the cradle → shuttle route
- [x] Bin capacity tracking with pause and resume
- [x] Web UI pause / resume / stop / machine-clear with a token; start-up refuses a card on the cradle or an unconfirmed unclean stop
- [x] Mock-hardware tests for the cycle, its safety paths and the audit fixes
- [x] CAD for every v2 part, with collision, kinematics and assembly-access checks (`cad/pick_arm_check.py`, `cad/shuttle_check.py`)
- [x] Calibration tools for arm, tilt, columns, camera crop and load cell; per-machine tunables in `config/machine.json`
- [ ] Physical build and calibration (see ASSEMBLY.md §19 for what to test first)
- [ ] Camera crop live preview in the web UI

---

## License

MIT
