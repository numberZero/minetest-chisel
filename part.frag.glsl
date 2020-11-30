#version 430

layout(location = 2) uniform vec4 i_color = {1.0, 1.0, 1.0, 1.0};
layout(location = 0) out vec4 o_color;
layout(location = 1) out ivec4 o_id;

in vec4 color;
in flat ivec4 id;

void main() {
	o_color = i_color * color;
	o_id = id;
}
