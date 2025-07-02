/*
 * SMT Tester - Arduino firmware for Surface Mount Technology (SMT) board testing
 * Version: 1.1.0
 * 
 * Description:
 * This firmware controls a 16-relay test fixture for SMT board validation.
 * It measures voltage and current through each relay circuit using an INA260
 * power monitor to verify proper board assembly and component functionality.
 * 
 * Hardware Requirements:
 * - Arduino R4 Minima with 16 digital outputs for relay control
 * - INA260 I2C power monitor for voltage/current measurements (SDA/SCL pins)
 * - Button input on pin A0 for manual test triggering
 * - 16 relay modules (active-LOW configuration)
 * 
 * Communication Protocol:
 * - Serial: 115200 baud
 * - Commands include sequence numbers and checksums for reliability
 * - Responses echo command sequence for synchronization
 * 
 * Main Commands:
 * - TX:1,2,5,6  Test specific relays (comma-separated or ranges)
 * - TX:ALL      Test all 16 relays in sequence
 * - X           Turn all relays off
 * - I           Get firmware identification
 * - B           Get button status (PRESSED/RELEASED)
 * - V           Get supply voltage without relay activation
 * - RESET_SEQ   Reset sequence numbers for synchronization
 */

#include <Wire.h>
#include <Adafruit_INA260.h>

// Relay logic configuration
// For active-LOW relay modules (most common):
const bool RELAY_ON = LOW;   // Change to HIGH if using active-HIGH relays
const bool RELAY_OFF = HIGH;  // Change to LOW if using active-HIGH relays

// Pin definitions
const int RELAY_PINS[] = {
  2, 3, 4, 5, 6, 7, 8, 9,        // Relays 1-8 (original pins)
  10, 11, 12, 13, 14, 15, 16, 17 // Relays 9-16 (using digital pins available on R4 Minima)
};
const int NUM_RELAYS = 16;
const int BUTTON_PIN = A0; // Using A0 on R4 Minima since A6 doesn't exist (A4/A5 are I2C)
const int LED_PIN = LED_BUILTIN;

// INA260 sensor
Adafruit_INA260 ina260 = Adafruit_INA260();
bool INA_OK = false;  // Global flag to track if sensor is available

// Button state tracking
bool lastButtonState = HIGH;
bool currentButtonPressed = false;  // Current debounced state
unsigned long lastButtonTime = 0;
const unsigned long DEBOUNCE_DELAY = 50;

// Global sequence tracking (unified with Offroad firmware)
uint16_t lastReceivedSeq = 0;      // Last sequence number received from host
uint16_t responseSeq = 0;          // Sequence to echo back in CMDSEQ
uint16_t globalSequenceNumber = 0;  // Auto-incrementing sequence for all responses

// Timing constants
const int RELAY_STABILIZATION_MS = 50;  // Increased from 15ms for better stability
const int MEASUREMENT_SAMPLES = 6;
const int SAMPLE_INTERVAL_MS = 17;
const int INTER_RELAY_DELAY_MS = 20;  // Increased from 10ms for better stability
const int I2C_RETRY_DELAY_MS = 5;  // Delay between I2C retry attempts
const int MAX_I2C_RETRIES = 3;  // Maximum I2C retry attempts

// Parse command with reliability format (unified with Offroad)
struct ParsedCommand {
    String command;
    uint16_t sequence;
    uint8_t checksum;
    bool hasReliability;
};

// Function prototypes
void testPanelSelective(String relayList, unsigned int seq = 0);
void getSupplyVoltage(unsigned int seq = 0);
void measureRelayValues(int relayIndex, float &voltage, float &current);
void allRelaysOff();
void checkButton();
bool parseRelayList(String relayList, bool relaysToTest[], int &count);
byte calculateChecksum(String data);
String formatChecksum(byte checksum);
void sendReliableResponse(const String& data, uint16_t seq = 0);
ParsedCommand parseReliableCommand(const String& cmdStr);
void processCommand(String command);
bool recoverI2C();

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(25);  // Reduce blocking time to 25ms
  
  // Wait for USB serial port to connect (needed for native USB boards)
  unsigned long t0 = millis();
  while (!Serial && (millis() - t0 < 5000)) { }
  
  // Initialize relay pins
  for (int i = 0; i < NUM_RELAYS; i++) {
    pinMode(RELAY_PINS[i], OUTPUT);
    digitalWrite(RELAY_PINS[i], RELAY_OFF);
  }
  
  // Initialize button pin
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  
  // Initialize LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  
  // Initialize INA260 (optional - don't block if missing)
  INA_OK = ina260.begin();
  if (!INA_OK) {
    Serial.println("WARN:INA260_MISSING");
  } else {
    // Set INA260 to fastest conversion time for better performance
    ina260.setMode(INA260_MODE_CONTINUOUS);
    ina260.setCurrentConversionTime(INA260_TIME_140_us);
    ina260.setVoltageConversionTime(INA260_TIME_140_us);
    ina260.setAveragingCount(INA260_COUNT_1);
  }
  
  Serial.println("SMT_BATCH_TESTER_V3_READY");
}

// Calculate XOR checksum for a string
byte calculateChecksum(String data) {
  byte checksum = 0;
  for (int i = 0; i < data.length(); i++) {
    checksum ^= data[i];
  }
  return checksum;
}

// Send response with sequence number and checksum
// Format checksum as 2-character uppercase hex (unified with Offroad)
String formatChecksum(byte checksum) {
  char buf[3];
  sprintf(buf, "%02X", checksum);
  return String(buf);
}

void sendReliableResponse(const String& data, uint16_t seq) {
  String response = data;
  
  // Use received sequence number for commands, auto-increment only for events
  if (seq > 0) {
    // This is a response to a command - use the command's sequence
    response += ":SEQ=" + String(seq);
    response += ":CMDSEQ=" + String(seq);  // Keep for backward compatibility
  } else {
    // This is an event (button press, etc) - use auto-incrementing sequence
    globalSequenceNumber++;
    response += ":SEQ=" + String(globalSequenceNumber);
  }
  
  // Calculate and add checksum (2-char uppercase hex)
  byte checksum = calculateChecksum(response);
  response += ":CHK=" + formatChecksum(checksum) + ":END";
  
  Serial.println(response);
  // Serial.flush() removed - can cause R4 Minima to hang
}

void loop() {
  // Check for button events
  checkButton();
  
  // Process serial commands
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    processCommand(command);
  }
  
  delay(1); // Small delay to prevent overwhelming the system
}

// Parse command with reliability format (unified with Offroad)
ParsedCommand parseReliableCommand(const String& cmdStr) {
    ParsedCommand parsed;
    parsed.hasReliability = false;
    parsed.sequence = 0;
    parsed.checksum = 0;
    
    // Check for reliability format: CMD:SEQ=1234:CHK=A7
    int seqPos = cmdStr.indexOf(":SEQ=");
    int chkPos = cmdStr.indexOf(":CHK=");
    
    if (seqPos > 0 && chkPos > seqPos) {
        // Extract command
        parsed.command = cmdStr.substring(0, seqPos);
        
        // Extract sequence
        int seqEnd = cmdStr.indexOf(':', seqPos + 5);
        if (seqEnd > 0) {
            parsed.sequence = cmdStr.substring(seqPos + 5, seqEnd).toInt();
        }
        
        // Extract checksum
        String chkStr = cmdStr.substring(chkPos + 5, chkPos + 7);
        parsed.checksum = strtoul(chkStr.c_str(), NULL, 16);
        
        parsed.hasReliability = true;
        
        // Verify checksum
        String dataToCheck = cmdStr.substring(0, chkPos);
        uint8_t calcChecksum = calculateChecksum(dataToCheck);
        if (calcChecksum != parsed.checksum) {
            parsed.hasReliability = false;  // Mark as invalid
            parsed.command = "";  // Clear command to prevent execution
        }
    } else {
        // Simple command without reliability
        parsed.command = cmdStr;
    }
    
    return parsed;
}

void processCommand(String command) {
  digitalWrite(LED_PIN, HIGH); // Indicate activity
  
  // Parse command with unified approach
  ParsedCommand parsed = parseReliableCommand(command);
  
  // Handle invalid checksum
  if (command.indexOf(":CHK=") > 0 && parsed.command.isEmpty()) {
    sendReliableResponse("ERROR:BAD_CHECKSUM", 0);
    digitalWrite(LED_PIN, LOW);
    return;
  }
  
  // Update sequence tracking
  if (parsed.hasReliability) {
    lastReceivedSeq = parsed.sequence;
    responseSeq = parsed.sequence; // Echo back same sequence
  } else {
    responseSeq = 0; // No sequence for simple commands
  }
  
  // Extract base command
  String baseCommand = parsed.command;
  
  if (baseCommand.startsWith("TX:")) {
    // Test specific relays (the only test command)
    testPanelSelective(baseCommand.substring(3), responseSeq);
  }
  else if (baseCommand == "X") {
    // Turn all relays off
    allRelaysOff();
    sendReliableResponse("OK:ALL_OFF", responseSeq);
  }
  else if (baseCommand == "I") {
    // Get board info
    sendReliableResponse("ID:SMT_BATCH_TESTER_V3.0_16RELAY", responseSeq);
  }
  else if (baseCommand == "B") {
    // Get current button status (use debounced state)
    if (currentButtonPressed) {
      sendReliableResponse("BUTTON:PRESSED", responseSeq);
    } else {
      sendReliableResponse("BUTTON:RELEASED", responseSeq);
    }
  }
  else if (baseCommand == "V") {
    // Get supply voltage without turning on any relays
    getSupplyVoltage(responseSeq);
  }
  else if (baseCommand == "RESET_SEQ") {
    // Reset sequence numbers (unified protocol enhancement)
    globalSequenceNumber = 0;
    lastReceivedSeq = 0;
    responseSeq = parsed.hasReliability ? parsed.sequence : 0;  // Use received seq for response
    sendReliableResponse("OK:SEQ_RESET", responseSeq);
  }
  else {
    sendReliableResponse("ERROR:UNKNOWN_COMMAND", responseSeq);
  }
  
  digitalWrite(LED_PIN, LOW);
}

// Attempt to recover I2C communication
bool recoverI2C() {
  // Try to reinitialize the INA260
  for (int attempt = 0; attempt < MAX_I2C_RETRIES; attempt++) {
    delay(I2C_RETRY_DELAY_MS);
    
    // Check if device responds
    Wire.beginTransmission(0x40);
    if (Wire.endTransmission() == 0) {
      // Device is responding, try to reinitialize
      INA_OK = ina260.begin();
      if (INA_OK) {
        // Reconfigure settings
        ina260.setMode(INA260_MODE_CONTINUOUS);
        ina260.setCurrentConversionTime(INA260_TIME_140_us);
        ina260.setVoltageConversionTime(INA260_TIME_140_us);
        ina260.setAveragingCount(INA260_COUNT_1);
        return true;
      }
    }
  }
  return false;
}

// Measure relay and return values (for internal use)
void measureRelayValues(int relayIndex, float &voltage, float &current) {
  // Turn on the specific relay
  digitalWrite(RELAY_PINS[relayIndex], RELAY_ON);
  
  // Wait for relay to stabilize (increased delay)
  delay(RELAY_STABILIZATION_MS);
  
  // Take multiple samples for accuracy
  float totalVoltage = 0;
  float totalCurrent = 0;
  bool sensorFailed = false;
  int validSamples = 0;
  
  // If sensor was marked as failed, try to recover it first
  if (!INA_OK) {
    if (recoverI2C()) {
      INA_OK = true;
    }
  }
  
  for (int i = 0; i < MEASUREMENT_SAMPLES; i++) {
    if (INA_OK) {
      // Try to read with retry logic
      bool readSuccess = false;
      for (int retry = 0; retry < MAX_I2C_RETRIES; retry++) {
        // Check I2C FIRST before attempting to read
        Wire.beginTransmission(0x40);  // INA260 default address
        byte i2cError = Wire.endTransmission();
        
        if (i2cError == 0) {
          // I2C is working, now safe to read
          float v = ina260.readBusVoltage();
          float c = ina260.readCurrent();
          
          // Validate readings
          if (!isnan(v) && !isnan(c) && v >= 0) {
            // Success - add to totals
            totalVoltage += v;
            totalCurrent += c;
            validSamples++;
            readSuccess = true;
            
            break;
          }
        }
        
        // If we're here, either I2C failed or readings were invalid
        if (retry < MAX_I2C_RETRIES - 1) {
          // Failed - try to recover
          delay(I2C_RETRY_DELAY_MS);
          if (recoverI2C()) {
            continue;
          }
        }
      }
      
      if (!readSuccess) {
        // All retries failed
        sensorFailed = true;
        INA_OK = false;
        break;
      }
    } else {
      // INA260 not available
      sensorFailed = true;
      break;
    }
    
    if (i < MEASUREMENT_SAMPLES - 1) {
      delay(SAMPLE_INTERVAL_MS);
    }
  }
  
  // Turn off the relay
  digitalWrite(RELAY_PINS[relayIndex], RELAY_OFF);
  
  // Small delay after turning off relay
  delay(5);
  
  // Calculate averages (convert mV to V and mA to A)
  if (validSamples > 0) {
    // We got at least some valid readings
    voltage = totalVoltage / validSamples / 1000.0;
    current = totalCurrent / validSamples / 1000.0;
  } else {
    // No valid readings at all
    voltage = -1.0;  // Indicate sensor failure
    current = -1.0;
  }
}



void allRelaysOff() {
  for (int i = 0; i < NUM_RELAYS; i++) {
    digitalWrite(RELAY_PINS[i], RELAY_OFF);
  }
}

// Get supply voltage without activating any relays
void getSupplyVoltage(unsigned int seq) {
  if (!INA_OK) {
    sendReliableResponse("VOLTAGE:0.000", seq);
    return;
  }
  
  // Take multiple samples for accuracy
  float totalVoltage = 0;
  const int samples = 5;
  
  for (int i = 0; i < samples; i++) {
    totalVoltage += ina260.readBusVoltage();
    if (i < samples - 1) {
      delay(5);  // Small delay between samples
    }
  }
  
  // Calculate average and convert mV to V
  float voltage = totalVoltage / samples / 1000.0;
  
  // Send result with checksum
  String response = "VOLTAGE:" + String(voltage, 3);
  sendReliableResponse(response, seq);
  delay(5);  // Small delay to prevent buffer conflicts
}

