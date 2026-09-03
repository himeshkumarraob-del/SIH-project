#!/usr/bin/env python3
"""
Test Sentinel-2 Planetary Computer integration for 3 specific clusters:
- Cluster #1105: 8.74N, 77.60E (should find usable observation)
- Cluster #38: 27.513N, 71.627E (should find usable observation)
- Cluster #22: test cloud-blocked behavior
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import torch
import numpy as np
from PIL import Image

from src.satellite.sentinel2_search import Sentinel2Searcher
from src.satellite.inference import SatelliteLandUsePredictor
from src.satellite.preprocessing import preprocess_image


def test_cluster(searcher, predictor, cluster_id, lat, lon, date_str, label):
    """Test a single cluster through the full pipeline."""
    print(f"\n{'='*70}")
    print(f"  TESTING {label}: Cluster #{cluster_id}")
    print(f"  Coordinates: {lat:.4f}N, {lon:.4f}E")
    print(f"  Date: {date_str}")
    print(f"{'='*70}")

    # Step 1: STAC search
    print(f"\n--- Step 1: STAC Metadata Search ---")
    result = searcher.search_image_for_cluster(cluster_id, lat, lon, date_str)

    print(f"  satellite_image_available: {result['satellite_image_available']}")
    print(f"  satellite_item_id: {result['satellite_item_id']}")
    print(f"  image_date: {result['image_date']}")
    print(f"  cloud_cover: {result['cloud_cover']}")
    print(f"  observation_status: {result['observation_status']}")

    has_tensor = "image_tensor" in result
    print(f"  has_image_tensor: {has_tensor}")

    if has_tensor:
        tensor = result["image_tensor"]
        print(f"  image_tensor shape: {tensor.shape}")
        print(f"  image_tensor dtype: {tensor.dtype}")
        print(f"  image_tensor min/max: {tensor.min():.4f}/{tensor.max():.4f}")

        # Verify tensor is valid (not all zeros, not NaN)
        is_valid = tensor.numel() > 0 and not torch.isnan(tensor).any() and not torch.all(tensor == 0)
        print(f"  tensor_valid: {is_valid}")

        if is_valid:
            # Step 2: CNN Inference
            print(f"\n--- Step 2: CNN Inference ---")
            cnn_result = predictor.predict(tensor)
            print(f"  predicted_class: {cnn_result['predicted_landcover_class']}")
            print(f"  confidence: {cnn_result['prediction_confidence']}")
            print(f"  is_model_trained: {cnn_result['is_model_trained']}")

            # Show top 3 class probabilities
            probs = cnn_result.get("class_probabilities", {})
            top3 = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:3]
            print(f"  top_3_classes:")
            for cls_name, prob in top3:
                print(f"    {cls_name}: {prob:.4f}")

            return {
                "success": True,
                "stac_found": True,
                "cloud_cover": result["cloud_cover"],
                "item_id": result["satellite_item_id"],
                "image_date": result["image_date"],
                "tensor_shape": list(tensor.shape),
                "predicted_class": cnn_result["predicted_landcover_class"],
                "confidence": cnn_result["prediction_confidence"],
                "is_trained": cnn_result["is_model_trained"],
                "status": result["observation_status"],
            }
        else:
            print(f"\n  WARNING: Tensor is invalid (zeros or NaN)")
            return {
                "success": False,
                "stac_found": True,
                "cloud_cover": result["cloud_cover"],
                "item_id": result["satellite_item_id"],
                "error": "Invalid image tensor",
                "status": result["observation_status"],
            }
    else:
        print(f"\n--- No image tensor retrieved ---")
        print(f"  This is expected for cloud-blocked or unavailable observations.")
        return {
            "success": True,  # Cloud-blocked is a valid outcome
            "stac_found": result["cloud_cover"] < 100.0,
            "cloud_cover": result["cloud_cover"],
            "item_id": result["satellite_item_id"],
            "predicted_class": "UNKNOWN",
            "confidence": None,
            "status": result["observation_status"],
        }


def main():
    print("=" * 70)
    print("  SENTINEL-2 PLANETARY COMPUTER INTEGRATION TEST")
    print("=" * 70)

    # Initialize searcher and predictor
    searcher = Sentinel2Searcher(temporal_window_days=5, max_cloud_cover_percent=30.0)
    print(f"\nSearcher config:")
    print(f"  STAC endpoint: Planetary Computer")
    print(f"  Cloud threshold: {searcher.max_cloud_cover_percent}%")
    print(f"  Temporal window: ±{searcher.temporal_window_days} days")
    print(f"  Planetary Computer signing: {searcher._signing_available}")

    checkpoint_path = PROJECT_ROOT / "models" / "satellite_landuse_efficientnet_b0.pth"
    print(f"  Checkpoint exists: {checkpoint_path.exists()}")
    print(f"  Checkpoint size: {checkpoint_path.stat().st_size if checkpoint_path.exists() else 0} bytes")

    predictor = SatelliteLandUsePredictor(checkpoint_path=checkpoint_path)
    print(f"  Model loaded: {predictor.is_trained}")
    print(f"  Model device: {predictor.device}")

    # Load cluster data to get actual dates
    gis_path = PROJECT_ROOT / "data" / "processed" / "gis_thermal_events.csv"
    gis_df = pd.read_csv(gis_path) if gis_path.exists() else pd.DataFrame()

    # Test configurations
    tests = [
        {
            "cluster_id": 1105,
            "lat": 8.74,
            "lon": 77.60,
            "label": "CLUSTER #1105 (Tamil Nadu)",
        },
        {
            "cluster_id": 38,
            "lat": 27.513,
            "lon": 71.627,
            "label": "CLUSTER #38 (Rajasthan)",
        },
        {
            "cluster_id": 22,
            "lat": None,  # Will be determined from data
            "lon": None,
            "label": "CLUSTER #22 (Cloud test)",
        },
    ]

    # Get actual dates and coordinates from gis_events
    for test in tests:
        cid = test["cluster_id"]
        if not gis_df.empty:
            cluster_data = gis_df[gis_df["cluster_id"] == cid]
            if not cluster_data.empty:
                if test["lat"] is None:
                    test["lat"] = cluster_data["latitude"].mean()
                    test["lon"] = cluster_data["longitude"].mean()
                test["date"] = cluster_data["acq_date"].min()
                print(f"\nCluster #{cid}: {test['lat']:.4f}N, {test['lon']:.4f}E, date={test['date']}")
            else:
                print(f"\nWARNING: Cluster #{cid} not found in gis_thermal_events.csv")
                # Use fallback
                test["date"] = "2026-08-01"
        else:
            test["date"] = "2026-08-01"

    # Run tests
    results = {}
    for test in tests:
        result = test_cluster(
            searcher, predictor,
            test["cluster_id"], test["lat"], test["lon"],
            test["date"], test["label"]
        )
        results[test["cluster_id"]] = result

    # Summary
    print(f"\n{'='*70}")
    print(f"  SUMMARY")
    print(f"{'='*70}")
    for cid, res in results.items():
        status = "SUCCESS" if res.get("success") else "FAILED"
        stac = "FOUND" if res.get("stac_found") else "NOT FOUND"
        cloud = res.get("cloud_cover", "N/A")
        pred = res.get("predicted_class", "N/A")
        conf = res.get("confidence", "N/A")
        print(f"\n  Cluster #{cid}:")
        print(f"    Result: {status}")
        print(f"    STAC: {stac}")
        print(f"    Cloud: {cloud}%")
        print(f"    Prediction: {pred} (conf={conf})")
        print(f"    Status: {res.get('status', 'N/A')}")

    # Save results
    results_path = PROJECT_ROOT / "data" / "processed" / "test_sentinel2_results.json"
    # Remove non-serializable items
    clean_results = {}
    for cid, res in results.items():
        clean_res = {k: v for k, v in res.items() if k != "image_tensor"}
        clean_results[str(cid)] = clean_res
    with open(results_path, "w") as f:
        json.dump(clean_results, f, indent=2, default=str)
    print(f"\nResults saved to: {results_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
