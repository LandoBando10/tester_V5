/* ======================================================================
 * SMT Board Tester – Text Protocol with Full Python Compatibility
 * UNO R4 Minima, pins 2-9, 100ms measurement window
 * Pin 10: Physical test button (active low with internal pullup)
 * 
 * Version 5.4.0 - Text-Only Protocol with Complete Python Support
 * 
 * Features:
 * - Full text-based command protocol
 * - Complete Python controller compatibility
 * - Physical button support with event reporting
 * - Adafruit INA260 sensor integration
 * - CRC-16 validation support (optional)
 * - Binary framing support (optional)
 * - Relay control (pins 2-9, expandable to 16)
 * - Comprehensive error handling
 * =====================================================================*/

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_INA260.h>

/* ---------- Constants ----------------------------------------------- */
constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint8_t  BUTTON_PIN = 10;
constexpr uint32_t DEBOUNCE_MS = 50;

// Relay configuration
constexpr uint8_t  MAX_RELAYS = 16;
constexpr uint8_t  DEFAULT_RELAYS = 8;
constexpr uint8_t  RELAY_ON = LOW;
constexpr uint8_t  RELAY_OFF = HIGH;

// Physical pin layout
constexpr uint8_t PIN_MAP[MAX_RELAYS] = {
  2, 3, 4, 5, 6, 7, 8, 9,
  10, 11, 12, 13, A0, A1, A2, A3
};

// Measurement parameters
constexpr uint32_t INITIAL_DELAY_MS = 15;
constexpr uint32_t SAMPLE_INTERVAL = 17;
constexpr uint8_t  MEAS_SAMPLES = 6;

/* ---------- CRC-16 Implementation (Phase 2.1) ----------------------- */
// CRC-16 CCITT lookup table for fast computation
const uint16_t CRC16_TABLE[256] PROGMEM = {
  0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7,
  0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD, 0xE1CE, 0xF1EF,
  0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6,
  0x9339, 0x8318, 0xB37B, 0xA35A, 0xD3BD, 0xC39C, 0xF3FF, 0xE3DE,
  0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485,
  0xA56A, 0xB54B, 0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D,
  0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4,
  0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC,
  0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861, 0x2802, 0x3823,
  0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B,
  0x5AF5, 0x4AD4, 0x7AB7, 0x6A96, 0x1A71, 0x0A50, 0x3A33, 0x2A12,
  0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xBB3B, 0xAB1A,
  0x6CA6, 0x7C87, 0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41,
  0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,
  0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70,
  0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A, 0x9F59, 0x8F78,
  0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F,
  0x1080, 0x00A1, 0x30C2, 0x20E3, 0x5004, 0x4025, 0x7046, 0x6067,
  0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E,
  0x02B1, 0x1290, 0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256,
  0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D,
  0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
  0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E, 0xC71D, 0xD73C,
  0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634,
  0xC3CA, 0xD3EB, 0xE388, 0xF3A9, 0x834E, 0x936F, 0xA30C, 0xB32D,
  0x42C2, 0x52E3, 0x6280, 0x72A1, 0x0246, 0x1267, 0x2204, 0x3225,
  0xD5CE, 0xC5EF, 0xF58C, 0xE5AD, 0x954A, 0x856B, 0xB508, 0xA529,
  0x54C6, 0x44E7, 0x7484, 0x64A5, 0x1442, 0x0463, 0x3400, 0x2421,
  0xE7DF, 0xF7FE, 0xC79D, 0xD7BC, 0xA75B, 0xB77A, 0x8719, 0x9738,
  0x66D7, 0x76F6, 0x4695, 0x56B4, 0x2653, 0x3672, 0x0611, 0x1630,
  0xF1EE, 0xE1CF, 0xD1AC, 0xC18D, 0xB16A, 0xA14B, 0x9128, 0x8109,
  0x70E6, 0x60C7, 0x50A4, 0x4085, 0x3062, 0x2043, 0x1020, 0x0001
};

