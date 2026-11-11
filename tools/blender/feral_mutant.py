"""Feral Mutant (Tier 1, Firn Strata): a starved human turned quadruped. Long thin limbs, human hands
that walk on their fingers, jumping hind legs with a high hock, a long hyena skull with a big ragged
jaw, pale flesh with bruising and red wounds, and blue-grey ice crystals grown out of the spine from
raw, swollen bases. Rags of its old clothes are still wrapped round the forearms and one thigh.

Same pipeline as infected_human.py (see docs/ART_DIRECTION.md):
  --stage high   sculpted forms (metaballs) + modelled detail + painted materials  -> OUT_high.blend
  --stage low    QuadriFlow / decimate to the game budget, one mesh, bake paint+AO   -> OUT_low.blend
  --stage rig    quadruped skeleton, bone-heat weights through a closed proxy, rigid crystals/teeth/claws,
                 clips (idle, walk, bite, hit, death), GLB + json                    -> OUT.glb, OUT.json, OUT_mutant.blend
Usage: python3 -I feral_mutant.py OUT_BASENAME --stage high|low|rig [--qc]
Model faces -Y, Z up, metres; the origin sits under the middle of the body.
"""
import sys, os, math, random, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
import numpy as np
from mathutils import Vector, Matrix, Quaternion, noise
from mathutils.bvhtree import BVHTree
import human_kit as H

OUT = sys.argv[1]
STAGE = sys.argv[sys.argv.index("--stage") + 1] if "--stage" in sys.argv else "high"
rng = random.Random(1981)
SIDES = (("L", 1), ("R", -1))


def V(*a):
    return Vector(a)


# ------------------------------------------------------------------ landmarks (joint centres)
SH = {s: V(x * 0.150, -0.10, 0.70) for s, x in SIDES}        # shoulder
EL = {s: V(x * 0.170, -0.03, 0.42) for s, x in SIDES}        # elbow (points back, like a human arm)
WR = {s: V(x * 0.165, -0.15, 0.10) for s, x in SIDES}        # wrist
KNU = {s: V(x * 0.165, -0.25, 0.030) for s, x in SIDES}      # knuckles (the hand stands on its fingers)
HIP = {s: V(x * 0.100, 0.56, 0.66) for s, x in SIDES}
KN = {s: V(x * 0.135, 0.36, 0.40) for s, x in SIDES}        # knee (forward)
HK = {s: V(x * 0.125, 0.62, 0.20) for s, x in SIDES}        # hock (high, back)
BALL = {s: V(x * 0.125, 0.53, 0.036) for s, x in SIDES}     # ball of the hind foot
TOE = {s: V(x * 0.125, 0.45, 0.014) for s, x in SIDES}
HC = V(0, -0.42, 0.87)                                      # cranium centre
HINGE = HC + V(0, 0.0, -0.065)                              # jaw hinge (on the midline)
JAW_OPEN = 26.0                                             # the jaw is sculpted hanging open this far


def along(a, b):
    """Quaternion turning an ellipsoid's local Z onto the segment a->b."""
    return V(0, 0, 1).rotation_difference((Vector(b) - Vector(a)).normalized())


def jaw_open(p, deg=JAW_OPEN):
    """A point of the lower jaw (given closed) swung open about the hinge."""
    return HINGE + (Matrix.Rotation(math.radians(deg), 3, "X") @ (Vector(p) - HINGE))


def topline(y):
    """Approximate height of the back's skin (for laying out the crystals before the mesh exists)."""
    pts = [(-0.50, 0.93), (-0.42, 0.945), (-0.30, 0.93), (-0.14, 0.945), (-0.04, 0.965), (0.14, 0.975),
           (0.36, 0.90), (0.56, 0.855), (0.70, 0.80)]
    for (y0, z0), (y1, z1) in zip(pts, pts[1:]):
        if y0 <= y <= y1:
            return z0 + (z1 - z0) * (y - y0) / (y1 - y0)
    return 0.85


PARTS = {}


def add(name, ob, mat):
    ob.name = name
    PARTS[name] = (ob, mat)
    return ob


# ------------------------------------------------------------------ crystal layout (used by body, paint, spikes)
def crystal_layout():
    """(base point on the back, direction, length, base radius, bone hint) for every crystal."""
    out = []
    r = random.Random(7)
    # the main ridge down the spine: longest over the withers and upper back
    y = -0.46
    while y < 0.66:
        big = math.exp(-((y - 0.05) / 0.30) ** 2)
        for c in range(r.choice((1, 1, 2, 2, 3))):
            x = r.uniform(-0.035, 0.035) if c == 0 else r.choice((-1, 1)) * r.uniform(0.04, 0.085)
            L = (0.05 + 0.36 * big) * r.uniform(0.5, 1.15) * (0.7 if c else 1.0)
            d = V(x * 5.0 + r.uniform(-0.12, 0.12), 0.35 + r.uniform(-0.1, 0.25), 1.0).normalized()
            out.append((V(x, y, topline(y) - abs(x) * 0.5), d, L, max(0.012, L * r.uniform(0.11, 0.15))))
        y += 0.038 + 0.03 * (1 - big) + r.uniform(-0.008, 0.008)
    # fans over the shoulder blades, pointing out (they read from above as a spiky collar)
    for s, x in SIDES:
        for d, L in (((x * 0.85, 0.15, 0.55), 0.24), ((x * 0.6, 0.45, 0.7), 0.19), ((x * 0.9, -0.15, 0.35), 0.13),
                     ((x * 0.7, 0.6, 0.45), 0.14)):
            out.append((V(x * 0.085, -0.05 + r.uniform(-0.03, 0.03), 0.885), V(*d).normalized(), L * r.uniform(0.85, 1.1), L * 0.12))
        # a few small ones on the elbow and the hip
        out.append((EL[s] + V(x * 0.035, 0.03, 0.02), V(x * 0.7, 0.6, 0.35).normalized(), 0.07, 0.011))
        out.append((HIP[s] + V(x * 0.06, 0.02, 0.10), V(x * 0.6, 0.5, 0.65).normalized(), 0.08, 0.012))
    # skull: a short crown
    for d in ((0.35, 0.6, 0.75), (-0.35, 0.6, 0.75), (0.0, 0.7, 0.8)):
        out.append((HC + V(d[0] * 0.07, 0.03, 0.068), V(*d).normalized(), 0.06, 0.011))
    return out


CRYSTALS = crystal_layout()


