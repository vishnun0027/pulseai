"""
ai/trainer.py
Offline trainer for the IsolationForest model.
Use this to pre-train on historical data and save the model to disk.
The live consumer (consumer.py) uses online incremental training, but this
module is useful for cold-start scenarios or retraining from a dataset.
"""

import os
import json
import pickle
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

from ai.features import FeatureEngineer


MODEL_PATH = os.environ.get("MODEL_PATH", "models/isolation_forest.pkl")


class OfflineTrainer:
    def __init__(self, contamination: float = 0.05, window_size: int = 5):
        self.contamination = contamination
        self.model = IsolationForest(
            contamination=contamination,
            n_estimators=200,   # More trees for better accuracy offline
            max_samples="auto",
            random_state=42,
        )
        self.engineer = FeatureEngineer(window_size=window_size)
        self.X_train = []
        self.X_test = []

    def load_from_jsonl(self, path: str):
        """Load telemetry payloads from a JSON-Lines file (one payload per line)."""
        feature_vectors = []
        with open(path) as f:
            for line in f:
                payload = json.loads(line.strip())
                feats = self.engineer.process(payload)
                fvec = self.engineer.get_feature_vector(feats)
                feature_vectors.append(fvec)
        print(f"[Trainer] Loaded {len(feature_vectors)} samples from {path}.")
        return feature_vectors

    def fit(self, feature_vectors: list, test_split: float = 0.1):
        """Train the IsolationForest on feature vectors, holding out a test split."""
        X = np.array(feature_vectors)
        self.X_train, self.X_test = train_test_split(X, test_size=test_split, random_state=42)
        self.model.fit(self.X_train)
        print(f"[Trainer] Trained on {len(self.X_train)} samples.")

    def evaluate(self):
        """Score the held-out test split. Prints average anomaly score."""
        if not len(self.X_test):
            print("[Trainer] No test data available.")
            return
        scores = self.model.decision_function(self.X_test)
        preds = self.model.predict(self.X_test)   # 1 = normal, -1 = anomaly
        anomaly_count = (preds == -1).sum()
        print(f"[Trainer] Test anomaly rate: {anomaly_count}/{len(preds)} "
              f"({100 * anomaly_count / len(preds):.1f}%)")
        print(f"[Trainer] Average decision score: {scores.mean():.4f}")

    def save(self, path: str = MODEL_PATH):
        """Persist the trained model to disk for hot-loading in the consumer."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self.model, f)
        print(f"[Trainer] Model saved to {path}")

    @staticmethod
    def load(path: str = MODEL_PATH):
        """Load a pre-trained model from disk."""
        with open(path, "rb") as f:
            model = pickle.load(f)
        print(f"[Trainer] Model loaded from {path}")
        return model


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m ai.trainer <path/to/telemetry.jsonl>")
        sys.exit(1)

    trainer = OfflineTrainer(contamination=0.05)
    vecs = trainer.load_from_jsonl(sys.argv[1])
    trainer.fit(vecs)
    trainer.evaluate()
    trainer.save()
