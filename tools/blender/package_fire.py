"""Pack the aimed firing clips (render_aim.py) into the game's player folder and record the
measurements the game aims with: the character's height, where to hit it, and for every aim
pitch and direction where the muzzle is on the firing frame.

Usage: python3 package_fire.py out_dir game/characters/player_male
"""
import os, sys, json, math, glob
from PIL import Image

SRC, DST = sys.argv[1], sys.argv[2]
COLS, PAD = 8, 2
steps = json.load(open(os.path.join(SRC, "steps.json")))
cj = os.path.join(DST, "character.json")
data = json.load(open(cj))

# measured on the model in its combat stance (Head and Spine2 bones; the model is scaled to 1.75 m)
data["height_m"] = 1.75
data["aim_points"] = {"body": [0.0, 1.27], "head": [0.05, 1.59]}       # forward of the feet, height (m)

keys = sorted((k for k in steps["animations"] if k.startswith("pistol_fire_")),
              key=lambda k: steps["animations"][k]["pitch_deg"])
data["aim"] = {"clip": "pistol_fire", "pitches": [steps["animations"][k]["pitch_deg"] for k in keys]}
for key in keys:
    meta = steps["animations"][key]
    n = meta["frames"]; ax, ay = meta["anchor_px"]
    entry = {"fps": meta["fps"], "loop": False, "frames": n, "action_frame": meta["action_frame"],
             "pitch_deg": meta["pitch_deg"], "directions": {}}
    for d in range(6):
        de = meta["directions"][str(d)]
        frames = [Image.open(os.path.join(SRC, key, f"dir{d}_{i:03d}.png")).convert("RGBA") for i in range(n)]
        boxes = [f.getbbox() for f in frames if f.getbbox()]
        x0 = max(0, min(b[0] for b in boxes) - PAD); y0 = max(0, min(b[1] for b in boxes) - PAD)
        x1 = min(frames[0].width, max(b[2] for b in boxes) + PAD); y1 = min(frames[0].height, max(b[3] for b in boxes) + PAD)
        fw, fh = x1 - x0, y1 - y0; cols = min(COLS, n); rows = math.ceil(n / cols)
        sheet = Image.new("RGBA", (cols * fw, rows * fh), (0, 0, 0, 0))
        for i, f in enumerate(frames):
            sheet.paste(f.crop((x0, y0, x1, y1)), ((i % cols) * fw, (i // cols) * fh))
        name = f"{key}_dir{d}.png"
        sheet.save(os.path.join(DST, name), optimize=True)
        entry["directions"][str(d)] = {
            "sheet": name, "frame_size": [fw, fh], "columns": cols,
            "feet_anchor": [round(ax - x0, 1), round(ay - y0, 1)], "step_px": [0.0, 0.0],
            "muzzle_offset_px": [round(de["muzzle_px"][0] - ax, 1), round(de["muzzle_px"][1] - ay, 1)],
            "muzzle_m": de["muzzle_m"], "barrel_pitch_deg": de["barrel_pitch_deg"]}
    data["animations"][key] = entry
    print(key, "barrel", [entry["directions"][str(d)]["barrel_pitch_deg"] for d in range(6)])

# the old shot started from the relaxed stance; the aimed clips replace it
if "pistol_attack" in data["animations"]:
    del data["animations"]["pistol_attack"]
    for f in glob.glob(os.path.join(DST, "pistol_attack_dir*.png*")):
        os.remove(f)
json.dump(data, open(cj, "w"), indent=1)
print("sheets MB", round(sum(os.path.getsize(p) for p in glob.glob(os.path.join(DST, "*.png"))) / 1e6, 1))
