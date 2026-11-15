# Option B: turntable picker (concept, 2026-11-13)

Budget rebuild: $100 cap on new parts, built mostly from parts already owned.

- `b_params.scad`: all shared geometry (stations, heights, yaw stage, lift servo, arm).
- `b_parts.scad`: printed parts (`-D 'part="bin"'` etc.) + reference solids.
- `b_assembly.scad`: whole machine, `-D yaw=<servo deg> -D th=<link deg>`.
- `b_check.py`: numeric checks (pocket spacing, yaw tolerance, lift range, FOV, camera clearance).
- `b_interfere.scad` + `b_sweep.sh`: collision sweep of the moving arm against every fixed part.

Card path: hopper (station 0, s=10) -> cup lifts top card -> scan/weigh bed (s=30, camera above, owned 5 kg bar cell under) -> released, photographed, weighed -> re-picked -> one of 6 bins or reject (s=50..170, 20 deg pitch, fan-shaped pockets).
Touch-down sensing: the cup slider rests on the hand under gravity; an M3 screw pair is a contact that opens when the cup touches anything.

## Round 2 changes (review fixes, 2026-11-13)

- Turntable: horn screw holes actually cut at the plate (were at Z 0); lift servo flipped to lie outboard of P1, so the yaw horn screw and the 4 M2.5 horn screws are reachable from above at any time.
- Tube + leads: zip-tied at the mast top, free loop back to a fixed `cable_post` behind the axis (no route through the yaw joint).
- Pivots: printed sleeves on M3 x 16 into inserts (no M3 x 25/35, no nylocks); servo tabs through-bolted with nuts in hex pockets.
- Accuracy: hopper 65 x 90 with a lead-in chamfer; bins 100 mm radially; bin dividers start at r 236 so nothing can catch the card's inner corners; b_check now has a yaw error stack-up.
- Swing clearance: lift range -6..+10 deg (card 21 mm over the walls); roller axles in slots to set the sag-stop gap.
- Arm stiffness: links 10 x 12 (was 5 x 12); full-height mast wall, rear gussets, gusset under the P2 boss.
- Touch sensing: 608 bearing ring on the slider (12 g of weight) rests on two M3 head-up screws + a printed bump (3-point); no wire on the moving slider.
- Slider Ø12 solid with an airline tee pocket at the bottom (stem into the cup neck, one leg to the tube, one to the pin-hole bleed).
- Camera: +5 D close-up lens, lens 176 mm over the bed, boom clamps to the post at any height; WS2812 ring on its own clamp beside the post.
- Bed boss 5 mm (4 mm under the M4 heads). Bin/hopper ears inboard only.
- `export_b.py` exports all print STLs (print orientation) + PRINT_LIST.md + zip.

## Round 3 changes (second review, 2026-11-13)

- Slider and bore are D-profiles (flat 3.5 mm off-axis, 0.1 clearance): the cup can no longer swivel the card.
- Touch contact: three M3 button heads at 120 deg on r 11.5 (two wired, one plain) under the 608 ring; inserts 3 mm from the bore; hand flange kept out of the link plane.
- Tee snaps into a slot 0.8 mm narrower than its seat.
- Camera tower moved off the station ray to (330, 60): it stays on a 2 ft board and clear of bin 1. Boom and ring holder clamp with an M3 into a 10 mm boss; camera turned so the sensor's long axis is along the card; new `lens_frame` holds the popped-out +5 D glasses lens; lens 188 mm over the bed (middle of the +5 D range).
- Hopper/bin ears overlap their walls; hand zip-tie slot moved between the pivots; mast zip-tie holes moved to x 50/60; mast wall widened to x 0..70 with the gussets outside the nut path (washer + nut on the flat back, no pockets); full-width gusset under the P2 boss; horn slots are +/-8 deg arcs; yaw-base tab holes and the slider stub use self-tap pilots (no heat-set in thin walls); cap screw M3 x 8.
- Print orientations fixed in export_b.py (post upright, boom and lens frame upside down, hand flange-down, brims on the slider and sleeves).
- b_check: slider swivel and radial bed offset in the error budget; the inner-zone check is now the honest two-card worst case (margin 0 mm, RSS 4.5 mm), which REQUIRES the firmware to approach every station from the same direction. Fallback if the bench repeatability test fails: 5 bins + reject at 22.9 deg pitch.

