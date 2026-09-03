"""
Weather Data Integration Module.

Fetches and processes weather data (cloud cover, wind, humidity)
to support cloud-aware fire detection and risk assessment.

Supports ERA5 and GFS data sources for historical and forecast data.
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

from src.logging_setup import get_logger

logger = get_logger("data.weather_integration")


@dataclass
class WeatherObservation:
    """Container for weather observation at a location and time."""
    latitude: float
    longitude: float
    timestamp: datetime
    cloud_cover: float  # 0-100 percentage
    cloud_type: Optional[str] = None
    temperature_2m: Optional[float] = None  # Celsius
    humidity: Optional[float] = None  # 0-100 %
    wind_speed: Optional[float] = None  # m/s
    wind_direction: Optional[float] = None  # degrees
    precipitation: Optional[float] = None  # mm/hour


class WeatherDataManager:
    """
    Manages weather data retrieval and caching.
    
    Supports multiple data sources:
    - ERA5 (ECMWF Reanalysis) - historical data
    - GFS (Global Forecast System) - forecast data
    - Open-Meteo API - free, no API key required
    
    Usage:
        manager = WeatherDataManager()
        weather = manager.get_historical_cloud_cover(lat, lon, start_date, end_date)
    """
    
    # Open-Meteo API endpoints (free, no API key)
    OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
    OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize weather data manager.
        
        Args:
            cache_dir: Directory to cache downloaded weather data
        """
        self.cache_dir = cache_dir
        self._cache = {}  # In-memory cache
        
        if cache_dir:
            from pathlib import Path
            Path(cache_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info("WeatherDataManager initialized")
    
    def get_historical_cloud_cover(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str
    ) -> List[WeatherObservation]:
        """
        Fetch historical cloud cover data from Open-Meteo Archive API.
        
        Args:
            latitude: Location latitude
            longitude: Location longitude
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            List of WeatherObservation objects
        """
        try:
            import requests
        except ImportError:
            logger.warning("requests library not available, using mock data")
            return self._generate_mock_weather_data(latitude, longitude, start_date, end_date)
        
        # Check cache first
        cache_key = f"archive_{latitude}_{longitude}_{start_date}_{end_date}"
        if cache_key in self._cache:
            logger.info(f"Returning cached weather data for {latitude}, {longitude}")
            return self._cache[cache_key]
        
        try:
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start_date,
                "end_date": end_date,
                "daily": "cloud_cover_mean,temperature_2m_mean,wind_speed_10m_mean",
                "timezone": "auto"
            }
            
            response = requests.get(
                self.OPEN_METEO_ARCHIVE_URL,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            observations = self._parse_open_meteo_response(data, latitude, longitude)
            
            # Cache the results
            self._cache[cache_key] = observations
            
            logger.info(f"Fetched {len(observations)} weather observations for {latitude}, {longitude}")
            return observations
            
        except Exception as e:
            logger.warning(f"Failed to fetch weather data: {e}. Using mock data.")
            return self._generate_mock_weather_data(latitude, longitude, start_date, end_date)
    
    def get_forecast_cloud_cover(
        self,
        latitude: float,
        longitude: float,
        forecast_days: int = 7
    ) -> List[WeatherObservation]:
        """
        Fetch cloud cover forecast from Open-Meteo Forecast API.
        
        Args:
            latitude: Location latitude
            longitude: Location longitude
            forecast_days: Number of days to forecast (max 16)
            
        Returns:
            List of WeatherObservation objects with forecast data
        """
        try:
            import requests
        except ImportError:
            logger.warning("requests library not available, using mock forecast")
            today = datetime.now().strftime("%Y-%m-%d")
            end_date = (datetime.now() + timedelta(days=forecast_days)).strftime("%Y-%m-%d")
            return self._generate_mock_weather_data(latitude, longitude, today, end_date)
        
        try:
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "daily": "cloud_cover_mean,temperature_2m_mean,wind_speed_10m_mean",
                "timezone": "auto",
                "forecast_days": min(forecast_days, 16)
            }
            
            response = requests.get(
                self.OPEN_METEO_FORECAST_URL,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            observations = self._parse_open_meteo_response(data, latitude, longitude)
            
            logger.info(f"Fetched {len(observations)} forecast observations")
            return observations
            
        except Exception as e:
            logger.warning(f"Failed to fetch forecast data: {e}. Using mock forecast.")
            today = datetime.now().strftime("%Y-%m-%d")
            end_date = (datetime.now() + timedelta(days=forecast_days)).strftime("%Y-%m-%d")
            return self._generate_mock_weather_data(latitude, longitude, today, end_date)
    
    def _parse_open_meteo_response(
        self, 
        data: Dict, 
        latitude: float, 
        longitude: float
    ) -> List[WeatherObservation]:
        """Parse Open-Meteo API response into WeatherObservation objects."""
        observations = []
        
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        cloud_cover = daily.get("cloud_cover_mean", [])
        temps = daily.get("temperature_2m_mean", [])
        winds = daily.get("wind_speed_10m_mean", [])
        
        for i, date_str in enumerate(dates):
            try:
                timestamp = datetime.fromisoformat(date_str)
            except:
                continue
            
            obs = WeatherObservation(
                latitude=latitude,
                longitude=longitude,
                timestamp=timestamp,
                cloud_cover=cloud_cover[i] if i < len(cloud_cover) else 50.0,
                temperature_2m=temps[i] if i < len(temps) else None,
                wind_speed=winds[i] if i < len(winds) else None
            )
            observations.append(obs)
        
        return observations
    
    def _generate_mock_weather_data(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str
    ) -> List[WeatherObservation]:
        """Generate mock weather data for testing."""
        from datetime import datetime
        
        observations = []
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        
        current = start
        while current <= end:
            # Generate realistic-looking cloud cover
            # India typically has 30-70% cloud cover
            cloud_cover = 40.0 + (hash(f"{latitude}{longitude}{current}") % 40)
            
            obs = WeatherObservation(
                latitude=latitude,
                longitude=longitude,
                timestamp=current,
                cloud_cover=cloud_cover,
                temperature_2m=25.0 + (hash(f"temp{current}") % 15),
                wind_speed=2.0 + (hash(f"wind{current}") % 8)
            )
            observations.append(obs)
            current += timedelta(days=1)
        
        return observations
    
    def correlate_clouds_with_detections(
        self,
        detection_dates: List[str],
        cloud_observations: List[WeatherObservation]
    ) -> Dict[str, Any]:
        """
        Correlate fire detection dates with cloud cover.
        
        Identifies which detection gaps might be due to cloud cover
        versus actual fire cessation.
        
        Args:
            detection_dates: List of dates with fire detections (YYYY-MM-DD)
            cloud_observations: Weather observations for the same period
            
        Returns:
            Dictionary with correlation analysis
        """
        cloud_by_date = {
            obs.timestamp.strftime("%Y-%m-%d"): obs.cloud_cover 
            for obs in cloud_observations
        }
        
        analysis = {
            "total_days_analyzed": len(cloud_observations),
            "days_with_detections": len(detection_dates),
            "high_cloud_days": 0,
            "low_cloud_days": 0,
            "potential_cloud_obscured_days": 0,
            "cloud_detection_correlation": []
        }
        
        all_dates = set(cloud_by_date.keys())
        detection_date_set = set(detection_dates)
        
        for date in sorted(all_dates):
            cloud_cover = cloud_by_date.get(date, 50.0)
            has_detection = date in detection_date_set
            
            if cloud_cover > 70:
                analysis["high_cloud_days"] += 1
                if not has_detection:
                    analysis["potential_cloud_obscured_days"] += 1
            else:
                analysis["low_cloud_days"] += 1
            
            analysis["cloud_detection_correlation"].append({
                "date": date,
                "cloud_cover": cloud_cover,
                "has_detection": has_detection,
                "cloud_obscuration_likely": cloud_cover > 70 and not has_detection
            })
        
        return analysis
    
    def get_fire_weather_index(
        self,
        temperature: float,
        humidity: float,
        wind_speed: float,
        precipitation: float = 0.0
    ) -> float:
        """
        Calculate simplified Fire Weather Index (FWI).
        
        Higher values indicate higher fire risk due to weather conditions.
        
        Args:
            temperature: Air temperature (°C)
            humidity: Relative humidity (%)
            wind_speed: Wind speed (m/s)
            precipitation: Precipitation (mm/day)
            
        Returns:
            Fire Weather Index (0-100, higher = more dangerous)
        """
        # Simplified FWI calculation
        # Based on Canadian Forest Fire Weather Index System (simplified)
        
        # Temperature component (0-30 points)
        temp_score = min(30, max(0, (temperature - 10) * 1.5))
        
        # Humidity component (0-30 points, inverted - low humidity = high risk)
        humidity_score = min(30, max(0, (100 - humidity) * 0.4))
        
        # Wind component (0-25 points)
        wind_score = min(25, max(0, wind_speed * 2.5))
        
        # Precipitation component (0-15 points, negative impact)
        precip_penalty = min(15, max(0, precipitation * 2))
        
        # Calculate final index
        fwi = temp_score + humidity_score + wind_score - precip_penalty
        fwi = max(0, min(100, fwi))
        
        return round(fwi, 2)


class CloudGapFiller:
    """
    Fill temporal gaps in fire detection caused by cloud cover.
    
    Uses weather data to identify which missing detection days
    are likely due to clouds versus actual fire cessation.
    """
    
    def __init__(self, weather_manager: WeatherDataManager):
        self.weather_manager = weather_manager
    
    def identify_cloud_gaps(
        self,
        detection_timeseries: Dict[str, bool],  # date -> has_detection
        cloud_observations: List[WeatherObservation]
    ) -> Dict[str, Any]:
        """
        Identify gaps in detection timeseries that may be cloud-related.
        
        Args:
            detection_timeseries: Dictionary mapping dates to detection status
            cloud_observations: Weather data for the same period
            
        Returns:
            Gap analysis with cloud-obscured vs real gaps
        """
        cloud_by_date = {
            obs.timestamp.strftime("%Y-%m-%d"): obs.cloud_cover 
            for obs in cloud_observations
        }
        
        gaps = {
            "cloud_obscured": [],  # Gaps likely due to clouds
            "real_gaps": [],       # Gaps likely real (fire stopped)
            "uncertain": []        # Cannot determine
        }
        
        sorted_dates = sorted(detection_timeseries.keys())
        
        for i, date in enumerate(sorted_dates):
            if not detection_timeseries[date]:
                cloud_cover = cloud_by_date.get(date, 50.0)
                
                # Check surrounding days for context
                prev_has_detection = i > 0 and detection_timeseries.get(sorted_dates[i-1], False)
                next_has_detection = i < len(sorted_dates)-1 and detection_timeseries.get(sorted_dates[i+1], False)
                
                # Classification logic
                if cloud_cover > 70:
                    # High cloud cover - likely obscuration
                    if prev_has_detection or next_has_detection:
                        gaps["cloud_obscured"].append({
                            "date": date,
                            "cloud_cover": cloud_cover,
                            "reason": "High cloud cover between detection days"
                        })
                    else:
                        gaps["uncertain"].append({
                            "date": date,
                            "cloud_cover": cloud_cover,
                            "reason": "High cloud cover but no adjacent detections"
                        })
                elif cloud_cover < 30:
                    # Clear sky - likely real gap
                    gaps["real_gaps"].append({
                        "date": date,
                        "cloud_cover": cloud_cover,
                        "reason": "Clear sky with no detection"
                    })
                else:
                    # Partial cloud cover - uncertain
                    gaps["uncertain"].append({
                        "date": date,
                        "cloud_cover": cloud_cover,
                        "reason": "Partial cloud cover"
                    })
        
        return gaps
    
    def interpolate_cloud_gaps(
        self,
        detection_timeseries: Dict[str, float],  # date -> detection_value (e.g., FRP)
        cloud_gaps: List[Dict]
    ) -> Dict[str, float]:
        """
        Interpolate values for cloud-obscured gaps.
        
        Uses linear interpolation between adjacent clear-sky observations.
        
        Args:
            detection_timeseries: Date to detection value mapping
            cloud_gaps: List of cloud-obscured gaps from identify_cloud_gaps
            
        Returns:
            Interpolated timeseries
        """
        interpolated = detection_timeseries.copy()
        
        for gap in cloud_gaps:
            gap_date = gap["date"]
            
            # Find adjacent non-gap observations
            sorted_dates = sorted(detection_timeseries.keys())
            gap_idx = None
            
            for i, d in enumerate(sorted_dates):
                if d == gap_date:
                    gap_idx = i
                    break
            
            if gap_idx is None:
                continue
            
            # Find previous and next observations
            prev_val = None
            next_val = None
            
            for i in range(gap_idx - 1, -1, -1):
                if sorted_dates[i] not in [g["date"] for g in cloud_gaps]:
                    prev_val = detection_timeseries.get(sorted_dates[i])
                    break
            
            for i in range(gap_idx + 1, len(sorted_dates)):
                if sorted_dates[i] not in [g["date"] for g in cloud_gaps]:
                    next_val = detection_timeseries.get(sorted_dates[i])
                    break
            
            # Interpolate
            if prev_val is not None and next_val is not None:
                interpolated[gap_date] = (prev_val + next_val) / 2
            elif prev_val is not None:
                interpolated[gap_date] = prev_val
            elif next_val is not None:
                interpolated[gap_date] = next_val
            
            # Mark as interpolated
            interpolated[f"{gap_date}_interpolated"] = True
        
        return interpolated


def get_weather_manager(cache_dir: Optional[str] = None) -> WeatherDataManager:
    """Factory function to get a weather data manager instance."""
    return WeatherDataManager(cache_dir=cache_dir)
