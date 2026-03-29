#!/usr/bin/env python3
"""
FPS Shooter with Infinite Terrain
- GLFW for window and input
- PyOpenGL for rendering
- Infinite terrain generated on the fly
- Simple shooting mechanics
"""

import glfw
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader
import numpy as np
import math
import random
import sys
import ctypes

# ------------------------------ Constants ------------------------------
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720

# Camera settings
MOUSE_SENSITIVITY = 0.002
MOVEMENT_SPEED = 10.0
PLAYER_HEIGHT = 1.5

# Terrain settings
TERRAIN_WIDTH = 200          # number of vertices along X
TERRAIN_HEIGHT = 200         # number of vertices along Z
TERRAIN_SPACING = 1.0        # distance between vertices

# Shooting settings
SHOOT_RANGE = 100.0
TARGET_COUNT = 10

# ------------------------------ Shader Sources ------------------------------
VERTEX_SHADER_SRC = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;

uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
uniform vec3 uLightDir;

out vec3 vColor;

void main() {
    // Simple directional lighting
    vec3 normal = normalize(aNormal);
    float diff = max(dot(normal, normalize(uLightDir)), 0.2);
    // Color based on height (green/brown)
    float h = aPos.y;
    vColor = mix(vec3(0.3, 0.6, 0.2), vec3(0.5, 0.4, 0.2), clamp((h + 2.0) / 6.0, 0.0, 1.0));
    vColor *= diff;
    gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
}
"""

FRAGMENT_SHADER_SRC = """
#version 330 core
in vec3 vColor;
out vec4 FragColor;

