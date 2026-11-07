import os, sys, json, math
from PIL import Image
SRC = sys.argv[1] if len(sys.argv) > 1 else "out"; DST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "game", "characters", "pipe_worm")
os.makedirs(DST, exist_ok=True)
steps = json.load(open(os.path.join(SRC, "steps.json")))
COLS, PAD = 8, 2
data = {"name": "pipe_worm", "pixels_per_metre": steps["pixels_per_metre"],
        "direction_order": "0=right, then counter-clockwise: 1=up-right, 2=up-left, 3=left, 4=down-left, 5=down-right",
        "animations": {}}
ACTION_FRAME = {"bite": 11, "hit": 0, "death": 0}
for anim in ["idle", "crawl", "bite", "hit", "death", "chew", "release"]:
    meta = steps["animations"][anim]; n = meta["frames"]; ax, ay = meta["anchor_px"]
    entry = {"fps": meta["fps"], "loop": meta["loop"], "frames": n, "directions": {}}
    if anim in ACTION_FRAME: entry["action_frame"] = ACTION_FRAME[anim]
    for d in range(6):
        frames = [Image.open(os.path.join(SRC, anim, f"dir{d}_{i:03d}.png")).convert("RGBA") for i in range(n)]
        boxes = [f.getbbox() for f in frames if f.getbbox()]
        x0 = max(0, min(b[0] for b in boxes) - PAD); y0 = max(0, min(b[1] for b in boxes) - PAD)
        x1 = min(frames[0].width, max(b[2] for b in boxes) + PAD); y1 = min(frames[0].height, max(b[3] for b in boxes) + PAD)
        fw, fh = x1 - x0, y1 - y0; cols = min(COLS, n); rows = math.ceil(n / cols)
        sheet = Image.new("RGBA", (cols * fw, rows * fh), (0, 0, 0, 0))
        for i, f in enumerate(frames):
            sheet.paste(f.crop((x0, y0, x1, y1)), ((i % cols) * fw, (i // cols) * fh))
        name = f"{anim}_dir{d}.png"; sheet.save(os.path.join(DST, name), optimize=True)
        entry["directions"][str(d)] = {"sheet": name, "frame_size": [fw, fh], "columns": cols,
            "feet_anchor": [round(ax - x0, 1), round(ay - y0, 1)], "step_px": meta["directions"][str(d)]["step_px"]}
    data["animations"][anim] = entry
json.dump(data, open(os.path.join(DST, "character.json"), "w"), indent=1)
print("ok", sum(os.path.getsize(os.path.join(DST, f)) for f in os.listdir(DST)) / 1e6, "MB")
