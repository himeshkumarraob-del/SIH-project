"""
Thermal Activity Movement and Direction Analysis Module.

Analyzes the spatial displacement and direction of thermal detection clusters
over time without assuming physical fire propagation.

IMPORTANT SCIENTIFIC NOTE
-------------------------
This module reports the direction of *detected thermal activity movement* only.
It does NOT claim to measure physical fire-front propagation. A satellite
thermal anomaly centroid moving over successive days can shift for many
reasons (satellite overpass geometry, detection noise, separate simultaneous
ignitions, agricultural clearing patterns, etc.). The direction estimates here
are therefore decision-support evidence, never a "confirmed fire spread" claim.

Direction confidence methodology (documented, deterministic, conservative)
---------------------------------------------------------------------------
Direction is assessed only when a cluster has at least two distinct active
observation days and a net displacement of its daily centroids at or above the
stationary threshold (default 0.5 km). Day-to-day movement "steps" are the
straight segments between consecutive daily centroids that are at least
STEP_MIN_KM (0.05 km) long (shorter segments are treated as centroid jitter).

For each step we compute a bearing (0-360). Directional consistency is the
*distance-weighted circular mean resultant length* R of the step bearings:

    R = | sum_i (w_i * e^(i*theta_i)) | / sum_i w_i

R is in [0, 1]; R = 1 means every step points the same way (perfectly
consistent), R ~ 0 means the steps point in contradictory directions.

The direction confidence score (0-100) is:

    score = round(100 * R * min(1.0, n_steps / 3.0))

so the score rewards both consistency (R) and independent confirmation from
multiple day-to-day steps. Confidence tiers map from the score together with
explicit minimum-evidence rules:

    HIGH          score >= 60 AND n_steps >= 3 AND active_days >= 4 AND R >= 0.70
                  (multiple days of strongly consistent directional movement)
    MODERATE      score >= 35
                  (direction reasonably consistent across several steps)
    PRELIMINARY   direction available but evidence weak/limited (e.g. a single
                  step, or consistency below MODERATE)
    INSUFFICIENT  no usable directional evidence (fewer than two active days,
                  zero/small displacement, or missing coordinates)

Movement pattern
----------------
    directional          R >= 0.50  -> one dominant direction across steps
    erratic              net displacement exists but steps contradict (R < 0.50)
    stationary           enough observations but net displacement below threshold
    insufficient_evidence  cannot assess (too few observations / bad data)

When movement is erratic, direction is NOT reported (direction_available=False)
because there is no single defensible direction; the confidence is PRELIMINARY
at best. When the pattern is stationary or insufficient, direction is None.
"""

from __future__ import annotations

import math
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd
import numpy as np

from src.logging_setup import get_logger

logger = get_logger("gis.thermal_movement")

EARTH_RADIUS_KM = 6371.0088

# A day-to-day centroid segment shorter than this is treated as coordinate
# jitter, not real movement (daily centroids are averaged, so residual noise is
# well below this value). Only segments >= STEP_MIN_KM count as movement steps.
STEP_MIN_KM = 0.05

# Consistency required before a single dominant direction is reported.
DIRECTIONAL_CONSISTENCY_THRESHOLD = 0.50

# Resultant length required for the HIGH confidence tier.
HIGH_R_MIN = 0.70
# Minimum independent day-to-day steps for the HIGH tier.
HIGH_STEPS_MIN = 3
# Minimum active days for the HIGH tier.
HIGH_ACTIVE_DAYS_MIN = 4

# Minimum circular mean resultant length needed for a defensible direction.
MIN_RESULTANT_FOR_DIRECTION = 0.50

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Great-Circle distance in km between two WGS84 points."""
    phi1, lambda1, phi2, lambda2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dphi = phi2 - phi1
    dlambda = lambda2 - lambda1
    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
    return 2.0 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(max(a, 0.0), 1.0)))

def calculate_initial_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate initial compass bearing in degrees [0, 360) from point 1 to point 2."""
    phi1, lambda1, phi2, lambda2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlambda = lambda2 - lambda1
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    bearing_rad = math.atan2(y, x)
    bearing_deg = math.degrees(bearing_rad)
    return (bearing_deg + 360.0) % 360.0

def bearing_to_compass_direction(bearing_deg: float) -> str:
    """Map bearing degrees [0, 360) to 8 cardinal/intercardinal compass directions."""
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int(round(bearing_deg / 45.0)) % 8
    return directions[idx]

