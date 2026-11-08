"""Silo 81 pipe worm: a procedural toothed worm, animated by spine functions (no rig),
rendered in the same toon style and camera as the player into 6 hex directions.

Usage: python3 -I worm.py out_dir [anim ...]       env QUICK=n renders only n frames per clip
"""
import sys, os, json, math
import numpy as np
import bpy, bmesh
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

OUT = sys.argv[1]
ONLY = set(sys.argv[2:])
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from worm_pose import PPM, L, R_MAX, HEX, NS, S, RAD, RIDGE, smooth, spine_from, TAIL0, REST, rest_params, lerp_pose, LATCH_FILE
ELEV = math.radians(json.load(open(os.environ.get("SILO_CAMERA", "/home/claude/level/camera.json")))["elev_deg"])   # shared view (camera.json)
SAMPLES = 10
CANVAS = 384
NA = 16                       # vertices per ring
os.makedirs(OUT, exist_ok=True)

# fps, frames, loop, inplace(crawl)
ANIMS = {
    "idle":    dict(fps=24, frames=32, loop=True),
    "crawl":   dict(fps=24, frames=24, loop=True, inplace=True),
    "bite":    dict(fps=24, frames=20, loop=False),
    "hit":     dict(fps=24, frames=12, loop=False),
    "death":   dict(fps=24, frames=32, loop=False),
    "chew":    dict(fps=24, frames=36, loop=True),      # latched onto a pipe, tearing at it
    "release": dict(fps=24, frames=14, loop=False),     # lets go and drops back to the rest pose
}

