# Weight Checking Workflow with Scale Integration

## Overview
The weight checking workflow provides automated weight measurement and validation for LED pods during final quality inspection. It uses a precision digital scale with serial communication to measure pod weights against SKU-specific tolerances. The system supports both manual and automatic testing modes with intelligent part detection and stability verification.

## Data Flow

```
SKU JSON File → Weight Parameters → WeightTest → Scale Controller → Digital Scale
     ↓                                                                   ↓
weight_testing                                                  Serial Data Stream
     ↓                                                                   ↓
Test Limits → Weight Measurement → Stability Check → Pass/Fail Analysis
```

## System Architecture

### 1. **Hardware Components**

- **Digital Scale**: Industrial precision scale with RS-232 serial output
  - Typical models: AND FX-300i, Ohaus Scout, Mettler Toledo
  - Resolution: 0.01g or better
  - Capacity: 300g - 5000g depending on application
  - Communication: 9600 baud, 8N1 serial protocol

- **Serial Interface**: USB-to-RS232 adapter or native COM port
- **Test Fixture**: Optional cradle or positioning guide for consistent placement

### 2. **Communication Protocol**

The scale continuously streams weight data over serial:

**Scale Output Formats (auto-detected):**
```
ST,GS,    123.45,g    # Stable weight format
US,GS,    123.45,g    # Unstable weight format
   123.45 g           # Simple format
```

**Controller Architecture:**
```python
ScaleController (9600 baud)
├── SerialManager (handles low-level serial I/O)
├── Weight Parser (regex-based multi-format parser)
├── Stability Filter (moving average, outlier detection)
└── Callback System (real-time updates to UI)
```

## Detailed Workflow

### 1. **Configuration Loading**

When an operator selects a SKU (e.g., DD5001), the system loads weight specifications:

```json
{
  "sku": "DD5001",
  "weight_testing": {
    "limits": {
      "weight_g": {"min": 210.0, "max": 215.0}
    },
    "tare_g": 0.5
  }
}
```

Or from the unified test parameters:
```json
{
  "WEIGHT": {
    "min_weight_g": 210.0,
    "max_weight_g": 215.0,
    "tare_g": 0.5
  }
}
```

### 2. **Test Initialization**

```python
# WeightHandler creates test instance
test = WeightTest(
    sku="DD5001",
    parameters=sku_params,
    port="COM3",
    weights_json_path="config/weight_specs.json"  # Optional
)

# WeightTest.setup_hardware():
1. Connect to scale on specified port
2. Test communication (verify weight data stream)
3. Configure sensor reading (50ms interval default)
4. Set up callbacks for real-time weight updates
5. Start continuous weight monitoring
```

### 3. **Weight Display and Monitoring**

The system provides real-time weight display with visual feedback:

```
┌─────────────────────────────────┐
│        Scale Display            │
│      [ 212.45 g ]               │
│   MIN: 210.0g  MAX: 215.0g      │
└─────────────────────────────────┘
```

**Display States:**
- **Green Border**: Live reading, scale connected
- **Orange Border**: Waiting for stable reading
- **Gray Border**: Scale disconnected

### 4. **Auto-Test Trigger System**

The auto-test feature monitors weight continuously and triggers tests automatically:

```python
# Auto-test logic:
1. Monitor current weight
2. If weight >= (80% of min_weight):
   - Start stability timer
   - Track weight readings for 2 seconds
3. If weight remains stable (±0.1g):
   - Trigger automatic test
4. After test completion:
   - Wait for part removal (weight < 50% of min)
   - Reset for next part
```

**Stability Detection:**
- Collects last 10 weight readings
- Checks if all readings within ±0.1g tolerance
- Requires 2 seconds of stable readings
- Filters outliers using median-based algorithm

### 5. **Test Execution Phases**

#### Phase 1: Part Detection
```python
# Wait for part placement (up to 30 seconds)
while not part_detected:
    current_weight = scale.current_weight
    if current_weight > 1.0g:  # Minimum threshold
        if weight_stable_for(2.0 seconds):
            part_detected = True
```

#### Phase 2: Weight Measurement
```python
# Get stable weight reading
stable_weight = scale.get_stable_weight(
    num_readings=5,      # Average 5 readings
    tolerance=0.05,      # ±0.05g stability
    timeout=10.0        # 10 second timeout
)

# Apply tare offset
final_weight = stable_weight - tare_offset
```

#### Phase 3: Results Analysis
```python
# Check against limits
if min_weight <= final_weight <= max_weight:
    result = "PASS"
else:
    result = "FAIL"
    
# Record measurement
result.add_measurement(
    name="weight",
    value=final_weight,
    min_val=min_weight,
    max_val=max_weight,
    unit="g"
)
```

### 6. **Scale Controller Features**

**Performance Optimizations:**
- Non-blocking serial reads (50ms timeout)
- Weight caching to avoid re-parsing identical strings
- Regex pattern pre-compilation for faster parsing
- Queue-based reading storage (max 100 readings)
- Dynamic buffer management to prevent data buildup

