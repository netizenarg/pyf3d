import glfw
import logging
import math
import numpy
import random

def get_height(x, z):
    return (math.sin(x * 0.1) * math.cos(z * 0.1) +
            0.3 * math.sin(x * 0.3 + 1.2) +
            0.3 * math.cos(z * 0.3 + 2.4) +
            0.2 * math.sin((x * 0.6 + z * 0.4) * 0.8)) * 2.0 + 0.5

def _hash_coord(x: int, z: int, seed: int) -> float:
    h = (x * 374761393 + z * 668265263 + seed) & 0xFFFFFFFF
    h = (h ^ (h >> 16)) & 0xFFFFFFFF
    h = (h * 0x85ebca6b) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) & 0xFFFFFFFF
    h = (h * 0xc2b2ae35) & 0xFFFFFFFF
    h = (h ^ (h >> 16)) & 0xFFFFFFFF
    return (h & 0x7FFFFFFF) / 0x7FFFFFFF

def _smoothstep(t: float) -> float:
    return t * t * t * (t * (t * 6 - 15) + 10)

def get_height_seed(x: float, z: float, seed: int = 0) -> float:
    """Terrain height function. Uses 4 octaves of value noise."""
    def noise(ix: int, iz: int) -> float:
        return _hash_coord(ix, iz, seed)
    def interp(xx: float, zz: float) -> float:
        x0 = math.floor(xx)
        z0 = math.floor(zz)
        fx = xx - x0
        fz = zz - z0
        ux = _smoothstep(fx)
        uz = _smoothstep(fz)
        v00 = noise(x0, z0)
        v10 = noise(x0 + 1, z0)
        v01 = noise(x0, z0 + 1)
        v11 = noise(x0 + 1, z0 + 1)
        return (v00 * (1 - ux) + v10 * ux) * (1 - uz) + (v01 * (1 - ux) + v11 * ux) * uz
    h = 0.0
    freq = 0.02
    amp = 1.0
    for _ in range(4):
        h += interp(x * freq, z * freq) * amp
        freq *= 2
        amp *= 0.5
    return h * 12.0 - 2.0


