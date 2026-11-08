class_name Puppet3D
extends Node2D
## A character drawn live from its 3D model instead of pre-rendered sprites.
##
## The model renders in its own little 3D world (a SubViewport) through an orthographic camera at the
## game's view angle (Hex.ELEV_DEG), 165 px per metre, and the result is shown here as a 2D sprite with
## the feet on this node's origin. So the 2D game keeps sorting, cutting walls and picking exactly as
## before. The Actor stays the clock: it tells the puppet which clip, frame and facing to show (sync()),
## so stride, shot timing and the "no sliding" rule are unchanged; the puppet only replaces the picture.
## Facing turns smoothly to any angle, and the aim pitch is applied continuously on the spine and arms.

const W := 384
const H := 416
const FOOT_Y := 368                     # where the feet sit in the viewport (px from the top)
const BIG_W := 720
const BIG_H := 600
const BIG_FOOT_Y := 340
const LYING := ["death", "fall"]
const TOON := preload("res://shaders/toon_v2.gdshader")
const INK := preload("res://shaders/ink_outline.gdshader")

var vp: SubViewport
var cam: Camera3D
var _big := false
var _res := 1.0                          # viewport pixels per game pixel (= on-screen zoom)
var view: Sprite2D
var model: Node3D                       # turns (yaw)
var shift: Node3D                       # holds locomotion in place
var _measured := false
var anim: AnimationPlayer
var skel: Skeleton3D
var gun: Node3D
var cfg: Dictionary
var _yaw := 0.0
var _yaw_target := 0.0
var _hips := -1
var _inplace := {}                      # clip -> [start offset, travel per loop] in model space (x, z)
var _shares: Array = []                 # [[bone index, share]]
var _toon_mats: Array = []
var _last_key := ""
var _dirty := 2                          # frames still to re-render after a resize


func setup(glb_path: String, json_path: String) -> void:
	cfg = JSON.parse_string(FileAccess.get_file_as_string(json_path))
	vp = SubViewport.new()
	vp.size = Vector2i(W, H)
	vp.transparent_bg = true
	vp.own_world_3d = true
	vp.msaa_3d = Viewport.MSAA_2X                       # soft edges like the sprite renders; 4x costs too much on weak GPUs
	vp.render_target_update_mode = SubViewport.UPDATE_ONCE  # re-rendered only when the pose changes (see sync)
	add_child(vp)
	cam = Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.keep_aspect = Camera3D.KEEP_HEIGHT
	cam.near = 0.05
	cam.far = 80.0
	vp.add_child(cam)
	var scene: PackedScene = load(glb_path)
	model = Node3D.new()
	vp.add_child(model)
	shift = Node3D.new()
	model.add_child(shift)
	var inst: Node3D = scene.instantiate()
	shift.add_child(inst)
	anim = _find(inst, "AnimationPlayer") as AnimationPlayer
	skel = _find(inst, "Skeleton3D") as Skeleton3D
	gun = _find_named(inst, "Pistol")
	_dress(inst)
	_hips = _bone("mixamorig:Hips")
	for s in cfg.get("pitch_shares", []):
		var b := _bone(str(s[0]))
		if b >= 0:
			_shares.append([b, float(s[1])])
	view = Sprite2D.new()
	view.centered = false
	var pm := CanvasItemMaterial.new()
	pm.blend_mode = CanvasItemMaterial.BLEND_MODE_PREMULT_ALPHA   # rendered over transparent black
	view.material = pm
	view.texture = vp.get_texture()
	add_child(view)
	_frame(false)


func _frame(big: bool) -> void:
	"""Standing clips fit a small view; lying down (death, fall) needs room all round the feet."""
	var res := _screen_scale()
	if _big == big and view.offset != Vector2.ZERO and absf(res - _res) < 0.03:
		return
	_big = big
	_res = res
	var w := BIG_W if big else W
	var h := BIG_H if big else H
	var fy := BIG_FOOT_Y if big else FOOT_Y
	# render at the size it is shown on screen: sharp, no dark fringes from shrinking, fewer pixels
	vp.size = Vector2i(maxi(16, int(ceil(w * res))), maxi(16, int(ceil(h * res))))
	var k := Vector2(float(vp.size.x) / w, float(vp.size.y) / h)
	view.scale = Vector2.ONE / k
	_dirty = 2
	cam.size = float(h) / Hex.PPM
	var e := deg_to_rad(Hex.ELEV_DEG)
	var a := (fy - h * 0.5) / (Hex.PPM * cos(e))           # puts the ground origin on row fy
	cam.rotation = Vector3(-e, 0.0, 0.0)
	cam.position = Vector3(0.0, a, 0.0) + Vector3(0.0, sin(e), cos(e)) * 30.0
	view.offset = -Vector2(w * 0.5, fy) * k
	view.texture = null
	view.texture = vp.get_texture()                     # a resized viewport needs re-binding


