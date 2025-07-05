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
- [ ] Replace delay() with millis()-based timing
- [ ] Implement microsecond-precision timing for critical sections
- [ ] Create timing queue for sequence execution
- [ ] Add timing compensation for measurement overhead
- [ ] Implement watchdog timer for sequence safety

### 1.5 Measurement System
- [ ] Continuous sampling during sequences (100Hz minimum)
- [ ] Ring buffer for measurement storage (512 samples)
- [ ] Measurement triggering at specific time points
- [ ] Peak/average/RMS calculations
- [ ] Simultaneous voltage/current measurement synchronization

### 1.6 Response Protocol
```
// Existing responses (maintain compatibility)
PANELX:1=12.5,3.2;2=12.4,3.1;...
OK:ALL_OFF
ERROR:INA260_FAIL

// New batch response
TESTRESULTS:1,2,3:12.5V,6.8A;7,8,9:12.4V,6.7A;...;END

// Error responses
ERROR:SEQUENCE_TOO_LONG
ERROR:INVALID_RELAY:9
```

### 1.7 Safety Features
- [ ] Maximum current limit per relay group
- [ ] Thermal protection timing (max on-time)
- [ ] Automatic shutdown on overcurrent
- [ ] Voltage drop detection and reporting
- [ ] Emergency stop on serial disconnect

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
- [ ] Parse complex measurement responses with timing data
- [ ] Handle streaming data efficiently
- [ ] Implement robust error recovery
- [ ] Add measurement interpolation for missed samples
- [ ] Create measurement aggregation functions

### 2.4 Buffer Management
- [ ] Implement circular buffer for streaming data
- [ ] Add flow control for long sequences
- [ ] Handle partial response recovery
- [ ] Implement response timeout handling
- [ ] Add sequence chunking for very long patterns

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
- [ ] Named relay groups for reusability
- [ ] Multiple test sequences per SKU
- [ ] Timing constraints and limits
- [ ] Measurement point specifications
- [ ] Dynamic limit calculations based on groups
- [ ] **Hierarchical function mapping for 48-relay systems**

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
#define PCF8575_ADDRESS 0x20  // Adjust based on A0-A2 pins

PCF8575 pcf8575(PCF8575_ADDRESS);

void setup() {
    Serial.begin(115200);
    
    // Initialize I2C
    Wire.begin();
    
    // Initialize PCF8575
    pcf8575.begin();
    
    // Set all pins as outputs and turn off all relays
    pcf8575.write16(0x0000);  // All LOW = all relays OFF
    
    Serial.println("SMT Tester with PCF8575 Ready");
}

void executeTestSequence(const char* sequence) {
    // Parse sequence: "1,2,3:500;OFF:100;7,8,9:500"
    struct TestStep {
        uint16_t relayMask;  // Internal bitmask for fast switching
        uint16_t duration_ms;
        bool is_delay;
    } steps[MAX_STEPS];
    
    int stepCount = parseSequence(sequence, steps);
    String results = "TESTRESULTS:";
    
    for (int i = 0; i < stepCount; i++) {
        if (!steps[i].is_delay) {
            // Use bitmask internally for simultaneous relay control
            setAllRelays(steps[i].relayMask);  // All relays switch at once
            delay(100);  // Stabilization
            
            // Measure and format as readable relay list
            float v = measureVoltage();
            float a = measureCurrent();
            results += getRelayList(steps[i].relayMask);  // Converts back to "1,2,3"
            results += ":" + String(v,1) + "V," + String(a,1) + "A;";
            
            delay(steps[i].duration_ms - 100);
            setAllRelays(0);  // All off
        } else {
            delay(steps[i].duration_ms);
        }
    }
    
    results += "END";
    Serial.println(results);
}

// Fast 16-relay control using PCF8575 I2C expander
#include <PCF8575.h>

PCF8575 pcf8575(0x20);  // I2C address 0x20 (adjust based on A0-A2 pins)

void setAllRelays(uint16_t mask) {
    // Write all 16 bits at once - truly simultaneous!
    pcf8575.write16(mask);
}
```

### 9.2 Python Sequence Builder
```python
class SequenceBuilder:
    def __init__(self):
        self.steps = []
    
    def activate(self, relays: List[int], duration_ms: int):
        self.steps.append(f"R{'&'.join(map(str, relays))},{duration_ms}")
        return self
    
    def delay(self, duration_ms: int):
        self.steps.append(f"OFF,{duration_ms}")
        return self
    
    def build(self) -> str:
        return ",".join(self.steps)

# Usage
seq = (SequenceBuilder()
    .activate([1, 2], 200)
    .delay(50)
    .activate([3, 4], 300)
    .build())
```

## 10. Success Criteria

- [ ] Execute complete test sequences in one command/response cycle
- [ ] Support 16 relay simultaneous activation
- [ ] Maintain simple "1,2,3" relay format in serial protocol
- [ ] Zero buffer overflows on Arduino R4 Minima
- [ ] Parse comma-separated relay groups in SKU files
- [ ] Maintain backward compatibility with existing SKUs
- [ ] Support panels up to 16 boards × 3 functions (48 relays total)
- [ ] Keep implementation simple and maintainable

## Notes and Considerations

1. **PCF8575 Configuration**: 
   - I2C Address: 0x20 (default, adjustable via A0-A2 pins)
   - All 16 I/O pins can be used for relays
   - Button input can be read from the same PCF8575 if needed
   - Supports interrupt output for button press detection

2. **Power Supply**: Simultaneous relay activation will increase instantaneous current draw. May need to add power supply validation step.

2. **Relay Protection**: Consider adding flyback diode validation and snubber circuits for simultaneous switching.

3. **Measurement Synchronization**: INA260 has 1.1ms conversion time. Need to account for this in timing calculations.

4. **Emergency Stop**: Keep simple "X" command for emergency all-off that bypasses sequence processing.

5. **Debugging**: Add debug mode that outputs detailed timing information for sequence validation.

6. **Future Extensions**: 
   - PWM control for relays
   - Ramp-up/ramp-down profiles
   - Conditional sequences based on measurements
   - External trigger support

This implementation will provide a robust, flexible system for advanced SMT panel testing with precise control over relay activation patterns and timing.