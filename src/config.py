import json
import os

class Config:
    CONFIG_FILE = "config.json"

    # Default values
    defaults = {
        "mouse_sensitivity": 1.0,
        "movement_speed": 10.0,
        "player_height": 1.5,
        "terrain_spacing": 1.0,
        "chunk_size": 32,
        "load_radius": 3,
        "cloud_count_per_chunk": 3,
        "day_duration": 60.0,
        "star_count": 500,
        "snow_count": 500,
        "snow_draw": False,
        "draw_compass": True
    }

    @classmethod
    def load(cls):
        if os.path.exists(cls.CONFIG_FILE):
            try:
                with open(cls.CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                # merge with defaults (any missing keys get default)
                merged = cls.defaults.copy()
                merged.update(data)
                return merged
            except Exception as e:
                print(f"Error loading config: {e}")
                return cls.defaults.copy()
        else:
            return cls.defaults.copy()

    @classmethod
    def save(cls, settings):
        try:
            with open(cls.CONFIG_FILE, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
