# health_bar.py
import numpy
import math
import ctypes
from OpenGL.GL import *
from shaders.shader import Shader
from shaders.mob_shdr import HEALTH_BAR_VERTEX, HEALTH_BAR_FRAGMENT

class HealthBarRenderer:
    def __init__(self):
        self.vao = None
        self.vbo = None
        self.ebo = None
        self.shader = None
        self._init_geometry()

    def _init_geometry(self):
        vertices = numpy.array([
            -0.5, 0.0, 0.0,
             0.5, 0.0, 0.0,
             0.5, 0.1, 0.0,
            -0.5, 0.1, 0.0,
        ], dtype=numpy.float32)
        indices = numpy.array([0, 1, 2, 0, 2, 3], dtype=numpy.uint32)

        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.ebo = glGenBuffers(1)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)

        self.shader = Shader(HEALTH_BAR_VERTEX, HEALTH_BAR_FRAGMENT)

    def draw(self, world_pos, health_percent, view, proj, camera_pos, bar_width=0.8, bar_height=0.15, y_offset=1.2):
        """Draw a billboarded health bar above world_pos."""
        to_cam = camera_pos - world_pos
        to_cam[1] = 0.0
        norm = numpy.linalg.norm(to_cam)
        if norm < 0.001:
            return
        to_cam /= norm
        angle = math.atan2(to_cam[0], to_cam[2])
        c = math.cos(angle)
        s = math.sin(angle)

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDepthMask(GL_FALSE)
        glEnable(GL_DEPTH_TEST)

        self.shader.use()
        glUniformMatrix4fv(glGetUniformLocation(self.shader.program, "uView"), 1, GL_TRUE, view)
        glUniformMatrix4fv(glGetUniformLocation(self.shader.program, "uProjection"), 1, GL_TRUE, proj)

        # Background (red)
        model_bg = numpy.array([
            [c * bar_width, 0, s * bar_width, 0],
            [0, bar_height, 0, 0],
            [-s * bar_width, 0, c * bar_width, 0],
            [0, 0, 0, 1]
        ], dtype=numpy.float32)
        model_bg[0, 3] = world_pos[0]
        model_bg[1, 3] = world_pos[1] + y_offset
        model_bg[2, 3] = world_pos[2]
        glUniformMatrix4fv(glGetUniformLocation(self.shader.program, "uModel"), 1, GL_TRUE, model_bg)
        glUniform4f(glGetUniformLocation(self.shader.program, "uColor"), 0.3, 0.0, 0.0, 0.8)
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)

        # Fill (green)
        fill_width = bar_width * health_percent
        local_center_x = (fill_width - bar_width) / 2.0
        world_center_x = world_pos[0] + c * local_center_x
        world_center_z = world_pos[2] - s * local_center_x
        model_fill = numpy.array([
            [c * fill_width, 0, s * fill_width, 0],
            [0, bar_height, 0, 0],
            [-s * fill_width, 0, c * fill_width, 0],
            [0, 0, 0, 1]
        ], dtype=numpy.float32)
        model_fill[0, 3] = world_center_x
        model_fill[1, 3] = world_pos[1] + y_offset
        model_fill[2, 3] = world_center_z
        glUniformMatrix4fv(glGetUniformLocation(self.shader.program, "uModel"), 1, GL_TRUE, model_fill)
        glUniform4f(glGetUniformLocation(self.shader.program, "uColor"), 0.0, 0.8, 0.0, 0.9)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)

        glBindVertexArray(0)
        glDepthMask(GL_TRUE)
        glDisable(GL_BLEND)