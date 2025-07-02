# Port Scanner Fix Summary

## Problem
The system had a circular dependency between `probe_port()` and the port registry that caused two major issues:
1. Empty dropdowns in the connection dialog on first open
2. Inability to reconnect to Arduino after mode changes

## Root Cause
The `probe_port()` method in `PortScannerService` would immediately return `None` for any port marked as "in use" in the registry:

```python
# OLD CODE - This was the problem
if port_registry.is_port_in_use(port):
    logger.info(f"Skipping port {port} - already in use")
    return None
```

This meant:
- Connected devices couldn't be re-identified for dropdown descriptions
- `ConnectionService.connect_arduino()` would fail because it relied on `probe_port()` returning device info

## Solution Implemented

### 1. Enhanced `probe_port()` Method
Added a `check_in_use` parameter to allow checking ports even when they're in the registry:

```python
def probe_port(self, port: str, timeout: float = None, check_in_use: bool = False) -> Optional[DeviceInfo]:
    """
    Args:
        check_in_use: If True, probe ports that are already in use (read-only check)
    """
```

When `check_in_use=True`:
- First tries to get info from cache (safe, no serial disruption)
- Returns cached device info if available
- Falls back to generic "Device in use" info if no cache

### 2. Updated Connection Dialog
The `_refresh_ports()` method now checks for connected ports that weren't in scan results:

```python
# For any connected ports that weren't in the scan results, 
# do a special check to get their info
if connected_arduino_port and not any(d.port == connected_arduino_port for d in devices):
    device_info = self.port_scanner.probe_port(connected_arduino_port, check_in_use=True)
    if device_info:
        devices.append(device_info)
```

### 3. Updated ConnectionService
Modified to handle the case where a port might already be in use:

```python
# Probe the port to get device info
# Use check_in_use=True if it's our current port
device_info = self.port_scanner.probe_port(port, check_in_use=is_our_port)

if not device_info:
    # Try with check_in_use=True as fallback
    device_info = self.port_scanner.probe_port(port, check_in_use=True)
```

### 4. Enhanced Cache Storage
Now stores the device response string for better re-identification:

```python
self.cache_service.update_device(port, {
    'device_type': 'Arduino',
    'firmware_type': firmware_type,
    'description': device_info.description,
    'response': device_info.response  # Important for re-identification
})
```

### 5. New Helper Method
Added `identify_port_safe()` for safe port identification without disruption:

```python
def identify_port_safe(self, port: str) -> Optional[DeviceInfo]:
    """Safely identify a port without disrupting existing connections."""
```

## Expected Results
1. **Connection dialog will show device descriptions** even for connected ports
2. **Arduino can be reconnected** after mode changes because `probe_port()` will return cached info
3. **No serial disruption** for already-connected devices
4. **Better user experience** with properly populated dropdowns

## Files Modified
- `/src/services/port_scanner_service.py` - Added `check_in_use` parameter and `identify_port_safe()` method
- `/src/gui/components/connection_dialog.py` - Updated to check connected ports with `check_in_use=True`
- `/src/services/connection_service.py` - Modified to use fallback probing with `check_in_use=True`
- `/src/services/device_cache_service.py` - Added `get_device()` alias method