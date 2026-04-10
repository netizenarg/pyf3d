import numpy
import math
import random
import ctypes

from OpenGL.GL import *

from camera import get_height
from shaders.shader import Shader
from shaders.stone_shdr import STONE_VERTEX_SHADER, STONE_FRAGMENT_SHADER


class StoneGeometry:
    _instance = None
    _vao = None
    _vertex_count = 0

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if StoneGeometry._vao is not None:
            return

        base_vertices = numpy.array([
            [-0.4, -0.4,  0.4],
            [ 0.4, -0.4,  0.4],
            [ 0.4,  0.4,  0.4],
            [-0.4,  0.4,  0.4],
            [-0.4, -0.4, -0.4],
            [ 0.4, -0.4, -0.4],
            [ 0.4,  0.4, -0.4],
            [-0.4,  0.4, -0.4],
        ], dtype=numpy.float32)

        rng = random.Random(12345)
        vertices = base_vertices.copy()
        for i in range(len(vertices)):
            dx = rng.uniform(-0.15, 0.15)
            dy = rng.uniform(-0.15, 0.15)
            dz = rng.uniform(-0.15, 0.15)
            vertices[i] += [dx, dy, dz]

        indices = numpy.array([
            0,1,2, 0,2,3,
            4,5,6, 4,6,7,
            0,3,7, 0,7,4,
            1,2,6, 1,6,5,
            3,2,6, 3,6,7,
            0,1,5, 0,5,4
        ], dtype=numpy.uint32)

        StoneGeometry._vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        ebo = glGenBuffers(1)

        glBindVertexArray(StoneGeometry._vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)

        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)

        glBindVertexArray(0)
        StoneGeometry._vertex_count = len(indices)

    @classmethod
    def get_vao(cls):
        return cls._vao

    @classmethod
    def get_vertex_count(cls):
        return cls._vertex_count


class Stone:
    def __init__(self, base_x, base_z, rotation_y=None):
        self.base_x = base_x
        self.base_z = base_z
        self.rotation_y = rotation_y if rotation_y is not None else random.uniform(0, 360)
        self.geometry = StoneGeometry.get_instance()
        shade = random.uniform(0.4, 0.7)
        self.color = numpy.array([shade, shade, shade], dtype=numpy.float32)
        self.scale_x = random.uniform(0.7, 1.3)
        self.scale_y = random.uniform(0.5, 1.2)
        self.scale_z = random.uniform(0.7, 1.3)

        # Precompute the model matrix (scale -> rotate -> translate)
        y = get_height(self.base_x, self.base_z)  # fixed Y position
        rad = math.radians(self.rotation_y)
        c = math.cos(rad)
        s = math.sin(rad)

        # Scale matrix
        scale = numpy.eye(4, dtype=numpy.float32)
        scale[0, 0] = self.scale_x
        scale[1, 1] = self.scale_y
        scale[2, 2] = self.scale_z

        # Rotation matrix
        rot = numpy.eye(4, dtype=numpy.float32)
        rot[0, 0] = c
        rot[0, 2] = s
        rot[2, 0] = -s
        rot[2, 2] = c

        # Combine: model = rot @ scale
        self.model = numpy.dot(rot, scale)
        # Apply translation
        self.model[0, 3] = self.base_x
        self.model[1, 3] = y
        self.model[2, 3] = self.base_z

    def draw(self, shader, view, projection):
        shader.use()
        shader.set_mat4("uView", view)
        shader.set_mat4("uProjection", projection)
        shader.set_mat4("uModel", self.model)
        shader.set_vec3("uColor", self.color)

        glBindVertexArray(self.geometry.get_vao())
        glDrawElements(GL_TRIANGLES, self.geometry.get_vertex_count(), GL_UNSIGNED_INT, None)
        glBindVertexArray(0)


class StoneManager:
    def __init__(self, chunk_manager, chunk_size=16, spacing=1.0):
        self.chunk_manager = chunk_manager
        self.shader = Shader(STONE_VERTEX_SHADER, STONE_FRAGMENT_SHADER)
        self.stones = {}
        self.loaded_chunks = set()

    def update(self):
        current_chunks = set(self.chunk_manager.chunks.keys())
        # Remove stones for unloaded chunks
        for chunk_key in list(self.loaded_chunks):
            if chunk_key not in current_chunks:
                self.stones.pop(chunk_key, None)
                self.loaded_chunks.discard(chunk_key)
        # Add stones for newly loaded chunks
        for chunk_key in current_chunks:
            if chunk_key not in self.loaded_chunks:
                chunk = self.chunk_manager.chunks[chunk_key]
                stones_list = []
                for stone_data in chunk.stones:
                    stone = Stone(
                        stone_data['x'],
                        stone_data['z'],
                        rotation_y=stone_data.get('rotation_y')
                    )
                    stones_list.append(stone)
                self.stones[chunk_key] = stones_list
                self.loaded_chunks.add(chunk_key)

    def draw(self, view, projection, light_dir, light_intensity):
        for stones_list in self.stones.values():
            for stone in stones_list:
                stone.draw(self.shader, view, projection)

    def shutdown(self):
        self.stones.clear()
        self.loaded_chunks.clear()
