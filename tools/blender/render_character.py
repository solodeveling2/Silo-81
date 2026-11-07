"""Render a Tripo/Mixamo-rigged character (.glb with several animations) into 6 hex-direction
sprite sheets with Silo 81 toon shading, Fallout-style.

- Locomotion clips (walk, run) have their average forward root motion removed, so the sprite
  animates in place; that same motion, projected to the screen, becomes the per-frame step the
  game applies. Because the source motion-capture keeps planted feet fixed in the world, moving
  the sprite by that step keeps them fixed on screen too (checked below, per direction).
- Orthographic camera at 30 degrees elevation (2:1 isometric, same as the Silo 81 floor tiles).
- Painted base-colour texture x 3 toon bands from a fixed key light, plus an ink outline.

Usage: python3 render_character.py model.glb out_dir [anim_name ...]
Importing it as a module (render_aim.py does) sets the scene up without rendering.
"""
import sys, os, json, math
import bpy
from mathutils import Vector, Matrix
import bmesh
from bpy_extras.object_utils import world_to_camera_view

MODEL, OUT = sys.argv[1], sys.argv[2]
ONLY = set(sys.argv[3:])
HEIGHT_M = 1.75            # real-world height the character is scaled to
PPM = 165.0                # screen pixels per metre: a 1.75 m person is about 250 px tall on screen
ELEV = math.radians(30)    # 2:1 isometric
SAMPLES = 10
# name prefix -> settings. fps = sprite playback rate; src frames are 24 fps
ANIMS = {
    "walk":         dict(fps=24, inplace=True,  loop=True,  canvas=384),
    "run":          dict(fps=24, inplace=True,  loop=True,  canvas=384),
    "idle":         dict(fps=12, inplace=False, loop=True,  canvas=384, find_loop=(48, 200)),
    "hit":          dict(fps=24, inplace=False, loop=False, canvas=384),
    "pistol":       dict(fps=24, inplace=False, loop=False, canvas=384),
    "fall":         dict(fps=24, inplace=False, loop=False, canvas=768),
    "pistol_idle":  dict(fps=24, inplace=False, loop=True,  canvas=384),
    "pistol_aim":   dict(fps=24, inplace=False, loop=False, canvas=384),
    "pistol_attack": dict(fps=24, inplace=False, loop=False, canvas=384),
    "pistol_shoot": dict(fps=24, inplace=False, loop=False, canvas=384),
    "hit_chest":    dict(fps=24, inplace=False, loop=False, canvas=384),
    "death":        dict(fps=24, inplace=False, loop=False, canvas=768),
}
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=MODEL)
for o in list(bpy.data.objects):
    if o.type == "MESH" and o.parent is None:
        bpy.data.objects.remove(o, do_unlink=True)          # stray helper meshes
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
body = next(o for o in bpy.data.objects if o.type == "MESH")
P = arm.pose.bones

def act_for(key):
    if key in bpy.data.actions:
        return bpy.data.actions[key]
    for a in bpy.data.actions:
        n = a.name.lower()
        if n.startswith(key) or (key == "pistol" and "pistol" in n) or (key == "hit" and n.startswith("hit")):
            return a
    raise KeyError(key)

# ---------- a parent we can turn and scale without touching the glTF transforms ----------
rig = bpy.data.objects.new("Rig", None); sc.collection.objects.link(rig)
arm.parent = rig
arm_base_loc = arm.location.copy()
def hips_world():
    return arm.matrix_world @ P["mixamorig:Hips"].head

arm.animation_data.action = act_for("idle")
sc.frame_set(0)
bpy.context.view_layer.update()
zs = [(body.matrix_world @ v.co).z for v in body.data.vertices]
scale = HEIGHT_M / (max(zs) - min(zs))
rig.scale = (scale, scale, scale)
print("model height", round(max(zs) - min(zs), 3), "-> scale", round(scale, 3))

