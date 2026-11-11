"""The Changed (docs/LEVEL_ROAD_TO_JUNK_TOWN.md §7) for live 3D: once ordinary people, now wrong.

Built from the civilian Tripo body (Tibor's mesh and Mixamo rig) so it shares the game's proportions,
then made strange in the game itself (game/characters/changed_3d/changed.json):
  - duotone recolour in the toon shader: pale, mottled skin over a dark coat in one of three colours
    (brown parka, blue ski jacket, grey work coat), chosen per instance;
  - posture offsets on the bones after every pose (head tilted, one shoulder dropped, spine hunched);
  - clips: idle (from the rig), walk (played slow: a shamble), hit, death (the player's fall, retargeted
    by bone name), and "claw", a lunge made here bone by bone.

Usage: python3 -I export_changed.py BODY.glb DEATH_SOURCE.glb OUT_BASENAME
"""
import sys, json, math
import bpy
from mathutils import Vector, Matrix, Quaternion

BODY, DEATH_SRC, OUT = sys.argv[1:4]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 24

bpy.ops.import_scene.gltf(filepath=BODY)
for o in list(bpy.data.objects):
    if o.type == "MESH" and o.parent is None:
        bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
body = next(o for o in bpy.data.objects if o.type == "MESH")
own_actions = set(bpy.data.actions)

def _fcurves(a):
    """(container, fcurve) pairs for legacy and layered (Blender 4.4+) actions."""
    if hasattr(a, "fcurves"):
        return [(a, fc) for fc in list(a.fcurves)]
    out = []
    for layer in a.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                out += [(bag, fc) for fc in list(bag.fcurves)]
    return out


# ---- the death clip from the player's set (same Mixamo bone names)
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=DEATH_SRC)
death = next((a for a in bpy.data.actions if a not in own_actions and a.name.startswith("death")), None)
for o in [o for o in bpy.data.objects if o not in before]:
    bpy.data.objects.remove(o, do_unlink=True)
for a in [a for a in bpy.data.actions if a not in own_actions and a is not death]:
    bpy.data.actions.remove(a)
if death:
    death.name = "death"
    # keep only rotations: the player's rig is a different size, its hip translation would float or sink
    for bag, fc in _fcurves(death):
        if fc.data_path.endswith("location") and "Hips" not in fc.data_path:
            bag.fcurves.remove(fc)


def act(key):
    if key in bpy.data.actions:
        return bpy.data.actions[key]
    return next(a for a in bpy.data.actions if a.name.lower().startswith(key))


P = arm.pose.bones
for pb in P:
    pb.rotation_mode = "QUATERNION"

# ---- claw: rear back, lunge and rake with both hands, recover (22 frames at 24 fps)
idle = act("idle")
claw = bpy.data.actions.new("claw")
arm.animation_data.action = idle
sc.frame_set(int(idle.frame_range[0]))
bpy.context.view_layer.update()
rest = {pb.name: (pb.rotation_quaternion.copy(), pb.location.copy()) for pb in P}
arm.animation_data.action = claw

W = arm.matrix_world
FWD = (W.to_3x3() @ Vector((0, -1, 0))).normalized()          # the rig faces -Y
SIDE = (W.to_3x3() @ Vector((1, 0, 0))).normalized()


def bone(n):
    for k in (n, "mixamorig:" + n, "mixamorig_" + n):
        if k in P:
            return P[k]
    return None


def turn(pb, axis_world, deg):
    """Rotate a pose bone about a world axis through its head, on top of its current pose."""
    if pb is None:
        return
    bpy.context.view_layer.update()
    Wb = W @ pb.matrix
    piv = Wb.translation.copy()
    R = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(deg), 4, axis_world) @ Matrix.Translation(-piv)
    pb.matrix = W.inverted() @ (R @ Wb)


