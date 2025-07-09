# SMT Tester Firmware Update Summary

## Version: 2.0.0

### Major Changes Implemented

1. **PCF8575 I2C Expander Support**
   - Replaced direct GPIO control with PCF8575 I2C expander
   - Supports all 16 relays through single I2C device at address 0x20
   - Configurable active-LOW/HIGH relay logic via `RELAY_ACTIVE_LOW` flag

2. **TESTSEQ Batch Command**
   - New command format: `TESTSEQ:1,2,3:500;OFF:100;7,8,9:500;OFF:100`
   - Supports simultaneous relay activation (up to 8 by default)
   - OFF command turns all relays off (not just a delay)
   - Response format: `TESTRESULTS:1,2,3:12.5V,6.8A;7,8,9:12.4V,6.7A;END`

3. **Relay State Management**
   - Implemented bitmask-based relay control (uint16_t)
   - Added relay validation to prevent overlaps between consecutive activations
   - Maximum simultaneous relay limit configurable (default: 8)

4. **Timing System**
   - Millis()-based timing for non-blocking operation
   - Emergency stop (X command) check during sequences
   - Configurable stabilization time (50ms)
   - Minimum duration validation (100ms)
   - Sequence timeout protection (30 seconds)

5. **Safety Features**
   - Relay number validation (1-16 only)
   - Relay overlap detection
   - I2C communication verification on startup
   - Buffer overflow prevention
   - Emergency stop always functional

6. **Error Handling**
   - New error responses:
     - ERROR:SEQUENCE_TOO_LONG
     - ERROR:INVALID_RELAY (for relays > 16)
     - ERROR:RELAY_OVERLAP
     - ERROR:I2C_FAIL
     - ERROR:MEASUREMENT_FAIL
     - ERROR:SEQUENCE_TIMEOUT
     - ERROR:TOO_MANY_RELAYS

7. **Backward Compatibility**
   - GET_BOARD_TYPE command returns "BOARD_TYPE:SMT_TESTER"
   - X command (emergency stop) still supported
   - I, B, V, RESET_SEQ commands unchanged
   - Removed TX command in favor of TESTSEQ

### Hardware Requirements

- Arduino R4 Minima (32KB RAM, 256KB Flash)
- PCF8575 I2C I/O expander at address 0x20
- INA260 power monitor at address 0x40
- 16 relay modules (active-LOW or active-HIGH configurable)

### Usage Example

```
// Test relays 1,2,3 for 500ms, then off for 100ms, then test 7,8,9 for 500ms
TESTSEQ:1,2,3:500;OFF:100;7,8,9:500

// Response
TESTRESULTS:1,2,3:12.5V,6.8A;7,8,9:12.4V,6.7A;END
```

### Configuration Options

```cpp
#define MAX_SIMULTANEOUS_RELAYS 8  // Maximum relays active at once
#define STABILIZATION_TIME 50      // ms to wait after relay activation
#define MIN_DURATION 100           // ms minimum duration per step
#define SEQUENCE_TIMEOUT 30000     // 30 second maximum sequence time
const bool RELAY_ACTIVE_LOW = true;  // Set false for active-HIGH relays
```

### Notes

- All relays must be connected through PCF8575 (no direct GPIO control)
- Each relay can only be in one group at a time
- OFF command is required between activations of overlapping relays
- Response buffer limited to 500 characters (sufficient for 16 relays)