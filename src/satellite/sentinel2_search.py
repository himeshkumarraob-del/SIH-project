"""
Sentinel-2 Imagery STAC Search & Cloud Quality Handling Module.

Connects FIRMS thermal cluster coordinates (latitude, longitude, date) to Copernicus Sentinel-2
multispectral satellite imagery via STAC catalog search.

Distinguishes explicitly between:
- "NO OBSERVATION / OBSERVATION OBSCURED" (image_available = False)
- Genuine clear observations.

Never fabricates satellite imagery or makes unverified claims.
"""

from __future__ import annotations

import os
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import requests

from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("satellite.sentinel2_search")

class Sentinel2Searcher:
    def __init__(
        self,
        temporal_window_days: int = 3,
        max_cloud_cover_percent: float = 20.0,
        stac_url: str = "https://catalogue.dataspace.copernicus.eu/stac/search"
    ):
        self.temporal_window_days = temporal_window_days
        self.max_cloud_cover_percent = max_cloud_cover_percent
        self.stac_url = stac_url

        self.client_id = os.environ.get("COPERNICUS_CLIENT_ID")
        self.client_secret = os.environ.get("COPERNICUS_CLIENT_SECRET")

    def search_image_for_cluster(
        self,
        cluster_id: int,
        latitude: float,
        longitude: float,
        event_date_str: str
    ) -> Dict[str, Any]:
        """
        Search Sentinel-2 imagery for a given cluster location and date.
        
        Returns record dictionary:
        - cluster_id
        - image_available (bool)
        - image_source (str)
        - image_id (str)
        - image_date (str)
        - cloud_cover (float)
        - observation_status (str)
        """
        # Baseline fallback record
        record = {
            "cluster_id": cluster_id,
            "image_available": False,
            "image_source": "Sentinel-2_L2A",
            "image_id": "none",
            "image_date": event_date_str,
            "cloud_cover": 100.0,
            "observation_status": "Satellite observation unavailable/obscured"
        }

        # Check credentials or network requirement
        if not self.client_id or not self.client_secret:
            record["observation_status"] = "Copernicus STAC credentials not configured (satellite data optional)"
            return record

        try:
            # Parse date
            evt_dt = pd.to_datetime(event_date_str)
            start_dt = (evt_dt - timedelta(days=self.temporal_window_days)).strftime("%Y-%m-%dT00:00:00Z")
            end_dt = (evt_dt + timedelta(days=self.temporal_window_days)).strftime("%Y-%m-%dT23:59:59Z")

            # Bounding box around lat/lon (~0.05 deg buffer)
            bbox = [longitude - 0.05, latitude - 0.05, longitude + 0.05, latitude + 0.05]

            query_payload = {
                "collections": ["SENTINEL-2"],
                "bbox": bbox,
                "datetime": f"{start_dt}/{end_dt}",
                "limit": 5
            }

            resp = requests.post(self.stac_url, json=query_payload, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                features = data.get("features", [])
                
                # Filter for cloud cover threshold
                valid_features = []
                for feat in features:
                    props = feat.get("properties", {})
                    cloud = props.get("eo:cloud_cover", 100.0)
                    if cloud <= self.max_cloud_cover_percent:
                        valid_features.append((cloud, feat))

                if valid_features:
                    # Select feature with lowest cloud cover
                    valid_features.sort(key=lambda x: x[0])
                    best_cloud, best_feat = valid_features[0]
                    props = best_feat.get("properties", {})
                    
                    record["image_available"] = True
                    record["image_id"] = best_feat.get("id", "S2_PATCH")
                    record["image_date"] = props.get("datetime", event_date_str)
                    record["cloud_cover"] = float(best_cloud)
                    record["observation_status"] = "Clear satellite observation retrieved"
                    return record
                else:
                    record["observation_status"] = "Satellite observation obscured by cloud cover (> 20%)"
                    return record

        except Exception as exc:
            logger.debug(f"Sentinel-2 STAC search skipped/failed for cluster {cluster_id}: {exc}")
            record["observation_status"] = "Satellite observation search unavailable (network/API)"
            return record

        return record
