"""Shared kit for Silo 81 creatures built in code (feral.py, infected.py): organic bodies from skin-modifier
graphs, rigid parts (spikes, teeth, claws), a hand-made rig with distance-based weights, a small FK/IK
solver for procedural animation (feet stay planted: locomotion is in place and the Actor moves the body),
a painted texture baked from procedural materials, and GLB export for game/scripts/puppet3d.gd.

Conventions (as goat_live.py and the Mixamo characters): Blender Z up, the creature faces -Y (+Z in
Godot), feet on z=0, real size in metres, 24 fps, base colour only (the toon shader reads nothing else).
"""
import math, random, os
import bpy, bmesh
import numpy as np
from mathutils import Vector, Matrix, Quaternion, noise

FPS = 24


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    return sc


# ------------------------------------------------------------------ geometry parts
class Part:
    """verts: list of Vector, faces: list of index tuples, mat: per-face material index list,
    bind: ("rigid", bone) or ("auto", [bones]) for the weights."""
    def __init__(self, verts, faces, mat, bind, smooth=True):
        self.verts, self.faces, self.mat, self.bind, self.smooth = verts, faces, mat, bind, smooth


def _mesh_to_part(me, mat, bind, smooth=True):
    verts = [v.co.copy() for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    mats = [mat] * len(faces) if isinstance(mat, int) else [mat(Vector(me.polygons[i].center)) for i in range(len(faces))]
    return Part(verts, faces, mats, bind, smooth)


def skin(nodes, edges, mat, bind, subdiv=2, displace=None, name="Skin"):
    """nodes: list of (position, radius or (rx, ry)); edges: index pairs (a tree). displace(v, n) -> offset."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([Vector(p) for p, _ in nodes], edges, [])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    sk = ob.modifiers.new("Skin", "SKIN")
    sk.branch_smoothing = 0.6
    me.skin_vertices[0].data[0].use_root = True
    for i, (_, r) in enumerate(nodes):
        rr = (r, r) if isinstance(r, (int, float)) else r
        me.skin_vertices[0].data[i].radius = rr
    if subdiv:
        sd = ob.modifiers.new("Sub", "SUBSURF"); sd.levels = subdiv; sd.render_levels = subdiv
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob, do_unlink=True)
    if displace:
        me2.calc_normals_split() if hasattr(me2, "calc_normals_split") else None
        for v in me2.vertices:
            v.co = v.co + displace(v.co.copy(), v.normal.copy())
    return _mesh_to_part(me2, mat, bind)


def ellipsoid(c, r, mat, bind, seg=12, M=Matrix()):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=max(4, seg // 2), radius=1.0,
                              matrix=M @ Matrix.Translation(Vector(c)) @ Matrix.Diagonal((r[0], r[1], r[2], 1.0)))
    me = bpy.data.meshes.new("e"); bm.to_mesh(me); bm.free()
    return _mesh_to_part(me, mat, bind)


def cone(p0, p1, r0, r1, mat, bind, seg=6, bend=None, rings=3):
    """A tapered prism from p0 to p1 (spike, tooth, claw); bend: a vector the tip curls towards."""
    p0, p1 = Vector(p0), Vector(p1)
    ax = (p1 - p0)
    L = ax.length; ax = ax / L
    t = Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0))
    n = ax.cross(t).normalized(); b = ax.cross(n)
    verts, faces = [], []
    for k in range(rings):
        s = k / (rings - 1) if rings > 1 else 0
        c = p0 + ax * (L * s)
        if bend is not None:
            c = c + Vector(bend) * (s * s)
        r = r0 + (r1 - r0) * s
        for j in range(seg):
            a = 2 * math.pi * j / seg
            verts.append(c + r * (math.cos(a) * n + math.sin(a) * b))
    tip = p1 + (Vector(bend) if bend is not None else Vector()) + ax * (r1 * 0.5)
    verts.append(tip)
    for k in range(rings - 1):
        for j in range(seg):
            a, b2 = k * seg + j, k * seg + (j + 1) % seg
            faces.append((a, b2, b2 + seg, a + seg))
    ti = len(verts) - 1
    for j in range(seg):
        a, b2 = (rings - 1) * seg + j, (rings - 1) * seg + (j + 1) % seg
        faces.append((a, b2, ti))
    faces.append(tuple(range(seg))[::-1])
    return Part(verts, faces, [mat] * len(faces), bind, smooth=False)


def shell(c, r, mat, bind, cut, seg=16, thick=0.015, name="Shell"):
    """A thin ellipsoid shell (a hood) with faces removed where cut(center) is true, then solidified."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=1.0,
                              matrix=Matrix.Translation(Vector(c)) @ Matrix.Diagonal((r[0], r[1], r[2], 1.0)))
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if cut(f.calc_center_median())], context="FACES")
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    so = ob.modifiers.new("Solid", "SOLIDIFY"); so.thickness = thick; so.offset = 1.0
    sd = ob.modifiers.new("Sub", "SUBSURF"); sd.levels = 1
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob, do_unlink=True)
    return _mesh_to_part(me2, mat, bind)


