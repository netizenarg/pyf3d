import numpy
import ctypes
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader
import glfw

from gui_shaders import *
from font import FONT_BITMAPS

# Ensure Q is exactly 8 rows
if 81 in FONT_BITMAPS and len(FONT_BITMAPS[81]) < 8:
    FONT_BITMAPS[81] += [0x00] * (8 - len(FONT_BITMAPS[81]))

class Menu:
    def __init__(self, screen_width, screen_height, config, camera):
        self.width = screen_width
        self.height = screen_height
        self.config = config
        self.camera = camera
        self.active = False

        # Layout
        self.panel_x = 50
        self.panel_y = 50
        self.panel_w = 400
        self.panel_h = 250
        self.button_h = 30
        self.button_spacing = 10

        y = self.panel_y + self.panel_h - 40
        self.settings = [
            ("Mouse Sens", "mouse_sensitivity", self.panel_x + 10, y, 200, self.button_h,
             lambda: self.change_setting("mouse_sensitivity", 0.1),
             lambda: self.change_setting("mouse_sensitivity", -0.1)),
            ("Move Speed", "movement_speed", self.panel_x + 10, y - self.button_h - self.button_spacing, 200, self.button_h,
             lambda: self.change_setting("movement_speed", 1.0),
             lambda: self.change_setting("movement_speed", -1.0)),
            ("Player Height", "player_height", self.panel_x + 10, y - 2*(self.button_h + self.button_spacing), 200, self.button_h,
             lambda: self.change_setting("player_height", 0.1),
             lambda: self.change_setting("player_height", -0.1)),
        ]
        self.save_button = (self.panel_x + 10, y - 3*(self.button_h + self.button_spacing), 150, self.button_h, self.close)

        self.buttons = []
        self.init_ui()

        # Shaders
        self.rect_shader = compileProgram(
            compileShader(RECT_VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(RECT_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
        )
        self.text_shader = compileProgram(
            compileShader(TEXT_VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(TEXT_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
        )

        # Common quad VAO (position + texcoord) – triangle strip order
        quad_verts = numpy.array([
            -0.5, -0.5,  0.0, 0.0,
             0.5, -0.5,  1.0, 0.0,
             0.5,  0.5,  1.0, 1.0,
            -0.5,  0.5,  0.0, 1.0,
        ], dtype=numpy.float32)
        self.quad_vao = glGenVertexArrays(1)
        self.quad_vbo = glGenBuffers(1)
        glBindVertexArray(self.quad_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.quad_vbo)
        glBufferData(GL_ARRAY_BUFFER, quad_verts.nbytes, quad_verts, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(8))
        glEnableVertexAttribArray(1)
        glBindVertexArray(0)

        # Font texture
        self.font_tex = self._create_font_texture()

        # Cache uniform locations
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

    def init_ui(self):
        for label, key, x, y, w, h, inc_action, dec_action in self.settings:
            inc_rect = (x + w - 50, y, 25, h)
            dec_rect = (x + w - 25, y, 25, h)
            self.buttons.append((inc_rect, inc_action))
            self.buttons.append((dec_rect, dec_action))
        x, y, w, h, action = self.save_button
        self.buttons.append(((x, y, w, h), action))

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

    def change_setting(self, key, delta):
        new_val = self.config[key] + delta
        if key == "mouse_sensitivity":
            new_val = max(0.1, min(10.0, new_val))
        elif key == "movement_speed":
            new_val = max(1.0, min(50.0, new_val))
        elif key == "player_height":
            new_val = max(0.5, min(5.0, new_val))
        self.config[key] = new_val
        if key == "mouse_sensitivity":
            self.camera.mouse_sensitivity = new_val
        elif key == "movement_speed":
            self.camera.movement_speed = new_val
        elif key == "player_height":
            self.camera.player_height = new_val
            self.camera.adjust_height()
        print(f"{key} now: {new_val}")

    def close(self):
        import config
        config.Config.save(self.config)
        self.active = False

    def handle_mouse(self, xpos, ypos, button):
        if not self.active or button != glfw.MOUSE_BUTTON_LEFT:
            return False
        y = self.height - ypos
        for (x, yb, w, h), action in self.buttons:
            if x <= xpos <= x + w and yb <= y <= yb + h:
                action()
                return True
        return False

    def draw(self):
        if not self.active:
            return

        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Draw rectangles
        glUseProgram(self.rect_shader)
        glUniform2f(self.rect_uScreenSize, self.width, self.height)

        # Background panel
        glUniform4f(self.rect_uColor, 0.2, 0.2, 0.2, 0.8)
        self._draw_rect(self.panel_x, self.panel_y, self.panel_w, self.panel_h)

        # Setting backgrounds
        for label, key, x, y, w, h, inc_action, dec_action in self.settings:
            glUniform4f(self.rect_uColor, 0.5, 0.5, 0.5, 0.9)
            self._draw_rect(x, y, w, h)

        # Save button background
        x, y, w, h, _ = self.save_button
        glUniform4f(self.rect_uColor, 0.5, 0.5, 0.5, 0.9)
        self._draw_rect(x, y, w, h)

        # Draw text
        glUseProgram(self.text_shader)
        glUniform2f(self.text_uScreenSize, self.width, self.height)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.font_tex)
        glUniform1i(self.text_uFontTexture, 0)
        glUniform3f(self.text_uColor, 1.0, 1.0, 1.0)

        char_size = 12
        off_x = 5
        off_y = 8

        for label, key, x, y, w, h, inc_action, dec_action in self.settings:
            self._draw_text(label, x + off_x, y + h - off_y, char_size)
            val_str = f"{self.config[key]:.1f}"
            self._draw_text(val_str, x + w - 80, y + h - off_y, char_size)
            self._draw_text("+", x + w - 50, y + h - off_y, char_size)
            self._draw_text("-", x + w - 25, y + h - off_y, char_size)

        sx, sy, sw, sh, _ = self.save_button
        self._draw_text("Save", sx + sw//2 - 25, sy + sh - off_y, char_size)

        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)

    def _draw_rect(self, x, y, w, h):
        glUniform2f(self.rect_uOffset, x + w/2, y + h/2)
        glUniform2f(self.rect_uScale, w, h)
        glBindVertexArray(self.quad_vao)
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        glBindVertexArray(0)

    def _draw_text(self, text, x, y, size):
        glBindVertexArray(self.quad_vao)
        for i, ch in enumerate(text):
            code = ord(ch)
            if code < 32 or code > 127:
                continue
            idx = code - 32
            cols = 16
            rows = 8
            cell_w = 8
            cell_h = 8
            row = idx // cols
            col = idx % cols
            # Texture coordinates of the character in the atlas
            u0 = col / cols
            v0 = row / rows
            u1 = (col + 1) / cols
            v1 = (row + 1) / rows
            tex_rect = (u0, v0, u1 - u0, v1 - v0)
            glUniform4f(self.text_uTexRect, *tex_rect)

            pos_x = x + i * size
            pos_y = y
            glUniform2f(self.text_uOffset, pos_x + size/2, pos_y + size/2)
            glUniform2f(self.text_uScale, size, size)
            glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        glBindVertexArray(0)
