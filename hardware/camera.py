"""
Pi Camera Module capture for card identification.
Returns JPEG bytes of the card face, cropped to card region.

Requires: picamera2
"""

import io
import time
from PIL import Image

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


def capture_card_jpeg() -> bytes:
    """
    Capture a full frame, crop to card region, return JPEG bytes.
    """
    time.sleep(STABILIZE_DELAY_S)
    buf = io.BytesIO()
    arr = _cam.capture_array()
    img = Image.fromarray(arr)
    cropped = img.crop(CARD_CROP)
    cropped.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def capture_full_jpeg() -> bytes:
    """Full uncropped frame (for calibration)."""
    buf = io.BytesIO()
    arr = _cam.capture_array()
    img = Image.fromarray(arr)
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def set_crop(left, top, right, bottom):
    """Update card crop region at runtime."""
    global CARD_CROP
    CARD_CROP = (left, top, right, bottom)
    print(f"[camera] Crop updated: {CARD_CROP}")


def deinit():
    if _cam:
        _cam.stop()
        _cam.close()
