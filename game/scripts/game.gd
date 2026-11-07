extends Node2D
## Silo 81 playable slice: click to move, Wasteland 3-style action bar on 1-5,
## turn-based combat with action points and Overwatch, doors you can pick or force,
## and the first repair job: worms chewing the heating pipes on Level 3.

const PLAYER_JSON := "res://characters/player_male/character.json"
const WORM_JSON := "res://characters/pipe_worm/character.json"
const TIBOR_JSON := "res://characters/tibor/character.json"
const TIBOR_START := Vector2(-3.0, 0.2)         # comes in from the lift landing
const TIBOR_POST := Vector2(1.2, -0.9)          # then waits in the corridor by the stairs
const CALL_NO := "81-214"
const AP_MAX := 8
const WORM_AP := 6
const WORM_HP := 14
const SHOT_AP := 3
const WELD_AP := 4
const MED_AP := 2
const PICK_AP := 2
const FORCE_AP := 4
const SIGHT := 6
const RANGE := 12

var hud: Hud
var cam: Camera2D
var mood: CanvasModulate
var marks: Marks
var level: Level
var level_id := "L2"
var player: Actor
var worms: Array = []
var mode := "explore"
var my_turn := true
var busy := false
var action := ""
var overwatch := 0
var pending_overwatch: Actor = null
var pending_combat := false
var focus: Node2D
var hover_hex := Vector2i(999999, 0)
var hover_worm: Actor = null
var hover_target := {}
var path_preview: Array = []
var dialog_handler := Callable()
var rng := RandomNumberGenerator.new()
var stats := {"hp": 40, "hp_max": 40, "ap": AP_MAX, "str": 6, "lockpick": 45, "medkits": 2, "kit": false}
var state := {"L2": {}, "L2W": {}, "L3": {"dead": [], "pipe_fixed": false}, "L4W": {}}
var flags := {"visited_L3": false, "found_leak": false, "seen_worms": false, "door_seen": false,
			  "quest": "none"}        # maintenance call: none -> given -> done (reported back to Tibor)
var tibor: Actor = null
var aim_target: Actor = null      # what the gun is held on between shots


func _ready() -> void:
	rng.randomize()
	hud = Hud.new()
	add_child(hud)
	hud.slot_pressed.connect(_on_slot)
	hud.end_turn_pressed.connect(end_turn)
	hud.dialog_choice.connect(_on_dialog_choice)
	hud.restart_pressed.connect(func() -> void: get_tree().reload_current_scene())
	cam = Camera2D.new()
	cam.zoom = Vector2(0.62, 0.62)
	cam.position_smoothing_enabled = true
	cam.position_smoothing_speed = 6.0
	add_child(cam)
	mood = CanvasModulate.new()
	add_child(mood)
	load_level("L2", Vector2.INF)
	hud.log_msg("Click to move. 1-5 or click the bar to pick an action, then click a target. Right-click cancels.", Hud.DIM)
	var testing := false
	for a in ["--autotest", "--test-commons", "--test-command", "--view-pipe"]:
		testing = testing or a in OS.get_cmdline_user_args()
	if testing:
		flags["quest"] = "given"                     # tests skip the opening scene
	else:
		intro.call_deferred()
	if "--autotest" in OS.get_cmdline_user_args():
		autotest.call_deferred()
	elif "--test-commons" in OS.get_cmdline_user_args():
		test_commons.call_deferred()
	elif "--test-command" in OS.get_cmdline_user_args():
		test_command.call_deferred()
	elif "--view-pipe" in OS.get_cmdline_user_args():           # debug: start at the burst pipe on Level 3
		load_level.call_deferred("L3", Vector2(6.6, -0.2))


# ================================================================== levels
func load_level(id: String, arrive: Vector2) -> void:
	if level:
		level.queue_free()
	worms.clear()
	level_id = id
	level = Level.new()
	add_child(level)
	move_child(level, 0)
	var st: Dictionary = state[id].duplicate()
	level.build("res://levels/" + id, st)
	marks = Marks.new()
	marks.game = self
	level.marks.add_child(marks)
	player = Actor.new()
	player.setup(PLAYER_JSON, "player")
	player.team = "player"
	player.display_name = "You"
	player.ring_color = Color(0.45, 0.8, 0.4, 0.8)
	level.sorted.add_child(player)
	var sp: Array = level.data["spawns"]["player"]
	var at := Vector2(sp[0], sp[1]) if arrive == Vector2.INF else arrive
	player.place_at_hex(level.nearest_walkable(at))
	player.play("idle", int(sp[2]) if arrive == Vector2.INF else 5)
	player.stepped.connect(_on_player_step)
	focus = player
	cam.position = player.position + Vector2(0, -80)
	cam.reset_smoothing()
	var bg: Dictionary = level.data["bg"]
	var tex: Texture2D = level.get_child(0).texture
	cam.limit_left = int(bg["x0"]) - 300
	cam.limit_top = int(bg["y0"]) - 300
	cam.limit_right = int(bg["x0"] + tex.get_width()) + 300
	cam.limit_bottom = int(bg["y0"] + tex.get_height()) + 300
	var i := 0
	for w in level.data["spawns"]["worms"]:
		if not (i in state["L3"]["dead"]):
			var a := Actor.new()
			a.setup(WORM_JSON, "worm")
			a.team = "hostile"
			a.display_name = "Pipe worm"
			a.hp = WORM_HP; a.hp_max = WORM_HP
			a.set_meta("index", i)
			level.sorted.add_child(a)
			a.place_at_hex(level.nearest_walkable(Vector2(w[0], w[1])))
			if w.size() > 3 and w[3] == "chew" and a.has_clip("chew"):
				a.set_meta("latched", true)         # teeth in the burst pipe until something disturbs it
				a.play("chew", int(w[2]))
			else:
				a.play("idle", int(w[2]))
				a.sprite.speed_scale = rng.randf_range(0.85, 1.1)
			a.stepped.connect(_on_worm_step.bind(a))
			worms.append(a)
		i += 1
	tibor = null
	if id == "L2" and FileAccess.file_exists(TIBOR_JSON):
		tibor = Actor.new()
		tibor.setup(TIBOR_JSON, "npc")
		tibor.team = "friendly"
		tibor.display_name = "Tibor"
		level.sorted.add_child(tibor)
		tibor.place_at_hex(level.nearest_walkable(TIBOR_START if flags["quest"] == "none" else TIBOR_POST))
		tibor.play("idle", 0 if flags["quest"] == "none" else 2)
	mood.color = Color(0.86, 0.9, 0.92) if id == "L3" else Color(0.93, 0.94, 1.0)
	if id == "L3":
		flags["visited_L3"] = true
	mode = "explore"
	my_turn = true
	action = ""
	hud.show_banner("SILO 81 - " + level.data["name"].to_upper())
	refresh()


