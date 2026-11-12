class_name Level
extends Node2D
## Builds a level from the Blender export: background, sorted props and doors, dark rooms,
## the hex grid with walls and doors, path finding and line of sight.

signal room_entered(room_id: String)
signal room_exited(room_id: String)

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
var room_bounds := {}               # room id -> [u0, u1, v0, v1]
var room_groups := {}               # room id -> Array[String] of open-connected room ids
var room_walls := {}                # room id -> Array of foreground wall strip dicts
var current_room := ""              # active RoomID the player is currently inside
var active_room_ids := {}           # room_id -> true for current_room and its open-connected sub-zones
var astar := AStar2D.new()
var pid := {}                       # Vector2i -> astar id
var pieces: Array = []              # solid wall pieces: {a, b, door}
var door_edges := {}                # door id -> [[id_a, id_b], ...]
var doors := {}                     # door id -> {data, node, sprite, open, locked, room_id, fade}
var props: Array = []               # {data, node, rect}
var blocked: Array = []             # plan rects
var dark := {}                      # room id -> {polys, props}
var pipe := {}
var wall_parts: Array = []          # {sprite, mat, rect, y, sort, wall, room_id, fade, cut, alpha}
var pipe_node: Sprite2D
var water = null   # Array of the water particle emitters, made on first use
var bg_rect := Rect2()                # screen rectangle the ground covers (camera limits)
var creatures: Array = []  # live 3D animals (Puppet3D), e.g. Junk Town goats: {p, facing, phase}
var grazers: Array = []   # {s: Sprite2D, phase: float} — goat heads nodding while they eat


const GROUND_PX_PER_M := 128.0           # texel density of game/levels/_ground textures
var _ground_tex := {}


func _gtex(name: String) -> Texture2D:
	if not _ground_tex.has(name):
		_ground_tex[name] = _load_tex("res://levels/_ground/%s.png" % name)
	return _ground_tex[name]


## The outdoor ground: tiling textures on plan rectangles, soft decals, snow drifts and lamp pools,
## in the level's light (docs/VISUAL_DIRECTION.md). Everything here lies under the sorted sprites.
func _build_ground(G: Dictionary) -> void:
	var holder := Node2D.new()
	add_child(holder)
	var amb := Color(G.get("ambient", [1, 1, 1])[0], G.get("ambient", [1, 1, 1])[1], G.get("ambient", [1, 1, 1])[2])
	var floors: Array = G.get("floors", []).duplicate()
	floors.sort_custom(func(a, b): return int(a["layer"]) < int(b["layer"]))
	for f in floors:
		var r: Array = f["r"]
		var pts := PackedVector2Array(); var uvs := PackedVector2Array()
		for c in [Vector2(r[0], r[2]), Vector2(r[1], r[2]), Vector2(r[1], r[3]), Vector2(r[0], r[3])]:
			pts.append(Hex.plan_to_screen(c))
			uvs.append(Vector2(c.x, -c.y) * GROUND_PX_PER_M)
		var poly := Polygon2D.new()
		poly.polygon = pts; poly.uv = uvs
		poly.texture = _gtex(str(f["tex"]))
		poly.texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED
		var t: Array = f.get("tint", [1, 1, 1])
		poly.color = Color(t[0] * amb.r, t[1] * amb.g, t[2] * amb.b)
		holder.add_child(poly)
	var patches: Array = G.get("patches", []).duplicate()
	patches.sort_custom(func(a, b): return int(a["layer"]) < int(b["layer"]))
	for pt in patches:
		var r: Array = pt["r"]
		var c := Vector2((r[0] + r[1]) * 0.5, (r[2] + r[3]) * 0.5)
		var hw := (float(r[1]) - float(r[0])) * 0.5; var hh := (float(r[3]) - float(r[2])) * 0.5
		var rot := deg_to_rad(float(pt.get("ang", 0.0)))
		var pts := PackedVector2Array(); var uvs := PackedVector2Array()
		var tex := _gtex(str(pt.get("tex", "softrect")))
		var ts := tex.get_size()
		for k in [[-1, -1, 0, 0], [1, -1, 1, 0], [1, 1, 1, 1], [-1, 1, 0, 1]]:
			var off := Vector2(k[0] * hw, k[1] * hh).rotated(rot)
			pts.append(Hex.plan_to_screen(c + off)); uvs.append(Vector2(k[2], k[3]) * ts)
		var poly := Polygon2D.new()
		poly.polygon = pts; poly.uv = uvs; poly.texture = tex
		var col: Array = pt["rgb"]
		poly.color = Color(col[0] * amb.r, col[1] * amb.g, col[2] * amb.b, float(pt.get("a", 0.85)))
		holder.add_child(poly)
	for md in G.get("mounds", []):
		_mound(holder, Vector2(md[0], md[1]), float(md[2]), float(md[3]), float(md[4]), amb)
	var soft := _gtex("soft")
	if not G.get("smoke", []).is_empty():               # smoke from barrels and chimneys, drifting with the wind
		var sky := Node2D.new()
		sky.z_index = 40                                    # over the props
		add_child.call_deferred(sky)
		for sm in G["smoke"]:
			var em := CPUParticles2D.new()
			em.texture = soft
			em.amount = 10
			em.lifetime = 5.0
			em.preprocess = 5.0
			em.position = Hex.plan_to_screen(Vector2(sm["u"], sm["v"]), float(sm["z"]))
			em.direction = Vector2(0.15, -1.0)
			em.spread = 12.0
			em.initial_velocity_min = 22.0; em.initial_velocity_max = 34.0
			em.gravity = Vector2(14.0, -6.0)
			var k := float(sm.get("k", 1.0))
			em.scale_amount_min = 0.12 * k; em.scale_amount_max = 0.2 * k
			var sc := Curve.new()                             # puff: swells, then thins away to nothing
			sc.add_point(Vector2(0.0, 0.25)); sc.add_point(Vector2(0.55, 1.0)); sc.add_point(Vector2(1.0, 0.0))
			em.scale_amount_curve = sc
			em.color = Color(0.38, 0.38, 0.40, 0.32 * k)          # (a colour ramp hides the particles in this scene)
			sky.add_child(em)
	for pl in G.get("pools", []):
		var spr := Sprite2D.new()
		spr.texture = soft
		var mat := CanvasItemMaterial.new(); mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		spr.material = mat
		var rad := float(pl["r"]) * 0.8 * Hex.PPM
		spr.scale = Vector2(rad * 2.0 / soft.get_width(), rad * 2.0 * Hex.SIN_E / soft.get_height())
		spr.position = Hex.plan_to_screen(Vector2(pl["u"], pl["v"]))
		var lc: Array = pl["rgb"]
		spr.modulate = Color(lc[0] * 0.13, lc[1] * 0.1, lc[2] * 0.06)
		holder.add_child(spr)


