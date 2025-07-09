# SMT Batch Sequence Design - Full Test in One Command

## Core Concept
Send the ENTIRE test sequence to Arduino in one command, get ALL results back in one response. Simple, efficient, and leverages the Arduino R4 Minima's capabilities. Supports up to 16 relays with simultaneous activation. No backward compatibility - this is a clean implementation for the new system.

## Command Format

### Python Sends Complete Test Sequence
```
TESTSEQ:1,2,3:500;OFF:100;7,8,9:500;OFF:100;1,2,3,7,8,9:1000;OFF:200;4,10:300
```

Breaking it down:
- `1,2,3:500` = Activate relays 1,2,3 for 500ms and measure
- `OFF:100` = All relays off, wait 100ms
- `7,8,9:500` = Activate relays 7,8,9 for 500ms and measure
- `1,2,3,7,8,9:1000` = Activate all these relays for 1000ms and measure
- `:` = Delimiter between relay list and duration
- `;` = Step separator

### Arduino Returns Complete Results
```
TESTRESULTS:1,2,3:12.5V,6.8A;7,8,9:12.4V,6.7A;1,2,3,7,8,9:12.3V,13.5A;4,10:12.5V,2.1A;END
```

## Python Implementation

```python
class SMTArduinoController:
    def execute_full_test(self, relay_mapping: Dict, test_sequence: List) -> Dict:
        """Execute complete test sequence in one batch"""
        
        # Parse relay mapping first
        relay_groups = {}
        for relay_key, mapping in relay_mapping.items():
            if mapping is None:
                continue
            
            # Parse relay key - could be "1" or "1,2,3"
            if ',' in relay_key:
                relays = [int(r) for r in relay_key.split(',')]
            else:
                relays = [int(relay_key)]
            
            # Store by function for easy lookup
            func = mapping['function']
            board = mapping['board']
            key = f"board_{board}_{func}"
            
            relay_groups[key] = {
                'relays': relays,
                'board': board,
                'function': func
            }
        
        # Build Arduino command sequence
        arduino_commands = []
        measurement_mapping = []
        
        for test_config in test_sequence:
            function = test_config['function']
            duration = test_config.get('duration_ms', 500)
            delay = test_config.get('delay_after_ms', 100)
            
            # Find all relay groups for this function
            for key, group in relay_groups.items():
                if group['function'] == function:
                    relays = ','.join(map(str, group['relays']))
                    arduino_commands.append(f"{relays}:{duration}")
                    if delay > 0:
                        arduino_commands.append(f"OFF:{delay}")
                    
                    measurement_mapping.append({
                        'board': group['board'],
                        'function': function,
                        'limits': test_config['limits']
                    })
        
        # Remove last OFF if present
        if arduino_commands and arduino_commands[-1].startswith("OFF"):
            arduino_commands.pop()
        
        # Send entire sequence
        full_command = f"TESTSEQ:{';'.join(arduino_commands)}"
        response = self._send_command(full_command, timeout=60.0)
        
        # Parse complete results
        return self._parse_batch_results(response, measurement_mapping)
    
    def _parse_batch_results(self, response: str, group_mapping: List) -> Dict:
        """Parse batch results and map back to groups"""
        if not response.startswith("TESTRESULTS:"):
            raise ValueError(f"Invalid response: {response}")
            
        results = {
            'passed': True,
            'measurements': [],
            'failures': []
        }
        
        # Remove prefix and suffix
        data = response[12:-4]  # Remove "TESTRESULTS:" and ";END"
        measurements = data.split(';')
        
        measurement_idx = 0
        for i, mapping in enumerate(group_mapping):
            if mapping is None:
                continue  # Skip delays
                
            if measurement_idx >= len(measurements):
                results['failures'].append(f"Missing measurement for step {i}")
                continue
                
            # Parse measurement: "1,2,3:12.5V,6.8A"
            meas_data = measurements[measurement_idx]
            relay_part, value_part = meas_data.split(':')
            voltage, current = value_part.rstrip('VA').split(',')
            
            measurement = {
                'relays': [int(r) for r in relay_part.split(',')],
                'voltage': float(voltage),
                'current': float(current),
                'power': float(voltage) * float(current)
            }
            
            # Add context from mapping
            if 'group_name' in mapping:
                # Single group test
                measurement.update({
                    'group_name': mapping['group_name'],
                    'board': mapping['board'],
                    'function': mapping['function']
                })
                
                # Check limits
                limits = mapping['limits']
                if not (limits['current_a']['min'] <= measurement['current'] <= limits['current_a']['max']):
                    results['failures'].append(
                        f"{mapping['group_name']}: Current {measurement['current']}A outside limits "
                        f"[{limits['current_a']['min']}-{limits['current_a']['max']}]"
                    )
                    results['passed'] = False
                    
            else:
                # Multiple groups test
                measurement.update({
                    'groups': mapping['groups'],
                    'boards': mapping['boards'],
                    'functions': mapping['functions']
                })
            
            results['measurements'].append(measurement)
            measurement_idx += 1
        
        return results
```

