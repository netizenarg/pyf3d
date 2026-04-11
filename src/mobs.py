import numpy
import math
import random
import ctypes
import logging

from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader

from camera import get_height
from shaders.shader import Shader
from shaders.mob_shdr import MOB_VERTEX_SHADER_SRC, MOB_FRAGMENT_SHADER_SRC
from shaders.ammo_shdr import PARTICLE_AMMO_EXPLOSION_VERTEX_SHADER_SRC, PARTICLE_AMMO_EXPLOSION_FRAGMENT_SHADER_SRC
from shaders.gui_shdr import RECT_VERTEX_SHADER, RECT_FRAGMENT_SHADER
from loot_types import LOOT_TYPES


def get_aimed_mob(camera, mob_manager, max_distance=50.0):
    """Return the closest mob intersected by the camera's forward ray."""
    origin = camera.position
    direction = camera.front
    best_mob = None
    best_dist = max_distance + 1.0
    for mobs in mob_manager.active_mobs.values():
        for mob in mobs:
            if not mob.is_alive():
                continue
            center = mob.position
            radius = 0.5
            oc = origin - center
            a = numpy.dot(direction, direction)
            b = 2.0 * numpy.dot(oc, direction)
            c = numpy.dot(oc, oc) - radius * radius
            disc = b*b - 4*a*c
            if disc >= 0:
                t = (-b - math.sqrt(disc)) / (2*a)
                if 0 < t < best_dist:
                    best_dist = t
                    best_mob = mob
    return best_mob


class Particle:
    __slots__ = ('position', 'life')
    def __init__(self, position):
        self.position = numpy.array(position, dtype=float)
        self.life = 1.0


class FlyingPart:
    __slots__ = ('start_pos', 'target_pos', 'mesh_type', 'scale', 'lifetime', 'elapsed', 'position')
    def __init__(self, pos, direction, mesh_type, scale, lifetime=2.0):
        self.start_pos = numpy.array(pos, dtype=float)
        self.position = self.start_pos.copy()
        self.mesh_type = mesh_type
        self.scale = scale
        self.lifetime = lifetime
        self.elapsed = 0.0

        # Guard against zero direction
        if numpy.linalg.norm(direction) < 0.01:
            direction = numpy.array([1.0, 0.0, 0.0])
        else:
            direction = direction / numpy.linalg.norm(direction)

        # Move at most 1.0 units (about the size of the part)
        horiz_distance = min(1.0, max(scale[0], scale[2]) * 0.8)
        horiz_offset = direction * horiz_distance
        target_x = self.start_pos[0] + horiz_offset[0]
        target_z = self.start_pos[2] + horiz_offset[2]
        target_y = get_height(target_x, target_z) + 0.2   # rest on ground
        self.target_pos = numpy.array([target_x, target_y, target_z])

    def update(self, dt, terrain_func=get_height):
        self.elapsed += dt
        if self.elapsed >= self.lifetime:
            return False
        t = self.elapsed / self.lifetime
        # Linear interpolation – smooth enough
        self.position = self.start_pos + (self.target_pos - self.start_pos) * t
        return True

    def get_model_matrix(self):
        mat = numpy.eye(4, dtype=numpy.float32)
        mat[0, 3] = self.position[0]
        mat[1, 3] = self.position[1]
        mat[2, 3] = self.position[2]
        mat[0, 0] = self.scale[0]
        mat[1, 1] = self.scale[1]
        mat[2, 2] = self.scale[2]
        return mat


