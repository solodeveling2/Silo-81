"""Schematic top-down map for docs/LEVEL_ROAD_TO_JUNK_TOWN.md.

Run:  python tools/design/road_map.py
Out:  docs/ROAD_TO_JUNK_TOWN_MAP.png
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

W, H = 1600, 900
PPU = 14.0          # pixels per metre
OX, OY = 130, 150   # screen origin for (u=0, v=-10)


def X(u):
    return OX + u * PPU


def Y(v):
    return OY + (v + 10) * PPU


def font(size, bold=False):
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    path = Path("C:/Windows/Fonts") / name
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:
        return ImageFont.load_default(size=size)


img = Image.new("RGB", (W, H), "#e9eef1")
d = ImageDraw.Draw(img, "RGBA")

F_TITLE = font(34, True)
F_SUB = font(17)
F_CHUNK = font(18, True)
F_LABEL = font(15)
F_SMALL = font(13)
F_LEGEND = font(15)

# ---------------------------------------------------------------- chunks
chunks = [
    ("RD_A", 0, 26, -8, 16, (52, 92, 120, 26)),
    ("RD_B", 26, 58, -8, 24, (52, 110, 72, 26)),
    ("RD_C", 58, 86, -2, 32, (140, 92, 52, 26)),
]
for name, u0, u1, v0, v1, col in chunks:
    d.rectangle([X(u0), Y(v0), X(u1), Y(v1)], fill=col, outline=(31, 42, 48, 120), width=2)
    d.text((X(u0) + 10, Y(v0) + 8), f"{name}  {u1-u0} × {v1-v0} m", font=F_CHUNK,
           fill=(31, 42, 48, 235))

# ---------------------------------------------------------------- road
road = [(2, 2), (10, 6), (20, 9), (30, 11), (36, 12), (44, 14), (52, 16), (60, 18), (68, 16), (76, 16)]
d.line([(X(u), Y(v)) for u, v in road], fill=(170, 178, 182, 255), width=120, joint="curve")
d.line([(X(u), Y(v)) for u, v in road], fill=(86, 92, 97, 255), width=92, joint="curve")
for i in range(len(road) - 1):
    (u0, v0), (u1, v1) = road[i], road[i + 1]
    d.line([(X(u0), Y(v0)), (X(u1), Y(v1))], fill=(214, 190, 110, 200), width=3)
    # centre dashes
    mx, my = (X(u0) + X(u1)) / 2, (Y(v0) + Y(v1)) / 2
    d.line([(mx - 6, my - 2), (mx + 6, my + 2)], fill=(240, 226, 170, 220), width=2)

# optional rest-stop loop
loop = [(46, 10), (46, 2), (49, -4), (53, 4), (54, 12)]
d.line([(X(u), Y(v)) for u, v in loop], fill=(31, 42, 48, 150), width=4)
d.text((X(46) - 4, Y(-6) - 20), "optional loop", font=F_SMALL, fill=(31, 42, 48, 190))

# ---------------------------------------------------------------- landmarks
# Silo hatch
d.rectangle([X(-2), Y(-2), X(4), Y(4)], fill=(60, 66, 72), outline=(20, 24, 28), width=3)
d.rectangle([X(-1), Y(-1), X(3), Y(3)], fill=(90, 98, 104))
d.text((X(-2), Y(5)), "SILO 81\nsurface hatch", font=F_LABEL, fill=(20, 24, 28))

# vehicle graveyard
for i, (u, v) in enumerate([(8, 4), (10, 9), (12, 5), (13, 11), (15, 8)]):
    d.rounded_rectangle([X(u) - 9, Y(v) - 5, X(u) + 9, Y(v) + 5], 3,
                        fill=(120, 126, 130), outline=(50, 56, 60))
d.text((X(8), Y(12)), "vehicle graveyard", font=F_SMALL, fill=(31, 42, 48, 210))

# fallen pylon
d.polygon([(X(30), Y(11) - 16), (X(30) - 9, Y(11) + 8), (X(30) + 9, Y(11) + 8)],
          fill=(110, 88, 56), outline=(40, 30, 20))
d.text((X(30) - 6, Y(11) + 12), "pylon", font=F_SMALL, fill=(40, 30, 20))

# red trailer
d.rectangle([X(42), Y(12), X(47), Y(16)], fill=(140, 48, 40), outline=(50, 20, 16), width=2)
d.text((X(42), Y(17)), "red trailer", font=F_SMALL, fill=(50, 20, 16))

# rest stop
d.rectangle([X(43), Y(-6), X(52), Y(0)], fill=(170, 165, 150), outline=(50, 50, 44), width=2)
d.rectangle([X(44), Y(-5), X(46), Y(-3)], fill=(90, 100, 110))
d.text((X(43), Y(-8) - 18), "rest stop (optional)", font=F_LABEL, fill=(31, 42, 48))

# billboard
d.line([(X(52), Y(16)), (X(52), Y(13))], fill=(60, 60, 60), width=3)
d.rectangle([X(50), Y(11), X(54), Y(13)], fill=(190, 190, 180), outline=(50, 50, 50))
d.text((X(50), Y(17)), "billboard", font=F_SMALL, fill=(31, 42, 48))

# scrapyard clutter
for (u, v) in [(61, 10), (63, 12), (66, 10), (60, 22), (63, 23), (66, 24), (68, 20)]:
    d.rectangle([X(u) - 7, Y(v) - 5, X(u) + 7, Y(v) + 5], fill=(120, 104, 86), outline=(50, 40, 30))

# Junk Town wall (gap at gate v 14..18)
d.line([(X(70), Y(4)), (X(70), Y(14))], fill=(120, 52, 40, 255), width=13)
d.line([(X(70), Y(18)), (X(70), Y(30))], fill=(120, 52, 40, 255), width=13)
for (u, v) in [(67, 8), (67, 26)]:
    d.rectangle([X(u) - 8, Y(v) - 8, X(u) + 8, Y(v) + 8], fill=(78, 62, 48), outline=(30, 22, 16), width=2)
d.text((X(70) + 8, Y(8)), "JUNK TOWN\ncar + corrugated wall\nwatchtowers", font=F_LABEL, fill=(70, 28, 20))
d.text((X(70) - 6, Y(31)), "gate (70,16)", font=F_SMALL, fill=(70, 28, 20))

# gate yard
d.rectangle([X(70), Y(8), X(86), Y(28)], fill=(200, 150, 90, 40), outline=(120, 70, 40, 120), width=2)
d.text((X(76), Y(12)), "safe hub\ngate yard", font=F_LABEL, fill=(70, 40, 20))
d.text((X(76), Y(20)), "Rook · Mara\nmarket · fire · pen", font=F_SMALL, fill=(70, 40, 20))

# ---------------------------------------------------------------- enemies / loot
def enemy(u, v, label):
    r = 11
    d.ellipse([X(u) - r, Y(v) - r, X(u) + r, Y(v) + r], fill=(180, 52, 42), outline=(70, 16, 12), width=2)
    d.text((X(u), Y(v) - 7), label, font=font(12, True), fill="white")


def loot(u, v, label):
    r = 7
    d.polygon([(X(u), Y(v) - r), (X(u) + r, Y(v)), (X(u), Y(v) + r), (X(u) - r, Y(v))],
              fill=(214, 168, 32), outline=(90, 64, 10))
    d.text((X(u) + 10, Y(v) - 8), label, font=F_SMALL, fill=(70, 50, 10))


enemy(36, 12, "3")
d.text((X(36) + 14, Y(12) - 8), "E1 first Changed", font=F_SMALL, fill=(90, 20, 16))
enemy(47, -1, "2")
d.text((X(47) + 14, Y(-1) - 8), "E2 optional", font=F_SMALL, fill=(90, 20, 16))
enemy(64, 14, "3")
d.text((X(64) + 14, Y(14) - 8), "E3 gate fight", font=F_SMALL, fill=(90, 20, 16))

loot(4, 5, "L1")
loot(11, 7, "L2")
loot(37, 14, "L3")
loot(45, -4, "L4")
loot(52, 15, "L5")

# ---------------------------------------------------------------- annotations
d.text((130, 34), "The Road to Junk Town — first outdoor area", font=F_TITLE, fill=(22, 30, 34))
d.text((132, 78), "Schematic top-down · 47° gameplay camera · 165 px/m · 3 streamed chunks · ~85 m main route",
       font=F_SUB, fill=(60, 72, 78))

# legend
lx, ly = 1180, 60
d.rounded_rectangle([lx, ly, 1540, ly + 150], 8, fill=(255, 255, 255, 210), outline=(60, 72, 78, 120))
d.text((lx + 14, ly + 10), "Legend", font=F_LEGEND, fill=(22, 30, 34))
d.ellipse([lx + 16, ly + 42, lx + 30, ly + 56], fill=(180, 52, 42)); d.text((lx + 40, ly + 40), "The Changed (count)", font=F_SMALL, fill=(30, 38, 42))
d.polygon([(lx + 23, ly + 66), (lx + 30, ly + 73), (lx + 23, ly + 80), (lx + 16, ly + 73)], fill=(214, 168, 32)); d.text((lx + 40, ly + 64), "loot", font=F_SMALL, fill=(30, 38, 42))
d.line([(lx + 16, ly + 98), (lx + 30, ly + 98)], fill=(31, 42, 48, 150), width=4); d.text((lx + 40, ly + 90), "optional loop", font=F_SMALL, fill=(30, 38, 42))
d.text((lx + 16, ly + 112), "E1 / E3 mandatory · E2 optional", font=F_SMALL, fill=(60, 72, 78))
d.text((lx + 16, ly + 128), "Route: hatch → E1 → trailer → gate", font=F_SMALL, fill=(60, 72, 78))

# axes
d.line([(120, 840), (240, 840)], fill=(40, 50, 56), width=3)
d.polygon([(240, 840), (228, 834), (228, 846)], fill=(40, 50, 56))
d.text((246, 832), "u (east)", font=F_SMALL, fill=(40, 50, 56))
d.line([(120, 840), (120, 760)], fill=(40, 50, 56), width=3)
d.polygon([(120, 760), (114, 772), (126, 772)], fill=(40, 50, 56))
d.text((100, 744), "v (south)", font=F_SMALL, fill=(40, 50, 56))

# scale bar
sx, sy = 120, 872
d.line([(sx, sy), (sx + 10 * PPU, sy)], fill=(30, 38, 42), width=3)
d.line([(sx, sy - 6), (sx, sy + 6)], fill=(30, 38, 42), width=2)
d.line([(sx + 10 * PPU, sy - 6), (sx + 10 * PPU, sy + 6)], fill=(30, 38, 42), width=2)
d.text((sx + 10 * PPU + 10, sy - 9), "10 m", font=F_SMALL, fill=(30, 38, 42))

out = Path(__file__).resolve().parents[2] / "docs" / "ROAD_TO_JUNK_TOWN_MAP.png"
out.parent.mkdir(parents=True, exist_ok=True)
img.save(out)
print(f"wrote {out} ({img.width}x{img.height})")
