# SKU Configuration Update Summary

## Overview

Section 3 of the SMT Simultaneous Relay Activation project has been completed. The SKU configuration system now supports comma-separated relay groups for simultaneous activation, with comprehensive validation and migration tools.

## Major Changes Implemented

### 1. SKU File Format Updates

**New relay_mapping format supports grouped relays:**
```json
"relay_mapping": {
    "1,2,3": {"board": 1, "function": "mainbeam"},     // Group of 3 relays
    "4": {"board": 1, "function": "position"},         // Single relay
    "5,6": {"board": 1, "function": "turn_signal"}     // Group of 2 relays
}
```

### 2. Parser Updates (in SMTArduinoController)

- `_parse_relay_mapping()` - Handles comma-separated relay groups
- Normalizes relay strings (removes spaces)
- Maintains backward compatibility with single relays

### 3. SMT Test Updates

- Updated to use new `execute_test_sequence()` method when available
- Falls back to legacy `test_panel()` for older firmware
- `_distribute_panel_results()` updated to handle grouped relays
- Aggregates measurements for parallel circuits (currents add, voltage same)
- `_format_board_results()` preserves relay group format in results

### 4. Validation Features

- Each relay can only appear in one group
- Relay numbers validated (1-16 only)
- Timing constraints enforced (min 100ms, max 30s total)
- Maximum simultaneous relays configurable (default 8)

### 5. Migration Tools

**Migration Script**: `scripts/migrate_sku_relay_groups.py`
- Automatically converts old format to new grouped format
- Groups relays by board and function
- Creates backups by default
- Supports dry-run mode
- Handles single files or entire directories

**Usage:**
```bash
# Migrate all SMT SKUs with backup
python scripts/migrate_sku_relay_groups.py

# Dry run to preview changes
python scripts/migrate_sku_relay_groups.py --dry-run

# Migrate without backup
python scripts/migrate_sku_relay_groups.py --no-backup
```

### 6. Documentation

**Created comprehensive documentation:**
- `docs/SKU_RELAY_GROUPING_GUIDE.md` - Complete guide for the new format
- Migration instructions
- Technical details
- Example configurations
- Troubleshooting guide

## Example Migration

**Before (old format):**
```json
"relay_mapping": {
    "1": {"board": 1, "function": "mainbeam"},
    "2": {"board": 1, "function": "mainbeam"},
    "3": {"board": 1, "function": "mainbeam"},
    "4": {"board": 1, "function": "position"}
}
```

**After (new format):**
```json
"relay_mapping": {
    "1,2,3": {"board": 1, "function": "mainbeam"},
    "4": {"board": 1, "function": "position"}
}
```

## Backward Compatibility

- Old SKU files continue to work without modification
- System automatically detects format (single vs grouped)
- Legacy Arduino firmware falls back to sequential testing
- No changes required to test_sequence configuration

## Test Integration

The system now provides two test paths:

1. **New TESTSEQ Protocol** (preferred):
   - Uses `execute_test_sequence()` method
   - Simultaneous relay activation
   - Single command/response cycle
   - Better performance and accuracy

2. **Legacy test_panel** (fallback):
   - Sequential relay testing
   - Multiple command/response cycles
   - Works with older firmware

## Files Created/Modified

### Created:
- `/scripts/migrate_sku_relay_groups.py` - Migration tool
- `/docs/SKU_RELAY_GROUPING_GUIDE.md` - User guide
- `/config/skus/smt/EXAMPLE_GROUPED.json` - Example grouped SKU

### Modified:
- `/src/core/smt_test.py` - Updated to use new protocol
- `/src/hardware/smt_arduino_controller.py` - Added TESTSEQ methods
- Existing SKU files can be migrated using the tool

## Next Steps

1. Run migration script on all SMT SKU files
2. Test with new firmware (v2.0.0) and PCF8575 hardware
3. Update production SKU files as new products are added
4. Monitor test performance improvements

## Benefits

- **Faster Testing**: Simultaneous activation reduces test time
- **More Accurate**: Measures actual parallel circuit behavior
- **Better Organization**: Groups related relays logically
- **Easy Migration**: Automated tools for conversion
- **Future Proof**: Supports up to 16 relays with expansion capability