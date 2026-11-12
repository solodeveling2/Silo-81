"""Junk Town goat for live 3D (game/scripts/puppet3d.gd): a low-poly rigged goat with a grazing loop.

Proportions (docs/JUNK_TOWN_ASSETS.md art pass): long barrel body, short legs, a visible neck, a small
head with a darker face, swept-back horns, a beard and an upturned tail. Three bones (body, neck, head);
the "graze" clip dips the head to the hay, crops and chews, lifts to look round, and goes back down.
Faces -Y in Blender (+Z in Godot, like the Mixamo characters). Base colour only (the toon shader reads
nothing else).

Usage: python3 -I goat_live.py OUT_BASENAME [brown|piebald]   -> OUT.glb + OUT.json
"""
import sys, json, math
import bpy, bmesh
from mathutils import Vector, Matrix

OUT = sys.argv[1]
COAT = sys.argv[2] if len(sys.argv) > 2 else "brown"
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 24

PALETTE = {
    "brown":   dict(coat=(0.33, 0.27, 0.21), belly=(0.46, 0.40, 0.32), face=(0.13, 0.11, 0.09)),
    "piebald": dict(coat=(0.60, 0.58, 0.53), belly=(0.48, 0.46, 0.42), face=(0.15, 0.13, 0.12)),
}[COAT]


def mat(name, srgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    lin = tuple(c ** 2.2 for c in srgb)
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*lin, 1)
    return m


MATS = [mat("GoatCoat", PALETTE["coat"]), mat("GoatBelly", PALETTE["belly"]), mat("GoatFace", PALETTE["face"]),
        mat("GoatHorn", (0.52, 0.47, 0.36)), mat("GoatHoof", (0.10, 0.09, 0.08))]
COAT_I, BELLY_I, FACE_I, HORN_I, HOOF_I = range(5)

bm = bmesh.new()
groups = {}                                         # vertex index -> bone name


def tag(verts, bone):
    for v in verts:
        groups[v] = bone


def ellipsoid(c, r, mi, bone, seg=10, M=Matrix()):
    res = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=max(4, seg // 2), radius=1.0,
                                    matrix=M @ Matrix.Translation(c) @ Matrix.Diagonal((r[0], r[1], r[2], 1.0)))
    for f in {f for v in res["verts"] for f in v.link_faces}:
        f.material_index = mi
    tag(res["verts"], bone)


def cyl(p0, p1, r0, r1, mi, bone, seg=7):
    p0, p1 = Vector(p0), Vector(p1)
    ax = (p1 - p0).normalized()
    t = Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0))
    n = ax.cross(t).normalized(); b = ax.cross(n)
    ring = lambda p, r: [bm.verts.new(p + r * (math.cos(2 * math.pi * k / seg) * n + math.sin(2 * math.pi * k / seg) * b)) for k in range(seg)]
    a, c = ring(p0, r0), ring(p1, r1)
    for k in range(seg):
        bm.faces.new([a[k], a[(k + 1) % seg], c[(k + 1) % seg], c[k]]).material_index = mi
    bm.faces.new(a[::-1]).material_index = mi
    bm.faces.new(c).material_index = mi
    tag(a + c, bone)


# ---- body (barrel), belly, legs, tail
ellipsoid((0, 0.02, 0.47), (0.19, 0.40, 0.21), COAT_I, "body", seg=12)
ellipsoid((0, 0.04, 0.37), (0.14, 0.30, 0.10), BELLY_I, "body", seg=10)
ellipsoid((0, -0.30, 0.52), (0.16, 0.14, 0.18), COAT_I, "body", seg=10)    # shoulders
LEGS = {}                                           # bone name -> hip point
for sx in (-1, 1):
    for y in (-0.27, 0.27):
        leg = ("f" if y < 0 else "b") + ("l" if sx < 0 else "r")
        LEGS[leg] = Vector((sx * 0.11, y, 0.40))
        cyl((sx * 0.11, y, 0.38), (sx * 0.11, y + 0.01, 0.06), 0.045, 0.032, COAT_I, leg)
        cyl((sx * 0.11, y + 0.01, 0.06), (sx * 0.11, y + 0.01, 0.0), 0.035, 0.037, HOOF_I, leg)
cyl((0, 0.38, 0.58), (0, 0.44, 0.72), 0.035, 0.012, COAT_I, "body", seg=5)    # tail, cocked up

# ---- neck and head (built in the rest pose: head up, looking forward)
NECK0, NECK1 = Vector((0, -0.33, 0.58)), Vector((0, -0.45, 0.78))
cyl(NECK0, NECK1, 0.085, 0.06, COAT_I, "neck")
H = Vector((0, -0.52, 0.82))                       # skull centre
ellipsoid(H, (0.065, 0.10, 0.07), COAT_I, "head", seg=9)
ellipsoid(H + Vector((0, -0.10, -0.035)), (0.045, 0.085, 0.045), FACE_I, "head", seg=8)   # face and muzzle
ellipsoid(H + Vector((0, -0.175, -0.05)), (0.035, 0.03, 0.03), FACE_I, "head", seg=6)     # nose
cyl(H + Vector((0, -0.12, -0.08)), H + Vector((0, -0.10, -0.16)), 0.022, 0.006, FACE_I, "head", seg=5)  # beard
for sx in (-1, 1):
    cyl(H + Vector((sx * 0.035, 0.0, 0.05)), H + Vector((sx * 0.05, 0.10, 0.12)), 0.016, 0.006, HORN_I, "head", seg=5)
    cyl(H + Vector((sx * 0.055, 0.02, 0.02)), H + Vector((sx * 0.13, 0.05, -0.02)), 0.022, 0.01, COAT_I, "head", seg=5)  # ears

