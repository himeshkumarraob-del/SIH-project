"""
Tests for src/models/risk_intelligence.py.

Verifies risk scoring, level assignments, reliability attenuation, boundary checks,
and dataset non-mutation.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import pandas as pd
import pytest

from src.models.risk_intelligence import RiskIntelligenceEngine

def _make_dummy_risk_record(
    abnormality="NORMAL",
    max_frp=1.5,
    active_days=1,
    pers_cat="isolated",
    max_ti4=310.0,
    bt_diff=20.0,
    fa_indicator="LOW"
) -> pd.DataFrame:
    return pd.DataFrame([{
        "cluster_id": 1,
        "abnormality_level": abnormality,
        "max_frp": max_frp,
        "active_days": active_days,
        "persistence_category": pers_cat,
        "max_bright_ti4": max_ti4,
        "bt_diff_max": bt_diff,
        "false_alarm_indicator": fa_indicator
    }])

def test_missing_required_columns_raises_error():
    engine = RiskIntelligenceEngine()
    df = pd.DataFrame([{"cluster_id": 1}])
    
    with pytest.raises(ValueError, match="Missing required columns"):
        engine.calculate_risk(df)

def test_normal_reliable_event():
    engine = RiskIntelligenceEngine()
    df = _make_dummy_risk_record(abnormality="NORMAL", max_frp=1.0, fa_indicator="LOW")
    res = engine.calculate_risk(df)
    
    assert res.iloc[0]["risk_level"] == "LOW"
    assert 0.0 <= res.iloc[0]["risk_score"] <= 100.0

def test_high_anomaly_strong_evidence():
    engine = RiskIntelligenceEngine()
    df = _make_dummy_risk_record(
        abnormality="HIGH",
        max_frp=30.0,
        active_days=5,
        pers_cat="persistent",
        max_ti4=360.0,
        bt_diff=55.0,
        fa_indicator="LOW"
    )
    res = engine.calculate_risk(df)
    
    assert res.iloc[0]["risk_level"] == "HIGH"
    assert res.iloc[0]["risk_score"] == 100.0
    assert "High statistical abnormality" in res.iloc[0]["risk_factors"]

def test_high_anomaly_weak_evidence_attenuation():
    engine = RiskIntelligenceEngine()
    # High anomaly but HIGH false alarm concern (0.50 multiplier)
    df = _make_dummy_risk_record(
        abnormality="HIGH",
        max_frp=6.0,
        active_days=1,
        pers_cat="isolated",
        max_ti4=338.0,
        bt_diff=36.0,
        fa_indicator="HIGH"
    )
    res = engine.calculate_risk(df)
    
    # Base score = 35 (HIGH) + 12 (FRP) + 3 (isolated) + 12 (TI4) = 62. 
    # Attenuated by 0.50 -> 31.0 -> MEDIUM risk
    assert res.iloc[0]["risk_level"] == "MEDIUM"
    assert res.iloc[0]["risk_score"] == 31.0
    assert "High false-alarm concern penalty applied" in res.iloc[0]["risk_factors"]

def test_persistent_event_increases_score():
    engine = RiskIntelligenceEngine()
    df_iso = _make_dummy_risk_record(pers_cat="isolated", active_days=1)
    df_pers = _make_dummy_risk_record(pers_cat="persistent", active_days=5)
    
    res_iso = engine.calculate_risk(df_iso)
    res_pers = engine.calculate_risk(df_pers)
    
    assert res_pers.iloc[0]["risk_score"] > res_iso.iloc[0]["risk_score"]

def test_high_false_alarm_concern_reduces_score():
    engine = RiskIntelligenceEngine()
    df_low_fa = _make_dummy_risk_record(fa_indicator="LOW")
    df_high_fa = _make_dummy_risk_record(fa_indicator="HIGH")
    
    res_low = engine.calculate_risk(df_low_fa)
    res_high = engine.calculate_risk(df_high_fa)
    
    assert res_high.iloc[0]["risk_score"] < res_low.iloc[0]["risk_score"]

def test_score_bounded_0_to_100():
    engine = RiskIntelligenceEngine()
    df_max = _make_dummy_risk_record(
        abnormality="HIGH", max_frp=100.0, active_days=10, 
        pers_cat="persistent", max_ti4=400.0, bt_diff=100.0, fa_indicator="LOW"
    )
    res = engine.calculate_risk(df_max)
    
    assert res.iloc[0]["risk_score"] == 100.0
    assert 0.0 <= res.iloc[0]["risk_score"] <= 100.0

def test_existing_ai_results_remain_unchanged():
    ai_file = Path("data/processed/firms_ai_results.csv")
    fa_file = Path("data/processed/firms_false_alarm.csv")
    
    assert ai_file.exists()
    assert fa_file.exists()
    
    mtime_ai_before = os.path.getmtime(ai_file)
    mtime_fa_before = os.path.getmtime(fa_file)
    
    # Run risk evaluation in memory
    engine = RiskIntelligenceEngine()
    df = _make_dummy_risk_record()
    engine.calculate_risk(df)
    
    mtime_ai_after = os.path.getmtime(ai_file)
    mtime_fa_after = os.path.getmtime(fa_file)
    
    assert mtime_ai_before == mtime_ai_after
    assert mtime_fa_before == mtime_fa_after
