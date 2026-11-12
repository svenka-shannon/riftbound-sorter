# Changelog

All notable changes to the Riftbound Card Sorter are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [2.3.2] — 2026-11-12 — code round 5: calibration windows vs servo gain (branch `audit-fixes`)

Fixes from the fifth (confirmation) audit. The 2.3.1 windows were too tight for real MG996R gain variance, and the documented arm crank fit added a 3° bias.

### Changed: software and safety
- **Arm crank fit (MJ-A):** fit the crank at servo 90° pointing **3° past vertical toward the hopper (93°**, the CAD `th_mid`), not straight up. Use the **25T spline × 4 horn slots (3.6° lattice)** so it is always within **1.8°**. Following the 2.3.1 docs (vertical, nearest tooth ±7.2°), only 87 % / 56 % / 35 % of builds passed at +5 / +8 / +10 % servo gain, and about 30 % needed PICK > 180 or DROP < 0 even at 0 %.
- **Arm windows widened toward PARK only:** PICK **155–180** (mirror 0–25), DROP **0–25** (mirror 155–180), PARK 80–100. New **symmetry rule** |(PICK − PARK) − (PARK − DROP)| ≤ 10°; PICK 157 for 175 still fails (by 18°). With the new fit every build the servo can reach passes for gain −10 … +10 % (model in `tests/test_audit5_fixes.py`). A 180° servo must turn ≥ 87° each side of 90° (reachable down to about −3.5 % gain).
- **Carriage (MJ-B):** ch2 window **±12°** (was ±8°, which failed 7 % of builds at 8 % gain). New gap rule **column 2 − column 3 ≥ 12°** (nominal 20.2°). The ≥ 5° neighbour rule and the order stay; col3 54, col2 56.2, col1 78.3, home 57.5 and reject 20 are still refused. Tilt (ch1) stays ±8°.
- **ch1 coupler residual is ≤ 1.2°**, not 0.6° (25T × hex = 2.4° lattice).
- **`calibrate_servos.py` jog (minor 3):** clamped to each pose's own window only. The rules between poses (order, gaps, arm side and symmetry) are checked at save. A pose that only waits for a later pose in the same menu is **held** and written with it, so a build 7–8° off everywhere calibrates in one pass. Anything still held at the end of the menu (or at `q`) is not saved, with a message.
- **Bin counts file (minor 2):** written mode **0644** and, run as root, given to `data/`'s owner (as are new `.lock` files). An unreadable or corrupt `data/bin_counts.json` at start-up is refused with **exit 78** and the fix, instead of starting every bin at 0 (which would overfill bins). `instance.data_dir_problems()` covers `bin_counts.json` and its `.lock`. `--empty-bin` / `--empty-all` / `--confirm-clear` with an unwritable `data/` exit 78 with the message, never a traceback.
- **`config_txt_line.py` (minor 4):** a missing `--file`, a directory, a non-UTF-8 file or an unwritable one gives a one-line error (exit 1, nothing changed), not a traceback.

### Changed: build procedure
- **ch2 crank set by eye, not by a spline tooth (§13.5).** Until now the crank was screwed to the round horn on the bench and the pair was then pressed onto the spline at home 75.5°. That leaves the crank up to **±7.2°** off (half a 14.4° tooth). At reject (ψ 0, a dead centre) that is up to ≈ 3.3 mm of carriage error against a reject box 3 mm wider than the card, and the tool can't trim past reject 2°. Column 0, at the other dead centre, moves only ≈ 0.3 mm.
  - The crank holds the disc only by 4 M2 self-tappers cut into plain plastic (`c2_horn_holes`), so its angle on the disc is free.
  - New order: direction check; the bare horn pressed onto the spline; ch2 held at **ψ 90** (menu 3, column 1 jogged to 90.0°, not saved).
  - The crank is centred by starting the M3 × 12 hub screw and lined up with a **paper gauge**: a line traced square to the servo case's long sides, s ≈ 10.2 mm from its spline-end face. The tip journal (Ø4.1, 139 mm out) must sit over the line within 1 mm (0.4°; 2.4 mm = 1°).
  - Only then are the 4 self-tappers driven, then the hub screw tightened.
  - ψ 90 is mid-travel, so the servo's gain error splits between the two ends. A ψ 178 reference would put it all on the sensitive reject end: ≈ 4.6 mm there at −5 % gain, against ≈ 1.6 mm.
- **ch2 square check on the machine (§13.6 step 6).** The M2.5 ear screws in the MG996R's Ø4.5+ tab holes let the case twist up to ≈ ±2°. With the module bolted down, command ψ 90 again and measure from the riser's front face (Y −113) to the far edge of the crank's tip boss: **17 mm**, 2.4 mm per degree. If it is out, re-seat the case in its tab holes.
- **DS3218MG-270 recommended for ch0 and ch2** (was a fallback): ≈ $15.59 each, ≈ $31 for the two, not in the totals. Set `ARM_ACTUATION_RANGE` 270 and `"actuation_range": {"2": 270}` before fitting, then fit at the commanded pose. On ch2, keep the MG996R's round plastic horn. The MG996R stays the baseline and the bench travel test decides.
- **Centring offset for 270° servos** (arm and both shuttle channels). Until now 0° was 500 µs on either range, so on a DS3218MG-270 the arm's DROP end and ch2's reject end still sat at the pulse limit, and the servo had to turn ≈ 261° over 500–2500 µs (some are reported at ≈ 255°).
  - The PWM now gets angle + offset, with offset = (actuation_range − 180) / 2: **45° for 270, 0 for 180**. With `invert` it gets range − offset − angle.
  - Geometric 0 / 90 / 180° are now **833 / 1500 / 2167 µs** on a 270° servo, so both ends keep 45° of servo travel spare. A 180° servo is unchanged.
  - The offset is derived from the range, not a config key. It is applied only at the PWM write (`servos.arm_pwm_angle` / `arm_pulse_us`, `shuttle.pwm_angle` / `pulse_us`, which `calibrate_servos.py` shows in its readout).
  - Every stored, nominal and tracked angle stays geometric, and so do the windows and the rules between poses. 90° is 1500 µs on either servo, so the builder still commands PARK 90° / ψ 90 and fits the crank there; the offset is invisible to them.
  - A geometric angle may now be anything the servo can be commanded to: 0–180°, or −45–225° on a 270° servo (was 0–270). The windows are clipped to that reach, so on a 270° servo arm PICK may go to 185°, DROP to −5°, ch2 reject to −10° and column 0 to 190°.
  - `calibrate_servos.py` menu 3 stops the carriage 2° inside the reach: 2–178° on a 180° servo as before; on a 270° servo the ±12° windows are the limit.
