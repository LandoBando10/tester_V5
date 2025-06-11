/* ======================================================================
 * TesterV4_Offroad
 * =====================================================================*/
#include <Wire.h>
#include <avr/pgmspace.h>
#include <Adafruit_INA260.h>
#include <Adafruit_VEML7700.h>
#include <SparkFun_OPT4048_Arduino_Library.h>
#include <Adafruit_MPRLS.h>
#include <math.h> // For isnan()

/* ------------------------- Compile switches ---------------------------- */
//#define DEBUG_MODE
#define CRC_MODE

/* ------------------------- Debug Macros -------------------------------- */
#ifdef DEBUG_MODE
  #define DPRINT(x)       Serial.print(F(x))
  #define DPRINTLN(x)     Serial.println(F(x))
  #define DVAR(l,v)       { Serial.print(F(l)); Serial.print(v); }
  #define DVARLN(l,v)     { Serial.print(F(l)); Serial.println(v); }
#else
  #define DPRINT(x)
  #define DPRINTLN(x)
  #define DVAR(l,v)
  #define DVARLN(l,v)
#endif

/* --------------------------- CRC-8 helper ------------------------------ */
#ifdef CRC_MODE
static uint8_t crc8(const char* d, size_t len) {
  uint8_t c = 0; while (len--) {
    c ^= *d++;
    for (uint8_t i=0;i<8;i++) c = (c & 0x80) ? (c<<1) ^ 0x07 : (c<<1);
  } return c;
}
void sendLine(const String& s) {
  Serial.print(s);
  #ifdef CRC_MODE
    uint8_t c = crc8(s.c_str(), s.length());
    Serial.print('*');
    if (c < 16) Serial.print('0'); // Ensure two hex digits
    Serial.print(c, HEX);
  #endif
  Serial.print('\r'); Serial.print('\n');
}
#else
  inline void sendLine(const String& s){ Serial.println(s); }
#endif

/* ----------------------------- Constants ------------------------------- */
constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint16_t I2C_TIMEOUT = 1000;
constexpr uint8_t  I2C_RETRY   = 3;
constexpr uint32_t HEARTBEAT_MS= 1000;
constexpr uint32_t STREAM_MS   = 100;   // 10 Hz
constexpr uint16_t RELAY_STAB_MS = 50;
constexpr uint16_t SAMPLE_WINDOW_MS = 450; // Duration of sampling after stabilization
constexpr uint8_t  MAX_SAMPLES = 10;
constexpr uint16_t SAMPLE_DELAY_MS = 25; // Target delay between samples
const uint16_t RGBW_SAMPLE_PTS[] PROGMEM = {200, 350, 450};
constexpr uint16_t RGBW_CYCLE_MS = 800; // Total duration of one RGBW light ON phase
constexpr uint8_t  RGBW_TOTAL_CYCLES = 8;
constexpr uint16_t RGBW_STAB_MS = 150; // Stabilization for RGBW before sampling window

/* --------------------------- Hardware Pins ----------------------------- */
constexpr uint8_t PIN_RELAY_MAIN = 5;
constexpr uint8_t PIN_RELAY_B1   = 3;
constexpr uint8_t PIN_RELAY_B2   = 4;
constexpr uint8_t PIN_VALVE      = 6;
constexpr uint8_t PIN_BUTTON     = 7;
constexpr bool    RELAY_ON       = LOW;
constexpr bool    RELAY_OFF      = HIGH;
constexpr bool    BTN_ACTIVE     = LOW;

/* --------------------------- Sensor Objects ---------------------------- */
Adafruit_INA260   ina;
Adafruit_VEML7700 veml; // Changed from lux to veml to avoid conflict with Sample.lux
OPT4048           opt;
Adafruit_MPRLS    mpr;
bool sINA=false, sLux=false, sOPT=false, sMPR=false;

/* ---------------------------- Globals ---------------------------------- */
static char curTest[24] = ""; // Currently running test name
static char lastRunTestType[24] = "FUNCTION_TEST"; // For button press
bool streamOn=false, pythonOn=false;

// Data types
struct Sample { float mv, mi, lux, x, y; };
static Sample sampMain[MAX_SAMPLES]; // Re-usable buffers for tests
static Sample sampBack[MAX_SAMPLES];


/* ---------------------- Simple Task Scheduler -------------------------- */
struct Task { uint32_t period; uint32_t last; void (*fn)(); };

void taskHeartbeat();
void taskStream();
void taskButton();
void taskPressure();
void taskFunctionTest();
void taskRGBWTest();
void taskDualBacklightTest();

Task tasks[] = {
  {HEARTBEAT_MS, 0, taskHeartbeat},
  {STREAM_MS,    0, taskStream},
  {10,           0, taskButton},          // 100 Hz for button debounce
  {5,            0, taskPressure},        // Fast tick for state machines
  {5,            0, taskFunctionTest},
  {5,            0, taskRGBWTest},
  {5,            0, taskDualBacklightTest}
};

