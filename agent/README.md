# Tracking Agent Module (Rust)

## Overview
The `agent/` module is an extremely lightweight, high-performance background daemon authored in Rust. 

## Responsibilities
- **Metrics Collection**: Gathers `sysinfo` data, including CPU usage, RAM utilization, load averages, and dynamically detects the presence of GPUs using `nvidia-smi`.
- **Environment Detection**: Automatically classifies the host operating framework (Linux Host, Windows, WSL, Docker Container, etc.). 
- **Session & State Management**: Maintains persistent identity tokens (`.agent_state.json`) and evaluates temporal gaps (`gap_detector.rs`) to classify periods of missing tracking points (e.g. `micro_gap`, `long_gap`).
- **Telemetry Publication**: Periodically sends the structured system snapshots to the `ingestion/` backend.
