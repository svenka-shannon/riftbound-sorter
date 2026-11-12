# 🃏 Riftbound Card Sorter — BOM v0.3

> Budget: **~$223** (AliExpress where possible) / **~$266** (Amazon + Pololu)
> 3D printed frame — no chassis cost. Printer: Bambu P1S.

## Electronics

| Qty | Part | Purpose | ~Price | Where |
|-----|------|---------|--------|-------|
| 1 | Raspberry Pi Zero 2W | Brain + WiFi | $15 | Adafruit |
| 1 | Pi Camera Module 3 | Card ID | $25 | Adafruit |
| 1 | Pi Zero CSI adapter cable | 22-pin mini → 15-pin standard CSI ribbon | $4 | Adafruit |
| 1 | PCA9685 16-ch PWM board | Servo driver (I²C) | $6 | Amazon |
| 3 | MG996R servo | ch0 arm / ch1 deflect gate / ch2 bin select | $12 | Amazon 3-pack |
| 1 | HX711 + 50g load cell kit | Double-pick detection | $6 | Amazon |
| 1 | 5V relay module (1-ch, active-LOW, 3.3V-logic compatible) | Vacuum pump switch | $4 | Amazon |
| 1 | 10 kΩ resistor, ¼ W | GPIO 17 → 3.3 V pull-up: floating pin = pump OFF (audit B-14) | $1 | Any resistor assortment / Adafruit / Digi-Key |
| 1 | 12V mini diaphragm pump | Card suction | $10 | Amazon |
| 1 | Pololu D24V22F5 — **fixed** 5V 2.5A step-down (#2858) | Regulator #1: Pi + logic rail | $19 | Pololu |
| 1 | Pololu D24V50F5 — **fixed** 5V 5A step-down (#2851) | Regulator #2: servo rail, PCA9685 V+ only (audit B-12) | $30 | Pololu |
| 1 | 12V 3A power supply *(B0CQ7M3MM1, already ordered)* | Main power | $12 | Amazon |
| 1 | Panel-mount barrel jack 5.5×2.1 mm | Chassis power inlet | $3 | Amazon |
| 2 | N20 gear motor 6V 200rpm | One per roller (both driven) | $8 | Amazon 2-pack |
| 1 | L9110S dual motor driver | Controls N20s | $3 | Amazon |
| 1 | LED ring / white LED strip | Scanner lighting | $6 | Amazon |
| 1 | Dupont jumper wire kit (M-F/F-F/M-M) | All wiring | $7 | Amazon |
| 1 | 32GB micro SD (Class 10) | Pi OS + software | $7 | Amazon |
| 1 | Suction cup + 4mm barbed fitting | Card pickup head | $4 | Amazon |

**Electronics: ~$182**

> **Why fixed-output regulators instead of 2× LM2596:** no multimeter is available for this build. An adjustable LM2596 must be set with a meter before any load is connected, and these boards often ship with the pot set near the input voltage. 12 V on the Pi's 5 V pin kills it instantly. The Pololu modules are factory-fixed at 5 V (±4 % → 4.8–5.2 V), so there's nothing to set. Cost: +$39 over two LM2596 boards.
>
> **Load check:**
> - Regulator #1: about 1.75 A of its 2.5 A (Pi, camera, LED, relay, logic, 2 × N20 running).
> - Regulator #2: about 3.5 A of its 5 A (one MG996R stalled at 2.5 A plus two moving).
> - The 12 V side at typical load is about 1.5 A for the regulators plus 1–2 A for the pump. That is close to the 3 A adapter's limit at pump start-up.

## Hardware (non-printed)

| Qty | Part | ~Price | Where |
|-----|------|--------|-------|
| 4 | 608ZZ bearings (8 ID × 22 OD × 7 mm), one per rail boss | $5 | Amazon 10-pack |
| 2 | 8 mm steel rod (linear shaft), 150 mm stock — **cut to 136 mm**, see math below | $9 | Amazon / AliExpress 2-pack |
| 2 | Shaft collar, 8 mm bore, set-screw (typ. Ø16 × 8 mm, M4 set screw) — plain-rail end of each rod (buy a 4-pack) | $8 | Amazon 4-pack |
| 2 | Shaft coupling 3 mm ↔ 8 mm, D19 × L25 (per `cad/motor_mount.scad`) — N20 shaft to rod, one per driven roller | $8 | Amazon / AliExpress 2-pack |
| 1 | M3 socket/button-head screw + nut + washer assortment (~250 pc, 6–30 mm). Covers: 4× M3×10 BHCS (motor mounts), 8× M3×12 + nuts (gate levers), 4× M3×16 + nuts (arm), 2× M3 + nut (camera foot), plus baseplate/tray screws | $12 | Amazon |
| 1 | M3 countersunk ISO 10642 (DIN 7991): 8× M3×12 (tray stacking) + 8× M3×25 (tray → baseplate through a 12 mm board) | $6 | Amazon assortment |
| 1 | M3 heat-set inserts (20pc), for a Ø4.0–4.2 mm hole, ≤ 9 mm long (e.g. Ruthex / CNC Kitchen M3×5.7, or generic M3×5×4.5). **4 needed** (motor-side rail pads) | $4 | Amazon |
| 1 | M2.5 brass standoff kit — PCB mounts Pi Zero / PCA9685 / HX711 *(already ordered — B0G1XNRC53)* | $6 | Amazon |
| 1 | M2.5 × 6 mm screws + hex nuts, 20pc ea. — PCB standoff mounts *(check if included with B0G1XNRC53)* | $4 | Amazon |
| 1 | Small screws: 4× M2×10 self-tapping (camera PCB) + 4× M1.6×4 pan head (N20 gearbox face → motor mount) | $6 | Amazon M1.6/M2 assortment |
| 1 | 4mm silicone tubing, 30cm | $3 | Amazon |
| 8 | #010 O-rings (16mm ID × 2mm), 4 per roller | $5 | Amazon |

**Hardware: ~$76**

### 8 mm rod length — PENDING motor-mount integration

All values come from the SCAD files.

| Segment | mm | Source |
|---------|----|--------|
| Rail inner gap | 90.0 | `assembly.scad` `rail_in = 45` → faces at Y = ±45 (= `roller_w` 90) |
| Rail walls, 2 × 3.0 | 6.0 | `conveyor_rail.scad` `wall = 3.0` |
| Bearing bosses, 2 × 7.2 | 14.4 | `conveyor_rail.scad` `boss_h = 7.2` |
| **Boss face → boss face** | **110.4** | |
| Motor side: past the boss face | 15.5 | `motor_mount.scad` `rod_protrusion` = `flange_t` 4 + `gap_flange_cpl` 1.5 + `cpl_rod_engage` 10 |
| Plain side: running gap + collar + stick-out | 10.0 | 0.5 + 8.0 (collar width, typical) + 1.5 |
| **Rod length** | **135.9 → cut to 136 mm** | |

- Don't leave the rod at 150 mm. The plain-side stub would reach Y = 55.2 + (150 − 110.4 − 15.5) = 79.3, which is 0.7 mm from the electronics tray (starts at Y = 80 in `assembly.scad`).
- Each rod also needs a filed flat, about 0.5 mm deep and 4 mm wide (`conveyor_roller.scad` `motor_flat_w`), along the 90 mm roller span and the last 10 mm on the motor side.
- Only 2 collars are needed. On the motor side, the motor-mount flange and the coupling locate the rod.

### Tools (not in total)

| Item | Why | ~Price |
|------|-----|--------|
| M3 heat-set insert tip for the 60 W iron (on order) | Keeps inserts square; a conical tip works but tilts | $10 |
| 8.0 mm drill bit | Ream rail shaft holes and roller bores if they print undersize | $3 |
| Flat needle file | Rod D-flats | $5 |
| Hacksaw + 3.4 mm drill | Cut rods to 136 mm; drill backing board for through-bolts | — |

## 3D Printing

| Material | Est. Weight | Est. Cost |
|----------|------------|-----------|
| PLA (most parts) | ~360g | ~$7 |
| PETG (arm + gate levers) | ~30g | ~$1 |

**Filament: ~$8** · Print time: ~20–25 hrs on P1S fast profile

> These filament figures have **not** been re-estimated for parts added since v0.2: 4 sorting-tray sections + 2 shelf halves, 2 rollers, 2 motor mounts, the camera bracket and 2 gate levers. Re-slice to confirm; the tray sections alone are 137 × 98 × 65 mm each.

---

## Grand Total

| | |
|--|--|
| Electronics | ~$182 |
| Hardware | ~$76 |
| Filament | ~$8 |
| **Total** | **~$266** |

**With AliExpress sourcing (~20% off everything except the $49 of Pololu regulators):** ~$223
**Full Amazon + Pololu:** ~$266

> Largest savings: Pi Camera v2 clone (~$12 vs $25) saves $13
> and buying servos/motors from AliExpress saves ~$10 more.
