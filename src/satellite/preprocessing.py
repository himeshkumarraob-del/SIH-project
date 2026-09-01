"""
Satellite Imagery Preprocessing Module.

Defines image transformations and normalization parameters compatible with ImageNet-pretrained
models (EfficientNet-B0) and EuroSAT Sentinel-2 RGB patches.
"""

from __future__ import annotations

from typing import Union
from pathlib import Path
from PIL import Image
import torch
import torchvision.transforms as T

# Standard ImageNet normalization parameters
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

def get_transforms(is_training: bool = False, image_size: int = 64) -> T.Compose:
    """
    Get PyTorch torchvision transforms for EuroSAT / Sentinel-2 image patches.
    """
    transform_list = [
        T.Resize((image_size, image_size)),
    ]
    
    if is_training:
        transform_list.extend([
            T.RandomHorizontalFlip(),
            T.RandomVerticalFlip(),
        ])
        
    transform_list.extend([
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    ])
    
    return T.Compose(transform_list)

def preprocess_image(image_input: Union[str, Path, Image.Image, torch.Tensor], image_size: int = 64) -> torch.Tensor:
    """
    Preprocess a single image input into a batch tensor of shape (1, 3, image_size, image_size).
    """
    transform = get_transforms(is_training=False, image_size=image_size)

    if isinstance(image_input, (str, Path)):
        path = Path(image_input)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {path}")
        img = Image.open(path).convert("RGB")
    elif isinstance(image_input, Image.Image):
        img = image_input.convert("RGB")
    elif isinstance(image_input, torch.Tensor):
        if image_input.dim() == 3:
            return image_input.unsqueeze(0)
        return image_input
    else:
        raise TypeError(f"Unsupported image input type: {type(image_input)}")

    tensor = transform(img)
    return tensor.unsqueeze(0) # Add batch dimension
