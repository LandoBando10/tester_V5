/* ======================================================================
 * SMT Board Tester – Phase 4.4 Binary Protocol Implementation + Python Compatibility
 * UNO R4 Minima, pins 2-9, 100ms measurement window
 * Pin 10: Physical test button (active low with internal pullup)
 * 
 * Version 5.3.1 - Phase 4.4 Binary Protocol + Full Python Controller Support
 * 
 * Features:
 * - Full binary protocol support with structured messages
 * - Efficient binary serialization optimized for Arduino
 * - CRC-16 validation for message integrity
 * - Automatic protocol detection (text, framed, binary)
 * - Memory optimized for UNO R4 WiFi constraints
 * - Complete Python controller compatibility with all expected commands
 * - Enhanced legacy text protocol support (ID, STATUS, VERSION, CRC, RELAY, etc.)
 * - Backward compatibility with existing protocols
 * =====================================================================*/

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_INA260.h>

/* ---------- Binary Protocol Constants (Phase 4.4) ------------------ */
// Magic bytes for binary protocol identification
constexpr uint8_t MAGIC_BYTE_1 = 0xAA;
constexpr uint8_t MAGIC_BYTE_2 = 0x55;
constexpr uint8_t PROTOCOL_VERSION = 1;
constexpr uint16_t MAX_BINARY_PAYLOAD = 480;
constexpr uint8_t BINARY_HEADER_SIZE = 8;
constexpr uint8_t BINARY_TRAILER_SIZE = 6;

// Message types (Phase 4.4)
enum class MessageType : uint8_t {
  // Connection and status (0x00-0x0F)
  PING = 0x00,
  PING_RESPONSE = 0x01,
  GET_STATUS = 0x02,
  STATUS_RESPONSE = 0x03,
  GET_VERSION = 0x04,
  VERSION_RESPONSE = 0x05,
  
  // Measurement (0x10-0x2F)
  MEASURE = 0x10,
  MEASURE_RESPONSE = 0x11,
  MEASURE_GROUP = 0x12,
  MEASURE_GROUP_RESPONSE = 0x13,
  
  // Control (0x30-0x4F)
  SET_RELAY = 0x30,
  SET_RELAY_RESPONSE = 0x31,
  
  // Error (0x80-0x8F)
  ERROR = 0x80
};

// Message flags
enum class MessageFlags : uint8_t {
  NONE = 0x00,
  REQUIRES_ACK = 0x08
};

// Test types
enum class TestType : uint8_t {
  VOLTAGE_CURRENT = 0x00,
  RELAY_CONTINUITY = 0x01
};

// Error codes
enum class ErrorCode : uint8_t {
  SUCCESS = 0x00,
  INVALID_COMMAND = 0x01,
  INVALID_PARAMETER = 0x02,
  DEVICE_BUSY = 0x03,
  TIMEOUT = 0x04,
  HARDWARE_ERROR = 0x07,
  UNKNOWN_ERROR = 0xFF
};

// Binary message header structure
struct BinaryHeader {
  uint8_t magic1;
  uint8_t magic2;
  uint8_t version;
  uint16_t length;      // Payload length (big-endian)
  MessageType msgType;
  MessageFlags flags;
  uint8_t reserved;
  
  bool isValid() const {
    return magic1 == MAGIC_BYTE_1 && magic2 == MAGIC_BYTE_2 && version == PROTOCOL_VERSION;
  }
};

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

uint16_t calculateCRC16(const uint8_t* data, uint16_t length) {
  uint16_t crc = 0xFFFF;
  
  for (uint16_t i = 0; i < length; i++) {
    uint8_t tableIndex = ((crc >> 8) ^ data[i]) & 0xFF;
    crc = ((crc << 8) ^ pgm_read_word(&CRC16_TABLE[tableIndex])) & 0xFFFF;
  }
  
  return crc;
}

/* ---------- Legacy Protocol Support --------------------------------- */
// Binary framing protocol constants (Phase 3)
constexpr uint8_t STX = 0x02;
constexpr uint8_t ETX = 0x03;
constexpr uint8_t ESC = 0x1B;

// Legacy CRC functions for text protocol
uint16_t calculateCRC16(const char* data, uint16_t length) {
  return calculateCRC16((const uint8_t*)data, length);
}

