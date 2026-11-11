"""Quick look at a code-built creature: Cycles renders at the game camera (47 degrees, orthographic),
a few frames of each clip, two facings, pasted into one contact sheet. For checking shape and poses
before the game; the game's own look comes from the toon shader."""
import math, os, json
import bpy
import numpy as np
from mathutils import Vector, Euler

ELEV = 47.0


def render(rig, body, out_dir, frames, size=360, span=1.7):
    os.makedirs(out_dir, exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 12
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.world = sc.world or bpy.data.worlds.new("W")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.55, 0.58, 0.64, 1); bg.inputs["Strength"].default_value = 0.8
    cam_d = bpy.data.cameras.new("C"); cam_d.type = "ORTHO"; cam_d.ortho_scale = span
    cam = bpy.data.objects.new("C", cam_d); sc.collection.objects.link(cam); sc.camera = cam
    sun_d = bpy.data.lights.new("S", "SUN"); sun_d.energy = 3.0
    sun = bpy.data.objects.new("S", sun_d); sc.collection.objects.link(sun)
    sun.rotation_euler = Euler((math.radians(40), 0, math.radians(-40)))
    tiles = []
    e = math.radians(ELEV)
    for clip, fl in frames.items():
        act = bpy.data.actions[clip]
        rig.ob.animation_data.action = act
        for f in fl:
            sc.frame_set(f)
            for yaw in (0, 1):
                ang = math.radians(-60 if yaw == 0 else -150)
                d = Vector((math.sin(ang) * math.cos(e), -math.cos(ang) * math.cos(e), math.sin(e)))
                tgt = Vector((0, 0, 0.35 if span < 2.0 else 0.8))
                cam.location = tgt + d * 10
                cam.rotation_euler = (d * -1).to_track_quat("-Z", "Y").to_euler()
                p = os.path.join(out_dir, f"{clip}_{f}_{yaw}.png")
                sc.render.filepath = p
                bpy.ops.render.render(write_still=True)
                tiles.append(p)
    from PIL import Image
    cols = 8
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * size, rows * size), (70, 74, 80))
    for i, p in enumerate(tiles):
        im = Image.open(p).convert("RGBA")
        sheet.paste(im, ((i % cols) * size, (i // cols) * size), im)
    sheet.save(os.path.join(out_dir, "sheet.png"))
    print("preview", os.path.join(out_dir, "sheet.png"), len(tiles))
