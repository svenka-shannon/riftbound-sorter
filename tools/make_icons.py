#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow>=10.1"]
# ///
"""
Generate the phone app's icons (web/static/icons/): a fan of three cards over
the turntable arc on a dark background.

  uv run tools/make_icons.py            # writes the PNGs (committed)
  uv run tools/make_icons.py --out DIR

  icon-192.png, icon-512.png     manifest "any" icons (full bleed, iOS / Android round them)
  icon-maskable-512.png          manifest "maskable": glyph inside the 80 % safe zone
  apple-touch-icon.png (180)     iOS home screen (no transparency)
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SS = 1024                                     # draw at this size, then downsample

BG_TOP, BG_BOTTOM = (16, 22, 34), (31, 45, 74)
CARDS = [((46, 168, 160), -24), ((214, 178, 92), 24), ((59, 130, 246), 0)]   # drawn in this order
EDGE = (236, 242, 248)


def _background() -> Image.Image:
    img = Image.new("RGB", (SS, SS))
    d = ImageDraw.Draw(img)
    for y in range(SS):
        t = y / (SS - 1)
        d.line([(0, y), (SS, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)))
    return img.convert("RGBA")


def _cards() -> Image.Image:
    """Transparent SS×SS layer with the three fanned cards (full size)."""
    layer = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    cx, pivot_y = SS / 2, SS * 0.95                       # cards fan around a point low down
    cw, ch = 300, 420
    for i, (colour, angle) in enumerate(CARDS):
        card = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        box = (cx - cw / 2, pivot_y - ch - 150, cx + cw / 2, pivot_y - 150)
        cd.rounded_rectangle(box, radius=34, fill=colour + (255,), outline=EDGE + (255,), width=16)
        if i == len(CARDS) - 1:                           # front card: inner frame
            inner = (box[0] + 46, box[1] + 46, box[2] - 46, box[3] - 46)
            cd.rounded_rectangle(inner, radius=18, outline=(150, 190, 250, 255), width=8)
        layer.alpha_composite(card.rotate(angle, resample=Image.BICUBIC, center=(cx, pivot_y)))
    return layer.crop(layer.getbbox())


def render(size: int, glyph_scale: float) -> Image.Image:
    """glyph_scale: the card fan's width as a fraction of the icon."""
    img = _background()
    cards = _cards()
    w = round(SS * glyph_scale * 0.78)
    h = round(cards.height * w / cards.width)
    cards = cards.resize((w, h), Image.LANCZOS)
    arc_h = round(h * 0.16)
    top = round((SS - h - arc_h) / 2)
    d = ImageDraw.Draw(img)                               # turntable arc under the fan
    r = w * 0.62
    cx, cy = SS / 2, top + h - r * 0.55
    d.arc((cx - r, cy - r, cx + r, cy + r), 35, 145, fill=(120, 140, 170, 255),
          width=max(2, round(30 * glyph_scale)))
    img.alpha_composite(cards, (round((SS - w) / 2), top))
    return img.convert("RGB").resize((size, size), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--out", type=Path, default=ROOT / "web" / "static" / "icons")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    outputs = {"icon-192.png": (192, 0.9), "icon-512.png": (512, 0.9),
               "icon-maskable-512.png": (512, 0.66), "apple-touch-icon.png": (180, 0.92)}
    for name, (size, scale) in outputs.items():
        path = args.out / name
        render(size, scale).save(path, optimize=True)
        print(f"wrote {path} ({size}x{size})")


if __name__ == "__main__":
    main()