# ---------- materials: painted texture x toon bands + ink outline ----------
def toon_from(mat):
    nt = mat.node_tree
    tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE" and "basecolor" in (n.image.name if n.image else "").lower()), None)
    tex = tex or next((n for n in nt.nodes if n.type == "TEX_IMAGE"), None)
    keep = tex.name
    for n in list(nt.nodes):
        if n.name != keep:
            nt.nodes.remove(n)
    tex = nt.nodes[keep]
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    dot = nt.nodes.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = Vector((-0.55, -0.55, 0.63)).normalized()     # key light: top-left-front
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.interpolation = "CONSTANT"
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.0, (0.55, 0.55, 0.6, 1)       # shadow, slightly cool
    e[1].position, e[1].color = 0.45, (1.08, 1.06, 1.0, 1)      # lit, slightly warm
    mid = e.new(0.12); mid.color = (0.8, 0.8, 0.82, 1)
    mul = nt.nodes.new("ShaderNodeVectorMath"); mul.operation = "MULTIPLY"     # texture x toon band
    emi = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(geo.outputs["Normal"], dot.inputs[0])
    nt.links.new(dot.outputs["Value"], ramp.inputs["Fac"])
    hsv = nt.nodes.new("ShaderNodeHueSaturation")                              # mute towards the Silo 81 palette
    hsv.inputs["Saturation"].default_value = 0.78
    nt.links.new(tex.outputs["Color"], hsv.inputs["Color"])
    nt.links.new(hsv.outputs["Color"], mul.inputs[0])
    nt.links.new(ramp.outputs["Color"], mul.inputs[1])
    nt.links.new(mul.outputs["Vector"], emi.inputs["Color"])
    nt.links.new(emi.outputs["Emission"], out.inputs["Surface"])

for slot in body.material_slots:
    toon_from(slot.material)
ink = bpy.data.materials.new("Ink"); ink.use_nodes = True
nt = ink.node_tree; nt.nodes.clear()
o = nt.nodes.new("ShaderNodeOutputMaterial"); g = nt.nodes.new("ShaderNodeNewGeometry")
em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (0.035, 0.03, 0.025, 1)
tr = nt.nodes.new("ShaderNodeBsdfTransparent"); mx = nt.nodes.new("ShaderNodeMixShader")
nt.links.new(g.outputs["Backfacing"], mx.inputs["Fac"]); nt.links.new(em.outputs["Emission"], mx.inputs[1])
nt.links.new(tr.outputs["BSDF"], mx.inputs[2]); nt.links.new(mx.outputs["Shader"], o.inputs["Surface"])
body.data.materials.append(ink)
sol = body.modifiers.new("Outline", "SOLIDIFY")
sol.thickness = -0.011 / scale; sol.use_flip_normals = True; sol.use_rim = False
sol.material_offset = len(body.material_slots) - 1

# ---------- camera ----------
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam)
cam.data.type = "ORTHO"
cam.rotation_euler = (math.radians(90) - ELEV, 0, 0)
FOCUS_Z = 0.85
cam.location = Vector((0, -30 * math.cos(ELEV), FOCUS_Z + 30 * math.sin(ELEV)))
sc.camera = cam
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = False
sc.cycles.max_bounces = 0; sc.cycles.transparent_max_bounces = 8
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"
if sc.world is None:
    sc.world = bpy.data.worlds.new("W")

def screen_xy(p, canvas):
    uv = world_to_camera_view(sc, cam, p)
    return uv.x * canvas, (1 - uv.y) * canvas

def pose_vec():
    h = P["mixamorig:Hips"].head
    return [(b.head - h) for b in P]


# ---------- pistol prop: a simple Tokarev-like gun locked to the right hand ----------
GUN_ANIMS = {"pistol_attack", "pistol_idle", "pistol_shoot", "pistol_aim"}
gun = None
def toon_flat(name, rgb):
    m = bpy.data.materials.new(name); m.use_nodes = True
    t = m.node_tree; t.nodes.clear()
    out = t.nodes.new("ShaderNodeOutputMaterial"); geo = t.nodes.new("ShaderNodeNewGeometry")
    dot = t.nodes.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = Vector((-0.55, -0.55, 0.63)).normalized()
    ramp = t.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.interpolation = "CONSTANT"
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.0, (*[c * 0.55 for c in rgb], 1)
    e[1].position, e[1].color = 0.45, (*[min(1, c * 1.15) for c in rgb], 1)
    mid = e.new(0.12); mid.color = (*[c * 0.8 for c in rgb], 1)
    em = t.nodes.new("ShaderNodeEmission")
    t.links.new(geo.outputs["Normal"], dot.inputs[0]); t.links.new(dot.outputs["Value"], ramp.inputs["Fac"])
    t.links.new(ramp.outputs["Color"], em.inputs["Color"]); t.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m

