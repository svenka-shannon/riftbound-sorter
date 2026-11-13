# Riftbound Card Sorter: Build Guide (v2)

This guide covers the v2 machine from the Nov 2026 redesign, including the audit fixes of 12 Nov 2026, the third CAD / code round (release 2.2.0: goBILDA ch1 coupler, board tee-nuts, NC hopper switches, crash-safe outputs) and the fourth (release 2.3.0: tilt crank that really fits the sled, cup bellows clear of its guide screws, strict calibration-file validation, tools that mark the machine unclean):
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

A narrated, part-by-part video of steps 1–11 (§4–§14) in this guide's install order is [`docs/assembly-video-v3.mp4`](assembly-video-v3.mp4) (≈ 8 min; source `cad/render_v2/video.yaml`). This guide is the reference: where the video simplifies (bench sub-assemblies float beside their final place, wiring is drawn as rough routes), follow the text.

## Contents

1. [Before you start](#1-before-you-start)
2. [Print list and settings](#2-print-list-and-settings)
3. [Heat-set inserts](#3-heat-set-inserts)
4. [Step 1: baseplate, backing board and tee-nuts](#4-step-1-baseplate-backing-board-and-tee-nuts)
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
| Riser | X −165..85 (plus the ch2 front-ear lug to X 89), Y −113..80, Z 4..64 (the deck is the rail base) |
| Conveyor | Belt X −165..85. Rollers at X −140 / +60, rod axis Z 79. Card face (belt top) Z 90.9. Slide bed X −127..47. Rail top Z 99. |
| Scan station | Hood X −49..59. Lens axis X +5. Lens tip Z 190.9 (100 mm above the card). |
| Hopper elevator | Cavity centre X −215, Y 0. Footprint X −263.5..−166.5, Y −65.6..74. Rim Z 94.4. Cap top Z ≈ 135, motor top Z ≈ 154. |
| Pick arm | Servo axis X −154.7, Z 151.8. Tower foot X −188..−112, Y −173..−122. Pick at X −215, drop (card centre) at X −95. |
| Pump bracket | X −276..−200, Y −234..−186, Z 4..47 (saddle + cap X −264..−246, head cradle X −232..−200). Pump axis Y −210, Z 28; nozzles to X ≈ −183. |
| Vent valve | Clip X −186..−144, Y −264..−246, Z 4..37.7. Barbed tee in the tube at X −165, Y −210, Z 28. |
| Shuttle | Cradle X 92..169. Carriage rod at X 106, Z 24 (Y −160..240). Tilt shaft (8 mm REX) at X 105, Z 44 (Y −175.2..241.8). ch1 servo case face Y −185. Carriage centre travels Y −102..176 (columns −102 / −35 / 35 / 102, home 0, reject 176). |
| Sorting tray | X 178..276, Y −137..137, open back face at X 178 |
| Lower ramp | X 136..178, in front of the tray's lower floor |
| Reject bin | X 159..274, Y 138..214 (beside the tray, at the shuttle's reject Y 176) |

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
- Hex keys 1.5–3 mm:
  - a **long-arm 2.5 mm** key for the riser anchors (54 mm deep wells);
  - a **1.5 mm L-key** for the ch2 ear screws (driven from below, short arm up) and the shuttle rod set screws;
  - a **2.5 mm ball-end** key for the one end-post anchor under the rod (§13.6);
  - a **3 mm** key for the ch1 coupler's M4 clamp screw;
  - a 2.5 mm hex driver for the ch1 ear screws.
- Small Phillips screwdriver (self-tapping screws).
- Calipers.
- Drill with Ø3.4, **Ø4.5** (tee-nut holes, §4) and Ø8.0 bits; Ø3.0 and Ø4.0 bits for reaming by hand (§2).
- Hacksaw or Dremel cut-off disc for the 4 mm rod, the 8 × 6 tube and the **REX shaft (cut to 417 mm)**.
- Fine file.
- Utility knife.
- Small mallet or hammer (tile keys, tee-nuts).

There is **no multimeter** in this build, which is why all three regulators are fixed-output modules. Never substitute an adjustable buck without a meter (BOM.md → Optional cost-down lists safe fixed-output alternatives).

---

## 2. Print list and settings

The full list is the **Printed parts** table in `BOM.md`: part, quantity, material, file/selector, orientation and supports. Summary:
- **PLA:** baseplate tiles and keys, electronics tray, riser, rails, rollers, slide bed, camera bracket, hopper, sorting tray, cradle, R-bars, lower ramp, reject bin.
- **PETG:** arm (all parts), card guides and clips, tilt frame, shuttle sled and cheeks, tilt crank and link, ch2 crank and link, end posts, pump bracket and vent-valve clip. Motor mounts can be PETG or PLA.
- **Black:** scanner hood (PLA or PETG). Make the card guides black too if you can.
- **TPU 95A:** the pump sleeve and the pump-head pad, if you can print TPU. Otherwise wrap the pump can in a neoprene strip and cut the 30 × 40 head pad from the same strip (§14.6).

| Setting | Value |
|---|---|
| Layer | 0.2 mm. Exceptions: cradle 0.12 mm (iron the top), lower ramp 0.16 mm, riser 0.24 mm. |
| Walls | 3–4 (5 for arm crank, links and ch2 crank) |
| Infill | 15–40 % per part (BOM table). Crank hub, tilt crank and tilt link 100 %. |
| Supports | **None, for every part.** The only support in the build is the break-away ladder that is part of the `end_post_neg` export (below). |
| Bed adhesion | **Brim** on the cradle and the scanner hood (below). |
| Bed | All parts fit 256 × 256 mm (Bambu P1S). |

Notes:
- **Export:** `openscad --backend=manifold -o part.stl -D 'part="cradle"' cad/shuttle.scad`. The `sorting_tray.scad` sections and the rollers are picked by editing the last lines of the file or with a wrapper `use <…>` file.
- **Baseplate:** 9 × `part="tile"` and one plate of 24 keys, `part="keys"`.
- **Cradle:** it prints bed-top up with every rib standing on one flat plane, but that plane is only ≈ 600 mm². **Use a brim.**
- **Scanner hood: brim required.** It is 101 mm tall and grows outward from a 26 × 26 roof (only 451 mm² on the bed) to a 108 × 103 top. Use an 8–10 mm outer brim (or 4 Ø15 mouse ears at the roof corners), a clean PEI or textured plate (glue stick for PETG) and outer walls ≤ 60 mm/s; otherwise it lifts or is knocked off near the top (`scanner_hood.scad`).
- **Tilt frame:** no supports. Printed upright (crossbar down), the crossbar, the plate bottoms and the skid-nub tangents are one flat plane at Z 63.8 (≈ 1420 mm² on the bed); the window tops are 12 mm bridges, the link slot (open below) has a flat bridged ceiling and then a 45° one, and the remaining edges are 45°.
- **Shuttle carriage:** it is three prints, the `sled` (on its +y face, no supports: the crank pocket closes with 45° roofs, with at most 0.5 mm ledges at their edges) and two `cheek_neg` / `cheek_pos` (flat on the outer face). **`part="carriage"` stops the export with an error**: export `sled`, `cheek_neg` and `cheek_pos`. (`part="carriage_preview"` shows the assembled carriage; it is not a print.)
- **End post −Y (`end_post_neg`):** the export includes a separate **break-away support ladder** (0.8 mm walls, 4 cells) standing on the bed under the ch2 rear-ear ledge (X 70.5..89.5, Y −161.5..−155.5, 0.2 mm below the ledge). Nothing printable can reach that ledge from the part itself (the ch2 crank sweeps below it), so leave the ladder in the print and snap it out with pliers afterwards. Everything else on the part is support-free (the rod set-screw boss on the +X face has a 45° underside).
- **Lower ramp:** prints **upright as modelled** (base on the bed). The 4 mm top bar is a 53 mm bridge: bridge fan 100 %.
- **Arm XY scale test:** before the arm head and hand, print a 50 mm XY scale test. The two plates only need to carry the *same* pivot pattern (`suction_arm.scad`), so print both links in one job.
- **Suggested print order** (long prints first): 9 tiles + keys; riser A/B; tray sections; hopper body; arm tower; everything else.

**Post-processing:**
- **Rails:** none needed. The 608 pockets are Ø22.15 press fits; tune ±0.05 if they print tight or loose.
- **Rollers:** ream the bore with an 8 mm drill bit, keeping the D-flat.
- **End post −Y:** snap out the support ladder; check the ch2 rear-ear ledge underside is clean.
- **Shuttle sled:** ream the tilt-shaft bushings to Ø8.3 and the ch2 drive-pin journal to Ø4.0+ (slip fit on the 4 mm shoulder).
- **Tilt crank:** its bore is the REX profile + 0.15 (Ø8.15 round ∩ 7.15 mm hex). Check it slides freely along the REX shaft with no rotational play.
- **Tilt frame:** ream the F-pin holes to Ø3.9 and the pin-A bore to Ø2.95 (turn a Ø3.0 bit by hand, lightly: the Ø3 dowel must stay a firm fit).
- **ch2 crank:** check the tip journal (Ø4.1) turns freely on the 4 mm shoulder.
- **Lower ramp:** sand the lanes with 600 grit.
- **R-bar:** sand the top.
- **Cradle:** cover the bed and kick with PTFE tape (§13.1).

---

## 3. Heat-set inserts

Fit **all 50 M3 inserts before any part is assembled**. Use M3 brass inserts for a Ø4.0–4.2 mm hole, 5.7 mm long (Ruthex / CNC Kitchen type). The ch2 link also takes **2 short M3 × 4 inserts** (OD ≤ 4.6 mm), listed at the end of the table. The baseplate's **tee-nuts** are not inserts; they go into the backing board (§4).

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
| Riser B | 2 | internal front wall behind the tie-tab recess, X −30.5, Z 37 and 56; Ø4.0 × 5.7 (Y −109.8..−104.1, Ø3.2 relief beyond), pressed in along +Y from the front face | front tie, M3 × 10 countersunk |
| Hopper body | 4 | tower walls under the cap, local (±44.5, 41) and (±44.5, 64.5), Ø4.0 × 6.1 | cap, M3 × 10 |
| Hopper cap | 2 | motor-ear bosses on the underside, 35 mm apart | 28BYJ-48 ears, M3 × 8 |
| Hopper carriage | 2 | **carriage bottom**, local (±8, 48.5), pressed in from below, flush with the bottom face | T8 nut flange, M3 × 14 (from the top pocket) |
| Hopper carriage | 2 | shelf, local (±9, 26.5), through 7 mm | floor plate, M3 × 10 countersunk |
| Arm head | 4 | back face of the ground plate, servo tab pattern 10 × 49.5 (Ø4.1 × 6.2; the shared MG996R pattern, §11) | MG996R tabs, **M3 × 8** (an M3 × 10 bottoms out) |
| Arm tower | 4 | column top, (±5, Y −134/−126) relative to the servo axis | head, M3 × 12 |
| Arm hand | 2 | beam tops at X ±14.5 (horizontal when printed) | guide screws, M3 × 40 |
| Shuttle cradle | 2 | boss underside, on the load-cell free end (Y ±3) | M3 × 10 through the cell |
| Shuttle sled | 6 | 3 in each side face at (X, Z) (112.5, 39), (97, 50), (114.5, 16.5); Ø4.0 × 6.5 | cheeks, M3 × 10 countersunk |
| R-bar −Y (`rbar_neg`) | 2 | lap splice at X 99.5, Y ±10, from the split face (Z 64.5) down; Ø4.0 × 8 | splice, M3 × 10 |
| End post −Y, ch1 cage | 4 | the cage's **−Y face** (Y −193.1), at X 100 / 110, Z 29.4 / 78.9; Ø4.0 × 6.9, Ø3.2 relief beyond | ch1 MG996R ears, M3 × 10 SHCS + washer |
| End post −Y and +Y | 1 each = 2 | the face of the 2 mm **boss on the post's +X face** (boss face X 118, insert X 118 → 112.3, 2.3 mm of plastic left to the rod bore), on the rod centre line (Z 24) at Y −155 and Y 237; Ø4.0 × 5.7, Ø3.2 on into the rod bore | rod set screw, **M3 × 8** flat point |
| Pump bracket base | 2 | saddle ears at Y −189.5 and −230.5 (pump axis ± 20.5) | cap, M3 × 10 |
| **Total (M3 × 5.7)** | **50** | | |
| ch2 link (short M3 × 4) | 2 | Ø4.0 through at both ends, pressed **flush from the top** | ch2 shoulder screws |

Everything else is either a clearance hole (Ø3.2–3.6, into a tee-nut or a nut) or a deliberate self-tapping pilot:
- Ø2.5: sorting-tray stacking (M3 × 12 countersunk).
- Ø2.6: arm guide-screw tails.
- Ø2.9: cheek dowels in the sled (press fit); pin-A bore in the tilt frame.
- Ø2.15: electronics-tray M2.5 posts and corner blocks.
- Ø2.2: M2 hopper-switch holes (clearance, with nuts); ch2 crank → horn M2 countersunk (clearance: the self-tappers thread only into the horn disc and pull the crank tight onto it).
- Ø2.1: ch2 servo-ear pilots for the M2.5 × 10 button heads (riser B's ear block and lug; the −Y end post's shelf, through its two Ø6 bosses). The ch1 ears no longer use pilots: they go into the 4 cage inserts above.
- Ø1.8: camera M2.
- Ø1.7: Pololu M2 posts.

**Never press an insert into a clearance hole.**

---

## 4. Step 1: baseplate, backing board and tee-nuts

Parts: 9 tiles; 24 bow-tie keys; a 6 mm plywood/MDF board at least 570 × 540; **49 M3 four-prong tee-nuts** (zinc steel, barrel Ø4.5 × 5, flange Ø13 × 0.9, e.g. FastenRight FF01 M3); 8 rubber feet **at least 10 mm tall**. Optional tile clamps: 18 × M3 × 16 + 18 more tee-nuts.

**Why tee-nuts.** Every part bolts down through a tile into the board. With a tee-nut hammered into the board from below at every hole a part uses, every baseplate screw is driven **from above** and nothing ever has to be reached under the loaded board. This is done **once, before anything is assembled** (`baseplate_tile.scad` BOARD FASTENING). Threaded inserts for wood are not used: M3 ones are 8–10 mm long (longer than the board) and hold only by their thread in MDF, which strips; a tee-nut's flange bears on the board underside, so tightening the screw pulls it *into* the board.

1. **Lay the tiles** on the board in a 3 × 3 grid, all the same way round, with no gaps: 570 × 540 mm, tile corners at X −285/−95/95/285 and Y −270/−90/90/270. Every tile edge has 2 dovetail half-pockets; on every seam two of them face each other and form one bow-tie pocket. **Number the tiles** (pencil on the underside) so each goes back in the same place in step 6.
2. **Keys.** Press a key into every seam pocket (24 in all; 12 interior seams × 2), from above, with a light mallet tap. A seated key sits 0.1 mm below the tile top, so parts bolted across a seam still sit flat. The keys lock the seams in X and Y and pull the tiles together; the board keeps them flush vertically.
3. **The grid.** Each tile has Ø3.4 holes every 30 mm, starting 15 mm in from its edges (6 × 6 per tile), each with a Ø5.2 × 1.5 counterbore on the underside for a tee-nut barrel. Because a tile is 190 wide, **the X grid restarts on each tile column**: X −270..−120, −80..70 and 110..260 (6 holes each, 30 apart). Y runs continuously: Y = −255 + 30 j, from −255 to 255.
4. **Drill the board through the tiles.** Clamp or tape the keyed tiles to the board and use them as the template: drill **Ø3.4 straight down through the tile hole and the whole board** at every hole in the table below (49 in all). Only these holes; nothing else is drilled through a tile.

| Step | Machine X, Y | Holes |
|---|---|---|
| Electronics tray (§5) | (−120, 105), (−50, 105), (−120, 195), (10, 195) | 4 |
| Riser anchors (§6) | (−150, −105), (−150, 75), (−80, −15), (−20, 75), (−20, 45) | 5 |
| Rail through-feet (§7) | (−80, −75), (−120, 75), (−80, 75), (10, 75) | 4 |
| Hopper (§10) | X −240 / −180, Y ±15 | 4 |
| Arm tower (§11) | X −180 / −120, Y −165 / −135 | 4 |
| Sorting tray (§12) | X 200 / 260, Y −105 / −45 / 45 / 105 | 8 |
| Shuttle end post −Y (§13) | (110, −225), (140, −195), (140, −165) | 3 |
| Shuttle end post +Y (§13) | (110, 225), (110, 255), (140, 255) | 3 |
| Lower ramp (§13) | X 140, Y ±45 / ±105 | 4 |
| Reject bin (§13) | X 200 / 230, Y 165 / 195 | 4 |
| Pump bracket (§14.6) | X −270 / −240, Y −225 / −195 | 4 |
| Vent-valve clip (§14.6) | (−180, −255), (−150, −255) | 2 |
| **Total** | | **49** |

5. **Tee-nuts.** Lift the tiles off and turn the board over. Open each of the 49 holes to **Ø4.5 from below**, about 5 mm deep (going all the way through is fine: the tile covers it). Tap an M3 tee-nut into each from below with a hammer, prongs into the board, until the flange is flush with the board underside. Its barrel stops ≈ 1 mm below the board top. Check each one: an M3 screw from the top side threads in by hand.
6. **Tiles back on.** Turn the board back over, lay the tiles back in their numbered places (key pockets up) and re-seat the 24 keys.
7. Optional: clamp each tile to the board with 2 × M3 × 16 at free grid holes (tile 4 + board 6 = 10 clamp). Drill and tee-nut those holes in steps 4–5 as well (18 more).
8. Stick 8 rubber feet (**≥ 10 mm tall**) under the board, clear of the tee-nut flanges. Screw tips end up to 7 mm below the board underside (the hopper base; most end 4–6 mm below).

**Check:**
- A straightedge across tile joints shows no step over 0.3 mm.
- Every key is flush or just below the tile tops.
- Every tee-nut is seated (flange flush) and takes a screw by hand.
- The board doesn't rock.

**Screw-length rule for every baseplate screw in this guide:** at least clamp length (part + tile 4 + board 6) + 4 mm, rounded up to a stock length. The tip then runs through all 5.9 mm of tee-nut thread and ends 4–7 mm below the board underside (7 mm: the hopper base's M3 × 20 countersunk). The electronics tray, sorting tray and reject bin take **M3 × 18** (clamp 12.5, tip 5.5 mm below the board); an M3 × 20 there also works but ends 7.5 mm below. Lengths below assume this 6 mm board. **Without tee-nuts** the same screws take a washer + nut under the board instead (every part file gives that as the fallback), but then every later bolt means lifting the loaded machine.

To save the 1.2 kg of tile filament, the board can be drilled from a printed template instead; see BOM.md → Optional cost-down, which also explains what that does to alignment.

---

## 5. Step 2: electronics tray

Parts: electronics tray; Pi Zero 2 W, PCA9685, 2-channel relay, ULN2003, three regulators, HX711, L9110S; barrel jack; Wago connectors; 3 × 1000 µF. Screws:
- 4 × M3 × 18 SHCS (tray → board tee-nuts).
- 16 × M2.5 × 6–8 self-tapping (Pi 4, PCA9685 4, relay 4, ULN2003 4).
- 6 × M2 × 5–6 self-tapping (Pololu regulators, 2 each).
- Foam tape (HX711, L9110S).

The tray has a mount for every board (`electronics_tray.scad`). Tray-local x = machine X + 150, y = machine Y − 80.

1. **Place the tray** at X −150..35, Y 80..230: its front face touches the riser's back face at Y 80. Its 4 mounting holes are real grid holes: machine (−120, 105), (−50, 105), (−120, 195), (10, 195). Fasten with **4 × M3 × 18** from above, head inside the tray, into the tee-nuts (floor 2.5 + tile 4 + board 6 = 12.5 clamp; the tip ends 5.5 mm below the board).
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
- 5 × M3 × 20: anchors (into the board tee-nuts).

1. **Joint.** Bolt A to B through the joint walls at X −40 with 3 × M3 × 12 + nut at (Y, Z) (−30, 40), (30, 30), (65, 30). Reach the heads and nuts from the open bottom.
2. **Front tie.** The joint's front is tunnel, so riser A's front skin carries on past the joint as a 16 × 3 tab (X −40..−24, Z 30..64) that sits flush in a recess in riser B's front face. Fit **2 × M3 × 10 countersunk** from the front into the riser B inserts at X −30.5, Z 37 and 56. The heads sit flush, clear of the harness at Z 45.
3. Set the riser on the baseplate at X −165..85, Y −113..80, deck up. The **open tunnel** under riser B (open below Z 26, closed by a 3 mm roof) is for the ch2 crank and link. It must stay empty: nothing taped or cabled in it.
4. **Anchors (do this now, before the conveyor; the slide bed later covers two wells):** fit 5 × M3 × 20 down the Ø6.8 wells from the deck top, at (−150, −105), (−150, 75), (−80, −15), (−20, 75), (−20, 45). The head sits on the 6 mm floor of the boss at Z 10; the screw goes into the tee-nut below (6 + tile 4 + board 6 = 16 clamp). Use the long-arm 2.5 mm hex key down the 54 mm well.

**Check:**
- The deck is flat. A straightedge along X shows no step at the X −40 joint.
- Deck height above the baseplate top is 60.0 ± 0.3 mm (deck Z 64).
- The ch2 servo's front-ear pocket in riser B's front face (X 69..86, Y −113..−105.8, Z 25..37) is clean, with the **solid ear block** above it (X 69..85, Y −113..−105, Z 37..64) and its 1 mm 45° lead-in along the front-bottom edge. The two Ø2.1 pilots at X 75 and 85, Y −109.4, go up into the block and the lug. The servo goes in at §13.6.

---

## 7. Step 4: rails and bearings

Parts: 4 rail halves, 4 × 608ZZ. Screws:
- 4 × M3 × 80 SHCS into the board tee-nuts (or 85 mm M3 threaded rod screwed into the tee-nut, washer + nut on top): through-feet.
- 2 × M3 × 10: insert feet X −50 front and X +40 back. The X −20 and +10 front feet wait for the camera bracket (§9).

The motor mounts are **not** fitted in this step. They go on at the end of §8, because each mount's flange covers its rod collar's set screw (`assembly-steps.yaml` step 5).

1. **Bearings.** Press one 608ZZ into each rail boss pocket (Ø22.15 × 7, open to the outside) with a vise, pushing **on the outer ring only**, until it seats on the 3 mm shoulder, flush with the boss face. Four bosses: one per rail half.
2. **Join the halves.** Push each tenon (5 × 3 × 12) into the next half's mortise. Back rail: `back1` + `back2`. Front (motor) rail: `front1` + `front2`.
3. **Place the rails** on the deck with the inner faces at Y ±45, the inlet end at X −165 and the bearing bosses facing out. The **front (−Y) rail** is the motor rail; its halves carry the insert pads.
4. **Feet** (8 total, `conveyor_rail.scad`):

| Rail | X | Y | Fastener |
|---|---|---|---|
| Front | −80 | −75 | through-bolt: M3 × 80 from the foot top through the riser (Ø3.6) into the tee-nut |
| Front | −50 | −75 | M3 × 10 into the riser insert |
| Front | −20, +10 | −75 | leave empty for now (camera bracket, §9) |
| Back | −120, −80, +10 | +75 | through-bolts, M3 × 80 |
| Back | +40 | +75 | M3 × 10 into the riser insert |

   Clamp stack for the through-feet: foot 4 + riser 60 + tile 4 + board 6 = 74, so an M3 × 80 runs through the whole tee-nut and pokes ≈ 5 mm out below it. With 85 mm threaded rod, screw the rod into the tee-nut first, then a washer + nut on top of the foot.
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
- 2 × 8 mm D-cut rods, 150 mm.
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

Parts:
- Hopper body, cap, carriage, floor plate, feeler flag.
- 2 × 8 × 150 rods, 2 × LM8UU.
- T8×8 lead screw 100 mm + brass nut.
- 5 → 8 coupling.
- 28BYJ-48 + ULN2003.
- 2 × SS-5GL2-F switches.

Screws:
- 4 × M3 × 20 countersunk (base → board tee-nuts; floor 3 + tile 4 + board 6 = 13 clamp, the tip ends 7 mm below the board).
- 4 × M3 × 10 (cap).
- 2 × M3 × 8 (motor ears).
- 2 × M3 × 14 SHCS (T8 nut flange → carriage-bottom inserts).
- 2 × M3 × 10 countersunk (plate).
- 1 × M3 × 20 + nylock (flag axle).
- 4 × M2 × 12 + nut (switches).

The hopper is modelled in a local frame. Local origin = cavity centre (machine X −215, Y 0); local Z 0 = baseplate top (machine Z 4).

**The cavity** is 91 × 66 (1.5 mm play round an 88 × 63 card), with r 1.2 vertical corner reliefs. From 1 mm below the top card's face (local Z 85.9, machine Z 89.9) up, the cavity **steps out**: 1.0 mm on the +X (belt-side) wall and 0.5 mm on the other three. This **lift relief** exists because the cup rises 2° off vertical and the card drifts +X as it is lifted; the step keeps a card that lies against any wall clear of it. The rim has a 0.8 mm × 45° chamfer.

1. **Base.** Set the body on the baseplate with the cavity centre at X −215, Y 0, the tower toward +Y and the finger slot toward −Y (front). Fit **4 × M3 × 20 countersunk** from inside the cavity, flush with the floor, at machine X −240 / −180, Y ±15, into the tee-nuts. Do this **before** the carriage and plate go in.
2. **Bottom (home) switch.** It goes on the tower floor against the back wall, body X −3.6..16.2 local, roller up. Fit **2 × M2 × 12 + nut** through the back-wall holes (Ø2.2).
3. **Rods.** Push the 8 × 150 rods into the Ø8.15 sockets (2.4 deep) at local X ±28, Y 48.5.
4. **Carriage.**
   - Press the 2 LM8UU in from the top onto the 1.5 mm lip.
   - **T8 nut, mounted flange-down.** Drop the brass nut into the Ø22.6 pocket in the carriage top **flange first, body pointing up**, flange holes on the X axis. The flange sits on the pocket floor and locates on the pocket's arcs; the body stands free in the pocket, its top flush with the carriage top. The carriage is only 21 mm deep in Y, so a square slot (|X| ≤ 7, pocket height) runs right through both ±Y faces where the pocket would break out: that is intended, not a misprint. Fit **2 × M3 × 14 SHCS** down through the flange (3.5) and the 12 mm under the pocket floor into the 2 inserts in the carriage bottom (≈ 4.2 mm engagement; the tips stop 1.5 mm above the bottom face). The lift load goes flange → pocket floor; the screws only stop the nut turning. (Why: a Ø10.8 bore with inserts at PCD 16 beside it left 0.6 mm of wall; `hopper.scad`.)
   - Thread the lead screw through the nut.
   - Slide the carriage down the rods with its shelf through the +Y wall slot into the cavity.
5. **Floor plate.** Lay it on the shelf: card face up, notch under the flag position (local X −30, −Y wall). Fit **2 × M3 × 10 countersunk** into the shelf inserts at local (±9, 26.5).
6. **Coupler.** Fit the 5 → 8 coupler onto the top of the lead screw.
7. **Cap.** Fit it over the rods (they stick **19.5 mm** out of the cap) with the coupler inside the Ø22.6 hole (1.8 mm radial play round the Ø19 coupler). Fasten with **4 × M3 × 10** into the tower inserts.
8. **Motor.** Mount the 28BYJ-48 **shaft down** on the cap, body offset 8 mm toward +Y. Fit **2 × M3 × 8** through the ears into the cap inserts. Push the shaft into the coupler's 5 mm bore and tighten both coupler set screws.
9. **Feeler flag.**
   - Fit the flag between the two cheeks on the −Y wall at local X −30.
   - Axle: **M3 × 20** through both cheeks (Ø3.4) + nylock, snug only.
   - **The flag must drop back onto its stop under its own weight** (≈1.2 g).
10. **Top switch.** Fit it on the +Y cheek with **2 × M2 × 12 + nut** in the slotted holes (±1.2 mm of adjustment along the actuation axis), roller under the flag's cam. Leave it mid-slot for now; it is set in §16.3.

**Check / measure:**
- **Plate travel:** turn the coupler by hand (motor unplugged).
  - The carriage runs smoothly over the full **71.6 mm** of plate travel: plate top Z 19.0..90.6 machine (local 15.0..86.6).
  - The home switch clicks with the carriage at the bottom (plate top local 15.3). The carriage lug that presses its roller has a single 45° ramp underside (it pushes the roller down along the lever, trip point 0.3 mm past the switch's operating point).
- **Top-of-stack trip:** with a stack of commons, lift the stack by hand until the top card is level with the belt top. The **top card should be 3.5 mm below the hopper rim** (rim Z 94.4, card Z 90.9). Lift the flag tip by hand and the top switch must click.
- **Empty plate:** an empty plate passes up under the flag through its notch without closing the switch. This is how "hopper empty" is detected.
- **Clearance to the belt:** the hopper's +X outer wall is at X −166.5 and the belt starts at X −165. The hopper must not touch the rail ends.

---

## 11. Step 8: pick arm

> **Test first (§19.1):** bench-test the MG996R you'll use on ch0 for ~170° of travel *before* printing or assembling the arm (`calibrate_servos.py --no-mock`, menu **`t`**, bare servo).

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
- 4 × M3 × 8 (servo tabs: an M3 × 10 would bottom out in the 6.2 mm insert hole).
- 4 × M3 × 6 (horn).
- 2 × M3 × 40 SHCS (guide screws).
- 4 × M3 × 12 (head → tower).
- 4 × M3 × 20 (tower → board tee-nuts: foot 6 + tile 4 + board 6 = 16 clamp).

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
2. **Servo.** Fit the MG996R into the head from behind, tabs on the plate's back face, with **4 × M3 × 8** into the tab inserts. **Measure your servo first:** every MG996R mount in the machine (arm head, ch1 cage, ch2 ears) uses one shared tab-hole pattern, 49.5 mm along the case × 10 mm across (`mg996r_hole_pitch` / `mg996r_hole_dx` in `cad/machine_frame.scad`). Clones vary (48.5–50 seen); the servo's own Ø4.5+ grommet holes still let an M3 land within about ±0.7 mm. If yours is further off, change it there and re-export the arm head, the −Y end post and riser B. The tab height is a typical value; shim under the tabs if your servo differs.
3. **Crank.** Power the servo at **ARM_PARK = 90°**:

   ```bash
   venv/bin/python scripts/calibrate_servos.py --no-mock   # menu 1
   ```

   or

   ```bash
   venv/bin/python -c "from hardware import servos; servos.init(); servos.arm_park()"
   ```

   Then fit the crank pointing **3° past vertical, toward the hopper (93°)**, not straight up. 93° is the crank angle at servo 90° in the CAD (`th_mid` in `cad/suction_arm.scad`): the middle of the pick (178°) to drop (8°) arc. A crank bolted vertical starts 3° off.
   - **Why it always fits within 1.8°.** The disc horn goes on the 25T spline in 14.4° steps, and the crank bolts to the horn in any of its **4 slot positions** (90° apart). Tooth and slot together give a **3.6° lattice**, so one combination always puts the crank within **±1.8° of 93°**. With the nearest tooth alone it can be 7.2° off. Then about a third of builds need PICK above 180° or DROP below 0°, and a servo with a few % more gain than nominal falls outside the calibration windows.
   - **Finding the combination.**
     1. Fit the horn, bolt the crank on with **4 × M3 × 6** in the slot that points it most nearly up, and measure its angle (below).
     2. If it is off by roughly a multiple of 14.4°, move the horn that many teeth (crank re-bolted in the slot that points it up).
     3. What is left is 0°, 3.6° or 7.2°. To move the crank **3.6°**, pull the horn, turn it **6 teeth the other way** (86.4°), and bolt the crank on **one slot further** in the wanted direction: 90° − 86.4° = 3.6°. For **7.2°**, turn the horn 12 teeth the other way and use the slot two positions round.
   - **Judging the angle** (target 93°; anything from 91.2° to 94.8° is right):
     - **Angle gauge (recommended):** a digital angle gauge or a phone inclinometer app. Zero it on the baseplate, then hold it against the crank's long straight edge. Target **3.0° from vertical, top leaning toward the hopper**; 1.2–4.8° is fine.
     - **Plumb line or square:** hang a thread with a nut on it in front of the spline centre (or stand a small square on the baseplate against it). The centre of the crank-tip bore (A', 60.3 mm out) should sit **3.2 mm toward the hopper** from that vertical; 1.3–5.0 mm is fine. One 3.6° step moves the tip 3.8 mm, so the right combination is obvious.
     - **Paper gauge (optional, nothing to print in CAD):** print or draw at 1:1 a cross for the spline centre, a vertical line, and a line 3° from it with ticks at ±1.8° about 60 mm out. Tape it to the head's front face with its vertical line on the plumb line or square.
   - A servo that turns the other way needs the same 93° fit (the arc is symmetric about servo 90°); swap ARM_PICK and ARM_DROP in calibration (§16.2).
   - The trim (slider compression at PICK, card height at DROP, and the servo's own gain) is set in calibration (§16.2).
4. **Links and hand.**
   - Put the sleeves on B and C, then link C (on C) and link B (on B).
   - Hand: press in the A' tube and the B'/C' dowels; fit the A' and C' sleeves.
   - Slide the hand on: A' into the crank, B' into link B, C' into link C. **It only goes on when all three links are parallel.**
   - Push a flat push-on washer onto every free pin end (≤ 0.5 mm thick; domed caps are too tall for the 1 mm gaps).
5. **Cup.**
   - Press the pad's 8 mm hex into the cup sled.
   - Fit the barb through the web into the pad (gasket).
   - Put the springs on the M3 × 40 guide screws (heads down), slide the cup sled on, and screw into the hand-beam inserts at X ±14.5. The guide-screw heads then sit 1.25 mm outside the Ø21 bellows pad, which rides up between them whenever the slider compresses (`cad/pick_arm_check.py` checks hand against sled).
6. **Tube.** Run it barb → loop → through the A' tube → free "spoke" (≈ 97 mm) → anchor bell on the servo axis → down the back of the column. Leave ~10 mm of slack in the hand loop.
7. **Tower and head.** Fit the head onto the tower with **4 × M3 × 12** into the column-top inserts. Bolt the tower foot to the baseplate at X −180 / −120, Y −165 / −135 with **4 × M3 × 20** into the tee-nuts.
8. **Zip ties.** The column has two tie tunnels 2.5 mm behind its back face at **Z 55 and Z 80**, open through both side faces (above the foot gussets, which end at Z 50). Thread a 100 mm tie in one side and out the other round the tube and the servo lead.

**Check / measure** (with `calibrate_servos.py` menu 1, §16.2):
- Servo axis at X −154.7, Z 151.8. Crank radius 60.3 mm.
- **PARK 90°:** crank at 93° (3° past vertical, toward the hopper), hand over X ≈ −158.
- **PICK ≈ 175°:** cup lip 3 mm **below** the top card (Z 87.9). The spring slider takes up the overtravel (10 mm stroke). The cup comes down within 2° of vertical.
- **DROP ≈ 5°:** card underside 3 mm above the belt (Z 93.9), card centre X −95, i.e. the card spans X −139..−51.
- During the lift a centred card clears the hopper by 1.5 mm, and a card lying 1.5 mm off-centre against any wall by ≥ 0.49 mm (`cad/pick_arm_check.py`). Watch the first lifts.
- **No link touches another** over the whole sweep (`cad/pick_arm_check.py` checks the CAD).

---

## 12. Step 9: sorting tray

Parts: sections A, B (lower), C, D (upper), 2 shelf halves. Screws:
- 8 × M3 × 18 countersunk (lower floor → board tee-nuts).
- 8 × M3 × 12 countersunk (stacking).

The tray spans **X 178..276, Y −137..137**. The **open back face of every slot is at X 178, facing the shuttle**, and nothing may block it. The label windows face +X.

1. **Join A + B.** A's Ø3 pin goes into B's Ø3.2 hole; fronts flush. A is at Y −137..0, B at Y 0..137.
2. **Fasten the lower floor (before the shelf).** Fit **8 × M3 × 18 countersunk** from inside the slots, down through the 2.5 floor + tile into the tee-nuts (clamp 12.5, the tip ends 5.5 mm below the board). Holes are at machine X **200 / 260**, Y **−105, −45, 45, 105**.
3. **Shelf.** Lay the 2 shelf halves on top, with the seam on the section seam.
4. **Upper floor.** Set C + D (joined by their pin) on the shelf. Fit **8 × M3 × 12 countersunk** from inside the upper slots' front corners: through floor 2.5 + shelf 3, self-tapping about 6.5 mm into the Ø2.5 pilots. Stop as soon as the heads seat.

**Check:**
- Slot centres are at Y −102, −35, 35, 102 (columns 0..3), with the same columns on both floors.
- Slots are 65 mm wide for a 63 mm card. The allowable carriage error is **≈ ±0.95 mm** (CAD audit); beyond that the card can strike a divider. §16.4 has the 20-dump test.
- Lower slot floor Z 6.5; upper slot floor Z 74.5.
- Bins (`hardware/shuttle.py`): 0–3 lower floor (column = bin), 4–7 upper floor (column = bin − 4), 9 = reject bin. What goes in each bin is set by `config/rules.json`, not by the tray.

---

## 13. Step 10: cradle shuttle, load cell, lower ramp, reject bin

Parts:
- Cradle, tilt frame (TF), **sled + 2 cheeks** (the carriage), tilt crank, tilt link, ch2 crank, ch2 link, R-bar −Y / +Y, end posts −Y / +Y.
- TAL221 load cell.
- 8 × 400 smooth rod (h6).
- **8 mm REX shaft** (round Ø8 ∩ 7 mm hex), goBILDA 2106-4008-4320 (432 mm, stainless), **cut to 417 mm**: hacksaw or cut-off disc, deburr, 0.5 mm chamfer on both ends. The E-clip is not used.
- 2 × LM8UU, 2 × 688ZZ.
- Dowel pins: 2 × Ø4 × 8 (F pins), 1 × Ø3 × 20 (pin A), 4 × Ø3 × 8 (cheek ↔ sled).
- 2 MG996R (ch1, ch2).
- **ch1 coupler: goBILDA 4001-0025-4008** clamping servo-to-shaft coupler (25T spline → 8 mm REX bore, aluminium, Ø13.8 × 17, M4 clamp screw included). **There is no horn on ch1.** Remove the rubber ear grommets from the ch1 servo.
- ch2: MG996R round 25T horn (from the servo bag), 2 shoulder screws (4 mm shoulder, M3 × 4 thread; one 5 mm and one 6 mm shoulder).
- PTFE tape; a dry PTFE lubricant (spray) for the REX shaft.
- 2 lower-ramp halves, reject bin.

Screws (`shuttle.scad` BOM):
- 2 × M3 × 12: TF crossbar → cell tapped end.
- 2 × M3 × 10: cell free end → cradle inserts.
- 6 × M3 × 10 countersunk: cheeks → sled inserts (3 per cheek).
- 1 × M3 × 16 + nylock: tilt crank ↔ tilt link (the only nylock in the shuttle).
- 2 × M3 × 10: R-bar splice (Y ±10).
- **2 × M3 × 8 flat-point set screws**: rod, one in each end post's +X-face boss insert.
- **1 × M3 × 6 SHCS**: goBILDA coupler → ch1 spline (driven down the REX bore).
- **4 × M3 × 10 SHCS + 4 washers**: ch1 ears → cage inserts (from behind the servo).
- **4 × M2.5 × 10 button-head hex socket (ISO 7380)**, self-threading: ch2 ears (2 into the end-post shelf, 2 into riser B's ear block / lug).
- 4 × M2 × 6 countersunk self-tapping: ch2 crank → horn disc.
- 1 × M3 × 12 countersunk: ch2 crank hub → servo spline.
- 6 × M3 × 20: end posts (3 each), into the tee-nuts.
- 4 × M3 × 20: ramp, into the tee-nuts.
- 4 × M3 × 18 countersunk: reject bin, into the tee-nuts.

There is **no set screw** on the tilt crank: it slides along the REX shaft with the carriage and is keyed by its hex bore.

**Install order.** The order below is the one `cad/shuttle_check.py assembly` verifies: it sweeps every part along its insertion path against what is already installed and gives every screw a tool path. Its step numbers (0–7) are given in brackets; do not reorder them. Step 0 (riser bolted down before the conveyor) was done in §6. §13.1 and §13.2 are bench sub-assemblies that come first.

### 13.1 Tilt frame, load cell, cradle (bench)

**Order matters:** the F pins are pressed in from **inside** the tilt frame, and once the cradle is on, its edge is only 0.8 mm from the side plate on the F axis. So the F pins go in first, before the load cell and the cradle.

1. **F pins (first).** Ream the TF's F-pin holes to Ø3.9 and the pin-A bore to Ø2.95 (§2). Press a **Ø4 × 8 dowel** into each side plate **from inside**, until its inner end is flush with the plate's inner face (|Y| 36). It then sticks 4 mm out past the plate's outside (to |Y| 44), where the cheek hooks will take it (§13.2).
2. **PTFE tape (required).** Cover the cradle bed and the 18° kick with **0.1 mm skived PTFE tape**, wrapping 2 mm over the lip. No bubbles or wrinkles; trim the edges with a knife. Bare PLA (μ ≈ 0.35–0.45) jams the upper-floor transfer (`shuttle_check.py slide`).
3. **Cell to TF.** Fit the TAL221's **tapped (cable) end** to the TF crossbar pad with **2 × M3 × 12** from below (counterbored holes). The cable goes toward the front notch in the crossbar.
4. **Cell to cradle.** Fit the cradle boss to the cell's **free end** with **2 × M3 × 10** from below through the cell's holes into the cradle inserts.
5. **Check:** the cradle touches nothing but the cell (0.8 mm to each TF plate). Press the cradle bed lightly and it must spring back. Cradle with tape is ≈ 19 g (target ≤ 35 g).

### 13.2 Carriage (sled + cheeks) and tilt crank (bench)

The carriage is three prints: the **sled** (rod and shaft bores, the tilt-crank pocket and the ch2 drive-pin arm, |y| ≤ 40.5) and two bolt-on **cheeks** (|y| 40.5..45.5) that carry the F-pin hooks. **Fit pin A before the cheeks:** the dowel goes in from outside the +Y TF plate, and the +Y cheek closes that path (`shuttle_check.py assembly`, pin-A path).

1. **Bearings and dowels.** Press an LM8UU into each end of the sled (Ø15.1 × 24.1 pockets; both bearings sit wholly in the sled). Press the 4 Ø3 × 8 dowels into the sled's side faces (Ø2.9, 2 per side).
2. **Tilt crank and link (before the tilt frame and the cheeks).** Join the tilt link to the crank tip with **M3 × 16 + nylock** on the bench (head on the crank side, nylock on the link side), snug so the joint pivots freely without play. With the LM8UUs already in the sled, hold the crank **pointing +X** (horizontal, the link hanging from its tip) and slide it **hub first along −X** into the open front channel of the sled's crank pocket, until its bore lines up with the sled's shaft bushings. The pocket is the crank's swept outline + 0.7 mm, so it only goes in this way; the crank arm's straight lower edge keeps it clear of the +Y LM8UU. It is captured there and will slide along the REX shaft (§13.4); leave it turned up toward HOLD (arm about 7° above +X).
3. **Tilt frame and pin A.** Hold the TF (with cell and cradle) in its level position over the sled, the link's free end in the TF's link slot. Push the **Ø3 × 20 dowel (pin A)** in along −Y from outside the +Y TF plate, through the Ø3.3 entry bore and the link, until it bottoms at Y 1.5 on the Ø2.9 → Ø2 shoulder. It is a firm fit in the Ø2.9 bore on both sides of the link. (To remove it later: cheek off, knock it out from −Y through the Ø2 hole.)
4. **Cheeks.** Offer each cheek onto its sled side so the F pin drops into the hook in the cheek's inner face and the 2 dowels enter the cheek's Ø3.1 holes. Fit **3 × M3 × 10 countersunk** per cheek into the sled inserts, heads flush with the outer face. The cheek root closes the LM8UU pocket mouth and retains the bearing.
5. **Load-cell lead.** Zip-tie it in the slot on the −Y cheek (X 150..154, Z 70). The rest of the route is in §14.7.

### 13.3 ch1 servo and coupler into the −Y end post (bench) [step 1]

1. **Inserts.** The 4 cage inserts (−Y face) and the rod set-screw insert (+X-face boss) are in (§3).
2. **ch1 direction check (bare servo, before the coupler).** Plug the servo into ch1 and run `venv/bin/python scripts/calibrate_servos.py --no-mock`, menu **`d`** (it is also offered before menus 2 and 3 until the shuttle has been homed). The servo goes straight to 80° and then ramps slowly to 100°. Increasing angle must turn the spline **clockwise looking straight at the spline face**: on the machine that is the crank arm rising from +X (toward the tray) up toward +Z. Answer the prompt; if it turned the other way the tool flips `"invert": {"1": …}` in `config/shuttle_calibration.json` (§16.4) and offers to re-check. Never fit the coupler to a servo that has not passed.
3. **Coupler indexing (at HOLD).** Power ch1 to **HOLD = 97°** (`calibrate_servos.py --no-mock`, menu 2, pose `hold`; ch2 may still be unplugged). Press the goBILDA coupler onto the spline at the tooth that puts **two flats of its hex bore 7° up from horizontal, rising toward +X** (φ_hold = 7°: the tilt crank's REX bore has its flats parallel to the crank arm, and at HOLD the arm points 7° above +X). One spline tooth is 14.4° and the hex repeats every 60°: together a 2.4° lattice, so one tooth lands within **1.2°**. Drive the **M3 × 6 SHCS** down the REX bore into the spline.
4. **Into the cage.** Unplug ch1, turn the coupler's clamp boss **up** by hand, and push servo + coupler nose-first along **+Y** through the cage opening from the −Y side. The servo sits **long side up** (body Z 33.8..74.5); its ears lie on the cage's −Y face. Fit **4 × M3 × 10 SHCS + washers** along +Y from **behind** the servo into the cage inserts (2.5 mm hex driver), at X 100 / 110, Z 29.4 / 78.9 (the shared 49.5 × 10 MG996R pattern: measure your servo, §11). The case face is at Y −185; the coupler sits in the open bay Y −184.2..−167.2 between the cage and the post.

### 13.4 Module on the bench: rod, carriage, shaft, R-bar [step 2]

1. Press a 688ZZ into each end post's inner-side pocket (Ø16.05).
2. **Rod:** through post −Y → carriage LM8UUs → 8 mm into post +Y. It sits Y −160..240 at X 106, Z 24.
3. **REX shaft, from the +Y end:** slide it along −Y through post +Y's 688ZZ → sled bushing → **tilt-crank hex bore** → sled bushing → post −Y's 688ZZ → **8 mm into the coupler's REX bore** (shaft Y −175.2..241.8, X 105, Z 44). Wipe the shaft with a **dry PTFE lubricant** first (no oil or grease: it collects dust). When the shaft reaches the crank, turn the crank a little (by the cradle) to line its hex bore up with the shaft.
4. **Clamp the coupler at HOLD.** Power ch1 to HOLD (97°) and set the cradle **10° nose-down**. Tighten the coupler's **M4 clamp screw from above** with a 3 mm key. Depending on which hex flat you indexed to, the clamp boss sits at 7°, −23° or 37° from horizontal-+X at HOLD; the screw head is up and reachable in all three (checked). The residual (≤ 1.2°) is trimmed in §16.4.
5. **Rod set screws.** Drive an **M3 × 8 flat-point set screw** through the insert in the 2 mm boss on each post's **+X face** onto the rod (along −X, 1.5 mm key from the open +X side; at Y −155 and Y 237, Z 24). The tip bears on the rod; the screw end sits flush with the boss face (X 118).
6. **R-bar.**
   - Join `rbar_neg` and `rbar_pos` at the 32 mm lap splice (Y −16..16) with **2 × M3 × 10** at Y ±10, down into the `rbar_neg` inserts. The heads sit 0.3 mm below the top; the skids land at Y ±1..4, clear of the counterbores.
   - Seat the ends in the end-post R-bar seats. The bar runs Y −150..232 at X 95..104.
   - The home notches at |Y| 29..45 must line up under the TF skids at home.
7. **Drag test** (§19.1). With ch1 at HOLD and the ch2 link not yet fitted, hook a spring scale on the carriage and pull it slowly along Y over its whole travel (Y −102..176). **Target ≤ 3 N** everywhere. More means the tilt crank binds in its pocket or on the shaft, the shaft is dry, or the rod and shaft aren't parallel: find it now, because ch2 has to overcome it at every move.

### 13.5 ch2 servo, horn, crank, onto the module (bench) [step 3]

The ch2 MG996R **hangs upside down** under the riser: output axis at X 80, Y −124, case face Z 26.3, spline down (`shuttle_geom.scad`). Under it, from the bottom up: link Z 9..14, crank Z 15..19 (and the carriage's drive-pin arm Z 15..20), shoulder-screw heads to Z 24, riser tunnel roof from Z 26. Nothing hangs below the link.

**How the case sits in the machine** (the reference for step 4). The case's long sides run along **Y**, symmetric about the spline (ear screws at X 75 / 85, spline at X 80). The spline is **10.2 mm from the case's +Y end** (the end toward the riser) and 30.5 mm from its −Y end (`sg_c2_body_y`). So with the servo standing **spline up** on the bench and its **spline end pointing away from you**: ψ 0 (+Y) points away from you, **ψ 90 (−X) points to your right, square to the long sides**, and ψ 180 (−Y) points toward you over the body.

**Why the crank is set by eye, not by a spline tooth.** The horn goes onto the 25T spline in 14.4° steps, so a horn and crank screwed together first and then pressed on can be up to **±7.2°** off. At reject (ψ 0, a dead centre) that alone moves the carriage up to ≈ 3.3 mm, against a reject box only 3 mm wider than the card. On a 180° servo the calibration tool can't trim past reject 2° or column 0 178° (column 0 sits at the other dead centre, so it moves only ≈ 0.3 mm). But the crank holds the horn disc only by **4 self-tappers cut into the plain plastic disc** (`c2_horn_holes` in `cad/shuttle.scad`: no matching holes or splines). So **the crank can sit at any angle on the disc**. Fit the horn to the spline first, hold the servo at **ψ 90**, line the crank up with the case, and only then drive the screws. Target: within **1°**, which is **2.4 mm at the tip journal** (139 mm out). ψ 90 is the middle of ch2's travel, so the servo's own gain error is split evenly between the reject and column-0 ends. It is also square to the case, which is easy to draw.

You need paper, a sharp pencil, a rule, a set square and calipers.

1. **ch2 direction check: before the crank goes on.** With nothing (or only the bare round horn) on the spline, plug the servo into ch2 and run `calibrate_servos.py --no-mock`, menu **`d`** for ch2 (80° → 100°, slowly). The firmware assumes servo angle = crank angle ψ: ψ 0 = crank pointing +Y (reject end), 90 = −X, 180 = −Y (column 0). **Increasing angle must turn the crank counter-clockwise seen from above** (clockwise looking straight at the spline, from below the upside-down servo; with the servo spline up on the bench, clockwise as you look down at it). If it turned the other way, **do not fit the crank**: the tool sets `"invert": {"2": true}` in `config/shuttle_calibration.json` (§16.4); re-run the check until it passes. A reversed servo without invert drives the crank into the end post. (MG996R clones differ.) With a DS3218MG-270 on ch2 (§19.1 item 1), set `"actuation_range": {"2": 270}` **before** this check. Everything below is then the same: the code adds its 45° centring offset at the pulse output, so you still command ψ 90 and fit there.
2. **Paper gauge.**
   - Measure your servo: **s** = spline centre to the case's spline-end face (calipers to the near and far sides of the spline, then average; ≈ 10.2 mm).
   - Tape a sheet of paper flat to the bench, with ≥ 160 mm free to its right. Stand the servo on it spline up, spline end away from you, and trace round its base.
   - Lift it off. Extend the outline's far edge (the spline-end face) ≥ 160 mm to the right with the rule. Draw a second line parallel to it, **s** toward you, over the whole length: the **ψ 90 line**. The spline centre and, at ψ 90, the crank's tip-journal centre both lie on it.
   - Put the servo back in its outline and keep it there: a strip of double-sided tape under the base, or a hand on it.
3. **Horn on, servo at ψ 90.**
   - Press the bare round horn onto the spline. Any tooth will do.
   - Unplug ch1, so the cradle on the bench module doesn't move. Run `calibrate_servos.py --no-mock`, menu **3**, and answer **N** to the direction-check offer (step 1 did it).
   - It homes (ch2 straight to home, 75.5°). Press `n` at **home** and at **column 0** (178°). At **column 1** (87.3°), jog **`+2.7`** (or `+` steps) until the readout shows **90.0°**.
   - Leave the tool at that prompt. **Do not save** (`s`).
4. **Crank on, lined up.**
   - Lay the crank on the horn disc, **countersunk face up** (its flat top face on the disc), pointing to your right along the ψ 90 line.
   - Start the **M3 × 12 countersunk** hub screw through the crank hub into the spline, only until its head just seats in the countersink. It centres the crank on the spline (the disc has no centring feature). The crank must still turn on the disc by hand: back the screw off a touch if it doesn't.
   - Turn the crank until, **looking straight down through the tip journal (Ø4.1)**, the ψ 90 line runs through the middle of the hole. A Ø4 drill bit dropped through the journal should touch the paper on the line. Aim for ≤ 1 mm: 2.4 mm is the 1° limit.
   - Check the case is still in its outline.
5. **Self-tappers, then the hub screw.**
   - Hold the crank tip on the line. Drive the **4 × M2 × 6 countersunk self-tapping** screws down through the crank's 4 holes (Ø2.2 clearance on Ø14) into the horn disc, heads flush. They thread only into the disc, so they pull the crank tight onto it. Drive them in diagonal pairs.
   - The screws cut their own thread in the disc. Their tips come ≈ 0.8 mm through it, beside the horn hub and 5 mm short of the case. They are driven from the crank's free face, so the horn on the spline is no obstacle.
   - Re-check through the journal after the first screw and again after all four.
   - If a crank hole lands over one of the disc's own holes (some round horns have a ring of them), that screw won't bite. If the crank has moved more than 1 mm at the tip, the next try needs fresh plastic. In either case: take the screws out, pull the horn, press it back on **one tooth round** and repeat from step 4. Only the crank's position on the paper matters, not the horn's.
   - Then **tighten the M3 × 12 hub screw** (≈ 4.9 mm into the spline), head flush with the crank bottom. It replaces the horn screw from the servo bag. This can only be done on the bench: once the servo hangs under the riser, the countersunk face points at the baseplate.
   - Press `q` in the tool. It parks (ch2 swings back to 75.5°, so keep hands clear of the crank) and goes limp. The crank angle is re-checked on the machine in §13.6 step 6.
6. **Park the crank** at ψ ≈ 100° (turn it by hand, servo unpowered): pointing −X, clear of where the riser will be.
7. **Hang it under the −Y end post's shelf.** Lift the servo straight up under the shelf, rear ear against the shelf. Fit the **2 rear-ear M2.5 × 10 button heads from below** (X 75 / 85, Y −158.9) through the shelf into its two Ø6 bosses (≈ 5.6 mm of thread). Use a **1.5 mm L-key, short arm up** into the socket, long arm swinging below. **Leave both one turn loose**: the servo hangs ≈ 0.5 mm low so the front ear can slide in at §13.6 step 2.

### 13.6 Module into place, ch2 front ear, anchors [steps 4–5]

1. **Park.** Slide the carriage by hand to **column 3 (Y ≈ 102)**, so its drive-pin arm is beyond the riser (Y > 80), and set the TF **level** (command ch1 to level, 93.1°, before you unplug it). The ch2 link is not fitted yet.
2. **Set the module down 10 mm toward −Y of its place, then slide it +Y** by 10 mm: the ch2 servo's front ear slides in under riser B's ear block through the 1 mm lead-in. The end posts land on their floor-plate holes (posts at Y −160..−150 and 232..242).
3. **Rear ear.** Tighten the 2 rear-ear screws: the servo comes up 0.5 mm onto both ceilings.
4. **Front ear.** Drive the **2 front-ear M2.5 × 10 button heads up from below, through the riser tunnel** (X 75 / 85, Y −109.4) into the Ø2.1 pilots in the ear block and lug: **1.5 mm L-key, short arm up** into the socket, long arm under the riser (≥ 195° of free swing, checked). Keep the crank parked at ψ ≈ 100°.
5. **End-post anchors: 6 × M3 × 20** into the tee-nuts (plate 4 + tile 4 + board 6 = 14 clamp): post −Y at (110, −225), (140, −195), (140, −165); post +Y at (110, 225), (110, 255), (140, 255). Five go straight down with a 2.5 mm key. **The one at (110, 225) is under the rod: use a 2.5 mm ball-end key tilted 45° toward +X.**
6. **ch2 square check (crank at ψ 90 on the machine).**
   - The ear screws are M2.5 in the servo's Ø4.5+ tab holes, so the case can sit up to about **±2° twisted** about Z (±1 mm at each ear, 49.5 mm apart). That is as much as §13.5 step 4 took out, so check it now.
   - With ch1 still unplugged, run menu **3** again: `n` at home and column 0, then jog column 1 to **90.0°** (as in §13.5 step 3). The link isn't fitted, so only the crank moves.
   - The crank now points −X along the riser's front face (Y −113; at the tip that is riser A, and the face starts above the tunnel opening). Hold the calipers' jaws upright, one on that face and one on the **far (−Y) edge of the tip boss** (X ≈ −59). It should read **17 mm**: tip-journal centre at Y −124, boss Ø12. Each degree moves it 2.4 mm.
   - If it is more than ~2.5 mm out: press `q`, turn the crank by hand to ψ ≈ 100° and loosen all 4 ear screws half a turn. Twist the case the way the tip has to go, tighten the rear ear and then the front ear (steps 3–4), and re-check.
   - Press `q` when it is right. Don't save anything here: the columns are calibrated in §16.4.

### 13.7 ch2 link and pivots, lower ramp, reject bin [steps 6–7]

1. **ch2 link.** Its 2 short M3 × 4 inserts are pressed flush into its top (§3). The link lies under the crank and under the carriage's drive-pin arm.
2. **Crank-tip pivot.** Command ch2 to **column 0 (178°)**: the crank tip is then at X 80, Y −263, outside the riser and reachable from above. Drop the **5 mm-shoulder screw** in from above through the crank tip's Ø4.1 journal into the link's insert.
3. **Drive-pin pivot.** Command ch2 to **reject (2°)** and slide the carriage by hand to the reject position (Y ≈ 177): the link's other insert then lines up under the carriage's drive-pin journal. Drop the **6 mm-shoulder screw** in from above.
4. Command ch2 back to home (75.5°). The carriage must sit at Y 0 with the cradle centred on the belt.
5. **Lower ramp.** With the carriage at **column 3** (TF level), lower `ramp_neg` straight down onto the baseplate behind the tray's open back; then move the carriage to **column 0** and lower `ramp_pos`. Lane exit at X 178, entry X 160.4, Z 34.7. Fit **4 × M3 × 20** through the rear floor tabs at X 140, Y ±45 and ±105, into the tee-nuts. The dividers line up with the tray walls, and the 4 mm fins (X 174..178) rise to the top bar at Z 100..104.
6. **Reject bin.** With the carriage still at column 0, lower it into place at X 159..274, Y 138..214, beside the tray. Fit **4 × M3 × 18 countersunk** through the 2.5 mm box floor at X 200 / 230, Y 165 / 195, into the tee-nuts (clamp 12.5, the tip ends 5.5 mm below the board).

**Check / measure** (move the servos with `calibrate_servos.py`, never by hand on a powered servo):
- **LEVEL at home:**
  - Cradle bed **0.7 mm below the belt top** (Z 90.2). Check with a straightedge across the belt end and the bed.
  - Cradle rear edge X 92, 7 mm past the belt end.
  - The skids rest on the home ledges.
- **HOLD:**
  - Bed 10° nose-down.
  - The card's tail is above the rails, guide clips and guide tops, so the carriage may move.
- **Carriage travel:**
  - The carriage runs freely Y −102..176. LM8UUs don't bind and the tilt crank slides along the REX shaft (drag ≤ 3 N, §13.4 step 7).
  - The ch2 crank tip stays inside the baseplate (reaches Y −269 at column 0).
- **Lower pose:** the TF's skids land on the R-bar at every column, and the kick reaches the ramp entry (≈1 mm before it, 1.5 mm above).
- **ch1 coupler:** no play between spline, coupler and shaft; the clamp screw is tight.
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
- **Check the relay switches OFF with 3.3 V logic, and with IN at only ≈ 2.7 V (bench test, before wiring it in).** The module runs from 5 V, but the Pi drives IN at 3.3 V, and the pull-ups hold IN at 3.3 V for "off". **At power-on it is worse:** from reset until the firmware applies the boot pull-up (below), the SoC's own ≈ 50 kΩ pull-*down* fights the 10 kΩ pull-up, so IN sits at only ≈ 3.3 × 50 / 60 ≈ 2.7 V, and the relay must stay released at that level too. On a board where the input indicator LED is in series with the opto LED, 5 V − 3.3 V = 1.7 V isn't enough to light them, so 3.3 V reads as off. On a board without that series LED, 1.7 V can still half-light the opto and the relay may stay on. Test each channel:
  1. Module VCC to 5 V (Reg #1 or a 5 V bench supply), GND to GND. Nothing on IN1 / IN2.
  2. Jumper IN1 to GND: the relay must click and its indicator LED light.
  3. Move the jumper from GND to the Pi's 3.3 V pin (pin 1 or 17): the relay must click **off** and the LED go fully dark. Repeat a few times.
  4. Repeat for IN2.
  5. **The ≈ 2.7 V (boot) case, on the Pi.** Stop the service. Wire IN1 to GPIO 17 and IN2 to GPIO 27, each with its 10 kΩ pull-up to 3.3 V (§14.2), module VCC from Reg #1. Run `pinctrl set 17 ip pd` and `pinctrl set 27 ip pd` (input with the SoC pull-down on: the state at power-on). Both relays must stay **released** with the LEDs fully dark, and must stay so through a reboot. Then `pinctrl set 17 op dl` must click relay 1 on and `pinctrl set 17 op dh` off (same for 27); finish with `sudo python3 scripts/safe_outputs.py`.

  **Boot pull-up (`config.txt`).** `scripts/setup.sh` adds the line **`gpio=17,27=ip,pu`** to `/boot/firmware/config.txt` (§15.1). After the next reboot, the firmware switches GPIO 17 / 27 to inputs with the SoC's internal pull-*up* a few seconds after power-on, before Linux starts, so IN sits at ≈ 3.3 V (relay released) from then until the sorter drives the pins. It does **not** cover those first few seconds after power-on, so keep the ≈ 2.7 V test in step 5. Check after the reboot: `pinctrl get 17,27` must show `pu` on both lines. **Alternative:** fit **4.7 kΩ** pull-ups on GPIO 17 / 27 instead of the 10 kΩ ones: IN is then ≈ 3.3 × 50 / 54.7 ≈ 3.0 V even straight out of reset.

  If a channel stays on (or chatters) at 3.3 V or at ≈ 2.7 V, the module is not 3.3 V-compatible. If it has a **JD-VCC jumper**, remove the jumper, feed **VCC** (the opto side) from the Pi's 3.3 V and **JD-VCC** (the coils) from Reg #1's 5 V, keep GND common, and repeat the test. Otherwise use a relay module sold as 3.3 V-logic compatible.
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
| 12 | 32 | in, pull-up | top-of-stack switch: **C → GND (pin 34), NC → GPIO 12** | `elevator.py` | normally closed: released = LOW, pressed (or broken wire) = HIGH |
| 13 | 33 | in, pull-up | home (bottom) switch: **C → GND (pin 30), NC → GPIO 13** | `elevator.py` | as above |
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
- **Released pins float; kept pins stay driven.** The SoC's default pulls only apply from power-on until a program configures the pin. RPi.GPIO `cleanup()` (`conveyor.deinit()`, `vacuum.deinit()`, `elevator.deinit()`) returns a pin to an input with **no pull**. And by default the Raspberry Pi kernel keeps a GPIO **output driven at its last level** when the process holding it dies (`pinctrl_bcm2835.persist_gpio_outputs=1`), so a pump left ON would stay ON. Three layers make every exit safe:
  - `scripts/setup.sh` sets **`pinctrl_bcm2835.persist_gpio_outputs=0`** on the kernel command line (applies after a **reboot**): freed lines revert to inputs.
  - The external resistors then set the level: **10 kΩ pull-ups on GPIO 17 and 27** (pump off, vent valve closed) and **10 kΩ pull-downs on GPIO 23–26** (belt stopped). At power-on, `setup.sh`'s `config.txt` line `gpio=17,27=ip,pu` adds the SoC's own pull-up on GPIO 17 / 27 a few seconds in, so the relay inputs sit at ≈ 3.3 V instead of ≈ 2.7 V (§14.1).
  - The service's **`ExecStopPost`** runs `scripts/safe_outputs.py` as root after **any** exit (clean, crash, `kill -9`, watchdog): it drives GPIO 17 / 27 HIGH, GPIO 23–26 and 16–21 LOW (with `pinctrl`, or `raspi-gpio` on Bookworm), switches every PCA9685 channel fully off and puts the PCA9685 to sleep (§14.8).
- **Hopper switches are wired normally-closed (NC).** Each SS-5GL2-F has three tabs: C (common), NO and NC. Wire **C → GND and NC → the GPIO** (top switch → GPIO 12, home switch → GPIO 13), with the Pi's internal pull-ups; leave NO unconnected. Released, the contact is closed to GND and reads LOW; pressed, it opens and reads HIGH. A broken wire or unplugged switch then reads **pressed**, which is the safe reading:
  - top switch: "top card at pick height", so the floor stops rising and never drives the stack into the arm (the cycle then stops with "card never seen");
  - home switch: `home()` stops lowering at once, and after the back-off the switch must read released, so a broken wire fails homing ("bottom (home) switch still pressed …") instead of zeroing at the wrong height.
- **`TOP_SWITCH_NC` must be `true`** (`config/machine.json`, section `elevator`; the default). Normally-open wiring of the top switch is **refused** (exit 78): the first raise after homing has to be allowed the full travel, because the stack height is unknown, and with NO wiring a broken wire reads "never pressed", so that raise would push the whole stack into the arm. With NC a broken wire reads pressed and the floor doesn't rise at all.
- **`BOTTOM_SWITCH_NC`** (default `true`) may be set to `false` if you wired the home switch normally-open (C → GND, NO → GPIO 13): a broken NO wire there only makes homing time out, which is safe.
- **Every raise after the first one since homing is capped at `RAISE_CAP_MM`** (3 mm, ≈ 9 cards). If the top switch hasn't tripped within it:
  - and the floor is within `RAISE_CAP_MM` of its soft top limit, the hopper is **empty** (the last card went at a trip height a little below the CAD value);
  - anywhere lower, the machine stops with **"top switch not detected — check wiring"**.
- **Remaining risk:** a top switch that is *mechanically* stuck closed (contact never opens although the wire is intact) can't be detected on the first raise after homing: the floor then rises to its soft top limit. §19.1 has the check. `test_hardware.py` test 11 prints how each switch is configured.
- HX711 pins: **DOUT (DT) = GPIO 5, SCK (CLK) = GPIO 6** (`hardware/loadcell.py`).
- HX711 wiring to the cell: E+ red, E− black, A+ white, A− green (confirm with your cell).
- 28BYJ-48: its keyed 5-pin plug goes into the ULN2003 board.
- Relay: COM1 and COM2 to 12 V+, **NO1** to the pump, **NO2** to the vent valve. If power is lost the pump stops and the valve closes.

### 14.3 PCA9685 channels (I²C 0x40, 50 Hz, 500–2500 µs)

| Ch | Servo | Owner | Nominal angles (calibration overrides) |
|---|---|---|---|
| 0 | Pick arm (MG996R) | `hardware/servos.py` → `config/servo_calibration.json` | ARM_PICK 175, ARM_DROP 5, ARM_PARK 90 |
| 1 | Cradle tilt (MG996R → goBILDA coupler → 8 mm REX shaft) | `hardware/shuttle.py` → `config/shuttle_calibration.json` | level 93.1, hold 97.0, upper 112.2, lower 41.5 |
| 2 | Shuttle carriage (MG996R, slider-crank) | `hardware/shuttle.py` → `config/shuttle_calibration.json` | reject 2.0, col 3 45.0, col 2 65.2, home 75.5, col 1 87.3, col 0 178.0 |
| 3–15 | unused | | |

- All ch1 / ch2 angles are **geometric** (ch1 = 90° + crank angle φ, ch2 = crank angle ψ). A servo that turns the wrong way is handled by `"invert"` in `config/shuttle_calibration.json` (the direction check, §13.3 / §13.5), never by editing angles.
- **270° servos (DS3218MG-270, any channel).** The 0–180° geometric span is centred in the servo's travel: the code adds a **centring offset** of (270 − 180) / 2 = **45°** at the pulse output only, so geometric 0 / 90 / 180 are **833 / 1500 / 2167 µs** (not 500 / 1500 / 2500) and both ends keep 45° of travel spare. It follows from the actuation range; there is nothing to set. Every angle (files, tool readout, the table above) stays geometric, and 90° is 1500 µs on either servo, so a crank fitted at the commanded pose sits the same way.
- **Level is 93.1°**, 0.5° past the geometric 93.6° (toward the ledges: level and lower are the same ch1 direction) so the skids sit firmly on the home ledges. Keep that preload small: past the hard stop the servo stalls against the ledge while the cradle waits level. While the machine **idles at rest with no card in it** (paused at a card boundary, stopped, hopper empty) the sorter switches **only ch1 (tilt) off**, so it doesn't stall: the cradle just rests on the home ledges. **ch0 (arm at PARK) and ch2 (carriage at home) stay powered and hold their pose** while you work in the machine (refilling the hopper, emptying bins). Before the next move ch1 gets one write to re-assert LEVEL (a small snap back by whatever it sagged). With a card anywhere in the machine (bin-full pause, jam, card held on the cup) nothing is switched off.
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
- **Pump and vent-valve 12 V leads:** from the valve's coil end (Y −264) and the pump's rear terminals to X −280, along the front-left edge, joining the harness drop at X −277 (§14.6).
- **Load-cell lead:** §14.7.
- **Keep clear of:**
  - the ch2 crank and link sweep (Z ≤ 24 under and in front of riser B);
  - the arm sweep above the hopper and belt inlet;
  - the shuttle carriage path (X 90..170).

### 14.5 Camera ribbon (SC1130, 500 mm)

1. Run the ribbon from the camera connector out through the bracket's −Y plate slot, up the plate, over the gusset and arm top (Z 234).
2. Bring it down behind the hood and the back rail (Y 62), over the riser deck's back edge (Y 80, Z 84).
3. Drop it into the tray at X ≈ 5, Y ≈ 88 and fold it gently into the Pi's CSI connector, which **faces +X** at machine X ≈ 22, Y ≈ 100.

- The CAD route to the tray entry is 405 mm; the run inside the tray to the connector adds ≈ 46 mm, so **expect ≈ 450 mm on the 500 mm cable: only ≈ 50 mm of slack**. Mount the Pi with its CSI end toward +X (facing −X would need ≈ 480 mm) and add no detours.
- **Test-fit the ribbon before you tie anything down** (§19).
- Ribbons are fragile: no sharp creases, no pulling at the connectors.

### 14.6 Pump bracket, vacuum tube and vent valve

**Pump bracket** (`pump_bracket.scad`): base (saddle + head cradle), cap, sleeve, head pad, and a separate vent-valve clip. Screws: 4 × M3 × 20 (base → board tee-nuts); 2 × M3 × 10 (cap → base inserts); 2 × M3 × 20 (valve clip → board tee-nuts).

**Base before pump.** The X −240 bolts are only 1.2 mm outside the pump can's outline, so a hex key can't reach them with the pump in place. Bolt the base down first, then fit the pump. (To remove the base later, take the cap and pump off first.)

1. **Base.** Bolt the base to the grid holes (−270, −225), (−270, −195), (−240, −225), (−240, −195) with **4 × M3 × 20** into the tee-nuts (base 5 + tile 4 + board 6 = 15 clamp).
2. **Isolation.** Slide the printed TPU sleeve onto the pump's motor can. No TPU? Wrap the can in a **1.5 mm neoprene or EPDM strip, 18 mm wide**, instead. The clamp closes a 1.0 mm gap onto it, so the squeeze is set by the geometry, not by screw torque.
3. **Head pad.** Lay the 30 × 40 × 1.5 TPU pad (`part="pad"`, or cut from the same neoprene strip) in the head-cradle pocket (floor Z 7.5) at X −232..−200. The pump head (≈ 32 long, ≈ 60 g) rests on it instead of hanging 50 mm off the clamp; the two cheeks 1 mm off the head sides stop it rocking in Y. R385 heads vary: if the head doesn't touch the pad, shim the pad; it must not lift the can off the saddle.
4. **Pump.** Lay the pump in the saddle: axis along X (Y −210, Z 28), can X −268..−230, head toward +X on the pad, nozzles reaching X ≈ −183. Fit the cap and **2 × M3 × 10** into the base inserts.
5. Fit a **1N5819 (or 1N4007) flyback diode across the pump terminals**, at the pump: cathode (stripe) to pump +, anode to pump −. Twist the pump leads and keep them away from the I²C wires.

**Vent valve** (`hardware/vacuum.py`): a **12 V normally-closed** 2-way mini air solenoid valve (the CAD reference is a uxcell 12 V 0.2 A unit, 0–350 mmHg, Ø3 mm barbs, ≈ 15 × 14 × 34 incl. the axial barb, 11 cm leads out of the coil end). Energised = open to air. **Measure yours:** the CAD envelope is a reference, not a vendor drawing.

6. **Valve clip.** Bolt the clip to grid holes **(−180, −255), (−150, −255)** with **2 × M3 × 20** into the tee-nuts (plate 5 + tile 4 + board 6 = 15). It sits at X −186..−144, Y −264..−246, clear of the arm tower foot, the arm sweep, the hopper and the pump base.
7. Put a 14 × 16 strip of 1 mm foam tape on the clip floor (Z 19.5). Snap the valve down between the two lipped walls: lying along Y, **axial (line) barb toward +Y**, side barb **up** (that one is the vent, open to air), coil leads toward −Y. Its axis is then at Z 28, the vacuum-line height.
8. Wire the coil to relay **NO2** and GND, with a **1N5819 (or 1N4007) across the coil**, at the valve: cathode (stripe) to the + lead. Run the 12 V leads of the valve and the pump to X −280 along the front-left edge and join the harness drop at X −277 (§14.4).

**Vacuum tube** (`assembly.scad` `asm_vac_tube()`), about 0.45 m of 4 mm OD PU in total:
1. A short silicone sleeve and a reducing barb take the pump's **inlet** (suction side) nozzle down to the 4 mm tube.
2. **Tee.** 18 mm past the nozzle, cut the tube and fit a **1/8" (3.2 mm) barbed plastic tee** (≈ 22 × 11, Ø3 barbs) at X −165, Y −210, Z 28, run along X, branch pointing −Y. PU 4 × 2.5 is a tight push onto a Ø3 barb: warm the tube end. From the branch, a **20 mm piece of 2 × 4 mm silicone tube** goes to the valve's axial barb.
3. The main tube runs on from the tee along Y −205, then up the back of the arm column (X −147, Y −160) through the tie tunnels at Z 55 and 80.
4. It goes into the anchor bell on the servo axis (Y −152.5), then out as the free spoke to the A' tube, then through the loop to the cup barb (§11).

- Mini valves seal best one way round. If the cup leaks down with the pump running and the valve shut, swap the valve's two ports (atmosphere on the IN / P port, vacuum line on OUT).
- `release()` switches the pump off, opens the valve for `VENT_S` = 0.4 s, then closes it. `pump_on()` always closes the valve first. To run without a valve, set `VENT_PIN = None` in `hardware/vacuum.py`; the code then just waits 0.3 s for the cup to leak down.

**Check:** `test_hardware.py --no-mock`, test 3 (vent valve). Hold the cup on a card while the pump runs: at release you hear the valve click and the suction vanishes at once, not slowly.

### 14.7 Load-cell lead (trailing loop)

The cradle moves 278 mm in Y and tilts. `assembly.scad` `asm_cell_lead(yc)` models the route (drawn for one carriage position; the loop changes shape as the carriage moves). **Test-fit it** before you tie anything down.

1. Splice about 1 m of 4-core flexible silicone wire (26–28 AWG) to the TAL221 leads at the cradle. Solder and heat-shrink the joint.
2. The lead leaves the TF crossbar notch, is zip-tied at the −Y cheek's slot (§13.2), then runs down the −Y cheek's outer face (X ≈ 135) and onto the baseplate at X ≈ 128.
3. **Rolling loop:** a flat loop on the baseplate under the carriage. The moving run goes from the carriage toward −Y along X ≈ 128, bends, and the fixed run comes back toward +Y along X ≈ 122. That is ≈ 350 mm of loop. The bend sits at Y ≈ (yc − 177) / 2 for carriage Y = yc, never less than 6 mm behind the moving end.
4. **Fixed end at Y 205, on the +Y side.** From Y 205 the lead is fixed to the baseplate (tape or adhesive tie mounts). It runs −X along **Y 205** (clear of the ch2 link, which reaches Y 182) to the tray's +X wall (X ≈ 38), up that wall at Y 165, and in through the cable slot (Y 160–170, Z 40.5–46.5) to the HX711 (machine X −88..−53, Y 162..184).
5. **Column 0 needs more slack.** The 350 mm loop works for carriage Y ≥ −70 (columns 1–3, home, reject). At column 0 (Y −102) the loop needs ≈ 30 mm more slack and its bend comes to Y ≈ −155, 5 mm from the −Y end post. Add that slack and check it at column 0.

Keep it out of:
- the rod, LM8UU, REX shaft and tilt crank (X 98..118, Z 20..54);
- the R-bar top;
- the ch2 link (X ≈ 75..90, Z 9..14, swept up to Y 182);
- the lower-ramp tabs (X 136..160 at Y ±45, ±105);
- the +Y end post's tongue (X 104..122 from Y 219);
- the card path.

**Check:** run the shuttle through every column and reject (`test_hardware.py` test 5). The lead must never tighten, rub, or pass under the ch2 link, and the cradle must read the same empty weight at every column (test 6).

### 14.8 Safe state

What the hardware and the service guarantee on their own:

| Event | Pump / vent valve | Servos | Belt / elevator |
|---|---|---|---|
| 12 V pulled | pump **off** (relay NO opens); valve **closed** (normally closed) | limp. **The arm falls and drops any card.** Always stop the sorter before unplugging. | stop; the 28BYJ-48 gearbox holds the hopper floor |
| Boot, before the sorter starts | **off / closed**: the 10 kΩ pull-ups on GPIO 17 and 27 hold both relay inputs HIGH (≈ 2.7 V for the first seconds after power-on, ≈ 3.3 V once the firmware applies the `config.txt` pull-up, §14.1) | PCA9685 not yet driven: limp | the 10 kΩ pull-downs on GPIO 23–26 keep the L9110S off; the ULN2003 stays off |
| The sorter exits for **any** reason (clean stop, crash, `kill -9`, watchdog) | `ExecStopPost` → `safe_outputs.py` drives GPIO 17 / 27 HIGH: **off / closed**. After the reboot that applies `persist_gpio_outputs=0`, the freed pins also fall back to the pull-ups on their own. | `safe_outputs.py` switches every PCA9685 channel fully off and puts it to sleep: **limp** | GPIO 23–26 and 16–21 driven LOW: belt stopped, stepper coils off |
| Main loop hangs | systemd watchdog (`WatchdogSec=60`): no ping for 60 s → SIGABRT, then `ExecStopPost` as above, then a restart that comes up in `needs_confirm` | | |
| The sorter idles at rest with no card in the machine (paused at a card boundary, stopped, hopper empty) | off / closed | **only ch1 (tilt) switched off**: the cradle rests on the home ledges. ch0 (arm at PARK) and ch2 (carriage at home) stay powered and hold. One write re-asserts LEVEL before anything moves | stopped / coils off |
| A card the arm could not carry to the belt is held on the cup | pump **on**, for at most `CUP_HOLD_MAX_S` (600 s), then off: **the card drops** from wherever the arm stopped (see below) | arm **never parked**: powered and holding where the failed carry left it | stopped |

What the software does on a stop, in outline (details in §15.4 and in `main.py`):
- A **stop request** (web UI Stop, or the first SIGTERM / SIGINT / SIGHUP) finishes the card in progress first; a **second** signal stops at once.
- A card on the cup is never dropped mid-arc: it is released back onto the stack if the cup is still at the pick pose, otherwise carried to the drop pose and released onto the belt. A second signal during that carry waits until the card is down.
- **If the arm can't carry it to the belt** (3 tries), the card is held, but only for a while. The arm is **never parked** with a card on the cup: it stays where the failed carry left it, powered, and the pump keeps holding the card. The web UI says **"card held on cup — remove it by hand before stopping the service"**, with the seconds left and where the card will land. When `CUP_HOLD_MAX_S` (default 600 s) runs out, or the service stops, the pump lets go and **the card falls from that pose**. A service stop lets go of it *before* the arm goes limp, so it falls from the known pose, not from a sagging arm. Where it lands depends on the arm angle (measured from your calibrated PICK / DROP, so it holds for a mirrored servo too):
  - within **2°** of PICK: never held at all; it is released straight back onto the stack;
  - within **10°** of PICK: flat back onto the hopper stack (a fall of ≤ 7 mm);
  - within **40°** of DROP: flat onto the belt in the drop zone (card X −160…−51; a fall of 3 mm at DROP, ≤ 18 mm within 15°, ≤ 39 mm at 40°);
  - anywhere else, PARK included: across the hopper's +X rim / the belt inlet from 12–55 mm up. It lands tilted, may catch on the rail inlet or the feeler flag, and **may be bent**.

  **Remove the card by hand first**, then **Machine clear**.
- The pump is switched off and the line vented, the belt stopped, the arm parked (unless a card is still held on the cup, above), a tipped cradle brought back to HOLD.
- **Teardown leaves the shuttle carriage where it is**; it never homes on the way out. Then every servo channel is switched off and the PCA9685 sleeps: **the servos are limp where they stand** and may sag a little.
- Every stop is recorded in `data/machine_state.json` as **clean** (no card in the machine, pump off, arm parked, shuttle at home + level, cradle empty) or **unclean** (with the reason). After a clean stop the next start re-asserts the rest pose with **one write per servo** (a small snap back by whatever the limp servos sagged, never a sweep). After an unclean stop **nothing on ch0–ch2 is commanded** until you confirm the machine is clear (§15.4).

**Safe-state test** (pump hose off): boot the machine and watch the relay. Neither channel may click or light. After boot, `pinctrl get 17` and `pinctrl get 27` read `hi` (and show `pu`, from the `config.txt` line), and `pinctrl get 23-26` read `lo`. Repeat after `sudo systemctl stop riftbound-sorter`, and once after `sudo systemctl kill -s KILL riftbound-sorter` (with the pump running): the pump must stop within a second, by `ExecStopPost`.

---

## 15. Software setup and operation

### 15.1 Install

1. **Flash the SD card.** Use Raspberry Pi OS Lite 64-bit with Raspberry Pi Imager: **Bookworm or trixie** (the current release) both work. Enable SSH, set the user and Wi-Fi, and set the hostname to `riftbound-sorter`. The camera is auto-detected (`camera_auto_detect=1`); there is no `raspi-config` camera step.
2. **Clone and run setup:**

   ```bash
   git clone https://github.com/svenka-shannon/riftbound-sorter && cd riftbound-sorter
   bash scripts/setup.sh
   ```

   `scripts/setup.sh` is safe to re-run (every step is idempotent) and stops with the failing line if anything goes wrong. It does all of this:
   - Enables I²C, runs `apt-get update` and `upgrade`.
   - Installs the apt packages: `python3-pip python3-venv python3-picamera2 python3-libcamera python3-numpy python3-scipy python3-pywt python3-pil i2c-tools git libopenjp2-7 libtiff6 avahi-daemon`.
   - Makes sure **`pinctrl`** is installed (package `raspi-utils-core`, normally preinstalled; `raspi-gpio` is the Bookworm fallback). `safe_outputs.py` needs one of them.
   - Adds the **kernel parameter `pinctrl_bcm2835.persist_gpio_outputs=0`** to `cmdline.txt` (`scripts/cmdline_param.py`: `/boot/firmware/cmdline.txt`, or `/boot/cmdline.txt` on older images; keeps a `cmdline.txt.riftbound.bak` copy the first time). It stops the kernel keeping a GPIO output driven after the process dies (§14.2). **It takes effect after a reboot.**
   - Adds **`gpio=17,27=ip,pu`** to `config.txt` (`scripts/config_txt_line.py`: `/boot/firmware/config.txt`, or `/boot/config.txt` on older images; appended once under its own `[all]` section; keeps a `config.txt.riftbound.bak` copy the first time). The firmware then pulls the relay inputs up a few seconds after power-on (§14.1). **It takes effect after a reboot.**
   - Installs **`python3-rpi-lgpio`**, the drop-in that provides `import RPi.GPIO` on current Raspberry Pi OS (it replaces `python3-rpi.gpio`). If the archive doesn't have it, it falls back to `python3-rpi.gpio`.
   - Creates `venv/` **with `--system-site-packages`**, so the venv can import the apt-only camera, GPIO and numpy modules. An existing venv made without that flag is deleted and re-created.
   - Installs the Python packages from the **lock file**: `pip install --no-deps --require-hashes -r requirements.lock`. Every package is pinned to an exact version and sha256 hash, the same for Python 3.11 (Bookworm) and 3.13 (trixie). `--no-deps` means pip never replaces the apt numpy / Pillow / scipy / PyWavelets. `adafruit-blinka` is held below 10 (Blinka 10 needs libgpiod bindings that nothing installs). `requirements.txt` only lists the top-level ranges.
   - Checks that the venv imports `picamera2`, `libcamera`, `RPi.GPIO`, `numpy`, `PIL`, `imagehash`, `flask`, `board`, `busio`, `adafruit_pca9685` and `adafruit_motor.servo`, and validates `config/machine.json` if there is one (§16.6).
   - Runs `i2cdetect`, creates `cache/` and `data/` and gives `cache/`, `data/` and `config/` to your user (`chown -R`; this also repairs root-owned files left by a tool run with `sudo`, §15.2), sets the hostname.
   - Installs and enables the **systemd service** for this checkout and user (`scripts/riftbound-sorter.service`, below).
   - Runs `safe_outputs.py` once, so every output is safe right away.
   - Prints the **web UI token** at the very end (§15.3).

   Notes:
   - **HX711:** the gandalf15/HX711 library is **vendored** as `hardware/vendor/hx711.py` (BSD-3 licence alongside, one marked local fix). There is nothing to install. **Do not** pip-install a package called `hx711`: the PyPI package of that name is a different library with an incompatible API.
   - **trixie:** `libtiff5` and `libatlas-base-dev` no longer exist there; setup.sh uses `libtiff6` and the apt builds of numpy, scipy and Pillow, which also keeps them ABI-matched with picamera2.
3. **Reboot** (`sudo reboot`) to apply the kernel parameter and the `config.txt` line. The service starts by itself after the reboot and waits in `needs_confirm` (§15.4). Check `cat /proc/cmdline` contains `pinctrl_bcm2835.persist_gpio_outputs=0`, and `pinctrl get 17,27` shows `pu` on both lines.
4. **Check the venv:**

   ```bash
   venv/bin/python -c "import picamera2, board, busio, adafruit_pca9685; from hardware.vendor import hx711"
   ```

   If `picamera2` fails, the venv was made without system packages. Re-run `bash scripts/setup.sh`; it re-creates the venv.
5. **Check the hardware is seen:**
   - `sudo i2cdetect -y 1` shows `40` (PCA9685).
   - `rpicam-hello --list-cameras` (or `libcamera-hello`) shows `imx708`.
6. **Card database:** stop the service (`sudo systemctl stop riftbound-sorter`), then `venv/bin/python main.py --build-db` (needs internet). It exits with an error if too many cards could not be hashed (§15.5). If the Riftcodex API is down later, the sorter uses the cached card list; with neither, it stays up, shows the reason in the web UI and retries every 60 s.

**The systemd service** (`scripts/riftbound-sorter.service`, installed by setup.sh):
- `ExecStart` runs `venv/bin/python main.py` as your user, with the groups `gpio i2c video`.
- **`ExecStopPost=+/usr/bin/python3 …/scripts/safe_outputs.py`** runs as root after **every** exit (clean, crash, kill, watchdog). It uses only the standard library, so it works even if the venv or the config is broken (§14.8). `sudo python3 scripts/safe_outputs.py --dry-run` prints what it would do.
- **Watchdog:** `WatchdogSec=60`, `NotifyAccess=main`. The main loop pings systemd (`WATCHDOG=1`) at most once a second while it is healthy, including inside long waits and elevator moves. If the pings stop for 60 s, systemd aborts the process, `ExecStopPost` makes the outputs safe, and the restart comes up needing **Machine clear**.
- `Restart=on-failure` (10 s), but **`RestartPreventExitStatus=78`**: a bad config file exits with status 78 and is *not* restarted. The five files checked are `config/machine.json` (§16.6), `config/identify.json` (§16.8), `config/shuttle_calibration.json` (§16.4), `config/servo_calibration.json` (§16.2) and `config/bin_limits.json` (§16.7). A `data/` directory or `data/sorter.lock` the service user can't open (left root-owned by a `sudo` run, §15.2) also exits 78, so the service doesn't loop through restarts.
- `TimeoutStopSec=60`: the first SIGTERM finishes the current card; that fits well inside 60 s.
- Optional extra: the **hardware** watchdog covers a hung OS (not just a hung sorter): add `dtparam=watchdog=on` to `/boot/firmware/config.txt`, set `RuntimeWatchdogSec=15` in `/etc/systemd/system.conf`, reboot and check that `/dev/watchdog` exists.

### 15.2 Hardware tests

Stop the service first (`sudo systemctl stop riftbound-sorter`). `venv/bin/python scripts/test_hardware.py --no-mock` gives a menu (A runs them all, Q quits). Before anything moves it asks you to confirm the arm, belt and cradle are clear, because the arm then parks and the shuttle homes with direct (full-speed) moves.

**The hardware tools and the sorter exclude each other.** `test_hardware.py`, `calibrate_servos.py` and `calibrate_camera.py` take the sorter's lock (`data/sorter.lock`): a tool refuses to run while the sorter service or another tool runs, and the sorter refuses to start while a tool runs. Before anything moves, a tool records the machine as **not clean** in `data/machine_state.json` ("tool ran: …") and never marks it clean again, because it may have stopped with the carriage at a column, the cradle tipped or a card in the machine. So **after any tool run the next sorter start asks for Machine clear** (§15.4). `main.py --calibrate` (§16.1) counts as a tool here too: it records "tool ran: main.py --calibrate" the same way. **Any config error stops a tool with exit 78** before anything moves, exactly as it stops the sorter: an invalid `machine.json`, `servo_calibration.json` or `shuttle_calibration.json` (with the list of bad keys), an unreadable calibration file, or a lock / `data/` it can't open (below). All three tools and `main.py` use the same status.

**Never run the tools or `main.py` with `sudo`.** Run them as your own user (the one the service runs as, in the `gpio i2c video` groups). A tool or sorter started as root can leave a **root-owned `data/`, `data/sorter.lock` or `data/machine_state.json`**. The service then refuses to start with an error naming the file, e.g. "cannot open …/data/sorter.lock … Fix: sudo chown -R <user>: …/data", and exits 78, so systemd does not keep restarting it. Fix it with `sudo chown -R <user>: data` (your user name, from the checkout), or re-run `bash scripts/setup.sh`, which gives `cache/`, `data/` and `config/` back to your user. Only `safe_outputs.py` is meant to run as root.

| Menu | What it runs |
|---|---|
| 1 | pick arm (ch0): park / pick / drop |
| 2 | vacuum pump, 2 s |
| 3 | vent valve release (pump on, then pump off + vent pulse) |
| 4 | pick and place one card onto the belt |
| 5 | shuttle: every column, both floors, reject |
| 6 | cradle load cell (a diagnostic tare: never stored as the empty reference) |
| 7 | camera full frame + card crop |
| 8 | card detection, live offset (belt off) |
| 9 | conveyor run (3 s) + brake |
| 10 | belt centring (drop zone → lens) |
| 11 | hopper elevator: home, then raise to pick (also prints whether each switch is configured NC or NO) |

The banners now match the menu numbers ("Test 1" … "Test 11"). Off the Pi, `uv run scripts/test_hardware.py` runs the same menu in MOCK mode.

Always run hardware scripts with the **Pi venv python** (`venv/bin/python …`); a uv script environment has no GPIO, camera or PCA libraries. Off the Pi, `MOCK_HARDWARE=1 python main.py --dry-run` exercises the whole cycle, and `python -m pytest tests/` runs the mock test suite in `tests/`.

**First motion checks (before calibration):**
- **Elevator direction.** Put the plate mid-travel with no cards, run test 11 and watch the first second. If "home" moves the floor **up**, press Ctrl-C at once and set `"UP_DIRECTION": -1` in the `elevator` section of `config/machine.json` (§16.6).
- **Belt direction.** Run test 9. Both rollers must move the card toward +X. Swap a motor's two leads if one runs backward.
- **Servo directions.** ch1 and ch2 were checked bare in §13.3 / §13.5. If you swap a servo later, re-run `calibrate_servos.py` menu `d` with the new servo bare.

### 15.3 Web UI, token and states

The web UI runs at `http://riftbound-sorter.local:5000` (or `http://<pi-ip>:5000`; set `RIFTBOUND_WEB_PORT` to change the port).

- **Token.** Every action that changes something needs the web UI token. It is generated on first use and stored in **`config/web.json`** (mode 600, not in git). It is never written to the journal. Show it with:

  ```bash
  venv/bin/python main.py --web-token
  ```

  `setup.sh` prints it at the end. The browser asks for it the first time you press a protected button and remembers it. API clients send it as an `X-Auth-Token` header (or a `token` form field).
- **Read-only pages** (dashboard, inventory, exports, `/api/status`, `/api/bins`) need no token.

**Machine states** (shown on the dashboard):

| State | Meaning |
|---|---|
| `starting` | start-up checks running: belt stop, arm / shuttle to rest, elevator homing, cradle check. **The machine may move.** |
| `running` | sorting |
| `paused` | operator Pause, or a bin is full (card held on the cradle); nothing moves. Paused at a card boundary with no card in the machine, only ch1 (tilt) is switched off; the arm and carriage keep holding |
| `stopped` | operator Stop; the process and web UI stay up; only ch1 (tilt) switched off, the arm and carriage keep holding |
| `hopper_empty` | refill and press Resume |
| `needs_confirm` | first start, unclean stop (also after any hardware tool or `main.py --calibrate` ran), a card found on the cradle, a Stop while a card waited on the cradle for a full bin, or a **card held on the cup** ("card held on cup — remove it by hand before stopping the service"): check the machine, remove any card, then **Machine clear** |
| `jam`, `error` | something stopped the machine (camera fault, elevator switch fault, load-cell fault, hash DB incomplete, …); the message says what |
| `idle` | `--web-only` mode |

**Dashboard controls** (token needed). Every one is checked against the state; a refused request gets HTTP 409 with the reason.

| Button | API | Allowed when | What it does |
|---|---|---|---|
| Pause | `POST /api/pause` | `running`, `starting`, `paused` | finishes the card in progress, then waits (state `paused`) |
| Resume | `POST /api/resume` | `paused`, `stopped`, `hopper_empty`; or to cancel a pending Pause / Stop while `running` / `starting` | continues. Refused in `needs_confirm`, `jam`, `error`: use Machine clear. A Stop while a card waits on the cradle for a full bin ends in `needs_confirm`, not `stopped`, so Resume is refused there too: remove the card, then Machine clear |
| Stop | `POST /api/stop` | `running`, `starting`, `paused` | stops sorting at the next card boundary. The process and the web UI stay up; Resume starts again |
| Machine clear | `POST /api/confirm-clear` | `needs_confirm`, `jam`, `error`, `stopped`, and only once no run is in progress | you confirm the arm, belt and cradle are clear (any card removed). **Never while `paused` or `starting`**: a card may be held on the cradle mid-run. Same as `main.py --confirm-clear` |
| Empty (per bin) | `POST /api/bins/<n>/empty` | the bin the machine is paused on because it is full; or any bin in an idle state (`paused`, `stopped`, `jam`, `hopper_empty`, `error`, `idle`, `needs_confirm`) | resets the count after you emptied the bin. Never while `starting` or `running` (the shuttle may move) |
| Empty all | `POST /api/bins/empty-all` | idle states only | resets every count |
| Save (rules page) | `POST /rules` | any state | validates, saves and hot-reloads `config/rules.json` (applied between cards) |

- **Bin full:** the machine pauses with the card held on the cradle. Empty the bin and press its **Empty** button; the sorter resumes 2 s later (`RESUME_DELAY_S`, so your hands are out of the tray). **If you pressed Pause before or during that wait, emptying the bin is not enough:** the card is routed only after an explicit **Resume**. Nothing moves while it waits.
- **One sorter at a time.** A running sorter (main loop, `--web-only` or `--calibrate`) holds a lock on `data/sorter.lock`. A second `main.py` exits at once with "another sorter process is running". (`--build-db` doesn't take the lock, but stop the service before rebuilding anyway.)
- **The CLI goes through the web API.** With a sorter running, `main.py --empty-bin N`, `--empty-all` and `--confirm-clear` send the request to that sorter's own web API (`127.0.0.1`, with the token), so exactly the same state rules apply. If its web UI can't be reached they refuse ("use the web UI, or stop the service first"). With no sorter running nothing can move, and they write the counts / state file directly.

### 15.4 Starting and stopping

**Starting** (`sudo systemctl start riftbound-sorter`, or `venv/bin/python main.py`):
1. **Config.** `config/machine.json` and `config/identify.json` are validated first, then `config/bin_limits.json`, then `config/servo_calibration.json` and `config/shuttle_calibration.json` at hardware init. Any bad key stops the program with a list of every problem and **exit status 78**; systemd does not restart it. Nothing ever falls back to the defaults silently.
2. **Hardware init moves nothing.** Pump and belt are driven off at once. After a **clean** stop the arm's park angle and the shuttle's home + level are re-asserted with one write each: a small snap back by whatever the limp servos sagged, never a sweep; later moves ramp from there. After an **unclean** stop (or the first start) nothing on PCA9685 ch0–ch2 is commanded at all.
3. The **web UI** comes up, so problems are visible there. Then the card list is loaded (cache fallback) and the **hash DB is checked for completeness**: the sorter refuses to sort while more than `max_missing_fraction` (1 %) of the card list has no hash, because a missing card would be matched to its nearest look-alike. It shows `error` "hash DB incomplete: N of M cards missing — run `main.py --build-db`" and retries the missing downloads every 60 s. A `--dry-run` only warns.
4. The state becomes **`starting`**, and the machine is recorded as **not clean** before the start-up moves anything (arm, shuttle, elevator), so a kill or power cut during start-up never leaves an old "clean" record behind.
5. **First start, or any start after an unclean stop:** the sorter waits in **`needs_confirm`** with the reason (for example "no record of a previous clean shutdown (first start?)", "a card was left on the cradle", "arm / shuttle pose not known to be at rest"). Check the arm, belt and cradle, remove any card, then confirm with **Machine clear** in the web UI or:

   ```bash
   venv/bin/python main.py --confirm-clear
   ```

   Only then do the arm and shuttle move to their rest pose, as **direct full-speed jumps** (hobby servos have no position feedback). Keep hands clear.
6. Start-up then stops the belt, switches the pump off, homes the hopper elevator and **checks the cradle by weight** (next point).
7. **The cradle check runs at every start, confirmed or not** (a confirmation is not a measurement). Before it tares, it compares the cradle's raw reading with the stored empty-cradle reference (§16.1):
   - more than **0.8 g above** it: "card on cradle — remove it", back to `needs_confirm`. It never tares a card away.
   - more than 0.8 g **below** it: load-cell fault ("load cell fault or zero drift"): check the cell and lead, then re-run `main.py --calibrate`.
   - **no stored reference** (never calibrated, or an old calibration file): unconfirmed → `needs_confirm` ("run `main.py --calibrate`, or check the cradle is EMPTY and confirm"); confirmed → it tares on your word, prints a warning, and nothing is stored as a reference until you run `--calibrate`.

**Stopping:**
- **Web UI Stop or Pause:** finishes the current card; the process stays up.
- **`sudo systemctl stop riftbound-sorter`, Ctrl-C or SIGHUP:** the **first** signal finishes the card in progress, then shuts down. A **second** signal stops immediately; a card on the cup is put back on the stack or carried to the belt, never dropped mid-arc (a second signal *during* that carry waits until the card is down).
- **Teardown:** pump off and vented, belt stopped, arm parked (a card still held on the cup is let go first, from where the arm stands, see below), a tipped cradle brought back to HOLD. **The shuttle carriage stays where it is**; it never homes on the way out. Then every servo goes **limp** (channels off, PCA9685 asleep) and the service's `ExecStopPost` drives all outputs safe (§14.8).
- **Clean or not.** The stop is recorded as clean only with no card in the machine, the pump off, the arm parked and the shuttle at home + level with an empty cradle. A card still on the cradle (for example during a bin-full pause) stays there; the state becomes `needs_confirm` (Resume refused), the stop is recorded as unclean and the next start asks you to remove it.
- **Card held on the cup.** If the arm couldn't carry a card to the belt, the arm is left where it stopped (never parked), powered, and the pump holds the card for at most `CUP_HOLD_MAX_S` (600 s). The web UI says "card held on cup — remove it by hand before stopping the service", the time left, and where the card will land. When the time runs out, or the service stops (it lets go before the arm goes limp), the pump lets go and the card falls from that pose: within 10° of PICK back onto the stack, within 40° of DROP flat onto the belt, anywhere else (PARK included) across the hopper rim / belt inlet, possibly bent (§14.8). **Remove it by hand first**, then **Machine clear**.
- **Idle servos.** While the sorter waits at rest with no card in the machine (stopped, paused at a card boundary, hopper empty) **only ch1 (tilt)** is switched off, so it doesn't stall against the home ledges; ch0 (arm at PARK) and ch2 (carriage at home) keep holding while you work in the machine (§14.3). ch1 gets one write before the next move.
- Before unplugging the 12 V, always stop the service first.

### 15.5 Card database

`main.py --build-db` downloads the Riftcodex card list and images and builds the perceptual-hash DB (`data/hash_db.json`). It reports every card it could not hash and **exits with an error** if more than `max_missing_fraction` of the list is missing; run it again (the missing downloads are retried). Identification settings are in `config/identify.json` (§16.8).

---

## 16. Calibration (in this order)

Use **bulk commons** for every step. Jogging is done with `scripts/calibrate_servos.py`, which drives the servos through the same modules the sorter uses (ramped moves, HOLD interlock):

```bash
venv/bin/python scripts/calibrate_servos.py --no-mock             # menu: 1 arm, 2 tilt, 3 carriage, d direction check (ch1/ch2), t travel test (ch0/ch1/ch2), v verify, p print, q quit
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
- **Jogging is clamped to each pose's own sanity window**, the same per-pose limits the sorter checks the file against (§16.2, §16.4):
  - arm (ch0): **PICK 155–180, DROP 0–25, PARK 80–100**, or the mirror (180° − angle) for a servo that turns the other way (PICK 0–25, DROP 155–180). The PICK and DROP windows open **toward PARK only**: a servo that turns more than commanded (MG996R gain varies by ±10 %) needs less command at both ends;
  - tilt (ch1): **±8°** round the nominal pose; carriage (ch2): **±12°** (§14.3 table).
  - all clipped to what the servo can be commanded to: **0–180°** on a 180° servo (the carriage stops 2° inside: 2–178°), **−45–225°** on a 270° one (§14.3, centring offset). So on a DS3218MG-270 the arm's PICK can go to 185° and DROP to −5°, and the carriage's reject to −10° and column 0 to 190°, for a servo that turns a little less than commanded.

  If the jog reaches a window edge before the pose is right, the arm horn or the ch1 coupler is on the wrong spline tooth, or the ch2 crank is off its ψ 90 line: re-fit it (§11 step 3, §13.3, §13.5 steps 2–5).
- **The rules between poses are checked when you save (`s`)**, against the other poses as they stand:
  - arm: PICK and DROP on opposite sides of PARK, and **symmetric about it within 10°**: |(PICK − PARK) − (PARK − DROP)| ≤ 10°;
  - tilt: lower < level < hold < upper, with **hold − level 2–8°**, **upper − hold ≥ 8°**, **level − lower ≥ 30°**;
  - carriage: reject < 3 < 2 < home < 1 < 0, each stop **≥ 5°** from the next, and **column 2 − column 3 ≥ 12°**.

  A pose that is fine on its own but breaks one of these rules only because a pose **later in the same menu** still has its old value is **HELD**. The tool names the rule, and writes the held pose together with the first later save that makes the whole file valid. So a build whose every stop sits 7–8° off nominal (a crank half a tooth out) is calibrated in **one pass**. Anything still held at the end of the menu, or at `q`, is **not saved**, and the tool says so.
- **The tool never writes an invalid file.** A value outside its own window is refused with the reason, and the old value is kept. An invalid file at start stops the tool (exit 78) with the list of bad keys, before anything moves.
- **Interlock** (§15.2): the tool refuses to run while the sorter service runs, and records the machine as not clean before anything moves, so the next sorter start asks for **Machine clear**.
- Saved values go to `config/servo_calibration.json` (arm, keys `ARM_PICK` / `ARM_DROP` / `ARM_PARK`) and `config/shuttle_calibration.json` (`tilt`, `shuttle`, and `invert` from the direction check).
- Menus 2 and 3 offer the **direction check** (menu `d`) first, until the shuttle has been homed in that session. It is only for a **bare** servo on the bench (§13.3, §13.5); once the crank or shaft is fitted, skip it.
- **Travel test** (menu `t`, §19.1 item 1): ch0, ch1 or ch2, **bare** servo with only a horn on the spline to mark. It asks the same "nothing fitted?" question as `d`, and refuses once the arm or the shuttle has been homed in that session (re-run the tool). The servo goes straight to 90°, then ramps slowly to 0°, 180° and back to 90°; mark the horn at each stop. Then type the two measured angles (90° mark → 0° mark, 90° mark → 180° mark). The tool compares them with what the channel needs: **arm ≥ 87° each side (174° in all)**, **ch2 ≥ 88° each side (176°)**, **ch1 ≥ 56.5° below and 30.2° above** (its nominal tilt range 41.5–112.2° plus the ±8° window, 86.7° in all). On a 270° servo a short side still passes if the command that would reach it is one calibration accepts (the tool prints it), because the centring offset leaves 45° of travel past each end. Unlike menu 3, it is not clamped to 2–178°: ch2 really goes to 0° and 180°.
- Without `--no-mock` nothing moves, but values **are** still written.

**Where each setting lives:**

| What | File |
|---|---|
| Arm angles | `config/servo_calibration.json` (calibrate_servos.py menu 1) |
| Tilt and carriage angles | `config/shuttle_calibration.json` `tilt`, `shuttle` (menus 2 and 3) |
| ch1 / ch2 direction | `config/shuttle_calibration.json` `"invert": {"1": false, "2": false}` (menu `d` writes it) |
| ch1 / ch2 actuation range (DS3218MG-270) | `config/shuttle_calibration.json` `"actuation_range": {"2": 270}` (by hand) |
| Load-cell scale factor and empty-cradle reference | `config/loadcell_calibration.json` (`main.py --calibrate`) |
| Camera crop | `config/camera_crop.json` (`calibrate_camera.py`) |
| Belt centring, camera, exit run, arm lift, calibration mass, **hopper switches and elevator**, **arm actuation range** | **`config/machine.json`** (§16.6) |
| Bin limits | `config/bin_limits.json` (§16.7) |
| Identification thresholds | `config/identify.json` (§16.8) |
| Web UI token | `config/web.json` |

Both calibration files are validated at every start, as strictly as `machine.json` (§16.2 for `servo_calibration.json`, §16.4 for `shuttle_calibration.json`): any problem refuses to start with every bad key listed (exit 78), because a dropped `invert` or a mistyped angle would drive a crank into its end stop or the arm into the hopper.

### 16.1 Load cell

1. Stop the service, then run `venv/bin/python main.py --calibrate`. Like the hardware tools (§15.2), it first records the machine as **not clean** ("tool ran: main.py --calibrate") and never marks it clean again, so the next sorter start asks for **Machine clear**: take the reference mass off before you confirm. If the arm / shuttle pose isn't known to be at rest, it first asks you to check the machine is clear and moves them there directly. The cradle goes to HOLD.
2. Press Enter with the cradle **empty** to tare. This stores the empty-cradle reference.
3. Put the reference mass flat in the middle of the cradle and press Enter. The default reference is a **US 5-cent nickel, 5.000 g**. For another known mass use `--mass G`, e.g. `main.py --calibrate --mass 10.0`. The scale factor is saved to `config/loadcell_calibration.json` and the script prints what the reference now reads.
4. Remove the reference and press Enter. The empty cradle is read again; if it reads empty it is tared once more, otherwise you are told to re-run the calibration.

**The empty-cradle reference and when it may change** (`hardware/loadcell.py`). `--calibrate` stores the empty cradle's absolute raw HX711 reading (`"empty_offset"`) and a drift baseline (`"calibrated_empty_offset"`). At **every** start-up the sorter compares the cradle with this reference **before** it tares, so a card left on the cradle is caught (§15.4). Only two things may overwrite the reference:
1. `main.py --calibrate`;
2. the tare the sorter takes right after a card has **provably left** the cradle (its weight dropped back to empty), and only if the zero that card was weighed against was itself anchored (from 1, from 2, or from the start-up check against the stored reference), and only if the new value is within **0.8 g** of the calibration baseline, so small residues can never ratchet it.

Nothing else stores it: not **Machine clear**, not a plain tare, not `test_hardware.py`. A tare taken "on the operator's word" (confirmed start with no stored reference) is never anchored, so nothing after it is stored until you run `--calibrate`.

**Re-run `--calibrate`** (cradle truly empty, PTFE tape fitted) when:
- you re-tape the cradle, re-route or re-tie the load-cell lead, or change anything on the cradle / TF;
- you change the HOLD angle (§16.4);
- start-up reports "cradle reads … BELOW the stored empty-cradle reference" (after checking the cell and lead);
- start-up reports "no stored empty-cradle reference";
- start-up keeps finding "card on cradle" with the cradle really empty (zero drift beyond 0.8 g).

Load-cell faults: a raw reading of −1 (HX711 unpowered or DOUT stuck high), a reading at the 24-bit rails, or one more than 100 g from the zero is a failed read and is re-read; after 6 failures in one measurement the machine stops ("load cell failed"). A weight more than 0.5 g **below** the tare is a fault, never "empty".

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
- **ARM_PARK (90):** top of the arc, the crank 3° past vertical toward the hopper (93°), as fitted in §11 step 3. Keep 90 (`n`) unless the cup isn't clear of both the hopper and the belt.

**`config/servo_calibration.json`** (section `pickup_arm`, written by menu 1) is validated at start (exit 78 on any problem): only `ARM_PICK`, `ARM_DROP`, `ARM_PARK` (old `ARM_DOWN` / `ARM_UP` are still read, with a warning, if the new key is missing); every angle a finite number within the servo's range and inside its window round the nominal (175 / 5 / 90) **or round the mirrored pose** (180° − nominal, for a servo that turns the other way): **PICK 155–180** (or 0–25), **DROP 0–25** (or 155–180), **PARK 80–100**. PICK and DROP must lie on opposite sides of PARK, and **the two half-arcs must match within 10°**: |(PICK − PARK) − (PARK − DROP)| ≤ 10°. Unknown sections and keys are refused.

Why these limits: the crank is fitted within 1.8° of 93° (§11 step 3), and the rest is trim and the servo's gain. A crank fitted as documented puts PICK and DROP both 85° / (1 + gain) from PARK, so a servo that turns 10 % more than commanded needs PICK ≈ 167 and DROP ≈ 13. That is why the windows open 20° toward PARK and only 10° away from it (away from PARK the arm would go past the stack or the belt). The symmetry rule holds whatever the gain. A model of every fit (±1.8°), gain from −10 % to +10 %, and PICK / DROP trim passes every build the servo can reach (`tests/test_audit5_fixes.py`). A typo such as `ARM_DROP` 400 or 50 is outside its window, and 157 for 175 breaks the symmetry by 18°, so neither can swing the arm into the hopper.

**DS3218MG-270 (recommended upgrade, §19.1 item 1):** set `"servos": {"ARM_ACTUATION_RANGE": 270}` in `config/machine.json` (default 180; only 180 or 270 are accepted), then re-calibrate all three arm angles. They stay **geometric** (PARK 90°): the code adds the 45° centring offset at the pulse output only (§14.3), so PARK is 1500 µs on either servo and the arc's ends sit 45° inside the DS3218's travel. Fit the crank at the commanded PARK (90°) exactly as in §11 step 3; the offset is invisible to you. The same windows and the symmetry rule apply, clipped to −45–225° instead of 0–180° (PICK up to 185°, DROP down to −5°).

**Check:** `test_hardware.py` test 4 (pick and place). The card lands flat inside the guide funnel, released ≤ 1.7 mm off-centre in Y.

### 16.3 Elevator trip height

Run test 11 (home, then raise to pick) with a stack of commons.

1. **Measure from the hopper rim down to the top card: target 3.5 ± 0.3 mm.** That puts the card at Z 90.9, level with the belt top.
2. **Coarse adjustment:** slide the top switch in its slots. Higher trip = less depth.
3. **Fine adjustment:** `"TRIP_EXTRA_STEPS"` in the `elevator` section of `config/machine.json` (whole number 0–2000, default 0). About 510 half-steps per mm (`STEPS_PER_MM` 509.5); positive values raise the card further after the trip. Restart the sorter after an edit.
4. Repeat with 10 cards removed and check it stays within ±0.3 mm.
5. Re-check ARM_PICK after any change.

The first raise after homing may travel the whole stack height (that is why the top switch must be wired NC, §14.2); its timeout scales with the distance still to travel, so even a nearly empty hopper (≈ 70 s of travel) reaches pick height. **Every later raise is capped at `RAISE_CAP_MM`** (3 mm ≈ 9 cards, `config/machine.json`). No trip within it: within `RAISE_CAP_MM` of the soft top limit that means **hopper empty**; lower down the machine stops with "top switch not detected — check wiring" (§14.2).

### 16.4 Shuttle: tilt and columns

1. **Menu 2, at home.**
   - **hold:** bed 10° nose-down, card tail clear of the rails, guides and clips.
   - **level:** skids firmly on the home ledges; bed 0.7 mm below the belt top. The default is **93.1°**; keep it only just past the point where the skids touch (§14.3).
   - The goBILDA coupler was indexed at HOLD to within 1.2° (§13.3: 25T × hex = 2.4° steps); this is where that residual is trimmed. If hold or level need more than a few degrees, the coupler is on the wrong tooth or the shaft slipped in the clamp: re-index it (§13.3–§13.4) rather than jogging.
2. **Menu 3, columns 0–3 and reject.**
   - Centre the cradle on each slot by eye, or drop a 65 mm card gauge into the slot and line the cradle up with it.
   - **Target: card centre within ±0.95 mm of the slot centre** (slot 65 for a 63 card; ≈ ±0.95 mm is the allowable carriage error from the CAD audit). The upper lead-in fins funnel ±2 mm.
   - Every move ends travelling toward +ψ, to take up backlash.
   - Expect ±2 mm repeatability (§19), so calibrate **each column on its own**.
3. **Menu 2 again, at a column (default column 1).**
   - **upper:** the card slides off the lip into the upper slot.
   - **lower:** the skids land on the R-bar, the kick reaches −40° and the card runs down the ramp into the lower slot.
4. **Verify:** run `--verify`, then `test_hardware.py` test 5. With a card, check both floors of all 4 columns and the reject bin.
5. **Column dump test** (§19.1). With a bulk common, dump **20 times into every column on each floor** (160 dumps, plus the reject bin). Not one card may strike a divider or land across one. If a column fails, re-calibrate it and repeat its 20 dumps on both floors.

**`config/shuttle_calibration.json`** (written by menus 2, 3 and `d`; edit `actuation_range` by hand):

```json
{"tilt": {"hold": 97.0, "level": 93.1, "upper": 112.2, "lower": 41.5},
 "shuttle": {"home": 75.5, "0": 178.0, "1": 87.3, "2": 65.2, "3": 45.0, "reject": 2.0},
 "invert": {"1": false, "2": false},
 "actuation_range": {"2": 270}}
```

- **`invert`**: per-channel direction. `true` makes the code write `actuation_range − offset − angle` (offset 45° on a 270° servo, else 0; a plain channel gets `angle + offset`), so every stored angle keeps its geometric meaning. Set by the direction check (menu `d`), never guessed. Only `"1"` and `"2"` with JSON `true` / `false` are accepted.
- **`actuation_range`** (DS3218MG-270, the recommended upgrade for ch2, §19.1 item 1): `{"2": 270}` for ch2 (ch1 can take `"1"` the same way); only 180 or 270. Set it **before** the direction check and before the crank (ch2) or coupler (ch1) goes on, fit them at the commanded pose (ch2: ψ 90, §13.5 steps 2–5; ch1: HOLD, §13.3), and re-calibrate every angle of that channel. Angles stay geometric: the code adds the 45° centring offset at the pulse output (§14.3), so the commanded pose and the fit are the same as with a 180° servo. The windows below (tilt ±8°, carriage ±12°) still apply, clipped to −45–225° instead of 0–180°.
- **Validation** (`hardware/shuttle.py`, at every start; any problem refuses to start with every bad key listed, exit 78, and nothing is applied):
  - valid JSON; sections only `tilt`, `shuttle`, `timing`, `actuation_range`, `invert` (keys starting with `_` are comments); unknown keys refused;
  - every angle a finite JSON number within the servo's reach (geometric **0–180**, or **−45–225** with `actuation_range` 270) **and within its window round the nominal** (the values in the table in §14.3): **tilt ±8°**, **carriage ±12°**.
    - ch1: the coupler is indexed at HOLD to ≤ 1.2°, and gain moves the tilt poses only a few degrees, so ±8° covers it. A typo (1122 for 112.2, a sign slip, swapped digits such as 79 for hold 97) lands outside.
    - ch2: the crank is set on the horn at ψ 90 to within about 1° (§13.5 steps 2–5, checked on the machine in §13.6 step 6). A servo that turns 10 % more or less than commanded then moves column 3 (45° from the ψ 90 fit) by up to ≈ 4.5°. Before 2.3.2 the crank went on by the nearest spline tooth (±7.2°): with gain that is up to 11.4°, which ±8° refused in about 7 % of builds at 8 % gain. ±12° passes even those. The swapped-digit carriage typos that now fit inside a window (54 for column 3's 45, 56.2 for column 2's 65.2, 78.3 for column 1's 87.3) break the gap rules below;
  - tilt order and gaps: `lower` < `level` < `hold` < `upper`, with **`hold` − `level` 2–8°** (nominal 3.9°), **`upper` − `hold` ≥ 8°** (nominal 15.2°) and **`level` − `lower` ≥ 30°** (nominal 51.6°), so two poses typed into each other's place (hold 93.2 with level 93.1) are refused too;
  - carriage order: `reject` < 3 < 2 < `home` < 1 < 0, neighbouring stops **at least 5° apart**, and **column 2 − column 3 ≥ 12°** (nominal 20.2°, still ≥ 18° at +10 % gain);
  - every `timing` value a finite number ≥ 0 within its range.

### 16.5 Camera

The code forces the IMX708's **2304 × 1296 2×2-binned full-field mode at 50 fps** (`hardware/camera.py`). Without that, picamera2 picks a 1536 × 864 centre crop that sees only 2/3 of the field. At start-up the camera reads back its sensor mode and crop, derives the mm-per-pixel figures from what it actually got, and prints a loud warning if it is not the full field. The main stream is 768 × 432 (identification), the low-res stream 320 × 180 (centring), both 16:9.

Focus is fixed (`AfMode` manual) at **`LensPosition` 10** dioptres (= 1 / 0.100 m, the card face). After a 1 s warm-up on the empty station, exposure and white balance are locked so the empty-station reference frame stays valid when a bright card comes in. All of this can be changed in `config/machine.json` (§16.6).

**Crop.** Stop the service, then run `venv/bin/python scripts/calibrate_camera.py --no-mock`. Like the other tools it refuses while the sorter runs and records the machine as not clean (§15.2):
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

**Afterwards, take the card off the belt.** The sorter's empty-station reference would otherwise include it; the next start asks for Machine clear anyway.

**`CARD_ROTATE`** (default 90, in the `camera` section of `config/machine.json`): if the saved crop is upside-down, set 270. It depends on which way the cards are loaded.

### 16.6 Machine tunables: `config/machine.json`

Belt centring, camera, sort timing, the hopper elevator and the arm's actuation range are **per-machine settings in `config/machine.json`**, not code. Copy the example and edit it:

```bash
cp config/machine.example.json config/machine.json
```

Every key is optional; a missing key keeps the code default shown below. The file is read when the sorter starts, so restart it after an edit. `config/machine.json` is not in git. (`RIFTBOUND_MACHINE_CONFIG` points the code at another file.)

**Validation** (`hardware/machine_config.py`). The **whole file** is checked the first time anything reads it, and the sorter **refuses to start** on any problem, listing **every** bad key, with **exit status 78** (`EX_CONFIG`). systemd does not restart on 78 (`RestartPreventExitStatus=78`), so the journal shows the list once: fix the keys, then `sudo systemctl start riftbound-sorter`. The rules:
- valid JSON; the top level and every section are JSON objects;
- **unknown sections and unknown keys (typos) are errors**; keys starting with `_` are comments and ignored;
- booleans are JSON `true` / `false`, never the string `"false"`; numbers are JSON numbers, never strings, `NaN` or `Infinity`; whole-number keys must be integral;
- every value inside its range or list below; `null` only where the table says so;
- `EXIT_MIN_S` ≤ `EXIT_MAX_S`.

There is no silent fall-back to the defaults. Delete the file to use them. `setup.sh` validates an existing file too, and so does `venv/bin/python -c "from hardware import machine_config; machine_config.load()"`.

**`card_detect` section** (belt centring, `hardware/card_detect.py`):

| Key | Default | Allowed | How to measure / meaning |
|---|---|---|---|
| `TRAVEL_SIGN` | 1 | 1 or −1 | Test 8 (live offset, belt off). Slide a card by hand in the travel direction (+X). The offset must **increase**; if it decreases, set −1. |
| `CENTRE_OFFSET_MM` | 0.0 | −20..20 | Place a card physically centred under the lens: hood inner end walls at X −45 / +55, so the card edges are 6.0 mm from each end wall. Read the offset in test 8 and **add** that reading to `CENTRE_OFFSET_MM`, so a centred card reads 0. |
| `BELT_SPEED_MM_S` | 150.0 | 30..600 | Mark a card's edge position, run test 9 (3 s), measure the distance moved and divide by 3. It also sets the seek timeout (`SEEK_MAX_TRAVEL_MM` 125 ÷ speed). |
| `STOP_LATENCY_S` | 0.040 | 0..0.5 | Age of the newest frame when the brake takes effect (≈ 1.5 frames at 50 fps + processing). Run test 10 (centring) at the nominal speed several times and adjust it until the mean stationary offset is ≈ 0. |
| `BRAKE_COAST_MM` | 1.5 | 0..20 | Test 10 5×. If the final offset is consistently +d mm (overshoot), add d. If it is consistently short, the nudges correct it; reduce slightly. |
| `CENTER_TOL_MM` | 2.5 | 0.1..20 | Stationary offset accepted without a nudge. |
| `MAX_CAPTURE_OFFSET_MM` | 6.0 | 0.5..30 | Above this the centring result is not ok (treated as a jam). |
| `PIXEL_DIFF` | 30 | whole 1..254 | Luma difference that counts as card. Change only if detection is unreliable. |
| `COL_FRAC` | 0.3 | 0.01..1 | Fraction of a column that must differ. |
| `VIEW_HALF_MM` | 48.0 | 10..64 | Visible half-window along X (hood interior ±50, less 2). |
| `SEEK_MAX_TRAVEL_MM` | 125.0 | 20..170 | Seek limit. |
| `SEEK_HARD_LIMIT_FACTOR` | 3.0 | 1..10 | Hard seek limit as a multiple of the above. |
| `FRAME_TIMEOUT_S` | 0.5 | 0.05..5 | Camera stall watchdog: if one low-res grab blocks longer than this, a helper thread brakes the belt and the cycle stops with a camera fault. |

**`camera` section** (`hardware/camera.py`):

| Key | Default | Allowed | Meaning |
|---|---|---|---|
| `LENS_POSITION` | 10.0 | 0..32 | dioptres = 1 / distance in m (100 mm → 10.0) |
| `AF_MODE` | `"manual"` | `"manual"`, `"continuous"` | fixed `LensPosition`, or continuous autofocus |
| `LOCK_AE_AWB` | true | true / false | freeze exposure and white balance after warm-up |
| `EXPOSURE_TIME_US` | null | null or whole 10..100000 | fixed exposure instead of the converged one |
| `ANALOGUE_GAIN` | null | null or 1..16 | fixed gain |
| `COLOUR_GAINS` | null | null or [red, blue], each 0.1..8 | fixed white balance |
| `CARD_ROTATE` | 90 | 0, 90, 180, 270 | 270 if cards are loaded the other way round (§16.5) |
| `STABILIZE_DELAY_S` | 0.15 | 0..2 | belt stopped → wait before the capture |
| `WARMUP_S` | 1.0 | 0..10 | AE/AWB warm-up on the empty station |
| `SWAP_RB` | true | true / false | BGR → RGB |
| `LORES_TIMEOUT_S` | 0.2 | 0.05..5 | a low-res frame not delivered within this → camera fault (belt braked). The main capture times out after 1.0 s. |

**`sort` section** (`main.py`):

| Key | Default | Allowed | Meaning |
|---|---|---|---|
| `EXIT_TRAVEL_MM` | 144.0 | 50..400 | belt travel from "centred" to "fully on the cradle" (trailing edge X −39 past the belt end X 85, + 20) |
| `EXIT_TIME_MARGIN` | 1.25 | 1..3 | × the computed run time. The run uses the belt speed **measured** during centring, never more than `BELT_SPEED_MM_S` |
| `EXIT_MIN_S`, `EXIT_MAX_S` | 0.6, 3.0 | 0.05..5, 0.1..10; MIN ≤ MAX | clamp on the exit run |
| `EXIT_EXTRA_S` | 0.4 | 0..3 | one extra belt burst if the card is only partly on the cradle |
| `SEAL_S` | 0.3 | 0..3 | cup on the card → pump seal time before the lift |
| `DROP_SETTLE_S` | 0.1 | 0..3 | settle at the drop pose before release |
| `ARM_LIFT_DEG`, `ARM_LIFT_S` | 10.0, 0.6 | 0..45, 0.05..5 | the slow first lift after release |
| `WEIGH_SETTLE_S`, `TARE_SETTLE_S` | 0.2, 0.3 | 0..5 each | settle before weighing / taring |
| `RESUME_DELAY_S` | 2.0 | 0..30 | bin reset → hands out of the tray before the shuttle moves |
| `CALIBRATION_MASS_G` | 5.0 | 0.5..500 | default reference mass for `--calibrate` |
| `CUP_HOLD_MAX_S` | 600.0 | 10..3600 | how long the pump keeps holding a card the arm could not carry to the belt, while the machine waits for you, with the arm left where the carry failed; then the pump switches off and the card drops from that pose (where it lands: §14.8) |

**`elevator` section** (`hardware/elevator.py`):

| Key | Default | Allowed | Meaning |
|---|---|---|---|
| `TOP_SWITCH_NC` | true | **true** (NO wiring refused) | top-of-stack switch wired C → GND, **NC** → GPIO 12 (§14.2). `false` stops the start with exit 78 |
| `BOTTOM_SWITCH_NC` | true | true / false | home switch wired C → GND, **NC** → GPIO 13; `false` if wired to NO |
| `RAISE_CAP_MM` | 3.0 | 0.5..10 | max travel of every raise after the first one since homing; no trip within it = hopper empty near the top limit, else "top switch not detected" |
| `UP_DIRECTION` | 1 | 1 or −1 | −1 if "raise" moves the floor down (§15.2) |
| `TRIP_EXTRA_STEPS` | 0 | whole 0..2000 | extra half-steps after the top switch trips (§16.3; ≈ 510 per mm) |
| `HOME_BACKOFF_MM` | 0.5 | 0.1..5 | back-off above the home switch; the switch must read released afterwards |

**`servos` section** (`hardware/servos.py`):

| Key | Default | Allowed | Meaning |
|---|---|---|---|
| `ARM_ACTUATION_RANGE` | 180 | 180 or 270 | 270 for a DS3218MG-270 on the arm (§16.2); re-calibrate the arm afterwards |

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
{"0": 45, "4": 14}
```

Every value must be a **whole number from 1 to the cap** of its bin: **lower 0–3: 54** (18 mm, the highest pile `cad/shuttle_check.py slide` covers), **upper 4–7: 15** (≈ 5 mm, 1 mm past the 4 mm pile the slide simulation still lands a card on; it already calls an 8 mm pile SHORT), **reject 9: 52** (17.4 mm under the lane lip). Keys are `"0"`–`"7"` and `"9"` (keys starting with `_` are comments). Anything else (an unknown bin, a string, a fraction, a value over the cap, invalid JSON) refuses to start with exit 78. The caps are geometric maxima, not recommended limits.

Raise in small steps (a few cards at a time), and only after a run of bulk commons into that bin shows every card landing flat with the pile at the new height. The upper floor is the one to be careful with: cards that can't slide fully into the slot hang on the cradle lip.

### 16.8 Identification: `config/identify.json`

Optional; every key overrides a default in `vision/identify.py`. Leave it out until you have a labelled sample of real scans to tune with.

```json
{"min_conf": 0.80, "min_margin_bits": 10, "fallback": true,
 "fallback_min_phash_conf": 0.70, "max_missing_fraction": 0.01}
```

| Key | Default | Meaning |
|---|---|---|
| `min_conf` | 0.80 | pHash confidence below this → not identified (reject). 0.80 ≈ Hamming distance ≤ 51 of 256 bits |
| `min_margin_bits` | 10 | the runner-up must be at least this many bits further away, else the match is **ambiguous** → reject. 0 turns the check off |
| `fallback` | true | JSON boolean. When pHash is merely below `min_conf` (and unambiguous), ahash and dhash may confirm it; the card is accepted only if all three agree on the same card. An ambiguous pHash is never overridden |
| `fallback_min_phash_conf` | 0.70 | pHash must reach at least this for the fallback to be tried |
| `max_missing_fraction` | 0.01 | share of the card list that may lack a hash before sorting is refused (§15.4) |

**Validation** (`vision/identify.py`, at start-up, like `machine.json`): `min_conf` a number 0.5–1.0; `min_margin_bits` a whole number 0–256; `fallback` a JSON boolean (never `"false"`); `fallback_min_phash_conf` a number 0.5–1.0 and not above `min_conf` when both are set; `max_missing_fraction` a number 0–1. Unknown keys (typos), wrong types, `NaN` / `Infinity` and invalid JSON refuse to start with every bad key listed, **exit 78**, and nothing is applied. Delete the file to use the defaults.

---

## 17. First run: bulk commons only

1. `--verify` the servo poses, then run every test in `test_hardware.py --no-mock` once.
2. **Start the service and confirm.** `sudo systemctl start riftbound-sorter`, open the web UI, enter the token when asked (`main.py --web-token`), check the machine is clear and press **Machine clear** (first start, and every start after a hardware tool ran, §15.4).
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
| Pump runs or vent clicks at boot or after the program exits | 10 kΩ pull-up on GPIO 17 / 27 missing; kernel parameter not applied (no reboot since setup); `ExecStopPost` failing | Fit it (§14.2). `cat /proc/cmdline` must contain `pinctrl_bcm2835.persist_gpio_outputs=0`. `journalctl -u riftbound-sorter` for `[safe_outputs]` errors. Run the safe-state test (§14.8). |
| Arm lifts nothing | Cup not reaching the card; leak; pump on the wrong port; vent valve leaking | Jog ARM_PICK deeper (slider must compress). Pinch-test the tube. Use the pump **inlet**. Swap the valve's ports (§14.6). |
| Card won't release at the drop | Vent valve not opening (wiring, relay IN2, GPIO 27); valve fitted the wrong way round | Test 3. Check relay channel 2 clicks. `VENT_S` in `hardware/vacuum.py`. |
| Card dropped off-centre, rides on a guide | ARM_DROP X is off; card released > 1.7 mm off in Y | Re-calibrate ARM_DROP. Check the hopper card isn't sitting against one wall. |
| "Hopper empty" with cards loaded | Flag not reaching the card; top switch set too high | §16.3. Check the flag drops freely and the plate notch is under the flag. |
| "top switch not detected — check wiring" | the top switch didn't trip within `RAISE_CAP_MM` while the floor was still well below its top limit: switch set too high, flag sticking, wiring | Check the flag drops freely, the switch position (§16.3) and the wiring (C → GND, NC → GPIO 12). Test 11. |
| Floor rises to the top limit at the first raise after homing, stack pushed up to the arm | the top switch is mechanically stuck closed (its contact never opens); this can't be detected (§19.1) | Stop at once. Replace the switch and check it clicks open when the flag tip is lifted (§10, §16.3). |
| "bottom (home) switch still pressed … above it" / homing fails | home-switch wire broken (reads pressed with NC wiring); switch stuck | Check C → GND, NC → GPIO 13 and `BOTTOM_SWITCH_NC`. |
| Arm picks too low / "card never seen" right after a refill, floor doesn't rise | top-switch wire broken with NC wiring (reads pressed = "at pick height") | Check the top-switch wiring. |
| Elevator stalls or misses steps | Binding on the rods or lead screw; steps too fast | Check the carriage slides by hand. Don't go below `MIN_STEP_S`. |
| "home" moves the floor up | stepper direction | `"UP_DIRECTION": -1` in `config/machine.json` (§15.2). |
| Jam: card not seen at the scanner | Belt slipping; `TRAVEL_SIGN` wrong; reference frame taken with a card present | §16.6. Check the coupling set screws on the rod flats. |
| Card stops off-centre | `BELT_SPEED_MM_S` / `STOP_LATENCY_S` / `BRAKE_COAST_MM` | §16.6, test 10. |
| Camera warns "NOT the full field of view" | the sensor mode wasn't applied | Update picamera2 (`sudo apt upgrade`), re-run setup.sh. The centring margin is lost until it is fixed. |
| `error`: "camera stopped delivering frames" / "camera grab blocked" | ribbon loose or damaged; camera stalled | Belt was braked. Remove the card, reseat the SC1130 at both ends, **Machine clear**. |
| Misidentification | Glare; crop off; focus; DB stale | Keep the LED strips in their bands. Redo §16.5. Check `LENS_POSITION`. `main.py --build-db`. |
| Image upside-down or mirrored | `CARD_ROTATE`; bracket FPC edge not facing −Y | §16.5. Re-mount the camera. |
| "No card on the cradle" / "card not fully on the cradle" | exit run too short; card caught at the belt end | §16.6 (`EXIT_TRAVEL_MM`). Check the cradle is LEVEL and 0.7 mm under the belt. Lift the card off by hand, then **Machine clear**. |
| "card on cradle — remove it" at start-up | a card was left on the cradle, or the empty reference is stale | Remove the card and confirm. If the cradle really is empty, re-run `main.py --calibrate`. |
| "cradle reads … BELOW the stored empty-cradle reference" | load-cell fault, lead tugging, zero drift | Check the cell, lead and loop (§14.7), then `main.py --calibrate`. |
| "no stored empty-cradle reference" | never calibrated, or an old calibration file | `main.py --calibrate` (§16.1). |
| Waits in `needs_confirm` | first start, the last stop was unclean, a hardware tool or `main.py --calibrate` ran since, or a stop while a card waited on the cradle | §15.4: check the machine, remove any card, then **Machine clear** or `--confirm-clear`. |
| "card held on cup — remove it by hand before stopping the service" | the arm couldn't carry the card to the belt (3 tries); the pump holds it | Take the card off the cup by hand, then **Machine clear**. Don't stop the service first: that lets the card go. The arm stays where it stopped (never parked); after `CUP_HOLD_MAX_S` (600 s) the pump switches off by itself and the card drops from there. The message says where: back onto the stack (near PICK), onto the belt (towards DROP) or across the hopper rim / belt inlet (mid-arc or PARK, may be bent) (§14.8). If it already dropped, pick it up from there, check it isn't bent, then **Machine clear**. |
| Won't start: `[config] ERROR: invalid … — refusing to start`, service not restarting (exit 78) | a bad key in one of the five checked files: `config/machine.json`, `identify.json`, `shuttle_calibration.json`, `servo_calibration.json`, `bin_limits.json` (typo, unknown key, string instead of number, out of range or outside the sanity window (arm PICK 155–180 / DROP 0–25 / PARK 80–100 or mirrored, tilt ±8°, carriage ±12°), poses out of order or too close / too far apart, arm PICK / DROP not symmetric about PARK within 10°, `TOP_SWITCH_NC` false, a bin limit over its cap) | Fix every key listed (§16.6, §16.8, §16.4, §16.2, §16.7), or delete the key / file for the defaults. Then start the service. |
| "another sorter process or a hardware tool is running" / a tool says "the sorter or another tool is running" | the service is running while you start `main.py` or a tool by hand (or a second copy) | `sudo systemctl stop riftbound-sorter` first, or let the tool finish. |
| Service, `main.py` or a tool won't start: "cannot open …/data/sorter.lock … Fix: sudo chown -R <user>: …/data" or "…/data is not writable by this user", exit 78, the service not restarting | a root-owned `data/`, `data/sorter.lock` or `data/machine_state.json`, left by a tool or `main.py` run with `sudo` | `sudo chown -R <user>: data` (your user name, in the checkout), or re-run `bash scripts/setup.sh`; then start the service. Never run the tools or `main.py` with `sudo` (§15.2). |
| `calibrate_servos.py` won't jog any further | the pose is at the edge of its own sanity window: arm PICK 155–180 / DROP 0–25 / PARK 80–100 (or mirrored), tilt ±8°, carriage ±12° (§16) | The arm horn or ch1 coupler is on the wrong spline tooth, or the ch2 crank is off its ψ 90 line: re-fit it (arm: the 93° fit, §11 step 3; ch1: §13.3; ch2: §13.5 steps 2–5 and the §13.6 step 6 check). |
| `calibrate_servos.py` says "HELD, not written yet", or "NOT saved: … still held at the end of the menu" | the pose is fine on its own but breaks a rule between poses (arm symmetry, tilt order / gaps, carriage order / spacing, column 2 − column 3 ≥ 12°) against poses not yet set (§16) | Set the remaining poses of that menu: the held pose is written with the first save that makes the file valid. If it is still held at the end, re-run the menu and check the pose the rule names. |
| `error`: "hash DB incomplete" | card image downloads failed | `main.py --build-db` with internet (§15.5); it retries by itself every 60 s. |
| Web UI or CLI action refused (HTTP 409) | not allowed in the current state | The message says why; see the table in §15.3. |
| ch2 crank swings toward the end post / wrong way | servo direction not checked or `invert` lost | Unplug ch2 at once. Remove the crank, re-run the direction check bare (menu `d`, §13.5). |
| Weight "unknown" / drifting | Load-cell lead tugging the cradle; cradle touching the TF | Re-route the trailing loop (§14.7). Check the cradle touches only the cell. Re-tare. |
| "load cell failed" | HX711 wiring or power; repeated failed reads | Check DOUT = GPIO 5, SCK = GPIO 6, VCC on 3.3 V. |
| Card hangs on the cradle lip | PTFE tape missing or worn; tilt pose short; bin pile too high | Re-tape. Re-calibrate upper/lower. Lower that bin's limit (§16.7). |
| Card hits a tray wall or divider | Column off by more than ≈ 0.95 mm | Re-calibrate that column and repeat its 20-dump test (§16.4). |
| Shuttle stalls or jerks | LM8UU misaligned; tilt crank binding in the sled pocket; REX shaft dry; ch2 pivot screw too tight; rod set screws loose | Re-align the end posts. Repeat the drag test (≤ 3 N, §13.4 step 7); wipe the REX shaft with dry PTFE lube. The shoulder screws should spin the link freely. Tighten the rod set screws (§13.4). |
| Cradle angle drifts or HOLD / level need large corrections | ch1 coupler clamp loose or on the wrong tooth | Re-tighten the M4 clamp at HOLD; re-index (§13.3–§13.4). |
| Cradle servo hums or gets hot at home | level angle too far past the ledges | Back `level` off toward the touch point (§16.4). |
| PCA9685 not found (`i2cdetect`) | SDA/SCL swapped; VCC missing | §14.2. |
| `vcgencmd get_throttled` ≠ 0x0 | Logic rail overloaded; bad wiring; 3 A adapter in use | Check that only the Pi, LEDs and relay are on Reg #1 (L9110S and ULN2003 on Reg #3). Use the 12 V 5 A adapter. Check the 22 AWG runs. |
| Belt twitches at boot or after exit | L9110S inputs floating | Fit the 10 kΩ pull-downs on GPIO 23–26 (§14.2). |
| PCA9685 flaky / I²C errors | PCA9685 VCC on 5 V; missing V+ capacitor | VCC to Pi 3.3 V. Fit 1000 µF at V+. |
| Web UI says "missing or wrong token" | token not entered or changed | `venv/bin/python main.py --web-token`; clear the browser's saved token and re-enter it. |
| "machine is running / starting: pause or stop it before emptying …" | a bin reset while sorting or starting | Pause or Stop first (§15.3). |
| "Machine clear" refused while paused | by design: a card may be held on the cradle | Stop first, then Machine clear (§15.3). |
| Web UI unreachable | Service down | `journalctl -u riftbound-sorter -n 50`; `sudo systemctl restart riftbound-sorter`. |

---

## 19. Known risks / test first

### 19.1 Test first on the real machine

None of these can be settled in CAD or in the mock tests. Check each one on the bench or on the built machine **before** relying on it (and before printing the big parts where it says so):

1. **Servo travel (before printing the arm).**
   - **Arm (ch0):** needs **170°** of crank travel (ARM_DROP 5° → ARM_PICK 175°), and the crank is fitted within 1.8° of its mid pose (§11 step 3). So the servo must turn **at least 87° each side of 90°** between 0° and 180° (≥ 174° in all). A servo that turns more than 3.5 % less than commanded can't reach both ends; one that turns up to 10 %+ more is fine, because the windows allow for it (§16.2).
   - **Carriage (ch2):** needs **~176°** (reject 2° → column 0 178°), with both stops at dead centres right at the ends of a 180° servo's range. With the crank fitted at ψ 90 (§13.5), that is **≥ 88° each side of 90°**. The reject side is the one that matters: a few degrees short there costs millimetres, while column 0 costs < 0.3 mm.
   - Many MG996Rs give only ~120° with standard pulses; the code uses 500–2500 µs.
   - **Test:** `calibrate_servos.py --no-mock`, menu **`t`** (travel test, §16), on the **bare** servo with a horn pressed on to mark. It refuses once the arm or shuttle has been homed in that session, so run it on the bench before anything is fitted. It sweeps slowly to 0°, 90° and 180°; mark the horn at each stop, measure each side from the 90° mark with a protractor, and type the two angles in. The tool reports them against what the channel needs (arm ≥ 87° each side, ch2 ≥ 88°, ch1 56.5° / 30.2°). Menu 3 can't do this for ch2, because it stops 2° short of each end.
   - **Recommendation: a DS3218MG-270 on the arm (ch0) and the carriage (ch2).** About **$15.59 each, ≈ $31 for the two** (e.g. ANNIMOS DS3218MG "Control Angle 270°", [amazon.com/dp/B076CNKQX4](https://www.amazon.com/dp/B076CNKQX4); BOM "Recommended upgrade"). Its 270° travel means the 0–180° working span asks for only two thirds of what the servo can turn. That removes the main MG996R risk: a unit that physically can't turn the ≥ 174° (arm) or ~176° (ch2) these two channels need.
     - **Fit:** same 25T spline and the same standard-size case (40 × 20 × 40.5 against the MG996R's 40.7 × 19.7 × 42.9). Measure its tab-hole pitch (item 13) and its spline-face-to-tab height against your MG996R before printing the arm head, the −Y end post and riser B.
     - **Configure, before fitting anything:** arm `"servos": {"ARM_ACTUATION_RANGE": 270}` in `config/machine.json` (§16.2); ch2 `"actuation_range": {"2": 270}` in `config/shuttle_calibration.json` (§16.4).
     - **Fit at the commanded pose:** the arm crank at PARK 90° (§11 step 3), the ch2 crank at ψ 90 (§13.5). Then calibrate every angle of that channel. The angles stay geometric; the code adds a 45° **centring offset** at the pulse output (§14.3), so 90° is 1500 µs on either servo and you never see the offset.
     - **ch2 horn:** keep the MG996R's round plastic horn on ch2. The M2 self-tappers need its plain plastic disc; the DS3218's aluminium arm won't take them.
     - **Why its ends are safe.** With the centring offset, geometric 0° and 180° are 833 µs and 2167 µs. The arm's DROP end and ch2's reject end sit 45° of servo travel inside the pulse limits, not at them (before 2.3.2 they were at 500 µs).
     - **Still run the travel test on it** (menu `t`). A true-scale 270° unit turns 90° each side of 90° at commanded 0° / 180°. Some DS3218s are reported to turn only ≈ 255° over 500–2500 µs, i.e. ≈ 85° each side. That is short of 87° / 88°, but such a unit can still reach both ends: calibration may command past 0° and 180° (arm PICK up to 185°, DROP down to −5°; ch2 reject down to −10°, column 0 up to 190°). The test prints the command each short side needs and passes it if that is inside those limits.
   - **The MG996R stays the baseline.** If yours passes the test, keep it: the bench test decides, servo by servo.
2. **Servo direction (ch1, ch2).** Run the bare-servo direction check (menu `d`) before the coupler or the crank goes on (§13.3, §13.5). MG996R clones differ; a reversed ch2 without `invert` drives the crank into the end post.
3. **Relay at 3.3 V logic.** The 5 V relay module is driven from 3.3 V GPIO; some boards never fully switch off. For the first few seconds after power-on IN sits at only ≈ 2.7 V (the SoC's ≈ 50 kΩ pull-down against the 10 kΩ pull-up), until the firmware applies the `config.txt` pull-up from `setup.sh` (`gpio=17,27=ip,pu`, ≈ 3.3 V; check `pinctrl get 17,27` shows `pu` after the reboot). Bench-test both channels at 3.3 V and at ≈ 2.7 V before wiring (§14.1 step 5). If one is marginal, 4.7 kΩ pull-ups instead of 10 kΩ give ≈ 3.0 V straight out of reset.
4. **Camera:** check at start-up that the IMX708 really runs the 2304 × 1296 full-field mode (no "NOT the full field of view" warning), that `LensPosition` 10 gives a sharp card, and tune `STOP_LATENCY_S` (and `BRAKE_COAST_MM`) with test 10 (§16.5, §16.6).
5. **HX711 timing under rpi-lgpio.** The vendored HX711 library bit-bangs SCK through `RPi.GPIO`, which on current Raspberry Pi OS is the `python3-rpi-lgpio` shim. Its per-call overhead and timing on a Pi Zero 2 W are untested here: with test 6, check that repeated empty and one-card readings are stable (0 ± 0.3 g; 1.3–2.3 g) and that no "load cell failed" / retry messages appear.
6. **Belt speed.** `BELT_SPEED_MM_S` (default 150) is a guess for two N20s at 5 V: measure it (test 9, §16.6). It sets the seek timeout and the exit run.
7. **Bin capacities depend on the card friction (μ).** The default limits (40 lower, 12 upper, 35 reject) come from the slide simulation at μ 0.35–0.45 (`cad/shuttle_check.py slide`). Real raw cards on PTFE tape may slide better or worse. Raise limits only after a run of commons into that bin shows every card landing flat at the new pile height (§16.7).
8. **Vent valve and pump dimensions.** The valve clip and the pump-head cradle are built round reference envelopes (uxcell 12 V NC valve ≈ 15 × 14 × 34; R385 head ≈ 32 long), not vendor drawings. Measure yours: the valve must snap into the clip on its foam strip, the pump head must rest on its pad without lifting the can (§14.6). Check the tee's Ø3 barbs take the 4 × 2.5 PU tube.
9. **ch1 coupler indexing.** The goBILDA coupler is indexed to the hex flats at HOLD (7° up from +X) to within 1.2° (§13.3). Confirm on the machine that HOLD and level land within a degree or two of 97° / 93.1° before trimming; a big error means a wrong tooth or a slipped clamp.
10. **Camera ribbon slack.** The route is ≈ 450 mm on the 500 mm SC1130: **≈ 50 mm of slack**. Test-fit it before tying anything down (§14.5). The fallback is a longer third-party 15-to-22-pin cable (1 m).
11. **Load-cell loop at column 0.** The 350 mm loop needs ≈ 30 mm more slack at column 0, where its bend comes within 5 mm of the −Y end post (§14.7). Test-fit through every column.
12. **Hopper lift clearance.** A card lying 1.5 mm off-centre (also in a cavity corner) clears the hopper by ≥ 0.49 mm during the lift (`cad/pick_arm_check.py`). Watch the first lifts.
13. **MG996R tab-hole pattern (before printing the arm head, −Y end post and riser B).** Every MG996R mount uses one pattern, 49.5 × 10 mm (`cad/machine_frame.scad`). Measure your servos; clones vary (48.5–50 seen). Within about ±0.7 mm the screws still land in the Ø4.5+ grommet holes; beyond that change `mg996r_hole_pitch` and re-export those three parts (§11).
14. **Column dump test.** The allowable carriage error is only **≈ ±0.95 mm** (65 mm slot, 63 mm card). After calibrating the columns, dump a bulk common **20 times into every column on each floor**: no card may strike a divider (§16.4 step 5). Repeat after any knock or re-calibration.
15. **Tilt-crank drag test.** The tilt crank slides along the REX shaft inside the sled as the carriage moves, and ch2 has to push it. Pull the carriage along its whole travel with a **spring scale, target ≤ 3 N** (ch1 at HOLD, ch2 link off, §13.4 step 7). Lubricate the REX shaft with a **dry PTFE lube**; re-check after the first few hundred cards.
16. **Stuck top switch (residual risk, cannot be tested away).** The NC wiring catches a broken wire, and every raise after the first is capped at 3 mm. But a top switch that is **mechanically stuck closed** (contact never opens, wire intact) is not detectable on the **first raise after homing**: the floor then rises to its soft top limit with the stack. Before the first run, and whenever a raise looks wrong, lift the flag tip by hand and check the switch clicks every time, and that the flag drops back onto its stop. Use a switch with a clean, positive click.

### 19.2 Other known risks

1. **PTFE tape on the cradle is required.** Without it the upper-floor transfer jams. Check it every few hundred cards.
2. **Bin capacities are small** (above). The machine pauses with the card held on the cradle until the bin is emptied and reset. A taller riser would buy upper-floor capacity, but that is a design change.
3. **Column accuracy is ±2 mm** (servo slider-crank plus backlash) against an allowable carriage error of only **≈ ±0.95 mm**. Calibrate each column (§16.4), run the 20-dump test, and re-check after any knock.
4. **Tight clearances to check on the printed parts:**
   - shuttle cradle / tilt frame / carriage / ramp: 0.5–0.8 mm;
   - card to the hopper during the lift: 1.5 mm centred, ≥ 0.49 mm for a card lying 1.5 mm off-centre (lift relief, §10);
   - a card held 1.5 mm off-centre in Y passes the scan station's guides by 0.46 mm at the drop;
   - ch2 crank tip at column 0 reaches Y −269 against a 270 mm baseplate edge;
   - hood clips and guide funnel within a few mm of the arm drop.
5. **Vacuum release** depends on the vent valve (§14.6). A valve fitted the wrong way round can leak during a pick or fail to vent. Run test 3 and the pick-and-place test with commons. Without a valve (`VENT_PIN = None`) the code just waits 0.3 s, and the R385's check valves may hold the card on the cup.
6. **Servos are limp whenever the sorter isn't running** (and on power loss). The arm is parked before it goes limp (a card still held on the cup is let go first, from where the arm stands, §14.8), but with the 12 V pulled it falls and drops any card. While the sorter idles, only ch1 is off; the arm and carriage keep holding. Always stop the service before unplugging.
7. **First moves after an unclean stop are full-speed jumps**, and only after **Machine clear** (§15.4). Keep hands out of the machine when you confirm after a crash or power loss. After a clean stop the servos snap back by whatever they sagged while limp.
8. **12 V supply.** The arm-move peak with the pump on is ≈ 3.2 A, over the owned 3 A adapter. **Use the 12 V 5 A adapter** (64 % at peak). The 3 A one is for bench tests with the servos unplugged.
9. **O-ring belts** run at 7.4 % stretch. NBR relaxes over time; if a card slips, replace the belts.
10. **Card position under the camera.** The Y margin is only 4.2 mm worst case. Cards must stay in the 66.4 mm guide channel.
11. **Glare.** The LED strips must stay below 21 mm above the card or foils will show a hotspot. No GPIO switches them: they are on whenever the logic rail is.
12. **Hopper-empty detection** depends on the plate notch passing under the flag. Check it in §10 with an empty plate.
13. **Shoulder screws.** The ch2 pivots need 4 mm-shoulder screws with an M3 × 4 thread (5 and 6 mm shoulders). Order them early; they are not in common assortments.
14. **Kernel parameter and boot pull-up need a reboot.** Until the first reboot after `setup.sh`, only `ExecStopPost` (not the kernel) releases the outputs after a crash, and the relay inputs sit at ≈ 2.7 V at boot (no `config.txt` pull-up yet). Reboot once after setup (§15.1).

---

## 20. Where the code and the CAD disagree

Re-checked against the repo on 12 Nov 2026 for release 2.3.1 (after commits 93c6986, 2e8712f, 30cd027, 2149c5b and b028645). Every row of the 2.1.0 list was closed in 2.2.0, and **every row left open in 2.2.0 is now fixed** in the code or the CAD:

| # (2.2.0) | Where | Closed by |
|---|---|---|
| 1 | `hardware/elevator.py` docstring said the ULN2003 runs from Reg #1 | now "5 V motor rail (Reg #3, D36V28F5)" (93c6986) |
| 2 | `hardware/vacuum.py` docstring had the flyback diode the wrong way round for this wiring | now cathode (stripe) to the device's + terminal, anode to its − (GND) (93c6986) |
| 3 | `cad/*.scad` fastening notes said "washer + nut under the board" | every part file now says board tee-nuts, with washer + nut as the fallback (2149c5b) |
| 4 | the tilt shaft was called the "D-shaft" in the CAD and code | renamed to the REX shaft everywhere (`rex_shaft()`, `sg_rex_shaft_y()`, `rex_bore()`; 93c6986). "D-shaft" is left only for the conveyor rods and the N20 output shaft, which really are D-shafts |
| 5 | `web/app.py` docstring said the token is printed | now: generated on first use, never printed; `main.py --web-token` shows it (93c6986) |
| 6 | `config/identify.json` was not validated (a bad value only warned) | validated like `machine.json`, exit 78 (93c6986; §16.8) |
| 7 | `scripts/setup.sh` "next steps" listed calibration before the reboot | reboot first, then stop the service, build the DB and calibrate in the §16 order (93c6986) |

Found in the 2.3.0 pass; both are now closed:

| # | Where | Disagreement | This guide |
|---|---|---|---|
| 1 | `cad/shuttle.scad`, tilt-frame comment above `tf_bot` | Said the bed plane is "≈ 1480 mm²" (the part measures 1420.7 mm²). **Closed in 7ec74e2:** the comment now says ≈ 1420. | ≈ 1420 mm² (§2, BOM). |
| 2 | `scripts/test_hardware.py` | A bad `config/machine.json` stopped it with exit status 1, a bad calibration file with 78. **Closed in b028645:** every tool and `main.py` now exit 78 on any config error (also a lock / `data/` they can't open). | §15.2: every config error exits 78. |
