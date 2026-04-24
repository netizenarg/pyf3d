import logging
import numpy
import ctypes
import multiprocessing as mp
import queue
import math
import random
import time

from OpenGL.GL import *

from camera import get_height
from portal import Portal


def generate_portal(cx, cz, world_origin_x, world_origin_z, phys_width, phys_height, rng):
    """Return a portal dict or None. At most one portal per chunk."""
    PORTAL_PROBABILITY = 0.1  # adjust as desired
    if rng.random() >= PORTAL_PROBABILITY:
        return None
    margin = 2.0
    x = world_origin_x + rng.uniform(margin, phys_width - margin)
    z = world_origin_z + rng.uniform(margin, phys_height - margin)
    rotation_y = rng.uniform(0, 2 * math.pi)
    scale = rng.uniform(0.9, 1.1)
    y = get_height(x, z)
    name = f"{int(round(x))}_{int(round(y))}_{int(round(z))}"
    return {
        'name': name,
        'x': x, 'z': z,
        'rotation_y': rotation_y,
        'scale': scale
    }

def generate_chunk_data(cx, cz, chunk_size, spacing):
    phys_width = (chunk_size - 1) * spacing
    phys_height = (chunk_size - 1) * spacing
    world_origin_x = cx * phys_width
    world_origin_z = cz * phys_height

    # Vertex array: positions (x,y,z) and normals (nx,ny,nz)
    vertices = numpy.zeros((chunk_size * chunk_size, 6), dtype=numpy.float32)
    for z in range(chunk_size):
        for x in range(chunk_size):
            wx = world_origin_x + x * spacing
            wz = world_origin_z + z * spacing
            wy = get_height(wx, wz)
            idx = z * chunk_size + x
            vertices[idx, 0:3] = [wx, wy, wz]

    # Compute normals using central differences
    for z in range(chunk_size):
        for x in range(chunk_size):
            idx = z * chunk_size + x
            if 0 < x < chunk_size - 1 and 0 < z < chunk_size - 1:
                hx1 = vertices[(z) * chunk_size + (x + 1), 1]
                hx2 = vertices[(z) * chunk_size + (x - 1), 1]
                hz1 = vertices[(z + 1) * chunk_size + x, 1]
                hz2 = vertices[(z - 1) * chunk_size + x, 1]
                dx = hx1 - hx2
                dz = hz1 - hz2
                normal = numpy.array([-dx, 2.0 * spacing, -dz])
                norm = numpy.linalg.norm(normal)
                if norm > 0:
                    normal /= norm
                vertices[idx, 3:6] = normal
            else:
                vertices[idx, 3:6] = [0.0, 1.0, 0.0]

    # Generate indices (two triangles per grid cell)
    indices = []
    for z in range(chunk_size - 1):
        for x in range(chunk_size - 1):
            i = z * chunk_size + x
            indices.extend([i, i + 1, i + chunk_size,
                            i + 1, i + chunk_size + 1, i + chunk_size])
    indices = numpy.array(indices, dtype=numpy.uint32)

    stones, trees = [], []
    rng = random.Random((cx * 1000003) ^ (cz * 1000033))
    num_items = rng.randint(5, 10)
    for _ in range(num_items):
        x = world_origin_x + rng.uniform(1.5, phys_width - 1.5)
        z = world_origin_z + rng.uniform(1.5, phys_height - 1.5)
        y = get_height(x, z)

        # Random tree appearance properties
        trunk_height = rng.uniform(1.8, 2.2)
        foliage_radius = rng.uniform(1.0, 1.4)
        rotation_y = rng.uniform(0, 2 * math.pi)

        stones.append({
            'x': x, 'y': y, 'z': z,
            'trunk_height': trunk_height,
            'foliage_radius': foliage_radius,
            'rotation_y': rotation_y
        })

        trees.append({
            'x': x+.5, 'y': y, 'z': z+.5,
            'trunk_height': trunk_height,
            'foliage_radius': foliage_radius,
            'rotation_y': rotation_y
        })

    # Portal generation (max one)
    portal = generate_portal(cx, cz, world_origin_x, world_origin_z, phys_width, phys_height, rng)

    return (cx, cz, vertices, indices, stones, trees, portal)


