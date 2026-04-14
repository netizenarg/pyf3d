import numpy
import math
import random
import ctypes
import json

from OpenGL.GL import *

from camera import get_height
from shaders.shader import Shader
from shaders.portal_shdr import PORTAL_PARTICLE_VERTEX_SHADER_SRC,\
                                PORTAL_PARTICLE_FRAGMENT_SHADER_SRC,\
                                PORTAL_VERTEX_SHADER_SRC,\
                                PORTAL_FRAGMENT_SHADER_SRC


class PortalParticle:
    __slots__ = ('position', 'velocity', 'lifetime', 'max_lifetime', 'color', 'size')
    def __init__(self, pos, vel, lifetime, color, size):
        self.position = numpy.array(pos, dtype=numpy.float32)
        self.velocity = numpy.array(vel, dtype=numpy.float32)
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.color = numpy.array(color, dtype=numpy.float32)
        self.size = size

class PortalParticleSystem:
    def __init__(self, min_particles=150, max_particles=300, global_size_scale=1.0):
        self.particles = []
        self.min_particles = min_particles
        self.max_particles = max_particles
        self.global_size_scale = global_size_scale
        self.vao = None
        self.vbo = None
        self.shader = Shader(PORTAL_PARTICLE_VERTEX_SHADER_SRC, PORTAL_PARTICLE_FRAGMENT_SHADER_SRC)
        self._init_gl()

    def _init_gl(self):
        # Simple point sprite shader
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        # position (3), color (4), size (1) -> 8 floats per particle
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 8 * 4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, 8 * 4, ctypes.c_void_p(3 * 4))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(2, 1, GL_FLOAT, GL_FALSE, 8 * 4, ctypes.c_void_p(7 * 4))
        glEnableVertexAttribArray(2)
        glBindVertexArray(0)

    def emit(self, position, count=150, color=(0.2, 0.8, 1.0, 0.8), size=0.15, velocity_range=(-0.5, 0.5, 0.8, 1.5)):
        for _ in range(count):
            if len(self.particles) >= self.max_particles:
                break
            vx = random.uniform(velocity_range[0], velocity_range[1])
            vy = random.uniform(velocity_range[2], velocity_range[3])
            vz = random.uniform(velocity_range[0], velocity_range[1])
            vel = (vx, vy, vz)
            lifetime = random.uniform(2.0, 5.0)
            self.particles.append(PortalParticle(position, vel, lifetime, color, size))

    def update(self, dt, emission_position, emission_params):
        for p in self.particles[:]:
            p.lifetime -= dt
            if p.lifetime <= 0:
                self.particles.remove(p)
                continue
            p.position += p.velocity * dt
            p.velocity[1] -= 0.02 * dt
            p.velocity *= 0.995
            alpha = p.color[3] * (p.lifetime / p.max_lifetime)
            p.color[3] = alpha
        deficit = self.min_particles - len(self.particles)
        if deficit > 0:
            self.emit(emission_position, count=deficit, **emission_params)

    def draw(self, view, projection):
        if not self.particles:
            return
        # Build vertex data
        data = numpy.zeros((len(self.particles), 8), dtype=numpy.float32)
        for i, p in enumerate(self.particles):
            data[i, 0:3] = p.position
            data[i, 3:7] = p.color
            data[i, 7] = p.size
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_DYNAMIC_DRAW)
        self.shader.use()
        self.shader.set_mat4("uView", view)
        self.shader.set_mat4("uProjection", projection)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_PROGRAM_POINT_SIZE)
        glDepthMask(GL_FALSE)
        glDrawArrays(GL_POINTS, 0, len(self.particles))
        glDepthMask(GL_TRUE)
        glDisable(GL_PROGRAM_POINT_SIZE)
        glDisable(GL_BLEND)
        glBindVertexArray(0)


