from pathlib import Path
from datetime import datetime
import joblib
import numpy as np
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "dataset" / "water_readings.csv"
MODEL_PATH = BASE_DIR / "models" / "water_anomaly_model.joblib"

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

FEATURES = ["flow_rate_lpm", "pressure_bar", "tank_level_percent"]

def create_sample_data():
    """Create clearly labelled demonstration sensor data if no CSV exists."""
    rng = np.random.default_rng(42)
    rows = []
    start = pd.Timestamp.now().floor("h") - pd.Timedelta(hours=167)
    for i in range(168):
        hour = (start + pd.Timedelta(hours=i)).hour
        normal_flow = 7.5 if 6 <= hour <= 22 else 0.8
        flow = max(0.0, rng.normal(normal_flow, 1.0))
        pressure = float(np.clip(rng.normal(3.0, 0.18), 2.3, 3.6))
        tank = float(np.clip(rng.normal(65, 8), 20, 90))
        label = "Normal"
        # Insert a few controlled examples for the demo.
        if i in [31, 32, 33, 84, 85, 126]:
            flow = float(rng.normal(18, 1.2))
            pressure = float(rng.normal(1.75, 0.12))
            label = "Leak-like"
        if i in [54, 55, 56]:
            flow = float(rng.normal(13, 0.8))
            tank = float(rng.normal(98, 0.8))
            label = "Possible overflow"
        rows.append({
            "timestamp": (start + pd.Timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S"),
            "flow_rate_lpm": round(flow, 2),
            "pressure_bar": round(pressure, 2),
            "tank_level_percent": round(tank, 1),
            "demo_label": label
        })
    pd.DataFrame(rows).to_csv(DATA_PATH, index=False)

def load_data():
    if not DATA_PATH.exists():
        create_sample_data()
    df = pd.read_csv(DATA_PATH)
    required = ["timestamp"] + FEATURES
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError("Dataset is missing columns: " + ", ".join(missing))
    for col in FEATURES:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=FEATURES).copy()
    return df

def train_or_load_model(df):
    if MODEL_PATH.exists():
        try:
            return joblib.load(MODEL_PATH)
        except Exception:
            MODEL_PATH.unlink(missing_ok=True)
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("detector", IsolationForest(
            n_estimators=150, contamination=0.07, random_state=42
        ))
    ])
    model.fit(df[FEATURES])
    joblib.dump(model, MODEL_PATH)
    return model

def analyse_readings(df):
    model = train_or_load_model(df)
    result = df.copy()
    result["anomaly"] = model.predict(result[FEATURES]) == -1
    result["reason"] = ""
    result["risk"] = "Low"
    result["estimated_loss_litres"] = 0.0

    for idx, row in result.iterrows():
        reasons = []
        # Demonstration rules; thresholds must be calibrated for real pipelines.
        if row["flow_rate_lpm"] > 14 and row["pressure_bar"] < 2.3:
            reasons.append("High flow with low pressure")
        if row["flow_rate_lpm"] > 12 and row["tank_level_percent"] >= 95:
            reasons.append("High flow while tank is nearly full")
        if row["flow_rate_lpm"] > 16:
            reasons.append("Unusually high flow")
        if row["anomaly"]:
            reasons.append("ML anomaly detected")

        if reasons:
            result.at[idx, "reason"] = "; ".join(dict.fromkeys(reasons))
            if row["flow_rate_lpm"] > 16 or (
                row["flow_rate_lpm"] > 14 and row["pressure_bar"] < 2.0
            ):
                result.at[idx, "risk"] = "High"
            else:
                result.at[idx, "risk"] = "Medium"
            # Estimate excess flow above a simple 8 L/min baseline for one reading hour.
            excess_lpm = max(0.0, float(row["flow_rate_lpm"]) - 8.0)
            result.at[idx, "estimated_loss_litres"] = round(excess_lpm * 60, 1)

    result["estimated_loss_litres"] = result["estimated_loss_litres"].fillna(0)
    return result

@app.route("/", methods=["GET"])
def index():
    try:
        df = load_data()
        analysed = analyse_readings(df)
    except Exception as exc:
        return render_template("error.html", error=str(exc)), 500

    alerts = analysed[analysed["risk"] != "Low"].sort_values("timestamp", ascending=False)
    latest = analysed.iloc[-1]
    total_loss = float(analysed["estimated_loss_litres"].sum())
    high_count = int((analysed["risk"] == "High").sum())
    medium_count = int((analysed["risk"] == "Medium").sum())

    chart_data = {
        "labels": analysed["timestamp"].tail(24).tolist(),
        "flow": analysed["flow_rate_lpm"].tail(24).round(2).tolist(),
        "pressure": analysed["pressure_bar"].tail(24).round(2).tolist(),
        "tank": analysed["tank_level_percent"].tail(24).round(2).tolist()
    }
    return render_template(
        "index.html",
        latest=latest,
        total_readings=len(analysed),
        alert_count=len(alerts),
        high_count=high_count,
        medium_count=medium_count,
        total_loss=round(total_loss, 1),
        alerts=alerts.tail(12).to_dict(orient="records"),
        chart_data=chart_data,
        last_updated=datetime.now().strftime("%d %b %Y, %I:%M %p")
    )

@app.route("/add-reading", methods=["POST"])
def add_reading():
    try:
        flow = float(request.form["flow_rate_lpm"])
        pressure = float(request.form["pressure_bar"])
        tank = float(request.form["tank_level_percent"])
        if flow < 0 or pressure < 0 or not 0 <= tank <= 100:
            raise ValueError("Values must be non-negative and tank level must be 0–100.")
        df = load_data()
        new_row = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "flow_rate_lpm": flow,
            "pressure_bar": pressure,
            "tank_level_percent": tank,
            "demo_label": "User entered"
        }])
        pd.concat([df, new_row], ignore_index=True).to_csv(DATA_PATH, index=False)
        # Retrain against the updated demonstration dataset.
        MODEL_PATH.unlink(missing_ok=True)
        flash("Reading added. The dashboard has been refreshed.", "success")
    except (ValueError, KeyError) as exc:
        flash(f"Could not add reading: {exc}", "error")
    return redirect(url_for("index"))

@app.route("/reset-demo", methods=["POST"])
def reset_demo():
    create_sample_data()
    MODEL_PATH.unlink(missing_ok=True)
    flash("Demo dataset reset to its original sample readings.", "success")
    return redirect(url_for("index"))

if __name__ == "__main__":
    if not DATA_PATH.exists():
        create_sample_data()
    app.run(host="0.0.0.0", port=5000, debug=True)
