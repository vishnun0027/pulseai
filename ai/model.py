from sklearn.ensemble import IsolationForest
import numpy as np

class AnomalyModel:
    def __init__(self, contamination="auto"):
        self.model = IsolationForest(contamination=contamination, random_state=42)
        self.is_trained = False
        self.buffer = []
        
    def train_or_update(self, feature_vector: list):
        """
        In a real system, we'd train on days of data. Here we build a quick buffer 
        and train once we have enough samples.
        """
        self.buffer.append(feature_vector)
        if len(self.buffer) >= 20: # Arbitrary small number for demo
            X = np.array(self.buffer)
            self.model.fit(X)
            self.is_trained = True
            print(f"[Model] Baseline training complete with {len(self.buffer)} samples.")
            # Clear buffer for next retrain
            self.buffer = []

    def score(self, feature_vector: list) -> float:
        """
        Returns anomaly score. Negative values are outliers, positive are inliers.
        We invert it so higher = more anomalous.
        """
        if not self.is_trained:
            return 0.0
            
        X = np.array([feature_vector])
        return -float(self.model.decision_function(X)[0])