# ------------------------------------------------------------------ forms (shared by the sculpts and the weight proxy)
def body_forms(s, coarse=False):
    s.ellipsoid(V(0, 0.02, 0.715), (0.12, 0.21, 0.21))                         # ribcage, deep and narrow
    s.ellipsoid(V(0, -0.09, 0.63), (0.09, 0.11, 0.12))                          # brisket
    for _, x in SIDES:
        s.ellipsoid(V(x * 0.072, -0.04, 0.86), (0.055, 0.12, 0.085), rot=Quaternion((0, 1, 0), x * 0.35))   # shoulder blades
    s.chain([V(0, -0.07, 0.875), V(0, 0.14, 0.895), V(0, 0.36, 0.83), V(0, 0.56, 0.775)], [0.085, 0.08, 0.07, 0.08])  # arched back
    s.ellipsoid(V(0, 0.33, 0.73), (0.078, 0.13, 0.08))                           # tucked waist
    s.ellipsoid(V(0, 0.56, 0.715), (0.10, 0.11, 0.095))                          # pelvis
    s.ball(V(0, 0.65, 0.74), 0.064)                                              # rump
    s.chain([V(0, -0.10, 0.80), V(0, -0.24, 0.84), V(0, -0.34, 0.86)], [0.11, 0.085, 0.068])   # neck
    s.ellipsoid(V(0, -0.19, 0.77), (0.065, 0.09, 0.055))                         # throat
    for side, x in SIDES:
        sh, el, wr = SH[side], EL[side], WR[side]
        s.ball(sh, 0.064)                                                        # deltoid
        s.ellipsoid(sh.lerp(el, 0.38) + V(0, 0.012, 0), (0.04, 0.042, 0.095), rot=along(sh, el))
        s.chain([sh, el], [0.046, 0.032])
        s.chain([el, wr], [0.032, 0.02])
        s.ellipsoid(el.lerp(wr, 0.26) + V(0, -0.006, 0), (0.032, 0.03, 0.08), rot=along(el, wr))   # forearm flexors
        hp, kn, hk, ba = HIP[side], KN[side], HK[side], BALL[side]
        s.ellipsoid(hp.lerp(kn, 0.42) + V(x * 0.01, 0.0, 0.02), (0.06, 0.08, 0.15), rot=along(hp, kn))  # thigh
        s.chain([hp, kn], [0.062, 0.034])
        s.chain([kn, hk], [0.032, 0.019])
        s.ellipsoid(kn.lerp(hk, 0.3) + V(0, 0.024, 0.012), (0.03, 0.036, 0.07), rot=along(kn, hk))   # calf
        s.chain([hk, ba], [0.019, 0.017])
    if not coarse:
        for p, d, L, rb in CRYSTALS:                                            # raw swellings round the crystals
            if p.z > 0.8 and p.y > -0.33:
                s.ball(p - d * 0.01, rb * 1.5)


def head_forms(s, coarse=False):
    C = HC
    s.ellipsoid(C + V(0, 0.02, 0.0), (0.06, 0.09, 0.064))                      # cranium
    s.capsule(C + V(0, 0.07, 0.056), C + V(0, -0.05, 0.062), 0.013)           # sagittal crest
    s.ellipsoid(C + V(0, -0.072, 0.033), (0.056, 0.022, 0.019))                 # heavy brow ridge
    for x in (-1, 1):
        s.ellipsoid(C + V(x * 0.056, -0.02, -0.04), (0.03, 0.06, 0.045))        # masseters (bone-crushing jaws)
        s.ellipsoid(C + V(x * 0.05, -0.055, -0.006), (0.013, 0.05, 0.012))       # cheekbone arch
        if not coarse:
            s.ball(C + V(x * 0.045, -0.085, 0.018), 0.0135, neg=True)          # deep eye sockets
    s.ellipsoid(C + V(0, -0.15, -0.022), (0.04, 0.11, 0.05))                   # long, deep muzzle
    s.ellipsoid(C + V(0, -0.14, 0.014), (0.033, 0.085, 0.022))                 # nasal bridge
    s.ellipsoid(C + V(0, -0.252, -0.032), (0.027, 0.032, 0.03))                # end of the muzzle
    s.ball(C + V(0, -0.276, -0.026), 0.018)                                    # nose pad
    if not coarse:
        for x in (-1, 1):
            s.ball(C + V(x * 0.01, -0.294, -0.026), 0.0065, neg=True)          # nostrils
    # lower jaw: a deep, heavy mandible hanging open
    for x in (-1, 1):
        s.capsule(jaw_open(C + V(x * 0.05, 0.0, -0.07)), jaw_open(C + V(x * 0.026, -0.22, -0.088)), 0.016)
        s.ellipsoid(jaw_open(C + V(x * 0.038, -0.10, -0.097)), (0.014, 0.085, 0.022))
        s.ellipsoid(C + V(x * 0.048, -0.045, -0.078), (0.019, 0.045, 0.026))    # lip web at the corner of the mouth
    s.ball(jaw_open(C + V(0, -0.238, -0.09)), 0.017)                            # chin
    s.capsule(jaw_open(C + V(-0.026, -0.22, -0.09)), jaw_open(C + V(0.026, -0.22, -0.09)), 0.015)
    s.chain([C + V(0, 0.06, -0.02), C + V(0, 0.12, -0.03)], [0.058, 0.064])     # into the neck


def hand_frame(side, x):
    u = (KNU[side] - WR[side]).normalized()                                     # along the hand
    up = u.cross(V(1, 0, 0)).normalized()                                       # back of the hand
    return u, V(x, 0, 0), up


FINGER_TIPS = {}


def hand_forms(s, side, x, coarse=False):
    u, lat, up = hand_frame(side, x)
    W, Kn = WR[side], KNU[side]
    s.capsule(W + (W - Kn).normalized() * 0.05, W, 0.027)                       # wrist into the forearm
    s.ellipsoid(W.lerp(Kn, 0.5), (0.036, 0.016, 0.066), rot=Matrix((V(1, 0, 0), up, u)).transposed().to_quaternion())
    tips = []
    spread = (-0.032, -0.011, 0.011, 0.031)
    for j, off in enumerate(spread):
        L = (0.86, 1.0, 1.04, 0.92)[j]
        p = Kn + lat * off
        heading = V(off * 1.2 * x, -1, 0).normalized()
        pts = [p]
        for seg, dz, r in ((0.046 * L, 0.26, 0.0105), (0.036 * L, -0.42, 0.0092), (0.028 * L, -0.95, 0.0078)):
            d = (heading + V(0, 0, dz)).normalized()
            p = p + d * seg
            pts.append(p)
        if p.z < 0.008:                                                         # finger pads rest on the ground
            dz = 0.008 - p.z
            pts = [q + V(0, 0, dz * k / 3) for k, q in enumerate(pts)]
        s.chain(pts, [0.012, 0.0105, 0.0092, 0.0078], stiff=2.5)
        tips.append((pts[-1], (pts[-1] - pts[-2]).normalized()))
    # thumb: inner side, shorter, pointing in and forward
    t0 = W.lerp(Kn, 0.55) - lat * 0.03 * 1.0
    td = V(-x * 0.45, -0.85, -0.25).normalized()
    tb = [t0, t0 + td * 0.04]
    tb.append(tb[-1] + V(-x * 0.2, -0.6, -0.75).normalized() * 0.032)
    if tb[-1].z < 0.009:
        tb[-1].z = 0.009
    s.chain(tb, [0.013, 0.011, 0.0088], stiff=2.5)
    tips.append((tb[-1], (tb[-1] - tb[-2]).normalized()))
    FINGER_TIPS[side] = tips


TOE_TIPS = {}


def paw_forms(s, side, x, coarse=False):
    hk, ba = HK[side], BALL[side]
    s.chain([hk.lerp(ba, 0.4), ba], [0.022, 0.024])
    s.ellipsoid(ba + V(0, -0.012, -0.006), (0.034, 0.03, 0.02))                 # pad
    tips = []
    for j, off in enumerate((-0.026, -0.009, 0.009, 0.025)):
        L = (0.8, 1.0, 1.0, 0.85)[j]
        p = ba + V(off, -0.02, -0.006)
        pts = [p]
        for seg, dz, r in ((0.036 * L, 0.12, 0.0105), (0.028 * L, -0.8, 0.009)):
            p = p + (V(off * 1.5, -1, dz)).normalized() * seg
            pts.append(p)
        if p.z < 0.009:
            pts[-1].z = 0.009
        s.chain(pts, [0.012, 0.0105, 0.009], stiff=2.5)
        tips.append((pts[-1], (pts[-1] - pts[-2]).normalized()))
    TOE_TIPS[side] = tips


