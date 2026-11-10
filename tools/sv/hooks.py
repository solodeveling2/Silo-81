#!/usr/bin/env python3
"""Claude Code hook handlers for the sv supervisor. One script, one subcommand per hook event.

  session-start   adds a short "what is running / what failed" note to the new session's context
  pre-bash        blocks a Bash command that would start a second copy of work already running
  post-bash       after a command is moved to the background: a reminder that it is still running
                  and how to watch it, so it is neither forgotten nor started again
  rewake          (async, asyncRewake) waits for jobs started by `sv run` / `sv batch` and wakes
                  Claude with the result when they finish, fail or need a decision
  stop            bounded: keeps the session going only while a job started with --hold is still
                  active or unverified, at most 3 times in a row (not an endless Ralph loop)

Every handler fails open: any internal error exits 0 so a hook bug never blocks real work.
"""
import json, os, re, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv  # noqa: E402

MAX_STOP_BLOCKS = 3


def read_input():
    try:
        return json.load(sys.stdin)
    except ValueError:
        return {}


def emit(obj):
    print(json.dumps(obj)); sys.exit(0)


def jobs_summary(limit=8):
    sv.fix_orphans()
    js = sv.all_jobs(); now = time.time()
    act = [j for j in js if j["status"] not in sv.TERMINAL]
    bad = [j for j in js if j["status"] in ("failed", "escalated") and not j.get("acked") and now - j.get("updated", 0) < 24 * 3600]
    lines = []
    if act:
        lines.append("Supervised jobs still running: " + "; ".join(sv.line_for(j) for j in act[:limit]))
    if bad:
        lines.append("Supervised jobs that failed or need a decision: " + "; ".join(sv.line_for(j) for j in bad[:limit]))
    unt = sv.untracked()
    if unt:
        lines.append(f"{len(unt)} heavy process(es) running outside sv: " + "; ".join(f"pid {p}: {c[:80]}" for p, c in unt[:4]))
    return lines


def session_start(inp):
    lines = jobs_summary()
    sv_path = os.path.abspath(sv.__file__)
    base = (f"This project has a job supervisor at {sv_path} (report: {os.path.join(sv.ROOT, 'REPORT.md')}). "
            "Long Blender/Godot/Python/asset jobs are started with `python3 tools/sv/sv.py run NAME --expect S --out FILE -- CMD` "
            "or `sv batch`, checked with `sv status` / `sv wait`, and failed batch items re-run with `sv retry`.")
    emit({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "\n".join([base] + lines)}})


def pre_bash(inp):
    cmd = (inp.get("tool_input") or {}).get("command", "")
    if not cmd or "sv.py" in cmd or not sv.HEAVY.search(cmd):
        sys.exit(0)
    core = sv.cmd_core(cmd)
    if not core:
        sys.exit(0)
    for pid, cl in sv.untracked():
        if core in cl:
            emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                  "permissionDecisionReason": f"The same work is already running (pid {pid}: {cl[:140]}). "
                  "Not starting a duplicate. Wait for it (e.g. a foreground `until ! kill -0 PID; do sleep 5; done`) "
                  "or inspect it with `python3 tools/sv/sv.py ps`."}})
    for j in sv.all_jobs():
        if j["status"] in sv.TERMINAL:
            continue
        units = [j["unit"]] if j["kind"] == "job" else j["items"]
        for u in units:
            if u.get("status") not in sv.TERMINAL and core and core in sv.cmd_core(u["cmd"]):
                emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                      "permissionDecisionReason": f"This is already running as supervised job '{j['name']}' ({u['status']}). "
                      f"Use `python3 tools/sv/sv.py wait {j['name']}` instead of starting it again."}})
    sys.exit(0)


def post_bash(inp):
    resp = json.dumps(inp.get("tool_response", ""))
    if re.search(r"moved to the background|running in background|background with ID", resp, re.I):
        m = re.search(r"Output is being written to: ([^\s\"\\]+)", resp)
        ctx = ("That command is now a background task and is still running. Do not start it again. "
               + (f"Its output file is {m.group(1)}. " if m else "")
               + "Check progress by reading that file or with `python3 tools/sv/sv.py ps`; "
               "for future long jobs prefer `sv run` so stalls, crashes and outputs are supervised.")
        emit({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": ctx}})
    sys.exit(0)


def rewake(inp):
    """asyncRewake: runs in the background after `sv run`/`sv batch`; exit 2 wakes Claude with stderr."""
    cmd = (inp.get("tool_input") or {}).get("command", "")
    m = re.search(r"sv\.py\s+(run|batch|retry)\s+(\S+)", cmd)
    if not m:
        sys.exit(0)
    name = m.group(2); t0 = time.time(); last = None
    while time.time() - t0 < 4 * 3600:
        sv.fix_orphans()
        j = sv.load(name)
        if not j:
            sys.exit(0)
        if j["status"] in sv.TERMINAL:
            msg = f"[sv] job finished: {sv.line_for(j)}"
            if j["status"] in ("failed", "escalated"):
                msg += f"\nDetails: python3 tools/sv/sv.py status {name}"
            print(msg, file=sys.stderr); sys.exit(2)
        st = j["status"] if j["kind"] == "batch" else j["unit"]["status"]
        if st == "stalled" and last != "stalled":
            print(f"[sv] job stalled: {sv.line_for(j)}", file=sys.stderr); sys.exit(2)
        last = st
        time.sleep(5)
    sys.exit(0)


def stop(inp):
    """Bounded continuation: a fresh stop (stop_hook_active false) starts a new count of 3."""
    js = [j for j in sv.all_jobs() if j.get("hold")]
    pending = [j for j in js if j["status"] not in sv.TERMINAL or j["status"] == "failed" and not j.get("acked")]
    counter = os.path.join(sv.ROOT, f"stop_blocks_{inp.get('session_id', 'x')}")
    n = int(open(counter).read()) if inp.get("stop_hook_active") and os.path.exists(counter) else 0
    if not pending or n >= MAX_STOP_BLOCKS:
        sys.exit(0)
    with open(counter, "w") as f:
        f.write(str(n + 1))
    reason = ("Supervised jobs marked --hold are not finished and verified yet: "
              + "; ".join(sv.line_for(j) for j in pending)
              + f". Wait with `python3 tools/sv/sv.py wait {pending[0]['name']}` (it returns within 9 minutes), "
              "retry failed items with `sv retry`, or report the problem to the user. "
              f"(Stop hook {n + 1}/{MAX_STOP_BLOCKS}; it will not block again after that.)")
    emit({"decision": "block", "reason": reason})


if __name__ == "__main__":
    ev = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        inp = read_input()
        {"session-start": session_start, "pre-bash": pre_bash, "post-bash": post_bash,
         "rewake": rewake, "stop": stop}[ev](inp)
    except SystemExit:
        raise
    except Exception as e:  # fail open
        print(f"sv hook {ev} error (ignored): {e}", file=sys.stderr)
        sys.exit(0)
