"""Silo 81 environment kit for Blender: toon materials, primitives and the props the level builder places.
Plan coordinates (u, v) run along the 45-degree iso grid; ground x = (u - v)/sqrt2, y = (u + v)/sqrt2,
z up. The camera looks north (+y) from 30 degrees above, like the character renders."""
import math
import bpy, bmesh
from mathutils import Vector, Matrix

R2 = 1 / math.sqrt(2)
LIGHT = Vector((-0.55, -0.55, 0.63)).normalized()


def g(u, v):
    return ((u - v) * R2, (u + v) * R2)


# ---------------------------------------------------------------- materials
_mats = {}


def _ramp(nt, lit, mid, shade):
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    dot = nt.nodes.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = LIGHT
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.interpolation = "CONSTANT"
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.0, (shade, shade, shade * 1.04, 1)
    e[1].position, e[1].color = 0.45, (lit, lit * 0.99, lit * 0.96, 1)
    m = e.new(0.12); m.color = (mid, mid, mid * 1.02, 1)
    nt.links.new(geo.outputs["Normal"], dot.inputs[0]); nt.links.new(dot.outputs["Value"], ramp.inputs["Fac"])
    return ramp


def toon(name, rgb, noise=0.0, noise_scale=6.0, lit=1.04, mid=0.84, shade=0.66, alpha_noise=None,
         dado=None, frost=None, grating=None, stripes=None):
    """Emission toon material. Options:
    noise: colour variation strength.  dado: (lower_rgb, height) painted lower wall.
    frost: (u_start, u_full, frost_rgb) frost creeping in along +u.  grating: (bar_rgb, pitch) steel floor grate.
    alpha_noise: (threshold, scale) cut out by noise, for stains and decals."""
    key = name
    if key in _mats:
        return _mats[key]
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    pos = nt.nodes.new("ShaderNodeNewGeometry")
    col = nt.nodes.new("ShaderNodeRGB"); col.outputs[0].default_value = (*rgb, 1)
    cur = col.outputs[0]

    def mix(a, b, fac):
        mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"
        nt.links.new(fac, mx.inputs["Factor"]); nt.links.new(a, mx.inputs[6]); nt.links.new(b, mx.inputs[7])
        return mx.outputs[2]

    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(pos.outputs["Position"], sep.inputs[0])
    if dado:
        lower, h = dado
        lc = nt.nodes.new("ShaderNodeRGB"); lc.outputs[0].default_value = (*lower, 1)
        lt = nt.nodes.new("ShaderNodeMath"); lt.operation = "LESS_THAN"; lt.inputs[1].default_value = h
        nt.links.new(sep.outputs["Z"], lt.inputs[0])
        cur = mix(cur, lc.outputs[0], lt.outputs[0])
        # dark painted line on top of the dado
        band = nt.nodes.new("ShaderNodeMath"); band.operation = "COMPARE"
        band.inputs[1].default_value = h + 0.02; band.inputs[2].default_value = 0.025
        nt.links.new(sep.outputs["Z"], band.inputs[0])
        dk = nt.nodes.new("ShaderNodeRGB"); dk.outputs[0].default_value = (lower[0] * 0.45, lower[1] * 0.45, lower[2] * 0.45, 1)
        cur = mix(cur, dk.outputs[0], band.outputs[0])
    if grating:
        bar, pitch = grating
        bc = nt.nodes.new("ShaderNodeRGB"); bc.outputs[0].default_value = (*bar, 1)
        acc = None
        for axis in ("X", "Y"):
            # bars along the plan diagonals: use (x+y) and (x-y)
            add = nt.nodes.new("ShaderNodeMath"); add.operation = "ADD" if axis == "X" else "SUBTRACT"
            nt.links.new(sep.outputs["X"], add.inputs[0]); nt.links.new(sep.outputs["Y"], add.inputs[1])
            sc_ = nt.nodes.new("ShaderNodeMath"); sc_.operation = "MULTIPLY"; sc_.inputs[1].default_value = R2 / pitch
            nt.links.new(add.outputs[0], sc_.inputs[0])
            fr = nt.nodes.new("ShaderNodeMath"); fr.operation = "FRACT"; nt.links.new(sc_.outputs[0], fr.inputs[0])
            lt = nt.nodes.new("ShaderNodeMath"); lt.operation = "LESS_THAN"
            lt.inputs[1].default_value = 0.22 if axis == "X" else 0.5
            nt.links.new(fr.outputs[0], lt.inputs[0])
            acc = lt.outputs[0] if acc is None else acc
            if axis == "Y":
                mx_ = nt.nodes.new("ShaderNodeMath"); mx_.operation = "MAXIMUM"
                fine = nt.nodes.new("ShaderNodeMath"); fine.operation = "MULTIPLY"; fine.inputs[1].default_value = 4.0
                nt.links.new(sc_.outputs[0], fine.inputs[0])
                fr2 = nt.nodes.new("ShaderNodeMath"); fr2.operation = "FRACT"; nt.links.new(fine.outputs[0], fr2.inputs[0])
                lt2 = nt.nodes.new("ShaderNodeMath"); lt2.operation = "LESS_THAN"; lt2.inputs[1].default_value = 0.3
                nt.links.new(fr2.outputs[0], lt2.inputs[0])
                nt.links.new(acc, mx_.inputs[0]); nt.links.new(lt2.outputs[0], mx_.inputs[1])
                acc = mx_.outputs[0]
        cur = mix(cur, bc.outputs[0], acc)
    if noise:
        tex = nt.nodes.new("ShaderNodeTexNoise"); tex.inputs["Scale"].default_value = noise_scale
        tex.inputs["Detail"].default_value = 6.0
        nt.links.new(pos.outputs["Position"], tex.inputs["Vector"])
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs[3].default_value = 1 - noise; mr.inputs[4].default_value = 1 + noise * 0.6
        nt.links.new(tex.outputs["Fac"], mr.inputs[0])
        mul = nt.nodes.new("ShaderNodeVectorMath"); mul.operation = "MULTIPLY"
        nt.links.new(cur, mul.inputs[0]); nt.links.new(mr.outputs[0], mul.inputs[1])
        cur = mul.outputs[0]
    if frost:
        u0, u1, frgb = frost[:3]
        zmax = frost[3] if len(frost) > 3 else None
        add = nt.nodes.new("ShaderNodeMath"); add.operation = "ADD"
        nt.links.new(sep.outputs["X"], add.inputs[0]); nt.links.new(sep.outputs["Y"], add.inputs[1])
        uu = nt.nodes.new("ShaderNodeMath"); uu.operation = "MULTIPLY"; uu.inputs[1].default_value = R2
        nt.links.new(add.outputs[0], uu.inputs[0])
        tex = nt.nodes.new("ShaderNodeTexNoise"); tex.inputs["Scale"].default_value = 3.0
        tex.inputs["Detail"].default_value = 8.0
        nt.links.new(pos.outputs["Position"], tex.inputs["Vector"])
        ramp_u = nt.nodes.new("ShaderNodeMapRange"); ramp_u.inputs[1].default_value = u0; ramp_u.inputs[2].default_value = u1
        nt.links.new(uu.outputs[0], ramp_u.inputs[0])
        f2 = nt.nodes.new("ShaderNodeMath"); f2.operation = "ADD"
        nt.links.new(ramp_u.outputs[0], f2.inputs[0])
        nm = nt.nodes.new("ShaderNodeMath"); nm.operation = "SUBTRACT"; nm.inputs[1].default_value = 0.55
        nt.links.new(tex.outputs["Fac"], nm.inputs[0]); nt.links.new(nm.outputs[0], f2.inputs[1])
        if zmax:                                   # frost creeps up from the floor only so far
            zf = nt.nodes.new("ShaderNodeMath"); zf.operation = "MULTIPLY"; zf.inputs[1].default_value = -0.6 / zmax
            nt.links.new(sep.outputs["Z"], zf.inputs[0])
            f3 = nt.nodes.new("ShaderNodeMath"); f3.operation = "ADD"
            nt.links.new(f2.outputs[0], f3.inputs[0]); nt.links.new(zf.outputs[0], f3.inputs[1])
            f2 = f3
        st = nt.nodes.new("ShaderNodeMath"); st.operation = "GREATER_THAN"; st.inputs[1].default_value = 0.5
        nt.links.new(f2.outputs[0], st.inputs[0])
        fc = nt.nodes.new("ShaderNodeRGB"); fc.outputs[0].default_value = (*frgb, 1)
        soft = nt.nodes.new("ShaderNodeMath"); soft.operation = "MULTIPLY"; soft.inputs[1].default_value = 0.75
        nt.links.new(st.outputs[0], soft.inputs[0])
        cur = mix(cur, fc.outputs[0], soft.outputs[0])
    ramp = _ramp(nt, lit, mid, shade)
    mul = nt.nodes.new("ShaderNodeVectorMath"); mul.operation = "MULTIPLY"
    nt.links.new(cur, mul.inputs[0]); nt.links.new(ramp.outputs["Color"], mul.inputs[1])
    em = nt.nodes.new("ShaderNodeEmission"); nt.links.new(mul.outputs[0], em.inputs["Color"])
    shader = em.outputs[0]
    if alpha_noise:
        th, scale = alpha_noise
        tex = nt.nodes.new("ShaderNodeTexNoise"); tex.inputs["Scale"].default_value = scale
        tex.inputs["Detail"].default_value = 6.0
        nt.links.new(pos.outputs["Position"], tex.inputs["Vector"])
        gt = nt.nodes.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = th
        nt.links.new(tex.outputs["Fac"], gt.inputs[0])
        tr = nt.nodes.new("ShaderNodeBsdfTransparent"); mx = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(gt.outputs[0], mx.inputs["Fac"]); nt.links.new(tr.outputs[0], mx.inputs[1])
        nt.links.new(em.outputs[0], mx.inputs[2]); shader = mx.outputs[0]
    nt.links.new(shader, out.inputs["Surface"])
    _mats[key] = m
    return m


