#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["kokoro-onnx", "soundfile", "numpy", "pyyaml"]
# ///
"""Synthesize per-segment narration with Kokoro, build one narration.wav and timeline.json.

Usage: make_narration.py narration.yaml OUTDIR [--lead 0.5] [--tail 0.9]
Each segment's on-screen duration = lead + clip length + tail.
"""
import argparse, json
from pathlib import Path
import numpy as np, soundfile as sf, yaml
from kokoro_onnx import Kokoro

ap = argparse.ArgumentParser()
ap.add_argument("script"); ap.add_argument("outdir")
ap.add_argument("--lead", type=float, default=0.5)
ap.add_argument("--tail", type=float, default=0.9)
ap.add_argument("--models", default=str(Path.home() / ".claude/skills/tts/models"))
a = ap.parse_args()
cfg = yaml.safe_load(open(a.script))
out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
m = Path(a.models)
k = Kokoro(str(m / "kokoro-v1.0.onnx"), str(m / "voices-v1.0.bin"))
sr = 24000
pieces, timeline, t = [], [], 0.0
for seg in cfg["segments"]:
    audio, sr = k.create(seg["say"], voice=cfg.get("voice", "af_heart"), speed=cfg.get("speed", 1.0), lang="en-us")
    audio = np.asarray(audio, dtype=np.float32)
    sf.write(out / f"{seg['id']}.wav", audio, sr)
    clip = len(audio) / sr
    lead = a.lead if seg["id"] != "intro" else 0.8
    tail = a.tail if seg["id"] != "outro" else 2.5
    dur = lead + clip + tail
    pieces += [np.zeros(int(lead * sr), np.float32), audio, np.zeros(int(tail * sr), np.float32)]
    timeline.append({"id": seg["id"], "caption": seg["caption"], "say": seg["say"],
                     "start": round(t, 3), "speech_start": round(t + lead, 3),
                     "speech_end": round(t + lead + clip, 3), "duration": round(dur, 3)})
    t += dur
full = np.concatenate(pieces)
sf.write(out / "narration.wav", full, sr)
json.dump({"total": round(t, 3), "segments": timeline}, open(out / "timeline.json", "w"), indent=1)
for s in timeline:
    print(f"{s['id']:12s} start {s['start']:6.2f}  dur {s['duration']:5.2f}  speech {s['speech_start']:.2f}-{s['speech_end']:.2f}")
print("total", round(t, 2))
