#version 430

layout(location = 2) uniform vec4 i_color = {1.0, 1.0, 1.0, 1.0};
layout(binding = 1) uniform sampler2D part_texture;
layout(location = 0) out vec4 o_color;
layout(location = 1) out ivec4 o_id;

in vec4 color;
in vec2 uv;
in flat ivec4 id;

void main() {
	vec4 tex = texture(part_texture, uv);
	o_color = i_color * color * vec4(tex.xyz, 1.0);
	o_id = id;
}
