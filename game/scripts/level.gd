class_name Level
extends Node2D
## Builds a level from the Blender export: background, sorted props and doors, dark rooms,
## the hex grid with walls and doors, path finding and line of sight.

const T := 0.25
const WALL_CLEAR := 0.26
const DOOR_JAMB := 0.12

var data: Dictionary
var level_dir := ""
var sorted: Node2D
var marks: Node2D
var dark_layer: Node2D
var walkable := {}                  # Vector2i -> true
var room_of := {}                   # Vector2i -> room id
var astar := AStar2D.new()
var pid := {}                       # Vector2i -> astar id
var pieces: Array = []              # solid wall pieces: {a, b, door}
var door_edges := {}                # door id -> [[id_a, id_b], ...]
var doors := {}                     # door id -> {data, node, sprite, open, locked}
var props: Array = []               # {data, node, rect}
var blocked: Array = []             # plan rects
var dark := {}                      # room id -> {polys, props}
var pipe := {}
var wall_parts: Array = []           # {sprite, rect, y, a}: full-height wall strips
var pipe_node: Sprite2D
var water = null   # Array of the water particle emitters, made on first use


func build(dir: String, state: Dictionary) -> void:
	level_dir = dir
	data = JSON.parse_string(FileAccess.get_file_as_string(dir + "/level.json"))
	var bg := Sprite2D.new()
	bg.centered = false
	bg.texture = load(dir + "/" + data["bg"]["file"])
	bg.position = Vector2(data["bg"]["x0"], data["bg"]["y0"])
	add_child(bg)
	dark_layer = Node2D.new(); add_child(dark_layer)
	marks = Node2D.new(); add_child(marks)
	sorted = Node2D.new(); sorted.y_sort_enabled = true; add_child(sorted)

	for r in data["blocked"]:
		blocked.append(r)
	for p in data["props"]:
		var n := Node2D.new()
		n.position = Vector2(p["sort"][0], p["sort"][1])
		var s := Sprite2D.new()
		s.centered = false
		s.texture = load(dir + "/" + p["sprite"])
		s.position = Vector2(p["x0"], p["y0"]) - n.position
		n.add_child(s)
		sorted.add_child(n)
		var rect := Rect2(Vector2(p["x0"], p["y0"]), s.texture.get_size())
		props.append({"data": p, "node": n, "sprite": s, "rect": rect})
		blocked.append(_grow(p["footprint"], 0.08))

	for wp in data.get("wallparts", []):          # full-height walls, in strips that sort and fade
		var n := Node2D.new()
		n.position = Vector2(wp["sort"][0], wp["sort"][1])
		var s := Sprite2D.new()
		s.centered = false
		s.texture = load(dir + "/" + wp["sprite"])
		s.position = Vector2(wp["x0"], wp["y0"]) - n.position
		n.add_child(s)
		sorted.add_child(n)
		wall_parts.append({"sprite": s, "rect": Rect2(Vector2(wp["x0"], wp["y0"]), s.texture.get_size()),
						   "y": n.position.y, "a": 1.0})

	for d in data["doors"]:
		var n := Node2D.new()
		n.position = Vector2(d["sort"][0], d["sort"][1])
		var s := Sprite2D.new()
		s.centered = false
		n.add_child(s)
		sorted.add_child(n)
		var is_open: bool = state.get("door_" + d["id"], d["open"])
		var locked: bool = state.get("locked_" + d["id"], d.get("locked", false))
		doors[d["id"]] = {"data": d, "node": n, "sprite": s, "open": is_open, "locked": locked}
		_show_door(d["id"])

	if data.has("pipe"):
		pipe = data["pipe"]
		var n := Node2D.new()
		n.position = Vector2(pipe["sort"][0], pipe["sort"][1])
		pipe_node = Sprite2D.new()
		pipe_node.centered = false
		n.add_child(pipe_node)
		sorted.add_child(n)
		set_pipe(state.get("pipe_fixed", false))

	_build_walls()
	_build_grid()
	_build_dark(state)


func _grow(r: Array, m: float) -> Array:
	return [r[0] - m, r[1] + m, r[2] - m, r[3] + m]


# ------------------------------------------------------------------ doors and pipe
func _show_door(id: String) -> void:
	var d: Dictionary = doors[id]
	var st := "spr_open" if d["open"] else "spr_closed"
	var info: Dictionary = d["data"][st]
	d["sprite"].texture = load(level_dir + "/" + info["sprite"])
	d["sprite"].position = Vector2(info["x0"], info["y0"]) - d["node"].position


