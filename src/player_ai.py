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
        self.weapon = weapon          # current weapon (fallback)
        self.enabled = enabled
        self.speed_multiplier = 0.5   # slow down AI movement

        # Random movement state
        self.move_timer = 0.0
        self.random_yaw_change = 0.0

        # Combat state
        self.attack_cooldown_left = 0.0
        self.attack_cooldown_right = 0.0
        self.strafe_timer = 0.0
        self.strafe_direction = 0.0   # -1 left, +1 right

        # Collection range
        self.collect_range = 2.5

        # Select best weapons from bag
        self._select_best_weapons()

    def _select_best_weapons(self):
        """Choose two most powerful weapons from bag (by rank)."""
        weapons = [w for w in self.player.bag.weapons.values() if w.name != "rifle"]  # exclude default
        weapons.sort(key=lambda w: w.rank, reverse=True)
        self.left_weapon = weapons[0] if len(weapons) > 0 else self.weapon
        self.right_weapon = weapons[1] if len(weapons) > 1 else self.weapon
        # Ensure we have two distinct weapons if possible
        if self.left_weapon == self.right_weapon and len(weapons) > 1:
            self.right_weapon = weapons[1]
        logging.debug(f"AI weapons: left={self.left_weapon.name}, right={self.right_weapon.name}")

    def update(self, dt, current_time):
        if not self.enabled:
            return

        # Update timers
        self.attack_cooldown_left = max(0.0, self.attack_cooldown_left - dt)
        self.attack_cooldown_right = max(0.0, self.attack_cooldown_right - dt)
        self.strafe_timer = max(0.0, self.strafe_timer - dt)
        self.move_timer -= dt

        # 1. Find closest interesting target
        closest_mob = self._find_closest_mob()
        closest_health = self._find_closest_health()
        closest_loot = self._find_closest_loot()

        # 2. Prioritize: mobs > health > loot > random roam
        if closest_mob and self._distance_to(closest_mob.position) < 20.0:
            self._combat_behavior(closest_mob, dt, current_time)
        elif closest_health and self._distance_to(closest_health.get_world_position()) < self.collect_range * 2:
            self._move_toward(closest_health.get_world_position())
        elif closest_loot and self._distance_to(closest_loot.position) < self.collect_range * 2:
            self._move_toward(closest_loot.position)
        else:
            self._random_wander(dt)

        # 3. Automatic collection
        self._auto_collect()

    def _distance_to(self, pos):
        dx = pos[0] - self.player.position[0]
        dz = pos[2] - self.player.position[2]
        return math.hypot(dx, dz)

    def _find_closest_mob(self):
        closest = None
        best_dist = 50.0
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

    def _move_toward(self, target_pos):
        """Set player yaw to face target and request forward movement."""
        dx = target_pos[0] - self.player.position[0]
        dz = target_pos[2] - self.player.position[2]
        if dx == 0 and dz == 0:
            return
        target_yaw = math.atan2(dx, dz)
        self._set_yaw_toward(target_yaw)
        # Apply speed multiplier
        self.player.movement['w'] = True
        self.player.movement['a'] = False
        self.player.movement['d'] = False
        self.player.movement['s'] = False

    def _set_yaw_toward(self, target_yaw):
        diff = target_yaw - self.player.yaw
        while diff > math.pi:
            diff -= 2*math.pi
        while diff < -math.pi:
            diff += 2*math.pi
        self.player.yaw += diff * 0.2   # smooth rotation
        self.player.yaw = math.atan2(math.sin(self.player.yaw), math.cos(self.player.yaw))

    def _combat_behavior(self, mob, dt, current_time):
        dist = self._distance_to(mob.position)

        # Always face the mob
        self._move_toward(mob.position)   # sets yaw and forward movement

        # Strafe when close
        if dist < 3.0:
            if self.strafe_timer <= 0.0:
                self.strafe_direction = random.choice([-1.0, 1.0])
                self.strafe_timer = random.uniform(0.8, 1.5)
            # Override forward movement with strafe
            forward = numpy.array([math.sin(self.player.yaw), 0.0, math.cos(self.player.yaw)])
            right = numpy.array([forward[2], 0.0, -forward[0]])
            strafe_vec = right * self.strafe_direction
            self.player.movement['w'] = False
            self.player.movement['s'] = False
            self.player.movement['a'] = strafe_vec[0] < 0
            self.player.movement['d'] = strafe_vec[0] > 0
        else:
            # Normal approach – already set by _move_toward
            pass

        # Shooting logic (both weapons)
        if dist < 15.0:
            # Check if mob is in front (angle < 45°)
            to_mob = numpy.array([mob.position[0] - self.player.position[0], 0.0,
                                  mob.position[2] - self.player.position[2]])
            to_mob = to_mob / (numpy.linalg.norm(to_mob) + 1e-6)
            forward = numpy.array([math.sin(self.player.yaw), 0.0, math.cos(self.player.yaw)])
            dot = numpy.dot(to_mob, forward)
            if dot > 0.7:   # facing mob
                # Shoot with left weapon if ready
                if self.attack_cooldown_left <= 0.0:
                    ammo = self._shoot_at(mob, self.left_weapon, current_time)
                    if ammo:
                        self.attack_cooldown_left = self.left_weapon.cooldown
                        logging.debug("AI shooting left at mob")
                # Shoot with right weapon if ready
                if self.attack_cooldown_right <= 0.0:
                    ammo = self._shoot_at(mob, self.right_weapon, current_time)
                    if ammo:
                        self.attack_cooldown_right = self.right_weapon.cooldown
                        logging.debug("AI shooting right at mob")

    def _shoot_at(self, mob, weapon, current_time):
        """Fire a weapon at the mob's current position."""
        # Compute direction from player to mob
        direction = numpy.array([mob.position[0] - self.player.position[0],
                                 0.0,   # ignore vertical difference
                                 mob.position[2] - self.player.position[2]])
        if numpy.linalg.norm(direction) < 0.01:
            return None
        direction = direction / numpy.linalg.norm(direction)
        weapon_pos = self.player.position
        # Determine which hand to use based on weapon reference
        if weapon == self.left_weapon:
            hand = 'left'
        else:
            hand = 'right'
        # Temporarily set player's weapon to this one
        original_left = self.player.weapon_left
        original_right = self.player.weapon_right
        if hand == 'left':
            self.player.weapon_left = weapon.name
        else:
            self.player.weapon_right = weapon.name
        ammo = self.player.shoot(hand, weapon_pos, direction, current_time)
        # Restore original weapons
        self.player.weapon_left = original_left
        self.player.weapon_right = original_right
        return ammo

    def _random_wander(self, dt):
        if self.move_timer <= 0.0:
            angle_change = random.uniform(-30, 30)
            self.random_yaw_change = math.radians(angle_change)
            self.move_timer = random.uniform(2.0, 5.0)
        self.player.yaw += self.random_yaw_change * dt
        self.player.movement['w'] = True
        self.player.movement['a'] = False
        self.player.movement['d'] = False
        self.player.movement['s'] = False

    def _auto_collect(self):
        # No need to force collection; the managers handle it when player moves into range
        pass

    def toggle(self):
        self.enabled = not self.enabled
        if not self.enabled:
            for k in ['w','a','s','d']:
                self.player.movement[k] = False
        else:
            self._select_best_weapons()   # refresh weapons when enabled
        return self.enabled