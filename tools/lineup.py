"""Line-up check for the art direction (docs/ART_DIRECTION.md, section 5): put every character's
idle frame side by side at the in-game camera zoom on a Silo 81 floor, so a new character can be
judged next to the approved ones at the size players will see.
Usage: python3 tools/lineup.py [out.png] [zoom]      (run from the repo root)"""
import os, sys, json, glob
from PIL import Image, ImageDraw

OUT = sys.argv[1] if len(sys.argv) > 1 else "lineup.png"
ZOOM = float(sys.argv[2]) if len(sys.argv) > 2 else 0.62          # the game camera's default zoom
chars = []
for cj in sorted(glob.glob("game/characters/*/character.json")):
    d = json.load(open(cj)); base = os.path.dirname(cj)
    a = d["animations"].get("idle") or next(iter(d["animations"].values()))
    di = a["directions"]["4"]                                       # facing down-left, towards the camera
    sheet = Image.open(os.path.join(base, di["sheet"])).convert("RGBA")
    fw, fh = di["frame_size"]
    fr = sheet.crop((0, 0, fw, fh))
    fr = fr.resize((max(1, round(fw * ZOOM)), max(1, round(fh * ZOOM))), Image.LANCZOS)
    chars.append((d.get("name", os.path.basename(base)), fr, [v * ZOOM for v in di["feet_anchor"]]))
gap = 30
W = sum(c[1].width for c in chars) + gap * (len(chars) + 1)
H = max(c[1].height for c in chars) + 70
img = Image.new("RGBA", (W, H), (58, 56, 52, 255))
dr = ImageDraw.Draw(img)
floor_y = H - 40
dr.rectangle((0, floor_y, W, H), fill=(92, 88, 80, 255))
x = gap
for name, fr, (ax, ay) in chars:
    img.alpha_composite(fr, (int(x), int(floor_y - ay)))
    dr.text((x, floor_y + 12), name, fill=(230, 220, 190, 255))
    x += fr.width + gap
img.save(OUT)
print(OUT, img.size, [c[0] for c in chars])
