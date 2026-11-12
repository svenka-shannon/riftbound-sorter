#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy"]
# ///
"""
Camera crop calibration for the scanner station.

Uses hardware/camera.py directly — the same capture the sorter uses
(capture_full_jpeg(): main stream, flipped 180° for the bracket, 16:9
CAPTURE_RESOLUTION) — and saves with camera.set_crop(..., save=True), so
config/camera_crop.json is exactly what camera.load_crop_config() reads:
    {"left": L, "top": T, "right": R, "bottom": B,
     "resolution": [768, 432], "rotate180": true}
Coordinates are pixels in the flipped (upright) main frame.

Usage:
    uv run scripts/calibrate_camera.py                 # MOCK (blank frames), anywhere
    venv/bin/python scripts/calibrate_camera.py --no-mock   # real camera (Pi venv)

Steps: capture the EMPTY station (reference), then a card centred under the
lens; the card is found by differencing the two. Previews (open them in an
image viewer / VNC after every change):
    /tmp/calibration_full.jpg     raw flipped frame with the card
    /tmp/calibration_overlay.jpg  green = crop box, yellow = auto-detected card
    /tmp/calibration_crop.jpg     the crop turned upright, as identification sees it

Commands:
    a            use the auto-detected box
    d            geometric default (card-sized box centred in the frame)
    m L T R B    type the box (or just 'm' to be asked)
    x N / y N    shift the box N px along the width / height
    c            re-capture the card frame
    s            save to config/camera_crop.json and quit
    q            quit without saving
"""

import argparse
import io
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
TMP = Path("/tmp")
FULL_JPG = TMP / "calibration_full.jpg"
OVERLAY_JPG = TMP / "calibration_overlay.jpg"
CROP_JPG = TMP / "calibration_crop.jpg"

DIFF_LEVEL = 25          # grey-level change that counts as "card here"
DIFF_FRACTION = 0.25     # a row/column is card if this share of its pixels changed
MIN_BOX_PX = 20

camera = None
_MOCK = True


class Quit(Exception):
    pass


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        print()
        raise Quit


def capture() -> Image.Image:
    img = Image.open(io.BytesIO(camera.capture_full_jpeg()))
    img.load()
    if img.size != tuple(camera.CAPTURE_RESOLUTION):
        print(f"  warning: frame is {img.size}, camera.CAPTURE_RESOLUTION is {camera.CAPTURE_RESOLUTION}")
    return img.convert("RGB")


def detect_card(reference: Image.Image, frame: Image.Image):
    """Bounding box (l, t, r, b) of what changed between the empty station and the card frame."""
    a = np.asarray(reference.convert("L"), dtype=np.int16)
    b = np.asarray(frame.convert("L"), dtype=np.int16)
    if a.shape != b.shape:
        return None
    changed = np.abs(b - a) > DIFF_LEVEL
    cols = np.where(changed.mean(axis=0) > DIFF_FRACTION)[0]
    rows = np.where(changed.mean(axis=1) > DIFF_FRACTION)[0]
    if len(cols) < MIN_BOX_PX or len(rows) < MIN_BOX_PX:
        return None
    return int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1


def clamp_box(box):
    w, h = camera.CAPTURE_RESOLUTION
    l, t, r, b = (int(round(v)) for v in box)
    l, r = max(0, min(l, w)), max(0, min(r, w))
    t, b = max(0, min(t, h)), max(0, min(b, h))
    if r - l < MIN_BOX_PX or b - t < MIN_BOX_PX:
        return None
    return l, t, r, b


def describe(box) -> str:
    w, h = camera.CAPTURE_RESOLUTION
    px_x, px_y = w / camera.FOV_X_MM, h / camera.FOV_Y_MM
    l, t, r, b = box
    off_x = ((l + r) / 2 - w / 2) / px_x
    off_y = ((t + b) / 2 - h / 2) / px_y
    return (f"({l}, {t}, {r}, {b})  {r - l}×{b - t} px = {(r - l) / px_x:.1f}×{(b - t) / px_y:.1f} mm "
            f"(card {camera.CARD_L_MM:g}×{camera.CARD_W_MM:g})  centre offset {off_x:+.1f}/{off_y:+.1f} mm")


