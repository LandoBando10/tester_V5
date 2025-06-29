# SMT Testing Workflow with New Relay Mapping

## Overview
The updated SMT testing workflow uses direct relay mapping from SKU JSON files, eliminating complex calculations and providing a clear, traceable path from configuration to hardware control.

## Data Flow

```
SKU JSON File → SMT Parameters → SMT Controller → Arduino → Physical Relays
     ↓                                                           ↓
relay_mapping                                            Measurements
     ↓                                                           ↓
Board/Function → Relay Number → Hardware Command → Current/Voltage Data
```

## Detailed Workflow

### 1. **Configuration Loading**

When an operator selects a SKU (e.g., DD5000), the system loads the SKU's JSON file:

```json
{
  "sku": "DD5000",
  "smt_testing": {
    "panel_layout": {
      "rows": 2,
      "columns": 2,
      "total_boards": 4
    },
    "relay_mapping": {
      "1": {"board": 1, "function": "mainbeam"},
      "2": {"board": 2, "function": "mainbeam"},
      "3": {"board": 3, "function": "mainbeam"},
      "4": {"board": 4, "function": "mainbeam"},
      "5": {"board": 1, "function": "backlight"},
      "6": {"board": 2, "function": "backlight"},
      "7": {"board": 3, "function": "backlight"},
      "8": {"board": 4, "function": "backlight"}
    },
    "test_sequence": [
      {
        "name": "mainbeam_test",
        "function": "mainbeam",
        "limits": {
          "current_A": {"min": 0.85, "max": 1.15}
        }
      }
    ]
  }
}
```

### 2. **Test Initialization**

```python
# SMTHandler creates test instance
test = SMTTest(sku="DD5000", parameters=sku_params, port="COM3")

# SMTTest.setup_hardware():
1. Connect to Arduino on specified port
2. Verify SMT firmware is running (checks for "SMT_TESTER" response)
3. Extract smt_testing configuration from parameters
4. Pass configuration to SMTController
5. Controller stores relay_mapping for quick lookups
```

### 3. **Test Execution Flow**

#### Phase 1: Programming (Optional)
If programming is enabled:
1. Use bed-of-nails fixture to connect to each board
2. Program microcontrollers using external programmers
3. Record success/failure for each board

#### Phase 2: Power Testing

**Mainbeam Test:**
```python
# Get all relays with mainbeam function
mainbeam_relays = controller.get_relays_for_function("mainbeam")
# Returns: [1, 2, 3, 4]

# Send to Arduino
arduino.send_command("MEASURE_GROUP:1,2,3,4")

# Arduino sequence:
1. Turn all relays OFF
2. For each relay in group:
   - Turn relay ON
   - Wait for stabilization
   - Take 5 current/voltage samples over 100ms
   - Turn relay OFF
3. Return measurements for each relay

# Map results back to boards
Relay 1 → Board 1 (from relay_mapping)
Relay 2 → Board 2
Relay 3 → Board 3
Relay 4 → Board 4
```

**Backlight Test:**
```python
# Get all relays with backlight function
backlight_relays = [5, 6, 7, 8]  # Filtered from relay_mapping

# Same measurement process
arduino.send_command("MEASURE_GROUP:5,6,7,8")

# Map results
Relay 5 → Board 1 (backlight)
Relay 6 → Board 2 (backlight)
Relay 7 → Board 3 (backlight)
Relay 8 → Board 4 (backlight)
```

### 4. **Results Processing**

```python
# For each measurement:
board_results = {
    "Board 1": {"relay": 1, "current": 0.95, "voltage": 12.1},
    "Board 2": {"relay": 2, "current": 0.93, "voltage": 12.0},
    "Board 3": {"relay": 3, "current": 0.97, "voltage": 12.1},
    "Board 4": {"relay": 4, "current": 0.91, "voltage": 12.0}
}

# Analyze against limits from test_sequence
for board, data in board_results.items():
    if data["current"] < 0.85 or data["current"] > 1.15:
        result.failures.append(f"{board} current out of limits")
```

### 5. **Display Results**

The SMTWidget displays results in a grid matching the physical panel:

```
[Board 4: PASS]  [Board 3: PASS]
[Board 1: FAIL]  [Board 2: PASS]
```

Each cell shows:
- Board number
- Function measurements (mainbeam, backlight)
- Pass/Fail status with color coding

## Key Workflow Improvements

### 1. **Direct Mapping**
- No calculations needed: relay 1 = board 1 mainbeam (directly from JSON)
- Easy to trace: which relay controls which board/function
- Simple debugging: check JSON to understand hardware mapping

### 2. **Function-Based Testing**
- Test by function ("test all mainbeams") not by relay numbers
- Supports different board configurations easily
- Clear intent in test sequences

### 3. **Flexible Panel Support**
Examples of different configurations:

**2x2 Panel (DD5000):**
```
Board 4  Board 3
Board 1  Board 2
```

**1x2 Panel (DD5001):**
```
Board 1  Board 2
```

**4x1 Panel (Future SKU):**
```
Board 1  Board 2  Board 3  Board 4
```

### 4. **Clear Error Handling**
- Missing relay_mapping → Test fails immediately with clear error
- Invalid relay numbers → Logged and skipped
- Failed measurements → Attributed to specific board/function

## Example Test Run

1. **Operator Actions:**
   - Selects SKU: DD5000
   - Enables: Power Testing + Programming
   - Clicks: Start Test

2. **System Flow:**
   ```
   Load DD5000.json
   ↓
   Extract relay_mapping and test_sequence
   ↓
   Initialize Arduino connection
   ↓
   Program boards 1-4 (if enabled)
   ↓
   Test mainbeam function (relays 1-4)
   ↓
   Test backlight function (relays 5-8)
   ↓
   Analyze measurements against limits
   ↓
   Display results in panel grid
   ```

3. **Results:**
   - Programming: 4/4 boards successful
   - Mainbeam: All boards within 0.85-1.15A limits
   - Backlight: All boards within 0.10-0.50A limits
   - Overall: PASS

## Benefits of New Workflow

1. **Transparency**: Every step is traceable through the relay mapping
2. **Maintainability**: Adding new board layouts only requires JSON changes
3. **Debugging**: Clear path from board → function → relay → measurement
4. **Flexibility**: Supports any panel configuration without code changes
5. **Simplicity**: No complex calculations or offset logic

This workflow makes SMT testing more reliable and easier to understand for both operators and engineers.