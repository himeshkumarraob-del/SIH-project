#!/usr/bin/env python3
"""
CLI entry point for persistence analysis.

Reads data/processed/firms_india.csv, clusters detections by spatial +
temporal proximity, computes per-cluster persistence features, writes
data/processed/firms_persistence.csv, and prints a summary.

Usage:
    python scripts/analyze_persistence.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run directly, this script's own dir (scripts/) lands on sys.path[0], not
# the project root -- add the root so `src` is importable regardless of cwd.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.persistence.persistence_analysis import (  # noqa: E402
    print_summary,
    run_persistence_pipeline,
    save_persistence_dataset,
)
from src.logging_setup import get_logger  # noqa: E402

logger = get_logger("scripts.analyze_persistence")


def main() -> int:
    try:
        clusters, report = run_persistence_pipeline()
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Persistence analysis failed: %s", exc)
        print(f"ERROR: {exc}")
        return 1

    out_path = save_persistence_dataset(clusters)
    print_summary(report)
    print(f"Output file: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())