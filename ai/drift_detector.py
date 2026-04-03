"""
ai/drift_detector.py
A feature-level concept drift detector wrapping the ADWIN algorithm.
Different from baseline/drift_classifier.py which tracks raw CPU/memory.
This module tracks model-level feature distributions — e.g., rolling CPU means —
to detect when the system's *behavior profile* has fundamentally shifted.
"""

from river import drift
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class DriftState:
    """Tracks drift state across multiple feature streams."""

    is_drifting: bool = False
    drifting_features: list = field(default_factory=list)
    change_count: int = 0


class FeatureDriftDetector:
    """
    Monitors multiple feature channels independently with ADWIN.
    Emits a drift event when any critical feature distribution shifts.
    """

    def __init__(self, feature_names: Optional[list] = None):
        self.feature_names = feature_names or [
            "cpu_raw",
            "cpu_mean_5",
            "cpu_std_5",
            "mem_raw",
        ]
        # One ADWIN instance per feature
        self._detectors: Dict[str, drift.ADWIN] = {
            name: drift.ADWIN() for name in self.feature_names
        }
        self.state = DriftState()

    def update(self, feature_dict: dict) -> DriftState:
        """
        Feed the latest feature values. Returns updated DriftState.
        Call this every inference cycle.
        """
        drifting = []
        for name in self.feature_names:
            value = feature_dict.get(name)
            if value is None:
                continue
            detector = self._detectors[name]
            detector.update(float(value))
            if detector.drift_detected:
                drifting.append(name)

        if drifting:
            self.state.is_drifting = True
            self.state.drifting_features = drifting
            self.state.change_count += 1
        else:
            self.state.is_drifting = False
            self.state.drifting_features = []

        return self.state

    def reset(self):
        """Reset all detectors — call after model retraining."""
        self._detectors = {name: drift.ADWIN() for name in self.feature_names}
        self.state = DriftState()
        print("[DriftDetector] All ADWIN detectors reset.")

    def summary(self) -> dict:
        return {
            "is_drifting": self.state.is_drifting,
            "drifting_features": self.state.drifting_features,
            "total_drift_events": self.state.change_count,
        }


if __name__ == "__main__":
    # Quick smoke test
    import random

    detector = FeatureDriftDetector()

    print("Feeding 200 normal samples...")
    for _ in range(200):
        state = detector.update(
            {
                "cpu_raw": random.gauss(5.0, 1.0),
                "cpu_mean_5": random.gauss(5.0, 0.5),
                "cpu_std_5": random.gauss(0.5, 0.1),
                "mem_raw": random.gauss(2.0e9, 1e8),
            }
        )
    print(f"Drift after normal: {detector.summary()}")

    print("\nFeeding 100 shifted samples (CPU jumps to 80%)...")
    for _ in range(100):
        state = detector.update(
            {
                "cpu_raw": random.gauss(80.0, 2.0),
                "cpu_mean_5": random.gauss(80.0, 1.0),
                "cpu_std_5": random.gauss(1.0, 0.2),
                "mem_raw": random.gauss(6.0e9, 2e8),
            }
        )
        if state.is_drifting:
            print(f"  Drift detected on: {state.drifting_features}")
            break
    print(f"Final: {detector.summary()}")
