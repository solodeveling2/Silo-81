"""Silo 81 environment kit for Blender: toon materials, primitives and the props the level builder places.
Plan coordinates (u, v) run along the 45-degree iso grid; ground x = (u - v)/sqrt2, y = (u + v)/sqrt2,
z up. The camera looks north (+y) from 30 degrees above, like the character renders."""
import math
import bpy, bmesh
from mathutils import Vector, Matrix

R2 = 1 / math.sqrt(2)
LIGHT = Vector((-0.55, -0.55, 0.63)).normalized()
import json as _json, os as _os
_E = math.radians(_json.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "camera.json")))["elev_deg"])
HALF = (LIGHT + Vector((0.0, -math.cos(_E), math.sin(_E)))).normalized()     # between the key light and the camera


def g(u, v):
    return ((u - v) * R2, (u + v) * R2)


# ---------------------------------------------------------------- materials
_mats = {}


# ---------------------------------------------------------------- look (lighting model)
# v1: the original flat toon look. v2: more contrast, warm key light / cool blue-grey shade, coloured
# light pools from practical lamps, and GLB props keep their colour and their metal/roughness.
# Chosen per build with SILO_LOOK=v2 (so levels change only when they are rebuilt on purpose).
LOOK = __import__("os").environ.get("SILO_LOOK", "v2")      # v2 is the game's look (docs/VISUAL_DIRECTION.md)
V2_LIT = (1.07, 1.02, 0.94)        # key light: slightly warm
V2_MID = (0.79, 0.79, 0.8)
V2_SHADE = (0.46, 0.49, 0.56)      # shade side: cool blue-grey, much darker than v1 (0.66 grey)
AMBIENT = (1.0, 1.0, 1.0)          # per level: cooler in unheated areas, e.g. (0.9, 0.95, 1.04)
PRACTICALS = []                    # [(x, y, z, radius_m, (r, g, b) added at the centre)], ground coordinates
AMBER = (0.5, 0.3, 0.08)           # a working lamp: amber light added to whatever it falls on
COLD = (-0.1, -0.05, 0.04)         # an unheated pocket: pulls towards blue-grey


# v2 palette for kit-made objects (muted: industrial teal, dark blue-grey, faded olive, hazard yellow)
V2_PALETTE = {
    "PumpGreen": (0.17, 0.33, 0.33), "MachineGreen": (0.2, 0.34, 0.32),        # industrial teal
    "FilingGrey": (0.3, 0.34, 0.38), "RadioGrey": (0.26, 0.3, 0.34), "SwitchGrey": (0.3, 0.34, 0.38),   # blue-grey
    "SafeGreen": (0.22, 0.27, 0.17), "LockerDark": (0.13, 0.15, 0.09),          # faded olive
    "Hazard": (0.7, 0.52, 0.08),                                                # restrained hazard yellow
}


def _light(nt):
    """Ambient x practical pools for the surface point, as a colour socket (v2 only)."""
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    acc = nt.nodes.new("ShaderNodeRGB"); acc.outputs[0].default_value = (*AMBIENT, 1)
    cur = acc.outputs[0]
    for (x, y, z, r, c) in PRACTICALS:
        # a pool, not a sphere: height counts for less, so the light reaches the floor under the lamp
        sub = nt.nodes.new("ShaderNodeVectorMath"); sub.operation = "SUBTRACT"; sub.inputs[1].default_value = (x, y, z)
        nt.links.new(geo.outputs["Position"], sub.inputs[0])
        flat_ = nt.nodes.new("ShaderNodeVectorMath"); flat_.operation = "MULTIPLY"; flat_.inputs[1].default_value = (1.0, 1.0, 0.45)
        nt.links.new(sub.outputs[0], flat_.inputs[0])
        d = nt.nodes.new("ShaderNodeVectorMath"); d.operation = "LENGTH"; nt.links.new(flat_.outputs[0], d.inputs[0])
        sq = nt.nodes.new("ShaderNodeMapRange"); sq.interpolation_type = "SMOOTHSTEP"
        sq.inputs[1].default_value = r; sq.inputs[2].default_value = 0.0
        nt.links.new(d.outputs["Value"], sq.inputs[0])
        sc = nt.nodes.new("ShaderNodeVectorMath"); sc.operation = "SCALE"; sc.inputs[0].default_value = c
        nt.links.new(sq.outputs[0], sc.inputs["Scale"])
        ad = nt.nodes.new("ShaderNodeVectorMath"); ad.operation = "ADD"
        nt.links.new(cur, ad.inputs[0]); nt.links.new(sc.outputs[0], ad.inputs[1]); cur = ad.outputs[0]
    return cur


def _shade(nt, lit, mid, shade):
    """The toon light bands x (v2) ambient and practical pools: a colour socket to multiply albedo by."""
    ramp = _ramp(nt, lit, mid, shade)
    if LOOK != "v2":
        return ramp.outputs["Color"]
    m = nt.nodes.new("ShaderNodeVectorMath"); m.operation = "MULTIPLY"
    nt.links.new(ramp.outputs["Color"], m.inputs[0]); nt.links.new(_light(nt), m.inputs[1])
    return m.outputs[0]


def _ramp(nt, lit, mid, shade):
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    dot = nt.nodes.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = LIGHT
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.interpolation = "CONSTANT"
    e = ramp.color_ramp.elements
    if LOOK == "v2":                         # same relative bands as the material asked for, v2 colours
        k = shade / 0.66
        e[0].position, e[0].color = 0.0, (*(c * k for c in V2_SHADE), 1)
        e[1].position, e[1].color = 0.45, (*(c * lit / 1.04 for c in V2_LIT), 1)
        m = e.new(0.12); m.color = (*(c * mid / 0.84 for c in V2_MID), 1)
    else:
        e[0].position, e[0].color = 0.0, (shade, shade, shade * 1.04, 1)
        e[1].position, e[1].color = 0.45, (lit, lit * 0.99, lit * 0.96, 1)
        m = e.new(0.12); m.color = (mid, mid, mid * 1.02, 1)
    nt.links.new(geo.outputs["Normal"], dot.inputs[0]); nt.links.new(dot.outputs["Value"], ramp.inputs["Fac"])
    return ramp


TEX_DIR = __import__("os").path.join(__import__("os").path.dirname(__file__), "tex")


def _tex_color(nt, name, scale, pos):
    """Pack-style texture projected along the plan grid: walls facing u or v and floors each get
    their own projection, picked by the surface normal. scale = metres per texture repeat."""
    img = bpy.data.images.get(name + ".png") or bpy.data.images.load(f"{TEX_DIR}/{name}.png")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(pos.outputs["Position"], sep.inputs[0])
    def lin(a, b, ka, kb):
        m1 = nt.nodes.new("ShaderNodeMath"); m1.operation = "MULTIPLY_ADD"
        nt.links.new(a, m1.inputs[0]); m1.inputs[1].default_value = ka
        m2 = nt.nodes.new("ShaderNodeMath"); m2.operation = "MULTIPLY"
        nt.links.new(b, m2.inputs[0]); m2.inputs[1].default_value = kb
        nt.links.new(m2.outputs[0], m1.inputs[2])
        return m1.outputs[0]
    k = R2 / scale
    u = lin(sep.outputs["X"], sep.outputs["Y"], k, k)          # plan u, in texture repeats
    v = lin(sep.outputs["Y"], sep.outputs["X"], k, -k)
    zz = nt.nodes.new("ShaderNodeMath"); zz.operation = "MULTIPLY"; zz.inputs[1].default_value = -1.0 / scale
    nt.links.new(sep.outputs["Z"], zz.inputs[0]); z = zz.outputs[0]
    def sample(a, b):
        cx = nt.nodes.new("ShaderNodeCombineXYZ"); nt.links.new(a, cx.inputs[0]); nt.links.new(b, cx.inputs[1])
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.interpolation = "Cubic"
        nt.links.new(cx.outputs[0], t.inputs["Vector"])
        return t.outputs["Color"]
    c_floor, c_u, c_v = sample(u, v), sample(v, z), sample(u, z)
    nrm = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(pos.outputs["Normal"], nrm.inputs[0])
    nu = lin(nrm.outputs["X"], nrm.outputs["Y"], R2, R2)
    nv = lin(nrm.outputs["Y"], nrm.outputs["X"], R2, -R2)
    def absn(x):
        a = nt.nodes.new("ShaderNodeMath"); a.operation = "ABSOLUTE"; nt.links.new(x, a.inputs[0]); return a.outputs[0]
    anu, anv, anz = absn(nu), absn(nv), absn(nrm.outputs["Z"])
    gt = nt.nodes.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"
    nt.links.new(anu, gt.inputs[0]); nt.links.new(anv, gt.inputs[1])
    m1 = nt.nodes.new("ShaderNodeMix"); m1.data_type = "RGBA"
    nt.links.new(gt.outputs[0], m1.inputs["Factor"]); nt.links.new(c_v, m1.inputs[6]); nt.links.new(c_u, m1.inputs[7])
    fz = nt.nodes.new("ShaderNodeMapRange"); fz.inputs[1].default_value = 0.6; fz.inputs[2].default_value = 0.75
    nt.links.new(anz, fz.inputs[0])
    m2 = nt.nodes.new("ShaderNodeMix"); m2.data_type = "RGBA"
    nt.links.new(fz.outputs[0], m2.inputs["Factor"]); nt.links.new(m1.outputs[2], m2.inputs[6]); nt.links.new(c_floor, m2.inputs[7])
    return m2.outputs[2]


# shared materials that take the asset pack's look: name -> (texture, metres per repeat, tint)
TEX_FOR = {      # name: (texture, metres per repeat, tint[, metal sheen 0..1])
    "PipeSteel": ("steel_rust", 0.7, (1.0, 1.0, 1.0), 0.5),
    "RustPipe": ("steel_rust", 0.5, (1.25, 0.8, 0.6)),
    "Lagging": ("lagging", 0.8, (1.0, 1.0, 1.0)),
    "LagBand": ("steel_rust", 0.4, (0.7, 0.7, 0.7), 0.5),
    "Bracket": ("steel_rust", 0.6, (0.85, 0.85, 0.85), 0.4),
    "Flange": ("steel_rust", 0.4, (0.9, 0.85, 0.8), 0.6),
    "ValveRed": ("valve_red", 0.35, (1.0, 1.0, 1.0), 0.4),
    "Steel": ("steel_rust", 0.6, (1.2, 1.2, 1.2), 0.5),
    "SteelDoor": ("steel_green", 1.2, (1.0, 1.0, 1.0), 0.3),
    # the three pipe-gallery runs, each its own metal
    "PipeWater": ("pipe_green", 0.9, (1.0, 1.0, 1.0), 0.6),       # bore water: painted steel
    "PipeClad": ("alu_clad", 1.0, (0.8, 0.82, 0.84), 0.9),          # heating return: aluminium cladding
    "PipeFlow": ("steel_black", 0.8, (1.0, 1.0, 1.0), 0.8),       # heating flow: bare black steel
    "PipeBandRed": ("valve_red", 0.3, (1.15, 1.0, 1.0), 0.5),     # flow marker bands
    "Bolt": ("steel_rust", 0.2, (1.0, 1.0, 1.0), 0.6),
    "BiteSteel": ("steel_grey", 0.15, (1.5, 1.5, 1.55), 1.0),     # fresh steel where the worm bit through
    "WeldPatch": ("steel_rust", 0.3, (1.15, 1.1, 1.05), 0.8),
}


# kit materials that keep their designed colour but take the pack's surface wear from a texture
DETAIL = {}
for _t, _names in [
    ("wood_grain", "TableWood DeskWood ChairWood BenchWood SchoolWood CrateWood CrateDark PatchWood PlyDoor CounterDoor ChopBoard BoardFrame Pegboard"),
    ("steel_grey", "Locker LockerDark FilingGrey FilingDrawer ShelfSteel BunkFrame SchoolFrame TermCase TVCase SwitchGrey RadioGrey "
                  "IntercomGrey PumpGrey CounterBody LiftSteel LiftFrame DoorFrame Railing HatchFrame StallPanel ScreenFrame ToolSteel Zinc"),
    ("steel_green", "MachineGreen PumpGreen SafeGreen SafeDoor LampGreen"),
    ("steel_rust", "StoveIron StoveDoor BlastSteel Rivet Breaker GasBottle DrainGrate Hotplate"),
    ("paint_white", "MedWhite MedDoor Enamel SinkDark PotEnamel"),
    ("fabric", "Mattress Pillow Rug RugInner ScreenCloth"),
    ("concrete_wall", "ConcretePlinth"),
    # wall fixtures and one-off props: same pack wear, designed colours kept
    ("paint_white", "Radiator_working"),
    ("steel_grey", "Radiator_dead Radiator_frozen RadioDark Tin PotAlu Knob CashTin Wire"),
    ("steel_rust", "GasRed Brass Padlock"),
    ("fabric", "Sack0 Sack1 BenchSeat LampShade Cork Leather Carton"),
    ("wood_grain", "CounterTop RationBoard Peg"),
    ("concrete_wall", "BoardGreen"),
]:
    for _n in _names.split():
        DETAIL[_n] = _t
_MEANS = None


def _detail_tint(texname, rgb, keep=0.75):
    """Tint so the texture averages to the material's designed colour (keep=1) or stays as painted (keep=0)."""
    global _MEANS
    if _MEANS is None:
        import json, os
        _MEANS = json.load(open(os.path.join(TEX_DIR, "means.json")))
    m = _MEANS[texname]
    return tuple((1 - keep) + keep * (c / max(mc, 1e-3)) for c, mc in zip(rgb, m))


# ---------------------------------------------------------------- aged walls
# Wear profiles: how a room's walls have aged. All values 0..1 except the colours. Every layer is a
# procedural mask in world space (no UVs, so it runs continuously across wall pieces and corners), and
# every feature is at least ~0.15 m: at the game zoom a metre is about 100 px, finer detail is noise.
#   drift    large, soft tonal variation of the paint (several metres across)
#   warm     how far the drift leans to yellowed / brownish paint
#   repaint  share of the wall covered by later, mismatched repaint patches
#   peel     paint worn or peeled back to the concrete
#   grime    dirt rising from the floor, darkest in the bottom 0.4 m
#   scuff    horizontal scuffs at hip height (trolleys, shoulders, stretchers)
#   stains   water streaks running down from the top of the wall
#   damp     damp / mould blotches near the floor
#   rust     rust bleed (streaks and spots)
#   cracks   repaired cracks (filler lines)
#   seed     offsets the patterns so neighbouring rooms don't share them
AGE_PROFILES = {
    "corridor":    dict(drift=0.5, warm=0.35, repaint=0.4, peel=0.22, grime=0.55, scuff=0.7, stains=0.35, damp=0.12, rust=0.12, cracks=0.35),
    "sleeping":    dict(drift=0.7, warm=0.6, repaint=0.25, peel=0.38, grime=0.5, scuff=0.2, stains=0.5, damp=0.25, rust=0.08, cracks=0.45),
    "storage":     dict(drift=0.6, warm=0.45, repaint=0.08, peel=0.5, grime=0.8, scuff=0.35, stains=0.55, damp=0.4, rust=0.35, cracks=0.3, shade=0.88),
    "maintenance": dict(drift=0.6, warm=0.4, repaint=0.3, peel=0.7, grime=0.75, scuff=0.4, stains=0.6, damp=0.3, rust=0.75, cracks=0.6, shade=0.92),
    "wet":         dict(drift=0.5, warm=0.3, repaint=0.2, peel=0.45, grime=0.55, scuff=0.1, stains=0.7, damp=0.7, rust=0.3, cracks=0.35),
    "public":      dict(drift=0.45, warm=0.4, repaint=0.35, peel=0.18, grime=0.35, scuff=0.45, stains=0.25, damp=0.1, rust=0.06, cracks=0.3),
    "kept":        dict(drift=0.3, warm=0.3, repaint=0.15, peel=0.06, grime=0.2, scuff=0.15, stains=0.1, damp=0.04, rust=0.03, cracks=0.12),
}
CONCRETE_BARE = (0.53, 0.5, 0.45)          # the substrate under the paint: warm, dirty grey
GRIME_RGB = (0.5, 0.42, 0.33)               # floor dirt and scuffs: brown-grey, multiplied in
STAIN_RGB = (0.62, 0.53, 0.4)               # water streaks: tea-brown
DAMP_RGB = (0.36, 0.38, 0.27)               # mould / damp: dark olive
RUST_RGB = (0.5, 0.27, 0.13)
FILLER_RGB = (0.9, 0.88, 0.82)              # crack filler: multiplied, so it reads as a pale, slightly greyer line


