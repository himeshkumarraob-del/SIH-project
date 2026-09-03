#!/usr/bin/env python3
"""
CLI entry point for Thermal Activity Movement Analysis.

1. Reads data/processed/firms_india.csv.
2. Applies cluster_detections to assign cluster_id.
3. Analyzes spatial movement, direction/bearing, and rate of movement per cluster.
4. Exports data/processed/thermal_movement.csv.

Usage:
    python scripts/analyze_thermal_movement.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.persistence.persistence_analysis import cluster_detections
from src.gis.thermal_movement import ThermalMovementAnalyzer
from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("scripts.analyze_thermal_movement")

def main() -> int:
    cfg = get_config()
    india_path = cfg.processed_data_dir / "firms_india.csv"
    output_path = cfg.processed_data_dir / "thermal_movement.csv"

    if not india_path.exists():
        logger.error(f"Missing required input dataset: {india_path}")
        print(f"ERROR: Missing input dataset: {india_path}")
        return 1

    try:
        india_df = pd.read_csv(india_path)
        logger.info(f"Loaded {len(india_df)} raw detection records from {india_path}")

        # Assign cluster_id using persistence module
        cluster_ids = cluster_detections(india_df, cfg.persistence)
        india_df["cluster_id"] = cluster_ids
        logger.info(f"Assigned clusters to {len(india_df)} detections.")

        analyzer = ThermalMovementAnalyzer()
        movement_df = analyzer.analyze_clusters(india_df)

        movement_df.to_csv(output_path, index=False)
        logger.info(f"Saved thermal movement results to {output_path}")

        total_clusters = len(movement_df)
        status_counts = movement_df["movement_status"].value_counts()
        conf_counts = movement_df["movement_confidence"].value_counts()

        moving_df = movement_df[movement_df["movement_status"] == "MOVING"]
        min_dist = moving_df["total_movement_distance_km"].min() if not moving_df.empty else 0.0
        max_dist = moving_df["total_movement_distance_km"].max() if not moving_df.empty else 0.0
        avg_dist = moving_df["total_movement_distance_km"].mean() if not moving_df.empty else 0.0

        # Direction intelligence breakdown (novel feature)
        pattern_counts = movement_df["movement_pattern"].value_counts()
        dir_conf_counts = movement_df["direction_confidence"].value_counts()
        dir_available = int(movement_df["direction_available"].sum())

        print("\n=== Thermal Activity Movement Summary ===")
        print(f"Total Clusters Analyzed:    {total_clusters}")
        print("\nMovement Status Breakdown:")
        print(f"  MOVING:                   {status_counts.get('MOVING', 0)}")
        print(f"  STATIONARY:               {status_counts.get('STATIONARY', 0)}")
        print(f"  INSUFFICIENT_DATA:        {status_counts.get('INSUFFICIENT_DATA', 0)}")

        print("\nMovement Confidence Breakdown:")
        print(f"  HIGH Confidence:          {conf_counts.get('HIGH', 0)}")
        print(f"  MEDIUM Confidence:        {conf_counts.get('MEDIUM', 0)}")
        print(f"  LOW Confidence:           {conf_counts.get('LOW', 0)}")
        print(f"  INSUFFICIENT_DATA:        {conf_counts.get('INSUFFICIENT_DATA', 0)}")

        print("\nThermal Activity Direction Intelligence:")
        print(f"  Direction available:      {dir_available}")
        print("  Movement pattern:")
        for pat in ["directional", "erratic", "stationary", "insufficient_evidence"]:
            print(f"    {pat:.<22} {int(pattern_counts.get(pat, 0))}")
        print("  Direction confidence:")
        for conf in ["HIGH", "MODERATE", "PRELIMINARY", "INSUFFICIENT"]:
            print(f"    {conf:.<22} {int(dir_conf_counts.get(conf, 0))}")

        print("\nDisplacement Metrics (for MOVING clusters):")
        print(f"  Min Movement Distance:     {min_dist:.2f} km")
        print(f"  Max Movement Distance:     {max_dist:.2f} km")
        print(f"  Average Movement Distance: {avg_dist:.2f} km")

        print("\n=== Top 10 Clusters by Movement Rate (km/day) ===")
        top10 = movement_df.sort_values(by="movement_rate_km_per_day", ascending=False).head(10)
        cols_show = [
            "cluster_id", "movement_status", "movement_pattern", "total_movement_distance_km",
            "time_span_days", "movement_rate_km_per_day", "movement_direction",
            "movement_confidence", "direction", "direction_confidence"
        ]
        print(top10[cols_show].to_string(index=False))

        print("\n=== Verification of Single-Day Clusters ===")
        single_day = movement_df[movement_df["active_days"] == 1]
        invalid_single_day = single_day[single_day["movement_direction"] != "INSUFFICIENT_DATA"]
        print(f"Single-day clusters analyzed: {len(single_day)}")
        print(f"Single-day clusters with improper non-INSUFFICIENT_DATA direction: {len(invalid_single_day)}")

        print(f"\nOutput File Saved:          {output_path}")
        print("==========================================\n")

    except Exception as exc:
        logger.exception("Thermal movement analysis failed")
        print(f"ERROR: Thermal movement analysis failed: {exc}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
