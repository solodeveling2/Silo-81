"""Infected Human (Tier 1, Firn Strata) for Silo 81: a deranged survivor, still recognizably human.
Reference: source/concepts/enemies/infected_turnaround.jpg (front, side, back, three-quarter).

Built from primitives in code (human_kit.py), following the blockout -> final shape -> retopology ->
detail -> layered paint workflow:
  high meshes: head and neck, hands (five fingers, long dark nails), eyes, teeth, mouth; clothing as its
  own volumes with real thickness: a faded-red parka (open front, flap pockets, ragged hem and cuffs,
  its own hood hanging down the back), a khaki inner hood worn up, an oatmeal sweater, an ochre scarf
  with a long frayed end, patched brown cargo trousers, leather boots with cloth wraps.
  game mesh: QuadriFlow retopology per part (about 20k triangles), one UV atlas, painted colour + AO
  baked from the high meshes (detail lives in the colour; the game's toon shader reads only that).
  rig: humanoid skeleton, bone-heat weights on a closed proxy, transferred to every part.

Stages (each saves a .blend next to OUT so the next can start from it):
  python3 -I infected_human.py OUT --stage high      sculpt + QC renders of the high meshes
  python3 -I infected_human.py OUT --stage low       retopology, UVs, bake, QC renders
  python3 -I infected_human.py OUT --stage rig       skeleton, weights, clips, GLB export, .blend
"""
import sys, os, math, random, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix, Quaternion, noise
from mathutils.bvhtree import BVHTree
import human_kit as H

OUT = sys.argv[1]
STAGE = sys.argv[sys.argv.index("--stage") + 1] if "--stage" in sys.argv else "high"
rng = random.Random(81)
SIDES = (("L", 1), ("R", -1))

# ------------------------------------------------------------------ landmarks (metres, faces -Y)
ARM_DOWN = math.radians(35)                                   # A-pose: arms 35 degrees out from the body
def arm_dir(x):
    return Vector((x * math.sin(ARM_DOWN), 0.0, -math.cos(ARM_DOWN)))
SH = {s: Vector((x * 0.19, 0.0, 1.43)) for s, x in SIDES}     # shoulder joints
EL = {s: SH[s] + arm_dir(x) * 0.29 + Vector((0, 0.012, 0)) for s, x in SIDES}
WR = {s: EL[s] + arm_dir(x) * 0.255 + Vector((0, -0.012, 0)) for s, x in SIDES}
HIP = {s: Vector((x * 0.095, 0.0, 0.92)) for s, x in SIDES}
KN = {s: Vector((x * 0.105, -0.012, 0.50)) for s, x in SIDES}
AN = {s: Vector((x * 0.11, 0.02, 0.085)) for s, x in SIDES}
HC = Vector((0.0, -0.005, 1.635))                             # head centre
NECK0, NECK1 = Vector((0, 0.012, 1.44)), Vector((0, 0.0, 1.56))


def hand_frame(s, x):
    """u: along the hand towards the fingertips, v: towards the thumb (forward), n: out of the palm."""
    u = arm_dir(x).normalized()
    v = Vector((0, -1, 0))
    v = (v - u * v.dot(u)).normalized()
    n = u.cross(v) * x                                          # palm faces the body
    return u, v, n


# ------------------------------------------------------------------ parts
PARTS = {}          # name -> (object, material key)


def add(name, ob, mat):
    ob.name = name
    PARTS[name] = (ob, mat)
    return ob


def build_head():
    s = H.Sculpt("Head", res=0.003, threshold=0.6)
    C = HC
    s.ellipsoid(C + Vector((0, 0.012, 0.02)), (0.074, 0.093, 0.098))               # cranium
    s.ellipsoid(C + Vector((0, -0.046, -0.008)), (0.053, 0.042, 0.072))             # face mass
    s.capsule(C + Vector((-0.044, -0.083, 0.034)), C + Vector((0.044, -0.083, 0.034)), 0.0145)  # brow ridge
    for x in (-1, 1):
        s.ellipsoid(C + Vector((x * 0.05, -0.062, -0.012)), (0.022, 0.02, 0.016))  # cheekbones
        s.capsule(C + Vector((x * 0.052, -0.055, -0.012)), C + Vector((x * 0.068, -0.005, -0.004)), 0.009)
        s.capsule(C + Vector((x * 0.06, 0.0, -0.028)), C + Vector((x * 0.055, -0.004, -0.082)), 0.014)   # jaw ramus
        s.capsule(C + Vector((x * 0.055, -0.004, -0.082)), C + Vector((x * 0.014, -0.074, -0.114)), 0.013)
        s.ellipsoid(C + Vector((x * 0.072, 0.008, -0.004)), (0.009, 0.021, 0.03))  # ears
        s.ellipsoid(C + Vector((x * 0.045, -0.07, -0.058)), (0.02, 0.022, 0.026), stiff=1.2, neg=True)   # hollow cheeks
        s.ellipsoid(C + Vector((x * 0.032, -0.086, 0.011)), (0.017, 0.016, 0.013), neg=True)            # eye sockets
    s.ellipsoid(C + Vector((0, -0.068, -0.046)), (0.04, 0.034, 0.024))             # maxilla
    s.capsule(C + Vector((0, -0.09, 0.024)), C + Vector((0, -0.11, -0.026)), 0.0095)                  # nose bridge
    s.ball(C + Vector((0, -0.107, -0.029)), 0.013)
    for x in (-1, 1):
        s.ball(C + Vector((x * 0.014, -0.098, -0.034)), 0.009)
    s.ball(C + Vector((0, -0.077, -0.112)), 0.02)                                   # chin (jaw hanging open)
    s.ellipsoid(C + Vector((0, -0.096, -0.07)), (0.025, 0.035, 0.02), neg=True)    # the open mouth
    s.capsule(C + Vector((-0.024, -0.094, -0.05)), C + Vector((0.024, -0.094, -0.05)), 0.0055)   # upper lip
    s.capsule(C + Vector((-0.022, -0.087, -0.09)), C + Vector((0.022, -0.087, -0.09)), 0.0062)   # lower lip
    s.capsule(NECK0, C + Vector((0, 0.01, -0.07)), 0.046)                          # neck
    s.ball(Vector((0, -0.036, 1.505)), 0.011)                                       # Adam's apple
    for x in (-1, 1):
        s.capsule(C + Vector((x * 0.055, 0.0, -0.06)), Vector((x * 0.018, -0.04, 1.455)), 0.012)   # neck cords
    ob = s.mesh("Head")
    H.smooth(ob, 4, 0.5)
    H.displace(ob, lambda c, n: n * (noise.noise(c * 60.0) * 0.0008 + noise.noise(c * 160.0) * 0.0003))
    add("Head", ob, "skin")
    # eyes, mouth inside, teeth
    for x in (-1, 1):
        e = H.Sculpt("Eye", res=0.0015)
        e.ball(C + Vector((x * 0.033, -0.073, 0.012)), 0.0125)
        add(f"Eye_{'L' if x > 0 else 'R'}", e.mesh(), "eye")
    m = H.Sculpt("Mouth", res=0.003)
    m.ellipsoid(C + Vector((0, -0.058, -0.068)), (0.026, 0.03, 0.024))
    add("Mouth", m.mesh(), "mouth")
    bm = bmesh.new()
    for row, (z, ang0) in enumerate(((-0.054, 0.0), (-0.086, 0.15))):
        for k in range(9):
            a = math.radians(-62 + k * 15.5 + rng.uniform(-3, 3))
            r = 0.026
            base = C + Vector((math.sin(a) * r, -0.066 - math.cos(a) * r * 0.95, z))
            L = rng.uniform(0.007, 0.013) * (1.4 if k in (1, 7) else 1.0)
            tip = base + Vector((0, 0, -L if row == 0 else L))
            res = bmesh.ops.create_cone(bm, cap_ends=True, segments=5, radius1=0.0045, radius2=0.0012, depth=L,
                                        matrix=Matrix.Translation((base + tip) / 2) @ (Vector((0, 0, 1)).rotation_difference((tip - base).normalized()).to_matrix().to_4x4()))
    ob = H.obj_from_bm(bm, "Teeth")
    add("Teeth", ob, "teeth")


