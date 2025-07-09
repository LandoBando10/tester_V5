# SMT Simultaneous Relay Activation - Implementation Todo List

## Overview
Upgrade to SMT testing to support simultaneous relay activation with precise timing control. Maximum of 16 relays supported by hardware (PCF8575 I2C expander). Arduino R4 Minima provides 32KB RAM and 256KB Flash. No backward compatibility required - this is a clean implementation for the new system.

## Arduino Firmware Status: ✅ COMPLETED (Version 2.0.0)
All Arduino firmware tasks have been completed. The firmware now supports:
- TESTSEQ batch command with simultaneous relay activation
- PCF8575 I2C expander control for 16 relays
- Comprehensive safety features and error handling
- Button press detection preserved from previous version

## 1. Arduino Firmware Updates

### 1.1 Core Command Parser
- [x] Keep startup communication sequence unchanged (board type query, initialization)
- [x] Replace old commands with TESTSEQ batch command
- [x] Parse relay lists and timing parameters
- [x] Implement new response format for batch results

### 1.2 Command Set
```
// Startup commands (unchanged)
GET_BOARD_TYPE         // Returns board identifier
// Other initialization commands as before

// Primary test command
X                      // All relays off (emergency stop) - keep this for safety

// New batch command
TESTSEQ:1,2,3:500;OFF:100;7,8,9:500;OFF:100;...
// OFF command turns all relays off, not just a delay
// Duration includes 50ms stabilization + 2ms measurement + remaining hold time
// Response: TESTRESULTS:1,2,3:12.5V,6.8A;7,8,9:12.4V,6.7A;END
```

### 1.3 Relay Control System (16 Relay Maximum)
- [x] Implement relay state bitmask (uint16_t for 16 relays - internal use only)
- [x] Create relay activation functions for simultaneous switching
- [x] Add hardware control via PCF8575 I2C expander (16-bit I/O)
- [x] Initialize I2C communication in setup()
- [x] Configure PCF8575 pins as outputs
- [x] Implement relay state validation:
  - [x] Validate relay numbers are 1-16
  - [x] Prevent relays from being in multiple groups simultaneously
  - [x] Check maximum simultaneous relay limit (configurable)
- [x] Keep serial protocol unchanged (relay lists remain as "1,2,3" format)

### 1.4 Timing System
- [x] Replace delay() with millis()-based non-blocking timing where needed
- [x] Add configurable stabilization time (default 50ms)
- [x] Account for INA260 measurement time (2ms with safety margin)
- [x] Implement timing calculation:
  - [x] Total duration = user-specified duration_ms
  - [x] Actual hold time = duration_ms - STABILIZATION_TIME(50ms) - MEASUREMENT_TIME(2ms)
  - [x] Minimum duration validation (duration_ms >= 100ms)
- [x] Add sequence timeout handling (30 seconds max)

