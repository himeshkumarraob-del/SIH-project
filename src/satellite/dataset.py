"""
EuroSAT Satellite Dataset & Split Utility Module.

Handles downloading, loading, and partitioning the 10-class EuroSAT Sentinel-2 RGB benchmark
dataset into deterministic Train (70%), Validation (15%), and Test (15%) splits.
"""

from __future__ import annotations

from typing import Tuple, List, Dict
from pathlib import Path
import torch
from torch.utils.data import Dataset, DataLoader, random_split
from torchvision.datasets import EuroSAT

from src.satellite.preprocessing import get_transforms
from src.logging_setup import get_logger

logger = get_logger("satellite.dataset")

# Official EuroSAT 10 Class Labels
EUROSAT_CLASSES = [
    "AnnualCrop",
    "Forest",
    "HerbaceousVegetation",
    "Highway",
    "Industrial",
    "Pasture",
    "PermanentCrop",
    "Residential",
    "River",
    "SeaLake",
]

CLASS_TO_IDX = {cls_name: i for i, cls_name in enumerate(EUROSAT_CLASSES)}
IDX_TO_CLASS = {i: cls_name for i, cls_name in enumerate(EUROSAT_CLASSES)}

def get_eurosat_dataloaders(
    data_dir: Path,
    batch_size: int = 32,
    seed: int = 42,
    download: bool = True
) -> Tuple[DataLoader, DataLoader, DataLoader, List[str]]:
    """
    Load EuroSAT dataset and return (train_loader, val_loader, test_loader, class_names).
    Splits: 70% Train, 15% Validation, 15% Test with seed for reproducibility.
    """
    train_transform = get_transforms(is_training=True)
    eval_transform = get_transforms(is_training=False)

    full_dataset = EuroSAT(root=str(data_dir), transform=train_transform, download=download)
    classes = full_dataset.classes if hasattr(full_dataset, "classes") else EUROSAT_CLASSES

    total_len = len(full_dataset)
    train_len = int(0.70 * total_len)
    val_len = int(0.15 * total_len)
    test_len = total_len - train_len - val_len

    generator = torch.Generator().manual_seed(seed)
    train_set, val_set, test_set = random_split(
        full_dataset, [train_len, val_len, test_len], generator=generator
    )

    # Set eval transforms for validation & test sets
    val_set.dataset.transform = eval_transform
    test_set.dataset.transform = eval_transform

    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_set, batch_size=batch_size, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_set, batch_size=batch_size, shuffle=False, num_workers=0)

    logger.info(f"Loaded EuroSAT dataset ({total_len} samples). Splits -> Train: {train_len}, Val: {val_len}, Test: {test_len}")

    return train_loader, val_loader, test_loader, classes
