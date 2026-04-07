import numpy
import math
import random
import ctypes

from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader

from logger import logging
from shaders.shader import Shader
from shaders.tree_shdr import TREE_FRAGMENT_SHADER_SRC, TREE_VERTEX_SHADER_SRC


class TreeGeometry:
    """Pre-computed geometry for trees (shared across all tree instances)."""

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
        #logging.debug("Initializing TreeGeometry...")
        self._build_trunk_cylinder()
        self._build_foliage_sphere()
        self._create_textures()
        #logging.debug(f"  Trunk VAO: {TreeGeometry._trunk_vao}, vertices: {TreeGeometry._trunk_vertex_count}")
        #logging.debug(f"  Foliage VAO: {TreeGeometry._foliage_vao}, vertices: {TreeGeometry._foliage_vertex_count}")

    def _build_trunk_cylinder(self, radius=0.25, height=1.2, segments=12):
        """Build a cylinder mesh with bottom at Y=0, top at Y=height."""
        vertices = []
        indices = []

        # Generate vertices for cylinder sides
        for i in range(segments + 1):
            angle = 2 * math.pi * i / segments
            x = radius * math.cos(angle)
            z = radius * math.sin(angle)
            nx = math.cos(angle)
            nz = math.sin(angle)

            # Bottom vertex (y = 0)
            u = i / segments
            vertices.append([x, 0.0, z, nx, 0, nz, u, 1.0])
            # Top vertex (y = height)
            vertices.append([x, height, z, nx, 0, nz, u, 0.0])

        # Generate indices for cylinder sides
        for i in range(segments):
            i0 = i * 2
            i1 = i0 + 1
            i2 = (i + 1) * 2
            i3 = i2 + 1
            indices.extend([i0, i1, i2, i1, i3, i2])

        # Bottom cap center
        center_idx = len(vertices)
        vertices.append([0, 0.0, 0, 0, -1, 0, 0.5, 0.5])

        # Bottom cap triangles
        for i in range(segments):
            i0 = i * 2
            i1 = ((i + 1) % segments) * 2
            indices.extend([center_idx, i0, i1])

        # Top cap center
        center_idx = len(vertices)
        vertices.append([0, height, 0, 0, 1, 0, 0.5, 0.5])

        # Top cap triangles
        for i in range(segments):
            i0 = i * 2 + 1
            i1 = ((i + 1) % segments) * 2 + 1
            indices.extend([center_idx, i1, i0])

        # Convert to numpy arrays
        vertices_arr = numpy.array(vertices, dtype=numpy.float32).flatten()
        indices_arr = numpy.array(indices, dtype=numpy.uint32)

        # Create VAO, VBO, EBO
        TreeGeometry._trunk_vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        ebo = glGenBuffers(1)

        glBindVertexArray(TreeGeometry._trunk_vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices_arr.nbytes, vertices_arr, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices_arr.nbytes, indices_arr, GL_STATIC_DRAW)

        # Position attribute (location 0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 8*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        # Normal attribute (location 1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 8*4, ctypes.c_void_p(3*4))
        glEnableVertexAttribArray(1)
        # TexCoord attribute (location 2)
        glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, 8*4, ctypes.c_void_p(6*4))
        glEnableVertexAttribArray(2)

        glBindVertexArray(0)
        TreeGeometry._trunk_vertex_count = len(indices)

        # Cleanup buffers (they're still bound to VAO)
        glDeleteBuffers(1, [vbo])
        glDeleteBuffers(1, [ebo])

    def _build_foliage_sphere(self, radius=0.55, stacks=16, slices=16):
        """Build an elongated sphere (ellipsoid) for foliage."""
        vertices = []
        indices = []

        # Elongate along Y axis
        y_scale = 1.3

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

                # Position
                x = radius * sin_theta * cos_phi
                y = radius * y_scale * cos_theta
                z = radius * sin_theta * sin_phi

                # Normal (approximate)
                nx = x / radius
                ny = y / (radius * y_scale)
                nz = z / radius
                norm = math.sqrt(nx*nx + ny*ny + nz*nz)
                if norm > 0:
                    nx /= norm
                    ny /= norm
                    nz /= norm

                vertices.append([x, y, z, nx, ny, nz, u, v])

        # Generate indices
        for i in range(stacks):
            for j in range(slices):
                i0 = i * (slices + 1) + j
                i1 = i0 + 1
                i2 = (i + 1) * (slices + 1) + j
                i3 = i2 + 1
                indices.extend([i0, i2, i1, i1, i2, i3])

        # Convert to numpy arrays
        vertices_arr = numpy.array(vertices, dtype=numpy.float32).flatten()
        indices_arr = numpy.array(indices, dtype=numpy.uint32)

        # Create VAO, VBO, EBO
        TreeGeometry._foliage_vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        ebo = glGenBuffers(1)

        glBindVertexArray(TreeGeometry._foliage_vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices_arr.nbytes, vertices_arr, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices_arr.nbytes, indices_arr, GL_STATIC_DRAW)

        # Position attribute (location 0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 8*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        # Normal attribute (location 1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 8*4, ctypes.c_void_p(3*4))
        glEnableVertexAttribArray(1)
        # TexCoord attribute (location 2)
        glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, 8*4, ctypes.c_void_p(6*4))
        glEnableVertexAttribArray(2)

        glBindVertexArray(0)
        TreeGeometry._foliage_vertex_count = len(indices)

        # Cleanup buffers
        glDeleteBuffers(1, [vbo])
        glDeleteBuffers(1, [ebo])

    def _create_textures(self):
        """Create procedural textures for trunk (brown wood) and foliage (green with variation)."""
        # Trunk texture: brown wood grain
        trunk_size = 64
        trunk_data = numpy.zeros((trunk_size, trunk_size, 4), dtype=numpy.uint8)
        for y in range(trunk_size):
            for x in range(trunk_size):
                # Wood grain pattern
                grain = int(20 * math.sin(x * 0.3) + 20 * math.cos(y * 0.2))
                r = 100 + grain % 40
                g = 60 + grain % 30
                b = 30 + grain % 20
                trunk_data[y, x] = [r, g, b, 255]

        TreeGeometry._trunk_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, TreeGeometry._trunk_texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, trunk_size, trunk_size, 0, GL_RGBA, GL_UNSIGNED_BYTE, trunk_data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glGenerateMipmap(GL_TEXTURE_2D)

        # Foliage texture: green with light/dark variation
        foliage_size = 64
        foliage_data = numpy.zeros((foliage_size, foliage_size, 4), dtype=numpy.uint8)
        for y in range(foliage_size):
            for x in range(foliage_size):
                # Create a leafy pattern with variation
                noise = (math.sin(x * 0.2) * math.cos(y * 0.15) + 1) / 2
                if noise > 0.7:
                    # Light green highlight
                    r, g, b = 80, 180, 60
                elif noise > 0.3:
                    # Medium green
                    r, g, b = 40, 140, 40
                else:
                    # Dark green shadow
                    r, g, b = 30, 90, 30
                # Add some speckle variation
                if (x * 7 + y * 13) % 17 < 3:
                    r = min(255, r + 20)
                    g = min(255, g + 20)
                foliage_data[y, x] = [r, g, b, 255]

        TreeGeometry._foliage_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, TreeGeometry._foliage_texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, foliage_size, foliage_size, 0, GL_RGBA, GL_UNSIGNED_BYTE, foliage_data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glGenerateMipmap(GL_TEXTURE_2D)

        glBindTexture(GL_TEXTURE_2D, 0)

    @classmethod
    def get_trunk_vao(cls):
        return cls._trunk_vao

    @classmethod
    def get_trunk_vertex_count(cls):
        return cls._trunk_vertex_count

    @classmethod
    def get_trunk_index_count(cls):
        return cls._trunk_index_count

    @classmethod
    def get_trunk_texture(cls):
        return cls._trunk_texture

    @classmethod
    def get_foliage_vao(cls):
        return cls._foliage_vao

    @classmethod
    def get_foliage_index_count(cls):
        return cls._foliage_index_count

    @classmethod
    def get_foliage_texture(cls):
        return cls._foliage_texture

    @classmethod
    def get_foliage_vertex_count(cls):
        return cls._foliage_vertex_count