/* --------------------------- I2C wrapper ------------------------------- */
struct I2CStat{ uint8_t err=0; uint32_t t=0; bool rst=false; }i2c;
inline bool i2cPing(uint8_t a) {
  if(i2c.rst){ if(millis()-i2c.t>5000){ Wire.end(); delay(50); Wire.begin(); Wire.setTimeout(I2C_TIMEOUT); i2c.rst=false; i2c.err=0; DPRINTLN("I2C Bus Recovered");} else return false; }
  for(uint8_t r=0;r<I2C_RETRY;r++){ Wire.beginTransmission(a); if(!Wire.endTransmission()){ if(i2c.err > 0) { i2c.err = 0; DPRINTLN("I2C Comms OK");} return true;} delay(10);}
  if(++i2c.err>=5){ i2c.rst=true; i2c.t=millis(); DPRINTLN("I2C Error Threshold Reached - Bus Reset Pending");}
  DPRINT("I2C Ping Fail Addr: 0x"); DVARLN("", a);
  return false;
}

/* --------------------------- RELAY utils ------------------------------- */
inline void relaysOff(){ digitalWrite(PIN_RELAY_MAIN,RELAY_OFF); digitalWrite(PIN_RELAY_B1,RELAY_OFF); digitalWrite(PIN_RELAY_B2,RELAY_OFF); digitalWrite(PIN_VALVE,HIGH); DPRINTLN("All Relays OFF");}

/* --------------------------- Sensor helpers ---------------------------- */
inline bool readINA(float&v,float&i){ if(!sINA||i2c.rst) {v=NAN;i=NAN; return false;} v=ina.readBusVoltage()/1000.0f; i=ina.readCurrent()/1000.0f; if(!isfinite(v)||!isfinite(i)){v=NAN;i=NAN;return false;} return true;}
inline float readLuxSensor(){ return (sLux&&!i2c.rst)?veml.readLux():NAN; } // Renamed to avoid conflict
inline bool readXY(float&x,float&y){ if(!sOPT||i2c.rst) {x=NAN;y=NAN; return false;} auto d=opt.readLuxData(); if(opt.getLastError()!=OPT4048::Error::NoError) {x=NAN;y=NAN;return false;} x=d.x; y=d.y; if(!isfinite(x)||!isfinite(y)){x=NAN;y=NAN;return false;} return true; }
inline float readPSI(){ return (sMPR&&!i2c.rst)?mpr.readPressure()*0.0145038f:NAN; }

/* --------------------------- Generic Helpers --------------------------- */
// Handles NAN by printing a placeholder string.
String formatFloat(float val, int prec) {
    if (isnan(val)) return "0.000"; // Or "ERR"
    return String(val, prec);
}

Sample averageSamples(const Sample* s_arr, uint8_t count) {
    Sample a = {NAN, NAN, NAN, NAN, NAN}; // Initialize with NAN
    if (count == 0) return a;

    float sum_mv = 0, sum_mi = 0, sum_lux = 0, sum_x = 0, sum_y = 0;
    uint8_t valid_mv_mi = 0, valid_lux = 0, valid_xy = 0;

    for (uint8_t i = 0; i < count; i++) {
        if (!isnan(s_arr[i].mv) && !isnan(s_arr[i].mi)) { sum_mv += s_arr[i].mv; sum_mi += s_arr[i].mi; valid_mv_mi++;}
        if (!isnan(s_arr[i].lux)) { sum_lux += s_arr[i].lux; valid_lux++;}
        if (!isnan(s_arr[i].x) && !isnan(s_arr[i].y)) { sum_x += s_arr[i].x; sum_y += s_arr[i].y; valid_xy++; }
    }

    if (valid_mv_mi > 0) { a.mv = sum_mv / valid_mv_mi; a.mi = sum_mi / valid_mv_mi; }
    if (valid_lux > 0) { a.lux = sum_lux / valid_lux; }
    if (valid_xy > 0) { a.x = sum_x / valid_xy; a.y = sum_y / valid_xy; }
    return a;
}


/**************************************************************************/
/* NON-BLOCKING TEST STATE-MACHINES                                       */
/**************************************************************************/

/* ------------------------- PRESSURE State-machine ---------------------- */
enum class PState:uint8_t{IDLE,FILL,WAIT,EXH}; // Removed DONE, EXH handles completion
PState pstate=PState::IDLE;
uint32_t pTaskPhaseTimer=0; // Timer for current phase
float pInitialPressure=0;   // Pressure at start of WAIT phase
uint16_t PT_FILL_MS=1500,PT_WAIT_MS=2500,PT_EXH_MS=500;

void beginPressureTest(){
    if(!sMPR){ sendLine("ERROR:SENSOR_MISSING:MPRLS"); return;}
    if (curTest[0] != '\0') { sendLine("ERROR:TEST_IN_PROGRESS"); return; }
    strncpy(curTest,"PRESSURE", sizeof(curTest)-1);
    strncpy(lastRunTestType, "PRESSURE", sizeof(lastRunTestType)-1);
    pstate=PState::FILL;
    pTaskPhaseTimer=millis();
    digitalWrite(PIN_VALVE,LOW); // Open valve to fill
    DPRINTLN("Pressure Test: FILLING");
}

