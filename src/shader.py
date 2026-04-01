from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader

class Shader:
    def __init__(self, vert_src, frag_src):
        self.program = compileProgram(compileShader(vert_src, GL_VERTEX_SHADER),
                                      compileShader(frag_src, GL_FRAGMENT_SHADER))

    def use(self):
        glUseProgram(self.program)

    def set_mat4(self, name, mat):
        loc = glGetUniformLocation(self.program, name)
        glUniformMatrix4fv(loc, 1, GL_TRUE, mat)

    def set_vec3(self, name, vec):
        loc = glGetUniformLocation(self.program, name)
        glUniform3fv(loc, 1, vec)

    def set_vec2(self, name, vec):
        loc = glGetUniformLocation(self.program, name)
        glUniform2fv(loc, 1, vec)

    def set_float(self, name, val):
        loc = glGetUniformLocation(self.program, name)
        glUniform1f(loc, val)


# Shader sources remain unchanged
VERTEX_SHADER_SRC = """
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
    float ambient = 0.1 * (0.2 + 0.8 * uLightIntensity);
    diff = max(diff, ambient);

    float h = aPos.y;
    vColor = mix(vec3(0.3, 0.6, 0.2), vec3(0.5, 0.4, 0.2), clamp((h + 2.0) / 6.0, 0.0, 1.0));
    vColor *= diff;
    gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
}
"""

FRAGMENT_SHADER_SRC = """
#version 330 core
in vec3 vColor;
out vec4 FragColor;

void main() {
    FragColor = vec4(vColor, 1.0);
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
