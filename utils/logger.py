from __future__ import annotations

import logging
from pathlib import Path


def get_logger(log_path: str):
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("geneva_gym_scanner")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger
