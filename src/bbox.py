import numpy
import ctypes

from OpenGL.GL import *

from shaders.shader import Shader
from shaders.bbox_shdr import BBOX_VERTEX, BBOX_FRAGMENT


class BoundingBox:
    def __init__(self):
        self.enabled = False
        self.shader = Shader(BBOX_VERTEX, BBOX_FRAGMENT)
        self._setup_buffers()

    def _setup_buffers(self):
        # 8 corners of a unit cube (centered at origin, size 1)
        corners = numpy.array([
            [-0.5, -0.5, -0.5], [ 0.5, -0.5, -0.5],
            [ 0.5, -0.5,  0.5], [-0.5, -0.5,  0.5],
            [-0.5,  0.5, -0.5], [ 0.5,  0.5, -0.5],
            [ 0.5,  0.5,  0.5], [-0.5,  0.5,  0.5]
        ], dtype=numpy.float32)

        # 12 edges (line pairs)
        edges = [
            (0,1), (1,2), (2,3), (3,0),  # bottom
            (4,5), (5,6), (6,7), (7,4),  # top
            (0,4), (1,5), (2,6), (3,7)   # vertical
        ]

        line_vertices = []
        for a,b in edges:
            line_vertices.append(corners[a])
            line_vertices.append(corners[b])
        self.line_vertices = numpy.array(line_vertices, dtype=numpy.float32).flatten()

        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, self.line_vertices.nbytes, self.line_vertices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)
        self.edge_count = len(edges) * 2

    def draw(self, center, size, view, proj, color=(1,1,0)):
        if not self.enabled:
            return
        model = numpy.eye(4, dtype=numpy.float32)
        model[0,3] = center[0]
        model[1,3] = center[1]
        model[2,3] = center[2]
        model[0,0] = size[0]
        model[1,1] = size[1]
        model[2,2] = size[2]
        mvp = proj @ view @ model

        glUseProgram(self.shader.program)
        glUniformMatrix4fv(glGetUniformLocation(self.shader.program, "uMVP"), 1, GL_TRUE, mvp)
        glUniform3f(glGetUniformLocation(self.shader.program, "uColor"), *color)
        glBindVertexArray(self.vao)
        glDrawArrays(GL_LINES, 0, self.edge_count)
        glBindVertexArray(0)