def build_hands():
    for s, x in SIDES:
        u, v, n = hand_frame(s, x)
        W = WR[s]
        P = lambda a, b, c: W + u * a + v * b + n * c
        sc = H.Sculpt("Hand_" + s, res=0.0028)
        sc.capsule(W - u * 0.05, W + u * 0.01, 0.031)                               # wrist (inside the cuff)
        sc.ellipsoid(P(0.052, 0.0, 0.0), (0.048, 0.041, 0.015), rot=Matrix((u, v, n)).transposed().to_quaternion())
        tips = []
        for j, (off, L) in enumerate(((0.027, 0.98), (0.009, 1.06), (-0.009, 1.0), (-0.026, 0.84))):
            p = P(0.098, off * 1.05, 0.0)
            d = (u + v * off * 1.8).normalized()
            pts, rad = [p], [0.0095]
            for k, (seg, bend, r) in enumerate(((0.047 * L, 14, 0.0088), (0.031 * L, 26, 0.0078), (0.026 * L, 22, 0.0068))):
                d = (Matrix.Rotation(math.radians(bend), 4, v.cross(d).normalized() * -1) @ d.to_4d()).to_3d().normalized()
                d = (d - n * 0.18 * (k + 1) * 0).normalized()
                p = p + d * seg
                pts.append(p); rad.append(r)
            # curl towards the palm (claw-like)
            curled = [pts[0]]
            for k in range(1, len(pts)):
                curled.append(pts[k] + n * 0.006 * k * k)
            sc.chain(curled, rad, stiff=2.5)
            tips.append((curled[-1], (curled[-1] - curled[-2]).normalized()))
        # thumb
        tb = [P(0.018, 0.03, -0.004)]
        td = (u * 0.55 + v * 0.75 + n * 0.25).normalized()
        for seg, r in ((0.045, 0.011), (0.033, 0.0095), (0.026, 0.0082)):
            td = (td + u * 0.25 + n * 0.15).normalized()
            tb.append(tb[-1] + td * seg)
        sc.chain(tb, [0.013, 0.011, 0.0095, 0.0082], stiff=2.5)
        tips.append((tb[-1], (tb[-1] - tb[-2]).normalized()))
        ob = sc.mesh("Hand_" + s)
        H.displace(ob, lambda c, nn: nn * noise.noise(c * 120.0) * 0.0006)
        add("Hand_" + s, ob, "skin")
        # long dark broken nails
        bm = bmesh.new()
        for (p, d) in tips:
            L = rng.uniform(0.016, 0.024)
            q = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
            bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.0058, radius2=0.0012, depth=L,
                                  matrix=Matrix.Translation(p + d * (L * 0.35) - n * 0.002) @ q)
        add("Nails_" + s, H.obj_from_bm(bm, "Nails_" + s), "nail")


def surface_hit(ob, origin, direction):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    tree = BVHTree.FromBMesh(bm); bm.free()
    return tree.ray_cast(origin, direction)


def build_parka():
    s = H.Sculpt("Parka", res=0.008, threshold=0.6)
    s.ellipsoid(Vector((0, 0.018, 1.20)), (0.178, 0.135, 0.29))                    # torso
    s.ellipsoid(Vector((0, 0.02, 1.36)), (0.2, 0.122, 0.085))                      # shoulder yoke
    s.ellipsoid(Vector((0, 0.024, 0.92)), (0.205, 0.156, 0.17))                    # skirt over the hips
    s.capsule(Vector((0, 0.024, 0.98)), Vector((0, 0.03, 0.78)), 0.16)
    for side, x in SIDES:
        s.ball(SH[side] + Vector((0, 0.01, -0.02)), 0.074)                          # shoulders
        s.capsule(SH[side], EL[side], 0.064)                                        # sleeves, roomy
        s.capsule(EL[side], WR[side] - arm_dir(x) * 0.01, 0.056)
        s.ball(EL[side], 0.062)
        s.ball(WR[side] - arm_dir(x) * 0.012, 0.058)                               # gathered cuff
    s.ellipsoid(Vector((0, 0.115, 1.46)), (0.12, 0.06, 0.085))                    # its hood, down, bunched behind the neck
    ob = s.mesh("Parka")

    def folds(c, nn):
        d = Vector()
        # drawcord at the waist pulls the cloth in; the skirt hangs in soft vertical folds
        d -= nn * 0.004 * math.exp(-((c.z - 1.04) / 0.025) ** 2)
        if c.z < 1.0:
            a = math.atan2(c.y, c.x)
            d += nn * 0.008 * math.sin(a * 9 + noise.noise(c * 3) * 2) * min(1.0, (1.0 - c.z) / 0.15)
        # sleeves: rings of compression folds at the elbows and above the cuffs
        for side, x in SIDES:
            for J, w in ((EL[side], 0.06), (WR[side] - arm_dir(x) * 0.06, 0.04)):
                dist = (c - J).length
                if dist < w * 1.6:
                    ax = arm_dir(x).normalized()
                    t = (c - J).dot(ax)
                    d += nn * 0.006 * math.sin(t * 2 * math.pi / 0.03) * math.exp(-(dist / w) ** 2)
        d += nn * (noise.noise(c * 14.0) * 0.004 + noise.noise(c * 45.0) * 0.0012)
        return d
    H.displace(ob, folds)

    def cut(c, nrm):
        if c.z > 1.465 and abs(c.x) < 0.115 and c.y < 0.06:                         # neck opening
            return True
        w = 0.045 + max(0.0, (c.z - 1.15)) * 0.25                                   # front opening, wider at the top
        if c.y < -0.05 and abs(c.x) < w and c.z < 1.47:
            return True
        hem = 0.775 + noise.noise(Vector((c.x * 9, c.y * 9, 0.3))) * 0.025 + (0.02 if math.sin(c.x * 60 + c.y * 40) > 0.75 else 0)
        if c.z < hem:
            return True
        for side, x in SIDES:                                                        # sleeve ends (ragged)
            ax = arm_dir(x).normalized()
            t = (c - WR[side]).dot(ax)
            if t > -0.022 + noise.noise(c * 70) * 0.012 and (c - WR[side]).length < 0.14:
                return True
        # a few tears through the coat
        for p in ((0.17, -0.08, 1.32), (-0.2, 0.05, 1.12), (0.12, 0.14, 1.0), (-0.33, 0.0, 1.22), (0.08, -0.15, 0.86)):
            if (c - Vector(p)).length < 0.016 + 0.01 * noise.noise(c * 40):
                return True
        return False
    H.delete_faces(ob, cut)
    H.keep_largest(ob); H.relax_boundary(ob, 6, 0.5)
    H.smooth(ob, 1, 0.3)
    hm = H.hem(ob, 0.0075, lambda m, loop: abs(m.x) < 0.2 and m.y < -0.02 and max(p.z for p in loop) - min(p.z for p in loop) > 0.3, "ParkaPlacket")
    if hm:
        add("ParkaPlacket", hm, "parka")
    add("Parka", ob, "parka")


