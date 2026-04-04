import numpy
import math
import random
from OpenGL.GL import *
import ctypes

from camera import get_height
from shaders.shader import Shader
from shaders.health_shdr import HEALTH_VERTEX_SHADER_SRC, HEALTH_FRAGMENT_SHADER_SRC


class HealthCube:
    """Health pickup that rotates and bobs above terrain."""
    def __init__(self, position, chunk_cx, chunk_cz):
        self.position = numpy.array(position, dtype=float)
        self.chunk_cx = chunk_cx
        self.chunk_cz = chunk_cz
        self.size = 0.8
        self.rotation_angle = 0.0
        self.bob_offset = 0.0
        self.collected = False
        self.restore_value = 10

    def update(self, dt, elapsed_time):
        """Update rotation and bobbing animation."""
        self.rotation_angle += 90.0 * dt  # degrees per second
        if self.rotation_angle > 360.0:
            self.rotation_angle -= 360.0
        self.bob_offset = math.sin(elapsed_time * 2.0) * 0.15

    def get_world_position(self):
        """Return position with vertical bob offset."""
        return self.position + numpy.array([0.0, self.bob_offset, 0.0])

    def to_dict(self):
        return {
            'pos_x': self.position[0],
            'pos_y': self.position[1],
            'pos_z': self.position[2],
            'restore_value': self.restore_value
        }

    @classmethod
    def from_dict(cls, data, chunk_cx, chunk_cz):
        cube = cls(
            position=(data['pos_x'], data['pos_y'], data['pos_z']),
            chunk_cx=chunk_cx,
            chunk_cz=chunk_cz
        )
        cube.restore_value = data.get('restore_value', 10.0)
        return cube


class HealthCubeModel:
    """Drawable model for a health cube with red cross on white faces."""
    def __init__(self, shader: Shader):
        self.shader = shader
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.ebo = glGenBuffers(1)
        self._build_cube_with_texcoords()
        self._setup_buffers()
        self.texture = self._create_cross_texture()

    def _build_cube_with_texcoords(self):
        # 8 vertices each with position (3) and texcoord (2)
        # Order: front, back, left, right, top, bottom
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

        self.vertex_data = vertices
        self.index_data = indices
        self.index_count = len(indices)

    def _create_cross_texture(self):
        """Create a 64x64 texture: white background with red cross (smaller, centered)."""
        size = 64
        tex_data = numpy.zeros((size, size, 3), dtype=numpy.uint8)
        tex_data[:, :] = [255, 255, 255]  # white background
        
        # Cross dimensions: 3/4 of the texture size -> 48x48 area
        cross_size = int(size * 0.75)  # 48
        start = (size - cross_size) // 2  # 8
        end = start + cross_size          # 56
        
        bar_width = 12  # thickness of cross arms
        bar_start = start + (cross_size - bar_width) // 2
        bar_end = bar_start + bar_width
        
        # Draw red cross within the centered square
        # Horizontal bar (full width within the cross area)
        tex_data[bar_start:bar_end, start:end] = [255, 0, 0]
        # Vertical bar (full height within the cross area)
        tex_data[start:end, bar_start:bar_end] = [255, 0, 0]
        
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, size, size, 0, GL_RGB, GL_UNSIGNED_BYTE, tex_data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glBindTexture(GL_TEXTURE_2D, 0)
        return tex_id

    def _setup_buffers(self):
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, self.vertex_data.nbytes, self.vertex_data, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self.index_data.nbytes, self.index_data, GL_STATIC_DRAW)

        # Position attribute (location 0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 5 * 4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        # TexCoord attribute (location 1)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 5 * 4, ctypes.c_void_p(3 * 4))
        glEnableVertexAttribArray(1)

        glBindVertexArray(0)

    def draw(self, cube, view, projection, light_dir, light_intensity):
        """Draw the health cube with rotation and bobbing (no update inside)."""
        if cube.collected:
            return

        pos = cube.get_world_position()
        angle = cube.rotation_angle
        size = cube.size

        glUseProgram(self.shader.program)
        self.shader.set_mat4("uView", view)
        self.shader.set_mat4("uProjection", projection)
        self.shader.set_vec3("uLightDir", light_dir)
        self.shader.set_float("uLightIntensity", light_intensity)

        # Build model matrix: translate, rotate, scale
        model = numpy.eye(4, dtype=numpy.float32)
        # Translate
        model[0, 3] = pos[0]
        model[1, 3] = pos[1]
        model[2, 3] = pos[2]
        # Rotate around Y axis
        rad = math.radians(angle)
        c, s = math.cos(rad), math.sin(rad)
        rot_y = numpy.array([
            [c, 0, s, 0],
            [0, 1, 0, 0],
            [-s, 0, c, 0],
            [0, 0, 0, 1]
        ], dtype=numpy.float32)
        model = model @ rot_y
        # Scale
        scale_mat = numpy.eye(4, dtype=numpy.float32)
        scale_mat[0, 0] = size
        scale_mat[1, 1] = size
        scale_mat[2, 2] = size
        model = model @ scale_mat

        self.shader.set_mat4("uModel", model)

        # Bind texture
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glUniform1i(glGetUniformLocation(self.shader.program, "uTexture"), 0)

        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, self.index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)


