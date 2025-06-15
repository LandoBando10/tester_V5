/* ======================================================================
 * SMT Board Tester – Enhanced Version with Physical Button Support + Binary Framing
 * UNO R4 Minima, pins 2-9, 100ms measurement window
 * Pin 10: Physical test button (active low with internal pullup)
 * 
 * Version 5.2.0 - Phase 3 Binary Framing Protocol Implementation
 * 
 * Improvements:
 * - Physical button support on pin 10
 * - Button debouncing and state reporting
 * - Better error handling and validation
 * - Enhanced status reporting
 * - Clearer response formats
 * - CRC-16 validation for message integrity (Phase 2.1)
 * - Binary framing protocol with STX/ETX markers (Phase 3)
 * - Automatic protocol detection and dual-mode support
 * - Improved robustness
 * =====================================================================*/

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_INA260.h>

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
  0xD94C, 0xC96D, 0xF90E, 0xE92F, 0x99C8, 0x89E9, 0xB98A, 0xA9AB,
  0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3,
  0xCB7D, 0xDB5C, 0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A,
  0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,
  0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9,
  0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83, 0x1CE0, 0x0CC1,
  0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8,
  0x6E17, 0x7E36, 0x4E55, 0x5E74, 0x2E93, 0x3EB2, 0x0ED1, 0x1EF0
};

uint16_t calculateCRC16(const char* data, uint16_t length) {
  uint16_t crc = 0xFFFF;  // Initial value
  
  for (uint16_t i = 0; i < length; i++) {
    uint8_t tableIndex = ((crc >> 8) ^ data[i]) & 0xFF;
    crc = ((crc << 8) ^ pgm_read_word(&CRC16_TABLE[tableIndex])) & 0xFFFF;
  }
  
  return crc;
}

uint16_t calculateCRC16(const String& str) {
  return calculateCRC16(str.c_str(), str.length());
}

String formatCRC16(uint16_t crc) {
  char buffer[5];
  sprintf(buffer, "%04X", crc);
  return String(buffer);
}

bool verifyCRC(const String& message) {
  int asteriskPos = message.lastIndexOf('*');
  if (asteriskPos == -1 || asteriskPos + 5 != message.length()) {
    return false;  // No CRC or wrong format
  }
  
  String data = message.substring(0, asteriskPos);
  String crcStr = message.substring(asteriskPos + 1);
  
  uint16_t expectedCRC = strtoul(crcStr.c_str(), NULL, 16);
  uint16_t calculatedCRC = calculateCRC16(data);
  
  return expectedCRC == calculatedCRC;
}

String extractMessage(const String& messageWithCRC) {
  int asteriskPos = messageWithCRC.lastIndexOf('*');
  if (asteriskPos == -1) {
    return messageWithCRC;  // No CRC
  }
  return messageWithCRC.substring(0, asteriskPos);
}

/* ---------- Binary Framing Protocol (Phase 3) ----------------------- */
// Frame format: <STX>LLL:TYPE:PAYLOAD<ETX>CCCC
constexpr uint8_t STX = 0x02;
constexpr uint8_t ETX = 0x03;
constexpr uint8_t ESC = 0x1B;
constexpr uint16_t MAX_FRAME_SIZE = 512;
constexpr uint16_t FRAME_TIMEOUT_MS = 5000;

enum class FrameState {
  IDLE,
  LENGTH,
  TYPE,
  PAYLOAD,
  CRC
};

struct FrameParser {
  FrameState state = FrameState::IDLE;
  String buffer = "";
  uint16_t expectedLength = 0;
  String frameType = "";
  String framePayload = "";
  uint32_t frameStartTime = 0;
  bool escapeNext = false;
  
  void reset() {
    state = FrameState::IDLE;
    buffer = "";
    expectedLength = 0;
    frameType = "";
    framePayload = "";
    frameStartTime = 0;
    escapeNext = false;
  }
  
  bool isTimedOut() {
    return (state != FrameState::IDLE) && 
           (millis() - frameStartTime > FRAME_TIMEOUT_MS);
  }
};

