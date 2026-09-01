"""
Feature Engineering module for thermal-intelligence.

Transforms raw cluster summary records (from firms_persistence.csv) into
structured, model-ready feature vectors for downstream risk assessment and
anomaly modeling.

All features are mathematically derived from verified thermal, temporal, and
persistence metrics without synthetic ground-truth assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("features.feature_engineering")

REQUIRED_PERSISTENCE_COLUMNS: list[str] = [
    "cluster_id",
    "observation_count",
    "active_days",
    "first_detection",
    "last_detection",
    "duration_days",
    "mean_bright_ti4",
    "max_bright_ti4",
    "mean_bright_ti5",
    "max_bright_ti5",
    "mean_frp",
    "max_frp",
    "mean_confidence",
    "persistence_score",
    "persistence_category",
]

PERSISTENCE_CATEGORY_ENCODING: dict[str, int] = {
    "isolated": 0,
    "short_lived_repeated": 1,
    "persistent": 2,
}


@dataclass
class FeatureRunReport:
    input_records: int = 0
    output_records: int = 0
    total_features: int = 0
    feature_columns: list[str] = field(default_factory=list)
    category_breakdown: dict[str, int] = field(default_factory=dict)


def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derive statistical, temporal, and thermal contrast features from persistence data.

    This function is deterministic, reusable, and safe for both batch CSV processing
    and real-time inference record transformations.
    """
    missing = [col for col in REQUIRED_PERSISTENCE_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Input DataFrame is missing required columns: {missing}")

    feat = df.copy()

    # --- 1. Thermal Contrast & Spectral Separation ---
    # Difference between VIIRS I4 (mid-IR ~3.9µm) and I5 (thermal-IR ~11µm) channels.
    # Higher values indicate localized high-temperature active thermal sources.
    feat["bt_diff_mean"] = (feat["mean_bright_ti4"] - feat["mean_bright_ti5"]).round(3)
    feat["bt_diff_max"] = (feat["max_bright_ti4"] - feat["max_bright_ti5"]).round(3)

    # Ratio of peak to mean brightness & FRP (fire intensity dynamics)
    feat["frp_mean_to_max_ratio"] = np.where(
        feat["max_frp"] > 0,
        (feat["mean_frp"] / feat["max_frp"]).round(4),
        1.0,
    )

    # --- 2. Temporal Dynamics & Recurrence ---
    # Safe division: duration_days is at least 1 for valid clusters
    safe_duration = np.maximum(feat["duration_days"].to_numpy(dtype=float), 1.0)
    
    # Detection density: observations per day of cluster lifespan
    feat["detection_density"] = (feat["observation_count"] / safe_duration).round(4)

    # Active day ratio: proportion of days within lifespan where fire was observed
    feat["active_day_ratio"] = (feat["active_days"] / safe_duration).round(4)

    # Binary flags for temporal patterns
    feat["is_multi_day"] = (feat["active_days"] > 1).astype(int)
    feat["is_persistent_candidate"] = (
        feat["persistence_category"].str.strip().str.lower() == "persistent"
    ).astype(int)

    # --- 3. Categorical Encodings ---
    feat["persistence_category_code"] = (
        feat["persistence_category"]
        .str.strip()
        .str.lower()
        .map(PERSISTENCE_CATEGORY_ENCODING)
        .fillna(-1)
        .astype(int)
    )

    return feat


def run_feature_pipeline() -> tuple[pd.DataFrame, FeatureRunReport]:
    """
    Executes end-to-end feature engineering pipeline reading from firms_persistence.csv.
    """
    cfg = get_config()
    input_path = cfg.processed_data_dir / "firms_persistence.csv"

    if not input_path.exists():
        raise FileNotFoundError(
            f"Persistence dataset not found at {input_path}. "
            "Run persistence analysis first."
        )

    df = pd.read_csv(input_path)
    report = FeatureRunReport(input_records=len(df))

    features_df = extract_features(df)

    report.output_records = len(features_df)
    report.total_features = len(features_df.columns)
    report.feature_columns = list(features_df.columns)
    report.category_breakdown = (
        features_df["persistence_category"].value_counts().to_dict()
    )

    return features_df, report


def save_features_dataset(df: pd.DataFrame) -> Path:
    """Save engineered feature dataframe to data/processed/firms_features.csv."""
    cfg = get_config()
    out_path: Path = cfg.processed_data_dir / "firms_features.csv"
    df.to_csv(out_path, index=False)
    logger.info("Saved features dataset: %s (%d records, %d columns)", out_path, len(df), len(df.columns))
    return out_path


def print_feature_summary(report: FeatureRunReport) -> None:
    """Prints formatted summary report of the feature engineering run."""
    print("\n=== Feature Engineering Summary ===")
    print(f"Input records:          {report.input_records}")
    print(f"Output records:         {report.output_records}")
    print(f"Total columns:          {report.total_features}")
    print(f"Category Breakdown:")
    for cat, count in report.category_breakdown.items():
        print(f"  {cat:22s}: {count}")
    print("\nEngineered Feature Columns:")
    for col in report.feature_columns:
        print(f"  - {col}")
    print("===================================\n")
