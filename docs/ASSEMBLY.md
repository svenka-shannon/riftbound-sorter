# Riftbound Card Sorter — Assembly Guide

## Table of Contents

1. [Parts Checklist](#1-parts-checklist)
2. [Print Order](#2-print-order)
3. [Electronics Assembly](#3-electronics-assembly)
4. [Mechanical Assembly](#4-mechanical-assembly)
5. [First-Time Setup](#5-first-time-setup)
6. [Calibration Checklist](#6-calibration-checklist)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Parts Checklist

### Electronics BOM

| Qty | Component | Notes |
|-----|-----------|-------|
| 1 | Raspberry Pi 4 (2 GB or 4 GB) | Pi 4B recommended; Pi 5 not yet tested |
| 1 | PCA9685 16-channel PWM/Servo driver | I2C, 5 V logic |
| 1 | HX711 load-cell amplifier module | 24-bit ADC |
| 1 | Single-point load cell (0–500 g) | Matched to HX711 |
| 1 | Relay module, 5 V coil (1- or 2-channel) | Controls suction pump |
| 1 | L9110S dual H-bridge motor driver | For N20 conveyor motor |
| 2 | N20 gear-motor 6 V, 100–300 RPM | Conveyor drive + roller return |
| 4–6 | MG90S or SG90 micro-servo | Suction arm axes + bin gate |
| 1 | Camera Module v2 or HQ Camera | CSI ribbon interface |
| 1 | LM2596 step-down buck converter | 12 V → 5 V regulated rail |
| 1 | 12 V DC power supply (≥ 3 A) | Wall adapter or bench PSU |
| 1 | DC barrel jack (5.5 × 2.1 mm) | Panel mount or PCB |
| 1 | Micro-USB or USB-C cable (Pi power) | Must support 3 A |
| 1 | 40-pin GPIO header ribbon (optional) | If soldering breakout board |
| 1 | Breadboard or custom PCB | For power/signal distribution |
| — | M2 / M3 hardware (screws + nuts) | Assorted lengths |
| — | Dupont jumper wires, 20 cm | Male–male and male–female |
| — | Heat-shrink tubing assortment | For power wires |
| — | 22 AWG stranded wire (red/black) | Power runs |
| — | 26 AWG stranded wire (multi-color) | Signal runs |

### 3D Printed Parts

Print all parts in PETG (preferred) or PLA. Layer height 0.2 mm; 3 perimeters; 20 % infill unless noted.

| Qty | Filename | Material note |
|-----|----------|---------------|
| 4–8 | `baseplate_tile.stl` | 40 % infill — structural |
| 8–16 | `bin_body.stl` | Standard |
| 2 | `bin_lid.stl` | Optional |
| 2 | `conveyor_rail_left.stl` | 40 % infill |
| 2 | `conveyor_rail_right.stl` | 40 % infill |
| 1 | `scanner_hood.stl` | Black filament — reduces reflections |
| 1 | `suction_arm_base.stl` | 40 % infill |
| 1 | `suction_arm_elbow.stl` | Standard |
| 1 | `suction_arm_wrist.stl` | Standard |
| 1 | `hopper_body.stl` | Standard |
| 1 | `hopper_gate.stl` | Standard |
| 1 | `electronics_tray.stl` | Standard |
| 1 | `motor_mount.stl` | 40 % infill |
| 1 | `camera_bracket.stl` | Standard |

---

## 2. Print Order

Print in this order so sub-assemblies are ready when needed during mechanical assembly:

1. **Baseplate tiles** (`baseplate_tile.stl` × N) — long print; start overnight.
2. **Bins** (`bin_body.stl`, `bin_lid.stl`) — many copies; batch on the build plate.
3. **Conveyor rails** (`conveyor_rail_left.stl`, `conveyor_rail_right.stl`) — must be dimensionally accurate; print at 0.15 mm layer height.
4. **Electronics tray** (`electronics_tray.stl`) — needed before electronics work begins.
5. **Motor mount** (`motor_mount.stl`) — pair with rails.
6. **Hopper body + gate** (`hopper_body.stl`, `hopper_gate.stl`).
7. **Scanner hood** (`scanner_hood.stl`) — use black filament; print before camera work.
8. **Suction arm** (`suction_arm_base.stl`, `suction_arm_elbow.stl`, `suction_arm_wrist.stl`) — last, because servo dimensions must be confirmed first.
9. **Camera bracket** (`camera_bracket.stl`) — small; print while arm is printing.

---

## 3. Electronics Assembly

> **Safety first.** Work with the power supply unplugged throughout assembly. Only plug in to test a completed, double-checked stage.

### 3a. Power Supply Wiring — 12 V In → LM2596 → 5 V Rail

```
Wall adapter (12 V DC)
  └─ Barrel jack
       ├─ 12 V+ ──► LM2596 IN+
       └─ GND   ──► LM2596 IN-  ──► common GND bus

LM2596 OUT+ ──► 5 V rail (powers Pi, PCA9685, servos, relay)
LM2596 OUT- ──► common GND bus
```

1. Solder 22 AWG red wire to the barrel jack center pin; black to the sleeve.
2. Connect 12 V+ to LM2596 `IN+` and GND to `IN-`.
3. Before connecting any load, adjust the LM2596 trim pot while measuring `OUT+`/`OUT-` with a multimeter. Dial in **5.1–5.2 V**.
4. The 12 V rail feeds the L9110S motor driver and relay `COM` directly. Label these wires.
5. Use a common GND bus (breadboard rail or terminal block) shared by all modules.

### 3b. Raspberry Pi + PCA9685 I2C Connection

```
Pi GPIO header               PCA9685 board
  Pin 1  (3.3 V) ──────────► VCC
  Pin 6  (GND)   ──────────► GND
  Pin 3  (SDA1)  ──────────► SDA
  Pin 5  (SCL1)  ──────────► SCL
  5 V rail       ──────────► V+ (servo power)
```

1. Connect the four I2C wires (VCC, GND, SDA, SCL) between the Pi header and PCA9685.
2. Connect the 5 V rail to PCA9685 `V+` to power servo rails. Do **not** use Pi 5 V pin for servo power — draw too high.
3. Verify with `i2cdetect -y 1` after first boot. PCA9685 default address is `0x40`.
4. If chaining a second PCA9685, bridge `A0` solder jumper → address `0x41`.

### 3c. HX711 + Load Cell Wiring (4-Wire)

Load cells have four wires. Standard color coding (confirm with your cell's datasheet):

| Wire color | Load cell terminal | HX711 pin |
|------------|--------------------|-----------|
| Red        | E+ (excitation +)  | E+        |
| Black      | E- (excitation -)  | E-        |
| White      | A+ (signal +)      | A+        |
| Green      | A- (signal -)      | A-        |

```
HX711 board        Pi GPIO header
  VCC ──────────► Pin 1  (3.3 V)
  GND ──────────► Pin 9  (GND)
  DT  ──────────► Pin 29 (GPIO 5)
  SCK ──────────► Pin 31 (GPIO 6)
```

1. Solder or clamp load cell wires to the HX711 `E+/E-/A+/A-` terminals.
2. Run the four-wire ribbon through the electronics tray cable channel before mounting.
3. Note the GPIO pins for `DT` and `SCK` — they must match `config.yaml` `hx711.dt_pin` and `hx711.sck_pin`.

### 3d. Relay Module

The relay switches 12 V power to the suction/vacuum pump.

```
Relay board        Pi GPIO header
  VCC ──────────► Pin 4  (5 V)
  GND ──────────► Pin 6  (GND)
  IN  ──────────► Pin 11 (GPIO 17)

Relay COM ──────► 12 V+
Relay NO  ──────► Pump + terminal
Pump -    ──────► GND
```

1. Use the **Normally Open (NO)** relay terminal — pump is off when Pi GPIO is LOW.
2. Double-check the relay coil voltage matches your module (5 V coil is standard).
3. Twist the 12 V pump wires and keep them away from I2C/signal wires to reduce noise.

### 3e. L9110S + N20 Motors

The L9110S drives up to two N20 motors (conveyor drive + roller return).

```
L9110S board       Pi GPIO header
  VCC ──────────► 5 V rail (or 6–12 V rail if motors need it)
  GND ──────────► common GND
  A-IA ─────────► Pin 33 (GPIO 13) — Motor A forward
  A-IB ─────────► Pin 35 (GPIO 19) — Motor A reverse
  B-IA ─────────► Pin 37 (GPIO 26) — Motor B forward
  B-IB ─────────► Pin 38 (GPIO 20) — Motor B reverse

L9110S OA1/OA2 ──► N20 Motor A terminals
L9110S OB1/OB2 ──► N20 Motor B terminals
```

1. If N20 motors are rated 6 V, connect L9110S `VCC` to the 12 V rail with a separate 6 V buck converter, or use 5 V for reduced speed.
2. Motor polarity determines direction — swap the two motor output wires if the conveyor runs backward.
3. PWM pins allow speed control from software. GPIO 13, 19 are hardware PWM on Pi 4.

### 3f. All Servos to PCA9685

Connect servo signal wires to PCA9685 channels:

| PCA9685 Channel | Servo function          |
|-----------------|------------------------|
| 0               | Suction arm — shoulder |
| 1               | Suction arm — elbow    |
| 2               | Suction arm — wrist / Z |
| 3               | Bin gate — left side   |
| 4               | Bin gate — right side  |
| 5–15            | Reserved / expansion   |

Each servo connector is three-wire: **GND (brown/black), 5 V (red), signal (orange/yellow/white)**.

1. Plug each servo into the corresponding PCA9685 header column. Signal wire goes to the innermost pin (toward the board edge labeled `S`).
2. All servo GND and 5 V come from the PCA9685 rail — do **not** use Pi GPIO for servo power.
3. After wiring, confirm channel mapping matches `config.yaml` `servos` block before powering.

### 3g. Camera CSI Ribbon

1. Locate the Camera Serial Interface (CSI) connector between the HDMI ports on the Pi 4 (labeled `CAMERA`).
2. Lift the plastic latch on the CSI connector gently — it slides upward.
3. Insert the ribbon cable with the **blue side facing the HDMI ports** (contacts face away from the latch).
4. Press the latch down firmly until it clicks.
5. Route the ribbon through the camera bracket slot before attaching the camera module.
6. Verify detection after first boot: `libcamera-hello --list-cameras` should show `imx219` or the HQ camera sensor.

---

## 4. Mechanical Assembly

Assemble in this order to avoid back-tracking:

### Step 1 — Baseplate

1. Lay out all baseplate tiles on a flat surface and click/bolt them together.
2. Fasten the joined tiles to a flat backing board (MDF or acrylic) with M3 × 8 mm screws from below.
3. Verify the surface is flat — place a ruler across tiles. Any gap > 0.5 mm will cause card misfeeds.

### Step 2 — Electronics Tray

1. Snap the electronics tray into the baseplate tile cutout designated for it.
2. Mount the following components to the tray using M2.5 standoffs or hot glue (use standoffs for serviceability):
   - Raspberry Pi 4
   - PCA9685
   - HX711
   - L9110S
   - Relay module
   - LM2596 buck converter
3. Route all power wires along the tray channels before connecting.
4. Leave signal wires loose for now — route after rails are in place.

### Step 3 — Conveyor Rails

1. Insert the two N20 motors into their motor mounts.
2. Slot each motor mount into the left and right conveyor rails.
3. Clip the rails onto the baseplate's rail guide pins. Rails should click firmly — no rocking.
4. Thread the conveyor belt (or timing belt) over the motor drive pulleys and idler rollers.
5. Tension by sliding the idler roller until the belt deflects ~2 mm under light finger pressure.
6. Secure the motor mount screws (M3 × 10 mm).

### Step 4 — Hopper

1. Slide the hopper body onto the inlet end of the conveyor rails until the locating tabs engage.
2. Insert the hopper gate servo (PCA9685 channel 3 or 4) into its slot on the hopper body.
3. Attach the servo horn to the gate arm with the supplied horn screw.
4. Set the servo to its center position (90°) before fixing the horn so the gate is half-open at rest.

### Step 5 — Suction Arm

1. Press the shoulder servo into the suction arm base and secure with M2 × 8 mm screws.
2. Attach the elbow servo to the arm elbow section; route servo cable through the arm channel.
3. Attach the wrist servo to the wrist section; press-fit the suction cup mount.
4. Connect suction tubing from the vacuum pump (mounted separately or on the tray) through the arm tubing channel to the suction cup.
5. Mount the completed arm onto the baseplate arm post using two M3 × 16 mm bolts.
6. Plug each servo into its PCA9685 channel (shoulder → ch0, elbow → ch1, wrist → ch2).

### Step 6 — Scanner Hood

1. Position the scanner hood over the scanning zone of the conveyor.
2. Mount the camera bracket inside the hood's top cutout; secure with M2.5 screws.
3. Route the CSI ribbon through the hood's rear cable slot.
4. Attach the camera module to the bracket; lock the CSI ribbon as described in 3g.
5. Clip the scanner hood onto the baseplate hood posts. It should be removable for cleaning.

### Step 7 — Load Cell + Weigh Platform

1. Mount the load cell between the lower mounting plate and the upper weigh platform using M3 bolts — do not overtighten (torque to hand-tight + 1/4 turn only).
2. Seat the weigh platform in the designated tray cutout so cards land flat on it.
3. Route the load cell cable to the HX711 on the electronics tray.

### Step 8 — Bins

1. Snap or slide each bin body into its row slot on the baseplate.
2. Connect the bin gate servo horn links if your design uses them.
3. Confirm each bin can be removed individually without lifting the entire assembly.

---

## 5. First-Time Setup

### 5a. Flash Pi OS

1. Download Raspberry Pi OS Lite (64-bit) from raspberrypi.com/software.
2. Flash to a microSD card (≥ 16 GB, Class 10 / A1) using Raspberry Pi Imager.
3. In Imager advanced settings (gear icon):
   - Enable SSH
   - Set hostname: `riftbound.local`
   - Set username/password
   - Configure Wi-Fi SSID + password (or leave blank for Ethernet)
4. Insert card, power on Pi, and SSH in: `ssh <user>@riftbound.local`

### 5b. Run setup.sh

```bash
git clone https://github.com/your-org/riftbound-sorter.git
cd riftbound-sorter
chmod +x setup.sh
sudo ./setup.sh
```

`setup.sh` will:
- Install system packages (`python3`, `libcamera`, `i2c-tools`, etc.)
- Enable I2C, SPI, and Camera interfaces via `raspi-config nonint`
- Create a Python virtual environment and install `requirements.txt`
- Install and enable the `riftbound.service` systemd unit
- Copy `config.yaml.example` to `config.yaml` if not present

### 5c. Build the Card Database

```bash
cd ~/riftbound-sorter
python main.py --build-db
```

This downloads card image data and builds the local SQLite database used for identification. Requires internet access. Typical run time: 5–15 minutes depending on set size.

### 5d. Calibrate Hardware

```bash
python main.py --calibrate
```

Interactive calibration wizard covers:
- Load cell zero (tare with empty weigh platform)
- Servo angle limits for each axis
- Conveyor speed (cards per minute)
- Camera exposure/white balance lock

### 5e. Calibrate Camera

```bash
python calibrate_camera.py
```

Prints a checkerboard calibration sheet (or use the included PDF), hold it in the scanner zone, and follow on-screen prompts. Produces `camera_calibration.npz` used by the vision pipeline.

---

## 6. Calibration Checklist

Run through this checklist after first assembly and again after any mechanical change:

### Load Cell Zero

- [ ] Remove all weight from the weigh platform.
- [ ] Run `python main.py --calibrate` and select **Tare load cell**.
- [ ] Place a known weight (e.g., 100 g calibration mass) and confirm readout is within ±2 g.
- [ ] Update `config.yaml` `scale.calibration_factor` if drift exceeds ±5 g.

### Servo Angle Tuning

- [ ] With `--calibrate` wizard, jog each servo and record minimum and maximum safe angles.
- [ ] Verify arm reaches the weigh platform without binding.
- [ ] Verify arm reaches each bin entry point.
- [ ] Update `config.yaml` `servos.ch0.min_angle` / `max_angle` (and same for ch1, ch2, ch3, ch4).
- [ ] Confirm suction cup aligns with card center at pick height; adjust `servos.ch2.pick_angle`.

### Camera Crop

- [ ] Run `calibrate_camera.py --preview` to open a live preview window (requires display or VNC).
- [ ] Confirm the crop rectangle (`config.yaml` `camera.crop_x`, `crop_y`, `crop_w`, `crop_h`) captures the full card face with < 5 px margin wasted.
- [ ] Ensure no shadow from the arm falls inside the crop rectangle during a simulated pick cycle.

### Conveyor Speed

- [ ] Place a single card in the hopper and run `python main.py --test-conveyor`.
- [ ] Measure time from hopper gate open to card reaching the weigh platform.
- [ ] Target: 0.8–1.2 seconds per card. Adjust `config.yaml` `conveyor.speed_pwm` (0–100).
- [ ] Confirm no double-feeds: run 10 cards and check that each stops on the weigh platform cleanly.

---

## 7. Troubleshooting

### Card Jams

**Symptom:** Card stops mid-conveyor or folds under the belt.

| Likely cause | Fix |
|---|---|
| Belt tension too high | Loosen idler roller; re-tension to 2 mm deflection |
| Belt tension too low | Cards slip under drive pulley — increase tension |
| Hopper gate opens too wide | Reduce `servos.ch3.open_angle` by 5° increments |
| Card burrs from cutting | Lightly sand card edges; check hopper alignment |
| Conveyor speed too fast | Reduce `conveyor.speed_pwm` by 10 and retest |

### Double Picks (Two Cards at Once)

**Symptom:** Weight reading is ~2× a single card; identification fails.

| Likely cause | Fix |
|---|---|
| Hopper gate opens too long | Reduce `conveyor.gate_open_ms` in config |
| Static cling between cards | Wipe cards with anti-static cloth; add a separator rib to hopper |
| Suction too strong | Add a bleed valve to tubing; reduce vacuum pump duty cycle |
| Cards not fanned in hopper | Fan cards before loading; add a ridged hopper insert |

### Misidentification

**Symptom:** Card is identified as the wrong card or marked as unknown.

| Likely cause | Fix |
|---|---|
| Poor lighting — glare | Reposition the LED strip inside the hood; use diffusion foam |
| Camera out of focus | Adjust camera lens ring; re-run `calibrate_camera.py` |
| Crop region too small | Increase `camera.crop_w` and `crop_h`; re-run calibration |
| Database out of date | Re-run `python main.py --build-db` to pull latest card data |
| Foil/holo cards | Increase `vision.match_threshold` tolerance in config (try 0.70 → 0.60) |
| Card face dirty | Clean cards; inspect hood for dust contamination |

### Web UI Not Loading

**Symptom:** Browser shows "connection refused" or times out at `http://riftbound.local:5000`.

1. SSH in and check service status:
   ```bash
   sudo systemctl status riftbound.service
   ```
2. If the service is failed, view logs:
   ```bash
   journalctl -u riftbound.service -n 50
   ```
3. Common causes:
   - **Port 5000 blocked** — check `sudo ufw status`; run `sudo ufw allow 5000/tcp`
   - **Flask startup error** — look for a Python traceback in the journal; usually a missing `config.yaml` key
   - **Service not enabled** — run `sudo systemctl enable --now riftbound.service`
   - **Wrong IP/hostname** — try `http://<Pi IP address>:5000` if mDNS is unreliable on your network
4. Restart the service after any fix:
   ```bash
   sudo systemctl restart riftbound.service
   ```

### Suction Arm Not Picking Cards

**Symptom:** Arm descends but card is not lifted; card falls off mid-transfer.

| Likely cause | Fix |
|---|---|
| Pump not activating | Check relay LED; verify GPIO 17 is toggled with `raspi-gpio get 17` |
| Tubing leak | Pinch tubing at cup — if suction improves, find and seal the leak |
| Cup not seating on card | Adjust `servos.ch2.pick_angle` by ±2° increments; re-run calibration |
| Cup worn or cracked | Replace suction cup (5 mm diameter silicone cup) |
| Card too textured | Increase pump duty cycle or try a larger cup diameter |

---

*End of Assembly Guide*
