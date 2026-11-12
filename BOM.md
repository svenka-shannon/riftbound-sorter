# Riftbound Card Sorter: Bill of Materials (v2)

This is the BOM for the v2 machine (Nov 2026 redesign): a motor-raised hopper, a single-servo suction pick arm, a raised round-belt conveyor with a camera-centred stop, and a cradle shuttle that weighs every card and tips it into a 2-floor tray or a reject bin. Every quantity and dimension comes from the `cad/*.scad` files and `hardware/*.py`. The build guide is [`docs/ASSEMBLY.md`](docs/ASSEMBLY.md).

**Status column**
- **have**: the owner has this or has ordered it (confirmed list).
- **verify (Nov 5 order)**: the project notes list this in Amazon order #114-6087458-4005855. Check the parts box before you buy it.
- **buy**: still to buy.
- **optional**: fallback or upgrade only. Not in the totals.

Prices are approximate US prices from Nov 2026. Links are examples, not endorsements. Amazon links are searches because listings change.

## Totals

| | ~Cost |
|---|---|
| Already have / ordered (confirmed) | $170 |
| Probably on hand from the Nov 5 order (verify) | $36 |
| **Still to buy** | **$552** (parts $440 + filament $112) |
| Whole machine | ~$758 |

**Still-to-buy subtotal: ~$552.**
- If the "verify" items turn out to be missing, it rises to ~$588.
- If the Arducam IMX708 from the earlier order fits the camera bracket, it drops by $25.
- The owned 12 V 3 A adapter is counted under "have" but is **replaced** by a 12 V 5 A adapter (see Power budget). Keep the 3 A one for bench work.

### Still to buy (summary)

- **Electronics:** Pi Camera Module 3, SC1130 500 mm camera cable, **12 V 5 A adapter**, Pololu D24V22F5 + D24V50F5 + D36V28F5, 28BYJ-48 + ULN2003, 2 × Omron SS-5GL2-F, 5 V COB LED strip, 5 × 10 kΩ resistors, 1N5819 diode, 3 × 1000 µF capacitors, panel barrel jack, Wago lever connectors, servo extension leads, 4-core flexible lead, 26 AWG hook-up wire.
- **Motion:**
  - Conveyor: 2 × 8 mm D-shaft 150 mm, 4 × 135 × 3 O-rings, 4 × 8 mm collars, 2 × 3→8 couplings.
  - Hopper: 5→8 coupling, T8×8 lead screw + nut.
  - Shuttle: 400 mm rod, 400 mm D-shaft, 2 × 688ZZ.
  - Shared: 4 × LM8UU, 2 × 25T aluminium disc horns, 8 mm flange coupling, 4 mm silver-steel rod + 2 dowels, 8 × 6 tube, push-on washers, slider springs.
- **Pneumatics:** SMC ZPT16BS-B5 pad, M5 × 4 mm barb, 4 mm OD tube, pump adapter.
- **Fasteners:** M3 × 40, M3 × 80, M3 countersunk set, M3 set screws, M2/M2.5 set, M1.6 × 4.
- **Frame and consumables:** PTFE tape (required), 6 mm backing board, rubber feet, black foam, foam tape, zip ties, heat-shrink, 600-grit paper, ~3.3 kg PLA + ~0.5 kg PETG + ~0.2 kg black.

### Removed from the v1 BOM (no longer used)

- **Removed outright:**
  - 2 sort-gate levers and their M3 × 12 horn screws (`sort_gate_lever.scad`).
  - Hopper gate / gravity sled / exit slot / separation wedge.
  - The old vertical-axis swing arm and its arm post.
  - 8 × #010 (16 mm ID) O-rings and the roller O-ring grooves.
  - LED ring / WS2812B ring: it puts a glare spot on foils. Strips are used instead.
  - The separate weigh platform (the load cell now sits under the cradle).
  - 9 output bins (`output_bin.scad`).
  - "Pi Zero CSI adapter cable": replaced by the 500 mm SC1130.
  - GT2 belt and pulleys.
  - LM2596 adjustable bucks: replaced by fixed Pololu modules, because there is no multimeter.
