"""The pipe worm (Meshy model "bunker pipe worm": a 19-bone chain, no clips) -> game-ready live 3D.
Replaces the procedural pipe worm (worm.py / worm_live.py).

The chain runs from the mouth (Bone_000, the root) to the tail tip (Bone_001). Every clip is written as a
spine curve per frame - a head point plus how the body bends sideways (yaw) and up (pitch) along its
length - and each bone is then aimed along that curve, root first, so the skeleton itself carries the
motion (no shape keys, no flipbook):
  idle (32)    breathing, the blind head lifting and turning, swinging slowly
  crawl (24)   serpentine: a sideways wave travels back along the body exactly as fast as the worm moves
               forward, so every part of it follows the same track (no sliding); 0.0533 m a frame
  bite (20)    coils back into an S with the head reared, strikes on frame 11, recoils
  hit (12)     jerks back and up, the wave kinks
  death (32)   thrashes, goes limp and curls up on the ground
  chew (36)    reared up with its mouth on the burst pipe (latch.json), tearing at it three times a loop
  release (14) lets go, rears back, drops into the rest pose
Usage: python3 -I meshy_worm.py IN.glb OUT_BASENAME [length_m]
"""
import sys, os, json, math
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

IN, OUT = sys.argv[1], sys.argv[2]
LENGTH = float(sys.argv[3]) if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else 1.3
FPS = 24
KEEP_NORMAL = "--flat" not in sys.argv     # default: keep the normal map, 2048 px textures, soft bands + rim (art rule); --flat = old base-colour-only look
TEX_MAX = 2048 if KEEP_NORMAL else 1024
CRAWL_N, CRAWL_V = 24, 0.0533                     # as the old worm (pipe_worm/character.json step_px 8.794)
LATCH = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "latch.json")))
# the old worm's frame: +x forward, +y left; this model faces -Y, its left is +X
TL = LATCH["target_local"]
CHEW_TARGET = Vector((TL[1], -TL[0], TL[2]))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS
bpy.ops.import_scene.gltf(filepath=IN)
for o in list(bpy.data.objects):
    if o.type == "MESH" and o.parent is None:
        bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
body = next(o for o in bpy.data.objects if o.type == "MESH")
P = arm.pose.bones
for pb in P:
    pb.rotation_mode = "QUATERNION"
skin_mod = next(m for m in body.modifiers if m.type == "ARMATURE")

# the chain, mouth to tail
root = next(b for b in arm.data.bones if b.parent is None)
CHAIN = [root.name]
while arm.data.bones[CHAIN[-1]].children:
    CHAIN.append(arm.data.bones[CHAIN[-1]].children[0].name)


def upd():
    bpy.context.view_layer.update()


def mesh_co():
    skin_mod.show_viewport = True; upd()
    dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); ev.to_mesh_clear()
    M = np.array(body.matrix_world)
    return co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]


# ------------------------------------------------------------------ scale to LENGTH along the chain
def joints_world():
    pts = [arm.matrix_world @ arm.data.bones[n].head_local for n in CHAIN]
    pts.append(arm.matrix_world @ arm.data.bones[CHAIN[-1]].tail_local)
    return pts


J = joints_world()
L0 = sum((b - a).length for a, b in zip(J, J[1:]))
arm.scale = arm.scale * (LENGTH / L0)
upd()
AW = arm.matrix_world.copy(); AWi = AW.inverted(); AWR = AW.to_3x3().normalized()
J = joints_world()
SEG = [(b - a).length for a, b in zip(J, J[1:])]
LT = sum(SEG)
# body radius: how far the skin sits from the chain, middle third of the body
co = np.array([(body.matrix_world @ v.co)[:] for v in body.data.vertices])
dense = np.array([a_.lerp(b_, t) for a_, b_ in zip(J, J[1:]) for t in np.linspace(0, 1, 8)])
d = np.min(np.linalg.norm(co[:, None, :] - dense[None, :, :], axis=2), axis=1)
RAD = float(np.median(d)) + 0.02                        # the skin's distance from the spine (belly side a bit fuller)
print("chain", len(CHAIN), "bones, length", round(LT, 3), "radius", round(RAD, 3))
REST_WROT = {n: (AWR @ arm.data.bones[n].matrix_local.to_3x3()).normalized() for n in CHAIN}
REST_DIR = {n: (J[i + 1] - J[i]).normalized() for i, n in enumerate(CHAIN)}


