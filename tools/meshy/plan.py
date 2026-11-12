"""The Meshy remake plan: every prop, wall detail, door and terrain piece, in batches of 10.

Images: Gemini (free) in the browser, one prop per message, 1:1. 3D: Meshy Image to 3D, Smart
Topology T2.5, texture Meshy 7 2K, Private (15 credits each). `poly` is the target face count.
Silo batches first; stop before credits run out. Walls and floors are textures (TEXTURES), not models.
Run `python3 tools/meshy/plan.py` to print the Gemini prompt for every item.
"""

SILO_STYLE = ("from a 1960s Eastern-bloc civilian Cold War fallout shelter, decades later, cold and slowly failing. "
              "Realistic weathered materials: chipped enamel and worn paint over steel, rust at edges and screw heads, "
              "grime, patched fabric, scuffed wood. Muted palette: faded olive, dark blue-grey, industrial teal, off-white, "
              "dull wood brown, rust orange. Not cartoonish, not glossy, not clean, not sci-fi")
ROAD_STYLE = ("on a frozen Eastern-bloc road decades after a Cold War catastrophe, 1960s-70s Soviet-style, abandoned in deep "
              "winter. Realistic and weathered: peeling paint, heavy rust, broken glass, a thin layer of snow only on "
              "upward-facing surfaces. Muted palette: rust orange, faded olive, dark blue-grey, dirty white, washed-out red. "
              "Not cartoonish, not glossy, not sci-fi")
TOWN_STYLE = ("from Junk Town, a survivor settlement in a frozen Eastern-bloc scrapyard decades after a Cold War catastrophe. "
              "Everything salvaged and patched: corrugated sheet in mismatched faded paints, car doors, planks, tyres, tarps, "
              "wire. Realistic, lived-in, a thin layer of snow only on upward-facing surfaces. Muted palette: rust orange, "
              "faded olive, dark blue-grey, washed-out red and green, raw timber brown. Not cartoonish, not medieval or fantasy")


def prompt(desc, style):
    return ("Generate an image: a single 3D game prop render, square 1:1, of " + desc + ", " + style + ". "
            "The object alone, centred, filling about 80% of the frame, three-quarter front view from slightly above, "
            "soft even studio light, on a plain flat light-grey background, no floor, no ground shadow, no text or "
            "lettering, no other objects.")