- **Bare-servo travel test** (`calibrate_servos.py` menu **`t`**, ch0 / ch1 / ch2). §19.1 said to command 0°, 90° and 180°, but menu 3 clamps ch2 to 2–178°.
  - It asks the same "is it bare?" question as `d`. It is refused once the arm or the shuttle has been homed in the session.
  - The servo goes straight to 90°, then ramps slowly to 0°, 180° and back. The builder marks the horn at each stop and types in the two measured sides.
  - The tool reports them against what is needed: arm ≥ 87° each side (174°); ch2 ≥ 88° each side (176°); ch1 56.5° / 30.2° (nominal tilt range plus its ±8° window, 86.7°).
  - On a 270° servo, a short side passes if the command that would reach it is inside the calibration limits. For example, a ≈ 255° DS3218 (≈ 85° each side) passes on both channels.
- **ch2 crank M2 holes Ø2.0 → Ø2.2 clearance** (`cad/shuttle.scad` `c2_crank`, countersinks kept). The self-tappers now thread only into the horn disc, so they pull the crank tight onto it instead of threading into both parts.
  - `c2_crank` re-exported: watertight, one body.
  - `cad/shuttle_check.py all` passes.
  - The install-order comment (step 3) now gives the §13.5 order: bare horn, ψ 90, hub screw started, tip journal on the paper-gauge line, self-tappers, then hub screw tightened.

### Documentation
- `docs/ASSEMBLY.md`:
  - §11 step 3: 93° crank fit, tooth × slot lattice, the 6-teeth / one-slot 3.6° step, judging with an angle gauge, plumb line or paper gauge. §11 check: PARK at 93°.
  - §13.3 step 3 and §13.4 step 4: coupler ≤ 1.2°.
  - §16 jog notes: per-pose clamp, rules at save, held poses.
  - §16.2: PARK advice, new arm windows, symmetry rule and why, DS3218 note.
  - §16.4: residual 1.2°, carriage ±12° and why, column 2 − 3 gap.
  - §18: config row, and the jog row split into "won't jog further" and "HELD / NOT saved".
  - §13.5 rewritten (case orientation, why not a spline tooth, paper gauge, horn on first, ψ 90, self-tappers then hub screw); §13.6 step 6 square check.
  - §16 jog note, §16.4 (`actuation_range` set before fitting; the ch2 window rationale now that the crank is within ~1°), §18 "won't jog" row: ch2 points at the ψ 90 fit, not a spline tooth.
  - §16.2 / §16.4: DS3218MG-270 is the recommended upgrade, not a fallback.
  - §19.1 item 1: ≥ 87° each side of 90°; ch2 ≥ 88° each side (reject is the sensitive end); the DS3218MG-270 recommendation (price, link, configuration, the ch2 horn, why it still needs the travel test). Item 9: 1.2°.
  - Centring offset and travel test:
    - §14.3: new 270° bullet (offset, 833 / 1500 / 2167 µs, nothing to set).
    - §16: menu `t`, the travel-test note, and the jog windows clipped to the servo's reach.
    - §16.2 / §16.4: angles stay geometric; fit at the commanded pose with the offset invisible; `invert` writes range − offset − angle; validation range 0–180 / −45–225.
    - §19.1 item 1: the test uses menu `t`; the DS3218's ends are 45° inside the pulse limits; a ≈ 255° unit can still pass.
    - §11 "Test first" points at menu `t`; §13.5 step 1 notes the offset.
  - §3 hole list and §13.5 step 5: crank M2 holes are Ø2.2 clearance.
- `BOM.md`: new **Upgrade** table under Optional cost-down (2 × DS3218MG-270, ≈ $31, not in the totals), a pointer from Totals and from the MG996R row. The row is gone from Optional / fallback, whose subtotal is now $35.
- `README.md`: calibration windows and rules, held saves, 93° fit, ch2 crank by eye at ψ 90, the DS3218MG-270 recommendation, unreadable bin counts and exit 78. Also: travel test (menu `t`), the centring offset with geometric angles and their range, and the Ø2.2 crank clearance holes.
- Tests: `tests/test_centring_offset.py`, new, covers these cases:
  - 180 vs 270 mapping, with and without invert, at both ends, for ch0 / ch1 / ch2.
  - Every pulse of an arm cycle and a full sort cycle is within 500–2500 µs, and on 270 at least 333 µs inside both limits.
  - The rest-pose write in `init()`.
  - Windows and validation on 270.
  - The calibrate readout and jog limits.
  - The travel test: sweep, refusals, verdicts, bad input.

  `tests/test_shuttle_invert.py`, `test_audit_fixes.py` and `test_audit4_fixes.py` are updated for the offset and the reach.

---

## [2.3.1] — 2026-11-12 — code round 4 (branch `audit-fixes`)

Fixes from the fourth code audit (commit b028645). Docs: `BOM.md`, `docs/ASSEMBLY.md`, `README.md`, `docs/wiring_diagram.svg`, `riftbound_sorter.kicad_sch` updated to match; every detail 2.3.0 left open for code round 4 is resolved.

