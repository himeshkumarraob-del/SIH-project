#!/usr/bin/env python3
"""
Comprehensive Model Training Script.

Trains all models in the Thermal Intelligence Engine:
1. Satellite CNN (EfficientNet-B0) on EuroSAT dataset
2. Anomaly Detector (Isolation Forest) on synthetic FIRMS data
3. Creates necessary model artifacts for inference

Usage:
    python scripts/train_all_models.py
    python scripts/train_all_models.py --skip-satellite  # Skip satellite CNN training
    python scripts/train_all_models.py --epochs 10       # Custom epochs for satellite CNN
"""

from __future__ import annotations

import sys
import argparse
import time
import numpy as np
import pandas as pd
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def create_models_directory():
    """Create models directory if it doesn't exist."""
    from src.config import get_config
    cfg = get_config()
    cfg.models_dir.mkdir(parents=True, exist_ok=True)
    print(f"✓ Models directory: {cfg.models_dir}")


def generate_synthetic_firms_data(n_clusters: int = 200, n_detections_per_cluster: int = 10):
    """
    Generate synthetic FIRMS-like data for training the anomaly detector.
    
    Creates realistic thermal detection data with:
    - Normal background thermal activity
    - Anomalous industrial fires
    - Agricultural burning events
    - Forest fire events
    """
    print("\n--- Generating Synthetic FIRMS Data ---")
    
    np.random.seed(42)
    
    # India bounding box
    lat_min, lat_max = 8.0, 35.0
    lon_min, lon_max = 68.0, 98.0
    
    all_detections = []
    cluster_types = []
    
    for cluster_id in range(n_clusters):
        # Random cluster center in India
        center_lat = np.random.uniform(lat_min, lat_max)
        center_lon = np.random.uniform(lon_min, lon_max)
        
        # Determine cluster type (for generating realistic patterns)
        cluster_type = np.random.choice(
            ['normal', 'industrial', 'agricultural', 'forest'],
            p=[0.6, 0.15, 0.15, 0.10]  # 60% normal, 15% each anomaly type
        )
        cluster_types.append(cluster_type)
        
        # Generate detections for this cluster
        n_detections = np.random.randint(1, n_detections_per_cluster + 1)
        
        for det_idx in range(n_detections):
            # Spatial spread (clustered around center)
            lat = center_lat + np.random.normal(0, 0.05)
            lon = center_lon + np.random.normal(0, 0.05)
            
            # Date (spread across 30 days)
            day = np.random.randint(1, 31)
            month = np.random.choice([8, 9])  # Aug-Sep 2026
            acq_date = f"2026-{month:02d}-{day:02d}"
            
            # Thermal characteristics based on cluster type
            if cluster_type == 'normal':
                bright_ti4 = np.random.normal(290, 10)  # Normal background
                bright_ti5 = np.random.normal(280, 8)
                frp = np.random.exponential(1.0)  # Low FRP
                confidence = np.random.choice(['l', 'n', 'h'], p=[0.2, 0.5, 0.3])
                
            elif cluster_type == 'industrial':
                bright_ti4 = np.random.normal(340, 15)  # High brightness
                bright_ti5 = np.random.normal(295, 10)
                frp = np.random.exponential(8.0)  # High FRP
                confidence = np.random.choice(['n', 'h'], p=[0.3, 0.7])
                
            elif cluster_type == 'agricultural':
                bright_ti4 = np.random.normal(320, 12)
                bright_ti5 = np.random.normal(285, 8)
                frp = np.random.exponential(5.0)  # Medium FRP
                confidence = np.random.choice(['l', 'n', 'h'], p=[0.3, 0.4, 0.3])
                
            elif cluster_type == 'forest':
                bright_ti4 = np.random.normal(330, 18)  # Variable
                bright_ti5 = np.random.normal(290, 12)
                frp = np.random.exponential(10.0)  # High FRP
                confidence = np.random.choice(['n', 'h'], p=[0.4, 0.6])
            
            # Ensure positive values
            bright_ti4 = max(250, bright_ti4)
            bright_ti5 = max(240, bright_ti5)
            frp = max(0.1, frp)
            
            detection = {
                'latitude': lat,
                'longitude': lon,
                'acq_date': acq_date,
                'bright_ti4': round(bright_ti4, 3),
                'bright_ti5': round(bright_ti5, 3),
                'frp': round(frp, 3),
                'confidence': confidence,
                'satellite': np.random.choice(['N20', 'N21']),
                'scan': round(np.random.uniform(0.375, 0.75), 3),
                'track': round(np.random.uniform(0.375, 0.75), 3),
                'bright_ti5': round(bright_ti5, 3),
                'acq_time': f"{np.random.randint(0, 24):02d}{np.random.randint(0, 60):02d}",
                'instrument': 'VIIRS',
                'cluster_id': cluster_id,
                'cluster_type': cluster_type  # For evaluation only
            }
            
            all_detections.append(detection)
    
    df = pd.DataFrame(all_detections)
    
    print(f"Generated {len(df)} synthetic detections across {n_clusters} clusters")
    print(f"Cluster type distribution:")
    for ctype, count in pd.Series(cluster_types).value_counts().items():
        print(f"  {ctype}: {count}")
    
    return df