def _age(nt, cur, pos, a, tcol=None, dado_h=None):
    """Layer a wall's history over its paint colour `cur` (a colour socket). Returns the new socket."""
    N = nt.nodes.new
    L = nt.links.new
    seed = a.get("seed", 0.0)
    P = N("ShaderNodeVectorMath"); P.operation = "ADD"; L(pos.outputs["Position"], P.inputs[0])
    P.inputs[1].default_value = (seed * 17.3, seed * 9.1, seed * 3.7)
    P = P.outputs[0]
    sep = N("ShaderNodeSeparateXYZ"); L(P, sep.inputs[0]); Z = sep.outputs["Z"]

    def noise(vec, scale, detail=2.0, rough=0.5, dist=0.0, stretch=None):
        v = vec
        if stretch:
            m = N("ShaderNodeVectorMath"); m.operation = "MULTIPLY"; m.inputs[1].default_value = stretch
            L(vec, m.inputs[0]); v = m.outputs[0]
        t = N("ShaderNodeTexNoise"); t.inputs["Scale"].default_value = scale
        t.inputs["Detail"].default_value = detail; t.inputs["Roughness"].default_value = rough
        t.inputs["Distortion"].default_value = dist
        L(v, t.inputs["Vector"]); return t.outputs["Fac"]

    def math(op, a_, b_=None, c_=None):
        m = N("ShaderNodeMath"); m.operation = op
        for i, x in enumerate((a_, b_, c_)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                m.inputs[i].default_value = x
            else:
                L(x, m.inputs[i])
        return m.outputs[0]

    def ramp(x, lo, hi):                      # smooth 0..1 between lo and hi
        r = N("ShaderNodeMapRange"); r.interpolation_type = "SMOOTHSTEP"
        r.inputs[1].default_value = lo; r.inputs[2].default_value = hi
        L(x, r.inputs[0]); return r.outputs[0]

    def rgb(c):
        n = N("ShaderNodeRGB"); n.outputs[0].default_value = (*c, 1); return n.outputs[0]

    def mix(a_, b_, fac, blend="MIX"):
        m = N("ShaderNodeMix"); m.data_type = "RGBA"; m.blend_type = blend; m.clamp_result = True
        L(fac, m.inputs["Factor"]); L(a_, m.inputs[6]); L(b_, m.inputs[7]); return m.outputs[2]

    def scaled(x, k):
        return math("MULTIPLY", x, k)

    # 1. drift: large, soft variation of the paint, some of it yellowed
    big = noise(P, 0.22, 2.0, 0.4)
    tone = N("ShaderNodeMapRange"); tone.inputs[1].default_value = 0.36; tone.inputs[2].default_value = 0.64
    tone.inputs[3].default_value = 1.0 - 0.28 * a["drift"]; tone.inputs[4].default_value = 1.0 + 0.08 * a["drift"]
    L(big, tone.inputs[0])
    m = N("ShaderNodeVectorMath"); m.operation = "MULTIPLY"; L(cur, m.inputs[0]); L(tone.outputs[0], m.inputs[1]); cur = m.outputs[0]
    yel = scaled(ramp(noise(P, 0.35, 1.0), 0.42, 0.6), 0.45 * a["warm"])
    cur = mix(cur, rgb((0.86, 0.78, 0.6)), yel, "MULTIPLY")
    if a.get("shade", 1.0) != 1.0:
        sh = N("ShaderNodeVectorMath"); sh.operation = "SCALE"; L(cur, sh.inputs[0]); sh.inputs["Scale"].default_value = a["shade"]
        cur = sh.outputs[0]

    # 2. repaint: blocky later patches in a slightly different, fresher paint (Chebyshev Voronoi = rectangles)
    if a["repaint"] > 0:
        vo = N("ShaderNodeTexVoronoi"); vo.distance = "CHEBYCHEV"; vo.inputs["Scale"].default_value = 0.55
        st = N("ShaderNodeVectorMath"); st.operation = "MULTIPLY"; st.inputs[1].default_value = (1.0, 1.0, 1.6)
        L(P, st.inputs[0]); L(st.outputs[0], vo.inputs["Vector"])
        cell = N("ShaderNodeSeparateColor"); L(vo.outputs["Color"], cell.inputs[0])
        patch = math("GREATER_THAN", cell.outputs[0], 1.0 - 0.45 * a["repaint"])
        cur = mix(cur, rgb((1.1, 1.12, 1.07)), patch, "MULTIPLY")       # cleaner, slightly cooler paint

    # 3. peel: paint worn back to concrete, in clusters, more near the floor and at hip height
    if a["peel"] > 0:
        cluster = ramp(noise(P, 0.4, 2.0), 0.53 - 0.06 * a["peel"], 0.62 - 0.06 * a["peel"])   # a few worn zones
        shape = noise(P, 2.0, 3.0, 0.55, 0.3)
        low = ramp(math("SUBTRACT", 1.4, Z), 0.0, 1.2)                      # 1 at the floor .. 0 above 1.4 m
        amount = math("MULTIPLY", cluster, math("ADD", 0.55, scaled(low, 0.45)))
        cut = math("SUBTRACT", 0.74, scaled(amount, 0.12 + 0.12 * a["peel"]))
        bare = math("GREATER_THAN", shape, cut)
        rim = math("SUBTRACT", math("GREATER_THAN", shape, math("SUBTRACT", cut, 0.03)), bare)
        conc = rgb(CONCRETE_BARE)
        if tcol is not None:
            cm = N("ShaderNodeVectorMath"); cm.operation = "MULTIPLY"; L(tcol, cm.inputs[0]); L(conc, cm.inputs[1]); conc = cm.outputs[0]
        cur = mix(cur, conc, bare)
        cur = mix(cur, rgb((0.55, 0.5, 0.44)), scaled(rim, 0.8), "MULTIPLY")   # the broken paint edge

    # 4. grime from the floor, uneven
    if a["grime"] > 0:
        rise = ramp(math("SUBTRACT", 0.55, Z), 0.0, 0.55)
        var = ramp(noise(P, 1.1, 2.0), 0.3, 0.75)
        g = math("MULTIPLY", math("MULTIPLY", rise, math("ADD", 0.45, scaled(var, 0.55))), 0.8 * a["grime"])
        cur = mix(cur, rgb(GRIME_RGB), g, "MULTIPLY")
        top = ramp(math("SUBTRACT", Z, 2.25), 0.0, 0.45)                 # soot / dust under the ceiling
        cur = mix(cur, rgb((0.75, 0.72, 0.66)), scaled(top, 0.6 * a["grime"]), "MULTIPLY")

    # 5. scuffs: horizontal smears at hip height
    if a["scuff"] > 0:
        band = math("MULTIPLY", ramp(Z, 0.55, 0.75), ramp(math("SUBTRACT", 1.25, Z), 0.0, 0.25))
        smear = ramp(noise(P, 1.0, 2.0, 0.5, 0.0, (1.0, 1.0, 9.0)), 0.5, 0.64)
        sc = math("MULTIPLY", math("MULTIPLY", band, smear), 0.55 * a["scuff"])
        cur = mix(cur, rgb(GRIME_RGB), sc, "MULTIPLY")

    # 6. water streaks: long vertical runs from a few leak points, fading towards the floor
    if a["stains"] > 0:
        runs = ramp(noise(P, 1.6, 1.0, 0.5, 0.0, (1.0, 1.0, 0.07)), 0.5, 0.6)
        where = ramp(noise(P, 0.3, 1.0), 0.44, 0.56)
        fade = ramp(Z, 0.2, 2.2)
        st_ = math("MULTIPLY", math("MULTIPLY", runs, where), math("MULTIPLY", fade, 0.95 * a["stains"]))
        cur = mix(cur, rgb(STAIN_RGB), st_, "MULTIPLY")
        tide = math("MULTIPLY", math("MULTIPLY", ramp(noise(P, 0.6, 2.0), 0.5, 0.58), ramp(math("SUBTRACT", 0.9, Z), 0.0, 0.25)),
                    0.5 * a["stains"])                                    # a tide line where water once stood
        cur = mix(cur, rgb(STAIN_RGB), scaled(math("MULTIPLY", tide, ramp(Z, 0.5, 0.75)), 1.0), "MULTIPLY")

    # 7. damp and mould: blotches near the floor and in the lower corners of the wall
    if a["damp"] > 0:
        blot = ramp(noise(P, 1.3, 3.0, 0.6, 0.3), 0.54, 0.62)
        low = ramp(math("SUBTRACT", 1.0, Z), 0.0, 0.9)
        dm = math("MULTIPLY", math("MULTIPLY", blot, low), math("MULTIPLY", ramp(noise(P, 0.35), 0.46, 0.58), 0.95 * a["damp"]))
        cur = mix(cur, rgb(DAMP_RGB), dm, "MULTIPLY")

    # 8. rust bleed: spots and short streaks
    if a["rust"] > 0:
        spot = ramp(noise(P, 1.8, 2.0, 0.6, 0.5), 0.62, 0.68)
        drip = ramp(noise(P, 3.0, 1.0, 0.5, 0.0, (1.0, 1.0, 0.12)), 0.54, 0.64)
        src = ramp(noise(P, 0.5, 1.0), 0.54, 0.62)
        r_ = math("MAXIMUM", spot, math("MULTIPLY", drip, src))
        cur = mix(cur, rgb(RUST_RGB), math("MULTIPLY", r_, 0.75 * a["rust"]), "MULTIPLY")

    # 9. repaired cracks: thin light filler lines (a ridge of distorted noise), only in some areas
    if a["cracks"] > 0:
        cr = noise(P, 0.55, 2.0, 0.5, 0.5)
        line = math("LESS_THAN", math("ABSOLUTE", math("SUBTRACT", cr, 0.5)), 0.006)
        area = ramp(noise(P, 0.2, 1.0), 0.6 - 0.06 * a["cracks"], 0.63 - 0.06 * a["cracks"])
        cur = mix(cur, rgb(FILLER_RGB), math("MULTIPLY", line, scaled(area, 0.9)), "MULTIPLY")
    return cur


def toon(name, rgb, noise=0.0, noise_scale=6.0, lit=1.04, mid=0.84, shade=0.66, alpha_noise=None,
         dado=None, frost=None, grating=None, stripes=None, tex=None, tex_scale=1.0, metal=0.0, age=None):
    """Emission toon material. Options:
    noise: colour variation strength.  dado: (lower_rgb, height) painted lower wall.
    frost: (u_start, u_full, frost_rgb) frost creeping in along +u.  grating: (bar_rgb, pitch) steel floor grate.
    alpha_noise: (threshold, scale) cut out by noise, for stains and decals.
    tex: name of a texture in tex/ (made by textures.py); rgb then tints it (1,1,1 = as painted).
    With dado, the lower colour tints the same texture too.
    age: a wear profile (dict, see AGE_PROFILES) layered over the paint: see _age()."""
    key = name
    if key in _mats:
        return _mats[key]
    if LOOK == "v2" and name in V2_PALETTE:      # v2 palette: separate machinery, cabinets and markings
        rgb = V2_PALETTE[name]
    if tex is None and name in TEX_FOR:
        tex, tex_scale, rgb = TEX_FOR[name][:3]
        metal = TEX_FOR[name][3] if len(TEX_FOR[name]) > 3 else metal
        noise = 0.0
    if metal:                                    # harder light/shadow split, like polished metal
        lit, mid, shade = 1.06, 0.78, 0.5
    elif tex is None and name in DETAIL:
        tex = DETAIL[name]; tex_scale = 1.4
        rgb = _detail_tint(tex, rgb); noise = 0.0
    if tex:
        grating = None
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    pos = nt.nodes.new("ShaderNodeNewGeometry")
    col = nt.nodes.new("ShaderNodeRGB"); col.outputs[0].default_value = (*rgb, 1)
    cur = col.outputs[0]
    tcol = None
    if tex:
        tcol = _tex_color(nt, tex, tex_scale, pos)
        tm = nt.nodes.new("ShaderNodeVectorMath"); tm.operation = "MULTIPLY"
        nt.links.new(tcol, tm.inputs[0]); nt.links.new(col.outputs[0], tm.inputs[1])
        cur = tm.outputs[0]

    def mix(a, b, fac):
        mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"
        nt.links.new(fac, mx.inputs["Factor"]); nt.links.new(a, mx.inputs[6]); nt.links.new(b, mx.inputs[7])
        return mx.outputs[2]

    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(pos.outputs["Position"], sep.inputs[0])
    if dado:
        lower, h = dado
        lc = nt.nodes.new("ShaderNodeRGB"); lc.outputs[0].default_value = (*lower, 1)
        lower_col = lc.outputs[0]
        if tcol is not None:
            lm = nt.nodes.new("ShaderNodeVectorMath"); lm.operation = "MULTIPLY"
            nt.links.new(tcol, lm.inputs[0]); nt.links.new(lc.outputs[0], lm.inputs[1]); lower_col = lm.outputs[0]
        lt = nt.nodes.new("ShaderNodeMath"); lt.operation = "LESS_THAN"; lt.inputs[1].default_value = h
        zsrc = sep.outputs["Z"]
        if age:                                  # hand-painted: the dado line wanders a few cm
            wn = nt.nodes.new("ShaderNodeTexNoise"); wn.inputs["Scale"].default_value = 1.3; wn.inputs["Detail"].default_value = 1.0
            nt.links.new(pos.outputs["Position"], wn.inputs["Vector"])
            wm = nt.nodes.new("ShaderNodeMath"); wm.operation = "MULTIPLY_ADD"; wm.inputs[1].default_value = 0.12; wm.inputs[2].default_value = -0.06
            nt.links.new(wn.outputs["Fac"], wm.inputs[0])
            wa = nt.nodes.new("ShaderNodeMath"); wa.operation = "ADD"
            nt.links.new(sep.outputs["Z"], wa.inputs[0]); nt.links.new(wm.outputs[0], wa.inputs[1]); zsrc = wa.outputs[0]
        nt.links.new(zsrc, lt.inputs[0])
        cur = mix(cur, lower_col, lt.outputs[0])
        # dark painted line on top of the dado
        band = nt.nodes.new("ShaderNodeMath"); band.operation = "COMPARE"
        band.inputs[1].default_value = h + 0.02; band.inputs[2].default_value = 0.025
        nt.links.new(zsrc, band.inputs[0])
        dk = nt.nodes.new("ShaderNodeRGB"); dk.outputs[0].default_value = (lower[0] * 0.45, lower[1] * 0.45, lower[2] * 0.45, 1)
        cur = mix(cur, dk.outputs[0], band.outputs[0])
    if grating:
        bar, pitch = grating
        bc = nt.nodes.new("ShaderNodeRGB"); bc.outputs[0].default_value = (*bar, 1)
        acc = None
        for axis in ("X", "Y"):
            # bars along the plan diagonals: use (x+y) and (x-y)
            add = nt.nodes.new("ShaderNodeMath"); add.operation = "ADD" if axis == "X" else "SUBTRACT"
            nt.links.new(sep.outputs["X"], add.inputs[0]); nt.links.new(sep.outputs["Y"], add.inputs[1])
            sc_ = nt.nodes.new("ShaderNodeMath"); sc_.operation = "MULTIPLY"; sc_.inputs[1].default_value = R2 / pitch
            nt.links.new(add.outputs[0], sc_.inputs[0])
            fr = nt.nodes.new("ShaderNodeMath"); fr.operation = "FRACT"; nt.links.new(sc_.outputs[0], fr.inputs[0])
            lt = nt.nodes.new("ShaderNodeMath"); lt.operation = "LESS_THAN"
            lt.inputs[1].default_value = 0.22 if axis == "X" else 0.5
            nt.links.new(fr.outputs[0], lt.inputs[0])
            acc = lt.outputs[0] if acc is None else acc
            if axis == "Y":
                mx_ = nt.nodes.new("ShaderNodeMath"); mx_.operation = "MAXIMUM"
                fine = nt.nodes.new("ShaderNodeMath"); fine.operation = "MULTIPLY"; fine.inputs[1].default_value = 4.0
                nt.links.new(sc_.outputs[0], fine.inputs[0])
                fr2 = nt.nodes.new("ShaderNodeMath"); fr2.operation = "FRACT"; nt.links.new(fine.outputs[0], fr2.inputs[0])
                lt2 = nt.nodes.new("ShaderNodeMath"); lt2.operation = "LESS_THAN"; lt2.inputs[1].default_value = 0.3
                nt.links.new(fr2.outputs[0], lt2.inputs[0])
                nt.links.new(acc, mx_.inputs[0]); nt.links.new(lt2.outputs[0], mx_.inputs[1])
                acc = mx_.outputs[0]
        cur = mix(cur, bc.outputs[0], acc)
    if noise:
        tex = nt.nodes.new("ShaderNodeTexNoise"); tex.inputs["Scale"].default_value = noise_scale
        tex.inputs["Detail"].default_value = 6.0
        nt.links.new(pos.outputs["Position"], tex.inputs["Vector"])
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs[3].default_value = 1 - noise; mr.inputs[4].default_value = 1 + noise * 0.6
        nt.links.new(tex.outputs["Fac"], mr.inputs[0])
        mul = nt.nodes.new("ShaderNodeVectorMath"); mul.operation = "MULTIPLY"
        nt.links.new(cur, mul.inputs[0]); nt.links.new(mr.outputs[0], mul.inputs[1])
        cur = mul.outputs[0]
    if frost:
        u0, u1, frgb = frost[:3]
        zmax = frost[3] if len(frost) > 3 else None
        add = nt.nodes.new("ShaderNodeMath"); add.operation = "ADD"
        nt.links.new(sep.outputs["X"], add.inputs[0]); nt.links.new(sep.outputs["Y"], add.inputs[1])
        uu = nt.nodes.new("ShaderNodeMath"); uu.operation = "MULTIPLY"; uu.inputs[1].default_value = R2
        nt.links.new(add.outputs[0], uu.inputs[0])
        tex = nt.nodes.new("ShaderNodeTexNoise"); tex.inputs["Scale"].default_value = 3.0
        tex.inputs["Detail"].default_value = 8.0
        nt.links.new(pos.outputs["Position"], tex.inputs["Vector"])
        ramp_u = nt.nodes.new("ShaderNodeMapRange"); ramp_u.inputs[1].default_value = u0; ramp_u.inputs[2].default_value = u1
        nt.links.new(uu.outputs[0], ramp_u.inputs[0])
        f2 = nt.nodes.new("ShaderNodeMath"); f2.operation = "ADD"
        nt.links.new(ramp_u.outputs[0], f2.inputs[0])
        nm = nt.nodes.new("ShaderNodeMath"); nm.operation = "SUBTRACT"; nm.inputs[1].default_value = 0.55
        nt.links.new(tex.outputs["Fac"], nm.inputs[0]); nt.links.new(nm.outputs[0], f2.inputs[1])
        if zmax:                                   # frost creeps up from the floor only so far
            zf = nt.nodes.new("ShaderNodeMath"); zf.operation = "MULTIPLY"; zf.inputs[1].default_value = -0.6 / zmax
            nt.links.new(sep.outputs["Z"], zf.inputs[0])
            f3 = nt.nodes.new("ShaderNodeMath"); f3.operation = "ADD"
            nt.links.new(f2.outputs[0], f3.inputs[0]); nt.links.new(zf.outputs[0], f3.inputs[1])
            f2 = f3
        st = nt.nodes.new("ShaderNodeMath"); st.operation = "GREATER_THAN"; st.inputs[1].default_value = 0.5
        nt.links.new(f2.outputs[0], st.inputs[0])
        fc = nt.nodes.new("ShaderNodeRGB"); fc.outputs[0].default_value = (*frgb, 1)
        soft = nt.nodes.new("ShaderNodeMath"); soft.operation = "MULTIPLY"; soft.inputs[1].default_value = 0.75
        nt.links.new(st.outputs[0], soft.inputs[0])
        cur = mix(cur, fc.outputs[0], soft.outputs[0])
    if age:
        cur = _age(nt, cur, pos, age, tcol, (dado[1] if dado else None))
    shading = _shade(nt, lit, mid, shade)
    mul = nt.nodes.new("ShaderNodeVectorMath"); mul.operation = "MULTIPLY"
    nt.links.new(cur, mul.inputs[0]); nt.links.new(shading, mul.inputs[1])
    lit_col = mul.outputs[0]
    if metal:
        # specular glint: normal close to the half vector between the key light and the camera
        geo2 = nt.nodes.new("ShaderNodeNewGeometry")
        hd = nt.nodes.new("ShaderNodeVectorMath"); hd.operation = "DOT_PRODUCT"
        hd.inputs[1].default_value = HALF
        nt.links.new(geo2.outputs["Normal"], hd.inputs[0])
        mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs[1].default_value = 0.9; mr.inputs[2].default_value = 0.955
        mr.inputs[4].default_value = metal * 0.75
        nt.links.new(hd.outputs["Value"], mr.inputs[0])
        glint = nt.nodes.new("ShaderNodeMix"); glint.data_type = "RGBA"
        nt.links.new(mr.outputs[0], glint.inputs["Factor"]); nt.links.new(lit_col, glint.inputs[6])
        glint.inputs[7].default_value = (0.92, 0.93, 0.95, 1)
        lit_col = glint.outputs[2]
        # dark reflection band just below the glint (rim of the cylinder facing away from the sky)
        mr2 = nt.nodes.new("ShaderNodeMapRange"); mr2.inputs[1].default_value = 0.55; mr2.inputs[2].default_value = 0.72
        mr2.inputs[3].default_value = 1.0; mr2.inputs[4].default_value = 1.0 - metal * 0.25
        nt.links.new(hd.outputs["Value"], mr2.inputs[0])
        dk = nt.nodes.new("ShaderNodeVectorMath"); dk.operation = "SCALE"
        nt.links.new(lit_col, dk.inputs[0]); nt.links.new(mr2.outputs[0], dk.inputs["Scale"])
        lit_col = dk.outputs[0]
    em = nt.nodes.new("ShaderNodeEmission"); nt.links.new(lit_col, em.inputs["Color"])
    shader = em.outputs[0]
    if alpha_noise:
        th, scale = alpha_noise
        tex = nt.nodes.new("ShaderNodeTexNoise"); tex.inputs["Scale"].default_value = scale
        tex.inputs["Detail"].default_value = 6.0
        nt.links.new(pos.outputs["Position"], tex.inputs["Vector"])
        gt = nt.nodes.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = th
        nt.links.new(tex.outputs["Fac"], gt.inputs[0])
        tr = nt.nodes.new("ShaderNodeBsdfTransparent"); mx = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(gt.outputs[0], mx.inputs["Fac"]); nt.links.new(tr.outputs[0], mx.inputs[1])
        nt.links.new(em.outputs[0], mx.inputs[2]); shader = mx.outputs[0]
    nt.links.new(shader, out.inputs["Surface"])
    _mats[key] = m
    return m


def ink():
    if "Ink" in _mats:
        return _mats["Ink"]
    m = bpy.data.materials.new("Ink"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); gg = nt.nodes.new("ShaderNodeNewGeometry")
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (0.035, 0.03, 0.025, 1)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent"); mx = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(gg.outputs["Backfacing"], mx.inputs["Fac"]); nt.links.new(em.outputs["Emission"], mx.inputs[1])
    nt.links.new(tr.outputs["BSDF"], mx.inputs[2]); nt.links.new(mx.outputs["Shader"], o.inputs["Surface"])
    _mats["Ink"] = m
    return m


def flat(name, rgb, alpha=1.0):
    """Unlit paint, for text, decals and graffiti."""
    key = "flat_" + name
    if key in _mats:
        return _mats[key]
    m = bpy.data.materials.new(key); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*rgb, 1)
    if alpha < 1:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent"); mx = nt.nodes.new("ShaderNodeMixShader")
        mx.inputs["Fac"].default_value = alpha
        nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2])
        nt.links.new(mx.outputs[0], o.inputs["Surface"])
    else:
        nt.links.new(em.outputs[0], o.inputs["Surface"])
    _mats[key] = m
    return m


