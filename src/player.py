import json
import numpy
import logging

from serializer import Serializer
from weapon import BaseWeapon, Weapon
from bazuka import Bazuka

class Bag:
    def __init__(self, capacity_weapons=10):
        self.capacity_weapons = capacity_weapons
        self.portal_keys = {}
        self.default_weapon = BaseWeapon()
        self.weapons = {self.default_weapon.name: self.default_weapon}

    def to_dict(self):
        weapons_list = []
        for weapon in self.weapons.values():
            weapons_list.append(weapon.to_dict())
        return {
            'portal_keys': self.portal_keys,
            'weapons': weapons_list,
        }

    @classmethod
    def from_dict(cls, data):
        bag = cls()
        bag.portal_keys = data.get('portal_keys', {})
        weapons_list = data.get('weapons', [])
        bag.weapons = {}
        for wdata in weapons_list:
            name = wdata.get('name')
            if name == 'rifle':
                bag.weapons[name] = BaseWeapon.from_dict(wdata)
            elif name == 'gun':
                bag.weapons[name] = Weapon.from_dict(wdata)
            elif name == 'bazuka':
                bag.weapons[name] = Bazuka.from_dict(wdata)
        return bag

    def add_weapon(self, weapon):
        if len(self.weapons) == self.capacity_weapons:
            return False, f'Full bag weapons capacity = {self.capacity_weapons}'
        if weapon.name in self.weapons:
            return False, f'Weapon {weapon.name} already in bag'
        self.weapons[weapon.name] = weapon
        return True, f'Weapon {weapon.name} success append to bag'

    def get_weapon_by_rank(self, rank):
        for weapon in self.weapons.values():
            if weapon.rank == rank:
                return weapon
        return None


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
        self.bag = Bag()
        self.weapon_left = ''
        self.weapon_right = self.bag.default_weapon
        self.ammo_left = 0        # ammo for left hand weapon
        self.ammo_right = -1      # -1 = infinite
        self.familiar_name = ""
        self.level = 0
        self.killed_mobs = 0
        self.load()
        self.change_rotation_handler = None

    @property
    def lweapon(self):
        return self.bag.weapons.get(self.weapon_left, self.bag.default_weapon)

    @property
    def rweapon(self):
        return self.bag.weapons.get(self.weapon_right, self.bag.default_weapon)

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
            'weapon_left': self.weapon_left,
            'weapon_right': self.weapon_right,
            'ammo_left': self.ammo_left,
            'ammo_right': self.ammo_right,
            'killed_mobs': self.killed_mobs,
            'familiar_name': self.familiar_name,
            'bag': json.dumps(self.bag.to_dict())
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
            self.weapon_left = data.get('weapon_left', self.bag.default_weapon)
            self.weapon_right = data.get('weapon_right', None)
            self.ammo_left = data.get('ammo_left', 0)
            self.ammo_right = data.get('ammo_right', -1)
            self.killed_mobs = data.get('killed_mobs', 0)
            self.familiar_name = data.get('familiar_name', '')
            self.portal_position = (data.get('portal_x',0.0), data.get('portal_y',0.0), data.get('portal_z',0.0))
            self.height = data.get('height', 1.5)
            bag_json = data.get('bag', '{}')
            self.bag = Bag.from_dict(json.loads(bag_json))

    def set_weapon(self, weapon, hand='right'):
        self.model.change_model_weapon(weapon, hand)
        if hand == 'right':
            self.weapon_right = weapon.name
        else:
            self.weapon_left = weapon.name

    def pickup_weapon(self, weapon):
        result, msg = self.bag.add_weapon(weapon)
        if not result:
            logging.debug(msg)
            return False
        if self.lweapon.rank < weapon.rank:
            self.set_weapon(weapon, 'left')
        elif self.rweapon.rank < weapon.rank:
            self.set_weapon(weapon, 'right')
        return True

    def shoot(self, hand='right', position=0, direction=0, current_time=0):
        weapon = None
        if hand == 'right':
            weapon = self.bag.weapons.get(self.weapon_right, self.bag.default_weapon)
        else:
            weapon = self.bag.weapons.get(self.weapon_left, self.bag.default_weapon)
        if weapon is None:
            return None
        #logging.debug(f'Weapon {hand} {weapon}')
        ammo = weapon.shoot(position, direction, current_time)
        if ammo:
            if hand == 'right' and self.ammo_right > 0:
                self.ammo_right -= 1
            elif hand == 'left' and self.ammo_left > 0:
                self.ammo_left -= 1
        return ammo

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

    def set_mob_manager(self, mob_manager):
        self.mob_manager = mob_manager

    def set_model(self, model):
        self.model = model

    def draw(self, view, proj, light_dir, light_intensity):
        self.model.draw(self.position, self.yaw, view, proj, light_dir, light_intensity)
