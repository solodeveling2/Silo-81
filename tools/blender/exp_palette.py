"""Palette / material test scene at the gameplay camera: a maintenance workshop (pump, stove,
workbench, crate, toolbox, pipe run with a valve) beside a living quarter (locker, bunk, desk, chair),
with the levels' aged walls and concrete floor.

  SILO_LOOK=v1|v2 python3 -I exp_palette.py OUT.png [mood r,g,b]

mood multiplies the finished image the way the game's CanvasModulate does (to reproduce what the
player sees today). v2 also places two amber practical lamps and one cold pocket.
"""
import sys, os, math
import bpy
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit
from kit import Builder, toon, g, place

OUT = sys.argv[1]
MOOD = tuple(float(x) for x in sys.argv[2].split(",")) if len(sys.argv) > 2 else None
E = math.radians(47.0)
PPM = 165.0
kit.GLB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "props3d")
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
V2 = kit.LOOK == "v2"
if V2:
    kit.PRACTICALS[:] = [(*g(3.4, 3.9), 2.3, 3.6, kit.AMBER),            # caged lamp over the workbench
                         (*g(8.6, 3.2), 2.0, 3.0, tuple(c * 0.85 for c in kit.AMBER)),  # bulb in the quarters
                         (*g(0.6, 0.6), 0.8, 3.0, kit.COLD)]              # the unheated corner by the shaft

PAINT = {"maintenance": ((0.92, 0.91, 0.88), (0.6, 0.72, 0.62), 1.3, "concrete_wall", 2.2),
         "sleeping": ((1.0, 0.94, 0.82), (0.6, 0.72, 0.6), 1.1, "plaster_cream", 2.0)}


def wall_mat(prof, seed):
    up, low, h, tex, ts = PAINT[prof]
    return toon(f"W_{prof}_{seed}", up, tex=tex, tex_scale=ts, dado=(low, h), age=dict(kit.AGE_PROFILES[prof], seed=seed))


TOP = toon("WallTop", (0.055, 0.052, 0.048))
SK = toon("Skirting", (0.22, 0.23, 0.21))


def plan_ob(ob):
    ob.matrix_world = Matrix.Rotation(math.radians(45), 4, "Z") @ ob.matrix_world
    return ob


# floor
b = Builder("Floor")
b.box(-0.2, 10.5, -1.5, 4.6, -0.05, 0.0, toon("Floor", (0.5, 0.49, 0.45), tex="concrete_floor", tex_scale=1.5))
b.box(6.05, 10.5, 0.0, 4.5, -0.04, 0.001, toon("FloorWood", (0.44, 0.36, 0.28), tex="wood_planks", tex_scale=2.4))
plan_ob(b.finish())
# hazard marking round the pump
b = Builder("Hazard")
hz = toon("Hazard", (0.75, 0.6, 0.12))
for (u0, u1, v0, v1) in ((0.3, 2.7, 2.25, 2.4), (0.3, 0.45, 2.25, 4.4), (2.55, 2.7, 2.25, 4.4)):
    b.box(u0, u1, v0, v1, 0.0, 0.012, hz)
plan_ob(b.finish())
# walls: shell at the back and left, a partition between workshop and quarters
b = Builder("Walls")
wm, ws = wall_mat("maintenance", 3.1), wall_mat("sleeping", 7.2)
b.box(-0.15, 10.5, 4.5, 4.8, 0, 2.7, wm, top_mat=TOP, faces_mat={2: wm})            # back shell (workshop side)
b.box(6.0, 10.5, 4.5, 4.8, 0, 2.7, ws, top_mat=TOP, faces_mat={2: ws})             # back shell (quarters side)
b.box(-0.45, -0.15, -1.5, 4.8, 0, 2.7, wm, top_mat=TOP, faces_mat={1: wm})         # left shell
b.box(5.94, 6.06, 0.0, 4.5, 0, 2.35, wm, top_mat=toon("TopPart", (0.11, 0.105, 0.1)), faces_mat={0: wm, 1: ws})
for (u0, u1, v0, v1) in ((-0.15, 10.5, 4.48, 4.5), (-0.15, -0.13, -1.5, 4.5)):
    b.box(u0, u1, v0, v1, 0, 0.12, SK)
plan_ob(b.finish())
# pipe run on the back wall with a valve, and on the left wall
b = Builder("Pipes")
steel = toon("PipeFlow", (0.1, 0.1, 0.1))
green = toon("PipeWater", (0.2, 0.3, 0.25))
for (z, m, r) in ((2.05, green, 0.09), (1.8, steel, 0.07)):
    b.cyl((-0.15, 4.25, z), (5.9, 4.25, z), r, m, seg=16)
b.cyl((-0.0, 4.4, 1.8), (-0.0, -1.4, 1.8), 0.07, steel, seg=16)
b.cyl((1.0, 4.17, 1.8), (1.0, 4.04, 1.8), 0.12, toon("ValveRed", (0.5, 0.12, 0.1)), seg=16)
plan_ob(b.finish())


def glb(file, u, v, face, L, D, fit="x", H=None, tint=None):
    ob, _ = kit.glb_prop(file, file, L, D, rot=180, fit=fit, H=H, tint=tint)
    place([ob], u, v, face)


glb("silo81_pump.glb", 1.5, 4.35, "-v", 1.4, 0.8, tint=(0.82, 1.04, 1.06))      # grey-green -> industrial teal
glb("silo81_workbench.glb", 3.5, 4.35, "-v", 1.8, 0.7)
glb("silo81_stove.glb", 5.0, 4.35, "-v", 1.3, 0.7, tint=(0.9, 0.96, 1.06))      # cast iron -> dark blue-grey
glb("silo81_crate.glb", 4.6, 1.0, "+u", 0.62, 0.62)
glb("silo81_toolbox.glb", 2.9, 1.4, "-v", 1.0, 0.3)
glb("silo81_locker.glb", 7.0, 4.35, "-v", 1.0, 0.5)
glb("silo81_bunk_a.glb", 9.0, 4.35, "-v", 2.0, 0.9)
glb("silo81_desk.glb", 6.12, 1.8, "+u", 1.2, 0.6)
glb("silo81_chair.glb", 7.1, 1.8, "-u", 0.5, 0.5, fit="z", H=0.9)

# camera: the game's view (47 degrees, orthographic), 1280x720 at the game's 0.62 zoom
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam)
cam.data.type = "ORTHO"; cam.rotation_euler = (math.radians(90) - E, 0, 0); sc.camera = cam
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 8; sc.cycles.use_denoising = False
sc.cycles.max_bounces = 0
sc.view_settings.view_transform = "Standard"
sc.world = bpy.data.worlds.new("W"); sc.world.color = (0.012, 0.012, 0.014)
W, H = 2064, 1160
sc.render.resolution_x, sc.render.resolution_y = W, H
cam.data.ortho_scale = W / PPM
cx, cy = g(5.0, 2.2)
cam.location = Vector((cx, cy, 0.9)) - Vector((0, math.cos(E), -math.sin(E))) * 60
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)

from PIL import Image
im = Image.open(OUT).convert("RGB").resize((1280, 720), Image.LANCZOS)
if MOOD:                                          # what the game's CanvasModulate does to every pixel
    import numpy as np
    a = np.asarray(im).astype(float) * np.array(MOOD)
    im = Image.fromarray(np.clip(a, 0, 255).astype("uint8"))
im.save(OUT)
print("done", OUT)