# ---------------------------------------------------------------- mesh building
class Builder:
    """Collects boxes and cylinders in a local frame into one mesh with several materials."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.mats = []

    def mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def box(self, x0, x1, y0, y1, z0, z1, mat, M=None, top_mat=None, faces_mat=None):
        """faces_mat: optional {face index: material}; faces are 0 -x, 1 +x, 2 -y, 3 +y, 4 bottom, 5 top."""
        vs = []
        for x in (x0, x1):
            for y in (y0, y1):
                for z in (z0, z1):
                    p = Vector((x, y, z))
                    vs.append(self.bm.verts.new(M @ p if M else p))
        faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        idx = self.mi(mat)
        tidx = self.mi(top_mat) if top_mat else idx
        fm = {k: self.mi(m_) for k, m_ in (faces_mat or {}).items()}
        for k, f in enumerate(faces):
            face = self.bm.faces.new([vs[i] for i in f])
            face.material_index = fm.get(k, tidx if k == 5 else idx)
        return vs

    def cyl(self, p0, p1, r, mat, seg=12, cap=True, r1=None):
        p0, p1 = Vector(p0), Vector(p1)
        ax = (p1 - p0); L = ax.length; ax.normalize()
        t = Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0))
        n = ax.cross(t).normalized(); b = ax.cross(n)
        r1 = r if r1 is None else r1
        ring0 = [self.bm.verts.new(p0 + r * (math.cos(2 * math.pi * k / seg) * n + math.sin(2 * math.pi * k / seg) * b)) for k in range(seg)]
        ring1 = [self.bm.verts.new(p1 + r1 * (math.cos(2 * math.pi * k / seg) * n + math.sin(2 * math.pi * k / seg) * b)) for k in range(seg)]
        idx = self.mi(mat)
        for k in range(seg):
            f = self.bm.faces.new([ring0[k], ring0[(k + 1) % seg], ring1[(k + 1) % seg], ring1[k]]); f.material_index = idx
        if cap:
            f = self.bm.faces.new(ring0[::-1]); f.material_index = idx
            if r1 > 0.0005:
                f = self.bm.faces.new(ring1); f.material_index = idx
        return ring0, ring1

    def quad(self, pts, mat):
        vs = [self.bm.verts.new(Vector(p)) for p in pts]
        f = self.bm.faces.new(vs); f.material_index = self.mi(mat)

    def finish(self, outline=0.012, collection=None):
        me = bpy.data.meshes.new(self.name)
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])
        self.bm.to_mesh(me); self.bm.free()
        for m in self.mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(self.name, me)
        (collection or bpy.context.scene.collection).objects.link(ob)
        if outline:
            me.materials.append(ink())
            sol = ob.modifiers.new("Outline", "SOLIDIFY"); sol.thickness = -outline
            sol.use_flip_normals = True; sol.use_rim = False; sol.material_offset = len(self.mats)
        return ob


def text_obj(body, font, size, mat, extrude=0.002, align="CENTER"):
    cu = bpy.data.curves.new("Text", "FONT"); cu.body = body
    cu.font = bpy.data.fonts.load(font, check_existing=True)
    cu.size = size; cu.extrude = extrude; cu.align_x = align; cu.align_y = "CENTER"
    ob = bpy.data.objects.new("Text", cu); bpy.context.scene.collection.objects.link(ob)
    cu.materials.append(mat)
    return ob


# ---------------------------------------------------------------- placement
FACING = {"-v": (0, -1), "+v": (0, 1), "-u": (-1, 0), "+u": (1, 0)}


def facing_frame(facing):
    """Local +y points out of the wall (the prop's front), +x along the wall."""
    fu, fv = FACING[facing]
    fx, fy = g(fu, fv)
    ang = math.atan2(fy, fx) - math.pi / 2
    return ang


def place(ob_list, u, v, facing, z=0.0):
    x, y = g(u, v)
    ang = facing_frame(facing)
    for ob in ob_list:
        ob.matrix_world = Matrix.Translation((x, y, z)) @ Matrix.Rotation(ang, 4, "Z") @ ob.matrix_world


def footprint(u, v, facing, length, depth):
    """Plan-space rectangle (u0, u1, v0, v1) covered by a prop whose back is at (u, v)."""
    fu, fv = FACING[facing]
    ru, rv = (fv, -fu)                  # along the wall
    cu_, cv_ = u + fu * depth / 2, v + fv * depth / 2
    hu = abs(fu) * depth / 2 + abs(ru) * length / 2
    hv = abs(fv) * depth / 2 + abs(rv) * length / 2
    return [round(cu_ - hu, 3), round(cu_ + hu, 3), round(cv_ - hv, 3), round(cv_ + hv, 3)]


# ---------------------------------------------------------------- colours
STEEL_PAINT = (0.36, 0.42, 0.37)
OLIVE = (0.36, 0.38, 0.27)
CREAM = (0.78, 0.74, 0.62)
WOOD = (0.42, 0.29, 0.17)
PLY = (0.62, 0.5, 0.33)
RUST = (0.45, 0.24, 0.12)
BLANKETS = [(0.42, 0.38, 0.33), (0.33, 0.37, 0.42), (0.38, 0.40, 0.30), (0.46, 0.33, 0.30), (0.5, 0.47, 0.4)]


# ---------------------------------------------------------------- props (local frame, back at y=0, front +y)
# ---------------------------------------------------------------- bedding and personal things (dorm remake)
BLANKET_TEX = ["blanket_plaid_red", "blanket_army", "blanket_quilt_blue", "blanket_check_brown", "blanket_stripe_cream",
               "blanket_plaid_green", "blanket_patchwork", "blanket_grey_wool", "blanket_quilt_rose", "blanket_plaid_navy"]
FRAME_PAINT = [("BunkFrame", "steel_grey", (0.32, 0.36, 0.33)), ("BunkFrameGreen", "steel_green", (0.24, 0.34, 0.26)),
               ("BunkFrameWhite", "paint_white", (0.62, 0.62, 0.58))]
LOCKER_PAINT = [(0.29, 0.33, 0.24), (0.26, 0.3, 0.27), (0.31, 0.34, 0.33), (0.24, 0.28, 0.22)]   # olive and grey, like the Tripo locker


def blanket_mat(k):
    t = BLANKET_TEX[k % len(BLANKET_TEX)]
    return toon("Blk_" + t, (1.0, 1.0, 1.0), tex=t, tex_scale=0.9)


def frame_mat(k):
    name, tex, rgb = FRAME_PAINT[k % len(FRAME_PAINT)]
    return toon(name, _detail_tint(tex, rgb), tex=tex, tex_scale=1.4, metal=0.35)


def ellipsoid(b, c, r, mat, seg=12):
    res = bmesh.ops.create_uvsphere(b.bm, u_segments=seg, v_segments=max(4, seg // 2), radius=1.0,
                                    matrix=Matrix.Translation(c) @ Matrix.Diagonal((r[0], r[1], r[2], 1.0)))
    idx = b.mi(mat)
    vs = set(res["verts"])
    for f in b.bm.faces:
        if f.verts[0] in vs:
            f.material_index = idx


def cloth(b, x0, x1, y0, y1, z, mat, rng, drape=0.18, messy=0.0, nx=18, ny=10):
    """A blanket: lies on the mattress with soft folds and hangs down over both long edges.
    messy pulls part of it into a rumpled heap."""
    W = y1 - y0
    ph = rng.random(4) * 6.28
    lumps = [(rng.uniform(x0, x1), rng.uniform(y0, y1), rng.uniform(0.04, 0.09) * messy) for _ in range(3)]
    grid = []
    for i in range(nx + 1):
        x = x0 + (x1 - x0) * i / nx
        row = []
        for j in range(ny + 1):
            p = -drape + (W + 2 * drape) * j / ny
            fold = 0.012 * math.sin(x * 9 + ph[0]) + 0.01 * math.sin(x * 4.3 + p * 6 + ph[1])
            if p < 0:
                y, zz = y0 - 0.012, z + p * 0.95 + fold * 0.6
            elif p > W:
                y, zz = y1 + 0.012, z - (p - W) * 0.95 + fold * 0.6
            else:
                y = y0 + p
                zz = z + 0.02 + fold
                for (lx, ly, lh) in lumps:
                    zz += lh * math.exp(-((x - lx) ** 2 / 0.05 + (y - ly) ** 2 / 0.03))
            row.append(b.bm.verts.new((x, y, zz)))
        grid.append(row)
    idx = b.mi(mat)
    for i in range(nx):
        for j in range(ny):
            f = b.bm.faces.new([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]]); f.material_index = idx


def personal_items(b, rng, L, D, z_low, z_top):
    """A few things that say someone sleeps here: boots, a book, a mug, folded clothes, a towel."""
    leather = toon("Leather", (0.2, 0.14, 0.1), noise=0.15, noise_scale=20)
    picks = rng.permutation(6)[:rng.integers(2, 4)]
    for p in picks:
        if p == 0:                                             # boots under the lower bunk, toes out
            x = rng.uniform(-0.5, 0.4)
            for dx in (0.0, 0.13):
                b.box(x + dx, x + dx + 0.1, D - 0.3, D + 0.02, 0.0, 0.12, leather)
                b.box(x + dx, x + dx + 0.1, D - 0.3, D - 0.16, 0.0, 0.26, leather)
        elif p == 1:                                           # a book on the top bunk
            c = toon("BookCover%d" % (rng.integers(4)), [(0.45, 0.14, 0.12), (0.14, 0.24, 0.4), (0.2, 0.32, 0.18), (0.55, 0.45, 0.2)][rng.integers(4)])
            x = rng.uniform(0.0, 0.6)
            b.box(x, x + 0.16, 0.3, 0.52, z_top + 0.2, z_top + 0.235, c)
        elif p == 2:                                           # tin mug on the lower bunk's end
            b.cyl((L / 2 - 0.25, 0.45, z_low + 0.19), (L / 2 - 0.25, 0.45, z_low + 0.27), 0.04, toon("Mug", (0.62, 0.62, 0.58)), seg=10)
        elif p == 3:                                           # folded clothes at the foot
            cols = [(0.3, 0.32, 0.36), (0.42, 0.36, 0.28), (0.5, 0.48, 0.44), (0.24, 0.3, 0.22)]
            zz = z_low + 0.2
            for kk in range(rng.integers(2, 4)):
                c = toon("Folded%d" % (kk % 4), cols[(kk + rng.integers(4)) % 4], noise=0.15, noise_scale=20)
                b.box(L / 2 - 0.5, L / 2 - 0.2, 0.2, 0.55, zz, zz + 0.05, c); zz += 0.05
        elif p == 4:                                           # towel over the end rail of the top bunk
            c = toon("Towel%d" % (rng.integers(3)), [(0.62, 0.6, 0.52), (0.36, 0.46, 0.55), (0.6, 0.42, 0.36)][rng.integers(3)], noise=0.15, noise_scale=20)
            b.box(L / 2 - 0.02, L / 2 + 0.02, 0.15, 0.55, z_top - 0.35, z_top + 0.02, c)
        elif p == 5:                                           # a photograph tucked into the frame
            b.box(-L / 2 + 0.01, -L / 2 + 0.015, 0.25, 0.37, z_top + 0.28, z_top + 0.43, toon("Photo", (0.78, 0.74, 0.62)))



def bunk(name, k=0, stripped=False):
    import numpy as np
    rng = np.random.default_rng(1000 + k)
    b = Builder(name)
    frame = frame_mat(k // 3)
    mat = toon("Mattress", (0.55, 0.52, 0.45), noise=0.1, noise_scale=12)
    L, D = 2.0, 0.9
    for x in (-L / 2 + 0.03, L / 2 - 0.03):
        for y in (0.05, D - 0.05):
            b.cyl((x, y, 0), (x, y, 1.68), 0.024, frame, seg=8)
    for zz in (0.36, 1.26):
        b.box(-L / 2, L / 2, 0.02, 0.08, zz - 0.06, zz, frame)
        b.box(-L / 2, L / 2, D - 0.08, D - 0.02, zz - 0.06, zz, frame)
        b.box(-L / 2 + 0.05, L / 2 - 0.05, 0.08, D - 0.08, zz - 0.03, zz, frame)
        b.box(-L / 2 + 0.06, L / 2 - 0.06, 0.08, D - 0.08, zz, zz + 0.12, mat)
        if not stripped:
            kk = k * 3 + (1 if zz > 1 else 0) * 5
            messy = float(rng.random() < 0.45)
            cloth(b, -L / 2 + 0.32 + 0.2 * rng.random() * messy, L / 2 - 0.04, 0.08, D - 0.08, zz + 0.12, blanket_mat(kk), rng,
                  drape=0.14 + 0.08 * rng.random(), messy=messy)
            if rng.random() < 0.85:                         # not everyone still has a pillow
                pc = [(0.56, 0.54, 0.48), (0.5, 0.52, 0.54), (0.56, 0.5, 0.44)][rng.integers(3)]
                ellipsoid(b, (-L / 2 + 0.24, D / 2 + rng.uniform(-0.08, 0.08), zz + 0.18), (0.17, 0.27, 0.06),
                          toon("Pillow%d" % rng.integers(3), pc, noise=0.08, noise_scale=20))
    for zz in (0.6, 0.85, 1.1):                                 # ladder
        b.box(L / 2 - 0.06, L / 2, 0.1, D - 0.1, zz - 0.015, zz + 0.015, frame)
    if not stripped:
        personal_items(b, rng, L, D, 0.36, 1.26)
    return b.finish(), (L, D)


def bed(name, k=1):
    import numpy as np
    rng = np.random.default_rng(2000 + k)
    b = Builder(name)
    frame = frame_mat(k)
    L, D = 2.0, 0.9
    for x in (-L / 2 + 0.03, L / 2 - 0.03):
        for y in (0.05, D - 0.05):
            b.cyl((x, y, 0), (x, y, 0.5 if x < 0 else 0.42), 0.024, frame, seg=8)
    b.box(-L / 2, -L / 2 + 0.05, 0.03, D - 0.03, 0.2, 0.75, frame)            # headboard
    b.box(-L / 2, L / 2, 0.05, D - 0.05, 0.34, 0.4, frame)
    b.box(-L / 2 + 0.06, L / 2 - 0.06, 0.08, D - 0.08, 0.4, 0.52, toon("Mattress", (0.55, 0.52, 0.45), noise=0.1, noise_scale=12))
    cloth(b, -L / 2 + 0.36, L / 2 - 0.02, 0.08, D - 0.08, 0.52, blanket_mat(k * 7 + 2), rng, drape=0.24, messy=float(k % 2))
    ellipsoid(b, (-L / 2 + 0.25, D / 2, 0.58), (0.17, 0.28, 0.065), toon("Pillow0", (0.56, 0.54, 0.48), noise=0.08, noise_scale=20))
    return b.finish(), (L, D)


def locker(name, width=0.55, open_door=False, k=0):
    import numpy as np
    rng = np.random.default_rng(3000 + k)
    b = Builder(name)
    paint = LOCKER_PAINT[k % len(LOCKER_PAINT)]
    body = toon("Locker%d" % (k % len(LOCKER_PAINT)), _detail_tint("steel_grey", paint), tex="steel_grey", tex_scale=1.2, metal=0.3)
    dark = toon("LockerDark", (0.12, 0.13, 0.1))
    D, H = 0.5, 1.85
    b.box(-width / 2, width / 2, 0.0, D, 0, H, body)
    n = max(1, round(width / 0.5))
    w = width / n
    for i in range(n):
        x0 = -width / 2 + i * w
        b.box(x0 + w - 0.006, x0 + w + 0.006, D, D + 0.004, 0.05, H - 0.05, dark)        # door seam
        for zz in (1.55, 1.6, 1.65):
            b.box(x0 + 0.1, x0 + w - 0.1, D, D + 0.006, zz, zz + 0.018, dark)            # vents
        b.box(x0 + w - 0.08, x0 + w - 0.05, D, D + 0.03, 0.95, 1.1, toon("Steel", (0.5, 0.5, 0.5)))
        if rng.random() < 0.7:                                # name on tape
            b.box(x0 + 0.08, x0 + w - 0.12, D, D + 0.005, 1.42, 1.47, toon("Tape", (0.8, 0.77, 0.66)))
        if rng.random() < 0.35:                               # padlock
            b.box(x0 + w - 0.09, x0 + w - 0.04, D + 0.02, D + 0.05, 0.86, 0.94, toon("Padlock", (0.55, 0.45, 0.18)))
        if rng.random() < 0.3:                                # a photo or a pin-up stuck to the door
            b.box(x0 + 0.1, x0 + 0.24, D, D + 0.004, 1.1, 1.3, toon("Photo", (0.78, 0.74, 0.62)))
        if rng.random() < 0.4:                                # a dent, darker
            zz = rng.uniform(0.3, 0.9)
            b.box(x0 + 0.12, x0 + 0.3, D - 0.004, D + 0.002, zz, zz + 0.16, toon("Locker%dDent" % (k % len(LOCKER_PAINT)),
                  tuple(c * 0.7 for c in _detail_tint("steel_grey", paint)), tex="steel_grey", tex_scale=1.2))
    if open_door:
        b.box(width / 2, width / 2 + 0.02, D, D + w, 0.05, H - 0.05, body)
        b.box(-width / 2 + 0.03, width / 2 - 0.03, D - 0.02, D, 0.06, H - 0.06, dark)
    return b.finish(), (width, D)


def desk(name, with_lamp=True):
    b = Builder(name)
    wood = toon("DeskWood", WOOD, noise=0.12, noise_scale=10)
    L, D = 1.2, 0.6
    b.box(-L / 2, L / 2, 0, D, 0.72, 0.76, wood)
    for x in (-L / 2 + 0.04, L / 2 - 0.04):
        for y in (0.04, D - 0.04):
            b.box(x - 0.025, x + 0.025, y - 0.025, y + 0.025, 0, 0.72, wood)
    b.box(L / 2 - 0.45, L / 2 - 0.04, 0.04, D - 0.02, 0.45, 0.72, wood)
    b.box(L / 2 - 0.4, L / 2 - 0.09, D - 0.02, D, 0.56, 0.62, toon("Steel", (0.5, 0.5, 0.5)))
    paper = toon("Paper", (0.85, 0.83, 0.76))
    b.box(-0.35, -0.05, 0.15, 0.42, 0.76, 0.765, paper)
    b.box(-0.3, 0.0, 0.2, 0.45, 0.765, 0.77, paper)
    b.cyl((0.15, 0.35, 0.76), (0.15, 0.35, 0.86), 0.04, toon("Mug", (0.62, 0.22, 0.16)))
    if with_lamp:
        lamp = toon("LampGreen", (0.18, 0.32, 0.22))
        b.cyl((-0.45, 0.2, 0.76), (-0.45, 0.2, 0.79), 0.08, lamp)
        b.cyl((-0.45, 0.2, 0.79), (-0.4, 0.25, 1.1), 0.012, toon("Steel", (0.5, 0.5, 0.5)))
        b.cyl((-0.4, 0.25, 1.1), (-0.3, 0.33, 1.02), 0.11, lamp, r1=0.04)
    return b.finish(), (L, D)


def chair(name, overturned=False):
    b = Builder(name)
    wood = toon("ChairWood", (0.4, 0.28, 0.17), noise=0.1)
    M = None
    if overturned:
        M = Matrix.Translation((0, 0.25, 0.22)) @ Matrix.Rotation(math.radians(95), 4, "X") @ Matrix.Translation((0, -0.22, -0.2))
    b.box(-0.21, 0.21, 0.05, 0.47, 0.42, 0.46, wood, M)
    for x in (-0.18, 0.18):
        for y in (0.08, 0.44):
            b.box(x - 0.02, x + 0.02, y - 0.02, y + 0.02, 0, 0.42, wood, M)
    b.box(-0.2, 0.2, 0.05, 0.09, 0.46, 0.9, wood, M)
    return b.finish(), (0.5, 0.5)


def table(name, L=1.2, D=0.7, k=0):
    b = Builder(name)
    wood = toon("TableWood", (0.45, 0.33, 0.2), noise=0.12, noise_scale=10)
    b.box(-L / 2, L / 2, 0, D, 0.72, 0.76, wood)
    for x in (-L / 2 + 0.05, L / 2 - 0.05):
        for y in (0.05, D - 0.05):
            b.box(x - 0.03, x + 0.03, y - 0.03, y + 0.03, 0, 0.72, wood)
    b.cyl((-0.2, 0.3, 0.76), (-0.2, 0.3, 0.84), 0.035, toon("Tin", (0.55, 0.55, 0.52)))
    b.box(0.05, 0.3, 0.2, 0.4, 0.76, 0.79, toon("Cards", (0.82, 0.8, 0.72)))
    return b.finish(), (L, D)


def stool(name):
    b = Builder(name)
    wood = toon("ChairWood", (0.4, 0.28, 0.17), noise=0.1)
    b.cyl((0, 0.18, 0.44), (0, 0.18, 0.47), 0.16, wood)
    for a in range(3):
        aa = 2 * math.pi * a / 3
        b.cyl((0.1 * math.cos(aa), 0.18 + 0.1 * math.sin(aa), 0.44), (0.15 * math.cos(aa), 0.18 + 0.15 * math.sin(aa), 0), 0.018, wood, seg=6)
    return b.finish(), (0.36, 0.36)


def radiator(name, sections=10, state="working"):
    """Cast-iron column radiator on wall brackets, fed from below."""
    b = Builder(name)
    rgb = {"working": CREAM, "dead": (0.62, 0.56, 0.46), "frozen": (0.72, 0.8, 0.84)}[state]
    paint = toon(f"Radiator_{state}", rgb, noise=0.15 if state != "working" else 0.06, noise_scale=14)
    pipe = toon("PipeSteel", (0.38, 0.38, 0.36), noise=0.08)
    pitch = 0.065
    L = sections * pitch
    for i in range(sections):
        x = -L / 2 + pitch * (i + 0.5)
        b.box(x - 0.026, x + 0.026, 0.05, 0.16, 0.14, 0.72, paint)
    b.box(-L / 2, L / 2, 0.08, 0.13, 0.66, 0.7, paint)
    b.box(-L / 2, L / 2, 0.08, 0.13, 0.16, 0.2, paint)
    b.cyl((-L / 2 - 0.05, 0.1, 0.0), (-L / 2 - 0.05, 0.1, 0.18), 0.018, pipe)
    b.cyl((-L / 2 - 0.05, 0.1, 0.18), (-L / 2, 0.1, 0.18), 0.018, pipe)
    b.cyl((-L / 2 - 0.05, 0.1, 0.3), (-L / 2 - 0.05, 0.15, 0.3), 0.04, toon("ValveRed", (0.5, 0.12, 0.1)), seg=10)
    if state == "frozen":
        ice = toon("Ice", (0.82, 0.9, 0.95))
        for i in range(0, sections, 2):
            x = -L / 2 + pitch * (i + 0.5)
            b.cyl((x, 0.11, 0.14), (x, 0.11, 0.04), 0.012, ice, seg=6, r1=0.0)
    return b.finish(), (L + 0.1, 0.18)


def curtain(name, k=0, width=0.65, height=1.75):
    """One blanket pinned to a wire: a hanging panel with soft folds (free-standing partition)."""
    b = Builder(name)
    cloth = blanket_mat(k * 3 + 1)
    nx, nz = 10, 6
    grid = []
    for iz in range(nz + 1):
        row = []
        for ix in range(nx + 1):
            x = -width / 2 + width * ix / nx
            z = 2.0 - height * iz / nz
            y = 0.04 * math.sin(ix / nx * math.pi * 3 + k) * (0.4 + 0.6 * iz / nz)
            row.append(b.bm.verts.new((x, y, z)))
        grid.append(row)
    idx = b.mi(cloth)
    for iz in range(nz):
        for ix in range(nx):
            f = b.bm.faces.new([grid[iz][ix], grid[iz][ix + 1], grid[iz + 1][ix + 1], grid[iz + 1][ix]]); f.material_index = idx
    wire = toon("Wire", (0.3, 0.3, 0.3))
    b.cyl((-width / 2 - 0.02, 0, 2.01), (width / 2 + 0.02, 0, 2.01), 0.006, wire, seg=6)
    ob = b.finish(outline=0.008)
    ob.modifiers.new("Thick", "SOLIDIFY").thickness = 0.015
    ob.modifiers.move(1, 0)
    return ob, (width, 0.1)


def toolbox(name):
    b = Builder(name)
    red = toon("ToolRed", (0.55, 0.14, 0.1), noise=0.08)
    b.box(-0.28, 0.28, 0.02, 0.26, 0, 0.24, red)
    b.box(-0.2, 0.2, 0.12, 0.16, 0.24, 0.3, toon("Steel", (0.5, 0.5, 0.5)))
    bottle = toon("GasBottle", (0.2, 0.35, 0.5))
    b.cyl((0.42, 0.14, 0), (0.42, 0.14, 0.55), 0.08, bottle)
    b.cyl((0.42, 0.14, 0.55), (0.42, 0.14, 0.62), 0.03, toon("Brass", (0.6, 0.48, 0.2)))
    b.cyl((0.6, 0.14, 0), (0.6, 0.14, 0.5), 0.07, toon("GasRed", (0.55, 0.18, 0.14)))
    return b.finish(), (1.0, 0.3)


def toolbox_bottles(name):
    """Just the gas bottles beside the toolbox (the box itself is a Tripo model)."""
    b = Builder(name)
    bottle = toon("GasBottle", (0.2, 0.35, 0.5))
    b.cyl((0.42, 0.14, 0), (0.42, 0.14, 0.55), 0.08, bottle)
    b.cyl((0.42, 0.14, 0.55), (0.42, 0.14, 0.62), 0.03, toon("Brass", (0.6, 0.48, 0.2)))
    b.cyl((0.6, 0.14, 0), (0.6, 0.14, 0.5), 0.07, toon("GasRed", (0.55, 0.18, 0.14)))
    return b.finish(), (1.0, 0.3)


def crate(name, h=0.55):
    b = Builder(name)
    wood = toon("CrateWood", (0.5, 0.4, 0.25), noise=0.15, noise_scale=10)
    dark = toon("CrateDark", (0.3, 0.22, 0.13))
    b.box(-0.3, 0.3, 0.0, 0.6, 0, h, wood)
    for zz in (0.12, h - 0.12):
        b.box(-0.31, 0.31, -0.01, 0.61, zz - 0.02, zz + 0.02, dark)
    return b.finish(), (0.62, 0.62)


def bucket(name):
    b = Builder(name)
    b.cyl((0, 0.18, 0), (0, 0.18, 0.3), 0.13, toon("Zinc", (0.55, 0.56, 0.55)), r1=0.16)
    return b.finish(), (0.34, 0.34)


def shelf(name):
    b = Builder(name)
    frame = toon("ShelfSteel", (0.42, 0.44, 0.42), noise=0.08)
    L, D = 1.1, 0.45
    for x in (-L / 2, L / 2):
        for y in (0.02, D - 0.02):
            b.box(x - 0.02, x + 0.02, y - 0.02, y + 0.02, 0, 1.9, frame)
    for zz in (0.12, 0.6, 1.1, 1.6):
        b.box(-L / 2, L / 2, 0.0, D, zz, zz + 0.025, frame)
    for i, zz in enumerate((0.145, 0.625, 1.125)):
        for j in range(3):
            b.box(-L / 2 + 0.05 + j * 0.34, -L / 2 + 0.33 + j * 0.34, 0.05, D - 0.05, zz, zz + 0.14 + 0.04 * j,
                  blanket_mat(i * 4 + j * 3))
    b.box(-0.4, 0.1, 0.05, 0.4, 1.625, 1.85, toon("Carton", (0.55, 0.45, 0.3), noise=0.1))
    return b.finish(), (L, D)


def sinks(name, n=3):
    b = Builder(name)
    enamel = toon("Enamel", (0.8, 0.8, 0.76), noise=0.06)
    dark = toon("SinkDark", (0.2, 0.22, 0.22))
    pipe = toon("PipeSteel", (0.38, 0.38, 0.36), noise=0.08)
    L = 0.7 * n
    for i in range(n):
        x = -L / 2 + 0.35 + i * 0.7
        b.box(x - 0.26, x + 0.26, 0.02, 0.45, 0.7, 0.85, enamel)
        b.box(x - 0.2, x + 0.2, 0.08, 0.4, 0.84, 0.851, dark)
        b.cyl((x, 0.05, 0.85), (x, 0.05, 1.0), 0.015, pipe)
        b.cyl((x, 0.05, 1.0), (x, 0.17, 1.0), 0.015, pipe)
        b.cyl((x, 0.2, 0.0), (x, 0.2, 0.7), 0.025, pipe)
    return b.finish(), (L, 0.45)


def stall(name):
    """Toilet cubicle: painted steel partitions on legs, a door ajar with a latch, a bowl and a cistern."""
    b = Builder(name)
    panel = toon("StallPanelPaint", _detail_tint("steel_green", (0.4, 0.5, 0.44)), tex="steel_green", tex_scale=1.2, metal=0.2)
    leg = toon("Steel", (0.5, 0.5, 0.5))
    for x0, x1 in ((-0.45, -0.42), (0.42, 0.45)):
        b.box(x0, x1, 0, 1.2, 0.15, 1.85, panel)
        for y in (0.05, 1.15):
            b.box(x0, x1, y - 0.02, y + 0.02, 0, 0.15, leg)
    b.box(-0.42, 0.42, 1.17, 1.2, 0.15, 1.85, panel)                      # back
    # door, swung half open into the cubicle
    M = Matrix.Translation((0.42, 0.0, 0)) @ Matrix.Rotation(math.radians(55), 4, "Z") @ Matrix.Translation((-0.42, 0.0, 0))
    b.box(-0.4, 0.4, -0.015, 0.015, 0.15, 1.8, panel, M)
    b.box(-0.36, -0.3, -0.04, -0.015, 0.98, 1.02, leg, M)                   # latch
    b.box(-0.15, 0.15, 0.7, 1.15, 0.0, 0.42, toon("Enamel", (0.8, 0.8, 0.76), noise=0.06))
    b.box(-0.2, 0.2, 1.05, 1.17, 1.4, 1.6, toon("Enamel", (0.8, 0.8, 0.76), noise=0.06))      # cistern
    b.cyl((0.12, 1.12, 1.45), (0.12, 1.12, 1.0), 0.012, leg, seg=6)                       # chain
    return b.finish(), (0.9, 1.2)


def laundry(name, k=0):
    b = Builder(name)
    pole = toon("Wire", (0.3, 0.3, 0.3))
    L = 1.8
    for x in (-L / 2, L / 2):
        b.cyl((x, 0.1, 0), (x, 0.1, 1.8), 0.02, pole, seg=8)
    b.cyl((-L / 2, 0.1, 1.75), (L / 2, 0.1, 1.75), 0.006, pole, seg=6)
    for i in range(3):
        c = blanket_mat(k * 3 + i * 4)
        x = -L / 2 + 0.15 + i * 0.55
        b.box(x, x + 0.45, 0.08, 0.12, 1.0 + 0.1 * (i % 2), 1.75, c)
        b.box(x + 0.1, x + 0.13, 0.06, 0.14, 1.72, 1.79, toon("Peg", (0.55, 0.42, 0.25)))
    return b.finish(), (L, 0.25)


def pump(name):
    b = Builder(name)
    paint = toon("PumpGreen", (0.28, 0.4, 0.33), noise=0.1)
    steel = toon("PipeSteel", (0.38, 0.38, 0.36), noise=0.08)
    b.box(-0.6, 0.6, 0.0, 0.7, 0, 0.15, toon("ConcretePlinth", (0.5, 0.5, 0.47), noise=0.1))
    b.cyl((-0.5, 0.35, 0.45), (0.05, 0.35, 0.45), 0.24, paint)
    b.cyl((0.05, 0.35, 0.45), (0.45, 0.35, 0.45), 0.2, toon("PumpGrey", (0.45, 0.47, 0.46), noise=0.08), seg=16)
    b.cyl((0.25, 0.35, 0.65), (0.25, 0.35, 1.6), 0.07, steel)
    b.cyl((0.45, 0.35, 0.45), (0.6, 0.35, 0.45), 0.07, steel)
    b.cyl((0.25, 0.35, 1.0), (0.25, 0.47, 1.0), 0.13, toon("ValveRed", (0.5, 0.12, 0.1)), seg=12)
    return b.finish(), (1.2, 0.7)


def workbench(name):
    b = Builder(name)
    wood = toon("BenchWood", (0.38, 0.27, 0.16), noise=0.14, noise_scale=10)
    steel = toon("Steel", (0.5, 0.5, 0.5))
    L, D = 1.8, 0.7
    b.box(-L / 2, L / 2, 0, D, 0.84, 0.9, wood)
    for x in (-L / 2 + 0.05, L / 2 - 0.05):
        for y in (0.05, D - 0.05):
            b.box(x - 0.035, x + 0.035, y - 0.035, y + 0.035, 0, 0.84, wood)
    b.box(-L / 2 + 0.05, L / 2 - 0.05, 0.05, D - 0.05, 0.2, 0.24, wood)
    b.box(0.5, 0.75, 0.45, 0.65, 0.9, 1.05, steel)                         # vice
    b.box(-0.6, -0.1, 0.1, 0.4, 0.9, 0.95, toon("ToolRed", (0.55, 0.14, 0.1), noise=0.08))
    return b.finish(), (L, D)


# ---------------------------------------------------------------- Level 2 west: commons, kitchen, clinic, school, archive
def bench(name, L=2.2):
    b = Builder(name)
    wood = toon("BenchSeat", (0.43, 0.31, 0.19), noise=0.14, noise_scale=10)
    D = 0.32
    b.box(-L / 2, L / 2, 0.0, D, 0.42, 0.46, wood)
    for x in (-L / 2 + 0.12, 0.0, L / 2 - 0.12):
        b.box(x - 0.03, x + 0.03, 0.04, D - 0.04, 0.0, 0.42, wood)
    b.box(-L / 2 + 0.1, L / 2 - 0.1, D / 2 - 0.02, D / 2 + 0.02, 0.12, 0.16, wood)      # stretcher
    b.box(L / 2 - 0.5, L / 2 - 0.36, 0.02, D - 0.02, 0.46, 0.47, toon("PatchWood", (0.56, 0.44, 0.28)))  # a repair
    return b.finish(), (L, D)


def stove(name):
    """Cast-iron cooking range on legs, two big pots, a flue going up the wall."""
    b = Builder(name)
    iron = toon("StoveIron", (0.16, 0.16, 0.15), noise=0.1)
    steel = toon("Steel", (0.5, 0.5, 0.5))
    L, D = 1.6, 0.8
    b.box(-L / 2, L / 2, 0.05, D, 0.12, 0.88, iron)
    for x in (-L / 2 + 0.06, L / 2 - 0.06):
        for y in (0.1, D - 0.06):
            b.box(x - 0.04, x + 0.04, y - 0.04, y + 0.04, 0, 0.12, iron)
    for x in (-0.55, 0.0, 0.55):                                             # oven doors
        b.box(x - 0.22, x + 0.22, D, D + 0.02, 0.25, 0.65, toon("StoveDoor", (0.24, 0.23, 0.21)))
        b.box(x - 0.12, x + 0.12, D + 0.02, D + 0.05, 0.6, 0.62, steel)
    b.box(-L / 2 + 0.05, L / 2 - 0.05, 0.1, D - 0.05, 0.88, 0.9, toon("Hotplate", (0.3, 0.27, 0.25)))
    b.cyl((-0.4, 0.45, 0.9), (-0.4, 0.45, 1.25), 0.24, toon("PotAlu", (0.6, 0.6, 0.58), noise=0.08), seg=16)
    b.cyl((0.35, 0.4, 0.9), (0.35, 0.4, 1.08), 0.2, toon("PotEnamel", (0.55, 0.2, 0.14)), seg=16)
    b.cyl((0.0, 0.1, 0.9), (0.0, 0.1, 2.6), 0.09, iron)                     # flue
    return b.finish(), (L, D)


def counter(name, L=2.0, hatch=False):
    """Kitchen or serving counter: steel-topped cupboards; with hatch=True, the Exchange's trading counter."""
    b = Builder(name)
    body = toon("CounterBody", (0.38, 0.42, 0.4), noise=0.1)
    top = toon("CounterTop", (0.58, 0.58, 0.56), noise=0.06)
    D = 0.62
    b.box(-L / 2, L / 2, 0.0, D, 0.0, 0.88, body)
    b.box(-L / 2 - 0.02, L / 2 + 0.02, -0.02, D + 0.03, 0.88, 0.92, top)
    n = max(1, int(L / 0.6))
    for i in range(n):
        x = -L / 2 + (i + 0.5) * L / n
        b.box(x - L / n / 2 + 0.03, x + L / n / 2 - 0.03, D, D + 0.01, 0.08, 0.8, toon("CounterDoor", (0.33, 0.37, 0.35)))
        b.box(x - 0.06, x + 0.06, D + 0.01, D + 0.03, 0.7, 0.73, toon("Steel", (0.5, 0.5, 0.5)))
    if hatch:                                                # goods for trade and a tin cash box
        for i, c in enumerate([(0.62, 0.22, 0.16), (0.55, 0.5, 0.3), (0.3, 0.35, 0.45)]):
            b.box(-L / 2 + 0.15 + i * 0.25, -L / 2 + 0.35 + i * 0.25, 0.15, 0.4, 0.92, 1.05 + 0.04 * i, toon(f"Goods{i}", c, noise=0.1))
        b.box(0.3, 0.6, 0.2, 0.45, 0.92, 1.02, toon("CashTin", (0.42, 0.45, 0.38), noise=0.1))
        b.box(-L / 2, L / 2, 0.0, 0.05, 0.92, 1.9, toon("HatchFrame", (0.4, 0.31, 0.2), noise=0.12))
    else:
        b.cyl((-0.5, 0.3, 0.92), (-0.5, 0.3, 1.1), 0.12, toon("PotAlu", (0.6, 0.6, 0.58), noise=0.08), seg=12)
        b.box(0.1, 0.55, 0.12, 0.45, 0.92, 0.95, toon("ChopBoard", (0.55, 0.4, 0.24)))
    return b.finish(), (L, D)


def cabinet(name):
    """Steel filing cabinet, four drawers."""
    b = Builder(name)
    body = toon("FilingGrey", (0.45, 0.47, 0.44), noise=0.08)
    D = 0.62
    b.box(-0.24, 0.24, 0.0, D, 0.0, 1.32, body)
    for k in range(4):
        z = 0.06 + k * 0.32
        b.box(-0.21, 0.21, D, D + 0.01, z, z + 0.28, toon("FilingDrawer", (0.4, 0.42, 0.39)))
        b.box(-0.07, 0.07, D + 0.01, D + 0.03, z + 0.2, z + 0.23, toon("Steel", (0.5, 0.5, 0.5)))
        b.box(-0.05, 0.05, D + 0.01, D + 0.012, z + 0.12, z + 0.16, toon("Paper", (0.85, 0.83, 0.76)))
    return b.finish(), (0.48, D)


def medscreen(name):
    """Three-leaf folding screen between ward beds."""
    b = Builder(name)
    frame = toon("ScreenFrame", (0.6, 0.62, 0.6), noise=0.05)
    cloth = toon("ScreenCloth", (0.74, 0.78, 0.76), noise=0.1, noise_scale=10)
    for i, x in enumerate((-0.6, 0.0, 0.6)):
        y = 0.12 if i == 1 else 0.0
        b.box(x - 0.29, x + 0.29, y, y + 0.03, 0.18, 1.7, cloth)
        for xx in (x - 0.3, x + 0.3):
            b.cyl((xx, y + 0.015, 0.0), (xx, y + 0.015, 1.75), 0.015, frame, seg=6)
    return b.finish(), (1.8, 0.2)


def medcab(name):
    """White medicine cabinet with glass doors and too few bottles."""
    b = Builder(name)
    white = toon("MedWhite", (0.8, 0.8, 0.76), noise=0.08)
    D = 0.42
    b.box(-0.45, 0.45, 0.0, D, 0.0, 1.8, white)
    b.box(-0.41, 0.41, D - 0.01, D + 0.004, 0.95, 1.72, toon("MedGlass", (0.5, 0.6, 0.62)))
    for k, z in enumerate((1.0, 1.35)):
        b.box(-0.41, 0.41, 0.05, D - 0.02, z, z + 0.02, white)
        for j in range(2 + k):
            x = -0.3 + j * 0.22
            b.cyl((x, 0.2, z + 0.02), (x, 0.2, z + 0.18), 0.04, toon(f"Bottle{(j + k) % 3}", [(0.45, 0.3, 0.12), (0.3, 0.45, 0.4), (0.75, 0.75, 0.72)][(j + k) % 3]), seg=8)
    b.box(-0.41, 0.41, D, D + 0.01, 0.06, 0.9, toon("MedDoor", (0.74, 0.74, 0.7)))
    b.box(-0.1, 0.1, D + 0.01, D + 0.014, 0.6, 0.8, flat("RedCross", (0.7, 0.1, 0.08)))
    return b.finish(), (0.9, D)


def schooldesk(name):
    """A two-seat school desk with its bench joined on."""
    b = Builder(name)
    wood = toon("SchoolWood", (0.5, 0.37, 0.22), noise=0.12, noise_scale=10)
    frame = toon("SchoolFrame", (0.25, 0.3, 0.28), noise=0.08)
    L = 1.1
    b.box(-L / 2, L / 2, 0.0, 0.42, 0.68, 0.72, wood)                       # slanted lid, roughly
    b.box(-L / 2, L / 2, 0.0, 0.05, 0.72, 0.78, wood)
    b.box(-L / 2, L / 2, 0.55, 0.85, 0.4, 0.44, wood)                        # seat
    for x in (-L / 2 + 0.05, L / 2 - 0.05):
        b.box(x - 0.025, x + 0.025, 0.05, 0.8, 0.0, 0.05, frame)
        b.box(x - 0.025, x + 0.025, 0.15, 0.2, 0.05, 0.68, frame)
        b.box(x - 0.025, x + 0.025, 0.68, 0.73, 0.05, 0.4, frame)
    b.cyl((0.3, 0.12, 0.72), (0.3, 0.12, 0.74), 0.03, toon("Inkwell", (0.15, 0.15, 0.2)), seg=8)
    b.box(-0.35, -0.05, 0.12, 0.34, 0.72, 0.73, toon("Paper", (0.85, 0.83, 0.76)))
    return b.finish(), (L, 0.85)


def sacks(name):
    """A pile of grain and potato sacks from the hydroponics bays."""
    b = Builder(name)
    for i, (x, y, z, s) in enumerate(((-0.3, 0.25, 0.0, 1.0), (0.25, 0.3, 0.0, 0.95), (0.0, 0.3, 0.32, 0.9))):
        m = toon(f"Sack{i % 2}", [(0.6, 0.53, 0.38), (0.52, 0.46, 0.33)][i % 2], noise=0.18, noise_scale=12)
        b.box(x - 0.26 * s, x + 0.26 * s, y - 0.2 * s, y + 0.2 * s, z, z + 0.34 * s, m)
        b.box(x - 0.1 * s, x + 0.1 * s, y - 0.08 * s, y + 0.08 * s, z + 0.34 * s, z + 0.42 * s, m)
    return b.finish(), (1.1, 0.6)


def file_shelf(name, k=0):
    """Archive shelving: box files, bundles of paper and a few loose ledgers."""
    b = Builder(name)
    frame = toon("ShelfSteel", (0.42, 0.44, 0.42), noise=0.08)
    L, D = 1.1, 0.42
    for x in (-L / 2, L / 2):
        for y in (0.02, D - 0.02):
            b.box(x - 0.02, x + 0.02, y - 0.02, y + 0.02, 0, 2.0, frame)
    boxes = [(0.5, 0.42, 0.3), (0.42, 0.4, 0.36), (0.55, 0.5, 0.38), (0.36, 0.33, 0.28)]
    for i, zz in enumerate((0.1, 0.55, 1.0, 1.45)):
        b.box(-L / 2, L / 2, 0.0, D, zz, zz + 0.025, frame)
        x = -L / 2 + 0.04
        j = 0
        while x < L / 2 - 0.12:
            w = 0.08 + 0.03 * ((i * 7 + j * 3 + k) % 3)
            h = 0.3 - 0.04 * ((i + j + k) % 2)
            if (i * 5 + j * 2 + k) % 9 == 4:                 # a gap where a file was taken
                x += w; j += 1; continue
            c = boxes[(i + j + k) % 4]
            b.box(x, x + w - 0.01, 0.06, D - 0.06, zz + 0.025, zz + 0.025 + h, toon(f"BoxFile{(i + j + k) % 4}", c, noise=0.1))
            x += w; j += 1
    return b.finish(), (L, D)


# ---------------------------------------------------------------- Level 4 west: Council, Engineering, valve gallery
def terminal(name):
    """Desk with a green-screen terminal and a printer: Varga's terminal."""
    b = Builder(name)
    wood = toon("DeskWood", WOOD, noise=0.12, noise_scale=10)
    case = toon("TermCase", (0.62, 0.6, 0.52), noise=0.06)
    L, D = 1.4, 0.7
    b.box(-L / 2, L / 2, 0, D, 0.72, 0.76, wood)
    for x in (-L / 2 + 0.04, L / 2 - 0.04):
        b.box(x - 0.03, x + 0.03, 0.04, D - 0.04, 0, 0.72, wood)
    b.box(-0.35, 0.15, 0.1, 0.5, 0.76, 1.16, case)
    b.box(-0.3, 0.1, 0.5, 0.51, 0.82, 1.1, flat("TermGlass", (0.12, 0.28, 0.16)))
    for k in range(4):
        b.box(-0.26, -0.26 + 0.08 + 0.06 * (k % 3), 0.511, 0.513, 1.04 - k * 0.05, 1.05 - k * 0.05, flat("TermText", (0.45, 0.85, 0.5)))
    b.box(-0.35, 0.2, 0.52, 0.68, 0.76, 0.79, case)                           # keyboard
    b.box(0.3, 0.62, 0.1, 0.45, 0.76, 0.92, case)                             # printer
    b.box(0.32, 0.6, 0.3, 0.52, 0.92, 0.93, toon("Paper", (0.85, 0.83, 0.76)))
    return b.finish(), (L, D)


def radioset(name):
    """The silent radio: a tall cabinet set with dials, a headset and a morse key on a bench."""
    b = Builder(name)
    grey = toon("RadioGrey", (0.36, 0.4, 0.38), noise=0.08)
    dark = toon("RadioDark", (0.14, 0.15, 0.14))
    L, D = 1.6, 0.6
    b.box(-L / 2, L / 2, 0, D, 0.72, 0.76, toon("BenchWood", (0.38, 0.27, 0.16), noise=0.14, noise_scale=10))
    for x in (-L / 2 + 0.04, L / 2 - 0.04):
        b.box(x - 0.03, x + 0.03, 0.04, D - 0.04, 0, 0.72, grey)
    b.box(-0.7, 0.4, 0.02, 0.4, 0.76, 1.75, grey)
    for r in range(3):
        for c in range(4):
            b.cyl((-0.58 + c * 0.25, 0.4, 0.95 + r * 0.25), (-0.58 + c * 0.25, 0.43, 0.95 + r * 0.25), 0.05, dark, seg=10)
    b.box(-0.6, 0.0, 0.4, 0.41, 1.55, 1.68, flat("RadioDial", (0.82, 0.74, 0.5)))
    b.cyl((0.6, 0.35, 0.76), (0.6, 0.35, 0.8), 0.06, dark, seg=10)            # morse key
    b.box(0.45, 0.65, 0.15, 0.3, 0.76, 0.86, dark)                            # headset
    return b.finish(), (L, D)


def maptable(name):
    b = Builder(name)
    wood = toon("TableWood", (0.45, 0.33, 0.2), noise=0.12, noise_scale=10)
    L, D = 1.8, 1.1
    b.box(-L / 2, L / 2, 0, D, 0.84, 0.88, wood)
    for x in (-L / 2 + 0.06, L / 2 - 0.06):
        for y in (0.06, D - 0.06):
            b.box(x - 0.04, x + 0.04, y - 0.04, y + 0.04, 0, 0.84, wood)
    b.box(-0.75, 0.75, 0.08, D - 0.08, 0.88, 0.885, toon("MapPaper", (0.78, 0.74, 0.6), noise=0.12, noise_scale=8))
    for k in range(5):
        b.box(-0.6 + k * 0.28, -0.55 + k * 0.28, 0.2, 0.9, 0.885, 0.887, flat("MapLine", (0.4, 0.35, 0.3)))
    b.cyl((0.4, 0.5, 0.885), (0.4, 0.5, 0.9), 0.12, flat("MapCircle", (0.6, 0.15, 0.1)), seg=16)
    return b.finish(), (L, D)


def floorlamp(name):
    b = Builder(name)
    brass = toon("Brass", (0.6, 0.48, 0.24), noise=0.06)
    b.cyl((0, 0.15, 0), (0, 0.15, 0.04), 0.14, brass, seg=12)
    b.cyl((0, 0.15, 0.04), (0, 0.15, 1.5), 0.015, brass, seg=8)
    b.cyl((0, 0.15, 1.42), (0, 0.15, 1.7), 0.22, toon("LampShade", (0.78, 0.66, 0.42), noise=0.08), seg=14, r1=0.12)
    return b.finish(), (0.3, 0.3)


def safe(name):
    b = Builder(name)
    body = toon("SafeGreen", (0.2, 0.28, 0.22), noise=0.08)
    b.box(-0.35, 0.35, 0.0, 0.6, 0.0, 0.9, body)
    b.box(-0.3, 0.3, 0.6, 0.62, 0.06, 0.84, toon("SafeDoor", (0.24, 0.32, 0.26), noise=0.08))
    b.cyl((0.0, 0.62, 0.55), (0.0, 0.66, 0.55), 0.08, toon("Brass", (0.6, 0.48, 0.24), noise=0.06), seg=14)
    b.box(0.15, 0.25, 0.62, 0.66, 0.35, 0.45, toon("Steel", (0.5, 0.5, 0.5)))
    return b.finish(), (0.7, 0.6)


def lathe(name):
    b = Builder(name)
    paint = toon("MachineGreen", (0.3, 0.38, 0.32), noise=0.1)
    steel = toon("Steel", (0.5, 0.5, 0.5))
    L, D = 1.8, 0.6
    for x in (-0.7, 0.7):
        b.box(x - 0.2, x + 0.2, 0.05, D - 0.05, 0, 0.85, paint)
    b.box(-L / 2, L / 2, 0.1, D - 0.1, 0.85, 1.0, paint)
    b.box(-0.85, -0.45, 0.1, D - 0.1, 1.0, 1.35, paint)                     # headstock
    b.cyl((-0.45, D / 2, 1.18), (0.6, D / 2, 1.18), 0.03, steel, seg=8)
    b.box(0.55, 0.8, 0.15, D - 0.15, 1.0, 1.25, paint)                       # tailstock
    b.box(-0.1, 0.2, 0.05, D - 0.05, 1.0, 1.12, steel)                       # carriage
    b.box(-0.6, 0.6, D - 0.02, D, 0.3, 0.32, toon("Hazard", (0.75, 0.6, 0.12)))
    return b.finish(), (L, D)


def monitors(name):
    """Multi-monitor telemetry & intercom station for Administration Office."""
    b = Builder(name)
    steel = toon("ConsoleSteel", (0.34, 0.37, 0.35), noise=0.1)
    dark = toon("RadioDark", (0.14, 0.15, 0.14))
    case = toon("TermCase", (0.54, 0.52, 0.45), noise=0.08)
    brass = toon("Brass", (0.6, 0.48, 0.24), noise=0.06)
    L, D = 1.3, 0.65
    b.box(-L / 2, L / 2, 0.0, D, 0.0, 0.74, steel)
    b.box(-L / 2 - 0.02, L / 2 + 0.02, -0.02, D + 0.02, 0.74, 0.78, toon("BenchWood", (0.38, 0.27, 0.16), noise=0.12))
    # Left CRT monitor (amber heating telemetry)
    b.box(-0.56, -0.08, 0.08, 0.46, 0.78, 1.18, case)
    b.box(-0.51, -0.13, 0.46, 0.47, 0.83, 1.13, flat("AmberCRT", (0.28, 0.16, 0.04)))
    for k in range(3):
        b.box(-0.47, -0.18, 0.471, 0.473, 0.88 + k * 0.07, 0.895 + k * 0.07, flat("AmberTrace", (0.95, 0.62, 0.18)))
    # Right CRT monitor (sector status, stacked above intercom switcher)
    b.box(0.02, 0.48, 0.08, 0.44, 0.78, 0.96, dark)
    b.box(0.04, 0.46, 0.10, 0.42, 0.96, 1.32, case)
    b.box(0.08, 0.42, 0.42, 0.43, 1.01, 1.27, flat("TermGlass", (0.12, 0.28, 0.16)))
    # Gooseneck intercom microphone & red push-to-talk key on right
    b.box(-0.02, 0.14, 0.46, 0.60, 0.78, 0.83, dark)
    b.cyl((0.06, 0.52, 0.83), (0.06, 0.56, 1.02), 0.01, brass, seg=6)
    b.cyl((0.06, 0.56, 1.02), (0.06, 0.58, 1.05), 0.024, dark, seg=8)
    b.cyl((0.10, 0.55, 0.83), (0.10, 0.55, 0.845), 0.018, toon("ValveRed", (0.65, 0.12, 0.1)), seg=8)
    # Ledger & loose reports
    b.box(0.22, 0.54, 0.44, 0.62, 0.78, 0.80, toon("Paper", (0.85, 0.83, 0.76)))
    return b.finish(), (L, D)


def boiler_assembly(name):
    """Main Heating Assembly & Primary Pressure Regulator: massive horizontal heat exchanger,
    glowing orange inspection port, insulated headers, and cracked cast-iron regulator with weld shims."""
    b = Builder(name)
    plinth = toon("ConcretePlinth", (0.44, 0.43, 0.40), noise=0.16)
    teal = toon("BoilerTeal", (0.23, 0.37, 0.34), noise=0.14, noise_scale=6)
    rust = toon("BoilerRust", RUST, noise=0.22, noise_scale=8)
    clad = toon("BoilerClad", (0.52, 0.53, 0.50), noise=0.1)
    steel = toon("PipeSteel", (0.36, 0.36, 0.34), noise=0.1)
    iron = toon("CastIron", (0.22, 0.21, 0.20), noise=0.14)
    brass = toon("Brass", (0.62, 0.48, 0.22), noise=0.06)
    red = toon("ValveRed", (0.55, 0.12, 0.10))
    glow_out = flat("FurnaceGlowOut", (0.88, 0.36, 0.08))
    glow_in = flat("FurnaceGlowIn", (1.0, 0.76, 0.28))

    L, D = 3.4, 1.6
    # Heavy concrete & rusted I-beam plinth
    b.box(-L / 2, L / 2, 0.05, D - 0.05, 0.0, 0.22, plinth)
    b.box(-L / 2 + 0.04, L / 2 - 0.04, D - 0.07, D - 0.03, 0.18, 0.23, toon("Hazard", (0.75, 0.58, 0.12)))
    for x in (-1.2, -0.3, 0.55):
        b.box(x - 0.12, x + 0.12, 0.18, D - 0.18, 0.22, 0.48, rust)

    # Main horizontal heat-exchanger pressure drum (x from -1.55 to +0.65)
    b.cyl((-1.55, 0.80, 1.02), (0.65, 0.80, 1.02), 0.56, teal, seg=20)
    # Dished end caps & heavy bolted rings
    b.cyl((-1.62, 0.80, 1.02), (-1.55, 0.80, 1.02), 0.48, rust, seg=18)
    b.cyl((0.65, 0.80, 1.02), (0.72, 0.80, 1.02), 0.50, rust, seg=18)
    for x in (-1.35, -0.75, -0.15, 0.45):
        b.cyl((x - 0.03, 0.80, 1.02), (x + 0.03, 0.80, 1.02), 0.575, clad, seg=20)
    # Rusted inspection patch on upper drum
    b.cyl((-0.65, 0.80, 1.02), (-0.25, 0.80, 1.02), 0.568, rust, seg=16)

    # Warm glowing orange furnace / exchanger sight-glass port on the camera-facing front (+y)
    b.cyl((-0.85, 1.32, 0.96), (-0.85, 1.42, 0.96), 0.20, iron, seg=16)
    b.cyl((-0.85, 1.42, 0.96), (-0.85, 1.44, 0.96), 0.15, glow_out, seg=16)
    b.cyl((-0.85, 1.44, 0.96), (-0.85, 1.45, 0.96), 0.09, glow_in, seg=12)
    # Second smaller burner sight port
    b.cyl((-0.30, 1.32, 0.96), (-0.30, 1.40, 0.96), 0.14, iron, seg=14)
    b.cyl((-0.30, 1.40, 0.96), (-0.30, 1.42, 0.96), 0.09, glow_out, seg=12)

    # Top steam dome & overhead riser pipes
    b.cyl((-0.95, 0.80, 1.50), (-0.95, 0.80, 1.88), 0.24, teal, seg=16)
    b.cyl((-0.95, 0.80, 1.88), (-0.95, 0.80, 1.94), 0.28, rust, seg=16)
    b.cyl((-0.95, 0.80, 1.94), (-0.95, 0.80, 2.50), 0.13, clad, seg=14)
    b.cyl((0.15, 0.80, 1.50), (0.15, 0.80, 2.50), 0.12, steel, seg=14)

    # Right side (+x = 0.72..1.55): MAIN THERMAL PRESSURE REGULATOR & GOVERNOR ASSEMBLY (fractured)
    b.cyl((0.70, 0.80, 1.02), (1.18, 0.80, 1.02), 0.22, iron, seg=16)
    # Regulator diaphragm bell housing
    b.cyl((1.05, 0.80, 0.55), (1.05, 0.80, 1.48), 0.28, iron, seg=16)
    b.cyl((1.05, 0.80, 1.48), (1.05, 0.80, 1.72), 0.18, rust, seg=14)
    b.cyl((1.05, 0.80, 1.72), (1.05, 0.80, 1.92), 0.06, brass, seg=10)
    # Improvised weld shims & cracked flange collar (bright raw steel + scorched rust + orange leak glow)
    shim = toon("WeldShim", (0.68, 0.68, 0.70))
    b.box(0.82, 0.96, 0.96, 1.12, 0.92, 1.14, rust)
    b.box(0.84, 0.94, 1.08, 1.14, 0.95, 0.99, shim)
    b.box(0.85, 0.95, 1.08, 1.14, 1.05, 1.09, shim)
    b.box(0.86, 0.92, 1.11, 1.15, 0.99, 1.05, glow_out)
    # Outgoing main distribution header & red emergency bypass handwheels
    b.cyl((1.18, 0.80, 1.02), (1.62, 0.80, 1.02), 0.16, steel, seg=14)
    b.cyl((1.38, 0.80, 1.02), (1.38, 0.80, 2.45), 0.12, toon("PipeBandRed", (0.5, 0.1, 0.1)), seg=14)
    b.cyl((1.05, 1.08, 1.18), (1.05, 1.26, 1.18), 0.18, red, seg=14)
    b.cyl((1.38, 0.92, 1.35), (1.38, 1.12, 1.35), 0.16, red, seg=14)

    # Twin pressure gauges mounted on the front of the regulator assembly
    for gx in (0.78, 1.24):
        b.cyl((gx, 0.98, 1.30), (gx, 1.12, 1.52), 0.015, brass, seg=6)
        b.cyl((gx, 1.10, 1.55), (gx, 1.16, 1.55), 0.10, brass, seg=14)
        b.cyl((gx, 1.16, 1.55), (gx, 1.175, 1.55), 0.085, flat("GaugeFace", (0.88, 0.86, 0.78)), seg=14)
        b.box(gx, gx + 0.055, 1.176, 1.18, 1.55, 1.60, red)
    return b.finish(), (L, D)


def control_panel(name):
    """Heavy industrial heating control switchboard & regulator console."""
    b = Builder(name)
    body = toon("PanelOlive", (0.31, 0.36, 0.32), noise=0.12)
    dark = toon("PanelDark", (0.15, 0.16, 0.15))
    steel = toon("Steel", (0.5, 0.5, 0.5))
    red = flat("AlarmRed", (0.88, 0.16, 0.10))
    amber = flat("WarnAmber", (0.95, 0.64, 0.14))
    green = flat("OkGreen", (0.22, 0.72, 0.30))
    L, D = 1.8, 0.62
    # Main cabinet & sloped control desk
    b.box(-L / 2, L / 2, 0.0, D - 0.12, 0.0, 1.72, body)
    b.box(-L / 2, L / 2, D - 0.12, D, 0.0, 0.92, body)
    b.box(-L / 2 + 0.04, L / 2 - 0.04, D - 0.02, D + 0.01, 0.12, 0.18, toon("Hazard", (0.75, 0.58, 0.12)))
    # Upper dial meters (3 round ammeters/manometers)
    for x in (-0.55, 0.0, 0.55):
        b.cyl((x, D - 0.12, 1.42), (x, D - 0.08, 1.42), 0.11, dark, seg=14)
        b.cyl((x, D - 0.08, 1.42), (x, D - 0.07, 1.42), 0.09, flat("GaugeFace", (0.88, 0.86, 0.78)), seg=14)
        b.box(x - 0.01, x + 0.05, D - 0.068, D - 0.065, 1.42, 1.47, red)
    # Indicator lamps row (alarm red & amber glowing)
    for i, x in enumerate((-0.65, -0.39, -0.13, 0.13, 0.39, 0.65)):
        col = [red, amber, red, green, amber, red][i]
        b.cyl((x, D - 0.12, 1.15), (x, D - 0.08, 1.15), 0.032, col, seg=10)
    # Rotary rheostats & knife switches on the lower desk lip
    for x in (-0.6, -0.2, 0.2, 0.6):
        b.cyl((x, D - 0.04, 0.92), (x, D - 0.04, 0.97), 0.055, dark, seg=10)
        b.box(x - 0.08, x + 0.08, D - 0.10, D - 0.02, 0.97, 0.98, toon("Tape", (0.84, 0.80, 0.64)))
    return b.finish(), (L, D)


def temp_monitor(name):
    """Temperature monitoring equipment: strip-chart drum recorders & thermocouple CRT console."""
    b = Builder(name)
    body = toon("MonitorSteel", (0.35, 0.38, 0.39), noise=0.1)
    paper = flat("ChartPaper", (0.88, 0.86, 0.78))
    trace = flat("RedTrace", (0.78, 0.15, 0.12))
    case = toon("TermCase", (0.54, 0.52, 0.45), noise=0.08)
    L, D = 1.5, 0.65
    b.box(-L / 2, L / 2, 0.0, D, 0.0, 0.78, body)
    # Twin paper strip-chart recorders on left
    for x in (-0.46, -0.06):
        b.box(x - 0.16, x + 0.16, 0.08, 0.52, 0.78, 1.22, body)
        b.box(x - 0.13, x + 0.13, 0.52, 0.53, 0.83, 1.16, paper)
        for k in range(4):
            b.box(x - 0.10 + 0.02 * (k % 2), x + 0.08, 0.531, 0.534, 0.86 + k * 0.07, 0.875 + k * 0.07, trace)
    # Amber CRT thermocouple readout on right
    b.box(0.18, 0.66, 0.10, 0.50, 0.78, 1.20, case)
    b.box(0.23, 0.61, 0.50, 0.51, 0.83, 1.14, flat("AmberCRT", (0.28, 0.15, 0.04)))
    for k in range(3):
        b.box(0.26, 0.57, 0.511, 0.514, 0.89 + k * 0.07, 0.908 + k * 0.07, flat("AmberTrace", (0.96, 0.62, 0.16)))
    return b.finish(), (L, D)


# ---------------------------------------------------------------- props made in Tripo (image -> 3D), shaded like the rest
GLB_DIR = __import__("os").path.join(__import__("os").path.dirname(__file__), "props3d")
if not __import__("os").path.isdir(GLB_DIR):
    GLB_DIR = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", "..", "source", "props3d"))


def _toon_textured(mat, tint=None):
    """Painted texture from the model x the kit's toon bands (same key light as everything else).
    v2 also reads the model's glTF metal/roughness: metal is darker with a bright, tight highlight,
    smooth paint gets a soft one, rough rubber, fabric and wood get none."""
    nt = mat.node_tree
    tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image and "base" in n.image.name.lower()), None)
    tex = tex or next((n for n in nt.nodes if n.type == "TEX_IMAGE"), None)
    if tex is None:
        return
    mr_tex, metal_f, rough_f = None, 0.0, 1.0
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is not None:
        metal_f = bsdf.inputs["Metallic"].default_value; rough_f = bsdf.inputs["Roughness"].default_value

        def upstream_image(sock):
            for l_ in sock.links:
                n = l_.from_node
                if n.type == "TEX_IMAGE":
                    return n
                for i in n.inputs:
                    r = upstream_image(i)
                    if r:
                        return r
            return None
        mr_tex = upstream_image(bsdf.inputs["Metallic"]) or upstream_image(bsdf.inputs["Roughness"])
        if mr_tex is not None:
            metal_f, rough_f = 1.0, 1.0
    keep = {tex.name} | ({mr_tex.name} if (mr_tex is not None and LOOK == "v2") else set())
    for n in list(nt.nodes):
        if n.name not in keep:
            nt.nodes.remove(n)
    tex = nt.nodes[tex.name]
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    shading = _shade(nt, 1.06, 0.82, 0.6)
    hsv = nt.nodes.new("ShaderNodeHueSaturation")
    hsv.inputs["Saturation"].default_value = 1.0 if LOOK == "v2" else 0.85
    nt.links.new(tex.outputs["Color"], hsv.inputs["Color"])
    base = hsv.outputs["Color"]
    mul = nt.nodes.new("ShaderNodeVectorMath"); mul.operation = "MULTIPLY"
    if LOOK == "v2":
        # metal (B) and roughness (G) of the glTF map, or the material's constant factors
        if mr_tex is not None:
            mr = nt.nodes[mr_tex.name]
            mr.image.colorspace_settings.name = "Non-Color"
            sp = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(mr.outputs["Color"], sp.inputs[0])
            metal, rough = sp.outputs[2], sp.outputs[1]
        else:
            v1_ = nt.nodes.new("ShaderNodeValue"); v1_.outputs[0].default_value = metal_f
            v2_ = nt.nodes.new("ShaderNodeValue"); v2_.outputs[0].default_value = rough_f
            metal, rough = v1_.outputs[0], v2_.outputs[0]
        dark = nt.nodes.new("ShaderNodeMapRange"); dark.inputs[3].default_value = 1.0; dark.inputs[4].default_value = 0.68
        nt.links.new(metal, dark.inputs[0])                                      # metal: darker body colour
        bm = nt.nodes.new("ShaderNodeVectorMath"); bm.operation = "SCALE"
        nt.links.new(base, bm.inputs[0]); nt.links.new(dark.outputs[0], bm.inputs["Scale"]); base = bm.outputs[0]
    if LOOK == "v2" and tint:                    # per-asset paint correction (authored-grey machinery)
        tn = nt.nodes.new("ShaderNodeVectorMath"); tn.operation = "MULTIPLY"; tn.inputs[1].default_value = tint
        nt.links.new(base, tn.inputs[0]); base = tn.outputs[0]
    nt.links.new(base, mul.inputs[0]); nt.links.new(shading, mul.inputs[1])
    col = mul.outputs[0]
    if LOOK == "v2":
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        hd = nt.nodes.new("ShaderNodeVectorMath"); hd.operation = "DOT_PRODUCT"; hd.inputs[1].default_value = HALF
        nt.links.new(geo.outputs["Normal"], hd.inputs[0])
        band = nt.nodes.new("ShaderNodeMapRange"); band.interpolation_type = "SMOOTHSTEP"
        band.inputs[1].default_value = 0.76; band.inputs[2].default_value = 0.9
        nt.links.new(hd.outputs["Value"], band.inputs[0])
        gloss = nt.nodes.new("ShaderNodeMapRange"); gloss.inputs[1].default_value = 0.75; gloss.inputs[2].default_value = 0.25
        nt.links.new(rough, gloss.inputs[0])                                     # 0 when rough, 1 when smooth
        w = nt.nodes.new("ShaderNodeMath"); w.operation = "MULTIPLY_ADD"; w.inputs[1].default_value = 0.9; w.inputs[2].default_value = 0.18
        nt.links.new(metal, w.inputs[0])                                         # metal shines more than paint
        s1 = nt.nodes.new("ShaderNodeMath"); s1.operation = "MULTIPLY"
        nt.links.new(band.outputs[0], s1.inputs[0]); nt.links.new(gloss.outputs[0], s1.inputs[1])
        s2 = nt.nodes.new("ShaderNodeMath"); s2.operation = "MULTIPLY"
        nt.links.new(s1.outputs[0], s2.inputs[0]); nt.links.new(w.outputs[0], s2.inputs[1])
        hl = nt.nodes.new("ShaderNodeMix"); hl.data_type = "RGBA"
        nt.links.new(s2.outputs[0], hl.inputs["Factor"]); nt.links.new(col, hl.inputs[6])
        hl.inputs[7].default_value = (0.96, 0.93, 0.86, 1)
        col = hl.outputs[2]
    em = nt.nodes.new("ShaderNodeEmission"); nt.links.new(col, em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])


