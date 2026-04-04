import numpy
import ctypes
from OpenGL.GL import *

from shaders.shader import Shader


class PlayerModel:
    def __init__(self, shader: Shader):
        self.shader = shader
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.ebo = glGenBuffers(1)
        self._build_cube_buffers()
        self._setup_buffers()

    def _build_cube_buffers(self):
        vertices = numpy.array([
            # front face
            -0.5, -0.5,  0.5,  0, 0, 1,
             0.5, -0.5,  0.5,  0, 0, 1,
             0.5,  0.5,  0.5,  0, 0, 1,
            -0.5,  0.5,  0.5,  0, 0, 1,
            # back face
            -0.5, -0.5, -0.5,  0, 0, -1,
             0.5, -0.5, -0.5,  0, 0, -1,
             0.5,  0.5, -0.5,  0, 0, -1,
            -0.5,  0.5, -0.5,  0, 0, -1,
            # left face
            -0.5, -0.5, -0.5, -1, 0, 0,
            -0.5, -0.5,  0.5, -1, 0, 0,
            -0.5,  0.5,  0.5, -1, 0, 0,
            -0.5,  0.5, -0.5, -1, 0, 0,
            # right face
             0.5, -0.5, -0.5,  1, 0, 0,
             0.5, -0.5,  0.5,  1, 0, 0,
             0.5,  0.5,  0.5,  1, 0, 0,
             0.5,  0.5, -0.5,  1, 0, 0,
            # top face
            -0.5,  0.5, -0.5,  0, 1, 0,
             0.5,  0.5, -0.5,  0, 1, 0,
             0.5,  0.5,  0.5,  0, 1, 0,
            -0.5,  0.5,  0.5,  0, 1, 0,
            # bottom face
            -0.5, -0.5, -0.5,  0, -1, 0,
             0.5, -0.5, -0.5,  0, -1, 0,
             0.5, -0.5,  0.5,  0, -1, 0,
            -0.5, -0.5,  0.5,  0, -1, 0,
        ], dtype=numpy.float32)

        indices = numpy.array([
            0,1,2, 0,2,3,
            4,5,6, 4,6,7,
            8,9,10, 8,10,11,
            12,13,14, 12,14,15,
            16,17,18, 16,18,19,
            20,21,22, 20,22,23
        ], dtype=numpy.uint32)

        self.vertex_data = vertices
        self.index_data = indices
        self.index_count = len(indices)
        self.appended_models = []

    def _setup_buffers(self):
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, self.vertex_data.nbytes, self.vertex_data, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self.index_data.nbytes, self.index_data, GL_STATIC_DRAW)

        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6 * 4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * 4, ctypes.c_void_p(3 * 4))
        glEnableVertexAttribArray(1)

        glBindVertexArray(0)

    def _draw_scaled_cube(self, scale, offset, parent_model):
        local_model = numpy.eye(4, dtype=numpy.float32)
        local_model[0, 0] = scale[0]
        local_model[1, 1] = scale[1]
        local_model[2, 2] = scale[2]
        local_model[0, 3] = offset[0]
        local_model[1, 3] = offset[1]
        local_model[2, 3] = offset[2]
        full_model = parent_model @ local_model
        self.shader.set_mat4("uModel", full_model)
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, self.index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def add_model(self, model):
        self.appended_models.append(model)

    def get_model_matrix(self, position, rotation_yaw):
        c = numpy.cos(rotation_yaw)
        s = numpy.sin(rotation_yaw)
        rot_y = numpy.array([
            [c, 0, s, 0],
            [0, 1, 0, 0],
            [-s, 0, c, 0],
            [0, 0, 0, 1]
        ], dtype=numpy.float32)
        trans = numpy.eye(4, dtype=numpy.float32)
        trans[0, 3] = position[0]
        trans[1, 3] = position[1]
        trans[2, 3] = position[2]
        return trans @ rot_y

    def draw(self, position, rotation_yaw, view, projection, light_dir, light_intensity):
        model_matrix = self.get_model_matrix(position, rotation_yaw)
        glUseProgram(self.shader.program)
        self.shader.set_mat4("uView", view)
        self.shader.set_mat4("uProjection", projection)
        self.shader.set_vec3("uLightDir", light_dir)
        self.shader.set_float("uLightIntensity", light_intensity)
        self.shader.set_mat4("uModel", model_matrix)
        # Draw body parts (same as before, but using parent matrix)
        center_y = 0.8
        scale_body = numpy.array([0.6, 0.8, 0.4], dtype=numpy.float32)
        self._draw_scaled_cube(scale_body, numpy.array([0.0, center_y, 0.0]), model_matrix)
        scale_head = numpy.array([0.5, 0.5, 0.5], dtype=numpy.float32)
        self._draw_scaled_cube(scale_head, numpy.array([0.0, center_y+0.8, 0.0]), model_matrix)
        scale_arm = numpy.array([0.3, 0.6, 0.3], dtype=numpy.float32)
        self._draw_scaled_cube(scale_arm, numpy.array([-0.5, center_y+0.4, 0.0]), model_matrix)
        self._draw_scaled_cube(scale_arm, numpy.array([ 0.5, center_y+0.4, 0.0]), model_matrix)
        scale_leg = numpy.array([0.3, 0.6, 0.3], dtype=numpy.float32)
        self._draw_scaled_cube(scale_leg, numpy.array([-0.3, center_y-0.5, 0.0]), model_matrix)
        self._draw_scaled_cube(scale_leg, numpy.array([ 0.3, center_y-0.5, 0.0]), model_matrix)
        head_center_y = center_y + 0.8
        eye_scale = numpy.array([0.12, 0.12, 0.08], dtype=numpy.float32)
        self._draw_scaled_cube(eye_scale, numpy.array([-0.2, head_center_y+0.1, 0.28]), model_matrix)
        self._draw_scaled_cube(eye_scale, numpy.array([ 0.2, head_center_y+0.1, 0.28]), model_matrix)
        nose_scale = numpy.array([0.1, 0.1, 0.1], dtype=numpy.float32)
        self._draw_scaled_cube(nose_scale, numpy.array([0.0, head_center_y-0.05, 0.32]), model_matrix)
        mouth_scale = numpy.array([0.2, 0.06, 0.06], dtype=numpy.float32)
        self._draw_scaled_cube(mouth_scale, numpy.array([0.0, head_center_y-0.15, 0.29]), model_matrix)
        for amodel in self.appended_models:
            amodel.draw(view, projection, model_matrix, amodel.offset)
