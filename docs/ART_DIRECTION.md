# Silo 81 - Character Art Direction & Visual Consistency

**Status: permanent project rule.** It applies to every character and creature made for this game:
player characters, NPCs, enemies, bosses. Read it before making or changing one. Do not redesign the
established visual identity without a deliberate, agreed reason.

**Core principle:** every character must look like it belongs in the same game, not like an
independently generated asset.

## 1. Consistent visual language

- Keep proportions, anatomical exaggeration and geometric complexity consistent.
- Use one coherent material philosophy across all characters.
- Don't mix realistic, cartoonish, photorealistic and overly stylized designs.
- Characters share similar levels of detail and surface refinement.
- Avoid the generic AI-generated look.

## 2. Colour and materials

- Keep to one colour palette that suits the game's atmosphere.
- Use controlled saturation, not over-vibrant colours.
- Materials should feel physically coherent within the same environment.
- Avoid random colour combinations, excessive gloss and inconsistent lighting responses.
- Each character or creature may have its own distinctive colours without breaking the overall palette.

## 3. Modelling philosophy

- Prioritise recognisable silhouettes.
- Give creatures distinctive anatomy and memorable proportions.
- Avoid micro-detail that disappears at the game's actual resolution.
- Keep modelling quality consistent across enemies of every size and importance.

## 4. Animation consistency

- Keep one animation philosophy.
- Movement is grounded and fits each creature's anatomy.
- Walk, idle, attack, hit and death share similar levels of polish.
- No exaggerated animation on one creature and stiff, mechanical animation on another, unless that's intentional.

## 5. Production requirements

- Always judge a character by how it looks inside the actual game.
- Preview models under the same lighting and camera.
- Evaluate the final rendered sprites at their in-game resolution.
- Use previously approved characters as visual references when making new ones.

**Final quality test:** put several characters next to each other in the same scene. Despite
different anatomy, species and designs, they must unmistakably look like inhabitants of the same world.

---

# How this applies in Silo 81 (the concrete pipeline)

These are the project's existing decisions that the rules above protect. Follow them unless the
rule above is being deliberately changed.

## World and look

- A civilian Cold War shelter in the Carpathians, three generations in. People wear practical,
  mended, worn clothing: wool, canvas, quilted vests, overalls, knitwear, old uniforms. Nothing new,
  nothing shiny, nothing heroic.
- Style anchor for concepts: painterly-realistic concept art, grounded proportions, muted and
  desaturated colours, readable silhouette, full figure on a plain light grey background.
- Faces are distinct, slightly asymmetric and realistic. Skin tones vary (different undertones even
  among white characters; Black and Asian characters are fine).
- Each character gets its own dominant clothing colour inside the muted palette; not everyone olive.

## Approved references (use them when making anything new)

- In game: `game/characters/player_male` (the player) and `game/characters/tibor` (maintenance dispatcher).
- Concepts: `art/concepts/` - tibor, grigore, kiss, oana, albu, rus (skin-tone revisions), plus the
  sheet `silo81_characters_v0.2.jpg`. elisabeta, kasimir, viktor and ileana are due for the same
  skin-tone pass before they are modelled.
- When prompting Gemini (Nano Banana 2.1) for a new concept, attach one or two approved concepts as
  reference and say "same style, same rendering, same palette, same proportions as the attached".

## Making a character

1. **Concept** - Gemini in the browser (Nano Banana 2.1), with approved concepts attached as style
   reference. Full body, neutral A-pose or relaxed stance, plain light grey background.
2. **3D** - Tripo Studio: image to model; Retopology 20k triangles (Smart Mesh); Auto Rig, Humanoid,
   Mixamo preset. Same settings for every character.
3. **Animation** - humans share the player's motion clips via `tools/blender/retarget.py`
   (copies walk, run, idle, hit, fall onto any Mixamo rig), so every human moves the same way.
   Creatures get their own animation, at the same frame rate and the same level of polish
   (idle loop, locomotion without sliding, attack, hit, death).
