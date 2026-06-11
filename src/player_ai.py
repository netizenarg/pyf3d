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

        self.state = "MOVING"
        self.attack_cooldown_left = 0.0
        self.attack_cooldown_right = 0.0
        self.engage_range = 100.0
        self.shoot_range = 30.0
        self.backoff_range = 6.0
        self.collect_range = 2.5
        self.ammo_list = None
        self._debug_timer = 0.0
        self._wander_timer = 0.0
        self._wander_yaw = 0.0
        self._last_shot_time = 0.0
        self._last_mob_dist = 0.0
        self._last_dist_change = 0.0
        self._backing_off = False
        self._backoff_start_time = 0.0
        self._chase_until = -1.0

        self.left_weapon = self.weapon
        self.right_weapon = self.weapon
        self._select_best_weapons()

    def _select_best_weapons(self):
        weapons = [w for w in self.player.bag.weapons.values() if w.name != "rifle"]
        weapons.sort(key=lambda w: w.rank, reverse=True)
        self.left_weapon = weapons[0] if weapons else self.weapon
        self.right_weapon = weapons[1] if len(weapons) > 1 else self.weapon
        if self.left_weapon == self.right_weapon and len(weapons) > 1:
            self.right_weapon = weapons[1]

    def set_enabled(self, enabled):
        self.enabled = enabled
        if not enabled:
            for k in ['w','a','s','d']:
                self.player.movement[k] = False
            self.state = "IDLE"
        else:
            self._select_best_weapons()

    def set_ammo_list(self, ammo_list):
        self.ammo_list = ammo_list

    def toggle(self):
        self.set_enabled(not self.enabled)
        return self.enabled

    def _direction_to_target(self, target_pos):
        dx = target_pos[0] - self.player.position[0]
        dz = target_pos[2] - self.player.position[2]
        if abs(dx) < 0.01 and abs(dz) < 0.01:
            return None
        forward = numpy.array([math.sin(self.player.yaw), 0.0, math.cos(self.player.yaw)])
        right = numpy.array([forward[2], 0.0, -forward[0]])
        to_target = numpy.array([dx, 0.0, dz])
        to_target = to_target / numpy.linalg.norm(to_target)
        fwd_dot = numpy.dot(to_target, forward)
        right_dot = numpy.dot(to_target, right)
        if abs(fwd_dot) > abs(right_dot):
            return 'w' if fwd_dot > 0 else 's'
        else:
            return 'd' if right_dot > 0 else 'a'

    def update(self, dt, current_time, nearest_mob=None, nearest_health=None, nearest_loot=None):
        if not self.enabled:
            return

        self.attack_cooldown_left = max(0.0, self.attack_cooldown_left - dt)
        self.attack_cooldown_right = max(0.0, self.attack_cooldown_right - dt)
        self._wander_timer -= dt

        for k in ['w','a','s','d']:
            self.player.movement[k] = False

        need_health = self.player.life < self.player.life_max

        mob = nearest_mob if nearest_mob and self._distance_to(nearest_mob.position) < self.engage_range else None

        if mob:
            if self._last_shot_time == 0.0:
                self._last_shot_time = current_time
            dist = self._distance_to(mob.position)

            # Give up if no shot landed in 3s (mob unreachable/unshootable)
            if current_time - self._last_shot_time > 3.0:
                self._last_shot_time = 0.0
                self.state = "MOVING"
                self.player.movement['w'] = True
                if need_health and nearest_health:
                    self.state = "COLLECTING"
                    pos = nearest_health.get_world_position()
                    self._aim_at_target(pos, dt)
                self._debug_log(dt, None)
                return

            # Give up if mob distance hasn't changed in 3s (stuck/unreachable)
            if abs(dist - self._last_mob_dist) < 0.5:
                if self._last_dist_change == 0.0:
                    self._last_dist_change = current_time
                elif current_time - self._last_dist_change > 3.0:
                    self._last_dist_change = 0.0
                    self._last_shot_time = 0.0
                    self.state = "MOVING"
                    self.player.movement['w'] = True
                    if need_health and nearest_health:
                        self.state = "COLLECTING"
                        pos = nearest_health.get_world_position()
                        self._aim_at_target(pos, dt)
                    self._debug_log(dt, None)
                    return
            else:
                self._last_mob_dist = dist
                self._last_dist_change = 0.0

            # --- CLOSE MOB: attack, move toward mob ---
            if dist < self.shoot_range:
                # Critical health: go to health immediately
                if need_health and self.player.life < 50 and nearest_health and self.player.life > 0:
                    self._last_shot_time = 0.0
                    self.state = "COLLECTING"
                    self._aim_at_target(nearest_health.get_world_position(), dt)
                    self.player.movement['w'] = True
                    self._debug_log(dt, None)
                    return

                self.state = "ATTACKING"
                self._aim_at_target(mob.position, dt)

                if dist < self.backoff_range and (current_time > self._chase_until or dist < 3.0):
                    self.player.movement['s'] = True
                    self._backing_off = True
                    self._backoff_start_time = current_time
                elif self._backing_off and current_time - self._backoff_start_time < 1.5:
                    self.player.movement['s'] = True
                else:
                    self._backing_off = False
                    self._chase_until = current_time + 2.0
                    if dist < 5.0:
                        self.player.movement['d' if random.random() < 0.5 else 'a'] = True
                    else:
                        self.player.movement['w'] = True
                        if dist < self.backoff_range + 3.0:
                            self.player.movement['d' if random.random() < 0.5 else 'a'] = True

                if need_health and nearest_health:
                    dir_key = self._direction_to_target(nearest_health.get_world_position())
                    if dir_key and dir_key in ('a', 'd'):
                        self.player.movement[dir_key] = True

                if dist < 20.0 and self._is_target_in_front(mob.position, 45.0):
                    if self.attack_cooldown_left <= 0.0:
                        ammo = self._shoot_at(mob, self.left_weapon, current_time)
                        if ammo:
                            self.attack_cooldown_left = self.left_weapon.cooldown
                            self._last_shot_time = current_time
                    if self.attack_cooldown_right <= 0.0:
                        ammo = self._shoot_at(mob, self.right_weapon, current_time)
                        if ammo:
                            self.attack_cooldown_right = self.right_weapon.cooldown
                            self._last_shot_time = current_time

                self._debug_log(dt, mob)
                return

            # --- FAR MOB + low HP: collect health first ---
            if need_health and nearest_health:
                self.state = "COLLECTING"
                pos = nearest_health.get_world_position()
                self._aim_at_target(pos, dt)
                self.player.movement['w'] = True
                self._debug_log(dt, mob)
                return

            # --- FAR MOB: chase ---
            self.state = "CHASING"
            self._aim_at_target(mob.position, dt)
            self.player.movement['w'] = True
            self._debug_log(dt, mob)
            return

        # --- NO MOB ---
        self._backing_off = False
        self.player.movement['w'] = True

        if need_health and nearest_health:
            self.state = "COLLECTING"
            pos = nearest_health.get_world_position()
            self._aim_at_target(pos, dt)
            self._debug_log(dt, None)
            return

        self.state = "MOVING"
        if self._wander_timer <= 0.0:
            self._wander_yaw = random.uniform(-30, 30)
            self._wander_timer = random.uniform(2.0, 5.0)
        self.player.yaw += math.radians(self._wander_yaw * dt)
        self.player.yaw = math.atan2(math.sin(self.player.yaw), math.cos(self.player.yaw))
        if self.camera.mode == 0:
            self.camera.yaw = math.degrees(self.player.yaw)
            self.camera.update_vectors()
        self._debug_log(dt, None)

    def _aim_at_target(self, target_pos, dt):
        dx = target_pos[0] - self.player.position[0]
        dz = target_pos[2] - self.player.position[2]
        if math.hypot(dx, dz) < 0.01:
            return True
        target_yaw = math.atan2(dx, dz)
        current_yaw = math.atan2(math.sin(self.player.yaw), math.cos(self.player.yaw))
        diff = target_yaw - current_yaw
        while diff > math.pi:
            diff -= 2*math.pi
        while diff < -math.pi:
            diff += 2*math.pi
        if abs(diff) < math.radians(2.0):
            return True
        max_rot = math.radians(120.0 * dt)
        if abs(diff) > max_rot:
            diff = max_rot if diff > 0 else -max_rot
        self.player.yaw += diff
        self.player.yaw = math.atan2(math.sin(self.player.yaw), math.cos(self.player.yaw))
        if self.camera.mode == 0:
            self.camera.yaw = math.degrees(self.player.yaw)
            self.camera.update_vectors()
        return False

    def _is_target_in_front(self, target_pos, angle_threshold_deg):
        player_forward = numpy.array([math.sin(self.player.yaw), 0.0, math.cos(self.player.yaw)])
        to_target = numpy.array([target_pos[0] - self.player.position[0],
                                  0.0,
                                  target_pos[2] - self.player.position[2]])
        if numpy.linalg.norm(to_target) == 0:
            return False
        to_target = to_target / numpy.linalg.norm(to_target)
        return numpy.dot(to_target, player_forward) >= math.cos(math.radians(angle_threshold_deg))

    def _shoot_at(self, target, weapon, current_time):
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
            direction = numpy.array([math.sin(self.player.yaw), 0.0, math.cos(self.player.yaw)])
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

    def _debug_log(self, dt, nearest_mob):
        self._debug_timer -= dt
        if self._debug_timer <= 0.0:
            self._debug_timer = 0.5
            mov = ''.join(k for k in ['w','a','s','d'] if self.player.movement.get(k))
            mob_d = f"{self._distance_to(nearest_mob.position):.1f}" if nearest_mob else "-"
            logging.debug(f"AI: {self.state} hp={self.player.life}/{self.player.life_max} y={self.player.position[1]:.1f} yaw={math.degrees(self.player.yaw):.0f} mov={mov} mob={mob_d}")
