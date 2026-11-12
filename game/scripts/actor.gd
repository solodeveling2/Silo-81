class_name Actor
extends Node2D
## A character on the square grid: drawn live in 3D (puppet3d) with any facing; the 6-direction sprite
## sheets are the clock and the fallback.
## Locomotion clips animate in place; every new animation frame moves the actor along its
## path by the stride measured in Blender, so the feet stay planted and never slide.

signal arrived
signal stepped(hex: Vector2i)
signal action_point
signal anim_done(anim: String)

const STEP_CLIPS := ["walk", "run", "crawl"]
const CLIP_SPEED := {"walk": 1.25, "run": 0.85}
static var _frames_cache := {}

var kind := "player"            # "player" or "worm"
var team := "player"
var display_name := ""
var data: Dictionary
var anim := "idle"
var dir := 4
var sprite: AnimatedSprite2D
var puppet: Puppet3D                              # live 3D body when the character has one (sprite = clock)
## live 3D models, by the character's sprite json (the sprites stay as the clock and the fallback)
const LIVE_3D := {
	"res://characters/player_male/character.json": ["res://characters/player_3d/player.glb", "res://characters/player_3d/player.json"],
	"res://characters/tibor/character.json": ["res://characters/tibor_3d/tibor.glb", "res://characters/tibor_3d/tibor.json"],
	"res://characters/overseer/character.json": ["res://characters/overseer_3d/overseer.glb", "res://characters/overseer_3d/overseer.json"],
	"res://characters/pipe_worm/character.json": ["res://characters/pipe_worm_3d/worm_meshy.glb", "res://characters/pipe_worm_3d/worm_meshy.json"],
	"res://characters/changed/character.json": ["res://characters/changed_3d/changed.glb", "res://characters/changed_3d/changed.json"],
	"res://characters/feral/character.json": ["res://characters/feral_3d/feral.glb", "res://characters/feral_3d/feral.json"],
	"res://characters/infected/character.json": ["res://characters/infected_3d/infected.glb", "res://characters/infected_3d/infected.json"],
	"res://characters/townsfolk/character.json": ["res://characters/changed_3d/changed.glb", "res://characters/townsfolk_3d/townsfolk.json"],
}
static var _blank := {}                           # frame size -> transparent texture (clock for live-only characters)
var speed := 1.0                                  # walk-speed multiplier (the Changed shamble)
var ground := Vector2.ZERO      # metres
var hex := Vector2i.ZERO
var face_deg := 0.0                  # exact ground facing for the live 3D model
var free_move := false               # straight-line move (out of combat): emit stepped on every cell crossed
var path: Array = []            # ground points still to reach
var move_clip := "walk"
var alive := true
var hp := 10
var hp_max := 10
var ap := 0
var ring_color := Color(0, 0, 0, 0)
var highlight := false
var _switching := false
## Held aim: the pitch (degrees) the gun is pointing at between shots, or NAN when not aiming.
## The gun stays on the target until it dies, you move, or combat ends.
var aim_pitch := NAN
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
	if LIVE_3D.has(json_path) and not "--sprites" in OS.get_cmdline_user_args():
		puppet = Puppet3D.new()
		puppet.setup(LIVE_3D[json_path][0], LIVE_3D[json_path][1])
		add_child(puppet)
		sprite.self_modulate.a = 0.0             # still the clock and the picking rect, just not drawn
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
			var fw: int = dinfo["frame_size"][0]
			var fh: int = dinfo["frame_size"][1]
			if not dinfo.has("sheet"):                # live 3D only: blank frames, the puppet is the picture
				var key := "%dx%d" % [fw, fh]
				if not _blank.has(key):
					var img := Image.create(fw, fh, false, Image.FORMAT_RGBA8)
					_blank[key] = ImageTexture.create_from_image(img)
				for i in int(info["frames"]):
					frames.add_frame(anim_name, _blank[key])
				continue
			var sheet: Texture2D = load(base + "/" + dinfo["sheet"])
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
	if a == "pistol_hold" and is_aiming():
		if posmod(int(roundf(face_deg / 60.0)), 6) != d:
			face_deg = d * 60.0
		anim = a; dir = d
		var hinfo: Dictionary = data["animations"][a]["directions"][str(d)]
		sprite.offset = -Vector2(hinfo["feet_anchor"][0], hinfo["feet_anchor"][1])
		_switching = true
		sprite.play("%s_%d" % [a, d])
		_switching = false
		_show_hold(aim_pitch)
		return
	var f := sprite.frame
	var p := sprite.frame_progress
	anim = a
	if posmod(int(roundf(face_deg / 60.0)), 6) != d:
		face_deg = d * 60.0                 # a caller chose a sprite direction: face it exactly
	dir = d
	var dinfo: Dictionary = data["animations"][a]["directions"][str(d)]
	sprite.offset = -Vector2(dinfo["feet_anchor"][0], dinfo["feet_anchor"][1])
	_switching = true
	sprite.play("%s_%d" % [a, d])
	if kind != "worm":
		sprite.speed_scale = CLIP_SPEED.get(a, 1.0) * (speed if a in STEP_CLIPS else 1.0)
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
		face_deg = Hex.angle_towards(ground, target)


