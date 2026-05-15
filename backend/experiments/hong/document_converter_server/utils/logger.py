from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from config import LOG_FILE, LOG_LEVEL, ensure_directories


def setup_logging() -> None:
    ensure_directories()

    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    root_logger.setLevel(LOG_LEVEL)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)