# ------------------------------------------------------------------ spine curve -> bones
def curve(head, yaw0, yaw_of_s, pitch_of_s):
    """Joint points from the mouth back: head point, the heading of the body at the mouth (yaw0, 0 =
    facing -Y), the sideways bend yaw(s) and the downward slope pitch(s) along the body (s in metres)."""
    pts = [Vector(head)]
    s = 0.0
    for l in SEG:
        sm = s + l / 2
        th = yaw0 + yaw_of_s(sm); ph = pitch_of_s(sm)
        dvec = Vector((-math.sin(th) * math.cos(ph), math.cos(th) * math.cos(ph), -math.sin(ph)))
        pts.append(pts[-1] + dvec * l)
        s += l
    return pts


def ground_curve(pts):
    """Nothing below the ground: the centreline keeps at least one radius up."""
    return [Vector((p.x, p.y, max(p.z, RAD))) for p in pts]


def pose_curve(pts):
    for i, n in enumerate(CHAIN):
        pb = P[n]
        want = (pts[i + 1] - pts[i]).normalized()
        R = REST_DIR[n].rotation_difference(want).to_matrix() @ REST_WROT[n]
        Ra = (AWR.inverted() @ R).normalized()
        sc_ = pb.matrix.to_scale()
        pb.matrix = Matrix.Translation(AWi @ pts[i]) @ Ra.to_4x4() @ Matrix.Diagonal((sc_.x, sc_.y, sc_.z, 1.0))
        upd()


