"""Retarget Quaternius Universal Animation Library clips (Rigify-style DEF- bones) onto a
Mixamo-standard rig (Tripo export), then save a new .glb with the extra actions added.

Method: both rigs are matched in their T-pose (UAL's 'A_TPose' clip, the Tripo rest pose).
For every frame, each source bone's world rotation relative to its T-pose is applied to the
matching target bone's T-pose world rotation; hips movement is scaled by the hip-height ratio.

Usage: python3 retarget.py target.glb ual.glb out.glb Clip=NewName [Clip=NewName ...]
"""
import sys
import bpy
from mathutils import Matrix

TARGET, SOURCE, OUT = sys.argv[1:4]
CLIPS = dict(a.split("=") for a in sys.argv[4:])

side_map = {
    "shoulder": "Shoulder", "upper_arm": "Arm", "forearm": "ForeArm", "hand": "Hand",
    "thigh": "UpLeg", "shin": "Leg", "foot": "Foot", "toe": "ToeBase",
}
fingers = {"thumb": "Thumb", "f_index": "Index", "f_middle": "Middle", "f_ring": "Ring", "f_pinky": "Pinky"}
BONES = {
    "DEF-hips": "Hips", "DEF-spine.001": "Spine", "DEF-spine.002": "Spine1", "DEF-spine.003": "Spine2",
    "DEF-neck": "Neck", "DEF-head": "Head",
}
for s, (L, R) in {"L": ("Left", "Left"), "R": ("Right", "Right")}.items():
    side = "Left" if s == "L" else "Right"
    for src, dst in side_map.items():
        BONES[f"DEF-{src}.{s}"] = f"{side}{dst}"
    for src, dst in fingers.items():
        for i in (1, 2, 3):
            BONES[f"DEF-{src}.0{i}.{s}"] = f"{side}Hand{dst}{i}"

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=TARGET)
tgt = next(o for o in bpy.data.objects if o.type == "ARMATURE")
tgt.name = "TargetRig"
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=SOURCE)
new = [o for o in bpy.data.objects if o not in before]
src = next(o for o in new if o.type == "ARMATURE")
for o in new:
    if o.type == "MESH":
        bpy.data.objects.remove(o, do_unlink=True)
for o in list(bpy.data.objects):
    if o.type == "MESH" and o.parent is None:
        bpy.data.objects.remove(o, do_unlink=True)

pairs = [(s, "mixamorig:" + t) for s, t in BONES.items()
         if s in src.pose.bones and ("mixamorig:" + t) in tgt.pose.bones]
print("mapped bones", len(pairs))

def world_rot(arm, name):
    return (arm.matrix_world @ arm.pose.bones[name].matrix).to_quaternion()

# T-pose references
src.animation_data.action = bpy.data.actions["A_TPose"]
tgt_action_backup = tgt.animation_data.action if tgt.animation_data else None
if tgt.animation_data:
    tgt.animation_data.action = None
for pb in tgt.pose.bones:
    pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
sc.frame_set(0); bpy.context.view_layer.update()
src_ref = {s: world_rot(src, s) for s, _ in pairs}
tgt_ref = {t: world_rot(tgt, t) for _, t in pairs}
src_hips0 = src.matrix_world @ src.pose.bones["DEF-hips"].head
tgt_hips0 = tgt.matrix_world @ tgt.pose.bones["mixamorig:Hips"].head
ratio = tgt_hips0.z / src_hips0.z
print("hip height ratio", round(ratio, 3))

# depth-ordered target bones so parents are posed before children
def depth(pb):
    d = 0
    while pb.parent:
        d += 1; pb = pb.parent
    return d
ordered = sorted(pairs, key=lambda p: depth(tgt.pose.bones[p[1]]))
tw_inv = tgt.matrix_world.inverted()

for clip, newname in CLIPS.items():
    act = bpy.data.actions[clip]
    src.animation_data.action = act
    f0, f1 = int(act.frame_range[0]), int(round(act.frame_range[1]))
    out = bpy.data.actions.new(newname)
    tgt.animation_data_create(); tgt.animation_data.action = out
    for f in range(f0, f1 + 1):
        sc.frame_set(f); bpy.context.view_layer.update()
        rots = {t: (world_rot(src, s) @ src_ref[s].inverted() @ tgt_ref[t]) for s, t in pairs}
        hips_now = src.matrix_world @ src.pose.bones["DEF-hips"].head
        hips_tgt = tgt_hips0 + (hips_now - src_hips0) * ratio
        level = None
        for s, t in ordered:
            pb = tgt.pose.bones[t]
            d = depth(pb)
            if level is not None and d != level:
                bpy.context.view_layer.update()
            level = d
            loc = (tw_inv @ hips_tgt) if t == "mixamorig:Hips" else (tw_inv @ (tgt.matrix_world @ pb.head))
            m = Matrix.Translation(loc) @ (tw_inv.to_quaternion() @ rots[t]).to_matrix().to_4x4()
            pb.matrix = m
        bpy.context.view_layer.update()
        for s, t in pairs:
            pb = tgt.pose.bones[t]
            pb.keyframe_insert("rotation_quaternion", frame=f - f0)
            if t == "mixamorig:Hips":
                pb.keyframe_insert("location", frame=f - f0)
    print("retargeted", clip, "->", newname, f1 - f0 + 1, "frames")

# keep only the target rig + its mesh, then export everything (old and new actions)
bpy.data.objects.remove(src, do_unlink=True)
if tgt_action_backup:
    tgt.animation_data.action = tgt_action_backup
for a in list(bpy.data.actions):
    if a.users == 0 and a.name not in CLIPS.values() and not a.name.startswith(("walk", "run", "idle", "fall", "hit", "A soldier")):
        bpy.data.actions.remove(a)
for a in bpy.data.actions:
    a.use_fake_user = True
bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_animations=True,
                          export_animation_mode="ACTIONS", export_force_sampling=True)
print("saved", OUT, [a.name for a in bpy.data.actions])
