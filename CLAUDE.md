# Silo 81 - notes for Claude

Fallout 1/2-style isometric RPG in Godot 4.3 (GDScript, Compatibility renderer). Hex grid,
turn-based combat only, Wasteland 3-style action bar. See README.md for layout and build commands.

## Permanent rules

- **Character art direction:** before creating, modelling, animating or rendering any character or
  creature, read and follow `docs/ART_DIRECTION.md`. Every character must look like it belongs to
  the same world: same proportions philosophy, materials, palette, lighting, camera and animation
  polish. Use the approved characters as references and check new ones with `tools/lineup.py`.
- Movement and attack animations must never slide: keep feet anchors and per-frame steps.
- The silo is a believable civilian Cold War shelter, not a dungeon built from game-design checklists.
  Heat inequality comes from infrastructure and politics.
- Don't use or open SpriteCook. Reference images come from Gemini (Nano Banana 2.1) in the browser;
  3D from Tripo Studio.
- Don't push to GitHub until the user says so.
