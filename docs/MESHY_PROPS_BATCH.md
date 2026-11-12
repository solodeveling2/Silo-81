# Meshy batch: every prop in every level (Nov 2026)

These four batches remake every object inside the levels: the silo rooms (L1–L5), the road (RD) and
Junk Town. Walls, floors and doors stay in the kit (`kit.py` / `build.py`), because they need exact sizes,
the wall hierarchy and the cutaway. Scale doesn't matter: `build.py` fits every GLB to the real size given
below (`GLB_PROPS` fit/L/D/H). Creatures (goats) are not props and are not in the batches.

**How to run:**
1. In Meshy, choose Agent Mode → Batch Models and paste one batch block, including the style header.
2. Model: Meshy 7, textured, with PBR (metallic + roughness + normal). 2K texture is enough.
3. Download each model as GLB and keep the item's name as the file name (for example `silo81_bunk_a.glb`).
4. Send me the GLBs, a batch at a time or all at once. I install them into `source/props3d/meshy/`,
   map them in `GLB_PROPS`, and rebuild the levels.

**Cost:** 79 models × ~35 credits ≈ 2,800 credits.

Sizes are length × depth × height in metres; the front is the long side people use.

---

## Batch 1: silo living quarters (dorms, canteen, school, clinic): 27 models

```
Game props for a 1960s Eastern-bloc civilian Cold War fallout shelter, decades later: cold, overcrowded,
slowly failing. Realistic, weathered, heavily used: chipped enamel and worn paint over steel, rust at
edges and screw heads, grime in corners, patched fabric, scuffed wood. Muted palette: faded olive, dark
blue-grey, industrial teal, off-white enamel, dull wood brown, rust orange. Not cartoonish, not glossy,
not clean, not sci-fi, not fantasy.
Every model: ONE single free-standing object, realistic real-world proportions, front facing the viewer,
standing on flat ground, no floor plate, no base, no background, no people, no readable text.
PBR textures with no baked lighting or shadows in the base colour; real metallic and roughness.

1. silo81_bunk_a - steel two-tier bunk bed, 2.0 x 0.9 x 1.7, thin striped mattresses, grey wool
   blankets folded badly, a pillow, a towel over the rail, a small bag tied to the ladder.
2. silo81_bunk_b - same steel two-tier bunk, lived-in differently: a patched quilt hanging down the side,
   clothes on the rail, a tin mug and a book on the top mattress.
3. silo81_bunk_stripped - the same bunk frame abandoned: bare sagging spring mesh, one rolled mattress,
   no bedding, rust on the welds.
4. silo81_bed_player - single steel-frame bed, 2.0 x 0.9 x 0.8, thin mattress, a hand-crocheted
   granny-square blanket in faded colours, a worn pillow, a small rug-covered crate at the foot.
5. silo81_locker - single steel locker, 0.55 x 0.5 x 1.9, olive paint worn to bare metal round the
   handle, louvred vents, dents, a padlock, a photo taped inside the vents.
6. silo81_locker_double - double steel locker, 1.0 x 0.5 x 1.9, two doors, faded olive, dents and rust.
7. silo81_curtain - privacy partition: a grey army blanket pinned with clothes pegs to a sagging wire
   between two thin steel posts, 0.65 wide x 1.9 high, heavy soft folds, frayed edges.
8. silo81_chair - steel-tube canteen chair with a plywood seat and back, 0.5 x 0.5 x 0.9, chipped paint.
9. silo81_stool - round-seat steel stool, 0.36 x 0.36 x 0.62, worn wooden top.
10. silo81_table - canteen table, 1.2 x 0.7 x 0.76, steel legs, scratched laminate top with a tin cup,
    an enamel bowl and a spoon.
11. silo81_bench - long wooden canteen bench on steel legs, 2.2 x 0.32 x 0.45, worn planks.
12. silo81_desk - office desk, 1.2 x 0.6 x 0.76, steel body painted blue-grey, drawers on the right,
    papers, a desk lamp, an ink stamp, a mug.
13. silo81_schooldesk - two-seat school desk with attached bench, 1.1 x 0.85 x 0.8, wood and steel,
    exercise books and pencils on top.
14. silo81_counter - canteen serving counter, 2.0 x 0.62 x 0.92, stainless steel top, painted front
    panels, a stack of trays, a ladle.
15. silo81_stove - large institutional cast-iron kitchen range, 1.6 x 0.8 x 0.95, four hot plates,
    a dented stockpot, an oven door with a towel, soot stains.
16. silo81_kitchen_shelf - open steel shelving unit, 1.1 x 0.45 x 1.8, tins, jars, enamel pots,
    sacks of flour.
17. silo81_linen_shelf - open steel shelving unit, 1.1 x 0.45 x 1.9, folded grey blankets, sheets and
    towels, some in bundles tied with string.
18. silo81_sinks - row of three ceramic washbasins on a steel frame, 2.1 x 0.45 x 0.9, brass taps,
    exposed pipes underneath, cracked enamel, a bar of soap, a tin mirror above each basin.
19. silo81_toilet_stall - one toilet cubicle, 0.9 x 1.2 x 2.05, painted steel partition walls and door
    ajar, a squat-style ceramic toilet inside, chipped green paint.
20. silo81_laundry - laundry corner, 1.8 x 0.6 x 1.6, a galvanised washtub on a stand with a washboard
    and a wooden drying rack with grey clothes.
21. silo81_bucket - galvanised steel bucket, 0.34 x 0.34 x 0.35, dented, with a rag over the rim.
22. silo81_medcab - medical cabinet, 0.9 x 0.42 x 1.8, white enamel, glass doors, bottles, bandage
    rolls, a red cross worn faint.
23. silo81_medscreen - three-leaf hospital folding screen, 1.8 x 0.2 x 1.7, steel frames with faded
    off-white cloth panels, stained.
24. silo81_filing_cabinet - steel filing cabinet, 0.48 x 0.62 x 1.3, four drawers, blue-grey paint,
    one drawer half open with folders.
25. silo81_file_shelf - open archive shelf, 1.1 x 0.42 x 1.9, rows of card binders and boxed files.
26. silo81_sacks - pile of hessian grain and potato sacks, 1.1 x 0.6 x 0.7, tied with twine, one split
    with potatoes spilling out.
27. silo81_crate - wooden supply crate, 0.62 x 0.62 x 0.62, stencil-less plank sides, iron corners.
```

