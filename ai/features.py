import pandas as pd
import numpy as np

class FeatureEngineer:
    def __init__(self, window_size=5):
        self.window_size = window_size
        self.history = []

    def process(self, payload: dict) -> dict:
        """
        Takes a raw AgentPayload dict and computes rolling features.
        """
        metrics = payload.get("metrics", {})
        cpu = metrics.get("cpu_usage", 0.0)
        mem = metrics.get("used_memory", 0)
        
        # Keep recent history
        self.history.append({"cpu": cpu, "mem": mem})
        if len(self.history) > self.window_size:
            self.history.pop(0)
            
        # Calculate rolling features
        cpu_hist = [h["cpu"] for h in self.history]
        
        cpu_mean = np.mean(cpu_hist)
        cpu_std = np.std(cpu_hist) if len(cpu_hist) > 1 else 0.0
        
        # Convert env info to a categorical representation (One-Hot dummy)
        env = payload.get("environment", {}).get("env_type", "Unknown")
        is_wsl = 1.0 if env == "Wsl" else 0.0
        is_container = 1.0 if env == "Container" else 0.0
        is_host = 1.0 if env in ("HostLinux", "HostWindows") else 0.0

        features = {
            "cpu_raw": float(cpu),
            "cpu_mean_5": float(cpu_mean),
            "cpu_std_5": float(cpu_std),
            "mem_raw": float(mem),
            "is_wsl": is_wsl,
            "is_container": is_container,
            "is_host": is_host
        }
        
        return features

    def get_feature_vector(self, features: dict) -> list:
        # Define a consistent ordering for the model
        keys = ["cpu_raw", "cpu_mean_5", "cpu_std_5", "mem_raw", "is_wsl", "is_container", "is_host"]
        return [features[k] for k in keys]