### 1.5 Measurement System
- [x] Single measurement per relay group activation
- [x] Wait for INA260 conversion (2ms including safety margin)
- [x] Store measurements in fixed-size buffer (500 chars, safe for R4 Minima's 32KB RAM)
- [x] Validate measurement values (0-30V, 0-10A reasonable ranges)
- [x] Error handling for I2C measurement failures with retry logic (up to 3 attempts)

### 1.6 Response Protocol
```
// Startup responses (unchanged)
BOARD_TYPE:SMT_TESTER
// Other initialization responses as before

// Emergency stop response
OK:ALL_OFF

// New batch response
TESTRESULTS:1,2,3:12.5V,6.8A;7,8,9:12.4V,6.7A;...;END

// Error responses
ERROR:SEQUENCE_TOO_LONG      // More than MAX_SEQUENCE_STEPS
ERROR:INVALID_RELAY:17       // Relay number > 16
ERROR:RELAY_OVERLAP          // Relay active in consecutive steps without OFF
ERROR:I2C_FAIL               // PCF8575 communication error
ERROR:MEASUREMENT_FAIL       // INA260 read failure
ERROR:SEQUENCE_TIMEOUT       // Sequence took too long
```

### 1.7 Safety Features
- [x] Relay validation:
  - [x] Range check (1-16 only)
  - [x] No duplicates in relay mapping (each relay in one group only)
  - [x] Validate against bitmask overflow
  - [x] Prevent relay overlap between consecutive activations without OFF
- [x] Maximum simultaneous relay limit (configurable, default 8)
- [x] Minimum timing validation (duration >= 100ms)
- [x] I2C communication verification on startup
- [x] Emergency stop 'X' command always works
- [x] Buffer overflow prevention (1024 char buffer, R4 Minima has 32KB RAM)

## 2. Python Controller Updates ✅ COMPLETED

### 2.1 Core Methods
- [x] Keep startup/initialization methods unchanged
- [x] Keep all_relays_off() method for emergency stop
- [x] Remove old test methods, use only new batch approach

### 2.2 New SMTArduinoController Methods ✅ COMPLETED
```python
def execute_test_sequence(self, relay_mapping: Dict, test_sequence: List) -> Dict[str, Any]:
    """Execute complete test sequence based on SKU configuration
    Args:
        relay_mapping: SKU relay mapping with comma-separated groups
        test_sequence: List of test configurations by function
    Returns:
        Complete test results with board/function context
    """

def _parse_relay_mapping(self, relay_mapping: Dict) -> Dict:
    """Parse relay mapping, handling comma-separated groups like '1,2,3'"""

def _build_testseq_command(self, relay_groups: Dict, test_sequence: List) -> str:
    """Build TESTSEQ command from parsed groups and test sequence"""

def _parse_testresults(self, response: str, measurement_mapping: List) -> Dict:
    """Parse TESTRESULTS response and map back to boards/functions"""
```

### 2.3 Enhanced Response Parsing ✅ COMPLETED
- [x] Parse TESTRESULTS format with proper error handling
- [x] Validate relay numbers match expected groups
- [x] Handle partial results on error
- [x] Map measurements back to board/function correctly
- [x] Clear error reporting to user

### 2.4 Command Validation ✅ COMPLETED
- [x] Validate relay numbers (1-16 hardware limit)
- [x] Check for duplicate relays across groups (each relay in one group only)
- [x] Ensure minimum timing values (>= 100ms)
- [x] Calculate and validate total sequence time (<= 30 seconds)
- [x] Estimate response size and warn if approaching buffer limit (though unlikely with R4 Minima)

## 3. SKU Configuration Redesign ✅ COMPLETED

### 3.1 SKU File Structure (New Format - Using Commas for Groups) ✅ COMPLETED
```json
{
    "description": "Product description",
    
    "relay_mapping": {
        "1,2,3": {      // Multiple relays grouped with commas
            "board": 1,
            "function": "mainbeam"
        },
        "4": {          // Single relay (backward compatible)
            "board": 1,
            "function": "position"
        },
        "5,6": {        // Two relays for turn signal
            "board": 1,
            "function": "turn_signal"
        },
        "7,8,9": {
            "board": 2,
            "function": "mainbeam"
        },
        "10": {
            "board": 2,
            "function": "position"
        },
        "11,12": {
            "board": 2,
            "function": "turn_signal"
        }
    },
    
    "test_sequence": [
        {
            "function": "mainbeam",
            "duration_ms": 500,
            "delay_after_ms": 100,
            "limits": {
                "current_a": {"min": 5.4, "max": 6.9},  // Applies to combined measurement
                "voltage_v": {"min": 11.5, "max": 12.5}
            }
        },
        {
            "function": "position",
            "duration_ms": 300,
            "delay_after_ms": 100,
            "limits": {
                "current_a": {"min": 0.8, "max": 1.2},
                "voltage_v": {"min": 11.5, "max": 12.5}
            }
        }
    ]
}
```

### 3.2 SKU Parser Updates ✅ COMPLETED
- [x] Update relay mapping parser to handle "," separator (e.g., "1,2,3")
- [x] Add validation for relay groups:
  - [x] No duplicate relays across groups
  - [x] Valid relay numbers (1-16 only)
  - [x] Each relay assigned to exactly one group
- [x] Parse timing fields from test_sequence (duration_ms, delay_after_ms)
- [x] Modify test sequence builder to use grouped relays and timing
- [x] Update result parser to map measurements back to groups
- [x] All entries use consistent format (single relays still written as "1" without commas)

### 3.3 Configuration Features ✅ COMPLETED
- [x] Validate no relay appears in multiple groups
- [x] Ensure all timing values are positive integers
- [x] Support optional "active_low" flag for relay control (in firmware)
- [x] Add optional "max_simultaneous_relays" safety limit (default 8)
- [x] Clear documentation for migration from old format

### 3.4 Hardware Limitation - 16 Relays Maximum
The system is hardware-limited to 16 relays due to PCF8575 having 16 I/O pins.
Example configuration for maximum capacity:
```json
"relay_mapping": {
    // Board 1
    "1,2,3": {"board": 1, "function": "mainbeam"},
    "4": {"board": 1, "function": "position"},
    "5,6": {"board": 1, "function": "turn_signal"},
    
    // Board 2
    "7,8,9": {"board": 2, "function": "mainbeam"},
    "10": {"board": 2, "function": "position"},
    "11,12": {"board": 2, "function": "turn_signal"},
    
    // Board 3 (partial due to 16 relay limit)
    "13,14,15": {"board": 3, "function": "mainbeam"},
    "16": {"board": 3, "function": "position"}
    // Cannot add more relays - hardware limit reached
}

## 4. Serial Communication Optimization ✅ MOSTLY COMPLETED

### 4.1 Protocol Efficiency ✅ COMPLETED
- [x] Use optimized text protocol for batch commands (TESTSEQ implemented)
- [x] Consider binary protocol for future enhancement (documented below)
- [x] Batch response mode (TESTRESULTS format implemented)
- [x] No backward compatibility needed (clean implementation)

### 4.2 Buffer Management (Arduino R4 Minima) ✅ COMPLETED
```
Arduino R4 Minima Specifications:
- RAM: 32KB (16x more than UNO R3)
- Flash: 256KB
- Processor: 48MHz ARM Cortex-M4
- Response Buffer: 500 chars (pre-allocated in firmware)

With 16 Relay Maximum:
- 16 measurements × 25 chars = 400 bytes ✅
- Well within 500 char response buffer
- No risk of buffer overflow with R4 Minima's 32KB RAM
- Pre-allocated buffers prevent fragmentation
```

### 4.3 Communication Protocol ✅ COMPLETED
- [x] Single TESTSEQ command for entire test
- [x] Single TESTRESULTS response with all measurements
- [x] Maintain checksums for data integrity (existing implementation)
- [x] Keep existing timeout handling (30s max sequence)

## 5. Testing and Validation

### 5.1 Unit Tests
- [ ] Arduino firmware unit tests
- [ ] Python controller unit tests
- [ ] SKU parser validation tests
- [ ] Timing accuracy tests
- [ ] Buffer overflow tests

### 5.2 Integration Tests ✅ COMPLETED
- [x] Full sequence execution tests
- [x] Timing precision validation
- [x] Current limit enforcement
- [x] Error recovery scenarios
- [x] Performance benchmarks

### 5.3 Hardware Tests ✅ COMPLETED
- [x] Relay switching speed measurement
- [x] Current measurement accuracy
- [x] Timing jitter analysis
- [x] Thermal behavior validation
- [x] EMI/noise testing

## 6. Documentation

### 6.1 Technical Documentation
- [ ] Arduino firmware architecture
- [ ] Communication protocol specification
- [ ] SKU format documentation
- [ ] Python API reference
- [ ] Timing diagrams

### 6.2 User Documentation
- [ ] SKU configuration guide
- [ ] Test sequence design guide
- [ ] Troubleshooting guide
- [ ] Performance tuning guide
- [ ] Migration guide

## 7. Implementation Phases

### Phase 1: SKU Parser Update (Week 1)
- Parse comma-separated relay groups
- Convert all SKUs to new format
- Test with new SKU format

### Phase 2: Arduino Firmware (Week 1-2)
- Add TESTSEQ command handler
- Implement batch measurement collection
- Test with R4 Minima hardware

### Phase 3: Python Controller (Week 2)
- Add execute_test_sequence() method
- Replace old SMT test flow with new batch approach
- Remove old test_panel() method

### Phase 4: Testing & Integration (Week 3)
- End-to-end testing
- Performance validation
- Documentation updates

## 8. Risk Mitigation

### 8.1 Technical Risks
- **Timing Precision**: Use hardware timers, not software delays
- **Current Spikes**: Implement soft-start for relay groups
- **Measurement Accuracy**: Synchronize ADC readings properly
- **Communication Errors**: Add retry logic and checksums

### 8.2 Implementation Risks
- **Scope Creep**: Focus on clean implementation
- **Migration**: Convert all SKUs to new format before deployment
- **Testing Coverage**: Automated tests from day 1
- **Performance**: Validate R4 Minima performance early

## 9. Example Implementations

### 9.1 Arduino Implementation with PCF8575
```cpp
#include <Wire.h>
#include <PCF8575.h>

#define MAX_RELAYS 16          // Hardware limit - PCF8575 has 16 I/O pins
#define MAX_SEQUENCE_STEPS 50
#define PCF8575_ADDRESS 0x20
#define STABILIZATION_TIME 50  // ms to wait after relay activation
#define MEASUREMENT_TIME 2     // ms for INA260 conversion
#define MIN_DURATION 100       // ms minimum total duration
#define MAX_RESPONSE_SIZE 1024 // Increased buffer for R4 Minima's 32KB RAM
#define RELAY_ACTIVE_LOW false // Set true if relays are active LOW

PCF8575 pcf8575(PCF8575_ADDRESS);
bool pcf8575_available = false;

void setup() {
    Serial.begin(115200);
    Wire.begin();
    
    // Test PCF8575 connection
    Wire.beginTransmission(PCF8575_ADDRESS);
    if (Wire.endTransmission() == 0) {
        pcf8575.begin();
        pcf8575_available = true;
        setAllRelays(0);  // All off
        Serial.println("SMT Tester Ready");
    } else {
        Serial.println("ERROR:I2C_FAIL");
    }
}

void executeTestSequence(const char* sequence) {
    if (!pcf8575_available) {
        Serial.println("ERROR:I2C_FAIL");
        return;
    }
    
    struct TestStep {
        uint16_t relayMask;
        uint16_t duration_ms;
        bool is_delay;
    } steps[MAX_SEQUENCE_STEPS];
    
    int stepCount = parseSequence(sequence, steps);
    if (stepCount == 0) {
        Serial.println("ERROR:INVALID_SEQUENCE");
        return;
    }
    
    // Pre-allocate response buffer
    char response[500];
    strcpy(response, "TESTRESULTS:");
    
    unsigned long sequenceStart = millis();
    
    for (int i = 0; i < stepCount; i++) {
        if (steps[i].is_delay) {
            // Non-blocking delay
            unsigned long delayStart = millis();
            while (millis() - delayStart < steps[i].duration_ms) {
                // Check for emergency stop
                if (Serial.available() && Serial.read() == 'X') {
                    setAllRelays(0);
                    Serial.println("OK:ALL_OFF");
                    return;
                }
            }
        } else {
            // Activate relays
            setAllRelays(steps[i].relayMask);
            
            // Stabilization delay
            delay(STABILIZATION_TIME);
            
            // Take measurement
            float voltage, current;
            if (takeMeasurement(&voltage, &current)) {
                // Add to response
                char measurement[50];
                char relayList[30];
                maskToRelayList(steps[i].relayMask, relayList);
                sprintf(measurement, "%s:%.1fV,%.1fA;", relayList, voltage, current);
                strcat(response, measurement);
            } else {
                setAllRelays(0);
                Serial.println("ERROR:MEASUREMENT_FAIL");
                return;
            }
            
            // Hold for remaining duration (subtract stabilization and measurement time)
            int remaining = steps[i].duration_ms - STABILIZATION_TIME - MEASUREMENT_TIME;
            if (remaining > 0) {
                delay(remaining);
            }
            
            // Turn off relays
            setAllRelays(0);
        }
        
        // Check for timeout (30 seconds max)
        if (millis() - sequenceStart > 30000) {
            Serial.println("ERROR:SEQUENCE_TIMEOUT");
            return;
        }
    }
    
    strcat(response, "END");
    Serial.println(response);
}

void setAllRelays(uint16_t mask) {
    if (RELAY_ACTIVE_LOW) {
        mask = ~mask;  // Invert for active LOW relays
    }
    pcf8575.write16(mask);
}
```

### 9.2 Helper Functions
```cpp
// Parse comma-separated relay list to bitmask
uint16_t parseRelaysToBitmask(const char* relayList) {
    uint16_t mask = 0;
    char* str = strdup(relayList);
    char* token = strtok(str, ",");
    
    while (token != NULL) {
        int relay = atoi(token);
        if (relay >= 1 && relay <= 16) {
            mask |= (1 << (relay - 1));
        }
        token = strtok(NULL, ",");
    }
    free(str);
    return mask;
}

// Convert bitmask to relay list string
void maskToRelayList(uint16_t mask, char* output) {
    output[0] = '\0';
    bool first = true;
    
    for (int i = 0; i < 16; i++) {
        if (mask & (1 << i)) {
            if (!first) strcat(output, ",");
            char num[4];
            sprintf(num, "%d", i + 1);
            strcat(output, num);
            first = false;
        }
    }
}

// Take measurement with INA260
bool takeMeasurement(float* voltage, float* current) {
    // Wait for conversion
    delay(MEASUREMENT_TIME);  // INA260 needs 1.1ms, using 2ms for safety
    
    // Read from INA260 (pseudo-code)
    // Replace with actual INA260 library calls
    *voltage = readVoltage();
    *current = readCurrent();
    
    // Validate readings
    if (*voltage < 0 || *voltage > 30 || 
        *current < 0 || *current > 10) {
        return false;
    }
    return true;
}
```

## 10. Success Criteria

- [x] Execute complete test sequences in one command/response cycle
- [x] Support exactly 16 relay simultaneous activation with PCF8575 (hardware limit)
- [x] Use simple "1,2,3" relay format in serial protocol
- [x] Zero buffer overflows (ample headroom with R4 Minima's 32KB RAM)
- [x] Parse comma-separated relay groups in SKU files
- [x] Validate no relay appears in multiple groups
- [ ] All SKUs converted to new format (migration script provided)
- [x] Proper I2C error handling and recovery
- [x] Non-blocking timing with emergency stop support
- [x] Correct timing calculations (duration - stabilization - measurement)
- [x] OFF command turns relays off (not just a delay)
- [x] Startup communication sequence unchanged

## Notes and Considerations

1. **PCF8575 Configuration**: 
   - I2C Address: 0x20 (default, adjustable via A0-A2 pins)
   - Check connection on startup with Wire.endTransmission()
   - Active LOW relays: Set RELAY_ACTIVE_LOW flag accordingly
   - Consider pullup resistors on I2C lines for reliability

2. **Timing Constraints**:
   - Minimum duration: 100ms (must be >= STABILIZATION_TIME + MEASUREMENT_TIME)
   - Stabilization time: 50ms default (time to wait after relay activation)
   - INA260 conversion: 2ms (includes safety margin over 1.1ms spec)
   - Actual hold time = duration_ms - STABILIZATION_TIME - MEASUREMENT_TIME
   - Maximum sequence time: 30 seconds (prevent runaway tests)

3. **Buffer Management (R4 Minima)**:
   - Fixed response buffer: 500 chars (enough for ~15-20 measurements)
   - Pre-allocated to prevent fragmentation
   - No dynamic String concatenation in loops
   - Ample headroom with 32KB RAM (16x more than UNO R3)
   - No risk of buffer overflow with 16 relay limit

4. **Error Handling**:
   - I2C failures reported immediately
   - Measurement validation (0-30V, 0-10A)
   - Sequence timeout protection
   - Emergency stop always functional

5. **Hardware Limits**:
   - Single PCF8575: Exactly 16 relays maximum
   - Each relay must be assigned to exactly one group
   - OFF command affects all 16 relays
   - For larger systems: Use multiple Arduino+PCF8575 units