class PortalGeometry:
    """Singleton that builds portal mesh: thick wall with oval cutout."""
    _instance = None
    _vao_wall = None
    _wall_vertex_count = 0
    _vao_window = None
    _window_vertex_count = 0

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if PortalGeometry._vao_wall is not None:
            return
        self._build_portal()

    def _build_portal(self):
        """Construct a thick wall (slab) with an oval window cutout."""
        width = 2.4       # wall width (X)
        height = 3.2      # wall height (Y)
        thickness = 0.4   # wall depth (Z)
        oval_rx = 0.8     # horizontal radius of window
        oval_ry = 1.2     # vertical radius

        # Colors
        wall_color = [0.5, 0.4, 0.3, 1.0]   # stone-like
        window_color = [0.2, 0.6, 1.0, 0.7] # cyan transparent

        vertices_wall = []
        indices_wall = []
        vertices_window = []
        indices_window = []

        def add_quad(vertices, indices, v0, v1, v2, v3, normal, color):
            base = len(vertices) // 10
            for v in (v0, v1, v2, v3):
                vertices.extend([*v, *normal, *color])
            indices.extend([base, base+1, base+2, base, base+2, base+3])

        w2 = width / 2.0
        h2 = height / 2.0
        d2 = thickness / 2.0

        # Helper to create a quad with hole (simplified: we just build the wall as four separate panels around the oval)
        # For simplicity, we'll build the wall as four rectangular pieces: left, right, bottom, top.
        # And a separate oval window mesh.

        # Front face (+Z) wall pieces
        # Left panel
        add_quad(vertices_wall, indices_wall,
                 (-w2, -h2, d2), (-oval_rx, -h2, d2), (-oval_rx, h2, d2), (-w2, h2, d2),
                 (0,0,1), wall_color)
        # Right panel
        add_quad(vertices_wall, indices_wall,
                 (oval_rx, -h2, d2), (w2, -h2, d2), (w2, h2, d2), (oval_rx, h2, d2),
                 (0,0,1), wall_color)
        # Bottom panel
        add_quad(vertices_wall, indices_wall,
                 (-oval_rx, -h2, d2), (oval_rx, -h2, d2), (oval_rx, -oval_ry, d2), (-oval_rx, -oval_ry, d2),
                 (0,0,1), wall_color)
        # Top panel
        add_quad(vertices_wall, indices_wall,
                 (-oval_rx, oval_ry, d2), (oval_rx, oval_ry, d2), (oval_rx, h2, d2), (-oval_rx, h2, d2),
                 (0,0,1), wall_color)

        # Back face (-Z) similar (with reversed normal)
        add_quad(vertices_wall, indices_wall,
                 (-w2, h2, -d2), (-oval_rx, h2, -d2), (-oval_rx, -h2, -d2), (-w2, -h2, -d2),
                 (0,0,-1), wall_color)
        add_quad(vertices_wall, indices_wall,
                 (oval_rx, h2, -d2), (w2, h2, -d2), (w2, -h2, -d2), (oval_rx, -h2, -d2),
                 (0,0,-1), wall_color)
        add_quad(vertices_wall, indices_wall,
                 (-oval_rx, -oval_ry, -d2), (oval_rx, -oval_ry, -d2), (oval_rx, -h2, -d2), (-oval_rx, -h2, -d2),
                 (0,0,-1), wall_color)
        add_quad(vertices_wall, indices_wall,
                 (-oval_rx, h2, -d2), (oval_rx, h2, -d2), (oval_rx, oval_ry, -d2), (-oval_rx, oval_ry, -d2),
                 (0,0,-1), wall_color)

        # Side faces (left, right, top, bottom)
        # Left side (-X)
        add_quad(vertices_wall, indices_wall,
                 (-w2, -h2, -d2), (-w2, -h2, d2), (-w2, h2, d2), (-w2, h2, -d2),
                 (-1,0,0), wall_color)
        # Right side (+X)
        add_quad(vertices_wall, indices_wall,
                 (w2, -h2, d2), (w2, -h2, -d2), (w2, h2, -d2), (w2, h2, d2),
                 (1,0,0), wall_color)
        # Top side (+Y)
        add_quad(vertices_wall, indices_wall,
                 (-w2, h2, d2), (w2, h2, d2), (w2, h2, -d2), (-w2, h2, -d2),
                 (0,1,0), wall_color)
        # Bottom side (-Y)
        add_quad(vertices_wall, indices_wall,
                 (-w2, -h2, -d2), (w2, -h2, -d2), (w2, -h2, d2), (-w2, -h2, d2),
                 (0,-1,0), wall_color)

        # Oval window (transparent, double-sided)
        # We'll create an ellipse by approximating with triangles.
        # For simplicity, we use a single quad with texture or just a flat disc.
        # We'll use a circle fan with many segments.
        segments = 16
        center = (0.0, 0.0, d2 + 0.01)  # slightly in front of wall
        base_window = len(vertices_window) // 10
        for i in range(segments):
            angle = 2 * math.pi * i / segments
            x = oval_rx * math.cos(angle)
            y = oval_ry * math.sin(angle)
            vertices_window.extend([x, y, center[2], 0, 0, 1, *window_color])
        # Indices for triangle fan
        for i in range(segments):
            idx0 = base_window
            idx1 = base_window + 1 + i
            idx2 = base_window + 1 + ((i+1) % segments)
            indices_window.extend([idx0, idx1, idx2])
        # Also back face (reverse winding)
        base_window2 = len(vertices_window) // 10
        for i in range(segments):
            angle = 2 * math.pi * i / segments
            x = oval_rx * math.cos(angle)
            y = oval_ry * math.sin(angle)
            vertices_window.extend([x, y, -d2 - 0.01, 0, 0, -1, *window_color])
        for i in range(segments):
            idx0 = base_window2
            idx1 = base_window2 + 1 + i
            idx2 = base_window2 + 1 + ((i+1) % segments)
            indices_window.extend([idx0, idx2, idx1])  # reverse winding

        # Upload wall geometry
        vertices_arr_wall = numpy.array(vertices_wall, dtype=numpy.float32)
        indices_arr_wall = numpy.array(indices_wall, dtype=numpy.uint32)

        PortalGeometry._vao_wall = glGenVertexArrays(1)
        vbo_wall = glGenBuffers(1)
        ebo_wall = glGenBuffers(1)

        glBindVertexArray(PortalGeometry._vao_wall)
        glBindBuffer(GL_ARRAY_BUFFER, vbo_wall)
        glBufferData(GL_ARRAY_BUFFER, vertices_arr_wall.nbytes, vertices_arr_wall, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo_wall)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices_arr_wall.nbytes, indices_arr_wall, GL_STATIC_DRAW)

        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 10*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 10*4, ctypes.c_void_p(3*4))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, 10*4, ctypes.c_void_p(6*4))
        glEnableVertexAttribArray(2)

        glBindVertexArray(0)
        PortalGeometry._wall_vertex_count = len(indices_wall)

        # Upload window geometry
        vertices_arr_window = numpy.array(vertices_window, dtype=numpy.float32)
        indices_arr_window = numpy.array(indices_window, dtype=numpy.uint32)

        PortalGeometry._vao_window = glGenVertexArrays(1)
        vbo_window = glGenBuffers(1)
        ebo_window = glGenBuffers(1)

        glBindVertexArray(PortalGeometry._vao_window)
        glBindBuffer(GL_ARRAY_BUFFER, vbo_window)
        glBufferData(GL_ARRAY_BUFFER, vertices_arr_window.nbytes, vertices_arr_window, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo_window)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices_arr_window.nbytes, indices_arr_window, GL_STATIC_DRAW)

        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 10*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 10*4, ctypes.c_void_p(3*4))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, 10*4, ctypes.c_void_p(6*4))
        glEnableVertexAttribArray(2)

        glBindVertexArray(0)
        PortalGeometry._window_vertex_count = len(indices_window)

    @classmethod
    def get_vao_wall(cls):
        return cls._vao_wall

    @classmethod
    def get_wall_vertex_count(cls):
        return cls._wall_vertex_count

    @classmethod
    def get_vao_window(cls):
        return cls._vao_window

    @classmethod
    def get_window_vertex_count(cls):
        return cls._window_vertex_count


