# text_renderer.py
import numpy
import ctypes
from OpenGL.GL import *
from gui.font import create_font_atlas
from shaders.shader import Shader
from shaders.gui_shdr import TEXT_VERTEX_SHADER, TEXT_FRAGMENT_SHADER

class TextRenderer:
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.font_atlas = create_font_atlas(16, 2.0)
        self.font_tex = self.font_atlas.tex_id
        self.shader = Shader(TEXT_VERTEX_SHADER, TEXT_FRAGMENT_SHADER)

        # Quad for text
        quad_verts = numpy.array([
            -0.5, -0.5,  0.0, 0.0,
             0.5, -0.5,  1.0, 0.0,
             0.5,  0.5,  1.0, 1.0,
            -0.5,  0.5,  0.0, 1.0,
        ], dtype=numpy.float32)
        quad_indices = numpy.array([0,1,2, 0,2,3], dtype=numpy.uint32)
        self.quad_vao = glGenVertexArrays(1)
        self.quad_vbo = glGenBuffers(1)
        self.quad_ebo = glGenBuffers(1)
        glBindVertexArray(self.quad_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.quad_vbo)
        glBufferData(GL_ARRAY_BUFFER, quad_verts.nbytes, quad_verts, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.quad_ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, quad_indices.nbytes, quad_indices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(8))
        glEnableVertexAttribArray(1)
        glBindVertexArray(0)
        self.quad_index_count = 6

    def resize(self, width, height):
        self.screen_width = width
        self.screen_height = height

    def draw_text_2d(self, text, x, y, size, color=(1,1,1,1)):
        """Draw text at screen coordinates (x, y) with given size and color."""
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        self.shader.use()
        glUniform2f(glGetUniformLocation(self.shader.program, "uScreenSize"), self.screen_width, self.screen_height)
        glUniform3f(glGetUniformLocation(self.shader.program, "uColor"), color[0], color[1], color[2])
        glUniform1f(glGetUniformLocation(self.shader.program, "uSmoothing"), 0.1 / (size / self.font_atlas.pixel_height))
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.font_tex)
        glUniform1i(glGetUniformLocation(self.shader.program, "uFontTexture"), 0)

        glBindVertexArray(self.quad_vao)
        scale = size / self.font_atlas.pixel_height
        for i, ch in enumerate(text):
            glyph = self.font_atlas.get_glyph(ch)
            if glyph is None:
                continue
            gw, gh, advance, u0, v0, u1, v1 = glyph
            tex_rect = (u0, v0, u1 - u0, v1 - v0)
            glUniform4f(glGetUniformLocation(self.shader.program, "uTexRect"), *tex_rect)
            pos_x = x + i * advance * scale
            quad_w = gw * scale
            quad_h = gh * scale
            y_bottom = self.screen_height - (y + quad_h)
            glUniform2f(glGetUniformLocation(self.shader.program, "uOffset"), pos_x + quad_w/2, y_bottom + quad_h/2)
            glUniform2f(glGetUniformLocation(self.shader.program, "uScale"), quad_w, quad_h)
            glDrawElements(GL_TRIANGLES, self.quad_index_count, GL_UNSIGNED_INT, None)

        glBindVertexArray(0)
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)