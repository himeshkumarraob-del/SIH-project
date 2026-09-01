"""
Industrial Fire & Thermal Source Classification Engine.

Segregates thermal detection clusters into:
- Industrial-context thermal event
- Agricultural-context thermal event
- Forest/Natural-context thermal event
- Unknown / Insufficient Evidence

Combines NASA FIRMS thermal signals, spatio-temporal persistence, thermal activity movement,
OpenStreetMap industrial proximity, and land-cover context using transparent evidence scoring.

NEVER outputs unverified claims such as "Confirmed Industrial Fire".
"""

from __future__ import annotations

from typing import Dict, Any, Tuple, List
import pandas as pd
import numpy as np

from src.logging_setup import get_logger

logger = get_logger("models.industrial_classifier")

class IndustrialClassifier:
    def __init__(self, min_confidence_score: float = 0.40):
        """
        Initialize the Industrial Classifier.
        
        :param min_confidence_score: Minimum evidence score (0.0 to 1.0) required to assign
                                     a specific context label instead of Unknown / Insufficient Evidence.
        """
        self.min_confidence_score = min_confidence_score

    def classify_clusters(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Classify input dataframe of cluster records.
        Requires cluster feature/movement/AI data.
        Appends:
        - classification_label
        - classification_score
        - classification_rationale
        """
        df_out = df.copy()

        labels = []
        scores = []
        rationales = []

        for _, row in df_out.iterrows():
            lbl, score, rationale = self._classify_single_record(row)
            labels.append(lbl)
            scores.append(score)
            rationales.append(rationale)

        df_out["classification_label"] = labels
        df_out["classification_score"] = scores
        df_out["classification_rationale"] = rationales

        return df_out

    def _classify_single_record(self, row: pd.Series) -> Tuple[str, float, str]:
        # Extract features with safe defaults
        cluster_id = row.get("cluster_id", 0)
        active_days = int(row.get("active_days", 1))
        pers_cat = str(row.get("persistence_category", "isolated")).lower()
        max_frp = float(row.get("max_frp", 0.0))
        mean_frp = float(row.get("mean_frp", 0.0))
        max_ti4 = float(row.get("max_bright_ti4", 0.0))
        bt_diff = float(row.get("bt_diff_max", 0.0))
        movement_status = str(row.get("movement_status", "INSUFFICIENT_DATA")).upper()
        move_dist_km = float(row.get("total_movement_distance_km", 0.0))
        
        osm_facility = str(row.get("osm_facility_type", "UNKNOWN")).lower()
        osm_dist_km = float(row.get("osm_distance_km", float("inf")))
        land_cover = str(row.get("land_cover_class", "UNKNOWN")).lower()

        # Satellite CNN Visual Context Evidence
        sat_available = bool(row.get("satellite_image_available", False))
        sat_landcover = str(row.get("predicted_landcover_class", "UNKNOWN"))
        sat_conf = float(row.get("prediction_confidence", 0.0))

        ind_score = 0.0
        agri_score = 0.0
        forest_score = 0.0

        ind_evidence = []
        agri_evidence = []
        forest_evidence = []

        # 1. Industrial Evidence Components
        if pers_cat == "persistent" or active_days >= 4:
            ind_score += 0.30
            ind_evidence.append(f"activity is persistent (active_days={active_days})")
        elif pers_cat == "short_lived_repeated" or active_days >= 2:
            ind_score += 0.15
            ind_evidence.append(f"activity is recurring (active_days={active_days})")

        if movement_status == "STATIONARY" or (active_days >= 2 and move_dist_km < 0.5):
            ind_score += 0.25
            ind_evidence.append(f"activity is spatially stationary (displacement={move_dist_km:.2f} km)")
        
        if bt_diff >= 35.0 or max_ti4 >= 340.0:
            ind_score += 0.20
            ind_evidence.append(f"high spectral brightness temperature contrast (bt_diff={bt_diff:.1f} K)")

        has_osm_industrial = (osm_dist_km <= 2.0 and osm_facility not in ["none", "unknown"])
        if has_osm_industrial:
            ind_score += 0.25
            ind_evidence.append(f"industrial facility detected nearby ({osm_facility} at {osm_dist_km:.2f} km)")
        
        if land_cover in ["built-up", "industrial", "urban"]:
            ind_score += 0.20
            ind_evidence.append(f"land-cover context is {land_cover}")

        # Optional Satellite CNN Evidence for Industrial Context
        if sat_landcover == "Industrial" and sat_conf >= 0.50:
            ind_score += 0.20
            ind_evidence.append(f"satellite CNN visual context is Industrial (model confidence={sat_conf:.2f})")

        # 2. Agricultural Evidence Components
        if pers_cat == "isolated" or active_days <= 2:
            agri_score += 0.35
            agri_evidence.append(f"short-lived transient activity (active_days={active_days})")
        
        if 0.05 <= move_dist_km < 1.0 and movement_status != "MOVING":
            agri_score += 0.20
            agri_evidence.append("minor localized plot displacement")

        if max_frp >= 5.0 and max_frp < 25.0:
            agri_score += 0.20
            agri_evidence.append(f"moderate thermal power typical of crop burning (max_frp={max_frp:.1f} MW)")

        if land_cover in ["cropland", "agriculture", "farmland"]:
            agri_score += 0.30
            agri_evidence.append("land-cover context is agricultural cropland")

        # Optional Satellite CNN Evidence for Agricultural Context
        if sat_landcover in ["AnnualCrop", "PermanentCrop", "Pasture"] and sat_conf >= 0.50:
            agri_score += 0.20
            agri_evidence.append(f"satellite CNN visual context is {sat_landcover} (model confidence={sat_conf:.2f})")

        if has_osm_industrial:
            agri_score -= 0.15  # Penalty if right next to industrial facility

        # 3. Forest / Natural Evidence Components
        if movement_status == "MOVING" or move_dist_km >= 0.5:
            forest_score += 0.40
            forest_evidence.append(f"active spatial displacement observed (movement={move_dist_km:.2f} km)")
        
        if max_frp >= 20.0:
            forest_score += 0.25
            forest_evidence.append(f"high peak thermal power surge (max_frp={max_frp:.1f} MW)")

        if active_days >= 2 and pers_cat != "persistent":
            forest_score += 0.15
            forest_evidence.append("multi-day active fire duration")

        if land_cover in ["tree_cover", "forest", "shrubland"]:
            forest_score += 0.30
            forest_evidence.append(f"land-cover context is {land_cover}")

        # Optional Satellite CNN Evidence for Forest Context
        if sat_landcover in ["Forest", "HerbaceousVegetation"] and sat_conf >= 0.50:
            forest_score += 0.20
            forest_evidence.append(f"satellite CNN visual context is {sat_landcover} (model confidence={sat_conf:.2f})")

        if has_osm_industrial:
            forest_score -= 0.20  # Penalty if inside industrial facility zone

        # Cap scores between 0.0 and 1.0
        ind_score = float(np.clip(ind_score, 0.0, 1.0))
        agri_score = float(np.clip(agri_score, 0.0, 1.0))
        forest_score = float(np.clip(forest_score, 0.0, 1.0))

        # Decision Logic & Scientific Guardrails
        # Guardrail Rule 1: OSM proximity alone CANNOT force an Industrial-context classification!
        if has_osm_industrial and ind_score >= self.min_confidence_score:
            if movement_status == "MOVING" or (active_days == 1 and not (bt_diff >= 35.0 or max_ti4 >= 340.0)):
                ind_score = min(ind_score, 0.35)

        # Guardrail Rule 2: CNN visual prediction alone CANNOT force Industrial-context if contradicted by movement
        if sat_landcover == "Industrial" and movement_status == "MOVING":
            ind_score = min(ind_score, 0.35)

        # Select Highest Evidence Score
        scores_map = {
            "Industrial-context thermal event": (ind_score, ind_evidence),
            "Agricultural-context thermal event": (agri_score, agri_evidence),
            "Forest/Natural-context thermal event": (forest_score, forest_evidence)
        }

        best_label = "Unknown / Insufficient Evidence"
        best_score = 0.0
        best_evidence = ["insufficient or conflicting physical & contextual evidence"]

        for lbl, (score, ev_list) in scores_map.items():
            if score >= self.min_confidence_score and score > best_score:
                best_label = lbl
                best_score = round(score, 2)
                best_evidence = ev_list

        # Note missing contexts in rationale
        context_notes = []
        if osm_facility == "unknown" or osm_dist_km == float("inf"):
            context_notes.append("OSM industrial context is UNKNOWN")
        if land_cover == "unknown":
            context_notes.append("land-cover context is UNKNOWN")
        if not sat_available or sat_landcover == "UNKNOWN":
            context_notes.append("satellite observation unavailable/obscured")

        evidence_str = "; ".join(best_evidence + context_notes)
        rationale = f"{best_label}\nSupporting evidence:\n- " + "\n- ".join(best_evidence + context_notes)

        return best_label, best_score, rationale
