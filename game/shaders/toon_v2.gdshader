shader_type spatial;
// Live characters in the same light as the pre-rendered world (docs/VISUAL_DIRECTION.md): the key light
// from top-left-front, three hard bands (cool blue-grey shade, mid, slightly warm lit), the texture
// muted a little (saturation 0.88), no scene lights. Matches render_character.py's bands.
render_mode unshaded, cull_back, depth_draw_opaque;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap;
uniform bool has_tex = true;
uniform vec4 albedo_color : source_color = vec4(1.0);
uniform float exposure = 1.0;
uniform float saturation = 0.88;
uniform vec3 light_dir = vec3(-0.55, 0.63, 0.55);     // world space (Blender's (-0.55, -0.55, 0.63))
uniform vec3 shade_col = vec3(0.47, 0.5, 0.57);
uniform vec3 mid_col = vec3(0.79, 0.79, 0.8);
uniform vec3 lit_col = vec3(1.09, 1.04, 0.96);
uniform float t_mid = 0.12;
uniform float t_lit = 0.45;
uniform bool flat_shade = false;   // facet normals (the worm's sprite renders are flat-shaded)
uniform vec4 flash : source_color = vec4(1.0);
// duotone (the Changed): the texture's brightness picks between a coat colour and pale, mottled skin
uniform bool duotone = false;
uniform vec3 duo_dark : source_color = vec3(0.16, 0.13, 0.11);
uniform vec3 duo_light : source_color = vec3(0.70, 0.71, 0.66);
uniform vec2 duo_split = vec2(0.22, 0.42);
uniform float duo_mottle = 1.0;     // 1 = the Changed's blotchy skin, 0 = plain (townsfolk)

float duo_noise(vec2 p) {
	vec2 i = floor(p); vec2 f = fract(p); f = f * f * (3.0 - 2.0 * f);
	float a = fract(sin(dot(i, vec2(127.1, 311.7))) * 43758.5453);
	float b = fract(sin(dot(i + vec2(1.0, 0.0), vec2(127.1, 311.7))) * 43758.5453);
	float c = fract(sin(dot(i + vec2(0.0, 1.0), vec2(127.1, 311.7))) * 43758.5453);
	float d = fract(sin(dot(i + vec2(1.0, 1.0), vec2(127.1, 311.7))) * 43758.5453);
	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

void fragment() {
	vec3 base = albedo_color.rgb;
	if (has_tex) {
		base *= texture(albedo_tex, UV).rgb;
	}
	base = clamp(base * exposure, 0.0, 1.0);
	float l = dot(base, vec3(0.2126, 0.7152, 0.0722));
	base = mix(vec3(l), base, saturation);
	if (duotone) {
		float warm = smoothstep(0.015, 0.08, base.r - base.b);         // skin is warm; navy, black and grey cloth are not
		float k = smoothstep(duo_split.x, duo_split.y, l) * warm;
		float mott = duo_noise(UV * 90.0) * 0.6 + duo_noise(UV * 23.0) * 0.4;
		float bruise = smoothstep(0.55, 0.85, duo_noise(UV * 37.0 + 3.1));
		vec3 skin = duo_light * mix(1.0, 0.78 + 0.34 * mott, duo_mottle);
		skin = mix(skin, skin * vec3(0.78, 0.70, 0.86), bruise * duo_mottle);        // violet blotches under the skin
		vec3 coat = duo_dark * clamp(0.75 + 0.9 * l / max(duo_split.x, 0.01), 0.6, 1.8);
		base = mix(coat, skin, k);
	}
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
