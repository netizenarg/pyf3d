import numpy
import re
import sqlite3

from logger import logging


class Serializer:
    def __init__(self, db_path):
        # Allowed tables – add more as needed
        self.allowed_tables = {'player', 'chunks', 'healthes', 'mobs'}
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Player stats table
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
            # table for chunks
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chunks (
                    cx INTEGER,
                    cz INTEGER,
                    vertices BLOB,
                    indices BLOB,
                    PRIMARY KEY (cx, cz)
                )
            ''')
            # table for healthes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS healthes (
                    cx INTEGER,
                    cz INTEGER,
                    data BLOB,
                    PRIMARY KEY (cx, cz)
                )
            ''')
            # table for mobs
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mobs (
                    cx INTEGER,
                    cz INTEGER,
                    data BLOB,
                    PRIMARY KEY (cx, cz)
                )
            ''')
            # table for trees
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trees (
                    cx INTEGER,
                    cz INTEGER,
                    data BLOB,
                    PRIMARY KEY (cx, cz)
                )
            ''')
            conn.commit()

    def update(self, table, fields, values, where="id = 1"):
        """
        Generic update for any table.
        - table: string, table name (must be in allowed list)
        - fields: tuple/list of column names
        - values: tuple/list of corresponding values
        - where: optional WHERE clause (default "id = 1")
        """
        if table not in self.allowed_tables:
            logging.error(f"Table '{table}' not allowed for update")
        if len(fields) != len(values):
            logging.error("Fields and values length mismatch")
        for col in fields: # Sanitize column names – only alphanumeric + underscore
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', col):
                logging.error(f"Invalid column name: {col}")
        # Build SET clause safely
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

    def save_chunk(self, cx, cz, vertices, indices):
        """Save chunk geometry as binary blobs."""
        vertices_bytes = vertices.tobytes()
        indices_bytes = indices.tobytes()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO chunks (cx, cz, vertices, indices)
                VALUES (?, ?, ?, ?)
            ''', (cx, cz, vertices_bytes, indices_bytes))
            conn.commit()

    def load_chunk(self, cx, cz):
        """Load chunk geometry; returns (vertices, indices) or (None, None)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT vertices, indices FROM chunks WHERE cx = ? AND cz = ?', (cx, cz))
            row = cursor.fetchone()
            if row:
                vertices_bytes, indices_bytes = row
                # Reconstruct numpy arrays (assuming float32 for vertices, uint32 for indices)
                # Vertex count = total bytes / (4 bytes per float * 6 floats per vertex)
                num_vertices = len(vertices_bytes) // (4 * 6)
                vertices = numpy.frombuffer(vertices_bytes, dtype=numpy.float32).reshape(num_vertices, 6)
                num_indices = len(indices_bytes) // 4
                indices = numpy.frombuffer(indices_bytes, dtype=numpy.uint32).reshape(num_indices)
                return vertices, indices
            return None, None

    def save_mobs(self, cx, cz, mobs_data):
        """Save list of mob dictionaries for a chunk as JSON."""
        import json
        json_str = json.dumps(mobs_data)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO mobs (cx, cz, data)
                VALUES (?, ?, ?)
            ''', (cx, cz, json_str))
            conn.commit()

    def load_mobs(self, cx, cz):
        """Load list of mob dictionaries for a chunk, or None if none."""
        import json
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT data FROM mobs WHERE cx = ? AND cz = ?', (cx, cz))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

    def save_health(self, cx, cz, cube_dict):
        """Save a health dict for a chunk, or delete if None."""
        import json
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
        """Load health dict for a chunk, or None if missing."""
        import json
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT data FROM healthes WHERE cx = ? AND cz = ?', (cx, cz))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

    def save_trees(self, cx, cz, trees_data):
        """Save list of tree dictionaries for a chunk as JSON, or delete if None."""
        import json
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if trees_data is None:
                cursor.execute('DELETE FROM trees WHERE cx = ? AND cz = ?', (cx, cz))
            else:
                json_str = json.dumps(trees_data)
                cursor.execute('''
                    INSERT OR REPLACE INTO trees (cx, cz, data)
                    VALUES (?, ?, ?)
                ''', (cx, cz, json_str))
            conn.commit()

    def load_trees(self, cx, cz):
        """Load list of tree dictionaries for a chunk, or None if missing."""
        import json
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT data FROM trees WHERE cx = ? AND cz = ?', (cx, cz))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
