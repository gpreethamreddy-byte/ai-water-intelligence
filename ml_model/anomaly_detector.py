import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
import joblib
import os

class WaterAnomalyDetector:
    def __init__(self, model_path="ml_model/isolation_forest.pkl"):
        self.model_path = model_path
        self.model = None
        self.contamination = 0.04
        self.load_or_train()

    def generate_synthetic_training_data(self, samples=2000):
        np.random.seed(42)
        # Normal operations
        q_in_normal = np.random.uniform(2.0, 15.0, int(samples * 0.96))
        delta_q_normal = np.random.normal(0.0, 0.12, int(samples * 0.96))
        pressure_normal = 300.0 - (q_in_normal * 4.0) + np.random.normal(0, 5, int(samples * 0.96))
        dh_dt_normal = np.random.normal(-0.05, 0.02, int(samples * 0.96))

        # Anomalies: Leak / burst scenarios
        q_in_leak = np.random.uniform(5.0, 18.0, int(samples * 0.04))
        delta_q_leak = np.random.uniform(1.2, 5.0, int(samples * 0.04))
        pressure_leak = np.random.uniform(120.0, 200.0, int(samples * 0.04))
        dh_dt_leak = np.random.uniform(-0.35, -0.15, int(samples * 0.04))

        X_normal = np.column_stack([q_in_normal, delta_q_normal, pressure_normal, dh_dt_normal])
        X_leak = np.column_stack([q_in_leak, delta_q_leak, pressure_leak, dh_dt_leak])
        return np.vstack([X_normal, X_leak])

    def load_or_train(self):
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                return
            except Exception:
                pass
        
        print("Training Isolation Forest anomaly detection model...")
        X_train = self.generate_synthetic_training_data()
        self.model = IsolationForest(
            n_estimators=120,
            contamination=self.contamination,
            random_state=42
        )
        self.model.fit(X_train)
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)

    def predict(self, q_in, q_out, pressure, dh_dt):
        delta_q = q_in - q_out
        feature_vector = np.array([[q_in, delta_q, pressure, dh_dt]])
        
        pred = self.model.predict(feature_vector)[0]  # -1 = anomaly, 1 = normal
        score = self.model.decision_function(feature_vector)[0]
        
        is_anomaly = bool((pred == -1) or (delta_q > 0.8))
        
        diagnosis = "NORMAL"
        if is_anomaly:
            if delta_q > 0.6 and pressure < 220:
                diagnosis = "PIPELINE_RUPTURE"
            elif delta_q > 0.6:
                diagnosis = "DIFFERENTIAL_LEAK"
            elif dh_dt < -0.2:
                diagnosis = "ABNORMAL_DRAINAGE"
            else:
                diagnosis = "UNUSUAL_CONSUMPTION_PATTERN"

        return is_anomaly, round(float(score), 3), diagnosis