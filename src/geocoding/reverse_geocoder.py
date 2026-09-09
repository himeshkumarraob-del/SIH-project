"""
Real reverse-geocoding module for ThermalWatch Local Location Intelligence.

Uses OpenStreetMap Nominatim API with persistent caching and rate-limiting.
Strictly returns real geospatial data or "Not available" when fields are missing.
NEVER fabricates addresses, landmarks, or street names.
"""

from __future__ import annotations

import json
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

import requests
from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("src.geocoding.reverse_geocoder")


@dataclass
class ReverseGeocodeResult:
    latitude: float
    longitude: float
    state: str = "Not available"
    district: str = "Not available"
    city_town: str = "Not available"
    locality_colony: str = "Not available"
    street_road: str = "Not available"
    landmark: str = "Not available"
    postcode: str = "Not available"
    display_name: str = "Not available"
    formatted_location_header: str = "Not available"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ReverseGeocoder:
    """Thread-safe reverse geocoder with file-backed caching and rate limiting."""

    _instance: Optional[ReverseGeocoder] = None
    _lock = threading.Lock()

    def __init__(self, cache_dir: Optional[Path] = None, rate_limit_seconds: float = 1.0):
        if cache_dir is None:
            cache_dir = get_config().processed_data_dir
        self.cache_file = cache_dir / "geocoding_cache.json"
        self.rate_limit_seconds = rate_limit_seconds
        self._last_request_time = 0.0
        self._cache: Dict[str, Dict[str, Any]] = self._load_cache()

    @classmethod
    def get_instance(cls, cache_dir: Optional[Path] = None) -> ReverseGeocoder:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(cache_dir=cache_dir)
            return cls._instance

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning(f"Failed to load geocoding cache from {self.cache_file}: {exc}")
        return {}

    def _save_cache(self) -> None:
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.warning(f"Failed to save geocoding cache to {self.cache_file}: {exc}")

    def _coord_key(self, lat: float, lon: float) -> str:
        return f"{lat:.4f},{lon:.4f}"

    def reverse_geocode(self, lat: float, lon: float) -> ReverseGeocodeResult:
        """Reverse geocode latitude and longitude into structured location fields."""
        key = self._coord_key(lat, lon)

        with self._lock:
            if key in self._cache:
                cached_data = self._cache[key]
                if cached_data.get("state") != "Not available" or cached_data.get("city_town") != "Not available":
                    return ReverseGeocodeResult(**cached_data)

        # Rate limiting outbound requests to Nominatim (max 1 req/sec)
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)

        url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}"
        headers = {"User-Agent": "ThermalWatch-Emergency-Response-Intelligence/2.0 (research-contact: info@thermalwatch.org)"}

        try:
            self._last_request_time = time.time()
            res = requests.get(url, headers=headers, timeout=5.0)
            if res.status_code == 200:
                data = res.json()
                result = self._parse_nominatim_response(lat, lon, data)
            else:
                logger.warning(f"Nominatim returned status {res.status_code} for ({lat}, {lon})")
                result = self._fallback_result(lat, lon)
        except Exception as exc:
            logger.warning(f"Reverse geocoding network request failed for ({lat}, {lon}): {exc}")
            result = self._fallback_result(lat, lon)

        with self._lock:
            if result.state != "Not available" or result.city_town != "Not available":
                self._cache[key] = result.to_dict()
                self._save_cache()

        return result


    def _parse_nominatim_response(self, lat: float, lon: float, data: Dict[str, Any]) -> ReverseGeocodeResult:
        address = data.get("address", {})

        state = address.get("state") or address.get("state_district") or "Not available"
        district = (
            address.get("state_district")
            or address.get("county")
            or address.get("district")
            or "Not available"
        )
        city_town = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
            or address.get("hamlet")
            or "Not available"
        )
        locality = (
            address.get("suburb")
            or address.get("neighbourhood")
            or address.get("residential")
            or address.get("quarter")
            or address.get("locality")
            or "Not available"
        )
        street = (
            address.get("road")
            or address.get("pedestrian")
            or address.get("highway")
            or "Not available"
        )
        landmark = (
            address.get("amenity")
            or address.get("building")
            or address.get("historic")
            or address.get("leisure")
            or address.get("tourism")
            or "Not available"
        )
        postcode = address.get("postcode") or "Not available"
        display_name = data.get("display_name") or "Not available"

        # Format header e.g. "Surandai, Tenkasi District, Tamil Nadu"
        header_parts = []
        if city_town != "Not available":
            header_parts.append(city_town)
        elif locality != "Not available":
            header_parts.append(locality)

        if district != "Not available" and district not in header_parts:
            header_parts.append(district)
        if state != "Not available" and state not in header_parts:
            header_parts.append(state)

        formatted_header = ", ".join(header_parts) if header_parts else f"Coordinates: {lat:.4f}, {lon:.4f}"

        return ReverseGeocodeResult(
            latitude=lat,
            longitude=lon,
            state=state,
            district=district,
            city_town=city_town,
            locality_colony=locality,
            street_road=street,
            landmark=landmark,
            postcode=postcode,
            display_name=display_name,
            formatted_location_header=formatted_header,
        )

    def _fallback_result(self, lat: float, lon: float) -> ReverseGeocodeResult:
        return ReverseGeocodeResult(
            latitude=lat,
            longitude=lon,
            formatted_location_header=f"Coordinates: {lat:.4f}, {lon:.4f}",
        )