me = bpy.data.meshes.new("Goat")
bm.verts.index_update()
idx_of = {v: v.index for v in bm.verts}
vg_idx = {idx_of[v]: g for v, g in groups.items()}
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
bm.to_mesh(me); bm.free()
for m in MATS:
    me.materials.append(m)
for p in me.polygons:
    p.use_smooth = False
body = bpy.data.objects.new("Goat", me)
sc.collection.objects.link(body)

# ---- armature: body -> neck -> head
arm_data = bpy.data.armatures.new("GoatRig")
arm = bpy.data.objects.new("GoatRig", arm_data)
sc.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
eb = arm_data.edit_bones
b_body = eb.new("body"); b_body.head = (0, 0.3, 0.47); b_body.tail = (0, -0.3, 0.47)
b_neck = eb.new("neck"); b_neck.head = NECK0; b_neck.tail = NECK1; b_neck.parent = b_body
b_head = eb.new("head"); b_head.head = NECK1; b_head.tail = H + Vector((0, -0.16, -0.03)); b_head.parent = b_neck
for b in (b_neck, b_head):
    b.roll = 0.0
for leg, hip in LEGS.items():                        # legs hang from the body; swing about their x axis
    lb = eb.new(leg); lb.head = hip; lb.tail = (hip.x, hip.y + 0.01, 0.0); lb.parent = b_body; lb.roll = 0.0
bpy.ops.object.mode_set(mode="OBJECT")
for name in ("body", "neck", "head") + tuple(LEGS):
    vg = body.vertex_groups.new(name=name)
    vg.add([i for i, g in vg_idx.items() if g == name], 1.0, "REPLACE")
body.parent = arm
mod = body.modifiers.new("Armature", "ARMATURE"); mod.object = arm

# ---- the grazing loop (4 s at 24 fps): down and cropping, chew, lift and look round, back down
N = 96
act = bpy.data.actions.new("graze")
arm.animation_data_create(); arm.animation_data.action = act
P = arm.pose.bones
for pb in P:
    pb.rotation_mode = "XYZ"


def key(f, neck_pitch, head_pitch, neck_yaw=0.0, body_roll=0.0, legs=None, bob=0.0):
    """Angles in degrees; positive pitch lowers the head. legs: {bone: swing degrees}."""
    P["neck"].rotation_euler = (math.radians(neck_pitch), 0.0, math.radians(neck_yaw))
    P["head"].rotation_euler = (math.radians(head_pitch), 0.0, 0.0)
    P["body"].rotation_euler = (0.0, math.radians(body_roll), 0.0)
    P["body"].location = (0.0, 0.0, bob)
    for leg in LEGS:
        P[leg].rotation_euler = (math.radians((legs or {}).get(leg, 0.0)), 0.0, 0.0)
    for pb in P:
        pb.keyframe_insert("rotation_euler", frame=f)
        pb.keyframe_insert("location", frame=f)


DOWN, CROP = 62, 30
key(0,  DOWN, CROP)
key(8,  DOWN - 4, CROP - 8)                        # cropping tugs
key(14, DOWN, CROP)
key(22, DOWN - 5, CROP - 9, 4)
key(30, DOWN, CROP, 3)
key(40, 18, 6, 0, 1)                               # head comes up, chewing
key(48, 14, 2, -18, 1)                             # looks round
key(56, 15, 4, -20, 0)
key(64, 16, 2, 12, -1)
key(72, 18, 6, 10, 0)
key(84, DOWN - 2, CROP - 2, 2)                     # back down to the hay
key(N,  DOWN, CROP)
sc.frame_start, sc.frame_end = 0, N
act.use_fake_user = True

# ---- the walk (1 s at 24 fps): diagonal pairs swing together, the body bobs twice, the head nods
W = 24
walk = bpy.data.actions.new("walk"); walk.use_fake_user = True
arm.animation_data.action = walk
SW = 22.0
for f in range(0, W + 1, 2):
    ph = 2 * math.pi * f / W
    a = SW * math.sin(ph)
    key(f, 14 + 4 * math.sin(2 * ph), 4, 0.0, 0.0,
        legs={"fl": a, "br": a, "fr": -a, "bl": -a}, bob=0.012 * abs(math.cos(ph)))
arm.animation_data.action = act

bpy.ops.export_scene.gltf(filepath=OUT + ".glb", export_format="GLB", export_animations=True,
                          export_animation_mode="ACTIONS", export_force_sampling=True, export_frame_range=False,
                          export_def_bones=False, export_apply=False, use_selection=False)
# a foot moves 2 * 0.40 * sin(22) = 0.30 m over its 12-frame stance: about 0.025 m a frame (0.6 m/s)
json.dump({"fps_src": 24, "clips": {"idle": "graze", "walk": "walk"}, "idle_loop_src": [0, N], "height_m": 0.85,
           "walk_m_per_frame": 0.025, "walk_frames": W,
           "creature": "goat", "coat": COAT}, open(OUT + ".json", "w"), indent=1)
print("exported", OUT, COAT, len(me.vertices), "verts")
