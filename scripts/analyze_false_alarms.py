#!/usr/bin/env python3
"""
CLI entry point for False Alarm Intelligence analysis.

Reads data/processed/firms_ai_results.csv, applies the FalseAlarmDetector,
and outputs data/processed/firms_false_alarm.csv.

Usage:
    python scripts/analyze_false_alarms.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.models.false_alarm_detector import FalseAlarmDetector
from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("scripts.analyze_false_alarms")

def main() -> int:
    cfg = get_config()
    input_path = cfg.processed_data_dir / "firms_ai_results.csv"
    output_path = cfg.processed_data_dir / "firms_false_alarm.csv"

    if not input_path.exists():
        logger.error(f"Missing required input AI results dataset: {input_path}")
        print(f"ERROR: Missing input AI results dataset: {input_path}")
        return 1

    try:
        df = pd.read_csv(input_path)
        logger.info(f"Loaded {len(df)} records from {input_path}")

        detector = FalseAlarmDetector()
        results_df = detector.evaluate(df)

        results_df.to_csv(output_path, index=False)
        logger.info(f"Saved false alarm intelligence results to {output_path}")

        total_records = len(results_df)
        counts = results_df["false_alarm_indicator"].value_counts()
        rel_counts = results_df["detection_reliability"].value_counts()

        print("\n=== False Alarm Intelligence Summary ===")
        print(f"Records Processed:          {total_records}")
        print("\nFalse Alarm Concern Indicators:")
        print(f"  LOW (Low Concern/Reliable): {counts.get('LOW', 0)}")
        print(f"  MEDIUM (Moderate Concern):  {counts.get('MEDIUM', 0)}")
        print(f"  HIGH (High Concern/Weak):   {counts.get('HIGH', 0)}")
        print("\nDetection Reliability Breakdown:")
        print(f"  HIGH Reliability:          {rel_counts.get('HIGH', 0)}")
        print(f"  MEDIUM Reliability:        {rel_counts.get('MEDIUM', 0)}")
        print(f"  LOW Reliability:           {rel_counts.get('LOW', 0)}")
        print(f"\nOutput File Saved:          {output_path}")

        print("\n--- Example Records ---")
        sample_high_fa = results_df[results_df["false_alarm_indicator"] == "HIGH"].head(2)
        sample_low_fa = results_df[results_df["false_alarm_indicator"] == "LOW"].head(2)

        sample = pd.concat([sample_high_fa, sample_low_fa])
        for _, row in sample.iterrows():
            print(f"Cluster ID: {row['cluster_id']} (Level: {row['abnormality_level']})")
            print(f"  False Alarm Concern: {row['false_alarm_indicator']}")
            print(f"  Reliability:         {row['detection_reliability']}")
            print(f"  Reasons:             {row['false_alarm_reasons']}\n")

        print("=======================================\n")

    except Exception as exc:
        logger.exception("False alarm analysis failed")
        print(f"ERROR: False alarm analysis failed: {exc}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
