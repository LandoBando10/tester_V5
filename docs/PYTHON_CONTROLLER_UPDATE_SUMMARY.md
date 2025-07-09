# Python Controller Update Summary

## Version: 3.0.0

### Overview
The SMTArduinoController has been updated to support the new TESTSEQ protocol for simultaneous relay activation with precise timing control. The controller maintains backward compatibility while adding new methods for the enhanced protocol.

### Major Changes Implemented

1. **New execute_test_sequence() Method**
   - Main entry point for TESTSEQ protocol
   - Takes relay mapping and test sequence from SKU configuration
   - Returns structured results organized by board and function
   - Comprehensive error handling and validation

2. **Relay Mapping Parser**
   - `_parse_relay_mapping()` handles comma-separated relay groups
   - Normalizes relay strings (removes spaces)
   - Supports both single relays ("4") and groups ("1,2,3")

3. **TESTSEQ Command Builder**
   - `_build_testseq_command()` constructs proper command format
   - Groups relays by function for simultaneous activation
   - Adds OFF delays between test steps as configured
   - Example output: `TESTSEQ:1,2,3:500;OFF:100;7,8,9:500`

4. **Response Parser**
   - `_parse_testresults()` handles new batch response format
   - Maps measurements back to board/function structure
   - Handles format: `TESTRESULTS:1,2,3:12.5V,6.8A;7,8,9:12.4V,6.7A;END`

5. **Command Validation**
   - Validates relay numbers (1-16 only)
   - Checks for duplicate relays across groups
   - Ensures minimum timing (>= 100ms)
   - Validates total sequence time (<= 30 seconds)

6. **Backward Compatibility**
   - All existing methods preserved
   - `test_panel()` and `test_panel_stream()` still work
   - `all_relays_off()` for emergency stop
   - Connection and initialization unchanged

### Usage Example

```python
# SKU configuration with relay groups
relay_mapping = {
    "1,2,3": {"board": 1, "function": "mainbeam"},
    "4": {"board": 1, "function": "position"},
    "5,6": {"board": 1, "function": "turn_signal"},
    "7,8,9": {"board": 2, "function": "mainbeam"},
    "10": {"board": 2, "function": "position"},
    "11,12": {"board": 2, "function": "turn_signal"}
}

# Test sequence configuration
test_sequence = [
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
    }
]

# Execute test
controller = SMTArduinoController()
if controller.connect("COM7"):
    result = controller.execute_test_sequence(relay_mapping, test_sequence)
    
    if result["success"]:
        # Results organized by board and function
        for board, functions in result["results"].items():
            print(f"Board {board}:")
            for function, data in functions.items():
                print(f"  {function}: {data['voltage']:.1f}V, {data['current']:.1f}A")
    else:
        print(f"Errors: {result['errors']}")
```

### Return Format

```python
{
    "success": True/False,
    "results": {
        "1": {  # board number
            "mainbeam": {"voltage": 12.5, "current": 6.8, "power": 85.0},
            "position": {"voltage": 12.4, "current": 1.0, "power": 12.4},
            "turn_signal": {"voltage": 12.4, "current": 2.0, "power": 24.8}
        },
        "2": {
            "mainbeam": {"voltage": 12.4, "current": 6.7, "power": 83.5},
            # ...
        }
    },
    "errors": []  # List of error messages if any
}
```

### Error Handling

The controller provides detailed error messages for:
- Invalid relay numbers (must be 1-16)
- Duplicate relay assignments
- Timing constraint violations
- Arduino communication errors
- Response parsing failures

### Testing

A test script `test_testseq_protocol.py` is provided to verify:
- Command building
- Response parsing
- Validation logic
- Integration with Arduino (if connected)

### Migration Notes

- The new `execute_test_sequence()` method is the preferred way to test panels
- Old `test_panel()` method still works but doesn't support simultaneous activation
- SKU files need to be updated to use comma-separated relay groups
- Limits are passed in SKU but validated by the calling code (not the controller)