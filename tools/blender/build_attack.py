"""Build one 'pistol_attack' clip on the target rig: idle -> raise to aim -> shoot -> hold -> lower.
Blends are per-bone quaternion slerps between sampled poses, so it stays smooth.

Usage: python3 build_attack.py in.glb out.glb
"""
import sys
import bpy

IN, OUT = sys.argv[1], sys.argv[2]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=IN)
for o in list(bpy.data.objects):
    if o.type == "MESH" and o.parent is None:
        bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
bones = list(arm.pose.bones)
for pb in bones:
    pb.rotation_mode = "QUATERNION"

def sample(action, frame):
    arm.animation_data.action = bpy.data.actions[action]
    sc.frame_set(int(frame)); bpy.context.view_layer.update()
    return {pb.name: (pb.rotation_quaternion.copy(), pb.location.copy()) for pb in bones}

idle = sample("idle", 0)
aim = sample("pistol_aim", 0)
shoot_act = bpy.data.actions["pistol_shoot"]
n_shoot = int(round(shoot_act.frame_range[1])) + 1
shoot = [sample("pistol_shoot", f) for f in range(n_shoot)]

def smooth(t):                       # ease in/out
    return t * t * (3 - 2 * t)

seq = []
RAISE, HOLD, LOWER = 7, 4, 8
for i in range(RAISE):
    seq.append(("blend", idle, aim, smooth((i + 1) / RAISE)))
seq.append(("blend", aim, shoot[0], 1.0))
for p in shoot:
    seq.append(("pose", p))
for _ in range(HOLD):
    seq.append(("pose", shoot[-1]))
for i in range(LOWER):
    seq.append(("blend", shoot[-1], idle, smooth((i + 1) / LOWER)))

out = bpy.data.actions.new("pistol_attack")
arm.animation_data.action = out
for f, step in enumerate(seq):
    for pb in bones:
        if step[0] == "pose":
            q, l = step[1][pb.name]
        else:
            _, a, b, t = step
            q = a[pb.name][0].slerp(b[pb.name][0], t)
            l = a[pb.name][1].lerp(b[pb.name][1], t)
        pb.rotation_quaternion = q
        pb.location = l
        pb.keyframe_insert("rotation_quaternion", frame=f)
        pb.keyframe_insert("location", frame=f)
print("pistol_attack frames", len(seq), "- shot fires on frame", RAISE + 1)
for a in bpy.data.actions:
    a.use_fake_user = True
bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_animations=True,
                          export_animation_mode="ACTIONS", export_force_sampling=True)
print("saved", [a.name for a in bpy.data.actions])