class HealthManager:
    """Manages health cubes per chunk, loads/saves only at shutdown."""
    def __init__(self, player, chunk_manager, chunk_size=32, spacing=1.0):
        self.prev_player_pos = None
        self.player = player
        self.chunk_manager = chunk_manager
        self.serializer = chunk_manager.serializer
        self.chunk_size = chunk_size
        self.spacing = spacing
        self.phys_size = (chunk_size - 1) * spacing
        self.active_cubes = {}      # (cx, cz) -> HealthCube
        self.loaded_chunks = set()
        self.pending_cubes = {}     # (cx, cz) -> cube dict for unloaded chunks
        self.elapsed_time = 0.0
        self.cube_model = HealthCubeModel(Shader(HEALTH_VERTEX_SHADER_SRC, HEALTH_FRAGMENT_SHADER_SRC))

    def _generate_cube_for_chunk(self, cx, cz):
        """Create a health cube at a random location within chunk."""
        world_min_x = cx * self.phys_size
        world_min_z = cz * self.phys_size
        world_max_x = world_min_x + self.phys_size
        world_max_z = world_min_z + self.phys_size
        x = random.uniform(world_min_x, world_max_x)
        z = random.uniform(world_min_z, world_max_z)
        y = get_height(x, z) + 0.8   # float above ground
        cube = HealthCube((x, y, z), cx, cz)
        return cube

    def _load_cube_for_chunk(self, cx, cz):
        """Load cube from DB or generate fresh, merge pending."""
        cube_data = self.serializer.load_health(cx, cz)
        pending = self.pending_cubes.pop((cx, cz), None)
        if pending is not None:
            cube_data = pending  # pending overrides DB
        if cube_data is not None:
            return HealthCube.from_dict(cube_data, cx, cz)
        else:
            return self._generate_cube_for_chunk(cx, cz)

    def _collect_cube(self, cube, chunk_key):
        """Helper to apply health restore and remove cube only if health is not full."""
        if self.player.life >= self.player.life_max:
            return  # No healing needed, don't collect
        self.player.life = min(100, self.player.life + cube.restore_value)
        cube.collected = True
        del self.active_cubes[chunk_key]
        self.pending_cubes[chunk_key] = None


    def update(self, dt):
        self.elapsed_time += dt
        # Determine currently loaded chunks
        current_chunks = set(self.chunk_manager.chunks.keys())
        for chunk_key in list(self.loaded_chunks): # Unload chunks that are no longer needed
            if chunk_key not in current_chunks:
                if chunk_key in self.active_cubes:
                    del self.active_cubes[chunk_key]
                self.loaded_chunks.discard(chunk_key)
        for chunk_key in current_chunks: # Load new chunks
            if chunk_key not in self.loaded_chunks:
                cube = self._load_cube_for_chunk(chunk_key[0], chunk_key[1])
                self.active_cubes[chunk_key] = cube
                self.loaded_chunks.add(chunk_key)
        # Update animations and check player collision
        player_pos = numpy.array(self.player.position)
        prev_pos = self.prev_player_pos if self.prev_player_pos is not None else player_pos
        for chunk_key, cube in list(self.active_cubes.items()):
            if cube.collected: # Already collected (should not happen, but safety)
                del self.active_cubes[chunk_key]
                self.pending_cubes[chunk_key] = None
                continue
            cube.update(dt, self.elapsed_time)
            cube_pos = cube.get_world_position()
            # Sphere-sphere collision with current position
            dist = numpy.linalg.norm(player_pos - cube_pos)
            if dist < 1.0:  # collision radius (increased)
                self._collect_cube(cube, chunk_key)
                continue
            # Continuous collision: check line segment from previous to current player position
            seg_vec = player_pos - prev_pos
            seg_len = numpy.linalg.norm(seg_vec)
            if seg_len > 0.01:
                seg_dir = seg_vec / seg_len
                to_cube = cube_pos - prev_pos
                t = numpy.dot(to_cube, seg_dir)
                if 0 <= t <= seg_len:
                    closest = prev_pos + seg_dir * t
                    if numpy.linalg.norm(closest - cube_pos) < 1.0:
                        self._collect_cube(cube, chunk_key)
                        continue
        self.prev_player_pos = player_pos

    def draw(self, view, projection, light_dir, light_intensity):
        """Draw all active cubes."""
        for cube in self.active_cubes.values():
            self.cube_model.draw(cube, view, projection, light_dir, light_intensity)

    def shutdown(self):
        """Save all active cubes and pending changes to DB."""
        # Save active cubes
        for (cx, cz), cube in self.active_cubes.items():
            if not cube.collected:
                self.serializer.save_health(cx, cz, cube.to_dict())
        # Apply pending deletions/updates
        for (cx, cz), cube_dict in self.pending_cubes.items():
            if cube_dict is None:
                # Delete from DB
                self.serializer.save_health(cx, cz, None)
            else:
                # Save new/updated cube
                self.serializer.save_health(cx, cz, cube_dict)
        self.active_cubes.clear()
        self.loaded_chunks.clear()
        self.pending_cubes.clear()
