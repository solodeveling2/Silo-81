extends SceneTree
## Debug: sprite idle (top row) vs live 3D puppet (bottom row) for the six directions -> /tmp/puppet_dirs.png
func _init() -> void:
	var root := Node2D.new()
	get_root().add_child(root)
	if OS.has_environment("ZOOM"): root.scale = Vector2.ONE * float(OS.get_environment("ZOOM"))
	RenderingServer.set_default_clear_color(Color(0.45, 0.42, 0.38))
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://characters/player_male/character.json"))
	var pups := []
	var args := OS.get_cmdline_user_args()
	var clip: String = args[0] if args.size() > 0 else "idle"
	var dd: int = int(args[1]) if args.size() > 1 else -1
	var pitch: float = float(args[2]) if args.size() > 2 else NAN
	var fr := []
	for d in 6:
		var di := d if dd < 0 else dd
		var f := 0 if dd < 0 else int(d * data["animations"][clip]["frames"] / 6.0)
		if clip == "pistol_hold":
			var hp: Array = data["aim"]["hold_pitches"]
			f = hp.find(-60.0 + 20.0 * d) if hp.find(-60.0 + 20.0 * d) >= 0 else hp.find(int(-60 + 20 * d))
		fr.append([di, f])
		var info: Dictionary = data["animations"][clip]["directions"][str(di)]
		var sheet: Texture2D = load("res://characters/player_male/" + info["sheet"])
		var at := AtlasTexture.new(); at.atlas = sheet
		var cols: int = info["columns"]; var fw: int = info["frame_size"][0]; var fh: int = info["frame_size"][1]
		at.region = Rect2((f % cols) * fw, (f / cols) * fh, fw, fh)
		var s := Sprite2D.new(); s.texture = at; s.centered = false
		s.position = Vector2(110 + d * 200, 330); s.offset = -Vector2(info["feet_anchor"][0], info["feet_anchor"][1])
		if not OS.has_environment("NOSPR"): root.add_child(s)
		var p := Puppet3D.new(); p.setup("res://characters/player_3d/player.glb", "res://characters/player_3d/player.json")
		p.position = Vector2(110 + d * 200, 680); root.add_child(p); pups.append(p)
	for i in 30:
		for d in 6:
			pups[d].sync(clip, fr[d][1], float(data["animations"][clip]["fps"]), fr[d][0] * 60.0, (-60.0 + 20.0 * d) if clip == "pistol_hold" else pitch, 1.0)
		await process_frame
	get_root().get_texture().get_image().save_png("/tmp/puppet_%s.png" % clip)
	quit()
