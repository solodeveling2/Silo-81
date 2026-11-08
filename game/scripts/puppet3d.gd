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

var W := 384
var H := 416
var FOOT_Y := 368                       # where the feet sit in the viewport (px from the top)
var BIG_W := 720
var BIG_H := 600
var BIG_FOOT_Y := 340
var LYING := ["death", "fall"]
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
var _yaw_offset := 0.0                  # model forward: +Z (Mixamo) = 0; +X (the worm) = -90 degrees
var flip: Dictionary = {}                # mesh flipbook (the worm): frame data, meshes, cached frames
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
	model = Node3D.new()
	vp.add_child(model)
	shift = Node3D.new()
	model.add_child(shift)
	if glb_path.ends_with(".bin"):
		_setup_flipbook(glb_path)
	else:
		_setup_rig(glb_path)
	view = Sprite2D.new()
	view.centered = false
	var pm := CanvasItemMaterial.new()
	pm.blend_mode = CanvasItemMaterial.BLEND_MODE_PREMULT_ALPHA   # rendered over transparent black
	view.material = pm
	view.texture = vp.get_texture()
	add_child(view)
	_frame(false)


func _setup_rig(glb_path: String) -> void:
	var scene: PackedScene = load(glb_path)
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


# ------------------------------------------------------------------ mesh flipbook (no rig: the worm)
func _setup_flipbook(bin_path: String) -> void:
	"""Every frame is a full set of vertex positions on one topology (tools/blender/worm_live.py).
	Frames are turned into meshes the first time they are shown, then kept."""
	flip = {"data": FileAccess.get_file_as_bytes(bin_path), "parts": [], "cache": {}}
	_yaw_offset = -PI * 0.5 if str(cfg.get("forward", "+z")) == "+x" else 0.0
	var off := 0
	for k in ["body", "teeth"]:
		var m: Dictionary = cfg["meshes"][k]
		var nv := int(m["verts"])
		var surfs := []
		for sd in m["surfaces"]:
			# each surface keeps only the vertices it uses
			var remap := {}
			var used := PackedInt32Array()
			var idx := PackedInt32Array()
			var src: Array = sd["indices"]
			for t in range(0, src.size(), 3):
				for c in [0, 2, 1]:                      # Blender winds front faces anticlockwise, Godot clockwise
					var vi := int(src[t + c])
					if not remap.has(vi):
						remap[vi] = used.size()
						used.append(vi)
					idx.append(remap[vi])
			var mat := ShaderMaterial.new()
			mat.shader = TOON
			var md: Dictionary = sd["material"]
			mat.set_shader_parameter("has_tex", false)
			mat.set_shader_parameter("albedo_color", Color.WHITE)
			mat.set_shader_parameter("saturation", 1.0)
			mat.set_shader_parameter("flat_shade", true)          # worm.py renders flat facets
			mat.set_shader_parameter("shade_col", Vector3(md["shade"][0], md["shade"][1], md["shade"][2]))
			mat.set_shader_parameter("mid_col", Vector3(md["mid"][0], md["mid"][1], md["mid"][2]))
			mat.set_shader_parameter("lit_col", Vector3(md["lit"][0], md["lit"][1], md["lit"][2]))
			mat.set_shader_parameter("t_mid", float(md["t_mid"]))
			mat.set_shader_parameter("t_lit", float(md["t_lit"]))
			var ink := ShaderMaterial.new()
			ink.shader = INK
			ink.set_shader_parameter("thickness_m", float(cfg.get("outline_m", {}).get(k, 0.011)) * 0.73)
			mat.next_pass = ink
			_toon_mats.append(mat)
			surfs.append({"used": used, "idx": idx, "mat": mat})
		var mi := MeshInstance3D.new()
		shift.add_child(mi)
		flip["parts"].append({"off": off, "n": nv, "surfs": surfs, "mi": mi})
		off += nv * 15
	_fit_view_to_extents()


