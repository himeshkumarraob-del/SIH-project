"""
Tests for src/models/false_alarm_detector.py.

Verifies evidence-based false alarm indicator logic across reliable events,
weak single detections, persistent clusters, low confidence records,
and missing value handling.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.models.false_alarm_detector import FalseAlarmDetector

def _make_dummy_event(
    obs_count=1,
    active_days=1,
    duration_days=1,
    max_frp=1.5,
    mean_frp=1.5,
    max_ti4=310.0,
    bt_diff=20.0,
    confidence=2.0,
    pers_cat="isolated",
    abnormality="NORMAL"
) -> pd.DataFrame:
    return pd.DataFrame([{
        "cluster_id": 1,
        "observation_count": obs_count,
        "active_days": active_days,
        "duration_days": duration_days,
        "max_frp": max_frp,
        "mean_frp": mean_frp,
        "max_bright_ti4": max_ti4,
        "bt_diff_max": bt_diff,
        "mean_confidence": confidence,
        "persistence_category": pers_cat,
        "abnormality_level": abnormality
    }])

def test_missing_required_columns_raises_error():
    detector = FalseAlarmDetector()
    df = pd.DataFrame([{"cluster_id": 1}])  # Missing required features
    
    with pytest.raises(ValueError, match="Missing required columns"):
        detector.evaluate(df)

def test_weak_single_detection_high_false_alarm():
    detector = FalseAlarmDetector()
    # 1 observation, 1 day, low FRP, low confidence
    df = _make_dummy_event(
        obs_count=1,
        active_days=1,
        max_frp=1.0,
        confidence=1.0,
        max_ti4=310.0,
        bt_diff=15.0
    )
    res = detector.evaluate(df)
    
    assert res.iloc[0]["false_alarm_indicator"] == "HIGH"
    assert res.iloc[0]["detection_reliability"] == "LOW"
    assert "single point observation" in res.iloc[0]["false_alarm_reasons"]
    assert "low satellite confidence rating" in res.iloc[0]["false_alarm_reasons"]

def test_strong_reliable_anomaly_low_false_alarm():
    detector = FalseAlarmDetector()
    # High obs count, strong FRP, high confidence, high TI4
    df = _make_dummy_event(
        obs_count=10,
        active_days=4,
        duration_days=4,
        max_frp=30.0,
        confidence=3.0,
        max_ti4=350.0,
        bt_diff=50.0,
        pers_cat="persistent",
        abnormality="HIGH"
    )
    res = detector.evaluate(df)
    
    assert res.iloc[0]["false_alarm_indicator"] == "LOW"
    assert res.iloc[0]["detection_reliability"] == "HIGH"

def test_persistent_event_low_false_alarm():
    detector = FalseAlarmDetector()
    df = _make_dummy_event(
        obs_count=15,
        active_days=5,
        duration_days=5,
        max_frp=10.0,
        pers_cat="persistent"
    )
    res = detector.evaluate(df)
    
    assert res.iloc[0]["false_alarm_indicator"] == "LOW"
    assert res.iloc[0]["detection_reliability"] == "HIGH"

def test_low_confidence_event_triggers_reason():
    detector = FalseAlarmDetector()
    df = _make_dummy_event(confidence=1.0)
    res = detector.evaluate(df)
    
    assert "low satellite confidence rating" in res.iloc[0]["false_alarm_reasons"]

def test_normal_event_evaluation():
    detector = FalseAlarmDetector()
    df = _make_dummy_event(abnormality="NORMAL")
    res = detector.evaluate(df)
    
    assert res.iloc[0]["false_alarm_indicator"] in ["LOW", "MEDIUM", "HIGH"]
    assert res.iloc[0]["detection_reliability"] in ["LOW", "MEDIUM", "HIGH"]
