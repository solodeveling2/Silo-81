"""Feral Form (Tier 1, Firn Strata): a starved human-animal crawler on all fours with ice crystals
growing out of its spine, a long snapping jaw and clawed hands. Built and animated in code
(creature_kit.py), exported for live 3D (game/characters/feral_3d).

Clips (24 fps, in place, feet planted): idle (sniffing, breathing, jaw chatter), walk (a fast scuttle),
bite (crouch, lunge, snap; hit on BITE_HIT), hit (recoil), death (collapses onto its side).

Usage: python3 -I feral.py OUT_BASENAME [--preview DIR]
"""
import sys, os, math, random, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector, Matrix, noise
import creature_kit as K

OUT = sys.argv[1]
PREVIEW = sys.argv[sys.argv.index("--preview") + 1] if "--preview" in sys.argv else None
rng = random.Random(81)
sc = K.reset()

SIDES = (("L", 1), ("R", -1))
# ------------------------------------------------------------------ rig (faces -Y, Z up, metres)
UP, FWD, BACK = (0, 0, 1), (0, -1, 0), (0, 1, 0)
bones = [
    ("pelvis", (0, 0.36, 0.50), (0, 0.16, 0.52), None, UP),
    ("spine", (0, 0.16, 0.52), (0, -0.10, 0.56), "pelvis", UP),
    ("chest", (0, -0.10, 0.56), (0, -0.32, 0.58), "spine", UP),
    ("neck", (0, -0.32, 0.58), (0, -0.47, 0.57), "chest", UP),
    ("head", (0, -0.47, 0.57), (0, -0.80, 0.53), "neck", UP),
    ("jaw", (0, -0.49, 0.49), (0, -0.77, 0.445), "head", UP),
]
for s, x in SIDES:
    bones += [
        (f"thigh_{s}", (x * 0.12, 0.38, 0.47), (x * 0.18, 0.12, 0.24), "pelvis", FWD),
        (f"shin_{s}", (x * 0.18, 0.12, 0.24), (x * 0.16, 0.44, 0.13), f"thigh_{s}", FWD),
        (f"foot_{s}", (x * 0.16, 0.44, 0.13), (x * 0.16, 0.36, 0.015), f"shin_{s}", FWD),
        (f"upperarm_{s}", (x * 0.15, -0.28, 0.54), (x * 0.24, -0.16, 0.30), "chest", (x * 0.4, 1, 0)),
        (f"forearm_{s}", (x * 0.24, -0.16, 0.30), (x * 0.22, -0.42, 0.07), f"upperarm_{s}", (x * 0.4, 1, 0)),
        (f"hand_{s}", (x * 0.22, -0.42, 0.07), (x * 0.22, -0.56, 0.015), f"forearm_{s}", UP),
    ]
rig = K.Rig("FeralRig", bones)
BODY_BONES = [b[0] for b in bones if b[0] != "jaw"]

# ------------------------------------------------------------------ materials (painted, then baked)
SKIN, ICE, BONE, MOUTH, EYE = range(5)
MOUTH_PT, HANDS = (0, -0.74, 0.47), [(x * 0.22, -0.52, 0.03) for _, x in SIDES]
mats = [
    K.paint_material("FeralSkin", (0.60, 0.50, 0.48), (0.36, 0.27, 0.27), accent=(0.30, 0.09, 0.08), noise_scale=7.0, contrast=0.7,
                     accent_mask=K.mask_noise(4.0, -0.14, K.mask_near([MOUTH_PT, (0, -0.62, 0.47)], 0.17, noise_amt=0.6, noise_scale=13.0))),
    K.paint_material("FeralIce", (0.78, 0.87, 0.92), (0.48, 0.62, 0.72), noise_scale=14.0, contrast=0.8),
    K.paint_material("FeralBone", (0.80, 0.73, 0.58), (0.50, 0.42, 0.33), accent=(0.40, 0.10, 0.08), noise_scale=20.0,
                     accent_mask=K.mask_near([MOUTH_PT] + HANDS, 0.08, noise_amt=0.4)),
    K.paint_material("FeralMouth", (0.34, 0.08, 0.08), (0.15, 0.03, 0.04), noise_scale=12.0),
    K.paint_material("FeralEye", (0.82, 0.80, 0.64), (0.62, 0.58, 0.44), noise_scale=30.0),
]

