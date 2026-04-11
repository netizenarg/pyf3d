import numpy
import math
import ctypes
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader

from loot import Loot
from weapon import Ammo, Weapon
from shaders.bazuka_shdr import *
from shaders.shader import Shader


class BazukaAmmo(Ammo):
    """High-damage, slower ammo with orange tetrahedron visual."""
    def __init__(self, position, direction, damage=50, speed=25.0, range_=80.0):
        super().__init__(position, direction, damage, speed, range_)
        self._shader = Shader(BAZUKA_AMMO_VERTEX_SHADER_SRC, BAZUKA_AMMO_FRAGMENT_SHADER_SRC)
        self.init_geometry()

    @classmethod
    def init_geometry(cls):
        if hasattr(cls, '_vao'):
            return
        # Build a tetrahedron (4 faces)
        vertices = numpy.array([
            # Vertex coordinates (x,y,z) and normals (nx,ny,nz) – simple flat shading
            # face 0 (base)
             0.0, -0.5,  0.577,   0.0, -0.816,  0.577,
             0.5, -0.5, -0.289,   0.0, -0.816,  0.577,
            -0.5, -0.5, -0.289,   0.0, -0.816,  0.577,
            # face 1
             0.0, -0.5,  0.577,   0.894,  0.447,  0.0,
             0.5, -0.5, -0.289,   0.894,  0.447,  0.0,
             0.0,  0.5,  0.0,     0.894,  0.447,  0.0,
            # face 2
             0.0, -0.5,  0.577,  -0.894,  0.447,  0.0,
            -0.5, -0.5, -0.289,  -0.894,  0.447,  0.0,
             0.0,  0.5,  0.0,    -0.894,  0.447,  0.0,
            # face 3
             0.5, -0.5, -0.289,   0.0,  0.816, -0.577,
            -0.5, -0.5, -0.289,   0.0,  0.816, -0.577,
             0.0,  0.5,  0.0,     0.0,  0.816, -0.577,
        ], dtype=numpy.float32)
        indices = numpy.array([0,1,2, 3,4,5, 6,7,8, 9,10,11], dtype=numpy.uint32)
        cls._vao = glGenVertexArrays(1)
        cls._vbo = glGenBuffers(1)
        cls._ebo = glGenBuffers(1)
        glBindVertexArray(cls._vao)
        glBindBuffer(GL_ARRAY_BUFFER, cls._vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, cls._ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6*4, ctypes.c_void_p(3*4))
        glEnableVertexAttribArray(1)
        glBindVertexArray(0)
        cls._index_count = len(indices)

    def draw(self, view, proj):
        self.init_geometry()
        glUseProgram(self._shader.program)
        self._shader.set_mat4("uView", view)
        self._shader.set_mat4("uProjection", proj)
        model = numpy.eye(4, dtype=numpy.float32)
        model[0,3], model[1,3], model[2,3] = self.position
        model[0,0] = model[1,1] = model[2,2] = 0.3
        self._shader.set_mat4("uModel", model)
        glBindVertexArray(self._vao)
        glDrawElements(GL_TRIANGLES, self._index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)


