# SKU Relay Grouping Guide

## Overview

The SMT testing system now supports simultaneous relay activation through comma-separated relay groups. This allows multiple relays to be activated together, enabling accurate measurement of parallel circuits and reducing test time.

## New SKU Format

### Relay Mapping

The `relay_mapping` section now supports comma-separated relay numbers:

```json
"relay_mapping": {
    "1,2,3": {      // Multiple relays activated simultaneously
        "board": 1,
        "function": "mainbeam"
    },
    "4": {          // Single relay (backward compatible)
        "board": 1,
        "function": "position"
    },
    "5,6": {        // Two relays for parallel circuit
        "board": 1,
        "function": "turn_signal"
    }
}
```

### Key Features

1. **Comma-Separated Groups**: Use commas to group relays that should activate together
2. **No Spaces**: While spaces are tolerated, prefer `"1,2,3"` over `"1, 2, 3"`
3. **Single Relays**: Single relays use the same format as before (`"4"`)
4. **16 Relay Maximum**: Hardware limited to relays 1-16

### Test Sequence

The test sequence remains the same, but now operates on relay groups:

```json
"test_sequence": [
    {
        "function": "mainbeam",
        "duration_ms": 500,      // Total time relays are active
        "delay_after_ms": 100,   // Delay before next test
        "limits": {
            "current_a": {"min": 5.4, "max": 6.9},  // Combined current for group
            "voltage_v": {"min": 11.5, "max": 12.5}
        }
    }
]
```

## Migration from Old Format

### Automatic Migration

Use the provided migration script to convert existing SKU files:

```bash
# Migrate all SMT SKU files
python scripts/migrate_sku_relay_groups.py

# Migrate specific directory
python scripts/migrate_sku_relay_groups.py config/skus/smt

# Migrate single file
python scripts/migrate_sku_relay_groups.py config/skus/smt/DD5001.json

# Dry run to see what would change
python scripts/migrate_sku_relay_groups.py --dry-run

# Migrate without creating backups
python scripts/migrate_sku_relay_groups.py --no-backup
```

### Manual Migration

To manually convert a SKU file:

1. Identify relays with the same board and function
2. Combine them into a comma-separated key
3. Keep single relays as-is

**Before:**
```json
"relay_mapping": {
    "1": {"board": 1, "function": "mainbeam"},
    "2": {"board": 1, "function": "mainbeam"},
    "3": {"board": 1, "function": "mainbeam"},
    "4": {"board": 1, "function": "position"}
}
```

**After:**
```json
"relay_mapping": {
    "1,2,3": {"board": 1, "function": "mainbeam"},
    "4": {"board": 1, "function": "position"}
}
```

## Technical Details

### Arduino Protocol

The system uses the TESTSEQ protocol:

```
Command:  TESTSEQ:1,2,3:500;OFF:100;7,8,9:500
Response: TESTRESULTS:1,2,3:12.5V,6.8A;7,8,9:12.4V,6.7A;END
```

### Measurement Behavior

- **Voltage**: Same across parallel relays (uses measured value)
- **Current**: Sum of all relays in the group
- **Power**: Calculated as voltage × total current

### Validation Rules

1. Each relay can only appear in one group
2. Relay numbers must be 1-16
3. Maximum 8 relays active simultaneously (configurable)
4. Minimum duration: 100ms
5. Maximum total sequence time: 30 seconds

### Error Handling

The system validates configurations and provides clear error messages:

- `Invalid relay number: 17 (must be 1-16)`
- `Relay 5 appears in multiple groups`
- `Duration 50ms too short (minimum 100ms)`
- `Total sequence time 35000ms exceeds 30 second limit`

## Example Configurations

### Simple 2-Board Panel

```json
{
    "description": "2-board panel with mainbeam and position lights",
    "relay_mapping": {
        "1,2": {"board": 1, "function": "mainbeam"},
        "3": {"board": 1, "function": "position"},
        "4,5": {"board": 2, "function": "mainbeam"},
        "6": {"board": 2, "function": "position"}
    },
    "test_sequence": [
        {
            "function": "mainbeam",
            "duration_ms": 500,
            "delay_after_ms": 100,
            "limits": {
                "current_a": {"min": 2.5, "max": 3.5},
                "voltage_v": {"min": 11.5, "max": 12.5}
            }
        },
        {
            "function": "position",
            "duration_ms": 300,
            "delay_after_ms": 0,
            "limits": {
                "current_a": {"min": 0.8, "max": 1.2},
                "voltage_v": {"min": 11.5, "max": 12.5}
            }
        }
    ]
}
```

### Complex Multi-Function Board

```json
{
    "description": "Complex board with multiple parallel LED strings",
    "relay_mapping": {
        "1,2,3,4": {"board": 1, "function": "high_beam"},
        "5,6": {"board": 1, "function": "low_beam"},
        "7": {"board": 1, "function": "position"},
        "8,9": {"board": 1, "function": "turn_signal"},
        "10,11,12,13": {"board": 2, "function": "high_beam"},
        "14,15": {"board": 2, "function": "low_beam"},
        "16": {"board": 2, "function": "position"}
    }
}
```

## Backward Compatibility

- Old SKU files with individual relay mappings still work
- The system automatically detects the format
- Legacy Arduino firmware falls back to sequential testing
- No changes required for existing test sequences

## Best Practices

1. **Group Related Relays**: Combine relays that power the same function
2. **Test Order**: Test high-current functions first for better thermal management
3. **Timing**: Allow adequate stabilization time (50ms default)
4. **Documentation**: Add notes explaining unusual groupings

## Troubleshooting

### Common Issues

1. **Relay Overlap Error**: Ensure each relay appears in only one group
2. **Measurement Differences**: Grouped relays show combined current
3. **Timing Issues**: Increase duration if measurements are unstable
4. **I2C Errors**: Check PCF8575 connections and pull-up resistors

### Debug Commands

```python
# Test command building without hardware
from src.hardware.smt_arduino_controller import SMTArduinoController
controller = SMTArduinoController()

relay_mapping = {"1,2,3": {"board": 1, "function": "mainbeam"}}
test_sequence = [{"function": "mainbeam", "duration_ms": 500}]

command = controller._build_testseq_command(
    controller._parse_relay_mapping(relay_mapping),
    test_sequence
)
print(f"Command: {command}")
# Output: TESTSEQ:1,2,3:500
```

## Support

For questions or issues:
- Check Arduino firmware version (must be 2.0.0+ for TESTSEQ support)
- Verify PCF8575 I2C connection at address 0x20
- Review validation errors in the test log
- Run migration script with `--dry-run` to preview changes