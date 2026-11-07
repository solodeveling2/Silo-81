import json, sys
from PIL import Image
d = sys.argv[1]; L = json.load(open(f"{d}/level.json"))
bg = Image.open(f"{d}/bg.png"); bx, by = L["bg"]["x0"], L["bg"]["y0"]
items = []
for p in L["props"]:
    items.append((p["sort"][1], p["sprite"], p["x0"], p["y0"]))
for dr in L["doors"]:
    st = "spr_open" if dr.get("open") else "spr_closed"
    items.append((dr["sort"][1], dr[st]["sprite"], dr[st]["x0"], dr[st]["y0"]))
if "pipe" in L:
    pp = L["pipe"]; items.append((-1e9, pp["broken"]["sprite"], pp["broken"]["x0"], pp["broken"]["y0"]))
canvas = Image.new("RGBA", bg.size, (28, 28, 30, 255)); canvas.alpha_composite(bg)
for _, f, x, y in sorted(items):
    im = Image.open(f"{d}/{f}")
    canvas.alpha_composite(im, (int(round(x - bx)), int(round(y - by))))
canvas.convert("RGB").resize((bg.width // 2, bg.height // 2)).save(sys.argv[2])
print(bg.size)
