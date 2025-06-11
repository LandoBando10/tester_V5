/* ======================================================================
 * SMT Board Tester – Enhanced Version
 * UNO R4 Minima, pins 2-9, 100ms measurement window
 * 
 * Improvements:
 * - Better error handling and validation
 * - Enhanced status reporting
 * - Clearer response formats
 * - Improved robustness
 * =====================================================================*/

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_INA260.h>

/* ---------- User-tunable constants ----------------------------------- */
constexpr uint32_t SERIAL_BAUD      = 115200;
constexpr uint8_t  MAX_RELAYS       = 16;
constexpr uint8_t  DEFAULT_RELAYS   = 8;        // Default to 8 relays
constexpr uint8_t  RELAY_ON         = LOW;      // Active-low relay modules
constexpr uint8_t  RELAY_OFF        = HIGH;
constexpr uint8_t  MEAS_SAMPLES     = 5;        // Number of INA260 samples
constexpr uint16_t MEAS_WINDOW_MS   = 100;     // Total measurement window
constexpr uint16_t INITIAL_DELAY_MS = 15;      // Initial stabilization
constexpr uint16_t SAMPLE_INTERVAL  = 17;      // Between samples

/* ---------- Physical pin layout -------------------------------------- */
constexpr uint8_t PIN_MAP[MAX_RELAYS] = {
  2, 3, 4, 5, 6, 7, 8, 9,          // Relays 1-8
  10, 11, 12, 13, A0, A1, A2, A3   // Relays 9-16 (future expansion)
};

/* ---------- Type definitions ----------------------------------------- */
enum class ResponseType {
  OK,
  ERROR,
  WARNING,
  INFO,
  DATA
};

struct SystemState {
  uint8_t   configuredRelays    = DEFAULT_RELAYS;
  bool      relayStates[MAX_RELAYS] = {};
  uint32_t  commandCount        = 0;
  uint32_t  lastCommandTime     = 0;
  bool      sensorOK            = false;
  bool      debugMode           = false;
};

/* ---------- Globals -------------------------------------------------- */
SystemState   sys;
Adafruit_INA260 ina;
String        inputBuffer;

/* ---------- Response formatting -------------------------------------- */
void sendResponse(ResponseType type, const String& message) {
  switch(type) {
    case ResponseType::OK:      Serial.print("OK:"); break;
    case ResponseType::ERROR:   Serial.print("ERROR:"); break;
    case ResponseType::WARNING: Serial.print("WARNING:"); break;
    case ResponseType::INFO:    Serial.print("INFO:"); break;
    case ResponseType::DATA:    Serial.print("DATA:"); break;
  }
  Serial.println(message);
}

void sendFormattedData(const String& prefix, const String& data) {
  Serial.print(prefix);
  Serial.print(":");
  Serial.println(data);
}

/* ---------- Relay control -------------------------------------------- */
bool isValidRelay(uint8_t relay) {
  return relay >= 1 && relay <= sys.configuredRelays;
}

void setRelay(uint8_t relay, bool state) {
  if (!isValidRelay(relay)) {
    sendResponse(ResponseType::ERROR, "INVALID_RELAY:" + String(relay));
    return;
  }
  
  uint8_t idx = relay - 1;
  uint8_t pin = PIN_MAP[idx];
  
  sys.relayStates[idx] = state;
  digitalWrite(pin, state ? RELAY_ON : RELAY_OFF);
  
  if (sys.debugMode) {
    sendResponse(ResponseType::INFO, 
      "RELAY_SET:" + String(relay) + ":" + (state ? "ON" : "OFF"));
  }
}

void allRelaysOff() {
  for (uint8_t i = 1; i <= sys.configuredRelays; i++) {
    setRelay(i, false);
  }
}

/* ---------- INA260 measurement --------------------------------------- */
bool initializeSensor() {
  Wire.begin();
  Wire.setClock(400000);  // 400kHz I2C
  
  sys.sensorOK = ina.begin();
  
  if (!sys.sensorOK) {
    sendResponse(ResponseType::ERROR, "INA260_NOT_FOUND");
    return false;
  }
  
  // Configure for fast, accurate measurements
  #if defined(INA260_TIME_1100_us)
    ina.setCurrentConversionTime(INA260_TIME_1100_us);
    ina.setVoltageConversionTime(INA260_TIME_1100_us);
  #else
    ina.setCurrentConversionTime(INA260_TIME_1_1_ms);
    ina.setVoltageConversionTime(INA260_TIME_1_1_ms);
  #endif
  
  ina.setAveragingCount(INA260_COUNT_4);
  ina.setMode(INA260_MODE_CONTINUOUS);
  
  sendResponse(ResponseType::OK, "INA260_INITIALIZED");
  return true;
}