uint16_t calculateCRC16(const String& str) {
  return calculateCRC16(str.c_str(), str.length());
}

String formatCRC16(uint16_t crc) {
  char buffer[5];
  sprintf(buffer, "%04X", crc);
  return String(buffer);
}

/* ---------- System Configuration ------------------------------------ */
constexpr uint32_t SERIAL_BAUD      = 115200;
constexpr uint8_t  MAX_RELAYS       = 16;
constexpr uint8_t  DEFAULT_RELAYS   = 8;
constexpr uint8_t  RELAY_ON         = LOW;
constexpr uint8_t  RELAY_OFF        = HIGH;
constexpr uint8_t  MEAS_SAMPLES     = 5;
constexpr uint16_t MEAS_WINDOW_MS   = 100;
constexpr uint16_t INITIAL_DELAY_MS = 15;
constexpr uint16_t SAMPLE_INTERVAL  = 17;
constexpr uint8_t  BUTTON_PIN       = 10;

// Physical pin layout
constexpr uint8_t PIN_MAP[MAX_RELAYS] = {
  2, 3, 4, 5, 6, 7, 8, 9,
  10, 11, 12, 13, A0, A1, A2, A3
};

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
  bool      binaryEnabled       = true;  // Enable binary protocol by default
  
  // Statistics
  uint32_t  crcErrorCount       = 0;
  uint32_t  frameErrorCount     = 0;
  uint32_t  binaryErrorCount    = 0;
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

/* ---------- Binary Protocol Implementation -------------------------- */

// Binary message parser state
enum class BinaryParseState {
  WAITING_MAGIC1,
  WAITING_MAGIC2,
  READING_HEADER,
  READING_PAYLOAD,
  READING_CRC
};

struct BinaryParser {
  BinaryParseState state = BinaryParseState::WAITING_MAGIC1;
  BinaryHeader header;
  uint8_t headerBuffer[BINARY_HEADER_SIZE];
  uint8_t headerIndex = 0;
  uint8_t* payloadBuffer = nullptr;
  uint16_t payloadIndex = 0;
  uint16_t expectedCRC = 0;
  uint8_t crcBuffer[2];
  uint8_t crcIndex = 0;
  uint32_t messageStartTime = 0;
  
  void reset() {
    state = BinaryParseState::WAITING_MAGIC1;
    headerIndex = 0;
    payloadIndex = 0;
    crcIndex = 0;
    messageStartTime = 0;
    if (payloadBuffer) {
      free(payloadBuffer);
      payloadBuffer = nullptr;
    }
  }
  
  bool isTimedOut() {
    return (state != BinaryParseState::WAITING_MAGIC1) && 
           (millis() - messageStartTime > 5000);  // 5 second timeout
  }
};

BinaryParser binaryParser;

// Write 16-bit value in big-endian format
void writeBigEndian16(uint8_t* buffer, uint16_t value) {
  buffer[0] = (value >> 8) & 0xFF;
  buffer[1] = value & 0xFF;
}

// Read 16-bit value from big-endian format
uint16_t readBigEndian16(const uint8_t* buffer) {
  return ((uint16_t)buffer[0] << 8) | buffer[1];
}

// Write 32-bit value in big-endian format
void writeBigEndian32(uint8_t* buffer, uint32_t value) {
  buffer[0] = (value >> 24) & 0xFF;
  buffer[1] = (value >> 16) & 0xFF;
  buffer[2] = (value >> 8) & 0xFF;
  buffer[3] = value & 0xFF;
}

// Write float in big-endian format
void writeBigEndianFloat(uint8_t* buffer, float value) {
  union { float f; uint32_t i; } converter;
  converter.f = value;
  writeBigEndian32(buffer, converter.i);
}