func _turn_to(target: Vector2) -> int:
	face_deg = Hex.angle_towards(ground, target)
	return Hex.dir_towards(ground, target)


## Walk (or run, or crawl) through a list of hexes. Emits stepped at each hex centre and arrived at the end.
func follow(hexes: Array, clip: String = "") -> void:
	path.clear()
	for h in hexes:
		path.append(Hex.hex_to_ground(h))
	if path.is_empty():
		arrived.emit.call_deferred()
		return
	free_move = false
	move_clip = clip if clip != "" else ("crawl" if kind == "worm" else "walk")
	aim_pitch = NAN                                   # you lower the gun to walk
	play(move_clip, _turn_to(path[0]))


## Free movement (out of combat): walk straight through ground points; stepped fires on each new cell.
func follow_points(points: Array, clip: String = "") -> void:
	path = points.duplicate()
	if path.is_empty():
		arrived.emit.call_deferred()
		return
	free_move = true
	move_clip = clip if clip != "" else "walk"
	aim_pitch = NAN
	play(move_clip, _turn_to(path[0]))


## Call from a stepped handler to stop right on the hex just reached.
func stop_now() -> void:
	path.clear()


func stop_at_next_hex() -> void:
	if path.size() > 1:
		path = [path[0]]


func is_moving() -> bool:
	return anim in STEP_CLIPS and not path.is_empty()


## A point on this character to shoot at: "body" or "head". x, y are ground metres, z is height.
## Measured from the 3D model and stored in character.json ("aim_points": forward, height).
func aim_point(part := "body") -> Vector3:
	var pts: Dictionary = data.get("aim_points", {})
	var fz: Array = pts.get(part, pts.get("body", [0.0, 0.5]))
	var f := Vector2(cos(deg_to_rad(face_deg)), sin(deg_to_rad(face_deg)))
	var g := ground + f * float(fz[0])
	return Vector3(g.x, g.y, float(fz[1]))


static func aim_to_screen(p: Vector3) -> Vector2:
	return Hex.ground_to_screen(Vector2(p.x, p.y), p.z)


## The firing clip whose gun angle best lines up with the target, for the current facing.
## Each clip was rendered at one aim pitch; its muzzle position on the firing frame is in the json.
func fire_clip(target: Vector3) -> String:
	var aim: Dictionary = data.get("aim", {})
	var best := "pistol_attack"
	var best_err := INF
	var dist := Vector2(target.x, target.y).distance_to(ground)
	for p in aim.get("pitches", []):
		var key: String = aim.get("shot", aim.get("clip", "pistol_fire")) + "_" + _pitch_tag(int(p))
		if not has_clip(key):
			continue
		var m: Array = data["animations"][key]["directions"][str(dir)]["muzzle_m"]
		var want := rad_to_deg(atan2(target.z - float(m[1]), maxf(dist - float(m[0]), 0.05)))
		var err := absf(want - float(p))
		if err < best_err:
			best_err = err
			best = key
	return best


## Where the muzzle is on the firing frame of a clip, in screen pixels from this actor's feet.
func muzzle_offset(clip: String) -> Vector2:
	var dinfo: Dictionary = data["animations"].get(clip, {}).get("directions", {}).get(str(dir), {})
	if dinfo.has("muzzle_offset_px"):
		return Vector2(dinfo["muzzle_offset_px"][0], dinfo["muzzle_offset_px"][1])
	var f := Vector2(cos(deg_to_rad(face_deg)), sin(deg_to_rad(face_deg)))
	return Hex.ground_to_screen(ground + f * 0.55, 1.32) - position


static func _pitch_tag(p: int) -> String:
	if p == 0:
		return "0"
	return ("m%d" % -p) if p < 0 else ("p%d" % p)


func idle_clip(in_combat: bool) -> String:
	if kind == "player" and in_combat:
		return "pistol_hold" if is_aiming() and has_clip("pistol_hold") else "pistol_idle"
	return "idle"


# ------------------------------------------------------------------ held aim
func is_aiming() -> bool:
	return not is_nan(aim_pitch)


## The rendered shot pitch that best points the gun at this target from here, facing d.
func pitch_for(target: Vector3, d: int) -> int:
	var keep := dir
	dir = d
	var key := fire_clip(target)
	dir = keep
	return int(data["animations"][key]["pitch_deg"]) if data["animations"].has(key) else 0


