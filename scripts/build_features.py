#!/usr/bin/env python3
"""
CLI entry point for feature engineering.

Reads data/processed/firms_persistence.csv, extracts mathematical,
thermal contrast, and temporal features, saves data/processed/firms_features.csv,
and prints a summary report.

Usage:
    python scripts/build_features.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.features.feature_engineering import (  # noqa: E402
    print_feature_summary,
    run_feature_pipeline,
    save_features_dataset,
)
from src.logging_setup import get_logger  # noqa: E402

logger = get_logger("scripts.build_features")


def main() -> int:
    try:
        features_df, report = run_feature_pipeline()
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Feature engineering failed: %s", exc)
        print(f"ERROR: {exc}")
        return 1

    out_path = save_features_dataset(features_df)
    print_feature_summary(report)
    print(f"Output file saved to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
