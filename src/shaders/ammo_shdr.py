AMMO_VERTEX_SHADER_SRC = """
#version 330 core
layout(location = 0) in vec3 aPos;
uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
void main() {
    gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
}
"""

AMMO_FRAGMENT_SHADER_SRC = """
#version 330 core
out vec4 FragColor;
void main() {
    FragColor = vec4(1.0, 1.0, 1.0, 1.0);
}
"""

PARTICLE_AMMO_EXPLOSION_VERTEX_SHADER_SRC = """
#version 330 core
layout(location = 0) in vec3 aPos;
uniform mat4 uView;
uniform mat4 uProjection;
uniform float uSize;
void main() {
    vec4 viewPos = uView * vec4(aPos, 1.0);
    gl_PointSize = uSize * (300.0 / (-viewPos.z));
    gl_Position = uProjection * viewPos;
}
"""

PARTICLE_AMMO_EXPLOSION_FRAGMENT_SHADER_SRC = """
#version 330 core
out vec4 FragColor;
uniform float uLife;
void main() {
    vec2 coord = gl_PointCoord;
    float dist = length(coord - vec2(0.5));
    if (dist > 0.5) discard;
    float alpha = (1.0 - dist * 2.0) * uLife;
    FragColor = vec4(1.0, 0.6, 0.2, alpha);
}
"""