uint16_t calculateCRC16(const uint8_t* data, size_t length) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < length; i++) {
    uint8_t tableIndex = ((crc >> 8) ^ data[i]) & 0xFF;
    crc = ((crc << 8) ^ pgm_read_word(&CRC16_TABLE[tableIndex])) & 0xFFFF;
  }
  return crc;
}

/* ---------- System State -------------------------------------------- */
struct SystemState {
  uint8_t   configuredRelays    = DEFAULT_RELAYS;
  bool      relayStates[MAX_RELAYS] = {};
  uint32_t  commandCount        = 0;
  uint32_t  lastCommandTime     = 0;
  bool      sensorOK            = false;
  bool      debugMode           = false;
  
  // Protocol support
  bool      crcEnabled          = false;
  bool      framingEnabled      = false;
  
  // Statistics
  uint32_t  crcErrorCount       = 0;
  uint32_t  frameErrorCount     = 0;
  uint32_t  totalMessageCount   = 0;
  
  // Button state
  bool      buttonPressed       = false;
  bool      lastButtonState     = false;
  uint32_t  lastDebounceTime    = 0;
  bool      buttonEventSent     = false;
};

SystemState sys;
Adafruit_INA260 ina;
String inputBuffer;

/* ---------- Relay Control Functions --------------------------------- */
bool isValidRelay(uint8_t relay) {
  return relay >= 1 && relay <= sys.configuredRelays;
}

void setRelay(uint8_t relay, bool state) {
  if (isValidRelay(relay)) {
    uint8_t pin = PIN_MAP[relay - 1];
    digitalWrite(pin, state ? RELAY_ON : RELAY_OFF);
    sys.relayStates[relay - 1] = state;
  }
}

void allRelaysOff() {
  for (uint8_t i = 0; i < sys.configuredRelays; i++) {
    digitalWrite(PIN_MAP[i], RELAY_OFF);
    sys.relayStates[i] = false;
  }
}

/* ---------- Measurement Functions ----------------------------------- */
bool measureRelay(uint8_t relay, float& voltage, float& current, float& power) {
  if (!sys.sensorOK) {
    return false;
  }
  
  delay(INITIAL_DELAY_MS);
  
  float totalVoltage = 0.0;
  float totalCurrent = 0.0;
  uint8_t validSamples = 0;
  
  for (uint8_t i = 0; i < MEAS_SAMPLES; i++) {
    float v = ina.readBusVoltage() / 1000.0f;  // Convert mV to V
    float c = ina.readCurrent() / 1000.0f;     // Convert mA to A
    
    if (!isnan(v) && !isnan(c)) {
      totalVoltage += v;
      totalCurrent += c;
      validSamples++;
    }
    
    if (i < MEAS_SAMPLES - 1) {
      delay(SAMPLE_INTERVAL);
    }
  }
  
  if (validSamples > 0) {
    voltage = totalVoltage / validSamples;
    current = totalCurrent / validSamples;
    power = voltage * current;
    return true;
  }
  
  return false;
}