String encodeFrame(const String& type, const String& payload) {
  if (type.length() != 3) {
    return "";  // Invalid type length
  }
  
  // Escape special characters in payload
  String escapedPayload = "";
  for (size_t i = 0; i < payload.length(); i++) {
    char c = payload.charAt(i);
    if (c == STX || c == ETX || c == ESC) {
      escapedPayload += char(ESC);
      escapedPayload += char(c ^ 0x20);  // XOR with 0x20 for escaping
    } else {
      escapedPayload += c;
    }
  }
  
  String content = type + ":" + escapedPayload;
  if (content.length() > 999) {
    return "";  // Content too large
  }
  
  String lengthStr = String(content.length());
  while (lengthStr.length() < 3) {
    lengthStr = "0" + lengthStr;  // Zero-pad to 3 digits
  }
  
  String frameContent = lengthStr + ":" + content;
  uint16_t crc = calculateCRC16(frameContent);
  String crcStr = formatCRC16(crc);
  
  String frame = "";
  frame += char(STX);
  frame += frameContent;
  frame += char(ETX);
  frame += crcStr;
  
  return frame;
}

String unescapePayload(const String& escapedPayload) {
  String result = "";
  bool escapeNext = false;
  
  for (size_t i = 0; i < escapedPayload.length(); i++) {
    char c = escapedPayload.charAt(i);
    if (escapeNext) {
      result += char(c ^ 0x20);  // Unescape character
      escapeNext = false;
    } else if (c == ESC) {
      escapeNext = true;
    } else {
      result += c;
    }
  }
  
  return result;
}

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

/* ---------- Button constants ----------------------------------------- */
constexpr uint8_t  BUTTON_PIN       = 10;       // Physical test button
constexpr uint32_t DEBOUNCE_MS      = 50;       // Button debounce time

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
  
  // Button state
  bool      buttonPressed       = false;
  bool      lastButtonState     = false;
  uint32_t  lastDebounceTime    = 0;
  bool      buttonEventSent     = false;
  
  // CRC-16 support (Phase 2.1)
  bool      crcEnabled          = false;
  uint32_t  crcErrorCount       = 0;
  uint32_t  totalMessageCount   = 0;
  
  // Binary framing support (Phase 3)
  bool      framingEnabled      = false;
  uint32_t  frameErrorCount     = 0;
  uint32_t  totalFrameCount     = 0;
};

/* ---------- Globals -------------------------------------------------- */
SystemState   sys;
Adafruit_INA260 ina;
String        inputBuffer;
FrameParser   frameParser;

/* ---------- Response formatting with dual protocol support --------- */
void sendResponse(ResponseType type, const String& message) {
  String typePrefix;
  switch(type) {
    case ResponseType::OK:      typePrefix = "OK"; break;
    case ResponseType::ERROR:   typePrefix = "ERR"; break;
    case ResponseType::WARNING: typePrefix = "WRN"; break;
    case ResponseType::INFO:    typePrefix = "INF"; break;
    case ResponseType::DATA:    typePrefix = "DAT"; break;
  }
  
  if (sys.framingEnabled) {
    // Send as framed binary protocol
    String frame = encodeFrame(typePrefix, message);
    if (frame.length() > 0) {
      Serial.print(frame);  // Don't add newline for binary frames
    } else {
      // Fallback to text mode if frame encoding fails
      String textResponse = typePrefix + ":" + message;
      if (sys.crcEnabled) {
        uint16_t crc = calculateCRC16(textResponse);
        textResponse += "*" + formatCRC16(crc);
      }
      Serial.println(textResponse);
    }
  } else {
    // Send as text protocol (legacy mode)
    String response = typePrefix + ":" + message;
    
    // Add CRC if enabled
    if (sys.crcEnabled) {
      uint16_t crc = calculateCRC16(response);
      response += "*" + formatCRC16(crc);
    }
    
    Serial.println(response);
  }
}

void sendFormattedData(const String& prefix, const String& data) {
  String response = prefix + ":" + data;
  
  // Add CRC if enabled
  if (sys.crcEnabled) {
    uint16_t crc = calculateCRC16(response);
    response += "*" + formatCRC16(crc);
  }
  
  Serial.println(response);
}