def train_satellite_cnn(epochs: int = 5, batch_size: int = 32):
    """Train Satellite CNN on EuroSAT dataset."""
    print("\n" + "="*60)
    print("  TRAINING: Satellite CNN (EfficientNet-B0)")
    print("="*60)
    
    from src.satellite.dataset import get_eurosat_dataloaders, EUROSAT_CLASSES
    from src.satellite.model import build_satellite_model
    from src.config import get_config
    
    import torch
    import torch.nn as nn
    import torch.optim as optim
    
    cfg = get_config()
    sat_dir = cfg.external_data_dir / "satellite" / "eurosat"
    sat_dir.mkdir(parents=True, exist_ok=True)
    
    checkpoint_path = cfg.models_dir / "satellite_landuse_efficientnet_b0.pth"
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    
    try:
        print("\nLoading EuroSAT dataset...")
        train_loader, val_loader, test_loader, classes = get_eurosat_dataloaders(
            data_dir=sat_dir,
            batch_size=batch_size,
            seed=42,
            download=True
        )
        
        print(f"Dataset loaded: {len(train_loader.dataset)} train, "
              f"{len(val_loader.dataset)} val, {len(test_loader.dataset)} test")
        
        # Build model
        model = build_satellite_model(num_classes=len(classes), pretrained=True)
        model.to(device)
        
        # Loss and optimizer
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.AdamW(model.parameters(), lr=1e-3)
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
        
        best_val_acc = 0.0
        
        print(f"\nStarting training for {epochs} epochs...")
        for epoch in range(1, epochs + 1):
            # Training phase
            model.train()
            train_loss = 0.0
            correct = 0
            total = 0
            
            for batch_idx, (images, targets) in enumerate(train_loader):
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
                
                if (batch_idx + 1) % 50 == 0:
                    print(f"  Batch [{batch_idx+1}/{len(train_loader)}] - Loss: {loss.item():.4f}")
            
            train_acc = correct / total if total > 0 else 0.0
            avg_loss = train_loss / total if total > 0 else 0.0
            
            # Validation phase
            model.eval()
            val_correct = 0
            val_total = 0
            val_loss = 0.0
            
            with torch.no_grad():
                for v_imgs, v_lbls in val_loader:
                    v_imgs, v_lbls = v_imgs.to(device), v_lbls.to(device)
                    v_outs = model(v_imgs)
                    v_loss = criterion(v_outs, v_lbls)
                    
                    val_loss += v_loss.item() * v_imgs.size(0)
                    _, v_preds = v_outs.max(1)
                    val_total += v_lbls.size(0)
                    val_correct += v_preds.eq(v_lbls).sum().item()
            
            val_acc = val_correct / val_total if val_total > 0 else 0.0
            val_avg_loss = val_loss / val_total if val_total > 0 else 0.0
            
            scheduler.step()
            
            print(f"\nEpoch [{epoch}/{epochs}]")
            print(f"  Train Loss: {avg_loss:.4f} | Train Acc: {train_acc:.4f}")
            print(f"  Val Loss:   {val_avg_loss:.4f} | Val Acc:   {val_acc:.4f}")
            
            # Save best model
            if val_acc >= best_val_acc:
                best_val_acc = val_acc
                torch.save({
                    "state_dict": model.state_dict(),
                    "val_acc": val_acc,
                    "epoch": epoch,
                    "classes": classes
                }, checkpoint_path)
                print(f"  ✓ Saved best model (val_acc: {val_acc:.4f})")
        
        print(f"\n✓ Training complete! Best validation accuracy: {best_val_acc:.4f}")
        print(f"✓ Model saved to: {checkpoint_path}")
        
        # Test evaluation
        print("\nEvaluating on test set...")
        model.eval()
        test_correct = 0
        test_total = 0
        
        with torch.no_grad():
            for t_imgs, t_lbls in test_loader:
                t_imgs = t_imgs.to(device)
                t_outs = model(t_imgs)
                _, t_preds = t_outs.max(1)
                test_total += t_lbls.size(0)
                test_correct += t_preds.cpu().eq(t_lbls).sum().item()
        
        test_acc = test_correct / test_total if test_total > 0 else 0.0
        print(f"Test Accuracy: {test_acc:.4f}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during satellite CNN training: {e}")

        # Guard: do NOT save ImageNet-only weights as a trained checkpoint
        if checkpoint_path.exists():
            print(f"Existing valid checkpoint preserved at: {checkpoint_path}")
        else:
            print("No valid checkpoint exists. Satellite CNN must be trained before inference.")

        print("Aborting satellite CNN training. Fix the issue and re-run.")
        return False


