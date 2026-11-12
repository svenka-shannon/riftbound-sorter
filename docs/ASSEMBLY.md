# Riftbound Card Sorter: Build Guide (v2)

This guide covers the v2 machine from the Nov 2026 redesign:
- **Hopper:** a motor-raised floor, so the top card always sits at pick height.
- **Pick arm:** one servo, a parallelogram linkage and a suction cup. It lifts the card straight up and puts it down flat on the belt.
- **Conveyor:** a 60 mm riser carries 4 round O-ring belts. The belt stops when the camera sees the card centred under the lens.
- **Cradle shuttle:** it receives the card at the belt end, weighs it at rest, moves it to one of 4 columns or the reject bin, and tips it into the upper or lower floor of the 2-floor tray.

The cards are **valuable raw (unsleeved) cards**. Build and calibrate with **bulk commons only** (§17), and read **§19 Known risks / test first** before you print anything big.

Every dimension and screw below comes from `cad/*.scad` or `hardware/*.py`; the file is cited where it isn't obvious. Machine coordinates (`cad/machine_frame.scad`, `cad/assembly.scad`):
- **X**: card travel (hopper → belt → shuttle → tray).
- **Y**: across the belt. +Y is the back, where the electronics are.
- **Z**: up. Z 0 is the underside of the baseplate tiles and the baseplate top is Z 4.

Parts and prices are in [`BOM.md`](../BOM.md). The wiring diagram is [`docs/wiring_diagram.svg`](wiring_diagram.svg).

## Contents

