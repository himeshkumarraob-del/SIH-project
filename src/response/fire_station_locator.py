"""
Fire Station Proximity Locator Module.

Locates the nearest REAL fire station (OpenStreetMap amenity=fire_station,
fetched by scripts/fetch_fire_stations.py into data/processed/fire_stations.csv)
and calculates geodesic distances from thermal anomaly cluster centroids.

No stations are fabricated: if the real station dataset is missing, or no real
station lies within the search radius, the locator reports that honestly.

Decision Support Disclaimer:
Provides advisory decision-support information for emergency responders. Does NOT perform
actual emergency dispatch.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd

from src.logging_setup import get_logger

logger = get_logger("response.fire_station_locator")

EARTH_RADIUS_KM = 6371.0088

# Location of the real OSM fire-station cache (project root: ai-engine/)
DEFAULT_STATIONS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "fire_stations.csv"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Haversine distance in km between two WGS84 points."""
    phi1, lambda1, phi2, lambda2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dphi = phi2 - phi1
    dlambda = lambda2 - lambda1
    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
    return 2.0 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(max(a, 0.0), 1.0)))


class FireStationLocator:
    """Locate the nearest REAL fire station from the cached OSM dataset."""

    _stations_cache: Optional[pd.DataFrame] = None
    _stations_cache_path: Optional[Path] = None

    def __init__(self, search_radius_km: float = 50.0, use_network: bool = False,
                 stations_path: Optional[Path] = None):
        self.search_radius_km = search_radius_km
        self.use_network = use_network  # retained for signature compatibility
        self.stations_path = stations_path or DEFAULT_STATIONS_PATH
        self._load_stations(self.stations_path)

    @classmethod
    def _load_stations(cls, path: Path) -> None:
        """Load the real fire-station CSV once per path (class-level cache)."""
        if cls._stations_cache is not None and cls._stations_cache_path == path:
            return
        cls._stations_cache = None
        cls._stations_cache_path = path
        if not path.exists():
            logger.warning(f"Fire-station dataset not found at {path}. Station lookup will report unavailable.")
            return
        try:
            df = pd.read_csv(path)
            if {"latitude", "longitude"}.issubset(df.columns):
                cls._stations_cache = df[["name", "latitude", "longitude"]].dropna(subset=["latitude", "longitude"])
                logger.info(f"Loaded {len(cls._stations_cache)} real fire stations from {path}")
            else:
                logger.warning(f"Fire-station dataset at {path} is missing lat/lon columns.")
        except Exception as exc:
            logger.warning(f"Failed to load fire-station dataset {path}: {exc}")
            cls._stations_cache = None

    def _stations(self) -> pd.DataFrame:
        self._load_stations(self.stations_path)
        return self._stations_cache if self._stations_cache is not None else pd.DataFrame()

    def find_nearest_station(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Find the nearest REAL fire station to given coordinates within the search radius.

        Returns dictionary with station_name, station_latitude, station_longitude,
        distance_km, station_available. Never fabricates a station — a missing
        dataset or an empty search radius is reported honestly.
        """
        if pd.isna(lat) or pd.isna(lon) or lat < -90 or lat > 90 or lon < -180 or lon > 180:
            return {
                "station_name": "Invalid Coordinates",
                "station_latitude": 0.0,
                "station_longitude": 0.0,
                "distance_km": float("inf"),
                "station_available": False
            }

        stations = self._stations()
        if stations.empty:
            return {
                "station_name": "Fire station data unavailable",
                "station_latitude": 0.0,
                "station_longitude": 0.0,
                "distance_km": float("inf"),
                "station_available": False
            }

        best_name = None
        best_lat = 0.0
        best_lon = 0.0
        min_dist = float("inf")

        for _, s in stations.iterrows():
            dist = haversine_km(lat, lon, float(s["latitude"]), float(s["longitude"]))
            if dist < min_dist:
                min_dist = dist
                best_name = str(s["name"])
                best_lat = float(s["latitude"])
                best_lon = float(s["longitude"])

        if best_name is not None and min_dist <= self.search_radius_km:
            return {
                "station_name": best_name,
                "station_latitude": round(best_lat, 4),
                "station_longitude": round(best_lon, 4),
                "distance_km": round(min_dist, 2),
                "station_available": True
            }

        return {
            "station_name": f"No fire station within {self.search_radius_km:.0f} km",
            "station_latitude": 0.0,
            "station_longitude": 0.0,
            "distance_km": float("inf"),
            "station_available": False
        }