class ThermalMovementAnalyzer:
    def __init__(self, stationary_threshold_km: float = 0.5):
        """
        Initialize movement analyzer.
        """
        self.stationary_threshold_km = stationary_threshold_km

    def analyze_clusters(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Analyze movement dynamics for detection records grouped by cluster_id.
        Returns a DataFrame containing one record per cluster with movement metrics.
        """
        required_cols = ["cluster_id", "latitude", "longitude", "acq_date"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns for movement analysis: {missing}")

        work = df.copy()
        # Drop invalid coordinates
        work = work.dropna(subset=["latitude", "longitude"])
        work = work[(work["latitude"] >= -90) & (work["latitude"] <= 90) &
                    (work["longitude"] >= -180) & (work["longitude"] <= 180)]

        # Ensure acquisition timestamp exists
        if "acquisition_datetime" in work.columns:
            work["_dt"] = pd.to_datetime(work["acquisition_datetime"], errors="coerce")
        elif "acq_time" in work.columns:
            # Combine acq_date and acq_time
            time_str = work["acq_time"].astype(str).str.zfill(4)
            work["_dt"] = pd.to_datetime(work["acq_date"].astype(str) + " " + time_str, format="%Y-%m-%d %H%M", errors="coerce")
        else:
            work["_dt"] = pd.to_datetime(work["acq_date"], errors="coerce")

        # Fallback for unparseable dates
        work["_dt"] = work["_dt"].fillna(pd.to_datetime(work["acq_date"], errors="coerce"))

        results = []

        for cluster_id, g in work.groupby("cluster_id"):
            res = self._analyze_single_cluster(int(cluster_id), g)
            results.append(res)

        out_df = pd.DataFrame(results).sort_values("cluster_id").reset_index(drop=True)
        return out_df

    def _analyze_single_cluster(self, cluster_id: int, g: pd.DataFrame) -> Dict[str, Any]:
        obs_count = len(g)
        g_sorted = g.sort_values("_dt")

        first_dt = g_sorted["_dt"].min()
        last_dt = g_sorted["_dt"].max()

        # Compute daily centroids
        daily = g_sorted.groupby(g_sorted["_dt"].dt.date).agg(
            lat=("latitude", "mean"),
            lon=("longitude", "mean"),
            count=("latitude", "count")
        ).reset_index()

        active_days = len(daily)

        # Calculate time span in days
        time_span_seconds = (last_dt - first_dt).total_seconds() if pd.notna(first_dt) and pd.notna(last_dt) else 0.0
        time_span_days = max(round(time_span_seconds / 86400.0, 3), 0.0)

        # Baseline record structure
        res = {
            "cluster_id": cluster_id,
            "observation_count": obs_count,
            "active_days": active_days,
            "first_detection": first_dt.isoformat() if pd.notna(first_dt) else str(g["acq_date"].min()),
            "last_detection": last_dt.isoformat() if pd.notna(last_dt) else str(g["acq_date"].max()),
            "time_span_days": time_span_days,
            "start_latitude": round(daily.iloc[0]["lat"], 5) if len(daily) else None,
            "start_longitude": round(daily.iloc[0]["lon"], 5) if len(daily) else None,
            "end_latitude": round(daily.iloc[-1]["lat"], 5) if len(daily) else None,
            "end_longitude": round(daily.iloc[-1]["lon"], 5) if len(daily) else None,
            "total_movement_distance_km": 0.0,
            "movement_rate_km_per_day": 0.0,
            "movement_bearing_degrees": 0.0,
            "movement_direction": "INSUFFICIENT_DATA",
            "movement_confidence": "INSUFFICIENT_DATA",
            "movement_status": "INSUFFICIENT_DATA",
            # --- Direction intelligence fields (Thermal Activity Movement Direction) ---
            "direction": None,
            "movement_pattern": "insufficient_evidence",
            "direction_confidence": "INSUFFICIENT",
            "direction_confidence_score": 0,
            "direction_available": False,
        }

        if len(daily) == 0:
            return res

        # If less than 2 active days or invalid time span -> INSUFFICIENT_DATA
        if active_days < 2 or time_span_days <= 0.0:
            return res

        # Compute distance between start and end daily centroids
        start_lat, start_lon = daily.iloc[0]["lat"], daily.iloc[0]["lon"]
        end_lat, end_lon = daily.iloc[-1]["lat"], daily.iloc[-1]["lon"]

        dist_km = haversine_distance_km(start_lat, start_lon, end_lat, end_lon)
        res["total_movement_distance_km"] = round(dist_km, 3)

        # Movement rate (km/day)
        rate = dist_km / time_span_days if time_span_days > 0 else 0.0
        res["movement_rate_km_per_day"] = round(rate, 3)

        # Day-to-day movement steps between consecutive daily centroids.
        # Only segments >= STEP_MIN_KM count as real movement steps; shorter
        # segments are centroid jitter (daily centroid averaging noise).
        step_bearings: List[float] = []
        step_dists: List[float] = []
        for i in range(len(daily) - 1):
            seg_km = haversine_distance_km(
                daily.iloc[i]["lat"], daily.iloc[i]["lon"],
                daily.iloc[i + 1]["lat"], daily.iloc[i + 1]["lon"],
            )
            if seg_km >= STEP_MIN_KM:
                step_bearings.append(calculate_initial_bearing(
                    daily.iloc[i]["lat"], daily.iloc[i]["lon"],
                    daily.iloc[i + 1]["lat"], daily.iloc[i + 1]["lon"],
                ))
                step_dists.append(seg_km)

        n_steps = len(step_bearings)

        # Bearing & direction (legacy fields preserved for existing consumers)
        net_bearing: Optional[float] = None
        if dist_km > 0.01:  # Non-zero movement
            bearing = calculate_initial_bearing(start_lat, start_lon, end_lat, end_lon)
            net_bearing = bearing
            res["movement_bearing_degrees"] = round(bearing, 2)
            res["movement_direction"] = bearing_to_compass_direction(bearing)
        else:
            res["movement_bearing_degrees"] = 0.0
            res["movement_direction"] = "STATIONARY"

        # Movement Status
        if dist_km < self.stationary_threshold_km:
            res["movement_status"] = "STATIONARY"
            if res["movement_direction"] == "INSUFFICIENT_DATA":
                res["movement_direction"] = "STATIONARY"
        else:
            res["movement_status"] = "MOVING"

        # Movement Confidence (legacy, preserved)
        if obs_count < 4 or dist_km < 1.0:
            res["movement_confidence"] = "LOW"
        elif active_days <= 3:
            res["movement_confidence"] = "MEDIUM"
        else:
            res["movement_confidence"] = "HIGH"

        # ------------------------------------------------------------------
        # Direction intelligence (novel decision-support feature).
        # A direction is only reported when the daily-centroid displacement is
        # real (>= stationary threshold, so we only evaluate MOVING clusters)
        # and the day-to-day step bearings are consistent enough (R >= 0.5).
        # ------------------------------------------------------------------
        if dist_km < self.stationary_threshold_km:
            # Stationary: enough observations, no meaningful displacement -> no direction.
            res["direction"] = None
            res["movement_pattern"] = "stationary"
            res["direction_confidence"] = "INSUFFICIENT"
            res["direction_confidence_score"] = 0
            res["direction_available"] = False
            return res

        if n_steps == 0:
            # MOVING net displacement with no usable day-to-day steps: the
            # apparent displacement comes from a single jump (jitter handling).
            # Report the pattern but treat direction as insufficient.
            res["movement_pattern"] = "erratic" if net_bearing is not None else "insufficient_evidence"
            res["direction_confidence"] = "INSUFFICIENT"
            res["direction_confidence_score"] = 0
            res["direction_available"] = False
            return res

        # Distance-weighted circular mean resultant length of step bearings.
        wsum = sum(step_dists)
        mean_sin = sum(d * math.sin(math.radians(b)) for d, b in zip(step_dists, step_bearings)) / wsum
        mean_cos = sum(d * math.cos(math.radians(b)) for d, b in zip(step_dists, step_bearings)) / wsum
        resultant = math.hypot(mean_sin, mean_cos)  # in [0, 1]
        resultant = min(max(resultant, 0.0), 1.0)

        # Confidence score: consistency (R) x independent confirmation from
        # multiple day-to-day steps (n_steps / 3, capped at 1). Documented above.
        support = min(1.0, n_steps / 3.0)
        score = round(100.0 * resultant * support)
        res["direction_confidence_score"] = int(score)

        if resultant >= DIRECTIONAL_CONSISTENCY_THRESHOLD:
            # A single dominant direction across steps.
            res["movement_pattern"] = "directional"
            res["direction_available"] = True
            # Net (start-to-end centroid) displacement bearing is the most
            # defensible single summary of the movement direction.
            if net_bearing is not None:
                res["direction"] = bearing_to_compass_direction(net_bearing)
                res["movement_bearing_degrees"] = round(net_bearing, 2)
                res["movement_direction"] = res["direction"]
            else:
                res["direction"] = None
                res["direction_available"] = False

            if (score >= 60 and n_steps >= HIGH_STEPS_MIN
                    and active_days >= HIGH_ACTIVE_DAYS_MIN and resultant >= HIGH_R_MIN):
                res["direction_confidence"] = "HIGH"
            elif score >= 35:
                res["direction_confidence"] = "MODERATE"
            else:
                res["direction_confidence"] = "PRELIMINARY"
        else:
            # Net displacement exists but day-to-day steps contradict each other.
            # No single defensible direction -> do not fabricate one.
            res["movement_pattern"] = "erratic"
            res["direction"] = None
            res["direction_available"] = False
            res["direction_confidence"] = "PRELIMINARY"

        return res
