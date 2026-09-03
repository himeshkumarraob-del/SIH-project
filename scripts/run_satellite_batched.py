#!/usr/bin/env python3
"""
Batched Sentinel-2 pipeline runner.
Processes clusters in batches, writes intermediate results, shows progress.
Can be resumed from where it left off.
"""

import sys
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.satellite.sentinel2_search import Sentinel2Searcher
from src.satellite.inference import SatelliteLandUsePredictor
from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("scripts.run_satellite_batched")

PROGRESS_FILE = PROJECT_ROOT / "data" / "processed" / "satellite_progress.json"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "satellite_context.csv"


def load_progress():
    """Load previously completed cluster results."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {}


def save_progress(progress):
    """Save progress to disk."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2, default=str)


def process_cluster(searcher, predictor, cid, lat, lon, dt_str):
    """Process a single cluster through STAC search + CNN inference."""
    result = searcher.search_image_for_cluster(cid, lat, lon, dt_str)

    pred_class = "UNKNOWN"
    pred_conf = None

    if result.get("satellite_image_available") and "image_tensor" in result:
        tensor = result["image_tensor"]
        cnn_res = predictor.predict(tensor)
        pred_class = cnn_res["predicted_landcover_class"]
        pred_conf = cnn_res["prediction_confidence"]
        result["observation_status"] = (
            f"Satellite CNN prediction: {pred_class} (confidence: {pred_conf:.2f})"
        )

    return {
        "cluster_id": cid,
        "satellite_image_available": result["satellite_image_available"],
        "predicted_landcover_class": pred_class,
        "prediction_confidence": pred_conf,
        "image_date": result["image_date"],
        "cloud_cover": result["cloud_cover"],
        "image_source": result["image_source"],
        "observation_status": result["observation_status"],
        "satellite_item_id": result.get("satellite_item_id", "none"),
    }


def main():
    cfg = get_config()
    persistence_path = cfg.processed_data_dir / "firms_persistence.csv"
    gis_events_path = cfg.processed_data_dir / "gis_thermal_events.csv"

    if not persistence_path.exists():
        print(f"ERROR: Missing {persistence_path}")
        return 1

    pers_df = pd.read_csv(persistence_path)
    gis_df = pd.read_csv(gis_events_path) if gis_events_path.exists() else pd.DataFrame()

    # Compute centroids from gis_events
    if not gis_df.empty and "latitude" in gis_df.columns:
        centroids = gis_df.groupby("cluster_id").agg(
            latitude=("latitude", "mean"),
            longitude=("longitude", "mean"),
            acq_date=("acq_date", "min")
        ).reset_index()
    else:
        centroids = pd.DataFrame({
            "cluster_id": pers_df["cluster_id"],
            "latitude": 20.0,
            "longitude": 78.0,
            "acq_date": pers_df["first_detection"]
        })

    merged = pd.merge(pers_df[["cluster_id"]], centroids, on="cluster_id", how="left")

    # Initialize
    searcher = Sentinel2Searcher(temporal_window_days=5, max_cloud_cover_percent=30.0)
    checkpoint_path = cfg.models_dir / "satellite_landuse_efficientnet_b0.pth"
    predictor = SatelliteLandUsePredictor(checkpoint_path=checkpoint_path)

    print(f"Loaded {len(merged)} clusters")
    print(f"Checkpoint loaded: {predictor.is_trained}")
    print(f"Planetary Computer signing: {searcher._signing_available}")

    # Load existing progress
    progress = load_progress()
    completed_ids = set(progress.keys())
    print(f"Previously completed: {len(completed_ids)} clusters")

    # Filter to unprocessed clusters
    remaining = merged[~merged["cluster_id"].astype(str).isin(completed_ids)]
    total = len(merged)
    done = len(completed_ids)
    todo = len(remaining)

    print(f"Remaining: {todo} clusters to process")
    print(f"Starting batch processing...\n")

    start_time = time.time()
    batch_count = 0

    for idx, (_, row) in enumerate(remaining.iterrows()):
        cid = int(row["cluster_id"])
        lat = float(row["latitude"])
        lon = float(row["longitude"])
        dt_str = str(row["acq_date"])

        try:
            row_res = process_cluster(searcher, predictor, cid, lat, lon, dt_str)
            progress[str(cid)] = row_res
        except Exception as exc:
            progress[str(cid)] = {
                "cluster_id": cid,
                "satellite_image_available": False,
                "predicted_landcover_class": "UNKNOWN",
                "prediction_confidence": None,
                "image_date": dt_str,
                "cloud_cover": 100.0,
                "image_source": "Sentinel-2_L2A",
                "observation_status": f"Processing error: {str(exc)[:100]}",
                "satellite_item_id": "none",
            }

        done += 1
        batch_count += 1

        # Progress update every 10 clusters
        if batch_count % 10 == 0:
            elapsed = time.time() - start_time
            rate = batch_count / elapsed if elapsed > 0 else 0
            eta = (todo - batch_count) / rate if rate > 0 else 0
            avail = sum(1 for v in progress.values() if v.get("satellite_image_available"))
            print(f"  [{done}/{total}] {batch_count} processed, {avail} images available, "
                  f"rate: {rate:.1f}/s, ETA: {eta/60:.1f}min")

        # Save progress every 50 clusters
        if batch_count % 50 == 0:
            save_progress(progress)

    # Final save
    save_progress(progress)

    # Write final CSV
    results = list(progress.values())
    out_df = pd.DataFrame(results).sort_values("cluster_id").reset_index(drop=True)
    out_df.to_csv(OUTPUT_FILE, index=False)

    elapsed = time.time() - start_time
    avail_count = sum(1 for v in progress.values() if v.get("satellite_image_available"))
    cnn_count = sum(1 for v in progress.values() if v.get("predicted_landcover_class") != "UNKNOWN")
    cloud_blocked = sum(1 for v in progress.values()
                       if "obscured by cloud" in v.get("observation_status", ""))
    no_obs = sum(1 for v in progress.values()
                 if "No matching" in v.get("observation_status", ""))
    errors = sum(1 for v in progress.values()
                 if "error" in v.get("observation_status", "").lower())

    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"  Total clusters:        {total}")
    print(f"  Satellite available:   {avail_count}")
    print(f"  CNN predictions:       {cnn_count}")
    print(f"  Cloud-blocked:         {cloud_blocked}")
    print(f"  No observation:        {no_obs}")
    print(f"  Errors:                {errors}")
    print(f"  Time:                  {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"  Output:                {OUTPUT_FILE}")

    # Status breakdown
    status_counts = {}
    for v in progress.values():
        status = v.get("observation_status", "unknown")[:60]
        status_counts[status] = status_counts.get(status, 0) + 1
    print(f"\n  Observation status breakdown:")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"    {count:4d}  {status}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
