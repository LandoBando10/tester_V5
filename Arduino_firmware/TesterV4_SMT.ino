/* ======================================================================
 * TesterV4_SMT – UNO R4 Minima, pins 2-9, 100ms measurement window
 * 2025-06-08
 * 
 * Timing: Each relay measurement takes exactly 100ms with 5 samples
 * taken at: 15ms, 32ms, 49ms, 66ms, 83ms (avoiding first/last 15ms)
 * =====================================================================*/

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_INA260.h>

/* ---------- User-tunable constants ----------------------------------- */
constexpr uint32_t SERIAL_BAUD   = 115200;
constexpr uint8_t  MAX_RELAYS    = 16;
constexpr uint8_t  DEFAULT_RELAYS= 8;        // we’re using 8 pins, 1-8
constexpr uint8_t  RELAY_ON      = LOW;      // active-low modules
constexpr uint8_t  RELAY_OFF     = HIGH;
constexpr uint8_t  MEAS_SAMPLES  = 5;        // INA260 averages
/* --------------------------------------------------------------------- */

/* ---------- Physical pin layout: 1-8 in the order requested ---------- */
constexpr uint8_t PIN_MAP[MAX_RELAYS] = {
  2,3,4,5,6,7,8,9,          // relays 1-8  (was 1-8)
  10,11,12,13, A0, A1, A2, A3
};

/* ---------- Type definitions ----------------------------------------- */
enum class LightType : uint8_t { Standard, RGBW };

struct RGBWState {
  bool     active           {false};
  uint8_t  pin              {0};
  uint32_t lastToggle       {0};
  uint16_t onMS             {50};
  uint16_t offMS            {50};
  bool     pinState         {false};
  uint8_t  colourPos        {0};
  bool     sampling         {false};
  uint8_t  sampleCnt        {0};
  uint16_t samplePts[10]    {};
  uint8_t  nextSample       {0};
  uint32_t cycleStart       {0};
};

/* ---------- Globals --------------------------------------------------- */
uint8_t   numRelays   = DEFAULT_RELAYS;
bool      relayState[MAX_RELAYS]{};
LightType relayType [MAX_RELAYS]{};
RGBWState rgbw      [MAX_RELAYS]{};

Adafruit_INA260 ina;
bool            sensorOK=false;

/* ---------- Tiny printf helper (works on any Arduino core) ----------- */
#include <stdarg.h>
static void sPrintf(const char *f, ...){
  char b[128]; va_list a; va_start(a,f); vsnprintf(b,sizeof(b),f,a); va_end(a);
  Serial.print(b);
}
#define PRINTF(...)  sPrintf(__VA_ARGS__)

/* ---------- Relay basics --------------------------------------------- */
inline void writeSafe(uint8_t pin,uint8_t v){ if(pin!=0xFF) digitalWrite(pin,v);}

void initRelays(){
  for(uint8_t i=0;i<MAX_RELAYS;++i){
    relayState[i]=false; relayType[i]=LightType::Standard; rgbw[i]={};
    if(i<numRelays){ pinMode(PIN_MAP[i],OUTPUT); writeSafe(PIN_MAP[i],RELAY_OFF);}
  }
}

void setRelay(uint8_t idx,bool on){
  if(!idx||idx>numRelays) return;
  uint8_t i=idx-1; relayState[i]=on;
  writeSafe(PIN_MAP[i], on?RELAY_ON:RELAY_OFF);
  if(!on && relayType[i]==LightType::RGBW) rgbw[i].active=false;
}

void allOff(){ for(uint8_t i=1;i<=numRelays;++i) setRelay(i,false);}

/* ---------- RGBW helper (unchanged timing logic) --------------------- */
void startRGBW(uint8_t ch,uint16_t on=50,uint16_t off=50){
  if(!ch||ch>numRelays) return;
  auto &s=rgbw[ch-1]; s={}; s.active=true; s.pin=PIN_MAP[ch-1];
  s.onMS=on; s.offMS=off; s.pinState=true; s.lastToggle=millis();
  s.cycleStart=millis(); writeSafe(s.pin,RELAY_ON);
}
void stopRGBW(uint8_t ch){ if(!ch||ch>numRelays) return;
  rgbw[ch-1].active=false; writeSafe(PIN_MAP[ch-1],RELAY_OFF);}
