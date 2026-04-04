import numpy
from serializer import Serializer

class Player:
    def __init__(self, db_path, height=0.5, model=None):
        self.model = model
        self.serializer = Serializer(db_path)
        self.height = height
        self.position = (0.0, 0.0, 0.0)
        self.speed = 0.0
        self.life = 100
        self.life_max = 100
        self.mana = 100
        self.mana_max = 100
        self.weapon_name = "Rifle"
        self.ammo_count = 100
        self.familiar_name = ""
        self.portal_position = (0.0, 0.0, 0.0)
        self.yaw = 0.0
        self.load()

    def save(self):
        data = {
            'pos_x': self.position[0],
            'pos_y': self.position[1],
            'pos_z': self.position[2],
            'speed': self.speed,
            'life': self.life,
            'mana': self.mana,
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
            self.life = data['life']
            self.mana = data['mana']
            self.weapon_name = data['weapon_name']
            self.ammo_count = data['ammo_count']
            self.familiar_name = data['familiar_name']
            self.portal_position = (data['portal_x'], data['portal_y'], data['portal_z'])
            self.height = data.get('height', 1.5)

    def update_portal_position(self, pos):
        self.portal_position = pos
        self.save()  # optionally save immediately

    def take_damage(self, amount):
        self.life = max(0, self.life - amount)
        if self.life <= 0:
            # Optionally respawn or handle death
            pass

    # def attack(self, mob):
    #     """Player attacks a mob. Damage scales with mana."""
    #     base_damage = 25
    #     mana_factor = (self.mana / 100.0) * 0.8 + 0.2   # 20% to 100% based on mana
    #     damage = int(base_damage * mana_factor)
    #     # Optional: consume mana
    #     self.mana = max(0, self.mana_max)
    #     mob.take_damage(damage)
    #     # Trigger hit particles
    #     if hasattr(self, 'mob_manager') and self.mob_manager:
    #         self.mob_manager.add_particles(mob.position)
    #     return damage

    def set_weapon(self, weapon):
        self.model.add_model(weapon)
        self.weapon = weapon

    def set_mob_manager(self, mob_manager):
        self.mob_manager = mob_manager

    def set_model(self, model):
        self.model = model

    def draw(self, view, proj, light_dir, light_intensity):
        self.model.draw(self.position, self.yaw, view, proj, light_dir, light_intensity)
