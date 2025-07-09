# TESTSEQ Protocol Integration Tests

This directory contains integration tests for the TESTSEQ protocol implementation as specified in section 5.2 of the SMT simultaneous relay activation todo list.

## Test Coverage

### 5.2.1 Full Sequence Execution Tests (`test_full_sequence_execution`)
- Executes complete test sequences with multiple relay groups
- Verifies all boards and functions are tested
- Validates measurement data structure and types
- Checks execution time against expected duration

### 5.2.2 Timing Precision Validation (`test_timing_precision_validation`)
- Runs multiple iterations to measure timing consistency
- Calculates average timing and standard deviation
- Verifies timing accuracy within 10% of expected
- Checks timing consistency (CV < 5%)

### 5.2.3 Current Limit Enforcement (`test_current_limit_enforcement`)
- Validates measurements against specified limits
- Tests detection of overcurrent conditions
- Verifies both current and voltage limit checking
- Uses mock data for predictable testing

### 5.2.4 Error Recovery Scenarios (`test_error_recovery_scenarios`)
- Tests invalid relay number detection (>16)
- Validates relay overlap detection between groups
- Checks timing constraint violations (min 100ms duration)
- Tests sequence timeout detection (30s limit)
- Verifies recovery from communication errors

### 5.2.5 Performance Benchmarks (`test_performance_benchmarks`)
- Benchmarks simple, complex, and maximum relay configurations
- Measures communication overhead
- Verifies overhead < 100ms per step
- Saves results to `testseq_benchmarks.json`

## Running the Tests

### Quick Start (No Hardware)
Run unit tests with mocked Arduino:
```bash
python run_integration_tests.py
```

### With Arduino Hardware
Connect Arduino with firmware v2.0.0+ and run:
```bash
python run_integration_tests.py --port COM7 --hardware
```

### Run Specific Test
```bash
python run_integration_tests.py --test test_timing_precision_validation
```

### Verbose Output
```bash
python run_integration_tests.py --verbose
```

### Command Line Options
- `--port PORT`: Arduino serial port (default: COM7)
- `--hardware`: Require Arduino hardware (tests skip if not available)
- `--verbose, -v`: Enable verbose output with debug logging
- `--test TEST`: Run specific test method

## Requirements

### Software
- Python 3.7+
- pyserial
- Arduino firmware v2.0.0+ with TESTSEQ protocol support

### Hardware (Optional)
- Arduino UNO R4 WiFi or Minima
- PCF8575 I2C expander at address 0x20
- INA260 current sensor
- Test relays connected to PCF8575 pins

## Test Output

Tests produce:
1. Console output with pass/fail status
2. `testseq_benchmarks.json` with performance metrics
3. Debug logs (when --verbose is used)

## CI/CD Integration

The tests are designed to work in CI/CD environments without hardware:
- Mocked tests run automatically
- Hardware tests are skipped unless --hardware flag is set
- Exit code 0 for success, 1 for failure

## Troubleshooting

### Common Issues

1. **"Arduino hardware not available"**
   - Check Arduino is connected to correct port
   - Verify firmware version supports TESTSEQ protocol
   - Try running `python -m serial.tools.list_ports` to find port

2. **"Port already in use"**
   - Close other applications using the serial port
   - Check if main application is running

3. **Timing test failures**
   - Ensure Arduino has stable power supply
   - Check for interference on I2C bus
   - Verify PCF8575 connection

4. **Current limit failures**
   - These are expected with mock data
   - With real hardware, check relay loads

## Example Output

```
test_full_sequence_execution (__main__.TestTESTSEQIntegration) ... ok
test_timing_precision_validation (__main__.TestTESTSEQIntegration) ... ok
test_current_limit_enforcement (__main__.TestTESTSEQIntegration) ... ok
test_error_recovery_scenarios (__main__.TestTESTSEQIntegration) ... ok
test_performance_benchmarks (__main__.TestTESTSEQIntegration) ... ok

======================================================================
TESTSEQ Integration Test Summary
======================================================================
Tests run: 5
Failures: 0
Errors: 0
Skipped: 0

✅ All tests passed!
```