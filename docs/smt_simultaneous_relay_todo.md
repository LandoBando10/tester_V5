# SMT Simultaneous Relay Activation - Implementation Todo List

## Overview
Complete redesign of SMT testing to support simultaneous relay activation with precise timing control. NO BACKWARD COMPATIBILITY - clean slate implementation.

## 1. Arduino Firmware Updates

### 1.1 Core Command Parser
- [ ] Remove all legacy single-relay commands (R1:ON, R1:OFF)
- [ ] Implement new command parser for complex sequences
- [ ] Add command validation with proper error responses
- [ ] Implement command queue with 1KB buffer for complex sequences

### 1.2 New Command Set
```
// Basic commands
MULTI_ON:1,2,5,6        // Turn on multiple relays
MULTI_OFF:1,2,5,6       // Turn off multiple relays
ALL_OFF                 // Emergency stop (keep this)

// Sequence commands
SEQ:R1&R2,200,OFF,50,R3&R4,300,OFF   // Complex sequence
PATTERN:1&2:200;0:50;3&4:300         // Alternative format

// Measurement commands
MEASURE_NOW             // Take immediate measurement
MEASURE_GROUP:1,2,5,6   // Measure specific relay group
STREAM_START            // Start continuous measurements
STREAM_STOP             // Stop continuous measurements
```

### 1.3 Relay Control System
- [ ] Implement relay state bitmask (uint8_t for 8 relays)
- [ ] Create relay group management functions
- [ ] Add simultaneous relay switching (single PORT write)
- [ ] Implement hardware abstraction layer for relay control
- [ ] Add relay state validation (max current limits)

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
// Success responses
OK:SEQ_COMPLETE
OK:MULTI_ON:1,2,5,6
DATA:R1&R2@200ms:12.5V,6.4A,80.0W
DATA:R3&R4@500ms:12.3V,3.2A,39.4W

// Error responses
ERROR:OVERCURRENT:R1&R2:8.5A
ERROR:SEQUENCE_TOO_LONG:2048
ERROR:INVALID_RELAY:9
ERROR:BUFFER_OVERFLOW
```

### 1.7 Safety Features
- [ ] Maximum current limit per relay group
- [ ] Thermal protection timing (max on-time)
- [ ] Automatic shutdown on overcurrent
- [ ] Voltage drop detection and reporting
- [ ] Emergency stop on serial disconnect

## 2. Python Controller Updates

### 2.1 Remove Legacy Code
- [ ] Delete measure_relay() method
- [ ] Delete measure_relays() method
- [ ] Remove backward compatibility wrappers
- [ ] Clean up unused relay control methods

### 2.2 New SMTArduinoController Methods
```python
def execute_sequence(self, sequence: str, timeout: float = 10.0) -> Dict[str, Any]:
    """Execute complex relay sequence
    Args:
        sequence: "R1&R2,200,OFF,50,R3,500,OFF"
    Returns:
        {
            'measurements': [
                {'time_ms': 200, 'relays': [1,2], 'voltage': 12.5, 'current': 6.4},
                {'time_ms': 750, 'relays': [3], 'voltage': 12.3, 'current': 3.2}
            ],
            'duration_ms': 750,
            'status': 'complete'
        }
    """

def activate_relay_group(self, relays: List[int], duration_ms: int = None) -> Dict[str, float]:
    """Activate multiple relays simultaneously"""

def stream_measurements(self, pattern: str, callback: Callable) -> None:
    """Stream measurements during pattern execution"""

def validate_sequence(self, sequence: str) -> Tuple[bool, str]:
    """Pre-validate sequence before execution"""
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
            "limits": {
                "current_a": {"min": 5.4, "max": 6.9},  // Applies to combined measurement
                "voltage_v": {"min": 11.5, "max": 12.5}
            }
        },
        {
            "function": "position",
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
- [ ] Modify test sequence builder to use grouped relays
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
- [ ] Binary protocol option for high-speed data
- [ ] Compressed measurement format
- [ ] Batch response mode
- [ ] Implement sliding window protocol
- [ ] **CRITICAL: Chunked response protocol for 48-relay systems**

### 4.2 Buffer Management (CRITICAL OVERFLOW RISK WITH 48 RELAYS!)
```
Worst Case Scenario: 16 boards × 3 functions = 48 relays
- Text response size: 48 × 15 chars = 720 bytes
- Arduino Uno buffer: 64 bytes ❌ OVERFLOW!
- Arduino Mega buffer: 256 bytes ❌ OVERFLOW!

SOLUTION: Chunked Response Protocol
- Split into 8-relay chunks (120 bytes each)
- ACK-based flow control between chunks
- Binary protocol option (36 bytes per 8 relays)
```

### 4.3 Chunked Response Protocol
```
CHUNK:1/6:1=12.5,3.2;2=12.4,3.1;...;8=11.8,2.5
Python: ACK
CHUNK:2/6:9=12.5,3.2;10=12.4,3.1;...;16=11.8,2.5
Python: ACK
...
CHUNK:6/6:41=12.5,3.2;...;48=11.8,2.5
CHUNK:END
```

### 4.4 Flow Control
- [ ] Implement ACK-based chunk protocol
- [ ] Add response acknowledgment system
- [ ] Create backpressure handling
- [ ] Add sequence pause/resume capability
- [ ] Timeout and retry mechanism for chunks

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

### Phase 1: Arduino Firmware Core (Week 1-2)
- Basic multi-relay control
- Simple sequence execution
- Basic measurement system

### Phase 2: Python Controller (Week 2-3)
- New controller methods
- Response parsing
- Basic testing

### Phase 3: SKU System (Week 3-4)
- New configuration format
- Parser implementation
- Migration tools

### Phase 4: Advanced Features (Week 4-5)
- Streaming measurements
- Complex patterns
- Performance optimization

### Phase 5: Testing & Polish (Week 5-6)
- Comprehensive testing
- Documentation
- Performance validation

## 8. Risk Mitigation

### 8.1 Technical Risks
- **Timing Precision**: Use hardware timers, not software delays
- **Current Spikes**: Implement soft-start for relay groups
- **Measurement Accuracy**: Synchronize ADC readings properly
- **Communication Errors**: Add retry logic and checksums

### 8.2 Implementation Risks
- **Scope Creep**: Stick to core features first
- **Compatibility**: Clean break, no legacy support
- **Testing Coverage**: Automated tests from day 1
- **Performance**: Profile early and often

## 9. Example Implementations

### 9.1 Arduino Sequence Executor
```cpp
void executeSequence(const char* sequence) {
    // Parse sequence: "R1&R2,200,OFF,50,R3,500,OFF"
    SequenceStep steps[MAX_STEPS];
    int stepCount = parseSequence(sequence, steps);
    
    for (int i = 0; i < stepCount; i++) {
        if (steps[i].isDelay) {
            delayMicroseconds(steps[i].duration_ms * 1000);
        } else {
            setRelayMask(steps[i].relayMask);
            if (steps[i].measure) {
                takeMeasurement(steps[i].relayMask, steps[i].duration_ms);
            }
        }
    }
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

- [ ] Execute 10-step sequences without timing drift
- [ ] Measure 8 relays simultaneously with <1% error
- [ ] Process 100Hz measurement stream without data loss
- [ ] Support sequences up to 60 seconds
- [ ] Maintain timing precision within ±5ms
- [ ] Zero buffer overflows in 24-hour test
- [ ] Parse new SKU format in <100ms
- [ ] Full test coverage (>90%)

## Notes and Considerations

1. **Power Supply**: Simultaneous relay activation will increase instantaneous current draw. May need to add power supply validation step.

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