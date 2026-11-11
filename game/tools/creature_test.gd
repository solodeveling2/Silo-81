extends SceneTree
## Debug: the Blender-built enemies (feral, infected) live in the toon shader, rows = creatures,
## columns = clips at chosen frames, two facings -> /tmp/creature_test.png (env FACE: facing degrees).
const ROWS := [
	["res://characters/feral_3d/feral.glb", "res://characters/feral_3d/feral.json",
	 [["idle", 0.0, 12.0], ["walk", 3.0, 24.0], ["walk", 13.0, 24.0], ["bite", 8.0, 24.0], ["bite", 11.0, 24.0], ["hit", 4.0, 24.0], ["death", 36.0, 24.0]]],
	["res://characters/infected_3d/infected.glb", "res://characters/infected_3d/infected.json",
	 [["idle", 8.0, 12.0], ["walk", 5.0, 24.0], ["run", 7.0, 24.0], ["bite", 4.0, 24.0], ["bite", 7.0, 24.0], ["hit", 6.0, 30.0], ["death", 57.0, 24.0]]],
	["res://characters/pipe_worm_3d/worm_meshy.glb", "res://characters/pipe_worm_3d/worm_meshy.json",
	 [["idle", 0.0, 24.0], ["crawl", 6.0, 24.0], ["crawl", 14.0, 24.0], ["bite", 6.0, 24.0], ["bite", 11.0, 24.0], ["chew", 8.0, 24.0], ["death", 32.0, 24.0]]],
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
		rows = [[ROWS[0][0], ROWS[0][1], cols], [ROWS[1][0], ROWS[1][1], cols], [ROWS[2][0], ROWS[2][1], cols]]
	if OS.has_environment("ONLY"):                      # e.g. ONLY=0 (feral) or ONLY=1 (infected)
		rows = [rows[int(OS.get_environment("ONLY"))]]
	var sc := float(OS.get_environment("SCALE")) if OS.has_environment("SCALE") else 0.62
	var step := 250.0 * sc / 0.62
	var pups := []
	for r in rows.size():
		for fi in 2:
			var cols: Array = rows[r][2]
			for c in cols.size():
				var p := Puppet3D.new()
				p.setup(rows[r][0], rows[r][1])
				p.position = Vector2(step * 0.6 + c * step, step + (r * 2 + fi) * step)
				p.scale = Vector2(sc, sc)
				root.add_child(p)
				pups.append([p, cols[c], facings[fi]])
	for i in 30:
		for e in pups:
			e[0].sync(e[1][0], e[1][1], e[1][2], e[2], NAN, 1.0)
		await process_frame
	get_root().get_texture().get_image().save_png("/tmp/creature_test.png")
	quit()
