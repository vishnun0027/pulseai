from sklearn.ensemble import IsolationForest
import numpy as np

class AnomalyModel:
    def __init__(self, contamination=0.02, threshold=0.05, max_buffer=100):
        """Initialize anomaly detector.
        
        Args:
            contamination: Expected proportion of anomalies in training set
            threshold: Score threshold below which samples are flagged as anomalies
            max_buffer: Maximum number of recent samples to keep for training
        """
        self.model = IsolationForest(contamination=contamination, random_state=42)
        self.is_trained = False
        self.buffer = []
        self.threshold = threshold
        self.max_buffer = max_buffer
        
    def train_or_update(self, feature_vector: list):
        """
        Maintain a sliding window of recent feature vectors and retrain
        the model periodically.
        """
        self.buffer.append(feature_vector)
        
        # Maintain sliding window
        if len(self.buffer) > self.max_buffer:
            self.buffer.pop(0)

        # Retrain if we have enough samples relative to window size
        # (Initial training at 20 samples, then continuous refinement)
        if len(self.buffer) >= 20 and (len(self.buffer) % 10 == 0 or not self.is_trained):
            X = np.array(self.buffer)
            self.model.fit(X)
            self.is_trained = True
            # No longer clearing buffer — it's now a sliding baseline.

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
