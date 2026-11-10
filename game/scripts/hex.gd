class_name Hex
## Coordinates shared by the level renders and the game.
## plan (u, v): the 45-degree grid the rooms are laid out on.
## ground (x, y): metres, x to screen right, y north (away from the camera).
## screen: Godot pixels at 165 px per metre, camera ELEV_DEG above the ground (level/camera.json).
## Hexes are pointy-topped in ground space, 0.64 m apart (14 frames of the walk cycle).

const PPM := 165.0
const S := 0.6396
const R2 := 0.70710678
const COS30 := 0.8660254                  # hexagon geometry, not the camera
const ELEV_DEG := 47.0                     # must match level/camera.json (level.gd checks each level)
const SIN_E := 0.7313537                   # sin(47): ground depth on screen
const COS_E := 0.6819984                   # cos(47): height on screen
const VSCALE := COS_E / COS30              # screen heights relative to the old 30-degree view
const DIRS := [Vector2i(1, 0), Vector2i(1, -1), Vector2i(0, -1), Vector2i(-1, 0), Vector2i(-1, 1), Vector2i(0, 1)]


static func plan_to_ground(p: Vector2) -> Vector2:
	return Vector2((p.x - p.y) * R2, (p.x + p.y) * R2)


static func ground_to_plan(g: Vector2) -> Vector2:
	return Vector2((g.x + g.y) * R2, (g.y - g.x) * R2)


static func ground_to_screen(g: Vector2, z: float = 0.0) -> Vector2:
	return Vector2(g.x * PPM, -(g.y * SIN_E + z * COS_E) * PPM)


static func screen_to_ground(p: Vector2) -> Vector2:
	return Vector2(p.x / PPM, -p.y / (SIN_E * PPM))


static func plan_to_screen(p: Vector2, z: float = 0.0) -> Vector2:
	return ground_to_screen(plan_to_ground(p), z)


static func hex_to_ground(h: Vector2i) -> Vector2:
	return Vector2(S * (h.x + h.y * 0.5), -S * COS30 * h.y)


static func hex_to_screen(h: Vector2i) -> Vector2:
	return ground_to_screen(hex_to_ground(h))


static func hex_to_plan(h: Vector2i) -> Vector2:
	return ground_to_plan(hex_to_ground(h))


static func ground_to_hex(g: Vector2) -> Vector2i:
	var r := -g.y / (S * COS30)
	var q := g.x / S - r * 0.5
	return cube_round(q, r)


static func screen_to_hex(p: Vector2) -> Vector2i:
	return ground_to_hex(screen_to_ground(p))


static func cube_round(q: float, r: float) -> Vector2i:
	var s := -q - r
	var rq := roundf(q)
	var rr := roundf(r)
	var rs := roundf(s)
	var dq := absf(rq - q)
	var dr := absf(rr - r)
	var ds := absf(rs - s)
	if dq > dr and dq > ds:
		rq = -rr - rs
	elif dr > ds:
		rr = -rq - rs
	return Vector2i(int(rq), int(rr))


static func distance(a: Vector2i, b: Vector2i) -> int:
	var d := a - b
	return int((absi(d.x) + absi(d.y) + absi(d.x + d.y)) / 2)


static func dir_towards(from_g: Vector2, to_g: Vector2) -> int:
	var a := rad_to_deg(atan2(to_g.y - from_g.y, to_g.x - from_g.x))
	return posmod(int(roundf(a / 60.0)), 6)


static func hex_polygon(h: Vector2i, scale: float = 0.94) -> PackedVector2Array:
	var c := hex_to_ground(h)
	var rad := S / sqrt(3.0) * scale
	var pts := PackedVector2Array()
	for k in 6:
		var a := deg_to_rad(30.0 + 60.0 * k)
		pts.append(ground_to_screen(c + Vector2(cos(a), sin(a)) * rad))
	return pts


static func seg_intersect(p1: Vector2, p2: Vector2, q1: Vector2, q2: Vector2) -> bool:
	var r := p2 - p1
	var s := q2 - q1
	var den := r.cross(s)
	if absf(den) < 1e-9:
		return false
	var t := (q1 - p1).cross(s) / den
	var u := (q1 - p1).cross(r) / den
	return t > 0.0 and t < 1.0 and u >= 0.0 and u <= 1.0


static func point_seg_dist(p: Vector2, a: Vector2, b: Vector2) -> float:
	var ab := b - a
	var t := clampf((p - a).dot(ab) / maxf(ab.length_squared(), 1e-9), 0.0, 1.0)
	return p.distance_to(a + ab * t)


static func point_rect_dist(p: Vector2, r: Array) -> float:
	var dx := maxf(maxf(r[0] - p.x, 0.0), p.x - r[1])
	var dy := maxf(maxf(r[2] - p.y, 0.0), p.y - r[3])
	return Vector2(dx, dy).length()
