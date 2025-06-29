# Offroad Testing Workflow with Arduino Integration

## Overview
The offroad testing workflow is designed for testing individual LED pods after final assembly. It uses Arduino-based hardware to control relays, measure electrical parameters, and interface with advanced sensors for optical measurements. The system supports various pod types (SS3, C2, etc.) with different testing requirements including pressure decay, mainbeam/backlight testing, and RGBW color cycling.

## Data Flow

```
SKU JSON File → Test Parameters → OffroadTest → Arduino Controller → Physical Hardware
     ↓                                                                    ↓
test_sequence                                                    Sensor Measurements
     ↓                                                                    ↓
Test Phase → Arduino Command → Hardware Control → Result Data → Analysis
```

## System Architecture

### 1. **Hardware Components**

- **Arduino Mega 2560**: Main controller running specialized firmware
- **Relay Board**: 8-channel relay module for switching pod functions
- **Current/Voltage Sensors**: ACS712 current sensors, voltage dividers
- **Optical Sensors**: 
  - AS7341 Color Sensor (I2C): Measures CIE xy color coordinates
  - TSL2591 Light Sensor (I2C): Measures lux levels
- **Pressure Sensor**: 0-30 PSI transducer for housing integrity tests
- **Pneumatic System**: Solenoid valves for pressure control

### 2. **Communication Protocol**

Arduino communicates via serial (115200 baud) using structured messages:

**Commands (PC → Arduino):**
```
SENSOR_CHECK                    # Verify sensor connectivity
TEST:PRESSURE                   # Run 5-second pressure decay test
TEST:FUNCTION_TEST              # Test mainbeam + backlight sequentially
TEST:DUAL_BACKLIGHT            # Test dual backlight configuration
TEST:RGBW_BACKLIGHT            # Run 8-cycle RGBW color test
STOP                           # Stop all tests and turn off relays
```

**Responses (Arduino → PC):**
```
READY                          # Arduino initialized and ready
SENSOR:AS7341=OK,TSL2591=OK    # Sensor status report
RESULT:INITIAL=14.5,DELTA=0.2  # Pressure test results
RESULT:MV_MAIN=12.5,MI_MAIN=1.2,LUX_MAIN=2500,X_MAIN=0.445,Y_MAIN=0.408,...
RGBW_SAMPLE:CYCLE=1,VOLTAGE=12.5,CURRENT=0.085,X=0.650,Y=0.330,LUX=125
```

## Detailed Workflow

### 1. **Configuration Loading**

When an operator selects a SKU (e.g., DD5002), the system loads the SKU's JSON configuration:

```json
{
  "sku": "DD5002",
  "offroad_testing": {
    "test_sequence": [
      {
        "name": "mainbeam",
        "relay": "main",
        "duration_ms": 500,
        "measurements": ["current", "voltage", "lux", "color"],
        "limits": {
          "current_A": {"min": 0.6, "max": 0.9},
          "lux": {"min": 1500, "max": 1900},
          "color_x": {"center": 0.460, "tolerance": 0.020},
          "color_y": {"center": 0.420, "tolerance": 0.020}
        }
      },
      {
        "name": "backlight_rgbw",
        "relay": "backlight_1",
        "duration_ms": 6400,
        "type": "rgbw_cycling",
        "rgbw_config": {
          "cycle_interval_ms": 800,
          "total_cycles": 8,
          "colors_to_test": [
            {"name": "red", "target_x": 0.650, "target_y": 0.330},
            {"name": "green", "target_x": 0.300, "target_y": 0.600},
            {"name": "blue", "target_x": 0.150, "target_y": 0.060},
            {"name": "white", "target_x": 0.313, "target_y": 0.329}
          ]
        }
      }
    ]
  }
}
```

### 2. **Test Initialization**

```python
# OffroadHandler creates test instance
test = OffroadTest(
    sku="DD5002",
    parameters=sku_params,
    port="COM3",
    test_config="offroad_standard",
    pressure_test_enabled=True
)

# OffroadTest.setup_hardware():
1. Connect to Arduino on specified port
2. Send SENSOR_CHECK command
3. Verify AS7341 and TSL2591 sensors respond
4. Set up callbacks for result parsing
5. Start continuous sensor monitoring
```

### 3. **Test Execution Phases**

