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

Sensor mode (audit B2): picamera2 picks the sensor mode closest to the MAIN
stream size unless told otherwise, and for a 768×432 main that is the IMX708's
1536×864 mode — a centre 2/3 crop of the sensor (86.6 × 49.9 mm at the card
instead of 129.9 × 74.8 mm). init() therefore forces the 2×2-binned full-FOV
mode with sensor={"output_size": SENSOR_MODE} (picamera2 accepts only the keys
"output_size" and "bit_depth" there). That mode runs at up to ~56 fps, so
DETECT_FPS is 50. After start-up init() reads back the configured sensor mode
and the ScalerCrop metadata, derives FOV_X_MM / FOV_Y_MM (hence every mm-per-
pixel figure in card_detect) from the crop actually in use, and warns loudly
if it is not the full field.

Streams (continuous preview configuration so the lores loop runs at the full
DETECT_FPS frame rate):
  main  CAPTURE_RESOLUTION, RGB888   → capture_card_jpeg(), capture_full_jpeg()
  lores LORES_RESOLUTION,   YUV420   → capture_lores_luma() (Y plane only)
Both are 16:9 on purpose: the 66° × 41° FOV is the sensor's full 16:9 field.
A 4:3 output (the old 640×480) makes the ISP crop the sides.

Focus and exposure (audit M3), config/machine.json "camera" section (all
keys optional, see hardware/machine_config.py):
  {"LENS_POSITION": 10.0,      # dioptres = 1 / distance in m (100 mm → 10.0)
   "AF_MODE": "manual",        # "manual" (fixed LensPosition) or "continuous"
   "LOCK_AE_AWB": true,        # freeze exposure + white balance after warm-up
   "EXPOSURE_TIME_US": null,   # optional fixed values instead of the AE result
   "ANALOGUE_GAIN": null,
   "COLOUR_GAINS": null,       # [red, blue]
   "CARD_ROTATE": 90}          # 270 if cards are loaded the other way round
The lens is set to Manual at LensPosition (libcamera controls AfMode /
LensPosition). After a warm-up with AE/AWB running on the EMPTY station, the
converged ExposureTime / AnalogueGain / ColourGains are read from the frame
metadata and frozen (AeEnable / AwbEnable False), so the empty-station
reference frame card_detect subtracts stays valid while a bright card enters.

Requires: picamera2 + libcamera (Raspberry Pi OS packages python3-picamera2,
python3-libcamera — not pip; see scripts/setup.sh)
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
# Full sensor field at the card face (lens 100 mm above it): 66° × 41°.
FULL_FOV_X_MM = 129.9       # along card travel (2 × 100 × tan 33°)
FULL_FOV_Y_MM = 74.8        # across the belt
PIXEL_ARRAY = (4608, 2592)  # IMX708 (Camera Module 3); read back from the camera at init()
# Field actually imaged = FULL_FOV × (ScalerCrop / pixel array). init() sets these
# from the crop in use; the defaults assume the full field (true for SENSOR_MODE).
FOV_X_MM = FULL_FOV_X_MM
FOV_Y_MM = FULL_FOV_Y_MM
FULL_FOV_MIN_FRACTION = 0.97   # crop narrower than this × the sensor → warn
CARD_L_MM = 88.0            # card length, along X / image width
CARD_W_MM = 63.0            # card width,  along Y / image height

# ── Capture settings ─────────────────────────────────────────────────────────
SENSOR_MODE        = (2304, 1296) # IMX708 2×2 binned, FULL field of view, ≤ 56 fps
CAPTURE_RESOLUTION = (768, 432)   # main stream, 16:9 → ~5.9 px/mm
LORES_RESOLUTION   = (320, 180)   # lores stream for card_detect, ~2.5 px/mm
DETECT_FPS         = 50           # lores loop rate (binned full-FOV mode max ~56 fps)
WARMUP_S           = 1.0          # AE/AWB converge on the empty station before locking
LENS_POSITION      = 10.0         # dioptres: 1 / 0.100 m (card face 100 mm below the lens)
AF_MODE            = "manual"
LOCK_AE_AWB        = True
EXPOSURE_TIME_US   = None         # fixed exposure instead of the converged AE value
ANALOGUE_GAIN      = None
COLOUR_GAINS       = None
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
_crop_calibrated = False   # True once CARD_CROP came from config/camera_crop.json