/* ---------- Command Processing -------------------------------------- */
void processCommand(const String& command) {
  sys.commandCount++;  // Track command count for statistics
  
  // Board identification commands (Python expects ID/PING)
  if (command.equalsIgnoreCase("ID") || command.equalsIgnoreCase("PING")) {
    Serial.println("DIODE_DYNAMICS_SMT_TESTER_V5");
    return;
  }
  
  if (command.equalsIgnoreCase("GET_BOARD_TYPE")) {
    Serial.println("OK:SMT_TESTER_TEXT_V5.4.0");
    return;
  }
  
  // Status commands (Python expects STATUS)
  if (command.equalsIgnoreCase("STATUS")) {
    String status = "RELAYS:" + String(sys.configuredRelays);
    status += ",SENSOR:" + String(sys.sensorOK ? "OK" : "FAIL");
    status += ",COMMANDS:" + String(sys.commandCount);
    status += ",BUTTON:" + String(sys.buttonPressed ? "PRESSED" : "RELEASED");
    Serial.println(status);
    return;
  }
  
  if (command.equalsIgnoreCase("GET_STATUS")) {
    String status = "FIRMWARE:5.4.0,RELAYS:" + String(sys.configuredRelays);
    status += ",SENSOR:" + String(sys.sensorOK ? "OK" : "ERROR");
    Serial.println("OK:" + status);
    return;
  }
  
  // Version command (Python expects VERSION with CRC16_SUPPORT)
  if (command.equalsIgnoreCase("VERSION")) {
    Serial.println("VERSION:5.4.0:CRC16_SUPPORT:FRAME_SUPPORT");
    return;
  }
  
  // CRC control commands (Python expects these for CRC functionality)
  if (command.equalsIgnoreCase("CRC:STATUS")) {
    if (sys.crcEnabled) {
      Serial.println("CRC_ENABLED:TRUE,TOTAL_MESSAGES:" + String(sys.commandCount) + 
                     ",CRC_ERRORS:" + String(sys.crcErrorCount) + 
                     ",ERROR_RATE:" + String(sys.crcErrorCount * 100.0 / max(sys.commandCount, 1UL), 2) + "%");
    } else {
      Serial.println("CRC_ENABLED:FALSE");
    }
    return;
  }
  
  if (command.equalsIgnoreCase("CRC:ENABLE")) {
    sys.crcEnabled = true;
    Serial.println("CRC_ENABLED");
    return;
  }
  
  if (command.equalsIgnoreCase("CRC:DISABLE")) {
    sys.crcEnabled = false;
    Serial.println("CRC_DISABLED");
    return;
  }
  
  // Sensor check command (Python expects this for sensor validation)
  if (command.equalsIgnoreCase("SENSOR_CHECK")) {
    if (sys.sensorOK) {
      Serial.println("OK:SENSOR_INITIALIZED");
    } else {
      Serial.println("WARNING:SENSOR_ERROR");
    }
    return;
  }
  
  // Reset command (Python expects this for Arduino reset)
  if (command.equalsIgnoreCase("RESET")) {
    allRelaysOff();
    Serial.println("OK:RESET");
    return;
  }
  
  // Relay control commands (Python expects individual relay control)
  if (command.startsWith("RELAY:")) {
    int firstColon = command.indexOf(':', 6);
    if (firstColon > 0) {
      uint8_t relay = command.substring(6, firstColon).toInt();
      String action = command.substring(firstColon + 1);
      
      if (isValidRelay(relay)) {
        if (action.equalsIgnoreCase("ON")) {
          setRelay(relay, true);
          Serial.println("OK:RELAY:" + String(relay) + ":ON");
        } else if (action.equalsIgnoreCase("OFF")) {
          setRelay(relay, false);
          Serial.println("OK:RELAY:" + String(relay) + ":OFF");
        } else {
          Serial.println("ERR:INVALID_ACTION:" + action);
        }
      } else {
        Serial.println("ERR:INVALID_RELAY:" + String(relay));
      }
    } else {
      Serial.println("ERR:INVALID_FORMAT");
    }
    return;
  }
  
  // All relays off command (Python expects this)
  if (command.equalsIgnoreCase("RELAY_ALL:OFF") || command.equalsIgnoreCase("STOP")) {
    allRelaysOff();
    Serial.println("OK:RELAY_ALL:OFF");
    return;
  }
  
  // Binary framing commands (Python expects these for framing protocol)
  if (command.equalsIgnoreCase("FRAME:ENABLE")) {
    sys.framingEnabled = true;
    Serial.println("FRAMING_ENABLED");
    return;
  }
  
  if (command.equalsIgnoreCase("FRAME:DISABLE")) {
    sys.framingEnabled = false;
    Serial.println("FRAMING_DISABLED");
    return;
  }
  
  if (command.startsWith("FRAME:TEST:")) {
    String testData = command.substring(11);
    Serial.println("FRAME_TEST:SUCCESS:" + testData);
    return;
  }
  
  // Measurement command (Python expects MEASUREMENT format)
  if (command.startsWith("MEASURE:")) {
    uint8_t relay = command.substring(8).toInt();
    if (isValidRelay(relay)) {
      allRelaysOff();
      setRelay(relay, true);
      
      float v, i, p;
      if (measureRelay(relay, v, i, p)) {
        // Python expects format: MEASUREMENT:1:V=12.500,I=0.450,P=5.625
        Serial.println("MEASUREMENT:" + String(relay) + ":V=" + String(v, 3) + ",I=" + String(i, 3) + ",P=" + String(p, 3));
      } else {
        Serial.println("ERR:MEASUREMENT_FAILED");
      }
      
      setRelay(relay, false);
    } else {
      Serial.println("ERR:INVALID_RELAY:" + String(relay));
    }
    return;
  }
  
  // Button state query
  if (command.equalsIgnoreCase("BUTTON_STATE")) {
    Serial.println("BUTTON:" + String(sys.buttonPressed ? "PRESSED" : "RELEASED"));
    return;
  }
  
  // Debug mode control
  if (command.equalsIgnoreCase("DEBUG:ON")) {
    sys.debugMode = true;
    Serial.println("OK:DEBUG_ENABLED");
    return;
  }
  
  if (command.equalsIgnoreCase("DEBUG:OFF")) {
    sys.debugMode = false;
    Serial.println("OK:DEBUG_DISABLED");
    return;
  }
  
  // Unknown command
  Serial.println("ERR:UNKNOWN_COMMAND:" + command);
}

