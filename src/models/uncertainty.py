"""
Uncertainty Quantification Module.

Provides calibrated uncertainty estimates for fire detection,
classification, and risk scoring predictions.

Helps identify high-uncertainty predictions that need human review
and provides confidence intervals for decision-making.
"""

from __future__ import annotations

from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
import numpy as np

from src.logging_setup import get_logger

logger = get_logger("models.uncertainty")


@dataclass
class PredictionWithUncertainty:
    """Container for prediction with uncertainty estimates."""
    prediction: str
    confidence: float
    uncertainty: float  # 0-1, higher = more uncertain
    confidence_interval: Tuple[float, float]  # (lower, upper)
    uncertainty_sources: List[str]  # What contributes to uncertainty
    needs_human_review: bool
    review_reason: Optional[str] = None


class UncertaintyQuantifier:
    """
    Quantifies uncertainty in fire detection and classification predictions.
    
    Sources of uncertainty:
    - Data quality (cloud cover, missing observations)
    - Model uncertainty (classifier confidence)
    - Feature uncertainty (noisy measurements)
    - Temporal gaps (interpolated vs observed data)
    """
    
    # Uncertainty thresholds
    HIGH_UNCERTAINTY_THRESHOLD = 0.6
    MEDIUM_UNCERTAINTY_THRESHOLD = 0.3
    REVIEW_CONFIDENCE_THRESHOLD = 0.4
    
    def __init__(self):
        self.uncertainty_weights = {
            "data_quality": 0.3,
            "model_confidence": 0.3,
            "feature_noise": 0.2,
            "temporal_gaps": 0.2
        }
    
    def quantify_classification_uncertainty(
        self,
        classification: str,
        classification_score: float,
        feature_values: Dict[str, float],
        cloud_cover: float = 0.0,
        temporal_completeness: float = 1.0,
        num_observations: int = 1
    ) -> PredictionWithUncertainty:
        """
        Quantify uncertainty for a classification prediction.
        
        Args:
            classification: Predicted class
            classification_score: Model confidence (0-1)
            feature_values: Dict of feature values used
            cloud_cover: Cloud cover fraction (0-1)
            temporal_completeness: Fraction of expected observations present (0-1)
            num_observations: Number of observations supporting this prediction
            
        Returns:
            PredictionWithUncertainty with detailed uncertainty info
        """
        uncertainty_sources = []
        
        # 1. Data quality uncertainty
        data_quality_uncertainty = 0.0
        
        if cloud_cover > 0.5:
            data_quality_uncertainty += (cloud_cover - 0.5) * 0.8
            uncertainty_sources.append(f"High cloud cover ({cloud_cover*100:.0f}%)")
        
        if num_observations < 3:
            data_quality_uncertainty += (3 - num_observations) * 0.15
            uncertainty_sources.append(f"Few observations ({num_observations})")
        
        # 2. Model confidence uncertainty
        model_uncertainty = 1.0 - classification_score
        if classification_score < 0.5:
            uncertainty_sources.append(f"Low classifier confidence ({classification_score:.2f})")
        
        # 3. Feature noise uncertainty
        feature_uncertainty = self._estimate_feature_uncertainty(feature_values)
        if feature_uncertainty > 0.3:
            uncertainty_sources.append("Noisy or ambiguous feature values")
        
        # 4. Temporal gap uncertainty
        temporal_uncertainty = 1.0 - temporal_completeness
        if temporal_completeness < 0.7:
            uncertainty_sources.append(f"Temporal gaps ({(1-temporal_completeness)*100:.0f}% missing)")
        
        # Calculate weighted uncertainty
        total_uncertainty = (
            self.uncertainty_weights["data_quality"] * data_quality_uncertainty +
            self.uncertainty_weights["model_confidence"] * model_uncertainty +
            self.uncertainty_weights["feature_noise"] * feature_uncertainty +
            self.uncertainty_weights["temporal_gaps"] * temporal_uncertainty
        )
        
        total_uncertainty = min(1.0, max(0.0, total_uncertainty))
        
        # Calculate confidence interval
        confidence_interval = self._calculate_confidence_interval(
            classification_score, total_uncertainty
        )
        
        # Determine if human review is needed
        needs_review, review_reason = self._determine_review_need(
            classification_score, total_uncertainty, uncertainty_sources
        )
        
        return PredictionWithUncertainty(
            prediction=classification,
            confidence=classification_score,
            uncertainty=total_uncertainty,
            confidence_interval=confidence_interval,
            uncertainty_sources=uncertainty_sources,
            needs_human_review=needs_review,
            review_reason=review_reason
        )
    
    def quantify_risk_uncertainty(
        self,
        risk_score: float,
        risk_level: str,
        anomaly_confidence: float,
        false_alarm_indicator: str,
        observation_count: int,
        cloud_cover: float = 0.0
    ) -> PredictionWithUncertainty:
        """
        Quantify uncertainty for risk score predictions.
        
        Args:
            risk_score: Predicted risk score (0-100)
            risk_level: Risk level (LOW/MEDIUM/HIGH)
            anomaly_confidence: Confidence in anomaly detection
            false_alarm_indicator: False alarm concern level
            observation_count: Number of observations
            cloud_cover: Cloud cover fraction
            
        Returns:
            PredictionWithUncertainty with risk-specific uncertainty info
        """
        uncertainty_sources = []
        
        # Normalize risk score to 0-1 for uncertainty calculation
        normalized_risk = risk_score / 100.0
        
        # Base uncertainty from risk level
        if risk_level == "HIGH":
            base_uncertainty = 0.2  # High risk is usually confident
        elif risk_level == "MEDIUM":
            base_uncertainty = 0.4
        else:
            base_uncertainty = 0.3
        
        # False alarm concern adds uncertainty
        fa_uncertainty = 0.0
        if false_alarm_indicator == "HIGH":
            fa_uncertainty = 0.4
            uncertainty_sources.append("High false alarm concern")
        elif false_alarm_indicator == "MEDIUM":
            fa_uncertainty = 0.2
            uncertainty_sources.append("Medium false alarm concern")
        
        # Data quality factors
        data_uncertainty = 0.0
        if cloud_cover > 0.5:
            data_uncertainty += 0.3
            uncertainty_sources.append(f"Cloud cover ({cloud_cover*100:.0f}%)")
        
        if observation_count < 3:
            data_uncertainty += 0.2
            uncertainty_sources.append(f"Few observations ({observation_count})")
        
        # Anomaly confidence
        anomaly_uncertainty = 1.0 - anomaly_confidence
        if anomaly_confidence < 0.5:
            uncertainty_sources.append("Low anomaly detection confidence")
        
        # Calculate total uncertainty
        total_uncertainty = (
            0.3 * base_uncertainty +
            0.3 * fa_uncertainty +
            0.2 * data_uncertainty +
            0.2 * anomaly_uncertainty
        )
        
        total_uncertainty = min(1.0, max(0.0, total_uncertainty))
        
        # Risk score confidence interval
        margin = total_uncertainty * 20  # Scale to risk score range
        ci_lower = max(0, risk_score - margin)
        ci_upper = min(100, risk_score + margin)
        
        # Determine review need
        needs_review, review_reason = self._determine_risk_review_need(
            risk_level, total_uncertainty, false_alarm_indicator, uncertainty_sources
        )
        
        return PredictionWithUncertainty(
            prediction=risk_level,
            confidence=normalized_risk,
            uncertainty=total_uncertainty,
            confidence_interval=(ci_lower, ci_upper),
            uncertainty_sources=uncertainty_sources,
            needs_human_review=needs_review,
            review_reason=review_reason
        )
    
    def _estimate_feature_uncertainty(self, feature_values: Dict[str, float]) -> float:
        """
        Estimate uncertainty from feature values.
        
        High variance or extreme values indicate higher uncertainty.
        """
        if not feature_values:
            return 0.5
        
        values = list(feature_values.values())
        
        # Check for extreme values
        extreme_count = 0
        for v in values:
            if abs(v) > 3.0:  # Assuming standardized features
                extreme_count += 1
        
        extreme_ratio = extreme_count / len(values) if values else 0
        
        # Check for NaN/missing
        nan_count = sum(1 for v in values if np.isnan(v) or v is None)
        nan_ratio = nan_count / len(values) if values else 0
        
        # Combined feature uncertainty
        uncertainty = 0.3 * extreme_ratio + 0.7 * nan_ratio
        
        return min(1.0, uncertainty)
    
    def _calculate_confidence_interval(
        self, 
        confidence: float, 
        uncertainty: float
    ) -> Tuple[float, float]:
        """
        Calculate confidence interval for a prediction.
        
        Returns (lower_bound, upper_bound) in [0, 1].
        """
        # Width of interval based on uncertainty
        width = uncertainty * 0.4  # Max 40% width
        
        lower = max(0.0, confidence - width)
        upper = min(1.0, confidence + width)
        
        return (round(lower, 3), round(upper, 3))
    
    def _determine_review_need(
        self,
        confidence: float,
        uncertainty: float,
        uncertainty_sources: List[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if human review is needed.
        
        Returns (needs_review, reason).
        """
        if uncertainty > self.HIGH_UNCERTAINTY_THRESHOLD:
            return True, f"High uncertainty ({uncertainty:.2f}): {'; '.join(uncertainty_sources[:2])}"
        
        if confidence < self.REVIEW_CONFIDENCE_THRESHOLD:
            return True, f"Low confidence ({confidence:.2f}) - prediction may be unreliable"
        
        if uncertainty > self.MEDIUM_UNCERTAINTY_THRESHOLD and confidence < 0.6:
            return True, f"Moderate uncertainty with borderline confidence"
        
        return False, None
    
    def _determine_risk_review_need(
        self,
        risk_level: str,
        uncertainty: float,
        false_alarm_indicator: str,
        uncertainty_sources: List[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if risk prediction needs human review.
        """
        # HIGH risk with high uncertainty always needs review
        if risk_level == "HIGH" and uncertainty > 0.4:
            return True, f"HIGH risk with significant uncertainty: {'; '.join(uncertainty_sources[:2])}"
        
        # HIGH risk with high false alarm concern needs review
        if risk_level == "HIGH" and false_alarm_indicator == "HIGH":
            return True, "HIGH risk but HIGH false alarm concern - verify before action"
        
        # MEDIUM risk with high uncertainty needs review
        if risk_level == "MEDIUM" and uncertainty > 0.5:
            return True, f"MEDIUM risk with high uncertainty - consider additional verification"
        
        # General high uncertainty
        if uncertainty > self.HIGH_UNCERTAINTY_THRESHOLD:
            return True, f"High prediction uncertainty ({uncertainty:.2f})"
        
        return False, None
    
    def aggregate_cluster_uncertainty(
        self,
        detections_with_uncertainty: List[PredictionWithUncertainty]
    ) -> Dict[str, Any]:
        """
        Aggregate uncertainty across multiple detections for a cluster.
        
        Provides overall cluster-level uncertainty assessment.
        
        Args:
            detections_with_uncertainty: List of individual detection uncertainties
            
        Returns:
            Aggregated uncertainty report
        """
        if not detections_with_uncertainty:
            return {
                "avg_uncertainty": 0.0,
                "max_uncertainty": 0.0,
                "uncertain_detections": 0,
                "needs_review": False,
                "recommendation": "No detections to analyze"
            }
        
        uncertainties = [d.uncertainty for d in detections_with_uncertainty]
        confidences = [d.confidence for d in detections_with_uncertainty]
        
        avg_uncertainty = np.mean(uncertainties)
        max_uncertainty = np.max(uncertainties)
        uncertain_count = sum(1 for u in uncertainties if u > self.MEDIUM_UNCERTAINTY_THRESHOLD)
        
        # Overall review need
        needs_review = avg_uncertainty > self.MEDIUM_UNCERTAINTY_THRESHOLD
        
        # Generate recommendation
        if avg_uncertainty > self.HIGH_UNCERTAINTY_THRESHOLD:
            recommendation = "High overall uncertainty - recommend comprehensive review"
        elif uncertain_count > len(detections_with_uncertainty) * 0.3:
            recommendation = f"{uncertain_count} of {len(detections_with_uncertainty)} detections have elevated uncertainty"
        elif np.mean(confidences) > 0.7:
            recommendation = "Generally reliable predictions with good confidence"
        else:
            recommendation = "Moderate uncertainty - routine monitoring sufficient"
        
        return {
            "avg_uncertainty": round(float(avg_uncertainty), 3),
            "max_uncertainty": round(float(max_uncertainty), 3),
            "avg_confidence": round(float(np.mean(confidences)), 3),
            "uncertain_detections": uncertain_count,
            "total_detections": len(detections_with_uncertainty),
            "needs_review": needs_review,
            "recommendation": recommendation
        }


class MonteCarloDropoutPredictor:
    """
    Uses Monte Carlo Dropout for Bayesian approximation of model uncertainty.
    
    Runs multiple forward passes with dropout enabled to estimate
    prediction variance.
    
    Note: Requires a PyTorch model with dropout layers.
    """
    
    def __init__(self, model, n_forward_passes: int = 50):
        """
        Args:
            model: PyTorch model with dropout layers
            n_forward_passes: Number of MC dropout forward passes
        """
        self.model = model
        self.n_forward_passes = n_forward_passes
    
    def predict_with_uncertainty(self, input_tensor):
        """
        Run MC Dropout inference to get predictions with uncertainty.
        
        Args:
            input_tensor: Input tensor for the model
            
        Returns:
            Dictionary with mean prediction, variance, and uncertainty
        """
        try:
            import torch
        except ImportError:
            logger.warning("PyTorch not available for MC Dropout")
            return {"prediction": None, "uncertainty": 0.0}
        
        self.model.train()  # Enable dropout
        
        predictions = []
        
        with torch.no_grad():
            for _ in range(self.n_forward_passes):
                output = self.model(input_tensor)
                predictions.append(output.cpu().numpy())
        
        self.model.eval()  # Disable dropout
        
        # Stack predictions
        preds = np.stack(predictions, axis=0)
        
        # Calculate statistics
        mean_pred = np.mean(preds, axis=0)
        variance = np.var(preds, axis=0)
        uncertainty = np.mean(variance)
        
        return {
            "prediction": mean_pred,
            "variance": variance,
            "uncertainty": float(uncertainty),
            "confidence_interval_lower": np.percentile(preds, 5, axis=0),
            "confidence_interval_upper": np.percentile(preds, 95, axis=0)
        }


def get_uncertainty_quantifier() -> UncertaintyQuantifier:
    """Factory function to get uncertainty quantifier instance."""
    return UncertaintyQuantifier()
