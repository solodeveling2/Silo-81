extends SceneTree
## Debug: everywhere on the road and in Junk Town is reachable from the Silo portal.
func _init() -> void:
	var lv := Level.new()
	get_root().add_child(lv)
	lv.build("res://levels/RD", {})
	var start := lv.nearest_walkable(Vector2(4.5, 8.2))
	var bad := 0
	for t in [["guard post", Vector2(13.0, 7.2)], ["car graveyard", Vector2(7.6, -7.6)], ["stalled car", Vector2(36.0, -2.0)],
			["rest stop pumps", Vector2(44.0, 6.4)], ["kiosk door", Vector2(45.0, 9.2)], ["billboard", Vector2(55.0, 10.6)],
			["graves", Vector2(59.0, -4.4)], ["gate", Vector2(64.0, 0.0)], ["burn barrel", Vector2(76.0, 0.6)],
			["bunkhouse", Vector2(69.2, 6.4)], ["clinic", Vector2(74.6, 7.4)], ["Mara's garage", Vector2(85.6, 6.8)],
			["market shack", Vector2(85.0, 4.6)], ["water store", Vector2(85.0, -1.6)], ["goat pen", Vector2(84.0, -7.6)],
			["tea house", Vector2(70.4, -6.8)], ["tool shed", Vector2(75.8, -9.8)], ["notice board", Vector2(69.6, -2.4)]]:
		var h := lv.nearest_walkable(t[1], 2.0)
		var p := lv.find_path(start, h)
		if p.is_empty():
			bad += 1
		print("PATH ", t[0], ": ", ("ok, %d steps" % p.size()) if p.size() > 0 else "NONE")
	print("PATH unreachable ", bad)
	quit()
