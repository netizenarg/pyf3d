import random
import math
import numpy
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader
import ctypes
from camera import get_height

# ------------------------------ Sky Shader (gradient background) ------------------------------
SKY_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec2 aPos;
out vec2 vTexCoord;
void main() {
    gl_Position = vec4(aPos, 0.0, 1.0);
    vTexCoord = aPos * 0.5 + 0.5;
}
"""

SKY_FRAGMENT_SHADER = """
#version 330 core
in vec2 vTexCoord;
uniform float uDayFactor;
uniform vec2 uScreenSize;
out vec4 FragColor;

vec3 nightZenith = vec3(0.05, 0.05, 0.15);
vec3 nightHorizon = vec3(0.1, 0.1, 0.2);
vec3 dayZenith = vec3(0.2, 0.5, 0.9);
vec3 dayHorizon = vec3(1.0, 0.8, 0.5);

void main() {
    float t = vTexCoord.y;
    vec3 zenith = mix(nightZenith, dayZenith, uDayFactor);
    vec3 horizon = mix(nightHorizon, dayHorizon, uDayFactor);
    vec3 color = mix(horizon, zenith, t);
    FragColor = vec4(color, 1.0);
}
"""

# ------------------------------ Celestial Shader (3D Sphere) ------------------------------
CELESTIAL_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
uniform vec3 uColor;
out vec3 vColor;

void main() {
    gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
    // Simple shading: light from top‑left
    vec3 lightDir = normalize(vec3(1.0, 2.0, 1.0));
    vec3 normal = normalize(aNormal);
    float diff = max(dot(normal, lightDir), 0.2);
    vColor = uColor * diff;
}
"""

CELESTIAL_FRAGMENT_SHADER = """
#version 330 core
in vec3 vColor;
out vec4 FragColor;

void main() {
    FragColor = vec4(vColor, 1.0);
}
"""

# ------------------------------ Cloud Sphere Shader (with alpha) ------------------------------
CLOUD_SPHERE_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
out float vAlpha;

void main() {
    gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
    // Simple alpha based on some factor (constant for now)
    vAlpha = 0.7;
}
"""

CLOUD_SPHERE_FRAGMENT_SHADER = """
#version 330 core
in float vAlpha;
out vec4 FragColor;

void main() {
    FragColor = vec4(0.95, 0.95, 0.95, vAlpha);
}
"""

# ------------------------------ Snow Shader (moving points) ------------------------------
SNOW_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec3 aPos;
uniform mat4 uView;
uniform mat4 uProjection;
uniform float uTime;

out float vBrightness;

void main() {
    vec4 worldPos = vec4(aPos, 1.0);
    gl_Position = uProjection * uView * worldPos;
    float twinkle = 0.5 + 0.5 * sin(uTime * 2.0 + aPos.x * 10.0 + aPos.y * 8.0 + aPos.z * 12.0);
    vBrightness = 0.6 + 0.4 * twinkle;
    gl_PointSize = 8.0 + twinkle * 3.0;
}
"""

SNOW_FRAGMENT_SHADER = """
#version 330 core
in float vBrightness;
out vec4 FragColor;

void main() {
    vec2 coord = gl_PointCoord;
    float dist = length(coord - vec2(0.5));
    if (dist > 0.5) discard;
    float alpha = (1.0 - dist * 2.0) * 0.8;
    FragColor = vec4(1.0, 1.0, 1.0, alpha * vBrightness);
}
"""

class CloudBlob:
    """A single cloud blob represented as a sphere."""
    def __init__(self, offset, size):
        self.offset = offset   # relative to cloud center
        self.size = size

