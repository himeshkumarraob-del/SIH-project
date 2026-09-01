"""
False Alarm Intelligence Module.

Evaluates thermal anomaly detections and clusters for evidence strength,
classifying false-alarm concern levels (LOW, MEDIUM, HIGH) and detection reliability
without claiming unverified ground-truth probabilities.
"""

from __future__ import annotations

from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np

from src.logging_setup import get_logger

logger = get_logger("models.false_alarm_detector")

class FalseAlarmDetector:
    def __init__(self, thresholds: Dict[str, float] = None):
        """
        Initialize the false alarm detector with configurable thresholds.
        """
        self.thresholds = {
            "low_confidence_max": 1.5,     # < 1.5 implies low confidence rating ('l')
            "high_confidence_min": 2.5,    # >= 2.5 implies high confidence rating ('h')
            "weak_frp_max": 2.0,           # < 2 MW FRP is considered weak
            "strong_frp_min": 15.0,        # >= 15 MW FRP is considered strong
            "low_bt_diff_max": 25.0,       # < 25 K is low spectral contrast
            "high_bt_diff_min": 45.0,      # >= 45 K is high spectral contrast
            "high_bright_ti4_min": 340.0,  # >= 340 K is high brightness
            "min_persistent_active_days": 3,
        }
        if thresholds:
            self.thresholds.update(thresholds)

    def evaluate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Evaluate each record in the dataframe and append:
        - false_alarm_indicator (LOW, MEDIUM, HIGH)
        - false_alarm_reasons (comma-separated text)
        - detection_reliability (HIGH, MEDIUM, LOW)
        """
        required_cols = [
            "observation_count", "active_days", "duration_days", 
            "mean_frp", "max_frp", "max_bright_ti4", "bt_diff_max", "mean_confidence"
        ]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns for false alarm evaluation: {missing}")

        df_out = df.copy()

        indicators = []
        reasons_list = []
        reliabilities = []

        for _, row in df.iterrows():
            ind, reasons, rel = self._evaluate_single_record(row)
            indicators.append(ind)
            reasons_list.append(reasons)
            reliabilities.append(rel)

        df_out["false_alarm_indicator"] = indicators
        df_out["false_alarm_reasons"] = reasons_list
        df_out["detection_reliability"] = reliabilities

        return df_out

    def _evaluate_single_record(self, row: pd.Series) -> Tuple[str, str, str]:
        concern_score = 0
        reasons = []

        obs_count = row.get("observation_count", 1)
        active_days = row.get("active_days", 1)
        duration_days = row.get("duration_days", 1)
        max_frp = row.get("max_frp", 0.0)
        max_ti4 = row.get("max_bright_ti4", 0.0)
        bt_diff = row.get("bt_diff_max", 0.0)
        conf = row.get("mean_confidence", 2.0)
        pers_cat = str(row.get("persistence_category", "isolated")).lower()

        # 1. Observation Count & Spatial/Temporal Evidence
        if obs_count == 1:
            concern_score += 2
            reasons.append("single point observation")
        elif obs_count >= 5:
            concern_score -= 2

        # 2. Persistence / Temporal Recurrence
        if active_days == 1 and duration_days == 1:
            concern_score += 1
            reasons.append("no temporal recurrence")
        elif active_days >= self.thresholds["min_persistent_active_days"] or pers_cat == "persistent":
            concern_score -= 2

        # 3. Confidence Rating
        if conf < self.thresholds["low_confidence_max"]:
            concern_score += 2
            reasons.append("low satellite confidence rating")
        elif conf >= self.thresholds["high_confidence_min"]:
            concern_score -= 1

        # 4. Fire Radiative Power (FRP)
        if max_frp < self.thresholds["weak_frp_max"]:
            concern_score += 1
            reasons.append("weak thermal power (< 2 MW)")
        elif max_frp >= self.thresholds["strong_frp_min"]:
            concern_score -= 2

        # 5. Brightness Temperature & Contrast
        if bt_diff < self.thresholds["low_bt_diff_max"] or max_ti4 < 315.0:
            concern_score += 1
            reasons.append("low spectral temperature contrast")
        elif max_ti4 >= self.thresholds["high_bright_ti4_min"] or bt_diff >= self.thresholds["high_bt_diff_min"]:
            concern_score -= 1

        # Determine Indicator & Reliability
        if concern_score >= 3:
            indicator = "HIGH"
            reliability = "LOW"
        elif concern_score >= 1:
            indicator = "MEDIUM"
            reliability = "MEDIUM"
        else:
            indicator = "LOW"
            reliability = "HIGH"
            if not reasons:
                reasons.append("strong supporting evidence across thermal and temporal metrics")

        reasons_str = "; ".join(reasons) if reasons else "strong supporting evidence"
        return indicator, reasons_str, reliability
