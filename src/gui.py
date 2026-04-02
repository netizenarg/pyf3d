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

        # Layout – all y‑coordinates are top‑origin (0 = top)
        self.panel_x = 50
        self.panel_y = 50                     # top edge of panel
        self.panel_w = 500
        self.panel_h = 250
        self.button_h = 30
        self.button_spacing = 15

        # Title bar occupies the top 40 pixels of the panel
        title_height = 40
        self.title_bar_y = self.panel_y         # top edge of title bar
        self.title_text = "Settings"

        # Close button (X) in top‑right corner of title bar
        close_size = 30
        self.close_button = (self.panel_x + self.panel_w - close_size - 10,
                             self.panel_y + (title_height - close_size) // 2,
                             close_size, close_size,
                             self.close)

        # First setting row starts 10 pixels below title bar
        start_y = self.panel_y + title_height + 10

        self.settings = [
            ("Mouse Sens", "mouse_sensitivity", self.panel_x + 10, start_y, 350, self.button_h,
             lambda: self.change_setting("mouse_sensitivity", 0.1),
             lambda: self.change_setting("mouse_sensitivity", -0.1)),
            ("Move Speed", "movement_speed", self.panel_x + 10, start_y + self.button_h + self.button_spacing, 350, self.button_h,
             lambda: self.change_setting("movement_speed", 1.0),
             lambda: self.change_setting("movement_speed", -1.0)),
            ("Player Height", "player_height", self.panel_x + 10, start_y + 2*(self.button_h + self.button_spacing), 350, self.button_h,
             lambda: self.change_setting("player_height", 0.1),
             lambda: self.change_setting("player_height", -0.1)),
        ]
        # Save button below the last setting
        self.save_button = (self.panel_x + 10,
                            start_y + 3*(self.button_h + self.button_spacing) + 10,
                            150, self.button_h,
                            self.close)

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

        # Common quad VAO (position + texcoord) – with indices for GL_TRIANGLES
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

    def resize(self, width, height):
        self.width = width
        self.height = height

    def init_ui(self):
        # Add close button
        self.buttons.append(((self.close_button[0], self.close_button[1],
                              self.close_button[2], self.close_button[3]),
                             self.close_button[4]))
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
            self.camera.player.height = new_val
            self.camera.adjust_height()
        print(f"Clicked {key} +/- : new value = {new_val}")

    def close(self):
        import config
        config.Config.save(self.config)
        self.active = False
        print("Menu closed, settings saved.")

    def handle_mouse(self, xpos, ypos, button):
        if not self.active or button != glfw.MOUSE_BUTTON_LEFT:
            return False
        # ypos is already top-origin (0 at top)
        for (x, y, w, h), action in self.buttons:
            if x <= xpos <= x + w and y <= ypos <= y + h:
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

        # Title bar background
        title_height = 40
        glUniform4f(self.rect_uColor, 0.3, 0.3, 0.3, 0.9)
        self._draw_rect(self.panel_x, self.panel_y, self.panel_w, title_height)

        # Close button background
        cx, cy, cw, ch, _ = self.close_button
        glUniform4f(self.rect_uColor, 0.6, 0.2, 0.2, 0.9)
        self._draw_rect(cx, cy, cw, ch)

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

        # Title text (centered in title bar)
        title_width = len(self.title_text) * char_size
        title_x = self.panel_x + (self.panel_w - title_width) // 2
        title_center_y = self.panel_y + (title_height - char_size) // 2
        self._draw_text(self.title_text, title_x, title_center_y, char_size, uppercase=True)

        for label, key, x, y, w, h, inc_action, dec_action in self.settings:
            y_center = y + (h - char_size) // 2
            self._draw_text(label, x + 5, y_center, char_size, uppercase=True)
            val_str = f"{self.config[key]:.1f}"
            self._draw_text(val_str, x + w - 110, y_center, char_size, uppercase=False)
            self._draw_text("+", x + w - 55, y_center, char_size, uppercase=False)
            self._draw_text("-", x + w - 30, y_center, char_size, uppercase=False)

        # Close button text (X)
        cx, cy, cw, ch, _ = self.close_button
        y_center = cy + (ch - char_size) // 2
        self._draw_text("X", cx + (cw - char_size) // 2, y_center, char_size, uppercase=True)

        # Save button text
        sx, sy, sw, sh, _ = self.save_button
        y_center = sy + (sh - char_size) // 2
        save_text = "Save"
        text_width = len(save_text) * char_size
        self._draw_text(save_text, sx + (sw - text_width) // 2, y_center, char_size, uppercase=True)

        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)

    def _draw_rect(self, x, y, w, h):
        """Draw rectangle with top‑origin coordinates (0 = top)."""
        # Convert to bottom‑origin for OpenGL
        y_bottom = self.height - (y + h)
        glUniform2f(self.rect_uOffset, x + w/2, y_bottom + h/2)
        glUniform2f(self.rect_uScale, w, h)
        glBindVertexArray(self.quad_vao)
        glDrawElements(GL_TRIANGLES, self.quad_index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def _draw_text(self, text, x, y, size, uppercase=True):
        """Draw text with top‑origin coordinates (0 = top). y is the baseline (center of characters)."""
        glBindVertexArray(self.quad_vao)
        for i, ch in enumerate(text):
            code = ord(ch)
            if uppercase and 97 <= code <= 122:
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
            # Convert y from top‑origin to bottom‑origin and compute center
            y_center = self.height - (y + size/2)
            glUniform2f(self.text_uOffset, pos_x + size/2, y_center)
            glUniform2f(self.text_uScale, size, size)
            glDrawElements(GL_TRIANGLES, self.quad_index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