def frames_along(pos):
    T = np.gradient(pos, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    N = np.zeros_like(T); B = np.zeros_like(T)
    up = np.array([0, 0, 1.0])
    n0 = np.cross(up, T[0]); n0 /= np.linalg.norm(n0)
    N[0] = n0
    for i in range(1, NS):                                 # parallel transport
        n = N[i - 1] - np.dot(N[i - 1], T[i]) * T[i]
        N[i] = n / np.linalg.norm(n)
    B = np.cross(T, N)
    return T, N, B

# ---------- mesh with constant topology ----------
INNER = [(0.82, 0.006), (0.55, 0.025), (0.25, 0.05), (0.0, 0.06)]   # throat rings: radius factor, depth
N_TEETH_OUT, N_TEETH_IN = 14, 9

def build_topology():
    bm = bmesh.new()
    verts = []
    for i in range(NS):
        for a in range(NA):
            verts.append(bm.verts.new((0, 0, 0)))
    tail = bm.verts.new((0, 0, 0))
    inner = [[bm.verts.new((0, 0, 0)) for a in range(NA)] for _ in INNER[:-1]]
    throat_end = bm.verts.new((0, 0, 0))
    bm.verts.ensure_lookup_table()
    V = lambda i, a: verts[i * NA + (a % NA)]
    for i in range(NS - 1):
        mat = 1 if RIDGE[i] > 0.45 else 0
        for a in range(NA):
            f = bm.faces.new([V(i, a), V(i, a + 1), V(i + 1, a + 1), V(i + 1, a)])
            top = abs(((a + 0.5) / NA) - 0.25) < 0.14               # a darker band along the back
            f.material_index = 2 if (top and mat == 0) else mat
    for a in range(NA):
        f = bm.faces.new([tail, V(0, a + 1), V(0, a)]); f.material_index = 0
    rings = [[V(NS - 1, a) for a in range(NA)]] + inner
    for k in range(len(rings) - 1):
        for a in range(NA):
            f = bm.faces.new([rings[k][a], rings[k + 1][a], rings[k + 1][(a + 1) % NA], rings[k][(a + 1) % NA]])
            f.material_index = 3 if k == 0 else 4
    for a in range(NA):
        f = bm.faces.new([rings[-1][a], throat_end, rings[-1][(a + 1) % NA]]); f.material_index = 4
    me = bpy.data.meshes.new("Worm"); bm.to_mesh(me); bm.free()
    return me

def body_coords(pos, mouth):
    T, N, B = frames_along(pos)
    ang = np.linspace(0, 2 * np.pi, NA, endpoint=False)
    ca, sa = np.cos(ang), np.sin(ang)
    # side view of the ring: N is horizontal-left, B is up for a flat body
    rr = RAD.copy()
    rr[-6:] *= 1 + 0.25 * mouth * np.linspace(0, 1, 6)      # the lip flares when the mouth opens
    ring = pos[:, None, :] + rr[:, None, None] * (ca[None, :, None] * N[:, None, :] + sa[None, :, None] * B[:, None, :])
    out = [ring.reshape(-1, 3)]
    out.append((pos[0] - T[0] * R_MAX * 0.35)[None])
    head, t, n, b = pos[-1], T[-1], N[-1], B[-1]
    rl = rr[-1]
    for f, depth in INNER[:-1]:
        fr = f * (1 + 0.35 * mouth)
        c = head - t * depth * (1 - 0.3 * mouth)
        out.append(c + rl * fr * (ca[:, None] * n + sa[:, None] * b))
    out.append((head - t * INNER[-1][1])[None])
    return np.concatenate(out, 0), (head, t, n, b, rl)

def teeth_mesh():
    bm = bmesh.new()
    for _ in range(N_TEETH_OUT + N_TEETH_IN):
        base = [bm.verts.new((0, 0, 0)) for _ in range(4)]
        tip = bm.verts.new((0, 0, 0))
        for k in range(4):
            bm.faces.new([base[k], base[(k + 1) % 4], tip])
        bm.faces.new(base[::-1])
    me = bpy.data.meshes.new("Teeth"); bm.to_mesh(me); bm.free()
    return me

def teeth_coords(hf, mouth):
    head, t, n, b, rl = hf
    out = []
    for ring, count, rf, depth, length in (("o", N_TEETH_OUT, 0.86, 0.004, 0.026), ("i", N_TEETH_IN, 0.5, 0.022, 0.02)):
        for k in range(count):
            a = 2 * np.pi * (k + (0.5 if ring == "i" else 0)) / count
            radial = math.cos(a) * n + math.sin(a) * b
            tang = -math.sin(a) * n + math.cos(a) * b
            c = head - t * depth + radial * rl * rf * (1 + 0.3 * mouth)
            # teeth point inward and forward; they splay out when the mouth opens
            direc = -radial * (0.8 - 0.9 * mouth) + t * (0.6 + 0.5 * mouth)
            direc /= np.linalg.norm(direc)
            w = length * 0.28
            base = [c + w * (math.cos(q) * radial + math.sin(q) * tang) for q in (0, math.pi / 2, math.pi, 3 * math.pi / 2)]
            out += base + [c + direc * length]
    return np.array(out)

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

def toon_flat(name, rgb, lit=0.62, midp=0.3):
    m = bpy.data.materials.new(name); m.use_nodes = True
    t = m.node_tree; t.nodes.clear()
    out = t.nodes.new("ShaderNodeOutputMaterial"); geo = t.nodes.new("ShaderNodeNewGeometry")
    dot = t.nodes.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = Vector((-0.55, -0.55, 0.63)).normalized()
    ramp = t.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.interpolation = "CONSTANT"
    e = ramp.color_ramp.elements
    # v2 bands (docs/VISUAL_DIRECTION.md): warm key, cool blue-grey shade, like the rooms and the people
    e[0].position, e[0].color = 0.0, (*[c * k for c, k in zip(rgb, (0.47, 0.5, 0.57))], 1)
    e[1].position, e[1].color = lit, (*[min(1, c * k) for c, k in zip(rgb, (1.17, 1.12, 1.04))], 1)
    mid = e.new(midp); mid.color = (*[c * 0.8 for c in rgb], 1)
    em = t.nodes.new("ShaderNodeEmission")
    t.links.new(geo.outputs["Normal"], dot.inputs[0]); t.links.new(dot.outputs["Value"], ramp.inputs["Fac"])
    t.links.new(ramp.outputs["Color"], em.inputs["Color"]); t.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m

def ink_mat():
    ink = bpy.data.materials.new("Ink"); ink.use_nodes = True
    nt = ink.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); g = nt.nodes.new("ShaderNodeNewGeometry")
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (0.035, 0.03, 0.025, 1)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent"); mx = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(g.outputs["Backfacing"], mx.inputs["Fac"]); nt.links.new(em.outputs["Emission"], mx.inputs[1])
    nt.links.new(tr.outputs["BSDF"], mx.inputs[2]); nt.links.new(mx.outputs["Shader"], o.inputs["Surface"])
    return ink