### Changed: software and safety
- **Tight calibration windows** (2.3.0: ±25°): arm **±10°** round its nominal pose or its mirror (PICK 165–180 / 0–15, DROP 0–15 / 165–180, PARK 80–100); tilt and carriage **±8°** round nominal. Tilt poses must be in order lower < level < hold < upper with **hold − level 2–8°**, **upper − hold ≥ 8°**, **level − lower ≥ 30°**; carriage stops **≥ 5° apart**. Swapped-digit typos and two poses typed into each other's place are now refused. `calibrate_servos.py` clamps its jog to exactly what the sorter accepts (`shuttle.allowed_range()`).
- **A card the arm couldn't carry is never parked.** The arm stays where the failed carry left it, powered, the pump holding the card, for at most `CUP_HOLD_MAX_S` (600 s). When that runs out, or the service stops (teardown now lets go *before* the arm goes limp), the card falls from that pose, and the web UI says where: within 10° of PICK back onto the stack (≤ 7 mm), within 40° of DROP flat onto the belt (3 mm at DROP, ≤ 39 mm at 40°), anywhere else (PARK included) across the hopper rim / belt inlet from 12–55 mm, possibly bent. Within 2° of PICK it is released onto the stack at once, as before.
- **Idle release is ch1 only:** at rest with no card in the machine, only the tilt servo is switched off (no stall against the home ledges); the arm (parked) and carriage (home) keep holding while you work in the machine. With a card anywhere in the machine nothing is switched off.
- **`main.py --calibrate` marks the machine not clean** ("tool ran: main.py --calibrate"), like the hardware tools: the next start asks for Machine clear.
- **Root-owned lock / `data/`** (a tool or `main.py` run with `sudo`): refused with the file named and the fix (`sudo chown -R <user>: data`), exit 78, so systemd does not restart-loop. A tool run as root anyway gives the files it creates to the owner of `data/`. `setup.sh` now `chown -R`s `cache/`, `data/` and `config/` to the service user.
- **Exit 78 for every config error in every tool** (`test_hardware.py`, `calibrate_servos.py`, `calibrate_camera.py`) as in `main.py`: `machine.json` (was exit 1 in `test_hardware.py`), calibration files, unreadable files, lock / `data/` permissions.
- **Upper-floor bin cap 24 → 15** (≈ 5 mm; the slide simulation already calls an 8 mm pile SHORT). Example in the error message: `{"0": 45, "4": 14}`.
- **Bin counts are fsynced** (file and directory) so a power cut never loses a count or leaves a 0-byte file.
- **Boot pull-up on the relay inputs:** `setup.sh` adds `gpio=17,27=ip,pu` to `config.txt` (new `scripts/config_txt_line.py`: idempotent, own `[all]` section, `.riftbound.bak` copy, durable write). After a reboot the firmware pulls GPIO 17 / 27 up a few seconds after power-on (IN ≈ 3.3 V instead of ≈ 2.7 V); the ≈ 2.7 V bench test still covers the first seconds. Check: `pinctrl get 17,27` shows `pu`.

### Documentation
- `docs/ASSEMBLY.md`: §14.1 boot pull-up, `pinctrl` check and the 4.7 kΩ alternative (≈ 3.0 V from reset); §14.2, §14.8 boot row and safe-state test; §14.3 / §14.8 / §15.3 / §15.4 idle release ch1 only; §14.8 / §15.4 / §16.6 / §18 held-card landing zones and expiry; §15.1 `config.txt` line, `chown`, reboot check; §15.2 `--calibrate` marks unclean, every tool exit 78, `sudo chown -R <user>: data` or re-run setup; §16.1; §16.2 / §16.4 / §16 jog notes: ±10° / ±8° windows and gap rules; §16.7 upper cap 15; §18 new lock / permission row and jog-limit row; §19 relay item, servo item, reboot item; §20 both 2.3.0 rows closed.
- `README.md`: upper cap 15, setup adds the `config.txt` line and chowns, `chown -R` fix and exit 78, calibration windows, held card, idle ch1 only, `--calibrate` asks for Machine clear.
- `BOM.md`: 4.7 kΩ alternative, boot pull-up in "Why the pull-ups".
- `docs/wiring_diagram.svg`, `riftbound_sorter.kicad_sch`: relay note gains the `config.txt` boot pull-up (with the `pinctrl` check) and the 4.7 kΩ alternative.

---

## [2.3.0] — 2026-11-12 — fourth CAD / code round (branch `audit-fixes`)

Fixes from the third independent audits (commits 93c6986 REX naming / identify.json / setup order, 2e8712f tilt crank and all-pairs shuttle checker, 30cd027 code round 3, 2149c5b CAD round 4). Docs: `BOM.md`, `docs/ASSEMBLY.md`, `README.md`, `docs/wiring_diagram.svg`, `riftbound_sorter.kicad_sch` updated to match. A few details were still changing in code round 4 (idle servo release, cup-hold expiry, upper bin-limit cap, a boot pull-up line); they are resolved in 2.3.1.

### Changed: shuttle
- **Tilt crank really fits the sled.** The crank hub overlapped solid sled material in every pose (the old checker never compared parts inside one moving group). The sled's crank pocket is now the crank's swept outline + 0.7 mm with a front insertion channel and 45° roofs; the crank arm has a straight lower edge that clears the +Y LM8UU; the tilt frame's link slot follows the link's real swing, with a bridge block tying the crossbar halves (bed plane ≈ 1420 mm²). **New install step:** crank + link joined on the bench, crank pointing +X, slid hub-first along −X into the pocket before the tilt frame and cheeks (ASSEMBLY.md §13.2).
- `cad/shuttle_check.py` now tests **every part pair in every pose**, with LM8UUs, 688ZZs, dowels, screws and the crank–link pivot modelled; the only allowed overlaps are an explicit, capped, commented whitelist.
- **Rod set screws** are M3 × 8 flat point in a 2 mm boss on each end post's +X face (insert pocket 2.3 mm from the rod bore). **ch2 rear ear:** two Ø6 bosses on the shelf give the M2.5 screws ≈ 5.6 mm of thread.
- **Shared MG996R tab pattern** 49.5 × 10 (`cad/machine_frame.scad`) for the arm head, ch1 cage (ear holes now Z 29.4 / 78.9) and ch2 ears (Y −109.4 / −158.9). Measure your servos.
- The tilt shaft is called the REX shaft everywhere in the CAD and code.

