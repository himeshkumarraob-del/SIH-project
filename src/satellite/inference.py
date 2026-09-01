"""
Satellite Land-Use Inference Engine.

Performs forward inference on single image patches (PIL, numpy array, image file path)
using the trained EfficientNet-B0 CNN model.

Output:
- predicted_landcover_class
- prediction_confidence (MODEL CONFIDENCE, NOT probability of fire)
- class_probabilities dictionary

Guardrail Notice:
Model confidence represents visual similarity to satellite land-use classes (e.g. Industrial, Forest).
It does NOT represent "probability of fire" or "probability of industrial fire".
"""

from __future__ import annotations

from typing import Dict, Any, Union, Optional
from pathlib import Path
import torch
import torch.nn.functional as F

from src.satellite.model import build_satellite_model, SatelliteCNNModel
from src.satellite.preprocessing import preprocess_image
from src.satellite.dataset import EUROSAT_CLASSES, IDX_TO_CLASS
from src.logging_setup import get_logger

logger = get_logger("satellite.inference")

class SatelliteLandUsePredictor:
    def __init__(self, checkpoint_path: Optional[Union[str, Path]] = None, device: str = "cpu"):
        self.device = torch.device(device)
        self.model = build_satellite_model(num_classes=len(EUROSAT_CLASSES), pretrained=True)
        self.model.to(self.device)
        self.model.eval()

        self.is_trained = False
        if checkpoint_path:
            cpath = Path(checkpoint_path)
            if cpath.exists():
                try:
                    checkpoint = torch.load(cpath, map_location=self.device)
                    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
                        self.model.load_state_dict(checkpoint["state_dict"])
                    else:
                        self.model.load_state_dict(checkpoint)
                    self.is_trained = True
                    logger.info(f"Loaded trained satellite CNN checkpoint from {cpath}")
                except Exception as exc:
                    logger.warning(f"Failed to load checkpoint from {cpath}: {exc}. Using base model.")

    def predict(self, image_input: Any) -> Dict[str, Any]:
        """
        Run satellite land-use inference on an input image.
        Returns dictionary with predicted_landcover_class, prediction_confidence, and class_probabilities.
        """
        try:
            tensor = preprocess_image(image_input)
            tensor = tensor.to(self.device)

            with torch.no_grad():
                logits = self.model(tensor)
                probs = F.softmax(logits, dim=1).squeeze(0).cpu().numpy()

            top_idx = int(probs.argmax())
            top_class = IDX_TO_CLASS.get(top_idx, "UNKNOWN")
            top_confidence = round(float(probs[top_idx]), 4)

            prob_dict = {
                IDX_TO_CLASS[i]: round(float(probs[i]), 4)
                for i in range(len(EUROSAT_CLASSES))
            }

            return {
                "predicted_landcover_class": top_class,
                "prediction_confidence": top_confidence, # Visual land-use MODEL CONFIDENCE
                "class_probabilities": prob_dict,
                "is_model_trained": self.is_trained
            }

        except Exception as exc:
            logger.error(f"Satellite inference error: {exc}")
            # Clean fallback dictionary if input image is unparseable
            return {
                "predicted_landcover_class": "UNKNOWN",
                "prediction_confidence": 0.0,
                "class_probabilities": {cls_name: 0.0 for cls_name in EUROSAT_CLASSES},
                "is_model_trained": self.is_trained
            }
