import random
import sys
import os

# Add the parent directory to sys.path so we can import baseline
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.features import FeatureEngineer
from ai.model import AnomalyModel
from baseline.drift_classifier import DriftDetector


def generate_mock_payload(is_anomaly=False, is_drift=False):
    """Simulates the JSON payload from the Rust agent."""
    cpu = random.uniform(2.0, 10.0)
    mem = random.uniform(1000000, 2000000)

    if is_anomaly:
        cpu = random.uniform(80.0, 95.0)  # Huge sudden spike
        mem = random.uniform(6000000, 8000000)

    if is_drift:
        cpu = random.uniform(40.0, 50.0)  # Sustained higher usage
        mem = random.uniform(4000000, 5000000)

    return {
        "metrics": {"cpu_usage": cpu, "used_memory": mem},
        "environment": {"env_type": "Wsl"},
    }


def run_simulation():
    engineer = FeatureEngineer(window_size=5)
    detector = DriftDetector()
    model = AnomalyModel(contamination=0.05, threshold=0.5)

    print("--- Phase 1: Training Baseline ---")
    # Feed 25 normal metrics to train the Isolation Forest
    for i in range(25):
        payload = generate_mock_payload()
        feats_dict = engineer.process(payload)
        fvec = engineer.get_feature_vector(feats_dict)
        model.train_or_update(fvec)

    print("\n--- Phase 2: Scoring Normal Traffic ---")
    for i in range(3):
        payload = generate_mock_payload()
        feats_dict = engineer.process(payload)
        fvec = engineer.get_feature_vector(feats_dict)
        score = model.score(fvec)
        drift = detector.check_drift(feats_dict["cpu_mean_5"], feats_dict["mem_raw"])
        print(f"Normal  | Score: {score:+.3f} | Drift: {drift}")

    print("\n--- Phase 3: Anomaly Injection ---")
    payload = generate_mock_payload(is_anomaly=True)
    feats_dict = engineer.process(payload)
    fvec = engineer.get_feature_vector(feats_dict)
    score = model.score(fvec)
    drift = detector.check_drift(feats_dict["cpu_mean_5"], feats_dict["mem_raw"])
    print(f"Spike   | Score: {score:+.3f} | Drift: {drift}")

    print("\n--- Phase 4: Concept Drift (New Normal) ---")
    for i in range(15):
        payload = generate_mock_payload(is_drift=True)
        feats_dict = engineer.process(payload)
        fvec = engineer.get_feature_vector(feats_dict)
        score = model.score(fvec)
        drift = detector.check_drift(feats_dict["cpu_mean_5"], feats_dict["mem_raw"])
        print(f"Drift   | Score: {score:+.3f} | Drift: {drift}")


if __name__ == "__main__":
    run_simulation()
