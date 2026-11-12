# Riftbound Card Sorter: Bill of Materials (v2)

This is the BOM for the v2 machine (Nov 2026 redesign): a motor-raised hopper, a single-servo suction pick arm with a vent valve for a clean release, a raised round-belt conveyor with a camera-centred stop, and a cradle shuttle that weighs every card and tips it into a 2-floor tray or a reject bin. Every quantity and dimension comes from the `cad/*.scad` headers and BOM footers and from `hardware/*.py`. The build guide is [`docs/ASSEMBLY.md`](docs/ASSEMBLY.md).

**Status column**
- **have**: the owner has this or has ordered it (confirmed list).
- **verify (Nov 5 order)**: the project notes list this in Amazon order #114-6087458-4005855. Check the parts box before you buy it.
- **buy**: still to buy.
- **optional**: fallback or upgrade only. Not in the totals.

Prices are approximate US prices from Nov 2026. Links are examples, not endorsements. Amazon links are searches because listings change.

## Totals

<!-- PENDING CAD round 3 / code round 2: totals will be re-checked after the final fastener, valve-mount, baseplate (tee-nut) and switch changes -->

| | ~Cost |
|---|---|
| Already have / ordered (confirmed) | $151 |
| Probably on hand from the Nov 5 order (verify) | $36 |
| **Still to buy** | **$609** (parts $497 + filament $112) |
| Whole machine | ~$796 |

**Still-to-buy subtotal: ~$609.**
- If the "verify" items turn out to be missing, it rises to ~$645.
- If the Arducam IMX708 from the earlier order fits the camera bracket, it drops by $25.
- The **Optional cost-down** section below can take another ~$60 off without changing the design (~$549).
- The owned 12 V 3 A adapter is counted under "have" but is **replaced** by a 12 V 5 A adapter (see Power budget). Keep the 3 A one for bench work.

### Still to buy (summary)

- **Electronics:** Pi Camera Module 3, SC1130 500 mm camera cable, **12 V 5 A adapter**, Pololu D24V22F5 + D24V50F5 + D36V28F5, **2-channel 5 V relay module**, 28BYJ-48 + ULN2003, 2 × Omron SS-5GL2-F, 5 V COB LED strip, 6 × 10 kΩ resistors, 2 × 1N5819 diodes, 3 × 1000 µF capacitors, panel barrel jack (M8 thread), Wago lever connectors, servo extension leads, 4-core flexible lead, 26 AWG hook-up wire.
- **Motion:**
  - Conveyor: 2 × 8 mm D-shaft 150 mm, 4 × 135 × 3 O-rings, 4 × 8 mm collars, 2 × 3→8 couplings.
  - Hopper: 5→8 coupling, T8×8 lead screw + nut.
  - Shuttle: 400 mm rod, 400 mm D-shaft, 2 × 688ZZ, Ø3 dowel pins (1 × 20, 4 × 8).
  - Shared: 4 × LM8UU, 2 × 25T aluminium disc horns, 8 mm flange coupling, 4 mm silver-steel rod + 2 Ø4 dowels, 8 × 6 tube, push-on washers, slider springs.
- **Pneumatics:** SMC ZPT16BS-B5 pad, M5 × 4 mm barb, 4 mm OD tube, pump adapter, **12 V normally-closed mini solenoid vent valve**, **4 mm barbed tee**.
- **Fasteners:** 2 × 4 mm shoulder screws (M3 thread), 2 × M3 × 4 short heat-set inserts, M3 × 40, M3 × 80, M3 × 20 top-up, M3 countersunk set, M3 set screws, M2/M2.5 set (incl. 16 self-tappers for the tray boards), M1.6 × 4.
- **Frame and consumables:** PTFE tape (required), 6 mm backing board, rubber feet, black foam, foam tape, neoprene strip (pump sleeve, or print it in TPU), zip ties, heat-shrink, 600-grit paper, ~3.4 kg PLA + ~0.5 kg PETG + ~0.2 kg black.

### Removed from the v1 BOM (no longer used)

The v1 hopper, sorter, arm and weigh station are gone; [`CHANGELOG.md`](CHANGELOG.md) lists what each was replaced by. Parts of the old BOM that v2 no longer buys:
- 9 output bins (`output_bin.scad`) and the 2 v1 sorter levers (`sort_gate_lever.scad`) with their M3 × 12 horn screws.
- The old vertical-axis swing arm and its arm post.
- 8 × #010 (16 mm ID) O-rings and the roller O-ring grooves.
- LED ring / WS2812B ring: it puts a glare spot on foils. Strips are used instead.
- The separate weigh platform (the load cell now sits under the cradle).
- "Pi Zero CSI adapter cable": replaced by the 500 mm SC1130.
- GT2 belt and pulleys.
- LM2596 adjustable bucks: replaced by fixed-output modules, because there is no multimeter.
- The tilt-crank M3 × 4 set screw and the M3 tap (the crank now slides on the D-shaft with no set screw).

**Owned but not used by v2** (not in the totals): the 1-channel relay module (replaced by a 2-channel one for the vent valve), the M2.5 brass standoff kit (the electronics tray now has printed posts), and from the Nov 5 order the 27 mm suction cup (it doesn't fit the arm's cup sled), the 12 V 2 A adapter (too small), the 2 × LM2596, the WS2812B ring and the 16 mm O-rings.

## Power budget

These are worst-case figures; none has been measured on this machine yet.

| Load | Assumed current |
|---|---|
| MG996R (5 V) | ≈ 0.5–0.9 A moving, ~2.5 A inrush when a move starts, 0.3–0.5 A holding against a load, 2.5 A stall |
| N20 6 V 200 rpm (at 5 V) | ≈ 0.15 A running, 0.5–1.6 A each at start or stall |
| 28BYJ-48 half-step | ≈ 0.24 A while stepping (`hardware/elevator.py`; coils released after every move) |
| Pi Zero 2 W | ≤ 0.6 A |
| Camera Module 3 | 0.25 A |
| LED strips (2 × 88 mm of 5 V COB) | ≈ 0.3 A |
| Relay coils (2-channel module) | ≈ 0.07 A per energised channel; 0.14 A with both on |
| R385 pump | 0.5–0.7 A at 12 V, ≈ 1 A start |
| 12 V NC mini solenoid vent valve | ≈ 0.2–0.3 A at 12 V (check the label). Energised only for the 0.4 s vent pulse (`vacuum.VENT_S`), always with the pump already off |

### Rails (three regulators)

