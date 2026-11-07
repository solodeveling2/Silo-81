class_name Hud
extends CanvasLayer
## Wasteland 3-style bottom bar: portrait, health and action points, five action slots on 1-5,
## End Turn. Plus the message log, objectives, tooltips, dialogs and banners.

signal slot_pressed(index: int)
signal end_turn_pressed
signal dialog_choice(index: int)
signal restart_pressed

const INK := Color(0.9, 0.86, 0.72)
const DIM := Color(0.62, 0.6, 0.52)
const BRASS := Color(0.62, 0.52, 0.3)
const PANEL := Color(0.07, 0.07, 0.065, 0.93)
const RED := Color(0.78, 0.22, 0.16)
const GREEN := Color(0.45, 0.68, 0.38)

var stencil: FontFile
var body_font: FontFile
var bar: Control
var hp_bar: ProgressBar
var hp_label: Label
var ap_box: HBoxContainer
var ap_label: Label
var mode_label: Label
var end_btn: Button
var slots: Array = []
var log_box: VBoxContainer
var obj_box: VBoxContainer
var tooltip: Label
var dialog: PanelContainer
var banner: Label
var death: Control


func _ready() -> void:
	stencil = load("res://fonts/AllertaStencil-Regular.ttf")
	body_font = load("res://fonts/Oswald-VF.ttf")
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	_build_bar(root)
	_build_log(root)
	_build_objectives(root)
	tooltip = _label("", 15, INK)
	tooltip.add_theme_stylebox_override("normal", _box(Color(0.05, 0.05, 0.045, 0.9), BRASS, 1, 6))
	tooltip.visible = false
	tooltip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(tooltip)
	banner = _label("", 30, INK, stencil)
	banner.set_anchors_preset(Control.PRESET_CENTER_TOP)
	banner.position = Vector2(-300, 70)
	banner.size = Vector2(600, 50)
	banner.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	banner.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.8))
	banner.add_theme_constant_override("shadow_offset_x", 2)
	banner.add_theme_constant_override("shadow_offset_y", 2)
	banner.modulate.a = 0.0
	banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(banner)
	_build_dialog(root)
	_build_death(root)


func _box(bg: Color, border: Color, bw: int = 2, r: int = 4) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.border_color = border
	sb.set_border_width_all(bw)
	sb.set_corner_radius_all(r)
	sb.content_margin_left = 10; sb.content_margin_right = 10
	sb.content_margin_top = 6; sb.content_margin_bottom = 6
	return sb


func _label(t: String, size: int, c: Color, font: Font = null) -> Label:
	var l := Label.new()
	l.text = t
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", c)
	l.add_theme_font_override("font", font if font else body_font)
	return l


func _button(t: String, size: int = 16) -> Button:
	var b := Button.new()
	b.text = t
	b.add_theme_font_override("font", stencil)
	b.add_theme_font_size_override("font_size", size)
	b.add_theme_color_override("font_color", INK)
	b.add_theme_color_override("font_hover_color", Color(1, 0.95, 0.75))
	b.add_theme_color_override("font_disabled_color", Color(0.45, 0.43, 0.38))
	b.add_theme_stylebox_override("normal", _box(Color(0.14, 0.13, 0.11), BRASS))
	b.add_theme_stylebox_override("hover", _box(Color(0.22, 0.2, 0.15), Color(0.85, 0.72, 0.4)))
	b.add_theme_stylebox_override("pressed", _box(Color(0.3, 0.25, 0.15), Color(0.95, 0.8, 0.45)))
	b.add_theme_stylebox_override("disabled", _box(Color(0.1, 0.1, 0.09), Color(0.3, 0.28, 0.22)))
	b.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	return b


