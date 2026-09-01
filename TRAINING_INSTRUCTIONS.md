# Model Training Instructions

## Overview

This guide explains how to train all models in the Thermal Intelligence Engine.

## Prerequisites

1. **Python 3.8+** installed
2. **pip** package manager
3. **GPU recommended** (but CPU works too)

## Quick Start

### Step 1: Install Dependencies

```bash
cd SIH-project
pip install -r requirements.txt
```

### Step 2: Train All Models

```bash
python scripts/train_all_models.py
```

This will:
- Download EuroSAT dataset (if not present)
- Train Satellite CNN (EfficientNet-B0)
- Generate synthetic FIRMS data for testing
- Train Anomaly Detector (Isolation Forest)
- Create model artifacts
- Generate evaluation report

### Step 3: Run Full Pipeline

```bash
python scripts/run_full_pipeline.py --skip-download
```

## Individual Model Training

### 1. Satellite CNN Training

```bash
python scripts/train_satellite_cnn.py --epochs 10 --batch-size 32
```

**What it does:**
- Downloads EuroSAT dataset (27,000 Sentinel-2 RGB patches)
- Fine-tunes EfficientNet-B0 on 10 land-use classes
- Saves best model to `models/satellite_landuse_efficientnet_b0.pth`

**Expected output:**
- Training accuracy: ~90-95%
- Validation accuracy: ~85-90%
- Test accuracy: ~85-90%

### 2. Anomaly Detector Training

The anomaly detector uses Isolation Forest which is unsupervised - it learns from the data structure without needing labeled examples.

```bash
python scripts/train_all_models.py --skip-satellite
```

**What it does:**
- Generates synthetic FIRMS data with realistic patterns
- Extracts 10 features for anomaly detection
- Trains Isolation Forest model
- Saves model to `models/isolation_forest.joblib`

### 3. Full Pipeline (with real data)

```bash
# Download FIRMS data first
python scripts/download_firms_data.py

# Then run full pipeline
python scripts/run_full_pipeline.py
```

## Model Outputs

After training, you'll have:

```
models/
├── satellite_landuse_efficientnet_b0.pth  # Satellite CNN weights
├── isolation_forest.joblib                # Anomaly detector model
├── robust_scaler.joblib                   # Feature scaler
└── model_metadata.json                    # Model information
```

## Evaluation

### View Evaluation Report

```bash
cat reports/model_evaluation_report.txt
```

### Test Individual Models

```bash
# Test Satellite CNN inference
python scripts/run_satellite_inference.py

# Test Anomaly Detector
python scripts/run_anomaly_detection.py
```

## Troubleshooting

### Issue: EuroSAT download fails

**Solution:** The script will save a fallback model using ImageNet pretrained weights. You can still use it for inference.

### Issue: Memory errors

**Solution:** Reduce batch size:
```bash
python scripts/train_satellite_cnn.py --batch-size 16
```

### Issue: GPU not available

**Solution:** Training will automatically use CPU. It will be slower but works fine.

## Advanced Training Options

### Custom Training Loop

```python
from src.satellite.model import build_satellite_model
from src.satellite.dataset import get_eurosat_dataloaders

# Load data
train_loader, val_loader, test_loader, classes = get_eurosat_dataloaders(
    data_dir="data/external/satellite/eurosat",
    batch_size=32
)

# Build model
model = build_satellite_model(num_classes=10, pretrained=True)

# Your custom training code here...
```

### Fine-tuning on Custom Data

```python
# Load pre-trained model
from src.satellite.inference import SatelliteLandUsePredictor

predictor = SatelliteLandUsePredictor(
    checkpoint_path="models/satellite_landuse_efficientnet_b0.pth"
)

# Fine-tune on your custom dataset
# (requires modifying the training script)
```

## Performance Benchmarks

### Satellite CNN (EuroSAT)
- **Model:** EfficientNet-B0
- **Parameters:** ~5.3M
- **Inference time:** ~10ms per image (GPU), ~50ms (CPU)
- **Accuracy:** 85-90% on EuroSAT test set

### Anomaly Detector (Isolation Forest)
- **Model:** Isolation Forest
- **Features:** 10 thermal/intensity metrics
- **Training time:** <1 second
- **Inference time:** <1ms per sample

## Next Steps After Training

1. **Run the full pipeline** to process real FIRMS data
2. **Start the backend** to serve predictions via API
3. **Start the frontend** to visualize results
4. **Deploy** to production (see DEPLOYMENT.md)

## Support

For issues or questions:
- Check the logs in `reports/logs/`
- Review the evaluation report in `reports/`
- Refer to the main README.md
