# Junk Town — asset status

**Status: 2 of 6 modules finished on Tripo; 4 blocked by credits. No GLBs downloaded yet.**
Project: `https://studio.tripo3d.ai/canvas/projects/01a1c0ea-08ae-7d31-9692-620b352aaf60`
Credits remaining: **10**.

| Module | Tripo node | State |
|---|---|---|
| Car-wall section | #45 | Smart Mesh + UV done, saved to asset library |
| Junk gate | #47 | Smart Mesh + UV done, saved to asset library |
| Corrugated fence | #46 | stopped at Smart UV — no credits |
| Watchtower | #48 | stopped at Smart UV — no credits |
| Shack | #49 | stopped at Smart UV — no credits |
| Animal pen | #50 | stopped at Smart UV — no credits |

Tripo’s own message: *“6 of 6 didn't finish… You don't have enough credits for this step.”*

## Exporting the two finished modules

They were saved with **right-click → Save to asset library** (toast confirmed). They are not yet
visible in the Assets grid in this session, so wait for the library to sync, then:

1. Open `https://studio.tripo3d.ai/assets`, find **car-wall section** and **junk gate**.
2. Open the model → **Export** → GLB (20k tri budget).
3. Save to `source/props3d/junk_town/car_wall_section.glb` and `junk_gate.glb`.

If they never appear, the fallback is to rebuild them in the Blender kit — the shapes are simple
stacked car bodies, corrugated sheets and timber posts.

## Recommended fallback (no credits)

Do not wait on a top-up to keep building. The four missing modules are all kit-friendly:

- **Corrugated fence:** sheet-metal panels on timber posts, leaning at slight angles.
- **Watchtower:** scaffold poles, ladder, car-seat platform, corrugated roof.
- **Shack:** timber frame, patched sheet walls, stovepipe, snow on roof.
- **Animal pen:** pallet/plank fence, trough, hay, goat silhouettes.

Build them as `kit.py` props, render them into the Junk Town level at 47°, and keep the two Tripo
models as the hero pieces (gate and car-wall) once exported.

## Reference

`art/concepts/junk_town_ref.png` and `art/concepts/junk_town_brief.txt`.

## Kit fallback — built (this pass)

The four missing modules now exist procedurally in 	ools/blender/kit.py:

- corrugated_fence(name, L, H) — leaning sheet panel on timber posts.
- junk_watchtower(name, H) — scaffold legs, deck, railing, corrugated roof, ladder.
- junk_shack(name) — timber frame, patched sheet walls, stovepipe, snow roof, door ajar.
- nimal_pen(name) — rail pen, trough, hay, feed bin.
- goat_body(name) + goat_head(name, pose) — the goat is split so the head can move while it eats.
  pose 0 = head down, 1 = half up, 2 = up.

Wired into uild.py as PROP_FN entries and a new **JT** plan (Junk Town blockout:
gate yard, market row, pen, two towers, three shacks, fence wall). Built with:

`
blender -b -P tools/blender/build.py -- JT out/JT
`

Preview: docs/JUNK_TOWN_BLOCKOUT.png (4781×3166 render, scaled).

### Grazing goats

game/scripts/level.gd now collects goat_head props into grazers and nods each head around
its neck (bottom-centre pivot) in _process:

`
rotation = sin(t * 1.25 + phase) * 0.10 + sin(t * 2.9 + phase) * 0.035
`

The body stays still; the head dips and lifts as if cropping grass. Not yet verified in the running
game because JT has not been copied to game/levels/JT or wired into the L1 transition.

## Integrated into the game

- Copied out/JT/JT to game/levels/JT (background + 12 sprites).
- level.json given spawns.player = [12, 0, 5], empty worms, and a 	o_l1_from_jt stair at (2, 8).
- game.gd state now includes "JT": {}.
- L1 has a 	o_jt_from_l1 stair at (-2.6, -1.4) (both uild.py source and the current L1 level.json).
- In-game screenshots: docs/JUNK_TOWN_INGAME.png, docs/JUNK_TOWN_GOATS.png.

**Known issue:** the split goat reads as a white cap on legs — the head is pitched too far down and the
body/neck proportions are placeholder. The head nod works mechanically, but the model needs an art pass
(smaller head, visible neck, longer body, shorter legs) before it looks like a goat.

Full --autotest still passes; JT loads with 819 walkable hexes.
