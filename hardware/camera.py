"""
Pi Camera Module 3 capture for card identification and card centring.

Mounting (cad/camera_bracket.scad): lens-down, 100 mm above the card face at
machine X +5, the image's long (66°) axis along the card travel (X). The
bracket turns the module 180° about Z, so every frame is flipped horizontally
AND vertically (ROTATE_180). This is done once in the ISP via
libcamera.Transform(hflip=1, vflip=1), which applies to BOTH the main stream
(identification) and the lores stream (hardware/card_detect.py); if Transform
is unavailable the same flip is applied in software. CARD_CROP is always in
the flipped (upright) frame.

Streams (continuous preview configuration so the lores loop runs at the full
DETECT_FPS frame rate):
  main  CAPTURE_RESOLUTION, RGB888   → capture_card_jpeg(), capture_full_jpeg()
  lores LORES_RESOLUTION,   YUV420   → capture_lores_luma() (Y plane only)
Both are 16:9 on purpose: the 66° × 41° FOV is the sensor's full 16:9 field.
A 4:3 output (the old 640×480) makes the ISP crop the sides, shrinking the
field along X from ~130 mm to ~97 mm — only ±4.7 mm of margin around an 88 mm
card instead of ±21 mm.

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

try:
    from libcamera import Transform
except ImportError:
    Transform = None

_CROP_FILE = Path(__file__).parent.parent / "config" / "camera_crop.json"

# ── Optics (cad/camera_bracket.scad) ─────────────────────────────────────────
FOV_X_MM = 129.9            # field along card travel at the card face (66°, 100 mm)
FOV_Y_MM = 74.8             # field across the belt (41°)
CARD_L_MM = 88.0            # card length, along X / image width
CARD_W_MM = 63.0            # card width,  along Y / image height

# ── Capture settings ─────────────────────────────────────────────────────────
CAPTURE_RESOLUTION = (768, 432)   # main stream, 16:9 → ~5.9 px/mm
LORES_RESOLUTION   = (320, 180)   # lores stream for card_detect, ~2.5 px/mm
DETECT_FPS         = 60           # lores loop rate (IMX708 binned 16:9 mode does 120)
ROTATE_180         = True         # camera mounted rotated 180° (bracket)
SWAP_RB            = True         # picamera2 "RGB888" arrays are ordered [B, G, R]
CARD_ROTATE        = 90           # PIL rotate() degrees (CCW) applied to the landscape
                                  # crop so the card is upright like the reference art;
                                  # use 270 if cards are loaded the other way round
STABILIZE_DELAY_S  = 0.15         # belt stopped → wait for motion blur / AE to settle


def _default_crop(size=CAPTURE_RESOLUTION) -> tuple[int, int, int, int]:
    """Card-sized box centred in the frame (card centred under the lens)."""
    w, h = size
    half_x = CARD_L_MM / 2 * w / FOV_X_MM
    half_y = CARD_W_MM / 2 * h / FOV_Y_MM
    cx, cy = w / 2, h / 2
    return (max(0, round(cx - half_x)), max(0, round(cy - half_y)),
            min(w, round(cx + half_x)), min(h, round(cy + half_y)))


# (left, top, right, bottom) in the flipped CAPTURE_RESOLUTION frame
CARD_CROP = _default_crop()

_cam = None
_hw_flip = False      # True when the ISP already applies the 180° transform


def init():
    global _cam, _hw_flip
    load_crop_config()
    if _MOCK:
        print("[camera] MOCK mode — captures return a blank JPEG")
        return
    if Picamera2 is None:
        raise ImportError("Install picamera2: pip install picamera2")
    _cam = Picamera2()
    kwargs = {}
    if ROTATE_180 and Transform is not None:
        kwargs["transform"] = Transform(hflip=1, vflip=1)
        _hw_flip = True
    config = _cam.create_preview_configuration(
        main={"size": CAPTURE_RESOLUTION, "format": "RGB888"},
        lores={"size": LORES_RESOLUTION, "format": "YUV420"},
        buffer_count=4,
        controls={"FrameRate": DETECT_FPS},
        **kwargs,
    )
    _cam.configure(config)
    _cam.start()
    time.sleep(1.0)  # warm-up (AE/AWB converge)
    flip = "ISP" if _hw_flip else ("software" if ROTATE_180 else "off")
    print(f"[camera] Pi Camera initialized (main {CAPTURE_RESOLUTION}, lores {LORES_RESOLUTION}, "
          f"180° flip: {flip})")


def _flip(arr):
    """Rotate 180° (= hflip + vflip) in software when the ISP did not."""
    if ROTATE_180 and not _hw_flip:
        return arr[::-1, ::-1]
    return arr


def _main_image() -> Image.Image:
    arr = _flip(_cam.capture_array("main"))
    if SWAP_RB:
        arr = arr[..., 2::-1]       # BGR → RGB (drops a 4th channel if present)
    return Image.fromarray(arr.copy())


def _blank_jpeg(width: int = 400, height: int = 540) -> bytes:
    """Return a small blank JPEG for mock/stub use."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(200, 200, 200)).save(buf, format="JPEG")
    return buf.getvalue()


