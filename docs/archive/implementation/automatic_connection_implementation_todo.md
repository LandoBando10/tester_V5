# Automatic Hardware Connection Implementation Todo List

## Overview
Implement automatic hardware connection management that connects appropriate devices when switching between SMT, Offroad, and Weight Checker modes while maintaining backward compatibility and system stability.

## Phase 1: Foundation (Priority: High)

### 1.1 Connection Helper Class
- [ ] Create `src/hardware/connection_helper.py`
- [ ] Implement `ConnectionHelper` class with:
  - [ ] `__init__(self, main_window, connection_dialog)`
  - [ ] `get_mode_requirements(mode)` - Returns required hardware for each mode
  - [ ] `find_compatible_device(device_type, firmware_type)` - Scans for matching device
  - [ ] `validate_connection(mode)` - Checks if current connections match mode requirements

### 1.2 Device Memory System
- [ ] Add device cache to `ConnectionDialog`:
  - [ ] Create `_mode_device_memory` dict to store last known devices per mode
  - [ ] Implement `save_successful_device(mode, device_type, port, device_info)`
  - [ ] Implement `get_last_known_device(mode, device_type)`
  - [ ] Update `.device_cache.json` format to include mode-specific memory

### 1.3 Graceful Disconnection
- [ ] Update `main_window.py` `set_mode()` method:
  - [ ] Add check for running tests before mode switch
  - [ ] Stop voltage monitoring if active
  - [ ] Clear Arduino callbacks before disconnect
  - [ ] Add proper wait for threads to stop

## Phase 2: Auto-Connection Logic (Priority: High)

### 2.1 Mode-Specific Connection Methods
- [ ] Add to `ConnectionDialog`:
  - [ ] `connect_for_mode(mode)` - Main auto-connect method
  - [ ] `auto_connect_smt_arduino()` - SMT-specific connection
  - [ ] `auto_connect_offroad_arduino()` - Offroad-specific connection
  - [ ] `auto_connect_scale()` - Scale connection for weight checker

### 2.2 Connection Progress Indication
- [ ] Create `ConnectionProgressDialog`:
  - [ ] Non-blocking progress dialog
  - [ ] Show connection steps (Scanning → Connecting → Validating)
  - [ ] Cancel button to skip auto-connect
  - [ ] Auto-close on success

### 2.3 Mode Switch Enhancement
- [ ] Update `main_window.py`:
  - [ ] Integrate ConnectionHelper
  - [ ] Add auto-disconnect logic for incompatible hardware
  - [ ] Add auto-connect call after mode switch
  - [ ] Handle connection failures gracefully

## Phase 3: Error Handling & Recovery (Priority: Medium)

### 3.1 Connection Failure Handling
- [ ] Implement retry logic (1 automatic retry)
- [ ] Show non-intrusive notification on failure
- [ ] Fall back to manual connection dialog
- [ ] Log connection attempts for debugging

### 3.2 Mode Validation
- [ ] Add firmware validation before mode operations
- [ ] Prevent test execution with wrong firmware
- [ ] Show clear status indicators
- [ ] Add recovery suggestions in UI

### 3.3 Thread Safety
- [ ] Add locks for connection state changes
- [ ] Ensure atomic mode switching
- [ ] Prevent concurrent connection attempts
- [ ] Handle interrupted connections

## Phase 4: User Experience (Priority: Medium)

### 4.1 Status Indicators
- [ ] Update status bar to show:
  - [ ] Current mode
  - [ ] Arduino connection state and firmware type
  - [ ] Scale connection state (if applicable)
  - [ ] Auto-connect status

### 4.2 Settings & Configuration
- [ ] Add settings for auto-connection:
  - [ ] Enable/disable auto-connect
  - [ ] Connection timeout adjustment
  - [ ] Clear device memory option
  - [ ] Connection retry count

### 4.3 Manual Override
- [ ] Preserve manual connection dialog functionality
- [ ] Add "Force Refresh" option
- [ ] Add "Clear Device Memory" button
- [ ] Keep all existing manual controls

## Phase 5: Testing & Validation (Priority: High)

### 5.1 Unit Tests
- [ ] Test ConnectionHelper methods
- [ ] Test device memory persistence
- [ ] Test mode requirement validation
- [ ] Test error handling paths

### 5.2 Integration Tests
- [ ] Test mode switching scenarios:
  - [ ] SMT → Offroad → SMT
  - [ ] SMT → Weight Checker → SMT
  - [ ] All permutations with disconnected hardware
- [ ] Test with wrong firmware Arduino connected
- [ ] Test with no hardware connected
- [ ] Test connection failures and retries

### 5.3 Regression Tests
- [ ] Verify voltage monitoring still works
- [ ] Verify button callbacks work in SMT
- [ ] Verify test execution unaffected
- [ ] Verify manual connections work
- [ ] Verify scale connections for weight checker

## Phase 6: Documentation (Priority: Low)

### 6.1 Code Documentation
- [ ] Document ConnectionHelper class
- [ ] Update connection dialog documentation
- [ ] Document new settings options
- [ ] Add inline comments for complex logic

### 6.2 User Documentation
- [ ] Update user manual with auto-connect behavior
- [ ] Document troubleshooting steps
- [ ] Create connection workflow diagram
- [ ] Update FAQ section

## Implementation Order

1. **Week 1**: Phase 1 (Foundation) + Phase 2.1-2.2
2. **Week 2**: Phase 2.3 + Phase 3 (Error Handling)
3. **Week 3**: Phase 4 (User Experience) + Phase 5.1-5.2
4. **Week 4**: Phase 5.3 (Regression) + Phase 6 (Documentation)

## Success Criteria

- [ ] Mode switching automatically connects correct hardware
- [ ] No manual intervention required for typical workflows
- [ ] Connection failures are handled gracefully
- [ ] All existing functionality remains intact
- [ ] Performance impact < 2 seconds for mode switch
- [ ] Zero breaking changes to existing code
- [ ] User satisfaction with auto-connect feature

## Rollback Plan

If issues arise:
1. Disable auto-connect via settings flag
2. Revert to manual connection only
3. Keep device memory for future retry
4. All changes designed to be feature-flagged

## Notes

- Prioritize stability over speed
- Test with multiple Arduino devices
- Consider edge cases (USB disconnect during operation)
- Monitor user feedback closely after deployment