# ================================================================== input
func _unhandled_input(e: InputEvent) -> void:
	if e is InputEventMouseMotion:
		_update_hover()
	elif e is InputEventMouseButton and e.pressed:
		match e.button_index:
			MOUSE_BUTTON_WHEEL_UP:
				cam.zoom = (cam.zoom * 1.1).clamp(Vector2(0.35, 0.35), Vector2(1.1, 1.1))
			MOUSE_BUTTON_WHEEL_DOWN:
				cam.zoom = (cam.zoom / 1.1).clamp(Vector2(0.35, 0.35), Vector2(1.1, 1.1))
			MOUSE_BUTTON_RIGHT:
				if hud.dialog_open():
					hud.close_dialog()
				action = ""
				refresh()
			MOUSE_BUTTON_LEFT:
				if not hud.over_ui(e.position):
					_click()
	elif e is InputEventKey and e.pressed and not e.echo:
		if hud.dialog_open():
			if e.keycode >= KEY_1 and e.keycode <= KEY_9:
				_on_dialog_choice(e.keycode - KEY_1)
			elif e.keycode == KEY_ESCAPE:
				hud.close_dialog()
			return
		match e.keycode:
			KEY_1, KEY_2, KEY_3, KEY_4, KEY_5:
				_on_slot(e.keycode - KEY_1)
			KEY_SPACE:
				end_turn()
			KEY_ESCAPE:
				action = ""
				refresh()


func can_act() -> bool:
	return player.alive and not busy and not hud.dialog_open() and (mode == "explore" or my_turn)


func _update_hover() -> void:
	var world := get_global_mouse_position()
	if hud.over_ui(get_viewport().get_mouse_position()):
		hud.show_tooltip("", Vector2.ZERO)
		return
	hover_worm = worm_at(world)
	for w in worms:
		w.highlight = (w == hover_worm)
	hover_target = {} if hover_worm else level.pick(world)
	hover_hex = Hex.screen_to_hex(world)
	path_preview = []
	var tip := ""
	if hover_worm:
		tip = "Pipe worm  -  %d/%d HP" % [hover_worm.hp, hover_worm.hp_max]
		if action in ["", "attack"]:
			var ok := level.line_of_sight(player.hex, hover_worm.hex)
			tip += "\nShoot: %d%% to hit, %d AP" % [hit_chance(player.hex, hover_worm.hex), SHOT_AP] if ok else "\nNo clear shot"
	elif npc_at(world) and mode != "combat":
		tip = "Tibor, maintenance dispatcher  (click to talk)"
	elif not hover_target.is_empty():
		tip = hover_target["name"]
		if hover_target["kind"] in ["door", "toolbox", "stairs", "pipe"]:
			tip += "  (click to use)"
		else:
			tip += "  (click to look)"
	elif level.walkable.has(hover_hex) and action == "" and can_act():
		path_preview = level.find_path(player.hex, hover_hex, occupied(player))
		if mode == "combat" and not path_preview.is_empty():
			tip = "Move: %d AP" % path_preview.size()
			if path_preview.size() > stats["ap"]:
				tip = "Move: %d AP (you have %d)" % [path_preview.size(), stats["ap"]]
	hud.show_tooltip(tip, get_viewport().get_mouse_position())
	marks.queue_redraw()


func worm_at(world: Vector2) -> Actor:
	var best: Actor = null
	for w in worms:
		if w.alive and w.sprite_rect().grow(-6).has_point(world):
			if best == null or w.position.y > best.position.y:
				best = w
	return best


func occupied(except: Actor) -> Array:
	var out: Array = []
	if player != except and player.alive:
		out.append(player.hex)
	for w in worms:
		if w != except and w.alive:
			out.append(w.hex)
	if tibor and tibor != except:
		out.append(tibor.hex)
	return out


func npc_at(world: Vector2) -> Actor:
	if tibor and tibor.sprite_rect().grow(-10).has_point(world):
		return tibor
	return null


func _click() -> void:
	if not can_act():
		return
	var world := get_global_mouse_position()
	var worm := worm_at(world)
	var target := {} if worm else level.pick(world)
	var act := action
	action = ""
	match act:
		"attack":
			if worm:
				attack(worm)
			else:
				hud.log_msg("Pick a target for the Tokarev.", Hud.DIM)
		"inspect":
			if worm:
				hud.log_msg("Pipe worm: blind, toothed, as thick as a forearm. They chew the lagging for the warmth. (%d/%d HP)" % [worm.hp, worm.hp_max])
			elif not target.is_empty():
				interact(target)
			else:
				hud.log_msg("Nothing there worth a second look.", Hud.DIM)
		"weld":
			if not target.is_empty() and target["kind"] == "pipe":
				interact(target)
			else:
				hud.log_msg("Use the welding kit on something that needs welding.", Hud.DIM)
		_:
			if worm:
				attack(worm)
			elif npc_at(world) and mode != "combat":
				talk_tibor()
			elif not target.is_empty():
				interact(target)
			else:
				move_to(Hex.screen_to_hex(world))
	refresh()


func _on_slot(i: int) -> void:
	if not player.alive or busy:
		return
	match i:
		0:
			action = "" if action == "attack" else "attack"
		1:
			set_overwatch()
		2:
			action = "" if action == "inspect" else "inspect"
		3:
			if stats["kit"]:
				action = "" if action == "weld" else "weld"
			else:
				hud.log_msg("You don't have the welding kit. It's in your toolbox.", Hud.DIM)
		4:
			use_medkit()
	refresh()


# ================================================================== movement and interaction
func move_to(h: Vector2i) -> void:
	if not level.walkable.has(h) or h == player.hex:
		return
	var path := level.find_path(player.hex, h, occupied(player))
	if path.is_empty():
		hud.log_msg("You can't get there.", Hud.DIM)
		return
	await walk(path)


func walk(path: Array) -> void:
	if mode == "combat":
		if stats["ap"] <= 0:
			hud.log_msg("No action points left. End your turn.", Hud.DIM)
			return
		path = path.slice(0, stats["ap"])
	busy = true
	var clip := "run" if (mode == "explore" and path.size() > 5) else "walk"
	player.follow(path, clip)
	await player.arrived
	busy = false
	if pending_combat:
		pending_combat = false
		start_combat("The worms stop chewing. Blind heads turn towards your footsteps.")
	refresh()


func _on_player_step(h: Vector2i) -> void:
	if mode == "combat":
		stats["ap"] -= 1
		refresh()
		return
	if level_id == "L3":
		if not flags["found_leak"] and Hex.plan_to_ground(Vector2(level.pipe["u"], level.pipe["v"])).distance_to(player.ground) < 5.0:
			flags["found_leak"] = true
			hud.log_msg("Water sprays from the heating flow, the lowest pipe on the wall. A worm hangs off it with its teeth in the steel.")
		for w in worms:
			if w.alive and Hex.distance(h, w.hex) <= SIGHT and level.line_of_sight(h, w.hex):
				player.stop_now()
				pending_combat = true
				return


