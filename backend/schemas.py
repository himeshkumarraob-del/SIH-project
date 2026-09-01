"""
Pydantic Schemas for FastAPI REST API endpoints.
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
    total_clusters: int
    risk_breakdown: Dict[str, int]
    abnormality_breakdown: Dict[str, int]
    false_alarm_breakdown: Dict[str, int]
    classification_breakdown: Dict[str, int]
    movement_breakdown: Dict[str, int]

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
