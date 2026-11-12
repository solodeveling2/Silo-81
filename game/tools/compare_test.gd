extends SceneTree
## Debug: two live models side by side in the toon shader (old vs new), a few facings, one clip frame.
## env: A=glb,json  B=glb,json  CLIP=idle  FRAME=0  SCALE=1.4  OUT=/tmp/compare.png
func _init() -> void:
	var root := Node2D.new()
	get_root().add_child(root)
	RenderingServer.set_default_clear_color(Color(0.42, 0.42, 0.40))
	var sides := [OS.get_environment("A").split(","), OS.get_environment("B").split(",")]
	var clip := OS.get_environment("CLIP") if OS.has_environment("CLIP") else "idle"
	var fr := float(OS.get_environment("FRAME")) if OS.has_environment("FRAME") else 0.0
	var sc := float(OS.get_environment("SCALE")) if OS.has_environment("SCALE") else 1.4
	var facings := [300.0, 0.0, 120.0]
	var pups := []
	var step := 360.0 * sc / 1.4
	for r in 2:
		for c in facings.size():
			var p := Puppet3D.new()
			p.setup(sides[r][0], sides[r][1])
			p.position = Vector2(step * 0.7 + c * step, step * 0.85 + r * step)
			p.scale = Vector2(sc, sc)
			root.add_child(p)
			pups.append([p, facings[c]])
	for i in 30:
		for e in pups:
			e[0].sync(clip, fr, 24.0, e[1], NAN, 1.0)
		await process_frame
	get_root().get_texture().get_image().save_png(OS.get_environment("OUT") if OS.has_environment("OUT") else "/tmp/compare.png")
	quit()
