"""
Sentinel-2 Image Patch Extractor Module.

Extracts local 64x64 pixel RGB patches (B04, B03, B02) around FIRMS cluster centroids
from Sentinel-2 satellite imagery.
"""

from __future__ import annotations

from typing import Tuple, Optional
from pathlib import Path
from PIL import Image, ImageDraw
import torch

from src.satellite.preprocessing import preprocess_image
from src.logging_setup import get_logger

logger = get_logger("satellite.patch_extractor")

class PatchExtractor:
    def __init__(self, patch_size: int = 64):
        self.patch_size = patch_size

    def create_synthetic_patch(self, landuse_type: str = "Industrial") -> Image.Image:
        """
        Generates a synthetic 64x64 PIL RGB image patch for local pipeline testing & fallback.
        """
        img = Image.new("RGB", (self.patch_size, self.patch_size), color=(128, 128, 128))
        draw = ImageDraw.Draw(img)

        if landuse_type == "Industrial":
            draw.rectangle([10, 10, 54, 54], fill=(100, 100, 110), outline=(200, 200, 200))
            draw.rectangle([20, 20, 30, 40], fill=(220, 80, 40)) # Thermal flare simulation
        elif landuse_type == "Forest":
            draw.rectangle([0, 0, 64, 64], fill=(30, 120, 40))
        elif landuse_type == "AnnualCrop":
            draw.rectangle([0, 0, 64, 64], fill=(180, 160, 60))
        else:
            draw.rectangle([0, 0, 64, 64], fill=(150, 150, 150))

        return img

    def extract_patch_tensor(self, image_path: Optional[Path] = None, landuse_hint: str = "Industrial") -> torch.Tensor:
        """
        Extract preprocessed image tensor of shape (1, 3, patch_size, patch_size).
        """
        if image_path and image_path.exists():
            img = Image.open(image_path).convert("RGB")
        else:
            img = self.create_synthetic_patch(landuse_type=landuse_hint)

        return preprocess_image(img, image_size=self.patch_size)