def train_anomaly_detector():
    """Train Anomaly Detector on synthetic FIRMS data."""
    print("\n" + "="*60)
    print("  TRAINING: Anomaly Detector (Isolation Forest)")
    print("="*60)
    
    from src.models.anomaly_detector import ThermalAnomalyDetector, FEATURES
    from src.features.feature_engineering import extract_features
    from src.config import get_config
    
    cfg = get_config()
    
    # Generate synthetic data
    raw_df = generate_synthetic_firms_data(n_clusters=200, n_detections_per_cluster=10)
    
    # Save raw data for reference
    raw_path = cfg.processed_data_dir / "synthetic_firms_india.csv"
    raw_df.to_csv(raw_path, index=False)
    print(f"✓ Saved synthetic data to: {raw_path}")
    
    # Create cluster-level features (simulating persistence analysis output)
    print("\nCreating cluster-level features...")
    
    clusters = []
    for cluster_id in raw_df['cluster_id'].unique():
        cluster_data = raw_df[raw_df['cluster_id'] == cluster_id]
        
        # Aggregate cluster features
        cluster_info = {
            'cluster_id': cluster_id,
            'observation_count': len(cluster_data),
            'active_days': cluster_data['acq_date'].nunique(),
            'first_detection': cluster_data['acq_date'].min(),
            'last_detection': cluster_data['acq_date'].max(),
            'duration_days': (pd.to_datetime(cluster_data['acq_date'].max()) - 
                            pd.to_datetime(cluster_data['acq_date'].min())).days + 1,
            'mean_bright_ti4': cluster_data['bright_ti4'].mean(),
            'max_bright_ti4': cluster_data['bright_ti4'].max(),
            'mean_bright_ti5': cluster_data['bright_ti5'].mean(),
            'max_bright_ti5': cluster_data['bright_ti5'].max(),
            'mean_frp': cluster_data['frp'].mean(),
            'max_frp': cluster_data['frp'].max(),
            'mean_confidence': cluster_data['confidence'].map({'l': 1, 'n': 2, 'h': 3}).mean(),
            'persistence_score': cluster_data['acq_date'].nunique() / 30.0,  # Normalized
            'persistence_category': (
                'persistent' if cluster_data['acq_date'].nunique() >= 5 else
                'short_lived_repeated' if cluster_data['acq_date'].nunique() >= 2 else
                'isolated'
            ),
            'latitude': cluster_data['latitude'].mean(),
            'longitude': cluster_data['longitude'].mean(),
            'cluster_type': cluster_data['cluster_type'].iloc[0]  # Ground truth for evaluation
        }
        clusters.append(cluster_info)
    
    clusters_df = pd.DataFrame(clusters)
    
    # Save cluster features
    clusters_path = cfg.processed_data_dir / "firms_persistence.csv"
    clusters_df.to_csv(clusters_path, index=False)
    print(f"✓ Saved cluster features to: {clusters_path}")
    
    # Extract engineered features
    print("\nExtracting engineered features...")
    features_df = extract_features(clusters_df)
    
    # Save features
    features_path = cfg.processed_data_dir / "firms_features.csv"
    features_df.to_csv(features_path, index=False)
    print(f"✓ Saved engineered features to: {features_path}")
    
    # Train Isolation Forest
    print("\nTraining Isolation Forest...")
    
    # Check if required features exist
    missing_features = [f for f in FEATURES if f not in features_df.columns]
    if missing_features:
        print(f"⚠ Missing features: {missing_features}")
        print("  Adding missing features with defaults...")
        for f in missing_features:
            features_df[f] = 0.0
    
    detector = ThermalAnomalyDetector(contamination=0.05)
    detector.fit(features_df)
    
    # Predict anomalies
    results = detector.predict(features_df)
    
    # Save results
    results_path = cfg.processed_data_dir / "firms_anomalies.csv"
    results.to_csv(results_path, index=False)
    print(f"✓ Saved anomaly detection results to: {results_path}")
    
    # Save model
    detector.save(cfg.models_dir)
    print(f"✓ Saved trained model to: {cfg.models_dir}")
    
    # Print summary
    print("\n--- Anomaly Detection Summary ---")
    print(f"Total clusters analyzed: {len(results)}")
    print(f"Abnormality breakdown:")
    for level, count in results['abnormality_level'].value_counts().items():
        print(f"  {level}: {count} ({count/len(results)*100:.1f}%)")
    
    # Evaluate against ground truth
    if 'cluster_type' in results.columns:
        print("\n--- Ground Truth Comparison ---")
        for ctype in ['normal', 'industrial', 'agricultural', 'forest']:
            subset = results[results['cluster_type'] == ctype]
            if len(subset) > 0:
                anomaly_rate = (subset['abnormality_level'] != 'NORMAL').mean()
                print(f"  {ctype}: {len(subset)} clusters, {anomaly_rate:.1%} flagged as anomalous")
    
    return True


