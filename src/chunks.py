import numpy
import ctypes
from OpenGL.GL import *
from camera import get_height

class Chunk:
    def __init__(self, cx, cz, terrain_width, terrain_height, spacing):
        self.cx = cx
        self.cz = cz
        self.terrain_width = terrain_width
        self.terrain_height = terrain_height
        self.spacing = spacing
        self.vertices = None
        self.indices = None
        self.vao = None
        self.vbo = None
        self.ebo = None
        self.generate_vertices()
        self.setup_mesh()

    def generate_vertices(self):
        # Physical size of one chunk in world units
        phys_width = (self.terrain_width - 1) * self.spacing
        phys_height = (self.terrain_height - 1) * self.spacing

        # World origin of this chunk (its lower‑left corner)
        world_origin_x = self.cx * phys_width
        world_origin_z = self.cz * phys_height

        self.vertices = numpy.zeros((self.terrain_width * self.terrain_height, 6), dtype=numpy.float32)
        for z in range(self.terrain_height):
            for x in range(self.terrain_width):
                wx = world_origin_x + x * self.spacing
                wz = world_origin_z + z * self.spacing
                wy = get_height(wx, wz)
                idx = z * self.terrain_width + x
                self.vertices[idx, 0:3] = [wx, wy, wz]

        # Compute normals (same as before)
        for z in range(self.terrain_height):
            for x in range(self.terrain_width):
                idx = z * self.terrain_width + x
                if 0 < x < self.terrain_width-1 and 0 < z < self.terrain_height-1:
                    hx1 = self.vertices[(z)*self.terrain_width + (x+1), 1]
                    hx2 = self.vertices[(z)*self.terrain_width + (x-1), 1]
                    hz1 = self.vertices[(z+1)*self.terrain_width + x, 1]
                    hz2 = self.vertices[(z-1)*self.terrain_width + x, 1]
                    dx = hx1 - hx2
                    dz = hz1 - hz2
                    normal = numpy.array([-dx, 2.0 * self.spacing, -dz])
                    norm = numpy.linalg.norm(normal)
                    if norm > 0:
                        normal /= norm
                else:
                    normal = numpy.array([0.0, 1.0, 0.0])
                self.vertices[idx, 3:6] = normal

        self.indices = []
        for z in range(self.terrain_height - 1):
            for x in range(self.terrain_width - 1):
                i = z * self.terrain_width + x
                self.indices.extend([i, i+1, i+self.terrain_width,
                                     i+1, i+self.terrain_width+1, i+self.terrain_width])
        self.indices = numpy.array(self.indices, dtype=numpy.uint32)

    def setup_mesh(self):
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.ebo = glGenBuffers(1)

        glBindVertexArray(self.vao)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self.indices.nbytes, self.indices, GL_STATIC_DRAW)

        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, self.vertices.nbytes, self.vertices, GL_STATIC_DRAW)

        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 24, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 24, ctypes.c_void_p(12))
        glEnableVertexAttribArray(1)

        glBindVertexArray(0)

    def draw(self, shader):
        model = numpy.eye(4, dtype=numpy.float32)
        shader.set_mat4("uModel", model)
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, len(self.indices), GL_UNSIGNED_INT, None)
        glBindVertexArray(0)


class ChunkManager:
    def __init__(self, chunk_size=32, load_radius=3, spacing=1.0):
        self.chunk_size = chunk_size          # vertices per side
        self.load_radius = load_radius
        self.spacing = spacing
        self.chunks = {}

    def update(self, camera_pos):
        # Physical size of one chunk (world units)
        phys_size = (self.chunk_size - 1) * self.spacing

        # Chunk index of the camera
        cx = int(camera_pos[0] // phys_size)
        cz = int(camera_pos[2] // phys_size)

        needed = set()
        for dx in range(-self.load_radius, self.load_radius + 1):
            for dz in range(-self.load_radius, self.load_radius + 1):
                needed.add((cx + dx, cz + dz))

        # Remove chunks that are no longer needed
        for key in list(self.chunks.keys()):
            if key not in needed:
                chunk = self.chunks.pop(key)
                glDeleteVertexArrays(1, [chunk.vao])
                glDeleteBuffers(1, [chunk.vbo])
                glDeleteBuffers(1, [chunk.ebo])

        # Add missing chunks
        for (nx, nz) in needed:
            if (nx, nz) not in self.chunks:
                self.chunks[(nx, nz)] = Chunk(nx, nz, self.chunk_size, self.chunk_size, self.spacing)

    def draw(self, shader):
        for chunk in self.chunks.values():
            chunk.draw(shader)