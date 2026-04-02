import numpy
from serializer import Serializer

class Player:
    def __init__(self, db_path, height=0.5):
        self.serializer = Serializer(db_path)
        self.height = height
        self.position = (0.0, 0.0, 0.0)
        self.speed = 0.0
        self.life_percent = 100.0
        self.mana_percent = 100.0
        self.weapon_name = "Rifle"
        self.ammo_count = 100
        self.familiar_name = ""
        self.portal_position = (0.0, 0.0, 0.0)
        self.load()

    def save(self):
        data = {
            'pos_x': self.position[0],
            'pos_y': self.position[1],
            'pos_z': self.position[2],
            'speed': self.speed,
            'life_percent': self.life_percent,
            'mana_percent': self.mana_percent,
            'weapon_name': self.weapon_name,
            'ammo_count': self.ammo_count,
            'familiar_name': self.familiar_name,
            'portal_x': self.portal_position[0],
            'portal_y': self.portal_position[1],
            'portal_z': self.portal_position[2],
            'height': self.height
        }
        self.serializer.save_player(data)

    def load(self):
        data = self.serializer.load_player()
        if data:
            self.position = (data['pos_x'], data['pos_y'], data['pos_z'])
            self.speed = data['speed']
            self.life_percent = data['life_percent']
            self.mana_percent = data['mana_percent']
            self.weapon_name = data['weapon_name']
            self.ammo_count = data['ammo_count']
            self.familiar_name = data['familiar_name']
            self.portal_position = (data['portal_x'], data['portal_y'], data['portal_z'])
            self.height = data.get('height', 1.5)

    def update_portal_position(self, pos):
        self.portal_position = pos
        self.save()  # optionally save immediately