# ------------------------------------------------------------------ surface detail
WOUNDS = [V(0.12, 0.10, 0.70), V(-0.11, -0.02, 0.62), V(0.09, 0.42, 0.66), V(-0.15, 0.30, 0.47), V(0.17, -0.08, 0.30),
          V(-0.13, 0.55, 0.60), V(0.05, -0.20, 0.72)]


def gaunt(v, n):
    d = n * (noise.noise(v * 8.0) * 0.006 + noise.noise(v * 23.0) * 0.0024)
    if -0.15 < v.y < 0.20 and 0.56 < v.z < 0.83 and abs(v.x) > 0.07:            # ribs, slanting down and forward
        ph = (v.y + 0.35 * (0.83 - v.z) + 0.15) * 2 * math.pi / 0.05
        fade = min(1.0, (abs(v.x) - 0.07) / 0.02) * min(1.0, (0.83 - v.z) / 0.05)
        d += n * fade * (0.0042 * max(0.0, math.sin(ph)) - 0.0016)
    if abs(v.x) < 0.03 and v.z > 0.8 and -0.3 < v.y < 0.66:                    # vertebrae
        d += n * 0.009 * max(0.0, math.sin(v.y * 2 * math.pi / 0.048)) ** 2
    if 0.24 < v.y < 0.44 and v.z < 0.68:                                        # sunken belly
        d -= n * 0.012
    for w in WOUNDS:                                                            # torn pits
        dd = (v - w).length
        if dd < 0.03:
            d -= n * 0.007 * (1 - dd / 0.03)
    if v.z < 0.6:                                                               # long sinews down the limbs
        d += n * 0.0022 * noise.noise(V(v.x * 70, v.y * 70, v.z * 9))
    return d


def snarl(v, n):
    rel = v - HC
    d = n * (noise.noise(v * 30.0) * 0.0018 + noise.noise(v * 70.0) * 0.0008)
    if -0.24 < rel.y < -0.12 and rel.z > 0.0:                                   # snarl folds over the muzzle
        w = rel.y * 260 + noise.noise(v * 25) * 2.5
        d += n * 0.003 * max(0.0, math.sin(w)) ** 3 * min(1.0, rel.z / 0.015)
    if -0.09 < rel.y < -0.04 and rel.z > 0.03:                                  # furrowed brow
        d += n * 0.002 * math.sin(rel.x * 300)
    return d


# ------------------------------------------------------------------ hard pieces
def crystal_bm(bm, base, d, L, rb, r):
    """A faceted ice crystal: an irregular 5-6 sided prism with a pyramid tip, slightly twisted."""
    sides = r.choice((5, 6, 6))
    d = d.normalized()
    t1 = d.orthogonal().normalized(); t2 = d.cross(t1)
    shaft = L * r.uniform(0.55, 0.7)
    tw = r.uniform(-0.3, 0.3)
    rings = []
    for k, (h, scale) in enumerate(((0.0, 1.0), (shaft * 0.5, 0.95 + r.uniform(-0.05, 0.08)), (shaft, 0.82))):
        ring = []
        for j in range(sides):
            a = 2 * math.pi * j / sides + tw * h / max(shaft, 1e-4)
            rr = rb * scale * r.uniform(0.85, 1.12)
            ring.append(bm.verts.new(base + d * h + (t1 * math.cos(a) + t2 * math.sin(a)) * rr))
        rings.append(ring)
    tip = bm.verts.new(base + d * L + (t1 * r.uniform(-1, 1) + t2 * r.uniform(-1, 1)) * rb * 0.25)
    for r0, r1 in zip(rings, rings[1:]):
        for j in range(sides):
            bm.faces.new([r0[j], r0[(j + 1) % sides], r1[(j + 1) % sides], r1[j]])
    for j in range(sides):
        bm.faces.new([rings[-1][j], rings[-1][(j + 1) % sides], tip])
    bm.faces.new(list(reversed(rings[0])))


def cone_bm(bm, base, tip, r0, bend=None, sides=6, rings=3):
    d = tip - base
    t1 = d.normalized().orthogonal().normalized(); t2 = d.normalized().cross(t1)
    loops = []
    for k in range(rings):
        t = k / rings
        c = base + d * t + (Vector(bend) * math.sin(math.pi * t * 0.5) * t if bend is not None else V(0, 0, 0))
        rr = r0 * (1 - t) ** 0.8
        loops.append([bm.verts.new(c + (t1 * math.cos(2 * math.pi * j / sides) + t2 * math.sin(2 * math.pi * j / sides)) * rr) for j in range(sides)])
    tipv = bm.verts.new(tip + (Vector(bend) if bend is not None else V(0, 0, 0)))
    for l0, l1 in zip(loops, loops[1:]):
        for j in range(sides):
            bm.faces.new([l0[j], l0[(j + 1) % sides], l1[(j + 1) % sides], l1[j]])
    for j in range(sides):
        bm.faces.new([loops[-1][j], loops[-1][(j + 1) % sides], tipv])
    bm.faces.new(list(reversed(loops[0])))


def snap_crystals(body_obs):
    """Seat each crystal on the real surface: cast down onto the body/head, push 2 cm in."""
    trees = []
    for ob in body_obs:
        bm = bmesh.new(); bm.from_mesh(ob.data); bm.transform(ob.matrix_world)
        trees.append((BVHTree.FromBMesh(bm), bm))
    out = []
    for p, d, L, rb in CRYSTALS:
        best = None
        for tree, _ in trees:
            if p.z > 0.8:                                                        # on the back: drop onto the top
                hit = tree.ray_cast(p + V(0, 0, 0.25), V(0, 0, -1), 0.6)
                if hit[0] is not None and (best is None or hit[0].z > best.z):
                    best = hit[0]
            else:                                                                # elbows, hips: nearest skin
                q = tree.find_nearest(p)
                if q[0] is not None and (best is None or (q[0] - p).length < (best - p).length):
                    best = q[0]
        base = (best if best is not None else p) - d * 0.02
        out.append((base, d, L, rb))
    for _, bm in trees:
        bm.free()
    return out


SPIKES = []


def build_spikes():
    global SPIKES
    SPIKES = snap_crystals([PARTS["Body"][0], PARTS["Head"][0]])
    bm = bmesh.new()
    r = random.Random(3)
    for base, d, L, rb in SPIKES:
        crystal_bm(bm, base, d, L + 0.02, rb, r)
        if L > 0.14 and r.random() < 0.6:                                        # a smaller crystal leaning off the big ones
            d2 = (d + d.orthogonal().normalized() * r.uniform(0.35, 0.6)).normalized()
            crystal_bm(bm, base + d * 0.01, d2, L * r.uniform(0.35, 0.5), rb * 0.6, r)
    ob = H.obj_from_bm(bm, "Spikes")
    for p in ob.data.polygons:
        p.use_smooth = False
    add("Spikes", ob, "ice")


