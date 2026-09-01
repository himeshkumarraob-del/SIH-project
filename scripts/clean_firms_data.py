#!/usr/bin/env python3
"""
CLI entry point for cleaning raw FIRMS CSVs.

Reads every raw CSV in data/raw/, combines and cleans them, writes
data/interim/firms_clean.csv, and prints a summary.

Usage:
    python scripts/clean_firms_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run directly, this script's own dir (scripts/) lands on sys.path[0], not
# the project root -- add the root so `src` is importable regardless of cwd.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.preprocessing.clean_firms import (  # noqa: E402
    print_summary,
    run_cleaning_pipeline,
    save_cleaned_dataset,
)
from src.logging_setup import get_logger  # noqa: E402

logger = get_logger("scripts.clean_firms_data")


def main() -> int:
    try:
        df, report = run_cleaning_pipeline()
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Cleaning pipeline failed: %s", exc)
        print(f"ERROR: {exc}")
        return 1

    save_cleaned_dataset(df)
    print_summary(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())