def build_hood():
    """The inner hoodie's hood, worn up: a deep shell round the skull, the face open."""
    s = H.Sculpt("Hood", res=0.006)
    C = HC
    s.ellipsoid(C + Vector((0, 0.03, 0.022)), (0.12, 0.135, 0.138))
    s.ellipsoid(C + Vector((0, 0.05, -0.09)), (0.105, 0.09, 0.07))                 # drape over the back of the neck
    s.ellipsoid(C + Vector((0, 0.035, 0.1)), (0.06, 0.07, 0.05))                    # the hood's crown, a little peaked
    ob = s.mesh("Hood")
    H.displace(ob, lambda c, nn: nn * (noise.noise(c * 18) * 0.004 + 0.003 * math.sin((c.z - C.z) * 90 + c.y * 30) * (c.y > 0.05)))

    def cut(c, nrm):
        rel = c - C
        face = rel.y < -0.03 and (rel.x / 0.086) ** 2 + ((rel.z + 0.005) / 0.115) ** 2 < 1.0
        return face or c.z < 1.47 or (rel.y < -0.03 and rel.z < -0.05)
    H.delete_faces(ob, cut)
    H.keep_largest(ob); H.relax_boundary(ob, 12)
    hm = H.hem(ob, 0.009, lambda m, loop: (m - C).y < 0.0, "HoodRim")
    if hm:
        add("HoodRim", hm, "hood")
    add("Hood", ob, "hood")


def build_sweater():
    s = H.Sculpt("Sweater", res=0.007)
    s.ellipsoid(Vector((0, 0.008, 1.18)), (0.152, 0.108, 0.27))
    s.capsule(Vector((0, 0.01, 1.0)), Vector((0, 0.015, 0.86)), 0.138)
    s.capsule(Vector((0, 0.0, 1.40)), Vector((0, 0.005, 1.47)), 0.075)             # roll neck under the scarf
    ob = s.mesh("Sweater")
    H.displace(ob, lambda c, nn: nn * (0.0025 * math.sin(c.x * 2 * math.pi / 0.03) + 0.004 * math.exp(-((c.z - 0.885) / 0.02) ** 2)))
    H.delete_faces(ob, lambda c, nrm: c.z < 0.855 + noise.noise(c * 30) * 0.008)
    add("Sweater", ob, "sweater")
    for side, x in SIDES:                                                            # knit cuffs at the wrists
        c = H.Sculpt("Cuff_" + side, res=0.004)
        c.capsule(WR[side] - arm_dir(x) * 0.045, WR[side] - arm_dir(x) * 0.012, 0.036)
        ob = c.mesh("Cuff_" + side)
        H.displace(ob, lambda cc, nn: nn * 0.002 * math.sin(math.atan2(cc.y, cc.z) * 28))
        add("Cuff_" + side, ob, "sweater")


def build_scarf():
    s = H.Sculpt("Scarf", res=0.006)
    for k in range(18):                                                              # two loose wraps round the neck
        a = 2 * math.pi * k / 18
        for loop, (z, r, tilt) in enumerate(((1.468, 0.082, 0.018), (1.43, 0.095, -0.02))):
            p = Vector((math.cos(a) * r, math.sin(a) * r * 0.9 + 0.01, z + math.sin(a) * tilt + 0.006 * noise.noise(Vector((a, loop, 0)))))
            s.ellipsoid(p, (0.04, 0.04, 0.03), stiff=1.5)
    s.ellipsoid(Vector((0.02, -0.095, 1.415)), (0.07, 0.04, 0.045))              # knot in front
    ob = s.mesh("Scarf")
    H.displace(ob, lambda c, nn: nn * (noise.noise(c * 25) * 0.005 + 0.003 * math.sin(math.atan2(c.y, c.x) * 14 + c.z * 80)))
    add("Scarf", ob, "scarf")
    # the long hanging end: a ribbon from the knot down to the belly, frayed at the bottom
    bm = bmesh.new()
    rows, cols = 16, 6
    grid = []
    for i in range(rows + 1):
        t = i / rows
        cx = 0.03 + 0.03 * t + 0.01 * math.sin(t * 5)
        cz = 1.41 - 0.36 * t
        cy = -0.112 - 0.05 * t - 0.012 * math.sin(t * 3.5)
        w = 0.068 - 0.006 * t
        row = []
        for j in range(cols + 1):
            sx = (j / cols - 0.5) * w
            z = cz
            if i == rows:
                z -= rng.uniform(0.0, 0.045)                                         # fringe
            row.append(bm.verts.new((cx + sx, cy + 0.006 * math.sin(j * 1.7 + i), z)))
        grid.append(row)
    for i in range(rows):
        for j in range(cols):
            bm.faces.new([grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]])
    ob = H.obj_from_bm(bm, "ScarfEnd")
    H.solidify(ob, 0.012, 0.0)
    m = ob.modifiers.new("Sub", "SUBSURF"); m.levels = 1; H.apply_mods(ob)
    add("ScarfEnd", ob, "scarf")


def build_trousers():
    s = H.Sculpt("Trousers", res=0.007)
    s.ellipsoid(Vector((0, 0.012, 0.88)), (0.17, 0.128, 0.11))
    for side, x in SIDES:
        s.chain([HIP[side] + Vector((0, 0.005, 0.0)), KN[side], AN[side] + Vector((0, 0, 0.22))], [0.088, 0.07, 0.062])
        s.ball(KN[side] + Vector((0, -0.01, 0.0)), 0.074)                           # baggy knees
    ob = s.mesh("Trousers")

    def folds(c, nn):
        d = nn * (noise.noise(c * 16) * 0.004)
        for side, x in SIDES:
            for zc, w, amp in ((0.31, 0.05, 0.005), (0.49, 0.035, 0.0025)):              # bunched above the boots, at the knee
                if abs(c.x - KN[side].x) < 0.12:
                    d += nn * amp * math.sin(c.z * 2 * math.pi / 0.05 + x + noise.noise(c * 8) * 2) * math.exp(-((c.z - zc) / w) ** 2)
        return d
    H.displace(ob, folds)
    H.delete_faces(ob, lambda c, nrm: c.z > 0.97 or c.z < 0.27)
    add("Trousers", ob, "trousers")
    # cargo pockets on the outer thighs
    for side, x in SIDES:
        hit = surface_hit(ob, Vector((x * 0.6, 0.0, 0.66)), Vector((-x, 0, 0)))
        if hit[0] is None:
            continue
        p, nrm = hit[0], hit[1]
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(p + nrm * 0.008) @ Matrix.Diagonal((0.016, 0.11, 0.13, 1)))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(p + nrm * 0.012 + Vector((0, 0, 0.07))) @ Matrix.Diagonal((0.02, 0.12, 0.035, 1)))
        pk = H.obj_from_bm(bm, "Pocket_" + side)
        m = pk.modifiers.new("Bev", "BEVEL"); m.width = 0.006; m.segments = 2; H.apply_mods(pk)
        add("Pocket_" + side, pk, "trousers")


