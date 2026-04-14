import numpy
import math
import random
import ctypes

from OpenGL.GL import *

from camera import get_height
from shaders.shader import Shader
from shaders.house_shdr import HOUSE_VERTEX_SHADER_SRC, HOUSE_FRAGMENT_SHADER_SRC


class HouseGeometry:
    """Singleton that builds a simple house mesh (walls + roof + door + windows)."""
    _instance = None
    _vao_opaque = None          # Walls, roof, door
    _vertex_count_opaque = 0
    _vao_windows = None         # Transparent windows
    _vertex_count_windows = 0

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if HouseGeometry._vao_opaque is not None:
            return
        self._build_house()

    def _build_house(self, width=1.5, depth=1.5, wall_height=1.8, roof_height=0.8):
        """
        Construct house with walls made of multiple quads (openings for door/windows).
        wall_height is now 1.5× the previous 1.2 (so 1.8).
        """
        vertices_opaque = []   # pos(3), normal(3), color(4) RGBA
        indices_opaque = []
        vertices_windows = []  # pos(3), normal(3), color(4) RGBA
        indices_windows = []

        w2 = width / 2.0
        d2 = depth / 2.0
        h = wall_height

        # Colors (RGBA)
        wall_color = [0.8, 0.6, 0.4, 1.0]     # light brown / wood
        roof_color = [0.6, 0.2, 0.1, 1.0]     # dark red / tile
        door_color = [0.5, 0.25, 0.0, 1.0]    # dark brown
        window_color = [0.5, 0.8, 1.0, 0.6]   # light blue, 60% opacity

        def add_quad_opaque(v0, v1, v2, v3, normal, color):
            base = len(vertices_opaque) // 10
            for v in (v0, v1, v2, v3):
                vertices_opaque.extend([*v, *normal, *color])
            indices_opaque.extend([base, base+1, base+2, base, base+2, base+3])

        def add_quad_window(v0, v1, v2, v3, normal, color):
            base = len(vertices_windows) // 10
            for v in (v0, v1, v2, v3):
                vertices_windows.extend([*v, *normal, *color])
            indices_windows.extend([base, base+1, base+2, base, base+2, base+3])

        # ------------------------------------------------------------
        #  FRONT WALL (+Z) with door opening
        # ------------------------------------------------------------
        # Door dimensions
        door_w = 0.5
        door_h = 1.5
        door_x_min = -door_w/2
        door_x_max =  door_w/2
        door_y_min = 0.0
        door_y_max = door_h

        # Left side of door
        add_quad_opaque(
            (-w2, 0, d2), (door_x_min, 0, d2), (door_x_min, h, d2), (-w2, h, d2),
            (0,0,1), wall_color
        )
        # Right side of door
        add_quad_opaque(
            (door_x_max, 0, d2), (w2, 0, d2), (w2, h, d2), (door_x_max, h, d2),
            (0,0,1), wall_color
        )
        # Above door
        add_quad_opaque(
            (door_x_min, door_y_max, d2), (door_x_max, door_y_max, d2), (door_x_max, h, d2), (door_x_min, h, d2),
            (0,0,1), wall_color
        )

        # Door itself (opaque, but separate)
        door_z = d2 + 0.01
        add_quad_opaque(
            (door_x_min, door_y_min, door_z), (door_x_max, door_y_min, door_z),
            (door_x_max, door_y_max, door_z), (door_x_min, door_y_max, door_z),
            (0,0,1), door_color
        )

        # ------------------------------------------------------------
        #  BACK WALL (-Z) with window opening
        # ------------------------------------------------------------
        win_w = 0.7
        win_h = 0.7
        win_x_min = -win_w/2
        win_x_max =  win_w/2
        win_y_center = h * 0.5
        win_y_min = win_y_center - win_h/2
        win_y_max = win_y_center + win_h/2

        # Bottom quad
        add_quad_opaque(
            (-w2, 0, -d2), (w2, 0, -d2), (w2, win_y_min, -d2), (-w2, win_y_min, -d2),
            (0,0,-1), wall_color
        )
        # Top quad
        add_quad_opaque(
            (-w2, win_y_max, -d2), (w2, win_y_max, -d2), (w2, h, -d2), (-w2, h, -d2),
            (0,0,-1), wall_color
        )
        # Left quad
        add_quad_opaque(
            (-w2, win_y_min, -d2), (win_x_min, win_y_min, -d2), (win_x_min, win_y_max, -d2), (-w2, win_y_max, -d2),
            (0,0,-1), wall_color
        )
        # Right quad
        add_quad_opaque(
            (win_x_max, win_y_min, -d2), (w2, win_y_min, -d2), (w2, win_y_max, -d2), (win_x_max, win_y_max, -d2),
            (0,0,-1), wall_color
        )

        # Back window (transparent, slightly offset)
        win_z_back = -d2
        add_quad_window(
            (win_x_min, win_y_min, win_z_back), (win_x_max, win_y_min, win_z_back),
            (win_x_max, win_y_max, win_z_back), (win_x_min, win_y_max, win_z_back),
            (0,0,-1), window_color
        )

        # ------------------------------------------------------------
        #  LEFT WALL (-X) with window opening
        # ------------------------------------------------------------
        win_z_min_left = -win_w/2
        win_z_max_left = win_w/2
        # Bottom
        add_quad_opaque(
            (-w2, 0, -d2), (-w2, 0, d2), (-w2, win_y_min, d2), (-w2, win_y_min, -d2),
            (-1,0,0), wall_color
        )
        # Top
        add_quad_opaque(
            (-w2, win_y_max, -d2), (-w2, win_y_max, d2), (-w2, h, d2), (-w2, h, -d2),
            (-1,0,0), wall_color
        )
        # Left (actually front/back relative to wall)
        add_quad_opaque(
            (-w2, win_y_min, -d2), (-w2, win_y_min, win_z_min_left), (-w2, win_y_max, win_z_min_left), (-w2, win_y_max, -d2),
            (-1,0,0), wall_color
        )
        # Right
        add_quad_opaque(
            (-w2, win_y_min, win_z_max_left), (-w2, win_y_min, d2), (-w2, win_y_max, d2), (-w2, win_y_max, win_z_max_left),
            (-1,0,0), wall_color
        )

        # Left window
        win_x_left = -w2
        add_quad_window(
            (win_x_left, win_y_min, -win_w/2), (win_x_left, win_y_min, win_w/2),
            (win_x_left, win_y_max, win_w/2), (win_x_left, win_y_max, -win_w/2),
            (-1,0,0), window_color
        )

        # ------------------------------------------------------------
        #  RIGHT WALL (+X) with window opening
        # ------------------------------------------------------------
        # Bottom
        add_quad_opaque(
            (w2, 0, -d2), (w2, 0, d2), (w2, win_y_min, d2), (w2, win_y_min, -d2),
            (1,0,0), wall_color
        )
        # Top
        add_quad_opaque(
            (w2, win_y_max, -d2), (w2, win_y_max, d2), (w2, h, d2), (w2, h, -d2),
            (1,0,0), wall_color
        )
        # Front/back quads
        add_quad_opaque(
            (w2, win_y_min, -d2), (w2, win_y_min, -win_w/2), (w2, win_y_max, -win_w/2), (w2, win_y_max, -d2),
            (1,0,0), wall_color
        )
        add_quad_opaque(
            (w2, win_y_min, win_w/2), (w2, win_y_min, d2), (w2, win_y_max, d2), (w2, win_y_max, win_w/2),
            (1,0,0), wall_color
        )

        # Right window
        win_x_right = w2
        add_quad_window(
            (win_x_right, win_y_min, win_w/2), (win_x_right, win_y_min, -win_w/2),
            (win_x_right, win_y_max, -win_w/2), (win_x_right, win_y_max, win_w/2),
            (1,0,0), window_color
        )

        # ------------------------------------------------------------
        #  ROOF (pyramid, unchanged)
        # ------------------------------------------------------------
        apex = (0, h + roof_height, 0)
        def add_triangle_opaque(v0, v1, v2, color):
            base = len(vertices_opaque) // 10
            u = numpy.subtract(v1, v0)
            v = numpy.subtract(v2, v0)
            normal = numpy.cross(u, v)
            norm = numpy.linalg.norm(normal)
            if norm > 0:
                normal = normal / norm
            else:
                normal = (0, 1, 0)
            for vtx in (v0, v1, v2):
                vertices_opaque.extend([*vtx, *normal, *color])
            indices_opaque.extend([base, base+1, base+2])

        corners = [(-w2, h, d2), (w2, h, d2), (w2, h, -d2), (-w2, h, -d2)]
        for i in range(4):
            add_triangle_opaque(corners[i], corners[(i+1)%4], apex, roof_color)

        # ------------------------------------------------------------
        #  Upload Opaque Geometry
        # ------------------------------------------------------------
        vertices_arr_opaque = numpy.array(vertices_opaque, dtype=numpy.float32)
        indices_arr_opaque = numpy.array(indices_opaque, dtype=numpy.uint32)

        HouseGeometry._vao_opaque = glGenVertexArrays(1)
        vbo_opaque = glGenBuffers(1)
        ebo_opaque = glGenBuffers(1)

        glBindVertexArray(HouseGeometry._vao_opaque)
        glBindBuffer(GL_ARRAY_BUFFER, vbo_opaque)
        glBufferData(GL_ARRAY_BUFFER, vertices_arr_opaque.nbytes, vertices_arr_opaque, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo_opaque)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices_arr_opaque.nbytes, indices_arr_opaque, GL_STATIC_DRAW)

        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 10*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 10*4, ctypes.c_void_p(3*4))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, 10*4, ctypes.c_void_p(6*4))
        glEnableVertexAttribArray(2)

        glBindVertexArray(0)
        HouseGeometry._vertex_count_opaque = len(indices_opaque)

        # ------------------------------------------------------------
        #  Upload Window Geometry (transparent)
        # ------------------------------------------------------------
        if vertices_windows:
            vertices_arr_windows = numpy.array(vertices_windows, dtype=numpy.float32)
            indices_arr_windows = numpy.array(indices_windows, dtype=numpy.uint32)

            HouseGeometry._vao_windows = glGenVertexArrays(1)
            vbo_windows = glGenBuffers(1)
            ebo_windows = glGenBuffers(1)

            glBindVertexArray(HouseGeometry._vao_windows)
            glBindBuffer(GL_ARRAY_BUFFER, vbo_windows)
            glBufferData(GL_ARRAY_BUFFER, vertices_arr_windows.nbytes, vertices_arr_windows, GL_STATIC_DRAW)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo_windows)
            glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices_arr_windows.nbytes, indices_arr_windows, GL_STATIC_DRAW)

            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 10*4, ctypes.c_void_p(0))
            glEnableVertexAttribArray(0)
            glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 10*4, ctypes.c_void_p(3*4))
            glEnableVertexAttribArray(1)
            glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, 10*4, ctypes.c_void_p(6*4))
            glEnableVertexAttribArray(2)

            glBindVertexArray(0)
            HouseGeometry._vertex_count_windows = len(indices_windows)

    @classmethod
    def get_vao_opaque(cls):
        return cls._vao_opaque

    @classmethod
    def get_vertex_count_opaque(cls):
        return cls._vertex_count_opaque

    @classmethod
    def get_vao_windows(cls):
        return cls._vao_windows

    @classmethod
    def get_vertex_count_windows(cls):
        return cls._vertex_count_windows


class House:
    def __init__(self, base_x, base_z, rotation_y=None, scale=1.0):
        self.base_x = base_x
        self.base_z = base_z
        self.rotation_y = rotation_y if rotation_y is not None else random.uniform(0, 360)
        self.scale = scale
        self.geometry = HouseGeometry.get_instance()
        self.base_width = 1.5 * scale
        self.base_depth = 1.5 * scale
        self.collision_radius = math.sqrt((self.base_width/2)**2 + (self.base_depth/2)**2) * 1.1
        self.center_y = get_height(base_x, base_z) + (1.2 * scale) / 2

    def get_collision_center(self):
        return (self.base_x, self.center_y, self.base_z)

    def draw(self, shader, view, projection, light_dir, light_intensity):
        y = get_height(self.base_x, self.base_z)
        if y < 0.1:
            return

        # Save OpenGL state
        blend_was_on = glIsEnabled(GL_BLEND)
        depth_test_was_on = glIsEnabled(GL_DEPTH_TEST)
        cull_face_was_on = glIsEnabled(GL_CULL_FACE)

        shader.use()
        shader.set_mat4("uView", view)
        shader.set_mat4("uProjection", projection)
        shader.set_vec3("uLightDir", light_dir)
        shader.set_float("uLightIntensity", light_intensity)

        rad = math.radians(self.rotation_y)
        c = math.cos(rad)
        s = math.sin(rad)
        model = numpy.array([
            [c * self.scale, 0, s * self.scale, 0],
            [0, self.scale, 0, 0],
            [-s * self.scale, 0, c * self.scale, 0],
            [0, 0, 0, 1]
        ], dtype=numpy.float32)
        model[0, 3] = self.base_x
        model[1, 3] = y
        model[2, 3] = self.base_z

        shader.set_mat4("uModel", model)

        # 1. Draw opaque parts – blending must be OFF
        glDisable(GL_BLEND)
        glBindVertexArray(self.geometry.get_vao_opaque())
        glDrawElements(GL_TRIANGLES, self.geometry.get_vertex_count_opaque(), GL_UNSIGNED_INT, None)

        # 2. Draw transparent windows with depth testing enabled,
        #    but depth writes disabled so they don't occlude each other incorrectly.
        if self.geometry.get_vao_windows() is not None:
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glDepthMask(GL_FALSE)          # don't write depth, but still test
            glDisable(GL_CULL_FACE)

            glBindVertexArray(self.geometry.get_vao_windows())
            glDrawElements(GL_TRIANGLES, self.geometry.get_vertex_count_windows(), GL_UNSIGNED_INT, None)

            # Restore depth mask and cull face
            glDepthMask(GL_TRUE)
            if cull_face_was_on:
                glEnable(GL_CULL_FACE)
            # Do NOT restore depth test here – it's already enabled (or was saved)

        # Restore original blend and depth test states
        if blend_was_on:
            glEnable(GL_BLEND)
        else:
            glDisable(GL_BLEND)

        if not depth_test_was_on:
            glDisable(GL_DEPTH_TEST)

        glBindVertexArray(0)


class HouseManager:
    def __init__(self, chunk_manager, chunk_size=16, spacing=1.0, house_probability=0.2):
        self.chunk_manager = chunk_manager
        self.shader = Shader(HOUSE_VERTEX_SHADER_SRC, HOUSE_FRAGMENT_SHADER_SRC)
        self.houses = {}          # chunk_key -> list of House objects
        self.loaded_chunks = set()
        self.house_probability = house_probability   # chance per chunk to contain a house

    def _should_chunk_have_house(self, cx, cz):
        """Deterministic check whether chunk (cx, cz) contains a house."""
        rng = random.Random((cx * 73856093) ^ (cz * 19349663))
        return rng.random() < self.house_probability

    def _generate_houses_for_chunk(self, chunk_key, chunk):
        """Generate houses for a chunk (called once when chunk is first loaded)."""
        cx, cz = chunk_key
        if not self._should_chunk_have_house(cx, cz):
            return []

        chunk_size = self.chunk_manager.chunk_size
        spacing = self.chunk_manager.spacing
        phys_size = (chunk_size - 1) * spacing
        origin_x = cx * phys_size
        origin_z = cz * phys_size

        # Use the same seed for consistent house placement inside the chunk
        rng = random.Random((cx * 73856093) ^ (cz * 19349663))
        margin = 2.0
        base_x = origin_x + rng.uniform(margin, phys_size - margin)
        base_z = origin_z + rng.uniform(margin, phys_size - margin)

        rotation = rng.uniform(0, 360)
        scale = rng.uniform(0.8, 1.2)

        return [House(base_x, base_z, rotation, scale)]

    def update(self):
        current_chunks = set(self.chunk_manager.chunks.keys())

        # Remove houses from unloaded chunks
        for chunk_key in list(self.loaded_chunks):
            if chunk_key not in current_chunks:
                self.houses.pop(chunk_key, None)
                self.loaded_chunks.discard(chunk_key)

        # Add houses for newly loaded chunks
        for chunk_key in current_chunks:
            if chunk_key not in self.loaded_chunks:
                chunk = self.chunk_manager.chunks[chunk_key]
                if not hasattr(chunk, 'houses'):
                    chunk.houses = []   # extend chunk data structure
                if chunk_key not in self.houses:
                    new_houses = self._generate_houses_for_chunk(chunk_key, chunk)
                    if new_houses:
                        chunk.houses = [{'x': h.base_x, 'z': h.base_z,
                                         'rotation_y': h.rotation_y, 'scale': h.scale}
                                        for h in new_houses]
                        self.houses[chunk_key] = new_houses
                    else:
                        self.houses[chunk_key] = []
                self.loaded_chunks.add(chunk_key)

    def draw(self, view, projection, light_dir, light_intensity):
        for houses_list in self.houses.values():
            for house in houses_list:
                house.draw(self.shader, view, projection, light_dir, light_intensity)

    def shutdown(self):
        self.houses.clear()
        self.loaded_chunks.clear()

    def collides_with_point(self, point, player_radius=0.5):
        px, py, pz = point
        for houses_list in self.houses.values():
            for house in houses_list:
                hx, hy, hz = house.get_collision_center()
                dx = px - hx
                dz = pz - hz
                dist_sq = dx*dx + dz*dz
                if dist_sq < (house.collision_radius + player_radius)**2:
                    if py + player_radius > hy - 0.6*house.scale and py - player_radius < hy + 0.6*house.scale:
                        return True
        return False
