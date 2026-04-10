import numpy
import re
import sqlite3
import json
from logger import logging


class Serializer:
    def __init__(self, db_path):
        self.allowed_tables = {'player', 'chunks', 'healthes', 'mobs'}
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS player (
                    id INTEGER PRIMARY KEY,
                    pos_x REAL,
                    pos_y REAL,
                    pos_z REAL,
                    portal_x REAL,
                    portal_y REAL,
                    portal_z REAL,
                    height REAL,
                    speed REAL,
                    level INTEGER,
                    life INTEGER,
                    mana INTEGER,
                    weapon_name TEXT,
                    ammo_count INTEGER,
                    killed_mobs INTEGER,
                    familiar_name TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chunks (
                    portal INTEGER DEFAULT 0,
                    cx INTEGER,
                    cz INTEGER,
                    vertices BLOB,
                    indices BLOB,
                    stones BLOB,
                    trees BLOB,
                    PRIMARY KEY (cx, cz)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS healthes (
                    cx INTEGER,
                    cz INTEGER,
                    data BLOB,
                    PRIMARY KEY (cx, cz)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mobs (
                    cx INTEGER,
                    cz INTEGER,
                    data BLOB,
                    PRIMARY KEY (cx, cz)
                )
            ''')
            conn.commit()

    def update(self, table, fields, values, where="id = 1"):
        if table not in self.allowed_tables:
            logging.error(f"Table '{table}' not allowed for update")
            return
        if len(fields) != len(values):
            logging.error("Fields and values length mismatch")
            return
        for col in fields:
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', col):
                logging.error(f"Invalid column name: {col}")
                return
        set_clause = ", ".join(f"{col} = ?" for col in fields)
        query = f"UPDATE {table} SET {set_clause} WHERE {where}"
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, values)
            conn.commit()

    def save_player(self, player_data):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO player
                (id, pos_x, pos_y, pos_z, portal_x, portal_y, portal_z,
                height, speed, level, life, mana, weapon_name,
                ammo_count, killed_mobs, familiar_name)
                VALUES (1, :pos_x, :pos_y, :pos_z,
                        :portal_x, :portal_y, :portal_z,
                        :height, :speed, :level, :life, :mana,
                        :weapon_name, :ammo_count, :killed_mobs,
                        :familiar_name)
            ''', player_data)

    def load_player(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM player WHERE id = 1')
            row = cursor.fetchone()
            if row:
                return {
                    'pos_x': row['pos_x'],
                    'pos_y': row['pos_y'],
                    'pos_z': row['pos_z'],
                    'portal_x': row['portal_x'],
                    'portal_y': row['portal_y'],
                    'portal_z': row['portal_z'],
                    'height': row['height'],
                    'speed': row['speed'],
                    'level': row['level'],
                    'life': row['life'],
                    'mana': row['mana'],
                    'weapon_name': row['weapon_name'],
                    'ammo_count': row['ammo_count'],
                    'killed_mobs': row['killed_mobs'],
                    'familiar_name': row['familiar_name']
                }
            return None

    def clear_chunks(self, portal=False):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''DELETE FROM chunks WHERE portal = ?''', (1 if portal else 0, ))
            conn.commit()

    def save_chunk(self, portal, cx, cz, vertices, indices, stones, trees):
        vertices_bytes = vertices.tobytes()
        indices_bytes = indices.tobytes()
        rounded_stones = []
        for s in stones:
            rounded_stones.append({
                'x': round(s['x'], 1),
                'y': round(s['y'], 1),
                'z': round(s['z'], 1),
                'trunk_height': round(s.get('trunk_height', 1.5), 1),
                'foliage_radius': round(s.get('foliage_radius', 0.6), 1),
                'rotation_y': round(s.get('rotation_y', 0), 1)
            })
        rounded_trees = []
        for t in trees:
            rounded_trees.append({
                'x': round(t['x'], 1),
                'y': round(t['y'], 1),
                'z': round(t['z'], 1),
                'trunk_height': round(t.get('trunk_height', 1.5), 1),
                'foliage_radius': round(t.get('foliage_radius', 0.6), 1),
                'rotation_y': round(t.get('rotation_y', 0), 1)
            })
        stones_json = json.dumps(rounded_stones).encode('utf-8')
        trees_json = json.dumps(rounded_trees).encode('utf-8')
        portal_int = 1 if portal else 0
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO chunks (portal, cx, cz, vertices, indices, stones, trees)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (portal_int, cx, cz, vertices_bytes, indices_bytes, stones_json, trees_json))
            conn.commit()

    def load_chunk(self, cx, cz):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT portal, vertices, indices, stones, trees FROM chunks WHERE cx = ? AND cz = ?', (cx, cz))
            row = cursor.fetchone()
            if row:
                portal, vertices_bytes, indices_bytes, stones_json, trees_json = row
                num_vertices = len(vertices_bytes) // (4 * 6)
                vertices = numpy.frombuffer(vertices_bytes, dtype=numpy.float32).reshape(num_vertices, 6)
                num_indices = len(indices_bytes) // 4
                indices = numpy.frombuffer(indices_bytes, dtype=numpy.uint32).reshape(num_indices)
                stones = json.loads(stones_json.decode('utf-8'))
                trees = json.loads(trees_json.decode('utf-8'))
                return bool(portal), vertices, indices, stones, trees
            return False, None, None, None, None

    def save_mobs(self, cx, cz, mobs_data):
        json_str = json.dumps(mobs_data)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO mobs (cx, cz, data)
                VALUES (?, ?, ?)
            ''', (cx, cz, json_str))
            conn.commit()

    def load_mobs(self, cx, cz):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT data FROM mobs WHERE cx = ? AND cz = ?', (cx, cz))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

    def save_health(self, cx, cz, cube_dict):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if cube_dict is None:
                cursor.execute('DELETE FROM healthes WHERE cx = ? AND cz = ?', (cx, cz))
            else:
                json_str = json.dumps(cube_dict)
                cursor.execute('''
                    INSERT OR REPLACE INTO healthes (cx, cz, data)
                    VALUES (?, ?, ?)
                ''', (cx, cz, json_str))
            conn.commit()

    def load_health(self, cx, cz):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT data FROM healthes WHERE cx = ? AND cz = ?', (cx, cz))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
