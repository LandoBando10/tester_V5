# SMT Panel Test - Single Command Implementation

## Overview

This update introduces a significant performance improvement to the SMT panel testing system by replacing 8 individual relay measurement commands with a single panel test command.

## Performance Improvement

### Old Approach (8 Commands)
```
Python → Arduino: "R1"
Arduino → Python: "R1:12847.500,3260.833"
Python → Arduino: "R2"
Arduino → Python: "R2:12850.000,3248.125"
... (6 more times)
```
**Total time: ~3-4 seconds**

### New Approach (1 Command)
```
Python → Arduino: "T"
Arduino → Python: "PANEL:12.847,3.260;12.850,3.248;12.857,3.211;..."
```
**Total time: ~1 second**

**Result: 3-4x faster testing!**

## Key Changes

### 1. Arduino Firmware (SMT_Simple_Tester.ino)
- Added `T` command for full panel test
- Added `TS` command for streaming test with progress updates
- Fixed unit conversion - now sends values in V and A (not mV/mA)
- Version updated to 1.1.0

### 2. Python Controller (smt_arduino_controller.py)
- Added `test_panel()` method for single-command testing
- Added `test_panel_stream()` method for progress feedback
- Fixed unit conversion bug (was treating mV as V)
- Maintains backward compatibility with individual relay commands

### 3. Test Logic (smt_test.py)
- Automatically uses fast panel test when measuring all 8 relays
- Falls back to individual measurements for partial tests
- No changes needed to existing test configurations

## Usage

### Basic Panel Test
```python
# Old way (still works)
results = arduino.measure_relays([1, 2, 3, 4, 5, 6, 7, 8])

# New way (3-4x faster)
results = arduino.test_panel()
```

### Panel Test with Progress Updates
```python
def progress_callback(relay_num, measurement):
    print(f"Relay {relay_num}: {measurement['voltage']:.3f}V")

results = arduino.test_panel_stream(progress_callback)
```

## Benefits

1. **Speed**: 3-4x faster panel testing
2. **Reliability**: Fewer commands = fewer opportunities for communication errors
3. **Simplicity**: Cleaner code with less state management
4. **Atomic Operations**: Either the whole panel test succeeds or fails
5. **Better Production Throughput**: Save 2-3 seconds per panel tested

## Migration

No code changes required! The system automatically uses the fast method when appropriate:
- Testing all 8 relays → Uses fast panel test
- Testing subset of relays → Uses individual measurements

## Testing

Run the performance comparison script:
```bash
python test_panel_performance.py
```

This will show the performance difference between old and new approaches.

## Important Notes

1. **Arduino Firmware Update Required**: You must upload the new Arduino firmware (v1.1.0) to use the new commands
2. **Unit Conversion Fixed**: The old bug where mV was treated as V has been fixed
3. **Backward Compatible**: Existing code continues to work without modification

## Troubleshooting

### "Panel test failed - no measurements received"
- Update Arduino firmware to v1.1.0
- Check serial connection
- Verify INA260 sensor is connected

### Cache Issues
If you see old behavior after updating:
```bash
python clean_cache.py
```

### Verification
Check firmware version:
```python
arduino = SMTArduinoController()
arduino.connect("COM7")
print(arduino.get_board_info())  # Should show "ID:SMT_SIMPLE_TESTER_V1.1"
```
