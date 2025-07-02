# Connection Dialog Combo Selection Fix

**Date:** 2025-01-01  
**Component:** ConnectionDialog  
**Issue:** Port dropdowns not defaulting to connected devices

## Summary

Fixed the hardware connection dialog dropdowns to properly default to showing connected devices. Arduino dropdown now shows the connected Arduino port, Scale dropdown shows the connected scale port, and both show "-- Select Port --" when nothing is connected.

## Changes Made

### 1. Fixed Initialization Order

**In `_load_initial_state()`:**
- Populate dropdowns BEFORE updating connection status
- This ensures ports exist in combos when trying to select them

### 2. Enhanced Port Selection Logic

**In `_populate_all_ports()`:**
- Added explicit selection of connected ports
- Added logging to track selection success/failure
- Explicitly set to placeholder (index 0) when nothing connected

### 3. Added Port Change Handlers

**New/Updated methods:**
- Enhanced `_on_arduino_port_changed()` to handle placeholder selection
- Added `_on_scale_port_changed()` for scale combo (was missing)
- Both properly enable/disable connect buttons based on selection

### 4. Connection State Synchronization

**In connection changed handlers:**
- When device connects, ensure combo shows the connected port
- Prevents combo from showing wrong selection after connection

## Technical Details

### Before:
- Dropdowns populated after connection state update
- No explicit selection when nothing connected
- Scale combo had no change handler
- Combos could show wrong port after connection

### After:
```python
# Proper initialization order
def _load_initial_state():
    self._populate_all_ports()  # First
    self._on_arduino_connection_changed()  # Second

# Explicit selection logic
if connected_arduino:
    index = combo.findData(port)
    combo.setCurrentIndex(index)
else:
    combo.setCurrentIndex(0)  # "-- Select Port --"

# Sync combo on connection
def _on_arduino_connection_changed(connected, port):
    if connected:
        index = combo.findData(port)
        combo.setCurrentIndex(index)
```

## User Experience Improvements

- **Connected devices shown by default**: No confusion about which port is connected
- **Clear placeholder when disconnected**: Shows "-- Select Port --" instead of random port
- **Connect button properly enabled**: Only enabled when valid unconnected port selected
- **Stays synchronized**: Combo updates when devices connect/disconnect

## Testing

- [x] Arduino dropdown defaults to connected Arduino
- [x] Scale dropdown defaults to connected scale
- [x] Both show "-- Select Port --" when nothing connected
- [x] Connect button disabled for placeholder selection
- [x] Connect button disabled for already connected ports
- [x] Combos update when devices connect/disconnect