_cam = None
_hw_flip = False      # True when the ISP already applies the 180° transform
SENSOR_INFO = {}      # what init() read back: sensor mode, ScalerCrop, FOV, controls


def _load_settings() -> None:
    """config/machine.json "camera" overrides (see module docstring)."""
    import sys
    from hardware import machine_config
    machine_config.apply(sys.modules[__name__], "camera", (
        "LENS_POSITION", "AF_MODE", "LOCK_AE_AWB", "EXPOSURE_TIME_US", "ANALOGUE_GAIN",
        "COLOUR_GAINS", "CARD_ROTATE", "STABILIZE_DELAY_S", "WARMUP_S", "SWAP_RB"))


_load_settings()


def apply_field_of_view(crop, pixel_array=None) -> float:
    """Set FOV_X_MM / FOV_Y_MM from the ScalerCrop (x, y, w, h) in use and
    return the fraction of the sensor width it covers. Re-derives the default
    CARD_CROP if no calibrated crop was loaded."""
    global FOV_X_MM, FOV_Y_MM, CARD_CROP
    aw, ah = pixel_array or PIXEL_ARRAY
    fx = crop[2] / aw
    fy = crop[3] / ah
    FOV_X_MM = FULL_FOV_X_MM * fx
    FOV_Y_MM = FULL_FOV_Y_MM * fy
    if not _crop_calibrated:
        CARD_CROP = _default_crop()
    return fx


def _focus_controls() -> dict:
    try:
        from libcamera import controls as lc
    except ImportError:
        return {}
    if AF_MODE == "continuous":
        return {"AfMode": lc.AfModeEnum.Continuous}
    return {"AfMode": lc.AfModeEnum.Manual, "LensPosition": float(LENS_POSITION)}


def _verify_sensor_mode() -> None:
    """Read back the sensor mode + ScalerCrop, derive the FOV, warn if cropped."""
    global PIXEL_ARRAY
    sensor = (_cam.camera_configuration() or {}).get("sensor") or {}
    md = _cam.capture_metadata()
    props = getattr(_cam, "camera_properties", {}) or {}
    active = props.get("PixelArrayActiveAreas")
    if active:
        PIXEL_ARRAY = (int(active[0][2]), int(active[0][3]))
    elif props.get("PixelArraySize"):
        PIXEL_ARRAY = tuple(int(v) for v in props["PixelArraySize"])
    crop = md.get("ScalerCrop")
    out = tuple(sensor.get("output_size") or ())
    SENSOR_INFO.update(sensor_mode=out, bit_depth=sensor.get("bit_depth"),
                       scaler_crop=tuple(crop) if crop else None, pixel_array=PIXEL_ARRAY)
    if crop is None:
        print("[camera] WARNING: no ScalerCrop in the frame metadata — cannot verify the field "
              f"of view; assuming the full field ({FOV_X_MM:.1f} × {FOV_Y_MM:.1f} mm)")
        return
    frac = apply_field_of_view(crop, PIXEL_ARRAY)
    SENSOR_INFO.update(fov_mm=(round(FOV_X_MM, 1), round(FOV_Y_MM, 1)))
    print(f"[camera] sensor mode {out} ({sensor.get('bit_depth')}-bit), ScalerCrop {tuple(crop)} of "
          f"{PIXEL_ARRAY} → field {FOV_X_MM:.1f} × {FOV_Y_MM:.1f} mm at the card")
    if out != tuple(SENSOR_MODE) or frac < FULL_FOV_MIN_FRACTION:
        print(f"[camera] WARNING: NOT the full field of view (wanted sensor mode {SENSOR_MODE}, "
              f"crop covers {frac:.0%} of the sensor width). Card centring loses its margin "
              "around the 88 mm card; mm/pixel figures were rescaled to the crop in use.")


