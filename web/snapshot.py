"""
Live-ish camera view for the phone app (GET /api/camera.jpg).

The camera belongs to the sort cycle. This module never touches it while a
run is in progress (main.run_in_progress(): starting / running / paused):
it then serves the frame the SORTER captured last (main._last_capture, the
card it just identified), else the last idle frame, else a placeholder.
Only when the machine is halted / idle does it grab a full frame itself
(camera.capture_full_jpeg()), at most once per MIN_INTERVAL_S however many
phones are polling, and never two at once (a busy grab returns the cached
frame).

MOCK_HARDWARE=1: a drawn placeholder of the scan bed (on option B with the
simulated cards on the bed and the cup when the arm is over it).

Every answer is a JPEG; X-Camera-Source says what it is:
  live    grabbed now (idle)
  cached  an earlier idle grab (rate limit, busy, or sorting with no card yet)
  sorter  the sorter's own last capture (sorting)
  mock    MOCK placeholder
  none    placeholder: nothing to show (camera unavailable / no frame yet)
"""

from __future__ import annotations

import io
import textwrap
import threading
import time

from PIL import Image, ImageDraw, ImageFont

MIN_INTERVAL_S = 0.5          # idle grabs: at most two a second for all clients

_lock = threading.Lock()
_cache = {"jpeg": None, "ts": 0.0, "source": "none"}


def reset() -> None:
    """Forget the cached frame (tests)."""
    _cache.update(jpeg=None, ts=0.0, source="none")


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)       # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def placeholder(lines: list[str], size=(768, 432), bg=(22, 27, 34), fg=(201, 209, 217)) -> bytes:
    img = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(img)
    y = size[1] // 2 - 18 * len(lines)
    for i, line in enumerate(lines):
        f = _font(30 if i == 0 else 20)
        w = d.textlength(line, font=f)
        d.text(((size[0] - w) / 2, y), line, fill=fg if i == 0 else (139, 148, 158), font=f)
        y += 40 if i == 0 else 30
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def mock_frame(sorter_main) -> bytes:
    """MOCK: the scan bed seen from above, with what the simulation has on it."""
    w, h = 768, 432
    img = Image.new("RGB", (w, h), (52, 46, 40))                # board
    d = ImageDraw.Draw(img)
    for x in range(0, w, 48):                                   # plywood grain
        d.line([(x, 0), (x + 30, h)], fill=(58, 51, 44), width=2)
    bed = (w // 2 - 170, h // 2 - 120, w // 2 + 170, h // 2 + 120)
    d.rounded_rectangle(bed, radius=14, fill=(84, 90, 98), outline=(120, 128, 138), width=3)
    cards, cup_here, th = 0, False, None
    if getattr(sorter_main, "MACHINE", "v2") == "b":
        try:
            from hardware import b_mock
            world = b_mock.WORLD
            cards = len(world.bed)
            cup_here = world.station() == "scan"
            th = world.th
        except Exception:
            pass
    cx, cy = w // 2, h // 2
    for i in range(min(cards, 3)):                              # card(s) on the bed
        o = i * 6
        d.rounded_rectangle((cx - 132 + o, cy - 94 + o, cx + 132 + o, cy + 94 + o), radius=10,
                            fill=(28, 61, 110), outline=(214, 178, 92), width=4)
    if cards:
        d.text((cx - 118, cy - 80), "RIFTBOUND", fill=(214, 178, 92), font=_font(26))
    if cup_here:                                                # the cup over / on the bed
        r = 34 if (th is not None and th < 9.9) else 28
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(25, 25, 25), outline=(200, 200, 200), width=3)
    f = _font(28)
    d.text((16, 12), "MOCK CAMERA", fill=(255, 196, 0), font=f)
    d.text((16, h - 44), time.strftime("%H:%M:%S") + f"   bed: {cards} card(s)", fill=(230, 230, 230), font=f)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def _grab(sorter_main, camera) -> bytes:
    if sorter_main.MOCK_HARDWARE:
        return mock_frame(sorter_main)
    return camera.capture_full_jpeg()


def frame(sorter_main, camera, now: float | None = None) -> tuple[bytes, str, float]:
    """(jpeg, source, age_s). Never raises."""
    now = time.time() if now is None else now
    if sorter_main.run_in_progress():
        last = getattr(sorter_main, "_last_capture", None)
        if last and last.get("jpeg"):
            return last["jpeg"], "sorter", max(0.0, now - last["ts"])
        if _cache["jpeg"]:
            return _cache["jpeg"], "cached", max(0.0, now - _cache["ts"])
        return placeholder(["Sorting", "live view paused while the machine runs"]), "none", 0.0
    if _cache["jpeg"] and now - _cache["ts"] < MIN_INTERVAL_S:
        return _cache["jpeg"], "cached", now - _cache["ts"]
    if not _lock.acquire(blocking=False):                       # another client is grabbing
        if _cache["jpeg"]:
            return _cache["jpeg"], "cached", max(0.0, now - _cache["ts"])
        return placeholder(["Camera busy", "try again"]), "none", 0.0
    try:
        if sorter_main.run_in_progress():                       # a run started meanwhile
            return frame(sorter_main, camera, now)
        try:
            jpeg = _grab(sorter_main, camera)
        except Exception as exc:
            if _cache["jpeg"]:
                return _cache["jpeg"], "cached", max(0.0, now - _cache["ts"])
            why = textwrap.wrap(f"{type(exc).__name__}: {exc}", 60)
            return placeholder(["Camera unavailable", *why]), "none", 0.0
        source = "mock" if sorter_main.MOCK_HARDWARE else "live"
        _cache.update(jpeg=jpeg, ts=time.time(), source=source)
        return jpeg, source, 0.0
    finally:
        _lock.release()
