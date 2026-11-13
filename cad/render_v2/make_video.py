#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6", "pillow>=10", "kokoro-onnx", "soundfile", "numpy"]
# ///
"""Part-by-part narrated assembly video (v3) for the Riftbound card sorter.

Everything is driven by video.yaml (parts, cameras, one segment per installed part).

  make_video.py export   [--jobs 8] [--force] [--only a,b]   STLs -> WORK/stl (openscad, w_*.scad)
  make_video.py narrate                                     Kokoro TTS -> WORK/audio (narration.wav, timeline.json)
  make_video.py plan                                        timeline + video.yaml -> WORK/plan.json
  make_video.py render   [--procs 3] [--samples 14] [--res 1280x720] [--step N] [--only F,F] [--out DIR]
  make_video.py keyframes [--at end|mid] [--out DIR]        render one captioned still per segment (review)
  make_video.py mux      [--frames DIR] [--step N] [--out file.mp4] [--crf 24]
  make_video.py captions                                    print the segment list (step, caption, say, times)

WORK defaults to /tmp/rv3 (--work). Blender: $BLENDER or /Applications/Blender.app.
"""
import argparse, json, math, os, subprocess, sys, tempfile, textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
BLENDER = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
LEAD, TAIL = 0.45, 0.8


def load_spec():
    return yaml.safe_load(open(HERE / "video.yaml"))


def part_table(spec):
    """name -> (wrapper, material)"""
    out = {}
    for w, parts in spec["parts"].items():
        for n, m in parts.items():
            if n in out: sys.exit(f"duplicate part {n}")
            out[n] = (w, m)
    return out


# ───────────────────────── export ─────────────────────────
def export(a):
    spec = load_spec(); pt = part_table(spec)
    out = Path(a.work) / "stl"; out.mkdir(parents=True, exist_ok=True)
    names = a.only.split(",") if a.only else list(pt)
    deps = max(p.stat().st_mtime for p in list(HERE.glob("*.scad")) + list((HERE.parent).glob("*.scad")))

    def one(n):
        w, _ = pt[n]; f = out / f"{n}.stl"
        if f.exists() and f.stat().st_mtime > deps and not a.force:
            return n, "cached", ""
        r = subprocess.run(["openscad", "--backend=manifold", "--export-format", "binstl", "-D", f'part="v3_{n}"',
                            "-o", str(f), str(HERE / f"{w}.scad")], capture_output=True, text=True)
        if r.returncode or not f.exists() or f.stat().st_size < 200:
            return n, "FAIL", r.stderr[-2000:]
        return n, "ok", ""

    bad = 0
    with ThreadPoolExecutor(a.jobs) as ex:
        for n, st, err in ex.map(one, names):
            if st == "FAIL": bad += 1; print(f"FAIL {n}\n{err}")
            elif a.verbose or st == "ok": print(f"{st:6s} {n}")
    print(f"{len(names) - bad}/{len(names)} parts ok in {out}")
    sys.exit(1 if bad else 0)


# ───────────────────────── narration ─────────────────────────
def anim_need(seg):
    """seconds after speech start that the segment's movers need"""
    need = 0.0
    for e in seg.get("add", []) + seg.get("move", []):
        d = e.get("delay", 0.1) + e.get("dur", 1.3) + e.get("stagger", 0.0) * max(0, e.get("n", 1) - 1)
        need = max(need, d)
    return need