### Changed: other CAD
- **Pick arm:** the bellows pad rode into the guide-screw heads at every pick (hidden by a blanket checker exclusion). Guide screws moved to X ±14.5 (1.25 mm clear at any compression); hand beams and cup sled widened; `pick_arm_check.py` checks hand against sled with a specific whitelist. Servo-tab screws **M3 × 8** (an M3 × 10 bottomed out in the 6.2 mm insert hole). The head's plate runs down to the head floor, so the print has no 9.7 mm overhang.
- **Screw lengths:** electronics tray **4 × M3 × 18** SHCS; sorting-tray lower floor and reject bin **12 × M3 × 18** countersunk (were M3 × 20: those poked 7.5 mm out below the board). Every part file now says board tee-nuts, washer + nut as the fallback.
- **Hopper:** a square through-slot replaces the knife-edge flaps where the T8 pocket broke out of the carriage faces; the home-switch lug's underside is one 45° ramp; cap coupler hole Ø22.6.
- Card guides export watertight (flare seam and chamfer fixed); 45° fixes on the sled's ch2 arm.
- Volumes re-measured: arm head 50.8, hand 20.0, cup sled 6.2, end posts 49.1 / 18.6, shuttle sled 64.6, tilt frame 19.6, tilt crank 1.7, hopper cap 13.9 cm³ (net +2 cm³; filament unchanged).

### Changed: software and safety
- **Strict calibration files:** `config/shuttle_calibration.json` and `config/servo_calibration.json` are validated like `machine.json`: known keys only, finite numbers within the servo range **and within a sanity window round the nominal pose** (arm: or its mirror, 180° − nominal; tightened to ±10° / ±8° in 2.3.1), pose order (tilt lower < level, hold < upper; carriage reject < 3 < 2 < home < 1 < 0; arm PICK and DROP either side of PARK), timings ≥ 0, `actuation_range` 180 or 270. `calibrate_servos.py` refuses to save a value that would make a file invalid.
- **`config/identify.json`** validated the same way (exit 78 instead of a warning).
- **`config/bin_limits.json`** validated: whole numbers from 1 to a geometric cap per bin; anything else exits 78.
- **Exit 78** (not restarted by systemd) now covers all five files: `machine.json`, `identify.json`, `shuttle_calibration.json`, `servo_calibration.json`, `bin_limits.json`.
- **Tools mark the machine unclean:** `test_hardware.py`, `calibrate_servos.py` and `calibrate_camera.py` take the sorter's lock (they refuse while the sorter or another tool runs, and vice versa) and record the machine as not clean before anything moves, so the next start asks for Machine clear. The state file is written atomically and fsynced; `cmdline_param.py` writes `cmdline.txt` durably.
- **Top switch must be NC:** `TOP_SWITCH_NC: false` is refused (exit 78). A capped raise without a trip near the top limit now means "hopper empty", lower down "top switch not detected". A mechanically stuck NC switch on the first raise after homing remains undetectable (listed as a residual risk).
- **Start-up** records the machine unclean before it moves anything. A Stop while a card waits on the cradle for a full bin ends in `needs_confirm`, not `stopped`.
- **Idle servos off:** while the sorter idles at rest the servos are switched off (no stall against the home ledges; 2.3.1: only ch1, the arm and carriage keep holding) and the rest pose is re-asserted with one write each before the next move.
- **Cup hold:** a card the arm could not carry to the belt is held with the pump on for at most `CUP_HOLD_MAX_S` (new `sort` key, default 600 s, 10–3600), then the pump lets go and the card drops (2.3.1: from wherever the arm stopped, never parked; the web UI says where); the web UI says "card held on cup — remove it by hand before stopping the service".
- `setup.sh` "next steps": reboot first, then stop the service, build the DB and calibrate in the guide's order. Docstrings fixed (`elevator.py` Reg #3, `vacuum.py` diode direction, `web/app.py` token).

### Documentation
- `BOM.md`: fastener table recounted from the round-4 BOM footers (M3 × 20 SHCS 29 → 25, M3 × 20 countersunk 16 → 4, + 4 M3 × 18 SHCS, + 12 M3 × 18 countersunk, arm tabs M3 × 8, rod set screws M3 × 8, M3 × 10 24 → 20); + M3 × 18 packs $7; totals: still to buy ≈ $645, whole machine ≈ $832, cost-down ≈ $585 / ≈ $531; printed-part volumes re-measured.
- `docs/ASSEMBLY.md`: §13.2 crank insertion order; inserts, screw lengths and coordinates from CAD round 4; tee-nut screw-tip rule (4–7 mm below the board); shared MG996R pattern; relay bench check also at the ≈ 2.7 V boot level; top switch NC only; tool interlock and "never run the tools with sudo"; every calibration file's validation; bin-limit caps; `CUP_HOLD_MAX_S`; new test-first items (MG996R pattern, 20-dump column test with ≈ ±0.95 mm allowed, ≤ 3 N tilt-crank drag test with dry PTFE lube, stuck NC top switch); §20: all seven 2.2.0 rows closed, two minor new ones listed.
- `docs/wiring_diagram.svg`, `riftbound_sorter.kicad_sch`: top switch NC only; relay bench check at 3.3 V and ≈ 2.7 V.

---

## [2.2.0] — 2026-11-12 — third CAD / code round (branch `audit-fixes`)

Fixes for the second independent code and CAD re-audits (commits f274d7f CAD round 3, 0be14a0 code round 2, 2e5a3a0 shuttle round 3, 4261e75 servo invert + direction check). Docs: `BOM.md`, `docs/ASSEMBLY.md`, `README.md`, `docs/wiring_diagram.svg`, `riftbound_sorter.kicad_sch` updated to match; every section that 2.1.0 left marked as pending is resolved.