def build_teeth():
    bm_up, bm_lo = bmesh.new(), bmesh.new()
    r = random.Random(11)
    C = HC
    for x in (-1, 1):
        for k in range(8):
            t = k / 7
            y = -0.075 - 0.185 * t
            half = 0.042 - 0.026 * t
            canine = k == 6
            L = 0.044 if canine else r.uniform(0.016, 0.034) * (1.25 if k in (3, 4) else 1.0)
            base = C + V(x * half, y, -0.056 - 0.006 * t)
            tip = base + V(x * r.uniform(-0.004, 0.004), r.uniform(0.0, 0.008), -L)
            cone_bm(bm_up, base, tip, 0.0085 if canine else 0.0065, bend=V(0, 0.006, 0), sides=5)
            if k < 7:                                                            # along the top of the mandible
                tl = k / 6
                L2 = r.uniform(0.016, 0.03) * (1.35 if k == 5 else 1.0)
                b2 = C + V(x * (0.046 - 0.022 * tl), -0.04 - 0.17 * tl, -0.06 - 0.016 * tl)
                t2 = b2 + V(x * r.uniform(-0.004, 0.004), r.uniform(-0.006, 0.0), L2)
                cone_bm(bm_lo, jaw_open(b2), jaw_open(t2), 0.0075 if k == 5 else 0.006, sides=5)
    for x in (-0.012, 0.0, 0.012):                                               # incisors
        b = C + V(x, -0.27, -0.056)
        cone_bm(bm_up, b, b + V(0, -0.002, -0.016), 0.0045, sides=5)
    ob = H.obj_from_bm(bm_up, "TeethUpper"); add("TeethUpper", ob, "teeth")
    ob = H.obj_from_bm(bm_lo, "TeethLower"); add("TeethLower", ob, "teeth")
    # the inside of the mouth: dark wet flesh filling the gape
    s = H.Sculpt("Mouth", res=0.003)
    s.ellipsoid(C + V(0, -0.14, -0.066), (0.03, 0.12, 0.016))                  # palate
    s.ellipsoid(jaw_open(C + V(0, -0.12, -0.084)), (0.026, 0.1, 0.012))        # tongue on the floor of the mouth
    s.ellipsoid(C + V(0, -0.05, -0.095), (0.036, 0.06, 0.04))                   # throat: no daylight through the gape
    add("Mouth", s.mesh("Mouth"), "mouth")
    for x in (-1, 1):
        e = H.Sculpt("Eye_" + ("L" if x > 0 else "R"), res=0.002)
        e.ball(C + V(x * 0.039, -0.088, 0.015), 0.0078)
        add("Eye_" + ("L" if x > 0 else "R"), e.mesh(), "eye")


def build_claws():
    for side, x in SIDES:
        bm = bmesh.new()
        for tip, d in FINGER_TIPS[side]:
            base = tip + V(0, 0, 0.004) + d * 0.004
            hd = V(d.x, d.y, 0).normalized() if V(d.x, d.y, 0).length > 1e-3 else V(0, -1, 0)
            cone_bm(bm, base, base + (hd * 0.95 + V(0, 0, -0.22)).normalized() * 0.034, 0.007, bend=V(0, 0, -0.004), sides=5)
        for tip, d in TOE_TIPS[side]:
            base = tip + V(0, 0, 0.004) + d * 0.004
            cone_bm(bm, base, base + V(0, -0.9, -0.35).normalized() * 0.026, 0.0065, bend=V(0, 0, -0.006), sides=5)
        add("Claws_" + side, H.obj_from_bm(bm, "Claws_" + side), "claw")


def band(bm, a, b, t, r, width, tilt=0.0, phase=0.0, segs=32, wobble=0.004):
    """A cloth strip round the limb segment a->b at t (radius r), its plane tilted by `tilt` radians."""
    ax = (b - a).normalized()
    c = a.lerp(b, t)
    t1 = ax.orthogonal().normalized(); t2 = ax.cross(t1)
    top, bot = [], []
    for j in range(segs):
        ang = 2 * math.pi * j / segs
        radial = t1 * math.cos(ang) + t2 * math.sin(ang)
        p = c + radial * r + ax * math.sin(ang + phase) * tilt * r
        p += radial * noise.noise(p * 50) * wobble
        top.append(bm.verts.new(p + ax * width / 2)); bot.append(bm.verts.new(p - ax * width / 2))
    for j in range(segs):
        k = (j + 1) % segs
        bm.faces.new([bot[j], bot[k], top[k], top[j]])


def flap(bm, top_center, across, width, length, r, cols=6, rows=8):
    """A torn strip of cloth hanging down from top_center, ragged bottom edge."""
    across = across.normalized()
    grid = []
    cut = [length * r.uniform(0.55, 1.0) for _ in range(cols + 1)]
    for i in range(rows + 1):
        row = []
        for j in range(cols + 1):
            u = (j / cols - 0.5) * width
            v = i / rows
            z = -min(v * length, cut[j])
            p = top_center + across * u * (1 - 0.25 * v) + V(0, 0, z)
            p += V(0, 1, 0) * 0.012 * math.sin(v * 3 + j) + V(0, 0, 0) + V(0.0, 0.0, 0.0)
            p += across.cross(V(0, 0, 1)) * noise.noise(p * 40) * 0.006
            row.append(bm.verts.new(p))
        grid.append(row)
    for i in range(rows):
        for j in range(cols):
            bm.faces.new([grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]])


def shrink_to(ob, target, offset):
    m = ob.modifiers.new("Wrap", "SHRINKWRAP"); m.target = target; m.offset = offset
    m.wrap_method = "NEAREST_SURFACEPOINT"; m.wrap_mode = "OUTSIDE_SURFACE"
    H.apply_mods(ob)


def build_rags():
    body = PARTS["Body"][0]
    r = random.Random(5)
    for side, x in SIDES:
        bm = bmesh.new()
        n = 4 if side == "L" else 3
        for k in range(n):
            t = 0.42 + k * 0.13 + r.uniform(-0.03, 0.03)
            band(bm, EL[side], WR[side], t, 0.04, 0.03, tilt=r.uniform(0.25, 0.5) * (1 if k % 2 else -1), phase=r.uniform(0, 6))
        ob = H.obj_from_bm(bm, "Wrap_" + side)
        shrink_to(ob, body, 0.004)
        H.solidify(ob, 0.004, 1.0, min_faces=0)
        m = ob.modifiers.new("Sub", "SUBSURF"); m.levels = 1; H.apply_mods(ob)
        add("Wrap_" + side, ob, "cloth")
    # torn cloth hanging off the left forearm, and a rag round the right thigh with a tatter
    bm = bmesh.new()
    flap(bm, EL["L"].lerp(WR["L"], 0.45) + V(0.03, 0.035, 0.0), V(0.3, 1, 0), 0.06, 0.13, r)
    ob = H.obj_from_bm(bm, "Flap"); H.solidify(ob, 0.003, 0.0, min_faces=0); add("Flap", ob, "cloth")
    bm = bmesh.new()
    for k, t in enumerate((0.38, 0.55)):
        band(bm, HIP["R"], KN["R"], t, 0.08, 0.045, tilt=0.35 * (1 if k else -1), phase=1.3 + k)
    ob = H.obj_from_bm(bm, "ThighRag"); shrink_to(ob, body, 0.005); H.solidify(ob, 0.004, 1.0, min_faces=0)
    m = ob.modifiers.new("Sub", "SUBSURF"); m.levels = 1; H.apply_mods(ob)
    add("ThighRag", ob, "cloth")
    bm = bmesh.new()
    flap(bm, HIP["R"].lerp(KN["R"], 0.6) + V(-0.07, 0.0, 0.0), V(0.2, 1, 0), 0.07, 0.11, r)
    ob = H.obj_from_bm(bm, "ThighFlap"); H.solidify(ob, 0.003, 0.0, min_faces=0); add("ThighFlap", ob, "cloth")


