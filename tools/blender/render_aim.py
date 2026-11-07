"""Render the combat shot at several vertical aim angles, so the gun points at the target:
down at a worm on the floor, up at something taller than you.

The clip 'pistol_fire' starts and ends in the combat stance (pistol_idle), swings onto the
target, fires (pistol_shoot) and settles back. For each aim pitch the upper body is bent
about the character's own left-right axis: part in the spine (so the shoulders lean into the
shot), the rest at both shoulders (the two-handed grip stays together), and the head follows.
The muzzle is measured on the firing frame, so the game can start the tracer at the gun.

Usage: python3 -I render_aim.py model.glb out_dir         (env PITCHES, DIRS, PICK for tests)
"""
import sys, os, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
MODEL, OUT = sys.argv[1], sys.argv[2]
sys.argv = [os.path.join(HERE, "render_character.py"), MODEL, OUT]
sys.path.insert(0, HERE)
import render_character as rc                      # scene, toon materials, pistol prop, camera
import bpy
from mathutils import Vector, Matrix

PITCHES = [int(p) for p in os.environ.get("PITCHES", "-60,-40,-20,0,20,40").split(",")]
DIRS = [int(d) for d in os.environ.get("DIRS", "0,1,2,3,4,5").split(",")]
PICK = [int(i) for i in os.environ["PICK"].split(",")] if os.environ.get("PICK") else None
# share of the pitch taken by each bone, applied in this order (parents first)
SHARES = [("mixamorig:Spine", 0.12), ("mixamorig:Spine1", 0.12), ("mixamorig:Spine2", 0.12),
          ("mixamorig:Neck", 0.3), ("mixamorig:LeftArm", 0.64), ("mixamorig:RightArm", 0.64)]
RAISE, HOLD, LOWER = 4, 2, 6
MUZZLE_LOCAL = Vector((0.155, 0.0, 0.04))          # end of the barrel in the pistol prop's frame

arm, P, sc = rc.arm, rc.P, rc.sc
bones = list(P)
for pb in bones:
    pb.rotation_mode = "QUATERNION"


def sample(action, frame):
    arm.animation_data.action = rc.act_for(action)
    sc.frame_set(int(frame)); bpy.context.view_layer.update()
    return {pb.name: (pb.rotation_quaternion.copy(), pb.location.copy()) for pb in bones}


def smooth(t):
    return t * t * (3 - 2 * t)


stance = sample("pistol_idle", int(rc.act_for("pistol_idle").frame_range[0]))
sa = rc.act_for("pistol_shoot")
shoot = [sample("pistol_shoot", f) for f in range(int(sa.frame_range[0]), int(round(sa.frame_range[1])) + 1)]
arm.animation_data.action = None                    # from here on the pose is set by hand

seq = []                                            # (pose a, pose b, blend, aim weight)
for i in range(RAISE):
    t = smooth((i + 1) / RAISE)
    seq.append((stance, shoot[0], t, t))
ACTION_FRAME = len(seq) - 1                         # first frame fully on target: the shot
for p in shoot[1:]:
    seq.append((p, p, 0.0, 1.0))
for _ in range(HOLD):
    seq.append((shoot[-1], shoot[-1], 0.0, 1.0))
for i in range(LOWER):
    t = smooth((i + 1) / LOWER)
    seq.append((shoot[-1], stance, t, 1.0 - t))
N = len(seq)


BASE = 0.0


def set_pose(step, pitch_deg, facing):
    a, b, t, w = step
    for pb in bones:
        qa, la = a[pb.name]; qb, lb = b[pb.name]
        pb.rotation_quaternion = qa.slerp(qb, t)
        pb.location = la.lerp(lb, t)
    bpy.context.view_layer.update()
    theta = math.radians(pitch_deg - BASE) * w
    if abs(theta) < 1e-6:
        return
    axis = facing.cross(Vector((0, 0, 1))).normalized()          # positive angle tilts the aim up
    A = arm.matrix_world.to_3x3().normalized()
    Ai = A.inverted()
    for name, share in SHARES:
        pb = P[name]
        R = (Ai @ Matrix.Rotation(theta * share, 3, axis) @ A).to_4x4()
        h = pb.head.copy()
        pb.matrix = Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ pb.matrix
        bpy.context.view_layer.update()


def tag(p):
    return "0" if p == 0 else ("m%d" % -p if p < 0 else "p%d" % p)


def barrel_pitch():
    b = (rc.gun.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()
    return math.degrees(math.asin(max(-1.0, min(1.0, b.z))))


# the shoot pose already tips the barrel a little; aim pitches are measured from level
rc.rig.rotation_euler = (0, 0, math.radians(90)); arm.location = rc.arm_base_loc
set_pose(seq[ACTION_FRAME], 0, Vector((1, 0, 0)))
BASE = barrel_pitch()
print("barrel pitch of the plain shot", round(BASE, 2))

steps_path = os.path.join(OUT, "steps.json")
summary = json.load(open(steps_path)) if os.path.exists(steps_path) else {"animations": {}}
canvas = 384
sc.render.resolution_x = sc.render.resolution_y = canvas
rc.cam.data.ortho_scale = canvas / rc.PPM
rc.gun.hide_render = False
frames = PICK if PICK is not None else list(range(N))
for pitch in PITCHES:
    key = "pistol_fire_" + tag(pitch)
    out_dir = os.path.join(OUT, key); os.makedirs(out_dir, exist_ok=True)
    meta = {"fps": 24, "frames": N, "loop": False, "canvas": canvas, "action_frame": ACTION_FRAME,
            "pitch_deg": pitch, "anchor_px": [round(v, 1) for v in rc.screen_xy(Vector((0, 0, 0)), canvas)],
            "directions": {}}
    for d in DIRS:
        ang = 60 * d
        rc.rig.rotation_euler = (0, 0, math.radians(ang + 90))      # the source faces -Y
        arm.location = rc.arm_base_loc
        facing = Vector((math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0))
        entry = {"angle_deg": ang, "step_px": [0.0, 0.0]}
        for i in frames:
            set_pose(seq[i], pitch, facing)
            if i == ACTION_FRAME:
                m = rc.gun.matrix_world @ MUZZLE_LOCAL
                entry["muzzle_px"] = [round(v, 1) for v in rc.screen_xy(m, canvas)]
                entry["muzzle_m"] = [round(m.dot(facing), 3), round(m.z, 3)]           # forward, height
                entry["barrel_pitch_deg"] = round(barrel_pitch(), 1)
            sc.render.filepath = os.path.join(out_dir, f"dir{d}_{i:03d}.png")
            bpy.ops.render.render(write_still=True)
        meta["directions"][str(d)] = entry
        print(key, "dir", d, {k: v for k, v in entry.items() if k != "step_px"}, flush=True)
    summary.setdefault("animations", {})[key] = meta
    json.dump(summary, open(steps_path, "w"), indent=2)
print("pistol_fire frames", N, "shot on frame", ACTION_FRAME)