| Rail | Source | Loads | Worst case | Rating | Verdict |
|---|---|---|---|---|---|
| 12 V | **12 V 5 A adapter** → barrel jack → Wago bus | Reg #1, #2, #3 VIN; relay COM 1 → pump; relay COM 2 → vent valve | Arm move with the pump on: Reg #2 4 A × 5 V / 0.9 = 22.2 W, Reg #1 1.3 A → 7.5 W, pump 8.4 W → **38.1 W = 3.2 A** (+ pump inrush). The valve (≤ 3.6 W) is never on with the pump, so it doesn't add. | 5 A (60 W) | OK (64 %). **The owned 3 A adapter is not enough** (106 %). |
| 5 V logic | Reg #1, Pololu D24V22F5 (2.5 A) | Pi (GPIO pins 2/4), camera (via the Pi), LED strips, relay VCC. HX711 and **PCA9685 VCC run from the Pi's 3.3 V pin**. | Pi 0.6 + camera 0.25 + LEDs 0.3 + both relay coils 0.14 ≈ **1.3 A**. Nothing on this rail can stall. | 2.5 A | OK (52 %) |
| 5 V servo | Reg #2, Pololu D24V50F5 (5 A) | **PCA9685 V+ only** (ch0, ch1, ch2), 1000 µF at the regulator + 1000 µF at V+ | Arm-move inrush 2.5 A + tilt hold + carriage hold ≈ **4 A**. Single servo stall ≈ 4 A. | 5 A | OK (80 %) |
| 5 V motor | **Reg #3, Pololu D36V28F5 (3.2 A)** | L9110S VCC (both N20s), ULN2003 + 28BYJ-48, 1000 µF at the output | Both N20s stalled 2 × 1.6 = **3.2 A**. Belt start ≈ 1.2 A. Stepper 0.24 A, never at the same time as the belt in the cycle. | 3.2 A | OK. A double stall is right at the limit; the regulator current-limits, and only the motor rail sags, never the Pi. |

### Why three regulators

- Two N20s at start or stall (up to 3.2 A) plus the stepper would overload Reg #1 and brown out the Pi and SD card.
- The servo rail has no room for them either: its arm-move peak is already ≈ 4 A.
- A separate fixed-5 V buck keeps the motor current off both rails. 5 V rather than 6 V keeps the 28BYJ-48 in spec and matches the belt speed the code was tuned for.
- Note the L9110S is rated 0.8 A continuous per channel. A stalled N20 is a fault (the belt-centring code stops the belt), not a running state.

### Additions this budget requires (all in the BOM below)

- 12 V 5 A adapter (replaces the 3 A one).
- Reg #3 (D36V28F5).
- 3 × 1000 µF: Reg #2 output, PCA9685 V+, Reg #3 output.
- 1N5819 (or 1N4007) flyback diodes: one across the pump, one across the vent-valve coil.
- 10 kΩ pull-ups on GPIO 17 (pump relay input) and GPIO 27 (vent relay input), to 3.3 V.
- 10 kΩ pull-downs on GPIO 23–26 (L9110S inputs).

**Why the pull-ups and pull-downs.** RPi.GPIO `cleanup()` (`conveyor.deinit()`, `vacuum.deinit()`) returns the pins to inputs with **no pull**, so they float. The SoC's default pulls only apply from power-on until the program first configures the pin, and on GPIO 17 and 27 that default is a pull-*down*, which an active-LOW relay reads as ON. The pull-ups hold both relay inputs HIGH (pump off, vent closed) and the pull-downs hold the L9110S inputs LOW (coast) whenever no program drives them. The ULN2003's inputs already have internal base-emitter resistors, so a floating stepper input stays off.

## Fastener counts

<!-- PENDING CAD round 3: ch1 coupler, ch2 ear block, guide-rod clamps, hopper carriage nut screws, valve/tee mount, possible tee-nuts in the board -->

Counted from the hardware notes and BOM footers of every `cad/*.scad` file, de-duplicated across steps. Screw lengths assume the **6 mm backing board** in this BOM. The rule for through-bolts is clamp length + 4 mm (washer 0.5 + nut 2.4 + 1 mm of thread). "Self-tap" means a thread-forming screw into a printed pilot.

| Size | Qty | Where (ASSEMBLY.md step) |
|---|---|---|
| M3 × 6 SHCS | 4 | arm crank → disc horn (§11) |
| M3 × 6 cup-point set screw | 2 | roller grub screws (§8) |
| M3 × 8 SHCS | 6 | 28BYJ-48 ears → cap inserts 2 (§10); ch1 disc horn ↔ flange coupling 4 (§13.4) |
| M3 × 10 SHCS / BHCS | 24 | motor mounts 4 BHCS (§8); rail insert feet X −50 front, X +40 back 2 (§7); hopper cap 4, T8 nut 2 (§10); MG996R tabs on the arm 4 (§11); load cell → cradle 2 (§13.1); R-bar splice 2, rod clamps 2 (§13.3); pump-bracket cap 2 (§14.6) |
| M3 × 12 SHCS | 9 | riser joint 3 + nut (§6); arm head → tower 4 (§11); tilt frame → load cell 2 (§13.1) |
| M3 × 16 SHCS | 3 | camera bracket + rail feet X −20 / +10 2 (§9); ch1 tilt crank ↔ tilt link 1 + nylock (§13.2) |
| M3 × 20 SHCS + washer + nut | 27 | electronics tray 4 (§5), riser anchors 5 (§6), arm tower 4 (§11), shuttle end posts 6, lower ramp 4 (§13), pump bracket 4 (§14.6) |
| M3 × 20 SHCS + nylock | 1 | hopper feeler-flag axle (§10) |
| M3 × 40 SHCS | 2 | cup-slider guide screws (§11) |
| M3 × 80 SHCS (or 85 mm M3 threaded rod) + washer + nut | 4 | rail through-feet X −80 front, X −120 / −80 / +10 back (§7) |
| M3 × 10 countersunk | 10 | hopper floor plate 2 (§10); riser front tie 2 (§6); shuttle cheeks → sled 6 (§13.2) |
| M3 × 12 countersunk | 9 | sorting-tray stacking 8, self-tap into Ø2.5 pilots (§12); ch2 crank hub → servo spline 1 (§13.5) |
| M3 × 20 countersunk + washer + nut | 16 | hopper base 4 (§10), sorting-tray lower floor 8 (§12), reject bin 4 (§13.6) |
| Shoulder screw, 4 mm shoulder, M3 × 4 thread, head ≤ Ø8 × 4 | 2 | ch2 crank tip (5 mm shoulder) and ch2 drive pin (6 mm shoulder) (§13.5) |
| M3 nuts / washers (plain) | 50 / 47 | under the board 47 (nut + washer each: 27 + 16 + 4); riser joint 3 (nut only). With threaded rod for the through-feet: +4 nuts, +4 washers. |
| M3 nylock | 2 | tilt-crank pivot 1, flag axle 1 |
| M3 brass heat-set insert, 5.7 long (Ø4.0–4.2 hole) | 44 | see ASSEMBLY.md §3 |
| M3 × 4 short heat-set insert (≤ Ø4.6 OD) | 2 | ch2 link top (§13.5) |
| M2 × 12 + nut | 4 | hopper switches (§10) |
| M2 × 10 self-tap | 4 | camera PCB (§9) |
| M2 × 6 countersunk self-tap | 4 | ch2 crank → round horn disc (§13.5) |
| M2 × 5–6 self-tap | 6 | three Pololu regulators, 2 each (§5) |
| M2.5 × 10 self-tap | 8 | ch1 servo ears 4, ch2 servo ears 4 (§13.4, §13.5) |
| M2.5 × 6–8 self-tap | 16 | Pi Zero 2 W 4, PCA9685 4, relay 4, ULN2003 4 (§5) |
| M1.6 × 4 pan head | 4 | N20 gearbox faces (§7) |
| Dowel pins | 2 × Ø4 × 8, 1 × Ø3 × 20, 4 × Ø3 × 8 | shuttle F pins, tilt pin A, cheek ↔ sled (§13) |
| Optional M3 × 16 + washer + nut | 18 | tile → board at free grid holes (2 per tile) |