def build_parka_details():
    """Flap pockets on the lower front, chest pocket flaps, the stand collar."""
    parka = PARKA_SOLID
    for side, x in SIDES:
        for (z, w, h, flap) in ((0.88, 0.14, 0.13, True), (1.30, 0.09, 0.012, False)):
            hit = surface_hit(parka, Vector((x * 0.125, -0.6, z)), Vector((0, 1, 0)))
            if hit[0] is None:
                continue
            p, nrm = hit[0], hit[1]
            q = Vector((0, -1, 0)).rotation_difference(nrm).to_matrix().to_4x4()
            bm = bmesh.new()
            if flap:
                bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(p + nrm * 0.008) @ q @ Matrix.Diagonal((w, 0.014, h, 1)))
                bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(p + nrm * 0.016 + Vector((0, 0, h * 0.42))) @ q @ Matrix.Diagonal((w * 1.06, 0.01, h * 0.3, 1)))
            else:
                bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(p + nrm * 0.004) @ q
                                      @ Matrix.Rotation(math.radians(x * 70), 4, "Y") @ Matrix.Diagonal((w, 0.008, 0.014, 1)))
            pk = H.obj_from_bm(bm, f"ParkaPocket_{side}_{int(z * 100)}")
            m = pk.modifiers.new("Bev", "BEVEL"); m.width = 0.004; m.segments = 2; H.apply_mods(pk)
            add(pk.name, pk, "parka")
    c = H.Sculpt("Collar", res=0.005)
    for k in range(20):
        a = 2 * math.pi * k / 20
        if -2.2 < a - math.pi * 1.5 < 2.2 or True:
            c.ellipsoid(Vector((math.cos(a) * 0.1, math.sin(a) * 0.094 + 0.015, 1.48)), (0.016, 0.016, 0.042), stiff=2.0)
    ob = c.mesh("Collar")
    H.delete_faces(ob, lambda cc, n: cc.y < -0.07 and abs(cc.x) < 0.045)
    add("Collar", ob, "parka")


def build_boots():
    for side, x in SIDES:
        s = H.Sculpt("Boot_" + side, res=0.0045)
        bx = AN[side].x + x * 0.005
        s.ball(Vector((bx, 0.055, 0.055)), 0.05)                                    # heel
        s.ellipsoid(Vector((bx, -0.045, 0.048)), (0.05, 0.12, 0.046))              # foot
        s.ball(Vector((bx, -0.145, 0.042)), 0.042)                                  # toe cap
        s.capsule(Vector((bx, 0.02, 0.07)), Vector((bx, 0.018, 0.31)), 0.06)         # shaft
        ob = s.mesh("Boot_" + side)
        H.displace(ob, lambda c, nn: nn * (noise.noise(c * 30) * 0.002 + 0.0015 * math.sin(c.y * 300) * (c.z > 0.06) * (c.y < -0.04)))
        H.delete_faces(ob, lambda c, n: c.z > 0.305)
        add("Boot_" + side, ob, "boot")
        bm = bmesh.new()                                                             # sole and heel block
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((bx, -0.045, 0.012)) @ Matrix.Diagonal((0.112, 0.31, 0.024, 1)))
        so = H.obj_from_bm(bm, "Sole_" + side)
        m = so.modifiers.new("Bev", "BEVEL"); m.width = 0.03; m.segments = 4; m.limit_method = "NONE"
        H.apply_mods(so)
        H.displace(so, lambda c, nn: Vector((0, 0, 0)) if c.z > 0.005 else Vector((0, 0, -c.z * 0.5)))
        add("Sole_" + side, so, "sole")
        # cloth strips wrapped criss-cross round the shaft: flat bands with a little thickness
        bm = bmesh.new()
        for k in range(7):
            z = 0.115 + k * 0.03
            H.ribbon_loop(Vector((bx, 0.018, 0)), 0.064 + k * 0.0006, 0.064, z, (1 if k % 2 else -1) * 0.02, 0.026, bm,
                          phase=rng.uniform(0, 1), wobble=0.002)
        wo = H.obj_from_bm(bm, "Wrap_" + side)
        H.solidify(wo, 0.004, 1.0)
        m = wo.modifiers.new("Sub", "SUBSURF"); m.levels = 1; H.apply_mods(wo)
        add("Wrap_" + side, wo, "wrap")


