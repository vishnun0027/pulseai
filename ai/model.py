from sklearn.ensemble import IsolationForest
import numpy as np

class AnomalyModel:
    def __init__(self, contamination=0.02, threshold=0.05):
        """Initialize anomaly detector.
        
        Args:
            contamination: Expected proportion of anomalies in training set (0.02 = 2% for aggressive detection)
            threshold: Score threshold above which samples are flagged as anomalies
        """
        self.model = IsolationForest(contamination=contamination, random_state=42)
        self.is_trained = False
        self.buffer = []
        self.threshold = threshold
        
    def train_or_update(self, feature_vector: list):
        """
        In a real system, we'd train on days of data. Here we build a quick buffer 
        and train once we have enough samples.
        """
        self.buffer.append(feature_vector)
        if len(self.buffer) >= 20:  # Quick baseline (~100 seconds at 5s intervals)
            X = np.array(self.buffer)
            self.model.fit(X)
            self.is_trained = True
            print(f"[Model] Baseline training complete with {len(self.buffer)} samples.")
            # Clear buffer for next retrain
            self.buffer = []

    def score(self, feature_vector: list) -> float:
        """
        Returns IsolationForest decision_function directly.
        Negative values = anomalies (outliers), Positive = normal.
        No inversion needed.
        """
        if not self.is_trained:
            return 0.0
            
        X = np.array([feature_vector])
        return float(self.model.decision_function(X)[0])
    
    def is_anomaly(self, score: float) -> bool:
        """Returns True if score is below the threshold (negative = anomaly)."""
        return score < self.threshold
