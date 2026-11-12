"""The Spined Wasteland Stalker (Meshy model, 27-bone quadruped rig, one walk clip) -> game-ready live 3D.
Replaces the Feral.

Meshy gave it a walk only, and no jaw. This script:
  - normalises it (height, feet on the ground, centred, Meshy's helper sphere dropped, walk played in place),
  - adds a jaw bone and weights the lower jaw to it (found on the mesh: below the line of the open mouth,
    connected to the chin), so the mouth can gape and snap,
  - builds a standing pose from the walk and animates bite (the attack: gather, gape, lunge, snap,
    shake, recover), plus idle, hit and death, with the planted paws held on the ground by a small
    CCD IK solver (the rig's bones carry no usable tails, so everything is posed in armature space
    from joint positions),
  - exports GLB + json (clip map, sprite-clock numbers, view box) and a packed .blend.

Usage: python3 -I meshy_stalker.py IN.glb OUT_BASENAME [height_m] [--qc]
"""
import sys, json, math
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

IN, OUT = sys.argv[1], sys.argv[2]
HEIGHT = float(sys.argv[3]) if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else 1.2
FPS = 24
KEEP_NORMAL = "--flat" not in sys.argv     # default: keep the normal map, 2048 px textures, soft bands + rim (art rule); --flat = old base-colour-only look
TEX_MAX = 2048 if KEEP_NORMAL else 1024
SIDES = ("", "R_")                       # left bones have no prefix, right ones "R_"
LEGS = {f"{s}{kind}": ([f"{s}{kind}", f"{s}{kind}0", f"{s}{kind}1"], f"{s}{kind}2") for s in SIDES for kind in ("frontleg", "backleg")}

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS
bpy.ops.import_scene.gltf(filepath=IN)
for o in list(bpy.data.objects):
    if o.type == "MESH" and o.parent is None:
        bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
body = next(o for o in bpy.data.objects if o.type == "MESH")
walk = bpy.data.actions[0]
walk.name = "walk"; walk.use_fake_user = True
arm.animation_data.action = walk
P = arm.pose.bones
for pb in P:
    pb.rotation_mode = "QUATERNION"
skin_mod = next(m for m in body.modifiers if m.type == "ARMATURE")


def fcurves(act):
    if hasattr(act, "layers"):
        return [fc for ly in act.layers for st in ly.strips for cb in st.channelbags for fc in cb.fcurves]
    return list(act.fcurves)


def upd():
    bpy.context.view_layer.update()


def mesh_co():
    skin_mod.show_viewport = True
    upd()
    dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); ev.to_mesh_clear()
    co = co.reshape(-1, 3)
    M = np.array(body.matrix_world)
    return co @ M[:3, :3].T + M[:3, 3]


# ------------------------------------------------------------------ size and placement
sc.frame_set(0)
co = mesh_co()
k = HEIGHT / (co[:, 2].max() - co[:, 2].min())
arm.scale = arm.scale * k
upd(); co = mesh_co()
arm.location -= Vector((co[:, 0].mean() * 0 + (co[:, 0].max() + co[:, 0].min()) / 2, (co[:, 1].max() + co[:, 1].min()) / 2, co[:, 2].min()))
upd()
lows = []
for f in range(int(walk.frame_range[1] - walk.frame_range[0])):
    sc.frame_set(f); lows.append(float(mesh_co()[:, 2].min()))
arm.location.z -= float(np.percentile(lows, 40))          # flat paws on the ground; toe-offs dig in a little
upd()
print("walk lows", [round(x, 3) for x in lows])
S = arm.matrix_world.to_scale().x                       # armature units -> metres
AW = arm.matrix_world.copy(); AWi = AW.inverted()
AWR = AW.to_3x3().normalized()                          # the rig is Y-up inside its object: world <-> armature turn


def W(v):          # armature space -> world (metres)
    return AW @ v


def A(v):          # world -> armature space
    return AWi @ v


