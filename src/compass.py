import numpy
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader
import math
import ctypes

from font import FONT_BITMAPS
from gui_shaders import TEXT_VERTEX_SHADER, TEXT_FRAGMENT_SHADER


class Compass:
    def __init__(self, screen_width, screen_height, camera, enabled=True):
        self.enabled = enabled
        self.width = screen_width
        self.height = screen_height
        self.camera = camera
        self.radius = 80
        self.margin = 20

        # Circle texture
        self.circle_tex = self._create_circle_texture()

        # Shaders
        self.tex_shader = self._create_textured_quad_shader()
        self.text_shader = self._create_text_shader()
        self.arrow_shader = self._create_arrow_shader()

        # Quad VAO (standard texture coordinates: v=0 bottom, v=1 top)
        self.quad_vao = self._create_quad_vao()
        # Arrow VAO (dynamic)
        self.arrow_vao = glGenVertexArrays(1)
        self.arrow_vbo = glGenBuffers(1)
        glBindVertexArray(self.arrow_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.arrow_vbo)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 8, None)
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)

        # Font texture
        self.font_tex = self._create_font_texture()

    # ----------------------------------------------------------------------
    # Create a dark gray circle with green border (semi‑transparent interior)
    # ----------------------------------------------------------------------
    def _create_circle_texture(self):
        size = 128
        border_width = 3
        data = numpy.zeros((size, size, 4), dtype=numpy.uint8)
        center = size / 2
        radius = size / 2 - 1
        for y in range(size):
            for x in range(size):
                dx = x - center
                dy = y - center
                dist = math.hypot(dx, dy)
                if dist <= radius:
                    if dist >= radius - border_width:
                        data[y, x] = [0, 255, 0, 255]          # green border
                    else:
                        data[y, x] = [40, 40, 40, 200]         # dark gray, semi‑transparent
                else:
                    data[y, x] = [0, 0, 0, 0]
        tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, size, size, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glBindTexture(GL_TEXTURE_2D, 0)
        return tex

    # ----------------------------------------------------------------------
    # Font texture (same as in gui.py)
    # ----------------------------------------------------------------------
    def _create_font_texture(self):
        cols = 16
        rows = 8
        cell_w = 8
        cell_h = 8
        tex_w = cols * cell_w
        tex_h = rows * cell_h
        data = numpy.zeros((tex_h, tex_w, 4), dtype=numpy.uint8)
        for code in range(32, 128):
            row = (code - 32) // cols
            col = (code - 32) % cols
            bitmap = FONT_BITMAPS.get(code, [0] * 8)
            for y in range(cell_h):
                row_bits = bitmap[y] if y < len(bitmap) else 0
                for x in range(cell_w):
                    if (row_bits >> (7 - x)) & 1:
                        data[row * cell_h + y, col * cell_w + x] = [255, 255, 255, 255]
        tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tex_w, tex_h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glBindTexture(GL_TEXTURE_2D, 0)
        return tex

    # ----------------------------------------------------------------------
    # Shader for textured quad (circle)
    # ----------------------------------------------------------------------
    def _create_textured_quad_shader(self):
        vert = """
        #version 330 core
        layout (location = 0) in vec2 aPos;
        layout (location = 1) in vec2 aTexCoord;
        out vec2 TexCoord;
        uniform vec2 uScreenSize;
        uniform vec2 uOffset;
        uniform vec2 uScale;
        void main() {
            vec2 pos = aPos * uScale + uOffset;
            // Convert bottom‑origin pixel coordinates to NDC
            vec2 ndc = vec2(pos.x / uScreenSize.x * 2.0 - 1.0,
                            pos.y / uScreenSize.y * 2.0 - 1.0);
            gl_Position = vec4(ndc, 0.0, 1.0);
            TexCoord = aTexCoord;
        }
        """
        frag = """
        #version 330 core
        in vec2 TexCoord;
        out vec4 FragColor;
        uniform sampler2D uTexture;
        uniform vec4 uColor;
        void main() {
            FragColor = texture(uTexture, TexCoord) * uColor;
        }
        """
        return compileProgram(compileShader(vert, GL_VERTEX_SHADER),
                              compileShader(frag, GL_FRAGMENT_SHADER))

    # ----------------------------------------------------------------------
    # Shader for text (re‑uses the same shader as the menu)
    # ----------------------------------------------------------------------
    def _create_text_shader(self):
        return compileProgram(compileShader(TEXT_VERTEX_SHADER, GL_VERTEX_SHADER),
                              compileShader(TEXT_FRAGMENT_SHADER, GL_FRAGMENT_SHADER))

    # ----------------------------------------------------------------------
    # Shader for red arrow (coloured triangle)
    # ----------------------------------------------------------------------
    def _create_arrow_shader(self):
        vert = """
        #version 330 core
        layout (location = 0) in vec2 aPos;
        uniform vec2 uScreenSize;
        uniform vec2 uOffset;
        void main() {
            vec2 pos = aPos + uOffset;
            vec2 ndc = vec2(pos.x / uScreenSize.x * 2.0 - 1.0,
                            pos.y / uScreenSize.y * 2.0 - 1.0);
            gl_Position = vec4(ndc, 0.0, 1.0);
        }
        """
        frag = """
        #version 330 core
        out vec4 FragColor;
        uniform vec3 uColor;
        uniform float uAlpha;
        void main() {
            FragColor = vec4(uColor, uAlpha);
        }
        """
        return compileProgram(compileShader(vert, GL_VERTEX_SHADER),
                              compileShader(frag, GL_FRAGMENT_SHADER))

    # ----------------------------------------------------------------------
    # Standard quad VAO (v=0 at bottom, v=1 at top)
    # ----------------------------------------------------------------------
    def _create_quad_vao(self):
        verts = numpy.array([
            -0.5, -0.5, 0.0, 0.0,   # bottom-left
             0.5, -0.5, 1.0, 0.0,   # bottom-right
             0.5,  0.5, 1.0, 1.0,   # top-right
            -0.5,  0.5, 0.0, 1.0,   # top-left
        ], dtype=numpy.float32)
        indices = numpy.array([0, 1, 2, 0, 2, 3], dtype=numpy.uint32)
        vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        ebo = glGenBuffers(1)
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(8))
        glEnableVertexAttribArray(1)
        glBindVertexArray(0)
        return vao

    # ----------------------------------------------------------------------
    # Public draw method
    # ----------------------------------------------------------------------
    def draw(self):
        if self.enabled:
            glDisable(GL_DEPTH_TEST)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            cx = self.width - self.margin - self.radius
            cy = self.margin + self.radius
            self._draw_circle(cx, cy, self.radius)
            self._draw_text("N", cx - 8, cy - self.radius + 10, 16, (0.7, 0.0, 1.0))
            self._draw_text("S", cx - 8, cy + self.radius - 20, 16, (0.7, 0.0, 1.0))
            self._draw_text("W", cx - self.radius + 10, cy, 16, (0.7, 0.0, 1.0))
            self._draw_text("E", cx + self.radius - 20, cy, 16, (0.7, 0.0, 1.0))
            angle_rad = math.radians(self.camera.yaw)
            self._draw_arrow(cx, cy, self.radius, angle_rad)
            glEnable(GL_DEPTH_TEST)
            glDisable(GL_BLEND)

    # ----------------------------------------------------------------------
    # Draw circle at given top‑origin centre
    # ----------------------------------------------------------------------
    def _draw_circle(self, cx, cy, radius):
        glUseProgram(self.tex_shader)
        # Convert centre from top‑origin to bottom‑origin
        offset_x = cx
        offset_y = self.height - cy
        glUniform2f(glGetUniformLocation(self.tex_shader, "uScreenSize"), self.width, self.height)
        glUniform2f(glGetUniformLocation(self.tex_shader, "uOffset"), offset_x, offset_y)
        glUniform2f(glGetUniformLocation(self.tex_shader, "uScale"), radius * 2, radius * 2)
        glUniform4f(glGetUniformLocation(self.tex_shader, "uColor"), 1.0, 1.0, 1.0, 1.0)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.circle_tex)
        glUniform1i(glGetUniformLocation(self.tex_shader, "uTexture"), 0)
        glBindVertexArray(self.quad_vao)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    # ----------------------------------------------------------------------
    # Draw text at top‑origin position (baseline = centre of character)
    # ----------------------------------------------------------------------
    def _draw_text(self, text, x, y, size, color=(0.7, 0.0, 1.0)):
        glUseProgram(self.text_shader)
        glUniform2f(glGetUniformLocation(self.text_shader, "uScreenSize"), self.width, self.height)
        glUniform3f(glGetUniformLocation(self.text_shader, "uColor"), *color)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.font_tex)
        glUniform1i(glGetUniformLocation(self.text_shader, "uFontTexture"), 0)

        for i, ch in enumerate(text):
            code = ord(ch)
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
            glUniform4f(glGetUniformLocation(self.text_shader, "uTexRect"), *tex_rect)

            # Character centre in top‑origin
            pos_x = x + i * size
            y_center = y
            # Convert to bottom‑origin centre
            y_bottom = self.height - y_center
            glUniform2f(glGetUniformLocation(self.text_shader, "uOffset"), pos_x + size / 2, y_bottom)
            glUniform2f(glGetUniformLocation(self.text_shader, "uScale"), size, size)
            glBindVertexArray(self.quad_vao)
            glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    # ----------------------------------------------------------------------
    # Draw red arrow at top‑origin centre
    # ----------------------------------------------------------------------
    def _draw_arrow(self, cx, cy, radius, angle_rad):
        border_width = 3                     # same as in texture creation
        inner_radius = radius - border_width  # arrow reaches inner edge

        tip_len = inner_radius               # tip touches inner border
        base_len = inner_radius * 0.25       # base shorter (adjust as desired)
        perp_angle = angle_rad + math.pi / 2

        tip_x = cx + math.cos(angle_rad) * tip_len
        tip_y = cy + math.sin(angle_rad) * tip_len

        base1_x = cx + math.cos(angle_rad) * base_len + math.cos(perp_angle) * (radius * 0.15)
        base1_y = cy + math.sin(angle_rad) * base_len + math.sin(perp_angle) * (radius * 0.15)
        base2_x = cx + math.cos(angle_rad) * base_len - math.cos(perp_angle) * (radius * 0.15)
        base2_y = cy + math.sin(angle_rad) * base_len - math.sin(perp_angle) * (radius * 0.15)

        # Convert vertices from top‑origin to bottom‑origin
        vertices = numpy.array([
            tip_x, self.height - tip_y,
            base1_x, self.height - base1_y,
            base2_x, self.height - base2_y
        ], dtype=numpy.float32)

        glUseProgram(self.arrow_shader)
        glUniform2f(glGetUniformLocation(self.arrow_shader, "uScreenSize"), self.width, self.height)
        glUniform2f(glGetUniformLocation(self.arrow_shader, "uOffset"), 0.0, 0.0)
        glUniform3f(glGetUniformLocation(self.arrow_shader, "uColor"), 1.0, 0.0, 0.0) # red
        glUniform1f(glGetUniformLocation(self.arrow_shader, "uAlpha"), 0.2)
        glBindVertexArray(self.arrow_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.arrow_vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_DYNAMIC_DRAW)
        glDrawArrays(GL_TRIANGLES, 0, 3)
        glBindVertexArray(0)
