import glfw
import math
import numpy
import random

def get_height(x, z):
    return (math.sin(x * 0.1) * math.cos(z * 0.1) +
            0.3 * math.sin(x * 0.3 + 1.2) +
            0.3 * math.cos(z * 0.3 + 2.4) +
            0.2 * math.sin((x * 0.6 + z * 0.4) * 0.8)) * 2.0 + 0.5

class Camera:
    def __init__(self, position=None, mouse_sensitivity=0.002, movement_speed=10.0, player_height=1.5):
        if position is None:
            position = numpy.array([0.0, player_height, 0.0])
        self.position = position
        self.yaw = -90.0
        self.pitch = 0.0
        self.front = numpy.array([0.0, 0.0, -1.0])
        self.up = numpy.array([0.0, 1.0, 0.0])
        self.right = numpy.array([1.0, 0.0, 0.0])
        self.mouse_sensitivity = mouse_sensitivity
        self.movement_speed = movement_speed
        self.player_height = player_height
        self.update_vectors()

    def update_vectors(self):
        front = numpy.array([
            math.cos(math.radians(self.yaw)) * math.cos(math.radians(self.pitch)),
            math.sin(math.radians(self.pitch)),
            math.sin(math.radians(self.yaw)) * math.cos(math.radians(self.pitch))
        ])
        self.front = front / numpy.linalg.norm(front)
        self.right = numpy.cross(self.front, self.up)
        self.right /= numpy.linalg.norm(self.right)
        self.up = numpy.cross(self.right, self.front)
        self.up /= numpy.linalg.norm(self.up)

    def process_mouse(self, dx, dy):
        self.yaw += dx * self.mouse_sensitivity
        self.pitch += dy * self.mouse_sensitivity
        if self.pitch > 89.0:
            self.pitch = 89.0
        if self.pitch < -89.0:
            self.pitch = -89.0
        self.update_vectors()

    def process_keyboard(self, keys, dt):
        speed = self.movement_speed * dt
        # Store old position for potential collision recovery (optional)
        old_pos = self.position.copy()

        # Apply movement
        if keys.get(glfw.KEY_W, False):
            self.position += self.front * speed
        if keys.get(glfw.KEY_S, False):
            self.position -= self.front * speed
        if keys.get(glfw.KEY_A, False):
            self.position -= self.right * speed
        if keys.get(glfw.KEY_D, False):
            self.position += self.right * speed

        # Adjust Y to terrain height
        self.adjust_height()

    def adjust_height(self):
        """Set the camera's Y position to ground + player height."""
        ground_y = get_height(self.position[0], self.position[2])
        self.position[1] = ground_y + self.player_height

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

    def get_target_position(self, x=None, z=None):
        if x is None:
            x = random.uniform(self.position[0] - 50, self.position[0] + 50)
        if z is None:
            z = random.uniform(self.position[2] - 50, self.position[2] + 50)
        y = get_height(x, z)
        return numpy.array([x, y, z])