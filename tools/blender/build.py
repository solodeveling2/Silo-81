"""Build one Silo 81 level in Blender and render it for Godot.

Outputs (in OUT/LEVEL):
  bg.png                     floor, walls, stairs, pipes and everything fixed to a back wall or the floor
  spr_*.png                  free-standing props, doors (open/closed) and pipe states, one image per variant
  level.json                 rooms, walls, doors, props, interactables and spawns, plus sprite placement
Screen space (Godot pixels): sx = x * PPM, sy = -(y * sin(e) + z * cos(e)) * PPM, e = camera.json elev_deg.

Usage: python3 -I build.py L2|L3 out_dir [--quick]
"""
import sys, os, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
import kit
from kit import Builder, toon, flat, text_obj, g, place, footprint, FACING, AGE_PROFILES

_argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [a for a in sys.argv[1:] if a not in ("-b", "--background", "-P", "--python") and not a.endswith("build.py")]
LEVEL, OUT = _argv[0], _argv[1]
QUICK = "--quick" in sys.argv
PPM = 165.0
CAMERA = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "camera.json")))
ELEV = math.radians(CAMERA["elev_deg"])
SIN, COS = math.sin(ELEV), math.cos(ELEV)            # ground depth and height factors on screen
T = 0.25                     # wall thickness
FULL, STUB = 2.7, 0.4
PIPE_Z = (1.75, 1.15, 0.45)  # pipe gallery runs, top to bottom: bore water, heating return, heating flow        # back walls stand full height; the rest are cut away like a dollhouse
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
    concrete = dict(rgb=(0.5, 0.49, 0.45), noise=0.18, noise_scale=3.0, tex="concrete_floor", ts=1.5)
    D["rooms"] += [
        dict(id="landing", r=[-4.2, 0.0, -1.4, 1.4], floor=concrete),
        dict(id="corridor", r=[0.0, 22.6, -1.4, 1.4], floor=dict(concrete, frost=(15.0, 22.0))),
        dict(id="room_2_1", name="Your room", r=[0.6, 4.6, 1.4, 5.6], floor=dict(rgb=(0.44, 0.36, 0.28), noise=0.15, noise_scale=8, tex="wood_planks", ts=2.4)),
        dict(id="dorm_2a", name="Dormitory 2-A", r=[4.6, 11.6, 1.4, 5.6], floor=concrete),
        dict(id="dorm_2b", name="Dormitory 2-B", r=[11.6, 18.6, 1.4, 5.6], floor=dict(concrete, frost=(16.0, 21.0))),
        dict(id="room_2_d", name="Room 2-D", r=[18.6, 22.6, 1.4, 5.6], floor=dict(concrete, frost=(18.0, 20.0)), dark=True),
        dict(id="washroom", name="Washroom", r=[1.0, 7.0, -5.0, -1.4], floor=dict(rgb=(0.62, 0.66, 0.62), noise=0.08, noise_scale=20, grating=((0.48, 0.52, 0.49), 0.3), tex="tile_frosted", ts=1.2)),
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
        dict(a=(-4.2, -1.4), b=(-4.2, 1.4), h=STUB, openings=[(-1.3, -0.1, None)]),
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
        dict(t="locker", u=4.6 + T / 2, v=2.6, f="+u", w=1.0, name="Lockers", text="Two doors, two names on tape, one padlock between them."),
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
        dict(t="floortext", u=-3.4, v=-0.95, text="< COMMONS"),
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
                         text="The stairwell down to Level 3, life support."),
                    dict(id="to_commons", u=-4.0, v=-0.7, to="L2W", arrive=[-5.0, 0.0], name="Commons wing",
                         text="West, past the dead lift, to the commons, the clinic and the school.")]
    D["spawns"] = {"player": [2.3, 3.5, 5], "worms": []}
    D["bounds"] = [-4.2, 22.6, -5.0, 5.6]
    # light: the dormitories are short of heat (a slightly cool base), dim bulbs along the corridor,
    # cold pockets at the frozen north end; Room 2-D stays unlit
    D["light"] = dict(ambient=(0.96, 0.98, 1.02),
                      lamps=[(u, -0.35, 2.5, 3.2, "bulb") for u in (2.0, 7.5, 13.0)] +
                            [(8.1, 3.4, 2.4, 3.0, "bulb"), (15.1, 3.4, 2.4, 2.6, "bulb"), (4.0, -3.2, 2.4, 2.8, "bulb"),
                             (10.5, -3.2, 2.4, 2.8, "bulb"), (2.6, 3.6, 2.3, 2.4, "bulb"),
                             (19.5, 0.0, 1.0, 4.0, "cold"), (20.6, 3.5, 1.0, 3.2, "cold"), (17.0, -3.2, 1.0, 3.0, "cold")])
    labels = [d for d in D["decor"] if d["t"] == "floortext" and d.get("v") == -0.75]
    lines = [d for d in D["decor"] if d["t"] == "floorline"]
    D = shift_south(D, -1.4, L2_WIDEN)
    for d in labels:                    # door labels on the corridor floor follow the south wall
        d["v"] = -0.75 - L2_WIDEN
    for d in lines:                     # the painted guide line stays mid-way across the wider corridor
        d["v"] = -0.95 - L2_WIDEN / 2
    return D


L2_WIDEN = 0.7                 # corridor 2.8 -> 3.5 m: the south wall and every room behind it move away


def widen(D, line, dv, label_v):
    """Widen a level's main corridor by moving its camera-side wall (plan v = line) and everything
    behind it by -dv; the door labels painted next to that wall (at v = label_v) follow it."""
    labels = [d for d in D["decor"] if d["t"] == "floortext" and abs(d.get("v", 99) - label_v) < 1e-6]
    mounted = [d for k in ("decor", "props", "inspect") for d in D[k]          # hung on the wall's corridor face
               if d.get("f") == "+v" and "v" in d and line < d["v"] <= line + 0.3]
    D = shift_south(D, line, dv)
    for d in mounted:                      # after the shift, so they move exactly once
        d["v"] -= dv
    for d in labels:
        d["v"] = label_v - dv
    return D


def shift_south(D, line, dv):
    """Move everything at or beyond plan v = line (the corridor's camera-side wall and the rooms behind
    it) by -dv. Door positions along the corridor and every room's size are unchanged."""
    f = lambda v: v - dv if v <= line + 1e-6 else v
    for r in D["rooms"]:
        r["r"] = [r["r"][0], r["r"][1], f(r["r"][2]), f(r["r"][3])]
    for w in D["walls"]:
        w["a"], w["b"] = (w["a"][0], f(w["a"][1])), (w["b"][0], f(w["b"][1]))
        if w["a"][0] == w["b"][0] and w.get("openings"):          # wall along v: openings are v ranges
            w["openings"] = [(f(o[0]), f(o[1]), o[2]) for o in w["openings"]]
    for key in ("doors", "props", "decor", "inspect", "stairs"):
        for d in D[key]:
            for k in ("v", "v0", "v1"):
                if k in d:
                    d[k] = f(d[k])
            if "arrive" in d:
                d["arrive"] = [d["arrive"][0], f(d["arrive"][1])]
    for key in ("holes", "blocked"):
        D[key] = [[h[0], h[1], f(h[2]), f(h[3])] for h in D.get(key, [])]
    sp = D["spawns"].get("player")
    if sp:
        sp[1] = f(sp[1])
    D["bounds"] = [D["bounds"][0], D["bounds"][1], f(D["bounds"][2]), D["bounds"][3]]
    return D


def L3():
    D = {"name": "Level 3 - Pipe gallery", "rooms": [], "walls": [], "doors": [], "props": [], "decor": [],
         "inspect": [], "stairs": [], "spawns": {}, "blocked": []}
    raw = dict(rgb=(0.47, 0.46, 0.43), noise=0.2, noise_scale=3.0, tex="concrete_floor", ts=1.5)
    D["rooms"] += [
        dict(id="landing", r=[-4.2, 0.0, -1.6, 1.8], floor=raw),
        dict(id="gallery", name="Pipe gallery", r=[0.0, 18.0, -1.6, 1.8], floor=dict(rgb=(0.2, 0.21, 0.2), tex="concrete_floor", ts=1.5, tint=(0.8, 0.82, 0.84))),
        dict(id="pumps", name="Pump room 3-P", r=[9.0, 18.0, -6.0, -1.6], floor=dict(raw, rgb=(0.45, 0.44, 0.41))),
    ]
    D["holes"] = []
    D["blocked"] += [[-4.2, -0.75, 0.35, 1.8]]       # the stair flight
    D["holes"] = [[-4.0, -0.8, -1.5, 0.15]]          # the flight down to Level 4
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
        dict(t="pipes", u0=-0.6, u1=18.0 - T / 2, v=WI, gap=(8.25, 9.45), gap_run=2),
        dict(t="stairs_up", u0=-4.0, u1=-0.8, v0=0.4, v1=1.8),
        dict(t="stairs_down", u0=-4.0, u1=-0.8, v0=-1.5, v1=0.15),
        dict(t="stencil", u=1.8, v=WI, f="-v", z=2.35, text="LEVEL 3 - LIFE SUPPORT", size=0.15),
        dict(t="stencil", u=18.0 - T / 2, v=-3.6, f="-u", z=2.3, text="PUMP ROOM 3-P", size=0.15),
        dict(t="manifold", u=18.0 - T / 2, v=-2.6, f="-u"),
        dict(t="puddle", u=8.95, v=0.82, ru=0.9, rv=0.55), dict(t="puddle", u=8.75, v=-0.35, ru=0.22, rv=0.7),
        dict(t="puddle", u=7.7, v=0.45, ru=0.45, rv=0.3), dict(t="puddle", u=9.2, v=-1.05, ru=0.6, rv=0.22),
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
    D["pipe"] = dict(id="pipe_break", u=8.85, v=WI, z=PIPE_Z[2], gap=(8.25, 9.45), name="Burst pipe",
                     text="The heating flow for the general circuit, chewed through. Hot water sprays from the hole and the pressure is falling. It needs welding.",
                     fixed_text="Welded. The bead is ugly but it holds, and the gauge needle is climbing back.")
    D["inspect"] += [
        dict(id="pipes_label", u=4.5, v=1.2, name="Pipes", text="Top to bottom: bore water; heating return; heating flow for the general circuit, up to Level 2. The flow runs lowest, where the worms can reach it."),
        dict(id="gauge", u=14.0, v=1.2, name="Gauge", text="Pressure on the general circuit, falling."),
        dict(id="manifold", u=17.6, v=-2.6, name="Valve manifold", text="Valve wheels tagged in three different handwritings. The newest tag says COUNCIL ORDER: DO NOT OPEN."),
    ]
    D["stairs"] += [dict(id="stairs_up", u=-0.45, v=1.0, to="L2", arrive=[-0.3, 0.0], name="Stairs up",
                         text="Back up to Level 2."),
                    dict(id="stairs_down", u=-0.45, v=-0.9, to="L4W", arrive=[-0.3, -0.6], name="Stairs down",
                         text="Down to Level 4: engineering and command. The air gets warmer on every step.")]
    D["spawns"] = {"player": [-0.3, 0.0, 0], "worms": [[8.32, 1.08, 1, "chew"], [5.4, 0.85, 2], [13.1, -3.0, 1]]}
    D["bounds"] = [-4.2, 18.0, -6.0, 1.8]
    D["front_h"] = 1.1           # the gallery's camera-side wall stays waist high: the pipes are the point
    # light: the heating mains keep the gallery warm; caged work lamps along it and over the pumps
    D["light"] = dict(ambient=(1.02, 1.0, 0.96),
                      lamps=[(u, 1.0, 2.4, 3.2, "work") for u in (2.5, 8.5, 14.5)] +
                            [(11.5, -3.6, 2.4, 3.6, "work"), (16.0, -4.5, 2.4, 2.8, "bulb"), (-2.0, 0.0, 2.4, 2.6, "bulb")])
    return D


def L2W():
    """Level 2 west of the core: the commons, kitchen, clinic, classroom, Archive and west washroom."""
    D = {"name": "Level 2 - Commons", "rooms": [], "walls": [], "doors": [], "props": [], "decor": [],
         "inspect": [], "stairs": [], "spawns": {}, "blocked": []}
    concrete = dict(rgb=(0.5, 0.49, 0.45), noise=0.18, noise_scale=3.0, tex="concrete_floor", ts=1.5)
    lino = dict(rgb=(0.45, 0.33, 0.27), noise=0.12, noise_scale=6, grating=((0.38, 0.27, 0.22), 0.6), tex="lino", ts=1.6)
    tile = dict(rgb=(0.6, 0.62, 0.58), noise=0.08, noise_scale=20, grating=((0.47, 0.49, 0.46), 0.3), tex="tile_white", ts=1.6)
    clinic = dict(rgb=(0.62, 0.68, 0.64), noise=0.06, noise_scale=20, grating=((0.52, 0.58, 0.55), 0.4), tex="tile_clinic", ts=1.2)
    wood = dict(rgb=(0.47, 0.36, 0.25), noise=0.15, noise_scale=8, tex="wood_planks", ts=2.4)
    D["rooms"] += [
        dict(id="lobby", r=[-8.2, -4.2, -1.4, 1.4], floor=concrete),
        dict(id="corridor_w", r=[-32.0, -8.2, -1.4, 1.4], floor=concrete),
        dict(id="commons", name="Commons", r=[-21.0, -8.2, 1.4, 9.4], floor=lino),
        dict(id="kitchen", name="Kitchen", r=[-26.0, -21.0, 1.4, 9.4], floor=tile),
        dict(id="classroom", name="Classroom", r=[-32.0, -26.0, 1.4, 7.9], floor=wood),
        dict(id="waiting", name="Clinic waiting room", r=[-12.0, -8.2, -6.4, -1.4], floor=clinic),
        dict(id="clinic", name="Clinic and ward", r=[-22.0, -12.0, -8.4, -1.4], floor=clinic),
        dict(id="wash_w", name="West washroom", r=[-25.5, -22.0, -7.9, -1.4], floor=tile),
        dict(id="archive", name="Archive", r=[-32.0, -25.5, -7.9, -1.4], floor=wood),
    ]
    W = D["walls"]
    W += [
        # back walls (north and east faces), full height
        dict(a=(-21.0, 9.4), b=(-8.2, 9.4), h=FULL, face="-v"),
        dict(a=(-26.0, 9.4), b=(-21.0, 9.4), h=FULL, face="-v"),
        dict(a=(-32.0, 7.9), b=(-26.0, 7.9), h=FULL, face="-v"),
        dict(a=(-8.2, 1.4), b=(-8.2, 9.4), h=FULL, face="-u"),
        dict(a=(-8.2, 1.4), b=(-4.2, 1.4), h=FULL, face="-v"),
        dict(a=(-8.2, -6.4), b=(-8.2, -1.4), h=FULL, face="-u"),
        # everything else cut down
        dict(a=(-26.0, 7.9), b=(-26.0, 9.4), h=STUB),
        dict(a=(-32.0, 1.4), b=(-8.2, 1.4), h=STUB, openings=[(-29.75, -28.45, "door_class"), (-24.4, -23.2, None), (-19.4, -17.6, None), (-12.6, -10.8, None)]),
        dict(a=(-26.0, 1.4), b=(-26.0, 7.9), h=STUB),
        dict(a=(-21.0, 1.4), b=(-21.0, 9.4), h=STUB, openings=[(6.6, 7.8, None)]),
        dict(a=(-32.0, 1.4), b=(-32.0, 7.9), h=STUB),
        dict(a=(-32.0, -1.4), b=(-32.0, 1.4), h=STUB),
        dict(a=(-32.0, -7.9), b=(-32.0, -1.4), h=STUB),
        dict(a=(-32.0, -1.4), b=(-8.2, -1.4), h=STUB, openings=[(-29.55, -28.25, "door_archive"), (-24.4, -23.1, None), (-16.15, -14.85, "door_clinic"), (-10.7, -9.5, None)]),
        dict(a=(-32.0, -7.9), b=(-22.0, -7.9), h=STUB),
        dict(a=(-25.5, -7.9), b=(-25.5, -1.4), h=STUB),
        dict(a=(-22.0, -8.4), b=(-22.0, -1.4), h=STUB),
        dict(a=(-22.0, -8.4), b=(-12.0, -8.4), h=STUB),
        dict(a=(-12.0, -8.4), b=(-12.0, -1.4), h=STUB, openings=[(-4.4, -3.2, None)]),
        dict(a=(-12.0, -6.4), b=(-8.2, -6.4), h=STUB),
        dict(a=(-8.2, -1.4), b=(-4.2, -1.4), h=STUB),
    ]
    D["doors"] += [
        dict(id="door_class", kind="plywood", u=-29.1, v=1.4, axis="u", open=True, locked=False, name="Classroom door",
             text="Plywood, painted with a sun and a row of handprints at child height."),
        dict(id="door_archive", kind="plywood", u=-28.9, v=-1.4, axis="u", open=False, locked=False, name="Archive door",
             text="ARCHIVE - RECORDS, stencilled. Hollo keeps it shut so the paper stays dry."),
        dict(id="door_clinic", kind="plywood", u=-15.5, v=-1.4, axis="u", open=True, locked=False, name="Clinic door",
             text="Propped open. The warm air leaks out into the corridor and nobody minds."),
    ]
    P = D["props"]
    CN = 9.4 - T / 2            # commons and kitchen back wall face
    # commons: three long tables with benches, the Exchange at the kitchen hatch
    for u in (-18.4, -14.9, -11.4):
        P += [dict(t="table", u=u, v=3.4, f="+u", L=2.4, name="Canteen table", text="Scrubbed pale. Meals are eaten in three shifts, and you sit where your shift sits."),
              dict(t="bench", u=u - 0.55, v=4.6, f="+u", L=2.2), dict(t="bench", u=u + 0.95, v=4.6, f="-u", L=2.2)]
    P += [
        dict(t="counter", u=-21.0 + T / 2, v=7.2, f="+u", L=1.8, hatch=True, id="exchange", name="The Exchange",
             text="Kasimir's counter at the old serving hatch. Thread, batteries, a jar of honey that is mostly water. Everything has a price in ration coupons, and the price moves."),
        dict(t="stool", u=-19.9, v=5.6, f="-u"),
        dict(t="crate", u=-20.4, v=8.7, f="+u", name="Crate", text="Kasimir's stock. Padlocked."),
        dict(t="bench", u=-8.2 - T / 2, v=6.2, f="-u", L=2.2, name="Bench", text="By the radiator, the best seat in the commons."),
    ]
    # kitchen
    P += [
        dict(t="stove", u=-24.6, v=CN, f="-v", name="Cooking range", text="Cast iron, older than anyone. It burns dried stalks from the bays when the hotplates are off."),
        dict(t="sinks", u=-22.5, v=CN, f="-v", n=2, name="Kitchen sinks", text="Warm water here twice a day, for washing pots, not hands."),
        dict(t="counter", u=-26.0 + T / 2, v=4.4, f="+u", L=2.4, name="Kitchen counter", text="Knives on chains. Someone has scratched a tally of meals into the steel."),
        dict(t="sacks", u=-22.3, v=2.0, f="+v", name="Sacks", text="Potatoes and barley from the bays, weighed in, weighed out, signed for by Albu's clerk."),
        dict(t="shelf", u=-26.0 + T / 2, v=7.4, f="+u", name="Shelves", text="Tins with no labels and a jar of salt counted by the spoon."),
    ]
    # classroom
    CL = 7.9 - T / 2
    for u in (-30.9, -27.3):
        for v in (5.4, 4.0, 2.6):
            P.append(dict(t="schooldesk", u=u, v=v, f="-v", name="School desk", text="Initials carved through three generations of varnish."))
    P += [dict(t="desk", u=-28.4, v=CL - 0.35, f="-v", name="Teacher's desk", text="Hollo's lesson plan, unchanged since the founders wrote it. Today: the core, and why we do not waste heat.")]
    # archive
    AS = -7.9 + T / 2
    for i, u in enumerate((-31.3, -30.1, -28.9)):
        P.append(dict(t="files", u=u, v=AS, f="+v", k=i, name="Archive shelves", text="Box files by year. Some years are thinner than others."))
    P += [
        dict(t="files", u=-32.0 + T / 2, v=-3.0, f="+u", k=3, id="archive_back", name="Back shelf",
             text="The last shelf against the wall. Behind the box files, wedged at the back, something hard and square wrapped in a rag."),
        dict(t="cabinet", u=-26.0, v=AS, f="+v", name="Filing cabinet", text="Ration ledgers, decades of them. Names crossed out in different inks."),
        dict(t="cabinet", u=-26.6, v=AS, f="+v", name="Filing cabinet", text="Admissions, 1952. The founders numbered the residents by trade."),
        dict(t="desk", u=-27.4, v=-3.6, f="+u", name="Hollo's desk", text="A black pen, a red pen and a stack of files with strips of paper pasted over lines."),
        dict(t="chair", u=-26.7, v=-3.6, f="-u"),
    ]
    # west washroom
    P += [dict(t="sinks", u=-25.5 + T / 2, v=-3.6, f="+u", n=2, name="Washbasins", text="Bath day is posted on the door. It is not today.")]
    for v in (-4.0, -5.2, -6.4):
        P.append(dict(t="stall", u=-22.0 - T / 2, v=v, f="-u", name="Toilet stall", text="Working, mostly."))
    # clinic and ward
    CS = -8.4 + T / 2
    for i, u in enumerate((-20.7, -18.0, -15.3)):
        P.append(dict(t="bed", u=u, v=CS, f="+v", k=(i + 2) % 5, name="Ward bed", text="Clean sheets, boiled and dried on the clinic's own radiator."))
    P[-1].update(id="bed_grigore", name="Grigore's bed",
                 text="Grigore's bed. Diagrams of the exchanger in pencil on the back of ration forms, under the pillow.")
    for u in (-19.35, -16.65):
        P.append(dict(t="medscreen", u=u, v=-6.9, f="+v", name="Screen", text="A folding screen. Privacy, of a kind."))
    P += [
        dict(t="medcab", u=-22.0 + T / 2, v=-3.0, f="+u", name="Medicine cabinet", text="Dr. Kiss's stock: aspirin cut in halves, iodine, a bottle of something brown with no label."),
        dict(t="medcab", u=-22.0 + T / 2, v=-4.1, f="+u", name="Medicine cabinet", text="Bandages washed and rolled for reuse."),
        dict(t="desk", u=-13.2, v=-2.4, f="-v", name="Dr. Kiss's desk", text="The health-screening schedule. Every resident, every quarter, measured against a list nobody here wrote."),
        dict(t="chair", u=-13.2, v=-3.2, f="+v"),
    ]
    # waiting room
    P += [
        dict(t="bench", u=-8.2 - T / 2, v=-3.9, f="-u", L=2.6, name="Waiting bench", text="Full. Half the people here are not ill; they are warm."),
        dict(t="bench", u=-10.4, v=-6.4 + T / 2, f="+v", L=2.6, name="Waiting bench", text="Someone is asleep on it, coat over their head."),
    ]
    D["decor"] += [
        dict(t="liftdoor", u=-6.2, v=1.4 - T / 2, f="-v"),
        dict(t="switchboard", u=-4.9, v=-1.4 + T / 2, f="+v", z=0.9),
        dict(t="noticeboard", u=-7.4, v=-1.4 + T / 2, f="+v", z=1.0, title="LEVEL 2 NOTICES"),
        dict(t="stencil", u=-14.5, v=CN, f="-v", z=2.45, text="LEVEL 2 - COMMONS", size=0.13),
        dict(t="tvscreen", u=-14.9, v=CN, f="-v", z=1.85),
        dict(t="poster", u=-11.0, v=CN, f="-v", z=0.9),
        dict(t="noticeboard", u=-18.4, v=CN, f="-v", z=1.0, title="ROTAS"),
        dict(t="rationboard", u=-21.0 + T / 2, v=4.6, f="+u", z=1.1),
        dict(t="radiator", u=-8.2 - T / 2, v=4.2, f="-u", sections=10, state="working"),
        dict(t="radiator", u=-16.6, v=CN, f="-v", sections=10, state="dead"),
        dict(t="blackboard", u=-29.0, v=CL, f="-v", z=0.85, text="THE CORE KEEPS US WARM"),
        dict(t="drawing", u=-31.3, v=CL, f="-v", z=1.3), dict(t="drawing", u=-26.9, v=CL, f="-v", z=1.4),
        dict(t="radiator", u=-31.0, v=CL, f="-v", sections=6, state="dead"),
        dict(t="redcross", u=-8.2 - T / 2, v=-2.6, f="-u", z=1.7),
        dict(t="radiator", u=-8.2 - T / 2, v=-5.3, f="-u", sections=12, state="working"),
        dict(t="radiator", u=-12.4, v=-8.4 + T / 2, f="+v", sections=10, state="working"),
        dict(t="stencil", u=-31.0, v=7.9 - T / 2, f="-v", z=2.45, text="SCHOOL", size=0.13),
        dict(t="graffiti", u=-27.3, v=CL, f="-v", z=0.55, text="HEAT IS RANK", size=0.16, rot=-6, rgb=(0.6, 0.07, 0.05)),
        dict(t="rug", u=-28.9, v=-4.6),
        dict(t="floorline", u0=-31.8, u1=-4.4, v=-0.95),
        dict(t="floortext", u=-5.6, v=-0.6, text="DORMS >"),
        dict(t="floortext", u=-11.6, v=0.75, text="COMMONS"), dict(t="floortext", u=-29.1, v=0.75, text="SCHOOL"),
        dict(t="floortext", u=-15.5, v=-0.75, text="CLINIC"), dict(t="floortext", u=-28.9, v=-0.75, text="ARCHIVE"),
        dict(t="floortext", u=-23.8, v=-0.75, text="WC"),
    ]
    D["inspect"] += [
        dict(id="screen", u=-14.9, v=8.6, name="The screen", text="The commons screen. At set hours it plays Hollo's history of the silo: the founders, the Frostfall, the Council's wisdom. The rest of the time it is dark."),
        dict(id="rations", u=-20.4, v=4.6, name="Ration board", text="Numbered portions, chalked weekly. Council members' portions are listed separately, at the bottom, in smaller writing."),
        dict(id="lift", u=-6.2, v=0.9, name="Lift 2", text="OUT OF ORDER, sprayed across doors that have not opened in forty years. The shaft behind carries the cables now."),
        dict(id="notices", u=-7.4, v=-0.9, name="Notice board", text="Bath-day rota. Heat hours for the general circuit. A lost glove. A reminder that radiator keys are Council property."),
        dict(id="blackboard", u=-29.0, v=7.1, name="Blackboard", text="THE CORE KEEPS US WARM, in Hollo's capitals, over a chalk drawing of the exchanger that is almost right."),
        dict(id="graffiti_w", u=-27.3, v=7.2, name="Graffiti", text="HEAT IS RANK, in red crayon under the blackboard, at the height of a ten-year-old. Someone has tried to scrub it off and given up."),
        dict(id="clinic_rad", u=-9.0, v=-5.3, name="Radiator", text="Hot to the touch. The clinic is on the priority circuit, and everyone on this level knows it."),
    ]
    D["stairs"] += [dict(id="to_dorms", u=-4.7, v=0.0, to="L2", arrive=[-3.4, -0.7], name="Dormitory wing",
                         text="East, past the stairwell, to the dormitories.")]
    D["spawns"] = {"player": [-5.0, 0.0, 3], "worms": []}
    D["bounds"] = [-32.0, -4.2, -8.4, 9.4]
    D = widen(D, -1.4, 0.7, -0.75)               # the corridor continues Level 2's 3.5 m one
    # light (after the widening, so south-side lamps are in the moved rooms): shared heat in the
    # commons, the clinic on the priority circuit, a working kitchen, the west washroom unheated
    D["light"] = dict(ambient=(0.99, 0.99, 1.0),
                      lamps=[(u, -0.35, 2.5, 3.2, "bulb") for u in (-10.0, -17.0, -24.0, -30.0)] +
                            [(-12.0, 5.0, 2.5, 3.6, "amber"), (-17.5, 5.0, 2.5, 3.6, "amber"), (-23.5, 5.4, 2.4, 3.2, "work"),
                             (-29.0, 4.6, 2.5, 3.2, "bulb"), (-17.0, -5.6, 2.5, 4.2, "amber"), (-10.1, -4.6, 2.4, 2.8, "bulb"),
                             (-28.7, -5.3, 2.4, 2.8, "bulb"), (-23.7, -5.3, 1.0, 3.0, "cold")])
    return D


