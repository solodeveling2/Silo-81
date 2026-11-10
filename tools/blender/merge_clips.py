"""Merge freshly packaged clips (PKG dir) into a game character folder: copy their sheets, replace
their character.json entries, keep every other clip. Usage: python3 merge_clips.py PKG_DIR GAME_CHAR_DIR"""
import json, os, shutil, sys
src, dst = sys.argv[1], sys.argv[2]
new = json.load(open(os.path.join(src, "character.json")))
cur = json.load(open(os.path.join(dst, "character.json")))
for a, e in new["animations"].items():
    for d in e["directions"].values():
        shutil.copy(os.path.join(src, d["sheet"]), os.path.join(dst, d["sheet"]))
    cur["animations"][a] = e
    print("merged", a)
json.dump(cur, open(os.path.join(dst, "character.json"), "w"), indent=2)