# ------------------------------------------------------------------ bottom bar
func _build_bar(root: Control) -> void:
	bar = PanelContainer.new()
	bar.add_theme_stylebox_override("panel", _box(PANEL, BRASS, 2, 6))
	bar.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	bar.custom_minimum_size = Vector2(900, 118)
	bar.position = Vector2(-450, -128)
	bar.size = Vector2(900, 118)
	root.add_child(bar)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 14)
	bar.add_child(row)

	# portrait, health, action points
	var left := HBoxContainer.new()
	left.add_theme_constant_override("separation", 10)
	row.add_child(left)
	var portrait := Portrait.new()
	portrait.custom_minimum_size = Vector2(84, 96)
	left.add_child(portrait)
	var stats := VBoxContainer.new()
	stats.custom_minimum_size = Vector2(200, 0)
	stats.add_theme_constant_override("separation", 4)
	left.add_child(stats)
	stats.add_child(_label("CHIEF ENGINEER", 17, INK, stencil))
	hp_bar = ProgressBar.new()
	hp_bar.custom_minimum_size = Vector2(190, 16)
	hp_bar.show_percentage = false
	var fill := StyleBoxFlat.new(); fill.bg_color = RED
	var back := StyleBoxFlat.new(); back.bg_color = Color(0.18, 0.06, 0.05)
	hp_bar.add_theme_stylebox_override("fill", fill)
	hp_bar.add_theme_stylebox_override("background", back)
	stats.add_child(hp_bar)
	hp_label = _label("HP", 14, DIM)
	stats.add_child(hp_label)
	ap_box = HBoxContainer.new()
	ap_box.add_theme_constant_override("separation", 3)
	stats.add_child(ap_box)
	ap_label = _label("", 14, DIM)
	stats.add_child(ap_label)

	# action slots
	var slot_row := HBoxContainer.new()
	slot_row.add_theme_constant_override("separation", 8)
	row.add_child(slot_row)
	for i in 5:
		var s := Slot.new()
		s.index = i
		s.custom_minimum_size = Vector2(78, 96)
		s.pressed.connect(func(idx: int) -> void: slot_pressed.emit(idx))
		s.label_font = stencil
		slot_row.add_child(s)
		slots.append(s)

	# end turn and mode
	var right := VBoxContainer.new()
	right.alignment = BoxContainer.ALIGNMENT_CENTER
	right.add_theme_constant_override("separation", 6)
	row.add_child(right)
	mode_label = _label("EXPLORING", 15, DIM, stencil)
	mode_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	mode_label.custom_minimum_size = Vector2(150, 0)
	right.add_child(mode_label)
	end_btn = _button("END TURN", 18)
	end_btn.custom_minimum_size = Vector2(150, 52)
	end_btn.pressed.connect(func() -> void: end_turn_pressed.emit())
	right.add_child(end_btn)
	var hint := _label("[Space]", 12, DIM)
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	right.add_child(hint)


func set_stats(hp: int, hp_max: int, ap: int, ap_max: int, mode_text: String, combat: bool, my_turn: bool) -> void:
	hp_bar.max_value = hp_max
	hp_bar.value = hp
	hp_label.text = "HEALTH %d / %d" % [hp, hp_max]
	for c in ap_box.get_children():
		c.queue_free()
	for i in ap_max:
		var pip := ColorRect.new()
		pip.custom_minimum_size = Vector2(19, 11)
		pip.color = Color(0.85, 0.72, 0.3) if (i < ap and combat) else Color(0.22, 0.2, 0.15)
		ap_box.add_child(pip)
	ap_label.text = ("ACTION POINTS %d / %d" % [ap, ap_max]) if combat else "ACTION POINTS (combat only)"
	mode_label.text = mode_text
	end_btn.disabled = not (combat and my_turn)


func set_slots(states: Array) -> void:
	for i in slots.size():
		slots[i].apply(states[i])


# ------------------------------------------------------------------ log and objectives
func _build_log(root: Control) -> void:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", _box(Color(0.05, 0.05, 0.045, 0.72), Color(0.3, 0.27, 0.2), 1, 4))
	panel.anchor_left = 0.0; panel.anchor_right = 0.0; panel.anchor_top = 1.0; panel.anchor_bottom = 1.0
	panel.grow_vertical = Control.GROW_DIRECTION_BEGIN          # new lines push the log upwards
	panel.offset_left = 14; panel.offset_right = 444
	panel.offset_bottom = -142; panel.offset_top = -142
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(panel)
	log_box = VBoxContainer.new()
	log_box.alignment = BoxContainer.ALIGNMENT_END
	log_box.add_theme_constant_override("separation", 2)
	log_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(log_box)


func log_msg(t: String, c: Color = INK) -> void:
	var l := _label(t, 14, c)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.custom_minimum_size = Vector2(410, 0)
	log_box.add_child(l)
	while log_box.get_child_count() > 6:
		log_box.get_child(0).free()
	print("[log] ", t)


func _build_objectives(root: Control) -> void:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", _box(Color(0.05, 0.05, 0.045, 0.78), Color(0.3, 0.27, 0.2), 1, 4))
	panel.position = Vector2(14, 14)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(panel)
	obj_box = VBoxContainer.new()
	obj_box.add_theme_constant_override("separation", 3)
	panel.add_child(obj_box)


func set_objectives(level_name: String, items: Array) -> void:
	for c in obj_box.get_children():
		c.free()
	obj_box.add_child(_label(level_name.to_upper(), 15, BRASS, stencil))
	for it in items:
		var done: bool = it["done"]
		var l := _label(("[x] " if done else "[ ] ") + it["text"], 14, DIM if done else INK)
		obj_box.add_child(l)


# ------------------------------------------------------------------ tooltip, banner
func show_tooltip(t: String, at: Vector2) -> void:
	if t == "":
		tooltip.visible = false
		return
	tooltip.text = t
	tooltip.visible = true
	tooltip.reset_size()
	tooltip.position = at + Vector2(18, 14)