def L4W():
    """Level 4 west of the core: valve gallery, Engineering, the Council chamber, Varga's office,
    the radio room and the duty quarters. Everything here is on the priority circuit."""
    D = {"name": "Level 4 - Command", "rooms": [], "walls": [], "doors": [], "props": [], "decor": [],
         "inspect": [], "stairs": [], "spawns": {}, "blocked": []}
    concrete = dict(rgb=(0.5, 0.49, 0.45), noise=0.18, noise_scale=3.0, tex="concrete_floor", ts=1.5)
    plant = dict(rgb=(0.42, 0.43, 0.4), noise=0.14, noise_scale=4, grating=((0.33, 0.34, 0.32), 0.5), tex="diamond_plate", ts=1.2)
    parquet = dict(rgb=(0.46, 0.32, 0.2), noise=0.14, noise_scale=8, grating=((0.38, 0.26, 0.16), 0.4), tex="parquet", ts=1.6)
    D["rooms"] += [
        dict(id="landing4", r=[-4.2, 0.0, -1.5, 1.5], floor=concrete),
        dict(id="corridor4", r=[-30.0, -4.2, -1.5, 1.5], floor=concrete),
        dict(id="valves", name="Valve gallery", r=[-12.0, -4.2, 1.5, 8.0], floor=plant),
        dict(id="engineering", name="Engineering", r=[-12.0, -4.2, -8.0, -1.5], floor=plant),
        dict(id="council", name="Council chamber", r=[-24.0, -12.0, 1.5, 10.0], floor=parquet),
        dict(id="varga", name="Administration office", r=[-30.0, -24.0, 1.5, 10.0], floor=concrete),
        dict(id="radio", name="Radio and map room", r=[-30.0, -24.0, -8.0, -1.5], floor=concrete),
        dict(id="duty1", name="Duty quarters D-1", r=[-24.0, -20.0, -7.0, -1.5], floor=parquet),
        dict(id="duty2", name="Duty quarters D-2", r=[-20.0, -16.0, -7.0, -1.5], floor=parquet),
        dict(id="duty3", name="Duty quarters D-3", r=[-16.0, -12.0, -7.0, -1.5], floor=parquet),
    ]
    D["holes"] = []
    D["blocked"] += [[-4.2, -0.75, 0.05, 1.5]]          # the flight up
    W = D["walls"]
    W += [
        # back walls (north and east faces), full height
        dict(a=(-12.0, 8.0), b=(-4.2, 8.0), h=FULL, face="-v", mat="machine"),
        dict(a=(-24.0, 10.0), b=(-12.0, 10.0), h=FULL, face="-v", mat="panel"),
        dict(a=(-30.0, 10.0), b=(-24.0, 10.0), h=FULL, face="-v", mat="raw"),
        dict(a=(-4.2, 1.5), b=(-4.2, 8.0), h=FULL, face="-u", mat="machine"),
        dict(a=(0.0, -1.5), b=(0.0, 1.5), h=FULL, face="-u", mat="raw"),
        dict(a=(-4.2, 1.5), b=(0.0, 1.5), h=FULL, face="-v", mat="raw"),
        dict(a=(-4.2, -8.0), b=(-4.2, -1.5), h=FULL, face="-u", mat="machine"),
        dict(a=(-12.0, 8.0), b=(-12.0, 10.0), h=FULL, face="-u", mat="panel"),
        # the rest cut down
        dict(a=(-30.0, 1.5), b=(-4.2, 1.5), h=STUB, mat="panel", openings=[(-27.65, -26.35, "door_varga"), (-18.9, -17.1, None), (-9.0, -7.2, None)]),
        dict(a=(-12.0, 1.5), b=(-12.0, 8.0), h=STUB, mat="panel"),
        dict(a=(-24.0, 1.5), b=(-24.0, 10.0), h=STUB, mat="raw"),
        dict(a=(-30.0, 1.5), b=(-30.0, 10.0), h=STUB, mat="raw"),
        dict(a=(-30.0, -1.5), b=(-30.0, 1.5), h=STUB),
        dict(a=(-30.0, -8.0), b=(-30.0, -1.5), h=STUB),
        dict(a=(-30.0, -1.5), b=(-4.2, -1.5), h=STUB, openings=[(-27.6, -26.3, None), (-22.65, -21.35, "door_d1"), (-18.65, -17.35, "door_d2"),
                                                               (-14.65, -13.35, "door_d3"), (-9.0, -7.2, None)]),
        dict(a=(-30.0, -8.0), b=(-24.0, -8.0), h=STUB),
        dict(a=(-24.0, -8.0), b=(-24.0, -1.5), h=STUB),
        dict(a=(-24.0, -7.0), b=(-12.0, -7.0), h=STUB, mat="panel"),
        dict(a=(-20.0, -7.0), b=(-20.0, -1.5), h=STUB, mat="panel"),
        dict(a=(-16.0, -7.0), b=(-16.0, -1.5), h=STUB, mat="panel"),
        dict(a=(-12.0, -8.0), b=(-12.0, -1.5), h=STUB, mat="machine"),
        dict(a=(-12.0, -8.0), b=(-4.2, -8.0), h=STUB, mat="machine"),
        dict(a=(-4.2, -1.5), b=(0.0, -1.5), h=STUB),
    ]
    D["doors"] += [
        dict(id="door_varga", kind="steel", label="ADMIN", u=-27.0, v=1.5, axis="u", open=True, locked=False,
             name="Administration office", text="Heavy steel door to the Overseer's administration office."),
        dict(id="door_d1", kind="plywood", u=-22.0, v=-1.5, axis="u", open=False, locked=False, name="Quarters D-1",
             text="D-1. ALBU on a card in a brass holder."),
        dict(id="door_d2", kind="plywood", u=-18.0, v=-1.5, axis="u", open=False, locked=False, name="Quarters D-2",
             text="D-2. RUS, typed, the card perfectly straight."),
        dict(id="door_d3", kind="plywood", u=-14.0, v=-1.5, axis="u", open=True, locked=False, name="Quarters D-3",
             text="D-3. KISS, in pencil. The door is propped open with a medical textbook."),
    ]
    P = D["props"]
    VN, CN, EN = 8.0 - T / 2, 10.0 - T / 2, -8.0 + T / 2
    # valve gallery
    P += [
        dict(t="workbench", u=-11.0, v=VN, f="-v", name="Logbook bench", text="The valve log: every turn of every wheel, signed and dated. Since the second generation, most entries are signed RUS."),
        dict(t="locker", u=-12.0 + T / 2, v=3.0, f="+u", w=1.0, name="Key locker", text="Steel, chained. The radiator keys hang inside in rows, each on its own numbered hook. Four hooks are empty."),
    ]
    # Engineering
    P += [
        dict(t="workbench", u=-9.6, v=EN, f="+v", name="Workbench", text="A half-rebuilt pump impeller, its blades built up with weld and filed back by hand."),
        dict(t="lathe", u=-6.5, v=EN, f="+v", name="Lathe", text="The silo's only lathe. Its maker's plate is from 1951; its belts are cut from a conveyor in a closed section."),
        dict(t="shelf", u=-12.0 + T / 2, v=-5.4, f="+u", name="Parts shelf", text="Gaskets cut from inner tubes, labelled by size. Bearings in jars of oil."),
        dict(t="crate", u=-5.0, v=-2.4, f="-u", name="Crate", text="SPARES - EXCHANGER. Nearly empty."),
        dict(t="crate", u=-5.0, v=-3.1, f="-u"),
        dict(t="locker", u=-4.2 - T / 2, v=-5.6, f="-u", w=1.0, name="Lockers", text="Mira's overalls, a spare set of yours, a photo of the first crew taped inside a door."),
    ]
    # Council chamber: a long table, rugs and lamps carried down from closed rooms
    P += [dict(t="table", u=-18.0, v=5.4, f="+v", L=3.2, name="Council table", text="Long enough for twelve. Four chairs are used; the rest are pushed back against the wall.")]
    for u in (-19.1, -18.0, -16.9):
        P.append(dict(t="chair", u=u, v=4.85, f="+v"))
        P.append(dict(t="chair", u=u, v=6.65, f="-v"))
    P += [
        dict(t="chair", u=-20.0, v=5.75, f="+u", name="Chair at the head", text="The chair at the head of the table, with a cushion."),
        dict(t="floorlamp", u=-23.5, v=CN - 0.2, f="-v", name="Lamp", text="A brass standard lamp. The Level 1 inventory lists one like it as missing."),
        dict(t="floorlamp", u=-12.7, v=CN - 0.2, f="-v"),
        dict(t="files", u=-23.9 + T / 2, v=6.0, f="+u", k=1, name="Council records", text="Minutes, valve orders, ration tables. The spines are dated in Albu's handwriting."),
        dict(t="chair", u=-13.0, v=2.6, f="-u"), dict(t="chair", u=-13.0, v=3.3, f="-u"),
    ]
    # Administration office (Overseer's office): functional desk, communication terminal, monitors, maps & paperwork, industrial concrete walls, practical furniture, warm desk lighting
    P += [
        dict(t="desk", u=-26.6, v=6.2, f="-v", id="admin_desk", name="Overseer's desk",
             text="A heavy wooden desk under a warm green-shaded lamp. Stacked with maintenance reports, water line schematics, and heating pressure logs."),
        dict(t="chair", u=-26.6, v=7.0, f="-v"),
        dict(t="chair", u=-26.6, v=5.2, f="+v", name="Visitor's chair", text="A plain wooden chair facing the Overseer's desk."),
        dict(t="terminal", u=-28.5, v=CN, f="-v", id="varga_terminal", name="Communication terminal",
             text="The settlement's central intercom and command terminal. Its green CRT lists INTERCOM CHANNELS, SECTOR PRESSURE, DIRECTIVES."),
        dict(t="monitors", u=-25.5, v=CN, f="-v", id="admin_monitors", name="Telemetry monitors",
             text="Dual CRT monitors wired to Level 3 and Level 4 sensors. The amber screen shows residential temperatures fluctuating and regulator pressure spiking."),
        dict(t="safe", u=-29.9 + T / 2, v=7.8, f="+u", name="Safe", text="An old Romanian-made safe, painted green. The dial is worn smooth around three numbers."),
        dict(t="cabinet", u=-24.2 - T / 2, v=8.6, f="-u", name="Filing cabinet", text="Personnel files and infrastructure maintenance logs. Each resident's trade, health record and number."),
        dict(t="files", u=-24.2 - T / 2, v=6.2, f="-u", k=2, name="Settlement archives", text="Binders of schematics, ration ledgers, and forty years of improvised repair notes."),
        dict(t="bed", u=-29.9 + T / 2, v=3.9, f="+u", k=4, name="Camp bed", text="A narrow cot made up with military corners. The Overseer catches a few hours of sleep here between shifts."),
        dict(t="floorlamp", u=-24.6, v=CN - 0.2, f="-v"),
    ]
    # radio and map room
    P += [
        dict(t="radioset", u=-27.0, v=-8.0 + T / 2, f="+v", name="Radio set", text="Dusted daily, powered never. The log beside it has one entry per year: NOTHING HEARD."),
        dict(t="maptable", u=-27.0, v=-4.9, f="+v", name="Map table", text="A survey map of the valley above. The town is circled in red. Someone has pencilled a date beside it."),
        dict(t="chair", u=-29.2, v=-3.4, f="+u"),
    ]
    # duty quarters D-1 (Albu), D-2 (Rus), D-3 (Dr. Kiss)
    for u0, k, who in ((-24.0, 0, "Albu's"), (-20.0, 2, "Rus's"), (-16.0, 3, "Dr. Kiss's")):
        P += [
            dict(t="bed", u=u0 + 2.0, v=-7.0 + T / 2, f="+v", k=k, name=f"{who} bed", text="A real bed with a real mattress, on the priority circuit. Nobody on Level 2 sleeps like this."),
            dict(t="locker", u=u0 + 4.0 - T / 2, v=-3.1, f="-u", w=0.55, name="Locker", text="Locked."),
        ]
    P += [
        dict(t="desk", u=-24.0 + T / 2, v=-4.2, f="+u", name="Albu's desk", text="A ledger open at this week's rations, and a jar of sugar lumps with a paper lid."),
        dict(t="desk", u=-14.6, v=-3.2, f="+u", name="Dr. Kiss's desk", text="Medical journals from 1951, read to pieces. A drawing of Oana's, of the clinic, pinned above it."),
    ]
    D["decor"] += [
        dict(t="stairs_up", u0=-4.0, u1=-0.8, v0=0.1, v1=1.5),
        dict(t="steeldoor", u=-0.0 - T / 2, v=0.0, f="-u", label="HEATING CONTROL"),
        dict(t="steeldoor", u=-4.2 - T / 2, v=3.2, f="-u", label="SURFACE LIFT L1"),
        dict(t="stencil", u=-8.1, v=VN, f="-v", z=2.45, text="VALVE GALLERY - PRIORITY / GENERAL", size=0.11),
        dict(t="manifold", u=-9.2, v=VN, f="-v"),
        dict(t="manifold", u=-6.6, v=VN, f="-v"),
        dict(t="radiator", u=-4.2 - T / 2, v=5.6, f="-u", sections=8, state="working"),
        dict(t="toolboard", u=-4.2 - T / 2, v=-3.6, f="-u", z=1.0),
        dict(t="stencil", u=-4.2 - T / 2, v=-3.6, f="-u", z=2.3, text="ENGINEERING", size=0.13),
        dict(t="banner", u=-18.0, v=CN, f="-v", z=1.85, text="COUNCIL OF SILO 81"),
        dict(t="silomap", u=-15.0, v=CN, f="-v", z=0.9),
        dict(t="silomap", u=-27.0, v=CN, f="-v", z=1.25),
        dict(t="noticeboard", u=-30.0 + T / 2, v=5.8, f="+u", z=1.05, title="ADMINISTRATION - REPORTS"),
        dict(t="intercom", u=-28.5, v=CN, f="-v", z=1.55),
        dict(t="radiator", u=-21.2, v=CN, f="-v", sections=12, state="working"),
        dict(t="radiator", u=-29.2, v=CN, f="-v", sections=6, state="working"),
        dict(t="rug", u=-18.0, v=5.9), dict(t="rug", u=-26.6, v=6.0), dict(t="rug", u=-14.2, v=3.6),
        dict(t="cd_sign", u=-12.0 + T / 2, v=7.0, f="+u", z=1.9),
        dict(t="floorline", u0=-29.8, u1=-0.2, v=-1.05),
        dict(t="drain", u0=-29.8, u1=-4.4, v=0.6),
        dict(t="floortext", u=-8.1, v=0.95, text="VALVES"), dict(t="floortext", u=-8.1, v=-0.95, text="ENGINEERING"),
        dict(t="floortext", u=-18.0, v=0.95, text="COUNCIL"), dict(t="floortext", u=-27.0, v=0.95, text="ADMIN"),
        dict(t="floortext", u=-27.0, v=-0.95, text="RADIO"), dict(t="floortext", u=-2.2, v=-0.9, text="STAIRS L3"),
    ]
    D["inspect"] += [
        dict(id="manifold_a", u=-9.2, v=7.2, name="Valve manifold", text="Four wheels, chained and padlocked. Tags in three handwritings: PRIORITY - COMMAND, PRIORITY - CLINIC, GENERAL - L2 EAST, GENERAL - L1. The newest tag says COUNCIL ORDER: HALF TURN ONLY."),
        dict(id="manifold_b", u=-6.6, v=7.2, name="Valve manifold", text="Water treatment, the bays, Level 3. One wheel at the end has no tag at all and no chain. Its pipe runs up into the ceiling and east, towards the heating control room."),
        dict(id="toolboard", u=-4.6, v=-3.6, name="Tool board", text="Painted outlines of thirty tools. Seven are still there. The rest were traded, broken or taken to closed sections and never brought back."),
        dict(id="banner", u=-18.0, v=9.4, name="Banner", text="COUNCIL OF SILO 81, in gold thread on red wool that was a curtain once."),
        dict(id="silomap", u=-15.0, v=9.4, name="General plan", text="The founders' plan of the silo, four levels and the core. East of Command lies the main heating control room."),
        dict(id="admin_map", u=-27.0, v=9.2, name="Sector map & schematics", text="Annotated blueprints of Silo 81's water and heating loops. Red grease-pencil marks circle the primary heating regulator on Level 4 East."),
    ]
    D["stairs"] += [
        dict(id="stairs_up4", u=-0.45, v=0.8, to="L3", arrive=[-0.3, -0.6], name="Stairs up",
             text="Up to Level 3, life support."),
        dict(id="to_heating", u=-0.55, v=-0.2, to="L4E", arrive=[-3.0, 0.0], name="Heating control room",
             text="Through the heavy steel bulkhead into the main heating control room."),
        dict(id="to_surface_depot", u=-4.8, v=3.2, to="L1", arrive=[-2.6, 0.6], name="Surface transit lift",
             text="Freight and personnel lift ascending to Level 1, the Surface Transit Depot."),
    ]
    D["spawns"] = {"player": [-0.3, -0.6, 3], "worms": []}
    D["bounds"] = [-30.0, 0.0, -8.0, 10.0]
    D = widen(D, -1.5, 0.5, -0.95)               # 3.0 -> 3.5 m, the main spine of the command level
    # light: the warm levels. Warm base, work lamps in the valve gallery and engineering, the council
    # and Administration office lit with warm desk lighting
    D["light"] = dict(ambient=(1.03, 1.0, 0.95),
                      lamps=[(u, -0.25, 2.5, 3.2, "bulb") for u in (-8.0, -15.0, -22.0, -28.0)] +
                            [(-8.0, 4.7, 2.4, 3.6, "work"), (-8.0, -5.2, 2.4, 3.8, "work"), (-18.0, 5.7, 2.6, 4.6, "amber"),
                             (-26.6, 6.2, 2.3, 4.0, "amber"), (-28.2, 8.8, 2.0, 3.0, "desk"), (-27.0, -5.2, 2.4, 3.0, "bulb"),
                             (-22.0, -4.7, 2.3, 2.6, "bulb"), (-18.0, -4.7, 2.3, 2.6, "bulb"), (-14.0, -4.7, 2.3, 2.6, "bulb")])
    return D


def L4E():
    """Level 4 east of the core: the Heating Control Room.
    Large industrial heating machinery, massive insulated pipes, pressure gauges, temperature monitoring
    equipment, control panels, maintenance workstation, engineering notes/diagrams, emergency valves,
    visible steam leaks, and warm orange machinery illumination contrasted against cooler blue ambient lighting."""
    D = {"name": "Level 4 - Heating Control Room", "rooms": [], "walls": [], "doors": [], "props": [], "decor": [],
         "inspect": [], "stairs": [], "spawns": {}, "blocked": []}
    concrete = dict(rgb=(0.48, 0.47, 0.44), noise=0.18, noise_scale=3.0, tex="concrete_floor", ts=1.5)
    plant = dict(rgb=(0.40, 0.42, 0.41), noise=0.15, noise_scale=4, grating=((0.31, 0.33, 0.32), 0.5), tex="diamond_plate", ts=1.2)
    rust_concrete = dict(rgb=(0.46, 0.41, 0.36), noise=0.22, noise_scale=3.5, tex="concrete_floor", ts=1.4)
    D["rooms"] += [
        dict(id="heat_entry", name="Bulkhead vestibule", r=[-4.2, 0.0, -2.0, 2.0], floor=concrete),
        dict(id="heat_hall", name="Heating control room", r=[0.0, 14.0, -2.2, 5.5], floor=plant),
        dict(id="heat_bay", name="Control & maintenance bay", r=[0.0, 14.0, -5.5, -2.2], floor=rust_concrete),
    ]
    D["holes"] = []
    W = D["walls"]
    W += [
        # back walls (north and east faces), full height
        dict(a=(-4.2, 2.0), b=(0.0, 2.0), h=FULL, face="-v", mat="raw"),
        dict(a=(0.0, 2.0), b=(0.0, 5.5), h=FULL, face="+u", mat="machine"),
        dict(a=(0.0, 5.5), b=(14.0, 5.5), h=FULL, face="-v", mat="machine"),
        dict(a=(14.0, -5.5), b=(14.0, 5.5), h=FULL, face="-u", mat="raw"),
        # camera-side and west stub walls
        dict(a=(-4.2, -2.0), b=(-4.2, 2.0), h=STUB, mat="raw"),
        dict(a=(-4.2, -2.0), b=(0.0, -2.0), h=STUB, mat="raw"),
        dict(a=(0.0, -5.5), b=(0.0, -2.0), h=STUB, mat="machine"),
        dict(a=(0.0, -5.5), b=(14.0, -5.5), h=STUB, mat="machine"),
    ]
    P = D["props"]
    HN, HS, HE = 5.5 - T / 2, -5.5 + T / 2, 14.0 - T / 2
    P += [
        # Centrepiece: Main Heating Assembly & Primary Pressure Regulator
        dict(t="boiler_assembly", u=6.2, v=2.6, f="-v", id="main_heating_assembly", name="Main heating assembly",
             text="The primary heat exchanger and thermal pressure regulator. The vessel shudders under fluctuating load, and superheated steam jets from a fractured cast-iron regulator collar patched with sheared weld shims."),
        # Auxiliary circulation & bypass pumps
        dict(t="pump", u=2.0, v=4.3, f="-v", name="Primary circulation pump",
             text="Driving heated water up the main riser to the residential sections. Its casing is scorching hot and vibrating against its bolts."),
        dict(t="pump", u=11.4, v=4.3, f="-v", name="Bypass booster pump",
             text="Running continuously at emergency overload to compensate for the failing pressure regulator."),
        # Control panels & Temperature monitoring equipment along the south bay
        dict(t="control_panel", u=3.6, v=HS, f="+v", id="heating_control_panel", name="Heating control panel",
             text="Main heating control board. Output has been manually stepped up to 118% to fight residential heat loss, pinning the back-pressure gauges in the red."),
        dict(t="temp_monitor", u=6.4, v=HS, f="+v", id="temp_monitoring_unit", name="Temperature monitoring console",
             text="Paper strip-chart drum recorders and thermocouple displays. Every residential sector trace shows erratic sawtooth drops whenever the main regulator slips."),
        dict(t="stool", u=3.6, v=-3.9, f="-v"),
        dict(t="stool", u=6.4, v=-3.9, f="-v"),
        # Maintenance workstation, engineering notes, spare parts rack
        dict(t="workbench", u=9.8, v=HS, f="+v", id="heating_workstation", name="Maintenance workstation",
             text="Covered in sheared weld shims, cracked governor springs, callipers, and the engineering team's diagnostic logbook."),
        dict(t="toolbox", u=11.6, v=HS + 0.1, f="+v", name="Engineering tool kit",
             text="Brazing torches and heavy spanners left by the engineers after their latest attempt to stabilize the regulator."),
        dict(t="shelf", u=HE, v=-3.4, f="-u", id="spares_shelf", name="Engineering spares rack",
             text="Bins of salvaged gaskets and pipe unions. The compartment labelled 'PRIMARY REGULATOR CORE / GOVERNOR SEAT' is completely bare."),
        dict(t="crate", u=12.4, v=3.4, f="-u", name="Parts crate",
             text="Stencilled: SPARES - HEATING REGULATOR. Inside: only oil-soaked packing material and broken cast-iron fragments."),
        dict(t="locker", u=0.0 + T / 2, v=-3.8, f="+u", w=1.0, name="Crew lockers",
             text="Heat-resistant gauntlets, ear defenders, and a chalkboard tally of regulator blowouts over the past three weeks."),
    ]
    D["decor"] += [
        dict(t="steeldoor", u=-4.2 + T / 2, v=0.0, f="+u", label="COMMAND L4"),
        dict(t="steeldoor", u=HE, v=-1.45, f="-u", label="DEEP STORAGE L5"),
        dict(t="pipes", u0=0.4, u1=13.6, v=5.5),
        dict(t="manifold", u=9.2, v=HN, f="-v"),
        dict(t="manifold", u=HE, v=2.2, f="-u"),
        dict(t="gauge_bank", u=3.8, v=HN, f="-v", z=1.15),
        dict(t="gauge_bank", u=HE, v=0.2, f="-u", z=1.15),
        dict(t="steam_vent", u=7.1, v=2.2, f="-v"),
        dict(t="steam_vent", u=9.2, v=5.1, f="-v"),
        dict(t="puddle", u=7.0, v=1.0, ru=1.15, rv=0.75),
        dict(t="blackboard", u=HE, v=-3.4, f="-u", z=0.95, text="REGULATOR CORE FRACTURED - 0 SPARES"),
        dict(t="silomap", u=1.4, v=HN, f="-v", z=1.05),
        dict(t="noticeboard", u=0.0 + T / 2, v=3.6, f="+u", z=1.05, title="HEATING SHIFT LOG"),
        dict(t="switchboard", u=1.8, v=HS, f="+v", z=0.95),
        dict(t="stencil", u=6.2, v=HN, f="-v", z=2.45, text="PRIMARY HEAT EXCHANGER & REGULATOR", size=0.12),
        dict(t="floorline", u0=0.4, u1=13.4, v=0.45),
        dict(t="floorline", u0=1.2, u1=12.6, v=-2.2),
        dict(t="drain", u0=0.8, u1=13.2, v=0.95),
        dict(t="floortext", u=6.2, v=-0.1, text="MAIN REGULATOR"),
        dict(t="floortext", u=5.0, v=-1.6, text="CONTROL"),
        dict(t="floortext", u=9.8, v=-1.6, text="WORKSTATION"),
    ]
    D["inspect"] += [
        dict(id="main_heating_assembly", u=6.2, v=1.35, kind="heating_assembly", name="Main heating assembly",
             text="Inspect the main heating assembly, heat exchanger drum, and pressure gauges."),
        dict(id="regulator_leak", u=7.25, v=1.35, kind="heating_instability", name="Fractured pressure regulator",
             text="Examine the source of instability in the primary thermal pressure regulator."),
        dict(id="eng_notes", u=9.8, v=-4.1, kind="heating_instability", name="Engineering notes & spares log",
             text="Read the engineering team's diagnostic schematics and spare-parts inventory."),
        dict(id="heating_control_panel", u=3.6, v=-4.1, kind="heating_assembly", name="Heating control panel",
             text="Inspect the main heating control board and output compensators."),
        dict(id="temp_monitoring_unit", u=6.4, v=-4.1, kind="heating_assembly", name="Temperature monitoring console",
             text="Check the residential temperature strip-charts and pressure telemetry."),
        dict(id="emergency_valves", u=9.2, v=4.7, name="Emergency relief valves",
             text="Three chained emergency relief wheels. Steam feathers continuously from the bypass packing nut; a wired tag reads: DO NOT CLOSE - REGULATOR SURGING."),
        dict(id="pressure_gauges", u=3.8, v=4.7, name="Pressure gauge bank",
             text="Four brass-rimmed manometers. Primary bore loop sits at 4.9 bar; residential supply swings wildly between 1.2 and 4.6 bar every few seconds."),
    ]
    D["stairs"] += [
        dict(id="to_command", u=-3.6, v=0.0, to="L4W", arrive=[-1.2, -0.2], name="Command corridor",
             text="Back through the blast bulkhead to Level 4 Command."),
        dict(id="to_deep_storage", u=13.3, v=-1.45, to="L5", arrive=[-1.8, 0.2], name="Sub-Level 4 - Deep Storage",
             text="Through the east bulkhead down to Sub-Level 4: the Geothermal Bore Ring, Deep Storage Vault, and Founders' Technical Archive."),
    ]
    D["spawns"] = {"player": [-3.0, 0.0, 0], "worms": []}
    D["bounds"] = [-4.2, 14.0, -5.5, 5.5]
    # Contrast warm orange machinery illumination ("furnace", "amber", "work") against cooler blue ambient/corners ("cold")
    D["light"] = dict(ambient=(0.88, 0.94, 1.04),
                      lamps=[(5.5, 1.8, 1.35, 4.4, "furnace"), (7.1, 1.8, 1.35, 4.0, "furnace"),
                             (6.2, 0.4, 2.3, 4.2, "amber"), (3.6, -3.8, 2.2, 3.4, "amber"),
                             (6.4, -3.8, 2.2, 3.2, "work"), (9.8, -3.8, 2.2, 3.8, "amber"),
                             (0.8, 4.4, 2.2, 3.8, "cold"), (12.8, 4.4, 2.2, 3.8, "cold"),
                             (-2.6, 0.0, 2.2, 3.4, "cold"), (12.8, -1.2, 2.2, 3.0, "cold")])
    return D


