extends SceneTree
## Debug: the live 3D goat, 4 facings (rows) x 5 moments of the grazing loop (columns) -> /tmp/goat_test.png
func _init() -> void:
	var root := Node2D.new()
	get_root().add_child(root)
	RenderingServer.set_default_clear_color(Color(0.62, 0.64, 0.66))
	var pups := []
	for r in 4:
		for c in 5:
			var coat := "piebald" if r == 3 else "brown"
			var p := Puppet3D.new()
			p.setup("res://characters/goat_3d/goat_%s.glb" % coat, "res://characters/goat_3d/goat_%s.json" % coat)
			p.position = Vector2(110 + c * 220, 160 + r * 170)
			root.add_child(p)
			pups.append([p, r * 90.0 + 30.0, c * 9.6])
	for i in 30:
		for e in pups:
			e[0].sync("idle", e[2], 12.0, e[1], NAN, 1.0)
		await process_frame
	get_root().get_texture().get_image().save_png("/tmp/goat_test.png")
	quit()