def build_body():
    s = H.Sculpt("Body", res=0.0055)
    body_forms(s)
    ob = s.mesh("Body")
    H.smooth(ob, 2, 0.5)
    H.displace(ob, gaunt)
    add("Body", ob, "skin")
    s = H.Sculpt("Head", res=0.003)
    head_forms(s)
    ob = s.mesh("Head")
    H.smooth(ob, 2, 0.5)
    H.displace(ob, snarl)
    add("Head", ob, "skin")
    for side, x in SIDES:
        s = H.Sculpt("Hand_" + side, res=0.0026)
        hand_forms(s, side, x)
        ob = s.mesh("Hand_" + side); H.smooth(ob, 1, 0.4)
        H.displace(ob, lambda c, n: n * noise.noise(c * 60) * 0.0012)
        add("Hand_" + side, ob, "skin")
        s = H.Sculpt("Paw_" + side, res=0.0026)
        paw_forms(s, side, x)
        ob = s.mesh("Paw_" + side); H.smooth(ob, 1, 0.4)
        add("Paw_" + side, ob, "skin")


# ------------------------------------------------------------------ paint
def paints():
    P = {}
    p = H.Paint("skin").base((0.62, 0.43, 0.37), (0.80, 0.62, 0.53), scale=4.5, contrast=0.6, fine=0.2)
    p.layer(p.mask_noise(1.5, 0.35), (0.56, 0.38, 0.35), 0.5)                      # blotchy, feverish flesh
    p.layer(p.mask_noise(3.0, 0.26), (0.36, 0.24, 0.28), 0.75)                     # bruising
    p.layer(p.mask_noise(8.0, 0.14), (0.24, 0.15, 0.16), 0.7)                      # dark necrotic spots
    p.layer(p.mask_below(0.0, 0.22, 0.06), (0.36, 0.26, 0.22), 0.75)               # filthy hands and feet
    ridge = [V(0, y, topline(y) - 0.01) for y in np.arange(-0.30, 0.64, 0.03)]
    p.layer(p.mask_near(ridge, 0.09, 0.85, 0.6, 7.0), (0.62, 0.27, 0.25), 0.75)   # inflamed skin along the ice ridge
    p.layer(p.mask_near(ridge, 0.04, 0.7, 0.6, 12.0), (0.48, 0.10, 0.09), 0.9)    # raw, split flesh at the roots
    bases = [b for b, d, L, rb in SPIKES]
    p.layer(p.mask_near(bases, 0.026, 0.6, 0.5, 20.0), (0.40, 0.07, 0.06), 0.9)
    r = random.Random(17)
    gashes = []
    for w in WOUNDS:                                                                # torn gashes, not round spots
        d = V(r.uniform(-0.3, 0.3), r.uniform(-1, 1), r.uniform(-0.6, 0.6)).normalized()
        gashes += [w + d * (k - 1.5) * 0.016 for k in range(4)]
    p.layer(p.mask_near(gashes, 0.03, 0.85, 0.6, 15.0), (0.60, 0.28, 0.25), 0.5)
    p.layer(p.mask_near(gashes, 0.013, 0.5, 0.5, 30.0), (0.38, 0.05, 0.05), 0.95)
    mouth = [HC + V(0, -0.22, -0.07), jaw_open(HC + V(0, -0.22, -0.09)), HC + V(0.04, -0.1, -0.07), HC + V(-0.04, -0.1, -0.07)]
    p.layer(p.mask_near(mouth, 0.06, 0.6, 0.45, 12.0), (0.40, 0.06, 0.05), 0.85)  # blood round the jaws
    p.layer(p.mask_near([jaw_open(HC + V(0.01, -0.22, -0.11)), V(0, -0.30, 0.62), V(0.02, -0.25, 0.55)], 0.05, 0.7, 0.5, 18.0),
            (0.38, 0.05, 0.05), 0.8)                                               # drool down the throat
    tips = [t for side, _ in SIDES for t, _ in FINGER_TIPS[side]]
    p.layer(p.mask_near(tips, 0.035, 0.6, 0.4), (0.35, 0.07, 0.06), 0.85)         # bloody fingers
    p.layer(p.mask_near([HC + V(x * 0.045, -0.088, 0.018) for x in (-1, 1)], 0.02, 0.6, 0.2), (0.30, 0.10, 0.10), 0.8)   # raw sockets
    p.skin_texture(1.0, crease=(0.30, 0.17, 0.16), vein=(0.38, 0.26, 0.40), amount=0.7, veins=0.55)
    p.crust(p.mask_near(ridge + gashes, 0.045, 0.7, 0.6, 10.0), 60.0, (0.26, 0.07, 0.05), 0.8)   # scabs round the roots and tears
    P["skin"] = p.cavity(0.65, 0.3).done()
    p = H.Paint("ice").base((0.22, 0.34, 0.46), (0.50, 0.63, 0.73), scale=14, contrast=0.7, fine=0.25)
    p.layer(p.mask_noise(5.0, 0.25), (0.24, 0.36, 0.48), 0.6)                      # deep blue inside
    p.layer(p.mask_near([b for b, d, L, rb in SPIKES], 0.03, 0.5, 0.3), (0.42, 0.18, 0.18), 0.6)   # blood drawn up the base
    p.fractures(22.0, (0.74, 0.85, 0.93), 0.3, 0.6)
    p.layer(p.mask_noise(9.0, 0.18), (0.66, 0.78, 0.88), 0.35)                      # frost
    P["ice"] = p.cavity(0.25, 0.0).done()
    p = H.Paint("teeth").base((0.56, 0.44, 0.22), (0.80, 0.70, 0.42), scale=40, contrast=0.6)
    p.layer(p.mask_noise(9.0, 0.2), (0.42, 0.30, 0.14), 0.6)
    p.layer(p.mask_noise(14.0, 0.15), (0.40, 0.08, 0.06), 0.6)
    p.streaks(90.0, "Z", (0.36, 0.26, 0.12), 0.4, 0.5)
    P["teeth"] = p.cavity(0.6, 0.3).done()
    P["claw"] = H.Paint("claw").base((0.14, 0.11, 0.10), (0.32, 0.26, 0.22), scale=30, contrast=0.6).streaks(80.0, "Y", (0.08, 0.06, 0.05), 0.4).done()
    P["eye"] = H.Paint("eye").base((0.22, 0.03, 0.03), (0.62, 0.12, 0.08), scale=60, contrast=0.8).done()
    P["mouth"] = H.Paint("mouth").base((0.24, 0.05, 0.05), (0.45, 0.12, 0.10), scale=20, contrast=0.6).streaks(40.0, "Y", (0.16, 0.03, 0.03), 0.4, 0.8).done()
    p = H.Paint("cloth").base((0.30, 0.28, 0.19), (0.47, 0.42, 0.29), scale=10, contrast=0.55)
    p.layer(p.mask_noise(4.0, 0.2), (0.25, 0.19, 0.13), 0.6)
    p.layer(p.mask_noise(9.0, 0.12), (0.38, 0.08, 0.06), 0.6)                       # old blood
    p.weave(40.0, (0.18, 0.16, 0.10), 0.35, 0.7)
    p.layer(p.ridges(25.0, 0.015), (0.62, 0.56, 0.40), 0.35)                         # pulled threads
    P["cloth"] = p.cavity(0.6, 0.25).done()
    p = H.Paint("strap").base((0.20, 0.13, 0.08), (0.34, 0.23, 0.14), scale=12, contrast=0.6)
    p.layer(p.stripes(1, 0.03, 0.003), (0.14, 0.09, 0.06), 0.5)
    P["strap"] = p.cavity(0.5, 0.3).done()
    return P


