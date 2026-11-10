extends SceneTree
## Debug: Junk Town is walkable from the road through the gate to the yard, the pen and the far shacks.
func _init() -> void:
	var lv := Level.new()
	get_root().add_child(lv)
	lv.build("res://levels/JT", {})
	var start := lv.nearest_walkable(Vector2(-3.0, 0.0))
	for t in [["burn barrel", Vector2(12.6, 0.6)], ["goat pen", Vector2(18.6, -8.6)], ["Mara's garage", Vector2(13.6, 10.0)],
			["market shack", Vector2(25.6, 5.0)], ["exit stair", Vector2(-6.0, 0.0)]]:
		var h := lv.nearest_walkable(t[1])
		var p := lv.find_path(start, h)
		print("PATH ", t[0], ": ", "ok, " + str(p.size()) + " steps" if p.size() > 0 else "NONE")
	quit()