### Changed: shuttle
- **ch1 drive:** the 8 mm D-shaft, disc horn and flange coupling (which could not actually couple to the servo) are replaced by a **goBILDA 8 mm REX shaft** (2106-4008-4320, cut to 417 mm) and a **goBILDA 4001-0025-4008 clamping servo-to-shaft coupler** (25T → REX). The coupler is indexed at HOLD (hex flats 7° up from +X, ≤ 0.6° residual) and clamped with its M4 screw from above. The ch1 servo moved 17 mm −Y (case face Y −185), mounted long side up; its ears are held by 4 × M3 × 10 + washers driven from behind into 4 inserts in the −Y end post's cage. The tilt crank has a REX bore.
- **ch2 front ear:** a solid block over the riser B ear pocket with a 1 mm lead-in; ear screws are M2.5 × 10 button heads driven from below with a 1.5 mm L-key.
- **Install order** rewritten and verified step by step by `cad/shuttle_check.py assembly` (steps 0–7): ch1 + coupler on the bench, module on the bench, ch2 hung on the bench, module set down 10 mm short and slid +Y, front-ear screws through the tunnel, end-post anchors (one under the rod needs a ball-end key), ch2 link, ramp and reject bin.
- **Rod** held by M3 × 6 flat-point set screws in inserts in each end post's +X face (the old top clamp screws were blind). Rod now Y −160..240.
- −Y end-post holes moved to (110, −225), (140, −195), (140, −165).
- **Tilt frame and sled print without supports**; `end_post_neg` exports with a break-away ladder under the ch2 rear-ear ledge; `part="carriage"` now stops with an error (print `sled` + `cheek_neg` + `cheek_pos`; `carriage_preview` to look).
- **ch2 (and ch1) direction:** `config/shuttle_calibration.json` gains `"invert": {"1": false, "2": false}` (an inverted channel gets `actuation_range − angle`; stored angles stay geometric), and `scripts/calibrate_servos.py` gains a bare-servo **direction check** (menu `d`, offered before ch1 / ch2 calibration) that sets it. A bad `invert` or unreadable calibration file refuses to start (exit 78).

### Changed: other CAD
- **Board tee-nuts:** 49 M3 four-prong tee-nuts in the 6 mm board (drilled Ø3.4 through the tiles, opened to Ø4.5 from below, tapped in before assembly); every baseplate screw goes in from above; tiles have Ø5.2 × 1.5 underside counterbores; rubber feet ≥ 10 mm.
- **Vent valve:** printed valve clip on grid holes (−180, −255), (−150, −255) for a 12 V NC mini valve (uxcell reference, 0.2 A); 1/8" barbed tee in the tube 18 mm past the pump; 20 mm 2 × 4 silicone branch. Modelled in `assembly.scad`.
- **Pump bracket:** head cradle with a TPU / neoprene pad under the pump head; base bolted down before the pump.
- **Hopper:** T8 nut mounted flange-down in a pocket, 2 × M3 × 14 into inserts pressed into the carriage bottom (the old inserts beside the bore left 0.6 mm of wall); rods 19.5 mm proud of the cap; cap top Z ≈ 135, motor top Z ≈ 154.
- **Riser:** no slivers where the tunnel cuts ribs; tie insert depth 5.7.
- **Load-cell lead** modelled (`asm_cell_lead`): rolling loop under the carriage, fixed from Y 205 on the +Y side; column 0 needs ≈ 30 mm more slack.
- Scanner hood: brim required. Diagonal card-play cases in `pick_arm_check.py` (all ≥ 0.49 mm). Headers and video captions corrected.

### Changed: software and safety
- **Dependencies locked:** `requirements.lock` (exact versions + sha256, same for Python 3.11 and 3.13), installed with `pip --no-deps --require-hashes`; Blinka held below 10.
- **Outputs safe after any exit:** kernel parameter `pinctrl_bcm2835.persist_gpio_outputs=0` (setup.sh, `scripts/cmdline_param.py`, needs a reboot) and `ExecStopPost=scripts/safe_outputs.py` (pins safe, PCA9685 off and asleep). setup.sh makes sure `pinctrl` is installed.
- **systemd watchdog** `WatchdogSec=60` (main loop pings via sd_notify); `RestartPreventExitStatus=78`.
- **`config/machine.json` validated** (`hardware/machine_config.py` SCHEMA): types, ranges, enums, unknown sections / keys, NaN / Infinity, `EXIT_MIN_S ≤ EXIT_MAX_S`; any problem refuses to start with exit 78. New keys: `elevator` (`TOP_SWITCH_NC`, `BOTTOM_SWITCH_NC`, `RAISE_CAP_MM`, `UP_DIRECTION`, `TRIP_EXTRA_STEPS`, `HOME_BACKOFF_MM`), `servos.ARM_ACTUATION_RANGE`, `card_detect.FRAME_TIMEOUT_S`, `camera.LORES_TIMEOUT_S`.
- **Hopper switches wired normally closed** (C → GND, NC → GPIO 12 / 13): a broken wire reads "pressed". Every raise after the first since homing is capped at 3 mm.
- **Safe restart rules:** state `starting` before anything moves; after an unclean stop nothing on ch0–ch2 is commanded until **Machine clear**; after a clean stop the limp servos get one write each (a small snap). Teardown parks the arm, brings a tipped cradle to HOLD and leaves every servo limp. A second stop signal during a cup carry waits until the card is down.
- **Load cell:** the empty-cradle reference is only stored by `--calibrate` or by an anchored tare after a card provably left, within 0.8 g of the calibration baseline; the cradle is checked against it at every start, also after Machine clear; a reading below it is a fault. Raw −1 / rail / implausible readings are rejected (vendored HX711 timeout fix).
- **Operator flow:** every web / CLI control gated by state (409 with the reason); Machine clear never while paused or starting; Pause during a bin-full wait needs an explicit Resume; single instance (`data/sorter.lock`); the CLI goes through the running sorter's web API; the token is never printed to the journal.
- **Camera stall:** grabs time out and a watchdog thread brakes the belt (camera fault).
- **Identification:** an ambiguous pHash is never overridden by ahash / dhash; sorting is refused while more than 1 % of the card list is missing from the hash DB; `config/identify.json` keys documented.
- L9110S stop and brake are the same (all inputs LOW, reverse never driven). Test banners now match the menu numbers (1–11).

### Documentation
- `BOM.md`: goBILDA shaft and coupler (D-shaft, second horn, flange coupling removed), tee-nuts, insert top-up (50 inserts), M3 × 14, M3 × 10 + washers for the ch1 ears, M2.5 × 10 button heads for the ch2 ears, rod set screws, valve + 1/8" tee + silicone branch, pump head pad; fastener table recounted; printed-part table (supports, ladder, brim, carriage selector) and volumes re-measured; totals: still to buy ≈ $638, whole machine ≈ $825, cost-down ≈ $578 / ≈ $524.
- `docs/ASSEMBLY.md`: tee-nut baseplate procedure; every baseplate screw from above; §13 rewritten in the verified install order; NC switch wiring and `*_SWITCH_NC`; vent valve, tee and pump-bracket steps; load-cell loop from the CAD; safe state, setup (lock file, `pinctrl`, kernel parameter + reboot, `ExecStopPost`, watchdog), every `machine.json` key with its range, `shuttle_calibration.json` and `identify.json`; states and operator controls; load-cell reference rule; troubleshooting; a "test first on the real machine" list; the code / CAD disagreement list re-verified (all 2.1.0 rows closed).
- `docs/wiring_diagram.svg`, `riftbound_sorter.kicad_sch`: NC hopper switches, flyback diodes on both coils, safe-output layers.

