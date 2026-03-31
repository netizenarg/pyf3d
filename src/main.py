#!/usr/bin/env python3

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
MOUSE_SENSITIVITY = 0.002
MOVEMENT_SPEED = 10.0
PLAYER_HEIGHT = 1.5
TERRAIN_SPACING = 1.0
SHOOT_RANGE = 100.0
TARGET_COUNT = 10


import glfw
from OpenGL.GL import *
import numpy
import math
import random
import sys
import ctypes

from camera import Camera
from shader import Shader, VERTEX_SHADER_SRC, FRAGMENT_SHADER_SRC, CROSSHAIR_VERT_SRC, CROSSHAIR_FRAG_SRC
from chunks import ChunkManager
from target import Target
from sky import Sky


def main():
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
    glEnable(GL_DEPTH_TEST)

    camera = Camera(mouse_sensitivity=MOUSE_SENSITIVITY, movement_speed=MOVEMENT_SPEED, player_height=PLAYER_HEIGHT)
    chunk_manager = ChunkManager(chunk_size=32, load_radius=3, spacing=TERRAIN_SPACING)
    sky = Sky(chunk_manager, cloud_count_per_chunk=5, snow_count=500)

    shader_3d = Shader(VERTEX_SHADER_SRC, FRAGMENT_SHADER_SRC)
    shader_crosshair = Shader(CROSSHAIR_VERT_SRC, CROSSHAIR_FRAG_SRC)

    light_dir = numpy.array([1.0, 2.0, 1.0], dtype=numpy.float32)
    light_dir = light_dir / numpy.linalg.norm(light_dir)

    targets = []
    for _ in range(TARGET_COUNT):
        x = random.uniform(-50, 50)
        z = random.uniform(-50, 50)
        targets.append(Target(camera.get_target_position(x, z)))

    proj = numpy.zeros((4, 4), dtype=numpy.float32)
    aspect = WINDOW_WIDTH / WINDOW_HEIGHT
    fov = math.radians(75.0)
    near = 0.1
    far = 200.0
    proj[0, 0] = 1.0 / (math.tan(fov / 2.0) * aspect)
    proj[1, 1] = 1.0 / math.tan(fov / 2.0)
    proj[2, 2] = -(far + near) / (far - near)
    proj[2, 3] = -(2.0 * far * near) / (far - near)
    proj[3, 2] = -1.0

    crosshair_verts = numpy.array([-10.0, 0.0, 10.0, 0.0, 0.0, -10.0, 0.0, 10.0], dtype=numpy.float32)
    crosshair_vao = glGenVertexArrays(1)
    crosshair_vbo = glGenBuffers(1)
    glBindVertexArray(crosshair_vao)
    glBindBuffer(GL_ARRAY_BUFFER, crosshair_vbo)
    glBufferData(GL_ARRAY_BUFFER, crosshair_verts.nbytes, crosshair_verts, GL_STATIC_DRAW)
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 8, ctypes.c_void_p(0))
    glEnableVertexAttribArray(0)
    glBindVertexArray(0)

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
            ray_dir = camera.front
            ray_origin = camera.position
            for target in targets:
                if target.active and target.hit(ray_origin, ray_dir):
                    target.active = False
                    target.position = camera.get_target_position()
                    target.active = True
                    break

    glfw.set_key_callback(window, key_callback)
    glfw.set_mouse_button_callback(window, mouse_button_callback)

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

    last_time = glfw.get_time()
    while not glfw.window_should_close(window):
        current_time = glfw.get_time()
        dt = current_time - last_time
        last_time = current_time

        camera.process_keyboard(keys, dt)
        chunk_manager.update(camera.position)
        sky.update(dt)

        glClearColor(0.1, 0.2, 0.3, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        view = camera.get_view_matrix()
        shader_3d.use()
        shader_3d.set_mat4("uView", view)
        shader_3d.set_mat4("uProjection", proj)
        shader_3d.set_vec3("uLightDir", light_dir)

        sky.draw_background(view, proj, camera.position, glfw.get_time(), WINDOW_WIDTH, WINDOW_HEIGHT)

        shader_3d.use()
        chunk_manager.draw(shader_3d)

        for target in targets:
            target.draw(shader_3d, view, proj, light_dir)

        sky.draw_all(view, proj, camera.position, glfw.get_time())

        glDisable(GL_DEPTH_TEST)
        shader_crosshair.use()
        shader_crosshair.set_vec2("uScreenSize", numpy.array([WINDOW_WIDTH, WINDOW_HEIGHT]))
        glBindVertexArray(crosshair_vao)
        glDrawArrays(GL_LINES, 0, 4)
        glBindVertexArray(0)
        glEnable(GL_DEPTH_TEST)

        glfw.swap_buffers(window)
        glfw.poll_events()

    chunk_manager.shutdown()
    glfw.terminate()

if __name__ == "__main__":
    main()
