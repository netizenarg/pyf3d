import numpy
from OpenGL.GL import *

class Loot:
    def __init__(self, position):
        self.position = numpy.array(position, dtype=float)
        self.active = True
        self.pickup_timer = 0.5

    def update(self, dt):
        if self.pickup_timer > 0:
            self.pickup_timer -= dt

    def on_pickup(self, player):
        raise NotImplementedError

    def draw(self, view, proj):
        raise NotImplementedError

    def get_model_matrix(self):
        mat = numpy.eye(4, dtype=numpy.float32)
        mat[0,3], mat[1,3], mat[2,3] = self.position
        return mat


class LootManager:
    _instance = None

    def __init__(self):
        self.loot_items = []

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def add_loot(self, loot):
        self.loot_items.append(loot)

    def update(self, player, dt):
        for loot in self.loot_items[:]:
            loot.update(dt)
            if loot.pickup_timer > 0:
                continue
            # Only horizontal distance matters (ignore y)
            dx = loot.position[0] - player.position[0]
            dz = loot.position[2] - player.position[2]
            if dx*dx + dz*dz < 1.0:   # 1.0 unit horizontal radius
                if loot.on_pickup(player):
                    self.loot_items.remove(loot)

    def draw(self, view, proj):
        for loot in self.loot_items:
            loot.draw(view, proj)
