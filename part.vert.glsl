#version 430

layout(location = 0) in ivec3 pos;
out PerVertex
{
	ivec3 pos;
} vert;

void main() {
	vert.pos = pos;
}
