"""
Risk Intelligence Engine.

Computes a deterministic, evidence-based Risk Index (0-100) by combining
AI statistical abnormality, thermal energy, spatio-temporal persistence,
and false-alarm evidence reliability.

This is an experimental risk INDEX for event prioritization, NOT a calibrated
probability of fire or guaranteed physical hazard.
"""

from __future__ import annotations

from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np

from src.logging_setup import get_logger

logger = get_logger("models.risk_intelligence")

class RiskIntelligenceEngine:
    def __init__(self, multipliers: Dict[str, float] = None):
        """
        Initialize the Risk Intelligence Engine.
        """
        # Reliability attenuation multipliers for false alarm indicators
        self.multipliers = {
            "LOW": 1.0,      # Low false alarm concern -> 100% confidence
            "MEDIUM": 0.85,  # Medium concern -> 85% confidence
            "HIGH": 0.50,    # High concern (weak evidence) -> 50% confidence penalty
        }
        if multipliers:
            self.multipliers.update(multipliers)

    def calculate_risk(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate risk score, level, factors, and explanations for input dataframe.
        Appends:
        - risk_score (0-100)
        - risk_level (LOW, MEDIUM, HIGH)
        - risk_factors (comma-separated list)
        - risk_explanation (human-readable string)
        """
        required_cols = [
            "abnormality_level", "max_frp", "active_days", "persistence_category",
            "max_bright_ti4", "bt_diff_max", "false_alarm_indicator"
        ]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns for risk calculation: {missing}")

        df_out = df.copy()

        scores = []
        levels = []
        factors_list = []
        explanations = []

        for _, row in df.iterrows():
            score, level, factors, exp = self._calculate_single_record(row)
            scores.append(score)
            levels.append(level)
            factors_list.append(factors)
            explanations.append(exp)

        df_out["risk_score"] = scores
        df_out["risk_level"] = levels
        df_out["risk_factors"] = factors_list
        df_out["risk_explanation"] = explanations

        return df_out

    def _calculate_single_record(self, row: pd.Series) -> Tuple[float, str, str, str]:
        base_score = 0.0
        factors = []

        abnormality = str(row.get("abnormality_level", "NORMAL")).upper()
        max_frp = float(row.get("max_frp", 0.0))
        active_days = int(row.get("active_days", 1))
        pers_cat = str(row.get("persistence_category", "isolated")).lower()
        max_ti4 = float(row.get("max_bright_ti4", 0.0))
        bt_diff = float(row.get("bt_diff_max", 0.0))
        fa_indicator = str(row.get("false_alarm_indicator", "MEDIUM")).upper()

        # 1. Statistical Abnormality Component (Max 35 pts)
        if abnormality == "HIGH":
            base_score += 35.0
            factors.append("High statistical abnormality")
        elif abnormality == "ELEVATED":
            base_score += 20.0
            factors.append("Elevated statistical abnormality")
        else:
            base_score += 5.0

        # 2. Thermal Energy / FRP Component (Max 25 pts)
        if max_frp >= 20.0:
            base_score += 25.0
            factors.append("Strong thermal power (FRP >= 20 MW)")
        elif max_frp >= 10.0:
            base_score += 18.0
            factors.append("Elevated thermal power (FRP >= 10 MW)")
        elif max_frp >= 5.0:
            base_score += 12.0
        elif max_frp >= 2.0:
            base_score += 6.0

        # 3. Persistence / Recurrence Component (Max 20 pts)
        if pers_cat == "persistent" or active_days >= 4:
            base_score += 20.0
            factors.append("Persistent multi-day activity")
        elif pers_cat == "short_lived_repeated" or active_days >= 2:
            base_score += 12.0
            factors.append("Recurring thermal activity")
        else:
            base_score += 3.0

        # 4. Thermal Intensity / Contrast Component (Max 20 pts)
        if max_ti4 >= 350.0 or bt_diff >= 50.0:
            base_score += 20.0
            factors.append("Peak thermal intensity / contrast")
        elif max_ti4 >= 335.0 or bt_diff >= 35.0:
            base_score += 12.0
        else:
            base_score += 4.0

        # 5. Reliability / False Alarm Multiplier Adjustment
        multiplier = self.multipliers.get(fa_indicator, 0.85)
        if fa_indicator == "HIGH":
            factors.append("High false-alarm concern penalty applied")
        elif fa_indicator == "LOW":
            factors.append("High evidence reliability")

        # Compute Final Risk Score (bounded [0, 100])
        final_score = round(float(np.clip(base_score * multiplier, 0.0, 100.0)), 1)

        # Assign Risk Level
        if final_score >= 60.0:
            level = "HIGH"
        elif final_score >= 30.0:
            level = "MEDIUM"
        else:
            level = "LOW"

        # Construct Human-Readable Explanation
        factors_str = "; ".join(factors) if factors else "Standard thermal baseline"
        
        if level == "HIGH":
            explanation = (
                f"High risk index ({final_score}/100) driven by strong thermal evidence and "
                f"statistical abnormality ({factors_str}). Ranked for priority inspection."
            )
        elif level == "MEDIUM":
            explanation = (
                f"Moderate risk index ({final_score}/100) based on localized thermal activity "
                f"or moderated evidence reliability."
            )
        else:
            explanation = (
                f"Low risk index ({final_score}/100) representing routine thermal baseline "
                f"or weak unverified single-detection evidence."
            )

        return final_score, level, factors_str, explanation
