import logging

import glfw
import numpy
from OpenGL.GL import *

from shaders.shader import Shader
from shaders.gui_shdr import *
from gui.font import create_font_atlas

class ChatBox:
    def __init__(self, screen_width, screen_height, network_client=None, active=False):
        self.network_client = network_client
        self.active = active
        self.width = screen_width
        self.height = screen_height
        self.messages = []
        self.max_messages = 20
        self.input_active = False
        self.input_text = ""
        self.panel_width = 400
        self.panel_height = 200
        self.line_height = 20
        self.padding = 5
        self.font_size = 14
        self.input_active = False
        self.focus_captured = False

        self._init_graphics()
        self._relayout()

    def _init_graphics(self):
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

        self._cache_uniforms()

    def _cache_uniforms(self):
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
        self.text_uSmoothing = self.text_shader.getUniformLocation("uSmoothing")

    def _relayout(self):
        self.panel_x = self.padding
        self.panel_y = self.height - self.panel_height - self.padding
        self.input_y = self.panel_y + self.panel_height - self.line_height - self.padding
        self.text_area_height = self.panel_height - self.line_height - 2*self.padding

    def resize(self, width, height):
        self.width = width
        self.height = height
        self._relayout()

    def add_message(self, sender, message, timestamp=None):
        self.messages.append((sender, message, timestamp))
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)

    def set_focus_captured(self, captured):
        self.focus_captured = captured
        if not captured:
            self.input_active = False

    def handle_key(self, key, char):
        if not self.active:
            return False
        if key == glfw.KEY_ENTER:
            if self.input_active:
                self.send_message()
                self.input_active = False
                self.set_focus_captured(False)
                return True
            else:
                self.input_active = True
                self.set_focus_captured(True)
                return True
        if key == glfw.KEY_ESCAPE:
            if self.input_active:
                self.input_active = False
                self.set_focus_captured(False)
                return True
        if self.input_active:
            if key == glfw.KEY_BACKSPACE:
                self.input_text = self.input_text[:-1]
                return True
            elif char and 32 <= ord(char) <= 126:
                self.input_text += char
                return True
        return False

    def send_message(self):
        message = self.input_text.strip()
        if message:
            if self.network_client:
                self.network_client.send_chat_message(message)
            self.input_text = ""
        logging.debug(f"send message: {message}")

    def draw(self):
        if not self.active:
            return
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Background panel
        self.rect_shader.use()
        glUniform2f(self.rect_uScreenSize, self.width, self.height)
        self._draw_rect(self.panel_x, self.panel_y, self.panel_width, self.panel_height,
                        (0, 0, 0, 0.7))

        # Draw messages
        self.text_shader.use()
        glUniform1f(self.text_uSmoothing, 0.1 / (self.font_size / self.font_atlas.pixel_height))
        glUniform2f(self.text_uScreenSize, self.width, self.height)
        glUniform3f(self.text_uColor, 1, 1, 1)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.font_tex)
        glUniform1i(self.text_uFontTexture, 0)

        y = self.panel_y + self.panel_height - self.padding - self.font_size
        for sender, msg, _ in reversed(self.messages[-self.max_messages:]):
            text = f"{sender}: {msg}"
            self._draw_text(text, self.panel_x + self.padding, y, self.font_size, (1,1,1,1))
            y -= self.line_height

        # Input line
        input_rect_y = self.input_y
        self.rect_shader.use()
        self._draw_rect(self.panel_x, input_rect_y, self.panel_width, self.line_height,
                        (0.2, 0.2, 0.2, 0.9))
        self.text_shader.use()
        display = self.input_text + ("|" if self.input_active else "")
        self._draw_text(display, self.panel_x + self.padding, input_rect_y + 3,
                        self.font_size, (1,1,1,1))

        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)

    def _draw_rect(self, x, y, w, h, color):
        glUniform4f(self.rect_uColor, *color)
        y_bottom = self.height - (y + h)
        glUniform2f(self.rect_uOffset, x + w/2, y_bottom + h/2)
        glUniform2f(self.rect_uScale, w, h)
        glBindVertexArray(self.quad_vao)
        glDrawElements(GL_TRIANGLES, self.quad_index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def _draw_text(self, text, x, y, size, color):
        glUniform3f(self.text_uColor, color[0], color[1], color[2])
        glBindVertexArray(self.quad_vao)
        scale = size / self.font_atlas.pixel_height
        for i, ch in enumerate(text):
            glyph = self.font_atlas.get_glyph(ch)
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
