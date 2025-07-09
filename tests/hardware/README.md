# Hardware Validation Tests

This directory contains hardware validation tests for the TESTSEQ protocol implementation as specified in section 5.3 of the SMT simultaneous relay activation todo list.

## ⚠️ Safety Warning

**These tests will activate relays and draw significant current!**

Before running:
- Ensure adequate power supply (rated for maximum expected current)
- Provide proper ventilation for thermal tests
- Use appropriate safety equipment (safety glasses, insulated tools)
- Monitor for excessive heat or unusual behavior
- Have emergency stop capability ready

## Test Coverage

### 5.3.1 Relay Switching Speed Measurement (`test_relay_switching_speed_measurement`)
- Measures relay activation overhead for different configurations
- Tests single, dual, quad, and 8-relay simultaneous switching
- Calculates average switching time and standard deviation
- Verifies switching overhead < 50ms
- Output: `relay_switching_speed.json`

### 5.3.2 Current Measurement Accuracy (`test_current_measurement_accuracy`)
- Takes multiple measurements to assess consistency
- Calculates coefficient of variation (CV) for voltage and current
- Tests different relay configurations and load conditions
- Verifies voltage CV < 5% and current CV < 10%
- Output: `measurement_accuracy.json`

### 5.3.3 Timing Jitter Analysis (`test_timing_jitter_analysis`)
- Runs 50 iterations of a precise timing sequence
- Measures timing variations and calculates jitter statistics
- Provides percentile analysis (50th, 90th, 95th, 99th)
- Verifies peak-to-peak jitter < 10ms
- Output: `timing_jitter_analysis.json`

### 5.3.4 Thermal Behavior Validation (`test_thermal_behavior_validation`)
- **Duration: 5 minutes** (can be skipped with --skip-thermal)
- Monitors measurements during extended operation
- Calculates thermal drift over time
- Verifies drift < 10% from initial values
- Includes safety shutdown for overcurrent
- Output: `thermal_behavior.json`

### 5.3.5 EMI/Noise Testing (`test_emi_noise_testing`)
- Measures baseline noise with no relays active
- Tests noise during relay switching operations
- Checks for crosstalk between adjacent channels
- Verifies crosstalk current < 100mA
- Output: `emi_noise_test.json`

## Hardware Requirements

### Essential
- Arduino UNO R4 (WiFi or Minima) with firmware v2.0.0+
- PCF8575 I2C expander at address 0x20
- INA260 current/voltage sensor
- Adequate power supply (12V, >10A recommended)
- Test loads on relay outputs

### Optional (for enhanced testing)
- Oscilloscope for switching waveform capture
- Reference multimeter for accuracy validation
- Thermal camera or thermocouples
- EMI test equipment (spectrum analyzer)

## Running the Tests

### Full Test Suite
```bash
python run_hardware_tests.py --port COM7
```

### Skip Thermal Test (saves 5 minutes)
```bash
python run_hardware_tests.py --port COM7 --skip-thermal
```

### Run Specific Test
```bash
python run_hardware_tests.py --port COM7 --test test_relay_switching_speed_measurement
```

### With Custom Output Directory
```bash
python run_hardware_tests.py --port COM7 --output-dir ./test_results
```

### Verbose Mode
```bash
python run_hardware_tests.py --port COM7 --verbose
```

## Output Files

All tests generate JSON files with detailed results:

1. **relay_switching_speed.json**
   - Switching times for different relay configurations
   - Statistical analysis (mean, std dev, min, max)

2. **measurement_accuracy.json**
   - Measurement consistency statistics
   - Coefficient of variation for voltage and current

3. **timing_jitter_analysis.json**
   - Detailed timing samples and statistics
   - Percentile analysis for jitter characterization

4. **thermal_behavior.json**
   - Time-series data over 5-minute test
   - Thermal drift analysis by channel

5. **emi_noise_test.json**
   - Baseline noise measurements
   - Switching noise characteristics
   - Crosstalk measurements

## Data Analysis

### Python Analysis Example
```python
import json
import matplotlib.pyplot as plt

# Load timing jitter data
with open('timing_jitter_analysis.json', 'r') as f:
    data = json.load(f)

# Plot timing distribution
errors = [s['error_ms'] for s in data['samples']]
plt.hist(errors, bins=20)
plt.xlabel('Timing Error (ms)')
plt.ylabel('Count')
plt.title('Timing Jitter Distribution')
plt.show()
```

### Key Metrics to Monitor
- **Switching speed**: Should be consistent across configurations
- **Measurement accuracy**: CV should remain low (<5%)
- **Timing jitter**: 95th percentile should be < 5ms
- **Thermal drift**: Should stabilize after warm-up
- **Crosstalk**: Should be minimal (<100mA)

## Troubleshooting

### "Arduino hardware not available"
- Check USB connection and port number
- Verify Arduino has TESTSEQ firmware v2.0.0+
- Try `python -m serial.tools.list_ports`

### High timing jitter
- Check for other USB devices causing interference
- Ensure stable power supply
- Verify I2C pull-up resistors are installed

### Thermal test failures
- Improve ventilation around test setup
- Reduce ambient temperature
- Check for proper heat sinking on high-power components

### EMI/crosstalk issues
- Verify proper grounding
- Check for loose connections
- Use shielded cables for sensitive signals
- Separate power and signal wiring

## Integration with CI/CD

For automated testing without hardware:
```python
# Run only the mocked tests
python -m pytest tests/hardware/test_hardware_validation.py::TestHardwareValidationMocked
```

## Interpreting Results

### Good Results Example
```json
{
  "relay_switching_speed": {
    "single_relay": {"avg_switching_ms": 5.2, "std_dev_ms": 0.8},
    "eight_relays": {"avg_switching_ms": 7.5, "std_dev_ms": 1.2}
  },
  "measurement_accuracy": {
    "voltage_cv_percent": 0.5,
    "current_cv_percent": 2.3
  },
  "timing_jitter": {
    "peak_to_peak_ms": 4.5,
    "p95": 2.1
  }
}
```

### Concerning Results
- Switching time > 50ms
- Measurement CV > 10%
- Timing jitter p95 > 5ms
- Thermal drift > 10%
- Crosstalk current > 100mA

## Next Steps

After running hardware tests:
1. Review all output JSON files
2. Compare results against specifications
3. Identify any failing metrics
4. Document hardware configuration used
5. Save results for regression testing
6. Consider running tests at temperature extremes