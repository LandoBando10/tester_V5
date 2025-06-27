/*
 * SMT Simple Tester - 16-relay Arduino firmware for SMT board testing
 * Version: 3.0.0
 * 
 * Commands:
 * - TX:1,2,5,6: Test specific relays (supports comma-separated and ranges)
 * - TX:ALL: Test all 16 relays
 * - X: Turn all relays off
 * - I: Get board ID/info
 * - B: Get button status
 * - V: Get supply voltage (no relay activation)
 * 
 * Events (sent automatically):
 * - EVENT:BUTTON_PRESSED - Sent when button is pressed
 * - EVENT:BUTTON_RELEASED - Sent when button is released
 * 
 * Response format:
 * - TX command: PANELX:1=v1,i1;2=v2,i2;...
 * 
 * Examples:
 * - TX:1,2,5,6 - Test relays 1, 2, 5, and 6
 * - TX:1-4,9-12 - Test relays 1-4 and 9-12
 * - TX:1-8 - Test relays 1-8 (replaces old T command)
 * - TX:ALL - Test all 16 relays
 * 
 * v3.0.0: 16-relay support only, no backward compatibility
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
  10, 11, 12, 13, 14, 15, 16, 17 // Relays 9-16 (pin 10-13, A0-A3)
};
const int NUM_RELAYS = 16;
const int BUTTON_PIN = 18; // A4 (moved from pin 10)
const int LED_PIN = LED_BUILTIN;

// INA260 sensor
Adafruit_INA260 ina260 = Adafruit_INA260();
bool INA_OK = false;  // Global flag to track if sensor is available

// Button state tracking
bool lastButtonState = HIGH;
bool currentButtonPressed = false;  // Current debounced state
unsigned long lastButtonTime = 0;
const unsigned long DEBOUNCE_DELAY = 50;

// Timing constants
const int RELAY_STABILIZATION_MS = 15;
const int MEASUREMENT_SAMPLES = 6;
const int SAMPLE_INTERVAL_MS = 17;
const int INTER_RELAY_DELAY_MS = 10;  // Delay between relay measurements

void setup() {
  Serial.begin(115200);
  
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

void processCommand(String command) {
  digitalWrite(LED_PIN, HIGH); // Indicate activity
  
  if (command.startsWith("TX:")) {
    // Test specific relays (the only test command)
    testPanelSelective(command.substring(3));
  }
  else if (command == "X") {
    // Turn all relays off
    allRelaysOff();
    Serial.println("OK:ALL_OFF");
  }
  else if (command == "I") {
    // Get board info
    Serial.println("ID:SMT_BATCH_TESTER_V3.0_16RELAY");
  }
  else if (command == "B") {
    // Get current button status (use debounced state)
    if (currentButtonPressed) {
      Serial.println("BUTTON:PRESSED");
    } else {
      Serial.println("BUTTON:RELEASED");
    }
  }
  else if (command == "V") {
    // Get supply voltage without turning on any relays
    getSupplyVoltage();
  }
  else {
    Serial.println("ERROR:UNKNOWN_COMMAND");
  }
  
  digitalWrite(LED_PIN, LOW);
}

// Measure relay and return values (for internal use)
void measureRelayValues(int relayIndex, float &voltage, float &current) {
  // Turn on the specific relay
  digitalWrite(RELAY_PINS[relayIndex], RELAY_ON);
  
  // Wait for relay to stabilize
  delay(RELAY_STABILIZATION_MS);
  
  // Take multiple samples for accuracy
  float totalVoltage = 0;
  float totalCurrent = 0;
  
  for (int i = 0; i < MEASUREMENT_SAMPLES; i++) {
    totalVoltage += INA_OK ? ina260.readBusVoltage() : 0.0;
    totalCurrent += INA_OK ? ina260.readCurrent() : 0.0;
    
    if (i < MEASUREMENT_SAMPLES - 1) {
      delay(SAMPLE_INTERVAL_MS);
    }
  }
  
  // Turn off the relay
  digitalWrite(RELAY_PINS[relayIndex], RELAY_OFF);
  
  // Calculate averages (convert mV to V and mA to A)
  voltage = totalVoltage / MEASUREMENT_SAMPLES / 1000.0;
  current = totalCurrent / MEASUREMENT_SAMPLES / 1000.0;
}



void allRelaysOff() {
  for (int i = 0; i < NUM_RELAYS; i++) {
    digitalWrite(RELAY_PINS[i], RELAY_OFF);
  }
}

// Get supply voltage without activating any relays
void getSupplyVoltage() {
  if (!INA_OK) {
    Serial.println("VOLTAGE:0.000");
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
  
  // Send result
  Serial.print("VOLTAGE:");
  Serial.println(voltage, 3);
  Serial.flush();  // Ensure complete transmission
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
        Serial.flush();  // Ensure immediate transmission
      } else if (currentState == HIGH && lastButtonState == LOW) {
        // Button was released
        currentButtonPressed = false;
        Serial.println("EVENT:BUTTON_RELEASED");
        Serial.flush();  // Ensure immediate transmission
      }
      lastButtonTime = millis();
    }
    lastButtonState = currentState;
  }
}


// Parse relay list and test specific relays
void testPanelSelective(String relayList) {
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
      Serial.println("ERROR:INVALID_RELAY_LIST");
      return;
    }
    
    if (relayCount == 0) {
      Serial.println("ERROR:EMPTY_RELAY_LIST");
      return;
    }
  }
  
  // Test selected relays
  String result = "PANELX:";
  bool firstRelay = true;
  
  for (int i = 0; i < NUM_RELAYS; i++) {
    if (relaysToTest[i]) {
      float voltage, current;
      measureRelayValues(i, voltage, current);
      
      // Append to result string with relay number
      if (!firstRelay) result += ";";
      result += String(i + 1) + "=" + String(voltage, 3) + "," + String(current, 3);
      firstRelay = false;
      
      // Small delay between relays
      if (relayCount > 1) delay(INTER_RELAY_DELAY_MS);
      relayCount--;
    }
  }
  
  Serial.println(result);
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
