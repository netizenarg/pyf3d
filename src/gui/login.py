# login.py
import ctypes
import glfw
import numpy
from OpenGL.GL import *

from logger import logging
from shaders.shader import Shader
from shaders.gui_shdr import RECT_VERTEX_SHADER, RECT_FRAGMENT_SHADER, TEXT_VERTEX_SHADER, TEXT_FRAGMENT_SHADER
from gui.font import create_font_atlas
from gui.widget import Widget
from gui.textbox import TextBox


def show_login_dialog(window, width, height, login: str = "", password: str = ""):
    login_dialog = LoginDialog(width, height, login, password)
    login_dialog.show()
    login_completed = False
    login_result = None
    def on_login(login, password):
        nonlocal login_completed, login_result
        login_completed = True
        login_result = (login, password) if login is not None else None
    login_dialog.callback = on_login
    drawer = LoginDrawer(width, height)
    def login_key_callback(win, key, scancode, action, mods):
        if action in (glfw.PRESS, glfw.RELEASE):
            login_dialog.handle_key(key, '', None)
    def login_char_callback(win, codepoint):
        login_dialog.handle_key(0, chr(codepoint), None)
    def login_mouse_callback(win, button, action, mods):
        if action == glfw.PRESS:
            x, y = glfw.get_cursor_pos(win)
            login_dialog.handle_mouse(x, y, button, None)
    def login_cursor_callback(win, x, y):
        pass
    glfw.set_key_callback(window, login_key_callback)
    glfw.set_char_callback(window, login_char_callback)
    glfw.set_mouse_button_callback(window, login_mouse_callback)
    glfw.set_cursor_pos_callback(window, login_cursor_callback)
    glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_NORMAL)
    while not login_completed and not glfw.window_should_close(window):
        glfw.poll_events()
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        login_dialog.draw(drawer)
        glfw.swap_buffers(window)
    return login_result


class LoginDrawer:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.use_shaders = True
        try:
            self.rect_shader = Shader(RECT_VERTEX_SHADER, RECT_FRAGMENT_SHADER)
            self.text_shader = Shader(TEXT_VERTEX_SHADER, TEXT_FRAGMENT_SHADER)
            quad_verts = numpy.array([-0.5,-0.5,0,0, 0.5,-0.5,1,0, 0.5,0.5,1,1, -0.5,0.5,0,1], dtype=numpy.float32)
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
            self.font_atlas = create_font_atlas(16)
            self.font_tex = self.font_atlas.tex_id
            self.text_uSmoothing = self.text_shader.getUniformLocation("uSmoothing")
        except Exception as err:
            logging.error(f"Shader compilation failed, using fallback: {err}")
            self.use_shaders = False
            self.font_atlas = None
            self.font_tex = self._create_fallback_texture()

    def _create_fallback_texture(self):
        cols, rows = 16, 8
        cell_w, cell_h = 8, 8
        tex_w, tex_h = cols*cell_w, rows*cell_h
        data = numpy.zeros((tex_h, tex_w, 4), dtype=numpy.uint8)
        from gui.fontdata import FONT_BITMAPS
        for code in range(32,128):
            row = (code-32)//cols
            col = (code-32)%cols
            bitmap = FONT_BITMAPS.get(code, [0]*8)
            for y in range(cell_h):
                bits = bitmap[y] if y<len(bitmap) else 0
                for x in range(cell_w):
                    if (bits>>(7-x))&1:
                        data[row*cell_h+y, col*cell_w+x] = [255,255,255,255]
        tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tex_w, tex_h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        return tex

    def _draw_rect(self, x, y, w, h, color):
        if self.use_shaders:
            self.rect_shader.use()
            glUniform2f(self.rect_shader.getUniformLocation("uScreenSize"), self.width, self.height)
            glUniform4f(self.rect_shader.getUniformLocation("uColor"), *color)
            y_bottom = self.height - (y + h)
            glUniform2f(self.rect_shader.getUniformLocation("uOffset"), x + w/2, y_bottom + h/2)
            glUniform2f(self.rect_shader.getUniformLocation("uScale"), w, h)
            glBindVertexArray(self.quad_vao)
            glDrawElements(GL_TRIANGLES, self.quad_index_count, GL_UNSIGNED_INT, None)
        else:
            glDisable(GL_TEXTURE_2D)
            glBegin(GL_QUADS)
            glColor4f(*color)
            glVertex2f(x, y)
            glVertex2f(x + w, y)
            glVertex2f(x + w, y + h)
            glVertex2f(x, y + h)
            glEnd()
            glEnable(GL_TEXTURE_2D)

    def _draw_text(self, text, x, y, size, color=(1,1,1,1), uppercase=False):
        if self.use_shaders:
            self.text_shader.use()
            glUniform1f(self.text_uSmoothing, 0.1 / (size / self.font_atlas.pixel_height))
            glUniform2f(self.text_shader.getUniformLocation("uScreenSize"), self.width, self.height)
            glUniform3f(self.text_shader.getUniformLocation("uColor"), color[0], color[1], color[2])
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, self.font_tex)
            glUniform1i(self.text_shader.getUniformLocation("uFontTexture"), 0)
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
                glUniform4f(self.text_shader.getUniformLocation("uTexRect"), *tex_rect)
                pos_x = x + i * advance * scale
                quad_w = gw * scale
                quad_h = gh * scale
                y_bottom = self.height - (y + quad_h)
                glUniform2f(self.text_shader.getUniformLocation("uOffset"), pos_x + quad_w/2, y_bottom + quad_h/2)
                glUniform2f(self.text_shader.getUniformLocation("uScale"), quad_w, quad_h)
                glDrawElements(GL_TRIANGLES, self.quad_index_count, GL_UNSIGNED_INT, None)
            glBindVertexArray(0)
        else:
            logging.warning("Text rendering not available in fallback mode")