void taskPressure(){
    if(pstate==PState::IDLE) return;
    uint32_t now=millis();
    switch(pstate){
        case PState::FILL:
            if(now-pTaskPhaseTimer>=PT_FILL_MS){
                digitalWrite(PIN_VALVE,HIGH); // Close valve to isolate
                pInitialPressure=readPSI();
                pTaskPhaseTimer=now;
                pstate=PState::WAIT;
                DPRINT("Pressure Test: WAITING, Initial PSI: "); DVARLN("", pInitialPressure);
            }
            break;
        case PState::WAIT:
            if(streamOn && sMPR){ String s="LIVE:PSI="; s+=formatFloat(readPSI(),3); sendLine(s);}
            if(now-pTaskPhaseTimer>=PT_WAIT_MS){
                // Result is calculated and sent in EXH state now
                pTaskPhaseTimer=now;
                pstate=PState::EXH;
                digitalWrite(PIN_VALVE,LOW); // Open valve to exhaust
                DPRINTLN("Pressure Test: EXHAUSTING");
            }
            break;
        case PState::EXH:
            if(now-pTaskPhaseTimer>=PT_EXH_MS){
                digitalWrite(PIN_VALVE,HIGH); // Close valve
                float pFinalPressure = readPSI();
                float delta = isnan(pInitialPressure) || isnan(pFinalPressure) ? NAN : pInitialPressure - pFinalPressure;
                String s="RESULT:INITIAL="+formatFloat(pInitialPressure,3)+",DELTA="+formatFloat(delta,3);
                sendLine(s);
                sendLine("TEST_COMPLETE:PRESSURE");
                curTest[0]='\0';
                pstate=PState::IDLE;
                DPRINTLN("Pressure Test: COMPLETE");
            }
            break;
        default: pstate=PState::IDLE; break;
    }
}

/* -------------------- FUNCTION TEST State-machine ---------------------- */
enum class FTestState:uint8_t{IDLE, START_MAIN, COLLECT_MAIN, START_BACK, COLLECT_BACK, CALC_RESULTS};
FTestState fState = FTestState::IDLE;
uint32_t fTestPhaseStartTime = 0; // When current relay was activated
uint32_t fTestNextSampleTime = 0; // When next sample is due
uint8_t mainSampleCount = 0, backSampleCount = 0;
char fTestType[20] = ""; // Stores type like "POWER", "FUNCTION_TEST"

void beginFunctionTest(const String& type) {
    if (curTest[0] != '\0') { sendLine("ERROR:TEST_IN_PROGRESS"); return; }
    strncpy(fTestType, type.c_str(), sizeof(fTestType) - 1);
    strncpy(curTest, fTestType, sizeof(curTest)-1); // Set global current test
    strncpy(lastRunTestType, fTestType, sizeof(lastRunTestType)-1);

    fState = FTestState::START_MAIN;
    DPRINT("Function Test Started: "); DVARLN("", fTestType);
}

