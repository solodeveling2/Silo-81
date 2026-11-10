#!/usr/bin/env python3
"""sv - development supervisor for long-running jobs (Blender, Godot, Python, asset batches).

Standard library only. State lives in <repo>/.sv (or $SV_HOME). Jobs run under a detached
runner, so supervision continues when nobody is watching the terminal.

  sv run NAME [opts] -- CMD ...      start one supervised job (refuses duplicates)
  sv batch NAME MANIFEST.json [opts] run a batch; finished+verified items are skipped
  sv retry NAME                      re-run only what failed (whole job, or failed batch items)
  sv status [NAME] [--json]          concise status; also rewrites .sv/REPORT.md
  sv wait NAME|--all [--timeout S]   block until terminal; exit 0 ok, 1 failed, 2 needs you, 124 timeout
  sv watch [--until-idle]            one line per state change (for the Monitor tool / async hooks)
  sv log NAME [-n N] [--item ID]     tail a job's log
  sv kill NAME                       stop a job sv started (never touches other processes)
  sv ps                              heavy processes running WITHOUT sv (possible duplicates)
  sv ack NAME                        mark an escalation as seen by the user

run/batch options:
  --expect S     normal duration; beyond it the job is "slow" (still fine if progressing)
  --stall S      no CPU, log or output progress for S seconds = frozen   (default max(90, expect/3))
  --out PATH     expected output (repeatable; globs allowed). Must exist, be non-empty, be newer
                 than the start, and pass a format check (png/glb/json/wav/zip magic).
  --verify CMD   extra shell check run after success (exit 0 = good)
  --retries N    retry transient failures (network, OOM-kill, frozen) up to N times. Pass only for
                 idempotent commands. Deterministic errors (tracebacks in code) are escalated.
  --cwd DIR      working directory          --parallel N   batch concurrency (default 2)
  --hold         ask the Stop hook to keep the session going until this job is verified
"""
import argparse, fnmatch, glob, hashlib, json, os, re, shlex, signal, subprocess, sys, time

ROOT = os.environ.get("SV_HOME") or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".sv")
JOBS = os.path.join(ROOT, "jobs")
CLK = os.sysconf("SC_CLK_TCK")
TERMINAL = {"verified", "failed", "escalated", "killed", "done"}   # done = finished, no outputs declared
ACTIVE = {"starting", "running", "slow", "stalled", "retrying", "verifying"}

TRANSIENT = re.compile(r"Connection (reset|refused|aborted)|timed? ?out|Temporary failure|ECONNRESET|"
                       r"Remote end closed|HTTP Error 5\d\d|\b(429|502|503|504)\b|Too Many Requests|"
                       r"Resource temporarily unavailable|BrokenPipe", re.I)
DETERMINISTIC = re.compile(r"SyntaxError|NameError|AttributeError|KeyError|TypeError|ImportError|"
                           r"ModuleNotFoundError|IndentationError|FileNotFoundError|Parse Error|SCRIPT ERROR|"
                           r"Cannot infer|AssertionError|ValueError")
ERRLINE = re.compile(r"Traceback|\bERROR\b|Error:|SCRIPT ERROR|Exception|Segmentation fault|core dumped|Killed|"
                     r"MemoryError|CUDA error|FATAL", re.I)
HEAVY = re.compile(r"blender|bpy|build\.py|glb_preview|render_|package_\w+\.py|Godot|godot|tripo|export-release")


# ---------------------------------------------------------------- state helpers
def jdir(name):
    return os.path.join(JOBS, re.sub(r"[^\w.-]", "_", name))


def load(name):
    for _ in range(5):                            # a reader can race a writer's replace; retry briefly
        try:
            with open(os.path.join(jdir(name), "state.json")) as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            time.sleep(0.05)
    return None


import threading
_LOCK = threading.RLock()


