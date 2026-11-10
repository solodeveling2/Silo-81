#!/usr/bin/env python3
"""Install the sv hooks.

  python3 tools/sv/install.py --project   write/merge <repo>/.claude/settings.json (shared via git)
  python3 tools/sv/install.py --user      merge into ~/.claude/settings.json with absolute paths, for
                                          sessions that start outside the repo (e.g. a scratch folder)
  python3 tools/sv/install.py --uninstall [--user|--project]

Merging keeps every existing setting and hook; sv's own entries are recognised by 'tools/sv/hooks.py'
and replaced, never duplicated. A .bak copy is written before any change.
"""
import json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))


def hooks(prefix):
    h = lambda ev, **kw: dict(type="command", command=f'python3 "{prefix}/tools/sv/hooks.py" {ev}', **kw)
    return {
        "SessionStart": [{"matcher": "startup|resume|compact", "hooks": [h("session-start", timeout=20)]}],
        "PreToolUse": [{"matcher": "Bash", "hooks": [h("pre-bash", timeout=15)]}],
        "PostToolUse": [{"matcher": "Bash", "hooks": [h("post-bash", timeout=15),
                                                     h("rewake", **{"async": True, "asyncRewake": True})]}],
        "Stop": [{"hooks": [h("stop", timeout=20)]}],
    }


def is_ours(group):
    return any("tools/sv/hooks.py" in x.get("command", "") for x in group.get("hooks", []))


def merge(path, prefix, remove=False):
    cfg = {}
    if os.path.exists(path):
        cfg = json.load(open(path)); shutil.copy(path, path + ".bak")
    hk = cfg.setdefault("hooks", {})
    for ev in list(hk):
        hk[ev] = [g for g in hk[ev] if not is_ours(g)]
        if not hk[ev]:
            del hk[ev]
    if not remove:
        for ev, groups in hooks(prefix).items():
            hk.setdefault(ev, []).extend(groups)
    if not hk:
        cfg.pop("hooks")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(cfg, open(path, "w"), indent=2)
    print(("removed sv hooks from " if remove else "installed sv hooks in ") + path)


if __name__ == "__main__":
    a = sys.argv[1:]
    user = "--user" in a
    path = os.path.expanduser("~/.claude/settings.json") if user else os.path.join(REPO, ".claude", "settings.json")
    merge(path, REPO if user else "${CLAUDE_PROJECT_DIR}", remove="--uninstall" in a)
