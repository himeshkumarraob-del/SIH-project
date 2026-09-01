#!/usr/bin/env python3
"""
CLI Script to run Sentinel-2 acquisition search & CNN land-use inference across FIRMS clusters.

1. Reads data/processed/firms_persistence.csv and data/processed/gis_thermal_events.csv.
2. Performs Sentinel-2 STAC metadata search per cluster location & date.
3. Extracts image patches and runs EfficientNet-B0 CNN land-use classification.
4. Outputs data/processed/satellite_context.csv.

Usage:
    python scripts/run_satellite_inference.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.satellite.sentinel2_search import Sentinel2Searcher
from src.satellite.patch_extractor import PatchExtractor
from src.satellite.inference import SatelliteLandUsePredictor
from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("scripts.run_satellite_inference")

def main() -> int:
    cfg = get_config()
    persistence_path = cfg.processed_data_dir / "firms_persistence.csv"
    gis_events_path = cfg.processed_data_dir / "gis_thermal_events.csv"
    output_path = cfg.processed_data_dir / "satellite_context.csv"
    checkpoint_path = cfg.models_dir / "satellite_landuse_efficientnet_b0.pth"

    if not persistence_path.exists():
        logger.error(f"Missing required dataset: {persistence_path}")
        print(f"ERROR: Missing required dataset: {persistence_path}")
        return 1

    try:
        pers_df = pd.read_csv(persistence_path)
        gis_df = pd.read_csv(gis_events_path) if gis_events_path.exists() else pd.DataFrame()
        logger.info(f"Loaded {len(pers_df)} clusters for satellite context analysis.")

        # Compute cluster centroids
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

        searcher = Sentinel2Searcher(temporal_window_days=3, max_cloud_cover_percent=20.0)
        patch_extractor = PatchExtractor(patch_size=64)
        predictor = SatelliteLandUsePredictor(checkpoint_path=checkpoint_path)

        results = []
        logger.info("Executing Sentinel-2 search and CNN inference...")

        for _, row in merged.iterrows():
            cid = int(row["cluster_id"])
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            dt_str = str(row["acq_date"])

            # 1. Search metadata
            stac_res = searcher.search_image_for_cluster(cid, lat, lon, dt_str)

            # 2. Extract patch & run CNN inference ONLY if genuine imagery was retrieved
            if stac_res["image_available"] and "image_file_path" in stac_res and Path(stac_res["image_file_path"]).exists():
                patch_tensor = patch_extractor.extract_patch_tensor(image_path=Path(stac_res["image_file_path"]))
                cnn_res = predictor.predict(patch_tensor)
                pred_class = cnn_res["predicted_landcover_class"]
                pred_conf = cnn_res["prediction_confidence"]
            else:
                # Strictly NO fabricated CNN predictions when satellite imagery is unavailable/obscured
                pred_class = "UNKNOWN"
                pred_conf = None

            row_res = {
                "cluster_id": cid,
                "satellite_image_available": stac_res["image_available"],
                "predicted_landcover_class": pred_class,
                "prediction_confidence": pred_conf,
                "image_date": stac_res["image_date"],
                "cloud_cover": stac_res["cloud_cover"],
                "image_source": stac_res["image_source"],
                "observation_status": stac_res["observation_status"]
            }
            results.append(row_res)

        out_df = pd.DataFrame(results).sort_values("cluster_id").reset_index(drop=True)
        out_df.to_csv(output_path, index=False)
        logger.info(f"Saved satellite context results to {output_path}")

        total = len(out_df)
        avail_count = sum(out_df["satellite_image_available"])
        class_counts = out_df["predicted_landcover_class"].value_counts()

        print("\n=== Satellite Context & CNN Inference Summary ===")
        print(f"Total Clusters Analyzed:            {total}")
        print(f"Satellite Imagery Available:        {avail_count}")
        print(f"Satellite Imagery Obscured/Unavail: {total - avail_count}")
        print("\nPredicted Satellite Land-Cover Classes:")
        for cls_name, count in class_counts.items():
            print(f"  {cls_name}: {count}")

        print(f"\nOutput File Saved:                  {output_path}")
        print("==================================================\n")

    except Exception as exc:
        logger.exception("Satellite inference execution failed")
        print(f"ERROR: Satellite inference failed: {exc}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
