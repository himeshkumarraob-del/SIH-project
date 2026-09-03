"""
Seasonal Fire Patterns Module.

Adjusts fire detection confidence and classification based on
regional seasonal patterns, agricultural burning calendars,
and fire weather indices.

This module adds context-aware intelligence without modifying
existing detection algorithms.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, date

from src.logging_setup import get_logger

logger = get_logger("models.seasonal_patterns")


@dataclass
class RegionalFireSeason:
    """Fire season information for a specific region."""
    region_name: str
    country: str
    peak_months: List[int]  # Months with highest fire activity (1-12)
    agricultural_burning_months: List[int]  # Crop residue burning
    forest_fire_months: List[int]  # Natural forest fire season
    industrial_baseline_months: List[int]  # Industrial fires are year-round
    notes: Optional[str] = None


# Predefined regional fire seasons for India
INDIA_FIRE_SEASONS = {
    "north_india": RegionalFireSeason(
        region_name="North India (Punjab, Haryana, UP)",
        country="India",
        peak_months=[10, 11, 12],  # Oct-Dec
        agricultural_burning_months=[10, 11],  # Post-harvest stubble burning
        forest_fire_months=[3, 4, 5],  # Pre-monsoon dry season
        industrial_baseline_months=list(range(1, 13)),  # Year-round
        notes="Major agricultural stubble burning in Oct-Nov causes severe air pollution"
    ),
    "central_india": RegionalFireSeason(
        region_name="Central India (MP, Chhattisgarh, Maharashtra)",
        country="India",
        peak_months=[3, 4, 5, 6],  # Mar-Jun
        agricultural_burning_months=[3, 4],  # Summer crop residue
        forest_fire_months=[2, 3, 4, 5],  # Dry season forest fires
        industrial_baseline_months=list(range(1, 13)),
        notes="Coal mining regions have persistent industrial thermal signatures"
    ),
    "eastern_india": RegionalFireSeason(
        region_name="Eastern India (Jharkhand, Odisha, West Bengal)",
        country="India",
        peak_months=[3, 4, 5],
        agricultural_burning_months=[4, 5],
        forest_fire_months=[2, 3, 4],
        industrial_baseline_months=list(range(1, 13)),
        notes="Coal belt region with frequent mining-related thermal events"
    ),
    "south_india": RegionalFireSeason(
        region_name="South India (Tamil Nadu, Kerala, Karnataka)",
        country="India",
        peak_months=[2, 3, 4],  # Feb-Apr
        agricultural_burning_months=[3, 4],  # Summer crop burning
        forest_fire_months=[2, 3, 4],  # Pre-monsoon
        industrial_baseline_months=list(range(1, 13)),
        notes="Western Ghats forest fires peak in Feb-Apr"
    ),
    "western_india": RegionalFireSeason(
        region_name="Western India (Rajasthan, Gujarat)",
        country="India",
        peak_months=[4, 5, 6],
        agricultural_burning_months=[5, 6],
        forest_fire_months=[3, 4, 5],
        industrial_baseline_months=list(range(1, 13)),
        notes="Thar Desert has naturally higher thermal baseline"
    ),
    "northeast_india": RegionalFireSeason(
        region_name="Northeast India (Assam, Manipur, Mizoram)",
        country="India",
        peak_months=[2, 3, 4],
        agricultural_burning_months=[2, 3],  # Jhum cultivation
        forest_fire_months=[1, 2, 3, 4],  # Extended dry season
        industrial_baseline_months=list(range(1, 13)),
        notes="Shifting cultivation (jhum) creates seasonal fire patterns"
    ),
}


class SeasonalFirePatterns:
    """
    Analyzes and applies seasonal context to fire detection and classification.
    
    Helps distinguish between:
    - Expected seasonal fires (agricultural burning during harvest)
    - Unexpected off-season fires (potentially industrial/anomalous)
    - Year-round industrial sources (power plants, factories)
    """
    
    def __init__(self):
        self.regional_seasons = INDIA_FIRE_SEASONS.copy()
    
    def get_regional_season(self, latitude: float, longitude: float) -> Optional[RegionalFireSeason]:
        """
        Determine the regional fire season based on coordinates.
        
        Uses simple bounding boxes for Indian regions.
        """
        # Simplified region detection based on lat/lon
        if 28 <= latitude <= 35 and 73 <= longitude <= 80:
            return self.regional_seasons.get("north_india")
        elif 20 <= latitude <= 28 and 73 <= longitude <= 82:
            return self.regional_seasons.get("central_india")
        elif 20 <= latitude <= 27 and 82 <= longitude <= 90:
            return self.regional_seasons.get("eastern_india")
        elif 8 <= latitude <= 20 and 73 <= longitude <= 82:
            return self.regional_seasons.get("south_india")
        elif 22 <= latitude <= 30 and 68 <= longitude <= 75:
            return self.regional_seasons.get("western_india")
        elif 22 <= latitude <= 29 and 89 <= longitude <= 98:
            return self.regional_seasons.get("northeast_india")
        
        return None
    
    def adjust_classification_by_season(
        self,
        raw_classification: str,
        classification_score: float,
        latitude: float,
        longitude: float,
        detection_date: str,
        thermal_characteristics: Dict[str, float]
    ) -> Tuple[str, float, str]:
        """
        Adjust fire classification based on seasonal context.
        
        Args:
            raw_classification: Original classification (Industrial/Agricultural/Forest/Unknown)
            classification_score: Original confidence score (0-1)
            latitude: Detection latitude
            longitude: Detection longitude
            detection_date: Date of detection (YYYY-MM-DD)
            thermal_characteristics: Dict with thermal features (FRP, brightness, etc.)
            
        Returns:
            Tuple of (adjusted_classification, adjusted_score, rationale)
        """
        region = self.get_regional_season(latitude, longitude)
        
        if region is None:
            return raw_classification, classification_score, "No regional season data available"
        
        try:
            detection_month = datetime.fromisoformat(detection_date).month
        except:
            return raw_classification, classification_score, "Invalid date format"
        
        adjusted_score = classification_score
        rationale_parts = []
        
        # Check if detection is during expected agricultural burning season
        is_agricultural_season = detection_month in region.agricultural_burning_months
        is_forest_season = detection_month in region.forest_fire_months
        is_industrial_season = detection_month in region.industrial_baseline_months
        
        # Thermal characteristics for classification hints
        max_frp = thermal_characteristics.get("max_frp", 0)
        is_stationary = thermal_characteristics.get("movement_status", "").upper() == "STATIONARY"
        has_persistence = thermal_characteristics.get("persistence_category", "") == "persistent"
        
        # Adjust Agricultural classification
        if raw_classification == "Agricultural-context thermal event":
            if is_agricultural_season:
                adjusted_score = min(1.0, adjusted_score * 1.2)  # Boost confidence
                rationale_parts.append(f"Detection aligns with {region.region_name} agricultural burning season (month {detection_month})")
            else:
                adjusted_score = adjusted_score * 0.8  # Reduce confidence
                rationale_parts.append(f"Agricultural classification outside typical burning season")
        
        # Adjust Forest classification
        elif raw_classification == "Forest/Natural-context thermal event":
            if is_forest_season:
                adjusted_score = min(1.0, adjusted_score * 1.15)
                rationale_parts.append(f"Detection during forest fire season for {region.region_name}")
            else:
                adjusted_score = adjusted_score * 0.85
                rationale_parts.append(f"Forest fire classification outside typical fire season")
        
        # Adjust Industrial classification
        elif raw_classification == "Industrial-context thermal event":
            if is_stationary and has_persistence:
                # Industrial fires are year-round and stationary
                adjusted_score = min(1.0, adjusted_score * 1.1)
                rationale_parts.append(f"Persistent stationary activity consistent with industrial source")
            elif not is_industrial_season:
                adjusted_score = adjusted_score * 0.9
                rationale_parts.append(f"Industrial classification during atypical period")
        
        # Unknown classification - try to infer from season
        elif raw_classification == "Unknown / Insufficient Evidence":
            if is_agricultural_season and max_frp > 5.0 and not is_stationary:
                # During agricultural season with moderate FRP and movement
                raw_classification = "Agricultural-context thermal event"
                adjusted_score = 0.5
                rationale_parts.append(f"Inferred agricultural burning during {region.region_name} burning season")
            
            elif is_forest_season and max_frp > 15.0:
                # During forest fire season with high FRP
                raw_classification = "Forest/Natural-context thermal event"
                adjusted_score = 0.45
                rationale_parts.append(f"Inferred forest fire during {region.region_name} fire season")
        
        # Cap score
        adjusted_score = max(0.0, min(1.0, adjusted_score))
        
        rationale = "; ".join(rationale_parts) if rationale_parts else "No seasonal adjustment applied"
        
        return raw_classification, adjusted_score, rationale
    
    def calculate_seasonal_risk_modifier(
        self,
        latitude: float,
        longitude: float,
        detection_date: str,
        fire_type: str
    ) -> float:
        """
        Calculate a risk modifier based on seasonal context.
        
        Returns a multiplier (0.7-1.3) to adjust risk scores.
        
        Args:
            latitude: Detection latitude
            longitude: Detection longitude
            detection_date: Date of detection
            fire_type: Classified fire type
            
        Returns:
            Risk modifier (multiplier)
        """
        region = self.get_regional_season(latitude, longitude)
        
        if region is None:
            return 1.0
        
        try:
            detection_month = datetime.fromisoformat(detection_date).month
        except:
            return 1.0
        
        modifier = 1.0
        
        # Agricultural fires during burning season are expected - lower risk
        if "Agricultural" in fire_type:
            if detection_month in region.agricultural_burning_months:
                modifier = 0.75  # Expected - lower priority
            else:
                modifier = 1.2  # Unexpected - higher priority
        
        # Forest fires during fire season are expected but still high risk
        elif "Forest" in fire_type or "Natural" in fire_type:
            if detection_month in region.forest_fire_months:
                modifier = 1.0  # Expected but still important
            else:
                modifier = 1.3  # Unusual timing - investigate
        
        # Industrial fires are always important
        elif "Industrial" in fire_type:
            modifier = 1.15  # Slightly elevated due to industrial context
        
        return modifier
    
    def generate_seasonal_report(
        self,
        detections: List[Dict[str, Any]],
        latitude: float,
        longitude: float
    ) -> Dict[str, Any]:
        """
        Generate a seasonal analysis report for a set of detections.
        
        Args:
            detections: List of detection records
            latitude: Region latitude
            longitude: Region longitude
            
        Returns:
            Seasonal analysis report
        """
        region = self.get_regional_season(latitude, longitude)
        
        report = {
            "region": region.region_name if region else "Unknown",
            "total_detections": len(detections),
            "seasonal_alignment": {},
            "recommendations": []
        }
        
        if region is None:
            report["recommendations"].append("No regional season data available")
            return report
        
        # Count detections by month
        monthly_counts = {}
        for det in detections:
            try:
                month = datetime.fromisoformat(det.get("acq_date", "")).month
                monthly_counts[month] = monthly_counts.get(month, 0) + 1
            except:
                continue
        
        # Analyze alignment
        for month, count in monthly_counts.items():
            is_agri = month in region.agricultural_burning_months
            is_forest = month in region.forest_fire_months
            
            report["seasonal_alignment"][month] = {
                "detection_count": count,
                "is_agricultural_burning_season": is_agri,
                "is_forest_fire_season": is_forest
            }
        
        # Generate recommendations
        if any(monthly_counts.get(m, 0) > 5 for m in region.agricultural_burning_months):
            report["recommendations"].append(
                "High detection count during agricultural burning season - "
                "expect increased agricultural fire classifications"
            )
        
        if any(monthly_counts.get(m, 0) > 0 for m in region.forest_fire_months):
            report["recommendations"].append(
                "Active fire detections during forest fire season - "
                "monitor for potential wildfire escalation"
            )
        
        return report


def get_seasonal_patterns() -> SeasonalFirePatterns:
    """Factory function to get seasonal patterns instance."""
    return SeasonalFirePatterns()
