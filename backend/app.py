from flask import Flask, request, jsonify, render_template_string
from datetime import datetime
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ml_model.anomaly_detector import WaterAnomalyDetector

app = Flask(__name__)
detector = WaterAnomalyDetector()

telemetry_history = []
last_tank_reading = None
last_reading_time = None

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>AQUA-INTEL Live Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }
    .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 15px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 15px; margin: 20px 0; }
    .card { background: #1e293b; border-radius: 8px; padding: 18px; text-align: center; border: 1px solid #334155; }
    .card h3 { margin: 0; font-size: 14px; color: #94a3b8; }
    .card p { margin: 10px 0 0 0; font-size: 26px; font-weight: bold; color: #38bdf8; }
    .status-ok { color: #4ade80 !important; }
    .status-alert { color: #f87171 !important; }
    .chart-container { background: #1e293b; border-radius: 8px; padding: 20px; border: 1px solid #334155; }
  </style>
</head>
<body>
  <div class="header">
    <h2>AQUA-INTEL: Live Water Intelligence</h2>
    <span>Team ImpactX | ESP32 Node 01</span>
  </div>
  <div class="grid">
    <div class="card"><h3>INLET FLOW</h3><p id="inlet">0.0 L/min</p></div>
    <div class="card"><h3>OUTLET FLOW</h3><p id="outlet">0.0 L/min</p></div>
    <div class="card"><h3>LINE PRESSURE</h3><p id="pressure">0.0 kPa</p></div>
    <div class="card"><h3>DIAGNOSIS</h3><p id="status" class="status-ok">MONITORING</p></div>
  </div>
  <div class="chart-container">
    <canvas id="flowChart" height="90"></canvas>
  </div>
  <script>
    const ctx = document.getElementById('flowChart').getContext('2d');
    const chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          { label: 'Inlet (L/min)', borderColor: '#38bdf8', data: [], tension: 0.3 },
          { label: 'Outlet (L/min)', borderColor: '#818cf8', data: [], tension: 0.3 }
        ]
      },
      options: { responsive: true, scales: { x: { grid: { color: '#334155' } }, y: { grid: { color: '#334155' } } } }
    });

    setInterval(async () => {
      try {
        const res = await fetch('/api/telemetry/latest');
        const data = await res.json();
        if (!data.timestamp) return;

        document.getElementById('inlet').innerText = data.flow_in + ' L/min';
        document.getElementById('outlet').innerText = data.flow_out + ' L/min';
        document.getElementById('pressure').innerText = data.pressure_kpa + ' kPa';
        
        const stEl = document.getElementById('status');
        stEl.innerText = data.diagnosis;
        stEl.className = data.is_anomaly ? 'status-alert' : 'status-ok';

        if (chart.data.labels.length > 20) {
          chart.data.labels.shift();
          chart.data.datasets[0].data.shift();
          chart.data.datasets[1].data.shift();
        }
        chart.data.labels.push(data.timestamp.split(' ')[1]);
        chart.data.datasets[0].data.push(data.flow_in);
        chart.data.datasets[1].data.push(data.flow_out);
        chart.update();
      } catch (err) {}
    }, 2000);
  </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    global last_tank_reading, last_reading_time
    data = request.get_json(force=True)
    now = datetime.now()

    q_in = float(data.get("flow_in", 0.0))
    q_out = float(data.get("flow_out", 0.0))
    pressure = float(data.get("pressure_kpa", 0.0))
    tank_cm = float(data.get("tank_distance_cm", -1.0))

    dh_dt = 0.0
    if last_tank_reading is not None and last_reading_time is not None:
        dt = (now - last_reading_time).total_seconds()
        if dt > 0:
            dh_dt = (tank_cm - last_tank_reading) / dt

    last_tank_reading = tank_cm
    last_reading_time = now

    is_anomaly, score, diagnosis = detector.predict(q_in, q_out, pressure, dh_dt)

    payload = {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "flow_in": q_in,
        "flow_out": q_out,
        "pressure_kpa": pressure,
        "is_anomaly": is_anomaly,
        "anomaly_score": score,
        "diagnosis": diagnosis,
        "emergency_cutoff": bool(is_anomaly and (q_in - q_out > 1.2))
    }

    telemetry_history.append(payload)
    if len(telemetry_history) > 100:
        telemetry_history.pop(0)

    return jsonify(payload)

@app.route('/api/telemetry/latest', methods=['GET'])
def get_latest():
    if not telemetry_history:
        return jsonify({})
    return jsonify(telemetry_history[-1])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)