def pose(f, spine, arms, hips_fwd, head=0.0, spread=0.0):
    """spine > 0 leans forward (degrees over three bones), arms > 0 lifts them forward."""
    for pb in P:
        pb.rotation_quaternion, pb.location = rest[pb.name][0].copy(), rest[pb.name][1].copy()
    bpy.context.view_layer.update()
    lean = SIDE                                               # rotating about +side tips the top forward
    for n in ("Spine", "Spine1", "Spine2"):
        turn(bone(n), lean, spine / 3)
    turn(bone("Head"), lean, head)
    for side, sgn in (("Left", 1), ("Right", -1)):
        turn(bone(side + "Arm"), lean, -arms)
        turn(bone(side + "Arm"), FWD, sgn * spread)
        turn(bone(side + "ForeArm"), lean, -arms * 0.35)
    for pb in P:
        pb.keyframe_insert("rotation_quaternion", frame=f)
        pb.keyframe_insert("location", frame=f)


pose(0, 0, 0, 0.0)
pose(6, -14, 55, -0.04, head=-8, spread=10)                    # rears back, hands up
pose(10, 30, 95, 0.10, head=12, spread=4)                      # lunges, hands high
pose(13, 42, 35, 0.16, head=16, spread=-6)                     # rakes down: the hit lands here
pose(17, 26, 10, 0.08, head=8)
pose(22, 0, 0, 0.0)
CLAW_FRAMES, CLAW_HIT = 22, 13

# ---- the same scale as the sprite renders (1.75 m, feet on the ground)
arm.animation_data.action = idle
sc.frame_set(int(idle.frame_range[0])); bpy.context.view_layer.update()
zs = [(body.matrix_world @ v.co).z for v in body.data.vertices]
s_ = 1.72 / (max(zs) - min(zs))
arm.scale = arm.scale * s_
arm.location = arm.location - Vector((0, 0, min(zs) * s_))
bpy.context.view_layer.update()

for m in bpy.data.materials:                                   # base colour only: the toon shader reads nothing else
    if not m.use_nodes:
        continue
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            for k in ("Normal", "Metallic", "Roughness"):
                for l in list(n.inputs[k].links):
                    m.node_tree.links.remove(l)
for im in bpy.data.images:
    if im.users and im.size[0] > 1024:
        im.scale(1024, 1024 * im.size[1] // im.size[0])
for a in bpy.data.actions:
    a.use_fake_user = True
bpy.ops.export_scene.gltf(filepath=OUT + ".glb", export_format="GLB", export_animations=True,
                          export_animation_mode="ACTIONS", export_force_sampling=True, export_frame_range=False,
                          export_def_bones=False, export_apply=False, use_selection=False)
lens = {a.name: int(a.frame_range[1] - a.frame_range[0]) for a in bpy.data.actions}
json.dump({
    "fps_src": 24,
    "clips": {"idle": "idle", "walk": "walk", "hit": "hit", "death": "death" if death else "fall", "bite": "claw"},
    "idle_loop_src": [0, 48],
    "height_m": 1.72,
    "exposure": 1.25,
    # head lolls to one side, one shoulder hangs low, the back is bent: degrees about the bone's own axes
    "pose_offsets": [["mixamorig_Head", 18, 8, 40], ["mixamorig_Neck", 22, 0, 12], ["mixamorig_Spine2", 16, 0, -8],
                     ["mixamorig_Spine1", 22, 0, -8], ["mixamorig_LeftShoulder", 0, 0, -26], ["mixamorig_LeftArm", 0, 0, -10],
                     ["mixamorig_RightArm", 8, 0, 14]],
    # fingers too long: forearms and hands stretched along the bone
    "pose_scales": [["mixamorig_LeftForeArm", 1.0, 1.18, 1.0], ["mixamorig_RightForeArm", 1.0, 1.18, 1.0],
                    ["mixamorig_LeftHand", 0.95, 1.4, 0.95], ["mixamorig_RightHand", 0.95, 1.4, 0.95]],
    "lengths": lens, "claw": {"frames": CLAW_FRAMES, "hit": CLAW_HIT},
}, open(OUT + ".json", "w"), indent=1)
print("exported", OUT, lens)