class Camera:
    def __init__(self, player=None, yaw=0, mouse_sensitivity=0.002, movement_speed=10.0, mode=0):
        self.mode = mode  # 0 = first‑person, 1 = third‑person
        self.player = player
        self.position = numpy.array([self.player.position[0], self.player.position[1], self.player.position[2]])
        self.yaw = yaw
        self.pitch = 0.0
        self.distance = 9.0 # Third‑person distance from player
        self.height_offset = 5.0 # Vertical offset above the orbit point
        self.rotate_only_horizontal = True if self.player.level < 2 else False
        if self.mode == 1:
            self.pitch = 20.0
            self.rotate_only_horizontal = False
        self.front = numpy.array([0.0, 0.0, -1.0])
        self.up = numpy.array([0.0, 1.0, 0.0])
        self.right = numpy.array([1.0, 0.0, 0.0])
        self.mouse_sensitivity = mouse_sensitivity
        self.movement_speed = movement_speed
        self.update_vectors()
        self.adjust_height()

    def change_rotation_horizontal(self, value):
        self.rotate_only_horizontal = value

    def update_vectors(self):
        front = numpy.array([
            math.cos(math.radians(self.yaw)) * math.cos(math.radians(self.pitch)),
            math.sin(math.radians(self.pitch)),
            math.sin(math.radians(self.yaw)) * math.cos(math.radians(self.pitch))
        ])
        self.front = front / numpy.linalg.norm(front)
        world_up = numpy.array([0.0, 1.0, 0.0])
        self.right = numpy.cross(self.front, world_up)
        if numpy.linalg.norm(self.right) < 0.001:
            self.right = numpy.array([1.0, 0.0, 0.0])
        else:
            self.right /= numpy.linalg.norm(self.right)
        self.up = numpy.cross(self.right, self.front)
        self.up /= numpy.linalg.norm(self.up)

    def set_mode(self, value=0):
        self.mode = value
        if self.mode == 1:
            self.rotate_only_horizontal = False
        else:
            self.rotate_only_horizontal = True if self.player.level < 2 else False
            self.pitch = 0.0
            self.up = numpy.array([0.0, 1.0, 0.0])
        self.update_vectors()

    def adjust_height(self):
        ground_y = get_height(self.position[0], self.position[2])
        if self.mode == 1:
            self.position[1] = ground_y + self.player.height + self.distance + self.height_offset
        else:
            self.position[1] = ground_y + self.player.height

    def process_mouse(self, dx, dy):
        self.yaw += dx * self.mouse_sensitivity
        if not self.rotate_only_horizontal:
            self.pitch += dy * self.mouse_sensitivity
            if self.mode == 1:
                if self.pitch > 80.0:
                    self.pitch = 80.0
                if self.pitch < 10.0:
                    self.pitch = 10.0
            else:
                if self.pitch > 89.0:
                    self.pitch = 89.0
                if self.pitch < -89.0:
                    self.pitch = -89.0
        if self.rotate_only_horizontal:
            self.pitch = 0.0
        self.update_vectors()

    def process_keyboard(self, keys, dt, forward=None):
        """Movement handling for both modes."""
        if self.mode == 1:
            # Third‑person: move the player relative to camera direction
            cam_right = numpy.cross(forward, numpy.array([0, 1, 0]))
            if numpy.linalg.norm(cam_right) > 0:
                cam_right /= numpy.linalg.norm(cam_right)
            speed = self.movement_speed * dt
            move = numpy.array([0.0, 0.0, 0.0])
            if keys.get(glfw.KEY_W, False):
                move += forward
            if keys.get(glfw.KEY_S, False):
                move -= forward
            if keys.get(glfw.KEY_A, False):
                move -= cam_right
            if keys.get(glfw.KEY_D, False):
                move += cam_right
            if numpy.linalg.norm(move) > 0:
                move = move / numpy.linalg.norm(move)
            new_pos = numpy.array(self.player.position) + move * speed
            new_pos[1] = get_height(new_pos[0], new_pos[2])
            self.player.position = tuple(new_pos)
        else:
            # First‑person: move the camera, player follows
            speed = self.movement_speed * dt
            if keys.get(glfw.KEY_W, False):
                self.position += self.front * speed
            if keys.get(glfw.KEY_S, False):
                self.position -= self.front * speed
            if keys.get(glfw.KEY_A, False):
                self.position -= self.right * speed
            if keys.get(glfw.KEY_D, False):
                self.position += self.right * speed
            self.player.position = (self.position[0], self.position[1], self.position[2])
        self.adjust_height()

    def get_view_matrix(self):
        f = self.front
        u = self.up
        s = self.right
        pos = self.position
        view = numpy.eye(4)
        view[0, 0] = s[0]
        view[0, 1] = s[1]
        view[0, 2] = s[2]
        view[1, 0] = u[0]
        view[1, 1] = u[1]
        view[1, 2] = u[2]
        view[2, 0] = -f[0]
        view[2, 1] = -f[1]
        view[2, 2] = -f[2]
        view[0, 3] = -numpy.dot(s, pos)
        view[1, 3] = -numpy.dot(u, pos)
        view[2, 3] = numpy.dot(f, pos)
        return view

    def look_at(self, eye, target, up):
        f = target - eye
        f = f / numpy.linalg.norm(f)
        s = numpy.cross(f, up)
        s = s / numpy.linalg.norm(s)
        u = numpy.cross(s, f)
        view = numpy.eye(4)
        view[0,0] = s[0]; view[0,1] = s[1]; view[0,2] = s[2]; view[0,3] = -numpy.dot(s, eye)
        view[1,0] = u[0]; view[1,1] = u[1]; view[1,2] = u[2]; view[1,3] = -numpy.dot(u, eye)
        view[2,0] = -f[0]; view[2,1] = -f[1]; view[2,2] = -f[2]; view[2,3] = numpy.dot(f, eye)
        view[3,3] = 1.0
        return view

    def get_target_position(self, x=None, z=None):
        if x is None:
            x = random.uniform(self.position[0] - 50, self.position[0] + 50)
        if z is None:
            z = random.uniform(self.position[2] - 50, self.position[2] + 50)
        y = get_height(x, z)
        return numpy.array([x, y, z])

    def update(self, keys, dt):
        view, forward = None, None
        if self.mode == 1:
            # Third‑person: camera orbits around the player
            yaw_rad = math.radians(self.yaw)
            pitch_rad = math.radians(self.pitch)
            cam_dir = numpy.array([
                math.cos(yaw_rad) * math.cos(pitch_rad),
                math.sin(pitch_rad),
                math.sin(yaw_rad) * math.cos(pitch_rad)
            ])
            cam_pos = numpy.array(self.player.position) + cam_dir * self.distance
            cam_pos[1] += self.height_offset # Apply vertical offset only
            # Clamp to ground
            ground_y = get_height(cam_pos[0], cam_pos[2])
            if cam_pos[1] < ground_y + 0.5:
                cam_pos[1] = ground_y + 0.5
            self.position = cam_pos
            view = self.look_at(cam_pos, numpy.array(self.player.position), numpy.array([0, 1, 0]))
            # Horizontal direction for movement
            cam_dir_horiz = numpy.array([cam_dir[0], 0.0, cam_dir[2]])
            if numpy.linalg.norm(cam_dir_horiz) > 0:
                cam_dir_horiz /= numpy.linalg.norm(cam_dir_horiz)
            forward = -cam_dir_horiz
            self.process_keyboard(keys, dt, forward)
        else:
            # First‑person: camera moves itself, player follows
            self.process_keyboard(keys, dt)
            view = self.get_view_matrix()
        return view, forward