def L5():
    """Sub-Level 4 (Level 5): Deep Storage & Geothermal Bore Ring.
    Explorable multi-room underground ring beneath Heating Control with zero enemies and zero puzzles:
    1) Service Bulkhead Vestibule (deep_entry)
    2) Sub-Level 4 Main Spine (corridor5, 3.6 m wide)
    3) Geothermal Borehead & Primary Exchanger Pit (geotherm_hall, north-west)
    4) Engineering Deep Storage Vault (deep_stores, north-east)
    5) Bore-Water Settling & Filtration Bay (filtration, south-west)
    6) Founders' Technical Vault & Blueprint Room (core_archive, south-east)"""
    D = {"name": "Sub-Level 4 - Deep Storage & Geotherm Ring", "rooms": [], "walls": [], "doors": [], "props": [],
         "decor": [], "inspect": [], "stairs": [], "spawns": {}, "blocked": []}
    concrete = dict(rgb=(0.48, 0.47, 0.44), noise=0.18, noise_scale=3.0, tex="concrete_floor", ts=1.5)
    plant = dict(rgb=(0.40, 0.42, 0.41), noise=0.15, noise_scale=4, grating=((0.31, 0.33, 0.32), 0.5), tex="diamond_plate", ts=1.2)
    rust_concrete = dict(rgb=(0.46, 0.41, 0.36), noise=0.22, noise_scale=3.5, tex="concrete_floor", ts=1.4)
    parquet = dict(rgb=(0.46, 0.32, 0.2), noise=0.14, noise_scale=8, grating=((0.38, 0.26, 0.16), 0.4), tex="parquet", ts=1.6)
    D["rooms"] += [
        dict(id="deep_entry", name="Service bulkhead vestibule", r=[-3.6, 0.0, -1.8, 1.8], floor=concrete),
        dict(id="corridor5", name="Sub-Level 4 main spine", r=[0.0, 22.0, -1.8, 1.8], floor=concrete),
        dict(id="geotherm_hall", name="Geothermal borehead pit", r=[0.0, 12.0, 1.8, 8.5], floor=plant),
        dict(id="deep_stores", name="Engineering deep storage vault", r=[12.0, 22.0, 1.8, 8.5], floor=rust_concrete),
        dict(id="filtration", name="Bore-water filtration bay", r=[0.0, 11.0, -7.5, -1.8], floor=concrete),
        dict(id="core_archive", name="Founders' technical vault", r=[11.0, 22.0, -7.5, -1.8], floor=parquet),
    ]
    D["holes"] = []
    W = D["walls"]
    W += [
        # Back walls (north +v and east +u outer perimeter), full height
        dict(a=(-3.6, 1.8), b=(0.0, 1.8), h=FULL, face="-v", mat="raw"),
        dict(a=(0.0, 1.8), b=(0.0, 8.5), h=FULL, face="+u", mat="machine"),
        dict(a=(0.0, 8.5), b=(12.0, 8.5), h=FULL, face="-v", mat="machine"),
        dict(a=(12.0, 8.5), b=(22.0, 8.5), h=FULL, face="-v", mat="raw"),
        dict(a=(22.0, 1.8), b=(22.0, 8.5), h=FULL, face="-u", mat="raw"),
        dict(a=(22.0, -1.8), b=(22.0, 1.8), h=FULL, face="-u", mat="raw"),
        dict(a=(22.0, -7.5), b=(22.0, -1.8), h=FULL, face="-u", mat="panel"),
        # Camera-facing and interior partition walls (h=STUB for room-based foreground wall fade)
        dict(a=(-3.6, -1.8), b=(-3.6, 1.8), h=STUB, mat="raw"),
        dict(a=(-3.6, -1.8), b=(0.0, -1.8), h=STUB, mat="raw"),
        dict(a=(0.0, 1.8), b=(22.0, 1.8), h=STUB, mat="machine",
             openings=[(4.5, 6.5, None), (15.85, 17.15, "door_stores")]),
        dict(a=(12.0, 1.8), b=(12.0, 8.5), h=STUB, mat="raw"),
        dict(a=(0.0, -1.8), b=(22.0, -1.8), h=STUB, mat="raw",
             openings=[(4.8, 6.2, None), (15.85, 17.15, "door_vault")]),
        dict(a=(0.0, -7.5), b=(0.0, -1.8), h=STUB, mat="raw"),
        dict(a=(0.0, -7.5), b=(11.0, -7.5), h=STUB, mat="raw"),
        dict(a=(11.0, -7.5), b=(11.0, -1.8), h=STUB, mat="panel"),
        dict(a=(11.0, -7.5), b=(22.0, -7.5), h=STUB, mat="panel"),
    ]
    D["doors"] += [
        dict(id="door_stores", kind="steel", label="STORES", u=16.5, v=1.8, axis="u", open=False, locked=False,
             name="Deep storage vault door", text="Heavy steel vault door stencilled: ENGINEERING DEEP STORES - HEAVY CASTINGS."),
        dict(id="door_vault", kind="steel", label="VAULT", u=16.5, v=-1.8, axis="u", open=False, locked=False,
             name="Technical archive door", text="Reinforced steel door to the Founders' Technical Vault and survey room."),
    ]
    P = D["props"]
    GN, SE, VS = 8.5 - T / 2, 22.0 - T / 2, -7.5 + T / 2
    # 1) Geothermal Borehead & Primary Exchanger Pit (north-west)
    P += [
        dict(t="boiler_assembly", u=6.0, v=5.8, f="-v", name="Geothermal borehead manifold",
             text="The deep geothermal borehead where superheated brine rises from six hundred metres below the valley floor before feeding Level 4's heat exchanger."),
        dict(t="pump", u=2.0, v=7.1, f="-v", name="Bore injection pump",
             text="High-pressure return pump forcing cooled brine back down the return bore. Its foundation bolts are crusted with white mineral scale."),
        dict(t="pump", u=10.0, v=7.1, f="-v", name="Primary geothermal lift pump",
             text="Drawing superheated water from the primary wellhead up to the Level 4 heating room."),
        dict(t="control_panel", u=2.4, v=2.4, f="+v", name="Borehead telemetry panel",
             text="Deep-well temperature and pressure gauges. The geothermal source itself is steady at 142 C; all the pressure fluctuations originate above, in the fractured Level 4 regulator."),
        dict(t="temp_monitor", u=9.6, v=2.4, f="+v", name="Seismic & thermal recorder",
             text="Drum chart recording deep-bore temperature over the past year. The well is healthy; the silo's surface-cast regulator hardware is what is failing."),
    ]
    # 2) Engineering Deep Storage Vault (north-east)
    P += [
        dict(t="shelf", u=14.2, v=GN, f="-v", name="Heavy spares rack A",
             text="Steel racking for primary heating valves and governor assemblies. Every cradle for the main regulator castings is empty, tagged 'ISSUED 1974' and 'ISSUED 1981'."),
        dict(t="shelf", u=18.2, v=GN, f="-v", name="Heavy spares rack B",
             text="Contains only small domestic radiator valves and perished rubber O-rings. No high-pressure regulator parts remain."),
        dict(t="shelf", u=SE, v=5.8, f="-u", name="Pipe & flange rack",
             text="Lengths of low-pressure steel pipe salvaged from closed dormitory branches."),
        dict(t="workbench", u=19.8, v=2.5, f="+v", name="Vault inventory bench",
             text="The master spare-parts ledger lies open. Under 'REGULATOR CORE / GOVERNOR SEAT (CLASS IV)', someone has written: STOCK EXHAUSTED. ORIGINAL FOUNDRY: INDUSTRIAL SECTOR 4, SURFACE CITY."),
        dict(t="lathe", u=13.6, v=5.2, f="+u", name="Heavy milling stand",
             text="An old boring mill used to re-face worn valve seats. A cracked regulator casting sits clamped in the chuck, split clean through the bolt ring."),
        dict(t="crate", u=20.6, v=7.2, f="-u", name="Crate",
             text="Stencilled: VULCAN FOUNDRY - BISTRITA MUNICIPAL WORKS, 1950. Empty save for oiled straw."),
        dict(t="crate", u=20.6, v=6.3, f="-u"),
        dict(t="locker", u=12.0 + T / 2, v=3.4, f="+u", w=1.0, name="Vault tool locker",
             text="Heavy chain hoists, micrometer gauges, and lead seals."),
    ]
    # 3) Bore-Water Settling & Filtration Bay (south-west)
    P += [
        dict(t="pump", u=3.0, v=-5.8, f="+v", name="Mineral separator pump",
             text="Flushes silica and sulfur sediment out of the geothermal loop before it can foul the Level 3 and Level 4 risers."),
        dict(t="pump", u=8.0, v=-5.8, f="+v", name="Filter backwash pump",
             text="Standby filtration pump humming quietly on the secondary bus."),
        dict(t="sinks", u=11.0 - T / 2, v=-4.6, f="-u", n=2, name="Water chemistry test sink",
             text="Glass titration flasks and pH strips for testing bore-water mineral content."),
        dict(t="workbench", u=2.4, v=-2.5, f="-v", name="Filtration log bench",
             text="Filter mesh samples laid out on blotting paper, dated by week."),
        dict(t="crate", u=1.0, v=-6.6, f="+u", name="Filter media crate",
             text="Sacks of graded quartz sand and charcoal for the settling tanks."),
    ]
    # 4) Founders' Technical Vault & Blueprint Room (south-east)
    P += [
        dict(t="maptable", u=16.5, v=-4.8, f="+v", name="Regional infrastructure map table",
             text="A large blueprint of the valley connecting Silo 81's surface transit depot to the municipal industrial foundry in the city twelve kilometres north."),
        dict(t="terminal", u=13.4, v=VS, f="+v", name="Founders' construction terminal",
             text="Offline construction database. Its magnetic tape directory lists original supplier manifests for every major machine in Silo 81."),
        dict(t="monitors", u=19.2, v=VS, f="+v", name="Core loop schematic display",
             text="Static backlit diagram of the Sub-Level 4 geothermal loop and surface freight shaft."),
        dict(t="files", u=SE, v=-3.4, f="-u", k=0, name="Supplier manifests",
             text="Binders titled: HEAVY THERMAL REGULATORS - MUNICIPAL FOUNDRY & RAIL DEPOT RESERVES."),
        dict(t="files", u=SE, v=-5.6, f="-u", k=2, name="Construction blueprints",
             text="Original 1951 engineering drawings for the Level 4 heating assembly and the Level 1 surface rail spur."),
        dict(t="safe", u=11.0 + T / 2, v=-6.2, f="+u", name="Founders' vault safe",
             text="Heavy steel safe containing master calibration certificates and surface transit keycodes."),
        dict(t="desk", u=13.6, v=-3.3, f="+u", name="Archivist's desk",
             text="Pencilled notes comparing the fractured Level 4 regulator dimensions against the spare units listed at the city rail foundry."),
        dict(t="chair", u=14.4, v=-3.3, f="-u"),
        dict(t="floorlamp", u=20.8, v=-6.6, f="+v"),
    ]
    D["decor"] += [
        dict(t="steeldoor", u=-1.8, v=1.8 - T / 2, f="-v", label="HEATING CONTROL L4"),
        dict(t="steeldoor", u=SE, v=0.0, f="-u", label="SURFACE LIFT L1"),
        dict(t="pipes", u0=0.4, u1=11.6, v=8.5),
        dict(t="manifold", u=3.6, v=GN, f="-v"),
        dict(t="manifold", u=8.8, v=GN, f="-v"),
        dict(t="gauge_bank", u=6.0, v=GN, f="-v", z=1.15),
        dict(t="steam_vent", u=5.2, v=5.2, f="-v"),
        dict(t="puddle", u=5.8, v=3.8, ru=1.0, rv=0.65),
        dict(t="puddle", u=5.5, v=-4.2, ru=1.1, rv=0.7),
        dict(t="blackboard", u=16.2, v=GN, f="-v", z=0.95, text="CLASS IV REGULATORS: 0 IN SILO"),
        dict(t="silomap", u=16.5, v=8.5 - T / 2, f="-v", z=1.05),
        dict(t="toolboard", u=SE, v=3.6, f="-u", z=1.0),
        dict(t="noticeboard", u=12.0 + T / 2, v=6.2, f="+u", z=1.05, title="DEEP STORES LEDGER"),
        dict(t="switchboard", u=0.0 + T / 2, v=4.2, f="+u", z=0.95),
        dict(t="stencil", u=6.0, v=GN, f="-v", z=2.45, text="GEOTHERMAL BOREHEAD - 600M", size=0.12),
        dict(t="stencil", u=17.0, v=GN, f="-v", z=2.45, text="ENGINEERING DEEP STORAGE", size=0.12),
        dict(t="rug", u=16.5, v=-4.8),
        dict(t="floorline", u0=-3.2, u1=21.4, v=0.85),
        dict(t="floorline", u0=-3.2, u1=21.4, v=-0.85),
        dict(t="drain", u0=0.4, u1=21.2, v=0.0),
        dict(t="floortext", u=5.5, v=1.1, text="GEOTHERM BORE"),
        dict(t="floortext", u=16.5, v=1.1, text="DEEP STORES"),
        dict(t="floortext", u=5.5, v=-1.1, text="FILTRATION"),
        dict(t="floortext", u=16.5, v=-1.1, text="TECH VAULT"),
        dict(t="floortext", u=19.8, v=0.0, text="LIFT L1 >"),
    ]
    D["inspect"] += [
        dict(id="borehead_inspect", u=6.0, v=4.4, name="Geothermal borehead",
             text="Deep geothermal intake pipes bringing 142 C water from the bedrock. The heat source is strong and steady — proving the silo's heating crisis is purely mechanical."),
        dict(id="stores_ledger", u=19.8, v=3.2, name="Master spare-parts ledger",
             text="Every Class IV pressure regulator casting stored in Silo 81 was used up decades ago. The ledger notes that spare assemblies were manufactured and warehoused at the surface city's municipal rail foundry."),
        dict(id="regional_map", u=16.5, v=-3.8, name="Valley transit & foundry blueprint",
             text="Shows the industrial rail spur linking Silo 81's Level 1 Surface Transit Depot directly to the city foundry warehouse."),
    ]
    D["stairs"] += [
        dict(id="to_heating_from_l5", u=-1.8, v=1.0, to="L4E", arrive=[12.6, -1.45], name="Heating Control Room (L4)",
             text="Up the service stair to the Level 4 Heating Control Room."),
        dict(id="to_surface_from_l5", u=21.2, v=0.0, to="L1", arrive=[0.0, 0.6], name="Surface Transit Depot (L1)",
             text="Take the heavy freight lift up to Level 1: the Surface Transit Depot and Frozen Switchyard."),
    ]
    D["spawns"] = {"player": [-1.8, 0.2, 0], "worms": []}
    D["bounds"] = [-3.6, 22.0, -7.5, 8.5]
    D["light"] = dict(ambient=(0.90, 0.95, 1.02),
                      lamps=[(5.0, 5.2, 1.6, 4.4, "furnace"), (7.2, 5.2, 1.6, 4.0, "furnace"),
                             (2.4, 3.0, 2.3, 3.4, "amber"), (9.6, 3.0, 2.3, 3.4, "work"),
                             (4.0, 0.0, 2.5, 3.4, "bulb"), (11.0, 0.0, 2.5, 3.4, "bulb"), (18.0, 0.0, 2.5, 3.4, "bulb"),
                             (15.5, 5.2, 2.4, 3.8, "work"), (19.8, 3.2, 2.3, 3.4, "amber"),
                             (5.5, -4.6, 2.3, 3.8, "cold"), (2.4, -3.0, 2.3, 3.0, "work"),
                             (16.5, -4.8, 2.4, 4.2, "amber"), (-1.8, 0.0, 2.3, 3.2, "cold")])
    return D