func show_banner(t: String) -> void:
	banner.text = t
	var tw := create_tween()
	tw.tween_property(banner, "modulate:a", 1.0, 0.3)
	tw.tween_interval(1.6)
	tw.tween_property(banner, "modulate:a", 0.0, 0.6)


# ------------------------------------------------------------------ dialog
var _dialog_title: Label
var _dialog_text: Label
var _dialog_buttons: VBoxContainer


func _build_dialog(root: Control) -> void:
	dialog = PanelContainer.new()
	dialog.add_theme_stylebox_override("panel", _box(Color(0.08, 0.075, 0.065, 0.97), BRASS, 2, 6))
	dialog.set_anchors_preset(Control.PRESET_CENTER)
	dialog.custom_minimum_size = Vector2(520, 0)
	dialog.position = Vector2(-260, -200)
	dialog.visible = false
	root.add_child(dialog)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 10)
	dialog.add_child(col)
	_dialog_title = _label("", 22, INK, stencil)
	col.add_child(_dialog_title)
	_dialog_text = _label("", 16, DIM)
	_dialog_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_dialog_text.custom_minimum_size = Vector2(490, 0)
	col.add_child(_dialog_text)
	_dialog_buttons = VBoxContainer.new()
	_dialog_buttons.add_theme_constant_override("separation", 6)
	col.add_child(_dialog_buttons)


func open_dialog(title: String, text: String, options: Array) -> void:
	_dialog_title.text = title
	_dialog_text.text = text
	for c in _dialog_buttons.get_children():
		c.free()
	for i in options.size():
		var o: Dictionary = options[i]
		var b := _button("%d. %s" % [i + 1, o["label"]], 16)
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.disabled = not o.get("enabled", true)
		b.pressed.connect(func() -> void: dialog_choice.emit(i))
		_dialog_buttons.add_child(b)
	dialog.visible = true
	dialog.reset_size()
	dialog.position = Vector2(-dialog.size.x / 2, -dialog.size.y / 2 - 60)


func close_dialog() -> void:
	dialog.visible = false


func dialog_open() -> bool:
	return dialog.visible


# ------------------------------------------------------------------ death
func _build_death(root: Control) -> void:
	death = ColorRect.new()
	death.color = Color(0.05, 0.0, 0.0, 0.0)
	death.set_anchors_preset(Control.PRESET_FULL_RECT)
	death.visible = false
	root.add_child(death)
	var col := VBoxContainer.new()
	col.set_anchors_preset(Control.PRESET_CENTER)
	col.position = Vector2(-160, -60)
	col.custom_minimum_size = Vector2(320, 0)
	death.add_child(col)
	var t := _label("YOU DIED", 44, Color(0.85, 0.3, 0.22), stencil)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(t)
	var b := _button("TRY AGAIN", 20)
	b.pressed.connect(func() -> void: restart_pressed.emit())
	col.add_child(b)


func show_death() -> void:
	death.visible = true
	var tw := create_tween()
	tw.tween_property(death, "color:a", 0.75, 1.5)


func over_ui(p: Vector2) -> bool:
	if bar.get_global_rect().has_point(p):
		return true
	if dialog.visible and dialog.get_global_rect().has_point(p):
		return true
	return death.visible


