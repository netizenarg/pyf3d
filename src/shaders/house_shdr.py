HOUSE_VERTEX_SHADER_SRC = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in vec4 aColor;   // Now RGBA

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

HOUSE_FRAGMENT_SHADER_SRC = """
#version 330 core
in vec4 vColor;
in float vBrightness;
out vec4 FragColor;

void main() {
    FragColor = vec4(vColor.rgb * vBrightness, vColor.a);
}
"""