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


def _ramp(nt, lit, mid, shade):
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    dot = nt.nodes.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = LIGHT
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.interpolation = "CONSTANT"
    e = ramp.color_ramp.elements
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
    ramp = _ramp(nt, lit, mid, shade)
    mul = nt.nodes.new("ShaderNodeVectorMath"); mul.operation = "MULTIPLY"
    nt.links.new(cur, mul.inputs[0]); nt.links.new(ramp.outputs["Color"], mul.inputs[1])
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


# ---------------------------------------------------------------- props made in Tripo (image -> 3D), shaded like the rest
GLB_DIR = __import__("os").path.join(__import__("os").path.dirname(__file__), "props3d")


def _toon_textured(mat):
    """Painted texture from the model x the kit's three toon bands (same key light as everything else)."""
    nt = mat.node_tree
    tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image and "base" in n.image.name.lower()), None)
    tex = tex or next((n for n in nt.nodes if n.type == "TEX_IMAGE"), None)
    if tex is None:
        return
    keep = tex.name
    for n in list(nt.nodes):
        if n.name != keep:
            nt.nodes.remove(n)
    tex = nt.nodes[keep]
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    ramp = _ramp(nt, 1.06, 0.82, 0.6)
    hsv = nt.nodes.new("ShaderNodeHueSaturation"); hsv.inputs["Saturation"].default_value = 0.85
    nt.links.new(tex.outputs["Color"], hsv.inputs["Color"])
    mul = nt.nodes.new("ShaderNodeVectorMath"); mul.operation = "MULTIPLY"
    nt.links.new(hsv.outputs["Color"], mul.inputs[0]); nt.links.new(ramp.outputs["Color"], mul.inputs[1])
    em = nt.nodes.new("ShaderNodeEmission"); nt.links.new(mul.outputs[0], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])


def glb_prop(name, file, L, D, rot=0.0, fit="x", H=None, outline=0.01, mirror=False):
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
        _toon_textured(m)
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    if outline:
        me.materials.append(ink())
        sol = ob.modifiers.new("Outline", "SOLIDIFY"); sol.thickness = -outline
        sol.use_flip_normals = True; sol.use_rim = False; sol.material_offset = len(mats)
    return ob, (L if fit in ("x", "box") else (max(xs) - min(xs)) * s, depth)