def L1():
    """Level 1: Surface Egress & Frozen Transit Depot.
    Explorable threshold sector at the top of Silo 81 with zero enemies and zero puzzles:
    1) Surface Airlock & Decontamination Vestibule (airlock, west)
    2) Covered Loading Platform & Transit Spine (depot_spine, centre)
    3) Surface Watchpost & Dispatch Office (guardhouse, north-west)
    4) Frozen Rail Switchyard & Cargo Bay (switchyard, north-east)
    5) Expedition Gear & Ration Store (ration_store, south-west)
    6) Field Triage & Decontamination Ward (triage_bay, south-east)"""
    D = {"name": "Level 1 - Surface Transit Depot", "rooms": [], "walls": [], "doors": [], "props": [],
         "decor": [], "inspect": [], "stairs": [], "spawns": {}, "blocked": []}
    concrete = dict(rgb=(0.50, 0.51, 0.52), noise=0.18, noise_scale=3.0, tex="concrete_floor", ts=1.5)
    plant = dict(rgb=(0.40, 0.42, 0.43), noise=0.15, noise_scale=4, grating=((0.31, 0.33, 0.34), 0.5), tex="diamond_plate", ts=1.2)
    lino = dict(rgb=(0.45, 0.33, 0.27), noise=0.12, noise_scale=6, grating=((0.38, 0.27, 0.22), 0.6), tex="lino", ts=1.6)
    frost_concrete = dict(rgb=(0.56, 0.60, 0.65), noise=0.22, noise_scale=3.5, tex="concrete_floor", ts=1.4)
    wood = dict(rgb=(0.47, 0.36, 0.25), noise=0.15, noise_scale=8, tex="wood_planks", ts=2.4)
    clinic = dict(rgb=(0.62, 0.68, 0.64), noise=0.06, noise_scale=20, grating=((0.52, 0.58, 0.55), 0.4), tex="tile_clinic", ts=1.2)
    D["rooms"] += [
        dict(id="airlock", name="Surface lift airlock", r=[-4.2, 1.5, -2.2, 2.2], floor=plant),
        dict(id="depot_spine", name="Covered loading platform", r=[1.5, 20.0, -1.8, 1.8], floor=concrete),
        dict(id="guardhouse", name="Surface watchpost & dispatch", r=[1.5, 10.0, 1.8, 7.8], floor=lino),
        dict(id="switchyard", name="Frozen rail switchyard bay", r=[10.0, 20.0, 1.8, 8.6], floor=frost_concrete),
        dict(id="ration_store", name="Expedition gear & ration store", r=[1.5, 10.5, -7.2, -1.8], floor=wood),
        dict(id="triage_bay", name="Field decontamination & triage", r=[10.5, 20.0, -7.2, -1.8], floor=clinic),
    ]
    D["holes"] = []
    W = D["walls"]
    W += [
        # Back walls (north +v and east +u outer perimeter), full height
        dict(a=(-4.2, 2.2), b=(1.5, 2.2), h=FULL, face="-v", mat="machine"),
        dict(a=(1.5, 2.2), b=(1.5, 7.8), h=FULL, face="+u", mat="panel"),
        dict(a=(1.5, 7.8), b=(10.0, 7.8), h=FULL, face="-v", mat="panel"),
        dict(a=(10.0, 7.8), b=(10.0, 8.6), h=FULL, face="+u", mat="raw"),
        dict(a=(10.0, 8.6), b=(20.0, 8.6), h=FULL, face="-v", mat="raw"),
        dict(a=(20.0, 1.8), b=(20.0, 8.6), h=FULL, face="-u", mat="raw"),
        dict(a=(20.0, -1.8), b=(20.0, 1.8), h=FULL, face="-u", mat="raw"),
        dict(a=(20.0, -7.2), b=(20.0, -1.8), h=FULL, face="-u", mat="tile"),
        # Camera-facing and interior partition walls (h=STUB for room-based foreground wall fade)
        dict(a=(-4.2, -2.2), b=(-4.2, 2.2), h=STUB, mat="machine"),
        dict(a=(-4.2, -2.2), b=(1.5, -2.2), h=STUB, mat="machine"),
        dict(a=(1.5, -2.2), b=(1.5, 2.2), h=STUB, mat="machine", openings=[(-0.9, 0.9, None)]),
        dict(a=(1.5, 1.8), b=(20.0, 1.8), h=STUB, mat="raw",
             openings=[(4.85, 6.15, "door_guard"), (13.8, 16.2, None)]),
        dict(a=(10.0, 1.8), b=(10.0, 7.8), h=STUB, mat="raw"),
        dict(a=(1.5, -1.8), b=(20.0, -1.8), h=STUB, mat="raw",
             openings=[(5.35, 6.65, "door_expedition"), (14.35, 15.65, "door_triage")]),
        dict(a=(1.5, -7.2), b=(1.5, -1.8), h=STUB, mat="raw"),
        dict(a=(1.5, -7.2), b=(10.5, -7.2), h=STUB, mat="raw"),
        dict(a=(10.5, -7.2), b=(10.5, -1.8), h=STUB, mat="tile"),
        dict(a=(10.5, -7.2), b=(20.0, -7.2), h=STUB, mat="tile"),
    ]
    D["doors"] += [
        dict(id="door_guard", kind="steel", label="DISPATCH", u=5.5, v=1.8, axis="u", open=True, locked=False,
             name="Surface dispatch door", text="Insulated steel door to the Surface Watchpost and Dispatch Office."),
        dict(id="door_expedition", kind="steel", label="GEAR", u=6.0, v=-1.8, axis="u", open=False, locked=False,
             name="Expedition gear store", text="Quartermaster's heavy door stencilled: SURFACE EXPEDITION GEAR & RATIONS."),
        dict(id="door_triage", kind="plywood", u=15.0, v=-1.8, axis="u", open=False, locked=False,
             name="Field triage ward", text="Decontamination and cold-exposure triage room."),
    ]
    P = D["props"]
    GN, SN, SE, RS = 7.8 - T / 2, 8.6 - T / 2, 20.0 - T / 2, -7.2 + T / 2
    # 1) Surface Lift Airlock (west)
    P += [
        dict(t="sinks", u=-4.2 + T / 2, v=-0.6, f="+u", n=2, name="Decontamination washbasins",
             text="Dry. The drain traps are packed with rock salt to stop them freezing solid."),
        dict(t="locker", u=-1.5, v=-2.2 + T / 2, f="+v", w=1.0, name="Airlock suit lockers",
             text="Heavy canvas greatcoats, frost goggles, and spare respirator canisters."),
    ]
    # 2) Surface Watchpost & Dispatch Office (north-west)
    P += [
        dict(t="desk", u=4.2, v=5.4, f="-v", name="Dispatch officer's desk",
             text="Surface weather logs and rail switchyard manifests. A brass barometer sits beside a mug of cold chicory."),
        dict(t="chair", u=4.2, v=6.2, f="-v"),
        dict(t="radioset", u=2.8, v=GN, f="-v", name="Surface beacon transceiver",
             text="Shortwave line-of-sight transceiver aimed down the valley toward the city rail terminus."),
        dict(t="terminal", u=6.2, v=GN, f="-v", name="Switchyard control terminal",
             text="Displays the track diagram for the covered rail spur between Silo 81 and the municipal industrial foundry."),
        dict(t="monitors", u=8.4, v=GN, f="-v", name="Exterior camera monitors",
             text="Grainy black-and-white feeds of the snow-buried blast gates and the frozen rail cutting outside."),
        dict(t="stove", u=10.0 - T / 2, v=4.2, f="-u", name="Watchpost stove",
             text="A small cast-iron stove keeping the dispatch office livable against the sub-zero draft from the switchyard."),
        dict(t="safe", u=1.5 + T / 2, v=6.2, f="+u", name="Dispatch safe",
             text="Contains surface gate logs and emergency flare cartridges."),
    ]
    # 3) Frozen Rail Switchyard & Cargo Bay (north-east)
    P += [
        dict(t="boiler_assembly", u=15.0, v=6.0, f="-v", name="Armoured thermal freight car",
             text="A heavy narrow-gauge rail tender coupled to the depot buffer stop, built to haul heavy foundry castings through the valley snow."),
        dict(t="control_panel", u=11.6, v=SN, f="-v", name="Blast-gate winch console",
             text="Hydraulic winch controls for the outer snow-shed doors leading toward the city rail line."),
        dict(t="crate", u=SE, v=6.8, f="-u", name="Cargo crate",
             text="Stencilled: SILO 81 SURFACE DEPOT - OUTBOUND SALVAGE."),
        dict(t="crate", u=SE, v=5.8, f="-u"),
        dict(t="sacks", u=11.2, v=3.0, f="+u", name="Road-salt sacks",
             text="Coarse rock salt for clearing ice from the switchyard points."),
    ]
    # 4) Expedition Gear & Ration Store (south-west)
    P += [
        dict(t="shelf", u=3.2, v=RS, f="+v", name="Cold-weather gear rack",
             text="Fleece-lined parkas, snowshoes, ice axes, andinsulated battery packs."),
        dict(t="workbench", u=6.0, v=RS, f="+v", name="Equipment maintenance bench",
             text="Ski bindings, lantern mantles, and a map of the surface highway with shelter huts marked in red pencil."),
        dict(t="shelf", u=8.8, v=RS, f="+v", name="Field ration shelf",
             text="Tins of Pemmican, compressed biscuit, and solid fuel tablets for surface work parties."),
        dict(t="toolbox", u=1.5 + T / 2, v=-4.5, f="+u", name="Field repair kit",
             text="Portable rivet gun, wire cutters, and flare pistol."),
        dict(t="locker", u=10.5 - T / 2, v=-4.2, f="-u", w=1.0, name="Expedition lockers",
             text="Numbered kit lockers for the surface maintenance crew."),
    ]
    # 5) Field Triage & Decontamination Ward (south-east)
    P += [
        dict(t="bed", u=12.6, v=RS, f="+v", k=1, name="Warming cot",
             text="Rigged with heated blankets for surface lookouts returning with frostbite."),
        dict(t="bed", u=16.8, v=RS, f="+v", k=3, name="Triage cot",
             text="Wool blankets folded neatly at the foot."),
        dict(t="medscreen", u=14.7, v=-5.6, f="+v", name="Privacy screen",
             text="Canvas medical screen."),
        dict(t="medcab", u=10.5 + T / 2, v=-3.4, f="+u", name="First-aid cabinet",
             text=" Frostbite salve, camphor spirits, and splints."),
        dict(t="desk", u=SE, v=-3.6, f="-u", name="Medical log desk",
             text="Logbook recording surface exposure times and wind-chill readings."),
        dict(t="chair", u=18.4, v=-3.6, f="+u"),
    ]
    D["decor"] += [
        dict(t="steeldoor", u=-2.6, v=2.2 - T / 2, f="-v", label="COMMAND LIFT L4"),
        dict(t="steeldoor", u=0.0, v=2.2 - T / 2, f="-v", label="FREIGHT LIFT L5"),
        dict(t="steeldoor", u=SE, v=4.4, f="-u", label="CITY RAIL SPUR"),
        dict(t="radiator", u=12.4, v=SN, f="-v", sections=10, state="dead"),
        dict(t="radiator", u=18.0, v=SN, f="-v", sections=10, state="dead"),
        dict(t="radiator", u=5.2, v=GN, f="-v", sections=8, state="working"),
        dict(t="silomap", u=4.2, v=GN, f="-v", z=1.05),
        dict(t="noticeboard", u=1.5 + T / 2, v=4.2, f="+u", z=1.05, title="SURFACE WEATHER LOG"),
        dict(t="switchboard", u=-4.2 + T / 2, v=1.0, f="+u", z=0.95),
        dict(t="redcross", u=12.4, v=-1.8 - T / 2, f="-v", z=1.7),
        dict(t="cd_sign", u=SE, v=0.0, f="-u", z=1.9),
        dict(t="stencil", u=5.8, v=GN, f="-v", z=2.45, text="LEVEL 1 - SURFACE DISPATCH", size=0.12),
        dict(t="stencil", u=15.0, v=SN, f="-v", z=2.45, text="TRANSIT DEPOT - CITY RAIL SPUR", size=0.12),
        dict(t="puddle", u=14.8, v=3.6, ru=1.1, rv=0.65),
        dict(t="rug", u=4.2, v=5.0),
        dict(t="floorline", u0=1.8, u1=19.4, v=0.85),
        dict(t="floorline", u0=1.8, u1=19.4, v=-0.85),
        dict(t="drain", u0=-3.8, u1=19.4, v=0.0),
        dict(t="floortext", u=-1.5, v=-0.9, text="AIRLOCK"),
        dict(t="floortext", u=5.5, v=1.1, text="DISPATCH"),
        dict(t="floortext", u=15.0, v=1.1, text="SWITCHYARD"),
        dict(t="floortext", u=6.0, v=-1.1, text="GEAR STORE"),
        dict(t="floortext", u=15.0, v=-1.1, text="TRIAGE"),
    ]
    D["inspect"] += [
        dict(id="surface_monitors", u=8.4, v=6.8, name="Exterior snow-shed cameras",
             text="The cameras show the armoured rail cutting leading out of the mountain toward the distant city. Heavy snow blankets the tracks, but the tunnel structure is intact."),
        dict(id="freight_car_inspect", u=15.0, v=4.6, name="Armoured rail tender",
             text="Built to transport multi-ton foundry castings between the city works and Silo 81. Its coupling latches are greased and ready under a rime of frost."),
        dict(id="city_spur_gate", u=19.2, v=4.4, name="Outer rail bulkhead",
             text="Sealed against the blizzard outside. Stencilled above the wheel: MUNICIPAL INDUSTRIAL SECTOR - 12 KM."),
    ]
    D["stairs"] += [
        dict(id="to_l4w_from_l1", u=-2.6, v=1.3, to="L4W", arrive=[-4.9, 3.2], name="Command Lift (L4)",
             text="Descend via the personnel lift to Level 4 Command (Valve Gallery)."),
        dict(id="to_l5_from_l1", u=0.0, v=1.3, to="L5", arrive=[20.8, 0.0], name="Freight Lift (Sub-Level 4)",
             text="Descend via the heavy freight lift to Sub-Level 4: Deep Storage & Geotherm Ring."),
        dict(id="to_jt_from_l1", u=-2.6, v=-1.4, to="RD", arrive=[4.5, 8.2], name="Surface portal: the road to Junk Town",
             text="The surface blast gate opens onto the snow road east, toward Junk Town."),
    ]
    D["spawns"] = {"player": [-2.6, 0.6, 0], "worms": []}
    D["bounds"] = [-4.2, 20.0, -7.2, 8.6]
    D["light"] = dict(ambient=(0.86, 0.93, 1.05),
                      lamps=[(-1.4, 0.0, 2.4, 3.6, "work"),
                             (4.2, 5.4, 2.3, 4.0, "amber"), (8.4, 5.4, 2.3, 3.4, "work"),
                             (5.0, 0.0, 2.5, 3.4, "bulb"), (11.5, 0.0, 2.5, 3.4, "bulb"), (17.5, 0.0, 2.5, 3.4, "bulb"),
                             (15.0, 2.8, 2.4, 3.8, "work"), (13.0, 6.8, 2.2, 4.2, "cold"), (18.2, 6.8, 2.2, 4.2, "cold"),
                             (6.0, -4.6, 2.4, 3.6, "bulb"), (15.0, -4.6, 2.4, 3.6, "bulb"), (18.5, -5.8, 2.2, 3.2, "cold")])
    return D


def RD():
    """The road from Silo 81 to Junk Town (docs/LEVEL_ROAD_TO_JUNK_TOWN.md), one continuous outdoor level.
    u runs east along the road (screen up-right), v north (screen up-left); the camera looks from the south-west,
    so tall things stand on the far (north / east) sides and the near (south / west) sides stay low.
      A  u  -2..22  Silo portal in the hillside, security remains, car graveyard
      B  u  22..50  leaning pylon, the first Changed at a stalled car, red trailer, rest stop (optional, north)
      C  u  50..64  billboard, scrapyard, graves, the gate fight (wall guards help after two rounds)
      JT u  64..92  Junk Town: a ring of wrecked vans, cars and fences round a yard of shacks and stalls"""
    D = {"name": "The Road to Junk Town", "rooms": [], "walls": [], "doors": [], "props": [], "decor": [],
         "inspect": [], "stairs": [], "spawns": {}, "blocked": [], "holes": [], "terrain": [], "mounds": []}
    # the ground is drawn by Godot from tiling textures (tools/design/ground_textures.py)
    snow = dict(tex="snow")
    snow_far = dict(tex="snow", tint=(1.02, 1.02, 1.02))
    asphalt = dict(tex="asphalt")
    concrete = dict(tex="concrete")
    forecourt = dict(tex="concrete", tint=(0.94, 0.94, 0.95))
    yard = dict(tex="yard")
    D["godot_ground"] = True
    D["max_zoom"] = 0.85
    D["sprite_scale"] = 0.62
    D["rooms"] += [
        dict(id="rd_apron", name="Silo 81 surface portal", r=[-1.0, 10.0, 3.0, 9.7], floor=concrete, layer=2),
        dict(id="rd_road", name="The road east", r=[-2.0, 64.0, -3.0, 3.0], floor=asphalt, layer=2),
        dict(id="rd_reststop", name="Rest stop", r=[36.0, 51.0, 3.0, 9.4], floor=forecourt, layer=2),
        dict(id="rd_west", name="Snowfield", r=[-2.0, 24.0, -12.0, 12.0], floor=snow),
        dict(id="rd_mid", name="Snowfield", r=[24.0, 50.0, -12.0, 12.5], floor=snow),
        dict(id="rd_scrap", name="Scrapyard", r=[50.0, 64.0, -12.5, 12.5], floor=snow),
        dict(id="jt_yard", name="Junk Town", r=[64.0, 90.6, -12.6, 12.6], floor=yard, layer=1),
    ]
    D["terrain"] = [dict(r=[-16.0, 104.0, -24.0, 26.0], floor=snow_far)]
    D["bounds"] = [-2.0, 92.0, -12.6, 12.6]
    # ---- terrain: the hill the Silo is dug into, banks along the edges, drifts
    D["mounds"] = [(4.5, 17.0, 10.0, 5.5, 4.2), (-6.0, 13.0, 6.0, 7.0, 3.2), (15.0, 16.5, 6.5, 4.0, 2.6),
                   (-6.0, 3.0, 3.2, 6.0, 1.6), (-8.0, -6.0, 4.0, 5.0, 1.0)]
    for i, u in enumerate(range(-2, 96, 7)):                      # far bank along the north edge
        D["mounds"].append((u + 3.0, 15.6 + (i % 3) * 0.6, 4.6, 1.8, 0.9 + 0.3 * (i % 2)))
    for i, u in enumerate(range(0, 96, 6)):                       # low bank along the near edge
        D["mounds"].append((u + 2.0, -14.6 - (i % 2) * 0.4, 3.8, 1.2, 0.45))
    for i, v in enumerate(range(-12, 14, 6)):                     # east edge beyond the town
        D["mounds"].append((94.5 + (i % 2) * 0.6, v + 2.0, 1.6, 3.6, 0.9))
    for (u, v, ru, rv, h) in ((19.0, 6.0, 2.2, 1.0, 0.35), (30.5, -7.5, 2.4, 1.2, 0.4), (47.0, -5.5, 1.8, 0.9, 0.3),
                              (8.0, -4.6, 2.6, 0.7, 0.25), (57.5, -10.0, 2.0, 1.0, 0.35)):
        D["mounds"].append((u, v, ru, rv, h))
        D["blocked"].append([u - ru * 0.7, u + ru * 0.7, v - rv * 0.7, v + rv * 0.7])
    # ---- ground marks: centre line, tyre ruts, black ice, slush at the road edges, boot prints, a drag mark
    dec = D["decor"]
    for u in range(0, 62, 5):
        dec.append(dict(t="patch", r=[u, u + 2.2, -0.08, 0.08], rgb=(0.78, 0.70, 0.42), alpha=0.75, layer=3, id="line"))
    for v0 in (-1.9, -1.2, 1.1, 1.8):
        dec.append(dict(t="patch", r=[-1.5, 63.5, v0, v0 + 0.3], rgb=(0.30, 0.31, 0.33), alpha=0.4, layer=3, id="rut"))
    for (u, v, a, w, l) in ((16.0, 1.2, 10, 1.6, 3.4), (33.5, -1.4, -14, 1.2, 4.0), (50.5, 0.8, 20, 1.4, 2.6), (58.0, -1.6, 4, 1.0, 3.0)):
        dec.append(dict(t="patch", r=[u - l / 2, u + l / 2, v - w / 2, v + w / 2], ang=a, rgb=(0.50, 0.60, 0.68), alpha=0.55, tex="soft", layer=4, id="ice"))
    for v0, v1 in ((-3.4, -2.8), (2.8, 3.4)):
        dec.append(dict(t="patch", r=[-1.5, 63.5, v0 - 0.3, v1 + 0.3], rgb=(0.62, 0.63, 0.65), alpha=0.6, layer=3, id="slush"))
    for k in range(14):                                         # boot prints away from the Silo, not coming back
        u = 6.0 + k * 0.62
        v = 4.2 - k * 0.32 + (0.12 if k % 2 else -0.12)
        dec.append(dict(t="patch", r=[u, u + 0.28, v, v + 0.13], ang=-25, rgb=(0.48, 0.53, 0.60), alpha=0.6, tex="soft", layer=5, id="print"))
    dec.append(dict(t="patch", r=[36.5, 41.5, -7.6, -7.0], ang=-18, rgb=(0.45, 0.46, 0.50), alpha=0.5, layer=4, id="drag"))
    # trodden paths: from the road to the rest stop, and the yard's tracks between the stalls
    dec.append(dict(t="patch", r=[40.0, 47.0, 2.5, 5.0], ang=0, rgb=(0.62, 0.64, 0.67), alpha=0.45, tex="soft", layer=3, id="trod"))
    dec.append(dict(t="patch", r=[66.0, 88.0, -1.6, 1.6], ang=0, rgb=(0.50, 0.48, 0.45), alpha=0.16, tex="soft", layer=3, id="trod"))
    dec.append(dict(t="patch", r=[74.0, 80.0, -9.0, 9.0], ang=0, rgb=(0.50, 0.48, 0.45), alpha=0.14, tex="soft", layer=3, id="trod"))
    # the yard: snow shovelled to the foot of the wall, churned mud where people stand and queue, ash by the fires
    for i, u in enumerate(range(66, 90, 4)):
        for v in (-11.9, 11.9):
            D["mounds"].append((u + 1.5 + (i % 2) * 0.6, v, 2.2, 0.8, 0.28 + 0.08 * (i % 3)))
    for i, v in enumerate(range(-10, 11, 4)):
        D["mounds"].append((90.2, v + 1.0, 0.8, 2.0, 0.3))
    for (u, v, a, l, w, al) in ((70.5, -3.2, 15, 4.5, 2.4, 0.32), (75.5, 4.0, -10, 5.0, 2.6, 0.30), (82.0, -4.5, 25, 4.0, 2.2, 0.30),
                                 (86.0, 3.5, -5, 3.6, 2.0, 0.28), (66.5, 0.0, 0, 3.0, 4.6, 0.34), (78.5, -0.4, 0, 3.4, 3.0, 0.26),
                                 (72.0, 8.6, 5, 5.0, 1.6, 0.24), (80.5, -8.8, -5, 6.0, 1.6, 0.24)):
        dec.append(dict(t="patch", r=[u - l / 2, u + l / 2, v - w / 2, v + w / 2], ang=a, rgb=(0.30, 0.26, 0.22), alpha=al, tex="soft", layer=3, id="mud"))
    for (u, v, r) in ((67.4, 3.2, 1.3), (77.0, 0.6, 1.3)):
        dec.append(dict(t="patch", r=[u - r, u + r, v - r * 0.8, v + r * 0.8], ang=0, rgb=(0.17, 0.16, 0.15), alpha=0.45, tex="soft", layer=4, id="ash"))
    P = D["props"]
    def add(t, u, v, f, **kw):
        P.append(dict(t=t, u=u, v=v, f=f, **kw))
    # ============ A: the Silo exit
    add("silo_portal", 4.5, 11.3, "-v", name="Silo 81 surface portal",
        text="Six metres of poured concrete and two blast leaves, one jammed open. Someone scratched SEALED FROM INSIDE into the pier. The door is not sealed now.")
    add("guard_shack", 13.0, 10.4, "-v", name="Guard post",
        text="The heater is a block of rust. The duty log stops in the middle of a sentence. The chair is still pulled up to the window.")
    add("sandbag_nest", 9.0, 7.4, "-v", name="Sandbag nest", text="Empty. Brass casings frozen into the snow, all pointing outwards.")
    add("road_barrier", 4.5, 2.4, "-v", L=4.4, noblock=True, posts=[[1.8, 2.8, 1.8, 2.4], [6.2, 7.2, 1.8, 2.4]],
        name="Checkpoint barrier", text="The boom snapped where it met the post. A child's red mitten is tied to the stump.")
    add("notice_board", 11.2, 3.6, "-v", name="Evacuation notice",
        text="EVACUATION - NEW MERIDIAN - 40 KM. Assemble at the depot. Bring documents, warm clothing, three days of food. The arrow pointing east has been torn half away.")
    add("glbp", -0.8, 6.2, "+u", key="jt_chainlink", name="Perimeter fence", text="Chain-link, bent outwards. Whatever went through it was leaving.")
    add("glbp", 15.6, 5.6, "-v", key="jt_chainlink", turn=8, name="Perimeter fence")
    # the car graveyard (near side, low)
    add("glbp", 4.8, -9.2, "+v", key="jt_van_a", turn=24, name="Abandoned van",
        text="Nose in the snow, doors open. The seats have been cut out for the foam.")
    add("glbp", 10.2, -6.6, "+v", key="jt_car", turn=-14, name="Abandoned car",
        text="A family estate car. Under the snow on the back seat, a shape you decide not to look at closely.")
    add("glbp", 13.4, -10.6, "+v", key="jt_van_b", turn=40, name="Abandoned van")
    add("glbp", 0.6, -7.0, "+v", key="jt_car", turn=72, mirror=True, name="Abandoned car")
    add("army_truck_side", 19.6, -10.8, "+v", name="Army truck",
        text="On its side. Sandbags, a field radio, jerrycans. No bodies. No tracks leading away, either.")
    add("dead_tree", -1.0, -11.5, "+v", seed=1, H=7.0)
    add("dead_tree", 17.8, 9.2, "-v", seed=2, H=6.0)
    add("dead_tree", 22.8, 11.0, "-v", seed=3, H=7.5)
    add("guardrail", 9.0, -3.6, "+v", L=6.0)
    add("guardrail", 20.0, -3.6, "+v", L=8.0, bent=0.9, name="Guardrail", text="Bent out by something heavy, long ago.")
    add("guardrail", 17.0, 3.6, "-v", L=6.0)
    # ============ B: pylon, the first Changed, the trailer, the rest stop
    add("power_pylon", 28.0, 10.6, "-v", lean=12.0, name="Leaning pylon",
        text="Leaning over the road like it is listening. Scorch marks on the legs and spent cases in the snow under it: people fought here.")
    add("fallen_pylon", 30.0, -10.8, "+v", L=12.0, name="Fallen pylon")
    add("glbp", 36.4, -4.4, "+v", key="jt_car", turn=12, name="Stalled car",
        text="Doors open, engine cold for years. A suitcase on the back seat, a child's seat, a road map with New Meridian circled in pencil.")
    add("guardrail", 31.5, 3.6, "-v", L=6.0)
    add("guardrail", 47.5, -3.6, "+v", L=6.0, bent=0.5)
    add("box_trailer", 41.8, 5.4, "-v", cab=52.0, name="Jack-knifed trailer",
        text="BALTIC FREIGHT, faded to pink. The back doors were cut open with a torch. Empty, apart from frost.")
    add("dead_tree", 38.8, -11.4, "+v", seed=4, H=6.5)
    add("dead_tree", 46.8, -8.8, "+v", seed=5, H=5.5)
    add("dead_tree", 35.0, 12.0, "-v", seed=6, H=6.8)
    add("rest_kiosk", 44.2, 13.6, "-v", name="Rest stop kiosk",
        text="Shelves stripped to the brackets. A kettle on a cold stove. A radio on the counter, its battery long dead, still tuned to the emergency band.")
    add("fuel_pump", 42.4, 8.0, "-v", name="Fuel pump", text="NO FUEL, says the sign. The hose has been cut for the rubber.")
    add("fuel_pump", 45.6, 8.0, "-v", broken=True, name="Fuel pump")
    add("glbp", 38.6, 11.6, "-v", key="jt_car", turn=-8, name="Snowed-in car",
        text="A photo tucked in the sun visor: three people squinting into summer.")
    add("tyre_stack", 49.2, 11.2, "-v", n=4)
    add("tyre_stack", 50.0, 10.6, "-v", n=2)
    # ============ C: billboard and scrapyard
    add("billboard", 55.0, 12.4, "-v", name="Billboard",
        text="NEW MERIDIAN 40 km - EVACUATION ROUTE. Someone has painted a line of marks under it, one for each day, until they stopped.")
    add("container", 55.4, -10.4, "+v", paint="teal", name="Shipping container")
    add("container", 49.2, -11.9, "+v", paint="red")
    add("burned_bus", 57.0, 10.6, "-v", name="Burned bus", text="Burned from the inside. The seats are springs.")
    add("glbp", 60.8, -12.8, "+v", key="jt_van_b", turn=-30, mirror=True)
    for i, (u, v) in enumerate(((56.6, -5.4), (58.0, -5.9), (59.4, -5.4), (56.9, -7.4), (58.4, -7.8))):
        add("grave", u, v, "+u", seed=i, name="Graves",
            text="Crosses of exhaust pipe and fence post, hubcaps for headstones. Number plates for names.")
    add("tyre_stack", 52.6, 5.4, "-v", n=3)
    add("tyre_stack", 53.4, 6.0, "-v", n=4)
    add("dead_tree", 55.0, -6.6, "+v", seed=7, H=5.0)
    # ============ Junk Town: the ring (west and south walls face out to the camera and stay low; north and
    # east walls are the tall far side). Centre sorting is right for these 4-5 m pieces.
    W = []
    def wall(key, u, v, f, **kw):
        L = {"jt_van_ladder": 4.6, "jt_van_a": 4.6, "jt_van_b": 3.6, "jt_car": 4.2, "jt_plank_fence": 4.2, "jt_chainlink": 3.4}[key]
        add("glbp", u, v, f, key=key, name=kw.pop("name", "Junk Town wall"),
            text=kw.pop("text", "Wrecks nose to tail, propped and chained, fence panels in the gaps."), **kw)
    # west wall (u = 64), gate at v = 0
    wall("jt_van_a", 65.1, -12.0, "-u")
    wall("jt_plank_fence", 64.45, -7.6, "-u")
    wall("jt_chainlink", 64.1, -4.0, "-u")
    wall("jt_car", 64.9, 4.3, "-u", text="A Zhiguli on its belly, chained to a post. Plates nailed along it: names, dates. A memorial of the road.")
    wall("jt_van_ladder", 65.1, 8.6, "-u")
    wall("jt_plank_fence", 64.45, 12.6, "-u")
    add("junk_gate_open", 64.2, 0.0, "-u", noblock=True, posts=[[63.8, 64.6, -2.5, -2.0], [63.8, 64.6, 2.0, 2.5]],
        name="Junk Town gate", text="Truck-box doors on rails, open by day. Somebody up on the towers is always watching the road.")
    # the two leaves: plank-and-sheet panels pulled open against the outside of the wall
    add("glbp", 61.8, -2.5, "-v", key="jt_plank_fence", name="Gate leaf", text="A gate leaf of planks and sheet on a rail, pulled open.")
    add("glbp", 61.8, 2.5, "+v", key="jt_plank_fence", mirror=True, name="Gate leaf", text="A gate leaf of planks and sheet on a rail, pulled open.")
    add("glbp", 62.8, -5.6, "-u", key="jt_tower", name="Gate tower", text="A rifleman's platform of scaffold and planks. The guard up there nods at you, rifle across his knees.")
    add("glbp", 62.8, 5.8, "-u", key="jt_tower", mirror=True, name="Gate tower")
    # north wall (v = 14), the tall far side
    wall("jt_van_a", 66.3, 14.6, "-v")
    wall("jt_plank_fence", 70.7, 14.0, "-v")
    wall("jt_van_ladder", 75.1, 14.6, "-v")
    wall("jt_car", 79.5, 14.4, "-v")
    wall("jt_van_b", 83.4, 15.1, "-v")
    wall("jt_plank_fence", 87.3, 14.0, "-v")
    add("glbp", 90.6, 13.4, "-v", key="jt_tower", name="Watchtower")
    add("glbp", 65.4, 13.0, "-v", key="jt_tower", mirror=True, name="Watchtower")
    # east wall (u = 92)
    wall("jt_van_a", 93.1, 9.0, "-u")
    wall("jt_plank_fence", 92.45, 4.6, "-u")
    wall("jt_van_ladder", 93.1, 0.2, "-u")
    wall("jt_car", 92.9, -4.0, "-u")
    wall("jt_plank_fence", 92.45, -8.2, "-u")
    wall("jt_van_b", 93.6, -12.1, "-u")
    # south wall (v = -14): low and see-through, the camera side
    wall("jt_chainlink", 66.0, -13.9, "-v")
    wall("jt_car", 70.0, -13.1, "-v", mirror=True)
    wall("jt_chainlink", 74.0, -13.9, "-v")
    wall("jt_plank_fence", 78.0, -13.55, "-v")
    wall("jt_car", 82.2, -13.1, "-v")
    wall("jt_chainlink", 86.1, -13.9, "-v")
    wall("jt_car", 90.0, -13.1, "-v", mirror=True)
    add("glbp", 90.4, -11.6, "-u", key="jt_tower", name="Watchtower")
    # ---- inside: shacks on the far sides, the market round the burn barrel, the pen
    # Scrap-built houses (kit.scrap_house): corrugated sheet, car doors and planks, not the Tripo timber-and-canvas shacks
    add("scrap_house", 69.2, 11.8, "-v", L=5.6, D=4.2, seed=1, pal="mixed", door=-1.4, windows=(0.5, 1.9), porch=True,
        sign_board=(1.2, 2.32, 1.7, 0.42), sign="BUNKS  -  2 SALT", name="Bunkhouse",
        text="Bunks for travellers who reach the gate after dark. Two blankets each, and a rule about boots.")
    add("scrap_house", 74.6, 11.8, "-v", L=4.4, D=4.0, seed=2, pal="clinic", door=1.2, windows=(-1.2,), cross=True, name="Clinic",
        text="A cot, a lamp, boiled rags on a line. The medic is out, but the kettle is warm.")
    add("scrap_house", 79.9, 11.8, "-v", L=3.6, D=3.2, seed=5, pal="warm", door=-0.7, windows=(), name="Smokehouse",
        text="Goat, mostly. The smell carries to the gate.")
    add("scrap_house", 85.6, 11.8, "-v", L=5.4, D=4.6, seed=4, pal="cool", door=0.4, garage=True, windows=(-2.0,),
        sign_board=(0.4, 3.0, 2.2, 0.42), sign="MARA  -  REPAIRS", name="Mara's garage",
        text="Half workshop, half home: a vice, a parts shelf, a stove that never goes out, and an engine block on a stand.")
    add("scrap_house", 90.2, 4.6, "-u", L=4.8, D=4.2, seed=7, pal="mixed", door=1.5, windows=(), awning=1.6,
        sign_board=(-0.6, 2.3, 2.0, 0.42), sign="BUY - SELL - SWAP", name="Market shack",
        text="Tin roof, salvaged counter, and a hand-painted sign: BUY - SELL - SWAP. Ammunition by the round.")
    add("scrap_house", 90.2, -2.5, "-u", L=4.0, D=4.0, seed=8, pal="bare", door=-0.6, windows=(), tank=True, name="Water store",
        text="Barrels of meltwater, boiled and counted. The cistern is padlocked twice.")
    add("laundry", 72.4, 6.2, "-v", L=3.6, seed=1, name="Washing line", text="Shirts, a blanket, socks frozen stiff. Somebody here still does laundry.")
    add("laundry", 84.0, -6.4, "-u", L=3.0, seed=2)
    add("glbp", 80.6, -7.6, "+v", key="jt_car", turn=6, mirror=True, name="Car on blocks", text="Mara's project. Half its parts are in the wall already.")
    add("burn_barrel", 77.0, 0.6, "+u", name="Burn barrel", text="Somebody always keeps it lit. People stand round it to trade news.")
    add("market_stall", 73.4, 4.6, "-v", seed=0, name="Market stall", text="Jars of rendered fat, valve washers, a radio that works if you hit it.")
    add("market_stall", 80.2, 4.6, "-v", seed=1, name="Market stall", text="Boots, coats, gloves: none of them new, all of them dry.")
    add("market_stall", 77.4, -3.8, "+v", seed=2, name="Market stall", text="Dried mushrooms, salt, a jar of something red.")
    add("notice_board", 68.6, -2.4, "+u", name="Notice board",
        text="WORK: wall repair, pays in food. LOST: grey dog, answers to Kopek. CONVOY TO NEW MERIDIAN - SUSPENDED - ASK MARA.")
    add("animal_pen", 84.2, -11.8, "+v", name="Goat pen", text="Three goats, a trough and a hay pile. The settlement's milk.")
    # Junk Town's people are neutral actors (game.gd _spawn_folk): they talk when clicked, and attacking one turns the town.
    FOLK = [
        dict(u=75.6, v=1.6, dir=4, coat=[0.21, 0.19, 0.16], name="Woman at the barrel", bark="Warm your hands, Silo. Then tell me how many of you are still down there."),
        dict(u=78.4, v=1.8, dir=3, coat=[0.16, 0.18, 0.21], name="Old trader", bark="Salt for news, news for salt. What's the road like?"),
        dict(u=73.4, v=2.0, dir=5, coat=[0.25, 0.22, 0.17], name="Washerwoman", bark="If you see a grey dog, his name's Kopek. He comes for sugar."),
        dict(u=80.2, v=2.0, dir=4, coat=[0.19, 0.20, 0.17], name="Boot seller", bark="Dry boots. Not new, but dry. You'll thank me past the bridge."),
        dict(u=77.4, v=-2.0, dir=1, coat=[0.22, 0.17, 0.15], name="Mushroom seller", bark="The red jar? Don't ask. Two salt."),
        dict(u=66.8, v=1.8, dir=3, coat=[0.17, 0.18, 0.17], name="Gate watch", bark="You came up the road on foot? Then you met them. Keep your voice down in here, people are tired."),
        dict(u=85.0, v=-8.4, dir=4, coat=[0.20, 0.19, 0.17], name="Goatherd", bark="Three goats, one stove. Touch the goats and we have words."),
        dict(u=83.6, v=4.0, dir=0, coat=[0.16, 0.17, 0.19], name="Customer", bark="Rook sets the prices. Mara fixes what breaks. The rest of us wait for spring."),
        dict(u=71.4, v=-6.2, dir=2, coat=[0.21, 0.20, 0.17], name="Tea drinker", bark="Tea's hot. That's about all I can say for today."),
    ]
    D["creatures"] = []
    D["creatures"] += [dict(kind="goat", u=83.2, v=-10.6, facing=40.0, phase=0.0),
                      dict(kind="goat", u=85.2, v=-11.0, facing=200.0, phase=2.1),
                      dict(kind="goat", u=84.4, v=-9.6, facing=110.0, phase=4.3)]
    add("firewood", 90.8, -5.4, "-u")
    for i, (u, v) in enumerate(((82.2, 6.2), (82.8, 5.8), (87.4, -9.2), (67.2, -11.2), (77.9, -9.4))):
        add("oil_drum", u, v, "+u", k=i)
    for (u, v, n) in ((66.4, 5.6, 3), (88.4, 7.6, 4), (73.2, -8.4, 2)):
        add("tyre_stack", u, v, "+u", n=n)
    for (u, v) in ((81.4, 1.6), (82.0, 1.2), (71.6, 1.8)):
        add("crate", u, v, "+u")
    add("crate", 74.2, -1.4, "+u")
    add("crate", 74.8, -1.0, "+u")
    D["smoke"] = []                       # the scrap houses' stovepipes smoke on their own (see out["ground"])
    add("scrap_house", 70.4, -12.0, "+v", L=4.6, D=3.6, seed=9, pal="warm", door=1.5, windows=(), awning=1.5,
        sign_board=(-0.9, 2.35, 1.2, 0.42), sign="TEA", name="Tea house",
        text="A stove, a samovar, six stools. Payment in sugar, salt or news.")
    add("scrap_house", 76.2, -12.4, "+v", L=3.0, D=2.6, H=2.3, seed=11, pal="bare", door=0.4, windows=(), lean=True, chimney=False, name="Tool shed", text="Shovels, a sledge, chain, rope. All counted, all signed out.")
    add("burn_barrel", 67.4, 3.2, "+u", name="Gate fire", text="The gate watch warms its hands here between shifts.")
    add("market_stall", 70.8, -4.6, "+v", seed=3, name="Market stall", text="Batteries, sorted by how much charge someone swears is left in them.")
    for (u, v) in ((68.6, 6.4), (69.2, 6.0), (86.0, -4.6), (83.6, 1.2), (84.2, 0.6)):
        add("crate", u, v, "+u")
    add("firewood", 79.8, 7.7, "-v")
    add("tyre_stack", 81.2, -4.8, "+u", n=2)
    add("scrap_pile", 66.6, -7.4, "+u", seed=3, name="Scrap pile", text="Door panels and bonnets, sorted by size. The wall eats them.")
    # ---- way back, spawns, enemies and the guards
    D["stairs"] = [dict(id="to_l1_from_rd", u=4.5, v=9.6, to="L1", arrive=[-2.6, 0.6], name="Silo 81 portal",
                        text="Back down the ramp to the surface depot and the lifts.")]
    D["spawns"] = {"player": [4.5, 8.2, 5], "worms": [], "enemies": [
        # E1: the stalled car. An infected stands still with its back to the road; two ferals lie under the snow.
        dict(kind="infected", u=35.0, v=-2.4, dir=1, group="car", wake=10, coat=0, state="still",
             speak="A voice from the figure by the car, wet and wrong: 'Close the door. You're letting the warm out.'", speak_d=19),
        dict(kind="feral", u=38.6, v=-6.0, dir=3, group="car", coat=1, state="hidden"),
        dict(kind="feral", u=39.4, v=-3.0, dir=3, group="car", coat=2, state="hidden"),
        # E2 (optional): the rest stop - two ferals nesting by the kiosk
        dict(kind="feral", u=46.6, v=8.6, dir=4, group="reststop", wake=8, coat=2, state="still"),
        dict(kind="feral", u=43.8, v=6.4, dir=2, group="reststop", wake=8, coat=0),
        # E3: the scrapyard before the gate - two infected and a feral, drawn by the gate fire
        dict(kind="infected", u=55.6, v=-2.0, dir=3, group="gate", wake=12, coat=1),
        dict(kind="feral", u=53.6, v=4.2, dir=4, group="gate", wake=12, coat=0),
        dict(kind="infected", u=59.0, v=5.2, dir=3, group="gate", wake=12, coat=2),
    ]}
    D["spawns"]["folk"] = FOLK
    D["support"] = [dict(group="gate", u=62.8, v=5.8, z=5.6, after_round=2, hit=65,
                         msg="A rifle cracks from the gate tower. 'Keep your head down, Silo!'"),
                    dict(group="gate", u=62.8, v=-5.6, z=5.6, after_round=3, hit=55,
                         msg="The second tower joins in. Somebody up there is a good shot.")]
    D["light"] = dict(ambient=(0.86, 0.93, 1.08),
                      lamps=[(77.0, 0.6, 1.2, 5.0, "amber"), (67.4, 3.2, 1.2, 3.5, "amber"), (85.6, 9.6, 2.2, 4.0, "amber"), (74.6, 9.8, 2.0, 3.0, "amber"),
                             (69.2, 9.4, 2.0, 3.0, "amber"), (89.0, 4.0, 2.0, 3.0, "amber"), (84.2, -10.2, 2.2, 3.0, "bulb"),
                             (63.0, 0.0, 3.0, 4.0, "work"),
                             (4.5, 8.0, 2.0, 6.0, "cold"), (36.0, -4.0, 1.5, 6.0, "cold"), (44.0, 9.0, 1.5, 5.0, "cold")])
    return D


