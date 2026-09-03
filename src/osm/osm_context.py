"""
OpenStreetMap (OSM) Context Extractor Module.

Queries nearby industrial infrastructure (factories, power plants, refineries, quarries,
chimneys, flare stacks) within a configurable search radius (default: 2.0 km) around
thermal cluster centroids.

Provides contextual evidence ONLY. Proximity to an industrial facility does NOT
automatically constitute proof of an industrial fire.

Query Status Values (osm_query_status):
  "found"           — Overpass returned >=1 industrial facility within radius
  "not_found"       — Overpass query succeeded, no industrial facilities within radius
  "timeout"         — Overpass query timed out
  "http_error"      — Overpass returned a non-200 HTTP status
  "parse_error"     — Overpass response was not valid JSON
  "network_error"   — Network/connection error (DNS, connection refused, etc.)
  "disabled"        — use_network=False, no query attempted
  "missing_coords"  — Latitude/longitude were NaN or missing
  "unavailable"     — Cached result from a previous failed lookup (retryable)

Cache Status Values (BatchedOSMExtractor osm_cache.json):
  "found"           — at least one industrial facility within radius
  "not_found"       — query succeeded, no facility within radius
  "unavailable"     — network/HTTP failure, cached with timestamp (retried later)
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
import pandas as pd
import requests

from src.logging_setup import get_logger

logger = get_logger("osm.osm_context")

EARTH_RADIUS_KM = 6371.0088

# User-Agent header required by Overpass API to avoid 406/rate-limiting
_REQUEST_HEADERS = {"User-Agent": "SIH-ThermalIntel/1.0 (academic research)"}

# Unavailable (network/HTTP error) cache entries are treated as valid for this
# long; after that they are re-queried on the next run instead of being
# permanently stuck as unavailable.
_CACHE_RETRY_HOURS = 1.0


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
        timeout_sec: float = 15.0,
        use_network: bool = False,
        max_retries: int = 2,
        retry_delay_sec: float = 2.0,
        inter_request_delay_sec: float = 1.0,
        overpass_url: str = "https://overpass-api.de/api/interpreter"
    ):
        """
        Initialize the OSM Context Extractor.
        
        :param radius_km: Search radius in kilometers (default 2.0 km).
        :param timeout_sec: HTTP query timeout in seconds (default 15s for Overpass).
        :param use_network: Whether to attempt live Overpass API queries.
        :param max_retries: Number of retries on rate-limit (HTTP 429) or timeout.
        :param retry_delay_sec: Base delay between retries (doubles each retry).
        :param inter_request_delay_sec: Delay between consecutive Overpass requests to avoid rate limiting.
        :param overpass_url: Overpass API endpoint URL.
        """
        self.radius_km = radius_km
        self.timeout_sec = timeout_sec
        self.use_network = use_network
        self.max_retries = max_retries
        self.retry_delay_sec = retry_delay_sec
        self.inter_request_delay_sec = inter_request_delay_sec
        self.overpass_url = overpass_url
        self._last_request_time = 0.0

    def _build_query(self, lat: float, lon: float) -> str:
        """Build the Overpass QL query for industrial infrastructure near a point."""
        radius_meters = int(self.radius_km * 1000)
        return f"""
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

    def _parse_elements(self, elements: list, lat: float, lon: float) -> Tuple[str, str, float]:
        """Parse Overpass elements and return the nearest facility within radius."""
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
                    tags.get("industrial")
                    or tags.get("man_made")
                    or tags.get("power")
                    or tags.get("landuse")
                    or "industrial"
                )
                best_name = tags.get("name", "none")

        if min_dist <= self.radius_km:
            return (best_facility, best_name, round(min_dist, 3))

        return ("none", "none", float("inf"))

    def get_cluster_context(self, lat: float, lon: float) -> Tuple[str, str, float]:
        """
        Get nearest industrial facility context for a given latitude and longitude.

    Returns:
        Tuple of (osm_facility_type, osm_facility_name, osm_distance_km)

    Query status is available via the last_query_status attribute after calling.
    """

        self.last_query_status = "disabled"

        if not self.use_network:
            self.last_query_status = "disabled"
            return ("UNKNOWN", "none", float("inf"))

        query = self._build_query(lat, lon)
        last_exc = None

        for attempt in range(1 + self.max_retries):
            try:
                resp = requests.post(
                    self.overpass_url,
                    data={"data": query},
                    headers=_REQUEST_HEADERS,
                    timeout=self.timeout_sec,
                )

                # Handle rate limiting (429) — retry with backoff
                if resp.status_code == 429:
                    wait = self.retry_delay_sec * (2 ** attempt)
                    logger.warning(
                        f"Overpass rate-limited (429) for ({lat}, {lon}), "
                        f"retrying in {wait:.1f}s (attempt {attempt + 1})"
                    )
                    time.sleep(wait)
                    last_exc = RuntimeError("Rate limited (HTTP 429)")
                    continue

                # Handle server errors (502, 504) — retry with backoff
                if resp.status_code in (502, 504):
                    wait = self.retry_delay_sec * (2 ** attempt)
                    logger.warning(
                        f"Overpass server error {resp.status_code} for ({lat}, {lon}), "
                        f"retrying in {wait:.1f}s (attempt {attempt + 1})"
                    )
                    time.sleep(wait)
                    last_exc = RuntimeError(f"Server error HTTP {resp.status_code}")
                    continue

                # Handle non-200 HTTP errors
                if resp.status_code != 200:
                    self.last_query_status = "http_error"
                    logger.warning(
                        f"Overpass HTTP {resp.status_code} for ({lat}, {lon})"
                    )
                    return ("UNKNOWN", "none", float("inf"))

                # Parse JSON response
                try:
                    data = resp.json()
                except ValueError:
                    self.last_query_status = "parse_error"
                    logger.warning(f"Overpass non-JSON response for ({lat}, {lon})")
                    return ("UNKNOWN", "none", float("inf"))

                elements = data.get("elements", [])

                if not elements:
                    self.last_query_status = "not_found"
                    return ("none", "none", float("inf"))

                facility, name, dist = self._parse_elements(elements, lat, lon)

                if facility != "none":
                    self.last_query_status = "found"
                else:
                    self.last_query_status = "not_found"

                return (facility, name, dist)

            except requests.exceptions.Timeout:
                last_exc = requests.exceptions.Timeout(
                    f"Overpass timeout for ({lat}, {lon})"
                )
                wait = self.retry_delay_sec * (2 ** attempt)
                logger.warning(
                    f"Overpass timeout for ({lat}, {lon}), "
                    f"retrying in {wait:.1f}s (attempt {attempt + 1})"
                )
                time.sleep(wait)
                continue

            except requests.exceptions.ConnectionError as exc:
                self.last_query_status = "network_error"
                logger.warning(f"Overpass connection error for ({lat}, {lon}): {exc}")
                return ("UNKNOWN", "none", float("inf"))

            except requests.exceptions.RequestException as exc:
                self.last_query_status = "network_error"
                logger.warning(f"Overpass request error for ({lat}, {lon}): {exc}")
                return ("UNKNOWN", "none", float("inf"))

            except Exception as exc:
                self.last_query_status = "network_error"
                logger.warning(f"Overpass unexpected error for ({lat}, {lon}): {exc}")
                return ("UNKNOWN", "none", float("inf"))

        # All retries exhausted (timeout or 429)
        self.last_query_status = "timeout" if isinstance(last_exc, requests.exceptions.Timeout) else "network_error"
        logger.error(
            f"Overpass query failed after {1 + self.max_retries} attempts for ({lat}, {lon}): {last_exc}"
        )
        return ("UNKNOWN", "none", float("inf"))

    def extract_context(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract OSM contextual columns for input dataframe containing latitude and longitude.
        Appends:
        - osm_facility_type
        - osm_facility_name
        - osm_distance_km
        - osm_query_status
        """
        if "latitude" not in df.columns or "longitude" not in df.columns:
            raise ValueError("Input DataFrame missing required 'latitude' or 'longitude' columns.")

        df_out = df.copy()
        fac_types = []
        fac_names = []
        fac_dists = []
        query_statuses = []

        total = len(df_out)
        queried = 0
        found_count = 0
        not_found_count = 0
        error_count = 0

        for idx, (_, row) in enumerate(df_out.iterrows()):
            lat = row.get("latitude")
            lon = row.get("longitude")
            if pd.isna(lat) or pd.isna(lon):
                fac_types.append("UNKNOWN")
                fac_names.append("none")
                fac_dists.append(float("inf"))
                query_statuses.append("missing_coords")
            else:
                # Rate-limit: enforce minimum delay between consecutive requests
                if self.use_network and idx > 0:
                    elapsed = time.time() - self._last_request_time
                    if elapsed < self.inter_request_delay_sec:
                        time.sleep(self.inter_request_delay_sec - elapsed)

                ftype, fname, fdist = self.get_cluster_context(float(lat), float(lon))
                self._last_request_time = time.time()
                fac_types.append(ftype)
                fac_names.append(fname)
                fac_dists.append(fdist)
                query_statuses.append(self.last_query_status)
                queried += 1

                if self.last_query_status == "found":
                    found_count += 1
                elif self.last_query_status == "not_found":
                    not_found_count += 1
                else:
                    error_count += 1

            # Progress logging every 100 clusters
            if (idx + 1) % 100 == 0 or (idx + 1) == total:
                logger.info(
                    f"OSM progress: {idx + 1}/{total} clusters processed "
                    f"({found_count} found, {not_found_count} not found, {error_count} errors)"
                )

        df_out["osm_facility_type"] = fac_types
        df_out["osm_facility_name"] = fac_names
        df_out["osm_distance_km"] = fac_dists
        df_out["osm_query_status"] = query_statuses

        # Summary logging
        logger.info(
            f"OSM extraction complete: {queried} queried, "
            f"{found_count} facilities found, {not_found_count} no facility, "
            f"{error_count} lookup failures"
        )

        return df_out


# ---------------------------------------------------------------------------
# Batched / Cached OSM Extractor (tile-based)
# ---------------------------------------------------------------------------
#
# Architecture:
#   1792 thermal clusters
#       → group ONLY the occupied area into small geographic tiles (0.25 deg)
#       → ONE compact bounding-box Overpass query per occupied tile
#         (landuse=industrial, industrial=*, power=plant, man_made=works/refinery)
#       → never per-cluster requests, never `around`, never empty areas
#       → cache each successful tile result in data/processed/osm_cache.json
#       → match every cluster to its tile's facilities LOCALLY (2 km radius)
#
# Failure handling: bounded retries with backoff across Overpass mirrors; if a
# tile still fails, retry ONCE as 4 smaller sub-tiles; any tile that still
# fails is cached as "unavailable" — NEVER as "no facility". Unavailable
# entries expire after _CACHE_RETRY_HOURS and are re-queried on later runs.
#
# This replaces the old per-cluster and multi-around patterns.
# ---------------------------------------------------------------------------

# Overpass query tags we care about (same as the per-cluster extractor)
_OSM_INDUSTRIAL_TAGS = [
    # (element_type, key, value) — exact tag match
    ("node", "landuse", "industrial"),
    ("way", "landuse", "industrial"),
    ("node", "power", "plant"),
    ("way", "power", "plant"),
    ("node", "man_made", "works"),
    ("way", "man_made", "works"),
    ("node", "man_made", "refinery"),
    ("way", "man_made", "refinery"),
    # (element_type, key) — any value for this key
    ("node", "industrial"),
    ("way", "industrial"),
]


def _grid_key(lat: float, lon: float, grid_size: float) -> str:
    """Return a string grid-cell identifier for a coordinate."""
    cell_lat = math.floor(lat / grid_size) * grid_size
    cell_lon = math.floor(lon / grid_size) * grid_size
    return f"{cell_lat:.4f}_{cell_lon:.4f}"


def _build_bbox_query(south: float, west: float, north: float, east: float,
                       timeout_sec: int = 60) -> str:
    """Build an Overpass QL query for a bounding box."""
    lines = [f"[out:json][timeout:{timeout_sec}];", "("]
    for tag_spec in _OSM_INDUSTRIAL_TAGS:
        elem_type = tag_spec[0]
        if len(tag_spec) == 3:
            key, value = tag_spec[1], tag_spec[2]
            lines.append(f'  {elem_type}["{key}"="{value}"]({south},{west},{north},{east});')
        elif len(tag_spec) == 2:
            key = tag_spec[1]
            lines.append(f'  {elem_type}["{key}"]({south},{west},{north},{east});')
    lines.append(");")
    lines.append("out center;")
    return "\n".join(lines)



def _cache_key(lat: float, lon: float, radius_km: float = 2.0, version: str = "v2") -> str:
    """Generate a cache key accounting for rounded coordinates, radius, and query version."""
    return f"{lat:.4f}_{lon:.4f}_r{radius_km:.1f}_{version}"


def _find_nearest_facility(lat: float, lon: float, elements: list,
                            radius_km: float = 2.0) -> Tuple[str, str, float]:
    """
    From a list of Overpass elements, find the nearest industrial facility
    within *radius_km* of (lat, lon).
    Returns (facility_type, facility_name, distance_km).
    """
    min_dist = float("inf")
    best_facility = "none"
    best_name = "none"

    for elem in elements:
        elem_lat = elem.get("lat") or (elem.get("center") or {}).get("lat")
        elem_lon = elem.get("lon") or (elem.get("center") or {}).get("lon")
        if elem_lat is None or elem_lon is None:
            continue

        dist = haversine_km(lat, lon, elem_lat, elem_lon)
        if dist < min_dist:
            min_dist = dist
            tags = elem.get("tags", {})
            best_facility = (
                tags.get("industrial")
                or tags.get("man_made")
                or tags.get("power")
                or tags.get("landuse")
                or "industrial"
            )
            best_name = tags.get("name", "none")

    if min_dist <= radius_km:
        return (best_facility, best_name, round(min_dist, 3))
    return ("none", "none", float("inf"))


class BatchedOSMExtractor:
    """
    Batched + cached OSM extractor using small geographic tile (bounding-box)
    Overpass queries.

    Cluster centroids are grouped into geographic grid tiles (default 0.25 deg).
    ONE compact bounding-box Overpass query is made per occupied tile — never
    per cluster, never for empty areas. Clusters are matched to their tile's
    OSM industrial features LOCALLY using the configured search radius (2 km).

    On 429/504/timeout the tile is retried (bounded backoff) across fallback
    Overpass mirrors; if it still fails, it is retried ONCE as 4 smaller
    sub-tiles; sub-tiles that still fail are cached as "unavailable" — never
    as "no facility". Unavailable entries carry a timestamp and are re-queried
    on later runs after _CACHE_RETRY_HOURS.

    Cache statuses distinguish:
      - "found"       — query succeeded, tile has >= 1 industrial element
      - "not_found"   — query succeeded, tile has 0 industrial elements
      - "unavailable" — network/HTTP failure (cached with timestamp)
    """

    # Overpass mirrors, primary (fastest/most reliable) first.
    DEFAULT_OVERPASS_URLS = [
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]

    def __init__(
        self,
        radius_km: float = 2.0,
        batch_size: int = 50,  # retained for signature compatibility (unused in tile mode)
        grid_size_deg: float = 0.25,
        use_network: bool = True,
        timeout_sec: int = 20,
        max_retries: int = 1,
        retry_delay_sec: float = 2.0,
        inter_request_delay_sec: float = 0.8,
        max_workers: int = 6,
        overpass_url: Optional[str] = None,
        overpass_urls: Optional[List[str]] = None,
        cache_path: Optional[Path] = None,
    ):
        self.radius_km = radius_km
        self.batch_size = batch_size
        self.grid_size_deg = grid_size_deg
        self.use_network = use_network
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.retry_delay_sec = retry_delay_sec
        self.inter_request_delay_sec = inter_request_delay_sec
        self.max_workers = max_workers

        if overpass_urls is None:
            overpass_urls = list(self.DEFAULT_OVERPASS_URLS)
        if overpass_url:
            overpass_urls = [overpass_url] + [u for u in overpass_urls if u != overpass_url]
        self.overpass_urls = overpass_urls

        if cache_path is None:
            cache_path = Path("data/processed/osm_cache.json")
        self.cache_path = cache_path
        self._cache: Dict[str, dict] = {}
        self._load_cache()

        # Thread-safety for concurrent tile resolution
        self._cache_lock = threading.Lock()
        self._rate_lock = threading.Lock()
        self._next_request_time = 0.0

        # Telemetry counters
        self.total_queries = 0
        self.total_cache_hits = 0
        self.fallback_tile_splits = 0
        self.endpoint_failovers = 0

    def _load_cache(self) -> None:
        """Load cached Overpass results from disk."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                # Drop stale-format entries (pre-tile v2 per-point cache)
                self._cache = {k: v for k, v in loaded.items() if v.get("version") == "v3"}
                if len(self._cache) != len(loaded):
                    logger.info(
                        f"Pruned {len(loaded) - len(self._cache)} stale-format cache entries "
                        f"(kept {len(self._cache)} v3 tile entries)"
                    )
                logger.info(f"Loaded OSM cache: {len(self._cache)} entries from {self.cache_path}")
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(f"Failed to load OSM cache, starting fresh: {exc}")
                self._cache = {}
        else:
            self._cache = {}

    def _save_cache(self) -> None:
        """Persist cache to disk (atomic write)."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.cache_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=None)
        tmp_path.replace(self.cache_path)

    def _build_tile_query(self, cell_lat: float, cell_lon: float, grid_size: float) -> str:
        """Compact bounding-box Overpass query for one tile.

        The bbox is expanded by the search radius so facilities just across a
        tile boundary are still matched locally within radius_km.
        """
        margin = max(self.radius_km / 111.0, 0.02)  # ~2 km in degrees
        south = max(cell_lat - margin, -90.0)
        west = max(cell_lon - margin, -180.0)
        north = min(cell_lat + grid_size + margin, 90.0)
        east = min(cell_lon + grid_size + margin, 180.0)
        t = int(self.timeout_sec)
        return (
            f"[out:json][timeout:{t}];\n"
            "(\n"
            f'  nwr["landuse"="industrial"]({south:.4f},{west:.4f},{north:.4f},{east:.4f});\n'
            f'  nwr["industrial"]({south:.4f},{west:.4f},{north:.4f},{east:.4f});\n'
            f'  nwr["power"="plant"]({south:.4f},{west:.4f},{north:.4f},{east:.4f});\n'
            f'  nwr["man_made"~"^(works|refinery)$"]({south:.4f},{west:.4f},{north:.4f},{east:.4f});\n'
            ");\n"
            "out center;"
        )

    def _post_overpass(self, query: str) -> Tuple[Optional[list], Optional[int]]:
        """POST an Overpass query with bounded retries and mirror failover.

        Returns (elements, status_code). 429/502/503/504/timeouts are retried
        with exponential backoff (up to max_retries), then the next mirror is
        tried. Never retries indefinitely.
        """
        last_url = len(self.overpass_urls) - 1
        for ei, url in enumerate(self.overpass_urls):
            for attempt in range(1 + self.max_retries):
                try:
                    resp = requests.post(
                        url,
                        data={"data": query},
                        headers=_REQUEST_HEADERS,
                        timeout=self.timeout_sec + 10,
                    )
                    if resp.status_code == 429:
                        wait = self.retry_delay_sec * (2 ** attempt)
                        logger.warning(f"Overpass 429 at {url}, retrying in {wait:.1f}s (attempt {attempt + 1})")
                        time.sleep(wait)
                        continue
                    if resp.status_code in (502, 503, 504):
                        wait = self.retry_delay_sec * (2 ** attempt)
                        logger.warning(f"Overpass {resp.status_code} at {url}, retrying in {wait:.1f}s (attempt {attempt + 1})")
                        time.sleep(wait)
                        continue
                    if resp.status_code != 200:
                        logger.warning(f"Overpass HTTP {resp.status_code} at {url}")
                        return None, resp.status_code
                    try:
                        return resp.json().get("elements", []), 200
                    except ValueError:
                        logger.warning(f"Overpass non-JSON response at {url}")
                        return None, 500
                except requests.exceptions.Timeout:
                    wait = self.retry_delay_sec * (2 ** attempt)
                    logger.warning(f"Overpass timeout at {url}, retrying in {wait:.1f}s (attempt {attempt + 1})")
                    time.sleep(wait)
                    continue
                except Exception as exc:
                    logger.warning(f"Overpass request exception at {url}: {exc}")
                    break  # try next mirror
            if ei < last_url:
                with self._cache_lock:
                    self.endpoint_failovers += 1
        return None, 504

    def _tile_cell(self, lat: float, lon: float, grid_size: float) -> Tuple[float, float]:
        """Return the SW corner of the tile containing (lat, lon)."""
        return (
            math.floor(lat / grid_size) * grid_size,
            math.floor(lon / grid_size) * grid_size,
        )

    def _tile_cache_key(self, cell_lat: float, cell_lon: float, grid_size: float) -> str:
        """Cache key for a tile (includes size and schema version)."""
        return f"tile_{cell_lat:.4f}_{cell_lon:.4f}_g{grid_size:.4f}_v3"

    def _throttle(self) -> None:
        """Global minimum interval between Overpass request starts (thread-safe)."""
        if self.inter_request_delay_sec <= 0.0:
            return
        with self._rate_lock:
            now = time.time()
            wait = self._next_request_time - now
            if wait > 0:
                time.sleep(wait)
            self._next_request_time = max(now, self._next_request_time) + self.inter_request_delay_sec

    def _cache_store(self, key: str, entry: dict) -> None:
        """Thread-safe cache write + atomic persist."""
        with self._cache_lock:
            self._cache[key] = entry
            self._save_cache()

    def _resolve_tile(
        self, cell_lat: float, cell_lon: float, grid_size: float, depth: int = 0
    ) -> Optional[dict]:
        """Return the cache entry for one tile, querying Overpass if needed.

        On network failure at depth 0 the tile is retried ONCE as 4 smaller
        sub-tiles; any sub-tile that still fails is cached as "unavailable"
        (never "not_found"). Returns None only when use_network=False and the
        tile is not cached. Thread-safe for concurrent tile resolution.
        """
        key = self._tile_cache_key(cell_lat, cell_lon, grid_size)

        # Fresh cache hit (unavailable entries expire after _CACHE_RETRY_HOURS)
        if key in self._cache:
            entry = self._cache[key]
            if entry.get("status") != "unavailable" or (
                time.time() - entry.get("timestamp", 0.0) < _CACHE_RETRY_HOURS * 3600.0
            ):
                with self._cache_lock:
                    self.total_cache_hits += 1
                return entry
            with self._cache_lock:
                self._cache.pop(key, None)  # stale unavailable -> re-query

        if not self.use_network:
            return None

        # Conservative rate limiting between network calls (thread-safe)
        self._throttle()

        query = self._build_tile_query(cell_lat, cell_lon, grid_size)
        with self._cache_lock:
            self.total_queries += 1
        elements, status_code = self._post_overpass(query)

        if status_code == 200 and elements is not None:
            self._cache_store(key, {
                "status": "found" if elements else "not_found",
                "elements": elements,
                "radius_km": self.radius_km,
                "grid_size": grid_size,
                "timestamp": time.time(),
                "version": "v3",
            })
            return self._cache[key]

        # Failed -> retry ONCE with smaller tiles (never indefinitely)
        if depth == 0:
            with self._cache_lock:
                self.fallback_tile_splits += 1
            half = grid_size / 2.0
            logger.warning(
                f"Tile ({cell_lat:.4f},{cell_lon:.4f}) @ {grid_size} deg failed "
                f"(HTTP {status_code}); splitting into 4 sub-tiles of {half} deg"
            )
            child_entries = []
            for dlat, dlon in ((0.0, 0.0), (0.0, half), (half, 0.0), (half, half)):
                child_entries.append(
                    self._resolve_tile(cell_lat + dlat, cell_lon + dlon, half, depth=1)
                )

            entries = [ce for ce in child_entries if ce is not None]
            elements = [e for ce in entries for e in ce.get("elements", [])]
            statuses = [ce.get("status") for ce in entries]
            if any(s == "found" for s in statuses):
                status = "found"
            elif statuses and all(s == "not_found" for s in statuses):
                status = "not_found"
            else:
                status = "unavailable"

            self._cache_store(key, {
                "status": status,
                "elements": elements,
                "radius_km": self.radius_km,
                "grid_size": grid_size,
                "timestamp": time.time(),
                "version": "v3",
            })
            return self._cache[key]

        # Deeper-level failure -> unavailable (bounded; no infinite retries)
        return self._mark_unavailable(cell_lat, cell_lon, grid_size)

    def _mark_unavailable(self, cell_lat: float, cell_lon: float, grid_size: float) -> dict:
        """Cache a tile as 'unavailable' (network/HTTP failure), NOT 'not_found'."""
        key = self._tile_cache_key(cell_lat, cell_lon, grid_size)
        self._cache_store(key, {
            "status": "unavailable",
            "elements": [],
            "timestamp": time.time(),
            "radius_km": self.radius_km,
            "grid_size": grid_size,
            "version": "v3",
        })
        logger.warning(
            f"Tile ({cell_lat:.4f},{cell_lon:.4f}) @ {grid_size} deg marked unavailable "
            "(will be retried on a later run)"
        )
        return self._cache[key]

    def extract_context(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract OSM contextual columns for input DataFrame containing 'latitude' and 'longitude'.
        Appends:
          - osm_facility_type
          - osm_facility_name
          - osm_distance_km
          - osm_query_status
        """
        if "latitude" not in df.columns or "longitude" not in df.columns:
            raise ValueError("Input DataFrame missing required 'latitude' or 'longitude' columns.")

        df_out = df.copy()

        # Step 1: group rows by geographic tile (only occupied tiles are queried)
        tiles: Dict[Tuple[float, float], List[int]] = defaultdict(list)
        for idx, (_, row) in enumerate(df_out.iterrows()):
            lat, lon = row.get("latitude"), row.get("longitude")
            if pd.isna(lat) or pd.isna(lon):
                continue
            tiles[self._tile_cell(float(lat), float(lon), self.grid_size_deg)].append(idx)

        logger.info(
            f"BatchedOSM: {len(df_out)} clusters | {len(tiles)} occupied tiles "
            f"(tile size {self.grid_size_deg} deg) | cache {len(self._cache)} entries"
        )

        # Step 2: resolve every occupied tile concurrently (cache hit or one bbox query)
        resolved: Dict[Tuple[float, float], Optional[dict]] = {}
        n_tiles = len(tiles)
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(self._resolve_tile, cell[0], cell[1], self.grid_size_deg): cell
                for cell in sorted(tiles)
            }
            for n, fut in enumerate(as_completed(futures), 1):
                cell = futures[fut]
                resolved[cell] = fut.result()
                if n % 50 == 0 or n == n_tiles:
                    logger.info(f"Tile progress: {n}/{n_tiles} tiles resolved")

        # Step 3: local distance matching per cluster (2 km radius)
        point_statuses: Dict[int, Tuple[str, str, float, str]] = {}
        for idx, (_, row) in enumerate(df_out.iterrows()):
            lat, lon = row.get("latitude"), row.get("longitude")
            if pd.isna(lat) or pd.isna(lon):
                point_statuses[idx] = ("UNKNOWN", "none", float("inf"), "missing_coords")
                continue
            lat_f, lon_f = float(lat), float(lon)
            cell = self._tile_cell(lat_f, lon_f, self.grid_size_deg)
            entry = resolved.get(cell)
            if entry is None:
                point_statuses[idx] = ("UNKNOWN", "none", float("inf"), "disabled")
            elif entry.get("status") == "unavailable":
                # Network failure != no facility: preserve UNKNOWN / insufficient evidence
                point_statuses[idx] = ("UNKNOWN", "none", float("inf"), "unavailable")
            else:
                fac, name, dist = _find_nearest_facility(
                    lat_f, lon_f, entry.get("elements", []), self.radius_km
                )
                if fac != "none":
                    point_statuses[idx] = (fac, name, dist, "found")
                else:
                    point_statuses[idx] = ("none", "none", float("inf"), "not_found")

        # Step 4: populate output dataframe
        df_out["osm_facility_type"] = [point_statuses[i][0] for i in range(len(df_out))]
        df_out["osm_facility_name"] = [point_statuses[i][1] for i in range(len(df_out))]
        df_out["osm_distance_km"] = [point_statuses[i][2] for i in range(len(df_out))]
        df_out["osm_query_status"] = [point_statuses[i][3] for i in range(len(df_out))]

        statuses = df_out["osm_query_status"].tolist()
        found_n = sum(1 for s in statuses if s == "found")
        not_found_n = sum(1 for s in statuses if s == "not_found")
        unavailable_n = sum(1 for s in statuses if s == "unavailable")
        logger.info(
            f"BatchedOSM complete: {found_n} found, {not_found_n} no facility, "
            f"{unavailable_n} unavailable | {self.total_queries} HTTP queries, "
            f"{self.fallback_tile_splits} tile splits, {self.total_cache_hits} cache hits"
        )

        return df_out