# (name, description, poly)
BATCHES = {
    "S1": [
        ("silo81_bunk_a", "a steel two-tier bunk bed with thin striped mattresses, badly folded grey wool blankets, a towel over the rail and a small bag tied to the ladder", 15000),
        ("silo81_bunk_b", "a steel two-tier bunk bed, lived in: a patched quilt hanging down the side, clothes on the rail, a tin mug and a book on the top mattress", 15000),
        ("silo81_bunk_stripped", "an abandoned steel two-tier bunk bed frame with bare sagging spring mesh, one rolled-up mattress and rust on the welds", 15000),
        ("silo81_bed_player", "a single steel-frame bed with a thin mattress, a hand-crocheted granny-square blanket in faded colours, a worn pillow and a small crate at its foot", 15000),
        ("silo81_locker", "a single tall steel locker with louvred vents, faded olive paint worn to bare metal round the handle, dents and a padlock", 10000),
        ("silo81_locker_double", "a double steel locker with two tall doors, louvred vents, faded olive paint, dents and rust", 10000),
        ("silo81_curtain", "a privacy partition: a grey army blanket pinned with clothes pegs to a sagging wire between two thin steel posts, heavy soft folds, frayed edges", 10000),
        ("silo81_chair", "a steel-tube canteen chair with a plywood seat and back, chipped paint", 10000),
        ("silo81_stool", "a round-seat steel stool with a worn wooden top", 8000),
        ("silo81_table", "a canteen table with steel legs and a scratched laminate top, a tin cup, an enamel bowl and a spoon on it", 10000),
    ],
    "S2": [
        ("silo81_bench", "a long wooden canteen bench on steel legs with worn planks", 8000),
        ("silo81_desk", "an office desk with a blue-grey steel body and drawers on the right, papers, a desk lamp, an ink stamp and a mug on top", 15000),
        ("silo81_schooldesk", "a two-seat school desk with attached bench, wood and steel, exercise books and pencils on top", 12000),
        ("silo81_counter", "a canteen serving counter with a stainless steel top, painted front panels, a stack of trays and a ladle", 12000),
        ("silo81_stove", "a large institutional cast-iron kitchen range with four hot plates, a dented stockpot, an oven door with a towel, soot stains", 15000),
        ("silo81_kitchen_shelf", "an open steel shelving unit stocked with tins, jars, enamel pots and sacks of flour", 15000),
        ("silo81_linen_shelf", "an open steel shelving unit with folded grey blankets, sheets and towels, some bundles tied with string", 15000),
        ("silo81_sinks", "a row of three ceramic washbasins on a steel frame, brass taps, exposed pipes underneath, cracked enamel, a bar of soap, a small tin mirror above each basin", 15000),
        ("silo81_toilet_stall", "a single toilet cubicle with painted steel partition walls, the door ajar, a squat-style ceramic toilet inside, chipped green paint", 12000),
        ("silo81_laundry", "a laundry corner: a galvanised washtub on a stand with a washboard and a wooden drying rack with grey clothes", 15000),
    ],
    "S3": [
        ("silo81_bucket", "a dented galvanised steel bucket with a rag over the rim", 5000),
        ("silo81_medcab", "a white enamel medical cabinet with glass doors, bottles and bandage rolls inside, a faded red cross", 10000),
        ("silo81_medscreen", "a three-leaf hospital folding screen with steel frames and faded stained off-white cloth panels", 10000),
        ("silo81_filing_cabinet", "a blue-grey steel filing cabinet with four drawers, one drawer half open with folders", 8000),
        ("silo81_file_shelf", "an open archive shelf with rows of card binders and boxed files", 15000),
        ("silo81_sacks", "a pile of hessian grain and potato sacks tied with twine, one split with potatoes spilling out", 12000),
        ("silo81_crate", "a wooden supply crate with plank sides and iron corners", 5000),
        ("silo81_safe", "a heavy steel safe with faded olive paint, a combination dial, a handle and scuffs", 8000),
        ("silo81_floorlamp", "a standing work lamp on a steel tripod with a caged bulb and a cable", 6000),
        ("silo81_toolbox", "a worn red-brown steel tool chest with drawers, wrenches and oil bottles on top", 10000),
    ],
    "S4": [
        ("silo81_pump", "an industrial water pump on a steel skid: cast-iron pump body painted industrial teal, flanged pipes, a pressure gauge, an electric motor, oil leaks", 20000),
        ("silo81_workbench", "a heavy workshop bench with a steel frame, a thick scarred wooden top, a vice, scattered tools and a pegboard of tools behind", 20000),
        ("silo81_lathe", "an old metal lathe with a cast-iron bed, chuck, tailstock, belt guard and swarf on the tray, blue-grey machine paint", 20000),
        ("silo81_boiler", "a massive horizontal heating boiler and heat exchanger drum with insulated pipe headers, a glowing orange inspection port, a cracked cast-iron pressure regulator with welded shims, gauges, valve wheels and a hazard-yellow guard rail", 30000),
        ("silo81_control_panel", "an industrial heating control switchboard console in dark blue-grey steel with analogue dials, big rotary switches, indicator lamps and a logbook on the ledge", 20000),
        ("silo81_temp_monitor", "a temperature monitoring station with strip-chart drum recorders, a small green CRT screen, thermocouple switches and cables", 20000),
        ("silo81_monitors", "a telemetry and intercom desk with three small CRT monitors, an intercom handset, switches and papers", 20000),
        ("silo81_terminal", "a computer desk with a 1970s green-screen terminal and a dot-matrix printer with fanfold paper", 15000),
        ("silo81_radioset", "a radio station: a tall valve radio cabinet with dials and a tuning window, beside a bench with headphones and a morse key", 20000),
        ("silo81_maptable", "a planning table with a large paper map of a region pinned flat, pencils, a ruler, a compass and an ashtray", 12000),
    ],
    "S5": [  # doors (leaf and frame apart, so the game can show them open) and wall details
        ("silo81_steel_door_leaf", "a single heavy steel door leaf on its own, riveted, faded olive paint, a lever handle, rust at the bottom edge, seen straight from the front", 8000),
        ("silo81_steel_door_frame", "an empty steel door frame on its own with thick riveted jambs and a lintel, no door in it, chipped grey paint", 8000),
        ("silo81_plywood_door_leaf", "a single plywood door leaf on its own, painted pale green, worn round the knob, a hand-written paper sign pinned on it (blank)", 6000),
        ("silo81_plywood_door_frame", "an empty wooden door frame on its own, painted, chipped, no door in it", 6000),
        ("silo81_blast_door", "a sealed round-cornered steel bulkhead door set in a thick frame, wheel lock in the middle, hazard-yellow stripes worn on the frame", 15000),
        ("silo81_radiator", "a cast-iron column radiator on wall brackets, fed from pipes below, chipped cream paint", 10000),
        ("silo81_pipe_run", "a straight 2-metre run of three parallel insulated pipes on wall brackets with flanges and a valve wheel", 10000),
        ("silo81_manifold", "a wall-mounted steam manifold: a horizontal header pipe with five valve wheels and branch pipes going down", 15000),
        ("silo81_gauge_bank", "a wall-mounted panel of six round pressure gauges with brass bezels on a steel board", 10000),
        ("silo81_steam_vent", "a wall-mounted steam relief vent pipe with a bent outlet, frost and rust around it", 6000),
    ],
    "S6": [
        ("silo81_switchboard", "a wall-mounted electrical switchboard cabinet with big knife switches, fuses and a door hanging open", 12000),
        ("silo81_intercom", "a wall-mounted Cold War intercom box with a speaker grille, a handset on a hook and a call button", 5000),
        ("silo81_noticeboard", "a wall cork noticeboard in a wooden frame with pinned blank papers and ration cards", 6000),
        ("silo81_blackboard", "a wall blackboard in a wooden frame with a chalk ledge and a sponge, faint chalk smudges, no writing", 5000),
        ("silo81_toolboard", "a wall pegboard full of hanging tools: wrenches, hammers, saws, pliers", 15000),
        ("silo81_tvscreen", "a wall-mounted 1960s television set in a steel cage bracket, dark screen", 8000),
        ("silo81_wall_lamp", "a caged industrial wall lamp with a heavy glass globe on a steel bracket", 5000),
        ("silo81_fuse_box", "a small grey wall fuse box with conduit pipes going up and down", 5000),
        ("silo81_vent_grille", "a square wall ventilation grille with louvres and a rusty frame, dust streaks", 4000),
        ("silo81_floor_drain", "a round cast-iron floor drain grate set in a square concrete slab", 3000),
    ],
    # ---- outdoor (after the silo; pause before credits run out)
    "R1": [
        ("road_silo_portal", "a shelter entrance in a hillside: a reinforced concrete headwall with short wing walls, a huge round steel blast door leaf jammed half open on darkness, a dead caged lamp above, snow on every ledge", 30000),
        ("road_guard_shack", "a small concrete guard post with a flat snowy roof, a broken window, the door open, a stovepipe", 15000),
        ("road_sandbag_nest", "a horseshoe of sandbags three courses high, open at the back", 12000),
        ("road_barrier", "a checkpoint boom: concrete blocks, a counterweight post and a red-white striped boom snapped and hanging", 10000),
        ("road_power_pylon", "a tall high-voltage steel lattice pylon with cross-arms, glass insulators and cut cable ends dangling", 30000),
        ("road_fallen_pylon", "a steel lattice pylon lying on its side broken in two, arms crumpled", 30000),
        ("road_box_trailer", "an articulated Soviet truck: a red box trailer jack-knifed with its cab folded back against it, flat tyres", 25000),
        ("road_billboard", "a roadside billboard on two steel posts with a weathered blank board, peeling paper strips and rust streaks", 10000),
        ("road_army_truck", "a GAZ-66-style Soviet army truck lying on its side, olive cab, canvas tilt torn off its hoops, wheels in the air", 25000),
        ("road_burned_bus", "a burned-out 1970s Soviet city bus, black and rust shell, empty windows, sitting on its rims", 25000),
    ],
    "R2": [
        ("road_container", "a 20 ft shipping container, faded blue-grey, dented and rusted, one door ajar", 10000),
        ("road_guardrail", "a steel W-beam guardrail section on four posts, bent outward in the middle by an old crash", 8000),
        ("road_dead_larch", "a dead larch tree with grey bark and a few bare branches", 12000),
        ("road_dead_birch", "a dead birch tree with peeling white bark and a broken top", 12000),
        ("road_rest_kiosk", "a small roadside rest-stop kiosk: a low brick-and-concrete building, a shop window, a door, a blank roof sign board, a stovepipe", 20000),
        ("road_fuel_pump", "an old Soviet petrol pump with a rounded steel cabinet, a mechanical counter dial and a hanging hose", 8000),
        ("road_grave", "a roadside grave: a cross of welded exhaust pipe with a hubcap hung on it over a low mound of frozen earth", 8000),
        ("road_notice_board", "an evacuation notice board on two timber posts with a small roof and torn blank paper notices", 8000),
        ("terrain_rock_a", "a large weathered grey granite rock outcrop with snow on top", 10000),
        ("terrain_rock_b", "a cluster of three frost-cracked boulders half buried, snow in the cracks", 10000),
    ],
    "R3": [
        ("terrain_snowdrift_a", "a long wind-sculpted snowdrift with a sharp crest", 6000),
        ("terrain_snowdrift_b", "a low rounded snow mound with a few frozen grass tufts poking through", 6000),
        ("terrain_snowbank", "a ploughed roadside snowbank, dirty grey snow with gravel and ice chunks", 8000),
        ("terrain_shrub_a", "a frozen leafless shrub with icy twigs", 8000),
        ("terrain_shrub_b", "a small snow-covered dwarf spruce", 10000),
        ("terrain_concrete_rubble", "a pile of broken concrete slabs with bent rebar, snow in the gaps", 12000),
        ("terrain_hill_cut", "a rocky snow-covered hillside slope with a flat cut face where a road was dug into it", 20000),
        ("terrain_ice_puddle", "a frozen puddle of dark cracked ice in a shallow dip", 3000),
        ("terrain_frozen_reeds", "a clump of frozen dry reeds and grass sticking out of snow", 8000),
        ("terrain_tyre_ruts", "a short stretch of deep frozen tyre ruts in snow and mud", 8000),
    ],
    "J1": [
        ("jt_scrap_house_a", "a one-room scrap house: timber frame on salvaged concrete blocks, corrugated sheet walls in mismatched paints, a single-pitch rusted roof weighed down with tyres, a smoking stovepipe, a car door as the front door", 25000),
        ("jt_scrap_house_b", "a scrap house with a lean-to, plank and sheet walls, a small scratched plexiglass window, a tarp awning over the door", 25000),
        ("jt_scrap_house_c", "a scrap house with a rusted water tank on stilts beside it, a pipe into the wall, road-sign panels in the walls", 25000),
        ("jt_scrap_house_d", "a garage workshop shack with wide sheet-metal double doors, a hoist beam and oil drums by the wall", 25000),
        ("jt_van_a", "a Soviet UAZ-452 van without wheels, propped on timber, faded green paint, windows boarded", 20000),
        ("jt_van_b", "a Soviet UAZ-452 van turned into a shelter with a tarp roof extension and a stovepipe through the roof", 20000),
        ("jt_van_ladder", "a Soviet UAZ-452 van propped on timber with a ladder up to a sandbagged lookout on its roof", 20000),
        ("jt_car", "a rusted Lada Zhiguli sedan with no wheels, on blocks, cracked windows", 15000),
        ("jt_plank_fence", "a wall panel of nailed salvaged planks and sheet metal on posts, leaning and braced", 10000),
        ("jt_chainlink", "a bent chain-link fence panel on steel posts with barbed wire on top and tins tied on as alarms", 15000),
    ],
    "J2": [
        ("jt_watchtower", "a scaffold watchtower with a car-door parapet, a ladder, a corrugated roof and a searchlight", 25000),
        ("jt_gate_open", "a settlement gate standing open: two corrugated-sheet leaves on welded pipe frames swung back, a chain and padlock hanging", 15000),
        ("jt_market_stall", "a trading stall: four leaning poles, a sagging ridged tarp, a plank counter on two drums with jars, tins, boots, a radio and a lantern, a blank chalkboard", 25000),
        ("jt_laundry_line", "two poles with a line of washing: shirts, a blanket and socks", 12000),
        ("jt_firewood", "a stack of split firewood under a small sheet-metal roof with an axe in a chopping block", 12000),
        ("jt_oil_drum", "a 200-litre steel drum with faded blue paint and heavy rust", 5000),
        ("jt_burn_barrel", "a steel drum with holes punched round it and a fire burning inside, soot, glowing holes", 8000),
        ("jt_tyre_stack", "a stack of four old car and truck tyres", 8000),
        ("jt_scrap_pile", "a heap of scrap half under snow: sheet panels, a car door, pipes, a wheel and a car bonnet", 15000),
        ("jt_animal_pen", "an empty goat pen of rails and planks with a wooden trough, a pile of hay and a small lean-to in one corner", 20000),
    ],
    "J3": [
        ("jt_yard_wreck", "a car on blocks being stripped for parts, bonnet open, its engine out on a pallet beside it", 20000),
        ("jt_corrugated_fence", "a leaning panel of corrugated sheet on two timber posts", 6000),
        ("jt_scrap_door", "a door made from a riveted car bonnet on strap hinges in a timber frame", 8000),
        ("jt_lantern_post", "a timber post with a hanging kerosene lantern and a coil of wire", 6000),
        ("jt_water_barrel", "a wooden water barrel with iron hoops, ice on the top, a tin ladle", 6000),
    ],
}
STYLE_OF = {k: (SILO_STYLE if k.startswith("S") else ROAD_STYLE if k.startswith("R") else TOWN_STYLE) for k in BATCHES}

