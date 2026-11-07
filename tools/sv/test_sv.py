#!/usr/bin/env python3
"""Scenario tests for sv: python3 tools/sv/test_sv.py   (about 1-2 minutes, uses a temp SV_HOME)."""
import json, os, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
SV = [sys.executable, os.path.join(HERE, "sv.py")]
HOME = tempfile.mkdtemp(prefix="svtest_")
W = os.path.join(HOME, "work"); os.makedirs(W)
ENV = dict(os.environ, SV_HOME=os.path.join(HOME, "state"))
PY = sys.executable
fails = []


def sv(*a, inp=None):
    return subprocess.run(SV + list(a), env=ENV, capture_output=True, text=True, cwd=W)


def state(n):
    return json.load(open(os.path.join(ENV["SV_HOME"], "jobs", n, "state.json")))


def wait(n, t=60):
    r = sv("wait", n, "--timeout", str(t)); return r.returncode, state(n)


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {info}"))
    if not cond:
        fails.append(name)


def script(name, body):
    p = os.path.join(W, name); open(p, "w").write(body); return p


# 1 ok + verified png
script("ok.py", "import time;time.sleep(1);open('a.png','wb').write(b'\\x89PNG....')\n")
sv("run", "ok", "--expect", "10", "--out", "a.png", "--", PY, "ok.py")
rc, s = wait("ok"); check("ok job verified", rc == 0 and s["unit"]["status"] == "verified", s["unit"])

# 2 slow but progressing (busy CPU past --expect, no stall)
script("slow.py", "import time\nt=time.time()\nwhile time.time()-t<9: pass\nopen('s.json','w').write('{}')\n")
sv("run", "slow", "--expect", "2", "--stall", "5", "--out", "s.json", "--", PY, "slow.py")
time.sleep(5.5); mid = state("slow")["unit"]["status"]
rc, s = wait("slow"); check("slow-but-progressing is 'slow', then verified", mid == "slow" and s["unit"]["status"] == "verified", (mid, s["unit"]))

# 3 frozen process, no retries -> killed and escalated
sv("run", "frozen", "--stall", "4", "--", "sleep", "60")
rc, s = wait("frozen"); check("frozen detected, killed, escalated", rc == 2 and "no CPU" in s["unit"].get("last_error", ""), s["unit"])

# 4 frozen first time, fine second time -> recovered by retry
script("flaky_freeze.py", "import os,time\nif not os.path.exists('m1'):\n  open('m1','w');time.sleep(60)\nopen('f.glb','wb').write(b'glTF..')\n")
sv("run", "freeze_retry", "--stall", "4", "--retries", "1", "--out", "f.glb", "--", PY, "flaky_freeze.py")
rc, s = wait("freeze_retry"); check("frozen then retried -> verified", rc == 0 and s["unit"]["attempts"] == 2, s["unit"])

# 5 deterministic crash is NOT retried
script("crash.py", "d={}\nprint(d['missing'])\n")
sv("run", "crash", "--retries", "3", "--", PY, "crash.py")
rc, s = wait("crash"); check("code error escalated without retry", rc == 2 and s["unit"]["attempts"] == 1 and "KeyError" in s["unit"]["note"], s["unit"])

# 6 transient network error retried
script("net.py", "import os,sys\nif not os.path.exists('m2'):\n  open('m2','w');print('ConnectionResetError: Connection reset by peer');sys.exit(1)\nopen('n.json','w').write('[1]')\n")
sv("run", "net", "--retries", "2", "--out", "n.json", "--", PY, "net.py")
rc, s = wait("net"); check("transient error retried -> verified", rc == 0 and s["unit"]["attempts"] == 2, s["unit"])

# 7 exit 0 but output missing
sv("run", "noout", "--out", "never.png", "--", "true")
rc, s = wait("noout"); check("missing output -> failed", rc == 1 and "missing output" in s["unit"]["note"], s["unit"])

# 8 stale output (exists but older than the run)
open(os.path.join(W, "old.png"), "wb").write(b"\x89PNG"); os.utime(os.path.join(W, "old.png"), (1, 1))
sv("run", "stale", "--out", "old.png", "--", "true")
rc, s = wait("stale"); check("stale output -> failed", rc == 1 and "stale" in s["unit"]["note"], s["unit"])