## Batch 2: silo technical and command rooms: 13 models

```
Game props for a 1960s Eastern-bloc civilian Cold War fallout shelter, decades later: cold, overcrowded,
slowly failing. Realistic, weathered, heavily used: chipped enamel and worn paint over steel, rust at
edges and screw heads, grime in corners, patched fabric, scuffed wood. Muted palette: faded olive, dark
blue-grey, industrial teal, off-white enamel, dull wood brown, rust orange. Not cartoonish, not glossy,
not clean, not sci-fi, not fantasy.
Every model: ONE single free-standing object, realistic real-world proportions, front facing the viewer,
standing on flat ground, no floor plate, no base, no background, no people, no readable text.
PBR textures with no baked lighting or shadows in the base colour; real metallic and roughness.

1. silo81_pump - industrial water pump on a skid, 1.2 x 0.7 x 0.9, cast-iron pump body painted
   industrial teal, flanged pipes, a pressure gauge, an electric motor, oil leaks, rust.
2. silo81_workbench - heavy workshop bench, 1.8 x 0.7 x 0.95, steel frame, thick scarred wooden top,
   a vice, scattered tools, a pegboard of tools behind.
3. silo81_toolbox - wall tool cabinet / tool chest, 1.0 x 0.3 x 1.0, red-brown paint worn, drawers,
   wrenches and bottles on top.
4. silo81_lathe - old metal lathe, 1.8 x 0.6 x 1.3, cast-iron bed, chuck, tailstock, belt guard,
   swarf on the tray, blue-grey machine paint.
5. silo81_boiler - the main heating assembly, 3.4 x 1.6 x 2.4: a massive horizontal heat exchanger
   drum, insulated pipe headers, a glowing orange inspection port, a cracked cast-iron pressure
   regulator with welded shims, gauges, valve wheels, hazard-yellow guard rail on one side.
6. silo81_control_panel - industrial heating control switchboard console, 1.8 x 0.62 x 1.6, dark
   blue-grey steel, analogue dials, big rotary switches, indicator lamps, a logbook on the ledge.
7. silo81_temp_monitor - temperature monitoring station, 1.5 x 0.65 x 1.5, strip-chart drum recorders,
   a small green CRT, thermocouple switches, cables.
8. silo81_monitors - telemetry and intercom station, 1.3 x 0.65 x 1.4, a desk with three small CRT
   monitors, an intercom handset, switches, coffee-stained papers.
9. silo81_terminal - computer desk, 1.4 x 0.7 x 1.3, a 1970s green-screen terminal, a dot-matrix
   printer with fanfold paper, a chair-less desk.
10. silo81_radioset - radio station, 1.6 x 0.6 x 1.7, a tall valve radio cabinet with dials and a
    tuning window, a bench with headphones and a morse key.
11. silo81_maptable - planning table, 1.8 x 1.1 x 0.9, a big paper map of the region pinned flat,
    pencils, a ruler, a compass, an ashtray.
12. silo81_floorlamp - standing work lamp, 0.3 x 0.3 x 1.6, steel tripod, caged bulb, a cable.
13. silo81_safe - heavy steel safe, 0.7 x 0.6 x 1.0, faded olive paint, combination dial, a handle,
    scuffs.
```