# ------------------------------------------------------------------ paint
def paints():
    P = {}
    SKIN_BASE, SKIN_DARK = (0.80, 0.69, 0.63), (0.60, 0.46, 0.44)
    p = H.Paint("skin").base(SKIN_DARK, SKIN_BASE, scale=9.0, contrast=0.5, fine=0.18)
    p.layer(p.mask_noise(5.0, 0.18), (0.55, 0.38, 0.45), 0.55)                       # bruising
    p.layer(p.mask_near([HC + Vector((x * 0.033, -0.08, 0.012)) for x in (-1, 1)], 0.03, 0.7, 0.2), (0.48, 0.24, 0.26), 0.8)   # raw sockets
    p.layer(p.mask_near([HC + Vector((0, -0.09, -0.08)), HC + Vector((0.02, -0.085, -0.115)), HC + Vector((-0.03, -0.07, -0.13))], 0.04, 0.6, 0.4), (0.36, 0.05, 0.05))
    tips = [WR[s] + arm_dir(x) * 0.17 for s, x in SIDES] + [WR[s] + arm_dir(x) * 0.12 for s, x in SIDES]
    p.layer(p.mask_near(tips, 0.05, 0.6, 0.4), (0.40, 0.07, 0.06), 0.9)
    p.skin_texture(1.6, crease=(0.40, 0.27, 0.27), vein=(0.42, 0.34, 0.46), amount=0.6, veins=0.45)   # finer: a human face and hands
    p.crust(p.mask_near([HC + Vector((0, -0.09, -0.08)), HC + Vector((0.03, -0.06, 0.05))], 0.03, 0.7, 0.5), 110.0, (0.30, 0.07, 0.06), 0.7)
    P["skin"] = p.cavity(0.55, 0.15).done()
    p = H.Paint("eye").base((0.80, 0.74, 0.58), (0.92, 0.88, 0.76), scale=40)
    p.layer(p.mask_near([HC + Vector((x * 0.033, -0.087, 0.012)) for x in (-1, 1)], 0.0045, 0.3, 0.0), (0.12, 0.08, 0.06))
    P["eye"] = p.done()
    P["mouth"] = H.Paint("mouth").base((0.16, 0.03, 0.04), (0.32, 0.06, 0.07), scale=30).done()
    p = H.Paint("teeth").base((0.62, 0.52, 0.32), (0.82, 0.74, 0.52), scale=60)
    P["teeth"] = p.streaks(90.0, "Z", (0.40, 0.30, 0.16), 0.4, 0.5).done()
    P["nail"] = H.Paint("nail").base((0.12, 0.08, 0.08), (0.26, 0.17, 0.16), scale=80).streaks(90.0, "Z", (0.06, 0.04, 0.04), 0.4).done()

    RED, RED_D, FADE = (0.58, 0.24, 0.16), (0.36, 0.12, 0.08), (0.68, 0.40, 0.29)
    p = H.Paint("parka").base(RED_D, RED, scale=3.5, contrast=0.55, fine=0.2)
    p.layer(p.mask_above(1.25, 1.45), FADE, 0.45)                                    # sun-faded shoulders
    p.layer(p.mask_noise(2.5, 0.22), (0.52, 0.28, 0.16), 0.5)                        # brown water stains
    p.layer(p.mask_below(0.78, 0.95, 0.05), (0.30, 0.18, 0.12), 0.6)                 # filthy hem
    p.layer(p.mask_near([Vector((x * 0.12, -0.16, 0.9)) for x in (-1, 1)] + [Vector((0.06, -0.15, 1.1))], 0.07, 0.6, 0.45), (0.33, 0.07, 0.06), 0.85)  # blood on the front
    for s_, x_ in SIDES:                                                               # elbow patches, sewn on
        e = EL[s_]
        p.layer(p.mask_box((e.x, e.y + 0.05, e.z), (0.05, 0.0, 0.06), 0.06), (0.36, 0.31, 0.19))
        p.layer(p.mask_box((e.x, e.y + 0.05, e.z), (0.05, 0.0, 0.06), 0.06, border=0.12), (0.18, 0.13, 0.08), 0.8)
    p.layer(p.mask_noise(9.0, 0.12), (0.26, 0.10, 0.07), 0.7)                          # grime speckle
    p.layer(p.mask_noise(1.6, 0.3), (0.30, 0.16, 0.10), 0.35)                          # large dirty areas
    for k, at in ((0, 0.0), (0, 0.205), (0, -0.205)):
        p.layer(p.seam_plane(k, at, 0.003), (0.30, 0.12, 0.08), 0.6)                  # back seam, side seams
    p.layer(p.stripes(2, 0.95, 0.004), (0.30, 0.12, 0.08), 0.0)
    p.weave(55.0, (0.26, 0.08, 0.05), 0.3, 0.6)                                          # heavy canvas
    p.layer(p.mask_noise(7.0, 0.12), (0.70, 0.46, 0.34), 0.35)                          # scuffed, rubbed pale
    P["parka"] = p.cavity(0.6, 0.35).done()
    p = H.Paint("sweater").base((0.66, 0.56, 0.40), (0.86, 0.77, 0.59), scale=6, contrast=0.4, fine=0.25)
    p.layer(p.stripes(0, 0.032, 0.004, 0.004), (0.55, 0.46, 0.32), 0.7)               # cable ribs
    p.layer(p.mask_near([Vector((0.02, -0.12, 1.2)), Vector((-0.03, -0.12, 1.32))], 0.06, 0.6, 0.45), (0.40, 0.10, 0.08), 0.8)
    p.knit(48.0, (0.46, 0.38, 0.25), 0.35, 0.8)
    P["sweater"] = p.cavity(0.5, 0.25).done()
    p = H.Paint("scarf").base((0.58, 0.38, 0.13), (0.80, 0.58, 0.24), scale=7, contrast=0.5)
    p.layer(p.mask_noise(4.0, 0.2), (0.45, 0.32, 0.16), 0.5)
    p.layer(p.mask_below(1.08, 1.16), (0.86, 0.70, 0.42), 0.6)                         # frayed, paler ends
    p.knit(36.0, (0.40, 0.25, 0.08), 0.4, 0.9)
    P["scarf"] = p.cavity(0.5, 0.2).done()
    p = H.Paint("hood").base((0.48, 0.39, 0.25), (0.66, 0.56, 0.38), scale=5, contrast=0.5)
    p.layer(p.seam_plane(0, 0.0, 0.003), (0.32, 0.25, 0.15), 0.8)
    p.layer(p.mask_noise(3.0, 0.2), (0.40, 0.32, 0.22), 0.5)
    p.weave(50.0, (0.30, 0.24, 0.14), 0.3, 0.6)
    P["hood"] = p.cavity(0.6, 0.25).done()
    p = H.Paint("trousers").base((0.32, 0.22, 0.12), (0.46, 0.34, 0.20), scale=4, contrast=0.5, fine=0.2)
    for (c, hx, hz, col) in (((0.11, 0, 0.52), 0.06, 0.07, (0.52, 0.40, 0.25)), ((-0.1, 0, 0.66), 0.055, 0.06, (0.40, 0.30, 0.18)),
                             ((-0.12, 0, 0.42), 0.05, 0.05, (0.55, 0.43, 0.28)), ((0.12, 0, 0.78), 0.05, 0.04, (0.36, 0.26, 0.15))):
        p.layer(p.mask_box(c, (hx, 0.0, hz), 0.08), col, 0.95)                          # sewn-on patches
        p.layer(p.mask_box(c, (hx, 0.0, hz), 0.08, border=0.14), (0.20, 0.14, 0.08), 0.8)
    p.layer(p.mask_noise(8.0, 0.12), (0.22, 0.15, 0.09), 0.6)
    p.layer(p.mask_below(0.3, 0.5, 0.06), (0.25, 0.19, 0.13), 0.6)                    # mud
    p.weave(55.0, (0.18, 0.12, 0.07), 0.3, 0.6, twill=True)                             # cotton twill
    p.layer(p.mask_noise(6.0, 0.12), (0.56, 0.44, 0.30), 0.3)                           # worn pale
    P["trousers"] = p.cavity(0.6, 0.3).done()
    p = H.Paint("boot").base((0.24, 0.14, 0.09), (0.42, 0.27, 0.17), scale=8, contrast=0.6)
    p.layer(p.mask_below(0.04, 0.09, 0.02), (0.22, 0.18, 0.14), 0.6)
    p.leather(140.0, (0.14, 0.08, 0.05), 0.4, 0.7)
    P["boot"] = p.cavity(0.7, 0.45).done()
    P["sole"] = H.Paint("sole").base((0.10, 0.08, 0.07), (0.18, 0.15, 0.12), scale=20).done()
    p = H.Paint("wrap").base((0.56, 0.47, 0.34), (0.76, 0.67, 0.50), scale=9, contrast=0.5)
    p.layer(p.mask_below(0.1, 0.22, 0.03), (0.40, 0.33, 0.24), 0.6)
    p.weave(35.0, (0.40, 0.33, 0.22), 0.4, 0.8)                                         # loose, coarse weave
    P["wrap"] = p.cavity(0.6, 0.2).done()
    P["lining"] = H.Paint("lining").base((0.52, 0.45, 0.32), (0.66, 0.58, 0.42), scale=8).weave(55.0, (0.36, 0.30, 0.2), 0.3).done()
    return P


# ------------------------------------------------------------------ stages
def stage_high():
    global PARKA_SOLID
    H.reset()
    build_head(); build_hands(); build_parka(); build_hood(); build_sweater(); build_scarf()
    build_trousers(); build_boots()
    # thickness for the cloth shells (kept open copies are not needed: QuadriFlow runs on the solid)
    for nm in ("Parka", "Hood"):
        ob = PARKA_SOLID = PARTS[nm][0]
        H.solidify(ob, 0.011 if nm == "Parka" else 0.009, -1.0, mat_offset=1)
    PARKA_SOLID = PARTS["Parka"][0]
    build_parka_details()
    P = paints()
    for nm, (ob, key) in PARTS.items():
        ob.data.materials.clear(); ob.data.materials.append(P[key])
        if nm in ("Parka", "Hood"):
            ob.data.materials.append(P["lining"])                                      # the inside of the shell
        for poly in ob.data.polygons:
            poly.use_smooth = True
    tris = sum(sum(len(p.vertices) - 2 for p in ob.data.polygons) for ob, _ in PARTS.values())
    print("high parts", len(PARTS), "tris", tris)
    bpy.ops.wm.save_as_mainfile(filepath=OUT + "_high.blend")
    if "--paintqc" in sys.argv:                                                 # the real paint (emission) up close
        H.closeups(OUT + "_paint_cu.png", [(HC, 0.32, 0, 0), (HC, 0.32, 45, 10), (WR["L"] + arm_dir(1) * 0.08, 0.26, 90, 0),
                                          (Vector((0, -0.02, 1.15)), 0.5, 20, 10), (Vector((0.11, -0.02, 0.45)), 0.45, 20, 10)])
    if "--qc" in sys.argv:
        preview_materials()
        H.qc_renders([o for o, _ in PARTS.values()], OUT + "_high_qc.png", height=1.8)
        H.closeups(OUT + "_high_cu.png", [(HC, 0.32, 0, 0), (HC, 0.32, 60, 5), (HC, 0.32, 300, 30),
                                          (WR["L"] + arm_dir(1) * 0.08, 0.26, 90, 0), (WR["L"] + arm_dir(1) * 0.08, 0.26, 0, 10),
                                          (Vector((0.11, -0.02, 0.2)), 0.45, 20, 10)])