/* ---------- Button handling ------------------------------------------ */
void checkButton() {
  bool currentState = digitalRead(BUTTON_PIN) == LOW;  // Active low
  
  // Debounce logic
  if (currentState != sys.lastButtonState) {
    sys.lastDebounceTime = millis();
  }
  
  if ((millis() - sys.lastDebounceTime) > DEBOUNCE_MS) {
    // Button state has been stable
    if (currentState != sys.buttonPressed) {
      sys.buttonPressed = currentState;
      
      // Send button event only on state change to avoid flooding
      // Only send PRESSED event once when button is first pressed
      if (sys.buttonPressed && !sys.buttonEventSent) {
        // Queue this for later or send immediately if no command is being processed
        if (millis() - sys.lastCommandTime > 100) {  // No recent command
          sendResponse(ResponseType::DATA, "BUTTON:PRESSED");
        }
        sys.buttonEventSent = true;
      } else if (!sys.buttonPressed && sys.buttonEventSent) {
        // Send RELEASED only if we previously sent PRESSED
        if (millis() - sys.lastCommandTime > 100) {  // No recent command
          sendResponse(ResponseType::DATA, "BUTTON:RELEASED");
        }
        sys.buttonEventSent = false;
      }
    }
  }
  
  sys.lastButtonState = currentState;
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
  sys.totalMessageCount++;
  
  // Trim command
  String command = cmd;
  command.trim();
  
  // CRC validation if enabled
  if (sys.crcEnabled) {
    if (!verifyCRC(command)) {
      sys.crcErrorCount++;
      sendResponse(ResponseType::ERROR, "CRC_VALIDATION_FAILED");
      return;
    }
    // Extract message without CRC for processing
    command = extractMessage(command);
  }
  
  // Clear any pending button events during command processing
  sys.buttonEventSent = false;
  
  // System commands
  if (command.equalsIgnoreCase("ID") || command.equalsIgnoreCase("PING")) {
    sendResponse(ResponseType::OK, "DIODE_DYNAMICS_SMT_TESTER_V5");
    return;
  }
  
  if (command.equalsIgnoreCase("VERSION")) {
    sendResponse(ResponseType::OK, "VERSION:5.2.0:CRC16_SUPPORT:FRAME_SUPPORT");
    return;
  }
  
  if (command.equalsIgnoreCase("STATUS")) {
    String status = "RELAYS:" + String(sys.configuredRelays);
    status += ",SENSOR:" + String(sys.sensorOK ? "OK" : "FAIL");
    status += ",COMMANDS:" + String(sys.commandCount);
    status += ",BUTTON:" + String(sys.buttonPressed ? "PRESSED" : "RELEASED");
    status += ",STATE:";
    for (uint8_t i = 0; i < sys.configuredRelays; i++) {
      status += sys.relayStates[i] ? '1' : '0';
    }
    sendResponse(ResponseType::DATA, status);
    return;
  }
  
  // Button state query
  if (command.equalsIgnoreCase("BUTTON_STATE")) {
    sendResponse(ResponseType::DATA, 
      "BUTTON:" + String(sys.buttonPressed ? "PRESSED" : "RELEASED"));
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
  
  // CRC-16 commands (Phase 2.1)
  if (command.equalsIgnoreCase("CRC:ENABLE")) {
    sys.crcEnabled = true;
    sendResponse(ResponseType::OK, "CRC_ENABLED");
    return;
  }
  
  if (command.equalsIgnoreCase("CRC:DISABLE")) {
    sys.crcEnabled = false;
    sendResponse(ResponseType::OK, "CRC_DISABLED");
    return;
  }
  
  if (command.equalsIgnoreCase("CRC:STATUS")) {
    String status = "CRC_ENABLED:" + String(sys.crcEnabled ? "TRUE" : "FALSE");
    status += ",TOTAL_MESSAGES:" + String(sys.totalMessageCount);
    status += ",CRC_ERRORS:" + String(sys.crcErrorCount);
    if (sys.totalMessageCount > 0) {
      float errorRate = (float)sys.crcErrorCount / sys.totalMessageCount * 100.0;
      status += ",ERROR_RATE:" + String(errorRate, 2) + "%";
    }
    sendResponse(ResponseType::DATA, status);
    return;
  }
  
  if (command.equalsIgnoreCase("CRC:RESET_STATS")) {
    sys.crcErrorCount = 0;
    sys.totalMessageCount = 0;
    sendResponse(ResponseType::OK, "CRC_STATS_RESET");
    return;
  }
  
  if (command.startsWith("CRC:TEST:")) {
    String testData = command.substring(9);
    uint16_t crc = calculateCRC16(testData);
    sendResponse(ResponseType::DATA, "CRC_TEST:" + testData + "*" + formatCRC16(crc));
    return;
  }
  
  // Binary framing commands (Phase 3)
  if (command.equalsIgnoreCase("FRAME:ENABLE")) {
    sys.framingEnabled = true;
    sendResponse(ResponseType::OK, "FRAMING_ENABLED");
    return;
  }
  
  if (command.equalsIgnoreCase("FRAME:DISABLE")) {
    sys.framingEnabled = false;
    sendResponse(ResponseType::OK, "FRAMING_DISABLED");
    return;
  }
  
  if (command.equalsIgnoreCase("FRAME:STATUS")) {
    String status = "FRAMING_ENABLED:" + String(sys.framingEnabled ? "TRUE" : "FALSE");
    status += ",TOTAL_FRAMES:" + String(sys.totalFrameCount);
    status += ",FRAME_ERRORS:" + String(sys.frameErrorCount);
    if (sys.totalFrameCount > 0) {
      float errorRate = (float)sys.frameErrorCount / sys.totalFrameCount * 100.0;
      status += ",ERROR_RATE:" + String(errorRate, 2) + "%";
    }
    sendResponse(ResponseType::DATA, status);
    return;
  }
  
  if (command.equalsIgnoreCase("FRAME:RESET_STATS")) {
    sys.frameErrorCount = 0;
    sys.totalFrameCount = 0;
    sendResponse(ResponseType::OK, "FRAME_STATS_RESET");
    return;
  }
  
  if (command.startsWith("FRAME:TEST:")) {
    String testData = command.substring(11);
    String frame = encodeFrame("TST", testData);
    if (frame.length() > 0) {
      sendResponse(ResponseType::DATA, "FRAME_TEST:SUCCESS");
    } else {
      sendResponse(ResponseType::ERROR, "FRAME_TEST:FAILED");
    }
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
    uint8_t byte = Serial.read();
    
    // Check for frame timeout
    if (frameParser.isTimedOut()) {
      sys.frameErrorCount++;
      frameParser.reset();
    }
    
    // Try to parse as frame first
    if (byte == STX || frameParser.state != FrameState::IDLE) {
      if (parseFrameByte(byte)) {
        // Frame complete - execute command
        String command = frameParser.frameType + ":" + frameParser.framePayload;
        handleFramedCommand(frameParser.frameType, frameParser.framePayload);
        frameParser.reset();
      }
    } else {
      // Parse as text protocol (legacy mode)
      char c = (char)byte;
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
}

bool parseFrameByte(uint8_t byte) {
  switch (frameParser.state) {
    case FrameState::IDLE:
      if (byte == STX) {
        frameParser.state = FrameState::LENGTH;
        frameParser.frameStartTime = millis();
        frameParser.buffer = "";
        sys.totalFrameCount++;
      }
      return false;
      
    case FrameState::LENGTH:
      if (frameParser.buffer.length() < 3) {
        if (isdigit(byte)) {
          frameParser.buffer += char(byte);
          if (frameParser.buffer.length() == 3) {
            frameParser.expectedLength = frameParser.buffer.toInt();
            frameParser.buffer = "";
          }
        } else {
          sys.frameErrorCount++;
          frameParser.reset();
          return false;
        }
      } else if (byte == ':') {
        frameParser.state = FrameState::TYPE;
      } else {
        sys.frameErrorCount++;
        frameParser.reset();
        return false;
      }
      return false;
      
    case FrameState::TYPE:
      if (frameParser.buffer.length() < 3) {
        frameParser.buffer += char(byte);
        if (frameParser.buffer.length() == 3) {
          frameParser.frameType = frameParser.buffer;
          frameParser.buffer = "";
        }
      } else if (byte == ':') {
        frameParser.state = FrameState::PAYLOAD;
      } else {
        sys.frameErrorCount++;
        frameParser.reset();
        return false;
      }
      return false;
      
    case FrameState::PAYLOAD:
      if (byte == ETX) {
        // For escaped payloads, we need to check the expected length against the original content
        String unescapedPayload = unescapePayload(frameParser.buffer);
        String reconstructedContent = frameParser.frameType + ":" + unescapedPayload;
        
        if (reconstructedContent.length() == frameParser.expectedLength) {
          frameParser.framePayload = unescapedPayload;
          frameParser.buffer = "";
          frameParser.state = FrameState::CRC;
        } else {
          sys.frameErrorCount++;
          frameParser.reset();
          return false;
        }
      } else {
        frameParser.buffer += char(byte);
        if (frameParser.buffer.length() > MAX_FRAME_SIZE) {
          sys.frameErrorCount++;
          frameParser.reset();
          return false;
        }
      }
      return false;
      
    case FrameState::CRC:
      frameParser.buffer += char(byte);
      if (frameParser.buffer.length() == 4) {
        // Validate CRC
        uint16_t receivedCRC = strtoul(frameParser.buffer.c_str(), NULL, 16);
        String frameContent = String(frameParser.expectedLength, DEC);
        while (frameContent.length() < 3) frameContent = "0" + frameContent;
        frameContent += ":" + frameParser.frameType + ":" + frameParser.framePayload;
        uint16_t calculatedCRC = calculateCRC16(frameContent);
        
        if (receivedCRC == calculatedCRC) {
          return true;  // Frame complete and valid
        } else {
          sys.frameErrorCount++;
          frameParser.reset();
          return false;
        }
      }
      return false;
  }
  
  return false;
}

void handleFramedCommand(const String& type, const String& payload) {
  // Enable framing mode when we receive a valid frame
  if (!sys.framingEnabled) {
    sys.framingEnabled = true;
  }
  
  // Convert frame type back to full command format
  String command;
  if (type == "OK" || type == "ERR" || type == "WRN" || type == "INF" || type == "DAT") {
    // This is a response frame - shouldn't happen, but handle gracefully
    command = payload;
  } else {
    // This is a command frame
    command = payload;
  }
  
  handleCommand(command);
}

/* ---------- Arduino setup/loop --------------------------------------- */
void setup() {
  Serial.begin(SERIAL_BAUD);
  while (!Serial && millis() < 3000) ; // Wait for serial
  
  // Initialize button pin
  pinMode(BUTTON_PIN, INPUT_PULLUP);  // Using internal pullup
  delay(100);  // Allow pullup to stabilize
  sys.lastButtonState = digitalRead(BUTTON_PIN);
  sys.buttonPressed = (digitalRead(BUTTON_PIN) == LOW);  // Check initial state
  sys.buttonEventSent = false;  // Haven't sent the initial state yet
  sys.lastDebounceTime = millis();  // Initialize debounce timer
  
  // Initialize relay pins
  for (uint8_t i = 0; i < sys.configuredRelays; i++) {
    pinMode(PIN_MAP[i], OUTPUT);
    digitalWrite(PIN_MAP[i], RELAY_OFF);
  }
  
  // Initialize sensor
  initializeSensor();
  
  // Startup message
  Serial.println("=== Diode Dynamics SMT Board Tester V5 ===");
  Serial.println("Firmware: Enhanced Version 5.2.0 with Binary Framing Support");
  Serial.print("Configured relays: ");
  Serial.println(sys.configuredRelays);
  Serial.print("INA260 sensor: ");
  Serial.println(sys.sensorOK ? "OK" : "NOT FOUND");
  Serial.print("Button on pin ");
  Serial.print(BUTTON_PIN);
  Serial.println(": READY");
  Serial.println("Ready for commands");
  Serial.println();
}

void loop() {
  processSerialInput();
  
  // Only check button if not recently processing a command
  // This prevents button events from interfering with command responses
  if (millis() - sys.lastCommandTime > 50) {
    checkButton();  // Check button state
  }
  
  // Add watchdog or heartbeat if needed
  static uint32_t lastHeartbeat = 0;
  if (sys.debugMode && millis() - lastHeartbeat > 10000) {
    sendResponse(ResponseType::INFO, "HEARTBEAT");
    lastHeartbeat = millis();
  }
}
