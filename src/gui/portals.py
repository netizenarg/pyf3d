import glfw
import numpy
import ctypes
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader

from gui.font import FONT_BITMAPS
from gui.widget import Widget
from shaders.shader import Shader
from shaders.gui_shdr import RECT_VERTEX_SHADER, RECT_FRAGMENT_SHADER, TEXT_VERTEX_SHADER, TEXT_FRAGMENT_SHADER


class DialogPortals:
    def __init__(self, window, screen_width, screen_height, player, camera):
        self.window = window
        self.width = screen_width
        self.height = screen_height
        self.player = player
        self.serializer = player.serializer
        self.camera = camera
        self.active = False
        self.scroll_offset = 0
        self.portals = []  # list of portal dicts from DB
        self.selected_index = -1

        # Panel dimensions
        self.panel_x = 100
        self.panel_y = 80
        self.panel_w = 400
        self.panel_h = 500
        self.title_height = 40
        self.item_height = 30
        self.bottom_margin = 60

        # Shaders
        self.rect_shader = compileProgram(
            compileShader(RECT_VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(RECT_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
        )
        self.text_shader = compileProgram(
            compileShader(TEXT_VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(TEXT_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
        )

        # Quad VAO (same as in settings)
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

        # Font texture (similar to settings)
        self.font_tex = self._create_font_texture()

        self._cache_uniforms()

    def _cache_uniforms(self):
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

    def _create_font_texture(self):
        # same as in settings.py
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

    def refresh_portals(self):
        self.portals = self.serializer.load_all_portals()
        self.selected_index = -1

    def open(self):
        self.refresh_portals()
        self.active = True
        glfw.set_input_mode(self.window, glfw.CURSOR, glfw.CURSOR_NORMAL)

    def close(self):
        self.active = False
        glfw.set_input_mode(self.window, glfw.CURSOR, glfw.CURSOR_DISABLED)

    def teleport_to_selected(self):
        if 0 <= self.selected_index < len(self.portals):
            p = self.portals[self.selected_index]
            # Teleport player
            self.player.position = (p['x'], p['y'], p['z'])
            self.camera.position = numpy.array([p['x'], p['y'], p['z']])
            self.camera.adjust_height()
            self.close()

    def handle_mouse(self, xpos, ypos, button):
        if not self.active:
            return False
        if button != glfw.MOUSE_BUTTON_LEFT:
            return False

        # Close button
        close_x = self.panel_x + self.panel_w - 40
        close_y = self.panel_y + 5
        if close_x <= xpos <= close_x + 30 and close_y <= ypos <= close_y + 30:
            self.close()
            return True

        # List items
        list_y_start = self.panel_y + self.title_height + 10
        visible_count = (self.panel_h - self.title_height - self.bottom_margin) // self.item_height
        for i in range(self.scroll_offset, min(self.scroll_offset + visible_count, len(self.portals))):
            item_y = list_y_start + (i - self.scroll_offset) * self.item_height
            if self.panel_x + 10 <= xpos <= self.panel_x + self.panel_w - 10 and item_y <= ypos <= item_y + self.item_height:
                self.selected_index = i
                return True

        # Teleport button
        btn_x = self.panel_x + 10
        btn_y = self.panel_y + self.panel_h - 40
        if btn_x <= xpos <= btn_x + 150 and btn_y <= ypos <= btn_y + 30:
            self.teleport_to_selected()
            return True

        return False

    def handle_scroll(self, xoffset, yoffset):
        if not self.active:
            return
        self.scroll_offset = max(0, min(self.scroll_offset - int(yoffset), max(0, len(self.portals) - 1)))

    def draw(self):
        if not self.active:
            return

        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Background panel
        glUseProgram(self.rect_shader)
        glUniform2f(self.rect_uScreenSize, self.width, self.height)
        self._draw_rect(self.panel_x, self.panel_y, self.panel_w, self.panel_h, (0.1,0.1,0.1,0.85))

        # Title bar
        self._draw_rect(self.panel_x, self.panel_y, self.panel_w, self.title_height, (0.3,0.3,0.3,0.9))
        self._draw_text("Portals", self.panel_x + 10, self.panel_y + (self.title_height-12)//2, 16, (1,1,1,1))

        # Close button
        close_x = self.panel_x + self.panel_w - 40
        close_y = self.panel_y + 5
        self._draw_rect(close_x, close_y, 30, 30, (0.8,0.2,0.2,0.9))
        self._draw_text("X", close_x + 9, close_y + 9, 14, (1,1,1,1))

        # Portal list
        list_y = self.panel_y + self.title_height + 10
        visible_count = (self.panel_h - self.title_height - self.bottom_margin) // self.item_height
        for i in range(self.scroll_offset, min(self.scroll_offset + visible_count, len(self.portals))):
            y = list_y + (i - self.scroll_offset) * self.item_height
            color = (0.5,0.7,1.0,0.8) if i == self.selected_index else (0.3,0.3,0.4,0.8)
            self._draw_rect(self.panel_x + 10, y, self.panel_w - 20, self.item_height - 2, color)
            p = self.portals[i]
            text = f"{p['name']}  ({p['x']:.1f}, {p['y']:.1f}, {p['z']:.1f})"
            self._draw_text(text, self.panel_x + 20, y + (self.item_height-12)//2, 12, (1,1,1,1))

        # Teleport button
        btn_x = self.panel_x + 10
        btn_y = self.panel_y + self.panel_h - 40
        self._draw_rect(btn_x, btn_y, 150, 30, (0.2,0.7,0.2,0.9))
        self._draw_text("Teleport", btn_x + 30, btn_y + 9, 14, (1,1,1,1))

        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)

    def _draw_rect(self, x, y, w, h, color):
        glUseProgram(self.rect_shader)
        glUniform2f(self.rect_uScreenSize, self.width, self.height)
        glUniform4f(self.rect_uColor, *color)
        y_bottom = self.height - (y + h)
        glUniform2f(self.rect_uOffset, x + w/2, y_bottom + h/2)
        glUniform2f(self.rect_uScale, w, h)
        glBindVertexArray(self.quad_vao)
        glDrawElements(GL_TRIANGLES, self.quad_index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def _draw_text(self, text, x, y, size, color=(1,1,1,1)):
        glUseProgram(self.text_shader)
        glUniform2f(self.text_uScreenSize, self.width, self.height)
        glUniform3f(self.text_uColor, color[0], color[1], color[2])
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.font_tex)
        glUniform1i(self.text_uFontTexture, 0)
        glBindVertexArray(self.quad_vao)

        for i, ch in enumerate(text):
            code = ord(ch)
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
