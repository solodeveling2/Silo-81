shader_type spatial;
// Inverted-hull ink outline, the same dark ink and ~1.1 cm width as the pre-rendered sprites.
render_mode unshaded, cull_front, depth_draw_opaque;

uniform float thickness_m = 0.008;
uniform vec3 ink = vec3(0.035, 0.03, 0.025);

void vertex() {
	float s = length(MODEL_MATRIX[0].xyz);           // model scale, so the width is in world metres
	VERTEX += normalize(NORMAL) * thickness_m / max(s, 1e-5);
}

void fragment() {
	ALBEDO = ink;
}