## Arduino Implementation (16 Relay Support with PCF8575)

```cpp
#include <Wire.h>
#include <PCF8575.h>
#include <INA260.h>  // For current/voltage measurement

#define MAX_SEQUENCE_STEPS 50
#define MAX_RELAYS 16
#define PCF8575_ADDRESS 0x20
#define INA260_ADDRESS 0x40
#define STABILIZATION_TIME 50   // ms to wait after relay activation
#define MIN_DURATION 100        // minimum duration for any step
#define RELAY_ACTIVE_LOW false  // Set true if relays are active LOW

PCF8575 pcf8575(PCF8575_ADDRESS);
INA260 ina260;
bool hardware_ready = false;

struct TestStep {
    uint16_t relayMask;     // Internal bitmask for 16 relays
    uint16_t duration_ms;
    bool is_delay;
};

void executeTestSequence(const char* sequence) {
    if (!hardware_ready) {
        Serial.println("ERROR:I2C_FAIL");
        return;
    }
    
    TestStep steps[MAX_SEQUENCE_STEPS];
    int step_count = 0;
    
    // Parse sequence with validation
    step_count = parseSequence(sequence, steps, MAX_SEQUENCE_STEPS);
    if (step_count <= 0) {
        Serial.println("ERROR:INVALID_SEQUENCE");
        return;
    }
    
    // Validate sequence
    for (int i = 0; i < step_count; i++) {
        if (!steps[i].is_delay && steps[i].duration_ms < MIN_DURATION) {
            Serial.println("ERROR:DURATION_TOO_SHORT");
            return;
        }
        // Validate relay numbers are within range 1-16
        if (!steps[i].is_delay) {
            for (int bit = 16; bit < 32; bit++) {
                if (steps[i].relayMask & (1 << bit)) {
                    Serial.println("ERROR:INVALID_RELAY");
                    return;
                }
            }
        }
    }
    
    // Pre-allocate response buffer (R4 Minima has 32KB RAM)
    char response[MAX_RESPONSE_SIZE];
    strcpy(response, "TESTRESULTS:");
    int response_len = strlen(response);
    
    // Execute sequence
    unsigned long sequence_start = millis();
    
    for (int i = 0; i < step_count; i++) {
        TestStep* step = &steps[i];
        
        if (step->is_delay) {
            // Non-blocking delay with emergency stop check
            unsigned long delay_start = millis();
            while (millis() - delay_start < step->duration_ms) {
                if (Serial.available() && Serial.read() == 'X') {
                    setAllRelays(0);
                    Serial.println("OK:ALL_OFF");
                    return;
                }
                delay(10);  // Small delay to not hog CPU
            }
        } else {
            // Activate relays
            setAllRelays(step->relayMask);
            
            // Stabilization delay
            delay(STABILIZATION_TIME);
            
            // Take measurement with retry
            float voltage = 0, current = 0;
            bool measurement_ok = false;
            
            for (int retry = 0; retry < 3; retry++) {
                delay(2);  // INA260 conversion time
                if (ina260.readVoltage(&voltage) && ina260.readCurrent(&current)) {
                    // Validate readings
                    if (voltage >= 0 && voltage <= 30 && current >= 0 && current <= 10) {
                        measurement_ok = true;
                        break;
                    }
                }
            }
            
            if (!measurement_ok) {
                setAllRelays(0);
                Serial.println("ERROR:MEASUREMENT_FAIL");
                return;
            }
            
            // Add to response buffer
            char measurement[50];
            char relay_list[30];
            maskToRelayList(step->relayMask, relay_list);
            int len = snprintf(measurement, sizeof(measurement), 
                             "%s:%.1fV,%.1fA;", relay_list, voltage, current);
            
            // Check buffer space
            if (response_len + len < sizeof(response) - 10) {
                strcat(response, measurement);
                response_len += len;
            } else {
                setAllRelays(0);
                Serial.println("ERROR:RESPONSE_TOO_LONG");
                return;
            }
            
            // Hold for remaining duration
            int remaining = step->duration_ms - STABILIZATION_TIME;
            if (remaining > 0) {
                delay(remaining);
            }
            
            // Turn off relays
            setAllRelays(0);
        }
        
        // Check timeout
        if (millis() - sequence_start > 30000) {
            Serial.println("ERROR:SEQUENCE_TIMEOUT");
            return;
        }
    }
    
    // Send complete response
    strcat(response, "END");
    Serial.println(response);
}

// Fast 16-relay control using PCF8575 I2C expander
void setAllRelays(uint16_t mask) {
    if (RELAY_ACTIVE_LOW) {
        mask = ~mask;  // Invert for active LOW relays
    }
    pcf8575.write16(mask);
}

// Parse complete sequence into steps
int parseSequence(const char* sequence, TestStep* steps, int max_steps) {
    char* seq_copy = strdup(sequence);
    char* step_str = strtok(seq_copy, ";");
    int count = 0;
    
    while (step_str != NULL && count < max_steps) {
        TestStep* step = &steps[count];
        
        if (strncmp(step_str, "OFF:", 4) == 0) {
            step->is_delay = true;
            step->duration_ms = atoi(step_str + 4);
            step->relayMask = 0;
            
            if (step->duration_ms <= 0 || step->duration_ms > 10000) {
                free(seq_copy);
                return -1;  // Invalid delay
            }
        } else {
            step->is_delay = false;
            
            // Find colon separator
            char* colon = strchr(step_str, ':');
            if (colon == NULL) {
                free(seq_copy);
                return -1;  // Invalid format
            }
            
            *colon = '\0';
            step->duration_ms = atoi(colon + 1);
            
            if (step->duration_ms <= 0 || step->duration_ms > 10000) {
                free(seq_copy);
                return -1;  // Invalid duration
            }
            
            // Parse relay list
            step->relayMask = parseRelaysToBitmask(step_str);
            if (step->relayMask == 0) {
                free(seq_copy);
                return -1;  // No valid relays
            }
        }
        
        count++;
        step_str = strtok(NULL, ";");
    }
    
    free(seq_copy);
    return count;
}

// Helper functions
uint16_t parseRelaysToBitmask(const char* relayList) {
    uint16_t mask = 0;
    char* str = strdup(relayList);
    char* token = strtok(str, ",");
    
    while (token != NULL) {
        int relay = atoi(token);
        if (relay >= 1 && relay <= MAX_RELAYS) {
            mask |= (1 << (relay - 1));
        } else {
            // Invalid relay number
            free(str);
            return 0;
        }
        token = strtok(NULL, ",");
    }
    free(str);
    return mask;
}

void maskToRelayList(uint16_t mask, char* output) {
    output[0] = '\0';
    bool first = true;
    
    for (int i = 0; i < MAX_RELAYS; i++) {
        if (mask & (1 << i)) {
            if (!first) strcat(output, ",");
            char num[4];
            sprintf(num, "%d", i + 1);
            strcat(output, num);
            first = false;
        }
    }
}

// Hardware initialization
void setup() {
    Serial.begin(115200);
    Wire.begin();
    
    // Startup communication remains unchanged
    // Handle board type queries and other initialization
    
    // Initialize PCF8575
    Wire.beginTransmission(PCF8575_ADDRESS);
    if (Wire.endTransmission() == 0) {
        pcf8575.begin();
        setAllRelays(0);  // All relays off
        
        // Initialize INA260
        if (ina260.begin(INA260_ADDRESS)) {
            hardware_ready = true;
            Serial.println("SMT Tester Ready");
        } else {
            Serial.println("ERROR:INA260_FAIL");
        }
    } else {
        Serial.println("ERROR:I2C_FAIL");
    }
}
```