## Batch 3: the road from the silo (surface, frozen highway): 18 models

```
Game props for a frozen Eastern-bloc road decades after a Cold War catastrophe: 1960s-70s Soviet-style
vehicles and infrastructure, abandoned in deep winter. Realistic, weathered, gritty: peeling paint,
heavy rust, broken glass, a thin layer of snow only on upward-facing surfaces, icicles here and there.
Muted palette: rust orange, faded olive, dark blue-grey, dirty white, washed-out red. Not cartoonish,
not glossy, not clean, not sci-fi, not fantasy.
Every model: ONE single object, realistic real-world proportions, front facing the viewer, sitting on
flat ground, no ground plate, no terrain, no background, no people, no readable text (sign faces blank).
PBR textures with no baked lighting or shadows in the base colour; real metallic and roughness.

1. road_silo_portal - shelter entrance in a hillside, 9.0 x 1.4 x 4.5: a reinforced concrete headwall
   with short wing walls, a huge round steel blast door leaf jammed half open on darkness, a dead caged
   lamp over it, snow on every ledge.
2. road_guard_shack - small concrete guard post, 3.0 x 2.6 x 2.6, flat roof under snow, a broken window,
   the door open, a stovepipe.
3. road_sandbag_nest - horseshoe of sandbags three courses high, 3.4 x 3.2 x 1.0, open at the back.
4. road_barrier - checkpoint boom, 4.6 x 0.6 x 1.3, concrete blocks, a counterweight post, a red-white
   striped boom snapped and hanging.
5. road_power_pylon - high-voltage steel lattice pylon, 4.2 x 4.2 x 14, cross-arms, glass insulators,
   cut cable ends dangling.
6. road_fallen_pylon - the same lattice pylon lying on its side in the snow, broken in two, arms
   crumpled, 14 x 2.8 x 2.5.
7. road_box_trailer - articulated truck: a red box trailer jack-knifed with its Soviet cab folded back
   against it, flat tyres, 11.5 x 2.5 x 3.6.
8. road_billboard - roadside billboard, 6.4 x 0.9 x 5.0, two steel posts, a weathered blank board with
   peeling paper strips and rust streaks.
9. road_army_truck - GAZ-66-style Soviet army truck lying on its side, 6.8 x 3.0 x 2.6, olive cab,
   canvas tilt torn off its hoops, wheels in the air.
10. road_burned_bus - burned-out 1970s Soviet city bus, 10.5 x 2.5 x 2.9, black and rust shell, empty
    windows, sitting on its rims.
11. road_container - 20 ft shipping container, 6.0 x 2.45 x 2.6, faded blue-grey, dented, rust, one
    door ajar.
12. road_guardrail - steel W-beam guardrail section on four posts, 6.0 x 0.4 x 0.8, bent outward in
    the middle by an old crash.
13. road_dead_larch - dead larch tree, 0.8 x 0.8 x 7, grey bark, a few bare branches.
14. road_dead_birch - dead birch tree, 0.8 x 0.8 x 6, white bark peeling, broken top.
15. road_rest_kiosk - small roadside shop / rest-stop kiosk, 6.0 x 4.0 x 3.2, low brick-and-concrete
    building, a shop window, a door, a blank roof sign board, a stovepipe.
16. road_fuel_pump - old Soviet petrol pump, 0.9 x 0.7 x 1.8, rounded steel cabinet, mechanical
    counter dial, hose hanging.
17. road_grave - roadside grave, 0.9 x 1.9 x 1.2, a cross made of welded exhaust pipe, a hubcap hung on
    it, a low mound of frozen earth.
18. road_notice_board - evacuation notice board, 2.0 x 0.3 x 2.1, two timber posts, a small roof, blank
    paper notices torn and flapping.
```

