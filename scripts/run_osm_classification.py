#!/usr/bin/env python3
"""
Batched OSM Classification Runner.

Uses BatchedOSMExtractor to group clusters into geographic grid cells,
make ONE Overpass query per cell (with local caching), and match
facilities locally.  Replaces the old per-cluster approach that made
1792 individual HTTP requests.

Usage:
    python scripts/run_osm_classification.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.osm.osm_context import BatchedOSMExtractor
from src.models.industrial_classifier import IndustrialClassifier
from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("scripts.run_osm_classification")


def main() -> int:
    cfg = get_config()
    ai_results_path = cfg.processed_data_dir / "firms_ai_results.csv"
    movement_path = cfg.processed_data_dir / "thermal_movement.csv"
    gis_events_path = cfg.processed_data_dir / "gis_thermal_events.csv"
    output_path = cfg.processed_data_dir / "firms_industrial_classification.csv"

    if not ai_results_path.exists():
        print(f"ERROR: Missing dataset: {ai_results_path}")
        return 1
    if not movement_path.exists():
        print(f"ERROR: Missing dataset: {movement_path}")
        return 1

    # Load data
    ai_df = pd.read_csv(ai_results_path)
    move_df = pd.read_csv(movement_path)
    gis_df = pd.read_csv(gis_events_path) if gis_events_path.exists() else pd.DataFrame()

    logger.info(f"Loaded {len(ai_df)} AI results and {len(move_df)} thermal movement records.")

    # Compute cluster centroids
    if not gis_df.empty and "latitude" in gis_df.columns:
        centroids = gis_df.groupby("cluster_id").agg(
            latitude=("latitude", "mean"), longitude=("longitude", "mean")
        ).reset_index()
    elif "start_latitude" in move_df.columns:
        centroids = move_df[["cluster_id", "start_latitude", "start_longitude"]].rename(
            columns={"start_latitude": "latitude", "start_longitude": "longitude"}
        )
    else:
        centroids = pd.DataFrame({"cluster_id": ai_df["cluster_id"], "latitude": 20.0, "longitude": 78.0})

    # Merge input streams
    merged = pd.merge(
        ai_df,
        move_df[["cluster_id", "movement_status", "total_movement_distance_km", "movement_direction"]],
        on="cluster_id", how="left",
    )
    merged = pd.merge(merged, centroids, on="cluster_id", how="left")

    total = len(merged)

    print(f"\n{'='*60}")
    print(f"  OSM Classification Pipeline -- {total} clusters")
    print(f"  Mode: BATCHED (geographic grid cells + local cache)")
    print(f"{'='*60}\n")

    # Initialize batched OSM extractor
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

    start_time = time.time()

    # Single batched extraction -- all clusters at once
    osm_df = osm_extractor.extract_context(merged[["latitude", "longitude"]].copy())

    merged["osm_facility_type"] = osm_df["osm_facility_type"].values
    merged["osm_facility_name"] = osm_df["osm_facility_name"].values
    merged["osm_distance_km"] = osm_df["osm_distance_km"].values
    merged["osm_query_status"] = osm_df["osm_query_status"].values
    merged["land_cover_class"] = "UNKNOWN"

    elapsed = time.time() - start_time
    print(f"  Batched OSM extraction done in {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"    Overpass queries made: {osm_extractor.total_queries}")
    print(f"    Cache hits: {osm_extractor.total_cache_hits}")

    # Merge satellite context
    sat_path = cfg.processed_data_dir / "satellite_context.csv"
    if sat_path.exists():
        sat_df = pd.read_csv(sat_path)
        merged = pd.merge(merged, sat_df, on="cluster_id", how="left")
        logger.info(f"Merged satellite context: {(merged['satellite_image_available'] == True).sum()} clusters with real satellite data.")

    # Run Industrial Classifier
    classifier = IndustrialClassifier(min_confidence_score=0.40)
    classified_df = classifier.classify_clusters(merged)

    # Export
    cols_export = [
        "cluster_id", "classification_label", "classification_score", "classification_rationale",
        "active_days", "persistence_category", "max_bright_ti4", "bt_diff_max", "max_frp",
        "movement_status", "total_movement_distance_km",
        "osm_facility_type", "osm_facility_name", "osm_distance_km", "osm_query_status",
        "land_cover_class",
        "satellite_image_available", "predicted_landcover_class", "prediction_confidence", "observation_status",
    ]
    export_df = classified_df[[c for c in cols_export if c in classified_df.columns]]
    export_df.to_csv(output_path, index=False)

    # Summary
    total_time = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"  CLASSIFICATION COMPLETE -- {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"{'='*60}")

    counts = export_df["classification_label"].value_counts()
    print(f"\nTotal Clusters: {total}")
    print(f"  Industrial-context:     {counts.get('Industrial-context thermal event', 0)}")
    print(f"  Agricultural-context:   {counts.get('Agricultural-context thermal event', 0)}")
    print(f"  Forest/Natural-context: {counts.get('Forest/Natural-context thermal event', 0)}")
    print(f"  Unknown/Insufficient:   {counts.get('Unknown / Insufficient Evidence', 0)}")

    osm_counts = export_df["osm_query_status"].value_counts()
    print(f"\nOSM Query Summary:")
    print(f"  Facilities found:       {osm_counts.get('found', 0)}")
    print(f"  No facility found:      {osm_counts.get('not_found', 0)}")
    print(f"  Unavailable (errors):   {osm_counts.get('unavailable', 0)}")
    print(f"  Timeouts:               {osm_counts.get('timeout', 0)}")
    print(f"  HTTP errors:            {osm_counts.get('http_error', 0)}")
    print(f"  Network errors:         {osm_counts.get('network_error', 0)}")
    print(f"  Parse errors:           {osm_counts.get('parse_error', 0)}")
    print(f"  Disabled (offline):     {osm_counts.get('disabled', 0)}")
    print(f"  Missing coords:         {osm_counts.get('missing_coords', 0)}")

    # Print specific cluster results
    print(f"\n{'='*60}")
    print(f"  TARGET CLUSTER RESULTS")
    print(f"{'='*60}")
    for cid in [1105, 38, 22, 76, 40]:
        row = export_df[export_df["cluster_id"] == cid]
        if not row.empty:
            r = row.iloc[0]
            print(f"\nCluster {cid}:")
            print(f"  lat/lon: {merged[merged['cluster_id']==cid]['latitude'].values[0]:.4f}, {merged[merged['cluster_id']==cid]['longitude'].values[0]:.4f}")
            print(f"  OSM query: {r['osm_query_status']}")
            print(f"  Facility: {r['osm_facility_type']} ({r.get('osm_facility_name', 'none')})")
            print(f"  Distance: {r['osm_distance_km']}")
            print(f"  Classification: {r['classification_label']} (score: {r['classification_score']})")

    # Guardrails
    prohibited = ["Confirmed Industrial Fire", "Confirmed Factory Fire", "Definite Explosion", "Confirmed Gas Leak"]
    violations = sum(export_df["classification_label"].str.contains("|".join(prohibited), regex=True, na=False))
    print(f"\nProhibited label violations: {violations}")
    print(f"Output: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
