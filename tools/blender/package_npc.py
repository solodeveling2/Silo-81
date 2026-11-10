"""Pack an NPC's rendered clips (from one or more render_character.py output folders) into sprite
sheets plus character.json, the same format the player uses.
Usage: python3 package_npc.py name dest_dir src_dir [src_dir ...]"""
import os, sys, json, math, glob
from PIL import Image

NAME, DST, SRCS = sys.argv[1], sys.argv[2], sys.argv[3:]
os.makedirs(DST, exist_ok=True)
COLS, PAD = 8, 2
data = {"name": NAME, "direction_order": "0=right, then counter-clockwise: 1=up-right, 2=up-left, 3=left, 4=down-left, 5=down-right",
        "animations": {}}
for src in SRCS:
    steps = json.load(open(os.path.join(src, "steps.json")))
    data["pixels_per_metre"] = steps["pixels_per_metre"]
    data["height_m"] = steps.get("height_m", 1.75)
    for anim, meta in steps["animations"].items():
        if not os.path.isdir(os.path.join(src, anim)):
            continue
        n = meta["frames"]; ax, ay = meta["anchor_px"]
        entry = {"fps": meta["fps"], "loop": meta["loop"], "frames": n, "directions": {}}
        for d in range(6):
            frames = [Image.open(os.path.join(src, anim, f"dir{d}_{i:03d}.png")).convert("RGBA") for i in range(n)]
            boxes = [f.getbbox() for f in frames if f.getbbox()]
            x0 = max(0, min(b[0] for b in boxes) - PAD); y0 = max(0, min(b[1] for b in boxes) - PAD)
            x1 = min(frames[0].width, max(b[2] for b in boxes) + PAD); y1 = min(frames[0].height, max(b[3] for b in boxes) + PAD)
            fw, fh = x1 - x0, y1 - y0
            cols = min(COLS, n); rows = math.ceil(n / cols)
            sheet = Image.new("RGBA", (cols * fw, rows * fh), (0, 0, 0, 0))
            for i, f in enumerate(frames):
                sheet.paste(f.crop((x0, y0, x1, y1)), ((i % cols) * fw, (i // cols) * fh))
            nm = f"{anim}_dir{d}.png"
            sheet.save(os.path.join(DST, nm), optimize=True)
            de = meta["directions"][str(d)]
            entry["directions"][str(d)] = {"sheet": nm, "frame_size": [fw, fh], "columns": cols,
                                           "feet_anchor": [round(ax - x0, 1), round(ay - y0, 1)], "step_px": de["step_px"]}
        data["animations"][anim] = entry
        print(anim, n, "frames")
json.dump(data, open(os.path.join(DST, "character.json"), "w"), indent=2)
print("MB", round(sum(os.path.getsize(p) for p in glob.glob(os.path.join(DST, "*.png"))) / 1e6, 1))
