# Riftbound Card Sorter — Assembly Guide

## Table of Contents

1. [Parts Checklist](#1-parts-checklist)
2. [Print Order](#2-print-order)
2b. [Pre-Assembly: Heat-Set Inserts](#2b-pre-assembly-heat-set-inserts)
3. [Electronics Assembly](#3-electronics-assembly)
4. [Mechanical Assembly](#4-mechanical-assembly)
5. [First-Time Setup](#5-first-time-setup)
6. [Calibration Checklist](#6-calibration-checklist)
7. [Troubleshooting](#7-troubleshooting)

> **Open design items (read before printing).** These are not yet defined in the CAD, so the matching steps below are marked **STOP** or **PENDING**:
> - **Suction arm post** (Step 2b): no part, no BOM line and no fastening exist yet.
> - **608ZZ bearing seat** (Step 3c): `conveyor_rail.scad` adds a solid Ø22.3 × 7.2 mm boss with only the Ø8.2 mm shaft hole through it. There is no 22 mm pocket for the bearing.
> - **Roller D-key** (Step 3a): `conveyor_roller.scad` subtracts the D-key block from the roller body, not from the bore. That cuts a 16.4 mm-wide slot along the whole roller (a cross-section at Z = 30 shows a C-shape). Do not print `conveyor_roller.stl` until this is fixed.
> - **Gate-lever servo mounts** (Step 8b): there is no bracket for the ch1/ch2 servos.
> - **Hopper fastening** (Step 4): `hopper.scad` has no locating tabs or screw holes.
> - **Rod length** (Step 3d): **PENDING motor-mount integration.**

---

## 1. Parts Checklist

### Electronics BOM

| Qty | Component | Notes |
|-----|-----------|-------|
| 1 | Raspberry Pi Zero 2W | 22-pin mini CSI connector; micro-USB power; 40-pin GPIO |
| 1 | PCA9685 16-channel PWM/Servo driver | I2C, 3.3 V logic; servo power only via the `V+` screw terminal |
| 1 | HX711 load-cell amplifier module | 24-bit ADC |
| 1 | Single-point load cell (0–500 g) | Matched to HX711 |
| 1 | Relay module, 5 V coil, 1-channel, **active-LOW** input | Switches the 12 V pump (IN LOW = relay ON) |
| 1 | 10 kΩ resistor, ¼ W | Pull-up GPIO 17 → 3.3 V so a floating pin means pump OFF (§3d) |
| 1 | L9110S dual H-bridge motor driver | Drives both N20 conveyor motors |
| 2 | N20 gear-motor 6 V, 200 RPM | One per roller. Both rollers are driven (`hardware/conveyor.py` motor A + B) |
| 3 | MG996R servo | ch0 pickup arm, ch1 deflect gate, ch2 bin select (`hardware/servos.py`) |
| 1 | Pi Camera Module 3 | Standard 15-pin CSI; use the Pi Zero CSI adapter cable (22-pin mini ↔ 15-pin standard) |
| 1 | 5 V regulator #1, **fixed output**: Pololu D24V22F5 (5 V 2.5 A) | Pi + logic rail (§3a) |
| 1 | 5 V regulator #2, **fixed output**: Pololu D24V50F5 (5 V 5 A) | Servo rail. Feeds the PCA9685 `V+` terminal only (§3a) |
| 1 | 12 V DC power supply (≥ 3 A) | Wall adapter |
| 1 | DC barrel jack (5.5 × 2.1 mm) | Panel mount, centre-positive |
| 1 | Micro-USB cable | **Bench testing only.** In the machine the Pi is powered from regulator #1. Never connect both at once. |
| 1 | Breadboard or terminal block | Common GND bus |
| — | Dupont jumper wires, 20 cm | Male–male and male–female |
| — | Heat-shrink tubing assortment | For power wires |
| — | 22 AWG stranded wire (red/black) | Power runs |
| — | 26 AWG stranded wire (multi-color) | Signal runs |

### Mechanical Hardware

| Qty | Item | Used in |
|-----|------|---------|
| 4 | 608ZZ bearing (8 ID × 22 OD × 7 mm) | One per rail boss (Step 3c) |
| 2 | 8 mm steel rod, 150 mm stock, **cut to 136 mm** | Roller axles (Step 3d). Length math in `BOM.md`. **PENDING motor-mount integration** |
| 2 | Shaft collar, 8 mm bore, set-screw type (typ. Ø16 × 8 mm, M4 set screw) | Plain-rail end of each rod (Step 3d) |
| 2 | Shaft coupling 3 mm ↔ 8 mm, D19 × L25 | N20 shaft → rod (Step 3e, per `motor_mount.scad`) |
| 8 | #010 O-ring (16 mm ID × 2 mm) | 4 per roller (Step 3d) |
| 4 | M3 brass heat-set insert (for a Ø4.0–4.2 mm hole) | Motor-side rail pads (Section 2b) |
| 4 | M3 × 10 button-head (BHCS) | Motor mount → rail inserts (Step 3e) |
| 4 | M1.6 × 4 pan-head | N20 gearbox face → motor mount face plate (Step 3e) |
| 8 | M3 countersunk (ISO 10642) + nut + washer, length per Step 8a | Sorting tray lower floor → baseplate |
| 8 | M3 × 12 countersunk (ISO 10642) | Sorting tray stacking, self-tapping into bosses (Step 8a) |
| 8 | M3 × 12 + nut | Gate levers → servo horns (Step 8b) |
| 4 | M3 × 16 + nut | Suction arm → servo horn (Step 5) |
| 2 | M3 + nut + washer, length per Step 6 | Camera bracket foot → baseplate |
| 4 | M2 × 10 self-tapping | Camera PCB → bracket standoffs (Step 6) |
| — | M2.5 standoffs, screws, nuts | PCB mounts in the electronics tray |

### 3D Printed Parts

Print all parts in PETG (preferred) or PLA. Layer height 0.2 mm; 3 perimeters; 20 % infill unless noted. Notes in *italics* come from the part's SCAD header.

| Qty | Part (SCAD source) | Material note |
|-----|--------------------|---------------|
| 4–8 | `baseplate_tile.stl` | 40 % infill — structural |
| 8–16 | `bin_body.stl` | Standard |
| 2 | `bin_lid.stl` | Optional |
| 1 + 1 | Conveyor rail, **motor side** (front, −Y): `rail_half(add_shaft_far=false, motor_mount=true)` + `rail_half(add_shaft_far=true, motor_mount=true)` | 40 % infill. Carries the 4 heat-set insert pads |
| 1 + 1 | Conveyor rail, **plain side** (back, +Y): `rail_half(add_shaft_far=false)` + `rail_half(add_shaft_far=true)`, mirrored | 40 % infill |
| 2 | `conveyor_roller.stl` (`conveyor_roller.scad`) | *PLA, 4 perimeters, 60 % infill, axis vertical.* **STOP: D-key bug, see top of guide** |
| 2 | `motor_mount.stl` (`motor_mount.scad`) | *PETG or PLA, 4 walls, 40 % infill, floor on bed* |
| 1 | `scanner_hood.stl` | Black filament — reduces reflections |
| 1 | `camera_bracket.stl` (`camera_bracket.scad`) | *PLA or PETG, 4 walls, 30–40 % infill, printed on its −X side (`print_orient = true`)* |
| 1 | `suction_arm.stl` (`suction_arm.scad`) | *PETG, 60 % infill.* Single-servo arm (ch0) |
| 1 | `hopper.stl` (`hopper_body()` in `hopper.scad`) | Standard |
| 1 | Hopper gravity sled (`spring_pusher()` in `hopper.scad`) | Standard |
| 1 | `electronics_tray.stl` | Standard |
| 1 | Sorting tray Section A: `tray_floor_section(start_slot=0, is_first=true, is_last=false)` | *PLA, 40 % infill.* Lower floor; pin on right face |
| 1 | Sorting tray Section B: `tray_floor_section(start_slot=2, is_first=false, is_last=true)` | Lower floor; pin hole on left face |
| 1 | Sorting tray Section C: `tray_floor_section(start_slot=4, is_first=true, is_last=false)` | Upper floor; pin on right face |
| 1 | Sorting tray Section D: `tray_floor_section(start_slot=6, is_first=false, is_last=true)` | Upper floor; pin hole on left face |
| 2 | Sorting tray shelf half: `floor_shelf_half()` (identical) | A one-piece 274 mm shelf won't fit the 256 mm bed |
| 2 | `sort_gate_lever.stl` (`sort_gate_lever.scad`) | *PETG, 60 % infill.* One per gate servo (ch1, ch2) |

> **Gate lever quantity = 2.** This matches the servo channels in `hardware/servos.py` (ch1 deflect gate, ch2 bin select; ch3–15 unused) and `gate_lever_x() = [30, 65]` in `assembly.scad`. An earlier `assembly.scad` and the audit (B-20) used 3. If a third gate channel is ever added to `servos.py`, print a third lever.
>
> **Not a printed part:** the suction arm post. See Step 2b.

---

## 2. Print Order

Print in this order so sub-assemblies are ready when needed during mechanical assembly:

1. **Baseplate tiles** (`baseplate_tile.stl` × N) — long print; start overnight.
2. **Bins** (`bin_body.stl`, `bin_lid.stl`) — many copies; batch on the build plate.
3. **Conveyor rails** (4 halves, see table) — must be dimensionally accurate; print at 0.15 mm layer height. Confirm the bearing pocket exists before printing (Step 3c).
4. **Rollers** (`conveyor_roller.stl` × 2) — only after the D-key fix (see top of guide).
5. **Motor mounts** (`motor_mount.stl` × 2) — pair with the rails.
6. **Electronics tray** (`electronics_tray.stl`) — needed before electronics work begins.
7. **Hopper + gravity sled** (`hopper.stl`, `spring_pusher()`).
8. **Scanner hood** (`scanner_hood.stl`) — use black filament.
9. **Camera bracket** (`camera_bracket.stl`).
10. **Suction arm + gate levers** (`suction_arm.stl`, `sort_gate_lever.stl` × 2) — PETG; batch together.
11. **Sorting tray** — Sections A, B, C, D and 2 shelf halves (6 prints; each section is 137 × 98 × 65 mm).

---

## 2b. Pre-Assembly: Heat-Set Inserts

Fit the inserts **before** any part is joined, clipped or screwed down. Once the rails are on the baseplate you can't get the iron square to the pads.

### Which parts have insert holes

A search of every `cad/*.scad` file for insert / heat-set features and 4.0–4.2 mm holes finds exactly one location:

| Part | Holes | Hole spec (SCAD) | Inserts |
|------|-------|------------------|---------|
| Conveyor rail, **motor side** (both halves, `motor_mount = true`) | 2 pads per shaft station × 1 station per half | Ø4.1 mm (`mm_insert_d`), blind, 9.2 mm deep (`mm_insert_depth = wall + boss_h − 1`). Pads are Ø9 mm, 15 mm either side of the shaft and 7.5 mm above it | **4** |

**No other part takes inserts.** Every other M3 hole in the design is a 3.2 mm or 3.4 mm clearance hole (used with a nut) or a deliberate self-tapping pilot (sorting tray Ø2.5 mm, camera bracket Ø1.8 mm M2). **Do not press inserts into clearance holes.** They won't hold and they will split the wall. The plain-side rail has no pads.

### Insert spec

- M3 knurled brass insert sized for a Ø4.0–4.2 mm hole. The rail comment lists two that fit the Ø4.1 hole: Ruthex / CNC Kitchen M3 × 5.7 (Ø4.0 hole) or generic M3 × 5 × 4.5 OD (Ø4.2 hole).
- Length must be under 9.2 mm (the blind hole depth). Both examples are.

### Tool and temperature

- 60 W adjustable soldering iron. An **M3 heat-set insert tip** is strongly recommended. A conical tip works but tends to tilt the insert.
- Rails are PLA (`conveyor_rail.scad` header): **210–220 °C** (the SCAD note says ~220 °C). If you printed the rails in PETG: 230–245 °C.

### Technique

1. Lay the rail half inner-face-down so the pads point straight up. The rails print wide face on the bed, so the pads are already vertical.
2. Set the insert on the hole, small end down, and check it's square.
3. Put the tip into the insert. Let it heat for 3–5 s, then press **straight down with light pressure**. Let the heat do the work and don't twist.
4. Stop when the insert is about 0.3 mm proud of the pad face. Lift the iron straight out.
5. Right away, press the insert flush with a flat metal object (the side of a steel ruler) and hold it for 10–30 s until the plastic sets.
6. Check: an M3 × 10 screw should thread in by hand and the insert must not spin. If an insert went in crooked, reheat it, pull it out with the tip and redo it.

---

## 3. Electronics Assembly

> **Safety first.** Work with the power supply unplugged throughout assembly. Only plug in to test a completed, double-checked stage.

### 3a. Power Supply Wiring — 12 V In → Two Fixed 5 V Regulators

The servos get their **own** 5 V regulator. Three MG996R servos can draw ~2.5 A each at stall. On a shared rail one stalled servo would brown out the Pi and risk SD-card corruption (audit B-12).

```
Wall adapter (12 V, 3 A)
  └─ Panel barrel jack (centre +)
       12 V+ ─┬─► Regulator #1 VIN   (Pololu D24V22F5, fixed 5 V 2.5 A)  — Pi + logic
              ├─► Regulator #2 VIN   (Pololu D24V50F5, fixed 5 V 5 A)    — servos ONLY
              └─► Relay COM          (12 V for the pump, §3d)
       GND ───┴─► common GND bus (terminal block)

Reg #1 VOUT (5 V "logic") ──► Pi pin 2 (5 V)
                         ──► L9110S VCC
                         ──► LED ring / strip +
                         (Pi pin 4 (5 V) then feeds relay VCC, §3d)
Reg #2 VOUT (5 V "servo") ──► PCA9685 V+ screw terminal  (nothing else)

Reg #1 GND, Reg #2 GND, Pi pin 6 (GND), PCA9685 GND terminal,
L9110S GND, relay GND, LED −, pump − ──► common GND bus
```

**Why fixed-output regulators.** No multimeter is available for this build. An adjustable LM2596 module has to be dialled in with a meter before any load is connected. These modules often ship with the pot set to an arbitrary voltage, sometimes near the 12 V input, and that kills a Pi instantly. The Pololu D24V22F5 and D24V50F5 are factory-fixed at 5 V (Pololu spec ±4 %, i.e. 4.8–5.2 V), so there is nothing to set. If you substitute an adjustable module anyway, set it to **5.0–5.2 V with a meter before connecting anything to its output.**

**Current budget.**
- Regulator #1 (2.5 A): Pi Zero 2W ~0.6 A + camera ~0.25 A + LED ~0.5 A + relay coil ~0.08 A + HX711/PCA9685 logic < 0.02 A + 2 × N20 running ~0.3 A ≈ **1.75 A**.
- Regulator #2 (5 A): 3 × MG996R at ~0.5 A moving; one stalled (2.5 A) + two moving ≈ **3.5 A**.

Steps:

1. Solder 22 AWG red wire to the barrel jack centre pin; black to the sleeve.
2. Wire 12 V+ and GND to `VIN` / `GND` of **both** regulators. Leave each regulator's `EN` pin unconnected (the regulator is enabled when EN is left open).
3. **Before connecting any load**, power the two regulators on their own for 30 s. Unplug, then touch-check: nothing should be warm. If anything is hot, recheck polarity.
4. Connect regulator #1 to the **Pi only** (pin 2 = 5 V, pin 6 = GND). Boot the Pi and run `vcgencmd get_throttled`. It must print `throttled=0x0`; any other value means under-voltage. Then connect the rest of the logic loads.
5. Connect regulator #2 `VOUT` to the PCA9685 **`V+` screw terminal** and its `GND` to the PCA9685 `GND` terminal. **Never** tie regulator #1 and regulator #2 outputs together, and never feed `V+` from the Pi's 5 V pins.
6. Use one common GND bus (terminal block) shared by both regulators and all modules.
7. Don't plug the micro-USB cable into the Pi while regulator #1 is connected (back-feeding).

### 3b. Raspberry Pi + PCA9685 I2C Connection

```
Pi GPIO header               PCA9685 board
  Pin 1  (3.3 V) ──────────► VCC   (logic)
  Pin 6  (GND)   ──────────► GND
  Pin 3  (SDA1)  ──────────► SDA
  Pin 5  (SCL1)  ──────────► SCL
Regulator #2 5 V ──────────► V+ screw terminal (servo power, §3a)
```

1. Connect the four I2C wires (VCC, GND, SDA, SCL) between the Pi header and the PCA9685.
2. Servo power comes only from regulator #2 into the `V+` screw terminal. Leave the `V+` pin on the PCA9685's side headers unconnected; it is the same net as the terminal.
3. Verify with `i2cdetect -y 1` after first boot. PCA9685 default address is `0x40`.

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

### 3d. Relay Module + GPIO 17 Pull-Up

The relay switches 12 V to the vacuum pump. The module is **active-LOW**: GPIO 17 LOW = relay ON = pump ON; HIGH = pump OFF (`hardware/vacuum.py`).

```
Relay board        Pi GPIO header
  VCC ──────────► Pin 4  (5 V, from regulator #1 via the Pi rail)
  GND ──────────► Pin 6  (GND)
  IN  ──────────► Pin 11 (GPIO 17)

Pin 17 (3.3 V) ──[ 10 kΩ ]──┬── Pin 11 (GPIO 17)
                            └── Relay IN   (pull-up: floating pin = HIGH = pump OFF)

Relay COM ──────► 12 V+
Relay NO  ──────► Pump + terminal
Pump -    ──────► GND
```

1. Use the **Normally Open (NO)** terminal. With no coil power the pump is disconnected, so a total power cut always stops the pump.
2. **Fit the 10 kΩ pull-up** from 3.3 V (pin 17) to GPIO 17 (pin 11). Solder it at the relay `IN` wire or on the breadboard. Why it's needed: GPIO 17 is a plain input with the SoC's default **pull-down** at boot, after `GPIO.cleanup()` (which `vacuum.deinit()` calls), and whenever no program is driving it. A pulled-down pin reads LOW, and on this relay LOW means **pump ON**. The 10 kΩ overpowers the ~50 kΩ internal pull-down and holds the pin HIGH (≈2.75 V), so the pump stays off.
3. Double-check the relay coil voltage matches your module (5 V coil).
4. Twist the 12 V pump wires and keep them away from I2C/signal wires to reduce noise.
5. **Safe-state check (pump hose disconnected):** power up the machine and watch the relay through the whole boot. The relay LED must stay off and you must hear no click. After boot, `pinctrl get 17` (or `raspi-gpio get 17` on older images) should report level `hi`. If the relay energises or its LED glows with `IN` at 3.3 V, this module needs a 5 V HIGH to turn off and is not safe with a 3.3 V GPIO. Replace it with a module rated for 3.3 V logic.

### 3e. L9110S + N20 Motors

The L9110S drives both N20 motors, one per roller. Pin numbers match `hardware/conveyor.py`.

```
L9110S board       Pi GPIO header
  VCC ──────────► Regulator #1 5 V
  GND ──────────► common GND
  A-1A ─────────► Pin 16 (GPIO 23) — Motor A forward
  A-1B ─────────► Pin 18 (GPIO 24) — Motor A reverse
  B-1A ─────────► Pin 22 (GPIO 25) — Motor B forward
  B-1B ─────────► Pin 37 (GPIO 26) — Motor B reverse

L9110S OA1/OA2 ──► N20 Motor A terminals
L9110S OB1/OB2 ──► N20 Motor B terminals
```

1. The 6 V N20s run from 5 V at somewhat reduced speed/torque.
2. Motor polarity sets direction. Swap the two motor output wires if a roller runs backward. Both rollers must turn so the card moves toward the sorting tray.
3. `conveyor.py` uses `RPi.GPIO` software PWM. Any GPIO works, but use the pins above.
4. At boot and after the program exits, GPIO 23–26 fall back to inputs with default pull-downs. Both L9110S inputs LOW = motor stopped.

### 3f. All Servos to PCA9685

Channel map from `hardware/servos.py`. There are exactly three servos; ch3–15 are unused.

| PCA9685 Channel | Servo function | Default angles (`servos.py`) |
|-----------------|----------------|------------------------------|
| 0 | Pickup arm (single servo) | `PICKUP_ARM_UP` 90° (rest), `PICKUP_ARM_DOWN` 10° (pick) |
| 1 | Deflect gate — floor select | `GATE_LEFT` 30° lower floor (bins 0–3), `GATE_CENTER` 90° reject (bin 9), `GATE_RIGHT` 150° upper floor (bins 4–7) |
| 2 | Bin select — column | `BIN_SELECT_ANGLES` 20 / 55 / 90 / 125° (columns 0–3, same on both floors), 160° reject |
| 3–15 | Unused | — |

Each servo connector is three-wire: **GND (brown/black), 5 V (red), signal (orange/yellow/white)**.

1. Plug each servo into the corresponding PCA9685 header column. The signal wire goes to the pin row marked `PWM`; GND goes to the row marked `GND`.
2. All servo GND and 5 V come from the PCA9685 rail, which is regulator #2 via the `V+` terminal. Never power servos from Pi GPIO.
3. Calibrated angles are stored in `config/servo_calibration.json` by `scripts/calibrate_servos.py` (§6).

### 3g. Camera CSI Ribbon

1. Locate the Camera Serial Interface (CSI) connector on the Pi Zero 2W — it sits near the center edge of the board, opposite the micro-USB port (labeled `CAMERA`). The Pi Zero 2W uses a **22-pin mini** CSI connector; the Pi Camera Module 3 ships with a standard 15-pin ribbon. Connect them with the Pi Zero CSI adapter cable.
2. Lift the plastic latch on the CSI connector gently — it slides upward.
3. Insert the adapter cable's mini (22-pin) end into the Pi Zero CSI connector with the **contacts facing the board** (blue backing faces up). Repeat at the camera end: insert the standard (15-pin) end with contacts facing away from the camera PCB.
4. Press each latch down firmly until it clicks.
5. Route the ribbon through the camera bracket's plate slot before attaching the camera module (Step 6).
6. Verify detection after first boot: `libcamera-hello --list-cameras` should show `imx708` (Pi Camera Module 3).

### 3h. Power-Loss Safe State

What each subsystem does when something goes wrong, assuming the §3d pull-up and the §5f watchdog are in place:

| Event | Vacuum pump | Servos (PCA9685) | Conveyor |
|-------|-------------|------------------|----------|
| 12 V cord pulled / brownout | **OFF.** Relay coil loses power and the NO contact opens | **Limp.** The arm drops under its own weight | Stops |
| Pi kernel hang | Holds its last state until the watchdog reboots the Pi (≤ 15 s). After that the pull-up keeps it **OFF** | PCA9685 keeps outputting the last pulse (servos hold position) until re-initialised | May hold its last level until the watchdog reboot, then stops |
| Sorter stopped normally (`systemctl stop`, Ctrl-C) | OFF (`shutdown()` → `pump_off()`, then pull-up) | `reset_all()`: arm to 90° rest, gate 90°, bin select 90° | Stopped |
| Sorter process killed with `kill -9` | **Can stay ON** if it was on (pins keep their last level). Run `sudo systemctl stop riftbound-sorter`, or reboot | Hold | Can keep running |

Because the arm goes limp on any power cut, **always home the arm before cutting power** (§5g). Make sure nothing that can jam (a card, a finger, a tool) is under the arm's path when power goes off.

---

## 4. Mechanical Assembly

Assemble in this order to avoid back-tracking. Machine coordinates (X along card travel, Y across the belt with +Y toward the electronics tray, Z up from the baseplate underside) are from `cad/assembly.scad`.

### Step 1 — Baseplate

1. Lay out all baseplate tiles on a flat surface and click/bolt them together.
2. Fasten the joined tiles to a flat backing board (MDF or acrylic) with M3 × 8 mm screws from below.
3. Verify the surface is flat — place a ruler across tiles. Any gap > 0.5 mm will cause card misfeeds.

> Several later steps (sorting tray, camera bracket) bolt **through** the 4 mm tiles with a nut underneath. Note your backing board thickness `t_board`; those screws must also pass through the board (drill Ø3.4 mm through the board at each tile hole you use).

### Step 2 — Electronics Tray

1. Snap the electronics tray into the baseplate tile cutout designated for it.
2. Mount the following components to the tray using M2.5 standoffs or hot glue (use standoffs for serviceability):
   - Raspberry Pi Zero 2W
   - PCA9685
   - HX711
   - L9110S
   - Relay module (with the 10 kΩ pull-up, §3d)
   - Regulators #1 and #2. The tray has no standoffs for these; use double-sided foam tape or hot glue, and keep them apart.
3. Route all power wires along the tray channels before connecting.
4. Leave signal wires loose for now — route after rails are in place.

### Step 2b — Suction Arm Post (DESIGN GAP — STOP)

The arm post is **not defined anywhere in the design**:

- `cad/assembly.scad` places the arm pivot at machine X = −270, Y = 0, at Z = 4 + 121 = 125 mm. The only post geometry is `asm_arm_post()`, a plain Ø12 × 121 mm cylinder that the file itself labels *"a 12mm stand-in, not a printed part"*.
- No SCAD file, STL, BOM line, servo mount or fastener exists for a real post.

Leave the area around X = −270, Y = 0 clear. Don't improvise a post: it has to hold the ch0 MG996R so the horn axis lands on the arm's pivot, and that geometry hasn't been designed. This step will be written once the post exists.

### Step 3 — Conveyor Rails, Bearings, Rods and Rollers

Layout from `conveyor_rail.scad` and `assembly.scad`:

- Each rail is two 125 mm halves joined by a tenon/mortise. The tenon is 5 × 3 × 12 mm on the far end of half 1; the mortise is 5.1 × 3.4 × 12.4 mm in the near end of half 2.
- Half 1 carries the near shaft station, 25 mm from the inlet end (`shaft_x1`). Half 2 carries the far shaft station, 100 mm into half 2 (`shaft_x2`), i.e. 225 mm from the inlet. That puts the rods at machine X = −140 and X = +60.
- Each station has a Ø8.2 mm shaft hole (`shaft_dia`) at 15 mm above the rail base (`shaft_y`) and a Ø22.3 × 7.2 mm 608ZZ boss on the outer face.
- Rail inner faces sit at Y = ±45 (`rail_in`), so the gap is **90.0 mm**. Both motors are on the **front (−Y) rail**.

#### 3a. Pre-checks before assembly

1. **STOP — roller D-key.** Open `conveyor_roller.scad` and confirm the D-key block is subtracted from the *bore* (leaving a flat inside the bore), not from the roller body. As of this writing it cuts a 16.4 mm-wide slot along the full 90 mm roller, so the roller is C-shaped. Don't print or fit rollers until this is fixed.
2. **STOP — bearing seat.** Confirm each boss has a 608ZZ pocket (Ø22 × 7 mm, opening on the boss face) in the rail STL. As of this writing the boss is solid with only the Ø8.2 mm hole.
3. **Rod flats.** The roller is keyed to the rod by a D-flat (`conveyor_roller.scad`). With a flat needle file, file a flat about 0.5 mm deep and 4 mm wide (`motor_flat_w`) on each rod:
   - along the 90 mm roller span;
   - along the last 10 mm on the motor side (coupling set-screw seat).

   Leave the rod round where it passes through the bearings.

#### 3b. Dry-fit the rails and measure the gap

1. Join each rail's two halves (tenon into mortise). They should push together by hand; if tight, file the tenon.
2. Stand both rails on the baseplate with their inner faces 90 mm apart and the bosses facing outward. Neither `baseplate_tile.scad` nor `conveyor_rail.scad` has rail-locating pins or mounting holes. The rails are located by the rods, collars and motor mounts. (An earlier version of this guide said "clip onto guide pins"; there is no geometry for that.)
3. Measure each roller's length **L** (nominal `roller_w` = 90.0 mm) with calipers.
4. The design has **zero clearance** (90 mm roller in a 90 mm gap). Set the rail gap **G** at both stations, at shaft height, to **L + 0.5 mm** (about 0.25 mm per side). Check that the two stations agree within 0.3 mm so the rails are parallel.
5. If you'd rather keep G at 90 mm, sand the roller **end faces** instead (sandpaper on a flat surface, figure-8 strokes, keep them square) until L ≤ G − 0.5 mm. Don't sand the rail inner faces; they carry the card-guide groove.
6. **Hole check (before bearings go in).** Push a rod through each rail shaft hole (Ø8.2) and through each roller bore (Ø8.2 nominal, with the D-flat). It should slide by hand. If a hole printed under 8.0 mm, **ream it**: turn an 8.0 mm drill bit by hand or at low speed. Ream the 90 mm roller bore from both ends (the `conveyor_roller.scad` footer specifies this). Never ream through a fitted bearing.

#### 3c. Press in the bearings (after the pocket fix)

1. Four 608ZZ bearings, one per boss. Each rail half has one station, so there are 4 bosses in total.
2. Press each bearing into its boss from the outer face. Use a bench vise with flat wood blocks and push **only on the outer race**. Keep it square and never hammer.
3. A loose bearing gets one drop of CA glue on the outer race (keep glue off the shields). An over-tight pocket: lightly sand the pocket, not the bearing.
4. Re-check that the rod slides through each bearing's inner race.

#### 3d. Rods and rollers

Rod length (full math in `BOM.md`):

- Boss face to boss face: 110.4 mm
- Motor-side protrusion: 15.5 mm (`motor_mount.scad` `rod_protrusion`)
- Plain-side protrusion: 10.0 mm (0.5 mm gap + 8 mm collar + 1.5 mm)
- Total: **≈ 136 mm.** Cut each 150 mm rod to 136 mm with a hacksaw and chamfer the ends.

An uncut 150 mm rod would end at Y ≈ 79.3 on the plain side, 0.7 mm from the electronics tray (starts at Y = 80). **PENDING motor-mount integration.**

1. Stretch 4 × #010 O-rings into each roller's grooves. The grooves sit at 18, 36, 54 and 72 mm along the roller (`roller_w / (n_orings + 1)` = 18 mm spacing). Groove root Ø = 22 − 2 × 1.6 = 18.8 mm, so a seated O-ring stands about 0.4 mm proud of the Ø22 roller.
2. From the **front (motor) rail's** outer face, push the rod through the bearing and the rail hole until about 5 mm shows inside the gap. Keep the filed flat facing the roller's D-key.
3. Hold the roller in the gap, line its D-key up with the rod flat, and slide the rod through the roller.
4. Push on through the back (plain) rail's hole and bearing. Set the rod so it protrudes **15.5 mm** past the front boss face (rod end to boss face).
5. Plain side: slide on a shaft collar. Put a 0.5 mm spacer (feeler gauge or folded paper) between the collar and the boss/bearing face. Push the collar against the spacer, tighten its set screw, then remove the spacer.
6. Spin the roller by hand. It must not rub the rail inner faces. Axial play should be ≤ 0.5 mm.
7. Repeat for the second station.

#### 3e. Motor mounts (per `motor_mount.scad`)

Each motor mount carries one N20 coaxial with a rod on the **outer side of the front rail**. Its flange seats on the boss face and both insert pads (the inserts went in during Section 2b). Order from the SCAD's assembly notes:

1. Slide the N20 into the mount's sleeve from the rear. Screw its gearbox face to the face plate with **2 × M1.6 × 4 pan head**, reaching through the Ø14 flange hole.
2. Push the coupling's 3 mm bore onto the N20 shaft with the set screw on the shaft's D-flat. Leave it loose.
3. With the rod protruding 15.5 mm past the boss face (Step 3d), offer the mount up and slide the coupling's 8 mm bore onto the rod. The rod goes 10 mm into the coupling (`cpl_rod_engage`).
4. Fasten the flange with **2 × M3 × 10 BHCS** into the rail inserts.
5. Tighten both coupling set screws from above through the bay's open top. The 8 mm side goes onto the rod's filed flat.
6. Spin the drive train by hand. It should turn without binding.

> **No belt.** Neither the BOM nor the CAD contains a belt or an idler tensioner. Cards are driven directly by the O-ring rollers. (Earlier versions of this guide described threading and tensioning a belt; disregard that.) `camera_bracket.scad` has a `belt_t` parameter if a flat belt is added later.

### Step 4 — Hopper

1. Place `hopper.stl` at the inlet end of the conveyor, exit slot facing down the belt (+X). In `assembly.scad` it occupies machine X = −262 … −165, Y = −36 … +36.
2. `hopper.scad` has **no locating tabs or screw holes**, so nothing fixes it in place yet (open CAD item). Until that's designed, hold it in position with double-sided foam tape so it can't shift.
3. Drop the gravity sled (`spring_pusher()`) into the channel in the back wall, on top of the card stack.
4. **Singulation is passive.** There is no hopper gate or servo. One card at a time is ensured by the 0.80 mm exit slot (`exit_slot_h`) with its separation wedge, backed up by the load-cell double-pick check (§7).

### Step 5 — Suction Arm

The arm is a single 130 mm lever driven directly by the **ch0** servo (`suction_arm.scad`). There are no elbow or wrist servos.

1. Plug the ch0 servo into the PCA9685 and move it to its rest position (90°):
   ```bash
   python -c "from hardware import servos; servos.init(); servos.reset_all()"
   ```
2. Bolt the arm to the servo horn. The arm has 4 × Ø3.2 holes on a 15 mm circle around the Ø5.2 pivot hole, which is 10 mm from the arm's end. Use **M3 × 16 + nut**: 10 mm arm + ~2.5 mm horn + 2.4 mm nut. Check that your horn has holes at 7.5 mm radius; if its holes are smaller than 3 mm, drill them to 3.0 mm.
3. Press the horn onto the servo spline with the arm in its rest pose and drive the servo's horn screw through the Ø5.2 centre hole.
4. Press the suction cup's barbed fitting into the Ø13.2 hole at the tip (120 mm from the pivot end).
5. Lay the 4 mm tubing in the Ø4.5 channel on the arm's top face. Secure it at 3 points with M2 screws or cable ties (SCAD note). Run the tubing to the pump.
6. **Mounting the servo on the post: STOP.** See Step 2b; the post isn't designed yet.

### Step 6 — Scanner Hood + Camera Bracket

1. Position the scanner hood over the scan zone, straddling the rails at rail-top height. In `assembly.scad` it occupies machine X = −77.5 … −2.5, Y = −47.5 … +47.5, centred on X = −40. The camera looks down through the hood's 25 × 25 mm top cutout. Clip the hood on so it can be lifted off for cleaning. (`scanner_hood.scad` has no fastening features.)
2. **Camera bracket (`camera_bracket.scad`).** Its foot sits on the baseplate behind the back rail and its arm cantilevers over the hood, putting the lens tip 100 mm above the card face (`lens_h`).
   - Fasten the foot through its 2 × Ø3.4 mm holes into the baseplate grid holes at machine **(−50, 75) and (−20, 75)**.
   - Screw length (SCAD: M3 × 12 + nut/washer, which assumes the nut goes straight under the 4 mm tile): foot 6 mm + tile 4 mm + nut 2.4 mm.
   - Because the baseplate is already on its backing board (Step 1), drill Ø3.4 mm through the board and use **M3 × (13 + t_board) rounded up**, with a washer and nut under the board. Example: a 12 mm board needs M3 × 25.
3. Feed the CSI ribbon (camera end) through the plate's 20 × 7 mm slot, then connect it to the camera with the FPC edge facing the plate (§3g).
4. Screw the camera PCB on **lens-down** with **4 × M2 × 10 self-tapping** into the Ø1.8 mm pilots in the standoffs. The pattern is 21 × 12.5 mm, the official Camera Module 3 hole pattern. Snug only; don't crush the PCB.
5. Route the ribbon back to the Pi on the electronics tray.

### Step 7 — Load Cell + Weigh Platform

1. Mount the load cell between the lower mounting plate and the upper weigh platform using M3 bolts — do not overtighten (torque to hand-tight + 1/4 turn only).
2. Seat the weigh platform in the designated tray cutout so cards land flat on it.
3. Route the load cell cable to the HX711 on the electronics tray.

### Step 8a — Sorting Tray (2 floors × 4 slots)

From `sorting_tray.scad`:

- Four sections, each 137 × 98 × 65 mm with 2 slots.
- A shelf made of 2 identical 137 × 98 × 3 mm halves.
- Assembled size: 274 mm wide (5 mm double wall at the A|B and C|D joins) × 133 mm tall (65 + 3 + 65).

`assembly.scad` places the tray at machine X = 85 … 183, Y = −137 … +137, centred on the belt axis. The **open back** of every slot (card entry) faces the belt exit. The label windows face away from the belt. Nothing may block the open backs.

| Piece | Floor | Slots | Joining face | Screw features |
|-------|-------|-------|--------------|----------------|
| A | lower | 0–1 | Ø3.0 pin on right face | 4 countersunk baseplate holes; front-corner bosses with Ø2.5 pilots |
| B | lower | 2–3 | Ø3.2 pin hole on left face | same as A |
| C | upper | 4–5 | Ø3.0 pin on right face | 4 countersunk stacking holes |
| D | upper | 6–7 | Ø3.2 pin hole on left face | 4 countersunk stacking holes |
| Shelf half × 2 | between floors | — | butt joint at the section seam | 4 × Ø3.4 holes each |

1. **Join A + B.** A's Ø3.0 pin sticks out 2.0 mm from its right face at mid-depth (49 mm) and mid-height (32.5 mm). Push it into B's Ø3.2 hole until the faces meet, with the front faces flush.
2. **Position A + B** at the tray location. The countersunk floor holes sit on the baseplate's 30 mm M3 grid at this position:
   - Section-local A: (32, 13), (32, 73), (92, 13), (92, 73)
   - Section-local B: (45, 13), (45, 73), (105, 13), (105, 73)
   - These land on machine X = 110 / 170 and Y = −105, −45, 45, 105.

   Look down each hole; you should see the baseplate hole underneath.
3. **Fasten the lower floor (before the shelf goes on).** Drive **8 × M3 countersunk** from inside the slots, down through the 2.5 mm floor and the 4 mm tile. Drill Ø3.4 mm through the backing board at each hole and fit a washer and nut underneath. Length = 2.5 + 4 + t_board + 2.4 (nut) + ~1, rounded up; e.g. **M3 × 25 for a 12 mm board**.
4. **Lay the two shelf halves** on top: one over A, one over B, with the seam on the section seam. Line each half's 4 × Ø3.4 holes up with the boss pilots below. Section-local positions: x = 6, 64, 73, 131 at y = 5.6, along the front edge.
5. **Join C + D** with the pin (as in step 1) and set them on the shelf: C over A, D over B, fronts flush.
6. **Fasten the upper floor.** Drive **8 × M3 × 12 countersunk** from inside the upper slots' front corners, down through the upper floor (2.5 mm) and shelf (3 mm). They self-tap about 6.5 mm into the Ø2.5 × 12 mm pilots in the lower bosses. Drive slowly and stop as soon as the head seats; over-torquing strips PLA.
7. **Check:** lay a card flat in each lower slot. There's 89.5 mm free in front of the bosses for an 88 mm card. Confirm the open backs line up with the belt exit.

### Step 8b — Sort Gate Levers (× 2)

- **Lever count:** two, one each on **ch1 (deflect gate / floor select)** and **ch2 (bin select / column)**, per `hardware/servos.py`. `assembly.scad` places them on the back rail at `gate_lever_x() = [30, 65]`.
- **Lever geometry:** a 70 × 12 × 6 mm bar with a 40 mm paddle angled at 15°. The Ø5.2 pivot hole is 10 mm from the end, with 4 × Ø3.2 holes on a 15 mm circle around it.
- **Servo mount: STOP.** No bracket for the ch1/ch2 servos exists in the CAD. `assembly.scad` puts each lever flat on top of the back rail with its pivot at machine (x + 6, Y = 38).
- **Print orientation:** the `sort_gate_lever.scad` footer says to mirror the second lever in the slicer, but `assembly.scad` uses two identical levers. Print two identical levers unless the CAD says otherwise.

Horn fastening (do this on the bench now; it doesn't depend on the missing bracket):

1. Plug the servos into ch1 and ch2 and run `servos.reset_all()` (see Step 5). Both go to 90°: `GATE_CENTER` for ch1 and the column-2 angle for ch2.
2. Off the servo, bolt each lever to its horn through the 4 × Ø3.2 holes with **M3 × 12 + nut**: 6 mm lever + ~2.5 mm horn + 2.4 mm nut. If the horn holes are smaller than 3 mm, drill them to 3.0 mm.
3. With the servo at 90°, press the horn and lever onto the spline in the `assembly.scad` pose: lever long axis across the belt (−Y), paddle toward the belt exit. Drive the servo's horn screw through the Ø5.2 centre hole into the spline.
4. Fine-tune the angles with `scripts/calibrate_servos.py` (§6).

### Step 8c — Bins

1. Snap or slide each bin body into its row slot on the baseplate.
2. Confirm each bin can be removed individually without lifting the entire assembly.

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
4. Insert the card and power on. In the machine, power comes from regulator #1 via GPIO pin 2; on the bench, use micro-USB 5 V / 3 A, never both. SSH in: `ssh <user>@riftbound.local`

> **Pi Zero 2W note:** UART is disabled by default. If you need serial/UART (e.g., a USB-serial debug console), add `enable_uart=1` to `/boot/config.txt` before first boot.

### 5b. Run setup.sh

```bash
git clone https://github.com/your-org/riftbound-sorter.git
cd riftbound-sorter
chmod +x scripts/setup.sh
sudo ./scripts/setup.sh
```

`setup.sh` will:
- Install system packages (`python3`, `libcamera`, `i2c-tools`, etc.)
- Enable I2C, SPI, and Camera interfaces via `raspi-config nonint`
- Create a Python virtual environment and install `requirements.txt`
- Install and enable the `riftbound-sorter.service` systemd unit (`scripts/riftbound-sorter.service`)
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

### 5f. Hardware Watchdog

If the Pi hangs, the watchdog reboots it. After the reboot GPIO 17 floats and the §3d pull-up turns the pump off.

1. Enable the watchdog. Add this line to `/boot/firmware/config.txt` (Bookworm; `/boot/config.txt` on older images):
   ```
   dtparam=watchdog=on
   ```
2. Have systemd feed it. In `/etc/systemd/system.conf`, set:
   ```
   RuntimeWatchdogSec=15
   ```
   The Pi's hardware watchdog tops out at about 15 s; larger values are rejected.
3. Reboot, then verify:
   ```bash
   ls /dev/watchdog                         # device exists
   systemctl show | grep RuntimeWatchdog    # RuntimeWatchdogUSec=15s
   dmesg | grep -i watchdog
   ```
4. Optional live test (crashes the kernel on purpose, so save your work first): `echo c | sudo tee /proc/sysrq-trigger`. The Pi should reboot by itself within ~15 s, and the relay must stay off throughout.

### 5g. Power-Off Procedure (Home the Arm First)

The servos go limp the moment power is cut. Always park the machine first:

1. Stop the sorter: `sudo systemctl stop riftbound-sorter`. This sends SIGTERM, and `main.py`'s `shutdown()` then turns the pump off, stops the conveyor and runs `servos.reset_all()`: arm to 90° rest, gate 90°, bin select 90°.
2. If the sorter wasn't running, home the arm by hand:
   ```bash
   cd ~/riftbound-sorter && python -c "from hardware import servos; servos.init(); servos.reset_all()"
   ```
3. Check the arm is at rest, holding no card, and that nothing is under its path.
4. `sudo shutdown -h now`. Wait until the green ACT LED stops blinking, then unplug the 12 V supply.
5. Before the next power-on, check the arm isn't resting on a card or in the conveyor path. If it is, move it to rest by hand, slowly; the servo is unpowered.

---

## 6. Calibration Checklist

Run through this checklist after first assembly and again after any mechanical change:

### Load Cell Zero

- [ ] Remove all weight from the weigh platform.
- [ ] Run `python main.py --calibrate` and select **Tare load cell**.
- [ ] Place a known weight (e.g., 100 g calibration mass) and confirm readout is within ±2 g.
- [ ] Update `config.yaml` `scale.calibration_factor` if drift exceeds ±5 g.

### Servo Angle Tuning

- [ ] Run `python scripts/calibrate_servos.py` and jog each servo (ch0 arm, ch1 deflect gate, ch2 bin select). Positions are saved to `config/servo_calibration.json` and override the defaults in `hardware/servos.py`:
  - ch0 arm: `ARM_UP` 90°, `ARM_DOWN` 10°
  - ch1 gate: `GATE_LEFT` 30°, `GATE_CENTER` 90°, `GATE_RIGHT` 150°
  - ch2 bin select: `BIN_0`–`BIN_7` 20 / 55 / 90 / 125°, `BIN_9_REJECT` 160°
- [ ] Verify the arm reaches the weigh platform without binding.
- [ ] Verify each gate/bin-select position steers a card into the correct tray slot.
- [ ] Confirm the suction cup sits flat on the card at pick height; adjust `ARM_DOWN` (ch0).

### Camera Crop

- [ ] Run `calibrate_camera.py --preview` to open a live preview window (requires display or VNC).
- [ ] Confirm the crop rectangle (`config.yaml` `camera.crop_x`, `crop_y`, `crop_w`, `crop_h`) captures the full card face with < 5 px margin wasted.
- [ ] Ensure no shadow from the arm falls inside the crop rectangle during a simulated pick cycle.

### Conveyor Speed

- [ ] Place a single card in the hopper and run one pick cycle.
- [ ] Measure the time from pickup to the card reaching the scanner. Set `CONVEYOR_TRAVEL_S` in `main.py` (default 1.2 s) to match. `SORT_TRAVEL_S` (default 0.8 s) is the scanner-to-sort-gate time.
- [ ] Confirm no double-feeds: run 10 cards and check that each arrives singly.

---

## 7. Troubleshooting

### Card Jams

**Symptom:** Card stops mid-conveyor or folds.

| Likely cause | Fix |
|---|---|
| Roller rubbing a rail face | Re-check roller end clearance (Step 3b): G − L ≥ 0.5 mm |
| Coupling slipping on rod | Re-tighten the coupling set screw onto the rod's filed flat (Step 3e) |
| Card burrs from cutting | Lightly sand card edges; check hopper alignment |
| Conveyor speed too fast | Lower `DEFAULT_SPEED` in `hardware/conveyor.py` (default 75 %) by 10 and retest |

### Double Picks (Two Cards at Once)

**Symptom:** Weight reading is ~2× a single card; identification fails.

| Likely cause | Fix |
|---|---|
| Hopper exit slot too tall | Slip a single card into the exit slot. If two fit, the slot printed oversize: reprint `hopper.stl` with a smaller `exit_slot_h` (default 0.80 mm) or `sep_wedge_h` adjustment |
| Double-pick threshold mis-set | Recalibrate the load cell, then adjust `WEIGHT_SINGLE_MAX` (default 2.3 g) / `WEIGHT_DOUBLE_MIN` (default 2.8 g) in `hardware/loadcell.py` |
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
   sudo systemctl status riftbound-sorter.service
   ```
2. If the service is failed, view logs:
   ```bash
   journalctl -u riftbound-sorter.service -n 50
   ```
3. Common causes:
   - **Port 5000 blocked** — check `sudo ufw status`; run `sudo ufw allow 5000/tcp`
   - **Flask startup error** — look for a Python traceback in the journal; usually a missing `config.yaml` key
   - **Service not enabled** — run `sudo systemctl enable --now riftbound-sorter.service`
   - **Wrong IP/hostname** — try `http://<Pi IP address>:5000` if mDNS is unreliable on your network
4. Restart the service after any fix:
   ```bash
   sudo systemctl restart riftbound-sorter.service
   ```

### Suction Arm Not Picking Cards

**Symptom:** Arm descends but card is not lifted; card falls off mid-transfer.

| Likely cause | Fix |
|---|---|
| Pump not activating | Check the relay LED. GPIO 17 must go **LOW** to turn the pump on (active-LOW): `pinctrl get 17` |
| Pump runs at boot / won't turn off | The 10 kΩ pull-up on GPIO 17 is missing or open (§3d) |
| Tubing leak | Pinch tubing at cup — if suction improves, find and seal the leak |
| Cup not seating on card | Adjust `ARM_DOWN` (ch0) by ±2° with `scripts/calibrate_servos.py` |
| Cup worn or cracked | Replace suction cup (5 mm diameter silicone cup) |
| Card too textured | Increase pump duty cycle or try a larger cup diameter |

---

*End of Assembly Guide*
