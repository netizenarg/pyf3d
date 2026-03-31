import random
import math
import numpy as np
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

# ------------------------------ Star Shader (twinkling points) ------------------------------
STAR_VERTEX_SHADER = """
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
    gl_PointSize = 8.0 + twinkle * 3.0;   // larger point size
}
"""

STAR_FRAGMENT_SHADER = """
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

# ------------------------------ Cloud Shader (simple MVP) ------------------------------
CLOUD_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec3 aPos;
uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;

void main() {
    gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
}
"""

CLOUD_FRAGMENT_SHADER = """
#version 330 core
out vec4 FragColor;

void main() {
    FragColor = vec4(0.95, 0.95, 0.95, 0.7);
}
"""

class Cloud:
    def __init__(self, position, speed=0.5):
        self.position = position
        self.speed = speed
        self.direction = np.array([random.uniform(-1, 1), 0, random.uniform(-1, 1)], dtype=np.float32)
        norm = np.linalg.norm(self.direction)
        if norm > 0:
            self.direction /= norm
        else:
            self.direction = np.array([1.0, 0.0, 0.0])

    def update(self, dt):
        self.position += self.direction * self.speed * dt

class Sky:
    def __init__(self, chunk_manager, cloud_count_per_chunk=5, star_count=500):
        self.chunk_manager = chunk_manager
        self.cloud_count_per_chunk = cloud_count_per_chunk
        self.clouds = {}
        self.star_count = star_count
        self.time_of_day = 0.0
        self.day_duration = 60.0
        self.init_shaders()
        self._setup_sky_vao()
        self._setup_cloud_vao()
        self._setup_star_vao()

    def init_shaders(self):
        self.sky_shader = compileProgram(
            compileShader(SKY_VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(SKY_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
        )
        self.star_shader = compileProgram(
            compileShader(STAR_VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(STAR_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
        )
        self.cloud_shader = compileProgram(
            compileShader(CLOUD_VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(CLOUD_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
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
            speed = random.uniform(5.0, 12.0)
            clouds.append(Cloud(np.array([x, y, z], dtype=np.float32), speed))
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

    def draw_clouds(self, view, proj, camera_pos):
        if not self.clouds:
            return
        glUseProgram(self.cloud_shader)
        glUniformMatrix4fv(glGetUniformLocation(self.cloud_shader, "uView"), 1, GL_TRUE, view)
        glUniformMatrix4fv(glGetUniformLocation(self.cloud_shader, "uProjection"), 1, GL_TRUE, proj)

        glBindVertexArray(self._cloud_vao)
        for clouds_list in self.clouds.values():
            for cloud in clouds_list:
                model = np.eye(4, dtype=np.float32)
                model[0, 3] = cloud.position[0]
                model[1, 3] = cloud.position[1]
                model[2, 3] = cloud.position[2]
                size = 15.0
                model[0, 0] = size
                model[1, 1] = size
                model[2, 2] = size
                glUniformMatrix4fv(glGetUniformLocation(self.cloud_shader, "uModel"), 1, GL_TRUE, model)
                glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def draw_stars(self, view, proj, camera_pos, current_time):
        # Generate fresh star positions around the camera
        radius = 150.0
        positions = []
        for _ in range(self.star_count):
            theta = random.uniform(0, 2 * math.pi)
            phi = math.acos(2 * random.uniform(0, 1) - 1)
            x = radius * math.cos(theta) * math.sin(phi)
            y = radius * math.sin(theta) * math.sin(phi)
            z = radius * math.cos(phi)
            pos = camera_pos + np.array([x, y, z], dtype=np.float32)
            positions.extend(pos)

        positions_np = np.array(positions, dtype=np.float32)
        glBindBuffer(GL_ARRAY_BUFFER, self._star_vbo)
        glBufferData(GL_ARRAY_BUFFER, positions_np.nbytes, positions_np, GL_DYNAMIC_DRAW)

        glUseProgram(self.star_shader)
        glUniformMatrix4fv(glGetUniformLocation(self.star_shader, "uView"), 1, GL_TRUE, view)
        glUniformMatrix4fv(glGetUniformLocation(self.star_shader, "uProjection"), 1, GL_TRUE, proj)
        glUniform1f(glGetUniformLocation(self.star_shader, "uTime"), current_time)

        glEnable(GL_PROGRAM_POINT_SIZE)
        glBindVertexArray(self._star_vao)
        glDrawArrays(GL_POINTS, 0, self.star_count)
        glBindVertexArray(0)
        glDisable(GL_PROGRAM_POINT_SIZE)

    def draw_clouds_and_stars(self, view, proj, camera_pos, current_time):
        day_factor = max(0.0, min(1.0, 1.0 - 2.0 * abs(0.5 - self.time_of_day)))
        is_day = day_factor > 0.5

        # Clouds – always drawn, with depth test on
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self.draw_clouds(view, proj, camera_pos)
        glDisable(GL_BLEND)

        # Stars – only at night, with depth test disabled
        if not is_day:
            glDisable(GL_DEPTH_TEST)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE)
            self.draw_stars(view, proj, camera_pos, current_time)
            glDisable(GL_BLEND)
            glEnable(GL_DEPTH_TEST)

    # ------------------------------ VAO Setup ------------------------------
    def _setup_sky_vao(self):
        vertices = np.array([-1.0, -1.0, 1.0, -1.0, 1.0, 1.0, -1.0, 1.0], dtype=np.float32)
        indices = np.array([0,1,2, 0,2,3], dtype=np.uint32)
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

    def _setup_cloud_vao(self):
        vertices = np.array([-0.5, -0.5, 0.0, 0.5, -0.5, 0.0, 0.5, 0.5, 0.0, -0.5, 0.5, 0.0], dtype=np.float32)
        indices = np.array([0,1,2, 0,2,3], dtype=np.uint32)
        self._cloud_vao = glGenVertexArrays(1)
        self._cloud_vbo = glGenBuffers(1)
        self._cloud_ebo = glGenBuffers(1)
        glBindVertexArray(self._cloud_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._cloud_vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._cloud_ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)

    def _setup_star_vao(self):
        positions = np.zeros(self.star_count * 3, dtype=np.float32)
        self._star_vao = glGenVertexArrays(1)
        self._star_vbo = glGenBuffers(1)
        glBindVertexArray(self._star_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._star_vbo)
        glBufferData(GL_ARRAY_BUFFER, positions.nbytes, positions, GL_DYNAMIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)