- **On the Nov 5 order but not used by v2:** the 27 mm suction cup (it doesn't fit the sled), the 12 V 2 A adapter (too small), the 2 × LM2596, the WS2812B ring and the 16 mm O-rings.

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
| Relay coil | 0.07 A |
| R385 pump | 0.5–0.7 A at 12 V, ≈ 1 A start |

The v1 budget left out the stepper and put the N20s on the Pi's regulator; both are corrected here.

### Rails (three regulators)

| Rail | Source | Loads | Worst case | Rating | Verdict |
|---|---|---|---|---|---|
| 12 V | **12 V 5 A adapter** → barrel jack → Wago bus | Reg #1, #2, #3 VIN; relay COM → pump | Arm move with pump on: Reg #2 4 A × 5 V / 0.9 = 22.2 W, Reg #1 1.35 A → 7.8 W, pump 8.4 W → **38.4 W = 3.2 A** (+ pump inrush) | 5 A (60 W) | OK (64 %). **The owned 3 A adapter is not enough** (107 %). |
| 5 V logic | Reg #1, Pololu D24V22F5 (2.5 A) | Pi (GPIO pins 2/4), camera (via the Pi), LED strips, relay VCC. HX711 and **PCA9685 VCC run from the Pi's 3.3 V pin**. | Pi 0.6 + camera 0.25 + LEDs 0.3 + relay 0.07 ≈ **1.35 A**. Nothing on this rail can stall. | 2.5 A | OK (54 %) |
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
- 1N5819 (or 1N4007) flyback diode across the pump.
- 10 kΩ pull-downs on GPIO 23–26 (L9110S inputs).
- The existing 10 kΩ pull-up on GPIO 17.

**Why the pull-downs.** RPi.GPIO `cleanup()` (`conveyor.deinit()`, `vacuum.deinit()`) returns the pins to inputs with **no pull**, so they float. The SoC's pull-downs only apply from power-on until the program first configures the pin. The pull-downs hold the L9110S inputs LOW (coast) and the pull-up holds the relay input HIGH (pump off) whenever no program drives them. The ULN2003's inputs already have internal base-emitter resistors, so a floating stepper input stays off.

## Fastener counts (by step)

Screw lengths assume the **6 mm backing board** in this BOM. The general rule for through-bolts is clamp length + 4 mm (washer 0.5 + nut 2.4 + 1 mm of thread).

| Size | Qty | Where (ASSEMBLY.md step) |
|---|---|---|
| M3 × 4 set screw | 1 | tilt crank (§13.2, **do not tighten**, see Known risks) |
| M3 × 6 cup-point set screw | 2 | roller grub screws |
| M3 × 6 SHCS | 4 | arm crank → disc horn |
| M3 × 8 | 2 + 4 | 28BYJ-48 ears → cap inserts; ch1 disc horn ↔ flange coupling |
| M3 × 10 (4 of them BHCS) | 22 | motor mounts 4 (BHCS), rail feet on riser inserts 2, hopper cap 4, T8 nut 2, MG996R tabs (arm) 4, TF → load cell 2, load cell → cradle 2, rod clamps 2 |
| M3 × 10 countersunk | 2 | hopper floor plate → shelf inserts |
| M3 × 12 | 8 | riser joint 4 (+ nuts), arm head → tower 4 |
| M3 × 12 countersunk | 8 | tray stacking (self-taps into the Ø2.5 pilots) |
| M3 × 16 | 8 | camera bracket + rail feet (X −20, +10) 2, shuttle pivots 4 (+ nylocks), R-bar splice 2 |
| M3 × 20 | 21 | electronics tray 4, riser anchors 5, arm tower 4, lower ramp 4, end posts 4 (all + nut + washer) |
| M3 × 20 + nylock | 1 | hopper feeler-flag axle |
| M3 × 20 countersunk | 16 | hopper base 4, tray lower floor 8, reject bin 4 (all + nut + washer) |
| M3 × 40 SHCS | 2 | cup-slider guide screws |
| M3 × 80 (or 85 mm M3 threaded rod) | 4 | rail through-feet X −80 front, −120 / −80 / +10 back |
| M3 nuts / washers | 45 / 41 | under the board 41 (nut + washer each), riser joint 4 (nut only) |
| M3 nylock | 5 | shuttle pivots 4, flag axle 1 |
| M3 heat-set insert (Ø4.0–4.2 hole) | 34 | see ASSEMBLY.md §3 |
| M2 × 12 + nut | 4 | hopper switches |
| M2 × 10 self-tap | 4 | camera PCB |
| M2 × 8 | 4 | ch2 crank → round horn |
| M2.5 × 10 self-tap | 6 (8) | ch1 ears 2 (the shuttle BOM says 4, but the cage has only 2 pilots), ch2 ears 4 |
| M1.6 × 4 pan head | 4 | N20 gearbox faces |
| Optional M3 × 16 + nut | ~18 | tile → board at free grid holes (2 per tile) |

## Printed parts

Everything fits a 256 × 256 mm bed (Bambu P1S); the largest parts are the 242 mm R-bar half and the 240 mm card guides. Volumes are the solid volume of the exported mesh (`openscad --backend=manifold`). Most v2 parts are thin-walled, so the printed mass is about 75–90 % of solid × 1.24 g/cm³. **Total ≈ 3 980 cm³ solid, ≈ 4.0 kg of filament (3.3 kg PLA, 0.5 kg PETG, 0.2 kg black).** That is ten times the v1 estimate, mostly the 9 baseplate tiles (1.2 L) and the riser (0.7 L). Expect about 120 h of printing on a P1S; slice to confirm.

| Part | Qty | Material / settings | File (`part=` or module) | Print orientation | Supports | Solid cm³ (each) |
|---|---|---|---|---|---|---|
| Baseplate tile 190 × 180 × 4 | 9 | PLA 0.2, 4 walls, 40 % | `baseplate_tile.scad` (print **without** pins: `baseplate_tile();`) | flat | none | 135.5 |
| Electronics tray 185 × 125 × 45 | 1 | PLA 0.2, 40 % | `electronics_tray.scad` | floor down | none (10 mm slot bridges) | 123.3 |
| Riser A / Riser B | 1 + 1 | PLA/PETG 0.24, 3 walls, 15 % gyroid | `riser.scad` `riser_a`, `riser_b` | upside down (deck on bed) | none | 362 / 357.5 |
| Rail half, back | 2 | PLA 0.2, 4 walls, 40 % | `conveyor_rail.scad` `back1`, `back2` | inner face on bed | none | 16.5 |
| Rail half, front (motor side) | 2 | PLA 0.2, 4 walls, 40 % | `conveyor_rail.scad` `front1`, `front2` (pre-mirrored) | inner face on bed | none | 17.1 |
| Roller Ø22 × 88 | 2 | PLA/PETG, 4 walls, 60 % | `conveyor_roller.scad` `roller()` | axis vertical | none | 27.5 |
| Race spacer 11/8.3 × 1 | 4 | PLA/PETG | `conveyor_roller.scad` `race_spacer()` | flat | none | 0.04 |
| Motor mount | 2 | PETG/PLA 0.2, 4 walls, 40 % | `motor_mount.scad` | floor down | none | 14.9 |
| Slide bed 174 × 89 | 1 | PLA/PETG 0.2, 3 walls, 20 % | `slide_bed.scad` | upside down (lands on bed) | none | 89.3 |
| Card guide back / front | 1 + 1 | PETG (black if possible) 0.2, 3 walls, 20 % | `card_guide.scad` `guide_back`, `guide_front` | upside down (flat top on bed) | none | 21.7 |
| Guide clip | 4 | PETG | `card_guide.scad` `clip` | profile on bed | none | 0.3 |
| Scanner hood | 1 | **black** PLA/PETG 0.2, 3 walls, 15 % | `scanner_hood.scad` `hood` | roof down | none | 126.9 |
| Camera bracket | 1 | PLA/PETG 0.2, 4 walls, 30–40 % | `camera_bracket.scad` `print_orient=true` | on its −X side | none | 114.2 |
| Hopper body | 1 | PLA/PETG 0.2, 3–4 walls, 25–40 % | `hopper.scad` `body` | upright | none | 189.8 |
| Hopper cap | 1 | same | `hopper.scad` `cap` | top face down (pre-flipped) | none | 13.8 |
| Hopper carriage | 1 | same | `hopper.scad` `carriage` | upright | none | 36.1 |
| Hopper floor plate | 1 | same | `hopper.scad` `plate` | card face down on PEI | none | 25.1 |
| Feeler flag | 1 | same | `hopper.scad` `flag` | on its side | none | 1.0 |
| Arm head | 1 | PETG 0.2, 4 walls, 40 % gyroid | `suction_arm.scad` `head` | plate front face down | none | 49.3 |
| Arm tower (≈155 tall) | 1 | PETG, 30 % | `suction_arm.scad` `tower` | upright on foot | none | 118.2 |
| Arm crank | 1 | PETG, 5 walls, 100 % round the hub | `suction_arm.scad` `crank` | flat | none | 8.0 |
| Arm links B + C | 2 (one print) | PETG, 5 walls | `suction_arm.scad` `link` | flat | none | 3.8 |
| Arm hand | 1 | PETG | `suction_arm.scad` `hand` | back face down, beams up | none | 19.7 |
| Cup sled | 1 | PETG | `suction_arm.scad` `sled` | upright, hex pocket down | none | 5.4 |
| Arm sleeves (4 lengths) | 4 | PETG (or nylon spacers) | `suction_arm.scad` `sleeves` | upright | none | 2.8 total |
| Tray section A / B (lower) | 1 + 1 | PLA 0.2, 40 % | `sorting_tray.scad` `tray_floor_section(0,true,false)` / `(2,false,true)` | open top up | none (label windows bridge) | 102 |
| Tray section C / D (upper) | 1 + 1 | PLA 0.2, 40 % | `tray_floor_section(4,true,false)` / `(6,false,true)` | open top up | none | 90.5 |
| Tray shelf half | 2 | PLA | `floor_shelf_half()` | flat | none | 40.2 |
| Cradle | 1 | PLA **0.12**, 3 walls, 15 %, iron top | `shuttle.scad` `cradle` | bed top up | none | 13.4 |
| Tilt frame | 1 | PETG 0.2, 4 walls, 40 % | `shuttle.scad` `tilt_frame` | upright, crossbar down | **tree supports** under plate bottom edges + skid nubs | 18.7 |
| Carriage | 1 | PETG 0.2, 4 walls, 40 % | `shuttle.scad` `carriage` | on its −y face | none stated; check preview | 101.1 |
| Tilt crank / tilt link | 1 + 1 | PETG 100 % | `shuttle.scad` `tilt_crank`, `tilt_link` | flat | none | 2.1 / 0.9 |
| ch2 crank (155 mm) | 1 | PETG 0.2, 5 walls, 50 % | `shuttle.scad` `c2_crank` | flat | none | 8.1 |
| ch2 link (173 mm) | 1 | PETG | `shuttle.scad` `c2_link` | flat | none | 6.3 |
| R-bar −Y / +Y | 1 + 1 | PLA, 4 walls | `shuttle.scad` `rbar_neg`, `rbar_pos` | on the −X face; sand the top | none | 16.7 / 26.2 |
| End post −Y / +Y | 1 + 1 | PETG/PLA 4 walls, 40 % | `shuttle.scad` `end_post_neg`, `end_post_pos` | upright | none | 27.4 / 13.6 |
| Lower ramp halves | 2 | PLA **0.16**, 3 walls, 15 % | `lower_ramp.scad` `ramp_neg`, `ramp_pos` | on the −X (rear) face | none; sand lanes 600 grit | 68.6 |
| Reject bin | 1 | PLA 0.2, 3 walls, 15 % | `reject_bin.scad` | upright | none | 78.8 |

Not printed in v2: `sort_gate_lever.scad`, `output_bin.scad`. These files are wrappers or helpers with no part of their own: `machine_frame.scad`, `shuttle_geom.scad`, `hopper_elevator.scad`, `assembly.scad`.

## Purchased parts

### Electronics

| Qty | Part | Example link | ~Price | Status | Notes |
|---|---|---|---|---|---|
| 1 | Raspberry Pi Zero 2 W starter kit (board, header, microSD, case, PSU) | [amazon.com](https://www.amazon.com/s?k=CanaKit+Raspberry+Pi+Zero+2+W+starter+kit) | $40 | **have** | CanaKit kit; SD card from the kit |
| 1 | Raspberry Pi Camera Module 3, standard lens (IMX708, 66° × 41°) | [adafruit.com](https://www.adafruit.com/product/5657) | $25 | buy | Project notes show an Arducam IMX708 (B0G5YJMR8Q) on an earlier order. Use it only if its PCB is the official 25 × 23.862 mm board with 21 × 12.5 mm holes (camera_bracket.scad) |
| 1 | Raspberry Pi camera cable Standard–Mini 500 mm, part SC1130 (22-pin 0.5 mm ↔ 15-pin 1 mm) | [digikey.com](https://www.digikey.com/en/products/detail/raspberry-pi/SC1130/21658263) | $3 | buy | Route is ≈ 440–490 mm, see ASSEMBLY.md §14.5 |
| 1 | PCA9685 16-ch 12-bit PWM board (I²C 0x40) | [amazon.com](https://www.amazon.com/s?k=PCA9685+16+channel+servo+driver) | $7 | **have** |  |
| 3 | MG996R metal-gear servo: ch0 arm, ch1 cradle tilt, ch2 shuttle | [amazon.com](https://www.amazon.com/dp/B07MFK266B) | $19 | **have** | 4-pack ordered, so 1 spare. Must reach ~170° (arm) and ~176° (ch2): test first |
| 1 | HX711 amplifier + TAL221 50 g mini load cell (47 × 12 × 6, 4 × M3) | [amazon.com](https://www.amazon.com/dp/B09K7G3477) | $10 | **have** |  |
| 1 | 1-ch 5 V relay module, active-LOW input | [amazon.com](https://www.amazon.com/dp/B00VRUAHLE) | $6 | **have** |  |
| 1 | 12 V R385 diaphragm pump (Gikfun), used as the vacuum source | [amazon.com](https://www.amazon.com/dp/B0744FWNFR) | $10 | **have** | 0.5–0.7 A at 12 V |
| 2 | N20 gear motor 6 V 200 rpm (GA12-N20, 3 mm D-shaft) | [amazon.com](https://www.amazon.com/dp/B0DFVHGZS4) | $13 | **have** | price is the 2-pack |
| 1 | L9110S dual H-bridge board | [amazon.com](https://www.amazon.com/dp/B0FTFLK1FC) | $7 | **have** | 3-pack ordered |
| 1 | 12 V 3 A DC adapter, 5.5 × 2.1 mm, centre + (owned, **to be replaced**) | [amazon.com](https://www.amazon.com/dp/B0CQ7M3MM1) | $9.50 | **have** | too small: the arm-move peak is ≈ 3.2 A at 12 V (power budget). Keep it as a bench supply |
| 1 | 12 V 5 A (60 W) DC adapter, 5.5 × 2.1 mm, centre + (main supply) | [amazon.com](https://www.amazon.com/s?k=12V+5A+power+adapter+5.5x2.1) | $14 | buy | replaces the 3 A adapter |
| 1 | Pololu D24V22F5: fixed 5 V 2.5 A buck (regulator #1, logic rail) | [pololu.com](https://www.pololu.com/product/2858) | $19 | buy |  |
| 1 | Pololu D24V50F5: fixed 5 V 5 A buck (regulator #2, servo rail: PCA9685 V+ only) | [pololu.com](https://www.pololu.com/product/2851) | $30 | buy |  |
| 1 | Pololu D36V28F5: fixed 5 V 3.2 A buck (regulator #3, motor rail: L9110S/N20s + ULN2003/28BYJ-48) | [pololu.com](https://www.pololu.com/product/3782) | $22 | buy |  |
| 1 | 28BYJ-48 5 V geared stepper + ULN2003 driver board | [amazon.com](https://www.amazon.com/s?k=28BYJ-48+5V+stepper+ULN2003+driver) | $8 | buy | hopper elevator |
| 2 | Omron SS-5GL2-F micro switch, roller lever (top-of-stack + home) | [digikey.com](https://www.digikey.com/en/products/result?keywords=SS-5GL2-F) | $7 | buy | hopper.scad footprint 19.8 × 6.4 × 10.2, Ø2.35 holes 9.5 apart. SS-01GL2-E halves the force on the card |
| 1 | 5 V white COB LED strip, 8 mm wide, cuttable at ≤ 22 mm (2 × 88 mm used) | [amazon.com](https://www.amazon.com/s?k=5V+COB+LED+strip+8mm+white) | $8 | buy | hood LED bands are 10 mm tall, 88 mm long per side |
| 5 | 10 kΩ ¼ W resistor: 1 pull-up GPIO 17 → 3.3 V, 4 pull-downs GPIO 23–26 → GND | [amazon.com](https://www.amazon.com/s?k=10k+ohm+resistor) | $2 | buy | RPi.GPIO cleanup() leaves pins floating with no pull |
| 1 | 1N5819 (or 1N4007) diode across the pump | [amazon.com](https://www.amazon.com/s?k=1N5819+diode) | $1 | buy |  |
| 3 | 1000 µF 16 V electrolytic capacitor: servo-rail regulator output, PCA9685 V+, motor-rail regulator output | [amazon.com](https://www.amazon.com/s?k=1000uF+16V+capacitor) | $3 | buy |  |
| 1 | Panel-mount DC barrel jack 5.5 × 2.1 mm | [amazon.com](https://www.amazon.com/s?k=panel+mount+DC+barrel+jack+5.5x2.1) | $3 | buy | drill the tray's +Y wall |
| 1 | Lever splice connectors (Wago 221, 3- and 5-way): 12 V, 5 V logic, 5 V servo, 5 V motor, GND buses | [amazon.com](https://www.amazon.com/s?k=Wago+221+lever+connector) | $8 | buy |  |
| 1 | Servo extension leads, 100 cm (pack of 5) | [amazon.com](https://www.amazon.com/s?k=servo+extension+cable+100cm) | $8 | buy | ch0, ch1, ch2 to the tray |
| 1 | 4-core flexible lead, 26–28 AWG silicone, 1 m (load-cell trailing loop) | [amazon.com](https://www.amazon.com/s?k=4+core+silicone+wire+26AWG) | $7 | buy |  |
| 1 | 26 AWG stranded hook-up wire, 6 colours (signal extensions, switches, stepper) | [amazon.com](https://www.amazon.com/s?k=26+AWG+stranded+hookup+wire+kit) | $12 | buy |  |
| 1 | 22 AWG stranded wire (power runs) | [amazon.com](https://www.amazon.com/dp/B07HGT44XY) | $11.50 | **have** |  |
| 1 | M2.5 brass standoff + screw + nut kit (PCB mounts) | [amazon.com](https://www.amazon.com/dp/B0G1XNRC53) | $13 | **have** |  |
| 1 | Micro-USB cable (bench power only, never with regulator #1 connected) | [amazon.com](https://www.amazon.com/dp/B01NBHYAR0) | $10 | **have** |  |
| 1 | Dupont jumper wires (bench tests) | [amazon.com](https://www.amazon.com/dp/B01EV70C78) | $7 | verify (Nov 5 order) |  |

Subtotal: $343 (have $156, verify $7, buy $180)

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
| 4 | LM8UU linear bearing 8 × 15 × 24 (2 hopper carriage, 2 shuttle carriage) | [adafruit.com](https://www.adafruit.com/product/1181) | $8 | buy |  |
| 1 | 8 mm smooth (h6, hardened) rod, 400 mm (shuttle) | [amazon.com](https://www.amazon.com/s?k=8mm+linear+rod+400mm) | $10 | buy |  |
| 1 | 8 mm D-shaft, 400 mm (shuttle tilt; ≈7.5 mm across the flat) | [amazon.com](https://www.amazon.com/s?k=8mm+D+shaft+400mm) | $15 | buy | check against d_bore() in shuttle.scad (flat at 3.55 mm) |
| 2 | 688ZZ bearing 8 × 16 × 5 (D-shaft, one per end post) | [amazon.com](https://www.amazon.com/s?k=688ZZ+bearing) | $6 | buy |  |
| 2 | 25T aluminium disc servo horn, Ø25, 4 × M3 (arm crank; ch1 D-shaft coupler) | [amazon.com](https://www.amazon.com/s?k=25T+aluminum+servo+horn+disc+25mm) | $8 | buy |  |
| 1 | Rigid flange coupling, 8 mm bore (bolts to the ch1 disc horn = 25T → D-shaft coupler) | [amazon.com](https://www.amazon.com/s?k=8mm+rigid+flange+coupling) | $6 | buy | hole PCD must match the horn; see ASSEMBLY.md §13.4 |
| 1 | Ø4 mm silver-steel rod 330 mm (arm pins: 38 + 29.5 + 13 + 21.5 mm) + 2 × Ø4 × 8 dowel pins (shuttle F pins) | [amazon.com](https://www.amazon.com/s?k=4mm+silver+steel+rod) | $10 | buy |  |
| 1 | 8 × 6 mm brass or aluminium tube, ≥ 31 mm (hollow A' pin, cut 30.5) | [amazon.com](https://www.amazon.com/s?k=8mm+OD+6mm+ID+aluminum+tube) | $6 | buy |  |
| 1 | Flat push-on retaining washers: 4 × for Ø4 pins (≤ 0.5 mm thick), 1 × for Ø8 | [amazon.com](https://www.amazon.com/s?k=push+on+retaining+washer+4mm+starlock) | $7 | buy |  |
| 2 | Compression spring ≈ 0.3 wire × 5 OD × 18 free, ≤ 0.1 N/mm (cup slider) | [amazon.com](https://www.amazon.com/s?k=compression+spring+assortment+0.3mm) | $8 | buy |  |

Subtotal: $145 (have $0, verify $13, buy $132)

### Pneumatics

| Qty | Part | Example link | ~Price | Status | Notes |
|---|---|---|---|---|---|
| 1 | SMC ZPT16BS-B5 bellows vacuum pad, Ø16 silicone, M5 female, 8 mm hex | [uk.rs-online.com](https://uk.rs-online.com/web/p/pneumatic-suction-cups/7681662) | $18 | buy | the 27 mm cup on the Nov 5 order does not fit the sled's 8 mm hex pocket |
| 1 | Festo CN-M5-PK-3 barb (M5 male → 4 mm OD tube), or any M5 × 4 mm barb | [amazon.com](https://www.amazon.com/s?k=M5+male+barb+4mm+tube+fitting) | $6 | buy |  |
| 1 | 4 mm OD vacuum tube, 1 m (PU PUN-H-4×0.75 or 2 × 4 silicone) | [amazon.com](https://www.amazon.com/s?k=4mm+OD+polyurethane+tube) | $6 | buy | route is ≈ 0.45 m; the Nov 5 '4 mm silicone tubing' works only if it is 4 mm OD |
| 1 | Pump adapter: 5 cm silicone sleeve to fit the R385 nozzle + reducing barb to 4 mm | [amazon.com](https://www.amazon.com/s?k=reducing+barb+connector+6mm+to+4mm) | $5 | buy | connect the cup to the pump INLET |

Subtotal: $35 (have $0, verify $0, buy $35)

### Fasteners and inserts

| Qty | Part | Example link | ~Price | Status | Notes |
|---|---|---|---|---|---|
| 34 | M3 brass heat-set insert for a Ø4.0–4.2 mm hole, 5.7 mm long (Ruthex / CNC Kitchen M3×5.7) | [amazon.com](https://www.amazon.com/dp/B0DYPKB5V7) | $8 | verify (Nov 5 order) | 50-pack on the Nov 5 order |
| 1 | M3 SHCS/BHCS assortment 6–20 mm with nuts, washers and nylocks (counts in the table below) | [amazon.com](https://www.amazon.com/dp/B0GDG2WGRV) | $8 | verify (Nov 5 order) | assortment on the Nov 5 order; check it covers the counts |
| 2 | M3 × 40 SHCS (cup-slider guide screws) | [amazon.com](https://www.amazon.com/s?k=M3x40+socket+head) | $3 | buy |  |
| 4 | M3 × 80 SHCS (rail through-feet) or M3 threaded rod, 85 mm, + extra nuts | [amazon.com](https://www.amazon.com/s?k=M3x80+socket+head+screw) | $5 | buy |  |
| 1 | M3 countersunk (ISO 10642) assortment: 2 × M3×10, 8 × M3×12, 16 × M3×20 | [amazon.com](https://www.amazon.com/s?k=M3+countersunk+screw+assortment) | $8 | buy |  |
| 1 | M3 set screws: 2 × M3×6 cup point (rollers), 1 × M3×4 (tilt crank) | [amazon.com](https://www.amazon.com/s?k=M3+set+screw+assortment) | $4 | buy |  |
| 1 | M2 / M2.5 assortment: 4 × M2×12 + nuts (switches), 4 × M2×10 self-tap (camera), 4 × M2×8 (ch2 horn), 8 × M2.5×10 self-tap (servo ears) | [amazon.com](https://www.amazon.com/s?k=M2+M2.5+self+tapping+screw+assortment) | $8 | buy |  |
| 4 | M1.6 × 4 pan head (N20 gearbox face) | [amazon.com](https://www.amazon.com/s?k=M1.6x4+screw) | $5 | buy |  |

Subtotal: $49 (have $0, verify $16, buy $33)

### Consumables and frame

| Qty | Part | Example link | ~Price | Status | Notes |
|---|---|---|---|---|---|
| 1 | 0.1 mm skived PTFE tape, self-adhesive (silicone), ≥ 75 mm wide (cradle bed + kick) — REQUIRED | [amazon.com](https://www.amazon.com/s?k=skived+PTFE+tape+0.1mm+adhesive+75mm) | $15 | buy |  |
| 1 | Backing board, 6 mm plywood/MDF, ≥ 570 × 540 mm | [amazon.com](https://www.amazon.com/s?k=6mm+plywood+sheet+24x24) | $12 | buy |  |
| 1 | Rubber feet ≥ 10 mm tall (8) | [amazon.com](https://www.amazon.com/s?k=rubber+feet+10mm+adhesive) | $6 | buy | clear the nuts under the board |
| 1 | Black adhesive foam, 2–3 mm (light seal round the lens on the hood roof) | [amazon.com](https://www.amazon.com/s?k=black+adhesive+foam+3mm) | $6 | buy |  |
| 1 | Double-sided foam tape (regulators, relay, L9110S, ULN2003, pump) | [amazon.com](https://www.amazon.com/s?k=double+sided+foam+mounting+tape) | $6 | buy |  |
| 1 | Zip ties 100 mm, black | [amazon.com](https://www.amazon.com/s?k=zip+ties+100mm) | $4 | buy |  |
| 1 | Heat-shrink tubing assortment | [amazon.com](https://www.amazon.com/s?k=heat+shrink+tubing+assortment) | $6 | buy |  |
| 1 | 600-grit sandpaper (lower ramp lanes, R-bar top) | [amazon.com](https://www.amazon.com/s?k=600+grit+sandpaper) | $5 | buy |  |
| 1 | 60 W soldering iron kit (heat-set inserts; M3 insert tip recommended) | [amazon.com](https://www.amazon.com/dp/B087767KNW) | $14 | **have** |  |
| 4 | PLA filament 1 kg | [amazon.com](https://www.amazon.com/s?k=PLA+filament+1kg) | $72 | buy | ≈ 3.3 kg, see printed parts |
| 1 | PETG filament 1 kg | [amazon.com](https://www.amazon.com/s?k=PETG+filament+1kg) | $20 | buy | ≈ 0.5 kg |
| 1 | Black PLA or PETG 1 kg (hood, card guides) | [amazon.com](https://www.amazon.com/s?k=black+PETG+filament+1kg) | $20 | buy | ≈ 0.2 kg |

Subtotal: $186 (have $14, verify $0, buy $172)

### Optional / fallback (not in the totals)

| Qty | Part | Example link | ~Price | Status | Notes |
|---|---|---|---|---|---|
| 1–2 | DS3218MG-270 servo (fallback if an MG996R will not reach 170°) | [amazon.com](https://www.amazon.com/s?k=DS3218MG+270+servo) | $15 | optional | per servo; ch2 needs a code change too |
| 1 | M3 tap (tilt crank set-screw hole, Ø2.6) | [amazon.com](https://www.amazon.com/s?k=M3+tap) | $5 | optional |  |
| 1 | 8.0 mm drill bit (ream roller bores, carriage bushings to Ø8.3) | [amazon.com](https://www.amazon.com/s?k=8mm+drill+bit) | $4 | optional |  |

Optional / fallback (not in the totals): $24