## Batch 4: Junk Town (survivor settlement in a scrapyard): 21 models

```
Game props for Junk Town, a survivor settlement built in a frozen Eastern-bloc scrapyard decades after
a Cold War catastrophe. Everything is salvaged and patched: corrugated sheet in mismatched faded paints,
car doors, planks, road signs, tyres, tarps, wire. Realistic, weathered, lived-in, gritty; a thin layer
of snow only on upward-facing surfaces. Muted palette: rust orange, faded olive, dark blue-grey,
washed-out red and green, raw timber brown. Not cartoonish, not glossy, not medieval or fantasy, no
slate roofs, no stone chimneys.
Every model: ONE single object, realistic real-world proportions, front facing the viewer, sitting on
flat ground, no ground plate, no terrain, no background, no people, no readable text.
PBR textures with no baked lighting or shadows in the base colour; real metallic and roughness.

1. jt_scrap_house_a - one-room scrap house, 4.4 x 4.0 x 3.0, timber frame on salvaged concrete blocks,
   corrugated sheet walls in mismatched paints, a single-pitch rusted roof weighed down with tyres,
   a smoking stovepipe, a car door used as the front door.
2. jt_scrap_house_b - scrap house with a lean-to, 5.6 x 4.0 x 3.0, plank and sheet walls, a small
   window of scratched plexiglass, a tarp awning over the door.
3. jt_scrap_house_c - scrap house with a water tank on stilts beside it, 6.0 x 4.0 x 4.5, rusted tank,
   pipe into the wall, road-sign panels in the walls.
4. jt_scrap_house_d - garage workshop shack, 5.0 x 4.4 x 3.2, wide sheet-metal double doors, a hoist
   beam, oil drums by the wall.
5. jt_van_a - Soviet UAZ-452 van, 4.6 x 2.2 x 2.1, wheels gone, propped on timber, faded green paint,
   windows boarded, used as part of a wall.
6. jt_van_b - another UAZ-452 van turned into a shelter, 3.6 x 3.2 x 2.6, a tarp roof extension,
   stovepipe through the roof.
7. jt_van_ladder - UAZ-452 van propped on timber with a ladder up to a lookout on its roof, sandbags
   on top, 4.6 x 2.2 x 3.2.
8. jt_car - rusted Lada Zhiguli sedan, 4.2 x 1.8 x 1.4, no wheels, on blocks, cracked windows.
9. jt_plank_fence - wall panel of nailed salvaged planks and sheet on posts, 4.2 x 0.9 x 2.4,
   leaning, braced.
10. jt_chainlink - bent chain-link fence panel, 3.4 x 0.25 x 2.2, steel posts, barbed wire on top,
    rags and tins tied on as alarms.
11. jt_watchtower - scaffold watchtower, 2.6 x 1.8 x 6.2, scaffold poles, car-door parapet, a ladder,
    a corrugated roof, a searchlight.
12. jt_gate_open - the town gate opened by day, 4.6 x 0.4 x 3.0, two corrugated-sheet leaves on welded
    pipe frames swung back, a chain and padlock hanging.
13. jt_market_stall - trading stall, 2.8 x 1.9 x 2.4, four leaning poles, a sagging ridged tarp, a plank
    counter on two drums, jars, tins, boots, a radio, a lantern, a blank chalkboard.
14. jt_laundry_line - two poles with a line of washing, 4.0 x 0.3 x 2.0: shirts, a blanket, socks.
15. jt_firewood - stack of split firewood under a small sheet-metal roof, 1.6 x 0.7 x 1.2, an axe in
    the chopping block.
16. jt_oil_drum - 200-litre steel drum, 0.58 x 0.58 x 0.9, faded blue paint, heavy rust.
17. jt_burn_barrel - steel drum with holes punched round it and a fire burning inside, 0.58 x 0.58 x 0.9,
    soot, glowing holes.
18. jt_tyre_stack - stack of four old car and truck tyres, 0.66 x 0.66 x 0.9.
19. jt_scrap_pile - heap of scrap half under snow, 2.0 x 1.6 x 1.0: sheet panels, a car door, pipes,
    a wheel, a car bonnet.
20. jt_animal_pen - goat pen without animals, 4.2 x 3.0 x 1.2, rails and planks, a wooden trough, a pile
    of hay, a small lean-to shelter in one corner.
21. jt_yard_wreck - car on blocks being stripped for parts, 4.8 x 1.9 x 1.5, bonnet open, engine out
    on a pallet beside it.
```