def save(st):
    with _LOCK:                                   # batch worker threads share one state dict
        d = jdir(st["name"]); os.makedirs(d, exist_ok=True)
        st["updated"] = time.time()
        tmp = os.path.join(d, f"state.json.{os.getpid()}.tmp")
        with open(tmp, "w") as f:
            json.dump(st, f, indent=1)
        os.replace(tmp, os.path.join(d, "state.json"))
        write_report()


def all_jobs():
    out = []
    if os.path.isdir(JOBS):
        for n in sorted(os.listdir(JOBS)):
            try:
                with open(os.path.join(JOBS, n, "state.json")) as f:
                    out.append(json.load(f))
            except (OSError, ValueError):
                pass
    return out


def alive(pid):
    if not pid:
        return False
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


def cmdline(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return f.read().replace(b"\0", b" ").decode(errors="replace").strip()
    except OSError:
        return ""


def tree(pid):
    """pid plus all descendants."""
    kids = {}
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                with open(f"/proc/{p}/stat") as f:
                    ppid = int(f.read().rsplit(")", 1)[1].split()[1])
                kids.setdefault(ppid, []).append(int(p))
            except (OSError, ValueError, IndexError):
                pass
    out, todo = [], [pid]
    while todo:
        p = todo.pop(); out.append(p); todo += kids.get(p, [])
    return out


def cpu_and_state(pid):
    """Total CPU ticks of the process tree, and the set of process states (R, S, D, T, Z)."""
    ticks, states = 0, set()
    for p in tree(pid):
        try:
            with open(f"/proc/{p}/stat") as f:
                fields = f.read().rsplit(")", 1)[1].split()
            states.add(fields[0]); ticks += int(fields[11]) + int(fields[12])
        except (OSError, ValueError, IndexError):
            pass
    return ticks, states


def fingerprint(cmd, cwd):
    return hashlib.sha1((cwd + "\0" + cmd).encode()).hexdigest()[:12]


def tail(path, n=20):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 64 * 1024))
            return f.read().decode(errors="replace").splitlines()[-n:]
    except OSError:
        return []


def fmt_t(s):
    s = int(s)
    return f"{s // 3600}h{s % 3600 // 60:02d}m" if s >= 3600 else f"{s // 60}m{s % 60:02d}s"


# ---------------------------------------------------------------- verification
MAGIC = {".png": b"\x89PNG", ".glb": b"glTF", ".zip": b"PK", ".wav": b"RIFF", ".jpg": b"\xff\xd8", ".webp": b"RIFF",
         ".wasm": None, ".pck": b"GDPC"}


def verify_outputs(patterns, since, cwd, verify_cmd=None):
    """Return a list of problems (empty = verified)."""
    problems = []
    for pat in patterns:
        full = pat if os.path.isabs(pat) else os.path.join(cwd, pat)
        hits = glob.glob(full) if any(c in pat for c in "*?[") else ([full] if os.path.exists(full) else [])
        if not hits:
            problems.append(f"missing output {pat}"); continue
        for h in hits:
            if os.path.isdir(h):
                continue
            st = os.stat(h)
            if st.st_size == 0:
                problems.append(f"empty output {h}")
            elif st.st_mtime < since - 2:
                problems.append(f"stale output {h} (older than this run)")
            else:
                ext = os.path.splitext(h)[1].lower(); magic = MAGIC.get(ext)
                if ext == ".json":
                    try:
                        json.load(open(h))
                    except ValueError as e:
                        problems.append(f"bad json {h}: {e}")
                elif magic:
                    with open(h, "rb") as f:
                        if not f.read(len(magic)) == magic:
                            problems.append(f"bad {ext} header {h}")
    if verify_cmd and not problems:
        r = subprocess.run(verify_cmd, shell=True, cwd=cwd, capture_output=True, text=True)
        if r.returncode:
            problems.append(f"verify command failed ({r.returncode}): {(r.stdout + r.stderr).strip()[-300:]}")
    return problems


