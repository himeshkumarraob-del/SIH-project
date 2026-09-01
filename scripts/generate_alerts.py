#!/usr/bin/env python3
"""
CLI Script to generate fire-station locator & emergency alert recommendations.

1. Reads data/processed/firms_risk_results.csv, data/processed/firms_false_alarm.csv,
   and data/processed/firms_industrial_classification.csv.
2. Locates nearest regional fire station for each cluster.
3. Evaluates decision-support alert recommendations based on risk and false-alarm concern.
4. Outputs data/processed/emergency_alerts.csv.

Usage:
    python scripts/generate_alerts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.response.alert_engine import OperationalAlertEngine
from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("scripts.generate_alerts")

def main() -> int:
    cfg = get_config()
    risk_path = cfg.processed_data_dir / "firms_risk_results.csv"
    fa_path = cfg.processed_data_dir / "firms_false_alarm.csv"
    class_path = cfg.processed_data_dir / "firms_industrial_classification.csv"
    gis_path = cfg.processed_data_dir / "gis_thermal_events.csv"
    output_path = cfg.processed_data_dir / "emergency_alerts.csv"

    if not risk_path.exists():
        logger.error(f"Missing required dataset: {risk_path}")
        print(f"ERROR: Missing dataset: {risk_path}")
        return 1

    try:
        risk_df = pd.read_csv(risk_path)
        fa_df = pd.read_csv(fa_path) if fa_path.exists() else pd.DataFrame()
        class_df = pd.read_csv(class_path) if class_path.exists() else pd.DataFrame()
        gis_df = pd.read_csv(gis_path) if gis_path.exists() else pd.DataFrame()

        # Compute cluster centroid lat/lon
        if not gis_df.empty and "latitude" in gis_df.columns:
            centroids = gis_df.groupby("cluster_id").agg(
                latitude=("latitude", "mean"),
                longitude=("longitude", "mean")
            ).reset_index()
        else:
            centroids = pd.DataFrame({"cluster_id": risk_df["cluster_id"], "latitude": 20.0, "longitude": 78.0})

        merged = pd.merge(risk_df, centroids, on="cluster_id", how="left")
        if not fa_df.empty and "false_alarm_indicator" in fa_df.columns:
            fa_cols = [c for c in fa_df.columns if c not in merged.columns or c == "cluster_id"]
            merged = pd.merge(merged, fa_df[fa_cols], on="cluster_id", how="left")

        if not class_df.empty and "classification_label" in class_df.columns:
            class_cols = [c for c in class_df.columns if c not in merged.columns or c == "cluster_id"]
            merged = pd.merge(merged, class_df[class_cols], on="cluster_id", how="left")

        engine = OperationalAlertEngine()
        alerts_df = engine.generate_alerts(merged)

        cols_export = [
            "cluster_id", "risk_score", "risk_level", "false_alarm_indicator", "classification_label",
            "alert_priority", "recommended_action", "nearest_station_name", "station_distance_km", "alert_rationale"
        ]
        export_df = alerts_df[[c for c in cols_export if c in alerts_df.columns]]
        export_df.to_csv(output_path, index=False)
        logger.info(f"Saved emergency alert recommendations to {output_path}")

        total = len(export_df)
        prio_counts = export_df["alert_priority"].value_counts()

        print("\n=== Emergency Alert & Fire Station Decision-Support Summary ===")
        print(f"Total Events Processed:        {total}")
        print("\nAlert Priority Breakdown:")
        print(f"  HIGH PRIORITY ALERT:         {prio_counts.get('HIGH PRIORITY ALERT', 0)}")
        print(f"  REVIEW / VERIFICATION:       {prio_counts.get('REVIEW / VERIFICATION', 0)}")
        print(f"  MONITOR / REVIEW:            {prio_counts.get('MONITOR / REVIEW', 0)}")
        print(f"  NO ALERT:                    {prio_counts.get('NO ALERT', 0)}")

        print("\n=== Top High Priority Response Recommendations ===")
        high_prio = export_df[export_df["alert_priority"] == "HIGH PRIORITY ALERT"]
        if not high_prio.empty:
            top10 = high_prio.head(10)
            show_cols = ["cluster_id", "risk_score", "nearest_station_name", "station_distance_km", "recommended_action"]
            print(top10[[c for c in show_cols if c in top10.columns]].to_string(index=False))
        else:
            print("  (No events met the criteria for High Priority Alert)")

        print(f"\nOutput File Saved:             {output_path}")
        print("===============================================================\n")

    except Exception as exc:
        logger.exception("Alert generation failed")
        print(f"ERROR: Alert generation failed: {exc}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