**Stability Filtering:**
```python
# Moving average filter
if len(weight_history) >= 3:
    weights = [0.1, 0.2, 0.3, 0.4]  # Recent readings weighted more
    filtered_weight = weighted_average(weight_history, weights)
```

**Outlier Detection:**
```python
# Detect and filter measurement spikes
if abs(current - median) > max(100g, median * 0.5):
    # Likely outlier, use conservative approach
    filtered = (median * 0.7) + (current * 0.3)
```

### 7. **Manual Controls**

**Zero/Tare Function:**
- Captures current weight as zero reference
- Applied to all subsequent readings
- Useful for fixture compensation

**Manual Test Trigger:**
- Bypasses auto-detection
- Immediate weight measurement
- Same analysis as auto-triggered tests

### 8. **Display Results**

The WeightTestWidget displays comprehensive results:

```
┌──────────────────────────────────────┐
│     DD5001 - Weight Check            │
├──────────────────────────────────────┤
│ Status: Ready for auto-test          │
│ Threshold: 168.0g (80% of 210.0g)    │
│                                      │
│        [ TEST PASS ]                 │
│                                      │
│ Results:                             │
│ ────────────────────────────────────│
│ Auto-triggered test for SKU: DD5001  │
│ Measuring weight...                  │
│                                      │
│ TEST PASS - DD5001                   │
│ Duration: 2.5 seconds                │
│                                      │
│ Measurements:                        │
│   weight: 212.35g [210.0-215.0]g    │
│                                      │
│ Remove part for next test.           │
└──────────────────────────────────────┘
```

## Key Workflow Features

### 1. **Intelligent Auto-Testing**
- Automatic part detection based on weight threshold
- Stability verification before measurement
- Automatic reset after part removal
- No operator intervention required for continuous testing

### 2. **Advanced Filtering**
- Real-time noise reduction using weighted moving average
- Outlier detection and correction
- Configurable filtering (can be disabled for troubleshooting)
- Maintains last 10 readings for stability analysis

### 3. **Flexible Configuration**
- Weight limits defined per SKU in JSON
- Optional weight specification file for batch testing
- Configurable tare offsets
- Support for different scale models and protocols

### 4. **Performance Optimization**
- 50ms scale polling for responsive display
- 100ms UI updates to balance responsiveness and CPU usage
- Non-blocking serial communication
- Efficient regex parsing with caching

### 5. **Error Handling**
- Automatic reconnection attempts
- Clear error messages for troubleshooting
- Timeout protection on all operations
- Graceful handling of scale disconnection

## Example Test Run

1. **Operator Actions:**
   - Selects SKU: DD5001
   - Connects to scale on COM3
   - Places pod on scale

2. **System Flow:**
   ```
   Load DD5001 weight parameters (210-215g)
   ↓
   Connect to scale and verify communication
   ↓
   Display live weight readings
   ↓
   Detect part placement (weight > 168g)
   ↓
   Verify weight stability (2 seconds)
   ↓
   Capture stable weight (5 readings avg)
   ↓
   Apply tare offset if configured
   ↓
   Compare to limits (210-215g)
   ↓
   Display PASS/FAIL result
   ↓
   Wait for part removal
   ↓
   Reset for next test
   ```

3. **Results:**
   - Weight measured: 212.35g
   - Limits: 210.0-215.0g
   - Tare applied: 0.5g
   - Result: PASS
   - Ready for next part

## Advanced Features

### 1. **Weight Specification File**
Optional JSON file for managing multiple part numbers:
```json
{
  "DD5001": {"min": 210.0, "max": 215.0},
  "DD5002": {"min": 180.0, "max": 185.0},
  "DD5003": {"min": 195.0, "max": 200.0}
}
```

### 2. **Statistics Tracking**
The system maintains weight statistics:
- Minimum weight seen
- Maximum weight seen
- Average of recent readings
- Total reading count

### 3. **Resource Management**
- Automatic cleanup of threads and timers
- Proper serial port management
- Memory-efficient reading storage
- Thread-safe weight access

### 4. **Scale Compatibility**
Supports multiple scale protocols:
- AND FX/FZ series format
- Ohaus Scout format
- Generic weight string parsing
- Configurable baud rates

## Benefits of Current Workflow

1. **Efficiency**: Auto-testing eliminates manual triggering
2. **Accuracy**: Multiple stability checks ensure reliable measurements
3. **Flexibility**: JSON configuration for easy limit updates
4. **Reliability**: Robust error handling and filtering
5. **Traceability**: All measurements logged with timestamps
6. **User-Friendly**: Clear visual feedback and status messages

## Troubleshooting Features

1. **Weight Filtering Toggle**: Can disable filtering to see raw data
2. **Connection Status**: Real-time scale connection monitoring
3. **Debug Logging**: Detailed logs for issue diagnosis
4. **Manual Controls**: Override auto-test for special cases
5. **Clear Error Messages**: Specific guidance for common issues

This workflow provides efficient, accurate weight verification while maintaining the simplicity needed for production environments. The auto-test feature significantly reduces operator workload while ensuring consistent quality checks.