def glb_prop(name, file, L, D, rot=0.0, fit="x", H=None, outline=0.01, mirror=False, tint=None):
    """A Tripo model as a prop in the kit's frame: length L along x (centred), depth from y=0 back to
    y=D front, standing on z=0. rot (degrees about z) turns the model's front to +y; fit picks the
    axis the size comes from ("x" = length L, "z" = height H)."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=__import__("os").path.join(GLB_DIR, file))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    bpy.context.view_layer.update()
    bm = bmesh.new()
    mats = []
    for o in meshes:
        me = o.data.copy()
        me.transform(o.matrix_world)
        slot0 = len(mats)
        for m in o.data.materials:
            mats.append(m)
        tmp = bmesh.new(); tmp.from_mesh(me)
        for f in tmp.faces:
            f.material_index += slot0
        tmp.to_mesh(me); tmp.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(rot), 3, "Z"))
    if mirror:                                   # a mirrored copy for variety (ladder on the other end)
        for v in bm.verts:
            v.co.x = -v.co.x
        bmesh.ops.reverse_faces(bm, faces=bm.faces, flip_multires=False)
    xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]; zs = [v.co.z for v in bm.verts]
    s = (L / (max(xs) - min(xs))) if fit == "x" else (H / (max(zs) - min(zs)))
    sx = sy = sz = s
    if fit == "box":                             # stretch each axis: long tables and counters from one model
        sx, sy, sz = L / (max(xs) - min(xs)), D / (max(ys) - min(ys)), H / (max(zs) - min(zs))
    cx = (max(xs) + min(xs)) / 2
    for v in bm.verts:
        v.co = Vector(((v.co.x - cx) * sx, (v.co.y - min(ys)) * sy, (v.co.z - min(zs)) * sz))
    depth = (max(ys) - min(ys)) * sy
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in mats:
        _toon_textured(m, tint)
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    if outline:
        me.materials.append(ink())
        sol = ob.modifiers.new("Outline", "SOLIDIFY"); sol.thickness = -outline
        sol.use_flip_normals = True; sol.use_rim = False; sol.material_offset = len(mats)
    return ob, (L if fit in ("x", "box") else (max(xs) - min(xs)) * s, depth)

# ---------------------------------------------------------------- Junk Town modules (outdoor scavenger settlement)
# Built from stacked car bodies, corrugated sheets, scaffold poles and timber. All local frames:
# back at y=0, front +y, standing on z=0; the build pipeline places and sorts them.

def _junk_mats():
    return dict(
        rust=toon("JunkRust", (0.40, 0.23, 0.13), noise=0.22, noise_scale=9.0, metal=0.15),
        rust_dark=toon("JunkRustDark", (0.27, 0.15, 0.09), noise=0.3, noise_scale=14.0, metal=0.1),
        sheet=toon("JunkSheet", (0.36, 0.36, 0.34), noise=0.16, noise_scale=7.0, metal=0.25),
        blue=toon("JunkCarBlue", (0.24, 0.31, 0.35), noise=0.18, noise_scale=8.0, metal=0.2),
        red=toon("JunkCarRed", (0.38, 0.18, 0.14), noise=0.2, noise_scale=8.0, metal=0.2),
        cream=toon("JunkCarCream", (0.46, 0.43, 0.34), noise=0.18, noise_scale=8.0, metal=0.15),
        wood=toon("JunkWood", (0.30, 0.21, 0.13), noise=0.2, noise_scale=10.0),
        dark=toon("JunkDark", (0.16, 0.15, 0.14), noise=0.1),
        glass=toon("JunkGlass", (0.10, 0.13, 0.14), noise=0.05, metal=0.3),
        snow=toon("JunkSnow", (0.78, 0.82, 0.84), noise=0.08, noise_scale=4.0),
    )


def corrugated_fence(name, L=2.6, H=2.2):
    """A leaning panel of corrugated sheet on two timber posts, the gap-filler of the Junk Town wall."""
    b = Builder(name); m = _junk_mats()
    for x in (-L / 2, L / 2):
        b.box(x - 0.06, x + 0.06, 0.0, 0.12, 0, H, m["wood"])
        b.box(x - 0.09, x + 0.09, -0.02, 0.1, H - 0.06, H + 0.02, m["dark"])   # post cap
    for z in (0.25, H - 0.3):
        b.box(-L / 2, L / 2, 0.04, 0.08, z - 0.035, z + 0.035, m["wood"])
    n = max(8, int(L / 0.09))
    for i in range(n):
        x = -L / 2 + 0.12 + i * (L - 0.24) / n
        mat = m["sheet"] if i % 3 else m["rust"]
        y = 0.07 if i % 2 else 0.055
        b.box(x, x + 0.09, y, y + 0.022, 0.3, H - 0.18, mat)
    b.box(-L / 2 + 0.1, L / 2 - 0.1, 0.05, 0.08, H - 0.2, H - 0.14, m["snow"])
    return b.finish(), (L, 0.14)


def junk_watchtower(name, H=4.2):
    """Scaffold-and-car-parts watchtower with a ladder and a corrugated roof."""
    b = Builder(name); m = _junk_mats()
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.cyl((sx * 0.62, sy * 0.62, 0), (sx * 0.34, sy * 0.34, H), 0.045, m["dark"], seg=6)
    for z in (0.9, 1.9, 2.9):
        k = 1 - 0.18 * (z / H)
        for a, c in (((-1, -1), (1, -1)), ((-1, 1), (1, 1)), ((-1, -1), (-1, 1)), ((1, -1), (1, 1))):
            b.cyl((a[0] * 0.62 * k, a[1] * 0.62 * k, z), (c[0] * 0.62 * k, c[1] * 0.62 * k, z + 0.7), 0.022, m["rust"], seg=5)
    b.box(-1.05, 1.05, -1.05, 1.05, H - 0.14, H, m["wood"])                    # deck
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box(sx * 1.0 - 0.035, sx * 1.0 + 0.035, sy * 1.0 - 0.035, sy * 1.0 + 0.035, H, H + 0.95, m["dark"])
    for z in (H + 0.2, H + 0.6):
        b.box(-1.0, 1.0, -1.0, -0.97, z, z + 0.05, m["rust"])
        b.box(-1.0, -0.97, -1.0, 1.0, z, z + 0.05, m["rust"])
    b.box(-1.2, 1.2, -1.2, 1.2, H + 1.15, H + 1.23, m["sheet"])                 # roof
    b.box(-1.1, 1.1, -1.1, 1.1, H + 1.23, H + 1.28, m["snow"])
    # ladder up the front
    for x in (-0.26, 0.26):
        b.cyl((x, 1.08, 0), (x, 1.08, H + 0.95), 0.025, m["wood"], seg=5)
    for i in range(9):
        z = 0.45 + i * 0.45
        if z < H + 0.9:
            b.cyl((-0.28, 1.08, z), (0.28, 1.08, z), 0.02, m["wood"], seg=5)
    return b.finish(), (2.4, 2.4)


def junk_shack_old(name):
    """Superseded by junk_shack (patched panels)."""
    return None


def animal_pen(name):
    """Rail-and-plank goat pen with a trough and hay; the goats are separate so they can move."""
    b = Builder(name); m = _junk_mats()
    L, D = 4.2, 3.0
    for x in (-L / 2, 0.0, L / 2):
        b.box(x - 0.05, x + 0.05, 0, 0.1, 0, 1.05, m["wood"])
        b.box(x - 0.05, x + 0.05, D - 0.1, D, 0, 1.05, m["wood"])
    for z in (0.45, 0.85):
        b.box(-L / 2, L / 2, 0.02, 0.07, z, z + 0.06, m["rust"])
        b.box(-L / 2, L / 2, D - 0.07, D - 0.02, z, z + 0.06, m["rust"])
    for sy in (0.0, D):
        for x in (-L / 2, L / 2):
            b.box(x - 0.07, x + 0.07, sy - 0.05, sy + 0.05, 0, 1.1, m["wood"])
    b.box(-0.9, 0.9, D / 2 - 0.25, D / 2 + 0.25, 0.25, 0.45, m["wood"])          # trough
    b.box(-0.82, 0.82, D / 2 - 0.2, D / 2 + 0.2, 0.42, 0.43, m["dark"])
    for i in range(5):
        b.box(-0.9 + i * 0.38, -0.6 + i * 0.38, 0.55, 1.0, 0.0, 0.16, m["sheet"])  # hay
    b.box(-L / 2 + 0.3, -L / 2 + 0.9, 0.4, 1.1, 0.0, 0.35, m["rust"])            # feed bin
    return b.finish(), (L, D)


def goat_body(name):
    """The shaggy body and legs; the head is a separate sprite so it can graze."""
    b = Builder(name)
    fur = toon("GoatFur", (0.54, 0.49, 0.40), noise=0.22, noise_scale=12.0)
    dark = toon("GoatDark", (0.20, 0.18, 0.15), noise=0.15)
    ellipsoid(b, (0, 0.38, 0.56), (0.44, 0.24, 0.24), fur, seg=10)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.cyl((sx * 0.26, 0.38 + sy * 0.14, 0), (sx * 0.26, 0.38 + sy * 0.14, 0.38), 0.036, dark, seg=5)
    b.cyl((0, 0.16, 0.62), (0, 0.10, 0.74), 0.02, dark, seg=4)                   # tail
    return b.finish(), (0.95, 0.60)


def goat_head(name, pose=0):
    """Neck, head, horns and ears, pivoting at the neck. pose 0 = down grazing, 2 = up."""
    b = Builder(name)
    fur = toon("GoatFur", (0.54, 0.49, 0.40), noise=0.22, noise_scale=12.0)
    dark = toon("GoatDark", (0.20, 0.18, 0.15), noise=0.15)
    horn = toon("GoatHorn", (0.58, 0.53, 0.40), noise=0.1)
    pivot = Vector((0, 0.50, 0.66))
    pitch = {0: 38, 1: 22, 2: 6}.get(pose, 22)
    M = Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(pitch), 4, "X") @ Matrix.Translation(-pivot)
    def P(x, y, z):
        return M @ Vector((x, y, z))
    b.cyl(P(0, 0.52, 0.40), P(0, 0.55, 0.70), 0.095, fur, seg=7)                  # neck
    ellipsoid(b, P(0, 0.58, 0.76), (0.10, 0.15, 0.09), fur, seg=8)                # skull
    ellipsoid(b, P(0, 0.69, 0.73), (0.065, 0.12, 0.065), fur, seg=7)              # muzzle
    ellipsoid(b, P(0, 0.77, 0.71), (0.05, 0.055, 0.045), dark, seg=6)             # nose
    for sx in (-1, 1):
        ellipsoid(b, P(sx * 0.058, 0.655, 0.80), (0.016, 0.018, 0.018), dark, seg=5)  # eyes
    for sx in (-1, 1):
        b.cyl(P(sx * 0.075, 0.58, 0.83), P(sx * 0.16, 0.52, 0.95), 0.015, horn, seg=5)  # horns
        x0, x1 = sorted((sx * 0.075, sx * 0.18))
        b.box(x0, x1, 0.53, 0.57, 0.76, 0.80, dark, M=M)                          # ears
    return b.finish(), (0.42, 0.42)

# ---------------------------------------------------------------- wrecked cars (Junk Town ring wall)
# Soviet-era shapes so the wall reads as car bodies, not boxes: a long-bonnet saloon (Volga), a short
# saloon (Zhiguli), a bread-loaf van (UAZ-452) and a cab pickup. Built from side profiles extruded across
# the width (Builder.prism). Local frame: nose towards +x, centred on x=0 and y=0, wheels on z=0.

CAR_PAINTS = [(0.24, 0.31, 0.35), (0.38, 0.18, 0.14), (0.46, 0.43, 0.34), (0.27, 0.33, 0.25),
              (0.33, 0.30, 0.27), (0.40, 0.33, 0.18), (0.20, 0.24, 0.27), (0.42, 0.40, 0.37)]

CAR_KINDS = {
    #          length, width, body profile (x/L, z),                                      cabin (x/L at sill, x/L at roof, sill z, roof z)
    "volga":  (4.7, 1.80, [(-0.5, 0.30), (0.5, 0.30), (0.5, 0.66), (0.47, 0.78), (-0.48, 0.80), (-0.5, 0.70)],
               (-0.27, 0.17, -0.19, 0.06, 0.80, 1.44)),
    "zhiguli": (4.05, 1.62, [(-0.5, 0.30), (0.5, 0.30), (0.5, 0.64), (0.47, 0.76), (-0.49, 0.78), (-0.5, 0.68)],
                (-0.26, 0.19, -0.18, 0.08, 0.78, 1.40)),
    "van":    (4.4, 1.94, [(-0.5, 0.32), (0.5, 0.32), (0.5, 1.05), (0.43, 1.95), (-0.49, 2.02), (-0.5, 1.9)],
               None),
    "pickup": (4.6, 1.80, [(-0.5, 0.32), (0.5, 0.32), (0.5, 0.74), (0.47, 0.86), (-0.5, 0.88)],
               (-0.05, 0.27, -0.02, 0.18, 0.88, 1.62)),
}


def _prism(b, prof, y0, y1, mat, M):
    """Extrude a convex side profile [(x, z), ...] (anticlockwise seen from -y) between y0 and y1."""
    bm = b.bm
    a = [bm.verts.new(M @ Vector((x, y0, z))) for x, z in prof]
    c = [bm.verts.new(M @ Vector((x, y1, z))) for x, z in prof]
    idx = b.mi(mat)
    n = len(prof)
    bm.faces.new(a[::-1]).material_index = idx
    bm.faces.new(c).material_index = idx
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([a[i], a[j], c[j], c[i]]).material_index = idx


def junk_car(b, M, kind, paint, m, rng, snow=True, door_gone=False, wheels=True):
    """One wrecked car into Builder b at transform M. rng: random.Random for rust and damage."""
    L, W, prof, cab = CAR_KINDS[kind]
    body = [(x * L, z) for x, z in prof]
    _prism(b, body, -W / 2, W / 2, paint, M)
    top = max(z for _, z in prof)
    if cab:
        xs0, xs1, xr0, xr1, zs, zr = cab
        inset = 0.09
        glass = [(xs0 * L, zs), (xs1 * L, zs), (xr1 * L, zr - 0.06), (xr0 * L, zr - 0.06)]
        _prism(b, glass, -W / 2 + inset, W / 2 - inset, m["glass"], M)
        roof = [(xr0 * L - 0.03, zr - 0.07), (xr1 * L + 0.03, zr - 0.07), (xr1 * L, zr), (xr0 * L, zr)]
        _prism(b, roof, -W / 2 + inset - 0.01, W / 2 - inset + 0.01, paint, M)
        # pillars: A at the windscreen, C at the back, B in the middle
        for s0, s1 in ((xs1, xr1), (xs0, xr0), ((xs0 + xs1) / 2, (xr0 + xr1) / 2)):
            pl = [(s0 * L - 0.05, zs), (s0 * L + 0.05, zs), (s1 * L + 0.05, zr - 0.06), (s1 * L - 0.05, zr - 0.06)]
            _prism(b, pl, -W / 2 + inset - 0.012, W / 2 - inset + 0.012, paint, M)
        top = zr
        if kind == "pickup":                                        # load bed walls behind the cab
            for y0, y1 in ((-W / 2, -W / 2 + 0.06), (W / 2 - 0.06, W / 2)):
                b.box(-0.5 * L, xs0 * L, y0, y1, 0.88, 1.22, paint, M)
            b.box(-0.5 * L, -0.5 * L + 0.06, -W / 2, W / 2, 0.88, 1.22, paint, M)
            b.box(-0.5 * L + 0.06, xs0 * L, -W / 2 + 0.06, W / 2 - 0.06, 0.86, 0.9, m["rust"], M)
    else:                                                            # van: window band and windscreen
        for y in (-W / 2 - 0.005, W / 2 - 0.005):
            b.box(-0.30 * L, 0.36 * L, y, y + 0.01, 1.28, 1.68, m["glass"], M)
        ws = [(0.5 * L + 0.004, 1.12), (0.5 * L + 0.004, 1.12), (0.43 * L + 0.004, 1.86), (0.45 * L, 1.86)]
        b.box(0.452 * L, 0.5 * L + 0.01, -W / 2 + 0.12, W / 2 - 0.12, 1.15, 1.75, m["glass"],
              M @ Matrix.Translation((0.47 * L, 0, 1.45)) @ Matrix.Rotation(math.radians(-14), 4, "Y") @ Matrix.Translation((-0.47 * L, 0, -1.45)))
    # bumpers, lights, wheel arches and wheels
    for sx in (-1, 1):
        b.box(sx * L / 2 - 0.05, sx * L / 2 + 0.05, -W / 2 + 0.04, W / 2 - 0.04, 0.34, 0.46, m["rust"] if rng.random() < 0.6 else m["sheet"], M)
    for y in (-W / 2 + 0.28, W / 2 - 0.28):
        b.cyl(M @ Vector((L / 2 + 0.005, y, 0.6)), M @ Vector((L / 2 + 0.03, y, 0.6)), 0.075,
              m["dark"] if rng.random() < 0.5 else m["glass"], seg=8)
    axle = (L / 2 - 0.85, -L / 2 + 0.95)
    for ax_x in axle:
        for y in (-W / 2, W / 2):
            sgn = 1 if y > 0 else -1
            b.box(ax_x - 0.42, ax_x + 0.42, y - sgn * 0.01, y + sgn * 0.004, 0.30, 0.58, m["dark"], M)   # arch shadow
            if wheels and rng.random() < 0.85:
                b.cyl(M @ Vector((ax_x, y - sgn * 0.20, 0.30)), M @ Vector((ax_x, y + sgn * 0.02, 0.30)), 0.31, m["dark"], seg=10)
                b.cyl(M @ Vector((ax_x, y + sgn * 0.02, 0.30)), M @ Vector((ax_x, y + sgn * 0.03, 0.30)), 0.13, m["sheet"], seg=8)
    # rust: along the sills, round the arches and a few blooms, flush with the panel
    rr = m.get("rust_dark", m["rust"])
    for y in (-W / 2, W / 2):
        sgn = 1 if y > 0 else -1
        x0 = -0.5 * L + rng.uniform(0.0, 0.3)
        b.box(x0, x0 + rng.uniform(0.45, 0.95) * L, y - sgn * 0.002, y + sgn * 0.006, 0.31, 0.31 + rng.uniform(0.08, 0.16), rr, M)
        for ax_x in axle:
            if rng.random() < 0.6:
                b.box(ax_x - 0.5, ax_x + 0.5, y - sgn * 0.002, y + sgn * 0.007, 0.56, 0.63, rr, M)
        for _ in range(rng.randint(0, 2)):
            xb = rng.uniform(-0.4, 0.35) * L
            zb = rng.uniform(0.4, 0.62)
            b.box(xb, xb + rng.uniform(0.15, 0.4), y - sgn * 0.002, y + sgn * 0.006, zb, zb + rng.uniform(0.06, 0.14), rr, M)
        if door_gone and cab and y > 0:
            dx0 = (cab[0] + cab[1]) / 2 * L
            b.box(dx0, dx0 + 0.9, y - 0.004, y + 0.003, 0.36, min(0.95, top - 0.1), m["dark"], M)
    if snow:                                                         # drifts of snow on the roof and bonnet
        x_lo = (cab[2] * L + 0.12) if cab else -0.40 * L
        x_hi = (cab[3] * L - 0.12) if cab else 0.36 * L
        for _ in range(rng.randint(1, 2)):
            a0 = rng.uniform(x_lo, (x_lo + x_hi) / 2)
            a1 = min(x_hi, a0 + rng.uniform(0.35, 0.9))
            w0 = rng.uniform(0.25, 0.45)
            b.box(a0, a1, -W / 2 + w0, W / 2 - rng.uniform(0.25, 0.45), top, top + 0.035, m["snow"], M)
        if cab and kind != "pickup" and rng.random() < 0.6:
            a0 = rng.uniform(0.24, 0.32) * L
            b.box(a0, a0 + rng.uniform(0.25, 0.5), -W / 2 + 0.35, W / 2 - 0.4, 0.78, 0.81, m["snow"], M)
    return L, W, top


def junk_car_wall(name, L=6.0, tall=True, seed=0, gap_fill=True):
    """A run of wrecked cars nose-to-tail along x (back at y=0, front +y), slightly skewed and overlapping,
    with corrugated sheet and timber posts filling the gaps. tall: stack some cars two high and add a sheet
    course behind (far-side walls); tall=False keeps it to one car high so the camera can see over it."""
    import random
    rng = random.Random(seed * 7919 + int(L * 10))
    b = Builder(name); m = _junk_mats()
    paints = [toon(f"JunkCar{i}", c, noise=0.2, noise_scale=8.0, metal=0.2) for i, c in enumerate(CAR_PAINTS)]
    kinds = ["volga", "zhiguli", "van", "pickup", "zhiguli", "volga"]
    D = 1.8
    x = -L / 2
    k = rng.randrange(len(kinds))
    placed = []
    while x < L / 2 - 1.2:
        kind = kinds[k % len(kinds)]; k += 1 + rng.randrange(2)
        if not tall and kind == "van":
            kind = "zhiguli"
        Lc, Wc = CAR_KINDS[kind][0], CAR_KINDS[kind][1]
        Lc_eff = min(Lc, L / 2 - x + 0.3)
        cx = x + Lc / 2
        yaw = math.radians(rng.uniform(-6, 6))
        flip = rng.random() < 0.5
        M = (Matrix.Translation((cx, D / 2 + rng.uniform(-0.08, 0.08), -0.08)) @ Matrix.Rotation(yaw, 4, "Z")
             @ Matrix.Rotation(math.pi if flip else 0.0, 4, "Z") @ Matrix.Rotation(math.radians(rng.uniform(-2, 2)), 4, "X"))
        _, _, top = junk_car(b, M, kind, paints[rng.randrange(len(paints))], m, rng, door_gone=rng.random() < 0.35)
        placed.append((cx, Lc, top))
        if tall and kind != "van" and rng.random() < 0.28:          # a second car on the roof
            k2 = rng.choice(["zhiguli", "volga"])
            M2 = (Matrix.Translation((cx + rng.uniform(-0.3, 0.3), D / 2, top - 0.30)) @ Matrix.Rotation(math.radians(rng.uniform(-9, 9)), 4, "Z")
                  @ Matrix.Rotation(math.radians(rng.uniform(-4, 4)), 4, "Y"))
            junk_car(b, M2, k2, paints[rng.randrange(len(paints))], m, rng, snow=True, wheels=rng.random() < 0.5)
        x += Lc - rng.uniform(0.15, 0.4)
    if gap_fill:
        # timber posts between cars and corrugated sheet behind them (the outer face of the wall)
        H = 2.5 if tall else 1.35
        for cx, Lc, top in placed:
            for px in (cx - Lc / 2 + 0.05,):
                if -L / 2 - 0.1 < px < L / 2 + 0.1:
                    b.box(px - 0.07, px + 0.07, 0.05, 0.19, 0, H + rng.uniform(0.1, 0.4), m["wood"])
        if tall:
            n = int(L / 0.95) + 1
            for i in range(n):
                x0 = -L / 2 + i * L / n
                h = H - rng.uniform(0.0, 0.35)
                Ms = Matrix.Translation((x0, 0.04, 0)) @ Matrix.Rotation(math.radians(rng.uniform(-4, 4)), 4, "Y")
                b.box(0, L / n + 0.08, 0.0, 0.035, 0.0, h, m["sheet"] if rng.random() < 0.55 else m["rust"], Ms)
                b.box(0.02, L / n + 0.06, 0.035, 0.05, h - 0.06, h, m["snow"], Ms)
        else:                                                         # low wall: sheet only in the gaps
            for i in range(len(placed) - 1):
                gx = (placed[i][0] + placed[i][1] / 2 + placed[i + 1][0] - placed[i + 1][1] / 2) / 2
                b.box(gx - 0.35, gx + 0.35, D / 2 - 0.03, D / 2 + 0.03, 0.0, 1.25, m["sheet"] if i % 2 else m["rust"],
                      Matrix.Rotation(math.radians(rng.uniform(-8, 8)), 4, "Z"))
        if tall:                                                      # a raking strut every few metres
            for i in range(int(L / 2.4)):
                px = -L / 2 + 1.2 + i * 2.4
                b.cyl((px, -0.9, 0), (px, 0.02, H - 0.2), 0.05, m["wood"], seg=6)
    return b.finish(), (L, D)


def junk_gate(name, W=4.2, H=3.0):
    """Two corrugated truck-box leaves on a timber/steel frame, with hinges and a top rail."""
    b = Builder(name); m = _junk_mats()
    for x in (-W / 2, W / 2):
        b.box(x - 0.12, x + 0.12, 0.0, 0.28, 0, H + 0.55, m["wood"])
        b.box(x - 0.18, x + 0.18, -0.02, 0.3, H + 0.55, H + 0.68, m["dark"])
    b.box(-W / 2, W / 2, 0.0, 0.14, H + 0.38, H + 0.52, m["rust"])              # top rail
    for side in (-1, 1):
        x0 = side * 0.06
        x1 = side * (W / 2 - 0.18)
        xa, xb = sorted((x0, x1))
        b.box(xa, xb, 0.02, 0.10, 0.12, H, m["sheet"])                          # leaf
        # diagonal brace
        b.cyl((xa + 0.12, 0.12, 0.3), (xb - 0.12, 0.12, H - 0.3), 0.035, m["rust"], seg=5)
        for z in (0.55, H - 0.55):
            b.cyl((side * (W / 2 - 0.18), 0.12, z), (side * (W / 2 - 0.02), 0.12, z), 0.045, m["dark"], seg=6)
        b.box(xa, xb, 0.10, 0.14, H - 0.22, H - 0.12, m["snow"])
    b.box(-W / 2 + 0.1, W / 2 - 0.1, 0.14, 0.18, H + 0.2, H + 0.38, m["rust"])
    return b.finish(), (W + 0.4, 0.4)

def goat(name, pose=0):
    """A complete shaggy goat; pose 0 head down grazing, 1 half up, 2 up."""
    b = Builder(name)
    fur = toon("GoatFur", (0.54, 0.49, 0.40), noise=0.22, noise_scale=12.0)
    dark = toon("GoatDark", (0.20, 0.18, 0.15), noise=0.15)
    horn = toon("GoatHorn", (0.58, 0.53, 0.40), noise=0.1)
    ellipsoid(b, (0, 0.38, 0.56), (0.44, 0.24, 0.24), fur, seg=10)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.cyl((sx * 0.26, 0.38 + sy * 0.14, 0), (sx * 0.26, 0.38 + sy * 0.14, 0.38), 0.036, dark, seg=5)
    b.cyl((0, 0.16, 0.62), (0, 0.10, 0.74), 0.02, dark, seg=4)
    pivot = Vector((0, 0.50, 0.66))
    pitch = {0: 38, 1: 22, 2: 6}.get(pose, 22)
    M = Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(pitch), 4, "X") @ Matrix.Translation(-pivot)
    def P(x, y, z):
        return M @ Vector((x, y, z))
    b.cyl(P(0, 0.52, 0.40), P(0, 0.55, 0.70), 0.095, fur, seg=7)
    ellipsoid(b, P(0, 0.58, 0.76), (0.10, 0.15, 0.09), fur, seg=8)
    ellipsoid(b, P(0, 0.69, 0.73), (0.065, 0.12, 0.065), fur, seg=7)
    ellipsoid(b, P(0, 0.77, 0.71), (0.05, 0.055, 0.045), dark, seg=6)
    for sx in (-1, 1):
        ellipsoid(b, P(sx * 0.058, 0.655, 0.80), (0.016, 0.018, 0.018), dark, seg=5)
    for sx in (-1, 1):
        b.cyl(P(sx * 0.075, 0.58, 0.83), P(sx * 0.16, 0.52, 0.95), 0.015, horn, seg=5)
        x0, x1 = sorted((sx * 0.075, sx * 0.18))
        b.box(x0, x1, 0.53, 0.57, 0.76, 0.80, dark, M=M)
    return b.finish(), (0.95, 0.60)


# ---------------------------------------------------------------- Junk Town yard clutter
def oil_drum(name, k=0):
    """A 200-litre drum, painted then rusted; k picks the paint."""
    b = Builder(name); m = _junk_mats()
    paint = toon(f"Drum{k % 3}", [(0.24, 0.31, 0.35), (0.40, 0.33, 0.18), (0.27, 0.33, 0.25)][k % 3], noise=0.25, noise_scale=10.0, metal=0.2)
    b.cyl((0, 0.29, 0), (0, 0.29, 0.88), 0.29, paint, seg=14)
    for z in (0.29, 0.59):
        b.cyl((0, 0.29, z - 0.02), (0, 0.29, z + 0.02), 0.296, m["rust_dark"], seg=14)
    b.cyl((0, 0.29, 0.88), (0, 0.29, 0.9), 0.27, m["snow"], seg=12)
    return b.finish(), (0.58, 0.58)


def burn_barrel(name):
    """A drum with holes punched round it and a fire inside: where people stand and talk."""
    b = Builder(name); m = _junk_mats()
    fire = flat("BarrelFire", (1.0, 0.62, 0.22))
    b.cyl((0, 0.29, 0), (0, 0.29, 0.86), 0.29, m["rust"], seg=14)
    for k in range(6):
        a = 2 * math.pi * k / 6
        x, y = 0.292 * math.cos(a), 0.29 + 0.292 * math.sin(a)
        b.box(x - 0.04, x + 0.04, y - 0.04, y + 0.04, 0.22, 0.32, fire)
    b.cyl((0, 0.29, 0.8), (0, 0.29, 0.98), 0.21, fire, seg=10, r1=0.04)
    return b.finish(), (0.58, 0.58)


def tyre_stack(name, n=3):
    b = Builder(name); m = _junk_mats()
    for i in range(n):
        dx = 0.04 * ((i * 37) % 5 - 2)
        b.cyl((0.33 + dx, 0.33, i * 0.2), (0.33 + dx, 0.33, i * 0.2 + 0.19), 0.32, m["dark"], seg=14)
        b.cyl((0.33 + dx, 0.33, i * 0.2 + 0.19), (0.33 + dx, 0.33, i * 0.2 + 0.192), 0.16, m["glass"], seg=10)
    b.cyl((0.33, 0.33, n * 0.2), (0.33, 0.33, n * 0.2 + 0.02), 0.28, m["snow"], seg=10)
    return b.finish(), (0.66, 0.66)


def scrap_pile(name, seed=0):
    """A heap of panels, a door, pipe, a wheel and a car bonnet, half under snow."""
    import random
    rng = random.Random(seed)
    b = Builder(name); m = _junk_mats()
    mats = [m["sheet"], m["rust"], m["rust_dark"], m["dark"]]
    for i in range(9):
        cx, cy = rng.uniform(-0.8, 0.8), rng.uniform(0.3, 1.3)
        w, d = rng.uniform(0.4, 1.0), rng.uniform(0.3, 0.8)
        M = (Matrix.Translation((cx, cy, rng.uniform(0.0, 0.35))) @ Matrix.Rotation(rng.uniform(-0.6, 0.6), 4, "Z")
             @ Matrix.Rotation(rng.uniform(-0.5, 0.5), 4, "X"))
        b.box(-w / 2, w / 2, -d / 2, d / 2, 0, 0.04, rng.choice(mats), M)
    b.cyl((-0.9, 0.5, 0.15), (0.7, 1.2, 0.35), 0.06, m["rust"], seg=8)
    b.cyl((0.6, 0.6, 0.3), (0.6, 0.8, 0.3), 0.3, m["dark"], seg=10)
    ellipsoid(b, (0.0, 0.8, 0.0), (1.0, 0.65, 0.22), m["snow"], seg=10)
    return b.finish(), (2.0, 1.6)


def junk_gate_open(name, W=4.2, H=3.0):
    """The gate by day: two corrugated leaves swung back against the outside of the wall."""
    b = Builder(name); m = _junk_mats()
    for x in (-W / 2, W / 2):
        b.box(x - 0.14, x + 0.14, 0.0, 0.28, 0, H + 0.55, m["wood"])
        b.box(x - 0.2, x + 0.2, -0.02, 0.3, H + 0.55, H + 0.68, m["dark"])
    b.box(-W / 2, W / 2, 0.0, 0.14, H + 0.38, H + 0.52, m["rust"])              # top rail
    b.box(-W / 2 + 0.1, W / 2 - 0.1, 0.0, 0.14, H + 0.52, H + 0.58, m["snow"])
    for side in (-1, 1):                                                      # rails the leaves slide on, chains
        b.box(side * W / 2 - 0.1, side * W / 2 + 0.1, 0.05, 0.25, 0.0, 0.12, m["dark"])
        b.cyl((side * (W / 2 - 0.1), 0.3, H - 0.2), (side * (W / 2 - 0.1), 0.3, 1.0), 0.02, m["rust_dark"], seg=4)
    # a sign over the gate
    b.box(-1.0, 1.0, 0.14, 0.2, H + 0.62, H + 1.02, m["wood"])
    return b.finish(), (W + 0.4, 0.4)


def junk_shack(name, seed=0, L=3.0, D=2.4):
    """A shack patched from whatever the wall did not need: wall strips of sheet, rust, planks and car
    panels; a single-pitch corrugated roof with snow only in drifts; stovepipe; a warm window; a door."""
    import random
    rng = random.Random(seed * 131 + 7)
    b = Builder(name); m = _junk_mats()
    panels = [m["sheet"], m["rust"], m["wood"], m["rust_dark"],
              toon(f"ShackPaint{seed % 4}", CAR_PAINTS[(seed * 3) % len(CAR_PAINTS)], noise=0.22, noise_scale=8.0, metal=0.15)]
    glow = flat("ShackWindow", (0.95, 0.66, 0.30))
    H0, H1 = 2.15, 2.65                                     # front (+y) is low, back high: the roof sheds to the yard
    b.box(-L / 2, L / 2, 0, D, 0, 0.1, m["wood"])           # sill
    def strips(x0, x1, y0, y1, h0, h1, along_x=True):
        n = max(2, int((x1 - x0 if along_x else y1 - y0) / 0.55))
        for i in range(n):
            t0, t1 = i / n, (i + 1) / n
            h = h0 + (h1 - h0) * (t0 + t1) / 2
            mat = rng.choice(panels)
            if along_x:
                b.box(x0 + (x1 - x0) * t0, x0 + (x1 - x0) * t1 + 0.02, y0, y1, 0.1, h - rng.uniform(0, 0.12), mat)
            else:
                b.box(x0, x1, y0 + (y1 - y0) * t0, y0 + (y1 - y0) * t1 + 0.02, 0.1, h0 + (h1 - h0) * (1 - (t0 + t1) / 2) - rng.uniform(0, 0.1), mat)
    strips(-L / 2, L / 2, 0.0, 0.06, H1, H1)                # back wall (against the car wall)
    strips(-L / 2, -L / 2 + 0.06, 0.0, D, H0, H1, along_x=False)
    strips(L / 2 - 0.06, L / 2, 0.0, D, H0, H1, along_x=False)
    # front: door, window, the rest in strips
    dx = rng.uniform(-0.5, 0.3)
    strips(-L / 2, dx - 0.45, D - 0.06, D, H0, H0)
    strips(dx + 0.45, L / 2, D - 0.06, D, H0, H0)
    b.box(dx - 0.45, dx + 0.45, D - 0.06, D, 1.95, H0, m["sheet"])
    b.box(dx - 0.42, dx + 0.42, D - 0.03, D + 0.01, 0.1, 1.95, rng.choice([m["wood"], m["rust"]]))   # door
    b.box(dx + 0.24, dx + 0.32, D + 0.01, D + 0.04, 0.95, 1.02, m["dark"])
    wx = (dx + 0.45 + L / 2) / 2 if dx < 0 else (dx - 0.45 - L / 2) / 2
    b.box(wx - 0.3, wx + 0.3, D + 0.001, D + 0.012, 1.1, 1.5, glow)
    b.box(wx - 0.36, wx + 0.36, D + 0.01, D + 0.03, 1.04, 1.1, m["wood"])
    b.box(wx - 0.015, wx + 0.015, D + 0.01, D + 0.02, 1.1, 1.5, m["wood"])
    # roof: corrugated sheets, sloping to the front, overhanging; snow in a couple of drifts
    ang = math.atan2(H1 - H0, D)
    Mr = Matrix.Translation((0, 0, H1)) @ Matrix.Rotation(-ang, 4, "X")
    run = math.hypot(D, H1 - H0) + 0.35
    n = int((L + 0.4) / 0.6) + 1
    for i in range(n):
        x0 = -L / 2 - 0.2 + i * (L + 0.4) / n
        b.box(x0, x0 + (L + 0.4) / n + 0.03, -0.12, run, 0.0, 0.05, rng.choice([m["sheet"], m["rust"], m["rust"]]),
              Mr @ Matrix.Rotation(math.radians(rng.uniform(-1.5, 1.5)), 4, "Y"))
    for _ in range(2):
        s0 = rng.uniform(-L / 2, 0.2)
        b.box(s0, s0 + rng.uniform(0.7, 1.4), 0.0, rng.uniform(0.9, run - 0.3), 0.05, 0.1, m["snow"], Mr)
    for _ in range(rng.randint(2, 4)):                       # weights on the roof: tyres and stones
        tx, ty = rng.uniform(-L / 2 + 0.3, L / 2 - 0.3), rng.uniform(0.2, run - 0.4)
        p = Mr @ Vector((tx, ty, 0.05))
        b.cyl(p, p + Vector((0, 0, 0.12)), 0.18, m["dark"], seg=10)
    px = L / 2 - 0.5 if seed % 2 else -L / 2 + 0.5
    b.cyl((px, 0.5, 0.5), (px, 0.5, H1 + 0.9), 0.07, m["rust_dark"], seg=8)        # stovepipe
    b.cyl((px, 0.5, H1 + 0.9), (px, 0.5, H1 + 1.0), 0.11, m["dark"], seg=8)
    return b.finish(), (L, D)


def _scrap_mats():
    T = lambda n, t, sc=2.0, metal=0.2: toon(n, (1.0, 1.0, 1.0), tex=t, tex_scale=sc, metal=metal)
    return dict(
        galv=T("ScrapGalv", "corr_galv"), rust=T("ScrapRust", "corr_rust"), teal=T("ScrapTeal", "corr_teal"),
        blue=T("ScrapBlue", "corr_blue"), olive=T("ScrapOlive", "corr_olive"), red=T("ScrapRed", "corr_red"),
        cream=T("ScrapCream", "corr_cream"), yellow=T("ScrapYellow", "corr_yellow"),
        planks=T("ScrapPlanks", "planks_grey", 2.2, 0.0),
        roof=T("ScrapRoof", "corr_rust", 2.4), roof_g=T("ScrapRoofGalv", "corr_galv", 2.4, 0.3),
        frame=toon("ScrapFrame", (0.24, 0.16, 0.11), noise=0.3, noise_scale=12.0, metal=0.2),
        post=toon("ScrapPost", (0.27, 0.20, 0.14), noise=0.25, noise_scale=10.0),
        block=toon("ScrapBlock", (0.42, 0.41, 0.39), tex="concrete_wall", tex_scale=1.2),
        dark=toon("ScrapDark", (0.07, 0.07, 0.08), noise=0.05),
        tyre=toon("ScrapTyre", (0.09, 0.09, 0.10), noise=0.15, noise_scale=10.0),
        glow=flat("ScrapGlow", (0.98, 0.70, 0.34)), bulb=flat("ScrapBulb", (1.0, 0.86, 0.55)),
        snow=toon("ScrapSnow", (0.80, 0.83, 0.87), noise=0.08, noise_scale=4.0),
        canvas=toon("ScrapCanvas", (0.40, 0.37, 0.28), noise=0.22, noise_scale=8.0),
        green=toon("ScrapGreen", (0.20, 0.36, 0.24), noise=0.1),
        white=toon("ScrapWhite", (0.72, 0.71, 0.66), noise=0.12, noise_scale=8.0),
        car=toon("ScrapCarDoor", (0.24, 0.31, 0.35), noise=0.2, noise_scale=8.0, metal=0.3),
        glass=toon("ScrapGlass", (0.12, 0.15, 0.17), noise=0.05, metal=0.3),
        steel=toon("ScrapSteel", (0.36, 0.38, 0.37), noise=0.15, noise_scale=7.0, metal=0.4),
    )


SCRAP_PALETTES = {
    "mixed": ["galv", "rust", "teal", "blue", "olive", "red", "planks", "rust", "galv"],
    "cool": ["galv", "teal", "blue", "rust", "galv", "planks"],
    "warm": ["rust", "red", "olive", "planks", "galv", "rust"],
    "clinic": ["cream", "cream", "galv", "cream", "planks"],
    "bare": ["galv", "rust", "galv", "rust", "planks"],
}


def scrap_house(name, seed=0, L=4.4, D=4.0, H=2.7, pal="mixed", door=0.0, windows=(-1,), awning=0.0, tank=False,
                garage=False, cross=False, chimney=True, lean=False, porch=False, sign_board=None):
    """A Junk Town building patched together from corrugated sheet, car doors, planks and road signs: a
    timber/steel frame on a course of salvaged blocks, mismatched painted panels (two sheets high, lapped,
    some skewed), a single-pitch rusted roof weighed down with tyres, a stovepipe. Front is +y.
    door: x of the door (None = no door). windows: x positions on the front. awning: depth of a front
    lean-to (market counter, tea house). tank: a water cistern on a stand at the side. garage: a wide
    roll door instead of the door. cross: a painted cross plate (clinic). lean: a side lean-to with
    firewood. porch: duckboards and a step at the door. sign_board: (x, z, w, h) a blank board for lettering."""
    import random
    rng = random.Random(seed * 977 + 13)
    b = Builder(name); m = _scrap_mats()
    pals = [m[k] for k in SCRAP_PALETTES[pal]]
    Hb = H + 0.55                                            # back is higher: the roof sheds to the front
    t = 0.05
    # ---- footing: salvaged blocks and a sill
    for side in ((-L / 2, L / 2, -0.02, 0.22), (-L / 2, L / 2, D - 0.22, D + 0.02), (-L / 2, -L / 2 + 0.24, 0, D), (L / 2 - 0.24, L / 2, 0, D)):
        b.box(*side, 0.0, 0.26, m["block"])
    b.box(-L / 2 - 0.02, L / 2 + 0.02, -0.04, D + 0.04, 0.26, 0.32, m["frame"])
    def hz(y):                                               # wall top height at depth y (pitched roof line)
        return Hb + (H - Hb) * (y / D)
    # ---- panels: two courses, lapped, mismatched; each wall is a run of sheets
    def wall(axis, c, a0, a1, outward, skip=()):
        """axis 'x': wall along x at y=c; axis 'y': wall along y at x=c. outward: +1/-1 normal sign."""
        a = a0
        while a < a1 - 0.05:
            w = min(rng.uniform(0.75, 1.25), a1 - a)
            mid = a + w / 2
            if any(s0 < mid < s1 for s0, s1 in skip):
                a += w; continue
            top = hz(c if axis == "x" else mid) if axis == "x" else hz(mid)
            split = rng.uniform(1.15, 1.6)
            off = outward * rng.uniform(0.0, 0.035)
            for (z0, z1) in ((0.3, split + 0.08), (split, top + rng.uniform(-0.05, 0.02))):
                mat = rng.choice(pals)
                if axis == "x":
                    b.box(a - 0.03, a + w + 0.03, c + off - t / 2 + (0.012 if z0 > 0.5 else 0) * outward,
                          c + off + t / 2 + (0.012 if z0 > 0.5 else 0) * outward, z0, z1, mat)
                else:
                    b.box(c + off - t / 2, c + off + t / 2, a - 0.03, a + w + 0.03, z0, min(z1, hz(a + w) if z1 > split else z1), mat)
            if rng.random() < 0.35:                         # a skewed patch over the seam
                pw = rng.uniform(0.4, 0.8); pz = split + rng.uniform(-0.3, 0.2)
                Mt = Matrix.Rotation(math.radians(rng.uniform(-9, 9)), 4, "Y" if axis == "x" else "X")
                pm = rng.choice(pals)
                if axis == "x":
                    cc = Vector((mid, c + outward * 0.05, pz))
                    b.box(-pw / 2, pw / 2, -0.015, 0.015, -0.3, 0.3, pm, Matrix.Translation(cc) @ Mt)
                else:
                    cc = Vector((c + outward * 0.05, mid, pz))
                    b.box(-0.015, 0.015, -pw / 2, pw / 2, -0.3, 0.3, pm, Matrix.Translation(cc) @ Mt)
            a += w
    dx = door if door is not None else 99
    dw = 1.0 if not garage else 2.6
    win = [(x - 0.42, x + 0.42) for x in windows if x is not None]
    wall("x", 0.0, -L / 2, L / 2, -1)
    wall("y", -L / 2, 0.0, D, -1)
    wall("y", L / 2, 0.0, D, +1)
    front_skip = [(dx - dw / 2, dx + dw / 2)]
    wall("x", D, -L / 2, L / 2, +1, skip=front_skip)
    # ---- frame: corner posts, a top plate, lintel
    for (x, y) in ((-L / 2, 0), (L / 2, 0), (-L / 2, D), (L / 2, D)):
        b.box(x - 0.08, x + 0.08, y - 0.08, y + 0.08, 0.26, hz(y) + 0.04, m["post"])
    b.box(-L / 2 - 0.08, L / 2 + 0.08, D - 0.06, D + 0.1, H - 0.1, H + 0.02, m["post"])
    # ---- door
    if door is not None:
        if garage:
            b.box(dx - dw / 2, dx + dw / 2, D - 0.02, D + 0.02, 0.3, 2.45, m["dark"])
            for k in range(14):                              # roll-door slats
                z = 0.32 + k * 0.152
                b.box(dx - dw / 2 + 0.04, dx + dw / 2 - 0.04, D + 0.02, D + 0.05, z, z + 0.13, m["galv"] if k % 5 else m["rust"])
            b.box(dx - dw / 2 - 0.1, dx + dw / 2 + 0.1, D, D + 0.14, 2.45, 2.7, m["steel"])
            b.box(dx - dw / 2 - 0.12, dx - dw / 2, D, D + 0.12, 0.26, 2.7, m["steel"])
            b.box(dx + dw / 2, dx + dw / 2 + 0.12, D, D + 0.12, 0.26, 2.7, m["steel"])
        else:
            b.box(dx - 0.5, dx + 0.5, D - 0.03, D + 0.0, 0.3, 2.1, m["dark"])
            dm = rng.choice([m["planks"], m["planks"], m["red"], m["teal"]])
            b.box(dx - 0.46, dx + 0.46, D + 0.0, D + 0.05, 0.32, 2.06, dm)
            for z in (0.6, 1.75):                            # strap hinges / battens
                b.box(dx - 0.46, dx + 0.46, D + 0.05, D + 0.07, z, z + 0.08, m["frame"])
            b.box(dx + 0.3, dx + 0.38, D + 0.05, D + 0.1, 1.05, 1.15, m["steel"])
            b.box(dx - 0.56, dx + 0.56, D, D + 0.1, 2.1, 2.22, m["post"])
            b.box(dx - 0.56, dx - 0.46, D, D + 0.1, 0.3, 2.1, m["post"])
            b.box(dx + 0.46, dx + 0.56, D, D + 0.1, 0.3, 2.1, m["post"])
            b.cyl((dx, D + 0.05, 2.36), (dx, D + 0.3, 2.36), 0.025, m["steel"], seg=6)       # a bulb on a bracket
            ellipsoid(b, (dx, D + 0.32, 2.3), (0.07, 0.07, 0.09), m["bulb"], seg=8)
        if porch:
            for k in range(5):
                b.box(dx - 0.9, dx + 0.9, D + 0.1 + k * 0.17, D + 0.24 + k * 0.17, 0.0, 0.08, m["planks"])
            b.box(dx - 0.7, dx + 0.7, D + 0.02, D + 0.42, 0.08, 0.2, m["block"])
    # ---- windows: a warm pane behind rebar, a sill, maybe a shutter
    for (w0, w1) in win:
        z0, z1 = 1.05, 1.62
        b.box(w0, w1, D + 0.03, D + 0.035, z0, z1, m["glow"])
        b.box(w0 - 0.07, w1 + 0.07, D + 0.03, D + 0.08, z0 - 0.07, z0, m["post"])
        b.box(w0 - 0.07, w1 + 0.07, D + 0.03, D + 0.08, z1, z1 + 0.07, m["post"])
        for k in range(4):
            x = w0 + (w1 - w0) * (k + 0.5) / 4
            b.box(x - 0.012, x + 0.012, D + 0.05, D + 0.07, z0, z1, m["dark"])
        if rng.random() < 0.5:                               # a shutter made of a road sign, swung open
            b.box(w1 + 0.08, w1 + 0.5, D + 0.05, D + 0.09, z0 - 0.02, z1 + 0.02, rng.choice([m["yellow"], m["red"], m["planks"]]))
    # ---- a car door bolted into one side wall, window and all
    sx = L / 2 + 0.06 if seed % 2 else -L / 2 - 0.06
    cy = rng.uniform(0.9, D - 1.6)
    b.box(sx - 0.03, sx + 0.03, cy, cy + 1.05, 0.55, 1.45, m["car"])
    b.box(sx - 0.035, sx + 0.035, cy + 0.12, cy + 0.85, 1.05, 1.4, m["glass"])
    b.box(sx - 0.04, sx + 0.04, cy + 0.75, cy + 0.9, 0.95, 1.0, m["steel"])
    # ---- roof: rusted corrugated sheets laid down the slope, overhanging, with tyres to hold them
    ang = math.atan2(Hb - H, D)
    Mr = Matrix.Translation((0, -0.25, Hb + 0.05 + 0.25 * math.tan(ang))) @ Matrix.Rotation(-ang, 4, "X")
    run = math.hypot(D, Hb - H) + 0.25 + 0.45
    n = max(3, int((L + 0.6) / 0.9))
    for i in range(n):
        x0 = -L / 2 - 0.3 + i * (L + 0.6) / n
        tilt = Matrix.Rotation(math.radians(rng.uniform(-1.2, 1.2)), 4, "Y")
        b.box(x0 - 0.04, x0 + (L + 0.6) / n + 0.04, 0.0, run + rng.uniform(-0.1, 0.1), 0.0, 0.04,
              rng.choice([m["roof_g"], m["roof_g"], m["roof"], m["roof_g"], rng.choice(pals)]), Mr @ Matrix.Translation((0, 0, 0.012 * (i % 2))) @ tilt)
    b.box(-L / 2 - 0.3, L / 2 + 0.3, run - 0.06, run, -0.12, 0.02, m["frame"], Mr)          # fascia
    for _ in range(rng.randint(1, 3)):                       # a couple of tyres and a timber to hold the sheets down
        tx, ty = rng.uniform(-L / 2 + 0.4, L / 2 - 0.4), rng.uniform(0.5, run - 0.7)
        p = Mr @ Vector((tx, ty, 0.04))
        b.cyl(p, p + Vector((0, 0, 0.13)), 0.22, m["tyre"], seg=12)
        b.cyl(p + Vector((0, 0, 0.13)), p + Vector((0, 0, 0.135)), 0.11, m["dark"], seg=10)
    yb = rng.uniform(0.4, run - 0.5)
    b.box(-L / 2 - 0.1, L / 2 + 0.1, yb, yb + 0.1, 0.04, 0.12, m["post"], Mr)
    # ---- stovepipe
    if chimney:
        px = (L / 2 - 0.6) if seed % 3 else (-L / 2 + 0.6)
        b.cyl((px, 0.45, 0.3), (px, 0.45, Hb + 1.1), 0.09, m["frame"], seg=10)
        b.cyl((px, 0.45, Hb + 1.1), (px, 0.45, Hb + 1.16), 0.2, m["dark"], seg=10, r1=0.05)
        b.cyl((px, 0.45, Hb + 0.4), (px, -0.05, Hb + 0.2), 0.012, m["steel"], seg=4)
    # ---- extras
    if awning:
        ang2 = math.radians(14)
        Ma = Matrix.Translation((0, D, H - 0.05)) @ Matrix.Rotation(-ang2, 4, "X")
        for x in (-L / 2 + 0.2, L / 2 - 0.2):
            b.box(x - 0.06, x + 0.06, D + awning - 0.08, D + awning + 0.04, 0.0, H - 0.05 - awning * math.tan(ang2), m["post"])
        b.box(-L / 2 + 0.1, L / 2 - 0.1, D + awning - 0.1, D + awning, H - 0.25 - awning * math.tan(ang2), H - 0.15 - awning * math.tan(ang2), m["post"])
        k = max(2, int(L / 1.1))
        for i in range(k):
            x0 = -L / 2 + i * L / k
            b.box(x0, x0 + L / k + 0.04, 0.0, awning / math.cos(ang2) + 0.15, 0.0, 0.035,
                  rng.choice([m["canvas"], m["roof_g"], m["canvas"]]), Ma @ Matrix.Translation((0, 0, 0.01 * (i % 2))))
        cx0 = -L / 2 + 0.4 if door is None or dx > 0 else 0.2
        cx1 = cx0 + min(2.2, L - 1.6)
        b.box(cx0, cx1, D + awning - 0.75, D + awning - 0.3, 0.0, 0.95, m["planks"])          # counter
        b.box(cx0 - 0.05, cx1 + 0.05, D + awning - 0.8, D + awning - 0.25, 0.95, 1.0, m["steel"])
        for i in range(rng.randint(3, 6)):                   # goods on the counter
            gx = rng.uniform(cx0 + 0.1, cx1 - 0.2)
            b.box(gx, gx + rng.uniform(0.12, 0.3), D + awning - 0.7, D + awning - 0.45, 1.0, 1.0 + rng.uniform(0.08, 0.3),
                  rng.choice([m["olive"], m["red"], m["galv"], m["canvas"], m["teal"]]))
    if tank:
        tx = L / 2 + 0.95 if seed % 2 == 0 else -L / 2 - 0.95
        for (x, y) in ((tx - 0.6, 0.5), (tx + 0.6, 0.5), (tx - 0.6, 1.7), (tx + 0.6, 1.7)):
            b.box(x - 0.06, x + 0.06, y - 0.06, y + 0.06, 0.0, 1.5, m["frame"])
        b.box(tx - 0.75, tx + 0.75, 0.3, 1.9, 1.45, 1.55, m["planks"])
        b.cyl((tx, 1.1, 1.55), (tx, 1.1, 3.0), 0.72, m["galv"], seg=16)
        b.cyl((tx, 1.1, 3.0), (tx, 1.1, 3.05), 0.74, m["rust"], seg=16)
        b.cyl((tx + 0.5, 1.1 + 0.5, 1.7), (tx + 0.5, 1.1 + 0.5, 0.25), 0.03, m["steel"], seg=6)
        b.cyl((tx + 0.5, 1.6, 0.25), (tx + 0.5, 1.9, 0.25), 0.03, m["steel"], seg=6)
        b.cyl((tx + 0.5, 1.95, 0.0), (tx + 0.5, 1.95, 0.4), 0.2, m["steel"], seg=12)        # a bucket under the tap
    if cross:
        b.box(-0.5, 0.5, D + 0.06, D + 0.09, H - 1.0, H - 0.08, m["white"])
        b.box(-0.09, 0.09, D + 0.09, D + 0.1, H - 0.86, H - 0.22, m["green"])
        b.box(-0.32, 0.32, D + 0.09, D + 0.1, H - 0.63, H - 0.45, m["green"])
    if lean:
        lx = -L / 2 if seed % 2 else L / 2
        sg = -1 if seed % 2 else 1
        for y in (0.3, D - 0.3):
            b.box(lx + sg * 1.2 - 0.05, lx + sg * 1.2 + 0.05, y - 0.05, y + 0.05, 0.0, 1.55, m["post"])
        Ml = Matrix.Translation((lx, 0.0, 2.05)) @ Matrix.Rotation(sg * math.radians(-22), 4, "Y")
        b.box(min(0, sg * 1.5), max(0, sg * 1.5), 0.0, D, 0.0, 0.035, m["roof"], Ml)
        for k in range(6):                                   # split logs, stacked
            for j in range(3):
                y = 0.3 + j * (D - 0.6) / 3
                b.cyl((lx + sg * (0.15 + (k % 3) * 0.3), y, 0.12 + (k // 3) * 0.22),
                      (lx + sg * (0.15 + (k % 3) * 0.3), y + (D - 0.6) / 3 - 0.05, 0.12 + (k // 3) * 0.22), 0.11, m["post"], seg=7)
    if sign_board:
        x, z, w, h = sign_board
        b.box(x - w / 2, x + w / 2, D + 0.06, D + 0.1, z - h / 2, z + h / 2, m["planks"])
        b.box(x - w / 2 - 0.05, x + w / 2 + 0.05, D + 0.05, D + 0.07, z - h / 2 - 0.05, z + h / 2 + 0.05, m["frame"])
    ext = 0.0
    if tank: ext = 1.7
    if lean: ext = max(ext, 1.6)
    return b.finish(), (L, D)


def market_stall(name, seed=0):
    """A trading stall: four leaning poles, a ridged tarp sagging between them, a plank counter on two drums,
    goods laid out (jars, tins, a radio, boots), a coat hung on a nail, a lantern, and a chalked price board."""
    import random
    rng = random.Random(seed)
    b = Builder(name); m = _junk_mats()
    sm = _scrap_mats()                                          # tin sheets and one painted panel, like the houses
    tarp = sm["roof_g"]
    tarp2 = sm[["teal", "olive", "red", "blue"][seed % 4]]
    glow = flat("StallLantern", (1.0, 0.72, 0.36))
    L, D, H = 2.8, 1.6, 2.25
    for x in (-L / 2, L / 2):
        for y in (0.0, D):
            lean = rng.uniform(-0.06, 0.06)
            b.cyl((x, y, 0), (x + lean, y, H + (0.3 if y == 0 else 0.0)), 0.05, m["wood"], seg=6)
    # tarp: two sagging slopes from a ridge along x
    n = 6
    for i in range(n):
        x0, x1 = -L / 2 - 0.15 + i * (L + 0.3) / n, -L / 2 - 0.15 + (i + 1) * (L + 0.3) / n
        sag = 0.12 * math.sin(math.pi * (i + 0.5) / n)
        mat = tarp2 if (seed + i) % 4 == 1 else tarp
        b.quad([(x0, -0.15, H + 0.18 - sag), (x1, -0.15, H + 0.18 - sag), (x1, D * 0.45, H + 0.55 - sag), (x0, D * 0.45, H + 0.55 - sag)], mat)
        b.quad([(x0, D * 0.45, H + 0.55 - sag), (x1, D * 0.45, H + 0.55 - sag), (x1, D + 0.3, H - 0.05 - sag), (x0, D + 0.3, H - 0.05 - sag)], mat)
    b.box(-L / 2 - 0.1, L / 2 + 0.1, D + 0.24, D + 0.3, H - 0.32, H - 0.02, tarp)                  # front flap
    # counter of planks on two drums
    for x in (-L / 2 + 0.45, L / 2 - 0.45):
        b.cyl((x, D + 0.05, 0), (x, D + 0.05, 0.82), 0.22, m["rust"], seg=12)
    for k in range(3):
        b.box(-L / 2 + 0.15, L / 2 - 0.15, D - 0.25 + k * 0.17, D - 0.1 + k * 0.17, 0.82, 0.88, sm["planks"])
    # goods
    for i in range(rng.randint(6, 9)):
        x = rng.uniform(-L / 2 + 0.3, L / 2 - 0.3); y = rng.uniform(D - 0.2, D + 0.2)
        kind = rng.random()
        if kind < 0.4:
            b.cyl((x, y, 0.88), (x, y, 0.88 + rng.uniform(0.12, 0.2)), 0.05, m["glass"], seg=8)
        elif kind < 0.7:
            b.cyl((x, y, 0.88), (x, y, 0.98), 0.05, m["sheet"], seg=8)
        else:
            b.box(x - 0.12, x + 0.12, y - 0.08, y + 0.08, 0.88, 1.0, rng.choice([m["dark"], m["rust"], tarp]))
    # a coat hung on a nail, a lantern, a price board
    b.box(-L / 2 + 0.05, -L / 2 + 0.5, 0.05, 0.12, 1.0, 1.85, rng.choice([m["blue"], m["red"], m["cream"]]))
    b.cyl((0.3, D * 0.5, H + 0.4), (0.3, D * 0.5, H - 0.15), 0.008, m["dark"], seg=4)
    b.cyl((0.3, D * 0.5, H - 0.15), (0.3, D * 0.5, H - 0.38), 0.07, glow, seg=8)
    b.box(L / 2 - 0.7, L / 2 - 0.1, D + 0.3, D + 0.33, 1.05, 1.5, m["dark"])
    for k in range(3):
        b.box(L / 2 - 0.62, L / 2 - 0.25 - 0.08 * k, D + 0.33, D + 0.335, 1.38 - 0.11 * k, 1.41 - 0.11 * k, m["snow"])
    for x in (-L / 2 + 0.3, L / 2 - 0.9):                                                     # crates behind
        b.box(x, x + 0.6, 0.1, 0.65, 0, 0.5, m["wood"])
    return b.finish(), (L, D + 0.3)


def laundry_line(name, L=4.0, seed=0):
    """Two poles and a line of washing: shirts, a blanket, socks. Somebody here still does laundry."""
    import random
    rng = random.Random(seed)
    b = Builder(name); m = _junk_mats()
    cloth = [toon("Wash%d" % i, c, noise=0.15, noise_scale=8.0) for i, c in
             enumerate([(0.62, 0.60, 0.54), (0.30, 0.36, 0.44), (0.52, 0.24, 0.20), (0.40, 0.42, 0.30), (0.70, 0.68, 0.62)])]
    for x in (-L / 2, L / 2):
        b.cyl((x, 0.1, 0), (x, 0.1, 2.1), 0.04, m["wood"], seg=6)
    b.cyl((-L / 2, 0.1, 2.0), (L / 2, 0.1, 2.0), 0.008, m["dark"], seg=4)
    x = -L / 2 + 0.3
    while x < L / 2 - 0.4:
        w = rng.uniform(0.25, 0.7)
        sag = 0.12 * math.sin(math.pi * (x + L / 2) / L)
        b.box(x, x + w, 0.08, 0.12, 2.0 - sag - rng.uniform(0.35, 0.8), 2.0 - sag, rng.choice(cloth))
        x += w + rng.uniform(0.08, 0.25)
    return b.finish(), (L, 0.3)


def firewood(name):
    b = Builder(name); m = _junk_mats()
    for row in range(4):
        for i in range(6 - row):
            x = -0.75 + 0.13 * row + i * 0.26
            b.cyl((x, 0.0, 0.11 + row * 0.2), (x, 0.7, 0.11 + row * 0.2), 0.1, m["wood"], seg=7)
    b.box(-0.8, 0.8, -0.05, 0.75, 0.9, 0.93, _scrap_mats()["roof_g"])     # a sheet of tin keeps the snow off
    return b.finish(), (1.6, 0.7)


def yard_wreck(name, seed=0):
    """A car in the yard being stripped for the wall: on blocks, bonnet up, one door gone."""
    import random
    rng = random.Random(seed)
    b = Builder(name); m = _junk_mats()
    paint = toon(f"WreckPaint{seed % 4}", CAR_PAINTS[(seed * 5 + 1) % len(CAR_PAINTS)], noise=0.2, noise_scale=8.0, metal=0.2)
    M = Matrix.Translation((0, 0.95, 0.12))
    junk_car(b, M, "volga", paint, m, rng, door_gone=True, wheels=False)
    for x in (-1.4, 1.4):
        b.box(x - 0.25, x + 0.25, 0.4, 1.5, 0, 0.16, m["wood"])                   # blocks
    Mh = Matrix.Translation((2.05, 0.95, 0.92)) @ Matrix.Rotation(math.radians(-62), 4, "Y")
    b.box(-0.9, 0.0, -0.8, 0.8, 0.0, 0.04, paint, Mh)                              # bonnet up
    b.cyl((2.6, 2.1, 0.0), (2.6, 2.1, 0.22), 0.31, m["dark"], seg=10)              # a wheel lying by it
    return b.finish(), (4.8, 1.9)


# ---------------------------------------------------------------- the road to Junk Town (docs/LEVEL_ROAD_TO_JUNK_TOWN.md)
# Local frames as everywhere: back at y=0, front +y, standing on z=0, length along x (centred).

def _road_mats():
    return dict(
        concrete=toon("RdConcrete", (0.52, 0.52, 0.50), noise=0.22, noise_scale=5.0),
        concrete_d=toon("RdConcreteDark", (0.36, 0.36, 0.35), noise=0.2, noise_scale=6.0),
        steel=toon("RdSteel", (0.30, 0.33, 0.31), noise=0.16, noise_scale=7.0, metal=0.4),
        steel_l=toon("RdSteelLight", (0.48, 0.50, 0.49), noise=0.12, noise_scale=7.0, metal=0.4),
        rust=toon("RdRust", (0.40, 0.23, 0.13), noise=0.25, noise_scale=9.0, metal=0.15),
        rust_d=toon("RdRustDark", (0.25, 0.14, 0.09), noise=0.3, noise_scale=12.0),
        red=toon("RdRed", (0.48, 0.15, 0.11), noise=0.22, noise_scale=7.0, metal=0.2),
        olive=toon("RdOlive", (0.27, 0.29, 0.19), noise=0.18, noise_scale=7.0, metal=0.15),
        canvas=toon("RdCanvas", (0.36, 0.35, 0.26), noise=0.2, noise_scale=8.0),
        teal=toon("RdTeal", (0.18, 0.32, 0.33), noise=0.2, noise_scale=7.0, metal=0.2),
        wood=toon("RdWood", (0.30, 0.21, 0.13), noise=0.2, noise_scale=10.0),
        bark=toon("RdBark", (0.17, 0.14, 0.12), noise=0.25, noise_scale=14.0),
        dark=toon("RdDark", (0.08, 0.08, 0.09), noise=0.05),
        black=toon("RdBurnt", (0.10, 0.09, 0.08), noise=0.25, noise_scale=6.0),
        glass=toon("RdGlass", (0.12, 0.15, 0.17), noise=0.05, metal=0.3),
        snow=toon("RdSnow", (0.80, 0.83, 0.86), noise=0.08, noise_scale=4.0),
        sand=toon("RdSandbag", (0.42, 0.38, 0.27), noise=0.22, noise_scale=12.0),
        white=toon("RdWhite", (0.70, 0.69, 0.64), noise=0.15, noise_scale=8.0),
        yellow=toon("RdHazard", (0.62, 0.50, 0.16), noise=0.18, noise_scale=8.0),
        lamp=flat("RdDeadLamp", (0.20, 0.22, 0.20)),
    )


def silo_portal(name):
    """The Silo 81 surface portal: a concrete headwall in the hillside, one blast-door leaf open on the dark,
    wing walls running back into the slope, a dead lamp, snow on every ledge. Faces +y."""
    b = Builder(name); m = _road_mats()
    W, H, D = 9.0, 5.6, 1.4
    OW, OH = 4.2, 3.8
    b.box(-W / 2, -OW / 2, 0, D, 0, H, m["concrete"])                        # piers
    b.box(OW / 2, W / 2, 0, D, 0, H, m["concrete"])
    b.box(-OW / 2, OW / 2, 0, D, OH, H, m["concrete"])                       # lintel
    b.box(-W / 2 - 0.1, W / 2 + 0.1, 0.0, D + 0.15, H, H + 0.25, m["concrete_d"])   # coping
    b.box(-W / 2, W / 2, 0.1, D + 0.1, H + 0.25, H + 0.36, m["snow"])
    b.box(-OW / 2 - 0.25, OW / 2 + 0.25, D, D + 0.12, OH - 0.05, OH + 0.25, m["concrete_d"])   # door head
    b.box(-OW / 2, OW / 2, -2.5, 0.05, 0, OH, m["dark"])                       # the dark inside
    # blast doors: left leaf shut, right leaf swung in and jammed
    b.box(-OW / 2 + 0.05, 0.0, 0.25, 0.55, 0.0, OH - 0.05, m["steel"])
    for z in (0.6, 1.6, 2.6):
        b.box(-OW / 2 + 0.15, -0.1, 0.55, 0.6, z, z + 0.16, m["steel_l"])
    Ml = Matrix.Translation((OW / 2 - 0.05, 0.4, 0)) @ Matrix.Rotation(math.radians(-112), 4, "Z")
    b.box(0.0, OW / 2 - 0.05, -0.15, 0.15, 0.0, OH - 0.05, m["steel"], Ml)
    b.box(-0.65, 0.65, D + 0.01, D + 0.06, 1.2, 1.3, m["yellow"])                # chevron band at the threshold
    # wing walls stepping back into the slope
    for sgn in (-1, 1):
        x0 = sgn * W / 2
        for k in range(4):
            h = H - 0.9 * (k + 1)
            if h <= 0.4:
                break
            Mw = Matrix.Translation((x0, 0.0, 0)) @ Matrix.Rotation(math.radians(sgn * -32), 4, "Z")
            a0, a1 = sorted((sgn * (k * 1.3), sgn * ((k + 1) * 1.3)))
            b.box(a0, a1, 0.0, 0.6, 0, h, m["concrete_d"] if k % 2 else m["concrete"], Mw)
            b.box(a0, a1, 0.0, 0.6, h, h + 0.12, m["snow"], Mw)
    # dead lamp and a conduit
    b.box(-0.25, 0.25, D + 0.05, D + 0.35, OH + 0.55, OH + 0.75, m["steel"])
    b.box(-0.18, 0.18, D + 0.1, D + 0.32, OH + 0.47, OH + 0.55, m["lamp"])
    b.cyl((W / 2 - 0.7, D + 0.04, 0.3), (W / 2 - 0.7, D + 0.04, H - 0.2), 0.05, m["steel"], seg=6)
    # stains of meltwater under the coping
    for x in (-3.6, -2.9, 2.7, 3.5):
        b.box(x, x + 0.18, D + 0.002, D + 0.008, 1.0, H - 0.1, m["rust_d"])
    return b.finish(), (W, D)


def guard_shack(name):
    """A concrete guard post: flat roof under snow, a broken window, the door open, a stovepipe."""
    b = Builder(name); m = _road_mats()
    L, D, H = 3.0, 2.6, 2.7
    b.box(-L / 2, L / 2, 0, D, 0, H, m["concrete"], faces_mat={3: m["concrete"]})
    b.box(-L / 2 - 0.15, L / 2 + 0.15, -0.15, D + 0.2, H, H + 0.18, m["concrete_d"])
    b.box(-L / 2 - 0.1, L / 2 + 0.1, -0.1, D + 0.15, H + 0.18, H + 0.32, m["snow"])
    b.box(0.35, 1.2, D, D + 0.03, 0.0, 2.05, m["dark"])                        # doorway
    Md = Matrix.Translation((1.2, D, 0)) @ Matrix.Rotation(math.radians(70), 4, "Z")
    b.box(-0.85, 0.0, 0.0, 0.05, 0.02, 2.0, m["olive"], Md)
    b.box(-1.15, -0.25, D, D + 0.03, 1.1, 1.75, m["glass"])                    # window, one pane gone
    b.box(-1.2, -0.2, D + 0.02, D + 0.06, 1.05, 1.1, m["concrete_d"])
    b.box(-0.72, -0.68, D + 0.02, D + 0.05, 1.1, 1.75, m["steel"])
    b.cyl((-L / 2 + 0.4, 0.4, H), (-L / 2 + 0.4, 0.4, H + 0.8), 0.06, m["rust"], seg=7)
    b.box(-L / 2 + 0.1, -L / 2 + 0.9, D + 0.01, D + 0.03, 2.1, 2.45, m["white"])  # a notice, faded
    return b.finish(), (L, D)


def sandbag_nest(name):
    """A horseshoe of sandbags, three courses, open at the back, snow in the dips."""
    b = Builder(name); m = _road_mats()
    R = 1.5
    for row in range(3):
        n = 11 - row
        for k in range(n):
            a = math.radians(-200 + 220 * (k + 0.5 * (row % 2)) / (n - 1))
            c = Vector((R * math.cos(a), 1.5 + R * math.sin(a), 0.13 + row * 0.24))
            ellipsoid(b, c, (0.3, 0.17, 0.13), m["sand"], seg=8)
        if row == 2:
            for k in range(0, n, 2):
                a = math.radians(-200 + 220 * k / (n - 1))
                ellipsoid(b, Vector((R * math.cos(a), 1.5 + R * math.sin(a), 0.72)), (0.24, 0.13, 0.05), m["snow"], seg=6)
    return b.finish(), (3.4, 3.2)


def road_barrier(name, L=4.0):
    """Checkpoint boom: concrete blocks, a counterweight post and a striped boom snapped and hanging."""
    b = Builder(name); m = _road_mats()
    b.box(-L / 2 - 0.3, -L / 2 + 0.3, 0.0, 0.6, 0.0, 0.9, m["concrete"])
    b.box(-L / 2 - 0.3, -L / 2 + 0.3, 0.0, 0.6, 0.9, 0.98, m["snow"])
    b.box(-L / 2 - 0.08, -L / 2 + 0.08, 0.22, 0.38, 0.9, 1.25, m["steel"])
    for i in range(6):                                                 # boom: red and white bands
        x0 = -L / 2 + i * (L * 0.62) / 6
        b.box(x0, x0 + L * 0.62 / 6, 0.25, 0.35, 1.08, 1.18, m["red"] if i % 2 == 0 else m["white"])
    Mb = Matrix.Translation((-L / 2 + L * 0.62, 0.3, 1.13)) @ Matrix.Rotation(math.radians(-58), 4, "Y")
    for i in range(3):                                                 # the broken end hanging down
        b.box(i * 0.4, (i + 1) * 0.4, -0.05, 0.05, -0.05, 0.05, m["white"] if i % 2 == 0 else m["red"], Mb)
    b.box(L / 2 - 0.3, L / 2 + 0.3, 0.0, 0.6, 0.0, 0.9, m["concrete"])
    b.box(L / 2 - 0.3, L / 2 + 0.3, 0.0, 0.6, 0.9, 0.98, m["snow"])
    return b.finish(), (L + 0.6, 0.6)


def _lattice(b, m, H, base, top, mat, braces=7):
    """A four-legged steel lattice tower in the local frame (z up)."""
    legs = [(sx, sy) for sx in (-1, 1) for sy in (-1, 1)]
    for sx, sy in legs:
        b.cyl((sx * base, sy * base, 0), (sx * top, sy * top, H), 0.07, mat, seg=5)
    for k in range(braces):
        z0, z1 = H * k / braces, H * (k + 1) / braces
        w0 = base + (top - base) * k / braces
        w1 = base + (top - base) * (k + 1) / braces
        for (ax, ay), (bx, by) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
            b.cyl((ax * w0, ay * w0, z0), (bx * w1, by * w1, z1), 0.035, mat, seg=4)
            b.cyl((bx * w0, by * w0, z0), (ax * w1, ay * w1, z1), 0.035, mat, seg=4)


def power_pylon(name, lean=11.0):
    """A high-voltage pylon leaning over the road, cross-arms, insulators and dangling cable ends.
    The base stands at the origin; the whole tower tips towards +y by lean degrees."""
    b = Builder(name); m = _road_mats()
    H = 15.0
    sub = Builder(name + "_t")
    _lattice(sub, m, H, 1.6, 0.45, m["steel"])
    for z, w in ((H - 3.0, 4.2), (H - 0.8, 3.0)):
        sub.box(-w, w, -0.12, 0.12, z, z + 0.25, m["steel"])
        for x in (-w + 0.2, w - 0.2):
            sub.cyl((x, 0, z), (x, 0, z - 1.0), 0.09, m["white"], seg=6)
    sub.box(-0.5, 0.5, -0.5, 0.5, H, H + 0.6, m["steel"])
    me = bpy.data.meshes.new(name + "_tmp")
    sub.bm.to_mesh(me); sub.bm.free()
    # move it over: tip, then copy into the main builder
    M = Matrix.Rotation(math.radians(-lean), 4, "X")
    tmp = bmesh.new(); tmp.from_mesh(me)
    bmesh.ops.transform(tmp, matrix=M, verts=tmp.verts)
    offset = len(b.mats)
    for mt in sub.mats:
        b.mi(mt)
    for f in tmp.faces:
        f.material_index = b.mats.index(sub.mats[f.material_index])
    tmp.to_mesh(me); tmp.free()
    b.bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    for sx in (-1, 1):                                                  # concrete feet
        for sy in (-1, 1):
            b.box(sx * 1.6 - 0.35, sx * 1.6 + 0.35, sy * 1.6 - 0.35, sy * 1.6 + 0.35, 0, 0.4, m["concrete"])
    # cables hanging from the arms down to the snow
    tip = M @ Vector((4.0, 0, H - 3.2))
    for dx in (0.0, -8.0):
        p0 = M @ Vector((4.0 + dx, 0, H - 3.2))
        p1 = Vector((p0.x + 1.0, p0.y + 3.0, 0.05))
        b.cyl(p0, p1, 0.03, m["dark"], seg=4)
    return b.finish(), (4.2, 4.2)


def fallen_pylon(name, L=14.0):
    """A pylon down in the snow along x, broken in two, arms crumpled."""
    b = Builder(name); m = _road_mats()
    sub = Builder(name + "_t")
    _lattice(sub, m, L, 1.4, 0.5, m["rust"], braces=6)
    me = bpy.data.meshes.new(name + "_tmp"); sub.bm.to_mesh(me); sub.bm.free()
    tmp = bmesh.new(); tmp.from_mesh(me)
    M = (Matrix.Translation((-L / 2, 1.4, 1.25)) @ Matrix.Rotation(math.radians(90), 4, "Y")
         @ Matrix.Rotation(math.radians(45), 4, "Z"))                    # on its side, along x, one leg-pair down
    bmesh.ops.transform(tmp, matrix=M, verts=tmp.verts)
    for mt in sub.mats:
        b.mi(mt)
    for f in tmp.faces:
        f.material_index = b.mats.index(sub.mats[f.material_index])
    tmp.to_mesh(me); tmp.free(); b.bm.from_mesh(me); bpy.data.meshes.remove(me)
    for k, (y0, z0) in enumerate(((0.6, 0.15), (2.2, 0.35))):             # the cross-arm, twisted, in the snow
        b.cyl((L / 2 - 0.6, y0, z0), (L / 2 + 3.2, y0 + 0.9, 0.08), 0.07, m["rust"], seg=5)
    for t in range(5):
        x = L / 2 - 0.4 + t * 0.75
        b.cyl((x, 0.6 + t * 0.18, 0.12), (x + 0.4, 2.2 + t * 0.18, 0.3), 0.035, m["rust"], seg=4)
    return b.finish(), (L, 2.8)                  # (no snow lumps: the Godot ground and mounds carry the snow)


def box_trailer(name, cab_angle=48.0):
    """A red box trailer, jack-knifed: the cab folded back against it at cab_angle, tyres flat, snow on top."""
    b = Builder(name); m = _road_mats()
    L, W, H = 11.5, 2.5, 3.6
    b.box(-L / 2, L / 2, 0.0, W, 1.1, H, m["red"])
    for i in range(16):                                                # ribs
        x = -L / 2 + 0.3 + i * (L - 0.6) / 15
        b.box(x - 0.05, x + 0.05, -0.02, W + 0.02, 1.1, H, m["red"] if i % 3 else m["rust"])
    b.box(-L / 2 + 0.3, L / 2 - 0.3, 0.2, W - 0.2, H, H + 0.12, m["snow"])
    b.box(-L / 2, L / 2, 0.3, W - 0.3, 0.75, 1.1, m["dark"])                 # chassis
    for x in (-L / 2 + 0.9, -L / 2 + 2.1):
        for y in (0.15, W - 0.15):
            b.cyl((x, y - 0.25, 0.5), (x, y + 0.25, 0.5), 0.5, m["dark"], seg=12)
    b.box(-L / 2 + 0.2, -L / 2 + 0.25, 0.3, W - 0.3, 1.2, H - 0.2, m["steel"])   # rear doors
    for k, (x0, w, z0, h) in enumerate(((-4.9, 0.25, 1.4, 1.9), (-2.6, 0.18, 2.2, 1.3), (-0.4, 0.3, 1.2, 2.0), (1.8, 0.2, 1.7, 1.6),
                                         (3.9, 0.28, 1.3, 2.1), (-3.6, 1.6, 1.1, 0.25), (2.4, 2.2, 1.1, 0.3))):
        b.box(x0, x0 + w, W + 0.03, W + 0.045, z0, z0 + h, m["rust_d"] if k % 2 else m["rust"])   # streaks and a dirty skirt
    b.box(-L / 2 + 0.6, -L / 2 + 4.2, W + 0.03, W + 0.045, 2.6, 3.2, m["white"])      # what is left of the lettering
    # the cab, folded round on the fifth wheel
    Mc = Matrix.Translation((L / 2 - 0.6, W / 2, 0)) @ Matrix.Rotation(math.radians(cab_angle), 4, "Z")
    b.box(0.2, 2.1, -1.25, 1.25, 0.95, 3.1, m["olive"], Mc)                    # cab box
    b.box(2.1, 3.2, -1.15, 1.15, 0.95, 1.95, m["olive"], Mc)                   # bonnet
    b.quad([Mc @ Vector((2.1, -1.1, 1.95)), Mc @ Vector((2.1, 1.1, 1.95)), Mc @ Vector((2.1, 1.1, 3.0)), Mc @ Vector((2.1, -1.1, 3.0))], m["olive"])
    b.box(2.08, 2.14, -1.05, 1.05, 2.05, 2.9, m["glass"], Mc)                  # windscreen
    for y in (-1.26, 1.24):
        b.box(1.0, 1.9, y, y + 0.02, 2.0, 2.85, m["glass"], Mc)              # side windows
        b.box(2.0, 2.06, y * 1.12, y * 1.12 + 0.05, 2.2, 2.6, m["dark"], Mc)  # mirrors
        b.box(0.4, 1.0, y * 1.02, y * 1.02 + 0.04, 0.5, 0.62, m["steel"], Mc)  # step
    b.box(3.2, 3.24, -0.9, 0.9, 1.1, 1.8, m["dark"], Mc)                       # grille
    for k in range(6):
        b.box(3.24, 3.26, -0.85 + k * 0.32, -0.75 + k * 0.32, 1.15, 1.75, m["steel"], Mc)
    b.box(3.15, 3.4, -1.2, 1.2, 0.6, 0.85, m["steel_l"], Mc)                  # bumper
    for y in (-0.95, 0.95):
        b.cyl(Mc @ Vector((3.25, y, 1.3)), Mc @ Vector((3.32, y, 1.3)), 0.11, m["glass"], seg=8)
    b.box(0.2, 2.1, -1.2, 1.2, 3.1, 3.24, m["snow"], Mc)
    b.box(2.2, 3.1, -1.05, 1.05, 1.95, 2.02, m["snow"], Mc)
    for x0 in (0.4, 1.4):                                                      # rust round the wheel arch
        b.box(x0, x0 + 0.5, -1.26, -1.25, 0.95, 1.3, m["rust_d"], Mc)
    b.box(-1.8, 0.2, -1.1, 1.1, 0.7, 1.0, m["dark"], Mc)
    for x in (-1.2, 1.8):
        for y in (-1.15, 1.15):
            b.cyl(Mc @ Vector((x, y - 0.25, 0.5)), Mc @ Vector((x, y + 0.25, 0.5)), 0.5, m["dark"], seg=12)
    return b.finish(), (L, W)


def billboard(name, W=6.4, H=2.8, z=3.0):
    """Steel posts and a weathered board (the text is added by the level builder). Faces +y."""
    b = Builder(name); m = _road_mats()
    for x in (-W / 2 + 0.8, W / 2 - 0.8):
        b.box(x - 0.12, x + 0.12, 0.1, 0.34, 0.0, z + H * 0.8, m["steel"])
        b.box(x - 0.3, x + 0.3, 0.0, 0.45, 0.0, 0.35, m["concrete"])
    b.box(-W / 2, W / 2, 0.34, 0.42, z, z + H, m["steel_l"])
    b.box(-W / 2 + 0.06, W / 2 - 0.06, 0.42, 0.43, z + 0.06, z + H - 0.06, m["white"])
    b.box(-W / 2 + 0.06, W / 2 - 0.06, 0.43, 0.432, z + 0.06, z + 0.6, m["teal"])          # a painted stripe
    b.quad([(W / 2 - 1.6, 0.433, z + H - 0.06), (W / 2 - 0.06, 0.433, z + H - 0.06), (W / 2 - 0.06, 0.433, z + H - 1.0)], m["steel"])
    b.box(-W / 2, W / 2, 0.3, 0.46, z + H, z + H + 0.12, m["snow"])
    b.box(-W / 2 + 0.3, W / 2 - 0.3, 0.45, 0.9, z - 0.05, z + 0.02, m["steel"])               # catwalk
    return b.finish(), (W, 0.9)


def army_truck_side(name):
    """A GAZ-66-style army truck on its side: olive cab, canvas tilt torn off its hoops, wheels in the air."""
    b = Builder(name); m = _road_mats()
    M = Matrix.Translation((0, 0.0, 0.0)) @ Matrix.Rotation(math.radians(-88), 4, "X") @ Matrix.Translation((0, -1.25, 0))
    def bx(x0, x1, y0, y1, z0, z1, mat):
        b.box(x0, x1, y0, y1, z0, z1, mat, M)
    bx(-3.2, 3.2, -1.1, 1.1, 0.7, 1.05, m["dark"])                          # frame
    bx(1.2, 3.2, -1.2, 1.2, 1.05, 2.7, m["olive"])                           # cab
    bx(3.0, 3.22, -1.0, 1.0, 1.9, 2.55, m["glass"])
    bx(-3.4, 1.1, -1.25, 1.25, 1.05, 1.6, m["olive"])                        # bed
    for x in (-3.0, -1.8, -0.6, 0.6):                                        # hoops, canvas half gone
        b.cyl(M @ Vector((x, -1.2, 1.6)), M @ Vector((x, -1.2, 2.9)), 0.04, m["dark"], seg=4)
        b.cyl(M @ Vector((x, 1.2, 1.6)), M @ Vector((x, 1.2, 2.9)), 0.04, m["dark"], seg=4)
    bx(-3.4, -0.9, -1.3, 1.3, 2.9, 3.0, m["canvas"])
    for x in (-2.3, 2.2):
        for y in (-1.2, 1.2):
            b.cyl(M @ Vector((x, y - 0.25, 0.55)), M @ Vector((x, y + 0.25, 0.55)), 0.55, m["dark"], seg=12)
    for k in range(4):                                                      # spilled jerrycans
        b.box(-2.0 + k * 0.6, -1.6 + k * 0.6, 2.6 + 0.3 * (k % 2), 3.0 + 0.3 * (k % 2), 0.0, 0.45, m["olive"])
    ellipsoid(b, (0.0, 1.5, 0.0), (3.4, 1.0, 0.3), m["snow"], seg=10)
    return b.finish(), (6.8, 3.0)


def burned_bus(name):
    """A burned-out bus: black and rust shell, empty windows, sitting on its rims."""
    b = Builder(name); m = _road_mats()
    L, W, H = 10.5, 2.5, 3.0
    b.box(-L / 2, L / 2, 0.0, W, 0.35, 1.25, m["black"])
    for i in range(9):
        x = -L / 2 + 0.25 + i * (L - 0.5) / 9
        b.box(x, x + 0.18, 0.0, W, 1.25, H - 0.2, m["rust_d"] if i % 2 else m["black"])
        b.box(x + 0.18, x + (L - 0.5) / 9, 0.06, W - 0.06, 1.25, H - 0.2, m["dark"])     # window holes
    b.box(-L / 2, L / 2, 0.0, W, H - 0.2, H, m["rust"])
    b.box(-L / 2 + 0.6, L / 2 - 0.6, 0.3, W - 0.3, H, H + 0.1, m["snow"])
    for x in (-L / 2 + 2.0, L / 2 - 2.2):
        for y in (0.05, W - 0.05):
            b.cyl((x, y - 0.12, 0.35), (x, y + 0.12, 0.35), 0.35, m["rust_d"], seg=10)
    return b.finish(), (L, W)


def shipping_container(name, paint="red"):
    b = Builder(name); m = _road_mats()
    c = m.get(paint, m["red"])
    L, W, H = 6.0, 2.45, 2.6
    b.box(-L / 2, L / 2, 0.0, W, 0.0, H, c)
    for i in range(23):
        x = -L / 2 + 0.2 + i * (L - 0.4) / 22
        b.box(x - 0.04, x + 0.04, -0.03, W + 0.03, 0.15, H - 0.12, c if i % 4 else m["rust"])
    b.box(-L / 2, L / 2, -0.04, W + 0.04, H - 0.12, H, m["steel"])
    b.box(-L / 2, L / 2, -0.04, W + 0.04, 0.0, 0.15, m["steel"])
    b.box(L / 2, L / 2 + 0.04, 0.1, W - 0.1, 0.15, H - 0.15, m["steel"])
    b.box(-L / 2 + 0.2, L / 2 - 0.2, 0.2, W - 0.2, H, H + 0.1, m["snow"])
    return b.finish(), (L, W)


def guardrail(name, L=6.0, bent=0.0, seed=0):
    """Steel W-beam guardrail on posts; bent: how far (m) the middle is pushed out by an old crash."""
    b = Builder(name); m = _road_mats()
    n = int(L / 2.0) + 1
    pts = []
    for i in range(n):
        x = -L / 2 + i * L / (n - 1)
        y = 0.1 + bent * math.sin(math.pi * i / (n - 1)) ** 2
        pts.append((x, y))
        tilt = Matrix.Translation((x, y, 0)) @ Matrix.Rotation(math.radians(bent * 25 * math.sin(math.pi * i / (n - 1))), 4, "X")
        b.box(-0.06, 0.06, -0.06, 0.06, 0.0, 0.85, m["steel"], tilt)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        ang = math.atan2(y1 - y0, x1 - x0)
        Ms = Matrix.Translation((x0, y0, 0)) @ Matrix.Rotation(ang, 4, "Z")
        Lg = math.hypot(x1 - x0, y1 - y0)
        b.box(0, Lg, 0.06, 0.12, 0.5, 0.8, m["steel_l"], Ms)
        b.box(0, Lg, 0.06, 0.13, 0.8, 0.84, m["snow"], Ms)
    return b.finish(), (L, 0.4 + bent)


def dead_tree(name, seed=0, H=6.0):
    """A dead larch or birch: tapering trunk and a few bare branches (two levels)."""
    import random
    rng = random.Random(seed)
    b = Builder(name); m = _road_mats()
    top = Vector((rng.uniform(-0.3, 0.3), 0.3 + rng.uniform(-0.3, 0.3), H))
    base = Vector((0, 0.3, 0))
    b.cyl(base, top, 0.16, m["bark"], seg=7, r1=0.03)
    for k in range(rng.randint(5, 8)):
        t = rng.uniform(0.3, 0.85)
        p = base.lerp(top, t)
        a = rng.uniform(0, 2 * math.pi)
        Lb = (1.0 - t) * H * rng.uniform(0.35, 0.55)
        d = Vector((math.cos(a), math.sin(a), rng.uniform(0.2, 0.7))).normalized()
        q = p + d * Lb
        b.cyl(p, q, 0.06 * (1 - t) + 0.015, m["bark"], seg=5, r1=0.01)
        for _ in range(2):
            a2 = a + rng.uniform(-0.9, 0.9)
            d2 = Vector((math.cos(a2), math.sin(a2), rng.uniform(0.3, 0.9))).normalized()
            p2 = p.lerp(q, rng.uniform(0.4, 0.8))
            b.cyl(p2, p2 + d2 * Lb * 0.45, 0.012, m["bark"], seg=4, r1=0.004)
    return b.finish(), (0.8, 0.8)


def rest_kiosk(name):
    """The rest-stop kiosk: a low building with a shop window, door, a roof sign (text added by the
    builder) and a stovepipe."""
    b = Builder(name); m = _road_mats()
    L, D, H = 6.0, 4.0, 3.0
    b.box(-L / 2, L / 2, 0, D, 0, H, m["white"])
    b.box(-L / 2, L / 2, 0, D, 0, 0.6, m["concrete_d"])
    b.box(-L / 2 - 0.2, L / 2 + 0.2, -0.2, D + 0.3, H, H + 0.2, m["teal"])
    b.box(-L / 2 - 0.1, L / 2 + 0.1, -0.1, D + 0.2, H + 0.2, H + 0.32, m["snow"])
    b.box(-2.6, -0.3, D, D + 0.03, 0.8, 2.3, m["glass"])                        # shop window, dark
    for x in (-1.5,):
        b.box(x - 0.04, x + 0.04, D + 0.02, D + 0.05, 0.8, 2.3, m["steel"])
    b.box(0.6, 1.6, D, D + 0.03, 0.0, 2.15, m["dark"])                          # the door open
    Md = Matrix.Translation((1.6, D, 0)) @ Matrix.Rotation(math.radians(80), 4, "Z")
    b.box(-1.0, 0.0, 0.0, 0.05, 0.02, 2.1, m["teal"], Md)
    b.box(-1.8, 1.8, D * 0.5 - 0.06, D * 0.5 + 0.06, H + 0.32, H + 1.3, m["steel_l"])   # roof sign board
    b.cyl((L / 2 - 0.6, 0.6, H), (L / 2 - 0.6, 0.6, H + 1.2), 0.07, m["rust"], seg=7)
    return b.finish(), (L, D)


def fuel_pump(name, broken=False):
    b = Builder(name); m = _road_mats()
    M = Matrix.Rotation(math.radians(-20 if broken else 0), 4, "Y")
    b.box(-0.45, 0.45, 0.0, 0.7, 0.0, 0.25, m["concrete"])
    b.box(-0.3, 0.3, 0.1, 0.55, 0.25, 1.75, m["red"], M)
    b.box(-0.24, 0.24, 0.55, 0.57, 1.0, 1.5, m["glass"] if not broken else m["dark"], M)
    b.box(-0.32, 0.32, 0.08, 0.57, 1.75, 1.85, m["white"], M)
    b.cyl(M @ Vector((0.3, 0.45, 1.2)), Vector((0.55, 0.9, 0.05)), 0.025, m["dark"], seg=5)
    return b.finish(), (0.9, 0.7)


def grave_marker(name, seed=0):
    """A grave outside the wall: a cross of timber or exhaust pipe, a hubcap or number plate, a mound."""
    import random
    rng = random.Random(seed)
    b = Builder(name); m = _road_mats()
    ellipsoid(b, (0, 0.8, -0.02), (0.32, 0.7, 0.08), toon("GraveEarth", (0.27, 0.23, 0.20), noise=0.35, noise_scale=6.0), seg=10)
    mat = rng.choice([m["wood"], m["rust"], m["steel"]])
    tilt = Matrix.Rotation(math.radians(rng.uniform(-8, 8)), 4, "Y")
    b.box(-0.04, 0.04, 0.0, 0.08, 0.0, 1.1, mat, tilt)
    b.box(-0.3, 0.3, 0.0, 0.08, 0.72, 0.8, mat, tilt)
    if rng.random() < 0.5:
        b.cyl(tilt @ Vector((0, 0.09, 0.5)), tilt @ Vector((0, 0.12, 0.5)), 0.17, m["steel_l"], seg=12)
    else:
        b.box(-0.24, 0.24, 0.085, 0.1, 0.36, 0.5, m["yellow"], tilt)
    return b.finish(), (0.9, 1.9)


def notice_board(name):
    b = Builder(name); m = _road_mats()
    for x in (-0.8, 0.8):
        b.box(x - 0.06, x + 0.06, 0.0, 0.12, 0.0, 2.0, m["wood"])
    b.box(-0.95, 0.95, 0.1, 0.16, 0.9, 1.9, m["wood"])
    for k, (x, z, w, h) in enumerate(((-0.7, 1.25, 0.5, 0.55), (-0.05, 1.05, 0.45, 0.7), (0.5, 1.3, 0.35, 0.45))):
        b.box(x, x + w, 0.16, 0.17, z, z + h, m["white"])
    b.box(-1.0, 1.0, 0.0, 0.25, 1.9, 1.98, m["snow"])
    return b.finish(), (2.0, 0.3)
