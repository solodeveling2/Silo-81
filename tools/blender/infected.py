"""Infected Human (Tier 1, Firn Strata): a deranged survivor in a hooded, torn field coat, hunched,
head lolling, mouth hanging open, hands bloody to the wrist. Built and animated in code
(creature_kit.py), exported for live 3D (game/characters/infected_3d).

Clips (24 fps, in place, feet planted): idle (hunched breathing, head jerks), walk (a dragging shamble),
bite (both hands up, lunge and rake; hit on CLAW_HIT), hit (recoil), death (knees go, falls on its face).

Usage: python3 -I infected.py OUT_BASENAME [--preview DIR]
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector, Matrix, noise
import creature_kit as K

OUT = sys.argv[1]
PREVIEW = sys.argv[sys.argv.index("--preview") + 1] if "--preview" in sys.argv else None
rng = random.Random(82)
sc = K.reset()
SIDES = (("L", 1), ("R", -1))
UP, FWD, BACK = (0, 0, 1), (0, -1, 0), (0, 1, 0)

bones = [
    ("pelvis", (0, 0, 0.95), (0, 0, 1.08), None, FWD),
    ("spine", (0, 0, 1.08), (0, 0.01, 1.26), "pelvis", FWD),
    ("chest", (0, 0.01, 1.26), (0, 0.0, 1.44), "spine", FWD),
    ("neck", (0, 0.0, 1.44), (0, -0.01, 1.54), "chest", FWD),
    ("head", (0, -0.01, 1.54), (0, -0.02, 1.74), "neck", FWD),
    ("jaw", (0, -0.03, 1.585), (0, -0.09, 1.535), "head", UP),
]
for s, x in SIDES:
    bones += [
        (f"clav_{s}", (x * 0.03, 0.0, 1.42), (x * 0.17, 0.01, 1.43), "chest", FWD),
        (f"upperarm_{s}", (x * 0.17, 0.01, 1.43), (x * 0.22, 0.03, 1.15), f"clav_{s}", BACK),
        (f"forearm_{s}", (x * 0.22, 0.03, 1.15), (x * 0.25, -0.02, 0.91), f"upperarm_{s}", BACK),
        (f"hand_{s}", (x * 0.25, -0.02, 0.91), (x * 0.26, -0.05, 0.72), f"forearm_{s}", FWD),
        (f"thigh_{s}", (x * 0.10, 0.0, 0.93), (x * 0.11, -0.01, 0.50), "pelvis", FWD),
        (f"shin_{s}", (x * 0.11, -0.01, 0.50), (x * 0.11, 0.02, 0.09), f"thigh_{s}", FWD),
        (f"foot_{s}", (x * 0.11, 0.02, 0.09), (x * 0.11, -0.13, 0.025), f"shin_{s}", UP),
    ]
rig = K.Rig("InfectedRig", bones)
BODY_BONES = [b[0] for b in bones if b[0] != "jaw"]
segs = {n: rig.seg(n) for n in rig.order}


def nearest_bone(p, among=BODY_BONES):
    best, bn = 9.0, None
    for n in among:
        a, b = segs[n]; ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / ab.dot(ab)))
        d = (p - (a + ab * t)).length
        if d < best:
            best, bn = d, n
    return bn


COAT, SKIN, TROUSER, BOOT, HOOD, MOUTH = range(6)
MOUTH_PT = (0, -0.08, 1.56)
HANDS = [(x * 0.26, -0.05, 0.78) for _, x in SIDES]
mats = [
    K.paint_material("InfCoat", (0.36, 0.33, 0.23), (0.17, 0.15, 0.11), accent=(0.30, 0.08, 0.07), noise_scale=5.0, contrast=0.75,
                     accent_mask=K.mask_noise(5.0, -0.22, K.mask_near([(0, -0.15, 1.34), (0.05, -0.13, 1.20)], 0.12, noise_amt=0.6, noise_scale=12.0))),
    K.paint_material("InfSkin", (0.70, 0.62, 0.57), (0.46, 0.38, 0.37), accent=(0.38, 0.09, 0.08), noise_scale=10.0, contrast=0.6,
                     accent_mask=K.mask_near([MOUTH_PT, (0, -0.09, 1.53)] + [(x * 0.265, -0.05, 0.73) for _, x in SIDES], 0.09, noise_amt=0.5, noise_scale=14.0)),
    K.paint_material("InfTrousers", (0.31, 0.32, 0.33), (0.16, 0.16, 0.17), accent=(0.24, 0.20, 0.16), noise_scale=6.0,
                     accent_mask=K.mask_noise(3.0, 0.0, K.mask_near([(x * 0.11, -0.02, 0.15) for _, x in SIDES], 0.25, noise_amt=0.5))),
    K.paint_material("InfBoots", (0.22, 0.18, 0.14), (0.10, 0.08, 0.07), noise_scale=12.0),
    K.paint_material("InfHood", (0.40, 0.36, 0.26), (0.20, 0.18, 0.13), accent=(0.30, 0.08, 0.07), noise_scale=6.0, contrast=0.7,
                     accent_mask=K.mask_noise(4.0, -0.25)),
    K.paint_material("InfMouth", (0.26, 0.06, 0.06), (0.10, 0.02, 0.03), noise_scale=12.0),
]


def region(c):
    b = nearest_bone(c)
    if b in ("head", "neck"):
        return SKIN
    if b.startswith("hand"):
        return SKIN
    if b.startswith(("thigh", "shin")):
        return TROUSER
    if b.startswith("foot"):
        return BOOT
    return COAT


nodes = [((0, 0.0, 0.95), 0.145), ((0, 0.015, 1.10), 0.135), ((0, 0.025, 1.30), 0.155), ((0, 0.02, 1.42), 0.12),
         ((0, 0.0, 1.52), 0.055), ((0, -0.015, 1.625), 0.092), ((0, 0.0, 1.715), 0.068)]
edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6)]
for s, x in SIDES:
    i = len(nodes)
    nodes += [((x * 0.10, 0.0, 0.92), 0.09), ((x * 0.11, -0.01, 0.50), 0.065), ((x * 0.11, 0.02, 0.10), 0.05), ((x * 0.11, -0.11, 0.045), 0.05)]
    edges += [(0, i), (i, i + 1), (i + 1, i + 2), (i + 2, i + 3)]
    i = len(nodes)
    nodes += [((x * 0.18, 0.01, 1.41), 0.068), ((x * 0.22, 0.03, 1.15), 0.055), ((x * 0.25, -0.02, 0.92), 0.045),
              ((x * 0.26, -0.04, 0.82), 0.042), ((x * 0.265, -0.05, 0.72), 0.022)]
    edges += [(3, i), (i, i + 1), (i + 1, i + 2), (i + 2, i + 3), (i + 3, i + 4)]


def lumpy(v, n):
    d = n * (noise.noise(v * 7.0) * 0.008 + noise.noise(v * 19.0) * 0.003)
    if v.z > 1.56 and v.y < -0.06:                                           # sunken eyes, a sharp brow
        d += n * -0.006
    return d


parts = [K.skin(nodes, edges, region, ("auto", BODY_BONES), subdiv=2, displace=lumpy, name="InfBody")]
parts.append(K.skin([((0, -0.035, 1.585), 0.045), ((0, -0.08, 1.548), 0.034)], [(0, 1)], SKIN, ("rigid", "jaw"), subdiv=2, name="InfJaw"))
parts.append(K.ellipsoid((0, -0.07, 1.585), (0.036, 0.03, 0.032), MOUTH, ("rigid", "head"), seg=10))
for s, x in SIDES:
    parts.append(K.ellipsoid((x * 0.034, -0.086, 1.648), (0.019, 0.012, 0.014), MOUTH, ("rigid", "head"), seg=8))


# the coat's skirt: open-ish, torn at the hem, swinging with the legs
def hem(a):
    return 0.06 * max(0.0, noise.noise(Vector((math.cos(a) * 3, math.sin(a) * 3, 0.5)))) + 0.05 * (math.sin(a * 7) > 0.6)


parts.append(K.tube([(0, 0.02, 1.04), (0, 0.025, 0.86), (0, 0.03, 0.66)], [(0.15, 0.14), (0.17, 0.155), (0.19, 0.165)], COAT,
                    ("auto", ["pelvis", "spine", "thigh_L", "thigh_R"]), seg=18, hem=hem, name="InfSkirt"))
# hood: a deep shell over the skull, the face open, hanging down the back of the neck
parts.append(K.shell((0, 0.012, 1.635), (0.125, 0.13, 0.135), HOOD, ("auto", ["head", "neck"]),
                     cut=lambda c: (c.y < -0.03 and 1.50 < c.z < 1.74 and abs(c.x) < 0.11) or c.z < 1.52, seg=20, thick=0.018, name="InfHood"))
# a torn flap of coat hanging from the left shoulder, a strap across the chest
parts.append(K.cone((0.19, 0.06, 1.38), (0.23, 0.08, 1.02), 0.05, 0.02, COAT, ("auto", ["upperarm_L", "chest"]), seg=4, rings=3))

body = K.build_body(rig, parts, mats, "Infected")
print("infected mesh", len(body.data.vertices), "verts")
tex = K.bake_texture(body, 1024, ao=0.5, path=OUT + "_paint.png")

# ------------------------------------------------------------------ animation
ANKLE = {s: Vector((x * 0.11, 0.02, 0.09)) for s, x in SIDES}
FOOT_DIR = Vector((0, -0.15, -0.065)).normalized()


def legs(P, feet):
    for s, x in SIDES:
        P.chain(f"thigh_{s}", f"shin_{s}", feet[s], Vector((x * 0.1, -1, 0)), f"foot_{s}", feet.get(s + "_dir", FOOT_DIR), UP)


def hunch(P, k=1.0, br=0.0):
    P.rot("spine", x=16 * k + 1.5 * br); P.rot("chest", x=20 * k + 2 * br); P.rot("neck", x=-12 * k); P.rot("head", x=-10 * k)
    for s, x in SIDES:
        P.rot(f"clav_{s}", x=-6 * k)
        P.rot(f"upperarm_{s}", x=-22 * k, z=x * 4)
        P.rot(f"forearm_{s}", x=-18 * k)
        P.rot(f"hand_{s}", x=10 * k)


clips = {}


def clip(name, n, fn):
    K.new_action(rig, name)
    for f in range(n + 1):
        P = K.Pose(rig)
        fn(P, f, n)
        P.solve().key(f)
    clips[name] = n


# idle: 96 frames - hunched, breathing hard, swaying, the head snapping to one side now and then
JERKS = [(14, 18, 26), (44, 47, -20), (70, 75, 32)]


def idle(P, f, n):
    t = f / n
    br = math.sin(t * 2 * math.pi * 4)
    jerk = sum(a * K.smoothstep(s0, s0 + 1.5, f) * (1 - K.smoothstep(e, e + 6, f)) for s0, e, a in JERKS)
    P.root("pelvis", offset=(0.02 * math.sin(t * 2 * math.pi), 0, -0.02 + 0.006 * br), ry=3 * math.sin(t * 2 * math.pi), rz=4 * math.sin(t * 2 * math.pi + 1))
    hunch(P, 1.0, br)
    P.rot("neck", z=jerk * 0.4); P.rot("head", z=jerk * 0.6, y=14 + 6 * math.sin(t * 2 * math.pi * 2))
    P.rot("jaw", x=-(14 + 6 * math.sin(t * 2 * math.pi * 3)))
    P.rot("upperarm_L", x=4 * math.sin(t * 2 * math.pi + 0.5)); P.rot("upperarm_R", x=-5 * math.sin(t * 2 * math.pi))
    P.rot("forearm_R", x=-8 * max(0.0, math.sin(t * 2 * math.pi * 5)) * (0.5 < t < 0.65))     # fingers twitch
    legs(P, {s: ANKLE[s].copy() for s, _ in SIDES})


# walk: 40 frames, 0.025 m a frame - the right leg drags, the body lurches onto the left
WALK_N, WALK_V, DUTY = 40, 0.025, 0.62
STRIDE = WALK_V * DUTY * WALK_N


def walk(P, f, n):
    t = f / n
    c = math.cos(t * 2 * math.pi)
    P.root("pelvis", offset=(0.03 * c, 0, -0.03 - 0.025 * max(0.0, -c)), ry=-6 * c, rz=8 * math.sin(t * 2 * math.pi))
    hunch(P, 1.2)
    P.rot("spine", y=6 * c); P.rot("chest", y=-8 * c, z=-6 * math.sin(t * 2 * math.pi))
    P.rot("head", z=10 * math.sin(t * 2 * math.pi + 1.5), y=16 + 8 * c)
    P.rot("jaw", x=-18)
    P.rot("upperarm_L", x=-30 - 10 * math.sin(t * 2 * math.pi)); P.rot("forearm_L", x=-20)       # the left reaches ahead
    P.rot("upperarm_R", x=14 * math.sin(t * 2 * math.pi + math.pi), z=-6)                        # the right hangs and swings
    feet = {}
    for s, x in SIDES:
        drag = s == "R"
        y, z = K.gait(t + (0.0 if s == "L" else 0.5), DUTY, STRIDE, 0.035 if drag else 0.09, ANKLE[s].y)
        feet[s] = Vector((ANKLE[s].x, y, ANKLE[s].z + z))
        if z > 0.005:
            tip = Vector((0, 0.3, -0.6)) if drag else Vector((0, 0.15, -0.35))
            feet[s + "_dir"] = (FOOT_DIR + tip * (z / (0.035 if drag else 0.09))).normalized()
    legs(P, feet)


# bite (the claw): 24 frames - hands up, lunge and rake down on CLAW_HIT, stagger back
CLAW_N, CLAW_HIT = 24, 13


def claw(P, f, n):
    up = K.smoothstep(0, 8, f) * (1 - K.smoothstep(10, 13, f))
    lunge = K.smoothstep(9, 13, f) * (1 - K.smoothstep(15, 23, f))
    rake = K.smoothstep(10, 14, f) * (1 - K.smoothstep(16, 23, f))
    P.root("pelvis", offset=(0, 0.05 * up - 0.16 * lunge, -0.03 * up - 0.06 * lunge), rx=-4 * up)
    hunch(P, 1.0 - 0.6 * up)
    P.rot("spine", x=-6 * up + 18 * lunge); P.rot("chest", x=-8 * up + 22 * lunge)
    P.rot("head", x=-10 * up + 8 * lunge)
    P.rot("jaw", x=-14 - 26 * K.smoothstep(4, 12, f) * (1 - K.smoothstep(16, 22, f)))
    for s, x in SIDES:
        P.rot(f"upperarm_{s}", x=-150 * up - 60 * rake, z=x * (10 * up))
        P.rot(f"forearm_{s}", x=-35 * up - 10 * rake)
        P.rot(f"hand_{s}", x=-20 * up + 30 * rake)
    legs(P, {s: ANKLE[s].copy() for s, _ in SIDES})


def hit(P, f, n):
    k = K.smoothstep(0, 3, f) * (1 - K.smoothstep(5, 13, f))
    P.root("pelvis", offset=(0, 0.05 * k, -0.02 * k), rz=8 * k)
    hunch(P, 1.0 - 0.8 * k)
    P.rot("spine", x=-10 * k); P.rot("chest", x=-12 * k, z=10 * k)
    P.rot("head", x=-20 * k, z=-24 * k)
    P.rot("jaw", x=-30 * k - 10)
    P.rot("upperarm_L", x=-30 * k, z=20 * k); P.rot("upperarm_R", x=20 * k, z=-25 * k)
    legs(P, {s: ANKLE[s].copy() for s, _ in SIDES})


# death: 40 frames - the knees go, it pitches forward onto its face, one arm under it
def death(P, f, n):
    buckle = K.smoothstep(2, 12, f)
    fall = K.smoothstep(10, 26, f)
    P.root("pelvis", offset=(0, -0.36 * fall, -0.20 * buckle - 0.66 * fall), rx=84 * fall, rz=10 * fall)
    hunch(P, 1.0 + 0.4 * buckle - 1.2 * fall)
    P.rot("neck", x=-20 * fall, z=18 * fall); P.rot("head", z=26 * fall, y=20 * fall)
    P.rot("jaw", x=-20 - 14 * fall)
    P.rot("upperarm_L", x=-40 * buckle - 120 * fall, z=20 * fall); P.rot("forearm_L", x=-30 * fall)
    P.rot("upperarm_R", x=-30 * buckle + 30 * fall, z=-30 * fall); P.rot("forearm_R", x=-50 * fall)
    R = P.rig.rest["pelvis"]
    W = R @ P.basis["pelvis"] @ R.inverted()
    feet = {}
    for s, x in SIDES:
        a = ANKLE[s]
        knelt = a + Vector((0, 0.05, 0.0))
        body = W @ (a + Vector((0, 0.10, 0.12)))
        feet[s] = a.lerp(knelt, buckle).lerp(body, fall)
        feet[s + "_dir"] = (W.to_3x3() @ FOOT_DIR).lerp(FOOT_DIR, 1 - fall).normalized()
    legs(P, feet)


clip("idle", 96, idle)
clip("walk", WALK_N, walk)
clip("bite", CLAW_N, claw)
clip("hit", 14, hit)
clip("death", 40, death)
sc.frame_start, sc.frame_end = 0, 96

if PREVIEW:
    import creature_preview
    creature_preview.render(rig, body, PREVIEW, {"idle": [0, 16, 48], "walk": [0, 10, 20, 30], "bite": [0, 8, 13, 18], "hit": [4], "death": [14, 40]}, span=2.4)

K.export(rig, OUT, {
    "fps_src": 24, "clips": {k: k for k in clips}, "idle_loop_src": [0, 96], "height_m": 1.72, "exposure": 1.05,
    "creature": "infected", "lengths": clips,
    "view": {"w": 420, "h": 460, "foot_y": 380, "big_w": 760, "big_h": 620, "big_foot_y": 330}, "walk_v": WALK_V, "bite_hit": CLAW_HIT,
})
print("exported", OUT, clips)
