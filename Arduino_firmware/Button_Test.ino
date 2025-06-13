/* Simple Button Test for Pin 10
 * Upload this to test if your button is working correctly
 * Open Serial Monitor at 115200 baud
 * Press and release the button to see state changes
 */

const int BUTTON_PIN = 10;
bool lastButtonState = HIGH;
bool buttonPressed = false;

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000); // Wait for serial
  
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  delay(100); // Let pullup stabilize
  
  lastButtonState = digitalRead(BUTTON_PIN);
  buttonPressed = (lastButtonState == LOW);
  
  Serial.println("=== Button Test on Pin 10 ===");
  Serial.println("Press and release the button to test");
  Serial.print("Initial button state: ");
  Serial.println(buttonPressed ? "PRESSED" : "RELEASED");
  Serial.println();
}

void loop() {
  bool currentState = digitalRead(BUTTON_PIN);
  
  if (currentState != lastButtonState) {
    delay(50); // Simple debounce
    
    currentState = digitalRead(BUTTON_PIN);
    if (currentState != lastButtonState) {
      lastButtonState = currentState;
      buttonPressed = (currentState == LOW);
      
      Serial.print("Button ");
      Serial.print(buttonPressed ? "PRESSED" : "RELEASED");
      Serial.print(" - Pin reads: ");
      Serial.println(currentState ? "HIGH" : "LOW");
    }
  }
}
