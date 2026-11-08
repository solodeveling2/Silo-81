# Silo 81 - notes for Claude

Fallout 1/2-style isometric RPG in Godot 4.3 (GDScript, Compatibility renderer). Hex grid,
turn-based combat only, Wasteland 3-style action bar. See README.md for layout and build commands.

## Permanent rules

- **Character art direction:** before creating, modelling, animating or rendering any character or
  creature, read and follow `docs/ART_DIRECTION.md`. Every character must look like it belongs to
  the same world: same proportions philosophy, materials, palette, lighting, camera and animation
  polish. Use the approved characters as references and check new ones with `tools/lineup.py`.
- **Rooms and levels:** every new room or level (and any rebuilt one) follows `docs/LEVEL_DESIGN.md`
  wherever it makes sense: the shared 47-degree camera (`tools/blender/camera.json`), real-world sizes with
  space around furniture, wide main corridors (about 3.5 m spines, 3.2 m secondary), the shell / corridor /
  partition wall hierarchy, the opaque cutaway, low camera-side walls (`front_h`) where a room exists to be
  seen, and testing one section before regenerating everything.
- Movement and attack animations must never slide: keep feet anchors and per-frame steps.
- The silo is a believable civilian Cold War shelter, not a dungeon built from game-design checklists.
  Heat inequality comes from infrastructure and politics.
- Don't use or open SpriteCook. Reference images come from Gemini (Nano Banana 2.1) in the browser;
  3D from Tripo Studio.
- Don't push to GitHub until the user says so.

## Long-running work: use the supervisor (tools/sv)
- Start anything that can run for more than about 2 minutes (Blender builds and previews, Godot import/export, packaging, asset batches) with `python3 tools/sv/sv.py run NAME --expect S --out FILE -- CMD`, or with `sv batch` for many assets. Do not use plain `&`/nohup.
- Before starting heavy work, check `sv status` / `sv ps`. Never start a second copy; use `sv wait NAME` instead (it returns within 9 minutes, and a job may legitimately still be running).
- A job is done only when `sv` says `verified` (its outputs exist, are fresh and pass format checks). `failed` means read `sv status NAME` and fix it. `escalated` means a code bug or used-up retries: report it to the user rather than looping.
- For a batch, run `sv retry NAME` to re-run only the failed items. Pass `--retries` only for idempotent commands; paid generation steps (Tripo, Gemini) run with `--retries 0`.
- Details and the hook setup are in tools/sv/README.md. Tests: `python3 tools/sv/test_sv.py`.
