from pathlib import Path
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

from flask import Flask, render_template, request, redirect, url_for, flash

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline


# ---------------------------------------
# 1. PROJECT PATHS AND FLASK CONFIGURATION
# ---------------------------------------

BASE_DIR = Path(__file__).resolve().parent

DATA_PATH = BASE_DIR / "dataset" / "water_readings.csv"

MODEL_PATH = BASE_DIR / "models" / "water_anomaly_model.joblib"

app = Flask(__name__)

app.secret_key = "change-this-secret-key"

FEATURES = [
    "flow_rate_lpm",
    "pressure_bar",
    "tank_level_percent"
]


# ---------------------------------------
# 2. CREATE SAMPLE DATA
# ---------------------------------------

def create_sample_data():

    """Create demonstration sensor readings."""

    rng = np.random.default_rng(42)

    rows = []

    start = pd.Timestamp.now().floor("h") - pd.Timedelta(hours=167)

    for i in range(168):

        current_time = start + pd.Timedelta(hours=i)

        hour = current_time.hour

        normal_flow = 7.5 if 6 <= hour <= 22 else 0.8

        flow = max(0.0, rng.normal(normal_flow, 1.0))

        pressure = float(
            np.clip(rng.normal(3.0, 0.18), 2.3, 3.6)
        )

        tank = float(
            np.clip(rng.normal(65, 8), 20, 90)
        )

        label = "Normal"

        # Demonstration leakage examples
        if i in [31, 32, 33, 84, 85, 126]:

            flow = float(rng.normal(18, 1.2))

            pressure = float(rng.normal(1.75, 0.12))

            label = "Leak-like"

        # Demonstration overflow examples
        if i in [54, 55, 56]:

            flow = float(rng.normal(13, 0.8))

            tank = float(rng.normal(98, 0.8))

            label = "Possible overflow"

        rows.append({

            "timestamp": current_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

            "flow_rate_lpm": round(flow, 2),

            "pressure_bar": round(pressure, 2),

            "tank_level_percent": round(tank, 1),

            "demo_label": label

        })

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(rows).to_csv(DATA_PATH, index=False)


# ---------------------------------------
# 3. LOAD DATASET
# ---------------------------------------

def load_data():

    if not DATA_PATH.exists():

        create_sample_data()

    df = pd.read_csv(DATA_PATH)

    required = ["timestamp"] + FEATURES

    missing = [
        column for column in required
        if column not in df.columns
    ]

    if missing:

        raise ValueError(
            "Dataset is missing columns: " + ", ".join(missing)
        )

    for column in FEATURES:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df = df.dropna(subset=FEATURES).copy()

    if df.empty:

        raise ValueError(
            "Dataset contains no valid sensor readings."
        )

    return df


# ---------------------------------------
# 4. TRAIN OR LOAD MACHINE LEARNING MODEL
# ---------------------------------------

def train_or_load_model(df):

    if MODEL_PATH.exists():

        try:

            return joblib.load(MODEL_PATH)

        except Exception:

            MODEL_PATH.unlink(missing_ok=True)

    model = Pipeline([

        ("scaler", StandardScaler()),

        ("detector", IsolationForest(
            n_estimators=150,
            contamination=0.07,
            random_state=42
        ))

    ])

    model.fit(df[FEATURES])

    MODEL_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    joblib.dump(model, MODEL_PATH)

    return model


# ---------------------------------------
# 5. ANALYSE WATER READINGS
# ---------------------------------------

