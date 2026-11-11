"""Sculpt-from-primitives kit for Silo 81 characters made in Blender from code.

The method (in place of hand sculpting): every form is a metaball element (ellipsoids and capsules for
muscles, bones and cloth volumes, negative elements to carve sockets and mouths), polygonised at a fine
resolution into a smooth "high" mesh, detailed with displacement functions (folds, seams, lesions), then
retopologised with QuadriFlow into a game mesh. Colour is painted procedurally on the high mesh (with
cavity from pointiness) and baked, together with ambient occlusion, onto the game mesh's UVs: detail
lives in the painted colour, which is all the game's toon shader reads.

Conventions: metres, Z up, the character faces -Y (glTF +Z), feet on z = 0.
"""
import math, random
import bpy, bmesh
import numpy as np
from mathutils import Vector, Matrix, Quaternion, noise
from mathutils.bvhtree import BVHTree


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    return sc


# ------------------------------------------------------------------ metaball sculpting
class Sculpt:
    """One metaball object; add forms, then .mesh() polygonises it."""
    def __init__(self, name, res=0.006, threshold=0.6):
        self.mb = bpy.data.metaballs.new(name)
        self.mb.resolution = res; self.mb.render_resolution = res; self.mb.threshold = threshold
        self.ob = bpy.data.objects.new(name, self.mb)
        bpy.context.scene.collection.objects.link(self.ob)
        self.name = name

    def vis(self, stiff):
        """Visible radius as a fraction of the element radius: the field (1 - (d/R)^2)^3 * stiffness
        meets the threshold at d = R * sqrt(1 - (threshold / stiffness)^(1/3))."""
        return math.sqrt(max(1e-4, 1.0 - (self.mb.threshold / stiff) ** (1.0 / 3.0)))

    def _el(self, kind, co, r, stiff=2.0, neg=False):
        """r is the radius the surface should have (the element's own radius is larger, see vis)."""
        e = self.mb.elements.new()
        e.type = kind; e.co = Vector(co); e.radius = r / self.vis(stiff); e.stiffness = stiff; e.use_negative = neg
        return e

    def ball(self, co, r, stiff=2.0, neg=False):
        return self._el("BALL", co, r, stiff, neg)

    def ellipsoid(self, co, size, r=None, stiff=2.0, neg=False, rot=None):
        """size: half extents (x, y, z) in metres (before any rotation)."""
        m = max(size)
        e = self._el("ELLIPSOID", co, r if r else m, stiff, neg)
        # sizes are factors of the element radius, which is already scaled up for the threshold
        e.size_x, e.size_y, e.size_z = size[0] / m, size[1] / m, size[2] / m
        if rot is not None:
            e.rotation = rot
        return e

    def capsule(self, a, b, r, stiff=2.0, neg=False):
        """A capsule from point a to point b, radius r (metaball capsules lie along local X)."""
        a, b = Vector(a), Vector(b)
        d = b - a
        e = self._el("CAPSULE", (a + b) / 2, r, stiff, neg)
        e.size_x = d.length / 2
        e.rotation = Vector((1, 0, 0)).rotation_difference(d.normalized())
        return e

    def chain(self, pts, radii, stiff=2.0):
        for (a, b), (ra, rb) in zip(zip(pts, pts[1:]), zip(radii, radii[1:])):
            self.capsule(a, b, (ra + rb) / 2, stiff)
            self.ball(b, rb, stiff)
        self.ball(pts[0], radii[0], stiff)

    def mesh(self, name=None):
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(self.ob.evaluated_get(dg))
        me.name = name or self.name
        bpy.data.objects.remove(self.ob, do_unlink=True)
        ob = bpy.data.objects.new(name or self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob


def obj_from_bm(bm, name):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def displace(ob, fn):
    """fn(co, normal) -> offset Vector, applied to every vertex (normals from the current shape)."""
    me = ob.data
    cos = [v.co.copy() for v in me.vertices]
    nos = [v.normal.copy() for v in me.vertices]
    for v, c, n in zip(me.vertices, cos, nos):
        v.co = c + fn(c, n)
    me.update()


def delete_faces(ob, pred):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    kill = [f for f in bm.faces if pred(f.calc_center_median(), f.normal)]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(ob.data); bm.free()


def smooth(ob, iters=2, factor=0.5):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    for _ in range(iters):
        bmesh.ops.smooth_vert(bm, verts=bm.verts, factor=factor, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(ob.data); bm.free()


def apply_mods(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)


def keep_largest(ob, min_faces=40):
    """Drop small loose islands (cut-off crumbs) from a shell."""
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.faces.ensure_lookup_table()
    seen, islands = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, isl = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop(); isl.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index); stack.append(h)
        islands.append(isl)
    kill = [f for isl in islands if len(isl) < min_faces for f in isl]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(ob.data); bm.free()


def solidify(ob, thick, offset=-1.0, mat_offset=0, min_faces=40):
    if min_faces:
        keep_largest(ob, min_faces)
    m = ob.modifiers.new("Solid", "SOLIDIFY"); m.thickness = thick; m.offset = offset; m.material_offset = mat_offset
    m.use_even_offset = False; m.use_quality_normals = True; m.nonmanifold_thickness_mode = "CONSTRAINTS"
    apply_mods(ob)


def select_only(ob):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def retopo(ob, faces, name=None):
    """QuadriFlow game mesh from a high mesh (the high one is kept)."""
    lo = ob.copy(); lo.data = ob.data.copy(); lo.name = name or (ob.name + "_low")
    bpy.context.scene.collection.objects.link(lo)
    lo.data.materials.clear()
    select_only(lo)
    try:
        r = bpy.ops.object.quadriflow_remesh(target_faces=faces, use_mesh_symmetry=False, use_preserve_sharp=False,
                                             use_preserve_boundary=True, smooth_normals=False)
    except RuntimeError as ex:
        print("quadriflow failed on", ob.name, "- decimating instead")
        r = {"CANCELLED"}
    if "FINISHED" not in r or len(lo.data.polygons) < faces * 0.3:
        # QuadriFlow can fail on thin or open shells: decimate instead
        lo.data = ob.data.copy()
        lo.data.materials.clear()
        m = lo.modifiers.new("Dec", "DECIMATE"); m.ratio = min(1.0, faces * 2.0 / max(len(ob.data.polygons), 1))
        apply_mods(lo)
    for p in lo.data.polygons:
        p.use_smooth = True
    return lo


def decimate(ob, tris, name=None):
    lo = ob.copy(); lo.data = ob.data.copy(); lo.name = name or (ob.name + "_low")
    bpy.context.scene.collection.objects.link(lo)
    lo.data.materials.clear()
    n = sum(len(p.vertices) - 2 for p in lo.data.polygons)
    m = lo.modifiers.new("Dec", "DECIMATE"); m.ratio = min(1.0, tris / max(n, 1))
    apply_mods(lo)
    for p in lo.data.polygons:
        p.use_smooth = True
    return lo


# ------------------------------------------------------------------ procedural paint (on the high meshes)
def lin(c):
    return tuple(x ** 2.2 for x in c) + (1.0,)


class Paint:
    """Builds an emission material for baking. Layers are mixed in order:
    base (two colours mottled by noise) -> extra layers (mask, colour, strength) -> cavity -> grime."""
    def __init__(self, name):
        self.m = bpy.data.materials.new(name); self.m.use_nodes = True
        nt = self.nt = self.m.node_tree; nt.nodes.clear()
        self.out = nt.nodes.new("ShaderNodeOutputMaterial")
        self.em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(self.em.outputs[0], self.out.inputs["Surface"])
        self.tc = nt.nodes.new("ShaderNodeTexCoord")
        self.geo = nt.nodes.new("ShaderNodeNewGeometry")
        self.col = None

    # -- helpers
    def node(self, t, **inputs):
        n = self.nt.nodes.new(t)
        for k, v in inputs.items():
            n.inputs[k].default_value = v
        return n

    def link(self, a, b):
        self.nt.links.new(a, b)

    def noise(self, scale, detail=6.0, rough=0.6, coord=None, w=None):
        n = self.node("ShaderNodeTexNoise", Scale=scale, Detail=detail, Roughness=rough)
        self.link(coord if coord is not None else self.tc.outputs["Object"], n.inputs["Vector"])
        return n.outputs["Fac"]

    def ramp(self, fac, lo, hi, c0, c1):
        r = self.nt.nodes.new("ShaderNodeValToRGB")
        r.color_ramp.elements[0].position = lo; r.color_ramp.elements[1].position = hi
        r.color_ramp.elements[0].color = lin(c0); r.color_ramp.elements[1].color = lin(c1)
        self.link(fac, r.inputs["Fac"])
        return r.outputs["Color"]

    def rng(self, val, a, b, c=0.0, d=1.0, clamp=True):
        n = self.node("ShaderNodeMapRange")
        n.inputs["From Min"].default_value = a; n.inputs["From Max"].default_value = b
        n.inputs["To Min"].default_value = c; n.inputs["To Max"].default_value = d
        n.clamp = clamp
        self.link(val, n.inputs["Value"])
        return n.outputs["Result"]

    def math(self, op, a, b=None, clamp=False):
        n = self.node("ShaderNodeMath"); n.operation = op; n.use_clamp = clamp
        if isinstance(a, (int, float)):
            n.inputs[0].default_value = a
        else:
            self.link(a, n.inputs[0])
        if b is not None:
            if isinstance(b, (int, float)):
                n.inputs[1].default_value = b
            else:
                self.link(b, n.inputs[1])
        return n.outputs[0]

    def mix(self, fac, a, b, blend="MIX"):
        n = self.node("ShaderNodeMix"); n.data_type = "RGBA"; n.blend_type = blend
        if isinstance(fac, (int, float)):
            n.inputs["Factor"].default_value = fac
        else:
            self.link(fac, n.inputs["Factor"])
        for slot, v in ((6, a), (7, b)):
            if isinstance(v, tuple):
                n.inputs[slot].default_value = lin(v) if len(v) == 3 else v
            else:
                self.link(v, n.inputs[slot])
        return n.outputs[2]

    def axis(self, k):
        sep = self.node("ShaderNodeSeparateXYZ"); self.link(self.tc.outputs["Object"], sep.inputs[0])
        return sep.outputs["XYZ"[k]]

    def dist(self, p):
        v = self.node("ShaderNodeVectorMath"); v.operation = "DISTANCE"
        self.link(self.tc.outputs["Object"], v.inputs[0]); v.inputs[1].default_value = Vector(p)
        return v.outputs["Value"]

    # -- layers
    def base(self, c0, c1, scale=4.0, contrast=0.5, fine=0.25):
        f = self.noise(scale, 8, 0.55)
        col = self.ramp(f, 0.5 - contrast * 0.3, 0.5 + contrast * 0.3, c0, c1)
        g = self.noise(scale * 9, 3, 0.5)
        gg = self.rng(g, 0.3, 0.7, 1 - fine, 1 + fine * 0.6)
        cc = self.node("ShaderNodeCombineColor")
        for k in ("Red", "Green", "Blue"):
            self.link(gg, cc.inputs[k])
        self.col = self.mix(1.0, col, cc.outputs["Color"], "MULTIPLY")
        return self

    def layer(self, mask, color, strength=1.0):
        m = self.math("MULTIPLY", mask, strength, clamp=True)
        self.col = self.mix(m, self.col, color)
        return self

    def mask_noise(self, scale, cover, soft=0.06, coord=None):
        f = self.noise(scale, 6, 0.6, coord)
        t = 0.5 + (0.5 - cover) * 0.32
        return self.rng(f, t, t + soft)

    def mask_near(self, pts, radius, falloff=0.5, ragged=0.35, scale=14.0):
        acc = None
        for p in pts:
            r = self.rng(self.dist(p), radius * (1 - falloff), radius, 1.0, 0.0)
            acc = r if acc is None else self.math("MAXIMUM", acc, r)
        n = self.noise(scale, 6, 0.6)
        off = self.math("MULTIPLY_ADD", n, ragged * 2)
        self.nt.nodes[-1].inputs[2].default_value = -ragged
        s = self.math("ADD", acc, off, clamp=True)
        return self.rng(s, 0.45, 0.6)

    def mask_box(self, c, half, ragged=0.08, border=0.0):
        """A sewn-on patch: an axis-aligned box (half extents) with slightly ragged sides. border > 0 returns
        only the outline band (stitches), as a fraction of the size."""
        sep = self.node("ShaderNodeSeparateXYZ"); self.link(self.tc.outputs["Object"], sep.inputs[0])
        m = None
        for k, ax in enumerate("XYZ"):
            if half[k] <= 0:
                continue
            d = self.math("DIVIDE", self.math("ABSOLUTE", self.math("SUBTRACT", sep.outputs[ax], c[k])), half[k])
            m = d if m is None else self.math("MAXIMUM", m, d)
        if ragged:
            n = self.noise(40.0, 3, 0.5)
            m = self.math("ADD", m, self.math("MULTIPLY", self.math("SUBTRACT", n, 0.5), ragged))
        if border:
            inner = self.rng(m, 1 - border * 1.6, 1 - border, 0.0, 1.0)
            outer = self.rng(m, 1.0, 1.02, 1.0, 0.0)
            return self.math("MULTIPLY", inner, outer)
        return self.rng(m, 0.98, 1.0, 1.0, 0.0)

    def mask_below(self, z0, z1, ragged=0.0):
        """1 below z0 fading to 0 at z1 (dirt rising from the ground)."""
        z = self.axis(2)
        if ragged:
            n = self.noise(6.0, 4, 0.5)
            z = self.math("ADD", z, self.math("MULTIPLY", self.math("SUBTRACT", n, 0.5), ragged))
        return self.rng(z, z0, z1, 1.0, 0.0)

    def mask_above(self, z0, z1):
        return self.rng(self.axis(2), z0, z1, 0.0, 1.0)

    def stripes(self, k, period, width, soft=0.002):
        """Thin lines every `period` metres along axis k (seams, ribbing): 1 on the line."""
        a = self.axis(k)
        w = self.math("WRAP", a, period); self.nt.nodes[-1].inputs[2].default_value = 0.0
        d = self.math("ABSOLUTE", self.math("SUBTRACT", w, period / 2))
        return self.rng(d, width, width + soft, 1.0, 0.0)

    def seam_plane(self, k, at, width=0.004):
        a = self.math("ABSOLUTE", self.math("SUBTRACT", self.axis(k), at))
        return self.rng(a, width, width * 2, 1.0, 0.0)

    def cavity(self, amount=0.5, edge=0.25):
        """Pointiness: darken creases and folds, lighten worn edges (Cycles only, baked)."""
        p = self.geo.outputs["Pointiness"]
        dark = self.rng(p, 0.46, 0.5, 1.0, 0.0)
        light = self.rng(p, 0.52, 0.6, 0.0, 1.0)
        self.col = self.mix(self.math("MULTIPLY", dark, amount), self.col, (0.06, 0.05, 0.05))
        self.col = self.mix(self.math("MULTIPLY", light, edge), self.col, (0.85, 0.82, 0.76))
        return self

    # -- surface texture: procedural relief, baked into the colour as creases and micro light/shade
    def warped(self, scale=3.0, amount=0.15):
        """Object coordinates pushed about by noise, so cell patterns don't look machine-made."""
        nz = self.node("ShaderNodeTexNoise", Scale=scale, Detail=2.0)
        self.link(self.tc.outputs["Object"], nz.inputs["Vector"])
        sub = self.node("ShaderNodeVectorMath"); sub.operation = "SUBTRACT"
        self.link(nz.outputs["Color"], sub.inputs[0]); sub.inputs[1].default_value = (0.5, 0.5, 0.5)
        sc = self.node("ShaderNodeVectorMath"); sc.operation = "SCALE"
        self.link(sub.outputs[0], sc.inputs[0]); sc.inputs["Scale"].default_value = amount
        add = self.node("ShaderNodeVectorMath"); add.operation = "ADD"
        self.link(sc.outputs[0], add.inputs[0]); self.link(self.tc.outputs["Object"], add.inputs[1])
        return add.outputs[0]

    def voronoi(self, scale, feature="DISTANCE_TO_EDGE", coord=None, rand=1.0):
        n = self.nt.nodes.new("ShaderNodeTexVoronoi"); n.feature = feature
        n.inputs["Scale"].default_value = scale; n.inputs["Randomness"].default_value = rand
        self.link(coord if coord is not None else self.tc.outputs["Object"], n.inputs["Vector"])
        return n.outputs["Distance"]

    def wave(self, scale, direction="X", distortion=0.0, detail=0.0, coord=None):
        n = self.nt.nodes.new("ShaderNodeTexWave"); n.wave_type = "BANDS"; n.bands_direction = direction
        n.inputs["Scale"].default_value = scale; n.inputs["Distortion"].default_value = distortion
        n.inputs["Detail"].default_value = detail
        self.link(coord if coord is not None else self.tc.outputs["Object"], n.inputs["Vector"])
        return n.outputs["Fac"]

    def ridges(self, scale, width=0.02, detail=2.5, coord=None):
        """Thin branching lines (veins, cracks): where a noise crosses its middle value."""
        a = self.math("ABSOLUTE", self.math("SUBTRACT", self.noise(scale, detail, 0.55, coord), 0.5))
        return self.rng(a, 0.0, width, 1.0, 0.0)

    def wsum(self, *pairs):
        acc = None
        for sock, w in pairs:
            t = self.math("MULTIPLY", sock, w)
            acc = t if acc is None else self.math("ADD", acc, t)
        return acc

    def relief(self, height, distance=0.004, amount=0.8, strength=1.0, light=(-0.3, -0.35, 0.89)):
        """Bake small relief into the colour: shade from a bump of `height` minus the shading of the bare
        surface, so only the fine detail is baked (the toon shader still lights the big forms in game)."""
        b = self.nt.nodes.new("ShaderNodeBump")
        b.inputs["Strength"].default_value = strength; b.inputs["Distance"].default_value = distance
        self.link(height, b.inputs["Height"])
        L = Vector(light).normalized()
        d1 = self.node("ShaderNodeVectorMath"); d1.operation = "DOT_PRODUCT"
        self.link(b.outputs["Normal"], d1.inputs[0]); d1.inputs[1].default_value = L
        d0 = self.node("ShaderNodeVectorMath"); d0.operation = "DOT_PRODUCT"
        self.link(self.geo.outputs["Normal"], d0.inputs[0]); d0.inputs[1].default_value = L
        delta = self.math("SUBTRACT", d1.outputs["Value"], d0.outputs["Value"])
        f = self.math("MULTIPLY_ADD", delta, amount); self.nt.nodes[-1].inputs[2].default_value = 1.0
        self.col = self.mix(1.0, self.col, f, "MULTIPLY")
        return self

    def skin_texture(self, scale=1.0, crease=(0.32, 0.20, 0.19), vein=(0.40, 0.28, 0.40), amount=0.6, veins=0.5):
        """Skin, not scales: branching fold lines, soft irregular creases in patches, pores, veins."""
        w = self.warped(3.0 * scale, 0.3 / scale)
        c1 = self.voronoi(34 * scale, coord=w)
        patch = self.mask_noise(2.5 * scale, 0.5)                                  # creased only in places
        folds = self.ridges(26 * scale, 0.014, 3.0)
        fine = self.ridges(70 * scale, 0.01, 2.0)
        vn = self.math("MULTIPLY", self.ridges(9 * scale, 0.022), self.mask_noise(2.2 * scale, 0.5))
        pores = self.noise(260 * scale, 2.0, 0.5)
        self.layer(self.math("MULTIPLY", self.rng(c1, 0.0, 0.03, 1.0, 0.0), patch), crease, 0.22)
        self.layer(folds, crease, 0.3)
        self.layer(fine, crease, 0.14)
        self.layer(vn, vein, veins)
        self.layer(self.rng(self.noise(180 * scale, 2.0), 0.64, 0.68), (0.36, 0.22, 0.20), 0.3)    # speckle
        h = self.wsum((self.math("MULTIPLY", self.rng(c1, 0.0, 0.08), patch), 0.25), (self.math("SUBTRACT", 1.0, folds), 0.3),
                      (self.math("SUBTRACT", 1.0, fine), 0.1), (vn, 0.2), (pores, 0.15))
        return self.relief(h, 0.005 / scale, amount)

    def crust(self, mask, scale=70.0, color=(0.30, 0.08, 0.06), strength=0.75):
        """Cracked, scabbed crust inside a mask (round wounds and raw roots)."""
        cells = self.voronoi(scale, coord=self.warped(6.0, 0.05))
        crack = self.rng(cells, 0.0, 0.05, 1.0, 0.0)
        self.layer(self.math("MULTIPLY", mask, crack), color, strength)
        return self.relief(self.math("MULTIPLY", mask, self.rng(cells, 0.0, 0.08)), 0.003, 0.8)

    def weave(self, scale=60.0, dark=(0.0, 0.0, 0.0), strength=0.3, amount=0.6, twill=False):
        """Woven cloth grain. Blender's wave period is 2*pi / (20 * scale) metres: 60 -> about 5 mm, the
        finest a 1024 game texture still holds. Distorted so the bands don't read as contour rings."""
        if twill:
            h = self.wsum((self.wave(scale, "DIAGONAL", 2.0), 0.65), (self.wave(scale * 0.6, "Z", 2.0), 0.35))
        else:
            h = self.wsum((self.wave(scale, "X", 2.0), 0.5), (self.wave(scale, "Z", 2.0), 0.5))
        h = self.wsum((h, 0.75), (self.noise(scale * 2.0, 2.0), 0.25))
        self.layer(self.rng(h, 0.25, 0.55, 1.0, 0.0), dark, strength)
        return self.relief(h, 0.002, amount)

    def knit(self, scale=45.0, dark=(0.0, 0.0, 0.0), strength=0.35, amount=0.8):
        """Knitted wool: rows of stitches (bands along Z, wobbled), about 7 mm a row at 45."""
        rows = self.wave(scale, "Z", 3.0, 1.0)
        cols = self.wave(scale * 0.6, "X", 1.5)
        h = self.wsum((rows, 0.6), (cols, 0.25), (self.noise(scale * 1.5, 2.0), 0.15))
        self.layer(self.rng(h, 0.2, 0.5, 1.0, 0.0), dark, strength)
        return self.relief(h, 0.003, amount)

    def leather(self, scale=160.0, dark=(0.0, 0.0, 0.0), strength=0.35, amount=0.7):
        grain = self.voronoi(scale, "F1", coord=self.warped(8.0, 0.02))
        creases = self.ridges(14.0, 0.015)
        h = self.wsum((grain, 0.5), (self.math("SUBTRACT", 1.0, creases), 0.5))
        self.layer(creases, dark, strength)
        return self.relief(h, 0.0015, amount)

    def fractures(self, scale=22.0, light=(0.82, 0.90, 0.95), strength=0.45, amount=0.6):
        """Ice: fracture planes inside, shown as pale lines and steps."""
        cells = self.voronoi(scale, coord=self.warped(3.0, 0.2))
        lines = self.rng(cells, 0.0, 0.022, 1.0, 0.0)
        self.layer(lines, light, strength)
        self.layer(self.ridges(30.0, 0.012), light, strength * 0.6)
        return self.relief(self.rng(cells, 0.0, 0.06), 0.003, amount)

    def streaks(self, scale=60.0, axis="Z", dark=(0.0, 0.0, 0.0), strength=0.35, amount=0.6):
        """Growth ridges and staining lines (teeth, claws, horn)."""
        w = self.wave(scale, axis, 6.0, 2.0)
        self.layer(self.rng(w, 0.2, 0.5, 1.0, 0.0), dark, strength)
        return self.relief(w, 0.0012, amount)

    def done(self):
        self.link(self.col, self.em.inputs["Color"])
        return self.m


# ------------------------------------------------------------------ baking high -> low
def bake_to_low(highs, low, size=2048, margin=8, cage=0.03, ao=0.5, path=None):
    """Bake the painted colour (emission) and AO of the high meshes onto the low mesh's UVs, multiply them,
    and give the low mesh one base-colour material with the result."""
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 1
    sc.world = sc.world or bpy.data.worlds.new("World")
    select_only(low)
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.003, area_weight=0.0)
    bpy.ops.uv.pack_islands(margin=0.002, rotate=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    imgs = {}
    low.data.materials.clear()
    tm = bpy.data.materials.new("BakeTarget"); tm.use_nodes = True
    low.data.materials.append(tm)
    for kind in ("EMIT", "AO"):
        img = bpy.data.images.new("bake_" + kind.lower(), size, size, alpha=False)
        img.colorspace_settings.name = "sRGB" if kind == "EMIT" else "Non-Color"
        imgs[kind] = img
        nt = tm.node_tree
        for n in [n for n in nt.nodes if n.type == "TEX_IMAGE"]:
            nt.nodes.remove(n)
        tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = img; nt.nodes.active = tn
        for h in highs:
            h.select_set(True)
        low.select_set(True); bpy.context.view_layer.objects.active = low
        sc.cycles.samples = 1 if kind == "EMIT" else 32
        sc.render.bake.use_selected_to_active = True
        sc.render.bake.cage_extrusion = cage
        sc.render.bake.max_ray_distance = cage * 2.5
        sc.render.bake.margin = margin
        bpy.ops.object.bake(type=kind, use_clear=True)
    W = H = size
    e = np.array(imgs["EMIT"].pixels[:], np.float32).reshape(H, W, 4)
    a = np.array(imgs["AO"].pixels[:], np.float32).reshape(H, W, 4)
    k = (1 - ao) + ao * np.clip(a[..., :1], 0, 1) ** 0.9
    e[..., :3] *= k
    final = bpy.data.images.new(low.name + "_paint", W, H, alpha=False)
    final.pixels[:] = e.ravel()
    if path:
        final.filepath_raw = path; final.file_format = "PNG"; final.save()
    low.data.materials.clear()
    m = bpy.data.materials.new(low.name + "_Mat"); m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    tn = m.node_tree.nodes.new("ShaderNodeTexImage"); tn.image = final
    m.node_tree.links.new(tn.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    low.data.materials.append(m)
    for o in highs:
        o.select_set(False)
    return final


# ------------------------------------------------------------------ weights from a proxy
def heat_weights(arm_ob, proxy):
    """Blender's automatic (bone heat) weights on a closed proxy mesh. Returns True on success."""
    select_only(proxy)
    arm_ob.select_set(True)
    bpy.context.view_layer.objects.active = arm_ob
    try:
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    except Exception as ex:
        print("heat weights failed:", ex)
        return False
    return len(proxy.vertex_groups) > 0 and any(len(g.name) for g in proxy.vertex_groups)


def transfer_weights(proxy, target, arm_ob, smooth_iters=2):
    """Each target vertex takes the weights of the nearest point on the proxy surface (barycentric)."""
    pme = proxy.data
    groups = [g.name for g in proxy.vertex_groups]
    W = np.zeros((len(pme.vertices), len(groups)), np.float32)
    for v in pme.vertices:
        for g in v.groups:
            W[v.index, g.group] = g.weight
    bm = bmesh.new(); bm.from_mesh(pme); bm.transform(proxy.matrix_world)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
    tree = BVHTree.FromBMesh(bm)
    tw = np.zeros((len(target.data.vertices), len(groups)), np.float32)
    M = target.matrix_world
    for v in target.data.vertices:
        p = M @ v.co
        loc, nrm, fi, d = tree.find_nearest(p)
        if fi is None:
            continue
        f = bm.faces[fi]
        a, b, c = [x.co for x in f.verts]
        # barycentric
        v0, v1, v2 = b - a, c - a, loc - a
        d00, d01, d11 = v0.dot(v0), v0.dot(v1), v1.dot(v1)
        d20, d21 = v2.dot(v0), v2.dot(v1)
        den = d00 * d11 - d01 * d01 or 1e-12
        wv = (d11 * d20 - d01 * d21) / den; ww = (d00 * d21 - d01 * d20) / den; wu = 1 - wv - ww
        ids = [x.index for x in f.verts]
        tw[v.index] = W[ids[0]] * wu + W[ids[1]] * wv + W[ids[2]] * ww
    bm.free()
    # a little smoothing over the target's own edges, then normalise and keep the top 4
    if smooth_iters:
        edges = np.array([e.vertices[:] for e in target.data.edges], np.int64)
        for _ in range(smooth_iters):
            acc = tw.copy(); cnt = np.ones(len(tw), np.float32)
            np.add.at(acc, edges[:, 0], tw[edges[:, 1]]); np.add.at(acc, edges[:, 1], tw[edges[:, 0]])
            np.add.at(cnt, edges[:, 0], 1); np.add.at(cnt, edges[:, 1], 1)
            tw = 0.5 * tw + 0.5 * acc / cnt[:, None]
    target.vertex_groups.clear()
    vgs = [target.vertex_groups.new(name=g) for g in groups]
    for i, row in enumerate(tw):
        top = np.argsort(row)[::-1][:4]
        s = row[top].sum()
        if s <= 1e-6:
            continue
        for j in top:
            if row[j] / s > 0.01:
                vgs[j].add([i], float(row[j] / s), "REPLACE")
    target.parent = arm_ob
    md = target.modifiers.new("Armature", "ARMATURE"); md.object = arm_ob


# ------------------------------------------------------------------ QC renders
def qc_renders(objs, out_png, height=1.8, size=520, views=(("front", 0), ("side", 90), ("back", 180), ("3/4", 35)), game=True):
    """Front/side/back/three-quarter orthographic renders in Cycles with a key/fill/rim set-up, plus one
    view from the game camera (47 degrees), pasted side by side."""
    import os
    from PIL import Image
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 24
    try:
        sc.cycles.use_denoising = True
    except Exception:
        pass
    sc.render.resolution_x = size; sc.render.resolution_y = int(size * 1.25); sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("World"); sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.36, 0.37, 0.40, 1); bg.inputs["Strength"].default_value = 0.6
    cam_d = bpy.data.cameras.new("QC"); cam_d.type = "ORTHO"; cam_d.ortho_scale = height * 1.12
    cam = bpy.data.objects.new("QC", cam_d); sc.collection.objects.link(cam); sc.camera = cam
    lights = []
    for name, rot, e in (("Key", (50, 0, -40), 3.2), ("Fill", (60, 0, 120), 1.0), ("Rim", (100, 0, 170), 2.0)):
        ld = bpy.data.lights.new(name, "SUN"); ld.energy = e
        lo = bpy.data.objects.new(name, ld); sc.collection.objects.link(lo)
        lo.rotation_euler = tuple(math.radians(x) for x in rot); lights.append(lo)
    tiles = []
    vs = list(views) + ([("game", 300)] if game else [])
    for label, yaw in vs:
        a = math.radians(yaw)
        if label == "game":
            el = math.radians(47.0)
            d = Vector((math.sin(a) * math.cos(el), -math.cos(a) * math.cos(el), math.sin(el)))
            cam_d.ortho_scale = height * 1.12
        else:
            d = Vector((math.sin(a), -math.cos(a), 0.0))
        tgt = Vector((0, 0, height * 0.5))
        cam.location = tgt + d * 12
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        p = f"{out_png}.tile_{label.replace('/', '')}.png"                    # unique per job (jobs may run side by side)
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        tiles.append(p)
    for o in lights + [cam]:
        bpy.data.objects.remove(o, do_unlink=True)
    ims = [Image.open(t).convert("RGB") for t in tiles]
    sheet = Image.new("RGB", (sum(i.width for i in ims), ims[0].height), (60, 60, 64))
    x = 0
    for im in ims:
        sheet.paste(im, (x, 0)); x += im.width
    sheet.save(out_png)
    print("qc", out_png)


def closeups(out_png, shots, size=420):
    """shots: list of (target (x, y, z), ortho size, yaw degrees, elevation degrees)."""
    from PIL import Image
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 24
    sc.render.resolution_x = sc.render.resolution_y = size; sc.render.resolution_percentage = 100
    sc.world = sc.world or bpy.data.worlds.new("World"); sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.36, 0.37, 0.40, 1); bg.inputs["Strength"].default_value = 0.6
    cam_d = bpy.data.cameras.new("CU"); cam_d.type = "ORTHO"
    cam = bpy.data.objects.new("CU", cam_d); sc.collection.objects.link(cam); sc.camera = cam
    lights = []
    for name, rot, e in (("Key", (50, 0, -40), 3.2), ("Fill", (60, 0, 120), 1.0), ("Rim", (100, 0, 170), 2.0)):
        ld = bpy.data.lights.new(name, "SUN"); ld.energy = e
        lo = bpy.data.objects.new(name, ld); sc.collection.objects.link(lo)
        lo.rotation_euler = tuple(math.radians(x) for x in rot); lights.append(lo)
    tiles = []
    for i, (tgt, ortho, yaw, el) in enumerate(shots):
        a, e = math.radians(yaw), math.radians(el)
        d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
        cam_d.ortho_scale = ortho
        cam.location = Vector(tgt) + d * 6
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        p = f"{out_png}.tile_{i}.png"; sc.render.filepath = p
        bpy.ops.render.render(write_still=True); tiles.append(p)
    for o in lights + [cam]:
        bpy.data.objects.remove(o, do_unlink=True)
    ims = [Image.open(t).convert("RGB") for t in tiles]
    sheet = Image.new("RGB", (sum(i.width for i in ims), size), (60, 60, 64))
    x = 0
    for im in ims:
        sheet.paste(im, (x, 0)); x += im.width
    sheet.save(out_png)


