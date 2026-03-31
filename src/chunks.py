import numpy
import ctypes
import multiprocessing as mp
import queue
from OpenGL.GL import *

from camera import get_height

def generate_chunk_data(cx, cz, chunk_size, spacing):
    """
    Generate vertices and indices for a chunk.
    This function runs in a worker process.
    Returns a tuple (cx, cz, vertices, indices).
    """
    # Physical size of one chunk in world units
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

    return (cx, cz, vertices, indices)


class ChunkWorker(mp.Process):
    """A worker process that generates chunks on demand."""
    def __init__(self, request_queue, result_queue, chunk_size, spacing):
        super().__init__(daemon=True)
        self.request_queue = request_queue
        self.result_queue = result_queue
        self.chunk_size = chunk_size
        self.spacing = spacing

    def run(self):
        while True:
            try:
                # Block until a request arrives (timeout to allow checking stop event)
                req = self.request_queue.get(timeout=0.5)
                if req is None:       # sentinel to stop
                    break
                cx, cz = req
                data = generate_chunk_data(cx, cz, self.chunk_size, self.spacing)
                self.result_queue.put(data)
            except queue.Empty:
                continue
            except Exception as e:
                # Log error and continue
                print(f"Worker error: {e}")


class ChunkGenerator:
    """Manages a pool of worker processes for chunk generation."""
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
        """Queue a chunk generation request."""
        self.request_queue.put((cx, cz))

    def get_completed(self):
        """Return a list of completed chunk data (non‑blocking)."""
        completed = []
        while True:
            try:
                data = self.result_queue.get_nowait()
                completed.append(data)
            except queue.Empty:
                break
        return completed

    def stop(self):
        """Stop all workers."""
        for _ in self.workers:
            self.request_queue.put(None)   # sentinel for each worker
        for w in self.workers:
            w.join(timeout=1.0)


class Chunk:
    """Chunk that lives on the GPU. Must be created on the main thread."""
    def __init__(self, cx, cz, vertices, indices):
        self.cx = cx
        self.cz = cz
        self.vao = None
        self.vbo = None
        self.ebo = None
        self.vertex_count = len(indices)
        self._upload(vertices, indices)

    def _upload(self, vertices, indices):
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

    def draw(self, shader):
        if self.vao is None:
            return
        model = numpy.eye(4, dtype=numpy.float32)
        shader.set_mat4("uModel", model)
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, self.vertex_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def delete(self):
        """Delete OpenGL buffers (must be called on main thread)."""
        if self.vao:
            glDeleteVertexArrays(1, [self.vao])
            glDeleteBuffers(1, [self.vbo])
            glDeleteBuffers(1, [self.ebo])
            self.vao = None


class ChunkManager:
    def __init__(self, chunk_size=32, load_radius=3, spacing=1.0, use_multiprocessing=True):
        self.chunk_size = chunk_size
        self.load_radius = load_radius
        self.spacing = spacing
        self.chunks = {}               # (cx, cz) -> Chunk
        self.pending_requests = set()  # chunks that have been requested but not yet built
        if use_multiprocessing:
            self.generator = ChunkGenerator(chunk_size, spacing)
        else:
            self.generator = None  # fallback to sync generation if needed

    def _generate_sync(self, cx, cz):
        """Fallback synchronous generation (no multiprocessing)."""
        data = generate_chunk_data(cx, cz, self.chunk_size, self.spacing)
        return Chunk(*data)

    def update(self, camera_pos):
        # Physical size of one chunk in world units
        phys_size = (self.chunk_size - 1) * self.spacing
        cx = int(camera_pos[0] // phys_size)
        cz = int(camera_pos[2] // phys_size)

        needed = set()
        for dx in range(-self.load_radius, self.load_radius + 1):
            for dz in range(-self.load_radius, self.load_radius + 1):
                needed.add((cx + dx, cz + dz))

        # Remove chunks that are no longer needed
        for key in list(self.chunks.keys()):
            if key not in needed:
                self.chunks.pop(key).delete()

        # Remove pending requests that are no longer needed
        self.pending_requests = {req for req in self.pending_requests if req in needed}

        # Request missing chunks
        for key in needed:
            if key not in self.chunks and key not in self.pending_requests:
                self.pending_requests.add(key)
                if self.generator:
                    self.generator.request_chunk(*key)
                else:
                    # Synchronous fallback (may cause stutter)
                    self.chunks[key] = self._generate_sync(*key)
                    self.pending_requests.discard(key)

        # Process completed chunks from generator
        if self.generator:
            for data in self.generator.get_completed():
                cx, cz, vertices, indices = data
                key = (cx, cz)
                if key in self.pending_requests and key in needed:
                    self.pending_requests.discard(key)
                    self.chunks[key] = Chunk(cx, cz, vertices, indices)
                else:
                    # Discard data for chunk that is no longer needed
                    self.pending_requests.discard(key)

    def draw(self, shader):
        for chunk in self.chunks.values():
            chunk.draw(shader)

    def shutdown(self):
        """Stop background workers and clean up."""
        if self.generator:
            self.generator.stop()
        for chunk in self.chunks.values():
            chunk.delete()
        self.chunks.clear()