# ------------------------------------------------------------------ the look
func _dress(n: Node) -> void:
	"""Every mesh gets the toon material (its own texture kept) and the ink outline pass."""
	if n is MeshInstance3D:
		var mi := n as MeshInstance3D
		for s in mi.mesh.get_surface_count():
			var src := mi.get_active_material(s)
			var m := ShaderMaterial.new()
			m.shader = TOON
			if src is BaseMaterial3D:
				var bm := src as BaseMaterial3D
				m.set_shader_parameter("albedo_color", bm.albedo_color)
				if bm.albedo_texture:
					m.set_shader_parameter("albedo_tex", bm.albedo_texture)
				m.set_shader_parameter("has_tex", bm.albedo_texture != null)
			var ink := ShaderMaterial.new()
			ink.shader = INK
			m.next_pass = ink
			mi.set_surface_override_material(s, m)
			_toon_mats.append(m)
	for c in n.get_children():
		_dress(c)


func set_flash(c: Color) -> void:
	for m in _toon_mats:
		(m as ShaderMaterial).set_shader_parameter("flash", c)
	_last_key = ""


# ------------------------------------------------------------------ driven by the Actor
## clip: the Actor's clip name; t_frames: its frame + progress; fps: the clip's playback rate;
## facing_deg: ground facing (0 = screen right, counter-clockwise); pitch: held aim in degrees (NAN = none).
func sync(clip: String, t_frames: float, fps: float, facing_deg: float, pitch: float, delta: float) -> void:
	if not _measured and is_inside_tree() and anim and anim.is_node_ready():
		_measured = true
		for c in ["walk", "run"]:
			_measure_inplace(c)
	_yaw_target = _yaw_for(facing_deg)
	_yaw = lerp_angle(_yaw, _yaw_target, clampf(delta * 14.0, 0.0, 1.0))
	if absf(angle_difference(_yaw, _yaw_target)) < 0.003:
		_yaw = _yaw_target
	# the pose only changes on a new frame, a turn or a new pitch: render the view only then
	var key := "%s|%d|%.3f|%.1f|%.2f" % [clip, int(t_frames), _yaw, -999.0 if is_nan(pitch) else pitch, _screen_scale()]
	if key == _last_key:
		if _dirty > 0:
			_dirty -= 1
			vp.render_target_update_mode = SubViewport.UPDATE_ONCE
		return
	_last_key = key
	_frame(clip in LYING)
	vp.render_target_update_mode = SubViewport.UPDATE_ONCE
	model.rotation.y = _yaw
	var src_fps := float(cfg.get("fps_src", 24))
	var name := ""
	var t := 0.0
	var w := 0.0                                           # how much of the held pitch applies
	var aim: Dictionary = cfg.get("aim", {})
	if clip.begins_with("pistol_raise") or clip.begins_with("pistol_shot") or clip.begins_with("pistol_lower") or clip == "pistol_hold":
		name = str(aim.get("anim", "aim_seq"))
		var k: int
		if clip == "pistol_hold":
			k = int(aim["hold"])
		else:
			var part := "raise" if clip.begins_with("pistol_raise") else ("shot" if clip.begins_with("pistol_shot") else "lower")
			k = int(aim[part][0]) + int(t_frames)
		k = clampi(k, 0, aim["weights"].size() - 1)
		t = k / src_fps
		w = float(aim["weights"][k])
	else:
		name = str(cfg["clips"].get(clip, clip))
		var step := src_fps / maxf(fps, 1.0)                   # sprite clips may skip source frames (idle: 12 fps)
		t = t_frames * step / src_fps
		if clip == "idle":
			var lp: Array = cfg.get("idle_loop_src", [0, 0])
			if float(lp[1]) > float(lp[0]):
				t = (float(lp[0]) + fmod(t_frames * step, float(lp[1]) - float(lp[0]))) / src_fps
	if anim and anim.has_animation(name):
		if anim.current_animation != name:
			anim.play(name)
		anim.seek(minf(t, anim.current_animation_length), true)
		anim.pause()
	if anim == null or not anim.is_node_ready():
		_last_key = ""                                     # not posed yet: try again next frame
	_apply_inplace(clip, t)
	if gun:
		gun.visible = clip.begins_with("pistol")
	if not is_nan(pitch) and w > 0.0:
		_apply_pitch(pitch * w)


