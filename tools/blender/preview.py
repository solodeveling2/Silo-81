import json, sys
from PIL import Image
d = sys.argv[1]; L = json.load(open(f"{d}/level.json"))
if "tiles" in L["bg"]:                                   # big outdoor level: tiled, lower-resolution ground
    B = L["bg"]; k = B["scale"]
    bg = Image.new("RGBA", (int(B["w"]), int(B["h"])), (0, 0, 0, 0))
    for t in B["tiles"]:
        ti = Image.open(f"{d}/{t['file']}").convert("RGBA")
        ti = ti.resize((int(ti.width * k), int(ti.height * k)))
        bg.alpha_composite(ti, (int(t["x0"] - B["x0"]), int(t["y0"] - B["y0"])))
    bx, by = B["x0"], B["y0"]
else:
    bg = Image.open(f"{d}/bg.png"); bx, by = L["bg"]["x0"], L["bg"]["y0"]
items = []
for p in L["props"]:
    items.append((p["sort"][1], p["sprite"], p["x0"], p["y0"]))
for dr in L["doors"]:
    st = "spr_open" if dr.get("open") else "spr_closed"
    items.append((dr["sort"][1], dr[st]["sprite"], dr[st]["x0"], dr[st]["y0"]))
for wp in ([] if __import__("os").environ.get("NOWALLS") else L.get("wallparts", [])):
    items.append((wp["sort"][1], wp["sprite"], wp["x0"], wp["y0"]))
if "pipe" in L:
    pp = L["pipe"]; items.append((-1e9, pp["broken"]["sprite"], pp["broken"]["x0"], pp["broken"]["y0"]))
canvas = Image.new("RGBA", bg.size, (28, 28, 30, 255)); canvas.alpha_composite(bg)
for _, f, x, y in sorted(items):
    im = Image.open(f"{d}/{f}")
    canvas.alpha_composite(im, (int(round(x - bx)), int(round(y - by))))
f = int(__import__("os").environ.get("SHRINK", "2"))
canvas.convert("RGB").resize((bg.width // f, bg.height // f)).save(sys.argv[2])
print(bg.size)
