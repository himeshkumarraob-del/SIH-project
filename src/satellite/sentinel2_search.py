"""
Sentinel-2 Imagery STAC Search & Cloud Quality Handling Module.

Connects FIRMS thermal cluster coordinates (latitude, longitude, date) to Sentinel-2
multispectral satellite imagery via Microsoft Planetary Computer STAC catalog.

Distinguishes explicitly between:
- "REAL USABLE OBSERVATION" (image_available = True)
- "REAL OBSERVATION BUT CLOUD/QUALITY TOO POOR" (image_available = False)
- "NO MATCHING SENTINEL-2 OBSERVATION" (image_available = False)
- "DOWNLOAD/PROCESSING ERROR" (image_available = False)

Never fabricates satellite imagery or makes unverified claims.
Missing imagery NEVER implies absence of fire or anomaly.
"""

from __future__ import annotations

import os
import io
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import requests

from src.logging_setup import get_logger

logger = get_logger("satellite.sentinel2_search")

# Microsoft Planetary Computer STAC endpoint (public metadata, no auth needed)
PLANETARY_COMPUTER_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

# Sentinel-2 L2A collection on Planetary Computer
SENTINEL2_COLLECTION = "sentinel-2-l2a"


class Sentinel2Searcher:
    def __init__(
        self,
        temporal_window_days: int = 5,
        max_cloud_cover_percent: float = 30.0,
        patch_size: int = 64,
    ):
        self.temporal_window_days = temporal_window_days
        self.max_cloud_cover_percent = max_cloud_cover_percent
        self.patch_size = patch_size
        self._signing_available = False

        # Check if planetary_computer is available for URL signing
        try:
            import planetary_computer
            self._signing_available = True
        except ImportError:
            logger.warning("planetary-computer package not installed. Image downloads will be unavailable.")

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
        - satellite_image_available (bool)
        - predicted_landcover_class (str)
        - prediction_confidence (float or None)
        - image_date (str)
        - cloud_cover (float)
        - image_source (str)
        - observation_status (str)
        - satellite_item_id (str)
        """
        # Baseline fallback record
        record = {
            "cluster_id": cluster_id,
            "satellite_image_available": False,
            "predicted_landcover_class": "UNKNOWN",
            "prediction_confidence": None,
            "image_date": event_date_str,
            "cloud_cover": 100.0,
            "image_source": "Sentinel-2_L2A",
            "observation_status": "Satellite observation search pending",
            "satellite_item_id": "none",
        }

        try:
            # Parse date
            evt_dt = pd.to_datetime(event_date_str)
            start_dt = (evt_dt - timedelta(days=self.temporal_window_days)).strftime("%Y-%m-%dT00:00:00Z")
            end_dt = (evt_dt + timedelta(days=self.temporal_window_days)).strftime("%Y-%m-%dT23:59:59Z")

            # Bounding box around lat/lon (~0.05 deg buffer ≈ 5.5 km)
            bbox = [longitude - 0.05, latitude - 0.05, longitude + 0.05, latitude + 0.05]

            # Search Planetary Computer STAC
            search_url = f"{PLANETARY_COMPUTER_STAC_URL}/search"
            query_payload = {
                "collections": [SENTINEL2_COLLECTION],
                "bbox": bbox,
                "datetime": f"{start_dt}/{end_dt}",
                "limit": 10,
            }

            resp = requests.post(search_url, json=query_payload, timeout=15)

            if resp.status_code != 200:
                record["observation_status"] = f"Satellite search API error (HTTP {resp.status_code})"
                return record

            data = resp.json()
            features = data.get("features", [])

            if not features:
                record["observation_status"] = "No matching Sentinel-2 observation found in temporal window"
                return record

            # Keep ONLY items whose footprint actually covers the cluster point.
            # The bbox search returns adjacent tiles that merely intersect the
            # search box; downloading from a non-covering tile yields empty/black
            # patches that must never be fed to the CNN.
            from shapely.geometry import Point as _Point
            from shapely.geometry import shape as _shape

            point = _Point(longitude, latitude)
            covering_features = []
            for feat in features:
                geom = feat.get("geometry")
                if not geom:
                    continue
                try:
                    if _shape(geom).contains(point):
                        covering_features.append(feat)
                except Exception:
                    # Unparseable geometry: do not assume coverage.
                    continue

            features = covering_features
            if not features:
                record["observation_status"] = "No matching Sentinel-2 observation found in temporal window"
                return record

            # Filter for cloud cover threshold
            valid_features: List[Tuple[float, dict]] = []
            all_features_info: List[Tuple[float, str]] = []

            for feat in features:
                props = feat.get("properties", {})
                cloud = props.get("eo:cloud_cover", 100.0)
                feat_id = feat.get("id", "unknown")
                all_features_info.append((cloud, feat_id))
                if cloud <= self.max_cloud_cover_percent:
                    valid_features.append((cloud, feat))

            if not valid_features:
                best_cloud, best_id = min(all_features_info, key=lambda x: x[0])
                record["observation_status"] = (
                    f"Sentinel-2 observation available but obscured by cloud cover "
                    f"(best: {best_cloud:.1f}%, threshold: {self.max_cloud_cover_percent}%)"
                )
                record["cloud_cover"] = float(best_cloud)
                record["satellite_item_id"] = best_id
                return record

            # Select cloud-free features, lowest cloud cover first
            valid_features.sort(key=lambda x: x[0])

            # Try up to 3 of the clearest features: the lowest-cloud item may not
            # actually cover the cluster point (tile edge), so fall back to the
            # next cloud-free scene before giving up.
            for best_cloud, best_feat in valid_features[:3]:
                props = best_feat.get("properties", {})
                if not self._signing_available:
                    break
                image_tensor = self._download_and_prepare_image(best_feat, latitude, longitude)
                if image_tensor is not None:
                    record["satellite_image_available"] = True
                    record["satellite_item_id"] = best_feat.get("id", "S2_PATCH")
                    record["image_date"] = props.get("datetime", event_date_str)
                    record["cloud_cover"] = float(best_cloud)
                    record["image_tensor"] = image_tensor
                    record["observation_status"] = "Satellite image retrieved and ready for CNN inference"
                    return record

            # Every cloud-free download attempt failed — keep the clearest item's
            # metadata and record an HONEST failure (never a black/garbage patch).
            if valid_features:
                best_cloud, best_feat = valid_features[0]
                props = best_feat.get("properties", {})
                record["satellite_item_id"] = best_feat.get("id", "S2_PATCH")
                record["image_date"] = props.get("datetime", event_date_str)
                record["cloud_cover"] = float(best_cloud)
                record["observation_status"] = "Satellite metadata available but image download failed"

            return record

        except requests.exceptions.Timeout:
            record["observation_status"] = "Satellite search timed out (network issue)"
            return record
        except requests.exceptions.ConnectionError:
            record["observation_status"] = "Satellite search unavailable (no network connection)"
            return record
        except Exception as exc:
            logger.warning(f"Sentinel-2 search failed for cluster {cluster_id}: {exc}")
            record["observation_status"] = f"Satellite search error: {str(exc)[:100]}"
            return record

    def _download_and_prepare_image(self, stac_feature: dict, lat: float, lon: float) -> Optional[Any]:
        """
        Download Sentinel-2 RGB bands (B04/B03/B02) and prepare as CNN-ready tensor.

        Crops a windowed area AROUND THE CLUSTER CENTROID (lat/lon) — NOT around
        the STAC tile-footprint centroid. Sentinel-2 L2A COGs are stored in UTM
        projection, so the geographic window is reprojected into the dataset CRS
        before windowed reading (feeding degrees straight into from_bounds yields
        empty/black patches).

        Returns a torch.Tensor of shape (1, 3, patch_size, patch_size) or None on
        failure (empty read, all-nodata/black patch, missing bands, network error).
        """
        try:
            import planetary_computer
            import numpy as np
            import rasterio
            from rasterio.windows import from_bounds
            from rasterio.warp import transform_bounds
            from PIL import Image

            assets = stac_feature.get("assets", {})

            # Window bounds around the cluster centroid (approximate degrees)
            patch_pixel_size = self.patch_size  # 64 pixels
            pixel_size_m = 10.0  # B04/B03/B02 are 10m resolution
            buffer_m = patch_pixel_size * pixel_size_m / 2  # 320m radius
            buffer_deg = buffer_m / 111000.0  # Approximate degrees (~0.00288)
            west, south = lon - buffer_deg, lat - buffer_deg
            east, north = lon + buffer_deg, lat + buffer_deg

            # We need B04 (Red), B03 (Green), B02 (Blue)
            band_keys = {"B04": None, "B03": None, "B02": None}

            for key in band_keys:
                if key in assets:
                    href = assets[key].get("href", "")
                    if href:
                        band_keys[key] = planetary_computer.sign(href)

            if not all(band_keys.values()):
                logger.warning("Missing required RGB bands (B04/B03/B02) in STAC assets")
                return None

            # Download bands using windowed reading to minimize bandwidth
            bands = {}
            for band_name, signed_href in band_keys.items():
                try:
                    with rasterio.open(signed_href) as src:
                        # Reproject the geographic window into the dataset CRS (UTM)
                        projected = transform_bounds(
                            "EPSG:4326", src.crs, west, south, east, north
                        )
                        window = from_bounds(*projected, transform=src.transform)
                        band_data = src.read(1, window=window)
                        if band_data is None or band_data.size == 0:
                            logger.warning(f"Empty window read for {band_name} (cluster outside scene?)")
                            return None
                        bands[band_name] = band_data.astype(np.float32)
                except Exception as e:
                    logger.warning(f"Failed to read {band_name}: {e}")
                    return None

            # Stack RGB: B04=R, B03=G, B02=B
            rgb = np.stack([bands["B04"], bands["B03"], bands["B02"]], axis=-1)

            # Sentinel-2 L2A values are surface reflectance * 10000
            # Apply scaling factor (DN * 0.0001 = reflectance)
            rgb = rgb * 0.0001

            # Clip to valid range and scale to 0-255
            rgb = np.clip(rgb, 0, 1)
            rgb = (rgb * 255).astype(np.uint8)

            # Validation: reject empty / all-nodata / black patches instead of
            # feeding garbage to the CNN (a black patch is NOT land-cover evidence).
            if (
                rgb.size == 0
                or float((rgb.sum(axis=2) == 0).mean()) > 0.95
                or float(rgb.std()) < 1.0
            ):
                logger.warning("Downloaded patch is empty/all-nodata; rejecting before CNN inference")
                return None

            # Create PIL image and resize to patch_size
            img = Image.fromarray(rgb)
            img = img.resize((self.patch_size, self.patch_size), Image.Resampling.LANCZOS)

            # Convert to tensor and apply ImageNet normalization
            from src.satellite.preprocessing import preprocess_image
            tensor = preprocess_image(img, image_size=self.patch_size)

            return tensor

        except Exception as exc:
            logger.warning(f"Image download/preparation failed: {exc}")
            return None

    def download_rgb_preview(self, stac_feature: dict, output_path: Optional[Path] = None) -> Optional[Path]:
        """
        Download a visual RGB preview image for display purposes.
        Returns path to saved image or None on failure.
        """
        try:
            import planetary_computer

            assets = stac_feature.get("assets", {})

            # Try visual/rendered preview first
            preview_asset = assets.get("rendered_preview") or assets.get("visual")
            if preview_asset:
                href = planetary_computer.sign(preview_asset["href"])
                resp = requests.get(href, timeout=30)
                if resp.status_code == 200:
                    if output_path:
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        output_path.write_bytes(resp.content)
                        return output_path
                    return None

            return None

        except Exception as exc:
            logger.warning(f"Preview download failed: {exc}")
            return None
