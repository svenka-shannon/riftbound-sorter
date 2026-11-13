# Option B: bill of materials (concept, 2026-11-13)

Cap: **$100 of new parts**. Filament is separate (owner's).
Prices were seen live on 2026-11-13 (Amazon Prime unless noted).

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
| | **Core subtotal** | | **$50.60** | |
| 8a | Camera focus, cheap: +5.0 reading glasses 5-pack; one lens as a close-up lens over the owned Arducam (fixed focus 1.5 m-inf -> 176..200 mm with +5 D; the boom slides to focus) | the owned camera can't focus at card distance | $9.99 | https://www.amazon.com/dp/B0C64JGSYC |
| 8b | Camera focus, sure: Raspberry Pi Camera Module 3 (autofocus, 10 cm min) | fallback if 8a is soft | $29.25 Adafruit + ship / $34.98 Amazon | https://www.adafruit.com/product/5657 |
| 9 | 1/2" × 2' × 2' plywood | base board (skip if there's scrap) | $13.06 Home Depot | https://www.homedepot.com/p/204853869 |
| 10 | Zip ties 4" (200) | cable/tube dressing (skip if on hand) | $3.99 | https://www.amazon.com/dp/B0BC1VH4XB |
| 11 | Heat-shrink kit | splices (skip if on hand) | $6.99 | https://www.amazon.com/dp/B072PCQ2LW |

Totals: core + 8a = **$60.59**; + 9–11 if nothing is on hand = **$84.63**. With 8b instead of 8a: ≈ $85.58 / $109.62 (then skip 10–11, or 7 if the HX711 kit came with M4 screws, to stay under $100).

Not bought on purpose: pull-down resistor (the relay is active-high and GPIO 17 defaults to pull-down), vent valve (a pin-hole bleed releases the card), tee-nuts and long bolts (every pivot is an M3 x 16 into an insert through a printed sleeve; servo tabs M3 x 12 + nut; horns M2.5 x 6 from the standoff kit), springs (the cup slider is gravity-loaded).

## Already owned and used

Pi Zero 2 W kit (incl. 5 V PSU), PCA9685, 2 of the 4 MG996R (+ horns), HX711 + 5 kg bar load cell, R385 pump, KY-019 relay, PATIKIL 27 mm bellows cup, 4 mm silicone tubing, 12 V 3 A adapter, 5 × 608ZZ (4 rollers + the slider contact ring), 50 M3 heat-set inserts (≈ 20 used), M3 screw/nut/nylock assortment, M2.5 standoff kit, WS2812B ring, Arducam IMX708 + 150 mm Zero ribbon, Dupont jumpers, 22 AWG wire, soldering iron.

Owned but unused by B: N20 motors, L9110S ×3, 2 × LM2596, 12 V 2 A adapter, 16 mm O-rings, 8 mm rods, 2 MG996R spares.

## Printed

≈ 0.9 kg solid volume (≈ 0.6–0.7 kg printed): 7 bins, hopper, bed + cell block, yaw base, turntable/mast, 2 links, hand, slider, camera tower, ring holder, 4 feet, 4 roller sleeves. Largest part: link A, 238 mm (fits the 256 bed). v2 needed ≈ 4 kg.
