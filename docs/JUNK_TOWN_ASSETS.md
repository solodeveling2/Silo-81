# The road to Junk Town and Junk Town itself - how they are built

Level `RD` in `tools/blender/build.py` -> `game/levels/RD`: one continuous outdoor level from the Silo 81
surface portal to the inside of Junk Town (brief: `docs/LEVEL_ROAD_TO_JUNK_TOWN.md`). Built with
`python3 -I tools/blender/build.py RD out` (about 6 minutes; run it through `tools/sv`), then copy
`out/RD/*` to `game/levels/RD`. Reference: `art/concepts/junk_town_ref.png`.

## Layout (plan metres: u east = screen up-right, v north = screen up-left)

| Section | u | What is there |
|---|---|---|
| A Silo exit | -2..22 | portal in the hillside (blast leaf jammed open, SEALED FROM INSIDE), guard post, sandbag nest, snapped barrier, evacuation board, bent chain-link, car graveyard and an overturned army truck |
| B The road | 22..50 | leaning pylon over the road, fallen pylon, **E1** the stalled car (1 Changed standing still, 2 buried in the snow that rise), jack-knifed red trailer, optional rest stop (kiosk NO FUEL, pumps, **E2** 2 Changed) |
| C Scrapyard | 50..64 | NEW MERIDIAN 40 billboard, containers, burned bus, graves of exhaust pipe and hubcaps, **E3** 3 Changed before the gate; the gate towers fire from round 2 |
| Junk Town | 64..92 | ring of Tripo vans, cars, plank and chain-link panels; gate in the west wall; watchtowers; tarp shacks (Bunkhouse, Clinic tent, Mara's garage, Market shack, Water store), smokehouse, market stalls round the burn barrel, washing lines, a car on blocks, goat pen with three live 3D goats |

Tall things stand on the far sides (north and east); the camera-side walls (west, south) stay low or see-through.
Entering any `jt_` room completes "Reach Junk Town".

## Tripo models (`source/props3d/junk_town/*.glb`)

From the two Tripo Studio canvases (textured FBX converted to GLB, textures capped at 2048):
`jt_van_ladder`, `jt_van_a`, `jt_van_b` (UAZ vans propped with timber), `jt_car` (Zhiguli),
`jt_plank_fence`, `jt_chainlink`, `jt_tower`, `jt_tarp_shack_a/b/c`, `jt_cabin_a/b/c`.
They are `GLB_PROPS` entries used through the `glbp` prop (`key`, optional `turn` and `mirror`); the kit's
toon treatment is applied to their textures. The cabins (blue slate roofs, stone chimneys) read as a fantasy
village and are not used. `JTT` in build.py renders all of them on one plot for checking.

## Kit pieces (`tools/blender/kit.py`)

Road: `silo_portal`, `guard_shack`, `sandbag_nest`, `road_barrier`, `power_pylon`, `fallen_pylon`,
`box_trailer`, `billboard`, `army_truck_side`, `burned_bus`, `shipping_container`, `guardrail`, `dead_tree`,
`rest_kiosk`, `fuel_pump`, `grave_marker`, `notice_board`. Town: `junk_gate_open`, `junk_shack`,
`market_stall`, `laundry_line`, `yard_wreck`, `oil_drum`, `burn_barrel`, `tyre_stack`, `scrap_pile`,
`animal_pen`, `firewood`. Signs get real lettering (`portal_fn`, `billboard_fn`, `kiosk_fn`).

## How a big outdoor level stays light (web)

- `godot_ground`: Blender renders no background. Godot draws the ground from tiling textures in
  `game/levels/_ground` (snow, yard, asphalt, concrete; `tools/design/ground_textures.py`) on the plan
  rectangles, plus soft decals (road line, ruts, slush, black ice, boot prints, trodden paths), snow drifts
  as three-band toon domes, and additive warm pools under the lamps (`level.gd _build_ground`).
- `sprite_scale` 0.62: props render at the size they are shown at the default zoom; `max_zoom` 0.85.
- Result: about 110 MB of textures for the whole road and town (a Silo level is about 80 MB).

## Enemies and encounters (`game.gd`)

`ENEMY` holds each kind (worm, changed): HP, AP, attack, messages. Level spawns
`spawns.enemies`: `{kind, u, v, dir, group, wake, state: idle|still|hidden, coat, speak, speak_d}`.
Only the group you wake (or shoot) joins the fight; `hidden` ones rise when the group is hurt or in round 2;
`support` entries are allies who fire from a point after a given round. Dead enemies are kept per level.
The Changed: `tools/blender/export_changed.py` (civilian Tripo body, claw lunge, retargeted death),
recoloured per instance in the toon shader (duotone: pale mottled skin, coat colour) and twisted by
`pose_offsets` / `pose_scales` in `game/characters/changed_3d/changed.json`.
Check: `godot --path game --script tools/changed_test.gd`, and `godot --headless --path game -- --test-road`
(walks portal -> both fights -> Junk Town, prints each step).

## Still to do

- Rook and Mara (Junk Town NPCs and the New Meridian lead), townsfolk.
- A proper Tripo model for the Changed (needs Tripo credits); now they share the civilian body.
- Loot in the cars and the rest stop (there is no pickup system yet).

## Update (Nov 11): scrap houses, neutral townsfolk, Blender-built enemies

- The Tripo tarp shacks and cabins read as medieval fantasy and are no longer placed. Every Junk Town
  building is `kit.scrap_house` (corrugated sheet in mismatched paints, car doors, planks, tin roofs
  weighed with tyres, stovepipes that smoke, painted signs): textures from `tools/blender/textures_scrap.py`.
  `SHT` in build.py is a check plot of all eight buildings.
- Townsfolk are neutral actors (`spawns.folk`, game.gd `_spawn_folk`): click to talk, attacking one turns
  the whole town hostile (`flags.town_hostile`). No enemies spawn inside the wall.
- Road enemies are the Tier 1 Firn Strata pair, built and animated in Blender from code
  (`tools/blender/creature_kit.py`, `feral.py`, `infected.py` -> `game/characters/feral_3d`, `infected_3d`):
  the Feral (ice-spined crawler) and the Infected (hooded, deranged survivor). The Changed (reworked
  Tibor body) are no longer spawned. Check them with `godot --path game -s tools/creature_test.gd`.
