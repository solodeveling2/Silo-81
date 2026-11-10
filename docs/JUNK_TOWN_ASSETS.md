# Junk Town — assets and how the level is built

Reference: `art/concepts/junk_town_ref.png` (brief: `art/concepts/junk_town_brief.txt`).
Level: `JT` in `tools/blender/build.py` → `game/levels/JT`. Built on a Blender-capable machine with
`python3 -I tools/blender/build.py JT out` (about 4 minutes), then `bg.png`, `spr_*.png` and
`level.json` copied to `game/levels/JT`. Spawns and stairs now live in the `JT()` plan itself, so the
generated `level.json` is complete (nothing hand-edited to preserve).

## Layout (plan metres)

- Town: u 2.4..28.5, v -12.5..12.5, one continuous snow floor. Road: u -7..2.4 along v = 0.
- **Ring wall** of wrecked cars nose-to-tail (`kit.junk_car_wall`):
  - far sides (north +v, east +u) are **tall**: some cars stacked two high, corrugated sheet and
    timber posts behind, raking struts on the outside; sorted *behind* everything inside (`sort_at="far"`).
  - camera-side walls (south -v, west -u) are **one car high**, sheet only in the gaps
    (LEVEL_DESIGN: low camera-side walls), split into ~4.4 m runs sorted *in front* (`sort_at="near"`).
- **Gate**: open, in the west wall at v = 0, facing the road (`junk_gate_open`, `noblock` with its
  two posts in `blocked`), so it is passable.
- **Watchtowers** on the NW, NE and SE corners (the SW corner would hide the yard).
- **Shacks** along the far walls (Bunk shack, Mara's garage, two more; Market shack and Smokehouse
  on the east wall, one on the south wall), each patched from mixed panels with a lit window.
- **Yard**: burn barrel (amber light), three market stalls, a car on blocks being stripped,
  drums, tyre stacks, crates, firewood, scrap piles.
- **Goat pen** in the south-east with three **live 3D goats**.
- Exit: `to_l1_from_jt` at (-6.2, 0) on the road; arriving from L1 puts the player at (-3, 0).

## Kit pieces (`tools/blender/kit.py`)

| piece | notes |
|---|---|
| `junk_car` | one wreck from a side profile: `volga`, `zhiguli`, `van` (UAZ-452), `pickup`; dark windows, pillars, wheel arches, half-buried wheels, rusted sills, missing doors, snow drifts |
| `junk_car_wall(L, tall, seed)` | cars nose-to-tail with yaw jitter and overlap; `tall` stacks cars and adds the sheet course |
| `junk_gate_open` | posts, top rail, sign board, leaves swung back |
| `junk_watchtower` | scaffold legs, deck, railing, roof, ladder |
| `junk_shack(seed, L, D)` | patched panel strips, single-pitch corrugated roof with drifts and tyre weights, stovepipe, warm window, door |
| `market_stall`, `firewood`, `yard_wreck`, `oil_drum`, `burn_barrel`, `tyre_stack`, `scrap_pile`, `animal_pen`, `corrugated_fence` | yard life |

## Goats (live 3D)

`tools/blender/goat_live.py OUT brown|piebald` → `game/characters/goat_3d/goat_<coat>.glb/.json`.
Low-poly rigged goat (bones body → neck → head), long body, short legs, visible neck, small head with
a darker face, horns, beard, tail up. Clip `graze` (4 s): head down cropping, up chewing and looking
round, back down. In the level they are `creatures` in `level.json`; `level.gd` spawns a `Puppet3D` for
each and drives the loop at 12 poses per second with a per-goat phase. Check with
`godot --path game --script tools/goat_test.gd` (4 facings × 5 moments → `/tmp/goat_test.png`).
The old split-sprite goat (`goat`, `goat_head`) is no longer used.

## Tripo models (still to come)

No Tripo GLBs are in the project yet (`source/props3d/junk_town/` does not exist). The kit versions
are complete stand-ins. When the GLBs are exported (Tripo Studio → model card → Export → GLB), put
them in `source/props3d/junk_town/` and swap them into `PROP_FN` the way the furniture GLBs are
(`have_glb` / `glb`), keeping the same footprints, then rebuild `JT` and compare at the game camera.

## History

The first blockout (DeepSeek pass) had one straight car wall of painted boxes, plain box shacks and a
split-sprite goat that read as a white cap on legs; it was replaced by the above.
