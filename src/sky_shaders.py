# ------------------------------ Sky gradient background ------------------------------
SKY_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec2 aPos;
out vec2 vTexCoord;
void main() {
    gl_Position = vec4(aPos, 0.0, 1.0);
    vTexCoord = aPos * 0.5 + 0.5;
}
"""

SKY_FRAGMENT_SHADER = """
#version 330 core
in vec2 vTexCoord;
uniform float uDayFactor;
uniform vec2 uScreenSize;
out vec4 FragColor;

vec3 nightZenith = vec3(0.05, 0.05, 0.15);
vec3 nightHorizon = vec3(0.1, 0.1, 0.2);
vec3 dayZenith = vec3(0.2, 0.5, 0.9);
vec3 dayHorizon = vec3(1.0, 0.8, 0.5);

void main() {
    float t = vTexCoord.y;
    vec3 zenith = mix(nightZenith, dayZenith, uDayFactor);
    vec3 horizon = mix(nightHorizon, dayHorizon, uDayFactor);
    vec3 color = mix(horizon, zenith, t);
    FragColor = vec4(color, 1.0);
}
"""

# ------------------------------ Celestial Shader (3D Sphere) ------------------------------
CELESTIAL_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
uniform vec3 uColor;
out vec3 vColor;

void main() {
    gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
    vec3 lightDir = normalize(vec3(1.0, 2.0, 1.0));
    vec3 normal = normalize(aNormal);
    float diff = max(dot(normal, lightDir), 0.2);
    vColor = uColor * diff;
}
"""

CELESTIAL_FRAGMENT_SHADER = """
#version 330 core
in vec3 vColor;
out vec4 FragColor;

void main() {
    FragColor = vec4(vColor, 1.0);
}
"""

# ------------------------------ Cloud Sphere Shader (with alpha) ------------------------------
CLOUD_SPHERE_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
out float vAlpha;

void main() {
    gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
    vAlpha = 0.7;
}
"""

CLOUD_SPHERE_FRAGMENT_SHADER = """
#version 330 core
in float vAlpha;
out vec4 FragColor;

void main() {
    FragColor = vec4(0.95, 0.95, 0.95, vAlpha);
}
"""

# ------------------------------ Star Shader (static twinkling points) ------------------------------
STAR_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec3 aPos;
uniform mat4 uView;
uniform mat4 uProjection;
uniform float uTime;

out float vBrightness;

void main() {
    vec4 worldPos = vec4(aPos, 1.0);
    gl_Position = uProjection * uView * worldPos;
    // Use position as seed for twinkling
    float seed = sin(aPos.x * 10.0 + aPos.y * 8.0 + aPos.z * 12.0);
    float twinkle = 0.5 + 0.5 * sin(uTime * 2.0 + seed * 100.0);
    vBrightness = 0.6 + 0.4 * twinkle;
    gl_PointSize = 2.0 + twinkle * 1.5;
}
"""

STAR_FRAGMENT_SHADER = """
#version 330 core
in float vBrightness;
out vec4 FragColor;

void main() {
    vec2 coord = gl_PointCoord;
    float dist = length(coord - vec2(0.5));
    if (dist > 0.5) discard;
    float alpha = (1.0 - dist * 2.0) * 0.8;
    FragColor = vec4(1.0, 1.0, 1.0, alpha * vBrightness);
}
"""

# ------------------------------ Snow Shader (moving points) ------------------------------
SNOW_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec3 aPos;
uniform mat4 uView;
uniform mat4 uProjection;
uniform float uTime;

out float vBrightness;

void main() {
    vec4 worldPos = vec4(aPos, 1.0);
    gl_Position = uProjection * uView * worldPos;
    float twinkle = 0.5 + 0.5 * sin(uTime * 2.0 + aPos.x * 10.0 + aPos.y * 8.0 + aPos.z * 12.0);
    vBrightness = 0.6 + 0.4 * twinkle;
    gl_PointSize = 8.0 + twinkle * 3.0;
}
"""

SNOW_FRAGMENT_SHADER = """
#version 330 core
in float vBrightness;
out vec4 FragColor;

void main() {
    vec2 coord = gl_PointCoord;
    float dist = length(coord - vec2(0.5));
    if (dist > 0.5) discard;
    float alpha = (1.0 - dist * 2.0) * 0.8;
    FragColor = vec4(1.0, 1.0, 1.0, alpha * vBrightness);
}
"""
