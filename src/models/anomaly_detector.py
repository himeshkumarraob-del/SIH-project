"""
Unsupervised Anomaly Detection using Isolation Forest.

Detects statistically abnormal thermal events in FIRMS clusters based on
thermal intensity, spatial spread, and persistence metrics.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("models.anomaly_detector")

# The exact 10 features requested
FEATURES = [
    "max_bright_ti4",
    "bt_diff_max",
    "mean_frp",
    "max_frp",
    "observation_count",
    "active_days",
    "duration_days",
    "detection_density",
    "mean_confidence",
    "frp_mean_to_max_ratio",
]

# We expect ~1-5% of real world detections to be truly anomalous industrial/extreme fires
DEFAULT_CONTAMINATION = 0.05
RANDOM_STATE = 42

class ThermalAnomalyDetector:
    def __init__(self, contamination: float = DEFAULT_CONTAMINATION, random_state: int = RANDOM_STATE):
        self.contamination = contamination
        self.random_state = random_state
        self.scaler = RobustScaler()
        # Isolation Forest isolates anomalies. 
        self.model = IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_jobs=-1
        )
        self.is_fitted = False

    def _validate_features(self, df: pd.DataFrame) -> None:
        missing = [f for f in FEATURES if f not in df.columns]
        if missing:
            raise ValueError(f"Missing required features for anomaly detection: {missing}")

    def _preprocess(self, df: pd.DataFrame, fit: bool = False) -> np.ndarray:
        self._validate_features(df)
        
        # Extract features and handle invalid/missing values safely
        X = df[FEATURES].copy()
        
        # Replace inf with nan, then fill nan with median
        X = X.replace([np.inf, -np.inf], np.nan)
        
        # We fill NaNs with 0 if median fails, but for RobustScaler, we must have valid floats
        # In a real pipeline we might use SimpleImputer, but here median per column is fine
        X = X.fillna(X.median())
        X = X.fillna(0) # Fallback if entirely NaNs
        
        if fit:
            self.scaler.fit(X)
            
        return self.scaler.transform(X)

    def fit(self, df: pd.DataFrame) -> None:
        """Fit the scaler and Isolation Forest model."""
        X_scaled = self._preprocess(df, fit=True)
        self.model.fit(X_scaled)
        self.is_fitted = True

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate anomaly_score, anomaly_flag, and abnormality_level.
        """
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before calling predict.")
            
        X_scaled = self._preprocess(df, fit=False)
        
        # IsolationForest decision_function returns > 0 for normal, < 0 for anomalies.
        # We invert it so higher score = more anomalous.
        raw_scores = self.model.decision_function(X_scaled)
        anomaly_scores = -raw_scores
        
        # predict returns 1 for normal, -1 for anomaly
        predictions = self.model.predict(X_scaled)
        anomaly_flags = (predictions == -1).astype(int)
        
        # Thresholds for abnormality levels based on anomaly_scores
        # score > 0 is anomalous (since we inverted decision_function).
        # We will define:
        # score <= -0.05 -> NORMAL
        # -0.05 < score <= 0.0 -> ELEVATED
        # score > 0.0 -> HIGH
        
        levels = []
        for score in anomaly_scores:
            if score > 0.0:
                levels.append("HIGH")
            elif score > -0.05:
                levels.append("ELEVATED")
            else:
                levels.append("NORMAL")
                
        results = df.copy()
        results["anomaly_score"] = np.round(anomaly_scores, 4)
        results["anomaly_flag"] = anomaly_flags
        results["abnormality_level"] = levels
        
        return results

    def save(self, model_dir: Path) -> None:
        """Save fitted model and scaler to the specified directory."""
        if not self.is_fitted:
            raise RuntimeError("Cannot save an unfitted model.")
            
        model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.scaler, model_dir / "robust_scaler.joblib")
        joblib.dump(self.model, model_dir / "isolation_forest.joblib")
        
    @classmethod
    def load(cls, model_dir: Path) -> "ThermalAnomalyDetector":
        """Load fitted model and scaler from the specified directory."""
        detector = cls()
        detector.scaler = joblib.load(model_dir / "robust_scaler.joblib")
        detector.model = joblib.load(model_dir / "isolation_forest.joblib")
        detector.is_fitted = True
        return detector
