#!/usr/bin/env python3
"""
CLI Script to run Sentinel-2 acquisition search & CNN land-use inference across FIRMS clusters.

1. Reads data/processed/firms_persistence.csv and data/processed/gis_thermal_events.csv.
2. Performs Sentinel-2 STAC metadata search per cluster location & date via Planetary Computer.
3. Downloads real Sentinel-2 RGB imagery when available.
4. Runs EfficientNet-B0 CNN land-use classification on retrieved images.
5. Outputs data/processed/satellite_context.csv.

Usage:
    python scripts/run_satellite_inference.py
"""

from __future__ import annotations

import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Dict

import pandas as pd
from src.satellite.sentinel2_search import Sentinel2Searcher
from src.satellite.inference import SatelliteLandUsePredictor
from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("scripts.run_satellite_inference")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Run Sentinel-2 acquisition search & CNN land-use inference across FIRMS clusters."
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from an existing satellite_context.csv: keep final search results "
             "(cloud-obscured / no-matching-observation) and reprocess everything else "
             "(no-network, timeouts, or earlier buggy black-patch CNN predictions)."
    )
    args = parser.parse_args()

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
        merged = merged.sort_values("cluster_id").reset_index(drop=True)
        rows_by_id = {int(r["cluster_id"]): r for _, r in merged.iterrows()}

        COLUMNS = [
            "cluster_id", "satellite_image_available", "predicted_landcover_class",
            "prediction_confidence", "image_date", "cloud_cover", "image_source",
            "observation_status", "satellite_item_id",
        ]

        # Use Planetary Computer STAC search (no credentials needed)
        searcher = Sentinel2Searcher(temporal_window_days=5, max_cloud_cover_percent=30.0)
        predictor = SatelliteLandUsePredictor(checkpoint_path=checkpoint_path)

        # --- Resume support -------------------------------------------------
        # Keep rows in a SETTLED state (genuine search/CNN outcomes from the
        # fixed pipeline): cloud-obscured, no matching observation, CNN
        # prediction, or an honest download failure. Only transient failures
        # (no network, timeouts, search errors, pending) are reprocessed.
        final_rows: Dict[int, dict] = {}
        if args.resume and output_path.exists():
            existing = pd.read_csv(output_path)
            transient_markers = (
                "no network connection",
                "timed out",
                "search error",
                "search pending",
                "observation search pending",
            )
            for _, row in existing.iterrows():
                status = str(row.get("observation_status", ""))
                if status and not any(m in status for m in transient_markers):
                    cid = int(row["cluster_id"])
                    final_rows[cid] = {c: row.get(c) for c in COLUMNS}
            logger.info(
                f"Resume: kept {len(final_rows)} settled results; "
                f"{len(existing) - len(final_rows)} transient rows to reprocess"
            )

        pending_ids = [cid for cid in sorted(rows_by_id) if cid not in final_rows]
        logger.info(f"Executing Sentinel-2 search and CNN inference via Planetary Computer...")
        logger.info(f"Clusters to process this run: {len(pending_ids)}")

        def _process_one(cid: int) -> Dict:
            row = rows_by_id[cid]
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            dt_str = str(row["acq_date"])

            # 1. Search metadata and download image if available
            stac_res = searcher.search_image_for_cluster(cid, lat, lon, dt_str)

            # 2. Run CNN inference ONLY if genuine imagery was retrieved
            if stac_res.get("satellite_image_available") and "image_tensor" in stac_res:
                # torch CPU forward is guarded so concurrent workers are safe
                with _predict_lock:
                    cnn_res = predictor.predict(stac_res["image_tensor"])
                pred_class = cnn_res["predicted_landcover_class"]
                pred_conf = cnn_res["prediction_confidence"]
                stac_res["observation_status"] = (
                    f"Satellite CNN prediction: {pred_class} (confidence: {pred_conf:.2f})"
                )
            else:
                # Strictly NO fabricated CNN predictions when satellite imagery is unavailable
                pred_class = "UNKNOWN"
                pred_conf = None

            return {
                "cluster_id": cid,
                "satellite_image_available": stac_res["satellite_image_available"],
                "predicted_landcover_class": pred_class,
                "prediction_confidence": pred_conf,
                "image_date": stac_res["image_date"],
                "cloud_cover": stac_res["cloud_cover"],
                "image_source": stac_res["image_source"],
                "observation_status": stac_res["observation_status"],
                "satellite_item_id": stac_res.get("satellite_item_id", "none"),
            }

        def _save() -> None:
            out_df = pd.DataFrame([final_rows[c] for c in sorted(final_rows)])
            out_df = out_df[COLUMNS]
            out_df.to_csv(output_path, index=False)

        _predict_lock = threading.Lock()
        processed = 0
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(_process_one, cid): cid for cid in pending_ids}
            for fut in as_completed(futures):
                cid = futures[fut]
                try:
                    final_rows[cid] = fut.result()
                except Exception as exc:
                    # Leave the row unset so a later --resume pass retries it.
                    logger.warning(f"Satellite processing failed for cluster {cid}: {exc}")
                    continue
                processed += 1
                if processed % 25 == 0:
                    _save()
                    logger.info(f"Satellite progress: {processed}/{len(pending_ids)} reprocessed")

        _save()
        logger.info(f"Saved satellite context results to {output_path}")

        out_df = pd.read_csv(output_path)
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
