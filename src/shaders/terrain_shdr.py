# terrain_unified_shdr.py
# Combines correct lighting (from terrain_shdr.py) with working fog (from terrain_fog_shdr.py)

VERTEX_SHADER_SRC = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;

uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
uniform vec3 uLightDir;
uniform float uLightIntensity;
uniform vec3 uCameraPos;   // required for fog (passed but not used in vertex)

out vec3 vColor;
out vec3 vWorldPos;

void main() {
    vec3 normal = normalize(aNormal);
    vec3 lightDir = normalize(uLightDir);
    float diff = max(dot(normal, lightDir), 0.0);
    diff = diff * uLightIntensity;
    float ambient = 0.1 * (0.2 + 0.8 * uLightIntensity);
    diff = max(diff, ambient);

    float h = aPos.y;
    vColor = mix(vec3(0.3, 0.6, 0.2), vec3(0.5, 0.4, 0.2), clamp((h + 2.0) / 6.0, 0.0, 1.0));
    vColor *= diff;

    vec4 worldPos4 = uModel * vec4(aPos, 1.0);
    vWorldPos = worldPos4.xyz;
    gl_Position = uProjection * uView * worldPos4;
}
"""

FRAGMENT_SHADER_SRC = """
#version 330 core
in vec3 vColor;
in vec3 vWorldPos;
out vec4 FragColor;

uniform vec3 uCameraPos;
uniform vec3 uFogColor;
uniform float uFogStart;
uniform float uFogEnd;

void main() {
    float dist = distance(vWorldPos, uCameraPos);
    float fogFactor = clamp((dist - uFogStart) / (uFogEnd - uFogStart), 0.0, 1.0);
    vec3 finalColor = mix(vColor, uFogColor, fogFactor);
    FragColor = vec4(finalColor, 1.0);
}
"""

CROSSHAIR_VERT_SRC = """
#version 330 core
layout(location = 0) in vec2 aPos;
uniform vec2 uScreenSize;
void main() {
    vec2 pos = aPos / uScreenSize * 2.0 - 1.0;
    gl_Position = vec4(pos, 0.0, 1.0);
}
"""

CROSSHAIR_FRAG_SRC = """
#version 330 core
out vec4 FragColor;
void main() {
    FragColor = vec4(1.0, 1.0, 1.0, 1.0);
}
"""