---

## [2.1.0] — 2026-11-12 — second audit round (branch `audit-fixes`)

Independent code/electrical and CAD audits of 2.0.0, and their fixes (commits ebffbf3, cdbe457, d08117b, 36f80ba, plus the build-order fix 8eae932). Docs: `BOM.md`, `docs/ASSEMBLY.md`, `README.md`, `docs/wiring_diagram.svg`, `riftbound_sorter.kicad_sch` updated to match. Some details were still changing in a further code and CAD round; those doc sections were marked as pending and are resolved in 2.2.0.

### Added
- **Vent valve.** A 12 V normally-closed mini solenoid valve, teed into the vacuum line, on relay channel 2 (GPIO 27, header pin 13, 10 kΩ pull-up to 3.3 V, flyback diode across the coil). `vacuum.release()` = pump off, vent open 0.4 s, vent closed; the arm then lifts the first ~10° slowly. The relay is now a **2-channel** 5 V active-LOW module. Docs include a bench check that the relay switches off at 3.3 V logic. New test 3 in `test_hardware.py`.
- **Pump bracket** (`cad/pump_bracket.scad`): base, cap and a TPU isolation sleeve (or a 1.5 mm neoprene strip), on 4 grid holes at the front-left. The vacuum tube now starts at the pump nozzle.
- **Baseplate keys:** 24 printed bow-tie keys lock the tile seams (the old edge pins could never engage).
- **`config/machine.json`** (`hardware/machine_config.py`, example in `config/machine.example.json`): belt-centring constants, camera focus/exposure/rotation, exit run, arm lift and calibration mass are per-machine settings instead of code edits.
- **Web UI controls:** Pause, Resume, Stop and **Machine clear**, all behind a token stored in `config/web.json` (`main.py --web-token`). Bins can only be reset while the machine is paused or stopped (or the bin it is paused on).
- **Start-up / shutdown safety.** The first start, or any start after an unclean stop, needs `--confirm-clear` or the web confirmation (`data/machine_state.json`). The sorter refuses to start with a card on the cradle (raw reading against the stored empty-cradle reference, before taring). The first stop signal finishes the current card; a second stops at once. Shutdown leaves the shuttle where it is, with its servos limp.
- `RIFTBOUND_WEB_PORT`; offline card-cache fallback.
- **BOM "Optional cost-down"** section: drill the board from a printed template instead of printing tiles, fixed-output buck modules from quality brands instead of Pololu, and smaller options, each with its trade-off.

### Changed: software and electrical
- **HX711:** the gandalf15 library is vendored (`hardware/vendor/hx711.py`); the PyPI `hx711` package is a different library. Weights are the median of 7 reads; failed reads are retried.
- **Camera:** forced into the IMX708's 2304 × 1296 full-field binned mode at 50 fps (picamera2 otherwise picked a 2/3 crop), fixed focus at `LensPosition` 10, AE/AWB locked after warm-up, sensor mode read back and checked.
- **Load-cell calibration** (`main.py --calibrate`) uses a 5.000 g US nickel (or `--mass G`) instead of an assumed card weight, and stores the empty-cradle reference.
- **Belt exit** runs a distance (144 mm) at the belt speed measured during centring; the card must weigh in fully on the level cradle before it is tipped.
- **Bin limits** lowered to 40 (lower floor) / 12 (upper floor) / 35 (reject), from the slide simulation. Raise them in `config/bin_limits.json` after testing.
- **Tilt level** default 93.1° (0.5° preload onto the home ledges). ch2 servo actuation range is configurable (`"actuation_range"` in `shuttle_calibration.json`) for a DS3218MG-270 fallback.
- **setup.sh:** Bookworm and trixie; apt `python3-picamera2`, `python3-libcamera`, `python3-rpi-lgpio`, numpy/scipy/Pillow, `libtiff6`; venv with `--system-site-packages` (re-created if not); prints the web token.
- Elevator raise timeout scales with the remaining travel; the L9110S stop never leaves a reverse input high; the PCA9685 is switched fully off before release; the shuttle never moves with the tilt unknown or after a jam until cleared.

### Changed: CAD
- **Electronics tray** 185 × 150 (was 185 × 125), X −150..35, Y 80..230, bolted to **real grid holes**, with posts or blocks for every board (16 × M2.5 and 6 × M2 self-tapping), the PCA9685 on its real 55.9 × 19.05 pattern, the 2-channel relay, and the barrel-jack hole (Ø8.2, +Y wall). The Pi moved to the +X end, closer to the camera ribbon.
- **Harness** now enters the tray through the −X wall slots (≈ 0.8 m trunk from the riser front).
- **Hopper:** lift relief (cavity steps out 1.0 mm on +X, 0.5 mm elsewhere, from just below the top card), 0.8 mm rim chamfer, r 1.2 corner reliefs. A card lying 1.5 mm off-centre now clears the hopper by ≥ 0.49 mm during the lift.
- **Arm tower:** M3 × 20 through a 6 mm board; zip-tie tunnels at Z 55 / 80.
- **Rails:** card-guide groove 1.8 mm deep, leaving a 1.2 mm top fin; the hood stands on the fins. Through-feet M3 × 80 or threaded rod; insert feet M3 × 10 (M3 × 16 under the camera bracket).
- **Riser:** joint 3 × M3 × 12 plus a front tie (2 × M3 × 10 countersunk into inserts); anchors M3 × 20; ch2 front-ear pocket at Z 25..37.
- **Shuttle:** carriage split into a **sled + 2 cheeks** (fit pin A before the cheeks); tilt pin A is a Ø3 × 20 dowel pushed in from outside; ch2 stack raised 5 mm, with 4 mm shoulder screws dropped in from above into M3 × 4 inserts in the link, the horn on 4 × M2 × 6 countersunk and an M3 × 12 countersunk hub screw (fitted on the bench); the tilt crank has no set screw (it slides on the D-flat); R-bar 9 wide with an M3 × 10 splice at Y ±10; end posts 3 × M3 × 20 each on the grid; ch1 servo on 4 ear screws; support-free cradle (rib plane) and carriage.
- **Lower ramp** prints upright; roller grooves have 45° flanks (support-free).
- Every printed part exports watertight.

