"""Build one Silo 81 level in Blender and render it for Godot.

Outputs (in OUT/LEVEL):
  bg.png                     floor, walls, stairs, pipes and everything fixed to a back wall or the floor
  spr_*.png                  free-standing props, doors (open/closed) and pipe states, one image per variant
  level.json                 rooms, walls, doors, props, interactables and spawns, plus sprite placement
Screen space (Godot pixels): sx = x * PPM, sy = -(y * 0.5 + z * 0.866) * PPM, ground origin at (0, 0).

Usage: python3 -I build.py L2|L3 out_dir [--quick]
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector, Matrix
import kit
from kit import Builder, toon, flat, text_obj, g, place, footprint, FACING

LEVEL, OUT = sys.argv[1], sys.argv[2]
QUICK = "--quick" in sys.argv
PPM = 165.0
SIN, COS = 0.5, math.sqrt(3) / 2
T = 0.25                     # wall thickness
FULL, STUB = 2.7, 0.4        # back walls stand full height; the rest are cut away like a dollhouse
FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
MARKER = os.path.join(FONTS, "PermanentMarker-Regular.ttf")
STENCIL = os.path.join(FONTS, "AllertaStencil-Regular.ttf")
OSWALD = os.path.join(FONTS, "Oswald-VF.ttf")
DIR = os.path.join(OUT, LEVEL); os.makedirs(DIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
ROT45 = Matrix.Rotation(math.radians(45), 4, "Z")      # plan (u, v) -> ground (x, y)


def scr(x, y, z=0.0):
    return (x * PPM, -(y * SIN + z * COS) * PPM)


def scr_uv(u, v, z=0.0):
    x, y = g(u, v)
    return scr(x, y, z)


# ============================================================ level definitions
def L2():
    D = {"name": "Level 2 - Dormitories", "rooms": [], "walls": [], "doors": [], "props": [], "decor": [],
         "inspect": [], "stairs": [], "spawns": {}, "blocked": []}
    concrete = dict(rgb=(0.5, 0.49, 0.45), noise=0.18, noise_scale=3.0)
    D["rooms"] += [
        dict(id="landing", r=[-4.2, 0.0, -1.4, 1.4], floor=concrete),
        dict(id="corridor", r=[0.0, 22.6, -1.4, 1.4], floor=dict(concrete, frost=(15.0, 22.0))),
        dict(id="room_2_1", name="Your room", r=[0.6, 4.6, 1.4, 5.6], floor=dict(rgb=(0.44, 0.36, 0.28), noise=0.15, noise_scale=8)),
        dict(id="dorm_2a", name="Dormitory 2-A", r=[4.6, 11.6, 1.4, 5.6], floor=concrete),
        dict(id="dorm_2b", name="Dormitory 2-B", r=[11.6, 18.6, 1.4, 5.6], floor=dict(concrete, frost=(16.0, 21.0))),
        dict(id="room_2_d", name="Room 2-D", r=[18.6, 22.6, 1.4, 5.6], floor=dict(concrete, frost=(18.0, 20.0)), dark=True),
        dict(id="washroom", name="Washroom", r=[1.0, 7.0, -5.0, -1.4], floor=dict(rgb=(0.62, 0.66, 0.62), noise=0.08, noise_scale=20, grating=((0.48, 0.52, 0.49), 0.3))),
        dict(id="dorm_2c", name="Dormitory 2-C", r=[7.0, 14.0, -5.0, -1.4], floor=concrete),
        dict(id="linen", name="Linen store", r=[14.0, 18.6, -5.0, -1.4], floor=dict(concrete, frost=(17.0, 22.0))),
    ]
    D["holes"] = [[-4.0, -0.8, 0.0, 1.4]]          # stairwell going down
    W = D["walls"]
    W += [
        dict(a=(-4.2, 1.4), b=(0.6, 1.4), h=STUB),
        dict(a=(0.6, 5.6), b=(22.6, 5.6), h=FULL, face="-v"),
        dict(a=(22.6, 1.4), b=(22.6, 5.6), h=FULL, face="-u"),
        dict(a=(22.6, -1.4), b=(22.6, 1.4), h=FULL, face="-u"),
        dict(a=(18.6, -5.0), b=(18.6, -1.4), h=STUB),
        dict(a=(-4.2, -1.4), b=(-4.2, 1.4), h=STUB),
        dict(a=(-4.2, -1.4), b=(1.0, -1.4), h=STUB),
        dict(a=(0.6, 1.4), b=(22.6, 1.4), h=STUB, openings=[(2.1, 3.1, "door_2_1"), (7.4, 8.8, None), (14.4, 15.8, None), (20.1, 21.1, "door_2_d")]),
        dict(a=(0.6, 1.4), b=(0.6, 5.6), h=STUB),
        dict(a=(4.6, 1.4), b=(4.6, 5.6), h=STUB),
        dict(a=(11.6, 1.4), b=(11.6, 5.6), h=STUB),
        dict(a=(18.6, 1.4), b=(18.6, 5.6), h=STUB),
        dict(a=(1.0, -1.4), b=(22.6, -1.4), h=STUB, openings=[(3.4, 4.8, None), (9.8, 11.2, None), (15.6, 17.0, None)]),
        dict(a=(1.0, -5.0), b=(1.0, -1.4), h=STUB),
        dict(a=(7.0, -5.0), b=(7.0, -1.4), h=STUB),
        dict(a=(14.0, -5.0), b=(14.0, -1.4), h=STUB),
        dict(a=(1.0, -5.0), b=(18.6, -5.0), h=STUB),
    ]
    D["doors"] += [
        dict(id="door_2_1", kind="plywood", u=2.6, v=1.4, axis="u", open=True, locked=False, name="Door to your room",
             text="Plywood on a steel frame. Your door; it has not locked properly in years."),
        dict(id="door_2_d", kind="steel", u=20.6, v=1.4, axis="u", open=False, locked=True, lock=45, strength=6,
             name="Room 2-D", text="A steel door at the cold end of the corridor. Security's padlock is through the hasp. Nobody has lived here for years."),
    ]
    WI = 5.6 - T / 2           # inner face of the north back wall
    P = D["props"]
    P += [
        dict(t="bed", u=1.9, v=WI, f="-v", k=1, id="bed_player", name="Your bunk", text="Your bed. The blanket is your mother's, older than you."),
        dict(t="locker", u=4.0, v=WI, f="-v", w=1.0, name="Your locker", text="Spare overalls, a dead torch, a photo of Mira's graduation from apprentice."),
        dict(t="desk", u=4.6 - T / 2, v=3.4, f="-u", name="Your desk", text="Work orders. Most are about the general circuit, and most are marked DEFERRED by the Council."),
        dict(t="chair", u=3.75, v=3.4, f="+u"),
        dict(t="toolbox", u=0.6 + T / 2, v=2.8, f="+u", id="toolbox", name="Your toolbox",
             text="Your toolbox. The welding kit is inside: torch, two small bottles, a handful of rods."),
    ]
    for i, u in enumerate((5.75, 8.1, 10.45)):
        P.append(dict(t="bunk", u=u, v=WI, f="-v", k=i, name="Bunk", text="Shared in shifts. Names are painted on the frame; two have been crossed out."))
    for u in (6.92, 9.27):
        for j, v in enumerate((5.1, 4.45, 3.8)):
            P.append(dict(t="curtain", u=u, v=v, f="-u", k=int(u) + j, name="Blanket partition", text="Blankets pinned to a wire: the only walls a family gets in here."))
    P += [
        dict(t="table", u=8.1, v=2.0, f="+v", L=1.2),
        dict(t="stool", u=7.6, v=3.05, f="-v"), dict(t="stool", u=8.6, v=3.05, f="-v"),
        dict(t="locker", u=4.6 + T / 2, v=2.3, f="+u", w=0.55), dict(t="locker", u=4.6 + T / 2, v=2.9, f="+u", w=0.55),
    ]
    for i, u in enumerate((12.75, 15.1, 17.45)):
        P.append(dict(t="bunk", u=u, v=WI, f="-v", k=i + 2, name="Bunk", text="The mattress is damp. Frost has got as far as the wall behind it."))
    for u in (13.92, 16.27):
        for j, v in enumerate((5.1, 4.45, 3.8)):
            P.append(dict(t="curtain", u=u, v=v, f="-u", k=int(u) + j + 1, name="Blanket partition", text="Blankets pinned to a wire."))
    P += [dict(t="bucket", u=15.1, v=3.0, f="-v", name="Bucket", text="Catching a drip from the ceiling. The water has a skin of ice.")]
    P += [
        dict(t="bunk", u=20.0, v=WI, f="-v", k=0, stripped=True, name="Bare bunk", text="Stripped to the springs. Someone took the mattress, and they took it a long time ago."),
        dict(t="chair", u=21.1, v=3.2, f="-v", overturned=True),
        dict(t="locker", u=22.6 - T / 2, v=4.75, f="-u", w=0.55, open=True, name="Open locker", text="Empty. The door hangs open."),
        dict(t="crate", u=19.4, v=2.2, f="+v", name="Crate", text="Nailed shut."),
    ]
    WS = -1.4 - T / 2          # south face of the corridor wall
    P += [
        dict(t="sinks", u=2.3, v=WS, f="-v", n=3, name="Washbasins", text="Cold water only, except on bath day."),
        dict(t="bucket", u=1.5, v=-4.4, f="+v"),
    ]
    for v in (-2.2, -3.1, -4.0):
        P.append(dict(t="stall", u=7.0 - T / 2, v=v, f="-u", name="Toilet stall", text="Fixtures from the closed washrooms on Level 1, refitted here."))
    for i, u in enumerate((8.4, 12.6)):
        P.append(dict(t="bunk", u=u, v=WS, f="-v", k=i + 3, name="Bunk", text="Shared in shifts."))
    for i, u in enumerate((8.4, 11.0)):
        P.append(dict(t="bunk", u=u, v=-5.0 + T / 2, f="+v", k=i + 1, name="Bunk", text="Shared in shifts."))
    P += [
        dict(t="table", u=12.2, v=-3.6, f="-v", L=1.0), dict(t="stool", u=11.7, v=-2.9, f="+v"),
        dict(t="crate", u=14.5, v=-4.6, f="+v"), dict(t="crate", u=15.2, v=-4.6, f="+v"),
        dict(t="laundry", u=15.8, v=-2.6, f="-v", k=1, name="Washing line", text="Blankets drying. They will not dry down here."),
        dict(t="laundry", u=16.0, v=-3.8, f="-v", k=3, name="Washing line", text="Blankets drying."),
    ]
    for v in (-2.2, -3.35, -4.3):
        P.append(dict(t="shelf", u=18.6 - T / 2, v=v, f="-u", name="Linen shelves", text="Folded blankets, counted and signed for."))
    # wall-mounted and floor decor (rendered into the background)
    E = 22.6 - T / 2           # end wall face
    D["decor"] += [
        dict(t="radiator", u=3.2, v=WI, f="-v", sections=8, state="working"),
        dict(t="radiator", u=E, v=-0.75, f="-u", sections=10, state="frozen"),
        dict(t="radiator", u=22.6 - T / 2, v=2.6, f="-u", sections=8, state="frozen"),
        dict(t="poster", u=E, v=0.45, f="-u", z=1.0),
        dict(t="graffiti", u=E, v=0.3, f="-u", z=1.55, text="HEAT IS RANK", size=0.3, rot=-5, rgb=(0.6, 0.07, 0.05), arrow=True),
        dict(t="chalk_sun", u=E, v=-0.1, f="-u", z=0.55),
        dict(t="cd_sign", u=E, v=-1.0, f="-u", z=1.9),
        dict(t="stencil", u=E, v=0.0, f="-u", z=2.45, text="LEVEL 2 - DORMITORIES", size=0.13),
        dict(t="floortext", u=-2.0, v=-0.6, text="STAIRS L3"),
        dict(t="intercom", u=1.0, v=WI, f="-v", z=1.45),
        dict(t="drawing", u=21.75, v=WI, f="-v", z=1.25),
        dict(t="mould", u=18.3, v=WI, f="-v"),
        dict(t="rug", u=2.5, v=3.3),
        dict(t="floorline", u0=0.0, u1=22.4, v=-0.95),
        dict(t="floortext", u=2.6, v=0.75, text="2-1"), dict(t="floortext", u=8.1, v=0.75, text="2-A"),
        dict(t="floortext", u=15.1, v=0.75, text="2-B"), dict(t="floortext", u=20.6, v=0.75, text="2-D"),
        dict(t="floortext", u=4.1, v=-0.75, text="WC"), dict(t="floortext", u=10.5, v=-0.75, text="2-C"),
        dict(t="floortext", u=16.3, v=-0.75, text="LINEN"),
        dict(t="stairs_down", u0=-4.0, u1=-0.8, v0=0.0, v1=1.4),
    ]
    D["inspect"] += [
        dict(id="graffiti", u=22.2, v=0.3, name="Graffiti",
             text="HEAT IS RANK, sprayed over the old WARMTH FOR ALL poster, with an arrow pointing down towards the warm levels. A child's handwriting, or someone who wanted it to look like one."),
        dict(id="radiator_end", u=22.1, v=-0.75, name="Radiator", text="Dead. Frost in the fins. The far end of the branch never gets enough flow, so the water barely moves out here."),
        dict(id="radiator_own", u=3.2, v=5.1, name="Radiator", text="Your radiator. Warm, mostly: your room is near the start of the branch."),
        dict(id="cd_sign", u=22.2, v=-1.0, name="Civil defence sign", text="Blue triangle on orange: civil defence. Painted when the silo was new."),
        dict(id="intercom", u=1.0, v=5.2, name="Intercom", text="The line to Engineering. It still smells of Mira's solder."),
        dict(id="drawing", u=21.75, v=5.2, name="Drawing", text="A child's drawing of a sky: blue, with a yellow sun. Nobody in Silo 81 has seen one.", room="room_2_d"),
    ]
    D["stairs"] += [dict(id="stairs_down", u=-0.45, v=0.7, to="L3", arrive=[-0.3, -0.2], name="Stairs down",
                         text="The stairwell down to Level 3, life support.")]
    D["spawns"] = {"player": [2.3, 3.5, 5], "worms": []}
    D["bounds"] = [-4.2, 22.6, -5.0, 5.6]
    return D


def L3():
    D = {"name": "Level 3 - Pipe gallery", "rooms": [], "walls": [], "doors": [], "props": [], "decor": [],
         "inspect": [], "stairs": [], "spawns": {}, "blocked": []}
    raw = dict(rgb=(0.47, 0.46, 0.43), noise=0.2, noise_scale=3.0)
    D["rooms"] += [
        dict(id="landing", r=[-4.2, 0.0, -1.6, 1.8], floor=raw),
        dict(id="gallery", name="Pipe gallery", r=[0.0, 18.0, -1.6, 1.8], floor=dict(rgb=(0.2, 0.21, 0.2), noise=0.1, noise_scale=6, grating=((0.42, 0.43, 0.41), 0.35))),
        dict(id="pumps", name="Pump room 3-P", r=[9.0, 18.0, -6.0, -1.6], floor=dict(raw, rgb=(0.45, 0.44, 0.41))),
    ]
    D["holes"] = []
    D["blocked"] += [[-4.2, -0.75, 0.35, 1.8]]       # the stair flight
    W = D["walls"]
    W += [
        dict(a=(-4.2, 1.8), b=(18.0, 1.8), h=FULL, face="-v", mat="raw"),
        dict(a=(18.0, -6.0), b=(18.0, 1.8), h=FULL, face="-u", mat="raw"),
        dict(a=(-4.2, -1.6), b=(-4.2, 1.8), h=STUB, mat="raw"),
        dict(a=(-4.2, -1.6), b=(18.0, -1.6), h=STUB, mat="raw", openings=[(12.4, 13.8, None)]),
        dict(a=(9.0, -6.0), b=(9.0, -1.6), h=STUB, mat="raw"),
        dict(a=(9.0, -6.0), b=(18.0, -6.0), h=STUB, mat="raw"),
    ]
    WI = 1.8 - T / 2
    D["decor"] += [
        dict(t="pipes", u0=-0.6, u1=18.0 - T / 2, v=WI, gap=(8.1, 9.3)),
        dict(t="stairs_up", u0=-4.0, u1=-0.8, v0=0.4, v1=1.8),
        dict(t="stencil", u=1.8, v=WI, f="-v", z=2.35, text="LEVEL 3 - LIFE SUPPORT", size=0.15),
        dict(t="stencil", u=18.0 - T / 2, v=-3.6, f="-u", z=2.3, text="PUMP ROOM 3-P", size=0.15),
        dict(t="manifold", u=18.0 - T / 2, v=-2.6, f="-u"),
        dict(t="puddle", u=8.7, v=0.6, r=0.9), dict(t="puddle", u=7.6, v=0.1, r=0.5),
        dict(t="drain", u0=0.0, u1=18.0, v=-1.2),
        dict(t="cd_sign", u=18.0 - T / 2, v=0.8, f="-u", z=1.9),
        dict(t="mould", u=4.0, v=WI, f="-v"),
    ]
    P = D["props"]
    P += [
        dict(t="pump", u=12.0, v=-4.6, f="-u", name="Circulation pump", text="Circulation pump for the general circuit, running hard against the leak."),
        dict(t="pump", u=15.6, v=-4.6, f="-u", name="Circulation pump", text="The standby pump. Its bearings were replaced with parts from Level 1."),
        dict(t="workbench", u=18.0 - T / 2, v=-4.9, f="-u", name="Workbench", text="Somebody's half-finished repair: a flange, filed by hand."),
        dict(t="crate", u=9.6, v=-5.5, f="+v"), dict(t="crate", u=10.3, v=-5.5, f="+v"),
        dict(t="crate", u=16.9, v=-2.2, f="-u"),
    ]
    D["blocked"] += [[-0.6, 18.0, 1.25, 1.8]]        # pipes stand off the north wall
    D["pipe"] = dict(id="pipe_break", u=8.7, v=WI, name="Burst pipe",
                     text="The heating flow for the general circuit, chewed through. Hot water sprays from the hole and the pressure is falling. It needs welding.",
                     fixed_text="Welded. The bead is ugly but it holds, and the gauge needle is climbing back.")
    D["inspect"] += [
        dict(id="pipes_label", u=4.5, v=1.2, name="Pipes", text="Top to bottom: bore water; heating flow, general circuit, to Level 2; heating return."),
        dict(id="gauge", u=14.0, v=1.2, name="Gauge", text="Pressure on the general circuit, falling."),
        dict(id="manifold", u=17.6, v=-2.6, name="Valve manifold", text="Valve wheels tagged in three different handwritings. The newest tag says COUNCIL ORDER: DO NOT OPEN."),
    ]
    D["stairs"] += [dict(id="stairs_up", u=-0.45, v=1.0, to="L2", arrive=[-0.3, 0.0], name="Stairs up",
                         text="Back up to Level 2.")]
    D["spawns"] = {"player": [-0.3, 0.0, 0], "worms": [[7.9, 0.75, 2], [9.4, 0.8, 2], [12.6, 0.85, 2]]}
    D["bounds"] = [-4.2, 18.0, -6.0, 1.8]
    return D


LV = {"L2": L2, "L3": L3}[LEVEL]()

# ============================================================ background geometry
bg_objects = []


def plan_obj(b, outline=0.012):
    ob = b.finish(outline=outline)
    ob.matrix_world = ROT45 @ ob.matrix_world
    bg_objects.append(ob)
    return ob


def floor_mat(spec, rid):
    return toon(f"Floor_{LEVEL}_{rid}", spec["rgb"], noise=spec.get("noise", 0.1), noise_scale=spec.get("noise_scale", 4),
                frost=(spec["frost"][0], spec["frost"][1], (0.78, 0.84, 0.88)) if spec.get("frost") else None,
                grating=spec.get("grating"), lit=1.0)


def rect_minus(r, holes):
    """Split a plan rectangle around holes (holes assumed to touch the rectangle edges or sit inside)."""
    parts = [r]
    for h in holes:
        new = []
        for p in parts:
            u0, u1, v0, v1 = p
            hu0, hu1, hv0, hv1 = max(u0, h[0]), min(u1, h[1]), max(v0, h[2]), min(v1, h[3])
            if hu0 >= hu1 or hv0 >= hv1:
                new.append(p); continue
            if u0 < hu0: new.append([u0, hu0, v0, v1])
            if hu1 < u1: new.append([hu1, u1, v0, v1])
            if v0 < hv0: new.append([hu0, hu1, v0, hv0])
            if hv1 < v1: new.append([hu0, hu1, hv1, v1])
        parts = new
    return parts


for room in LV["rooms"]:
    b = Builder("Floor_" + room["id"])
    m = floor_mat(room["floor"], room["id"])
    for p in rect_minus(room["r"], LV.get("holes", [])):
        b.box(p[0], p[1], p[2], p[3], -0.08, 0.0, m)
    plan_obj(b, outline=0)

# thresholds under door openings
for w in LV["walls"]:
    for (t0, t1, _) in w.get("openings", []):
        b = Builder("Threshold")
        m = toon(f"Threshold_{LEVEL}", (0.42, 0.41, 0.38), noise=0.1)
        (ua, va), (ub, vb) = w["a"], w["b"]
        if va == vb:
            b.box(t0, t1, va - T / 2, va + T / 2, -0.08, 0.005, m)
        else:
            b.box(ua - T / 2, ua + T / 2, t0, t1, -0.08, 0.005, m)
        plan_obj(b, outline=0)


def wall_material(w):
    if w.get("mat") == "raw":
        return toon(f"WallRaw_{LEVEL}", (0.56, 0.55, 0.51), noise=0.22, noise_scale=2.5,
                    frost=None)
    frost = (16.5, 23.0, (0.8, 0.86, 0.9), 1.1) if LEVEL == "L2" else None
    return toon(f"WallDado_{LEVEL}", (0.76, 0.74, 0.67), noise=0.12, noise_scale=3.0,
                dado=((0.38, 0.47, 0.42), 1.25), frost=frost)


CUT = toon("WallCut", (0.2, 0.2, 0.19))
for w in LV["walls"]:
    (ua, va), (ub, vb) = w["a"], w["b"]
    along_u = va == vb
    lo, hi = (min(ua, ub), max(ua, ub)) if along_u else (min(va, vb), max(va, vb))
    ops = sorted(w.get("openings", []))
    segs, cur = [], lo - T / 2
    for (t0, t1, _) in ops:
        segs.append((cur, t0)); cur = t1
    segs.append((cur, hi + T / 2))
    b = Builder("Wall")
    m = wall_material(w)
    z0 = -2.75 if w.get("shaft") else 0.0
    for (s0, s1) in segs:
        if s1 - s0 < 0.01:
            continue
        if along_u:
            b.box(s0, s1, va - T / 2, va + T / 2, z0, w["h"], m, top_mat=CUT if w["h"] < FULL else None)
        else:
            b.box(ua - T / 2, ua + T / 2, s0, s1, z0, w["h"], m, top_mat=CUT if w["h"] < FULL else None)
    if w["h"] >= FULL:
        for (t0, t1, _) in ops:                     # lintels over openings in full walls
            if along_u:
                b.box(t0, t1, va - T / 2, va + T / 2, 2.1, w["h"], m)
            else:
                b.box(ua - T / 2, ua + T / 2, t0, t1, 2.1, w["h"], m)
    plan_obj(b, outline=0.012)


# ---------- decor builders (background) ----------
def wall_frame(u, v, facing, z):
    """Matrix for flat things on a wall face: local x along the wall, z up, -y into the wall."""
    x, y = g(u, v)
    ang = kit.facing_frame(facing)
    return Matrix.Translation((x, y, z)) @ Matrix.Rotation(ang, 4, "Z")


def add_text_on_wall(text, font, size, mat, u, v, facing, z, rot=0.0, dy=0.006, align="CENTER"):
    ob = text_obj(text, font, size, mat, align=align)
    # text lies in XY facing +Z; stand it up so it faces the prop front (+y local)
    ob.matrix_world = wall_frame(u, v, facing, z) @ Matrix.Translation((0, dy, 0)) @ \
        Matrix.Rotation(math.pi, 4, "Z") @ Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Rotation(math.radians(rot), 4, "Z")
    bg_objects.append(ob)
    return ob


def add_on_wall(builder_fn, u, v, facing, z=0.0):
    ob = builder_fn
    ob.matrix_world = wall_frame(u, v, facing, z) @ ob.matrix_world
    bg_objects.append(ob)
    return ob


def decor(d):
    t = d["t"]
    if t == "radiator":
        ob, _ = kit.radiator("Radiator", d["sections"], d["state"])
        add_on_wall(ob, d["u"], d["v"], d["f"])
    elif t == "poster":
        b = Builder("Poster")
        paper = toon("PosterPaper", (0.8, 0.74, 0.58), noise=0.12, noise_scale=10)
        red = toon("PosterRed", (0.62, 0.16, 0.1))
        orange = toon("PosterOrange", (0.86, 0.5, 0.16))
        b.box(-0.42, 0.42, 0.0, 0.006, 0.0, 1.1, paper)
        b.box(-0.42, 0.42, 0.006, 0.008, 0.88, 1.1, red)
        b.cyl((0.0, 0.007, 0.6), (0.0, 0.01, 0.6), 0.14, orange, seg=20)
        for i in range(5):                          # radiator fins under the sun
            x = -0.2 + i * 0.1
            b.box(x - 0.03, x + 0.03, 0.007, 0.01, 0.18, 0.4, red)
        ob = b.finish(outline=0)
        add_on_wall(ob, d["u"], d["v"], d["f"], d["z"])
        add_text_on_wall("WARMTH FOR ALL", OSWALD, 0.11, flat("PosterText", (0.92, 0.88, 0.76)), d["u"], d["v"], d["f"], d["z"] + 0.99, dy=0.012)
    elif t == "graffiti":
        mat = flat("Spray", d["rgb"])
        add_text_on_wall(d["text"], MARKER, d["size"], mat, d["u"], d["v"], d["f"], d["z"], rot=d["rot"], dy=0.02)
        if d.get("arrow"):
            b = Builder("Arrow")
            b.box(-0.03, 0.03, 0, 0.004, -0.55, -0.2, mat)
            b.quad([(-0.14, 0.004, -0.5), (0.14, 0.004, -0.5), (0.0, 0.004, -0.72)], mat)
            ob = b.finish(outline=0)
            add_on_wall(ob, d["u"] + 0.0, d["v"] - 0.55, d["f"], d["z"] + 0.0)
    elif t == "chalk_sun":
        mat = flat("Chalk", (0.86, 0.8, 0.45))
        b = Builder("ChalkSun")
        for k in range(24):
            a0, a1 = 2 * math.pi * k / 24, 2 * math.pi * (k + 1) / 24
            b.quad([(0.12 * math.cos(a0), 0.003, 0.12 * math.sin(a0)), (0.12 * math.cos(a1), 0.003, 0.12 * math.sin(a1)),
                    (0.1 * math.cos(a1), 0.003, 0.1 * math.sin(a1)), (0.1 * math.cos(a0), 0.003, 0.1 * math.sin(a0))], mat)
        for k in range(8):
            a = 2 * math.pi * k / 8
            c, s = math.cos(a), math.sin(a)
            b.quad([(0.15 * c - 0.01 * s, 0.003, 0.15 * s + 0.01 * c), (0.24 * c - 0.01 * s, 0.003, 0.24 * s + 0.01 * c),
                    (0.24 * c + 0.01 * s, 0.003, 0.24 * s - 0.01 * c), (0.15 * c + 0.01 * s, 0.003, 0.15 * s - 0.01 * c)], mat)
        for (x0, z0, x1, z1) in ((0.45, -0.25, 0.45, 0.05), (0.45, 0.05, 0.38, -0.08), (0.45, 0.05, 0.52, -0.08),
                                 (0.45, -0.25, 0.4, -0.38), (0.45, -0.25, 0.5, -0.38)):
            dx, dz = x1 - x0, z1 - z0; L = math.hypot(dx, dz); nx, nz = -dz / L * 0.012, dx / L * 0.012
            b.quad([(x0 + nx, 0.003, z0 + nz), (x1 + nx, 0.003, z1 + nz), (x1 - nx, 0.003, z1 - nz), (x0 - nx, 0.003, z0 - nz)], mat)
        b.cyl((0.45, 0.003, 0.11), (0.45, 0.004, 0.11), 0.05, mat, seg=12)
        ob = b.finish(outline=0)
        add_on_wall(ob, d["u"], d["v"], d["f"], d["z"])
    elif t == "cd_sign":
        b = Builder("CDSign")
        b.box(-0.17, 0.17, 0.0, 0.01, -0.17, 0.17, flat("CDOrange", (0.85, 0.42, 0.08)))
        b.quad([(-0.12, 0.012, -0.09), (0.12, 0.012, -0.09), (0.0, 0.012, 0.12)], flat("CDBlue", (0.12, 0.25, 0.6)))
        ob = b.finish(outline=0.006)
        add_on_wall(ob, d["u"], d["v"], d["f"], d["z"])
    elif t == "stencil":
        add_text_on_wall(d["text"], STENCIL, d["size"], flat("StencilPaint", (0.12, 0.12, 0.11)), d["u"], d["v"], d["f"], d["z"])
    elif t == "intercom":
        b = Builder("Intercom")
        b.box(-0.11, 0.11, 0.0, 0.08, -0.16, 0.16, toon("IntercomGrey", (0.45, 0.47, 0.45), noise=0.06))
        for i in range(5):
            b.box(-0.07, 0.07, 0.08, 0.083, 0.02 + i * 0.022, 0.03 + i * 0.022, toon("SinkDark", (0.2, 0.22, 0.22)))
        b.cyl((0.0, 0.08, -0.08), (0.0, 0.1, -0.08), 0.02, toon("ValveRed", (0.5, 0.12, 0.1)), seg=10)
        ob = b.finish(outline=0.006)
        add_on_wall(ob, d["u"], d["v"], d["f"], d["z"])
    elif t == "drawing":
        b = Builder("Drawing")
        b.box(-0.21, 0.21, 0.0, 0.004, -0.15, 0.15, flat("DrawPaper", (0.86, 0.84, 0.76)))
        b.box(-0.19, 0.19, 0.005, 0.007, -0.02, 0.13, flat("DrawSky", (0.36, 0.56, 0.82)))
        b.box(-0.19, 0.19, 0.005, 0.007, -0.13, -0.04, flat("DrawGrass", (0.36, 0.6, 0.26)))
        b.cyl((0.1, 0.008, 0.07), (0.1, 0.009, 0.07), 0.04, flat("DrawSun", (0.95, 0.82, 0.2)), seg=14)
        ob = b.finish(outline=0.004)
        add_on_wall(ob, d["u"], d["v"], d["f"], d["z"])
    elif t == "mould":
        b = Builder("Mould")
        b.box(-0.6, 0.6, 0.0, 0.004, 0.0, 0.9, toon("Mould", (0.18, 0.22, 0.16), alpha_noise=(0.56, 4.5)))
        ob = b.finish(outline=0)
        add_on_wall(ob, d["u"], d["v"], d["f"], 0.02)
    elif t == "rug":
        b = Builder("Rug")
        b.box(d["u"] - 0.9, d["u"] + 0.9, d["v"] - 0.6, d["v"] + 0.6, 0.0, 0.012, toon("Rug", (0.46, 0.2, 0.16), noise=0.15, noise_scale=12))
        b.box(d["u"] - 0.75, d["u"] + 0.75, d["v"] - 0.45, d["v"] + 0.45, 0.012, 0.014, toon("RugInner", (0.62, 0.48, 0.3), noise=0.15, noise_scale=12))
        plan_obj(b, outline=0)
    elif t == "floorline":
        b = Builder("FloorLine")
        b.box(d["u0"], d["u1"], d["v"] - 0.05, d["v"] + 0.05, 0.0, 0.003, toon("FloorPaint", (0.7, 0.58, 0.22), alpha_noise=(0.3, 9)))
        plan_obj(b, outline=0)
    elif t == "floortext":
        ob = text_obj(d["text"], STENCIL, 0.32, flat("FloorStencil", (0.72, 0.68, 0.58), alpha=0.85))
        x, y = g(d["u"], d["v"])
        ob.matrix_world = Matrix.Translation((x, y, 0.004)) @ Matrix.Rotation(math.radians(45), 4, "Z")
        bg_objects.append(ob)
    elif t == "puddle":
        b = Builder("Puddle")
        m = toon("Puddle", (0.12, 0.16, 0.17), alpha_noise=(0.45, 2.2))
        r = d["r"]
        b.box(d["u"] - r, d["u"] + r, d["v"] - r * 0.7, d["v"] + r * 0.7, 0.0, 0.006, m)
        plan_obj(b, outline=0)
    elif t == "drain":
        b = Builder("Drain")
        b.box(d["u0"], d["u1"], d["v"] - 0.18, d["v"] + 0.18, 0.0, 0.004, toon("DrainGrate", (0.12, 0.12, 0.11), grating=((0.36, 0.36, 0.34), 0.12)))
        plan_obj(b, outline=0)
    elif t == "stairs_down":
        b = Builder("StairsDown")
        m = toon(f"Steps_{LEVEL}", (0.5, 0.49, 0.46), noise=0.12)
        blackm = flat("Void", (0.02, 0.02, 0.025))
        side = toon(f"PitWall_{LEVEL}", (0.4, 0.4, 0.38), noise=0.15)
        n, rise, run = 3, 0.18, 0.3
        for i in range(n):
            ua = d["u1"] - run * i; ub = d["u1"] - run * (i + 1)
            b.box(ub, ua, d["v0"] + 0.05, d["v1"] - 0.05, -0.6, -rise * (i + 1), m)
        b.box(d["u0"], d["u1"] - run * n, d["v0"], d["v1"], -0.62, -0.6, blackm)
        b.box(d["u0"], d["u1"], d["v1"] - 0.05, d["v1"], -0.6, 0.0, side)
        rail = toon("Railing", (0.55, 0.42, 0.12), noise=0.05)
        for k in range(5):
            uu = d["u0"] + (d["u1"] - d["u0"]) * k / 4
            b.box(uu - 0.025, uu + 0.025, d["v0"] - 0.025, d["v0"] + 0.025, 0, 1.0, rail)
        b.box(d["u0"], d["u1"], d["v0"] - 0.03, d["v0"] + 0.03, 0.97, 1.03, rail)
        b.box(d["u0"], d["u1"], d["v0"] - 0.015, d["v0"] + 0.015, 0.5, 0.53, rail)
        plan_obj(b, outline=0.01)
    elif t == "stairs_up":
        b = Builder("StairsUp")
        m = toon(f"Steps_{LEVEL}", (0.5, 0.49, 0.46), noise=0.12)
        n = 13
        for i in range(n):
            ua = d["u1"] - (d["u1"] - d["u0"]) * i / n
            ub = d["u1"] - (d["u1"] - d["u0"]) * (i + 1) / n
            b.box(ub, ua, d["v0"] + 0.05, d["v1"] - 0.05, 0.0, 0.2 * (i + 1), m)
        rail = toon("Railing", (0.55, 0.42, 0.12), noise=0.05)
        for k in range(5):
            uu = d["u0"] + (d["u1"] - d["u0"]) * k / 4
            zb = 0.2 * n * (d["u1"] - uu) / (d["u1"] - d["u0"])
            b.box(uu - 0.025, uu + 0.025, d["v0"] + 0.03, d["v0"] + 0.08, zb, zb + 1.0, rail)
        plan_obj(b, outline=0.01)
    elif t == "pipes":
        build_pipes(d)
    elif t == "manifold":
        b = Builder("Manifold")
        steel = toon("PipeSteel", (0.38, 0.38, 0.36), noise=0.08)
        red = toon("ValveRed", (0.5, 0.12, 0.1))
        for i, x in enumerate((-0.6, -0.2, 0.2, 0.6)):
            b.cyl((x, 0.2, 0.0), (x, 0.2, 2.6), 0.06, steel)
            b.cyl((x, 0.2, 1.2 + 0.1 * (i % 2)), (x, 0.32, 1.2 + 0.1 * (i % 2)), 0.12, red, seg=14)
            b.box(x - 0.06, x + 0.06, 0.26, 0.27, 0.85, 0.95, flat(f"Tag{i}", [(0.85, 0.82, 0.7), (0.8, 0.7, 0.3), (0.9, 0.9, 0.85), (0.9, 0.4, 0.3)][i]))
        b.cyl((-0.75, 0.2, 2.0), (0.75, 0.2, 2.0), 0.08, steel)
        ob = b.finish()
        add_on_wall(ob, d["u"], d["v"], d["f"])


def pipe_run(b, u0, u1, v, z, r, lag, label_mat=None):
    steel = toon("PipeSteel", (0.38, 0.38, 0.36), noise=0.08)
    lagging = toon("Lagging", (0.72, 0.7, 0.62), noise=0.14, noise_scale=9)
    band = toon("LagBand", (0.32, 0.33, 0.31))
    b.cyl((u0, v, z), (u1, v, z), lag, lagging, seg=16)
    u = u0 + 0.5
    while u < u1 - 0.2:
        b.cyl((u, v, z), (u + 0.04, v, z), lag + 0.006, band, seg=16)
        u += 1.0


def build_pipes(d):
    b = Builder("Pipes")
    steel = toon("PipeSteel", (0.38, 0.38, 0.36), noise=0.08)
    v = d["v"] - 0.24
    gap = d.get("gap")
    runs = [(1.75, 0.07, 0.1), (1.15, 0.09, 0.13), (0.55, 0.09, 0.13)]
    for k, (z, r, lag) in enumerate(runs):
        if k == 1 and gap:
            pipe_run(b, d["u0"], gap[0], v, z, r, lag); pipe_run(b, gap[1], d["u1"], v, z, r, lag)
        else:
            pipe_run(b, d["u0"], d["u1"], v, z, r, lag)
        b.cyl((d["u0"], v, z), (d["u0"], d["v"], z), r, steel)              # into the wall
    u = d["u0"] + 0.8
    while u < d["u1"]:
        b.box(u - 0.04, u + 0.04, v, d["v"], 0.3, 1.95, toon("Bracket", (0.3, 0.3, 0.28), noise=0.1))
        u += 2.0
    for u in (2.9, 3.5):                                                       # valve wheels
        z = 1.15 if u < 3.2 else 0.55
        b.cyl((u, v - 0.13, z), (u, v - 0.3, z), 0.03, steel)
        b.cyl((u, v - 0.3, z), (u, v - 0.33, z), 0.16, toon("ValveRed", (0.5, 0.12, 0.1)), seg=16)
    for u in (6.0, 14.0):                                                      # gauges
        b.cyl((u, v - 0.1, 1.75), (u, v - 0.25, 1.95), 0.012, steel)
        b.cyl((u, v - 0.24, 1.98), (u, v - 0.29, 1.98), 0.08, flat("GaugeFace", (0.86, 0.85, 0.8)), seg=16)
    ob = b.finish(outline=0.01)
    ob.matrix_world = ROT45 @ ob.matrix_world
    bg_objects.append(ob)
    # labels on the pipe lagging, facing the camera side (-v)
    lab = flat("PipeLabel", (0.1, 0.1, 0.1))
    for (u, z, txt) in ((1.5, 1.75, "BORE WATER  >>"), (1.5, 1.15, "HEATING FLOW - GENERAL CIRCUIT  >> L2"), (1.5, 0.55, "<<  HEATING RETURN"),
                        (11.5, 1.15, "HEATING FLOW - GENERAL CIRCUIT  >> L2"), (11.5, 0.55, "<<  HEATING RETURN")):
        lag = 0.1 if z > 1.5 else 0.13
        add_text_on_wall(txt, STENCIL, 0.085, lab, u, v - lag - 0.012, "-v", z - 0.04, dy=0.0, align="LEFT")


for d in LV["decor"]:
    decor(d)

# ============================================================ camera and rendering
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam)
cam.data.type = "ORTHO"
cam.rotation_euler = (math.radians(60), 0, 0)
sc.camera = cam
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"; sc.cycles.samples = 4 if QUICK else 10; sc.cycles.use_denoising = False
sc.cycles.max_bounces = 0; sc.cycles.transparent_max_bounces = 12
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"
sc.world = bpy.data.worlds.new("W")
UPV = Vector((0, SIN, COS)); VIEW = Vector((0, COS, -SIN))


def screen_rect(objs, pad=6):
    dg = bpy.context.evaluated_depsgraph_get()
    xs, ys = [], []
    for ob in objs:
        e = ob.evaluated_get(dg)
        for c in e.bound_box:
            p = e.matrix_world @ Vector(c)
            sx, sy = scr(p.x, p.y, p.z)
            xs.append(sx); ys.append(sy)
    return [math.floor(min(xs)) - pad, math.floor(min(ys)) - pad, math.ceil(max(xs)) + pad, math.ceil(max(ys)) + pad]


def render(objs, path, rect=None):
    for ob in sc.objects:
        if ob.type in ("MESH", "FONT", "CURVE"):
            ob.hide_render = ob not in objs
    rect = rect or screen_rect(objs)
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    sc.render.resolution_x, sc.render.resolution_y = w, h
    cam.data.ortho_scale = max(w, h) / PPM
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    centre = Vector((cx / PPM, 0, 0)) + UPV * (-cy / PPM)
    cam.location = centre - VIEW * 60
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return rect


out = {"level": LEVEL, "name": LV["name"], "ppm": PPM, "rooms": [], "walls": [], "doors": [], "props": [],
       "inspect": LV["inspect"], "stairs": LV["stairs"], "spawns": LV["spawns"], "blocked": LV["blocked"] + LV.get("holes", []),
       "bounds": LV["bounds"], "sprites": []}
for r in LV["rooms"]:
    out["rooms"].append({k: r[k] for k in ("id", "r") if k in r} | ({"name": r["name"]} if "name" in r else {}) | ({"dark": True} if r.get("dark") else {}))
for w in LV["walls"]:
    out["walls"].append({"a": list(w["a"]), "b": list(w["b"]), "h": w["h"], "openings": [list(o) for o in w.get("openings", [])]})

print("background objects", len(bg_objects))
rect = render(bg_objects, os.path.join(DIR, "bg.png"))
out["bg"] = {"file": "bg.png", "x0": rect[0], "y0": rect[1]}
for ob in bg_objects:
    ob.hide_render = True

# ============================================================ sprites
PROP_FN = {
    "bunk": lambda p: kit.bunk("Bunk", p.get("k", 0), p.get("stripped", False)),
    "bed": lambda p: kit.bed("Bed", p.get("k", 1)),
    "locker": lambda p: kit.locker("Locker", p.get("w", 0.55), p.get("open", False)),
    "desk": lambda p: kit.desk("Desk"),
    "chair": lambda p: kit.chair("Chair", p.get("overturned", False)),
    "table": lambda p: kit.table("Table", p.get("L", 1.2)),
    "stool": lambda p: kit.stool("Stool"),
    "curtain": lambda p: kit.curtain("Curtain", p.get("k", 0)),
    "toolbox": lambda p: kit.toolbox("Toolbox"),
    "crate": lambda p: kit.crate("Crate"),
    "bucket": lambda p: kit.bucket("Bucket"),
    "shelf": lambda p: kit.shelf("Shelf"),
    "sinks": lambda p: kit.sinks("Sinks", p.get("n", 3)),
    "stall": lambda p: kit.stall("Stall"),
    "laundry": lambda p: kit.laundry("Laundry", p.get("k", 0)),
    "pump": lambda p: kit.pump("Pump"),
    "workbench": lambda p: kit.workbench("Workbench"),
}
cache = {}


def sprite_for(sig, build):
    """Render a variant once at the origin; return (file, offset of its top-left from the origin's screen point)."""
    if sig in cache:
        return cache[sig]
    objs = build()
    rect = render(objs, os.path.join(DIR, f"spr_{len(cache):03d}.png"))
    for ob in objs:
        bpy.data.objects.remove(ob, do_unlink=True)
    cache[sig] = (f"spr_{len(cache):03d}.png", [rect[0], rect[1]], [rect[2] - rect[0], rect[3] - rect[1]])
    return cache[sig]


for i, p in enumerate(LV["props"]):
    keyargs = tuple(sorted((k, v) for k, v in p.items() if k not in ("u", "v", "name", "text", "id")))

    def build(p=p):
        ob, size = PROP_FN[p["t"]](p)
        place([ob], 0.0, 0.0, p["f"])
        return [ob]

    ob, size = None, None
    # footprint needs the size: build a throwaway to measure only on first use
    f, off, wh = sprite_for(keyargs, build)
    L, Dp = {"bunk": (2.0, 0.9), "bed": (2.0, 0.9), "locker": (p.get("w", 0.55), 0.5), "desk": (1.2, 0.6), "chair": (0.5, 0.5),
             "table": (p.get("L", 1.2), 0.7), "stool": (0.36, 0.36), "curtain": (0.65, 0.1), "toolbox": (1.0, 0.3), "crate": (0.62, 0.62),
             "bucket": (0.34, 0.34), "shelf": (1.1, 0.45), "sinks": (0.7 * p.get("n", 3), 0.45), "stall": (0.9, 1.2), "laundry": (1.8, 0.25),
             "pump": (1.2, 0.7), "workbench": (1.8, 0.7)}[p["t"]]
    fp = footprint(p["u"], p["v"], p["f"], L, Dp)
    cu, cv = (fp[0] + fp[1]) / 2, (fp[2] + fp[3]) / 2
    sx, sy = scr_uv(p["u"], p["v"])
    srt = scr_uv(cu, cv)
    entry = {"type": p["t"], "footprint": fp, "sprite": f, "x0": round(sx + off[0], 1), "y0": round(sy + off[1], 1),
             "sort": [round(srt[0], 1), round(srt[1], 1)]}
    for k in ("id", "name", "text"):
        if k in p:
            entry[k] = p[k]
    out["props"].append(entry)


def door_obj(kind, is_open):
    b = Builder("Door")
    frame = toon("DoorFrame", (0.3, 0.33, 0.3), noise=0.08)
    W, H = 1.0, 2.05
    b.box(-W / 2 - 0.06, -W / 2, -T / 2, T / 2, 0, H + 0.06, frame)
    b.box(W / 2, W / 2 + 0.06, -T / 2, T / 2, 0, H + 0.06, frame)
    b.box(-W / 2 - 0.06, W / 2 + 0.06, -T / 2, T / 2, H, H + 0.08, frame)
    if kind == "steel":
        slab = toon("SteelDoor", (0.33, 0.38, 0.35), noise=0.12, noise_scale=6)
        rivet = toon("Rivet", (0.25, 0.28, 0.26))
    else:
        slab = toon("PlyDoor", kit.PLY, noise=0.12, noise_scale=8)
        rivet = toon("Steel", (0.5, 0.5, 0.5))
    th = 0.06
    if is_open:                      # swung inwards (+y local is the corridor side, door opens away from it)
        M = Matrix.Translation((-W / 2, 0, 0)) @ Matrix.Rotation(math.radians(-95), 4, "Z") @ Matrix.Translation((W / 2, 0, 0))
    else:
        M = Matrix()
    b.box(-W / 2 + 0.01, W / 2 - 0.01, -th / 2, th / 2, 0.02, H - 0.02, slab, M)
    b.box(W / 2 - 0.15, W / 2 - 0.1, th / 2, th / 2 + 0.04, 0.95, 1.05, rivet, M)
    if kind == "steel":
        for x in (-W / 2 + 0.08, W / 2 - 0.08):
            for z in (0.15, 0.7, 1.3, 1.9):
                b.box(x - 0.015, x + 0.015, th / 2, th / 2 + 0.01, z - 0.015, z + 0.015, rivet, M)
        b.box(W / 2 - 0.2, W / 2 - 0.05, th / 2, th / 2 + 0.05, 1.1, 1.25, toon("Padlock", (0.55, 0.45, 0.18)), M)
    ob = b.finish(outline=0.01)
    if kind == "steel" and not is_open:
        txt = text_obj("2-D", STENCIL, 0.2, flat("DoorStencil", (0.82, 0.78, 0.66)))
        txt.matrix_world = Matrix.Translation((0, th / 2 + 0.004, 1.6)) @ Matrix.Rotation(math.pi, 4, "Z") @ Matrix.Rotation(math.radians(90), 4, "X")
        return [ob, txt]
    return [ob]


for d in LV["doors"]:
    facing = "-v" if d["axis"] == "u" else "-u"        # the door's front faces the corridor (camera side)
    ent = {k: d[k] for k in d if k not in ("axis",)}
    for state in ("closed", "open"):
        def build(d=d, state=state, facing=facing):
            objs = door_obj(d["kind"], state == "open")
            ang = kit.facing_frame(facing)
            for o in objs:
                o.matrix_world = Matrix.Rotation(ang, 4, "Z") @ o.matrix_world
            return objs
        f, off, wh = sprite_for(("door", d["kind"], state, facing), build)
        sx, sy = scr_uv(d["u"], d["v"])
        ent["spr_" + state] = {"sprite": f, "x0": round(sx + off[0], 1), "y0": round(sy + off[1], 1)}
    srt = scr_uv(d["u"], d["v"])
    ent["sort"] = [round(srt[0], 1), round(srt[1], 1)]
    out["doors"].append(ent)

if "pipe" in LV:
    pd = LV["pipe"]
    v = pd["v"] - 0.24
    gap = (8.1, 9.3)

    def build_broken():
        b = Builder("PipeBroken")
        steel = toon("PipeSteel", (0.38, 0.38, 0.36), noise=0.08)
        lag = toon("Lagging", (0.72, 0.7, 0.62), noise=0.14, noise_scale=9)
        dark = toon("PipeHole", (0.06, 0.05, 0.05))
        b.cyl((gap[0], v, 1.15), (gap[1], v, 1.15), 0.09, toon("RustPipe", kit.RUST, noise=0.2, noise_scale=12), seg=16)
        b.cyl((gap[0], v, 1.15), (gap[0] + 0.25, v, 1.15), 0.13, lag, seg=16)
        b.cyl((gap[1] - 0.2, v, 1.15), (gap[1], v, 1.15), 0.13, lag, seg=16)
        for k in range(7):                                # shredded lagging hanging down
            uu = gap[0] + 0.3 + k * 0.09
            b.box(uu, uu + 0.05, v - 0.12, v - 0.1, 0.8 + 0.05 * (k % 3), 1.12, lag)
        b.box(8.55, 8.8, v - 0.095, v - 0.08, 1.08, 1.2, dark)
        b.box(8.6, 8.75, v - 0.1, v - 0.085, 1.0, 1.08, dark)
        ob = b.finish(outline=0.01)
        ob.matrix_world = ROT45 @ ob.matrix_world
        return [ob]

    def build_fixed():
        b = Builder("PipeFixed")
        lag = toon("LaggingNew", (0.8, 0.78, 0.68), noise=0.08, noise_scale=9)
        steel = toon("PipeSteel", (0.38, 0.38, 0.36), noise=0.08)
        b.cyl((gap[0], v, 1.15), (gap[1], v, 1.15), 0.13, toon("Lagging", (0.72, 0.7, 0.62), noise=0.14, noise_scale=9), seg=16)
        b.cyl((8.4, v, 1.15), (9.05, v, 1.15), 0.135, lag, seg=16)
        for uu in (8.42, 9.0):
            b.cyl((uu, v, 1.15), (uu + 0.05, v, 1.15), 0.145, steel, seg=16)
        ob = b.finish(outline=0.01)
        ob.matrix_world = ROT45 @ ob.matrix_world
        return [ob]

    ent = dict(pd)
    for state, fn in (("broken", build_broken), ("fixed", build_fixed)):
        f, off, wh = sprite_for(("pipe", state), fn)
        ent[state] = {"sprite": f, "x0": off[0], "y0": off[1]}         # absolute: built in place
    srt = scr_uv(pd["u"], pd["v"])
    ent["sort"] = [round(srt[0], 1), round(srt[1], 1)]
    out["pipe"] = ent

json.dump(out, open(os.path.join(DIR, "level.json"), "w"), indent=1)
print("done", LEVEL, "sprites", len(cache))
