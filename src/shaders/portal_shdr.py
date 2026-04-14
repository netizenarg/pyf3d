PORTAL_PARTICLE_VERTEX_SHADER_SRC = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec4 aColor;
layout(location = 2) in float aSize;
uniform mat4 uView;
uniform mat4 uProjection;
out vec4 vColor;
void main() {
    vColor = aColor;
    gl_Position = uProjection * uView * vec4(aPos, 1.0);
    gl_PointSize = aSize * (300.0 / gl_Position.w);
}
"""

PORTAL_PARTICLE_FRAGMENT_SHADER_SRC = """
#version 330 core
in vec4 vColor;
out vec4 FragColor;
void main() {
    vec2 circCoord = gl_PointCoord * 2.0 - 1.0;
    float dist = length(circCoord);
    if (dist > 1.0) discard;
    float alpha = (1.0 - dist) * vColor.a;
    FragColor = vec4(vColor.rgb, alpha);
}
"""

PORTAL_VERTEX_SHADER_SRC = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in vec4 aColor;

uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
uniform vec3 uLightDir;
uniform float uLightIntensity;

out vec4 vColor;
out float vBrightness;

void main() {
    vec3 normal = normalize(aNormal);
    vec3 lightDir = normalize(uLightDir);
    float diff = max(dot(normal, lightDir), 0.0);
    diff = diff * uLightIntensity;
    float ambient = 0.3;
    vBrightness = max(diff, ambient);
    vColor = aColor;
    gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
}
"""

PORTAL_FRAGMENT_SHADER_SRC = """
#version 330 core
in vec4 vColor;
in float vBrightness;
out vec4 FragColor;

void main() {
    FragColor = vec4(vColor.rgb * vBrightness, vColor.a);
}
"""
