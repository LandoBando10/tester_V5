# Enhanced Relay Mapping - Minimal Change Design

## Core Concept
Keep the existing `relay_mapping` structure, but allow relay groups using comma separator.

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
        "1,2,3": {"board": 1, "function": "mainbeam"},
        "4": {"board": 1, "function": "position"},
        
        "5,6,7": {"board": 2, "function": "mainbeam"},
        "8": {"board": 2, "function": "position"},
        
        "9,10,11": {"board": 3, "function": "mainbeam"},
        "12": {"board": 3, "function": "position"},
        
        "13,14,15": {"board": 4, "function": "mainbeam"},
        "16": {"board": 4, "function": "position"}
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
        self.relay_groups = {}
        
        for relay_key, mapping in relay_mapping.items():
            if mapping is None:
                continue
                
            # Parse relay key - could be "1" or "1,2,3" up to "13,14,15,16"
            if ',' in relay_key:
                relays = [int(r) for r in relay_key.split(',')]
            else:
                relays = [int(relay_key)]
            
            # Validate relay numbers (1-16)
            if any(r < 1 or r > 16 for r in relays):
                raise ValueError(f"Invalid relay number in '{relay_key}' - must be 1-16")
            
            # Store the group info
            self.relay_groups[relay_key] = {
                'relays': relays,
                'board': mapping['board'],
                'function': mapping['function']
            }
    
    def _build_test_sequence(self) -> str:
        """Build Arduino test sequence from test_sequence config"""
        arduino_steps = []
        
        for test_config in self.parameters.get("test_sequence", []):
            function = test_config["function"]
            duration = test_config.get("duration_ms", 500)
            delay = test_config.get("delay_after_ms", 100)
            
            # Find all relay groups for this function
            for relay_key, group in self.relay_groups.items():
                if group['function'] == function:
                    relays = ','.join(map(str, group['relays']))
                    arduino_steps.append(f"{relays}:{duration}")
                    
            if delay > 0:
                arduino_steps.append(f"OFF:{delay}")
        
        # Remove last OFF if present
        if arduino_steps and arduino_steps[-1].startswith("OFF"):
            arduino_steps.pop()
        
        return ';'.join(arduino_steps)
```

## Benefits of This Approach

1. **Minimal Change** - Existing code barely needs modification
2. **Backward Compatible** - Old SKUs with single relays still work
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

## Migration Examples

### Before (Individual Relays)
```json
"relay_mapping": {
    "1": {"board": 1, "function": "mainbeam"},
    "2": {"board": 1, "function": "mainbeam"},
    "3": {"board": 1, "function": "mainbeam"}
}
```

### After (Grouped)
```json
"relay_mapping": {
    "1,2,3": {"board": 1, "function": "mainbeam"}
}
```

## Edge Cases Handled

1. **Single Relay Groups** - "4" works the same as before
2. **Mixed Configurations** - Can have both "1,2,3" and "4" in same config
3. **Large Groups** - "1,2,3,4,5,6" for high-power functions
4. **Null Mappings** - Unused relays can still be null

## Implementation Priority

1. **Phase 1**: Update relay mapping parser to handle "," separator
2. **Phase 2**: Modify test sequence builder to use grouped relays
3. **Phase 3**: Update result parser to map measurements back to groups
4. **Phase 4**: Add validation for grouped relay configurations

This design maintains the familiar structure while adding powerful grouping capabilities!