def create_model_artifacts():
    """Create necessary model artifacts for inference."""
    print("\n" + "="*60)
    print("  CREATING: Model Artifacts for Inference")
    print("="*60)
    
    from src.config import get_config
    import json
    
    cfg = get_config()
    
    # Create model metadata
    metadata = {
        "satellite_cnn": {
            "model": "EfficientNet-B0",
            "dataset": "EuroSAT",
            "num_classes": 10,
            "classes": [
                "AnnualCrop", "Forest", "HerbaceousVegetation", "Highway",
                "Industrial", "Pasture", "PermanentCrop", "Residential",
                "River", "SeaLake"
            ],
            "checkpoint": str(cfg.models_dir / "satellite_landuse_efficientnet_b0.pth")
        },
        "anomaly_detector": {
            "model": "IsolationForest",
            "features": [
                "max_bright_ti4", "bt_diff_max", "mean_frp", "max_frp",
                "observation_count", "active_days", "duration_days",
                "detection_density", "mean_confidence", "frp_mean_to_max_ratio"
            ],
            "contamination": 0.05,
            "scaler": str(cfg.models_dir / "robust_scaler.joblib"),
            "model_path": str(cfg.models_dir / "isolation_forest.joblib")
        },
        "trained_date": "2026-09-02",
        "version": "1.0.0"
    }
    
    metadata_path = cfg.models_dir / "model_metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✓ Created model metadata: {metadata_path}")
    
    # Create dummy satellite context for demo
    demo_context = pd.DataFrame({
        'cluster_id': range(10),
        'satellite_image_available': [False] * 10,
        'predicted_landcover_class': ['UNKNOWN'] * 10,
        'prediction_confidence': [0.0] * 10,
        'observation_status': ['Demo mode - no satellite imagery fetched'] * 10
    })
    
    context_path = cfg.processed_data_dir / "satellite_context.csv"
    demo_context.to_csv(context_path, index=False)
    print(f"✓ Created demo satellite context: {context_path}")
    
    return True


