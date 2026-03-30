# Feedback Handle (Python)

## Overview
The `feedback/` module handles incoming classifications from the user interface where a human operator flags previous anomalies as either a false positive or true anomalous threat.

## Responsibilities
- **Label Ingestion**: Accepts inputs indicating `false_positive`, `true_anomaly`, or `expected_change` (like "I just installed an update").
- **Metrics Reweighting**: Dispatches configuration amendments down into the AI pipelines to tune sensitivities iteratively based on user consensus.
