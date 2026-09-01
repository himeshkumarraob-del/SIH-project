"""Tests for src/persistence/persistence_analysis.py.

Uses synthetic FIRMS-shaped data only -- never touches the real
data/processed/firms_india.csv.
"""

from __future__ import annotations

import os

import pandas as pd

os.environ.setdefault("FIRMS_MAP_KEY", "test_key_1234567890")

from src.config import PersistenceConfig  # noqa: E402
from src.persistence.persistence_analysis import (  # noqa: E402
    cluster_detections,
    compute_cluster_features,
    _haversine_km,
)

CFG = PersistenceConfig(
    spatial_distance_km=1.0,
    temporal_window_days=3,
    persistent_min_active_days=5,
    repeated_min_active_days=2,
)

COLS = ["latitude", "longitude", "acq_date", "bright_ti4", "bright_ti5", "frp", "confidence"]


def _row(lat, lon, date, bti4=320.0, bti5=290.0, frp=5.0, conf="n"):
    return [lat, lon, date, bti4, bti5, frp, conf]


def test_haversine_known_distance():
    # Roughly 111km per degree of latitude at the equator.
    d = _haversine_km(0.0, 0.0, 1.0, 0.0)
    assert 110 < d < 112


def test_isolated_detection_gets_its_own_cluster():
    df = pd.DataFrame(
        [_row(28.6139, 77.2090, "2026-08-05")],  # single detection, no follow-up
        columns=COLS,
    )
    cluster_ids = cluster_detections(df, CFG)
    features = compute_cluster_features(df, cluster_ids, CFG)
    assert len(features) == 1
    assert features.iloc[0]["persistence_category"] == "isolated"
    assert features.iloc[0]["active_days"] == 1


def test_persistent_cluster_spans_many_active_days():
    # Same location (within spatial_distance_km), chained every 2 days
    # across the full dataset window -> should be "persistent".
    dates = [f"2026-08-{d:02d}" for d in [1, 3, 5, 7, 9, 11, 13, 15]]
    rows = [_row(19.0760 + 0.0001 * i, 72.8777, d) for i, d in enumerate(dates)]
    df = pd.DataFrame(rows, columns=COLS)
    cluster_ids = cluster_detections(df, CFG)
    features = compute_cluster_features(df, cluster_ids, CFG)
    assert len(features) == 1  # all chained into one cluster
    row = features.iloc[0]
    assert row["active_days"] == 8
    assert row["persistence_category"] == "persistent"
    assert row["observation_count"] == 8


def test_short_lived_repeated_cluster():
    # 3 active days, close together -> short_lived_repeated (>=2, <5 active days).
    dates = ["2026-08-10", "2026-08-11", "2026-08-13"]
    rows = [_row(22.5726, 88.3639, d) for d in dates]
    df = pd.DataFrame(rows, columns=COLS)
    cluster_ids = cluster_detections(df, CFG)
    features = compute_cluster_features(df, cluster_ids, CFG)
    assert len(features) == 1
    assert features.iloc[0]["persistence_category"] == "short_lived_repeated"


def test_spatially_distant_points_form_separate_clusters_even_if_same_day():
    df = pd.DataFrame(
        [
            _row(28.6139, 77.2090, "2026-08-05"),   # Delhi
            _row(19.0760, 72.8777, "2026-08-05"),   # Mumbai -- far from Delhi
        ],
        columns=COLS,
    )
    cluster_ids = cluster_detections(df, CFG)
    assert len(set(cluster_ids)) == 2


def test_temporally_distant_points_form_separate_clusters_even_if_close():
    df = pd.DataFrame(
        [
            _row(28.6139, 77.2090, "2026-08-01"),
            _row(28.6140, 77.2091, "2026-08-20"),  # same spot, 19 days later -> beyond window
        ],
        columns=COLS,
    )
    cluster_ids = cluster_detections(df, CFG)
    assert len(set(cluster_ids)) == 2


def test_original_feature_columns_present():
    df = pd.DataFrame(
        [_row(28.6139, 77.2090, "2026-08-05"), _row(28.6140, 77.2091, "2026-08-07")],
        columns=COLS,
    )
    cluster_ids = cluster_detections(df, CFG)
    features = compute_cluster_features(df, cluster_ids, CFG)
    expected_cols = {
        "cluster_id", "observation_count", "active_days", "first_detection",
        "last_detection", "duration_days", "mean_bright_ti4", "max_bright_ti4",
        "mean_bright_ti5", "max_bright_ti5", "mean_frp", "max_frp",
        "mean_confidence", "persistence_score", "persistence_category",
    }
    assert expected_cols.issubset(set(features.columns))