def classify(rc, log_lines):
    """('transient'|'deterministic'|'unknown', reason)."""
    text = "\n".join(log_lines)
    if rc in (-9, 137) or "Killed" in text or "MemoryError" in text:
        return "transient", "killed (likely out of memory)"
    det = DETERMINISTIC.search(text)
    if det:
        return "deterministic", f"code error: {det.group(0)}"
    tr = TRANSIENT.search(text)
    if tr:
        return "transient", f"transient: {tr.group(0)}"
    return "unknown", f"exit code {rc}"


# ---------------------------------------------------------------- the runner (detached)
def run_unit(st, unit, logpath):
    """Run one command under the watchdog. Mutates unit (dict with cmd/cwd/outputs/...). Returns final status."""
    expect, stall = st["expect"], st["stall"]
    unit.update(attempts=unit.get("attempts", 0) + 1, started=time.time(), status="running", problems=[])
    save(st)
    with open(logpath, "ab") as log:
        log.write(f"\n=== sv attempt {unit['attempts']} {time.strftime('%H:%M:%S')}: {unit['cmd']}\n".encode()); log.flush()
        p = subprocess.Popen(unit["cmd"], shell=True, cwd=unit["cwd"], stdout=log, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, start_new_session=True)
    unit["pid"] = p.pid; save(st)
    last_sig, last_prog = None, time.time()
    while p.poll() is None:
        time.sleep(3)
        ticks, states = cpu_and_state(p.pid)
        outs = []
        for pat in unit.get("outputs", []):
            full = pat if os.path.isabs(pat) else os.path.join(unit["cwd"], pat)
            for h in glob.glob(full):
                try:
                    s = os.stat(h); outs.append((h, s.st_size, s.st_mtime))
                except OSError:
                    pass
        try:
            lsize = os.path.getsize(logpath)
        except OSError:
            lsize = 0
        sig = (ticks // max(1, CLK // 2), lsize, tuple(outs))       # half-second CPU granularity
        now = time.time()
        if sig != last_sig:
            last_sig, last_prog = sig, now
        unit["cpu_s"] = round(ticks / CLK, 1); unit["log_bytes"] = lsize; unit["last_progress"] = last_prog
        # repeated identical error lines = an error loop, even if the process keeps "progressing"
        counts = {}
        recent = tail(logpath, 200)
        marks = [i for i, l in enumerate(recent) if l.startswith("=== sv attempt")]
        for line in recent[marks[-1] + 1:] if marks else recent:
            if ERRLINE.search(line):
                k = re.sub(r"\d+", "#", line.strip())[:160]; counts[k] = counts.get(k, 0) + 1
        loop = [k for k, c in counts.items() if c >= 8]
        el = now - unit["started"]
        if "T" in states:
            unit["status"], unit["note"] = "stalled", "process is stopped (SIGSTOP / state T)"
        elif now - last_prog > stall:
            unit["status"] = "stalled"
            unit["note"] = f"no CPU, log or output change for {fmt_t(now - last_prog)}" + (" (blocked on disk I/O)" if "D" in states else "")
        elif loop:
            unit["status"], unit["note"] = "stalled", f"error loop: '{loop[0][:80]}' x{counts[loop[0]]}"
        elif expect and el > expect:
            unit["status"], unit["note"] = "slow", f"over expected {fmt_t(expect)} but progressing (cpu {unit['cpu_s']}s)"
        else:
            unit["status"], unit["note"] = "running", ""
        save(st)
        if unit["status"] == "stalled":
            # frozen: kill our own process group; the retry policy below decides what happens next
            kill_group(p.pid)
            p.wait()
            unit["rc"] = "frozen"; unit["ended"] = time.time()
            return "frozen"
    unit["rc"] = p.returncode; unit["ended"] = time.time()
    return "exited"


def kill_group(pid):
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pid, sig)
        except OSError:
            pass
        for _ in range(20):
            if not alive(pid):
                return
            time.sleep(0.25)