def JTT():
    """Tripo model check: every Junk Town GLB on a snow plot at the game camera."""
    D = {"name": "Tripo check", "rooms": [], "walls": [], "doors": [], "props": [], "decor": [], "inspect": [],
         "stairs": [], "spawns": {"player": [2.0, 2.0, 5]}, "blocked": [], "holes": [], "bounds": [0.0, 34.0, 0.0, 14.0]}
    D["rooms"] += [dict(id="plot", name="Plot", r=[0.0, 34.0, 0.0, 14.0], floor=dict(rgb=(0.74, 0.77, 0.80), noise=0.16, noise_scale=1.6))]
    keys = ["jt_van_ladder", "jt_van_a", "jt_van_b", "jt_car", "jt_plank_fence", "jt_tower", "jt_chainlink"]
    for i, k in enumerate(keys):
        D["props"].append(dict(t="glbp", key=k, u=2.6 + i * 4.6, v=11.0, f="-v"))
    for i, k in enumerate(["jt_tarp_shack_a", "jt_tarp_shack_b", "jt_tarp_shack_c", "jt_cabin_a", "jt_cabin_b", "jt_cabin_c"]):
        D["props"].append(dict(t="glbp", key=k, u=3.0 + i * 5.4, v=5.4, f="-v"))
    D["light"] = dict(ambient=(0.86, 0.93, 1.06), lamps=[])
    return D


def SHT():
    """Scrap-house check: the Junk Town buildings on a snow plot at the game camera, plus one Tripo wall for scale."""
    D = {"name": "Scrap house check", "rooms": [], "walls": [], "doors": [], "props": [], "decor": [], "inspect": [],
         "stairs": [], "spawns": {"player": [2.0, 2.0, 5]}, "blocked": [], "holes": [], "bounds": [0.0, 30.0, 0.0, 12.0]}
    D["rooms"] += [dict(id="plot", name="Plot", r=[0.0, 30.0, 0.0, 12.0], floor=dict(rgb=(0.52, 0.52, 0.53), noise=0.16, noise_scale=1.6))]
    rd = {p.get("name"): p for p in RD()["props"] if p["t"] == "scrap_house"}
    for i, nm in enumerate(["Bunkhouse", "Clinic", "Smokehouse", "Mara's garage"]):
        q = dict(rd[nm]); q.update(u=3.5 + i * 7.0, v=11.6, f="-v"); D["props"].append(q)
    for i, nm in enumerate(["Market shack", "Water store", "Tea house", "Tool shed"]):
        q = dict(rd[nm]); q.update(u=3.5 + i * 7.0, v=0.4, f="+v"); D["props"].append(q)
    D["light"] = dict(ambient=(0.86, 0.93, 1.06), lamps=[])
    return D


LV = {"L2": L2, "L3": L3, "L2W": L2W, "L4W": L4W, "L4E": L4E, "L5": L5, "L1": L1, "RD": RD, "JTT": JTT, "SHT": SHT}[LEVEL]()

# ---------- light (docs/VISUAL_DIRECTION.md): the level's base tone, its lamps and its cold pockets.
# Desks with a lamp and standing lamps light themselves; "lamps" adds ceiling bulbs, work lamps and
# cold pockets: (u, v, height, radius, kind).
LAMP = {"amber": kit.AMBER, "work": tuple(c * 1.15 for c in kit.AMBER), "bulb": tuple(c * 0.6 for c in kit.AMBER),
        "desk": tuple(c * 0.75 for c in kit.AMBER), "cold": kit.COLD, "furnace": (0.72, 0.30, 0.06)}
_light = LV.get("light", {})
kit.AMBIENT = _light.get("ambient", (1.0, 1.0, 1.0))
kit.PRACTICALS[:] = [(*g(u, v), z, r, LAMP[kd]) for (u, v, z, r, kd) in _light.get("lamps", [])]
for p in LV["props"]:
    if p["t"] == "desk" and not p.get("dark_lamp"):
        kit.PRACTICALS.append((*g(p["u"], p["v"]), 0.95, 1.7, LAMP["desk"]))
    if p["t"] == "floorlamp":
        kit.PRACTICALS.append((*g(p["u"], p["v"]), 1.5, 2.8, LAMP["amber"]))
print("light: ambient", kit.AMBIENT, "lamps", len(kit.PRACTICALS))

# ============================================================ background geometry
bg_objects = []


def plan_obj(b, outline=0.012):
    ob = b.finish(outline=outline)
    ob.matrix_world = ROT45 @ ob.matrix_world
    bg_objects.append(ob)
    return ob


def floor_mat(spec, rid):
    if spec.get("tex"):                         # painted texture in the asset pack's palette (textures.py)
        return toon(f"Floor_{LEVEL}_{rid}", spec.get("tint", (1.0, 1.0, 1.0)), tex=spec["tex"], tex_scale=spec.get("ts", 1.2),
                    frost=(spec["frost"][0], spec["frost"][1], (0.78, 0.84, 0.88)) if spec.get("frost") else None, lit=1.0)
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


for room in ([] if LV.get("godot_ground") else LV["rooms"]):
    b = Builder("Floor_" + room["id"])
    m = floor_mat(room["floor"], room["id"])
    top = 0.003 * room.get("layer", 0)                 # outdoors, a road laid over the snowfield sits a hair higher
    for p in rect_minus(room["r"], LV.get("holes", [])):
        b.box(p[0], p[1], p[2], p[3], -0.08, top, m)
    plan_obj(b, outline=0)

# terrain: ground you can see but not walk on (outdoors the snowfield carries on past the playable area)
for i, t in enumerate([] if LV.get("godot_ground") else LV.get("terrain", [])):
    b = Builder("Terrain_%d" % i)
    m = floor_mat(t["floor"], "terrain%d" % i)
    b.box(t["r"][0], t["r"][1], t["r"][2], t["r"][3], -0.12, -0.004 + 0.001 * t.get("layer", 0), m)
    plan_obj(b, outline=0)

# low snow mounds, drifts and banks baked into the ground (keep them under ~1 m: the bg never covers a character)
for i, md in enumerate([] if LV.get("godot_ground") else LV.get("mounds", [])):
    u, v, ru, rv, h = md[:5]
    b = Builder("Mound_%d" % i)
    m = floor_mat(md[5] if len(md) > 5 else LV.get("mound_floor", dict(rgb=(0.80, 0.83, 0.86), noise=0.12, noise_scale=2.0)), "mound%d" % i)
    kit.ellipsoid(b, (u, v, -0.05), (ru, rv, h), m, seg=14)
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


def room_profile(room):
    """Which wear profile a room's walls get (kit.AGE_PROFILES), from what the room is for."""
    if room is None:
        return "corridor"
    if room.get("age"):
        return room["age"]                       # explicit, per room
    k = (room.get("id", "") + " " + room.get("name", "")).lower()
    for words, prof in ((("council", "varga", "office"), "kept"),
                        (("pump", "engineering", "valve", "gallery", "plant", "boiler", "radio"), "maintenance"),
                        (("wash", "wc", "shower", "toilet"), "wet"),
                        (("linen", "store", "archive", "kitchen", "pantry"), "storage"),
                        (("corridor", "landing", "lobby"), "corridor"),
                        (("dorm", "room", "quarters", "duty", "bunk"), "sleeping"),
                        (("commons", "classroom", "clinic", "waiting", "school"), "public")):
        if any(w_ in k for w_ in words):
            return prof
    return "public"


# Palette: one building, a few related paints. (upper tint, dado colour, dado height) per profile, over
# the cream plaster texture; storage and maintenance show more of the concrete under thinner paint.
PAINT = {"corridor":    ((1.0, 1.0, 1.0), (0.55, 0.78, 0.66), 1.25),       # institutional cream over green
         "public":      ((1.0, 0.99, 0.96), (0.55, 0.76, 0.64), 1.25),
         "sleeping":    ((1.0, 0.94, 0.82), (0.6, 0.72, 0.6), 1.1),         # yellowed beige, faded green
         "wet":         ((0.95, 0.98, 0.96), (0.62, 0.8, 0.76), 1.5),       # paler, cooler, a higher dado
         "storage":     ((0.86, 0.84, 0.8), (0.56, 0.6, 0.54), 1.0),        # dull, almost unpainted
         "maintenance": ((0.92, 0.91, 0.88), (0.6, 0.72, 0.62), 1.3),
         "kept":        ((1.0, 1.0, 0.97), (0.55, 0.76, 0.64), 1.25)}


def wall_material(w, room=None):
    """The material of one face of a wall: the wall's own type (panel / machine / raw / painted) aged
    like the room the face looks into. One material per (type, room), cached by name."""
    prof = room_profile(room)
    rid = room["id"] if room else "out"
    seed = (sum(map(ord, rid)) % 97) / 9.7
    age = dict(AGE_PROFILES[prof], seed=seed)
    # textures from textures.py, in the asset pack's palette; the rgb values tint them
    if w.get("mat") == "panel":                 # Council rooms: wood panelling under cream paint
        return toon(f"WallPanel_{LEVEL}_{rid}", (1.0, 1.0, 1.0), tex="plaster_cream", tex_scale=2.0,
                    dado=((0.62, 0.42, 0.26), 1.1), age=dict(age, peel=age["peel"] * 0.3))
    if w.get("mat") == "machine":               # plant rooms: machinery green under grey
        return toon(f"WallMachine_{LEVEL}_{rid}", (1.0, 1.0, 0.97), tex="concrete_wall", tex_scale=2.2,
                    dado=((0.68, 0.86, 0.7), 1.3), age=age)
    if w.get("mat") == "raw":
        return toon(f"WallRaw_{LEVEL}_{rid}", (0.97, 0.95, 0.9), tex="concrete_wall", tex_scale=2.2,
                    age=dict(age, peel=0.0, repaint=0.0))
    up, low, h = PAINT[prof]
    frost = (16.5, 23.0, (0.8, 0.86, 0.9), 1.1) if LEVEL == "L2" else None
    if prof in ("storage", "maintenance"):
        return toon(f"WallDado_{LEVEL}_{rid}", up, tex="concrete_wall", tex_scale=2.2, dado=(low, h), frost=frost, age=age)
    return toon(f"WallDado_{LEVEL}_{rid}", up, tex="plaster_cream", tex_scale=2.0, dado=(low, h), frost=frost, age=age)


def wall_rooms(w):
    """(room on the -side, room on the +side) at the middle of the wall: -v/+v for walls along u,
    -u/+u for walls along v. None where there is no room (outside the shelter)."""
    (ua, va), (ub, vb) = w["a"], w["b"]
    along_u = va == vb
    out = []
    for s_ in (-0.3, 0.3):
        best = None
        for t in (0.5, 0.3, 0.7, 0.15, 0.85):
            pu, pv = ua + (ub - ua) * t, va + (vb - va) * t
            qu, qv = (pu, pv + s_) if along_u else (pu + s_, pv)
            hit = [r for r in LV["rooms"] if r["r"][0] <= qu <= r["r"][1] and r["r"][2] <= qv <= r["r"][3]]
            if hit:
                best = hit[0]; break
        out.append(best)
    return out[0], out[1]


CUT = toon("WallCut", (0.2, 0.2, 0.19))
# Wall hierarchy. The shelter's shell keeps its full height and weight; corridor walls are full height
# but lighter; partitions between rooms are thin and stop short of the slab. Each wall's dark top is
# its own thickness, so caps are proportional; posts only stand at the shell's corners.
TOP = toon("WallTop", (0.055, 0.052, 0.048), noise=0.1, noise_scale=9)
TOP_PART = toon("WallTopPart", (0.11, 0.105, 0.1), noise=0.08, noise_scale=9)
SKIRT = toon("Skirting", (0.22, 0.23, 0.21), noise=0.06)
JAMB = toon("DoorJamb", (0.42, 0.42, 0.4), tex="concrete_wall", tex_scale=1.2)
WALL_KIND = {"struct": dict(t=0.30, h=FULL, top=TOP, post=True),
             "corr": dict(t=0.18, h=FULL, top=TOP, post=False),
             "part": dict(t=0.12, h=2.35, top=TOP_PART, post=False)}
SK_H, SK_D = 0.12, 0.02
front_walls = []                                    # full height too, but drawn as sorted sprites that fade (see below)


def wall_kind(w):
    """struct: open space on one side (the shell). corr: a corridor/landing on one side. part: rooms both sides."""
    if w.get("kind"):
        return w["kind"]
    (ua, va), (ub, vb) = w["a"], w["b"]
    along_u = va == vb
    sides = [set(), set()]
    for t in (0.2, 0.5, 0.8):
        pu, pv = ua + (ub - ua) * t, va + (vb - va) * t
        for k, s_ in enumerate((-0.3, 0.3)):
            qu, qv = (pu, pv + s_) if along_u else (pu + s_, pv)
            hit = [r for r in LV["rooms"] if r["r"][0] <= qu <= r["r"][1] and r["r"][2] <= qv <= r["r"][3]]
            if not hit and not any(h[0] <= qu <= h[1] and h[2] <= qv <= h[3] for h in LV.get("holes", [])):
                return "struct"
            sides[k].update(r["id"] for r in hit)
    ids = sides[0] | sides[1]
    if any(any(x in i for x in ("corridor", "landing", "lobby", "gallery")) for i in ids):
        return "corr"
    return "part"


