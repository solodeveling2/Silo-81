"""Tileable surface textures for Silo 81, matched to the colours and wear of the v0.2 asset pack
(Silo81_Assets): stained concrete, rusty steel, canvas pipe lagging, floor grating, diamond plate,
clinic tiles. The pack's own sprites are about 128 px, too small to stretch over the rooms, so the
surfaces are rebuilt here at 1024 px from its palette.

Usage: python3 textures.py out_dir
"""
import os, sys
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

N = 1024
OUT = sys.argv[1] if len(sys.argv) > 1 else "tex"
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(81)


def C(*rgb):
    return np.array(rgb, dtype=np.float32) / 255.0


def noise(sigma, n=N, seed=None, aniso=None):
    """Tileable value noise in 0..1: white noise blurred with wrap-around."""
    r = np.random.default_rng(seed) if seed is not None else rng
    a = r.random((n, n)).astype(np.float32)
    s = (sigma * aniso[0], sigma * aniso[1]) if aniso else sigma
    a = gaussian_filter(a, s, mode="wrap")
    a -= a.min(); a /= max(a.max(), 1e-6)
    return a


def fbm(octaves, seed=0):
    out = np.zeros((N, N), np.float32); tot = 0
    for i, (sig, w) in enumerate(octaves):
        out += noise(sig, seed=seed + i) * w; tot += w
    return out / tot


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a * (1 - t[..., None]) + b * t[..., None]


def save(name, img):
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, name + ".png"))
    print("wrote", name)


def cracks(n_cracks, seed, width=1.2, length=(80, 260)):
    """Thin random-walk cracks, wrapping at the edges. Returns 0..1 mask."""
    r = np.random.default_rng(seed)
    m = np.zeros((N, N), np.float32)
    for _ in range(n_cracks):
        x, y = r.random(2) * N
        ang0 = ang = r.random() * 2 * np.pi
        for _ in range(int(r.integers(*length)) * 2):
            ang = ang0 + r.normal(0, 0.55) if r.random() < 0.08 else ang   # jagged kinks, no curling
            x = (x + np.cos(ang) * 1.5) % N; y = (y + np.sin(ang) * 1.5) % N
            m[int(y), int(x)] = 1.0
    return np.clip(gaussian_filter(m, width, mode="wrap") * 6, 0, 1)


def grime(seed):
    """Large soft stains plus fine speckle, the pack's dirty-concrete look."""
    big = fbm([(60, 1.0), (24, 0.6), (8, 0.3)], seed)
    speck = noise(1.0, seed=seed + 50)
    return big, speck


def rust_patches(seed, cover=0.55, sigma=18):
    n = fbm([(sigma, 1.0), (sigma / 3, 0.5), (2, 0.25)], seed)
    return smooth(n, cover, cover + 0.08), n