class Portal:
    def __init__(self, name='', base_x=0, base_z=0, rotation_y=None, scale=1.0):
        self.base_x = base_x
        self.base_z = base_z
        self.rotation_y = rotation_y if rotation_y is not None else random.uniform(0, 2 * math.pi)  # radians
        self.scale = scale
        self.geometry = PortalGeometry.get_instance()
        # Collision dimensions
        self.width = 2.4 * scale
        self.height = 3.2 * scale
        self.depth = 0.4 * scale
        self.collision_radius = math.sqrt((self.width/2)**2 + (self.height/2)**2) * 1.1
        # Compute center Y based on terrain
        ground_y = get_height(base_x, base_z)
        self.center_y = ground_y + self.height / 2.0
        if not name:
            ix = int(round(base_x))
            iy = int(round(self.center_y))
            iz = int(round(base_z))
            name = f"{ix}_{iy}_{iz}"
        self.name = name

    def get_collision_center(self):
        return (self.base_x, self.center_y, self.base_z)

    def draw(self, shader, view, projection, light_dir, light_intensity):
        ground_y = get_height(self.base_x, self.base_z)
        if ground_y < 0.1:
            return
        # Position the model so its bottom sits on the terrain
        y_translation = ground_y + self.height / 2.0

        # Save state
        blend_was_on = glIsEnabled(GL_BLEND)
        depth_test_was_on = glIsEnabled(GL_DEPTH_TEST)
        cull_face_was_on = glIsEnabled(GL_CULL_FACE)

        shader.use()
        shader.set_mat4("uView", view)
        shader.set_mat4("uProjection", projection)
        shader.set_vec3("uLightDir", light_dir)
        shader.set_float("uLightIntensity", light_intensity)

        # Use stored rotation (already in radians)
        c = math.cos(self.rotation_y)
        s = math.sin(self.rotation_y)
        model = numpy.array([
            [c * self.scale, 0, s * self.scale, 0],
            [0, self.scale, 0, 0],
            [-s * self.scale, 0, c * self.scale, 0],
            [0, 0, 0, 1]
        ], dtype=numpy.float32)
        model[0, 3] = self.base_x
        model[1, 3] = y_translation
        model[2, 3] = self.base_z

        shader.set_mat4("uModel", model)

        # Draw wall (opaque)
        glDisable(GL_BLEND)
        glBindVertexArray(self.geometry.get_vao_wall())
        glDrawElements(GL_TRIANGLES, self.geometry.get_wall_vertex_count(), GL_UNSIGNED_INT, None)

        # Draw window (transparent)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDepthMask(GL_FALSE)
        glDisable(GL_CULL_FACE)

        glBindVertexArray(self.geometry.get_vao_window())
        glDrawElements(GL_TRIANGLES, self.geometry.get_window_vertex_count(), GL_UNSIGNED_INT, None)

        glDepthMask(GL_TRUE)
        if cull_face_was_on:
            glEnable(GL_CULL_FACE)

        # Restore states
        if blend_was_on:
            glEnable(GL_BLEND)
        else:
            glDisable(GL_BLEND)
        if not depth_test_was_on:
            glDisable(GL_DEPTH_TEST)
        glBindVertexArray(0)