func _yaw_for(facing_deg: float) -> float:
	var g := Vector2(cos(deg_to_rad(facing_deg)), sin(deg_to_rad(facing_deg)))
	return atan2(g.x, -g.y)                                    # the model faces +Z; ground y is -Z


# ------------------------------------------------------------------ in place and aim
func _measure_inplace(clip: String) -> void:
	"""Locomotion clips carry their forward travel in the hips; the Actor moves the character, so the
	model keeps the hips' sway but not their travel (the same as render_character.py does)."""
	var name := str(cfg["clips"].get(clip, clip))
	if not anim.has_animation(name) or _hips < 0:
		return
	var L := anim.get_animation(name).length
	shift.position = Vector3.ZERO
	anim.play(name); anim.seek(0.0, true)
	var p0 := _hips_model()
	anim.seek(L, true)
	var p1 := _hips_model()
	anim.stop()
	_inplace[clip] = [Vector2(p0.x, p0.z), Vector2(p1.x - p0.x, p1.z - p0.z), L]


func _skel_to_model() -> Transform3D:
	"""Skeleton space -> model (yaw node) space, without the yaw itself."""
	var t := Transform3D.IDENTITY
	var n: Node = skel
	while n and n != model:
		if n is Node3D:
			t = (n as Node3D).transform * t
		n = n.get_parent()
	return t


func _hips_model() -> Vector3:
	return (_skel_to_model() * skel.get_bone_global_pose(_hips)).origin


func _apply_inplace(clip: String, t: float) -> void:
	if _inplace.has(clip):
		var d: Array = _inplace[clip]
		var off: Vector2 = d[0] + d[1] * clampf(t / maxf(float(d[2]), 1e-3), 0.0, 1.0)
		shift.position = Vector3(-off.x, 0.0, -off.y)
	else:
		shift.position = Vector3.ZERO


func _apply_pitch(deg: float) -> void:
	"""Tilt spine, neck and arms by their shares, about the character's own sideways axis
	(render_aim.py's method), so the pistol points along the held pitch."""
	if _shares.is_empty():
		return
	var axis_model := Vector3(-1.0, 0.0, 0.0)                  # the model faces +Z: positive = aim up
	var axis := (_skel_to_model().basis.inverse() * axis_model).normalized()
	for s in _shares:
		var b: int = s[0]
		var share: float = s[1]
		var R := Basis(axis, deg_to_rad(deg) * share)
		var g := skel.get_bone_global_pose(b)
		var ng := Transform3D(R * g.basis, g.origin)
		var parent := skel.get_bone_parent(b)
		var pg := skel.get_bone_global_pose(parent) if parent >= 0 else Transform3D.IDENTITY
		var local := pg.affine_inverse() * ng
		skel.set_bone_pose_rotation(b, local.basis.get_rotation_quaternion())


func _screen_scale() -> float:
	if not is_inside_tree():
		return 1.0
	var sc := get_global_transform_with_canvas().get_scale().x * get_viewport().get_final_transform().get_scale().x
	return clampf(sc, 0.25, 2.0)


# ------------------------------------------------------------------ helpers
func _bone(name: String) -> int:
	if skel == null:
		return -1
	for n in [name, name.replace(":", "_"), name.replace("_", ":")]:
		var i := skel.find_bone(n)
		if i >= 0:
			return i
	return -1


static func _find(n: Node, cls: String) -> Node:
	if n.get_class() == cls:
		return n
	for c in n.get_children():
		var r := _find(c, cls)
		if r:
			return r
	return null


static func _find_named(n: Node, nm: String) -> Node3D:
	if n.name.begins_with(nm) and n is Node3D:
		return n
	for c in n.get_children():
		var r := _find_named(c, nm)
		if r:
			return r
	return null
