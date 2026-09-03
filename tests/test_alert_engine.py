"""
Tests for src/models/alert_engine.py and the /api/v1/alerts endpoints.

Covers severity mapping, false-alarm suppression/downgrade, evidence confidence,
reason generation, missing-field safety, file-based deduplication, lifecycle
(acknowledge/resolve), escalation, and API behavior.

All store tests use a temporary directory so the real generated
data/processed/thermal_alerts.csv is never mutated.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.models.alert_engine import ThermalAlertEngine, ThermalAlertStore


def _frame(rows: list[dict]) -> pd.DataFrame:
    """Wrap alert-intelligence rows with safe defaults for missing fields."""
    defaults = {
        "cluster_id": 0,
        "latitude": 20.0,
        "longitude": 78.0,
        "risk_score": 10.0,
        "risk_level": "LOW",
        "false_alarm_indicator": "LOW",
        "detection_reliability": "HIGH",
        "classification_label": "Unknown / Insufficient Evidence",
        "classification_score": 0.0,
        "observation_count": 1,
        "active_days": 1,
        "persistence_category": "isolated",
        "max_frp": 1.0,
        "max_bright_ti4": 310.0,
        "bt_diff_max": 20.0,
        "direction": "",
        "movement_bearing_degrees": None,
        "movement_rate_km_per_day": None,
        "movement_pattern": "insufficient_evidence",
        "direction_confidence": "",
        "nearest_station_name": "",
        "station_distance_km": None,
        "station_available": False,
    }
    out = []
    for row in rows:
        merged = dict(defaults)
        merged.update(row)
        out.append(merged)
    return pd.DataFrame(out)


def _make_store(tmp_path: Path) -> ThermalAlertStore:
    return ThermalAlertStore(tmp_path / "alerts")


# ============================================================================
# 1-4. Severity mapping
# ============================================================================

def test_low_risk_yields_low_alert():
    engine = ThermalAlertEngine()
    df = _frame([{"cluster_id": 1, "risk_score": 10.0, "risk_level": "LOW",
                  "false_alarm_indicator": "LOW"}])
    res = engine.generate_alerts(df).iloc[0]
    assert res["severity"] == "LOW"
    assert res["status"] == "ACTIVE"
    assert res["evidence_confidence"] == "HIGH"


def test_medium_risk_yields_medium_alert():
    engine = ThermalAlertEngine()
    df = _frame([{"cluster_id": 2, "risk_score": 45.0, "risk_level": "MEDIUM",
                  "false_alarm_indicator": "MEDIUM", "detection_reliability": "MEDIUM"}])
    res = engine.generate_alerts(df).iloc[0]
    assert res["severity"] == "MEDIUM"
    assert res["evidence_confidence"] == "MODERATE"


def test_high_risk_yields_high_alert():
    engine = ThermalAlertEngine()
    df = _frame([{"cluster_id": 3, "risk_score": 75.0, "risk_level": "HIGH",
                  "false_alarm_indicator": "LOW", "detection_reliability": "HIGH"}])
    res = engine.generate_alerts(df).iloc[0]
    assert res["severity"] == "HIGH"
    assert bool(res["suppressed"]) is False


def test_very_high_risk_yields_critical_alert():
    engine = ThermalAlertEngine()
    df = _frame([{"cluster_id": 4, "risk_score": 92.0, "risk_level": "HIGH",
                  "false_alarm_indicator": "LOW", "detection_reliability": "HIGH",
                  "observation_count": 6, "active_days": 4,
                  "persistence_category": "persistent", "max_frp": 40.0,
                  "max_bright_ti4": 360.0, "bt_diff_max": 60.0}])
    res = engine.generate_alerts(df).iloc[0]
    assert res["severity"] == "CRITICAL"
    assert res["evidence_confidence"] == "HIGH"


# ============================================================================
# 5-6. False-alarm suppression / downgrade
# ============================================================================

def test_high_false_alarm_suppresses_weak_alert():
    engine = ThermalAlertEngine()
    df = _frame([{"cluster_id": 5, "risk_score": 55.0, "risk_level": "MEDIUM",
                  "false_alarm_indicator": "HIGH", "detection_reliability": "LOW",
                  "observation_count": 1, "active_days": 1}])
    res = engine.generate_alerts(df).iloc[0]
    # High FA concern + weak evidence -> suppressed for monitoring (never deleted)
    assert bool(res["suppressed"]) is True
    assert res["severity"] == "LOW"
    assert "suppressed as an operator alert" in res["suppression_reason"]
    assert res["status"] == "ACTIVE"  # event still retained/monitored


def test_low_false_alarm_preserves_strong_alert():
    engine = ThermalAlertEngine()
    df = _frame([{"cluster_id": 6, "risk_score": 80.0, "risk_level": "HIGH",
                  "false_alarm_indicator": "LOW", "detection_reliability": "HIGH"}])
    res = engine.generate_alerts(df).iloc[0]
    assert bool(res["suppressed"]) is False
    assert res["severity"] == "HIGH"
    assert res["evidence_confidence"] == "HIGH"


# ============================================================================
# 7-8. Missing fields handled safely
# ============================================================================

def test_missing_classification_handled_safely():
    engine = ThermalAlertEngine()
    df = _frame([{"cluster_id": 7, "risk_score": 70.0, "risk_level": "HIGH",
                  "false_alarm_indicator": "LOW", "classification_label": "",
                  "classification_score": float("nan")}])
    res = engine.generate_alerts(df).iloc[0]
    assert res["classification_label"] == "Unknown / Insufficient Evidence"
    assert res["severity"] == "HIGH"  # classification absence does not crash/block


def test_missing_movement_handled_safely():
    engine = ThermalAlertEngine()
    df = _frame([{"cluster_id": 8, "risk_score": 65.0, "risk_level": "HIGH",
                  "false_alarm_indicator": "LOW", "direction": "",
                  "movement_bearing_degrees": None, "movement_pattern": ""}])
    res = engine.generate_alerts(df).iloc[0]
    assert res["movement_direction"] is None
    assert res["movement_pattern"] in ("insufficient_evidence", "")
    assert res["severity"] == "HIGH"


# ============================================================================
# 13. Reasons generated from actual evidence
# ============================================================================

def test_reasons_generated_from_evidence():
    engine = ThermalAlertEngine()
    df = _frame([{"cluster_id": 9, "risk_score": 88.0, "risk_level": "HIGH",
                  "false_alarm_indicator": "LOW", "detection_reliability": "HIGH",
                  "active_days": 5, "persistence_category": "persistent",
                  "max_frp": 25.0, "max_bright_ti4": 355.0, "bt_diff_max": 52.0,
                  "classification_label": "Industrial-context thermal event",
                  "classification_score": 0.9, "direction": "NE",
                  "direction_confidence": "MODERATE",
                  "nearest_station_name": "Test Station", "station_distance_km": 5.2,
                  "station_available": True}])
    res = engine.generate_alerts(df).iloc[0]
    reasons = str(res["reasons"]).lower()
    assert "risk score 88" in reasons
    assert "low false-alarm concern" in reasons
    assert "persistent multi-day" in reasons
    assert "frp 25.0 mw" in reasons
    assert "industrial context detected" in reasons
    assert "thermal activity movement ne" in reasons
    assert "verified fire station nearby: test station" in reasons


def test_no_fire_station_never_fabricated():
    engine = ThermalAlertEngine()
    df = _frame([{"cluster_id": 10, "risk_score": 80.0, "risk_level": "HIGH",
                  "false_alarm_indicator": "LOW", "nearest_station_name": "",
                  "station_distance_km": None, "station_available": False}])
    res = engine.generate_alerts(df).iloc[0]
    assert bool(res["station_available"]) is False
    assert res["station_distance_km"] is None
    assert "test station" not in str(res["reasons"]).lower()


# ============================================================================
# 9. Deduplication (idempotent generation)
# ============================================================================

def test_duplicate_generation_does_not_create_duplicate_alerts(tmp_path):
    engine = ThermalAlertEngine()
    store = _make_store(tmp_path)
    df = _frame([
        {"cluster_id": 11, "risk_score": 90.0, "risk_level": "HIGH", "false_alarm_indicator": "LOW"},
        {"cluster_id": 12, "risk_score": 20.0, "risk_level": "LOW", "false_alarm_indicator": "HIGH"},
        {"cluster_id": 13, "risk_score": 55.0, "risk_level": "MEDIUM", "false_alarm_indicator": "MEDIUM"},
    ])
    fresh = engine.generate_alerts(df)
    snap1 = store.sync(fresh)
    snap2 = store.sync(fresh)  # rerun
    assert len(snap1) == 3
    assert len(snap2) == 3
    assert snap2["alert_id"].duplicated().sum() == 0
    # same deterministic alert ids
    assert set(snap1["alert_id"]) == set(snap2["alert_id"])


def test_rerun_preserves_existing_status(tmp_path):
    engine = ThermalAlertEngine()
    store = _make_store(tmp_path)
    df = _frame([{"cluster_id": 21, "risk_score": 70.0, "risk_level": "HIGH",
                  "false_alarm_indicator": "LOW"}])
    store.sync(engine.generate_alerts(df))
    store.acknowledge(21)
    snap2 = store.sync(engine.generate_alerts(df))  # rerun after acknowledge
    assert snap2[snap2["cluster_id"] == 21].iloc[0]["status"] == "ACKNOWLEDGED"


# ============================================================================
# 10-11. Lifecycle
# ============================================================================

def test_acknowledge_works(tmp_path):
    engine = ThermalAlertEngine()
    store = _make_store(tmp_path)
    df = _frame([{"cluster_id": 31, "risk_score": 70.0, "risk_level": "HIGH",
                  "false_alarm_indicator": "LOW"}])
    store.sync(engine.generate_alerts(df))
    rec = store.acknowledge(31)
    assert rec["status"] == "ACKNOWLEDGED"
    assert rec["alert_id"] == "TAL-00031"


def test_resolve_works(tmp_path):
    engine = ThermalAlertEngine()
    store = _make_store(tmp_path)
    df = _frame([{"cluster_id": 32, "risk_score": 70.0, "risk_level": "HIGH",
                  "false_alarm_indicator": "LOW"}])
    store.sync(engine.generate_alerts(df))
    rec = store.resolve(32)
    assert rec["status"] == "RESOLVED"


def test_acknowledge_twice_rejected(tmp_path):
    engine = ThermalAlertEngine()
    store = _make_store(tmp_path)
    df = _frame([{"cluster_id": 33, "risk_score": 70.0, "risk_level": "HIGH",
                  "false_alarm_indicator": "LOW"}])
    store.sync(engine.generate_alerts(df))
    store.acknowledge(33)
    with pytest.raises(ValueError, match="Cannot transition"):
        store.acknowledge(33)


def test_resolve_from_acknowledged_works(tmp_path):
    engine = ThermalAlertEngine()
    store = _make_store(tmp_path)
    df = _frame([{"cluster_id": 34, "risk_score": 70.0, "risk_level": "HIGH",
                  "false_alarm_indicator": "LOW"}])
    store.sync(engine.generate_alerts(df))
    store.acknowledge(34)
    rec = store.resolve(34)
    assert rec["status"] == "RESOLVED"


def test_invalid_alert_id_raises_keyerror(tmp_path):
    engine = ThermalAlertEngine()
    store = _make_store(tmp_path)
    df = _frame([{"cluster_id": 35, "risk_score": 70.0, "risk_level": "HIGH",
                  "false_alarm_indicator": "LOW"}])
    store.sync(engine.generate_alerts(df))
    with pytest.raises(KeyError):
        store.acknowledge(99999)


# ============================================================================
# 12. Escalation
# ============================================================================

def test_escalation_records_previous_and_new_severity(tmp_path):
    engine = ThermalAlertEngine()
    store = _make_store(tmp_path)
    low = _frame([{"cluster_id": 41, "risk_score": 40.0, "risk_level": "MEDIUM",
                   "false_alarm_indicator": "LOW"}])
    store.sync(engine.generate_alerts(low))
    assert store.get_alert("TAL-00041")["severity"] == "MEDIUM"

    # intelligence improves -> HIGH risk now
    high = _frame([{"cluster_id": 41, "risk_score": 85.0, "risk_level": "HIGH",
                    "false_alarm_indicator": "LOW", "detection_reliability": "HIGH",
                    "active_days": 4, "persistence_category": "persistent",
                    "max_frp": 30.0, "max_bright_ti4": 360.0, "bt_diff_max": 55.0}])
    store.sync(engine.generate_alerts(high), run_reason="updated intelligence")
    assert store.get_alert("TAL-00041")["severity"] == "CRITICAL"

    hist = store._load_history()
    row = hist[hist["cluster_id"] == 41].iloc[-1]
    assert row["previous_severity"] == "MEDIUM"
    assert row["new_severity"] == "CRITICAL"
    assert "escalation" in str(row["reason"]).lower()


def test_resolved_alert_reopens_on_genuine_escalation(tmp_path):
    engine = ThermalAlertEngine()
    store = _make_store(tmp_path)
    med = _frame([{"cluster_id": 42, "risk_score": 45.0, "risk_level": "MEDIUM",
                   "false_alarm_indicator": "LOW"}])
    store.sync(engine.generate_alerts(med))
    store.resolve(42)
    assert store.get_alert("TAL-00042")["status"] == "RESOLVED"

    # Same severity on rerun -> stays resolved
    store.sync(engine.generate_alerts(med), run_reason="rerun")
    assert store.get_alert("TAL-00042")["status"] == "RESOLVED"

    # Escalation to HIGH -> reopened ACTIVE
    high = _frame([{"cluster_id": 42, "risk_score": 80.0, "risk_level": "HIGH",
                    "false_alarm_indicator": "LOW", "detection_reliability": "HIGH",
                    "active_days": 5, "persistence_category": "persistent"}])
    store.sync(engine.generate_alerts(high), run_reason="escalation rerun")
    alert = store.get_alert("TAL-00042")
    assert alert["severity"] == "HIGH"
    assert alert["status"] == "ACTIVE"


# ============================================================================
# API endpoint tests
# ============================================================================

def _seed_api_store(tmp_path: Path):
    """Build a small alert snapshot inside the API store used by tests."""
    from backend import main as backend_main
    store = ThermalAlertStore(tmp_path / "api_alerts")
    engine = ThermalAlertEngine()
    df = _frame([
        {"cluster_id": 51, "risk_score": 95.0, "risk_level": "HIGH",
         "false_alarm_indicator": "LOW", "detection_reliability": "HIGH",
         "classification_label": "Industrial-context thermal event", "max_frp": 50.0},
        {"cluster_id": 52, "risk_score": 70.0, "risk_level": "HIGH",
         "false_alarm_indicator": "LOW", "detection_reliability": "HIGH"},
        {"cluster_id": 53, "risk_score": 45.0, "risk_level": "MEDIUM",
         "false_alarm_indicator": "MEDIUM", "detection_reliability": "MEDIUM"},
        {"cluster_id": 54, "risk_score": 12.0, "risk_level": "LOW",
         "false_alarm_indicator": "HIGH", "detection_reliability": "LOW"},
    ])
    store.sync(engine.generate_alerts(df))
    backend_main._ALERT_STORE = store
    return backend_main


def test_api_get_alerts(tmp_path):
    backend_main = _seed_api_store(tmp_path)
    from fastapi.testclient import TestClient
    client = TestClient(backend_main.app)
    resp = client.get("/api/v1/alerts")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 4
    # sorted severity-first (CRITICAL, HIGH, MEDIUM, LOW)
    assert rows[0]["severity"] == "CRITICAL"


def test_api_get_alerts_filters(tmp_path):
    backend_main = _seed_api_store(tmp_path)
    from fastapi.testclient import TestClient
    client = TestClient(backend_main.app)
    assert len(client.get("/api/v1/alerts?severity=HIGH").json()) == 1
    assert len(client.get("/api/v1/alerts?severity=CRITICAL").json()) == 1
    assert len(client.get("/api/v1/alerts?status=ACTIVE").json()) == 4
    assert len(client.get("/api/v1/alerts?cluster_id=53").json()) == 1
    assert len(client.get("/api/v1/alerts?severity=LOW&suppressed=true").json()) == 1


def test_api_get_alert_detail_and_404(tmp_path):
    backend_main = _seed_api_store(tmp_path)
    from fastapi.testclient import TestClient
    client = TestClient(backend_main.app)
    resp = client.get("/api/v1/alerts/TAL-00051")
    assert resp.status_code == 200
    assert resp.json()["cluster_id"] == 51
    assert resp.json()["severity"] == "CRITICAL"
    assert resp.json()["is_decision_support_only"] is True
    assert client.get("/api/v1/alerts/TAL-99999").status_code == 404


def test_api_acknowledge_and_resolve(tmp_path):
    backend_main = _seed_api_store(tmp_path)
    from fastapi.testclient import TestClient
    client = TestClient(backend_main.app)
    ack = client.post("/api/v1/alerts/TAL-00052/acknowledge")
    assert ack.status_code == 200
    assert ack.json()["status"] == "ACKNOWLEDGED"
    # double acknowledge -> 409
    assert client.post("/api/v1/alerts/TAL-00052/acknowledge").status_code == 409
    res = client.post("/api/v1/alerts/TAL-00052/resolve")
    assert res.status_code == 200
    assert res.json()["status"] == "RESOLVED"
    # resolve of already resolved -> 409
    assert client.post("/api/v1/alerts/TAL-00052/resolve").status_code == 409
    assert client.post("/api/v1/alerts/TAL-99999/acknowledge").status_code == 404
