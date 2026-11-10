# Voice lines — The Long Cold

**Status: recorded and verified — 8 MP3s in `game/audio/voice/`.** Godot 4.3 imports all eight
(`ResourceLoader.exists` true, lengths 2.2–14.3 s). The playback hook is `_play_voice` in
`game/scripts/game.gd`; it plays `res://audio/voice/<key>.mp3` and stays silent if a line is
missing.

`ov_finish.mp3` is recorded but currently unused: `ov_finish` is a choice target, not a spoken
node. Keep it for a future beat or wire it into the Overseer's exit line.

Keep every line short — these are in-game barks, not cutscenes.

## Cast (ElevenLabs)

| Role | Voice | Direction |
|---|---|---|
| Overseer Varga | **Spuds Oxley – Grandpa** | old, dry, in control; never shouts |
| Tibor | **Flint – Deep, Raspy, and Warm** | tired maintenance dispatcher, fond of the Chief |
| Player (Chief Engineer) | **James – Husky, Engaging and Bold** | quiet, practical, not heroic |

## Lines and file names

Put the files in `game/audio/voice/`. The key is the dialogue node name.

| Key | File | Role | Text |
|---|---|---|---|
| `ov_report_3` | `ov_report_3.mp3` | Overseer | “There are no spare cores. Then we have forty-eight hours before the residential levels start to freeze. The only plant that ever cast those cores is in New Meridian. The city.” |
| `ov_report_4` | `ov_report_4.mp3` | Overseer | “Forty kilometres of frozen road and whatever else is out there. I'm sending you anyway. Junk Town first — the only roof between us and the city. Find Mara, the mechanic. She knows the road.” |
| `ov_expedition` | `ov_expedition.mp3` | Overseer | “Take what you need from stores. Tell Tibor. And Chief — the Silo stays warm only if you come back.” |
| `ov_finish` | `ov_finish.mp3` | Overseer | “Forty-eight hours, Chief. Don't waste them.” |
| `tibor_report_2` | `tibor_report_2.mp3` | Tibor | “Three medkits. Don't spend them all in one pipe gallery.” |
| `tibor_long_cold` | `tibor_long_cold.mp3` | Tibor | “Outside. Of course he did. Junk Town's the only light out there — keep to the road, and don't wave at anything that stands too still.” |
| `player_accept` | `player_accept.mp3` | Player | “I'll bring back the parts. Keep the Silo warm.” |
| `player_ready` | `player_ready.mp3` | Player | “I'll be back before the pipes freeze.” |

`ov_finish` is currently a HUD-only line; record it only if the node is given a spoken beat later.

## Technical

- MP3, mono, 44.1 kHz; trim leading/trailing silence; peak around −3 dB.
- Godot imports them on editor open (`--headless --editor --quit`).
- `_play_voice(key)` is called from `_say()` (`tibor_<node>`), `_say_overseer()` (`<node>`), and on
  the player's accept choices (`player_accept`, `player_ready`).
- Never commit API keys. Generate in the browser or with a local key outside the repo.
