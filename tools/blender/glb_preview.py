"""Preview Tripo GLBs under the game's camera (30 degree iso, toon shading) at four turns, so you can
see what each model is and which turn puts its front towards the room (the kit's +y).
Usage: python3 -I glb_preview.py out.png model1.glb [model2.glb ...]"""
import sys, os, math, json
import bpy
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit
OUT, FILES = sys.argv[1], sys.argv[2:]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
kit.GLB_DIR = "/"
objs = []
for r, f in enumerate(FILES):
    for c, rot in enumerate((0, 90, 180, 270)):
        ob, size = kit.glb_prop(f"m{r}_{rot}", os.path.abspath(f).lstrip("/"), 1.0, 1.0, rot=rot, fit="z", H=1.6)
        # kit frame: front is +y. Place each so +y points at the camera-left (like a prop facing -v).
        ob.matrix_world = Matrix.Translation((c * 3.4, -r * 3.4, 0)) @ Matrix.Rotation(math.radians(180 + 45), 4, "Z") @ ob.matrix_world
        objs.append(ob)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam)
_E = math.radians(json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "camera.json")))["elev_deg"])
cam.data.type = "ORTHO"; cam.rotation_euler = (math.pi / 2 - _E, 0, 0); sc.camera = cam
cx, cy = 1.5 * 3.4, -(len(FILES) - 1) * 1.7
cam.location = Vector((cx, cy, 0.6)) - Vector((0, math.cos(_E), -math.sin(_E))) * 40
cam.data.ortho_scale = max(14.0, len(FILES) * 4.0)
sc.render.engine = "CYCLES"; sc.cycles.samples = 4; sc.cycles.max_bounces = 0
sc.render.resolution_x, sc.render.resolution_y = 1400, max(500, 380 * len(FILES))
sc.render.film_transparent = False
sc.world = bpy.data.worlds.new("W"); sc.world.color = (0.25, 0.24, 0.22)
sc.view_settings.view_transform = "Standard"
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("wrote", OUT)