def ink():
    if "Ink" in _mats:
        return _mats["Ink"]
    m = bpy.data.materials.new("Ink"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); gg = nt.nodes.new("ShaderNodeNewGeometry")
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (0.035, 0.03, 0.025, 1)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent"); mx = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(gg.outputs["Backfacing"], mx.inputs["Fac"]); nt.links.new(em.outputs["Emission"], mx.inputs[1])
    nt.links.new(tr.outputs["BSDF"], mx.inputs[2]); nt.links.new(mx.outputs["Shader"], o.inputs["Surface"])
    _mats["Ink"] = m
    return m


def flat(name, rgb, alpha=1.0):
    """Unlit paint, for text, decals and graffiti."""
    key = "flat_" + name
    if key in _mats:
        return _mats[key]
    m = bpy.data.materials.new(key); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*rgb, 1)
    if alpha < 1:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent"); mx = nt.nodes.new("ShaderNodeMixShader")
        mx.inputs["Fac"].default_value = alpha
        nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2])
        nt.links.new(mx.outputs[0], o.inputs["Surface"])
    else:
        nt.links.new(em.outputs[0], o.inputs["Surface"])
    _mats[key] = m
    return m


# ---------------------------------------------------------------- mesh building
class Builder:
    """Collects boxes and cylinders in a local frame into one mesh with several materials."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.mats = []

    def mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def box(self, x0, x1, y0, y1, z0, z1, mat, M=None, top_mat=None):
        vs = []
        for x in (x0, x1):
            for y in (y0, y1):
                for z in (z0, z1):
                    p = Vector((x, y, z))
                    vs.append(self.bm.verts.new(M @ p if M else p))
        faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        idx = self.mi(mat)
        tidx = self.mi(top_mat) if top_mat else idx
        for k, f in enumerate(faces):
            face = self.bm.faces.new([vs[i] for i in f])
            face.material_index = tidx if k == 5 else idx
        return vs

    def cyl(self, p0, p1, r, mat, seg=12, cap=True, r1=None):
        p0, p1 = Vector(p0), Vector(p1)
        ax = (p1 - p0); L = ax.length; ax.normalize()
        t = Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0))
        n = ax.cross(t).normalized(); b = ax.cross(n)
        r1 = r if r1 is None else r1
        ring0 = [self.bm.verts.new(p0 + r * (math.cos(2 * math.pi * k / seg) * n + math.sin(2 * math.pi * k / seg) * b)) for k in range(seg)]
        ring1 = [self.bm.verts.new(p1 + r1 * (math.cos(2 * math.pi * k / seg) * n + math.sin(2 * math.pi * k / seg) * b)) for k in range(seg)]
        idx = self.mi(mat)
        for k in range(seg):
            f = self.bm.faces.new([ring0[k], ring0[(k + 1) % seg], ring1[(k + 1) % seg], ring1[k]]); f.material_index = idx
        if cap:
            f = self.bm.faces.new(ring0[::-1]); f.material_index = idx
            if r1 > 0.0005:
                f = self.bm.faces.new(ring1); f.material_index = idx
        return ring0, ring1

    def quad(self, pts, mat):
        vs = [self.bm.verts.new(Vector(p)) for p in pts]
        f = self.bm.faces.new(vs); f.material_index = self.mi(mat)

    def finish(self, outline=0.012, collection=None):
        me = bpy.data.meshes.new(self.name)
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])
        self.bm.to_mesh(me); self.bm.free()
        for m in self.mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(self.name, me)
        (collection or bpy.context.scene.collection).objects.link(ob)
        if outline:
            me.materials.append(ink())
            sol = ob.modifiers.new("Outline", "SOLIDIFY"); sol.thickness = -outline
            sol.use_flip_normals = True; sol.use_rim = False; sol.material_offset = len(self.mats)
        return ob


def text_obj(body, font, size, mat, extrude=0.002, align="CENTER"):
    cu = bpy.data.curves.new("Text", "FONT"); cu.body = body
    cu.font = bpy.data.fonts.load(font, check_existing=True)
    cu.size = size; cu.extrude = extrude; cu.align_x = align; cu.align_y = "CENTER"
    ob = bpy.data.objects.new("Text", cu); bpy.context.scene.collection.objects.link(ob)
    cu.materials.append(mat)
    return ob


# ---------------------------------------------------------------- placement
FACING = {"-v": (0, -1), "+v": (0, 1), "-u": (-1, 0), "+u": (1, 0)}


def facing_frame(facing):
    """Local +y points out of the wall (the prop's front), +x along the wall."""
    fu, fv = FACING[facing]
    fx, fy = g(fu, fv)
    ang = math.atan2(fy, fx) - math.pi / 2
    return ang


def place(ob_list, u, v, facing, z=0.0):
    x, y = g(u, v)
    ang = facing_frame(facing)
    for ob in ob_list:
        ob.matrix_world = Matrix.Translation((x, y, z)) @ Matrix.Rotation(ang, 4, "Z") @ ob.matrix_world


def footprint(u, v, facing, length, depth):
    """Plan-space rectangle (u0, u1, v0, v1) covered by a prop whose back is at (u, v)."""
    fu, fv = FACING[facing]
    ru, rv = (fv, -fu)                  # along the wall
    cu_, cv_ = u + fu * depth / 2, v + fv * depth / 2
    hu = abs(fu) * depth / 2 + abs(ru) * length / 2
    hv = abs(fv) * depth / 2 + abs(rv) * length / 2
    return [round(cu_ - hu, 3), round(cu_ + hu, 3), round(cv_ - hv, 3), round(cv_ + hv, 3)]


# ---------------------------------------------------------------- colours
STEEL_PAINT = (0.36, 0.42, 0.37)
OLIVE = (0.36, 0.38, 0.27)
CREAM = (0.78, 0.74, 0.62)
WOOD = (0.42, 0.29, 0.17)
PLY = (0.62, 0.5, 0.33)
RUST = (0.45, 0.24, 0.12)
BLANKETS = [(0.42, 0.38, 0.33), (0.33, 0.37, 0.42), (0.38, 0.40, 0.30), (0.46, 0.33, 0.30), (0.5, 0.47, 0.4)]


# ---------------------------------------------------------------- props (local frame, back at y=0, front +y)
def bunk(name, k=0, stripped=False):
    b = Builder(name)
    frame = toon("BunkFrame", (0.32, 0.36, 0.33), noise=0.08)
    mat = toon("Mattress", (0.55, 0.52, 0.45), noise=0.1, noise_scale=12)
    L, D = 2.0, 0.9
    for x in (-L / 2 + 0.03, L / 2 - 0.03):
        for y in (0.05, D - 0.05):
            b.box(x - 0.025, x + 0.025, y - 0.025, y + 0.025, 0, 1.68, frame)
    for zz in (0.36, 1.26):
        b.box(-L / 2, L / 2, 0.02, 0.08, zz - 0.06, zz, frame)
        b.box(-L / 2, L / 2, D - 0.08, D - 0.02, zz - 0.06, zz, frame)
        b.box(-L / 2 + 0.05, L / 2 - 0.05, 0.08, D - 0.08, zz - 0.03, zz, frame)
        b.box(-L / 2 + 0.06, L / 2 - 0.06, 0.08, D - 0.08, zz, zz + 0.12, mat)
        if not stripped:
            bl = toon(f"Blanket{(k + int(zz * 10)) % 5}", BLANKETS[(k + int(zz * 10)) % 5], noise=0.12, noise_scale=9)
            b.box(-L / 2 + 0.3, L / 2 - 0.04, 0.06, D - 0.06, zz + 0.12, zz + 0.17, bl)
            b.box(-L / 2 + 0.3, -L / 2 + 0.36, 0.06, D - 0.06, zz + 0.0, zz + 0.17, bl)
            b.box(-L / 2 + 0.08, -L / 2 + 0.38, 0.2, D - 0.2, zz + 0.12, zz + 0.22, toon("Pillow", (0.72, 0.7, 0.64)))
    for zz in (0.6, 0.85, 1.1):                                 # ladder
        b.box(L / 2 - 0.06, L / 2, 0.1, D - 0.1, zz - 0.015, zz + 0.015, frame)
    return b.finish(), (L, D)


def bed(name, k=1):
    b = Builder(name)
    frame = toon("BunkFrame", (0.32, 0.36, 0.33), noise=0.08)
    L, D = 2.0, 0.9
    for x in (-L / 2 + 0.03, L / 2 - 0.03):
        for y in (0.05, D - 0.05):
            b.box(x - 0.025, x + 0.025, y - 0.025, y + 0.025, 0, 0.5 if x < 0 else 0.42, frame)
    b.box(-L / 2, -L / 2 + 0.05, 0.03, D - 0.03, 0.2, 0.75, frame)            # headboard
    b.box(-L / 2, L / 2, 0.05, D - 0.05, 0.34, 0.4, frame)
    b.box(-L / 2 + 0.06, L / 2 - 0.06, 0.08, D - 0.08, 0.4, 0.52, toon("Mattress", (0.55, 0.52, 0.45), noise=0.1, noise_scale=12))
    bl = toon(f"Blanket{k}", BLANKETS[k], noise=0.12, noise_scale=9)
    b.box(-L / 2 + 0.35, L / 2 - 0.02, 0.04, D - 0.04, 0.5, 0.57, bl)
    b.box(L / 2 - 0.06, L / 2 - 0.02, 0.04, D - 0.04, 0.3, 0.57, bl)
    b.box(-L / 2 + 0.1, -L / 2 + 0.42, 0.2, D - 0.2, 0.52, 0.62, toon("Pillow", (0.72, 0.7, 0.64)))
    return b.finish(), (L, D)


def locker(name, width=0.55, open_door=False):
    b = Builder(name)
    body = toon("Locker", OLIVE, noise=0.1, noise_scale=8)
    dark = toon("LockerDark", (0.12, 0.13, 0.1))
    D, H = 0.5, 1.85
    b.box(-width / 2, width / 2, 0.0, D, 0, H, body)
    n = max(1, round(width / 0.5))
    w = width / n
    for i in range(n):
        x0 = -width / 2 + i * w
        b.box(x0 + w - 0.006, x0 + w + 0.006, D, D + 0.004, 0.05, H - 0.05, dark)        # door seam
        for zz in (1.55, 1.6, 1.65):
            b.box(x0 + 0.1, x0 + w - 0.1, D, D + 0.006, zz, zz + 0.018, dark)            # vents
        b.box(x0 + w - 0.08, x0 + w - 0.05, D, D + 0.03, 0.95, 1.1, toon("Steel", (0.5, 0.5, 0.5)))
    if open_door:
        b.box(width / 2, width / 2 + 0.02, D, D + w, 0.05, H - 0.05, body)
        b.box(-width / 2 + 0.03, width / 2 - 0.03, D - 0.02, D, 0.06, H - 0.06, dark)
    return b.finish(), (width, D)


def desk(name, with_lamp=True):
    b = Builder(name)
    wood = toon("DeskWood", WOOD, noise=0.12, noise_scale=10)
    L, D = 1.2, 0.6
    b.box(-L / 2, L / 2, 0, D, 0.72, 0.76, wood)
    for x in (-L / 2 + 0.04, L / 2 - 0.04):
        for y in (0.04, D - 0.04):
            b.box(x - 0.025, x + 0.025, y - 0.025, y + 0.025, 0, 0.72, wood)
    b.box(L / 2 - 0.45, L / 2 - 0.04, 0.04, D - 0.02, 0.45, 0.72, wood)
    b.box(L / 2 - 0.4, L / 2 - 0.09, D - 0.02, D, 0.56, 0.62, toon("Steel", (0.5, 0.5, 0.5)))
    paper = toon("Paper", (0.85, 0.83, 0.76))
    b.box(-0.35, -0.05, 0.15, 0.42, 0.76, 0.765, paper)
    b.box(-0.3, 0.0, 0.2, 0.45, 0.765, 0.77, paper)
    b.cyl((0.15, 0.35, 0.76), (0.15, 0.35, 0.86), 0.04, toon("Mug", (0.62, 0.22, 0.16)))
    if with_lamp:
        lamp = toon("LampGreen", (0.18, 0.32, 0.22))
        b.cyl((-0.45, 0.2, 0.76), (-0.45, 0.2, 0.79), 0.08, lamp)
        b.cyl((-0.45, 0.2, 0.79), (-0.4, 0.25, 1.1), 0.012, toon("Steel", (0.5, 0.5, 0.5)))
        b.cyl((-0.4, 0.25, 1.1), (-0.3, 0.33, 1.02), 0.11, lamp, r1=0.04)
    return b.finish(), (L, D)


def chair(name, overturned=False):
    b = Builder(name)
    wood = toon("ChairWood", (0.4, 0.28, 0.17), noise=0.1)
    M = None
    if overturned:
        M = Matrix.Translation((0, 0.25, 0.22)) @ Matrix.Rotation(math.radians(95), 4, "X") @ Matrix.Translation((0, -0.22, -0.2))
    b.box(-0.21, 0.21, 0.05, 0.47, 0.42, 0.46, wood, M)
    for x in (-0.18, 0.18):
        for y in (0.08, 0.44):
            b.box(x - 0.02, x + 0.02, y - 0.02, y + 0.02, 0, 0.42, wood, M)
    b.box(-0.2, 0.2, 0.05, 0.09, 0.46, 0.9, wood, M)
    return b.finish(), (0.5, 0.5)


def table(name, L=1.2, D=0.7, k=0):
    b = Builder(name)
    wood = toon("TableWood", (0.45, 0.33, 0.2), noise=0.12, noise_scale=10)
    b.box(-L / 2, L / 2, 0, D, 0.72, 0.76, wood)
    for x in (-L / 2 + 0.05, L / 2 - 0.05):
        for y in (0.05, D - 0.05):
            b.box(x - 0.03, x + 0.03, y - 0.03, y + 0.03, 0, 0.72, wood)
    b.cyl((-0.2, 0.3, 0.76), (-0.2, 0.3, 0.84), 0.035, toon("Tin", (0.55, 0.55, 0.52)))
    b.box(0.05, 0.3, 0.2, 0.4, 0.76, 0.79, toon("Cards", (0.82, 0.8, 0.72)))
    return b.finish(), (L, D)


def stool(name):
    b = Builder(name)
    wood = toon("ChairWood", (0.4, 0.28, 0.17), noise=0.1)
    b.cyl((0, 0.18, 0.44), (0, 0.18, 0.47), 0.16, wood)
    for a in range(3):
        aa = 2 * math.pi * a / 3
        b.cyl((0.1 * math.cos(aa), 0.18 + 0.1 * math.sin(aa), 0.44), (0.15 * math.cos(aa), 0.18 + 0.15 * math.sin(aa), 0), 0.018, wood, seg=6)
    return b.finish(), (0.36, 0.36)


def radiator(name, sections=10, state="working"):
    """Cast-iron column radiator on wall brackets, fed from below."""
    b = Builder(name)
    rgb = {"working": CREAM, "dead": (0.62, 0.56, 0.46), "frozen": (0.72, 0.8, 0.84)}[state]
    paint = toon(f"Radiator_{state}", rgb, noise=0.15 if state != "working" else 0.06, noise_scale=14)
    pipe = toon("PipeSteel", (0.38, 0.38, 0.36), noise=0.08)
    pitch = 0.065
    L = sections * pitch
    for i in range(sections):
        x = -L / 2 + pitch * (i + 0.5)
        b.box(x - 0.026, x + 0.026, 0.05, 0.16, 0.14, 0.72, paint)
    b.box(-L / 2, L / 2, 0.08, 0.13, 0.66, 0.7, paint)
    b.box(-L / 2, L / 2, 0.08, 0.13, 0.16, 0.2, paint)
    b.cyl((-L / 2 - 0.05, 0.1, 0.0), (-L / 2 - 0.05, 0.1, 0.18), 0.018, pipe)
    b.cyl((-L / 2 - 0.05, 0.1, 0.18), (-L / 2, 0.1, 0.18), 0.018, pipe)
    b.cyl((-L / 2 - 0.05, 0.1, 0.3), (-L / 2 - 0.05, 0.15, 0.3), 0.04, toon("ValveRed", (0.5, 0.12, 0.1)), seg=10)
    if state == "frozen":
        ice = toon("Ice", (0.82, 0.9, 0.95))
        for i in range(0, sections, 2):
            x = -L / 2 + pitch * (i + 0.5)
            b.cyl((x, 0.11, 0.14), (x, 0.11, 0.04), 0.012, ice, seg=6, r1=0.0)
    return b.finish(), (L + 0.1, 0.18)


def curtain(name, k=0, width=0.65, height=1.75):
    """One blanket pinned to a wire: a hanging panel with soft folds (free-standing partition)."""
    b = Builder(name)
    cloth = toon(f"Blanket{k % 5}", BLANKETS[k % 5], noise=0.12, noise_scale=9)
    nx, nz = 10, 6
    grid = []
    for iz in range(nz + 1):
        row = []
        for ix in range(nx + 1):
            x = -width / 2 + width * ix / nx
            z = 2.0 - height * iz / nz
            y = 0.04 * math.sin(ix / nx * math.pi * 3 + k) * (0.4 + 0.6 * iz / nz)
            row.append(b.bm.verts.new((x, y, z)))
        grid.append(row)
    idx = b.mi(cloth)
    for iz in range(nz):
        for ix in range(nx):
            f = b.bm.faces.new([grid[iz][ix], grid[iz][ix + 1], grid[iz + 1][ix + 1], grid[iz + 1][ix]]); f.material_index = idx
    wire = toon("Wire", (0.3, 0.3, 0.3))
    b.cyl((-width / 2 - 0.02, 0, 2.01), (width / 2 + 0.02, 0, 2.01), 0.006, wire, seg=6)
    ob = b.finish(outline=0.008)
    ob.modifiers.new("Thick", "SOLIDIFY").thickness = 0.015
    ob.modifiers.move(1, 0)
    return ob, (width, 0.1)


def toolbox(name):
    b = Builder(name)
    red = toon("ToolRed", (0.55, 0.14, 0.1), noise=0.08)
    b.box(-0.28, 0.28, 0.02, 0.26, 0, 0.24, red)
    b.box(-0.2, 0.2, 0.12, 0.16, 0.24, 0.3, toon("Steel", (0.5, 0.5, 0.5)))
    bottle = toon("GasBottle", (0.2, 0.35, 0.5))
    b.cyl((0.42, 0.14, 0), (0.42, 0.14, 0.55), 0.08, bottle)
    b.cyl((0.42, 0.14, 0.55), (0.42, 0.14, 0.62), 0.03, toon("Brass", (0.6, 0.48, 0.2)))
    b.cyl((0.6, 0.14, 0), (0.6, 0.14, 0.5), 0.07, toon("GasRed", (0.55, 0.18, 0.14)))
    return b.finish(), (1.0, 0.3)


def crate(name, h=0.55):
    b = Builder(name)
    wood = toon("CrateWood", (0.5, 0.4, 0.25), noise=0.15, noise_scale=10)
    dark = toon("CrateDark", (0.3, 0.22, 0.13))
    b.box(-0.3, 0.3, 0.0, 0.6, 0, h, wood)
    for zz in (0.12, h - 0.12):
        b.box(-0.31, 0.31, -0.01, 0.61, zz - 0.02, zz + 0.02, dark)
    return b.finish(), (0.62, 0.62)


def bucket(name):
    b = Builder(name)
    b.cyl((0, 0.18, 0), (0, 0.18, 0.3), 0.13, toon("Zinc", (0.55, 0.56, 0.55)), r1=0.16)
    return b.finish(), (0.34, 0.34)


def shelf(name):
    b = Builder(name)
    frame = toon("ShelfSteel", (0.42, 0.44, 0.42), noise=0.08)
    L, D = 1.1, 0.45
    for x in (-L / 2, L / 2):
        for y in (0.02, D - 0.02):
            b.box(x - 0.02, x + 0.02, y - 0.02, y + 0.02, 0, 1.9, frame)
    for zz in (0.12, 0.6, 1.1, 1.6):
        b.box(-L / 2, L / 2, 0.0, D, zz, zz + 0.025, frame)
    for i, zz in enumerate((0.145, 0.625, 1.125)):
        for j in range(3):
            c = BLANKETS[(i * 3 + j) % 5]
            b.box(-L / 2 + 0.05 + j * 0.34, -L / 2 + 0.33 + j * 0.34, 0.05, D - 0.05, zz, zz + 0.14 + 0.04 * j,
                  toon(f"Blanket{(i * 3 + j) % 5}", c, noise=0.12, noise_scale=9))
    b.box(-0.4, 0.1, 0.05, 0.4, 1.625, 1.85, toon("Carton", (0.55, 0.45, 0.3), noise=0.1))
    return b.finish(), (L, D)


def sinks(name, n=3):
    b = Builder(name)
    enamel = toon("Enamel", (0.8, 0.8, 0.76), noise=0.06)
    dark = toon("SinkDark", (0.2, 0.22, 0.22))
    pipe = toon("PipeSteel", (0.38, 0.38, 0.36), noise=0.08)
    L = 0.7 * n
    for i in range(n):
        x = -L / 2 + 0.35 + i * 0.7
        b.box(x - 0.26, x + 0.26, 0.02, 0.45, 0.7, 0.85, enamel)
        b.box(x - 0.2, x + 0.2, 0.08, 0.4, 0.84, 0.851, dark)
        b.cyl((x, 0.05, 0.85), (x, 0.05, 1.0), 0.015, pipe)
        b.cyl((x, 0.05, 1.0), (x, 0.17, 1.0), 0.015, pipe)
        b.cyl((x, 0.2, 0.0), (x, 0.2, 0.7), 0.025, pipe)
    return b.finish(), (L, 0.45)


def stall(name):
    b = Builder(name)
    panel = toon("StallPanel", (0.45, 0.5, 0.48), noise=0.08)
    b.box(-0.45, -0.42, 0, 1.2, 0.12, 1.85, panel)
    b.box(0.42, 0.45, 0, 1.2, 0.12, 1.85, panel)
    b.box(-0.42, 0.42, 1.17, 1.2, 0.12, 1.85, panel)
    b.box(-0.15, 0.15, 0.0, 0.45, 0.0, 0.42, toon("Enamel", (0.8, 0.8, 0.76), noise=0.06))
    return b.finish(), (0.9, 1.2)


def laundry(name, k=0):
    b = Builder(name)
    pole = toon("Wire", (0.3, 0.3, 0.3))
    L = 1.8
    for x in (-L / 2, L / 2):
        b.cyl((x, 0.1, 0), (x, 0.1, 1.8), 0.02, pole, seg=8)
    b.cyl((-L / 2, 0.1, 1.75), (L / 2, 0.1, 1.75), 0.006, pole, seg=6)
    for i in range(3):
        c = toon(f"Blanket{(k + i) % 5}", BLANKETS[(k + i) % 5], noise=0.12, noise_scale=9)
        x = -L / 2 + 0.15 + i * 0.55
        b.box(x, x + 0.45, 0.08, 0.12, 1.0 + 0.1 * (i % 2), 1.75, c)
    return b.finish(), (L, 0.25)


def pump(name):
    b = Builder(name)
    paint = toon("PumpGreen", (0.28, 0.4, 0.33), noise=0.1)
    steel = toon("PipeSteel", (0.38, 0.38, 0.36), noise=0.08)
    b.box(-0.6, 0.6, 0.0, 0.7, 0, 0.15, toon("ConcretePlinth", (0.5, 0.5, 0.47), noise=0.1))
    b.cyl((-0.5, 0.35, 0.45), (0.05, 0.35, 0.45), 0.24, paint)
    b.cyl((0.05, 0.35, 0.45), (0.45, 0.35, 0.45), 0.2, toon("PumpGrey", (0.45, 0.47, 0.46), noise=0.08), seg=16)
    b.cyl((0.25, 0.35, 0.65), (0.25, 0.35, 1.6), 0.07, steel)
    b.cyl((0.45, 0.35, 0.45), (0.6, 0.35, 0.45), 0.07, steel)
    b.cyl((0.25, 0.35, 1.0), (0.25, 0.47, 1.0), 0.13, toon("ValveRed", (0.5, 0.12, 0.1)), seg=12)
    return b.finish(), (1.2, 0.7)


def workbench(name):
    b = Builder(name)
    wood = toon("BenchWood", (0.38, 0.27, 0.16), noise=0.14, noise_scale=10)
    steel = toon("Steel", (0.5, 0.5, 0.5))
    L, D = 1.8, 0.7
    b.box(-L / 2, L / 2, 0, D, 0.84, 0.9, wood)
    for x in (-L / 2 + 0.05, L / 2 - 0.05):
        for y in (0.05, D - 0.05):
            b.box(x - 0.035, x + 0.035, y - 0.035, y + 0.035, 0, 0.84, wood)
    b.box(-L / 2 + 0.05, L / 2 - 0.05, 0.05, D - 0.05, 0.2, 0.24, wood)
    b.box(0.5, 0.75, 0.45, 0.65, 0.9, 1.05, steel)                         # vice
    b.box(-0.6, -0.1, 0.1, 0.4, 0.9, 0.95, toon("ToolRed", (0.55, 0.14, 0.1), noise=0.08))
    return b.finish(), (L, D)


# ---------------------------------------------------------------- Level 2 west: commons, kitchen, clinic, school, archive
def bench(name, L=2.2):
    b = Builder(name)
    wood = toon("BenchSeat", (0.43, 0.31, 0.19), noise=0.14, noise_scale=10)
    D = 0.32
    b.box(-L / 2, L / 2, 0.0, D, 0.42, 0.46, wood)
    for x in (-L / 2 + 0.12, 0.0, L / 2 - 0.12):
        b.box(x - 0.03, x + 0.03, 0.04, D - 0.04, 0.0, 0.42, wood)
    b.box(-L / 2 + 0.1, L / 2 - 0.1, D / 2 - 0.02, D / 2 + 0.02, 0.12, 0.16, wood)      # stretcher
    b.box(L / 2 - 0.5, L / 2 - 0.36, 0.02, D - 0.02, 0.46, 0.47, toon("PatchWood", (0.56, 0.44, 0.28)))  # a repair
    return b.finish(), (L, D)


def stove(name):
    """Cast-iron cooking range on legs, two big pots, a flue going up the wall."""
    b = Builder(name)
    iron = toon("StoveIron", (0.16, 0.16, 0.15), noise=0.1)
    steel = toon("Steel", (0.5, 0.5, 0.5))
    L, D = 1.6, 0.8
    b.box(-L / 2, L / 2, 0.05, D, 0.12, 0.88, iron)
    for x in (-L / 2 + 0.06, L / 2 - 0.06):
        for y in (0.1, D - 0.06):
            b.box(x - 0.04, x + 0.04, y - 0.04, y + 0.04, 0, 0.12, iron)
    for x in (-0.55, 0.0, 0.55):                                             # oven doors
        b.box(x - 0.22, x + 0.22, D, D + 0.02, 0.25, 0.65, toon("StoveDoor", (0.24, 0.23, 0.21)))
        b.box(x - 0.12, x + 0.12, D + 0.02, D + 0.05, 0.6, 0.62, steel)
    b.box(-L / 2 + 0.05, L / 2 - 0.05, 0.1, D - 0.05, 0.88, 0.9, toon("Hotplate", (0.3, 0.27, 0.25)))
    b.cyl((-0.4, 0.45, 0.9), (-0.4, 0.45, 1.25), 0.24, toon("PotAlu", (0.6, 0.6, 0.58), noise=0.08), seg=16)
    b.cyl((0.35, 0.4, 0.9), (0.35, 0.4, 1.08), 0.2, toon("PotEnamel", (0.55, 0.2, 0.14)), seg=16)
    b.cyl((0.0, 0.1, 0.9), (0.0, 0.1, 2.6), 0.09, iron)                     # flue
    return b.finish(), (L, D)


def counter(name, L=2.0, hatch=False):
    """Kitchen or serving counter: steel-topped cupboards; with hatch=True, the Exchange's trading counter."""
    b = Builder(name)
    body = toon("CounterBody", (0.38, 0.42, 0.4), noise=0.1)
    top = toon("CounterTop", (0.58, 0.58, 0.56), noise=0.06)
    D = 0.62
    b.box(-L / 2, L / 2, 0.0, D, 0.0, 0.88, body)
    b.box(-L / 2 - 0.02, L / 2 + 0.02, -0.02, D + 0.03, 0.88, 0.92, top)
    n = max(1, int(L / 0.6))
    for i in range(n):
        x = -L / 2 + (i + 0.5) * L / n
        b.box(x - L / n / 2 + 0.03, x + L / n / 2 - 0.03, D, D + 0.01, 0.08, 0.8, toon("CounterDoor", (0.33, 0.37, 0.35)))
        b.box(x - 0.06, x + 0.06, D + 0.01, D + 0.03, 0.7, 0.73, toon("Steel", (0.5, 0.5, 0.5)))
    if hatch:                                                # goods for trade and a tin cash box
        for i, c in enumerate([(0.62, 0.22, 0.16), (0.55, 0.5, 0.3), (0.3, 0.35, 0.45)]):
            b.box(-L / 2 + 0.15 + i * 0.25, -L / 2 + 0.35 + i * 0.25, 0.15, 0.4, 0.92, 1.05 + 0.04 * i, toon(f"Goods{i}", c, noise=0.1))
        b.box(0.3, 0.6, 0.2, 0.45, 0.92, 1.02, toon("CashTin", (0.42, 0.45, 0.38), noise=0.1))
        b.box(-L / 2, L / 2, 0.0, 0.05, 0.92, 1.9, toon("HatchFrame", (0.4, 0.31, 0.2), noise=0.12))
    else:
        b.cyl((-0.5, 0.3, 0.92), (-0.5, 0.3, 1.1), 0.12, toon("PotAlu", (0.6, 0.6, 0.58), noise=0.08), seg=12)
        b.box(0.1, 0.55, 0.12, 0.45, 0.92, 0.95, toon("ChopBoard", (0.55, 0.4, 0.24)))
    return b.finish(), (L, D)


def cabinet(name):
    """Steel filing cabinet, four drawers."""
    b = Builder(name)
    body = toon("FilingGrey", (0.45, 0.47, 0.44), noise=0.08)
    D = 0.62
    b.box(-0.24, 0.24, 0.0, D, 0.0, 1.32, body)
    for k in range(4):
        z = 0.06 + k * 0.32
        b.box(-0.21, 0.21, D, D + 0.01, z, z + 0.28, toon("FilingDrawer", (0.4, 0.42, 0.39)))
        b.box(-0.07, 0.07, D + 0.01, D + 0.03, z + 0.2, z + 0.23, toon("Steel", (0.5, 0.5, 0.5)))
        b.box(-0.05, 0.05, D + 0.01, D + 0.012, z + 0.12, z + 0.16, toon("Paper", (0.85, 0.83, 0.76)))
    return b.finish(), (0.48, D)


def medscreen(name):
    """Three-leaf folding screen between ward beds."""
    b = Builder(name)
    frame = toon("ScreenFrame", (0.6, 0.62, 0.6), noise=0.05)
    cloth = toon("ScreenCloth", (0.74, 0.78, 0.76), noise=0.1, noise_scale=10)
    for i, x in enumerate((-0.6, 0.0, 0.6)):
        y = 0.12 if i == 1 else 0.0
        b.box(x - 0.29, x + 0.29, y, y + 0.03, 0.18, 1.7, cloth)
        for xx in (x - 0.3, x + 0.3):
            b.cyl((xx, y + 0.015, 0.0), (xx, y + 0.015, 1.75), 0.015, frame, seg=6)
    return b.finish(), (1.8, 0.2)


def medcab(name):
    """White medicine cabinet with glass doors and too few bottles."""
    b = Builder(name)
    white = toon("MedWhite", (0.8, 0.8, 0.76), noise=0.08)
    D = 0.42
    b.box(-0.45, 0.45, 0.0, D, 0.0, 1.8, white)
    b.box(-0.41, 0.41, D - 0.01, D + 0.004, 0.95, 1.72, toon("MedGlass", (0.5, 0.6, 0.62)))
    for k, z in enumerate((1.0, 1.35)):
        b.box(-0.41, 0.41, 0.05, D - 0.02, z, z + 0.02, white)
        for j in range(2 + k):
            x = -0.3 + j * 0.22
            b.cyl((x, 0.2, z + 0.02), (x, 0.2, z + 0.18), 0.04, toon(f"Bottle{(j + k) % 3}", [(0.45, 0.3, 0.12), (0.3, 0.45, 0.4), (0.75, 0.75, 0.72)][(j + k) % 3]), seg=8)
    b.box(-0.41, 0.41, D, D + 0.01, 0.06, 0.9, toon("MedDoor", (0.74, 0.74, 0.7)))
    b.box(-0.1, 0.1, D + 0.01, D + 0.014, 0.6, 0.8, flat("RedCross", (0.7, 0.1, 0.08)))
    return b.finish(), (0.9, D)


def schooldesk(name):
    """A two-seat school desk with its bench joined on."""
    b = Builder(name)
    wood = toon("SchoolWood", (0.5, 0.37, 0.22), noise=0.12, noise_scale=10)
    frame = toon("SchoolFrame", (0.25, 0.3, 0.28), noise=0.08)
    L = 1.1
    b.box(-L / 2, L / 2, 0.0, 0.42, 0.68, 0.72, wood)                       # slanted lid, roughly
    b.box(-L / 2, L / 2, 0.0, 0.05, 0.72, 0.78, wood)
    b.box(-L / 2, L / 2, 0.55, 0.85, 0.4, 0.44, wood)                        # seat
    for x in (-L / 2 + 0.05, L / 2 - 0.05):
        b.box(x - 0.025, x + 0.025, 0.05, 0.8, 0.0, 0.05, frame)
        b.box(x - 0.025, x + 0.025, 0.15, 0.2, 0.05, 0.68, frame)
        b.box(x - 0.025, x + 0.025, 0.68, 0.73, 0.05, 0.4, frame)
    b.cyl((0.3, 0.12, 0.72), (0.3, 0.12, 0.74), 0.03, toon("Inkwell", (0.15, 0.15, 0.2)), seg=8)
    b.box(-0.35, -0.05, 0.12, 0.34, 0.72, 0.73, toon("Paper", (0.85, 0.83, 0.76)))
    return b.finish(), (L, 0.85)


def sacks(name):
    """A pile of grain and potato sacks from the hydroponics bays."""
    b = Builder(name)
    for i, (x, y, z, s) in enumerate(((-0.3, 0.25, 0.0, 1.0), (0.25, 0.3, 0.0, 0.95), (0.0, 0.3, 0.32, 0.9))):
        m = toon(f"Sack{i % 2}", [(0.6, 0.53, 0.38), (0.52, 0.46, 0.33)][i % 2], noise=0.18, noise_scale=12)
        b.box(x - 0.26 * s, x + 0.26 * s, y - 0.2 * s, y + 0.2 * s, z, z + 0.34 * s, m)
        b.box(x - 0.1 * s, x + 0.1 * s, y - 0.08 * s, y + 0.08 * s, z + 0.34 * s, z + 0.42 * s, m)
    return b.finish(), (1.1, 0.6)


def file_shelf(name, k=0):
    """Archive shelving: box files, bundles of paper and a few loose ledgers."""
    b = Builder(name)
    frame = toon("ShelfSteel", (0.42, 0.44, 0.42), noise=0.08)
    L, D = 1.1, 0.42
    for x in (-L / 2, L / 2):
        for y in (0.02, D - 0.02):
            b.box(x - 0.02, x + 0.02, y - 0.02, y + 0.02, 0, 2.0, frame)
    boxes = [(0.5, 0.42, 0.3), (0.42, 0.4, 0.36), (0.55, 0.5, 0.38), (0.36, 0.33, 0.28)]
    for i, zz in enumerate((0.1, 0.55, 1.0, 1.45)):
        b.box(-L / 2, L / 2, 0.0, D, zz, zz + 0.025, frame)
        x = -L / 2 + 0.04
        j = 0
        while x < L / 2 - 0.12:
            w = 0.08 + 0.03 * ((i * 7 + j * 3 + k) % 3)
            h = 0.3 - 0.04 * ((i + j + k) % 2)
            if (i * 5 + j * 2 + k) % 9 == 4:                 # a gap where a file was taken
                x += w; j += 1; continue
            c = boxes[(i + j + k) % 4]
            b.box(x, x + w - 0.01, 0.06, D - 0.06, zz + 0.025, zz + 0.025 + h, toon(f"BoxFile{(i + j + k) % 4}", c, noise=0.1))
            x += w; j += 1
    return b.finish(), (L, D)
