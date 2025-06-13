"""
SMT Arduino Controller - Specialized for SMT Panel Testing

PHASE 1 FIXES IMPLEMENTED:
- Fixed MEASURE_GROUP command handling with proper queue usage
- Added serial buffer management and flushing before commands  
- Added empty response detection and error handling
- Added basic recovery logic with Arduino responsiveness verification
- Added 2-second minimum interval between tests
- Added command queue overflow protection
- Specialized for SMT testing patterns

Modified: December 2024 - Phase 1 stability fixes for SMT testing
"""

import time
import logging
import threading
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

    def __init__(self, baud_rate: int = 115200):
        super().__init__()  # Initialize ResourceMixin
        self.serial = SerialManager(baud_rate=baud_rate)
        self.logger = logging.getLogger(self.__class__.__name__)

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
        
        # MEASURE_GROUP specific tracking
        self.active_measure_group = False
        self.measure_group_responses: List[str] = []

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
        
        # PHASE 1: Turn off all relays before disconnecting
        if self.is_connected():
            try:
                self.send_command("RELAY_ALL:OFF", timeout=1.0)
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
        """Test if Arduino is responding - enhanced for SMT"""
        try:
            # Clear any pending data
            self.serial.flush_buffers()

            # Try multiple times with different commands
            for attempt in range(3):
                # Send identification command
                response = self.serial.query("ID", response_timeout=3.0)
                if response and ("SMT" in response.upper() or "DIODE_DYNAMICS" in response.upper()):
                    self.logger.debug(f"Arduino identification: {response}")
                    return True

                # Try STATUS command
                response = self.serial.query("STATUS", response_timeout=2.0)
                if response and "RELAYS:" in response:
                    self.logger.debug(f"Arduino status: {response}")
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
            self.reading_thread.join(timeout=5.0)
            if self.reading_thread.is_alive():
                self.logger.warning("Reading thread did not terminate gracefully")

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
        """Process a command from the queue with special handling for MEASURE_GROUP"""
        command = command_data['command']
        response_queue = command_data['response_queue']
        timeout = command_data.get('timeout', 2.0)
        
        # PHASE 1: Clear input buffer before sending critical commands
        if command.startswith("MEASURE_GROUP") or self.serial.connection.in_waiting > 100:
            self.serial.flush_buffers()
            time.sleep(0.05)  # Small delay for buffer to clear
        
        # Send command
        if not self.serial.write(command + '\r\n'):
            response_queue.put(None)
            return
            
        # Special handling for MEASURE_GROUP commands
        if command.startswith("MEASURE_GROUP"):
            self._handle_measure_group_response(response_queue, timeout)
        else:
            # Normal command handling
            self._handle_normal_command_response(command, response_queue, timeout)

    def _handle_measure_group_response(self, response_queue: Queue, timeout: float):
        """PHASE 1: Proper MEASURE_GROUP response handling"""
        responses = []
        start_time = time.time()
        measurement_count = 0
        got_complete = False
        
        self.logger.debug("Waiting for MEASURE_GROUP response...")
        
        while time.time() - start_time < timeout:
            line = self.serial.read_line(timeout=0.5)
            if not line:
                continue
                
            line = line.strip()
            responses.append(line)
            
            # Count measurements
            if line.startswith("MEASUREMENT:"):
                measurement_count += 1
                self.logger.debug(f"Got measurement: {line}")
            
            # Check for completion
            if "MEASURE_GROUP:COMPLETE" in line:
                got_complete = True
                self.logger.debug(f"MEASURE_GROUP complete with {measurement_count} measurements")
                break
            
            # Check for error
            if line.startswith("ERROR:"):
                self.logger.error(f"MEASURE_GROUP error: {line}")
                response_queue.put(line)
                return
        
        # PHASE 1: Validate response
        if not got_complete:
            self.logger.error(f"MEASURE_GROUP timeout after {timeout}s - got {len(responses)} lines")
            response_queue.put(None)
        elif measurement_count == 0:
            self.logger.error("MEASURE_GROUP returned no measurements!")
            # Return first response line to indicate command was received
            response_queue.put(responses[0] if responses else None)
        else:
            # Return first response line (should be INFO:MEASURE_GROUP:START)
            response_queue.put(responses[0] if responses else "OK")
        
        # Store responses for later retrieval
        self.measure_group_responses = responses

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
            return resp.startswith("DATA:RELAYS:") or resp.startswith("STATUS:")
        elif cmd.startswith("RELAY"):
            return resp.startswith("OK:RELAY") or resp.startswith("ERROR:RELAY")
        elif cmd == "RESET":
            return resp.startswith("OK:RESET") or resp == "RESET"
        elif cmd == "SENSOR_CHECK":
            return resp.startswith("OK:SENSOR") or resp.startswith("WARNING:SENSOR")
        elif cmd.startswith("MEASURE_GROUP"):
            return resp.startswith("INFO:MEASURE_GROUP:")
        else:
            # Generic OK/ERROR responses
            return resp.startswith("OK:") or resp.startswith("ERROR:")

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

    def send_command(self, command: str, timeout: float = 2.0) -> Optional[str]:
        """Send command with PHASE 1 improvements"""
        # Record command time
        self.last_command_time = time.time()
        
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
                
                # PHASE 1: Check for empty MEASURE_GROUP responses
                if response is None and command.startswith("MEASURE_GROUP"):
                    self.logger.error("MEASURE_GROUP returned no response - possible serial overflow")
                    self.consecutive_errors += 1
                    # Attempt to clear buffers
                    self.serial.flush_buffers()
                
                return response
            except Empty:
                self.logger.warning(f"Timeout waiting for response to command: {command}")
                self.consecutive_errors += 1
                return None
        else:
            # Normal query when reading loop is not active
            return self.serial.query(command, response_timeout=timeout)

    def send_measure_group(self, relays: str, timeout: float = 15.0) -> Tuple[bool, List[str]]:
        """PHASE 1: Specialized method for MEASURE_GROUP commands"""
        # Clear previous responses
        self.measure_group_responses = []
        
        # Send command
        response = self.send_command(f"MEASURE_GROUP:{relays}", timeout=timeout)
        
        if response:
            # Return success and collected responses
            return True, self.measure_group_responses
        else:
            return False, []

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
        # Always turn off relays after test
        self.send_command("RELAY_ALL:OFF", timeout=1.0)

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