def build_wall(w, full=False):
    (ua, va), (ub, vb) = w["a"], w["b"]
    along_u = va == vb
    lo, hi = (min(ua, ub), max(ua, ub)) if along_u else (min(va, vb), max(va, vb))
    K = WALL_KIND[wall_kind(w)]
    t = K["t"]
    ops = sorted(w.get("openings", []))
    segs, cur = [], lo - t / 2
    for (t0, t1, _) in ops:
        segs.append((cur, t0)); cur = t1
    segs.append((cur, hi + t / 2))
    b = Builder("Wall")
    r_minus, r_plus = wall_rooms(w)
    m_minus = wall_material(w, r_minus or r_plus)
    m_plus = wall_material(w, r_plus or r_minus)
    m = m_minus
    faces = {2: m_minus, 3: m_plus} if along_u else {0: m_minus, 1: m_plus}
    z0 = -2.75 if w.get("shaft") else 0.0
    tall = full or w["h"] >= FULL
    h = K["h"] if tall else w["h"]
    low_front = full and LV.get("front_h") and w["h"] < FULL    # this level keeps its camera-side walls low
    if low_front:
        h, tall = LV["front_h"], False

    def box(s0, s1, half, za, zb, mat, top=None):
        """A box along the wall: s along it, `half` the half-thickness across it. Wall-material boxes
        get each long face from the room it looks into."""
        fm = faces if mat is m else None
        if along_u:
            b.box(s0, s1, va - half, va + half, za, zb, mat, top_mat=top, faces_mat=fm)
        else:
            b.box(ua - half, ua + half, s0, s1, za, zb, mat, top_mat=top, faces_mat=fm)

    for (s0, s1) in segs:
        if s1 - s0 < 0.01:
            continue
        box(s0, s1, t / 2, z0, h, m, K["top"] if tall else CUT)          # low walls show a sawn dark top
        if not w.get("shaft"):
            box(s0, s1, t / 2 + SK_D, 0.0, SK_H, SKIRT, SKIRT)          # skirting on both faces
    if tall:
        for (t0, t1, _) in ops:                     # lintel, and a slim frame sized to this wall
            if h > 2.1:
                box(t0, t1, t / 2, 2.1, h, m, K["top"])
            box(t0 - 0.05, t1 + 0.05, t / 2 + 0.025, 2.1, 2.2, JAMB, JAMB)
            for e in (t0, t1):
                box(e - 0.05, e + 0.05, t / 2 + 0.025, 0.0, 2.2, JAMB, JAMB)
        if K["post"]:
            for e in (lo, hi):                      # shell corners and ends, a little proud of both faces
                box(e - (t + 0.1) / 2, e + (t + 0.1) / 2, (t + 0.1) / 2, z0, h + 0.03, m, TOP)
    return b


for w in LV["walls"]:
    if w["h"] < FULL:
        front_walls.append(w)
        continue
    plan_obj(build_wall(w), outline=0.012)


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


def puddle_mat(name, cu, cv, ru, rv, kind):
    """Shader for a puddle in plan space (object coords are plan u, v, z): kind 'water' or 'wet'."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    L = nt.links.new
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); L(tc.outputs["Object"], sep.inputs[0])
    def lin(src, c, r):
        a = nt.nodes.new("ShaderNodeMath"); a.operation = "SUBTRACT"; L(src, a.inputs[0]); a.inputs[1].default_value = c
        m_ = nt.nodes.new("ShaderNodeMath"); m_.operation = "DIVIDE"; L(a.outputs[0], m_.inputs[0]); m_.inputs[1].default_value = r
        return m_.outputs[0]
    cx = nt.nodes.new("ShaderNodeCombineXYZ"); L(lin(sep.outputs["X"], cu, ru), cx.inputs[0]); L(lin(sep.outputs["Y"], cv, rv), cx.inputs[1])
    ln = nt.nodes.new("ShaderNodeVectorMath"); ln.operation = "LENGTH"; L(cx.outputs[0], ln.inputs[0])
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 3.2; nz.inputs["Detail"].default_value = 4.0
    L(tc.outputs["Object"], nz.inputs["Vector"])
    wob = nt.nodes.new("ShaderNodeMapRange"); wob.inputs[3].default_value = 0.7; wob.inputs[4].default_value = 1.35
    L(nz.outputs["Fac"], wob.inputs[0])
    dd = nt.nodes.new("ShaderNodeMath"); dd.operation = "MULTIPLY"; L(ln.outputs["Value"], dd.inputs[0]); L(wob.outputs[0], dd.inputs[1])
    d2 = dd.outputs[0]
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    em = nt.nodes.new("ShaderNodeEmission")
    mix = nt.nodes.new("ShaderNodeMixShader")
    a = nt.nodes.new("ShaderNodeMapRange"); a.interpolation_type = "SMOOTHSTEP"; L(d2, a.inputs[0])
    if kind == "wet":                       # darkened, damp concrete fading out softly
        a.inputs[1].default_value = 0.3; a.inputs[2].default_value = 1.0
        a.inputs[3].default_value = 0.42; a.inputs[4].default_value = 0.0
        em.inputs["Color"].default_value = (0.03, 0.03, 0.03, 1)
    else:
        a.inputs[1].default_value = 0.78; a.inputs[2].default_value = 0.95
        a.inputs[3].default_value = 1.0; a.inputs[4].default_value = 0.0
        # reflections: the lamps above smeared into streaks along the screen vertical (plan u+v)
        sx = nt.nodes.new("ShaderNodeMath"); sx.operation = "SUBTRACT"; L(sep.outputs["X"], sx.inputs[0]); L(sep.outputs["Y"], sx.inputs[1])
        sy = nt.nodes.new("ShaderNodeMath"); sy.operation = "ADD"; L(sep.outputs["X"], sy.inputs[0]); L(sep.outputs["Y"], sy.inputs[1])
        sy2 = nt.nodes.new("ShaderNodeMath"); sy2.operation = "MULTIPLY"; L(sy.outputs[0], sy2.inputs[0]); sy2.inputs[1].default_value = 0.18
        sv = nt.nodes.new("ShaderNodeCombineXYZ"); L(sx.outputs[0], sv.inputs[0]); L(sy2.outputs[0], sv.inputs[1])
        st = nt.nodes.new("ShaderNodeTexNoise"); st.inputs["Scale"].default_value = 2.2; st.inputs["Detail"].default_value = 2.0
        L(sv.outputs[0], st.inputs["Vector"])
        hi = nt.nodes.new("ShaderNodeMapRange"); hi.interpolation_type = "SMOOTHSTEP"
        hi.inputs[1].default_value = 0.55; hi.inputs[2].default_value = 0.68; L(st.outputs["Fac"], hi.inputs[0])
        # bright meniscus near the edge
        rim = nt.nodes.new("ShaderNodeMapRange"); rim.interpolation_type = "SMOOTHSTEP"
        rim.inputs[1].default_value = 0.74; rim.inputs[2].default_value = 0.88; rim.inputs[4].default_value = 0.2; L(d2, rim.inputs[0])
        tot = nt.nodes.new("ShaderNodeMath"); tot.operation = "ADD"; tot.use_clamp = True
        L(hi.outputs[0], tot.inputs[0]); L(rim.outputs[0], tot.inputs[1])
        cm = nt.nodes.new("ShaderNodeMix"); cm.data_type = "RGBA"; L(tot.outputs[0], cm.inputs["Factor"])
        cm.inputs[6].default_value = (0.03, 0.04, 0.046, 1)            # dark: the unlit ceiling, reflected
        cm.inputs[7].default_value = (0.5, 0.58, 0.62, 1)              # lamp light on the water
        L(cm.outputs[2], em.inputs["Color"])
        op = nt.nodes.new("ShaderNodeMapRange"); op.inputs[3].default_value = 0.42; op.inputs[4].default_value = 0.85
        L(tot.outputs[0], op.inputs[0])
        af = nt.nodes.new("ShaderNodeMath"); af.operation = "MULTIPLY"
        L(a.outputs[0], af.inputs[0]); L(op.outputs[0], af.inputs[1])
        a = af
    L(a.outputs[0], mix.inputs["Fac"]); L(tr.outputs[0], mix.inputs[1]); L(em.outputs[0], mix.inputs[2])
    L(mix.outputs[0], out.inputs["Surface"])
    return m


def decor(d):
    t = d["t"]
    if t == "patch":                               # flat mark on the ground: plan rect (u0, u1, v0, v1), turned by ang
        if LV.get("godot_ground"):
            return                                 # drawn by Godot (out["ground"]["patches"])
        b = Builder("Patch")
        m = toon("Patch_%s" % d.get("id", "%.2f%.2f%.2f" % tuple(d["rgb"])), d["rgb"], noise=d.get("noise", 0.15), noise_scale=d.get("ns", 3.0))
        u0, u1, v0, v1 = d["r"]
        cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
        M = Matrix.Translation((cu, cv, 0)) @ Matrix.Rotation(math.radians(d.get("ang", 0.0)), 4, "Z")
        b.box(u0 - cu, u1 - cu, v0 - cv, v1 - cv, -0.05, 0.004 + 0.001 * d.get("layer", 0), m, M)
        plan_obj(b, outline=0)
        return
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
        # water lying on the floor: soft wavy edge, a dark wet halo, and the ceiling lamps reflected as streaks
        u0, v0, ru, rv = d["u"], d["v"], d["ru"], d["rv"]
        for kind, sc_, z in (("wet", 1.45, 0.002), ("water", 1.0, 0.004)):
            b = Builder("Puddle_" + kind)
            m = puddle_mat(f"Puddle_{kind}_{u0}_{v0}", u0, v0, ru * sc_, rv * sc_, kind)
            n = 48
            b.quad([(u0 + ru * sc_ * 1.15 * math.cos(2 * math.pi * k / n), v0 + rv * sc_ * 1.15 * math.sin(2 * math.pi * k / n), z) for k in range(n)], m)
            plan_obj(b, outline=0)
    elif t == "drain":
        # floor drain channel: a dark slot under a row of steel bars
        b = Builder("Drain")
        b.box(d["u0"], d["u1"], d["v"] - 0.17, d["v"] + 0.17, -0.01, 0.002, flat("DrainSlot", (0.025, 0.025, 0.028)))
        b.box(d["u0"], d["u1"], d["v"] - 0.2, d["v"] - 0.17, 0.0, 0.008, toon("Bracket", (0.3, 0.3, 0.28)))
        b.box(d["u0"], d["u1"], d["v"] + 0.17, d["v"] + 0.2, 0.0, 0.008, toon("Bracket", (0.3, 0.3, 0.28)))
        u = d["u0"] + 0.03
        while u < d["u1"] - 0.02:
            b.box(u, u + 0.025, d["v"] - 0.17, d["v"] + 0.17, 0.0, 0.007, toon("Bracket", (0.3, 0.3, 0.28)))
            u += 0.07
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
    elif t == "blackboard":
        b = Builder("Blackboard")
        b.box(-1.3, 1.3, 0.0, 0.03, -0.05, 1.15, toon("BoardFrame", (0.4, 0.3, 0.18), noise=0.1))
        b.box(-1.24, 1.24, 0.03, 0.035, 0.0, 1.1, toon("BoardGreen", (0.16, 0.24, 0.2), noise=0.12, noise_scale=6))
        b.box(-1.2, 1.2, 0.03, 0.08, -0.06, -0.03, toon("BoardFrame", (0.4, 0.3, 0.18), noise=0.1))
        chalk = flat("ChalkWhite", (0.82, 0.82, 0.76))
        for k in range(4):                                   # lines of chalk writing
            b.box(-1.0, -0.2 + 0.12 * (k % 3), 0.036, 0.038, 0.42 - k * 0.1, 0.43 - k * 0.1, chalk)
        for k in range(10):                                  # a chalk drawing of the core: a circle and pipes
            a0, a1 = 2 * math.pi * k / 10, 2 * math.pi * (k + 1) / 10
            b.quad([(0.6 + 0.2 * math.cos(a0), 0.037, 0.55 + 0.2 * math.sin(a0)), (0.6 + 0.2 * math.cos(a1), 0.037, 0.55 + 0.2 * math.sin(a1)),
                    (0.6 + 0.18 * math.cos(a1), 0.037, 0.55 + 0.18 * math.sin(a1)), (0.6 + 0.18 * math.cos(a0), 0.037, 0.55 + 0.18 * math.sin(a0))], chalk)
        b.box(0.79, 1.1, 0.037, 0.039, 0.54, 0.56, chalk)
        b.box(0.79, 1.1, 0.037, 0.039, 0.64, 0.66, chalk)
        ob = b.finish(outline=0.006)
        add_on_wall(ob, d["u"], d["v"], d["f"], d.get("z", 0.85))
        add_text_on_wall(d.get("text", "THE CORE KEEPS US WARM"), MARKER, 0.11, chalk, d["u"] - 0.45, d["v"], d["f"], d.get("z", 0.85) + 0.82, dy=0.04)
    elif t == "noticeboard":
        b = Builder("Noticeboard")
        b.box(-0.65, 0.65, 0.0, 0.03, 0.0, 0.85, toon("Cork", (0.56, 0.4, 0.24), noise=0.2, noise_scale=14))
        notes = [(-0.45, 0.45, (0.85, 0.83, 0.74)), (-0.1, 0.5, (0.86, 0.8, 0.56)), (0.3, 0.42, (0.85, 0.83, 0.74)),
                 (-0.35, 0.12, (0.78, 0.82, 0.86)), (0.15, 0.1, (0.85, 0.83, 0.74)), (0.45, 0.15, (0.9, 0.62, 0.55))]
        for i, (x, z, c) in enumerate(notes):
            b.box(x - 0.13, x + 0.13, 0.031, 0.034, z, z + 0.26 - 0.04 * (i % 2), flat(f"Note{i}", c))
            b.box(x - 0.015, x + 0.015, 0.034, 0.04, z + 0.22 - 0.04 * (i % 2), z + 0.25 - 0.04 * (i % 2), flat("Pin", (0.7, 0.12, 0.1)))
        ob = b.finish(outline=0.006)
        add_on_wall(ob, d["u"], d["v"], d["f"], d.get("z", 1.0))
        if d.get("title"):
            add_text_on_wall(d["title"], STENCIL, 0.09, flat("StencilPaint", (0.12, 0.12, 0.11)), d["u"], d["v"], d["f"], d.get("z", 1.0) + 0.9)
    elif t == "tvscreen":
        b = Builder("TVScreen")
        case = toon("TVCase", (0.32, 0.27, 0.2), noise=0.1)
        b.box(-0.08, 0.08, 0.0, 0.3, -0.05, 0.03, toon("Steel", (0.5, 0.5, 0.5)))       # bracket
        b.box(-0.36, 0.36, 0.1, 0.55, 0.03, 0.55, case)
        b.box(-0.27, 0.2, 0.55, 0.56, 0.1, 0.48, flat("TVGlass", (0.52, 0.6, 0.58)))
        b.box(-0.22, 0.12, 0.56, 0.562, 0.3, 0.33, flat("TVLine", (0.82, 0.86, 0.8)))
        b.cyl((0.28, 0.55, 0.38), (0.28, 0.57, 0.38), 0.03, toon("Knob", (0.15, 0.15, 0.14)), seg=8)
        b.cyl((0.28, 0.55, 0.25), (0.28, 0.57, 0.25), 0.03, toon("Knob", (0.15, 0.15, 0.14)), seg=8)
        ob = b.finish(outline=0.008)
        add_on_wall(ob, d["u"], d["v"], d["f"], d.get("z", 1.9))
    elif t == "liftdoor":
        b = Builder("LiftDoor")
        frame = toon("LiftFrame", (0.3, 0.33, 0.3), noise=0.08)
        b.box(-1.0, 1.0, 0.0, 0.08, 0.0, 2.45, frame)
        for x in (-0.47, 0.47):
            b.box(x - 0.46, x + 0.46, 0.08, 0.1, 0.02, 2.2, toon("LiftSteel", (0.42, 0.45, 0.42), noise=0.14, noise_scale=6))
        b.box(-0.6, 0.6, 0.1, 0.12, 1.1, 1.38, flat("OOOPaper", (0.86, 0.82, 0.7)))
        b.box(-0.9, 0.9, 0.1, 0.11, 0.3, 0.36, toon("Hazard", (0.75, 0.6, 0.12)))
        ob = b.finish(outline=0.01)
        add_on_wall(ob, d["u"], d["v"], d["f"], 0.0)
        add_text_on_wall("OUT OF ORDER", MARKER, 0.09, flat("Spray", (0.6, 0.07, 0.05)), d["u"], d["v"], d["f"], 1.2, dy=0.13)
        add_text_on_wall("LIFT 2", STENCIL, 0.16, flat("StencilPaint", (0.12, 0.12, 0.11)), d["u"], d["v"], d["f"], 2.25, dy=0.09)
    elif t == "redcross":
        b = Builder("RedCross")
        b.box(-0.3, 0.3, 0.0, 0.01, -0.3, 0.3, flat("CrossWhite", (0.86, 0.85, 0.8)))
        b.box(-0.2, 0.2, 0.01, 0.014, -0.06, 0.06, flat("RedCross", (0.7, 0.1, 0.08)))
        b.box(-0.06, 0.06, 0.01, 0.014, -0.2, 0.2, flat("RedCross", (0.7, 0.1, 0.08)))
        ob = b.finish(outline=0.006)
        add_on_wall(ob, d["u"], d["v"], d["f"], d.get("z", 1.7))
    elif t == "rationboard":
        b = Builder("RationBoard")
        b.box(-0.75, 0.75, 0.0, 0.03, 0.0, 1.0, toon("RationBoard", (0.2, 0.22, 0.2), noise=0.1))
        line = flat("ChalkWhite", (0.82, 0.82, 0.76))
        for k in range(6):
            b.box(-0.68, 0.68, 0.031, 0.033, 0.12 + k * 0.13, 0.13 + k * 0.13, line)
        for x in (-0.25, 0.2):
            b.box(x, x + 0.01, 0.031, 0.033, 0.1, 0.85, line)
        for k in range(5):
            b.box(0.3, 0.3 + 0.06 + 0.04 * (k % 3), 0.033, 0.035, 0.17 + k * 0.13, 0.22 + k * 0.13, line)
        ob = b.finish(outline=0.006)
        add_on_wall(ob, d["u"], d["v"], d["f"], d.get("z", 1.1))
        add_text_on_wall("RATIONS - WEEK 3", STENCIL, 0.08, flat("CrossWhite", (0.86, 0.85, 0.8)), d["u"], d["v"], d["f"], d.get("z", 1.1) + 0.88, dy=0.035)
    elif t == "switchboard":
        b = Builder("Switchboard")
        b.box(-0.35, 0.35, 0.0, 0.18, 0.0, 0.9, toon("SwitchGrey", (0.42, 0.45, 0.43), noise=0.08))
        for r in range(3):
            for c in range(5):
                b.box(-0.27 + c * 0.13, -0.19 + c * 0.13, 0.18, 0.2, 0.15 + r * 0.25, 0.27 + r * 0.25, toon("Breaker", (0.15, 0.15, 0.14)))
                b.box(-0.26 + c * 0.13, -0.2 + c * 0.13, 0.2, 0.202, 0.2 + r * 0.25, 0.24 + r * 0.25, flat("TapeLabel", (0.86, 0.82, 0.62)))
        ob = b.finish(outline=0.006)
        add_on_wall(ob, d["u"], d["v"], d["f"], d.get("z", 0.9))
    elif t == "toolboard":
        b = Builder("ToolBoard")
        b.box(-1.0, 1.0, 0.0, 0.03, 0.0, 1.0, toon("Pegboard", (0.62, 0.52, 0.36), noise=0.12, noise_scale=12))
        ghost = flat("ToolOutline", (0.22, 0.2, 0.18))
        tool = toon("ToolSteel", (0.48, 0.5, 0.5), noise=0.06)
        for i, (x, z, w, h, present) in enumerate(((-0.8, 0.5, 0.06, 0.4, False), (-0.6, 0.45, 0.08, 0.45, True), (-0.4, 0.55, 0.05, 0.35, False),
                                                   (-0.15, 0.4, 0.22, 0.08, False), (0.15, 0.6, 0.05, 0.3, True), (0.35, 0.5, 0.07, 0.42, False),
                                                   (0.6, 0.55, 0.18, 0.06, False), (0.8, 0.45, 0.05, 0.4, True), (-0.5, 0.12, 0.3, 0.06, False), (0.3, 0.12, 0.25, 0.08, False))):
            b.box(x - w / 2, x + w / 2, 0.031, 0.033, z, z + h, ghost)
            if present:
                b.box(x - w / 2 + 0.01, x + w / 2 - 0.01, 0.034, 0.05, z + 0.02, z + h - 0.02, tool)
        ob = b.finish(outline=0.006)
        add_on_wall(ob, d["u"], d["v"], d["f"], d.get("z", 1.0))
    elif t == "silomap":
        b = Builder("SiloMap")
        b.box(-0.8, 0.8, 0.0, 0.03, 0.0, 1.1, toon("BoardFrame", (0.4, 0.3, 0.18), noise=0.1))
        b.box(-0.74, 0.74, 0.03, 0.034, 0.06, 1.04, flat("MapPaper", (0.84, 0.8, 0.66)))
        ink = flat("MapInk", (0.2, 0.22, 0.3))
        for k in range(4):
            z = 0.2 + k * 0.2
            b.box(-0.55, 0.55, 0.035, 0.037, z, z + 0.012, ink)
            b.box(-0.55, -0.54, 0.035, 0.037, z, z + 0.14, ink)
            b.box(0.54, 0.55, 0.035, 0.037, z, z + 0.14, ink)
        b.box(-0.06, 0.06, 0.035, 0.037, 0.2, 0.96, ink)
        b.box(-0.02, 0.02, 0.035, 0.037, 0.02, 0.2, flat("MapRed", (0.65, 0.12, 0.1)))
        ob = b.finish(outline=0.006)
        add_on_wall(ob, d["u"], d["v"], d["f"], d.get("z", 1.0))
        add_text_on_wall("SILO 81 - GENERAL PLAN", STENCIL, 0.06, ink, d["u"], d["v"], d["f"], d.get("z", 1.0) + 0.98, dy=0.04)
    elif t == "steeldoor":
        b = Builder("SteelDoor")
        b.box(-0.75, 0.75, 0.0, 0.1, 0.0, 2.4, toon("LiftFrame", (0.3, 0.33, 0.3), noise=0.08))
        b.box(-0.65, 0.65, 0.1, 0.16, 0.05, 2.25, toon("BlastSteel", (0.4, 0.43, 0.4), noise=0.14, noise_scale=6))
        b.cyl((0.0, 0.16, 1.2), (0.0, 0.24, 1.2), 0.22, toon("ValveRed", (0.5, 0.12, 0.1)), seg=16)
        for z in (0.3, 2.0):
            b.box(-0.6, 0.6, 0.16, 0.18, z, z + 0.06, toon("Hazard", (0.75, 0.6, 0.12)))
        ob = b.finish(outline=0.01)
        add_on_wall(ob, d["u"], d["v"], d["f"], 0.0)
        if d.get("label"):
            add_text_on_wall(d["label"], STENCIL, 0.14, flat("StencilPaint", (0.12, 0.12, 0.11)), d["u"], d["v"], d["f"], 2.5, dy=0.05)
    elif t == "banner":
        b = Builder("Banner")
        b.box(-0.9, 0.9, 0.0, 0.01, 0.0, 0.5, toon("BannerRed", (0.5, 0.1, 0.08), noise=0.1, noise_scale=10))
        b.box(-0.95, 0.95, -0.02, 0.03, 0.48, 0.52, toon("Brass", (0.6, 0.48, 0.24), noise=0.06))
        ob = b.finish(outline=0.006)
        add_on_wall(ob, d["u"], d["v"], d["f"], d.get("z", 1.9))
        add_text_on_wall(d.get("text", "COUNCIL OF SILO 81"), STENCIL, 0.1, flat("BannerText", (0.88, 0.8, 0.55)), d["u"], d["v"], d["f"], d.get("z", 1.9) + 0.2, dy=0.015)
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
    elif t == "gauge_bank":
        b = Builder("GaugeBank")
        plate = toon("GaugePlate", (0.30, 0.33, 0.31), noise=0.1)
        brass = toon("Brass", (0.62, 0.48, 0.22), noise=0.06)
        face = flat("GaugeFace", (0.88, 0.86, 0.78))
        red = flat("GaugeRed", (0.75, 0.14, 0.10))
        b.box(-0.65, 0.65, 0.0, 0.04, -0.25, 0.35, plate)
        for i, x in enumerate((-0.45, -0.15, 0.15, 0.45)):
            b.cyl((x, 0.04, 0.08), (x, 0.09, 0.08), 0.10, brass, seg=14)
            b.cyl((x, 0.09, 0.08), (x, 0.10, 0.08), 0.085, face, seg=14)
            b.box(x - 0.01, x + 0.055, 0.101, 0.104, 0.08, 0.13, red)
            b.cyl((x, 0.03, -0.55), (x, 0.03, -0.02), 0.014, brass, seg=6)
        ob = b.finish(outline=0.006)
        add_on_wall(ob, d["u"], d["v"], d["f"], d.get("z", 1.15))
    elif t == "steam_vent":
        b = Builder("SteamVent")
        rust = toon("BoilerRust", (0.45, 0.24, 0.12), noise=0.2)
        stain = toon("SteamStain", (0.72, 0.68, 0.60), alpha_noise=(0.45, 5.0))
        b.box(-0.35, 0.35, 0.002, 0.006, 0.4, 1.8, stain)
        b.cyl((0.0, 0.0, 0.75), (0.0, 0.22, 0.75), 0.07, rust, seg=12)
        b.cyl((0.0, 0.16, 0.75), (0.0, 0.20, 0.75), 0.11, rust, seg=12)
        ob = b.finish(outline=0.006)
        add_on_wall(ob, d["u"], d["v"], d["f"], 0.0)


PIPE_STYLE = [   # the three gallery runs, top to bottom; radius of what you see, and its look
    dict(name="bore water", r=0.07, mat="PipeWater", joint=3.0, bands=None),
    dict(name="heating return", r=0.13, mat="PipeClad", joint=1.0, bands=None, core=0.09),
    dict(name="heating flow", r=0.1, mat="PipeFlow", joint=3.0, bands="PipeBandRed"),
]
FLOW_R = PIPE_STYLE[2]["r"]


def flange_pair(b, u, v, z, r, bolts=6):
    fl = toon("Flange", (0.35, 0.33, 0.3)); bolt = toon("Bolt", (0.3, 0.3, 0.3))
    R = r + 0.045
    b.cyl((u - 0.05, v, z), (u - 0.008, v, z), R, fl, seg=20)
    b.cyl((u + 0.008, v, z), (u + 0.05, v, z), R, fl, seg=20)
    for k in range(bolts):                                    # bolts through both flanges
        a = 2 * math.pi * (k + 0.5) / bolts
        dv, dz = math.cos(a) * (R - 0.022), math.sin(a) * (R - 0.022)
        b.cyl((u - 0.075, v + dv, z + dz), (u + 0.075, v + dv, z + dz), 0.011, bolt, seg=6)


def pipe_run(b, u0, u1, v, z, style, phase=0.0):
    """One gallery pipe in its own metal: painted steel, aluminium-clad, or bare black steel with
    red marker bands. Flange pairs at the joints."""
    r = style["r"]
    m = toon(style["mat"], (0.4, 0.4, 0.4))
    if style.get("core"):                                     # cladding: sheet sections with lapped seams
        u = u0
        while u < u1 - 0.01:
            e = min(u + style["joint"], u1)
            b.cyl((u, v, z), (e, v, z), r, m, seg=20)
            b.cyl((e - 0.03, v, z), (e, v, z), r + 0.006, m, seg=20)
            u = e
        u = u0 + 3.0 + phase
        while u < u1 - 0.3:
            b.cyl((u - 0.12, v, z), (u + 0.12, v, z), style["core"] + 0.012, toon("PipeSteel", (0.38, 0.38, 0.36)), seg=16)
            flange_pair(b, u, v, z, style["core"])
            u += 3.0
        return
    b.cyl((u0, v, z), (u1, v, z), r, m, seg=20)
    u = u0 + style["joint"] * 0.6 + phase
    while u < u1 - 0.3:
        flange_pair(b, u, v, z, r)
        if style.get("bands"):                                 # identification bands either side of the joint
            for du in (-0.55, 0.42):
                b.cyl((u + du, v, z), (u + du + 0.13, v, z), r + 0.003, toon(style["bands"], (0.5, 0.1, 0.1)), seg=20)
        u += style["joint"]


def valve_wheel(b, u, v, z, rad=0.15, axis_len=0.17):
    """Hand wheel facing the camera side (-v): rim, three spokes and a hub, like the pack's valve."""
    steel = toon("PipeSteel", (0.38, 0.38, 0.36), noise=0.08)
    red = toon("ValveRed", (0.5, 0.12, 0.1))
    b.cyl((u, v, z), (u, v - axis_len, z), 0.025, steel)
    y = v - axis_len
    n = 14
    for k in range(n):                                       # rim from short segments
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        b.cyl((u + rad * math.cos(a0), y, z + rad * math.sin(a0)), (u + rad * math.cos(a1), y, z + rad * math.sin(a1)), 0.018, red, seg=8)
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.5
        b.cyl((u, y, z), (u + rad * math.cos(a), y, z + rad * math.sin(a)), 0.012, red, seg=6)
    b.cyl((u, y + 0.02, z), (u, y - 0.03, z), 0.035, red, seg=10)


