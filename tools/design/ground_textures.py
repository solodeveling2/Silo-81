"""Tileable ground textures for outdoor levels drawn by Godot (game/levels/_ground/*.png).
Painted in the game's palette (docs/VISUAL_DIRECTION.md): soft, low-contrast, a little grain.
Each tile is 512 px for 4 m of ground (128 px per metre). Run: python3 tools/design/ground_textures.py"""
import numpy as np
from PIL import Image
import os

N = 512
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "game", "levels", "_ground")
rng = np.random.default_rng(81)


def noise(beta=2.0, aniso=(1.0, 1.0), seed=None):
    """Periodic (tileable) fractal noise in [0, 1]: white noise shaped by 1/f^beta in the frequency domain."""
    r = np.random.default_rng(seed) if seed is not None else rng
    w = r.standard_normal((N, N))
    fx = np.fft.fftfreq(N)[None, :] * aniso[0]
    fy = np.fft.fftfreq(N)[:, None] * aniso[1]
    f = np.sqrt(fx * fx + fy * fy); f[0, 0] = 1
    n = np.real(np.fft.ifft2(np.fft.fft2(w) / f ** (beta / 2)))
    return (n - n.min()) / (n.max() - n.min())


def band(x, lo, hi):
    return np.clip((x - lo) / (hi - lo), 0, 1)


def save(name, rgb):
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, name + ".png"))
    print(name)


def col(c):
    return np.array(c)[None, None, :]


# snow (1024 px = 8 m): wind ripples (sastrugi), faint blue hollows, a fine grain
N = 1024
low, mid, fine = noise(3.2, seed=1), noise(2.0, seed=2), noise(0.6, seed=3)
ripple = noise(2.4, aniso=(0.3, 1.0), seed=4)
h = 0.35 * low + 0.4 * ripple + 0.25 * mid
lit, shade = col((0.84, 0.87, 0.90)), col((0.74, 0.78, 0.84))
snow = shade + (lit - shade) * band(h, 0.28, 0.7)[..., None]
snow += (fine[..., None] - 0.5) * 0.03
save("snow", snow)
N = 512
low, mid, fine = noise(3.0, seed=1), noise(2.0, seed=2), noise(0.6, seed=3)

# trodden snow (the yard and the verges): grey slush, boot-churned, a few darker wet patches
churn = noise(1.6, seed=5); wet = band(noise(2.8, seed=6), 0.6, 0.8)
yard = col((0.66, 0.67, 0.69)) * (0.92 + 0.12 * churn[..., None])
yard = yard * (1 - 0.18 * wet[..., None]) + col((0.40, 0.38, 0.35)) * 0.18 * wet[..., None]
yard += (fine[..., None] - 0.5) * 0.04
save("yard", yard)

# asphalt under old snow: dark aggregate, cracks, snow dusting in the low spots
agg = noise(0.3, seed=7); patches = band(noise(2.8, seed=8), 0.55, 0.75)
ash = col((0.42, 0.43, 0.45)) * (0.86 + 0.24 * agg[..., None]) * (0.95 + 0.1 * mid[..., None])
crack = band(1 - np.abs(noise(2.2, seed=9) - 0.5) * 2, 0.97, 1.0)
ash = ash * (1 - 0.35 * crack[..., None])
ash = ash * (1 - patches[..., None]) + col((0.74, 0.77, 0.80)) * patches[..., None] * (0.95 + 0.05 * fine[..., None])
save("asphalt", ash)

# concrete: 2 m slabs, joints, stains
yy, xx = np.mgrid[0:N, 0:N]
joint = ((xx % 256) < 3) | ((yy % 256) < 3)
con = col((0.56, 0.56, 0.55)) * (0.9 + 0.14 * noise(1.8, seed=10)[..., None]) * (0.96 + 0.06 * agg[..., None])
con[joint] *= 0.72
stain = band(noise(2.6, seed=11), 0.62, 0.8)
con = con * (1 - 0.15 * stain[..., None])
dust = band(noise(2.6, seed=12), 0.6, 0.78)
con = con * (1 - dust[..., None]) + col((0.76, 0.79, 0.82)) * dust[..., None]
save("concrete", con)

# soft round mask for decals (ice, slush, light pools): white with a feathered alpha edge
r = np.sqrt(((xx - N / 2 + 0.5) / (N / 2)) ** 2 + ((yy - N / 2 + 0.5) / (N / 2)) ** 2)
a = 1 - band(r, 0.55, 1.0)
Image.fromarray((np.dstack([np.ones_like(a), np.ones_like(a), np.ones_like(a), a]) * 255).astype(np.uint8), "RGBA") \
    .save(os.path.join(OUT, "soft.png")); print("soft")
# soft-edged rectangle (road ruts, lines with worn ends)
ax = 1 - band(np.abs(xx - N / 2 + 0.5) / (N / 2), 0.7, 1.0)
ay = 1 - band(np.abs(yy - N / 2 + 0.5) / (N / 2), 0.5, 1.0)
Image.fromarray((np.dstack([np.ones_like(ax)] * 3 + [ax * ay]) * 255).astype(np.uint8), "RGBA") \
    .save(os.path.join(OUT, "softrect.png")); print("softrect")