class ChunkWorker(mp.Process):
    def __init__(self, request_queue, result_queue, chunk_size, spacing):
        super().__init__(daemon=True)
        self.request_queue = request_queue
        self.result_queue = result_queue
        self.chunk_size = chunk_size
        self.spacing = spacing

    def run(self):
        while True:
            try:
                req = self.request_queue.get(timeout=0.5)
                if req is None:
                    break
                cx, cz = req
                data = generate_chunk_data(cx, cz, self.chunk_size, self.spacing)
                self.result_queue.put(data)
            except queue.Empty:
                continue
            except Exception as err:
                logging.error(f"Worker error: {err}")


class ChunkGenerator:
    def __init__(self, chunk_size, spacing, num_workers=None):
        self.chunk_size = chunk_size
        self.spacing = spacing
        if num_workers is None:
            num_workers = mp.cpu_count()
        self.request_queue = mp.Queue()
        self.result_queue = mp.Queue()
        self.workers = []
        for _ in range(num_workers):
            w = ChunkWorker(self.request_queue, self.result_queue,
                            self.chunk_size, self.spacing)
            w.start()
            self.workers.append(w)

    def request_chunk(self, cx, cz):
        self.request_queue.put((cx, cz))

    def get_chunks(self):
        completed = []
        while True:
            try:
                data = self.result_queue.get_nowait()
                completed.append(data)
            except queue.Empty:
                break
        return completed

    def stop(self):
        for _ in self.workers:
            self.request_queue.put(None)
        for w in self.workers:
            w.join(timeout=1.0)


class Chunk:
    def __init__(self, cx=0, cz=0, vertices=[], indices=[], stones=None, trees=None, portal=None):
        logging.debug(f"Creating chunk ({cx},{cz}) with {len(vertices)} vertices, {len(indices)} indices")
        self.cx = cx
        self.cz = cz
        self.vertices = vertices
        self.indices = indices
        self.stones = stones if stones is not None else []
        self.trees = trees if trees is not None else []

        if portal is not None and isinstance(portal, dict):
            self.portal = Portal(
                name=portal.get('name', ''),
                base_x=portal['x'],
                base_z=portal['z'],
                rotation_y=portal.get('rotation_y', 0),
                scale=portal.get('scale', 1.0)
            )
        elif portal is not None and isinstance(portal, Portal):
            self.portal = portal
        else:
            self.portal = None

        self.vao = None
        self.vbo = None
        self.ebo = None
        self.vertex_count = len(indices)
        self._upload(vertices, indices)

    def _upload(self, vertices, indices):
        if len(vertices) == 0 or len(indices) == 0:
            logging.error(f"Chunk ({self.cx},{self.cz}) has empty vertices or indices - skipping upload")
            return
        try:
            self.vao = glGenVertexArrays(1)
            self.vbo = glGenBuffers(1)
            self.ebo = glGenBuffers(1)
            glBindVertexArray(self.vao)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
            glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
            glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 24, ctypes.c_void_p(0))
            glEnableVertexAttribArray(0)
            glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 24, ctypes.c_void_p(12))
            glEnableVertexAttribArray(1)
            glBindVertexArray(0)
            logging.debug(f"Chunk ({self.cx},{self.cz}) uploaded successfully to GPU")
        except Exception as err:
            logging.error(f"Failed to upload chunk ({self.cx},{self.cz}): {err}")

    def draw(self, shader):
        if self.vao is None:
            return
        model = numpy.eye(4, dtype=numpy.float32)
        shader.set_mat4("uModel", model)
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, self.vertex_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def delete(self):
        if self.vao:
            glDeleteVertexArrays(1, [self.vao])
            glDeleteBuffers(1, [self.vbo])
            glDeleteBuffers(1, [self.ebo])
            self.vao = None