## A snow drift: an ellipse dome in three toon bands (shade rim, mid, lit cap towards the key light),
## the cap raised by its height so it reads as a mound from the 47-degree camera.
func _mound(parent: Node2D, c: Vector2, ru: float, rv: float, h: float, amb: Color) -> void:
	var lift := Vector2(0, -h * Hex.COS_E * Hex.PPM)
	var key := Vector2(-0.22, 0.0)                      # the cap leans to the lit side (the key comes from -u in plan)
	var bands := [[1.0, 0.0, Color(0.76, 0.80, 0.86)], [0.82, 0.55, Color(0.85, 0.89, 0.94)], [0.55, 0.9, Color(0.91, 0.94, 0.98)]]   # final colours, matched to the lit snow (no ambient: it pushed them blue)
	for b in bands:
		var k: float = b[0]
		var up: float = b[1]
		var pts := PackedVector2Array()
		var cc := c + Vector2(key.x * ru, key.y * rv) * (1.0 - k) * 2.0
		for i in 24:
			var a := TAU * i / 24.0
			pts.append(Hex.plan_to_screen(cc + Vector2(cos(a) * ru * k, sin(a) * rv * k)) + lift * up)
		var poly := Polygon2D.new()
		poly.polygon = pts
		var col: Color = b[2]
		poly.color = col
		poly.antialiased = true
		parent.add_child(poly)


static func _load_tex(path: String) -> Texture2D:
	if ResourceLoader.exists(path):
		var res = load(path)
		if res is Texture2D:
			return res
	var global_path := ProjectSettings.globalize_path(path)
	if FileAccess.file_exists(global_path):
		var img := Image.load_from_file(global_path)
		if img:
			return ImageTexture.create_from_image(img)
	elif FileAccess.file_exists(path):
		var img := Image.load_from_file(path)
		if img:
			return ImageTexture.create_from_image(img)
	return null