def evaluate_models():
    """Evaluate trained models and generate reports."""
    print("\n" + "="*60)
    print("  EVALUATING: Model Performance")
    print("="*60)
    
    from src.config import get_config
    from sklearn.metrics import classification_report
    
    cfg = get_config()
    
    # Evaluate anomaly detector
    results_path = cfg.processed_data_dir / "firms_anomalies.csv"
    if results_path.exists():
        results = pd.read_csv(results_path)
        
        print("\n--- Anomaly Detector Evaluation ---")
        
        if 'cluster_type' in results.columns:
            # Map cluster types to expected anomaly levels
            type_to_level = {
                'normal': 'NORMAL',
                'industrial': 'HIGH',
                'agricultural': 'ELEVATED',
                'forest': 'HIGH'
            }
            
            results['expected_level'] = results['cluster_type'].map(type_to_level)
            
            # Classification report
            valid_mask = results['expected_level'].notna()
            if valid_mask.sum() > 0:
                print("\nClassification Report (Expected vs Predicted Abnormality Level):")
                print(classification_report(
                    results.loc[valid_mask, 'expected_level'],
                    results.loc[valid_mask, 'abnormality_level'],
                    zero_division=0
                ))
        
        # Risk distribution
        if 'risk_level' in results.columns:
            print("\nRisk Level Distribution:")
            for level, count in results['risk_level'].value_counts().items():
                print(f"  {level}: {count}")
    
    # Create evaluation report
    report_path = cfg.reports_dir / "model_evaluation_report.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, 'w') as f:
        f.write("="*60 + "\n")
        f.write("THERMAL INTELLIGENCE ENGINE - MODEL EVALUATION REPORT\n")
        f.write("="*60 + "\n\n")
        f.write(f"Generated: 2026-09-02\n\n")
        
        f.write("MODELS TRAINED:\n")
        f.write("-" * 40 + "\n")
        f.write("1. Satellite CNN: EfficientNet-B0 (EuroSAT 10-class)\n")
        f.write("   - Purpose: Land-use classification from satellite imagery\n")
        f.write("   - Input: 64x64 RGB Sentinel-2 patches\n")
        f.write("   - Output: 10 land-use classes\n\n")
        
        f.write("2. Anomaly Detector: Isolation Forest\n")
        f.write("   - Purpose: Detect statistically abnormal thermal events\n")
        f.write("   - Features: 10 thermal/intensity metrics\n")
        f.write("   - Output: anomaly_score, anomaly_flag, abnormality_level\n\n")
        
        f.write("RECOMMENDED NEXT STEPS:\n")
        f.write("-" * 40 + "\n")
        f.write("1. Download real FIRMS data: python scripts/download_firms_data.py\n")
        f.write("2. Run full pipeline: python scripts/run_full_pipeline.py\n")
        f.write("3. Evaluate on real data: python scripts/evaluate_satellite_cnn.py\n")
    
    print(f"\n✓ Evaluation report saved to: {report_path}")
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Train all Thermal Intelligence models")
    parser.add_argument("--skip-satellite", action="store_true", help="Skip satellite CNN training")
    parser.add_argument("--skip-anomaly", action="store_true", help="Skip anomaly detector training")
    parser.add_argument("--epochs", type=int, default=5, help="Training epochs for satellite CNN")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size for satellite CNN")
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("  THERMAL INTELLIGENCE ENGINE - MODEL TRAINING")
    print("  SIH Project: AI-Driven Fire Detection & Risk Assessment")
    print("="*60)
    
    start_time = time.time()
    
    # Create directories
    create_models_directory()
    
    # Train models
    if not args.skip_satellite:
        train_satellite_cnn(epochs=args.epochs, batch_size=args.batch_size)
    
    if not args.skip_anomaly:
        train_anomaly_detector()
    
    # Create artifacts
    create_model_artifacts()
    
    # Evaluate
    evaluate_models()
    
    elapsed = time.time() - start_time
    
    print("\n" + "="*60)
    print(f"  TRAINING COMPLETE")
    print(f"  Total time: {elapsed:.1f}s")
    print("="*60)
    
    print("\nNext steps:")
    print("1. Run the full pipeline: python scripts/run_full_pipeline.py")
    print("2. Start the backend: uvicorn backend.main:app --reload")
    print("3. Start the frontend: cd web && npm run dev")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
