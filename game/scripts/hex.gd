class_name Hex
## Coordinates shared by the level renders and the game.
## plan (u, v): the 45-degree grid the rooms are laid out on.
## ground (x, y): metres, x to screen right, y north (away from the camera).
## screen: Godot pixels at 165 px per metre, camera ELEV_DEG above the ground (level/camera.json).

const PPM := 165.0
const R2 := 0.70710678
const ELEV_DEG := 47.0                     # must match level/camera.json (level.gd checks each level)
const SIN_E := 0.7313537                   # sin(47): ground depth on screen
const COS_E := 0.6819984                   # cos(47): height on screen
const VSCALE := COS_E / 0.8660254          # screen heights relative to the old 30-degree view
## Wasteland 3 style: square cells on the plan axes (the room walls), 8 neighbours. The grid is only
## drawn in combat; out of combat the player moves freely (paths are straightened, see Level.smooth).
## The names say "hex" for history: a "hex" is now one square cell, Vector2i(u, v) in plan cells.
const CELL := 0.64                        # the old hex spacing: same reach per AP, fits the narrow gaps
const DIRS := [Vector2i(1, 0), Vector2i(1, 1), Vector2i(0, 1), Vector2i(-1, 1), Vector2i(-1, 0), Vector2i(-1, -1), Vector2i(0, -1), Vector2i(1, -1)]
const HALF_DIRS := [Vector2i(1, 0), Vector2i(1, 1), Vector2i(0, 1), Vector2i(-1, 1)]   # each edge once


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


static func hex_to_plan(h: Vector2i) -> Vector2:
	return Vector2(h) * CELL


static func hex_to_ground(h: Vector2i) -> Vector2:
	return plan_to_ground(hex_to_plan(h))


static func hex_to_screen(h: Vector2i) -> Vector2:
	return ground_to_screen(hex_to_ground(h))


static func ground_to_hex(g: Vector2) -> Vector2i:
	var p := ground_to_plan(g) / CELL
	return Vector2i(int(roundf(p.x)), int(roundf(p.y)))


static func screen_to_hex(p: Vector2) -> Vector2i:
	return ground_to_hex(screen_to_ground(p))


## Grid distance in cells: a diagonal counts 1, every second diagonal 2 (about 1.5 on average).
static func distance(a: Vector2i, b: Vector2i) -> int:
	var dx := absi(a.x - b.x)
	var dy := absi(a.y - b.y)
	return maxi(dx, dy) + mini(dx, dy) / 2


## Action-point cost of walking a cell path starting at from: 1 per straight step, diagonals 1, 2, 1, 2...
static func step_costs(from: Vector2i, path: Array) -> Array:
	var out := []
	var prev := from
	var diag := 0
	for h in path:
		var d: Vector2i = h - prev
		if d.x != 0 and d.y != 0:
			diag += 1
			out.append(2 if diag % 2 == 0 else 1)
		else:
			out.append(1)
		prev = h
	return out


## How many steps of path the given action points pay for.
static func affordable(from: Vector2i, path: Array, ap: int) -> int:
	var n := 0
	var spent := 0
	for c in step_costs(from, path):
		if spent + c > ap:
			break
		spent += c
		n += 1
	return n


## Facing in degrees on the ground (0 = screen right, counter-clockwise), and the nearest of the
## six sprite directions the pre-rendered fallback sheets have.
static func angle_towards(from_g: Vector2, to_g: Vector2) -> float:
	return rad_to_deg(atan2(to_g.y - from_g.y, to_g.x - from_g.x))


static func dir_towards(from_g: Vector2, to_g: Vector2) -> int:
	return posmod(int(roundf(angle_towards(from_g, to_g) / 60.0)), 6)


## The cell outline on screen (a diamond: the grid runs along the walls, 45 degrees to the screen).
static func hex_polygon(h: Vector2i, scale: float = 0.94) -> PackedVector2Array:
	var c := hex_to_plan(h)
	var r := CELL * 0.5 * scale
	var pts := PackedVector2Array()
	for o in [Vector2(-r, -r), Vector2(r, -r), Vector2(r, r), Vector2(-r, r)]:
		pts.append(plan_to_screen(c + o))
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