func build(dir: String, state: Dictionary) -> void:
	level_dir = dir
	data = JSON.parse_string(FileAccess.get_file_as_string(dir + "/level.json"))
	if abs(float(data.get("elev_deg", 30.0)) - Hex.ELEV_DEG) > 0.01:
		push_warning("%s was rendered at %s degrees but the game projects at %s: rebuild it" % [dir, data.get("elev_deg", 30.0), Hex.ELEV_DEG])
	var bgd: Dictionary = data["bg"]
	if bgd.has("none"):                          # outdoors: Godot draws the ground (_build_ground)
		_build_ground(data.get("ground", {}))
		bg_rect = Rect2(bgd["x0"], bgd["y0"], bgd["w"], bgd["h"])
	elif bgd.has("tiles"):                         # big outdoor level: ground in tiles, rendered at a lower resolution
		var holder := Node2D.new()
		add_child(holder)
		var k := float(bgd.get("scale", 1.0))
		for t in bgd["tiles"]:
			var ts := Sprite2D.new()
			ts.centered = false
			ts.texture = _load_tex(dir + "/" + t["file"])
			ts.position = Vector2(t["x0"], t["y0"])
			ts.scale = Vector2(k, k)
			holder.add_child(ts)
		bg_rect = Rect2(bgd["x0"], bgd["y0"], bgd["w"], bgd["h"])
	else:
		var bg := Sprite2D.new()
		bg.centered = false
		bg.texture = _load_tex(dir + "/" + bgd["file"])
		bg.position = Vector2(bgd["x0"], bgd["y0"])
		add_child(bg)
		bg_rect = Rect2(bg.position, bg.texture.get_size())
	dark_layer = Node2D.new(); add_child(dark_layer)
	marks = Node2D.new(); add_child(marks)
	sorted = Node2D.new(); sorted.y_sort_enabled = true; add_child(sorted)

	for r in data["blocked"]:
		blocked.append(r)
	var sk := 1.0 / float(data.get("sprite_scale", 1.0))
	for p in data["props"]:
		var n := Node2D.new()
		n.position = Vector2(p["sort"][0], p["sort"][1])
		var s := Sprite2D.new()
		s.centered = false
		s.texture = _load_tex(dir + "/" + p["sprite"])
		s.scale = Vector2(sk, sk)
		s.position = Vector2(p["x0"], p["y0"]) - n.position
		n.add_child(s)
		sorted.add_child(n)
		if p.get("type", "") == "goat_head":
			# pivot the head at the neck (bottom centre) so it can nod without drifting
			var sz: Vector2 = s.texture.get_size()
			var piv := Vector2(p["x0"] + sz.x * 0.5, p["y0"] + sz.y * 1.00)
			s.position = piv - n.position
			s.offset = Vector2(-sz.x * 0.5, -sz.y * 1.00)
			grazers.append({"s": s, "phase": float(p["x0"]) * 0.013})
		var rect := Rect2(Vector2(p["x0"], p["y0"]), s.texture.get_size() * sk)
		props.append({"data": p, "node": n, "sprite": s, "rect": rect})
		blocked.append(_grow(p["footprint"], 0.08))

	for c in data.get("creatures", []):           # live 3D animals and townsfolk (CLAUDE.md: anything that moves is 3D)
		var base: String
		if c["kind"] == "person":                 # the civilian body in its own coat colour and warm skin
			base = "res://characters/tibor_3d/tibor"
		else:
			base = "res://characters/%s_3d/%s_%s" % [c["kind"], c["kind"], "piebald" if creatures.size() % 3 == 1 else "brown"]
		if not FileAccess.file_exists(base + ".json"):
			continue
		var pup := Puppet3D.new()
		pup.setup(base + ".glb", base + ".json")
		if c.has("coat"):
			pup.set_duotone(Color(c["coat"][0], c["coat"][1], c["coat"][2]), Color(c["skin"][0], c["skin"][1], c["skin"][2]), 0.0)
		var cn := Node2D.new()
		cn.position = Hex.plan_to_screen(Vector2(c["u"], c["v"]))
		cn.add_child(pup)
		sorted.add_child(cn)
		var home := Hex.plan_to_ground(Vector2(c["u"], c["v"]))
		var area := []                            # the pen it lives in (plan footprint), if any
		for pr in data.get("props", []):
			if pr.get("type", "") == "animal_pen":
				var fp: Array = pr["footprint"]
				if Hex.point_rect_dist(Vector2(c["u"], c["v"]), fp) < 1.0:
					area = [fp[0] + 0.45, fp[1] - 0.45, fp[2] + 0.45, fp[3] - 0.45]
		creatures.append({"p": pup, "n": cn, "facing": float(c.get("facing", 0.0)), "phase": float(c.get("phase", 0.0)),
						  "g": home, "home": home, "area": area, "walks": pup.cfg.get("clips", {}).has("walk"), "state": "graze",
						  "timer": 3.0 + float(c.get("phase", 0.0)), "target": home, "t": 0.0,
						  "speed": float(pup.cfg.get("walk_m_per_frame", 0.025)) * 24.0})

	for wp in data.get("wallparts", []):          # full-height walls, in strips that sort and fade
		var n := Node2D.new()
		n.position = Vector2(wp["sort"][0], wp["sort"][1])
		var s := Sprite2D.new()
		s.centered = false
		s.texture = _load_tex(dir + "/" + wp["sprite"])
		s.position = Vector2(wp["x0"], wp["y0"]) - n.position
		n.add_child(s)
		sorted.add_child(n)
		var mat := ShaderMaterial.new()
		mat.shader = WALL_CUT
		s.material = mat
		wall_parts.append({"sprite": s, "mat": mat, "rect": Rect2(Vector2(wp["x0"], wp["y0"]), s.texture.get_size()),
						   "y": n.position.y, "sort": n.position, "wall": int(wp.get("wall", -1)), "cut": WALL_FULL_PX})

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

	if data.get("level", "") == "L4E":
		var steam := SteamLeaks.new()
		steam.z_index = 6
		add_child(steam)

	_build_walls()
	_build_grid()
	_prep_wall_cuts()
	_build_dark(state)


func _grow(r: Array, m: float) -> Array:
	return [r[0] - m, r[1] + m, r[2] - m, r[3] + m]


# ------------------------------------------------------------------ doors and pipe
func _show_door(id: String) -> void:
	var d: Dictionary = doors[id]
	var st := "spr_open" if d["open"] else "spr_closed"
	var info: Dictionary = d["data"][st]
	d["sprite"].texture = _load_tex(level_dir + "/" + info["sprite"])
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