def add_box(bm, x0, x1, y0, y1, z0, z1, mat_index, tilt=0.0):
    verts = []
    for x in (x0, x1):
        for y in (y0, y1):
            for z in (z0, z1):
                xx = x + (z - z1) * tilt          # lean the grip backwards
                verts.append(bm.verts.new((xx, y, z)))
    idx = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    for f in idx:
        face = bm.faces.new([verts[i] for i in f]); face.material_index = mat_index

if any(k in GUN_ANIMS for k in ANIMS) and "pistol_aim" in bpy.data.actions:
    arm.animation_data.action = act_for("pistol_aim"); rig.rotation_euler = (0, 0, 0); arm.location = arm_base_loc
    sc.frame_set(0); bpy.context.view_layer.update()
    W = arm.matrix_world
    wrist = W @ P["mixamorig:RightHand"].head
    knuck = W @ P["mixamorig:RightHandMiddle1"].head
    shoulder = W @ P["mixamorig:RightArm"].head
    palm = wrist.lerp(knuck, 0.55)
    aim = (knuck - shoulder).normalized()
    up = Vector((0, 0, 1)); side = up.cross(aim).normalized(); up = aim.cross(side).normalized()
    basis = Matrix((aim, side, up)).transposed().to_4x4()
    me = bpy.data.meshes.new("Pistol"); bm = bmesh.new()
    add_box(bm, -0.035, 0.155, -0.014, 0.014, 0.022, 0.058, 0)            # slide and barrel
    add_box(bm, -0.030, 0.012, -0.013, 0.013, -0.075, 0.024, 1, tilt=0.28)  # grip
    add_box(bm, 0.010, 0.040, -0.004, 0.004, -0.012, 0.022, 0)             # trigger guard
    bm.to_mesh(me); bm.free()
    gun = bpy.data.objects.new("Pistol", me); sc.collection.objects.link(gun)
    me.materials.append(toon_flat("Steel", (0.05, 0.05, 0.055)))
    me.materials.append(toon_flat("GripWood", (0.12, 0.065, 0.03)))
    me.materials.append(ink)
    gsol = gun.modifiers.new("Outline", "SOLIDIFY")
    gsol.thickness = -0.006; gsol.use_flip_normals = True; gsol.use_rim = False; gsol.material_offset = 2
    gun.parent = arm; gun.parent_type = "BONE"; gun.parent_bone = "mixamorig:RightHand"
    bpy.context.view_layer.update()
    gun.matrix_world = Matrix.Translation(palm) @ basis
    print("pistol prop attached to mixamorig:RightHand")

