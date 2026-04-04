HEALTH_VERTEX_SHADER_SRC = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec2 aTexCoord;

uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
uniform vec3 uLightDir;
uniform float uLightIntensity;

out vec2 vTexCoord;
out float vBrightness;

void main() {
    vTexCoord = aTexCoord;
    vec3 normal = vec3(0.0, 1.0, 0.0); // simplified lighting
    vec3 lightDir = normalize(uLightDir);
    float diff = max(dot(normal, lightDir), 0.0);
    diff = diff * uLightIntensity;
    float ambient = 0.3;
    vBrightness = max(diff, ambient);
    gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
}
"""

HEALTH_FRAGMENT_SHADER_SRC = """
#version 330 core
in vec2 vTexCoord;
in float vBrightness;
out vec4 FragColor;
uniform sampler2D uTexture;
void main() {
    vec4 texColor = texture(uTexture, vTexCoord);
    FragColor = vec4(texColor.rgb * vBrightness, 1.0);
}
"""
