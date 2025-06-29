# Fast Startup Connection Implementation

## Overview
Optimize startup by connecting to first Arduino immediately during port scan, then scan remaining ports in background.

## Current Problem
- All ports scanned with temp connections before auto-connect
- First Arduino connected twice (scan + actual connection)
- 2-5 second delay before user can start working

## Implementation Tasks

### 1. Modify Preloader Port Scanning
**File:** `src/gui/startup/preloader.py`
- Change `_scan_serial_ports()` to sequential scan with immediate connection
- When Arduino found:
  - Keep connection open
  - Store connected port and controller instance
  - Continue scanning other ports in background
- Pass connected controller to MainWindow via PreloadedComponents

### 2. Update Connection Dialog Auto-Connect
**File:** `src/gui/components/connection_dialog.py`
- Check if controller already connected from preloader
- Skip auto-connect if already connected
- Update UI to show connected device immediately
- Implement background port scanning for remaining devices
- Add "Scanning..." indicator to port dropdown

### 3. Implement Smart Port Ordering
**File:** `src/hardware/serial_manager.py`
- Load last successful Arduino port from cache
- Try cached port first during startup
- Sort remaining ports by likelihood (COM3-10 first on Windows)

### 4. Create Progressive Port Scanner
**File:** `src/gui/components/connection_dialog.py`
- Add `ProgressivePortScanner` class:
  - Sequential scan for first Arduino
  - Parallel scan for remaining ports
  - Emit signals for UI updates as devices found
  - Support cancellation

### 5. Update MainWindow Integration
**File:** `src/gui/main_window.py`
- Accept pre-connected controller from preloader
- Skip connection dialog if already connected
- Show connection status immediately

### 6. Handle Edge Cases
- If first device is Scale, continue scanning for Arduino
- If pre-connected Arduino disconnects, handle gracefully
- Ensure proper cleanup if user cancels during startup

### 7. Update Device Cache
**File:** `config/.device_cache.json`
- Add `last_arduino_port` field
- Update on successful connection
- Use for smart port ordering

## Testing Checklist
- [ ] Single Arduino: Connects in <0.5s
- [ ] Multiple devices: All shown after background scan
- [ ] No Arduino: Falls back gracefully
- [ ] Port disconnect during scan: Handled properly
- [ ] Cache works across restarts
- [ ] UI updates progressively