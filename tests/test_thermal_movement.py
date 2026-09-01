"""
Tests for src/gis/thermal_movement.py.

Verifies Haversine distance, bearing calculations, cardinal direction mappings,
movement classifications, confidence levels, single-day safeguards, and output schemas.
"""

from __future__ import annotations

import math
import pandas as pd
import pytest

from src.gis.thermal_movement import (
    ThermalMovementAnalyzer,
    haversine_distance_km,
    calculate_initial_bearing,
    bearing_to_compass_direction,
)

def _make_cluster_df(cluster_id: int, points: list[tuple[float, float, str]]) -> pd.DataFrame:
    rows = []
    for lat, lon, dt_str in points:
        rows.append({
            "cluster_id": cluster_id,
            "latitude": lat,
            "longitude": lon,
            "acq_date": dt_str.split()[0],
            "acq_time": "1200",
            "acquisition_datetime": dt_str
        })
    return pd.DataFrame(rows)

def test_haversine_distance_calculation():
    # Equator 1 degree longitude ~ 111.32 km
    dist = haversine_distance_km(0.0, 0.0, 0.0, 1.0)
    assert abs(dist - 111.32) < 1.0

def test_bearing_calculation_cardinal_directions():
    # North (lat increases)
    b_n = calculate_initial_bearing(10.0, 75.0, 11.0, 75.0)
    assert abs(b_n - 0.0) < 1.0 or abs(b_n - 360.0) < 1.0
    assert bearing_to_compass_direction(b_n) == "N"

    # East (lon increases)
    b_e = calculate_initial_bearing(10.0, 75.0, 10.0, 76.0)
    assert abs(b_e - 90.0) < 2.0
    assert bearing_to_compass_direction(b_e) == "E"

    # South (lat decreases)
    b_s = calculate_initial_bearing(11.0, 75.0, 10.0, 75.0)
    assert abs(b_s - 180.0) < 1.0
    assert bearing_to_compass_direction(b_s) == "S"

    # West (lon decreases)
    b_w = calculate_initial_bearing(10.0, 76.0, 10.0, 75.0)
    assert abs(b_w - 270.0) < 2.0
    assert bearing_to_compass_direction(b_w) == "W"

def test_known_northward_movement():
    analyzer = ThermalMovementAnalyzer()
    df = _make_cluster_df(101, [
        (20.0, 78.0, "2026-08-01 12:00:00"),
        (20.5, 78.0, "2026-08-02 12:00:00")
    ])
    res = analyzer.analyze_clusters(df)
    
    assert res.iloc[0]["movement_status"] == "MOVING"
    assert res.iloc[0]["movement_direction"] == "N"
    assert res.iloc[0]["total_movement_distance_km"] > 50.0

def test_known_eastward_movement():
    analyzer = ThermalMovementAnalyzer()
    df = _make_cluster_df(102, [
        (20.0, 78.0, "2026-08-01 12:00:00"),
        (20.0, 78.5, "2026-08-02 12:00:00")
    ])
    res = analyzer.analyze_clusters(df)
    
    assert res.iloc[0]["movement_status"] == "MOVING"
    assert res.iloc[0]["movement_direction"] == "E"

def test_known_southward_movement():
    analyzer = ThermalMovementAnalyzer()
    df = _make_cluster_df(103, [
        (20.5, 78.0, "2026-08-01 12:00:00"),
        (20.0, 78.0, "2026-08-02 12:00:00")
    ])
    res = analyzer.analyze_clusters(df)
    
    assert res.iloc[0]["movement_status"] == "MOVING"
    assert res.iloc[0]["movement_direction"] == "S"

def test_known_westward_movement():
    analyzer = ThermalMovementAnalyzer()
    df = _make_cluster_df(104, [
        (20.0, 78.5, "2026-08-01 12:00:00"),
        (20.0, 78.0, "2026-08-02 12:00:00")
    ])
    res = analyzer.analyze_clusters(df)
    
    assert res.iloc[0]["movement_status"] == "MOVING"
    assert res.iloc[0]["movement_direction"] == "W"

def test_stationary_cluster():
    analyzer = ThermalMovementAnalyzer(stationary_threshold_km=0.5)
    # Movement of ~0.01 km
    df = _make_cluster_df(105, [
        (20.0000, 78.0000, "2026-08-01 12:00:00"),
        (20.0001, 78.0001, "2026-08-02 12:00:00")
    ])
    res = analyzer.analyze_clusters(df)
    
    assert res.iloc[0]["movement_status"] == "STATIONARY"

def test_single_day_cluster_insufficient_data():
    analyzer = ThermalMovementAnalyzer()
    # 2 observations on the exact same date
    df = _make_cluster_df(106, [
        (20.0, 78.0, "2026-08-01 12:00:00"),
        (20.1, 78.1, "2026-08-01 14:00:00")
    ])
    res = analyzer.analyze_clusters(df)
    
    assert res.iloc[0]["movement_status"] == "INSUFFICIENT_DATA"
    assert res.iloc[0]["movement_direction"] == "INSUFFICIENT_DATA"
    assert res.iloc[0]["movement_confidence"] == "INSUFFICIENT_DATA"

def test_missing_coordinates_handled_safely():
    analyzer = ThermalMovementAnalyzer()
    df = pd.DataFrame([
        {"cluster_id": 107, "latitude": None, "longitude": 78.0, "acq_date": "2026-08-01"},
        {"cluster_id": 107, "latitude": 20.0, "longitude": 78.0, "acq_date": "2026-08-01"},
    ])
    res = analyzer.analyze_clusters(df)
    assert len(res) == 1
    assert res.iloc[0]["movement_status"] == "INSUFFICIENT_DATA"

def test_missing_timestamps_fallback():
    analyzer = ThermalMovementAnalyzer()
    df = pd.DataFrame([
        {"cluster_id": 108, "latitude": 20.0, "longitude": 78.0, "acq_date": "2026-08-01"},
        {"cluster_id": 108, "latitude": 20.5, "longitude": 78.0, "acq_date": "2026-08-02"},
    ])
    res = analyzer.analyze_clusters(df)
    assert res.iloc[0]["movement_status"] == "MOVING"
    assert res.iloc[0]["movement_direction"] == "N"

def test_movement_rate_and_output_schema():
    analyzer = ThermalMovementAnalyzer()
    df = _make_cluster_df(109, [
        (20.0, 78.0, "2026-08-01 12:00:00"),
        (21.0, 78.0, "2026-08-03 12:00:00")  # 2 days span, ~111 km -> rate ~55.6 km/day
    ])
    res = analyzer.analyze_clusters(df)
    
    expected_cols = [
        "cluster_id", "start_latitude", "start_longitude", "end_latitude", "end_longitude",
        "time_span_days", "total_movement_distance_km", "movement_rate_km_per_day",
        "movement_bearing_degrees", "movement_direction", "movement_confidence", "movement_status"
    ]
    for col in expected_cols:
        assert col in res.columns
        
    assert res.iloc[0]["time_span_days"] == 2.0
    assert abs(res.iloc[0]["movement_rate_km_per_day"] - 55.6) < 2.0
