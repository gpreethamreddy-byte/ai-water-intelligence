import os
import pandas as pd
import joblib

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

# Project paths

DATA_PATH = "dataset/water_readings.csv"
MODEL_PATH = "models/water_anomaly_model.joblib"

# Load dataset

data = pd.read_csv(DATA_PATH)

# Features used by app.py

FEATURES = [
"flow_rate_lpm",
"pressure_bar",
"tank_level_percent"
]

# Prepare training data

X = data[FEATURES].dropna()

# Create ML model

model = Pipeline([
("scaler", StandardScaler()),
("detector", IsolationForest(
n_estimators=150,
contamination=0.07,
random_state=42
))
])

# Train model

model.fit(X)

# Create models folder

os.makedirs("models", exist_ok=True)

# Save trained model

joblib.dump(model, MODEL_PATH)

print("SUCCESS: Water anomaly model trained!")
print("Model saved at:", MODEL_PATH)
print("Training records:", len(X))
