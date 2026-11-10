"""Camera / wall-hierarchy experiment on one representative section of Level 2: your room, part of
Dormitory 2-A, the corridor, and the washroom / Dormitory 2-C wall across it, with the real player
model and the real Tripo furniture placed through kit.place / kit.footprint (the game's own data path).

  python3 -I exp_camera.py OUT_PREFIX ELEV

Writes OUT_PREFIX.png (the view at the game's 0.62 zoom) and OUT_PREFIX_check.json: screen positions,
from Blender's own camera, of the points the game computes with its projection formula
sx = x*PPM, sy = -(y*sin(e) + z*cos(e))*PPM, so the formula can be validated before anything is rebuilt.
"""
import sys, os, math, json
import bpy
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit
from kit import Builder, toon, g, place, footprint

PREFIX, ELEV = sys.argv[1], float(sys.argv[2])
CW = float(sys.argv[3]) if len(sys.argv) > 3 else 2.8         # corridor width (wall centre to wall centre)
DV = CW - 2.8                                                  # the camera-side wall and the rooms behind it move by this


def sv(v):
    """Shift plan v for everything on the far (camera) side of the corridor."""
    return v - DV if v <= -1.4 + 1e-6 else v
E = math.radians(ELEV)
PPM, ZOOM = 165.0, 0.62
kit.GLB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "props3d")
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene

# ---- wall hierarchy
STRUCT = dict(t=0.30, h=2.70, post=True)       # shelter shell: full height and weight
CORR = dict(t=0.18, h=2.70, post=False)        # corridor walls: full height, lighter
PART = dict(t=0.12, h=2.35, post=False)        # partitions between rooms: thin, stop short of the slab
wall = toon("Wall", (1.0, 1.0, 1.0), tex="plaster_cream", tex_scale=2.0, dado=((0.55, 0.78, 0.66), 1.25))
shell = toon("Shell", (0.96, 0.95, 0.92), tex="concrete_wall", tex_scale=2.2, dado=((0.55, 0.78, 0.66), 1.25))
top = toon("Top", (0.055, 0.052, 0.048))
top_part = toon("TopPart", (0.11, 0.105, 0.1))  # thin partitions: a lighter, finer cap line
AGED = os.environ.get("AGE") == "1"
PAINT = {"corridor": ((1.0, 1.0, 1.0), (0.55, 0.78, 0.66), 1.25), "sleeping": ((1.0, 0.94, 0.82), (0.6, 0.72, 0.6), 1.1),
         "wet": ((0.95, 0.98, 0.96), (0.62, 0.8, 0.76), 1.5), "out": ((1.0, 1.0, 1.0), (0.55, 0.78, 0.66), 1.25)}


def face_mat(prof, seed):
    """Same recipe as build.py's wall_material for painted walls."""
    if not AGED:
        return wall
    up, low, h = PAINT[prof]
    return toon(f"Aged_{prof}_{seed}", up, tex="plaster_cream", tex_scale=2.0, dado=(low, h),
                age=dict(kit.AGE_PROFILES[prof if prof != "out" else "corridor"], seed=seed))
skirt = toon("Skirt", (0.22, 0.23, 0.21))
jamb = toon("Jamb", (0.42, 0.42, 0.4), tex="concrete_wall", tex_scale=1.2)
floor_c = toon("FloorC", (0.5, 0.49, 0.45), tex="concrete_floor", tex_scale=1.5)
floor_w = toon("FloorW", (0.44, 0.36, 0.28), tex="wood_planks", tex_scale=2.4)
tile = toon("Tile", (0.62, 0.66, 0.62), tex="tile_frosted", tex_scale=1.2)


def plan_ob(ob):
    """Builder geometry is in plan (u, v); turn it into ground space like build.py does."""
    ob.matrix_world = Matrix.Rotation(math.radians(45), 4, "Z") @ ob.matrix_world
    return ob


b = Builder("Floors")
b.box(0.6, 11.6, 1.4, 5.6, -0.05, 0.0, floor_c)
b.box(0.6, 4.6, 1.4, 5.6, -0.04, 0.001, floor_w)
b.box(1.0, 7.0, sv(-5.0), sv(-1.4), -0.05, 0.0, tile)
b.box(7.0, 11.6, sv(-5.0), sv(-1.4), -0.05, 0.0, floor_c)
plan_ob(b.finish())
b = Builder("Corridor")                                        # its own object, for the visibility mask
b.box(-1.0, 11.6, sv(-1.4), 1.4, -0.05, 0.0, floor_c)
CORRIDOR = plan_ob(b.finish())


