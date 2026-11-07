shader_type canvas_item;
// Cutaway for one full-height wall strip. Pixels higher than `cut` px above the wall's base line are
// dropped (fully, never half-transparent); a band under the cut is painted as the wall's sawn top.
uniform vec2 origin;          // strip sprite top-left, level coords
uniform vec2 size;
uniform vec2 base;            // a point on the wall's centre line at floor level, level coords
uniform float slope;          // screen dy/dx of that line
uniform float cut = 10000.0;  // height kept, in screen px
uniform vec4 cap_color : source_color = vec4(0.26, 0.25, 0.235, 1.0);   // matches the wall tops (WallTop)
uniform float edge_left = 0.0;   // > 0: the strip to the left is cut down to this height; draw a wall-end line
uniform float edge_right = 0.0;
uniform float cap_px = 13.0;

void fragment() {
	vec4 c = texture(TEXTURE, UV);
	if (cut < 1000.0) {
		vec2 p = origin + UV * size;
		float base_y = base.y + slope * (p.x - base.x);
		float top = base_y - cut;              // screen y of the cut line at this x
		if (p.y < top - cap_px) {
			c.a = 0.0;
		} else if (p.y < top && c.a > 0.5) {
			float edge = smoothstep(top - cap_px, top - cap_px + 1.5, p.y);
			c.rgb = mix(cap_color.rgb * 1.12, cap_color.rgb, smoothstep(0.0, 3.0, p.y - (top - cap_px)));
			c.a *= edge;
		}
	}
	if (c.a > 0.5 && (edge_left > 0.0 || edge_right > 0.0)) {
		vec2 p = origin + UV * size;
		float base_y = base.y + slope * (p.x - base.x);
		float lx = UV.x * size.x;
		if (edge_left > 0.0 && lx < 3.0 && p.y < base_y - edge_left) c.rgb = cap_color.rgb * 0.75;
		if (edge_right > 0.0 && size.x - lx < 3.0 && p.y < base_y - edge_right) c.rgb = cap_color.rgb * 0.75;
	}
	COLOR = c;
}
