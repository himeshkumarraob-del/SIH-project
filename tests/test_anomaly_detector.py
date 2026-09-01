"""
Tests for src/models/anomaly_detector.py.

Verifies model initialization, feature validation, preprocessing,
score/flag/level generation, and saving/loading functionality.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import pytest
from pathlib import Path
import tempfile

from src.models.anomaly_detector import ThermalAnomalyDetector, FEATURES

def _make_synthetic_features_df(n_samples=50, with_anomalies=True) -> pd.DataFrame:
    # Create mostly normal data
    np.random.seed(42)
    data = {
        "cluster_id": np.arange(n_samples),
        "max_bright_ti4": np.random.normal(310, 5, n_samples),
        "bt_diff_max": np.random.normal(20, 2, n_samples),
        "mean_frp": np.random.normal(2, 0.5, n_samples),
        "max_frp": np.random.normal(3, 1, n_samples),
        "observation_count": np.random.poisson(2, n_samples) + 1,
        "active_days": np.random.poisson(1, n_samples) + 1,
        "duration_days": np.random.poisson(1, n_samples) + 1,
        "detection_density": np.random.normal(1.5, 0.5, n_samples),
        "mean_confidence": np.random.normal(2, 0.2, n_samples),
        "frp_mean_to_max_ratio": np.random.normal(0.8, 0.1, n_samples),
    }
    
    # Inject a few extreme anomalies
    if with_anomalies:
        for i in range(3):
            data["max_bright_ti4"][i] = 360 + np.random.random() * 20
            data["bt_diff_max"][i] = 60 + np.random.random() * 20
            data["max_frp"][i] = 150 + np.random.random() * 50
            data["observation_count"][i] = 50 + np.random.randint(0, 50)
            data["active_days"][i] = 10 + np.random.randint(0, 5)
            
    return pd.DataFrame(data)

def test_missing_features_raises_error():
    df = _make_synthetic_features_df()
    df = df.drop(columns=["max_frp"])
    
    detector = ThermalAnomalyDetector()
    with pytest.raises(ValueError, match="Missing required features"):
        detector.fit(df)

def test_invalid_values_handled_safely():
    df = _make_synthetic_features_df(n_samples=20)
    
    # Introduce infs and nans
    df.loc[0, "max_bright_ti4"] = np.inf
    df.loc[1, "mean_frp"] = -np.inf
    df.loc[2, "bt_diff_max"] = np.nan
    
    detector = ThermalAnomalyDetector()
    detector.fit(df)
    results = detector.predict(df)
    
    assert len(results) == 20
    assert not results["anomaly_score"].isna().any()

def test_model_fitting_and_prediction():
    df = _make_synthetic_features_df(n_samples=100)
    
    detector = ThermalAnomalyDetector()
    detector.fit(df)
    assert detector.is_fitted
    
    results = detector.predict(df)
    
    # Check outputs
    assert "anomaly_score" in results.columns
    assert "anomaly_flag" in results.columns
    assert "abnormality_level" in results.columns
    
    # Flags should be 0 or 1
    assert set(results["anomaly_flag"].unique()).issubset({0, 1})
    
    # Levels should be valid
    assert set(results["abnormality_level"].unique()).issubset({"NORMAL", "ELEVATED", "HIGH"})

def test_unfitted_model_raises_error():
    df = _make_synthetic_features_df()
    detector = ThermalAnomalyDetector()
    
    with pytest.raises(RuntimeError, match="must be fitted"):
        detector.predict(df)

def test_save_and_load_model():
    df = _make_synthetic_features_df(n_samples=50)
    
    detector = ThermalAnomalyDetector(contamination=0.1)
    detector.fit(df)
    original_results = detector.predict(df)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        model_dir = Path(tmpdir)
        
        # Save
        detector.save(model_dir)
        assert (model_dir / "isolation_forest.joblib").exists()
        assert (model_dir / "robust_scaler.joblib").exists()
        
        # Load
        loaded_detector = ThermalAnomalyDetector.load(model_dir)
        assert loaded_detector.is_fitted
        
        # Predict with loaded model
        loaded_results = loaded_detector.predict(df)
        
        # Check equivalence
        pd.testing.assert_series_equal(original_results["anomaly_score"], loaded_results["anomaly_score"])
        pd.testing.assert_series_equal(original_results["anomaly_flag"], loaded_results["anomaly_flag"])
        pd.testing.assert_series_equal(original_results["abnormality_level"], loaded_results["abnormality_level"])
