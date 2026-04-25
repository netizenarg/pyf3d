import numpy

from player_model import PlayerModel
from shaders.shader import Shader
from shaders.remote_player_shdr import REMOTE_PLAYER_VERTEX_SHADER_SRC, REMOTE_PLAYER_FRAGMENT_SHADER_SRC

class RemotePlayer:
    def __init__(self, player_id, name, position, yaw, health, max_health):
        self.plid = player_id
        self.name = name
        self.position = numpy.array(position, dtype=float)
        self.yaw = yaw
        self.health = health
        self.max_health = max_health
        self.model = PlayerModel(Shader(REMOTE_PLAYER_VERTEX_SHADER_SRC, REMOTE_PLAYER_FRAGMENT_SHADER_SRC))

    def get_id(self):
        return self.plid

    def update(self, position, yaw, health, max_health):
        self.position = numpy.array(position, dtype=float)
        self.yaw = yaw
        self.health = health
        self.max_health = max_health

    def draw(self, view, proj, light_dir, light_intensity):
        self.model.draw(self.position, self.yaw, view, proj, light_dir, light_intensity)