# walk in place: take any travel out of the hips (the game moves the actor)
N_WALK = int(round(walk.frame_range[1] - walk.frame_range[0]))
sc.frame_set(0); h0 = W(P["Hips"].head); sc.frame_set(N_WALK); h1 = W(P["Hips"].head)
print("walk frames", N_WALK, "hips travel per loop", tuple(round(x, 3) for x in (h1 - h0)))
if (h1 - h0).xy.length > 0.05:
    # remove the linear drift from the Hips location channel (in its rest frame)
    rest_rot = arm.data.bones["Hips"].matrix_local.to_3x3()
    drift_a = A(h1) - A(h0)
    local = rest_rot.inverted() @ drift_a
    for fc in fcurves(walk):
        if fc.data_path == 'pose.bones["Hips"].location' and abs(local[fc.array_index]) > 1e-6:
            for kp in fc.keyframe_points:
                d = local[fc.array_index] * kp.co.x / N_WALK
                kp.co.y -= d; kp.handle_left.y -= d; kp.handle_right.y -= d
    upd()

# ground speed of the walk: how fast a planted paw slides back under the body
speeds = []
for leg, (chain, paw) in LEGS.items():
    pts = []
    for f in range(N_WALK + 1):
        sc.frame_set(f); pts.append(W(P[paw].head))
    zmin = min(p.z for p in pts)
    run, best = [], []
    for f_, p_ in enumerate(pts):                          # the longest stretch of frames on the ground
        if p_.z < zmin + 0.02:
            run.append((f_, p_))
            best = max(best, run, key=len)
        else:
            run = []
    if len(best) > 3:
        speeds.append(abs(best[-1][1].y - best[0][1].y) / (best[-1][0] - best[0][0]))
WALK_V = float(np.mean(speeds)) if speeds else 0.04
print("walk speed m/frame", round(WALK_V, 4), [round(s, 4) for s in speeds])

# ------------------------------------------------------------------ the jaw (picked on the mesh at walk frame 0)
# measured from the side at the game height 1.2 m: mouth corner at (y -0.49, z 0.71), the open mouth's
# midline falls 0.27 m per metre towards the snout, the chin is at (y -0.585, z 0.615)
sc.frame_set(0)
co = mesh_co()
s_ = HEIGHT / 1.2
corner = Vector((0, -0.49 * s_, 0.71 * s_)); slope = 0.27
chin = Vector((0, -0.585 * s_, 0.615 * s_))
HINGE = Vector((0, -0.465 * s_, 0.718 * s_))
below = (co[:, 1] < corner.y + 0.015 * s_) & (co[:, 2] < corner.z + slope * (co[:, 1] - corner.y))
me = body.data
edges = np.empty(len(me.edges) * 2, np.int64); me.edges.foreach_get("vertices", edges); edges = edges.reshape(-1, 2)
parent = np.arange(len(me.vertices))
def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]; i = parent[i]
    return i
for a_, b_ in edges:
    ra, rb = find(a_), find(b_)
    if ra != rb:
        parent[ra] = rb
roots = np.array([find(i) for i in range(len(me.vertices))])
ids, counts = np.unique(roots, return_counts=True)
big = set(ids[counts > 0.05 * len(me.vertices)])
in_mouth = (co[:, 1] < corner.y + 0.015 * s_) & (co[:, 1] > corner.y - 0.2 * s_) & (co[:, 2] > corner.z - 0.16 * s_)
jaw = below & in_mouth
for r_ in ids:                                              # small pieces (teeth, gums) go whole, by their middle
    if r_ in big:
        continue
    m_ = roots == r_
    c_ = co[m_].mean(axis=0)
    if in_mouth[m_].any():
        jaw[m_] = c_[2] < corner.z + slope * (c_[1] - corner.y)
# soft at the back (the throat), full in front of the corner
wt = np.clip((corner.y + 0.015 * s_ - co[:, 1]) / (0.05 * s_), 0.0, 1.0) * jaw
print("lower jaw vertices", int(jaw.sum()), "of", len(co))