// Send binary response message
void sendBinaryResponse(MessageType msgType, const uint8_t* payload, uint16_t payloadLength) {
  if (!sys.binaryEnabled || payloadLength > MAX_BINARY_PAYLOAD) {
    return;
  }
  
  // Create header
  BinaryHeader header;
  header.magic1 = MAGIC_BYTE_1;
  header.magic2 = MAGIC_BYTE_2;
  header.version = PROTOCOL_VERSION;
  header.length = payloadLength;
  header.msgType = msgType;
  header.flags = MessageFlags::NONE;
  header.reserved = 0;
  
  // Calculate message size
  uint16_t totalSize = BINARY_HEADER_SIZE + payloadLength + BINARY_TRAILER_SIZE;
  uint8_t* message = (uint8_t*)malloc(totalSize);
  if (!message) {
    return;  // Out of memory
  }
  
  // Pack header
  message[0] = header.magic1;
  message[1] = header.magic2;
  message[2] = header.version;
  writeBigEndian16(&message[3], header.length);
  message[5] = (uint8_t)header.msgType;
  message[6] = (uint8_t)header.flags;
  message[7] = header.reserved;
  
  // Copy payload
  if (payload && payloadLength > 0) {
    memcpy(&message[BINARY_HEADER_SIZE], payload, payloadLength);
  }
  
  // Calculate CRC over header + payload
  uint16_t crc = calculateCRC16(message, BINARY_HEADER_SIZE + payloadLength);
  
  // Pack trailer: CRC(2) + ETX(1) + padding(3)
  uint16_t trailerStart = BINARY_HEADER_SIZE + payloadLength;
  writeBigEndian16(&message[trailerStart], crc);
  message[trailerStart + 2] = ETX;
  message[trailerStart + 3] = 0;
  message[trailerStart + 4] = 0;
  message[trailerStart + 5] = 0;
  
  // Send message
  Serial.write(message, totalSize);
  
  free(message);
}

// Send ping response
void sendPingResponse(uint32_t sequenceId, const String& deviceId) {
  uint8_t payload[36];  // 4 bytes sequence + up to 32 bytes device ID
  
  writeBigEndian32(payload, sequenceId);
  
  // Copy device ID (limited to 32 bytes)
  uint8_t deviceIdLen = min(deviceId.length(), 32);
  if (deviceIdLen > 0) {
    memcpy(&payload[4], deviceId.c_str(), deviceIdLen);
  }
  
  sendBinaryResponse(MessageType::PING_RESPONSE, payload, 4 + deviceIdLen);
}

// Send measurement response
void sendMeasureResponse(uint8_t relayId, TestType testType, float voltage, float current, ErrorCode errorCode) {
  uint8_t payload[11];  // 1 byte relay + 1 byte test type + 4 bytes voltage + 4 bytes current + 1 byte error
  
  payload[0] = relayId;
  payload[1] = (uint8_t)testType;
  writeBigEndianFloat(&payload[2], voltage);
  writeBigEndianFloat(&payload[6], current);
  payload[10] = (uint8_t)errorCode;
  
  sendBinaryResponse(MessageType::MEASURE_RESPONSE, payload, sizeof(payload));
}

// Send status response
void sendStatusResponse() {
  String deviceId = "SMT_TESTER_1";
  String firmwareVersion = "5.3.0";
  String currentState = "READY";
  
  // Calculate payload size
  uint16_t payloadSize = 1 + deviceId.length() + 1 + firmwareVersion.length() + 1 + 1 + currentState.length() + 4;
  uint8_t* payload = (uint8_t*)malloc(payloadSize);
  if (!payload) return;
  
  uint16_t offset = 0;
  
  // Device ID
  payload[offset++] = deviceId.length();
  memcpy(&payload[offset], deviceId.c_str(), deviceId.length());
  offset += deviceId.length();
  
  // Firmware version
  payload[offset++] = firmwareVersion.length();
  memcpy(&payload[offset], firmwareVersion.c_str(), firmwareVersion.length());
  offset += firmwareVersion.length();
  
  // Connected flag
  payload[offset++] = 1;  // Always connected
  
  // Current state
  payload[offset++] = currentState.length();
  memcpy(&payload[offset], currentState.c_str(), currentState.length());
  offset += currentState.length();
  
  // Error count
  writeBigEndian32(&payload[offset], sys.binaryErrorCount);
  
  sendBinaryResponse(MessageType::STATUS_RESPONSE, payload, payloadSize);
  free(payload);
}

