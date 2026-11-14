# Option B: bill of materials (round 4, 2026-11-14)

Cap: **$100 of new parts**. Filament is separate (owner's).
Prices were seen live on 2026-11-13/14. All ship from Amazon; free delivery on a $35+ order (no Prime).

## To buy

| # | Part | Why | Price | Link |
|---|---|---|---|---|
| 1 | DROK 12 V → 5 V 3 A potted converter (fixed output) | servo power; the owned LM2596s can't be set without a meter | $9.99 | https://www.amazon.com/dp/B07P663XJV |
| 2 | Diode kit (1N4007 / 1N5819) | flyback across the pump | $5.99 | https://www.amazon.com/dp/B0D69Q6HXG |
| 3 | AQUANEAT airline connectors, 40 pcs (straight, tee, elbow) | cup neck ↔ 4 mm tube; bleed tee | $4.97 | https://www.amazon.com/dp/B08LMZ86QC |
| 4 | Joytube 8 → 4 mm barb reducer, 3-pack | pump nozzle → 4 mm tube | $5.99 | https://www.amazon.com/dp/B08PRVY7RR |
| 5 | Silicone tube 8 mm ID × 10 mm OD, 1 m | short sleeve over the 8.5 mm pump nozzle | $5.69 | https://www.amazon.com/dp/B0DSQSZKFP |
| 6 | 5.5 × 2.1 mm screw-terminal barrel connectors | 12 V adapter → wiring, no cutting | $3.99 | https://www.amazon.com/dp/B09S3S6RYC |
| 7 | M4 × 10 SHCS (50) | load cell (skip if the HX711 kit came with M4 screws) | $6.99 | https://www.amazon.com/dp/B0GCSJR229 |
| 7b | Rubycon 1000 µF 16 V capacitors (15) | bulk cap at the PCA9685 servo terminals (review) | $6.99 | https://www.amazon.com/dp/B0F8C2HP5Y |
| 12 | ELEGOO 28BYJ-48 5 V stepper + ULN2003 driver, 5 sets | yaw axis (round 4): 0.09 deg half-steps through a 64:1 gearbox, replaces the yaw MG996R | $14.99 | https://www.amazon.com/dp/B01CP18J4A |
| 13 | 4" square lazy-susan bearing, 2-pack (steel balls, 5/16" thick) | carries the turntable and the arm's tipping moment (the servo's spline used to) | $6.48 | https://www.amazon.com/dp/B09V87HXG5 |
| 14 | HiLetgo KW12-3 roller-lever microswitch, 10-pack (20 x 10.5 x 6.5) | yaw home switch | $5.99 | https://www.amazon.com/dp/B07X142VGC |
| 15 | M2 button-head screw + nut kit | 2 x M2 x 12 + nuts hold the switch in its slots | $6.99 | https://www.amazon.com/dp/B0DDY2L533 |
| | **Core subtotal** | | **$85.05** | |
| 8a | Camera focus, cheap: +5.0 reading glasses 5-pack; one lens as a close-up lens over the owned Arducam (fixed focus 1.5 m-inf -> 176..200 mm with +5 D; the boom slides to focus) | the owned camera can't focus at card distance | $9.99 | https://www.amazon.com/dp/B0C64JGSYC |
| 8b | Camera focus, sure: Raspberry Pi Camera Module 3 (autofocus, 10 cm min) | fallback if 8a is soft | $29.25 Adafruit + ship / $34.98 Amazon | https://www.adafruit.com/product/5657 |
| 9 | 1/2" × 2' × 2' plywood | base board (skip if there's scrap) | $13.06 Home Depot | https://www.homedepot.com/p/204853869 |
| 10 | Zip ties 4" (200) | cable/tube dressing (skip if on hand) | $3.99 | https://www.amazon.com/dp/B0BC1VH4XB |
| 11 | Heat-shrink kit | splices (skip if on hand) | $6.99 | https://www.amazon.com/dp/B072PCQ2LW |

Totals: core + 8a = **$95.04** (round 3 was $60.59; the stepper yaw adds $34.45). 9–11 only if nothing is on hand, and they would push it past $100: use scrap wood, tape or hot glue instead. 8b instead of 8a breaks the cap.

Not bought on purpose: pull-down resistor (the relay is active-high and GPIO 17 defaults to pull-down), vent valve (a pin-hole bleed releases the card), tee-nuts and long bolts (every pivot is an M3 x 16 into an insert through a printed sleeve; servo tabs M3 x 12 + nut; horns M2.5 x 6 from the standoff kit), springs (the cup slider is gravity-loaded).

## Already owned and used

Pi Zero 2 W kit (incl. 5 V PSU), PCA9685, 1 of the 4 MG996R (lift; + horn), HX711 + 5 kg bar load cell, R385 pump, KY-019 relay, PATIKIL 27 mm bellows cup, 4 mm silicone tubing, 12 V 3 A adapter, 1 × 608ZZ (the slider contact ring; the 4 rollers are gone in round 4), 50 M3 heat-set inserts (≈ 20 used), M3 screw/nut/nylock assortment, M2.5 standoff kit, WS2812B ring, Arducam IMX708 + 150 mm Zero ribbon, Dupont jumpers, 22 AWG wire, soldering iron.

Owned but unused by B: N20 motors, L9110S ×3, 2 × LM2596, 12 V 2 A adapter, 16 mm O-rings, 8 mm rods, 3 MG996R spares, the other 19 608ZZ.

## Printed

≈ 0.9 kg solid volume (≈ 0.6–0.7 kg printed): 7 bins, hopper, bed + cell block, pedestal, turntable/mast, hub, 2 links, hand, slider, camera tower, ring holder, 4 feet. Largest part: link A, 238 mm (fits the 256 bed). v2 needed ≈ 4 kg.