func set_door_open(id: String, open: bool) -> void:
	doors[id]["open"] = open
	_show_door(id)
	for e in door_edges.get(id, []):
		if open:
			astar.connect_points(e[0], e[1])
		elif astar.are_points_connected(e[0], e[1]):
			astar.disconnect_points(e[0], e[1])
	if open:
		for rid in dark.keys():
			if dark[rid]["door"] == id:
				reveal(rid)


# Fade the wall strips that stand in front of something you need to see (the player, the spot under
# the cursor, worms): strips drawn after it whose picture overlaps it go see-through, with a soft edge.
func fade_walls(foci: Array, dt: float) -> void:
	for wp in wall_parts:
		var r: Rect2 = wp["rect"]
		var target := 1.0
		for f in foci:
			var fr: Rect2 = f["rect"]
			if wp["y"] <= f["y"] + 1.0:              # strip is behind it: nothing to hide
				continue
			if r.position.y > fr.end.y or r.end.y < fr.position.y:
				continue
			var dx: float = abs(r.get_center().x - fr.get_center().x) - (r.size.x + fr.size.x) * 0.5
			var k: float = clamp((dx + 10.0) / 120.0, 0.0, 1.0)       # soft edge, 120 px wide
			target = min(target, lerp(0.16, 1.0, k * k * (3.0 - 2.0 * k)))
		var a: float = wp["a"]
		a = move_toward(a, target, dt * 4.0)
		if a != wp["a"]:
			wp["a"] = a
			wp["sprite"].modulate.a = a


func set_pipe(fixed: bool) -> void:
	var info: Dictionary = pipe["fixed" if fixed else "broken"]
	pipe_node.texture = load(level_dir + "/" + info["sprite"])
	pipe_node.position = Vector2(info["x0"], info["y0"]) - pipe_node.get_parent().position
	if water == null:
		_make_water()
	for p in water:
		p.emitting = not fixed


# Water from the bitten pipe: a jet of drops arcing down from the hole, a splash
# where it lands, and ripple rings spreading on the puddle (drawn on the floor, under the actors).
func _make_water() -> void:
	water = []
	# the bite is on the front of the heating flow, 0.34 m in front of the wall line
	var hole := Hex.plan_to_screen(Vector2(pipe["u"] + 0.02, pipe["v"] - 0.34), pipe.get("z", 0.45) - 0.01)
	var land := Hex.plan_to_screen(Vector2(pipe["u"] + 0.05, pipe["v"] - 0.83), 0.0)
	var t := 0.32                                         # flight time of a drop, seconds
	var g := 1100.0
	var v0 := Vector2((land.x - hole.x) / t, (land.y - hole.y - 0.5 * g * t * t) / t)
	var stream := WaterStream.new()                        # jet, droplets and splash, simulated and drawn here
	stream.hole = hole; stream.land = land; stream.v0 = v0; stream.g = g; stream.t = t
	stream.z_index = 5
	add_child(stream); water.append(stream)
	var rings := WaterRipples.new()                        # rings on the puddle, on the floor under the actors
	rings.position = land
	add_child(rings); move_child(rings, marks.get_index())
	water.append(rings)


class WaterStream extends Node2D:
	var hole := Vector2.ZERO
	var land := Vector2.ZERO
	var v0 := Vector2.ZERO
	var g := 1100.0
	var t := 0.32
	var emitting := true:
		set(value):
			emitting = value; visible = value
	var clock := 0.0
	const DROPS := 26
	const SPLASH := 14

	func _process(dt: float) -> void:
		clock += dt
		queue_redraw()

	func _at(s: float, spread: float) -> Vector2:
		return hole + v0 * s * spread + Vector2(0, 0.5 * g * s * s)

	func _draw() -> void:
		# the unbroken first part of the jet: a tapered arc that wobbles a little
		var n := 12
		var tc := t * 0.5
		var prev := hole
		for i in range(1, n + 1):
			var f := float(i) / n
			var p := _at(tc * f, 1.0) + Vector2(sin(clock * 37.0 + i * 1.7) * 0.9 * f, 0)
			draw_line(prev, p, Color(0.78, 0.88, 0.98, 0.6 * (1.0 - f * 0.5)), 5.0 * (1.0 - f * 0.45), true)
			draw_line(prev, p, Color(0.96, 0.98, 1.0, 0.85 * (1.0 - f * 0.7)), 1.6, true)
			prev = p
		# the jet breaking up into drops further along
		for k in DROPS:
			var h := fmod(k * 0.618034, 1.0)
			var f := fmod(clock / t + h, 1.0)
			if f < 0.35:
				continue
			var p := _at(t * f, 0.94 + 0.12 * fmod(k * 0.377, 1.0))
			draw_circle(p, 1.2 + 1.4 * fmod(k * 0.29, 1.0), Color(0.86, 0.93, 1.0, 0.75))
		# splash: short hops of spray where the jet hits the puddle
		for k in SPLASH:
			var h := fmod(k * 0.7548, 1.0)
			var life := 0.34
			var f := fmod(clock / life + h, 1.0)
			var ang := -PI * 0.5 + (fmod(k * 0.41, 1.0) - 0.5) * 2.2
			var sp := 50.0 + 70.0 * fmod(k * 0.53, 1.0)
			var tt := f * life
			var p := land + Vector2(cos(ang), sin(ang)) * sp * tt + Vector2(0, 0.5 * 700.0 * tt * tt)
			draw_circle(p, 0.9 + 0.8 * fmod(k * 0.31, 1.0), Color(0.9, 0.95, 1.0, 0.8 * (1.0 - f)))