## Example Usage

### SKU Configuration (Using Comma-Separated Relay Mapping)
```json
{
    "relay_mapping": {
        "1,2,3": {"board": 1, "function": "mainbeam"},
        "4": {"board": 1, "function": "position"},
        "5,6": {"board": 1, "function": "turn_signal"},
        "7,8,9": {"board": 2, "function": "mainbeam"},
        "10": {"board": 2, "function": "position"},
        "11,12": {"board": 2, "function": "turn_signal"}
    },
    
    "test_sequence": [
        {
            "function": "mainbeam",
            "duration_ms": 500,
            "delay_after_ms": 100,
            "limits": {
                "current_a": {"min": 5.4, "max": 6.9},
                "voltage_v": {"min": 11.5, "max": 12.5}
            }
        },
        {
            "function": "position",
            "duration_ms": 300,
            "delay_after_ms": 0,
            "limits": {
                "current_a": {"min": 0.8, "max": 1.2},
                "voltage_v": {"min": 11.5, "max": 12.5}
            }
        }
    ]
}
```

### Python Execution
```python
# Execute entire test sequence in one go
results = controller.execute_full_test(
    sku_config['relay_mapping'], 
    sku_config['test_sequence']
)

# Results contain all measurements with full context
for measurement in results['measurements']:
    print(f"Board {measurement['board']} {measurement['function']}: "
          f"{measurement['current']}A @ {measurement['voltage']}V")
```

