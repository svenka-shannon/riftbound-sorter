# Riftbound Card Sorter: Build Guide (v2)

This guide covers the v2 machine from the Nov 2026 redesign, including the audit fixes of 12 Nov 2026:
- **Hopper:** a motor-raised floor, so the top card always sits at pick height.
- **Pick arm:** one servo, a parallelogram linkage and a suction cup. It lifts the card straight up and puts it down flat on the belt. A vent valve breaks the vacuum so the card drops cleanly.
- **Conveyor:** a 60 mm riser carries 4 round O-ring belts. The belt stops when the camera sees the card centred under the lens.
- **Cradle shuttle:** it receives the card at the belt end, weighs it at rest, moves it to one of 4 columns or the reject bin, and tips it into the upper or lower floor of the 2-floor tray.

The cards are **valuable raw (unsleeved) cards**. Build and calibrate with **bulk commons only** (§17), and read **§19 Known risks / test first** before you print anything big.

Every dimension and screw below comes from the headers and BOM footers of `cad/*.scad`, or from `hardware/*.py`; the file is cited where it isn't obvious. Machine coordinates (`cad/machine_frame.scad`, `cad/assembly.scad`):
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
7. [Step 4: rails and bearings](#7-step-4-rails-and-bearings)
8. [Step 5: slide bed, belts, rollers, rods, collars, motor mounts](#8-step-5-slide-bed-belts-rollers-rods-collars-motor-mounts)
9. [Step 6: scan station](#9-step-6-scan-station)
10. [Step 7: hopper elevator](#10-step-7-hopper-elevator)
11. [Step 8: pick arm](#11-step-8-pick-arm)
12. [Step 9: sorting tray](#12-step-9-sorting-tray)
13. [Step 10: cradle shuttle, load cell, lower ramp, reject bin](#13-step-10-cradle-shuttle-load-cell-lower-ramp-reject-bin)
14. [Step 11: wiring and vacuum](#14-step-11-wiring-and-vacuum)
15. [Software setup and operation](#15-software-setup-and-operation)
16. [Calibration (in this order)](#16-calibration-in-this-order)
17. [First run: bulk commons only](#17-first-run-bulk-commons-only)
18. [Troubleshooting](#18-troubleshooting)
19. [Known risks / test first](#19-known-risks--test-first)
20. [Where the code and the CAD disagree](#20-where-the-code-and-the-cad-disagree)

---

## 1. Before you start

**Machine layout** (`cad/assembly.scad`, part headers):

| Assembly | Where |
|---|---|
| Baseplate | 3 × 3 tiles of 190 × 180, X −285..285, Y −270..270, top Z 4 |
| Electronics tray | X −150..35, Y 80..230 (185 × 150 × 45) |
| Riser | X −165..85, Y −113..80, Z 4..64 (the deck is the rail base) |
| Conveyor | Belt X −165..85. Rollers at X −140 / +60, rod axis Z 79. Card face (belt top) Z 90.9. Slide bed X −127..47. Rail top Z 99. |
| Scan station | Hood X −49..59. Lens axis X +5. Lens tip Z 190.9 (100 mm above the card). |
| Hopper elevator | Cavity centre X −215, Y 0. Footprint X −263.5..−166.5. Rim Z 94.4. Motor top Z ≈ 158. |
| Pick arm | Servo axis X −154.7, Z 151.8. Tower foot X −188..−112, Y −173..−122. Pick at X −215, drop (card centre) at X −95. |
| Pump bracket | X −276..−234, Y −234..−186, Z 4..47. Pump axis Y −210, Z 28; nozzles to X ≈ −183. |
| Shuttle | Cradle X 92..169. Carriage rod at X 106, Z 24. Carriage centre travels Y −102..176. |
| Sorting tray | X 178..276, Y −137..137, open back face at X 178 |
| Reject bin | Y 141..211 (beside the tray), X 178..276 |

**One sort cycle** (`main.py`):
1. The elevator raises the stack until the feeler flag trips.
2. The arm picks the card (pump on), carries it over the top and holds it 3 mm above the belt at X −95. `vacuum.release()` switches the pump off and opens the vent valve for 0.4 s, so the card drops. The arm lifts slowly for the first ~10° (a card still stuck to the cup peels off onto the belt), then parks.
3. The belt runs until `card_detect` sees the card centred under the lens at X +5, then brakes.
4. The camera captures and the card is identified.
5. The belt carries the card the exit distance (144 mm) at the belt speed measured during centring, and the card slides onto the cradle (home, level). It must weigh in fully on the level cradle before anything tips it.
6. The cradle tips to HOLD (10°) and the card is weighed at rest.
7. If the target bin is full, the machine pauses with the card held on the cradle.
8. The shuttle moves to the column and tips the card into the upper or lower floor, or into the reject bin.
9. The cradle is checked empty, re-tared and levelled.

**Tools:**
- 60 W soldering iron with an M3 heat-set insert tip.
- Hex keys 1.5–2.5 mm, plus a **long-arm 2.5 mm** key for the riser anchors (54 mm deep wells).
- Small Phillips screwdriver (self-tapping screws).
- Calipers.
- Drill with Ø3.4 and Ø8.0 bits; Ø3.0 and Ø4.0 bits for reaming by hand (§2).
- Hacksaw or Dremel for cutting the 4 mm rod and the 8 × 6 tube.
- Fine file.
- Utility knife.
- Small mallet (tile keys).

There is **no multimeter** in this build, which is why all three regulators are fixed-output modules. Never substitute an adjustable buck without a meter (BOM.md → Optional cost-down lists safe fixed-output alternatives).

---

## 2. Print list and settings

The full list is the **Printed parts** table in `BOM.md`: part, quantity, material, file/selector, orientation and supports. Summary:
- **PLA:** baseplate tiles and keys, electronics tray, riser, rails, rollers, slide bed, camera bracket, hopper, sorting tray, cradle, R-bars, lower ramp, reject bin.
- **PETG:** arm (all parts), card guides and clips, tilt frame, shuttle sled and cheeks, tilt crank and link, ch2 crank and link, end posts, pump bracket. Motor mounts can be PETG or PLA.
- **Black:** scanner hood (PLA or PETG). Make the card guides black too if you can.
- **TPU 95A:** the pump sleeve, if you can print TPU. Otherwise wrap the pump in a neoprene strip (§14.6).

| Setting | Value |
|---|---|
| Layer | 0.2 mm. Exceptions: cradle 0.12 mm (iron the top), lower ramp 0.16 mm, riser 0.24 mm. |
| Walls | 3–4 (5 for arm crank, links and ch2 crank) |
| Infill | 15–40 % per part (BOM table). Crank hub, tilt crank and tilt link 100 %. |
| Supports | **None** for every part except the shuttle **tilt frame** (tree supports under the plate bottom edges and the skid nubs). |
| Bed | All parts fit 256 × 256 mm (Bambu P1S). |

Notes:
- **Export:** `openscad --backend=manifold -o part.stl -D 'part="cradle"' cad/shuttle.scad`. The `sorting_tray.scad` sections and the rollers are picked by editing the last lines of the file or with a wrapper `use <…>` file.
- **Baseplate:** 9 × `part="tile"` and one plate of 24 keys, `part="keys"`.
- **Cradle:** it prints bed-top up with every rib standing on one flat plane, but that plane is only ≈ 600 mm². **Use a brim.**
- **Shuttle carriage:** it is three prints, the `sled` (on its +y face) and two `cheek_neg` / `cheek_pos` (flat on the outer face). `part="carriage"` is only a preview.
- **Lower ramp:** prints **upright as modelled** (base on the bed). The 4 mm top bar is a 53 mm bridge: bridge fan 100 %.
- **Arm XY scale test:** before the arm head and hand, print a 50 mm XY scale test. The two plates only need to carry the *same* pivot pattern (`suction_arm.scad`), so print both links in one job.
- **Suggested print order** (long prints first): 9 tiles + keys; riser A/B; tray sections; hopper body; arm tower; everything else.

**Post-processing:**
- **Rails:** none needed. The 608 pockets are Ø22.15 press fits; tune ±0.05 if they print tight or loose.
- **Rollers:** ream the bore with an 8 mm drill bit, keeping the D-flat.
- **Shuttle sled:** ream the D-shaft bushings to Ø8.3 and the ch2 drive-pin journal to Ø4.0+ (slip fit on the 4 mm shoulder).
- **Tilt frame:** ream the F-pin holes to Ø3.9 and the pin-A bore to Ø2.95 (turn a Ø3.0 bit by hand, lightly: the Ø3 dowel must stay a firm fit).
- **ch2 crank:** check the tip journal (Ø4.1) turns freely on the 4 mm shoulder.
- **Lower ramp:** sand the lanes with 600 grit.
- **R-bar:** sand the top.
- **Cradle:** cover the bed and kick with PTFE tape (§13.1).

---

## 3. Heat-set inserts

<!-- PENDING CAD round 3: insert count may change (hopper carriage nut screws, guide-rod clamps, valve/tee mount) -->

Fit **all 44 M3 inserts before any part is assembled**. Use M3 brass inserts for a Ø4.0–4.2 mm hole, 5.7 mm long (Ruthex / CNC Kitchen type). The ch2 link also takes **2 short M3 × 4 inserts** (OD ≤ 4.6 mm), listed at the end of the table.

Technique:
- Iron temperature: 210–220 °C for PLA, 230–245 °C for PETG.
- Use the insert tip and press straight down with light pressure.
- Stop about 0.3 mm proud, then flatten the insert flush with a steel ruler and hold it 10–30 s.
- **Check:** an M3 screw threads in by hand and the insert does not spin.

Every insert hole in the design:

| Part | Qty | Where / hole | Takes |
|---|---|---|---|
| Rail `front1` | 2 | Ø9 pads ±15 mm either side of the shaft, 9 mm above it; Ø4.1 blind 9 mm (`conveyor_rail.scad`) | motor mount, M3 × 10 BHCS |
| Rail `front2` | 2 | same | motor mount, M3 × 10 BHCS |
| Roller | 1 each = 2 | radial Ø4.0 × 6 at mid-length, on the flat side (`conveyor_roller.scad`) | M3 × 6 cup-point grub onto the rod flat |
| Riser A | 1 | deck top at front foot X −50, Y −75 (Ø4.0 × 7, 14 mm relief below) | rail foot, M3 × 10 |
| Riser B | 3 | deck top at front feet X −20, +10 (Y −75) and back foot X +40 (Y +75) | front: rail foot + camera bracket, M3 × 16. Back: rail foot, M3 × 10. |
| Riser B | 2 | internal front wall behind the tie-tab recess, X −30.5, Z 37 and 56; Ø4.0 × 6.5, pressed in along +Y from the front face | front tie, M3 × 10 countersunk |
| Hopper body | 4 | tower walls under the cap, local (±44.5, 41) and (±44.5, 64.5), Ø4.0 × 6.1 | cap, M3 × 10 |
| Hopper cap | 2 | motor-ear bosses on the underside, 35 mm apart | 28BYJ-48 ears, M3 × 8 |
| Hopper carriage | 2 | top face, ±8 mm (PCD 16) beside the T8 bore | T8 nut flange, M3 × 10 |
| Hopper carriage | 2 | shelf, local (±9, 26.5), through 7 mm | floor plate, M3 × 10 countersunk |
| Arm head | 4 | back face of the ground plate, servo tab pattern 10 × 49.5 (Ø4.1 × 6.2) | MG996R tabs, M3 × 10 |
| Arm tower | 4 | column top, (±5, Y −134/−126) relative to the servo axis | head, M3 × 12 |
| Arm hand | 2 | beam tops at X ±12 (horizontal when printed) | guide screws, M3 × 40 |
| Shuttle cradle | 2 | boss underside, on the load-cell free end (Y ±3) | M3 × 10 through the cell |
| Shuttle sled | 6 | 3 in each side face at (X, Z) (112.5, 39), (97, 50), (114.5, 16.5); Ø4.0 × 6.5 | cheeks, M3 × 10 countersunk |
| R-bar −Y (`rbar_neg`) | 2 | lap splice at X 99.5, Y ±10, from the split face (Z 64.5) down; Ø4.0 × 8 | splice, M3 × 10 |
| Pump bracket base | 2 | saddle ears at Y −189.5 and −230.5 (pump axis ± 20.5) | cap, M3 × 10 |
| **Total (M3 × 5.7)** | **44** | | |
| ch2 link (short M3 × 4) | 2 | Ø4.0 through at both ends, pressed **flush from the top** | ch2 shoulder screws |

Everything else is either a clearance hole (Ø3.2–3.6, with a nut) or a deliberate self-tapping pilot:
- Ø2.5: sorting-tray stacking (M3 × 12 countersunk).
- Ø2.6: shuttle rod clamps (M3 × 10), arm guide-screw tails.
- Ø2.9: cheek dowels in the sled (press fit); pin-A bore in the tilt frame.
- Ø2.15: electronics-tray M2.5 posts and corner blocks.
- Ø2.2: M2 hopper-switch holes (clearance, with nuts).
- Ø2.1: M2.5 servo-ear pilots (ch1 cage, ch2 riser pocket and end-post shelf).
- Ø2.0: ch2 crank → horn M2 countersunk.
- Ø1.8: camera M2.
- Ø1.7: Pololu M2 posts.

**Never press an insert into a clearance hole.**

---

## 4. Step 1: baseplate and backing board

<!-- PENDING CAD round 3: baseplate fastening may change to tee-nuts in the MDF board -->

Parts: 9 tiles; 24 bow-tie keys; a 6 mm plywood/MDF board at least 570 × 540; 8 rubber feet. Optionally 18 × M3 × 16 with nuts and washers.

1. **Lay the tiles** on the board in a 3 × 3 grid, all the same way round, with no gaps: 570 × 540 mm, tile corners at X −285/−95/95/285 and Y −270/−90/90/270. Every tile edge has 2 dovetail half-pockets; on every seam two of them face each other and form one bow-tie pocket.
2. **Keys.** Press a key into every seam pocket (24 in all; 12 interior seams × 2), from above, with a light mallet tap. A seated key sits 0.1 mm below the tile top, so parts bolted across a seam still sit flat. The keys lock the seams in X and Y and pull the tiles together; the board keeps them flush vertically.
3. **The grid.** Each tile has Ø3.4 holes every 30 mm, starting 15 mm in from its edges. Because a tile is 190 wide, **the X grid restarts on each tile column**: X −270..−120, −80..70 and 110..260 (6 holes each, 30 apart). Y runs continuously: Y = −255 + 30 j, from −255 to 255.
4. **Drill the board.** Tape the tiles down and use them as the template. Drill **Ø3.4 holes in the board** at every hole a later step uses (47 in all). Every part now bolts to real grid holes; nothing is drilled through a tile.

| Step | Machine X | Machine Y |
|---|---|---|
| Electronics tray (§5) | (−120, 105), (−50, 105), (−120, 195), (10, 195) | |
| Riser anchors (§6) | (−150, −105), (−150, 75), (−80, −15), (−20, 75), (−20, 45) | |
| Rail through-feet (§7) | (−80, −75), (−120, 75), (−80, 75), (10, 75) | |
| Hopper (§10) | −240, −180 | ±15 |
| Arm tower (§11) | −180, −120 | −165, −135 |
| Sorting tray (§12) | 200, 260 | −105, −45, 45, 105 |
| Shuttle end post −Y (§13) | (110, −165), (110, −195), (140, −165) | |
| Shuttle end post +Y (§13) | (110, 225), (110, 255), (140, 255) | |
| Lower ramp (§13) | 140 | ±45, ±105 |
| Reject bin (§13) | 200, 230 | 165, 195 |
| Pump bracket (§14.6) | −270, −240 | −225, −195 |

5. Optional: clamp each tile with 2 × M3 × 16 + washer + nut at free grid holes (tile 4 + board 6 = 10 clamp).
6. Stick 8 rubber feet (≥ 10 mm tall) under the board, clear of the nut positions above. The nuts and screw tips stick out up to ~7 mm.

**Check:**
- A straightedge across tile joints shows no step over 0.3 mm.
- Every key is flush or just below the tile tops.
- The board doesn't rock.

**Screw-length rule for every through-bolt in this guide:** clamp length + 4 mm (washer 0.5, nut 2.4, ≥ 1 mm of thread). Lengths below assume this 6 mm board.

To save the 1.2 kg of tile filament, the board can be drilled from a printed template instead; see BOM.md → Optional cost-down, which also explains what that does to alignment.

---

## 5. Step 2: electronics tray

Parts: electronics tray; Pi Zero 2 W, PCA9685, 2-channel relay, ULN2003, three regulators, HX711, L9110S; barrel jack; Wago connectors; 3 × 1000 µF. Screws:
- 4 × M3 × 20 + washer + nut (tray → board).
- 16 × M2.5 × 6–8 self-tapping (Pi 4, PCA9685 4, relay 4, ULN2003 4).
- 6 × M2 × 5–6 self-tapping (Pololu regulators, 2 each).
- Foam tape (HX711, L9110S).

The tray has a mount for every board (`electronics_tray.scad`). Tray-local x = machine X + 150, y = machine Y − 80.

1. **Place the tray** at X −150..35, Y 80..230: its front face touches the riser's back face at Y 80. Its 4 mounting holes are real grid holes: machine (−120, 105), (−50, 105), (−120, 195), (10, 195). Fasten with **4 × M3 × 20**, head inside the tray, washer + nut under the board (floor 2.5 + tile 4 + board 6 = 12.5 clamp).
2. **Barrel jack.** The Ø8.2 hole is in the tray's **+Y (back) wall**, tray-local x 92, 18 mm up. It takes a DC-022-type jack with an M8 × 0.75 thread. If your jack has an 11 mm thread, open the hole to Ø11.2.
3. **Mount the boards.** Posts and blocks have blind pilots; board undersides sit 5 mm above the floor (Pololus 4 mm), clear of their solder tails.

| Board | Mount | Tray-local position | Machine X, Y |
|---|---|---|---|
| Pi Zero 2 W | 4 posts, 58 × 23 pattern, M2.5 | x 107..172, y 5..35 | X −43..22, Y 85..115 |
| PCA9685 | 4 posts, **55.88 × 19.05** pattern (Adafruit #815; the blue clone copies it), M2.5 | x 108..170, y 44..69 | X −42..20, Y 124..149 |
| 2-ch relay | 4 solid 8 × 8 corner blocks, 44.3 × 32.8 pattern, M2.5 | x 5..55, y 42..80.5 | X −145..−95, Y 122..160.5 |
| ULN2003 board | 4 corner blocks, 30 × 26.5 pattern, M2.5 | x 62..97, y 42..74 | X −88..−53, Y 122..154 |
| HX711 | corner-stop pocket, 1 mm foam tape | x 62..97, y 82..104 | X −88..−53, Y 162..184 |
| L9110S | corner-stop pocket, 1 mm foam tape | x 38..67, y 5..29 | X −112..−83, Y 85..109 |
| D24V22F5 (logic) | 2 posts on the diagonal, M2 | x 40..58, y 125..143 | back strip |
| D24V50F5 (servo) | 2 posts on the diagonal, M2 | x 62..80, y 125..145 | back strip |
| D36V28F5 (motor) | 2 posts on the diagonal, M2 | x 104..122, y 125..145 | back strip |
| Wago bank, capacitors | free floor | x 126..180 (back strip); x 5..55 y 85..108; x 105..180 y 75..110 | |

   - Turn the Pi so its **camera (CSI) connector faces +X** (machine X ≈ 22, Y ≈ 100). That puts it close to where the camera ribbon enters the tray (§14.5).
   - The relay and ULN2003 blocks are solid 8 × 8, so a clone whose holes are up to ±2.5 mm off the nominal pattern can be drilled Ø2.15 in place.
   - Keep the regulators apart from the Pi. They get warm.
4. **Cable slots.** Each X wall has three 10 × 6 mm slots at machine Y 100–110, 130–140 and 160–170, Z 40.5–46.5. The front harness enters through the **−X** slots (§14.4); the load-cell lead through a +X slot (§14.7).

**Check:**
- The tray sits flat and touches the riser footprint line at Y 80 without overlapping it.
- The Pi CSI connector is at the +X end of the board.
- No board edge touches another (the CAD keeps ≥ 3 mm between footprints).

---

## 6. Step 3: conveyor riser

Parts: `riser_a` (X −165..−40, plus a 16 mm front tie tab) and `riser_b` (X −40..85). Screws:
- 3 × M3 × 12 + nut: joint.
- 2 × M3 × 10 countersunk: front tie (into the 2 riser_b inserts).
- 5 × M3 × 20 + washer + nut: anchors.

1. **Joint.** Bolt A to B through the joint walls at X −40 with 3 × M3 × 12 + nut at (Y, Z) (−30, 40), (30, 30), (65, 30). Reach the heads and nuts from the open bottom.
2. **Front tie.** The joint's front is tunnel, so riser A's front skin carries on past the joint as a 16 × 3 tab (X −40..−24, Z 30..64) that sits flush in a recess in riser B's front face. Fit **2 × M3 × 10 countersunk** from the front into the riser B inserts at X −30.5, Z 37 and 56. The heads sit flush, clear of the harness at Z 45.
3. Set the riser on the baseplate at X −165..85, Y −113..80, deck up. The **open tunnel** under riser B (open below Z 26, closed by a 3 mm roof) is for the ch2 crank and link. It must stay empty: nothing taped or cabled in it.
4. **Anchors (do this now, before the conveyor; the slide bed later covers two wells):** fit 5 × M3 × 20 down the Ø6.8 wells from the deck top, at (−150, −105), (−150, 75), (−80, −15), (−20, 75), (−20, 45). The head sits on the 6 mm floor of the boss at Z 10. Washer + nut under the board (6 + tile 4 + board 6 = 16 clamp). Use the long-arm 2.5 mm hex key down the 54 mm well.

**Check:**
- The deck is flat. A straightedge along X shows no step at the X −40 joint.
- Deck height above the baseplate top is 60.0 ± 0.3 mm (deck Z 64).
- The ch2 servo's front-ear pocket in riser B's front face (X 69..86, Y −113..−105.8, Z 25..37) is clean; the servo goes in at §13.5.

---

## 7. Step 4: rails and bearings

Parts: 4 rail halves, 4 × 608ZZ. Screws:
- 4 × M3 × 80 (or 85 mm threaded rod) + washer + nut: through-feet.
- 2 × M3 × 10: insert feet X −50 front and X +40 back. The X −20 and +10 front feet wait for the camera bracket (§9).

The motor mounts are **not** fitted in this step. They go on at the end of §8, because each mount's flange covers its rod collar's set screw (`assembly-steps.yaml` step 5).

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

   Clamp stack for the through-feet: foot 4 + riser 60 + tile 4 + board 6 = 74, so M3 × 80 leaves 6 mm for washer and nut. With threaded rod, use a washer + nut at both ends.
5. **Motor mounts, bench part** (fitted in §8). Slide each N20 into its mount's sleeve from the rear. Screw the gearbox face to the face plate with **2 × M1.6 × 4**, reaching through the Ø18 flange hole. Push a 3 → 8 coupling's 3 mm bore onto the N20 shaft, set screw on the D-flat, 6.5 mm engagement, and leave it loose.

**Check:**
- Rail gap is **90.0 ± 0.3 mm** at both shaft stations (rod axes X −140 and +60, 15 mm above the deck).
- Rails are parallel.
- Rail top is 35 mm above the deck (Z 99).
- The card-guide groove along each rail's inner top edge is 2.5 tall and **1.8 deep**, leaving a **1.2 mm fin** along the rail top. The fin carries the hood and the clip jaws (§9): check it isn't damaged.

---

## 8. Step 5: slide bed, belts, rollers, rods, collars, motor mounts

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
6. **Centre the roller.** Leave a **1.0 mm gap to each rail inner face** (roller 88 in the 90 gap). Tighten the M3 × 6 cup-point grub through the roller insert onto the rod flat. The belt grooves have 45° flanks; each cord seats in the R1.6 groove bottom.
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

1. **Guides.** Drop each guide into its rail's top groove: groove fill down (it rests on the groove floor at Z 96.5), flat face against the rail inner face. They run X −155..85.
   - Channel width is **66.4 mm**: a 63 mm card + 1.7 mm per side.
   - Guide underside is Z 90.4 (0.5 below the card underside). The 45° funnel catches a card lowered up to 4.9 mm off-centre.
2. **LED strips.** Stick one 88 mm strip in each long-wall recess band inside the hood: 10 mm tall, 10–20 mm above the card face, i.e. Z 100.9–110.9. Pass the leads out through the Ø4 holes at the downstream end (X +45). **Keep the strips inside that band.** Glare from a strip only misses the card while the strip stays below 21 mm above the card face (`scanner_hood.scad`).
3. **Hood.** Lower it straight down over the rails: skirts outside the rails, end walls straddling the guides. It stands **only on the rails' 1.2 mm top fins** at Z 99 (|Y| 47.1..48, ≈ 190 mm² per side) and keeps 0.4 mm clear of the guides. It spans X −49..59. The card slots in the end walls are |Y| ≤ 34, ceiling Z 94.9.
4. **Clips.** Press 4 clips over the rail walls at **X −62 and X +72**, both rails. Each clip's bridge rests on the guide top and the fin top, its inner leg seats in the guide-top pocket and its outer jaw grips the rail's outer face. The X −62 clip is the one nearest the arm drop zone; nothing else above the rail top is allowed between X −80 and the hood.
5. **Camera.**
   - Connect the SC1130's 15-pin end to the camera, contacts toward the PCB connector contacts.
   - Feed the ribbon through the bracket plate's 20 × 7 slot.
   - Screw the PCB **lens-down** onto the 4 standoffs with **4 × M2 × 10 self-tapping** (Ø1.8 pilots, 21 × 12.5 pattern), **FPC edge facing −Y (toward the plate)**. This turns the image 180°; the camera's ISP flips it back (`camera.ROTATE_180`).
6. **Bracket.** Lower it straight down so the lens drops into the 15 × 15 roof port. Its foot sits on the front rail feet at X −20 and +10 (Y −75). Fit **M3 × 16** through bracket foot (6) + rail foot (4) into the riser inserts; the insert hole has a 14 mm relief below for the extra length.
7. Put the black foam ring round the lens on the roof. It closes the 2.9 mm gap between roof and PCB.

**Check / measure:**
- Lens tip Z 190.9 (100 mm above the card face). PCB front Z 197.9. Hood roof top Z 195.0.
- A card slides by hand along the whole channel with ~1.7 mm play each side and never touches a clip or the hood.
- Field of view at the card: 129.9 × 74.8 mm in the full-field 2304 × 1296 sensor mode the code forces (§16.5). Y margin is 5.9 mm per side centred, 4.2 mm worst case.
- To lift the hood later: remove the 2 bracket screws first.

---

## 10. Step 7: hopper elevator

<!-- PENDING CAD round 3: hopper carriage nut screws and guide-rod clamp screws -->

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

**The cavity** is 91 × 66 (1.5 mm play round an 88 × 63 card), with r 1.2 vertical corner reliefs. From 1 mm below the top card's face (local Z 85.9, machine Z 89.9) up, the cavity **steps out**: 1.0 mm on the +X (belt-side) wall and 0.5 mm on the other three. This **lift relief** exists because the cup rises 2° off vertical and the card drifts +X as it is lifted; the step keeps a card that lies against any wall clear of it. The rim has a 0.8 mm × 45° chamfer.

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
- Head, tower, crank, links B and C, hand, cup sled, 4 sleeves.
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
- 4 × M3 × 20 + washer + nut (tower → board: foot 6 + tile 4 + board 6 = 16 clamp).

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
   - Press the pad's 8 mm hex into the cup sled.
   - Fit the barb through the web into the pad (gasket).
   - Put the springs on the M3 × 40 guide screws (heads down), slide the cup sled on, and screw into the hand-beam inserts.
6. **Tube.** Run it barb → loop → through the A' tube → free "spoke" (≈ 97 mm) → anchor bell on the servo axis → down the back of the column. Leave ~10 mm of slack in the hand loop.
7. **Tower and head.** Fit the head onto the tower with **4 × M3 × 12** into the column-top inserts. Bolt the tower foot to the baseplate at X −180 / −120, Y −165 / −135 with **4 × M3 × 20** + washer + nut.
8. **Zip ties.** The column has two tie tunnels 2.5 mm behind its back face at **Z 55 and Z 80**, open through both side faces (above the foot gussets, which end at Z 50). Thread a 100 mm tie in one side and out the other round the tube and the servo lead.

**Check / measure** (with `calibrate_servos.py` menu 1, §16.2):
- Servo axis at X −154.7, Z 151.8. Crank radius 60.3 mm.
- **PARK 90°:** crank vertical, hand over X −155.
- **PICK ≈ 175°:** cup lip 3 mm **below** the top card (Z 87.9). The spring slider takes up the overtravel (10 mm stroke). The cup comes down within 2° of vertical.
- **DROP ≈ 5°:** card underside 3 mm above the belt (Z 93.9), card centre X −95, i.e. the card spans X −139..−51.
- During the lift a centred card clears the hopper by 1.5 mm, and a card lying 1.5 mm off-centre against any wall by ≥ 0.49 mm (`cad/pick_arm_check.py`). Watch the first lifts.
- **No link touches another** over the whole sweep (`cad/pick_arm_check.py` checks the CAD).

---

## 12. Step 9: sorting tray

Parts: sections A, B (lower), C, D (upper), 2 shelf halves. Screws:
- 8 × M3 × 20 countersunk + washer + nut (lower floor → board).
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

<!-- PENDING CAD round 3: shuttle install order and fasteners (ch1 servo/coupler, ch2 ear block) -->

Parts:
- Cradle, tilt frame (TF), **sled + 2 cheeks** (the carriage), tilt crank, tilt link, ch2 crank, ch2 link, R-bar −Y / +Y, end posts −Y / +Y.
- TAL221 load cell.
- 8 × 400 rod, 8 mm D-shaft 400.
- 2 × LM8UU, 2 × 688ZZ.
- Dowel pins: 2 × Ø4 × 8 (F pins), 1 × Ø3 × 20 (pin A), 4 × Ø3 × 8 (cheek ↔ sled).
- 2 MG996R (ch1, ch2).
- ch1 coupler: 25T disc horn + 8 mm flange coupling.
- ch2: MG996R round 25T horn (from the servo bag), 2 shoulder screws (4 mm shoulder, M3 × 4 thread; one 5 mm and one 6 mm shoulder).
- PTFE tape.
- 2 lower-ramp halves, reject bin.

Screws (`shuttle.scad` BOM):
- 2 × M3 × 12: TF crossbar → cell tapped end.
- 2 × M3 × 10: cell free end → cradle inserts.
- 6 × M3 × 10 countersunk: cheeks → sled inserts (3 per cheek).
- 1 × M3 × 16 + nylock: tilt crank ↔ tilt link.
- 2 × M3 × 10: R-bar splice (Y ±10).
- 2 × M3 × 10: rod clamps.
- 4 × M2.5 × 10 self-tapping: ch1 ears.
- 4 × M2.5 × 10 self-tapping: ch2 ears.
- 4 × M2 × 6 countersunk self-tapping: ch2 crank → horn disc.
- 1 × M3 × 12 countersunk: ch2 crank hub → servo spline.
- 4 × M3 × 8: ch1 horn ↔ flange coupling.
- 6 × M3 × 20 + washer + nut: end posts (3 each).
- 4 × M3 × 20 + washer + nut: ramp.
- 4 × M3 × 20 countersunk + washer + nut: reject bin.

There is **no set screw** anywhere on the tilt crank: it slides along the D-shaft with the carriage and is keyed by its D-bore.

### 13.1 Tilt frame, load cell, cradle

<!-- PENDING CAD round 3: shuttle install order (ch1 servo position and coupler, ch2 ear block) -->

**Order matters:** the F pins are pressed in from **inside** the tilt frame, and once the cradle is on, its edge is only 0.8 mm from the side plate on the F axis. So the F pins go in first, before the load cell and the cradle.

1. **F pins (first).** Ream the TF's F-pin holes to Ø3.9 and the pin-A bore to Ø2.95 (§2). Press a **Ø4 × 8 dowel** into each side plate **from inside**, until its inner end is flush with the plate's inner face (|Y| 36). It then sticks 4 mm out past the plate's outside (to |Y| 44), where the cheek hooks will take it (§13.2).
2. **PTFE tape (required).** Cover the cradle bed and the 18° kick with **0.1 mm skived PTFE tape**, wrapping 2 mm over the lip. No bubbles or wrinkles; trim the edges with a knife. Bare PLA (μ ≈ 0.35–0.45) jams the upper-floor transfer (`shuttle_check.py`).
3. **Cell to TF.** Fit the TAL221's **tapped (cable) end** to the TF crossbar pad with **2 × M3 × 12** from below (counterbored holes). The cable goes toward the front notch in the crossbar.
4. **Cell to cradle.** Fit the cradle boss to the cell's **free end** with **2 × M3 × 10** from below through the cell's holes into the cradle inserts.
5. **Check:** the cradle touches nothing but the cell (0.8 mm to each TF plate). Press the cradle bed lightly and it must spring back. Cradle with tape is ≈ 19 g (target ≤ 35 g).

### 13.2 Carriage (sled + cheeks) and tilt drive, on the bench

The carriage is three prints: the **sled** (rod and D-shaft bores, the ch1 crank pocket and the ch2 drive-pin arm, |y| ≤ 40.5) and two bolt-on **cheeks** (|y| 40.5..45.5) that carry the F-pin hooks. **Fit pin A before the cheeks:** the dowel goes in from outside the +Y TF plate, and the +Y cheek closes that path (`shuttle_check.py assembly`).

1. **Bearings and dowels.** Press an LM8UU into each end of the sled (Ø15.1 × 24.1 pockets; both bearings sit wholly in the sled). Press the 4 Ø3 × 8 dowels into the sled's side faces (Ø2.9, 2 per side).
2. **Tilt crank and link.** Join the tilt link to the crank tip with **M3 × 16 + nylock**, snug so the joint pivots freely without play. Put the crank into the sled's swing pocket. It is captured there and will slide along the D-shaft.
3. **Tilt frame and pin A.** Hold the TF (with cell and cradle) in its level position over the sled, the link's free end in the TF's link slot. Push the **Ø3 × 20 dowel (pin A)** in along −Y from outside the +Y TF plate, through the Ø3.3 entry bore and the link, until it bottoms at Y 1.5 on the Ø2.9 → Ø2 shoulder. It is a firm fit in the Ø2.9 bore on both sides of the link. (To remove it later: cheek off, knock it out from −Y through the Ø2 hole.)
4. **Cheeks.** Offer each cheek onto its sled side so the F pin drops into the hook in the cheek's inner face and the 2 dowels enter the cheek's Ø3.1 holes. Fit **3 × M3 × 10 countersunk** per cheek into the sled inserts, heads flush with the outer face. The cheek root closes the LM8UU pocket mouth and retains the bearing.
5. **Load-cell lead.** Zip-tie it in the slot on the −Y cheek (X 150..154, Z 70). The rest of the route is in §14.7.

### 13.3 Rail system: end posts, rod, D-shaft, R-bar

<!-- PENDING CAD round 3: rod clamp screws -->

1. Press a 688ZZ into each end post's inner-side pocket (Ø16.05).
2. **Dry-assemble on the bench:**
   - Rod through post −Y → carriage LM8UUs → post +Y. The rod sits Y −160..232 at X 106, Z 24.
   - D-shaft through post −Y 688ZZ → sled bushing → tilt crank D-bore → sled bushing → post +Y 688ZZ. The D-shaft sits Y −168..232 at X 105, Z 44.
   - Fit the 2 rod clamps (M3 × 10 down into the Ø2.6 pilot in each post).
3. **R-bar.**
   - Join `rbar_neg` and `rbar_pos` at the 32 mm lap splice (Y −16..16) with **2 × M3 × 10** at Y ±10, down into the `rbar_neg` inserts. The heads sit 0.3 mm below the top; the skids land at Y ±1..4, clear of the counterbores.
   - Seat the ends in the end-post R-bar seats. The bar runs Y −150..232 at X 95..104.
   - The home notches at |Y| 29..45 must line up under the TF skids at home.
4. **Mount the module.** Set the whole assembly in place (posts at Y −160..−150 and 232..242). The floor-plate holes are on the baseplate grid: post −Y at (110, −165), (110, −195), (140, −165); post +Y at (110, 225), (110, 255), (140, 255). Fit **6 × M3 × 20** + washer + nut (plate 4 + tile 4 + board 6 = 14 clamp).

### 13.4 ch1 (tilt) servo

<!-- PENDING CAD round 3: ch1 servo moves ≈ 15 mm −Y with a new coupler -->

1. Seat the MG996R in the −Y end post's cage, spline on the D-shaft axis at Y −168, body toward −Y. Fit **4 × M2.5 × 10 self-tapping** into the cage pilots at X 100 / 110, Z 9.5 / 58.5.
2. **Coupler.** Fit a 25T aluminium disc horn to the spline and bolt it to an 8 mm-bore rigid flange coupling on the D-shaft end (4 × M3 × 8). Check the coupling's hole circle matches the horn's M3 pattern before buying (BOM). If they don't match, drill the flange.
3. Power ch1 to **HOLD = 97°** and fit the coupler so the cradle is **10° nose-down** about the F pins. Trim it in §16.4.

### 13.5 ch2 (shuttle) servo, crank and link

<!-- PENDING CAD round 3: ch2 ear ceiling block and its new install order -->

The ch2 MG996R **hangs upside down** under the riser: output axis at X 80, Y −124, case face Z 26.3, spline down (`shuttle_geom.scad`). Under it, from the bottom up: link Z 9..14, crank Z 15..19 (and the carriage's drive-pin arm Z 15..20), shoulder-screw heads to Z 24, riser tunnel roof from Z 26. Nothing hangs below the link.

**The crank's hub screw can only be fitted on the bench:** once the servo hangs under the riser, the crank's countersunk face points down at the baseplate. So do steps 1–3 before step 4.

1. **Horn onto the crank (bench).** Lay the round 25T horn's disc on the crank's top face over the 4 holes (Ø2.0 on Ø14). Fit **4 × M2 × 6 countersunk self-tapping** from the crank's bottom (countersunk) face up into the horn disc, heads flush.
2. **Set the angle (bench).** Plug the servo into ch2 and set it to **home = 75.5°** (`calibrate_servos.py --no-mock`, menu 3). The servo angle equals the crank angle ψ: 0° = crank pointing +Y (reject end), 90° = pointing −X. Press the horn onto the spline with the crank at ψ = 75.5°.
3. **Hub screw (bench).** Drive **1 × M3 × 12 countersunk** up through the crank hub into the spline (≈ 4.9 mm engagement), head flush with the crank bottom. It replaces the horn screw from the servo bag.
4. **Mount the servo.**
   - **Front ear:** into the pocket in riser B's front face (X 69..86, Y −113..−105.8, Z 25..37). Fit **2 × M2.5 × 10** up into the pocket ceiling at X 75 and 85 (the X 85 one goes into a 4 mm lug on riser B's +X face).
   - **Rear ear:** under the −Y end post's shelf, **2 × M2.5 × 10** up into the shelf.
5. **ch2 link.** Its 2 short M3 × 4 inserts are pressed flush into its top (§3). The link lies under the crank and under the carriage's drive-pin arm.
6. **Crank-tip pivot.** Command ch2 to **column 0 (178°)**: the crank tip is then at Y −263, outside the riser, and reachable from above. Drop the **5 mm-shoulder screw** in from above through the crank tip's Ø4.1 journal into the link's insert.
7. **Drive-pin pivot.** Command ch2 to **reject (2°)** and slide the carriage by hand to the reject position (Y ≈ 177): the link's other insert then lines up under the carriage's drive-pin journal. Drop the **6 mm-shoulder screw** in from above.
8. Command ch2 back to home (75.5°). The carriage must sit at Y 0 with the cradle centred on the belt.

### 13.6 Lower ramp and reject bin

1. **Lower ramp.** Set the two halves on the baseplate directly behind the tray's open back: lane exit at X 178, entry X 160.4, Z 34.7. Fit **4 × M3 × 20** + washer + nut through the rear floor tabs at X 140, Y ±45 and ±105. The dividers line up with the tray walls, and the 4 mm fins (X 174..178) rise to the top bar at Z 100..104.
2. **Reject bin.** Set it at Y 141..211 beside the tray. Fit **4 × M3 × 20 countersunk** + washer + nut through the box floor at X 200 / 230, Y 165 / 195.

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
         ├─ Relay COM1 ── Relay NO1 ── pump (+)          [1N5819 across the pump]
         └─ Relay COM2 ── Relay NO2 ── vent valve (+)    [1N5819 across the valve coil]
           (each diode: cathode/stripe to +, anode to −)
  GND ───── GND bus (Wago) ── every regulator GND, every module GND, pump (−), valve (−)

Reg #1 VOUT ── Pi pin 2 (5 V)        Reg #2 VOUT ── PCA9685 V+ screw terminal ONLY
           ├── LED strips +                    ├── 1000 µF at the regulator output
           └── relay VCC                       └── 1000 µF across V+/GND at the PCA9685

Reg #3 VOUT ── L9110S VCC (both N20s)
           ├── ULN2003 + (28BYJ-48)
           └── 1000 µF at the regulator output

Pi pin 1 (3.3 V) ── PCA9685 VCC (logic; MUST be 3.3 V), HX711 VCC
Pi pin 17 (3.3 V) ─┬─ 10 kΩ ── GPIO 17 (relay IN1, pump)
                   └─ 10 kΩ ── GPIO 27 (relay IN2, vent valve)
GND ── 10 kΩ ── GPIO 23, 24, 25, 26 (L9110S inputs), one resistor each
```

- **The relay is a 2-channel 5 V module with active-LOW inputs:** IN1 = pump, IN2 = vent valve. Leave its JD-VCC jumper (if it has one) fitted so the coils run from VCC.
- **Check the relay switches OFF with 3.3 V logic (bench test, before wiring it in).** The module runs from 5 V, but the Pi drives IN at 3.3 V, and the pull-ups hold IN at 3.3 V for "off". On a board where the input indicator LED is in series with the opto LED, 5 V − 3.3 V = 1.7 V isn't enough to light them, so 3.3 V reads as off. On a board without that series LED, 1.7 V can still half-light the opto and the relay may stay on. Test each channel:
  1. Module VCC to 5 V (Reg #1 or a 5 V bench supply), GND to GND. Nothing on IN1 / IN2.
  2. Jumper IN1 to GND: the relay must click and its indicator LED light.
  3. Move the jumper from GND to the Pi's 3.3 V pin (pin 1 or 17): the relay must click **off** and the LED go fully dark. Repeat a few times.
  4. Repeat for IN2.
  
  If a channel stays on (or chatters) at 3.3 V, the module is not 3.3 V-compatible. If it has a **JD-VCC jumper**, remove the jumper, feed **VCC** (the opto side) from the Pi's 3.3 V and **JD-VCC** (the coils) from Reg #1's 5 V, keep GND common, and repeat the test. Otherwise use a relay module sold as 3.3 V-logic compatible.
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
| 12 | 32 | in, pull-up | top-of-stack switch (C → GND pin 34) <!-- PENDING code round 2 --> | `elevator.py` | contact (NO or NC) and active level: see the note below |
| 13 | 33 | in, pull-up | home switch (C → GND pin 30) <!-- PENDING code round 2 --> | `elevator.py` | as above |
| 16 | 36 | out | ULN2003 IN1 | `elevator.py` | SoC pull-down at boot; the ULN2003's internal input resistors keep a floating input off |
| 19 | 35 | out | ULN2003 IN2 | `elevator.py` | |
| 20 | 38 | out | ULN2003 IN3 | `elevator.py` | |
| 21 | 40 | out | ULN2003 IN4 | `elevator.py` | |
| 17 | 11 | out | relay **IN1** (**active LOW** = pump ON) + **10 kΩ to 3.3 V** | `vacuum.py` | the pull-up keeps the pump off when the pin floats |
| 27 | 13 | out | relay **IN2** (**active LOW** = vent valve OPEN) + **10 kΩ to 3.3 V** | `vacuum.py` | the pull-up keeps the valve coil off (valve closed) when the pin floats |
| 23 | 16 | out (PWM) | L9110S A-1A (motor A forward) **+ 10 kΩ to GND** | `conveyor.py` | pull-down: pins float after `cleanup()` |
| 24 | 18 | out | L9110S A-1B (motor A reverse / brake) **+ 10 kΩ to GND** | `conveyor.py` | |
| 25 | 22 | out (PWM) | L9110S B-1A (motor B forward) **+ 10 kΩ to GND** | `conveyor.py` | |
| 26 | 37 | out | L9110S B-1B (motor B reverse / brake) **+ 10 kΩ to GND** | `conveyor.py` | |
| — | 2, 4 | power | 5 V in from Reg #1 | | |
| — | 1, 17 | power | 3.3 V → **PCA9685 VCC**, HX711 VCC, the two 10 kΩ pull-ups | | PCA9685 VCC must be 3.3 V |
| — | 6, 9, 14, 20, 25, 30, 34, 39 | GND | GND bus | | |
| CSI | — | | Camera Module 3 via SC1130 | `camera.py` | connector faces +X |

- **The L9110S is plain GPIO, not I²C.** Its VCC comes from Reg #3, not the Pi rail.
- **Pins float after `cleanup()`.** The SoC's default pulls only apply from power-on until a program configures the pin. RPi.GPIO `cleanup()` (`conveyor.deinit()`, `vacuum.deinit()`, `elevator.deinit()`) returns them to inputs with **no pull**. The external resistors set the safe level:
  - 10 kΩ pull-ups on GPIO 17 and 27: pump off, vent valve closed.
  - 10 kΩ pull-downs on GPIO 23–26: belt coasts.
- **Hopper switches** <!-- PENDING code round 2 -->: each SS-5GL2-F has three tabs, C (common), NO and NC. C goes to GND; which of NO or NC goes to the GPIO, and whether "pressed" reads LOW or HIGH, is set by `SWITCH_ACTIVE_LEVEL` and the switch notes in `hardware/elevator.py`. Wire them the way that file says. (This is being changed in the code; details to follow.)
- HX711 pins: **DOUT (DT) = GPIO 5, SCK (CLK) = GPIO 6** (`hardware/loadcell.py`).
- HX711 wiring to the cell: E+ red, E− black, A+ white, A− green (confirm with your cell).
- 28BYJ-48: its keyed 5-pin plug goes into the ULN2003 board.
- Relay: COM1 and COM2 to 12 V+, **NO1** to the pump, **NO2** to the vent valve. If power is lost the pump stops and the valve closes.

### 14.3 PCA9685 channels (I²C 0x40, 50 Hz, 500–2500 µs)

| Ch | Servo | Owner | Nominal angles (calibration overrides) |
|---|---|---|---|
| 0 | Pick arm (MG996R) | `hardware/servos.py` → `config/servo_calibration.json` | ARM_PICK 175, ARM_DROP 5, ARM_PARK 90 |
| 1 | Cradle tilt (MG996R, D-shaft) | `hardware/shuttle.py` → `config/shuttle_calibration.json` | level 93.1, hold 97.0, upper 112.2, lower 41.5 |
| 2 | Shuttle carriage (MG996R, slider-crank) | `hardware/shuttle.py` → `config/shuttle_calibration.json` | reject 2.0, col 3 45.0, col 2 65.2, home 75.5, col 1 87.3, col 0 178.0 |
| 3–15 | unused | | |

- **Level is 93.1°**, 0.5° past the geometric 92.6° so the skids sit firmly on the home ledges. Keep that preload small: past the hard stop the servo stalls against the ledge while the cradle waits level.
- PCA9685 power: VCC = 3.3 V from the Pi (logic and I²C pull-ups), V+ = Reg #2 servo rail (5 V 5 A), with 1000 µF across V+/GND at the board.
- Servo leads: brown/black = GND, red = V+, orange = signal (the `PWM` row). Use 100 cm extensions from the tray to each servo.

### 14.4 Harness route

There is no front-to-back pass through the riser. The ch2 crank and link sweep the floor in front of and under riser B (Z 9..24), so **the only route goes round the hopper's −X side** (`assembly.scad` `asm_harness()`):

1. **Collect at the front.**
   - The N20 leads drop down the front of the riser.
   - The arm servo lead runs from the head-floor slot (Y ≈ −108), under the head, and down in front of the column (Y −117.5).
   - The ch1 and ch2 leads join them.
   - Bundle everything to Ø ≈ 7 mm and clip it to the **riser's front face at Z 45**, above the ch2 linkage.
2. **Around the −X end.** Run the bundle along the front (Y −117.5) to X −277, in front of the arm column. Drop to Z 12 outside the hopper and run along the −X edge to Y 135.
3. **Into the tray.** Turn +X at Y 135 and enter the tray through its **−X wall slots** (X −150, Y 100..170, Z 40.5..46.5), fanning the leads out over the three slots.

**Lengths** (from the `asm_harness()` polyline): the trunk from the riser's front face (X 66) to the −X slots is **≈ 0.8 m**. End to end, with the drop from each servo or motor and the run inside the tray to its board:
- ch1 and ch2 servo leads ≈ 1.0 m (servo lead + 100 cm extension);
- arm servo lead ≈ 0.75 m;
- N20 leads ≈ 0.85 m (motor B, X +60) and ≈ 0.65 m (motor A, X −140).

Other runs:
- **Hopper motor and switches:** run down the back of the tower (Y 80) and join the harness at the −X edge (≈ 0.2 m to the harness).
- **LED leads:** from the hood's Ø4 holes (X +45) over the back rail into the tray.
- **Keep clear of:**
  - the ch2 crank and link sweep (Z ≤ 24 under and in front of riser B);
  - the arm sweep above the hopper and belt inlet;
  - the shuttle carriage path (X 90..170).

### 14.5 Camera ribbon (SC1130, 500 mm)

1. Run the ribbon from the camera connector out through the bracket's −Y plate slot, up the plate, over the gusset and arm top (Z 234).
2. Bring it down behind the hood and the back rail (Y 62), over the riser deck's back edge (Y 80, Z 84).
3. Drop it into the tray at X ≈ 5, Y ≈ 88 and fold it gently into the Pi's CSI connector, which **faces +X** at machine X ≈ 22, Y ≈ 100.

- The CAD route to the tray entry is ≈ 405 mm; the run to the connector adds ≈ 30–45 mm, so **expect ≈ 0.45 m on the 500 mm cable**.
- **Test-fit the ribbon before you tie anything down** (§19).
- Ribbons are fragile: no sharp creases, no pulling at the connectors.

### 14.6 Pump bracket, vacuum tube and vent valve

<!-- PENDING CAD round 3: vent valve + tee mount on the pump bracket -->

**Pump bracket** (`pump_bracket.scad`). Screws: 4 × M3 × 20 + washer + nut (base → board); 2 × M3 × 10 (cap → base inserts).

1. **Isolation.** Slide the printed TPU sleeve onto the pump's motor can. No TPU? Wrap the can in a **1.5 mm neoprene or EPDM strip, 18 mm wide**, instead. The clamp closes a 1.0 mm gap onto it, so the squeeze is set by the geometry, not by screw torque.
2. **Base.** Bolt the base to the grid holes (−270, −225), (−270, −195), (−240, −225), (−240, −195) with **4 × M3 × 20** + washer + nut (base 5 + tile 4 + board 6 = 15 clamp).
3. **Pump.** Lay the pump in the saddle: axis along X (Y −210, Z 28), can X −268..−230, head toward +X, nozzles reaching X ≈ −183. Fit the cap and **2 × M3 × 10** into the base inserts.
4. Fit the 1N5819 (or 1N4007) flyback diode across the pump terminals: cathode (stripe) to pump +, anode to pump −. Twist the pump leads and keep them away from the I²C wires.

**Vacuum tube** (`assembly.scad` `asm_vac_tube()`), about 0.45 m in total:
1. A short silicone sleeve and a reducing barb take the pump's **inlet** (suction side) nozzle down to the 4 mm tube.
2. The tube runs from the nozzle (X ≈ −183, Y −210, Z 28) along Y −205, then up the back of the arm column (X −147, Y −160) through the tie tunnels at Z 55 and 80.
3. It goes into the anchor bell on the servo axis (Y −152.5), then out as the free spoke to the A' tube, then through the loop to the cup barb (§11).

**Vent valve** (`hardware/vacuum.py`): a **12 V normally-closed** mini solenoid valve, teed into the vacuum line between the pump and the cup. Energised = open to air.
1. Cut the tube a few cm after the pump nozzle and fit the 4 mm barbed tee. A short tube from the tee's branch goes to one valve port; the other valve port stays open to the air.
2. Mini valves seal best one way round: put **atmosphere on the IN (P) port** and the vacuum line on the OUT port. If the cup leaks down with the pump running and the valve shut, swap the ports.
3. Fix the valve on the baseplate next to the pump bracket with foam tape and a zip tie, clear of the arm sweep (everything here is Y ≤ −186, Z ≤ 47).
4. Wire it to relay NO2 / GND, with a 1N5819 across its coil like the pump.
5. `release()` switches the pump off, opens the valve for `VENT_S` = 0.4 s, then closes it. `pump_on()` always closes the valve first. To run without a valve, set `VENT_PIN = None` in `hardware/vacuum.py`; the code then just waits 0.3 s for the cup to leak down.

**Check:** `test_hardware.py --no-mock`, test 3 (vent valve). Hold the cup on a card while the pump runs: at release you hear the valve click and the suction vanishes at once, not slowly.

### 14.7 Load-cell lead (trailing loop, not modelled in CAD)

The cradle moves 278 mm in Y and tilts, and `assembly.scad` only says "trailing service loop (not modelled)". Suggested routing, **to be test-fitted**:

1. Splice about 1 m of 4-core flexible silicone wire (26–28 AWG) to the TAL221 leads at the cradle. Solder and heat-shrink the joint.
2. The lead leaves the TF crossbar notch, is zip-tied at the −Y cheek's slot, then runs down the cheek's outer face to the cheek bottom (Z 13).
3. From there it forms a **flat rolling loop on the baseplate under the carriage**, at about X 125–130. The moving end is under the carriage; the fixed end is taped to the baseplate at about Y 0.
4. The fixed lead then runs along the baseplate in +Y to Y ≈ 215 (past the ch2 link's sweep, which reaches Y 182), then −X along Y ≈ 215 to the tray's +X wall at X 35. Run it along the outside of that wall to the slot at Y 160–170 and in to the HX711 (machine X −88..−53, Y 162..184).

Keep it out of:
- the rod, LM8UU, D-shaft and tilt crank (X 98..118, Z 20..54);
- the R-bar top;
- the ch2 link (X ≈ 75..90, Z 9..14, swept up to Y 182);
- the lower-ramp tabs (X 136..160 at Y ±45, ±105);
- the +Y end post's tongue (X 104..122 from Y 219);
- the card path.

**Check:** run the shuttle through every column and reject (`test_hardware.py` test 5). The lead must never tighten, rub, or pass under the ch2 link.

### 14.8 Safe state

<!-- PENDING code round 2: teardown behaviour, systemd watchdog, safe-outputs ExecStopPost and the kernel cmdline parameter are being changed; this section will be updated with the final details. -->

What the hardware guarantees on its own (this does not depend on the software):

| Event | Pump / vent valve | Servos | Belt / elevator |
|---|---|---|---|
| 12 V pulled | pump **off** (relay NO opens); valve **closed** (normally closed) | limp. **The arm falls and drops any card.** Always stop the sorter before unplugging. | stop; the 28BYJ-48 gearbox holds the hopper floor |
| No program driving the pins (boot, after exit, after a crash) | **off / closed**: the 10 kΩ pull-ups on GPIO 17 and 27 hold both relay inputs HIGH | the PCA9685 keeps whatever it was last told until it is reset or powered off | the 10 kΩ pull-downs on GPIO 23–26 keep the L9110S coasting; the ULN2003 stays off |

What the software does on a stop, in outline (details in §15.4 and in `main.py`):
- A **stop request** (web UI Stop, or the first SIGTERM / Ctrl-C) finishes the card in progress first; a **second** signal stops at once.
- A card on the cup is never dropped mid-arc: it is released back onto the stack if the cup is still at the pick pose, otherwise carried to the drop pose and released onto the belt.
- The pump is switched off and the line vented, the belt stopped, the arm parked.
- **Shutdown leaves the shuttle carriage where it is**; it never homes on the way out. The servos are then de-energised (limp).
- Every stop is recorded in `data/machine_state.json` as **clean** (no card in the machine, shuttle at home + level, cradle empty) or **unclean** (with the reason). After an unclean stop the sorter won't start until you confirm the machine is clear (§15.4).
- `kill -9` skips all of this: the outputs keep their last level. Run `sudo systemctl stop riftbound-sorter` or reboot.

**Safe-state test** (pump hose off): boot the machine and watch the relay. Neither channel may click or light. After boot, `pinctrl get 17` and `pinctrl get 27` read `hi`, and `pinctrl get 23-26` read `lo`. Repeat after the sorter has run and exited.

---

## 15. Software setup and operation

### 15.1 Install

<!-- PENDING code round 2: dependency lock file, systemd watchdog, ExecStopPost safe outputs, kernel cmdline parameter -->

1. **Flash the SD card.** Use Raspberry Pi OS Lite 64-bit with Raspberry Pi Imager: **Bookworm or trixie** (the current release) both work. Enable SSH, set the user and Wi-Fi, and set the hostname to `riftbound-sorter`. The camera is auto-detected (`camera_auto_detect=1`); there is no `raspi-config` camera step.
2. **Clone and run setup:**

   ```bash
   git clone https://github.com/svenka-shannon/riftbound-sorter && cd riftbound-sorter
   bash scripts/setup.sh
   ```

   `scripts/setup.sh` does all of this:
   - Enables I²C, runs `apt-get update` and `upgrade`.
   - Installs the apt packages: `python3-pip python3-venv python3-picamera2 python3-libcamera python3-numpy python3-scipy python3-pywt python3-pil i2c-tools git libopenjp2-7 libtiff6 avahi-daemon`.
   - Installs **`python3-rpi-lgpio`**, the drop-in that provides `import RPi.GPIO` on current Raspberry Pi OS (it replaces `python3-rpi.gpio`). If the archive doesn't have it, it falls back to `python3-rpi.gpio`.
   - Creates `venv/` **with `--system-site-packages`**, so the venv can import the apt-only camera, GPIO and numpy modules. An existing venv made without that flag is deleted and re-created.
   - `pip install -r requirements.txt`: `adafruit-blinka`, `adafruit-circuitpython-pca9685`, `adafruit-circuitpython-motor`, `Pillow`, `imagehash`, `numpy`, `flask`, `requests` (on the Pi, Pillow and numpy are already satisfied by apt).
   - Checks that the venv can import `picamera2`, `libcamera`, `RPi.GPIO`, `numpy`, `PIL`, `imagehash`, `flask` and `board`, and runs `i2cdetect`.
   - Creates `cache/` and `data/`, sets the hostname, installs and enables the systemd service for this checkout and user.
   - Creates the web UI token and prints it (§15.3).

   Notes:
   - **HX711:** the gandalf15/HX711 library is **vendored** as `hardware/vendor/hx711.py` (BSD-3 licence alongside). There is nothing to install. **Do not** pip-install a package called `hx711`: the PyPI package of that name is a different library with an incompatible API.
   - **trixie:** `libtiff5` and `libatlas-base-dev` no longer exist there; setup.sh uses `libtiff6` and the apt builds of numpy, scipy and Pillow, which also keeps them ABI-matched with picamera2.
   - **Bookworm:** the same commands work; `python3-rpi-lgpio` is in the Bookworm archive too.
3. **Check the venv:**

   ```bash
   venv/bin/python -c "import picamera2, board; from hardware.vendor import hx711"
   ```

   If `picamera2` fails, the venv was made without system packages. Re-run `bash scripts/setup.sh`; it re-creates the venv.
4. **Check the hardware is seen:**
   - `sudo i2cdetect -y 1` shows `40` (PCA9685).
   - `rpicam-hello --list-cameras` (or `libcamera-hello`) shows `imx708`.
5. **Card database:** `venv/bin/python main.py --build-db` (needs internet). If the Riftcodex API is down later, the sorter uses the cached card list; with neither, it stays up, shows the reason in the web UI and retries every 60 s.
6. **Watchdog:**
   - Add `dtparam=watchdog=on` to `/boot/firmware/config.txt`.
   - Set `RuntimeWatchdogSec=15` in `/etc/systemd/system.conf`.
   - Reboot and check that `/dev/watchdog` exists.

### 15.2 Hardware tests

`venv/bin/python scripts/test_hardware.py --no-mock` gives a menu (A runs them all, Q quits):

| Menu | What it runs |
|---|---|
| 1 | pick arm (ch0): park / pick / drop |
| 2 | vacuum pump, 2 s |
| 3 | vent valve release (pump on, then pump off + vent pulse) |
| 4 | pick and place one card onto the belt |
| 5 | shuttle: every column, both floors, reject |
| 6 | cradle load cell |
| 7 | camera full frame + card crop |
| 8 | card detection, live offset (belt off) |
| 9 | conveyor run (3 s) + brake |
| 10 | belt centring (drop zone → lens) |
| 11 | hopper elevator: home, then raise to pick |

The banner printed by each test still uses the older numbering ("Test 2b", "Test 3" … "Test 10"); this guide always means the **menu** number. Off the Pi, `uv run scripts/test_hardware.py` runs the same menu in MOCK mode.

Always run hardware scripts with the **Pi venv python** (`venv/bin/python …`); a uv script environment has no GPIO, camera or PCA libraries. Off the Pi, `MOCK_HARDWARE=1 python main.py --dry-run` exercises the whole cycle, and `python -m pytest tests/` runs the mock test suite in `tests/`.

**First motion checks (before calibration):**
- **Elevator direction.** Put the plate mid-travel with no cards, run test 11 and watch the first second. If "home" moves the floor **up**, press Ctrl-C at once and set `UP_DIRECTION = -1` in `hardware/elevator.py`.
- **Belt direction.** Run test 9. Both rollers must move the card toward +X. Swap a motor's two leads if one runs backward.

### 15.3 Web UI and token

The web UI runs at `http://riftbound-sorter.local:5000` (or `http://<pi-ip>:5000`; set `RIFTBOUND_WEB_PORT` to change the port).

- **Token.** Every action that changes something needs the web UI token. It is generated on first use and stored in **`config/web.json`** (mode 600, not in git). Show it with:

  ```bash
  venv/bin/python main.py --web-token
  ```

  `setup.sh` prints it too. The browser asks for it the first time you press a protected button and remembers it. API clients send it as an `X-Auth-Token` header (or a `token` form field).
- **Read-only pages** (dashboard, inventory, exports, `/api/status`, `/api/bins`) need no token.
- **Dashboard controls** (token needed):

| Button | API | What it does |
|---|---|---|
| Pause | `POST /api/pause` | finishes the card in progress, then waits (state `paused`) |
| Resume | `POST /api/resume` | continues after a pause, a Stop or a refilled hopper |
| Stop | `POST /api/stop` | stops sorting at the next card boundary. The process and the web UI stay up; Resume starts again |
| Machine clear | `POST /api/confirm-clear` | you confirm the arm, belt and cradle are clear (any card removed) after an unclean stop or a jam. Same as `main.py --confirm-clear`. Refused while the machine is running |
| Empty (per bin) / Empty all | `POST /api/bins/<n>/empty`, `POST /api/bins/empty-all` | resets the count after you emptied the bin |
| Save (rules page) | `POST /rules` | validates, saves and hot-reloads `config/rules.json` |

- **Bins can only be emptied while the machine is paused or stopped** (that includes jam, hopper empty, error and waiting for confirmation). The one exception is the bin the machine is paused on because it is full: you may empty that one, and the sorter resumes 2 s after the reset. "Empty all" needs the machine paused or stopped. The web UI refuses anything else, because the shuttle may be moving. `main.py --empty-bin N` / `--empty-all` don't check the machine state, so only use them with the machine paused or stopped.

### 15.4 Starting and stopping

<!-- PENDING code round 2: teardown behaviour -->

**Starting** (`sudo systemctl start riftbound-sorter`, or `venv/bin/python main.py`):
1. The web UI comes up first, so problems are visible there.
2. **First start, or any start after an unclean stop:** the sorter waits in state `needs_confirm` with the reason (for example "no record of a previous clean shutdown (first start?)" or "a card was left on the cradle"). Check the arm, belt and cradle, remove any card, then confirm with **Machine clear** in the web UI or:

   ```bash
   venv/bin/python main.py --confirm-clear
   ```

3. Start-up then stops the belt, parks the arm, homes the hopper elevator, brings the shuttle home and checks the cradle.
4. **The sorter refuses to start with a card on the cradle.** Before it tares, it compares the cradle's raw reading with the stored empty-cradle reference (§16.1). More than 0.8 g above it stops start-up with "card on cradle — remove it", and asks for confirmation again. It never tares a card away.
5. After a clean stop, the servos start from their recorded rest pose, so the first moves are ramped. After an unclean stop their position is unknown, so the first commands are **full-speed jumps** (hobby servos have no position feedback). Keep hands clear.

**Stopping:**
- **Web UI Stop or Pause:** finishes the current card; the process stays up.
- **`sudo systemctl stop riftbound-sorter` or Ctrl-C:** the **first** signal finishes the card in progress, then shuts down. A **second** signal stops immediately (a card on the cup is put back on the stack or onto the belt, never dropped mid-arc).
- **Shutdown leaves the shuttle where it is**, with ch1 and ch2 limp; it never homes on the way out. The arm is parked first, then every servo goes limp.
- A card still on the cradle (for example during a bin-full pause) stays there; the stop is recorded as unclean and the next start asks you to remove it.
- Before unplugging the 12 V, always stop the service first.

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
- Saved values go to `config/servo_calibration.json` (arm, keys `ARM_PICK` / `ARM_DROP` / `ARM_PARK`) and `config/shuttle_calibration.json` (tilt, carriage).
- Without `--no-mock` nothing moves, but values **are** still written.

**Where each setting lives:**

| What | File |
|---|---|
| Arm angles | `config/servo_calibration.json` (calibrate_servos.py menu 1) |
| Tilt and carriage angles, ch2 actuation range, shuttle timing | `config/shuttle_calibration.json` (menus 2 and 3; edit `actuation_range` by hand) |
| Load-cell scale factor and empty-cradle reference | `config/loadcell_calibration.json` (`main.py --calibrate`) |
| Camera crop | `config/camera_crop.json` (`calibrate_camera.py`) |
| Belt centring, camera focus / exposure / rotation, exit run, arm lift, calibration mass | **`config/machine.json`** (§16.6) |
| Bin limits | `config/bin_limits.json` (§16.7) |
| Web UI token | `config/web.json` |
| Arm actuation range, elevator direction and trip offset | code constants: `hardware/servos.py` `ARM_ACTUATION_RANGE`; `hardware/elevator.py` `UP_DIRECTION`, `TRIP_EXTRA_STEPS` |

### 16.1 Load cell

1. Run `venv/bin/python main.py --calibrate`. The cradle goes to HOLD (the calibrated ch1 angle if there is one, otherwise the nominal, which is close enough).
2. Press Enter with the cradle **empty** to tare. This also stores the empty-cradle reference.
3. Put the reference mass flat in the middle of the cradle and press Enter. The default reference is a **US 5-cent nickel, 5.000 g**. For another known mass use `--mass G`, e.g. `main.py --calibrate --mass 10.0`. The scale factor is saved to `config/loadcell_calibration.json` and the script prints what the reference now reads.
4. Remove the reference and press Enter. The empty cradle is read again and, if it reads empty, tared once more.

**Empty-cradle reference.** `--calibrate` stores the empty cradle's absolute raw HX711 reading (`"empty_offset"`) with the scale factor, and every later verified-empty tare refreshes it. At start-up the sorter compares the cradle to this reference **before** it tares, so a card left on the cradle is caught (§15.4). Run the calibration with the cradle truly empty and the PTFE tape fitted. Re-run it if you re-tape the cradle or re-route the load-cell lead.

**Check** (test 6; each reading is the median of 7):

| Load | Expected reading | Class |
|---|---|---|
| Empty | 0 ± 0.3 g | empty at or below 0.5 |
| One card | 1.3–2.3 g | single |
| Two cards | ≥ 2.8 g | double |

Re-run this step if you change the HOLD angle in §16.4.

### 16.2 Arm (ch0)

Menu **1**. Use a sacrificial card. PICK and DROP start 8° short (toward PARK); jog the last degrees yourself.

- **ARM_PICK (≈175):** cup on the card centre with the slider visibly compressed (~3 mm of the 10 mm stroke). The card seals when the pump is on.
- **ARM_DROP (≈5):** card flat and ~3 mm above the belts. Its upstream edge should be **26 mm downstream of the rail inlet end** (card X −139..−51).
- **ARM_PARK (90):** crank vertical.

**DS3218MG-270 fallback** (§19.1): set `ARM_ACTUATION_RANGE = 270` in `hardware/servos.py` (default 180), then re-calibrate all three arm angles: they are servo degrees within that range.

**Check:** `test_hardware.py` test 4 (pick and place). The card lands flat inside the guide funnel, released ≤ 1.7 mm off-centre in Y.

### 16.3 Elevator trip height

Run test 11 (home, then raise to pick) with a stack of commons.

1. **Measure from the hopper rim down to the top card: target 3.5 ± 0.3 mm.** That puts the card at Z 90.9, level with the belt top.
2. **Coarse adjustment:** slide the top switch in its slots. Higher trip = less depth.
3. **Fine adjustment:** `TRIP_EXTRA_STEPS` in `hardware/elevator.py`. About 510 half-steps per mm (`STEPS_PER_MM` 509.5); positive values raise the card further after the trip.
4. Repeat with 10 cards removed and check it stays within ±0.3 mm.
5. Re-check ARM_PICK after any change.

The raise timeout scales with the distance still to travel, so even a nearly empty hopper straight after homing (≈ 70 s of travel) reaches pick height.

### 16.4 Shuttle: tilt and columns

1. **Menu 2, at home.**
   - **hold:** bed 10° nose-down, card tail clear of the rails, guides and clips.
   - **level:** skids firmly on the home ledges; bed 0.7 mm below the belt top. The default is **93.1°**; keep it only just past the point where the skids touch (§14.3).
2. **Menu 3, columns 0–3 and reject.**
   - Centre the cradle on each slot by eye, or drop a 65 mm card gauge into the slot and line the cradle up with it.
   - **Target: card centre within ±1 mm of the slot centre** (slot 65 for a 63 card). The upper lead-in fins funnel ±2 mm.
   - Every move ends travelling toward +ψ, to take up backlash.
   - Expect ±2 mm repeatability (§19), so calibrate **each column on its own**.
3. **Menu 2 again, at a column (default column 1).**
   - **upper:** the card slides off the lip into the upper slot.
   - **lower:** the skids land on the R-bar, the kick reaches −40° and the card runs down the ramp into the lower slot.
4. **Verify:** run `--verify`, then `test_hardware.py` test 5. With a card, check both floors of all 4 columns and the reject bin.

**DS3218MG-270 fallback for ch2** (§19.1): add `"actuation_range": {"2": 270}` to `config/shuttle_calibration.json` (ch1 can take `"1"` the same way), then re-calibrate every ch2 angle with menu 3.

### 16.5 Camera

The code forces the IMX708's **2304 × 1296 2×2-binned full-field mode at 50 fps** (`hardware/camera.py`). Without that, picamera2 picks a 1536 × 864 centre crop that sees only 2/3 of the field. At start-up the camera reads back its sensor mode and crop, derives the mm-per-pixel figures from what it actually got, and prints a loud warning if it is not the full field. The main stream is 768 × 432 (identification), the low-res stream 320 × 180 (centring), both 16:9.

Focus is fixed (`AfMode` manual) at **`LensPosition` 10** dioptres (= 1 / 0.100 m, the card face). After a 1 s warm-up on the empty station, exposure and white balance are locked so the empty-station reference frame stays valid when a bright card comes in. All of this can be changed in `config/machine.json` (§16.6).

**Crop.** Run `venv/bin/python scripts/calibrate_camera.py --no-mock`:
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

**`CARD_ROTATE`** (default 90, in the `camera` section of `config/machine.json`): if the saved crop is upside-down, set 270. It depends on which way the cards are loaded.

### 16.6 Machine tunables: `config/machine.json`

Belt centring, camera and sort timing are **per-machine settings in `config/machine.json`**, not code. Copy the example and edit it:

```bash
cp config/machine.example.json config/machine.json
```

Every key is optional; a missing key keeps the code default shown below. The file is read when the sorter starts, so restart it after an edit. `config/machine.json` is not in git. (`RIFTBOUND_MACHINE_CONFIG` points the code at another file.)

**`card_detect` section** (belt centring, `hardware/card_detect.py`):

| Key | Default | How to measure |
|---|---|---|
| `TRAVEL_SIGN` | 1 | Test 8 (live offset, belt off). Slide a card by hand in the travel direction (+X). The offset must **increase**; if it decreases, set −1. |
| `CENTRE_OFFSET_MM` | 0.0 | Place a card physically centred under the lens: hood inner end walls at X −45 / +55, so the card edges are 6.0 mm from each end wall. Read the offset in test 8 and **add** that reading to `CENTRE_OFFSET_MM`, so a centred card reads 0. |
| `BELT_SPEED_MM_S` | 150.0 | Mark a card's edge position, run test 9 (3 s), measure the distance moved and divide by 3. It also sets the seek timeout (`SEEK_MAX_TRAVEL_MM` 125 ÷ speed). |
| `STOP_LATENCY_S` | 0.040 | Age of the newest frame when the brake takes effect (≈ 1.5 frames at 50 fps + processing). Run test 10 (centring) at the nominal speed several times and adjust it until the mean stationary offset is ≈ 0. |
| `BRAKE_COAST_MM` | 1.5 | Test 10 5×. If the final offset is consistently +d mm (overshoot), add d. If it is consistently short, the nudges correct it; reduce slightly. |
| `CENTER_TOL_MM` | 2.5 | Stationary offset accepted without a nudge. |
| `MAX_CAPTURE_OFFSET_MM` | 6.0 | Above this the centring result is not ok (treated as a jam). |
| `PIXEL_DIFF`, `COL_FRAC` | 30, 0.3 | Detection thresholds: luma difference that counts as card; fraction of a column that must differ. Change only if detection is unreliable. |
| `VIEW_HALF_MM` | 48.0 | Visible half-window along X (hood interior ±50, less 2). |
| `SEEK_MAX_TRAVEL_MM`, `SEEK_HARD_LIMIT_FACTOR` | 125, 3.0 | Seek limits (also accepted). |

**`camera` section** (`hardware/camera.py`):

| Key | Default | Meaning |
|---|---|---|
| `LENS_POSITION` | 10.0 | dioptres = 1 / distance in m (100 mm → 10.0) |
| `AF_MODE` | `"manual"` | `"manual"` (fixed `LensPosition`) or `"continuous"` |
| `LOCK_AE_AWB` | true | freeze exposure and white balance after warm-up |
| `EXPOSURE_TIME_US`, `ANALOGUE_GAIN`, `COLOUR_GAINS` | null | fixed values instead of the converged ones (`COLOUR_GAINS` = [red, blue]) |
| `CARD_ROTATE` | 90 | 270 if cards are loaded the other way round (§16.5) |
| `STABILIZE_DELAY_S`, `WARMUP_S`, `SWAP_RB` | 0.15, 1.0, true | also accepted |

**`sort` section** (`main.py`):

| Key | Default | Meaning |
|---|---|---|
| `EXIT_TRAVEL_MM` | 144.0 | belt travel from "centred" to "fully on the cradle" (trailing edge X −39 past the belt end X 85, + 20) |
| `EXIT_TIME_MARGIN` | 1.25 | × the computed run time. The run uses the belt speed **measured** during centring, never more than `BELT_SPEED_MM_S` |
| `EXIT_MIN_S`, `EXIT_MAX_S` | 0.6, 3.0 | clamp on the exit run |
| `EXIT_EXTRA_S` | 0.4 | one extra belt burst if the card is only partly on the cradle |
| `ARM_LIFT_DEG`, `ARM_LIFT_S` | 10.0, 0.6 | the slow first lift after release |
| `CALIBRATION_MASS_G` | 5.0 | default reference mass for `--calibrate` |
| `SEAL_S`, `DROP_SETTLE_S`, `WEIGH_SETTLE_S`, `TARE_SETTLE_S`, `RESUME_DELAY_S` | 0.3, 0.1, 0.2, 0.3, 2.0 | also accepted |

**Exit run check:** with commons, the card must land fully on the cradle (tail off the roller, nose against the kick) 10 times out of 10. If it doesn't, raise `EXIT_TRAVEL_MM` a few mm. A short run is caught by the weight check ("card not fully on the cradle"), and the cradle is then **not** tipped.

**Target:** test 10 ends with |offset| ≤ 2.5 mm (`CENTER_TOL_MM`). Anything above 6 mm is reported as not ok.

### 16.7 Bin limits

The sorter counts cards per bin and pauses when a bin reaches its limit (`main.py` `DEFAULT_BIN_LIMITS`):

| Bins | Default limit | Why |
|---|---|---|
| 0–3, lower floor | **40** | 50 cards (16.5 mm) left < 1 mm of margin in the slide simulation; 40 ≈ 13 mm |
| 4–7, upper floor | **12** | the slide simulation (`cad/shuttle_check.py slide`) jams on a 4 mm pile at μ 0.45; 12 cards ≈ 4 mm loose |
| 9, reject | 35 | 17.4 mm of pile under the lane lip; 35 × 0.33 = 11.6 mm |

**To raise a limit**, create `config/bin_limits.json` with only the bins you change, e.g.

```json
{"0": 45, "4": 16}
```

Raise in small steps (a few cards at a time), and only after a run of bulk commons into that bin shows every card landing flat with the pile at the new height. The upper floor is the one to be careful with: cards that can't slide fully into the slot hang on the cradle lip.

---

## 17. First run: bulk commons only

1. `--verify` the servo poses, then run every test in `test_hardware.py --no-mock` once.
2. **Start the service and confirm.** `sudo systemctl start riftbound-sorter`, open the web UI, enter the token when asked (`main.py --web-token`), check the machine is clear and press **Machine clear** (first start, §15.4).
3. **Dry run:** load **20–30 bulk commons** and run `venv/bin/python main.py --dry-run` (stop the service first). Every card is identified, weighed and sent to the **reject bin**, whose pause limit is 35. Watch for:
   - one card per pick (weight 1.3–2.3 g);
   - a clean release at the drop (vent valve click, card flat on the belt);
   - card centring offsets ≤ 2.5 mm;
   - clean identification;
   - every card landing in the reject bin.
4. **Sorting run:** load 50 commons and run `venv/bin/python main.py`. Watch the web UI at `http://riftbound-sorter.local:5000`.
   - Check every bin's cards by hand.
   - Check the bin-full pause: limits are 40 lower, 12 upper, 35 reject (§16.7). Empty the bin, then reset it with its **Empty** button (or `main.py --empty-bin N`); the sorter resumes.
   - Try Pause, Resume and Stop.
5. Only after **several hundred commons** run with no jam, double pick or mis-route, sort anything of value. Even then, empty the bins well before their limits.

Before powering off, always stop with `sudo systemctl stop riftbound-sorter` (or Ctrl-C) and wait for it to finish the current card. Then shut down and unplug the 12 V.

---

## 18. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Pump runs or vent clicks at boot or after the program exits | 10 kΩ pull-up on GPIO 17 / 27 missing | Fit it (§14.2). Run the safe-state test (§14.8). |
| Arm lifts nothing | Cup not reaching the card; leak; pump on the wrong port; vent valve leaking | Jog ARM_PICK deeper (slider must compress). Pinch-test the tube. Use the pump **inlet**. Swap the valve's ports (§14.6). |
| Card won't release at the drop | Vent valve not opening (wiring, relay IN2, GPIO 27); valve fitted the wrong way round | Test 3. Check relay channel 2 clicks. `VENT_S` in `hardware/vacuum.py`. |
| Card dropped off-centre, rides on a guide | ARM_DROP X is off; card released > 1.7 mm off in Y | Re-calibrate ARM_DROP. Check the hopper card isn't sitting against one wall. |
| "Hopper empty" with cards loaded | Flag not reaching the card; top switch set too high | §16.3. Check the flag drops freely and the plate notch is under the flag. |
| Elevator stalls or misses steps | Binding on the rods or lead screw; steps too fast | Check the carriage slides by hand. Don't go below `MIN_STEP_S`. |
| Jam: card not seen at the scanner | Belt slipping; `TRAVEL_SIGN` wrong; reference frame taken with a card present | §16.6. Check the coupling set screws on the rod flats. |
| Card stops off-centre | `BELT_SPEED_MM_S` / `STOP_LATENCY_S` / `BRAKE_COAST_MM` | §16.6, test 10. |
| Camera warns "NOT the full field of view" | the sensor mode wasn't applied | Update picamera2 (`sudo apt upgrade`), re-run setup.sh. The centring margin is lost until it is fixed. |
| Misidentification | Glare; crop off; focus; DB stale | Keep the LED strips in their bands. Redo §16.5. Check `LENS_POSITION`. `main.py --build-db`. |
| Image upside-down or mirrored | `CARD_ROTATE`; bracket FPC edge not facing −Y | §16.5. Re-mount the camera. |
| "No card on the cradle" / "card not fully on the cradle" | exit run too short; card caught at the belt end | §16.6 (`EXIT_TRAVEL_MM`). Check the cradle is LEVEL and 0.7 mm under the belt. Lift the card off by hand, then **Machine clear**. |
| "card on cradle — remove it" at start-up | a card was left on the cradle, or the empty reference is stale | Remove the card and confirm. If the cradle really is empty, re-run `main.py --calibrate`. |
| Waits in `needs_confirm` | first start, or the last stop was unclean | §15.4: check the machine, then **Machine clear** or `--confirm-clear`. |
| Weight "unknown" / drifting | Load-cell lead tugging the cradle; cradle touching the TF | Re-route the trailing loop (§14.7). Check the cradle touches only the cell. Re-tare. |
| "load cell failed" | HX711 wiring or power; repeated failed reads | Check DOUT = GPIO 5, SCK = GPIO 6, VCC on 3.3 V. |
| Card hangs on the cradle lip | PTFE tape missing or worn; tilt pose short; bin pile too high | Re-tape. Re-calibrate upper/lower. Lower that bin's limit (§16.7). |
| Card hits a tray wall | Column off by > 1 mm | Re-calibrate that column (§16.4). |
| Shuttle stalls or jerks | LM8UU misaligned; tilt crank binding in the sled pocket; ch2 pivot screw too tight | Re-align the end posts. Check the crank slides freely along the D-shaft. The shoulder screws should spin the link freely. |
| Cradle servo hums or gets hot at home | level angle too far past the ledges | Back `level` off toward the touch point (§16.4). |
| PCA9685 not found (`i2cdetect`) | SDA/SCL swapped; VCC missing | §14.2. |
| `vcgencmd get_throttled` ≠ 0x0 | Logic rail overloaded; bad wiring; 3 A adapter in use | Check that only the Pi, LEDs and relay are on Reg #1 (L9110S and ULN2003 on Reg #3). Use the 12 V 5 A adapter. Check the 22 AWG runs. |
| Belt twitches at boot or after exit | L9110S inputs floating | Fit the 10 kΩ pull-downs on GPIO 23–26 (§14.2). |
| PCA9685 flaky / I²C errors | PCA9685 VCC on 5 V; missing V+ capacitor | VCC to Pi 3.3 V. Fit 1000 µF at V+. |
| Web UI says "missing or wrong token" | token not entered or changed | `venv/bin/python main.py --web-token`; clear the browser's saved token and re-enter it. |
| "machine is running: pause or stop it before emptying" | a bin reset while sorting | Pause or Stop first (§15.3). |
| Web UI unreachable | Service down | `journalctl -u riftbound-sorter -n 50`; `sudo systemctl restart riftbound-sorter`. |

---

## 19. Known risks / test first

1. **MG996R rotation range (test before printing the arm).**
   - The arm needs **~170°** of servo travel (ARM_DROP 5° → ARM_PICK 175°). The ch2 shuttle needs **~176°** (reject 2° → column 0 178°).
   - Many MG996Rs give only ~120° with standard pulses; the code uses 500–2500 µs.
   - **Test:** bolt a horn on, command 5°, 90° and 175° with `calibrate_servos.py --no-mock`, and measure with a protractor.
   - **Fallback: DS3218MG-270** (~$15). Arm: `ARM_ACTUATION_RANGE = 270` in `hardware/servos.py` (§16.2). ch2: `"actuation_range": {"2": 270}` in `config/shuttle_calibration.json` (§16.4). Re-calibrate after either.
2. **PTFE tape on the cradle is required.** Without it the upper-floor transfer jams. Check it every few hundred cards.
3. **Bin capacities are small**, and the default limits (40 lower, 12 upper, 35 reject) are deliberately conservative (§16.7). The machine pauses with the card held on the cradle until the bin is emptied and reset. Raise the limits only after testing. A taller riser would buy upper-floor capacity, but that is a design change.
4. **Column accuracy is ±2 mm** (servo slider-crank plus backlash) against ±1 mm of slot clearance. Calibrate each column (§16.4) and re-check after any knock.
5. **Tight clearances to check on the printed parts:**
   - shuttle cradle / tilt frame / carriage / ramp: 0.5–0.8 mm;
   - card to the hopper during the lift: 1.5 mm centred, ≥ 0.49 mm for a card lying 1.5 mm off-centre (lift relief, §10);
   - a card held 1.5 mm off-centre in Y passes the scan station's guides by 0.46 mm at the drop;
   - ch2 crank tip at column 0 reaches Y −269 against a 270 mm baseplate edge;
   - hood clips and guide funnel within a few mm of the arm drop.
6. **Vacuum release** depends on the vent valve (§14.6). A valve fitted the wrong way round can leak during a pick or fail to vent. Run test 3 and the pick-and-place test with commons. Without a valve (`VENT_PIN = None`) the code just waits 0.3 s, and the R385's check valves may hold the card on the cup.
7. **Camera ribbon length** is ≈ 0.45 m on a 500 mm cable. Test-fit first. The fallback is a longer 15-to-22-pin cable (third-party, 1 m).
8. **Load-cell lead routing** isn't in the CAD (§14.7). A snagged lead mis-weighs cards or gets torn.
9. **Servos are limp whenever the sorter isn't running** (and on power loss). The arm is parked before it goes limp, but with the 12 V pulled it falls and drops any card. Always stop the service before unplugging.
10. **First moves after an unclean stop are full-speed jumps** (§15.4). Keep hands out of the machine when you start it after a crash or power loss.
11. **12 V supply.** The arm-move peak with the pump on is ≈ 3.2 A, over the owned 3 A adapter. **Use the 12 V 5 A adapter** (64 % at peak). The 3 A one is for bench tests with the servos unplugged.
12. **O-ring belts** run at 7.4 % stretch. NBR relaxes over time; if a card slips, replace the belts.
13. **Card position under the camera.** The Y margin is only 4.2 mm worst case. Cards must stay in the 66.4 mm guide channel.
14. **Glare.** The LED strips must stay below 21 mm above the card or foils will show a hotspot. No GPIO switches them: they are on whenever the logic rail is.
15. **Hopper-empty detection** depends on the plate notch passing under the flag. Check it in §10 with an empty plate.
16. **Shoulder screws.** The ch2 pivots need 4 mm-shoulder screws with an M3 × 4 thread (5 and 6 mm shoulders). Order them early; they are not in common assortments.
17. **Relay at 3.3 V logic.** The 5 V relay module is driven from 3.3 V GPIO. Some boards never fully switch off at 3.3 V; bench-test it before wiring (§14.1).

---

## 20. Where the code and the CAD disagree

Re-checked against the repo on 12 Nov 2026. Every row of the earlier list that is not repeated below has been fixed in the code or the CAD. What is left is reported here, not fixed (this guide works round each).

| # | Where | Disagreement | Workaround in this guide |
|---|---|---|---|
| 1 | `sorting_tray.scad` header | Still describes the v1 routing, a "reject = small tray at end of lower floor", and slot names that differ from `config/rules.json` (bin 4 Legendary/Epic, 5 Rare, 6 Common/Basic, 7 Default). | Bins follow `rules.json`; the reject bin is `reject_bin.scad`. |
| 2 | `assembly.scad` header | Gives the electronics tray as X −150..35, Y 80..205; the tray is now 185 × 150, Y 80..230 (the module itself is right). | §1, §5 |
| 3 | `baseplate_tile.scad` header | Says machine X ≡ 15 (mod 30) from −270 to 270. The X grid restarts on each tile column (−270..−120, −80..70, 110..260); only Y is continuous. `electronics_tray.scad` and `shuttle_check.py` use the correct grid. | §4 |
| 4 | `riser.scad` header | Lists back X +40 as a through-bolt foot; the code (`feet_insert`) and `conveyor_rail.scad` make it an insert foot (M3 × 10). | §7 follows the code. |
| 5 <!-- PENDING CAD round 3: captions being corrected --> | `assembly-steps.yaml` captions, `cad/render_v2/parts.scad` | Video captions still say tiles "screw to backing board, M3 x 8", boards "on M2.5 standoffs" and riser "M3 x 80 through"; `parts.scad` draws the boards at their old tray positions. | Follow this guide, not the video captions. |
| 6 | `scripts/test_hardware.py` | The menu is now 1–11 (vent valve inserted as 3), but the test banners still say "Test 2b", "Test 3" … "Test 10". `hardware/card_detect.py` refers to the centring test as "test 9" (menu 10). | This guide uses menu numbers (§15.2). |
| 7 | `hardware/vacuum.py` docstring | Points to "docs/ASSEMBLY.md §3d, audit B-14" for the pull-ups; they are in §14.2. | — |
| 8 | `hardware/conveyor.py` docstring | Says pigpio PWM; it uses RPi.GPIO software PWM. | — |
| 9 | `web/app.py` docstring | Gives `http://raspberrypi.local:5000`; the hostname is `riftbound-sorter`. | §15.3 |
| 10 | `main.py` CLI vs web UI | The web UI only resets bins while paused or stopped; `--empty-bin` / `--empty-all` don't check the machine state. | Only use them paused or stopped (§15.3). |
| 11 | Config locations | Most tunables moved to `config/machine.json`, but `ARM_ACTUATION_RANGE` (servos.py) and the elevator's `UP_DIRECTION` / `TRIP_EXTRA_STEPS` are still code constants, while ch2's range lives in `shuttle_calibration.json`. | §16 "Where each setting lives" |
| 12 | `shuttle.scad` BOM, ch1 coupler | Lists "metal round horn + 8 mm D-hub"; the coupler isn't modelled. This guide uses a 25T disc horn + 8 mm rigid flange coupling (4 × M3 × 8). | §13.4: check the hole circles match. |
| 13 | `camera_bracket.scad` | Estimates the ribbon at ≈ 420 mm; the `assembly.scad` route to the tray entry is ≈ 405 mm plus ≈ 30–45 mm to the Pi connector. | Test-fit (§14.5). |
| 14 | `assembly.scad` | The load-cell trailing loop and the vent valve + tee are not modelled. | §14.6, §14.7 |