# 9 repeated error loop while still busy
script("loop.py", "import time\nwhile True:\n  print('ERROR: texture slot 3 missing', flush=True); time.sleep(0.2)\n")
sv("run", "errloop", "--stall", "60", "--", PY, "loop.py")
rc, s = wait("errloop"); check("error loop detected", rc == 2 and "error loop" in s["unit"].get("last_error", ""), s["unit"])

# 10 duplicate refused (same name, and same command under another name)
sv("run", "dup", "--", "sleep", "20")
time.sleep(1)
r1 = sv("run", "dup", "--", "sleep", "20"); r2 = sv("run", "dup2", "--", "sleep", "20")
check("duplicate refused", r1.returncode == 3 and r2.returncode == 3, (r1.stdout, r2.stdout))
sv("kill", "dup")

# 11 batch: one item fails; after the fix, retry re-runs only that item
script("item.py", "import sys,os\nn=sys.argv[1]\nif n=='b' and not os.path.exists('fixed'): raise KeyError('b')\nopen(n+'.png','wb').write(b'\\x89PNG')\n")
man = {"items": [{"id": k, "cmd": [PY, "item.py", k], "outputs": [k + ".png"]} for k in "abc"], "parallel": 2}
json.dump(man, open(os.path.join(W, "m.json"), "w"))
sv("batch", "assets", "m.json")
rc, s = wait("assets"); st = {i["id"]: i["status"] for i in s["items"]}
check("batch reports the one failed item", st == {"a": "verified", "b": "escalated", "c": "verified"}, st)
open(os.path.join(W, "fixed"), "w")
sv("retry", "assets"); rc, s = wait("assets")
att = {i["id"]: i.get("attempts") for i in s["items"]}
check("batch retry re-ran only the failed item", rc == 0 and att["a"] == 1 and att["c"] == 1 and s["status"] == "verified", att)
# re-submitting the manifest reuses verified items
sv("batch", "assets", "m.json"); rc, s = wait("assets")
check("re-submitted batch reuses verified outputs", all("reused" in i.get("note", "") for i in s["items"]), [i.get("note") for i in s["items"]])

# 12 hooks
H = [sys.executable, os.path.join(HERE, "hooks.py")]
bg = subprocess.Popen(["bash", "-c", "exec -a blender_fake_render sleep 30"])
time.sleep(0.5)
p = subprocess.Popen(["python3", "-c", "import time;time.sleep(30)", "glb_preview.py", "x.png", "y.glb"])
time.sleep(0.5)
r = subprocess.run(H + ["pre-bash"], input=json.dumps({"tool_input": {"command": "cd /x && python3 -I glb_preview.py x.png y.glb > /tmp/l 2>&1"}}),
                   env=ENV, capture_output=True, text=True)
deny = r.stdout and json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
r2 = subprocess.run(H + ["pre-bash"], input=json.dumps({"tool_input": {"command": "python3 -I glb_preview.py other.png z.glb"}}),
                    env=ENV, capture_output=True, text=True)
check("pre-bash blocks the duplicate, allows different work", deny and not r2.stdout.strip(), (r.stdout, r2.stdout))
p.kill(); bg.kill()
sv("run", "held", "--hold", "--", "sleep", "15"); time.sleep(1)
blocks = 0
for k in range(5):
    r = subprocess.run(H + ["stop"], input=json.dumps({"session_id": "t", "stop_hook_active": k > 0}), env=ENV, capture_output=True, text=True)
    blocks += bool(r.stdout.strip() and json.loads(r.stdout).get("decision") == "block")
check("stop hook blocks while held job runs, at most 3 times", blocks == 3, blocks)
sv("kill", "held")
r = subprocess.run(H + ["session-start"], input="{}", env=ENV, capture_output=True, text=True)
check("session-start emits context", "additionalContext" in r.stdout, r.stdout[:200])
r = subprocess.run(H + ["post-bash"], input=json.dumps({"tool_response": {"stdout": "Command did not complete within its 120s timeout and was moved to the background (ID: x). Output is being written to: /tmp/o.output"}}),
                   env=ENV, capture_output=True, text=True)
check("post-bash notices backgrounded commands", "/tmp/o.output" in r.stdout, r.stdout)
r = subprocess.run(H + ["pre-bash"], input="not json", env=ENV, capture_output=True, text=True)
check("hooks fail open on bad input", r.returncode == 0, r.returncode)

print(open(os.path.join(ENV["SV_HOME"], "REPORT.md")).read())
print("ALL PASSED" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