ink = ink_mat()
body_me = build_topology()
for name, rgb in (("Skin", (0.56, 0.41, 0.38)), ("Ridge", (0.36, 0.24, 0.23)), ("Back", (0.44, 0.31, 0.30)),
                  ("Lip", (0.47, 0.17, 0.17)), ("Throat", (0.13, 0.025, 0.035))):
    body_me.materials.append(toon_flat(name, rgb))
body_me.materials.append(ink)
body = bpy.data.objects.new("Worm", body_me); sc.collection.objects.link(body)
sol = body.modifiers.new("Outline", "SOLIDIFY"); sol.thickness = -0.011; sol.use_flip_normals = True
sol.use_rim = False; sol.material_offset = 5
teeth_me = teeth_mesh(); teeth_me.materials.append(toon_flat("Tooth", (0.86, 0.8, 0.62))); teeth_me.materials.append(ink)
teeth = bpy.data.objects.new("Teeth", teeth_me); sc.collection.objects.link(teeth)
tsol = teeth.modifiers.new("Outline", "SOLIDIFY"); tsol.thickness = -0.003; tsol.use_flip_normals = True
tsol.use_rim = False; tsol.material_offset = 1
rig = bpy.data.objects.new("Rig", None); sc.collection.objects.link(rig)
body.parent = rig; teeth.parent = rig

cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam)
cam.data.type = "ORTHO"
cam.rotation_euler = (math.radians(90) - ELEV, 0, 0)
FOCUS_Z = 0.2
cam.location = Vector((0, -30 * math.cos(ELEV), FOCUS_Z + 30 * math.sin(ELEV)))
cam.data.ortho_scale = CANVAS / PPM
sc.camera = cam
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = False
sc.cycles.max_bounces = 0; sc.cycles.transparent_max_bounces = 8
sc.render.film_transparent = True
sc.render.resolution_x = sc.render.resolution_y = CANVAS
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"
sc.world = bpy.data.worlds.new("W")

def screen_xy(p):
    uv = world_to_camera_view(sc, cam, p)
    return uv.x * CANVAS, (1 - uv.y) * CANVAS

# ---------- animation parameter curves ----------
def pose_for(anim, i, n):
    u = i / n                                    # loop phase for loops, progress for one-shots
    p = rest_params()
    if anim == "idle":                                         # chewing: head bobs, mouth works
        p["raise_"] += 0.08 * math.sin(2 * math.pi * u)
        p["head_pitch"] += 0.18 * math.sin(2 * math.pi * 2 * u)
        p["mouth"] = 0.15 + 0.55 * max(0.0, math.sin(2 * math.pi * 2 * u))
        p["lat_phase"] += 0.03 * math.sin(2 * math.pi * u)
    elif anim == "crawl":
        p.update(crawl=True, crawl_d=HEX * u, lat_amp=0.42, raise_=0.45, head_pitch=-0.55,
                 mouth=0.1 + 0.08 * math.sin(2 * math.pi * 2 * u))
    elif anim == "bite":
        f = i
        rear = float(smooth(0, 7, f)) * (1 - float(smooth(8, 12, f)))
        lunge = float(smooth(8, 11, f)) * (1 - float(smooth(13, 19, f)))
        p["raise_"] += 0.35 * rear - 0.75 * lunge
        p["lat_amp"] += 0.18 * rear - 0.3 * lunge
        p["head_pitch"] += -0.1 * rear + 0.3 * lunge
        p["mouth"] = 0.15 + 0.5 * rear + 0.85 * lunge
    elif anim == "hit":
        f = i
        k = math.exp(-f / 4.0) * math.sin(f / 1.6 + 0.8)
        p["raise_"] += 0.35 * k
        p["head_pitch"] -= 0.4 * k
        p["lat_phase"] += 0.12 * k
        p["lat_amp"] += 0.2 * abs(k)
        p["mouth"] = 0.15 + 0.6 * abs(k)
    elif anim == "death":
        f = i
        thrash = (1 - float(smooth(14, 22, f)))
        p["lat_amp"] = 0.32 + 0.35 * thrash * math.sin(f / 1.4)
        p["lat_phase"] += 0.25 * thrash * math.sin(f / 2.1)
        fall = float(smooth(6, 20, f))
        p["raise_"] = REST["raise_v"] * (1 - fall) + 0.25 * thrash * math.sin(f / 1.7) * (1 - fall)
        p["head_pitch"] = REST["head_pitch"] * (1 - fall) - 0.05 * fall
        p["curl"] = 0.9 * fall
        p["lat_amp"] = p["lat_amp"] * (1 - 0.6 * fall)
        p["mouth"] = 0.15 + 0.5 * thrash + 0.25 * fall
    elif anim == "chew":                                       # latched onto the pipe, tearing at it
        w = 2 * math.pi * u
        p.update(LATCH["pose"])
        bite = max(0.0, math.sin(3 * w)) ** 0.7                                # three bites per loop
        tug = math.sin(3 * w - 1.2)                                             # each bite tears back
        p["mouth"] = 0.15 + 0.85 * bite
        p["neck_yaw"] += 0.16 * math.sin(w) + 0.05 * math.sin(3 * w + 1.0)      # worrying side to side
        p["head_pitch"] += 0.18 * tug                                           # wrenching upwards
        p["raise_"] -= 0.07 * max(0.0, tug)                                     # pulling back off the steel
        p["lat_amp"] += 0.05 * max(0.0, tug)                                    # the body bunches as it pulls
        p["lat_phase"] += 0.03 * math.sin(w)
    elif anim == "release":                                    # lets go and drops back to rest
        t = float(smooth(0.0, 1.0, (i + 1) / n))
        p = lerp_pose(dict(p, **LATCH["pose"]), rest_params(), t)
        jerk = math.sin(math.pi * t)
        p["raise_"] += 0.18 * jerk                                              # rears back off the pipe
        p["head_pitch"] -= 0.25 * jerk
        p["mouth"] = 0.2 * (1 - t) + 0.4 * jerk + REST["mouth"] * t
    return p


