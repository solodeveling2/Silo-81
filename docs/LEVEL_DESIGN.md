# Level and room design rules

World structure (one seamless, chunk-streamed overworld + isolated interiors) follows
`docs/WORLD_ARCHITECTURE.md`; this file covers the rooms and levels inside it.
The first outdoor level brief (Silo 81 → Junk Town) is `docs/LEVEL_ROAD_TO_JUNK_TOWN.md`.

These rules come from the Level 2 and Level 3 rework (47° camera, 3.5 m corridor, wall hierarchy, low gallery wall). Apply them to every new room or level, and to any room that gets rebuilt, wherever they make sense for that space. Where a room is a deliberate exception (a cramped crawlspace, a ruined section), say so in a comment next to its definition in `build.py`.

## Camera
- One view for everything: `tools/blender/camera.json` (47° above the horizon, orthographic, diagonal across the plan grid, 165 px/m). `Hex.ELEV_DEG` in `game/scripts/hex.gd` must match it. Never put a camera angle or a 0.5 / 0.866 factor directly in new code; use `Hex.SIN_E` / `Hex.COS_E` / `Hex.VSCALE` in the game and `SIN` / `COS` from `camera.json` in the render scripts.
- A level or character rendered at another angle is a bug. `level.gd` warns when it loads one.

## Proportions and spacing
- Use real-world sizes. A room should hold its furniture with walking space around it: about 0.8 m clear in front of beds, lockers, desks and fixtures.
- **Corridors:**
  - A level's main spine, where people queue, gather and pass doors on both sides: about 3.5 m between wall centres.
  - Secondary corridors: about 3.2 m.
  - Never below 2.8 m.
- Don't make every room the same rectangle. Vary sizes by use: dormitories are long, single rooms small, shared spaces (commons, galleries, plant rooms) large.
- No gaps for the sake of gaps. Rooms share walls and open off corridors like a real building.
- Avoid parallel walls closer than about 1.5 m unless the space is meant to feel tight.

## Wall hierarchy (`wall_kind` in build.py classifies walls automatically)

| Kind | When | Thickness | Height | Top cap | Posts |
|---|---|---|---|---|---|
| `struct` (the shelter's shell) | open space on one side | 0.30 m | full (2.7 m) | dark | at its corners and ends only |
| `corr` (corridor walls) | a corridor, landing, lobby or gallery on one side | 0.18 m | full | dark | none |
| `part` (partitions) | rooms on both sides | 0.12 m | 2.35 m | lighter, finer | none |

- Caps are the wall's own top, so they stay proportional to its thickness.
- Override with `kind=` on a wall only when the automatic class is wrong.
- Door frames are slim and sized to the wall they sit in. Don't add jambs heavier than the wall.

## Seeing into rooms
- Walls in front of the player are handled by the cutaway (`wall_cut.gdshader`). It cuts strips that overlap an actor's outline down to an opaque stub with a sawn top. Never use transparency for walls.
- When a room exists to show something along its back wall (pipe galleries, plant rooms, anything the player has to read at a glance), give the level `front_h` (Level 3 uses 1.1 m). Its camera-side walls then stay low permanently, with a dark sawn top; back walls keep full height.
- Keep tall furniture off camera-side walls where it would be hidden. Put it against back walls or free-standing.

## Wall materials: aged, per room (kit.py `_age`, build.py `wall_material`)
Every new room uses this by default.
- **One building, a few paints.** `PAINT` in build.py gives each room type its upper paint, its dado colour and its dado height: institutional cream over green in corridors, yellowed beige over faded green in quarters, a paler and higher dado in wet rooms, thin paint over concrete in storage and maintenance. Keep new paints muted and close to these.
- **Each wall face ages like the room it looks into** (`wall_rooms` picks the room on each side). A partition between a dormitory and a store is clean-ish on one side and grimy on the other.
- **Room type → wear profile** (`room_profile`, by room id/name, or set `age="storage"` on a room): `corridor`, `sleeping`, `storage`, `maintenance`, `wet`, `public`, `kept` (rooms people with power keep up).
- **Wear profile controls** (kit.py `AGE_PROFILES`, each 0..1):

  | Control | What it does |
  |---|---|
  | `drift` | large, soft tonal zones in the paint |
  | `warm` | how much of that drift is yellowed |
  | `repaint` | later rectangular repaint patches in fresher paint |
  | `peel` | paint worn back to concrete, in a few clusters, mostly low down |
  | `grime` | dirt rising from the floor, and dust under the ceiling |
  | `scuff` | hip-height smears |
  | `stains` | water runs from the top, plus a tide line |
  | `damp` | mould blotches near the floor |
  | `rust` | rust spots and drips |
  | `cracks` | rare, pale filler lines |
  | `shade` | darkens the whole wall (storage, maintenance) |
  | `seed` | set per room, so neighbouring rooms don't repeat |

- **Colours of the layers** are constants next to the profiles (`CONCRETE_BARE`, `GRIME_RGB`, `STAIN_RGB`, `DAMP_RGB`, `RUST_RGB`, `FILLER_RGB`).
- **Scale rule:** at the game zoom, 1 m is about 100 px. Nothing in a material may be finer than about 0.15 m, or it reads as noise. Judge materials only in renders from the game camera (`exp_camera.py`, `--shot`), never in close-ups.
- **No bump or roughness:** walls use the flat toon style (colour times light bands), so material identity comes from colour layers.
- **Not every wall is dirty.** Profiles keep large clean stretches. Raise a control for a specific room rather than globally.

## Changing a layout
- Move whole sides of a level with helpers like `shift_south(D, line, dv)` rather than editing coordinates one by one. Doors keep their positions along the corridor, rooms keep their sizes, and props, decor, inspect points, stairs, spawns, holes and bounds move with them.
- The game's collision, pathfinding and the autotest read positions from the level data, so they follow automatically. Check spawns and quest positions after any move.

## Process (test before regenerating)
1. Try a new idea on one representative section first with `tools/blender/exp_camera.py`, which renders a section with real furniture and the player. It also reports the projection error, which must be 0.0 px, and how much floor is visible.
2. Compare variants side by side (for example current, +15% and +25%) and pick one before touching the level.
3. Rebuild only the affected level, through the supervisor:
   `python3 tools/sv/sv.py run build_L2 --expect 700 --cwd level --out out/L2/level.json -- python3 -I build.py L2 out`
4. Check it in the running game with `--shot=OUT.png,LEVEL,u,v`. Confirm that feet sit in their rings, sorting is right against furniture and walls, the cutaway opens only in front of the player, and nothing floats. Then run the autotest.
5. Only then regenerate further levels or characters.
