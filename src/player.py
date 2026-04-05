import numpy
from serializer import Serializer

class Player:
    def __init__(self, db_path, height=0.5, model=None):
        self.model = model
        self.serializer = Serializer(db_path)
        self.height = height
        self.position = (0.0, 0.0, 0.0)
        self.portal_position = (0.0, 0.0, 0.0)
        self.yaw = 0.0
        self.speed = 0.0
        self.life = 100
        self.life_max = 100
        self.mana = 100
        self.mana_max = 100
        self.weapon_name = "Rifle"
        self.ammo_count = 100
        self.familiar_name = ""
        self.level = 0
        self.killed_mobs = 0
        self.load()
        self.change_rotation_handler = None

    def save(self):
        data = {
            'pos_x': self.position[0],
            'pos_y': self.position[1],
            'pos_z': self.position[2],
            'portal_x': self.portal_position[0],
            'portal_y': self.portal_position[1],
            'portal_z': self.portal_position[2],
            'height': self.height,
            'speed': self.speed,
            'level': self.level,
            'life': self.life,
            'mana': self.mana,
            'weapon_name': self.weapon_name,
            'ammo_count': self.ammo_count,
            'killed_mobs': self.killed_mobs,
            'familiar_name': self.familiar_name
        }
        self.serializer.save_player(data)

    def load(self):
        data = self.serializer.load_player()
        if data:
            self.position = (data.get('pos_x',0.0), data.get('pos_y',0.0), data.get('pos_z',0.0))
            self.speed = data.get('speed', 10.0)
            self.level = data.get('level', 0)
            self.life = data.get('life', 100)
            self.mana = data.get('mana', 100)
            self.weapon_name = data.get('weapon_name', '')
            self.ammo_count = data.get('ammo_count', 0)
            self.familiar_name = data.get('familiar_name', '')
            self.portal_position = (data.get('portal_x',0.0), data.get('portal_y',0.0), data.get('portal_z',0.0))
            self.height = data.get('height', 1.5)
            self.killed_mobs = data.get('killed_mobs', 0)

    def update_portal_position(self, pos):
        self.portal_position = pos
        self.save()

    def take_damage(self, amount):
        self.life = max(0, self.life - amount)
        if self.life <= 0:
            # Optionally respawn or handle death
            pass

    def add_kill(self):
        self.killed_mobs += 1
        if self.killed_mobs % 10 == 0:
            self.level += 1
            self.serializer.update('player', ('level', 'killed_mobs'), (self.level, self.killed_mobs))
            if self.level > 1:# start from this level camera.rotate_only_horizontal = False
                self.change_rotation_handler(False)

    def set_weapon(self, weapon):
        self.model.add_model(weapon)
        self.weapon = weapon

    def set_mob_manager(self, mob_manager):
        self.mob_manager = mob_manager

    def set_model(self, model):
        self.model = model

    def draw(self, view, proj, light_dir, light_intensity):
        self.model.draw(self.position, self.yaw, view, proj, light_dir, light_intensity)