void taskFunctionTest() {
    if (fState == FTestState::IDLE) return;
    uint32_t now = millis();
    switch(fState) {
        case FTestState::START_MAIN:
            relaysOff();
            mainSampleCount = 0;
            digitalWrite(PIN_RELAY_MAIN, RELAY_ON);
            fTestPhaseStartTime = now;
            fTestNextSampleTime = now + RELAY_STAB_MS;
            fState = FTestState::COLLECT_MAIN;
            DPRINTLN("Function Test: Main Beam Sampling");
            break;

        case FTestState::COLLECT_MAIN:
            if ((now - fTestPhaseStartTime >= (RELAY_STAB_MS + SAMPLE_WINDOW_MS)) || (mainSampleCount >= MAX_SAMPLES)) {
                fState = FTestState::START_BACK;
                DPRINT("Main Beam Samples Collected: "); DVARLN("",mainSampleCount);
                break;
            }
            if (now >= fTestNextSampleTime && mainSampleCount < MAX_SAMPLES) {
                if(sINA) readINA(sampMain[mainSampleCount].mv, sampMain[mainSampleCount].mi); else {sampMain[mainSampleCount].mv=NAN; sampMain[mainSampleCount].mi=NAN;}
                if(sLux) sampMain[mainSampleCount].lux = readLuxSensor(); else sampMain[mainSampleCount].lux=NAN;
                if(sOPT) readXY(sampMain[mainSampleCount].x, sampMain[mainSampleCount].y); else {sampMain[mainSampleCount].x=NAN; sampMain[mainSampleCount].y=NAN;}
                
                // Debug output for each INA260 measurement
                String debugMsg = "DEBUG:MAIN_SAMPLE:" + String(mainSampleCount) + 
                                  ",V=" + formatFloat(sampMain[mainSampleCount].mv, 3) + 
                                  ",I=" + formatFloat(sampMain[mainSampleCount].mi, 3) +
                                  ",TIME=" + String(now - fTestPhaseStartTime);
                sendLine(debugMsg);
                
                mainSampleCount++;
                fTestNextSampleTime = now + SAMPLE_DELAY_MS;
            }
            break;

        case FTestState::START_BACK:
            relaysOff();
            backSampleCount = 0;
            digitalWrite(PIN_RELAY_B1, RELAY_ON); // Assuming B1 is the general backlight
            fTestPhaseStartTime = now;
            fTestNextSampleTime = now + RELAY_STAB_MS;
            fState = FTestState::COLLECT_BACK;
            DPRINTLN("Function Test: Backlight Sampling");
            break;

        case FTestState::COLLECT_BACK:
             if ((now - fTestPhaseStartTime >= (RELAY_STAB_MS + SAMPLE_WINDOW_MS)) || (backSampleCount >= MAX_SAMPLES)) {
                fState = FTestState::CALC_RESULTS;
                DPRINT("Backlight Samples Collected: "); DVARLN("", backSampleCount);
                break;
            }
            if (now >= fTestNextSampleTime && backSampleCount < MAX_SAMPLES) {
                if(sINA) readINA(sampBack[backSampleCount].mv, sampBack[backSampleCount].mi); else {sampBack[backSampleCount].mv=NAN; sampBack[backSampleCount].mi=NAN;}
                if(sLux) sampBack[backSampleCount].lux = readLuxSensor(); else sampBack[backSampleCount].lux=NAN;
                if(sOPT) readXY(sampBack[backSampleCount].x, sampBack[backSampleCount].y); else {sampBack[backSampleCount].x=NAN; sampBack[backSampleCount].y=NAN;}
                
                // Debug output for each INA260 measurement
                String debugMsg = "DEBUG:BACK_SAMPLE:" + String(backSampleCount) + 
                                  ",V=" + formatFloat(sampBack[backSampleCount].mv, 3) + 
                                  ",I=" + formatFloat(sampBack[backSampleCount].mi, 3) +
                                  ",TIME=" + String(now - fTestPhaseStartTime);
                sendLine(debugMsg);
                
                backSampleCount++;
                fTestNextSampleTime = now + SAMPLE_DELAY_MS;
            }
            break;

        case FTestState::CALC_RESULTS:
            {
                relaysOff();
                Sample M = averageSamples(sampMain, mainSampleCount);
                Sample B = averageSamples(sampBack, backSampleCount);
                
                // Debug output for averaged values
                String debugAvg = "DEBUG:AVERAGES:MAIN_V=" + formatFloat(M.mv, 3) + 
                                  ",MAIN_I=" + formatFloat(M.mi, 3) +
                                  ",BACK_V=" + formatFloat(B.mv, 3) +
                                  ",BACK_I=" + formatFloat(B.mi, 3) +
                                  ",MAIN_SAMPLES=" + String(mainSampleCount) +
                                  ",BACK_SAMPLES=" + String(backSampleCount);
                sendLine(debugAvg);
                
                String result = "RESULT:";
                if (strcmp(fTestType, "POWER") == 0) {
                    result += "MV_MAIN=" + formatFloat(M.mv, 3) + ",MI_MAIN=" + formatFloat(M.mi, 3) +
                              ",MV_BACK=" + formatFloat(B.mv, 3) + ",MI_BACK=" + formatFloat(B.mi, 3);
                } else if (strcmp(fTestType, "POWER_LUX") == 0) {
                    result += "LUX_MAIN=" + formatFloat(M.lux, 2) + ",LUX_BACK=" + formatFloat(B.lux, 2);
                } else if (strcmp(fTestType, "POWER_COLOR") == 0) {
                    result += "X_MAIN=" + formatFloat(M.x, 3) + ",Y_MAIN=" + formatFloat(M.y, 3) +
                              ",X_BACK=" + formatFloat(B.x, 3) + ",Y_BACK=" + formatFloat(B.y, 3);
                } else { // FUNCTION_TEST
                    result += "MV_MAIN=" + formatFloat(M.mv, 3) + ",MI_MAIN=" + formatFloat(M.mi, 3) +
                              ",LUX_MAIN=" + formatFloat(M.lux, 2) + ",X_MAIN=" + formatFloat(M.x, 3) + ",Y_MAIN=" + formatFloat(M.y, 3);
                    result += ",MV_BACK=" + formatFloat(B.mv, 3) + ",MI_BACK=" + formatFloat(B.mi, 3) +
                              ",LUX_BACK=" + formatFloat(B.lux, 2) + ",X_BACK=" + formatFloat(B.x, 3) + ",Y_BACK=" + formatFloat(B.y, 3);
                }
                sendLine(result);
                sendLine(String("TEST_COMPLETE:") + fTestType);
                curTest[0] = '\0';
                fState = FTestState::IDLE;
                DPRINTLN("Function Test: COMPLETE");
            }
            break;
        default: fState = FTestState::IDLE; break;
    }
}

/* --------------------- RGBW TEST State-machine ------------------------- */
enum class RGBWState:uint8_t {IDLE, CYCLE_START, SAMPLING, CYCLE_PAUSE}; // Removed DONE
RGBWState rgbwState = RGBWState::IDLE;
uint32_t rgbwCycleTimer = 0;    // Marks start of current ON or PAUSE phase
uint32_t rgbwSampleWindowStart = 0; // Marks start of the sampling part of an ON phase
uint8_t rgbwCycleNum = 0;
uint8_t rgbwSamplePointIndex = 0;