def centred(pts, at=Vector((0, 0, 0))):
    """Move the curve so the middle of the body sits over `at` (the actor's spot)."""
    c = pts[len(pts) // 2]
    off = Vector((at.x - c.x, at.y - c.y, 0))
    return [p + off for p in pts]


def smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def rear_profile(lift_len, angle):
    """Pitch along the body for a reared front: steep at the mouth, flat after lift_len."""
    return lambda s: angle * max(0.0, 1 - s / max(lift_len, 1e-3)) ** 1.5 * 2.0


def head_height(pitch):
    """Height the mouth needs so the rest of the body lies on the ground."""
    s, h = 0.0, RAD
    for l in SEG:
        h += math.sin(pitch(s + l / 2)) * l; s += l
    return h


def rest_params():
    return dict(amp=0.28, wl=LT * 1.1, phase=0.0, lift=0.38, rear=0.32, yaw0=0.0, neck=0.0, curl=0.0)


def build(p, at=Vector((0, 0, 0)), head=None):
    def yaw(s):
        return (p["amp"] * math.sin(2 * math.pi * s / p["wl"] + p["phase"]) * min(1.0, s / 0.25 + 0.3)
                + p["neck"] * max(0.0, 1 - s / 0.3) + p["curl"] * (s / LT) ** 1.2 * 2.6)
    pitch = rear_profile(p["lift"], p["rear"])
    if head is None:
        pts = curve(Vector((0, 0, head_height(pitch))), p["yaw0"], yaw, pitch)
        pts = centred(pts, at)
    else:
        # reared onto something: find how steeply the front must rise for the rest to lie on the ground
        lo, hi = 0.0, 1.5
        for _ in range(30):
            mid_ = (lo + hi) / 2
            if head_height(rear_profile(p["lift"], mid_)) < head.z:
                lo = mid_
            else:
                hi = mid_
        pts = curve(head, p["yaw0"], yaw, rear_profile(p["lift"], lo))
    return ground_curve(pts)


def lerp(a, b, t):
    return {k: a[k] + (b[k] - a[k]) * t for k in a}


clips = {}


def key_all(f):
    for n in CHAIN:
        P[n].keyframe_insert("rotation_quaternion", frame=f, group=n)
        P[n].keyframe_insert("location", frame=f, group=n)
        P[n].keyframe_insert("scale", frame=f, group=n)


def clip(name, n, fn):
    act = bpy.data.actions.new(name); act.use_fake_user = True
    arm.animation_data_create(); arm.animation_data.action = act
    for f in range(n + 1):
        pose_curve(fn(f, n))
        key_all(f)
    clips[name] = n
    arm.animation_data.action = None
    print("clip", name, n)


skin_mod.show_viewport = False
REST = rest_params()


def idle(f, n):
    t = f / n; w = 2 * math.pi * t
    p = dict(REST)
    p["phase"] = 0.35 * math.sin(w)
    p["neck"] = 0.35 * math.sin(w + 0.6) + 0.12 * math.sin(3 * w)            # the blind head casting about
    p["rear"] = REST["rear"] * (1 + 0.18 * math.sin(2 * w))                    # lifting, sniffing
    p["amp"] = REST["amp"] * (1 + 0.1 * math.sin(w + 1.3))
    return build(p)


def crawl(f, n):
    # serpentine: in the body's frame the wave runs back along it at the crawl speed, so each point
    # traces the path of the one in front (the Actor carries the worm forward at CRAWL_V)
    p = dict(REST)
    p["wl"] = CRAWL_V * n
    p["phase"] = -2 * math.pi * f / n
    p["amp"] = 0.42
    p["rear"] = 0.22; p["lift"] = 0.3
    return build(p)


BITE_N, BITE_HIT = 20, 11


def bite(f, n):
    coil = smooth(0, 7, f) * (1 - smooth(8, 11, f))
    strike = smooth(8, 11, f) * (1 - smooth(13, 19, f))
    p = dict(REST)
    p["amp"] = REST["amp"] + 0.35 * coil - 0.18 * strike                       # S-coil, then straight
    p["wl"] = REST["wl"] * (1 - 0.35 * coil)
    p["rear"] = REST["rear"] + 0.35 * coil - 0.12 * strike
    p["lift"] = REST["lift"] + 0.1 * coil + 0.15 * strike
    p["neck"] = 0.15 * math.sin(f * 1.7) * strike
    at = Vector((0, 0.10 * coil - 0.28 * strike, 0))                           # drawn back, then thrown forward
    return build(p, at)


def hit(f, n):
    k = smooth(0, 2, f) * (1 - smooth(4, 11, f))
    p = dict(REST)
    p["rear"] = REST["rear"] + 0.3 * k
    p["neck"] = -0.5 * k
    p["phase"] = 1.2 * k
    p["amp"] = REST["amp"] + 0.2 * k
    return build(p, Vector((0, 0.06 * k, 0)))


def death(f, n):
    thrash = smooth(0, 3, f) * (1 - smooth(10, 18, f))
    fall = smooth(6, 20, f)
    p = dict(REST)
    p["phase"] = 1.6 * thrash * math.sin(f / 1.4)
    p["neck"] = 0.6 * thrash * math.sin(f / 1.1)
    p["rear"] = (REST["rear"] + 0.25 * thrash * math.sin(f / 1.7)) * (1 - fall)
    p["curl"] = 0.85 * fall
    p["amp"] = REST["amp"] * (1 - 0.6 * fall)
    return build(p)


def chew_params(u):
    w = 2 * math.pi * u
    bite_ = max(0.0, math.sin(3 * w)) ** 0.7
    tug = math.sin(3 * w - 1.2)
    p = dict(REST)
    p["rear"] = 0.95; p["lift"] = 0.66; p["amp"] = 0.18
    p["neck"] = 0.18 * math.sin(w) + 0.06 * math.sin(3 * w + 1.0)
    return p, tug, bite_


def chew(f, n):
    p, tug, bite_ = chew_params(f / n)
    # the mouth on the pipe, worrying at it; the body trails back on the ground
    head = CHEW_TARGET + Vector((0.02 * math.sin(2 * math.pi * f / n), 0.03 * max(0.0, tug), 0.025 * bite_ - 0.02 * max(0.0, tug)))
    yaw0 = math.atan2(-CHEW_TARGET.x, -CHEW_TARGET.y) * 0.6
    p["yaw0"] = yaw0
    return build(p, head=head)


def release(f, n):
    t = smooth(0.0, 1.0, (f + 1) / n)
    jerk = math.sin(math.pi * t)
    p0, _, _ = chew_params(0.0)
    p0["yaw0"] = math.atan2(-CHEW_TARGET.x, -CHEW_TARGET.y) * 0.6
    p = lerp(p0, dict(REST), t)
    p["rear"] += 0.2 * jerk
    chew_pts = build(p0, head=CHEW_TARGET)
    rest_pts = build(p)
    return [a.lerp(b, t) for a, b in zip(chew_pts, rest_pts)]


clip("idle", 32, idle)
clip("crawl", CRAWL_N, crawl)
clip("bite", BITE_N, bite)
clip("hit", 12, hit)
clip("death", 32, death)
clip("chew", 36, chew)
clip("release", 14, release)
skin_mod.show_viewport = True

# ------------------------------------------------------------------ ground, view box, export
PPM, e, m = 165.0, math.radians(47.0), 12
res = {}
for name, n in clips.items():
    arm.animation_data.action = bpy.data.actions[name]
    lows = []
    for f in range(0, n + 1, 2):
        sc.frame_set(f); c = mesh_co(); lows.append(float(c[:, 2].min()))
        r = float(np.sqrt(c[:, 0] ** 2 + c[:, 1] ** 2).max()); top = float(c[:, 2].max())
        for big in (False, True):
            if big or name != "death":
                rr, tt = res.get(big, (0.0, 0.0)); res[big] = (max(rr, r), max(tt, top))
    print("ground", name, " ".join(f"{z:+.3f}" for z in lows))
VIEW = {}
for big, (r, top) in res.items():
    above = (r * math.sin(e) + top * math.cos(e)) * PPM
    pre = "big_" if big else ""
    VIEW[pre + "w"] = int(math.ceil(2 * r * PPM)) + 2 * m
    VIEW[pre + "h"] = int(math.ceil(above + r * math.sin(e) * PPM)) + 2 * m
    VIEW["big_foot_y" if big else "foot_y"] = int(math.ceil(above)) + m
print("NUMBERS", json.dumps({"view": VIEW, "lengths": clips}))

for mt in bpy.data.materials:
    if mt.node_tree:
        for nd in mt.node_tree.nodes:
            if nd.type == "BSDF_PRINCIPLED":
                for nm in ("Metallic", "Roughness") + (() if KEEP_NORMAL else ("Normal",)):
                    for l in list(nd.inputs[nm].links):
                        mt.node_tree.links.remove(l)
for img in bpy.data.images:
    if img.users and img.size[0] > TEX_MAX:
        img.scale(TEX_MAX, max(1, img.size[1] * TEX_MAX // img.size[0]))
for img in bpy.data.images:                               # colour as JPEG; only the normal map stays lossless
    if img.users and "normal" not in img.name.lower():
        img.file_format = "JPEG"
arm.animation_data.action = None
sc.frame_set(0)
bpy.ops.export_scene.gltf(filepath=OUT + ".glb", export_format="GLB", export_animations=True,
                          export_animation_mode="ACTIONS", export_force_sampling=True, export_frame_range=False,
                          export_def_bones=False, export_apply=False, use_selection=False,
                          export_image_format="JPEG", export_jpeg_quality=92 if KEEP_NORMAL else 88)
json.dump({**({"normal_strength": 1.6, "band_soft": 0.06, "rim": 0.6} if KEEP_NORMAL else {}), "fps_src": FPS, "clips": {c: c for c in clips}, "idle_loop_src": [0, 32], "height_m": 0.5, "exposure": 1.1,
           "lengths": clips, "view": VIEW},
          open(OUT + ".json", "w"), indent=1)
for img in bpy.data.images:
    try:
        if img.source == "FILE" or img.is_dirty:
            img.pack()
    except RuntimeError:
        pass
bpy.ops.wm.save_as_mainfile(filepath=OUT + ".blend")
print("exported", OUT)
