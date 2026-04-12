import math
import random
import numpy
from logger import logging


class PlayerAI:
    def __init__(self, player, camera, mob_manager, health_manager, loot_manager, weapon, enabled=False):
        self.player = player
        self.camera = camera
        self.mob_manager = mob_manager
        self.health_manager = health_manager
        self.loot_manager = loot_manager
        self.weapon = weapon
        self.enabled = enabled

        self.state = "IDLE"
        self.current_target = None
        self.target_type = None

        self.move_timer = 0.0
        self.random_yaw_change = 0.0
        self.attack_cooldown_left = 0.0
        self.attack_cooldown_right = 0.0
        self.strafe_timer = 0.0
        self.strafe_direction = 0.0
        self.collect_range = 2.5

        self.engage_range = 100.0
        self.standoff_min = 6.0
        self.standoff_max = 12.0

        self._select_best_weapons()
        self.ammo_list = None

    def _select_best_weapons(self):
        weapons = [w for w in self.player.bag.weapons.values() if w.name != "rifle"]
        weapons.sort(key=lambda w: w.rank, reverse=True)
        self.left_weapon = weapons[0] if weapons else self.weapon
        self.right_weapon = weapons[1] if len(weapons) > 1 else self.weapon
        if self.left_weapon == self.right_weapon and len(weapons) > 1:
            self.right_weapon = weapons[1]
        logging.debug(f"AI weapons: left={self.left_weapon.name}, right={self.right_weapon.name}")

    def set_enabled(self, enabled):
        self.enabled = enabled
        if not enabled:
            for k in ['w','a','s','d']:
                self.player.movement[k] = False
            self.state = "IDLE"
            self.current_target = None
        else:
            self._select_best_weapons()
            logging.info("AI enabled")

    def set_ammo_list(self, ammo_list):
        self.ammo_list = ammo_list

    def update(self, dt, current_time):
        if not self.enabled:
            return

        self.attack_cooldown_left = max(0.0, self.attack_cooldown_left - dt)
        self.attack_cooldown_right = max(0.0, self.attack_cooldown_right - dt)
        self.strafe_timer = max(0.0, self.strafe_timer - dt)
        self.move_timer -= dt

        closest_mob = self._find_closest_mob()
        if closest_mob and self._distance_to(closest_mob.position) < self.engage_range:
            self._handle_mob_target(closest_mob, dt, current_time)
        else:
            health = self._find_closest_health()
            if health and self._distance_to(health.get_world_position()) < self.collect_range * 2:
                self._handle_item_target(health, 'health', dt)
            else:
                loot = self._find_closest_loot()
                if loot and self._distance_to(loot.position) < self.collect_range * 2:
                    self._handle_item_target(loot, 'loot', dt)
                else:
                    self._handle_no_target(dt)
        #logging.debug(f'{(round(self.player.position[0],1), round(self.player.position[1],1), round(self.player.position[2],1))}')
        #logging.debug(f'{round(self.player.yaw,1)}; {round(self.camera.yaw,1)}; {self.camera.mode}; {self.state}')

    def _handle_mob_target(self, mob, dt, current_time):
        dist = self._distance_to(mob.position)
        self.current_target = mob
        self.target_type = 'mob'

        # Rotate player yaw toward the mob
        self._aim_at_target(mob.position, dt)

        # Movement logic
        if dist > self.standoff_max:
            self.player.movement['w'] = True
            self.player.movement['a'] = False
            self.player.movement['d'] = False
            self.player.movement['s'] = False
        elif dist < self.standoff_min:
            if self.strafe_timer <= 0.0:
                self.strafe_direction = random.choice([-1.0, 1.0])
                self.strafe_timer = random.uniform(0.8, 1.5)
            # Strafe relative to player's forward (feels natural in both modes)
            forward = numpy.array([math.sin(self.player.yaw), 0.0, math.cos(self.player.yaw)])
            right = numpy.array([forward[2], 0.0, -forward[0]])
            strafe_vec = right * self.strafe_direction
            self.player.movement['w'] = False
            self.player.movement['s'] = False
            self.player.movement['a'] = strafe_vec[0] < 0
            self.player.movement['d'] = strafe_vec[0] > 0
        else:
            self.player.movement['w'] = False
            self.player.movement['s'] = False
            self.player.movement['a'] = False
            self.player.movement['d'] = False

        # Shooting – if mob is roughly in front of player (45° cone) and within 20 units
        if dist < 20.0 and self._is_target_in_front(mob.position, 45.0):
            if self.attack_cooldown_left <= 0.0:
                ammo = self._shoot_at(mob, self.left_weapon, current_time)
                if ammo:
                    self.attack_cooldown_left = self.left_weapon.cooldown
                    self.state = "ATTACKING"
            if self.attack_cooldown_right <= 0.0:
                ammo = self._shoot_at(mob, self.right_weapon, current_time)
                if ammo:
                    self.attack_cooldown_right = self.right_weapon.cooldown
                    self.state = "ATTACKING"

    def _handle_item_target(self, item, item_type, dt):
        self.current_target = item
        self.target_type = item_type
        self.state = "COLLECTING"
        self.player.movement['w'] = True
        self.player.movement['a'] = False
        self.player.movement['d'] = False
        self.player.movement['s'] = False

    def _handle_no_target(self, dt):
        self.current_target = None
        if self.move_timer <= 0.0:
            angle_change = random.uniform(-30, 30)
            self.random_yaw_change = angle_change
            self.move_timer = random.uniform(2.0, 5.0)
        if self.state == "ROTATE":
            self.state = "WANDER"
        else:#"ROTATE"
            self.state = "ROTATE"
            self.player.yaw += math.radians(self.random_yaw_change * dt)
            self.player.yaw = math.atan2(math.sin(self.player.yaw), math.cos(self.player.yaw))
            # In first-person, sync camera yaw; in third-person, do nothing (camera follows)
            if self.camera.mode == 0:
                self.camera.yaw = math.degrees(self.player.yaw)
                self.camera.update_vectors()
        self.player.movement['w'] = True
        self.player.movement['a'] = False
        self.player.movement['d'] = False
        self.player.movement['s'] = False

    def _aim_at_target(self, target_pos, dt):
        """Rotate player yaw to face target."""
        if self.state == "ROTATE" or self.state == "COLLECTING":
            return
        dx = target_pos[0] - self.player.position[0]
        dz = target_pos[2] - self.player.position[2]
        dist_h = math.hypot(dx, dz)
        if dist_h < 0.01:
            return
        target_yaw = math.atan2(dx, dz)
        diff = target_yaw - self.player.yaw
        while diff > math.pi:
            diff -= 2*math.pi
        while diff < -math.pi:
            diff += 2*math.pi
        max_rot = math.radians(120.0 * dt)   # 120°/s
        if abs(diff) > max_rot:
            diff = max_rot if diff > 0 else -max_rot
        self.player.yaw += diff
        self.player.yaw = math.atan2(math.sin(self.player.yaw), math.cos(self.player.yaw))
        if self.camera.mode == 0:
            self.camera.yaw = math.degrees(self.player.yaw)
            self.camera.update_vectors()

    def _is_target_in_front(self, target_pos, angle_threshold_deg):
        """Check if target is within a cone in front of the player."""
        player_forward = numpy.array([math.sin(self.player.yaw), 0.0, math.cos(self.player.yaw)])
        to_target = numpy.array([target_pos[0] - self.player.position[0],
                                  0.0,
                                  target_pos[2] - self.player.position[2]])
        if numpy.linalg.norm(to_target) == 0:
            return False
        to_target = to_target / numpy.linalg.norm(to_target)
        dot = numpy.dot(to_target, player_forward)
        required_dot = math.cos(math.radians(angle_threshold_deg))
        return dot >= required_dot

    def _shoot_at(self, target, weapon, current_time):
        # Direction from weapon muzzle to target centre
        target_center = (target.position[0], target.position[1] + 0.5, target.position[2])
        hand = 'left' if weapon == self.left_weapon else 'right'
        offset = weapon.offset
        c = math.cos(self.player.yaw)
        s = math.sin(self.player.yaw)
        world_offset = numpy.array([
            offset[0] * c - offset[2] * s,
            offset[1],
            offset[0] * s + offset[2] * c
        ])
        muzzle_pos = self.player.position + world_offset
        direction = numpy.array(target_center) - muzzle_pos
        if numpy.linalg.norm(direction) > 0:
            direction = direction / numpy.linalg.norm(direction)
        else:
            # Fallback to player forward
            direction = numpy.array([math.sin(self.player.yaw), 0.0, math.cos(self.player.yaw)])

        # Temporarily equip weapon, shoot, restore
        original_left = self.player.weapon_left
        original_right = self.player.weapon_right
        if hand == 'left':
            self.player.weapon_left = weapon.name
        else:
            self.player.weapon_right = weapon.name
        ammo = self.player.shoot(hand, muzzle_pos, direction, current_time)
        self.player.weapon_left = original_left
        self.player.weapon_right = original_right

        if ammo and self.ammo_list is not None:
            self.ammo_list.append(ammo)
        return ammo

    def _distance_to(self, pos):
        dx = pos[0] - self.player.position[0]
        dz = pos[2] - self.player.position[2]
        return math.hypot(dx, dz)

    def _find_closest_mob(self):
        closest = None
        best_dist = self.engage_range
        for mobs in self.mob_manager.active_mobs.values():
            for mob in mobs:
                if not mob.is_alive():
                    continue
                dist = self._distance_to(mob.position)
                if dist < best_dist:
                    best_dist = dist
                    closest = mob
        return closest

    def _find_closest_health(self):
        closest = None
        best_dist = 50.0
        for item in self.health_manager.active_items.values():
            if item.collected:
                continue
            dist = self._distance_to(item.get_world_position())
            if dist < best_dist:
                best_dist = dist
                closest = item
        return closest

    def _find_closest_loot(self):
        closest = None
        best_dist = 50.0
        for item in self.loot_manager.loot_items:
            if hasattr(item, 'collected') and item.collected:
                continue
            if hasattr(item, 'active') and not item.active:
                continue
            dist = self._distance_to(item.position)
            if dist < best_dist:
                best_dist = dist
                closest = item
        return closest

    def toggle(self):
        self.enabled = not self.enabled
        if not self.enabled:
            for k in ['w','a','s','d']:
                self.player.movement[k] = False
            self.state = "IDLE"
            self.current_target = None
        else:
            self._select_best_weapons()
        return self.enabled
