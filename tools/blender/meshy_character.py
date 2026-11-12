"""A rigged Meshy character (Mixamo bone names) -> live 3D that plays an existing character's clips.

Every clip of SRC (a game-ready live GLB such as game/characters/player_3d/player.glb) is retargeted
onto the Meshy rig, so stride, timing, aim and the json numbers stay exactly what the game already uses
(CLAUDE.md: movement must never slide). A pistol parented to a hand bone in SRC is carried over.
The detail treatment is on by default (normal map kept, 2048 px JPEG q92, json normal_strength 1.6,
band_soft 0.06, rim 0.6); --flat for comparison only.

Usage: python3 -I meshy_character.py IN_rigged.glb SRC_live.glb SRC.json OUT_BASENAME [height_m] [--flat]
"""
import sys, json, math
import bpy
from mathutils import Quaternion, Vector, Matrix

IN, SRC, SRC_JSON, OUT = sys.argv[1:5]
HEIGHT = float(sys.argv[5]) if len(sys.argv) > 5 and not sys.argv[5].startswith("--") else 1.75
FPS = 24
HIPS = "mixamorig:Hips"
KEEP_NORMAL = "--flat" not in sys.argv
TEX_MAX = 2048 if KEEP_NORMAL else 1024

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS


def norm(n):
    return n.replace("_", ":") if n.startswith("mixamorig_") else n


def load(path):
    before = set(bpy.data.objects); acts = set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    for o in list(new):
        if o.type == "MESH" and o.parent is None:                 # Meshy / Tripo helper meshes
            bpy.data.objects.remove(o, do_unlink=True); new.remove(o)
    arm = next(o for o in new if o.type == "ARMATURE")
    for b in arm.data.bones:                                       # one naming for both rigs
        b.name = norm(b.name)
    return arm, [o for o in new if o.type == "MESH"], [a for a in bpy.data.actions if a not in acts]


src_arm, src_meshes, src_actions = load(SRC)
props = [m for m in src_meshes if m.parent_type == "BONE"]        # the pistol in the right hand
for m in src_meshes:
    if m not in props:
        bpy.data.objects.remove(m, do_unlink=True)
arm, meshes, own = load(IN)
for a in own:                                                      # Meshy's own clips are not used
    bpy.data.actions.remove(a)
body = max(meshes, key=lambda m: len(m.data.vertices))

cfg = json.load(open(SRC_JSON))
wanted = set(cfg.get("clips", {}).values()) | set(cfg.get("aim", {}).get("gun_clips", [])) | ({cfg["aim"]["anim"]} if cfg.get("aim") else set())

# ------------------------------------------------------------------ retarget (same method as meshy_hunger.py)
TB, SB = arm.data.bones, src_arm.data.bones
names = [b.name for b in TB if b.name in SB]
scale = TB[HIPS].head_local.length / max(SB[HIPS].head_local.length, 1e-6)
src_rest = {n: SB[n].matrix_local.to_quaternion() for n in names}
tgt_rest = {n: TB[n].matrix_local.to_quaternion() for n in names}
tgt_rel = {n: (tgt_rest[TB[n].parent.name].inverted() @ tgt_rest[n]) if TB[n].parent else tgt_rest[n] for n in names}
Y = Vector((0, 1, 0))
arm.animation_data_create(); src_arm.animation_data_create()
lengths = {}
for act in src_actions:
    key = act.name[:-4] if act.name[-4:-3] == "." else act.name
    if key not in wanted:
        continue
    src_arm.animation_data.action = act
    f0, f1 = (int(round(v)) for v in act.frame_range)
    new = bpy.data.actions.new("_" + key); new.use_fake_user = True
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
    new.use_frame_range = True
    new.frame_range = (0, f1 - f0)
    lengths[key] = f1 - f0
    print("retargeted", key, f1 - f0, "frames")
missing = sorted(wanted - set(lengths))
if missing:
    print("WARNING: clips not in source:", missing)

# carry the hand props over, same offset from the same bone
for pr in props:
    bone = norm(pr.parent_bone)
    mw = pr.matrix_world.copy()
    src_arm.animation_data.action = None
    for pb in src_arm.pose.bones:
        pb.matrix_basis = Matrix()
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix()
    bpy.context.view_layer.update()
    local = (src_arm.matrix_world @ SB[bone].matrix_local).inverted() @ pr.matrix_world   # offset from the bone at rest
    pr.parent = arm; pr.parent_type = "BONE"; pr.parent_bone = bone
    bpy.context.view_layer.update()
    pr.matrix_world = (arm.matrix_world @ TB[bone].matrix_local) @ local
bpy.data.objects.remove(src_arm, do_unlink=True)
for a in src_actions:
    bpy.data.actions.remove(a)
for a in bpy.data.actions:
    if a.name.startswith("_"):
        a.name = a.name[1:]

# ------------------------------------------------------------------ size: HEIGHT, feet on the ground in the idle pose
zs = [(body.matrix_world @ v.co).z for v in body.data.vertices]
k = HEIGHT / (max(zs) - min(zs))
arm.scale = arm.scale * k
idle = cfg["clips"].get("idle", "idle")
arm.animation_data.action = bpy.data.actions[idle]; sc.frame_set(0); bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
me = body.evaluated_get(dg).to_mesh()
low = min((body.matrix_world @ v.co).z for v in me.vertices)
body.evaluated_get(dg).to_mesh_clear()
arm.location.z -= low
bpy.context.view_layer.update()
print("scale", round(k, 4))

# ------------------------------------------------------------------ materials and export
for m in bpy.data.materials:
    if m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED":
                for name in ("Metallic", "Roughness") + (() if KEEP_NORMAL else ("Normal",)):
                    for l in list(n.inputs[name].links):
                        m.node_tree.links.remove(l)
for img in bpy.data.images:
    if img.users and img.size[0] > TEX_MAX:
        img.scale(TEX_MAX, max(1, img.size[1] * TEX_MAX // img.size[0]))
arm.animation_data.action = None
bpy.ops.export_scene.gltf(filepath=OUT + ".glb", export_format="GLB", export_animations=True,
                          export_animation_mode="ACTIONS", export_force_sampling=True, export_frame_range=False,
                          export_def_bones=False, export_apply=False, use_selection=False,
                          export_image_format="JPEG", export_jpeg_quality=92 if KEEP_NORMAL else 88)
out = dict(cfg)
out.update({"height_m": HEIGHT})
if KEEP_NORMAL:
    out.update({"normal_strength": 1.6, "band_soft": 0.06, "rim": 0.6})
json.dump(out, open(OUT + ".json", "w"), indent=1)
print("exported", OUT, json.dumps(lengths))
