"""
Anomaly Explainer Module.

Generates deterministic, transparent, and evidence-based explanations
for thermal anomalies detected by the Isolation Forest model.

Provides characterizations such as HIGH_THERMAL_INTENSITY or
PERSISTENT_THERMAL_ACTIVITY without asserting unsupported physical causes.
"""

from __future__ import annotations

import pandas as pd
from typing import Dict, Any, List

class ThermalAnomalyExplainer:
    def __init__(self, thresholds: Dict[str, float] = None):
        """
        Initialize the explainer with thresholds for various factors.
        These thresholds determine when a factor is considered "elevated" or "high".
        """
        # Default thresholds based on typical VIIRS I-band data statistics
        self.thresholds = {
            "max_bright_ti4": 340.0,  # High brightness temperature (K)
            "bt_diff_max": 45.0,      # High spectral contrast (K)
            "max_frp": 15.0,          # High Fire Radiative Power (MW)
            "mean_frp": 10.0,
            "active_days": 4.0,       # Sustained persistence (days)
        }
        if thresholds:
            self.thresholds.update(thresholds)

    def explain(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process the dataframe containing anomaly results and append explanation columns:
        - anomaly_characterization
        - explanation
        - contributing_factors
        """
        required_cols = [
            "abnormality_level", "max_bright_ti4", "bt_diff_max", 
            "mean_frp", "max_frp", "active_days", "duration_days"
        ]
        
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns for explanation: {missing}")

        df_out = df.copy()
        
        characterizations = []
        explanations = []
        factors_list = []

        for _, row in df.iterrows():
            char, exp, factors = self._explain_single_record(row)
            characterizations.append(char)
            explanations.append(exp)
            factors_list.append(factors)

        df_out["anomaly_characterization"] = characterizations
        df_out["explanation"] = explanations
        df_out["contributing_factors"] = factors_list

        return df_out

    def _explain_single_record(self, row: pd.Series) -> tuple[str, str, str]:
        # If the model marked this as normal, the explanation is simple.
        if row.get("abnormality_level", "NORMAL") == "NORMAL":
            return (
                "NORMAL_THERMAL_ACTIVITY",
                "Thermal activity falls within normal statistical bounds.",
                "none"
            )

        # Identify contributing factors
        factors = []
        descriptions = []
        
        # 1. Thermal Intensity
        intensity_factor = False
        if row.get("max_bright_ti4", 0) >= self.thresholds["max_bright_ti4"]:
            factors.append("max_bright_ti4")
            intensity_factor = True
        if row.get("bt_diff_max", 0) >= self.thresholds["bt_diff_max"]:
            factors.append("bt_diff_max")
            intensity_factor = True
            
        if intensity_factor:
            descriptions.append("elevated thermal intensity")
            
        # 2. Thermal Energy
        energy_factor = False
        if row.get("max_frp", 0) >= self.thresholds["max_frp"]:
            factors.append("max_frp")
            energy_factor = True
        if row.get("mean_frp", 0) >= self.thresholds["mean_frp"]:
            factors.append("mean_frp")
            energy_factor = True
            
        if energy_factor:
            descriptions.append("elevated thermal energy (FRP)")

        # 3. Persistence / Temporal
        persistence_factor = False
        recurring_factor = False
        if row.get("active_days", 0) >= self.thresholds["active_days"]:
            factors.append("active_days")
            persistence_factor = True
            descriptions.append("persistent multi-day activity")
        elif row.get("active_days", 0) >= 2 and row.get("duration_days", 0) > self.thresholds["active_days"]:
            factors.append("duration_days")
            recurring_factor = True
            descriptions.append("recurring thermal activity over an extended duration")

        # Determine characterization label
        num_major_factors = sum([intensity_factor, energy_factor, persistence_factor, recurring_factor])
        
        if num_major_factors > 1:
            characterization = "MULTI_FACTOR_ANOMALY"
        elif persistence_factor:
            characterization = "PERSISTENT_THERMAL_ACTIVITY"
        elif recurring_factor:
            characterization = "RECURRING_THERMAL_ACTIVITY"
        elif intensity_factor:
            if row.get("active_days", 0) <= 2:
                characterization = "SHORT_LIVED_EXTREME_EVENT"
            else:
                characterization = "HIGH_THERMAL_INTENSITY"
        elif energy_factor:
            characterization = "HIGH_THERMAL_ENERGY"
        else:
            # Fallback if anomaly was flagged but doesn't meet specific hard thresholds
            characterization = "STATISTICAL_ANOMALY"
            descriptions.append("unusual multi-variate statistical signature")
            factors.append("multivariate_combination")

        # Construct explanation string
        level = row.get("abnormality_level", "ELEVATED").capitalize()
        if descriptions:
            desc_str = " and ".join([", ".join(descriptions[:-1]), descriptions[-1]] if len(descriptions) > 1 else descriptions)
            explanation = f"{level} abnormality primarily associated with {desc_str}."
        else:
            explanation = f"{level} abnormality with unusual statistical signature."
            
        factors_str = ",".join(factors) if factors else "none"

        return characterization, explanation, factors_str
