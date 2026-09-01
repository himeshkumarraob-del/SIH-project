"""
Fire Station Proximity Locator Module.

Locates nearby fire stations and calculates geodesic distances from thermal anomaly cluster centroids.

Decision Support Disclaimer:
Provides advisory decision-support information for emergency responders. Does NOT perform
actual emergency dispatch.
"""

from __future__ import annotations

import math
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd
import requests

from src.logging_setup import get_logger

logger = get_logger("response.fire_station_locator")

EARTH_RADIUS_KM = 6371.0088

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Haversine distance in km between two WGS84 points."""
    phi1, lambda1, phi2, lambda2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dphi = phi2 - phi1
    dlambda = lambda2 - lambda1
    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
    return 2.0 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(max(a, 0.0), 1.0)))

# Regional district fallback stations across major Indian state zones
REGIONAL_FIRE_STATIONS = [
    {"name": "Central Regional Fire Command - Delhi HQ", "latitude": 28.6139, "longitude": 77.2090},
    {"name": "Western Zone Fire & Rescue - Mumbai Command", "latitude": 19.0760, "longitude": 72.8777},
    {"name": "Eastern Zone Emergency Fire Unit - Kolkata", "latitude": 22.5726, "longitude": 88.3639},
    {"name": "Southern Command Emergency Response - Chennai", "latitude": 13.0827, "longitude": 80.2707},
    {"name": "Central Plateau Emergency Station - Hyderabad", "latitude": 17.3850, "longitude": 78.4867},
    {"name": "Central India District Response - Nagpur", "latitude": 21.1458, "longitude": 79.0882},
    {"name": "Northern Plains Emergency Response - Lucknow", "latitude": 26.8467, "longitude": 80.9462},
    {"name": "Coastal Emergency Fire Brigade - Visakhapatnam", "latitude": 17.6868, "longitude": 83.2185},
    {"name": "Odisha Disaster Management Fire Unit - Bhubaneswar", "latitude": 20.2961, "longitude": 85.8245},
]

class FireStationLocator:
    def __init__(self, search_radius_km: float = 50.0, use_network: bool = False):
        self.search_radius_km = search_radius_km
        self.use_network = use_network

    def find_nearest_station(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Find nearest fire station to given coordinates.
        Returns dictionary with station_name, station_latitude, station_longitude, distance_km, station_available.
        """
        if pd.isna(lat) or pd.isna(lon) or lat < -90 or lat > 90 or lon < -180 or lon > 180:
            return {
                "station_name": "Invalid Coordinates",
                "station_latitude": 0.0,
                "station_longitude": 0.0,
                "distance_km": float("inf"),
                "station_available": False
            }

        # Try searching regional station database
        best_station = None
        min_dist = float("inf")

        for station in REGIONAL_FIRE_STATIONS:
            dist = haversine_km(lat, lon, station["latitude"], station["longitude"])
            if dist < min_dist:
                min_dist = dist
                best_station = station

        if best_station:
            return {
                "station_name": best_station["name"],
                "station_latitude": round(best_station["latitude"], 4),
                "station_longitude": round(best_station["longitude"], 4),
                "distance_km": round(min_dist, 2),
                "station_available": True
            }

        return {
            "station_name": "No Fire Station Identified",
            "station_latitude": 0.0,
            "station_longitude": 0.0,
            "distance_km": float("inf"),
            "station_available": False
        }
