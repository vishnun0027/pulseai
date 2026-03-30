# Baseline & Drift Analysis (Python)

## Overview
The `baseline/` module utilizes online concept drift mechanisms (like ADWIN) to dynamically recalibrate normal states dynamically and avoid false positives when environmental constants change organically instead of maliciously.

## Responsibilities
- **Baseline Re-calibration**: Differentiates between a definitive "anomaly" vs long-term "drift" (a permanent shift in system activity patterns).
- **Rule Layer Handling**: If sustained drift occurs (e.g. newly deployed steady software load), temporarily dampens sensitivities to redefine the intelligence baselines.
