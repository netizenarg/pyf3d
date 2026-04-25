import numpy
import ctypes

from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader

from shaders.shader import Shader
from shaders.gui_shdr import *
from gui.font import create_font_atlas


class StatsPanel:
    def __init__(self, screen_width, screen_height, player=None, enabled=True):
        self.player = player
        self.enabled = enabled
        self.width = screen_width
        self.height = screen_height
        self.panel_margin = 10
        self.char_size = 8
        self.padding = 10
        self.cell_padding = 8
        self.row_height = self.char_size + self.cell_padding * 2
        self.rows = 3
        self.cols = 4

        # Table content – rows x columns
        self.cells = [[""] * self.cols for _ in range(self.rows)]

        self.rect_shader = Shader(RECT_VERTEX_SHADER, RECT_FRAGMENT_SHADER)
        self.text_shader = Shader(TEXT_VERTEX_SHADER, TEXT_FRAGMENT_SHADER)

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

        self.font_atlas = create_font_atlas(32, 2.0)
        self.font_tex = self.font_atlas.tex_id

        self.rect_uScreenSize = self.rect_shader.getUniformLocation("uScreenSize")
        self.rect_uColor = self.rect_shader.getUniformLocation("uColor")
        self.rect_uOffset = self.rect_shader.getUniformLocation("uOffset")
        self.rect_uScale = self.rect_shader.getUniformLocation("uScale")

        self.text_uScreenSize = self.text_shader.getUniformLocation("uScreenSize")
        self.text_uColor = self.text_shader.getUniformLocation("uColor")
        self.text_uOffset = self.text_shader.getUniformLocation("uOffset")
        self.text_uScale = self.text_shader.getUniformLocation("uScale")
        self.text_uTexRect = self.text_shader.getUniformLocation("uTexRect")
        self.text_uFontTexture = self.text_shader.getUniformLocation("uFontTexture")
        self.text_uTexRect = self.text_shader.getUniformLocation("uTexRect")
        self.text_uSmoothing = self.text_shader.getUniformLocation("uSmoothing")

    def _create_font_texture(self):
        cols = 16
        rows = 8
        cell_w = 8
        cell_h = 8
        tex_w = cols * cell_w
        tex_h = rows * cell_h
        texture_data = numpy.zeros((tex_h, tex_w, 4), dtype=numpy.uint8)
        for code in range(32, 128):
            row = (code - 32) // cols
            col = (code - 32) % cols
            bitmap = FONT_BITMAPS.get(code, [0]*8)
            for y in range(cell_h):
                row_bits = bitmap[y] if y < len(bitmap) else 0
                for x in range(cell_w):
                    if (row_bits >> (7 - x)) & 1:
                        texture_data[row * cell_h + y, col * cell_w + x] = [255, 255, 255, 255]
                    else:
                        texture_data[row * cell_h + y, col * cell_w + x] = [0, 0, 0, 0]
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tex_w, tex_h, 0, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glBindTexture(GL_TEXTURE_2D, 0)
        return tex_id

    def resize(self, width, height):
        self.width = width
        self.height = height

    def update(self, auto_play=False):
        self.auto_play = auto_play

        # Build table content (3 rows x 4 columns)
        self.cells[0][0] = f"Level: {self.player.level}"
        self.cells[0][1] = f"Pos: ({self.player.position[0]:.1f}, {self.player.position[1]:.1f}, {self.player.position[2]:.1f})"
        self.cells[0][2] = f"Speed: {self.player.speed:.1f}"
        self.cells[0][3] = f"Life: {self.player.life}%"

        self.cells[1][0] = f"Mana: {self.player.mana}%"
        self.cells[1][1] = f"L: {self.player.lweapon.name} ({self.player.ammo_left if self.player.ammo_left >= 0 else '∞'})"
        self.cells[1][2] = f"R: {self.player.rweapon.name} ({self.player.ammo_right if self.player.ammo_right >= 0 else '∞'})"
        self.cells[1][3] = f"Kills: {self.player.killed_mobs}"

        self.cells[2][0] = f'{self.player.name} ({self.player.get_id()})'
        self.cells[2][1] = self.player.familiar_name
        self.cells[2][2] = f"Auto: {'ON' if auto_play else 'OFF'}"
        self.cells[2][3] = ""

    def draw(self):
        if not self.enabled:
            return
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        col_widths = [0] * self.cols
        scale = (self.row_height - 2 * self.cell_padding) / self.font_atlas.pixel_height
        for row in range(self.rows):
            for col in range(self.cols):
                text = self.cells[row][col]
                if not text:
                    continue
                text = str(text)
                width = 0
                for ch in text:
                    glyph = self.font_atlas.get_glyph(ch)
                    if glyph:
                        width += glyph[2] * scale
                width = max(width, 20)
                if width > col_widths[col]:
                    col_widths[col] = width
        for col in range(self.cols):
            col_widths[col] += 2 * self.cell_padding
        panel_w = sum(col_widths) + 2 * self.panel_margin
        panel_h = self.rows * self.row_height + 2 * self.panel_margin
        panel_y = self.height - panel_h - self.panel_margin
        panel_x = (self.width - panel_w) // 2   # center horizontally
        self.rect_shader.use()
        glUniform2f(self.rect_uScreenSize, self.width, self.height)
        glUniform4f(self.rect_uColor, 0.0, 0.0, 0.0, 0.6)
        self._draw_rect(panel_x, panel_y, panel_w, panel_h)
        self.text_shader.use()
        font_size = self.row_height - 2 * self.cell_padding
        glUniform1f(self.text_uSmoothing, 0.1 / (font_size / self.font_atlas.pixel_height))
        glUniform2f(self.text_uScreenSize, self.width, self.height)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.font_tex)
        glUniform1i(self.text_uFontTexture, 0)
        glUniform3f(self.text_uColor, 1.0, 1.0, 1.0)
        start_x = panel_x + self.panel_margin
        y = panel_y + self.panel_margin + self.cell_padding
        for row in range(self.rows):
            x = start_x
            for col in range(self.cols):
                text = self.cells[row][col]
                if text:
                    y_center = y + (self.row_height - font_size) // 2
                    self._draw_text(str(text), x + self.cell_padding, y_center, font_size)
                x += col_widths[col]
            y += self.row_height
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)

    def _draw_rect(self, x, y, w, h):
        y_bottom = self.height - (y + h)
        glUniform2f(self.rect_uOffset, x + w/2, y_bottom + h/2)
        glUniform2f(self.rect_uScale, w, h)
        glBindVertexArray(self.quad_vao)
        glDrawElements(GL_TRIANGLES, self.quad_index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def _draw_text(self, text, x, y, size, uppercase=False):
        glBindVertexArray(self.quad_vao)
        scale = size / self.font_atlas.pixel_height
        for i, ch in enumerate(text):
            code = ord(ch)
            if uppercase and 97 <= code <= 122:
                code -= 32
            ch_upper = chr(code)
            glyph = self.font_atlas.get_glyph(ch_upper)
            if glyph is None:
                continue
            gw, gh, advance, u0, v0, u1, v1 = glyph
            tex_rect = (u0, v0, u1 - u0, v1 - v0)
            glUniform4f(self.text_uTexRect, *tex_rect)
            pos_x = x + i * advance * scale
            quad_w = gw * scale
            quad_h = gh * scale
            y_bottom = self.height - (y + quad_h)
            glUniform2f(self.text_uOffset, pos_x + quad_w/2, y_bottom + quad_h/2)
            glUniform2f(self.text_uScale, quad_w, quad_h)
            glDrawElements(GL_TRIANGLES, self.quad_index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