def relax_boundary(ob, iters=8, factor=0.6):
    """Straighten the stair-stepped edges left by deleting voxel faces (cuts, hems, openings)."""
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bverts = [v for v in bm.verts if v.is_boundary]
    for _ in range(iters):
        new = {}
        for v in bverts:
            nb = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
            if len(nb) == 2:
                avg = (nb[0].co + nb[1].co) / 2
                new[v] = v.co.lerp(avg, factor)
        for v, c in new.items():
            v.co = c
    bm.to_mesh(ob.data); bm.free()


def boundary_loops(ob):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    edges = [e for e in bm.edges if e.is_boundary]
    seen, loops = set(), []
    adj = {}
    for e in edges:
        a, b = e.verts
        adj.setdefault(a.index, []).append(b.index); adj.setdefault(b.index, []).append(a.index)
    co = {v.index: v.co.copy() for v in bm.verts}
    for start in adj:
        if start in seen:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = [n for n in adj[cur] if n != prev and n not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur); loop.append(cur)
        loops.append([co[i] for i in loop])
    bm.free()
    return loops


def hem(ob, radius, pred, name, seg=6, step=2):
    """A rolled hem (tube) along the boundary loops of a shell whose midpoint passes pred(point)."""
    bm = bmesh.new()
    for loop in boundary_loops(ob):
        if len(loop) < 8:
            continue
        mid = loop[len(loop) // 2]
        if not pred(sum(loop, Vector()) / len(loop), loop):
            continue
        pts = loop[::step]
        if (pts[0] - pts[-1]).length < radius * 6:
            pts = pts + [pts[0]]
        rings = []
        for i, p in enumerate(pts):
            a = pts[max(i - 1, 0)]; b = pts[min(i + 1, len(pts) - 1)]
            t = (b - a).normalized()
            up = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            n1 = t.cross(up).normalized(); n2 = t.cross(n1)
            rings.append([bm.verts.new(p + radius * (math.cos(2 * math.pi * k / seg) * n1 + math.sin(2 * math.pi * k / seg) * n2)) for k in range(seg)])
        for r0, r1 in zip(rings, rings[1:]):
            for k in range(seg):
                bm.faces.new([r0[k], r0[(k + 1) % seg], r1[(k + 1) % seg], r1[k]])
    if not bm.faces:
        bm.free(); return None
    return obj_from_bm(bm, name)


def ribbon_loop(center, rx, ry, z, tilt, width, name_bm, segs=40, phase=0.0, wobble=0.003):
    """A flat band wrapped round an ellipse (cloth strip round a boot shaft), tilted about x."""
    verts_top, verts_bot = [], []
    for j in range(segs):
        a = 2 * math.pi * j / segs
        c = Vector((center.x + math.cos(a) * rx, center.y + math.sin(a) * ry, z + math.sin(a + phase) * tilt))
        c += Vector((math.cos(a), math.sin(a), 0)) * noise.noise(c * 60) * wobble
        verts_top.append(name_bm.verts.new(c + Vector((0, 0, width / 2))))
        verts_bot.append(name_bm.verts.new(c - Vector((0, 0, width / 2))))
    for j in range(segs):
        k = (j + 1) % segs
        name_bm.faces.new([verts_bot[j], verts_bot[k], verts_top[k], verts_top[j]])
