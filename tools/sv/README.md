# sv: development supervisor

`sv` supervises long-running work in this project, such as Blender builds, previews, Godot imports and exports, packaging and asset batches. It uses only Python's standard library and Claude Code's built-in hooks, with no plugins and no extra dependencies.

```
python3 tools/sv/sv.py run build_L2 --expect 600 --stall 180 --retries 1 \
        --cwd level --out out/L2/level.json --out out/L2/bg.png -- python3 -I build.py L2 out
python3 tools/sv/sv.py wait build_L2        # blocks at most 9 min; exit 0 ok / 1 failed / 2 needs you / 124 still going
python3 tools/sv/sv.py status               # one line per job; also rewrites .sv/REPORT.md
python3 tools/sv/sv.py batch previews m.json   # many assets; verified ones are reused on resubmit
python3 tools/sv/sv.py retry previews       # re-runs only the failed items
python3 tools/sv/sv.py ps                   # heavy processes running outside sv
```

## What it decides for you

| Situation | How it is detected | What sv does |
|---|---|---|
| Slow but healthy | past `--expect`, but CPU time, log size or output files still changing | `slow`, keeps waiting |
| Frozen | no CPU, log or output change for `--stall` seconds, or process state `T` | kills its own process group, then retries if `--retries` allows, else escalates |
| Error loop | same error line (numbers ignored) 8+ times in one attempt | same as frozen |
| Transient failure | OOM kill (137/-9), connection reset, timeouts, HTTP 429/5xx | retries with backoff, up to `--retries` |
| Code bug | traceback with KeyError / NameError / SyntaxError / SCRIPT ERROR ... | **escalates**: never retried, needs a fix |
| Exit 0 but bad output | `--out` missing, empty, older than the run, bad PNG/GLB/JSON/WAV/ZIP/PCK header, `--verify` fails | `failed` |
| Duplicate start | same job name, same command+cwd, or an identical process outside sv | refuses (exit 3) |
| Supervisor itself died | runner pid gone while the job is still marked active | `failed`, safe to `sv retry` |

`sv` never deletes files and never kills a process it did not start. Anything that needs a design decision or a destructive action is set to `escalated`. It is listed under "Needs a decision" in `.sv/REPORT.md` and appended to `.sv/ESCALATIONS.md`. `sv ack NAME` marks it as seen.

Only pass `--retries` for idempotent commands, meaning ones that rewrite their outputs from scratch. Paid generation steps such as Tripo or Gemini are not idempotent: run them with `--retries 0` so a failure is reported instead of paid for twice.

## Batch manifest

```json
{"parallel": 2, "expect": 150, "stall": 120, "retries": 1,
 "items": [{"id": "chair", "cmd": "python3 -I glb_preview.py chair.png chair.glb", "cwd": "level",
            "outputs": ["chair.png"], "verify": "optional shell check"}]}
```

## Claude Code hooks (`.claude/settings.json`, installed by `tools/sv/install.py`)

| Hook | Behaviour |
|---|---|
| SessionStart | Adds a short status of running, failed and escalated jobs to the new session, so a resumed session never re-runs live work. |
| PreToolUse (Bash) | Denies a Bash command that would start a second copy of a heavy job (Blender, build.py, previews, Godot export) that is already running, inside or outside sv. |
| PostToolUse (Bash) | When a command is moved to the background, adds a reminder that it is still running and names its output file. |
| PostToolUse, async + `asyncRewake` | After `sv run`/`sv batch`/`sv retry`, waits in the background and wakes Claude when the job finishes, stalls, fails or escalates. |
| Stop | Only for jobs started with `--hold`. Keeps the session going until they are verified, at most 3 times in a row. |

Every hook fails open: an internal error exits 0 and never blocks work.

`python3 tools/sv/install.py --user` installs the same hooks with absolute paths into `~/.claude/settings.json`, for sessions that start outside the repo. `--uninstall` removes only sv's entries, and a `.bak` copy is kept.

### Why not the Ralph Wiggum plugin

Ralph is a Stop hook that feeds the same prompt back until a completion phrase appears. That is good for long unattended iteration, but it is unbounded by default, costs a full turn per loop, needs `jq`, and checks text rather than files. sv borrows only the Stop-hook idea and narrows it: it holds only for jobs flagged `--hold`, it checks verified outputs rather than a phrase, and it stops after 3 continuations.

For live event streams during one turn, the built-in **Monitor** tool works with `sv watch`. It prints one line per state change, and `--until-idle` makes it exit when nothing is running:

```
Monitor: python3 tools/sv/sv.py watch --until-idle
```

## Tests

`python3 tools/sv/test_sv.py` runs 18 scenarios (about 1 minute) in a temporary `SV_HOME`. They cover verification, slow vs. frozen, frozen-then-retry, code errors not retried, transient errors retried, missing and stale outputs, error loops, duplicate refusal, batch partial retry and reuse, and every hook.
