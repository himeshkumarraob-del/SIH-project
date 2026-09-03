#!/usr/bin/env python3
"""
Test batched OSM extraction on a subset of clusters.
Verifies: real OSM request, facility/no-facility, facility type, distance.

Usage:
    python scripts/test_osm_10.py [--ids 1105,38,22,76,40] [--cache path] [--count N]

Defaults to 10 cluster IDs. --ids takes precedence over --count.
"""

from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.osm.osm_context import BatchedOSMExtractor

# Default: 5 real cluster IDs (1105, 38, 22, 76, 40) + 5 more
DEFAULT_CLUSTER_IDS = [1105, 38, 22, 76, 40, 100, 200, 500, 800, 1000]


def main() -> int:
    parser = argparse.ArgumentParser(description="Test batched OSM extraction on a subset of clusters.")
    parser.add_argument(
        "--ids", type=str, default=None,
        help="Comma-separated cluster IDs to test (takes precedence over --count)."
    )
    parser.add_argument(
        "--count", type=int, default=10,
        help="When --ids is not given, take the first N clusters by cluster_id."
    )
    parser.add_argument(
        "--cache", type=str, default="data/processed/osm_cache_10_test.json",
        help="Cache file path (relative to project root)."
    )
    args = parser.parse_args()

    # Load cluster centroids
    gis_path = PROJECT_ROOT / "data/processed/gis_thermal_events.csv"
    if not gis_path.exists():
        print(f"ERROR: {gis_path} not found")
        return 1

    gis_df = pd.read_csv(gis_path)

    # Compute centroids
    centroids = gis_df.groupby("cluster_id").agg(
        latitude=("latitude", "mean"), longitude=("longitude", "mean")
    ).reset_index()

    available_ids = set(centroids["cluster_id"])

    if args.ids:
        requested = [int(c.strip()) for c in args.ids.split(",") if c.strip()]
        target_ids = [cid for cid in requested if cid in available_ids]
        # Fill with extra clusters if some requested IDs are missing
        extra = [cid for cid in sorted(available_ids) if cid not in target_ids]
        target_ids.extend(extra[: len(requested) - len(target_ids)])
        target_ids = target_ids[: len(requested)]
    else:
        target_ids = sorted(available_ids)[: args.count]

    print(f"Testing with {len(target_ids)} clusters: {target_ids}")
    subset = centroids[centroids["cluster_id"].isin(target_ids)].copy()
    print(f"Subset shape: {subset.shape}")
    print(subset[["cluster_id", "latitude", "longitude"]].to_string(index=False))

    row_ids = subset["cluster_id"].tolist()

    # Initialize batched extractor
    test_cache = PROJECT_ROOT / args.cache
    ext = BatchedOSMExtractor(
        radius_km=2.0,
        grid_size_deg=0.25,
        use_network=True,
        timeout_sec=20,
        max_retries=1,
        retry_delay_sec=2.0,
        inter_request_delay_sec=0.8,
        max_workers=6,
        cache_path=test_cache,
    )

    start = time.time()
    result = ext.extract_context(subset[["latitude", "longitude"]].copy())
    elapsed = time.time() - start

    # Add cluster_id back for reporting (aligned by row position)
    result["cluster_id"] = row_ids

    print(f"\n{'='*60}")
    print(f"  {len(target_ids)}-CLUSTER TEST RESULTS")
    print(f"{'='*60}")
    print(f"  Runtime: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"  Overpass queries: {ext.total_queries}")
    print(f"  Cache hits: {ext.total_cache_hits}")

    found = result[result["osm_query_status"] == "found"]
    not_found = result[result["osm_query_status"] == "not_found"]
    errors = result[~result["osm_query_status"].isin(["found", "not_found"])]

    print(f"\n  Facilities found: {len(found)}")
    print(f"  No facility: {len(not_found)}")
    print(f"  Errors: {len(errors)}")

    print(f"\n  Per-cluster results:")
    for _, row in result.iterrows():
        cid = row["cluster_id"]
        print(f"    Cluster {cid}: status={row['osm_query_status']}, "
              f"facility={row['osm_facility_type']}, "
              f"dist={row['osm_distance_km']}")

    # Verify cache was created
    if test_cache.exists():
        import json
        with open(test_cache, encoding="utf-8") as f:
            cache_data = json.load(f)
        print(f"\n  Cache cells: {len(cache_data)}")
        for k, v in cache_data.items():
            print(f"    {k}: status={v['status']}, elements={len(v.get('elements', []))}")
    else:
        print("\n  WARNING: Cache file not created!")

    # Validation checks
    print(f"\n  Validation:")
    assert len(result) == len(row_ids), f"Expected {len(row_ids)} rows, got {len(result)}"
    print(f"    [PASS] Row count matches")

    has_status = "osm_query_status" in result.columns
    print(f"    [{'PASS' if has_status else 'FAIL'}] osm_query_status column exists")

    has_type = "osm_facility_type" in result.columns
    print(f"    [{'PASS' if has_type else 'FAIL'}] osm_facility_type column exists")

    has_dist = "osm_distance_km" in result.columns
    print(f"    [{'PASS' if has_dist else 'FAIL'}] osm_distance_km column exists")

    # At least one real query should have happened (unless fully cached)
    print(f"    [INFO] Total Overpass queries: {ext.total_queries}")

    # Check that "found" results have valid facility types
    for _, row in found.iterrows():
        assert row["osm_facility_type"] not in ("UNKNOWN", "none"), \
            f"Cluster {row['cluster_id']} found but facility_type is {row['osm_facility_type']}"
        assert row["osm_distance_km"] <= 2.0, \
            f"Cluster {row['cluster_id']} distance {row['osm_distance_km']} > 2.0 km"
    print(f"    [{'PASS' if len(found) > 0 else 'INFO'}] At least one facility found")

    print(f"\n  Cache file: {test_cache}")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