void checkButton() {
  bool currentState = digitalRead(BUTTON_PIN);
  
  // Check for button state change with debounce
  if (currentState != lastButtonState) {
    if (millis() - lastButtonTime > DEBOUNCE_DELAY) {
      if (currentState == LOW && lastButtonState == HIGH) {
        // Button was pressed
        currentButtonPressed = true;
        // Send event immediately for responsiveness
        Serial.println("EVENT:BUTTON_PRESSED");
        // Serial.flush() removed - can cause R4 Minima to hang
      } else if (currentState == HIGH && lastButtonState == LOW) {
        // Button was released
        currentButtonPressed = false;
        Serial.println("EVENT:BUTTON_RELEASED");
        // Serial.flush() removed - can cause R4 Minima to hang
      }
      lastButtonTime = millis();
    }
  }
  lastButtonState = currentState;
}


// Parse relay list and test specific relays
void testPanelSelective(String relayList, unsigned int seq) {
  // Array to store which relays to test
  bool relaysToTest[NUM_RELAYS] = {false};
  int relayCount = 0;
  
  // Special case: TX:ALL tests all 16 relays
  if (relayList == "ALL") {
    for (int i = 0; i < NUM_RELAYS; i++) {
      relaysToTest[i] = true;
    }
    relayCount = NUM_RELAYS;
  } else {
    // Parse the relay list
    if (!parseRelayList(relayList, relaysToTest, relayCount)) {
      sendReliableResponse("ERROR:INVALID_RELAY_LIST", seq);
      return;
    }
    
    if (relayCount == 0) {
      sendReliableResponse("ERROR:EMPTY_RELAY_LIST", seq);
      return;
    }
  }
  
  // Test selected relays
  char result[200];  // Buffer for response (16 relays * ~12 chars each)
  strcpy(result, "PANELX:");
  bool firstRelay = true;
  
  for (int i = 0; i < NUM_RELAYS; i++) {
    if (relaysToTest[i]) {
      float voltage, current;
      measureRelayValues(i, voltage, current);
      
      // Check for sensor failure
      if (voltage < 0 || current < 0) {
        sendReliableResponse("ERROR:INA260_FAIL", seq);
        allRelaysOff();  // Ensure all relays are off
        return;
      }
      
      // Append to result buffer with relay number
      char relayData[20];
      if (!firstRelay) strcat(result, ";");
      snprintf(relayData, sizeof(relayData), "%d=%.3f,%.3f", i + 1, voltage, current);
      strcat(result, relayData);
      firstRelay = false;
      
      // Small delay between relays
      if (relayCount > 1) delay(INTER_RELAY_DELAY_MS);
      relayCount--;
    }
  }
  
  sendReliableResponse(String(result), seq);
}


// Parse relay list (supports individual numbers and ranges)
// Examples: "1,2,5,6" or "1-4,9-12" or "1,2,5-8,12"
bool parseRelayList(String relayList, bool relaysToTest[], int &count) {
  count = 0;
  int startPos = 0;
  
  // Clear the array
  for (int i = 0; i < NUM_RELAYS; i++) {
    relaysToTest[i] = false;
  }
  
  // Parse comma-separated tokens
  while (startPos < relayList.length()) {
    int commaPos = relayList.indexOf(',', startPos);
    if (commaPos == -1) commaPos = relayList.length();
    
    String token = relayList.substring(startPos, commaPos);
    token.trim();
    
    // Check for range (contains dash)
    int dashPos = token.indexOf('-');
    if (dashPos > 0) {
      // Parse range
      int rangeStart = token.substring(0, dashPos).toInt();
      int rangeEnd = token.substring(dashPos + 1).toInt();
      
      if (rangeStart < 1 || rangeStart > NUM_RELAYS || 
          rangeEnd < 1 || rangeEnd > NUM_RELAYS || 
          rangeStart > rangeEnd) {
        return false; // Invalid range
      }
      
      // Mark relays in range
      for (int i = rangeStart; i <= rangeEnd; i++) {
        if (!relaysToTest[i - 1]) {
          relaysToTest[i - 1] = true;
          count++;
        }
      }
    } else {
      // Parse single number
      int relayNum = token.toInt();
      if (relayNum < 1 || relayNum > NUM_RELAYS) {
        return false; // Invalid relay number
      }
      
      if (!relaysToTest[relayNum - 1]) {
        relaysToTest[relayNum - 1] = true;
        count++;
      }
    }
    
    startPos = commaPos + 1;
  }
  
  return true;
}