def write_previews(frame: Image.Image, box, auto) -> None:
    frame.save(FULL_JPG, quality=90)
    over = frame.copy()
    draw = ImageDraw.Draw(over)
    if auto:
        draw.rectangle((auto[0], auto[1], auto[2] - 1, auto[3] - 1), outline=(255, 220, 0), width=1)
    draw.rectangle((box[0], box[1], box[2] - 1, box[3] - 1), outline=(0, 255, 0), width=2)
    w, h = frame.size
    draw.line((w // 2 - 8, h // 2, w // 2 + 8, h // 2), fill=(255, 0, 0))
    draw.line((w // 2, h // 2 - 8, w // 2, h // 2 + 8), fill=(255, 0, 0))
    over.save(OVERLAY_JPG, quality=90)
    crop = frame.crop(box)
    if camera.CARD_ROTATE % 360:
        crop = crop.rotate(camera.CARD_ROTATE, expand=True)
    crop.save(CROP_JPG, quality=90)
    print(f"  previews: {OVERLAY_JPG}  {CROP_JPG}")


def main() -> None:
    global camera, _MOCK
    parser = argparse.ArgumentParser(description="Calibrate the scanner-station card crop")
    parser.add_argument("--no-mock", action="store_true",
                        help="use the real Pi camera (default: MOCK_HARDWARE=1, blank frames)")
    args = parser.parse_args()
    _MOCK = not args.no_mock
    os.environ["MOCK_HARDWARE"] = "1" if _MOCK else "0"
    sys.path.insert(0, str(ROOT))
    from hardware import camera as _camera
    camera = _camera

    print(f"=== Camera crop calibration ({'MOCK — blank frames' if _MOCK else 'REAL camera'}) ===")
    camera.init()                       # loads config/camera_crop.json, starts the camera
    w, h = camera.CAPTURE_RESOLUTION
    print(f"  frame {w}×{h} (flipped 180°: {camera.ROTATE_180}), crop file {camera._CROP_FILE}")
    print(f"  current crop {describe(camera.CARD_CROP)}")
    saved = False
    try:
        print("\n  1) Empty scanner station: no card under the lens, hood closed.")
        reference = None
        if ask("     Enter to capture the reference ('n' to skip auto-detect): ").lower() != "n":
            reference = capture()
        print("  2) Place a card face-up on the belt, centred under the lens, against the guides.")
        ask("     Enter to capture... ")
        frame = capture()

        auto = detect_card(reference, frame) if reference is not None else None
        if auto:
            print(f"  auto-detected card {describe(auto)}")
        else:
            print("  no card found by differencing — use 'm' (read the corners off "
                  f"{FULL_JPG}) or 'd'")
        box = tuple(camera.CARD_CROP)
        write_previews(frame, box, auto)
        print("\n  a auto   d default   m L T R B   x N / y N shift   c re-capture   s save   q quit")

        while True:
            print(f"  crop {describe(box)}")
            cmd = ask("  > ")
            parts = cmd.split()
            c = parts[0].lower() if parts else ""
            new = None
            if c == "a":
                if not auto:
                    print("  nothing auto-detected")
                    continue
                new = auto
            elif c == "d":
                new = camera._default_crop()
            elif c == "m":
                nums = parts[1:] or ask("  left top right bottom: ").split()
                try:
                    new = tuple(int(v) for v in nums)
                except ValueError:
                    new = ()
                if len(new) != 4:
                    print("  need 4 integers: left top right bottom")
                    continue
            elif c in ("x", "y") and len(parts) == 2:
                try:
                    n = int(parts[1])
                except ValueError:
                    print("  x N / y N with an integer N")
                    continue
                l, t, r, b = box
                if c == "x":            # keep the size: stop at the frame edge
                    n = max(-l, min(w - r, n))
                    new = (l + n, t, r + n, b)
                else:
                    n = max(-t, min(h - b, n))
                    new = (l, t + n, r, b + n)
            elif c == "c":
                ask("  card in place? Enter to capture... ")
                frame = capture()
                auto = detect_card(reference, frame) if reference is not None else None
                print(f"  auto-detected card {describe(auto)}" if auto else "  no card found by differencing")
                write_previews(frame, box, auto)
                continue
            elif c == "s":
                camera.set_crop(*box, save=True)
                saved = True
                break
            elif c == "q":
                break
            else:
                print("  a auto   d default   m L T R B   x N / y N shift   c re-capture   s save   q quit")
                continue
            clamped = clamp_box(new)
            if clamped is None:
                print(f"  box {new} is outside the {w}×{h} frame or smaller than {MIN_BOX_PX} px")
                continue
            if clamped != tuple(new):
                print("  clamped to the frame")
            box = clamped
            write_previews(frame, box, auto)
    except Quit:
        pass
    finally:
        camera.deinit()

    if saved:
        camera.load_crop_config()       # read it back the way the sorter will
        print(f"\nSaved {camera._CROP_FILE}:\n{camera._CROP_FILE.read_text().rstrip()}")
        print(f"camera.load_crop_config() → CARD_CROP {camera.CARD_CROP}")
    else:
        print("\nNot saved.")


if __name__ == "__main__":
    main()