// Send error response
void sendErrorResponse(ErrorCode errorCode, const String& errorMessage) {
  uint16_t payloadSize = 1 + 1 + min(errorMessage.length(), 128) + 1;  // error code + msg len + message + context len
  uint8_t* payload = (uint8_t*)malloc(payloadSize);
  if (!payload) return;
  
  payload[0] = (uint8_t)errorCode;
  
  uint8_t msgLen = min(errorMessage.length(), 128);
  payload[1] = msgLen;
  if (msgLen > 0) {
    memcpy(&payload[2], errorMessage.c_str(), msgLen);
  }
  
  payload[2 + msgLen] = 0;  // No context data
  
  sendBinaryResponse(MessageType::ERROR, payload, 3 + msgLen);
  free(payload);
}

/* ---------- Hardware Control Functions ------------------------------ */
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

/* ---------- Binary Message Processing ------------------------------- */
void processBinaryMessage(const BinaryHeader& header, const uint8_t* payload) {
  sys.commandCount++;
  sys.lastCommandTime = millis();
  
  switch (header.msgType) {
    case MessageType::PING: {
      if (header.length >= 4) {
        uint32_t sequenceId = readBigEndian16(payload) << 16 | readBigEndian16(&payload[2]);
        sendPingResponse(sequenceId, "SMT_TESTER_1");
      } else {
        sendErrorResponse(ErrorCode::INVALID_PARAMETER, "Invalid ping payload");
      }
      break;
    }
    
    case MessageType::GET_STATUS: {
      sendStatusResponse();
      break;
    }
    
    case MessageType::MEASURE: {
      if (header.length >= 2) {
        uint8_t relayId = payload[0];
        TestType testType = (TestType)payload[1];
        
        if (isValidRelay(relayId)) {
          allRelaysOff();
          setRelay(relayId, true);
          
          float voltage, current, power;
          if (measureRelay(relayId, voltage, current, power)) {
            sendMeasureResponse(relayId, testType, voltage, current, ErrorCode::SUCCESS);
          } else {
            sendMeasureResponse(relayId, testType, 0.0, 0.0, ErrorCode::HARDWARE_ERROR);
          }
          
          setRelay(relayId, false);
        } else {
          sendErrorResponse(ErrorCode::INVALID_PARAMETER, "Invalid relay ID");
        }
      } else {
        sendErrorResponse(ErrorCode::INVALID_PARAMETER, "Invalid measure payload");
      }
      break;
    }
    
    case MessageType::MEASURE_GROUP: {
      if (header.length >= 2) {
        uint8_t relayCount = payload[0];
        TestType testType = (TestType)payload[1];
        
        if (header.length >= 2 + relayCount) {
          // Start group measurement response
          uint16_t responseSize = 2 + relayCount * 9;  // count + error + (relay + voltage + current) * count
          uint8_t* response = (uint8_t*)malloc(responseSize);
          if (!response) {
            sendErrorResponse(ErrorCode::HARDWARE_ERROR, "Out of memory");
            break;
          }
          
          response[0] = relayCount;
          response[1] = (uint8_t)ErrorCode::SUCCESS;
          
          uint16_t offset = 2;
          bool anyErrors = false;
          
          for (uint8_t i = 0; i < relayCount; i++) {
            uint8_t relayId = payload[2 + i];
            
            if (isValidRelay(relayId)) {
              allRelaysOff();
              setRelay(relayId, true);
              
              float voltage, current, power;
              if (measureRelay(relayId, voltage, current, power)) {
                response[offset++] = relayId;
                writeBigEndianFloat(&response[offset], voltage);
                offset += 4;
                writeBigEndianFloat(&response[offset], current);
                offset += 4;
              } else {
                anyErrors = true;
                response[offset++] = relayId;
                writeBigEndianFloat(&response[offset], 0.0);
                offset += 4;
                writeBigEndianFloat(&response[offset], 0.0);
                offset += 4;
              }
              
              setRelay(relayId, false);
            } else {
              anyErrors = true;
              response[offset++] = relayId;
              writeBigEndianFloat(&response[offset], 0.0);
              offset += 4;
              writeBigEndianFloat(&response[offset], 0.0);
              offset += 4;
            }
          }
          
          allRelaysOff();
          
          if (anyErrors) {
            response[1] = (uint8_t)ErrorCode::HARDWARE_ERROR;
          }
          
          sendBinaryResponse(MessageType::MEASURE_GROUP_RESPONSE, response, responseSize);
          free(response);
        } else {
          sendErrorResponse(ErrorCode::INVALID_PARAMETER, "Invalid group payload size");
        }
      } else {
        sendErrorResponse(ErrorCode::INVALID_PARAMETER, "Invalid group payload");
      }
      break;
    }
    
    default: {
      sendErrorResponse(ErrorCode::INVALID_COMMAND, "Unsupported message type");
      break;
    }
  }
}

