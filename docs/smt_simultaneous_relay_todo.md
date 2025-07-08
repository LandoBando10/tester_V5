# SMT Simultaneous Relay Activation - Implementation Todo List

## Overview
Incremental upgrade to SMT testing to support simultaneous relay activation with precise timing control. Maintains backward compatibility with existing SKU files and minimal code changes.

## 1. Arduino Firmware Updates

### 1.1 Core Command Parser
- [ ] Keep existing commands for compatibility
- [ ] Add support for TESTSEQ batch command
- [ ] Parse relay lists and timing parameters
- [ ] Maintain existing error response format

### 1.2 Enhanced Command Set
```
// Existing commands (keep for compatibility)
TX:ALL                  // Test all relays
TX:1,2,3,4             // Test specific relays
X                      // All relays off (emergency stop)

// New batch command
TESTSEQ:1,2,3:500;OFF:100;7,8,9:500;OFF:100;...
// Response: TESTRESULTS:1,2,3:12.5V,6.8A;7,8,9:12.4V,6.7A;END
```

### 1.3 Relay Control System (16 Relay Support)
- [ ] Implement relay state bitmask (uint16_t for 16 relays - internal use only)
- [ ] Create relay activation functions for simultaneous switching
- [ ] Add hardware control via PCF8575 I2C expander (16-bit I/O)
- [ ] Initialize I2C communication in setup()
- [ ] Configure PCF8575 pins as outputs
- [ ] Implement simple relay state validation (max current limits)
- [ ] Keep serial protocol unchanged (relay lists remain as "1,2,3" format)

### 1.4 Timing System
- [ ] Replace delay() with millis()-based non-blocking timing
- [ ] Add configurable stabilization time (default 50ms, min 10ms)
- [ ] Account for INA260 1.1ms conversion time
- [ ] Implement minimum duration validation (duration_ms >= stabilization + conversion time)
- [ ] Add sequence timeout handling

### 1.5 Measurement System
- [ ] Single measurement per relay group activation
- [ ] Wait for INA260 conversion (1.1ms) before reading
- [ ] Store measurements in fixed-size array (not dynamic string)
- [ ] Validate measurement values (0-30V, 0-10A reasonable ranges)
- [ ] Error handling for I2C measurement failures

### 1.6 Response Protocol
```
// Existing responses (maintain compatibility)
PANELX:1=12.5,3.2;2=12.4,3.1;...
OK:ALL_OFF
ERROR:INA260_FAIL

// New batch response
TESTRESULTS:1,2,3:12.5V,6.8A;7,8,9:12.4V,6.7A;...;END

// Error responses
ERROR:SEQUENCE_TOO_LONG      // More than MAX_SEQUENCE_STEPS
ERROR:INVALID_RELAY:17       // Relay number > 16
ERROR:I2C_FAIL               // PCF8575 communication error
ERROR:MEASUREMENT_FAIL       // INA260 read failure
ERROR:SEQUENCE_TIMEOUT       // Sequence took too long
```

### 1.7 Safety Features
- [ ] Relay validation (1-16 range, no duplicates in mapping)
- [ ] Maximum simultaneous relay limit (configurable, default 8)
- [ ] Minimum timing validation (duration >= 100ms)
- [ ] I2C communication verification on startup
- [ ] Emergency stop 'X' command always works

## 2. Python Controller Updates

### 2.1 Maintain Existing Methods
- [ ] Keep test_panel() for backward compatibility
- [ ] Keep all_relays_off() method
- [ ] Maintain existing response parsing

### 2.2 New SMTArduinoController Methods
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

### 2.3 Enhanced Response Parsing
- [ ] Parse TESTRESULTS format with proper error handling
- [ ] Validate relay numbers match expected groups
- [ ] Handle partial results on error
- [ ] Map measurements back to board/function correctly
- [ ] Clear error reporting to user

### 2.4 Command Validation
- [ ] Validate relay numbers (1-16)
- [ ] Check for duplicate relays across groups
- [ ] Ensure minimum timing values
- [ ] Calculate and validate total sequence time
- [ ] Limit command length to prevent buffer issues

## 3. SKU Configuration Redesign

### 3.1 Enhanced SKU File Structure (Minimal Change - Using Commas for Groups)
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

### 3.2 SKU Parser Updates
- [ ] Update relay mapping parser to handle "," separator (e.g., "1,2,3")
- [ ] Add validation for relay groups (no duplicates, valid numbers)
- [ ] Parse timing fields from test_sequence (duration_ms, delay_after_ms)
- [ ] Modify test sequence builder to use grouped relays and timing
- [ ] Update result parser to map measurements back to groups
- [ ] Maintain backward compatibility for single relay entries (e.g., "1")

### 3.3 Configuration Features
- [ ] Validate no relay appears in multiple groups
- [ ] Ensure all timing values are positive integers
- [ ] Support optional "active_low" flag for relay control
- [ ] Add optional "max_simultaneous_relays" safety limit
- [ ] Clear documentation for migration from old format

