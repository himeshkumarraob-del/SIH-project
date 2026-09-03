"""
Cloud Detection Module for Satellite Imagery.

Detects and classifies clouds in satellite images to estimate
thermal infrared penetration for fire detection under cloudy conditions.

This module is designed to work alongside existing fire detection
without modifying core functionality.
"""

from __future__ import annotations

from typing import Dict, Any, Tuple, Optional
from pathlib import Path
import numpy as np
from dataclasses import dataclass

from src.logging_setup import get_logger

logger = get_logger("satellite.cloud_detector")


@dataclass
class CloudInfo:
    """Container for cloud detection results."""
    cloud_probability: float  # 0.0 (clear) to 1.0 (fully cloudy)
    cloud_type: str  # 'clear', 'cirrus', 'cumulus', 'stratus', 'cumulonimbus'
    ir_penetration_factor: float  # 0.0 (no penetration) to 1.0 (full penetration)
    confidence: float  # Confidence in cloud detection
    optical_depth: Optional[float] = None  # Cloud optical depth if available


class CloudDetector:
    """
    Detect and classify clouds in satellite imagery.
    
    Uses spectral thresholds and machine learning to identify cloud types
    and estimate how much thermal infrared signal penetrates through them.
    
    Cloud IR Penetration Rates (approximate):
    - Cirrus (thin): 60-80% penetration
    - Cumulus (fair weather): 40-60% penetration
    - Stratus (thick): 10-30% penetration
    - Cumulonimbus (thunderstorm): 5-15% penetration
    """
    
    # VIIRS band-specific cloud detection thresholds
    VIIRS_THRESHOLDS = {
        'bright_ti4_cloud': 280.0,  # Brightness temp threshold for cloud detection
        'bright_ti5_cloud': 270.0,  # Thermal IR cloud threshold
        'bt_diff_clear_min': 15.0,  # Minimum BT difference for clear sky
        'bt_diff_cirrus_max': 25.0,  # Max BT diff for cirrus clouds
    }
    
    # Cloud type IR penetration factors (higher = more IR penetrates)
    CLOUD_PENETRATION = {
        'clear': 1.0,
        'cirrus': 0.7,  # Thin ice clouds - good IR penetration
        'cumulus': 0.5,  # Fair weather clouds - moderate penetration
        'stratus': 0.2,  # Thick low clouds - poor penetration
        'cumulonimbus': 0.1,  # Thunderstorm clouds - very poor penetration
        'unknown': 0.5,  # Default for unknown cloud types
    }
    
    def __init__(self, use_ml: bool = False):
        """
        Initialize cloud detector.
        
        Args:
            use_ml: If True, use ML model for cloud detection (requires training)
                   If False, use spectral threshold-based detection (default)
        """
        self.use_ml = use_ml
        self.ml_model = None
        
        if use_ml:
            logger.info("ML cloud detection enabled (requires trained model)")
        else:
            logger.info("Using spectral threshold-based cloud detection")
    
    def detect_clouds_from_viirs(
        self, 
        bright_ti4: float, 
        bright_ti5: float,
        latitude: float = 0.0,
        longitude: float = 0.0
    ) -> CloudInfo:
        """
        Detect clouds from VIIRS brightness temperatures.
        
        Args:
            bright_ti4: VIIRS I-band 4 brightness temperature (K)
            bright_ti5: VIIRS I-band 5 brightness temperature (K)
            latitude: Observation latitude (for regional calibration)
            longitude: Observation longitude
            
        Returns:
            CloudInfo with cloud detection results
        """
        # Calculate spectral difference
        bt_diff = bright_ti4 - bright_ti5
        
        # Cloud detection logic based on VIIRS spectral signatures
        cloud_prob = self._estimate_cloud_probability(bright_ti4, bright_ti5, bt_diff)
        cloud_type = self._classify_cloud_type(bright_ti4, bright_ti5, bt_diff)
        ir_penetration = self.CLOUD_PENETRATION.get(cloud_type, 0.5)
        
        return CloudInfo(
            cloud_probability=cloud_prob,
            cloud_type=cloud_type,
            ir_penetration_factor=ir_penetration,
            confidence=0.8,  # Threshold-based confidence
            optical_depth=None
        )
    
    def _estimate_cloud_probability(
        self, 
        ti4: float, 
        ti5: float, 
        bt_diff: float
    ) -> float:
        """
        Estimate cloud probability from VIIRS channels.
        
        Clouds typically show:
        - Lower brightness temperatures than clear ground
        - Smaller I4-I5 difference than clear sky
        """
        prob = 0.0
        
        # Low brightness temperature suggests clouds
        if ti4 < self.VIIRS_THRESHOLDS['bright_ti4_cloud']:
            prob += 0.3
        if ti5 < self.VIIRS_THRESHOLDS['bright_ti5_cloud']:
            prob += 0.3
        
        # Small BT difference suggests clouds (not fire)
        if bt_diff < self.VIIRS_THRESHOLDS['bt_diff_clear_min']:
            prob += 0.2
        
        # Very small BT difference suggests thick clouds
        if bt_diff < 5.0:
            prob += 0.2
        
        return min(prob, 1.0)
    
    def _classify_cloud_type(
        self, 
        ti4: float, 
        ti5: float, 
        bt_diff: float
    ) -> str:
        """
        Classify cloud type based on spectral characteristics.
        """
        # Clear sky indicators
        if bt_diff > self.VIIRS_THRESHOLDS['bt_diff_clear_min']:
            if ti4 > 300:  # Warm surface
                return 'clear'
        
        # Cirrus clouds (thin ice clouds)
        if bt_diff > self.VIIRS_THRESHOLDS['bt_diff_cirrus_max']:
            if ti4 > 260:
                return 'cirrus'
        
        # Thick clouds (stratus/cumulonimbus)
        if bt_diff < 10.0:
            if ti4 < 270:
                return 'cumulonimbus'
            else:
                return 'stratus'
        
        # Moderate clouds (cumulus)
        if bt_diff < self.VIIRS_THRESHOLDS['bt_diff_clear_min']:
            return 'cumulus'
        
        return 'unknown'
    
    def detect_clouds_from_image(
        self, 
        image: np.ndarray,
        cloud_model=None
    ) -> CloudInfo:
        """
        Detect clouds from satellite image patch.
        
        Args:
            image: RGB or multispectral image array (H, W, C)
            cloud_model: Optional trained cloud detection model
            
        Returns:
            CloudInfo with cloud detection results
        """
        if cloud_model is not None:
            return self._ml_cloud_detection(image, cloud_model)
        
        # Fallback to simple threshold-based detection
        return self._threshold_cloud_detection(image)
    
    def _threshold_cloud_detection(self, image: np.ndarray) -> CloudInfo:
        """
        Simple threshold-based cloud detection for RGB images.
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = np.mean(image, axis=2)
        else:
            gray = image
        
        # Simple cloud detection: bright areas are likely clouds
        cloud_mask = gray > np.percentile(gray, 70)
        cloud_fraction = np.mean(cloud_mask)
        
        # Classify based on cloud fraction
        if cloud_fraction < 0.1:
            cloud_type = 'clear'
        elif cloud_fraction < 0.3:
            cloud_type = 'cirrus'
        elif cloud_fraction < 0.6:
            cloud_type = 'cumulus'
        else:
            cloud_type = 'stratus'
        
        ir_penetration = self.CLOUD_PENETRATION.get(cloud_type, 0.5)
        
        return CloudInfo(
            cloud_probability=cloud_fraction,
            cloud_type=cloud_type,
            ir_penetration_factor=ir_penetration,
            confidence=0.6  # Lower confidence for simple threshold method
        )
    
    def _ml_cloud_detection(self, image: np.ndarray, model) -> CloudInfo:
        """
        ML-based cloud detection (placeholder for future implementation).
        """
        # Placeholder: would use trained model here
        logger.warning("ML cloud detection not yet implemented, using fallback")
        return self._threshold_cloud_detection(image)
    
    def adjust_detection_confidence(
        self, 
        raw_confidence: float, 
        cloud_info: CloudInfo
    ) -> float:
        """
        Adjust fire detection confidence based on cloud conditions.
        
        Args:
            raw_confidence: Original detection confidence (0-1)
            cloud_info: Cloud detection results
            
        Returns:
            Adjusted confidence accounting for cloud cover
        """
        # Adjustment factors
        cloud_penalty = 1.0 - (cloud_info.cloud_probability * 0.5)
        penetration_bonus = cloud_info.ir_penetration_factor
        
        # Combined adjustment
        adjusted = raw_confidence * cloud_penalty * penetration_bonus
        
        # Ensure reasonable bounds
        adjusted = max(0.1, min(adjusted, 1.0))
        
        return round(adjusted, 4)
    
    def should_flag_for_review(
        self, 
        cloud_info: CloudInfo, 
        detection_confidence: float
    ) -> Tuple[bool, str]:
        """
        Determine if a detection should be flagged for human review
        due to cloud-related uncertainty.
        
        Returns:
            Tuple of (should_flag, reason)
        """
        if cloud_info.cloud_probability > 0.7:
            return True, "Heavy cloud cover detected - detection may be unreliable"
        
        if cloud_info.ir_penetration_factor < 0.3:
            return True, "Low IR penetration expected - thermal signal likely attenuated"
        
        if detection_confidence < 0.4 and cloud_info.cloud_probability > 0.3:
            return True, "Low confidence detection under partial cloud cover"
        
        return False, ""


class CloudAwareFireDetector:
    """
    Wrapper to make existing fire detection cloud-aware.
    
    This class can wrap existing detection logic and add cloud awareness
    without modifying the original detection code.
    """
    
    def __init__(self, base_detector):
        """
        Args:
            base_detector: Original fire detector instance
        """
        self.base_detector = base_detector
        self.cloud_detector = CloudDetector()
    
    def detect_with_cloud_awareness(
        self, 
        observations: list,
        cloud_observations: Optional[list] = None
    ) -> list:
        """
        Run fire detection with cloud awareness.
        
        Args:
            observations: List of thermal observations
            cloud_observations: Optional parallel list of cloud observations
            
        Returns:
            List of detections with cloud-adjusted confidence
        """
        detections = []
        
        for i, obs in enumerate(observations):
            # Get cloud info if available
            if cloud_observations and i < len(cloud_observations):
                cloud_info = self.cloud_detector.detect_clouds_from_viirs(
                    obs.get('bright_ti4', 0),
                    obs.get('bright_ti5', 0)
                )
            else:
                # No cloud data available
                cloud_info = CloudInfo(
                    cloud_probability=0.0,
                    cloud_type='unknown',
                    ir_penetration_factor=0.5,
                    confidence=0.3
                )
            
            # Run base detection
            raw_detection = self.base_detector.detect(obs)
            
            if raw_detection is not None:
                # Adjust confidence
                adjusted_confidence = self.cloud_detector.adjust_detection_confidence(
                    raw_detection.get('confidence', 0.5),
                    cloud_info
                )
                
                # Add cloud metadata
                raw_detection['cloud_adjusted_confidence'] = adjusted_confidence
                raw_detection['cloud_type'] = cloud_info.cloud_type
                raw_detection['cloud_probability'] = cloud_info.cloud_probability
                
                # Check if should flag for review
                should_flag, reason = self.cloud_detector.should_flag_for_review(
                    cloud_info, adjusted_confidence
                )
                raw_detection['needs_human_review'] = should_flag
                raw_detection['review_reason'] = reason
                
                detections.append(raw_detection)
        
        return detections


def get_cloud_detector(use_ml: bool = False) -> CloudDetector:
    """Factory function to get a cloud detector instance."""
    return CloudDetector(use_ml=use_ml)