void main() {
    FragColor = vec4(vColor, 1.0);
}
"""

CROSSHAIR_VERT_SRC = """
#version 330 core
layout(location = 0) in vec2 aPos;
uniform vec2 uScreenSize;
void main() {
    vec2 pos = aPos / uScreenSize * 2.0 - 1.0;
    gl_Position = vec4(pos, 0.0, 1.0);
}
"""

CROSSHAIR_FRAG_SRC = """
#version 330 core
out vec4 FragColor;
void main() {
    FragColor = vec4(1.0, 1.0, 1.0, 1.0);
}
"""

# ------------------------------ Camera Class ------------------------------
class Camera:
    def __init__(self, position=np.array([0.0, PLAYER_HEIGHT, 0.0])):
        self.position = position
        self.yaw = -90.0
        self.pitch = 0.0
        self.front = np.array([0.0, 0.0, -1.0])
        self.up = np.array([0.0, 1.0, 0.0])
        self.right = np.array([1.0, 0.0, 0.0])
        self.update_vectors()

    def update_vectors(self):
        front = np.array([
            math.cos(math.radians(self.yaw)) * math.cos(math.radians(self.pitch)),
            math.sin(math.radians(self.pitch)),
            math.sin(math.radians(self.yaw)) * math.cos(math.radians(self.pitch))
        ])
        self.front = front / np.linalg.norm(front)
        self.right = np.cross(self.front, self.up)
        self.right /= np.linalg.norm(self.right)
        self.up = np.cross(self.right, self.front)
        self.up /= np.linalg.norm(self.up)

    def process_mouse(self, dx, dy):
        self.yaw += dx * MOUSE_SENSITIVITY
        self.pitch += dy * MOUSE_SENSITIVITY
        if self.pitch > 89.0:
            self.pitch = 89.0
        if self.pitch < -89.0:
            self.pitch = -89.0
        self.update_vectors()

    def process_keyboard(self, keys, dt):
        speed = MOVEMENT_SPEED * dt
        if keys.get(glfw.KEY_W, False):
            self.position += self.front * speed
        if keys.get(glfw.KEY_S, False):
            self.position -= self.front * speed
        if keys.get(glfw.KEY_A, False):
            self.position -= self.right * speed
        if keys.get(glfw.KEY_D, False):
            self.position += self.right * speed

    def get_view_matrix(self):
        # Build lookAt matrix
        f = self.front
        u = self.up
        s = self.right
        pos = self.position
        view = np.eye(4)
        view[0, 0] = s[0]
        view[0, 1] = s[1]
        view[0, 2] = s[2]
        view[1, 0] = u[0]
        view[1, 1] = u[1]
        view[1, 2] = u[2]
        view[2, 0] = -f[0]
        view[2, 1] = -f[1]
        view[2, 2] = -f[2]
        view[0, 3] = -np.dot(s, pos)
        view[1, 3] = -np.dot(u, pos)
        view[2, 3] = np.dot(f, pos)
        return view

# ------------------------------ Terrain Class ------------------------------
class Terrain:
    def __init__(self, camera, width, height, spacing):
        self.camera = camera
        self.width = width
        self.height = height
        self.spacing = spacing
        self.vertices = None
        self.indices = None
        self.last_cam_pos = None
        self.setup_mesh()

    def setup_mesh(self):
        # Generate indices (two triangles per cell)
        indices = []
        for z in range(self.height - 1):
            for x in range(self.width - 1):
                i = z * self.width + x
                indices.append(i)
                indices.append(i + 1)
                indices.append(i + self.width)
                indices.append(i + 1)
                indices.append(i + self.width + 1)
                indices.append(i + self.width)
        self.indices = np.array(indices, dtype=np.uint32)

        # Create VAO, VBO, EBO
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.ebo = glGenBuffers(1)

        glBindVertexArray(self.vao)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self.indices.nbytes, self.indices, GL_STATIC_DRAW)

        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        # Position attribute
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 24, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        # Normal attribute
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 24, ctypes.c_void_p(12))
        glEnableVertexAttribArray(1)

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

    def get_height(self, x, z):
        # Smooth, infinite height function (no external libraries)
        # Combine sine/cosine waves to create rolling hills
        h = (math.sin(x * 0.1) * math.cos(z * 0.1) +
             0.3 * math.sin(x * 0.3 + 1.2) +
             0.3 * math.cos(z * 0.3 + 2.4) +
             0.2 * math.sin((x * 0.6 + z * 0.4) * 0.8))
        return h * 2.0  # scale to reasonable height range

    def update_vertices(self):
        # Update only when camera moves more than half a spacing
        cam_xz = np.array([self.camera.position[0], self.camera.position[2]])
        if self.last_cam_pos is not None and np.linalg.norm(cam_xz - self.last_cam_pos) < TERRAIN_SPACING * 0.5:
            return
        self.last_cam_pos = cam_xz.copy()

        # Center the grid on the camera
        center_x = self.camera.position[0]
        center_z = self.camera.position[2]

        # Build vertex array (position + normal)
        vertices = np.zeros((self.width * self.height, 6), dtype=np.float32)  # xyz, normal xyz
        for z in range(self.height):
            for x in range(self.width):
                wx = center_x + (x - self.width // 2) * self.spacing
                wz = center_z + (z - self.height // 2) * self.spacing
                wy = self.get_height(wx, wz)
                idx = z * self.width + x
                vertices[idx, 0:3] = [wx, wy, wz]

        # Compute normals (simple central differences)
        for z in range(self.height):
            for x in range(self.width):
                idx = z * self.width + x
                if 0 < x < self.width-1 and 0 < z < self.height-1:
                    # height differences
                    hx1 = vertices[(z)*self.width + (x+1), 1]
                    hx2 = vertices[(z)*self.width + (x-1), 1]
                    hz1 = vertices[(z+1)*self.width + x, 1]
                    hz2 = vertices[(z-1)*self.width + x, 1]
                    dx = hx1 - hx2
                    dz = hz1 - hz2
                    normal = np.array([-dx, 2.0 * self.spacing, -dz])
                    normal = normal / np.linalg.norm(normal)
                else:
                    normal = np.array([0.0, 1.0, 0.0])
                vertices[idx, 3:6] = normal

        # Update VBO
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_DYNAMIC_DRAW)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

    def draw(self, shader):
        self.update_vertices()
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, len(self.indices), GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

# ------------------------------ Target Class ------------------------------
class Target:
    def __init__(self, position, size=0.5):
        self.position = position
        self.size = size
        self.active = True
        self.vao = None
        self.vbo = None
        self.ebo = None
        self.setup_cube()

    def setup_cube(self):
        # Cube vertices (positions and normals)
        vertices = np.array([
            # positions          # normals
            -0.5, -0.5, -0.5,  0.0, -1.0,  0.0,
             0.5, -0.5, -0.5,  0.0, -1.0,  0.0,
             0.5, -0.5,  0.5,  0.0, -1.0,  0.0,
            -0.5, -0.5,  0.5,  0.0, -1.0,  0.0,

            -0.5,  0.5, -0.5,  0.0,  1.0,  0.0,
             0.5,  0.5, -0.5,  0.0,  1.0,  0.0,
             0.5,  0.5,  0.5,  0.0,  1.0,  0.0,
            -0.5,  0.5,  0.5,  0.0,  1.0,  0.0,

            -0.5, -0.5, -0.5, -1.0,  0.0,  0.0,
            -0.5,  0.5, -0.5, -1.0,  0.0,  0.0,
            -0.5,  0.5,  0.5, -1.0,  0.0,  0.0,
            -0.5, -0.5,  0.5, -1.0,  0.0,  0.0,

             0.5, -0.5, -0.5,  1.0,  0.0,  0.0,
             0.5,  0.5, -0.5,  1.0,  0.0,  0.0,
             0.5,  0.5,  0.5,  1.0,  0.0,  0.0,
             0.5, -0.5,  0.5,  1.0,  0.0,  0.0,

            -0.5, -0.5, -0.5,  0.0,  0.0, -1.0,
             0.5, -0.5, -0.5,  0.0,  0.0, -1.0,
             0.5,  0.5, -0.5,  0.0,  0.0, -1.0,
            -0.5,  0.5, -0.5,  0.0,  0.0, -1.0,

            -0.5, -0.5,  0.5,  0.0,  0.0,  1.0,
             0.5, -0.5,  0.5,  0.0,  0.0,  1.0,
             0.5,  0.5,  0.5,  0.0,  0.0,  1.0,
            -0.5,  0.5,  0.5,  0.0,  0.0,  1.0,
        ], dtype=np.float32)

        indices = np.array([
             0,  1,  2,  0,  2,  3,   # bottom
             4,  5,  6,  4,  6,  7,   # top
             8,  9, 10,  8, 10, 11,   # left
            12, 13, 14, 12, 14, 15,   # right
            16, 17, 18, 16, 18, 19,   # back
            20, 21, 22, 20, 22, 23    # front
        ], dtype=np.uint32)

        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.ebo = glGenBuffers(1)

        glBindVertexArray(self.vao)

        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)

        # Position attribute
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 24, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        # Normal attribute
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 24, ctypes.c_void_p(12))
        glEnableVertexAttribArray(1)

        glBindVertexArray(0)

    def draw(self, shader, view, proj, light_dir):
        if not self.active:
            return
        model = np.eye(4)
        model[0, 3] = self.position[0]
        model[1, 3] = self.position[1]
        model[2, 3] = self.position[2]
        model[0, 0] = self.size
        model[1, 1] = self.size
        model[2, 2] = self.size

        shader.use()
        shader.set_mat4("uModel", model)
        shader.set_mat4("uView", view)
        shader.set_mat4("uProjection", proj)
        shader.set_vec3("uLightDir", light_dir)

        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, 36, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def hit(self, ray_origin, ray_dir):
        # Simple sphere intersection (cube approximated as sphere for simplicity)
        center = self.position
        radius = self.size * 0.866  # half cube diagonal
        oc = ray_origin - center
        a = np.dot(ray_dir, ray_dir)
        b = 2.0 * np.dot(oc, ray_dir)
        c = np.dot(oc, oc) - radius * radius
        disc = b * b - 4 * a * c
        return disc >= 0

# ------------------------------ Shader Wrapper ------------------------------
class Shader:
    def __init__(self, vert_src, frag_src):
        self.program = compileProgram(compileShader(vert_src, GL_VERTEX_SHADER),
                                      compileShader(frag_src, GL_FRAGMENT_SHADER))

    def use(self):
        glUseProgram(self.program)

    def set_mat4(self, name, mat):
        loc = glGetUniformLocation(self.program, name)
        glUniformMatrix4fv(loc, 1, GL_TRUE, mat)

    def set_vec3(self, name, vec):
        loc = glGetUniformLocation(self.program, name)
        glUniform3fv(loc, 1, vec)

    def set_vec2(self, name, vec):
        loc = glGetUniformLocation(self.program, name)
        glUniform2fv(loc, 1, vec)

    def set_float(self, name, val):
        loc = glGetUniformLocation(self.program, name)
        glUniform1f(loc, val)

# ------------------------------ Main Application ------------------------------
def main():
    # Initialize GLFW
    if not glfw.init():
        sys.exit("Failed to initialize GLFW")

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)

    window = glfw.create_window(WINDOW_WIDTH, WINDOW_HEIGHT, "FPS Shooter - Infinite Terrain", None, None)
    if not window:
        glfw.terminate()
        sys.exit("Failed to create window")

    glfw.make_context_current(window)
    glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_DISABLED)

    # Enable depth testing
    glEnable(GL_DEPTH_TEST)

    # Create camera
    camera = Camera()

    # Create terrain
    terrain = Terrain(camera, TERRAIN_WIDTH, TERRAIN_HEIGHT, TERRAIN_SPACING)

    # Create shaders
    shader_3d = Shader(VERTEX_SHADER_SRC, FRAGMENT_SHADER_SRC)
    shader_crosshair = Shader(CROSSHAIR_VERT_SRC, CROSSHAIR_FRAG_SRC)

    # Light direction (from top left)
    light_dir = np.array([1.0, 2.0, 1.0], dtype=np.float32)
    light_dir = light_dir / np.linalg.norm(light_dir)

    # Generate targets
    targets = []
    for _ in range(TARGET_COUNT):
        # Place on terrain at random position around camera
        x = random.uniform(-50, 50)
        z = random.uniform(-50, 50)
        y = terrain.get_height(x, z) + 0.5
        targets.append(Target(np.array([x, y, z])))

    # Projection matrix
    proj = np.zeros((4, 4), dtype=np.float32)
    aspect = WINDOW_WIDTH / WINDOW_HEIGHT
    fov = math.radians(75.0)
    near = 0.1
    far = 200.0
    proj[0, 0] = 1.0 / (math.tan(fov / 2.0) * aspect)
    proj[1, 1] = 1.0 / math.tan(fov / 2.0)
    proj[2, 2] = -(far + near) / (far - near)
    proj[2, 3] = -(2.0 * far * near) / (far - near)
    proj[3, 2] = -1.0

    # Crosshair vertices (two lines)
    crosshair_verts = np.array([
        -10.0, 0.0,
        10.0, 0.0,
        0.0, -10.0,
        0.0, 10.0
    ], dtype=np.float32)
    crosshair_vao = glGenVertexArrays(1)
    crosshair_vbo = glGenBuffers(1)
    glBindVertexArray(crosshair_vao)
    glBindBuffer(GL_ARRAY_BUFFER, crosshair_vbo)
    glBufferData(GL_ARRAY_BUFFER, crosshair_verts.nbytes, crosshair_verts, GL_STATIC_DRAW)
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 8, ctypes.c_void_p(0))
    glEnableVertexAttribArray(0)
    glBindVertexArray(0)

    # Input state
    keys = {}

    def key_callback(window, key, scancode, action, mods):
        if action == glfw.PRESS:
            keys[key] = True
        elif action == glfw.RELEASE:
            keys[key] = False
        if key == glfw.KEY_ESCAPE:
            glfw.set_window_should_close(window, True)

    def mouse_button_callback(window, button, action, mods):
        if button == glfw.MOUSE_BUTTON_LEFT and action == glfw.PRESS:
            # Ray casting from camera through center of screen
            ray_dir = camera.front
            ray_origin = camera.position
            # Check targets
            for target in targets:
                if target.active and target.hit(ray_origin, ray_dir):
                    target.active = False
                    # Respawn at new random location
                    x = random.uniform(camera.position[0] - 50, camera.position[0] + 50)
                    z = random.uniform(camera.position[2] - 50, camera.position[2] + 50)
                    y = terrain.get_height(x, z) + 0.5
                    target.position = np.array([x, y, z])
                    target.active = True
                    break

    glfw.set_key_callback(window, key_callback)
    glfw.set_mouse_button_callback(window, mouse_button_callback)

    # Mouse look
    last_x = WINDOW_WIDTH // 2
    last_y = WINDOW_HEIGHT // 2
    first_mouse = True

    def mouse_callback(window, xpos, ypos):
        nonlocal last_x, last_y, first_mouse
        if first_mouse:
            last_x = xpos
            last_y = ypos
            first_mouse = False
        dx = xpos - last_x
        dy = last_y - ypos
        last_x = xpos
        last_y = ypos
        camera.process_mouse(dx, dy)

    glfw.set_cursor_pos_callback(window, mouse_callback)

    # Main loop
    last_time = glfw.get_time()
    while not glfw.window_should_close(window):
        current_time = glfw.get_time()
        dt = current_time - last_time
        last_time = current_time

        # Process input
        camera.process_keyboard(keys, dt)

        # Clear buffers
        glClearColor(0.1, 0.2, 0.3, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # 3D rendering
        view = camera.get_view_matrix()
        shader_3d.use()
        shader_3d.set_mat4("uView", view)
        shader_3d.set_mat4("uProjection", proj)
        shader_3d.set_vec3("uLightDir", light_dir)

        # Draw terrain
        terrain.draw(shader_3d)

        # Draw targets
        for target in targets:
            target.draw(shader_3d, view, proj, light_dir)

        # Draw crosshair (2D overlay)
        glDisable(GL_DEPTH_TEST)
        shader_crosshair.use()
        shader_crosshair.set_vec2("uScreenSize", np.array([WINDOW_WIDTH, WINDOW_HEIGHT]))
        glBindVertexArray(crosshair_vao)
        glDrawArrays(GL_LINES, 0, 4)
        glBindVertexArray(0)
        glEnable(GL_DEPTH_TEST)

        glfw.swap_buffers(window)
        glfw.poll_events()

    # Cleanup
    glfw.terminate()

if __name__ == "__main__":
    main()