### 3.4 Function Mapping for Large Panels (16 boards × 3 functions)
Example with 48 relays:
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
    
    // ... continues for all 16 boards
    
    // Board 16
    "43,44,45": {"board": 16, "function": "mainbeam"},
    "46": {"board": 16, "function": "position"},
    "47,48": {"board": 16, "function": "turn_signal"}
}

## 4. Serial Communication Optimization

### 4.1 Protocol Efficiency
- [ ] Optimize existing text protocol
- [ ] Consider binary protocol for future enhancement
- [ ] Batch response mode (TESTRESULTS format)
- [ ] Maintain backward compatibility

### 4.2 Buffer Management (Arduino R4 Minima - No Overflow Risk)
```
Arduino R4 Minima Specifications:
- RAM: 32KB
- Serial Buffer: 512+ bytes (estimated)
- Processor: 120MHz ARM Cortex-M4

With Relay Grouping:
- 16 measurements × 25 chars = 400 bytes ✅
- Well within R4 Minima buffer capacity

Without Grouping (worst case):
- 48 measurements × 15 chars = 720 bytes
- Still manageable with R4 Minima's larger buffer
```

### 4.3 Communication Protocol
- [ ] Single TESTSEQ command for entire test
- [ ] Single TESTRESULTS response with all measurements
- [ ] Maintain checksums for data integrity
- [ ] Keep existing timeout handling

## 5. Testing and Validation

### 5.1 Unit Tests
- [ ] Arduino firmware unit tests
- [ ] Python controller unit tests
- [ ] SKU parser validation tests
- [ ] Timing accuracy tests
- [ ] Buffer overflow tests

### 5.2 Integration Tests
- [ ] Full sequence execution tests
- [ ] Timing precision validation
- [ ] Current limit enforcement
- [ ] Error recovery scenarios
- [ ] Performance benchmarks

### 5.3 Hardware Tests
- [ ] Relay switching speed measurement
- [ ] Current measurement accuracy
- [ ] Timing jitter analysis
- [ ] Thermal behavior validation
- [ ] EMI/noise testing

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
- Maintain backward compatibility
- Test with existing SKUs

### Phase 2: Arduino Firmware (Week 1-2)
- Add TESTSEQ command handler
- Implement batch measurement collection
- Test with R4 Minima hardware

### Phase 3: Python Controller (Week 2)
- Add execute_test_sequence() method
- Integrate with existing SMT test flow
- Maintain compatibility with test_panel()

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
- **Scope Creep**: Focus on incremental improvements
- **Compatibility**: Test thoroughly with existing SKUs
- **Testing Coverage**: Automated tests from day 1
- **Performance**: Validate R4 Minima performance early

## 9. Example Implementations

### 9.1 Arduino Implementation with PCF8575
```cpp
#include <Wire.h>
#include <PCF8575.h>

#define MAX_RELAYS 16
#define MAX_SEQUENCE_STEPS 50
#define PCF8575_ADDRESS 0x20
#define STABILIZATION_TIME 50  // ms
#define MIN_DURATION 100       // ms
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
            
            // Hold for remaining duration
            if (steps[i].duration_ms > STABILIZATION_TIME) {
                delay(steps[i].duration_ms - STABILIZATION_TIME);
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
    delay(2);  // INA260 needs 1.1ms
    
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

- [ ] Execute complete test sequences in one command/response cycle
- [ ] Support 16 relay simultaneous activation with PCF8575
- [ ] Maintain simple "1,2,3" relay format in serial protocol
- [ ] Zero buffer overflows with fixed-size buffers
- [ ] Parse comma-separated relay groups in SKU files
- [ ] Maintain backward compatibility with existing SKUs
- [ ] Proper I2C error handling and recovery
- [ ] Non-blocking timing with emergency stop support

## Notes and Considerations

1. **PCF8575 Configuration**: 
   - I2C Address: 0x20 (default, adjustable via A0-A2 pins)
   - Check connection on startup with Wire.endTransmission()
   - Active LOW relays: Set RELAY_ACTIVE_LOW flag accordingly
   - Consider pullup resistors on I2C lines for reliability

2. **Timing Constraints**:
   - Minimum duration: 100ms (to ensure stable measurements)
   - Stabilization time: 50ms default (configurable)
   - INA260 conversion: 1.1ms (add 2ms delay to be safe)
   - Maximum sequence time: 30 seconds (prevent runaway tests)

3. **Buffer Management**:
   - Fixed response buffer: 500 chars (enough for ~15 measurements)
   - Pre-allocated to prevent fragmentation
   - No dynamic String concatenation in loops

4. **Error Handling**:
   - I2C failures reported immediately
   - Measurement validation (0-30V, 0-10A)
   - Sequence timeout protection
   - Emergency stop always functional

5. **Scaling Beyond 16 Relays**:
   - Use multiple PCF8575 at different addresses (0x20-0x27)
   - Or use multiple Arduino+PCF8575 combinations
   - Keep each Arduino at 16 relays max for simplicity