## Round 4 changes (yaw stepper, 2026-11-14)

Why: the MG996R yaw servo needed ~0.6 deg repeatability and the inner bin zone had 0 mm worst-case margin.

- Yaw axis is a 28BYJ-48 (5 V, ULN2003): 0.088 deg half-steps through its 64:1 gearbox, unlimited travel. Firmware approaches every station from the same direction, so the gearbox backlash is always taken up the same way. The error budget assumes 0.25 deg repeatability (not measured yet); the inner-zone margin goes from 0 to +4 mm.
- The servo spline was also the turntable's bearing, and the stepper's shaft can't carry the arm (CoG ~90 mm out). A 4" square steel lazy-susan bearing now carries the turntable. The old 4 rollers and the yaw base are gone.
- New `pedestal` (tube r 80, deck at Z 34.5..39.5, 4 board tabs): bearing bottom plate in a 1 mm pocket, M3 x 6 into Ø2.5 pilots. The stepper hangs under the deck, shaft up on the axis, M3 x 10 + washer + nut through Ø5 float holes. Assemble loose, sweep the arm by hand, then tighten so the shaft centres on the bearing.
- New `hub` (Ø14, flange Ø32): double-D press fit on the shaft (2.95 across the flats), 3 x M3 x 8 up into the turntable.
- Turntable: horn screws removed; square 108 footprint for the bearing's top plate (M3 x 6 into pilots); Ø8 access holes at local 90/180/270 deg r 57 for driving the bottom-plate screws (rotate the arm 45 deg off the deck square).
- Home: a KW12-3 roller-lever switch lies flat on a bracket at az 180 (Z 44), M2 x 12 in radial slots to set the lever against the end of a tab on the turntable (local 180 deg, r 92). HOME = arm at az 0. Wired NC to a GPIO with pull-up.
- Speed estimate (b_check): ~2.6 s for the full 160 deg, ~0.6 s per 20 deg hop at 12 rpm, vs well under 1 s for the servo.
- **Check on arrival:** the 28BYJ-48 dims (shaft offset 8, double-D 3.0, shaft 10 above the face) and the lazy susan's hole pattern (assumed 80.8 mm square on both plates). If the holes don't line up with the printed pilots, drill new Ø2.5 pilots through the plate's own holes.

## Round 5 changes (review of round 4, 2026-11-14)

The reviewer found three blockers in round 4. Two were the 28BYJ-48's 1-3 deg gearbox backlash, which bearing drag can't hold to one side, and a pedestal deck that couldn't print. The third was the bearing's two plates probably having different hole patterns. A bias weight or band to take up the backlash didn't hold up either: it needs ~0.1 N held constant, and pulley friction is about the same size.

- Yaw motor is now a **NEMA 17 pancake** (42 x 42 x 23) on a **TMC2209**, direct drive. There's no gearbox and no backlash. 1/16 microsteps = 0.1125 deg. ~170 mN m holding torque, so a 10 mN m disturbance moves the arm 0.07 deg. 160 deg in ~1.7 s, 20 deg hop ~0.5 s. Inner-zone margin is +4.7 mm.
- `pedestal` is now an open tube (prints with no supports). New flat `deck` part: the motor's Ø22 boss locates in it (centring the shaft on the bearing), the motor screws are 4 x M3 x 8 from above, and 4 x M3 x 10 hold the deck to bosses in the tube.
- Drive: a `collar` on top of the turntable, sunk 3 mm, with an M3 x 6 set screw onto the shaft's flat through a captive nut. It works with a 20 or a 24 mm shaft. 2 x M3 x 10 go into the turntable through float holes. Everything stays reachable from above. The round-4 hub is gone.
- Bearing holes: `ls_pitch_bot` (deck, 80.8 assumed) and `ls_pitch_top` (turntable, 88.9 assumed) are separate. **Measure the real bearing before printing the deck and turntable.** Everything else can print now. To reach all 4 bottom-plate screws, park the arm at +45 deg and then at -45 deg.
- Home switch moved to az 270, behind the axis. At az 180 the links hit it at the reject station (caught by the sweep). It's a KW12-3 press-fit in a walled cradle at Z 51. A separate chamfered `trip` block on a 20 mm tab (local 270) slides in a radial slot (M3 x 12 + nut) to set the click point. During homing the tab arrives from the +X side: fit the switch with its lever hinge on that side.
- Firmware: approach every station from the same direction anyway (it costs nothing). Re-home at each hopper visit to catch any missed step.

