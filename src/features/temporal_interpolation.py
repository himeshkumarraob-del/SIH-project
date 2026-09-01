"""
Temporal Interpolation Module.

Provides methods for filling temporal gaps in fire detection timeseries
caused by cloud cover, missing observations, or sensor issues.

Uses various interpolation techniques while preserving the integrity
of observed data and clearly marking interpolated values.
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
import numpy as np

from src.logging_setup import get_logger

logger = get_logger("features.temporal_interpolation")


@dataclass
class InterpolationResult:
    """Container for interpolation results."""
    original_timeseries: Dict[str, float]
    interpolated_timeseries: Dict[str, float]
    interpolation_mask: Dict[str, bool]  # True = interpolated
    interpolation_method: str
    quality_score: float  # 0-1, higher = more reliable interpolation
    warnings: List[str]


class TemporalInterpolator:
    """
    Interpolates missing values in temporal fire detection data.
    
    Handles gaps caused by:
    - Cloud cover obscuring observations
    - Sensor downtime
    - Data quality filtering
    """
    
    def __init__(self):
        self.methods = {
            "linear": self._linear_interpolation,
            "nearest": self._nearest_interpolation,
            "kalman": self._kalman_interpolation,
            "gaussian_process": self._gaussian_process_interpolation
        }
    
    def interpolate(
        self,
        timeseries: Dict[str, float],
        cloud_info: Optional[Dict[str, bool]] = None,
        method: str = "linear",
        max_gap_days: int = 3
    ) -> InterpolationResult:
        """
        Interpolate missing values in a timeseries.
        
        Args:
            timeseries: Dictionary mapping date strings to values
                       Missing dates should not be in the dict
            cloud_info: Optional dict mapping dates to cloud obscuration status
            method: Interpolation method ('linear', 'nearest', 'kalman', 'gaussian_process')
            max_gap_days: Maximum gap size to interpolate (larger gaps are left as-is)
            
        Returns:
            InterpolationResult with interpolated values and metadata
        """
        if method not in self.methods:
            logger.warning(f"Unknown method '{method}', falling back to 'linear'")
            method = "linear"
        
        # Sort dates
        sorted_dates = sorted(timeseries.keys())
        
        if len(sorted_dates) < 2:
            return InterpolationResult(
                original_timeseries=timeseries.copy(),
                interpolated_timeseries=timeseries.copy(),
                interpolation_mask={d: False for d in sorted_dates},
                interpolation_method=method,
                quality_score=1.0,
                warnings=["Insufficient data for interpolation"]
            )
        
        # Identify gaps
        gaps = self._identify_gaps(sorted_dates)
        
        # Filter gaps by size and cloud info
        interpolatable_gaps = []
        for gap_start, gap_end, gap_dates in gaps:
            gap_size = len(gap_dates)
            
            if gap_size > max_gap_days:
                continue
            
            # Check if gap is cloud-related
            if cloud_info:
                cloud_related = all(
                    cloud_info.get(d, False) for d in gap_dates
                )
                if not cloud_related:
                    continue
            
            interpolatable_gaps.append((gap_start, gap_end, gap_dates))
        
        # Apply interpolation
        interpolated = timeseries.copy()
        interpolation_mask = {d: False for d in sorted_dates}
        
        for gap_start, gap_end, gap_dates in interpolatable_gaps:
            # Get values before and after gap
            val_before = timeseries.get(gap_start)
            val_after = timeseries.get(gap_end)
            
            if val_before is None or val_after is None:
                continue
            
            # Interpolate
            interp_func = self.methods[method]
            interp_values = interp_func(
                val_before, val_after, 
                len(gap_dates),
                gap_start, gap_end
            )
            
            # Fill in values
            for d, v in zip(gap_dates, interp_values):
                interpolated[d] = v
                interpolation_mask[d] = True
        
        # Calculate quality score
        quality = self._calculate_interpolation_quality(
            timeseries, interpolated, interpolation_mask, gaps
        )
        
        # Generate warnings
        warnings = self._generate_warnings(interpolation_mask, gaps)
        
        return InterpolationResult(
            original_timeseries=timeseries.copy(),
            interpolated_timeseries=interpolated,
            interpolation_mask=interpolation_mask,
            interpolation_method=method,
            quality_score=quality,
            warnings=warnings
        )
    
    def _identify_gaps(self, sorted_dates: List[str]) -> List[Tuple[str, str, List[str]]]:
        """
        Identify gaps in the sorted date list.
        
        Returns list of (gap_start, gap_end, gap_dates) tuples.
        """
        from datetime import datetime, timedelta
        
        gaps = []
        
        for i in range(len(sorted_dates) - 1):
            date1 = datetime.fromisoformat(sorted_dates[i])
            date2 = datetime.fromisoformat(sorted_dates[i + 1])
            
            diff_days = (date2 - date1).days
            
            if diff_days > 1:
                # There's a gap
                gap_dates = []
                current = date1 + timedelta(days=1)
                while current < date2:
                    gap_dates.append(current.strftime("%Y-%m-%d"))
                    current += timedelta(days=1)
                
                gaps.append((sorted_dates[i], sorted_dates[i + 1], gap_dates))
        
        return gaps
    
    def _linear_interpolation(
        self,
        val_before: float,
        val_after: float,
        n_points: int,
        date_before: str,
        date_after: str
    ) -> List[float]:
        """Linear interpolation between two points."""
        return [
            val_before + (val_after - val_before) * (i + 1) / (n_points + 1)
            for i in range(n_points)
        ]
    
    def _nearest_interpolation(
        self,
        val_before: float,
        val_after: float,
        n_points: int,
        date_before: str,
        date_after: str
    ) -> List[float]:
        """Nearest neighbor interpolation."""
        # Use the closer value
        mid = n_points // 2
        return [
            val_before if i <= mid else val_after
            for i in range(n_points)
        ]
    
    def _kalman_interpolation(
        self,
        val_before: float,
        val_after: float,
        n_points: int,
        date_before: str,
        date_after: str
    ) -> List[float]:
        """
        Simple Kalman-like interpolation.
        
        Assumes linear trend with noise.
        """
        # Simple approach: linear with uncertainty growth
        linear_values = self._linear_interpolation(
            val_before, val_after, n_points, date_before, date_after
        )
        
        # Add small noise to simulate Kalman uncertainty
        noise_scale = abs(val_after - val_before) * 0.1
        noisy_values = [
            v + np.random.normal(0, noise_scale * (i + 1) / n_points)
            for i, v in enumerate(linear_values)
        ]
        
        return noisy_values
    
    def _gaussian_process_interpolation(
        self,
        val_before: float,
        val_after: float,
        n_points: int,
        date_before: str,
        date_after: str
    ) -> List[float]:
        """
        Simple Gaussian Process interpolation.
        
        Uses RBF kernel approximation for smooth interpolation.
        """
        # For simplicity, use cubic interpolation (smooth curve)
        x = np.array([0, 1])
        y = np.array([val_before, val_after])
        
        # Create smooth interpolation points
        x_new = np.linspace(0, 1, n_points + 2)[1:-1]
        
        # Simple cubic-like interpolation
        t = x_new
        interp_values = val_before + (val_after - val_before) * (3 * t**2 - 2 * t**3)
        
        return interp_values.tolist()
    
    def _calculate_interpolation_quality(
        self,
        original: Dict[str, float],
        interpolated: Dict[str, float],
        mask: Dict[str, bool],
        gaps: List
    ) -> float:
        """
        Calculate quality score for interpolation.
        
        Factors:
        - Number of interpolated points vs original
        - Gap sizes (smaller gaps = better)
        - Consistency with original data
        """
        n_original = sum(1 for v in mask.values() if not v)
        n_interpolated = sum(1 for v in mask.values() if v)
        n_total = len(mask)
        
        if n_total == 0:
            return 1.0
        
        # Penalty for high interpolation ratio
        interp_ratio = n_interpolated / n_total
        ratio_score = 1.0 - (interp_ratio * 0.5)  # Max 50% penalty
        
        # Penalty for large gaps
        max_gap = max(len(g[2]) for g in gaps) if gaps else 0
        gap_penalty = min(0.3, max_gap * 0.1)
        
        # Combine scores
        quality = max(0.0, ratio_score - gap_penalty)
        
        return round(quality, 3)
    
    def _generate_warnings(
        self,
        mask: Dict[str, bool],
        gaps: List
    ) -> List[str]:
        """Generate warnings about interpolation quality."""
        warnings = []
        
        n_interpolated = sum(1 for v in mask.values() if v)
        n_total = len(mask)
        
        if n_total > 0 and n_interpolated / n_total > 0.3:
            warnings.append(
                f"High interpolation ratio: {n_interpolated}/{n_total} points interpolated"
            )
        
        for gap_start, gap_end, gap_dates in gaps:
            if len(gap_dates) > 2:
                warnings.append(
                    f"Large gap between {gap_start} and {gap_end} ({len(gap_dates)} days)"
                )
        
        return warnings


class CloudAwareInterpolator(TemporalInterpolator):
    """
    Enhanced interpolator that uses cloud data to improve gap filling.
    """
    
    def interpolate_with_cloud_data(
        self,
        timeseries: Dict[str, float],
        cloud_cover_timeseries: Dict[str, float],
        method: str = "linear"
    ) -> InterpolationResult:
        """
        Interpolate using cloud cover information.
        
        Args:
            timeseries: Fire detection values
            cloud_cover_timeseries: Cloud cover values (0-100)
            method: Interpolation method
            
        Returns:
            InterpolationResult with cloud-aware interpolation
        """
        # Identify cloud-obscured gaps
        cloud_info = {
            date: cover > 70  # Assume >70% cloud cover obscures detection
            for date, cover in cloud_cover_timeseries.items()
        }
        
        # Use base interpolation with cloud info
        result = self.interpolate(
            timeseries,
            cloud_info=cloud_info,
            method=method
        )
        
        # Add cloud-specific quality adjustments
        cloud_quality_adjustment = self._assess_cloud_impact(
            cloud_cover_timeseries, result.interpolation_mask
        )
        
        # Adjust quality score
        result.quality_score = max(0.0, min(1.0, 
            result.quality_score * cloud_quality_adjustment
        ))
        
        return result
    
    def _assess_cloud_impact(
        self,
        cloud_cover: Dict[str, float],
        interpolation_mask: Dict[str, bool]
    ) -> float:
        """
        Assess how cloud cover affects interpolation quality.
        """
        interpolated_dates = [d for d, v in interpolation_mask.items() if v]
        
        if not interpolated_dates:
            return 1.0
        
        # Check cloud cover on interpolated dates
        cloud_covers = [
            cloud_cover.get(d, 50.0) for d in interpolated_dates
        ]
        
        avg_cloud_cover = np.mean(cloud_covers) if cloud_covers else 50.0
        
        # Higher cloud cover on interpolated dates = more reliable interpolation
        # (because the gap was likely caused by clouds)
        if avg_cloud_cover > 70:
            return 1.0  # High confidence - gaps were cloud-related
        elif avg_cloud_cover > 50:
            return 0.9  # Moderate confidence
        else:
            return 0.7  # Lower confidence - gaps may not be cloud-related


def interpolate_cluster_timeseries(
    cluster_detections: List[Dict[str, Any]],
    cloud_observations: Optional[List[Dict[str, Any]]] = None,
    method: str = "linear"
) -> InterpolationResult:
    """
    Convenience function to interpolate a cluster's detection timeseries.
    
    Args:
        cluster_detections: List of detection records with 'acq_date' and values
        cloud_observations: Optional cloud observations
        method: Interpolation method
        
    Returns:
        InterpolationResult
    """
    # Convert to timeseries format
    timeseries = {}
    for det in cluster_detections:
        date = det.get("acq_date", "")
        value = det.get("frp", det.get("max_bright_ti4", 0))
        if date:
            # Keep max value if multiple observations per day
            if date in timeseries:
                timeseries[date] = max(timeseries[date], value)
            else:
                timeseries[date] = value
    
    # Convert cloud observations if provided
    cloud_timeseries = None
    if cloud_observations:
        cloud_timeseries = {}
        for obs in cloud_observations:
            date = obs.get("date", "")
            cover = obs.get("cloud_cover", 50.0)
            if date:
                cloud_timeseries[date] = cover
    
    # Interpolate
    interpolator = CloudAwareInterpolator()
    
    if cloud_timeseries:
        result = interpolator.interpolate_with_cloud_data(
            timeseries, cloud_timeseries, method
        )
    else:
        result = interpolator.interpolate(timeseries, method=method)
    
    return result