bool measureRelay(uint8_t relay, float& voltage, float& current, float& power) {
  if (!sys.sensorOK) {
    sendResponse(ResponseType::ERROR, "SENSOR_NOT_READY");
    return false;
  }
  
  // Initial stabilization
  delay(INITIAL_DELAY_MS);
  
  float sumV = 0, sumI = 0, sumP = 0;
  uint8_t validSamples = 0;
  
  // Take measurements at specific intervals
  for (uint8_t i = 0; i < MEAS_SAMPLES; i++) {
    float v = ina.readBusVoltage() / 1000.0f;
    float c = ina.readCurrent() / 1000.0f;
    float p = ina.readPower() / 1000.0f;
    
    if (!isnan(v) && !isnan(c) && !isnan(p)) {
      sumV += v;
      sumI += c;
      sumP += p;
      validSamples++;
    }
    
    // Delay between samples (except after last)
    if (i < MEAS_SAMPLES - 1) {
      delay(SAMPLE_INTERVAL);
    }
  }
  
  // Complete the measurement window
  delay(SAMPLE_INTERVAL);
  
  if (validSamples == 0) {
    sendResponse(ResponseType::ERROR, "NO_VALID_MEASUREMENTS");
    return false;
  }
  
  voltage = sumV / validSamples;
  current = sumI / validSamples;
  power = sumP / validSamples;
  
  return true;
}

/* ---------- Command parsing ------------------------------------------ */
void parseRelayList(const String& list, bool state) {
  int start = 0;
  int comma = list.indexOf(',');
  
  while (comma != -1) {
    String relayStr = list.substring(start, comma);
    relayStr.trim();
    if (relayStr.length() > 0) {
      uint8_t relay = relayStr.toInt();
      if (isValidRelay(relay)) {
        setRelay(relay, state);
      }
    }
    start = comma + 1;
    comma = list.indexOf(',', start);
  }
  
  // Handle last relay
  String relayStr = list.substring(start);
  relayStr.trim();
  if (relayStr.length() > 0) {
    uint8_t relay = relayStr.toInt();
    if (isValidRelay(relay)) {
      setRelay(relay, state);
    }
  }
}

