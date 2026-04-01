import numpy
import ctypes
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader
from gui_shaders import *
from font import FONT_BITMAPS

class StatsPanel:
    def __init__(self, screen_width, screen_height, enabled=True):
        self.enabled = enabled
        self.width = screen_width
        self.height = screen_height
        self.panel_margin = 10
        self.char_size = 8                      # reduced font size
        self.padding = 10
        self.cell_padding = 8                   # padding inside each cell
        self.row_height = self.char_size + self.cell_padding * 2
        self.rows = 3
        self.cols = 4

        # Shaders
        self.rect_shader = compileProgram(
            compileShader(RECT_VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(RECT_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
        )
        self.text_shader = compileProgram(
            compileShader(TEXT_VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(TEXT_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
        )

        # Quad VAO
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
        self.rect_uScreenSize = glGetUniformLocation(self.rect_shader, "uScreenSize")
        self.rect_uColor = glGetUniformLocation(self.rect_shader, "uColor")
        self.rect_uOffset = glGetUniformLocation(self.rect_shader, "uOffset")
        self.rect_uScale = glGetUniformLocation(self.rect_shader, "uScale")

        self.text_uScreenSize = glGetUniformLocation(self.text_shader, "uScreenSize")
        self.text_uColor = glGetUniformLocation(self.text_shader, "uColor")
        self.text_uOffset = glGetUniformLocation(self.text_shader, "uOffset")
        self.text_uScale = glGetUniformLocation(self.text_shader, "uScale")
        self.text_uTexRect = glGetUniformLocation(self.text_shader, "uTexRect")
        self.text_uFontTexture = glGetUniformLocation(self.text_shader, "uFontTexture")

        # Data
        self.position = (0, 0, 0)
        self.speed = 0.0
        self.life_percent = 100.0
        self.mana_percent = 100.0
        self.weapon_name = "Rifle"
        self.ammo_count = 100
        self.familiar_name = ""

        # Table content – 3 rows x 4 columns
        self.cells = [[""] * self.cols for _ in range(self.rows)]

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

    def update(self, position, speed, life_percent, mana_percent, weapon_name, ammo_count, familiar_name):
        self.position = position
        self.speed = speed
        self.life_percent = life_percent
        self.mana_percent = mana_percent
        self.weapon_name = weapon_name
        self.ammo_count = ammo_count
        self.familiar_name = familiar_name

        # Build table content
        # Row 0: Pos, Speed, Life, Mana
        self.cells[0][0] = f"Pos: ({position[0]:.1f}, {position[1]:.1f}, {position[2]:.1f})"
        self.cells[0][1] = f"Speed: {speed:.1f}"
        self.cells[0][2] = f"Life: {life_percent:.0f}%"
        self.cells[0][3] = f"Mana: {mana_percent:.0f}%"

        # Row 1: Weapon (value only), Ammo, Familiar (value only), empty
        self.cells[1][0] = weapon_name          # no label for strings
        self.cells[1][1] = f"Ammo: {ammo_count:.0f}"
        self.cells[1][2] = familiar_name
        self.cells[1][3] = ""

        # Row 2: empty for now (can be used for extra stats)
        self.cells[2][0] = ""
        self.cells[2][1] = ""
        self.cells[2][2] = ""
        self.cells[2][3] = ""

    def draw(self):
        if not self.enabled:
            return

        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Compute column widths based on maximum text width per column
        col_widths = [0] * self.cols
        for row in range(self.rows):
            for col in range(self.cols):
                text = self.cells[row][col]
                width = len(text) * self.char_size
                if width > col_widths[col]:
                    col_widths[col] = width

        # Add cell padding to column widths
        for col in range(self.cols):
            col_widths[col] += 2 * self.cell_padding

        # Total panel width = sum(col_widths) + 2*margin
        panel_w = sum(col_widths) + 2 * self.panel_margin
        panel_h = self.rows * self.row_height + 2 * self.panel_margin
        panel_y = self.height - panel_h - self.panel_margin
        panel_x = (self.width - panel_w) // 2   # center horizontally

        # Draw background panel
        glUseProgram(self.rect_shader)
        glUniform2f(self.rect_uScreenSize, self.width, self.height)
        glUniform4f(self.rect_uColor, 0.0, 0.0, 0.0, 0.6)
        self._draw_rect(panel_x, panel_y, panel_w, panel_h)

        # Draw table
        glUseProgram(self.text_shader)
        glUniform2f(self.text_uScreenSize, self.width, self.height)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.font_tex)
        glUniform1i(self.text_uFontTexture, 0)
        glUniform3f(self.text_uColor, 1.0, 1.0, 1.0)

        # Starting x for columns
        start_x = panel_x + self.panel_margin
        y = panel_y + self.panel_margin + self.cell_padding

        for row in range(self.rows):
            x = start_x
            for col in range(self.cols):
                text = self.cells[row][col]
                if text:
                    y_center = y + self.row_height // 2 - self.char_size // 2
                    self._draw_text(text, x + self.cell_padding, y_center, self.char_size, uppercase=True)
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

    def _draw_text(self, text, x, y, size, uppercase=True):
        glBindVertexArray(self.quad_vao)
        for i, ch in enumerate(text):
            code = ord(ch)
            if uppercase and 97 <= code <= 122:   # a-z -> A-Z
                code -= 32
            if code < 32 or code > 127:
                continue
            idx = code - 32
            cols = 16
            rows = 8
            row = idx // cols
            col = idx % cols
            u0 = col / cols
            v0 = row / rows
            u1 = (col + 1) / cols
            v1 = (row + 1) / rows
            tex_rect = (u0, v0, u1 - u0, v1 - v0)
            glUniform4f(self.text_uTexRect, *tex_rect)
            pos_x = x + i * size
            y_center = self.height - (y + size/2)
            glUniform2f(self.text_uOffset, pos_x + size/2, y_center)
            glUniform2f(self.text_uScale, size, size)
            glDrawElements(GL_TRIANGLES, self.quad_index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
