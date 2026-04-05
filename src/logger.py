import json
import logging
import logging.config
import os

# # default log to console stream
# from sys import stderr, stdout
# logger = logging.getLogger()
# logger.setLevel(logging.DEBUG)
# logger.addHandler(logging.StreamHandler(stderr))
# logger.addHandler(logging.StreamHandler(stdout))


class LevelFilter(logging.Filter):
    def __init__(self, max_level):
        self.max_level = getattr(logging, max_level.upper())
    def filter(self, record):
        return record.levelno < self.max_level


def setup_logging(log_cfg):
    if isinstance(log_cfg, str):
        try:
            log_cfg = json.loads(log_cfg)
        except json.JSONDecodeError as err:
            logging.basicConfig(level=logging.DEBUG)
            logging.error(f"Failed to parse log_config JSON: {err}")
            return
    if not log_cfg:
        # fallback to a basic configuration
        logging.basicConfig(level=logging.DEBUG)
        return

    # Ensure the log directory exists for any file handlers
    for handler_cfg in log_cfg.get('handlers', {}).values():
        if 'filename' in handler_cfg:
            log_dir = os.path.dirname(handler_cfg['filename'])
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)

    # Apply the dictionary configuration
    logging.config.dictConfig(log_cfg)
    logging.debug("Logging configured via dictConfig")
