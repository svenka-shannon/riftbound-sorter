"""Riftbound Card Sorter - part-by-part assembly video (v3), Blender EEVEE side.

Do not run directly: `make_video.py render|keyframes` writes plan.json and shards frames.
  Blender --background --python render_blender.py -- --plan plan.json --out DIR [--only F,F] ...

plan.json (make_video.py build_plan): parts {stl: material}, groups [{parts, keys, vis, split,
stagger, spin, ...}] (offsets in mm, times in s), segments [{start, dur, cam, shot, no_bench}],
cams {name: [target, dist, azimuth, elevation, drift deg/s, fstop]}. Every frame is posed in
Python (no keyframes), so frames can be rendered in any order by any number of processes.
"""
import bpy, bmesh, json, math, os, sys, argparse
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--plan", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--fps", type=int, default=24)
ap.add_argument("--only", default="")
ap.add_argument("--res", default="1280x720")
ap.add_argument("--samples", type=int, default=14)
A = ap.parse_args(argv)
MM = 0.001
PL = json.load(open(A.plan))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
W, H = (int(v) for v in A.res.split("x"))
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = "PNG"
ee = sc.eevee
ee.taa_render_samples = A.samples
for attr, val in [("use_raytracing", True), ("use_shadows", True), ("shadow_ray_count", 2),
                  ("shadow_step_count", 8), ("use_gtao", True), ("fast_gi_method", "GLOBAL_ILLUMINATION")]:
    try: setattr(ee, attr, val)
    except Exception: pass
try: ee.ray_tracing_options.resolution_scale = "2"
except Exception: pass
sc.view_settings.view_transform = "AgX"
try: sc.view_settings.look = "AgX - Medium High Contrast"
except Exception: pass

world = bpy.data.worlds.new("studio"); sc.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.62, 0.64, 0.68, 1); bg.inputs[1].default_value = 0.16


def mat(name, color, rough=0.5, metal=0.0, layer_lines=False, brushed=False, wood=False, spec=0.5, coat=0.0, emit=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    N = m.node_tree.nodes; L = m.node_tree.links; p = N["Principled BSDF"]
    c = tuple((int(color[i:i + 2], 16) / 255) ** 2.2 for i in (1, 3, 5)) + (1,)
    p.inputs["Base Color"].default_value = c
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    try: p.inputs["Specular IOR Level"].default_value = spec
    except Exception: pass
    if coat: p.inputs["Coat Weight"].default_value = coat
    if emit:
        p.inputs["Emission Color"].default_value = c; p.inputs["Emission Strength"].default_value = emit
    if layer_lines:
        geo = N.new("ShaderNodeNewGeometry"); sep = N.new("ShaderNodeSeparateXYZ")
        mul = N.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = 2 * math.pi / (0.2 * MM)
        sn = N.new("ShaderNodeMath"); sn.operation = "SINE"
        bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.06; bump.inputs["Distance"].default_value = 0.00004
        L.new(geo.outputs["Position"], sep.inputs[0]); L.new(sep.outputs["Z"], mul.inputs[0])
        L.new(mul.outputs[0], sn.inputs[0]); L.new(sn.outputs[0], bump.inputs["Height"]); L.new(bump.outputs[0], p.inputs["Normal"])
    if brushed:
        tc = N.new("ShaderNodeTexCoord"); mp = N.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1, 1, 400)
        nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 60
        rmp = N.new("ShaderNodeMapRange"); rmp.inputs[3].default_value = rough * 0.6; rmp.inputs[4].default_value = rough * 1.4
        L.new(tc.outputs["Object"], mp.inputs[0]); L.new(mp.outputs[0], nz.inputs[0])
        L.new(nz.outputs[0], rmp.inputs[0]); L.new(rmp.outputs[0], p.inputs["Roughness"])
    if wood:
        tc = N.new("ShaderNodeTexCoord"); mp = N.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (0.6, 9, 1)
        wv = N.new("ShaderNodeTexWave"); wv.inputs["Scale"].default_value = 3.0
        wv.inputs["Distortion"].default_value = 1.5; wv.inputs["Detail"].default_value = 4
        nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 8
        mix = N.new("ShaderNodeMix"); mix.data_type = "FLOAT"; mix.inputs[0].default_value = 0.35
        ramp = N.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (0.16, 0.085, 0.04, 1); ramp.color_ramp.elements[1].color = (0.36, 0.22, 0.11, 1)
        L.new(tc.outputs["Object"], mp.inputs[0]); L.new(mp.outputs[0], wv.inputs[0]); L.new(mp.outputs[0], nz.inputs[0])
        L.new(wv.outputs["Fac"], mix.inputs[2]); L.new(nz.outputs["Fac"], mix.inputs[3])
        L.new(mix.outputs[0], ramp.inputs[0]); L.new(ramp.outputs[0], p.inputs["Base Color"])
    return m


