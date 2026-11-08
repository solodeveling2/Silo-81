"""Export the pipe worm for live 3D in the game: worm.py builds its body from spine functions (no rig),
so every frame of every clip is exported as vertex positions + normals on one fixed topology, and
game/scripts/puppet3d.gd plays them as a mesh flipbook (same frames, same clock as the sprites).

Usage: python3 -I worm_live.py OUT_BASENAME        -> OUT.bin + OUT.json
Coordinates are written in Godot's axes (x, z, -y); the worm faces +X at rest (as in worm.py).
"""
import sys, os, json, runpy, struct
import numpy as np

OUT = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
tmp = OUT + "_scratch"
# run worm.py for its scene and pose functions only: an unknown clip name renders nothing
sys.argv = [os.path.join(HERE, "worm.py"), tmp, "__export_only__"]
g = runpy.run_path(os.path.join(HERE, "worm.py"), run_name="worm")
body_me, teeth_me, set_pose, ANIMS, LATCH = g["body_me"], g["teeth_me"], g["set_pose"], g["ANIMS"], g["LATCH"]


def tris(me):
    me.calc_loop_triangles()
    by = {}
    for t in me.loop_triangles:
        by.setdefault(t.material_index, []).extend(int(v) for v in t.vertices)
    return by


def mats(me):
    out = []
    for m in me.materials:
        if m.name.startswith("Ink"):
            out.append(None)
            continue
        ramp = next(n for n in m.node_tree.nodes if n.type == "VALTORGB")
        e = sorted(ramp.color_ramp.elements, key=lambda x: x.position)
        out.append({"name": m.name, "shade": list(e[0].color[:3]), "mid": list(e[1].color[:3]),
                    "lit": list(e[2].color[:3]), "t_mid": e[1].position, "t_lit": e[2].position})
    return out


def surfaces(me):
    ms = mats(me)
    return [{"material": ms[i], "indices": idx} for i, idx in sorted(tris(me).items()) if ms[i] is not None]


def to_godot(a):
    return np.stack([a[:, 0], a[:, 2], -a[:, 1]], 1)


meshes = {"body": body_me, "teeth": teeth_me}
side = {"fps_src": 24, "meshes": {}, "clips": {}, "forward": "+x", "outline_m": {"body": 0.011, "teeth": 0.003}}
for k, me in meshes.items():
    side["meshes"][k] = {"verts": len(me.vertices), "surfaces": surfaces(me)}
stride = sum(len(me.vertices) for me in meshes.values())
blob = bytearray()
frame = 0
for key, cfg in ANIMS.items():
    if key in ("chew", "release") and LATCH is None:
        continue
    n = cfg["frames"]
    side["clips"][key] = {"first": frame, "frames": n, "loop": cfg["loop"]}
    for i in range(n):
        set_pose(key, i, n)
        for me in meshes.values():
            me.update()
            co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co)
            no = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("normal", no)
            blob += to_godot(co.reshape(-1, 3)).astype(np.float32).tobytes()
            blob += np.clip(np.round(to_godot(no.reshape(-1, 3)) * 127), -127, 127).astype(np.int8).tobytes()
        frame += 1
side["frames"] = frame
side["frame_bytes"] = stride * 15
side["layout"] = "per frame, per mesh (body, teeth): float32 xyz * verts, then int8 normal xyz * verts"
open(OUT + ".bin", "wb").write(bytes(blob))
json.dump(side, open(OUT + ".json", "w"), indent=1)
print("exported", OUT, frame, "frames", len(blob) // 1024, "KB", {k: v["verts"] for k, v in side["meshes"].items()})