# ------------------------------------------------------------------ body: one skin graph (spine, legs, arms)
nodes = [((0, 0.36, 0.50), 0.115), ((0, 0.49, 0.47), 0.06), ((0, 0.14, 0.50), 0.08), ((0, -0.08, 0.55), 0.13),
         ((0, -0.28, 0.57), 0.15), ((0, -0.42, 0.58), 0.08), ((0, -0.54, 0.58), 0.11), ((0, -0.68, 0.55), 0.075),
         ((0, -0.79, 0.53), 0.05)]
edges = [(1, 0), (0, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8)]
for s, x in SIDES:
    i = len(nodes)
    nodes += [((x * 0.11, 0.38, 0.47), 0.09), ((x * 0.18, 0.12, 0.24), 0.055), ((x * 0.16, 0.44, 0.13), 0.034), ((x * 0.16, 0.37, 0.025), 0.04)]
    edges += [(0, i), (i, i + 1), (i + 1, i + 2), (i + 2, i + 3)]
    i = len(nodes)
    nodes += [((x * 0.15, -0.28, 0.54), 0.09), ((x * 0.24, -0.16, 0.30), 0.052), ((x * 0.22, -0.42, 0.07), 0.036), ((x * 0.22, -0.50, 0.03), 0.05)]
    edges += [(4, i), (i, i + 1), (i + 1, i + 2), (i + 2, i + 3)]


def gaunt(v, n):
    """Ribs, a knuckled spine, hip bones and lumps: the starved look."""
    d = Vector()
    lump = noise.noise(v * 9.0) * 0.007 + noise.noise(v * 23.0) * 0.003
    d += n * lump
    if -0.26 < v.y < 0.06 and v.z < 0.62 and abs(v.x) > 0.04:              # ribs down the flanks
        d += n * (0.008 * max(0.0, math.sin((v.y + 0.26) * 2 * math.pi / 0.052)) - 0.004)
    if abs(v.x) < 0.035 and v.z > 0.58 and -0.4 < v.y < 0.45:               # vertebrae
        d += n * 0.012 * max(0.0, math.sin(v.y * 2 * math.pi / 0.06)) ** 2
    if 0.06 < v.y < 0.24 and v.z < 0.52:                                      # sunken belly
        d -= n * 0.012
    return d


parts = [K.skin(nodes, edges, SKIN, ("auto", BODY_BONES), subdiv=2, displace=gaunt, name="FeralBody")]
# lower jaw (its own island so the mouth can gape) and the inside of the mouth
parts.append(K.skin([((0, -0.50, 0.49), 0.06), ((0, -0.64, 0.46), 0.055), ((0, -0.76, 0.448), 0.036)], [(0, 1), (1, 2)],
                    SKIN, ("rigid", "jaw"), subdiv=2, name="FeralJaw"))
parts.append(K.ellipsoid((0, -0.62, 0.50), (0.058, 0.15, 0.035), MOUTH, ("rigid", "head"), seg=12))
for s, x in SIDES:                                                       # milky eyes, deep set
    parts.append(K.ellipsoid((x * 0.07, -0.60, 0.605), (0.018, 0.022, 0.015), EYE, ("rigid", "head"), seg=8))
# teeth: a ragged row on each jaw, interleaving when shut
for k in range(8):
    y = -0.57 - k * 0.028
    for s, x in SIDES:
        L = 0.038 if k % 2 == 0 else 0.024
        parts.append(K.cone((x * (0.05 - k * 0.003), y, 0.50), (x * (0.048 - k * 0.003), y - 0.004, 0.50 - L), 0.009, 0.002, BONE, ("rigid", "head"), seg=4, rings=2))
        y2 = y - 0.014
        if y2 > -0.77:
            parts.append(K.cone((x * (0.042 - k * 0.003), y2, 0.475), (x * (0.04 - k * 0.003), y2 + 0.003, 0.475 + L * 0.8), 0.008, 0.002, BONE, ("rigid", "jaw"), seg=4, rings=2))