def build_pipes(d):
    b = Builder("Pipes")
    steel = toon("PipeSteel", (0.38, 0.38, 0.36), noise=0.08)
    v = d["v"] - 0.24
    gap = d.get("gap")
    for k, z in enumerate(PIPE_Z):
        st = PIPE_STYLE[k]
        if k == d.get("gap_run", 1) and gap:
            pipe_run(b, d["u0"], gap[0], v, z, st, phase=0.3 * k); pipe_run(b, gap[1], d["u1"], v, z, st, phase=0.3 * k)
        else:
            pipe_run(b, d["u0"], d["u1"], v, z, st, phase=0.3 * k)
        b.cyl((d["u0"], v, z), (d["u0"], d["v"], z), st.get("core", st["r"]), steel)     # into the wall
    u = d["u0"] + 0.8
    while u < d["u1"]:                                         # wall brackets with a strap round each pipe
        b.box(u - 0.04, u + 0.04, v + 0.05, d["v"], 0.25, 1.95, toon("Bracket", (0.3, 0.3, 0.28), noise=0.1))
        for k, z in enumerate(PIPE_Z):
            rr = PIPE_STYLE[k]["r"] + 0.012
            b.cyl((u - 0.025, v, z), (u + 0.025, v, z), rr, toon("Bracket", (0.3, 0.3, 0.28)), seg=16)
        u += 2.0
    for u in (2.9, 3.5):                                       # valves
        k = 1 if u < 3.2 else 2
        z = PIPE_Z[k]
        b.cyl((u - 0.1, v, z), (u + 0.1, v, z), PIPE_STYLE[k]["r"] + 0.05, toon("Flange", (0.35, 0.33, 0.3)), seg=16)
        valve_wheel(b, u, v - PIPE_STYLE[k]["r"] + 0.02, z, rad=0.14, axis_len=0.16)
    for u in (6.0, 14.0):                                      # gauges on the bore-water line
        b.cyl((u, v - 0.06, 1.75), (u, v - 0.22, 1.95), 0.012, steel)
        b.cyl((u, v - 0.21, 1.98), (u, v - 0.27, 1.98), 0.08, flat("GaugeFace", (0.86, 0.85, 0.8)), seg=16)
        b.cyl((u, v - 0.2, 1.98), (u, v - 0.215, 1.98), 0.088, toon("Flange", (0.35, 0.33, 0.3)), seg=16)
    ob = b.finish(outline=0.01)
    ob.matrix_world = ROT45 @ ob.matrix_world
    bg_objects.append(ob)
    # stencilled labels on the camera side (-v): dark on the green and the aluminium, white on the black steel
    dark, white = flat("PipeLabel", (0.08, 0.08, 0.08)), flat("PipeLabelW", (0.82, 0.8, 0.74))
    for (u, k, txt) in ((1.5, 0, "BORE WATER  >>"), (1.5, 1, "<<  HEATING RETURN"), (4.3, 2, "HEATING FLOW - GENERAL CIRCUIT  >> L2"),
                        (11.5, 1, "<<  HEATING RETURN"), (11.5, 2, "HEATING FLOW - GENERAL CIRCUIT  >> L2")):
        z = PIPE_Z[k]; r = PIPE_STYLE[k]["r"]
        add_text_on_wall(txt, STENCIL, 0.07 if k == 0 else 0.085, white if k == 2 else dark, u, v - r - 0.004, "-v", z - 0.035, dy=0.0, align="LEFT")


for d in LV["decor"]:
    decor(d)

# ============================================================ camera and rendering
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam)
cam.data.type = "ORTHO"
cam.rotation_euler = (math.pi / 2 - ELEV, 0, 0)
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


out = {"level": LEVEL, "name": LV["name"], "ppm": PPM, "elev_deg": CAMERA["elev_deg"], "rooms": [], "walls": [], "doors": [], "props": [],
       "inspect": LV["inspect"], "stairs": LV["stairs"], "spawns": LV["spawns"], "creatures": LV.get("creatures", []), "support": LV.get("support", []), "max_zoom": LV.get("max_zoom", 1.1), "blocked": LV["blocked"] + LV.get("holes", []),
       "bounds": LV["bounds"], "sprites": []}
for r in LV["rooms"]:
    out["rooms"].append({k: r[k] for k in ("id", "r") if k in r} | ({"name": r["name"]} if "name" in r else {}) | ({"dark": True} if r.get("dark") else {}))
for w in LV["walls"]:
    out["walls"].append({"a": list(w["a"]), "b": list(w["b"]), "h": w["h"], "openings": [list(o) for o in w.get("openings", [])]})

print("background objects", len(bg_objects))
if LV.get("godot_ground"):
    # outdoors the ground is drawn by Godot from small tiling textures (game/levels/_ground), which stays sharp
    # and costs a few MB instead of hundreds; Blender renders only the props
    for ob in bg_objects:
        ob.hide_render = True
    T = LV["terrain"][0]["r"] if LV.get("terrain") else LV["bounds"]
    xs, ys = [], []
    for (u, v) in ((T[0], T[2]), (T[0], T[3]), (T[1], T[2]), (T[1], T[3])):
        sx, sy = scr_uv(u, v); xs.append(sx); ys.append(sy)
    out["bg"] = {"none": True, "x0": round(min(xs)), "y0": round(min(ys)), "w": round(max(xs) - min(xs)), "h": round(max(ys) - min(ys))}
    G = {"ambient": list(LV.get("light", {}).get("ambient", (1, 1, 1))), "floors": [], "patches": [], "mounds": [], "pools": []}
    for t in LV.get("terrain", []):
        G["floors"].append({"r": t["r"], "tex": t["floor"]["tex"], "tint": list(t["floor"].get("tint", (1, 1, 1))), "layer": -1})
    for r in LV["rooms"]:
        G["floors"].append({"r": r["r"], "tex": r["floor"]["tex"], "tint": list(r["floor"].get("tint", (1, 1, 1))), "layer": r.get("layer", 0)})
    for d in LV["decor"]:
        if d["t"] == "patch":
            G["patches"].append({"r": d["r"], "ang": d.get("ang", 0.0), "rgb": list(d["rgb"]), "a": d.get("alpha", 0.85),
                                 "tex": d.get("tex", "softrect"), "layer": d.get("layer", 0)})
    for md in LV.get("mounds", []):
        G["mounds"].append([round(x, 3) for x in md[:5]])
    for (u, v, z, r, kd) in LV.get("light", {}).get("lamps", []):
        if kd != "cold":
            G["pools"].append({"u": u, "v": v, "r": r, "rgb": [round(c, 3) for c in LAMP[kd]]})
    G["smoke"] = []
    for p in LV["props"]:
        if p["t"] == "burn_barrel":
            G["smoke"].append({"u": p["u"], "v": p["v"], "z": 1.2, "k": 1.0})
        elif p["t"] == "junk_shack":
            fu, fv = FACING[p["f"]]
            G["smoke"].append({"u": p["u"] + fu * 0.5, "v": p["v"] + fv * 0.5, "z": 3.7, "k": 0.7})
        elif p["t"] == "scrap_house" and p.get("chimney", True):
            fu, fv = FACING[p["f"]]
            L_, H_ = p.get("L", 4.4), p.get("H", 2.7)
            px = (L_ / 2 - 0.6) if p.get("seed", 0) % 3 else (-L_ / 2 + 0.6)
            G["smoke"].append({"u": p["u"] + fu * 0.45 + fv * px, "v": p["v"] + fv * 0.45 - fu * px, "z": H_ + 0.55 + 1.25,
                               "k": 1.0 if p.get("name") == "Smokehouse" else 0.6})
    G["smoke"] += LV.get("smoke", [])
    out["ground"] = G
elif LV.get("bg_scale"):
    # big outdoor level: the ground renders at a fraction of the sprite resolution and is cut into tiles
    # (texture limits and memory on the web); empty tiles are dropped. Props stay at full resolution.
    from PIL import Image as _Img
    k = LV["bg_scale"]
    rect = screen_rect(bg_objects)
    TS = 2048                                     # tile size in output pixels
    step = int(TS / k)                            # in full-resolution screen pixels
    sc.render.resolution_percentage = int(round(k * 100))
    tiles = []
    for ty in range(rect[1], rect[3], step):
        for tx in range(rect[0], rect[2], step):
            sub = [tx, ty, min(tx + step, rect[2]), min(ty + step, rect[3])]
            name = "bg_%02d_%02d.png" % ((ty - rect[1]) // step, (tx - rect[0]) // step)
            render(bg_objects, os.path.join(DIR, name), rect=sub)
            im = _Img.open(os.path.join(DIR, name))
            if im.getchannel("A").getbbox() is None:
                os.remove(os.path.join(DIR, name))
                continue
            tiles.append({"file": name, "x0": sub[0], "y0": sub[1]})
            print("bg tile", name, im.size, flush=True)
    sc.render.resolution_percentage = 100
    out["bg"] = {"tiles": tiles, "scale": round(1.0 / k, 4), "x0": rect[0], "y0": rect[1],
                 "w": rect[2] - rect[0], "h": rect[3] - rect[1]}
    print("bg tiles", len(tiles))
else:
    rect = render(bg_objects, os.path.join(DIR, "bg.png"))
    out["bg"] = {"file": "bg.png", "x0": rect[0], "y0": rect[1]}
for ob in bg_objects:
    ob.hide_render = True

# ============================================================ sprites
# Furniture made in Tripo from Gemini reference paintings (props3d/*.glb). rot turns each model's
# front to the kit's +y; fit/size give it real-world scale. Missing files fall back to the kit models.
GLB_PROPS = {
    "bunk_a": dict(file="silo81_bunk_a.glb", rot=180, fit="x", L=2.0, D=0.9),
    "bunk_b": dict(file="silo81_bunk_b.glb", rot=180, fit="x", L=2.0, D=0.9),
    "bed": dict(file="silo81_bed_player.glb", rot=180, fit="x", L=2.0, D=0.9),
    "locker": dict(file="silo81_locker.glb", rot=180, fit="x", L=1.0, D=0.5),
    "stall": dict(file="silo81_toilet_stall.glb", rot=180, fit="z", H=2.05, L=0.9, D=1.2),
    "shelf": dict(file="silo81_linen_shelf.glb", rot=180, fit="z", H=1.9, L=1.1, D=0.45),
    # leftover furniture (Gemini reference -> Tripo); "box" stretches to the procedural footprint
    "chair": dict(file="silo81_chair.glb", rot=180, fit="z", H=0.9, L=0.5, D=0.5),
    "stool": dict(file="silo81_stool.glb", rot=180, fit="z", H=0.62, L=0.36, D=0.36),
    "desk": dict(file="silo81_desk.glb", rot=180, fit="box", L=1.2, D=0.6, H=0.95),
    "schooldesk": dict(file="silo81_schooldesk.glb", rot=180, fit="box", L=1.1, D=0.85, H=0.8),
    "table": dict(file="silo81_table.glb", rot=144.7, fit="box", L=1.2, D=0.7, H=0.76),
    "bench": dict(file="silo81_bench.glb", rot=180, fit="box", L=2.2, D=0.32, H=0.45),
    "crate": dict(file="silo81_crate.glb", rot=180, fit="x", L=0.62, D=0.62),
    "washbasin": dict(file="silo81_washbasin.glb", rot=180, fit="z", H=0.5, L=0.56, D=0.45, lift=0.38),
    "kshelf": dict(file="silo81_shelf.glb", rot=180, fit="z", H=1.8, L=1.1, D=0.45, tint=(0.93, 0.98, 1.05)),
    "files": dict(file="silo81_filing.glb", rot=0, fit="box", L=1.1, D=0.42, H=1.9, tint=(0.92, 0.98, 1.06)),
    "workbench": dict(file="silo81_workbench.glb", rot=180, fit="box", L=1.8, D=0.7, H=0.95),
    "stove": dict(file="silo81_stove.glb", rot=180, fit="box", L=1.6, D=0.8, H=0.95, tint=(0.9, 0.96, 1.06)),
    "counter": dict(file="silo81_counter.glb", rot=180, fit="box", L=2.0, D=0.62, H=0.92),
    "pump": dict(file="silo81_pump.glb", rot=180, fit="x", L=1.2, D=0.7, tint=(0.82, 1.04, 1.06)),        # industrial teal
    "toolbox": dict(file="silo81_toolbox.glb", rot=180, fit="x", L=1.0, D=0.3),
    "medcab": dict(file="silo81_medcab.glb", rot=180, fit="z", H=1.8, L=0.9, D=0.42),
    # ---- Junk Town / the road (Tripo Studio canvases, textured; docs/JUNK_TOWN_ASSETS.md)
    "jt_van_ladder": dict(file="junk_town/jt_van_ladder.glb", rot=0, fit="x", L=4.6, D=2.2),
    "jt_van_a": dict(file="junk_town/jt_van_a.glb", rot=0, fit="x", L=4.6, D=2.2),
    "jt_van_b": dict(file="junk_town/jt_van_b.glb", rot=0, fit="z", H=2.6, L=3.6, D=3.2),
    "jt_car": dict(file="junk_town/jt_car.glb", rot=0, fit="x", L=4.2, D=1.8),
    "jt_plank_fence": dict(file="junk_town/jt_plank_fence.glb", rot=90, fit="x", L=4.2, D=0.9),
    "jt_tower": dict(file="junk_town/jt_tower.glb", rot=0, fit="z", H=6.2, L=2.6, D=1.8),
    "jt_chainlink": dict(file="junk_town/jt_chainlink.glb", rot=90, fit="x", L=3.4, D=0.25),
    "jt_tarp_shack_a": dict(file="junk_town/jt_tarp_shack_a.glb", rot=0, fit="x", L=4.8, D=4.8),
    "jt_tarp_shack_b": dict(file="junk_town/jt_tarp_shack_b.glb", rot=0, fit="x", L=4.8, D=4.4),
    "jt_tarp_shack_c": dict(file="junk_town/jt_tarp_shack_c.glb", rot=0, fit="x", L=4.4, D=4.2),
    "jt_cabin_a": dict(file="junk_town/jt_cabin_a.glb", rot=0, fit="x", L=5.0, D=4.8),
    "jt_cabin_b": dict(file="junk_town/jt_cabin_b.glb", rot=0, fit="x", L=5.4, D=4.2),
    "jt_cabin_c": dict(file="junk_town/jt_cabin_c.glb", rot=0, fit="x", L=5.2, D=4.2)}


def glb_box(key, L=None, D=None, H=None):
    """A "box"-fit GLB stretched to this instance's size (long tables, short counters)."""
    c = dict(GLB_PROPS[key]); c.update({k: v for k, v in (("L", L), ("D", D), ("H", H)) if v is not None})
    return kit.glb_prop(key, c["file"], c["L"], c["D"], rot=c["rot"], fit=c["fit"], H=c.get("H"), tint=c.get("tint"))


def joined(parts, name):
    """Join (object, x-offset) parts into one object, keeping one ink outline."""
    obs = []
    for ob, dx in parts:
        ob.location.x += dx
        obs.append(ob)
    for ob in obs[1:]:
        for m in list(ob.modifiers):
            ob.modifiers.remove(m)
    with bpy.context.temp_override(active_object=obs[0], selected_editable_objects=obs, object=obs[0]):
        bpy.ops.object.join()
    ob = obs[0]; ob.name = name
    mats = list(ob.data.materials)
    ink = [i for i, mm in enumerate(mats) if mm and mm.name.startswith("Ink")]
    if ink and ink[0] != len(mats) - 1:            # the outline material must stay addressable by offset
        ob.data.materials.append(mats[ink[0]])
    for m in ob.modifiers:
        if m.type == "SOLIDIFY":
            m.material_offset = len(ob.data.materials) - 1
    return ob


def sinks_fn(p):
    n = p.get("n", 3)
    if not have_glb("washbasin"):
        return kit.sinks("Sinks", n)
    L = 0.7 * n
    parts = [(glb("washbasin")[0], -L / 2 + 0.35 + i * 0.7) for i in range(n)]
    return joined(parts, "Sinks"), (L, 0.45)


def toolbox_fn(p):
    return glb("toolbox") if have_glb("toolbox") else kit.toolbox("Toolbox")   # Tripo box includes the gas bottles


def _front_text(body, font, size, rgb, x, y, z, rot=0.0):
    """Lettering on a prop's front face (+y), for signs."""
    t = text_obj(body, font, size, flat("Sign_" + body[:8], rgb))
    t.matrix_world = (Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.pi, 4, "Z") @ Matrix.Rotation(math.radians(90), 4, "X")
                      @ Matrix.Rotation(math.radians(rot), 4, "Z"))
    return t


def portal_fn(p):
    ob, size = kit.silo_portal("SiloPortal")
    return [ob, _front_text("SILO 81", STENCIL, 0.62, (0.80, 0.78, 0.70), 0.0, 1.41, 4.75),
            _front_text("SURFACE ACCESS", STENCIL, 0.24, (0.80, 0.78, 0.70), 0.0, 1.41, 4.25),
            _front_text("SEALED FROM INSIDE", MARKER, 0.16, (0.20, 0.19, 0.18), -3.1, 1.41, 1.5, rot=-6)], size


def billboard_fn(p):
    ob, size = kit.billboard("Billboard")
    ink = (0.14, 0.24, 0.26)
    return [ob, _front_text("NEW MERIDIAN", OSWALD, 0.72, ink, -0.4, 0.44, 4.95),
            _front_text("40 km", OSWALD, 0.9, (0.55, 0.20, 0.12), -1.4, 0.44, 3.95),
            _front_text("->", OSWALD, 0.9, (0.55, 0.20, 0.12), 1.2, 0.44, 3.95),
            _front_text("EVACUATION ROUTE", OSWALD, 0.24, (0.86, 0.85, 0.80), -0.6, 0.44, 3.32)], size


def kiosk_fn(p):
    ob, size = kit.rest_kiosk("Kiosk")
    return [ob, _front_text("NO FUEL", OSWALD, 0.5, (0.60, 0.17, 0.12), 0.0, 4.0 * 0.5 + 0.07, 3.82),
            _front_text("CAFE  -  TYRES  -  24h", OSWALD, 0.18, (0.84, 0.83, 0.78), -1.45, 4.04, 2.55)], size


def scrap_house_fn(p):
    kw = {k: p[k] for k in ("seed", "L", "D", "H", "pal", "door", "windows", "awning", "tank", "garage", "cross", "chimney", "lean", "porch", "sign_board") if k in p}
    if "windows" in kw: kw["windows"] = tuple(kw["windows"])
    ob, size = kit.scrap_house("ScrapHouse", **kw)
    out = [ob]
    if p.get("sign") and p.get("sign_board"):
        x, z, w, h = p["sign_board"]
        out.append(_front_text(p["sign"], MARKER, min(0.28, h * 0.62), (0.16, 0.14, 0.12), x, p.get("D", 4.0) + 0.105, z - h * 0.22))
    return out, size


def glbp_fn(p):
    """A Tripo model from GLB_PROPS by key; p may override rot (turn) and mirror."""
    c = dict(GLB_PROPS[p["key"]])
    sc = p.get("size", 1.0)                    # per-placement scale (a smaller shed from the same shack model)
    ob, size = kit.glb_prop(p["key"], c["file"], c.get("L", 1.0) * sc, c.get("D", 1.0) * sc, rot=c["rot"], fit=c["fit"], H=c.get("H"),
                            mirror=p.get("mirror", False), tint=c.get("tint"))
    if p.get("turn"):                         # turn after sizing (a turn before would change what "length" means)
        me = ob.data
        cy = size[1] / 2
        me.transform(Matrix.Translation((0, cy, 0)) @ Matrix.Rotation(math.radians(p["turn"]), 4, "Z") @ Matrix.Translation((0, -cy, 0)))
        ys = [v.co.y for v in me.vertices]
        me.transform(Matrix.Translation((0, -min(ys), 0)))
    return ob, size


def have_glb(key):
    return os.path.exists(os.path.join(kit.GLB_DIR, GLB_PROPS[key]["file"]))


def glb(key, mirror=False):
    c = GLB_PROPS[key]
    ob, size = kit.glb_prop(key, c["file"], c.get("L", 1.0), c.get("D", 1.0), rot=c["rot"], fit=c["fit"], H=c.get("H"), mirror=mirror,
                            tint=c.get("tint"))
    if c.get("lift"):                                  # wall-hung (washbasins)
        ob.data.transform(Matrix.Translation((0, 0, c["lift"])))
    return ob, size


def bunk_fn(p):
    if p.get("stripped"):
        return kit.bunk("Bunk", p.get("k", 0), True)
    key = "bunk_a" if p.get("k", 0) % 2 == 0 else "bunk_b"
    if not have_glb(key):
        key = "bunk_a" if have_glb("bunk_a") else "bunk_b"
    return glb(key, mirror=p.get("k", 0) % 4 >= 2) if have_glb(key) else kit.bunk("Bunk", p.get("k", 0), False)