4. **In game: live 3D (general rule).** Everything that moves is drawn live from its GLB, not from
   sprites: export it game-ready (feet at z=0, real height, all clips, held items attached; see
   `tools/blender/export_live.py` for the player) with a sidecar JSON mapping the Actor's clip names to its actions,
   and show it through `scripts/puppet3d.gd` (orthographic camera at the shared 47 degrees, 165 px per
   metre, `shaders/toon_v2.gdshader` with the same three bands and saturation, plus
   `shaders/ink_outline.gdshader`). Locomotion is played in place; the Actor moves the character, so
   feet never slide. Static scenery stays pre-rendered. Sprite renders (step 5) are a fallback and
   the reference the live look is checked against.
   Status (Nov 2026): the player, Tibor and the pipe worm are live 3D (`game/characters/*_3d`),
   each checked against its sprites with `CHAR=<folder> godot --script tools/puppet_test.gd`.
   Rigged characters: `tools/blender/export_live.py` (player, with pistol and aim) and
   `export_live_npc.py` (any Mixamo NPC). Rig-less creatures built in code (the worm): export every
   frame's vertices (`worm_live.py`) and the puppet plays them as a mesh flipbook.
   The toon shader takes Blender's bands as linear values (it converts them, because the
   Compatibility renderer shades in sRGB). Launch with `-- --sprites` to compare.
   **Detail treatment (general rule for every new model, Nov 2026):** keep the model's normal map
   and use it as relief inside the toon bands, export textures at up to 2048 px as JPEG q92, and
   give the sidecar json `"normal_strength": 1.6, "band_soft": 0.06, "rim": 0.6` (soft band edges
   and a faint warm rim on the lit side). Metal and roughness maps are still dropped. Bands are
   chosen from the smooth normal, so the three-band look stays and the normal map only modulates
   brightness within a band (clamped 0.55-1.45). A model with no normal map still gets soft bands
   and rim (`normal_strength` 0). This is the default in `export_live_npc.py` and the
   `tools/blender/meshy_*.py` scripts; `--flat` gives the old base-colour-only 1024 px export and
   is only for comparison. Characters exported before this rule (player, Tibor, Overseer,
   townsfolk, goat) keep the flat look until they are re-exported. Check a new model next to its
   source with `A=src.glb,src.json B=game.glb,game.json godot --path game -s tools/compare_test.gd`.
5. **Render (fallback / reference)** - only through `tools/blender/render_character.py`: orthographic, the shared camera
   (`tools/blender/camera.json`, 47 degrees), 165 px per metre, six hex directions, key light from
   top-left-front, three toon bands over the painted texture, the same ink outline and the same
   saturation reduction. Never light or shade one character differently from the rest, and keep the
   bands in line with the environment's v2 look (`docs/VISUAL_DIRECTION.md`).
