# Silo 81 – asset pack v0.2

First art pass for Silo 81, the opening area, plus the first five character designs. Made in SpriteCook with **Nano Banana 2.1**
(`gemini-nano-banana-2.1`), HD (not pixel art), 2:1 isometric, transparent backgrounds,
using your Post-Apocalyptic Wasteland Tileset as the style reference.

Tested in **Godot 4.3**: the TileSet and the preview scene load, and floor tiles paint.

## Install

Copy the whole `Silo81_Assets` folder into your Godot project's root folder
(so the paths start with `res://Silo81_Assets/`), then open `silo81_preview.tscn`.

## What's inside

| Folder | Contents |
| --- | --- |
| `sprites/floors/` | 24 floor tiles: 8 materials × 3 variants (a, b, c) |
| `sprites/walls/` | 17 wall pieces: concrete, steel bulkhead, doorways, pressure door, pipes, windows |
| `sprites/machinery/` | 10 pieces: geothermal core, heat exchanger, boiler, air filtration, fuse cabinet, water tank, terminal, 3 pipe parts |
| `sprites/props/` | 11 pieces: bunk bed, mess table, lockers, hospital cot, medical cabinet, hydroponic rack, archive shelf, desk, space heater, crates, water canister |
| `sprites/doors/` | The frozen blast door with "81" |
| `sprites/characters/` | 5 character designs, one facing each: player (male), player (female), Mira Lenz, Sanda Rusu, Ilona Varga |
| `tilesets/silo81_floors.tres` | Isometric TileSet (tile size 120×60) built from `silo81_floors_atlas.png` |
| `tilesets/silo81_floors_atlas_map.json` | Which atlas cell holds which floor tile |
| `silo81_preview.tscn` | An empty `Floor` TileMapLayer ready to paint, plus every sprite laid out by category |
| `sheets/` | The 4 original generated sheets |
| `spritecook-assets.json` | SpriteCook asset IDs, so pieces can be edited or regenerated in the same style |

## Notes

- **Scale.** Pieces came out at different sizes. The preview scene already applies a suggested
  scale to each prop (for example the blast door at 0.55, the water canister at 0.4) so they
  roughly match the 120 px floor tile. Walls and floors are at 1.0.
- **Characters** are design stills, not animated yet, at a suggested scale of 0.25 (about 250 px tall).
  They all face down-left; flip them horizontally for down-right. The other 4 hex directions and
  the walk/attack animations come next.
- **Hex grid.** The floor TileSet is isometric, which is how Fallout 1 drew its floors too.
  The hex grid for movement and turn-based combat is a separate logic layer drawn on top.
- **Sorting.** The `Props` node has Y-sort on, so props further down the screen draw in front.
- **Texture filter.** For this HD art, keep Godot's default Linear filter (not Nearest).
