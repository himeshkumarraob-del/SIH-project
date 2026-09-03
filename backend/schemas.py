"""
Pydantic Schemas for FastAPI REST API endpoints.

These schemas define the response shapes that the React frontend expects.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class EventSummary(BaseModel):
    cluster_id: int
    latitude: float
    longitude: float
    acq_date: Optional[str] = None
    abnormality_level: Optional[str] = None
    false_alarm_indicator: Optional[str] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    classification_label: Optional[str] = None
    classification_score: Optional[float] = None
    movement_status: Optional[str] = None
    max_frp: Optional[float] = None
    max_bright_ti4: Optional[float] = None
    explanation: Optional[str] = None
    observation_count: Optional[int] = None
    active_days: Optional[int] = None



class PaginatedEventsResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    events: List[EventSummary]


class DashboardStatistics(BaseModel):
    total_detections: int
    active_clusters: int
    high_risk_count: int
    moving_count: int
    high_false_alarm_count: int
    anomaly_distribution: Dict[str, int]
    risk_distribution: Dict[str, int]
    false_alarm_distribution: Dict[str, int]
    movement_distribution: Dict[str, int]


class ClusterDetail(BaseModel):
    cluster_id: int
    latitude: float
    longitude: float
    observation_count: int
    active_days: int
    first_detection: Optional[str] = None
    last_detection: Optional[str] = None
    duration_days: Optional[int] = None
    persistence_category: Optional[str] = None
    max_frp: float
    max_bright_ti4: float
    bt_diff_max: float
    abnormality_level: str
    anomaly_characterization: Optional[str] = None
    explanation: Optional[str] = None
    false_alarm_indicator: str
    detection_reliability: str
    risk_score: float
    risk_level: str
    classification_label: str
    classification_score: float
    classification_rationale: str
    movement_status: str
    total_movement_distance_km: float


class MovementVector(BaseModel):
    cluster_id: int
    observation_count: int
    active_days: int
    first_detection: Optional[str] = None
    last_detection: Optional[str] = None
    time_span_days: float = 0.0
    start_latitude: float = 0.0
    start_longitude: float = 0.0
    end_latitude: float = 0.0
    end_longitude: float = 0.0
    total_movement_distance_km: float = 0.0
    movement_rate_km_per_day: float = 0.0
    movement_bearing_degrees: float = 0.0
    movement_direction: str = "INSUFFICIENT_DATA"
    movement_confidence: str = "INSUFFICIENT_DATA"
    movement_status: str = "INSUFFICIENT_DATA"
    # --- Direction intelligence (Thermal Activity Movement Direction) ---
    # "direction" is null unless a defensible direction exists; the legacy
    # movement_direction column above is retained for existing consumers.
    direction: Optional[str] = None
    movement_pattern: str = "insufficient_evidence"
    direction_confidence: str = "INSUFFICIENT"
    direction_confidence_score: int = 0
    direction_available: bool = False



class ClassificationDetail(BaseModel):
    cluster_id: int
    classification_label: str
    classification_score: float
    classification_rationale: str
    osm_facility_type: str = "UNKNOWN"
    osm_distance_km: float = 999.0
    predicted_landcover_class: str = "UNKNOWN"
    prediction_confidence: float = 0.0


class RiskDetail(BaseModel):
    cluster_id: int
    risk_score: float
    risk_level: str
    risk_factors: str = ""
    risk_explanation: str = ""


class AlertResponse(BaseModel):
    cluster_id: int
    risk_score: float
    risk_level: str
    alert_priority: str
    recommended_action: str
    nearest_station_name: str
    station_distance_km: Optional[float] = None
    station_available: bool = False
    alert_rationale: str
    is_decision_support_only: bool = True


class ThermalAlert(BaseModel):
    """Structured thermal-alert record from the Thermal Alert Engine.

    Severity (LOW/MEDIUM/HIGH/CRITICAL) is a decision-support classification of
    processed thermal evidence; it is NOT a confirmed fire declaration.
    """

    alert_id: str
    cluster_id: int
    severity: str
    status: str = "ACTIVE"
    evidence_confidence: str = "INSUFFICIENT"
    suppressed: bool = False
    suppression_reason: str = ""
    risk_score: Optional[float] = None
    risk_level: str = "LOW"
    classification_label: str = "Unknown / Insufficient Evidence"
    classification_score: Optional[float] = None
    false_alarm_indicator: str = "UNKNOWN"
    detection_reliability: str = "UNKNOWN"
    observation_count: int = 1
    active_days: int = 1
    persistence_category: str = "isolated"
    max_frp: Optional[float] = None
    max_bright_ti4: Optional[float] = None
    bt_diff_max: Optional[float] = None
    movement_direction: Optional[str] = None
    movement_bearing_degrees: Optional[float] = None
    movement_rate_km_per_day: Optional[float] = None
    movement_pattern: str = "insufficient_evidence"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    nearest_station_name: str = ""
    station_distance_km: Optional[float] = None
    station_available: bool = False
    reasons: str = ""
    alert_rationale: str = ""
    created_at: str = ""
    updated_at: str = ""
    is_decision_support_only: bool = True


class AlertTransitionResult(BaseModel):
    alert_id: str
    cluster_id: int
    status: str
    severity: str
    updated_at: str
    detail: str = ""


class AlertHistoryEntry(BaseModel):
    alert_id: str
    cluster_id: int
    previous_severity: str = ""
    new_severity: str = ""
    status: str = ""
    timestamp: str = ""
    reason: str = ""