# claws: four long curved nails per hand, three per hind foot
for s, x in SIDES:
    for j, dx in enumerate((-0.036, -0.012, 0.012, 0.036)):
        p0 = Vector((x * 0.22 + dx * x, -0.53, 0.03))
        parts.append(K.cone(p0, p0 + Vector((dx * 0.4 * x, -0.085 - 0.01 * (j % 2), -0.012)), 0.011, 0.002, BONE, ("rigid", f"hand_{s}"),
                            seg=5, bend=(0, 0, -0.025)))
    for dx in (-0.025, 0.0, 0.025):
        p0 = Vector((x * 0.16 + dx, 0.345, 0.02))
        parts.append(K.cone(p0, p0 + Vector((dx * 0.3, -0.05, -0.01)), 0.009, 0.002, BONE, ("rigid", f"foot_{s}"), seg=5, bend=(0, 0, -0.012)))
# ice: crystals grown out of the spine, longest over the shoulders, a few on the skull and elbows
def back_z(y):
    pts = [(-0.47, 0.64), (-0.30, 0.70), (-0.08, 0.675), (0.14, 0.58), (0.36, 0.61), (0.48, 0.53)]
    for (y0, z0), (y1, z1) in zip(pts, pts[1:]):
        if y0 <= y <= y1:
            return z0 + (z1 - z0) * (y - y0) / (y1 - y0)
    return 0.6


def spine_bone(y):
    return "neck" if y < -0.33 else "chest" if y < -0.10 else "spine" if y < 0.16 else "pelvis"


for k in range(15):
    y = -0.44 + k * 0.058 + rng.uniform(-0.012, 0.012)
    big = max(0.0, 1 - abs(y + 0.22) / 0.62)
    for c in range(rng.choice((1, 2, 2, 3))):
        x = rng.uniform(-0.06, 0.06)
        L = (0.09 + 0.26 * big) * rng.uniform(0.6, 1.1)
        z0 = back_z(y) - 0.02 - abs(x) * 0.6
        d = Vector((x * 4 + rng.uniform(-0.15, 0.15), 0.42 + rng.uniform(-0.1, 0.2), 1.0)).normalized()
        p0 = Vector((x, y, z0))
        parts.append(K.cone(p0, p0 + d * L, 0.022 + 0.022 * big, 0.003, ICE, ("rigid", spine_bone(y)), seg=5, rings=2))
for s, x in SIDES:
    for d in ((x * 0.6, 0.6, 0.7), (x * 0.9, 0.2, 0.4)):
        p0 = Vector((x * 0.22, -0.15, 0.33))
        parts.append(K.cone(p0, p0 + Vector(d).normalized() * 0.09, 0.016, 0.003, ICE, ("rigid", f"upperarm_{s}"), seg=5, rings=2))
for d in ((0.3, 0.8, 0.6), (-0.3, 0.8, 0.6), (0.0, 0.9, 0.8)):
    p0 = Vector((d[0] * 0.08, -0.50, 0.63))
    parts.append(K.cone(p0, p0 + Vector(d).normalized() * 0.08, 0.014, 0.002, ICE, ("rigid", "head"), seg=5, rings=2))

body = K.build_body(rig, parts, mats, "Feral")
print("feral mesh", len(body.data.vertices), "verts", len(body.data.polygons), "faces")
tex = K.bake_texture(body, 1024, ao=0.5, path=OUT + "_paint.png")

# ------------------------------------------------------------------ animation
REST = {}
for s, x in SIDES:
    REST[f"ankle_{s}"] = Vector((x * 0.16, 0.44, 0.13))
    REST[f"wrist_{s}"] = Vector((x * 0.22, -0.42, 0.07))
FOOT_DIR = (Vector((0, 0.36, 0.015)) - Vector((0, 0.44, 0.13))).normalized()
HAND_DIR = Vector((0, -1.0, -0.38)).normalized()


def limbs(P, feet, hands, pole_spread=1.0):
    for s, x in SIDES:
        P.chain(f"thigh_{s}", f"shin_{s}", feet[s], Vector((x * 0.15, -1, -0.2)), f"foot_{s}", feet.get(s + "_dir", FOOT_DIR), FWD)
        P.chain(f"upperarm_{s}", f"forearm_{s}", hands[s], Vector((x * 0.6 * pole_spread, 1, 0.1)), f"hand_{s}", hands.get(s + "_dir", HAND_DIR), UP)