### What Gets Sent to Arduino
```
TESTSEQ:1,2,3:500;OFF:100;7,8,9:500;OFF:100;13,14,15,16:500
```
Simple relay lists up to 16 relays, human-readable format.

### What Arduino Returns
```
TESTRESULTS:1,2,3:12.5V,6.8A;7,8,9:12.4V,6.7A;13,14,15,16:12.3V,8.2A;END
```
Same format - relay lists with measurements. Bitmask is internal only.

## Benefits

1. **Single Command**: Entire test runs with one serial command
2. **Atomic Operation**: Either the whole test succeeds or fails
3. **Reduced Overhead**: No back-and-forth communication during test
4. **Better Timing**: Arduino controls all timing precisely
5. **Error Handling**: Clear error messages for each failure type
6. **16 Relay Support**: PCF8575 enables truly simultaneous switching
7. **Safety Features**: 
   - Emergency stop always works
   - Timeout protection
   - Measurement validation
   - Buffer overflow prevention
8. **Clean Implementation**: No legacy code or backward compatibility concerns
9. **Consistent Format**: All SKUs use the new comma-separated relay mapping

## Implementation Considerations

### Hardware Requirements
- Arduino R4 Minima
- PCF8575 I2C expander at address 0x20
- INA260 current/voltage sensor at address 0x40
- Pull-up resistors on I2C lines (typically 4.7kΩ)

### Timing Constraints
- Minimum duration: 100ms per step
- Stabilization time: 50ms (configurable)
- INA260 conversion: 1.1ms minimum
- Maximum sequence: 30 seconds total

### Buffer Management
- Fixed 500-char response buffer
- Pre-allocated to prevent fragmentation
- Supports ~15 measurements safely
- Error if response would overflow

### Error Recovery
- All errors turn off relays immediately
- Clear error codes for debugging
- Hardware checks on startup (keeping existing startup sequence)
- Measurement retry logic

### Startup Communication
- Board type queries remain unchanged
- Initialization handshake preserved
- Only the test execution commands are replaced