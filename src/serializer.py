import sqlite3

class Serializer:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Player stats table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS player_stats (
                    id INTEGER PRIMARY KEY,
                    pos_x REAL,
                    pos_y REAL,
                    pos_z REAL,
                    speed REAL,
                    life_percent REAL,
                    mana_percent REAL,
                    weapon_name TEXT,
                    ammo_count INTEGER,
                    familiar_name TEXT,
                    portal_x REAL,
                    portal_y REAL,
                    portal_z REAL,
                    height REAL
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
            conn.commit()

    def save_player(self, player_data):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO player_stats
                (id, pos_x, pos_y, pos_z, speed, life_percent, mana_percent,
                weapon_name, ammo_count, familiar_name, portal_x, portal_y, portal_z, height)
                VALUES (1, :pos_x, :pos_y, :pos_z, :speed, :life_percent,
                        :mana_percent, :weapon_name, :ammo_count, :familiar_name,
                        :portal_x, :portal_y, :portal_z, :height)
            ''', player_data)

    def load_player(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM player_stats WHERE id = 1')
            row = cursor.fetchone()
            if row:
                return {
                    'pos_x': row[1], 'pos_y': row[2], 'pos_z': row[3],
                    'speed': row[4], 'life_percent': row[5], 'mana_percent': row[6],
                    'weapon_name': row[7], 'ammo_count': row[8], 'familiar_name': row[9],
                    'portal_x': row[10], 'portal_y': row[11], 'portal_z': row[12],
                    'height': row[13]
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
