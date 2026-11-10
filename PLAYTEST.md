# Playtesting Silo 81

Double-click **`PLAYTEST.bat`** (or the desktop shortcut **Playtest Silo 81**) and pick a number.
Each option opens the game directly at that level — no intro, no walking through the whole silo.

| Key | Destination |
|---|---|
| 1 | Full game from the Level 2 intro |
| 2 | Level 3 pipe gallery, by the worms |
| 3 | Level 4 Command |
| 4 | Heating Control Room (L4E) |
| 5 | Sub-Level 4 (L5) |
| 6 | Level 1 Surface Transit Depot |
| 7 | Junk Town gate yard |
| 8 | Junk Town animal pen |
| 9 | Junk Town with god mode (999 HP) |
| 10 | Level 2 West — commons, kitchen, clinic, school |
| 11 | Administration Office, next to the Overseer |
| 0 | Headless autotest |

## Command line

The game now understands:

```
--start=LEVEL[,u,v]   load a level immediately, optionally at a plan position
--god                 set max HP to 999 and heal to full
```

Examples:

```
Godot_v4.3-stable_win64.exe --path game -- --start=JT,12,0
Godot_v4.3-stable_win64.exe --path game -- --start=L4W,-27.8,7.2
Godot_v4.3-stable_win64.exe --path game -- --start=JT,19,-4 --god
```

Screenshots still work without opening a window in front:

```
Godot_v4.3-stable_win64.exe --path game --position -3000,-3000 -- --shot=out.png,JT,12,0
```

Autotest:

```
Godot_v4.3-stable_win64.exe --headless --fixed-fps 60 --path game -- --autotest
```

## Adding an option

Edit `PLAYTEST.bat`, add a line to the menu and a matching `if /i "%pick%"=="N"` that runs:

```
start "" "%GODOT%" --path "%GAME%" -- --start=LEVEL,u,v
```

Use `Vector2.INF` behaviour by omitting `u,v` (the level's own `spawns.player` is used).

Godot path is set at the top of the batch file:

```
set "GODOT=D:\Godot4.3\Godot_v4.3-stable_win64.exe"
```

Change it if Godot moves.
