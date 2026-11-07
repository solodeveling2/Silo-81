"""Copy the player's animation clips onto another Tripo/Mixamo-rigged character.

Both rigs use mixamorig:* bone names and the Mixamo bone-axis convention (local Y along the
bone), so each bone's armature-space orientation is copied directly from the source pose.
That matches the pose itself even when the two rest poses differ (A-pose vs T-pose arms).
Hips translation is scaled by the ratio of hip heights.

Usage: python3 -I retarget.py source_with_anims.glb target_rigged.glb out.glb [clip ...]
"""
import sys, math
import bpy
from mathutils import Matrix, Quaternion, Vector

SRC, TGT, OUT = sys.argv[1:4]
WANT = sys.argv[4:] or ["walk", "run", "idle", "hit", "fall"]

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def load(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == "ARMATURE")
    return arm, new


src_arm, src_objs = load(SRC)
src_actions = list(bpy.data.actions)
tgt_arm, tgt_objs = load(TGT)
for a in list(bpy.data.actions):
    if a not in src_actions:
        bpy.data.actions.remove(a)          # any clip Tripo baked into the target
for o in src_objs:
    if o.type == "MESH":
        bpy.data.objects.remove(o, do_unlink=True)


def pick(key):
    for a in src_actions:
        n = a.name.lower()
        if n == key or n.startswith(key):
            return a
    raise KeyError(key)


def rot(m):
    return m.to_quaternion()


TB = tgt_arm.data.bones
SB = src_arm.data.bones
names = [b.name for b in TB if b.name in SB]          # hierarchy order (parents first)
hips = "mixamorig:Hips"
scale = TB[hips].head_local.length / max(SB[hips].head_local.length, 1e-6)
# rest orientation of each target bone relative to its parent's rest
rest_rel = {}
for n in names:
    b = TB[n]
    rest_rel[n] = rot(b.parent.matrix_local).inverted() @ rot(b.matrix_local) if b.parent else rot(b.matrix_local)

tgt_arm.animation_data_create()
src_arm.animation_data_create()
for key in WANT:
    act = pick(key)
    src_arm.animation_data.action = act
    f0, f1 = (int(round(v)) for v in act.frame_range)
    new = bpy.data.actions.new("rt_" + key)
    new.use_fake_user = True
    tgt_arm.animation_data.action = new
    last = {}
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        M = {n: rot(src_arm.pose.bones[n].matrix) for n in names}   # source armature-space orientation
        hips_loc = src_arm.pose.bones[hips].location.copy() * scale
        for n in names:
            pb = tgt_arm.pose.bones[n]
            b = TB[n]
            parent_M = M.get(b.parent.name) if b.parent else Quaternion()
            if b.parent and b.parent.name not in M:
                parent_M = rot(tgt_arm.pose.bones[b.parent.name].matrix)
            local = rest_rel[n].inverted() @ parent_M.inverted() @ M[n]
            prev = last.get(n)
            if prev is not None and prev.dot(local) < 0:
                local.negate()                     # keep quaternions continuous
            last[n] = local
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = local
            pb.keyframe_insert("rotation_quaternion", frame=f, group=n)
            if n == hips:
                pb.location = hips_loc
                pb.keyframe_insert("location", frame=f, group=n)
    print("retargeted", key, "->", new.name, f0, f1)

src_arm.animation_data.action = None
bpy.data.objects.remove(src_arm, do_unlink=True)
for a in src_actions:
    bpy.data.actions.remove(a)
for a in list(bpy.data.actions):
    if a.name.startswith("rt_"):
        a.name = a.name[3:]
tgt_arm.animation_data.action = None
bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_animations=True,
                          export_animation_mode="ACTIONS", export_force_sampling=True)
print("wrote", OUT)
