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
    movement_status: Optional[str] = None


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
    station_distance_km: float
    alert_rationale: str
    is_decision_support_only: bool = True