class Bazuka(Loot, Weapon):
    def __init__(self, position=None):
        if position is not None:
            Loot.__init__(self, position)
        self.rank = 2
        self.name = 'bazuka'
        self.damage = 50
        self.ammo_speed = 25.0
        self.ammo_range = 80.0
        self.cooldown = 0.5
        self.last_shot_time = 0.0
        self.offset = numpy.array([0.3, -0.2, 0.5])
        self.size = 0.5
        # OpenGL resources – lazy init
        self._opengl_initialized = False
        self._vao = None
        self._vbo = None
        self._ebo = None
        self._index_count = 0
        self._shader = None

    def _init_opengl(self):
        if self._opengl_initialized:
            return
        self._init_geometry()
        self._opengl_initialized = True

    def _init_geometry(self):
        # Build a simple cylinder-like model (tube) using 8-sided prism
        vertices = []
        indices = []
        height = 0.6
        radius = 0.15
        slices = 8
        # bottom vertices
        for i in range(slices):
            angle = 2 * math.pi * i / slices
            x = radius * math.cos(angle)
            z = radius * math.sin(angle)
            vertices.extend([x, -height/2, z, 0,0,1])  # normal placeholder
        # top vertices
        for i in range(slices):
            angle = 2 * math.pi * i / slices
            x = radius * math.cos(angle)
            z = radius * math.sin(angle)
            vertices.extend([x, height/2, z, 0,0,1])
        # sides
        for i in range(slices):
            next_i = (i+1) % slices
            indices.extend([i, next_i, i+slices])
            indices.extend([next_i, next_i+slices, i+slices])
        # caps (simple triangles)
        center_bottom = len(vertices)//6
        vertices.extend([0, -height/2, 0, 0,-1,0])
        for i in range(slices):
            next_i = (i+1) % slices
            indices.extend([center_bottom, i, next_i])
        center_top = len(vertices)//6
        vertices.extend([0, height/2, 0, 0,1,0])
        for i in range(slices):
            next_i = (i+1) % slices
            indices.extend([center_top, i+slices, next_i+slices])
        vertices = numpy.array(vertices, dtype=numpy.float32)
        indices = numpy.array(indices, dtype=numpy.uint32)
        self._vao = glGenVertexArrays(1)
        self._vbo = glGenBuffers(1)
        self._ebo = glGenBuffers(1)
        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6*4, ctypes.c_void_p(3*4))
        glEnableVertexAttribArray(1)
        glBindVertexArray(0)
        self._index_count = len(indices)
        self._shader = Shader(BAZUKA_VERTEX_SHADER_SRC, BAZUKA_FRAGMENT_SHADER_SRC)

    @classmethod
    def from_dict(cls, data):
        obj = cls()
        obj.damage = data.get('damage', 50)
        obj.ammo_speed = data.get('ammo_speed', 25.0)
        obj.ammo_range = data.get('ammo_range', 80.0)
        obj.cooldown = data.get('cooldown', 0.5)
        obj.rank = data.get('rank', 2)
        obj.name = data.get('name', 'bazuka')
        obj.offset = numpy.array(data.get('offset', [0.3, -0.2, 0.5]))
        obj.size = data.get('size', 0.5)
        return obj

    def to_dict(self):
        d = super().to_dict()
        d['name'] = 'bazuka'
        return d

    def draw(self, view, proj, model_matrix=None, offset=None):
        """Draw the bazuka (loot or weapon)."""
        self._init_opengl()
        glUseProgram(self._shader.program)
        self._shader.set_mat4("uView", view)
        self._shader.set_mat4("uProjection", proj)

        if model_matrix is not None and offset is not None:
            # Weapon mode: attach to hand
            model = model_matrix.copy()
            offset_mat = numpy.eye(4, dtype=numpy.float32)
            offset_mat[0, 3] = offset[0]
            offset_mat[1, 3] = offset[1]
            offset_mat[2, 3] = offset[2]
            model = model @ offset_mat
        else:
            # Loot mode: use world position
            model = self.get_model_matrix()

        self._shader.set_mat4("uModel", model)

        # Simplified lighting
        light_dir = numpy.array([1.0, -1.0, 0.0], dtype=float)
        light_dir = light_dir / numpy.linalg.norm(light_dir)
        self._shader.set_vec3("uLightDir", light_dir)
        self._shader.set_float("uLightIntensity", 1.0)

        glBindVertexArray(self._vao)
        glDrawElements(GL_TRIANGLES, self._index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def on_pickup(self, player):
        return player.pickup_weapon(self)

    def shoot(self, position, direction, current_time):
        if current_time - self.last_shot_time < self.cooldown:
            return None
        self.last_shot_time = current_time
        return BazukaAmmo(position, direction, self.damage, self.ammo_speed, self.ammo_range)