func _flip_mesh(part: Dictionary, frame: int) -> ArrayMesh:
	var key := "%d_%d" % [part["off"], frame]
	if flip["cache"].has(key):
		return flip["cache"][key]
	var data: PackedByteArray = flip["data"]
	var base := int(cfg["frame_bytes"]) * frame + int(part["off"])
	var n: int = part["n"]
	var f := data.slice(base, base + n * 12).to_float32_array()
	var nb := base + n * 12
	var am := ArrayMesh.new()
	for sf in part["surfs"]:
		var used: PackedInt32Array = sf["used"]
		var pos := PackedVector3Array(); pos.resize(used.size())
		var nor := PackedVector3Array(); nor.resize(used.size())
		for j in used.size():
			var v := used[j]
			pos[j] = Vector3(f[v * 3], f[v * 3 + 1], f[v * 3 + 2])
			nor[j] = Vector3(data.decode_s8(nb + v * 3), data.decode_s8(nb + v * 3 + 1), data.decode_s8(nb + v * 3 + 2)).normalized()
		var arr := []
		arr.resize(Mesh.ARRAY_MAX)
		arr[Mesh.ARRAY_VERTEX] = pos
		arr[Mesh.ARRAY_NORMAL] = nor
		arr[Mesh.ARRAY_INDEX] = sf["idx"]
		am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
		am.surface_set_material(am.get_surface_count() - 1, sf["mat"])
	flip["cache"][key] = am
	return am


func _fit_view_to_extents() -> void:
	"""Size the view to everything the model ever covers (all frames, any facing), plus the outline."""
	var r := 0.0
	var top := 0.0
	var data: PackedByteArray = flip["data"]
	var fb := int(cfg["frame_bytes"])
	for fr in range(0, int(cfg["frames"]), 3):
		for part in flip["parts"]:
			var base: int = fb * fr + int(part["off"])
			var f := data.slice(base, base + int(part["n"]) * 12).to_float32_array()
			for j in range(0, f.size(), 3):
				r = maxf(r, Vector2(f[j], f[j + 2]).length())
				top = maxf(top, f[j + 1])
	var e := deg_to_rad(Hex.ELEV_DEG)
	var m := 12
	W = int(ceil(2.0 * r * Hex.PPM)) + 2 * m
	var below := r * sin(e) * Hex.PPM
	var above := (r * sin(e) + top * cos(e)) * Hex.PPM
	H = int(ceil(above + below)) + 2 * m
	FOOT_Y = int(ceil(above)) + m
	BIG_W = W; BIG_H = H; BIG_FOOT_Y = FOOT_Y
	LYING = []


func _sync_flipbook(clip: String, t_frames: float) -> void:
	var c: Dictionary = cfg["clips"].get(clip, cfg["clips"].get("idle"))
	var n := int(c["frames"])
	var k := int(t_frames)
	k = posmod(k, n) if c["loop"] else clampi(k, 0, n - 1)
	for part in flip["parts"]:
		(part["mi"] as MeshInstance3D).mesh = _flip_mesh(part, int(c["first"]) + k)


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
	if not _measured and is_inside_tree() and anim and anim.is_node_ready() and skel:
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
	if not flip.is_empty():
		_sync_flipbook(clip, t_frames)
		return
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
	if anim != null and not anim.is_node_ready():
		_last_key = ""                                     # not posed yet: try again next frame
	_apply_inplace(clip, t)
	if gun:
		gun.visible = clip.begins_with("pistol")
	if not is_nan(pitch) and w > 0.0:
		_apply_pitch(pitch * w)


func _yaw_for(facing_deg: float) -> float:
	var g := Vector2(cos(deg_to_rad(facing_deg)), sin(deg_to_rad(facing_deg)))
	return atan2(g.x, -g.y) + _yaw_offset                      # +Z forward models; ground y is -Z


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
