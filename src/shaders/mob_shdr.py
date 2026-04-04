MOB_VERTEX_SHADER_SRC = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;

uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
uniform vec3 uLightDir;
uniform float uLightIntensity;

out vec3 vColor;

void main() {
    vec3 normal = normalize(aNormal);
    vec3 lightDir = normalize(uLightDir);
    float diff = max(dot(normal, lightDir), 0.0);
    diff = diff * uLightIntensity;
    float ambient = 0.2;
    diff = max(diff, ambient);
    // Mob colour: red-ish
    vec3 objectColor = vec3(0.8, 0.2, 0.2);
    vColor = objectColor * diff;
    gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
}
"""

MOB_FRAGMENT_SHADER_SRC = """
#version 330 core
in vec3 vColor;
out vec4 FragColor;
void main() {
    FragColor = vec4(vColor, 1.0);
}
"""