def planted():
    return ({s: REST[f"ankle_{s}"].copy() for s, _ in SIDES}, {s: REST[f"wrist_{s}"].copy() for s, _ in SIDES})


clips = {}


def clip(name, n, fn):
    K.new_action(rig, name)
    for f in range(n + 1):
        P = K.Pose(rig)
        fn(P, f, n)
        P.solve().key(f)
    clips[name] = n


# idle: 48 frames - breathing, sniffing left and right, a twitch, jaw chattering
def idle(P, f, n):
    t = f / n
    br = math.sin(t * 2 * math.pi * 3)
    look = math.sin(t * 2 * math.pi) * 22 + (12 if 0.55 < t < 0.62 else 0)
    P.root("pelvis", offset=(0, 0.01 * math.sin(t * 2 * math.pi), -0.012 + 0.006 * br), rx=-3)
    P.rot("spine", x=-2 + 1.5 * br); P.rot("chest", x=3 + 2 * br, z=look * 0.15)
    P.rot("neck", x=-14 + 4 * math.sin(t * 4 * math.pi), z=look * 0.4)
    P.rot("head", x=6 + 6 * math.sin(t * 2 * math.pi * 6) * (t > 0.3 and t < 0.45), z=look * 0.4, y=-6 * math.sin(t * 2 * math.pi))
    P.rot("jaw", x=-(4 + 10 * max(0.0, math.sin(t * 2 * math.pi * 8)) * (0.7 < t < 0.9)))
    feet, hands = planted()
    limbs(P, feet, hands)


# walk: 20 frames, 0.04 m a frame (about 1 m/s): diagonal pairs, spine snaking, head low and steady
WALK_N, WALK_V = 20, 0.04
DUTY = 0.56
STRIDE = WALK_V * DUTY * WALK_N


def walk(P, f, n):
    t = f / n
    ph = {"hL": 0.0, "fR": 0.08, "hR": 0.5, "fL": 0.58}
    P.root("pelvis", offset=(0, 0, -0.03 + 0.014 * math.cos(t * 4 * math.pi)), rx=-5, ry=4 * math.sin(t * 2 * math.pi), rz=5 * math.sin(t * 2 * math.pi))
    P.rot("spine", z=-6 * math.sin(t * 2 * math.pi), x=2)
    P.rot("chest", z=-7 * math.sin(t * 2 * math.pi + 0.6), x=4 + 2 * math.cos(t * 4 * math.pi))
    P.rot("neck", x=-20, z=8 * math.sin(t * 2 * math.pi + 1.2))
    P.rot("head", x=12 - 3 * math.cos(t * 4 * math.pi), z=4 * math.sin(t * 2 * math.pi + 1.8))
    P.rot("jaw", x=-6 - 6 * max(0.0, math.sin(t * 4 * math.pi)))
    feet, hands = {}, {}
    for s, x in SIDES:
        y, z = K.gait(t + ph["h" + s], DUTY, STRIDE, 0.10, REST[f"ankle_{s}"].y)
        feet[s] = Vector((REST[f"ankle_{s}"].x, y, REST[f"ankle_{s}"].z + z))
        if z > 0.01:                                                    # toes point down as the foot swings
            feet[s + "_dir"] = (FOOT_DIR + Vector((0, 0.5, -0.3)) * (z / 0.1)).normalized()
        y, z = K.gait(t + ph["f" + s], DUTY, STRIDE, 0.12, REST[f"wrist_{s}"].y)
        hands[s] = Vector((REST[f"wrist_{s}"].x, y, REST[f"wrist_{s}"].z + z))
        if z > 0.01:
            hands[s + "_dir"] = (HAND_DIR + Vector((0, 0.6, -0.8)) * (z / 0.12)).normalized()
    limbs(P, feet, hands)


# bite: 22 frames - gathers back, lunges with the jaw wide, snaps shut on BITE_HIT, recovers
BITE_N, BITE_HIT = 22, 11


