# Silo 81 - handoff for the next AI assistant

Read this file first, then `CLAUDE.md` (the permanent rules; they apply to you too, whatever your name),
then the three docs it points to. Do not start changing things before you have read all five.

## 1. What the project is

A Fallout 1/2-style isometric RPG in **Godot 4.3, GDScript, Compatibility renderer** (it must run in a
browser). Hex grid, turn-based combat, Wasteland 3-style action bar. Setting: a believable civilian
Cold War shelter ("Silo 81"); heat inequality comes from infrastructure and politics.

The current playable slice: the Chief Engineer wakes in Level 2 (dormitories), Tibor briefs him, he takes
the welding kit, goes down to Level 3 (pipe gallery), fights pipe worms, welds a burst pipe and reports back.
`README.md` has the layout, controls and build commands.

## 2. How the picture is made (do not break this)

- **Static things are pre-rendered 2D**: levels, walls, furniture and props are built and rendered in
  Blender by `tools/blender/build.py` + `kit.py` into PNGs that Godot y-sorts.
- **Things that move are live 3D** (since Nov 2026): the player, Tibor and the pipe worm are drawn from
  their 3D models by `game/scripts/puppet3d.gd`, each in its own small orthographic 3D view, shown as a
  sprite inside the same 2D y-sort. The old sprite sheets stay: the `Actor` (`game/scripts/actor.gd`)
  still runs them invisibly as the animation clock and for click areas, and `-- --sprites` shows them.
- **One camera for everything**: 47 degrees elevation, orthographic, 165 px per metre
  (`tools/blender/camera.json`, `game/scripts/hex.gd`). Never change it in one place only.
- **One look for everything ("v2")**: warm key light from top-left-front, cool blue-grey shade, three toon
  bands, dark ink outline, muted industrial palette, light baked per level, no screen-wide tint.
  See `docs/VISUAL_DIRECTION.md`.
- **No foot sliding**: the Actor moves characters by a fixed step per animation frame; models play
  locomotion in place. Keep it that way.

## 3. Traps that already cost time (avoid them)

1. **Colour space.** Godot's Compatibility renderer shades in sRGB; Blender works in linear. Any colour
   or band taken from Blender must be converted with `pow(c, 1/2.2)` in the shader (see
   `game/shaders/toon_v2.gdshader` and `ink_outline.gdshader`). Forgetting this made characters too dark
   and outlines pitch black.
2. **Winding order.** Blender front faces are anticlockwise, Godot's clockwise. Meshes built by hand from
   Blender data must flip triangle order (done in `puppet3d.gd`, `_setup_flipbook`).
3. **Two-sided materials.** Cycles renders both sides of a face; Godot culls back faces. Open shapes
   (the worm's throat) need `toon_v2_2side.gdshader`.
4. **SubViewport timing.** A model's AnimationPlayer is not ready on the first frame, and a resized
   SubViewport must have its texture re-bound. Both are handled in `puppet3d.gd`; keep those guards.
5. **Web size.** The toon shader reads only base colour. Exporters drop normal/roughness maps and cap
   textures at 1024 px. Keep exports lean; the web build is about 81 MB.
6. **Long jobs** (Blender renders, Godot export) go through the supervisor `tools/sv` (see `CLAUDE.md`).
   Never start a second copy of a running job.
7. **Check before rolling out.** Test one section or one character at the gameplay camera, compare it
   with what exists, then regenerate the rest. Never re-render everything to try an idea.

## 4. How to verify a change (do this every time)

- Whole mission, headless: `godot --headless --fixed-fps 60 --path game -- --autotest`
  Must end with `quest: done` and no `SCRIPT ERROR`.
- Screenshot at a spot: `godot --path game -- --shot=/tmp/a.png,L3,6.0,-0.6` (add `--sprites` for the old look).
- Live 3D model vs its sprites, six facings side by side:
  `CHAR=tibor godot --path game --script tools/puppet_test.gd -- walk 1`
  (CHAR = `player_male`, `tibor` or `pipe_worm`; writes `/tmp/puppet_<char>_<clip>.png`).
- Web: export with the `Web` preset, then `python3 tools/web/package_web.py <export dir> <site dir>`.

## 5. Where things come from

- Concept images: Gemini (Nano Banana) in the browser. 3D models: Tripo Studio (20k tris, Mixamo rig).
  **Do not use SpriteCook.**
- Source models: `source/models/` (player, Tibor), `source/props3d/` (furniture).
- Live 3D exports: `tools/blender/export_live.py` (player, with pistol and aim sequence),
  `export_live_npc.py` (any Mixamo NPC), `worm_live.py` (the worm; it has no rig, so every frame's
  vertices are exported and played as a flipbook).
- Adding a new moving character: export it with `export_live_npc.py`, add its sprite json path to
  `LIVE_3D` in `actor.gd`, compare with `puppet_test.gd`, run the autotest.

## 6. Where it stands and what is next

Done: 47-degree camera, wall hierarchy and cutaway, 3.5 m corridors, aged per-room walls, v2 light on all
four levels (L2, L3, L2W, L4W), live 3D player / Tibor / worm, web build published.

Next, in this order:
1. The user tests the live 3D characters in the browser (smoothness in Level 3 with three worms).
2. Known issues: Tibor reads a little darker than the player; the table GLB is missing (the table is
   still procedural); floor labels on camera-side walls are hidden at 47 degrees.
3. New characters and enemies: live 3D from the start (rule in `CLAUDE.md`).

## 7. Working rules with this user

- Do not push to GitHub until the user says so. Commit locally with clear messages.
- Never print, commit or share API keys (Tripo, ElevenLabs). Keys live outside the repo.
- Work fast and incrementally: do not rebuild what has not changed, run targeted tests, report progress.
- Show results as images taken at the gameplay camera, before and after.
- When something is unclear and expensive to redo, ask first; otherwise make the reasonable call and say so.
