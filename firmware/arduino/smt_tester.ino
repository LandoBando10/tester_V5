/*
 * SMT Tester - Arduino firmware for Surface Mount Technology (SMT) board testing
 * Version: 2.0.0
 * 
 * Description:
 * This firmware controls a 14-relay test fixture for SMT board validation.
 * It measures voltage and current through each relay circuit using an INA260
 * power monitor to verify proper board assembly and component functionality.
 * Supports simultaneous relay activation with precise timing control.
 * 
 * Hardware Requirements:
 * - Arduino R4 Minima (32KB RAM, 256KB Flash)
 * - PCF8575 I2C I/O expander for 16 relay control (address 0x20)
 * - INA260 I2C power monitor for voltage/current measurements (address 0x40)
 * - Button input on PCF8575 pin P16 for manual test triggering
 * - 14 relay modules on PCF8575 P0-P13 (configurable active-HIGH/LOW)
 * 
 * Communication Protocol:
 * - Serial: 115200 baud
 * - Commands include sequence numbers and checksums for reliability
 * - Responses echo command sequence for synchronization
 * 
 * Main Commands:
 * - TESTSEQ:1,2,3:500;OFF:100;7,8,9:500;OFF:100;...  Batch test sequence
 * - X           Turn all relays off (emergency stop)
 * - I           Get firmware identification
 * - B           Get button status (PRESSED/RELEASED)
 * - V           Get supply voltage without relay activation
 * - RESET_SEQ   Reset sequence numbers for synchronization
 * - GET_BOARD_TYPE  Returns board identifier
 */

#include <Wire.h>
#include <Adafruit_INA260.h>
#include <PCF8575.h>

// Hardware configuration
// ==========================================
// PCF8575 Pin Assignment Configuration
// ==========================================
// Hardware mapping:
// - P00-P07 (bits 0-7): Relays 1-8
// - P10-P15 (bits 8-13): Relays 9-14
// - P16 (bit 14): Button input
// - P17 (bit 15): Unused (keep high)

#define BUTTON_BIT        14                  // P16 = bit 14
#define BUTTON_MASK       (1U << BUTTON_BIT)  // 0x4000

// Relay bits: 0-13 for relays 1-14
#define RELAY_BITS_MASK   0x3FFF              // bits 0-13
#define UNUSED_BITS_MASK  0x8000              // bit 15 (P17)

#define MAX_RELAYS 14          // Relays use P0-P13, P16 is button
#define MAX_SEQUENCE_STEPS 50  // Maximum steps in a test sequence
#define PCF8575_ADDRESS 0x20   // I2C address of PCF8575
#define INA260_ADDRESS 0x40    // I2C address of INA260
#define STABILIZATION_TIME 50  // ms to wait after relay activation
#define MEASUREMENT_TIME 2     // ms for INA260 conversion
#define MIN_DURATION 100       // ms minimum total duration
#define MAX_RESPONSE_SIZE 1024 // Response buffer size
#define MAX_SIMULTANEOUS_RELAYS 8  // Safety limit for simultaneous relays
#define SEQUENCE_TIMEOUT 30000     // Maximum sequence duration (30 seconds)

// Relay configuration - IMPORTANT: Check your relay module documentation!
// Most relay modules are active LOW (relay turns ON when signal is LOW)
// Some solid-state relays are active HIGH (relay turns ON when signal is HIGH)
const bool RELAY_ACTIVE_LOW = true;  // Set false if relays are active HIGH
const bool RELAY_ON = RELAY_ACTIVE_LOW ? LOW : HIGH;
const bool RELAY_OFF = RELAY_ACTIVE_LOW ? HIGH : LOW;

// Pin definitions (relays and button now controlled via PCF8575)
const int LED_PIN = LED_BUILTIN;

// I2C devices
PCF8575 pcf8575(PCF8575_ADDRESS);
Adafruit_INA260 ina260 = Adafruit_INA260();
bool pcf8575_available = false;
bool INA_OK = false;

// Test sequence structure
struct TestStep {
    uint16_t relayMask;     // Bitmask of relays to activate
    uint16_t duration_ms;   // Total duration including stabilization
    bool is_off;            // True for OFF command (all relays off)
};

