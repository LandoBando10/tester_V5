# SMT Batch Sequence Design - Full Test in One Command

## Core Concept
Send the ENTIRE test sequence to Arduino in one command, get ALL results back in one response. This leverages the Arduino R4 Minima's capabilities for efficient, atomic test operations.

## Command Format

### Python Sends Complete Test Sequence
```
TESTSEQ:1,2,3,500;OFF,100;7,8,9,500;OFF,100;1,2,3,7,8,9,1000;OFF,200;4,10,300
```

Breaking it down:
- `1,2,3,500` = Activate relays 1,2,3 for 500ms and measure
- `OFF,100` = All relays off, wait 100ms
- `7,8,9,500` = Activate relays 7,8,9 for 500ms and measure
- `1,2,3,7,8,9,1000` = Activate all these relays for 1000ms and measure
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
            
            # Find all relay groups for this function
            for key, group in relay_groups.items():
                if group['function'] == function:
                    relays = ','.join(map(str, group['relays']))
                    arduino_commands.append(f"{relays},500")  # 500ms default
                    arduino_commands.append("OFF,100")  # 100ms between
                    
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

## Arduino Implementation

```cpp
#define MAX_SEQUENCE_STEPS 50
#define MAX_RELAYS_PER_STEP 48

struct TestStep {
    uint8_t relays[MAX_RELAYS_PER_STEP];
    uint8_t relay_count;
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
        
        if (strncmp(step_str, "OFF,", 4) == 0) {
            // Delay step
            step->is_delay = true;
            step->duration_ms = atoi(step_str + 4);
        } else {
            // Relay activation step
            step->is_delay = false;
            
            // Parse relays and duration
            char* last_comma = strrchr(step_str, ',');
            if (last_comma != NULL) {
                *last_comma = '\0';
                step->duration_ms = atoi(last_comma + 1);
                
                // Parse relay numbers
                step->relay_count = parseRelayList(step_str, step->relays);
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
            allRelaysOff();
            delay(step->duration_ms);
        } else {
            // Activate relays
            activateRelays(step->relays, step->relay_count);
            
            // Wait for stabilization (10% of duration, max 100ms)
            delay(min(step->duration_ms / 10, 100));
            
            // Take measurement
            float voltage = measureVoltage();
            float current = measureTotalCurrent();
            
            // Send result
            if (i > 0 && !steps[i-1].is_delay) {
                Serial.print(";");
            }
            
            printRelayList(step->relays, step->relay_count);
            Serial.print(":");
            Serial.print(voltage, 1);
            Serial.print("V,");
            Serial.print(current, 1);
            Serial.print("A");
            
            // Hold for remaining duration
            delay(step->duration_ms - min(step->duration_ms / 10, 100));
            
            // Turn off relays
            allRelaysOff();
        }
    }
    
    Serial.println(";END");
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
            "limits": {
                "current_a": {"min": 5.4, "max": 6.9},
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
TESTSEQ:1,2,3,500;OFF,100;7,8,9,500;OFF,100;1,2,3,7,8,9,1000;OFF,200;4,10,16,22,300
```

### What Arduino Returns
```
TESTRESULTS:1,2,3:12.5V,6.8A;7,8,9:12.4V,6.7A;1,2,3,7,8,9:12.3V,13.5A;4,10,16,22:12.5V,4.2A;END
```

## Benefits

1. **Single Command**: Entire test runs with one serial command
2. **Atomic Operation**: Either the whole test succeeds or fails
3. **Reduced Overhead**: No back-and-forth communication during test
4. **Better Timing**: Arduino controls all timing without Python delays
5. **Simpler Error Handling**: One response to parse and validate
6. **R4 Minima Advantages**: 
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