"""
Tests for src/models/anomaly_explainer.py.

Verifies characterization logic, missing column handling, and that
explanations match the configured thresholds correctly.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.models.anomaly_explainer import ThermalAnomalyExplainer

def _make_dummy_row(
    level="HIGH",
    max_ti4=300,
    bt_diff=20,
    max_frp=5,
    mean_frp=3,
    active_days=1,
    duration_days=1
) -> pd.DataFrame:
    return pd.DataFrame([{
        "abnormality_level": level,
        "max_bright_ti4": max_ti4,
        "bt_diff_max": bt_diff,
        "max_frp": max_frp,
        "mean_frp": mean_frp,
        "active_days": active_days,
        "duration_days": duration_days
    }])

def test_missing_required_columns_raises_error():
    explainer = ThermalAnomalyExplainer()
    df = pd.DataFrame([{"abnormality_level": "NORMAL"}])  # Missing features
    
    with pytest.raises(ValueError, match="Missing required columns for explanation"):
        explainer.explain(df)

def test_normal_records():
    explainer = ThermalAnomalyExplainer()
    df = _make_dummy_row(level="NORMAL")
    result = explainer.explain(df)
    
    assert result.iloc[0]["anomaly_characterization"] == "NORMAL_THERMAL_ACTIVITY"
    assert "normal statistical bounds" in result.iloc[0]["explanation"]
    assert result.iloc[0]["contributing_factors"] == "none"

def test_high_thermal_intensity():
    explainer = ThermalAnomalyExplainer()
    # TI4 > 340 triggers intensity
    df = _make_dummy_row(max_ti4=350, active_days=3)
    result = explainer.explain(df)
    
    assert result.iloc[0]["anomaly_characterization"] == "HIGH_THERMAL_INTENSITY"
    assert "elevated thermal intensity" in result.iloc[0]["explanation"]
    assert "max_bright_ti4" in result.iloc[0]["contributing_factors"]

def test_high_thermal_energy():
    explainer = ThermalAnomalyExplainer()
    # FRP > 15 triggers energy
    df = _make_dummy_row(max_frp=25)
    result = explainer.explain(df)
    
    assert result.iloc[0]["anomaly_characterization"] == "HIGH_THERMAL_ENERGY"
    assert "elevated thermal energy" in result.iloc[0]["explanation"]
    assert "max_frp" in result.iloc[0]["contributing_factors"]

def test_persistent_activity():
    explainer = ThermalAnomalyExplainer()
    # active_days >= 4 triggers persistence
    df = _make_dummy_row(active_days=6, duration_days=6)
    result = explainer.explain(df)
    
    assert result.iloc[0]["anomaly_characterization"] == "PERSISTENT_THERMAL_ACTIVITY"
    assert "persistent multi-day activity" in result.iloc[0]["explanation"]
    assert "active_days" in result.iloc[0]["contributing_factors"]

def test_multi_factor_anomaly():
    explainer = ThermalAnomalyExplainer()
    # Triggers both intensity and energy
    df = _make_dummy_row(max_ti4=360, max_frp=30)
    result = explainer.explain(df)
    
    assert result.iloc[0]["anomaly_characterization"] == "MULTI_FACTOR_ANOMALY"
    assert "elevated thermal intensity" in result.iloc[0]["explanation"]
    assert "elevated thermal energy" in result.iloc[0]["explanation"]
    assert "max_bright_ti4" in result.iloc[0]["contributing_factors"]
    assert "max_frp" in result.iloc[0]["contributing_factors"]

def test_short_lived_extreme_event():
    explainer = ThermalAnomalyExplainer()
    # High intensity but only 1 active day
    df = _make_dummy_row(max_ti4=360, active_days=1)
    result = explainer.explain(df)
    
    assert result.iloc[0]["anomaly_characterization"] == "SHORT_LIVED_EXTREME_EVENT"