void serviceRGBW(){
  uint32_t now=millis();
  for(uint8_t i=0;i<numRelays;++i){ auto &s=rgbw[i]; if(!s.active) continue;
    uint16_t limit=s.pinState? s.onMS:s.offMS;
    if(now-s.lastToggle>=limit){
      s.pinState=!s.pinState; writeSafe(s.pin,s.pinState?RELAY_ON:RELAY_OFF);
      s.lastToggle=now; if(s.pinState) ++s.colourPos;
    }
    if(s.sampling && s.nextSample<s.sampleCnt){
      uint32_t t=now-s.cycleStart;
      if(t>=s.samplePts[s.nextSample]){
        PRINTF("RGBW_SAMPLE:%u:%u:%u:%lu\n",i+1,s.nextSample,s.colourPos,t);
        if(++s.nextSample>=s.sampleCnt){ stopRGBW(i+1); PRINTF("RGBW_COMPLETE:%u\n",i+1);}
      }
    }
  }
}

/* ---------- INA260 averaged read ------------------------------------- */
bool readINA(float &V,float &I,float &P){
  if(!sensorOK) return false;
  
  // 100ms total window with 5 measurements
  // Avoid first and last 10ms, so measurements at: 15ms, 32.5ms, 50ms, 67.5ms, 85ms
  // This gives us 17.5ms spacing with 15ms initial offset
  constexpr uint16_t INITIAL_DELAY_MS = 15;  // Start measuring at 15ms
  constexpr uint16_t SAMPLE_INTERVAL_MS = 17; // 17.5ms rounded to 17ms
  
  float sv=0,si=0,sp=0; uint8_t ok=0;
  
  // Initial delay to avoid measurement at the very beginning
  delay(INITIAL_DELAY_MS);
  
  for(uint8_t i=0;i<MEAS_SAMPLES;++i){
    float v=ina.readBusVoltage()/1000.0f, c=ina.readCurrent()/1000.0f, p=ina.readPower()/1000.0f;
    if(!isnan(v)&&!isnan(c)&&!isnan(p)){ sv+=v; si+=c; sp+=p; ++ok;}
    
    // Delay between samples (except after last sample)
    if(i < MEAS_SAMPLES - 1) {
      delay(SAMPLE_INTERVAL_MS);
    }
  }
  
  // Final delay to complete the 100ms window
  // Total time so far: 15 + (4 * 17) = 83ms, need 17ms more to reach 100ms
  delay(17);
  
  if(!ok) return false; V=sv/ok; I=si/ok; P=sp/ok; return true;
}

/* ---------- Command parser ------------------------------------------- */
String buf;
void exec(String);      // forward

void pollSerial(){
  while(Serial.available()){
    char c=Serial.read();
    if(c=='\n'||c=='\r'){ if(buf.length()){ exec(buf); buf="";}}
    else if(buf.length()<120) buf+=c;
  }
}
bool sw(const String&s,const char*p){ return s.startsWith(p); }

