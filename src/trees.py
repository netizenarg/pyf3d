import numpy
import math
import random
import ctypes

from OpenGL.GL import *

from camera import get_height
from shaders.shader import Shader
from shaders.tree_shdr import TREE_VERTEX_SHADER_SRC, TREE_FRAGMENT_SHADER_SRC


class TreeGeometry:
    _instance = None
    _trunk_vao = None
    _trunk_vertex_count = 0
    _foliage_vao = None
    _foliage_vertex_count = 0
    _trunk_texture = None
    _foliage_texture = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if TreeGeometry._trunk_vao is not None:
            return
        self._build_trunk_cylinder()
        self._build_foliage_sphere()
        self._create_textures()

    def _build_trunk_cylinder(self, radius=0.3, height=1.5, segments=12):
        vertices = []  # each vertex: pos(3), normal(3), texcoord(2)
        indices = []

        for i in range(segments + 1):
            angle = 2 * math.pi * i / segments
            x = radius * math.cos(angle)
            z = radius * math.sin(angle)
            nx = math.cos(angle)
            nz = math.sin(angle)
            u = i / segments
            # bottom vertex
            vertices.append([x, 0.0, z, nx, 0, nz, u, 1.0])
            # top vertex
            vertices.append([x, height, z, nx, 0, nz, u, 0.0])

        for i in range(segments):
            i0 = i * 2
            i1 = i0 + 1
            i2 = (i + 1) * 2
            i3 = i2 + 1
            indices.extend([i0, i1, i2, i1, i3, i2])

        # Bottom cap
        center_idx = len(vertices)
        vertices.append([0, 0.0, 0, 0, -1, 0, 0.5, 0.5])
        for i in range(segments):
            i0 = i * 2
            i1 = ((i + 1) % segments) * 2
            indices.extend([center_idx, i0, i1])

        # Top cap
        center_idx = len(vertices)
        vertices.append([0, height, 0, 0, 1, 0, 0.5, 0.5])
        for i in range(segments):
            i0 = i * 2 + 1
            i1 = ((i + 1) % segments) * 2 + 1
            indices.extend([center_idx, i1, i0])

        vertices_arr = numpy.array(vertices, dtype=numpy.float32).flatten()
        indices_arr = numpy.array(indices, dtype=numpy.uint32)

        TreeGeometry._trunk_vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        ebo = glGenBuffers(1)

        glBindVertexArray(TreeGeometry._trunk_vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices_arr.nbytes, vertices_arr, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices_arr.nbytes, indices_arr, GL_STATIC_DRAW)

        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 8*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 8*4, ctypes.c_void_p(3*4))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, 8*4, ctypes.c_void_p(6*4))
        glEnableVertexAttribArray(2)

        glBindVertexArray(0)
        TreeGeometry._trunk_vertex_count = len(indices)

    def _build_foliage_sphere(self, radius=0.6, stacks=16, slices=16):
        vertices = []
        indices = []

        for i in range(stacks + 1):
            theta = math.pi * i / stacks
            sin_theta = math.sin(theta)
            cos_theta = math.cos(theta)
            v = 1.0 - (i / stacks)
            for j in range(slices + 1):
                phi = 2 * math.pi * j / slices
                sin_phi = math.sin(phi)
                cos_phi = math.cos(phi)
                u = j / slices
                x = radius * sin_theta * cos_phi
                y = radius * cos_theta
                z = radius * sin_theta * sin_phi
                nx = x / radius
                ny = y / radius
                nz = z / radius
                norm = math.sqrt(nx*nx + ny*ny + nz*nz)
                if norm > 0:
                    nx /= norm
                    ny /= norm
                    nz /= norm
                vertices.append([x, y, z, nx, ny, nz, u, v])

        for i in range(stacks):
            for j in range(slices):
                i0 = i * (slices + 1) + j
                i1 = i0 + 1
                i2 = (i + 1) * (slices + 1) + j
                i3 = i2 + 1
                indices.extend([i0, i2, i1, i1, i2, i3])

        vertices_arr = numpy.array(vertices, dtype=numpy.float32).flatten()
        indices_arr = numpy.array(indices, dtype=numpy.uint32)

        TreeGeometry._foliage_vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        ebo = glGenBuffers(1)

        glBindVertexArray(TreeGeometry._foliage_vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices_arr.nbytes, vertices_arr, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices_arr.nbytes, indices_arr, GL_STATIC_DRAW)

        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 8*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 8*4, ctypes.c_void_p(3*4))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, 8*4, ctypes.c_void_p(6*4))
        glEnableVertexAttribArray(2)

        glBindVertexArray(0)
        TreeGeometry._foliage_vertex_count = len(indices)

    def _create_textures(self):
        # Simple brown texture for trunk
        trunk_size = 32
        trunk_data = numpy.zeros((trunk_size, trunk_size, 4), dtype=numpy.uint8)
        trunk_data[:, :] = [139, 69, 19, 255]  # brown
        TreeGeometry._trunk_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, TreeGeometry._trunk_texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, trunk_size, trunk_size, 0, GL_RGBA, GL_UNSIGNED_BYTE, trunk_data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        # Simple green texture for foliage
        foliage_size = 32
        foliage_data = numpy.zeros((foliage_size, foliage_size, 4), dtype=numpy.uint8)
        foliage_data[:, :] = [34, 139, 34, 255]  # forest green
        TreeGeometry._foliage_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, TreeGeometry._foliage_texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, foliage_size, foliage_size, 0, GL_RGBA, GL_UNSIGNED_BYTE, foliage_data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        glBindTexture(GL_TEXTURE_2D, 0)

    @classmethod
    def get_trunk_vao(cls):
        return cls._trunk_vao

    @classmethod
    def get_trunk_vertex_count(cls):
        return cls._trunk_vertex_count

    @classmethod
    def get_trunk_texture(cls):
        return cls._trunk_texture

    @classmethod
    def get_foliage_vao(cls):
        return cls._foliage_vao

    @classmethod
    def get_foliage_vertex_count(cls):
        return cls._foliage_vertex_count

    @classmethod
    def get_foliage_texture(cls):
        return cls._foliage_texture


