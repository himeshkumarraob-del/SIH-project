"""
Enhanced Explainability Module.

Provides model-agnostic interpretability for fire detection and
classification predictions using SHAP and LIME.

Generates human-understandable explanations showing which features
drove each prediction.
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
import numpy as np

from src.logging_setup import get_logger

logger = get_logger("models.explainer")


@dataclass
class ExplanationResult:
    """Container for explanation results."""
    prediction: str
    base_value: float  # Model's average prediction
    feature_contributions: Dict[str, float]  # Feature name -> contribution
    top_positive_features: List[Tuple[str, float]]  # Top features pushing prediction up
    top_negative_features: List[Tuple[str, float]]  # Top features pushing prediction down
    human_readable_explanation: str
    counterfactual: Optional[str] = None  # What would change the prediction


class SHAPExplainer:
    """
    SHAP-based explanation generator for fire classification models.
    
    Uses SHAP (SHapley Additive exPlanations) to explain model predictions
    by computing the contribution of each feature.
    
    Works with tree-based models (Random Forest, XGBoost, etc.) efficiently.
    """
    
    def __init__(self, model=None, background_data=None):
        """
        Args:
            model: Trained model to explain
            background_data: Background dataset for SHAP computation
        """
        self.model = model
        self.background_data = background_data
        self._shap_explainer = None
        
        if model is not None:
            self._initialize_shap()
    
    def _initialize_shap(self):
        """Initialize SHAP explainer based on model type."""
        try:
            import shap
            
            # Choose explainer based on model type
            model_type = type(self.model).__name__
            
            if hasattr(self.model, 'predict_proba'):
                # Tree-based model (Random Forest, XGBoost, etc.)
                self._shap_explainer = shap.TreeExplainer(self.model)
                logger.info(f"Initialized SHAP TreeExplainer for {model_type}")
            elif self.background_data is not None:
                # Kernel explainer for any model
                self._shap_explainer = shap.KernelExplainer(
                    self.model.predict_proba, 
                    self.background_data
                )
                logger.info(f"Initialized SHAP KernelExplainer for {model_type}")
            else:
                logger.warning("Cannot initialize SHAP: no background data for KernelExplainer")
                
        except ImportError:
            logger.warning("SHAP library not installed. Using fallback explanations.")
        except Exception as e:
            logger.warning(f"Failed to initialize SHAP: {e}")
    
    def explain_prediction(
        self, 
        instance: np.ndarray, 
        feature_names: List[str]
    ) -> ExplanationResult:
        """
        Generate SHAP explanation for a single prediction.
        
        Args:
            instance: Feature values for the instance (1D array)
            feature_names: Names of features
            
        Returns:
            ExplanationResult with detailed explanation
        """
        if self._shap_explainer is None:
            return self._fallback_explanation(instance, feature_names)
        
        try:
            import shap
            
            # Compute SHAP values
            shap_values = self._shap_explainer.shap_values(instance.reshape(1, -1))
            
            # Handle multi-class output
            if isinstance(shap_values, list):
                # For multi-class, take the predicted class
                prediction_idx = self.model.predict(instance.reshape(1, -1))[0]
                shap_vals = shap_values[prediction_idx][0]
            else:
                shap_vals = shap_values[0]
            
            # Calculate base value
            base_value = self._shap_explainer.expected_value
            if isinstance(base_value, (list, np.ndarray)):
                base_value = base_value[0] if len(base_value) > 0 else 0
            
            # Create feature contribution dictionary
            feature_contributions = {
                name: float(val) for name, val in zip(feature_names, shap_vals)
            }
            
            # Sort by absolute contribution
            sorted_features = sorted(
                feature_contributions.items(), 
                key=lambda x: abs(x[1]), 
                reverse=True
            )
            
            # Separate positive and negative contributions
            top_positive = [(k, v) for k, v in sorted_features if v > 0][:5]
            top_negative = [(k, v) for k, v in sorted_features if v < 0][:5]
            
            # Generate human-readable explanation
            human_readable = self._generate_human_readable(
                feature_contributions, top_positive, top_negative
            )
            
            return ExplanationResult(
                prediction=str(self.model.predict(instance.reshape(1, -1))[0]),
                base_value=float(base_value),
                feature_contributions=feature_contributions,
                top_positive_features=top_positive,
                top_negative_features=top_negative,
                human_readable_explanation=human_readable
            )
            
        except Exception as e:
            logger.warning(f"SHAP explanation failed: {e}. Using fallback.")
            return self._fallback_explanation(instance, feature_names)
    
    def _fallback_explanation(
        self, 
        instance: np.ndarray, 
        feature_names: List[str]
    ) -> ExplanationResult:
        """
        Generate simple explanation without SHAP.
        
        Uses feature importance based on value magnitude.
        """
        # Simple magnitude-based explanation
        contributions = {}
        for i, name in enumerate(feature_names):
            if i < len(instance):
                contributions[name] = float(instance[i])
        
        # Sort by absolute value
        sorted_features = sorted(
            contributions.items(), 
            key=lambda x: abs(x[1]), 
            reverse=True
        )
        
        top_positive = [(k, v) for k, v in sorted_features if v > 0][:5]
        top_negative = [(k, v) for k, v in sorted_features if v < 0][:5]
        
        human_readable = self._generate_human_readable(
            contributions, top_positive, top_negative
        )
        
        return ExplanationResult(
            prediction="Unknown",
            base_value=0.0,
            feature_contributions=contributions,
            top_positive_features=top_positive,
            top_negative_features=top_negative,
            human_readable_explanation=human_readable
        )
    
    def _generate_human_readable(
        self,
        contributions: Dict[str, float],
        top_positive: List[Tuple[str, float]],
        top_negative: List[Tuple[str, float]]
    ) -> str:
        """
        Generate human-readable explanation from feature contributions.
        """
        explanation_parts = []
        
        # Top contributing features
        if top_positive:
            pos_features = [f"{name} ({val:.3f})" for name, val in top_positive[:3]]
            explanation_parts.append(
                f"Top positive factors: {', '.join(pos_features)}"
            )
        
        if top_negative:
            neg_features = [f"{name} ({val:.3f})" for name, val in top_negative[:3]]
            explanation_parts.append(
                f"Top negative factors: {', '.join(neg_features)}"
            )
        
        # Overall summary
        total_positive = sum(v for v in contributions.values() if v > 0)
        total_negative = sum(v for v in contributions.values() if v < 0)
        
        if total_positive > abs(total_negative):
            explanation_parts.append("Overall positive signal dominates")
        else:
            explanation_parts.append("Overall negative signal dominates")
        
        return "; ".join(explanation_parts)


class LIMEExplainer:
    """
    LIME-based explanation generator for local interpretable explanations.
    
    LIME creates simple surrogate models that explain individual predictions.
    """
    
    def __init__(self, model=None, training_data=None, feature_names=None):
        """
        Args:
            model: Trained model to explain
            training_data: Training data for LIME (to understand feature distributions)
            feature_names: Names of features
        """
        self.model = model
        self.training_data = training_data
        self.feature_names = feature_names or []
        self._lime_explainer = None
    
    def explain_prediction(
        self, 
        instance: np.ndarray,
        num_features: int = 10
    ) -> ExplanationResult:
        """
        Generate LIME explanation for a single prediction.
        
        Args:
            instance: Feature values for the instance
            num_features: Number of features to include in explanation
            
        Returns:
            ExplanationResult with LIME explanation
        """
        if self._lime_explainer is None:
            self._initialize_lime()
        
        if self._lime_explainer is None:
            return self._simple_explanation(instance)
        
        try:
            explanation = self._lime_explainer.explain_instance(
                instance,
                self.model.predict_proba,
                num_features=num_features
            )
            
            # Extract feature contributions
            feature_contributions = {}
            for idx, weight in explanation.as_list():
                if isinstance(idx, int) and idx < len(self.feature_names):
                    feature_contributions[self.feature_names[idx]] = weight
            
            # Sort features
            sorted_features = sorted(
                feature_contributions.items(),
                key=lambda x: abs(x[1]),
                reverse=True
            )
            
            top_positive = [(k, v) for k, v in sorted_features if v > 0][:5]
            top_negative = [(k, v) for k, v in sorted_features if v < 0][:5]
            
            return ExplanationResult(
                prediction=str(explanation.predict_proba),
                base_value=float(explanation.intercept[1]) if len(explanation.intercept) > 1 else 0.0,
                feature_contributions=feature_contributions,
                top_positive_features=top_positive,
                top_negative_features=top_negative,
                human_readable_explanation=str(explanation)
            )
            
        except Exception as e:
            logger.warning(f"LIME explanation failed: {e}")
            return self._simple_explanation(instance)
    
    def _initialize_lime(self):
        """Initialize LIME explainer."""
        try:
            from lime.lime_tabular import LimeTabularExplainer
            
            if self.training_data is not None:
                self._lime_explainer = LimeTabularExplainer(
                    self.training_data,
                    feature_names=self.feature_names,
                    mode='classification'
                )
                logger.info("Initialized LIME TabularExplainer")
            else:
                logger.warning("No training data available for LIME")
                
        except ImportError:
            logger.warning("LIME library not installed")
    
    def _simple_explanation(self, instance: np.ndarray) -> ExplanationResult:
        """Fallback simple explanation."""
        contributions = {}
        for i, name in enumerate(self.feature_names):
            if i < len(instance):
                contributions[name] = float(instance[i])
        
        sorted_features = sorted(
            contributions.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )
        
        return ExplanationResult(
            prediction="Unknown",
            base_value=0.0,
            feature_contributions=contributions,
            top_positive_features=[(k, v) for k, v in sorted_features if v > 0][:5],
            top_negative_features=[(k, v) for k, v in sorted_features if v < 0][:5],
            human_readable_explanation="Simple feature-based explanation (LIME not available)"
        )


class FirePredictionExplainer:
    """
    High-level explainer combining SHAP, LIME, and rule-based explanations
    for fire predictions.
    
    Provides comprehensive explanations suitable for operational decision-making.
    """
    
    def __init__(self, classification_model=None, risk_model=None):
        """
        Args:
            classification_model: Trained classification model
            risk_model: Trained risk scoring model
        """
        self.classification_model = classification_model
        self.risk_model = risk_model
        
        self.shap_explainer = None
        self.lime_explainer = None
        
        if classification_model is not None:
            self.shap_explainer = SHAPExplainer(classification_model)
            self.lime_explainer = LIMEExplainer(classification_model)
    
    def explain_classification(
        self,
        instance: np.ndarray,
        feature_names: List[str],
        raw_features: Dict[str, float],
        classification_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate comprehensive explanation for a classification prediction.
        
        Args:
            instance: Preprocessed feature vector
            feature_names: Names of features
            raw_features: Original feature values (before preprocessing)
            classification_result: Classification output from the model
            
        Returns:
            Comprehensive explanation dictionary
        """
        explanation = {
            "prediction": classification_result.get("classification_label", "Unknown"),
            "confidence": classification_result.get("classification_score", 0.0),
            "method": "combined",
            "model_explanation": None,
            "rule_based_explanation": None,
            "counterfactual": None,
            "feature_importance": {}
        }
        
        # Model-based explanation (SHAP/LIME)
        if self.shap_explainer is not None:
            try:
                model_exp = self.shap_explainer.explain_prediction(instance, feature_names)
                explanation["model_explanation"] = {
                    "method": "SHAP",
                    "top_features": model_exp.top_positive_features + model_exp.top_negative_features,
                    "summary": model_exp.human_readable_explanation
                }
                explanation["feature_importance"] = model_exp.feature_contributions
            except Exception as e:
                logger.warning(f"SHAP explanation failed: {e}")
        
        # Rule-based explanation
        rule_exp = self._generate_rule_based_explanation(raw_features, classification_result)
        explanation["rule_based_explanation"] = rule_exp
        
        # Counterfactual explanation
        counterfactual = self._generate_counterfactual(raw_features, classification_result)
        explanation["counterfactual"] = counterfactual
        
        # Combined summary
        explanation["summary"] = self._combine_explanations(
            explanation.get("model_explanation"),
            rule_exp,
            classification_result
        )
        
        return explanation
    
    def _generate_rule_based_explanation(
        self,
        features: Dict[str, float],
        result: Dict[str, Any]
    ) -> str:
        """
        Generate rule-based explanation using domain knowledge.
        """
        parts = []
        
        classification = result.get("classification_label", "Unknown")
        score = result.get("classification_score", 0.0)
        
        # High-level summary
        parts.append(f"Classification: {classification} (confidence: {score:.2f})")
        
        # Feature-based reasoning
        max_frp = features.get("max_frp", 0)
        bt_diff = features.get("bt_diff_max", 0)
        active_days = features.get("active_days", 1)
        movement = features.get("movement_status", "UNKNOWN")
        
        if "Industrial" in classification:
            if features.get("persistence_category") == "persistent":
                parts.append("Persistent thermal activity suggests industrial source")
            if movement == "STATIONARY":
                parts.append("Stationary signal consistent with fixed industrial facility")
            if bt_diff > 35:
                parts.append("High spectral contrast indicates intense heat source")
        
        elif "Agricultural" in classification:
            if active_days <= 2:
                parts.append("Short duration typical of crop burning")
            if max_frp > 5:
                parts.append("Moderate FRP consistent with agricultural fires")
        
        elif "Forest" in classification:
            if movement == "MOVING":
                parts.append("Moving signal suggests spreading wildfire")
            if max_frp > 20:
                parts.append("High FRP indicates intense fire activity")
        
        return "; ".join(parts)
    
    def _generate_counterfactual(
        self,
        features: Dict[str, float],
        result: Dict[str, Any]
    ) -> Optional[str]:
        """
        Generate counterfactual explanation: what would change the prediction?
        """
        classification = result.get("classification_label", "Unknown")
        
        # Simple counterfactual rules
        if "Industrial" in classification:
            return "If the signal were moving and less persistent, it would be classified as Agricultural/Forest"
        elif "Agricultural" in classification:
            return "If the signal were persistent and stationary with high spectral contrast, it would be classified as Industrial"
        elif "Forest" in classification:
            return "If the signal were stationary and near an industrial facility, it would be classified as Industrial"
        else:
            return "Insufficient evidence - need more observations or clearer thermal signatures"
    
    def _combine_explanations(
        self,
        model_explanation: Optional[Dict],
        rule_explanation: str,
        result: Dict[str, Any]
    ) -> str:
        """
        Combine model and rule-based explanations into a summary.
        """
        parts = []
        
        # Add model explanation if available
        if model_explanation and model_explanation.get("summary"):
            parts.append(f"Model analysis: {model_explanation['summary']}")
        
        # Add rule-based explanation
        parts.append(f"Domain reasoning: {rule_explanation}")
        
        # Add confidence assessment
        confidence = result.get("classification_score", 0.0)
        if confidence > 0.7:
            parts.append("High confidence prediction")
        elif confidence > 0.4:
            parts.append("Moderate confidence - consider additional verification")
        else:
            parts.append("Low confidence - recommend human review")
        
        return " | ".join(parts)
    
    def generate_operational_brief(
        self,
        cluster_data: Dict[str, Any],
        classification: Dict[str, Any],
        risk: Dict[str, Any]
    ) -> str:
        """
        Generate a concise operational brief for decision-makers.
        
        Args:
            cluster_data: Cluster features
            classification: Classification result
            risk: Risk assessment
            
        Returns:
            Human-readable operational brief
        """
        brief_parts = []
        
        # Header
        cluster_id = cluster_data.get("cluster_id", "Unknown")
        brief_parts.append(f"=== CLUSTER {cluster_id} ASSESSMENT ===")
        
        # Classification
        class_label = classification.get("classification_label", "Unknown")
        class_score = classification.get("classification_score", 0.0)
        brief_parts.append(f"\nClassification: {class_label}")
        brief_parts.append(f"Confidence: {class_score:.0%}")
        
        # Risk
        risk_level = risk.get("risk_level", "Unknown")
        risk_score = risk.get("risk_score", 0)
        brief_parts.append(f"\nRisk Level: {risk_level} (Score: {risk_score}/100)")
        
        # Key evidence
        brief_parts.append("\nKey Evidence:")
        
        if class_label == "Industrial-context thermal event":
            brief_parts.append("• Persistent, stationary thermal signature")
            brief_parts.append("• High spectral contrast (I4-I5)")
            if cluster_data.get("osm_facility_type") != "UNKNOWN":
                brief_parts.append(f"• Near industrial facility: {cluster_data.get('osm_facility_type')}")
        
        elif class_label == "Agricultural-context thermal event":
            brief_parts.append("• Short-duration thermal activity")
            brief_parts.append("• Moderate fire radiative power")
            brief_parts.append("• Likely crop residue burning")
        
        elif class_label == "Forest/Natural-context thermal event":
            brief_parts.append("• Spatially moving thermal signature")
            brief_parts.append("• High fire radiative power")
            brief_parts.append("• Possible wildfire spread")
        
        # Recommendation
        brief_parts.append("\nRecommendation:")
        
        if risk_level == "HIGH" and classification.get("classification_score", 0) > 0.6:
            brief_parts.append("• Priority monitoring recommended")
            brief_parts.append("• Consider ground verification")
        elif risk_level == "MEDIUM":
            brief_parts.append("• Continue monitoring for escalation")
        else:
            brief_parts.append("• Routine monitoring sufficient")
        
        return "\n".join(brief_parts)


def get_fire_explainer(
    classification_model=None,
    risk_model=None
) -> FirePredictionExplainer:
    """Factory function to get fire prediction explainer."""
    return FirePredictionExplainer(classification_model, risk_model)
