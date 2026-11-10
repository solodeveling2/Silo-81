"""Export a rigged NPC (Mixamo rig, Tripo model) for live 3D in the game, matching its sprite renders:
the same 1.75 m scale render_character.py uses (rest mesh height), feet at z=0, every action kept.
Writes OUT.glb and OUT.json (clip map and idle loop) for game/scripts/puppet3d.gd.

Usage: blender -b --python-exit-code 1 -P export_live_npc.py -- model.glb OUT_BASENAME [height_m]
   or: python3 -I export_live_npc.py model.glb OUT_BASENAME [height_m]   (bpy module)
"""
import sys, os, json
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
MODEL, OUT = argv[0], argv[1]
HEIGHT_M = float(argv[2]) if len(argv) > 2 else 1.75
EXPOSURE = float(argv[3]) if len(argv) > 3 else 1.35
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=MODEL)
for o in list(bpy.data.objects):
    if o.type == "MESH" and o.parent is None:
        bpy.data.objects.remove(o, do_unlink=True)          # stray helper meshes (as render_character.py)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
body = next(o for o in bpy.data.objects if o.type == "MESH")


def act(key):
    if key in bpy.data.actions:
        return bpy.data.actions[key]
    return next(a for a in bpy.data.actions if a.name.lower().startswith(key))


clips = {}
for key in ("walk", "run", "idle", "hit", "death", "fall"):
    try:
        clips[key] = act(key).name
    except StopIteration:
        pass

# ---- the loop point render_character.py picks for idle (cleanest return to frame 0 in 48..200)
P = arm.pose.bones
arm.animation_data.action = act("idle")
f0, f1 = int(act("idle").frame_range[0]), int(act("idle").frame_range[1])


def pose_vec():
    bpy.context.view_layer.update()
    return [arm.matrix_world @ b.head for b in P]


sc.frame_set(f0); ref = pose_vec()
best = None
for f in range(f0 + 48, min(f1, f0 + 200) + 1):
    sc.frame_set(f)
    d = sum((a - b).length for a, b in zip(pose_vec(), ref))
    if best is None or d < best[0]:
        best = (d, f)
idle_loop = [0, best[1] - f0]

# ---- scale like the sprite renders (rest mesh height at idle frame 0), feet on the ground
sc.frame_set(f0); bpy.context.view_layer.update()
zs = [(body.matrix_world @ v.co).z for v in body.data.vertices]
s_ = HEIGHT_M / (max(zs) - min(zs))
arm.scale = arm.scale * s_
arm.location = arm.location - Vector((0, 0, min(zs) * s_))
bpy.context.view_layer.update()

def slim_materials(max_px=1024):
    """The game's toon shader reads only base colour: drop normal / metal / roughness maps and
    cap the colour texture, so the web download carries nothing unused."""
    for m in bpy.data.materials:
        if not m.use_nodes:
            continue
        nt = m.node_tree
        for n in list(nt.nodes):
            if n.type == "BSDF_PRINCIPLED":
                for name in ("Normal", "Metallic", "Roughness"):
                    for l in list(n.inputs[name].links):
                        nt.links.remove(l)
    for img in bpy.data.images:
        if img.users and img.size[0] > max_px:
            img.scale(max_px, max(1, img.size[1] * max_px // img.size[0]))


slim_materials()
for a in bpy.data.actions:
    a.use_fake_user = True
try:
    bpy.ops.export_scene.gltf(filepath=OUT + ".glb", export_format="GLB", export_animations=True,
                              export_animation_mode="ACTIONS", export_force_sampling=True, export_frame_range=False,
                              export_def_bones=False, export_apply=False, use_selection=False)
except TypeError:
    bpy.ops.export_scene.gltf(filepath=OUT + ".glb", export_format="GLB", export_animations=True,
                              export_nla_strips=True, export_force_sampling=True, export_frame_range=False,
                              export_def_bones=False, export_apply=False, use_selection=False)
    clips = {k: k for k in clips}
json.dump({"fps_src": 24, "clips": clips, "idle_loop_src": idle_loop, "height_m": HEIGHT_M, "exposure": EXPOSURE},
          open(OUT + ".json", "w"), indent=1)
print("exported", OUT, "scale", round(s_, 4), "clips", clips, "idle loop", idle_loop)