## Round 5.1 (second review fixes, 2026-11-14)

- Home switch: the trip block and tab are gone. A **cam rim** on a sector of the turntable (local 262..350 deg, r 96, Z 51.4..57.4, 8 deg ramps at both ends) holds the switch pressed for every arm angle from 0 down to -72. So pressed means "at or below home", released means "in the working range", and homing is never ambiguous. The cable post is hit at about -90, below the cam.
- `switch_cradle` is a separate part on the board at az 270 (2 x M3 x 12 into pilots drilled in the plywood). Its radial slots put the switch face anywhere from r 97.5 to 103.5: slide it in until the roller clicks on the rim with ~1 mm of overtravel. The KW12-3 press-fits between the end walls, and the solder tags exit through the open outer side.
- Deck pocket is now 1.3 mm per side oversize. Bottom-plate screws are M3 x 6 with washers, so the bearing's bottom plate can centre itself on the motor shaft (see assembly). The collar is now rigid (Ø3.4 holes, fully tight).
- Collar: set screw moved to +X, with a key notch in the recess rim. The ears are full height, so it prints top-face-down with no supports.
- Pedestal: 6 vent slots for motor heat. b_check: link mass 2 x 33 g, stiffness at the TMC2209's default 50 % standstill current (0.135 deg), and the cam coverage check replaces a span check that could never fail.

### Yaw stage assembly order
1. Motor to deck on the bench: boss into the Ø22.4 hole, 4 x M3 x 8 from above. These screws can't be reached later.
2. Deck onto the pedestal tube: 4 x M3 x 10. Pedestal to the board: 4 x M3. Run the motor leads out through the az 315 slot.
3. Bearing's top plate to the turntable underside: M3 x 6 into pilots on `ls_pitch_top`, driven up from below with the plates turned 45 deg apart.
4. Turntable + bearing onto the deck, with the bottom plate loose in its pocket. Shaft up through the Ø7 hole.
5. Collar onto the shaft, set screw (+X) onto the flat, 2 x M3 x 10 into the turntable, all fully tight.
6. Bottom-plate screws: M3 x 6 + washers through the Ø8 access holes. Park the arm at +45 deg for three of them and -45 deg for the fourth, and snug them. Swing the arm a full sweep by hand, then tighten.
7. Switch cradle: drill 2 pilots in the board, slide it in until the switch clicks with the arm at 0 (on the rim, ~1 mm overtravel), then tighten.

### Electronics notes (TMC2209 on the Pi Zero 2 W)
- VM 12 V from the adapter, with a 1000 µF cap at VM/GND. VIO 3.3 V from the Pi. Common ground.
- STEP/DIR on two GPIOs, step pulses timed with pigpio DMA waveforms. EN on a GPIO with its pull-up set in `config.txt` (`gpio=<EN>=ip,pu`, same trick as the relay pins), so the motor stays off during boot. No resistor to buy.
- UART, write-only: Pi TX wired straight to PDN_UART (no RX, so no 1 kΩ resistor is needed; the driver settings are written, never read back). Use `dtoverlay=disable-bt` and turn off the serial console. Set the run current to ~0.7 A. Set the hold current equal to the run current (IHOLD = IRUN) for full stiffness at the stations.
- The 12 V 3 A adapter feeds the pump, the 5 V converter (servo) and the stepper: stagger the pump start and the yaw moves.
- Firmware: approach every station from the same direction. Allow ~150 ms of settle after each move (the arm rings at ~5-7 Hz). Home onto the switch's press edge from above. At hopper visits only *check* the switch state, don't re-zero. Measure station angles once with the camera rather than trusting the computed ones.

