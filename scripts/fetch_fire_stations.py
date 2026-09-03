#!/usr/bin/env python3
"""
Fetch REAL OpenStreetMap fire stations (amenity=fire_station) across India.

Queries the Overpass API using small geographic tiles (2 deg) over the study
extent, one compact bounding-box query per tile, then caches all stations to
data/processed/fire_stations.csv for the response-intelligence locator.

No fabricated stations: the output contains only real OSM objects that are
tagged amenity=fire_station.

Usage:
    python scripts/fetch_fire_stations.py
"""

from __future__ import annotations

import math
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Overpass mirrors, primary (fastest/most reliable) first
OVERPASS_URLS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
HEADERS = {"User-Agent": "SIH-ThermalIntel/1.0 (academic research)"}

# Study extent (India thermal-cluster bounding box plus margin)
LAT_MIN, LAT_MAX = 6.0, 38.0
LON_MIN, LON_MAX = 66.0, 100.0
TILE_DEG = 2.0
TIMEOUT_SEC = 25
MAX_RETRIES = 1
RETRY_DELAY_SEC = 2.0
INTER_REQUEST_DELAY_SEC = 0.8
MAX_WORKERS = 6


def _tiles() -> List[Tuple[float, float, float, float]]:
    cells = []
    lat = LAT_MIN
    while lat < LAT_MAX:
        lon = LON_MIN
        while lon < LON_MAX:
            cells.append((lat, lon, min(lat + TILE_DEG, LAT_MAX), min(lon + TILE_DEG, LON_MAX)))
            lon += TILE_DEG
        lat += TILE_DEG
    return cells


def _build_query(south: float, west: float, north: float, east: float) -> str:
    return (
        f"[out:json][timeout:{TIMEOUT_SEC}];\n"
        "(\n"
        f'  nwr["amenity"="fire_station"]({south:.4f},{west:.4f},{north:.4f},{east:.4f});\n'
        ");\n"
        "out center;"
    )


def _post_overpass(query: str) -> Optional[list]:
    for url in OVERPASS_URLS:
        for attempt in range(1 + MAX_RETRIES):
            try:
                resp = requests.post(url, data={"data": query}, headers=HEADERS, timeout=TIMEOUT_SEC + 10)
                if resp.status_code == 429:
                    wait = RETRY_DELAY_SEC * (2 ** attempt)
                    print(f"  429 at {url}, retry in {wait:.0f}s", flush=True)
                    time.sleep(wait)
                    continue
                if resp.status_code in (502, 503, 504):
                    wait = RETRY_DELAY_SEC * (2 ** attempt)
                    print(f"  {resp.status_code} at {url}, retry in {wait:.0f}s", flush=True)
                    time.sleep(wait)
                    continue
                if resp.status_code != 200:
                    return None
                return resp.json().get("elements", [])
            except requests.exceptions.Timeout:
                wait = RETRY_DELAY_SEC * (2 ** attempt)
                time.sleep(wait)
                continue
            except Exception:
                break  # next mirror
    return None


def main() -> int:
    rate_lock = threading.Lock()
    next_request_time = 0.0

    def throttle() -> None:
        nonlocal next_request_time
        with rate_lock:
            now = time.time()
            wait = next_request_time - now
            if wait > 0:
                time.sleep(wait)
            next_request_time = max(now, next_request_time) + INTER_REQUEST_DELAY_SEC

    def fetch_tile(tile) -> List[dict]:
        south, west, north, east = tile
        throttle()
        elements = _post_overpass(_build_query(south, west, north, east))
        if elements is None:
            return []
        stations = []
        for el in elements:
            el_lat = el.get("lat") or (el.get("center") or {}).get("lat")
            el_lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if el_lat is None or el_lon is None:
                continue
            tags = el.get("tags", {})
            stations.append({
                "osm_type": el.get("type", "node"),
                "osm_id": el.get("id"),
                "name": tags.get("name") or tags.get("short_name") or "Fire station (unnamed)",
                "latitude": round(float(el_lat), 6),
                "longitude": round(float(el_lon), 6),
            })
        return stations

    tiles = _tiles()
    print(f"Fetching real OSM fire stations across {len(tiles)} tiles...", flush=True)
    collected: List[dict] = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_tile, tile): tile for tile in tiles}
        for n, fut in enumerate(as_completed(futures), 1):
            collected.extend(fut.result())
            if n % 25 == 0:
                print(f"  tiles done: {n}/{len(tiles)} (stations so far: {len(collected)})", flush=True)

    # Deduplicate by (osm_type, osm_id)
    seen = set()
    unique = []
    for s in collected:
        key = (s["osm_type"], s["osm_id"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)

    df = pd.DataFrame(unique)
    df = df.sort_values(["latitude", "longitude"]).reset_index(drop=True)
    out_path = PROJECT_ROOT / "data" / "processed" / "fire_stations.csv"
    df.to_csv(out_path, index=False)
    elapsed = time.time() - t0
    print(f"\nDone in {elapsed/60:.1f} min: {len(df)} real OSM fire stations saved to {out_path}")
    named = int(df["name"].ne("Fire station (unnamed)").sum())
    print(f"  named stations: {named}, unnamed: {len(df) - named}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
