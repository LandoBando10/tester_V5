# SMT Testing System - Batch-Only Migration Guide

## Overview

Version 2.0 of the SMT testing system has been simplified to use **only batch communication**. All individual relay measurement commands have been removed in favor of a single panel test approach.

## Key Changes

### What's Been Removed
- ❌ Individual relay commands (`R1`, `R2`, ... `R8`)
- ❌ `measure_relay()` method
- ❌ `measure_relays()` method
- ❌ Complex retry logic for individual measurements
- ❌ Unnecessary communication overhead

### What's New
- ✅ Batch-only communication (always measures all 8 relays)
- ✅ Simplified Arduino firmware (v2.0.0)
- ✅ Cleaner Python controller code
- ✅ Consistent ~1 second test time
- ✅ More reliable communication

## Performance

**Before (v1.x):** 8 individual commands = 3-4 seconds per panel
**Now (v2.0):** 1 batch command = ~1 second per panel

**Result:** 3-4x faster with simpler, more reliable code!

## Arduino Commands

### Old System (v1.x)
```
R1 - Measure relay 1
R2 - Measure relay 2
...
R8 - Measure relay 8
T  - Test panel (optional)
X  - All relays off
I  - Get info
B  - Button status
```

### New System (v2.0)
```
T  - Test panel (required - measures all 8 relays)
TS - Test panel with streaming updates
X  - All relays off
I  - Get info
B  - Button status
```

## Code Migration

### Testing a Panel

**Old way (v1.x):**
```python
# Could test individual relays
result1 = controller.measure_relay(1)
result2 = controller.measure_relay(2)

# Or multiple relays
results = controller.measure_relays([1, 2, 3, 4])

# Or all relays
results = controller.measure_relays([1, 2, 3, 4, 5, 6, 7, 8])
```

**New way (v2.0):**
```python
# Always tests all 8 relays
results = controller.test_panel()

# Or with progress updates
results = controller.test_panel_stream(progress_callback)
```

### Handling Partial Tests

If you only need data from specific relays, you still run the full panel test but only use the results you need:

```python
# Test entire panel
all_results = controller.test_panel()

# Extract only the relays you care about
relay_2_data = all_results.get(2)
relay_5_data = all_results.get(5)
```

## Benefits of Batch-Only

1. **Simplicity**: One way to do things = less confusion
2. **Speed**: Always fast, no slow paths
3. **Reliability**: Fewer commands = fewer failure points
4. **Consistency**: Every test takes the same time
5. **Maintainability**: Less code to maintain and debug

## Installation

1. **Update Arduino Firmware**
   - Upload the new `SMT_Simple_Tester.ino` (v2.0.0)
   - Firmware will report as `ID:SMT_BATCH_TESTER_V2.0`

2. **Clear Python Cache**
   ```bash
   python clean_cache.py
   ```

3. **Test the System**
   ```bash
   python demo_batch_testing.py
   ```

## API Reference

### SMTArduinoController (v2.0)

```python
class SMTArduinoController:
    def connect(port: str) -> bool
    def disconnect()
    def is_connected() -> bool
    
    # Main testing methods
    def test_panel() -> Dict[int, Dict[str, float]]
    def test_panel_stream(progress_callback) -> Dict[int, Dict[str, float]]
    
    # Utility methods
    def all_relays_off() -> bool
    def get_button_status() -> str
    def get_firmware_info() -> str
    def set_button_callback(callback)
    def start_reading()
    def stop_reading()
```

## Example Usage

```python
from src.hardware.smt_arduino_controller import SMTArduinoController

# Create controller
controller = SMTArduinoController()

# Connect
if controller.connect("COM7"):
    # Test panel
    results = controller.test_panel()
    
    # Process results
    for relay_num, data in results.items():
        if data:
            print(f"Relay {relay_num}: {data['voltage']:.3f}V, {data['current']:.3f}A")
    
    # Cleanup
    controller.all_relays_off()
    controller.disconnect()
```

## Troubleshooting

### "Invalid panel test response"
- Make sure you've uploaded the v2.0 firmware
- Check that INA260 sensor is connected
- Verify serial connection at 115200 baud

### Results show all 8 relays but I only need some
- This is normal - the system always measures all 8
- Just extract the data you need from the results dictionary
- The extra measurements don't slow things down

### Old code is still running
- Run `python clean_cache.py` to clear Python cache
- Restart your application
- Verify firmware with `controller.get_firmware_info()`

## Philosophy

The batch-only approach follows the principle of "one way to do things". By removing the option for individual relay measurements, we've made the system:
- Faster (always uses the optimal path)
- Simpler (less code, fewer bugs)
- More predictable (consistent timing)
- Easier to maintain (fewer code paths to test)

This is a breaking change, but the benefits far outweigh the migration effort.