class ChunkManager:
    def __init__(self, chunk_size=32, load_radius=3, spacing=1.0,
                 player=None, network_mode=False, network_client=None):
        self.chunk_size = chunk_size
        self.load_radius = load_radius
        self.spacing = spacing
        self.serializer = player.serializer if player else None
        self.chunks = {}
        self.pending_requests = set()
        self.generator = ChunkGenerator(chunk_size, spacing)
        self.network_mode = network_mode
        self.network_client = network_client
        if player:
            phys_size = (chunk_size - 1) * spacing
            player_cx = int(player.position[0] // phys_size)
            player_cz = int(player.position[2] // phys_size)
            self.load_chunks_around(player_cx, player_cz)
        self.first_running = True
        self.pending_request_time = {}
        self.request_timeout = 1.0

    def _generate_sync(self, cx, cz):
        cx, cz, vertices, indices, stones, trees, portal = generate_chunk_data(cx, cz, self.chunk_size, self.spacing)
        return Chunk(cx, cz, vertices, indices, stones, trees, portal)

    def _create_chunk_from_data(self, data):
        cx, cz, vertices, indices, stones, trees, portal_dict = data
        if portal_dict and self.serializer:
            x, z = portal_dict['x'], portal_dict['z']
            ground_y = get_height(x, z)
            # Portal height is 3.2 * scale
            scale = portal_dict.get('scale', 1.0)
            center_y = ground_y + (3.2 * scale) / 2.0
            self.serializer.save_portal(
                portal_dict['name'], x, center_y, z,
                portal_dict['rotation_y'],
                scale
            )
        return Chunk(cx, cz, vertices, indices, stones, trees, portal_dict)

    def load_chunks_around(self, center_cx, center_cz):
        if not self.serializer:
            return
        for dx in range(-self.load_radius, self.load_radius + 1):
            for dz in range(-self.load_radius, self.load_radius + 1):
                cx, cz = center_cx + dx, center_cz + dz
                key = (cx, cz)
                if key not in self.chunks:
                    portal_name, vertices, indices, stones, trees = self.serializer.load_chunk(cx, cz)
                    if vertices is not None:
                        portal_dict = None
                        if portal_name:
                            portal_dict = self.serializer.load_portal_by_name(portal_name)
                        self.chunks[key] = Chunk(cx, cz, vertices, indices, stones, trees, portal_dict)

    def save_all_chunks(self):
        if not self.serializer:
            return
        self.serializer.clear_chunks()
        for (cx, cz), chunk in self.chunks.items():
            portal_name = chunk.portal.name if chunk.portal else None
            self.serializer.save_chunk(portal_name, cx, cz,
                chunk.vertices, chunk.indices, chunk.stones, chunk.trees)

    def update_old(self, camera_pos):
        phys_size = (self.chunk_size - 1) * self.spacing
        cx = int(camera_pos[0] // phys_size)
        cz = int(camera_pos[2] // phys_size)
        needed = set()
        for dx in range(-self.load_radius, self.load_radius + 1):
            for dz in range(-self.load_radius, self.load_radius + 1):
                needed.add((cx + dx, cz + dz))
        for key in list(self.chunks.keys()):
            if key not in needed:
                self.chunks.pop(key).delete()
        self.pending_requests = {req for req in self.pending_requests if req in needed}
        for key in list(self.pending_request_time.keys()):
            if key not in self.pending_requests:
                self.pending_request_time.pop(key, None)
        for key in needed:
            if key not in self.chunks and key not in self.pending_requests:
                if self.network_mode and self.network_client and self.network_client.is_connected():
                    self.pending_requests.add(key)
                    self.pending_request_time[key] = time.time()
                    self.network_client.request_chunk(*key)
                elif self.first_running and self.serializer:
                    self.first_running = not self.first_running
                    portal_name, vertices, indices, stones, trees = self.serializer.load_chunk(*key)
                    if vertices is not None:
                        self.chunks[key] = Chunk(*key, vertices, indices, stones, trees, portal_name)
                        continue
                elif self.generator:
                    self.pending_requests.add(key)
                    self.generator.request_chunk(*key)
                else:
                    self.chunks[key] = self._generate_sync(*key)
        if self.network_client:
            for data in self.network_client.get_chunks():
                if data is None:
                    continue
                if len(data) == 5:
                    cx, cz, vertices, indices, trees = data
                    stones = []
                    portal = None
                elif len(data) == 6:
                    cx, cz, vertices, indices, stones, trees = data
                    portal = None
                elif len(data) == 7:
                    cx, cz, vertices, indices, stones, trees, portal = data
                else:
                    logging.error(f"Unexpected data length from network: {len(data)}")
                    continue
                key = (cx, cz)
                if vertices is not None and len(vertices) > 0:
                    chunk = Chunk(cx, cz, vertices, indices, stones, trees, portal)
                    if key in needed:
                        self.chunks[key] = chunk
                        logging.debug(f"Added chunk {key} to active chunks")
                    else:
                        logging.warning(f"Chunk {key} arrived but no longer needed, discarding")
                    if self.serializer:
                        portal_name = portal.get('name') if portal else None
                        self.serializer.save_chunk(portal_name, cx, cz, vertices, indices, stones, trees)
                    logging.debug(f"Received chunk {key} from network with {len(vertices)} vertices")
                else:
                    logging.warning(f"Network returned empty data for chunk {key}")
                self.pending_requests.discard(key)
                self.pending_request_time.pop(key, None)
        now = time.time()
        for key in list(self.pending_requests):
            if key in self.pending_request_time and now - self.pending_request_time[key] > self.request_timeout:
                logging.warning(f"Chunk {key} request timed out after {self.request_timeout}s, falling back to local generation")
                self.pending_requests.discard(key)
                self.pending_request_time.pop(key, None)
                if self.generator:
                    self.generator.request_chunk(*key)
                else:
                    self.chunks[key] = self._generate_sync(*key)
        if self.generator:
            for data in self.generator.get_chunks():
                cx, cz, vertices, indices, stones, trees, portal = data
                key = (cx, cz)
                if key in needed:
                    self.chunks[key] = Chunk(cx, cz, vertices, indices, stones, trees, portal)
                self.pending_requests.discard(key)
                self.pending_request_time.pop(key, None)

    def draw(self, shader):
        for chunk in self.chunks.values():
            chunk.draw(shader)

    def shutdown(self):
        if self.generator:
            self.generator.stop()
        for chunk in self.chunks.values():
            chunk.delete()
        self.chunks.clear()

    def update(self, camera_pos):
        if self.network_mode and self.network_client:
            phys_size = 15.0
        else:
            phys_size = (self.chunk_size - 1) * self.spacing
        cx = int(camera_pos[0] // phys_size)
        cz = int(camera_pos[2] // phys_size)
        needed = set()
        for dx in range(-self.load_radius, self.load_radius + 1):
            for dz in range(-self.load_radius, self.load_radius + 1):
                needed.add((cx + dx, cz + dz))
        for key in list(self.chunks.keys()):
            if key not in needed:
                self.chunks.pop(key).delete()
        self.pending_requests = {req for req in self.pending_requests if req in needed}
        for key in list(self.pending_request_time.keys()):
            if key not in self.pending_requests:
                self.pending_request_time.pop(key, None)
        for key in needed:
            if key not in self.chunks and key not in self.pending_requests:
                if self.network_mode and self.network_client and self.network_client.is_connected():
                    self.pending_requests.add(key)
                    self.pending_request_time[key] = time.time()
                    self.network_client.request_chunk(*key)
                elif self.first_running and self.serializer:
                    self.first_running = not self.first_running
                    portal_name, vertices, indices, stones, trees = self.serializer.load_chunk(*key)
                    if vertices is not None:
                        self.chunks[key] = Chunk(*key, vertices, indices, stones, trees, portal_name)
                        continue
                elif self.generator:
                    self.pending_requests.add(key)
                    self.generator.request_chunk(*key)
                else:
                    self.chunks[key] = self._generate_sync(*key)
        if self.network_client:
            for data in self.network_client.get_chunks():
                if data is None:
                    continue
                if len(data) == 5:
                    cx, cz, vertices, indices, trees = data
                    stones = []
                    portal = None
                elif len(data) == 6:
                    cx, cz, vertices, indices, stones, trees = data
                    portal = None
                elif len(data) == 7:
                    cx, cz, vertices, indices, stones, trees, portal = data
                else:
                    logging.error(f"Unexpected data length from network: {len(data)}")
                    continue
                key = (cx, cz)
                if vertices is not None and len(vertices) > 0:
                    if isinstance(vertices, numpy.ndarray):
                        vertices = vertices.astype(numpy.float32)
                    else:
                        vertices = numpy.array(vertices, dtype=numpy.float32)
                    if isinstance(indices, numpy.ndarray):
                        indices = indices.astype(numpy.uint32)
                    else:
                        indices = numpy.array(indices, dtype=numpy.uint32)
                    chunk = Chunk(cx, cz, vertices, indices, stones, trees, portal)
                    if key in needed:
                        self.chunks[key] = chunk
                        logging.debug(f"Added chunk {key} to active chunks")
                    else:
                        logging.warning(f"Chunk {key} arrived but no longer needed, discarding")
                    if self.serializer:
                        portal_name = portal.get('name') if portal else None
                        save_stones = []
                        for stone in stones:
                            if isinstance(stone, dict):
                                save_stone = {}
                                for k, v in stone.items():
                                    if isinstance(v, (numpy.floating, numpy.integer)):
                                        save_stone[k] = v.item()
                                    elif isinstance(v, numpy.ndarray):
                                        save_stone[k] = v.tolist()
                                    else:
                                        save_stone[k] = v
                                save_stones.append(save_stone)
                            else:
                                save_stones.append(stone)
                        save_trees = []
                        for tree in trees:
                            if isinstance(tree, dict):
                                save_tree = {}
                                for k, v in tree.items():
                                    if isinstance(v, (numpy.floating, numpy.integer)):
                                        save_tree[k] = v.item()
                                    elif isinstance(v, numpy.ndarray):
                                        save_tree[k] = v.tolist()
                                    else:
                                        save_tree[k] = v
                                save_trees.append(save_tree)
                            else:
                                save_trees.append(tree)
                        self.serializer.save_chunk(portal_name, cx, cz, vertices, indices, save_stones, save_trees)
                    logging.debug(f"Received chunk {key} from network with {len(vertices)} vertices")
                else:
                    logging.warning(f"Network returned empty data for chunk {key}")
                self.pending_requests.discard(key)
                self.pending_request_time.pop(key, None)
        now = time.time()
        for key in list(self.pending_requests):
            if key in self.pending_request_time and now - self.pending_request_time[key] > self.request_timeout:
                logging.warning(f"Chunk {key} request timed out after {self.request_timeout}s, falling back to local generation")
                self.pending_requests.discard(key)
                self.pending_request_time.pop(key, None)
                if self.generator:
                    self.generator.request_chunk(*key)
                else:
                    self.chunks[key] = self._generate_sync(*key)
        if self.generator:
            for data in self.generator.get_chunks():
                cx, cz, vertices, indices, stones, trees, portal = data
                key = (cx, cz)
                if key in needed:
                    self.chunks[key] = Chunk(cx, cz, vertices, indices, stones, trees, portal)
                self.pending_requests.discard(key)
                self.pending_request_time.pop(key, None)
