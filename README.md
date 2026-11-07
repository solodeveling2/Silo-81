# Silo 81

A 2D isometric post-apocalyptic RPG in the spirit of Fallout 1 and 2, built in Godot 4.3. Exploration is real time and combat is turn-based on a hex grid. The art is pre-rendered from 3D in a toon style.

This repository holds the first playable slice and the tools that build its art.

## The playable slice

You wake in your room on Level 2. Mira calls on the intercom: pressure on the general heating circuit is dropping. You take the welding kit from your toolbox and go down to Level 3. There, blind toothed worms are chewing through the heating pipes; one still has its teeth in the burst flow pipe, the lowest on the wall. You fight them and weld the burst pipe.

Room 2-D at the cold end of the corridor is locked. You can pick the lock or force it with enough Strength. Its contents are still to be designed.

### Controls

| Input | Action |
|---|---|
| Left click | Move, use an object, or shoot a hostile |
| 1 to 5, or click the bar | Tokarev, Overwatch, Inspect, Welding kit, Medkit |
| Right click / Esc | Cancel the selected action |
| Space / End Turn | End your turn in combat |
| Mouse wheel | Zoom |

Combat gives you 8 action points (AP) per turn:

| Action | Cost |
|---|---|
| Move one hex | 1 AP |
| Shoot | 3 AP |
| Pick a lock | 2 AP |
| Force a door | 4 AP |
| Weld | 4 AP |
| Medkit | 2 AP |

Overwatch spends what is left of your AP on reaction shots at anything that moves. All of these numbers are placeholders, to be balanced later.

## Running it

1. Install [Godot 4.3](https://godotengine.org/download/archive/4.3-stable/).
2. Open `game/project.godot` and press Play.

To build for the browser, export with the `Web` preset (no-threads template), then run:

```
python3 tools/web/package_web.py build/web site
```

The script repacks the export for hosts that limit file size. The engine is gzipped and the game pack is split into parts, and a small loader rebuilds both in the browser.

To play the whole mission automatically and print a log:

```
godot --headless --fixed-fps 60 --path game -- --autotest
```

## Layout

```
game/                      Godot project
  scripts/                 game.gd (rules, turns, AI), level.gd (map, hexes, doors),
                           actor.gd (sprites, slide-free movement), hud.gd (UI), hex.gd (coordinates)
  characters/              sprite sheets + character.json (player, pipe worm)
  levels/L2, L2W, L3, L4W  pre-rendered background, prop and door sprites, level.json
tools/blender/             art pipeline (Blender 5.2 as the bpy Python module)
  build.py, kit.py         build a level from its plan and render background + sorted sprites
  worm.py, worm_pose.py    procedural pipe worm, animated from spine functions
  latch.py                 solves the chewing worm's pose so its mouth sits on the burst pipe
  render_character.py      render a rigged GLB into 6 hex directions
  render_aim.py, package_fire.py   the aimed firing clips, muzzle positions and aim data
  retarget.py, build_attack.py   pistol animations retargeted from Quaternius (CC0)
tools/web/                 web packaging and a headless browser test
source/models/             player GLBs (Tripo export, and with retargeted pistol clips)
art/spritecook_pack_v0.2/  the earlier SpriteCook asset pack
art/concepts/              character concept art (Nano Banana 2.1 via Gemini)
```

### Rebuilding the art

```
python3 -I tools/blender/build.py L2 out    # then copy out/L2 to game/levels/L2
python3 -I tools/blender/build.py L3 out
python3 -I tools/blender/build.py L2W out   # Level 2 west: commons, kitchen, clinic, school, Archive
python3 -I tools/blender/build.py L4W out   # Level 4 west: Council, Varga, valve gallery, Engineering
python3 -I tools/blender/latch.py              # pose of the worm latched onto the burst pipe -> latch.json
python3 -I tools/blender/render_aim.py source/models/player_male_v2.glb aim_out
python3 tools/blender/package_fire.py aim_out game/characters/player_male
python3 -I tools/blender/worm.py worm_out && python3 tools/blender/package_worm.py worm_out
```

## How it is drawn

Everything uses one camera: orthographic, 30 degrees above the ground (2:1 isometric), at 165 px per metre.

- **Walls.** Interior walls are cut down to stubs, dollhouse style, so rooms stay readable. Only the outer back walls stand full height.
- **Draw order.** Props, doors and characters are separate sprites, sorted by their footprint.
- **Hexes.** A hex is 0.64 m: exactly 14 frames of the walk cycle.
- **Aiming.** Every character records its height and where to hit it (body, head), measured on the 3D model. The shot is rendered at six gun angles, from 60 degrees down to 40 up, and the game picks the one that lines up with the target, so the pistol points down at a worm on the floor and up at anything taller. The tracer starts at the muzzle measured on the firing frame.
- **No foot sliding.** Characters move by the stride measured in Blender for each animation frame, so their feet don't slide.

## Credits and licences

- Fonts: Allerta Stencil and Oswald (SIL Open Font License), Permanent Marker (Apache 2.0), from Google Fonts.
- Pistol animations: Quaternius Universal Animation Library (CC0).
- Player model: generated with Tripo.