### Documentation
- `BOM.md`: new and changed parts, fastener table recounted from the SCAD BOM footers (44 heat-set inserts), printed-part volumes re-measured (≈ 4.0 kg), power budget with the vent valve and second relay coil, totals (still to buy ≈ $609, whole machine ≈ $796), optional cost-down section.
- `docs/ASSEMBLY.md`: rewritten steps for the tray, riser, rails, hopper, arm, shuttle (sled + cheeks, F-pin and pin-A order, ch2 bench fitting), pump bracket and vent valve; GPIO 27; software setup, web UI, start-up/shutdown and `config/machine.json` calibration; known-issue list re-verified.

---

## [2.0.0] — 2026-11-11 — v2 redesign (branch `audit-fixes`)

The whole card path is redesigned for **valuable raw (unsleeved) cards**: no friction feeding, no gates that slide a card sideways, and every card weighed at rest. The pre-build audit fixes ship in the same release. Build guide: `docs/ASSEMBLY.md`. Parts and power: `BOM.md`.

### Changed: machine
- **Hopper**
  - Before: bottom-feed gravity hopper (exit slot, separation wedge, gravity sled).
  - Now: a **motor-raised floor**. A 28BYJ-48 + ULN2003 turns a T8×8 lead screw that lifts a carriage on 2 × LM8UU.
  - A light printed feeler flag with a conjugate cam trips a microswitch when the top card reaches pick height. A second switch homes the floor.
  - An empty plate passes under the flag through a notch, so the soft top limit reports "hopper empty".
  - Code: `hardware/elevator.py` (GPIO 16/19/20/21, switches 12/13). CAD: `cad/hopper.scad`, `cad/hopper_elevator.scad`.
- **Pick arm**
  - Before: vertical-axis swing arm on an undesigned post.
  - Now: a **single MG996R (ch0) with a crank and two phased followers** (triple parallelogram). The suction cup stays vertical and the card stays flat, lifting straight up and lowering straight down.
  - The cup sits on a spring slider. SMC ZPT16BS-B5 bellows pad. The vacuum tube runs through the hollow pivot.
  - Pick at X −215, drop at X −95. Servo moves are cosine-ramped.
  - Files: `cad/suction_arm.scad`, `cad/pick_arm_check.py`.
- **Conveyor**
  - Before: rollers with #010 O-rings.
  - Now: a **60 mm riser**; 608ZZ bearing housings; **4 × 135 × 3 mm O-ring round belts** over a slide bed; both rollers direct-driven by N20s through 3 → 8 mm couplings (`cad/riser.scad`, `conveyor_rail.scad`, `conveyor_roller.scad`, `motor_mount.scad`, `slide_bed.scad`).
- **Scan station**
  - Light-tight hood with **LED strips** instead of a ring (no glare spot on foils).
  - Side guides narrow the channel to 66.4 mm.
  - The camera bracket stands on the front rail feet and holds the lens 100 mm above the card.
  - The camera axis moved to X +5 to clear the arm's drop zone.
  - 500 mm SC1130 ribbon; the Pi's CSI connector faces +X.
- **Sorter**
  - Before: 2 flat gate levers.
  - Now: a **cradle shuttle**. The card leaves the belt onto a cradle on the TAL221 load cell and is weighed at rest in HOLD.
  - ch2 (slider-crank) moves it to one of 4 columns or the reject position. ch1 (D-shaft crank) tips it into the upper slot, or down a fixed ramp into the lower slot or the reject bin.
  - The cradle needs PTFE tape.
  - Files: `cad/shuttle.scad`, `shuttle_geom.scad`, `shuttle_check.py`, `lower_ramp.scad`, `reject_bin.scad`.
- **Tray**
  - The 2-floor tray moved to X 178..276.
  - New separate reject bin.
- **Assembly**
  - `cad/machine_frame.scad` is the single source of truth for the card path.
  - `cad/assembly.scad` builds the machine from `asm_*` modules with poses.
  - `cad/assembly-steps.yaml` has 11 build steps.
- **Electronics tray:** added 3 cable slots in the −X wall for the shorter (≈0.8 m) harness route round the hopper.

### Changed: software
- **New sort cycle in `main.py`:**
  1. elevator raise;
  2. suction pick and drop;
  3. belt runs until the camera sees the card centred (`hardware/card_detect.py`);
  4. capture (flipped 180°, 16:9) and identify;
  5. cradle weigh;
  6. route.
  - Empty, unknown and double weights all go to the reject bin.
  - Jams, a lost card and an empty hopper stop the machine safely.
- **Bin capacity.** Per-bin counts with limits (lower 50, upper 24, reject 35). A full bin **pauses with the card held on the cradle** until it is reset from the web UI, `--empty-bin N` or `--empty-all`.
- **Module ownership.** `hardware/servos.py` owns only ch0 (arm). `hardware/shuttle.py` owns ch1 (tilt) and ch2 (carriage), each with ramped moves and interlocks.
- **Load cell.** `hardware/loadcell.py` uses `zero()`, detects failed reads and saves its calibration to `config/loadcell_calibration.json`.
- **Calibration tools.**
  - `scripts/calibrate_servos.py`: arm, tilt and columns, with jog keys and `--verify`.
  - `scripts/calibrate_camera.py`: empty-station reference + centred card → crop.
- **Tests.** `scripts/test_hardware.py` has 10 subsystem tests. `tests/test_cycle_mock.py` has 26 mock tests, including every safety path.

### Fixed (pre-build audit)
- **Firmware**
  - Pump-off and arm-park now run in `finally`.
  - The session survives per-card errors.
  - A double pick no longer re-fires the pump.
  - Load-cell calibration uses tared counts.
  - The relay polarity and presets in the test script now match `servos.py` and `vacuum.py`.
