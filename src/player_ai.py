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

        # No LOCKING state – only ATTACKING, COLLECTING, WANDER
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
        self.seek_range = 30.0
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

    def _handle_mob_target(self, mob, dt, current_time):
        dist = self._distance_to(mob.position)
        self.current_target = mob
        self.target_type = 'mob'
        self.state = "ATTACKING"

        # Continuously aim at the mob (smooth rotation)
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
            forward = numpy.array([math.sin(math.radians(self.camera.yaw)), 0.0,
                                   math.cos(math.radians(self.camera.yaw))])
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

        # Shooting – wide cone (45°) and within 20 units
        if dist < 20.0 and self._is_target_in_front(mob.position, 45.0):
            if self.attack_cooldown_left <= 0.0:
                ammo = self._shoot_at(mob, self.left_weapon, current_time)
                if ammo:
                    self.attack_cooldown_left = self.left_weapon.cooldown
            if self.attack_cooldown_right <= 0.0:
                ammo = self._shoot_at(mob, self.right_weapon, current_time)
                if ammo:
                    self.attack_cooldown_right = self.right_weapon.cooldown

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
        self.state = "WANDER"
        if self.move_timer <= 0.0:
            angle_change = random.uniform(-30, 30)
            self.random_yaw_change = angle_change
            self.move_timer = random.uniform(2.0, 5.0)
        self.camera.yaw += self.random_yaw_change * dt
        self.camera.yaw %= 360
        self.camera.update_vectors()
        self.player.movement['w'] = True
        self.player.movement['a'] = False
        self.player.movement['d'] = False
        self.player.movement['s'] = False

    def _aim_at_target(self, target_pos, dt):
        """Smoothly rotate camera toward target (no return value, always rotates)."""
        dx = target_pos[0] - self.player.position[0]
        dy = target_pos[1] - (self.player.position[1] + self.player.height)
        dz = target_pos[2] - self.player.position[2]
        dist_h = math.hypot(dx, dz)
        if dist_h < 0.01:
            return

        target_yaw = math.degrees(math.atan2(dx, dz))
        target_pitch = math.degrees(math.atan2(dy, dist_h))
        target_pitch = max(-89, min(89, target_pitch))

        yaw_diff = target_yaw - self.camera.yaw
        while yaw_diff > 180:
            yaw_diff -= 360
        while yaw_diff < -180:
            yaw_diff += 360
        pitch_diff = target_pitch - self.camera.pitch

        # Rotation speed (120°/s for fast tracking)
        max_rot = 120.0 * dt
        yaw_step = max(-max_rot, min(max_rot, yaw_diff))
        pitch_step = max(-max_rot, min(max_rot, pitch_diff))

        self.camera.yaw += yaw_step
        self.camera.pitch += pitch_step
        self.camera.yaw %= 360
        self.camera.pitch = max(-89, min(89, self.camera.pitch))
        self.camera.update_vectors()
        if self.camera.mode == 0:
            self.player.yaw = math.radians(self.camera.yaw)

    def _is_target_in_front(self, target_pos, angle_threshold_deg):
        to_target = numpy.array([target_pos[0] - self.player.position[0],
                                  0.0,
                                  target_pos[2] - self.player.position[2]])
        if numpy.linalg.norm(to_target) == 0:
            return False
        to_target = to_target / numpy.linalg.norm(to_target)
        forward = numpy.array([math.sin(math.radians(self.camera.yaw)), 0.0,
                               math.cos(math.radians(self.camera.yaw))])
        dot = numpy.dot(to_target, forward)
        required_dot = math.cos(math.radians(angle_threshold_deg))
        return dot >= required_dot

    def _shoot_at(self, target, weapon, current_time):
        # Direction: from camera to target's center (for accuracy)
        target_center = (target.position[0], target.position[1] + 0.5, target.position[2])
        direction = numpy.array(target_center) - self.camera.position
        if numpy.linalg.norm(direction) > 0:
            direction = direction / numpy.linalg.norm(direction)
        else:
            direction = self.camera.front

        # Determine hand and get weapon offset
        hand = 'left' if weapon == self.left_weapon else 'right'
        offset = weapon.offset  # each weapon has (x, y, z) offset relative to player
        # Rotate offset by player's yaw (same as manual third‑person)
        c = math.cos(self.player.yaw)
        s = math.sin(self.player.yaw)
        world_offset = numpy.array([
            offset[0] * c - offset[2] * s,
            offset[1],
            offset[0] * s + offset[2] * c
        ])
        weapon_pos = self.player.position + world_offset

        # Temporarily equip weapon, shoot, then restore
        original_left = self.player.weapon_left
        original_right = self.player.weapon_right
        if hand == 'left':
            self.player.weapon_left = weapon.name
        else:
            self.player.weapon_right = weapon.name
        ammo = self.player.shoot(hand, weapon_pos, direction, current_time)
        self.player.weapon_left = original_left
        self.player.weapon_right = original_right

        if ammo and self.ammo_list is not None:
            self.ammo_list.append(ammo)
        return ammo

    # ---------- Distance and search helpers (unchanged) ----------
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
