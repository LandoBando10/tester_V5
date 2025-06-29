# 16-Relay SMT Testing Workflow Examples

## Overview
This document provides practical workflow examples for using the 16-relay SMT testing system. The system uses a single test command:
- `TX` - Test specified relays (1-16)

## Example 1: Simple 4-Board Panel (Mainbeam Only)

### SKU Configuration
```json
{
  "sku": "EX-4MB",
  "description": "4-board mainbeam panel",
  "relay_mapping": {
    "1": {"board": 1, "function": "mainbeam"},
    "2": {"board": 2, "function": "mainbeam"},
    "3": {"board": 3, "function": "mainbeam"},
    "4": {"board": 4, "function": "mainbeam"},
    "5": null,
    "6": null,
    "7": null,
    "8": null,
    "9": null,
    "10": null,
    "11": null,
    "12": null,
    "13": null,
    "14": null,
    "15": null,
    "16": null
  }
}
```

### Testing Workflow
1. **System detects active relays**: 1, 2, 3, 4
2. **Python sends command**: `TX:1,2,3,4`
3. **Arduino tests only 4 relays** (~0.5 seconds)
4. **Response received**: 
   ```
   PANELX:1=12.847,3.260;2=12.850,3.245;3=12.843,3.267;4=12.841,3.251
   ```
5. **Results mapped to boards**:
   - Board 1: 12.847V, 3.260A
   - Board 2: 12.850V, 3.245A
   - Board 3: 12.843V, 3.267A
   - Board 4: 12.841V, 3.251A

**Time saved**: 1.5 seconds vs testing all 16 relays

## Example 2: Complex 8-Board Panel (Dual Function)

### SKU Configuration
```json
{
  "sku": "EX-8DUAL",
  "description": "8-board panel with mainbeam and backlight",
  "relay_mapping": {
    "1": {"board": 1, "function": "mainbeam"},
    "2": {"board": 2, "function": "mainbeam"},
    "3": {"board": 3, "function": "mainbeam"},
    "4": {"board": 4, "function": "mainbeam"},
    "5": {"board": 5, "function": "mainbeam"},
    "6": {"board": 6, "function": "mainbeam"},
    "7": {"board": 7, "function": "mainbeam"},
    "8": {"board": 8, "function": "mainbeam"},
    "9": {"board": 1, "function": "backlight"},
    "10": {"board": 2, "function": "backlight"},
    "11": {"board": 3, "function": "backlight"},
    "12": {"board": 4, "function": "backlight"},
    "13": {"board": 5, "function": "backlight"},
    "14": {"board": 6, "function": "backlight"},
    "15": {"board": 7, "function": "backlight"},
    "16": {"board": 8, "function": "backlight"}
  }
}
```

### Testing Workflow
1. **System detects all 16 relays active**
2. **Python sends command**: `TX:ALL` or `TX:1-16`
3. **Arduino tests all 16 relays** (~2 seconds)
4. **Response received**: 
   ```
   PANELX:1=12.847,3.260;2=12.850,3.245;...;15=5.123,0.450;16=5.125,0.448
   ```
5. **Results distributed by function**:
   - Mainbeam (relays 1-8): High current ~3.2A
   - Backlight (relays 9-16): Low current ~0.45A

## Example 3: 8-Relay Panel (Former T Command Use Case)

### Use Case
Testing a SKU that uses relays 1-8 (previously used T command).

### SKU Configuration
```json
{
  "relay_mapping": {
    "1": {"board": 1, "function": "mainbeam"},
    "2": {"board": 2, "function": "mainbeam"},
    "3": {"board": 3, "function": "mainbeam"},
    "4": {"board": 4, "function": "mainbeam"},
    "5": {"board": 5, "function": "mainbeam"},
    "6": {"board": 6, "function": "mainbeam"},
    "7": {"board": 7, "function": "mainbeam"},
    "8": {"board": 8, "function": "mainbeam"}
  }
}
```

### Testing Workflow
1. **Python detects relays 1-8 are active**
2. **Python sends command**: `TX:1-8`
3. **Arduino tests relays 1-8** (~1 second)
4. **Response in new format**: 
   ```
   PANELX:1=12.847,3.260;2=12.850,3.245;3=12.843,3.267;4=12.841,3.251;5=12.844,3.263;6=12.842,3.258;7=12.846,3.259;8=12.845,3.261
   ```
5. **Python parses relay-numbered format**:
   - Clear mapping: relay number → measurements
   - No position-based assumptions

## Example 4: Mixed Panel with Multiple Functions

### SKU Configuration
```json
{
  "sku": "EX-MIXED",
  "description": "4-board panel with mixed functions",
  "relay_mapping": {
    "1": {"board": 1, "function": "mainbeam"},
    "2": {"board": 1, "function": "backlight"},
    "3": {"board": 1, "function": "indicator_left"},
    "4": {"board": 1, "function": "indicator_right"},
    "5": {"board": 2, "function": "mainbeam"},
    "6": {"board": 2, "function": "backlight"},
    "9": {"board": 3, "function": "mainbeam"},
    "10": {"board": 3, "function": "backlight"},
    "13": {"board": 4, "function": "mainbeam"},
    "14": {"board": 4, "function": "backlight"}
  }
}
```

### Testing Workflow
1. **Active relays**: 1,2,3,4,5,6,9,10,13,14
2. **Python optimizes command**: `TX:1-6,9,10,13,14`
3. **Results organized by board and function**:
   ```
   Board 1:
     - mainbeam: 12.847V, 3.260A ✓
     - backlight: 12.845V, 0.450A ✓
     - indicator_left: 12.844V, 0.220A ✓
     - indicator_right: 12.843V, 0.225A ✓
   Board 2:
     - mainbeam: 12.850V, 3.245A ✓
     - backlight: 12.848V, 0.448A ✓
   ...
   ```

## Example 5: Error Handling

### Scenario 1: Empty relay list
```
Command: TX:
Response: ERROR:EMPTY_RELAY_LIST
```

### Scenario 2: Invalid relay number
```
Command: TX:1,2,17,18
Response: ERROR:INVALID_RELAY_LIST
```

### Scenario 3: Malformed command
```
Command: TX:1,2,a,b
Response: ERROR:INVALID_RELAY_LIST
```

## Performance Comparison

| Configuration | Old Method (Test All) | New Method (Selective) | Time Saved |
|--------------|----------------------|------------------------|------------|
| 4 relays active | 0.94s (8 relays) | 0.47s (4 relays) | 50% |
| 6 relays active | 0.94s (8 relays) | 0.70s (6 relays) | 25% |
| 8 relays active | 0.94s (8 relays) | 0.94s (8 relays) | 0% |
| 10 relays active | N/A | 1.17s (10 relays) | N/A |
| 16 relays active | N/A | 1.87s (16 relays) | N/A |

## Best Practices

1. **SKU Design**
   - Group related functions on consecutive relays
   - Use ranges for cleaner commands (1-4 vs 1,2,3,4)
   - Document relay assignments clearly

2. **Command Usage**
   - Use `TX:1-8` for SKUs that previously used T command
   - Use `TX:ALL` when testing all 16 relays
   - Let Python determine optimal relay list from SKU

3. **Migration**
   - Update Arduino firmware first
   - Update Python code to use TX command
   - Update all systems together (no backward compatibility)

4. **Troubleshooting**
   - Check firmware version with `I` command
   - Verify relay mapping in SKU file
   - Monitor serial communication for errors
   - PANELX format clearly shows which relays were tested