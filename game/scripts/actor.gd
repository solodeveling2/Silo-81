class_name Actor
extends Node2D
## A pre-rendered character with 6 hex facings, Fallout-style.
## Locomotion clips animate in place; every new animation frame moves the actor along its
## path by the stride measured in Blender, so the feet stay planted and never slide.

signal arrived
signal stepped(hex: Vector2i)
signal action_point
signal anim_done(anim: String)

const STEP_CLIPS := ["walk", "run", "crawl"]
static var _frames_cache := {}

var kind := "player"            # "player" or "worm"
var team := "player"
var display_name := ""
var data: Dictionary
var anim := "idle"
var dir := 4
var sprite: AnimatedSprite2D
var ground := Vector2.ZERO      # metres
var hex := Vector2i.ZERO
var path: Array = []            # ground points still to reach
var move_clip := "walk"
var alive := true
var hp := 10
var hp_max := 10
var ap := 0
var ring_color := Color(0, 0, 0, 0)
var highlight := false
var _switching := false
var _per_frame := {}


func setup(json_path: String, actor_kind: String) -> void:
	kind = actor_kind
	data = JSON.parse_string(FileAccess.get_file_as_string(json_path))
	sprite = AnimatedSprite2D.new()
	sprite.centered = false
	add_child(sprite)
	if not _frames_cache.has(json_path):
		_frames_cache[json_path] = _build_frames(json_path)
	sprite.sprite_frames = _frames_cache[json_path]
	for clip in STEP_CLIPS:
		if data["animations"].has(clip):
			var s: Array = data["animations"][clip]["directions"]["0"]["step_px"]
			_per_frame[clip] = absf(float(s[0])) / Hex.PPM
	sprite.frame_changed.connect(_on_frame_changed)
	sprite.animation_finished.connect(func() -> void: anim_done.emit(anim))
	play("idle", dir)


func _build_frames(json_path: String) -> SpriteFrames:
	var base := json_path.get_base_dir()
	var frames := SpriteFrames.new()
	frames.remove_animation("default")
	for a: String in data["animations"]:
		var info: Dictionary = data["animations"][a]
		for d in 6:
			var dinfo: Dictionary = info["directions"][str(d)]
			var anim_name := "%s_%d" % [a, d]
			frames.add_animation(anim_name)
			frames.set_animation_loop(anim_name, info["loop"])
			frames.set_animation_speed(anim_name, info["fps"])
			var sheet: Texture2D = load(base + "/" + dinfo["sheet"])
			var fw: int = dinfo["frame_size"][0]
			var fh: int = dinfo["frame_size"][1]
			var cols: int = dinfo["columns"]
			for i in int(info["frames"]):
				var tex := AtlasTexture.new()
				tex.atlas = sheet
				tex.region = Rect2((i % cols) * fw, (i / cols) * fh, fw, fh)
				frames.add_frame(anim_name, tex)
	return frames


func has_clip(a: String) -> bool:
	return data["animations"].has(a)


func play(a: String, d: int, keep_phase := false) -> void:
	if not has_clip(a):
		return
	var f := sprite.frame
	var p := sprite.frame_progress
	anim = a
	dir = d
	var dinfo: Dictionary = data["animations"][a]["directions"][str(d)]
	sprite.offset = -Vector2(dinfo["feet_anchor"][0], dinfo["feet_anchor"][1])
	_switching = true
	sprite.play("%s_%d" % [a, d])
	if keep_phase:
		sprite.set_frame_and_progress(f % sprite.sprite_frames.get_frame_count(sprite.animation), p)
	_switching = false


func place_at_hex(h: Vector2i) -> void:
	hex = h
	ground = Hex.hex_to_ground(h)
	position = Hex.ground_to_screen(ground)


func face_ground(target: Vector2) -> void:
	if target.distance_to(ground) > 0.01:
		dir = Hex.dir_towards(ground, target)


## Walk (or run, or crawl) through a list of hexes. Emits stepped at each hex centre and arrived at the end.
func follow(hexes: Array, clip: String = "") -> void:
	path.clear()
	for h in hexes:
		path.append(Hex.hex_to_ground(h))
	if path.is_empty():
		arrived.emit.call_deferred()
		return
	move_clip = clip if clip != "" else ("crawl" if kind == "worm" else "walk")
	play(move_clip, Hex.dir_towards(ground, path[0]))


## Call from a stepped handler to stop right on the hex just reached.
func stop_now() -> void:
	path.clear()


func stop_at_next_hex() -> void:
	if path.size() > 1:
		path = [path[0]]


func is_moving() -> bool:
	return anim in STEP_CLIPS and not path.is_empty()


func idle_clip(in_combat: bool) -> String:
	if kind == "player" and in_combat:
		return "pistol_idle"
	return "idle"


func _on_frame_changed() -> void:
	if _switching:
		return
	if anim in STEP_CLIPS and not path.is_empty():
		_advance(_per_frame.get(anim, 0.045))
	var info: Dictionary = data["animations"][anim]
	if info.has("action_frame") and sprite.frame == int(info["action_frame"]) and anim not in ["hit", "death"]:
		action_point.emit()


func _advance(dist: float) -> void:
	var remaining := dist
	while remaining > 0.0 and not path.is_empty():
		var target: Vector2 = path[0]
		var to := target - ground
		var l := to.length()
		if l <= remaining:
			ground = target
			remaining -= l
			path.pop_front()
			hex = Hex.ground_to_hex(ground)
			stepped.emit(hex)
			if not path.is_empty():
				var nd := Hex.dir_towards(ground, path[0])
				if nd != dir:
					play(anim, nd, true)
		else:
			ground += to / l * remaining
			remaining = 0.0
	position = Hex.ground_to_screen(ground)
	if path.is_empty():
		play(idle_clip(get_meta("combat", false)), dir)
		arrived.emit()


func flash(c: Color) -> void:
	var tw := create_tween()
	sprite.modulate = c
	tw.tween_property(sprite, "modulate", Color.WHITE, 0.35)


func sprite_rect() -> Rect2:
	var tex := sprite.sprite_frames.get_frame_texture(sprite.animation, sprite.frame)
	if tex == null:
		return Rect2(position, Vector2.ZERO)
	return Rect2(position + sprite.offset, tex.get_size())


func _process(_delta: float) -> void:
	queue_redraw()


func _draw() -> void:
	if ring_color.a > 0.0 and alive:
		var pts := PackedVector2Array()
		var rx := 0.34 * Hex.PPM
		var ry := rx * 0.5
		for k in 33:
			var a := TAU * k / 32.0
			pts.append(Vector2(cos(a) * rx, sin(a) * ry))
		var c := ring_color
		if highlight:
			c = c.lightened(0.35)
		draw_polyline(pts, c, 3.0 if highlight else 2.0, true)
