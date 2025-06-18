"""
SMT Arduino Controller - Simplified for Phase 2 Implementation

*** Fixed for Arduino R4 Minima Compatibility (June 2025) ***
- DTR/RTS must be set AFTER opening port for R4
- Added permission error handling with fallback connection
- Extended USB stabilization delays for R4
- Improved buffer flush error handling

Simplified version that removes:
- Threading and queues
- CRC validation
- Binary framing
- Complex statistics tracking
- Resource management
- Configuration system

Keeps only:
- Basic relay measurement
- Serial communication with timeouts
- Button event callbacks
- Error handling and retries
- Format validation
"""

import time
import logging
import serial
import threading
from typing import Dict, List, Optional, Callable

class SMTArduinoController:
    """Simplified Arduino controller for SMT panel testing"""

    def __init__(self, baud_rate: int = 115200):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)  # Ensure debug logging is enabled
        self.baud_rate = baud_rate
        self.connection: Optional[serial.Serial] = None
        self.port: Optional[str] = None
        
        # Button callback
        self.button_callback: Optional[Callable[[str], None]] = None
        
        # Reading thread
        self.is_reading = False
        self._reading_thread = None
        self._stop_reading = threading.Event()
        
        # Simple retry and timeout settings
        self.command_timeout = 2.0
        self.max_retries = 3
        self.retry_delay = 0.1

    def connect(self, port: str) -> bool:
        """Connect to Arduino on specified port"""
        # First, try to release the port if it's stuck
        self._attempt_port_release(port)
        
        try:
            # First check if port exists and get its info
            import serial.tools.list_ports
            ports = serial.tools.list_ports.comports()
            port_info = None
            for p in ports:
                if p.device == port:
                    port_info = p
                    break
            
            if port_info:
                self.logger.info(f"Port {port} info:")
                self.logger.info(f"  Description: {port_info.description}")
                self.logger.info(f"  Manufacturer: {port_info.manufacturer}")
                self.logger.info(f"  Product: {port_info.product}")
                self.logger.info(f"  VID:PID: {port_info.vid}:{port_info.pid}")
            else:
                self.logger.warning(f"Port {port} not found in system ports list")
            
            # Configure serial connection (R4 Minima compatible)
            self.connection = serial.Serial()
            self.connection.port = port
            self.connection.baudrate = self.baud_rate
            self.connection.timeout = self.command_timeout
            self.connection.write_timeout = 1.0
            
            # For Arduino R4 Minima: Must open BEFORE setting DTR/RTS
            try:
                self.connection.open()
                self.port = port
                self.logger.info("Port opened successfully")
                
                # NOW set DTR/RTS after opening (R4 Minima requirement)
                try:
                    self.connection.dtr = True  # Arduino needs DTR HIGH to know we're connected!
                    self.connection.rts = False
                    self.logger.debug("DTR set to True, RTS to False after opening")
                except Exception as dtr_error:
                    self.logger.debug(f"Could not set DTR/RTS (may not be supported): {dtr_error}")
                    # This is okay - some devices don't support DTR/RTS control
                    
            except serial.SerialException as e:
                if "PermissionError" in str(e) or "Access is denied" in str(e):
                    self.logger.warning("Permission error - trying alternative connection method for R4...")
                    
                    # Try direct connection without DTR/RTS control
                    try:
                        self.connection = serial.Serial(
                            port=port,
                            baudrate=self.baud_rate,
                            timeout=self.command_timeout,
                            write_timeout=1.0
                        )
                        self.port = port
                        self.logger.info("Alternative connection method successful")
                    except Exception as alt_error:
                        self.logger.error(f"Alternative connection also failed: {alt_error}")
                        raise
                else:
                    raise
            
            # Log actual serial settings
            self.logger.info(f"Serial port settings:")
            self.logger.info(f"  Baudrate: {self.connection.baudrate}")
            self.logger.info(f"  Bytesize: {self.connection.bytesize}")
            self.logger.info(f"  Parity: {self.connection.parity}")
            self.logger.info(f"  Stopbits: {self.connection.stopbits}")
            self.logger.info(f"  Timeout: {self.connection.timeout}")
            self.logger.info(f"  DTR: {self.connection.dtr}")
            self.logger.info(f"  RTS: {self.connection.rts}")
            
            # Arduino R4 Minima needs time to stabilize USB connection
            self.logger.info("Waiting for Arduino R4 USB stabilization...")
            time.sleep(1.0)  # R4 needs longer delay
            
            # Clear any existing data
            self._flush_buffers()
            
            # Check if Arduino is already sending data
            time.sleep(0.5)
            if self.connection.in_waiting > 0:
                self.logger.info(f"Arduino already active, {self.connection.in_waiting} bytes waiting")
                try:
                    existing_data = self.connection.read(self.connection.in_waiting)
                    self.logger.info(f"Existing data: {existing_data}")
                except:
                    pass
            
            # Skip DTR reset - it seems to cause issues
            # Just give Arduino a moment to respond
            self.logger.info(f"Waiting for Arduino to respond on {port}...")
            time.sleep(0.5)
            
            # Don't clear buffers yet - we want to catch any error messages
            
            # Read and log any startup messages with shorter timeout
            self.logger.info("Listening for Arduino startup messages...")
            startup_deadline = time.time() + 0.5  # Reduced from 3 seconds to 0.5
            startup_messages = []
            error_detected = False
            no_data_time = 0
            
            while time.time() < startup_deadline:
                if self.connection.in_waiting > 0:
                    no_data_time = 0  # Reset no data counter
                    try:
                        # Read any available data
                        data = self.connection.readline()
                        if data:
                            decoded = data.decode('utf-8', errors='ignore').strip()
                            if decoded:
                                startup_messages.append(decoded)
                                self.logger.info(f"Arduino message: '{decoded}'")
                                
                                # Check for specific messages
                                if "ERROR:INA260_INIT_FAILED" in decoded:
                                    self.logger.error("INA260 sensor initialization failed! Arduino is stuck.")
                                    error_detected = True
                                    break
                                elif "SMT_SIMPLE_TESTER_READY" in decoded:
                                    self.logger.info("Arduino reported ready successfully")
                                    break
                    except Exception as e:
                        self.logger.error(f"Error reading startup message: {e}")
                else:
                    time.sleep(0.05)
                    no_data_time += 0.05
                    # If no data for 200ms, assume no startup messages
                    if no_data_time > 0.2:
                        self.logger.debug("No startup messages detected, continuing...")
                        break
            
            if error_detected:
                self.logger.error("Arduino firmware detected hardware error (INA260 sensor not found)")
                self.logger.error("Please check: 1) INA260 sensor is connected, 2) I2C connections are correct")
                self.disconnect()
                return False
            
            if not startup_messages:
                self.logger.warning("No startup messages received from Arduino")
            
            # Now clear buffers for fresh start
            self._flush_buffers()
            
            # Check if this might be wrong firmware or device
            self.logger.info("Checking device responsiveness...")
            if not self._check_device_type():
                self.logger.warning("Device check failed - may not be Arduino or wrong firmware")
            
            # First try raw communication test
            if not self.test_raw_communication():
                self.logger.error("Raw communication test failed - Arduino may not be responding")
                # Continue anyway to get more diagnostic info
            
            if self._test_communication():
                self.logger.info(f"Connected to SMT Arduino on {port}")
                return True
            else:
                self.logger.error("Arduino connected but communication test failed")
                self.disconnect()
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to connect to {port}: {e}")
            return False

    def disconnect(self):
        """Disconnect from Arduino"""
        # Stop reading thread first
        self.stop_reading()
        
        if self.connection and self.connection.is_open:
            try:
                # Turn off all relays before disconnecting
                self._send_command("X")
                self.connection.close()
                self.logger.info("Disconnected from Arduino")
            except Exception as e:
                self.logger.error(f"Error during disconnect: {e}")
        
        self.connection = None
        self.port = None

    def _attempt_port_release(self, port: str):
        """Try to release a potentially stuck port"""
        try:
            # Quick open/close to release any stuck handles
            for _ in range(3):
                try:
                    temp_ser = serial.Serial()
                    temp_ser.port = port
                    temp_ser.baudrate = 9600
                    temp_ser.timeout = 0.01
                    temp_ser.open()
                    temp_ser.close()
                    time.sleep(0.05)
                except:
                    pass
            
            # Give Windows time to release the port
            time.sleep(0.2)
            
        except Exception as e:
            self.logger.debug(f"Port release attempt: {e}")

    def is_connected(self) -> bool:
        """Check if Arduino is connected"""
        return self.connection is not None and self.connection.is_open

    def _flush_buffers(self):
        """Clear serial buffers (with R4 Minima compatibility)"""
        if self.connection and self.connection.is_open:
            try:
                self.connection.reset_input_buffer()
                self.connection.reset_output_buffer()
            except Exception as e:
                # R4 Minima might not support buffer operations in all states
                self.logger.debug(f"Could not flush buffers (R4 limitation): {e}")

    def _test_communication(self) -> bool:
        """Test basic communication with Arduino"""
        self.logger.info("Testing communication with Arduino...")
        for attempt in range(3):
            self.logger.info(f"Communication test attempt {attempt + 1}/3")
            response = self._send_command("I")
            if response and response.startswith("ID:SMT_SIMPLE_TESTER"):
                self.logger.info(f"Communication test successful, received: '{response}'")
                return True
            self.logger.warning(f"Communication test attempt {attempt + 1} failed")
            time.sleep(0.5)
        self.logger.error("All communication test attempts failed")
        return False

    def test_communication(self) -> bool:
        """Public method to test communication with Arduino"""
        return self._test_communication()

    def get_firmware_type(self) -> str:
        """Get the firmware type of connected Arduino"""
        try:
            response = self._send_command("I")
            if response:
                response_upper = response.upper()
                if "SMT_SIMPLE_TESTER" in response_upper or "SMT_TESTER" in response_upper or "SMT" in response_upper:
                    return "SMT"
                elif "OFFROAD" in response_upper:
                    return "OFFROAD"
            return "UNKNOWN"
        except Exception as e:
            self.logger.error(f"Error getting firmware type: {e}")
            return "UNKNOWN"

    def configure_sensors(self, sensor_configs) -> bool:
        """Configure sensors - SMT Arduino doesn't need sensor configuration"""
        # SMT Arduino has fixed INA260 sensor, no configuration needed
        self.logger.info("SMT Arduino uses fixed INA260 sensor configuration")
        return True

    def start_reading(self):
        """Start the background reading thread for button events"""
        if self.is_reading:
            self.logger.warning("Reading thread already running")
            return
            
        self._stop_reading.clear()
        self.is_reading = True
        self._reading_thread = threading.Thread(target=self._reading_loop)
        self._reading_thread.daemon = True
        self._reading_thread.start()
        self.logger.info("Started reading thread for button events")

    def stop_reading(self):
        """Stop the background reading thread"""
        if not self.is_reading:
            return
            
        self.logger.info("Stopping reading thread...")
        self._stop_reading.set()
        self.is_reading = False
        
        if self._reading_thread and self._reading_thread.is_alive():
            self._reading_thread.join(timeout=2.0)
            
        self.logger.info("Reading thread stopped")

    def _reading_loop(self):
        """Background thread to read button events"""
        self.logger.info("Reading loop started")
        
        while not self._stop_reading.is_set():
            try:
                if self.connection and self.connection.is_open and self.connection.in_waiting > 0:
                    data = self.connection.readline()
                    if data:
                        message = data.decode('utf-8', errors='ignore').strip()
                        if message.startswith("BUTTON:") and self.button_callback:
                            self.logger.info(f"Button event: {message}")
                            self.button_callback(message)
            except Exception as e:
                self.logger.error(f"Error in reading loop: {e}")
                
            time.sleep(0.01)  # Small delay to prevent CPU spinning
        
        self.logger.info("Reading loop ended")

    def _send_command(self, command: str, timeout: float = None) -> Optional[str]:
        """Send command to Arduino with retry logic"""
        if not self.is_connected():
            return None
            
        if timeout is None:
            timeout = self.command_timeout
            
        for attempt in range(self.max_retries):
            try:
                # Clear input buffer before sending
                self.connection.reset_input_buffer()
                
                # Send command
                cmd_bytes = f"{command}\n".encode()
                self.logger.debug(f"Sending command: '{command}' as bytes: {cmd_bytes}")
                bytes_written = self.connection.write(cmd_bytes)
                self.connection.flush()
                self.logger.debug(f"Wrote {bytes_written} bytes")
                
                # Read response with timeout
                # Save original timeout and set new one
                original_timeout = self.connection.timeout
                self.connection.timeout = timeout
                
                try:
                    # Check if data is available before reading
                    wait_start = time.time()
                    while self.connection.in_waiting == 0 and (time.time() - wait_start) < timeout:
                        time.sleep(0.01)
                    
                    if self.connection.in_waiting > 0:
                        self.logger.debug(f"Data available: {self.connection.in_waiting} bytes")
                        # Use readline() for proper line ending handling
                        raw_bytes = self.connection.readline()
                        self.logger.debug(f"Raw bytes received: {raw_bytes}")
                        response = raw_bytes.decode('utf-8', errors='ignore').strip()
                    else:
                        self.logger.debug("No data received within timeout")
                        response = ""
                finally:
                    # Restore original timeout
                    self.connection.timeout = original_timeout
                
                self.logger.debug(f"Decoded response: '{response}'")
                
                if response:
                    response = response.strip()
                    if self._validate_response(command, response):
                        self.logger.debug(f"Valid response for {command}: {response}")
                        return response
                    else:
                        self.logger.warning(f"Invalid response for {command}: {response}")
                else:
                    self.logger.warning(f"No response received for command: {command}")
                
            except Exception as e:
                self.logger.error(f"Command error (attempt {attempt + 1}): {e}")
                
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        self.logger.error(f"Command failed after {self.max_retries} attempts: {command}")
        return None

    def _validate_response(self, command: str, response: str) -> bool:
        """Validate response format"""
        if not response:
            return False
            
        # Check for error responses
        if response.startswith("ERROR:"):
            return True  # Error responses are valid
            
        # Command-specific validation
        if command == "I":
            return response.startswith("ID:SMT_SIMPLE_TESTER")
        elif command == "X":
            return response == "OK:ALL_OFF"
        elif command == "B":
            return response.startswith("BUTTON:")
        elif command.startswith("R") and len(command) == 2:
            # Relay measurement: R1:12.500,0.450
            return ":" in response and "," in response
        
        return True

    def measure_relay(self, relay_num: int) -> Optional[Dict[str, float]]:
        """Measure a single relay"""
        if relay_num < 1 or relay_num > 8:
            self.logger.error(f"Invalid relay number: {relay_num}")
            return None
            
        command = f"R{relay_num}"
        # Increased timeout to account for measurement time + response
        # Arduino takes ~120ms for measurement (15ms stabilization + 6 samples * 17ms)
        response = self._send_command(command, timeout=0.5)
        
        if not response:
            return None
            
        if response.startswith("ERROR:"):
            self.logger.error(f"Relay {relay_num} measurement error: {response}")
            return None
            
        try:
            # Parse response: R1:12.500,0.450
            if ":" in response and "," in response:
                _, data = response.split(":", 1)
                voltage_str, current_str = data.split(",", 1)
                
                voltage = float(voltage_str)
                current = float(current_str)
                power = voltage * current
                
                return {
                    'voltage': voltage,
                    'current': current,
                    'power': power
                }
        except Exception as e:
            self.logger.error(f"Failed to parse relay {relay_num} response '{response}': {e}")
            
        return None

    def measure_relays(self, relay_list: List[int]) -> Dict[int, Optional[Dict[str, float]]]:
        """Measure multiple relays sequentially"""
        results = {}
        
        for relay in relay_list:
            results[relay] = self.measure_relay(relay)
            
        return results

    def all_relays_off(self) -> bool:
        """Turn off all relays"""
        response = self._send_command("X")
        return response == "OK:ALL_OFF"

    def get_button_status(self) -> Optional[str]:
        """Get current button status"""
        response = self._send_command("B")
        if response and response.startswith("BUTTON:"):
            return response[7:]  # Remove "BUTTON:" prefix
        return None

    def set_button_callback(self, callback: Optional[Callable[[str], None]]):
        """Set callback for button events"""
        self.button_callback = callback
    
    # Compatibility methods for standard ArduinoController interface
    @property
    def serial(self):
        """Compatibility property for code expecting 'serial' attribute"""
        class SerialWrapper:
            def __init__(self, controller):
                self.controller = controller
            
            def flush_buffers(self):
                self.controller._flush_buffers()
        
        return SerialWrapper(self)
    
    def send_command(self, command: str, timeout: float = None) -> Optional[str]:
        """Public wrapper for _send_command to match ArduinoController interface"""
        return self._send_command(command, timeout)

    def check_button_events(self):
        """Check for button events (should be called periodically)"""
        if not self.button_callback:
            return
            
        button_state = self.get_button_status()
        if button_state == "PRESSED":
            try:
                self.button_callback("PRESSED")
            except Exception as e:
                self.logger.error(f"Button callback error: {e}")

    def get_board_info(self) -> Optional[str]:
        """Get board identification"""
        return self._send_command("I")
    
    def _check_device_type(self) -> bool:
        """Check if device responds like an Arduino"""
        try:
            # Skip DTR test - it causes issues with some Arduino boards
            self.logger.info("Skipping DTR test...")
            
            # Test 2: Send invalid command and check for any response
            self.logger.info("Testing error response...")
            self.connection.write(b"INVALID_COMMAND\n")
            self.connection.flush()
            time.sleep(0.3)
            
            if self.connection.in_waiting > 0:
                data = self.connection.read(self.connection.in_waiting)
                self.logger.info(f"Response to invalid command: {data}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Device type check error: {e}")
            return False
    
    def test_raw_communication(self) -> bool:
        """Test raw serial communication without command structure"""
        if not self.is_connected():
            self.logger.error("Cannot test - not connected")
            return False
        
        try:
            self.logger.info("Testing raw serial communication...")
            
            # Test different command formats
            test_commands = [
                (b"I\n", "LF only"),
                (b"I\r\n", "CR+LF"),
                (b"I\r", "CR only"),
                (b"ID\n", "ID command"),
                (b"?\n", "Query"),
                (b"\n", "Empty line"),
                (b"STATUS\n", "STATUS command")
            ]
            
            for cmd, description in test_commands:
                self.logger.info(f"Testing {description}: {cmd}")
                self.connection.reset_input_buffer()
                
                # Send command
                bytes_written = self.connection.write(cmd)
                self.connection.flush()
                self.logger.debug(f"Sent {bytes_written} bytes")
                
                # Wait for response
                time.sleep(0.3)
                
                if self.connection.in_waiting > 0:
                    self.logger.info(f"Response received! {self.connection.in_waiting} bytes available")
                    raw_data = self.connection.read(self.connection.in_waiting)
                    self.logger.info(f"Raw data: {raw_data}")
                    
                    try:
                        decoded = raw_data.decode('utf-8', errors='ignore')
                        self.logger.info(f"Decoded: '{decoded}'")
                        # If we got any response, that's a good sign
                        return True
                    except Exception as e:
                        self.logger.error(f"Decode error: {e}")
                        # Even if decode fails, we got data
                        return True
                else:
                    self.logger.debug(f"No response to {description}")
            
            # Final check - look for any spontaneous data
            self.logger.info("Checking for spontaneous data...")
            time.sleep(1.0)
            if self.connection.in_waiting > 0:
                self.logger.info(f"Spontaneous data found: {self.connection.in_waiting} bytes")
                data = self.connection.read(self.connection.in_waiting)
                self.logger.info(f"Data: {data}")
                return True
            
            self.logger.warning("No response to any test command")
            return False
                
        except Exception as e:
            self.logger.error(f"Raw communication test error: {e}")
            return False


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    def button_handler(state: str):
        print(f"Button {state}")
    
    # Test controller
    controller = SMTArduinoController()
    
    # Mock connection for testing
    if controller.connect("/dev/ttyUSB0"):
        controller.set_button_callback(button_handler)
        
        # Test measurements
        results = controller.measure_relays([1, 2, 3])
        for relay, data in results.items():
            if data:
                print(f"Relay {relay}: {data['voltage']:.3f}V, {data['current']:.3f}A, {data['power']:.3f}W")
            else:
                print(f"Relay {relay}: Failed")
        
        controller.disconnect()