6. **Pack** - `tools/blender/package_npc.py` (or the player's packer), then quantise the sheets to
   256 colours. Keep feet anchors and per-frame steps, so movement never slides.
7. **Check** - `python3 tools/lineup.py lineup.png` puts every character's idle frame side by side
   at the game camera's zoom on a Silo 81 floor. A new character is done only when it passes the
   final quality test in that line-up and in the game itself.

## Meshy models (enemies, Nov 2026)

The Tier 1 enemies now come from Meshy and replace the Blender-built ones below (those scripts and
.blend files are kept for reference):

- The Tattered Hunger (`tools/blender/meshy_hunger.py`): replaces the Infected. It keeps Meshy's
  idle, walk, run and attack clips and retargets hit and death from the Changed. Outside combat it
  patrols left and right at walking pace; in combat it only runs.
- The Spined Wasteland Stalker (`meshy_stalker.py`): replaces the Feral. The script adds a jaw bone,
  plus idle, bite, hit and death clips authored in Blender on Meshy's skeleton.
- The pipe worm (`meshy_worm.py`): a 19-bone chain with crawl, bite, chew and release clips posed
  along a spine curve.
- Each writes the game GLB and json with the detail treatment above. The Meshy originals are in
  `source/meshy/` (not in git).

## Enemies and creatures modelled in Blender (from code)

The Tier 1 Firn Strata pair are built entirely in Blender by script, following the creature workflow
(blockout -> final shape -> retopology -> baked detail -> painted texture):

- `tools/blender/human_kit.py` - the kit: metaball sculpting with true radii (`Sculpt`), surface
  displacement, cloth shells (solidify, hems, wrapped bands), QuadriFlow retopology with a decimate
  fallback, painted emission materials (`Paint`: noise, masks near points, sewn patches, stitches,
  cavity), a selected-to-active bake of paint x AO onto the game mesh, bone-heat weights through a
  closed proxy body and weight transfer, and Cycles QC sheets (front/side/back/3-4 + game camera, close-ups).
- `tools/blender/infected_human.py` - the Infected (hooded red parka, scarf, patched trousers, wrapped
  boots, clawed hands, gaunt open-mouthed face). About 24k triangles, humanoid skeleton (25 bones).
- `tools/blender/feral_mutant.py` - the Feral Mutant (quadruped, human hands it walks on, jumping hind
  legs, hyena jaw, ice crystals from raw bases along the spine, rags on the limbs). Dedicated quadruped
  skeleton; crystals, teeth, claws and eyes are rigid islands.
- Each runs in three stages: `--stage high` (sculpt + paint), `--stage low` (game mesh + 2k bake),
  `--stage rig` (skeleton, weights, clips idle/walk/bite/hit/death, GLB + json, packed .blend), each with
  `--qc` for renders. Long runs go through `tools/sv/sv.py`.
- Paint for the game camera first: at default zoom a metre is ~100 px and the texture is shown heavily
  shrunk (mipmapped), so anything finer than ~2 cm averages away. Carry the read with big patterns
  (skin folds ~9 cm, crease lines several cm wide, painted rib and sinew shadows, large bruises, darker
  dirty limbs, strong AO), then add fine procedural detail (pores, small wrinkles, weave) for close views.
  Check skin in the real toon shader (`ONLY=0 SCALE=1.0 godot --path game -s tools/creature_test.gd`),
  not only in Blender close-ups.
- Detail is baked into the painted colour; the game keeps its toon_v2 + ink outline look. Grey is kept
  out of the palette's lead (warm reds, ochres, browns, pale flesh; ice blue-grey only on the crystals).
- Deliverables: `source/blend/infected_human.blend`, `source/models/infected_human.glb`,
  `source/blend/feral_mutant.blend`, `source/models/feral_mutant.glb`; the game copies live in
  `game/characters/infected_3d` and `feral_3d`. Check with `godot --path game -s tools/creature_test.gd`.
- The rig stage prints a ground report (lowest point per clip) and sizes the puppet view from every frame.

## Detail budget at game resolution

At the default camera zoom (0.62) a metre is about 100 screen pixels, so a 1.75 m person is about
170 px tall. Anything under about 5 cm (a button, a stitch, a rivet) is one or two pixels: it adds
noise, not readability. Spend detail on silhouette, big shapes, clothing colour blocks and the face.

## Known inconsistencies to fix (from the first line-up, Nov 2026)

- Tibor renders darker and more contrasty than the player: his Tripo texture is darker. Match his
  overall value range to the player's (texture levels or a per-character exposure in the renderer).
- The pipe worm reads as smoother, pinker and more cartoon-like than the humans. It needs the same
  painted, worn surface treatment (mottled, scarred, less candy-pink) to sit in the same world.
- `render_character.py` scales every character to 1.75 m. Characters should have their own real
  heights (a short grandmother, a tall guard) so silhouettes differ.
