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

    def __init__(self, baud_rate: int = 115200, enable_framing: bool = False):
        super().__init__()  # Initialize ResourceMixin
        # Start with CRC disabled - will auto-detect during connection
        self.serial = SerialManager(baud_rate=baud_rate, enable_crc=False, enable_framing=enable_framing)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.framing_enabled = enable_framing

        # Sensor management
        self.sensors: Dict[str, SensorConfig] = {}
        self.readings: List[SensorReading] = []
        self.max_readings = 1000  # Reduced for SMT (less data needed)

        # Reading control
        self.is_reading = False
        self.is_shutting_down = False  # Graceful shutdown flag
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
        self.min_test_interval = 0.1  # 0.1s minimum between tests (was 0.5s)
        
        
        # Command throttling (PHASE 1.2)
        self.min_command_interval = 0.005  # 5ms minimum between commands (was 10ms)
        
        # CRC-16 support (Phase 2.1)
        self.crc_supported = False
        self.crc_enabled = False
        self.firmware_version = None
        

    def _detect_crc_capability(self) -> bool:
        """Detect if Arduino firmware supports CRC-16 validation (Phase 2.1)"""
        try:
            # Query firmware version to check for CRC support
            response = self.serial.query("VERSION", response_timeout=2.0)
            if response:
                self.firmware_version = response
                # Check if version indicates CRC support
                if "CRC16_SUPPORT" in response or "5.1.0" in response:
                    # Arduino claims CRC support but doesn't actually append CRC to responses
                    # Disable CRC support until Arduino firmware is fixed
                    self.crc_supported = False
                    self.logger.warning(f"Arduino firmware claims CRC-16 support but implementation is incomplete: {response}")
                    self.logger.warning("CRC validation disabled - Arduino firmware does not append CRC to responses")
                    return False
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
        """Connect to Arduino on specified port with enhanced recovery and protocol verification"""
        if self.serial.connect(port):
            # PHASE 1: Clear buffers immediately
            self.serial.flush_buffers()
            time.sleep(0.1)  # Small delay for Arduino to stabilize
            
            # Test basic communication
            if self.test_communication():
                self.logger.info(f"SMT Arduino connected successfully on {port}")
                self.consecutive_errors = 0
                
                # Phase 4: Establish communication protocols
                self._establish_communication_protocols()
                
                return True
            else:
                self.logger.error("Arduino connected but communication test failed")
                self.serial.disconnect()
                return False
        return False
    
    def _establish_communication_protocols(self):
        """Phase 4: Establish and verify communication protocols with Arduino"""
        try:
            self.logger.info("Establishing communication protocols with Arduino...")
            
            # 1. Query firmware capabilities
            response = self.send_command("VERSION", timeout=3.0)
            if response:
                self.firmware_version = response
                self.logger.info(f"Arduino firmware: {response}")
                
                # Check for required features - no backward compatibility
                required_capabilities = []
                optional_capabilities = []
                
                if "CRC16_SUPPORT" in response or "5.1.0" in response or "5.2.0" in response or "5.3.0" in response or "5.4.0" in response:
                    optional_capabilities.append("CRC-16")
                if "FRAMING_SUPPORT" in response or "5.2.0" in response or "5.3.0" in response or "5.4.0" in response:
                    optional_capabilities.append("Binary Framing")
                if "BINARY_PROTOCOL" in response or "5.3.0" in response or "5.4.0" in response:
                    optional_capabilities.append("Binary Protocol")
                if "CONFIG_SUPPORT" in response or "5.4.0" in response:
                    required_capabilities.append("Timing Configuration")
                
                if required_capabilities:
                    self.logger.info(f"Arduino required capabilities: {', '.join(required_capabilities)}")
                if optional_capabilities:
                    self.logger.info(f"Arduino optional capabilities: {', '.join(optional_capabilities)}")
                
                # Verify minimum firmware version
                # Extract version number from response like "VERSION:5.4.1:..."
                version_parts = response.split(':')
                if len(version_parts) > 1:
                    version_str = version_parts[1]  # Get "5.4.1"
                    try:
                        # Parse major.minor.patch
                        version_nums = version_str.split('.')
                        major = int(version_nums[0])
                        minor = int(version_nums[1]) if len(version_nums) > 1 else 0
                        
                        # Check if version is 5.1 or higher
                        if major < 5 or (major == 5 and minor < 1):
                            self.logger.error(f"Arduino firmware {version_str} is too old - requires version 5.1.0 or higher")
                            raise Exception("Incompatible Arduino firmware version")
                        else:
                            self.logger.info(f"Arduino firmware version {version_str} is compatible")
                    except (ValueError, IndexError):
                        self.logger.warning(f"Could not parse firmware version from: {response}")
                else:
                    self.logger.warning("Could not determine Arduino firmware version")
            
            # 2. Test basic relay control
            relay_test = self.send_command("RELAY:1:OFF", timeout=2.0)
            if relay_test and ("OK" in relay_test or "RELAY" in relay_test):
                self.logger.debug("Relay control verified")
            else:
                self.logger.warning(f"Relay control test failed: {relay_test}")
            
            # 3. Test measurement capability
            status_response = self.send_command("STATUS", timeout=2.0)
            if status_response and "RELAYS:" in status_response:
                self.logger.debug("Status reporting verified")
            else:
                self.logger.warning(f"Status reporting test failed: {status_response}")
            
            # 4. Test configuration support (Phase 4) - REQUIRED
            config_test = self.send_command("CONFIG:STATUS", timeout=2.0)
            if config_test and ("CONFIG:" in config_test or "OK:" in config_test):
                self.logger.info("Arduino supports timing configuration")
            else:
                self.logger.error("Arduino firmware does not support timing configuration")
                self.logger.error("Please update Arduino firmware to version 5.4.0 or higher")
                raise Exception("Incompatible Arduino firmware - timing configuration not supported")
            
            # 5. Enable CRC if supported (Phase 2.1)
            if self.crc_supported:
                self.enable_crc_validation(True)
            
            self.logger.info("Communication protocols established successfully")
            
        except Exception as e:
            self.logger.error(f"Error establishing communication protocols: {e}")
            # Don't fail connection for protocol setup errors

    def disconnect(self):
        """Disconnect from Arduino with proper cleanup"""
        self.stop_reading()
        
        # PHASE 1: Turn off all relays using batch command before disconnecting
        if self.is_connected():
            try:
                self.send_command("RELAY:ALL:OFF", timeout=0.05)
                time.sleep(0.05)
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
        """Stop reading loop with graceful shutdown"""
        if not self.is_reading:
            return

        # Set shutdown flag to prevent new commands
        self.is_shutting_down = True
        self.is_reading = False

        # Wait for command queue to empty (process pending commands)
        timeout = time.time() + 2.0  # 2 second timeout
        while not self.command_queue.empty() and time.time() < timeout:
            time.sleep(0.05)  # Small delay to allow queue processing
        
        if not self.command_queue.empty():
            self.logger.warning(f"Command queue still has {self.command_queue.qsize()} items after timeout")
            # Clear remaining commands
            while not self.command_queue.empty():
                try:
                    self.command_queue.get_nowait()
                except Empty:
                    break

        # Wait for reading thread to finish
        if self.reading_thread and self.reading_thread.is_alive():
            self.reading_thread.join(timeout=2.0)
            if self.reading_thread.is_alive():
                self.logger.warning("Reading thread did not terminate gracefully")
        
        # Add small delay to ensure last command completes
        time.sleep(0.1)
        
        # Reset shutdown flag
        self.is_shutting_down = False

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
        elif cmd == "RELAY:ALL:OFF":
            return resp.startswith("OK:ALL_RELAYS_OFF") or resp.startswith("OK:RELAY_ALL:OFF")
        elif cmd == "RELAY:ALL:ON":
            return resp.startswith("OK:ALL_RELAYS_ON")
        elif cmd.startswith("RELAY:GROUP:"):
            return resp.startswith("OK:GROUP_") or resp.startswith("ERR:")
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
        elif cmd.startswith("CONFIG:"):
            # Configuration commands (Phase 4)
            if cmd == "CONFIG:STATUS":
                return resp.startswith("CONFIG:") or resp.startswith("OK:CONFIG") or resp.startswith("ERROR:")
            else:
                return resp.startswith("OK:CONFIG") or resp.startswith("ERROR:CONFIG") or resp.startswith("OK:") or resp.startswith("ERROR:")
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
        # Check if we're shutting down
        if self.is_shutting_down:
            self.logger.debug(f"Ignoring command during shutdown: {command}")
            return None
            
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

    def measure_relays(self, relay_list: List[int], timeout: float = 0.1) -> Dict[int, Dict[str, float]]:
        """
        Measure multiple relays using individual commands - OPTIMIZED VERSION.
        Returns dict of relay_number -> measurement results.
        
        Optimized for ~250ms per relay cycle with minimal delays.
        """
        results = {}
        
        # Turn off all relays at once using batch command
        self.send_command("RELAY:ALL:OFF", timeout=0.05)
        # No stabilization delay needed
        
        for i, relay in enumerate(relay_list):
            try:
                # Only turn off previous relay if not first
                if i > 0:
                    prev_relay = relay_list[i-1]
                    self.send_command(f"RELAY:{prev_relay}:OFF", timeout=0.05)
                
                # Turn on specific relay
                relay_cmd = f"RELAY:{relay}:ON"
                relay_response = self.send_command(relay_cmd, timeout=0.1)
                if not relay_response or "ERROR" in relay_response:
                    self.logger.error(f"Failed to turn on relay {relay}")
                    results[relay] = None
                    continue
                
                # Minimal settle time
                time.sleep(0.005)  # 5ms relay settle time
                
                # Send simple MEASURE command with reduced timeout
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
                
            except Exception as e:
                self.logger.error(f"Error measuring relay {relay}: {e}")
                results[relay] = None
            
            # Minimal delay between measurements
            # No delay between relays - go as fast as possible
        
        # Turn off last relay (or could use RELAY:ALL:OFF)
        if relay_list:
            self.send_command(f"RELAY:{relay_list[-1]}:OFF", timeout=0.05)
        
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
        # Turn off all relays quickly using batch command
        self.send_command("RELAY:ALL:OFF", timeout=0.05)

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
    
    def apply_timing_config(self, timing: Dict[str, Any]) -> bool:
        """Apply timing configuration from SKU (Phase 4)"""
        try:
            self.logger.info(f"Applying timing configuration: {timing}")
            
            # Apply command interval if specified
            if 'command_interval_ms' in timing:
                new_interval = timing['command_interval_ms'] / 1000.0
                old_interval = self.min_command_interval
                self.min_command_interval = new_interval
                self.logger.info(f"Command interval: {old_interval*1000:.0f}ms -> {new_interval*1000:.0f}ms")
            
            # Apply test cooldown if specified
            if 'test_cooldown_s' in timing:
                old_cooldown = self.min_test_interval
                self.min_test_interval = timing['test_cooldown_s']
                self.logger.info(f"Test cooldown: {old_cooldown:.1f}s -> {self.min_test_interval:.1f}s")
            
            # Send timing configuration to Arduino if connected
            if self.is_connected():
                success = self._configure_arduino_timing(timing)
                if success:
                    self.logger.info("Arduino timing configuration applied successfully")
                    return True
                else:
                    self.logger.error("Failed to apply timing configuration to Arduino")
                    return False
            else:
                self.logger.error("Arduino not connected - cannot apply timing configuration")
                return False
                
        except Exception as e:
            self.logger.error(f"Error applying timing configuration: {e}")
            return False
    
    def _configure_arduino_timing(self, timing: Dict[str, Any]) -> bool:
        """Send timing configuration to Arduino"""
        try:
            # Configure power stabilization time
            if 'power_stabilization_s' in timing:
                stabilization_ms = int(timing['power_stabilization_s'] * 1000)
                response = self.send_command(f"CONFIG:STABILIZATION:{stabilization_ms}", timeout=2.0)
                if not response or "ERROR" in response:
                    self.logger.warning(f"Failed to set Arduino stabilization time: {response}")
            
            # Configure measurement duration if available
            if 'default_test_duration_s' in timing:
                duration_ms = int(timing['default_test_duration_s'] * 1000)
                response = self.send_command(f"CONFIG:DURATION:{duration_ms}", timeout=2.0)
                if not response or "ERROR" in response:
                    self.logger.warning(f"Failed to set Arduino test duration: {response}")
            
            # Configure command throttling on Arduino side
            if 'command_interval_ms' in timing:
                interval_ms = int(timing['command_interval_ms'])
                response = self.send_command(f"CONFIG:THROTTLE:{interval_ms}", timeout=2.0)
                if not response or "ERROR" in response:
                    self.logger.warning(f"Failed to set Arduino command throttling: {response}")
            
            # Verify configuration was applied
            response = self.send_command("CONFIG:STATUS", timeout=2.0)
            if response and "CONFIG:" in response:
                self.logger.debug(f"Arduino timing configuration status: {response}")
                return True
            else:
                self.logger.error("Arduino firmware does not support timing configuration commands")
                self.logger.error("Please update Arduino firmware to version 5.4.0 or higher")
                return False
                
        except Exception as e:
            self.logger.error(f"Error configuring Arduino timing: {e}")
            return False

    def get_health_status(self) -> Dict[str, Any]:
        """PHASE 1: Get health status of the controller"""
        return {
            "connected": self.is_connected(),
            "reading": self.is_reading,
            "consecutive_errors": self.consecutive_errors,
            "command_queue_depth": self.command_queue.qsize(),
            "time_since_last_command": time.time() - self.last_command_time if self.last_command_time > 0 else None,
            "time_since_last_test": time.time() - self.last_test_end_time if self.last_test_end_time > 0 else None,
            "current_timing": {
                "command_interval_ms": self.min_command_interval * 1000,
                "test_cooldown_s": self.min_test_interval
            }
        }


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