PRESET = {
    "petg": dict(color="#C9CAC6", rough=0.42, layer_lines=True),
    "petg_matte": dict(color="#1B1C1F", rough=0.62, layer_lines=True, spec=0.35),
    "steel": dict(color="#C4C6C8", rough=0.28, metal=1.0, brushed=True),
    "alu": dict(color="#D3D5D8", rough=0.32, metal=1.0, brushed=True),
    "screw": dict(color="#B9BCC0", rough=0.22, metal=1.0),
    "brass": dict(color="#C9A04E", rough=0.3, metal=1.0),
    "rubber": dict(color="#151515", rough=0.85, spec=0.2),
    "pcb": dict(color="#1E6B3C", rough=0.35, coat=0.4),
    "chip": dict(color="#141416", rough=0.5),
    "mdf": dict(color="#A3835C", rough=0.8),
    "plastic": dict(color="#888888", rough=0.4),
    "led": dict(color="#FFF6E0", rough=0.3, emit=2.0),
    "mark": dict(color="#E03A2F", rough=0.5, emit=0.6),
}
M = {"wood": mat("bench oak", "#8A6440", 0.55, wood=True)}


def material(spec):
    if spec not in M:
        kind, _, col = spec.partition(":")
        kw = dict(PRESET.get(kind, PRESET["plastic"]))
        if col: kw["color"] = col
        color = kw.pop("color"); rough = kw.pop("rough", 0.4)
        M[spec] = mat(spec, color, rough, **kw)
    return M[spec]


def import_part(name):
    bpy.ops.wm.stl_import(filepath=os.path.join(PL["stl_dir"], name + ".stl"), global_scale=MM)
    ob = bpy.context.selected_objects[0]; ob.name = name
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.to_mesh(ob.data); bm.free()
    ob.data.materials.append(material(PL["parts"][name]))
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.selected_objects: o.select_set(o == ob)
    try: bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
    except Exception:
        try: bpy.ops.object.shade_auto_smooth(angle=math.radians(35))
        except Exception: pass
    return ob


def split_loose(ob):
    for o in bpy.context.selected_objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.mesh.separate(type="LOOSE")
    parts = list(bpy.context.selected_objects)
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    return parts