## Round 5.2 (assembly-video review, 2026-11-14)

- Camera board is clamped face-down in a 1.5 mm pocket on top of the lens frame. 4 × M3 × 16 go down through the boom (which now has a 48 mm wide camera end) into Ø2.5 pilots in the frame's side walls, outside the lens pocket. The old lens-frame screws ran through the lens pocket and only reached 0.5 mm into the insert. No M2 screws are needed.
- Collar: an M3 × 8 socket screw is the set screw (an M3 × 6 head would stop with its tip just touching the flat). The turntable notch is 1.4 mm deeper, so the head clears it.
- Feet go open side down: an M3 × 12 goes up through each foot's 2 mm floor into the board.
- Clamp screws for the boom and ring holder are M3 × 12 (an M3 × 10 only reaches the post face).
- Order fixes:
  - The ring holder goes on the post BEFORE the boom: both slide on from the top.
  - The slider goes in bare from the top; the tee and cup go on from below afterwards.
- `board_template.py`: 1:1 drilling template (12 US Letter pages, 36 holes plus the station centres), taken from the same numbers as the CAD.
- To check once the bearing is measured: the top-plate screw heads (r ~63) and the bottom-plate heads (r ~57) leave only ~0.2 mm between them inside the bearing. If they rub, use button heads on the bottom plate.

## Pin map (option B)

Pi Zero 2 W, BCM numbering. The same numbers are the code defaults (`hardware/yaw.py`, `touch.py`, `vacuum.py`, `loadcell.py`, `lift.py`) and the `config/machine.b.example.json` values; `tests/test_b_machine.py` checks they don't clash.

| Function | GPIO | Header pin | Direction / pull | Notes |
|---|---|---|---|---|
| I2C SDA (PCA9685, 0x40) | GPIO 2 | 3 | I2C | lift servo on PCA9685 ch 0; PCA9685 VCC from the Pi's 3.3 V |
| I2C SCL | GPIO 3 | 5 | I2C | |
| TMC2209 PDN_UART (write-only) | GPIO 14 | 8 | UART0 TX | straight wire, no resistor; `enable_uart=1`, `dtoverlay=disable-bt`, serial console off |
| (reserved) UART RX | GPIO 15 | 10 | — | keep free: a 1 kΩ from TX + this pin would let the driver settings be read back |
| WS2812 ring data | GPIO 18 | 12 | PWM0 | pigpiod runs with `-t 1` (PCM clock) so it never touches PWM; audio off |
| HX711 DOUT | GPIO 5 | 29 | in | same as v2 |
| HX711 SCK | GPIO 6 | 31 | out | same as v2 |
| Pump relay IN (KY-019, active HIGH) | GPIO 17 | 11 | out, boot pull-down | `gpio=17=ip,pd`: relay OFF at boot; no resistor |
| Yaw home switch (KW12-3, NC) | GPIO 22 | 15 | in, pull-up | COM → GND, NC → GPIO. Released = LOW; pressed / broken wire = HIGH |
| Yaw STEP | GPIO 23 | 16 | out (pigpio waves) | |
| Yaw DIR | GPIO 24 | 18 | out | |
| Yaw EN (TMC2209 ENN, active LOW) | GPIO 25 | 22 | out, boot pull-up | `gpio=25=ip,pu`: motor OFF at boot |
| Cup touch contact | GPIO 16 | 36 | in, pull-up | one screw head → GND, the other → GPIO. Resting = closed = LOW; touching / broken wire = HIGH |
| Camera | CSI | — | — | Arducam IMX708, Zero ribbon |

