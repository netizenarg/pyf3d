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
