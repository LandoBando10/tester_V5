# Enhanced Relay Mapping - New Design

## Core Concept
New `relay_mapping` structure that uses comma-separated relay groups. No backward compatibility needed - all SKUs will be converted to the new format.

## Maximum Relay Support
- **Hard limit**: 16 relays maximum (hardware constraint from PCF8575)
- **Valid relay numbers**: 1-16 only
- **No support for relay numbers > 16**

## Current Structure (Single Relays)
```json
"relay_mapping": {
    "1": {
        "board": 1,
        "function": "mainbeam"
    },
    "2": {
        "board": 2,
        "function": "mainbeam"
    }
}
```

## Enhanced Structure (Supporting Groups)
```json
"relay_mapping": {
    "1,2,3": {
        "board": 1,
        "function": "mainbeam"
    },
    "4": {
        "board": 1,
        "function": "position"
    },
    "5,6": {
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
}
```

## Real-World Example: 4-Board Panel (16 Relays)
```json
{
    "description": "4-board LED panel - 16 relays total",
    
    "panel_layout": {
        "rows": 2,
        "columns": 2,
        "total_boards": 4
    },
    
    "relay_mapping": {
        // Board 1
        "1,2,3": {"board": 1, "function": "mainbeam"},
        "4": {"board": 1, "function": "position"},
        "5,6": {"board": 1, "function": "turn_signal"},
        
        // Board 2
        "7,8,9": {"board": 2, "function": "mainbeam"},
        "10": {"board": 2, "function": "position"},
        "11,12": {"board": 2, "function": "turn_signal"},
        
        // Board 3
        "13,14,15": {"board": 3, "function": "mainbeam"},
        "16": {"board": 3, "function": "position"}
        // Note: Only 16 relays total, so board 3 has no turn_signal
        // and board 4 is not used in this example
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
            "delay_after_ms": 100,
            "limits": {
                "current_a": {"min": 0.8, "max": 1.2},
                "voltage_v": {"min": 11.5, "max": 12.5}
            }
        },
        {
            "function": "turn_signal",
            "duration_ms": 400,
            "delay_after_ms": 0,
            "limits": {
                "current_a": {"min": 3.6, "max": 4.2},
                "voltage_v": {"min": 11.5, "max": 12.5}
            }
        }
    ]
}
```

## Python Implementation Changes

```python
class SMTArduinoController:
    def _parse_relay_mapping(self, relay_mapping: Dict) -> Dict:
        """Parse relay mapping, handling grouped relays (up to 16 relays)"""
        relay_groups = {}
        used_relays = set()
        
        for relay_key, mapping in relay_mapping.items():
            if mapping is None:
                continue
                
            # Parse relay key - could be "1" or "1,2,3" up to "13,14,15,16"
            if ',' in relay_key:
                relays = [int(r.strip()) for r in relay_key.split(',')]
            else:
                relays = [int(relay_key.strip())]
            
            # Validate relay numbers (1-16)
            for relay in relays:
                if relay < 1 or relay > 16:
                    raise ValueError(f"Invalid relay number {relay} in '{relay_key}' - must be 1-16")
                if relay in used_relays:
                    raise ValueError(f"Relay {relay} appears in multiple groups")
                used_relays.add(relay)
            
            # Validate no more than 16 total relays
            if len(used_relays) > 16:
                raise ValueError(f"Total relay count {len(used_relays)} exceeds maximum of 16")
            
            # Store the group info
            board = mapping.get('board')
            function = mapping.get('function')
            
            if not board or not function:
                raise ValueError(f"Missing board or function for relay group '{relay_key}'")
            
            relay_groups[relay_key] = {
                'relays': relays,
                'board': board,
                'function': function
            }
        
        return relay_groups
    
    def _build_test_sequence(self, relay_groups: Dict, test_sequence: List) -> str:
        """Build Arduino test sequence from test_sequence config"""
        arduino_steps = []
        total_duration = 0
        active_relays = set()
        
        for test_config in test_sequence:
            function = test_config.get("function")
            duration = test_config.get("duration_ms", 500)
            delay = test_config.get("delay_after_ms", 100)
            
            # Validate timing
            if duration < 100:
                raise ValueError(f"Duration {duration}ms too short for function {function} (min 100ms)")
            
            # Find all relay groups for this function
            found_any = False
            new_active_relays = set()
            
            for relay_key, group in relay_groups.items():
                if group['function'] == function:
                    # Check for relay overlap
                    relay_set = set(group['relays'])
                    if active_relays and relay_set & active_relays:
                        overlapping = relay_set & active_relays
                        raise ValueError(f"Relay overlap detected: relays {overlapping} are already active")
                    
                    new_active_relays.update(relay_set)
                    relays = ','.join(map(str, group['relays']))
                    arduino_steps.append(f"{relays}:{duration}")
                    total_duration += duration
                    found_any = True
            
            active_relays = new_active_relays
                    
            if not found_any:
                # Warning, but don't fail - function might not be mapped
                print(f"Warning: No relay mapping found for function '{function}'")
                
            if delay > 0:
                arduino_steps.append(f"OFF:{delay}")
                total_duration += delay
                active_relays.clear()  # OFF command turns all relays off
        
        # Remove last OFF if present
        if arduino_steps and arduino_steps[-1].startswith("OFF"):
            last_delay = int(arduino_steps[-1].split(':')[1])
            total_duration -= last_delay
            arduino_steps.pop()
        
        # Check total duration
        if total_duration > 30000:
            raise ValueError(f"Total sequence duration {total_duration}ms exceeds 30 second limit")
        
        return ';'.join(arduino_steps)
```