def wallrun(b, a, c, kind, gaps=(), sides=None):
    t, h, post = kind["t"], kind["h"], kind["post"]
    mat = shell if kind is STRUCT else wall
    fm = None
    if AGED and sides:
        ma, mb = face_mat(*sides[0]), face_mat(*sides[1])
        mat = ma
        fm = {2: ma, 3: mb} if a[1] == c[1] else {0: ma, 1: mb}
    cap = top if t >= 0.18 else top_part
    (ua, va), (ub, vb) = a, c
    along_u = va == vb
    lo, hi = (min(ua, ub), max(ua, ub)) if along_u else (min(va, vb), max(va, vb))

    def box(s0, s1, half, z0, z1, m, tm=None):
        f_ = fm if m is mat else None
        if along_u:
            b.box(s0, s1, va - half, va + half, z0, z1, m, top_mat=tm, faces_mat=f_)
        else:
            b.box(ua - half, ua + half, s0, s1, z0, z1, m, top_mat=tm, faces_mat=f_)
    cur = lo - t / 2
    for g0, g1 in sorted(gaps) + [(hi + t / 2, None)]:
        if g0 - cur > 0.01:
            box(cur, g0, t / 2, 0, h, mat, cap)
            box(cur, g0, t / 2 + 0.02, 0, 0.12, skirt, skirt)
        if g1 is None:
            break
        box(g0, g1, t / 2, 2.1, h, mat, cap)                       # lintel
        box(g0 - 0.05, g1 + 0.05, t / 2 + 0.025, 2.1, 2.2, jamb, jamb)
        for e in (g0, g1):                                          # slim frame, sized to this wall
            box(e - 0.05, e + 0.05, t / 2 + 0.025, 0, 2.2, jamb, jamb)
        cur = g1
    if post:
        for e in (lo, hi):
            box(e - (t + 0.1) / 2, e + (t + 0.1) / 2, (t + 0.1) / 2, 0, h + 0.03, mat, top)


b = Builder("Walls")
wallrun(b, (0.6, 5.6), (11.6, 5.6), STRUCT, sides=[("sleeping", 1.1), ("out", 0.0)])       # back: shelter shell
wallrun(b, (0.6, 1.4), (0.6, 5.6), STRUCT, sides=[("out", 0.0), ("sleeping", 1.1)])        # left: shell (landing side)
wallrun(b, (4.6, 1.4), (4.6, 5.6), PART, sides=[("sleeping", 1.1), ("sleeping", 4.3)])     # your room | dorm 2-A
wallrun(b, (0.6, 1.4), (11.6, 1.4), CORR, gaps=[(2.1, 3.1), (7.4, 8.8)], sides=[("corridor", 2.2), ("sleeping", 1.1)])
wallrun(b, (1.0, sv(-1.4)), (11.6, sv(-1.4)), CORR, gaps=[(3.6, 4.6), (9.4, 10.4)], sides=[("wet", 6.6), ("corridor", 2.2)])
wallrun(b, (7.0, sv(-5.0)), (7.0, sv(-1.4)), PART, sides=[("wet", 6.6), ("sleeping", 7.7)])   # washroom | dorm 2-C
wallrun(b, (1.0, sv(-5.0)), (1.0, sv(-1.4)), STRUCT, sides=[("out", 0.0), ("wet", 6.6)])
plan_ob(b.finish())

# ---- furniture through the game's own placement (back of the prop at (u, v), front facing f)
PROPS = [("silo81_bed_player.glb", 180, "x", None, 2.0, 0.9, 1.6, 5.6 - 0.15, "-v"),
         ("silo81_locker.glb", 180, "x", None, 1.0, 0.5, 0.6 + 0.15, 3.3, "+u"),
         ("silo81_desk.glb", 180, "x", None, 1.2, 0.6, 4.6 - 0.06, 3.0, "-u"),
         ("silo81_chair.glb", 180, "z", 0.9, 0.5, 0.5, 3.6, 2.7, "+u"),
         ("silo81_bunk_a.glb", 180, "x", None, 2.0, 0.9, 6.6, 5.6 - 0.15, "-v"),
         ("silo81_bunk_b.glb", 180, "x", None, 2.0, 0.9, 9.4, 5.6 - 0.15, "-v"),
         ("silo81_washbasin.glb", 180, "z", 0.5, 0.56, 0.45, 2.4, -5.0 + 0.15, "+v"),
         ("silo81_toilet_stall.glb", 180, "z", 2.05, 0.9, 1.2, 6.3, -5.0 + 0.15, "+v")]
fps = []
for f, rot, fit, H, L, D, u, v, face in PROPS:
    ob, _ = kit.glb_prop(f, f, L, D, rot=rot, fit=fit, H=H)
    if f.endswith("washbasin.glb"):
        ob.data.transform(Matrix.Translation((0, 0, 0.38)))
    place([ob], u, sv(v), face)
    fps.append(footprint(u, sv(v), face, L, D))

# ---- the player: the real model, rest of the first frame of idle, feet at plan (2.6, 0.0)
PU, PV = 6.0, 1.4 - CW / 2                                       # mid-corridor
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath="/home/claude/ual/player_male_v2.glb")
new = [o for o in bpy.data.objects if o not in before]
arm = next(o for o in new if o.type == "ARMATURE")
acts = [a for a in bpy.data.actions if "idle" == a.name.split("|")[-1].lower() or a.name.lower().endswith("idle")]
if arm.animation_data and acts:
    arm.animation_data.action = acts[0]
sc.frame_set(1)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
for o in [o for o in new if o.type == "MESH" and not o.name.startswith("tripo")]:      # stray helper meshes in the GLB
    new.remove(o); bpy.data.objects.remove(o, do_unlink=True)