def finish_unit(st, unit, how, logpath):
    """Decide verified / retry / failed / escalated for one unit. Returns True if it should be retried."""
    lines = tail(logpath, 80)
    if how == "frozen":
        kind, why = "transient", unit.get("note", "frozen")
    elif unit["rc"] == 0:
        unit["status"] = "verifying"; save(st)
        probs = verify_outputs(unit.get("outputs", []), unit["started"], unit["cwd"], unit.get("verify"))
        if not probs:
            unit["status"] = "verified" if unit.get("outputs") or unit.get("verify") else "done"
            unit["note"] = f"{fmt_t(unit['ended'] - unit['started'])}"
            return False
        unit["problems"] = probs
        kind, why = "unknown", "; ".join(probs)
    else:
        kind, why = classify(unit["rc"], lines)
    unit["last_error"] = why
    unit["error_tail"] = [l for l in lines if ERRLINE.search(l)][-5:] or lines[-5:]
    if kind == "transient" and unit["attempts"] <= st["retries"]:
        unit["status"], unit["note"] = "retrying", f"{why} - retry {unit['attempts']}/{st['retries']}"
        save(st)
        time.sleep(min(60, 5 * 2 ** (unit["attempts"] - 1)))
        return True
    if kind == "deterministic":
        unit["status"], unit["note"] = "escalated", f"{why} - needs a code fix, not a retry"
    elif kind == "transient":
        unit["status"], unit["note"] = "escalated", f"{why} - retries used up ({st['retries']})"
    else:
        unit["status"], unit["note"] = "failed", why
    return False


def runner(name):
    st = load(name)
    st["runner_pid"] = os.getpid(); save(st)
    d = jdir(name)
    if st["kind"] == "job":
        unit = st["unit"]
        while True:
            how = run_unit(st, unit, os.path.join(d, "log"))
            if not finish_unit(st, unit, how, os.path.join(d, "log")):
                break
        st["status"] = unit["status"]
    else:
        items = st["items"]
        todo = [i for i in items if i["status"] not in ("verified", "done")]
        running = {}
        import threading

        def work(it):
            lp = os.path.join(d, "items", re.sub(r"[^\w.-]", "_", it["id"]) + ".log")
            while True:
                how = run_unit(st, it, lp)
                if not finish_unit(st, it, how, lp):
                    break
            save(st)
        lock_q = list(todo)
        threads = []
        while lock_q or any(t.is_alive() for t in threads):
            threads = [t for t in threads if t.is_alive()]
            while lock_q and len(threads) < st["parallel"]:
                it = lock_q.pop(0)
                t = threading.Thread(target=work, args=(it,), daemon=True); t.start(); threads.append(t)
            st["status"] = "running"; save(st)
            time.sleep(2)
        bad = [i for i in items if i["status"] not in ("verified", "done")]
        esc = [i for i in bad if i["status"] == "escalated"]
        st["status"] = "verified" if not bad else ("escalated" if esc else "failed")
        st["note"] = f"{len(items) - len(bad)}/{len(items)} verified" + (f"; failed: {', '.join(i['id'] for i in bad)}" if bad else "")
    st["ended"] = time.time(); st["runner_pid"] = None
    if st["status"] == "escalated":
        with open(os.path.join(ROOT, "ESCALATIONS.md"), "a") as f:
            f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} **{name}**: {summary_note(st)}\n")
    save(st)


def summary_note(st):
    if st["kind"] == "job":
        return st["unit"].get("note", "")
    return st.get("note", "")