def narrate(a):
    import numpy as np, soundfile as sf
    from kokoro_onnx import Kokoro
    spec = load_spec(); segs = spec["segments"]
    out = Path(a.work) / "audio"; out.mkdir(parents=True, exist_ok=True)
    m = Path.home() / ".claude/skills/tts/models"
    k = Kokoro(str(m / "kokoro-v1.0.onnx"), str(m / "voices-v1.0.bin"))
    sr = 24000; pieces, tl, t = [], [], 0.0
    for i, seg in enumerate(segs):
        cache = out / f"{seg['id']}.wav"; txt = out / f"{seg['id']}.txt"
        if cache.exists() and txt.exists() and txt.read_text() == seg["say"]:
            audio, sr = sf.read(cache, dtype="float32")
        else:
            audio, sr = k.create(seg["say"], voice=spec.get("voice", "af_heart"), speed=spec.get("speed", 1.0), lang="en-us")
            audio = np.asarray(audio, dtype=np.float32); sf.write(cache, audio, sr); txt.write_text(seg["say"])
        clip = len(audio) / sr
        lead = 0.8 if i == 0 else LEAD
        tail = 2.5 if i == len(segs) - 1 else TAIL
        read = 0.6 + len(seg.get("caption", "")) / 17.0                  # caption reading time at ~17 chars/s
        tail = max(tail, anim_need(seg) + 0.5 - clip, seg.get("min_dur", 0) - lead - clip, read - lead - clip)
        dur = lead + clip + tail
        pieces += [np.zeros(int(round(lead * sr)), np.float32), audio, np.zeros(int(round(tail * sr)), np.float32)]
        tl.append({"id": seg["id"], "start": round(t, 3), "speech_start": round(t + lead, 3),
                   "speech_end": round(t + lead + clip, 3), "duration": round(dur, 3)})
        t += dur
    full = np.concatenate(pieces)
    sf.write(out / "narration.wav", full, sr)
    json.dump({"total": round(len(full) / sr, 3), "segments": tl}, open(out / "timeline.json", "w"), indent=1)
    print(f"{len(segs)} segments, total {t:.1f} s ({t / 60:.2f} min)")


# ───────────────────────── plan ─────────────────────────
def build_plan(a):
    spec = load_spec(); pt = part_table(spec)
    tl = json.load(open(Path(a.work) / "audio" / "timeline.json"))
    T = {s["id"]: s for s in tl["segments"]}
    segs = spec["segments"]
    if [s["id"] for s in segs] != [s["id"] for s in tl["segments"]]:
        sys.exit("timeline.json is stale: run narrate")
    groups, owner = [], {}
    cur_cam, shot0 = None, 0
    seg_out = []
    for i, seg in enumerate(segs):
        tm = T[seg["id"]]; t_sp = tm["speech_start"]; t0 = tm["start"]
        cam = seg.get("cam", cur_cam)
        if cam not in spec["cams"]: sys.exit(f"{seg['id']}: unknown cam {cam}")
        if cam != cur_cam: shot0 = i
        cur_cam = cam
        seg_out.append({"id": seg["id"], "step": seg.get("step"), "start": t0, "dur": tm["duration"],
                        "speech_start": t_sp, "cam": cam, "shot": shot0, "no_bench": bool(seg.get("no_bench"))})
        for e in seg.get("add", []):
            for n in e["parts"]:
                if n not in pt: sys.exit(f"{seg['id']}: unknown part {n}")
                if n in owner: sys.exit(f"{seg['id']}: part {n} added twice")
            g = {"name": e["parts"][0], "parts": e["parts"], "split": bool(e.get("split")),
                 "stagger": e.get("stagger", 0.0), "sort_axis": e.get("sort_axis", "x"),
                 "spin": e.get("spin", 0.0), "spin_axis": e.get("spin_axis", "z"),
                 "keys": [], "vis": [[t0, None]], "seg": seg["id"]}
            rest = e.get("at", [0, 0, 0]); frm = [r + f for r, f in zip(rest, e.get("from", [0, 0, 120]))]
            ts = t_sp + e.get("delay", 0.1)
            g["keys"].append([ts, ts + e.get("dur", 1.3), frm, rest, True])
            groups.append(g)
            for n in e["parts"]: owner[n] = g
        for e in seg.get("move", []):
            gs = {id(owner[n]): owner[n] for n in e["parts"]}.values()
            for g in gs:
                prev = g["keys"][-1][3]; ts = t_sp + e.get("delay", 0.1)
                g["keys"].append([ts, ts + e.get("dur", 1.5), prev, e.get("to", [0, 0, 0]), False])
        for n in seg.get("hide", []):
            g = owner[n]
            if g["vis"][-1][1] is None: g["vis"][-1][1] = t0
        for n in seg.get("show", []):
            if n not in owner:   # instant appear at home (pose variants)
                g = {"name": n, "parts": [n], "split": False, "stagger": 0, "sort_axis": "x", "spin": 0,
                     "spin_axis": "z", "keys": [], "vis": [[t0, None]], "seg": seg["id"]}
                groups.append(g); owner[n] = g
            elif owner[n]["vis"][-1][1] is not None:
                owner[n]["vis"].append([t0, None])
    final_vis = {g["name"]: g["vis"][-1][1] is None for g in groups}
    for g in groups:
        for v in g["vis"]:
            if v[1] is None: v[1] = 1e9
        g["final"] = final_vis[g["name"]] and g["keys"] and g["keys"][-1][3] == [0, 0, 0]
    unused = sorted(set(pt) - set(owner))
    if unused: print("WARNING parts never shown:", ", ".join(unused))
    plan = {"stl_dir": str(Path(a.work) / "stl"), "total": tl["total"], "fps": a.fps,
            "floor_z": spec.get("floor_z", -16), "scene_radius": spec.get("scene_radius", 650),
            "parts": {n: m for n, (w, m) in pt.items() if n in owner},
            "groups": groups, "segments": seg_out, "cams": spec["cams"],
            "intro": segs[0]["id"], "outro": segs[-1]["id"]}
    p = Path(a.work) / "plan.json"; json.dump(plan, open(p, "w"), indent=1)
    print(f"plan: {len(groups)} groups, {len(seg_out)} segments, {tl['total']:.1f} s -> {p}")
    return plan