class WaterRipples extends Node2D:
	var emitting := true:
		set(value):
			emitting = value; visible = value
	var clock := 0.0

	func _process(dt: float) -> void:
		clock += dt
		queue_redraw()

	func _draw() -> void:
		draw_set_transform(Vector2.ZERO, 0.0, Vector2(1.0, 0.5))      # flat on the floor
		for k in 4:
			var f := fmod(clock / 1.3 + k * 0.25, 1.0)
			var r := 6.0 + 46.0 * f
			var off := Vector2(sin(k * 2.1) * 8.0, cos(k * 1.3) * 10.0)
			draw_arc(off, r, 0.0, TAU, 40, Color(0.85, 0.92, 1.0, 0.42 * (1.0 - f)), 1.6, true)


# ------------------------------------------------------------------ walls and grid
func _build_walls() -> void:
	for w in data["walls"]:
		var a := Vector2(w["a"][0], w["a"][1])
		var b := Vector2(w["b"][0], w["b"][1])
		var along_u := is_equal_approx(a.y, b.y)
		var lo := minf(a.x, b.x) if along_u else minf(a.y, b.y)
		var hi := maxf(a.x, b.x) if along_u else maxf(a.y, b.y)
		var cur := lo - T / 2.0
		var ops: Array = w["openings"].duplicate()
		ops.sort_custom(func(x, y): return x[0] < y[0])
		for o in ops:
			_add_piece(along_u, a, cur, float(o[0]) + DOOR_JAMB, "")
			if o[2] != null:
				_add_piece(along_u, a, float(o[0]), float(o[1]), String(o[2]))
			cur = float(o[1]) - DOOR_JAMB
		_add_piece(along_u, a, cur, hi + T / 2.0, "")


func _add_piece(along_u: bool, a: Vector2, s0: float, s1: float, door: String) -> void:
	if s1 - s0 < 0.01:
		return
	var p0 := Vector2(s0, a.y) if along_u else Vector2(a.x, s0)
	var p1 := Vector2(s1, a.y) if along_u else Vector2(a.x, s1)
	pieces.append({"a": p0, "b": p1, "door": door})


func _in_room(p: Vector2) -> String:
	for r in data["rooms"]:
		var rr: Array = r["r"]
		if p.x > rr[0] and p.x < rr[1] and p.y > rr[2] and p.y < rr[3]:
			return r["id"]
	return ""


func _hex_ok(h: Vector2i) -> bool:
	var p := Hex.hex_to_plan(h)
	if _in_room(p) == "":
		return false
	for pc in pieces:
		if pc["door"] == "" and Hex.point_seg_dist(p, pc["a"], pc["b"]) < WALL_CLEAR:
			return false            # a doorway itself may hold a hex; crossing the door is an edge rule
	for r in blocked:
		if Hex.point_rect_dist(p, r) <= 0.0:
			return false
	return true


func _edge_door(a: Vector2i, b: Vector2i) -> String:
	## "" = open edge, "#" = blocked, otherwise the id of a door the edge passes through
	var pa := Hex.hex_to_plan(a)
	var pb := Hex.hex_to_plan(b)
	var through := ""
	for pc in pieces:
		if Hex.seg_intersect(pa, pb, pc["a"], pc["b"]):
			if pc["door"] == "":
				return "#"
			through = pc["door"]
	var mid := (pa + pb) * 0.5
	for r in blocked:
		if Hex.point_rect_dist(mid, r) <= 0.0:
			return "#"
	return through


