"""
Card centring under the scanner (machine X +5, cad/machine_frame.scad cam_x).

The belt runs until the camera sees the card centred under the lens, then
brakes. Works on the camera's low-res (lores) Y stream at DETECT_FPS.

Detection (one lores frame):
  1. |frame − reference| per pixel, where the reference is a frame of the EMPTY
     station taken before the card is dropped (dark belt, round belts, guides,
     hood walls all cancel out). Only the middle BAND of rows is used, so the
     side guides never count.
  2. A column is "card" if ≥ COL_FRAC of its band pixels differ by > PIXEL_DIFF.
  3. Gaps ≤ GAP_MM (dark art on the card face) are closed and the longest run
     ≥ MIN_BLOB_MM is the card. Its two ends are the trailing/leading edges.
  4. Only the hood interior is visible (end walls at cam_x ± 50 mm,
     cad/scanner_hood.scad), so an end within EDGE_MARGIN_MM of the visible
     window (VIEW_HALF_MM) is not a real edge. Card centre:
       both edges real   → midpoint (if the length is within LEN_TOL_MM of 88)
       leading edge only → leading − 44 mm      (the usual case while seeking:
       trailing only     → trailing + 44 mm      the 88 mm card only fits the
                                                  ~96 mm window when centred)
  Offset = card centre − lens axis, mm along travel, + = past centre.

Seek (centre_card): run the belt, measure every frame, track belt speed from
successive frames, and brake when the predicted stopping point
    offset + speed·(STOP_LATENCY_S + ½ frame) + BRAKE_COAST_MM ≥ 0.
Then measure the stationary card; if it stopped short by > CENTER_TOL_MM, nudge
forward (≤ MAX_NUDGES). The belt never reverses, so a small overshoot is left
and the capture crop is shifted instead (crop_shift_px()).

Fail-safe: not seen within SEEK_TIMEOUT_S (or not centred within
SEEK_HARD_LIMIT_FACTOR × that), card lost after being seen, or card
far past centre → belt braked/stopped and the result is not ok (main.py treats
it as a jam). The belt is stopped on ANY exception.

Accuracy (assumptions): position error per frame ≈ lores pixel (0.4 mm) +
edge blur; the stopping error is dominated by speed × frame interval / 2
(150 mm/s, 50 fps → ±1.5 mm) plus brake coast variation (~±1 mm). The
stationary re-measure + nudge pulls a short stop back inside CENTER_TOL_MM;
an overshoot of up to MAX_CAPTURE_OFFSET_MM is absorbed by the crop shift.

Timing (camera at DETECT_FPS = 50 in the full-FOV 2304×1296 binned mode):
STOP_LATENCY_S is the age of the newest frame when the brake takes effect —
the frame is exposed mid-period, read out (one frame time) and handed to
Python through the request queue, then measured (~5 ms on a Zero 2W) — so
about 1.5 frame periods + processing ≈ 40 ms, not the 25 ms assumed at 60 fps.
Calibrate it: run test_hardware.py test 9 at the nominal belt speed and adjust
STOP_LATENCY_S until the mean stationary offset is ~0.

mm per pixel come from camera.FOV_X_MM, which camera.init() derives from the
sensor crop actually in use (so a cropped sensor mode cannot silently scale
every distance by 2/3). The usable window is the smaller of the hood interior
(VIEW_HALF_MM) and half the imaged field.

MOCK mode: frames are synthesised from MOCK_SCENE (a card moving at
MOCK_SCENE.speed_mm_s while the belt runs) on a simulated clock.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import numpy as np

from hardware import camera

_MOCK = os.environ.get("MOCK_HARDWARE", "0") == "1"

# ── Geometry (cad/machine_frame.scad, cad/scanner_hood.scad) ────────────────
CAM_X_MM = 5.0              # lens axis
DROP_X_MM = -95.0           # card centre where the arm releases it
BELT_END_X_MM = 85.0
CARD_L_MM = camera.CARD_L_MM
VIEW_HALF_MM = 48.0         # visible card plane: hood interior ±50 mm, less 2 mm
CENTRE_OFFSET_MM = 0.0      # lens axis − image centre along travel (calibrate)
TRAVEL_SIGN = +1            # +1: the card moves toward higher image columns in the
                            # (flipped) frame; −1 if it moves toward lower columns

# ── Detection ────────────────────────────────────────────────────────────────
BAND = (0.25, 0.75)         # rows used, as fractions of the height (skip guides)
PIXEL_DIFF = 30             # luma difference vs reference that counts as card
COL_FRAC = 0.30             # fraction of band pixels per column that must differ
GAP_MM = 8.0                # close gaps (dark card art) up to this length
MIN_BLOB_MM = 12.0          # ignore smaller blobs (dust, reflections)
EDGE_MARGIN_MM = 2.0        # an end this close to the window edge is not an edge
LEN_TOL_MM = 10.0           # both edges seen: length must be 88 ± this

# ── Belt / stopping ──────────────────────────────────────────────────────────
BELT_SPEED_MM_S = 150.0     # nominal belt speed at conveyor.DEFAULT_SPEED (calibrate)
STOP_LATENCY_S = 0.040      # frame exposure → brake taking effect (≈1.5 frames @ 50 fps + processing)
BRAKE_COAST_MM = 1.5        # travel after conveyor.brake()
CENTER_TOL_MM = 2.5         # stationary offset accepted without a nudge
MAX_NUDGES = 2
NUDGE_MIN_S = 0.01
SETTLE_S = 0.12             # after braking, before the stationary measurement
STATIONARY_FRAMES = 3       # median of this many frames for the final offset
LOST_FRAMES = 6             # card seen, then missing for this many frames → lost
OVERRUN_MM = 20.0           # card centre this far past the lens → stop, fail
MAX_CAPTURE_OFFSET_MM = 6.0  # |final offset| above this → result.ok is False
# Give up before the card can reach the belt end: drop centre X −95 → centre at
# X +30 is 125 mm (leading edge X 74 < belt end 85) at the nominal speed.
SEEK_MAX_TRAVEL_MM = 125.0
# Once the card is seen, a slower-than-nominal belt may take longer; LOST_FRAMES and
# OVERRUN_MM guard that phase, plus a hard cap of this many × SEEK_TIMEOUT_S.
SEEK_HARD_LIMIT_FACTOR = 3.0

# Per-machine calibration: config/machine.json "card_detect" section (code values above
# are the defaults).
import sys as _sys
from hardware import machine_config as _machine_config
_machine_config.apply(_sys.modules[__name__], "card_detect", (
    "TRAVEL_SIGN", "CENTRE_OFFSET_MM", "BELT_SPEED_MM_S", "BRAKE_COAST_MM", "STOP_LATENCY_S",
    "CENTER_TOL_MM", "MAX_CAPTURE_OFFSET_MM", "PIXEL_DIFF", "COL_FRAC", "VIEW_HALF_MM",
    "SEEK_MAX_TRAVEL_MM", "SEEK_HARD_LIMIT_FACTOR"))
SEEK_TIMEOUT_S = SEEK_MAX_TRAVEL_MM / BELT_SPEED_MM_S


def _mm_per_px(width: int) -> float:
    return camera.FOV_X_MM / width


def _view_half_mm() -> float:
    """Half-width of the usable window: hood interior, or the imaged field if narrower."""
    return min(VIEW_HALF_MM, camera.FOV_X_MM / 2 - 1.0)


def col_to_mm(col: float, width: int) -> float:
    """Lores column (pixel centre) → mm along travel relative to the lens axis."""
    return TRAVEL_SIGN * (col + 0.5 - width / 2) * _mm_per_px(width) - CENTRE_OFFSET_MM


def crop_shift_px(offset_mm: float) -> float:
    """Main-stream column shift that moves the capture crop onto a card that
    stopped `offset_mm` past centre (for camera.capture_card_jpeg)."""
    return TRAVEL_SIGN * offset_mm * camera.CAPTURE_RESOLUTION[0] / camera.FOV_X_MM


@dataclass
class Detection:
    found: bool
    centre_mm: float | None = None     # card centre − lens axis (+ = past centre)
    lead_mm: float | None = None       # leading-edge position (None = not a real edge)
    trail_mm: float | None = None
    length_ok: bool | None = None      # both edges seen and length ≈ 88 mm


@dataclass
class CentreResult:
    ok: bool                           # card centred within MAX_CAPTURE_OFFSET_MM
    reason: str                        # centred | off_centre | timeout | lost | overrun
    offset_mm: float | None = None     # final stationary offset (+ = past centre)
    speed_mm_s: float | None = None    # measured belt speed
    frames: int = 0
    elapsed_s: float = 0.0
    nudges: int = 0
    seen: bool = True                  # False: the card never appeared on the belt

    @property
    def jam(self) -> bool:
        return self.reason in ("timeout", "lost", "overrun")


def _runs(mask: np.ndarray) -> list[list[int]]:
    """[start, end) index pairs of True runs."""
    if not mask.any():
        return []
    m = np.concatenate(([False], mask, [False])).astype(np.int8)
    d = np.diff(m)
    return [list(p) for p in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1))]


def measure(luma: np.ndarray, reference: np.ndarray) -> Detection:
    """Locate the card in one lores luma frame (see module docstring)."""
    h, w = luma.shape
    r0, r1 = int(h * BAND[0]), max(int(h * BAND[1]), int(h * BAND[0]) + 1)
    diff = np.abs(luma[r0:r1].astype(np.int16) - reference[r0:r1].astype(np.int16)) > PIXEL_DIFF
    cols = diff.mean(axis=0) >= COL_FRAC
    pos = col_to_mm(np.arange(w), w)
    view_half = _view_half_mm()
    cols &= np.abs(pos) <= view_half

    mmpp = _mm_per_px(w)
    runs = _runs(cols)
    if not runs:
        return Detection(False)
    merged = [runs[0]]
    for s, e in runs[1:]:
        if (s - merged[-1][1]) * mmpp <= GAP_MM:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    s, e = max(merged, key=lambda r: r[1] - r[0])
    if (e - s) * mmpp < MIN_BLOB_MM:
        return Detection(False)

    a = col_to_mm(s - 0.5, w)      # outer boundaries of the end pixels
    b = col_to_mm(e - 0.5, w)
    trail, lead = min(a, b), max(a, b)
    lead_ok = lead < view_half - EDGE_MARGIN_MM
    trail_ok = trail > -view_half + EDGE_MARGIN_MM
    det = Detection(True,
                    lead_mm=lead if lead_ok else None,
                    trail_mm=trail if trail_ok else None)
    if lead_ok and trail_ok:
        det.length_ok = abs((lead - trail) - CARD_L_MM) <= LEN_TOL_MM
        det.centre_mm = (lead + trail) / 2 if det.length_ok else lead - CARD_L_MM / 2
    elif lead_ok:
        det.centre_mm = lead - CARD_L_MM / 2
    elif trail_ok:
        det.centre_mm = trail + CARD_L_MM / 2
    return det


# ── Frame sources ────────────────────────────────────────────────────────────
class CameraSource:
    """Real lores stream (hardware/camera.py) on the wall clock."""

    def now(self) -> float:
        return time.monotonic()

    def grab(self) -> np.ndarray:
        return camera.capture_lores_luma()

    def wait(self, seconds: float) -> None:
        time.sleep(seconds)

    def belt(self, running: bool, braked: bool = False) -> None:
        pass

    def begin(self) -> None:
        pass

    def reference(self) -> np.ndarray:
        self.grab()                                   # flush a frame
        frames = [self.grab().astype(np.int16) for _ in range(3)]
        return np.median(np.stack(frames), axis=0).astype(np.uint8)


class MockScene:
    """Synthetic scanner station: dark belt, guides, hood walls, one card.

    card_x_mm: card centre in MACHINE X (None = no card). While the belt runs
    the card moves at speed_mm_s; brake() adds latency + coast like the real one.
    auto_card: a seek with no card on the belt places one at the drop point
    (simulates a successful pick); set False to simulate a missed pick.
    """

    def __init__(self, size=None, seed: int = 1):
        self.size = size or camera.LORES_RESOLUTION
        self.rng = np.random.default_rng(seed)
        self.card_x_mm: float | None = None
        self.speed_mm_s = BELT_SPEED_MM_S * 1.1       # deliberately ≠ nominal
        self.coast_mm = BRAKE_COAST_MM
        self.latency_s = STOP_LATENCY_S
        self.dt = 1.0 / camera.DETECT_FPS
        self.running = False
        self.clock = 0.0
        self.auto_card = True
        self.visible = True            # False: card present but invisible to the camera
        self.dark_stripe_mm = 5.0      # dark art band across the card (tests gap closing)

    # simulated hardware
    def advance(self, seconds: float) -> None:
        if self.running and self.card_x_mm is not None:
            self.card_x_mm += self.speed_mm_s * seconds
        self.clock += seconds

    def set_belt(self, running: bool, braked: bool) -> None:
        if self.running and not running and self.card_x_mm is not None:
            self.card_x_mm += self.speed_mm_s * self.latency_s + (self.coast_mm if braked else 3.0)
        self.running = running

    def render(self, with_card: bool = True) -> np.ndarray:
        w, h = self.size
        img = np.full((h, w), 28.0)
        rows = np.arange(h)
        for frac in (0.3, 0.7):                       # two round belts along X
            img[np.abs(rows - frac * h) < h * 0.03] = 45.0
        img[rows < h * 0.08] = 70.0                   # side guides
        img[rows > h * 0.92] = 70.0
        pos = col_to_mm(np.arange(w), w)                      # mm rel. lens, along travel
        if with_card and self.visible and self.card_x_mm is not None:
            c = self.card_x_mm - CAM_X_MM
            on = np.abs(pos - c) <= CARD_L_MM / 2
            y_half = camera.CARD_W_MM / 2 * h / camera.FOV_Y_MM
            band = np.abs(rows - h / 2) <= y_half
            card = 150 + 60 * self.rng.random((h, w))
            stripe = np.abs(pos - (c + 10.0)) <= self.dark_stripe_mm / 2
            card[:, stripe] = 30.0
            m = band[:, None] & on[None, :]
            img[m] = card[m]
        img[:, np.abs(pos) > 50.0] = 8.0              # hood end walls hide the rest
        img += self.rng.normal(0, 3.0, img.shape)
        return np.clip(img, 0, 255).astype(np.uint8)


class MockSource:
    def __init__(self, scene: MockScene):
        self.scene = scene

    def now(self) -> float:
        return self.scene.clock

    def grab(self) -> np.ndarray:
        self.scene.advance(self.scene.dt)
        return self.scene.render()

    def wait(self, seconds: float) -> None:
        self.scene.advance(seconds)

    def belt(self, running: bool, braked: bool = False) -> None:
        self.scene.set_belt(running, braked)

    def begin(self) -> None:
        if self.scene.card_x_mm is None and self.scene.auto_card:
            self.scene.card_x_mm = DROP_X_MM

    def reference(self) -> np.ndarray:
        # The reference is taken with the station empty: the previous card has left.
        self.scene.card_x_mm = None
        return self.scene.render(with_card=False)


MOCK_SCENE = MockScene()


def default_source():
    return MockSource(MOCK_SCENE) if _MOCK else CameraSource()


def capture_reference(source=None) -> np.ndarray:
    """Frame of the EMPTY station. Take it before the card is dropped."""
    return (source or default_source()).reference()


def _stationary_offset(source, reference) -> float | None:
    source.wait(SETTLE_S)
    vals = []
    for _ in range(STATIONARY_FRAMES):
        d = measure(source.grab(), reference)
        if d.centre_mm is not None:
            vals.append(d.centre_mm)
    return float(np.median(vals)) if vals else None


def centre_card(reference: np.ndarray, run, brake, stop, source=None,
                timeout_s: float | None = None) -> CentreResult:
    """Run the belt until the card is centred under the lens, then brake.

    run/brake/stop: conveyor callables (conveyor.run, conveyor.brake, conveyor.stop).
    Returns a CentreResult; result.jam means stop the machine. The belt is
    never left running when this returns or raises.
    """
    source = source or default_source()
    timeout_s = SEEK_TIMEOUT_S if timeout_s is None else timeout_s
    frame_dt = 1.0 / camera.DETECT_FPS
    belt_on = False

    def _run():
        nonlocal belt_on
        run()
        belt_on = True
        source.belt(True)

    def _brake():
        nonlocal belt_on
        brake()
        belt_on = False
        source.belt(False, braked=True)

    source.begin()
    t0 = source.now()
    frames = 0
    speed = BELT_SPEED_MM_S
    speed_seen = None
    prev = None
    seen = False
    missing = 0
    try:
        _run()
        while True:
            waited = source.now() - t0
            if (not seen and waited > timeout_s) or waited > SEEK_HARD_LIMIT_FACTOR * timeout_s:
                _brake()
                return CentreResult(False, "timeout", None, speed_seen, frames, waited, seen=seen)
            luma = source.grab()
            t = source.now()
            frames += 1
            det = measure(luma, reference)
            if det.centre_mm is None:
                if seen:
                    missing += 1
                    if missing >= LOST_FRAMES:
                        _brake()
                        return CentreResult(False, "lost", None, speed_seen, frames, t - t0)
                continue
            seen, missing = True, 0
            if prev is not None and t > prev[1]:
                v = (det.centre_mm - prev[0]) / (t - prev[1])
                if 0.3 * BELT_SPEED_MM_S < v < 3.0 * BELT_SPEED_MM_S:
                    speed = v if speed_seen is None else 0.5 * speed + 0.5 * v
                    speed_seen = speed
            prev = (det.centre_mm, t)
            if det.centre_mm > OVERRUN_MM:
                _brake()
                return CentreResult(False, "overrun", det.centre_mm, speed_seen, frames, t - t0)
            predicted = det.centre_mm + speed * (STOP_LATENCY_S + frame_dt / 2) + BRAKE_COAST_MM
            if predicted >= 0.0:
                _brake()
                break

        offset = _stationary_offset(source, reference)
        nudges = 0
        while offset is not None and offset < -CENTER_TOL_MM and nudges < MAX_NUDGES:
            dur = max(NUDGE_MIN_S, (-offset - BRAKE_COAST_MM) / speed)
            _run()
            source.wait(dur)
            _brake()
            nudges += 1
            offset = _stationary_offset(source, reference)
        elapsed = source.now() - t0
        if offset is None:
            return CentreResult(False, "lost", None, speed_seen, frames, elapsed, nudges)
        ok = abs(offset) <= MAX_CAPTURE_OFFSET_MM
        return CentreResult(ok, "centred" if ok else "off_centre", offset, speed_seen,
                            frames, elapsed, nudges)
    finally:
        if belt_on:
            stop()
            source.belt(False)
