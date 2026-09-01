"""
Shared logging configuration.

Every module that needs to log should call get_logger(__name__) rather
than configuring logging itself, so log format/destination stays
consistent across ingestion, preprocessing, persistence, etc.
"""

from __future__ import annotations

import logging
import sys

from src.config import get_config

_configured = False


def _configure_root_logger() -> None:
    global _configured
    if _configured:
        return

    cfg = get_config()
    level = getattr(logging, cfg.log_level.upper(), logging.INFO)

    root = logging.getLogger("thermal_intel")
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    root.addHandler(stream_handler)

    file_handler = logging.FileHandler(cfg.log_file)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    _configure_root_logger()
    return logging.getLogger(f"thermal_intel.{name}")
