"""
OpenStreetMap (OSM) Context Extractor Module.

Queries nearby industrial infrastructure (factories, power plants, refineries, quarries,
chimneys, flare stacks) within a configurable search radius (default: 2.0 km) around
thermal cluster centroids.

Provides contextual evidence ONLY. Proximity to an industrial facility does NOT
automatically constitute proof of an industrial fire.
"""

from __future__ import annotations

import math
from typing import Dict, Any, Tuple, Optional
import pandas as pd
import requests

from src.logging_setup import get_logger

logger = get_logger("osm.osm_context")

EARTH_RADIUS_KM = 6371.0088

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Haversine distance in km between two WGS84 points."""
    phi1, lambda1, phi2, lambda2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dphi = phi2 - phi1
    dlambda = lambda2 - lambda1
    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
    return 2.0 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(max(a, 0.0), 1.0)))

class OSMContextExtractor:
    def __init__(
        self,
        radius_km: float = 2.0,
        timeout_sec: float = 3.0,
        use_network: bool = False,
        overpass_url: str = "https://overpass-api.de/api/interpreter"
    ):
        """
        Initialize the OSM Context Extractor.
        
        :param radius_km: Search radius in kilometers (default 2.0 km).
        :param timeout_sec: HTTP query timeout in seconds.
        :param use_network: Whether to attempt live Overpass API queries. If False or request fails,
                            falls back cleanly to UNKNOWN/None without crashing.
        """
        self.radius_km = radius_km
        self.timeout_sec = timeout_sec
        self.use_network = use_network
        self.overpass_url = overpass_url

    def get_cluster_context(self, lat: float, lon: float) -> Tuple[str, str, float]:
        """
        Get nearest industrial facility context for a given latitude and longitude.
        
        Returns:
            Tuple of (osm_facility_type, osm_facility_name, osm_distance_km)
        """
        if not self.use_network:
            return ("UNKNOWN", "none", float("inf"))

        try:
            # Overpass QL query searching for industrial landuse, power plants, works, refineries
            radius_meters = int(self.radius_km * 1000)
            query = f"""
            [out:json][timeout:{int(self.timeout_sec)}];
            (
              node["landuse"="industrial"](around:{radius_meters},{lat},{lon});
              way["landuse"="industrial"](around:{radius_meters},{lat},{lon});
              node["industrial"](around:{radius_meters},{lat},{lon});
              way["industrial"](around:{radius_meters},{lat},{lon});
              node["power"="plant"](around:{radius_meters},{lat},{lon});
              way["power"="plant"](around:{radius_meters},{lat},{lon});
              node["man_made"="works"](around:{radius_meters},{lat},{lon});
              way["man_made"="works"](around:{radius_meters},{lat},{lon});
              node["man_made"="refinery"](around:{radius_meters},{lat},{lon});
              way["man_made"="refinery"](around:{radius_meters},{lat},{lon});
            );
            out center 10;
            """
            resp = requests.post(self.overpass_url, data={"data": query}, timeout=self.timeout_sec)
            if resp.status_code == 200:
                data = resp.json()
                elements = data.get("elements", [])
                if not elements:
                    return ("none", "none", float("inf"))

                min_dist = float("inf")
                best_facility = "industrial"
                best_name = "none"

                for elem in elements:
                    elem_lat = elem.get("lat") or elem.get("center", {}).get("lat")
                    elem_lon = elem.get("lon") or elem.get("center", {}).get("lon")
                    if elem_lat is None or elem_lon is None:
                        continue

                    dist = haversine_km(lat, lon, elem_lat, elem_lon)
                    if dist < min_dist:
                        min_dist = dist
                        tags = elem.get("tags", {})
                        best_facility = (
                            tags.get("industrial") or
                            tags.get("man_made") or
                            tags.get("power") or
                            tags.get("landuse") or
                            "industrial"
                        )
                        best_name = tags.get("name", "none")

                if min_dist <= self.radius_km:
                    return (best_facility, best_name, round(min_dist, 3))

            return ("none", "none", float("inf"))

        except Exception as exc:
            logger.debug(f"OSM network query skipped/failed for ({lat}, {lon}): {exc}")
            return ("UNKNOWN", "none", float("inf"))

    def extract_context(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract OSM contextual columns for input dataframe containing latitude and longitude.
        Appends:
        - osm_facility_type
        - osm_facility_name
        - osm_distance_km
        """
        if "latitude" not in df.columns or "longitude" not in df.columns:
            raise ValueError("Input DataFrame missing required 'latitude' or 'longitude' columns.")

        df_out = df.copy()
        fac_types = []
        fac_names = []
        fac_dists = []

        for _, row in df_out.iterrows():
            lat = row.get("latitude")
            lon = row.get("longitude")
            if pd.isna(lat) or pd.isna(lon):
                fac_types.append("UNKNOWN")
                fac_names.append("none")
                fac_dists.append(float("inf"))
            else:
                ftype, fname, fdist = self.get_cluster_context(float(lat), float(lon))
                fac_types.append(ftype)
                fac_names.append(fname)
                fac_dists.append(fdist)

        df_out["osm_facility_type"] = fac_types
        df_out["osm_facility_name"] = fac_names
        df_out["osm_distance_km"] = fac_dists

        return df_out