def preview_materials():
    cols = {"skin": (0.72, 0.57, 0.52), "ice": (0.62, 0.74, 0.82), "teeth": (0.76, 0.66, 0.38), "claw": (0.2, 0.15, 0.13),
            "eye": (0.6, 0.2, 0.1), "mouth": (0.3, 0.06, 0.06), "cloth": (0.42, 0.38, 0.26), "strap": (0.3, 0.2, 0.12)}
    mats = {}
    for k, c in cols.items():
        m = bpy.data.materials.new("prev_" + k); m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = H.lin(c); b.inputs["Roughness"].default_value = 0.75
        mats[k] = m
    for nm, (ob, key) in PARTS.items():
        ob.data.materials.clear(); ob.data.materials.append(mats[key])


QC_HEIGHT = 1.55
CU_SHOTS = [(HC + V(0, -0.08, -0.02), 0.36, 0, 5), (HC + V(0, -0.08, -0.02), 0.36, 70, 10), (HC + V(0, -0.05, 0.0), 0.36, 300, 35),
            (KNU["L"] + V(0, 0.02, 0.05), 0.24, 60, 15), (BALL["L"] + V(0, 0, 0.05), 0.22, 90, 10), (V(0, 0.08, 0.95), 0.8, 330, 45)]


def stage_high():
    H.reset()
    build_body()
    build_spikes(); build_teeth(); build_claws(); build_rags()
    P = paints()
    for nm, (ob, key) in PARTS.items():
        ob.data.materials.clear(); ob.data.materials.append(P[key])
        if key not in ("ice",):
            for poly in ob.data.polygons:
                poly.use_smooth = True
    tris = sum(sum(len(p.vertices) - 2 for p in ob.data.polygons) for ob, _ in PARTS.values())
    print("high parts", len(PARTS), "tris", tris, "crystals", len(SPIKES))
    json.dump({"spikes": [[list(b), list(d), L, rb] for b, d, L, rb in SPIKES],
               "fingers": {s: [list(t) for t, _ in FINGER_TIPS[s]] for s, _ in SIDES}}, open(OUT + "_layout.json", "w"))
    bpy.ops.wm.save_as_mainfile(filepath=OUT + "_high.blend")
    if "--paintqc" in sys.argv:                                                 # the real paint (emission) up close
        H.closeups(OUT + "_paint_cu.png", CU_SHOTS)
    if "--qc" in sys.argv:
        preview_materials()
        objs = [o for o, _ in PARTS.values()]
        H.qc_renders(objs, OUT + "_high_qc.png", height=QC_HEIGHT)
        H.closeups(OUT + "_high_cu.png", CU_SHOTS)


# ------------------------------------------------------------------ stage: game mesh
BUDGET = {"Body": 5000, "Head": 2300, "Hand_L": 420, "Hand_R": 420, "Paw_L": 260, "Paw_R": 260, "Mouth": 120}
DECIMATE = {"TeethUpper": 420, "TeethLower": 300, "Eye_L": 50, "Eye_R": 50, "Claws_L": 300, "Claws_R": 300,
            "Wrap_L": 520, "Wrap_R": 420, "Flap": 160, "ThighRag": 360, "ThighFlap": 160, "Mouth": 160}
KEEP = {"Spikes"}                                       # already low: faceted prisms
RIGID = {"Spikes", "TeethUpper", "TeethLower", "Eye_L", "Eye_R", "Claws_L", "Claws_R"}


def stage_low():
    bpy.ops.wm.open_mainfile(filepath=OUT + "_high.blend")
    highs = [o for o in bpy.data.objects if o.type == "MESH"]
    lows = []
    for h in highs:
        nm = h.name
        if nm in KEEP:
            lo = h.copy(); lo.data = h.data.copy(); lo.name = nm + "_low"; bpy.context.scene.collection.objects.link(lo)
        elif nm in BUDGET and nm not in DECIMATE:
            lo = H.retopo(h, BUDGET[nm], nm + "_low")
        else:
            lo = H.decimate(h, DECIMATE.get(nm, 120), nm + "_low")
        at = lo.data.attributes.new("rigid", "INT", "POINT")
        at.data.foreach_set("value", [1 if nm in RIGID else 0] * len(lo.data.vertices))
        lows.append(lo)
        print("low", nm, len(h.data.polygons), "->", sum(len(p.vertices) - 2 for p in lo.data.polygons), "tris")
    H.select_only(lows[0])
    for lo in lows:
        lo.select_set(True)
    bpy.context.view_layer.objects.active = lows[0]
    bpy.ops.object.join()
    game = bpy.context.view_layer.objects.active
    game.name = "Feral"
    for p in game.data.polygons:
        p.use_smooth = True
    tris = sum(len(p.vertices) - 2 for p in game.data.polygons)
    print("game mesh", len(game.data.vertices), "verts", tris, "tris")
    H.bake_to_low(highs, game, size=2048, cage=0.02, ao=0.55, path=OUT + "_paint_2k.png")
    # crystals keep their facets
    rig_attr = game.data.attributes["rigid"]
    rig_v = np.zeros(len(game.data.vertices), np.int32); rig_attr.data.foreach_get("value", rig_v)
    ice_faces = 0
    for p in game.data.polygons:
        if all(rig_v[v] for v in p.vertices) and p.center.z > 0.55 and not (-0.7 < p.center.y < -0.3 and p.center.z < 0.84):
            p.use_smooth = False; ice_faces += 1
    print("flat-shaded crystal faces", ice_faces)
    for h in highs:
        h.hide_render = True; h.hide_set(True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT + "_low.blend")
    if "--qc" in sys.argv:
        H.qc_renders([game], OUT + "_low_qc.png", height=QC_HEIGHT)
        H.closeups(OUT + "_low_cu.png", CU_SHOTS)


if STAGE == "high":
    stage_high()
elif STAGE == "low":
    stage_low()


# ------------------------------------------------------------------ stage: rig, weights, clips, export
UP, FWD, BACK = (0, 0, 1), (0, -1, 0), (0, 1, 0)
JAW_TIP = jaw_open(HC + V(0, -0.238, -0.09))


def bones_spec():
    B = [
        ("Hips", (0, 0.56, 0.72), (0, 0.36, 0.80), None, UP),
        ("Spine", (0, 0.36, 0.80), (0, 0.14, 0.85), "Hips", UP),
        ("Chest", (0, 0.14, 0.85), (0, -0.10, 0.84), "Spine", UP),
        ("Neck", (0, -0.10, 0.83), (0, -0.33, 0.86), "Chest", UP),
        ("Head", (0, -0.33, 0.86), (0, -0.70, 0.84), "Neck", UP),
        ("Jaw", tuple(HINGE), tuple(JAW_TIP), "Head", UP),
    ]
    for s, x in SIDES:
        arm_z = (x * 0.4, 1, 0)
        B += [
            (f"Scapula_{s}", (x * 0.04, -0.02, 0.86), tuple(SH[s]), "Chest", FWD),
            (f"UpperArm_{s}", tuple(SH[s]), tuple(EL[s]), f"Scapula_{s}", arm_z),
            (f"ForeArm_{s}", tuple(EL[s]), tuple(WR[s]), f"UpperArm_{s}", arm_z),
            (f"Hand_{s}", tuple(WR[s]), tuple(KNU[s]), f"ForeArm_{s}", UP),
            (f"Fingers_{s}", tuple(KNU[s]), tuple(KNU[s] + V(0, -0.10, -0.012)), f"Hand_{s}", UP),
            (f"Thigh_{s}", tuple(HIP[s]), tuple(KN[s]), "Hips", FWD),
            (f"Shin_{s}", tuple(KN[s]), tuple(HK[s]), f"Thigh_{s}", FWD),
            (f"Meta_{s}", tuple(HK[s]), tuple(BALL[s]), f"Shin_{s}", FWD),
            (f"Toes_{s}", tuple(BALL[s]), tuple(TOE[s]), f"Meta_{s}", UP),
        ]
    return B


