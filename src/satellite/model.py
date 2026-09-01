"""
EfficientNet-B0 Satellite Land-Use CNN Model Architecture Module.

Uses ImageNet-pretrained torchvision.models.efficientnet_b0 with a customized 10-class linear head
for EuroSAT land-use classification.
"""

from __future__ import annotations

import torch
import torch.nn as nn
from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights

from src.satellite.dataset import EUROSAT_CLASSES

class SatelliteCNNModel(nn.Module):
    def __init__(self, num_classes: int = len(EUROSAT_CLASSES), pretrained: bool = True):
        super().__init__()
        weights = EfficientNet_B0_Weights.DEFAULT if pretrained else None
        self.backbone = efficientnet_b0(weights=weights)

        # Replace 1000-class ImageNet classifier with 10-class EuroSAT classifier
        in_features = self.backbone.classifier[1].in_features
        self.backbone.classifier = nn.Sequential(
            nn.Dropout(p=0.2, inplace=True),
            nn.Linear(in_features, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(x)

def build_satellite_model(num_classes: int = len(EUROSAT_CLASSES), pretrained: bool = True) -> SatelliteCNNModel:
    """Build and return an EfficientNet-B0 satellite land-use model instance."""
    model = SatelliteCNNModel(num_classes=num_classes, pretrained=pretrained)
    return model
