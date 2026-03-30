# AI Engine Module (Python)

## Overview
The `ai/` folder orchestrates the anomaly detection machine learning pipelines via scikit-learn variants (like Isolation Forest) and TreeSHAP.

## Responsibilities
- **Feature Engineering**: Calculates rolling statistics, momentum/variance equations, and categorizes categorical inputs (like time-of-day or OS type).
- **Inference Workers**: Assigns real-time risk scores to incoming system telemetry payload streams.
- **Explainability**: Utilizes TreeSHAP to calculate human-readable causal feature descriptions (e.g. *“Anomaly score elevated because of high sustained GPU accompanied by unknown `backup_x` process novelty”*).
