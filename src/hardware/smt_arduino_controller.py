"""
SMT Arduino Controller - Specialized for SMT Panel Testing

PHASE 1 IMPLEMENTATION (December 2024):
- Removed MEASURE_GROUP command entirely - no backward compatibility
- Added measure_relays() method using individual MEASURE commands
- Eliminated buffer overflow risks by sending one command at a time
- Each measurement response ~30 characters (well under 512 byte limit)
- Added 50ms command throttling to prevent overwhelming Arduino
- Added serial buffer management and recovery logic
- Added 2-second minimum interval between tests

Key improvements:
- No more buffer overflows
- Simple, maintainable code
- Better error recovery (per-relay)
- Real-time progress capability
- Graceful degradation on failures

Modified: December 2024 - Phase 1.1/1.2 Clean implementation
"""

import time
import logging
import threading
import asyncio
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass
from .serial_manager import SerialManager
from src.utils.resource_manager import ResourceMixin
from queue import Queue, Empty


@dataclass
class SensorReading:
    """Container for sensor reading data"""
    timestamp: float
    sensor_type: str
    sensor_id: str
    value: float
    unit: str
    raw_data: str = ""


@dataclass
class MeasurementResult:
    """Container for SMT relay measurement results"""
    relay: int
    board: int
    voltage: float
    current: float
    power: float
    timestamp: float


@dataclass
class SensorConfig:
    """Configuration for a sensor - kept for compatibility"""
    sensor_type: str  # 'INA260' for SMT
    sensor_id: str  # Unique identifier
    read_interval_ms: int = 100
    enabled: bool = True


