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

### ✅ Phase 2.1 - CRC-16 Implementation (COMPLETED)
- Created CRC-16 module with CCITT polynomial (0x1021)
- Integrated CRC validation into SerialManager for message integrity
- Updated SMT Arduino firmware to v5.1.0 with CRC-16 support
- Updated Offroad Arduino firmware to v4.1.0 with CRC-16 support  
- Added firmware version detection and CRC capability negotiation
- Implemented retry mechanism with exponential backoff for CRC failures
- Created comprehensive CRC test suite with performance benchmarks
- Files: `src/utils/crc16.py`, `test_phase2_crc_verification.py`

### ✅ Phase 3 - Binary Framing Protocol (COMPLETED)
- Implemented binary framing protocol with STX/ETX markers
- Created frame encoder with escape sequence handling for special characters
- Implemented state machine parser with timeout recovery
- Added CRC-16 validation for frame integrity
- Updated SMT Arduino firmware to v5.2.0 with framing support
- Updated Offroad Arduino firmware to v4.2.0 with basic framing support
- Integrated framing protocol into SerialManager
- Added framing capabilities to SMT Arduino controller
- Created comprehensive Phase 3 verification test suite
- Files: `test_phase3_verification.py` (deprecated)

### ✅ Phase 4.4 - Binary Protocol Implementation (COMPLETED)
- Designed comprehensive binary message schemas for all command types
- Implemented efficient binary message serialization with custom format optimized for Arduino
- Created binary message encoder/decoder classes with CRC-16 validation
- Developed full binary protocol implementation with async communication support
- Updated Arduino firmware to v5.3.0 with complete binary protocol support
- Added automatic protocol detection (text, framed, binary) in Arduino firmware
- Memory optimized implementation for UNO R4 WiFi constraints (32KB SRAM, 256KB Flash)
- Comprehensive binary message format verification test suite
- Performance benchmarking showing 38.5% bandwidth savings for group operations
- Excellent memory efficiency (under 100KB for 1000 messages)
- Files: `Arduino_firmware/SMT_Board_Tester_Binary_v5.3.0.ino` (deprecated)

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

# Phase 2.1 CRC verification tests (unit tests with mocks)
python test_phase2_crc_verification.py

# Phase 3 binary framing verification tests (unit tests with mocks)
python test_phase3_verification.py

# Phase 3 basic framing test (simple integration test)
python test_phase3_basic.py

# Phase 4.4 binary protocol verification tests (unit tests with mocks)
python test_phase4_4_verification.py

# Phase 4.4 basic functionality test (simple verification)
python test_phase4_4_basic.py

# Phase 4.4 performance benchmark (binary vs text protocol)
python test_phase4_4_performance_benchmark.py

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