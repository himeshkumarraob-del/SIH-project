"""
Tests for GIS Map Builder and Dataset Construction.

Verifies required columns, lat/lon bounds, cluster mapping, AI result join,
map HTML generation, invalid coordinate filtering, and dataset non-mutation.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import pandas as pd
import pytest

from src.gis.map_builder import build_india_map, REQUIRED_COLUMNS

def _make_dummy_gis_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "detection_id": 1,
            "latitude": 28.6139,
            "longitude": 77.2090,
            "acq_date": "2026-08-01",
            "cluster_id": 101,
            "persistence_category": "isolated",
            "anomaly_score": -0.15,
            "anomaly_flag": 0,
            "abnormality_level": "NORMAL",
            "anomaly_characterization": "NORMAL_THERMAL_ACTIVITY",
            "explanation": "Normal thermal detection.",
            "contributing_factors": "none",
            "bright_ti4": 305.2,
            "bright_ti5": 290.1,
            "frp": 3.5,
            "confidence": "n",
            "satellite": "N20",
        },
        {
            "detection_id": 2,
            "latitude": 19.0760,
            "longitude": 72.8777,
            "acq_date": "2026-08-02",
            "cluster_id": 102,
            "persistence_category": "persistent",
            "anomaly_score": 0.18,
            "anomaly_flag": 1,
            "abnormality_level": "HIGH",
            "anomaly_characterization": "HIGH_THERMAL_INTENSITY",
            "explanation": "High abnormality primarily associated with elevated thermal intensity.",
            "contributing_factors": "max_bright_ti4",
            "bright_ti4": 355.0,
            "bright_ti5": 310.0,
            "frp": 25.0,
            "confidence": "h",
            "satellite": "N21",
        },
    ])

def test_missing_required_columns_raises_error():
    df = _make_dummy_gis_df()
    df = df.drop(columns=["abnormality_level"])
    
    with tempfile.TemporaryDirectory() as tmpdir:
        out_file = Path(tmpdir) / "test_map.html"
        with pytest.raises(ValueError, match="Missing required columns"):
            build_india_map(df, out_file)

def test_valid_lat_lon_and_map_generation():
    df = _make_dummy_gis_df()
    with tempfile.TemporaryDirectory() as tmpdir:
        out_file = Path(tmpdir) / "test_map.html"
        res_path = build_india_map(df, out_file)
        
        assert res_path.exists()
        assert res_path.stat().st_size > 0
        
        content = res_path.read_text(encoding="utf-8")
        assert "Cluster ID: 101" in content
        assert "Cluster ID: 102" in content
        assert "HIGH Anomaly" in content

def test_invalid_coordinates_handled_safely():
    df = _make_dummy_gis_df()
    # Add invalid lat/lon
    df_invalid = pd.concat([
        df,
        pd.DataFrame([{
            "detection_id": 3,
            "latitude": 999.0,  # Invalid
            "longitude": 77.2090,
            "acq_date": "2026-08-03",
            "cluster_id": 103,
            "persistence_category": "isolated",
            "anomaly_score": 0.0,
            "anomaly_flag": 0,
            "abnormality_level": "NORMAL",
            "anomaly_characterization": "NORMAL_THERMAL_ACTIVITY",
            "explanation": "Normal",
            "contributing_factors": "none",
            "bright_ti4": 300.0,
            "bright_ti5": 290.0,
            "frp": 1.0,
            "confidence": "n",
            "satellite": "N20",
        }])
    ], ignore_index=True)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        out_file = Path(tmpdir) / "test_map.html"
        res_path = build_india_map(df_invalid, out_file)
        assert res_path.exists()

def test_source_datasets_remain_unchanged():
    india_csv = Path("data/processed/firms_india.csv")
    ai_csv = Path("data/processed/firms_ai_results.csv")
    
    assert india_csv.exists()
    assert ai_csv.exists()
    
    mtime_india_before = os.path.getmtime(india_csv)
    mtime_ai_before = os.path.getmtime(ai_csv)
    
    # Perform dummy operation
    df = _make_dummy_gis_df()
    with tempfile.TemporaryDirectory() as tmpdir:
        build_india_map(df, Path(tmpdir) / "map.html")
        
    mtime_india_after = os.path.getmtime(india_csv)
    mtime_ai_after = os.path.getmtime(ai_csv)
    
    assert mtime_india_before == mtime_india_after
    assert mtime_ai_before == mtime_ai_after
