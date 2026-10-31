#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* serverUrl = "http://YOUR_LOCAL_IP:5000/api/telemetry";

#define FLOW_IN_PIN   18
#define FLOW_OUT_PIN  19
#define PRESSURE_PIN  34
#define TRIG_PIN      5
#define ECHO_PIN      17
#define RELAY_PIN     23

volatile unsigned long pulseInCount = 0;
volatile unsigned long pulseOutCount = 0;

void IRAM_ATTR onPulseIn() { pulseInCount++; }
void IRAM_ATTR onPulseOut() { pulseOutCount++; }

unsigned long lastTime = 0;

void setup() {
  Serial.begin(115200);
  pinMode(FLOW_IN_PIN, INPUT_PULLUP);
  pinMode(FLOW_OUT_PIN, INPUT_PULLUP);
  pinMode(PRESSURE_PIN, INPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, HIGH);

  attachInterrupt(digitalPinToInterrupt(FLOW_IN_PIN), onPulseIn, FALLING);
  attachInterrupt(digitalPinToInterrupt(FLOW_OUT_PIN), onPulseOut, FALLING);

  WiFi.begin(ssid, password);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected!");
}

float getTankDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long dur = pulseIn(ECHO_PIN, HIGH, 25000);
  if (dur == 0) return -1.0;
  return (dur * 0.0343) / 2.0;
}

void loop() {
  if (millis() - lastTime >= 2000) {
    float dt = (millis() - lastTime) / 1000.0;
    lastTime = millis();

    noInterrupts();
    unsigned long countIn = pulseInCount;
    unsigned long countOut = pulseOutCount;
    pulseInCount = 0;
    pulseOutCount = 0;
    interrupts();

    float flowIn = (countIn / (7.5 * dt));
    float flowOut = (countOut / (7.5 * dt));

    int rawPres = analogRead(PRESSURE_PIN);
    float volt = (rawPres / 4095.0) * 3.3;
    float pressureKpa = (volt >= 0.5) ? ((volt - 0.5) / 2.0) * 1200.0 : 0.0;

    float tankDist = getTankDistanceCm();

    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(serverUrl);
      http.addHeader("Content-Type", "application/json");

      StaticJsonDocument<256> doc;
      doc["flow_in"] = flowIn;
      doc["flow_out"] = flowOut;
      doc["pressure_kpa"] = pressureKpa;
      doc["tank_distance_cm"] = tankDist;

      String json;
      serializeJson(doc, json);
      int code = http.POST(json);

      if (code > 0) {
        String res = http.getString();
        StaticJsonDocument<128> resDoc;
        deserializeJson(resDoc, res);
        if (resDoc["emergency_cutoff"] == true) {
          digitalWrite(RELAY_PIN, LOW);
          Serial.println("EMERGENCY CUTOFF ACTIVATED");
        }
      }
      http.end();
    }
  }
}