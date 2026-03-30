# Dashboard Web Interface (Python/FastAPI)

## Overview
The `dashboard/` module houses a FastAPI web layer serving a graphical interface for human operators.

## Responsibilities
- **Data Visualization**: Graphs the timeseries metrics (CPU, RAM, Connections) efficiently pulled from TimescaleDB read replicas.
- **Incident Explainability**: Exposes SHAP-generated JSON models visualizing *why* a particular timeframe was flagged anomalous to non-AI engineers.
- **Feedback Collection**: Implements a simple form and classification endpoint allowing users to score flagged events.
