# Offroad to SMT-Style Communication Migration TODO

## Overview
This document outlines the remaining tasks to complete the migration of Offroad testing to SMT-style communication. The Arduino firmware has been updated to support both old and new command styles for backward compatibility.

## Arduino Firmware Changes (COMPLETED ✓)
- [x] Added SMT-style short commands (TF, TP, TR, TD, X, V, B, S, I)
- [x] Implemented reliability packet format with SEQ, CHK, END
- [x] Updated response formats to be more compact and structured
- [x] Changed button events from INFO: to EVENT: format
- [x] Maintained backward compatibility with old commands
- [x] Added checksum calculation and verification
- [x] Implemented sequence number tracking

## Python Controller Updates (TODO)

### Phase 1: Testing Infrastructure
- [ ] Create test harness to verify Arduino firmware changes
  - [ ] Test all new short commands (TF, TP, TR, TD, etc.)
  - [ ] Verify reliability packet format parsing
  - [ ] Test checksum calculation and verification
  - [ ] Verify sequence number handling
  - [ ] Test backward compatibility with old commands

### Phase 2: Create Adapter Layer
- [ ] Create `OffroadSMTAdapter` class that extends `SMTArduinoController`
  - [ ] Override `_send_command()` to support reliability format
  - [ ] Add sequence number generation and tracking
  - [ ] Implement checksum calculation
  - [ ] Add response parsing for new compact formats

### Phase 3: Response Parsing Updates
- [ ] Update response parsers for new formats:
  - [ ] `TESTF:MAIN=v,i,lux,x,y;BACK=v,i,lux,x,y` (Function Test)
  - [ ] `PRESSURE:initial,delta` (Pressure Test)
  - [ ] `DUAL:B1=v,i,lux,x,y;B2=v,i,lux,x,y` (Dual Backlight)
  - [ ] `POWER:MAIN=v,i;BACK=v,i` (Power Test)
  - [ ] Handle EVENT: messages instead of INFO:

### Phase 4: Special Handling for Pressure Test
- [ ] Implement live data streaming for pressure test
  - [ ] Keep existing `LIVE:PSI=` format during test
  - [ ] Add callback mechanism for live pressure updates
  - [ ] Ensure streaming only active during WAIT phase

### Phase 5: Integration Testing
- [ ] Test with existing Offroad GUI
  - [ ] Verify all test types work correctly
  - [ ] Check button event handling
  - [ ] Validate live data streaming
  - [ ] Test error handling and recovery

### Phase 6: Performance Optimization
- [ ] Benchmark communication speed improvements
- [ ] Optimize parsing for new compact formats
- [ ] Reduce latency in command-response cycles

### Phase 7: Documentation
- [ ] Update API documentation for new command format
- [ ] Create migration guide for existing users
- [ ] Document reliability packet format
- [ ] Add troubleshooting guide

### Phase 8: Gradual Rollout
- [ ] Deploy to test environment
- [ ] Run parallel testing (old vs new)
- [ ] Monitor for any issues
- [ ] Create rollback plan if needed

## Command Mapping Reference

### SMT-Style Commands
| Old Command | New Command | Description |
|------------|-------------|-------------|
| TEST:FUNCTION_TEST | TF | Run function test |
| TEST:PRESSURE | TP | Run pressure test |
| TEST:RGBW_BACKLIGHT | TR | Run RGBW test |
| TEST:DUAL_BACKLIGHT | TD | Run dual backlight test |
| SENSOR_CHECK | S | Check sensors |
| STREAM:ON | M:1 | Enable monitoring |
| STREAM:OFF | M:0 | Disable monitoring |
| (none) | X | All relays off |
| (none) | V | Get voltage |
| (none) | B | Get button status |
| ID/PING | I | Identify |

### Response Format Changes
| Test Type | Old Format | New Format |
|-----------|------------|------------|
| Function | RESULT:MV_MAIN=12.5,MI_MAIN=1.2,... | TESTF:MAIN=12.5,1.2,2500,0.45,0.41;BACK=... |
| Pressure | RESULT:INITIAL=14.5,DELTA=0.25 | PRESSURE:14.5,0.25 |
| Dual | RESULT:MV_BACK1=12.5,MI_BACK1=1.2,... | DUAL:B1=12.5,1.2,2500,0.45,0.41;B2=... |
| Button | INFO:BUTTON_PRESSED | EVENT:BUTTON_PRESSED |

### Reliability Packet Format
```
Command:  CMD:SEQ=1234:CHK=A7
Response: DATA:SEQ=1234:...:CHK=B3:END
```

## Testing Checklist
- [ ] All commands work with and without reliability format
- [ ] Checksums are calculated and verified correctly
- [ ] Sequence numbers are tracked properly
- [ ] Backward compatibility maintained
- [ ] Error handling works for corrupted messages
- [ ] Performance meets or exceeds current system
- [ ] Live streaming works for pressure test
- [ ] Button events are properly handled

## Success Criteria
1. All existing functionality works with new command format
2. Communication is more reliable (checksums, sequences)
3. Responses are more compact and faster to parse
4. System maintains backward compatibility
5. Code is cleaner and more maintainable

## Notes
- Arduino firmware supports both old and new commands during transition
- Priority is maintaining system stability during migration
- Focus on incremental changes that can be rolled back if needed
- Keep SMT and Offroad controllers separate until fully tested