# ---------------------------------------------------------------- room-based wall occlusion & fade
# Foreground walls (South / South-East -v and South-West -u camera-facing walls that obscure a room's
# interior floor) are tagged with their corresponding RoomID. Entering a room smoothly fades and cuts
# all of that room's foreground walls over FADE_DURATION (~0.25s) to WALL_FADE_ALPHA (~0.20) so all
# interior props, shelves, and containers against camera-facing walls are immediately visible.
# North/rear background walls remain permanently opaque (alpha = 1.0).
const PX_PER_M := Hex.PPM * Hex.COS_E          # screen px per metre of height
const WALL_FULL_PX := 2.7 * PX_PER_M + 40.0  # above the wall top: nothing cut
const WALL_STUB_PX := 0.35 * PX_PER_M        # low wall base height kept when room foreground wall fades
const WALL_FADE_ALPHA := 0.20                # target alpha (~0.15 - 0.25) for active room foreground walls
const FADE_DURATION := 0.25                  # smooth transition duration (~0.2s - 0.3s)
const ROOM_ENTER_MARGIN := 0.14              # m inset inside room bounds required to trigger entering across a doorway
const ROOM_EXIT_HYSTERESIS := 0.28           # m hysteresis buffer outside room bounds before exiting (prevents doorway flicker)
const WALL_CUT := preload("res://scripts/wall_cut.gdshader")


func _build_room_triggers() -> void:
	"""Build per-room bounding boxes and group adjacent room floor rects that have no wall between them."""
	room_bounds.clear()
	room_groups.clear()
	room_walls.clear()
	var rooms: Array = data["rooms"]
	var walls: Array = data["walls"]
	var adj := {}
	for r in rooms:
		var rid: String = r["id"]
		room_bounds[rid] = r["r"]
		room_walls[rid] = []
		adj[rid] = {rid: true}
	for i in rooms.size():
		for j in range(i + 1, rooms.size()):
			var id1: String = rooms[i]["id"]
			var id2: String = rooms[j]["id"]
			var b1: Array = rooms[i]["r"]
			var b2: Array = rooms[j]["r"]
			# Shared u boundary (vertical in plan space)
			var u_shared := INF
			if absf(float(b1[1]) - float(b2[0])) < 0.05:
				u_shared = float(b1[1])
			elif absf(float(b1[0]) - float(b2[1])) < 0.05:
				u_shared = float(b1[0])
			if u_shared != INF:
				var vlo := maxf(float(b1[2]), float(b2[2]))
				var vhi := minf(float(b1[3]), float(b2[3]))
				if vhi - vlo > 0.5:
					var has_wall := false
					for w in walls:
						var ua := float(w["a"][0]); var va := float(w["a"][1])
						var ub := float(w["b"][0]); var vb := float(w["b"][1])
						if absf(ua - ub) < 1e-4 and absf(ua - u_shared) < 0.20:
							if minf(vhi, maxf(va, vb)) - maxf(vlo, minf(va, vb)) > 0.5:
								has_wall = true
								break
					if not has_wall:
						adj[id1][id2] = true
						adj[id2][id1] = true
			# Shared v boundary (horizontal in plan space)
			var v_shared := INF
			if absf(float(b1[3]) - float(b2[2])) < 0.05:
				v_shared = float(b1[3])
			elif absf(float(b1[2]) - float(b2[3])) < 0.05:
				v_shared = float(b1[2])
			if v_shared != INF:
				var ulo := maxf(float(b1[0]), float(b2[0]))
				var uhi := minf(float(b1[1]), float(b2[1]))
				if uhi - ulo > 0.5:
					var has_wall := false
					for w in walls:
						var ua := float(w["a"][0]); var va := float(w["a"][1])
						var ub := float(w["b"][0]); var vb := float(w["b"][1])
						if absf(va - vb) < 1e-4 and absf(va - v_shared) < 0.20:
							if minf(uhi, maxf(ua, ub)) - maxf(ulo, minf(ua, ub)) > 0.5:
								has_wall = true
								break
					if not has_wall:
						adj[id1][id2] = true
						adj[id2][id1] = true
	# Transitive closure for connected open room zones (e.g. L4E heat_entry + heat_hall + heat_bay)
	for k in adj.keys():
		for i in adj.keys():
			if adj[i].has(k):
				for m in adj[k].keys():
					adj[i][m] = true
	for rid in adj.keys():
		room_groups[rid] = adj[rid].keys()