def preview_materials():
    """Simple lit stand-ins (base colour of each paint) so the QC renders show form."""
    cols = {"skin": (0.78, 0.66, 0.6), "eye": (0.9, 0.86, 0.74), "mouth": (0.25, 0.05, 0.05), "teeth": (0.78, 0.7, 0.5),
            "nail": (0.2, 0.12, 0.12), "parka": (0.6, 0.26, 0.17), "sweater": (0.8, 0.7, 0.52), "scarf": (0.72, 0.5, 0.2),
            "hood": (0.6, 0.5, 0.33), "trousers": (0.42, 0.3, 0.17), "boot": (0.36, 0.22, 0.14), "sole": (0.14, 0.11, 0.09),
            "wrap": (0.7, 0.6, 0.45)}
    mats = {}
    for k, c in cols.items():
        m = bpy.data.materials.new("prev_" + k); m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = H.lin(c); b.inputs["Roughness"].default_value = 0.8
        mats[k] = m
    for nm, (ob, key) in PARTS.items():
        ob.data.materials.clear(); ob.data.materials.append(mats[key])


# ------------------------------------------------------------------ stage: game mesh
BUDGET = {   # QuadriFlow quads (x2 = triangles); small hard parts are decimated to a triangle count instead
    "Head": 1700, "Hand_L": 450, "Hand_R": 450, "Parka": 1450, "Hood": 520, "HoodRim": 120, "ParkaPlacket": 120,
    "Sweater": 300, "Cuff_L": 60, "Cuff_R": 60, "Scarf": 360, "ScarfEnd": 160, "Trousers": 900, "Collar": 150,
    "Boot_L": 300, "Boot_R": 300, "Wrap_L": 260, "Wrap_R": 260,
}
DECIMATE = {"Wrap_L": 500, "Wrap_R": 500, "ParkaPlacket": 240, "Eye_L": 60, "Eye_R": 60, "Mouth": 80, "Teeth": 200, "Nails_L": 60, "Nails_R": 60, "Sole_L": 80, "Sole_R": 80,
            "Pocket_L": 60, "Pocket_R": 60}


def stage_low():
    bpy.ops.wm.open_mainfile(filepath=OUT + "_high.blend")
    highs = [o for o in bpy.data.objects if o.type == "MESH"]
    lows = []
    for h in highs:
        nm = h.name
        if nm in BUDGET and nm not in DECIMATE:
            lo = H.retopo(h, BUDGET[nm], nm + "_low")
        else:
            lo = H.decimate(h, DECIMATE.get(nm, 120), nm + "_low")
        lows.append(lo)
        print("low", nm, len(h.data.polygons), "->", sum(len(p.vertices) - 2 for p in lo.data.polygons), "tris")
    # one game mesh
    H.select_only(lows[0])
    for lo in lows:
        lo.select_set(True)
    bpy.context.view_layer.objects.active = lows[0]
    bpy.ops.object.join()
    game = bpy.context.view_layer.objects.active
    game.name = "Infected"
    tris = sum(len(p.vertices) - 2 for p in game.data.polygons)
    print("game mesh", len(game.data.vertices), "verts", tris, "tris")
    H.bake_to_low(highs, game, size=2048, cage=0.02, ao=0.55, path=OUT + "_paint_2k.png")
    for h in highs:
        h.hide_render = True; h.hide_set(True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT + "_low.blend")
    if "--qc" in sys.argv:
        H.qc_renders([game], OUT + "_low_qc.png", height=1.8)
        H.closeups(OUT + "_low_cu.png", [(HC, 0.32, 0, 0), (HC, 0.32, 45, 10), (WR["L"] + arm_dir(1) * 0.08, 0.26, 90, 0),
                                          (Vector((0, -0.02, 1.15)), 0.6, 20, 10), (Vector((0, 0.05, 1.15)), 0.6, 180, 10)])


if STAGE == "high":
    stage_high()
elif STAGE == "low":
    stage_low()


# ------------------------------------------------------------------ stage: rig, weights, clips, export
def bones_spec():
    UP, FWD, BACK = (0, 0, 1), (0, -1, 0), (0, 1, 0)
    B = [
        ("Hips", (0, 0.0, 0.92), (0, 0.0, 1.03), None, FWD),
        ("Spine", (0, 0.0, 1.03), (0, 0.005, 1.16), "Hips", FWD),
        ("Spine1", (0, 0.005, 1.16), (0, 0.01, 1.29), "Spine", FWD),
        ("Spine2", (0, 0.01, 1.29), (0, 0.01, 1.42), "Spine1", FWD),
        ("Neck", (0, 0.01, 1.44), (0, 0.0, 1.55), "Spine2", FWD),
        ("Head", (0, 0.0, 1.55), (0, -0.005, 1.75), "Neck", FWD),
        ("Jaw", tuple(HC + Vector((0, 0.0, -0.03))), tuple(HC + Vector((0, -0.075, -0.105))), "Head", UP),
    ]
    for s, x in SIDES:
        d = arm_dir(x)
        palm = tuple(hand_frame(s, x)[2])                     # fingers curl towards the palm on +x
        B += [
            (f"Shoulder_{s}", (x * 0.03, 0.0, 1.42), (x * 0.17, 0.005, 1.43), "Spine2", FWD),
            (f"UpperArm_{s}", tuple(SH[s]), tuple(EL[s]), f"Shoulder_{s}", BACK),
            (f"ForeArm_{s}", tuple(EL[s]), tuple(WR[s]), f"UpperArm_{s}", BACK),
            (f"Hand_{s}", tuple(WR[s]), tuple(WR[s] + d * 0.09), f"ForeArm_{s}", palm),
            (f"Fingers_{s}", tuple(WR[s] + d * 0.095), tuple(WR[s] + d * 0.19), f"Hand_{s}", palm),
            (f"UpLeg_{s}", tuple(HIP[s]), tuple(KN[s]), "Hips", FWD),
            (f"Leg_{s}", tuple(KN[s]), tuple(AN[s]), f"UpLeg_{s}", FWD),
            (f"Foot_{s}", tuple(AN[s]), (x * 0.11, -0.105, 0.025), f"Leg_{s}", UP),
            (f"Toe_{s}", (x * 0.11, -0.105, 0.025), (x * 0.11, -0.19, 0.02), f"Foot_{s}", UP),
        ]
    return B