1. [Before you start](#1-before-you-start)
2. [Print list and settings](#2-print-list-and-settings)
3. [Heat-set inserts](#3-heat-set-inserts)
4. [Step 1: baseplate and backing board](#4-step-1-baseplate-and-backing-board)
5. [Step 2: electronics tray](#5-step-2-electronics-tray)
6. [Step 3: conveyor riser](#6-step-3-conveyor-riser)
7. [Step 4: rails, bearings, motor mounts](#7-step-4-rails-bearings-motor-mounts)
8. [Step 5: slide bed, belts, rollers, rods, collars](#8-step-5-slide-bed-belts-rollers-rods-collars)
9. [Step 6: scan station](#9-step-6-scan-station)
10. [Step 7: hopper elevator](#10-step-7-hopper-elevator)
11. [Step 8: pick arm](#11-step-8-pick-arm)
12. [Step 9: sorting tray](#12-step-9-sorting-tray)
13. [Step 10: cradle shuttle, load cell, lower ramp, reject bin](#13-step-10-cradle-shuttle-load-cell-lower-ramp-reject-bin)
14. [Step 11: wiring and vacuum](#14-step-11-wiring-and-vacuum)
15. [Software setup](#15-software-setup)
16. [Calibration (in this order)](#16-calibration-in-this-order)
17. [First run: bulk commons only](#17-first-run-bulk-commons-only)
18. [Troubleshooting](#18-troubleshooting)
19. [Known risks / test first](#19-known-risks--test-first)
20. [Where the code and the CAD disagree](#20-where-the-code-and-the-cad-disagree)

---

## 1. Before you start

**Machine layout** (`cad/assembly.scad` header):

| Assembly | Where |
|---|---|
| Baseplate | 3 × 3 tiles of 190 × 180, X −285..285, Y −270..270, top Z 4 |
| Electronics tray | X −150..35, Y 80..205 |
| Riser | X −165..85, Y −113..80, Z 4..64 (the deck is the rail base) |
| Conveyor | Belt X −165..85. Rollers at X −140 / +60, rod axis Z 79. Card face (belt top) Z 90.9. Slide bed X −127..47. Rail top Z 99. |
| Scan station | Hood X −49..59. Lens axis X +5. Lens tip Z 190.9 (100 mm above the card). |
| Hopper elevator | Cavity centre X −215, Y 0. Footprint X −263.5..−166.5. Rim Z 94.4. Motor top Z ≈ 158. |
| Pick arm | Servo axis X −154.7, Z 151.8. Tower Y −173..−122. Pick at X −215, drop (card centre) at X −95. |
| Shuttle | Cradle X 92..169. Carriage rod at X 106, Z 24. Carriage centre travels Y −102..176. |
| Sorting tray | X 178..276, Y −137..137, open back face at X 178 |
| Reject bin | Y 176 (beside the tray), X 178..276 |

**One sort cycle** (`main.py`):
1. The elevator raises the stack until the feeler flag trips.
2. The arm picks the card (pump on), carries it over the top and holds it 3 mm above the belt at X −95. The pump goes off, the card is released, and the arm parks.
3. The belt runs until `card_detect` sees the card centred under the lens at X +5, then brakes.
4. The camera captures and the card is identified.
5. The belt runs `EXIT_TRAVEL_S` and the card slides onto the cradle (home, level).
6. The cradle tips to HOLD (10°) and the card is weighed at rest.
7. If the target bin is full, the machine pauses with the card held on the cradle.
8. The shuttle moves to the column and tips the card into the upper or lower floor, or into the reject bin.
9. The cradle is checked empty, re-tared and levelled.

**Tools:**
- 60 W soldering iron with an M3 heat-set insert tip.
- Hex keys 1.5–2.5 mm.
- Small Phillips screwdriver.
- Calipers.
- Drill with Ø3.4 and Ø8.0 bits.
- Hacksaw or Dremel for cutting the 4 mm rod and the 8 × 6 tube.
- Fine file.
- Utility knife.
- Optional M3 tap.

There is **no multimeter** in this build, which is why all three regulators are fixed-output Pololu modules. Never substitute an adjustable buck without a meter.

---

## 2. Print list and settings

The full list is the **Printed parts** table in `BOM.md`: part, quantity, material, file/selector, orientation and supports. Summary:
- **PLA:** baseplate tiles, electronics tray, riser, rails, rollers, slide bed, camera bracket, hopper, sorting tray, cradle, R-bars, lower ramp, reject bin.
- **PETG:** arm (all parts), card guides and clips, tilt frame, carriage, tilt crank and link, ch2 crank and link, end posts. Motor mounts can be PETG or PLA.
- **Black:** scanner hood (PLA or PETG). Make the card guides black too if you can.

| Setting | Value |
|---|---|
| Layer | 0.2 mm. Exceptions: cradle 0.12 mm (iron the top), lower ramp 0.16 mm, riser 0.24 mm. |
| Walls | 3–4 (5 for arm crank, links and ch2 crank) |
| Infill | 15–40 % per part (BOM table). Crank hub, tilt crank and tilt link 100 %. |
| Supports | **None** for every part except the shuttle **tilt frame** (tree supports under the plate bottom edges and the skid nubs). |
| Bed | All parts fit 256 × 256 mm (Bambu P1S). |

Notes:
- **Export:** `openscad --backend=manifold -o part.stl -D 'part="cradle"' cad/shuttle.scad`. The `sorting_tray.scad` sections and the rollers are picked by editing the last lines of the file or with a wrapper `use <…>` file.
- **Baseplate tiles:** print **without pins**, using `baseplate_tile();` with all options false. The file's default render adds pins on the top and right edges, but no tile variant has matching holes on the bottom and left edges, so the pins can't engage. Alignment comes from the backing board and the bolts.
- **Arm XY scale test:** before the arm head and hand, print a 50 mm XY scale test. The two plates only need to carry the *same* pivot pattern (`suction_arm.scad`), so print both links in one job.
- **Suggested print order** (long prints first): 9 tiles; riser A/B; tray sections; hopper body; arm tower; everything else.

**Post-processing:**
- **Rails:** none needed. The 608 pockets are Ø22.15 press fits; tune ±0.05 if they print tight or loose.
- **Rollers:** ream the bore with an 8 mm drill bit, keeping the D-flat.
- **Carriage:** ream the D-shaft bushings to Ø8.3.
- **Tilt frame:** ream the F-pin holes to Ø3.9.
- **Lower ramp:** sand the lanes with 600 grit.
- **R-bar:** sand the top.
- **Cradle:** cover the bed and kick with PTFE tape (§13.1).

---

## 3. Heat-set inserts

Fit **all 34 inserts before any part is assembled**. Use M3 brass inserts for a Ø4.0–4.2 mm hole, 5.7 mm long (Ruthex / CNC Kitchen type).

Technique:
- Iron temperature: 210–220 °C for PLA, 230–245 °C for PETG.
- Use the insert tip and press straight down with light pressure.
- Stop about 0.3 mm proud, then flatten the insert flush with a steel ruler and hold it 10–30 s.
- **Check:** an M3 screw threads in by hand and the insert does not spin.

Every insert hole in the design (grep of `cad/*.scad` for insert holes Ø4.0/4.1):

| Part | Qty | Where / hole | Takes |
|---|---|---|---|
| Rail `front1` | 2 | Ø9 pads ±15 mm either side of the shaft, 9 mm above it; Ø4.1 blind 9 mm (`conveyor_rail.scad`) | motor mount, M3 × 10 BHCS |
| Rail `front2` | 2 | same | motor mount, M3 × 10 BHCS |
| Roller | 1 each = 2 | radial Ø4.0 × 6 at mid-length, on the flat side (`conveyor_roller.scad`) | M3 × 6 cup-point grub onto the rod flat |
| Riser A | 1 | deck top at front foot X −50, Y −75 (Ø4.0 × 7, 14 mm relief below) | rail foot, M3 × 10 |
| Riser B | 3 | deck top at front feet X −20, +10 (Y −75) and back foot X 40 (Y +75) | front: rail foot + camera bracket, M3 × 16. Back: rail foot, M3 × 10. |
| Hopper body | 4 | tower walls under the cap, local (±44.5, 41) and (±44.5, 64.5), Ø4.0 × 6.1 | cap, M3 × 10 |
| Hopper cap | 2 | motor-ear bosses on the underside, 35 mm apart | 28BYJ-48 ears, M3 × 8 |
| Hopper carriage | 2 | top face, ±8 mm (PCD 16) beside the T8 bore | T8 nut flange, M3 × 10 |
| Hopper carriage | 2 | shelf, local (±9, 26.5), through 7 mm | floor plate, M3 × 10 countersunk |
| Arm head | 4 | back face of the ground plate, servo tab pattern 10 × 49.5 (Ø4.1 × 6.2) | MG996R tabs, M3 × 10 |
| Arm tower | 4 | column top, (±5, Y −134/−126) relative to the servo axis | head, M3 × 12 |
| Arm hand | 2 | beam tops at X ±12 (horizontal when printed) | guide screws, M3 × 40 |
| Shuttle cradle | 2 | boss underside, on the load-cell free end (Y ±3) | M3 × 10 through the cell |
| R-bar −Y (`rbar_neg`) | 2 | lap-splice top at Y ±5, Ø4.0 × 8 | splice, M3 × 16 |
| **Total** | **34** | | |

Everything else is either a clearance hole (Ø3.2–3.6, with a nut) or a deliberate self-tapping pilot:
- Ø2.5: tray stacking.
- Ø2.6: rod clamps, tilt-crank set screw, ch1 ear screws, guide-screw tails.
- Ø2.2: M2.5 servo ears, M2 switch holes.
- Ø1.8: camera M2, ch2 horn M2.

**Never press an insert into a clearance hole.**

---

## 4. Step 1: baseplate and backing board

Parts: 9 tiles; a 6 mm plywood/MDF board at least 570 × 540; 8 rubber feet. Optionally 18 × M3 × 16 with nuts and washers.

1. Lay the 9 tiles on the board in a 3 × 3 grid with no gaps: 570 × 540 mm, tile corners at X −285/−95/95/285 and Y −270/−90/90/270. Each tile has a 30 mm M3 grid starting 15 mm in from its corner.
2. Tape the tiles down and use them as a drill template. Drill **Ø3.4 through the board** at every hole a later step uses:

| Step | Machine X | Machine Y |
|---|---|---|
| Hopper | −240, −180 | ±15 |
| Arm tower | −180, −120 | −165, −135 |
| Riser anchors | (−150, −105), (−150, 75), (−80, −15), (−20, 75), (−20, 45) | |
| Rail through-feet | (−80, −75), (−120, 75), (−80, 75), (10, 75) | |
| Sorting tray | 200, 260 | −105, −45, 45, 105 |
| Lower ramp | 140 | ±45, ±105 |
| Reject bin | 200, 230 | 165, 195 |

   Holes **not** on the grid are drilled later through the part itself: electronics tray (§5) and shuttle end posts (§13).
3. Optional: clamp each tile with 2 × M3 × 16 + washer + nut at free grid holes.
4. Stick 8 rubber feet (≥ 10 mm tall) under the board, clear of the nut positions above. The nuts and screw tips stick out up to ~7 mm.

**Check:**
- A straightedge across tile joints shows no step over 0.3 mm.
- The board doesn't rock.

**Screw-length rule for every through-bolt in this guide:** clamp length + 4 mm (washer 0.5, nut 2.4, ≥ 1 mm of thread). Lengths below assume this 6 mm board. Some SCAD comments assume no board (arm tower M3 × 16) or a 12 mm one (rail notes); see §20.

---

## 5. Step 2: electronics tray

Parts: electronics tray; Pi Zero 2 W, PCA9685 and HX711 on M2.5 standoffs; relay, L9110S, ULN2003 and the three Pololu regulators on foam tape; barrel jack; Wago connectors. Screws: 4 × M3 × 20 + nut + washer.

1. **Barrel jack.** Drill the panel jack's hole in the tray's **+Y (back) wall**, which faces the back of the machine. The CAD has no hole for it.
2. **Place the tray** at X −150..35, Y 80..205: its front face touches the riser's back face at Y 80. Its 4 corner holes (Ø3.4, tray-local 8 mm from each corner) land at machine X −142 / 27, Y 88 / 197. **That is off the 30 mm grid** (§20), so drill Ø3.4 through tile and board using the tray as the template. Fasten with **4 × M3 × 20**, head inside the tray, washer + nut under the board.
3. **Mount the boards:**
   - **Pi Zero 2 W** on the standoffs at tray-local (10, 10), (68, 10), (10, 33), (68, 33). This is the 58 × 23 pattern at the tray's −X end, i.e. machine X −140..−82, Y 90..113. Turn it so the **camera (CSI) connector faces +X**: the 500 mm ribbon only reaches with this orientation (§14.5).
   - **PCA9685** on the standoffs at tray-local x 100/125, y 10/70 (a 25 × 60 pattern). The common PCA9685 board has holes about 19 × 56 mm, so check yours. If it doesn't match, use foam tape (§20).
   - **HX711** on the 20 × 15 standoffs at tray-local (150, 75).
   - **Relay, L9110S, ULN2003 board, the three Pololu regulators (logic, servo, motor) and the Wago buses:** double-sided foam tape on the floor. Keep the regulators apart and away from the Pi. They get hot.
4. Ignore the 60 × 12 × 3 recess in the tray top. It was the v1 load-cell pocket and is unused (§20).

The tray has cable slots on both X walls: 10 × 6 mm at machine Y 100–110, 130–140 and 160–170, Z 40.5–46.5. The **−X** slots were added for the short harness route (§14.4).

**Check:**
- The tray sits flat and touches the riser footprint line at Y 80 without overlapping it.
- The Pi CSI connector is at the +X end of the board.

---

## 6. Step 3: conveyor riser

Parts: `riser_a` (X −165..−40) and `riser_b` (X −40..85). Screws:
- 4 × M3 × 12 + nut: joint.
- 5 × M3 × 20 + nut + washer: anchors.

1. Bolt A to B through the joint walls at X −40 with 4 × M3 × 12 + nut (Y −95, −30, 30, 65). Reach the nuts from the open bottom.
2. Set the riser on the baseplate at X −165..85, Y −113..80, deck up. The **open tunnel** under riser B is for the ch2 crank and link. It must stay empty: nothing taped or cabled in it.
3. **Anchors (do this now, before the conveyor; the slide bed later covers two wells):** fit 5 × M3 × 20 down the Ø6.8 wells from the deck top, at (−150, −105), (−150, 75), (−80, −15), (−20, 75), (−20, 45). The head sits at the well bottom, Z 10. Washer + nut under the board. `riser.scad` says "M3 × 80" here; that is wrong for a head that sits at Z 10 (§20).

**Check:**
- The deck is flat. A straightedge along X shows no step at the X −40 joint.
- Deck height above the baseplate top is 60.0 ± 0.3 mm (deck Z 64).

---

## 7. Step 4: rails, bearings, motor mounts

Parts: 4 rail halves, 4 × 608ZZ, 2 motor mounts, 2 N20, 2 couplings 3 → 8. Screws:
- 4 × M3 × 80 (or 85 mm threaded rod) + nut + washer: through-feet.
- 2 × M3 × 10: insert feet X −50 front and X 40 back. The X −20 and +10 front feet wait for the camera bracket (§9).
- 4 × M1.6 × 4: N20 to mount.

`cad/assembly-steps.yaml` shows the motor mounts in this step. **Prepare** them here, but **fit** them at the end of §8. `motor_mount.scad` needs the rod collars tightened first, and the collar set screw is behind the flange afterwards.

1. **Bearings.** Press one 608ZZ into each rail boss pocket (Ø22.15 × 7, open to the outside) with a vise, pushing **on the outer ring only**, until it seats on the 3 mm shoulder, flush with the boss face. Four bosses: one per rail half.
2. **Join the halves.** Push each tenon (5 × 3 × 12) into the next half's mortise. Back rail: `back1` + `back2`. Front (motor) rail: `front1` + `front2`.
3. **Place the rails** on the deck with the inner faces at Y ±45, the inlet end at X −165 and the bearing bosses facing out. The **front (−Y) rail** is the motor rail; its halves carry the insert pads.
4. **Feet** (8 total, `conveyor_rail.scad`):

| Rail | X | Y | Fastener |
|---|---|---|---|
| Front | −80 | −75 | through-bolt: M3 × 80 from the foot top through the riser (Ø3.6) to the board |
| Front | −50 | −75 | M3 × 10 into the riser insert |
| Front | −20, +10 | −75 | leave empty for now (camera bracket, §9) |
| Back | −120, −80, +10 | +75 | through-bolts, M3 × 80 |
| Back | +40 | +75 | M3 × 10 into the riser insert |

   Clamp stack for the through-feet: foot 4 + riser 60 + tile 4 + board 6 = 74, so M3 × 80 leaves 6 mm for washer and nut.
5. **Motor mounts, bench part.** Slide each N20 into its mount's sleeve from the rear. Screw the gearbox face to the face plate with **2 × M1.6 × 4**, reaching through the Ø18 flange hole. Push a 3 → 8 coupling's 3 mm bore onto the N20 shaft, set screw on the D-flat, 6.5 mm engagement, and leave it loose.

**Check:**
- Rail gap is **90.0 ± 0.3 mm** at both shaft stations (rod axes X −140 and +60, 15 mm above the deck).
- Rails are parallel.
- Rail top is 35 mm above the deck (Z 99).

---

## 8. Step 5: slide bed, belts, rollers, rods, collars

Parts:
- Slide bed.
- 4 × O-ring 135 × 3.
- 2 rollers, each with 1 insert.
- 2 × 8 mm D-shafts, 150 mm.
- 4 race spacers.
- 4 collars Ø16 × 8: a race spacer + collar goes on **each side** of each rod (`assembly.scad` `asm_collars()`, `motor_mount.scad`).
- The 2 prepared motor mounts.

Screws: 2 × M3 × 6 cup-point grub; 4 × M3 × 10 BHCS (motor mounts).

1. **Slide bed.** Lay it upside-up between the rails, skirts on the deck (|Y| 41.5..44.5), plate X −127..47 (13 mm from each roller axis). It is captured with no screws.
2. **Belts.** Loop the 4 O-rings lengthwise round the slide bed, one in each 5 mm channel (Y −25.5, −8.5, 8.5, 25.5).
3. **Rollers.** Put a roller inside each loop end, lift it to bearing height and push the rod through:
   - front bearing;
   - roller, with the rod's D-flat matched to the roller's D-bore;
   - back bearing.
4. **Rod position.** Set it to protrude **20.0 mm past the front boss face**. That gives 10 mm into the coupling and an 8.5 mm gap to the N20 shaft tip (`motor_mount.scad` echo). With a 150 mm rod it then sticks out 20 mm past the back boss face as well.
5. **Collars.** On each side, slide on a race spacer (Ø11/8.3 × 1), then a Ø16 collar. Push both collars against the bearing inner rings (no end play) and tighten the M4 set screws.
6. **Centre the roller.** Leave a **1.0 mm gap to each rail inner face** (roller 88 in the 90 gap). Tighten the M3 × 6 cup-point grub through the roller insert onto the rod flat.
7. **Motor mounts.**
   - Offer each bracket up; the Ø18 flange hole passes over the front collar.
   - Slide the coupling's 8 mm bore onto the rod (10 mm).
   - Fit **2 × M3 × 10 BHCS** into the front-rail pad inserts.
   - Tighten the coupling's 8 mm set screw onto the rod flat from above, through the open bay.
   - Tighten the 3 mm set screw onto the N20 flat.

**Check / measure:**
- Each roller turns freely by hand through the N20 gearbox, with no rub on the rails or the slide bed.
- Belt top is **0.9 mm above the roller body**: belt top Z 90.9, roller top Z 90.0. The slide-bed lands are 1.0 mm below the belt top.
- Belt stretch is 7.4 % (centre distance 200 mm). The strands are taut, not slack, about 2.9 N each (`conveyor_roller.scad` math).
- A card laid on the belts touches only the belts.

---

## 9. Step 6: scan station

Parts:
- Card guide back + front.
- 4 clips.
- Scanner hood.
- 2 × 88 mm LED strip.
- Camera Module 3.
- Camera bracket.
- SC1130 ribbon.
- Black foam ring.

Screws: 4 × M2 × 10 self-tapping (camera); 2 × M3 × 16 (bracket + rail feet X −20 / +10).

1. **Guides.** Drop each guide into its rail's top groove: groove fill down, flat face against the rail inner face. They run X −155..85.
   - Channel width is **66.4 mm**: a 63 mm card + 1.7 mm per side.
   - Guide underside is Z 90.4 (0.5 below the card underside). The 45° funnel catches a card lowered up to 4.9 mm off-centre.
2. **LED strips.** Stick one 88 mm strip in each long-wall recess band inside the hood: 10 mm tall, 10–20 mm above the card face, i.e. Z 100.9–110.9. Pass the leads out through the Ø4 holes at the downstream end (X +45). **Keep the strips inside that band.** Glare from a strip only misses the card while the strip stays below 21 mm above the card face (`scanner_hood.scad`).
3. **Hood.** Lower it straight down over the rails: skirts outside the rails, end walls straddling the guides. It rests on the rail tops and guide tops at Z 99 and spans X −49..59. The card slots in the end walls are |Y| ≤ 34, ceiling Z 94.9.
4. **Clips.** Press 4 clips over the rail walls at **X −62 and X +72**, both rails. Each inner leg seats in the guide-top pocket. The X −62 clip is the one nearest the arm drop zone; nothing else above the rail top is allowed between X −80 and the hood.
5. **Camera.**
   - Connect the SC1130's 15-pin end to the camera, contacts toward the PCB connector contacts.
   - Feed the ribbon through the bracket plate's 20 × 7 slot.
   - Screw the PCB **lens-down** onto the 4 standoffs with **4 × M2 × 10 self-tapping** (Ø1.8 pilots, 21 × 12.5 pattern), **FPC edge facing −Y (toward the plate)**. This turns the image 180°; the code flips it (`camera.ROTATE_180`).
6. **Bracket.** Lower it straight down so the lens drops into the 15 × 15 roof port. Its foot sits on the front rail feet at X −20 and +10 (Y −75). Fit **M3 × 16** through bracket foot (6) + rail foot (4) into the riser inserts; the insert hole has a 14 mm relief below for the extra length.
7. Put the black foam ring round the lens on the roof. It closes the 2.9 mm gap between roof and PCB.

**Check / measure:**
- Lens tip Z 190.9 (100 mm above the card face). PCB front Z 197.9. Hood roof top Z 195.0.
- A card slides by hand along the whole channel with ~1.7 mm play each side and never touches a clip or the hood.
- Field of view at the card: 129.9 × 74.8 mm. Y margin is 5.9 mm per side centred, 4.2 mm worst case.
- To lift the hood later: remove the 2 bracket screws first.

---

## 10. Step 7: hopper elevator

Parts:
- Hopper body, cap, carriage, floor plate, feeler flag.
- 2 × 8 × 150 rods, 2 × LM8UU.
- T8×8 lead screw 100 mm + brass nut.
- 5 → 8 coupling.
- 28BYJ-48 + ULN2003.
- 2 × SS-5GL2-F switches.

Screws:
- 4 × M3 × 20 countersunk + nut + washer (base).
- 4 × M3 × 10 (cap).
- 2 × M3 × 8 (motor ears).
- 2 × M3 × 10 (T8 nut).
- 2 × M3 × 10 countersunk (plate).
- 1 × M3 × 20 + nylock (flag axle).
- 4 × M2 × 12 + nut (switches).

The hopper is modelled in a local frame. Local origin = cavity centre (machine X −215, Y 0); local Z 0 = baseplate top (machine Z 4).

1. **Base.** Set the body on the baseplate with the cavity centre at X −215, Y 0, the tower toward +Y and the finger slot toward −Y (front). Fit **4 × M3 × 20 countersunk** from inside the cavity, flush with the floor, at machine X −240 / −180, Y ±15, with washer + nut under the board. Do this **before** the carriage and plate go in.
2. **Bottom (home) switch.** It goes on the tower floor against the back wall, body X −3.6..16.2 local, roller up. Fit **2 × M2 × 12 + nut** through the back-wall holes (Ø2.2).
3. **Rods.** Push the 8 × 150 rods into the Ø8.15 sockets (2.4 deep) at local X ±28, Y 48.5.
4. **Carriage.**
   - Press the 2 LM8UU in from the top onto the 1.5 mm lip.
   - Drop the T8 nut body into the Ø10.8 bore from the top and screw the flange down with **2 × M3 × 10** into the carriage inserts.
   - Thread the lead screw through the nut.
   - Slide the carriage down the rods with its shelf through the +Y wall slot into the cavity.
5. **Floor plate.** Lay it on the shelf: card face up, notch under the flag position (local X −30, −Y wall). Fit **2 × M3 × 10 countersunk** into the shelf inserts at local (±9, 26.5).
6. **Coupler.** Fit the 5 → 8 coupler onto the top of the lead screw.
7. **Cap.** Fit it over the rods (they stick 16 mm out of the cap) with the coupler inside the Ø23 hole. Fasten with **4 × M3 × 10** into the tower inserts.
8. **Motor.** Mount the 28BYJ-48 **shaft down** on the cap, body offset 8 mm toward +Y. Fit **2 × M3 × 8** through the ears into the cap inserts. Push the shaft into the coupler's 5 mm bore and tighten both coupler set screws.
9. **Feeler flag.**
   - Fit the flag between the two cheeks on the −Y wall at local X −30.
   - Axle: **M3 × 20** through both cheeks (Ø3.4) + nylock, snug only.
   - **The flag must drop back onto its stop under its own weight** (≈1.2 g).
10. **Top switch.** Fit it on the +Y cheek with **2 × M2 × 12 + nut** in the slotted holes (±1.2 mm of adjustment along the actuation axis), roller under the flag's cam. Leave it mid-slot for now; it is set in §16.3.

**Check / measure:**
- **Plate travel:** turn the coupler by hand (motor unplugged).
  - The carriage runs smoothly over the full **71.6 mm** of plate travel: plate top Z 19.0..90.6 machine (local 15.0..86.6).
  - The home switch clicks with the carriage at the bottom (plate top local 15.3).
- **Top-of-stack trip:** with a stack of commons, lift the stack by hand until the top card is level with the belt top. The **top card should be 3.5 mm below the hopper rim** (rim Z 94.4, card Z 90.9). Lift the flag tip by hand and the top switch must click.
- **Empty plate:** an empty plate passes up under the flag through its notch without closing the switch. This is how "hopper empty" is detected.
- **Clearance to the belt:** the hopper's +X outer wall is at X −166.5 and the belt starts at X −165. The hopper must not touch the rail ends.

---

## 11. Step 8: pick arm

> **Test first (§19.1):** bench-test the MG996R you'll use on ch0 for ~170° of travel *before* printing or assembling the arm.

Parts:
- Head, tower, crank, links B and C, hand, sled, 4 sleeves.
- MG996R.
- 25T aluminium disc horn.
- 4 mm silver-steel pins.
- 8 × 6 tube.
- Push-on washers.
- 2 springs.
- SMC ZPT16BS-B5 pad + M5 barb.
- Vacuum tube.

Screws:
- 4 × M3 × 10 (servo tabs).
- 4 × M3 × 6 (horn).
- 2 × M3 × 40 SHCS (guide screws).
- 4 × M3 × 12 (head → tower).
- 4 × M3 × 20 + nut + washer (tower → board). `suction_arm.scad` says M3 × 16, which assumes no board.

Pin lengths (`suction_arm.scad` echo). Cut them from 4 mm silver-steel and chamfer the ends:

| Pin | Length |
|---|---|
| B ground | 38 |
| C ground | 29.5 |
| B' | 13 |
| C' | 21.5 |
| A' (8 × 6 tube) | 30.5 |

Sleeves: B ground 23.7, C ground 15.2, C' hand 9.2, A' hand 16.7 (the `sleeves` print).

Order (`suction_arm.scad` ASSEMBLY ORDER):

1. **Inserts are in (§3).** Press the B and C dowels into the head plate from the front, flush at the back.
2. **Servo.** Fit the MG996R into the head from behind, tabs on the plate's back face, with **4 × M3 × 10** into the tab inserts. The tab height is a typical value; shim under the tabs if your servo differs.
3. **Crank.** Power the servo at **ARM_PARK = 90°**:

   ```bash
   venv/bin/python scripts/calibrate_servos.py --no-mock   # menu 1
   ```

   or

   ```bash
   venv/bin/python -c "from hardware import servos; servos.init(); servos.arm_park()"
   ```

   Then:
   - Fit the disc horn so its screw slots roughly line up.
   - Bolt the crank on **pointing straight up** with **4 × M3 × 6**.
   - One spline tooth is 14.4°; trim the rest in calibration.
4. **Links and hand.**
   - Put the sleeves on B and C, then link C (on C) and link B (on B).
   - Hand: press in the A' tube and the B'/C' dowels; fit the A' and C' sleeves.
   - Slide the hand on: A' into the crank, B' into link B, C' into link C. **It only goes on when all three links are parallel.**
   - Push a flat push-on washer onto every free pin end (≤ 0.5 mm thick; domed caps are too tall for the 1 mm gaps).
5. **Cup.**
   - Press the pad's 8 mm hex into the sled.
   - Fit the barb through the web into the pad (gasket).
   - Put the springs on the M3 × 40 guide screws (heads down), slide the sled on, and screw into the hand-beam inserts.
6. **Tube.** Run it barb → loop → through the A' tube → free "spoke" (≈ 97 mm) → anchor bell on the servo axis → down the back of the column with zip ties. Leave ~10 mm of slack in the hand loop.
7. **Tower and head.** Fit the head onto the tower with **4 × M3 × 12** into the column-top inserts. Bolt the tower foot to the baseplate at X −180 / −120, Y −165 / −135 with **4 × M3 × 20** + nut + washer.

**Check / measure** (with `calibrate_servos.py` menu 1, §16.2):
- Servo axis at X −154.7, Z 151.8. Crank radius 60.3 mm.
- **PARK 90°:** crank vertical, hand over X −155.
- **PICK ≈ 175°:** cup lip 3 mm **below** the top card (Z 87.9). The spring slider takes up the overtravel (10 mm stroke). The cup comes down within 2° of vertical.
- **DROP ≈ 5°:** card underside 3 mm above the belt (Z 93.9), card centre X −95, i.e. the card spans X −139..−51.
- During the lift the card clears the hopper wall by only **1.09 mm**. Watch it the first time.
- **No link touches another** over the whole sweep (`cad/pick_arm_check.py` checks the CAD).

---

## 12. Step 9: sorting tray

Parts: sections A, B (lower), C, D (upper), 2 shelf halves. Screws:
- 8 × M3 × 20 countersunk + nut + washer (lower floor → board).
- 8 × M3 × 12 countersunk (stacking).

The tray spans **X 178..276, Y −137..137**. The **open back face of every slot is at X 178, facing the shuttle**, and nothing may block it. The label windows face +X.

1. **Join A + B.** A's Ø3 pin goes into B's Ø3.2 hole; fronts flush. A is at Y −137..0, B at Y 0..137.
2. **Fasten the lower floor (before the shelf).** Fit **8 × M3 × 20 countersunk** from inside the slots, down through the 2.5 floor + tile + board, with washer + nut. Holes are at machine X **200 / 260**, Y **−105, −45, 45, 105**.
3. **Shelf.** Lay the 2 shelf halves on top, with the seam on the section seam.
4. **Upper floor.** Set C + D (joined by their pin) on the shelf. Fit **8 × M3 × 12 countersunk** from inside the upper slots' front corners: through floor 2.5 + shelf 3, self-tapping about 6.5 mm into the Ø2.5 pilots. Stop as soon as the heads seat.

**Check:**
- Slot centres are at Y −102, −35, 35, 102 (columns 0..3), with the same columns on both floors.
- Slots are 65 mm wide for a 63 mm card, so **±1 mm** of shuttle error still drops the card cleanly.
- Lower slot floor Z 6.5; upper slot floor Z 74.5.
- Bins (`hardware/shuttle.py`): 0–3 lower floor (column = bin), 4–7 upper floor (column = bin − 4), 9 = reject bin. What goes in each bin is set by `config/rules.json`, not by the tray.

---

## 13. Step 10: cradle shuttle, load cell, lower ramp, reject bin

Parts:
- Cradle, tilt frame (TF), carriage, tilt crank, tilt link, ch2 crank, ch2 link, R-bar −Y / +Y, end posts −Y / +Y.
- TAL221 load cell.
- 8 × 400 rod, 8 mm D-shaft 400.
- 2 × LM8UU, 2 × 688ZZ.
- 2 × Ø4 × 8 dowels.
- 2 MG996R (ch1, ch2).
- 25T disc horn + 8 mm flange coupling (ch1).
- MG996R round horn (ch2, from the servo bag).
- PTFE tape.
- 2 lower-ramp halves, reject bin.

Screws (`shuttle.scad` BOM):
- 2 × M3 × 10: TF → cell tapped end.
- 2 × M3 × 10: cell → cradle inserts.
- 4 × M3 × 16 + nylock: the 4 pivots.
- 1 × M3 × 4 set screw. **Do not tighten it**, see step 5.
- 2 × M3 × 16: R-bar splice.
- 2 × M3 × 10: rod clamps.
- 2 + 4 × M2.5 × 10 self-tapping: ch1 / ch2 ears.
- 4 × M2 × 8: ch2 crank → horn.
- 4 × M3 × 8: ch1 horn ↔ flange coupling.
- 4 × M3 × 20 + nut + washer: end posts.
- 4 × M3 × 20 + nut + washer: ramp.
- 4 × M3 × 20 countersunk + nut + washer: reject bin.

### 13.1 Cradle and load cell

1. **PTFE tape (required).** Cover the cradle bed and the 18° kick with **0.1 mm skived PTFE tape**, wrapping 2 mm over the lip. No bubbles or wrinkles; trim the edges with a knife. Bare PLA (μ ≈ 0.35–0.45) jams the upper-floor transfer (`shuttle_check.py`).
2. **Cell to TF.** Fit the TAL221's **tapped (cable) end** to the TF crossbar pad with **2 × M3 × 10** from below (counterbored holes). The cable goes toward the front notch in the crossbar.
3. **Cell to cradle.** Fit the cradle boss to the cell's **free end** with **2 × M3 × 10** from below through the cell's holes into the cradle inserts.
4. **Check:** the cradle touches nothing but the cell. Press the cradle bed lightly and it must spring back. Cradle with tape is ≈ 19 g (target ≤ 35 g).
5. **F pins.** Ream the TF's F-pin holes to Ø3.9. Press the 2 Ø4 × 8 dowels in **from inside** so they stick out of the side plates.

### 13.2 Rail system: end posts, rod, D-shaft, carriage, R-bar

1. Press a 688ZZ into each end post's inner-side pocket (Ø16.05).
2. **Carriage.**
   - Press an LM8UU into each end pocket (Ø15.1 × 24.1).
   - Ream the D-shaft bushings to Ø8.3.
   - Put the **tilt crank** into the carriage's swing pocket.
3. **Dry-assemble on the bench:**
   - Rod through post −Y → carriage LM8UUs → post +Y. The rod sits Y −160..232 at X 106, Z 24.
   - D-shaft through post −Y 688ZZ → carriage bushing → tilt crank D-bore → bushing → post +Y 688ZZ. The D-shaft sits Y −168..232 at X 105, Z 44.
   - Fit the 2 rod clamps (M3 × 10 down into the Ø2.6 pilots in each post).
4. **R-bar.**
   - Join `rbar_neg` and `rbar_pos` at the 20 mm lap splice at Y 0 with **2 × M3 × 16** down into the inserts.
   - Seat the ends in the end-post R-bar seats. The bar runs Y −150..232 at X 97..104.
   - The home notches at |Y| 29..45 must line up under the TF skids at home.
5. **Tilt crank set screw: leave it loose.** The crank is captured in the carriage pocket and **slides along the D-shaft** as the carriage moves, so a tightened set screw would bind the carriage (§20). The D-bore alone keys the rotation.
6. **Mount the module.** Set the whole assembly in place (posts at Y −160..−150 and 232..242, X 96..116). The floor-plate holes are **not on the baseplate grid**: post −Y at X 100 / 110, Y −170; post +Y at X 98 / 114, Y 249. Mark and drill Ø3.4 through tile and board, then fit **4 × M3 × 20** + nut + washer.

### 13.3 Tilt frame onto the carriage, tilt drive

1. Hang the TF, with cell and cradle, in the carriage: the F pins drop into the hook channels in the cheeks' inner faces.
2. **Tilt link.** Crank tip → TF pin A, with **M3 × 16 + nylock** at both ends. Snug the nylocks so the joints pivot freely without play.
3. **Load-cell lead.** Zip-tie it in the slot on the carriage's −Y cheek (X 150..154, Z 70). The rest of the route is in §14.7.

### 13.4 ch1 (tilt) servo

1. Seat the MG996R in the −Y end post's cage, spline on the D-shaft axis at Y −168, body toward −Y. Fit **2 × M2.5 × 10 self-tapping** into the two cage pilots (X 105, Z 9.5 and 58.5).
2. **Coupler.** Fit a 25T aluminium disc horn to the spline and bolt it to an 8 mm-bore rigid flange coupling on the D-shaft end (4 × M3 × 8). Check the coupling's hole circle matches the horn's M3 pattern before buying (BOM). If they don't match, drill the flange.
3. Power ch1 to **HOLD = 97°** and fit the coupler so the cradle is **10° nose-down** about the F pins. Trim it in §16.4.

### 13.5 ch2 (shuttle) servo and crank

1. The ch2 MG996R **hangs upside down**: output axis at X 80, Y −124, case face Z 20.8, spline down (`shuttle_geom.scad`).
   - **Front ear:** into the pocket in riser B's front face (X 69..85, Y −113..−105.8, Z 18..31.5). **2 × M2.5 × 10** up into the pocket ceiling at Z 31.5.
   - **Rear ear:** on the −Y end post's shelf, **2 × M2.5 × 10**.
2. **Crank.** Fit the round 25T horn to the spline. Bolt the **ch2 crank** (139 mm) to the horn disc with **4 × M2 × 8** (Ø1.8 holes on Ø14), then drive the horn screw through the crank hub.
   - Set the servo to **home = 75.5°** first. At that angle the carriage must sit at Y 0 with the cradle centred on the belt.
   - The servo angle equals the crank angle ψ: 0° = crank pointing +Y (reject end), 90° = pointing −X.
3. **Link.** The ch2 link (162 mm) goes from the crank tip to the carriage drive pin, with **M3 × 16 + nylock** at both ends. The drive-pin bolt goes in from below.

### 13.6 Lower ramp and reject bin

1. **Lower ramp.** Set the two halves on the baseplate directly behind the tray's open back: lane exit at X 178, entry X 160.4, Z 34.7. Fit **4 × M3 × 20** through the rear floor tabs at X 140, Y ±45 and ±105. The dividers line up with the tray walls, and the 4 mm fins (X 174..178) rise to Z 104.
2. **Reject bin.** Set it at Y 141..211 beside the tray. Fit **4 × M3 × 20 countersunk** through the box floor at X 200 / 230, Y 165 / 195.

**Check / measure** (move the servos with `calibrate_servos.py`, never by hand on a powered servo):
- **LEVEL at home:**
  - Cradle bed **0.7 mm below the belt top** (Z 90.2). Check with a straightedge across the belt end and the bed.
  - Cradle rear edge X 92, 7 mm past the belt end.
  - The skids rest on the home ledges.
- **HOLD:**
  - Bed 10° nose-down.
  - The card's tail is above the rails, guide clips and guide tops, so the carriage may move.
- **Carriage travel:**
  - The carriage runs freely Y −102..176. LM8UUs don't bind and the tilt crank slides along the D-shaft.
  - The ch2 crank tip stays inside the baseplate (reaches Y −269 at column 0).
- **Lower pose:** the TF's skids land on the R-bar at every column, and the kick reaches the ramp entry (≈1 mm before it, 1.5 mm above).
- **Tight spots:** the carriage, cradle and ramp have **0.5–0.8 mm clearances** in places (§19). Cycle every pose slowly once and look for rubbing.

---

## 14. Step 11: wiring and vacuum

> Work with the 12 V adapter **unplugged**. Plug in only to test a finished, double-checked stage.

### 14.1 Power rails

Three fixed 5 V regulators, one per kind of load. The full budget is in `BOM.md` → Power budget. The supply is a **12 V 5 A** adapter: the arm-move peak is ≈ 3.2 A at 12 V, so the 3 A adapter is too small.

```
12 V 5 A adapter ── panel jack (tray +Y wall)
  12 V+ ─┬─ Reg #1 VIN  (Pololu D24V22F5, 5 V 2.5 A)  "5 V logic"
         ├─ Reg #2 VIN  (Pololu D24V50F5, 5 V 5 A)    "5 V servo"
         ├─ Reg #3 VIN  (Pololu D36V28F5, 5 V 3.2 A)  "5 V motor"
         └─ Relay COM ── Relay NO ── pump (+)    [1N5819 across the pump: cathode to pump +, anode to pump −]
  GND ───── GND bus (Wago) ── every regulator GND, every module GND, pump (−)

Reg #1 VOUT ── Pi pin 2 (5 V)        Reg #2 VOUT ── PCA9685 V+ screw terminal ONLY
           ├── LED strips +                    ├── 1000 µF at the regulator output
           └── relay VCC                       └── 1000 µF across V+/GND at the PCA9685

Reg #3 VOUT ── L9110S VCC (both N20s)
           ├── ULN2003 + (28BYJ-48)
           └── 1000 µF at the regulator output

Pi pin 1 (3.3 V) ── PCA9685 VCC (logic; MUST be 3.3 V), HX711 VCC
Pi pin 17 (3.3 V) ── 10 kΩ ── GPIO 17 (relay IN)
GND ── 10 kΩ ── GPIO 23, 24, 25, 26 (L9110S inputs), one resistor each
```

- **PCA9685 VCC is 3.3 V from the Pi, never 5 V.** The board's I²C pull-ups go to VCC; at 5 V they would pull the Pi's SDA/SCL pins to 5 V. Servo power comes only through the **V+ screw terminal** from Reg #2. Leave the V+ pins on the side headers unconnected (same net).
- **Why three rails:**
  - One MG996R move start (~2.5 A) on a shared rail browns out the Pi.
  - Two N20s at start or stall (up to 3.2 A) plus the stepper would overload the Pi's regulator.
  - So servos, motors and logic each get their own regulator.
- **Never** tie two regulator outputs together. Never feed PCA9685 V+ from the Pi. Never plug the micro-USB into the Pi while Reg #1 is connected.
- Leave every Pololu EN pin unconnected (enabled).
- Use 22 AWG for 12 V, the three 5 V rails and GND.
- Signal wires: 26 AWG or Dupont.
- **Electrolytic capacitors are polarised:** the stripe goes to GND.

**First power-up:**
1. Regulators only, no loads, for 30 s. Unplug and touch-check: nothing warm.
2. Connect the Pi only. Boot it and check that `vcgencmd get_throttled` prints `throttled=0x0`.
3. Add the other loads one rail at a time.

### 14.2 GPIO table (BCM; header pin in brackets). Source of truth: `hardware/*.py`

| BCM | Pin | Direction | Connects to | Module | Notes |
|---|---|---|---|---|---|
| 2 (SDA1) | 3 | I²C | PCA9685 SDA | `servos.py`, `shuttle.py` | PCA9685 at 0x40 |
| 3 (SCL1) | 5 | I²C | PCA9685 SCL | | |
| 5 | 29 | in | HX711 DOUT (DT) | `loadcell.py` | |
| 6 | 31 | out | HX711 SCK | `loadcell.py` | |
| 12 | 32 | in, pull-up | top-of-stack switch NO (C → GND pin 34) | `elevator.py` | pressed = LOW |
| 13 | 33 | in, pull-up | home switch NO (C → GND pin 30) | `elevator.py` | pressed = LOW |
| 16 | 36 | out | ULN2003 IN1 | `elevator.py` | SoC pull-down at boot; the ULN2003's internal input resistors keep a floating input off |
| 19 | 35 | out | ULN2003 IN2 | `elevator.py` | |
| 20 | 38 | out | ULN2003 IN3 | `elevator.py` | |
| 21 | 40 | out | ULN2003 IN4 | `elevator.py` | |
| 17 | 11 | out | relay IN (**active LOW** = pump ON) + **10 kΩ to 3.3 V** | `vacuum.py` | the pull-up keeps the pump off when the pin floats |
| 23 | 16 | out (PWM) | L9110S A-1A (motor A forward) **+ 10 kΩ to GND** | `conveyor.py` | pull-down: pins float after `cleanup()` |
| 24 | 18 | out | L9110S A-1B (motor A reverse / brake) **+ 10 kΩ to GND** | `conveyor.py` | |
| 25 | 22 | out (PWM) | L9110S B-1A (motor B forward) **+ 10 kΩ to GND** | `conveyor.py` | |
| 26 | 37 | out | L9110S B-1B (motor B reverse / brake) **+ 10 kΩ to GND** | `conveyor.py` | |
| — | 2, 4 | power | 5 V in from Reg #1 | | |
| — | 1, 17 | power | 3.3 V → **PCA9685 VCC**, HX711 VCC, 10 kΩ pull-up | | PCA9685 VCC must be 3.3 V |
| — | 6, 9, 14, 20, 25, 30, 34, 39 | GND | GND bus | | |
| CSI | — | | Camera Module 3 via SC1130 | `camera.py` | connector faces +X |

- **The L9110S is plain GPIO, not I²C.** Its VCC comes from Reg #3, not the Pi rail.
- **Pins float after `cleanup()`.** The SoC pull-downs on GPIO 9–27 only apply from power-on until a program configures the pin. RPi.GPIO `cleanup()` (`conveyor.deinit()`, `vacuum.deinit()`, `elevator.deinit()`) returns them to inputs with **no pull**. The external resistors set the safe level:
  - 10 kΩ pull-up on GPIO 17: pump off.
  - 10 kΩ pull-downs on GPIO 23–26: belt coasts.
- HX711 pins: **DOUT (DT) = GPIO 5, SCK (CLK) = GPIO 6** (`hardware/loadcell.py`).
- HX711 wiring to the cell: E+ red, E− black, A+ white, A− green (confirm with your cell).
- 28BYJ-48: its keyed 5-pin plug goes into the ULN2003 board.
- Relay: COM to 12 V+, **NO** to the pump. If power is lost the pump stops.

### 14.3 PCA9685 channels (I²C 0x40, 50 Hz, 500–2500 µs)

| Ch | Servo | Owner | Nominal angles (calibration overrides) |
|---|---|---|---|
| 0 | Pick arm (MG996R) | `hardware/servos.py` → `config/servo_calibration.json` | ARM_PICK 175, ARM_DROP 5, ARM_PARK 90 |
| 1 | Cradle tilt (MG996R, D-shaft) | `hardware/shuttle.py` → `config/shuttle_calibration.json` | level 92.1, hold 97.0, upper 112.2, lower 41.5 |
| 2 | Shuttle carriage (MG996R, slider-crank) | `hardware/shuttle.py` → `config/shuttle_calibration.json` | reject 2.0, col 3 45.0, col 2 65.2, home 75.5, col 1 87.3, col 0 178.0 |
| 3–15 | unused | | |

PCA9685 power: VCC = 3.3 V from the Pi (logic and I²C pull-ups), V+ = Reg #2 servo rail (5 V 5 A), with 1000 µF across V+/GND at the board. Servo leads: brown/black = GND, red = V+, orange = signal (the `PWM` row). Use 100 cm extensions from the tray to each servo.

### 14.4 Harness route

There is no front-to-back pass through the riser. The ch2 crank sweeps the floor in front of it (Z 5..13.5), so **the only route goes round the hopper's −X side** (`assembly.scad` `asm_harness()`):

1. **Collect at the front.**
   - The N20 leads drop down the front of the riser.
   - The arm servo lead runs from the head-floor slot (Y ≈ −108), under the head, and down in front of the column (Y −117.5).
   - The ch1 and ch2 leads join them.
   - Bundle everything to Ø ≈ 7 mm and clip it to the **riser's front face at Z 45**, above the ch2 crank.
2. **Around the −X end.** Run the bundle along the front to X −277, in front of the arm column. Drop to Z 12 outside the hopper and run along the −X edge.
3. **Into the tray, shorter option (recommended):** turn +X at Y ≈ 135 and enter the tray through the new **−X wall slots** (X −150, Z 40.5..46.5). About **0.8 m** in total.
4. **Into the tray, CAD route:** carry on to Y 215, run behind the tray to X 45, and enter through the +X slots. About **1.1 m**.

- **Hopper motor and switches:** run down the back of the tower (Y 80) and join the harness at the −X edge.
- **LED leads:** from the hood's Ø4 holes (X +45) over the back rail into the tray.
- **Keep clear of:**
  - the ch2 crank and link sweep (Z ≤ 13.5 under and in front of riser B);
  - the arm sweep above the hopper and belt inlet;
  - the shuttle carriage path (X 90..170).

### 14.5 Camera ribbon (SC1130, 500 mm)

1. Run the ribbon from the camera connector out through the bracket's −Y plate slot, up the plate, over the gusset and arm top (Z 234).
2. Bring it down behind the hood and the back rail (Y 62), over the riser deck's back edge (Y 80, Z 84).
3. **Fold it 45° toward −X**, down into the tray to the Pi's CSI connector. That connector **must face +X** (machine X ≈ −78, Y ≈ 101).

- The CAD route to the tray entry (X 5, Y 88, Z 30) is 405 mm. Going on to the connector square-on adds 86 mm (491 mm in total); the 45° fold saves about 50 mm, so **expect ≈ 440–490 mm on a 500 mm cable**.
- **Test-fit the ribbon before you tie anything down** (§19).
- Ribbons are fragile: no sharp creases, no pulling at the connectors.

### 14.6 Vacuum tube

Route (`assembly.scad` `asm_vac_tube()`), about 0.45 m in total:
1. The pump sits on the baseplate at the front-left corner (X −265..−205, Y ≈ −205). The CAD has no pump mount, so use foam tape and a zip tie.
2. A short silicone sleeve and a reducing barb take the pump's **inlet** (suction side) down to the 4 mm tube.
3. The tube runs along Y −205, then up the back of the arm column (X −147, Y −160, zip-tie slots at Z 40 and 75).
4. It goes into the anchor bell on the servo axis (Y −142), then out as the free spoke to the A' tube, then through the loop to the cup barb.

Fit the 1N5819 (or 1N4007) flyback diode across the pump terminals: cathode (stripe) to pump +, anode to pump −. Twist the pump leads and keep them away from the I²C wires.

### 14.7 Load-cell lead (trailing loop, not modelled in CAD)

The cradle moves 278 mm in Y and tilts, and `assembly.scad` only says "trailing service loop (not modelled)". Suggested routing, **to be test-fitted**:

1. Splice about 1 m of 4-core flexible silicone wire (26–28 AWG) to the TAL221 leads at the cradle. Solder and heat-shrink the joint.
2. The lead leaves the TF crossbar notch, is zip-tied at the carriage's −Y cheek slot, then runs down the cheek's outer face to the cheek bottom (Z 13).
3. From there it forms a **flat rolling loop on the baseplate under the carriage**, at about X 125–130. The moving end is under the carriage; the fixed end is taped to the baseplate at about Y 0.
4. The fixed lead then runs along the baseplate in +Y to Y ≈ 215, then −X along Y 215, then into the tray to the HX711.

Keep it out of:
- the rod, LM8UU, D-shaft and tilt crank (X 98..118, Z 20..54);
- the R-bar top;
- the ch2 link (X ≈ 75..90, Z 5..9, swept up to Y 182);
- the lower-ramp tabs (X 136..160 at Y ±45, ±105);
- the card path.

**Check:** run the shuttle through every column and reject (`test_hardware.py` test 4). The lead must never tighten, rub, or pass under the ch2 link.

### 14.8 Safe state

| Event | Pump | Servos | Belt / elevator |
|---|---|---|---|
| 12 V pulled | **off** (relay NO opens) | limp. **The arm falls and drops any card.** Always park before powering down. | stop; the 28BYJ-48 gearbox holds the hopper floor |
| Pi hang | holds its state until the watchdog reboots (≤ 15 s), then **off** through the pull-up | hold their last pulse | hold their last level until the reboot; then the SoC boot pull-downs (and the external 10 kΩ on GPIO 23–26) → off |
| Program exits (`cleanup()`) | **off** through the 10 kΩ pull-up | PCA9685 keeps its last pulse | pins **float**: the 10 kΩ pull-downs keep the L9110S coasting; the ULN2003 stays off |
| Normal stop (`systemctl stop`, Ctrl-C) | off | arm parked, cradle level at home | stopped |
| `kill -9` | **can stay ON**. Run `sudo systemctl stop riftbound-sorter` or reboot | hold | can keep running |

**Safe-state test** (pump hose off): boot the machine and watch the relay. It must never click or light. After boot, `pinctrl get 17` reads `hi`, and `pinctrl get 23-26` read `lo`. Repeat after the sorter has run and exited.

---

## 15. Software setup

1. **Flash the SD card.** Use Raspberry Pi OS Lite 64-bit (Bookworm) with Raspberry Pi Imager. Enable SSH, set the user and Wi-Fi, and set the hostname to `riftbound-sorter`. The camera is auto-detected on Bookworm (`camera_auto_detect=1`); `raspi-config do_camera` is a no-op there.
2. **Clone and run setup:**

   ```bash
   git clone https://github.com/svenka-shannon/riftbound-sorter && cd riftbound-sorter
   bash scripts/setup.sh
   ```

   It enables I²C and installs the apt packages, including **`python3-picamera2`**. picamera2 needs the apt-only libcamera bindings, so it comes from apt, not pip. setup.sh then creates `venv/` **with `--system-site-packages`** so the venv can see picamera2, and installs `requirements.txt`.

   Pi Python dependencies:
   - `RPi.GPIO`
   - `adafruit-blinka`
   - `adafruit-circuitpython-pca9685`
   - `adafruit-circuitpython-motor`
   - **gandalf15/HX711**: vendored in the repo as `hardware/vendor/hx711.py` (licence alongside). **Do not** `pip install hx711`; the PyPI package of that name is a different library.
   - `python3-picamera2` (apt)
   - `Pillow`, `imagehash`, `numpy`, `flask`, `requests`

   `scripts/setup.sh` and `requirements.txt` are the reference for the exact commands.
3. **Check the venv:**

   ```bash
   venv/bin/python -c "import picamera2, board; from hardware.vendor import hx711"
   ```

   If `picamera2` fails, the venv was made without system packages:

   ```bash
   rm -rf venv && python3 -m venv --system-site-packages venv
   ```

   Then re-run the pip installs from `setup.sh`.

4. **Check the hardware is seen:**
   - `sudo i2cdetect -y 1` shows `40` (PCA9685).
   - `rpicam-hello --list-cameras` (or `libcamera-hello`) shows `imx708`.
5. **Card database:** `venv/bin/python main.py --build-db` (needs internet).
6. **Watchdog:**
   - Add `dtparam=watchdog=on` to `/boot/firmware/config.txt`.
   - Set `RuntimeWatchdogSec=15` in `/etc/systemd/system.conf`.
   - Reboot and check that `/dev/watchdog` exists.
7. **Hardware tests:** `venv/bin/python scripts/test_hardware.py --no-mock` gives a menu of tests 1–10:

   | Test | What it runs |
   |---|---|
   | 1 | arm |
   | 2 | pump |
   | 3 | pick and place |
   | 4 | shuttle |
   | 5 | load cell |
   | 6 | camera |
   | 7 | live detection |
   | 8 | conveyor |
   | 9 | centring |
   | 10 | elevator |

   Off the Pi, `uv run scripts/test_hardware.py` runs the same menu in MOCK mode.

Always run hardware scripts with the **Pi venv python** (`venv/bin/python …`); a uv script environment has no GPIO, camera or PCA libraries. Off the Pi, `MOCK_HARDWARE=1 python main.py --dry-run` exercises the whole cycle, and the 26 mock tests live in `tests/test_cycle_mock.py`.

**Operating safeguards in the software** (see `main.py`, `web/app.py`, `hardware/camera.py` for current details):
- **Camera focus.** The Camera Module 3 is fixed-focused at `LensPosition` ≈ 10 (dioptres, i.e. ~100 mm to the card) instead of autofocus.
- **Web UI token.** Actions that change anything need the web UI token: bin resets, rules edits, **pause** and **stop**. Read-only pages don't.
- **Start-up refusals.** The sorter refuses to start if the cradle reads a card at start-up, or if the previous run did not stop cleanly. Clear the cradle, check the machine, then follow the start-up message.
- **Empty-cradle offset.** The empty-cradle offset is calibrated (§16.1) so a card left on the cradle is detected before the first tare.

**First motion checks (before calibration):**
- **Elevator direction.** Put the plate mid-travel with no cards, run test 10 and watch the first second. If "home" moves the floor **up**, press Ctrl-C at once and set `UP_DIRECTION = -1` in `hardware/elevator.py`.
- **Belt direction.** Run test 8. Both rollers must move the card toward +X. Swap a motor's two leads if one runs backward.

---

## 16. Calibration (in this order)

Use **bulk commons** for every step. Jogging is done with `scripts/calibrate_servos.py`, which drives the servos through the same modules the sorter uses (ramped moves, HOLD interlock):

```bash
venv/bin/python scripts/calibrate_servos.py --no-mock             # menu: 1 arm, 2 tilt, 3 carriage, v verify, p print, q quit
venv/bin/python scripts/calibrate_servos.py --no-mock --verify    # cycle saved poses slowly (--dwell S, --step)
```

Jog keys at every pose:

| Key | Action |
|---|---|
| `+` / `-` | ±0.5° |
| `++` / `--` | ±2° |
| `+++` / `---` | ±5° |
| `+1.5` / `-3` | any step up to ±5° |
| `s` | save |
| `n` | skip |
| `r` | back to the stored value |
| `q` | quit (parks everything) |

Notes:
- Jogging is limited to ±25° round the stored value. One MG996R spline tooth is 14.4°; re-seat the horn if you need more.
- Saved values go to `config/servo_calibration.json` (arm) and `config/shuttle_calibration.json` (tilt, carriage).
- Without `--no-mock` nothing moves, but values **are** still written.

### 16.1 Load cell

1. Run `venv/bin/python main.py --calibrate`. The cradle goes to HOLD, using the nominal ch1 angle, which is close enough.
2. Press Enter with the cradle **empty** to tare.
3. Put **one** card flat on the cradle and press Enter. The scale factor is computed assuming that card is **1.75 g** (`CARD_WEIGHT_G`) and saved to `config/loadcell_calibration.json`.
4. **Empty-cradle offset.** `--calibrate` also records the empty cradle's absolute raw HX711 reading (`"empty_offset"`), which is saved with the scale factor in `config/loadcell_calibration.json`. At start-up the sorter compares the cradle to this offset, before it tares, so a card left on the cradle is caught. Run the calibration with the cradle truly empty and PTFE tape fitted. Re-run it if you re-tape the cradle or re-route the load-cell lead.

**Check** (test 5):

| Load | Expected reading | Class |
|---|---|---|
| Empty | 0 ± 0.3 g | empty below 0.5 |
| One card | 1.3–2.3 g | single |
| Two cards | ≥ 2.8 g | double |

Re-run this step if you change the HOLD angle in §16.4.

### 16.2 Arm (ch0)

Menu **1**. Use a sacrificial card. PICK and DROP start 8° short (toward PARK); jog the last degrees yourself.

- **ARM_PICK (≈175):** cup on the card centre with the slider visibly compressed (~3 mm of the 10 mm stroke). The card seals when the pump is on.
- **ARM_DROP (≈5):** card flat and ~3 mm above the belts. Its upstream edge should be **26 mm downstream of the rail inlet end** (card X −139..−51).
- **ARM_PARK (90):** crank vertical.

**Check:** `test_hardware.py` test 3 (pick and place). The card lands flat inside the guide funnel, released ≤ 1.7 mm off-centre in Y.

### 16.3 Elevator trip height

Run test 10 (home, then raise to pick) with a stack of commons.

1. **Measure from the hopper rim down to the top card: target 3.5 ± 0.3 mm.** That puts the card at Z 90.9, level with the belt top.
2. **Coarse adjustment:** slide the top switch in its slots. Higher trip = less depth.
3. **Fine adjustment:** `TRIP_EXTRA_STEPS` in `hardware/elevator.py`. About 510 half-steps per mm (`STEPS_PER_MM` 509.5); positive values raise the card further after the trip.
4. Repeat with 10 cards removed and check it stays within ±0.3 mm.
5. Re-check ARM_PICK after any change.

### 16.4 Shuttle: tilt and columns

1. **Menu 2, at home.**
   - **hold:** bed 10° nose-down, card tail clear of the rails, guides and clips.
   - **level:** skids firmly on the home ledges; bed 0.7 mm below the belt top.
2. **Menu 3, columns 0–3 and reject.**
   - Centre the cradle on each slot by eye, or drop a 65 mm card gauge into the slot and line the cradle up with it.
   - **Target: card centre within ±1 mm of the slot centre** (slot 65 for a 63 card). The upper lead-in fins funnel ±2 mm.
   - Every move ends travelling toward +ψ, to take up backlash.
   - Expect ±2 mm repeatability (§19), so calibrate **each column on its own**.
3. **Menu 2 again, at a column (default column 1).**
   - **upper:** the card slides off the lip into the upper slot.
   - **lower:** the skids land on the R-bar, the kick reaches −40° and the card runs down the ramp into the lower slot.
4. **Verify:** run `--verify`, then `test_hardware.py` test 4. With a card, check both floors of all 4 columns and the reject bin.

### 16.5 Camera crop

Run `venv/bin/python scripts/calibrate_camera.py --no-mock`:
1. It captures the **empty** station.
2. You place a card face-up, centred under the lens and against the guides; it captures again and auto-detects the card by differencing the two frames.
3. Check the previews and save.

| Command | Action |
|---|---|
| `a` | use the auto-detected box |
| `d` | geometric default |
| `m L T R B` | type the box |
| `x N` / `y N` | shift the box |
| `c` | re-capture |
| `s` | save |
| `q` | quit |

Previews:
- `/tmp/calibration_overlay.jpg`: green = crop box, yellow = detected card.
- `/tmp/calibration_crop.jpg`: the crop as identification sees it.

Saving calls `camera.set_crop(..., save=True)`, which writes `config/camera_crop.json`. Coordinates are in the 180°-flipped 768 × 432 frame.

**`CARD_ROTATE`** (`hardware/camera.py`, default 90): if the saved crop is upside-down, set 270. It depends on which way the cards are loaded.

### 16.6 Belt-centring constants

These are module constants with no config file: edit `hardware/card_detect.py` (and `main.py` for `EXIT_TRAVEL_S`), then re-test.

| Constant | Default | How to measure |
|---|---|---|
| `TRAVEL_SIGN` | +1 | Test 7 (live offset, belt off). Slide a card by hand in the travel direction (+X). The offset must **increase**; if it decreases, set −1. |
| `CENTRE_OFFSET_MM` | 0.0 | Place a card physically centred under the lens: hood inner end walls at X −45 / +55, so the card edges are 6.0 mm from each end wall. Read the offset in test 7 and **add** that reading to `CENTRE_OFFSET_MM`, so a centred card reads 0. |
| `BELT_SPEED_MM_S` | 150 | Mark a card's edge position, run test 8 (3 s), measure the distance moved and divide by 3. It also sets `SEEK_TIMEOUT_S`. |
| `BRAKE_COAST_MM` | 1.5 | Test 9 (centring) 5×. If the final offset is consistently +d mm (overshoot), add d. If it is consistently short, nudges correct it; reduce slightly. |
| `STOP_LATENCY_S` | 0.025 | Only if the overshoot grows with speed: increase by (overshoot ÷ speed). |
| `EXIT_TRAVEL_S` (`main.py`) | 1.0 | Smallest belt time after capture that lands the card fully on the cradle (tail off the roller, nose against the kick) in 10/10 tries, + 0.2 s. Nominal 144 mm ÷ belt speed. |
| `CARD_ROTATE` (`camera.py`) | 90 | §16.5 |

**Target:** test 9 ends with |offset| ≤ 2.5 mm (`CENTER_TOL_MM`). Anything above 6 mm is reported as not ok.

---

## 17. First run: bulk commons only

1. `--verify` the servo poses, then run every test in `test_hardware.py --no-mock` once.
2. **Dry run:** load **20–30 bulk commons** and run `venv/bin/python main.py --dry-run`. Every card is identified, weighed and sent to the **reject bin**, whose pause limit is 35. Watch for:
   - one card per pick (weight 1.3–2.3 g);
   - card centring offsets ≤ 2.5 mm;
   - clean identification;
   - every card landing in the reject bin.
3. **Sorting run:** load 50 commons and run `venv/bin/python main.py`. Watch the web UI at `http://riftbound-sorter.local:5000`.
   - Check every bin's cards by hand.
   - Check the bin-full pause. Limits are lower floor 50, upper floor 24, reject 35 (`main.py` `DEFAULT_BIN_LIMITS`; override in `config/bin_limits.json`). After emptying a bin, reset it in the web UI or with `main.py --empty-bin N` / `--empty-all`.
4. Only after **several hundred commons** run with no jam, double pick or mis-route, sort anything of value. Even then, empty the bins well before their limits.

Before powering off, always stop with `sudo systemctl stop riftbound-sorter` (or Ctrl-C). That parks the arm and levels the cradle. Then shut down and unplug the 12 V.

---

## 18. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Pump runs at boot or after the program exits | 10 kΩ pull-up on GPIO 17 missing | Fit it (§14.2). Run the safe-state test (§14.8). |
| Arm lifts nothing | Cup not reaching the card; leak; pump on the wrong port | Jog ARM_PICK deeper (slider must compress). Pinch-test the tube. Use the pump **inlet**. |
| Card won't release at the drop | Pump check valves hold the vacuum (no vent valve) | Increase `RELEASE_S` in `main.py`. Add a tiny bleed hole (≈0.3 mm) in the tube near the pump (§19). |
| Card dropped off-centre, rides on a guide | ARM_DROP X is off; card released > 1.7 mm off in Y | Re-calibrate ARM_DROP. Check the hopper card isn't sitting against one wall. |
| "Hopper empty" with cards loaded | Flag not reaching the card; top switch set too high | §16.3. Check the flag drops freely and the plate notch is under the flag. |
| Elevator stalls or misses steps | Binding on the rods or lead screw; steps too fast | Check the carriage slides by hand. Don't go below `MIN_STEP_S`. |
| Jam: card not seen at the scanner | Belt slipping; `TRAVEL_SIGN` wrong; reference frame taken with a card present | §16.6. Check the coupling set screws on the rod flats. |
| Card stops off-centre | `BELT_SPEED_MM_S` / `BRAKE_COAST_MM` | §16.6, test 9. |
| Misidentification | Glare; crop off; DB stale | Keep the LED strips in their bands. Redo §16.5. `main.py --build-db`. |
| Image upside-down or mirrored | `CARD_ROTATE`; bracket FPC edge not facing −Y | §16.5. Re-mount the camera. |
| "No card on the cradle" (jam) | `EXIT_TRAVEL_S` too short; card caught at the belt end | §16.6. Check the cradle is LEVEL and 0.7 mm under the belt. |
| Weight "unknown" / drifting | Load-cell lead tugging the cradle; cradle touching the TF | Re-route the trailing loop (§14.7). Check the cradle touches only the cell. Re-tare. |
| Card hangs on the cradle lip | PTFE tape missing or worn; tilt pose short | Re-tape. Re-calibrate upper/lower. |
| Card hits a tray wall | Column off by > 1 mm | Re-calibrate that column (§16.4). |
| Shuttle stalls or jerks | Tilt-crank set screw tightened; LM8UU misaligned | Loosen the set screw (§13.2). Re-align the end posts. |
| PCA9685 not found (`i2cdetect`) | SDA/SCL swapped; VCC missing | §14.2. |
| `vcgencmd get_throttled` ≠ 0x0 | Logic rail overloaded; bad wiring; 3 A adapter in use | Check that only the Pi, LEDs and relay are on Reg #1 (L9110S and ULN2003 on Reg #3). Use the 12 V 5 A adapter. Check the 22 AWG runs. |
| Belt twitches at boot or after exit | L9110S inputs floating | Fit the 10 kΩ pull-downs on GPIO 23–26 (§14.2). |
| PCA9685 flaky / I²C errors | PCA9685 VCC on 5 V; missing V+ capacitor | VCC to Pi 3.3 V. Fit 1000 µF at V+. |
| Web UI unreachable | Service down | `journalctl -u riftbound-sorter -n 50`; `sudo systemctl restart riftbound-sorter`. |

---

## 19. Known risks / test first

1. **MG996R rotation range (test before printing the arm).**
   - The arm needs **~170°** of servo travel (ARM_DROP 5° → ARM_PICK 175°). The ch2 shuttle needs **~176°** (reject 2° → column 0 178°).
   - Many MG996Rs give only ~120° with standard pulses; the code uses 500–2500 µs.
   - **Test:** bolt a horn on, command 5°, 90° and 175° with `calibrate_servos.py --no-mock`, and measure with a protractor.
   - **Fallback: DS3218MG-270** (~$15). For the arm, set `ARM_ACTUATION_RANGE = 270` in `hardware/servos.py` and re-calibrate. For ch2, `shuttle.py` has no actuation-range setting yet, so it would need a code change (§20).
2. **PTFE tape on the cradle is required.** Without it the upper-floor transfer jams. Check it every few hundred cards.
3. **Bin capacities are small:** lower slots ~50 cards (17 mm), upper slots ~24 (8 mm), reject 35 (17.4 mm under the lane lip). The machine pauses with the card held on the cradle until the bin is reset (web UI or `--empty-bin`). A taller riser would buy upper-floor capacity, but that is a design change.
4. **Column accuracy is ±2 mm** (servo slider-crank plus backlash) against ±1 mm of slot clearance. Calibrate each column (§16.4) and re-check after any knock.
5. **Tight clearances to check on the printed parts:**
   - shuttle cradle / tilt frame / carriage / ramp: 0.5–0.8 mm;
   - card to hopper wall during the lift: 1.09 mm;
   - ch2 crank tip at column 0 reaches Y −269 against a 270 mm baseplate edge;
   - hood clips and guide funnel within a few mm of the arm drop.
6. **Vacuum release.** The relay only cuts the pump; there is no vent valve. The R385's internal valves can hold vacuum, so the card may stick to the cup. `RELEASE_S` (0.3 s) assumes it leaks down. Test with commons. If cards stick, add a ~0.3 mm bleed hole or a vent valve (needs another GPIO).
7. **Camera ribbon length** is ≈ 440–490 mm on a 500 mm cable. Test-fit first. The fallback is a longer 15-to-22-pin cable (third-party, 1 m).
8. **Load-cell lead routing** isn't in the CAD (§14.7). A snagged lead mis-weighs cards or gets torn.
9. **The arm falls on power loss** and drops the card. Always stop the service before unplugging.
10. **12 V supply.** The arm-move peak with the pump on is ≈ 3.2 A, over the owned 3 A adapter. **Use the 12 V 5 A adapter** (64 % at peak). The 3 A one is for bench tests with the servos unplugged.
11. **O-ring belts** run at 7.4 % stretch. NBR relaxes over time; if a card slips, replace the belts.
12. **Card position under the camera.** The Y margin is only 4.2 mm worst case. Cards must stay in the 66.4 mm guide channel.
13. **Glare.** The LED strips must stay below 21 mm above the card or foils will show a hotspot.
14. **Hopper-empty detection** depends on the plate notch passing under the flag. Check it in §10 with an empty plate.

---

## 20. Where the code and the CAD disagree

Found while writing this guide. They are reported here, not fixed in the CAD or code (this guide works round them).

| # | Where | Disagreement | Workaround in this guide |
|---|---|---|---|
| 1 | `shuttle.scad` BOM, `tilt_crank()` | An M3 set screw locks the tilt crank on the D-shaft, but the crank is captured in the carriage pocket and must **slide** along the fixed D-shaft as the carriage moves. | Leave the set screw loose (§13.2). |
| 2 | `shuttle.scad` `end_post_neg()` vs BOM | BOM: 4 × M2.5 for the ch1 ears. The cage has only 2 pilots (X 105, Z 9.5 / 58.5). | 2 screws (or drill 2 more). |
| 3 | `shuttle.scad` end posts | Baseplate holes at (100, −170), (110, −170), (98, 249), (114, 249) are not on the 30 mm tile grid (the comment says "X 110 grid"). | Drill through the tile (§13.2). |
| 4 | `electronics_tray.scad` | Corner holes land at X −142 / 27, Y 88 / 197, off the tile grid. | Drill through (§5). |
| 5 | `electronics_tray.scad` | PCA9685 standoffs are 25 × 60; the usual PCA9685 board is ≈ 19 × 56. The obsolete TAL221 pocket is still there. There are no mounts for the regulators, relay, L9110S, ULN2003 or barrel jack. | Foam tape; drill the jack hole (§5). |
| 6 | `riser.scad` anchors | The comment says M3 × 80 / threaded rod, but the head sits at the well bottom (Z 10), so the clamp is only 10 mm + board. | M3 × 20 with a 6 mm board (§6). |
| 7 | `suction_arm.scad`, `conveyor_rail.scad`, `shuttle.scad` | Through-bolt lengths assume no board (arm tower M3 × 16), a 12 mm board (rail M3 × 25), or M3 × 25 (end posts). | All lengths restated for a 6 mm board. |
| 8 | `assembly-steps.yaml` step 4 vs `motor_mount.scad` | The video fits motor mounts before the rods and collars (step 5); the bracket must go on after the collars are tightened. | Mounts fitted at the end of §8. |
| 9 | `baseplate_tile.scad` | The default export has pins on the top/right edges, but the only hole options are also on the top/right, so pins can never mate. | Print without pins (§2). |
| 10 | `sorting_tray.scad` header | Still describes gate routing, "reject = small tray at end of lower floor", and slot names that differ from `config/rules.json` (bin 4 Legendary/Epic, 5 Rare, 6 Common/Basic, 7 Default). | Bins follow `rules.json`. |
| 11 | `slide_bed.scad` header | Camera axis X −40, hood X −77.5..−2.5, card plane "machine 30.9": all pre-riser / pre-cam_x values. Now X +5, X −49..59, Z 90.9. | — |
| 12 | `conveyor_rail.scad` header | Feet "to the baseplate". They now stand on the riser (through-bolts or riser inserts). | §7 |
| 13 | `lower_ramp.scad`, `reject_bin.scad` | Comment `xt = sg_tray_x0() // 175`; the value is 178. | — |
| 14 | `hardware/servos.py` docstring | Still lists ch1 "deflect gate" and ch2 "bin select" and 2 sort-gate levers. The code itself owns only ch0, and ch1/ch2 belong to `shuttle.py`. | Channel table §14.3 |
| 15 | `hardware/conveyor.py` docstring | Says pigpio PWM; it uses RPi.GPIO software PWM. | — |
| 16 | `hardware/shuttle.py` | ch2 uses 2..178° (as much range as the arm), but there is no `actuation_range` setting for a 270° fallback servo. | §19.1 |
| 17 | `camera_bracket.scad` | Estimates the ribbon at ≈ 420 mm. The `assembly.scad` route to the Pi connector computes to ≈ 490 mm square-on. | 45° fold, test-fit (§14.5). |
| 18 | `assembly.scad` | Pump is a stand-in only: no printed pump mount. Load-cell trailing loop not modelled. Harness modelled through the +X slots (the −X slots are new). | §14.4–14.7 |
| 19 | `main.py --calibrate` | Uses one card assumed to weigh 1.75 g as the reference mass, not a known weight. | Good enough to classify single/double; noted in §16.1. |
| 20 | `hardware/card_detect.py` | The centring constants are module constants (no config file). Calibration means editing code. | §16.6 |
| 21 | `scripts/setup.sh` (as of b5d3bc8) | The venv was created without `--system-site-packages` (so picamera2/libcamera may not import) and installed `hx711` from PyPI instead of gandalf15 from git. `raspi-config do_camera` is obsolete on Bookworm. The code agent is fixing setup.sh. | §15 step 3 check |
| 22 | Code | No GPIO switches the LED strips; they are on whenever the logic rail is. | — |
