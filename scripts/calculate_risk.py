#!/usr/bin/env python3
"""
CLI entry point for Risk Intelligence calculation.

1. Reads data/processed/firms_ai_results.csv and data/processed/firms_false_alarm.csv.
2. Merges datasets on cluster_id.
3. Applies RiskIntelligenceEngine to calculate risk_score, risk_level, risk_factors, risk_explanation.
4. Saves output to data/processed/firms_risk_results.csv.

Usage:
    python scripts/calculate_risk.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.models.risk_intelligence import RiskIntelligenceEngine
from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("scripts.calculate_risk")

def main() -> int:
    cfg = get_config()
    ai_results_path = cfg.processed_data_dir / "firms_ai_results.csv"
    false_alarm_path = cfg.processed_data_dir / "firms_false_alarm.csv"
    output_path = cfg.processed_data_dir / "firms_risk_results.csv"

    if not ai_results_path.exists():
        logger.error(f"Missing required AI results dataset: {ai_results_path}")
        print(f"ERROR: Missing AI results dataset: {ai_results_path}")
        return 1

    if not false_alarm_path.exists():
        logger.error(f"Missing required false alarm dataset: {false_alarm_path}")
        print(f"ERROR: Missing false alarm dataset: {false_alarm_path}")
        return 1

    try:
        ai_df = pd.read_csv(ai_results_path)
        fa_df = pd.read_csv(false_alarm_path)

        logger.info(f"Loaded {len(ai_df)} AI results and {len(fa_df)} false alarm records.")

        # Merge on cluster_id, combining non-duplicate columns
        fa_extra_cols = [c for c in fa_df.columns if c not in ai_df.columns or c == "cluster_id"]
        merged_df = pd.merge(ai_df, fa_df[fa_extra_cols], on="cluster_id", how="left")

        engine = RiskIntelligenceEngine()
        results_df = engine.calculate_risk(merged_df)

        results_df.to_csv(output_path, index=False)
        logger.info(f"Saved risk intelligence results to {output_path}")

        total_records = len(results_df)
        level_counts = results_df["risk_level"].value_counts()
        min_score = results_df["risk_score"].min()
        max_score = results_df["risk_score"].max()
        avg_score = results_df["risk_score"].mean()

        print("\n=== Risk Intelligence Summary ===")
        print(f"Total Records Processed:   {total_records}")
        print(f"Risk Score Range:          {min_score:.1f} to {max_score:.1f}")
        print(f"Average Risk Score:        {avg_score:.1f}")
        print("\nRisk Level Breakdown:")
        print(f"  LOW Risk:                {level_counts.get('LOW', 0)}")
        print(f"  MEDIUM Risk:             {level_counts.get('MEDIUM', 0)}")
        print(f"  HIGH Risk:               {level_counts.get('HIGH', 0)}")

        print("\n=== Cross-Tabulation: abnormality_level x risk_level ===")
        print(pd.crosstab(results_df["abnormality_level"], results_df["risk_level"], margins=True))

        print("\n=== Cross-Tabulation: false_alarm_indicator x risk_level ===")
        print(pd.crosstab(results_df["false_alarm_indicator"], results_df["risk_level"], margins=True))

        print("\n=== Top 10 Highest-Risk Events ===")
        top10 = results_df.sort_values(by="risk_score", ascending=False).head(10)
        cols_show = ["cluster_id", "risk_score", "risk_level", "abnormality_level", "false_alarm_indicator", "max_frp", "risk_factors"]
        print(top10[cols_show].to_string(index=False))

        print(f"\nOutput File Saved:          {output_path}")
        print("===================================\n")

    except Exception as exc:
        logger.exception("Risk calculation failed")
        print(f"ERROR: Risk calculation failed: {exc}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
