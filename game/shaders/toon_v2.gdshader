shader_type spatial;
// Live characters in the same light as the pre-rendered world (docs/VISUAL_DIRECTION.md): the key light
// from top-left-front, three hard bands (cool blue-grey shade, mid, slightly warm lit), the texture
// muted a little (saturation 0.88), no scene lights. Matches render_character.py's bands.
render_mode unshaded, cull_back, depth_draw_opaque;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap;
uniform bool has_tex = true;
uniform vec4 albedo_color : source_color = vec4(1.0);
uniform float saturation = 0.88;
uniform vec3 light_dir = vec3(-0.55, 0.63, 0.55);     // world space (Blender's (-0.55, -0.55, 0.63))
uniform vec3 shade_col = vec3(0.47, 0.5, 0.57);
uniform vec3 mid_col = vec3(0.79, 0.79, 0.8);
uniform vec3 lit_col = vec3(1.09, 1.04, 0.96);
uniform float t_mid = 0.12;
uniform float t_lit = 0.45;
uniform bool flat_shade = false;   // facet normals (the worm's sprite renders are flat-shaded)
uniform vec4 flash : source_color = vec4(1.0);

void fragment() {
	vec3 base = albedo_color.rgb;
	if (has_tex) {
		base *= texture(albedo_tex, UV).rgb;
	}
	float l = dot(base, vec3(0.2126, 0.7152, 0.0722));
	base = mix(vec3(l), base, saturation);
	vec3 L = normalize((VIEW_MATRIX * vec4(normalize(light_dir), 0.0)).xyz);
	vec3 n = normalize(NORMAL);
	if (flat_shade) { n = normalize(cross(dFdx(VERTEX), dFdy(VERTEX))); if (n.z < 0.0) n = -n; }
	float d = dot(n, L);
	vec3 band = d < t_mid ? shade_col : (d < t_lit ? mid_col : lit_col);
	// the bands are Blender's (scene-linear multipliers); the Compatibility renderer shades in sRGB,
	// so (tex_lin * band) -> sRGB equals tex_srgb * band^(1/2.2)
	band = pow(band, vec3(1.0 / 2.2));
	ALBEDO = base * band * flash.rgb;
}