Free: GPIO 4, 7-13, 19-21, 26, 27. GPIO 19-21 are PCM pins: leave them alone while pigpiod uses the PCM clock.

Wiring notes the software relies on:
- **TMC2209 MS1 = MS2 = VIO.** The UART config is write-only and can't be checked. The code writes it to all four slave addresses, so the MS pins don't matter while the UART works. If the UART line is dead, the pins set the step size: MS1 = MS2 high gives 1/16, the same as the code. The module default (both low) gives 1/8, and every move would then go twice as far.
- **EN pull-up vs the module.** Some TMC2209 boards pull ENN to GND with a resistor (always enabled). The Pi's ~50 kΩ boot pull-up can't beat a 10 kΩ pull-down. Measure EN with the Pi booted and the sorter stopped: it must read > 2.5 V.
- **pigpiod keeps driving its pins after the sorter dies** (it owns them, not the kernel). On B the pump relay goes through pigpiod too, on purpose: a card held on the cup away from the bed or a bin stays held across a crash or a service stop. `scripts/safe_outputs.py` (ExecStopPost) runs `pigs wvhlt` first, then drives EN high and STEP/DIR low. It drives the relay low unless `data/machine_state.json` says `"pump_hold": true`. It only puts the PCA9685 to sleep after a clean stop with the arm parked; otherwise the lift keeps holding its height. With no machine selected it touches nothing.

## Software (option B)

`config/machine.json` `"machine": "b"` makes `main.py` drive this machine (`sorter_b.py`). Everything else is the v2 program: same service, web UI, `/api/status`, Pause / Stop at card boundaries, clean / unclean record, "Machine clear", bin counts. Rules bins 0-5 are the bins at yaw 50..150 and 9 is reject at 170. Rules with bin 6/7 go to reject.

- Drivers: `hardware/yaw.py` (TMC2209 + pigpio, trapezoid moves, homing, hard limits [-80, 175], same-direction approach, lift interlock), `hardware/lift.py` (th ↔ servo map, touch-down, full-lift interlock), `hardware/touch.py`, `hardware/b_calibration.py` (`config/b_calibration.json`: station yaws, lift th per station, park / clear pose, servo map), `hardware/b_mock.py` (simulated machine for `MOCK_HARDWARE=1`).
- Cycle, safety rules and make-safe behaviour: the `sorter_b.py` docstring.
- Calibration / jog API (token-protected, refused while running): `/api/b/...` in `web/app.py`.
- Bench tests: `scripts/test_hardware.py` shows a B menu on a B machine.
- Setup: `bash scripts/setup.sh --machine b` writes `"machine": "b"` into `config/machine.json`. On real hardware a missing selection refuses to start (exit 78): v2 code on B wiring would switch the pump and the stepper on. Setup installs pigpiod (`-l -t 1`), turns on the UART (`enable_uart=1`, `dtoverlay=disable-bt`, console off) and adds `gpio=17=ip,pd`, `gpio=25=ip,pu`, `gpio=16,22=ip,pu` to config.txt.
- Yaw limits are [-64, 175]. -64 keeps the arm inside the home cam (pressed down to -72), so the switch never reads "released" below home.
- Homing is bounded by `data/yaw_hint.json`: the interval the arm is in, written atomically before and after every move. It runs at `HOME_CURRENT_A` (0.3 A), so a stall against the cable post is harmless. A hint that contradicts the switch (pressed while the hint says the arm is above the cam, or released while it says inside the cam) is refused without moving. With no trusted hint, homing only searches 20°. If that fails: motor off, put the arm at the park pose by hand, then "declare position" (calibration API).
- One hardware lock: every sorter step that moves something holds it, and a calibration-API command arriving meanwhile is refused as busy (409).
- A held card is never let go except over the bed or a bin. The pump keeps holding it with no time limit: the R385 is a diaphragm pump, which draws less against a sealed cup than at free flow. That means wear, not heat. It also holds across exits and restarts until "Machine clear".

