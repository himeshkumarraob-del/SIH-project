"""
Incident Report Generator for ThermalWatch Local Thermal Incident Reports.

Assembles complete decision-support evidence for any cluster, combining:
- Real satellite thermal observations (FIRMS)
- Reverse-geocoded location intelligence
- Risk assessment scores & factors
- Industrial classification and Sentinel-2 context
- Thermal Activity Movement vectors
- Local surroundings (fire stations, roads, OSM facilities)
- Evidence-based flagging rationale
- Recommendations & standard disclaimers
"""

from __future__ import annotations

import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

from src.geocoding.reverse_geocoder import ReverseGeocoder, ReverseGeocodeResult
from src.logging_setup import get_logger

logger = get_logger("src.reports.incident_report_generator")


@dataclass
class IncidentReportData:
    title: str = "THERMALWATCH LOCAL THERMAL INCIDENT REPORT"
    report_generated_at: str = ""
    cluster_id: int = 0
    severity: str = "LOW"
    risk_score: float = 0.0

    # A. Incident Identification
    location: Dict[str, Any] = None

    # B. Thermal Observation
    observation_count: int = 1
    first_detected: str = "Not available"
    last_detected: str = "Not available"
    active_days: int = 1
    max_frp: float = 0.0
    brightness_temp_ti4: float = 0.0
    thermal_contrast_k: float = 0.0
    persistence_category: str = "isolated"

    # C. Risk Assessment
    risk_level: str = "LOW"
    risk_factors: str = "Not available"
    false_alarm_concern: str = "MEDIUM"
    evidence_reliability_level: str = "MEDIUM"

    # D. Classification
    classification_label: str = "Unknown"
    classification_confidence: float = 0.0
    osm_industrial_context: str = "Not available"
    sentinel2_cnn_context: str = "Not available"
    cloud_imagery_limitations: str = "Optical Sentinel-2 cloud cover or revisit interval constraints apply."

    # E. Thermal Activity Movement
    movement_status: str = "INSUFFICIENT_DATA"
    movement_direction: str = "Not available"
    direction_confidence: str = "INSUFFICIENT"
    displacement_km: float = 0.0
    movement_rate_km_per_day: float = 0.0
    directional_consistency: str = "Not available"
    movement_disclaimer: str = "Thermal Activity Movement tracking describes shifts in satellite thermal detections and does NOT state physical fire spread."

    # F. Local Surroundings
    nearby_industrial_infrastructure: str = "Not available"
    nearby_roads: str = "Not available"
    nearest_fire_station_name: str = "Not available"
    distance_to_fire_station_km: str = "Not available"
    nearby_landmarks: str = "Not available"

    # G. Why Flagged
    why_flagged_explanation: str = ""

    # H. Recommended Actions
    recommended_actions: List[str] = None
    action_type: str = "DECISION-SUPPORT"

    # I. Disclaimer
    disclaimer: str = (
        "This report is a decision-support product based on satellite thermal observations "
        "and available geospatial evidence. A thermal anomaly does not independently "
        "confirm a fire or its source. Local verification is required."
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IncidentReportGenerator:
    """Generates structured incident reports using real system data."""

    def __init__(self, geocoder: Optional[ReverseGeocoder] = None):
        self.geocoder = geocoder or ReverseGeocoder.get_instance()

    def generate_report(
        self,
        event: Dict[str, Any],
        alert: Optional[Dict[str, Any]] = None,
        movement: Optional[Dict[str, Any]] = None,
        classification: Optional[Dict[str, Any]] = None,
        risk: Optional[Dict[str, Any]] = None,
        response: Optional[Dict[str, Any]] = None,
    ) -> IncidentReportData:
        cluster_id = int(event.get("cluster_id", 0))
        lat = float(event.get("latitude", 0.0))
        lon = float(event.get("longitude", 0.0))

        # Reverse geocode coordinates
        geo_result = self.geocoder.reverse_geocode(lat, lon)
        location_dict = geo_result.to_dict()

        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Risk parameters
        risk_score = float(event.get("risk_score") or (risk.get("risk_score") if risk else 0.0))
        risk_level = str(event.get("risk_level") or (risk.get("risk_level") if risk else "LOW")).upper()
        severity = str(alert.get("severity") if alert else risk_level).upper()

        # Thermal observation metrics
        obs_count = int(event.get("observation_count") or 1)
        first_det = str(event.get("first_detection") or event.get("acq_date") or "Not available")
        last_det = str(event.get("last_detection") or event.get("acq_date") or "Not available")
        active_days = int(event.get("active_days") or 1)
        max_frp = float(event.get("max_frp") or 0.0)
        max_bt = float(event.get("max_bright_ti4") or 0.0)
        bt_diff = float(event.get("bt_diff_max") or 0.0)
        persistence = str(event.get("persistence_category") or alert.get("persistence_category") if alert else "isolated")

        # Classification metrics
        cls_label = str(event.get("classification_label") or (classification.get("classification_label") if classification else "Unknown"))
        cls_score = float(event.get("classification_score") or (classification.get("classification_score") if classification else 0.0))
        osm_facility = str(classification.get("osm_facility_type") if classification else event.get("osm_facility_type", "Not available"))
        osm_dist = classification.get("osm_distance_km") if classification else event.get("osm_distance_km")
        osm_context = f"{osm_facility} ({osm_dist:.2f} km away)" if (osm_dist is not None and osm_facility != "Not available" and osm_facility != "UNKNOWN") else "No industrial facility identified in close proximity."

        sentinel_landcover = str(classification.get("predicted_landcover_class") if classification else "Not available")
        sentinel_context = f"Predicted landcover: {sentinel_landcover}" if sentinel_landcover != "UNKNOWN" else "Optical Sentinel-2 imagery pending or clouded."

        # Movement metrics
        move_status = str(event.get("movement_status") or (movement.get("movement_status") if movement else "INSUFFICIENT_DATA"))
        move_dir = movement.get("direction") if movement else event.get("movement_direction")
        move_dir_str = str(move_dir) if (move_dir and str(move_dir).strip()) else "Not available"
        move_conf = str(movement.get("direction_confidence") if movement else event.get("movement_confidence", "INSUFFICIENT"))
        move_dist = float(movement.get("total_movement_distance_km") if movement else event.get("total_movement_distance_km", 0.0))
        move_rate = float(movement.get("movement_rate_km_per_day") if movement else event.get("movement_rate_km_per_day", 0.0))
        move_pattern = str(movement.get("movement_pattern") if movement else "insufficient_evidence")

        # Surroundings metrics
        station_name = str(response.get("nearest_station_name") if response else event.get("nearest_station_name", "Not available"))
        station_dist_val = response.get("station_distance_km") if response else event.get("station_distance_km")
        if station_dist_val is not None and station_dist_val > 0:
            station_dist_str = f"{float(station_dist_val):.2f} km"
        else:
            station_dist_str = "Not available"
            if station_name == "Unknown Station":
                station_name = "Not available"

        nearby_roads = geo_result.street_road if geo_result.street_road != "Not available" else "No major road mapped in immediate 50m radius."
        nearby_landmarks = geo_result.landmark if geo_result.landmark != "Not available" else "No specific public landmark mapped in immediate vicinity."

        # Why Flagged explanation
        why_explanation = self._build_why_flagged_explanation(
            severity=severity,
            risk_score=risk_score,
            obs_count=obs_count,
            max_frp=max_frp,
            persistence=persistence,
            cls_label=cls_label,
            move_status=move_status,
            fa_indicator=str(event.get("false_alarm_indicator", "MEDIUM")),
        )

        # Recommended Next Actions
        rec_actions = self._build_recommended_actions(severity)

        return IncidentReportData(
            title="THERMALWATCH LOCAL THERMAL INCIDENT REPORT",
            report_generated_at=now_str,
            cluster_id=cluster_id,
            severity=severity,
            risk_score=risk_score,
            location=location_dict,
            observation_count=obs_count,
            first_detected=first_det,
            last_detected=last_det,
            active_days=active_days,
            max_frp=max_frp,
            brightness_temp_ti4=max_bt,
            thermal_contrast_k=bt_diff,
            persistence_category=persistence,
            risk_level=risk_level,
            risk_factors=str(event.get("risk_factors") or (risk.get("risk_factors") if risk else "Elevated FRP and persistence")),
            false_alarm_concern=str(event.get("false_alarm_indicator", "MEDIUM")),
            evidence_reliability_level=str(event.get("detection_reliability", "MEDIUM")),
            classification_label=cls_label,
            classification_confidence=cls_score,
            osm_industrial_context=osm_context,
            sentinel2_cnn_context=sentinel_context,
            cloud_imagery_limitations="Optical Sentinel-2 cloud cover or satellite revisit constraints may apply.",
            movement_status=move_status,
            movement_direction=move_dir_str,
            direction_confidence=move_conf,
            displacement_km=move_dist,
            movement_rate_km_per_day=move_rate,
            directional_consistency=move_pattern,
            nearby_industrial_infrastructure=osm_context,
            nearby_roads=nearby_roads,
            nearest_fire_station_name=station_name,
            distance_to_fire_station_km=station_dist_str,
            nearby_landmarks=nearby_landmarks,
            why_flagged_explanation=why_explanation,
            recommended_actions=rec_actions,
        )

    def _build_why_flagged_explanation(
        self,
        severity: str,
        risk_score: float,
        obs_count: int,
        max_frp: float,
        persistence: str,
        cls_label: str,
        move_status: str,
        fa_indicator: str,
    ) -> str:
        factors = []
        if persistence in ("multi_day", "persistent", "recurrent"):
            factors.append("persistent thermal activity over multiple satellite passes")
        else:
            factors.append("localized thermal anomaly detection")

        if max_frp > 20.0:
            factors.append(f"elevated Fire Radiative Power (FRP {max_frp:.1f} MW)")
        elif max_frp > 5.0:
            factors.append(f"moderate Fire Radiative Power (FRP {max_frp:.1f} MW)")

        if cls_label not in ("Unknown", "Not available"):
            factors.append(f"supporting geospatial context ({cls_label})")

        if fa_indicator == "LOW":
            factors.append("low false-alarm indicator score")

        factors_str = ", ".join(factors)
        return (
            f"Cluster flagged at {severity} level (Risk Score {risk_score:.1f}/100) because "
            f"the anomaly exhibits {factors_str} across {obs_count} satellite observations."
        )

    def _build_recommended_actions(self, severity: str) -> List[str]:
        sev = severity.upper()
        if sev == "CRITICAL":
            return [
                "Immediate local field verification required at identified coordinates.",
                "Notify appropriate local emergency / fire-response authority with incident location context.",
                "Check identified location, street access, and nearby industrial/vulnerable infrastructure.",
                "Maintain continuous alert monitoring for subsequent satellite overpasses.",
            ]
        elif sev == "HIGH":
            return [
                "Prioritize field verification at specified location.",
                "Review nearby industrial infrastructure and local geographic access.",
                "Notify responsible regional monitoring and emergency response personnel.",
                "Continue tracking cluster thermal persistence and movement vectors.",
            ]
        elif sev == "MEDIUM":
            return [
                "Continue satellite alert monitoring.",
                "Review cluster persistence and supporting geospatial evidence.",
                "Consider local ground verification if thermal activity continues into next overpass.",
            ]
        else:
            return [
                "Continue routine observation.",
                "No immediate escalation based solely on current satellite thermal evidence.",
            ]