zs = []
for o in new:
    if o.type == "MESH":
        e = o.evaluated_get(dg); me = e.to_mesh()
        zs += [(e.matrix_world @ v.co).z for v in me.vertices]
        e.to_mesh_clear()
s = 1.78 / (max(zs) - min(zs))
px, py = g(PU, PV)
arm.matrix_world = Matrix.Translation((px, py, -min(zs) * s)) @ Matrix.Rotation(math.radians(-135), 4, "Z") @ Matrix.Scale(s, 4) @ arm.matrix_world
for o in new:
    if o.type == "MESH":
        for slot in o.material_slots:
            kit._toon_textured(slot.material)

# ---- camera: orthographic, diagonal across the plan, ELEV above the horizon
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam)
cam.data.type = "ORTHO"
cam.rotation_euler = (math.radians(90) - E, 0, 0)
sc.camera = cam
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 8; sc.cycles.use_denoising = False
sc.cycles.max_bounces = 0
sc.view_settings.view_transform = "Standard"
sc.world = bpy.data.worlds.new("W"); sc.world.color = (0.012, 0.012, 0.014)
W, Hh = 2064, 1160                     # 1280x720 game view at zoom 0.62
sc.render.resolution_x, sc.render.resolution_y = W, Hh
cam.data.ortho_scale = W / PPM
cx, cy = g(5.2, 0.8)
centre = Vector((cx, cy, 0.9))
view = Vector((0, math.cos(E), -math.sin(E)))
cam.location = centre - view * 60
sc.render.filepath = PREFIX + "_full.png"
bpy.ops.render.render(write_still=True)

if os.environ.get("SAVE_BLEND"):                 # a self-contained .blend of this section, for opening in Blender
    try:
        bpy.ops.file.pack_all()
    except Exception as e:
        print("pack_all:", e)
    bpy.ops.wm.save_as_mainfile(filepath=os.environ["SAVE_BLEND"], compress=True)
    print("saved", os.environ["SAVE_BLEND"])

# ---- how much corridor floor can be seen: a mask pass (corridor white, everything else black)
white = bpy.data.materials.new("MaskW"); white.use_nodes = True
black = bpy.data.materials.new("MaskB"); black.use_nodes = True
for m, col in ((white, (1, 1, 1, 1)), (black, (0, 0, 0, 1))):
    nt = m.node_tree; nt.nodes.clear(); o = nt.nodes.new("ShaderNodeOutputMaterial"); e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = col; nt.links.new(e.outputs[0], o.inputs[0])
for ob in sc.objects:
    if ob.type == "MESH":
        for slot in ob.material_slots:
            slot.material = white if ob is CORRIDOR else black
        for md in ob.modifiers:
            md.show_render = False
sc.cycles.samples = 1
sc.render.resolution_percentage = 25
import numpy as np


def count(path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(path); px = np.array(im.pixels[:]).reshape(-1, 4)
    return int((px[:, 0] > 0.5).sum())


seen = count(PREFIX + "_mask.png")
for ob in sc.objects:
    if ob.type == "MESH" and ob is not CORRIDOR:
        ob.hide_render = True
total = count(PREFIX + "_mask_all.png")
VIS = {"corridor_width_m": CW, "visible_floor_fraction": round(seen / max(1, total), 3)}
print("corridor floor visible", VIS)


# ---- projection check: Blender's camera vs the game's formula for the same points
def pix(p):
    c = world_to_camera_view(sc, cam, Vector(p))
    return [c.x * W, (1 - c.y) * Hh]


def formula(p):
    return [p[0] * PPM, -(p[1] * math.sin(E) + p[2] * math.cos(E)) * PPM]


pts = {"feet": (px, py, 0.0), "head": (px, py, 1.78)}
for i, fp in enumerate(fps):
    for k, (u, v) in enumerate([(fp[0], fp[2]), (fp[1], fp[2]), (fp[1], fp[3]), (fp[0], fp[3])]):
        gx, gy = g(u, v); pts[f"fp{i}_{k}"] = (gx, gy, 0.0)
for k in range(16):                                # the selection ring: r = 0.34 m on the ground
    a = 2 * math.pi * k / 16
    pts[f"ring{k}"] = (px + 0.34 * math.cos(a), py + 0.34 * math.sin(a), 0.0)
f0, b0 = formula(pts["feet"]), pix(pts["feet"])
check = {"elev": ELEV, "W": W, "H": Hh, "points": {}}
worst = 0.0
for k, p in pts.items():
    fp_ = formula(p)
    pred = [b0[0] + fp_[0] - f0[0], b0[1] + fp_[1] - f0[1]]          # formula, anchored at the feet
    act = pix(p)
    err = math.hypot(pred[0] - act[0], pred[1] - act[1])
    worst = max(worst, err)
    check["points"][k] = {"blender": act, "formula": pred, "err_px": round(err, 3)}
check["worst_err_px"] = round(worst, 3)
check["footprints"] = fps
check.update(VIS)
json.dump(check, open(PREFIX + "_check.json", "w"), indent=1)
print("worst projection error px", worst)