class Tree:
    def __init__(self, base_x, base_z, trunk_height=1.5, foliage_radius=0.6, rotation_y=None):
        self.base_x = base_x
        self.base_z = base_z
        self.trunk_height = trunk_height
        self.foliage_radius = foliage_radius
        self.rotation_y = rotation_y if rotation_y is not None else random.uniform(0, 360)
        self.geometry = TreeGeometry.get_instance()
        self.shader = Shader(TREE_VERTEX_SHADER_SRC, TREE_FRAGMENT_SHADER_SRC)

    def draw(self, view, projection, light_dir, light_intensity):
        y = get_height(self.base_x, self.base_z)
        if y < 0.1:
            return

        self.shader.use()
        self.shader.set_mat4("uView", view)
        self.shader.set_mat4("uProjection", projection)
        self.shader.set_vec3("uLightDir", light_dir)
        self.shader.set_float("uLightIntensity", light_intensity)

        # Build model matrix: rotation then translation
        rad = math.radians(self.rotation_y)
        c = math.cos(rad)
        s = math.sin(rad)
        model = numpy.array([
            [c, 0, s, 0],
            [0, 1, 0, 0],
            [-s, 0, c, 0],
            [0, 0, 0, 1]
        ], dtype=numpy.float32)
        model[0, 3] = self.base_x
        model[1, 3] = y
        model[2, 3] = self.base_z

        # Draw trunk
        self.shader.set_mat4("uModel", model)
        self.shader.set_int("uPart", 0)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.geometry.get_trunk_texture())
        self.shader.set_int("uTrunkTexture", 0)
        glBindVertexArray(self.geometry.get_trunk_vao())
        glDrawElements(GL_TRIANGLES, self.geometry.get_trunk_vertex_count(), GL_UNSIGNED_INT, None)

        # Draw foliage
        foliage_model = model.copy()
        foliage_model[1, 3] = y + self.trunk_height
        self.shader.set_mat4("uModel", foliage_model)
        self.shader.set_int("uPart", 1)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.geometry.get_foliage_texture())
        self.shader.set_int("uFoliageTexture", 0)
        glBindVertexArray(self.geometry.get_foliage_vao())
        glDrawElements(GL_TRIANGLES, self.geometry.get_foliage_vertex_count(), GL_UNSIGNED_INT, None)

        # Reset state
        glBindVertexArray(0)
        glBindTexture(GL_TEXTURE_2D, 0)


class TreeManager:
    def __init__(self, chunk_manager, chunk_size=16, spacing=1.0):
        self.chunk_manager = chunk_manager

    def draw(self, view, projection, light_dir, light_intensity):
        for chunk in self.chunk_manager.chunks.values():
            for tree_data in chunk.trees:
                tree = Tree(
                    tree_data['x'],
                    tree_data['z'],
                    trunk_height=tree_data.get('trunk_height', 1.5),
                    foliage_radius=tree_data.get('foliage_radius', 0.6),
                    rotation_y=tree_data.get('rotation_y')
                )
                tree.draw(view, projection, light_dir, light_intensity)