LATCH = json.load(open(LATCH_FILE)) if os.path.exists(LATCH_FILE) else None


def set_pose(anim, i, n):
    p = pose_for(anim, i, n)
    pos = spine_from(p)
    if p.get("crawl"):                                         # in place: keep the body centre fixed
        c = pos[NS // 2]
        pos = pos - np.array([c[0], c[1], 0])
    else:
        pos = pos + TAIL0
    co, hf = body_coords(pos, p["mouth"])
    body_me.vertices.foreach_set("co", co.astype(np.float32).ravel()); body_me.update()
    tco = teeth_coords(hf, p["mouth"])
    teeth_me.vertices.foreach_set("co", tco.astype(np.float32).ravel()); teeth_me.update()

summary = {"pixels_per_metre": PPM, "camera_elevation_deg": round(math.degrees(ELEV), 2), "animations": {}}
anchor = None
for key, cfg in ANIMS.items():
    if ONLY and key not in ONLY:
        continue
    if key in ("chew", "release") and LATCH is None:
        print("skip", key, "(run latch.py first)"); continue
    n = cfg["frames"]
    n_out = int(os.environ.get("QUICK", n))
    picks = [int(x) % n for x in os.environ["PICK"].split(",")] if os.environ.get("PICK") else list(range(n_out))
    out_dir = os.path.join(OUT, key); os.makedirs(out_dir, exist_ok=True)
    meta = {"fps": cfg["fps"], "frames": n_out, "loop": cfg["loop"], "canvas": CANVAS, "directions": {}}
    dist = HEX / n if cfg.get("inplace") else 0.0
    for d in range(6):
        ang = 60 * d
        rig.rotation_euler = (0, 0, math.radians(ang))
        for i in picks:
            set_pose(key, i, n)
            bpy.context.view_layer.update()
            sc.render.filepath = os.path.join(out_dir, f"dir{d}_{i:03d}.png")
            bpy.ops.render.render(write_still=True)
        step = (dist * math.cos(math.radians(ang)) * PPM, -dist * math.sin(math.radians(ang)) * math.sin(ELEV) * PPM)
        meta["directions"][str(d)] = {"angle_deg": ang, "step_px": [round(step[0], 3), round(step[1], 3)]}
    meta["anchor_px"] = [round(v, 1) for v in screen_xy(Vector((0, 0, 0)))]
    summary["animations"][key] = meta
    print(key, "done", meta["directions"]["0"])

p = os.path.join(OUT, "steps.json")
prev = json.load(open(p)) if os.path.exists(p) else {}
prev.update({k: v for k, v in summary.items() if k != "animations"})
prev.setdefault("animations", {}).update(summary["animations"])
json.dump(prev, open(p, "w"), indent=2)
