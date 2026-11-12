# Silo 81 — Hybrid Seamless World Architecture

**Status: permanent project rule.** It applies to the world map, every surface region, and every
interior transition. Read it before changing level loading, world state, transitions or streaming.

Recovered from the Antigravity design session (conversation `41a47b10-0645-4029-8f45-8ed14e678b3c`,
2026-11-09). The full original reply was truncated in the chat log; this document is the agreed
rules and phase plan.

---

## 1. What the world is

Silo 81 is a Fallout 1/2-style isometric RPG. The **first building is Silo 81 itself**: L1 (surface
transit depot) through L5 (deep storage / geothermal bore ring), entered and exited through the
**L1 surface egress**. The game is not a series of disconnected levels selected from a menu.

The target is a **hybrid world**:

- **One continuous outdoor overworld** — walk freely between outdoor locations, settlements, roads,
  checkpoints, ruins, forests and frozen wasteland. Discover places organically. No loading screen
  when crossing an ordinary outdoor boundary.
- **Isolated interiors and special locations** — Silo 81 and selected buildings/caves/dungeons are
  separate scenes, entered through explicit transitions (doors, hatches, cave mouths, lifts).
- **State survives the seams** — NPCs, enemies, dropped items, containers and quest flags keep their
  state when a chunk unloads or the player enters/leaves an interior.

Do **not** design the overworld as a collection of disconnected instances. Do **not** use a loading
screen between ordinary outdoor areas.

---

## 2. Streaming rules

- **Chunk-based**: split the surface into square chunks (terrain, props, encounters, NPCs, decor).
- **Prototype**: a **2×2 chunk** surface region outside Silo 81's blast hatch:
  - `chunk_0_0` — Silo 81 mountain trench and surface hatch
  - `chunk_1_0` — frozen rail cutting and abandoned checkpoint
  - `chunk_0_1` — mountain trail and snow clearing
  - `chunk_1_1` — valley highway approach
- **Dynamic window**: a **3×3 chunk window** around the player; background load/unload; distant
  chunks simplified or unloaded.
- **Seamless edges**: hex edges must stitch across chunk borders, and **A\* pathfinding must cross
  seams** without a visible break.
- **Budget**: this project targets the Compatibility renderer and a web build (~81 MB). Stream
  aggressively; never preload the whole world. Keep chunks lean and reusable.
- **Never unload state**: unloading a chunk unloads its visuals and physics, not its ledger of NPCs,
  enemies, loot or flags.

---

## 3. Persistence rules

- **`PersistentWorldState`** owns the world's mutable truth: per-level/per-chunk NPCs, enemy states,
  dropped items, opened containers, doors, quest flags and counters.
- `game.gd` currently keeps flat `state`/`flags` dictionaries. Phase 1 extracts them into
  `PersistentWorldState` **without changing behaviour**; existing L1–L5 and `--autotest` must pass.
- **Save/load** serialises `PersistentWorldState` to `user://savegame.json` (world position, level,
  quest flags, inventory, HP).
- **Coordinate memory**: every interior transition stores an `OverworldExitPoint` (chunk + position +
  facing) so leaving a building returns the player exactly where they entered.
- Enemy/NPC state, loot and containers must be deterministic on reload — no respawns unless the
  design explicitly says so.

---

## 4. Transitions

- **Outdoors**: no transition at all; chunks stream under the player.
- **Interiors**: a short fade through `SceneTransitionManager`, preserving the world state and the
  exit point. Silo 81 is one such interior complex, entered from L1.
- **Special locations**: same rule; they are scenes, not holes in the outdoor mesh.
- **World map**: no menu teleporting for ordinary travel; a map screen may exist for fast travel only
  if the user asks for it.

---

## 5. Current code map (what exists now)

| File | Role |
|---|---|
| `game/scripts/game.gd` | Orchestrator: root, camera, HUD, player, `load_level(id, arrive)`, state/flags, NPC/enemy spawns |
| `game/scripts/level.gd` | Parses `level.json`, renders `bg.png`, y-sorted props, wall cutaway, AStar2D square tile grid (8-way, no corner cutting), line of sight, room-based wall fade |
| `game/scripts/hex.gd` | Plan `(u,v)` ↔ metres ↔ screen pixels (165 px/m at 47°) ↔ tile `(u,v)` cells, 0.64 m squares (the file keeps its old name) |
| `game/scripts/actor.gd` / `puppet3d.gd` | Live 3D GLB characters in orthographic SubViewports; hex pathfinding; no foot sliding |
| `tools/blender/build.py` + `kit.py` | Level construction and pre-rendered art pipeline |
| `game/levels/L1…L5` | Existing interiors, connected by bulkheads and lifts |

Current `load_level()` destroys the current level with `queue_free()` and loads
`res://levels/<id>`. The hybrid world replaces this for outdoor travel with chunk streaming, while
keeping the same API for interiors.

---

## 6. Agreed phased plan

Do these in order; each phase ends with `--autotest` green and a local commit.

1. **State decoupling — `PersistentWorldState`.** Extract `state` and `flags` from `game.gd`.
   Verify L1–L5 and the full autotest still pass.
2. **Transitions — `WorldManager` + `SceneTransitionManager`.** Fade, coordinate memory
   (`OverworldExitPoint`); Silo 81 remains an isolated interior reached from the L1 surface egress.
3. **Seamless prototype — 2×2 surface chunks.** Build the four chunks above and connect their borders
   so the player walks across without loading screens.
4. **Dynamic streaming — 3×3 chunk window.** Background load/unload, hex edge stitching, A\* across
   seams; test continuous sprint across 4+ chunk transitions.
5. **Persistence and life —** ground item drops, persistent containers, wandering outdoor encounters,
   save/load to `user://savegame.json`.

---

## 7. Non-negotiables

- **Do not break** the existing L1–L5 interiors, the opening tutorial, "A Cold Reality", the live-3D
  character pipeline, or the Blender art pipeline.
- **Do not** turn ordinary outdoor travel into loading-screen hops or a menu of instances.
- **Do not** reset NPC/enemy/loot state when a chunk unloads.
- **Silo 81 is the first building and stays an interior complex**; the L1 surface depot is its
  threshold to the overworld.
- Verify with:
  `godot --headless --fixed-fps 60 --path game -- --autotest` → `quest: done`, no `SCRIPT ERROR`.
- Screenshots at the gameplay camera (`--shot=OUT.png,LEVEL,u,v`) before/after.
- No push to GitHub until the user says so. Commit locally with clear messages.

---

## 8. Related rules

- `docs/LEVEL_DESIGN.md` — camera, proportions, wall hierarchy, cutaway, aged materials.
- `docs/VISUAL_DIRECTION.md` — one light, v2 shading, palette, per-level lighting.
- `docs/ART_DIRECTION.md` — character consistency and the Gemini → Tripo → Blender pipeline.
- `docs/wasteland3_level_design_knowledge_base.md` — the 40/40 Wasteland 3 study: five spatial
  topologies, the pre-combat sabotage apron, squad-split puzzles, three reward horizons, tier pacing.
- `docs/LEVEL_ROAD_TO_JUNK_TOWN.md` — the first outdoor area (Silo exit → Junk Town): layout,
  encounters, The Changed, Junk Town hub, production plan.
- `CLAUDE.md` — permanent rules and the `tools/sv` supervisor workflow.