// Button state tracking
bool lastButtonState = HIGH;
bool currentButtonPressed = false;
unsigned long lastButtonTime = 0;
const unsigned long DEBOUNCE_DELAY = 50;

// Global sequence tracking (unified with Offroad firmware)
uint16_t lastReceivedSeq = 0;      // Last sequence number received from host
uint16_t responseSeq = 0;          // Sequence to echo back in CMDSEQ
uint16_t globalSequenceNumber = 0;  // Auto-incrementing sequence for all responses

// I2C retry configuration
const int I2C_RETRY_DELAY_MS = 5;
const int MAX_I2C_RETRIES = 3;

// Parse command with reliability format (unified with Offroad)
struct ParsedCommand {
    String command;
    uint16_t sequence;
    uint8_t checksum;
    bool hasReliability;
};

// Function prototypes
void executeTestSequence(const char* sequence, unsigned int seq = 0);
int parseTestSequence(const char* sequence, TestStep steps[]);
uint16_t parseRelaysToBitmask(const char* relayList);
void maskToRelayList(uint16_t mask, char* output);
bool takeMeasurement(float* voltage, float* current);
void setRelayMask(uint16_t mask);
void getSupplyVoltage(unsigned int seq = 0);
void allRelaysOff();
void checkButton();
byte calculateChecksum(String data);
String formatChecksum(byte checksum);
void sendReliableResponse(const String& data, uint16_t seq = 0);
ParsedCommand parseReliableCommand(const String& cmdStr);
void processCommand(String command);
bool recoverI2C();
bool validateRelayMask(uint16_t mask);
int countSetBits(uint16_t mask);

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(25);
  
  // Wait for USB serial port to connect
  unsigned long t0 = millis();
  while (!Serial && (millis() - t0 < 5000)) { }
  
  // Initialize I2C
  Wire.begin();
  Wire.setClock(100000);  // Set I2C to 100kHz (standard mode)
  delay(50);  // Allow I2C bus to stabilize
  
  // Report I2C initialization starting
  Serial.println("I2C:INIT:START");
  
  // Initialize PCF8575 (required for relay control)
  Wire.beginTransmission(PCF8575_ADDRESS);
  uint8_t pcf_error = Wire.endTransmission();
  if (pcf_error == 0) {
    pcf8575.begin();
    pcf8575_available = true;
    
    // Initialize with all relays off, button and unused pins high
    uint16_t initial_state = 0;
    
    if (RELAY_ACTIVE_LOW) {
      // Active low: relay bits HIGH = off
      initial_state |= RELAY_BITS_MASK;
    }
    // Always set button and unused pins HIGH
    initial_state |= BUTTON_MASK | UNUSED_BITS_MASK;
    
    pcf8575.write16(initial_state);
    Serial.println("I2C:PCF8575:OK:0x20");
  } else {
    Serial.print("I2C:PCF8575:FAIL:0x20:ERROR_");
    Serial.println(pcf_error);
    pcf8575_available = false;
  }
  
  // Button is now read from PCF8575 P16, no Arduino pin setup needed
  
  // Initialize LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  
  // Initialize INA260 (optional - don't block if missing)
  Wire.beginTransmission(INA260_ADDRESS);
  uint8_t ina_error = Wire.endTransmission();
  if (ina_error == 0) {
    INA_OK = ina260.begin();
    if (INA_OK) {
      // Set INA260 for fast conversion
      ina260.setMode(INA260_MODE_CONTINUOUS);
      ina260.setCurrentConversionTime(INA260_TIME_140_us);
      ina260.setVoltageConversionTime(INA260_TIME_140_us);
      ina260.setAveragingCount(INA260_COUNT_1);
      Serial.println("I2C:INA260:OK:0x40");
    } else {
      Serial.println("I2C:INA260:FAIL:0x40:INIT_ERROR");
    }
  } else {
    INA_OK = false;
    Serial.print("I2C:INA260:FAIL:0x40:ERROR_");
    Serial.println(ina_error);
  }
  
  // Report I2C initialization complete with summary
  Serial.print("I2C:INIT:COMPLETE:");
  Serial.print(pcf8575_available ? "PCF8575_OK" : "PCF8575_FAIL");
  Serial.print(",");
  Serial.println(INA_OK ? "INA260_OK" : "INA260_FAIL");
  
  if (pcf8575_available) {
    Serial.println("SMT_TESTER_V2_READY");
  } else {
    Serial.println("SMT_TESTER_V2_ERROR:NO_RELAY_CONTROL");
  }
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
  
  if (baseCommand.startsWith("TESTSEQ:")) {
    // New batch test sequence command
    if (!pcf8575_available) {
      sendReliableResponse("ERROR:I2C_FAIL", responseSeq);
    } else {
      executeTestSequence(baseCommand.substring(8).c_str(), responseSeq);
    }
  }
  else if (baseCommand == "X") {
    // Emergency stop - turn all relays off
    allRelaysOff();
    sendReliableResponse("OK:ALL_OFF", responseSeq);
  }
  else if (baseCommand == "GET_BOARD_TYPE") {
    // Return board identifier for compatibility
    sendReliableResponse("BOARD_TYPE:SMT_TESTER", responseSeq);
  }
  else if (baseCommand == "I") {
    // Get board info
    sendReliableResponse("ID:SMT_TESTER_V2.0_14RELAY_PCF8575", responseSeq);
  }
  else if (baseCommand == "B") {
    // Get current button status
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
    // Reset sequence numbers
    globalSequenceNumber = 0;
    lastReceivedSeq = 0;
    responseSeq = parsed.hasReliability ? parsed.sequence : 0;
    sendReliableResponse("OK:SEQ_RESET", responseSeq);
  }
  else if (baseCommand == "I2C_STATUS") {
    // Report I2C device status
    String status = "I2C_STATUS:";
    status += "PCF8575@0x20=";
    status += pcf8575_available ? "OK" : "FAIL";
    status += ",INA260@0x40=";
    status += INA_OK ? "OK" : "FAIL";
    sendReliableResponse(status, responseSeq);
  }
  else if (baseCommand.startsWith("RELAY:")) {
    // Manual relay control for debugging: RELAY:1:ON or RELAY:1:OFF
    String params = baseCommand.substring(6);
    int colonPos = params.indexOf(':');
    if (colonPos > 0) {
      int relayNum = params.substring(0, colonPos).toInt();
      String state = params.substring(colonPos + 1);
      
      if (relayNum >= 1 && relayNum <= MAX_RELAYS) {
        if (state == "ON") {
          setRelayMask(1 << (relayNum - 1));
          sendReliableResponse("OK:RELAY_" + String(relayNum) + "_ON", responseSeq);
        } else if (state == "OFF") {
          setRelayMask(0);
          sendReliableResponse("OK:RELAY_" + String(relayNum) + "_OFF", responseSeq);
        } else {
          sendReliableResponse("ERROR:INVALID_STATE", responseSeq);
        }
      } else {
        sendReliableResponse("ERROR:INVALID_RELAY", responseSeq);
      }
    } else {
      sendReliableResponse("ERROR:INVALID_FORMAT", responseSeq);
    }
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

// Set relay state using bitmask
void setRelayMask(uint16_t mask) {
  if (!pcf8575_available) return;
  
  // Safety: only use bits designated for relays
  mask &= RELAY_BITS_MASK;
  
  uint16_t output;
  if (RELAY_ACTIVE_LOW) {
    // Start with all relay bits HIGH (off)
    output = RELAY_BITS_MASK;
    // Pull selected relays LOW (on)
    output &= ~mask;
  } else {
    // Active high: directly use mask
    output = mask;
  }
  
  // Critical: Always keep button bit HIGH (input mode)
  output |= BUTTON_MASK;
  
  // Keep unused bits HIGH to avoid floating inputs
  output |= UNUSED_BITS_MASK;
  
  pcf8575.write16(output);
}

// Validate relay mask for safety
bool validateRelayMask(uint16_t mask) {
  // Ensure mask only uses relay bits
  if (mask & ~RELAY_BITS_MASK) {
    return false;  // Mask tries to use non-relay bits
  }
  
  // Check maximum simultaneous relays
  if (countSetBits(mask) > MAX_SIMULTANEOUS_RELAYS) {
    return false;
  }
  
  return true;
}

// Count number of set bits in mask
int countSetBits(uint16_t mask) {
  int count = 0;
  while (mask) {
    count += mask & 1;
    mask >>= 1;
  }
  return count;
}

// Take measurement with INA260
bool takeMeasurement(float* voltage, float* current) {
  if (!INA_OK) {
    if (!recoverI2C()) {
      return false;
    }
  }
  
  // Wait for measurement to stabilize
  delay(MEASUREMENT_TIME);
  
  // Try to read with retry logic
  for (int retry = 0; retry < MAX_I2C_RETRIES; retry++) {
    Wire.beginTransmission(INA260_ADDRESS);
    if (Wire.endTransmission() == 0) {
      float v = ina260.readBusVoltage();
      float c = ina260.readCurrent();
      
      if (!isnan(v) && !isnan(c) && v >= 0) {
        *voltage = v / 1000.0;  // Convert mV to V
        *current = c / 1000.0;  // Convert mA to A
        
        // Validate ranges
        if (*voltage >= 0 && *voltage <= 30 && 
            *current >= 0 && *current <= 10) {
          return true;
        }
      }
    }
    
    if (retry < MAX_I2C_RETRIES - 1) {
      delay(I2C_RETRY_DELAY_MS);
      recoverI2C();
    }
  }
  
  return false;
}

// Parse comma-separated relay list to bitmask
uint16_t parseRelaysToBitmask(const char* relayList) {
  uint16_t mask = 0;
  char buffer[50];
  strncpy(buffer, relayList, sizeof(buffer) - 1);
  buffer[sizeof(buffer) - 1] = '\0';
  
  char* saveptr2;
  char* token = strtok_r(buffer, ",", &saveptr2);
  while (token != NULL) {
    int relay = atoi(token);
    if (relay >= 1 && relay <= MAX_RELAYS) {
      mask |= (1 << (relay - 1));
    }
    token = strtok_r(NULL, ",", &saveptr2);
  }
  
  return mask;
}

// Convert bitmask to relay list string
void maskToRelayList(uint16_t mask, char* output) {
  output[0] = '\0';
  bool first = true;
  
  for (int i = 0; i < MAX_RELAYS; i++) {
    if (mask & (1 << i)) {
      if (!first) strcat(output, ",");
      char num[4];
      sprintf(num, "%d", i + 1);
      strcat(output, num);
      first = false;
    }
  }
}



void allRelaysOff() {
  if (pcf8575_available) {
    setRelayMask(0x0000);  // All relays off
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
  if (!pcf8575_available) return;
  
  uint16_t pcfState = pcf8575.read16();
  // Check the correct bit for P16
  bool currentState = (pcfState & BUTTON_MASK) ? HIGH : LOW;
  
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


// Execute test sequence from TESTSEQ command
void executeTestSequence(const char* sequence, unsigned int seq) {
  if (!pcf8575_available) {
    sendReliableResponse("ERROR:I2C_FAIL", seq);
    return;
  }
  
  TestStep steps[MAX_SEQUENCE_STEPS];
  int stepCount = parseTestSequence(sequence, steps);
  
  if (stepCount == 0) {
    sendReliableResponse("ERROR:INVALID_SEQUENCE", seq);
    return;
  }
  
  if (stepCount > MAX_SEQUENCE_STEPS) {
    sendReliableResponse("ERROR:SEQUENCE_TOO_LONG", seq);
    return;
  }
  
  // Send immediate ACK to let host know we're processing
  sendReliableResponse("ACK", seq);
  
  // Pre-allocate response buffer
  char response[1024];
  strcpy(response, "TESTRESULTS:");
  
  unsigned long sequenceStart = millis();
  
  for (int i = 0; i < stepCount; i++) {
    // Check for timeout
    if (millis() - sequenceStart > SEQUENCE_TIMEOUT) {
      setRelayMask(0);  // Safety: turn off all relays
      sendReliableResponse("ERROR:SEQUENCE_TIMEOUT", seq);
      return;
    }
    
    // Check for emergency stop
    if (Serial.available() && Serial.peek() == 'X') {
      setRelayMask(0);
      Serial.read();  // Consume the 'X'
      sendReliableResponse("OK:ALL_OFF", seq);
      return;
    }
    
    if (steps[i].is_off) {
      // OFF command - turn all relays off and delay
      setRelayMask(0);
      delay(steps[i].duration_ms);
    } else {
      // Validate relay mask
      if (!validateRelayMask(steps[i].relayMask)) {
        setRelayMask(0);
        sendReliableResponse("ERROR:TOO_MANY_RELAYS", seq);
        return;
      }
      
      // Activate relays
      setRelayMask(steps[i].relayMask);
      
      // Wait for stabilization
      delay(STABILIZATION_TIME);
      
      // Take measurement
      float voltage, current;
      if (takeMeasurement(&voltage, &current)) {
        // Add to response
        char measurement[50];
        char relayList[30];
        maskToRelayList(steps[i].relayMask, relayList);
        sprintf(measurement, "%s:%.3fV,%.3fA;", relayList, voltage, current);
        
        // Check buffer space
        if (strlen(response) + strlen(measurement) < sizeof(response) - 10) {
          strcat(response, measurement);
        }
      } else {
        setRelayMask(0);
        sendReliableResponse("ERROR:MEASUREMENT_FAIL", seq);
        return;
      }
      
      // Hold for remaining duration
      int remaining = steps[i].duration_ms - STABILIZATION_TIME - MEASUREMENT_TIME;
      if (remaining > 0) {
        delay(remaining);
      }
      
      // Turn off relays
      setRelayMask(0);
    }
  }
  
  strcat(response, "END");
  sendReliableResponse(response, seq);
}

// Parse test sequence string into steps
// Format: "1,2,3:500;OFF:100;7,8,9:500;OFF:100"
int parseTestSequence(const char* sequence, TestStep steps[]) {
  int stepCount = 0;
  char buffer[500];
  strncpy(buffer, sequence, sizeof(buffer) - 1);
  buffer[sizeof(buffer) - 1] = '\0';
  
  uint16_t lastActiveMask = 0;  // Track last active relay mask
  
  char* saveptr1;
  char* stepToken = strtok_r(buffer, ";", &saveptr1);
  while (stepToken != NULL && stepCount < MAX_SEQUENCE_STEPS) {
    // Find the colon separator
    char* colonPos = strchr(stepToken, ':');
    if (colonPos == NULL) {
      return 0;  // Invalid format
    }
    
    *colonPos = '\0';  // Split at colon
    char* relayPart = stepToken;
    char* durationPart = colonPos + 1;
    
    // Parse duration
    int duration = atoi(durationPart);
    
    // Check if this is an OFF command
    bool isOffCmd = (strcmp(relayPart, "OFF") == 0);
    
    // Only enforce MIN_DURATION for relay-ON steps, not OFF steps
    if (!isOffCmd && duration < MIN_DURATION) {
      return 0;  // Duration too short for relay activation
    }
    
    if (isOffCmd) {
      // OFF command - allow any duration including 0
      steps[stepCount].relayMask = 0;
      steps[stepCount].duration_ms = duration;
      steps[stepCount].is_off = true;
      lastActiveMask = 0;  // OFF clears active relays
    } else {
      // Parse relay list
      uint16_t mask = parseRelaysToBitmask(relayPart);
      if (mask == 0) {
        return 0;  // No valid relays
      }
      
      // Note: Relay overlap check removed - different relay groups can be activated
      // sequentially as long as they don't conflict electrically
      
      steps[stepCount].relayMask = mask;
      steps[stepCount].duration_ms = duration;
      steps[stepCount].is_off = false;
      lastActiveMask = mask;  // Update last active mask
    }
    
    stepCount++;
    stepToken = strtok_r(NULL, ";", &saveptr1);
  }
  
  return stepCount;
}