def render_clips():
    summary = {"pixels_per_metre": PPM, "camera_elevation_deg": 30, "height_m": HEIGHT_M, "animations": {}}
    for key, cfg in ANIMS.items():
        if ONLY and key not in ONLY:
            continue
        act = act_for(key)
        arm.animation_data.action = act
        if gun is not None:
            gun.hide_render = key not in GUN_ANIMS
        f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
        rig.rotation_euler = (0, 0, 0); arm.location = arm_base_loc
        if cfg.get("find_loop"):                                  # pick the cleanest loop point
            lo, hi = cfg["find_loop"]
            sc.frame_set(f0); ref = pose_vec()
            best = None
            for f in range(f0 + lo, min(f1, f0 + hi) + 1):
                sc.frame_set(f)
                d = sum((a - b).length for a, b in zip(pose_vec(), ref))
                if best is None or d < best[0]:
                    best = (d, f)
            f1 = best[1]
            print(key, "loop point", f1, "pose error", round(best[0], 4))
        n_src = f1 - f0                     # loops: last frame == first frame, so it is not rendered
        step_src = 24 / cfg["fps"]
        n_out = int(round(n_src / step_src)) if cfg["loop"] else int(n_src // step_src) + 1
        if os.environ.get("QUICK"):
            n_out = int(os.environ["QUICK"])
        # forward root motion (in the rig's own, unscaled space)
        sc.frame_set(f0); a = hips_world(); sc.frame_set(f1); b = hips_world()
        D = (b - a) / scale if cfg["inplace"] else Vector((0, 0, 0))
        D.z = 0
        A0 = Vector((a.x, a.y, 0)) / scale if cfg["inplace"] else Vector((0, 0, 0))   # clip may not start at the origin
        fwd = Vector((D.x, D.y, 0)).normalized() if D.length > 1e-6 else Vector((0, -1, 0))
        face_angle = math.degrees(math.atan2(fwd.y, fwd.x))       # -90 = facing -Y
        canvas = cfg["canvas"]
        sc.render.resolution_x = sc.render.resolution_y = canvas
        cam.data.ortho_scale = canvas / PPM
        out_dir = os.path.join(OUT, key); os.makedirs(out_dir, exist_ok=True)
        meta = {"fps": cfg["fps"], "frames": n_out, "loop": cfg["loop"], "canvas": canvas,
                "anchor_px": None, "directions": {}}
        for d in range(6):
            ang = 60 * d                                               # 0 = screen right, counter-clockwise
            rig.rotation_euler = (0, 0, math.radians(ang - (-90)))     # source faces -Y
            track = []
            for i in range(n_out + (1 if cfg["inplace"] else 0)):
                f = f0 + i * step_src
                sc.frame_set(int(f), subframe=f - int(f))
                t = (f - f0) / n_src
                arm.location = arm_base_loc - A0 - D * t               # centre it and strip the average forward motion
                bpy.context.view_layer.update()
                if i < n_out:
                    sc.render.filepath = os.path.join(out_dir, f"dir{d}_{i:03d}.png")
                    bpy.ops.render.render(write_still=True)
                if cfg["inplace"]:
                    toes = [arm.matrix_world @ P[n].head for n in ("mixamorig:LeftToeBase", "mixamorig:RightToeBase")]
                    k = min(range(2), key=lambda j: toes[j].z)
                    track.append((k, toes[k].z, screen_xy(toes[k], canvas)))
            if meta["anchor_px"] is None:
                meta["anchor_px"] = [round(v, 1) for v in screen_xy(Vector((0, 0, 0)), canvas)]
            dist = D.length * scale / n_src * step_src               # metres per sprite frame
            step = (dist * math.cos(math.radians(ang)) * PPM, -dist * math.sin(math.radians(ang)) * math.sin(ELEV) * PPM)
            entry = {"angle_deg": ang, "step_px": [round(step[0], 3), round(step[1], 3)]}
            if cfg["inplace"]:
                zmin = min(z for _, z, _ in track)
                res = []
                for i in range(len(track) - 1):
                    (k1, z1, p1), (k2, z2, p2) = track[i], track[i + 1]
                    if k1 == k2 and z1 < zmin + 0.02 and z2 < zmin + 0.02:
                        res.append(math.hypot(p2[0] + step[0] - p1[0], p2[1] + step[1] - p1[1]))
                entry["planted_toe_drift_px_per_frame"] = round(sum(res) / len(res), 3) if res else None
                entry["contact_frames_checked"] = len(res)
            meta["directions"][str(d)] = entry
            print(key, "dir", d, entry)
        summary["animations"][key] = meta
        rig.rotation_euler = (0, 0, 0); arm.location = arm_base_loc

    prev = {}
    p = os.path.join(OUT, "steps.json")
    if os.path.exists(p):
        prev = json.load(open(p))
    prev.update({k: v for k, v in summary.items() if k != "animations"})
    prev.setdefault("animations", {}).update(summary["animations"])
    json.dump(prev, open(p, "w"), indent=2)


if __name__ == "__main__":
    render_clips()