## Printed parts

Everything fits a 256 × 256 mm bed (Bambu P1S); the largest parts are the 248 mm R-bar +Y half and the 240 mm card guides. Volumes are the solid volume of each exported part (`openscad --backend=manifold`, measured for this BOM). Most v2 parts are thin-walled, so the printed mass is about 75–90 % of solid × 1.24 g/cm³. **Total ≈ 4 025 cm³ solid, ≈ 4.0 kg of filament (3.4 kg PLA, 0.45 kg PETG, 0.2 kg black, ~5 g TPU).** Most of it is the 9 baseplate tiles (1.2 L) and the riser (0.7 L). Expect about 120 h of printing on a P1S; slice to confirm.

| Part | Qty | Material / settings | File (`part=` or module) | Print orientation | Supports | Solid cm³ (each) |
|---|---|---|---|---|---|---|
| Baseplate tile 190 × 180 × 4 | 9 | PLA 0.2, 4 walls, 40 % | `baseplate_tile.scad` `tile` | flat, top up (key pockets open upward) | none | 134.1 |
| Bow-tie tile key 16 × 11.3 × 2.3 | 24 | PLA | `baseplate_tile.scad` `keys` (24 on one plate) | flat | none | 0.31 |
| Electronics tray 185 × 150 × 45 | 1 | PLA 0.2, 3 walls, 25 % | `electronics_tray.scad` | floor down | none (10 mm slot bridges) | 142.8 |
| Riser A / Riser B | 1 + 1 | PLA/PETG 0.24, 3 walls, 15 % gyroid | `riser.scad` `riser_a`, `riser_b` | upside down (deck on bed) | none | 361.7 / 332.6 |
| Rail half, back | 2 | PLA 0.2, 4 walls, 40 % | `conveyor_rail.scad` `back1`, `back2` | inner face on bed | none | 16.7 |
| Rail half, front (motor side) | 2 | PLA 0.2, 4 walls, 40 % | `conveyor_rail.scad` `front1`, `front2` (pre-mirrored) | inner face on bed | none | 17.3 |
| Roller Ø22 × 88 | 2 | PLA/PETG, 4 walls, 60 % | `conveyor_roller.scad` `roller()` | axis vertical | none (45° groove flanks) | 27.1 |
| Race spacer 11/8.3 × 1 | 4 | PLA/PETG | `conveyor_roller.scad` `race_spacer()` | flat | none | 0.04 |
| Motor mount | 2 | PETG/PLA 0.2, 4 walls, 40 % | `motor_mount.scad` | floor down | none | 14.9 |
| Slide bed 174 × 89 | 1 | PLA/PETG 0.2, 3 walls, 20 % | `slide_bed.scad` | upside down (lands on bed) | none | 88.1 |
| Card guide back / front | 1 + 1 | PETG (black if possible) 0.2, 3 walls, 20 % | `card_guide.scad` `guide_back`, `guide_front` | upside down (flat top on bed) | none | 21.3 |
| Guide clip | 4 | PETG | `card_guide.scad` `clip` | profile on bed | none | 0.32 |
| Scanner hood | 1 | **black** PLA/PETG 0.2, 3 walls, 15 % | `scanner_hood.scad` `hood` | roof down | none | 127.1 |
| Camera bracket | 1 | PLA/PETG 0.2, 4 walls, 30–40 % | `camera_bracket.scad` `print_orient=true` | on its −X side | none | 114.2 |
| Hopper body | 1 | PLA/PETG 0.2, 3–4 walls, 25–40 % | `hopper.scad` `body` | upright | none | 193.3 |
| Hopper cap | 1 | same | `hopper.scad` `cap` | top face down (pre-flipped) | none | 13.8 |
| Hopper carriage | 1 | same | `hopper.scad` `carriage` | upright (shelf on bed) | none | 35.9 |
| Hopper floor plate | 1 | same | `hopper.scad` `plate` | card face down on PEI | none | 25.1 |
| Feeler flag | 1 | same | `hopper.scad` `flag` | on its side | none | 1.0 |
| Arm head | 1 | PETG 0.2, 4 walls, 40 % gyroid | `suction_arm.scad` `head` | plate front face down | none | 49.3 |
| Arm tower (≈155 tall) | 1 | PETG, 30 % | `suction_arm.scad` `tower` | upright on foot | none | 117.9 |
| Arm crank | 1 | PETG, 5 walls, 100 % round the hub | `suction_arm.scad` `crank` | flat | none | 8.1 |
| Arm links B + C | 2 (one print) | PETG, 5 walls | `suction_arm.scad` `link` | flat | none | 7.6 (both) |
| Arm hand | 1 | PETG | `suction_arm.scad` `hand` | back face down, beams up | none | 19.8 |
| Cup sled | 1 | PETG | `suction_arm.scad` `sled` | upright, hex pocket down | none | 5.4 |
| Arm sleeves (4 lengths) | 4 | PETG (or nylon spacers) | `suction_arm.scad` `sleeves` | upright | none | 4.7 (all 4) |
| Tray section A / B (lower) | 1 + 1 | PLA 0.2, 40 % | `sorting_tray.scad` `tray_floor_section(0,true,false)` / `(2,false,true)` | open top up | none (label windows bridge) | 102.0 |
| Tray section C / D (upper) | 1 + 1 | PLA 0.2, 40 % | `tray_floor_section(4,true,false)` / `(6,false,true)` | open top up | none | 90.4 |
| Tray shelf half | 2 | PLA | `floor_shelf_half()` | flat | none | 40.2 |
| Cradle | 1 | PLA **0.12**, 3 walls, 15 %, iron top | `shuttle.scad` `cradle` | bed top up, ribs on the plate; **use a brim** (≈ 600 mm² on the bed) | none | 13.7 |
| Tilt frame | 1 | PETG 0.2, 4 walls, 40 % | `shuttle.scad` `tilt_frame` | upright, crossbar down | **tree supports** under the plate bottom edges + skid nubs | 18.5 |
| Shuttle sled | 1 | PETG 0.2, 4 walls, 40 % | `shuttle.scad` `sled` | on its +y face | none | 65.3 |
| Shuttle cheek −Y / +Y | 1 + 1 | PETG 0.2, 4 walls, 40 % | `shuttle.scad` `cheek_neg`, `cheek_pos` | flat on the outer face | none | 18.0 |
| Tilt crank / tilt link | 1 + 1 | PETG 100 % | `shuttle.scad` `tilt_crank`, `tilt_link` | flat | none | 2.1 / 0.9 |
| ch2 crank (155 mm) | 1 | PETG 0.2, 5 walls, 50 % | `shuttle.scad` `c2_crank` | flat, countersinks down | none | 8.0 |
| ch2 link (173 mm) | 1 | PETG | `shuttle.scad` `c2_link` | flat | none | 7.8 |
| R-bar −Y / +Y | 1 + 1 | PLA, 4 walls | `shuttle.scad` `rbar_neg`, `rbar_pos` | on the −X face; sand the top | none | 21.4 / 33.6 |
| End post −Y / +Y | 1 + 1 | PETG/PLA, 4 walls, 40 % | `shuttle.scad` `end_post_neg`, `end_post_pos` | upright | none | 31.7 / 18.4 |
| Lower ramp halves | 2 | PLA **0.16**, 3 walls, 15 %, bridge fan 100 % | `lower_ramp.scad` `ramp_neg`, `ramp_pos` | **upright as modelled** (base on the bed) | none; sand lanes 600 grit | 69.0 |
| Reject bin | 1 | PLA 0.2, 3 walls, 15 % | `reject_bin.scad` | upright | none | 78.8 |
| Pump bracket base / cap | 1 + 1 | PETG or PLA | `pump_bracket.scad` `base`, `cap` | base upright; cap on its end face | none | 19.4 / 3.4 |
| Pump sleeve | 1 | **TPU 95A** (or skip it and use a neoprene strip) | `pump_bracket.scad` `sleeve` | upright | none | 4.1 |

