/*
 * SMT Simple Tester - Batch-only Arduino firmware for SMT board testing
 * Version: 2.0.0
 * 
 * Commands:
 * - T: Test entire panel (returns all relay measurements)
 * - TS: Test panel with streaming updates
 * - X: Turn all relays off
 * - I: Get board ID/info
 * - B: Get button status
 * 
 * REMOVED: Individual relay commands (R1-R8) for simplification
 * 
 * Response format: Simple text without CRC or framing
 * All measurements sent in Volts and Amps (not millivolts/milliamps)
 */

#include <Wire.h>
#include <Adafruit_INA260.h>

// Relay logic configuration
// For active-LOW relay modules (most common):
const bool RELAY_ON = LOW;   // Change to HIGH if using active-HIGH relays
const bool RELAY_OFF = HIGH;  // Change to LOW if using active-HIGH relays

// Pin definitions
const int RELAY_PINS[] = {2, 3, 4, 5, 6, 7, 8, 9}; // Relay control pins
const int BUTTON_PIN = 10;
const int LED_PIN = LED_BUILTIN;

// INA260 sensor
Adafruit_INA260 ina260 = Adafruit_INA260();
bool INA_OK = false;  // Global flag to track if sensor is available

// Button state tracking
bool lastButtonState = HIGH;
bool buttonPressed = false;
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
  for (int i = 0; i < 8; i++) {
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
  
  Serial.println("SMT_BATCH_TESTER_READY");
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
  
  if (command == "T") {
    // Test entire panel - batch mode
    testPanel();
  }
  else if (command == "TS") {
    // Test panel with streaming updates
    testPanelStream();
  }
  else if (command == "X") {
    // Turn all relays off
    allRelaysOff();
    Serial.println("OK:ALL_OFF");
  }
  else if (command == "I") {
    // Get board info
    Serial.println("ID:SMT_BATCH_TESTER_V2.0");
  }
  else if (command == "B") {
    // Get button status
    if (buttonPressed) {
      Serial.println("BUTTON:PRESSED");
      buttonPressed = false; // Clear the flag
    } else {
      Serial.println("BUTTON:RELEASED");
    }
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

// Test entire panel and return all results at once
void testPanel() {
  String result = "PANEL:";
  
  for (int i = 0; i < 8; i++) {
    float voltage, current;
    measureRelayValues(i, voltage, current);
    
    // Append to result string
    if (i > 0) result += ";";
    result += String(voltage, 3) + "," + String(current, 3);
    
    // Small delay between relays
    if (i < 7) delay(INTER_RELAY_DELAY_MS);
  }
  
  Serial.println(result);
}

// Test panel with streaming updates
void testPanelStream() {
  for (int i = 0; i < 8; i++) {
    float voltage, current;
    measureRelayValues(i, voltage, current);
    
    // Send individual relay result
    Serial.print("RELAY:");
    Serial.print(i + 1);
    Serial.print(",");
    Serial.print(voltage, 3);
    Serial.print(",");
    Serial.println(current, 3);
    
    // Small delay between relays
    if (i < 7) delay(INTER_RELAY_DELAY_MS);
  }
  
  Serial.println("PANEL_COMPLETE");
}

void allRelaysOff() {
  for (int i = 0; i < 8; i++) {
    digitalWrite(RELAY_PINS[i], RELAY_OFF);
  }
}

void checkButton() {
  bool currentState = digitalRead(BUTTON_PIN);
  
  // Check for button press (HIGH to LOW transition with debounce)
  if (currentState != lastButtonState) {
    if (millis() - lastButtonTime > DEBOUNCE_DELAY) {
      if (currentState == LOW && lastButtonState == HIGH) {
        // Button was pressed
        buttonPressed = true;
      }
      lastButtonTime = millis();
    }
    lastButtonState = currentState;
  }
}
