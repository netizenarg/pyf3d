import numpy
import math
from OpenGL.GL import *
import ctypes

from shaders.shader import Shader
from shaders.ammo_shdr import AMMO_VERTEX_SHADER_SRC, AMMO_FRAGMENT_SHADER_SRC
from shaders.weapon_shdr import WEAPON_VERTEX_SHADER_SRC, WEAPON_FRAGMENT_SHADER_SRC


class Ammo:
    """Projectile that flies forward, collides with mobs, then disappears."""
    _vao = None
    _vbo = None
    _ebo = None
    _index_count = 0

    @staticmethod
    def _generate_sphere(radius=0.5, sectors=16, stacks=16):
        vertices = []
        indices = []
        for i in range(stacks + 1):
            stack_angle = math.pi / 2 - i * math.pi / stacks
            xy = radius * math.cos(stack_angle)
            z = radius * math.sin(stack_angle)
            for j in range(sectors + 1):
                sector_angle = j * 2 * math.pi / sectors
                x = xy * math.cos(sector_angle)
                y = xy * math.sin(sector_angle)
                vertices.extend([x, y, z])
        for i in range(stacks):
            k1 = i * (sectors + 1)
            k2 = (i + 1) * (sectors + 1)
            for j in range(sectors):
                if i != 0:
                    indices.extend([k1 + j, k1 + j + 1, k2 + j])
                if i != stacks - 1:
                    indices.extend([k1 + j + 1, k2 + j + 1, k2 + j])
        return numpy.array(vertices, dtype=numpy.float32), numpy.array(indices, dtype=numpy.uint32)

    def __init__(self, position, direction, speed=30.0, range=50.0, damage=25):
        self.position = numpy.array(position, dtype=float)
        self.direction = numpy.array(direction, dtype=float)
        norm = numpy.linalg.norm(self.direction)
        if norm > 0:
            self.direction /= norm
        self.speed = speed
        self.range = range
        self.damage = damage
        self.traveled = 0.0
        self.active = True
        self.size = 0.2
        self.shader = Shader(AMMO_VERTEX_SHADER_SRC, AMMO_FRAGMENT_SHADER_SRC)

    def update(self, dt):
        if not self.active:
            return
        step = self.direction * self.speed * dt
        self.position += step
        self.traveled += self.speed * dt
        if self.traveled >= self.range:
            self.active = False

    def get_collision_sphere(self):
        return (self.position, self.size)

    def draw(self, view, proj):
        if not self.active:
            return
        model = numpy.eye(4, dtype=numpy.float32)
        model[0, 3] = self.position[0]
        model[1, 3] = self.position[1]
        model[2, 3] = self.position[2]
        scale = self.size
        model[0, 0] = model[1, 1] = model[2, 2] = scale
        self.shader.use()
        self.shader.set_mat4("uModel", model)
        self.shader.set_mat4("uView", view)
        self.shader.set_mat4("uProjection", proj)
        glBindVertexArray(self._vao)
        glDrawElements(GL_TRIANGLES, self._index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    @classmethod
    def init_geometry(cls):
        vertices, indices = cls._generate_sphere(radius=0.5, sectors=24, stacks=24)
        cls._vao = glGenVertexArrays(1)
        cls._vbo = glGenBuffers(1)
        cls._ebo = glGenBuffers(1)
        glBindVertexArray(cls._vao)
        glBindBuffer(GL_ARRAY_BUFFER, cls._vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, cls._ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)
        cls._index_count = len(indices)


class Weapon:
    """Gun held by the player, shoots ammo."""
    def __init__(self, player, damage=25, ammo_speed=30.0, ammo_range=50.0, cooldown=0.3):
        self.player = player
        self.damage = damage
        self.ammo_speed = ammo_speed
        self.ammo_range = ammo_range
        self.cooldown = cooldown
        self.last_shot_time = 0.0
        # Right hand offset in local coordinates (x: right, y: up, z: forward)
        self.offset = numpy.array([0.65, 1.5, 0.3])
        self.size = 0.3
        self._init_model()
        self.texture = self._create_stripe_texture()
        self.weapon_shader = Shader(WEAPON_VERTEX_SHADER_SRC, WEAPON_FRAGMENT_SHADER_SRC)

    def _create_stripe_texture(self):
        size = 64
        stripe_height = 8
        tex_data = numpy.zeros((size, size, 3), dtype=numpy.uint8)
        for y in range(size):
            color = [180, 180, 180]  # light grey
            if (y // stripe_height) % 2 == 1:
                color = [40, 40, 40]   # dark grey/black
            tex_data[y, :] = color
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, size, size, 0, GL_RGB, GL_UNSIGNED_BYTE, tex_data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glBindTexture(GL_TEXTURE_2D, 0)
        return tex_id

    def _init_model(self):
        vertices = numpy.array([
            # front face (z = +0.5)
            -0.5, -0.5,  0.5,  0, 0,
             0.5, -0.5,  0.5,  1, 0,
             0.5,  0.5,  0.5,  1, 1,
            -0.5,  0.5,  0.5,  0, 1,
            # back face (z = -0.5)
            -0.5, -0.5, -0.5,  0, 0,
             0.5, -0.5, -0.5,  1, 0,
             0.5,  0.5, -0.5,  1, 1,
            -0.5,  0.5, -0.5,  0, 1,
            # left face (x = -0.5)
            -0.5, -0.5, -0.5,  0, 0,
            -0.5, -0.5,  0.5,  1, 0,
            -0.5,  0.5,  0.5,  1, 1,
            -0.5,  0.5, -0.5,  0, 1,
            # right face (x = +0.5)
             0.5, -0.5, -0.5,  0, 0,
             0.5, -0.5,  0.5,  1, 0,
             0.5,  0.5,  0.5,  1, 1,
             0.5,  0.5, -0.5,  0, 1,
            # top face (y = +0.5)
            -0.5,  0.5, -0.5,  0, 0,
             0.5,  0.5, -0.5,  1, 0,
             0.5,  0.5,  0.5,  1, 1,
            -0.5,  0.5,  0.5,  0, 1,
            # bottom face (y = -0.5)
            -0.5, -0.5, -0.5,  0, 0,
             0.5, -0.5, -0.5,  1, 0,
             0.5, -0.5,  0.5,  1, 1,
            -0.5, -0.5,  0.5,  0, 1,
        ], dtype=numpy.float32)

        indices = numpy.array([
            0,1,2, 0,2,3,       # front
            4,5,6, 4,6,7,       # back
            8,9,10, 8,10,11,    # left
            12,13,14, 12,14,15, # right
            16,17,18, 16,18,19, # top
            20,21,22, 20,22,23  # bottom
        ], dtype=numpy.uint32)

        self.model_vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        ebo = glGenBuffers(1)
        glBindVertexArray(self.model_vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 5*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 5*4, ctypes.c_void_p(3*4))
        glEnableVertexAttribArray(1)
        glBindVertexArray(0)
        self.model_index_count = len(indices)

    def shoot(self, origin, direction, current_time):
        if current_time - self.last_shot_time < self.cooldown:
            return None
        self.last_shot_time = current_time
        return Ammo(origin, direction, self.ammo_speed, self.ammo_range, self.damage)

    def draw(self, view, proj, parent_matrix, local_offset):
        """Draw weapon using parent's model matrix and local offset."""
        # Build local transform for the hand (translation + optional rotation)
        local = numpy.eye(4, dtype=numpy.float32)
        local[0, 3] = local_offset[0]
        local[1, 3] = local_offset[1]
        local[2, 3] = local_offset[2]
        # Optionally rotate weapon to align with hand (if needed)
        # Here we assume weapon's forward is +Z, which matches player's forward after parent rotation.
        # So just multiply parent * local.
        model = parent_matrix @ local
        # Apply scale
        scale = self.size
        scale_mat = numpy.eye(4, dtype=numpy.float32)
        scale_mat[0, 0] = scale
        scale_mat[1, 1] = scale
        scale_mat[2, 2] = scale
        model = model @ scale_mat
        self.weapon_shader.use()
        self.weapon_shader.set_mat4("uModel", model)
        self.weapon_shader.set_mat4("uView", view)
        self.weapon_shader.set_mat4("uProjection", proj)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glUniform1i(glGetUniformLocation(self.weapon_shader.program, "uTexture"), 0)
        glBindVertexArray(self.model_vao)
        glDrawElements(GL_TRIANGLES, self.model_index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
