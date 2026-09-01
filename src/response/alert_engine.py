"""
Operational Alert & Decision Support Engine.

Evaluates operational response priorities based on Risk Index, False Alarm Concern, and
Fire Station Proximity.

Decision Support Guardrail:
Outputs operational recommendations strictly for advisory review. Does NOT execute emergency dispatch.
"""

from __future__ import annotations

from typing import Dict, Any, Tuple
import pandas as pd

from src.response.fire_station_locator import FireStationLocator
from src.logging_setup import get_logger

logger = get_logger("response.alert_engine")

class OperationalAlertEngine:
    def __init__(self, locator: Optional[FireStationLocator] = None):
        self.locator = locator or FireStationLocator()

    def generate_alerts(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate emergency alert recommendations for input cluster dataframe.
        Appends:
        - alert_priority (HIGH PRIORITY ALERT, REVIEW / VERIFICATION, MONITOR, NO ALERT)
        - recommended_action
        - nearest_station_name
        - station_distance_km
        - alert_rationale
        """
        df_out = df.copy()

        priorities = []
        actions = []
        st_names = []
        st_dists = []
        rationales = []

        for _, row in df_out.iterrows():
            cid = row.get("cluster_id", 0)
            lat = float(row.get("latitude", row.get("start_latitude", 0.0)))
            lon = float(row.get("longitude", row.get("start_longitude", 0.0)))
            risk_level = str(row.get("risk_level", "LOW")).upper()
            fa_indicator = str(row.get("false_alarm_indicator", "MEDIUM")).upper()
            classification = str(row.get("classification_label", "Unknown")).strip()

            # Find nearest fire station
            st_info = self.locator.find_nearest_station(lat, lon)
            st_name = st_info["station_name"]
            st_dist = st_info["distance_km"]

            # Alert Rules Logic
            if risk_level == "HIGH" and fa_indicator == "LOW":
                prio = "HIGH PRIORITY ALERT"
                act = f"Dispatch priority ground verification unit from {st_name} ({st_dist:.1f} km away)."
                rat = f"High Risk Index ({row.get('risk_score', 80)}) combined with high evidence reliability (Low False-Alarm Concern)."
            elif risk_level == "HIGH" and fa_indicator == "HIGH":
                prio = "REVIEW / VERIFICATION"
                act = "Perform remote verification before ground deployment."
                rat = "High statistical abnormality but weak supporting evidence (High False-Alarm Concern)."
            elif risk_level == "HIGH" or risk_level == "MEDIUM":
                prio = "MONITOR / REVIEW"
                act = f"Monitor thermal activity for escalation. Closest station: {st_name} ({st_dist:.1f} km)."
                rat = f"Moderate thermal risk context ({classification}). Operational review recommended."
            else:
                prio = "NO ALERT"
                act = "Routine baseline monitoring."
                rat = "Low Risk Index representing routine thermal baseline."

            priorities.append(prio)
            actions.append(act)
            st_names.append(st_name)
            st_dists.append(st_dist)
            rationales.append(rat)

        df_out["alert_priority"] = priorities
        df_out["recommended_action"] = actions
        df_out["nearest_station_name"] = st_names
        df_out["station_distance_km"] = st_dists
        df_out["alert_rationale"] = rationales
        df_out["is_decision_support_only"] = True

        return df_out