class Mob:

    COLLISION_RADIUS = 0.6

    def __init__(self, position, chunk_cx, chunk_cz, speed=1.5, follow_range=8.0,
                 attack_range=2.0, damage=5, npc_type="basic"):
        self.position = numpy.array(position, dtype=float)
        self.chunk_cx = chunk_cx
        self.chunk_cz = chunk_cz
        self.speed = speed
        self.follow_range = follow_range
        self.attack_range = attack_range
        self.damage = damage
        self.npc_type = npc_type
        self.max_health = 50
        self.health = self.max_health
        self.attack_cooldown = 0.0
        self.loot_type = None

    def update(self, dt, player_pos, phys_size):
        dx = player_pos[0] - self.position[0]
        dz = player_pos[2] - self.position[2]
        dist = math.hypot(dx, dz)
        if dist < self.COLLISION_RADIUS:
            if dist > 0.01: # push away from player
                push_dir_x = -dx / dist
                push_dir_z = -dz / dist
            else:
                push_dir_x, push_dir_z = 1.0, 0.0
            push = self.speed * dt * 0.5
            self.position[0] += push_dir_x * push
            self.position[2] += push_dir_z * push
            new_cx = int(self.position[0] // phys_size)
            new_cz = int(self.position[2] // phys_size)
            self.position[1] = get_height(self.position[0], self.position[2]) + 0.5
            return new_cx, new_cz
        if dist < (self.follow_range * 1.5) and dist > 0.5:
            move = numpy.array([dx / dist, 0.0, dz / dist]) * self.speed * dt
            new_pos = self.position + move
            new_pos[1] = get_height(new_pos[0], new_pos[2]) + 0.5
            self.position = new_pos
        new_cx = int(self.position[0] // phys_size)
        new_cz = int(self.position[2] // phys_size)
        return new_cx, new_cz

    def to_dict(self):
        return {
            'pos_x': self.position[0], 'pos_y': self.position[1], 'pos_z': self.position[2],
            'npc_type': self.npc_type, 'speed': self.speed,
            'follow_range': self.follow_range, 'attack_range': self.attack_range,
            'damage': self.damage, 'health': self.health, 'max_health': self.max_health
        }

    @classmethod
    def from_dict(cls, data, chunk_cx, chunk_cz):
        mob = cls(
            position=(data['pos_x'], data['pos_y'], data['pos_z']),
            chunk_cx=chunk_cx, chunk_cz=chunk_cz,
            speed=data.get('speed', 2.5), follow_range=data.get('follow_range', 15.0),
            attack_range=data.get('attack_range', 2.0), damage=data.get('damage', 10),
            npc_type=data.get('npc_type', 'basic')
        )
        mob.health = data.get('health', mob.max_health)
        mob.max_health = data.get('max_health', mob.max_health)
        return mob

    def take_damage(self, amount):
        self.health -= amount
        return self.health <= 0

    def attack_enemy(self, enemy, dt):
        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt
            return False
        dx = enemy.position[0] - self.position[0]
        dz = enemy.position[2] - self.position[2]
        dist_sq = dx*dx + dz*dz
        if dist_sq < self.attack_range * self.attack_range:
            enemy.take_damage(self.damage)
            self.attack_cooldown = 1.0
            return True
        return False

    def is_alive(self):
        return self.health > 0


class MobModel:
    def __init__(self, shader: Shader):
        self.shader = shader
        # Build low‑poly sphere and pyramid VAOs (once)
        self.sphere_vao, self.sphere_index_count = self._build_sphere(radius=0.5, stacks=6, slices=8)
        self.pyramid_vao, self.pyramid_index_count = self._build_pyramid()
        # Simple cube VAO for distant mobs (LOD)
        self.cube_vao, self.cube_index_count = self._build_cube()

    def _build_sphere(self, radius, stacks, slices):
        """Low‑poly UV sphere with normals."""
        vertices = []
        indices = []
        for i in range(stacks + 1):
            theta = math.pi * i / stacks
            sin_theta = math.sin(theta)
            cos_theta = math.cos(theta)
            for j in range(slices + 1):
                phi = 2 * math.pi * j / slices
                x = radius * sin_theta * math.cos(phi)
                y = radius * cos_theta
                z = radius * sin_theta * math.sin(phi)
                nx, ny, nz = x / radius, y / radius, z / radius
                vertices.extend([x, y, z, nx, ny, nz])
        for i in range(stacks):
            for j in range(slices):
                first = i * (slices + 1) + j
                second = first + slices + 1
                indices.extend([first, second, first+1, second, second+1, first+1])
        vertices = numpy.array(vertices, dtype=numpy.float32)
        indices = numpy.array(indices, dtype=numpy.uint32)
        vao, vbo, ebo = glGenVertexArrays(1), glGenBuffers(1), glGenBuffers(1)
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6*4, ctypes.c_void_p(3*4))
        glEnableVertexAttribArray(1)
        glBindVertexArray(0)
        return vao, len(indices)

    def _build_pyramid(self):
        """Square‑based pyramid (apex at +Y) – unchanged."""
        v = [
            -0.5, 0.0, -0.5,  0.0, -1.0, 0.0,
             0.5, 0.0, -0.5,  0.0, -1.0, 0.0,
             0.5, 0.0,  0.5,  0.0, -1.0, 0.0,
            -0.5, 0.0,  0.5,  0.0, -1.0, 0.0,
             0.0, 0.5,  0.0,  0.0,  1.0, 0.0,
        ]
        indices = [
            0,1,4, 1,2,4, 2,3,4, 3,0,4,
            0,2,1, 0,3,2
        ]
        vertices = numpy.array(v, dtype=numpy.float32)
        indices = numpy.array(indices, dtype=numpy.uint32)
        vao, vbo, ebo = glGenVertexArrays(1), glGenBuffers(1), glGenBuffers(1)
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6*4, ctypes.c_void_p(3*4))
        glEnableVertexAttribArray(1)
        glBindVertexArray(0)
        return vao, len(indices)

    def _build_cube(self):
        """Simple cube for distant LOD."""
        vertices = numpy.array([
            -0.5,-0.5, 0.5,  0,0,1,
             0.5,-0.5, 0.5,  0,0,1,
             0.5, 0.5, 0.5,  0,0,1,
            -0.5, 0.5, 0.5,  0,0,1,
            -0.5,-0.5,-0.5,  0,0,-1,
             0.5,-0.5,-0.5,  0,0,-1,
             0.5, 0.5,-0.5,  0,0,-1,
            -0.5, 0.5,-0.5,  0,0,-1,
            -0.5,-0.5,-0.5, -1,0,0,
            -0.5,-0.5, 0.5, -1,0,0,
            -0.5, 0.5, 0.5, -1,0,0,
            -0.5, 0.5,-0.5, -1,0,0,
             0.5,-0.5,-0.5,  1,0,0,
             0.5,-0.5, 0.5,  1,0,0,
             0.5, 0.5, 0.5,  1,0,0,
             0.5, 0.5,-0.5,  1,0,0,
            -0.5, 0.5,-0.5,  0,1,0,
             0.5, 0.5,-0.5,  0,1,0,
             0.5, 0.5, 0.5,  0,1,0,
            -0.5, 0.5, 0.5,  0,1,0,
            -0.5,-0.5,-0.5,  0,-1,0,
             0.5,-0.5,-0.5,  0,-1,0,
             0.5,-0.5, 0.5,  0,-1,0,
            -0.5,-0.5, 0.5,  0,-1,0,
        ], dtype=numpy.float32)
        indices = numpy.array([
            0,1,2, 0,2,3, 4,5,6, 4,6,7, 8,9,10, 8,10,11,
            12,13,14, 12,14,15, 16,17,18, 16,18,19, 20,21,22, 20,22,23
        ], dtype=numpy.uint32)
        vao, vbo, ebo = glGenVertexArrays(1), glGenBuffers(1), glGenBuffers(1)
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6*4, ctypes.c_void_p(3*4))
        glEnableVertexAttribArray(1)
        glBindVertexArray(0)
        return vao, len(indices)

    def draw(self, mob, view, projection, light_dir, light_intensity, camera_pos):
        """Draw mob with LOD and frustum culling."""
        # Frustum culling (simple sphere test)
        center = mob.position
        radius = 0.8  # approximate bounding sphere
        # Get view frustum planes from view-projection matrix (simplified)
        vp = projection @ view
        # Test if sphere is in front of near plane (z < 0 in clip space)
        # For simplicity, just check distance from camera
        dist = numpy.linalg.norm(camera_pos - center)
        if dist > 60:  # beyond draw distance
            return

        # LOD: use cube for distant mobs (>30 units)
        use_cube = dist > 30.0

        glUseProgram(self.shader.program)
        self.shader.set_mat4("uView", view)
        self.shader.set_mat4("uProjection", projection)
        self.shader.set_vec3("uLightDir", light_dir)
        self.shader.set_float("uLightIntensity", light_intensity)

        def build_model(pos, scale, rot_deg=0.0):
            mat = numpy.eye(4, dtype=numpy.float32)
            mat[0,3], mat[1,3], mat[2,3] = pos
            mat[0,0], mat[1,1], mat[2,2] = scale
            if rot_deg != 0.0:
                rad = math.radians(rot_deg)
                c, s = math.cos(rad), math.sin(rad)
                rot = numpy.array([
                    [c, 0, s, 0],
                    [0, 1, 0, 0],
                    [-s, 0, c, 0],
                    [0, 0, 0, 1]
                ], dtype=numpy.float32)
                mat = rot @ mat
            return mat

        if use_cube:
            glBindVertexArray(self.cube_vao)
            self.current_index_count = self.cube_index_count
            # Draw a single cube (body only) for distant mobs
            body_pos = mob.position + numpy.array([0.0, 0.3, 0.0])
            self.shader.set_mat4("uModel", build_model(body_pos, (0.8, 0.8, 0.8)))
            glDrawElements(GL_TRIANGLES, self.current_index_count, GL_UNSIGNED_INT, None)
        else:
            # Full detail: sphere for body/head/legs, pyramid for nose/tail
            glBindVertexArray(self.sphere_vao)
            self.current_index_count = self.sphere_index_count

            # Body
            body_pos = mob.position + numpy.array([0.0, 0.2, 0.0])
            self.shader.set_mat4("uModel", build_model(body_pos, (0.8, 0.6, 0.8)))
            glDrawElements(GL_TRIANGLES, self.current_index_count, GL_UNSIGNED_INT, None)

            # Head
            head_pos = mob.position + numpy.array([0.0, 0.5, 0.5])
            self.shader.set_mat4("uModel", build_model(head_pos, (0.5, 0.5, 0.5)))
            glDrawElements(GL_TRIANGLES, self.current_index_count, GL_UNSIGNED_INT, None)

            # Legs (4 ellipsoids)
            leg_scale = (0.3, 0.2, 0.3)
            leg_offsets = [(-0.4, 0.0, -0.5), (0.4, 0.0, -0.5), (-0.4, 0.0, 0.5), (0.4, 0.0, 0.5)]
            for off in leg_offsets:
                leg_pos = mob.position + numpy.array([off[0], 0.0, off[2]])
                self.shader.set_mat4("uModel", build_model(leg_pos, leg_scale))
                glDrawElements(GL_TRIANGLES, self.current_index_count, GL_UNSIGNED_INT, None)

            # Nose (pyramid)
            glBindVertexArray(self.pyramid_vao)
            self.current_index_count = self.pyramid_index_count
            nose_pos = mob.position + numpy.array([0.0, 0.5, 0.85])
            self.shader.set_mat4("uModel", build_model(nose_pos, (0.2, 0.2, 0.3)))
            glDrawElements(GL_TRIANGLES, self.current_index_count, GL_UNSIGNED_INT, None)

            # Tail (pyramid)
            tail_pos = mob.position + numpy.array([0.0, 0.2, -0.7])
            self.shader.set_mat4("uModel", build_model(tail_pos, (0.2, 0.15, 0.4), rot_deg=180))
            glDrawElements(GL_TRIANGLES, self.current_index_count, GL_UNSIGNED_INT, None)

        glBindVertexArray(0)


class MobManager:
    def __init__(self, player, chunk_manager, chunk_size=32, spacing=1.0, loot_manager=None):
        self.player = player
        self.chunk_manager = chunk_manager
        self.serializer = chunk_manager.serializer
        self.chunk_size = chunk_size
        self.spacing = spacing
        self.phys_size = (chunk_size - 1) * spacing
        self.active_mobs = {}
        self.loaded_chunks = set()
        self.pending_mobs = {}
        self.loot_manager = loot_manager

        # Mob model
        self.mob_model = MobModel(Shader(MOB_VERTEX_SHADER_SRC, MOB_FRAGMENT_SHADER_SRC))

        # Expose VAOs for parts drawing
        self.sphere_vao = self.mob_model.sphere_vao
        self.sphere_index_count = self.mob_model.sphere_index_count
        self.pyramid_vao = self.mob_model.pyramid_vao
        self.pyramid_index_count = self.mob_model.pyramid_index_count
        self.dead_parts = []          # list of FlyingPart objects

        # Particle system
        self.particles = []
        self.particle_shader = Shader(PARTICLE_AMMO_EXPLOSION_VERTEX_SHADER_SRC, PARTICLE_AMMO_EXPLOSION_FRAGMENT_SHADER_SRC)
        self.particle_vao = glGenVertexArrays(1)
        self.particle_vbo = glGenBuffers(1)
        glBindVertexArray(self.particle_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.particle_vbo)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, None)
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)

        # Health bar rendering (GUI-like)
        self._init_health_bar_ui()

    def _init_health_bar_ui(self):
        # Reuse the same rect shader as GUI (simplified)
        self.health_shader = compileProgram(
            compileShader(RECT_VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(RECT_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
        )
        # Quad VAO (same as stats panel)
        quad_verts = numpy.array([
            -0.5, -0.5, 0.0, 0.0,
             0.5, -0.5, 1.0, 0.0,
             0.5,  0.5, 1.0, 1.0,
            -0.5,  0.5, 0.0, 1.0,
        ], dtype=numpy.float32)
        quad_indices = numpy.array([0,1,2, 0,2,3], dtype=numpy.uint32)
        self.health_vao = glGenVertexArrays(1)
        self.health_vbo = glGenBuffers(1)
        self.health_ebo = glGenBuffers(1)
        glBindVertexArray(self.health_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.health_vbo)
        glBufferData(GL_ARRAY_BUFFER, quad_verts.nbytes, quad_verts, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.health_ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, quad_indices.nbytes, quad_indices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(8))
        glEnableVertexAttribArray(1)
        glBindVertexArray(0)
        self.health_quad_count = 6
        self.health_uScreenSize = glGetUniformLocation(self.health_shader, "uScreenSize")
        self.health_uColor = glGetUniformLocation(self.health_shader, "uColor")
        self.health_uOffset = glGetUniformLocation(self.health_shader, "uOffset")
        self.health_uScale = glGetUniformLocation(self.health_shader, "uScale")

    def _generate_mobs_for_chunk(self, cx, cz):
        world_min_x = cx * self.phys_size
        world_min_z = cz * self.phys_size
        world_max_x = world_min_x + self.phys_size
        world_max_z = world_min_z + self.phys_size
        count = random.randint(0, 1)
        mobs = []
        for _ in range(count):
            x = random.uniform(world_min_x, world_max_x)
            z = random.uniform(world_min_z, world_max_z)
            y = get_height(x, z) + 0.5
            mob = Mob((x, y, z), cx, cz)
            mob.max_health = random.randint(30, 80)
            mob.health = mob.max_health
            mob.damage = random.randint(8, 20)
            #mob.loot_type = LOOT_TYPES[random.randint(0, 1)]
            if random.random() < 1.0:
                loot_keys = list(LOOT_TYPES.keys())
                if loot_keys:
                    mob.loot_type = LOOT_TYPES[random.choice(loot_keys)]
            mobs.append(mob)
        return mobs

    def _load_mobs_for_chunk(self, cx, cz):
        mobs_data = self.serializer.load_mobs(cx, cz)
        if mobs_data is None:
            mobs_data = []
        pending = self.pending_mobs.pop((cx, cz), [])
        if pending:
            mobs_data.extend(pending)
        if mobs_data:
            return [Mob.from_dict(d, cx, cz) for d in mobs_data]
        else:
            return self._generate_mobs_for_chunk(cx, cz)

    def _update_spatial_grid(self):
        """Rebuild grid based on current mob positions (called each frame)."""
        self.grid = {}
        cell_size = 10.0  # 10 units per cell
        for mobs in self.active_mobs.values():
            for mob in mobs:
                if not mob.is_alive():
                    continue
                cx = int(mob.position[0] // cell_size)
                cz = int(mob.position[2] // cell_size)
                key = (cx, cz)
                self.grid.setdefault(key, []).append(mob)

    def update_dead_parts(self, dt):
        """Update all flying parts, remove expired ones."""
        self.dead_parts = [p for p in self.dead_parts if p.update(dt, get_height)]

    def dismantle_mob(self, mob, impact_point, lifetime=2.0):
        """Replace a dying mob with animated parts that slide sideways and drop to ground."""
        # Remove mob from active_mobs
        key = (mob.chunk_cx, mob.chunk_cz)
        if key in self.active_mobs:
            self.active_mobs[key] = [m for m in self.active_mobs[key] if m is not mob]

        if mob.loot_type is not None:
            # Spawn loot at a random direction, 1.2 to 2.0 units away
            angle = random.uniform(0, 2 * math.pi)
            radius = random.uniform(1.2, 2.0)
            offset_x = math.cos(angle) * radius
            offset_z = math.sin(angle) * radius
            loot_pos = numpy.array([impact_point[0] + offset_x,
                                    impact_point[1],
                                    impact_point[2] + offset_z])
            # Place loot on ground
            loot_pos[1] = get_height(loot_pos[0], loot_pos[2]) + 0.5
            self.loot_manager.add_loot(mob.loot_type(loot_pos))
            #logging.debug(f'Restore LOOT {mob.loot_type} at {loot_pos}')

        # Determine directions – safe against vertical alignment
        to_player = self.player.position - mob.position
        dist_to_player = numpy.linalg.norm(to_player)
        if dist_to_player < 0.01:
            forward = numpy.array([0.0, 0.0, 1.0])
        else:
            forward = to_player / dist_to_player

        up = numpy.array([0.0, 1.0, 0.0])
        right = numpy.cross(forward, up)
        if numpy.linalg.norm(right) < 0.01:
            right = numpy.array([1.0, 0.0, 0.0])
        else:
            right = right / numpy.linalg.norm(right)
        left = -right
        backward = -forward

        def add_part(offset, direction, mesh_type, scale):
            pos = mob.position + numpy.array(offset)
            self.dead_parts.append(FlyingPart(pos, direction, mesh_type, scale, lifetime))

        # Body – slides left
        add_part((0.0, 0.2, 0.0), left, 'sphere', (0.8, 0.6, 0.8))
        # Head – slides right
        add_part((0.0, 0.5, 0.5), right, 'sphere', (0.5, 0.5, 0.5))
        # Front legs – slide forward
        front_leg_offsets = [(-0.4, 0.0, -0.5), (0.4, 0.0, -0.5)]
        for off in front_leg_offsets:
            add_part(off, forward, 'sphere', (0.3, 0.2, 0.3))
        # Hind legs – slide backward
        hind_leg_offsets = [(-0.4, 0.0, 0.5), (0.4, 0.0, 0.5)]
        for off in hind_leg_offsets:
            add_part(off, backward, 'sphere', (0.3, 0.2, 0.3))
        # Tail – slides backward
        add_part((0.0, 0.2, -0.7), backward, 'pyramid', (0.2, 0.15, 0.4))
        #logging.debug(f"dismantle_mob added {len(self.dead_parts)} parts")

        self.add_particles(impact_point, count=20)

    def get_nearby_mobs(self, center, radius):
        """Return mobs within a radius using grid lookup."""
        cell_size = 10.0
        min_cx = int((center[0] - radius) // cell_size)
        max_cx = int((center[0] + radius) // cell_size)
        min_cz = int((center[2] - radius) // cell_size)
        max_cz = int((center[2] + radius) // cell_size)
        nearby = []
        for cx in range(min_cx, max_cx + 1):
            for cz in range(min_cz, max_cz + 1):
                mobs = self.grid.get((cx, cz), [])
                for mob in mobs:
                    if numpy.linalg.norm(mob.position - center) <= radius:
                        nearby.append(mob)
        return nearby

    def update(self, dt):
        # Remove dead mobs
        for chunk_key, mobs in list(self.active_mobs.items()):
            self.active_mobs[chunk_key] = [m for m in mobs if m.is_alive()]
        current_chunks = set(self.chunk_manager.chunks.keys())
        # Unload
        for chunk_key in list(self.loaded_chunks):
            if chunk_key not in current_chunks:
                if chunk_key in self.active_mobs:
                    del self.active_mobs[chunk_key]
                self.loaded_chunks.discard(chunk_key)
        # Load
        for chunk_key in current_chunks:
            if chunk_key not in self.loaded_chunks:
                mobs = self._load_mobs_for_chunk(chunk_key[0], chunk_key[1])
                self.active_mobs[chunk_key] = mobs
                self.loaded_chunks.add(chunk_key)
        player_pos = numpy.array(self.player.position)
        # Cap total mobs to 30
        total_mobs = sum(len(mobs) for mobs in self.active_mobs.values())
        if total_mobs > 30:
            # Remove excess mobs from the farthest chunks
            chunks_sorted = sorted(self.active_mobs.items(), key=lambda x:
                (x[0][0] - player_pos[0]//self.phys_size)**2 +
                (x[0][1] - player_pos[2]//self.phys_size)**2, reverse=True)
            for (cx, cz), mobs in chunks_sorted:
                if total_mobs <= 30:
                    break
                removed = mobs[:total_mobs-30]
                self.active_mobs[(cx, cz)] = mobs[len(removed):]
                total_mobs = sum(len(m) for m in self.active_mobs.values())
        mobs_to_remove = []
        mobs_to_add = []
        for chunk_key, mobs in list(self.active_mobs.items()):
            for i, mob in enumerate(mobs):
                new_cx, new_cz = mob.update(dt, player_pos, self.phys_size)
                new_key = (new_cx, new_cz)
                if new_key != chunk_key:
                    mobs_to_remove.append((chunk_key, i, mob))
                    if new_key in self.loaded_chunks:
                        mob.chunk_cx = new_cx
                        mob.chunk_cz = new_cz
                        mobs_to_add.append((new_key, mob))
                    else:
                        pending = self.pending_mobs.setdefault(new_key, [])
                        pending.append(mob.to_dict())
                mob.attack_enemy(self.player, dt)
        # Apply removals
        for chunk_key, idx, mob in mobs_to_remove:
            if chunk_key in self.active_mobs:
                lst = self.active_mobs[chunk_key]
                if idx < len(lst) and lst[idx] is mob:
                    lst.pop(idx)
        # Apply additions
        for new_key, mob in mobs_to_add:
            self.active_mobs.setdefault(new_key, []).append(mob)
        # Update particles
        self.particles = [p for p in self.particles if p.life > 0]
        for p in self.particles:
            p.life -= dt * 2.0
        self.update_dead_parts(dt)
        self._update_spatial_grid()

    def draw_health_bars(self, view, proj, screen_width, screen_height):
        """Call after 3D rendering, with depth test disabled."""
        if not self.active_mobs:
            return
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glUseProgram(self.health_shader)
        glUniform2f(self.health_uScreenSize, screen_width, screen_height)
        # Helper to project world to screen
        def world_to_screen(pos, view_mat, proj_mat, width, height):
            clip = proj_mat @ view_mat @ numpy.append(pos, 1.0)
            if clip[3] == 0:
                return None
            ndc = clip[:3] / clip[3]
            if ndc[2] < -1 or ndc[2] > 1:
                return None
            x = (ndc[0] + 1.0) * 0.5 * width
            y = (1.0 - (ndc[1] + 1.0) * 0.5) * height
            return (x, y)
        bar_width = 60
        bar_height = 8
        y_offset = 0.8
        for mobs in self.active_mobs.values():
            for mob in mobs:
                if numpy.linalg.norm(self.player.position - mob.position) > 40:
                    continue
                # Project mob position
                world_pos = mob.position + numpy.array([0.0, y_offset, 0.0])
                screen_pos = world_to_screen(world_pos, view, proj, screen_width, screen_height)
                if screen_pos is None:
                    continue
                x, y = screen_pos
                x -= bar_width / 2
                # Background (dark red)
                glUniform4f(self.health_uColor, 0.3, 0.0, 0.0, 0.8)
                self._draw_health_rect(x, y, bar_width, bar_height, screen_width, screen_height)
                # Foreground (green fill)
                fill_width = bar_width * (mob.health / mob.max_health)
                glUniform4f(self.health_uColor, 0.0, 0.8, 0.0, 0.9)
                self._draw_health_rect(x, y, fill_width, bar_height, screen_width, screen_height)
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)

    def draw(self, view, projection, light_dir, light_intensity, screen_width, screen_height):
        # Draw mobs
        for mobs in self.active_mobs.values():
            for mob in mobs:
                self.mob_model.draw(mob, view, projection, light_dir, light_intensity, self.player.position)
        if self.particles: # Draw particles (point sprites)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glEnable(GL_PROGRAM_POINT_SIZE)
            self.particle_shader.use()
            self.particle_shader.set_mat4("uView", view)
            self.particle_shader.set_mat4("uProjection", projection)
            glBindVertexArray(self.particle_vao)
            # Build vertex buffer
            positions = numpy.array([p.position for p in self.particles], dtype=numpy.float32).flatten()
            glBindBuffer(GL_ARRAY_BUFFER, self.particle_vbo)
            glBufferData(GL_ARRAY_BUFFER, positions.nbytes, positions, GL_DYNAMIC_DRAW)
            for i, p in enumerate(self.particles):
                self.particle_shader.set_float("uSize", 20.0)
                self.particle_shader.set_float("uLife", p.life)
                glDrawArrays(GL_POINTS, i, 1)
            glBindVertexArray(0)
            glDisable(GL_PROGRAM_POINT_SIZE)
            glDisable(GL_BLEND)
        #logging.debug(f"drawing {len(self.dead_parts)} dead parts")
        if self.dead_parts:
            self.mob_model.shader.use()
            self.mob_model.shader.set_mat4("uView", view)
            self.mob_model.shader.set_mat4("uProjection", projection)
            self.mob_model.shader.set_vec3("uLightDir", light_dir)
            self.mob_model.shader.set_float("uLightIntensity", light_intensity)
            for part in self.dead_parts:
                model = part.get_model_matrix()
                self.mob_model.shader.set_mat4("uModel", model)
                if part.mesh_type == 'sphere':
                    glBindVertexArray(self.sphere_vao)
                    glDrawElements(GL_TRIANGLES, self.sphere_index_count, GL_UNSIGNED_INT, None)
                else:  # pyramid
                    glBindVertexArray(self.pyramid_vao)
                    glDrawElements(GL_TRIANGLES, self.pyramid_index_count, GL_UNSIGNED_INT, None)
            glBindVertexArray(0)
        self.draw_health_bars(view, projection, screen_width, screen_height)

    def _draw_health_rect(self, x, y, w, h, screen_w, screen_h):
        y_bottom = screen_h - (y + h)
        glUniform2f(self.health_uOffset, x + w/2, y_bottom + h/2)
        glUniform2f(self.health_uScale, w, h)
        glBindVertexArray(self.health_vao)
        glDrawElements(GL_TRIANGLES, self.health_quad_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def add_particles(self, position, count=8):
        for _ in range(count):
            self.particles.append(Particle(position))

    def shutdown(self):
        for (cx, cz), mobs in self.active_mobs.items():
            data = [mob.to_dict() for mob in mobs]
            self.serializer.save_mobs(cx, cz, data)
        for (cx, cz), pending_list in self.pending_mobs.items():
            existing = self.serializer.load_mobs(cx, cz)
            if existing is None:
                existing = []
            existing.extend(pending_list)
            self.serializer.save_mobs(cx, cz, existing)
        self.active_mobs.clear()
        self.loaded_chunks.clear()
        self.pending_mobs.clear()
