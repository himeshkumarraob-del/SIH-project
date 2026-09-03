#!/usr/bin/env python3
"""
CLI entry point for Industrial Fire & Thermal Source Classification.

1. Reads data/processed/firms_ai_results.csv, data/processed/thermal_movement.csv,
   and data/processed/gis_thermal_events.csv.
2. Extracts OSM industrial proximity context (with clean offline/unknown fallback).
3. Applies IndustrialClassifier evidence fusion engine.
4. Exports data/processed/firms_industrial_classification.csv.

Usage:
    python scripts/classify_industrial_fires.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.osm.osm_context import BatchedOSMExtractor
from src.models.industrial_classifier import IndustrialClassifier
from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("scripts.classify_industrial_fires")

def main() -> int:
    cfg = get_config()
    ai_results_path = cfg.processed_data_dir / "firms_ai_results.csv"
    movement_path = cfg.processed_data_dir / "thermal_movement.csv"
    gis_events_path = cfg.processed_data_dir / "gis_thermal_events.csv"
    output_path = cfg.processed_data_dir / "firms_industrial_classification.csv"

    if not ai_results_path.exists():
        logger.error(f"Missing required dataset: {ai_results_path}")
        print(f"ERROR: Missing dataset: {ai_results_path}")
        return 1

    if not movement_path.exists():
        logger.error(f"Missing required dataset: {movement_path}")
        print(f"ERROR: Missing dataset: {movement_path}")
        return 1

    try:
        ai_df = pd.read_csv(ai_results_path)
        move_df = pd.read_csv(movement_path)
        gis_df = pd.read_csv(gis_events_path) if gis_events_path.exists() else pd.DataFrame()

        logger.info(f"Loaded {len(ai_df)} AI results and {len(move_df)} thermal movement records.")

        # Compute cluster centroids (mean latitude and longitude per cluster) from gis_df or ai_df
        if not gis_df.empty and "latitude" in gis_df.columns:
            centroids = gis_df.groupby("cluster_id").agg(
                latitude=("latitude", "mean"),
                longitude=("longitude", "mean")
            ).reset_index()
        elif "start_latitude" in move_df.columns:
            centroids = move_df[["cluster_id", "start_latitude", "start_longitude"]].rename(
                columns={"start_latitude": "latitude", "start_longitude": "longitude"}
            )
        else:
            centroids = pd.DataFrame({"cluster_id": ai_df["cluster_id"], "latitude": 20.0, "longitude": 78.0})

        # Merge input streams into cluster-level table
        merged = pd.merge(ai_df, move_df[["cluster_id", "movement_status", "total_movement_distance_km", "movement_direction"]], on="cluster_id", how="left")
        merged = pd.merge(merged, centroids, on="cluster_id", how="left")

        # 1. Extract OSM Context (batched Overpass queries with caching)
        osm_extractor = BatchedOSMExtractor(
            radius_km=2.0,
            grid_size_deg=0.25,
            use_network=True,
            timeout_sec=20,
            max_retries=1,
            retry_delay_sec=2.0,
            inter_request_delay_sec=0.8,
            max_workers=6,
            cache_path=cfg.processed_data_dir / "osm_cache.json",
        )
        logger.info("Extracting OSM industrial proximity context (batched Overpass queries)...")
        osm_df = osm_extractor.extract_context(merged[["latitude", "longitude"]])
        
        merged["osm_facility_type"] = osm_df["osm_facility_type"]
        merged["osm_facility_name"] = osm_df["osm_facility_name"]
        merged["osm_distance_km"] = osm_df["osm_distance_km"]
        merged["osm_query_status"] = osm_df["osm_query_status"]
        merged["land_cover_class"] = "UNKNOWN" # Explicit UNKNOWN for missing land-cover

        # Merge satellite context (Sentinel-2 CNN predictions)
        sat_path = cfg.processed_data_dir / "satellite_context.csv"
        if sat_path.exists():
            sat_df = pd.read_csv(sat_path)
            merged = pd.merge(merged, sat_df, on="cluster_id", how="left")
            logger.info(f"Merged satellite context: {(merged['satellite_image_available'] == True).sum()} clusters with real satellite data.")
        else:
            logger.warning(f"satellite_context.csv not found, proceeding without satellite evidence.")

        # 2. Run Industrial Classifier
        classifier = IndustrialClassifier(min_confidence_score=0.40)
        logger.info("Running Industrial Classifier evidence fusion engine...")
        classified_df = classifier.classify_clusters(merged)

        # Save results
        cols_export = [
            "cluster_id", "classification_label", "classification_score", "classification_rationale",
            "active_days", "persistence_category", "max_bright_ti4", "bt_diff_max", "max_frp",
            "movement_status", "total_movement_distance_km",
            "osm_facility_type", "osm_facility_name", "osm_distance_km", "osm_query_status",
            "land_cover_class",
            "satellite_image_available", "predicted_landcover_class", "prediction_confidence", "observation_status"
        ]
        export_df = classified_df[[c for c in cols_export if c in classified_df.columns]]
        export_df.to_csv(output_path, index=False)
        logger.info(f"Saved industrial fire classification results to {output_path}")

        total_clusters = len(export_df)
        counts = export_df["classification_label"].value_counts()

        print("\n=== Industrial Fire & Thermal Source Classification Summary ===")
        print(f"Total Clusters Processed:   {total_clusters}")
        print("\nClassification Category Breakdown:")
        print(f"  Industrial-context thermal event:     {counts.get('Industrial-context thermal event', 0)}")
        print(f"  Agricultural-context thermal event:   {counts.get('Agricultural-context thermal event', 0)}")
        print(f"  Forest/Natural-context thermal event: {counts.get('Forest/Natural-context thermal event', 0)}")
        print(f"  Unknown / Insufficient Evidence:     {counts.get('Unknown / Insufficient Evidence', 0)}")

        print("\n=== Top 10 Industrial-Context Events ===")
        ind_events = export_df[export_df["classification_label"] == "Industrial-context thermal event"]
        if not ind_events.empty:
            top10 = ind_events.sort_values(by="classification_score", ascending=False).head(10)
            show_cols = ["cluster_id", "classification_score", "active_days", "bt_diff_max", "movement_status", "osm_facility_type"]
            print(top10[[c for c in show_cols if c in top10.columns]].to_string(index=False))
        else:
            print("  (No events met the full industrial evidence threshold)")

        # OSM Query Summary
        if "osm_query_status" in export_df.columns:
            osm_counts = export_df["osm_query_status"].value_counts()
            print("\n=== OSM Query Summary ===")
            print(f"  Facilities found:        {osm_counts.get('found', 0)}")
            print(f"  No facility found:       {osm_counts.get('not_found', 0)}")
            print(f"  Unavailable (errors):    {osm_counts.get('unavailable', 0)}")
            print(f"  Query disabled:          {osm_counts.get('disabled', 0)}")
            print(f"  Timeout:                 {osm_counts.get('timeout', 0)}")
            print(f"  HTTP errors:             {osm_counts.get('http_error', 0)}")
            print(f"  Network errors:          {osm_counts.get('network_error', 0)}")
            print(f"  Parse errors:            {osm_counts.get('parse_error', 0)}")
            print(f"  Missing coordinates:     {osm_counts.get('missing_coords', 0)}")

        print("\n=== Scientific Guardrails Audit ===")
        prohibited = ["Confirmed Industrial Fire", "Confirmed Factory Fire", "Definite Explosion", "Confirmed Gas Leak"]
        violations = sum(export_df["classification_label"].str.contains("|".join(prohibited), regex=True, na=False))
        print(f"Prohibited label violations found: {violations}")

        print(f"\nOutput File Saved:          {output_path}")
        print("=============================================================\n")

    except Exception as exc:
        logger.exception("Industrial classification failed")
        print(f"ERROR: Industrial classification failed: {exc}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