func _tag_strip_room(w: Dictionary, pu: float, pv: float) -> String:
	"""Associate a foreground wall strip with the RoomID whose interior floor it occludes.
	Returns '' if the wall segment is a North/East rear background wall (stays permanently opaque)."""
	var ua := float(w["a"][0]); var va := float(w["a"][1])
	var ub := float(w["b"][0]); var vb := float(w["b"][1])
	var along_u := is_equal_approx(va, vb)
	var rooms: Array = data["rooms"]
	if along_u:
		var lo := minf(ua, ub)
		var hi := maxf(ua, ub)
		var wv := va
		var u_clamped := clampf(pu, lo + 0.05, hi - 0.05)
		var cands: Array = []
		for r in rooms:
			var rr: Array = r["r"]
			# A wall along u at v = wv is on the camera-facing South-East (-v) side of a room when rr[2] (v0) == wv
			if absf(float(rr[2]) - wv) < 0.25 and minf(float(rr[1]), hi) - maxf(float(rr[0]), lo) > 0.2:
				cands.append(r)
		for r in cands:
			var rr: Array = r["r"]
			if u_clamped >= float(rr[0]) - 0.02 and u_clamped <= float(rr[1]) + 0.02:
				return String(r["id"])
		for r in cands:
			var rr: Array = r["r"]
			if u_clamped >= float(rr[0]) - 0.35 and u_clamped <= float(rr[1]) + 0.35:
				return String(r["id"])
	else:
		var lo := minf(va, vb)
		var hi := maxf(va, vb)
		var wu := ua
		var v_clamped := clampf(pv, lo + 0.05, hi - 0.05)
		var cands: Array = []
		for r in rooms:
			var rr: Array = r["r"]
			# A wall along v at u = wu is on the camera-facing South-West (-u) side of a room when rr[0] (u0) == wu
			if absf(float(rr[0]) - wu) < 0.25 and minf(float(rr[3]), hi) - maxf(float(rr[2]), lo) > 0.2:
				cands.append(r)
		for r in cands:
			var rr: Array = r["r"]
			if v_clamped >= float(rr[2]) - 0.02 and v_clamped <= float(rr[3]) + 0.02:
				return String(r["id"])
		for r in cands:
			var rr: Array = r["r"]
			if v_clamped >= float(rr[2]) - 0.35 and v_clamped <= float(rr[3]) + 0.35:
				return String(r["id"])
	# Corner-extension check: if a wall segment has no room directly behind its base but meets a room's
	# South corner (e.g. L2 wall [-4.2, 1.4]->[0.6, 1.4] meeting room_2_1 at (0.6, 1.4)), its upper
	# height projects along (pu + s, pv + s) across that room's interior floor and South-West wall props.
	for s in [0.4, 0.8, 1.2, 1.6]:
		var hit := _in_room(Vector2(pu + s, pv + s))
		if hit != "":
			var rr: Array = room_bounds[hit]
			if (along_u and absf(float(rr[2]) - va) < 0.25) or ((not along_u) and absf(float(rr[0]) - ua) < 0.25):
				return hit
	return ""


func _prep_wall_cuts() -> void:
	"""Tag each foreground wall strip and door with its occluded RoomID and configure its cutaway shader."""
	_build_room_triggers()
	var front_walls: Array = []
	for w in data["walls"]:
		if float(w["h"]) < 2.65:
			front_walls.append(w)
	var by_wall := {}
	for wp in wall_parts:
		if not by_wall.has(wp["wall"]):
			by_wall[wp["wall"]] = []
		by_wall[wp["wall"]].append(wp)
	for k in by_wall:
		var strips: Array = by_wall[k]
		strips.sort_custom(func(a, b): return a["sort"].x < b["sort"].x)
		for i in strips.size():
			strips[i]["left"] = strips[i - 1] if i > 0 else null
			strips[i]["right"] = strips[i + 1] if i < strips.size() - 1 else null
		var w_idx := int(k)
		var has_w := w_idx >= 0 and w_idx < front_walls.size()
		var w: Dictionary = front_walls[w_idx] if has_w else {}
		var along_u := true
		var base_screen := Vector2.ZERO
		if has_w:
			var a := Vector2(float(w["a"][0]), float(w["a"][1]))
			var b := Vector2(float(w["b"][0]), float(w["b"][1]))
			along_u = is_equal_approx(a.y, b.y)
			base_screen = Hex.plan_to_screen(a)
		var slope := -Hex.SIN_E if along_u else Hex.SIN_E
		for wp in strips:
			var p_plan := Hex.ground_to_plan(Hex.screen_to_ground(wp["sort"]))
			var rid := _tag_strip_room(w, p_plan.x, p_plan.y) if has_w else _in_room(p_plan + (Vector2(0.0, 0.28) if slope < 0.0 else Vector2(0.28, 0.0)))
			wp["room_id"] = rid
			wp["front_of"] = rid
			wp["fade"] = 0.0
			wp["cut"] = WALL_FULL_PX
			wp["alpha"] = 1.0
			if rid != "" and room_walls.has(rid):
				room_walls[rid].append(wp)
			var m: ShaderMaterial = wp["mat"]
			m.set_shader_parameter("origin", wp["rect"].position)
			m.set_shader_parameter("size", wp["rect"].size)
			m.set_shader_parameter("base", base_screen if has_w else wp["sort"])
			m.set_shader_parameter("slope", slope)
			m.set_shader_parameter("cut", WALL_FULL_PX)
			m.set_shader_parameter("alpha", 1.0)
	# Tag doors mounted in foreground walls so they fade alongside their wall
	for did in doors.keys():
		var d: Dictionary = doors[did]
		var dd: Dictionary = d["data"]
		var dp := Vector2(float(dd["u"]), float(dd["v"]))
		var rid := ""
		for w in front_walls:
			var a := Vector2(float(w["a"][0]), float(w["a"][1]))
			var b := Vector2(float(w["b"][0]), float(w["b"][1]))
			if Hex.point_seg_dist(dp, a, b) < 0.25:
				rid = _tag_strip_room(w, dp.x, dp.y)
				break
		d["room_id"] = rid
		d["fade"] = 0.0


