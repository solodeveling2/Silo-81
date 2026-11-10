import bpy
import glob
import os
import math
from mathutils import Vector

SRC = r"D:\Silo-81-main\Silo-81-main\source\props3d\junk_town"
OUT = r"D:\Silo-81-main\Silo-81-main\out\glb_preview"
os.makedirs(OUT, exist_ok=True)

for f in sorted(glob.glob(os.path.join(SRC, "*.glb"))):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=f)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        print("NO_MESH", f)
        continue
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    for o in meshes:
        for c in o.bound_box:
            p = o.matrix_world @ Vector(c)
            mn = Vector((min(mn[i], p[i]) for i in range(3)))
            mx = Vector((max(mx[i], p[i]) for i in range(3)))
    size = mx - mn
    center = (mn + mx) / 2
    maxdim = max(size)

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = maxdim * 1.25
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    d = 4.0
    direction = Vector((math.cos(math.radians(45)) * math.cos(math.radians(47)),
                        math.sin(math.radians(45)) * math.cos(math.radians(47)),
                        math.sin(math.radians(47))))
    cam.location = center + direction * d
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam

    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "TEXTURE"
    sc.display.shading.show_shadows = True
    sc.render.film_transparent = True
    sc.render.resolution_x = 512
    sc.render.resolution_y = 512
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    name = os.path.splitext(os.path.basename(f))[0]
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("PREVIEW", name, [round(v, 3) for v in size])
