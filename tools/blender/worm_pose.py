"""Pose maths for the pipe worm (numpy only, no Blender), shared by worm.py and the latch solver.

The body is a spine of NS points from tail to head. Pose parameters bend it sideways (lat_*),
rear the front third up (raise_), tip the head (head_pitch), open the mouth and curl it up.
Frame: x forward, y left, z up; the rest pose's middle sits on the origin and the tail stays put.
"""
import math, json, os
import numpy as np

PPM = 165.0
L = 1.25                       # body length, metres
R_MAX = 0.085                 # body radius
HEX = 28 * 7.538 / PPM        # 1.279 m: one player walk half-clip (two hexes of 0.64 m)
NS = 120

def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)

S = np.linspace(0, 1, NS)

def radius(s):
    r = 0.22 + 0.78 * smooth(0.0, 0.28, s)
    r = r * (1 - 0.1 * smooth(0.78, 0.86, s) * (1 - smooth(0.9, 0.96, s)))   # slight neck
    r = r * (1 + 0.12 * smooth(0.9, 0.97, s))                                   # head bulb
    ridge = np.maximum(0, np.cos(2 * np.pi * s * L / 0.055)) ** 6
    return R_MAX * r * (1 + 0.07 * ridge), ridge

RAD, RIDGE = radius(S)


def spine(p):
    """p: pose parameters. Returns positions (NS,3) with the tail at the origin."""
    lat = p["lat_amp"] * np.cos(2 * np.pi * (p["lat_cycles"] * S + p["lat_phase"]))
    if p.get("crawl"):
        k = 2 * np.pi / (HEX / 2)                          # two waves per hex
        lat = p["lat_amp"] * np.cos(k * (S * L + p["crawl_d"]))
    lat = lat * (1 - 0.55 * smooth(0.75, 1.0, S))        # the head stays steadier
    lat = lat + p.get("curl", 0.0) * (S - 0.5) * 2.0
    lat = lat + p.get("yaw", 0.0) + p.get("neck_yaw", 0.0) * smooth(0.6, 0.95, S)
    raise_ = p["raise"] * smooth(p.get("rs0", 0.5), p.get("rs1", 0.68), S) * (1 - smooth(0.8, 0.93, S))
    pitch = raise_ + p["head_pitch"] * smooth(0.86, 1.0, S)
    ds = L / (NS - 1)
    d = np.stack([np.cos(pitch) * np.cos(lat), np.cos(pitch) * np.sin(lat), np.sin(pitch)], 1)
    pos = np.zeros((NS, 3))
    pos[1:] = np.cumsum(d[:-1] * ds, 0)
    return pos


REST = dict(lat_amp=0.32, lat_cycles=1.0, lat_phase=0.1, raise_=0, raise_v=1.2, head_pitch=-0.5, mouth=0.15, curl=0.0)
KEYS = ("lat_amp", "lat_phase", "raise_", "head_pitch", "yaw", "neck_yaw", "rs0", "rs1")


def rest_params():
    return dict(lat_amp=REST["lat_amp"], lat_cycles=REST["lat_cycles"], lat_phase=REST["lat_phase"],
                raise_=REST["raise_v"], head_pitch=REST["head_pitch"], mouth=REST["mouth"], curl=0.0,
                yaw=0.0, neck_yaw=0.0, rs0=0.5, rs1=0.68)


def spine_from(p):
    q = {"lat_amp": p["lat_amp"], "lat_cycles": p["lat_cycles"], "lat_phase": p["lat_phase"],
         "raise": p["raise_"], "head_pitch": p["head_pitch"], "curl": p.get("curl", 0.0),
         "crawl": p.get("crawl", False), "crawl_d": p.get("crawl_d", 0.0),
         "yaw": p.get("yaw", 0.0), "neck_yaw": p.get("neck_yaw", 0.0),
         "rs0": p.get("rs0", 0.5), "rs1": p.get("rs1", 0.68)}
    pos = spine(q)
    pos[:, 2] += RAD                                           # rest on the ground
    return pos


_rest = spine_from(rest_params())
TAIL0 = -np.array([_rest[NS // 2][0], _rest[NS // 2][1], 0.0])


def body_pos(p):
    """Spine in the actor frame: the tail stays where the rest pose puts it."""
    return spine_from(p) + TAIL0


# ---------------------------------------------------------------- latching onto a pipe
LATCH_FILE = os.environ.get("WORM_LATCH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "latch.json")


def solve_latch(target, mouth_dir=(1.0, 0.0, 0.25)):
    """Find a pose whose mouth sits at target (actor frame, metres) facing roughly mouth_dir.
    The tail stays put, so the worm reaches by rearing, straightening and turning its neck."""
    from scipy.optimize import minimize
    target = np.asarray(target, float)
    md = np.asarray(mouth_dir, float); md /= np.linalg.norm(md)
    base = rest_params()

    def pose(x):
        p = dict(base)
        p.update(raise_=x[0], head_pitch=x[1], lat_amp=x[2], lat_phase=x[3], yaw=x[4], neck_yaw=x[5], rs0=x[6], rs1=x[6] + 0.2)
        return p

    def cost(x):
        pos = body_pos(pose(x))
        head = pos[-1]
        t = pos[-1] - pos[-4]; t /= np.linalg.norm(t)
        c = 40 * np.sum((head - target) ** 2) + 0.4 * (1 - np.dot(t, md))
        c += 0.05 * x[4] ** 2 + 0.1 * x[5] ** 2                              # stay close to the rest pose
        c += 0.4 * (x[2] - REST["lat_amp"]) ** 2 + 0.5 * (x[6] - 0.5) ** 2
        c += 2.0 * max(0.0, x[0] - 1.45) ** 2 + 2.0 * max(0.0, 0.3 - x[6]) ** 2 + 2.0 * max(0.0, x[6] - 0.62) ** 2
        return c

    x0 = np.array([1.2, 0.1, 0.25, 0.1, 0.0, 0.0, 0.5])
    best = None
    for yaw0 in (-0.4, 0.0, 0.4):
        for r0 in (0.9, 1.2):
            x0[4] = yaw0; x0[0] = r0
            res = minimize(cost, x0, method="Nelder-Mead", options=dict(maxiter=6000, xatol=1e-5, fatol=1e-8))
            if best is None or res.fun < best.fun:
                best = res
    p = pose(best.x)
    err = float(np.linalg.norm(body_pos(p)[-1] - target))
    return {k: float(p[k]) for k in KEYS}, err


def lerp_pose(a, b, t):
    out = dict(a)
    for k in KEYS:
        out[k] = a[k] + (b[k] - a[k]) * t
    return out