class Tree:
    """Tree entity with brown cylinder trunk and green elongated sphere foliage."""

    def __init__(self, position, trunk_height=1.2, trunk_radius=0.25, foliage_radius=0.55):
        """
        Initialize a tree at the given position.

        Args:
            position: (x, y, z) tuple or array for tree BASE (bottom of trunk)
            trunk_height: Height of the trunk in world units
            trunk_radius: Radius of the trunk cylinder
            foliage_radius: Radius of the foliage sphere
        """
        self.position = numpy.array(position, dtype=float)
        self.trunk_height = trunk_height
        self.trunk_radius = trunk_radius
        self.foliage_radius = foliage_radius

        # Random rotation for variety
        self.rotation_y = random.uniform(0, 2 * math.pi)

        # Ensure geometry is initialized
        self.geometry = TreeGeometry.get_instance()

    def get_ground_contact(self):
        """Return the Y-coordinate where the trunk meets the ground."""
        # The trunk extends from position.y (bottom) to position.y + trunk_height
        return self.position[1]

    def get_bounding_radius(self):
        """Return bounding radius for culling."""
        return max(self.trunk_radius, self.foliage_radius) + self.trunk_height

    def get_position(self):
        """Return tree position."""
        return self.position

    def to_dict(self):
        """Serialize tree to dictionary for saving."""
        return {
            'pos_x': float(self.position[0]),
            'pos_y': float(self.position[1]),
            'pos_z': float(self.position[2]),
            'trunk_height': self.trunk_height,
            'trunk_radius': self.trunk_radius,
            'foliage_radius': self.foliage_radius,
            'rotation_y': self.rotation_y
        }

    @classmethod
    def from_dict(cls, data):
        """Deserialize tree from dictionary - Y coordinate is NOT loaded from DB."""
        tree = cls(
            position=(data['pos_x'], 0.0, data['pos_z']),
            trunk_height=data.get('trunk_height', 1.2),
            trunk_radius=data.get('trunk_radius', 0.25),
            foliage_radius=data.get('foliage_radius', 0.55)
        )
        tree.rotation_y = data.get('rotation_y', random.uniform(0, 2 * math.pi))
        return tree

    def draw(self, shader, view, projection, light_dir, light_intensity):
        """Draw the tree using the provided shader."""
        if self.geometry.get_trunk_vao() is None:
            return

        # Debug: Skip drawing if tree is underground
        if self.position[1] < 0.1:
            return

        shader.use()
        shader.set_mat4("uView", view)
        shader.set_mat4("uProjection", projection)
        shader.set_vec3("uLightDir", light_dir)
        shader.set_float("uLightIntensity", light_intensity)

        # Build model matrix
        model = numpy.eye(4, dtype=numpy.float32)
        model[0, 3] = self.position[0]
        model[1, 3] = self.position[1]
        model[2, 3] = self.position[2]

        # Rotation around Y axis
        c = math.cos(self.rotation_y)
        s = math.sin(self.rotation_y)
        rot_y = numpy.array([
            [c, 0, s, 0],
            [0, 1, 0, 0],
            [-s, 0, c, 0],
            [0, 0, 0, 1]
        ], dtype=numpy.float32)
        model = rot_y @ model

        # Draw trunk
        shader.set_mat4("uModel", model)
        shader.set_int("uPart", 0)

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.geometry.get_trunk_texture())
        shader.set_int("uTrunkTexture", 0)

        glBindVertexArray(self.geometry.get_trunk_vao())
        glDrawElements(GL_TRIANGLES, self.geometry.get_trunk_vertex_count(), GL_UNSIGNED_INT, None)

        # Draw foliage
        foliage_model = numpy.copy(model)
        foliage_model[1, 3] = self.position[1] + self.trunk_height
        shader.set_mat4("uModel", foliage_model)
        shader.set_int("uPart", 1)

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.geometry.get_foliage_texture())
        shader.set_int("uFoliageTexture", 0)

        glBindVertexArray(self.geometry.get_foliage_vao())
        glDrawElements(GL_TRIANGLES, self.geometry.get_foliage_vertex_count(), GL_UNSIGNED_INT, None)

        glBindVertexArray(0)
        glBindTexture(GL_TEXTURE_2D, 0)


