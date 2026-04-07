TREE_VERTEX_SHADER_SRC = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in vec2 aTexCoord;

uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
uniform vec3 uLightDir;
uniform float uLightIntensity;

out vec3 vColor;
out vec2 vTexCoord;
out float vBrightness;

void main() {
    vec3 normal = normalize(aNormal);
    vec3 lightDir = normalize(uLightDir);
    float diff = max(dot(normal, lightDir), 0.0);
    diff = diff * uLightIntensity;
    float ambient = 0.25;
    vBrightness = max(diff, ambient);
    vTexCoord = aTexCoord;
    gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
}
"""

TREE_FRAGMENT_SHADER_SRC = """
#version 330 core
in vec2 vTexCoord;
in float vBrightness;
out vec4 FragColor;

uniform sampler2D uTrunkTexture;
uniform sampler2D uFoliageTexture;
uniform int uPart;  // 0 = trunk, 1 = foliage

void main() {
    vec4 texColor;
    if (uPart == 0) {
        texColor = texture(uTrunkTexture, vTexCoord);
        if (texColor.a < 0.5) discard;
    } else {
        texColor = texture(uFoliageTexture, vTexCoord);
        if (texColor.a < 0.5) discard;
    }
    FragColor = vec4(texColor.rgb * vBrightness, texColor.a);
}
"""
