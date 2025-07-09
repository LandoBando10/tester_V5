# TESTSEQ Protocol Specification

## Protocol Version: 1.0

### Overview

The TESTSEQ protocol enables efficient batch testing of SMT panels with simultaneous relay activation. This specification defines the command and response formats.

## Command Format

### TESTSEQ Command

**Syntax:**
```
TESTSEQ:<step1>;<step2>;...;<stepN>
```

**Step Format:**
- Relay activation: `<relay_list>:<duration_ms>`
- Delay step: `OFF:<delay_ms>`

**Examples:**
```
TESTSEQ:1,2,3:500;OFF:100;7,8,9:500
TESTSEQ:1:300;2:300;3:300
TESTSEQ:1,2,3,4,5,6,7,8:1000;OFF:500;9,10,11,12,13,14,15,16:1000
```

### Other Commands

| Command | Description | Response |
|---------|-------------|----------|
| `X` | Emergency stop - all relays off | `OK:ALL_OFF` |
| `GET_BOARD_TYPE` | Get board identifier | `BOARD_TYPE:SMT_TESTER` |
| `I` | Get firmware info | `ID:SMT_TESTER_V2.0_16RELAY_PCF8575` |
| `B` | Get button status | `BUTTON:PRESSED` or `BUTTON:RELEASED` |
| `V` | Get supply voltage | `VOLTAGE:12.500` |
| `RESET_SEQ` | Reset sequence numbers | `OK:SEQ_RESET` |

## Response Format

### TESTRESULTS Response

**Syntax:**
```
TESTRESULTS:<measurement1>;<measurement2>;...;<measurementN>;END
```

**Measurement Format:**
```
<relay_list>:<voltage>V,<current>A
```

**Example:**
```
TESTRESULTS:1,2,3:12.5V,6.8A;7,8,9:12.4V,6.7A;END
```

### Error Responses

| Error | Description |
|-------|-------------|
| `ERROR:SEQUENCE_TOO_LONG` | More than 50 steps |
| `ERROR:INVALID_SEQUENCE` | Malformed command |
| `ERROR:INVALID_RELAY` | Relay number > 16 |
| `ERROR:RELAY_OVERLAP` | Relay active in consecutive steps |
| `ERROR:I2C_FAIL` | PCF8575 communication error |
| `ERROR:MEASUREMENT_FAIL` | INA260 read failure |
| `ERROR:SEQUENCE_TIMEOUT` | Exceeded 30 second limit |
| `ERROR:TOO_MANY_RELAYS` | Exceeded simultaneous relay limit |

## Protocol Rules

### 1. Relay Numbering
- Valid range: 1-16
- Hardware limited by PCF8575 16-bit I/O

### 2. Relay Groups
- Multiple relays separated by commas: `1,2,3`
- No spaces in relay lists
- Each relay in one group only

### 3. Timing Constraints
- Minimum duration: 100ms
- Maximum sequence time: 30 seconds
- Duration includes:
  - Stabilization time: 50ms
  - Measurement time: 2ms
  - Hold time: remainder

### 4. OFF Command
- `OFF` turns all relays off
- Not just a delay - actively deactivates relays
- Required between overlapping relay activations

### 5. Measurement Behavior
- One measurement per relay group activation
- Taken after stabilization period
- Validated for reasonable ranges (0-30V, 0-10A)

## Timing Diagram

```
Command: TESTSEQ:1,2,3:500;OFF:100;7,8,9:500

Timeline:
0ms     ─┬─ Relays 1,2,3 ON
50ms    ─┼─ Stabilization complete
52ms    ─┼─ Measurement taken
500ms   ─┼─ Relays 1,2,3 OFF
         │  (OFF:100 delay)
600ms   ─┼─ Relays 7,8,9 ON
650ms   ─┼─ Stabilization complete
652ms   ─┼─ Measurement taken
1100ms  ─┴─ Relays 7,8,9 OFF
         Response sent
```

## Implementation Example

### Arduino (Simplified)
```cpp
void executeTestSequence(const char* sequence, unsigned int seq) {
    TestStep steps[MAX_SEQUENCE_STEPS];
    int stepCount = parseTestSequence(sequence, steps);
    
    char response[500];
    strcpy(response, "TESTRESULTS:");
    
    for (int i = 0; i < stepCount; i++) {
        if (steps[i].is_off) {
            setRelayMask(0);
            delay(steps[i].duration_ms);
        } else {
            setRelayMask(steps[i].relayMask);
            delay(STABILIZATION_TIME);
            
            float voltage, current;
            if (takeMeasurement(&voltage, &current)) {
                char measurement[50];
                sprintf(measurement, "%s:%.1fV,%.1fA;", 
                        relayList, voltage, current);
                strcat(response, measurement);
            }
            
            int remaining = steps[i].duration_ms - STABILIZATION_TIME - MEASUREMENT_TIME;
            if (remaining > 0) delay(remaining);
            
            setRelayMask(0);
        }
    }
    
    strcat(response, "END");
    sendReliableResponse(response, seq);
}
```

### Python Client
```python
def execute_test_sequence(relay_mapping, test_sequence):
    # Build command
    command = self._build_testseq_command(relay_mapping, test_sequence)
    
    # Send and receive
    response = self._send_command(command, timeout=30.0)
    
    # Parse response
    if response.startswith("TESTRESULTS:"):
        return self._parse_testresults(response)
    else:
        raise Exception(f"Unexpected response: {response}")
```

## Validation Requirements

### Command Validation
1. Verify relay numbers 1-16
2. Check for duplicate relays in consecutive non-OFF steps
3. Validate timing >= 100ms per step
4. Calculate total time <= 30 seconds

### Response Validation
1. Verify format starts with `TESTRESULTS:`
2. Verify format ends with `;END`
3. Validate voltage range 0-30V
4. Validate current range 0-10A
5. Match relay groups to command

## Version History

- **1.0** (2024): Initial TESTSEQ protocol specification
  - Simultaneous relay activation
  - PCF8575 16-relay support
  - Batch command/response model