class TreeManager:
    """Manages trees across chunks with auto-generation (0-2 per chunk)."""

    def __init__(self, chunk_manager, chunk_size=16, spacing=1.0):
        self.chunk_manager = chunk_manager
        self.chunk_size = chunk_size
        self.spacing = spacing
        self.phys_size = (chunk_size - 1) * spacing

        self.trees = {}
        self.loaded_chunks = set()

        self.shader = Shader(TREE_VERTEX_SHADER_SRC, TREE_FRAGMENT_SHADER_SRC)
        self.serializer = getattr(chunk_manager, 'serializer', None)

    def _generate_trees_for_chunk(self, cx, cz):
        """Generate 0-2 trees randomly within a chunk."""
        world_min_x = cx * self.phys_size
        world_min_z = cz * self.phys_size
        world_max_x = world_min_x + self.phys_size
        world_max_z = world_min_z + self.phys_size

        tree_count = random.randint(0, 2)
        trees = []

        for _ in range(tree_count):
            x = random.uniform(world_min_x + 1.5, world_max_x - 1.5)
            z = random.uniform(world_min_z + 1.5, world_max_z - 1.5)

            from camera import get_height
            terrain_y = get_height(x, z)

            # Ensure tree is not placed below ground
            # Clamp to minimum 0.2 to avoid underground placement
            y = max(terrain_y, 0.2)

            trunk_height = 1.0 + random.uniform(-0.2, 0.4)
            foliage_radius = 0.5 + random.uniform(-0.1, 0.15)

            tree = Tree((x, y, z), trunk_height=trunk_height, foliage_radius=foliage_radius)
            trees.append(tree)

            # Detailed debug output
            #if terrain_y < 0:
                #logging.debug(f"  Tree at chunk ({cx},{cz}): terrain_y={terrain_y:.1f} clamped to {y:.1f}")
            #logging.debug(f"  Tree at chunk ({cx},{cz}): pos=({x:.1f}, {y:.1f}, {z:.1f}), trunk={trunk_height:.1f}")

        return trees

    def _load_trees_for_chunk(self, cx, cz):
        """Load trees from database and recalculate Y based on current terrain."""
        trees = []

        if self.serializer:
            trees_data = self.serializer.load_trees(cx, cz)
            if trees_data is not None:
                for data in trees_data:
                    x = data['pos_x']
                    z = data['pos_z']

                    from camera import get_height
                    terrain_y = get_height(x, z)

                    # Ensure tree is not placed below ground
                    y = max(terrain_y, 0.2)

                    tree = Tree(
                        (x, y, z),
                        trunk_height=data.get('trunk_height', 1.2),
                        foliage_radius=data.get('foliage_radius', 0.55)
                    )
                    tree.rotation_y = data.get('rotation_y', random.uniform(0, 2 * math.pi))
                    trees.append(tree)

                if trees:
                    return trees

        return self._generate_trees_for_chunk(cx, cz)

    def _save_trees_for_chunk(self, cx, cz):
        """Save trees in a chunk to database."""
        if not self.serializer:
            return

        trees_list = self.trees.get((cx, cz), [])
        if trees_list:
            trees_data = []
            for tree in trees_list:
                data = {
                    'pos_x': float(tree.position[0]),
                    'pos_z': float(tree.position[2]),
                    'trunk_height': tree.trunk_height,
                    'trunk_radius': tree.trunk_radius,
                    'foliage_radius': tree.foliage_radius,
                    'rotation_y': tree.rotation_y
                }
                trees_data.append(data)
            self.serializer.save_trees(cx, cz, trees_data)
        else:
            self.serializer.save_trees(cx, cz, None)

    def update(self, camera_pos):
        """Update loaded chunks based on camera position."""
        cx = int(camera_pos[0] // self.phys_size)
        cz = int(camera_pos[2] // self.phys_size)

        load_radius = getattr(self.chunk_manager, 'load_radius', 3)

        # Determine needed chunks (all chunks in load radius)
        needed = set()
        for dx in range(-load_radius, load_radius + 1):
            for dz in range(-load_radius, load_radius + 1):
                needed.add((cx + dx, cz + dz))

        # Save and remove chunks that are no longer needed
        for chunk_key in list(self.loaded_chunks):
            if chunk_key not in needed:
                self._save_trees_for_chunk(*chunk_key)
                self.trees.pop(chunk_key, None)
                self.loaded_chunks.discard(chunk_key)

        # Load new chunks - ALWAYS load trees for needed chunks
        # Don't depend on chunk_manager.chunks
        for chunk_key in needed:
            if chunk_key not in self.loaded_chunks:
                trees = self._load_trees_for_chunk(*chunk_key)
                self.trees[chunk_key] = trees if trees else []
                self.loaded_chunks.add(chunk_key)

    def draw(self, view, projection, light_dir, light_intensity, camera_pos=None):
        """Draw all trees in loaded chunks."""
        if not self.trees:
            return

        # Debug
        #if camera_pos is not None:
            #logging.debug(f"Drawing trees, total chunks: {len(self.trees)}")

        glDisable(GL_DEPTH_TEST)  # Temporarily disable depth test
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        drawn_count = 0
        for trees_list in self.trees.values():
            for tree in trees_list:
                tree.draw(self.shader, view, projection, light_dir, light_intensity)
                drawn_count += 1

        #if drawn_count > 0:
            #logging.debug(f"Draw {drawn_count} trees")

        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)

    def shutdown(self):
        """Save all trees and clean up."""
        for chunk_key in list(self.loaded_chunks):
            self._save_trees_for_chunk(*chunk_key)
        self.trees.clear()
        self.loaded_chunks.clear()