# ---------------------------------------------------------------- commands
def find_duplicate(cmd, cwd, name):
    fp = fingerprint(cmd, cwd)
    for j in all_jobs():
        if j["name"] == name and j.get("runner_pid") and alive(j["runner_pid"]):
            return f"job '{name}' is already running (runner pid {j['runner_pid']}). Use: sv wait {name}"
        if j.get("fp") == fp and j.get("runner_pid") and alive(j["runner_pid"]):
            return f"the same command is already running as job '{j['name']}'. Use: sv wait {j['name']}"
    for pid, cl in untracked():
        if cmd_core(cmd) and cmd_core(cmd) in cl:
            return f"an identical process is already running outside sv (pid {pid}): {cl[:120]}"
    return None


def cmd_core(cmd):
    """The part of a command that identifies the work (script + args), ignoring shell plumbing."""
    segs = [s for s in re.split(r"\s*(?:\|\||&&|;|\||\n)\s*", cmd.strip()) if s]
    seg = next((s for s in segs if HEAVY.search(s)), segs[0] if segs else "")
    c = re.split(r"\s*(?:\d?>>?|&>)\s*", seg)[0].rstrip("& ")
    try:
        toks = shlex.split(c) if c else []
    except ValueError:
        toks = c.split()
    toks = [t for t in toks if not t.startswith("-I") and t not in ("nohup", "timeout", "python3", "python", "exec")]
    toks = [t for t in toks if not re.fullmatch(r"\d+[smh]?", t)]
    return " ".join(toks)


def untracked():
    """Heavy processes not started by an sv runner (and not their descendants)."""
    ours = set()
    for j in all_jobs():
        for pid in [j.get("runner_pid")] + [u.get("pid") for u in ([j["unit"]] if j["kind"] == "job" else j["items"])]:
            if pid and alive(pid):
                ours.update(tree(pid))
    me = os.getpid(); out = []
    for p in os.listdir("/proc"):
        if p.isdigit() and int(p) not in ours and int(p) != me:
            cl = cmdline(int(p))
            if cl and HEAVY.search(cl) and "sv.py" not in cl and "hooks.py" not in cl:
                out.append((int(p), cl))
    return out


def spawn_runner(name):
    subprocess.Popen([sys.executable, os.path.abspath(__file__), "_runner", name], start_new_session=True,
                     stdout=open(os.path.join(jdir(name), "runner.log"), "ab"), stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, cwd=jdir(name))