class LoginDialog(Widget):
    def __init__(self, screen_width, screen_height, default_login="", default_password="", callback=None):
        super().__init__(0, 0, 400, 250)
        self.width = 400
        self.height = 250
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.default_login = default_login
        self.default_password = default_password
        self.active = False
        self.callback = callback
        self.login_input = None
        self.password_input = None
        self._init_widgets()

    def _init_widgets(self):
        self.login_input = TextBox("Login", "login", 0, 0, 0, 0, label_width=80)
        self.password_input = TextBox("Password", "password", 0, 0, 0, 0, label_width=80)
        self.login_input.text = self.default_login
        self.password_input.text = self.default_password

    def show(self):
        self.active = True
        self.x = (self.screen_width - self.width) // 2
        self.y = (self.screen_height - self.height) // 2
        self.rect = (self.x, self.y, self.width, self.height)
        self.login_input.rect = (self.x + 20, self.y + 60, self.width - 40, 30)
        self.password_input.rect = (self.x + 20, self.y + 110, self.width - 40, 30)
        self.login_input.active = True
        self.password_input.active = False

    def close(self):
        self.active = False

    def handle_key(self, key, char, dialog):
        if not self.active:
            return False
        if self.login_input.active:
            return self.login_input.handle_key(key, char)
        if self.password_input.active:
            return self.password_input.handle_key(key, char)
        if key == 257 or key == 335:
            self._submit()
            return True
        return False

    def handle_mouse(self, x, y, button, dialog):
        if not self.active or button != glfw.MOUSE_BUTTON_LEFT:
            return False
        ok_x = self.x + self.width - 90
        ok_y = self.y + self.height - 50
        ok_w = 80
        ok_h = 30
        if ok_x <= x <= ok_x + ok_w and ok_y <= y <= ok_y + ok_h:
            self._submit()
            return True
        cancel_x = self.x + 10
        if cancel_x <= x <= cancel_x + ok_w and ok_y <= y <= ok_y + ok_h:
            self.close()
            if self.callback:
                self.callback(None, None)
            return True
        if self.login_input.handle_mouse(x, y, None):
            self.login_input.active = True
            self.password_input.active = False
            return True
        if self.password_input.handle_mouse(x, y, None):
            self.password_input.active = True
            self.login_input.active = False
            return True
        return False

    def _submit(self):
        login = self.login_input.text
        password = self.password_input.text
        self.close()
        if self.callback:
            self.callback(login, password)

    def draw(self, dialog):
        if not self.active:
            return
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        dialog._draw_rect(0, 0, dialog.width, dialog.height, (0, 0, 0, 0.5))
        dialog._draw_rect(self.x, self.y, self.width, self.height, (0.2, 0.2, 0.2, 0.95))
        dialog._draw_rect(self.x, self.y, self.width, 40, (0.3, 0.3, 0.3, 0.95))
        dialog._draw_text("Login", self.x + 20, self.y + 12, 16, (1,1,1,1))
        self.login_input.draw(dialog)
        self.password_input.draw(dialog)
        button_w = 80
        button_h = 30
        button_y = self.y + self.height - button_h - 20
        cancel_x = self.x + 10
        dialog._draw_rect(cancel_x, button_y, button_w, button_h, (0.5, 0.5, 0.5, 0.9))
        dialog._draw_text("Cancel", cancel_x + 20, button_y + 8, 12, (1,1,1,1))
        ok_x = self.x + self.width - button_w - 10
        dialog._draw_rect(ok_x, button_y, button_w, button_h, (0.2, 0.6, 0.2, 0.9))
        dialog._draw_text("OK", ok_x + 30, button_y + 8, 12, (1,1,1,1))
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)
