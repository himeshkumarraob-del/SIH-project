"""
Unit Tests for FastAPI REST API backend (backend/main.py).

Verifies endpoints, pagination, filtering parameters, response schemas, and 404 handling.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

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
    assert "total_clusters" in data
    assert "risk_breakdown" in data
    assert "abnormality_breakdown" in data

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
