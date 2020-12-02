#version 430

layout(points) in;
layout(triangle_strip, max_vertices = 24) out;

layout(location = 0) uniform mat4 mvp;
layout(location = 1) uniform int part_id = 0;
layout(binding = 0) uniform usampler3D part_shape;

in PerVertex
{
	in ivec3 pos;
} vert[];

out vec4 color;
out vec2 uv;
out flat ivec4 id;

struct Face {
	ivec3 u, v, w;
	mat4x2 tmat;
	float shade;
};
const Face faces[6] = {
	{ {0, 1, 0}, {1, 0, 0}, {0, 0, 1}, {{-1, 0}, {0, -1}, {0, 0}, {1, 1}}, 0.84 },
	{ {1, 0, 0}, {0, 0, 1}, {0, 1, 0}, {{-1, 0}, {0, 0}, {0, -1}, {1, 1}}, 1.00 },
	{ {0, 0, 1}, {0, 1, 0}, {1, 0, 0}, {{0, 0}, {0, -1}, {1, 0}, {0, 1}}, 0.67 },
	{ {1, 0, 0}, {0, 1, 0}, {0, 0, -1}, {{1, 0}, {0, -1}, {0, 0}, {0, 1}}, 0.84 },
	{ {0, 0, 1}, {1, 0, 0}, {0, -1, 0}, {{1, 0}, {0, 0}, {0, 1}, {0, 0}}, 0.45 },
	{ {0, 1, 0}, {0, 0, 1}, {-1, 0, 0}, {{0, 0}, {0, -1}, {-1, 0}, {1, 1}}, 0.67 },
};
const ivec2 offs[4] = {{0, 0}, {1, 0}, {0, 1}, {1, 1}};

ivec3 pos;

void MakeFace(int face_id) {
	Face face = faces[face_id];
	ivec3 w = face.w;
	ivec3 pos2 = pos + w;
	if (all(greaterThanEqual(pos2, ivec3(0))) && all(lessThan(pos2, textureSize(part_shape, 0)))) {
		uint type2 = texelFetch(part_shape, pos + w, 0).x;
		if (type2 != 0)
			return;
	}
	ivec3 face_offset = clamp(w, 0, 1);
	for (int vid = 0; vid < 4; vid++) {
		ivec2 vertex_offset = offs[vid];
		ivec3 off = face_offset + face.u * vertex_offset.x + face.v * vertex_offset.y;
		vec3 vp = vec3(pos + off - 8) * (1.0 / 16.0);
		gl_Position = mvp * vec4(vp, 1.0);
		color = vec4(face.shade.xxx, 1.0);
		uv = face.tmat * vec4(vp, 1.0);
		id = ivec4(pos, part_id | (face_id << 5));
		EmitVertex();
	}
	EndPrimitive();
}

void main() {
	pos = vert[0].pos;
	uint type = texelFetch(part_shape, pos, 0).x;
	if (type == 0)
		return;
	for (int k = 0; k < 6; k++)
		MakeFace(k);
}
