"""
Pi Camera Module capture for card identification.
Returns JPEG bytes of the card face, cropped to card region.

Requires: picamera2
"""

import io
import json
import os
import time
from pathlib import Path
from PIL import Image

_MOCK = os.environ.get("MOCK_HARDWARE", "0") == "1"

try:
    from picamera2 import Picamera2
except ImportError:
    Picamera2 = None

# Crop region for card face (pixels, tuned after physical setup)
# Calibrate by taking a full frame and measuring card corners
CARD_CROP = (120, 80, 520, 620)   # (left, top, right, bottom) in 640×480

# Capture settings
CAPTURE_RESOLUTION = (640, 480)
CAPTURE_FORMAT     = "JPEG"
STABILIZE_DELAY_S  = 0.15   # wait for auto-exposure after card arrives

_cam = None


def init():
    global _cam
    if _MOCK:
        print("[camera] MOCK mode — captures will return a blank JPEG")
        return
    if Picamera2 is None:
        raise ImportError("Install picamera2: pip install picamera2")
    _cam = Picamera2()
    config = _cam.create_still_configuration(
        main={"size": CAPTURE_RESOLUTION, "format": "RGB888"},
        lores={"size": (320, 240), "format": "YUV420"},
        display="lores",
    )
    _cam.configure(config)
    _cam.start()
    time.sleep(1.0)  # warm-up
    print("[camera] Pi Camera initialized")
    load_crop_config()


def _blank_jpeg(width: int = 400, height: int = 540) -> bytes:
    """Return a small blank JPEG for mock/stub use."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(200, 200, 200)).save(buf, format="JPEG")
    return buf.getvalue()


def capture_card_jpeg() -> bytes:
    """
    Capture a full frame, crop to card region, return JPEG bytes.
    """
    if _MOCK:
        return _blank_jpeg()
    time.sleep(STABILIZE_DELAY_S)
    buf = io.BytesIO()
    arr = _cam.capture_array()
    img = Image.fromarray(arr)
    cropped = img.crop(CARD_CROP)
    cropped.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def capture_full_jpeg() -> bytes:
    """Full uncropped frame (for calibration)."""
    if _MOCK:
        return _blank_jpeg(640, 480)
    buf = io.BytesIO()
    arr = _cam.capture_array()
    img = Image.fromarray(arr)
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def load_crop_config():
    """
    Load saved crop calibration from config/camera_crop.json if it exists.
    Overrides CARD_CROP with the saved (left, top, right, bottom) values.
    Path is resolved relative to the project root (parent of the hardware/ dir).
    """
    global CARD_CROP
    cfg_path = Path(__file__).parent.parent / "config" / "camera_crop.json"
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text())
            CARD_CROP = (data["left"], data["top"], data["right"], data["bottom"])
            print(f"[camera] Loaded crop calibration from {cfg_path}: {CARD_CROP}")
        except Exception as e:
            print(f"[camera] Warning: could not load {cfg_path}: {e}")


def set_crop(left, top, right, bottom):
    """Update card crop region at runtime."""
    global CARD_CROP
    CARD_CROP = (left, top, right, bottom)
    print(f"[camera] Crop updated: {CARD_CROP}")


def deinit():
    if _MOCK or not _cam:
        return
    _cam.stop()
    _cam.close()