def _lock_exposure() -> None:
    """Freeze AE/AWB at the values they converged to on the empty station
    (or the fixed values from config/machine.json)."""
    md = _cam.capture_metadata()
    exp = EXPOSURE_TIME_US or md.get("ExposureTime")
    gain = ANALOGUE_GAIN or md.get("AnalogueGain")
    cg = COLOUR_GAINS or md.get("ColourGains")
    ctl = {"AeEnable": False, "AwbEnable": False}
    if exp:
        ctl["ExposureTime"] = int(exp)
    if gain:
        ctl["AnalogueGain"] = float(gain)
    if cg:
        ctl["ColourGains"] = (float(cg[0]), float(cg[1]))
    _cam.set_controls(ctl)
    SENSOR_INFO.update(exposure_us=ctl.get("ExposureTime"), analogue_gain=ctl.get("AnalogueGain"),
                       colour_gains=ctl.get("ColourGains"))
    print(f"[camera] AE/AWB locked: exposure {ctl.get('ExposureTime')} µs, gain "
          f"{ctl.get('AnalogueGain')}, colour gains {ctl.get('ColourGains')}")


def init():
    global _cam, _hw_flip
    load_crop_config()
    if _MOCK:
        print("[camera] MOCK mode — captures return a blank JPEG")
        return
    if Picamera2 is None:
        raise ImportError("picamera2 missing: sudo apt install python3-picamera2 (and create the "
                          "venv with --system-site-packages, see scripts/setup.sh)")
    _cam = Picamera2()
    kwargs = {}
    if ROTATE_180 and Transform is not None:
        kwargs["transform"] = Transform(hflip=1, vflip=1)
        _hw_flip = True
    config = _cam.create_preview_configuration(
        main={"size": CAPTURE_RESOLUTION, "format": "RGB888"},
        lores={"size": LORES_RESOLUTION, "format": "YUV420"},
        sensor={"output_size": SENSOR_MODE},     # full-FOV binned mode, not the 1536×864 crop
        buffer_count=4,
        controls={"FrameRate": DETECT_FPS, **_focus_controls()},
        **kwargs,
    )
    _cam.configure(config)
    _cam.start()
    time.sleep(WARMUP_S)  # warm-up (AE/AWB converge, lens moves to LensPosition)
    _verify_sensor_mode()
    if LOCK_AE_AWB:
        _lock_exposure()
    flip = "ISP" if _hw_flip else ("software" if ROTATE_180 else "off")
    focus = f"manual {LENS_POSITION:g} dpt" if AF_MODE != "continuous" else "continuous AF"
    print(f"[camera] Pi Camera initialized (main {CAPTURE_RESOLUTION}, lores {LORES_RESOLUTION}, "
          f"{DETECT_FPS} fps, focus {focus}, 180° flip: {flip})")


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
    global CARD_CROP, _crop_calibrated
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
        _crop_calibrated = True
        print(f"[camera] Loaded crop calibration from {_CROP_FILE}: {CARD_CROP}")
    except Exception as e:
        print(f"[camera] Warning: could not load {_CROP_FILE}: {e}")


def set_crop(left, top, right, bottom, save: bool = False):
    """Update the card crop (flipped-frame pixels); save=True writes the config file."""
    global CARD_CROP, _crop_calibrated
    CARD_CROP = (int(left), int(top), int(right), int(bottom))
    _crop_calibrated = True
    print(f"[camera] Crop updated: {CARD_CROP}")
    if save:
        _CROP_FILE.parent.mkdir(parents=True, exist_ok=True)
        l, t, r, b = CARD_CROP
        _CROP_FILE.write_text(json.dumps({
            "left": l, "top": t, "right": r, "bottom": b,
            "resolution": list(CAPTURE_RESOLUTION), "rotate180": ROTATE_180,
        }, indent=2))


def deinit():
    global _cam
    if _MOCK or not _cam:
        return
    cam, _cam = _cam, None
    try:
        cam.stop()
    finally:
        cam.close()
