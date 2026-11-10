"""Trim the rendered frames, pack them into one sprite sheet per animation and direction, and write
character.json, which the Godot script reads (fps, loop, frame size, feet anchor, step per frame)."""
import os, json, math, glob
from PIL import Image

SRC = os.environ.get("PKG_SRC", "out")
DST = os.environ.get("PKG_DST", "pkg/Silo81_Player/characters/player_male")
os.makedirs(DST, exist_ok=True)
steps = json.load(open(os.path.join(SRC, "steps.json")))
COLS = 8
PAD = 2
data = {"name": "player_male", "pixels_per_metre": steps["pixels_per_metre"],
        "direction_order": "0=right, then counter-clockwise: 1=up-right, 2=up-left, 3=left, 4=down-left, 5=down-right",
        "animations": {}}
KEEP = os.environ.get("PKG_KEEP", "walk run idle hit pistol_idle pistol_attack death fall").split()
ACTION_FRAME = {"pistol_attack": 8, "hit": 0, "death": 0}
for anim in KEEP:
    meta = steps["animations"][anim]
    n = meta["frames"]
    ax, ay = meta["anchor_px"]
    entry = {"fps": meta["fps"], "loop": meta["loop"], "frames": n, "directions": {}}
    if anim in ACTION_FRAME:
        entry["action_frame"] = ACTION_FRAME[anim]       # the frame where the shot/hit lands
    for d in range(6):
        frames = [Image.open(os.path.join(SRC, anim, f"dir{d}_{i:03d}.png")).convert("RGBA") for i in range(n)]
        boxes = [f.getbbox() for f in frames if f.getbbox()]
        x0 = max(0, min(b[0] for b in boxes) - PAD); y0 = max(0, min(b[1] for b in boxes) - PAD)
        x1 = min(frames[0].width, max(b[2] for b in boxes) + PAD); y1 = min(frames[0].height, max(b[3] for b in boxes) + PAD)
        fw, fh = x1 - x0, y1 - y0
        cols = min(COLS, n); rows = math.ceil(n / cols)
        sheet = Image.new("RGBA", (cols * fw, rows * fh), (0, 0, 0, 0))
        for i, f in enumerate(frames):
            sheet.paste(f.crop((x0, y0, x1, y1)), ((i % cols) * fw, (i // cols) * fh))
        name = f"{anim}_dir{d}.png"
        sheet.save(os.path.join(DST, name), optimize=True)
        de = meta["directions"][str(d)]
        entry["directions"][str(d)] = {
            "sheet": name, "frame_size": [fw, fh], "columns": cols,
            "feet_anchor": [round(ax - x0, 1), round(ay - y0, 1)],        # where the feet touch the ground, inside a frame
            "step_px": de["step_px"],                                      # move the character this far every frame
        }
        if "planted_toe_drift_px_per_frame" in de:
            entry["directions"][str(d)]["slide_check_px_per_frame"] = de["planted_toe_drift_px_per_frame"]
    data["animations"][anim] = entry
    print(anim, "frames", n, "frame size dir4", entry["directions"]["4"]["frame_size"])
json.dump(data, open(os.path.join(DST, "character.json"), "w"), indent=2)
tot = sum(os.path.getsize(p) for p in glob.glob(os.path.join(DST, "*.png")))
print("sheets total MB", round(tot / 1e6, 1))
