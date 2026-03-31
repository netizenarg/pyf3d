import numpy
import ctypes
from OpenGL.GL import *


class Target:
    def __init__(self, position, size=0.5):
        self.position = position
        self.size = size
        self.active = True
        self.vao = None
        self.vbo = None
        self.ebo = None
        self.setup_cube()

    def setup_cube(self):
        vertices = numpy.array([
            -0.5, -0.5, -0.5,  0.0, -1.0,  0.0,
             0.5, -0.5, -0.5,  0.0, -1.0,  0.0,
             0.5, -0.5,  0.5,  0.0, -1.0,  0.0,
            -0.5, -0.5,  0.5,  0.0, -1.0,  0.0,
            -0.5,  0.5, -0.5,  0.0,  1.0,  0.0,
             0.5,  0.5, -0.5,  0.0,  1.0,  0.0,
             0.5,  0.5,  0.5,  0.0,  1.0,  0.0,
            -0.5,  0.5,  0.5,  0.0,  1.0,  0.0,
            -0.5, -0.5, -0.5, -1.0,  0.0,  0.0,
            -0.5,  0.5, -0.5, -1.0,  0.0,  0.0,
            -0.5,  0.5,  0.5, -1.0,  0.0,  0.0,
            -0.5, -0.5,  0.5, -1.0,  0.0,  0.0,
             0.5, -0.5, -0.5,  1.0,  0.0,  0.0,
             0.5,  0.5, -0.5,  1.0,  0.0,  0.0,
             0.5,  0.5,  0.5,  1.0,  0.0,  0.0,
             0.5, -0.5,  0.5,  1.0,  0.0,  0.0,
            -0.5, -0.5, -0.5,  0.0,  0.0, -1.0,
             0.5, -0.5, -0.5,  0.0,  0.0, -1.0,
             0.5,  0.5, -0.5,  0.0,  0.0, -1.0,
            -0.5,  0.5, -0.5,  0.0,  0.0, -1.0,
            -0.5, -0.5,  0.5,  0.0,  0.0,  1.0,
             0.5, -0.5,  0.5,  0.0,  0.0,  1.0,
             0.5,  0.5,  0.5,  0.0,  0.0,  1.0,
            -0.5,  0.5,  0.5,  0.0,  0.0,  1.0,
        ], dtype=numpy.float32)

        indices = numpy.array([
             0,  1,  2,  0,  2,  3,
             4,  5,  6,  4,  6,  7,
             8,  9, 10,  8, 10, 11,
            12, 13, 14, 12, 14, 15,
            16, 17, 18, 16, 18, 19,
            20, 21, 22, 20, 22, 23
        ], dtype=numpy.uint32)

        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.ebo = glGenBuffers(1)

        glBindVertexArray(self.vao)

        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)

        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 24, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 24, ctypes.c_void_p(12))
        glEnableVertexAttribArray(1)

        glBindVertexArray(0)

    def draw(self, shader, view, proj, light_dir):
        if not self.active:
            return
        model = numpy.eye(4)
        model[0, 3] = self.position[0]
        model[1, 3] = self.position[1]
        model[2, 3] = self.position[2]
        model[0, 0] = self.size
        model[1, 1] = self.size
        model[2, 2] = self.size

        shader.use()
        shader.set_mat4("uModel", model)
        shader.set_mat4("uView", view)
        shader.set_mat4("uProjection", proj)
        shader.set_vec3("uLightDir", light_dir)

        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, 36, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def hit(self, ray_origin, ray_dir):
        center = self.position
        radius = self.size * 0.866
        oc = ray_origin - center
        a = numpy.dot(ray_dir, ray_dir)
        b = 2.0 * numpy.dot(oc, ray_dir)
        c = numpy.dot(oc, oc) - radius * radius
        disc = b * b - 4 * a * c
        return disc >= 0