func _build_grid() -> void:
	var bnd: Array = data["bounds"]
	var corners := [Vector2(bnd[0], bnd[2]), Vector2(bnd[0], bnd[3]), Vector2(bnd[1], bnd[2]), Vector2(bnd[1], bnd[3])]
	var qmin := 99999; var qmax := -99999; var rmin := 99999; var rmax := -99999
	for c in corners:
		var h := Hex.ground_to_hex(Hex.plan_to_ground(c))
		qmin = mini(qmin, h.x); qmax = maxi(qmax, h.x); rmin = mini(rmin, h.y); rmax = maxi(rmax, h.y)
	qmin -= 30; qmax += 30
	for r in range(rmin - 2, rmax + 3):
		for q in range(qmin, qmax + 1):
			var h := Vector2i(q, r)
			if _hex_ok(h):
				walkable[h] = true
				room_of[h] = _in_room(Hex.hex_to_plan(h))
				var id := astar.get_available_point_id()
				pid[h] = id
				astar.add_point(id, Hex.hex_to_ground(h))
	for h in walkable:
		for k in 3:                       # each edge once: directions 0, 1, 2
			var n: Vector2i = h + Hex.DIRS[k]
			if not walkable.has(n):
				continue
			var e := _edge_door(h, n)
			if e == "#":
				continue
			if e == "":
				astar.connect_points(pid[h], pid[n])
			else:
				if not door_edges.has(e):
					door_edges[e] = []
				door_edges[e].append([pid[h], pid[n]])
				if doors.has(e) and doors[e]["open"]:
					astar.connect_points(pid[h], pid[n])
	print("level ", data["level"], ": ", walkable.size(), " walkable hexes")


func find_path(from: Vector2i, to: Vector2i, occupied: Array = []) -> Array:
	if not pid.has(from) or not pid.has(to):
		return []
	for h in occupied:
		if pid.has(h) and h != from and h != to:
			astar.set_point_disabled(pid[h], true)
	var ids := astar.get_id_path(pid[from], pid[to])
	for h in occupied:
		if pid.has(h):
			astar.set_point_disabled(pid[h], false)
	var out: Array = []
	for i in range(1, ids.size()):
		out.append(Hex.ground_to_hex(astar.get_point_position(ids[i])))
	return out


func nearest_walkable(p_plan: Vector2, max_d: float = 1.5) -> Vector2i:
	var best := Vector2i(999999, 0)
	var bd := max_d
	for h in walkable:
		var d := Hex.hex_to_plan(h).distance_to(p_plan)
		if d < bd:
			bd = d; best = h
	return best


func line_of_sight(a: Vector2i, b: Vector2i) -> bool:
	var pa := Hex.hex_to_plan(a)
	var pb := Hex.hex_to_plan(b)
	for pc in pieces:
		if pc["door"] != "" and doors.has(pc["door"]) and doors[pc["door"]]["open"]:
			continue
		if Hex.seg_intersect(pa, pb, pc["a"], pc["b"]):
			return false
	return true


# ------------------------------------------------------------------ dark rooms
func _build_dark(state: Dictionary) -> void:
	for r in data["rooms"]:
		if not r.get("dark", false):
			continue
		var door_id := ""
		for d in data["doors"]:
			var dp := Vector2(d["u"], d["v"])
			var rr: Array = r["r"]
			if dp.x >= rr[0] and dp.x <= rr[1] and dp.y >= rr[2] - 0.01 and dp.y <= rr[3] + 0.01:
				door_id = d["id"]
		var entry := {"door": door_id, "polys": [], "props": []}
		dark[r["id"]] = entry
		if door_id != "" and doors.has(door_id) and doors[door_id]["open"]:
			continue
		var rr: Array = r["r"]
		var u0: float = rr[0] + T / 2; var u1: float = rr[1] - T / 2
		var v0: float = rr[2] + T / 2; var v1: float = rr[3] - T / 2
		var col := Color(0.035, 0.035, 0.045, 0.97)
		var floor_pts := [Vector2(u0, v0), Vector2(u1, v0), Vector2(u1, v1), Vector2(u0, v1)]
		var walls := [
			[Vector2(u0, v1), Vector2(u1, v1)],          # back wall (north)
			[Vector2(u1, v0), Vector2(u1, v1)],          # back wall (east)
		]
		var polys := [floor_pts.map(func(p): return Hex.plan_to_screen(p))]
		for w in walls:
			polys.append([Hex.plan_to_screen(w[0]), Hex.plan_to_screen(w[1]), Hex.plan_to_screen(w[1], 2.75), Hex.plan_to_screen(w[0], 2.75)])
		for pts in polys:
			var poly := Polygon2D.new()
			poly.polygon = PackedVector2Array(pts)
			poly.color = col
			dark_layer.add_child(poly)
			entry["polys"].append(poly)
		for p in props:
			var fp: Array = p["data"]["footprint"]
			var c := Vector2((fp[0] + fp[1]) / 2.0, (fp[2] + fp[3]) / 2.0)
			if c.x > rr[0] and c.x < rr[1] and c.y > rr[2] and c.y < rr[3]:
				p["sprite"].modulate = Color(0.06, 0.06, 0.07)
				entry["props"].append(p)