## Benefits of This Approach

1. **Clean Implementation** - No legacy code to maintain
2. **Consistent Format** - All SKUs use the same structure
3. **Intuitive** - "1,2,3" clearly means relays 1, 2, and 3 work together
4. **Flexible** - Can mix single relays and groups in same config
5. **Natural Limits** - Limits in test_sequence apply to the combined measurement
6. **16 Relay Support** - Handles up to 16 simultaneous relays
7. **Simple Protocol** - Commands stay human-readable, no binary formats

## How It Works

### Configuration
```json
"relay_mapping": {
    "1,2,3": {"board": 1, "function": "mainbeam"},
    "7,8,9": {"board": 2, "function": "mainbeam"}
}
```

### Python Processing
1. Parses "1,2,3" into relays [1,2,3]
2. When testing "mainbeam" function, finds all entries with that function
3. Sends to Arduino: `TESTSEQ:1,2,3:500;OFF:100;7,8,9:500`

### Arduino Response
```
TESTRESULTS:1,2,3:12.5V,6.8A;7,8,9:12.4V,6.7A;END
```

### Python Maps Back
- "1,2,3" measurement → board 1, mainbeam function
- "7,8,9" measurement → board 2, mainbeam function

## SKU Format Examples

### Old Format (No Longer Supported)
```json
"relay_mapping": {
    "1": {"board": 1, "function": "mainbeam"},
    "2": {"board": 1, "function": "mainbeam"},
    "3": {"board": 1, "function": "mainbeam"}
}
```

### New Format (Required)
```json
"relay_mapping": {
    "1,2,3": {"board": 1, "function": "mainbeam"}
}
```

All existing SKUs must be converted to use the new grouped format before deployment.

## Edge Cases Handled

1. **Single Relay Groups** - Use "4" format (without comma) for single relays
2. **Mixed Configurations** - Can have both "1,2,3" and "4" in same config
3. **Large Groups** - "1,2,3,4,5,6" for high-power functions
4. **All 16 Relays Must Be Mapped** - No unused relay slots in new format

## Validation Examples

### Good Configuration
```json
{
    "relay_mapping": {
        "1,2,3": {"board": 1, "function": "mainbeam"},
        "4": {"board": 1, "function": "position"},
        "5,6": {"board": 2, "function": "mainbeam"}
    }
}
```
✅ No duplicate relays
✅ All relays in valid range (1-16)
✅ All have board and function

### Bad Configuration - Duplicate Relay
```json
{
    "relay_mapping": {
        "1,2,3": {"board": 1, "function": "mainbeam"},
        "3,4": {"board": 2, "function": "position"}  // ERROR: Relay 3 used twice
    }
}
```
❌ ValueError: Relay 3 appears in multiple groups

### Bad Configuration - Invalid Relay Number
```json
{
    "relay_mapping": {
        "15,16,17": {"board": 1, "function": "mainbeam"}  // ERROR: Relay 17 > 16
    }
}
```
❌ ValueError: Invalid relay number 17 - must be 1-16

## Implementation Priority

1. **SKU Conversion**: Convert all existing SKUs to new format
2. **Validation First**: Ensure relay mapping is valid before use
3. **Clear Error Messages**: Help users fix configuration issues
4. **Timing Validation**: Prevent too-short durations (min 100ms)
5. **Total Duration Check**: Prevent tests exceeding 30 seconds
6. **Startup Communication**: Keep board initialization sequence unchanged

This design provides a clean implementation focused on the new simultaneous relay activation capabilities!