void beginRGBWTest() {
    if (curTest[0] != '\0') { sendLine("ERROR:TEST_IN_PROGRESS"); return; }
    strncpy(curTest, "RGBW_BACKLIGHT", sizeof(curTest)-1);
    strncpy(lastRunTestType, "RGBW_BACKLIGHT", sizeof(lastRunTestType)-1);
    rgbwCycleNum = 0;
    rgbwState = RGBWState::CYCLE_START;
    DPRINTLN("RGBW Test: STARTED");
}

void taskRGBWTest() {
    if (rgbwState == RGBWState::IDLE) return;
    uint32_t now = millis();
    switch(rgbwState) {
        case RGBWState::CYCLE_START:
            relaysOff();
            digitalWrite(PIN_RELAY_B1, RELAY_ON);
            rgbwCycleTimer = now; // Marks start of this ON phase
            rgbwSampleWindowStart = now + RGBW_STAB_MS; // Sampling starts after stabilization
            rgbwSamplePointIndex = 0;
            rgbwState = RGBWState::SAMPLING;
            DPRINT("RGBW Test: Cycle "); DPRINT(rgbwCycleNum + 1); DPRINTLN(" ON");
            break;

        case RGBWState::SAMPLING:
            // Check if the entire ON phase for this cycle is over
            if (now - rgbwCycleTimer >= RGBW_CYCLE_MS) {
                digitalWrite(PIN_RELAY_B1, RELAY_OFF);
                rgbwCycleTimer = now; // Mark start of PAUSE phase
                rgbwState = RGBWState::CYCLE_PAUSE;
                DPRINT("RGBW Test: Cycle "); DPRINT(rgbwCycleNum + 1); DPRINTLN(" OFF (Pause)");
                break;
            }

            // Check if we are within the sampling part of the ON phase
            if (now >= rgbwSampleWindowStart && rgbwSamplePointIndex < 3) {
                 uint16_t targetSampleTimeOffset = pgm_read_word(&RGBW_SAMPLE_PTS[rgbwSamplePointIndex]);
                 // elapsedInSampleWindow is time since sampling *should* have started
                 uint32_t elapsedInSampleWindow = now - rgbwSampleWindowStart;

                 if (elapsedInSampleWindow >= targetSampleTimeOffset) {
                    float mv=NAN, mi=NAN, rlux=NAN, x=NAN, y=NAN; // Use rlux for raw lux
                    if(sINA) readINA(mv, mi);
                    if(sLux) rlux = readLuxSensor();
                    if(sOPT) readXY(x,y);
                    
                    // Debug output for RGBW INA260 measurement
                    String debugMsg = "DEBUG:RGBW_SAMPLE:CYCLE=" + String(rgbwCycleNum + 1) + 
                                      ",POINT=" + String(rgbwSamplePointIndex) +
                                      ",V=" + formatFloat(mv, 3) + 
                                      ",I=" + formatFloat(mi, 3) +
                                      ",TIME=" + String(elapsedInSampleWindow);
                    sendLine(debugMsg);
                    
                    String s = "RGBW_SAMPLE:CYCLE=" + String(rgbwCycleNum + 1) +
                               ",VOLTAGE=" + formatFloat(mv, 3) + ",CURRENT=" + formatFloat(mi, 3);
                    s += ",LUX=" + formatFloat(rlux, 2) + ",X=" + formatFloat(x, 3) + ",Y=" + formatFloat(y, 3);
                    sendLine(s);
                    DPRINT("RGBW Sample: "); DVARLN("", s);
                    rgbwSamplePointIndex++;
                 }
            }
            break;

        case RGBWState::CYCLE_PAUSE:
            if (now - rgbwCycleTimer >= 100) { // 100ms pause between cycles
                rgbwCycleNum++;
                if (rgbwCycleNum >= RGBW_TOTAL_CYCLES) {
                    sendLine("TEST_COMPLETE:RGBW_BACKLIGHT");
                    curTest[0] = '\0';
                    rgbwState = RGBWState::IDLE;
                    DPRINTLN("RGBW Test: COMPLETE");
                } else {
                    rgbwState = RGBWState::CYCLE_START; // Start next cycle
                }
            }
            break;
        default: rgbwState = RGBWState::IDLE; break;
    }
}

/* ----------------- DUAL BACKLIGHT TEST State-machine ------------------- */
enum class DualState:uint8_t {IDLE, START_B1, COLLECT_B1, START_B2, COLLECT_B2, CALC}; // Removed DONE
DualState dualState = DualState::IDLE;
uint32_t dualTestPhaseStartTime = 0;
uint32_t dualTestNextSampleTime = 0;
uint8_t b1SampleCount = 0, b2SampleCount = 0;