#### Phase 1: Pressure Decay Test (Optional, 5 seconds)
If the operator enables pressure testing:

```python
# Send pressure test command
arduino.send_command("TEST:PRESSURE")

# Arduino sequence:
1. Close exhaust valve
2. Open fill valve for 1500ms (pressurize to ~15 PSI)
3. Close fill valve, wait 500ms for stabilization
4. Record initial pressure
5. Monitor pressure for 2500ms
6. Calculate pressure drop
7. Open exhaust valve
8. Send RESULT:INITIAL=14.5,DELTA=0.2

# Pass/Fail criteria:
- Initial pressure: 14.0-16.0 PSI
- Pressure drop: < 0.5 PSI over 2.5 seconds
```

#### Phase 2: Function Test (Mainbeam + Backlight)

```python
# Send function test command
arduino.send_command("TEST:FUNCTION_TEST")

# Arduino sequence:
1. Activate mainbeam relay (relay 2)
2. Wait 150ms for stabilization
3. Take 5 measurements over 350ms:
   - Voltage (12V rail)
   - Current (via ACS712)
   - Lux (via TSL2591)
   - Color X,Y (via AS7341)
4. Turn off mainbeam
5. Activate backlight relay (relay 3)
6. Repeat measurement sequence
7. Turn off backlight
8. Send combined results:
   RESULT:MV_MAIN=12.5,MI_MAIN=0.75,LUX_MAIN=1750,X_MAIN=0.458,Y_MAIN=0.418,
          MV_BACK=12.4,MI_BACK=0.09,LUX_BACK=145,X_BACK=0.575,Y_BACK=0.392
```

#### Phase 3: Backlight Variants

**Dual Backlight (DD5001 style):**
```python
arduino.send_command("TEST:DUAL_BACKLIGHT")

# Tests two separate backlight circuits:
1. Activate backlight_1 (relay 3), measure current
2. Activate backlight_2 (relay 4), measure current
3. Send RESULT:MV_BACK1=12.5,MI_BACK1=0.10,MV_BACK2=12.4,MI_BACK2=0.11
```

**RGBW Cycling (DD5002 style):**
```python
arduino.send_command("TEST:RGBW_BACKLIGHT")

# 8-cycle color test sequence:
For each cycle (1-8):
  1. Activate RGBW backlight relay
  2. Wait 150ms for color transition
  3. Take measurements at 200ms, 350ms, 450ms
  4. Average the readings
  5. Send RGBW_SAMPLE message
  6. Wait remainder of 800ms cycle
  7. Turn off relay briefly (50ms)

# Sample output for each cycle:
RGBW_SAMPLE:CYCLE=1,VOLTAGE=12.5,CURRENT=0.085,X=0.650,Y=0.330,LUX=125
RGBW_SAMPLE:CYCLE=2,VOLTAGE=12.5,CURRENT=0.082,X=0.300,Y=0.600,LUX=130
...
```

### 4. **Results Processing**

```python
# OffroadTest._analyze_arduino_results():

# Process pressure test results
if pressure_test_data:
    initial_psi = pressure_test_data["INITIAL"]  # 14.5
    delta_psi = pressure_test_data["DELTA"]      # 0.2
    
    # Check against limits
    if not (14.0 <= initial_psi <= 16.0):
        result.failures.append("Initial pressure out of range")
    if delta_psi > 0.5:
        result.failures.append("Excessive pressure loss")

# Process function test results
if function_test_data:
    # Mainbeam analysis
    mainbeam_current = function_test_data["MI_MAIN"]  # 0.75A
    mainbeam_lux = function_test_data["LUX_MAIN"]     # 1750
    mainbeam_x = function_test_data["X_MAIN"]         # 0.458
    mainbeam_y = function_test_data["Y_MAIN"]         # 0.418
    
    # Check all parameters against SKU limits
    if not (0.6 <= mainbeam_current <= 0.9):
        result.failures.append("Mainbeam current out of limits")
    if not (1500 <= mainbeam_lux <= 1900):
        result.failures.append("Mainbeam brightness out of limits")
    
    # Color coordinate check (elliptical tolerance)
    center_x, center_y = 0.460, 0.420
    tolerance = 0.020
    distance = sqrt((mainbeam_x - center_x)² + (mainbeam_y - center_y)²)
    if distance > tolerance:
        result.failures.append("Mainbeam color out of tolerance")

# Process RGBW samples
if rgbw_samples:
    # Verify color variation across cycles
    x_values = [s.x for s in rgbw_samples]
    y_values = [s.y for s in rgbw_samples]
    
    x_range = max(x_values) - min(x_values)  # Should be > 0.1
    y_range = max(y_values) - min(y_values)  # Should be > 0.1
    
    # Check for each expected color
    for expected_color in ["red", "green", "blue", "white"]:
        if not any(color_matches(sample, expected_color) for sample in rgbw_samples):
            result.failures.append(f"RGBW: {expected_color} not detected")
```