void parseList(String l,bool st){
  uint16_t n=0; for(uint16_t i=0;i<=l.length();++i){
    char c=(i<l.length())?l[i]:','; if(c==','||c=='\0'){ if(n) setRelay(n,st); n=0;}
    else if(isdigit(c)) n=n*10+(c-'0');
  }
}
/* main command dispatcher */
void exec(String cmd){
  cmd.trim();
  if(cmd.equalsIgnoreCase("PING")||cmd.equalsIgnoreCase("ID")){
    Serial.println("DIODE_DYNAMICS_SMT_TESTER_V4"); return;}
  if(cmd.equalsIgnoreCase("STOP")||cmd.equalsIgnoreCase("RELAY_ALL:OFF")){
    allOff(); Serial.println("STOPPED"); return;}
  if(cmd.equalsIgnoreCase("STATUS")){
    PRINTF("STATUS:RELAYS=%u,STATE=",numRelays);
    for(uint8_t i=0;i<numRelays;++i) Serial.print(relayState[i]?'1':'0');
    Serial.println(); return;}
  /* single relay */
  if(sw(cmd,"RELAY:")){
    int p=cmd.indexOf(':',6); if(p>6){
      uint8_t n=cmd.substring(6,p).toInt(); bool on=cmd.substring(p+1).equalsIgnoreCase("ON");
      setRelay(n,on); PRINTF("RELAY:%u:%s\n",n,on?"ON":"OFF");
    } return;}
  /* group */
  if(sw(cmd,"RELAY_GROUP:")){
    int p=cmd.indexOf(':',12); if(p>12){
      String list=cmd.substring(12,p); bool on=cmd.substring(p+1).equalsIgnoreCase("ON");
      parseList(list,on); PRINTF("RELAY_GROUP:%s:%s\n",list.c_str(),on?"ON":"OFF");
    } return;}
  /* RGBW */
  if(sw(cmd,"RGBW:")){
    int p=cmd.indexOf(':',5); if(p<0) return; uint8_t ch=cmd.substring(5,p).toInt();
    String a=cmd.substring(p+1);
    if(a.equalsIgnoreCase("START")){ startRGBW(ch); PRINTF("RGBW:%u:STARTED\n",ch);}
    else if(a.equalsIgnoreCase("STOP")){ stopRGBW(ch); PRINTF("RGBW:%u:STOPPED\n",ch);}
    else if(a.startsWith("PATTERN:")){
      int c=a.indexOf(',',8); if(c>8){
        uint16_t on=a.substring(8,c).toInt(), off=a.substring(c+1).toInt();
        startRGBW(ch,on,off); PRINTF("RGBW:%u:PATTERN:%u,%u\n",ch,on,off);}
    } return;}
  /* config : only channel count needed here */
  if(sw(cmd,"CONFIG:CHANNELS:")){
    numRelays=constrain(cmd.substring(16).toInt(),1,MAX_RELAYS); initRelays();
    PRINTF("CONFIG:CHANNELS:%u\n",numRelays); return;}
  /* measurement – no dead-time between relays -------------------------- */
  if(cmd.equalsIgnoreCase("MEASURE")){
    float V,I,P; if(readINA(V,I,P))
      PRINTF("MEASUREMENT:V=%.3f,I=%.3f,P=%.3f\n",V,I,P);
    else Serial.println("ERROR:MEASUREMENT_FAILED"); return;}
  if(sw(cmd,"MEASURE:")){
    uint8_t ch=cmd.substring(8).toInt(); if(!ch||ch>numRelays) return;
    allOff(); setRelay(ch,true);                 // **no delay here**
    float V,I,P; if(readINA(V,I,P))
      PRINTF("MEASUREMENT:%u:V=%.3f,I=%.3f,P=%.3f\n",ch,V,I,P);
    setRelay(ch,false); return;}
  if(sw(cmd,"MEASURE_GROUP:")){
    String l=cmd.substring(14); uint8_t q[16]{},u=0;
    for(uint16_t n=0,i=0;i<=l.length();++i){ char c=(i<l.length())?l[i]:',';
      if(c==','||c=='\0'){ if(n&&n<=numRelays&&u<16) q[u++]=n; n=0;}
      else if(isdigit(c)) n=n*10+(c-'0');}
    for(uint8_t k=0;k<u;++k){
      allOff(); setRelay(q[k],true);             // **no delay**
      float V,I,P; if(readINA(V,I,P))
        PRINTF("MEASUREMENT:%u:V=%.3f,I=%.3f,P=%.3f\n",q[k],V,I,P);
    }
    allOff(); Serial.println("MEASURE_GROUP:COMPLETE"); return;}
  /* sensor check */
  if(cmd.equalsIgnoreCase("SENSOR_CHECK")){
    Serial.println(sensorOK? "SENSOR_CHECK:INA260:OK":"SENSOR_CHECK:INA260:NOT_FOUND"); return;}
  Serial.print("ERROR:UNKNOWN_CMD:"); Serial.println(cmd);
}

/* ---------- INA260 init ---------------------------------------------- */
void initINA(){
  Wire.begin(); Wire.setClock(400000);
  sensorOK=ina.begin(); if(!sensorOK){ Serial.println("WARNING: INA260 not found"); return;}
#if defined(INA260_TIME_1100_us)
  ina.setCurrentConversionTime(INA260_TIME_1100_us);
  ina.setVoltageConversionTime(INA260_TIME_1100_us);
#else
  ina.setCurrentConversionTime(INA260_TIME_1_1_ms);
  ina.setVoltageConversionTime(INA260_TIME_1_1_ms);
#endif
  ina.setAveragingCount(INA260_COUNT_4); ina.setMode(INA260_MODE_CONTINUOUS);
}

/* ---------- Arduino setup / loop ------------------------------------- */
void setup(){
  Serial.begin(SERIAL_BAUD); initINA(); initRelays();
  Serial.println("=== Diode Dynamics SMT Tester V4 – UNO R4 pins 1-8 ===");
  PRINTF("Configured for %u relays\n",numRelays);
  Serial.println(sensorOK? "INA260 detected":"INA260 missing");
  Serial.println("Ready");
}
void loop(){ pollSerial(); serviceRGBW(); }