def build_proxy():
    """A closed, simplified body for bone-heat weights (cloth and skin take their weights from it)."""
    s = H.Sculpt("Proxy", res=0.012)
    s.ellipsoid(Vector((0, 0.015, 1.2)), (0.17, 0.125, 0.27))
    s.ellipsoid(Vector((0, 0.02, 0.92)), (0.18, 0.13, 0.13))
    s.capsule(NECK0, Vector((0, 0.0, 1.56)), 0.06)
    s.ellipsoid(HC + Vector((0, 0.02, 0.01)), (0.11, 0.12, 0.125))
    s.ball(HC + Vector((0, -0.07, -0.1)), 0.035)
    for side, x in SIDES:
        s.ball(SH[side], 0.07)
        s.chain([SH[side], EL[side], WR[side]], [0.062, 0.055, 0.045])
        u, v, n = hand_frame(side, x)
        s.capsule(WR[side], WR[side] + u * 0.2, 0.03)
        s.chain([HIP[side], KN[side], AN[side]], [0.085, 0.068, 0.06])
        s.capsule(Vector((AN[side].x, 0.05, 0.05)), Vector((AN[side].x, -0.18, 0.04)), 0.05)
    ob = s.mesh("Proxy")
    return ob


def stage_rig():
    import creature_kit as K
    bpy.ops.wm.open_mainfile(filepath=OUT + "_low.blend")
    game = bpy.data.objects["Infected"]
    for o in list(bpy.data.objects):
        if o is not game:
            bpy.data.objects.remove(o, do_unlink=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    rig = K.Rig("InfectedRig", bones_spec())
    proxy = build_proxy()
    ok = H.heat_weights(rig.ob, proxy)
    print("bone heat on proxy:", ok)
    proxy.parent = None
    H.transfer_weights(proxy, game, rig.ob, smooth_iters=2)
    bpy.data.objects.remove(proxy, do_unlink=True)
    # the eyes, teeth and mouth follow the head (the lower teeth the jaw) rigidly
    vg = {g.name: g for g in game.vertex_groups}
    clips = make_clips(K, rig)
    ground_report(rig, game, clips)
    for img in bpy.data.images:
        if img.size[0] > 1024:
            img.scale(1024, 1024)
    for img in bpy.data.images:                                                  # self-contained .blend
        if img.source == "FILE" or img.is_dirty:
            img.pack()
    bpy.ops.wm.save_as_mainfile(filepath=OUT + "_human.blend")
    K.export(rig, OUT, {
        "fps_src": 24, "clips": {k: k for k in clips}, "idle_loop_src": [0, 96], "height_m": 1.75, "exposure": 1.0,
        "creature": "infected", "lengths": clips, "walk_v": WALK_V, "bite_hit": CLAW_HIT,
        "view": {"w": 420, "h": 460, "foot_y": 380, "big_w": 760, "big_h": 620, "big_foot_y": 330},
    })
    if "--qc" in sys.argv:
        frames = [("idle", 20), ("walk", 5), ("walk", 25), ("bite", 8), ("bite", 13), ("hit", 4), ("death", 40)]
        shots = []
        for clip, f in frames:
            rig.ob.animation_data.action = bpy.data.actions[clip]
            sc.frame_set(f)
            p = f"/tmp/inf_pose_{clip}_{f}.png"
            H.qc_renders([game], p, height=1.9, views=(("3/4", 35),), game=True)
        from PIL import Image
        ims = [Image.open(f"/tmp/inf_pose_{c}_{f}.png") for c, f in frames]
        sheet = Image.new("RGB", (sum(i.width for i in ims) // 2, ims[0].height // 2))
        x = 0
        for im in ims:
            im = im.resize((im.width // 2, im.height // 2)); sheet.paste(im, (x, 0)); x += im.width
        sheet.save(OUT + "_poses.png")


WALK_N, WALK_V, DUTY = 40, 0.025, 0.62
DEATH_DROP = 0.57
CLAW_N, CLAW_HIT = 24, 13


def make_clips(K, rig):
    STRIDE = WALK_V * DUTY * WALK_N
    ANK = {s: AN[s].copy() for s, _ in SIDES}
    FOOT_DIR = (Vector((0, -0.105, 0.025)) - Vector((0, 0.02, 0.085))).normalized()

    def legs(P, feet):
        P._feet = feet
        for s, x in SIDES:
            P.chain(f"UpLeg_{s}", f"Leg_{s}", feet[s], Vector((x * 0.1, -1, 0)), f"Foot_{s}", feet.get(s + "_dir", FOOT_DIR),
                    feet.get(s + "_z", (0, 0, 1)))

    def arms_rest(P, k=1.0, lean=None):
        """A-pose -> arms hanging by gravity (the spine's forward lean is taken back out), elbows soft."""
        ax = -12 * k if lean is None else -(lean + 4) * k
        for s, x in SIDES:
            P.rot(f"UpperArm_{s}", x=ax, z=x * 27)
            P.rot(f"ForeArm_{s}", x=-16 * k)

    def hunch(P, k=1.0, br=0.0):
        P.rot("Spine", x=8 * k + 1.5 * br); P.rot("Spine1", x=8 * k + 1.5 * br); P.rot("Spine2", x=10 * k + 2 * br)
        P.rot("Neck", x=-6 * k); P.rot("Head", x=-10 * k)
        for s, x in SIDES:
            P.rot(f"Shoulder_{s}", x=8 * k)
            P.rot(f"Fingers_{s}", x=18 * k)
        return 26 * k                                          # degrees the chest leans forward

    clips = {}

    BOOT = [("Foot", 0.0, 0.055), ("Foot", 1.0, 0.045), ("Toe", 1.0, 0.03)]     # (bone, along, half thickness)

    def boot_low(M_of):
        low = 9.0
        for b, t, h in BOOT:
            M = M_of(b)
            c = M @ Vector((0, rig.len[f"{b}_L"] * t, 0))
            zax = M.to_3x3() @ Vector((0, 0, 1))
            low = min(low, c.z - abs(zax.z) * h)
        return low

    REST_LOW = boot_low(lambda b: rig.rest[f"{b}_L"])

    def ground_feet(P):
        """Raise a foot's IK target if any part of the boot would go through the floor (falls, kneels)."""
        for _ in range(2):
            P.solve()
            lift = {}
            for s, x in SIDES:
                low = boot_low(lambda b: P.pose[f"{b}_{s}"])
                if low < REST_LOW - 0.002:
                    lift[s] = REST_LOW - low
            if not lift:
                return
            feet = dict(P._feet)
            for s, d in lift.items():
                feet[s] = feet[s] + Vector((0, 0, d))
            P.ik = [c for c in P.ik if not c[0].startswith("UpLeg_")]
            legs(P, feet)

    def clip(name, n, fn):
        K.new_action(rig, name)
        for f in range(n + 1):
            P = K.Pose(rig)
            fn(P, f, n)
            ground_feet(P)
            P.solve().key(f)
        clips[name] = n

    JERKS = [(14, 18, 26), (44, 47, -20), (70, 75, 32)]

    def idle(P, f, n):
        t = f / n
        br = math.sin(t * 2 * math.pi * 4)
        jerk = sum(a * K.smoothstep(s0, s0 + 1.5, f) * (1 - K.smoothstep(e, e + 6, f)) for s0, e, a in JERKS)
        P.root("Hips", offset=(0.02 * math.sin(t * 2 * math.pi), 0, -0.02 + 0.006 * br), ry=3 * math.sin(t * 2 * math.pi), rz=4 * math.sin(t * 2 * math.pi + 1))
        arms_rest(P, 1.0, hunch(P, 1.0, br))
        P.rot("Neck", z=jerk * 0.4); P.rot("Head", z=jerk * 0.6, y=12 + 6 * math.sin(t * 2 * math.pi * 2))
        P.rot("Jaw", x=-(3 + 4 * math.sin(t * 2 * math.pi * 3)))
        P.rot("UpperArm_L", x=4 * math.sin(t * 2 * math.pi + 0.5)); P.rot("UpperArm_R", x=-5 * math.sin(t * 2 * math.pi))
        P.rot("Fingers_R", x=14 * max(0.0, math.sin(t * 2 * math.pi * 5)) * (0.5 < t < 0.65))
        legs(P, {s: ANK[s].copy() for s, _ in SIDES})

    def walk(P, f, n):
        t = f / n
        c = math.cos(t * 2 * math.pi)
        P.root("Hips", offset=(0.03 * c, 0, -0.03 - 0.025 * max(0.0, -c)), ry=-6 * c, rz=8 * math.sin(t * 2 * math.pi))
        arms_rest(P, 1.0, hunch(P, 1.25))
        P.rot("Spine", y=6 * c); P.rot("Spine2", y=-8 * c, z=-6 * math.sin(t * 2 * math.pi))
        P.rot("Head", z=10 * math.sin(t * 2 * math.pi + 1.5), y=14 + 8 * c)
        P.rot("Jaw", x=-5)
        P.rot("UpperArm_L", x=-32 - 10 * math.sin(t * 2 * math.pi)); P.rot("ForeArm_L", x=-18)        # the left reaches ahead
        P.rot("UpperArm_R", x=14 * math.sin(t * 2 * math.pi + math.pi))                              # the right hangs and swings
        feet = {}
        for s, x in SIDES:
            drag = s == "R"
            y, z = K.gait(t + (0.0 if s == "L" else 0.5), DUTY, STRIDE, 0.045 if drag else 0.09, ANK[s].y)
            feet[s] = Vector((ANK[s].x, y, ANK[s].z + z))
            if z > 0.005:
                tip = Vector((0, 0.14, -0.22)) if drag else Vector((0, 0.12, -0.25))
                feet[s + "_dir"] = (FOOT_DIR + tip * (z / (0.045 if drag else 0.09))).normalized()
        legs(P, feet)

    def claw(P, f, n):
        # wind up (arms up and forward, claws high) -> rake down and forward on the hit frame -> recover
        up = K.smoothstep(0, 8, f) * (1 - K.smoothstep(9, 13, f))
        lunge = K.smoothstep(9, 13, f) * (1 - K.smoothstep(15, 23, f))
        rake = K.smoothstep(9, 13, f) * (1 - K.smoothstep(16, 23, f))
        P.root("Hips", offset=(0, 0.04 * up - 0.16 * lunge, -0.02 * up - 0.06 * lunge), rx=-3 * up)
        lean = hunch(P, 1.0 - 0.6 * up) - 11 * up + 30 * lunge
        arms_rest(P, 1.0 - max(up, rake), lean)
        P.rot("Spine1", x=-5 * up + 14 * lunge); P.rot("Spine2", x=-6 * up + 16 * lunge)
        P.rot("Head", x=-8 * up + 6 * lunge)
        P.rot("Jaw", x=-2 - 20 * K.smoothstep(4, 12, f) * (1 - K.smoothstep(16, 22, f)))
        for s, x in SIDES:
            P.rot(f"UpperArm_{s}", x=-105 * up - (lean + 74) * rake, z=-x * 8 * up)
            P.rot(f"ForeArm_{s}", x=-45 * up - 6 * rake)
            P.rot(f"Fingers_{s}", x=34 * rake - 14 * up)
        legs(P, {s: ANK[s].copy() for s, _ in SIDES})

    def hit(P, f, n):
        k = K.smoothstep(0, 3, f) * (1 - K.smoothstep(5, 13, f))
        P.root("Hips", offset=(0, 0.05 * k, -0.02 * k), rz=8 * k)
        arms_rest(P, 1.0, hunch(P, 1.0 - 0.8 * k) - 22 * k)
        P.rot("Spine1", x=-10 * k); P.rot("Spine2", x=-12 * k, z=10 * k)
        P.rot("Head", x=-20 * k, z=-24 * k)
        P.rot("Jaw", x=-18 * k - 2)
        P.rot("UpperArm_L", x=-20 * k, z=-10 * k); P.rot("UpperArm_R", x=14 * k, z=12 * k)
        legs(P, {s: ANK[s].copy() for s, _ in SIDES})

    DEAD_DIR = Vector((0, 0.85, -0.35)).normalized()            # face down: the feet lie on their tops, toes back

    def death(P, f, n):
        buckle = K.smoothstep(2, 12, f)                            # knees give way
        fall = K.smoothstep(10, 26, f)                             # topples forward onto the chest
        tip = K.smoothstep(10, 24, f)                              # the body pitches over before it drops
        P.root("Hips", offset=(0, -0.30 * fall, -0.20 * buckle - DEATH_DROP * fall ** 2), rx=84 * tip, rz=10 * fall)
        hunch(P, 1.0 + 0.4 * buckle - 1.2 * fall)
        arms_rest(P)
        P.rot("Neck", x=-24 * fall, z=14 * fall); P.rot("Head", z=22 * fall, y=28 * fall)     # cheek on the ground
        P.rot("Jaw", x=-4 - 12 * fall)
        # left arm thrown forward past the head, right arm out to the side, both flat on the ground
        P.rot("UpperArm_L", x=-40 * buckle - 110 * fall, z=-14 * fall); P.rot("ForeArm_L", x=-20 * fall)
        P.rot("UpperArm_R", x=-30 * buckle + 52 * fall, z=34 * fall); P.rot("ForeArm_R", x=-8 * fall)
        P.rot("Fingers_L", x=20 * fall); P.rot("Fingers_R", x=-16 * fall)
        R = P.rig.rest["Hips"]
        W = R @ P.basis["Hips"] @ R.inverted()
        feet = {}
        for s, x in SIDES:
            a = ANK[s]
            knelt = a + Vector((0, 0.05, 0.0))
            body = W @ (a + Vector((0, 0.06, 0.06)))
            q = a.lerp(knelt, buckle).lerp(body, fall)
            q.z = max(q.z, AN[s].z - 0.01)                       # the feet never go through the floor
            feet[s] = q
            feet[s + "_dir"] = FOOT_DIR.lerp(DEAD_DIR, fall).normalized()
            ang = math.pi * fall
            feet[s + "_z"] = (0, -math.sin(ang), math.cos(ang))
        legs(P, feet)

    clip("idle", 96, idle)
    clip("walk", WALK_N, walk)
    clip("bite", CLAW_N, claw)
    clip("hit", 14, hit)
    clip("death", 40, death)
    return clips


def ground_report(rig, game, clips):
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    for name, n in clips.items():
        rig.ob.animation_data.action = bpy.data.actions[name]
        lows = []
        for f in range(0, n + 1, 2 if name in ("death", "walk") else max(1, n // 8)):
            sc.frame_set(f)
            ev = game.evaluated_get(dg)
            me = ev.to_mesh()
            lows.append(min((game.matrix_world @ v.co).z for v in me.vertices))
            ev.to_mesh_clear()
        print("ground", name, " ".join(f"{z:+.3f}" for z in lows))


if STAGE == "rig":
    stage_rig()