func _show_hold(p: float) -> void:
	# the held-aim clip has one frame per pitch (every 5 degrees); show the nearest, paused
	var hp: Array = data.get("aim", {}).get("hold_pitches", [])
	if hp.is_empty() or not has_clip("pistol_hold"):
		return
	var best := 0
	for i in hp.size():
		if absf(float(hp[i]) - p) < absf(float(hp[best]) - p):
			best = i
	if anim != "pistol_hold":
		play("pistol_hold", dir)
	elif sprite.animation != "pistol_hold_%d" % dir:
		play("pistol_hold", dir)
	sprite.pause()
	sprite.frame = best


## Bring the gun onto a target and keep it there. From the lowered stance this is the raise; if
## already aiming, the arms swing from the held pitch to the new one (turning first if needed).
func aim_at(target: Vector3) -> void:
	face_deg = Hex.angle_towards(ground, Vector2(target.x, target.y))
	var nd := Hex.dir_towards(ground, Vector2(target.x, target.y))
	var p := pitch_for(target, nd)
	var tag := _pitch_tag(p)
	if not is_aiming():
		dir = nd
		if has_clip("pistol_raise_" + tag):
			play("pistol_raise_" + tag, dir)
			await anim_done
		aim_pitch = p
		_show_hold(p)
		return
	if nd != dir:
		dir = nd
		_show_hold(aim_pitch)
	var from := aim_pitch
	var steps := int(ceil(absf(p - from) / 5.0))
	for i in range(1, steps + 1):
		await get_tree().create_timer(1.0 / 40.0).timeout
		_show_hold(lerpf(from, p, float(i) / steps))
	aim_pitch = p
	_show_hold(p)


## Fire from the held aim (call aim_at first). Emits action_point on the shot; ends back on the hold.
func fire_held() -> String:
	var key: String = str(data.get("aim", {}).get("shot", "pistol_shot")) + "_" + _pitch_tag(int(aim_pitch))
	if not has_clip(key):
		key = fire_clip(Vector3(ground.x, ground.y, 1.0))
	play(key, dir)
	if int(data["animations"][key].get("action_frame", -1)) == 0:
		action_point.emit.call_deferred()             # fires on its first frame, which never "changes" to itself
	return key


## Lower the gun back to the combat stance (target dead, combat over).
func lower_aim() -> void:
	if not is_aiming():
		return
	var key: String = str(data.get("aim", {}).get("lower", "pistol_lower")) + "_" + _pitch_tag(int(aim_pitch))
	aim_pitch = NAN
	if has_clip(key) and alive:
		play(key, dir)
		await anim_done
	if alive and anim == key:
		play("pistol_idle" if has_clip("pistol_idle") else "idle", dir)


func _on_frame_changed() -> void:
	if _switching:
		return
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
			if not free_move:
				hex = Hex.ground_to_hex(ground)
				stepped.emit(hex)
			if not path.is_empty():
				var nd := _turn_to(path[0])
				if nd != dir:
					play(anim, nd, true)
		else:
			ground += to / l * remaining
			remaining = 0.0
		if free_move:
			var hc := Hex.ground_to_hex(ground)
			if hc != hex:
				hex = hc
				stepped.emit(hex)
	position = Hex.ground_to_screen(ground)
	if path.is_empty():
		play(idle_clip(get_meta("combat", false)), dir)
		arrived.emit()


func flash(c: Color) -> void:
	var tw := create_tween()
	sprite.modulate = c
	tw.tween_property(sprite, "modulate", Color.WHITE, 0.35)
	if puppet:
		var tp := create_tween()
		tp.tween_method(puppet.set_flash, c, Color.WHITE, 0.35)


func sprite_rect() -> Rect2:
	var tex := sprite.sprite_frames.get_frame_texture(sprite.animation, sprite.frame)
	if tex == null:
		return Rect2(position, Vector2.ZERO)
	return Rect2(position + sprite.offset, tex.get_size())


func _process(delta: float) -> void:
	if is_moving():
		var clip_fps := float(data["animations"].get(anim, {}).get("fps", 24)) * sprite.speed_scale
		_advance(_per_frame.get(anim, 0.045) * clip_fps * delta)
	if puppet:
		var fps := float(data["animations"].get(anim, {}).get("fps", 24))
		puppet.sync(anim, sprite.frame + sprite.frame_progress, fps, face_deg, aim_pitch, delta)
	queue_redraw()


func _draw() -> void:
	if ring_color.a > 0.0 and alive:
		var pts := PackedVector2Array()
		var rx := 0.34 * Hex.PPM
		var ry := rx * Hex.SIN_E                 # a ground circle seen from the camera
		for k in 33:
			var a := TAU * k / 32.0
			pts.append(Vector2(cos(a) * rx, sin(a) * ry))
		var c := ring_color
		if highlight:
			c = c.lightened(0.35)
		draw_polyline(pts, c, 3.0 if highlight else 2.0, true)
