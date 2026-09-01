"""
Tests for src/response/fire_station_locator.py and src/response/alert_engine.py.

Verifies station proximity calculations, invalid coordinate safety, alert priority rules,
and decision-support advisory flags.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.response.fire_station_locator import FireStationLocator, haversine_km
from src.response.alert_engine import OperationalAlertEngine

def test_haversine_known_distance():
    # Delhi (28.6139, 77.2090) to Mumbai (19.0760, 72.8777) ~ 1148 km
    dist = haversine_km(28.6139, 77.2090, 19.0760, 72.8777)
    assert abs(dist - 1148.0) < 30.0

def test_find_nearest_station():
    locator = FireStationLocator()
    # Coordinates near Delhi
    res = locator.find_nearest_station(28.60, 77.20)
    assert res["station_available"] is True
    assert "Delhi" in res["station_name"]
    assert res["distance_km"] < 15.0

def test_invalid_coordinates_handled_safely():
    locator = FireStationLocator()
    res = locator.find_nearest_station(999.0, 999.0)
    assert res["station_available"] is False
    assert res["station_name"] == "Invalid Coordinates"

def test_high_risk_low_false_alarm_triggers_high_priority_alert():
    engine = OperationalAlertEngine()
    df = pd.DataFrame([{
        "cluster_id": 1,
        "latitude": 28.61,
        "longitude": 77.20,
        "risk_level": "HIGH",
        "risk_score": 85.0,
        "false_alarm_indicator": "LOW",
        "classification_label": "Industrial-context thermal event"
    }])

    res = engine.generate_alerts(df)
    assert res.iloc[0]["alert_priority"] == "HIGH PRIORITY ALERT"
    assert "Dispatch priority ground verification unit" in res.iloc[0]["recommended_action"]
    assert bool(res.iloc[0]["is_decision_support_only"]) is True

def test_high_risk_high_false_alarm_triggers_review_priority():
    engine = OperationalAlertEngine()
    df = pd.DataFrame([{
        "cluster_id": 2,
        "latitude": 28.61,
        "longitude": 77.20,
        "risk_level": "HIGH",
        "risk_score": 65.0,
        "false_alarm_indicator": "HIGH",
        "classification_label": "Unknown"
    }])

    res = engine.generate_alerts(df)
    assert res.iloc[0]["alert_priority"] == "REVIEW / VERIFICATION"

def test_low_risk_triggers_no_alert():
    engine = OperationalAlertEngine()
    df = pd.DataFrame([{
        "cluster_id": 3,
        "latitude": 28.61,
        "longitude": 77.20,
        "risk_level": "LOW",
        "risk_score": 15.0,
        "false_alarm_indicator": "HIGH",
        "classification_label": "Unknown"
    }])

    res = engine.generate_alerts(df)
    assert res.iloc[0]["alert_priority"] == "NO ALERT"
