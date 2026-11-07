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
4. **Render** - only through `tools/blender/render_character.py`: orthographic, 30 degree elevation
   (2:1 iso), 165 px per metre, six hex directions, key light from top-left-front, three toon bands
   over the painted texture, the same ink outline and the same saturation reduction. Never light or
   shade one character differently from the rest.
5. **Pack** - `tools/blender/package_npc.py` (or the player's packer), then quantise the sheets to
   256 colours. Keep feet anchors and per-frame steps, so movement never slides.
6. **Check** - `python3 tools/lineup.py lineup.png` puts every character's idle frame side by side
   at the game camera's zoom on a Silo 81 floor. A new character is done only when it passes the
   final quality test in that line-up and in the game itself.

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
