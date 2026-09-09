"""
Shared file I/O helpers for pipeline stages: atomic CSV writes with
one-generation backup/rollback.

Every pipeline output that the API serves is written to a temp file and then
moved into place with os.replace(), so readers never observe a partially
written dataset and a crash mid-write can never corrupt the previous
generation. Before replacing an existing file, the current generation is
copied to <parent>/.backup/<name> (rotated, keeping N generations) so a bad
run can be rolled back by copying the backup over the live file.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pandas as pd

from src.logging_setup import get_logger

logger = get_logger("persistence.atomic_io")

BACKUP_DIRNAME = ".backup"
KEEP_GENERATIONS = 2


def _backup_path(target: Path) -> Path:
    return target.parent / BACKUP_DIRNAME / target.name


def write_csv_atomic(
    df: pd.DataFrame,
    target: Path,
    keep_backup: bool = True,
    backup_generations: int = KEEP_GENERATIONS,
) -> Path:
    """
    Write a DataFrame to `target` atomically.

    Steps:
      1. Rotate existing backups (keep the newest `backup_generations`).
      2. Copy the current live file into .backup/ (if it exists and
         keep_backup is True).
      3. Write to <target>.tmp in the same directory.
      4. os.replace() tmp -> target (atomic on POSIX and Windows).

    A crash at any point leaves either the old file or the new file — never a
    truncated one.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    if keep_backup and target.exists():
        backup = _backup_path(target)
        backup.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(target, backup)
            # Rotate older generations: .backup/<name>.1, .backup/<name>.2 ...
            for gen in range(backup_generations - 1, 0, -1):
                src = backup.with_name(backup.name + f".{gen}")
                dst = backup.with_name(backup.name + f".{gen + 1}")
                if src.exists():
                    os.replace(src, dst)
            shutil.copy2(target, backup.with_name(backup.name + ".1"))
        except OSError as exc:
            # Backup failure must never block the write itself.
            logger.warning("Could not back up %s before overwrite: %s", target, exc)

    tmp_path = target.with_name(target.name + ".tmp")
    df.to_csv(tmp_path, index=False)
    os.replace(tmp_path, target)
    logger.debug("Atomically wrote %s (%d rows)", target, len(df))
    return target


def write_json_atomic(payload: dict, target: Path) -> Path:
    """Write a JSON dict atomically (same guarantees as write_csv_atomic)."""
    import json

    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(target.name + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    os.replace(tmp_path, target)
    return target


def restore_latest_backup(target: Path) -> bool:
    """
    Roll a file back from .backup/<name>.1 (the most recent generation).
    Returns True when a rollback was performed.
    """
    target = Path(target)
    backup = _backup_path(target).with_name(target.name + ".1")
    if backup.exists():
        shutil.copy2(backup, target)
        logger.warning("Rolled back %s from %s", target, backup)
        return True
    return False
