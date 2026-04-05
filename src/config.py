import logging
import json
import os

DEFAULT_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        "simple": {
            "format": "%(levelname)s: %(message)s"
        }
    },
    "handlers": {
        "console_stdout": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "simple",
            "stream": "ext://sys.stdout",
            "filters": ["level_filter_stdout"]
        },
        "console_stderr": {
            "class": "logging.StreamHandler",
            "level": "WARNING",
            "formatter": "default",
            "stream": "ext://sys.stderr"
        },
        "file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "level": "DEBUG",
            "formatter": "default",
            "filename": "logs/pyf3d.log",
            "when": "D",
            "interval": 1,
            "backupCount": 31,
            "encoding": "utf8"
        }
    },
    "filters": {
        "level_filter_stdout": {
            "()": "logger.LevelFilter",
            "max_level": "WARNING"
        }
    },
    "root": {
        "level": "DEBUG",
        "handlers": ["console_stdout", "console_stderr", "file"]
    }
}

class Config:
    CONFIG_FILE = "config.json"

    # Default values
    defaults = {
        "mouse_sensitivity": 1.0,
        "movement_speed": 10.0,
        "player_height": 1.5,
        "terrain_spacing": 1.0,
        "chunk_size": 16,
        "load_radius": 1,
        "cloud_count_per_chunk": 2,
        "day_duration": 60.0,
        "star_count": 500,
        "snow_count": 500,
        "snow_draw": False,
        "draw_compass": True,
        "compass_scale": 1.0,
        "draw_stats": True,
        "db_path": "data.db",
        "spawn_mode": "saved",   # "saved", "random", "portal"
        "random_spawn_range": 500,
        "camera_mode": 0,
        "rotate_only_horizontal": False,
        "show_fps": False,
        "draw_fog": False,
        "log_config": DEFAULT_LOG_CONFIG
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
            except Exception as e: # fallback: create default file
                logging.error(f"Error loading config: {e}")
                cls.save(cls.defaults)
                return cls.defaults.copy()
        else: # Config file missing – create it with defaults
            cls.save(cls.defaults)
            return cls.defaults.copy()

    @classmethod
    def save(cls, settings):
        try:
            with open(cls.CONFIG_FILE, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving config: {e}")
