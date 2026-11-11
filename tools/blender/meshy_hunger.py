"""The Tattered Hunger (Meshy model, Mixamo rig) -> game-ready live 3D. Replaces the Infected.

Keeps Meshy's own clips (Alert -> idle, Walking -> walk, Running -> run, Left_Hook_from_Guard -> bite),
retargets hit and death from another Mixamo-rigged character (the Changed: same bone names and axes),
scales to 1.75 m with the feet on the ground, drops Meshy's helper sphere, slims the materials to base
colour (the toon shader reads only that) and exports GLB + json for game/scripts/puppet3d.gd.
It prints the numbers character.json needs (frames, speeds, the bite's hit frame).

Usage: python3 -I meshy_hunger.py IN.glb SRC_WITH_HIT_DEATH.glb OUT_BASENAME [height_m]
"""
import sys, json, math
import bpy
from mathutils import Quaternion, Vector

IN, SRC, OUT = sys.argv[1:4]
HEIGHT = float(sys.argv[4]) if len(sys.argv) > 4 else 1.75
FPS = 24
RENAME = {"Alert": "idle", "Walking": "walk", "Running": "run", "Left_Hook_from_Guard": "bite"}
HIPS = "mixamorig:Hips"

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS


def load(path):
    before = set(bpy.data.objects); acts = set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    for o in list(new):
        if o.type == "MESH" and o.parent is None:                 # Meshy / Tripo helper meshes
            bpy.data.objects.remove(o, do_unlink=True); new.remove(o)
    return next(o for o in new if o.type == "ARMATURE"), [o for o in new if o.type == "MESH"], [a for a in bpy.data.actions if a not in acts]


src_arm, src_meshes, src_actions = load(SRC)
for m in src_meshes:
    bpy.data.objects.remove(m, do_unlink=True)
arm, meshes, own = load(IN)
body = meshes[0]

# ------------------------------------------------------------------ retarget hit and death
# Meshy's Mixamo rig rolls its bones differently from Tripo's, so orientations can't be copied as they
# are: each bone takes the source's rotation away from its rest pose, then is swung so it points exactly
# where the source bone points (that also absorbs A-pose / T-pose rest differences).
TB, SB = arm.data.bones, src_arm.data.bones
names = [b.name for b in TB if b.name in SB]                       # parents first
scale = TB[HIPS].head_local.length / max(SB[HIPS].head_local.length, 1e-6)
src_rest = {n: SB[n].matrix_local.to_quaternion() for n in names}
tgt_rest = {n: TB[n].matrix_local.to_quaternion() for n in names}
tgt_rel = {n: (tgt_rest[TB[n].parent.name].inverted() @ tgt_rest[n]) if TB[n].parent else tgt_rest[n] for n in names}
Y = Vector((0, 1, 0))
arm.animation_data_create(); src_arm.animation_data_create()
for key in ("hit", "death"):
    act = next(a for a in src_actions if a.name.lower() == key)
    src_arm.animation_data.action = act
    f0, f1 = (int(round(v)) for v in act.frame_range)
    new = bpy.data.actions.new(key); new.use_fake_user = True
    arm.animation_data.action = new
    last = {}
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        Ms = {n: src_arm.pose.bones[n].matrix.to_quaternion() for n in names}
        Mt = {}
        for n in names:
            cand = (Ms[n] @ src_rest[n].inverted()) @ tgt_rest[n]
            Mt[n] = (cand @ Y).rotation_difference(Ms[n] @ Y) @ cand
            b = TB[n]
            parent = Mt.get(b.parent.name, tgt_rest.get(b.parent.name, Quaternion())) if b.parent else Quaternion()
            local = tgt_rel[n].inverted() @ parent.inverted() @ Mt[n]
            if n in last and last[n].dot(local) < 0:
                local.negate()
            last[n] = local
            pb = arm.pose.bones[n]
            pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = local
            pb.keyframe_insert("rotation_quaternion", frame=f - f0, group=n)
            if n == HIPS:
                p = src_arm.pose.bones[HIPS].head * scale
                pb.location = tgt_rest[HIPS].inverted() @ (p - TB[HIPS].head_local)
                pb.keyframe_insert("location", frame=f - f0, group=n)
    print("retargeted", key, f1 - f0, "frames")
bpy.data.objects.remove(src_arm, do_unlink=True)
for a in src_actions:
    bpy.data.actions.remove(a)
for a in bpy.data.actions:
    if a.name.endswith(".001"):
        a.name = a.name[:-4]

# ------------------------------------------------------------------ Meshy's clips: names, whole-frame loops
for a in own:
    a.name = RENAME.get(a.name, a.name); a.use_fake_user = True


def fcurves(act):
    """All F-curves of an action (Blender 4.4+ keeps them in layers / strips / channel bags)."""
    if hasattr(act, "fcurves") and not hasattr(act, "layers"):
        return list(act.fcurves)
    return [fc for ly in act.layers for st in ly.strips for cb in st.channelbags for fc in cb.fcurves]


def retime(act, frames):
    """Stretch a loop to a whole number of frames (the game's clock counts whole frames)."""
    k = frames / (act.frame_range[1] - act.frame_range[0])
    for fc in fcurves(act):
        for kp in fc.keyframe_points:
            kp.co.x *= k; kp.handle_left.x *= k; kp.handle_right.x *= k
    act.use_frame_range = True
    act.frame_range = (0, frames)


LOOPS = {}
for key in ("walk", "run"):
    act = bpy.data.actions[key]
    n = int(round(act.frame_range[1] - act.frame_range[0]))
    retime(act, n); LOOPS[key] = n