def build_proxy():
    s = H.Sculpt("Proxy", res=0.011)
    body_forms(s, coarse=True)
    head_forms(s, coarse=True)
    for side, x in SIDES:
        hand_forms(s, side, x, coarse=True)
        paw_forms(s, side, x, coarse=True)
    return s.mesh("Proxy")


def rigid_islands(game, proxy):
    """Crystals, teeth, claws and eyes: each island takes the weights of its vertex nearest the body."""
    me = game.data
    rv = np.zeros(len(me.vertices), np.int32); me.attributes["rigid"].data.foreach_get("value", rv)
    bm = bmesh.new(); bm.from_mesh(proxy.data); tree = BVHTree.FromBMesh(bm); bm.free()
    adj = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        adj[a].append(b); adj[b].append(a)
    seen = np.zeros(len(me.vertices), bool)
    n_isl = 0
    for i in range(len(me.vertices)):
        if not rv[i] or seen[i]:
            continue
        isl, stack = [], [i]
        seen[i] = True
        while stack:
            v = stack.pop(); isl.append(v)
            for w in adj[v]:
                if rv[w] and not seen[w]:
                    seen[w] = True; stack.append(w)
        best = min(isl, key=lambda v: tree.find_nearest(me.vertices[v].co)[3])
        ws = [(g.group, g.weight) for g in me.vertices[best].groups]
        for v in isl:
            for g in list(me.vertices[v].groups):
                game.vertex_groups[g.group].remove([v])
            for gi, w in ws:
                game.vertex_groups[gi].add([v], w, "REPLACE")
        n_isl += 1
    print("rigid islands", n_isl)


