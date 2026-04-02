#!/usr/bin/env python3

class Screen:
    width = 1280
    height = 720
    @property
    def aspect(self):
        return self.width / self.height
screen = Screen()


MOVEMENT_SPEED = 10.0
PLAYER_HEIGHT = 1.5
TERRAIN_SPACING = 1.0
SHOOT_RANGE = 100.0
TARGET_COUNT = 10
NEAR = 0.1
FAR = 1000.0

import glfw
from OpenGL.GL import *
import numpy
import math
import random
import sys
import ctypes

from camera import get_height
from config import Config
from gui import Menu
from gui_stats import StatsPanel
from compass import Compass
from camera import Camera
from shader import Shader, VERTEX_SHADER_SRC, FRAGMENT_SHADER_SRC, CROSSHAIR_VERT_SRC, CROSSHAIR_FRAG_SRC
from chunks import ChunkManager
from target import Target
from sky import Sky
from player import Player


def compute_projection(width, height):
    proj = numpy.zeros((4, 4), dtype=numpy.float32)
    aspect = width / height
    fov_rad = math.radians(75.0)
    proj[0, 0] = 1.0 / (math.tan(fov_rad / 2.0) * aspect)
    proj[1, 1] = 1.0 / math.tan(fov_rad / 2.0)
    proj[2, 2] = -(FAR + NEAR) / (FAR - NEAR)
    proj[2, 3] = -(2.0 * FAR * NEAR) / (FAR - NEAR)
    proj[3, 2] = -1.0
    return proj


