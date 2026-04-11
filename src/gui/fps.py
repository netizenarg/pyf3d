import glfw
import numpy

from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader

from gui.font import FONT_BITMAPS
from shaders.gui_shdr import TEXT_VERTEX_SHADER, TEXT_FRAGMENT_SHADER


class FPSOverlay:
    def __init__(self, screen_width, screen_height, enabled=False):
        self.width = screen_width
        self.height = screen_height
        self.enabled = enabled
        self.fps = 0.0
        self.frame_count = 0
        self.last_time = glfw.get_time()

        # Shaders (reuse from gui_shaders)
        self.text_shader = compileProgram(
            compileShader(TEXT_VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(TEXT_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
        )

        # Quad VAO (same as StatsPanel)
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

        # Font texture
        self.font_tex = self._create_font_texture()

        # Cache uniform locations
        self.text_uScreenSize = glGetUniformLocation(self.text_shader, "uScreenSize")
        self.text_uColor = glGetUniformLocation(self.text_shader, "uColor")
        self.text_uOffset = glGetUniformLocation(self.text_shader, "uOffset")
        self.text_uScale = glGetUniformLocation(self.text_shader, "uScale")
        self.text_uTexRect = glGetUniformLocation(self.text_shader, "uTexRect")
        self.text_uFontTexture = glGetUniformLocation(self.text_shader, "uFontTexture")

    def _create_font_texture(self):
        cols, rows = 16, 8
        cell_w, cell_h = 8, 8
        tex_w, tex_h = cols * cell_w, rows * cell_h
        data = numpy.zeros((tex_h, tex_w, 4), dtype=numpy.uint8)
        for code in range(32, 128):
            row = (code - 32) // cols
            col = (code - 32) % cols
            bitmap = FONT_BITMAPS.get(code, [0]*8)
            for y in range(cell_h):
                row_bits = bitmap[y] if y < len(bitmap) else 0
                for x in range(cell_w):
                    if (row_bits >> (7 - x)) & 1:
                        data[row*cell_h + y, col*cell_w + x] = [255,255,255,255]
        tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tex_w, tex_h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glBindTexture(GL_TEXTURE_2D, 0)
        return tex

    def update_fps(self, dt):
        self.frame_count += 1
        # Update FPS every second
        if self.last_time + 1.0 <= glfw.get_time():
            self.fps = self.frame_count / (glfw.get_time() - self.last_time)
            self.frame_count = 0
            self.last_time = glfw.get_time()

    def draw(self, dt):
        self.update_fps(dt)
        if not self.enabled:
            return
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glUseProgram(self.text_shader)
        glUniform2f(self.text_uScreenSize, self.width, self.height)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.font_tex)
        glUniform1i(self.text_uFontTexture, 0)
        glUniform3f(self.text_uColor, 1.0, 1.0, 1.0)  # white text

        text = f"FPS: {self.fps:.1f}"
        x, y = 10, 10  # top-left corner (top‑origin)
        size = 16
        self._draw_text(text, x, y, size)

        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)

    def _draw_text(self, text, x, y, size):
        glBindVertexArray(self.quad_vao)
        for i, ch in enumerate(text):
            code = ord(ch)
            if 97 <= code <= 122:  # uppercase
                code -= 32
            if code < 32 or code > 127:
                continue
            idx = code - 32
            row = idx // 16
            col = idx % 16
            u0 = col / 16.0
            v0 = row / 8.0
            u1 = (col + 1) / 16.0
            v1 = (row + 1) / 8.0
            tex_rect = (u0, v0, u1 - u0, v1 - v0)
            glUniform4f(self.text_uTexRect, *tex_rect)

            pos_x = x + i * size
            # Convert top‑origin y to bottom‑origin centre
            y_center = self.height - (y + size/2)
            glUniform2f(self.text_uOffset, pos_x + size/2, y_center)
            glUniform2f(self.text_uScale, size, size)
            glDrawElements(GL_TRIANGLES, self.quad_index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def resize(self, width, height):
        self.width = width
        self.height = height
