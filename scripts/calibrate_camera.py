#!/usr/bin/env python3
"""
Camera crop calibration helper.
Run this interactively to find the correct CARD_CROP coordinates
for your physical scanner station setup.

Usage:
  python scripts/calibrate_camera.py

Saves calibration to: config/camera_crop.json
"""

import json
import io
import time
from pathlib import Path

try:
    from picamera2 import Picamera2
    from PIL import Image
    import numpy as np
except ImportError:
    print("Install: pip install picamera2 Pillow numpy")
    raise

CROP_FILE = Path("config/camera_crop.json")

def capture_full(cam) -> Image.Image:
    arr = cam.capture_array()
    return Image.fromarray(arr)

def auto_detect_card(img: Image.Image) -> tuple[int,int,int,int] | None:
    """
    Try to auto-detect card edges using contrast.
    Returns (left, top, right, bottom) or None.
    """
    import numpy as np
    gray = np.array(img.convert("L"), dtype=float)

    # Vertical/horizontal edge sums
    col_var = np.var(gray, axis=0)
    row_var = np.var(gray, axis=1)

    thresh = 50
    cols = np.where(col_var > thresh)[0]
    rows = np.where(row_var > thresh)[0]

    if len(cols) < 10 or len(rows) < 10:
        return None

    margin = 5
    return (
        max(0, int(cols[0]) - margin),
        max(0, int(rows[0]) - margin),
        min(img.width,  int(cols[-1]) + margin),
        min(img.height, int(rows[-1]) + margin),
    )

def main():
    print("=== Camera Crop Calibration ===")
    print("Place a Riftbound card face-up in the scanner station.")
    print()

    cam = Picamera2()
    config = cam.create_still_configuration(
        main={"size": (640, 480), "format": "RGB888"}
    )
    cam.configure(config)
    cam.start()
    time.sleep(1.5)

    print("Capturing full frame... ", end="", flush=True)
    img = capture_full(cam)
    img.save("/tmp/calibration_full.jpg")
    print("saved to /tmp/calibration_full.jpg")

    auto = auto_detect_card(img)
    if auto:
        l, t, r, b = auto
        print(f"\nAuto-detected card region: left={l}, top={t}, right={r}, bottom={b}")
        print(f"Card size in frame: {r-l}×{b-t}px")

        # Save crop preview
        cropped = img.crop(auto)
        cropped.save("/tmp/calibration_crop.jpg")
        print("Crop preview saved to /tmp/calibration_crop.jpg")

        confirm = input("\nUse this crop? [Y/n]: ").strip().lower()
        if confirm in ("", "y", "yes"):
            crop = {"left": l, "top": t, "right": r, "bottom": b}
        else:
            crop = manual_entry()
    else:
        print("\nAuto-detect failed — please enter crop manually.")
        print("Open /tmp/calibration_full.jpg and find card corner pixel coords.")
        crop = manual_entry()

    CROP_FILE.parent.mkdir(exist_ok=True)
    CROP_FILE.write_text(json.dumps(crop, indent=2))
    print(f"\n✅ Saved crop to {CROP_FILE}: {crop}")
    print("Update hardware/camera.py CARD_CROP with these values.")

    cam.stop()
    cam.close()


def manual_entry() -> dict:
    print("Enter crop boundaries (pixel coordinates in 640×480 frame):")
    l = int(input("  left:   "))
    t = int(input("  top:    "))
    r = int(input("  right:  "))
    b = int(input("  bottom: "))
    return {"left": l, "top": t, "right": r, "bottom": b}


if __name__ == "__main__":
    main()