void beginDualBacklightTest() {
    if (curTest[0] != '\0') { sendLine("ERROR:TEST_IN_PROGRESS"); return; }
    strncpy(curTest, "DUAL_BACKLIGHT", sizeof(curTest)-1);
    strncpy(lastRunTestType, "DUAL_BACKLIGHT", sizeof(lastRunTestType)-1);
    dualState = DualState::START_B1;
    DPRINTLN("Dual Backlight Test: STARTED");
}

void taskDualBacklightTest() {
    if (dualState == DualState::IDLE) return;
    uint32_t now = millis();
    switch(dualState) {
        case DualState::START_B1:
            relaysOff();
            b1SampleCount = 0;
            digitalWrite(PIN_RELAY_B1, RELAY_ON);
            dualTestPhaseStartTime = now;
            dualTestNextSampleTime = now + RELAY_STAB_MS;
            dualState = DualState::COLLECT_B1;
            DPRINTLN("Dual B Test: B1 Sampling");
            break;
        case DualState::COLLECT_B1:
            if ((now - dualTestPhaseStartTime >= (RELAY_STAB_MS + SAMPLE_WINDOW_MS)) || (b1SampleCount >= MAX_SAMPLES)) {
                dualState = DualState::START_B2;
                DPRINT("Dual B Test: B1 Samples: "); DVARLN("", b1SampleCount);
                break;
            }
            if (now >= dualTestNextSampleTime && b1SampleCount < MAX_SAMPLES) {
                if(sINA) readINA(sampMain[b1SampleCount].mv, sampMain[b1SampleCount].mi); else {sampMain[b1SampleCount].mv=NAN; sampMain[b1SampleCount].mi=NAN;}
                if(sLux) sampMain[b1SampleCount].lux = readLuxSensor(); else sampMain[b1SampleCount].lux=NAN;
                if(sOPT) readXY(sampMain[b1SampleCount].x, sampMain[b1SampleCount].y); else {sampMain[b1SampleCount].x=NAN; sampMain[b1SampleCount].y=NAN;}
                
                // Debug output for each INA260 measurement
                String debugMsg = "DEBUG:DUAL_B1_SAMPLE:" + String(b1SampleCount) + 
                                  ",V=" + formatFloat(sampMain[b1SampleCount].mv, 3) + 
                                  ",I=" + formatFloat(sampMain[b1SampleCount].mi, 3) +
                                  ",TIME=" + String(now - dualTestPhaseStartTime);
                sendLine(debugMsg);
                
                b1SampleCount++;
                dualTestNextSampleTime = now + SAMPLE_DELAY_MS;
            }
            break;
        case DualState::START_B2:
            relaysOff();
            b2SampleCount = 0;
            digitalWrite(PIN_RELAY_B2, RELAY_ON);
            dualTestPhaseStartTime = now;
            dualTestNextSampleTime = now + RELAY_STAB_MS;
            dualState = DualState::COLLECT_B2;
            DPRINTLN("Dual B Test: B2 Sampling");
            break;
        case DualState::COLLECT_B2:
            if ((now - dualTestPhaseStartTime >= (RELAY_STAB_MS + SAMPLE_WINDOW_MS)) || (b2SampleCount >= MAX_SAMPLES)) {
                dualState = DualState::CALC;
                 DPRINT("Dual B Test: B2 Samples: "); DVARLN("", b2SampleCount);
                break;
            }
            if (now >= dualTestNextSampleTime && b2SampleCount < MAX_SAMPLES) {
                if(sINA) readINA(sampBack[b2SampleCount].mv, sampBack[b2SampleCount].mi); else {sampBack[b2SampleCount].mv=NAN; sampBack[b2SampleCount].mi=NAN;}
                if(sLux) sampBack[b2SampleCount].lux = readLuxSensor(); else sampBack[b2SampleCount].lux=NAN;
                if(sOPT) readXY(sampBack[b2SampleCount].x, sampBack[b2SampleCount].y); else {sampBack[b2SampleCount].x=NAN; sampBack[b2SampleCount].y=NAN;}
                
                // Debug output for each INA260 measurement
                String debugMsg = "DEBUG:DUAL_B2_SAMPLE:" + String(b2SampleCount) + 
                                  ",V=" + formatFloat(sampBack[b2SampleCount].mv, 3) + 
                                  ",I=" + formatFloat(sampBack[b2SampleCount].mi, 3) +
                                  ",TIME=" + String(now - dualTestPhaseStartTime);
                sendLine(debugMsg);
                
                b2SampleCount++;
                dualTestNextSampleTime = now + SAMPLE_DELAY_MS;
            }
            break;
        case DualState::CALC:
            {
                relaysOff();
                Sample B1_avg = averageSamples(sampMain, b1SampleCount);
                Sample B2_avg = averageSamples(sampBack, b2SampleCount);
                String result = "RESULT:MV_BACK1=" + formatFloat(B1_avg.mv, 3) + ",MI_BACK1=" + formatFloat(B1_avg.mi, 3) +
                                ",LUX_BACK1=" + formatFloat(B1_avg.lux, 2) + ",X_BACK1=" + formatFloat(B1_avg.x, 3) + ",Y_BACK1=" + formatFloat(B1_avg.y, 3);
                result += ",MV_BACK2=" + formatFloat(B2_avg.mv, 3) + ",MI_BACK2=" + formatFloat(B2_avg.mi, 3) +
                          ",LUX_BACK2=" + formatFloat(B2_avg.lux, 2) + ",X_BACK2=" + formatFloat(B2_avg.x, 3) + ",Y_BACK2=" + formatFloat(B2_avg.y, 3);
                sendLine(result);
                sendLine("TEST_COMPLETE:DUAL_BACKLIGHT");
                curTest[0] = '\0';
                dualState = DualState::IDLE;
                DPRINTLN("Dual Backlight Test: COMPLETE");
            }
            break;
        default: dualState = DualState::IDLE; break;
    }
}


