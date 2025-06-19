# SMT Panel Testing - Batch Communication Only (v2.0)

## Quick Summary

The SMT testing system has been simplified to use **only batch communication**. No more individual relay commands - every test measures all 8 relays at once.

**Result: 3-4x faster testing with simpler, more reliable code!**

## What Changed?

### ❌ Removed (No Longer Available)
- Individual relay measurements (`R1`, `R2`, etc.)
- `measure_relay()` method
- `measure_relays()` method
- Complex retry logic
- Optional measurement modes

### ✅ Added/Kept
- Single `test_panel()` method - measures all 8 relays
- `test_panel_stream()` method - with progress updates
- Consistent ~1 second test time
- Simplified, maintainable code

## How to Upgrade

1. **Upload New Arduino Firmware**
   ```
   Arduino_firmware/SMT_Simple_Tester.ino (v2.0.0)
   ```

2. **Clear Python Cache**
   ```bash
   python clean_cache.py
   ```

3. **Update Your Code**
   ```python
   # Old way (no longer works):
   results = controller.measure_relays([1, 2, 3, 4])
   
   # New way (only option):
   results = controller.test_panel()  # Always measures all 8
   ```

## Example Code

```python
from src.hardware.smt_arduino_controller import SMTArduinoController

# Connect
controller = SMTArduinoController()
controller.connect("COM7")

# Test panel (always all 8 relays)
results = controller.test_panel()

# Use the results you need
for relay_num, data in results.items():
    if data:
        print(f"Relay {relay_num}: {data['voltage']:.3f}V")

# Cleanup
controller.disconnect()
```

## Why Batch-Only?

1. **Speed**: 3-4x faster (1 second vs 3-4 seconds)
2. **Simplicity**: One way to do things = no confusion
3. **Reliability**: Fewer commands = fewer failure points
4. **Maintainability**: Less code to debug and maintain

## Files Changed

- `Arduino_firmware/SMT_Simple_Tester.ino` - Batch-only firmware
- `src/hardware/smt_arduino_controller.py` - Simplified controller
- `src/core/smt_test.py` - Updated to use batch testing only

## Demo Scripts

- `demo_batch_testing.py` - Shows the new batch-only system
- `clean_cache.py` - Clears Python cache files

## Need Help?

See the full migration guide: `docs/batch_only_migration.md`

---

**Remember: The system now ALWAYS measures all 8 relays. This is by design for maximum speed and simplicity.**
