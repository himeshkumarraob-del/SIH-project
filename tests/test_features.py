"""
Tests for src/features/feature_engineering.py.

Uses synthetic persistence cluster data to verify deterministic transformation,
contrast indices, edge-case safety, and categorical encodings.
"""

from __future__ import annotations

import pytest
import pandas as pd
import numpy as np

from src.features.feature_engineering import (
    REQUIRED_PERSISTENCE_COLUMNS,
    PERSISTENCE_CATEGORY_ENCODING,
    extract_features,
)


def _make_synthetic_persistence_df() -> pd.DataFrame:
    data = [
        {
            "cluster_id": 0,
            "observation_count": 1,
            "active_days": 1,
            "first_detection": "2026-08-01",
            "last_detection": "2026-08-01",
            "duration_days": 1,
            "mean_bright_ti4": 329.54,
            "max_bright_ti4": 329.54,
            "mean_bright_ti5": 290.50,
            "max_bright_ti5": 290.50,
            "mean_frp": 3.14,
            "max_frp": 3.14,
            "mean_confidence": 2.0,
            "persistence_score": 0.0333,
            "persistence_category": "isolated",
        },
        {
            "cluster_id": 1,
            "observation_count": 8,
            "active_days": 2,
            "first_detection": "2026-08-01",
            "last_detection": "2026-08-02",
            "duration_days": 2,
            "mean_bright_ti4": 313.59,
            "max_bright_ti4": 333.41,
            "mean_bright_ti5": 279.76,
            "max_bright_ti5": 291.28,
            "mean_frp": 2.26,
            "max_frp": 5.27,
            "mean_confidence": 2.0,
            "persistence_score": 0.0667,
            "persistence_category": "short_lived_repeated",
        },
        {
            "cluster_id": 2,
            "observation_count": 25,
            "active_days": 10,
            "first_detection": "2026-08-01",
            "last_detection": "2026-08-25",
            "duration_days": 25,
            "mean_bright_ti4": 350.00,
            "max_bright_ti4": 375.50,
            "mean_bright_ti5": 295.00,
            "max_bright_ti5": 305.00,
            "mean_frp": 15.80,
            "max_frp": 45.00,
            "mean_confidence": 3.0,
            "persistence_score": 0.3333,
            "persistence_category": "persistent",
        },
    ]
    return pd.DataFrame(data)


def test_extract_features_columns_present():
    df = _make_synthetic_persistence_df()
    features = extract_features(df)

    expected_new_cols = [
        "bt_diff_mean",
        "bt_diff_max",
        "frp_mean_to_max_ratio",
        "detection_density",
        "active_day_ratio",
        "is_multi_day",
        "is_persistent_candidate",
        "persistence_category_code",
    ]

    for col in expected_new_cols:
        assert col in features.columns, f"Missing engineered feature column: {col}"

    assert "frp_per_observation" not in features.columns, (
        "frp_per_observation should not be present in engineered features"
    )


def test_thermal_brightness_differences():
    df = _make_synthetic_persistence_df()
    features = extract_features(df)

    # Row 0: mean_ti4(329.54) - mean_ti5(290.50) = 39.04
    assert pytest.approx(features.loc[0, "bt_diff_mean"], 0.01) == 39.04
    assert pytest.approx(features.loc[0, "bt_diff_max"], 0.01) == 39.04

    # Row 1: max_ti4(333.41) - max_ti5(291.28) = 42.13
    assert pytest.approx(features.loc[1, "bt_diff_max"], 0.01) == 42.13


def test_temporal_ratios_and_flags():
    df = _make_synthetic_persistence_df()
    features = extract_features(df)

    # Row 0: isolated (1 day, 1 obs)
    assert features.loc[0, "detection_density"] == 1.0
    assert features.loc[0, "active_day_ratio"] == 1.0
    assert features.loc[0, "is_multi_day"] == 0
    assert features.loc[0, "is_persistent_candidate"] == 0
    assert features.loc[0, "persistence_category_code"] == 0

    # Row 1: short_lived_repeated (2 days, 8 obs)
    assert features.loc[1, "detection_density"] == 4.0
    assert features.loc[1, "active_day_ratio"] == 1.0
    assert features.loc[1, "is_multi_day"] == 1
    assert features.loc[1, "is_persistent_candidate"] == 0
    assert features.loc[1, "persistence_category_code"] == 1

    # Row 2: persistent (25 duration, 10 active days, 25 obs)
    assert features.loc[2, "detection_density"] == 1.0
    assert pytest.approx(features.loc[2, "active_day_ratio"], 0.01) == 0.40
    assert features.loc[2, "is_multi_day"] == 1
    assert features.loc[2, "is_persistent_candidate"] == 1
    assert features.loc[2, "persistence_category_code"] == 2


def test_missing_required_column_raises_value_error():
    df = _make_synthetic_persistence_df().drop(columns=["mean_frp"])
    with pytest.raises(ValueError, match="Input DataFrame is missing required columns"):
        extract_features(df)


def test_empty_dataframe_handling():
    empty_df = pd.DataFrame(columns=REQUIRED_PERSISTENCE_COLUMNS)
    features = extract_features(empty_df)
    assert len(features) == 0
    assert "bt_diff_mean" in features.columns