# ───────────────────────── render ─────────────────────────
def render(a):
    plan = build_plan(a)
    out = Path(a.out or (Path(a.work) / "frames")); out.mkdir(parents=True, exist_ok=True)
    total = int(math.ceil(plan["total"] * a.fps))
    common = [BLENDER, "--background", "--python", str(HERE / "render_blender.py"), "--",
              "--plan", str(Path(a.work) / "plan.json"), "--out", str(out), "--fps", str(a.fps),
              "--samples", str(a.samples), "--res", a.res]
    if a.only:
        frames = [int(x) for x in a.only.split(",")]
        chunks = [frames[i::a.procs] for i in range(a.procs)]
        procs = [subprocess.Popen(common + ["--only", ",".join(map(str, c))], stdout=subprocess.DEVNULL,
                                  stderr=open(out / f"log{i}.txt", "w")) for i, c in enumerate(chunks) if c]
    else:
        frames = list(range(a.start, total if a.end < 0 else min(a.end, total), a.step))
        if a.skip_existing:
            frames = [f for f in frames if not (out / f"f_{f:05d}.png").exists()]
        chunks = [frames[i::a.procs] for i in range(a.procs)]   # interleaved: every proc sees every part of the film
        procs = [subprocess.Popen(common + ["--only", ",".join(map(str, c))], stdout=open(out / f"log{i}.txt", "w"),
                                  stderr=subprocess.STDOUT) for i, c in enumerate(chunks) if c]
    rc = [p.wait() for p in procs]
    print(json.dumps({"frames_dir": str(out), "total_frames": total, "rendered": len(frames), "exit_codes": rc}))


# ───────────────────────── captions / mux ─────────────────────────
FONT = "/System/Library/Fonts/Avenir Next.ttc"


def _font(size, S, bold=True):
    from PIL import ImageFont
    try: return ImageFont.truetype(FONT, int(size * S), index=2 if bold else 0)
    except Exception: return ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", int(size * S))


