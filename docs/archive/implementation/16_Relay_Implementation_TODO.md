# 16-Relay Implementation TODO List

## Overview
This document tracks the implementation tasks for extending the SMT testing system from 8 to 16 relays with selective testing capabilities.

## ✅ Completed Tasks

### Arduino Firmware (SMT_Simple_Tester.ino)
- [x] Update pin definitions to support 16 relays
- [x] Move button from pin 10 to pin A4
- [x] Implement TX command for selective relay testing
- [x] Add TX:ALL support for testing all 16 relays
- [x] Add relay list parsing (comma-separated and ranges)
- [x] Add PANELX response format with relay numbers
- [x] Add error handling for invalid relay lists
- [x] Update version ID to V3.0_16RELAY
- [x] Remove all backward compatibility (T command)
- [x] Remove all streaming functionality (TS, TSX, TS16)
- [x] Create documentation for firmware changes

## 🔲 Pending Tasks

### Python Code Updates

#### Phase 1: Core Controller Updates (Priority: High)
- [ ] **SMTArduinoController** (`src/hardware/smt_arduino_controller.py`)
  - [ ] Replace `test_panel()` method with `test_panel_selective(relay_list)`
  - [ ] Remove `test_panel_stream()` method entirely
  - [ ] Add `_parse_panelx_response()` parser for PANELX format
  - [ ] Remove all hardcoded "8 relay" references
  - [ ] Remove firmware version detection (not needed)
  - [ ] Update all test methods to use TX command only

#### Phase 2: Test Logic Updates (Priority: High)
- [ ] **SMTTest** (`src/tests/smt_test.py`)
  - [ ] Add `_get_active_relays()` method to extract from SKU
  - [ ] Update `run_test_sequence()` to use selective testing
  - [ ] Update `_distribute_panel_results()` to handle >8 relays
  - [ ] Add firmware version compatibility checks
  - [ ] Update result formatting for 16 relays

#### Phase 3: GUI Updates (Priority: Medium)
- [ ] **SMTHandler** (`src/gui/handlers/smt_handler.py`)
  - [ ] Remove hardcoded `range(1, 9)` loops
  - [ ] Make relay display dynamic based on SKU
  - [ ] Update progress tracking for variable relay counts
  - [ ] Update relay control buttons (if any)

#### Phase 4: SKU System Updates (Priority: Medium)
- [ ] **SKU Schema** (`src/data/sku_manager.py` or schema file)
  - [ ] Update validation to allow relay keys "1"-"16"
  - [ ] Add firmware version requirements to SKU (optional)
  - [ ] Create migration guide for existing SKUs

- [ ] **SKU Files** (`config/skus/*.json`)
  - [ ] Create example 16-relay SKU file
  - [ ] Document relay_mapping for 16-relay configurations
  - [ ] Add examples for different panel layouts

#### Phase 5: Error Handling (Priority: High)
- [ ] Add clear error messages for invalid relay configurations
- [ ] Handle empty relay list errors
- [ ] Validate relay numbers are within 1-16 range

### Testing & Validation

#### Unit Tests
- [ ] Test relay list parsing (comma-separated, ranges, mixed)
- [ ] Test PANELX response parsing
- [ ] Test firmware version detection
- [ ] Test backward compatibility with v2.3 responses
- [ ] Test selective testing logic

#### Integration Tests
- [ ] Test firmware with 8-relay SKUs using TX:1-8
- [ ] Test firmware with new SKUs (>8 relays)
- [ ] Test GUI with various relay configurations
- [ ] Test performance improvements with selective testing
- [ ] Verify TX:ALL works for 16 relays

#### Hardware Tests
- [ ] Verify button works on new pin (A4)
- [ ] Test all 16 relay outputs
- [ ] Verify current draw with multiple relays
- [ ] Test with actual SMT panels

### Documentation

- [ ] Update main SMT testing documentation
- [ ] Create migration guide for existing installations
- [ ] Document new SKU relay_mapping format
- [ ] Add troubleshooting guide for common issues
- [ ] Update API documentation for new methods

### Deployment

- [ ] Create firmware update procedure
- [ ] Plan rollout strategy (pilot → production)
- [ ] Create rollback plan if issues arise
- [ ] Prepare training materials for operators

## Timeline Estimate

- **Phase 1**: 2-3 days (Core functionality)
- **Phase 2**: 1-2 days (Test logic)
- **Phase 3**: 1 day (GUI updates)
- **Phase 4**: 1 day (SKU system)
- **Phase 5**: 1-2 days (Error handling)
- **Testing**: 2-3 days
- **Documentation**: 1-2 days

**Total**: 10-15 days

## Risk Mitigation

1. **Clean Break**: No backward compatibility reduces complexity
2. **Coordinated Rollout**: Update all systems together
3. **Simple Protocol**: Single TX command for all testing
4. **Clear Errors**: Users get clear error messages

## Success Criteria

- [ ] All systems updated to use TX command
- [ ] 16-relay systems can test selectively
- [ ] Test time reduced for SKUs using <16 relays
- [ ] Simple, consistent command interface
- [ ] Clear error messages for invalid configurations