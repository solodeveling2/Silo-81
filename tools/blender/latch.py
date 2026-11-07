"""Solve the pose of the worm that is latched onto the burst pipe on Level 3.

The worm stands on a hex in front of the pipe gallery; its mouth must sit on the chewed lagging
of the bottom pipe. Writes latch.json (read by worm.py for the chew and release clips) and prints
the direction to give the worm's spawn in the level file.

Usage: python3 -I latch.py
"""
import sys, os, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worm_pose as wp

S, C30, R2 = 0.6396, math.cos(math.radians(30)), 0.70710678

# Level 3 geometry (tools/blender/build.py): the pipes stand 0.24 m off the north wall's inner face
WALL_V = 1.8 - 0.25 / 2
PIPE_V = WALL_V - 0.24
PIPE_Z = 0.45                  # the bottom run: heating flow, general circuit
LAG_R = 0.13                   # lagging radius
HOLE_U = float(os.environ.get("HOLE_U", 8.75))   # the worm worries the left rim of the hole (hole centre u = 8.85)
ONLY_DIR = os.environ.get("DIR", "1")             # lying along the pipe, so its curve and teeth read from the camera
WORM_HEX = (14, -12)           # plan (8.32, 1.08): the walkable hex beside the breach

target_plan = np.array([HOLE_U, PIPE_V - LAG_R + 0.02])      # a little way into the lagging
target_z = PIPE_Z - 0.03


def hex_to_ground(q, r):
    return np.array([S * (q + r * 0.5), -S * C30 * r])


def plan_to_ground(p):
    return np.array([(p[0] - p[1]) * R2, (p[0] + p[1]) * R2])


hg = hex_to_ground(*WORM_HEX)
rel = plan_to_ground(target_plan) - hg
into_pipe = plan_to_ground(np.array([0.0, 1.0])) - plan_to_ground(np.array([0.0, 0.0]))   # plan +v
best = None
for d in range(6):
    a = -math.radians(60 * d)
    rot = lambda v: np.array([v[0] * math.cos(a) - v[1] * math.sin(a), v[0] * math.sin(a) + v[1] * math.cos(a)])
    loc = np.array([*rot(rel), target_z])
    md = np.array([*rot(into_pipe), 0.35])
    if loc[0] < 0.1 or (ONLY_DIR and d != int(ONLY_DIR)):
        continue                                                 # the head must be in front of the worm
    pose, err = wp.solve_latch(loc, md)
    turn = abs(pose["yaw"]) + abs(pose["neck_yaw"])
    score = err * 10 + turn
    print(f"dir {d}: local {loc.round(3)} err {err:.3f} yaw {pose['yaw']:.2f} neck {pose['neck_yaw']:.2f} raise {pose['raise_']:.2f}")
    if best is None or score < best[0]:
        best = (score, d, pose, err, loc)

_, d, pose, err, loc = best
json.dump({"dir": d, "hex": WORM_HEX, "pose": pose, "err_m": round(err, 4), "target_local": [round(x, 4) for x in loc]},
          open(wp.LATCH_FILE, "w"), indent=1)
pl = (hg[0] + hg[1]) * R2, (hg[1] - hg[0]) * R2
print(f"chosen dir {d}, mouth error {err * 100:.1f} cm; spawn the chewer at plan ({pl[0]:.2f}, {pl[1]:.2f}) facing {d}")