def analyse_readings(df):

    model = train_or_load_model(df)

    result = df.copy()

    # Machine learning anomaly detection
    result["anomaly"] = (
        model.predict(result[FEATURES]) == -1
    )

    # Create additional columns
    result["reason"] = ""

    result["risk"] = "Low"

    result["risk_score"] = 0

    result["recommendation"] = (
        "Continue normal monitoring."
    )

    result["estimated_loss_litres"] = 0.0

    # Extract hour from timestamp
    timestamps = pd.to_datetime(
        result["timestamp"],
        errors="coerce"
    )

    result["hour"] = timestamps.dt.hour

    for idx, row in result.iterrows():

        reasons = []

        recommendations = []

        score = 0

        flow = float(row["flow_rate_lpm"])

        pressure = float(row["pressure_bar"])

        tank = float(row["tank_level_percent"])

        hour = row["hour"]

        # RULE 1: Possible pipeline leakage
        if flow > 14 and pressure < 2.3:

            reasons.append(
                "High flow with low pressure"
            )

            recommendations.append(
                "Inspect pipeline joints and check for possible leakage."
            )

            score += 45

        # RULE 2: Unusually high flow
        if flow > 16:

            reasons.append(
                "Unusually high flow"
            )

            recommendations.append(
                "Verify the water flow meter and inspect consumption."
            )

            score += 25

        # RULE 3: Possible tank overflow
        if flow > 12 and tank >= 95:

            reasons.append(
                "High flow while tank is nearly full"
            )

            recommendations.append(
                "Inspect the tank inlet and water-level control."
            )

            score += 25

        # RULE 4: Unexpected night-time usage
        # Quiet hours: 11 PM to 5 AM
        if (
            pd.notna(hour)
            and (hour == 23 or hour < 5)
            and flow > 3
        ):

            reasons.append(
                "Unusual water usage during quiet hours"
            )

            recommendations.append(
                "Check whether water is flowing when usage is expected to be low."
            )

            score += 20

        # RULE 5: Machine learning anomaly
        if row["anomaly"]:

            reasons.append(
                "ML anomaly detected"
            )

            recommendations.append(
                "Review this reading against normal usage patterns."
            )

            score += 25

        # Maximum illustrative score
        score = min(score, 100)

        # Risk classification
        if score >= 60:

            risk = "High"

        elif score >= 25:

            risk = "Medium"

        else:

            risk = "Low"

        # Estimated excess water
        # Assumes one hour of flow and an 8 L/min baseline.
        excess_lpm = max(0.0, flow - 8.0)

        estimated_loss = round(
            excess_lpm * 60,
            1
        )

        # Store analysis results
        result.at[idx, "reason"] = (
            "; ".join(dict.fromkeys(reasons))
        )

        result.at[idx, "recommendation"] = (
            " ".join(dict.fromkeys(recommendations))
            if recommendations
            else "Continue normal monitoring."
        )

        result.at[idx, "risk_score"] = score

        result.at[idx, "risk"] = risk

        result.at[idx, "estimated_loss_litres"] = (
            estimated_loss
        )

    result["estimated_loss_litres"] = (
        result["estimated_loss_litres"].fillna(0)
    )

    return result


# ---------------------------------------
# 6. HOME DASHBOARD
# ---------------------------------------

@app.route("/", methods=["GET"])
def index():

    try:

        df = load_data()

        analysed = analyse_readings(df)

    except Exception as exc:

        return render_template(
            "error.html",
            error=str(exc)
        ), 500

    # Get alerts
    alerts = analysed[
        analysed["risk"] != "Low"
    ].sort_values(
        "timestamp",
        ascending=False
    )

    # Latest reading
    latest = analysed.iloc[-1]

    # Total estimated excess water
    total_loss = float(
        analysed["estimated_loss_litres"].sum()
    )

    # Count high-risk readings
    high_count = int(
        (analysed["risk"] == "High").sum()
    )

    # Count medium-risk readings
    medium_count = int(
        (analysed["risk"] == "Medium").sum()
    )

    # Chart data
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

        alerts=alerts.head(12).to_dict(orient="records"),

        chart_data=chart_data,

        last_updated=datetime.now().strftime(
            "%d %b %Y, %I:%M %p"
        )

    )


# ---------------------------------------
# 7. ADD NEW SENSOR READING
# ---------------------------------------

@app.route("/add-reading", methods=["POST"])
def add_reading():

    try:

        flow = float(
            request.form["flow_rate_lpm"]
        )

        pressure = float(
            request.form["pressure_bar"]
        )

        tank = float(
            request.form["tank_level_percent"]
        )

        # Validate numeric values
        if (
            not np.isfinite(flow)
            or not np.isfinite(pressure)
            or not np.isfinite(tank)
        ):

            raise ValueError(
                "Please enter valid finite numbers."
            )

        # Validate sensor values
        if flow < 0 or pressure < 0 or not 0 <= tank <= 100:

            raise ValueError(
                "Values must be non-negative and tank level must be 0–100."
            )

        df = load_data()

        new_row = pd.DataFrame([{

            "timestamp": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

            "flow_rate_lpm": flow,

            "pressure_bar": pressure,

            "tank_level_percent": tank,

            "demo_label": "User entered"

        }])

        updated_data = pd.concat(
            [df, new_row],
            ignore_index=True
        )

        updated_data.to_csv(
            DATA_PATH,
            index=False
        )

        # Retrain model using updated readings
        MODEL_PATH.unlink(missing_ok=True)

        flash(
            "Reading added and analysed successfully.",
            "success"
        )

    except (ValueError, KeyError) as exc:

        flash(
            f"Could not add reading: {exc}",
            "error"
        )

    return redirect(url_for("index"))


# ---------------------------------------
# 8. RESET DEMONSTRATION DATA
# ---------------------------------------

@app.route("/reset-demo", methods=["POST"])
def reset_demo():

    create_sample_data()

    MODEL_PATH.unlink(missing_ok=True)

    flash(
        "Demo dataset reset to its original sample readings.",
        "success"
    )

    return redirect(url_for("index"))


# ---------------------------------------
# 9. RUN FLASK APPLICATION
# ---------------------------------------

if __name__ == "__main__":

    if not DATA_PATH.exists():

        create_sample_data()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )