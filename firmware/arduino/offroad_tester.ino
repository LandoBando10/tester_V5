/* ======================================================================
 * Offroad Tester - Arduino firmware for offroad lighting assembly testing
 * Version 1.0.0
 * 
 * Description:
 * This firmware controls a test fixture for automotive offroad lighting
 * assemblies. It performs electrical and optical validation of main beam
 * and backlight circuits, tests for air leaks in sealed assemblies, and
 * verifies RGBW color functionality.
 * 
 * Hardware Requirements:
 * - Arduino board with relay control outputs
 * - INA260 power monitor for voltage/current measurements
 * - VEML7700 ambient light sensor for illuminance measurements
 * - OPT4048 color sensor for chromaticity (x,y) measurements
 * - MPRLS pressure sensor for air leak testing
 * - Pneumatic valve control for pressure testing
 * - Button input for manual test triggering
 * 
 * Communication Protocol:
 * - Serial: 115200 baud
 * - SMT-style short commands with reliability (SEQ/CHK/END)
 * - Supports both legacy long commands and new short format
 * 
 * Main Test Types:
 * - TF/TEST:FUNCTION_TEST - Full electrical and optical test
 * - TP/TEST:PRESSURE - Air leak test with live pressure monitoring
 * - TR/TEST:RGBW_BACKLIGHT - RGBW color cycle verification
 * - TD/TEST:DUAL_BACKLIGHT - Dual backlight zone testing
 * =====================================================================*/
#include <Wire.h>
#include <avr/pgmspace.h>
#include <Adafruit_INA260.h>
#include <Adafruit_VEML7700.h>
#include <SparkFun_OPT4048_Arduino_Library.h>
#include <Adafruit_MPRLS.h>

/* --------------------------- Hardware Pins ----------------------------- */
constexpr uint8_t PIN_RELAY_MAIN = 5;
constexpr uint8_t PIN_RELAY_B1   = 3;
constexpr uint8_t PIN_RELAY_B2   = 4;
constexpr uint8_t PIN_VALVE      = 6;
constexpr uint8_t PIN_BUTTON     = 7;
constexpr bool    RELAY_ON       = LOW;
constexpr bool    RELAY_OFF      = HIGH;
constexpr bool    BTN_ACTIVE     = LOW;

/* --------------------------- Timing Constants -------------------------- */
constexpr uint16_t RELAY_STAB_MS = 50;
constexpr uint16_t SAMPLE_WINDOW_MS = 450;
constexpr uint8_t  MAX_SAMPLES = 10;
constexpr uint16_t SAMPLE_DELAY_MS = 25;
constexpr uint16_t PT_FILL_MS = 1500;
constexpr uint16_t PT_WAIT_MS = 2500;
constexpr uint16_t PT_EXH_MS = 500;
constexpr uint32_t STREAM_INTERVAL_MS = 100;

/* --------------------------- Sensor Objects ---------------------------- */
Adafruit_INA260   ina;
Adafruit_VEML7700 veml;
OPT4048           opt;
Adafruit_MPRLS    mpr;
bool sINA=false, sLux=false, sOPT=false, sMPR=false;

/* ---------------------------- Globals ---------------------------------- */
char curTest[24] = "";
char lastRunTestType[24] = "FUNCTION_TEST";
bool streamOn = false;
bool pythonOn = false;
uint32_t lastStreamTime = 0;
uint32_t lastButtonTime = 0;
bool lastButtonState = HIGH;

// Sequence tracking
uint16_t globalSequenceNumber = 0;
uint16_t responseSeq = 0;

// Simple sample structure
struct Sample { 
    float mv, mi, lux, x, y; 
};

// Pressure test state (only state machine we keep for live readings)
enum PressureState { P_IDLE, P_FILL, P_WAIT, P_EXHAUST };
PressureState pressureState = P_IDLE;
uint32_t pressurePhaseStart = 0;
float pressureInitial = 0;

/* --------------------------- Helper Functions -------------------------- */
String formatFloat(float val, int prec) {
    if (isnan(val)) return "0.000";
    return String(val, prec);
}

uint8_t calculateChecksum(const String& data) {
    uint8_t checksum = 0;
    for (size_t i = 0; i < data.length(); i++) {
        checksum ^= data[i];
    }
    return checksum;
}

String formatChecksum(uint8_t checksum) {
    char buf[3];
    sprintf(buf, "%02X", checksum);
    return String(buf);
}

void sendLine(const String& s) {
    Serial.println(s);
}

void sendReliableResponse(const String& data, uint16_t seq) {
    String response = data;
    
    globalSequenceNumber++;
    response += ":SEQ=" + String(globalSequenceNumber);
    
    if (seq > 0) {
        response += ":CMDSEQ=" + String(seq);
    }
    
    uint8_t checksum = calculateChecksum(response);
    response += ":CHK=" + formatChecksum(checksum) + ":END";
    
    sendLine(response);
}

/* --------------------------- Relay Control ----------------------------- */
void relaysOff() {
    digitalWrite(PIN_RELAY_MAIN, RELAY_OFF);
    digitalWrite(PIN_RELAY_B1, RELAY_OFF);
    digitalWrite(PIN_RELAY_B2, RELAY_OFF);
    digitalWrite(PIN_VALVE, HIGH);
}

/* --------------------------- Sensor Reading ---------------------------- */
bool readINA(float& v, float& i) {
    if (!sINA) {
        v = NAN;
        i = NAN;
        return false;
    }
    
    v = ina.readBusVoltage() / 1000.0f;
    i = ina.readCurrent() / 1000.0f;
    
    // Check if reading failed
    if (!isfinite(v) || !isfinite(i)) {
        v = NAN;
        i = NAN;
        return false;
    }
    
    return true;
}

float readLux() {
    return sLux ? veml.readLux() : NAN;
}

bool readXY(float& x, float& y) {
    if (!sOPT) {
        x = NAN;
        y = NAN;
        return false;
    }
    
    auto data = opt.readLuxData();
    x = data.x;
    y = data.y;
    
    if (!isfinite(x) || !isfinite(y)) {
        x = NAN;
        y = NAN;
        return false;
    }
    
    return true;
}

float readPSI() {
    return sMPR ? mpr.readPressure() * 0.0145038f : NAN;
}

/* --------------------------- Sensor Check ------------------------------ */
void checkSensors() {
    sINA = ina.begin();
    sLux = veml.begin();
    sOPT = opt.begin();
    sMPR = mpr.begin();
    
    if (sLux) {
        veml.setGain(VEML7700_GAIN_1);
        veml.setIntegrationTime(VEML7700_IT_100MS);
    }
    
    if (sOPT) {
        opt.setContinuousMode();
        opt.setIntegrationTime(OPT4048::IntegrationTime::Integration_100ms);
        opt.setChannelEnable(true);
    }
}

/* --------------------------- Sample Collection ------------------------- */
Sample collectSamples(int relay, int sampleCount) {
    Sample samples[MAX_SAMPLES];
    
    // Turn on relay
    digitalWrite(relay, RELAY_ON);
    delay(RELAY_STAB_MS);
    
    // Collect samples
    for (int i = 0; i < sampleCount; i++) {
        readINA(samples[i].mv, samples[i].mi);
        samples[i].lux = readLux();
        readXY(samples[i].x, samples[i].y);
        
        if (i < sampleCount - 1) {
            delay(SAMPLE_DELAY_MS);
        }
    }
    
    // Turn off relay
    digitalWrite(relay, RELAY_OFF);
    
    // Average the samples
    Sample avg = {0, 0, 0, 0, 0};
    int validCount = 0;
    
    for (int i = 0; i < sampleCount; i++) {
        if (!isnan(samples[i].mv)) {
            avg.mv += samples[i].mv;
            avg.mi += samples[i].mi;
            avg.lux += isnan(samples[i].lux) ? 0 : samples[i].lux;
            avg.x += isnan(samples[i].x) ? 0 : samples[i].x;
            avg.y += isnan(samples[i].y) ? 0 : samples[i].y;
            validCount++;
        }
    }
    
    if (validCount > 0) {
        avg.mv /= validCount;
        avg.mi /= validCount;
        avg.lux /= validCount;
        avg.x /= validCount;
        avg.y /= validCount;
    } else {
        avg.mv = avg.mi = avg.lux = avg.x = avg.y = NAN;
    }
    
    return avg;
}

/* --------------------------- Test Functions ---------------------------- */
void runFunctionTest(const String& testType) {
    if (curTest[0] != '\0') {
        sendLine("ERROR:TEST_IN_PROGRESS");
        return;
    }
    
    strncpy(curTest, testType.c_str(), sizeof(curTest) - 1);
    strncpy(lastRunTestType, testType.c_str(), sizeof(lastRunTestType) - 1);
    
    // Collect main beam samples
    Sample mainBeam = collectSamples(PIN_RELAY_MAIN, MAX_SAMPLES);
    delay(10);
    
    // Collect backlight samples
    Sample backlight = collectSamples(PIN_RELAY_B1, MAX_SAMPLES);
    
    // Format results based on test type
    char result[256];
    if (testType == "POWER") {
        snprintf(result, sizeof(result), "POWER:MAIN=%.3f,%.3f;BACK=%.3f,%.3f",
                 mainBeam.mv, mainBeam.mi, backlight.mv, backlight.mi);
    } else if (testType == "POWER_LUX") {
        snprintf(result, sizeof(result), "POWER_LUX:MAIN=%.2f;BACK=%.2f",
                 mainBeam.lux, backlight.lux);
    } else if (testType == "POWER_COLOR") {
        snprintf(result, sizeof(result), "POWER_COLOR:MAIN=%.3f,%.3f;BACK=%.3f,%.3f",
                 mainBeam.x, mainBeam.y, backlight.x, backlight.y);
    } else { // FUNCTION_TEST
        snprintf(result, sizeof(result), "TESTF:MAIN=%.3f,%.3f,%.2f,%.3f,%.3f;BACK=%.3f,%.3f,%.2f,%.3f,%.3f",
                 mainBeam.mv, mainBeam.mi, mainBeam.lux, mainBeam.x, mainBeam.y,
                 backlight.mv, backlight.mi, backlight.lux, backlight.x, backlight.y);
    }
    
    sendReliableResponse(String(result), responseSeq);
    sendLine("TEST_COMPLETE:" + testType);
    curTest[0] = '\0';
}

void beginPressureTest() {
    if (!sMPR) {
        sendLine("ERROR:SENSOR_MISSING:MPRLS");
        return;
    }
    if (curTest[0] != '\0') {
        sendLine("ERROR:TEST_IN_PROGRESS");
        return;
    }
    
    strncpy(curTest, "PRESSURE", sizeof(curTest) - 1);
    strncpy(lastRunTestType, "PRESSURE", sizeof(lastRunTestType) - 1);
    
    pressureState = P_FILL;
    pressurePhaseStart = millis();
    digitalWrite(PIN_VALVE, LOW); // Open valve
}

void runRGBWTest() {
    if (curTest[0] != '\0') {
        sendLine("ERROR:TEST_IN_PROGRESS");
        return;
    }
    
    strncpy(curTest, "RGBW_BACKLIGHT", sizeof(curTest) - 1);
    strncpy(lastRunTestType, "RGBW_BACKLIGHT", sizeof(lastRunTestType) - 1);
    
    // Run 8 cycles
    for (int cycle = 0; cycle < 8; cycle++) {
        digitalWrite(PIN_RELAY_B1, RELAY_ON);
        delay(150); // Stabilization
        
        // Take 3 samples at specific times
        for (int sample = 0; sample < 3; sample++) {
            delay(sample == 0 ? 50 : 150); // 200ms, 350ms, 500ms from start
            
            float mv, mi, lux, x, y;
            readINA(mv, mi);
            lux = readLux();
            readXY(x, y);
            
            String s = "RGBW_SAMPLE:CYCLE=" + String(cycle + 1) +
                       ",VOLTAGE=" + formatFloat(mv, 3) + 
                       ",CURRENT=" + formatFloat(mi, 3) +
                       ",LUX=" + formatFloat(lux, 2) + 
                       ",X=" + formatFloat(x, 3) + 
                       ",Y=" + formatFloat(y, 3);
            sendLine(s);
        }
        
        digitalWrite(PIN_RELAY_B1, RELAY_OFF);
        delay(100); // Pause between cycles
    }
    
    sendLine("TEST_COMPLETE:RGBW_BACKLIGHT");
    curTest[0] = '\0';
}

void runDualBacklightTest() {
    if (curTest[0] != '\0') {
        sendLine("ERROR:TEST_IN_PROGRESS");
        return;
    }
    
    strncpy(curTest, "DUAL_BACKLIGHT", sizeof(curTest) - 1);
    strncpy(lastRunTestType, "DUAL_BACKLIGHT", sizeof(lastRunTestType) - 1);
    
    // Test B1
    Sample b1 = collectSamples(PIN_RELAY_B1, MAX_SAMPLES);
    delay(10);
    
    // Test B2
    Sample b2 = collectSamples(PIN_RELAY_B2, MAX_SAMPLES);
    
    // Send results
    char result[256];
    snprintf(result, sizeof(result), "DUAL:B1=%.3f,%.3f,%.2f,%.3f,%.3f;B2=%.3f,%.3f,%.2f,%.3f,%.3f",
             b1.mv, b1.mi, b1.lux, b1.x, b1.y,
             b2.mv, b2.mi, b2.lux, b2.x, b2.y);
    
    sendReliableResponse(String(result), responseSeq);
    sendLine("TEST_COMPLETE:DUAL_BACKLIGHT");
    curTest[0] = '\0';
}

/* --------------------------- Pressure Test Update ---------------------- */
void updatePressureTest() {
    if (pressureState == P_IDLE) return;
    
    uint32_t now = millis();
    uint32_t elapsed = now - pressurePhaseStart;
    
    switch (pressureState) {
        case P_FILL:
            if (elapsed >= PT_FILL_MS) {
                digitalWrite(PIN_VALVE, HIGH); // Close valve
                pressureInitial = readPSI();
                pressurePhaseStart = now;
                pressureState = P_WAIT;
            }
            break;
            
        case P_WAIT:
            // Send live pressure readings during wait phase
            if (streamOn && (now - lastStreamTime >= STREAM_INTERVAL_MS)) {
                String s = "LIVE:PSI=" + formatFloat(readPSI(), 3);
                sendLine(s);
                lastStreamTime = now;
            }
            
            if (elapsed >= PT_WAIT_MS) {
                float finalPressure = readPSI();
                float delta = pressureInitial - finalPressure;
                pressurePhaseStart = now;
                pressureState = P_EXHAUST;
                digitalWrite(PIN_VALVE, LOW); // Open to exhaust
                
                // Send result
                String result = "PRESSURE:" + formatFloat(pressureInitial, 3) + "," + formatFloat(delta, 3);
                sendReliableResponse(result, responseSeq);
            }
            break;
            
        case P_EXHAUST:
            if (elapsed >= PT_EXH_MS) {
                digitalWrite(PIN_VALVE, HIGH); // Close valve
                sendLine("TEST_COMPLETE:PRESSURE");
                curTest[0] = '\0';
                pressureState = P_IDLE;
            }
            break;
    }
}

/* --------------------------- Button Handling --------------------------- */
void checkButton() {
    bool currentState = digitalRead(PIN_BUTTON);
    
    if (currentState != lastButtonState) {
        lastButtonTime = millis();
    }
    
    if (millis() - lastButtonTime > 30) { // Debounce
        if (currentState == BTN_ACTIVE && lastButtonState != BTN_ACTIVE) {
            sendLine("EVENT:BUTTON_PRESSED");
            
            if (curTest[0] == '\0') { // No test running
                sendLine("TEST_STARTED:" + String(lastRunTestType));
                
                // Run the last test type
                if (strcmp(lastRunTestType, "PRESSURE") == 0) {
                    beginPressureTest();
                } else if (strcmp(lastRunTestType, "RGBW_BACKLIGHT") == 0) {
                    runRGBWTest();
                } else if (strcmp(lastRunTestType, "DUAL_BACKLIGHT") == 0) {
                    runDualBacklightTest();
                } else {
                    runFunctionTest(String(lastRunTestType));
                }
            }
        }
    }
    
    lastButtonState = currentState;
}

/* --------------------------- Stream Data ------------------------------- */
void streamData() {
    if (!streamOn || curTest[0] != '\0') return;
    if (millis() - lastStreamTime < STREAM_INTERVAL_MS) return;
    
    String data = "LIVE:";
    bool first = true;
    
    float v, i;
    if (readINA(v, i)) {
        data += "V=" + formatFloat(v, 3) + ",I=" + formatFloat(i, 3);
        first = false;
    }
    
    float lux = readLux();
    if (!isnan(lux)) {
        if (!first) data += ",";
        data += "LUX=" + formatFloat(lux, 2);
        first = false;
    }
    
    float x, y;
    if (readXY(x, y)) {
        if (!first) data += ",";
        data += "X=" + formatFloat(x, 3) + ",Y=" + formatFloat(y, 3);
        first = false;
    }
    
    float psi = readPSI();
    if (!isnan(psi)) {
        if (!first) data += ",";
        data += "PSI=" + formatFloat(psi, 3);
    }
    
    if (data.length() > 5) {
        sendLine(data);
    }
    
    lastStreamTime = millis();
}

/* --------------------------- Command Parsing --------------------------- */
struct ParsedCommand {
    String command;
    uint16_t sequence;
    uint8_t checksum;
    bool hasReliability;
};

ParsedCommand parseCommand(const String& cmdStr) {
    ParsedCommand parsed;
    parsed.hasReliability = false;
    parsed.sequence = 0;
    
    int seqPos = cmdStr.indexOf(":SEQ=");
    int chkPos = cmdStr.indexOf(":CHK=");
    
    if (seqPos > 0 && chkPos > seqPos) {
        parsed.command = cmdStr.substring(0, seqPos);
        
        int seqEnd = cmdStr.indexOf(':', seqPos + 5);
        if (seqEnd > 0) {
            parsed.sequence = cmdStr.substring(seqPos + 5, seqEnd).toInt();
        }
        
        String chkStr = cmdStr.substring(chkPos + 5, chkPos + 7);
        parsed.checksum = strtoul(chkStr.c_str(), NULL, 16);
        parsed.hasReliability = true;
        
        // Verify checksum
        String dataToCheck = cmdStr.substring(0, chkPos);
        uint8_t calcChecksum = calculateChecksum(dataToCheck);
        if (calcChecksum != parsed.checksum) {
            parsed.command = ""; // Invalid
        }
    } else {
        parsed.command = cmdStr;
    }
    
    return parsed;
}

/* --------------------------- Command Handler --------------------------- */
void handleCommand(const String& cmdStr) {
    ParsedCommand parsed = parseCommand(cmdStr);
    
    if (cmdStr.indexOf(":CHK=") > 0 && parsed.command.isEmpty()) {
        sendReliableResponse("ERROR:BAD_CHECKSUM", 0);
        return;
    }
    
    String cmd = parsed.command;
    responseSeq = parsed.hasReliability ? parsed.sequence : 0;
    
    // ID commands
    if (cmd == "I" || cmd == "ID" || cmd == "PING") {
        pythonOn = true;
        sendReliableResponse("ID:OFFROAD_TESTER_V1.0", responseSeq);
        return;
    }
    
    // Basic status commands
    if (cmd == "V") {
        float voltage = sINA ? ina.readBusVoltage() / 1000.0f : NAN;
        sendReliableResponse("VOLTAGE:" + formatFloat(voltage, 3), responseSeq);
        return;
    }
    
    if (cmd == "B") {
        String state = digitalRead(PIN_BUTTON) == BTN_ACTIVE ? "PRESSED" : "RELEASED";
        sendReliableResponse("BUTTON:" + state, responseSeq);
        return;
    }
    
    if (cmd == "X") {
        relaysOff();
        curTest[0] = '\0';
        streamOn = false;
        pressureState = P_IDLE;
        sendReliableResponse("OK:ALL_OFF", responseSeq);
        return;
    }
    
    // Sensor check
    if (cmd == "S" || cmd == "SENSOR_CHECK") {
        checkSensors();
        sendReliableResponse("OK:SENSOR_CHECK", responseSeq);
        return;
    }
    
    // Monitoring
    if (cmd == "M:1" || cmd == "STREAM:ON") {
        streamOn = true;
        pythonOn = true;
        sendReliableResponse("OK:MONITORING_ON", responseSeq);
        return;
    }
    
    if (cmd == "M:0" || cmd == "STREAM:OFF") {
        streamOn = false;
        sendReliableResponse("OK:MONITORING_OFF", responseSeq);
        return;
    }
    
    // Test commands
    if (cmd == "TF" || cmd == "TEST:FUNCTION_TEST") {
        runFunctionTest("FUNCTION_TEST");
        return;
    }
    
    if (cmd == "TP" || cmd == "TEST:PRESSURE") {
        beginPressureTest();
        return;
    }
    
    if (cmd == "TR" || cmd == "TEST:RGBW_BACKLIGHT") {
        runRGBWTest();
        return;
    }
    
    if (cmd == "TD" || cmd == "TEST:DUAL_BACKLIGHT") {
        runDualBacklightTest();
        return;
    }
    
    // Power test variants
    if (cmd.startsWith("TEST:")) {
        String testType = cmd.substring(5);
        if (testType == "POWER" || testType == "POWER_LUX" || testType == "POWER_COLOR") {
            runFunctionTest(testType);
            return;
        }
    }
    
    // Reset sequence
    if (cmd == "RESET_SEQ") {
        globalSequenceNumber = 0;
        responseSeq = 0;
        sendReliableResponse("OK:SEQ_RESET", responseSeq);
        return;
    }
    
    sendReliableResponse("ERROR:UNKNOWN_CMD:" + cmd, responseSeq);
}

/* -------------------------------- Setup -------------------------------- */
void setup() {
    Serial.begin(115200);
    Serial.setTimeout(25);
    
    // Initialize pins
    pinMode(PIN_RELAY_MAIN, OUTPUT);
    pinMode(PIN_RELAY_B1, OUTPUT);
    pinMode(PIN_RELAY_B2, OUTPUT);
    pinMode(PIN_VALVE, OUTPUT);
    pinMode(PIN_BUTTON, INPUT_PULLUP);
    relaysOff();
    
    // Initialize I2C
    Wire.begin();
    Wire.setTimeout(1000);
    Wire.setClock(400000);
    
    // Check sensors
    checkSensors();
    
    sendLine("=== Offroad Tester V5 Simplified ===");
}

/* -------------------------------- Loop --------------------------------- */
void loop() {
    // Handle serial commands
    if (Serial.available()) {
        String command = Serial.readStringUntil('\n');
        command.trim();
        if (command.length() > 0) {
            handleCommand(command);
        }
    }
    
    // Update pressure test if running
    updatePressureTest();
    
    // Check button
    checkButton();
    
    // Stream data if enabled
    streamData();
    
    delay(1);
}