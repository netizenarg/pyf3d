# Shader for Bazuka weapon model (blue tube)
BAZUKA_VERTEX_SHADER_SRC = """
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
    // Blue tube color
    vColor = vec3(0.2, 0.3, 0.8) * diff;
    gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
}
"""

BAZUKA_FRAGMENT_SHADER_SRC = """
#version 330 core
in vec3 vColor;
out vec4 FragColor;
void main() {
    FragColor = vec4(vColor, 1.0);
}
"""

# Shader for BazukaAmmo (orange tetrahedron)
BAZUKA_AMMO_VERTEX_SHADER_SRC = """
#version 330 core
layout(location = 0) in vec3 aPos;
uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
out vec3 vColor;
void main() {
    gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
    vColor = vec3(1.0, 0.5, 0.0); // orange
}
"""

BAZUKA_AMMO_FRAGMENT_SHADER_SRC = """
#version 330 core
in vec3 vColor;
out vec4 FragColor;
void main() {
    FragColor = vec4(vColor, 1.0);
}
"""

# Particle shader for bazuka explosion (orange sparks)
BAZUKA_PARTICLE_VERTEX_SHADER_SRC = """
#version 330 core
layout(location = 0) in vec3 aPos;
uniform mat4 uView;
uniform mat4 uProjection;
uniform float uSize;
out float vLife;
void main() {
    gl_PointSize = uSize;
    gl_Position = uProjection * uView * vec4(aPos, 1.0);
    vLife = 1.0;
}
"""

BAZUKA_PARTICLE_FRAGMENT_SHADER_SRC = """
#version 330 core
in float vLife;
out vec4 FragColor;
void main() {
    FragColor = vec4(1.0, 0.5, 0.0, 0.8);
}
"""