/**************************************************************************/
/* CORE TASKS AND COMMAND HANDLING                                        */
/**************************************************************************/

/* --------------------------- Button task ------------------------------- */
bool lastBtnState=HIGH; uint32_t lastDebounceTime=0;
void taskButton(){
    bool currentBtnState=digitalRead(PIN_BUTTON);
    if(currentBtnState!=lastBtnState) lastDebounceTime=millis();

    if(millis()-lastDebounceTime > 30){ // Debounce delay
        if(currentBtnState==BTN_ACTIVE && lastBtnState!=BTN_ACTIVE){ // Falling edge
            sendLine(String("INFO:BUTTON_PRESSED"));
            if(curTest[0] == '\0'){ // No test currently running
                sendLine(String("TEST_STARTED:") + lastRunTestType);
                // Call the appropriate begin function based on lastRunTestType
                if (strcmp(lastRunTestType, "PRESSURE") == 0) beginPressureTest();
                else if (strcmp(lastRunTestType, "RGBW_BACKLIGHT") == 0) beginRGBWTest();
                else if (strcmp(lastRunTestType, "DUAL_BACKLIGHT") == 0) beginDualBacklightTest();
                else if (strncmp(lastRunTestType, "POWER", 5) == 0 || strcmp(lastRunTestType, "FUNCTION_TEST") == 0) {
                    beginFunctionTest(String(lastRunTestType));
                }
            } else {
                sendLine("INFO:TEST_ALREADY_RUNNING");
            }
        }
    }
    lastBtnState=currentBtnState;
}

/* --------------------------- Heartbeat task ---------------------------- */
uint32_t lastHB = 0;
void taskHeartbeat(){
    if(!pythonOn || millis() - lastHB < HEARTBEAT_MS) return;
    sendLine("HEARTBEAT:OK");
    lastHB = millis();
}

/* --------------------------- Stream task ------------------------------- */
uint32_t lastStream = 0;
void taskStream(){
    if(!streamOn || curTest[0] != '\0' || millis() - lastStream < STREAM_MS) return;

    String l="LIVE:"; bool firstDataPoint=true;
    float v_val, i_val;
    if(sINA && readINA(v_val,i_val)){
        l+="V="+formatFloat(v_val,3)+",I="+formatFloat(i_val,3); firstDataPoint=false;
    }
    float lux_val;
    if(sLux){
        lux_val = readLuxSensor();
        if(!firstDataPoint) l+=",";
        l+="LUX="+formatFloat(lux_val,2); firstDataPoint=false;
    }
    float x_val, y_val;
    if(sOPT && readXY(x_val,y_val)){
        if(!firstDataPoint) l+=",";
        l+="X="+formatFloat(x_val,3)+",Y="+formatFloat(y_val,3); firstDataPoint=false;
    }
    float psi_val;
    if(sMPR){
        psi_val = readPSI();
        if(!firstDataPoint) l+=",";
        l+="PSI="+formatFloat(psi_val,3);
    }
    if (l.length() > 5) { // Check if any data was actually added beyond "LIVE:"
       sendLine(l);
    }
    lastStream = millis();
}

/* --------------------------- Serial Command ---------------------------- */
char serialCmdBuffer[128]; uint8_t serialCmdIdx=0; // Renamed to avoid conflict
void handleCmd(const String&);  // fwd
void serialPoll(){
    while(Serial.available()){
        char c=Serial.read();
        if(c=='\n'||c=='\r'){
            if(serialCmdIdx > 0){
                serialCmdBuffer[serialCmdIdx]='\0';
                handleCmd(String(serialCmdBuffer));
                serialCmdIdx=0;
            }
        } else if(c>=32 && c<=126 && serialCmdIdx < sizeof(serialCmdBuffer)-1){
            serialCmdBuffer[serialCmdIdx++]=c;
        } else if(serialCmdIdx >= sizeof(serialCmdBuffer)-1){ // Buffer overflow
            serialCmdIdx=0; // Reset buffer
            sendLine("ERROR:CMD_OVERFLOW");
        }
    }
}

/* --------------------------- Command Implement ------------------------- */
void sendStatus(){
    String s="STATUS:SENSORS=";
    if(sINA) s+="INA260,"; if(sLux) s+="VEML7700,"; if(sOPT) s+="OPT4048,"; if(sMPR) s+="MPRLS";
    if(s.endsWith(",")) s.remove(s.length()-1); // Remove trailing comma
    sendLine(s);
    sendLine(String("STATUS:TEST=")+ (curTest[0]?curTest:"IDLE"));
    sendLine(String("STATUS:LASTRUN=")+ lastRunTestType);
}

