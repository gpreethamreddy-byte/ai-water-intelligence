# AI-Powered Water Intelligence and Leak Prediction System

Smart water resource management and predictive leak detection system developed by **Team ImpactX** for the **Seva First Innovation Challenge 2026** under the theme **Swachh & Sustainable Bharat**.

## 📌 Features
- **Differential Flow Balance:** Uses dual YF-S201 flow sensors to compute liquid loss ($Q_{in} - Q_{out}$) in real time.
- **Unsupervised Anomaly Detection:** Isolation Forest machine learning model dynamically filters out morning consumption surges and flags true pipeline ruptures.
- **Live Web Dashboard:** Chart.js streaming interface displaying flow rates, line pressure, and diagnostic state.
- **Automated Cut-Off Guardrail:** Sends instant shut-off signals to an edge relay valve during verified pipeline breaks.

## 🛠️ Project Structure
```text
├── backend/
│   └── app.py                  # Flask REST API & Web Dashboard
├── firmware/
│   └── esp32_water_node.ino    # ESP32 FreeRTOS Interrupt Telemetry
├── ml_model/
│   └── anomaly_detector.py     # Isolation Forest Anomaly Detection Engine
├── requirements.txt
└── README.md