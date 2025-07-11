"""
SMT Arduino Controller - TESTSEQ Protocol Implementation
Version 3.0.0 - Simultaneous relay activation with timing control

This version implements the TESTSEQ protocol for simultaneous relay
activation with precise timing control using PCF8575 I2C expander.

Key changes from v2.x:
- Added execute_test_sequence() for new TESTSEQ protocol
- Support for comma-separated relay groups
- Parse TESTRESULTS batch response format
- Command validation for relay numbers and timing
- Backward compatible with existing methods
"""

import time
import logging
import serial
import threading
import queue
from typing import Dict, Optional, Callable, List, Any
from src.services.port_registry import port_registry

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
        
        # I2C device status tracking
        self._i2c_status = {"PCF8575": None, "INA260": None}

    def connect(self, port: str) -> bool:
        """Connect to Arduino on specified port"""
        try:
            # Check if port is already in use
            if port_registry.is_port_in_use(port):
                self.logger.warning(f"Port {port} is already in use by another component")
                return False
            
            # Try to acquire the port exclusively
            if not port_registry.acquire_port(port):
                self.logger.error(f"Failed to acquire port {port}")
                return False
            
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
            except Exception as e:
                # If connection fails, release the port
                port_registry.release_port(port)
                raise
            
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
            # NOTE: Arduino firmware v1.0.x has sequence sync issues, v1.1.0+ fixes this
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
            # Make sure to release port if we acquired it
            if port_registry.is_port_in_use(port):
                port_registry.release_port(port)
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
        
        # Release the port in the registry
        if self.port:
            port_registry.release_port(self.port)
            self.logger.debug(f"Released port {self.port} from registry")
        
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
        """Read and log any startup messages including I2C status"""
        deadline = time.time() + 0.5  # Extended to capture I2C messages
        messages = []
        i2c_status = {"PCF8575": None, "INA260": None}
        i2c_errors = []
        
        while time.time() < deadline:
            if self.connection.in_waiting > 0:
                try:
                    data = self.connection.readline()
                    if data:
                        msg = data.decode('utf-8', errors='ignore').strip()
                        if msg:
                            messages.append(msg)
                            
                            # Parse I2C status messages
                            if msg.startswith("I2C:"):
                                self._parse_i2c_message(msg, i2c_status, i2c_errors)
                                self.logger.info(f"Arduino I2C: {msg}")
                            else:
                                self.logger.debug(f"Arduino: {msg}")
                except:
                    pass
            else:
                time.sleep(0.05)
        
        # Report I2C status summary
        if i2c_errors:
            self.logger.error("I2C initialization errors detected:")
            for error in i2c_errors:
                self.logger.error(f"  - {error}")
        
        # Store I2C status for later queries
        self._i2c_status = i2c_status
        
        if not messages:
            self.logger.debug("No startup messages received")
    
    def _parse_i2c_message(self, msg: str, status: dict, errors: list):
        """Parse I2C status messages from Arduino"""
        try:
            if "PCF8575:OK" in msg:
                status["PCF8575"] = "OK"
            elif "PCF8575:FAIL" in msg:
                status["PCF8575"] = "FAIL"
                errors.append("PCF8575 (relay controller) at 0x20 failed to initialize")
            elif "INA260:OK" in msg:
                status["INA260"] = "OK"
            elif "INA260:FAIL" in msg:
                status["INA260"] = "FAIL"
                errors.append("INA260 (power monitor) at 0x40 failed to initialize")
            elif "INIT:COMPLETE" in msg:
                # Parse summary line
                if "PCF8575_FAIL" in msg:
                    status["PCF8575"] = "FAIL"
                    if "PCF8575 (relay controller) at 0x20 failed to initialize" not in errors:
                        errors.append("PCF8575 (relay controller) at 0x20 failed - no relay control available")
                if "INA260_FAIL" in msg:
                    status["INA260"] = "FAIL"
                    if "INA260 (power monitor) at 0x40 failed to initialize" not in errors:
                        errors.append("INA260 (power monitor) at 0x40 failed - no power measurements available")
        except Exception as e:
            self.logger.debug(f"Error parsing I2C message '{msg}': {e}")

    def _test_communication(self) -> bool:
        """Test basic communication with Arduino"""
        response = self._send_command("I")
        return response and "SMT_TESTER" in response
    
    def test_communication(self) -> bool:
        """Public method to test communication - just checks if connected"""
        # Connection already tested during connect(), so just return connection status
        return self.is_connected()
    
    def get_i2c_status(self) -> dict:
        """Get current I2C device status"""
        # Try to get fresh status if connected
        if self.is_connected():
            response = self._send_command("I2C_STATUS", timeout=0.5)
            if response and response.startswith("I2C_STATUS:"):
                # Parse response like "I2C_STATUS:PCF8575@0x20=OK,INA260@0x40=OK"
                try:
                    parts = response[11:].split(",")  # Remove "I2C_STATUS:"
                    for part in parts:
                        if "PCF8575" in part:
                            self._i2c_status["PCF8575"] = "OK" if "=OK" in part else "FAIL"
                        elif "INA260" in part:
                            self._i2c_status["INA260"] = "OK" if "=OK" in part else "FAIL"
                except:
                    pass
        
        return self._i2c_status.copy()
    
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
                                # TEMPORARY: Accept Arduino's seq or seq+1 due to firmware counting behavior
                                # TODO: Remove this workaround after Arduino firmware v1.1.0 is deployed
                                expected_plus_one = (self._sequence_number + 1) % 65536
                                if seq_num != expected_plus_one:
                                    self.logger.warning(f"Sequence mismatch: expected {self._sequence_number} or {expected_plus_one}, got {seq_num}")
                                else:
                                    # Log at debug level when we get the expected+1 pattern
                                    self.logger.debug(f"Sequence offset detected: expected {self._sequence_number}, got {seq_num} (firmware v1.0.x behavior)")
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

    def test_panel(self, relay_list: Optional[List[int]] = None) -> Dict[int, Optional[Dict[str, float]]]:
        """Test entire panel with single command
        
        Args:
            relay_list: Optional list of relay numbers to test. If None, tests all relays.
        """
        # Build command based on relay list
        if relay_list:
            # Sort and format relay list (e.g., [1,2,3,4] -> "TX:1,2,3,4")
            relay_str = ",".join(str(r) for r in sorted(relay_list))
            command = f"TX:{relay_str}"
        else:
            command = "TX:ALL"
            
        # Increased timeout to 3.0 seconds to handle 8-16 relays
        response = self._send_command(command, timeout=3.0)
        
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
    
    # New TESTSEQ protocol methods
    def execute_test_sequence(self, relay_mapping: Dict, test_sequence: List[Dict]) -> Dict[str, Any]:
        """Execute complete test sequence based on SKU configuration
        
        Args:
            relay_mapping: SKU relay mapping with comma-separated groups
                          e.g., {"1,2,3": {"board": 1, "function": "mainbeam"}}
            test_sequence: List of test configurations by function
                          e.g., [{"function": "mainbeam", "duration_ms": 500, "delay_after_ms": 100}]
        
        Returns:
            Complete test results with board/function context:
            {
                "success": True/False,
                "results": {
                    "1": {  # board number
                        "mainbeam": {"voltage": 12.5, "current": 6.8, "power": 85.0},
                        "position": {"voltage": 12.4, "current": 1.0, "power": 12.4}
                    }
                },
                "errors": []
            }
        """
        if not self.is_connected():
            return {"success": False, "results": {}, "errors": ["Not connected"]}
        
        try:
            # Parse relay mapping to extract groups
            relay_groups = self._parse_relay_mapping(relay_mapping)
            
            # Build TESTSEQ command
            command = self._build_testseq_command(relay_groups, test_sequence)
            
            # Log the exact command being sent for debugging
            self.logger.info(f"Sending TESTSEQ command: {command}")
            
            # Validate command before sending
            validation_errors = self._validate_testseq_command(relay_groups, test_sequence)
            if validation_errors:
                return {"success": False, "results": {}, "errors": validation_errors}
            
            # Send command with extended timeout for long sequences
            timeout = self._calculate_sequence_timeout(test_sequence)
            response = self._send_command(command, timeout=timeout)
            
            if not response:
                return {"success": False, "results": {}, "errors": ["No response from Arduino"]}
            
            # Check for immediate ACK response
            if response == "ACK":
                self.logger.debug("Received ACK, waiting for TESTRESULTS...")
                # Re-enable expecting response for TESTRESULTS
                self._expecting_response = True
                try:
                    # Wait for the actual TESTRESULTS response
                    raw_response = self._response_queue.get(timeout=timeout)
                    self.logger.debug(f"Received raw: {raw_response}")
                    
                    # Validate response
                    is_valid, clean_response, seq_num = self._validate_response(raw_response)
                    
                    if is_valid:
                        response = clean_response
                    else:
                        return {"success": False, "results": {}, "errors": ["Invalid TESTRESULTS response after ACK"]}
                except Exception as e:
                    self.logger.error(f"Error waiting for TESTRESULTS: {e}")
                    return {"success": False, "results": {}, "errors": ["No TESTRESULTS after ACK"]}
                finally:
                    # Ensure flag is cleared even if there's an error
                    self._expecting_response = False
            
            # Parse response
            if response.startswith("ERROR:"):
                error_msg = response[6:]
                return {"success": False, "results": {}, "errors": [f"Arduino error: {error_msg}"]}
            
            if not response.startswith("TESTRESULTS:"):
                return {"success": False, "results": {}, "errors": [f"Invalid response format: {response}"]}
            
            # Parse TESTRESULTS and map back to boards/functions
            results = self._parse_testresults(response, relay_groups, test_sequence)
            
            return {"success": True, "results": results, "errors": []}
            
        except Exception as e:
            self.logger.error(f"Test sequence execution error: {e}")
            return {"success": False, "results": {}, "errors": [str(e)]}
    
    def _parse_relay_mapping(self, relay_mapping: Dict) -> Dict[str, Dict]:
        """Parse relay mapping, handling comma-separated groups
        
        Returns:
            Dict mapping relay group string to metadata
            e.g., {"1,2,3": {"board": 1, "function": "mainbeam"}}
        """
        relay_groups = {}
        
        for relay_str, metadata in relay_mapping.items():
            if metadata:  # Skip null/empty mappings
                # Normalize relay string (remove spaces)
                normalized = relay_str.replace(" ", "")
                relay_groups[normalized] = metadata
        
        return relay_groups
    
    def _build_testseq_command(self, relay_groups: Dict, test_sequence: List[Dict]) -> str:
        """Build TESTSEQ command by walking through relay mapping in order
        
        Example output: "TESTSEQ:1:500;OFF:100;2:500;OFF:100;7,8,9:500"
        """
        command_parts = []
        
        # Build a map of functions to their timing parameters
        function_timing = {}
        for test_step in test_sequence:
            function = test_step["function"]
            function_timing[function] = {
                "duration_ms": test_step["duration_ms"],
                "delay_after_ms": test_step.get("delay_after_ms", 0)
            }
        
        # Sort relay groups by their first relay number to maintain order
        sorted_relay_groups = []
        for relay_str, metadata in relay_groups.items():
            # Extract first relay number for sorting
            first_relay = int(relay_str.split(',')[0])
            sorted_relay_groups.append((first_relay, relay_str, metadata))
        
        # Sort by first relay number
        sorted_relay_groups.sort(key=lambda x: x[0])
        
        # Walk through relay mappings in order
        for i, (_, relay_str, metadata) in enumerate(sorted_relay_groups):
            function = metadata.get("function")
            
            # Get timing for this function
            if function in function_timing:
                timing = function_timing[function]
                duration = timing["duration_ms"]
                delay_after = timing["delay_after_ms"]
                
                # Add relay activation step
                command_parts.append(f"{relay_str}:{duration}")
                
                # Always add OFF command between relays
                # Use the specified delay, or 0 if not specified
                if i < len(sorted_relay_groups) - 1:  # Not the last relay
                    command_parts.append(f"OFF:{delay_after}")
        
        # Always add a final OFF command to ensure clean shutdown
        if sorted_relay_groups:  # If we have any relays
            command_parts.append("OFF:0")
        
        return "TESTSEQ:" + ";".join(command_parts)
    
    def _parse_testresults(self, response: str, relay_groups: Dict, test_sequence: List[Dict]) -> Dict:
        """Parse TESTRESULTS response and map back to boards/functions
        
        Response format: "TESTRESULTS:1,2,3:12.5V,6.8A;7,8,9:12.4V,6.7A;END"
        
        Returns:
            Dict organized by board number and function
        """
        results = {}
        
        # Remove prefix and suffix
        if not response.startswith("TESTRESULTS:") or not response.endswith(";END"):
            self.logger.error(f"Invalid TESTRESULTS format: {response}")
            return results
        
        data = response[12:-4]  # Remove "TESTRESULTS:" and ";END"
        
        # Parse each measurement
        measurements = data.split(";")
        
        for measurement in measurements:
            if ":" not in measurement:
                continue
                
            parts = measurement.split(":", 1)
            if len(parts) != 2:
                continue
                
            relay_str = parts[0]
            values_str = parts[1]
            
            # Parse voltage and current
            if "V," in values_str and values_str.endswith("A"):
                try:
                    voltage_str = values_str.split("V,")[0]
                    current_str = values_str.split("V,")[1][:-1]  # Remove 'A'
                    
                    voltage = float(voltage_str)
                    current = float(current_str)
                    
                    # Find which board and function this relay group belongs to
                    if relay_str in relay_groups:
                        metadata = relay_groups[relay_str]
                        board = metadata.get("board", 1)
                        function = metadata.get("function", "unknown")
                        
                        # Initialize board results if needed
                        if board not in results:
                            results[board] = {}
                        
                        # Store measurement
                        results[board][function] = {
                            "voltage": voltage,
                            "current": current,
                            "power": voltage * current
                        }
                        
                except (ValueError, IndexError) as e:
                    self.logger.error(f"Failed to parse measurement '{measurement}': {e}")
        
        return results
    
    def _validate_testseq_command(self, relay_groups: Dict, test_sequence: List[Dict]) -> List[str]:
        """Validate relay numbers and timing parameters
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        all_relays = set()
        
        # Check relay numbers
        for relay_str in relay_groups.keys():
            relays = [int(r) for r in relay_str.split(",")]
            
            for relay in relays:
                if relay < 1 or relay > 16:
                    errors.append(f"Invalid relay number: {relay} (must be 1-16)")
                
                if relay in all_relays:
                    errors.append(f"Relay {relay} appears in multiple groups")
                
                all_relays.add(relay)
        
        # Check timing
        total_time = 0
        for test_step in test_sequence:
            duration = test_step.get("duration_ms", 0)
            delay_after = test_step.get("delay_after_ms", 0)
            
            if duration < 100:
                errors.append(f"Duration {duration}ms too short (minimum 100ms)")
            
            total_time += duration + delay_after
        
        if total_time > 30000:
            errors.append(f"Total sequence time {total_time}ms exceeds 30 second limit")
        
        return errors
    
    def _calculate_sequence_timeout(self, test_sequence: List[Dict]) -> float:
        """Calculate appropriate timeout for test sequence"""
        total_ms = 0
        
        for test_step in test_sequence:
            total_ms += test_step.get("duration_ms", 0)
            total_ms += test_step.get("delay_after_ms", 0)
        
        # Add 2 seconds buffer for communication overhead
        return (total_ms / 1000.0) + 2.0
    
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
        # Example SKU configuration
        relay_mapping = {
            "1,2,3": {"board": 1, "function": "mainbeam"},
            "4": {"board": 1, "function": "position"},
            "5,6": {"board": 1, "function": "turn_signal"},
            "7,8,9": {"board": 2, "function": "mainbeam"},
            "10": {"board": 2, "function": "position"},
            "11,12": {"board": 2, "function": "turn_signal"}
        }
        
        test_sequence = [
            {
                "function": "mainbeam",
                "duration_ms": 500,
                "delay_after_ms": 100,
                "limits": {
                    "current_a": {"min": 5.4, "max": 6.9},
                    "voltage_v": {"min": 11.5, "max": 12.5}
                }
            },
            {
                "function": "position",
                "duration_ms": 300,
                "delay_after_ms": 100,
                "limits": {
                    "current_a": {"min": 0.8, "max": 1.2},
                    "voltage_v": {"min": 11.5, "max": 12.5}
                }
            }
        ]
        
        # Test new TESTSEQ protocol
        print("\nTesting with TESTSEQ protocol...")
        result = controller.execute_test_sequence(relay_mapping, test_sequence)
        
        if result["success"]:
            print("Test successful!")
            for board, functions in result["results"].items():
                print(f"\nBoard {board}:")
                for function, data in functions.items():
                    print(f"  {function}: {data['voltage']:.1f}V, {data['current']:.1f}A")
        else:
            print(f"Test failed: {result['errors']}")
        
        # Legacy test panel method still works
        print("\nLegacy test panel method...")
        results = controller.test_panel()
        
        controller.disconnect()