def _shifted_crop(shift_px: int) -> tuple[int, int, int, int]:
    """CARD_CROP moved `shift_px` columns, clamped inside the frame."""
    l, t, r, b = CARD_CROP
    w = CAPTURE_RESOLUTION[0]
    shift_px = max(-l, min(w - r, int(round(shift_px))))
    return (l + shift_px, t, r + shift_px, b)


def capture_card_jpeg(shift_px: float = 0) -> bytes:
    """
    Capture a main-stream frame, crop to the card, turn it upright, return JPEG.
    shift_px: move the crop along the image width (card travel) by this many
    main-stream pixels — card_detect.crop_shift_px() turns the residual
    centring error into this, so the crop follows the card.
    """
    if _MOCK:
        return _blank_jpeg()
    time.sleep(STABILIZE_DELAY_S)
    img = _main_image().crop(_shifted_crop(shift_px))
    if CARD_ROTATE % 360:
        img = img.rotate(CARD_ROTATE, expand=True)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def capture_full_jpeg() -> bytes:
    """Full uncropped (flipped) main frame, for calibration."""
    if _MOCK:
        return _blank_jpeg(*CAPTURE_RESOLUTION)
    buf = io.BytesIO()
    _main_image().save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def capture_lores_luma():
    """Next lores frame as a 2-D uint8 numpy array (Y plane), flipped like main.
    Blocks until the next frame (~1/DETECT_FPS). Not available in MOCK mode —
    card_detect generates synthetic frames there."""
    if _MOCK or _cam is None:
        raise RuntimeError("capture_lores_luma() needs the real camera (MOCK mode uses card_detect's mock scene)")
    w, h = LORES_RESOLUTION
    yuv = _cam.capture_array("lores")       # YUV420: Y plane is the first h rows
    return _flip(yuv[:h, :w])


def load_crop_config():
    """
    Load config/camera_crop.json if present:
      {"left":..,"top":..,"right":..,"bottom":.., "resolution":[w,h], "rotate180": true}
    "rotate180": true means the box was measured in the flipped frame. A file
    without it (written by the old scripts/calibrate_camera.py, unflipped) is
    turned 180° here. A file for a different resolution is ignored (re-calibrate);
    files without "resolution" are assumed to be 640×480.
    """
    global CARD_CROP
    if not _CROP_FILE.exists():
        return
    try:
        data = json.loads(_CROP_FILE.read_text())
        crop = (int(data["left"]), int(data["top"]), int(data["right"]), int(data["bottom"]))
        res = tuple(data.get("resolution", (640, 480)))
        if res != tuple(CAPTURE_RESOLUTION):
            print(f"[camera] Warning: {_CROP_FILE} is for {res[0]}×{res[1]}, capture is "
                  f"{CAPTURE_RESOLUTION[0]}×{CAPTURE_RESOLUTION[1]} — ignored, using the "
                  f"geometric default {CARD_CROP}. Re-calibrate the crop.")
            return
        if ROTATE_180 and not data.get("rotate180", False):
            w, h = res
            l, t, r, b = crop
            crop = (w - r, h - b, w - l, h - t)
            print("[camera] crop file was measured unflipped — rotated 180° to match the mount")
        CARD_CROP = crop
        print(f"[camera] Loaded crop calibration from {_CROP_FILE}: {CARD_CROP}")
    except Exception as e:
        print(f"[camera] Warning: could not load {_CROP_FILE}: {e}")


def set_crop(left, top, right, bottom, save: bool = False):
    """Update the card crop (flipped-frame pixels); save=True writes the config file."""
    global CARD_CROP
    CARD_CROP = (int(left), int(top), int(right), int(bottom))
    print(f"[camera] Crop updated: {CARD_CROP}")
    if save:
        _CROP_FILE.parent.mkdir(parents=True, exist_ok=True)
        l, t, r, b = CARD_CROP
        _CROP_FILE.write_text(json.dumps({
            "left": l, "top": t, "right": r, "bottom": b,
            "resolution": list(CAPTURE_RESOLUTION), "rotate180": ROTATE_180,
        }, indent=2))


def deinit():
    if _MOCK or not _cam:
        return
    _cam.stop()
    _cam.close()