def stage_rig():
    import creature_kit as K
    bpy.ops.wm.open_mainfile(filepath=OUT + "_low.blend")
    game = bpy.data.objects["Feral"]
    for o in list(bpy.data.objects):
        if o is not game:
            bpy.data.objects.remove(o, do_unlink=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    rig = K.Rig("FeralRig", bones_spec())
    proxy = build_proxy()
    print("bone heat on proxy:", H.heat_weights(rig.ob, proxy))
    proxy.parent = None
    H.transfer_weights(proxy, game, rig.ob, smooth_iters=2)
    rigid_islands(game, proxy)
    bpy.data.objects.remove(proxy, do_unlink=True)
    clips = make_clips(K, rig)
    ground_report(rig, game, clips)
    view = view_box(rig, game, clips)
    for img in bpy.data.images:
        if img.size[0] > 1024:
            img.scale(1024, 1024)
    for img in bpy.data.images:                                                  # self-contained .blend
        if img.source == "FILE" or img.is_dirty:
            img.pack()
    bpy.ops.wm.save_as_mainfile(filepath=OUT + "_mutant.blend")
    K.export(rig, OUT, {
        "fps_src": 24, "clips": {k: k for k in clips}, "idle_loop_src": [0, 48], "height_m": 1.0, "exposure": 1.0,
        "creature": "feral", "lengths": clips, "view": view, "walk_v": WALK_V, "bite_hit": BITE_HIT,
    })
    print("exported", OUT, clips, view)
    if "--qc" in sys.argv:
        from PIL import Image
        frames = [("idle", 20), ("walk", 0), ("walk", 5), ("walk", 10), ("bite", 6), ("bite", 11), ("hit", 4), ("death", 36)]
        for clip, f in frames:
            rig.ob.animation_data.action = bpy.data.actions[clip]
            sc.frame_set(f)
            H.qc_renders([game], f"/tmp/fer_pose_{clip}_{f}.png", height=QC_HEIGHT, views=(("side", 90),), game=True)
        ims = [Image.open(f"/tmp/fer_pose_{c}_{f}.png") for c, f in frames]
        w, h = ims[0].width // 4, ims[0].height // 2                            # each half keeps its aspect
        sheet = Image.new("RGB", (w * len(ims), h * 2))
        for i, im in enumerate(ims):
            sheet.paste(im.crop((0, 0, im.width // 2, im.height)).resize((w, h)), (i * w, 0))
            sheet.paste(im.crop((im.width // 2, 0, im.width, im.height)).resize((w, h)), (i * w, h))
        sheet.save(OUT + "_poses.png")


def ground_report(rig, game, clips):
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    for name, n in clips.items():
        rig.ob.animation_data.action = bpy.data.actions[name]
        lows = []
        for f in range(0, n + 1, 2):
            sc.frame_set(f)
            me = game.evaluated_get(dg).to_mesh()
            lows.append(min(v.co.z for v in me.vertices))
            game.evaluated_get(dg).to_mesh_clear()
        print("ground", name, " ".join(f"{z:+.3f}" for z in lows))


def view_box(rig, game, clips):
    """The viewport the puppet renders into: room for every frame of every clip at any facing."""
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    PPM, e, m = 165.0, math.radians(47.0), 12
    res = {}
    for big, names in ((False, [c for c in clips if c != "death"]), (True, list(clips))):
        r = top = 0.0
        for name in names:
            rig.ob.animation_data.action = bpy.data.actions[name]
            for f in range(0, clips[name] + 1, 3):
                sc.frame_set(f)
                me = game.evaluated_get(dg).to_mesh()
                co = np.array([v.co[:] for v in me.vertices])
                game.evaluated_get(dg).to_mesh_clear()
                r = max(r, float(np.sqrt(co[:, 0] ** 2 + co[:, 1] ** 2).max())); top = max(top, float(co[:, 2].max()))
        W = int(math.ceil(2 * r * PPM)) + 2 * m
        above = (r * math.sin(e) + top * math.cos(e)) * PPM
        Hh = int(math.ceil(above + r * math.sin(e) * PPM)) + 2 * m
        res[big] = (W, Hh, int(math.ceil(above)) + m)
    return {"w": res[False][0], "h": res[False][1], "foot_y": res[False][2],
            "big_w": res[True][0], "big_h": res[True][1], "big_foot_y": res[True][2]}


WALK_N, WALK_V, DUTY = 20, 0.04, 0.56
BITE_N, BITE_HIT = 22, 11


def make_clips(K, rig):
    STRIDE = WALK_V * DUTY * WALK_N
    L_META = rig.len["Meta_L"]; L_HAND = rig.len["Hand_L"]
    META_DIR = (BALL["L"] - HK["L"]).normalized()
    HAND_DIR = (KNU["L"] - WR["L"]).normalized()
    clips = {}

    def limbs(P, feet, hands):
        """feet / hands: ground contacts (ball of the foot, knuckles) per side; *_dir overrides."""
        P._feet, P._hands = feet, hands
        for s, x in SIDES:
            md = feet.get(s + "_dir", META_DIR)
            P.chain(f"Thigh_{s}", f"Shin_{s}", feet[s] - md * L_META, Vector((x * 0.15, -1, -0.2)), f"Meta_{s}", md, FWD)
            hd = hands.get(s + "_dir", HAND_DIR)
            P.chain(f"UpperArm_{s}", f"ForeArm_{s}", hands[s] - hd * L_HAND, Vector((x * 0.5, 1, 0.1)), f"Hand_{s}", hd, UP)

    def planted():
        return ({s: BALL[s].copy() for s, _ in SIDES}, {s: KNU[s].copy() for s, _ in SIDES})

    def jaw(P, close):
        """close: 0 = as sculpted (open 26 degrees), 1 = shut, negative = wider."""
        P.rot("Jaw", x=JAW_OPEN * close)

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
        P.root("Hips", offset=(0, 0.01 * math.sin(t * 2 * math.pi), -0.015 + 0.006 * br), rx=-2)
        P.rot("Spine", x=-2 + 1.5 * br); P.rot("Chest", x=2 + 2 * br, z=look * 0.15)
        P.rot("Neck", x=-12 + 4 * math.sin(t * 4 * math.pi), z=look * 0.4)
        P.rot("Head", x=4 + 6 * math.sin(t * 2 * math.pi * 6) * (0.3 < t < 0.45), z=look * 0.4, y=-6 * math.sin(t * 2 * math.pi))
        jaw(P, 0.6 - 0.35 * max(0.0, math.sin(t * 2 * math.pi * 8)) * (0.7 < t < 0.9))
        for s, x in SIDES:
            P.rot(f"Fingers_{s}", x=3 + 5 * max(0.0, math.sin(t * 2 * math.pi * 2 + x)))   # claws lift and tap
        limbs(P, *planted())

    # walk: 20 frames, 0.04 m a frame (about 1 m/s): diagonal pairs, the back rolling, head low and steady
    def walk(P, f, n):
        t = f / n
        ph = {"hL": 0.0, "fR": 0.08, "hR": 0.5, "fL": 0.58}
        P.root("Hips", offset=(0, 0, -0.03 + 0.014 * math.cos(t * 4 * math.pi)), rx=-3, ry=4 * math.sin(t * 2 * math.pi),
               rz=5 * math.sin(t * 2 * math.pi))
        P.rot("Spine", z=-6 * math.sin(t * 2 * math.pi), x=1)
        P.rot("Chest", z=-7 * math.sin(t * 2 * math.pi + 0.6), x=3 + 2 * math.cos(t * 4 * math.pi), y=-5 * math.sin(t * 2 * math.pi))
        P.rot("Neck", x=-16, z=8 * math.sin(t * 2 * math.pi + 1.2))
        P.rot("Head", x=8 - 3 * math.cos(t * 4 * math.pi), z=4 * math.sin(t * 2 * math.pi + 1.8))
        jaw(P, 0.5 - 0.2 * max(0.0, math.sin(t * 4 * math.pi)))
        feet, hands = {}, {}
        for s, x in SIDES:
            y, z = K.gait(t + ph["h" + s], DUTY, STRIDE, 0.10, BALL[s].y)
            feet[s] = Vector((BALL[s].x, y, BALL[s].z + z))
            if z > 0.005:                                                        # the hind foot folds as it swings
                feet[s + "_dir"] = (META_DIR + Vector((0, 0.7, -0.15)) * (z / 0.1)).normalized()
            y, z = K.gait(t + ph["f" + s], DUTY, STRIDE, 0.12, KNU[s].y)
            hands[s] = Vector((KNU[s].x, y, KNU[s].z + z))
            if z > 0.005:                                                        # the hand curls as it lifts
                hands[s + "_dir"] = (HAND_DIR + Vector((0, 0.5, -0.9)) * (z / 0.12)).normalized()
                P.rot(f"Fingers_{s}", x=-30 * z / 0.12)
        limbs(P, feet, hands)

    # bite: 22 frames - gathers back, lunges with the jaw wide, snaps shut on BITE_HIT, recovers
    def bite(P, f, n):
        back = K.smoothstep(0, 6, f) * (1 - K.smoothstep(7, 10, f))
        lunge = K.smoothstep(7, 11, f) * (1 - K.smoothstep(14, 21, f))
        gape = K.smoothstep(2, 8, f) * (1 - K.smoothstep(9.5, 11, f))
        shut = K.smoothstep(10, 11, f) * (1 - K.smoothstep(14, 20, f))
        P.root("Hips", offset=(0, 0.07 * back - 0.22 * lunge, -0.05 * back + 0.02 * lunge), rx=4 * back - 7 * lunge)
        P.rot("Spine", x=-4 * back + 4 * lunge)
        P.rot("Chest", x=8 * back - 5 * lunge)
        P.rot("Neck", x=-10 + 20 * back - 8 * lunge)
        P.rot("Head", x=6 + 10 * back - 6 * lunge, y=8 * lunge)
        jaw(P, 0.5 - 1.1 * gape + 0.5 * shut)
        feet, hands = planted()
        for s, x in SIDES:
            hands[s] = hands[s] + Vector((0, -0.16 * lunge, 0.07 * lunge * (1 if s == "L" else 0.3)))
            if s == "L":
                hands["L_dir"] = (HAND_DIR + Vector((0, 0.3, -0.5)) * lunge).normalized()
        limbs(P, feet, hands)

    def hit(P, f, n):
        k = K.smoothstep(0, 3, f) * (1 - K.smoothstep(5, 13, f))
        P.root("Hips", offset=(0, 0.06 * k, -0.02 * k), rx=6 * k, ry=-6 * k)
        P.rot("Chest", x=10 * k, z=10 * k)
        P.rot("Neck", x=8 * k, z=-24 * k)
        P.rot("Head", x=10 * k, y=-12 * k)
        jaw(P, 0.5 - 0.6 * k)
        limbs(P, *planted())

    # death: 36 frames - rears, staggers, collapses onto its side, legs draw in, jaw falls open
    def death(P, f, n):
        rear = K.smoothstep(0, 6, f) * (1 - K.smoothstep(8, 14, f))
        fall = K.smoothstep(8, 22, f)
        curl = K.smoothstep(16, 32, f)
        P.root("Hips", offset=(0.10 * fall, 0.04 * rear, -DEATH_DROP * fall + 0.04 * rear), ry=-84 * fall, rx=8 * rear)
        P.rot("Chest", x=14 * rear - 6 * fall, z=8 * fall)
        P.rot("Neck", x=12 * rear - 10 * fall, z=-14 * fall)
        P.rot("Head", x=-10 * curl, z=-10 * fall, y=-14 * fall)
        jaw(P, 0.5 - 0.9 * K.smoothstep(14, 26, f))
        R = P.rig.rest["Hips"]
        W = R @ P.basis["Hips"] @ R.inverted()
        feet, hands = planted()
        for s, x in SIDES:
            a, w = BALL[s], KNU[s]
            a_body = W @ (a + Vector((-x * 0.05, -0.14, 0.12)) * curl)
            w_body = W @ (w + Vector((-x * 0.04, 0.14, 0.16)) * curl)
            feet[s] = a.lerp(a_body, fall); hands[s] = w.lerp(w_body, fall)
            feet[s].z = max(feet[s].z, 0.03); hands[s].z = max(hands[s].z, 0.03)
            feet[s + "_dir"] = (W.to_3x3() @ META_DIR).lerp(META_DIR, 1 - fall).normalized()
            hands[s + "_dir"] = (W.to_3x3() @ HAND_DIR).lerp(HAND_DIR, 1 - fall).normalized()
            P.rot(f"Fingers_{s}", x=-25 * curl)
        limbs(P, feet, hands)

    clip("idle", 48, idle)
    clip("walk", WALK_N, walk)
    clip("bite", BITE_N, bite)
    clip("hit", 14, hit)
    clip("death", 36, death)
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = 0, 48
    return clips


DEATH_DROP = 0.50

if STAGE == "rig":
    stage_rig()
