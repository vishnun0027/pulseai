import shap
import numpy as np
import warnings

warnings.filterwarnings("ignore")  # Suppress SHAP runtime warnings


class AnomalyExplainer:
    def __init__(self, model):
        self.model = model
        self.explainer = None
        self.feature_names = [
            "cpu_raw",
            "cpu_mean_5",
            "cpu_std_5",
            "mem_raw",
            "is_wsl",
            "is_container",
            "is_host",
        ]

    def update_explainer(self):
        """Re-initializes the SHAP TreeExplainer after the model retrains."""
        try:
            self.explainer = shap.TreeExplainer(self.model)
        except Exception as e:
            print(f"Failed to build SHAP explainer: {e}")

    def explain(self, feature_vector: list) -> dict:
        if not self.explainer:
            return {"error": "Explainer not initialized or model untrained"}

        X = np.array([feature_vector])

        try:
            shap_values = self.explainer.shap_values(X)
            if isinstance(shap_values, list):
                vals = shap_values[0][0]
            elif len(shap_values.shape) > 1:
                vals = shap_values[0]
            else:
                vals = shap_values

            importance = {}
            for i, name in enumerate(self.feature_names):
                importance[name] = float(vals[i])

            sorted_impact = sorted(
                importance.items(), key=lambda x: abs(x[1]), reverse=True
            )
            return {
                "top_contributors": [
                    {"feature": k, "impact": round(v, 4)} for k, v in sorted_impact[:3]
                ]
            }
        except Exception as e:
            return {"error": str(e)}