func go_near(t: Dictionary) -> bool:
	var cands := level.approach_hexes(t)
	if player.hex in cands:
		player.face_ground(Hex.plan_to_ground(t["plan"]))
		player.play(player.idle_clip(mode == "combat"), player.dir)
		return true
	var best: Array = []
	for h in cands:
		var p := level.find_path(player.hex, h, occupied(player))
		if not p.is_empty() and (best.is_empty() or p.size() < best.size()):
			best = p
	if best.is_empty():
		hud.log_msg("You can't reach it from here.", Hud.DIM)
		return false
	if mode == "combat" and best.size() > stats["ap"]:
		hud.log_msg("Not enough action points to get there.", Hud.DIM)
		return false
	await walk(best)
	if mode == "combat" and pending_combat:
		return false
	if not (player.hex in cands):
		return false
	player.face_ground(Hex.plan_to_ground(t["plan"]))
	player.play(player.idle_clip(mode == "combat"), player.dir)
	return true


func interact(t: Dictionary) -> void:
	match t["kind"]:
		"look", "prop":
			player.face_ground(Hex.plan_to_ground(t["plan"]))
			player.play(player.idle_clip(mode == "combat"), player.dir)
			hud.log_msg("%s: %s" % [t["name"], t["text"]])
		"door":
			if await go_near(t):
				door_dialog(t["id"])
		"toolbox":
			if await go_near(t):
				toolbox_dialog(t)
		"stairs":
			if mode == "combat":
				hud.log_msg("Not with worms at your back.", Hud.DIM)
				return
			if await go_near(t):
				hud.log_msg(t["text"])
				load_level(t["to"], Vector2(t["arrive"][0], t["arrive"][1]))
		"pipe":
			flags["found_leak"] = true
			if await go_near(t):
				pipe_dialog()
	refresh()


func open_dialog(title: String, text: String, options: Array, handler: Callable) -> void:
	dialog_handler = handler
	hud.open_dialog(title, text, options)


func _on_dialog_choice(i: int) -> void:
	var h := dialog_handler
	hud.close_dialog()
	dialog_handler = Callable()
	if h.is_valid():
		h.call(i)
	refresh()


func toolbox_dialog(t: Dictionary) -> void:
	if stats["kit"]:
		hud.log_msg("Your toolbox. Spanners, a dead torch, no welding kit: you have that.")
		return
	open_dialog(t["name"], t["text"], [{"label": "Take the welding kit"}, {"label": "Leave it"}], _toolbox_choice)


func _toolbox_choice(i: int) -> void:
	if i == 0:
		stats["kit"] = true
		hud.log_msg("You take the welding kit. (Slot 4)", Hud.GREEN)


func door_dialog(id: String) -> void:
	var d: Dictionary = level.doors[id]
	var dd: Dictionary = d["data"]
	if d["open"]:
		hud.log_msg("%s: %s" % [dd["name"], "It's open."])
		return
	if not d["locked"]:
		_open_door(id, "The door swings open.")
		return
	flags["door_seen"] = true
	var combat := mode == "combat"
	var pick_label := "Pick the lock  (Lockpick %d%%)" % stats["lockpick"]
	var force_label := "Force it  (needs Strength %d, you have %d)" % [dd["strength"], stats["str"]]
	if combat:
		pick_label += "  %d AP" % PICK_AP
		force_label += "  %d AP" % FORCE_AP
	open_dialog(dd["name"], dd["text"], [{"label": pick_label}, {"label": force_label}, {"label": "Leave"}], _door_choice.bind(id))


func _door_choice(i: int, id: String) -> void:
	var dd: Dictionary = level.doors[id]["data"]
	var combat := mode == "combat"
	if i == 0:
		if combat:
			if stats["ap"] < PICK_AP:
				hud.log_msg("Not enough action points.", Hud.DIM)
				return
			stats["ap"] -= PICK_AP
		if rng.randi_range(1, 100) <= stats["lockpick"]:
			_open_door(id, "The last pin sets. The padlock drops into your hand.")
		else:
			hud.log_msg("The pins slip under the pick. You can try again.", Hud.DIM)
	elif i == 1:
		if combat:
			if stats["ap"] < FORCE_AP:
				hud.log_msg("Not enough action points.", Hud.DIM)
				return
			stats["ap"] -= FORCE_AP
		if stats["str"] >= int(dd["strength"]):
			_open_door(id, "You put your shoulder into it. The hasp tears out of the frame.")
		else:
			hud.log_msg("It won't budge. (Strength %d needed)" % dd["strength"], Hud.DIM)
	refresh()


func _open_door(id: String, msg: String) -> void:
	level.doors[id]["locked"] = false
	level.set_door_open(id, true)
	state[level_id]["door_" + id] = true
	state[level_id]["locked_" + id] = false
	hud.log_msg(msg, Hud.GREEN)
	if id == "door_2_d":
		hud.log_msg("Room 2-D. Frost on everything, a stripped bunk, a chair on its side. Whoever lived here left in a hurry, or never left.")


func pipe_dialog() -> void:
	if state["L3"]["pipe_fixed"]:
		hud.log_msg("%s: %s" % [level.pipe["name"], level.pipe["fixed_text"]])
		return
	if not stats["kit"]:
		hud.log_msg("%s: %s You need your welding kit." % [level.pipe["name"], level.pipe["text"]])
		return
	var lbl := "Weld it" + ("  (%d AP)" % WELD_AP if mode == "combat" else "")
	open_dialog(level.pipe["name"], level.pipe["text"], [{"label": lbl}, {"label": "Leave it"}], _pipe_choice)


func _pipe_choice(i: int) -> void:
	if i == 0:
		weld()


func weld() -> void:
	if mode == "combat":
		if stats["ap"] < WELD_AP:
			hud.log_msg("Not enough action points to weld.", Hud.DIM)
			return
		stats["ap"] -= WELD_AP
	busy = true
	var sparks := _sparks(Hex.plan_to_screen(Vector2(level.pipe["u"], level.pipe["v"] - 0.37), 1.15))
	await get_tree().create_timer(1.6).timeout
	sparks.emitting = false
	state["L3"]["pipe_fixed"] = true
	level.set_pipe(true)
	busy = false
	hud.log_msg("You weld the flow pipe shut and wrap it in fresh lagging. The hiss stops.", Hud.GREEN)
	if live_worms().is_empty():
		_finish_job()
	else:
		hud.log_msg("The worms are still here.", Hud.DIM)
	refresh()


func _finish_job() -> void:
	hud.show_banner("PRESSURE RESTORED")
	hud.log_msg("MIRA, on the gallery intercom: \"Pressure's climbing on the general circuit! The dorms will feel that tonight.\"", Color(0.75, 0.85, 0.95))
	hud.log_msg("Report back to Tibor on Level 2 to close the call.", Color(1.0, 0.8, 0.4))


