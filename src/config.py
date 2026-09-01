"""
Central configuration loader for thermal-intelligence.

Loads:
- Non-secret settings from config.yaml.
- Secrets (FIRMS_MAP_KEY) from environment variables / .env file.

Every other module should import from here rather than re-reading
config.yaml or os.environ directly, so there is exactly one source of
truth for configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


@dataclass(frozen=True)
class BoundingBox:
    west: float
    south: float
    east: float
    north: float

    def as_firms_bbox_str(self) -> str:
        """FIRMS area API expects 'west,south,east,north'."""
        return f"{self.west},{self.south},{self.east},{self.north}"


@dataclass(frozen=True)
class FirmsProduct:
    key: str
    source: str
    description: str


@dataclass(frozen=True)
class PersistenceConfig:
    """Configuration for spatial-temporal FIRMS persistence analysis."""

    spatial_distance_km: float
    temporal_window_days: int
    persistent_min_active_days: int
    repeated_min_active_days: int


class ConfigError(RuntimeError):
    """Raised when required configuration or secrets are missing."""


class Config:
    """
    Lazily-loaded, cached access to config.yaml + environment secrets.

    Usage:
        from src.config import get_config
        cfg = get_config()
        cfg.firms_map_key
        cfg.study_area
        cfg.persistence
        cfg.raw_data_dir
    """

    def __init__(self, config_path: Path = CONFIG_PATH):
        # Load .env if present. Does NOT override variables already set
        # in the real environment.
        load_dotenv(PROJECT_ROOT / ".env", override=False)

        if not config_path.exists():
            raise ConfigError(
                f"config.yaml not found at {config_path}. "
                "This file is required and should not be deleted."
            )

        with open(config_path, "r", encoding="utf-8") as f:
            self._raw: dict[str, Any] = yaml.safe_load(f)

    # -- secrets ------------------------------------------------------

    @property
    def firms_map_key(self) -> str:
        key = os.environ.get("FIRMS_MAP_KEY")

        if not key or key == "YOUR_KEY_HERE":
            raise ConfigError(
                "FIRMS_MAP_KEY is not set. Copy .env.example to .env and "
                "fill in a real key from "
                "https://firms.modaps.eosdis.nasa.gov/api/map_key/"
            )

        return key

    # -- study area ---------------------------------------------------

    @property
    def study_area(self) -> BoundingBox:
        sa = self._raw["study_area"]

        # Allow environment variable overrides for testing.
        return BoundingBox(
            west=float(os.environ.get("STUDY_AREA_WEST", sa["west"])),
            south=float(os.environ.get("STUDY_AREA_SOUTH", sa["south"])),
            east=float(os.environ.get("STUDY_AREA_EAST", sa["east"])),
            north=float(os.environ.get("STUDY_AREA_NORTH", sa["north"])),
        )

    # -- FIRMS --------------------------------------------------------

    @property
    def firms_base_url(self) -> str:
        return self._raw["firms"]["base_url"]

    @property
    def firms_max_days_per_request(self) -> int:
        return int(self._raw["firms"]["max_days_per_request"])

    @property
    def firms_products(self) -> dict[str, FirmsProduct]:
        return {
            p["key"]: FirmsProduct(
                key=p["key"],
                source=p["source"],
                description=p["description"],
            )
            for p in self._raw["firms"]["products"]
        }

    @property
    def firms_default_product_keys(self) -> list[str]:
        return list(self._raw["firms"]["default_products"])

    @property
    def initial_collection_lookback_days(self) -> int:
        return int(self._raw["initial_collection"]["lookback_days"])

    # -- persistence --------------------------------------------------

    @property
    def persistence(self) -> PersistenceConfig:
        """Return spatial-temporal persistence analysis configuration."""

        persistence = self._raw["persistence"]

        return PersistenceConfig(
            spatial_distance_km=float(
                persistence["spatial_distance_km"]
            ),
            temporal_window_days=int(
                persistence["temporal_window_days"]
            ),
            persistent_min_active_days=int(
                persistence["persistent_min_active_days"]
            ),
            repeated_min_active_days=int(
                persistence["repeated_min_active_days"]
            ),
        )

    # -- paths --------------------------------------------------------

    def _path(self, key: str) -> Path:
        p = PROJECT_ROOT / self._raw["paths"][key]
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def raw_data_dir(self) -> Path:
        return self._path("data_raw")

    @property
    def interim_data_dir(self) -> Path:
        return self._path("data_interim")

    @property
    def processed_data_dir(self) -> Path:
        return self._path("data_processed")

    @property
    def external_data_dir(self) -> Path:
        return self._path("data_external")

    @property
    def reports_dir(self) -> Path:
        return self._path("reports")

    @property
    def models_dir(self) -> Path:
        return self._path("models")

    @property
    def log_file(self) -> Path:
        log_path = PROJECT_ROOT / self._raw["logging"]["log_file"]
        log_path.parent.mkdir(parents=True, exist_ok=True)
        return log_path

    @property
    def log_level(self) -> str:
        return self._raw["logging"]["level"]


_config_instance: Config | None = None


def get_config() -> Config:
    """Return a process-wide cached Config instance."""
    global _config_instance

    if _config_instance is None:
        _config_instance = Config()

    return _config_instance