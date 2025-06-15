import serial
import serial.tools.list_ports
import time
import logging
from typing import List, Optional, Union, Tuple
import threading
from src.utils.resource_manager import ResourceMixin, get_resource_tracker
from src.utils.crc16 import get_crc_calculator


class SerialManager(ResourceMixin):
    """Manages serial communication with devices supporting both text and binary framing protocols"""

    def __init__(self, baud_rate: int = 9600, timeout: float = 5.0, write_timeout: float = 5.0, 
                 enable_crc: bool = False, enable_framing: bool = False):
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self.connection: Optional[serial.Serial] = None
        self.port: Optional[str] = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self._lock = threading.Lock()
        
        # CRC-16 support (Phase 2.1)
        self.crc_enabled = enable_crc
        self.crc_calculator = get_crc_calculator() if enable_crc else None
        self.crc_error_count = 0
        self.total_message_count = 0
        
        # Binary framing support (Phase 3)
        self.framing_enabled = enable_framing
        self.frame_protocol = None
        self.frame_error_count = 0
        self.total_frame_count = 0
        
        if enable_framing:
            from src.protocols.frame_protocol import FrameProtocol
            self.frame_protocol = FrameProtocol()

    def get_available_ports(self) -> List[str]:
        """Get list of available COM ports"""
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append(port.device)
        return ports

    def connect(self, port: str) -> bool:
        """Connect to specified COM port"""
        try:
            with self._lock:
                if self.connection and self.connection.is_open:
                    self.disconnect()

                self.connection = serial.Serial(
                    port=port,
                    baudrate=self.baud_rate,
                    timeout=self.timeout,
                    write_timeout=self.write_timeout,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE
                )

                # Reduce or remove sleep after connection
                # time.sleep(0.05)  # Remove or reduce to 0.01
                
                # Only clear buffers if data exists
                if self.connection.in_waiting > 0:
                    self.connection.reset_input_buffer()
                    self.connection.reset_output_buffer()

                self.port = port
                self.logger.info(f"Connected to {port} at {self.baud_rate} baud")
                return True

        except serial.SerialException as e:
            self.logger.error(f"Failed to connect to {port}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error connecting to {port}: {e}")
            return False

    def disconnect(self):
        """Disconnect from current port"""
        try:
            with self._lock:
                if self.connection and self.connection.is_open:
                    self.connection.close()
                    self.logger.info(f"Disconnected from {self.port}")
                self.connection = None
                self.port = None
        except Exception as e:
            self.logger.error(f"Error disconnecting: {e}")

    def is_connected(self) -> bool:
        """Check if currently connected"""
        with self._lock:
            return self.connection is not None and self.connection.is_open

    def write(self, data: Union[str, bytes]) -> bool:
        """Write data to serial port"""
        if not self.is_connected():
            self.logger.error("Cannot write - not connected")
            return False

        try:
            with self._lock:
                if isinstance(data, str):
                    data = data.encode('utf-8')

                bytes_written = self.connection.write(data)
                self.connection.flush()

                self.logger.debug(f"Wrote {bytes_written} bytes: {data}")
                return True

        except serial.SerialTimeoutError:
            self.logger.error("Write timeout")
            return False
        except Exception as e:
            self.logger.error(f"Write error: {e}")
            return False

    def read_line(self, timeout: Optional[float] = None) -> Optional[str]:
        """Read a line from serial port"""
        if not self.is_connected():
            self.logger.error("Cannot read - not connected")
            return None

        try:
            with self._lock:
                original_timeout = self.connection.timeout
                if timeout is not None:
                    self.connection.timeout = timeout

                try:
                    line = self.connection.readline().decode('utf-8').strip()
                    if line:
                        self.logger.debug(f"Read: {line}")
                        return line
                    return None
                finally:
                    self.connection.timeout = original_timeout

        except serial.SerialTimeoutError:
            self.logger.debug("Read timeout")
            return None
        except UnicodeDecodeError as e:
            self.logger.error(f"Unicode decode error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Read error: {e}")
            return None

    def read_bytes(self, num_bytes: int, timeout: Optional[float] = None) -> Optional[bytes]:
        """Read specified number of bytes"""
        if not self.is_connected():
            self.logger.error("Cannot read - not connected")
            return None

        try:
            with self._lock:
                original_timeout = self.connection.timeout
                if timeout is not None:
                    self.connection.timeout = timeout

                try:
                    data = self.connection.read(num_bytes)
                    if data:
                        self.logger.debug(f"Read {len(data)} bytes: {data}")
                        return data
                    return None
                finally:
                    self.connection.timeout = original_timeout

        except Exception as e:
            self.logger.error(f"Read bytes error: {e}")
            return None

    def query(self, command: str, response_timeout: float = 2.0) -> Optional[str]:
        """Send command and wait for response with optional CRC validation"""
        if not self.write_with_crc(command + '\r\n'):
            return None

        # Small delay to ensure command is processed
        time.sleep(0.05)

        return self.read_line_with_crc(timeout=response_timeout)
    
    def write_with_crc(self, data: Union[str, bytes]) -> bool:
        """Write data with optional CRC-16 validation"""
        if not self.is_connected():
            self.logger.error("Cannot write - not connected")
            return False

        try:
            with self._lock:
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                
                # Add CRC if enabled
                if self.crc_enabled and self.crc_calculator:
                    # Remove trailing newline for CRC calculation, add it back after
                    message = data.rstrip('\r\n')
                    data_with_crc = self.crc_calculator.append_crc(message)
                    # Add newline back
                    data = data_with_crc + '\r\n'
                    self.logger.debug(f"Sending with CRC: {data_with_crc}")
                
                data_bytes = data.encode('utf-8')
                bytes_written = self.connection.write(data_bytes)
                self.connection.flush()

                self.logger.debug(f"Wrote {bytes_written} bytes: {data.strip()}")
                return True

        except serial.SerialTimeoutError:
            self.logger.error("Write timeout")
            return False
        except Exception as e:
            self.logger.error(f"Write error: {e}")
            return False
    
    def read_line_with_crc(self, timeout: Optional[float] = None) -> Optional[str]:
        """Read a line with optional CRC-16 validation"""
        if not self.is_connected():
            self.logger.error("Cannot read - not connected")
            return None

        try:
            with self._lock:
                original_timeout = self.connection.timeout
                if timeout is not None:
                    self.connection.timeout = timeout

                try:
                    line = self.connection.readline().decode('utf-8').strip()
                    if not line:
                        return None
                    
                    self.total_message_count += 1
                    
                    # Validate CRC if enabled
                    if self.crc_enabled and self.crc_calculator:
                        message, crc_valid = self.crc_calculator.extract_and_verify(line)
                        
                        if not crc_valid:
                            self.crc_error_count += 1
                            self.logger.warning(f"CRC validation failed for message: {line}")
                            return None
                        
                        self.logger.debug(f"Read with valid CRC: {message}")
                        return message
                    else:
                        self.logger.debug(f"Read: {line}")
                        return line
                        
                finally:
                    self.connection.timeout = original_timeout

        except serial.SerialTimeoutError:
            self.logger.debug("Read timeout")
            return None
        except UnicodeDecodeError as e:
            self.logger.error(f"Unicode decode error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Read error: {e}")
            return None

    def flush_buffers(self):
        """Clear input and output buffers"""
        if self.is_connected():
            with self._lock:
                self.connection.reset_input_buffer()
                self.connection.reset_output_buffer()
    
    def enable_crc(self, enabled: bool = True):
        """Enable or disable CRC-16 validation"""
        self.crc_enabled = enabled
        if enabled and not self.crc_calculator:
            self.crc_calculator = get_crc_calculator()
        self.logger.info(f"CRC validation {'enabled' if enabled else 'disabled'}")
    
    def get_crc_statistics(self) -> dict:
        """Get CRC error statistics"""
        if self.total_message_count == 0:
            error_rate = 0.0
        else:
            error_rate = (self.crc_error_count / self.total_message_count) * 100
            
        return {
            'crc_enabled': self.crc_enabled,
            'total_messages': self.total_message_count,
            'crc_errors': self.crc_error_count,
            'error_rate_percent': error_rate
        }
    
    def reset_crc_statistics(self):
        """Reset CRC error statistics"""
        self.crc_error_count = 0
        self.total_message_count = 0
        self.logger.info("CRC statistics reset")
    
    # Binary framing methods (Phase 3)
    
    def enable_framing(self, enabled: bool = True):
        """Enable or disable binary framing protocol"""
        self.framing_enabled = enabled
        if enabled and not self.frame_protocol:
            from src.protocols.frame_protocol import FrameProtocol
            self.frame_protocol = FrameProtocol()
        self.logger.info(f"Binary framing {'enabled' if enabled else 'disabled'}")
    
    def write_frame(self, command_type: str, payload: str) -> bool:
        """Write data using binary framing protocol"""
        if not self.frame_protocol:
            self.logger.error("Frame protocol not initialized")
            return False
            
        try:
            frame_data = self.frame_protocol.encode_message(command_type, payload)
            with self._lock:
                if not self.connection or not self.connection.is_open:
                    self.logger.error("No active serial connection")
                    return False
                
                self.connection.write(frame_data)
                self.logger.debug(f"Sent frame: type={command_type}, payload_len={len(payload)}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to write frame: {e}")
            return False
    
    def read_frames(self, timeout: Optional[float] = None) -> List:
        """Read available frames from serial connection"""
        if not self.frame_protocol:
            self.logger.error("Frame protocol not initialized")
            return []
            
        if timeout is None:
            timeout = self.timeout
            
        frames = []
        start_time = time.time()
        
        try:
            with self._lock:
                if not self.connection or not self.connection.is_open:
                    self.logger.error("No active serial connection")
                    return frames
                
                # Read available data
                while (time.time() - start_time) < timeout:
                    if self.connection.in_waiting > 0:
                        data = self.connection.read(self.connection.in_waiting)
                        new_frames = self.frame_protocol.parse_data(data)
                        frames.extend(new_frames)
                        self.total_frame_count += len(new_frames)
                        
                        if frames:  # Return immediately if we have frames
                            break
                    else:
                        time.sleep(0.001)  # Small delay to prevent busy waiting
                        
        except Exception as e:
            self.logger.error(f"Failed to read frames: {e}")
            self.frame_error_count += 1
            
        return frames
    
    def query_frame(self, command_type: str, payload: str, timeout: float = 2.0):
        """Send frame command and wait for response"""
        if not self.write_frame(command_type, payload):
            return None
            
        frames = self.read_frames(timeout)
        if frames:
            # Return the first frame's payload
            return frames[0].payload
        return None
    
    def get_frame_statistics(self) -> dict:
        """Get frame protocol statistics"""
        if self.total_frame_count == 0:
            error_rate = 0.0
        else:
            error_rate = (self.frame_error_count / self.total_frame_count) * 100
            
        stats = {
            'framing_enabled': self.framing_enabled,
            'total_frames': self.total_frame_count,
            'frame_errors': self.frame_error_count,
            'error_rate_percent': error_rate
        }
        
        if self.frame_protocol:
            parser_stats = self.frame_protocol.get_parser_stats()
            stats.update({
                'parser_total_frames': parser_stats.total_frames,
                'parser_valid_frames': parser_stats.valid_frames,
                'parser_crc_errors': parser_stats.crc_errors,
                'parser_format_errors': parser_stats.format_errors,
                'parser_timeout_errors': parser_stats.timeout_errors
            })
        
        return stats
    
    def reset_frame_statistics(self):
        """Reset frame protocol statistics"""
        self.frame_error_count = 0
        self.total_frame_count = 0
        if self.frame_protocol:
            self.frame_protocol.reset_parser()
        self.logger.info("Frame statistics reset")
    
    def query_with_retry(self, command: str, response_timeout: float = 2.0, 
                        max_retries: int = 3, backoff_factor: float = 0.1) -> Tuple[Optional[str], int]:
        """
        Send command with retry mechanism for CRC failures
        
        Args:
            command: Command to send
            response_timeout: Timeout for each attempt
            max_retries: Maximum number of retries
            backoff_factor: Exponential backoff factor (seconds)
            
        Returns:
            Tuple of (response, attempt_count)
        """
        for attempt in range(max_retries + 1):
            if attempt > 0:
                # Exponential backoff delay
                delay = backoff_factor * (2 ** (attempt - 1))
                self.logger.debug(f"Retry attempt {attempt}, waiting {delay:.3f}s")
                time.sleep(delay)
            
            response = self.query(command, response_timeout)
            if response is not None:
                if attempt > 0:
                    self.logger.info(f"Command succeeded on attempt {attempt + 1}")
                return response, attempt + 1
            
            self.logger.warning(f"Command failed on attempt {attempt + 1}")
        
        self.logger.error(f"Command failed after {max_retries + 1} attempts")
        return None, max_retries + 1

    # Binary protocol methods (Phase 4.4)
    
    def send_data(self, data: bytes) -> bool:
        """Send raw binary data"""
        if not self.is_connected():
            self.logger.error("Cannot send data - not connected")
            return False

        try:
            with self._lock:
                bytes_written = self.connection.write(data)
                self.connection.flush()
                self.logger.debug(f"Sent {bytes_written} bytes of binary data")
                return True

        except serial.SerialTimeoutError:
            self.logger.error("Binary write timeout")
            return False
        except Exception as e:
            self.logger.error(f"Binary write error: {e}")
            return False

    def read_data(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """Read available binary data"""
        if not self.is_connected():
            self.logger.error("Cannot read data - not connected")
            return None

        try:
            with self._lock:
                original_timeout = self.connection.timeout
                if timeout is not None:
                    self.connection.timeout = timeout

                try:
                    if self.connection.in_waiting > 0:
                        data = self.connection.read(self.connection.in_waiting)
                        if data:
                            self.logger.debug(f"Read {len(data)} bytes of binary data")
                            return data
                    return b""
                finally:
                    self.connection.timeout = original_timeout

        except Exception as e:
            self.logger.error(f"Binary read error: {e}")
            return None

    def read_exact(self, num_bytes: int, timeout: Optional[float] = None) -> Optional[bytes]:
        """Read exact number of bytes with timeout"""
        if not self.is_connected():
            self.logger.error("Cannot read data - not connected")
            return None

        try:
            with self._lock:
                original_timeout = self.connection.timeout
                if timeout is not None:
                    self.connection.timeout = timeout

                try:
                    data = self.connection.read(num_bytes)
                    if len(data) == num_bytes:
                        self.logger.debug(f"Read exactly {len(data)} bytes")
                        return data
                    else:
                        self.logger.warning(f"Read {len(data)} bytes, expected {num_bytes}")
                        return data if data else None
                finally:
                    self.connection.timeout = original_timeout

        except Exception as e:
            self.logger.error(f"Read exact error: {e}")
            return None

    def available_bytes(self) -> int:
        """Get number of bytes available to read"""
        if not self.is_connected():
            return 0
        
        try:
            with self._lock:
                return self.connection.in_waiting
        except Exception as e:
            self.logger.error(f"Error checking available bytes: {e}")
            return 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


# Example usage and testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Test serial manager
    serial_mgr = SerialManager()

    print("Available ports:", serial_mgr.get_available_ports())

    # Example of how to use it
    # if serial_mgr.connect("COM3"):  # Replace with actual port
    #     response = serial_mgr.query("*IDN?")  # Common SCPI command
    #     print(f"Device response: {response}")
    #     serial_mgr.disconnect()