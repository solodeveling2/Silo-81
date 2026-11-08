# Silo 81: visual direction (environments, props, lighting)

This is the game's visual standard. It applies to every level, room, prop, piece of machinery and character, now and later. Characters also follow `ART_DIRECTION.md`; layouts also follow `LEVEL_DESIGN.md`. Any new asset or level must look like it belongs to the same building, under the same light.

The target is a believable, heavily used, slowly failing Cold War shelter: weathered, gritty and muted. It should not be grey-washed, colourful, cartoonish, glossy or clean. Objects must stay distinguishable from each other and from the walls.

## 1. No screen-wide grading
- The game never tints or grades the whole screen (`CanvasModulate` stays white, with no post effects).
- Mood comes from light baked into each level: its base tone, its lamps and its cold pockets (section 3).
- Why: a global grey-blue multiply was the single biggest cause of the washed-out look. It cost about 22% of the colourfulness on its own.

## 2. Shading model ("v2", `kit.py`, the default look)
- **Light:** one key light from the top-left-front for everything: a slightly warm lit band (`V2_LIT`), a mid band, and a darker, cool blue-grey shade band (`V2_SHADE`). That gives depth without saturation.
- **GLB props keep their full colour** (no desaturation on import) and use their glTF metal and roughness:

  | Surface | Treatment |
  |---|---|
  | Bare metal | darker body, tight bright highlight |
  | Smooth paint, enamel | soft highlight |
  | Rough rubber, fabric, wood, concrete | no highlight |

  Never throw a model's metal/roughness map away.
- **Kit-made materials** use textures from `textures.py`, tinted to their designed colour, with the same bands. Metal kit materials (`metal=` / `TEX_FOR`) get the same highlight.
- **Colour management:** Blender stays on "Standard": no Filmic or AgX, no tonemapping.

## 3. Light per level (`build.py`, `D["light"]`)
- **`ambient`:** the level's base tone. Slightly cool where heat is short (dormitories, abandoned areas), slightly warm where the heating mains run (Level 3 gallery, plant rooms, the warm command levels). Heat inequality should be visible in the light.
- **`lamps`:** `(u, v, height, radius, kind)`, where kind is one of:

  | Kind | Light |
  |---|---|
  | `amber` | working lamp |
  | `work` | strong caged lamp |
  | `bulb` | dim ceiling bulb |
  | `desk` | desk lamp |
  | `cold` | an unheated pocket |

  Put warm light where equipment works and people live; put `cold` where the frost is.
- **Automatic lamps:** desks and standing lamps add their own pools. Dark, abandoned rooms get no lamp.
- **Readability:** keep pools soft and local. Light should never wash out a whole room or hide the player.

## 4. Palette
- **Concrete:** grey, but never flat. It gets tonal drift with warm and cool undertones, from the aged-wall layers (`LEVEL_DESIGN.md`) and the textures.
- **Accents, muted, used for separation rather than decoration:**

  | Accent | Approx. linear RGB | Where |
  |---|---|---|
  | Industrial teal | (0.17, 0.33, 0.33) | pumps, machinery |
  | Dark blue-grey | (0.26–0.30, 0.30–0.34, 0.34–0.38) | cabinets, switchgear, radios, cast iron |
  | Faded olive | (0.22, 0.27, 0.17) | lockers, safes, military kit |
  | Rusty orange | from the rust layers and `RUST_RGB` | metal edges, drips, old fixtures |
  | Hazard yellow | (0.70, 0.52, 0.08) | floor markings round machinery, guard rails |
  | Institutional green / cream | the wall paints in `PAINT` | walls |

- **Where the palette lives:** kit-made objects use `V2_PALETTE` in `kit.py`. An authored-grey GLB gets a small `tint` in its `GLB_PROPS` entry (the pump to teal, cast iron to blue-grey). Correct towards the palette; never repaint a model's whole texture.
- **Saturation:** controlled. Average scene saturation around 0.18–0.22 at the game camera. Don't raise saturation globally; separate objects by hue family, value and material instead.
- **Material families must differ in colour *and* response:** rubber, painted metal, bare steel, concrete, wood and fabric.

## 5. Characters
- Characters are lit by the same model: key light from top-left-front, warm lit band and cool shade band, ink outline.
- They keep a controlled, slightly muted saturation (`ART_DIRECTION.md`) so they read as people in this world, but not greyer than the environment around them.
- At the next character re-render, match `render_character.py`'s bands to `V2_LIT`/`V2_SHADE` and check the line-up against a v2 level.

## 6. How to check (always at the gameplay camera)
1. Make a test scene first (`tools/blender/exp_palette.py` for materials and lighting, `exp_camera.py` for layout) with walls, floor, machinery and props. Render it before and after at 47°.
2. Check that:
   - objects separate from the walls and from each other;
   - metal reads as metal;
   - lamps read as warm pools;
   - cold areas read as cold;
   - the player and interactive things stay readable;
   - nothing looks glossy or cartoonish.
3. Then rebuild only the affected levels through the supervisor, and confirm with `--shot` in the running game.
