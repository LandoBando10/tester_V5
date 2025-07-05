# SMT Batch Sequence Design - Full Test in One Command

## Core Concept
Send the ENTIRE test sequence to Arduino in one command, get ALL results back in one response. Simple, efficient, and leverages the Arduino R4 Minima's capabilities. Supports up to 16 relays with simultaneous activation.

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

#define MAX_SEQUENCE_STEPS 50
#define MAX_RELAYS 16
#define PCF8575_ADDRESS 0x20

PCF8575 pcf8575(PCF8575_ADDRESS);

struct TestStep {
    uint16_t relayMask;     // Internal bitmask for 16 relays
    uint16_t duration_ms;
    bool is_delay;
};

void executeTestSequence(const char* sequence) {
    TestStep steps[MAX_SEQUENCE_STEPS];
    int step_count = 0;
    
    // Parse the entire sequence first
    char* seq_copy = strdup(sequence);
    char* step_str = strtok(seq_copy, ";");
    
    while (step_str != NULL && step_count < MAX_SEQUENCE_STEPS) {
        TestStep* step = &steps[step_count];
        
        if (strncmp(step_str, "OFF:", 4) == 0) {
            // Delay step
            step->is_delay = true;
            step->duration_ms = atoi(step_str + 4);
            step->relayMask = 0;
        } else {
            // Relay activation step: "1,2,3:500"
            step->is_delay = false;
            
            // Parse relays and duration
            char* colon = strchr(step_str, ':');
            if (colon != NULL) {
                *colon = '\0';
                step->duration_ms = atoi(colon + 1);
                
                // Parse relay numbers into bitmask
                step->relayMask = parseRelaysToBitmask(step_str);
            }
        }
        
        step_count++;
        step_str = strtok(NULL, ";");
    }
    
    free(seq_copy);
    
    // Execute the sequence and collect results
    Serial.print("TESTRESULTS:");
    
    for (int i = 0; i < step_count; i++) {
        TestStep* step = &steps[i];
        
        if (step->is_delay) {
            // Just delay, no measurement
            setAllRelays(0);  // All off
            delay(step->duration_ms);
        } else {
            // Activate relays using bitmask (all switch simultaneously)
            setAllRelays(step->relayMask);
            
            // Wait for stabilization (10% of duration, max 100ms)
            delay(min(step->duration_ms / 10, 100));
            
            // Take measurement
            float voltage = measureVoltage();
            float current = measureTotalCurrent();
            
            // Send result
            if (i > 0 && !steps[i-1].is_delay) {
                Serial.print(";");
            }
            
            // Convert bitmask back to relay list for response
            printRelayListFromMask(step->relayMask);
            Serial.print(":");
            Serial.print(voltage, 1);
            Serial.print("V,");
            Serial.print(current, 1);
            Serial.print("A");
            
            // Hold for remaining duration
            delay(step->duration_ms - min(step->duration_ms / 10, 100));
            
            // Turn off relays
            setAllRelays(0);
        }
    }
    
    Serial.println(";END");
}

// Fast 16-relay control using PCF8575 I2C expander
void setAllRelays(uint16_t mask) {
    // PCF8575 updates all 16 outputs simultaneously with a single I2C write
    pcf8575.write16(mask);
    // Note: Relay board may use active LOW, so invert if needed:
    // pcf8575.write16(~mask);
}

// Helper functions
uint16_t parseRelaysToBitmask(const char* relayList) {
    // Convert "1,2,3" to bitmask 0x0007
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

void printRelayListFromMask(uint16_t mask) {
    // Convert bitmask back to "1,2,3" format
    bool first = true;
    for (int i = 0; i < 16; i++) {
        if (mask & (1 << i)) {
            if (!first) Serial.print(",");
            Serial.print(i + 1);
            first = false;
        }
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
4. **Better Timing**: Arduino controls all timing without Python delays
5. **Simpler Error Handling**: One response to parse and validate
6. **16 Relay Support**: Internal bitmask enables truly simultaneous switching
7. **R4 Minima Advantages**: 
   - 32KB RAM can buffer entire sequence
   - Fast processing ensures accurate timing
   - Large serial buffer handles long commands

## Buffer Considerations with Arduino R4 Minima

### Command Size
- Typical test: ~200-300 bytes
- Worst case (48 relays, 20 steps): ~400 bytes
- **R4 Minima: ✅ No problem with 32KB RAM**

### Response Size
- With relay grouping: ~400 bytes for 16 measurements
- Without grouping: ~720 bytes for 48 measurements
- **R4 Minima: ✅ 512+ byte serial buffer handles both**

### Conclusion
The Arduino R4 Minima's superior specifications eliminate buffer overflow concerns, making this batch approach highly reliable and efficient.