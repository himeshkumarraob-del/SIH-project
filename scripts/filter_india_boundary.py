#!/usr/bin/env python3
"""
CLI entry point for filtering the cleaned FIRMS dataset to India's actual
national boundary (replacing the coarse bounding-box filter).

Reads data/interim/firms_clean.csv, downloads/caches India's boundary
polygon under data/external/, keeps only detections inside it, writes
data/processed/firms_india.csv, and prints a summary.

Usage:
    python scripts/filter_india_boundary.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run directly, this script's own dir (scripts/) lands on sys.path[0], not
# the project root -- add the root so `src` is importable regardless of cwd.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.preprocessing.india_boundary_filter import (  # noqa: E402
    print_summary,
    run_india_filter_pipeline,
    save_india_dataset,
)
from src.logging_setup import get_logger  # noqa: E402

logger = get_logger("scripts.filter_india_boundary")


def main() -> int:
    try:
        df, report = run_india_filter_pipeline()
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        logger.error("India boundary filtering failed: %s", exc)
        print(f"ERROR: {exc}")
        return 1

    save_india_dataset(df)
    print_summary(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())