Hardware points found while writing the software (not fixed in the CAD):
1. **Empty hopper — fixed in the CAD (029e479).** There is now a Ø32 hole in the hopper floor and a Ø35 through-hole in the board under the cup. With no card left, the cup drops through and never touches. "No touch, with the cup lip ≥ 1.5 mm below the floor top" = hopper empty: a clean stop that needs no "Machine clear". A touch at floor height that delivers nothing to the bed is still a fault: the last card was not picked. Each hopper descent is also bounded 5 mm below the previous touch, so a contact stuck closed can't press through the stack. Bins are bounded by their card count in the same way.
2. **The lost-step check at the hopper is weak.** The hopper (10°) is only ~2° above where the switch is guaranteed released (~8°). The check only catches the arm sitting ≥ 2-10° *lower* than tracked, never higher. The software adds an edge check: released at +1°, pressed at -1°, run at every park and every `EDGE_CHECK_EVERY` (20) cards.
3. **Homing with a misadjusted switch.** Now bounded by the position hint and run at the low homing current (see Software). Still adjust the switch cradle and check it on the bench first (`test_hardware.py` B → home switch watch, motor off, arm turned by hand).
4. **The 5 kg cell vs a 1.75 g card.** The thresholds (empty ≤ 0.5 g, single 1.3-2.3 g, double ≥ 2.8 g) need the bed's noise well under 0.3 g. Check it with the B load-cell bench test.
5. **The WS2812 ring has no driver in this pass.** GPIO 18 is reserved. `rpi_ws281x` on PWM needs root (or move the ring to SPI, GPIO 10).

## Phone app

The sorter's web server is also a phone app: a PWA served by the Pi itself, so there is no App Store and nothing is fetched from the internet. It runs on both machines; the Setup screen is option B only.

### Open it and add it to the home screen
1. Put the phone on the same Wi-Fi as the Pi. In Safari, open `http://riftbound-sorter.local:5000` (or `http://<pi-ip>:5000`).
2. Tap Share → **Add to Home Screen** → Add. The "Sorter" icon opens full screen, without the Safari bars. On Android Chrome: menu → **Add to Home screen**.
3. Open the app from the home screen and pair it there (next section). iOS gives the home-screen app its own storage, separate from Safari's, so a pairing done in Safari doesn't carry over.

Browsers only run service workers on https or localhost. On `http://…local:5000` the offline shell cache stays off. The app works the same, but with the Pi off, the icon opens Safari's "can't connect" page instead of the app.

### Pair the phone
You can watch the status and the camera without pairing. Every control needs the web token. The token rules are unchanged: it lives in `config/web.json`, is never printed to the journal, and is never sent in answer to a GET.
1. SSH to the Pi and, as the service user: `cd /opt/riftbound-sorter && sudo -u pi venv/bin/python main.py --pair`. It prints a 6-digit code, valid for 10 minutes and usable once. Five wrong tries cancel it. Only a salted hash of the code is stored (`config/web_pair.json`, mode 600).
2. In the app: ☰ → **Pair this phone** → type the code → **Pair**. The app gets the token in the answer to that POST and keeps it in the phone's local storage. The desktop pages in the same browser use it too.

Or type the token itself: run `main.py --web-token`, then in the app open "Or type the token". To unpair a phone: ☰ → **Paired · manage** → **Unpair**. To lock every phone out, delete `config/web.json` and restart the service. A new token is generated, and every phone has to pair again.

### Screens
- **Run**: shows the state and message (polled every 1.5 s) with red or amber banners for jam, error, "check the machine", hopper empty and bin full. Below that are cards per minute (last 60 s and session average), session counts, the last card, and each bin's fill bar with **Emptied** and **All emptied**. The buttons appear only when the server would accept them: Pause / Stop while running, Resume when paused or the hopper is empty, Start after a Stop, and **Machine clear** after a jam, an error or an unclean stop. Machine clear restarts sorting. Stop, Start, Resume, Machine clear and Emptied ask for confirmation first. There is no separate "start" command: the service starts sorting when it starts, and Start resumes after a Stop. `--web-only` runs no sorting loop at all.
- **Camera**: a scan-bed frame about once a second while the machine is idle (`/api/camera.jpg`). While a run is in progress the app never touches the camera. It shows the sorter's own last capture (the card it just identified) instead. MOCK mode shows a drawn bed.
- **Setup** (option B): the calibration API in `web/app.py` `/api/b/...`. The server refuses it while a run is in progress, paused included, and the app shows the reason; stop the machine first. The yaw buttons (jog, go to, Home) are disabled until the arm is homed, at full lift and the touch contact reads closed, the same interlock as `hardware/lift.yaw_permitted`. They are also disabled while the pump is on and while the sorter holds the hardware lock (busy). A lift **Down** stops on contact. **Off** for the pump only works with the cup resting on a station. Anywhere else the app asks you to take any card off the cup by hand, then sends `card_removed`. If homing fails, use the **Homing failed?** panel: **Motor off**, turn the arm by hand to the park pose (home switch pressed), **Arm is at park**, then **Home**. Every refusal (409) is shown with the server's reason. Any move marks the machine not clean. When you are done: Run → **Machine clear**.

### Calibrate the stations, step by step
Bins use the rules-engine numbers, **Bin 0 … Bin 5**, plus **Reject** (rules bin 9), the same as `config/rules.json` and the Run screen. Every save goes straight into `config/b_calibration.json`. It is validated first, and a value out of range is refused with the reason.
1. Run → **Stop** and wait for "stopped" (or use `--web-only`). Open **Setup**.
2. Servo map, once (and again after re-fitting the lift servo horn): **Advanced** → send a raw servo angle near the bottom of the lift, measure the link angle th with an angle gauge, then do the same near full lift. Enter both `[th, servo]` pairs → **Save servo map**. The "cup lip" millimetres in the readout are only right once this is done.
3. **Home**. The readout shows Homed yes, Yaw ≈ 0°, Full lift yes, and "Yaw free".
4. For each station (Hopper, Scan bed, Bin 0-5, Reject):
   1. Clear the station: empty hopper, empty bed, empty bin.
   2. **Go to** the station. This is its CAD angle.
   3. Jog until the cup is centred over the pocket. Finish with a **+** jog: runs approach every station from below. If you overshoot, go −1° and come back up in +0.1° steps. For the scan bed, the Camera tab shows the cup over the bed.
   4. **Save current position**: tap the station → **Yaw → station**.
   5. Floor / touch height: **Probe** (the lift steps down until the touch contact opens and stays there). Hopper: **th → floor**. Scan bed: **th → touch**.
   6. Limit: from the probe height, step **Down** about 1 mm for a bin or the hopper (0.1° × 3) and about 3 mm for the bed (0.1° × 8). Then **th → limit**. The slider has 10 mm of travel; never go further.
   7. Approach: **Full lift**, then step **Down** until the cup lip is just above the highest surface it can meet there. Use the readout: about 35 mm over a bin or the hopper (walls at 34 mm), about 33 mm over the bed (bed top 29 mm). Then **th → approach**.
   8. **Full lift** before moving on. Yaw stays locked until you do.
5. Park pose (optional; the default is -10°): jog into the home cam, where the switch reads pressed, with nothing below the cup → **Yaw → park pose**.
6. Camera-clear pose (optional; the default is the hopper's angle): a yaw at least 15° from the bed where the arm is out of the camera's view. Check it on the Camera tab → **Yaw → cam-clear pose**.
7. Check the calibration table, then **Full lift**, then Run → **Machine clear**. The start-up self-test touches down on the empty bed and checks that the scale feels it.

Files: `web/static/` (app, manifest, service worker, icons from `uv run tools/make_icons.py`), `web/pairing.py`, `web/snapshot.py`, `tests/test_phone_app.py`.

Bin numbering: the phone app, video and template call the six bins 1-6; in rules.json and the API they are bin ids 0-5 (bin 1 = id 0), reject = 9.