- **L9110S brake** was driving both motors in reverse at full power for 50 ms; it is now a true brake (both inputs HIGH).
- **Weights** outside the bands are rejected, and the belt stops after routing.
- **CAD**
  - Real 608ZZ pockets (the boss used to be solid).
  - The roller key no longer slots the whole roller.
  - Sorting-tray joins and screws go into solid bosses.
  - The camera bracket uses the real Pi Cam 3 hole pattern.
  - The hopper is now fastened down; the arm post exists.
- **Electrical: from the independent audit, documented in BOM.md / ASSEMBLY.md §14**
  - **12 V 5 A** supply. The arm-move peak is ≈ 3.2 A, over the 3 A adapter.
  - **Three** fixed 5 V regulators: logic, servo, and a new motor rail for the N20s and the stepper, which were on the Pi's regulator.
  - 1000 µF on the servo and motor rails and at PCA9685 V+.
  - Flyback diode across the pump.
  - **10 kΩ pull-downs on the L9110S inputs** (GPIO 23–26 float after `cleanup()`), plus the existing 10 kΩ pull-up on the relay input (GPIO 17).
  - **PCA9685 VCC on 3.3 V** (the old schematic had 5 V, which pulls the Pi's I²C pins to 5 V).
  - HX711 DOUT = GPIO 5 and SCK = GPIO 6 (the old SVG had them swapped).

### Documentation
- **`BOM.md`** rewritten for v2:
  - one de-duplicated BOM with have / verify / buy status and totals;
  - still to buy ≈ $552;
  - power budget, printed-parts table, fastener counts.
- **`docs/ASSEMBLY.md`** rewritten:
  - print list; all 34 heat-set inserts;
  - 11 mechanical steps with screws and checks;
  - GPIO and PCA9685 tables, power rails, harness, ribbon, tube and load-cell routing;
  - software setup and calibration order;
  - first run, troubleshooting, known risks, and a list of code/CAD disagreements.
- **`README.md`** updated to the v2 design. The L9110S is plain GPIO, not I²C 0x60. The rules format is the real `match` format.
- **`docs/wiring_diagram.svg`** redrawn for the v2 pinout. **`riftbound_sorter.kicad_sch`** text updated to match. **`docs/assembly-guide.html`** marked as superseded (v1 design).

### Removed
- Sort-gate levers (`sort_gate_lever.scad` no longer printed).
- Hopper gate, gravity sled and exit slot.
- Old swing arm and arm post.
- #010 O-rings.
- LED ring.
- Separate weigh platform.
- 9 printed output bins (`output_bin.scad`).
- LM2596 bucks.
- Short CSI adapter cable.

---

## [0.1.0] — 2024-10

Initial hardware prototype and software stack.

### Added

**Hardware drivers (`hardware/`)**
- `conveyor.py` — L9110S dual-motor driver for card transport rollers; software PWM via RPi.GPIO; forward/stop/brake modes
- `servos.py` — PCA9685 I2C servo controller (0x40, 50 Hz); pickup arm, deflect gate, and bin-select channels; angle presets for 8-bin + reject layout
- `vacuum.py` — Active-LOW relay control of 12V vacuum pump on GPIO 17; pulse helper for card release
- `loadcell.py` — HX711 load-cell reader (GPIO 5/6); classifies weight as empty / single / double pick; calibration helper
- `camera.py` — Pi Camera Module 3 via picamera2; JPEG capture with configurable crop region; loads `config/camera_crop.json` at startup if present

**Vision (`vision/`)**
- `identify.py` — Perceptual hash (pHash, 16x16) card identification; parallel image download and hash DB build via ThreadPoolExecutor; returns (card_id, confidence) with 0.75 minimum threshold; DB cached at `cache/hash_db.json`

**API layer (`api/`)**
- `riftcodex.py` — Riftcodex API client; fetches all card metadata with 24-hour disk cache at `cache/cards.json`; lookup by ID or name
- `inventory.py` — SQLite inventory (`data/inventory.db`); WAL mode; `scans` and `inventory` tables; session stats and CSV export

**Sorting logic (`sorter/`)**
- `rules_engine.py` — JSON-driven rules engine; top-to-bottom evaluation; supports exact-match and list-match on any card field; default catch-all rule; runtime reload

**Web UI (`web/`)**
- `app.py` — Flask dashboard on port 5000; live stats (cards/min, hopper-empty banner) polled every 3–5 s; inventory table; in-browser rules editor with save; CSV export endpoint

**Main loop (`main.py`)**
- Full pick-scan-sort cycle: arm down, vacuum on, weight check, arm up, conveyor transport, camera capture, card identification, rules engine bin assignment, servo routing, inventory log
- Hopper-empty detection after 3 consecutive empty picks with auto-resume on refill
- Double-pick detection with vacuum pulse recovery
- CLI flags: `--calibrate`, `--build-db`, `--dry-run`, `--web-only`
- Clean shutdown on SIGINT/SIGTERM

**Scripts & deployment (`scripts/`)**
- `calibrate_camera.py` — Interactive crop calibration; auto-detects card edges via column/row variance; saves `config/camera_crop.json`
- `setup.sh` — Pi setup script (dependencies, systemd service install)
- `riftbound-sorter.service` — systemd unit for auto-start on boot

**CAD models (`cad/`)**
- Baseplate tile, conveyor rail, conveyor roller, electronics tray, hopper, output bin, scanner hood, sort gate lever, suction arm (OpenSCAD `.scad` sources)

**Configuration**
- `config/rules.json` — Default 8-bin sort rules: Champions, Spells, Followers, Equipment, Legendary/Epic, Rare, Common/Basic, Default
- `config/rules.example.json` — Committed example so the real rules can be machine-local

**KiCad schematic**
- `riftbound_sorter.kicad_sch` — Pi Zero 2W + PCA9685 + HX711 + relay + camera wiring

### Notes
- `concurrent.futures` and `sqlite3` are Python stdlib — no pip entry required
- `adafruit-blinka` is required for `import board` and `import busio` used by the CircuitPython servo driver
- `config/camera_crop.json` is machine-specific and gitignored; run `scripts/calibrate_camera.py` after physical assembly
