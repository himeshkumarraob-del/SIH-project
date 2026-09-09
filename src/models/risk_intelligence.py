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

# Reliability attenuation multipliers for false alarm indicators
DEFAULT_MULTIPLIERS: Dict[str, float] = {
    "LOW": 1.0,      # Low false alarm concern -> 100% confidence
    "MEDIUM": 0.85,  # Medium concern -> 85% confidence
    "HIGH": 0.50,    # High concern (weak evidence) -> 50% confidence penalty
}

# Max points available per risk component (must reconcile with _calculate_single_record)
COMPONENT_MAX_POINTS: Dict[str, float] = {
    "abnormality": 35.0,  # Statistical abnormality
    "frp": 25.0,          # Thermal energy / FRP
    "persistence": 20.0,  # Persistence / recurrence
    "intensity": 20.0,    # Thermal intensity / contrast
}


def _component_scores(row: pd.Series, multipliers: Dict[str, float]) -> Tuple[float, float, float, float, float]:
    """Compute the four raw risk components and the reliability multiplier.

    This is the single source of truth for the risk-index breakdown. The risk
    engine applies it, and the evidence explorer reuses it so the displayed
    contributions always reconcile with the existing risk score.
    """
    abnormality = str(row.get("abnormality_level", "NORMAL")).upper()
    max_frp = float(row.get("max_frp", 0.0))
    active_days = int(row.get("active_days", 1))
    pers_cat = str(row.get("persistence_category", "isolated")).lower()
    max_ti4 = float(row.get("max_bright_ti4", 0.0))
    bt_diff = float(row.get("bt_diff_max", 0.0))
    fa_indicator = str(row.get("false_alarm_indicator", "MEDIUM")).upper()

    # 1. Statistical Abnormality Component (Max 35 pts)
    if abnormality == "HIGH":
        abn = 35.0
    elif abnormality == "ELEVATED":
        abn = 20.0
    else:
        abn = 5.0

    # 2. Thermal Energy / FRP Component (Max 25 pts)
    if max_frp >= 20.0:
        frp = 25.0
    elif max_frp >= 10.0:
        frp = 18.0
    elif max_frp >= 5.0:
        frp = 12.0
    elif max_frp >= 2.0:
        frp = 6.0
    else:
        frp = 0.0

    # 3. Persistence / Recurrence Component (Max 20 pts)
    if pers_cat == "persistent" or active_days >= 4:
        pers = 20.0
    elif pers_cat == "short_lived_repeated" or active_days >= 2:
        pers = 12.0
    else:
        pers = 3.0

    # 4. Thermal Intensity / Contrast Component (Max 20 pts)
    if max_ti4 >= 350.0 or bt_diff >= 50.0:
        inten = 20.0
    elif max_ti4 >= 335.0 or bt_diff >= 35.0:
        inten = 12.0
    else:
        inten = 4.0

    # 5. Reliability / False Alarm Multiplier Adjustment
    multiplier = multipliers.get(fa_indicator, 0.85)

    return abn, frp, pers, inten, multiplier


class RiskIntelligenceEngine:
    def __init__(self, multipliers: Dict[str, float] = None):
        """
        Initialize the Risk Intelligence Engine.
        """
        self.multipliers = dict(DEFAULT_MULTIPLIERS)
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

        abn, frp, pers, inten, multiplier = _component_scores(row, self.multipliers)
        base_score = abn + frp + pers + inten

        # 1. Statistical Abnormality Component (Max 35 pts)
        if abnormality == "HIGH":
            factors.append("High statistical abnormality")
        elif abnormality == "ELEVATED":
            factors.append("Elevated statistical abnormality")

        # 2. Thermal Energy / FRP Component (Max 25 pts)
        if max_frp >= 20.0:
            factors.append("Strong thermal power (FRP >= 20 MW)")
        elif max_frp >= 10.0:
            factors.append("Elevated thermal power (FRP >= 10 MW)")

        # 3. Persistence / Recurrence Component (Max 20 pts)
        if pers_cat == "persistent" or active_days >= 4:
            factors.append("Persistent multi-day activity")
        elif pers_cat == "short_lived_repeated" or active_days >= 2:
            factors.append("Recurring thermal activity")

        # 4. Thermal Intensity / Contrast Component (Max 20 pts)
        if max_ti4 >= 350.0 or bt_diff >= 50.0:
            factors.append("Peak thermal intensity / contrast")

        # 5. Reliability / False Alarm Multiplier Adjustment
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


def build_risk_evidence(row: pd.Series, multipliers: Dict[str, float] = None) -> Dict[str, Any]:
    """Deterministic breakdown of the existing Risk Index into its evidence components.

    Exposes the already-calculated component contributions of the risk engine in a
    backward-compatible, read-only way. The final score is recomputed with the exact
    engine formula and must equal the stored ``risk_score`` for the same row. No new
    risk calculation is introduced and no evidence is invented.

    Returns a dict with:
    - components: label/points/max/detail per component
    - reliability_multiplier: attenuation applied for the false-alarm concern
    - false_alarm_concern: LOW/MEDIUM/HIGH
    - base_score: sum of raw component points
    - final_score: round(clip(base_score * multiplier, 0, 100), 1)
    """
    mult_map = dict(DEFAULT_MULTIPLIERS)
    if multipliers:
        mult_map.update(multipliers)

    abnormality = str(row.get("abnormality_level", "NORMAL")).upper()
    max_frp = float(row.get("max_frp", 0.0))
    active_days = int(row.get("active_days", 1))
    pers_cat = str(row.get("persistence_category", "isolated")).lower()
    max_ti4 = float(row.get("max_bright_ti4", 0.0))
    bt_diff = float(row.get("bt_diff_max", 0.0))
    fa_indicator = str(row.get("false_alarm_indicator", "MEDIUM")).upper()

    abn, frp, pers, inten, multiplier = _component_scores(row, mult_map)
    base_score = abn + frp + pers + inten
    final_score = round(float(np.clip(base_score * multiplier, 0.0, 100.0)), 1)

    components = [
        {
            "key": "abnormality",
            "label": "Thermal Abnormality",
            "points": abn,
            "max_points": COMPONENT_MAX_POINTS["abnormality"],
            "detail": (
                f"Statistical abnormality relative to the analyzed thermal baseline "
                f"(abnormality level: {abnormality})."
            ),
        },
        {
            "key": "frp",
            "label": "FRP Intensity",
            "points": frp,
            "max_points": COMPONENT_MAX_POINTS["frp"],
            "detail": f"Peak Fire Radiative Power of {max_frp:.1f} MW.",
        },
        {
            "key": "persistence",
            "label": "Persistence",
            "points": pers,
            "max_points": COMPONENT_MAX_POINTS["persistence"],
            "detail": (
                f"Thermal activity spanning {active_days} active day(s) with persistence "
                f"category '{pers_cat}'."
            ),
        },
        {
            "key": "intensity",
            "label": "Thermal Intensity / Contrast",
            "points": inten,
            "max_points": COMPONENT_MAX_POINTS["intensity"],
            "detail": (
                f"Peak brightness temperature {max_ti4:.1f} K with spectral contrast "
                f"{bt_diff:.1f} K."
            ),
        },
    ]

    return {
        "components": components,
        "reliability_multiplier": multiplier,
        "false_alarm_concern": fa_indicator,
        "base_score": base_score,
        "final_score": final_score,
    }