void handleCmd(const String& cmdStr){
    DPRINT("CMD RX: "); DVARLN("", cmdStr);
    if(cmdStr.equalsIgnoreCase("ID")||cmdStr.equalsIgnoreCase("PING")){
        pythonOn=true; sendLine("DIODE_DYNAMICS_TESTER_V4_PH3_REVIEWED"); return;
    }
    if(cmdStr.equalsIgnoreCase("STATUS")){ sendStatus(); return; }
    if(cmdStr.equalsIgnoreCase("START")){
        streamOn=true; pythonOn=true; sendLine("STARTED"); return;
    }
    if(cmdStr.equalsIgnoreCase("STOP")){
        relaysOff();
        curTest[0]='\0'; // Stop current test indication
        streamOn=false;
        // Reset all test state machines
        pstate=PState::IDLE;
        fState=FTestState::IDLE;
        rgbwState=RGBWState::IDLE;
        dualState=DualState::IDLE;
        sendLine("STOPPED"); return;
    }
    if(cmdStr.startsWith("STREAM:")){
        String arg = cmdStr.substring(7);
        streamOn = arg.equalsIgnoreCase("ON");
        sendLine(String("STREAMING:")+(streamOn?"ON":"OFF")); return;
    }
    if(cmdStr.equalsIgnoreCase("SENSOR_CHECK")){
        sINA = i2cPing(0x40) && ina.begin();
        sLux = i2cPing(0x10) && veml.begin();
        sOPT = i2cPing(0x44) && opt.begin();
        sMPR = i2cPing(0x18) && mpr.begin();
        if(sLux){ veml.setGain(VEML7700_GAIN_1); veml.setIntegrationTime(VEML7700_IT_100MS); }
        if(sOPT){ opt.setContinuousMode(); opt.setIntegrationTime(OPT4048::IntegrationTime::Integration_100ms); opt.setChannelEnable(true); }
        sendLine("SENSOR_CHECK:COMPLETE"); return;
    }
    if(cmdStr.startsWith("TEST:")){
        // Guard already present in individual beginTestX functions
        String testTypeArg = cmdStr.substring(5);
        if(testTypeArg.equalsIgnoreCase("PRESSURE")){ beginPressureTest(); return; }
        if(testTypeArg.equalsIgnoreCase("RGBW_BACKLIGHT")){ beginRGBWTest(); return; }
        if(testTypeArg.equalsIgnoreCase("DUAL_BACKLIGHT")){ beginDualBacklightTest(); return; }
        if(testTypeArg.equalsIgnoreCase("FUNCTION_TEST") || testTypeArg.equalsIgnoreCase("POWER") ||
           testTypeArg.equalsIgnoreCase("POWER_LUX") || testTypeArg.equalsIgnoreCase("POWER_COLOR")){
            beginFunctionTest(testTypeArg); return;
        }
        sendLine("ERROR:UNKNOWN_TEST:"+testTypeArg); return;
    }
    if(cmdStr.equalsIgnoreCase("RESET")){ NVIC_SystemReset(); }
    else sendLine("ERROR:UNKNOWN_CMD:"+cmdStr);
}

/* -------------------------------- Setup -------------------------------- */
void setup(){
    Serial.begin(SERIAL_BAUD);
    delay(500); // Wait for serial to stabilize
    Wire.begin();
    Wire.setTimeout(I2C_TIMEOUT);
    Wire.setClock(400000); // 400kHz is generally safer for multiple I2C devices
    pinMode(PIN_RELAY_MAIN,OUTPUT); pinMode(PIN_RELAY_B1,OUTPUT); pinMode(PIN_RELAY_B2,OUTPUT);
    pinMode(PIN_VALVE,OUTPUT); pinMode(PIN_BUTTON,INPUT_PULLUP);
    relaysOff();
    sendLine("=== Diode Dynamics Tester V4 Phase-3 Reviewed ===");
    // Initial sensor check on boot
    sINA = i2cPing(0x40) && ina.begin();
    sLux = i2cPing(0x10) && veml.begin();
    sOPT = i2cPing(0x44) && opt.begin();
    sMPR = i2cPing(0x18) && mpr.begin();
    if(sLux){ veml.setGain(VEML7700_GAIN_1); veml.setIntegrationTime(VEML7700_IT_100MS); }
    if(sOPT){ opt.setContinuousMode(); opt.setIntegrationTime(OPT4048::IntegrationTime::Integration_100ms); opt.setChannelEnable(true); }
    sendStatus(); // Send initial status
}

/* -------------------------------- Loop --------------------------------- */
void loop(){
    serialPoll(); // Check for incoming serial commands
    uint32_t now=millis();
    for(Task&t:tasks){ // Run scheduled tasks
        if(now - t.last >= t.period){
            t.last = now;
            t.fn();
        }
    }
  // yield(); // Not strictly necessary for this simple scheduler unless using FreeRTOS or ESP32
}