# ================================================================== Tibor: the maintenance dispatcher, and the first call
# The opening scene: Tibor runs in from the landing, shoves your door open and gives you the job.
# The call is mandatory (it teaches moving, using things, combat, consumables and welding), but how
# you go about it is yours.
const TIBOR_TITLE := "TIBOR  -  maintenance dispatcher"
var _talk_node := ""
const TALK := {
	"intro": {"text": "Chief! Good, you're up. Mira's on the line from Engineering: pressure on the general circuit is falling like a stone. Something's gone on Three, in the pipe gallery. If the flow goes, this whole level freezes by morning.",
			  "options": [["What do we know?", "know"], ["I'm on it.", "go"]]},
	"know": {"text": "Not much. The gauge in the pump room is dropping and there's water on the gallery floor. Rus swears he heard scratching in the pipes last week. Rus hears a lot of things.",
			 "options": [["Scratching?", "worms"], ["Right. I'll take a look.", "go"]]},
	"worms": {"text": "Pipe worms, maybe. They come up the old drains when it's warm, and nothing on Three is warmer than that flow pipe. Take the Tokarev. And a medkit, if you've still got one.",
			  "options": [["Anything else?", "go"]]},
	"go": {"text": "Your welding kit's in the toolbox by your bed. Stairs to Three are at the end of the corridor. I'm logging it as maintenance call %s. Go, Chief. I'll keep Mira off your back.",
		   "options": [["On my way.", "accept"]]},
	"waiting": {"text": "Still here, Chief? Three. The pipe gallery. Every minute that pipe sprays is a cold night for somebody.",
				"options": [["Going.", "close"]]},
	"report": {"text": "Mira says the pressure's back. Worms, was it? The Council will want that in writing, and they'll want it to be somebody else's fault.\nThat's call %s closed. Here: Dr. Kiss left this for whoever came back bleeding. You'll need it more than I will.",
			   "options": [["Thanks, Tibor.", "closed"]]},
	"after": {"text": "Three more calls on the board, all marked urgent by the Council, none of them urgent. They'll keep till morning. Get some sleep, if the radiators let you.",
			  "options": [["Goodnight, Tibor.", "close"]]},
}


func intro() -> void:
	if tibor == null or flags["quest"] != "none":
		return
	busy = true
	await get_tree().create_timer(0.8).timeout
	level.set_door_open("door_2_1", true)
	state["L2"]["door_door_2_1"] = true
	var target := player.hex
	var path := level.find_path(tibor.hex, target, [])
	if path.size() > 1:
		path = path.slice(0, path.size() - 1)          # stop next to you, not on you
	focus = tibor
	tibor.follow(path, "run" if tibor.has_clip("run") else "walk")
	await tibor.arrived
	tibor.face_ground(player.ground); tibor.play("idle", tibor.dir)
	player.face_ground(tibor.ground); player.play("idle", player.dir)
	focus = player
	busy = false
	_say("intro")


func talk_tibor() -> void:
	if await go_near({"plan": Hex.ground_to_plan(tibor.ground)}):
		tibor.face_ground(player.ground); tibor.play("idle", tibor.dir)
		if flags["quest"] == "given" and state["L3"]["pipe_fixed"]:
			_say("report")
		elif flags["quest"] == "given":
			_say("waiting")
		else:
			_say("after")


func _say(node: String) -> void:
	_talk_node = node
	var n: Dictionary = TALK[node]
	var txt: String = n["text"]
	if "%s" in txt:
		txt = txt % CALL_NO
	var opts: Array = []
	for o in n["options"]:
		opts.append({"label": o[0]})
	open_dialog(TIBOR_TITLE, txt, opts, _talk_choice)


func _talk_choice(i: int) -> void:
	var nxt: String = TALK[_talk_node]["options"][i][1]
	match nxt:
		"accept":
			flags["quest"] = "given"
			hud.show_banner("MAINTENANCE CALL %s: BURST PIPE, LEVEL 3" % CALL_NO)
			hud.log_msg("New job: maintenance call %s. Your welding kit is in your toolbox (marked)." % CALL_NO, Color(1.0, 0.8, 0.4))
			_tibor_to_post()
		"closed":
			flags["quest"] = "done"
			stats["medkits"] += 1
			hud.show_banner("CALL %s CLOSED" % CALL_NO)
			hud.log_msg("Tibor hands you a medkit. (Medkits: %d)" % stats["medkits"], Hud.GREEN)
		"close":
			pass
		_:
			_say.call_deferred(nxt)
	refresh()


func _tibor_to_post() -> void:
	var path := level.find_path(tibor.hex, level.nearest_walkable(TIBOR_POST), [player.hex])
	if path.is_empty():
		return
	tibor.follow(path, "walk")
	await tibor.arrived
	tibor.play("idle", 2)


# ================================================================== combat
func live_worms() -> Array:
	return worms.filter(func(w): return w.alive)


func start_combat(msg: String) -> void:
	if mode == "combat":
		return
	mode = "combat"
	my_turn = true
	stats["ap"] = AP_MAX
	overwatch = 0
	flags["seen_worms"] = true
	player.set_meta("combat", true)
	player.play("pistol_idle", player.dir)
	for w in live_worms():
		w.set_meta("combat", true)
		w.ring_color = Color(0.85, 0.25, 0.2, 0.8)
		if w.get_meta("latched", false):
			_unlatch(w)
			continue
		w.face_ground(player.ground)
		w.play("idle", w.dir)
	hud.show_banner("COMBAT")
	hud.log_msg(msg, Color(0.95, 0.6, 0.45))
	hud.log_msg("Your turn: %d action points." % AP_MAX, Hud.DIM)
	refresh()


## The worm on the burst pipe lets go, drops back and turns towards you.
func _unlatch(w: Actor) -> void:
	if w.has_clip("release"):
		w.play("release", w.dir)
		await w.anim_done               # nothing else may play on it until it has let go
	w.set_meta("latched", false)
	if w.alive:
		w.face_ground(player.ground)
		w.play("idle", w.dir)


func _wait_unlatched(w: Actor) -> void:
	while w.get_meta("latched", false):
		await get_tree().process_frame


func end_combat() -> void:
	mode = "explore"
	my_turn = true
	overwatch = 0
	player.set_meta("combat", false)
	player.aim_pitch = NAN
	aim_target = null
	player.play("idle", player.dir)
	hud.show_banner("COMBAT OVER")
	hud.log_msg("The last worm curls up and stops moving.", Hud.GREEN)
	if state["L3"]["pipe_fixed"]:
		_finish_job()
	refresh()


func hit_chance(a: Vector2i, b: Vector2i) -> int:
	var d := Hex.distance(a, b)
	return clampi(92 - maxi(0, d - 3) * 5, 20, 95)


func attack(w: Actor) -> void:
	if not w.alive:
		return
	if not level.line_of_sight(player.hex, w.hex):
		hud.log_msg("No clear shot from here.", Hud.DIM)
		return
	if Hex.distance(player.hex, w.hex) > RANGE:
		hud.log_msg("Out of range.", Hud.DIM)
		return
	if mode == "explore":
		start_combat("You draw the Tokarev and fire first.")
	if not my_turn:
		return
	if stats["ap"] < SHOT_AP:
		hud.log_msg("Not enough action points (%d needed). End your turn." % SHOT_AP, Hud.DIM)
		return
	busy = true
	stats["ap"] -= SHOT_AP
	refresh()
	await shoot(w, 0)
	busy = false
	_check_combat_over()
	refresh()