class SMTArduinoController(ResourceMixin):
    """Specialized Arduino controller for SMT panel testing with Phase 1 fixes"""

    def __init__(self, baud_rate: int = 115200, enable_framing: bool = False, enable_binary: bool = False):
        super().__init__()  # Initialize ResourceMixin
        # Start with CRC disabled - will auto-detect during connection
        self.serial = SerialManager(baud_rate=baud_rate, enable_crc=False, enable_framing=enable_framing)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.framing_enabled = enable_framing
        self.binary_enabled = enable_binary

        # Sensor management
        self.sensors: Dict[str, SensorConfig] = {}
        self.readings: List[SensorReading] = []
        self.max_readings = 1000  # Reduced for SMT (less data needed)

        # Reading control
        self.is_reading = False
        self.reading_thread: Optional[threading.Thread] = None
        self.reading_lock = threading.Lock()

        # Callbacks
        self.button_callback: Optional[Callable[[str], None]] = None  # Button state callback

        # Command queue for sending commands during reading loop
        self.command_queue: Queue = Queue()
        self.response_lock = threading.Lock()
        
        # Health monitoring (PHASE 1)
        self.last_command_time = 0
        self.consecutive_errors = 0
        self.max_consecutive_errors = 3
        
        # Test timing control (PHASE 1)
        self.last_test_end_time = 0
        self.min_test_interval = 2.0  # Minimum seconds between tests
        
        
        # Command throttling (PHASE 1.2)
        self.min_command_interval = 0.05  # 50ms minimum between commands
        
        # CRC-16 support (Phase 2.1)
        self.crc_supported = False
        self.crc_enabled = False
        self.firmware_version = None
        
        # Binary protocol support (Phase 4.4)
        self.binary_protocol = None
        self.binary_supported = False
        if enable_binary:
            self._initialize_binary_protocol()

    def _detect_crc_capability(self) -> bool:
        """Detect if Arduino firmware supports CRC-16 validation (Phase 2.1)"""
        try:
            # Query firmware version to check for CRC support
            response = self.serial.query("VERSION", response_timeout=2.0)
            if response:
                self.firmware_version = response
                # Check if version indicates CRC support
                if "CRC16_SUPPORT" in response or "5.1.0" in response:
                    self.crc_supported = True
                    self.logger.info(f"Arduino firmware supports CRC-16: {response}")
                    
                    # Test CRC functionality with a simple command
                    test_response = self.serial.query("CRC:STATUS", response_timeout=2.0)
                    if test_response and "CRC_ENABLED" in test_response:
                        self.logger.info("CRC-16 functionality verified")
                        return True
                else:
                    self.crc_supported = False
                    self.logger.info(f"Arduino firmware does not support CRC-16: {response}")
            
            return self.crc_supported
            
        except Exception as e:
            self.logger.error(f"Error detecting CRC capability: {e}")
            self.crc_supported = False
            return False
    
    def enable_crc_validation(self, enable: bool = True) -> bool:
        """Enable or disable CRC-16 validation if supported (Phase 2.1)"""
        if not self.crc_supported:
            self.logger.warning("CRC-16 not supported by Arduino firmware")
            return False
        
        # Track if reading loop was active
        was_reading = False
        
        try:
            # Temporarily stop reading loop if active to prevent response consumption
            was_reading = self.is_reading
            if was_reading:
                self.logger.debug("Temporarily stopping reading loop for CRC configuration")
                self.stop_reading()
                time.sleep(0.1)  # Let reading loop finish
            else:
                self.logger.debug("No reading loop active during CRC configuration")
            
            # Clear buffers before sending command
            self.serial.flush_buffers()
            
            # Enable CRC on Arduino side
            command = "CRC:ENABLE" if enable else "CRC:DISABLE"
            response = self.serial.query(command, response_timeout=2.0)
            
            if response and ("CRC_ENABLED" in response or "CRC_DISABLED" in response):
                # Enable CRC on Python side
                self.serial.enable_crc(enable)
                self.crc_enabled = enable
                self.logger.info(f"CRC-16 validation {'enabled' if enable else 'disabled'}")
                success = True
            else:
                self.logger.error(f"Failed to set CRC mode: {response}")
                success = False
            
            # Restart reading loop if it was active
            if was_reading:
                self.logger.debug("Restarting reading loop after CRC configuration")
                self.start_reading()
            
            return success
                
        except Exception as e:
            self.logger.error(f"Error setting CRC mode: {e}")
            # Restart reading loop on error if it was active
            if was_reading:
                self.start_reading()
            return False
    
    def get_crc_statistics(self) -> dict:
        """Get CRC error statistics from both Arduino and Python sides (Phase 2.1)"""
        stats = {
            'crc_supported': self.crc_supported,
            'crc_enabled': self.crc_enabled,
            'firmware_version': self.firmware_version,
            'python_stats': {},
            'arduino_stats': {}
        }
        
        # Get Python-side statistics
        if self.serial.crc_enabled:
            stats['python_stats'] = self.serial.get_crc_statistics()
        
        # Get Arduino-side statistics
        if self.crc_supported:
            try:
                response = self.serial.query("CRC:STATUS", response_timeout=2.0)
                if response:
                    # Parse Arduino CRC status response
                    # Format: CRC_ENABLED:TRUE,TOTAL_MESSAGES:123,CRC_ERRORS:1,ERROR_RATE:0.81%
                    arduino_stats = {}
                    for pair in response.split(','):
                        if ':' in pair:
                            key, value = pair.split(':', 1)
                            arduino_stats[key.lower()] = value
                    stats['arduino_stats'] = arduino_stats
            except Exception as e:
                self.logger.error(f"Error getting Arduino CRC statistics: {e}")
        
        return stats
    
    def is_crc_enabled(self) -> bool:
        """Check if CRC is currently enabled"""
        return self.crc_enabled

    def connect(self, port: str) -> bool:
        """Connect to Arduino on specified port with enhanced recovery"""
        if self.serial.connect(port):
            # PHASE 1: Clear buffers immediately
            self.serial.flush_buffers()
            time.sleep(0.1)  # Small delay for Arduino to stabilize
            
            # Test communication
            if self.test_communication():
                self.logger.info(f"SMT Arduino connected successfully on {port}")
                self.consecutive_errors = 0
                return True
            else:
                self.logger.error("Arduino connected but communication test failed")
                self.serial.disconnect()
                return False
        return False

    def disconnect(self):
        """Disconnect from Arduino with proper cleanup"""
        self.stop_reading()
        
        # PHASE 1: Turn off all relays individually before disconnecting
        if self.is_connected():
            try:
                for relay in range(1, 9):  # Turn off relays 1-8
                    self.send_command(f"RELAY:{relay}:OFF", timeout=0.5)
                time.sleep(0.1)
            except:
                pass
        
        # Clear command queue
        while not self.command_queue.empty():
            try:
                self.command_queue.get_nowait()
            except Empty:
                break
                
        self.serial.disconnect()
        self.cleanup_resources()  # Clean up all tracked resources

    def test_communication(self) -> bool:
        """Test if Arduino is responding - enhanced for SMT with CRC capability detection"""
        try:
            # Clear any pending data
            self.serial.flush_buffers()

            # Try multiple times with different commands
            for attempt in range(3):
                # Send identification command
                response = self.serial.query("ID", response_timeout=3.0)
                if response and ("SMT" in response.upper() or "DIODE_DYNAMICS" in response.upper()):
                    self.logger.debug(f"Arduino identification: {response}")
                    
                    # Test CRC capability detection (Phase 2.1)
                    self._detect_crc_capability()
                    return True

                # Try STATUS command
                response = self.serial.query("STATUS", response_timeout=2.0)
                if response and "RELAYS:" in response:
                    self.logger.debug(f"Arduino status: {response}")
                    
                    # Test CRC capability detection (Phase 2.1)
                    self._detect_crc_capability()
                    return True
                
                time.sleep(0.5)

            return False

        except Exception as e:
            self.logger.error(f"Communication test error: {e}")
            return False

    def verify_arduino_responsive(self) -> bool:
        """PHASE 1: Verify Arduino is still responsive before operations"""
        try:
            response = self.send_command("STATUS", timeout=2.0)
            return response is not None and "RELAYS:" in str(response)
        except:
            return False

    def configure_sensors(self, sensor_configs: List[SensorConfig]) -> bool:
        """Initialize Arduino sensors for SMT testing"""
        try:
            # Store sensor configs locally
            self.sensors.clear()
            for sensor in sensor_configs:
                self.sensors[sensor.sensor_id] = sensor

            # Check sensor status
            self.logger.info("Checking Arduino sensor status...")
            status_response = self.serial.query("STATUS", response_timeout=3.0)
            if status_response:
                self.logger.info(f"Arduino status: {status_response}")
            
            # Run sensor check
            self.logger.info("Running sensor check...")
            response = self.serial.query("SENSOR_CHECK", response_timeout=10.0)
            if response and (response.startswith("OK:") or response.startswith("WARNING:")):
                self.logger.info(f"Arduino sensors initialized: {response}")
                return True
            else:
                self.logger.error(f"Arduino sensor check failed: {response}")
                return False

        except Exception as e:
            self.logger.error(f"Error configuring sensors: {e}")
            return False

    def start_reading(self, callback: Optional[Callable[[SensorReading], None]] = None):
        """Start reading loop for button events"""
        if self.is_reading:
            self.logger.warning("Already reading")
            return

        self.is_reading = True

        # Start reading thread with resource tracking
        self.reading_thread = threading.Thread(target=self._reading_loop, daemon=True)
        thread_id = self.register_thread(self.reading_thread, "smt_arduino_reading")
        self.reading_thread.start()

        self.logger.info("Started SMT reading loop for button events")

    def stop_reading(self):
        """Stop reading loop"""
        if not self.is_reading:
            return

        self.is_reading = False

        # Wait for reading thread to finish
        if self.reading_thread and self.reading_thread.is_alive():
            self.reading_thread.join(timeout=2.0)  # Reduced timeout for faster response
            if self.reading_thread.is_alive():
                self.logger.warning("Reading thread did not terminate gracefully")
        
        # Clear command queue
        while not self.command_queue.empty():
            try:
                self.command_queue.get_nowait()
            except Empty:
                break

        self.logger.info("Stopped SMT reading loop")

    def _reading_loop(self):
        """Main reading loop with PHASE 1 improvements"""
        consecutive_errors = 0
        
        while self.is_reading:
            try:
                # PHASE 1: Monitor command queue depth
                queue_depth = self.command_queue.qsize()
                if queue_depth > 10:
                    self.logger.warning(f"Command queue depth high: {queue_depth}")
                    # Clear old commands
                    while self.command_queue.qsize() > 5:
                        try:
                            self.command_queue.get_nowait()
                        except Empty:
                            break
                
                # Check for queued commands first
                try:
                    command_data = self.command_queue.get_nowait()
                    self._process_queued_command(command_data)
                    consecutive_errors = 0  # Reset on success
                except Empty:
                    pass
                
                # Read line from Arduino
                line = self.serial.read_line(timeout=0.1)
                if line:
                    self._process_arduino_message(line.strip())
                    consecutive_errors = 0  # Reset on success
                
                # PHASE 1: Monitor serial buffer health
                if self.serial.is_connected() and hasattr(self.serial.connection, 'in_waiting'):
                    if self.serial.connection.in_waiting > 1000:
                        self.logger.warning(f"Serial input buffer getting full: {self.serial.connection.in_waiting} bytes")
                        self.serial.flush_buffers()

            except Exception as e:
                self.logger.error(f"Reading loop error: {e}")
                consecutive_errors += 1
                
                # PHASE 1: Recovery after multiple errors
                if consecutive_errors >= self.max_consecutive_errors:
                    self.logger.error(f"Too many consecutive errors ({consecutive_errors}) - attempting recovery")
                    try:
                        self.serial.flush_buffers()
                        time.sleep(1.0)
                        consecutive_errors = 0
                    except:
                        pass
                
                time.sleep(0.1)

    def _process_queued_command(self, command_data: Dict):
        """Process a command from the queue"""
        command = command_data['command']
        response_queue = command_data['response_queue']
        timeout = command_data.get('timeout', 2.0)
        
        # Clear input buffer if it's getting full
        if self.serial.connection.in_waiting > 100:
            self.serial.flush_buffers()
            time.sleep(0.05)  # Small delay for buffer to clear
        
        # Send command
        if not self.serial.write(command + '\r\n'):
            response_queue.put(None)
            return
            
        # Normal command handling
        self._handle_normal_command_response(command, response_queue, timeout)


    def _handle_normal_command_response(self, command: str, response_queue: Queue, timeout: float):
        """Handle response for normal commands"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            line = self.serial.read_line(timeout=0.1)
            if line:
                line = line.strip()
                if self._is_command_response(command, line):
                    response_queue.put(line)
                    return
                else:
                    # Process other messages normally
                    self._process_arduino_message(line)
            
            # Small delay to prevent busy waiting
            time.sleep(0.001)
        
        # Timeout
        response_queue.put(None)
    
    def _is_command_response(self, command: str, line: str) -> bool:
        """Check if a line is a response to a specific command"""
        cmd = command.strip().upper()
        resp = line.strip().upper()
        
        # SMT-specific response patterns
        if cmd == "ID":
            return "SMT" in resp or "DIODE_DYNAMICS" in resp
        elif cmd == "STATUS":
            return resp.startswith("DATA:RELAYS:") or resp.startswith("STATUS:") or "RELAYS:" in resp
        elif cmd.startswith("RELAY"):
            return resp.startswith("OK:RELAY") or resp.startswith("ERROR:RELAY") or resp.startswith("ERR:")
        elif cmd == "RESET":
            return resp.startswith("OK:RESET") or resp == "RESET"
        elif cmd == "SENSOR_CHECK":
            return resp.startswith("OK:SENSOR") or resp.startswith("WARNING:SENSOR")
        elif cmd == "CRC:ENABLE":
            return resp == "CRC_ENABLED"
        elif cmd == "CRC:DISABLE":
            return resp == "CRC_DISABLED"
        elif cmd == "CRC:STATUS":
            return resp.startswith("CRC_ENABLED:") or resp == "CRC_ENABLED:FALSE"
        elif cmd == "VERSION":
            return "VERSION:" in resp
        elif cmd.startswith("MEASURE:"):
            return resp.startswith("MEASUREMENT:") or resp.startswith("ERR:")
        else:
            # Generic OK/ERROR responses
            return resp.startswith("OK:") or resp.startswith("ERROR:") or resp.startswith("ERR:")

    def _process_arduino_message(self, line: str):
        """Process Arduino messages - simplified for SMT"""
        try:
            # Handle button messages (most important for SMT)
            if line.startswith("DATA:BUTTON:"):
                button_state = line[12:].strip()
                self.logger.info(f"Button event: {button_state}")
                if self.button_callback:
                    try:
                        self.button_callback(button_state)
                    except Exception as e:
                        self.logger.error(f"Button callback error: {e}")
            
            # Log other message types
            elif line.startswith("ERROR:"):
                self.logger.error(f"Arduino error: {line}")
                self.consecutive_errors += 1
            elif line.startswith("INFO:"):
                self.logger.info(f"Arduino info: {line}")
            elif line.startswith("DEBUG:"):
                self.logger.debug(f"Arduino debug: {line}")
            elif line.startswith("STATUS:"):
                self.logger.debug(f"Arduino status: {line}")
            else:
                if line and not line.startswith("==="):
                    self.logger.debug(f"Arduino message: {line}")

        except Exception as e:
            self.logger.error(f"Error processing Arduino message '{line}': {e}")

    def _throttle_command(self):
        """Ensure minimum time between commands (Phase 1.2)"""
        elapsed = time.time() - self.last_command_time
        if elapsed < self.min_command_interval:
            time.sleep(self.min_command_interval - elapsed)
        self.last_command_time = time.time()

    def send_command(self, command: str, timeout: float = 2.0) -> Optional[str]:
        """Send command with PHASE 1 improvements including throttling"""
        # Apply command throttling
        self._throttle_command()
        
        # If reading loop is active, use command queue
        if self.is_reading and self.reading_thread and self.reading_thread.is_alive():
            response_queue = Queue()
            command_data = {
                'command': command,
                'response_queue': response_queue,
                'timeout': timeout
            }
            
            # Add command to queue
            self.command_queue.put(command_data)
            
            # Wait for response
            try:
                response = response_queue.get(timeout=timeout + 0.5)
                return response
            except Empty:
                self.logger.warning(f"Timeout waiting for response to command: {command}")
                self.consecutive_errors += 1
                return None
        else:
            # Normal query when reading loop is not active
            return self.serial.query(command, response_timeout=timeout)

    def measure_relays(self, relay_list: List[int], timeout: float = 2.0) -> Dict[int, Dict[str, float]]:
        """
        Measure multiple relays using individual commands.
        Returns dict of relay_number -> measurement results.
        
        This replaces the complex MEASURE_GROUP approach with simple, reliable individual measurements.
        Phase 1.1 implementation - eliminates buffer overflow risks.
        """
        results = {}
        
        for relay in relay_list:
            try:
                # Turn off all relays first (using individual commands)
                for r in range(1, 9):  # Turn off relays 1-8
                    self.send_command(f"RELAY:{r}:OFF", timeout=0.5)
                time.sleep(0.05)  # Small delay for relay settling
                
                # Turn on specific relay
                relay_cmd = f"RELAY:{relay}:ON"
                relay_response = self.send_command(relay_cmd, timeout=1.0)
                if not relay_response or "ERROR" in relay_response:
                    self.logger.error(f"Failed to turn on relay {relay}")
                    results[relay] = None
                    continue
                
                # Small delay for relay to stabilize
                time.sleep(0.1)
                
                # Send simple MEASURE command
                command = f"MEASURE:{relay}"
                response = self.send_command(command, timeout=timeout)
                
                if response and not response.startswith("ERROR:"):
                    # Parse response format: "MEASUREMENT:1:V=12.500,I=0.450,P=5.625"
                    if response.startswith("MEASUREMENT:"):
                        parts = response.split(':', 2)  # Split into 3 parts max
                        if len(parts) >= 3:
                            # Parse the measurement data
                            data_part = parts[2]  # "V=12.500,I=0.450,P=5.625"
                            measurements = {}
                            
                            for item in data_part.split(','):
                                if '=' in item:
                                    key, value = item.split('=', 1)
                                    try:
                                        if key == 'V':
                                            measurements['voltage'] = float(value)
                                        elif key == 'I':
                                            measurements['current'] = float(value)
                                        elif key == 'P':
                                            measurements['power'] = float(value)
                                    except ValueError:
                                        self.logger.error(f"Failed to parse {key}={value}")
                            
                            if 'voltage' in measurements and 'current' in measurements and 'power' in measurements:
                                results[relay] = measurements
                                self.logger.debug(f"Relay {relay} measured: V={measurements['voltage']:.3f}, I={measurements['current']:.3f}, P={measurements['power']:.3f}")
                            else:
                                self.logger.error(f"Incomplete measurements for relay {relay}: {measurements}")
                                results[relay] = None
                        else:
                            self.logger.error(f"Invalid response format for relay {relay}: {response}")
                            results[relay] = None
                    else:
                        self.logger.error(f"Unexpected response format for relay {relay}: {response}")
                        results[relay] = None
                else:
                    self.logger.error(f"Measurement failed for relay {relay}: {response}")
                    results[relay] = None
                
                # Turn off relay after measurement
                self.send_command(f"RELAY:{relay}:OFF", timeout=1.0)
                
            except Exception as e:
                self.logger.error(f"Error measuring relay {relay}: {e}")
                results[relay] = None
            
            # Small delay between measurements (Arduino needs time to settle)
            if relay != relay_list[-1]:  # Don't delay after last relay
                time.sleep(0.05)
        
        # Ensure all relays are off after measurements (using individual commands)
        for relay in range(1, 9):  # Turn off relays 1-8
            self.send_command(f"RELAY:{relay}:OFF", timeout=0.5)
        
        return results


    def enforce_test_cooldown(self) -> bool:
        """PHASE 1: Enforce minimum interval between tests"""
        current_time = time.time()
        elapsed = current_time - self.last_test_end_time
        
        if elapsed < self.min_test_interval:
            wait_time = self.min_test_interval - elapsed
            self.logger.info(f"Enforcing {wait_time:.1f}s cooldown between tests")
            time.sleep(wait_time)
            return True
        return False

    def mark_test_complete(self):
        """PHASE 1: Mark test as complete for cooldown tracking"""
        self.last_test_end_time = time.time()
        # Always turn off relays after test (using individual commands)
        for relay in range(1, 9):  # Turn off relays 1-8
            self.send_command(f"RELAY:{relay}:OFF", timeout=0.5)

    def recover_communication(self) -> bool:
        """PHASE 1: Attempt to recover communication with Arduino"""
        try:
            self.logger.info("Attempting Arduino communication recovery")
            
            # 1. Flush buffers
            self.serial.flush_buffers()
            
            # 2. Send reset signal
            self.serial.write(b"\x03")  # Ctrl+C
            time.sleep(0.1)
            
            # 3. Clear any pending data
            if hasattr(self.serial.connection, 'reset_input_buffer'):
                self.serial.connection.reset_input_buffer()
            
            # 4. Test communication
            for attempt in range(3):
                response = self.send_command("ID", timeout=2.0)
                if response and ("SMT" in response or "DIODE" in response):
                    self.logger.info("Arduino communication recovered successfully")
                    self.consecutive_errors = 0
                    return True
                time.sleep(0.5)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error during Arduino recovery: {e}")
            return False

    def is_connected(self) -> bool:
        """Check if Arduino is connected"""
        return self.serial.is_connected()
    
    def set_button_callback(self, callback: Optional[Callable[[str], None]]):
        """Set callback for button state changes"""
        self.button_callback = callback
    
    # Binary framing support (Phase 3)
    
    def enable_framing(self, enabled: bool = True) -> bool:
        """Enable binary framing protocol"""
        try:
            self.framing_enabled = enabled
            self.serial.enable_framing(enabled)
            
            if enabled:
                # Try to enable framing on the Arduino
                response = self.send_command("FRAME:ENABLE")
                if response and "FRAMING_ENABLED" in response:
                    self.logger.info("Binary framing enabled successfully")
                    return True
                else:
                    self.logger.warning("Arduino did not confirm framing support")
                    return False
            else:
                # Disable framing
                response = self.send_command("FRAME:DISABLE")
                self.logger.info("Binary framing disabled")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to enable framing: {e}")
            return False
    
    def test_framing(self, test_data: str = "TEST123") -> bool:
        """Test binary framing protocol"""
        if not self.framing_enabled:
            self.logger.error("Framing not enabled")
            return False
            
        try:
            response = self.send_command(f"FRAME:TEST:{test_data}")
            if response and "FRAME_TEST:SUCCESS" in response:
                self.logger.info("Frame test successful")
                return True
            else:
                self.logger.error(f"Frame test failed: {response}")
                return False
                
        except Exception as e:
            self.logger.error(f"Frame test error: {e}")
            return False
    
    def get_framing_statistics(self) -> Dict[str, Any]:
        """Get framing protocol statistics"""
        stats = self.serial.get_frame_statistics()
        stats['controller_framing_enabled'] = self.framing_enabled
        return stats
    
    def get_health_status(self) -> Dict[str, Any]:
        """PHASE 1: Get health status of the controller"""
        return {
            "connected": self.is_connected(),
            "reading": self.is_reading,
            "consecutive_errors": self.consecutive_errors,
            "command_queue_depth": self.command_queue.qsize(),
            "time_since_last_command": time.time() - self.last_command_time if self.last_command_time > 0 else None,
            "time_since_last_test": time.time() - self.last_test_end_time if self.last_test_end_time > 0 else None
        }

    # Binary protocol methods (Phase 4.4)
    
    def _initialize_binary_protocol(self):
        """Initialize binary protocol support"""
        try:
            from src.protocols.binary_protocol import BinaryProtocol, BinaryProtocolConfig
            from src.protocols.base_protocol import DeviceType
            
            config = BinaryProtocolConfig()
            config.enable_compression = False  # Disabled for Arduino compatibility
            config.max_retries = 3
            config.response_timeout = 5.0
            
            self.binary_protocol = BinaryProtocol(
                device_type=DeviceType.SMT_TESTER,
                device_id="SMT_Arduino",
                serial_manager=self.serial,
                config=config
            )
            
            self.logger.info("Binary protocol initialized")
            
        except ImportError as e:
            self.logger.error(f"Failed to import binary protocol: {e}")
            self.binary_enabled = False
        except Exception as e:
            self.logger.error(f"Failed to initialize binary protocol: {e}")
            self.binary_enabled = False

    async def connect_binary(self, port: str) -> bool:
        """Connect using binary protocol"""
        if not self.binary_enabled or not self.binary_protocol:
            self.logger.error("Binary protocol not enabled or initialized")
            return False
        
        try:
            connection_params = {
                'port': port,
                'baud_rate': self.serial.baud_rate
            }
            
            success = await self.binary_protocol.connect(connection_params)
            if success:
                self.binary_supported = True
                self.logger.info(f"Connected to {port} using binary protocol")
                return True
            else:
                self.logger.error("Binary protocol connection failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Binary protocol connection error: {e}")
            return False

    async def measure_relays_binary(self, relay_list: List[int], timeout: float = 2.0) -> Dict[int, Dict[str, float]]:
        """
        Measure multiple relays using binary protocol.
        More efficient than text-based commands.
        """
        if not self.binary_supported or not self.binary_protocol:
            self.logger.error("Binary protocol not supported or initialized")
            return {}
        
        results = {}
        
        try:
            from src.protocols.base_protocol import CommandRequest, CommandType, TestType
            
            for relay in relay_list:
                try:
                    # Create measurement request
                    request = CommandRequest(
                        command_type=CommandType.MEASURE,
                        device_id="SMT_Arduino",
                        parameters={
                            'relay_id': relay,
                            'test_type': 'voltage_current'
                        },
                        timeout_seconds=timeout
                    )
                    
                    # Send command using binary protocol
                    response = await self.binary_protocol.send_command(request)
                    
                    if response.success and response.data:
                        measurements = {
                            'voltage': response.data.get('voltage', 0.0),
                            'current': response.data.get('current', 0.0),
                            'power': response.data.get('voltage', 0.0) * response.data.get('current', 0.0)
                        }
                        results[relay] = measurements
                        self.logger.debug(f"Binary measurement relay {relay}: V={measurements['voltage']:.3f}, I={measurements['current']:.3f}")
                    else:
                        self.logger.error(f"Binary measurement failed for relay {relay}: {response.error}")
                        results[relay] = None
                
                except Exception as e:
                    self.logger.error(f"Error in binary measurement for relay {relay}: {e}")
                    results[relay] = None
                
                # Small delay between measurements
                if relay != relay_list[-1]:
                    await asyncio.sleep(0.05)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Binary measurement error: {e}")
            return {}

    async def measure_group_binary(self, relay_list: List[int], timeout: float = 5.0) -> Dict[int, Dict[str, float]]:
        """
        Measure multiple relays as a group using binary protocol.
        More efficient for multiple measurements.
        """
        if not self.binary_supported or not self.binary_protocol:
            self.logger.error("Binary protocol not supported or initialized")
            return {}
        
        try:
            from src.protocols.base_protocol import CommandRequest, CommandType
            
            # Create group measurement request
            request = CommandRequest(
                command_type=CommandType.MEASURE_GROUP,
                device_id="SMT_Arduino",
                parameters={
                    'relay_ids': relay_list,
                    'test_type': 'voltage_current'
                },
                timeout_seconds=timeout
            )
            
            # Send group command using binary protocol
            response = await self.binary_protocol.send_command(request)
            
            results = {}
            
            if response.success and response.data and 'measurements' in response.data:
                for measurement in response.data['measurements']:
                    relay_id = measurement.get('relay_id')
                    if relay_id is not None:
                        results[relay_id] = {
                            'voltage': measurement.get('voltage', 0.0),
                            'current': measurement.get('current', 0.0),
                            'power': measurement.get('voltage', 0.0) * measurement.get('current', 0.0)
                        }
                        
                self.logger.debug(f"Binary group measurement completed for {len(results)} relays")
            else:
                self.logger.error(f"Binary group measurement failed: {response.error}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Binary group measurement error: {e}")
            return {}

    def enable_binary_protocol(self, enabled: bool = True) -> bool:
        """Enable or disable binary protocol"""
        if enabled and not self.binary_protocol:
            self._initialize_binary_protocol()
        
        self.binary_enabled = enabled
        self.logger.info(f"Binary protocol {'enabled' if enabled else 'disabled'}")
        return self.binary_enabled

    def test_binary_protocol(self) -> bool:
        """Test binary protocol connectivity"""
        if not self.binary_supported or not self.binary_protocol:
            return False
        
        try:
            # Run async test in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                from src.protocols.base_protocol import CommandRequest, CommandType
                
                request = CommandRequest(
                    command_type=CommandType.PING,
                    device_id="SMT_Arduino",
                    timeout_seconds=2.0
                )
                
                response = loop.run_until_complete(self.binary_protocol.send_command(request))
                
                if response.success:
                    self.logger.info("Binary protocol test successful")
                    return True
                else:
                    self.logger.error(f"Binary protocol test failed: {response.error}")
                    return False
                    
            finally:
                loop.close()
                
        except Exception as e:
            self.logger.error(f"Binary protocol test error: {e}")
            return False

    def get_binary_statistics(self) -> Dict[str, Any]:
        """Get binary protocol statistics"""
        if not self.binary_protocol:
            return {'binary_enabled': False}
        
        stats = self.binary_protocol.get_statistics()
        stats['binary_enabled'] = self.binary_enabled
        stats['binary_supported'] = self.binary_supported
        return stats

    def get_firmware_type(self) -> str:
        """Get the firmware type of connected Arduino"""
        try:
            response = self.send_command("ID", timeout=2.0)
            if response:
                response_upper = response.upper()
                if "SMT_TESTER" in response_upper or "SMT" in response_upper:
                    return "SMT"
                elif "OFFROAD" in response_upper:
                    return "OFFROAD"
                elif "DIODE_DYNAMICS" in response_upper:
                    # Generic firmware - need more info
                    # Try to determine by checking available commands
                    status = self.send_command("STATUS", timeout=2.0)
                    if status and "RELAYS:" in status.upper():
                        return "SMT"
                    else:
                        return "OFFROAD"
            return "UNKNOWN"
        except Exception as e:
            self.logger.error(f"Error getting firmware type: {e}")
            return "UNKNOWN"


# Predefined sensor configuration for SMT
class SMTSensorConfigurations:
    """Predefined sensor configurations for SMT testing"""

    @staticmethod
    def smt_panel_sensors(read_interval_ms: int = 100) -> List[SensorConfig]:
        """SMT panel testing sensor configuration
        
        For SMT testing, uses a single INA260 that's switched
        between different measurement points via relays.
        """
        return [
            SensorConfig("INA260", "CURRENT", read_interval_ms),
            SensorConfig("INA260", "VOLTAGE", read_interval_ms)
        ]


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    def button_handler(state: str):
        print(f"Button {state}")

    # Test SMT Arduino controller
    arduino = SMTArduinoController(baud_rate=115200)
    
    print("SMT Arduino Controller with Phase 1 Fixes:")
    print("✅ Proper MEASURE_GROUP command handling")
    print("✅ Serial buffer management")
    print("✅ Empty response detection")
    print("✅ Test cooldown enforcement")
    print("✅ Communication recovery")
    print("✅ Health monitoring")