# the jaw bone, made in rest space: the hinge rides on the head bone
head_pose = P["head"].matrix.copy(); head_rest = arm.data.bones["head"].matrix_local.copy()
to_rest = head_rest @ head_pose.inverted()
hinge_rest = to_rest @ A(HINGE)
tip_rest = to_rest @ A(HINGE + Vector((0, -0.12, -0.05)) * s_)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
eb = arm.data.edit_bones
j = eb.new("jaw"); j.head = hinge_rest; j.tail = tip_rest
j.align_roll(to_rest.to_3x3() @ Vector((0, 0, 1)))
j.parent = eb["head"]; j.use_connect = False
bpy.ops.object.mode_set(mode="OBJECT")
P["jaw"].rotation_mode = "QUATERNION"
vg_jaw = body.vertex_groups.new(name="jaw")
for i in np.nonzero(wt > 0.0)[0]:
    v = me.vertices[int(i)]
    w = float(wt[i])
    for g in v.groups:
        g.weight *= (1.0 - w)
    vg_jaw.add([int(i)], w, "REPLACE")
HEAD_LAT = head_pose.to_quaternion().inverted() @ (AWR.inverted() @ Vector((1, 0, 0)))   # the head's own sideways axis

# ------------------------------------------------------------------ posing in armature space
skin_mod.show_viewport = False


def set_world_rot(name, R, pivot_w):
    """Rotate bone `name` (and so its children) by world rotation R (3x3) about world point pivot."""
    pb = P[name]
    p = A(pivot_w)
    Ra = AWR.inverted() @ R @ AWR                       # the same turn, in armature axes
    pb.matrix = Matrix.Translation(p) @ Ra.to_4x4() @ Matrix.Translation(-p) @ pb.matrix
    upd()


def rot(name, axis, deg, pivot_w=None):
    if abs(deg) < 1e-4:
        return
    set_world_rot(name, Matrix.Rotation(math.radians(deg), 3, Vector(axis).normalized()), pivot_w if pivot_w is not None else W(P[name].head))


def move(name, d_w):
    pb = P[name]
    pb.matrix = Matrix.Translation(A(W(Vector()) + Vector(d_w)) - A(W(Vector()))) @ pb.matrix
    upd()


def head_axis():
    return (AWR @ (P["head"].matrix.to_quaternion() @ HEAD_LAT)).normalized()


def reach(leg, target_w, lateral, iters=14):
    """CCD on a three-bone leg so the paw joint lands on target; bones bend about the body's sideways
    axis (hinges), the first one may also swing a little sideways; the paw keeps its standing angle."""
    chain, paw = LEGS[leg]
    paw_rot = PAW_ROT[paw]
    for it in range(iters):
        for b in reversed(chain):
            jw = W(P[b].head); ew = W(P[paw].head)
            v1, v2 = ew - jw, target_w - jw
            ax = lateral
            p1 = v1 - ax * v1.dot(ax); p2 = v2 - ax * v2.dot(ax)
            if p1.length < 1e-5 or p2.length < 1e-5:
                continue
            ang = p1.angle(p2)
            if p1.cross(p2).dot(ax) < 0:
                ang = -ang
            ang = max(-0.35, min(0.35, ang))
            set_world_rot(b, Matrix.Rotation(ang, 3, ax), jw)
            if b == chain[0]:
                v1, v2 = W(P[paw].head) - jw, target_w - jw
                q = v1.rotation_difference(v2)
                q = Quaternion(q.axis, max(-0.08, min(0.08, q.angle)))
                set_world_rot(b, q.to_matrix(), jw)
        if (W(P[paw].head) - target_w).length < 0.002:
            break
    pw = W(P[paw].head)
    sc_ = P[paw].matrix.to_scale()                        # keep the scale the rig carries down the chain
    R_a = (AWi.to_3x3() @ paw_rot.to_matrix()).normalized().to_4x4()
    P[paw].matrix = Matrix.Translation(A(pw)) @ R_a @ Matrix.Diagonal((sc_.x, sc_.y, sc_.z, 1.0))
    upd()