PROP_FN = {
    "bunk": bunk_fn,
    "bed": lambda p: glb("bed") if p.get("mine") and have_glb("bed") else kit.bed("Bed", p.get("k", 1)),
    "locker": lambda p: glb("locker") if have_glb("locker") and p.get("w", 0.55) >= 0.9 and not p.get("open") else kit.locker("Locker", p.get("w", 0.55), p.get("open", False), p.get("k", 0)),
    "desk": lambda p: glb("desk") if have_glb("desk") else kit.desk("Desk"),
    "chair": lambda p: kit.chair("Chair", True) if p.get("overturned") or not have_glb("chair") else glb("chair"),
    "table": lambda p: glb_box("table", L=p.get("L", 1.2)) if have_glb("table") else kit.table("Table", p.get("L", 1.2)),
    "stool": lambda p: glb("stool") if have_glb("stool") else kit.stool("Stool"),
    "curtain": lambda p: kit.curtain("Curtain", p.get("k", 0)),
    "toolbox": toolbox_fn,
    "crate": lambda p: glb("crate") if have_glb("crate") else kit.crate("Crate"),
    "bucket": lambda p: kit.bucket("Bucket"),
    "shelf": lambda p: glb("shelf") if p.get("linen") and have_glb("shelf") else glb("kshelf") if have_glb("kshelf") else kit.shelf("Shelf"),
    "sinks": sinks_fn,
    "stall": lambda p: glb("stall") if have_glb("stall") else kit.stall("Stall"),
    "laundry": lambda p: kit.laundry("Laundry", p.get("k", 0)),
    "pump": lambda p: glb("pump") if have_glb("pump") else kit.pump("Pump"),
    "workbench": lambda p: glb("workbench") if have_glb("workbench") else kit.workbench("Workbench"),
    "bench": lambda p: glb_box("bench", L=p.get("L", 2.2)) if have_glb("bench") else kit.bench("Bench", p.get("L", 2.2)),
    "stove": lambda p: glb("stove") if have_glb("stove") else kit.stove("Stove"),
    "counter": lambda p: glb_box("counter", L=p.get("L", 2.0)) if have_glb("counter") and not p.get("hatch") else kit.counter("Counter", p.get("L", 2.0), p.get("hatch", False)),
    "cabinet": lambda p: kit.cabinet("Cabinet"),
    "medscreen": lambda p: kit.medscreen("Screen"),
    "medcab": lambda p: glb("medcab") if have_glb("medcab") else kit.medcab("MedCabinet"),
    "schooldesk": lambda p: glb("schooldesk") if have_glb("schooldesk") else kit.schooldesk("SchoolDesk"),
    "sacks": lambda p: kit.sacks("Sacks"),
    "files": lambda p: glb("files") if have_glb("files") else kit.file_shelf("Files", p.get("k", 0)),
    "terminal": lambda p: kit.terminal("Terminal"),
    "radioset": lambda p: kit.radioset("Radio"),
    "maptable": lambda p: kit.maptable("MapTable"),
    "floorlamp": lambda p: kit.floorlamp("FloorLamp"),
    "safe": lambda p: kit.safe("Safe"),
    "lathe": lambda p: kit.lathe("Lathe"),
    "monitors": lambda p: kit.monitors("Monitors"),
    "corrugated_fence": lambda p: kit.corrugated_fence("Fence", p.get("L", 2.6), p.get("H", 2.2)),
    "junk_watchtower": lambda p: kit.junk_watchtower("Watchtower"),
    "junk_shack": lambda p: kit.junk_shack("Shack", p.get("seed", 0), p.get("L", 3.0), p.get("D", 2.4)),
    "market_stall": lambda p: kit.market_stall("Stall", p.get("seed", 0)),
    "firewood": lambda p: kit.firewood("Firewood"),
    "laundry": lambda p: kit.laundry_line("Laundry", p.get("L", 4.0), p.get("seed", 0)),
    "yard_wreck": lambda p: kit.yard_wreck("YardWreck", p.get("seed", 0)),
    "animal_pen": lambda p: kit.animal_pen("AnimalPen"),
    "goat": lambda p: kit.goat("Goat", p.get("pose", 0)),
    "junk_car_wall": lambda p: kit.junk_car_wall("CarWall", p.get("L", 6.0), p.get("tall", True), p.get("seed", 0)),
    "junk_gate": lambda p: kit.junk_gate("JunkGate"),
    "junk_gate_open": lambda p: kit.junk_gate_open("JunkGateOpen"),
    "glbp": lambda p: glbp_fn(p),
    "scrap_house": lambda p: scrap_house_fn(p),
    "silo_portal": lambda p: portal_fn(p),
    "guard_shack": lambda p: kit.guard_shack("GuardShack"),
    "sandbag_nest": lambda p: kit.sandbag_nest("Sandbags"),
    "road_barrier": lambda p: kit.road_barrier("Barrier", p.get("L", 4.0)),
    "power_pylon": lambda p: kit.power_pylon("Pylon", p.get("lean", 11.0)),
    "fallen_pylon": lambda p: kit.fallen_pylon("FallenPylon", p.get("L", 14.0)),
    "box_trailer": lambda p: kit.box_trailer("Trailer", p.get("cab", 48.0)),
    "billboard": lambda p: billboard_fn(p),
    "army_truck_side": lambda p: kit.army_truck_side("ArmyTruck"),
    "burned_bus": lambda p: kit.burned_bus("Bus"),
    "container": lambda p: kit.shipping_container("Container", p.get("paint", "red")),
    "guardrail": lambda p: kit.guardrail("Guardrail", p.get("L", 6.0), p.get("bent", 0.0)),
    "dead_tree": lambda p: kit.dead_tree("DeadTree", p.get("seed", 0), p.get("H", 6.0)),
    "rest_kiosk": lambda p: kiosk_fn(p),
    "fuel_pump": lambda p: kit.fuel_pump("FuelPump", p.get("broken", False)),
    "grave": lambda p: kit.grave_marker("Grave", p.get("seed", 0)),
    "notice_board": lambda p: kit.notice_board("NoticeBoard"),
    "oil_drum": lambda p: kit.oil_drum("OilDrum", p.get("k", 0)),
    "burn_barrel": lambda p: kit.burn_barrel("BurnBarrel"),
    "tyre_stack": lambda p: kit.tyre_stack("Tyres", p.get("n", 3)),
    "scrap_pile": lambda p: kit.scrap_pile("ScrapPile", p.get("seed", 0)),
    "boiler_assembly": lambda p: kit.boiler_assembly("BoilerAssembly"),
    "control_panel": lambda p: kit.control_panel("ControlPanel"),
    "temp_monitor": lambda p: kit.temp_monitor("TempMonitor"),
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


if LV.get("sprite_scale"):
    sc.render.resolution_percentage = int(round(LV["sprite_scale"] * 100))
    out["sprite_scale"] = LV["sprite_scale"]
for i, p in enumerate(LV["props"]):
    if p["t"] in ("bunk", "curtain", "locker"):
        p["k"] = int(p.get("k", 0)) * 7 + int(abs(p["u"] * 13 + p["v"] * 29)) % 23
    if p["t"] == "bed" and p.get("id") == "bed_player":
        p["mine"] = True                               # the Tripo bed (granny-square blanket) is only yours
    if p["t"] == "shelf" and "Linen" in p.get("name", ""):
        p["linen"] = True                              # (kept in the sprite key: linen and kitchen shelves differ)
    if p["t"] == "bunk" and not p.get("stripped") and have_glb("bunk_a"):
        p["k"] = p["k"] % 4                            # two Tripo bunks, each plain or mirrored
    if p["t"] == "locker" and have_glb("locker") and p.get("w", 0.55) >= 0.9 and not p.get("open"):
        p["k"] = 0
    keyargs = tuple(sorted((k, repr(v)) for k, v in p.items() if k not in ("u", "v", "name", "text", "id", "sort_at", "noblock", "posts")))

    def build(p=p):
        ob, size = PROP_FN[p["t"]](p)
        objs = ob if isinstance(ob, list) else [ob]
        place(objs, 0.0, 0.0, p["f"])
        return objs

    ob, size = None, None
    # footprint needs the size: build a throwaway to measure only on first use
    f, off, wh = sprite_for(keyargs, build)
    L, Dp = {"bunk": (2.0, 0.9), "bed": (2.0, 0.9), "locker": (p.get("w", 0.55), 0.5), "desk": (1.2, 0.6), "chair": (0.5, 0.5),
             "table": (p.get("L", 1.2), 0.7), "stool": (0.36, 0.36), "curtain": (0.65, 0.1), "toolbox": (1.0, 0.3), "crate": (0.62, 0.62),
             "bucket": (0.34, 0.34), "shelf": (1.1, 0.45), "sinks": (0.7 * p.get("n", 3), 0.45), "stall": (0.9, 1.2), "laundry": (1.8, 0.25),
             "pump": (1.2, 0.7), "workbench": (1.8, 0.7), "bench": (p.get("L", 2.2), 0.32), "stove": (1.6, 0.8),
             "counter": (p.get("L", 2.0), 0.62), "cabinet": (0.48, 0.62), "medscreen": (1.8, 0.2), "medcab": (0.9, 0.42),
             "schooldesk": (1.1, 0.85), "sacks": (1.1, 0.6), "files": (1.1, 0.42), "terminal": (1.4, 0.7), "radioset": (1.6, 0.6),
             "maptable": (1.8, 1.1), "floorlamp": (0.3, 0.3), "safe": (0.7, 0.6), "lathe": (1.8, 0.6),
             "monitors": (1.3, 0.65), "boiler_assembly": (3.4, 1.6), "control_panel": (1.8, 0.62), "temp_monitor": (1.5, 0.65),
             "corrugated_fence": (p.get("L", 2.6), 0.14), "junk_watchtower": (2.4, 2.4), "junk_shack": (p.get("L", 3.0), p.get("D", 2.4)), "scrap_house": (p.get("L", 4.4) + 2 * (1.75 if p.get("tank") else 1.3 if p.get("lean") else 0.0), p.get("D", 4.0) + p.get("awning", 0.0)), "market_stall": (2.8, 1.9), "laundry": (p.get("L", 4.0), 0.3), "firewood": (1.6, 0.7), "yard_wreck": (4.8, 1.9),
             "animal_pen": (4.2, 3.0), "goat": (0.95, 0.60),
             "junk_car_wall": (p.get("L", 6.0), 1.8), "junk_gate": (4.6, 0.4), "junk_gate_open": (4.6, 0.4),
             "oil_drum": (0.58, 0.58), "burn_barrel": (0.58, 0.58), "tyre_stack": (0.66, 0.66), "scrap_pile": (2.0, 1.6),
             "glbp": (GLB_PROPS.get(p.get("key"), {}).get("L", 1.0) * p.get("size", 1.0), GLB_PROPS.get(p.get("key"), {}).get("D", 1.0) * p.get("size", 1.0)),
             "silo_portal": (9.0, 1.4), "guard_shack": (3.0, 2.6), "sandbag_nest": (3.4, 3.2), "road_barrier": (p.get("L", 4.0) + 0.6, 0.6),
             "power_pylon": (4.2, 4.2), "fallen_pylon": (p.get("L", 14.0), 2.8), "box_trailer": (11.5, 2.5), "billboard": (6.4, 0.9),
             "army_truck_side": (6.8, 3.0), "burned_bus": (10.5, 2.5), "container": (6.0, 2.45), "guardrail": (p.get("L", 6.0), 0.4 + p.get("bent", 0.0)),
             "dead_tree": (0.8, 0.8), "rest_kiosk": (6.0, 4.0), "fuel_pump": (0.9, 0.7), "grave": (0.9, 1.9), "notice_board": (2.0, 0.3)}[p["t"]]
    if p.get("turn"):                                  # a turned prop covers its turned bounding box
        ta = math.radians(p["turn"])
        L, Dp = abs(L * math.cos(ta)) + abs(Dp * math.sin(ta)), abs(L * math.sin(ta)) + abs(Dp * math.cos(ta))
    fp = footprint(p["u"], p["v"], p["f"], L, Dp)
    cu, cv = (fp[0] + fp[1]) / 2, (fp[2] + fp[3]) / 2
    # long outdoor walls sort by a corner, not their centre: "far" walls behind everything inside the
    # ring (the corner nearest the far edge), "near" walls in front of it (the corner nearest the camera)
    if p.get("sort_at") == "far":
        cu, cv = fp[1], fp[3]
    elif p.get("sort_at") == "near":
        cu, cv = fp[0], fp[2]
    if p.get("noblock"):                               # passable (an open gate): block only its posts
        out["blocked"] += p.get("posts", [])
        fp = [round(cu, 3), round(cu, 3), round(cv, 3), round(cv, 3)]
    sx, sy = scr_uv(p["u"], p["v"])
    srt = scr_uv(cu, cv)
    entry = {"type": p["t"], "footprint": fp, "sprite": f, "x0": round(sx + off[0], 1), "y0": round(sy + off[1], 1),
             "sort": [round(srt[0], 1), round(srt[1], 1)]}
    for k in ("id", "name", "text"):
        if k in p:
            entry[k] = p[k]
    out["props"].append(entry)


def door_obj(kind, is_open, label="2-D"):
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
        txt = text_obj(label, STENCIL, 0.2, flat("DoorStencil", (0.82, 0.78, 0.66)))
        txt.matrix_world = Matrix.Translation((0, th / 2 + 0.004, 1.6)) @ Matrix.Rotation(math.pi, 4, "Z") @ Matrix.Rotation(math.radians(90), 4, "X")
        return [ob, txt]
    return [ob]


for d in LV["doors"]:
    facing = "-v" if d["axis"] == "u" else "-u"        # the door's front faces the corridor (camera side)
    ent = {k: d[k] for k in d if k not in ("axis",)}
    for state in ("closed", "open"):
        def build(d=d, state=state, facing=facing):
            objs = door_obj(d["kind"], state == "open", d.get("label", "2-D"))
            ang = kit.facing_frame(facing)
            for o in objs:
                o.matrix_world = Matrix.Rotation(ang, 4, "Z") @ o.matrix_world
            return objs
        f, off, wh = sprite_for(("door", d["kind"], state, facing, d.get("label", "2-D")), build)
        sx, sy = scr_uv(d["u"], d["v"])
        ent["spr_" + state] = {"sprite": f, "x0": round(sx + off[0], 1), "y0": round(sy + off[1], 1)}
    srt = scr_uv(d["u"], d["v"])
    ent["sort"] = [round(srt[0], 1), round(srt[1], 1)]
    out["doors"].append(ent)

if "pipe" in LV:
    pd = LV["pipe"]
    v = pd["v"] - 0.24
    gap = tuple(pd["gap"])
    Z = pd["z"]
    hu = pd["u"]                                          # centre of the hole

    R_OUT, R_IN = FLOW_R, FLOW_R - 0.013
    BITE_U = hu + 0.02
    D = Vector((0.0, -1.0, -0.12)).normalized()             # the worm bit from the front, a little low
    T2 = D.cross(Vector((1.0, 0.0, 0.0))).normalized()
    C0 = Vector((BITE_U, v, Z)) + D * R_OUT

    def tube(b, u0, u1, outer, inner, seg=40):
        """Hollow pipe section in plan space (axis along u), open ends capped with rings."""
        bm = b.bm
        io, ii = b.mi(outer), b.mi(inner)
        def ring(u, r):
            return [bm.verts.new((u, v + r * math.cos(2 * math.pi * k / seg), Z + r * math.sin(2 * math.pi * k / seg))) for k in range(seg)]
        o0, o1, i0, i1 = ring(u0, R_OUT), ring(u1, R_OUT), ring(u0, R_IN), ring(u1, R_IN)
        for k in range(seg):
            k2 = (k + 1) % seg
            bm.faces.new([o0[k], o0[k2], o1[k2], o1[k]]).material_index = io
            bm.faces.new([i0[k], i1[k], i1[k2], i0[k2]]).material_index = ii
            bm.faces.new([o0[k], i0[k], i0[k2], o0[k2]]).material_index = io
            bm.faces.new([o1[k], o1[k2], i1[k2], i1[k]]).material_index = io

    def bite_cutter():
        """Overlapping spheres: one deep bite plus a ring of tooth scallops and shallow tooth gouges."""
        bm = bmesh.new()
        rng = np.random.default_rng(7)
        def sph(c, r):
            bmesh.ops.create_uvsphere(bm, u_segments=18, v_segments=10, radius=r, matrix=Matrix.Translation(c))
        sph(C0 + D * 0.045, 0.072)
        n = 11
        for k in range(n):
            a = 2 * math.pi * k / n
            c = C0 + Vector((1, 0, 0)) * (0.085 * math.cos(a)) + T2 * (0.052 * math.sin(a)) + D * (0.012 + 0.008 * rng.random())
            sph(c, 0.026 + 0.008 * rng.random())
        for k in range(9):                                    # tooth gouges around the bite
            a = 2 * math.pi * (k + 0.5) / 9 + rng.normal(0, 0.15)
            c = C0 + Vector((1, 0, 0)) * (0.13 * math.cos(a)) + T2 * (0.085 * math.sin(a)) + D * 0.006
            sph(c, 0.011 + 0.004 * rng.random())
        me = bpy.data.meshes.new("BiteCutter"); bm.to_mesh(me); bm.free()
        me.materials.append(toon("BiteSteel", (0.7, 0.7, 0.72)))
        ob = bpy.data.objects.new("BiteCutter", me); sc.collection.objects.link(ob)
        return ob

    def outlined(ob, outline=0.01):
        ob.data.materials.append(kit.ink())
        sol = ob.modifiers.new("Outline", "SOLIDIFY"); sol.thickness = -outline
        sol.use_flip_normals = True; sol.use_rim = False; sol.material_offset = len(ob.data.materials) - 1

    def scraps(b):
        """Steel shavings and chips of black paint under the breach: they stay after the repair."""
        rng = np.random.default_rng(81)
        mats = (toon("BiteSteel", (0.7, 0.7, 0.72)), toon("PipeFlow", (0.4, 0.4, 0.4)))
        for k in range(16):
            uu = hu - 0.4 + rng.random() * 0.8
            vv = v - 0.25 - rng.random() * 0.55
            a = rng.random() * math.pi
            l = 0.012 + rng.random() * 0.025
            du, dv = math.cos(a) * l / 2, math.sin(a) * l / 2
            b.cyl((uu - du, vv - dv, 0.004), (uu + du, vv + dv, 0.006), 0.0035, mats[k % 2], seg=5)

    def bitten_tube(b):
        """The pipe section with a bite out of it: a fine grid of the steel surface, faces inside a
        scalloped outline (one scallop per tooth) removed, a raw steel wall round the torn edge and
        the dark inside of the pipe showing through."""
        bm = b.bm
        pf, bs = b.mi(toon("PipeFlow", (0.4, 0.4, 0.4))), b.mi(toon("BiteSteel", (0.7, 0.7, 0.72)))
        inside = b.mi(toon("PipeInsideRust", (0.2, 0.11, 0.06), noise=0.35, noise_scale=40, lit=0.9, mid=0.75, shade=0.6))
        NU, NA = 120, 72
        us = [gap[0] + (gap[1] - gap[0]) * i / NU for i in range(NU + 1)]
        ang = [2 * math.pi * k / NA for k in range(NA)]
        a_bite = math.atan2(D.z, D.y)                         # angle of the bite centre round the pipe
        rng = np.random.default_rng(11)
        jit = rng.normal(0, 0.06, 64)
        def inside_bite(u, a, grow=1.0):
            du = (u - BITE_U) / 0.13
            da = math.atan2(math.sin(a - a_bite), math.cos(a - a_bite)) * R_OUT / 0.075
            r = math.hypot(du, da); th = math.atan2(da, du)
            scallop = 0.16 * abs(math.sin(th * 4.5)) + jit[int((th + math.pi) / (2 * math.pi) * 63)]
            return r < (0.84 + scallop) * grow
        def vtx(u, a, r):
            return bm.verts.new((u, v + r * math.cos(a), Z + r * math.sin(a)))
        O = [[vtx(u, a, R_OUT) for a in ang] for u in us]
        I = [[vtx(u, a, R_IN) for a in ang] for u in us]
        hole = set()
        for i in range(NU):
            for k in range(NA):
                k2 = (k + 1) % NA
                uc, ac = (us[i] + us[i + 1]) / 2, ang[k] + math.pi / NA
                if inside_bite(uc, ac):
                    hole.add((i, k)); continue
                scraped = inside_bite(uc, ac, 1.28)   # paint scraped off by the teeth
                bm.faces.new([O[i][k], O[i][k2], O[i + 1][k2], O[i + 1][k]]).material_index = bs if scraped else pf
        for i in range(NU):
            for k in range(NA):
                k2 = (k + 1) % NA
                bm.faces.new([I[i][k], I[i + 1][k], I[i + 1][k2], I[i][k2]]).material_index = inside
        # raw steel wall along every edge between a kept face and a bitten one
        for (i, k) in hole:
            k2 = (k + 1) % NA
            for (j, kk), (ea, eb) in (((i - 1, k), (O[i][k], O[i][k2])), ((i + 1, k), (O[i + 1][k2], O[i + 1][k])),
                                      ((i, (k - 1) % NA), (O[i + 1][k], O[i][k])), ((i, k2), (O[i][k2], O[i + 1][k2]))):
                if (j, kk) in hole or j < 0 or j >= NU:
                    continue
                ia = Vector(ea.co); ib = Vector(eb.co)
                def inward(p):
                    c = Vector((p.x, v, Z)); return c + (p - c) * (R_IN / R_OUT)
                f = bm.faces.new([bm.verts.new(ia), bm.verts.new(ib), bm.verts.new(inward(ib)), bm.verts.new(inward(ia))])
                f.material_index = bs
        for i in (0, NU):                                     # end rings
            for k in range(NA):
                k2 = (k + 1) % NA
                f = bm.faces.new([O[i][k], O[i][k2], I[i][k2], I[i][k]]) if i == 0 else bm.faces.new([O[i][k2], O[i][k], I[i][k], I[i][k2]])
                f.material_index = pf
        # bright tooth scratches in the paint around the bite
        for k in range(10):
            th = 2 * math.pi * k / 10 + rng.normal(0, 0.2)
            uu = BITE_U + math.cos(th) * 0.2
            aa = a_bite + math.sin(th) * 0.12 / R_OUT
            ln = 0.025 + 0.02 * rng.random()
            p0 = Vector((uu, v + (R_OUT + 0.0015) * math.cos(aa), Z + (R_OUT + 0.0015) * math.sin(aa)))
            dirv = Vector((math.cos(th), 0, 0)) * ln
            n = (p0 - Vector((uu, v, Z))).normalized()
            side = n.cross(Vector((1, 0, 0))).normalized() * 0.004
            f = bm.faces.new([bm.verts.new(p0 - side), bm.verts.new(p0 + side), bm.verts.new(p0 + side + dirv), bm.verts.new(p0 - side + dirv)])
            f.material_index = bs

    def build_broken():
        b = Builder("PipeBroken")
        bitten_tube(b)
        b.bm.normal_update()
        me = bpy.data.meshes.new("PipeBroken"); b.bm.to_mesh(me); b.bm.free()
        for m in b.mats:
            me.materials.append(m)
        ob = bpy.data.objects.new("PipeBroken", me); sc.collection.objects.link(ob)
        ob.matrix_world = ROT45
        outlined(ob, 0.008)
        b3 = Builder("Shavings")
        scraps(b3)
        sh = b3.finish(outline=0.004); sh.matrix_world = ROT45
        return [ob, sh]

    def build_fixed():
        b = Builder("PipeFixed")
        pf = toon("PipeFlow", (0.4, 0.4, 0.4))
        tube(b, gap[0], gap[1], pf, flat("PipeInside", (0.03, 0.03, 0.035)))
        patch = toon("WeldPatch", (0.5, 0.5, 0.5))
        bead = toon("WeldBead", (0.22, 0.17, 0.12), metal=0.5)
        b.cyl((BITE_U - 0.16, v, Z), (BITE_U + 0.16, v, Z), R_OUT + 0.007, patch, seg=32)      # sleeve over the bite
        for uu in (BITE_U - 0.16, BITE_U + 0.16):                                              # weld bead, lumpy
            for k in range(20):
                a = 2 * math.pi * k / 20
                b.cyl((uu - 0.012, v + (R_OUT + 0.006) * math.cos(a), Z + (R_OUT + 0.006) * math.sin(a)),
                      (uu + 0.012, v + (R_OUT + 0.006) * math.cos(a + 0.35), Z + (R_OUT + 0.006) * math.sin(a + 0.35)), 0.009, bead, seg=6)
        scraps(b)
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

# ============================================================ front walls: full height, cut into sorted strips
# Every wall but the two back walls stands full height. Each is rendered alone and cut into narrow
# vertical strips (STRIP_M along the wall); each strip sorts with the actors by the point on the wall's
# centre line under it, so people walk behind and in front of walls correctly, and the game fades the
# strips that would hide the player or the spot under the cursor.
from PIL import Image as _PIL
STRIP_M = 0.45
out["wallparts"] = []
for wi, w in enumerate(front_walls):
    ob = plan_obj(build_wall(w, full=True), outline=0.012)
    bg_objects.remove(ob)
    path = os.path.join(DIR, f"wall_{wi:02d}.png")
    rect = render([ob], path)
    bpy.data.objects.remove(ob, do_unlink=True)
    im = _PIL.open(path).convert("RGBA")
    os.remove(path)
    (ua, va), (ub, vb) = w["a"], w["b"]
    along_u = va == vb
    lo, hi = (min(ua, ub), max(ua, ub)) if along_u else (min(va, vb), max(va, vb))
    step = max(8, int(round(STRIP_M * kit.R2 * PPM)))
    x = 0
    k = 0
    while x < im.width:
        xb = min(im.width, x + step)
        piece = im.crop((x, 0, xb, im.height))
        bb = piece.getbbox()
        if bb:
            piece = piece.crop((0, bb[1], xb - x, bb[3]))
            xc = rect[0] + (x + xb) / 2.0
            if along_u:
                cu, cv = min(hi, max(lo, xc / PPM / kit.R2 + va)), va
            else:
                cu, cv = ua, min(hi, max(lo, ua - xc / PPM / kit.R2))
            srt = scr_uv(cu, cv)
            f = f"wall_{wi:02d}_{k:02d}.png"
            piece.save(os.path.join(DIR, f))
            out["wallparts"].append({"sprite": f, "x0": round(rect[0] + x, 1), "y0": round(rect[1] + bb[1], 1),
                                     "sort": [round(srt[0], 1), round(srt[1], 1)], "wall": wi})
            k += 1
        x = xb
print("wall strips", len(out["wallparts"]))

# Props that are long (bunks, benches) can't be sorted against narrow wall strips by one point, so
# clamp each prop's sort line: before every strip of a wall it stands behind, after every strip of a
# wall it stands in front of, wherever they overlap on screen.
_strips_by_wall = {}
for wp in out["wallparts"]:
    w_ = _PIL.open(os.path.join(DIR, wp["sprite"])).width
    _strips_by_wall.setdefault(wp["wall"], []).append((wp["x0"], wp["x0"] + w_, wp["sort"][1]))
def _clamp_sort(entry, fp):
    if not entry.get("sprite"):
        return
    w_ = _PIL.open(os.path.join(DIR, entry["sprite"])).width
    px0, px1 = entry["x0"], entry["x0"] + w_
    y = entry["sort"][1]
    for wi, w in enumerate(front_walls):
        (ua, va), (ub, vb) = w["a"], w["b"]
        along_u = va == vb
        lo, hi = (min(ua, ub), max(ua, ub)) if along_u else (min(va, vb), max(va, vb))
        a0, a1, c0, c1 = (fp[0], fp[1], fp[2], fp[3]) if along_u else (fp[2], fp[3], fp[0], fp[1])
        line = va if along_u else ua
        if a1 < lo - 0.3 or a0 > hi + 0.3:
            continue
        over = [sy for (sx0, sx1, sy) in _strips_by_wall.get(wi, []) if sx1 > px0 + 2 and sx0 < px1 - 2]
        if not over:
            continue
        if c0 >= line - 0.05:                         # behind the wall: draw before its strips
            y = min(y, min(over) - 1.0)
        elif c1 <= line + 0.05:                       # in front of it: draw after
            y = max(y, max(over) + 1.0)
    entry["sort"][1] = round(y, 1)
for e in out["props"]:
    _clamp_sort(e, e["footprint"])

json.dump(out, open(os.path.join(DIR, "level.json"), "w"), indent=1)
print("done", LEVEL, "sprites", len(cache))
