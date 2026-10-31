import time
import requests
import random

SERVER_URL = "http://localhost:5000/api/telemetry"

print("Starting Water Telemetry Simulation... Press Ctrl+C to stop.")
step = 0

while True:
    step += 1
    # First 6 cycles: Normal flow; Cycle 7+: Simulated pipe rupture / leak
    if step < 7:
        flow_in = round(random.uniform(5.0, 8.0), 2)
        flow_out = round(flow_in - random.uniform(0.05, 0.15), 2)
        pressure = round(random.uniform(280.0, 310.0), 1)
        tank_dist = round(30.0 + (step * 0.2), 1)
        state = "NORMAL FLOW"
    else:
        flow_in = round(random.uniform(9.0, 12.0), 2)
        flow_out = round(random.uniform(3.0, 4.5), 2)  # Significant loss
        pressure = round(random.uniform(140.0, 180.0), 1)  # Depressurization
        tank_dist = round(32.0 + (step * 1.5), 1)  # Rapid drain
        state = "LEAK / PIPE RUPTURE"

    payload = {
        "flow_in": flow_in,
        "flow_out": flow_out,
        "pressure_kpa": pressure,
        "tank_distance_cm": tank_dist
    }

    try:
        res = requests.post(SERVER_URL, json=payload, timeout=2)
        data = res.json()
        print(f"[{state}] Sent: {payload} | Status: {data.get('diagnosis')}")
    except Exception as e:
        print(f"Server offline or unreachable: {e}")

    time.sleep(2)