class PortalManager:
    def __init__(self, chunk_manager):
        self.chunk_manager = chunk_manager
        self.shader = Shader(PORTAL_VERTEX_SHADER_SRC, PORTAL_FRAGMENT_SHADER_SRC)
        self.particle_system = PortalParticleSystem(min_particles=300, max_particles=500, global_size_scale=5.0)

    def update(self, dt):
        for chunk in self.chunk_manager.chunks.values():
            if chunk.portal:
                portal = chunk.portal
                ground_y = get_height(portal.base_x, portal.base_z)
                center_y = ground_y + portal.height / 2.0
                oval_ry = 1.2 * portal.scale
                base_y = center_y - oval_ry
                emission_pos = (
                    portal.base_x + random.uniform(-0.5, 0.5) * portal.scale,
                    base_y,
                    portal.base_z + random.uniform(-0.5, 0.5) * portal.scale
                )
                self.particle_system.update(dt, emission_pos, {
                    'color': (0.2, 0.8, 1.0, 0.8),
                    'size': 0.15,
                    'velocity_range': (-0.8, 0.8, 1.0, 2.0)#(-1.2, 1.2, 1.5, 3.0)
                })

    def get_all_portals(self):
        portals = []
        for chunk in self.chunk_manager.chunks.values():
            if chunk.portal:
                portals.append(chunk.portal)
        return portals

    def draw(self, view, projection, light_dir, light_intensity):
        for portal in self.get_all_portals():
            portal.draw(self.shader, view, projection, light_dir, light_intensity)
        self.particle_system.draw(view, projection)

    def get_portal_at(self, position, radius=1.0):
        for portal in self.get_all_portals():
            hx, hy, hz = portal.get_collision_center()
            dx = position[0] - hx
            dz = position[2] - hz
            if abs(dx) < portal.width/2 + radius and abs(dz) < portal.depth/2 + radius:
                if abs(position[1] - hy) < portal.height/2 + radius:
                    return portal
        return None