func shoot(w: Actor, penalty: int) -> void:
	var target := w.aim_point("body")
	# the gun goes onto the target's height and stays there between shots: raise from the stance,
	# or swing from whatever you were aiming at before
	await player.aim_at(target)
	aim_target = w
	var clip := player.fire_held()
	if "--autotest" in OS.get_cmdline_user_args():
		print("shot: ", clip, " at ", Hex.distance(player.hex, w.hex), " hexes, target height ", snappedf(target.z, 0.01))
	await player.action_point
	var chance := hit_chance(player.hex, w.hex) - penalty
	var hit := rng.randi_range(1, 100) <= chance
	_tracer(player.position + player.muzzle_offset(clip), Actor.aim_to_screen(target), hit)
	if hit:
		damage(w, rng.randi_range(5, 9))
	else:
		_float(w.position + Vector2(0, -60), "MISS", Hud.DIM)
	await player.anim_done
	if not player.alive:
		return
	if not w.alive or mode != "combat":
		aim_target = null
		await player.lower_aim()                  # target down: lower the gun
	else:
		player.play("pistol_hold", player.dir)    # keep it on the target


func damage(a: Actor, dmg: int) -> void:
	if a == player:
		stats["hp"] = maxi(0, stats["hp"] - dmg)
		_float(a.position + Vector2(0, -300), "-%d" % dmg, Hud.RED)
		a.flash(Color(1.0, 0.45, 0.4))
		if stats["hp"] <= 0:
			player.alive = false
			player.play("death", player.dir)
			hud.log_msg("The worm's teeth find your throat.", Hud.RED)
			hud.show_death()
		else:
			_react(a)
		refresh()
		return
	a.hp -= dmg
	_float(a.position + Vector2(0, -70), "-%d" % dmg, Color(1.0, 0.85, 0.4))
	a.flash(Color(1.0, 0.5, 0.45))
	if a.hp <= 0:
		a.alive = false
		a.ring_color = Color(0, 0, 0, 0)
		state["L3"]["dead"].append(a.get_meta("index"))
		hud.log_msg("The worm thrashes and goes limp.", Hud.GREEN)
	_wound_anim(a)


func _wound_anim(a: Actor) -> void:
	await _wait_unlatched(a)                # a worm still letting go of the pipe finishes that first
	if a.alive:
		_react(a)
	else:
		a.play("death", a.dir)


func _react(a: Actor) -> void:
	a.play("hit", a.dir)
	await a.anim_done
	if a.alive and a.anim == "hit":
		a.play(a.idle_clip(mode == "combat"), a.dir)


func _check_combat_over() -> void:
	if mode == "combat" and live_worms().is_empty():
		end_combat()


func set_overwatch() -> void:
	if mode != "combat" or not my_turn or busy:
		hud.log_msg("Overwatch only works in combat, on your turn.", Hud.DIM)
		return
	if stats["ap"] < SHOT_AP:
		hud.log_msg("Overwatch needs at least %d action points." % SHOT_AP, Hud.DIM)
		return
	overwatch = stats["ap"] / SHOT_AP
	stats["ap"] = 0
	player.play("pistol_idle", player.dir)
	hud.log_msg("Overwatch: %d shot%s ready for anything that moves." % [overwatch, "" if overwatch == 1 else "s"], Color(0.85, 0.75, 0.45))
	end_turn()


func use_medkit() -> void:
	if stats["medkits"] <= 0:
		hud.log_msg("No medkits left.", Hud.DIM)
		return
	if stats["hp"] >= stats["hp_max"]:
		hud.log_msg("You're not hurt.", Hud.DIM)
		return
	if mode == "combat":
		if not my_turn:
			return
		if stats["ap"] < MED_AP:
			hud.log_msg("Not enough action points.", Hud.DIM)
			return
		stats["ap"] -= MED_AP
	stats["medkits"] -= 1
	var healed := mini(12, stats["hp_max"] - stats["hp"])
	stats["hp"] += healed
	_float(player.position + Vector2(0, -300), "+%d" % healed, Hud.GREEN)
	hud.log_msg("You patch yourself up. (+%d HP)" % healed, Hud.GREEN)
	refresh()


func end_turn() -> void:
	if mode != "combat" or not my_turn or busy or not player.alive:
		return
	my_turn = false
	action = ""
	refresh()
	await enemy_phase()
	if not player.alive:
		return
	if live_worms().is_empty():
		end_combat()
		return
	my_turn = true
	stats["ap"] = AP_MAX
	if overwatch > 0:
		overwatch = 0
	focus = player
	hud.log_msg("Your turn: %d action points." % AP_MAX, Hud.DIM)
	refresh()


func enemy_phase() -> void:
	var order := live_worms()
	order.sort_custom(func(a, b): return Hex.distance(a.hex, player.hex) < Hex.distance(b.hex, player.hex))
	for w in order:
		if not player.alive:
			return
		if w.alive:
			focus = w
			await worm_turn(w)
			await get_tree().create_timer(0.25).timeout


func worm_turn(w: Actor) -> void:
	await _wait_unlatched(w)
	w.ap = WORM_AP
	var guard := 0
	while w.alive and player.alive and w.ap > 0 and guard < 8:
		guard += 1
		if Hex.distance(w.hex, player.hex) == 1:
			if w.ap >= 3:
				await bite(w)
				w.ap -= 3
				continue
			break
		var path := _path_to_player(w)
		if path.is_empty():
			break
		path = path.slice(0, w.ap)
		w.follow(path)
		await w.arrived
		if pending_overwatch == w:
			pending_overwatch = null
			await overwatch_shot(w)
	if w.alive:
		w.play("idle", w.dir)


func _path_to_player(w: Actor) -> Array:
	var occ := occupied(w)
	var best: Array = []
	for d in Hex.DIRS:
		var n: Vector2i = player.hex + d
		if not level.walkable.has(n) or n in occ:
			continue
		var p := level.find_path(w.hex, n, occ)
		if not p.is_empty() and (best.is_empty() or p.size() < best.size()):
			best = p
	return best


func _on_worm_step(h: Vector2i, w: Actor) -> void:
	if mode != "combat":
		return
	w.ap -= 1
	if overwatch > 0 and Hex.distance(player.hex, h) <= RANGE and level.line_of_sight(player.hex, h):
		w.stop_now()
		pending_overwatch = w


func overwatch_shot(w: Actor) -> void:
	overwatch -= 1
	hud.log_msg("Overwatch! You fire as it moves.", Color(0.85, 0.75, 0.45))
	await shoot(w, 10)
	refresh()


