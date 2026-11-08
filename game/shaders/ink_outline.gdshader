shader_type spatial;
// Inverted-hull ink outline: the same ink colour and width as the pre-rendered sprites (render_character.py,
// worm.py: Solidify 1.1 cm, emission 0.035/0.03/0.025). That colour is a linear Blender value; the
// Compatibility renderer shades in sRGB, so it is converted here (otherwise it draws near-black).
render_mode unshaded, cull_front, depth_draw_opaque;

uniform float thickness_m = 0.011;
uniform vec3 ink = vec3(0.035, 0.03, 0.025);   // linear, as in Blender

void vertex() {
	float s = length(MODEL_MATRIX[0].xyz);           // model scale, so the width is in world metres
	VERTEX += normalize(NORMAL) * thickness_m / max(s, 1e-5);
}

void fragment() {
	ALBEDO = pow(ink, vec3(1.0 / 2.2));
}