### 5. **Display Results**

The OffroadWidget displays real-time test progress and final results:

```
┌─────────────────────────────────────┐
│     DD5002 - Offroad Test           │
├─────────────────────────────────────┤
│ [✓] Pressure Test                   │
│     Initial: 14.5 PSI (PASS)        │
│     Delta: 0.2 PSI (PASS)           │
│                                     │
│ [✓] Mainbeam Test                   │
│     Current: 0.75A (PASS)           │
│     Brightness: 1750 lux (PASS)     │
│     Color: (0.458, 0.418) (PASS)    │
│                                     │
│ [✓] RGBW Backlight Test             │
│     Colors Detected: 4/4            │
│     ● Red   ● Green                │
│     ● Blue  ● White                │
│                                     │
│ Overall Result: PASS                │
└─────────────────────────────────────┘
```

## Key Workflow Features

### 1. **Flexible Test Configuration**
- Test sequences defined in JSON for easy modification
- Support for different pod types (SS3, C2) with varying power levels
- Configurable measurement limits per SKU

### 2. **Advanced Sensor Integration**
- AS7341 provides 11-channel spectral data converted to CIE xy coordinates
- TSL2591 offers high dynamic range lux measurements (0.1 - 88,000 lux)
- Real-time pressure monitoring with 0.1 PSI resolution

### 3. **Intelligent Result Parsing**
- Arduino sends structured RESULT messages with key-value pairs
- Python parses results into typed data structures
- Automatic limit checking against SKU specifications

### 4. **RGBW Color Validation**
- Automated 8-cycle test captures full color gamut
- Each cycle measured at multiple points for stability
- Color matching algorithm verifies all expected colors present

### 5. **Error Handling**
- Sensor connectivity verified before each test
- Timeout protection on all Arduino commands
- Clear error messages for troubleshooting

## Example Test Run

1. **Operator Actions:**
   - Places DD5002 pod in test fixture
   - Selects SKU: DD5002
   - Enables: Pressure Test
   - Clicks: Start Test

2. **System Flow:**
   ```
   Load DD5002.json configuration
   ↓
   Initialize Arduino and verify sensors
   ↓
   Run pressure decay test (5 seconds)
   ↓
   Run mainbeam test (measure I, V, lux, color)
   ↓
   Run RGBW cycling test (8 cycles, 6.4 seconds)
   ↓
   Parse all RESULT and RGBW_SAMPLE messages
   ↓
   Compare measurements to SKU limits
   ↓
   Display pass/fail results with details
   ```

3. **Results:**
   - Pressure: Initial 14.5 PSI, Delta 0.2 PSI (PASS)
   - Mainbeam: 0.75A, 1750 lux, color (0.458, 0.418) (PASS)
   - RGBW: All 4 colors detected with proper cycling (PASS)
   - Overall: PASS

## Benefits of Current Workflow

1. **Accuracy**: Direct sensor measurements eliminate subjective assessments
2. **Speed**: Entire test sequence completes in under 15 seconds
3. **Flexibility**: JSON configuration allows easy adaptation to new products
4. **Traceability**: All measurements logged with timestamps
5. **Reliability**: Structured communication protocol prevents data corruption
6. **Integration**: Results can be exported to MES/ERP systems

## Sensor Timing Configurations

The system supports two timing modes:

**Standard Mode (default):**
- Sensor read interval: 50ms
- Suitable for production testing
- Lower CPU usage

**Precision Mode:**
- Sensor read interval: 10ms
- Higher measurement density
- Used for engineering validation

This workflow provides comprehensive testing of LED pods while maintaining efficiency and accuracy required for production environments.