Not printed in v2: `sort_gate_lever.scad`, `output_bin.scad`. These files are wrappers or helpers with no part of their own: `machine_frame.scad`, `shuttle_geom.scad`, `hopper_elevator.scad`, `assembly.scad`. The shuttle `carriage` selector is a preview of sled + cheeks, not a print.

## Purchased parts

### Electronics

| Qty | Part | Example link | ~Price | Status | Notes |
|---|---|---|---|---|---|
| 1 | Raspberry Pi Zero 2 W starter kit (board, header, microSD, case, PSU) | [amazon.com](https://www.amazon.com/s?k=CanaKit+Raspberry+Pi+Zero+2+W+starter+kit) | $40 | **have** | CanaKit kit; SD card from the kit |
| 1 | Raspberry Pi Camera Module 3, standard lens (IMX708, 66° × 41°) | [adafruit.com](https://www.adafruit.com/product/5657) | $25 | buy | Project notes show an Arducam IMX708 (B0G5YJMR8Q) on an earlier order. Use it only if its PCB is the official 25 × 23.862 mm board with 21 × 12.5 mm holes (camera_bracket.scad) |
| 1 | Raspberry Pi camera cable Standard–Mini 500 mm, part SC1130 (22-pin 0.5 mm ↔ 15-pin 1 mm) | [digikey.com](https://www.digikey.com/en/products/detail/raspberry-pi/SC1130/21658263) | $3 | buy | Route is ≈ 0.45 m, see ASSEMBLY.md §14.5 |
| 1 | PCA9685 16-ch 12-bit PWM board (I²C 0x40) | [amazon.com](https://www.amazon.com/s?k=PCA9685+16+channel+servo+driver) | $7 | **have** | The tray posts are on the Adafruit #815 pattern, 55.88 × 19.05 mm; the common blue clone copies it |
| 3 | MG996R metal-gear servo: ch0 arm, ch1 cradle tilt, ch2 shuttle | [amazon.com](https://www.amazon.com/dp/B07MFK266B) | $19 | **have** | 4-pack ordered, so 1 spare. Must reach ~170° (arm) and ~176° (ch2): test first |
| 1 | HX711 amplifier + TAL221 50 g mini load cell (47 × 12 × 6, 4 × M3) | [amazon.com](https://www.amazon.com/dp/B09K7G3477) | $10 | **have** | the HX711 sits in a corner-stop pocket on foam tape |
| 1 | **2-channel** 5 V relay module, opto-isolated, active-LOW inputs (Songle type, ≈ 50 × 38.5, holes ≈ 44.3 × 32.8) | [amazon.com](https://www.amazon.com/s?k=2+channel+5V+relay+module+optocoupler+low+level+trigger) | $7 | buy | ch1 pump (GPIO 17), ch2 vent valve (GPIO 27). Replaces the owned 1-channel module. Must switch off with a 3.3 V input: bench-test it (ASSEMBLY.md §14.1); a board with a JD-VCC jumper can be fixed if not |
| 1 | 12 V R385 diaphragm pump (Gikfun), used as the vacuum source | [amazon.com](https://www.amazon.com/dp/B0744FWNFR) | $10 | **have** | 0.5–0.7 A at 12 V. Mounted in the printed pump bracket |
| 2 | N20 gear motor 6 V 200 rpm (GA12-N20, 3 mm D-shaft) | [amazon.com](https://www.amazon.com/dp/B0DFVHGZS4) | $13 | **have** | price is the 2-pack |
| 1 | L9110S dual H-bridge board | [amazon.com](https://www.amazon.com/dp/B0FTFLK1FC) | $7 | **have** | 3-pack ordered; sits in a corner-stop pocket on foam tape |
| 1 | 12 V 3 A DC adapter, 5.5 × 2.1 mm, centre + (owned, **to be replaced**) | [amazon.com](https://www.amazon.com/dp/B0CQ7M3MM1) | $9.50 | **have** | too small: the arm-move peak is ≈ 3.2 A at 12 V (power budget). Keep it as a bench supply |
| 1 | 12 V 5 A (60 W) DC adapter, 5.5 × 2.1 mm, centre + (main supply) | [amazon.com](https://www.amazon.com/s?k=12V+5A+power+adapter+5.5x2.1) | $14 | buy | replaces the 3 A adapter |
| 1 | Pololu D24V22F5: fixed 5 V 2.5 A buck (regulator #1, logic rail) | [pololu.com](https://www.pololu.com/product/2858) | $19 | buy | see Optional cost-down |
| 1 | Pololu D24V50F5: fixed 5 V 5 A buck (regulator #2, servo rail: PCA9685 V+ only) | [pololu.com](https://www.pololu.com/product/2851) | $30 | buy | see Optional cost-down |
| 1 | Pololu D36V28F5: fixed 5 V 3.2 A buck (regulator #3, motor rail: L9110S/N20s + ULN2003/28BYJ-48) | [pololu.com](https://www.pololu.com/product/3782) | $22 | buy | see Optional cost-down |
| 1 | 28BYJ-48 5 V geared stepper + ULN2003 driver board | [amazon.com](https://www.amazon.com/s?k=28BYJ-48+5V+stepper+ULN2003+driver) | $8 | buy | hopper elevator; the tray blocks are for the 35 × 32 board with 30 × 26.5 holes |
| 2 | Omron SS-5GL2-F micro switch, roller lever (top-of-stack + home) | [digikey.com](https://www.digikey.com/en/products/result?keywords=SS-5GL2-F) | $7 | buy | hopper.scad footprint 19.8 × 6.4 × 10.2, Ø2.35 holes 9.5 apart. SS-01GL2-E halves the force on the card |
| 1 | 5 V white COB LED strip, 8 mm wide, cuttable at ≤ 22 mm (2 × 88 mm used) | [amazon.com](https://www.amazon.com/s?k=5V+COB+LED+strip+8mm+white) | $8 | buy | hood LED bands are 10 mm tall, 88 mm long per side |
| 6 | 10 kΩ ¼ W resistor: 2 pull-ups (GPIO 17, 27 → 3.3 V), 4 pull-downs (GPIO 23–26 → GND) | [amazon.com](https://www.amazon.com/s?k=10k+ohm+resistor) | $2 | buy | RPi.GPIO cleanup() leaves pins floating with no pull |
| 2 | 1N5819 (or 1N4007) diode: across the pump and across the vent-valve coil | [amazon.com](https://www.amazon.com/s?k=1N5819+diode) | $1 | buy |  |
| 3 | 1000 µF 16 V electrolytic capacitor: servo-rail regulator output, PCA9685 V+, motor-rail regulator output | [amazon.com](https://www.amazon.com/s?k=1000uF+16V+capacitor) | $3 | buy |  |
| 1 | Panel-mount DC barrel jack 5.5 × 2.1 mm, DC-022 type with **M8 × 0.75** thread, rated ≥ 5 A | [amazon.com](https://www.amazon.com/s?k=DC-022+panel+mount+barrel+jack+5.5x2.1) | $3 | buy | the Ø8.2 hole is in the tray's +Y wall. An 11 mm-thread jack needs the hole opened to Ø11.2 |
| 1 | Lever splice connectors (Wago 221, 3- and 5-way): 12 V, 5 V logic, 5 V servo, 5 V motor, GND buses | [amazon.com](https://www.amazon.com/s?k=Wago+221+lever+connector) | $8 | buy |  |
| 1 | Servo extension leads, 100 cm (pack of 5) | [amazon.com](https://www.amazon.com/s?k=servo+extension+cable+100cm) | $8 | buy | ch0, ch1, ch2 to the tray (≈ 1 m runs, ASSEMBLY.md §14.4) |
| 1 | 4-core flexible lead, 26–28 AWG silicone, 1 m (load-cell trailing loop) | [amazon.com](https://www.amazon.com/s?k=4+core+silicone+wire+26AWG) | $7 | buy |  |
| 1 | 26 AWG stranded hook-up wire, 6 colours (signal extensions, switches, stepper) | [amazon.com](https://www.amazon.com/s?k=26+AWG+stranded+hookup+wire+kit) | $12 | buy |  |
| 1 | 22 AWG stranded wire (power runs) | [amazon.com](https://www.amazon.com/dp/B07HGT44XY) | $11.50 | **have** |  |
| 1 | Micro-USB cable (bench power only, never with regulator #1 connected) | [amazon.com](https://www.amazon.com/dp/B01NBHYAR0) | $10 | **have** |  |
| 1 | Dupont jumper wires (bench tests) | [amazon.com](https://www.amazon.com/dp/B01EV70C78) | $7 | verify (Nov 5 order) |  |

Subtotal: $331 (have $137, verify $7, buy $187)

### Motion

| Qty | Part | Example link | ~Price | Status | Notes |
|---|---|---|---|---|---|
| 2 | 8 mm D-cut shaft, 150 mm (conveyor roller rods; 7.5 mm across the flat) | [amazon.com](https://www.amazon.com/s?k=8mm+D+shaft+150mm) | $10 | buy | or file a 4 mm wide, 0.5 mm deep flat full length on plain rods |
| 4 | 608ZZ bearing 8 × 22 × 7 (rail pockets) | [amazon.com](https://www.amazon.com/dp/B0DYNNW8N8) | $7 | verify (Nov 5 order) | 20-pack on the Nov 5 order |
| 4 | NBR 70A O-ring, ID 135 × CS 3.0 mm (round belts) | [amazon.com](https://www.amazon.com/s?k=O-ring+135mm+ID+3mm+cross+section+NBR) | $8 | buy |  |
| 4 | Shaft collar 8 mm bore, Ø16 × 8 wide, M4 set screw | [amazon.com](https://www.amazon.com/s?k=8mm+shaft+collar+16mm+OD) | $8 | buy | Ø18 collars have zero clearance, avoid |
| 2 | Shaft coupling 3 → 8 mm, D19 × L25, set screws | [amazon.com](https://www.amazon.com/s?k=shaft+coupling+3mm+to+8mm+D19+L25) | $8 | buy |  |
| 1 | Shaft coupling 5 → 8 mm, D19 × L25 (28BYJ-48 → T8 screw) | [amazon.com](https://www.amazon.com/s?k=shaft+coupling+5mm+to+8mm+D19+L25) | $5 | buy |  |
| 1 | T8 lead screw, 8 mm lead (T8×8), 100 mm, + brass flange nut (Ø22 flange, Ø10.2 body, 16 mm PCD) | [amazon.com](https://www.amazon.com/s?k=T8+lead+screw+100mm+lead+8mm+brass+nut) | $9 | buy |  |
| 2 | 8 mm smooth rod, 150 mm (hopper guide rods) | [amazon.com](https://www.amazon.com/dp/B0BNL57QGL) | $6 | verify (Nov 5 order) | 2-pack on the Nov 5 order |
| 4 | LM8UU linear bearing 8 × 15 × 24 (2 hopper carriage, 2 shuttle sled) | [adafruit.com](https://www.adafruit.com/product/1181) | $8 | buy |  |
| 1 | 8 mm smooth (h6, hardened) rod, 400 mm (shuttle) | [amazon.com](https://www.amazon.com/s?k=8mm+linear+rod+400mm) | $10 | buy |  |
| 1 | 8 mm D-shaft, 400 mm (shuttle tilt; ≈7.5 mm across the flat) | [amazon.com](https://www.amazon.com/s?k=8mm+D+shaft+400mm) | $15 | buy | check against d_bore() in shuttle.scad (flat at 3.55 mm). The tilt crank slides along it |
| 2 | 688ZZ bearing 8 × 16 × 5 (D-shaft, one per end post) | [amazon.com](https://www.amazon.com/s?k=688ZZ+bearing) | $6 | buy |  |
| 2 | 25T aluminium disc servo horn, Ø25, 4 × M3 (arm crank; ch1 D-shaft coupler) | [amazon.com](https://www.amazon.com/s?k=25T+aluminum+servo+horn+disc+25mm) | $8 | buy |  |
| 1 | Rigid flange coupling, 8 mm bore (bolts to the ch1 disc horn = 25T → D-shaft coupler) | [amazon.com](https://www.amazon.com/s?k=8mm+rigid+flange+coupling) | $6 | buy | hole PCD must match the horn; see ASSEMBLY.md §13.4 |
| 1 | Ø4 mm silver-steel rod 330 mm (arm pins: 38 + 29.5 + 13 + 21.5 mm) + 2 × Ø4 × 8 dowel pins (shuttle F pins) | [amazon.com](https://www.amazon.com/s?k=4mm+silver+steel+rod) | $10 | buy |  |
| 1 | Ø3 mm steel dowel pins: 1 × Ø3 × 20 (tilt pin A) + 4 × Ø3 × 8 (cheek ↔ sled) | [amazon.com](https://www.amazon.com/s?k=3mm+dowel+pin+assortment) | $6 | buy | an M3 dowel assortment covers both lengths |
| 1 | 8 × 6 mm brass or aluminium tube, ≥ 31 mm (hollow A' pin, cut 30.5) | [amazon.com](https://www.amazon.com/s?k=8mm+OD+6mm+ID+aluminum+tube) | $6 | buy |  |
| 1 | Flat push-on retaining washers: 4 × for Ø4 pins (≤ 0.5 mm thick), 1 × for Ø8 | [amazon.com](https://www.amazon.com/s?k=push+on+retaining+washer+4mm+starlock) | $7 | buy |  |
| 2 | Compression spring ≈ 0.3 wire × 5 OD × 18 free, ≤ 0.1 N/mm (cup slider) | [amazon.com](https://www.amazon.com/s?k=compression+spring+assortment+0.3mm) | $8 | buy |  |

Subtotal: $151 (have $0, verify $13, buy $138)

### Pneumatics

<!-- PENDING CAD round 3: vent valve + tee mount on the pump bracket -->

| Qty | Part | Example link | ~Price | Status | Notes |
|---|---|---|---|---|---|
| 1 | SMC ZPT16BS-B5 bellows vacuum pad, Ø16 silicone, M5 female, 8 mm hex | [uk.rs-online.com](https://uk.rs-online.com/web/p/pneumatic-suction-cups/7681662) | $18 | buy | the 27 mm cup on the Nov 5 order does not fit the cup sled's 8 mm hex pocket |
| 1 | Festo CN-M5-PK-3 barb (M5 male → 4 mm OD tube), or any M5 × 4 mm barb | [amazon.com](https://www.amazon.com/s?k=M5+male+barb+4mm+tube+fitting) | $6 | buy |  |
| 1 | 4 mm OD vacuum tube, 1 m (PU PUN-H-4×0.75 or 2 × 4 silicone) | [amazon.com](https://www.amazon.com/s?k=4mm+OD+polyurethane+tube) | $6 | buy | pump → cup ≈ 0.45 m, plus a short branch to the vent valve; the Nov 5 '4 mm silicone tubing' works only if it is 4 mm OD |
| 1 | Pump adapter: 5 cm silicone sleeve to fit the R385 nozzle + reducing barb to 4 mm | [amazon.com](https://www.amazon.com/s?k=reducing+barb+connector+6mm+to+4mm) | $5 | buy | connect the cup to the pump INLET |
| 1 | **12 V normally-closed** mini solenoid valve, 2-way, for air, barbed ports for ≈ 4 mm tube (vent valve) | [amazon.com](https://www.amazon.com/s?k=12V+normally+closed+mini+solenoid+valve+air) | $8 | buy | teed into the vacuum line; energised = open to air (`hardware/vacuum.py`). Must be **normally closed** |
| 1 | Barbed tee for 4 mm tube (pack) | [amazon.com](https://www.amazon.com/s?k=4mm+barbed+tee+connector) | $5 | buy | tees the vent valve into the line near the pump |

Subtotal: $48 (have $0, verify $0, buy $48)

### Fasteners and inserts

<!-- PENDING CAD round 3: fastener purchase lines follow the fastener table -->

| Qty | Part | Example link | ~Price | Status | Notes |
|---|---|---|---|---|---|
| 44 | M3 brass heat-set insert for a Ø4.0–4.2 mm hole, 5.7 mm long (Ruthex / CNC Kitchen M3×5.7) | [amazon.com](https://www.amazon.com/dp/B0DYPKB5V7) | $8 | verify (Nov 5 order) | 50-pack on the Nov 5 order: 44 used, 6 spare |
| 1 | M3 SHCS/BHCS assortment 6–20 mm with nuts, washers and nylocks (counts in the table above) | [amazon.com](https://www.amazon.com/dp/B0GDG2WGRV) | $8 | verify (Nov 5 order) | assortment on the Nov 5 order; check it covers the counts |
| 1 | M3 × 20 SHCS, 50-pack (top-up) | [amazon.com](https://www.amazon.com/s?k=M3x20+socket+head+cap+screw+50) | $6 | buy | the build needs 28 × M3 × 20; an assortment rarely has that many |
| 2 | Shoulder screw, 4 mm shoulder, M3 × 4 thread, head ≤ Ø8 × 4: one 5 mm shoulder, one 6 mm (ISO 7379 style, e.g. MISUMI MSB4-5 / MSB4-6) | [amazon.com](https://www.amazon.com/s?k=M3+shoulder+screw+4mm+shoulder) | $8 | buy | ch2 pivots |
| 2 | M3 × 4 short heat-set insert, OD ≤ 4.6 mm (pack) | [amazon.com](https://www.amazon.com/s?k=M3x4+brass+heat+set+insert) | $6 | buy | pressed flush into the ch2 link top |
| 2 | M3 × 40 SHCS (cup-slider guide screws) | [amazon.com](https://www.amazon.com/s?k=M3x40+socket+head) | $3 | buy |  |
| 4 | M3 × 80 SHCS (rail through-feet) or M3 threaded rod, 85 mm, + extra nuts | [amazon.com](https://www.amazon.com/s?k=M3x80+socket+head+screw) | $5 | buy |  |
| 1 | M3 countersunk (ISO 10642) assortment: 10 × M3×10, 9 × M3×12, 16 × M3×20 | [amazon.com](https://www.amazon.com/s?k=M3+countersunk+screw+assortment) | $8 | buy |  |
| 1 | M3 set screws: 2 × M3×6 cup point (rollers) | [amazon.com](https://www.amazon.com/s?k=M3+set+screw+assortment) | $4 | buy |  |
| 1 | M2 / M2.5 self-tapping assortment (pan + countersunk): 4 × M2×12 + nuts (switches), 4 × M2×10 (camera), 4 × M2×6 countersunk (ch2 horn), 6 × M2×5–6 (Pololus), 8 × M2.5×10 (servo ears), 16 × M2.5×6–8 (tray boards) | [amazon.com](https://www.amazon.com/s?k=M2+M2.5+self+tapping+screw+assortment) | $12 | buy |  |
| 4 | M1.6 × 4 pan head (N20 gearbox face) | [amazon.com](https://www.amazon.com/s?k=M1.6x4+screw) | $5 | buy |  |

Subtotal: $73 (have $0, verify $16, buy $57)

### Consumables and frame

| Qty | Part | Example link | ~Price | Status | Notes |
|---|---|---|---|---|---|
| 1 | 0.1 mm skived PTFE tape, self-adhesive (silicone), ≥ 75 mm wide (cradle bed + kick) — REQUIRED | [amazon.com](https://www.amazon.com/s?k=skived+PTFE+tape+0.1mm+adhesive+75mm) | $15 | buy |  |
| 1 | Backing board, 6 mm plywood/MDF, ≥ 570 × 540 mm | [amazon.com](https://www.amazon.com/s?k=6mm+plywood+sheet+24x24) | $12 | buy |  |
| 1 | Rubber feet ≥ 10 mm tall (8) | [amazon.com](https://www.amazon.com/s?k=rubber+feet+10mm+adhesive) | $6 | buy | clear the nuts under the board |
| 1 | Black adhesive foam, 2–3 mm (light seal round the lens on the hood roof) | [amazon.com](https://www.amazon.com/s?k=black+adhesive+foam+3mm) | $6 | buy |  |
| 1 | Double-sided foam tape (HX711, L9110S, vent valve) | [amazon.com](https://www.amazon.com/s?k=double+sided+foam+mounting+tape) | $6 | buy |  |
| 1 | Neoprene or EPDM strip, 1.5 mm thick, ≥ 18 mm wide (pump isolation sleeve) | [amazon.com](https://www.amazon.com/s?k=1.5mm+neoprene+rubber+strip) | $7 | buy | skip it if you can print the TPU sleeve |
| 1 | Zip ties 100 mm, black | [amazon.com](https://www.amazon.com/s?k=zip+ties+100mm) | $4 | buy |  |
| 1 | Heat-shrink tubing assortment | [amazon.com](https://www.amazon.com/s?k=heat+shrink+tubing+assortment) | $6 | buy |  |
| 1 | 600-grit sandpaper (lower ramp lanes, R-bar top) | [amazon.com](https://www.amazon.com/s?k=600+grit+sandpaper) | $5 | buy |  |
| 1 | 60 W soldering iron kit (heat-set inserts; M3 insert tip recommended) | [amazon.com](https://www.amazon.com/dp/B087767KNW) | $14 | **have** |  |
| 4 | PLA filament 1 kg | [amazon.com](https://www.amazon.com/s?k=PLA+filament+1kg) | $72 | buy | ≈ 3.4 kg, see printed parts |
| 1 | PETG filament 1 kg | [amazon.com](https://www.amazon.com/s?k=PETG+filament+1kg) | $20 | buy | ≈ 0.45 kg |
| 1 | Black PLA or PETG 1 kg (hood, card guides) | [amazon.com](https://www.amazon.com/s?k=black+PETG+filament+1kg) | $20 | buy | ≈ 0.2 kg |

Subtotal: $193 (have $14, verify $0, buy $179)

### Optional / fallback (not in the totals)

| Qty | Part | Example link | ~Price | Status | Notes |
|---|---|---|---|---|---|
| 1–2 | DS3218MG-270 servo (fallback if an MG996R will not reach 170° on the arm or 176° on ch2) | [amazon.com](https://www.amazon.com/s?k=DS3218MG+270+servo) | $15 | optional | per servo. Arm: `ARM_ACTUATION_RANGE = 270` in `hardware/servos.py`. ch2: `{"actuation_range": {"2": 270}}` in `config/shuttle_calibration.json`. Re-calibrate after either |
| 1 | 8.0 mm drill bit (ream roller bores, sled D bushings to Ø8.3) | [amazon.com](https://www.amazon.com/s?k=8mm+drill+bit) | $4 | optional |  |
| 1 | TPU 95A filament (pump sleeve, ~5 g) | [amazon.com](https://www.amazon.com/s?k=TPU+95A+filament) | $20 | optional | only if you have no neoprene strip |

Optional / fallback (not in the totals): $39

## Optional cost-down

These options cut the still-to-buy total **without changing the design**: the CAD, the code and the wiring stay as they are. Each has a trade-off.

| Option | Saves | Trade-off |
|---|---|---|
| 1. Drill the board from a printed template instead of printing 9 tiles | ≈ 1.1 kg PLA = 1 fewer spool, **~$18**, and ≈ 30 h of printing | Alignment comes from your drilling, not from printed tiles (below) |
| 2. Fixed-output 5 V buck modules from a quality brand instead of the three Pololus | **~$40–45** | Fixed-output only; derate; different footprint (below) |
| 3. Use the Arducam IMX708 already owned (if its PCB matches) | **$25** | Only if it is the official 25 × 23.862 mm board with 21 × 12.5 mm holes; otherwise it won't fit `camera_bracket.scad` |
| 4. A generic Ø16 silicone bellows pad instead of the SMC ZPT16BS-B5 | **~$10–12** | It must have an **M5 female thread and an 8 mm hex** to fit the cup sled. Cheap silicone can leave marks on foils: test it on bulk commons first. Buy 2 |
| 5. Budget PLA (≈ $13–15/kg) for the big, non-critical parts: tiles (if printed), riser, sorting tray, reject bin | **~$10–15** | Diameter and shrink vary between spools. Keep a good spool for the press fits: rails (608 pockets), hopper carriage and shuttle sled (LM8UU pockets), rollers |
| 6. Plain 8 mm rods with a filed flat instead of the two 150 mm D-shafts | **~$5** | You file a 4 mm wide, 0.5 mm deep flat full length by hand. Don't do this for the 400 mm tilt shaft: the tilt crank slides along it |

With options 1 and 2 the still-to-buy total is about **$549**. With 1–6 (and the Arducam fits), it is about **$495**.

### 1. Drilling template instead of printed tiles

<!-- PENDING CAD round 3: if the board switches to tee-nuts, this option needs re-checking -->

The 9 tiles are 1.2 L of the 4.0 L printed (≈ 1.2 kg of PLA). They do two jobs: they carry the 30 mm M3 grid every part bolts to, and they raise the floor 4 mm. You can replace them with a thin drilling template and drill the backing board directly.

- **Print one template** (≈ 67 cm³, ≈ 65 g): a 2 mm-thick tile from the same file. The key pockets break through at 2 mm and leave notches at the edges, which is harmless.

  ```bash
  openscad --backend=manifold -o template.stl -D 'part="tile"' -D tile_h=2 cad/baseplate_tile.scad
  ```

- **Use a thicker board.** Use 9 mm MDF or plywood instead of 6 mm. The tiles (4 mm) plus the 6 mm board are a 10 mm floor, so a 9 mm board keeps every clamp length within 1 mm of the design and **every screw in the fastener table still fits**. It also gives back the stiffness the tiles added. On a 6 mm board without tiles the screws still fit, but each sticks out 4 mm further underneath, so use rubber feet ≥ 15 mm.
- **Drill.** Draw the 3 × 3 tile outlines on the board (corners at X −285/−95/95/285, Y −270/−90/90/270, measured from the board centre). Clamp the template inside each outline in turn and drill only the holes in the ASSEMBLY.md §4 table: a Ø2 pilot through the template hole first, then Ø3.4. A drill press or drill guide is better than a hand drill.
- **Alignment: what you lose.** Printed tiles put every grid hole within about ±0.2 mm, and the keyed seams hold the tiles together to about ±0.3 mm. With a template, each hole's position is the template placement (≈ ±0.5 mm against a pencil line) plus drill wander (≈ ±0.3 mm), so holes on different template placements can be ≈ 1 mm out relative to each other. What that means for the build:
  - Parts whose holes span two tile areas may not drop onto all their bolts: the riser (anchors on tiles 1 and 2) and the electronics tray (holes on tiles 1 and 2). Open the **board** hole to Ø4–4.5 where needed. The part's own Ø3.4 holes still locate the screws, but the part can then shift a few tenths.
  - The shuttle end posts, lower ramp, sorting tray and reject bin are all on the +X tile column. Drill them with one template placement per tile and their relative accuracy is just drill wander. That matters most for the cradle-to-ramp gap (≈ 1 mm).
  - The cradle-to-tray column offset in Y is absorbed by the per-column calibration (ASSEMBLY.md §16.4). The belt-end-to-cradle gap in X has 7 mm of margin.
  - Everything stands 4 mm lower (on the board, not on a tile), but every height in the machine is relative to that surface, so nothing else changes.
- **Not needed** with this option: the 24 tile keys and the optional tile clamp screws.

### 2. Cheaper fixed-output 5 V regulators

The three Pololu modules cost about $71. Quality fixed-output modules cost about $25–30 for the same three rails.

| Rail | Need (power budget) | Example | ~Price |
|---|---|---|---|
| #1 logic | 1.3 A worst case | TRACO TSR 2-2450 (5 V 2 A, 6.5–36 V in, drop-in 7805 format) | $9 |
| #2 servo | 4 A peaks, 5 A rating | a potted 12 V → 5 V **5 A (25 W)** converter from an established brand (e.g. DROK) | $10–12 |
| #3 motor | 3.2 A double-stall worst case | a potted 12 V → 5 V **3 A** converter from the same kind of brand | $6–8 |

Rules, because this build has **no multimeter**:
- **Fixed output only.** The module must be sold as a 5 V output with no trimmer potentiometer. An adjustable module (LM2596 boards and the like) can't be set or checked without a meter, and a wrong setting kills the Pi or the servos.
- **Quality brands only:** TRACO, RECOM, Murata, Mean Well; on Amazon only an established seller (DROK, for example). Never an unbranded board.
- **Rated continuous current.** Many cheap "5 A" units are 5 A peak. Buy one rated 5 A (25 W) continuous for the servo rail. Avoid USB-socket car converters: they current-limit at 2.1–3 A.
- **Keep the capacitors** (3 × 1000 µF) exactly as in the Pololu wiring.
- **Mounting.** The tray's M2 posts are on the Pololu hole patterns, so the substitutes go on double-sided foam tape (plus a zip tie for the potted ones) in the same back strip. The tray itself doesn't change.
- **Check after power-up** (ASSEMBLY.md §14.1): `vcgencmd get_throttled` must print `throttled=0x0`, during an arm move as well.
