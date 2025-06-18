/*
 * SMT Simple Tester - Simplified Arduino firmware for SMT board testing
 * Version: 1.0.1
 * 
 * Commands:
 * - R1-R8: Measure specific relay (returns voltage and current)
 * - X: Turn all relays off
 * - I: Get board ID/info
 * - B: Get button status
 * 
 * Response format: Simple text without CRC or framing
 * Target timing: <100ms per relay measurement
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

// Button state tracking
bool lastButtonState = HIGH;
bool buttonPressed = false;
unsigned long lastButtonTime = 0;
const unsigned long DEBOUNCE_DELAY = 50;

// Timing constants
const int RELAY_STABILIZATION_MS = 15;
const int MEASUREMENT_SAMPLES = 6;
const int SAMPLE_INTERVAL_MS = 17;

void setup() {
  Serial.begin(115200);
  
  // Wait for USB serial port to connect (needed for native USB boards)
  while (!Serial && millis() < 3000) ;
  delay(100); // Extra delay to ensure stable connection
  
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
  
  // Initialize INA260
  if (!ina260.begin()) {
    Serial.println("ERROR:INA260_INIT_FAILED");
    while (1) delay(10);
  }
  
  // Set INA260 to fastest conversion time for better performance
  ina260.setMode(INA260_MODE_CONTINUOUS);
  ina260.setCurrentConversionTime(INA260_TIME_140_us);
  ina260.setVoltageConversionTime(INA260_TIME_140_us);
  ina260.setAveragingCount(INA260_COUNT_1);
  
  Serial.println("SMT_SIMPLE_TESTER_READY");
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
  
  if (command.startsWith("R") && command.length() == 2) {
    // Relay measurement command (R1-R8)
    int relayNum = command.charAt(1) - '1';
    if (relayNum >= 0 && relayNum < 8) {
      measureRelay(relayNum);
    } else {
      Serial.println("ERROR:INVALID_RELAY");
    }
  }
  else if (command == "X") {
    // Turn all relays off
    allRelaysOff();
    Serial.println("OK:ALL_OFF");
  }
  else if (command == "I") {
    // Get board info
    Serial.println("ID:SMT_SIMPLE_TESTER_V1.0");
  }
  else if (command == "B") {
    // Get button status
    bool currentState = digitalRead(BUTTON_PIN) == LOW;
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

void measureRelay(int relayIndex) {
  // Turn on the specific relay
  digitalWrite(RELAY_PINS[relayIndex], RELAY_ON);
  
  // Wait for relay to stabilize
  delay(RELAY_STABILIZATION_MS);
  
  // Take multiple samples for accuracy
  float totalVoltage = 0;
  float totalCurrent = 0;
  
  for (int i = 0; i < MEASUREMENT_SAMPLES; i++) {
    totalVoltage += ina260.readBusVoltage();
    totalCurrent += ina260.readCurrent();
    
    if (i < MEASUREMENT_SAMPLES - 1) {
      delay(SAMPLE_INTERVAL_MS);
    }
  }
  
  // Turn off the relay
  digitalWrite(RELAY_PINS[relayIndex], RELAY_OFF);
  
  // Calculate averages
  float avgVoltage = totalVoltage / MEASUREMENT_SAMPLES;
  float avgCurrent = totalCurrent / MEASUREMENT_SAMPLES;
  
  // Send response in simple format: R[num]:voltage,current
  Serial.print("R");
  Serial.print(relayIndex + 1);
  Serial.print(":");
  Serial.print(avgVoltage, 3);
  Serial.print(",");
  Serial.println(avgCurrent, 3);
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