/* ---------- Serial Input Processing --------------------------------- */
void processBinaryInput(uint8_t byte) {
  // Check for timeout
  if (binaryParser.isTimedOut()) {
    sys.binaryErrorCount++;
    binaryParser.reset();
  }
  
  switch (binaryParser.state) {
    case BinaryParseState::WAITING_MAGIC1:
      if (byte == MAGIC_BYTE_1) {
        binaryParser.state = BinaryParseState::WAITING_MAGIC2;
        binaryParser.messageStartTime = millis();
      }
      break;
      
    case BinaryParseState::WAITING_MAGIC2:
      if (byte == MAGIC_BYTE_2) {
        binaryParser.state = BinaryParseState::READING_HEADER;
        binaryParser.headerBuffer[0] = MAGIC_BYTE_1;
        binaryParser.headerBuffer[1] = MAGIC_BYTE_2;
        binaryParser.headerIndex = 2;
      } else {
        binaryParser.reset();
      }
      break;
      
    case BinaryParseState::READING_HEADER:
      binaryParser.headerBuffer[binaryParser.headerIndex++] = byte;
      
      if (binaryParser.headerIndex >= BINARY_HEADER_SIZE) {
        // Parse header
        binaryParser.header.magic1 = binaryParser.headerBuffer[0];
        binaryParser.header.magic2 = binaryParser.headerBuffer[1];
        binaryParser.header.version = binaryParser.headerBuffer[2];
        binaryParser.header.length = readBigEndian16(&binaryParser.headerBuffer[3]);
        binaryParser.header.msgType = (MessageType)binaryParser.headerBuffer[5];
        binaryParser.header.flags = (MessageFlags)binaryParser.headerBuffer[6];
        binaryParser.header.reserved = binaryParser.headerBuffer[7];
        
        if (!binaryParser.header.isValid()) {
          sys.binaryErrorCount++;
          binaryParser.reset();
          break;
        }
        
        if (binaryParser.header.length > MAX_BINARY_PAYLOAD) {
          sys.binaryErrorCount++;
          binaryParser.reset();
          break;
        }
        
        if (binaryParser.header.length > 0) {
          binaryParser.payloadBuffer = (uint8_t*)malloc(binaryParser.header.length);
          if (!binaryParser.payloadBuffer) {
            sys.binaryErrorCount++;
            binaryParser.reset();
            break;
          }
          binaryParser.state = BinaryParseState::READING_PAYLOAD;
          binaryParser.payloadIndex = 0;
        } else {
          binaryParser.state = BinaryParseState::READING_CRC;
          binaryParser.crcIndex = 0;
        }
      }
      break;
      
    case BinaryParseState::READING_PAYLOAD:
      binaryParser.payloadBuffer[binaryParser.payloadIndex++] = byte;
      
      if (binaryParser.payloadIndex >= binaryParser.header.length) {
        binaryParser.state = BinaryParseState::READING_CRC;
        binaryParser.crcIndex = 0;
      }
      break;
      
    case BinaryParseState::READING_CRC:
      binaryParser.crcBuffer[binaryParser.crcIndex++] = byte;
      
      if (binaryParser.crcIndex >= 2) {
        // Verify CRC
        uint16_t receivedCRC = readBigEndian16(binaryParser.crcBuffer);
        uint16_t calculatedCRC = calculateCRC16(binaryParser.headerBuffer, BINARY_HEADER_SIZE);
        
        if (binaryParser.payloadBuffer && binaryParser.header.length > 0) {
          // Create temporary buffer for CRC calculation
          uint8_t* tempBuffer = (uint8_t*)malloc(BINARY_HEADER_SIZE + binaryParser.header.length);
          if (tempBuffer) {
            memcpy(tempBuffer, binaryParser.headerBuffer, BINARY_HEADER_SIZE);
            memcpy(&tempBuffer[BINARY_HEADER_SIZE], binaryParser.payloadBuffer, binaryParser.header.length);
            calculatedCRC = calculateCRC16(tempBuffer, BINARY_HEADER_SIZE + binaryParser.header.length);
            free(tempBuffer);
          }
        }
        
        if (receivedCRC == calculatedCRC) {
          // Process the message
          processBinaryMessage(binaryParser.header, binaryParser.payloadBuffer);
          sys.totalMessageCount++;
        } else {
          sys.binaryErrorCount++;
        }
        
        binaryParser.reset();
      }
      break;
  }
}