def cmd_run(a):
    cmd = " ".join(shlex.quote(x) for x in a.cmd) if len(a.cmd) > 1 else a.cmd[0]
    cwd = os.path.abspath(a.cwd or os.getcwd())
    dup = find_duplicate(cmd, cwd, a.name)
    if dup:
        print("sv: refused -", dup); return 3
    os.makedirs(jdir(a.name), exist_ok=True)
    stall = a.stall or max(90, (a.expect or 0) // 3)
    st = dict(name=a.name, kind="job", status="starting", created=time.time(), expect=a.expect, stall=stall,
              retries=a.retries, hold=a.hold, fp=fingerprint(cmd, cwd), acked=False,
              unit=dict(id=a.name, cmd=cmd, cwd=cwd, outputs=a.out, verify=a.verify, status="starting"))
    open(os.path.join(jdir(a.name), "log"), "w").close()
    save(st); spawn_runner(a.name)
    print(f"sv: started '{a.name}' (expect {fmt_t(a.expect) if a.expect else '?'}, stall after {fmt_t(stall)}). "
          f"Check: sv status {a.name} | sv wait {a.name}")
    return 0


def cmd_batch(a):
    man = json.load(open(a.manifest))
    cwd = os.path.abspath(a.cwd or man.get("cwd") or os.path.dirname(os.path.abspath(a.manifest)))
    old = load(a.name)
    if old and old.get("runner_pid") and alive(old["runner_pid"]):
        print(f"sv: refused - batch '{a.name}' is already running. Use: sv wait {a.name}"); return 3
    prev = {i["id"]: i for i in (old or {}).get("items", [])}
    items = []
    for it in man["items"]:
        p = prev.get(it["id"])
        u = dict(id=it["id"], cmd=it["cmd"] if isinstance(it["cmd"], str) else " ".join(shlex.quote(x) for x in it["cmd"]),
                 cwd=os.path.abspath(os.path.join(cwd, it.get("cwd", "."))), outputs=it.get("outputs", []),
                 verify=it.get("verify"), status="pending")
        if p and p["status"] in ("verified", "done") and p["cmd"] == u["cmd"] and not a.force:
            if not verify_outputs(u["outputs"], 0, u["cwd"], None):     # still on disk -> reuse
                u.update(status=p["status"], note="reused (verified earlier)", attempts=p.get("attempts", 1))
        items.append(u)
    os.makedirs(os.path.join(jdir(a.name), "items"), exist_ok=True)
    expect = a.expect or man.get("expect", 0)
    st = dict(name=a.name, kind="batch", status="starting", created=time.time(), expect=expect,
              stall=a.stall or man.get("stall") or max(90, expect // 3), retries=a.retries if a.retries is not None else man.get("retries", 0),
              parallel=a.parallel or man.get("parallel", 2), hold=a.hold, fp=None, acked=False, items=items,
              manifest=os.path.abspath(a.manifest), cwd=cwd)
    save(st); spawn_runner(a.name)
    skip = sum(1 for i in items if i["status"] in ("verified", "done"))
    print(f"sv: batch '{a.name}' started: {len(items) - skip} to run, {skip} reused. Check: sv status {a.name}")
    return 0


def cmd_retry(a):
    st = load(a.name)
    if not st:
        print("sv: no such job"); return 1
    if st.get("runner_pid") and alive(st["runner_pid"]):
        print("sv: refused - still running"); return 3
    units = [st["unit"]] if st["kind"] == "job" else st["items"]
    n = 0
    for u in units:
        if u["status"] not in ("verified", "done"):
            u.update(status="pending", attempts=0, note="manual retry"); n += 1
    if not n:
        print("sv: nothing failed - nothing to retry"); return 0
    st.update(status="starting", acked=False); save(st); spawn_runner(a.name)
    print(f"sv: retrying {n} unit(s) of '{a.name}'"); return 0


def line_for(j, now=None):
    now = now or time.time()
    if j["kind"] == "job":
        u = j["unit"]; s = u.get("status", j["status"])
        if s in ACTIVE or s == "pending":
            el = now - u.get("started", j["created"])
            extra = f"{fmt_t(el)}" + (f"/{fmt_t(j['expect'])}" if j.get("expect") else "") + f", cpu {u.get('cpu_s', 0)}s"
        else:
            extra = ""
        note = u.get("note", "")
        return f"{j['name']:<22} {s:<10} {extra} {note}".rstrip()
    items = j["items"]; c = {}
    for i in items:
        c[i["status"]] = c.get(i["status"], 0) + 1
    parts = ", ".join(f"{v} {k}" for k, v in sorted(c.items()))
    bad = [i for i in items if i["status"] in ("failed", "escalated", "stalled")]
    return f"{j['name']:<22} {j['status']:<10} [{parts}]" + (f" problems: {', '.join(i['id'] + ': ' + i.get('note', '')[:60] for i in bad[:3])}" if bad else "")


def fix_orphans():
    """A runner that died without finishing (container restart, OOM) leaves an ACTIVE state behind."""
    for j in all_jobs():
        if j["status"] in ACTIVE | {"starting"} and j.get("runner_pid") and not alive(j["runner_pid"]) \
                and time.time() - j.get("updated", 0) > 10:
            j["status"] = "failed"
            msg = "supervisor runner disappeared (session/container restart?) - safe to `sv retry`"
            if j["kind"] == "job":
                j["unit"]["status"] = "failed"; j["unit"]["note"] = msg
            else:
                j["note"] = msg
                for i in j["items"]:
                    if i["status"] not in TERMINAL:
                        i["status"] = "failed"; i["note"] = msg
            save(j)


def write_report():
    os.makedirs(ROOT, exist_ok=True)
    js = all_jobs(); now = time.time()
    act = [j for j in js if j["status"] not in TERMINAL]
    rec = [j for j in js if j["status"] in TERMINAL and now - j.get("updated", 0) < 6 * 3600]
    esc = [j for j in js if j["status"] == "escalated" and not j.get("acked")]
    L = [f"# sv report  ({time.strftime('%Y-%m-%d %H:%M:%S')})", ""]
    L += ["## Active"] + ([f"- {line_for(j, now)}" for j in act] or ["- none"])
    L += ["", "## Needs a decision"] + ([f"- **{j['name']}**: {summary_note(j)}" for j in esc] or ["- none"])
    L += ["", "## Finished (last 6 h)"] + ([f"- {line_for(j, now)}" for j in rec] or ["- none"])
    tmp = os.path.join(ROOT, f"REPORT.md.{os.getpid()}.tmp")
    with open(tmp, "w") as f:
        f.write("\n".join(L) + "\n")
    os.replace(tmp, os.path.join(ROOT, "REPORT.md"))


def cmd_status(a):
    fix_orphans()
    js = [load(a.name)] if a.name else all_jobs()
    js = [j for j in js if j]
    if a.json:
        print(json.dumps(js, indent=1)); return 0
    if not js:
        print("sv: no jobs"); return 0
    for j in js:
        if not a.name and j["status"] in TERMINAL and time.time() - j.get("updated", 0) > 6 * 3600:
            continue
        print(line_for(j))
        if a.name:
            units = [j["unit"]] if j["kind"] == "job" else j["items"]
            for u in units:
                if u.get("problems") or u.get("error_tail"):
                    print(f"  [{u['id']}] " + "; ".join(u.get("problems") or []))
                    for l in u.get("error_tail", [])[-3:]:
                        print("    | " + l[:200])
    unt = untracked()
    if unt:
        print(f"untracked heavy processes: {len(unt)} (sv ps)")
    write_report(); return 0


def cmd_wait(a):
    names = [j["name"] for j in all_jobs() if j["status"] not in TERMINAL] if a.all else [a.name]
    t0 = time.time(); seen = {}
    while True:
        fix_orphans()
        js = [load(n) for n in names]
        for j in js:
            if j:
                u = j["unit"] if j["kind"] == "job" else j
                key = (j["status"], u.get("status"), u.get("note", ""),
                       tuple(i["status"] for i in j.get("items", [])))
                last = seen.get(j["name"])
                if last is None or last[0] != key or time.time() - last[1] > 60:   # changes, plus a heartbeat a minute
                    print(time.strftime("%H:%M:%S"), line_for(j), flush=True); seen[j["name"]] = (key, time.time())
        if all((j is None and not os.path.isdir(jdir(n))) or (j and j["status"] in TERMINAL) for n, j in zip(names, js)):
            st = [j["status"] for j in js if j]
            return 2 if "escalated" in st else 1 if ("failed" in st or "killed" in st) else 0
        if a.timeout and time.time() - t0 > a.timeout:
            return 124
        time.sleep(2)


def cmd_watch(a):
    """Event stream: one line per state change. --until-idle exits when nothing is active."""
    seen = {}
    t0 = time.time()
    while True:
        fix_orphans()
        js = all_jobs()
        for j in js:
            key = (j["status"], summary_note(j) if j["status"] in TERMINAL | {"stalled", "slow", "retrying"} else "")
            if j["name"] in seen and seen[j["name"]] != key or (j["name"] not in seen and j["status"] not in TERMINAL):
                print(f"[sv] {line_for(j)}", flush=True)
            seen[j["name"]] = key
        if a.until_idle and not any(j["status"] not in TERMINAL for j in js) and time.time() - t0 > 3:
            return 0
        if a.max and time.time() - t0 > a.max:
            return 124
        time.sleep(3)


def cmd_log(a):
    d = jdir(a.name)
    p = os.path.join(d, "items", re.sub(r"[^\w.-]", "_", a.item) + ".log") if a.item else os.path.join(d, "log")
    print("\n".join(tail(p, a.n))); return 0


def cmd_kill(a):
    st = load(a.name)
    if not st:
        print("sv: no such job"); return 1
    for pid in [st.get("runner_pid")] + [u.get("pid") for u in ([st["unit"]] if st["kind"] == "job" else st["items"])]:
        if pid and alive(pid):
            kill_group(pid)
    units = [st["unit"]] if st["kind"] == "job" else st["items"]
    for u in units:
        if u["status"] not in TERMINAL:
            u["status"], u["note"] = "killed", "stopped by sv kill"
    st.update(status="killed", runner_pid=None); save(st)
    print(f"sv: killed '{a.name}'"); return 0


def cmd_ps(a):
    u = untracked()
    for pid, cl in u:
        try:
            t = time.time() - os.stat(f"/proc/{pid}").st_mtime
        except OSError:
            t = 0
        print(f"{pid:>7} {cl[:150]}")
    if not u:
        print("sv: no untracked heavy processes")
    return 0


def cmd_ack(a):
    st = load(a.name)
    if st:
        st["acked"] = True; save(st)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sv", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd_name", required=True)

    def common(p):
        p.add_argument("--expect", type=int, default=0); p.add_argument("--stall", type=int, default=0)
        p.add_argument("--retries", type=int, default=None); p.add_argument("--cwd"); p.add_argument("--hold", action="store_true")
    r = sub.add_parser("run"); r.add_argument("name"); common(r)
    r.add_argument("--out", action="append", default=[]); r.add_argument("--verify"); r.add_argument("cmd", nargs="*")
    b = sub.add_parser("batch"); b.add_argument("name"); b.add_argument("manifest"); common(b)
    b.add_argument("--parallel", type=int, default=0); b.add_argument("--force", action="store_true")
    for n in ("retry", "kill", "ack"):
        sub.add_parser(n).add_argument("name")
    s = sub.add_parser("status"); s.add_argument("name", nargs="?"); s.add_argument("--json", action="store_true")
    w = sub.add_parser("wait"); w.add_argument("name", nargs="?"); w.add_argument("--all", action="store_true"); w.add_argument("--timeout", type=int, default=540)
    wa = sub.add_parser("watch"); wa.add_argument("--until-idle", action="store_true"); wa.add_argument("--max", type=int, default=0)
    l = sub.add_parser("log"); l.add_argument("name"); l.add_argument("-n", type=int, default=40); l.add_argument("--item")
    sub.add_parser("ps"); sub.add_parser("report")
    sub.add_parser("_runner").add_argument("name")
    argv = list(sys.argv[1:] if argv is None else argv)
    rest = []
    if argv and argv[0] == "run" and "--" in argv:
        i = argv.index("--"); argv, rest = argv[:i], argv[i + 1:]
    a = ap.parse_args(argv)
    if a.cmd_name == "run":
        a.cmd = rest or a.cmd
    os.makedirs(JOBS, exist_ok=True)
    if a.cmd_name == "run":
        if not a.cmd:
            ap.error("run needs a command after --")
        a.retries = a.retries or 0
        return cmd_run(a)
    if a.cmd_name == "batch":
        return cmd_batch(a)
    if a.cmd_name == "_runner":
        return runner(a.name)
    if a.cmd_name == "report":
        fix_orphans(); write_report(); print(open(os.path.join(ROOT, "REPORT.md")).read()); return 0
    return {"retry": cmd_retry, "kill": cmd_kill, "ack": cmd_ack, "status": cmd_status, "wait": cmd_wait,
            "watch": cmd_watch, "log": cmd_log, "ps": cmd_ps}[a.cmd_name](a)


if __name__ == "__main__":
    sys.exit(main())
