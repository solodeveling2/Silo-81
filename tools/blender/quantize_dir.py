"""Cut every sprite sheet in a character folder to 256 colours (same method as package_aim.py).
Usage: python3 quantize_dir.py DIR [only-these-prefixes ...]"""
import glob, os, sys
from PIL import Image
d, pre = sys.argv[1], sys.argv[2:]
for p in sorted(glob.glob(os.path.join(d, "*.png"))):
    if pre and not any(os.path.basename(p).startswith(x) for x in pre):
        continue
    im = Image.open(p)
    if im.mode == "P":
        continue
    im.convert("RGBA").quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG).save(p, optimize=True)
tot = sum(os.path.getsize(p) for p in glob.glob(os.path.join(d, "*.png")))
print("MB", round(tot / 1e6, 1))
