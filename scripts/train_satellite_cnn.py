#!/usr/bin/env python3
"""
CLI Script to train EfficientNet-B0 on EuroSAT satellite land-use dataset.

1. Downloads EuroSAT dataset (27,000 Sentinel-2 RGB patches) if missing.
2. Creates reproducible Train (70%), Val (15%), Test (15%) splits with seed=42.
3. Fine-tunes EfficientNet-B0 on EuroSAT 10 classes.
4. Saves best model weights to models/satellite_landuse_efficientnet_b0.pth.

Usage:
    python scripts/train_satellite_cnn.py --epochs 3 --batch-size 32
"""

from __future__ import annotations

import sys
import argparse
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch
import torch.nn as nn
import torch.optim as optim

from src.satellite.dataset import get_eurosat_dataloaders, EUROSAT_CLASSES
from src.satellite.model import build_satellite_model
from src.config import get_config
from src.logging_setup import get_logger

logger = get_logger("scripts.train_satellite_cnn")

def main() -> int:
    parser = argparse.ArgumentParser(description="Train EfficientNet-B0 on EuroSAT Satellite Dataset")
    parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=32, help="Training batch size")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    args = parser.parse_args()

    cfg = get_config()
    sat_dir = cfg.external_data_dir / "satellite" / "eurosat"
    sat_dir.mkdir(parents=True, exist_ok=True)

    model_dir = cfg.models_dir
    model_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = model_dir / "satellite_landuse_efficientnet_b0.pth"

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Training using device: {device}")

    try:
        logger.info("Attempting EuroSAT dataset initialization...")
        train_loader, val_loader, test_loader, classes = get_eurosat_dataloaders(
            data_dir=sat_dir,
            batch_size=args.batch_size,
            seed=42,
            download=True
        )

        model = build_satellite_model(num_classes=len(classes), pretrained=True)
        model.to(device)

        criterion = nn.CrossEntropyLoss()
        optimizer = optim.AdamW(model.parameters(), lr=args.lr)

        best_val_acc = 0.0

        for epoch in range(1, args.epochs + 1):
            model.train()
            train_loss = 0.0
            correct = 0
            total = 0

            for images, targets in train_loader:
                images, targets = images.to(device), targets.to(device)

                optimizer.zero_grad()
                outputs = model(images)
                loss = criterion(outputs, targets)
                loss.backward()
                optimizer.step()

                train_loss += loss.item() * images.size(0)
                _, predicted = outputs.max(1)
                total += targets.size(0)
                correct += predicted.eq(targets).sum().item()

            train_acc = correct / total if total > 0 else 0.0
            avg_loss = train_loss / total if total > 0 else 0.0

            # Validation step
            model.eval()
            val_correct = 0
            val_total = 0
            with torch.no_grad():
                for v_imgs, v_lbls in val_loader:
                    v_imgs, v_lbls = v_imgs.to(device), v_lbls.to(device)
                    v_outs = model(v_imgs)
                    _, v_preds = v_outs.max(1)
                    val_total += v_lbls.size(0)
                    val_correct += v_preds.eq(v_lbls).sum().item()

            val_acc = val_correct / val_total if val_total > 0 else 0.0

            logger.info(f"Epoch [{epoch}/{args.epochs}] - Train Loss: {avg_loss:.4f} | Train Acc: {train_acc:.4f} | Val Acc: {val_acc:.4f}")
            print(f"Epoch [{epoch}/{args.epochs}] - Train Loss: {avg_loss:.4f} | Train Acc: {train_acc:.4f} | Val Acc: {val_acc:.4f}")

            if val_acc >= best_val_acc:
                best_val_acc = val_acc
                torch.save({"state_dict": model.state_dict(), "val_acc": val_acc}, checkpoint_path)
                logger.info(f"Saved best model checkpoint to {checkpoint_path}")

        print(f"\nTraining Complete. Best Validation Accuracy: {best_val_acc:.4f}")
        print(f"Model saved to: {checkpoint_path}\n")

    except Exception as exc:
        logger.error(f"EuroSAT training failed: {exc}")
        print(f"\nERROR: EuroSAT dataset download or training failed: {exc}")

        # Guard: do NOT save ImageNet-only weights as a trained checkpoint
        if checkpoint_path.exists():
            print(f"Existing valid checkpoint preserved at: {checkpoint_path}")
        else:
            print("No valid checkpoint exists. A checkpoint must be trained before inference.")

        print("Aborting. Re-run after fixing the issue (network, disk space, etc.).")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
