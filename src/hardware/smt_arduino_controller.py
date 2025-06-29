"""
SMT Arduino Controller - Batch Communication Only
Version 2.0.0 - Simplified for batch-only operation

This version removes all individual relay measurement commands and
only supports batch panel testing for maximum simplicity and performance.

Key changes from v1.x:
- Removed measure_relay() method
- Removed measure_relays() method  
- Only supports test_panel() and test_panel_stream()
- Simplified command validation
- Cleaner, more maintainable code
"""

import time
import logging
import serial
import threading
import queue
from typing import Dict, Optional, Callable

class SMTArduinoController:
    """Simplified Arduino controller for SMT panel testing - batch only"""

    def __init__(self, baud_rate: int = 115200):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)
        self.baud_rate = baud_rate
        self.connection: Optional[serial.Serial] = None
        self.port: Optional[str] = None
        
        # Callbacks
        self.button_callback: Optional[Callable[[str], None]] = None
        self.error_callback: Optional[Callable[[str, str], None]] = None  # error_type, message
        
        # Reading thread for button events
        self.is_reading = False
        self._reading_thread = None
        self._stop_reading = threading.Event()
        
        # Event queue for messages during command execution
        self._event_queue = queue.Queue()
        self._command_lock = threading.Lock()
        self._expecting_response = False
        self._response_queue = queue.Queue()
        
        # Simple retry and timeout settings
        self.command_timeout = 2.0
        self.max_retries = 3
        self.retry_delay = 0.1
        
        # Protocol reliability
        self._sequence_number = 0
        self._enable_checksums = True  # Can be disabled for backward compatibility

    def connect(self, port: str) -> bool:
        """Connect to Arduino on specified port"""
        try:
            # Configure serial connection
            self.connection = serial.Serial(
                port=port,
                baudrate=self.baud_rate,
                timeout=self.command_timeout,
                write_timeout=1.0,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            self.port = port
            self.logger.info(f"Connected to {port}")
            
            # Set DTR if supported
            try:
                self.connection.dtr = True
                self.connection.rts = False
            except:
                pass  # Some devices don't support DTR/RTS
            
            # Wait for Arduino to stabilize
            time.sleep(1.0)
            
            # Clear buffers
            self._flush_buffers()
            
            # Read any startup messages
            self._read_startup_messages()
            
            # Start reading thread BEFORE testing communication
            # This is essential for the queue-based command system to work
            self.start_reading()
            
            # Reset sequence numbers on both sides
            reset_response = self._send_command("RESET_SEQ", timeout=0.5)
            if reset_response and "OK:SEQ_RESET" in reset_response:
                self.logger.debug("Sequence numbers reset successfully")
                self._sequence_number = 0  # Reset Python side to match
            else:
                self.logger.debug("RESET_SEQ not supported by firmware (legacy compatibility)")
            
            # Test communication
            if self._test_communication():
                self.logger.info(f"Connected to SMT Arduino on {port}")
                return True
            else:
                self.logger.error("Communication test failed")
                self.disconnect()
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to connect to {port}: {e}")
            return False

    def disconnect(self):
        """Disconnect from Arduino"""
        if self.connection and self.connection.is_open:
            try:
                # Try to turn off relays BEFORE stopping reading thread
                if self.is_reading:
                    try:
                        self.all_relays_off()
                    except:
                        pass
                
                # Now stop reading thread
                self.stop_reading()
                
                # Force close the connection
                self.connection.close()
                time.sleep(0.1)  # Give OS time to release the port
                self.logger.info("Disconnected from Arduino")
            except Exception as e:
                self.logger.error(f"Error during disconnect: {e}")
                # Force connection to None even if close failed
        else:
            # Still need to stop reading thread even if connection is closed
            self.stop_reading()
        
        self.connection = None
        self.port = None
        
        # Clear response queue
        while not self._response_queue.empty():
            try:
                self._response_queue.get_nowait()
            except:
                break

    def is_connected(self) -> bool:
        """Check if Arduino is connected"""
        return self.connection is not None and self.connection.is_open

    def _flush_buffers(self):
        """Clear serial buffers - safe to call with reading thread active"""
        if self.connection and self.connection.is_open:
            try:
                # Just clear the input buffer - output buffer flush is less critical
                # and could interfere with ongoing writes
                self.connection.reset_input_buffer()
                # Also clear our internal queues
                while not self._response_queue.empty():
                    try:
                        self._response_queue.get_nowait()
                    except:
                        break
                self.logger.debug("Buffers flushed")
            except Exception as e:
                self.logger.debug(f"Buffer flush error: {e}")

    def _read_startup_messages(self):
        """Read and log any startup messages"""
        deadline = time.time() + 0.5
        messages = []
        
        while time.time() < deadline:
            if self.connection.in_waiting > 0:
                try:
                    data = self.connection.readline()
                    if data:
                        msg = data.decode('utf-8', errors='ignore').strip()
                        if msg:
                            messages.append(msg)
                            self.logger.info(f"Arduino: {msg}")
                except:
                    pass
            else:
                time.sleep(0.05)
        
        if not messages:
            self.logger.debug("No startup messages received")

    def _test_communication(self) -> bool:
        """Test basic communication with Arduino"""
        response = self._send_command("I")
        return response and "SMT_BATCH_TESTER" in response
    
    def test_communication(self) -> bool:
        """Public method to test communication - just checks if connected"""
        # Connection already tested during connect(), so just return connection status
        return self.is_connected()
    
    def _calculate_checksum(self, data: str) -> int:
        """Calculate XOR checksum for a string"""
        checksum = 0
        for char in data:
            checksum ^= ord(char)
        return checksum
    
    def _add_protocol_wrapper(self, command: str) -> str:
        """Add sequence number and checksum to command"""
        if not self._enable_checksums:
            return command
            
        # Increment sequence number
        self._sequence_number = (self._sequence_number + 1) % 65536
        
        # Add sequence number
        cmd_with_seq = f"{command}:SEQ={self._sequence_number}"
        
        # Calculate and add checksum
        checksum = self._calculate_checksum(cmd_with_seq)
        return f"{cmd_with_seq}:CHK={checksum:X}"
    
    def _validate_response(self, response: str) -> tuple[bool, str, int]:
        """Validate response checksum and extract data
        Returns: (is_valid, clean_response, sequence_number)
        """
        if not self._enable_checksums or ":CHK=" not in response:
            return (True, response, 0)
        
        try:
            # Find the checksum and END marker
            chk_index = response.rfind(":CHK=")
            end_index = response.rfind(":END")
            
            if chk_index == -1 or end_index == -1 or end_index <= chk_index:
                self.logger.warning(f"Invalid response format: {response}")
                return (False, response, 0)
            
            # Extract parts
            data_with_seq = response[:chk_index]
            checksum_str = response[chk_index+5:end_index]
            
            # Calculate expected checksum
            expected_checksum = self._calculate_checksum(data_with_seq)
            received_checksum = int(checksum_str, 16)
            
            if expected_checksum != received_checksum:
                self.logger.warning(f"Checksum mismatch: expected {expected_checksum:X}, got {checksum_str}")
                return (False, response, 0)
            
            # Extract sequence number and handle CMDSEQ if present
            seq_num = 0
            clean_data = data_with_seq
            
            # First, remove CMDSEQ if present (command echo from firmware)
            cmdseq_index = clean_data.find(":CMDSEQ=")
            if cmdseq_index > 0:
                # Find the end of CMDSEQ value
                cmdseq_end = clean_data.find(":", cmdseq_index + 8)
                if cmdseq_end == -1:
                    cmdseq_end = len(clean_data)
                # Remove the CMDSEQ portion
                clean_data = clean_data[:cmdseq_index] + clean_data[cmdseq_end:]
                self.logger.debug(f"Removed CMDSEQ from response")
            
            # Now extract SEQ if present
            seq_index = clean_data.rfind(":SEQ=")
            if seq_index > 0:
                # Find the end of SEQ value
                seq_end = clean_data.find(":", seq_index + 5)
                if seq_end == -1:
                    seq_end = len(clean_data)
                seq_str = clean_data[seq_index+5:seq_end]
                seq_num = int(seq_str)
                clean_data = clean_data[:seq_index]
            
            return (True, clean_data, seq_num)
            
        except Exception as e:
            self.logger.error(f"Error validating response: {e}")
            return (False, response, 0)

    def get_firmware_type(self) -> str:
        """Get the firmware type of connected Arduino"""
        try:
            response = self._send_command("I")
            if response:
                response_upper = response.upper()
                if "SMT" in response_upper:  # Covers SMT_BATCH_TESTER, SMT_SIMPLE_TESTER, etc.
                    return "SMT"
                elif "OFFROAD" in response_upper:
                    return "OFFROAD"
            return "UNKNOWN"
        except Exception as e:
            self.logger.error(f"Error getting firmware type: {e}")
            return "UNKNOWN"

    def _send_command(self, command: str, timeout: float = None) -> Optional[str]:
        """Send command to Arduino and get response with optional checksum validation"""
        if not self.is_connected():
            return None
            
        if timeout is None:
            timeout = self.command_timeout
        
        with self._command_lock:
            # Retry loop for checksum failures
            for attempt in range(self.max_retries):
                try:
                    # Clear any stale responses
                    while not self._response_queue.empty():
                        self._response_queue.get_nowait()
                    
                    # Signal that we're expecting a response
                    self._expecting_response = True
                    
                    # Clear input buffer
                    self.connection.reset_input_buffer()
                    
                    # Small delay to ensure serial line is idle
                    time.sleep(0.02)
                    
                    # Add protocol wrapper if enabled
                    wrapped_command = self._add_protocol_wrapper(command)
                    
                    # Send command
                    cmd_bytes = f"{wrapped_command}\n".encode()
                    self.logger.debug(f"Sending: {wrapped_command}")
                    self.connection.write(cmd_bytes)
                    self.connection.flush()
                    
                    # Wait for response with timeout
                    try:
                        raw_response = self._response_queue.get(timeout=timeout)
                        self.logger.debug(f"Received raw: {raw_response}")
                        
                        # Validate response
                        is_valid, clean_response, seq_num = self._validate_response(raw_response)
                        
                        if is_valid:
                            # Check sequence number matches if checksums enabled
                            if self._enable_checksums and seq_num != self._sequence_number:
                                self.logger.warning(f"Sequence mismatch: expected {self._sequence_number}, got {seq_num}")
                                # Continue anyway - sequence mismatch is less critical than checksum
                            
                            self.logger.debug(f"Valid response: {clean_response}")
                            return clean_response
                        else:
                            self.logger.warning(f"Invalid response on attempt {attempt + 1}")
                            if attempt < self.max_retries - 1:
                                time.sleep(self.retry_delay)
                                continue
                            else:
                                return None
                                
                    except queue.Empty:
                        self.logger.warning(f"No response to command: {command} (attempt {attempt + 1})")
                        if attempt < self.max_retries - 1:
                            time.sleep(self.retry_delay)
                            continue
                        return None
                        
                except Exception as e:
                    self.logger.error(f"Command error: {e}")
                    return None
                finally:
                    self._expecting_response = False
                    
            return None  # All retries failed

    def test_panel(self) -> Dict[int, Optional[Dict[str, float]]]:
        """Test entire panel with single command"""
        # Increased timeout to 3.0 seconds to handle 8-16 relays
        response = self._send_command("TX:ALL", timeout=3.0)
        
        if not response:
            self.logger.error("No response from panel test - possible power loss or Arduino hang")
            # Send an 'X' command to reset Arduino state
            self._send_command("X", timeout=0.5)
            return {}
        
        # Check for INA260 failure
        if response == "ERROR:INA260_FAIL":
            self.logger.error("INA260 sensor failure detected during panel test")
            # Notify via callback if available
            if self.error_callback:
                self.error_callback("INA260_FAIL", "Current sensor failure detected. Check I2C connections.")
            return {}
        
        # Check for other errors
        if response.startswith("ERROR:"):
            error_type = response[6:]
            self.logger.error(f"Arduino error: {error_type}")
            if self.error_callback:
                self.error_callback(error_type, f"Arduino reported error: {error_type}")
            return {}
        
        if not response.startswith("PANELX:"):
            self.logger.error(f"Invalid panel test response: {response}")
            return {}
        
        try:
            results = {}
            data = response[7:]  # Remove "PANELX:"
            
            # Parse format: 1=12.5,3.2;2=12.4,3.1;...
            relay_data_list = data.split(";")
            for relay_data in relay_data_list:
                if "=" in relay_data:
                    relay_str, values = relay_data.split("=", 1)
                    relay_num = int(relay_str)
                    
                    if "," in values:
                        voltage_str, current_str = values.split(",", 1)
                        try:
                            voltage = float(voltage_str)
                            current = float(current_str)
                            
                            # Basic sanity check
                            if -100 < voltage < 100 and -10 < current < 10:
                                results[relay_num] = {
                                    'voltage': voltage,
                                    'current': current,
                                    'power': voltage * current
                                }
                            else:
                                self.logger.error(f"Invalid values for relay {relay_num}: {voltage}V, {current}A")
                                results[relay_num] = None
                        except ValueError:
                            self.logger.error(f"Failed to parse relay {relay_num} data: {relay_data}")
                            results[relay_num] = None
                    else:
                        self.logger.error(f"Invalid format for relay {relay_num}: {relay_data}")
                        results[relay_num] = None
                else:
                    self.logger.error(f"Invalid relay data format: {relay_data}")
            
            successful = len([r for r in results.values() if r])
            total_relays = len(results)
            self.logger.info(f"Panel test complete: {successful}/{total_relays} relays measured")
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to parse panel response: {e}")
            return {}

    def test_panel_stream(self, progress_callback=None) -> Dict[int, Optional[Dict[str, float]]]:
        """Test panel with streaming updates for progress feedback"""
        if not self.is_connected():
            return {}
            
        # Pause reading thread
        was_reading = self.is_reading
        if was_reading:
            self.stop_reading()
            # Give time for thread to fully stop
            time.sleep(0.1)
        
        try:
            # Send command
            self.connection.reset_input_buffer()
            self.connection.write(b"TS\n")
            self.connection.flush()
            
            results = {}
            deadline = time.time() + 5.0
            complete = False
            
            while time.time() < deadline and not complete:
                if self.connection.in_waiting > 0:
                    line = self.connection.readline()
                    if line:
                        response = line.decode('utf-8', errors='ignore').strip()
                        
                        if response.startswith("RELAY:"):
                            # Parse RELAY:1,12.847,3.260
                            try:
                                data = response[6:]
                                parts = data.split(",")
                                if len(parts) >= 3:
                                    relay_num = int(parts[0])
                                    voltage = float(parts[1])
                                    current = float(parts[2])
                                    
                                    measurement = {
                                        'voltage': voltage,
                                        'current': current,
                                        'power': voltage * current
                                    }
                                    
                                    results[relay_num] = measurement
                                    
                                    if progress_callback:
                                        try:
                                            progress_callback(relay_num, measurement)
                                        except:
                                            pass
                                            
                            except Exception as e:
                                self.logger.error(f"Failed to parse: {response}")
                                
                        elif response == "PANEL_COMPLETE":
                            self.logger.info("Panel stream test complete")
                            complete = True
                            
                time.sleep(0.01)
            
            if not complete:
                self.logger.warning("Panel stream test timed out")
            
            return results
            
        finally:
            # Resume reading thread
            if was_reading:
                self.start_reading()

    def all_relays_off(self) -> bool:
        """Turn off all relays"""
        response = self._send_command("X")
        return response and "ALL_OFF" in response

    def get_button_status(self) -> Optional[str]:
        """Get current button status"""
        response = self._send_command("B")
        if response and response.startswith("BUTTON:"):
            return response[7:]
        return None

    def get_firmware_info(self) -> Optional[str]:
        """Get firmware identification"""
        return self._send_command("I")
    
    def get_supply_voltage(self, retry_count: int = 3) -> Optional[float]:
        """Get current supply voltage without activating relays with retry on corruption"""
        for attempt in range(retry_count):
            # Clear buffer before sending to avoid partial reads
            if self.connection and self.connection.is_open:
                self.connection.reset_input_buffer()
                time.sleep(0.02)  # Let buffer clear
            
            # Use the new V command that doesn't activate any relays
            response = self._send_command("V", timeout=0.5)
            
            if not response:
                if attempt < retry_count - 1:
                    self.logger.debug(f"No response to V command (attempt {attempt + 1}/{retry_count})")
                    time.sleep(0.05)  # Wait before retry
                continue
                
            # Expected format: "VOLTAGE:13.200"
            try:
                if response.startswith("VOLTAGE:") and len(response) >= 9:
                    voltage_str = response[8:]  # Remove "VOLTAGE:"
                    voltage = float(voltage_str.strip())
                    
                    # Sanity check
                    if 0 < voltage < 30:  # Reasonable voltage range
                        return voltage
                    else:
                        self.logger.warning(f"Voltage {voltage}V outside reasonable range")
                else:
                    # Log corruption patterns for debugging
                    if "VOLT" in response or response == "V":
                        self.logger.debug(f"Corrupted voltage response: '{response}' (attempt {attempt + 1}/{retry_count})")
                        # Clear buffer after corruption
                        if self.connection and self.connection.is_open:
                            self.connection.reset_input_buffer()
                    else:
                        self.logger.error(f"Unexpected response format: '{response}'")
                    
            except Exception as e:
                self.logger.debug(f"Failed to parse voltage from '{response}': {e} (attempt {attempt + 1}/{retry_count})")
            
            # Wait longer before retry if not last attempt
            if attempt < retry_count - 1:
                time.sleep(0.1)
        
        self.logger.warning(f"Failed to get valid voltage after {retry_count} attempts")
        return None

    def set_button_callback(self, callback: Optional[Callable[[str], None]]):
        """Set callback for button events"""
        self.button_callback = callback
    
    def set_checksum_enabled(self, enabled: bool):
        """Enable or disable checksum protocol for backward compatibility"""
        self._enable_checksums = enabled
        self.logger.info(f"Checksum protocol {'enabled' if enabled else 'disabled'}")

    def start_reading(self):
        """Start background thread for button events"""
        if self.is_reading:
            return
            
        self._stop_reading.clear()
        self.is_reading = True
        self._reading_thread = threading.Thread(target=self._reading_loop)
        self._reading_thread.daemon = True
        self._reading_thread.start()
        self.logger.info("Started reading thread")

    def stop_reading(self):
        """Stop background thread"""
        if not self.is_reading:
            return
            
        self.logger.info("Stopping reading thread...")
        self._stop_reading.set()
        self.is_reading = False
        
        if self._reading_thread and self._reading_thread.is_alive():
            self._reading_thread.join(timeout=2.0)
            
        self.logger.info("Reading thread stopped")

    def _reading_loop(self):
        """Background thread to read all serial data and route appropriately"""
        while not self._stop_reading.is_set():
            try:
                if self.connection and self.connection.is_open:
                    # Use non-blocking check with very short timeout
                    old_timeout = self.connection.timeout
                    self.connection.timeout = 0.05
                    
                    try:
                        data = self.connection.readline()
                        if data:
                            message = data.decode('utf-8', errors='ignore').strip()
                            if message:
                                # Route the message appropriately
                                if message.startswith("EVENT:"):
                                    # Handle events - these don't have checksums
                                    event_type = message[6:]
                                    if event_type.startswith("BUTTON_") and self.button_callback:
                                        self.logger.info(f"Button event: {event_type}")
                                        # Extract just the state (PRESSED/RELEASED)
                                        state = event_type.replace("BUTTON_", "")
                                        self.button_callback(state)
                                elif self._expecting_response:
                                    # This is a response to a command - put raw message with checksum
                                    self._response_queue.put(message)
                                else:
                                    # Unexpected message - could be a delayed response
                                    # For messages with checksums, validate before ignoring
                                    if ":CHK=" in message and self._enable_checksums:
                                        is_valid, clean_msg, _ = self._validate_response(message)
                                        if is_valid:
                                            # Common responses we can safely ignore
                                            if clean_msg in ["OK:ALL_OFF", "PANEL_COMPLETE"] or clean_msg.startswith(("VOLTAGE:", "RELAY:", "PANEL:", "PANELX:", "ID:")):
                                                self.logger.debug(f"Ignoring delayed response: {clean_msg}")
                                            else:
                                                self.logger.debug(f"Unexpected message: {clean_msg}")
                                        else:
                                            self.logger.debug(f"Ignoring corrupted message")
                                    else:
                                        # Legacy format or checksums disabled
                                        if message in ["OK:ALL_OFF", "PANEL_COMPLETE"] or message.startswith(("VOLTAGE:", "RELAY:", "PANEL:", "ID:")):
                                            self.logger.debug(f"Ignoring delayed response: {message}")
                                        else:
                                            self.logger.debug(f"Unexpected message: {message}")
                    finally:
                        self.connection.timeout = old_timeout
            except Exception as e:
                if not self._stop_reading.is_set():
                    self.logger.error(f"Reading thread error: {e}")
                
            time.sleep(0.01)

    # Compatibility methods for existing code
    def configure_sensors(self, sensor_configs) -> bool:
        """SMT Arduino has fixed sensors - no configuration needed"""
        return True
    
    def pause_reading_for_test(self):
        """Compatibility method - reading thread must stay active in new architecture"""
        # In the new queue-based architecture, the reading thread MUST continue running
        # to route command responses to the queue. Button events during tests are harmless
        # as they'll be ignored if a test is already running.
        self.logger.debug("pause_reading_for_test called - keeping thread active")
    
    def resume_reading_after_test(self):
        """Compatibility method - reading thread should already be active"""
        # Thread should never be stopped, so nothing to resume
        self.logger.debug("resume_reading_after_test called - thread already active")
    
    @property
    def serial(self):
        """Compatibility property for code expecting 'serial' attribute"""
        class SerialWrapper:
            def __init__(self, controller):
                self.controller = controller
            
            def flush_buffers(self):
                self.controller._flush_buffers()
        # Enable parameter removed - not used in implementation
        return SerialWrapper(self)
    
    def get_board_info(self) -> Optional[str]:
        """Alias for get_firmware_info() for compatibility"""
        return self.get_firmware_info()
    
    def query(self, command: str, response_timeout: float = None) -> Optional[str]:
        """Compatibility method for query - same as send_command"""
        return self._send_command(command, timeout=response_timeout)
    
    def send_command(self, command: str, timeout: float = None) -> Optional[str]:
        """Public wrapper for _send_command for compatibility"""
        return self._send_command(command, timeout)
    
    def set_error_callback(self, callback: Callable[[str, str], None]):
        """Set callback for error events (error_type, message)"""
        self.error_callback = callback
    
    # Legacy method stubs for backward compatibility
    def measure_relay(self, relay_num: int):
        """DEPRECATED: Use test_panel() instead"""
        raise NotImplementedError(
            "Individual relay measurement no longer supported. "
            "Use test_panel() to measure all 8 relays at once."
        )
    
    def measure_relays(self, relay_list):
        """DEPRECATED: Use test_panel() instead"""
        raise NotImplementedError(
            "Individual relay measurement no longer supported. "
            "Use test_panel() to measure all 8 relays at once."
        )


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    controller = SMTArduinoController()
    
    if controller.connect("COM7"):
        # Test panel
        print("\nTesting panel (batch mode)...")
        results = controller.test_panel()
        
        for relay, data in results.items():
            if data:
                print(f"Relay {relay}: {data['voltage']:.3f}V, {data['current']:.3f}A")
            else:
                print(f"Relay {relay}: FAILED")
        
        # Test with progress
        print("\nTesting panel with progress...")
        def progress(relay, measurement):
            print(f"  Relay {relay}: {measurement['voltage']:.3f}V")
        
        results = controller.test_panel_stream(progress)
        
        controller.disconnect()