func _point_in_rect_margin(p: Vector2, rr: Array, margin: float) -> bool:
	"""margin > 0 shrinks the rect (for enter checks); margin < 0 expands the rect (for exit hysteresis)."""
	return p.x >= float(rr[0]) + margin and p.x <= float(rr[1]) - margin and p.y >= float(rr[2]) + margin and p.y <= float(rr[3]) - margin


func _on_room_enter(room_id: String) -> void:
	active_room_ids.clear()
	for rid in room_groups.get(room_id, [room_id]):
		active_room_ids[rid] = true
	room_entered.emit(room_id)


func _on_room_exit(room_id: String) -> void:
	room_exited.emit(room_id)


func update_player_room(player_plan: Vector2, fallback_hex: Vector2i = Vector2i(999999, 0)) -> String:
	"""Track when the player enters or exits a room zone, with doorway hysteresis to prevent flickering."""
	var next_room := current_room
	if current_room != "" and room_bounds.has(current_room):
		# Check if the player has stepped past ROOM_ENTER_MARGIN into a different room
		var entered_other := ""
		for r in data["rooms"]:
			var rid: String = r["id"]
			if rid == current_room:
				continue
			# Open-connected floor rects (no wall between them) require no doorway inset
			var margin := 0.0 if active_room_ids.has(rid) else ROOM_ENTER_MARGIN
			if _point_in_rect_margin(player_plan, r["r"], margin):
				entered_other = rid
				break
		if entered_other != "":
			next_room = entered_other
		elif _point_in_rect_margin(player_plan, room_bounds[current_room], -ROOM_EXIT_HYSTERESIS):
			# Still within current room's hysteresis buffer: hold current_room to avoid threshold flicker
			next_room = current_room
		else:
			next_room = _in_room(player_plan)
	else:
		for r in data["rooms"]:
			if _point_in_rect_margin(player_plan, r["r"], ROOM_ENTER_MARGIN):
				next_room = String(r["id"])
				break
		if next_room == "":
			next_room = _in_room(player_plan)
		if next_room == "" and room_of.has(fallback_hex):
			next_room = String(room_of[fallback_hex])

	if next_room != current_room:
		if current_room != "":
			_on_room_exit(current_room)
		current_room = next_room
		if current_room != "":
			_on_room_enter(current_room)
		else:
			active_room_ids.clear()
	return current_room


func fade_walls(_foci: Array, dt: float, active_room: String = "") -> void:
	"""Smoothly fade foreground walls of the active room (alpha 1.0 -> WALL_FADE_ALPHA, cut -> WALL_STUB_PX)
	over FADE_DURATION (~0.25s), and restore to 1.0 on exit."""
	if active_room != "" and active_room != current_room:
		if current_room != "":
			_on_room_exit(current_room)
		current_room = active_room
		_on_room_enter(current_room)
	var step := dt / FADE_DURATION if dt > 0.0 else 1.0
	for wp in wall_parts:
		var rid: String = wp.get("room_id", "")
		var is_active: bool = rid != "" and active_room_ids.has(rid)
		var target_fade := 1.0 if is_active else 0.0
		var f: float = wp.get("fade", 0.0)
		var nf: float = move_toward(f, target_fade, step)
		if nf != f:
			wp["fade"] = nf
			var nc := lerpf(WALL_FULL_PX, WALL_STUB_PX, nf)
			var na := lerpf(1.0, WALL_FADE_ALPHA, nf)
			wp["cut"] = nc
			wp["alpha"] = na
			var m: ShaderMaterial = wp["mat"]
			m.set_shader_parameter("cut", nc)
			m.set_shader_parameter("alpha", na)
	for did in doors.keys():
		var d: Dictionary = doors[did]
		var rid: String = d.get("room_id", "")
		var is_active: bool = rid != "" and active_room_ids.has(rid)
		var target_fade := 1.0 if is_active else 0.0
		var f: float = d.get("fade", 0.0)
		var nf: float = move_toward(f, target_fade, step)
		if nf != f:
			d["fade"] = nf
			(d["sprite"] as Sprite2D).modulate.a = lerpf(1.0, WALL_FADE_ALPHA, nf)
	for wp in wall_parts:                         # a dark edge where a standing wall meets a cut beside it
		var m: ShaderMaterial = wp["mat"]
		var mine: float = wp["cut"]
		for side in ["left", "right"]:
			var nb = wp[side]
			var e := 0.0
			if nb != null and nb["cut"] < mine - 20.0:
				e = nb["cut"]
			if wp.get("e_" + side, -1.0) != e:
				wp["e_" + side] = e
				m.set_shader_parameter("edge_" + side, e)