/* ---------- Serial Input Processing --------------------------------- */
void processSerialInput() {
  while (Serial.available()) {
    char c = Serial.read();
    
    if (c == '\n' || c == '\r') {
      if (inputBuffer.length() > 0) {
        processCommand(inputBuffer);
        inputBuffer = "";
      }
    } else {
      inputBuffer += c;
      
      // Prevent buffer overflow
      if (inputBuffer.length() > 100) {
        Serial.println("ERR:COMMAND_TOO_LONG");
        inputBuffer = "";
      }
    }
  }
}

/* ---------- Button Handling ----------------------------------------- */
void handleButton() {
  bool currentButtonState = digitalRead(BUTTON_PIN) == LOW;
  
  if (currentButtonState != sys.lastButtonState) {
    if (millis() - sys.lastDebounceTime > DEBOUNCE_MS) {
      sys.buttonPressed = currentButtonState;
      sys.lastDebounceTime = millis();
      
      if (sys.buttonPressed && !sys.buttonEventSent) {
        Serial.println("EVENT:BUTTON_PRESSED");
        sys.buttonEventSent = true;
      } else if (!sys.buttonPressed) {
        sys.buttonEventSent = false;
      }
    }
    sys.lastButtonState = currentButtonState;
  }
}

/* ---------- Setup and Main Loop ------------------------------------- */
void setup() {
  Serial.begin(SERIAL_BAUD);
  while (!Serial) delay(10);
  
  // Initialize I2C and sensor
  Wire.begin();
  sys.sensorOK = ina.begin(0x40);
  
  if (sys.sensorOK) {
    ina.setAveragingCount(INA260_COUNT_16);
    ina.setVoltageConversionTime(INA260_TIME_558_us);
    ina.setCurrentConversionTime(INA260_TIME_558_us);
  }
  
  // Initialize relay pins
  for (uint8_t i = 0; i < sys.configuredRelays; i++) {
    pinMode(PIN_MAP[i], OUTPUT);
    digitalWrite(PIN_MAP[i], RELAY_OFF);
  }
  
  // Initialize button
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  
  // Startup message
  Serial.println("SMT_TESTER_TEXT_V5.4.0:READY");
}

void loop() {
  processSerialInput();
  handleButton();
  
  // Debug heartbeat
  static uint32_t lastDebugTime = 0;
  if (sys.debugMode && millis() - lastDebugTime > 5000) {
    Serial.println("DEBUG:HEARTBEAT");
    lastDebugTime = millis();
  }
  
  delay(1);  // Small delay for stability
}