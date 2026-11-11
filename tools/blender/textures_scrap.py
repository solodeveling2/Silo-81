"""Tileable scrap-metal textures for Junk Town buildings: painted corrugated sheet (vertical ribs),
chipped to rust, with water and rust streaks, and weathered grey planks. Same 1024 px tiles and
linear-mean bookkeeping as textures.py (means.json is merged, not rewritten).

Usage: python3 textures_scrap.py [out_dir]     (default: tex)
"""
import os, sys, json
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

N = 1024
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "tex")
os.makedirs(OUT, exist_ok=True)


def C(*rgb):
    return np.array(rgb, dtype=np.float32) / 255.0


def noise(sigma, seed, aniso=None):
    a = np.random.default_rng(seed).random((N, N)).astype(np.float32)
    a = gaussian_filter(a, (sigma * aniso[0], sigma * aniso[1]) if aniso else sigma, mode="wrap")
    a -= a.min(); a /= max(a.max(), 1e-6)
    return a


def fbm(octaves, seed):
    out = np.zeros((N, N), np.float32); tot = 0
    for i, (sig, w) in enumerate(octaves):
        out += noise(sig, seed + i) * w; tot += w
    return out / tot


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a * (1 - t[..., None]) + b * t[..., None]


def streaks(seed, density=0.004, length=260):
    r = np.random.default_rng(seed)
    a = np.zeros((N, N), np.float32)
    for x in r.integers(0, N, int(N * density * 10)):
        y0 = r.integers(0, N); L = int(r.integers(length // 3, length))
        a[(y0 + np.arange(L)) % N, x] = np.linspace(1, 0.1, L) ** 0.7 * r.uniform(0.3, 1.0)
    return np.clip(gaussian_filter(a, (3.0, 2.2), mode="wrap") * 3.0, 0, 1)


def save(name, img):
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, name + ".png"))
    print("wrote", name)


RIBS = 11                       # ribs per tile; at 2 m per tile that is an 18 cm pitch (the 15 cm rule)


def corrugated(name, paint, seed, rust=0.62, chip=0.6, fade=0.25):
    """paint None = bare galvanised/rusting sheet. rust: threshold of the rust mask (lower = more rust).
    chip: threshold where paint has flaked to bare metal."""
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    rib = np.sin(xx / N * RIBS * 2 * np.pi)                       # -1..1 across each rib
    light = 0.80 + 0.20 * rib + 0.07 * np.clip(rib, 0, 1) ** 6    # lit flank, shaded flank, a glint on the crown
    big = fbm([(90, 1.0), (30, 0.5), (10, 0.25)], seed)
    metal = lerp(C(104, 104, 100), C(132, 132, 126), big)
    img = metal
    if paint is not None:
        p = lerp(paint * 0.86, np.minimum(paint * 1.15 + 0.03, 1), big)
        p = lerp(p, np.minimum(p + 0.10, 1), smooth(fbm([(70, 1), (20, .4)], seed + 3), 0.55, 0.8) * fade)   # sun-faded blotches
        flake = smooth(fbm([(16, 1.0), (5, 0.6), (1.5, 0.2)], seed + 5), chip, chip + 0.05)
        img = lerp(p, metal, flake)
    n = fbm([(26, 1.0), (8, 0.5), (2, 0.25)], seed + 9)
    m = smooth(n, rust, rust + 0.09)
    rc = lerp(C(116, 60, 32), C(150, 86, 46), noise(3, seed + 13))
    rc = lerp(rc, C(70, 38, 24), smooth(n, rust + 0.14, rust + 0.26))
    img = lerp(img, rc, m)
    st = streaks(seed + 21)
    img = lerp(img, img * C(0.62, 0.48, 0.38) / 0.62 * 0.62, st * 0.75)   # rust runs down the ribs
    dirt = streaks(seed + 23, density=0.002, length=420)
    img = lerp(img, img * 0.7, dirt * 0.6)
    img = img * light[..., None]
    img = lerp(img, img * 0.75, smooth(noise(1.0, seed + 17), 0.82, 0.9) * 0.6)  # pitting
    save(name, img)


def planks_weathered(name, base, seed, w=110):
    yy, xx = np.mgrid[0:N, 0:N]
    r = np.random.default_rng(seed)
    grain = noise(1.0, seed + 1, aniso=(40, 1))                   # boards stand upright: grain runs vertically
    col = xx // w
    offs = r.integers(0, N, N // w + 2)
    Lb = 512
    cell = col * 64 + ((yy + offs[col]) % N) // Lb
    edges = ((xx % w) < 5) | (((yy + offs[col]) % Lb) < 4)
    tone = r.normal(1.0, 0.10, cell.max() + 1).astype(np.float32)[cell]
    big = fbm([(60, 1.0), (24, 0.6)], seed + 4)
    img = base * tone[..., None] * (0.82 + 0.32 * grain[..., None])
    img = lerp(img, np.minimum(img * C(1.0, 1.04, 1.1) + 0.07, 1), smooth(big, 0.5, 0.8) * 0.45)   # silvered
    img = lerp(img, img * 0.72, streaks(seed + 7, density=0.002) * 0.4)
    img = lerp(img, img * 0.3, gaussian_filter(edges.astype(np.float32), 1.0, mode="wrap"))
    nails = np.zeros((N, N), np.float32)
    for c in range(N // w + 1):
        for y in (60, 60 + N // 2):
            x = int(c * w + w * 0.5)
            if x < N: nails[y - 3:y + 3, x - 3:x + 3] = 1
    img = lerp(img, img * 0.35, gaussian_filter(nails, 1.0, mode="wrap") * 0.9)
    save(name, img)


corrugated("corr_galv", None, seed=101, rust=0.66)
corrugated("corr_rust", None, seed=102, rust=0.40)
corrugated("corr_teal", C(66, 94, 90), seed=103)
corrugated("corr_blue", C(78, 92, 104), seed=104)
corrugated("corr_olive", C(90, 92, 64), seed=105)
corrugated("corr_red", C(112, 60, 48), seed=106, rust=0.58)
corrugated("corr_cream", C(176, 166, 136), seed=107, rust=0.7, chip=0.66)
corrugated("corr_yellow", C(150, 124, 64), seed=108, rust=0.6)
planks_weathered("planks_grey", C(118, 104, 88), seed=110)

mp = os.path.join(OUT, "means.json")
means = json.load(open(mp)) if os.path.exists(mp) else {}
for k in ("corr_galv", "corr_rust", "corr_teal", "corr_blue", "corr_olive", "corr_red", "corr_cream", "corr_yellow", "planks_grey"):
    a = np.asarray(Image.open(os.path.join(OUT, k + ".png")).convert("RGB")).astype(np.float32) / 255.0
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    means[k] = [round(float(x), 4) for x in lin.reshape(-1, 3).mean(0)]
json.dump(means, open(mp, "w"), indent=0)
print("means", len(means))