def center(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return (lo + hi) / 2


objs = {n: import_part(n) for n in PL["parts"]}

# ───────────────────────── movers ─────────────────────────
AX = {"x": 0, "y": 1, "z": 2}
movers = []   # {empty, home, keys, vis, spin, axis, final}


def add_mover(parts, g, appear_delay=0.0):
    c = center(parts)
    e = bpy.data.objects.new(f"mv_{g['name']}_{len(movers)}", None); sc.collection.objects.link(e)
    e.location = c; bpy.context.view_layer.update()
    for p in parts:
        mw = p.matrix_world.copy(); p.parent = e; p.matrix_world = mw
    keys = [list(k) for k in g["keys"]]
    if keys and appear_delay:
        keys[0][0] += appear_delay; keys[0][1] += appear_delay
    movers.append(dict(empty=e, home=c.copy(), keys=keys, vis=g["vis"], spin=g["spin"], axis=AX[g["spin_axis"]],
                       final=g["final"], parts=parts))


for g in PL["groups"]:
    if not g["split"]:
        add_mover([objs[n] for n in g["parts"]], g); continue
    units = sorted(split_loose(objs[g["parts"][0]]), key=lambda o: o.matrix_world.translation[AX[g["sort_axis"]]])
    grp = [[u] for u in units]
    for n in g["parts"][1:]:
        for pc in split_loose(objs[n]):
            j = min(range(len(units)), key=lambda q: (units[q].matrix_world.translation - pc.matrix_world.translation).length)
            grp[j].append(pc)
    for k, u in enumerate(grp):
        add_mover(u, g, appear_delay=g["stagger"] * k)

# ───────────────────────── bench, lights, camera ─────────────────────────
R = PL["scene_radius"] * MM / 0.6
bpy.ops.mesh.primitive_plane_add(size=10 * R, location=(0, 0, PL["floor_z"] * MM))
bench = bpy.context.active_object; bench.name = "bench"; bench.data.materials.append(M["wood"])


def area(name, loc, power, size, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA"); ld.energy = power * R * R; ld.size = size * R; ld.color = color
    lo = bpy.data.objects.new(name, ld); sc.collection.objects.link(lo); lo.location = loc = Vector(loc) * R
    lo.rotation_euler = (Vector((0, 0, 0.05)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return lo


area("key", (-1.1, -1.3, 1.6), 105, 1.6, (1.0, 0.96, 0.9))
area("fill", (1.5, -0.8, 0.9), 32, 2.0, (0.9, 0.95, 1.0))
area("rim", (0.3, 1.6, 1.2), 65, 1.2)
under = area("under", (0.2, -0.6, -1.4), 0, 2.2)          # only on for the from-below shots

camd = bpy.data.cameras.new("cam"); camd.lens = 45; camd.sensor_width = 36; camd.clip_start = 0.01
cam = bpy.data.objects.new("cam", camd); sc.collection.objects.link(cam); sc.camera = cam
tgt = bpy.data.objects.new("focus", None); sc.collection.objects.link(tgt)
camd.dof.use_dof = True; camd.dof.focus_object = tgt

SEGS = PL["segments"]; CAMS = PL["cams"]
INTRO, OUTRO = PL["intro"], PL["outro"]


def ease(t):
    t = max(0.0, min(1.0, t)); return t * t * t * (t * (6 * t - 15) + 10)


def seg_at(t):
    i = 0
    for k, s in enumerate(SEGS):
        if s["start"] <= t + 1e-6: i = k
    return i


def shot_state(i, t):
    """camera of segment i's shot at absolute time t"""
    s = SEGS[i]; sh = SEGS[s["shot"]]
    j = s["shot"]
    while j + 1 < len(SEGS) and SEGS[j + 1]["shot"] == s["shot"]: j += 1
    shot_end = SEGS[j]["start"] + SEGS[j]["dur"]
    tg, d, az, el, drift, fs = CAMS[s["cam"]]
    t_in = t - sh["start"]; dur = max(1e-3, shot_end - sh["start"])
    d = d * (1.0 - 0.06 * min(1.0, t_in / dur))
    return Vector(tg) * MM, d * MM, az + drift * t_in, el, fs


def pose_camera(t):
    i = seg_at(t); s = SEGS[i]
    tg, d, az, el, fs = shot_state(i, t)
    if i > 1 and s["shot"] == i:            # a new shot: ease over from the previous one (cut after the intro)
        p = SEGS[i - 1]
        a0 = CAMS[p["cam"]][2]; a1 = CAMS[s["cam"]][2]
        blend = min(3.0, 1.3 + abs(a1 - a0) / 90 + abs(CAMS[s["cam"]][3] - CAMS[p["cam"]][3]) / 60)
        j = i
        while j + 1 < len(SEGS) and SEGS[j + 1]["shot"] == i: j += 1
        blend = min(blend, 0.8 * (SEGS[j]["start"] + SEGS[j]["dur"] - s["start"]))
        t_in = t - s["start"]
        if t_in < blend:
            ptg, pd, paz, pel, pfs = shot_state(i - 1, t)
            k = ease(t_in / blend)
            tg = ptg.lerp(tg, k); d = pd + (d - pd) * k; az = paz + (az - paz) * k; el = pel + (el - pel) * k
            fs = pfs + (fs - pfs) * k
    a, e = math.radians(az), math.radians(el)
    pos = tg + d * Vector((math.cos(e) * math.sin(a), -math.cos(e) * math.cos(a), math.sin(e)))
    cam.location = pos
    cam.rotation_euler = (tg - pos).to_track_quat("-Z", "Y").to_euler()
    tgt.location = tg; camd.dof.aperture_fstop = fs
    return i


def pose_parts(t, i):
    s = SEGS[i]
    showcase = s["id"] in (INTRO, OUTRO)
    bench.hide_render = bool(s["no_bench"])
    under.data.energy = (40 * R * R) if s["no_bench"] else 0
    for mv in movers:
        e = mv["empty"]
        if showcase:
            vis = mv["final"]; off = Vector((0, 0, 0)); rot = 0.0
        else:
            vis = any(a <= t + 1e-6 < b for a, b in mv["vis"]) and bool(mv["keys"] or True)
            off = Vector(mv["keys"][0][2]) if mv["keys"] else Vector((0, 0, 0)); rot = 0.0
            for (t0, t1, fr, to, first) in mv["keys"]:
                if t < t0: break
                k = ease((t - t0) / max(1e-3, t1 - t0))
                off = Vector(fr).lerp(Vector(to), k)
                if first: rot = mv["spin"] * 2 * math.pi * (1 - k)
        for p in mv["parts"]: p.hide_render = not vis
        e.location = mv["home"] + off * MM
        r = [0.0, 0.0, 0.0]; r[mv["axis"]] = -rot; e.rotation_euler = r


fps = A.fps
os.makedirs(A.out, exist_ok=True)
frames = [int(x) for x in A.only.split(",") if x != ""]
print(f"rendering {len(frames)} frames", flush=True)
for f in frames:
    t = f / fps
    i = pose_camera(t)
    pose_parts(t, i)
    sc.render.filepath = os.path.join(A.out, f"f_{f:05d}.png")
    bpy.ops.render.render(write_still=True)
    print(f"frame {f} {SEGS[i]['id']}", flush=True)
