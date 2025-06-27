# SMT Simple Tester - 16 Relay Version (v3.0)

## Overview
The SMT Simple Tester now supports 16 relays with selective testing capabilities. This allows testing of larger panels and more complex SKUs with a single TX command.

## Hardware Changes

### Pin Mapping
```
Relays 1-8:  Pins 2-9 (unchanged)
Relays 9-16: Pins 10-13, A0-A3 (pins 14-17)
Button:      Pin A4 (18) - moved from pin 10
LED:         Built-in LED (unchanged)
```

### Wiring Changes Required
1. Move button connection from pin 10 to pin A4
2. Connect relays 9-16 to pins 10-13 and A0-A3
3. Ensure relay modules support 16 channels or add second 8-channel module

## Command Reference

### Commands
- `TX:1,2,5,6` - Test specific relays (1-16)
- `TX:1-4,9-12` - Test relay ranges
- `TX:1-8` - Test first 8 relays (replaces old T command)
- `TX:ALL` - Test all 16 relays
- `X` - Turn all relays off
- `I` - Get ID, returns: `ID:SMT_BATCH_TESTER_V3.0_16RELAY`
- `B` - Get button status
- `V` - Get supply voltage

### Response Format

#### TX Command Response
```
PANELX:1=12.847,3.260;2=12.850,3.245;5=12.843,3.267;6=12.841,3.251
```

Note: Each relay is explicitly numbered in the response, making it clear which relays were tested.

### Error Messages
- `ERROR:INVALID_RELAY_LIST` - Malformed relay list or invalid relay numbers
- `ERROR:EMPTY_RELAY_LIST` - No relays specified in TX command
- `ERROR:UNKNOWN_COMMAND` - Command not recognized

## Usage Examples

### Test specific relays for a 4-board mainbeam SKU
```
Command: TX:1,2,3,4
Response: PANELX:1=12.847,3.260;2=12.850,3.245;3=12.843,3.267;4=12.841,3.251
```

### Test 8-board panel with mainbeam and backlight
```
Command: TX:1-8,9-16
Response: PANELX:1=12.847,3.260;2=12.850,3.245;...;16=5.123,0.450
```

### Stream test for real-time feedback
```
Command: TSX:1,5,9,13
Response:
RELAY:1,12.847,3.260
RELAY:5,12.843,3.267
RELAY:9,12.845,3.262
RELAY:13,12.844,3.265
PANEL_COMPLETE
```

## Python Integration

The Python code should:
1. Read SKU relay_mapping to determine which relays to test
2. Use TX command with only the mapped relays
3. Parse PANELX response format to map results back to boards/functions

Example:
```python
# For SKU with relays 1,2,5,6 mapped
active_relays = [1, 2, 5, 6]
command = f"TX:{','.join(map(str, active_relays))}"
# Send: TX:1,2,5,6
# Receive: PANELX:1=12.847,3.260;2=12.850,3.245;5=12.843,3.267;6=12.841,3.251
```

## Migration Notes

1. **Python changes required** - Must update to use TX command instead of T
2. **All SKUs must be updated** - Use TX:1-8 to test first 8 relays
3. **Hardware modification required** - Button must be moved to A4
4. **No backward compatibility** - All systems must be updated together

## Performance

- Per-relay test time: ~117ms (unchanged)
- 8-relay test: ~1 second
- 16-relay test: ~2 seconds
- Selective 4-relay test: ~0.5 seconds

## Version History
- v2.3.0: Original 8-relay version
- v3.0.0: Extended to 16 relays with selective testing