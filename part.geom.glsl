#version 430

layout(points) in;
layout(triangle_strip, max_vertices = 24) out;

layout(location = 0) uniform mat4 mvp;
layout(location = 1) uniform int part_id = 0;

in PerVertex
{
	in ivec3 pos;
} vert[];

out vec4 color;
out flat ivec4 id;

ivec3 pos;

void MakeVertex(ivec3 off, float br) {
	gl_Position = mvp * vec4((vec3(pos + off - 8) - 0.5) / 16.0, 1.0);
	color = vec4(br.xxx, 1.0);
	id = ivec4(pos, part_id);
	EmitVertex();
}

void main() {
	pos = vert[0].pos;

	MakeVertex(ivec3(1, 0, 0), 0.67);
	MakeVertex(ivec3(1, 1, 0), 0.67);
	MakeVertex(ivec3(1, 0, 1), 0.67);
	MakeVertex(ivec3(1, 1, 1), 0.67);
	EndPrimitive();
	MakeVertex(ivec3(0, 0, 0), 0.67);
	MakeVertex(ivec3(0, 0, 1), 0.67);
	MakeVertex(ivec3(0, 1, 0), 0.67);
	MakeVertex(ivec3(0, 1, 1), 0.67);
	EndPrimitive();
	MakeVertex(ivec3(0, 1, 0), 1.00);
	MakeVertex(ivec3(0, 1, 1), 1.00);
	MakeVertex(ivec3(1, 1, 0), 1.00);
	MakeVertex(ivec3(1, 1, 1), 1.00);
	EndPrimitive();
	MakeVertex(ivec3(0, 0, 0), 0.45);
	MakeVertex(ivec3(1, 0, 0), 0.45);
	MakeVertex(ivec3(0, 0, 1), 0.45);
	MakeVertex(ivec3(1, 0, 1), 0.45);
	EndPrimitive();
	MakeVertex(ivec3(0, 0, 1), 0.84);
	MakeVertex(ivec3(1, 0, 1), 0.84);
	MakeVertex(ivec3(0, 1, 1), 0.84);
	MakeVertex(ivec3(1, 1, 1), 0.84);
	EndPrimitive();
	MakeVertex(ivec3(0, 0, 0), 0.84);
	MakeVertex(ivec3(0, 1, 0), 0.84);
	MakeVertex(ivec3(1, 0, 0), 0.84);
	MakeVertex(ivec3(1, 1, 0), 0.84);
	EndPrimitive();
}
