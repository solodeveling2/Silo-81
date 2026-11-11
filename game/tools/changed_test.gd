extends SceneTree
## Debug: the Changed, 3 coat variants (rows) x idle, walk, claw (hit frame), hit, death (end) -> /tmp/changed_test.png
const COATS := [Color(0.22, 0.17, 0.13), Color(0.15, 0.18, 0.23), Color(0.19, 0.19, 0.18)]
func _init() -> void:
	var root := Node2D.new()
	get_root().add_child(root)
	RenderingServer.set_default_clear_color(Color(0.66, 0.68, 0.71))
	var facing := float(OS.get_environment("FACE")) if OS.has_environment("FACE") else 300.0
	var cols := [["idle", 0.0, 12.0], ["walk", 14.0, 24.0], ["bite", 13.0, 24.0], ["hit", 8.0, 24.0], ["death", 58.0, 24.0]]
	var pups := []
	for r in 3:
		for c in cols.size():
			var p := Puppet3D.new()
			p.setup("res://characters/changed_3d/changed.glb", "res://characters/changed_3d/changed.json")
			p.position = Vector2(120 + c * 230, 330 + r * 300)
			root.add_child(p)
			p.set_duotone(COATS[r], Color(0.74, 0.75, 0.70))
			pups.append([p, cols[c]])
	for i in 30:
		for e in pups:
			e[0].sync(e[1][0], e[1][1], e[1][2], facing, NAN, 1.0)
		await process_frame
	get_root().get_texture().get_image().save_png("/tmp/changed_test.png")
	quit()
