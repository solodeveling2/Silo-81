"""Preview video of the packaged player sprites, using the same rules as the Godot demo:
the sprite animates in place and walk/run frames move the character by the stored step."""
import json, os, subprocess
from PIL import Image, ImageDraw, ImageFont

PKG = "pkg/Silo81_Player/characters/player_male"
data = json.load(open(os.path.join(PKG, "character.json")))
ATLAS = Image.open("/home/claude/silo81/Silo81_Assets/tilesets/silo81_floors_atlas.png").convert("RGBA")
W, H = 960, 640
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)

def tile(c, r):
    return ATLAS.crop((c * 128, r * 128, (c + 1) * 128, (r + 1) * 128))
# a big floor in world space; the camera follows the player like the Godot Camera2D
FW, FH = 4200, 3200
floor = Image.new("RGBA", (FW, FH), (24, 26, 26, 255))
plain = [(4, 1), (5, 1), (6, 1)]
for gy in range(-2, FH // 30 + 2):
    for gx in range(-2, FW // 120 + 2):
        c = plain[abs(gx * 3 + gy) % 3]
        if (gx * 7 + gy * 5) % 11 == 0:
            c = (2, 2)
        floor.alpha_composite(tile(*c), (gx * 120 + (60 if gy % 2 else 0) - 64, gy * 30 - 64))
floor.alpha_composite(Image.new("RGBA", (FW, FH), (0, 0, 0, 50)))
ORIGIN = (FW // 2, FH // 2)

cache = {}
def frame(anim, d, i):
    key = (anim, d)
    if key not in cache:
        info = data["animations"][anim]["directions"][str(d)]
        cache[key] = (Image.open(os.path.join(PKG, info["sheet"])).convert("RGBA"), info)
    sheet, info = cache[key]
    fw, fh = info["frame_size"]; cols = info["columns"]
    return sheet.crop(((i % cols) * fw, (i // cols) * fh, (i % cols + 1) * fw, (i // cols + 1) * fh)), info

plan = [("walk", d, 56) for d in range(6)] + [("run", d, 15) for d in range(6)] + \
       [("idle", 4, 48), ("pistol_idle", 5, 40), ("pistol_attack", 5, None), ("pistol_attack", 0, None),
        ("pistol_attack", 4, None), ("hit", 4, None), ("death", 4, None)]
os.makedirs("preview", exist_ok=True)
for f in os.listdir("preview"):
    os.remove(os.path.join("preview", f))
pos = [0.0, 0.0]; cam = [0.0, 0.0]; k = 0
for anim, d, count in plan:
    info_a = data["animations"][anim]
    n = count or info_a["frames"]
    repeat = 24 // info_a["fps"]                      # idle plays at 12 fps in a 24 fps video
    hold = 18 if anim in ("fall", "death") else 0
    for i in range(n + hold):
        fi = min(i, info_a["frames"] - 1) % info_a["frames"]
        spr, info = frame(anim, d, fi)
        for _ in range(repeat):
            cam[0] += (pos[0] - cam[0]) * 0.12; cam[1] += (pos[1] - cam[1]) * 0.12
            cx, cy = ORIGIN[0] + cam[0] - W / 2, ORIGIN[1] + cam[1] - H * 0.74
            view = floor.crop((int(cx), int(cy), int(cx) + W, int(cy) + H))
            ax, ay = info["feet_anchor"]
            view.alpha_composite(spr, (int(round(ORIGIN[0] + pos[0] - cx - ax)), int(round(ORIGIN[1] + pos[1] - cy - ay))))
            dr = ImageDraw.Draw(view)
            dr.rectangle((0, 0, W, 64), fill=(16, 17, 17, 230))
            dr.text((16, 8), f"{anim}  ·  direction {d}", font=font, fill=(240, 236, 220, 255))
            dr.text((16, 36), "Silo 81 player: Tripo model, Quaternius pistol animations, rendered in Blender, frame-synced movement",
                    font=small, fill=(175, 172, 160, 255))
            view.convert("RGB").save(f"preview/f{k:05d}.png"); k += 1
        if anim in ("walk", "run") and i < n:
            s = info["step_px"]; pos[0] += s[0]; pos[1] += s[1]
print("frames", k, "end position", [round(v, 2) for v in pos])
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "24", "-i", "preview/f%05d.png",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                "silo81_player_preview.mp4"], check=True)
