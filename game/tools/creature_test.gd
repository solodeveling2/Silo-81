extends SceneTree
## Debug: the Blender-built enemies (feral, infected) live in the toon shader, rows = creatures,
## columns = clips at chosen frames, two facings -> /tmp/creature_test.png (env FACE: facing degrees).
const ROWS := [
	["res://characters/feral_3d/feral.glb", "res://characters/feral_3d/feral.json",
	 [["idle", 0.0, 12.0], ["walk", 3.0, 24.0], ["walk", 13.0, 24.0], ["bite", 6.0, 24.0], ["bite", 11.0, 24.0], ["hit", 4.0, 24.0], ["death", 36.0, 24.0]]],
	["res://characters/infected_3d/infected.glb", "res://characters/infected_3d/infected.json",
	 [["idle", 8.0, 12.0], ["walk", 5.0, 24.0], ["walk", 25.0, 24.0], ["bite", 8.0, 24.0], ["bite", 13.0, 24.0], ["hit", 4.0, 24.0], ["death", 40.0, 24.0]]],
]
func _init() -> void:
	var root := Node2D.new()
	get_root().add_child(root)
	RenderingServer.set_default_clear_color(Color(0.66, 0.68, 0.71))
	var facings := [300.0, 120.0]
	if OS.has_environment("FACE"):
		facings = [float(OS.get_environment("FACE")), float(OS.get_environment("FACE")) + 180.0]
	var rows := ROWS
	if OS.has_environment("CLIPS"):                     # e.g. CLIPS=death:0,12,24,36
		var cs := OS.get_environment("CLIPS").split(":")
		var cols := []
		for fr in cs[1].split(","):
			cols.append([cs[0], float(fr), 24.0])
		rows = [[ROWS[0][0], ROWS[0][1], cols], [ROWS[1][0], ROWS[1][1], cols]]
	var pups := []
	for r in rows.size():
		for fi in 2:
			var cols: Array = rows[r][2]
			for c in cols.size():
				var p := Puppet3D.new()
				p.setup(rows[r][0], rows[r][1])
				p.position = Vector2(150 + c * 250, 250 + (r * 2 + fi) * 250)
				p.scale = Vector2(0.62, 0.62)
				root.add_child(p)
				pups.append([p, cols[c], facings[fi]])
	for i in 30:
		for e in pups:
			e[0].sync(e[1][0], e[1][1], e[1][2], e[2], NAN, 1.0)
		await process_frame
	get_root().get_texture().get_image().save_png("/tmp/creature_test.png")
	quit()