func set_pipe(fixed: bool) -> void:
	var info: Dictionary = pipe["fixed" if fixed else "broken"]
	pipe_node.texture = _load_tex(level_dir + "/" + info["sprite"])
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
		draw_set_transform(Vector2.ZERO, 0.0, Vector2(1.0, Hex.SIN_E))      # flat on the floor
		for k in 4:
			var f := fmod(clock / 1.3 + k * 0.25, 1.0)
			var r := 6.0 + 46.0 * f
			var off := Vector2(sin(k * 2.1) * 8.0, cos(k * 1.3) * 10.0)
			draw_arc(off, r, 0.0, TAU, 40, Color(0.85, 0.92, 1.0, 0.42 * (1.0 - f)), 1.6, true)


class SteamLeaks extends Node2D:
	## Pressurised steam jets & billow plumes escaping from the fractured regulator and relief valves in L4E.
	var clock := 0.0
	var vents: Array = []

	func _ready() -> void:
		vents = [
			{"pos": Hex.plan_to_screen(Vector2(7.08, 1.55), 1.02), "dir": Vector2(0.82, -0.57), "speed": 115.0, "warm": true},
			{"pos": Hex.plan_to_screen(Vector2(9.20, 5.10), 1.32), "dir": Vector2(-0.35, -0.93), "speed": 90.0, "warm": false},
			{"pos": Hex.plan_to_screen(Vector2(5.25, 2.00), 1.88), "dir": Vector2(-0.15, -0.98), "speed": 75.0, "warm": true},
		]

	func _process(dt: float) -> void:
		clock += dt
		queue_redraw()

	func _draw() -> void:
		for v in vents:
			var origin: Vector2 = v["pos"]
			var dir: Vector2 = v["dir"]
			var spd: float = v["speed"]
			var warm: bool = v["warm"]
			# Core high-pressure hiss streak near the nozzle
			var tip := origin + dir * (18.0 + 4.0 * sin(clock * 23.0))
			draw_line(origin, tip, Color(0.96, 0.92, 0.86, 0.55), 3.2, true)
			# Expanding turbulent steam puffs
			for k in 18:
				var h := fmod(k * 0.618034, 1.0)
				var life := 0.85
				var f := fmod(clock / life + h, 1.0)
				var lateral := Vector2(-dir.y, dir.x) * sin(clock * 6.0 + k * 2.3) * (14.0 * f)
				var rise := Vector2(0.0, -38.0 * f * f)
				var p := origin + dir * (spd * f) + lateral + rise
				var rad := 3.5 + 18.0 * f
				var alpha := (1.0 - f) * (0.36 if f > 0.12 else f * 3.0)
				var col := Color(0.95, 0.85, 0.74, alpha) if (warm and f < 0.45) else Color(0.88, 0.92, 0.96, alpha)
				draw_circle(p, rad, col)


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
		if p.x >= rr[0] and p.x < rr[1] and p.y >= rr[2] and p.y < rr[3]:   # half-open: rooms that touch share no dead line
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
	var umin := int(floor(float(bnd[0]) / Hex.CELL)) - 1
	var umax := int(ceil(float(bnd[1]) / Hex.CELL)) + 1
	var vmin := int(floor(float(bnd[2]) / Hex.CELL)) - 1
	var vmax := int(ceil(float(bnd[3]) / Hex.CELL)) + 1
	for v in range(vmin, vmax + 1):
		for u in range(umin, umax + 1):
			var h := Vector2i(u, v)
			if _hex_ok(h):
				walkable[h] = true
				room_of[h] = _in_room(Hex.hex_to_plan(h))
				var id := astar.get_available_point_id()
				pid[h] = id
				astar.add_point(id, Hex.hex_to_ground(h))
	for h in walkable:
		for dd in Hex.HALF_DIRS:           # each edge once
			var d: Vector2i = dd
			var n: Vector2i = h + d
			if not walkable.has(n):
				continue
			if d.x != 0 and d.y != 0:      # a diagonal may not cut a corner: both side cells free and joined
				var a: Vector2i = h + Vector2i(d.x, 0)
				var b: Vector2i = h + Vector2i(0, d.y)
				if not (walkable.has(a) and walkable.has(b)) or _edge_door(h, a) != "" or _edge_door(h, b) != "" \
						or _edge_door(a, n) != "" or _edge_door(b, n) != "":
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
	print("level ", data["level"], ": ", walkable.size(), " walkable cells")


## Combat reach: every cell the actor at start can walk to with ap, and its cheapest AP cost
## (straight steps 1, diagonals alternating 1 and 2), following the same graph as find_path.
func reach_from(start: Vector2i, ap: int, occupied: Array = []) -> Dictionary:
	var best := {}                       # [cell, parity] -> cost
	var out := {start: 0}
	if not pid.has(start):
		return out
	var open := [[0, start, 0]]          # cost, cell, diagonals taken so far (parity)
	best[[start, 0]] = 0
	while not open.is_empty():
		var bi := 0
		for i in open.size():
			if open[i][0] < open[bi][0]:
				bi = i
		var cur: Array = open.pop_at(bi)
		var c: int = cur[0]
		var h: Vector2i = cur[1]
		var par: int = cur[2]
		for nid in astar.get_point_connections(pid[h]):
			var n := Hex.ground_to_hex(astar.get_point_position(nid))
			if n in occupied:
				continue
			var d := n - h
			var diag := d.x != 0 and d.y != 0
			var step := (2 if par == 1 else 1) if diag else 1
			var nc := c + step
			if nc > ap:
				continue
			var np := (1 - par) if diag else par
			var key := [n, np]
			if best.has(key) and best[key] <= nc:
				continue
			best[key] = nc
			if not out.has(n) or out[n] > nc:
				out[n] = nc
			open.append([nc, n, np])
	return out