void handleCommand(const String& cmd) {
  sys.commandCount++;
  sys.lastCommandTime = millis();
  
  // Trim and convert to uppercase for consistent parsing
  String command = cmd;
  command.trim();
  
  // System commands
  if (command.equalsIgnoreCase("ID") || command.equalsIgnoreCase("PING")) {
    sendResponse(ResponseType::OK, "DIODE_DYNAMICS_SMT_TESTER_V5");
    return;
  }
  
  if (command.equalsIgnoreCase("VERSION")) {
    sendResponse(ResponseType::OK, "VERSION:5.0.0");
    return;
  }
  
  if (command.equalsIgnoreCase("STATUS")) {
    String status = "RELAYS:" + String(sys.configuredRelays);
    status += ",SENSOR:" + String(sys.sensorOK ? "OK" : "FAIL");
    status += ",COMMANDS:" + String(sys.commandCount);
    status += ",STATE:";
    for (uint8_t i = 0; i < sys.configuredRelays; i++) {
      status += sys.relayStates[i] ? '1' : '0';
    }
    sendResponse(ResponseType::DATA, status);
    return;
  }
  
  if (command.equalsIgnoreCase("STOP") || command.equalsIgnoreCase("RELAY_ALL:OFF")) {
    allRelaysOff();
    sendResponse(ResponseType::OK, "ALL_RELAYS_OFF");
    return;
  }
  
  // Debug mode
  if (command.equalsIgnoreCase("DEBUG:ON")) {
    sys.debugMode = true;
    sendResponse(ResponseType::OK, "DEBUG_ENABLED");
    return;
  }
  
  if (command.equalsIgnoreCase("DEBUG:OFF")) {
    sys.debugMode = false;
    sendResponse(ResponseType::OK, "DEBUG_DISABLED");
    return;
  }
  
  // Configuration
  if (command.startsWith("CONFIG:CHANNELS:")) {
    uint8_t channels = command.substring(16).toInt();
    if (channels >= 1 && channels <= MAX_RELAYS) {
      sys.configuredRelays = channels;
      // Re-initialize pins
      for (uint8_t i = 0; i < MAX_RELAYS; i++) {
        if (i < sys.configuredRelays) {
          pinMode(PIN_MAP[i], OUTPUT);
          digitalWrite(PIN_MAP[i], RELAY_OFF);
        }
      }
      sendResponse(ResponseType::OK, "CHANNELS:" + String(sys.configuredRelays));
    } else {
      sendResponse(ResponseType::ERROR, "INVALID_CHANNEL_COUNT:" + String(channels));
    }
    return;
  }
  
  // Single relay control
  if (command.startsWith("RELAY:")) {
    int colon1 = 6;
    int colon2 = command.indexOf(':', colon1);
    if (colon2 > colon1) {
      uint8_t relay = command.substring(colon1, colon2).toInt();
      String state = command.substring(colon2 + 1);
      state.toUpperCase();
      
      if (isValidRelay(relay)) {
        bool on = (state == "ON");
        setRelay(relay, on);
        sendResponse(ResponseType::OK, "RELAY:" + String(relay) + ":" + state);
      } else {
        sendResponse(ResponseType::ERROR, "INVALID_RELAY:" + String(relay));
      }
    }
    return;
  }
  
  // Group relay control
  if (command.startsWith("RELAY_GROUP:")) {
    int colon1 = 12;
    int colon2 = command.lastIndexOf(':');
    if (colon2 > colon1) {
      String relayList = command.substring(colon1, colon2);
      String state = command.substring(colon2 + 1);
      state.toUpperCase();
      
      bool on = (state == "ON");
      parseRelayList(relayList, on);
      sendResponse(ResponseType::OK, "RELAY_GROUP:" + relayList + ":" + state);
    }
    return;
  }
  
  // Measurement commands
  if (command.equalsIgnoreCase("MEASURE")) {
    float v, i, p;
    if (measureRelay(0, v, i, p)) {  // Measure without changing relays
      sendFormattedData("MEASUREMENT", 
        "V=" + String(v, 3) + ",I=" + String(i, 3) + ",P=" + String(p, 3));
    }
    return;
  }
  
  if (command.startsWith("MEASURE:")) {
    uint8_t relay = command.substring(8).toInt();
    if (isValidRelay(relay)) {
      allRelaysOff();
      setRelay(relay, true);
      
      float v, i, p;
      if (measureRelay(relay, v, i, p)) {
        sendFormattedData("MEASUREMENT:" + String(relay),
          "V=" + String(v, 3) + ",I=" + String(i, 3) + ",P=" + String(p, 3));
      }
      
      setRelay(relay, false);
    } else {
      sendResponse(ResponseType::ERROR, "INVALID_RELAY:" + String(relay));
    }
    return;
  }
  
  if (command.startsWith("MEASURE_GROUP:")) {
    String relayList = command.substring(14);
    sendResponse(ResponseType::INFO, "MEASURE_GROUP:START");
    
    // Parse relay list and measure each
    int start = 0;
    int comma = relayList.indexOf(',');
    uint8_t measureCount = 0;
    
    while (true) {
      String relayStr;
      if (comma != -1) {
        relayStr = relayList.substring(start, comma);
      } else {
        relayStr = relayList.substring(start);
      }
      
      relayStr.trim();
      if (relayStr.length() > 0) {
        uint8_t relay = relayStr.toInt();
        if (isValidRelay(relay)) {
          allRelaysOff();
          setRelay(relay, true);
          
          float v, i, p;
          if (measureRelay(relay, v, i, p)) {
            sendFormattedData("MEASUREMENT:" + String(relay),
              "V=" + String(v, 3) + ",I=" + String(i, 3) + ",P=" + String(p, 3));
            measureCount++;
          }
          
          setRelay(relay, false);
        }
      }
      
      if (comma == -1) break;
      start = comma + 1;
      comma = relayList.indexOf(',', start);
    }
    
    allRelaysOff();
    sendResponse(ResponseType::OK, "MEASURE_GROUP:COMPLETE:" + String(measureCount));
    return;
  }
  
  // Sensor check
  if (command.equalsIgnoreCase("SENSOR_CHECK")) {
    if (sys.sensorOK) {
      // Try a test measurement
      float v = ina.readBusVoltage() / 1000.0f;
      if (!isnan(v)) {
        sendResponse(ResponseType::OK, "SENSOR:INA260:VOLTAGE:" + String(v, 3));
      } else {
        sendResponse(ResponseType::WARNING, "SENSOR:INA260:NO_READING");
      }
    } else {
      sendResponse(ResponseType::ERROR, "SENSOR:INA260:NOT_FOUND");
    }
    return;
  }
  
  // Unknown command
  sendResponse(ResponseType::ERROR, "UNKNOWN_COMMAND:" + command);
}

/* ---------- Serial communication ------------------------------------- */
void processSerialInput() {
  while (Serial.available()) {
    char c = Serial.read();
    
    if (c == '\n' || c == '\r') {
      if (inputBuffer.length() > 0) {
        handleCommand(inputBuffer);
        inputBuffer = "";
      }
    } else if (inputBuffer.length() < 120) {
      inputBuffer += c;
    }
  }
}

/* ---------- Arduino setup/loop --------------------------------------- */
void setup() {
  Serial.begin(SERIAL_BAUD);
  while (!Serial && millis() < 3000) ; // Wait for serial
  
  // Initialize pins
  for (uint8_t i = 0; i < sys.configuredRelays; i++) {
    pinMode(PIN_MAP[i], OUTPUT);
    digitalWrite(PIN_MAP[i], RELAY_OFF);
  }
  
  // Initialize sensor
  initializeSensor();
  
  // Startup message
  Serial.println("=== Diode Dynamics SMT Board Tester V5 ===");
  Serial.println("Firmware: Enhanced Version 5.0.0");
  Serial.print("Configured relays: ");
  Serial.println(sys.configuredRelays);
  Serial.print("INA260 sensor: ");
  Serial.println(sys.sensorOK ? "OK" : "NOT FOUND");
  Serial.println("Ready for commands");
  Serial.println();
}

void loop() {
  processSerialInput();
  
  // Add watchdog or heartbeat if needed
  static uint32_t lastHeartbeat = 0;
  if (sys.debugMode && millis() - lastHeartbeat > 10000) {
    sendResponse(ResponseType::INFO, "HEARTBEAT");
    lastHeartbeat = millis();
  }
}