# ================================================================== slot widget
class Slot extends Control:
	signal pressed(index: int)
	var index := 0
	var kind := "attack"
	var title := ""
	var cost := ""
	var enabled := true
	var selected := false
	var count := -1
	var label_font: Font
	var hover := false

	func _ready() -> void:
		mouse_entered.connect(func() -> void: hover = true; queue_redraw())
		mouse_exited.connect(func() -> void: hover = false; queue_redraw())
		tooltip_text = ""

	func apply(st: Dictionary) -> void:
		kind = st["kind"]; title = st["title"]; cost = st.get("cost", "")
		enabled = st.get("enabled", true); selected = st.get("selected", false); count = st.get("count", -1)
		queue_redraw()

	func _gui_input(e: InputEvent) -> void:
		if e is InputEventMouseButton and e.pressed and e.button_index == MOUSE_BUTTON_LEFT:
			pressed.emit(index)
			accept_event()

	func _draw() -> void:
		var r := Rect2(Vector2.ZERO, Vector2(size.x, 70))
		var bg := Color(0.13, 0.12, 0.1)
		if selected:
			bg = Color(0.32, 0.26, 0.13)
		elif hover and enabled:
			bg = Color(0.2, 0.18, 0.14)
		draw_rect(r, bg)
		var border := Color(0.95, 0.8, 0.42) if selected else (Color(0.62, 0.52, 0.3) if enabled else Color(0.3, 0.28, 0.22))
		draw_rect(r, border, false, 2.0)
		var ic := Color(0.9, 0.86, 0.72) if enabled else Color(0.38, 0.36, 0.32)
		var c := r.get_center()
		match kind:
			"attack": _pistol(c, ic)
			"overwatch": _eye(c, ic)
			"inspect": _lens(c, ic)
			"weld": _torch(c, ic)
			"medkit": _cross(c, ic)
		var f := label_font if label_font else ThemeDB.fallback_font
		draw_string(f, Vector2(5, 15), str(index + 1), HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(0.95, 0.8, 0.42))
		if cost != "":
			draw_string(f, Vector2(0, 66), cost, HORIZONTAL_ALIGNMENT_RIGHT, size.x - 5, 11, ic)
		if count >= 0:
			draw_string(f, Vector2(0, 15), "x%d" % count, HORIZONTAL_ALIGNMENT_RIGHT, size.x - 5, 12, ic)
		draw_string(f, Vector2(0, 88), title, HORIZONTAL_ALIGNMENT_CENTER, size.x, 11, ic)

	func _pistol(c: Vector2, col: Color) -> void:
		var pts := PackedVector2Array([c + Vector2(-22, -10), c + Vector2(20, -10), c + Vector2(20, -2), c + Vector2(-4, -2),
			c + Vector2(-6, 2), c + Vector2(-2, 16), c + Vector2(-12, 16), c + Vector2(-16, 0), c + Vector2(-22, -2)])
		draw_colored_polygon(pts, col)
		draw_rect(Rect2(c + Vector2(-6, -2), Vector2(6, 6)), Color(0.13, 0.12, 0.1), false, 2.0)

	func _eye(c: Vector2, col: Color) -> void:
		var top := PackedVector2Array(); var bot := PackedVector2Array()
		for k in 17:
			var t := -1.0 + 2.0 * k / 16.0
			top.append(c + Vector2(t * 22, -sqrt(1.0 - t * t) * 12))
			bot.append(c + Vector2(t * 22, sqrt(1.0 - t * t) * 12))
		draw_polyline(top, col, 2.5); draw_polyline(bot, col, 2.5)
		draw_circle(c, 6.5, col)
		draw_line(c + Vector2(-26, -18), c + Vector2(-18, -13), col, 2.0)
		draw_line(c + Vector2(26, -18), c + Vector2(18, -13), col, 2.0)

	func _lens(c: Vector2, col: Color) -> void:
		draw_arc(c + Vector2(-4, -4), 12, 0, TAU, 24, col, 3.0)
		draw_line(c + Vector2(5, 5), c + Vector2(16, 16), col, 5.0)

	func _torch(c: Vector2, col: Color) -> void:
		draw_line(c + Vector2(-18, 14), c + Vector2(6, -6), col, 6.0)
		draw_line(c + Vector2(6, -6), c + Vector2(12, -12), col, 3.0)
		var flame := PackedVector2Array([c + Vector2(13, -13), c + Vector2(22, -18), c + Vector2(17, -10)])
		draw_colored_polygon(flame, Color(0.95, 0.6, 0.2) if col.r > 0.5 else col)
		for k in 4:
			var a := -0.8 + k * 0.4
			draw_line(c + Vector2(14, -14), c + Vector2(14, -14) + Vector2(cos(a), sin(a)) * 9, Color(1, 0.85, 0.4, 0.8) if col.r > 0.5 else col, 1.5)

	func _cross(c: Vector2, col: Color) -> void:
		draw_rect(Rect2(c - Vector2(18, 14), Vector2(36, 28)), col, false, 2.5)
		draw_rect(Rect2(c - Vector2(3, 10), Vector2(6, 20)), Color(0.78, 0.22, 0.16) if col.r > 0.5 else col)
		draw_rect(Rect2(c - Vector2(10, 3), Vector2(20, 6)), Color(0.78, 0.22, 0.16) if col.r > 0.5 else col)


class Portrait extends Control:
	func _draw() -> void:
		var r := Rect2(Vector2.ZERO, size)
		draw_rect(r, Color(0.16, 0.18, 0.16))
		var c := Vector2(size.x / 2, size.y * 0.42)
		draw_circle(c + Vector2(0, -6), 17, Color(0.68, 0.55, 0.45))
		draw_arc(c + Vector2(0, -10), 18, PI, TAU, 16, Color(0.24, 0.27, 0.22), 9.0)
		var body := PackedVector2Array([Vector2(8, size.y), Vector2(14, size.y * 0.66), Vector2(size.x - 14, size.y * 0.66), Vector2(size.x - 8, size.y)])
		draw_colored_polygon(body, Color(0.3, 0.38, 0.27))
		draw_line(Vector2(size.x / 2 - 12, size.y * 0.64), Vector2(size.x / 2 + 12, size.y * 0.64), Color(0.12, 0.12, 0.1), 6.0)
		draw_rect(r, Color(0.62, 0.52, 0.3), false, 2.0)