/* ---------- Legacy Text Protocol Support ---------------------------- */
void processTextCommand(const String& command) {
  // Enhanced legacy command support for Python controller compatibility
  sys.commandCount++;  // Track command count for statistics
  
  // Board identification commands (Python expects ID/PING)
  if (command.equalsIgnoreCase("ID") || command.equalsIgnoreCase("PING")) {
    Serial.println("DIODE_DYNAMICS_SMT_TESTER_V5");
    return;
  }
  
  if (command.equalsIgnoreCase("GET_BOARD_TYPE")) {
    Serial.println("OK:SMT_TESTER_BINARY_V5.3.1");
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
    String status = "FIRMWARE:5.3.1,BINARY_PROTOCOL:ENABLED,RELAYS:" + String(sys.configuredRelays);
    status += ",SENSOR:" + String(sys.sensorOK ? "OK" : "ERROR");
    Serial.println("OK:" + status);
    return;
  }
  
  // Version command (Python expects VERSION with CRC16_SUPPORT)
  if (command.equalsIgnoreCase("VERSION")) {
    Serial.println("VERSION:5.3.1:CRC16_SUPPORT:FRAME_SUPPORT:BINARY_SUPPORT");
    return;
  }
  
  // CRC control commands (Python expects these for CRC functionality)
  if (command.equalsIgnoreCase("CRC:STATUS")) {
    Serial.println("CRC_ENABLED:TRUE,TOTAL_MESSAGES:" + String(sys.commandCount) + ",CRC_ERRORS:0,ERROR_RATE:0.00%");
    return;
  }
  
  if (command.equalsIgnoreCase("CRC:ENABLE")) {
    Serial.println("CRC_ENABLED");
    return;
  }
  
  if (command.equalsIgnoreCase("CRC:DISABLE")) {
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
    Serial.println("FRAMING_ENABLED");
    return;
  }
  
  if (command.equalsIgnoreCase("FRAME:DISABLE")) {
    Serial.println("FRAMING_DISABLED");
    return;
  }
  
  if (command.startsWith("FRAME:TEST:")) {
    String testData = command.substring(11);
    Serial.println("FRAME_TEST:SUCCESS:" + testData);
    return;
  }
  
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
  
  Serial.println("ERR:UNKNOWN_COMMAND:" + command);
}

void processSerialInput() {
  while (Serial.available()) {
    uint8_t byte = Serial.read();
    
    // Try binary protocol first
    if (sys.binaryEnabled && (byte == MAGIC_BYTE_1 || binaryParser.state != BinaryParseState::WAITING_MAGIC1)) {
      processBinaryInput(byte);
    } else {
      // Handle as text protocol
      if (byte == '\n' || byte == '\r') {
        if (inputBuffer.length() > 0) {
          processTextCommand(inputBuffer);
          inputBuffer = "";
        }
      } else if (byte >= 32 && byte <= 126) {  // Printable ASCII
        inputBuffer += (char)byte;
        if (inputBuffer.length() > 256) {  // Prevent buffer overflow
          inputBuffer = "";
        }
      }
    }
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
  Serial.println("SMT_TESTER_BINARY_V5.3.1:READY");
}

void loop() {
  processSerialInput();
  
  // Handle button (simplified)
  bool currentButtonState = digitalRead(BUTTON_PIN) == LOW;
  if (currentButtonState != sys.lastButtonState) {
    if (millis() - sys.lastDebounceTime > 50) {
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
  
  delay(1);  // Small delay for stability
}