def streaks(seed, density=0.004, length=180):
    """Vertical rust/water streaks running down from the top of each tile (for walls)."""
    r = np.random.default_rng(seed)
    a = np.zeros((N, N), np.float32)
    xs = r.integers(0, N, int(N * density * 10))
    for x in xs:
        y0 = r.integers(0, N); L = int(r.integers(length // 3, length))
        ys = (y0 + np.arange(L)) % N
        a[ys, x] = np.linspace(1, 0.15, L) ** 0.7 * r.uniform(0.3, 1.0)
    return gaussian_filter(a, (2.0, 0.9), mode="wrap") * 2.2


# ---------------------------------------------------------------- concrete (walls, raw floors)
def concrete(name, base, dark, light, seed, crack_n=6, stain=0.35, streak=0.0, joints=None):
    big, speck = grime(seed)
    img = lerp(dark, light, big * 0.85 + speck * 0.15)
    img = lerp(img, base, np.full((N, N), 0.35, np.float32))
    # pitted aggregate
    pits = smooth(noise(1.3, seed=seed + 7), 0.78, 0.86)
    img = lerp(img, dark * 0.75, pits * 0.6)
    # damp stains
    st = smooth(fbm([(40, 1), (12, 0.5)], seed + 11), 0.62, 0.8) * stain
    img = lerp(img, dark * 0.8, st)
    if streak:
        s = np.clip(streaks(seed + 3), 0, 1) * streak
        img = lerp(img, C(104, 78, 58), s * 0.7)
    if crack_n:
        c = cracks(crack_n, seed + 21)
        img = lerp(img, dark * 0.55, c * 0.6)
    if joints:                                            # formwork / slab joints at the tile edge
        j = np.zeros((N, N), np.float32)
        w = joints
        j[:w, :] = 1; j[:, :w] = 1
        j = gaussian_filter(j, 1.0, mode="wrap")
        img = lerp(img, dark * 0.6, np.clip(j, 0, 1) * 0.8)
    save(name, img)


# ---------------------------------------------------------------- rusty steel
def steel(name, base, rust_cover=0.6, seed=0, paint=None, rivets=None, plates=None, pit=1.0, rust_sigma=18, chip_at=0.64):
    big, speck = grime(seed)
    img = lerp(base * 0.82, base * 1.12, big * 0.8 + speck * 0.2)
    if paint is not None:                                  # chipped paint over the steel
        chip = smooth(fbm([(14, 1), (4, 0.6)], seed + 5), chip_at, chip_at + 0.04)
        img = lerp(img, paint * (0.9 + 0.2 * big[..., None]), 1 - chip)
    mask, n = rust_patches(seed + 9, cover=rust_cover, sigma=rust_sigma)
    rust = lerp(C(118, 62, 34), C(150, 88, 48), noise(3, seed=seed + 13))
    rust = lerp(rust, C(72, 40, 26), smooth(n, rust_cover + 0.12, rust_cover + 0.25))
    img = lerp(img, rust, mask)
    img = lerp(img, img * 0.7, smooth(noise(1.0, seed=seed + 17), 0.8, 0.9) * pit)   # pitting
    if plates:                                             # plate seams at the tile edge, darker
        j = np.zeros((N, N), np.float32); j[:plates, :] = 1; j[:, :plates] = 1
        img = lerp(img, img * 0.45, gaussian_filter(j, 1.2, mode="wrap"))
    if rivets:
        rr = np.zeros((N, N), np.float32)
        step = N // rivets
        yy, xx = np.mgrid[0:N, 0:N]
        for k in range(rivets):
            for (cx, cy) in ((k * step + step // 2, 24), (24, k * step + step // 2)):
                d = np.hypot(xx - cx, yy - cy); rr = np.maximum(rr, smooth(-d, -9, -6))
        img = lerp(img, img * 1.25, rr)
        img = lerp(img, img * 0.5, np.roll(np.roll(rr, 3, 0), 3, 1) * (1 - rr) * 0.8)
    save(name, img)


# ---------------------------------------------------------------- lagging (canvas pipe insulation)
def lagging(name, seed=0):
    base, dark = C(166, 155, 130), C(116, 104, 82)
    big, speck = grime(seed)
    img = lerp(base * 1.04, dark, smooth(big, 0.2, 0.95) * 0.3 + speck * 0.08)
    weave = (np.sin(np.arange(N) * 2 * np.pi / 6)[None, :] * 0.5 + 0.5) * 0.06
    img = img * (1 - weave[..., None])
    # wrap seams: the pack's lagging is wound in overlapping bands
    x = np.arange(N)
    seam = np.zeros(N, np.float32)
    for c in (N // 4, 3 * N // 4):
        seam += np.exp(-((x - c) / 5.0) ** 2)
    img = lerp(img, dark * 0.7, np.tile(seam[None, :], (N, 1)) * 0.75)
    # soot and water marks from below
    yy = np.linspace(0, 1, N)[:, None]
    img = lerp(img, C(120, 108, 86), smooth(fbm([(70, 1), (20, 0.4)], seed + 3), 0.55, 0.8) * 0.45)
    save(name, img)


# ---------------------------------------------------------------- floor grating
def grating(name, seed=0, pitch=64, bar=14):
    yy, xx = np.mgrid[0:N, 0:N]
    gx = ((xx % pitch) < bar).astype(np.float32)          # main bars
    gy = ((yy % (pitch // 2)) < 6).astype(np.float32)     # cross bars
    g = np.maximum(gx, gy)
    g = gaussian_filter(g, 0.8, mode="wrap")
    below = lerp(C(26, 23, 21), C(58, 44, 34), smooth(fbm([(50, 1), (16, 0.5)], seed), 0.45, 0.7))  # pipes and murk below
    bars = lerp(C(84, 82, 78), C(120, 116, 110), noise(2, seed=seed + 2))
    mask, n = rust_patches(seed + 5, cover=0.58, sigma=22)
    bars = lerp(bars, C(118, 66, 38), mask * 0.85)
    # top edge highlight on bars
    edge = np.clip(gx - np.roll(gx, 3, 1), 0, 1)
    bars = lerp(bars, bars * 1.25, edge)
    img = lerp(below, bars, g)
    save(name, img)


# ---------------------------------------------------------------- diamond plate
def diamond(name, seed=0):
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    p = 64
    a = ((xx + yy) % p) / p; b = ((xx - yy) % p) / p
    lug = np.exp(-(((a - 0.5) / 0.08) ** 2 + ((b - 0.25) / 0.3) ** 2)) + \
          np.exp(-(((b - 0.5) / 0.08) ** 2 + ((a - 0.75) / 0.3) ** 2))
    base = C(108, 100, 92)
    big, speck = grime(seed)
    img = lerp(base * 0.8, base * 1.1, big * 0.8 + speck * 0.2)
    img = lerp(img, img * 1.35, np.clip(lug, 0, 1) * 0.7)
    img = lerp(img, img * 0.6, np.clip(np.roll(lug, 4, 0), 0, 1) * 0.4 * (1 - np.clip(lug, 0, 1)))
    mask, n = rust_patches(seed + 3, cover=0.55, sigma=26)
    img = lerp(img, C(122, 70, 40), mask * 0.75)
    j = np.zeros((N, N), np.float32); j[:5, :] = 1; j[:, :5] = 1
    img = lerp(img, img * 0.45, gaussian_filter(j, 1.0, mode="wrap"))
    save(name, img)


# ---------------------------------------------------------------- tiles (clinic green, frosted blue-white)
def tiles(name, base, grout, seed=0, n=4, frost=0.0):
    yy, xx = np.mgrid[0:N, 0:N]
    s = N // n
    gr = (((xx % s) < 7) | ((yy % s) < 7)).astype(np.float32)
    gr = gaussian_filter(gr, 1.0, mode="wrap")
    r = np.random.default_rng(seed)
    per = r.normal(1.0, 0.05, (n, n)).astype(np.float32)          # each tile a slightly different glaze
    shade = np.kron(per, np.ones((s, s), np.float32))
    big, speck = grime(seed)
    img = base * shade[..., None]
    img = lerp(img, img * 0.78, smooth(big, 0.55, 0.85) * 0.8)
    chips = smooth(noise(4, seed=seed + 9), 0.83, 0.86)
    img = lerp(img, grout * 0.9, chips * 0.9)
    c = cracks(5, seed + 4, width=0.9)
    img = lerp(img, grout * 0.6, c * 0.8)
    img = lerp(img, grout, gr)
    if frost:
        fr = smooth(fbm([(26, 1), (6, 0.5), (1.5, 0.3)], seed + 13), 0.35, 0.75)
        img = lerp(img, C(214, 226, 232), fr * frost)
    save(name, img)


concrete("concrete_wall", C(113, 109, 98), C(90, 85, 76), C(130, 125, 114), seed=1, crack_n=5, stain=0.22, streak=0.8)
concrete("concrete_floor", C(138, 132, 121), C(104, 99, 90), C(152, 146, 135), seed=2, crack_n=9, stain=0.4, joints=5)
concrete("concrete_floor_iced", C(150, 160, 162), C(108, 112, 112), C(178, 190, 196), seed=3, crack_n=7, stain=0.3, joints=5)
concrete("plaster_cream", C(196, 188, 166), C(160, 150, 128), C(212, 205, 186), seed=4, crack_n=3, stain=0.3, streak=0.4)
steel("steel_rust", C(92, 92, 90), rust_cover=0.56, seed=5)
steel("steel_bulkhead", C(98, 92, 84), rust_cover=0.6, seed=6, plates=6, rivets=8)
steel("steel_green", C(86, 90, 82), rust_cover=0.74, seed=7, paint=C(88, 104, 86), pit=0.4, rust_sigma=26, chip_at=0.7)
steel("valve_red", C(90, 80, 74), rust_cover=0.68, seed=8, paint=C(112, 50, 40))
lagging("lagging", seed=9)
grating("grating", seed=10)
diamond("diamond_plate", seed=11)
tiles("tile_clinic", C(128, 138, 106), C(80, 76, 64), seed=12, n=4)
tiles("tile_frosted", C(168, 182, 184), C(110, 116, 118), seed=13, n=4, frost=0.6)


# ---------------------------------------------------------------- floors the pack has no tile for, in its palette
def planks(name, base, seed=0, w=128, parquet=False):
    yy, xx = np.mgrid[0:N, 0:N]
    r = np.random.default_rng(seed)
    grain = noise(1.0, seed=seed + 1, aniso=(1, 40))            # long grain along the plank
    if parquet:                                                  # herringbone-ish blocks: alternate grain direction
        blk = ((xx // w + yy // w) % 2).astype(bool)
        grain = np.where(blk, grain, noise(1.0, seed=seed + 2, aniso=(40, 1)))
        cell = (yy // w) * 64 + xx // w
        edges = ((xx % w) < 4) | ((yy % w) < 4)
    else:
        row = yy // w
        offs = r.integers(0, N, N // w + 1)
        L = 384
        cell = row * 64 + ((xx + offs[row]) % N) // L
        edges = ((yy % w) < 4) | (((xx + offs[row]) % L) < 4)
    tone = r.normal(1.0, 0.08, cell.max() + 1).astype(np.float32)[cell]
    big, speck = grime(seed)
    img = base * tone[..., None] * (0.85 + 0.3 * grain[..., None])
    img = lerp(img, img * 0.7, smooth(big, 0.55, 0.85) * 0.7)     # worn, dirty traffic areas
    img = lerp(img, img * 0.35, gaussian_filter(edges.astype(np.float32), 0.8, mode="wrap"))
    save(name, img)


def lino(name, base, seed=0):
    yy, xx = np.mgrid[0:N, 0:N]
    s = N // 4
    chk = (((xx // s) + (yy // s)) % 2).astype(np.float32)
    big, speck = grime(seed)
    img = lerp(base, base * 0.93, chk)
    img = lerp(img, img * 0.8, smooth(big, 0.5, 0.85))
    worn = smooth(fbm([(40, 1), (10, 0.5)], seed + 3), 0.74, 0.8)  # worn through to the black backing
    img = lerp(img, C(60, 50, 44), worn * 0.6)
    gr = (((xx % s) < 3) | ((yy % s) < 3)).astype(np.float32)
    img = lerp(img, img * 0.5, gaussian_filter(gr, 0.8, mode="wrap"))
    save(name, img)


planks("wood_planks", C(122, 92, 62), seed=20)
planks("parquet", C(118, 80, 50), seed=21, parquet=True)
lino("lino", C(112, 86, 70), seed=22)
tiles("tile_white", C(176, 178, 170), C(104, 104, 98), seed=23, n=8)


def wood_grain(name, base, seed=0):
    grain = noise(1.0, seed=seed + 1, aniso=(1, 60))
    rings = noise(6, seed=seed + 2, aniso=(1, 12))
    big, speck = grime(seed)
    img = base * (0.8 + 0.25 * grain[..., None] + 0.15 * rings[..., None])
    img = lerp(img, img * 0.7, smooth(big, 0.55, 0.9) * 0.6)
    scuff = smooth(noise(2.5, seed=seed + 5), 0.82, 0.86)
    img = lerp(img, img * 1.25, scuff * 0.6)
    save(name, img)


def fabric(name, base, seed=0):
    x = np.arange(N)
    weave = (np.sin(x * 2 * np.pi / 5)[None, :] * np.sin(x * 2 * np.pi / 5)[:, None]) * 0.05
    big, speck = grime(seed)
    img = base * (1 + weave[..., None])
    img = lerp(img, img * 0.72, smooth(big, 0.5, 0.9) * 0.7)
    img = lerp(img, img * 0.85, speck[..., None][..., 0] * 0.3)
    save(name, img)


wood_grain("wood_grain", C(128, 96, 66), seed=30)
steel("steel_grey", C(96, 96, 92), rust_cover=0.8, seed=31, paint=C(132, 134, 128), pit=0.25, rust_sigma=30, chip_at=0.74)
steel("paint_white", C(96, 96, 92), rust_cover=0.82, seed=32, paint=C(196, 196, 186), pit=0.2, rust_sigma=30, chip_at=0.76)
fabric("fabric", C(150, 144, 128), seed=33)

# linear-light mean colour of every texture, so the kit can tint a texture to a material's designed colour
import json, glob
means = {}
for f in sorted(glob.glob(os.path.join(OUT, "*.png"))):
    a = np.asarray(Image.open(f).convert("RGB")).astype(np.float32) / 255.0
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    means[os.path.basename(f)[:-4]] = [round(float(x), 4) for x in lin.reshape(-1, 3).mean(0)]
json.dump(means, open(os.path.join(OUT, "means.json"), "w"), indent=0)
print("means", len(means))
