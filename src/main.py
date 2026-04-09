#!/usr/bin/env python3

TARGET_COUNT = 10
NEAR = 0.1
FAR = 1000.0

class Screen:
    width = 1280
    height = 720
    @property
    def aspect(self):
        return self.width / self.height
screen = Screen()

from logger import logging, setup_logging

import glfw
from OpenGL.GL import *
import numpy
import math
import random
import sys
import ctypes

from shaders.shader import Shader
from shaders.terrain_shdr import VERTEX_SHADER_SRC, FRAGMENT_SHADER_SRC, CROSSHAIR_VERT_SRC, CROSSHAIR_FRAG_SRC

from camera import get_height
from config import Config
from media.audio import Audio
from gui import Menu
from gui_stats import StatsPanel
from gui_fps import FPSOverlay
from compass import Compass
from camera import Camera
from chunks import ChunkManager
from target import Target
from sky import Sky
from player import Player
from player_model import PlayerModel
from health import HealthManager
from mobs import get_aimed_mob, MobManager
from weapon import Ammo, Weapon
from trees import TreeManager


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
    config = Config.load()

    setup_logging(config.get('log_config', {}))

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
    camera_mode = config.get("camera_mode", 0)
    draw_fog = config.get("draw_fog", False)
    fog_color = numpy.array([0.1, 0.2, 0.3])
    # Compute physical distance to furthest loaded chunk corner
    max_visible_dist = (chunk_size - 1) * (load_radius + 0.5)
    fog_start = max_visible_dist * 0.6   # 13.5
    fog_end = max_visible_dist * 0.9     # 20.25

    audio = Audio()

    player = Player(db_path, height=player_height)

    if spawn_mode == "random":
        rand_x = random.uniform(-random_range, random_range)
        rand_z = random.uniform(-random_range, random_range)
        rand_y = get_height(rand_x, rand_z) + player.height
        player.position = (rand_x, rand_y, rand_z)
    elif spawn_mode == "portal":
        if player.portal_position != (0.0, 0.0, 0.0):
            player.position = player.portal_position
        else:
            if player.position == (0.0, 0.0, 0.0):
                rand_x = random.uniform(-random_range, random_range)
                rand_z = random.uniform(-random_range, random_range)
                rand_y = get_height(rand_x, rand_z) + player.height
                player.position = (rand_x, rand_y, rand_z)

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

    camera = Camera(player=player, mode=camera_mode,
                    mouse_sensitivity=mouse_sensitivity,
                    movement_speed=movement_speed)

    def change_rotation_handler(value):
        camera.rotate_only_horizontal = value
        audio.play_random_thread(duration=1.0, volume=0.5, mode='sweep', min_freq=300, max_freq=1500)

    player.change_rotation_handler = change_rotation_handler

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
              snow_draw=snow_draw,
              day_duration=day_duration,
              draw_fog=draw_fog,
              fog_color=fog_color,
              fog_start=fog_start,
              fog_end=fog_end)

    shader_3d = Shader(VERTEX_SHADER_SRC, FRAGMENT_SHADER_SRC)
    shader_crosshair = Shader(CROSSHAIR_VERT_SRC, CROSSHAIR_FRAG_SRC)

    health_manager = HealthManager(player, chunk_manager,
                                chunk_size=chunk_size, spacing=terrain_spacing)

    mob_manager = MobManager(player, chunk_manager,
                             chunk_size=chunk_size, spacing=terrain_spacing)
    player.set_mob_manager(mob_manager)

    player_model = PlayerModel(shader_3d)
    player.set_model(player_model)

    tree_manager = TreeManager(chunk_manager, chunk_size=chunk_size, spacing=terrain_spacing)

    targets = []
    for _ in range(TARGET_COUNT):
        x = random.uniform(-50, 50)
        z = random.uniform(-50, 50)
        targets.append(Target(camera.get_target_position(x, z)))

    proj = compute_projection(screen.width, screen.height)

    crosshair_verts = numpy.array([-10.0, 0.0, 10.0, 0.0, 0.0, -10.0, 0.0, 10.0], dtype=numpy.float32)
    crosshair_vao = glGenVertexArrays(1)
    crosshair_vbo = glGenBuffers(1)
    glBindVertexArray(crosshair_vao)
    glBindBuffer(GL_ARRAY_BUFFER, crosshair_vbo)
    glBufferData(GL_ARRAY_BUFFER, crosshair_verts.nbytes, crosshair_verts, GL_STATIC_DRAW)
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 8, ctypes.c_void_p(0))
    glEnableVertexAttribArray(0)
    glBindVertexArray(0)

    Ammo.init_geometry()
    weapon = Weapon(player, damage=25, ammo_speed=35.0, ammo_range=60.0, cooldown=0.3)
    player.set_weapon(weapon)
    ammo_list = [] # Create a list for active ammo

    compass = Compass(screen.width, screen.height, camera, draw_compass, compass_scale)
    stats_panel = StatsPanel(screen.width, screen.height, draw_stats)
    menu = Menu(screen.width, screen.height, config, camera)
    fps_overlay = FPSOverlay(screen.width, screen.height, config.get("show_fps", False))

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

    def key_callback(window, key, scancode, action, mods):
        if action == glfw.RELEASE:
            keys[key] = False
            if key == glfw.KEY_ESCAPE:
                glfw.set_window_should_close(window, True)
        elif action == glfw.PRESS:
            keys[key] = True
            if key == glfw.KEY_F9:
                menu.active = not menu.active
                if menu.active:
                    glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_NORMAL)
                else:
                    glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_DISABLED)
            elif key == glfw.KEY_V:
                if camera.mode == 1:
                    ground_y = get_height(player.position[0], player.position[2])
                    eye_y = ground_y + player.height
                    camera.position = numpy.array([player.position[0], eye_y, player.position[2]])
                    camera.update_vectors()   # recalc front/right/up from current yaw/pitch
                camera.set_mode(1 - camera.mode)
            elif key == glfw.KEY_F10:
                compass.enabled = not compass.enabled
            elif key == glfw.KEY_F11:
                stats_panel.enabled = not stats_panel.enabled
            elif key == glfw.KEY_F12:
                fps_overlay.enabled = not fps_overlay.enabled
                config["show_fps"] = fps_overlay.enabled
                Config.save(config) # persist

    def mouse_button_callback(window, button, action, mods):
        if button == glfw.MOUSE_BUTTON_LEFT and action == glfw.PRESS:
            if menu.active:
                xpos, ypos = glfw.get_cursor_pos(window)
                menu.handle_mouse(xpos, ypos, button)
                return

            weapon_pos = player.position

            # Determine shooting direction based on camera mode
            if camera.mode == 1:
                # Third‑person: shoot away from camera (opposite of camera's forward)
                ray_dir = -camera.front
                offset = player.weapon.offset
                c, s = math.cos(player.yaw), math.sin(player.yaw)
                world_offset = numpy.array([
                    offset[0] * c - offset[2] * s,
                    offset[1],
                    offset[0] * s + offset[2] * c
                ])
                weapon_pos += world_offset
            else:
                # First‑person: shoot where camera is looking
                ray_dir = camera.front

            # Optional target handling (kept for compatibility)
            for target in targets:
                if target.active and target.hit(camera.position, ray_dir):
                    target.active = False
                    target.position = camera.get_target_position()
                    target.active = True
                    break

            # Spawn ammo from weapon position
            ammo = player.weapon.shoot(weapon_pos, ray_dir, glfw.get_time())
            if ammo:
                ammo_list.append(ammo)

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
    last_move_dir = numpy.array([0.0, 0.0, 0.0])

    while not glfw.window_should_close(window):
        prev_player_pos = numpy.array(player.position)
        current_time = glfw.get_time()
        dt = current_time - last_time
        last_time = current_time

        view, forward = camera.update(keys, dt)

        # ----- Update world (chunks, sky, etc.) -----
        chunk_manager.update(camera.position)
        health_manager.update(dt)
        mob_manager.update(dt)
        tree_manager.update(camera.position)
        sky.update(dt)
        light_dir, light_intensity = sky.get_combined_light()

        # Update ammo
        for ammo in ammo_list[:]:
            ammo.update(dt)
            if not ammo.active:
                ammo_list.remove(ammo)
                continue
            # Use spatial grid for collision
            nearby_mobs = mob_manager.get_nearby_mobs(ammo.position, ammo.range + 0.5)
            for mob in nearby_mobs:
                if not mob.is_alive():
                    continue
                dist = numpy.linalg.norm(mob.position - ammo.position)
                if dist < 0.5 + 0.5:  # ammo radius 0.5, mob radius 0.5
                    if mob.take_damage(ammo.damage): # check mob is died
                        player.add_kill()
                        audio.play_random_thread(duration=0.5, volume=0.3, mode='noise')
                        mob_manager.dismantle_mob(mob, ammo.position, 1.0)
                    mob_manager.add_particles(ammo.position, count=12)
                    ammo.active = False
                    break

        player.speed = numpy.linalg.norm(numpy.array(player.position) - prev_player_pos) / dt if dt > 0 else 0.0

        if stats_panel.enabled:
            stats_panel.update(
                position=player.position,
                speed=player.speed,
                level=player.level,
                life=player.life,
                mana=player.mana,
                weapon_name=player.weapon_name,
                ammo_count=player.ammo_count,
                killed_mobs=player.killed_mobs,
                familiar_name=player.familiar_name
            )

        # ----- Rendering -----
        glClearColor(0.1, 0.2, 0.3, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        shader_3d.use()
        shader_3d.set_mat4("uView", view)
        shader_3d.set_mat4("uProjection", proj)
        shader_3d.set_vec3("uLightDir", light_dir)
        shader_3d.set_float("uLightIntensity", light_intensity)
        # Fog settings
        shader_3d.set_vec3("uCameraPos", camera.position)
        if draw_fog:
            shader_3d.set_vec3("uFogColor", fog_color)
            shader_3d.set_float("uFogStart", fog_start)
            shader_3d.set_float("uFogEnd", fog_end)
        else:
            shader_3d.set_vec3("uFogColor", fog_color)   # any color, won't be used
            shader_3d.set_float("uFogStart", 1e9)
            shader_3d.set_float("uFogEnd", 2e9)

        sky.draw_background(view, proj, camera.position, glfw.get_time(), screen.width, screen.height)

        shader_3d.use()
        chunk_manager.draw(shader_3d)
        health_manager.draw(view, proj, light_dir, light_intensity)
        mob_manager.draw(view, proj, light_dir, light_intensity, screen.width, screen.height)
        tree_manager.draw(view, proj, light_dir, light_intensity, camera.position)

        for target in targets:
            target.draw(shader_3d, view, proj, light_dir)

        if camera.mode == 1: # Draw player model in third‑person
            if numpy.linalg.norm(last_move_dir) > 0.1:
                facing = last_move_dir
            else: # When stationary, face forward (away from camera)
                facing = numpy.array([forward[0], 0.0, forward[2]])
                if numpy.linalg.norm(facing) < 0.1:
                    facing = numpy.array([0.0, 0.0, 1.0])
                facing = facing / numpy.linalg.norm(facing)
            player.yaw = math.atan2(facing[0], facing[2])
            # Draw weapon
            player.draw(view, proj, light_dir, light_intensity)

        for ammo in ammo_list:
            ammo.draw(view, proj)

        sky.draw_foreground(view, proj, camera.position, glfw.get_time())

        # Crosshair
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
        fps_overlay.draw(dt)

        glfw.swap_buffers(window)
        glfw.poll_events()

    chunk_manager.save_all_chunks()
    mob_manager.shutdown()
    health_manager.shutdown()
    tree_manager.shutdown()
    chunk_manager.shutdown()
    player.save()
    glfw.terminate()

if __name__ == "__main__":
    main()
