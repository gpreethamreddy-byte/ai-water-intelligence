# AI-Powered Water Intelligence and Leak Prediction System

A hackathon software prototype that analyses water flow, pipeline pressure, and tank-level readings. It combines transparent rule-based checks with an Isolation Forest anomaly-detection model and displays possible issues in a Flask dashboard.

## Features
- Sample sensor dataset generated automatically on first run.
- Detects possible leak-like patterns, high flow, and possible tank overflow.
- Isolation Forest flags unusual combinations of readings.
- Low / Medium / High risk labels for review.
- Approximate excess-water estimate for flagged readings.
- Dashboard trends and a form to add simulated sensor readings.
- Reset button to restore the sample dataset.

## Project structure
```text
AI_Water_Intelligence/
├── app.py
├── requirements.txt
├── README.md
├── dataset/
│   └── water_readings.csv  (created automatically if missing)
├── models/
│   └── water_anomaly_model.joblib  (created after first run)
├── static/
│   └── style.css
└── templates/
    ├── index.html
    └── error.html
```

## Run on Windows (VS Code terminal / PowerShell)
1. Install Python 3.10 or newer.
2. Open this folder in VS Code.
3. Create a virtual environment:
   `python -m venv venv`
4. Activate it:
   `.env\Scripts\Activate.ps1`
   If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and activate again.
5. Install dependencies:
   `pip install -r requirements.txt`
6. Start the app:
   `python app.py`
7. Open `http://127.0.0.1:5000` in your browser.

## Test a suspected leak
On the dashboard, enter an example such as:
- Flow rate: `18`
- Pressure: `1.8`
- Tank level: `60`

Then click **Analyse reading**. The dashboard should show a possible issue. Try tank level `98` with flow `13` to test the high-flow / nearly-full-tank rule.

## Important limitations
- This is a demonstration using simulated readings, not a validated production leak detector.
- Isolation Forest identifies unusual patterns; it does not prove a leak or provide a calibrated probability of future failure.
- The rules and thresholds are illustrative and must be calibrated for each pipeline using real sensor readings.
- Excess-water estimates assume a baseline of 8 L/min and one hour per flagged record; they are illustrative only.
- Real-time IoT sensor integration, notification delivery, multi-building support, and field validation are future extensions.
- Do not claim measured water savings, field testing, or a particular model accuracy until these have actually been measured.

## Suggested hackathon demonstration
1. Show the dashboard with sample data.
2. Explain flow, pressure, and tank level.
3. Add a high-flow / low-pressure reading and show the alert.
4. Add a high-flow / nearly-full-tank reading to demonstrate an overflow warning.
5. Explain the limitations and how real flow / tank sensors could be connected in a future pilot.