def tube(path, radii, mat, bind, seg=12, hem=None, name="Tube"):
    """A cloth tube along a path of centres (a coat skirt), open at both ends, ragged hem: hem(angle) -> drop."""
    verts, faces = [], []
    for k, (c, r) in enumerate(zip(path, radii)):
        rr = (r, r) if isinstance(r, (int, float)) else r
        for j in range(seg):
            a = 2 * math.pi * j / seg
            v = Vector(c) + Vector((math.cos(a) * rr[0], math.sin(a) * rr[1], 0))
            if hem and k == len(path) - 1:
                v.z -= hem(a)
            verts.append(v)
    for k in range(len(path) - 1):
        for j in range(seg):
            a, b = k * seg + j, k * seg + (j + 1) % seg
            faces.append((a, a + seg, b + seg, b))
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces)
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    so = ob.modifiers.new("Solid", "SOLIDIFY"); so.thickness = 0.018; so.offset = 1.0
    sd = ob.modifiers.new("Sub", "SUBSURF"); sd.levels = 1
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob, do_unlink=True)
    return _mesh_to_part(me2, mat, bind)


# ------------------------------------------------------------------ rig
class Rig:
    """bones: list of (name, head, tail, parent or None, z_hint). z_hint sets the roll (bone z axis);
    for IK limbs point it to the side the joint bends towards."""
    def __init__(self, name, bones):
        self.spec = {b[0]: b for b in bones}
        self.order = [b[0] for b in bones]
        data = bpy.data.armatures.new(name)
        self.ob = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(self.ob)
        bpy.context.view_layer.objects.active = self.ob
        bpy.ops.object.mode_set(mode="EDIT")
        eb = data.edit_bones
        for (n, h, t, p, z) in bones:
            e = eb.new(n); e.head = Vector(h); e.tail = Vector(t)
            e.align_roll(Vector(z))
            if p:
                e.parent = eb[p]
            e.use_connect = False
        bpy.ops.object.mode_set(mode="OBJECT")
        self.rest = {n: data.bones[n].matrix_local.copy() for n in self.order}
        self.len = {n: data.bones[n].length for n in self.order}
        self.parent = {b[0]: b[3] for b in bones}
        for pb in self.ob.pose.bones:
            pb.rotation_mode = "QUATERNION"

    def seg(self, n):
        M = self.rest[n]
        return M.translation.copy(), (M @ Vector((0, self.len[n], 0)))


def frame_from(y, zhint, pos):
    y = Vector(y).normalized()
    x = y.cross(Vector(zhint)).normalized()
    if x.length < 1e-6:
        x = y.orthogonal().normalized()
    z = x.cross(y).normalized()
    M = Matrix((x, y, z)).transposed().to_4x4()
    M.translation = Vector(pos)
    return M


class Pose:
    """One frame: root (armature-space matrix for the root bone), local rotations (Quaternion in the
    bone's rest frame) for FK bones, and IK chains solved on top."""
    def __init__(self, rig):
        self.rig = rig
        self.basis = {n: Matrix.Identity(4) for n in rig.order}
        self.pose = {}
        self.ik = []          # (b1, b2, target, pole, end_bone, end_dir, end_zhint)

    def rot(self, n, x=0.0, y=0.0, z=0.0):
        """Rotate bone n about its own rest axes (degrees), on top of what it has."""
        q = Matrix.Rotation(math.radians(x), 4, "X") @ Matrix.Rotation(math.radians(y), 4, "Y") @ Matrix.Rotation(math.radians(z), 4, "Z")
        self.basis[n] = self.basis[n] @ q

    def root(self, n, offset=(0, 0, 0), rx=0.0, ry=0.0, rz=0.0):
        """The root bone: rotate about its head in armature axes (degrees), then move (metres)."""
        R = self.rig.rest[n]
        piv = R.translation
        W = (Matrix.Translation(Vector(offset) + piv) @ Matrix.Rotation(math.radians(rz), 4, "Z") @ Matrix.Rotation(math.radians(ry), 4, "Y")
             @ Matrix.Rotation(math.radians(rx), 4, "X") @ Matrix.Translation(-piv))
        self.basis[n] = R.inverted() @ W @ R

    def chain(self, b1, b2, target, pole, end=None, end_dir=None, end_z=None):
        self.ik.append((b1, b2, Vector(target), Vector(pole), end, end_dir, end_z))

    def _parent_rel(self, n):
        p = self.rig.parent[n]
        if p is None:
            return self.rig.rest[n].copy()
        return self.pose[p] @ self.rig.rest[p].inverted() @ self.rig.rest[n]

    def solve(self):
        ikb = {c[0]: c for c in self.ik}
        skip = set()
        for c in self.ik:
            skip.add(c[1])
            if c[4]:
                skip.add(c[4])
        for n in self.rig.order:
            if n in skip:
                continue
            if n in ikb:
                b1, b2, T, pole, end, end_dir, end_z = ikb[n]
                P1 = self._parent_rel(b1)
                H = P1.translation
                L1, L2 = self.rig.len[b1], self.rig.len[b2]
                d = (T - H).length
                d = min(max(d, abs(L1 - L2) + 1e-4), L1 + L2 - 1e-4)
                dirT = (T - H).normalized()
                pp = pole - dirT * pole.dot(dirT)
                pp = pp.normalized() if pp.length > 1e-6 else dirT.orthogonal().normalized()
                a = (L1 * L1 - L2 * L2 + d * d) / (2 * d)
                h = math.sqrt(max(L1 * L1 - a * a, 0.0))
                K = H + dirT * a + pp * h
                Tc = H + dirT * d
                M1 = frame_from(K - H, pp, H)
                self.basis[b1] = self._rot_only(P1.inverted() @ M1)
                self.pose[b1] = P1 @ self.basis[b1]
                P2 = self._parent_rel(b2)
                M2 = frame_from(Tc - K, pp, P2.translation)
                self.basis[b2] = self._rot_only(P2.inverted() @ M2)
                self.pose[b2] = P2 @ self.basis[b2]
                if end:
                    P3 = self._parent_rel(end)
                    if end_dir is not None:
                        M3 = frame_from(Vector(end_dir), Vector(end_z) if end_z is not None else pp, P3.translation)
                        self.basis[end] = self._rot_only(P3.inverted() @ M3)
                    self.pose[end] = P3 @ self.basis[end]
                continue
            self.pose[n] = self._parent_rel(n) @ self.basis[n]
        # bones below IK ends (fingers, toes) follow FK
        for n in self.rig.order:
            if n not in self.pose:
                self.pose[n] = self._parent_rel(n) @ self.basis[n]
        return self

    @staticmethod
    def _rot_only(M):
        q = M.to_quaternion()
        return q.to_matrix().to_4x4()

    def head(self, n):
        if not self.pose:
            self.solve()
        return self.pose[n].translation.copy()

    def key(self, frame):
        pbs = self.rig.ob.pose.bones
        for n in self.rig.order:
            pbs[n].matrix_basis = self.basis[n]
            pbs[n].keyframe_insert("rotation_quaternion", frame=frame)
            pbs[n].keyframe_insert("location", frame=frame)


def fk_point(pose, n, local):
    """A point in bone n's rest-space (relative to its head, metres) after posing."""
    return pose.pose[n] @ (pose.rig.rest[n].inverted() @ Vector(local))


# ------------------------------------------------------------------ assembling, weights
def build_body(rig, parts, materials, name="Body"):
    verts, faces, fmat, weights = [], [], [], []
    segs = {n: rig.seg(n) for n in rig.order}

    def seg_dist(p, n):
        a, b = segs[n]
        ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.dot(ab), 1e-9)))
        return (p - (a + ab * t)).length

    for part in parts:
        base = len(verts)
        verts += part.verts
        faces += [tuple(base + i for i in f) for f in part.faces]
        fmat += part.mat
        kind, bones = part.bind
        for v in part.verts:
            if kind == "rigid":
                weights.append({bones: 1.0})
            else:
                ds = sorted(((seg_dist(v, n), n) for n in bones))[:3]
                w = [(1.0 / (d + 0.012) ** 4, n) for d, n in ds]
                s = sum(x for x, _ in w)
                weights.append({n: x / s for x, n in w if x / s > 0.03})
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    for m in materials:
        me.materials.append(m)
    for i, p in enumerate(me.polygons):
        p.material_index = fmat[i] if i < len(fmat) else 0
    flat = set()
    off = 0
    for part in parts:
        if not part.smooth:
            flat.update(range(off, off + len(part.faces)))
        off += len(part.faces)
    for i, p in enumerate(me.polygons):
        p.use_smooth = i not in flat
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    groups = {n: ob.vertex_groups.new(name=n) for n in rig.order}
    for i, w in enumerate(weights):
        s = sum(w.values())
        for n, x in w.items():
            groups[n].add([i], x / s, "REPLACE")
    ob.parent = rig.ob
    mod = ob.modifiers.new("Armature", "ARMATURE"); mod.object = rig.ob
    return ob


# ------------------------------------------------------------------ painted texture (procedural, baked)
def paint_material(name, base, dark, accent=None, noise_scale=6.0, contrast=0.6, accent_mask=None, streaks=0.0):
    """Emission material for baking: base/dark mottled by noise, an accent colour (blood, bruise, frost)
    where accent_mask nodes say. Colours are sRGB triples."""
    lin = lambda c: tuple(x ** 2.2 for x in c) + (1.0,)
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = noise_scale; nz.inputs["Detail"].default_value = 8.0
    nz.inputs["Roughness"].default_value = 0.62
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.5 - contrast * 0.25
    ramp.color_ramp.elements[1].position = 0.5 + contrast * 0.25
    ramp.color_ramp.elements[0].color = lin(dark)
    ramp.color_ramp.elements[1].color = lin(base)
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    col = ramp.outputs["Color"]
    # fine grain on top
    nz2 = nt.nodes.new("ShaderNodeTexNoise"); nz2.inputs["Scale"].default_value = noise_scale * 6; nz2.inputs["Detail"].default_value = 4.0
    nt.links.new(tc.outputs["Object"], nz2.inputs["Vector"])
    mg = nt.nodes.new("ShaderNodeMix"); mg.data_type = "RGBA"; mg.blend_type = "MULTIPLY"; mg.inputs["Factor"].default_value = 0.35
    nt.links.new(col, mg.inputs[6])
    r2 = nt.nodes.new("ShaderNodeMapRange"); r2.inputs["From Min"].default_value = 0.3; r2.inputs["From Max"].default_value = 0.7
    r2.inputs["To Min"].default_value = 0.75; r2.inputs["To Max"].default_value = 1.15
    nt.links.new(nz2.outputs["Fac"], r2.inputs["Value"])
    cc = nt.nodes.new("ShaderNodeCombineColor")
    for k in ("Red", "Green", "Blue"):
        nt.links.new(r2.outputs["Result"], cc.inputs[k])
    nt.links.new(cc.outputs["Color"], mg.inputs[7])
    col = mg.outputs[2]
    if accent is not None and accent_mask is not None:
        mask = accent_mask(nt, tc)
        mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"
        nt.links.new(mask, mx.inputs["Factor"])
        nt.links.new(col, mx.inputs[6])
        mx.inputs[7].default_value = lin(accent)
        col = mx.outputs[2]
    nt.links.new(col, em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    m["base"] = base
    return m


def mask_near(points, radius, falloff=0.6, noise_amt=0.5, noise_scale=9.0):
    """Accent mask: near any of the points (object space), broken up by noise (splatter)."""
    def f(nt, tc):
        acc = None
        for p in points:
            vm = nt.nodes.new("ShaderNodeVectorMath"); vm.operation = "DISTANCE"
            nt.links.new(tc.outputs["Object"], vm.inputs[0]); vm.inputs[1].default_value = Vector(p)
            mr = nt.nodes.new("ShaderNodeMapRange")
            mr.inputs["From Min"].default_value = radius * (1 - falloff); mr.inputs["From Max"].default_value = radius
            mr.inputs["To Min"].default_value = 1.0; mr.inputs["To Max"].default_value = 0.0
            nt.links.new(vm.outputs["Value"], mr.inputs["Value"])
            if acc is None:
                acc = mr.outputs["Result"]
            else:
                mx = nt.nodes.new("ShaderNodeMath"); mx.operation = "MAXIMUM"
                nt.links.new(acc, mx.inputs[0]); nt.links.new(mr.outputs["Result"], mx.inputs[1]); acc = mx.outputs[0]
        nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = noise_scale; nz.inputs["Detail"].default_value = 6
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        sub = nt.nodes.new("ShaderNodeMath"); sub.operation = "MULTIPLY_ADD"
        nt.links.new(nz.outputs["Fac"], sub.inputs[0]); sub.inputs[1].default_value = noise_amt * 2; sub.inputs[2].default_value = -noise_amt
        add = nt.nodes.new("ShaderNodeMath"); add.operation = "ADD"; add.use_clamp = True
        nt.links.new(acc, add.inputs[0]); nt.links.new(sub.outputs[0], add.inputs[1])
        sm = nt.nodes.new("ShaderNodeMapRange"); sm.inputs["From Min"].default_value = 0.45; sm.inputs["From Max"].default_value = 0.6
        nt.links.new(add.outputs[0], sm.inputs["Value"])
        return sm.outputs["Result"]
    return f


def mask_noise(scale=3.0, cover=0.22, extra=None):
    """Accent mask: large noise patches covering about `cover` of the surface (raw flesh, stains),
    combined with another mask (extra) if given."""
    def f(nt, tc):
        nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = scale; nz.inputs["Detail"].default_value = 7
        nz.inputs["Roughness"].default_value = 0.65
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        mr = nt.nodes.new("ShaderNodeMapRange")
        t = 0.56 - cover * 0.25
        mr.inputs["From Min"].default_value = t; mr.inputs["From Max"].default_value = t + 0.07
        nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
        out = mr.outputs["Result"]
        if extra:
            mx = nt.nodes.new("ShaderNodeMath"); mx.operation = "MAXIMUM"
            nt.links.new(out, mx.inputs[0]); nt.links.new(extra(nt, tc), mx.inputs[1]); out = mx.outputs[0]
        return out
    return f


def bake_texture(ob, size=1024, ao=0.45, path=None):
    """Smart-UV the body, bake the emission paint and ambient occlusion, multiply, and replace every
    material with one base-colour material using the baked image (what the exporter and toon shader want)."""
    sc = bpy.context.scene
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.006)
    bpy.ops.object.mode_set(mode="OBJECT")
    mods = [(m, m.show_viewport, m.show_render) for m in ob.modifiers]
    for m, _, _ in mods:
        m.show_viewport = False; m.show_render = False
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 1
    imgs = {}
    for kind in ("EMIT", "AO"):
        img = bpy.data.images.new("bake_" + kind, size, size, alpha=False)
        img.colorspace_settings.name = "sRGB" if kind == "EMIT" else "Non-Color"
        imgs[kind] = img
        for m in ob.data.materials:
            nt = m.node_tree
            for n in [n for n in nt.nodes if n.name == "BakeTarget"]:
                nt.nodes.remove(n)
            tn = nt.nodes.new("ShaderNodeTexImage"); tn.name = "BakeTarget"; tn.image = img
            nt.nodes.active = tn
        if kind == "AO":
            sc.cycles.samples = 24
            sc.world = sc.world or bpy.data.worlds.new("W")
            sc.render.bake.use_pass_direct = False
        bpy.ops.object.bake(type=kind, margin=6, use_clear=True)
    for m, v, r in mods:
        m.show_viewport = v; m.show_render = r
    W, H = size, size
    e = np.array(imgs["EMIT"].pixels[:], np.float32).reshape(H, W, 4)
    a = np.array(imgs["AO"].pixels[:], np.float32).reshape(H, W, 4)
    k = (1 - ao) + ao * np.clip(a[..., :1], 0, 1) ** 0.8
    e[..., :3] = e[..., :3] * k
    final = bpy.data.images.new("paint", W, H, alpha=False)
    final.pixels[:] = e.ravel()
    if path:
        final.filepath_raw = path; final.file_format = "PNG"; final.save()
    m = bpy.data.materials.new("Paint"); m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    tn = m.node_tree.nodes.new("ShaderNodeTexImage"); tn.image = final
    m.node_tree.links.new(tn.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.9
    ob.data.materials.clear()
    ob.data.materials.append(m)
    for p in ob.data.polygons:
        p.material_index = 0
    sc.render.engine = "BLENDER_WORKBENCH"
    return final


# ------------------------------------------------------------------ clips and export
def new_action(rig, name):
    a = bpy.data.actions.new(name)
    a.use_fake_user = True
    rig.ob.animation_data_create()
    rig.ob.animation_data.action = a
    return a


def export(rig, out, clips_json):
    import json
    bpy.ops.export_scene.gltf(filepath=out + ".glb", export_format="GLB", export_animations=True,
                              export_animation_mode="ACTIONS", export_force_sampling=True, export_frame_range=False,
                              export_def_bones=False, export_apply=False, use_selection=False,
                              export_image_format="JPEG", export_jpeg_quality=88)
    json.dump(clips_json, open(out + ".json", "w"), indent=1)


def gait(p, duty, stride, lift, y0):
    """Foot along -Y (forward) for phase p in [0,1): on the ground for `duty` (moving back at the body's
    speed), then a swing forward. Returns (y, z)."""
    p = p % 1.0
    if p < duty:
        s = p / duty
        return y0 - stride / 2 + stride * s, 0.0                         # planted: slides back under the body
    s = (p - duty) / (1 - duty)
    e = 0.5 - 0.5 * math.cos(math.pi * s)
    return y0 + stride / 2 - stride * e, lift * math.sin(math.pi * s)


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)