func reveal(rid: String) -> void:
	var entry: Dictionary = dark[rid]
	for poly in entry["polys"]:
		var tw := create_tween()
		tw.tween_property(poly, "modulate:a", 0.0, 1.2)
		tw.tween_callback(poly.queue_free)
	for p in entry["props"]:
		var tw := create_tween()
		tw.tween_property(p["sprite"], "modulate", Color.WHITE, 1.2)
	entry["polys"] = []
	entry["props"] = []


func is_dark(rid: String) -> bool:
	return dark.has(rid) and not dark[rid]["polys"].is_empty()


# ------------------------------------------------------------------ picking
## The interactable under a screen point: {kind, id, name, text, plan, ...}
func pick(screen: Vector2) -> Dictionary:
	var best := {}
	var best_sort := -INF
	for d in doors.values():
		var spr: Sprite2D = d["sprite"]
		var r := Rect2(d["node"].position + spr.position, spr.texture.get_size())
		if r.has_point(screen) and d["node"].position.y > best_sort:
			best_sort = d["node"].position.y
			best = {"kind": "door", "id": d["data"]["id"], "name": d["data"]["name"], "text": d["data"]["text"],
					"plan": Vector2(d["data"]["u"], d["data"]["v"])}
	if not pipe.is_empty():
		var r := Rect2(pipe_node.get_parent().position + pipe_node.position, pipe_node.texture.get_size()).grow(20)
		if r.has_point(screen):
			return {"kind": "pipe", "id": pipe["id"], "name": pipe["name"], "text": pipe["text"],
					"plan": Vector2(pipe["u"], pipe["v"] - 0.6)}
	if not best.is_empty():
		return best
	for p in props:
		var pd: Dictionary = p["data"]
		if not pd.has("name"):
			continue
		if p["rect"].has_point(screen) and _alpha_at(p["sprite"], screen - p["rect"].position) and p["node"].position.y > best_sort:
			var fp: Array = pd["footprint"]
			var rid := _in_room(Vector2((fp[0] + fp[1]) / 2.0, (fp[2] + fp[3]) / 2.0))
			if is_dark(rid):
				continue
			best_sort = p["node"].position.y
			best = {"kind": "toolbox" if pd.get("id", "") == "toolbox" else "prop", "id": pd.get("id", pd["name"]),
					"name": pd["name"], "text": pd["text"], "plan": Vector2((fp[0] + fp[1]) / 2.0, (fp[2] + fp[3]) / 2.0),
					"footprint": fp}
	if not best.is_empty():
		return best
	var g := Hex.screen_to_ground(screen)
	for s in data["stairs"]:
		var sp := Vector2(s["u"], s["v"])
		if Hex.plan_to_screen(sp).distance_to(screen) < 70:
			return {"kind": "stairs", "id": s["id"], "name": s["name"], "text": s["text"], "plan": sp, "to": s["to"], "arrive": s["arrive"]}
	for it in data["inspect"]:
		var ip := Vector2(it["u"], it["v"])
		if it.has("room") and is_dark(it["room"]):
			continue
		if Hex.plan_to_screen(ip, 1.3).distance_to(screen) < 60 or Hex.plan_to_screen(ip).distance_to(screen) < 50:
			return {"kind": "look", "id": it["id"], "name": it["name"], "text": it["text"], "plan": ip}
	return {}


static var _img_cache := {}


func _alpha_at(s: Sprite2D, local: Vector2) -> bool:
	var key := s.texture.resource_path
	if not _img_cache.has(key):
		_img_cache[key] = s.texture.get_image()
	var img: Image = _img_cache[key]
	if img == null:
		return true
	var x := int(local.x); var y := int(local.y)
	if x < 0 or y < 0 or x >= img.get_width() or y >= img.get_height():
		return false
	return img.get_pixel(x, y).a > 0.2


## Walkable hexes from which the player can reach an object.
func approach_hexes(target: Dictionary) -> Array:
	var out: Array = []
	var p: Vector2 = target["plan"]
	for h in walkable:
		var hp := Hex.hex_to_plan(h)
		var d: float
		if target.has("footprint"):
			d = Hex.point_rect_dist(hp, target["footprint"])
		else:
			d = hp.distance_to(p)
		if d < 0.95:
			out.append(h)
	return out
