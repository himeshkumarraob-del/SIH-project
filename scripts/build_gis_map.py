#!/usr/bin/env python3
"""
CLI entry point for GIS map construction.

1. Loads detection data (data/processed/firms_india.csv) and runs cluster_detections.
2. Joins with AI anomaly results (data/processed/firms_ai_results.csv) by cluster_id.
3. Exports data/processed/gis_thermal_events.csv.
4. Generates interactive HTML map at reports/thermal_india_map.html.

Usage:
    python scripts/build_gis_map.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.persistence.persistence_analysis import cluster_detections, compute_cluster_features
from src.gis.map_builder import build_india_map
from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("scripts.build_gis_map")

def main() -> int:
    cfg = get_config()
    india_path = cfg.processed_data_dir / "firms_india.csv"
    persistence_path = cfg.processed_data_dir / "firms_persistence.csv"
    ai_results_path = cfg.processed_data_dir / "firms_ai_results.csv"
    output_csv_path = cfg.processed_data_dir / "gis_thermal_events.csv"
    output_html_path = PROJECT_ROOT / "reports" / "thermal_india_map.html"

    if not india_path.exists():
        logger.error(f"Missing required input dataset: {india_path}")
        print(f"ERROR: Missing input dataset: {india_path}")
        return 1

    if not ai_results_path.exists():
        logger.error(f"Missing required AI results dataset: {ai_results_path}")
        print(f"ERROR: Missing AI results dataset: {ai_results_path}")
        return 1

    try:
        # 1. Load detections
        india_df = pd.read_csv(india_path)
        logger.info(f"Loaded {len(india_df)} raw detection records from {india_path}")

        # 2. Assign cluster_id using existing clustering logic
        cluster_ids = cluster_detections(india_df, cfg.persistence)
        clustered_df = india_df.copy()
        clustered_df["cluster_id"] = cluster_ids
        logger.info(f"Assigned clusters to {len(clustered_df)} detections.")

        # 3. Load or compute persistence categories
        if persistence_path.exists():
            persistence_df = pd.read_csv(persistence_path)
        else:
            persistence_df = compute_cluster_features(india_df, cluster_ids, cfg.persistence)

        pers_subset = persistence_df[["cluster_id", "persistence_category"]].drop_duplicates()
        clustered_df = pd.merge(clustered_df, pers_subset, on="cluster_id", how="left")

        # 4. Load AI results
        ai_df = pd.read_csv(ai_results_path)
        logger.info(f"Loaded {len(ai_df)} cluster AI results from {ai_results_path}")

        # Columns to merge from AI results
        ai_cols = [
            "cluster_id",
            "anomaly_score",
            "anomaly_flag",
            "abnormality_level",
            "anomaly_characterization",
            "explanation",
            "contributing_factors",
        ]
        ai_df_subset = ai_df[[c for c in ai_cols if c in ai_df.columns]].drop_duplicates(subset=["cluster_id"])

        # 5. Merge detections with AI cluster results
        gis_df = pd.merge(clustered_df, ai_df_subset, on="cluster_id", how="left")

        # Fallback values if any unmerged
        gis_df["abnormality_level"] = gis_df["abnormality_level"].fillna("NORMAL")
        gis_df["anomaly_score"] = gis_df["anomaly_score"].fillna(0.0)
        gis_df["anomaly_flag"] = gis_df["anomaly_flag"].fillna(0).astype(int)
        gis_df["anomaly_characterization"] = gis_df["anomaly_characterization"].fillna("NORMAL_THERMAL_ACTIVITY")
        gis_df["explanation"] = gis_df["explanation"].fillna("Normal thermal detection")
        gis_df["contributing_factors"] = gis_df["contributing_factors"].fillna("none")

        if "detection_id" not in gis_df.columns:
            gis_df["detection_id"] = range(1, len(gis_df) + 1)

        # 6. Export NEW dataset: data/processed/gis_thermal_events.csv
        desired_order = [
            "detection_id",
            "latitude",
            "longitude",
            "acq_date",
            "cluster_id",
            "persistence_category",
            "anomaly_score",
            "anomaly_flag",
            "abnormality_level",
            "anomaly_characterization",
            "explanation",
            "contributing_factors",
            "bright_ti4",
            "bright_ti5",
            "frp",
            "confidence",
            "satellite",
        ]
        
        final_cols = [c for c in desired_order if c in gis_df.columns]
        extra_cols = [c for c in gis_df.columns if c not in final_cols]
        gis_df = gis_df[final_cols + extra_cols]

        gis_df.to_csv(output_csv_path, index=False)
        logger.info(f"Saved GIS thermal events dataset to {output_csv_path}")

        # 7. Generate Folium Interactive Map
        build_india_map(gis_df, output_html_path)

        # Summary statistics
        total_detections = len(gis_df)
        total_clusters = gis_df["cluster_id"].nunique()
        level_counts = gis_df["abnormality_level"].value_counts()
        normal_count = level_counts.get("NORMAL", 0)
        elevated_count = level_counts.get("ELEVATED", 0)
        high_count = level_counts.get("HIGH", 0)

        print("\n=== GIS Map Building Summary ===")
        print(f"Detections Mapped:       {total_detections}")
        print(f"Clusters Mapped:         {total_clusters}")
        print("\nEvents Breakdown:")
        print(f"  NORMAL:                {normal_count}")
        print(f"  ELEVATED:              {elevated_count}")
        print(f"  HIGH:                  {high_count}")
        print(f"\nGIS Dataset Saved:       {output_csv_path}")
        print(f"Interactive Map Saved:   {output_html_path}")
        print("================================\n")

    except Exception as exc:
        logger.exception("GIS map building failed")
        print(f"ERROR: GIS map building failed: {exc}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