def bite(P, f, n):
    back = K.smoothstep(0, 6, f) * (1 - K.smoothstep(7, 10, f))
    lunge = K.smoothstep(7, 11, f) * (1 - K.smoothstep(14, 21, f))
    gape = K.smoothstep(2, 8, f) * (1 - K.smoothstep(10, 11.5, f))
    P.root("pelvis", offset=(0, 0.07 * back - 0.20 * lunge, -0.05 * back + 0.03 * lunge), rx=4 * back - 8 * lunge)
    P.rot("spine", x=-4 * back + 4 * lunge)
    P.rot("chest", x=10 * back - 6 * lunge)
    P.rot("neck", x=-10 + 22 * back - 10 * lunge)
    P.rot("head", x=10 + 10 * back - 6 * lunge, y=8 * lunge)
    P.rot("jaw", x=-4 - 48 * gape)
    feet, hands = planted()
    for s, x in SIDES:
        hands[s] = hands[s] + Vector((0, -0.16 * lunge, 0.06 * lunge * (1 if s == "L" else 0.3)))
    limbs(P, feet, hands)


def hit(P, f, n):
    k = K.smoothstep(0, 3, f) * (1 - K.smoothstep(5, 13, f))
    P.root("pelvis", offset=(0, 0.06 * k, -0.02 * k), rx=6 * k, ry=-6 * k)
    P.rot("chest", x=12 * k, z=10 * k)
    P.rot("neck", x=10 * k, z=-24 * k)
    P.rot("head", x=10 * k, y=-12 * k)
    P.rot("jaw", x=-30 * k)
    feet, hands = planted()
    limbs(P, feet, hands)


# death: 36 frames - rears, staggers, collapses onto its right side, legs draw in, jaw falls open
def death(P, f, n):
    rear = K.smoothstep(0, 6, f) * (1 - K.smoothstep(8, 14, f))
    fall = K.smoothstep(8, 22, f)
    curl = K.smoothstep(16, 32, f)
    P.root("pelvis", offset=(0.08 * fall, 0.04 * rear, -0.34 * fall + 0.04 * rear), ry=-84 * fall, rx=10 * rear)
    P.rot("chest", x=16 * rear - 6 * fall, z=8 * fall)
    P.rot("neck", x=14 * rear - 10 * fall, z=-14 * fall)
    P.rot("head", x=-10 * curl, z=-10 * fall, y=-14 * fall)
    P.rot("jaw", x=-10 - 26 * K.smoothstep(14, 26, f))
    R = P.rig.rest["pelvis"]
    W = R @ P.basis["pelvis"] @ R.inverted()                          # how the body has moved
    feet, hands = planted()
    for s, x in SIDES:
        a = REST[f"ankle_{s}"]; w = REST[f"wrist_{s}"]
        a_body = W @ (a + Vector((-x * 0.05, -0.12, 0.10)) * curl)
        w_body = W @ (w + Vector((-x * 0.04, 0.14, 0.14)) * curl)
        feet[s] = a.lerp(a_body, fall); hands[s] = w.lerp(w_body, fall)
        feet[s + "_dir"] = (W.to_3x3() @ FOOT_DIR).lerp(FOOT_DIR, 1 - fall).normalized()
        hands[s + "_dir"] = (W.to_3x3() @ HAND_DIR).lerp(HAND_DIR, 1 - fall).normalized()
    limbs(P, feet, hands)


clip("idle", 48, idle)
clip("walk", WALK_N, walk)
clip("bite", BITE_N, bite)
clip("hit", 14, hit)
clip("death", 36, death)
sc.frame_start, sc.frame_end = 0, 48

if PREVIEW:
    import creature_preview
    creature_preview.render(rig, body, PREVIEW, {"idle": [0, 24], "walk": [0, 5, 10, 15], "bite": [0, 6, 11, 16], "hit": [4], "death": [12, 36]})

K.export(rig, OUT, {
    "fps_src": 24, "clips": {k: k for k in clips}, "idle_loop_src": [0, 48], "height_m": 0.75, "exposure": 1.05,
    "creature": "feral", "lengths": clips,
    "view": {"w": 460, "h": 440, "foot_y": 290, "big_w": 640, "big_h": 520, "big_foot_y": 300}, "walk_v": WALK_V, "bite_hit": BITE_HIT,
})
print("exported", OUT, clips)