# Seamless textures for walls, floors and outdoor ground (Gemini images, made tileable in code; no Meshy credits).
TEXTURES = [
    ("wall_concrete", "raw cast concrete wall with shutter-board marks, stains and fine cracks"),
    ("wall_plaster_cream", "old painted plaster wall, cream paint, hairline cracks, scuffs"),
    ("wall_paint_white", "institutional white paint over concrete, slightly yellowed, chips and grime"),
    ("wall_steel_bulkhead", "riveted steel bulkhead plates painted grey, rust runs at the seams"),
    ("wall_alu_clad", "ribbed aluminium cladding panels, dull, dented"),
    ("pipe_lagging", "canvas-wrapped pipe insulation lagging with straps, stained"),
    ("floor_concrete", "worn concrete floor, smooth with scuffs, oil stains and cracks"),
    ("floor_concrete_iced", "concrete floor with a thin layer of frost and ice patches"),
    ("floor_tile_clinic", "small square off-white ceramic floor tiles, cracked, grey grout"),
    ("floor_tile_frosted", "pale green ceramic wall-and-floor tiles with frost in the grout"),
    ("floor_lino", "worn institutional linoleum, mottled grey-green, scuffed paths"),
    ("floor_parquet", "old oak herringbone parquet, worn and dull"),
    ("floor_planks_grey", "grey weathered wooden floor planks"),
    ("floor_grating", "steel bar grating floor, rusty"),
    ("floor_diamond_plate", "steel diamond tread plate, worn shiny on the high points, rust in corners"),
    ("metal_steel_grey", "painted grey steel, chipped"),
    ("metal_steel_green", "painted green steel, chipped and scratched"),
    ("metal_steel_rust", "heavily rusted steel sheet"),
    ("ground_snow", "trodden snow seen from above, uneven, faint footprints"),
    ("ground_yard", "a scrapyard ground of frozen mud, slush and gravel seen from above"),
    ("ground_asphalt", "cracked icy asphalt road surface seen from above with frost in the cracks"),
    ("ground_concrete", "outdoor concrete slabs with frost, cracks and weeds frozen in the joints"),
]


def texture_prompt(desc):
    return ("Generate an image: a seamless tileable texture, square 1:1, flat top-down orthographic view, even lighting with "
            "no shadows or highlights, of " + desc + ". Realistic, from a cold Eastern-bloc Cold War setting, muted colours, "
            "no objects, no perspective, no text.")


if __name__ == "__main__":
    n = 0
    for k, items in BATCHES.items():
        print(f"== {k} ({len(items)})")
        for name, desc, poly in items:
            n += 1
            print(f"{name} [{poly}]: {prompt(desc, STYLE_OF[k])}\n")
    print(n, "models,", len(TEXTURES), "textures")