def main():
    # Load configuration
    config = Config.load()
    db_path = config.get("db_path", "data.db")
    mouse_sensitivity = config["mouse_sensitivity"]
    movement_speed = config["movement_speed"]
    player_height = config["player_height"]
    terrain_spacing = config["terrain_spacing"]
    chunk_size = config["chunk_size"]
    load_radius = config["load_radius"]
    cloud_count_per_chunk = config["cloud_count_per_chunk"]
    day_duration = config["day_duration"]
    star_count = config["star_count"]
    snow_count = config["snow_count"]
    snow_draw = config["snow_draw"]
    draw_stats = config.get("draw_stats", True)
    draw_compass = config.get("draw_compass", False)
    compass_scale = config.get("compass_scale", 1.0)
    spawn_mode = config.get("spawn_mode", "saved")
    random_range = config.get("random_spawn_range", 500)

    player = Player(db_path, height=player_height)

    if spawn_mode == "random":
        # Generate random position within range
        rand_x = random.uniform(-random_range, random_range)
        rand_z = random.uniform(-random_range, random_range)
        rand_y = get_height(rand_x, rand_z) + player_height
        player.position = (rand_x, rand_y, rand_z)
        # Also update camera position later
    elif spawn_mode == "portal":
        # Use saved portal position if exists, otherwise fallback to saved or origin
        if player.portal_position != (0.0, 0.0, 0.0):
            player.position = player.portal_position
        else:
            # Fallback to saved position (or generate random if none)
            if player.position == (0.0, 0.0, 0.0):
                rand_x = random.uniform(-random_range, random_range)
                rand_z = random.uniform(-random_range, random_range)
                rand_y = get_height(rand_x, rand_z) + player_height
                player.position = (rand_x, rand_y, rand_z)
    elif spawn_mode == "saved":
        # Already loaded, do nothing
        pass
    else:
        # Unknown mode, use saved
        pass

    if not glfw.init():
        sys.exit("Failed to initialize GLFW")

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)

    window = glfw.create_window(screen.width, screen.height, "FPS Shooter - Infinite Terrain", None, None)
    if not window:
        glfw.terminate()
        sys.exit("Failed to create window")

    glfw.make_context_current(window)
    glViewport(0, 0, screen.width, screen.height)
    glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_DISABLED)
    glEnable(GL_DEPTH_TEST)

    camera = Camera(player=player,
                    mouse_sensitivity=mouse_sensitivity,
                    movement_speed=movement_speed)

    chunk_manager = ChunkManager(
        chunk_size=chunk_size,
        load_radius=load_radius,
        spacing=terrain_spacing,
        player=player
    )

    sky = Sky(chunk_manager,
              cloud_count_per_chunk=cloud_count_per_chunk,
              star_count=star_count,
              snow_count=snow_count,
              snow_draw=snow_draw)
    sky.day_duration = day_duration

    shader_3d = Shader(VERTEX_SHADER_SRC, FRAGMENT_SHADER_SRC)
    shader_crosshair = Shader(CROSSHAIR_VERT_SRC, CROSSHAIR_FRAG_SRC)

    targets = []
    for _ in range(TARGET_COUNT):
        x = random.uniform(-50, 50)
        z = random.uniform(-50, 50)
        targets.append(Target(camera.get_target_position(x, z)))

    proj = numpy.zeros((4, 4), dtype=numpy.float32)
    fov = math.radians(75.0)
    proj[0, 0] = 1.0 / (math.tan(fov / 2.0) * screen.aspect)
    proj[1, 1] = 1.0 / math.tan(fov / 2.0)
    proj[2, 2] = -(FAR + NEAR) / (FAR - NEAR)
    proj[2, 3] = -(2.0 * FAR * NEAR) / (FAR - NEAR)
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

    compass = Compass(screen.width, screen.height, camera, draw_compass, compass_scale)
    stats_panel = StatsPanel(screen.width, screen.height, draw_stats)
    menu = Menu(screen.width, screen.height, config, camera)

    # Projection matrix – initially computed
    proj = compute_projection(screen.width, screen.height)

    def resize_callback(window, width, height):
        nonlocal proj
        screen.width = width
        screen.height = height
        glViewport(0, 0, width, height)
        stats_panel.resize(width, height)
        compass.resize(width, height)
        menu.resize(width, height)
        proj = compute_projection(width, height)

    glfw.set_window_size_callback(window, resize_callback)

    keys = {}

    # Combined key callback
    def key_callback(window, key, scancode, action, mods):
        if action == glfw.PRESS:
            keys[key] = True
        elif action == glfw.RELEASE:
            keys[key] = False
        if key == glfw.KEY_ESCAPE:
            glfw.set_window_should_close(window, True)
        if action == glfw.PRESS:
            if key == glfw.KEY_F9:
                menu.active = not menu.active
                if menu.active:
                    glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_NORMAL)
                else:
                    glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_DISABLED)
            elif key == glfw.KEY_F10:
                compass.enabled = not compass.enabled
            elif key == glfw.KEY_F11:
                stats_panel.enabled = not stats_panel.enabled

    # Combined mouse button callback
    def mouse_button_callback(window, button, action, mods):
        if button == glfw.MOUSE_BUTTON_LEFT and action == glfw.PRESS:
            if menu.active:
                xpos, ypos = glfw.get_cursor_pos(window)
                menu.handle_mouse(xpos, ypos, button)
                return
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

    last_x = screen.width // 2
    last_y = screen.height // 2
    first_mouse = True

    def mouse_callback(window, xpos, ypos):
        nonlocal last_x, last_y, first_mouse
        if menu.active:
            return
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
        light_dir, light_intensity = sky.get_combined_light()

        # Keep track of previous position
        if 'prev_pos' not in locals():
            prev_pos = camera.position.copy()

        # Compute speed
        speed = numpy.linalg.norm(camera.position - prev_pos) / dt if dt > 0 else 0.0
        prev_pos = camera.position.copy()

        player.speed = speed
        player.update_from_camera(camera)

        # Update stats panel with player's values
        if stats_panel.enabled:
            stats_panel.update(
                position=player.position,
                speed=player.speed,
                life_percent=player.life_percent,
                mana_percent=player.mana_percent,
                weapon_name=player.weapon_name,
                ammo_count=player.ammo_count,
                familiar_name=player.familiar_name
            )

        glClearColor(0.1, 0.2, 0.3, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        view = camera.get_view_matrix()
        shader_3d.use()
        shader_3d.set_mat4("uView", view)
        shader_3d.set_mat4("uProjection", proj)
        shader_3d.set_vec3("uLightDir", light_dir)
        shader_3d.set_float("uLightIntensity", light_intensity)

        sky.draw_background(view, proj, camera.position, glfw.get_time(), screen.width, screen.height)

        shader_3d.use()
        chunk_manager.draw(shader_3d)

        for target in targets:
            target.draw(shader_3d, view, proj, light_dir)

        sky.draw_foreground(view, proj, camera.position, glfw.get_time())

        glDisable(GL_DEPTH_TEST)
        shader_crosshair.use()
        shader_crosshair.set_vec2("uScreenSize", numpy.array([screen.width, screen.height]))
        glBindVertexArray(crosshair_vao)
        glDrawArrays(GL_LINES, 0, 4)
        glBindVertexArray(0)
        glEnable(GL_DEPTH_TEST)

        compass.draw()
        stats_panel.draw()
        menu.draw()

        glfw.swap_buffers(window)
        glfw.poll_events()

    chunk_manager.shutdown()

    chunk_manager.save_all_chunks()
    player.save()

    glfw.terminate()

if __name__ == "__main__":
    main()
