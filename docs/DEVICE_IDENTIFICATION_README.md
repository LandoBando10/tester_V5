# Device Type Identification Feature

## Overview
The testerv5 program now automatically identifies the type of device connected to each COM port when refreshing the port list. Instead of showing generic port names like "COM1", "COM4", etc., it now displays:
- `COM4 (SMT Arduino)`
- `COM5 (Offroad Arduino)`
- `COM7 (Scale)`
- `COM3 (Unknown)` - for unidentified devices

## How It Works

### Device Identification Process
When you click "Refresh Ports" in the connection dialog, the program:

1. **Lists all available COM ports** on the system
2. **Probes each port** to identify the connected device:
   - First attempts Arduino connection at 115200 baud
   - Sends an "ID" command and analyzes the response
   - If no Arduino response, tries Scale connection at 9600 baud
   - Looks for weight data patterns (e.g., "g", "GS", numeric values)
3. **Categorizes devices** based on their responses:
   - **SMT Arduino**: Response contains "SMT" or "SMT_TESTER"
   - **Offroad Arduino**: Response contains "OFFROAD"
   - **Scale**: Data contains weight patterns (grams, numeric values)
   - **Unknown**: No recognizable response pattern

### Display Format
The port selection dropdown now shows:
```
COM4 (SMT Arduino)
COM5 (Scale)
COM7 (Offroad Arduino)
COM3 (Unknown)
COM8 (Connected Arduino)  // Already connected devices
```

## Important Notes

### Performance
- The identification process adds a small delay (1-2 seconds) when refreshing ports
- Each port is probed briefly with short timeouts to minimize delays
- Already connected devices are not re-probed

### Device Recognition
- **Arduino devices** must respond to the "ID" command with proper firmware identification
- **Scales** are identified by continuous weight data output
- Devices that don't respond or have unexpected protocols show as "Unknown"

### Troubleshooting
If a device shows as "Unknown" when it should be identified:
1. Ensure the device is powered on and properly connected
2. Check that the device firmware is up to date
3. Try disconnecting and reconnecting the device
4. Manual selection still works - you can connect to "Unknown" devices

### Firmware Requirements
For proper identification:
- **Arduino firmware** must implement the "ID" command returning:
  - "SMT_TESTER" or similar for SMT boards
  - "OFFROAD" for offroad testing boards
  - "DIODE_DYNAMICS" as a fallback (will check STATUS for mode)
- **Scales** should output continuous weight data in standard formats

## Usage Tips

1. **Smart Filtering**: The dropdown lists prioritize showing appropriate devices:
   - Arduino dropdown shows Arduino devices first
   - Scale dropdown shows scales first
   - Unknown devices appear in both lists

2. **Quick Identification**: Look for the device type in parentheses to quickly find the right port

3. **Fallback Support**: If identification fails, you can still manually select any port

## Technical Details

### Implementation
The feature is implemented in `src/gui/components/connection_dialog.py`:
- `_identify_devices()`: Orchestrates device identification for all ports
- `_probe_port()`: Probes a single port to determine device type
- Modified `refresh_ports()`: Updates UI with device type information

### Communication Protocols
- **Arduino**: 115200 baud, expects "ID" command response
- **Scale**: 9600 baud, continuous weight data stream
- Timeouts are kept short (0.5-1.0 seconds) to maintain responsiveness

## Future Enhancements
Potential improvements could include:
- Caching device types between refreshes
- Background identification to avoid UI blocking
- More device type support (e.g., different scale models)
- User-configurable device identification patterns
