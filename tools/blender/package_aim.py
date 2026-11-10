"""Pack the aimed shooting animation as pieces the game can chain, so the gun stays on the target:

  pistol_raise_<p>   combat stance -> aimed at pitch p             (frames 0..A of the full shot)
  pistol_shot_<p>    aimed -> fire -> recoil -> aimed again          (frames A..E; fires on its frame 0)
  pistol_lower_<p>   aimed -> combat stance                          (frames E..end)
  pistol_hold        one frame per held aim pitch, every 5 degrees:  the game shows the frame for the
                     current pitch, and steps through them to swing smoothly onto a new target

p is one of the six pitches the shot was rendered at (render_aim.py, out/); the held poses at every
5 degrees come from render_aim.py with PICK=<E> (out_hold/). Sheets are cut to 256 colours.

Usage: python3 package_aim.py out out_hold ../game/characters/player_male
"""
import os, sys, json, math, glob
from PIL import Image

SRC, HOLD_SRC, DST = sys.argv[1:4]
COLS, PAD = 8, 2
steps = json.load(open(os.path.join(SRC, "steps.json")))
hsteps = json.load(open(os.path.join(HOLD_SRC, "steps.json")))
cj = os.path.join(DST, "character.json")
data = json.load(open(cj))
LOWER, HOLD = 6, 2


def sheet_of(frames, name):
    boxes = [f.getbbox() for f in frames if f.getbbox()]
    x0 = max(0, min(b[0] for b in boxes) - PAD); y0 = max(0, min(b[1] for b in boxes) - PAD)
    x1 = min(frames[0].width, max(b[2] for b in boxes) + PAD); y1 = min(frames[0].height, max(b[3] for b in boxes) + PAD)
    fw, fh = x1 - x0, y1 - y0
    n = len(frames); cols = min(COLS, n); rows = math.ceil(n / cols)
    sh = Image.new("RGBA", (cols * fw, rows * fh), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sh.paste(f.crop((x0, y0, x1, y1)), ((i % cols) * fw, (i // cols) * fh))
    sh.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG).save(os.path.join(DST, name), optimize=True)
    return fw, fh, cols, x0, y0


def tag(p):
    return "0" if p == 0 else ("m%d" % -p if p < 0 else "p%d" % p)


keys = sorted((k for k in steps["animations"] if k.startswith("pistol_fire_")), key=lambda k: steps["animations"][k]["pitch_deg"])
pitches = [steps["animations"][k]["pitch_deg"] for k in keys]
for key in keys:
    meta = steps["animations"][key]
    n, A = meta["frames"], meta["action_frame"]
    E = n - 1 - LOWER                                   # last held frame after the recoil
    ax, ay = meta["anchor_px"]
    t = tag(meta["pitch_deg"])
    parts = {"pistol_raise_" + t: list(range(0, A + 1)), "pistol_shot_" + t: list(range(A, E + 1)),
             "pistol_lower_" + t: list(range(E, n))}
    for clip, idx in parts.items():
        entry = {"fps": meta["fps"], "loop": False, "frames": len(idx), "pitch_deg": meta["pitch_deg"], "directions": {}}
        if clip.startswith("pistol_shot_"):
            entry["action_frame"] = 0
        for d in range(6):
            de = meta["directions"][str(d)]
            frames = [Image.open(os.path.join(SRC, key, f"dir{d}_{i:03d}.png")).convert("RGBA") for i in idx]
            fw, fh, cols, x0, y0 = sheet_of(frames, f"{clip}_dir{d}.png")
            e = {"sheet": f"{clip}_dir{d}.png", "frame_size": [fw, fh], "columns": cols,
                 "feet_anchor": [round(ax - x0, 1), round(ay - y0, 1)], "step_px": [0.0, 0.0]}
            if clip.startswith("pistol_shot_"):
                e["muzzle_offset_px"] = [round(de["muzzle_px"][0] - ax, 1), round(de["muzzle_px"][1] - ay, 1)]
                e["muzzle_m"] = de["muzzle_m"]; e["barrel_pitch_deg"] = de["barrel_pitch_deg"]
            entry["directions"][str(d)] = e
        data["animations"][clip] = entry
    print(t, {c: len(i) for c, i in parts.items()})

# held aim: one frame per pitch, every 5 degrees, all frames the same size per direction
hkeys = sorted((k for k in hsteps["animations"] if k.startswith("pistol_fire_")), key=lambda k: hsteps["animations"][k]["pitch_deg"])
hp = [hsteps["animations"][k]["pitch_deg"] for k in hkeys]
E = hsteps["animations"][hkeys[0]]["frames"] - 1 - LOWER
ax, ay = hsteps["animations"][hkeys[0]]["anchor_px"]
entry = {"fps": 24, "loop": False, "frames": len(hkeys), "directions": {}}
for d in range(6):
    frames = [Image.open(os.path.join(HOLD_SRC, k, f"dir{d}_{E:03d}.png")).convert("RGBA") for k in hkeys]
    fw, fh, cols, x0, y0 = sheet_of(frames, f"pistol_hold_dir{d}.png")
    entry["directions"][str(d)] = {"sheet": f"pistol_hold_dir{d}.png", "frame_size": [fw, fh], "columns": cols,
                                   "feet_anchor": [round(ax - x0, 1), round(ay - y0, 1)], "step_px": [0.0, 0.0]}
data["animations"]["pistol_hold"] = entry
data["aim"] = {"shot": "pistol_shot", "raise": "pistol_raise", "lower": "pistol_lower", "hold": "pistol_hold",
               "pitches": pitches, "hold_pitches": hp}
# the old one-piece clips are replaced by the pieces
for k in [k for k in data["animations"] if k.startswith("pistol_fire_")]:
    del data["animations"][k]
for f in glob.glob(os.path.join(DST, "pistol_fire_*_dir*.png")):
    os.remove(f)
json.dump(data, open(cj, "w"), indent=1)
print("hold pitches", hp)
print("sheets MB", round(sum(os.path.getsize(p) for p in glob.glob(os.path.join(DST, "*.png"))) / 1e6, 1))