class Cloud:
    def __init__(self, position, speed=0.1):
        self.position = position
        self.speed = speed
        # Random direction in XZ plane
        self.direction = numpy.array([random.uniform(-1, 1), 0, random.uniform(-1, 1)], dtype=numpy.float32)
        norm = numpy.linalg.norm(self.direction)
        if norm > 0:
            self.direction /= norm
        else:
            self.direction = numpy.array([1.0, 0.0, 0.0])

        # Generate blobs (spheres)
        num_blobs = random.randint(5, 12)
        self.blobs = []
        for _ in range(num_blobs):
            # Random offset in a disc of radius 4.0
            angle = random.uniform(0, 2 * math.pi)
            radius = random.uniform(0, 4.0)
            off_x = math.cos(angle) * radius
            off_z = math.sin(angle) * radius
            off_y = random.uniform(-1.0, 1.0)
            size = random.uniform(1.0, 2.5)
            self.blobs.append(CloudBlob(numpy.array([off_x, off_y, off_z]), size))

    def update(self, dt):
        self.position += self.direction * self.speed * dt

class Sky:
    def __init__(self, chunk_manager, cloud_count_per_chunk=5, snow_count=500):
        self.chunk_manager = chunk_manager
        self.cloud_count_per_chunk = cloud_count_per_chunk
        self.clouds = {}
        self.snow_count = snow_count
        self.time_of_day = 0.0
        self.day_duration = 60.0
        self.init_shaders()
        self._setup_sky_vao()
        self._setup_sphere_vao()     # for sun, moon, clouds
        self._setup_snow_vao()

    def init_shaders(self):
        self.sky_shader = compileProgram(
            compileShader(SKY_VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(SKY_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
        )
        self.celestial_shader = compileProgram(
            compileShader(CELESTIAL_VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(CELESTIAL_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
        )
        self.cloud_sphere_shader = compileProgram(
            compileShader(CLOUD_SPHERE_VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(CLOUD_SPHERE_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
        )
        self.snow_shader = compileProgram(
            compileShader(SNOW_VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(SNOW_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
        )

    def update(self, dt):
        self.time_of_day += dt / self.day_duration
        if self.time_of_day >= 1.0:
            self.time_of_day -= 1.0
        self.update_clouds(dt)

    def update_clouds(self, dt):
        loaded_chunks = self.chunk_manager.chunks.keys()
        for key in loaded_chunks:
            if key not in self.clouds:
                self.generate_clouds_for_chunk(key)
            else:
                for cloud in self.clouds[key]:
                    cloud.update(dt)
        for key in list(self.clouds.keys()):
            if key not in loaded_chunks:
                del self.clouds[key]

    def generate_clouds_for_chunk(self, key):
        cx, cz = key
        phys_size = (self.chunk_manager.chunk_size - 1) * self.chunk_manager.spacing
        world_min_x = cx * phys_size
        world_min_z = cz * phys_size
        world_max_x = world_min_x + phys_size
        world_max_z = world_min_z + phys_size
        clouds = []
        for _ in range(self.cloud_count_per_chunk):
            x = random.uniform(world_min_x, world_max_x)
            z = random.uniform(world_min_z, world_max_z)
            y = get_height(x, z) + random.uniform(8, 15)
            speed = random.uniform(0.5, 2.0)
            clouds.append(Cloud(numpy.array([x, y, z], dtype=numpy.float32), speed))
        self.clouds[key] = clouds

    def draw_background(self, view, proj, camera_pos, current_time, screen_width, screen_height):
        day_factor = max(0.0, min(1.0, 1.0 - 2.0 * abs(0.5 - self.time_of_day)))
        glDisable(GL_DEPTH_TEST)
        glUseProgram(self.sky_shader)
        glUniform1f(glGetUniformLocation(self.sky_shader, "uDayFactor"), day_factor)
        glUniform2f(glGetUniformLocation(self.sky_shader, "uScreenSize"), screen_width, screen_height)
        glBindVertexArray(self._sky_vao)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
        glEnable(GL_DEPTH_TEST)

    def draw_celestial_sphere(self, view, proj, world_pos, color, size):
        """Draw a 3D sphere at world_pos with given color and size (radius)."""
        glUseProgram(self.celestial_shader)
        glUniformMatrix4fv(glGetUniformLocation(self.celestial_shader, "uView"), 1, GL_TRUE, view)
        glUniformMatrix4fv(glGetUniformLocation(self.celestial_shader, "uProjection"), 1, GL_TRUE, proj)
        glUniform3fv(glGetUniformLocation(self.celestial_shader, "uColor"), 1, color)

        model = numpy.eye(4, dtype=numpy.float32)
        model[0, 3] = world_pos[0]
        model[1, 3] = world_pos[1]
        model[2, 3] = world_pos[2]
        model[0, 0] = size
        model[1, 1] = size
        model[2, 2] = size
        glUniformMatrix4fv(glGetUniformLocation(self.celestial_shader, "uModel"), 1, GL_TRUE, model)

        glBindVertexArray(self._sphere_vao)
        glDrawElements(GL_TRIANGLES, self._sphere_index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def draw_clouds(self, view, proj, camera_pos):
        if not self.clouds:
            return
        glUseProgram(self.cloud_sphere_shader)
        glUniformMatrix4fv(glGetUniformLocation(self.cloud_sphere_shader, "uView"), 1, GL_TRUE, view)
        glUniformMatrix4fv(glGetUniformLocation(self.cloud_sphere_shader, "uProjection"), 1, GL_TRUE, proj)

        glBindVertexArray(self._sphere_vao)
        for clouds_list in self.clouds.values():
            for cloud in clouds_list:
                for blob in cloud.blobs:
                    model = numpy.eye(4, dtype=numpy.float32)
                    model[0, 3] = cloud.position[0] + blob.offset[0]
                    model[1, 3] = cloud.position[1] + blob.offset[1]
                    model[2, 3] = cloud.position[2] + blob.offset[2]
                    model[0, 0] = blob.size
                    model[1, 1] = blob.size
                    model[2, 2] = blob.size
                    glUniformMatrix4fv(glGetUniformLocation(self.cloud_sphere_shader, "uModel"), 1, GL_TRUE, model)
                    glDrawElements(GL_TRIANGLES, self._sphere_index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def draw_snow(self, view, proj, camera_pos, current_time):
        # Generate fresh snow positions around the camera
        radius = 150.0
        positions = []
        for _ in range(self.snow_count):
            theta = random.uniform(0, 2 * math.pi)
            phi = math.acos(2 * random.uniform(0, 1) - 1)
            x = radius * math.cos(theta) * math.sin(phi)
            y = radius * math.sin(theta) * math.sin(phi)
            z = radius * math.cos(phi)
            pos = camera_pos + numpy.array([x, y, z], dtype=numpy.float32)
            positions.extend(pos)

        positions_np = numpy.array(positions, dtype=numpy.float32)
        glBindBuffer(GL_ARRAY_BUFFER, self._snow_vbo)
        glBufferData(GL_ARRAY_BUFFER, positions_np.nbytes, positions_np, GL_DYNAMIC_DRAW)

        glUseProgram(self.snow_shader)
        glUniformMatrix4fv(glGetUniformLocation(self.snow_shader, "uView"), 1, GL_TRUE, view)
        glUniformMatrix4fv(glGetUniformLocation(self.snow_shader, "uProjection"), 1, GL_TRUE, proj)
        glUniform1f(glGetUniformLocation(self.snow_shader, "uTime"), current_time)

        glEnable(GL_PROGRAM_POINT_SIZE)
        glBindVertexArray(self._snow_vao)
        glDrawArrays(GL_POINTS, 0, self.snow_count)
        glBindVertexArray(0)
        glDisable(GL_PROGRAM_POINT_SIZE)

    def draw_all(self, view, proj, camera_pos, current_time):
        day_factor = max(0.0, min(1.0, 1.0 - 2.0 * abs(0.5 - self.time_of_day)))
        is_day = day_factor > 0.5

        # Draw Sun / Moon (3D spheres) – fixed world positions
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)

        distance = 200.0

        # Sun angle: 0 at dawn (0.25), π/2 at noon (0.5), π at dusk (0.75)
        sun_angle = (self.time_of_day - 0.25) * 2 * math.pi
        sun_x = distance * math.cos(sun_angle)
        sun_y = distance * math.sin(sun_angle)
        sun_z = 0.0
        sun_world_pos = numpy.array([sun_x, sun_y, sun_z], dtype=numpy.float32)

        if sun_y > 0:
            self.draw_celestial_sphere(view, proj, sun_world_pos,
                                       numpy.array([1.0, 0.4, 0.4], dtype=numpy.float32), 20.0)

        moon_angle = sun_angle + math.pi
        moon_x = distance * math.cos(moon_angle)
        moon_y = distance * math.sin(moon_angle)
        moon_z = 0.0
        moon_world_pos = numpy.array([moon_x, moon_y, moon_z], dtype=numpy.float32)

        if moon_y > 0:
            self.draw_celestial_sphere(view, proj, moon_world_pos,
                                       numpy.array([0.5, 0.5, 0.5], dtype=numpy.float32), 15.0)

        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)

        # Clouds – drawn with alpha blending
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self.draw_clouds(view, proj, camera_pos)
        glDisable(GL_BLEND)

        # Snow – only at night, depth test disabled
        if not is_day:
            glDisable(GL_DEPTH_TEST)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE)
            self.draw_snow(view, proj, camera_pos, current_time)
            glDisable(GL_BLEND)
            glEnable(GL_DEPTH_TEST)

    # ------------------------------ VAO Setup ------------------------------
    def _setup_sky_vao(self):
        vertices = numpy.array([-1.0, -1.0, 1.0, -1.0, 1.0, 1.0, -1.0, 1.0], dtype=numpy.float32)
        indices = numpy.array([0,1,2, 0,2,3], dtype=numpy.uint32)
        self._sky_vao = glGenVertexArrays(1)
        self._sky_vbo = glGenBuffers(1)
        self._sky_ebo = glGenBuffers(1)
        glBindVertexArray(self._sky_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._sky_vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._sky_ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 8, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)

    def _setup_sphere_vao(self):
        # Generate a UV sphere (latitude/longitude) with radius 1.
        slices = 32   # number of longitudinal segments
        stacks = 16   # number of latitudinal segments
        vertices = []
        normals = []
        indices = []

        for i in range(stacks + 1):
            theta = i * math.pi / stacks
            sin_theta = math.sin(theta)
            cos_theta = math.cos(theta)
            for j in range(slices + 1):
                phi = j * 2 * math.pi / slices
                sin_phi = math.sin(phi)
                cos_phi = math.cos(phi)
                x = sin_theta * cos_phi
                y = cos_theta
                z = sin_theta * sin_phi
                vertices.extend([x, y, z])
                normals.extend([x, y, z])

        for i in range(stacks):
            for j in range(slices):
                first = i * (slices + 1) + j
                second = first + slices + 1
                indices.extend([first, second, first + 1,
                                second, second + 1, first + 1])

        vertices = numpy.array(vertices, dtype=numpy.float32)
        normals = numpy.array(normals, dtype=numpy.float32)
        indices = numpy.array(indices, dtype=numpy.uint32)

        self._sphere_vao = glGenVertexArrays(1)
        self._sphere_vbo = glGenBuffers(1)
        self._sphere_nbo = glGenBuffers(1)
        self._sphere_ebo = glGenBuffers(1)

        glBindVertexArray(self._sphere_vao)

        glBindBuffer(GL_ARRAY_BUFFER, self._sphere_vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)

        glBindBuffer(GL_ARRAY_BUFFER, self._sphere_nbo)
        glBufferData(GL_ARRAY_BUFFER, normals.nbytes, normals, GL_STATIC_DRAW)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._sphere_ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)

        glBindVertexArray(0)
        self._sphere_index_count = len(indices)

    def _setup_snow_vao(self):
        positions = numpy.zeros(self.snow_count * 3, dtype=numpy.float32)
        self._snow_vao = glGenVertexArrays(1)
        self._snow_vbo = glGenBuffers(1)
        glBindVertexArray(self._snow_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._snow_vbo)
        glBufferData(GL_ARRAY_BUFFER, positions.nbytes, positions, GL_DYNAMIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)