# ------------------------------------------------------------------ size: 1.75 m, feet on the ground in the idle pose
zs = [v.co.z for v in body.data.vertices]
k = HEIGHT / (max(zs) - min(zs))
arm.scale = arm.scale * k
arm.animation_data.action = bpy.data.actions["idle"]; sc.frame_set(0); bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
me = body.evaluated_get(dg).to_mesh()
low = min((body.matrix_world @ v.co).z for v in me.vertices)
body.evaluated_get(dg).to_mesh_clear()
arm.location.z -= low
bpy.context.view_layer.update()
print("scale", round(k, 4), "rest height", round(max(zs) - min(zs), 3))


def wpos(bone):
    return arm.matrix_world @ arm.pose.bones[bone].head


def speed(key):
    """Ground speed (m per frame) of a locomotion clip: the hips' own travel if the clip carries it,
    otherwise how fast a planted foot slides back under the body."""
    arm.animation_data.action = bpy.data.actions[key]
    n = LOOPS[key]
    sc.frame_set(0); h0 = wpos(HIPS); sc.frame_set(n); h1 = wpos(HIPS)
    travel = (h1 - h0).xy.length
    if travel > 0.05:
        return travel / n, "hips"
    best = 0.0
    for foot in ("mixamorig:LeftToeBase", "mixamorig:RightToeBase"):
        pts = []
        for f in range(n + 1):
            sc.frame_set(f); pts.append(wpos(foot) - wpos(HIPS) * Vector((1, 1, 0)))
        zmin = min(p.z for p in pts)
        planted = [p for p in pts if p.z < zmin + 0.02]
        if len(planted) > 2:
            best = max(best, abs(planted[-1].y - planted[0].y) / (len(planted) - 1))
    return best, "feet"


V = {k_: speed(k_) for k_ in ("walk", "run")}
# the bite's hit frame: the left fist furthest out from the chest
arm.animation_data.action = bpy.data.actions["bite"]
reach = []
for f in range(0, 25):
    sc.frame_set(f)
    d = wpos("mixamorig:LeftHand") - wpos("mixamorig:Spine2")
    reach.append((d.xy.length, f))
hit_frame = max(reach)[1]
lengths = {a.name: int(round(a.frame_range[1] - a.frame_range[0])) for a in bpy.data.actions}


def view_box(names_small, names_big):
    """The viewport the puppet renders into: room for every frame (any facing), standing and lying."""
    import numpy as np
    PPM, e, m = 165.0, math.radians(47.0), 12
    res = []
    for names in (names_small, names_big):
        r = top = 0.0
        for nm in names:
            arm.animation_data.action = bpy.data.actions[nm]
            for f in range(0, lengths[nm] + 1, 3):
                sc.frame_set(f)
                dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh()
                co = np.array([(body.matrix_world @ v.co)[:] for v in me.vertices]); ev.to_mesh_clear()
                co[:, :2] -= np.array((wpos(HIPS).x, wpos(HIPS).y)) * (nm in ("walk", "run"))   # played in place
                r = max(r, float(np.sqrt(co[:, 0] ** 2 + co[:, 1] ** 2).max())); top = max(top, float(co[:, 2].max()))
        W = int(math.ceil(2 * r * PPM)) + 2 * m
        above = (r * math.sin(e) + top * math.cos(e)) * PPM
        res.append((W, int(math.ceil(above + r * math.sin(e) * PPM)) + 2 * m, int(math.ceil(above)) + m))
    return {"w": res[0][0], "h": res[0][1], "foot_y": res[0][2], "big_w": res[1][0], "big_h": res[1][1], "big_foot_y": res[1][2]}


VIEW = view_box(["idle", "walk", "run", "bite", "hit"], ["idle", "walk", "run", "bite", "hit", "death"])
print("NUMBERS", json.dumps({"view": VIEW, "lengths": lengths, "speed_m_per_frame": {k_: round(v[0], 4) for k_, v in V.items()},
                             "speed_from": {k_: v[1] for k_, v in V.items()}, "bite_hit": hit_frame}))

# ------------------------------------------------------------------ materials: base colour only, 1024 px
for m in bpy.data.materials:
    if m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED":
                for name in ("Normal", "Metallic", "Roughness"):
                    for l in list(n.inputs[name].links):
                        m.node_tree.links.remove(l)
for img in bpy.data.images:
    if img.users and img.size[0] > 1024:
        img.scale(1024, max(1, img.size[1] * 1024 // img.size[0]))

arm.animation_data.action = None
bpy.ops.export_scene.gltf(filepath=OUT + ".glb", export_format="GLB", export_animations=True,
                          export_animation_mode="ACTIONS", export_force_sampling=True, export_frame_range=False,
                          export_def_bones=False, export_apply=False, use_selection=False,
                          export_image_format="JPEG", export_jpeg_quality=88)
json.dump({"fps_src": FPS, "clips": {c: c for c in ("idle", "walk", "run", "bite", "hit", "death")},
           "idle_loop_src": [0, lengths["idle"]], "height_m": HEIGHT, "exposure": 1.2, "creature": "infected",
           "lengths": lengths, "bite_hit": hit_frame, "view": VIEW},
          open(OUT + ".json", "w"), indent=1)
for img in bpy.data.images:
    if img.source == "FILE" or img.is_dirty:
        try:
            img.pack()
        except RuntimeError:
            pass
bpy.ops.wm.save_as_mainfile(filepath=OUT + ".blend")
print("exported", OUT)