## Free movement out of combat: straighten a cell path into the fewest straight segments that stay
## on walkable cells and cross no wall or closed door. Returns ground points (the last is the goal).
func smooth(from: Vector2i, path: Array) -> Array:
	var cells: Array = [from] + path
	var out: Array = []
	var i := 0
	while i < cells.size() - 1:
		var j := cells.size() - 1
		while j > i + 1 and not _straight_ok(cells[i], cells[j]):
			j -= 1
		out.append(Hex.hex_to_ground(cells[j]))
		i = j
	return out


func _straight_ok(a: Vector2i, b: Vector2i) -> bool:
	var pa := Hex.hex_to_plan(a)
	var pb := Hex.hex_to_plan(b)
	var n := int(ceil(pa.distance_to(pb) / (Hex.CELL * 0.25)))
	var prev := a
	for k in range(1, n + 1):
		var p := pa.lerp(pb, float(k) / n)
		for o in [Vector2(0.22, 0.22), Vector2(-0.22, 0.22), Vector2(0.22, -0.22), Vector2(-0.22, -0.22)]:
			if not walkable.has(Hex.ground_to_hex(Hex.plan_to_ground(p + o * Hex.CELL))):
				return false
		var h := Hex.ground_to_hex(Hex.plan_to_ground(p))
		if h != prev:
			if not pid.has(h) or not pid.has(prev):
				return false
			var e := _edge_door(prev, h)
			if e == "#" or (e != "" and not (doors.has(e) and doors[e]["open"])):
				return false
			prev = h
	return true


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
			var p_id: String = pd.get("id", pd["name"])
			var p_kind := "prop"
			if p_id == "toolbox":
				p_kind = "toolbox"
			elif p_id in ["main_heating_assembly", "heating_control_panel", "temp_monitoring_unit"]:
				p_kind = "heating_assembly"
			elif p_id in ["heating_workstation", "spares_shelf"]:
				p_kind = "heating_instability"
			best = {"kind": p_kind, "id": p_id,
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
			return {"kind": it.get("kind", "look"), "id": it["id"], "name": it["name"], "text": it["text"], "plan": ip}
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


func _creature_step(c: Dictionary, dt: float) -> void:
	if not c["walks"]:
		return
	c["timer"] = float(c["timer"]) - dt
	if c["state"] == "graze":
		if c["timer"] > 0.0:
			return
		var tgt: Vector2 = c["g"]
		for _try in 12:                          # a spot in the pen, away from the other animals
			var p_plan: Vector2
			if c["area"].is_empty():
				p_plan = Hex.ground_to_plan(c["home"]) + Vector2(randf_range(-1.0, 1.0), randf_range(-1.0, 1.0))
			else:
				var a: Array = c["area"]
				p_plan = Vector2(randf_range(a[0], a[1]), randf_range(a[2], a[3]))
			var g := Hex.plan_to_ground(p_plan)
			if g.distance_to(c["g"]) < 0.6:
				continue
			var free := true
			for o in creatures:
				if o != c and (g.distance_to(o["g"]) < 0.7 or g.distance_to(o["target"]) < 0.7):
					free = false
			if free:
				tgt = g
				break
		c["target"] = tgt
		c["state"] = "walk"
		c["t"] = 0.0
		return
	# walking: turn towards the target (no more than 140 degrees a second), then step on
	var to: Vector2 = c["target"] - c["g"]
	var want := rad_to_deg(atan2(to.y, to.x))
	var diff := wrapf(want - float(c["facing"]), -180.0, 180.0)
	c["facing"] = float(c["facing"]) + clampf(diff, -140.0 * dt, 140.0 * dt)
	c["t"] = float(c["t"]) + dt
	if absf(diff) < 35.0:
		var step: float = minf(float(c["speed"]) * dt, to.length())
		c["g"] = c["g"] + to.normalized() * step
		(c["n"] as Node2D).position = Hex.ground_to_screen(c["g"])
	if to.length() < 0.03 or c["t"] > 12.0:
		c["state"] = "graze"
		c["timer"] = randf_range(4.0, 10.0)


func _process(_dt: float) -> void:
	var t := Time.get_ticks_msec() / 1000.0
	for c in creatures:                           # graze a while, amble to another spot in the pen, graze again
		_creature_step(c, _dt)
		if c["state"] == "walk":
			(c["p"] as Puppet3D).sync("walk", c["t"] * 24.0, 24.0, c["facing"], NAN, _dt)
		else:                                     # 12 poses a second: the grazing loop at half its source rate
			(c["p"] as Puppet3D).sync("idle", (t + c["phase"]) * 12.0, 12.0, c["facing"], NAN, _dt)
	for g in grazers:
		var ph: float = g["phase"]
		g["s"].rotation = sin(t * 1.25 + ph) * 0.10 + sin(t * 2.9 + ph) * 0.035

