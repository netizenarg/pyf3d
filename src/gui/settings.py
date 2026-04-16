import logging
import numpy
import ctypes
import glfw

from OpenGL.GL import *

import config
from shaders.shader import Shader
from shaders.gui_shdr import *
from gui.font import FONT_BITMAPS
from gui.widget import Widget
from gui.label import Label
from gui.checkbox import CheckBox
from gui.numberbox import NumberBox
from gui.dropdown import Dropdown
from gui.tabs import Tab


# Server URL dropdown
SERVER_URL_OPTIONS = [
    ("Local (8080)", "http://localhost:8080"),
    ("Local (9999)", "localhost:9999"),
    ("Official Server", "https://game.example.com"),
    ("Custom (edit config)", "")
]

# Protocol options
PROTOCOL_OPTIONS = [
    ("Binary (recommended)", "binary"),
    ("WebSocket (JSON)", "websocket"),
]


class DialogSettings(Widget):
    def __init__(self, window, screen_width, screen_height, config_dict, camera, player=None,
                 stats_panel=None, fps_overlay=None, compass=None, player_ai=None):
        self.window = window
        self.width = screen_width
        self.height = screen_height
        self.config = config_dict
        self.camera = camera
        self.player = player
        self.stats_panel = stats_panel
        self.fps_overlay = fps_overlay
        self.compass = compass
        self.player_ai = player_ai
        self.active = False
        self.active_tab_index = 0

        # Panel dimensions
        self.panel_x = 50
        self.panel_y = 50
        self.panel_w = 550
        self.panel_h = 400
        self.title_height = 40
        self.tab_header_height = 30
        self.bottom_margin = 60   # space for Save button

        # Title and close button
        self.title_text = "Settings"
        close_size = 30
        self.close_button = (
            self.panel_x + self.panel_w - close_size - 10,
            self.panel_y + (self.title_height - close_size) // 2,
            close_size, close_size,
            self.close
        )

        # Save button
        self.save_button = (
            self.panel_x + 10,
            self.panel_y + self.panel_h - 40,
            150, 30,
            self.save
        )

        # Build tabs and widgets
        self.tabs = []
        self._build_tabs()

        # Set current server URL in dropdown and protocol
        current_url = self.config.get("server_url", "http://localhost:8080")
        current_protocol = self.config.get("protocol", "binary")
        for tab in self.tabs:
            if tab.name == "Network":
                for widget in tab.widgets:
                    if isinstance(widget, Dropdown) and widget.key == "server_url":
                        widget.set_value(current_url)
                    elif isinstance(widget, Dropdown) and widget.key == "protocol":
                        widget.set_value(current_protocol)

        # Shaders and common geometry
        self.rect_shader = Shader(RECT_VERTEX_SHADER, RECT_FRAGMENT_SHADER)
        self.text_shader = Shader(TEXT_VERTEX_SHADER, TEXT_FRAGMENT_SHADER)

        # Common quad VAO (position + texcoord) with indices
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

        # Initial layout
        self._relayout()

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

    def _build_tabs(self):
        # Helper callbacks
        def update_mouse_sens(val):
            self.camera.mouse_sensitivity = val
        def update_move_speed(val):
            self.camera.movement_speed = val
        def update_player_height(val):
            if self.player:
                self.player.height = val
                self.camera.adjust_height()
        def update_show_fps(val):
            if self.fps_overlay:
                self.fps_overlay.enabled = val
            self.config["show_fps"] = val
        def update_draw_stats(val):
            if self.stats_panel:
                self.stats_panel.enabled = val
        def update_draw_compass(val):
            if self.compass:
                self.compass.enabled = val
        def update_draw_fog(val):
            # fog handled in main loop via config
            pass
        def update_snow_draw(val):
            # handled by sky; can be updated on next frame
            pass
        def update_camera_mode(val):
            # val is bool: True = third person (mode 1), False = first person (mode 0)
            new_mode = 1 if val else 0
            if self.camera:
                self.camera.set_mode(new_mode)
            self.config["camera_mode"] = new_mode

        # ---- Core tab ----
        core = Tab("Core")
        core.add_widget(NumberBox("Mouse Sens", "mouse_sensitivity", 0,0,0,0,
                                       0.1, 10.0, 0.1, update_mouse_sens))
        core.add_widget(NumberBox("Move Speed", "movement_speed", 0,0,0,0,
                                       1.0, 50.0, 1.0, update_move_speed))
        core.add_widget(NumberBox("Player Height", "player_height", 0,0,0,0,
                                       0.5, 5.0, 0.1, update_player_height))
        core.add_widget(CheckBox("Show FPS", "show_fps", 0,0,20,20, update_show_fps))
        core.add_widget(CheckBox("Draw Stats", "draw_stats", 0,0,20,20, update_draw_stats))
        core.add_widget(CheckBox("Draw Compass", "draw_compass", 0,0,20,20, update_draw_compass))
        core.add_widget(CheckBox("Draw Fog", "draw_fog", 0,0,20,20, update_draw_fog))
        core.add_widget(CheckBox("Snow Draw", "snow_draw", 0,0,20,20, update_snow_draw))

        # Load radius (1..5)
        def on_load_radius_change(val):
            self.config["load_radius"] = int(val)
            # No live update – requires restart
            logging.info(f"Load radius changed to {val}. Restart required for full effect.")

        core.add_widget(NumberBox("Load Radius", "load_radius", 0,0,0,0,
                                    1, 5, 1, on_load_radius_change))

        self.tabs.append(core)

        # ---- Player tab ----
        player_tab = Tab("Player")
        player_tab.add_widget(CheckBox("Third Person", "camera_mode", 0,0,20,20, update_camera_mode))
        def update_auto_play(val):
            if self.player_ai:
                self.player_ai.set_enabled(val)
                self.config["auto_play"] = val
                config.Config.save(self.config)
            else:
                logging.warning("player_ai not available")
        player_tab.add_widget(CheckBox("Auto Play", "auto_play", 0,0,20,20, update_auto_play))
        self.tabs.append(player_tab)

        # ---- Network tab ----
        net_tab = Tab("Network")

        def update_network_mode(value):
            self.config["network_mode"] = value
            logging.info(f"Network mode changed to '{value}' – restart required for full effect")

        net_tab.add_widget(CheckBox("Network Mode", "network_mode", 0,0,20,20, update_network_mode))

        def on_server_url_change(value):
            if value:
                self.config["server_url"] = value
                logging.info(f"Server URL changed to {value}. Restart required.")

        server_dropdown = Dropdown("Server URL", "server_url", 0,0,0,0,
                                SERVER_URL_OPTIONS, on_server_url_change)
        net_tab.add_widget(server_dropdown)

        # Protocol dropdown
        def on_protocol_change(value):
            self.config["protocol"] = value
            logging.info(f"Protocol changed to '{value}'. Restart required.")

        protocol_dropdown = Dropdown("Protocol", "protocol", 0, 0, 0, 0,
                                     PROTOCOL_OPTIONS, on_protocol_change)
        net_tab.add_widget(protocol_dropdown)

        # Show current URL and protocol as read-only labels
        def get_current_url():
            return self.config.get("server_url", "unknown")
        net_tab.add_widget(Label("Current URL", "current_url", 0,0,0,0, getter=get_current_url))

        def get_current_protocol():
            return self.config.get("protocol", "binary")
        net_tab.add_widget(Label("Current Protocol", "current_protocol", 0,0,0,0,
                                 getter=get_current_protocol))

        self.tabs.append(net_tab)

    def _relayout(self):
        """Compute positions of all UI elements after a resize."""
        # Content area below title and tab headers
        content_y = self.panel_y + self.title_height + self.tab_header_height + 10
        content_h = self.panel_h - self.title_height - self.tab_header_height - self.bottom_margin
        # Each widget row height
        row_h = 30
        spacing = 5
        # Layout each tab's widgets in the content area
        for tab in self.tabs:
            tab.layout(self.panel_x + 10, content_y, self.panel_w - 20, row_h, spacing)

        # Also reposition close and save buttons (they are not in tabs)
        # Close button already defined with absolute coordinates; they depend on panel_x/w
        close_size = 30
        self.close_button = (
            self.panel_x + self.panel_w - close_size - 10,
            self.panel_y + (self.title_height - close_size) // 2,
            close_size, close_size,
            self.close
        )
        self.save_button = (
            self.panel_x + 10,
            self.panel_y + self.panel_h - 40,
            150, 30,
            self.save
        )

    def resize(self, width, height):
        self.width = width
        self.height = height
        self._relayout()

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

    def close(self):
        self.active = False
        if self.window:
            glfw.set_input_mode(self.window, glfw.CURSOR, glfw.CURSOR_DISABLED)
        logging.debug("Dialog settings closed.")

    def save(self):
        config.Config.save(self.config)
        self.close()
        logging.debug("Settings saved.")

    def handle_mouse(self, xpos, ypos, button):
        if not self.active or button != glfw.MOUSE_BUTTON_LEFT:
            return False
        # Check close button
        cx, cy, cw, ch, action = self.close_button
        if cx <= xpos <= cx + cw and cy <= ypos <= cy + ch:
            action()
            return True
        # Check save button
        sx, sy, sw, sh, action = self.save_button
        if sx <= xpos <= sx + sw and sy <= ypos <= sy + sh:
            action()
            return True
        # Check tab headers
        header_y = self.panel_y + self.title_height
        header_h = self.tab_header_height
        tab_x = self.panel_x + 10
        for i, tab in enumerate(self.tabs):
            # Simple tab width based on text length
            text_width = len(tab.name) * 12  # approximate
            tab_w = text_width + 20
            if tab_x <= xpos <= tab_x + tab_w and header_y <= ypos <= header_y + header_h:
                self.active_tab_index = i
                return True
            tab_x += tab_w + 5
        # Forward to active tab's widgets
        if 0 <= self.active_tab_index < len(self.tabs):
            return self.tabs[self.active_tab_index].handle_mouse(xpos, ypos, self)
        return False

    def draw(self):
        if not self.active:
            return

        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Draw background panel
        self.rect_shader.use()
        glUniform2f(self.rect_uScreenSize, self.width, self.height)
        self._draw_rect(self.panel_x, self.panel_y, self.panel_w, self.panel_h, (0.2,0.2,0.2,0.8))

        # Title bar
        self._draw_rect(self.panel_x, self.panel_y, self.panel_w, self.title_height, (0.3,0.3,0.3,0.9))

        # Close button
        cx, cy, cw, ch, _ = self.close_button
        self._draw_rect(cx, cy, cw, ch, (0.6,0.2,0.2,0.9))

        # Tab headers
        header_y = self.panel_y + self.title_height
        header_h = self.tab_header_height
        tab_x = self.panel_x + 10
        for i, tab in enumerate(self.tabs):
            text_width = len(tab.name) * 12
            tab_w = text_width + 20
            # Active tab highlighted
            color = (0.4,0.6,0.9,0.9) if i == self.active_tab_index else (0.5,0.5,0.5,0.7)
            self._draw_rect(tab_x, header_y, tab_w, header_h, color)
            self._draw_text(tab.name, tab_x + 10, header_y + (header_h - 12)//2, 12,
                            color=(1,1,1,1))
            tab_x += tab_w + 5

        # Draw active tab widgets
        if 0 <= self.active_tab_index < len(self.tabs):
            self.tabs[self.active_tab_index].draw(self)

        # Save button
        sx, sy, sw, sh, _ = self.save_button
        self._draw_rect(sx, sy, sw, sh, (0.5,0.5,0.5,0.9))
        self._draw_text("Save", sx + (sw - 4*12)//2, sy + (sh - 12)//2, 12,
                        color=(1,1,1,1))

        # Title text
        title_width = len(self.title_text) * 12
        title_x = self.panel_x + (self.panel_w - title_width) // 2
        title_center_y = self.panel_y + (self.title_height - 12) // 2
        self._draw_text(self.title_text, title_x, title_center_y, 12,
                        color=(1,1,1,1))

        # Close button text
        cx, cy, cw, ch, _ = self.close_button
        self._draw_text("X", cx + (cw - 12)//2, cy + (ch - 12)//2, 12,
                        color=(1,1,1,1))

        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)

    def _draw_rect(self, x, y, w, h, color):
        """Draw a rectangle with given color (r,g,b,a) using top‑origin coordinates."""
        self.rect_shader.use()
        glUniform2f(self.rect_uScreenSize, self.width, self.height)
        glUniform4f(self.rect_uColor, *color)
        y_bottom = self.height - (y + h)
        glUniform2f(self.rect_uOffset, x + w/2, y_bottom + h/2)
        glUniform2f(self.rect_uScale, w, h)
        glBindVertexArray(self.quad_vao)
        glDrawElements(GL_TRIANGLES, self.quad_index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def _draw_text(self, text, x, y, size, color=(1,1,1,1), uppercase=False):
        """Draw text with given color, top‑origin coordinates, y is baseline (center)."""
        self.text_shader.use()
        glUniform2f(self.text_uScreenSize, self.width, self.height)
        glUniform3f(self.text_uColor, color[0], color[1], color[2])
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.font_tex)
        glUniform1i(self.text_uFontTexture, 0)
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
            y_center = self.height - (y + size/2)
            glUniform2f(self.text_uOffset, pos_x + size/2, y_center)
            glUniform2f(self.text_uScale, size, size)
            glDrawElements(GL_TRIANGLES, self.quad_index_count, GL_UNSIGNED_INT, None)

        glBindVertexArray(0)
