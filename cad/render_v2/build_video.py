#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Mux rendered frames + narration into the final MP4 with burned-in subtitles.

Usage: build_video.py FRAMES_DIR AUDIO_DIR OUT.mp4 [--fps 24] [--step 1] [--crf 26]
FRAMES_DIR holds f_00000.png... (every --step'th frame), AUDIO_DIR holds narration.wav +
timeline.json from make_narration.py. Captions are Pillow PNGs overlaid per segment
(this ffmpeg has no drawtext).
"""
import argparse, json, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("frames"); ap.add_argument("audio"); ap.add_argument("out")
ap.add_argument("--fps", type=int, default=24); ap.add_argument("--step", type=int, default=1)
ap.add_argument("--crf", type=int, default=24)
ap.add_argument("--maxrate", default="")
a = ap.parse_args()
tl = json.load(open(Path(a.audio) / "timeline.json"))
first = sorted(Path(a.frames).glob("f_*.png"))[0]
W, H = Image.open(first).size
S = W / 1280
tmp = Path(tempfile.mkdtemp(prefix="capv2_"))
FONT = "/System/Library/Fonts/Avenir Next.ttc"


def font(size, bold=True):
    try: return ImageFont.truetype(FONT, int(size * S), index=2 if bold else 0)  # 2 = Demi Bold
    except Exception: return ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", int(size * S))


steps = [s for s in tl["segments"] if s["id"] not in ("intro", "outro")]
caps = []
for i, seg in enumerate(tl["segments"]):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if seg["id"] in ("intro", "outro"):
        title = "Riftbound Card Sorter" if seg["id"] == "intro" else "Assembly complete"
        sub = "Mechanical assembly  -  10 steps" if seg["id"] == "intro" else "8 sort slots across 2 floors"
        f1, f2 = font(54), font(26, bold=False)
        bw = max(d.textlength(title, font=f1), d.textlength(sub, font=f2)) + 80 * S
        x0 = (W - bw) / 2; y0 = H * 0.05
        d.rounded_rectangle([x0, y0, x0 + bw, y0 + 120 * S], radius=18 * S, fill=(12, 14, 18, 170))
        d.text((W / 2, y0 + 44 * S), title, font=f1, fill=(255, 255, 255, 255), anchor="mm")
        d.text((W / 2, y0 + 92 * S), sub, font=f2, fill=(225, 228, 232, 255), anchor="mm")
    else:
        n = steps.index(seg) + 1
        text = seg["caption"].split(". ", 1)[-1] if seg["caption"][:3].strip(". ").isdigit() else seg["caption"]
        f = font(30, bold=True)
        tw = d.textlength(text, font=f)
        bw = tw + 60 * S; x0 = (W - bw) / 2; y0 = H - 92 * S
        d.rounded_rectangle([x0, y0, x0 + bw, y0 + 56 * S], radius=14 * S, fill=(12, 14, 18, 178))
        d.text((W / 2, y0 + 28 * S), text, font=f, fill=(255, 255, 255, 255), anchor="mm")
        # step badge, top-left
        fb = font(24); badge = f"STEP {n} / {len(steps)}"
        bw2 = d.textlength(badge, font=fb) + 36 * S
        d.rounded_rectangle([28 * S, 26 * S, 28 * S + bw2, 70 * S], radius=12 * S, fill=(226, 116, 43, 225))
        d.text((28 * S + bw2 / 2, 48 * S), badge, font=fb, fill=(255, 255, 255, 255), anchor="mm")
    p = tmp / f"cap_{i:02d}.png"; im.save(p); caps.append((p, seg))

in_fps = a.fps / a.step
cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", f"{in_fps}", "-pattern_type", "glob",
       "-i", str(Path(a.frames) / "f_*.png"), "-i", str(Path(a.audio) / "narration.wav")]
for p, _ in caps: cmd += ["-i", str(p)]
fc, last = [], "[0:v]"
if a.step > 1: fc.append(f"{last}fps={a.fps}[v0]"); last = "[v0]"
for k, (p, seg) in enumerate(caps):
    st = seg["start"] + (0.15 if seg["id"] != "intro" else 0.4); en = seg["start"] + seg["duration"] - 0.05
    out = f"[c{k}]"
    fc.append(f"{last}[{k + 2}:v]overlay=0:0:enable='between(t,{st:.2f},{en:.2f})'{out}"); last = out
T = tl["total"]
fc.append(f"{last}fade=t=in:st=0:d=0.6,fade=t=out:st={T - 1.0:.2f}:d=1.0,format=yuv420p[vout]")
fc.append(f"[1:a]afade=t=in:st=0:d=0.3,afade=t=out:st={T - 1.0:.2f}:d=1.0[aout]")
cmd += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf), "-r", str(a.fps)]
if a.maxrate: cmd += ["-maxrate", a.maxrate, "-bufsize", "4M"]
cmd += ["-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-t", f"{T:.2f}", a.out]
subprocess.run(cmd, check=True)
print("wrote", a.out)