func bite(w: Actor) -> void:
	w.face_ground(player.ground)
	w.play("bite", w.dir)
	await w.action_point
	if rng.randi_range(1, 100) <= 70:
		var dmg := rng.randi_range(3, 6)
		hud.log_msg("A worm bites you for %d." % dmg, Hud.RED)
		damage(player, dmg)
	else:
		_float(player.position + Vector2(0, -300), "MISS", Hud.DIM)
	await w.anim_done
	if w.alive:
		w.play("idle", w.dir)


# ================================================================== effects
func _float(at: Vector2, t: String, c: Color) -> void:
	var l := Label.new()
	l.text = t
	l.add_theme_font_size_override("font_size", 42)
	l.add_theme_color_override("font_color", c)
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	l.add_theme_constant_override("outline_size", 8)
	l.position = at - Vector2(40, 0)
	l.z_index = 100
	level.add_child(l)
	var tw := create_tween()
	tw.tween_property(l, "position:y", at.y - 90, 1.0)
	tw.parallel().tween_property(l, "modulate:a", 0.0, 1.0).set_delay(0.4)
	tw.tween_callback(l.queue_free)


func _tracer(muzzle: Vector2, aimp: Vector2, hit: bool) -> void:
	var hitp := aimp
	if not hit:                                   # a miss goes wide and carries on past the target
		var along := (aimp - muzzle).normalized()
		var side := Vector2(-along.y, along.x) * rng.randf_range(18.0, 40.0) * (1.0 if rng.randf() < 0.5 else -1.0)
		hitp = aimp + side + along * 140.0
	var line := Line2D.new()
	line.points = PackedVector2Array([muzzle, hitp])
	line.width = 4.0
	line.default_color = Color(1.0, 0.9, 0.55, 0.9)
	line.z_index = 90
	level.add_child(line)
	var flash := Polygon2D.new()
	var pts := PackedVector2Array()
	for k in 10:
		var a := TAU * k / 10.0
		pts.append(muzzle + Vector2(cos(a), sin(a)) * (22.0 if k % 2 == 0 else 9.0))
	flash.polygon = pts
	flash.color = Color(1.0, 0.85, 0.4)
	flash.z_index = 91
	level.add_child(flash)
	var tw := create_tween()
	tw.tween_property(line, "modulate:a", 0.0, 0.15)
	tw.parallel().tween_property(flash, "modulate:a", 0.0, 0.1)
	tw.tween_callback(line.queue_free)
	tw.tween_callback(flash.queue_free)


func _sparks(at: Vector2) -> CPUParticles2D:
	var p := CPUParticles2D.new()
	p.position = at
	p.amount = 60
	p.lifetime = 0.6
	p.direction = Vector2(0, -1)
	p.spread = 80.0
	p.initial_velocity_min = 120.0
	p.initial_velocity_max = 260.0
	p.gravity = Vector2(0, 600)
	p.scale_amount_min = 2.0
	p.scale_amount_max = 4.0
	var cr := Gradient.new()
	cr.set_color(0, Color(1.0, 0.95, 0.6)); cr.set_color(1, Color(1.0, 0.45, 0.1, 0.0))
	p.color_ramp = cr
	p.z_index = 95
	level.add_child(p)
	p.emitting = true
	get_tree().create_timer(2.5).timeout.connect(p.queue_free)
	return p


# ================================================================== HUD state
func objectives() -> Array:
	var o: Array = []
	if flags["quest"] == "none":
		return [{"text": "Hear Tibor out", "done": false}]
	o.append({"text": "Take the welding kit from your toolbox", "done": stats["kit"]})
	o.append({"text": "Go down to Level 3", "done": flags["visited_L3"]})
	if flags["visited_L3"]:
		o.append({"text": "Find where the pressure is going", "done": flags["found_leak"]})
	if flags["seen_worms"]:
		o.append({"text": "Deal with the pipe worms", "done": state["L3"]["dead"].size() >= 3})
	if flags["found_leak"]:
		o.append({"text": "Weld the burst pipe", "done": state["L3"]["pipe_fixed"]})
	if state["L3"]["pipe_fixed"]:
		o.append({"text": "Report back to Tibor on Level 2", "done": flags["quest"] == "done"})
	if flags["door_seen"]:
		o.append({"text": "Optional: get into Room 2-D", "done": state["L2"].get("door_door_2_d", false)})
	return o


func refresh() -> void:
	var combat := mode == "combat"
	var mt := "EXPLORING"
	if combat:
		mt = "YOUR TURN" if my_turn else "WORMS' TURN"
	if not combat:
		stats["ap"] = AP_MAX
	hud.set_stats(stats["hp"], stats["hp_max"], stats["ap"], AP_MAX, mt, combat, my_turn)
	hud.set_slots([
		{"kind": "attack", "title": "TOKAREV", "cost": "%d AP" % SHOT_AP, "selected": action == "attack"},
		{"kind": "overwatch", "title": "OVERWATCH", "cost": "ALL AP", "enabled": combat and my_turn and stats["ap"] >= SHOT_AP},
		{"kind": "inspect", "title": "INSPECT", "selected": action == "inspect"},
		{"kind": "weld", "title": "WELD KIT", "cost": "%d AP" % WELD_AP, "enabled": stats["kit"], "selected": action == "weld",
		 "pulse": _weld_time()},
		{"kind": "medkit", "title": "MEDKIT", "cost": "%d AP" % MED_AP, "enabled": stats["medkits"] > 0, "count": stats["medkits"]},
	])
	var head: String = ("MAINTENANCE CALL %s" % CALL_NO) if flags["quest"] != "none" else (str(level.data["name"]) if level else "")
	if flags["quest"] == "done":
		head = "CALL %s - CLOSED" % CALL_NO
	hud.set_objectives(head, objectives())
	if marks:
		marks.queue_redraw()
	_update_beacon()


# ================================================================== quest guidance
# A beacon (a bobbing chevron over the thing, a ring on the floor, the thing itself glowing) shows
# where the current objective is; the weld kit slot breathes when it's time to weld.
var beacon: Beacon = null
var beacon_sprite: CanvasItem = null


func _weld_time() -> bool:
	return level != null and level_id == "L3" and stats["kit"] and mode != "combat" \
		and not state["L3"]["pipe_fixed"] and flags["found_leak"]


func _objective_target() -> Dictionary:
	# returns {pos (screen), sprite (CanvasItem or null), floor (screen point for the ring)}
	if level == null:
		return {}
	if level_id == "L2" and not stats["kit"]:
		for p in level.props:
			if p["data"].get("id", "") == "toolbox":
				var fp: Array = p["data"]["footprint"]
				var c := Vector2((fp[0] + fp[1]) / 2.0, (fp[2] + fp[3]) / 2.0)
				return {"pos": Hex.plan_to_screen(c, 0.75), "floor": Hex.plan_to_screen(c, 0.0), "sprite": p["sprite"]}
	if flags["quest"] == "none":
		return {}
	if state["L3"]["pipe_fixed"] and flags["quest"] != "done":
		if level_id == "L2" and tibor:
			return {"pos": tibor.position + Vector2(0, -250), "floor": tibor.position, "sprite": tibor.sprite}
		if level_id == "L3":
			for st in level.data["stairs"]:
				if st["to"] == "L2":
					var cs := Vector2(st["u"], st["v"])
					return {"pos": Hex.plan_to_screen(cs, 1.0), "floor": Hex.plan_to_screen(cs, 0.0), "sprite": null}
		return {}
	if level_id == "L2" and stats["kit"] and not state["L3"]["pipe_fixed"]:
		for st in level.data["stairs"]:
			if st["to"] == "L3":
				var c2 := Vector2(st["u"], st["v"])
				return {"pos": Hex.plan_to_screen(c2, 1.0), "floor": Hex.plan_to_screen(c2, 0.0), "sprite": null}
	if level_id == "L3" and not stats["kit"]:
		for st in level.data["stairs"]:
			if st["to"] == "L2":
				var c3 := Vector2(st["u"], st["v"])
				return {"pos": Hex.plan_to_screen(c3, 1.0), "floor": Hex.plan_to_screen(c3, 0.0), "sprite": null}
	if _weld_time():
		var pc := Vector2(level.pipe["u"], level.pipe["v"] - 0.34)
		return {"pos": Hex.plan_to_screen(pc, 0.95), "floor": Hex.plan_to_screen(Vector2(level.pipe["u"], level.pipe["v"] - 0.7), 0.0),
				"sprite": level.pipe_node}
	return {}


func _update_beacon() -> void:
	var t := _objective_target()
	if beacon_sprite and is_instance_valid(beacon_sprite):
		beacon_sprite.self_modulate = Color.WHITE
	beacon_sprite = null
	if t.is_empty() or mode == "combat":
		if beacon and is_instance_valid(beacon):
			beacon.visible = false
		return
	if beacon == null or not is_instance_valid(beacon) or beacon.get_parent() != level:
		beacon = Beacon.new()
		level.add_child(beacon)
	beacon.visible = true
	if _weld_time() and not flags.get("weld_hint", false):
		flags["weld_hint"] = true
		hud.log_msg("Now weld it: pick the WELD KIT (4), then click the burst pipe.", Color(1.0, 0.8, 0.4))
	beacon.top = t["pos"]; beacon.floor_pt = t["floor"]
	beacon.z_index = 60
	beacon_sprite = t["sprite"]
	beacon.glow = beacon_sprite


class Beacon extends Node2D:
	var top := Vector2.ZERO
	var floor_pt := Vector2.ZERO
	var glow: CanvasItem = null

	func _process(_dt: float) -> void:
		queue_redraw()
		if glow and is_instance_valid(glow):
			var a := 0.5 + 0.5 * sin(Time.get_ticks_msec() * 0.005)
			glow.self_modulate = Color(1.0 + 0.45 * a, 1.0 + 0.35 * a, 1.0 + 0.1 * a)

	func _draw() -> void:
		var ms := Time.get_ticks_msec()
		var bob := sin(ms * 0.005) * 7.0
		var a := 0.5 + 0.5 * sin(ms * 0.005)
		var amber := Color(1.0, 0.76, 0.28)
		# ring on the floor, flat (2:1)
		draw_set_transform(floor_pt, 0.0, Vector2(1.0, 0.5))
		draw_arc(Vector2.ZERO, 34.0 + 6.0 * a, 0.0, TAU, 48, Color(amber, 0.35 + 0.35 * a), 3.0, true)
		draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
		# chevron above, pointing down, with a dark edge so it reads on any background
		var p := top + Vector2(0, -46 + bob)
		var pts := PackedVector2Array([p + Vector2(-16, -14), p + Vector2(0, 2), p + Vector2(16, -14), p + Vector2(16, -6), p + Vector2(0, 10), p + Vector2(-16, -6)])
		draw_colored_polygon(pts, amber)
		var ol := pts.duplicate(); ol.append(pts[0])
		draw_polyline(ol, Color(0.1, 0.07, 0.03, 0.9), 2.0, true)


func _process(delta: float) -> void:
	if focus and is_instance_valid(focus):
		cam.position = focus.position + Vector2(0, -80)
	if level and player:
		var foci: Array = []
		var feet := player.global_position - level.global_position
		foci.append({"y": feet.y, "rect": Rect2(feet + Vector2(-50, -270), Vector2(100, 280))})
		if not hud.over_ui(get_viewport().get_mouse_position()):
			var m := get_global_mouse_position() - level.global_position
			foci.append({"y": m.y, "rect": Rect2(m + Vector2(-45, -150), Vector2(90, 165))})
		for w in worms:
			if w.alive:
				var wf: Vector2 = w.global_position - level.global_position
				foci.append({"y": wf.y, "rect": Rect2(wf + Vector2(-50, -90), Vector2(100, 100))})
		level.fade_walls(foci, delta)


# ================================================================== hex highlights
class Marks extends Node2D:
	var game

	func _draw() -> void:
		if game == null or game.level == null:
			return
		var lv: Level = game.level
		var combat: bool = game.mode == "combat"
		if combat and game.my_turn:
			for w in game.worms:
				if w.alive:
					draw_colored_polygon(Hex.hex_polygon(w.hex), Color(0.8, 0.2, 0.15, 0.22))
		var p: Array = game.path_preview
		for i in p.size():
			var ok: bool = (not combat) or i < game.stats["ap"]
			var c := Color(0.55, 0.85, 0.45, 0.45) if ok else Color(0.85, 0.3, 0.25, 0.4)
			draw_colored_polygon(Hex.hex_polygon(p[i], 0.5), c)
		var h: Vector2i = game.hover_hex
		if lv.walkable.has(h):
			var c2 := Color(0.95, 0.88, 0.6, 0.9)
			if game.action == "attack":
				c2 = Color(0.95, 0.35, 0.3, 0.9)
			var poly := Hex.hex_polygon(h)
			poly.append(poly[0])
			draw_polyline(poly, c2, 2.5, true)


# ================================================================== automated playthrough for testing
func autotest() -> void:
	await get_tree().create_timer(0.5).timeout
	print("AUTOTEST start at ", player.hex)
	var tb := {}
	for p in level.props:
		if p["data"].get("id", "") == "toolbox":
			var fp: Array = p["data"]["footprint"]
			tb = {"kind": "toolbox", "id": "toolbox", "name": "Your toolbox", "text": p["data"]["text"],
				  "plan": Vector2((fp[0] + fp[1]) / 2.0, (fp[2] + fp[3]) / 2.0), "footprint": fp}
	await interact(tb)
	print("toolbox dialog open: ", hud.dialog_open())
	_on_dialog_choice(0)
	print("kit: ", stats["kit"])
	var d: Dictionary = level.doors["door_2_d"]["data"]
	await interact({"kind": "door", "id": "door_2_d", "name": d["name"], "text": d["text"], "plan": Vector2(d["u"], d["v"])})
	print("door dialog open: ", hud.dialog_open())
	_on_dialog_choice(1)
	print("door open: ", level.doors["door_2_d"]["open"], "  dark left: ", level.is_dark("room_2_d"))
	var s: Dictionary = level.data["stairs"][0]
	await interact({"kind": "stairs", "id": s["id"], "name": s["name"], "text": s["text"], "plan": Vector2(s["u"], s["v"]), "to": s["to"], "arrive": s["arrive"]})
	print("now on ", level_id, " at ", player.hex, " worms ", worms.size())
	await get_tree().create_timer(0.5).timeout
	await move_to(level.nearest_walkable(Vector2(4.5, 0.0)))
	print("mode after approach: ", mode, " hp ", stats["hp"])
	var rounds := 0
	while mode == "combat" and player.alive and rounds < 12:
		rounds += 1
		while stats["ap"] >= SHOT_AP * (2 if rounds == 1 else 1) and not live_worms().is_empty():
			var tgt: Actor = null
			for w in live_worms():
				if level.line_of_sight(player.hex, w.hex) and (tgt == null or Hex.distance(w.hex, player.hex) < Hex.distance(tgt.hex, player.hex)):
					tgt = w
			if tgt == null:
				break
			await attack(tgt)
		if mode == "combat":
			if rounds == 1 and stats["ap"] >= SHOT_AP:
				set_overwatch()
			else:
				await end_turn()
			while busy or not my_turn:
				await get_tree().process_frame
				if not player.alive:
					break
		print("round ", rounds, " hp ", stats["hp"], " worms left ", live_worms().size())
	print("combat over: ", mode, " alive ", player.alive)
	if player.alive:
		await interact({"kind": "pipe", "id": "pipe_break", "name": level.pipe["name"], "text": level.pipe["text"],
			"plan": Vector2(level.pipe["u"], level.pipe["v"] - 0.6)})
		print("pipe dialog: ", hud.dialog_open())
		_on_dialog_choice(0)
		await get_tree().create_timer(2.0).timeout
	print("pipe fixed: ", state["L3"]["pipe_fixed"])
	if state["L3"]["pipe_fixed"]:                    # back up to report to Tibor
		var up: Dictionary = level.data["stairs"][0]
		for st in level.data["stairs"]:
			if st["to"] == "L2":
				up = st
		await interact({"kind": "stairs", "id": up["id"], "name": up["name"], "text": up["text"], "plan": Vector2(up["u"], up["v"]), "to": up["to"], "arrive": up["arrive"]})
		await get_tree().create_timer(0.5).timeout
		print("back on ", level_id, " tibor ", tibor != null)
		if tibor:
			await talk_tibor()
			print("talking: ", hud.dialog_open(), " node ", _talk_node)
			_on_dialog_choice(0)
			await get_tree().create_timer(0.3).timeout
		print("quest: ", flags["quest"], " medkits ", stats["medkits"])
	for o in objectives():
		print("  ", "[x] " if o["done"] else "[ ] ", o["text"])
	print("AUTOTEST end")
	get_tree().quit()


## Walks from your room through the passage to the commons wing, into every room, and back.
func test_commons() -> void:
	await get_tree().create_timer(0.3).timeout
	var p: Dictionary = level.data["stairs"][1]
	await interact({"kind": "stairs", "id": p["id"], "name": p["name"], "text": p["text"], "plan": Vector2(p["u"], p["v"]), "to": p["to"], "arrive": p["arrive"]})
	print("now on ", level_id, " at ", player.hex, " walkable ", level.walkable.size())
	for room in ["commons", "kitchen", "classroom", "waiting", "clinic", "wash_w", "archive"]:
		var r: Array = []
		for rr in level.data["rooms"]:
			if rr["id"] == room:
				r = rr["r"]
		var target := level.nearest_walkable(Vector2((r[0] + r[1]) / 2.0, (r[2] + r[3]) / 2.0), 3.0)
		if room == "archive":
			var d: Dictionary = level.doors["door_archive"]["data"]
			await interact({"kind": "door", "id": "door_archive", "name": d["name"], "text": d["text"], "plan": Vector2(d["u"], d["v"])})
		var path := level.find_path(player.hex, target, [])
		print(room, ": target ", target, " path ", path.size())
		if not path.is_empty():
			await walk(path)
		print("  reached ", player.hex == target, "  in room ", level._in_room(Hex.hex_to_plan(player.hex)))
	var back: Dictionary = level.data["stairs"][0]
	await interact({"kind": "stairs", "id": back["id"], "name": back["name"], "text": back["text"], "plan": Vector2(back["u"], back["v"]), "to": back["to"], "arrive": back["arrive"]})
	print("back on ", level_id, " at ", player.hex)
	print("TEST END")
	get_tree().quit()


## Goes down from Level 3 to Level 4 and walks into every room of the command wing.
func test_command() -> void:
	await get_tree().create_timer(0.3).timeout
	load_level("L3", Vector2(-0.3, 0.0))
	await get_tree().create_timer(0.3).timeout
	for w in worms:
		w.alive = false                     # this test is about rooms, not worms
	var down: Dictionary = level.data["stairs"][1]
	await interact({"kind": "stairs", "id": down["id"], "name": down["name"], "text": down["text"], "plan": Vector2(down["u"], down["v"]), "to": down["to"], "arrive": down["arrive"]})
	print("now on ", level_id, " at ", player.hex, " walkable ", level.walkable.size())
	var doors_for := {"duty1": "door_d1", "duty2": "door_d2", "duty3": "door_d3", "varga": "door_varga"}
	for room in ["valves", "engineering", "council", "radio", "duty1", "duty2", "duty3", "varga"]:
		var r: Array = []
		for rr in level.data["rooms"]:
			if rr["id"] == room:
				r = rr["r"]
		if doors_for.has(room):
			var did: String = doors_for[room]
			if room == "varga":
				level.doors[did]["locked"] = false      # skip the lockpick roll in the test
			var d: Dictionary = level.doors[did]["data"]
			await interact({"kind": "door", "id": did, "name": d["name"], "text": d["text"], "plan": Vector2(d["u"], d["v"])})
		var target := level.nearest_walkable(Vector2((r[0] + r[1]) / 2.0, (r[2] + r[3]) / 2.0), 3.0)
		var path := level.find_path(player.hex, target, [])
		print(room, ": target ", target, " path ", path.size())
		if not path.is_empty():
			await walk(path)
		print("  reached ", player.hex == target, "  in room ", level._in_room(Hex.hex_to_plan(player.hex)))
	var up: Dictionary = level.data["stairs"][0]
	await interact({"kind": "stairs", "id": up["id"], "name": up["name"], "text": up["text"], "plan": Vector2(up["u"], up["v"]), "to": up["to"], "arrive": up["arrive"]})
	print("back on ", level_id, " at ", player.hex)
	print("TEST END")
	get_tree().quit()