def key_all(f):
    for pb in P:
        pb.keyframe_insert("rotation_quaternion", frame=f, group=pb.name)
        pb.keyframe_insert("location", frame=f, group=pb.name)
        pb.keyframe_insert("scale", frame=f, group=pb.name)       # the Unreal take scales the hips


def smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# the standing pose: the walk averaged over its cycle (legs come out mid-stride), paws put down flat
avg = {pb.name: [Quaternion((0, 0, 0, 0)), Vector()] for pb in P if pb.name != "jaw"}
for f in range(N_WALK):
    sc.frame_set(f)
    for pb in P:
        if pb.name == "jaw":
            continue
        q = pb.rotation_quaternion.copy()
        if avg[pb.name][0].dot(q) < 0:
            q.negate()
        avg[pb.name][0] = Quaternion(avg[pb.name][0][:]) if False else avg[pb.name][0]
        a0 = avg[pb.name][0]
        avg[pb.name][0] = Quaternion((a0.w + q.w, a0.x + q.x, a0.y + q.y, a0.z + q.z))
        avg[pb.name][1] += pb.location
paw_z, PAW_ROT = {}, {}
for leg, (chain, paw) in LEGS.items():
    zs = []
    for f in range(N_WALK):
        sc.frame_set(f); zs.append(W(P[paw].head).z)
    zmin = min(zs)
    down = [f for f in range(N_WALK) if zs[f] < zmin + 0.01]
    fm = down[len(down) // 2]                              # mid-stance: the paw lies flat
    sc.frame_set(fm)
    paw_z[leg] = zs[fm]
    PAW_ROT[paw] = (AW.to_3x3() @ P[paw].matrix.to_3x3()).normalized().to_quaternion()
arm.animation_data.action = None
for pb in P:
    if pb.name == "jaw":
        pb.rotation_quaternion = Quaternion(); pb.location = Vector()
        continue
    pb.rotation_quaternion = avg[pb.name][0].normalized(); pb.location = avg[pb.name][1] / N_WALK
upd()
STAND_WROT = {pb.name: (AW.to_3x3() @ pb.matrix.to_3x3()).normalized().to_quaternion() for pb in P}
FEET = {leg: Vector((W(P[paw].head).x, W(P[paw].head).y, paw_z[leg])) for leg, (chain, paw) in LEGS.items()}
for leg in LEGS:
    reach(leg, FEET[leg], Vector((1, 0, 0)))
STAND = {pb.name: pb.matrix_basis.copy() for pb in P}
STAND_WROT = {pb.name: (AW.to_3x3() @ pb.matrix.to_3x3()).normalized().to_quaternion() for pb in P}
print("stand paws", {leg: tuple(round(x, 3) for x in W(P[LEGS[leg][1]].head)) for leg in LEGS})


def stand():
    for pb in P:
        pb.matrix_basis = STAND[pb.name]
    upd()


X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
TAIL = ["tail", "tailstart", "tail1", "tail2", "tail3"]


def plant(lateral=X, skip=()):
    for leg in LEGS:
        if leg not in skip:
            reach(leg, FEET[leg], lateral)


def jaw_open(deg):
    """+ opens wider than sculpted, - closes (about -18 shuts the teeth together)."""
    rot("jaw", head_axis(), deg, W(P["jaw"].head))


clips = {}


def clip(name, n, fn, ground_clamp=0):
    act = bpy.data.actions.new(name); act.use_fake_user = True
    arm.animation_data.action = act
    for f in range(n + 1):
        stand()
        fn(f, n)
        if ground_clamp:
            low = float(mesh_co()[:, 2].min()); skin_mod.show_viewport = False
            if low < 0.0 or (low > 0.0 and f >= ground_clamp):     # lying: rests on the ground, no floating
                move("Hips", (0, 0, -low))
        key_all(f)
    clips[name] = n
    arm.animation_data.action = None
    print("clip", name, n)


# bite: 22 frames, the teeth meet on frame 11
BITE_N, BITE_HIT = 22, 11


def bite(f, n):
    back = smooth(0, 6, f) * (1 - smooth(7, 10, f))          # gathers itself
    lunge = smooth(7, 11, f) * (1 - smooth(14, 21, f))       # throws itself forward
    gape = smooth(2, 8, f) * (1 - smooth(9.5, 11, f))        # jaw wide
    snap = smooth(10, 11, f) * (1 - smooth(14, 20, f))       # jaw shut on the target
    shake = math.sin((f - 11) * math.pi / 1.6) * max(0.0, 1 - (f - 11) / 5.0) * (f >= 11)
    hips = W(P["Hips"].head)
    move("Hips", (0, 0.07 * back - 0.17 * lunge, -0.05 * back - 0.01 * lunge))
    rot("Hips", X, -4 * back + 5 * lunge, W(P["Hips"].head))
    rot("chest", X, -7 * back + 5 * lunge)
    rot("head", X, -22 * back + 14 * lunge)                   # head drawn back and up, then driven down into the bite
    rot("head", W(P["head"].head) - W(P["chest"].head), 10 * shake)   # worrying shake once it has hold
    rot("head", Z, 5 * shake)
    jaw_open(26 * gape - 20 * snap)
    for i, b in enumerate(TAIL):
        rot(b, X, (8 * back - 14 * lunge) * (0.5 + 0.2 * i))
    # the left fore-paw comes up and rakes forward with the lunge; the other three stay planted
    lift = smooth(6, 10, f) * (1 - smooth(13, 19, f))
    plant(skip=("frontleg",))
    t = FEET["frontleg"] + Vector((0, -0.16 * lift - 0.05 * lunge, 0.13 * lift * (1 - 0.6 * smooth(10, 12, f))))
    reach("frontleg", t, X)


def idle(f, n):
    t = f / n
    br = math.sin(t * 2 * math.pi * 3)                        # three breaths a loop
    look = math.sin(t * 2 * math.pi) * 18 + (10 if 0.55 < t < 0.62 else 0)
    move("Hips", (0.008 * math.sin(t * 2 * math.pi), 0, 0.006 * br - 0.006))
    rot("chest", X, 1.5 * br)
    rot("chest", Z, look * 0.15)
    rot("head", Z, look * 0.6)
    rot("head", X, -4 + 6 * math.sin(t * 2 * math.pi * 6) * (0.3 < t < 0.45))   # sniffing
    rot("head", W(P["head"].head) - W(P["chest"].head), -5 * math.sin(t * 2 * math.pi))
    jaw_open(-6 + 8 * max(0.0, math.sin(t * 2 * math.pi * 8)) * (0.7 < t < 0.9))   # mouth half shut, chattering
    for i, b in enumerate(TAIL):
        rot(b, Z, 6 * math.sin(t * 2 * math.pi * 2 - i * 0.6))
    plant()


def hit(f, n):
    k = smooth(0, 3, f) * (1 - smooth(5, 13, f))
    move("Hips", (0, 0.06 * k, -0.02 * k))
    rot("Hips", Z, -7 * k)
    rot("chest", X, -9 * k)
    rot("chest", Z, 10 * k)
    rot("head", X, -16 * k)
    rot("head", Z, -20 * k)
    jaw_open(14 * k)
    plant()


DEATH_ROLL = 84.0


def death(f, n):
    rear = smooth(0, 6, f) * (1 - smooth(8, 14, f))
    fall = smooth(8, 22, f)
    curl = smooth(16, 32, f)
    hp = W(P["Hips"].head)
    move("Hips", (0.06 * fall, 0.03 * rear, 0.04 * rear))
    rot("chest", X, -12 * rear)
    rot("head", X, -14 * rear + 8 * fall)
    # roll onto its right side about the body's long axis, the whole animal together
    axis = (W(P["chest"].head) - W(P["Hips"].head)).normalized()
    rot("Hips", axis, -DEATH_ROLL * fall, W(P["Hips"].head))
    rot("head", W(P["head"].head) - W(P["chest"].head), -12 * fall)
    jaw_open(18 * smooth(14, 26, f))
    lat = (P["Hips"].matrix.to_quaternion() @ (STAND["Hips"].to_quaternion().inverted() @ Vector((1, 0, 0)))).normalized()
    # the legs draw in towards the belly as it dies
    for leg, (chain, paw) in LEGS.items():
        sgn = 1 if leg.startswith("front") or leg.startswith("R_front") else -1
        for i, b in enumerate(chain[1:]):
            rot(b, X, sgn * 30 * curl * (1 if i == 0 else -0.6))
    for i, b in enumerate(TAIL):
        rot(b, X, 10 * curl)


clip("idle", 48, idle)
clip("bite", BITE_N, bite)
clip("hit", 14, hit)
clip("death", 36, death, ground_clamp=12)
clips["walk"] = N_WALK
skin_mod.show_viewport = True

# ------------------------------------------------------------------ ground report and view box
def ground_and_view():
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
                    rr, tt = res.get(big, (0.0, 0.0))
                    res[big] = (max(rr, r), max(tt, top))
        print("ground", name, " ".join(f"{z:+.3f}" for z in lows))
    out = {}
    for big, (r, top) in res.items():
        Wd = int(math.ceil(2 * r * PPM)) + 2 * m
        above = (r * math.sin(e) + top * math.cos(e)) * PPM
        Hh = int(math.ceil(above + r * math.sin(e) * PPM)) + 2 * m
        pre = "big_" if big else ""
        out[pre + "w"], out[pre + "h"], out[("big_foot_y" if big else "foot_y")] = Wd, Hh, int(math.ceil(above)) + m
    return out


VIEW = ground_and_view()
print("NUMBERS", json.dumps({"view": VIEW, "lengths": clips, "walk_v": round(WALK_V, 4), "bite_hit": BITE_HIT}))

# ------------------------------------------------------------------ materials, export
for m in bpy.data.materials:
    if m.node_tree:
        for nd in m.node_tree.nodes:
            if nd.type == "BSDF_PRINCIPLED":
                for nm in ("Metallic", "Roughness") + (() if KEEP_NORMAL else ("Normal",)):
                    for l in list(nd.inputs[nm].links):
                        m.node_tree.links.remove(l)
HAS_NORMAL = KEEP_NORMAL and any(nd.type == "NORMAL_MAP" and nd.inputs["Color"].links
                                  for m in bpy.data.materials if m.node_tree for nd in m.node_tree.nodes)
for img in bpy.data.images:
    if img.users and img.size[0] > TEX_MAX:
        img.scale(TEX_MAX, max(1, img.size[1] * TEX_MAX // img.size[0]))
arm.animation_data.action = None
sc.frame_set(0)
bpy.ops.export_scene.gltf(filepath=OUT + ".glb", export_format="GLB", export_animations=True,
                          export_animation_mode="ACTIONS", export_force_sampling=True, export_frame_range=False,
                          export_def_bones=False, export_apply=False, use_selection=False,
                          export_image_format="AUTO" if HAS_NORMAL else "JPEG", export_jpeg_quality=92 if KEEP_NORMAL else 88)
json.dump({"fps_src": FPS, "clips": {c: c for c in clips}, "idle_loop_src": [0, 48], "height_m": HEIGHT, "exposure": 1.1,
           **({"normal_strength": 1.6 if HAS_NORMAL else 0.0, "band_soft": 0.06, "rim": 0.6} if KEEP_NORMAL else {}),
           "creature": "feral", "lengths": clips, "view": VIEW, "walk_v": round(WALK_V, 4), "bite_hit": BITE_HIT},
          open(OUT + ".json", "w"), indent=1)
for img in bpy.data.images:
    try:
        if img.source == "FILE" or img.is_dirty:
            img.pack()
    except RuntimeError:
        pass
bpy.ops.wm.save_as_mainfile(filepath=OUT + ".blend")
print("exported", OUT)