def wrap_px(d, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines


def caption_image(spec, seg, idx, nseg, W, H):
    from PIL import Image, ImageDraw
    S = W / 1280
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    steps = spec["steps"]; nsteps = len(steps)
    if idx in (0, nseg - 1):
        title, sub = seg.get("title", ""), seg.get("subtitle", "")
        f1, f2 = _font(50, S), _font(25, S, bold=False)
        bw = max(d.textlength(title, font=f1), d.textlength(sub, font=f2)) + 80 * S
        x0 = (W - bw) / 2; y0 = H * 0.045; hh = (118 if sub else 80) * S
        d.rounded_rectangle([x0, y0, x0 + bw, y0 + hh], radius=18 * S, fill=(12, 14, 18, 175))
        d.text((W / 2, y0 + 42 * S), title, font=f1, fill=(255, 255, 255, 255), anchor="mm")
        if sub: d.text((W / 2, y0 + 90 * S), sub, font=f2, fill=(225, 228, 232, 255), anchor="mm")
    else:
        n = seg["step"]
        fb = _font(22, S); badge = f"STEP {n} / {nsteps}"
        ft = _font(22, S, bold=False); title = steps[n]
        bw2 = d.textlength(badge, font=fb) + 30 * S; tw = d.textlength(title, font=ft) + 30 * S
        d.rounded_rectangle([24 * S, 22 * S, 24 * S + bw2 + tw, 62 * S], radius=12 * S, fill=(12, 14, 18, 170))
        d.rounded_rectangle([24 * S, 22 * S, 24 * S + bw2, 62 * S], radius=12 * S, fill=(226, 116, 43, 235))
        d.text((24 * S + bw2 / 2, 42 * S), badge, font=fb, fill=(255, 255, 255, 255), anchor="mm")
        d.text((24 * S + bw2 + 14 * S, 42 * S), title, font=ft, fill=(240, 240, 240, 255), anchor="lm")
    cap = seg.get("caption", "")
    if cap:
        f = _font(27, S); lines = wrap_px(d, cap, f, W - 140 * S)
        lh = 36 * S; bh = lh * len(lines) + 22 * S
        bw = max(d.textlength(l, font=f) for l in lines) + 56 * S
        x0 = (W - bw) / 2; y1 = H - 26 * S; y0 = y1 - bh
        d.rounded_rectangle([x0, y0, x0 + bw, y1], radius=14 * S, fill=(12, 14, 18, 185))
        for k, l in enumerate(lines):
            d.text((W / 2, y0 + 11 * S + lh * (k + 0.5)), l, font=f, fill=(255, 255, 255, 255), anchor="mm")
    return im


def mux(a):
    from PIL import Image
    spec = load_spec(); segs = spec["segments"]
    tl = json.load(open(Path(a.work) / "audio" / "timeline.json"))
    frames = Path(a.frames or (Path(a.work) / "frames"))
    W, H = Image.open(sorted(frames.glob("f_*.png"))[0]).size
    tmp = Path(tempfile.mkdtemp(prefix="rv3cap_")); caps = []
    for i, (seg, tm) in enumerate(zip(segs, tl["segments"])):
        p = tmp / f"cap_{i:03d}.png"; caption_image(spec, seg, i, len(segs), W, H).save(p); caps.append((p, tm))
    # concat-demuxer list of caption stills with durations → one overlay stream (cheap, no 90-input graph)
    lst = tmp / "caps.txt"
    with open(lst, "w") as fh:
        for p, tm in caps: fh.write(f"file '{p}'\nduration {tm['duration']:.3f}\n")
        fh.write(f"file '{caps[-1][0]}'\n")
    T = tl["total"]; fps = a.fps
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", f"{fps / a.step}", "-pattern_type", "glob",
           "-i", str(frames / "f_*.png"), "-i", str(Path(a.work) / "audio" / "narration.wav"),
           "-f", "concat", "-safe", "0", "-i", str(lst)]
    fc = "[0:v]" + (f"fps={fps}," if a.step > 1 else "") + "format=rgba[v0];[2:v]fps=%d,format=rgba[c];" % fps
    fc += f"[v0][c]overlay=0:0:shortest=0,fade=t=in:st=0:d=0.6,fade=t=out:st={T - 1.0:.2f}:d=1.0,format=yuv420p[vout];"
    fc += f"[1:a]afade=t=in:st=0:d=0.3,afade=t=out:st={T - 1.0:.2f}:d=1.0[aout]"
    out = a.out or str(Path(a.work) / "assembly-video-v3.mp4")
    cmd += ["-filter_complex", fc, "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "slow",
            "-crf", str(a.crf), "-r", str(fps), "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            "-t", f"{T:.2f}", out]
    subprocess.run(cmd, check=True)
    print(json.dumps({"out": out, "bytes": os.path.getsize(out), "duration": T}))


def keyframes(a):
    """Render one still per segment (late in the segment, after its parts have landed) and burn the caption in."""
    from PIL import Image
    spec = load_spec(); segs = spec["segments"]
    plan = build_plan(a)
    out = Path(a.out or (Path(a.work) / "keyframes")); raw = out / "raw"; raw.mkdir(parents=True, exist_ok=True)
    frames = []
    for s in plan["segments"]:
        t = s["start"] + (s["dur"] - 0.25 if a.at == "end" else s["dur"] * 0.5)
        frames.append(int(t * a.fps))
    a2 = argparse.Namespace(**{**vars(a), "only": ",".join(map(str, frames)), "out": str(raw), "step": 1,
                               "start": 0, "end": -1, "skip_existing": False})
    if not a.no_render: render(a2)
    for i, (seg, f) in enumerate(zip(segs, frames)):
        src = raw / f"f_{f:05d}.png"
        if not src.exists(): print("missing", src); continue
        im = Image.open(src).convert("RGBA"); W, H = im.size
        im.alpha_composite(caption_image(spec, seg, i, len(segs), W, H))
        im.convert("RGB").save(out / f"{i:03d}_{seg['id']}.jpg", quality=88)
    print(f"keyframes in {out}")


def captions(a):
    spec = load_spec()
    tlp = Path(a.work) / "audio" / "timeline.json"
    T = {s["id"]: s for s in json.load(open(tlp))["segments"]} if tlp.exists() else {}
    for i, s in enumerate(spec["segments"]):
        tm = T.get(s["id"], {}); st = tm.get("start", 0); du = tm.get("duration", 0)
        print(f"{i:03d} [{st:6.1f}s +{du:4.1f}] step {s.get('step', '-')!s:>2} {s['id']}\n"
              f"     CAPTION: {s.get('caption', '')}\n     SAY:     {s['say']}")


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--work", default="/tmp/rv3")
ap.add_argument("--fps", type=int, default=24)
sub = ap.add_subparsers(dest="cmd", required=True)
e = sub.add_parser("export"); e.add_argument("--jobs", type=int, default=8); e.add_argument("--force", action="store_true")
e.add_argument("--only", default=""); e.add_argument("--verbose", action="store_true")
sub.add_parser("narrate"); sub.add_parser("plan"); sub.add_parser("captions")
for name in ("render", "keyframes"):
    r = sub.add_parser(name)
    r.add_argument("--procs", type=int, default=3); r.add_argument("--samples", type=int, default=14)
    r.add_argument("--res", default="1280x720"); r.add_argument("--step", type=int, default=1)
    r.add_argument("--only", default=""); r.add_argument("--out", default="")
    r.add_argument("--start", type=int, default=0); r.add_argument("--end", type=int, default=-1)
    r.add_argument("--skip-existing", action="store_true")
    if name == "keyframes":
        r.add_argument("--at", default="end", choices=["end", "mid"]); r.add_argument("--no-render", action="store_true")
m = sub.add_parser("mux"); m.add_argument("--frames", default=""); m.add_argument("--step", type=int, default=1)
m.add_argument("--out", default=""); m.add_argument("--crf", type=int, default=24)
a = ap.parse_args()
{"export": export, "narrate": narrate, "plan": build_plan, "render": render, "mux": mux,
 "keyframes": keyframes, "captions": captions}[a.cmd](a)
