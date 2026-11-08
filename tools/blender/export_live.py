"""Export a character for live 3D rendering in the game (Godot): the rigged model with its clips,
the pistol locked to the right hand (as render_character.py places it), and the aimed-shot sequence
baked at pitch 0 as one action ("aim_seq") - the game adds the pitch live with the same bone shares
render_aim.py uses. Writes OUT.glb and OUT.json (clip map, aim weights, pitch shares, stray meshes removed).

Usage: python3 -I export_live.py model.glb OUT_BASENAME
"""
import sys, os, json, math
import bpy, bmesh
from mathutils import Vector, Matrix

MODEL, OUT = sys.argv[1], sys.argv[2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=MODEL)
for o in [o for o in bpy.data.objects if o.type == "MESH" and not o.name.startswith("tripo")]:
    bpy.data.objects.remove(o, do_unlink=True)                     # stray helper meshes (an icosphere)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
P = arm.pose.bones
sc = bpy.context.scene


def act(name):
    if name in bpy.data.actions:
        return bpy.data.actions[name]
    return next(a for a in bpy.data.actions if a.name.lower().startswith(name))


# ---- the pistol, exactly where render_character.py puts it (pose: pistol_aim, frame 0)
arm.animation_data.action = act("pistol_aim"); sc.frame_set(0); bpy.context.view_layer.update()
W = arm.matrix_world
wrist = W @ P["mixamorig:RightHand"].head
knuck = W @ P["mixamorig:RightHandMiddle1"].head
shoulder = W @ P["mixamorig:RightArm"].head
palm = wrist.lerp(knuck, 0.55)
aim = (knuck - shoulder).normalized()
up = Vector((0, 0, 1)); side = up.cross(aim).normalized(); up = aim.cross(side).normalized()
basis = Matrix((aim, side, up)).transposed().to_4x4()


def add_box(bm, x0, x1, y0, y1, z0, z1, mi, tilt=0.0):
    vs = []
    for x in (x0, x1):
        for y in (y0, y1):
            for z in (z0, z1):
                vs.append(bm.verts.new((x + (z - z1) * tilt, y, z)))
    for f in [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]:
        bm.faces.new([vs[i] for i in f]).material_index = mi


me = bpy.data.meshes.new("Pistol"); bm = bmesh.new()
add_box(bm, -0.035, 0.155, -0.014, 0.014, 0.022, 0.058, 0)
add_box(bm, -0.030, 0.012, -0.013, 0.013, -0.075, 0.024, 1, tilt=0.28)
add_box(bm, 0.010, 0.040, -0.004, 0.004, -0.012, 0.022, 0)
bm.to_mesh(me); bm.free()
for nm, col in (("PistolSteel", (0.05, 0.05, 0.055)), ("PistolGrip", (0.12, 0.065, 0.03))):
    m = bpy.data.materials.new(nm); m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*[c ** 2.2 for c in col], 1)   # sRGB-intended colours
    m.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0.8 if "Steel" in nm else 0.0
    m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.35 if "Steel" in nm else 0.7
    me.materials.append(m)
gun = bpy.data.objects.new("Pistol", me); sc.collection.objects.link(gun)
gun.parent = arm; gun.parent_type = "BONE"; gun.parent_bone = "mixamorig:RightHand"
bpy.context.view_layer.update()
gun.matrix_world = Matrix.Translation(palm) @ basis

# ---- the aimed shot at pitch 0, baked: stance -> shoot (raise), the shoot clip, hold, -> stance (lower)
RAISE, HOLD, LOWER = 4, 2, 6
bones = list(P)
for pb in bones:
    pb.rotation_mode = "QUATERNION"


def sample(name, frame):
    arm.animation_data.action = act(name); sc.frame_set(int(frame)); bpy.context.view_layer.update()
    return {pb.name: (pb.rotation_quaternion.copy(), pb.location.copy()) for pb in bones}


def smooth(t):
    return t * t * (3 - 2 * t)


stance = sample("pistol_idle", int(act("pistol_idle").frame_range[0]))
sa = act("pistol_shoot")
shoot = [sample("pistol_shoot", f) for f in range(int(sa.frame_range[0]), int(round(sa.frame_range[1])) + 1)]
seq = []
for i in range(RAISE):
    t = smooth((i + 1) / RAISE); seq.append((stance, shoot[0], t, t))
for p in shoot[1:]:
    seq.append((p, p, 0.0, 1.0))
for _ in range(HOLD):
    seq.append((shoot[-1], shoot[-1], 0.0, 1.0))
for i in range(LOWER):
    t = smooth((i + 1) / LOWER); seq.append((shoot[-1], stance, t, 1.0 - t))
baked = bpy.data.actions.new("aim_seq")
arm.animation_data.action = baked
for k, (a, b, t, w) in enumerate(seq):
    for pb in bones:
        qa, la = a[pb.name]; qb, lb = b[pb.name]
        pb.rotation_quaternion = qa.slerp(qb, t); pb.location = la.lerp(lb, t)
        pb.keyframe_insert("rotation_quaternion", frame=k); pb.keyframe_insert("location", frame=k)
arm.animation_data.action = act("idle")

# ---- scale to the same 1.75 m the sprite renders use (measured on the posed mesh, idle frame 0)
arm.animation_data.action = act("idle"); sc.frame_set(0); bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
zs = []
for o in bpy.data.objects:
    if o.type == "MESH" and o.name.startswith("tripo"):
        e = o.evaluated_get(dg); m_ = e.to_mesh(); zs += [(e.matrix_world @ v.co).z for v in m_.vertices]; e.to_mesh_clear()
s_ = 1.75 / (max(zs) - min(zs))
arm.scale = arm.scale * s_
gun.scale = gun.scale / s_                     # the pistol is in real metres, not the source rig's units
arm.location = arm.location - Vector((0, 0, min(zs) * s_))
print("height scale", s_)

# ---- export (every action) and the sidecar the game reads
for a in bpy.data.actions:
    a.use_fake_user = True
bpy.ops.export_scene.gltf(filepath=OUT + ".glb", export_format="GLB", export_animations=True,
                          export_animation_mode="ACTIONS", export_force_sampling=True, export_frame_range=False,
                          export_def_bones=False, export_apply=False, use_selection=False)
side = {
    "fps_src": 24,
    "clips": {"walk": "walk", "run": "run", "idle": "idle", "hit": "hit_chest", "pistol_idle": "pistol_idle",
              "pistol_attack": "pistol_attack", "death": "death", "fall": "fall"},
    "idle_loop_src": [0, 95],
    "aim": {"anim": "aim_seq", "raise": [0, RAISE], "shot": [RAISE - 1, RAISE - 1 + len(shoot) + HOLD],
            "lower": [RAISE - 1 + len(shoot) + HOLD - 1, len(seq)], "hold": RAISE - 1 + len(shoot) + HOLD - 1,
            "weights": [round(s[3], 4) for s in seq]},
    "pitch_shares": [["mixamorig_Spine", 0.12], ["mixamorig_Spine1", 0.12], ["mixamorig_Spine2", 0.12],
                     ["mixamorig_Neck", 0.3], ["mixamorig_LeftArm", 0.64], ["mixamorig_RightArm", 0.64]],
    "gun_clips": ["pistol_idle", "pistol_attack", "pistol_raise", "pistol_shot", "pistol_lower", "pistol_hold"],
    "height_m": 1.75,
}
json.dump(side, open(OUT + ".json", "w"), indent=1)
print("exported", OUT, len(seq), "aim frames", [a.name for a in bpy.data.actions])
