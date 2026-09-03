"""
Unit Tests for FastAPI REST API backend (backend/main.py).

Verifies endpoints, pagination, filtering parameters, response schemas, and 404 handling.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from src.config import get_config

client = TestClient(app)


def _movement_csv() -> pd.DataFrame:
    path = get_config().processed_data_dir / "thermal_movement.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _pick_cluster_id(mov_df: pd.DataFrame, col: str, value: str) -> int:
    """Return the first cluster_id in the movement CSV matching a column value."""
    if mov_df.empty or col not in mov_df.columns:
        return -1
    sub = mov_df[mov_df[col].astype(str) == value]
    if sub.empty:
        return -1
    return int(sub.iloc[0]["cluster_id"])

def test_api_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "total_records_loaded" in data

def test_api_statistics_endpoint():
    response = client.get("/api/v1/statistics")
    assert response.status_code == 200
    data = response.json()
    assert "total_detections" in data
    assert "active_clusters" in data
    assert "risk_distribution" in data
    assert "anomaly_distribution" in data

def test_api_events_paginated_endpoint():
    response = client.get("/api/v1/events?page=1&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["limit"] == 5
    assert len(data["events"]) <= 5
    assert "total" in data

def test_api_events_filtering():
    response = client.get("/api/v1/events?risk_level=HIGH")
    assert response.status_code == 200
    data = response.json()
    for evt in data["events"]:
        assert evt["risk_level"] == "HIGH"

def test_api_map_data_geojson_endpoint():
    response = client.get("/api/v1/map-data")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert isinstance(data["features"], list)
    if data["features"]:
        assert data["features"][0]["type"] == "Feature"
        assert "coordinates" in data["features"][0]["geometry"]

def test_api_cluster_detail_valid():
    response = client.get("/api/v1/events/1")
    if response.status_code == 200:
        data = response.json()
        assert data["cluster_id"] == 1
        assert "risk_score" in data
        assert "classification_label" in data

def test_api_cluster_detail_invalid_404():
    response = client.get("/api/v1/events/999999")
    assert response.status_code == 404

def test_api_response_detail_endpoint():
    response = client.get("/api/v1/response/1")
    if response.status_code == 200:
        data = response.json()
        assert "alert_priority" in data
        assert "recommended_action" in data
        assert data["is_decision_support_only"] is True


def test_api_movement_direction_fields_present():
    """Every /movement record exposes the direction-intelligence schema fields."""
    response = client.get("/api/v1/movement")
    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list) and len(rows) > 0
    for row in rows[:50]:
        assert "direction" in row
        assert "movement_pattern" in row
        assert "direction_confidence" in row
        assert "direction_confidence_score" in row
        assert "direction_available" in row


def test_api_movement_directional_cluster():
    """A valid directional cluster returns direction + HIGH/MODERATE confidence."""
    mov_df = _movement_csv()
    cid = _pick_cluster_id(mov_df, "movement_pattern", "directional")
    if cid == -1:
        pytest.skip("No directional cluster in movement CSV")
    response = client.get(f"/api/v1/movement?cluster_id={cid}")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["cluster_id"] == cid
    assert row["direction_available"] is True
    assert row["direction"] in ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    assert row["direction_confidence"] in ("HIGH", "MODERATE", "PRELIMINARY")
    assert isinstance(row["direction_confidence_score"], int)


def test_api_movement_stationary_cluster():
    """A stationary cluster reports stationary pattern and null direction."""
    mov_df = _movement_csv()
    cid = _pick_cluster_id(mov_df, "movement_pattern", "stationary")
    if cid == -1:
        pytest.skip("No stationary cluster in movement CSV")
    response = client.get(f"/api/v1/movement?cluster_id={cid}")
    assert response.status_code == 200
    row = response.json()[0]
    assert row["movement_pattern"] == "stationary"
    assert row["direction_available"] is False
    assert row["direction"] is None
    assert row["direction_confidence"] == "INSUFFICIENT"


def test_api_movement_insufficient_cluster_null_direction():
    """Insufficient-observation clusters report null direction (never fabricated)."""
    mov_df = _movement_csv()
    cid = _pick_cluster_id(mov_df, "movement_pattern", "insufficient_evidence")
    if cid == -1:
        pytest.skip("No insufficient cluster in movement CSV")
    response = client.get(f"/api/v1/movement?cluster_id={cid}")
    assert response.status_code == 200
    row = response.json()[0]
    assert row["direction"] is None
    assert row["direction_available"] is False
    assert row["direction_confidence"] == "INSUFFICIENT"


def test_api_movement_cluster_id_filtering():
    """cluster_id filter returns exactly that cluster."""
    response = client.get("/api/v1/movement?cluster_id=1")
    assert response.status_code == 200
    rows = response.json()
    for row in rows:
        assert row["cluster_id"] == 1


def test_api_movement_cluster_id_not_found_returns_empty():
    """Unknown cluster_id returns an empty list, not a fabricated row."""
    response = client.get("/api/v1/movement?cluster_id=9999999")
    assert response.status_code == 200
    assert response.json() == []
