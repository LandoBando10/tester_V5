"""
SMT Arduino Controller - Simplified for Phase 2 Implementation

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
from typing import Dict, List, Optional, Callable

class SMTArduinoController:
    """Simplified Arduino controller for SMT panel testing"""

    def __init__(self, baud_rate: int = 115200):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.baud_rate = baud_rate
        self.connection: Optional[serial.Serial] = None
        self.port: Optional[str] = None
        
        # Button callback
        self.button_callback: Optional[Callable[[str], None]] = None
        
        # Simple retry and timeout settings
        self.command_timeout = 2.0
        self.max_retries = 3
        self.retry_delay = 0.1

    def connect(self, port: str) -> bool:
        """Connect to Arduino on specified port"""
        try:
            self.connection = serial.Serial(
                port=port,
                baudrate=self.baud_rate,
                timeout=1.0,
                write_timeout=1.0
            )
            self.port = port
            
            # Clear buffers and test communication
            self._flush_buffers()
            time.sleep(0.1)
            
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

    def is_connected(self) -> bool:
        """Check if Arduino is connected"""
        return self.connection is not None and self.connection.is_open

    def _flush_buffers(self):
        """Clear serial buffers"""
        if self.connection:
            self.connection.reset_input_buffer()
            self.connection.reset_output_buffer()

    def _test_communication(self) -> bool:
        """Test basic communication with Arduino"""
        for attempt in range(3):
            response = self._send_command("I")
            if response and "SMT_SIMPLE_TESTER" in response:
                return True
            time.sleep(0.5)
        return False

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
                self.connection.write(f"{command}\n".encode())
                self.connection.flush()
                
                # Read response with timeout
                start_time = time.time()
                response = ""
                
                while time.time() - start_time < timeout:
                    if self.connection.in_waiting > 0:
                        char = self.connection.read(1).decode('utf-8', errors='ignore')
                        if char == '\n':
                            break
                        response += char
                    else:
                        time.sleep(0.01)
                
                if response:
                    response = response.strip()
                    if self._validate_response(command, response):
                        return response
                    else:
                        self.logger.warning(f"Invalid response for {command}: {response}")
                
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
            return "SMT_SIMPLE_TESTER" in response
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
        response = self._send_command(command, timeout=0.2)
        
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