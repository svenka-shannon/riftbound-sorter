# Riftbound Sorter

![Status: Work in Progress](https://img.shields.io/badge/Status-Work%20in%20Progress-yellow)

A DIY card sorting machine for the Riftbound (League of Legends TCG) card game. Identifies cards via perceptual hashing using a Pi Camera, then physically routes them into one of 9 output bins based on configurable sort rules. No cloud API or internet connection required for card identification.

Machine footprint: ~580×540mm (under 2ft×2ft).

---

## Features

- **Offline card identification** — perceptual hash matching against a local image database; no cloud calls, no API key needed
- **Riftcodex integration** — pulls card metadata (set, rarity, type, cost, etc.) from the free Riftcodex API on first sync
- **Configurable rules engine** — JSON-based sort logic; map any card attribute or combination to a bin
- **Double-pick detection** — HX711 load cell catches two cards stuck together before they reach the sort gate
- **SQLite inventory** — every sorted card is logged; query counts by set, rarity, or any field
- **Flask web UI** — live sort stats, full inventory viewer, rules editor, and manual overrides at `http://<pi-ip>:5000`
- **9 output bins** — all 3D-printed, designed for Bambu P1S (all parts fit 256×256mm bed; rails split to 2×190mm pieces)

---

## Hardware

| Component | Purpose | Est. Cost |
|-----------|---------|-----------|
| Raspberry Pi Zero 2W | Brain | ~$15 |
| Pi Camera Module 3 | Card identification | ~$25 |
| PCA9685 16-ch PWM driver (I2C) | Servo control | ~$5 |
| 3× MG996R servos | Pickup arm, deflect gate, bin select | ~$15 |
| HX711 + 50g load cell | Double-pick detection | ~$5 |
| 5V relay + 12V vacuum pump | Suction card pickup | ~$20 |
| L9110S motor driver + 2× N20 gear motors | Conveyor belt | ~$10 |
| 9× 3D-printed output bins + frame | Card output | ~$8 filament |
| Misc (wiring, connectors, hardware) | — | ~$10–$55 |

**Total: ~$105–155 USD + filament**

3D print files are in `cad/`. All parts fit a 256×256mm print bed; the two conveyor rails each split into 190mm halves.

---

## Quick Start

### 1. Flash the Pi

Use Raspberry Pi OS Lite (64-bit). Enable I2C, SPI, and the camera interface in `raspi-config`.

### 2. Run setup script

```bash
git clone https://github.com/yourname/riftbound-sorter
cd riftbound-sorter
bash scripts/setup.sh
```

This enables I2C/camera interfaces, installs all system and Python dependencies (including `avahi-daemon` for mDNS), sets the hostname to `riftbound-sorter`, and installs/enables the systemd service.

### 3. Sync card database

Downloads card images from Riftcodex and builds the local perceptual-hash index (requires internet, ~10–20 min depending on set size):

```bash
source venv/bin/activate
python main.py --build-db
```

### 4. Calibrate camera crop

Place a card in the scanner station and run the interactive calibration:

```bash
python scripts/calibrate_camera.py
```

This saves `config/camera_crop.json`. Skip if the default crop region (120, 80, 520, 620) works for your setup.

### 5. Configure sort rules

`config/rules.json` ships with sensible defaults (Champion/Spell/Follower/Equipment by type, then by rarity). Edit it directly or use the web Rules Editor. No copy step needed.

### 6. Run

```bash
sudo systemctl start riftbound-sorter
```

Or run manually:

```bash
python main.py           # normal sort run
python main.py --dry-run # identify without moving cards
```

Web UI is available at `http://riftbound-sorter.local:5000` or `http://<pi-ip>:5000`.

### Development (non-Pi machine)

Set `MOCK_HARDWARE=1` to stub all GPIO/camera/I2C calls. Combine with `--dry-run` to exercise the full pipeline without any hardware:

```bash
MOCK_HARDWARE=1 python main.py --dry-run
MOCK_HARDWARE=1 python main.py --web-only
```

### Estimated time from unboxing to first sorted card

Assuming all parts are already in hand:

| Step | Time |
|------|------|
| 3D print all parts (Bambu P1S) | 6–12 h |
| Mechanical assembly & wiring | 2–3 h |
| Pi OS flash + `setup.sh` | 30 min |
| `--build-db` (first card sync) | 10–20 min |
| Camera calibration | 15–30 min |
| Load-cell calibration | 10 min |
| **Total** | **~10–16 h** (mostly print time) |

Parts not in hand yet: add 1–3 days for domestic shipping.

---

## Wiring Overview

```
Pi Zero 2W
├── I2C (GPIO 2/3) ──── PCA9685
│                           ├── CH0 ── MG996R (pickup arm)
│                           ├── CH1 ── MG996R (deflect gate)
│                           └── CH2 ── MG996R (bin select)
│
├── GPIO 5 / GPIO 6 ─── HX711 (DOUT / SCK)
│                           └── 50g load cell
│
├── GPIO 17 ──────────── 5V relay ──── 12V vacuum pump
│
└── I2C shared ──────── L9110S
                            ├── Motor A ── N20 conveyor left
                            └── Motor B ── N20 conveyor right

Pi Camera Module 3 ─── CSI ribbon
```

I2C addresses: PCA9685 at `0x40`, L9110S at `0x60` (check with `i2cdetect -y 1`).

Full KiCad schematic: `riftbound_sorter.kicad_sch`

---

## Rules Engine

Sort logic lives in `config/rules.json`. Each rule has a list of conditions and a target bin (0–8). Rules are evaluated in order; first match wins.

**Example `config/rules.json`:**

```json
{
  "default_bin": 8,
  "rules": [
    {
      "name": "Champions to bin 0",
      "conditions": [
        { "field": "type", "op": "eq", "value": "Champion" }
      ],
      "bin": 0
    },
    {
      "name": "Rare and above to bin 1",
      "conditions": [
        { "field": "rarity", "op": "in", "value": ["Rare", "Epic", "Legendary"] }
      ],
      "bin": 1
    },
    {
      "name": "Bilgewater commons to bin 2",
      "conditions": [
        { "field": "region", "op": "eq", "value": "Bilgewater" },
        { "field": "rarity", "op": "eq", "value": "Common" }
      ],
      "bin": 2
    }
  ]
}
```

Available card fields mirror the Riftcodex API response: `type`, `rarity`, `region`, `set`, `cost`, `name`, and any other top-level metadata fields.

Edit rules live in the web UI without restarting the sorter.

---

## Web UI

Served by Flask on port 5000.

| Page | Path | Description |
|------|------|-------------|
| Dashboard | `/` | Live sort rate, cards per bin, hopper-empty alert |
| Inventory | `/inventory` | Full sorted card log by card ID and name |
| Rules Editor | `/rules` | Edit and save sort rules as JSON in-browser |
| Export | `/export` | Download full inventory as CSV |

---

## Project Structure

```
riftbound-sorter/
├── main.py              # Entry point
├── requirements.txt
├── riftbound_sorter.kicad_sch
├── api/                 # Riftcodex API client
├── cad/                 # 3D print files (.3mf / .stl)
├── config/              # rules.json, settings.json
├── hardware/            # Servo, motor, relay, HX711 drivers
├── scripts/             # sync_cards.py, calibrate.py, etc.
├── sorter/              # Core sort logic and rules engine
├── vision/              # Camera capture and perceptual hash matching
└── web/                 # Flask app, templates, static assets
```

---

## Development Status

- [x] Card identification via perceptual hashing
- [x] Riftcodex sync and local hash index
- [x] Servo control via PCA9685
- [x] Conveyor belt control
- [x] HX711 double-pick detection
- [x] Vacuum pump / relay sequencing
- [x] Rules engine (JSON)
- [x] SQLite inventory logging
- [x] Flask web UI (dashboard, inventory, rules editor, CSV export)
- [x] `MOCK_HARDWARE` mode for dev without Pi
- [ ] Full mechanical assembly and physical calibration (hardware needed)
- [ ] Inventory filter by set/rarity/type in web UI (deferred to v0.2)
- [ ] Camera crop live-preview in web UI (deferred to v0.2)

---

## License

MIT
