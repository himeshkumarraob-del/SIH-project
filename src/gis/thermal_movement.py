"""
Thermal Activity Movement and Direction Analysis Module.

Analyzes the spatial displacement and direction of thermal detection clusters
over time without assuming physical fire propagation.
"""

from __future__ import annotations

import math
from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np

from src.logging_setup import get_logger

logger = get_logger("gis.thermal_movement")

EARTH_RADIUS_KM = 6371.0088

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
            "start_latitude": round(daily.iloc[0]["lat"], 5),
            "start_longitude": round(daily.iloc[0]["lon"], 5),
            "end_latitude": round(daily.iloc[-1]["lat"], 5),
            "end_longitude": round(daily.iloc[-1]["lon"], 5),
            "total_movement_distance_km": 0.0,
            "movement_rate_km_per_day": 0.0,
            "movement_bearing_degrees": 0.0,
            "movement_direction": "INSUFFICIENT_DATA",
            "movement_confidence": "INSUFFICIENT_DATA",
            "movement_status": "INSUFFICIENT_DATA",
        }

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

        # Bearing & direction
        if dist_km > 0.01: # Non-zero movement
            bearing = calculate_initial_bearing(start_lat, start_lon, end_lat, end_lon)
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

        # Movement Confidence
        if obs_count < 4 or dist_km < 1.0:
            res["movement_confidence"] = "LOW"
        elif active_days <= 3:
            res["movement_confidence"] = "MEDIUM"
        else:
            res["movement_confidence"] = "HIGH"

        return res
