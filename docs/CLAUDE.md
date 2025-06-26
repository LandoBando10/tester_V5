# Claude Code Assistant Configuration

## Project: Tester V5 Communication Protocol Migration

## Phase 1 Implementation Status

### ✅ Phase 1.1 - Individual Commands (COMPLETED)
- Implemented `measure_relays()` method using individual MEASURE commands
- Updated `send_measure_group()` to use individual commands internally
- Eliminates buffer overflow risks completely
- Each response ~30 characters (well under 512 byte limit)
- Location: `src/hardware/smt_arduino_controller.py`

### ✅ Phase 1.2 - Command Throttling (COMPLETED)  
- Added 50ms minimum interval between commands
- Implemented `_throttle_command()` method
- Prevents overwhelming Arduino serial buffer
- Location: `src/hardware/smt_arduino_controller.py`

### ✅ Phase 1.3 - Thread Safety (COMPLETED)
- Qt signal connections already properly implemented for all GUI updates
- Button callback thread safety already working correctly via signals
- All Arduino callbacks use Qt.QueuedConnection for thread-safe GUI updates
- Location: `src/gui/handlers/smt_handler.py`, `src/gui/workers/smt_worker.py`

### ✅ Phase 1.4 - Verification Tests (COMPLETED)
- Created comprehensive test suite with 10 verification tests
- Performance benchmarks for latency, throughput, and success rates
- Hardware testing script for real Arduino validation
- Files: `test_phase1_verification.py`, `test_phase1_hardware_benchmark.py`

### ✅ Phase 2.1 - CRC-16 Implementation (DEPRECATED AND REMOVED)
- Originally planned for data integrity verification
- Determined to be unnecessary for reliable USB serial communication
- All CRC-related code has been removed from the codebase

### ✅ Phase 3 - Binary Framing Protocol (DEPRECATED AND REMOVED)
- Originally planned for structured message passing
- Determined to be overly complex for the application needs
- Simple text-based communication proved sufficient
- All binary framing code has been removed from the codebase

### ✅ Phase 4.4 - Binary Protocol Implementation (DEPRECATED AND REMOVED)
- Originally planned for bandwidth optimization
- Performance testing showed minimal benefit over text protocol
- Added unnecessary complexity to firmware and Python code
- All binary protocol code has been removed from the codebase

### Testing Commands
```bash
# Python linting
python -m pylint src/

# Type checking
python -m mypy src/

# Run unit tests
python -m pytest tests/

# SMT communication test
python test_smt_communication.py

# Phase 1 verification tests (unit tests with mocks)
python test_phase1_verification.py

# Phase 1 hardware benchmark (requires Arduino)
python test_phase1_hardware_benchmark.py

# Note: CRC tests have been removed as this feature is deprecated

# Note: Binary framing tests have been removed as this feature is deprecated

# Note: Binary protocol tests have been removed as this feature is deprecated

# Phase 4.4 simple benchmark (no dependencies)
python test_phase4_4_simple_benchmark.py

# CRC-16 module self-test
python src/utils/crc16.py

# Run main application
python main.py

# Check serial ports
python -m serial.tools.list_ports
```

### Key Communication Files
- **SMT Controller**: `src/hardware/smt_arduino_controller.py` ✅ Phase 1.1/1.2 COMPLETED
- **SMT Handler**: `src/handlers/smt_handler.py`
- **Offroad Controller**: `src/controllers/offroad_arduino_controller.py`
- **Serial Manager**: `src/utils/serial_manager.py`
- **Resource Mixin**: `src/utils/resource_mixin.py`
- **Arduino SMT Firmware**: `Arduino_firmware/SMT_Board_Tester_with_Button.ino` (v5.0.1)
- **Arduino SMT Basic**: `Arduino_firmware/SMT_Board_Tester.ino` (v5.0.0)
- **Arduino Offroad Firmware**: `Arduino_firmware/Offroad_Assembly_Tester.ino` (v4)
- **Button Test Utility**: `Arduino_firmware/Button_Test.ino`

### Critical Constraints
- **Arduino UNO R4 WiFi**: 32KB SRAM, 256KB Flash
- **Serial Buffer**: 512 bytes (Arduino default)
- **Baud Rate**: 115200 (current standard)
- **Firmware Requirements**: Arduino firmware 5.1.0+ with timing configuration support
- **No backward compatibility** - requires modern Arduino firmware with CONFIG commands
- **GUI callbacks must use Qt signals** - no direct GUI updates from threads
- **Maximum relay count**: 16 for SMT boards

### Communication Protocol Details
- **Current**: Text-based, newline-terminated
- **Target**: Binary protocol with STX/ETX framing and CRC-16
- **Command format**: `COMMAND:PARAM1:PARAM2`
- **Response format**: `RESPONSE:DATA` or `ERROR:MESSAGE`

### Performance Targets
- **Command latency**: <100ms
- **Success rate**: >99.9%
- **Buffer overflow**: 0 occurrences
- **GUI responsiveness**: No freezes during communication

### Development Workflow
1. Make changes to implementation
2. Run linting: `python -m pylint <changed_file>`
3. Run type checking: `python -m mypy <changed_file>`
4. Test with simulator or hardware
5. Run full test suite before marking task complete

### Debugging Tools
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Monitor serial communication
# Set debug=True in SerialManager initialization
```

### Quick Reference Commands

#### SMT Arduino Commands
- `GET_BOARD_TYPE` - Returns board identifier
- `SHOW_ALL_RELAYS` - Display relay states
- `MEASURE_GROUP:relay1,relay2,...` - Measure multiple relays
- `START_TEST:relay:test_type` - Start relay test
- `STOP_TEST` - Stop current test

#### Offroad Arduino Commands
- `START_FORWARD` - Start forward test
- `STOP_FORWARD` - Stop forward test
- `GET_STATUS` - Get current status
- `SET_DUTY_CYCLE:value` - Set PWM duty cycle