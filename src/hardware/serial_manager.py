import serial
import serial.tools.list_ports
import time
import logging
from typing import List, Optional, Union
import threading
from src.utils.thread_cleanup import ThreadCleanupMixin


class SerialManager(ThreadCleanupMixin):
    """Manages serial communication with devices"""

    def __init__(self, baud_rate: int = 9600, timeout: float = 5.0, write_timeout: float = 5.0):
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self.connection: Optional[serial.Serial] = None
        self.port: Optional[str] = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self._lock = threading.Lock()

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

                # Try standard connection first
                try:
                    self.connection = serial.Serial(
                        port=port,
                        baudrate=self.baud_rate,
                        timeout=self.timeout,
                        write_timeout=self.write_timeout,
                        bytesize=serial.EIGHTBITS,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE
                    )
                except serial.SerialException as e:
                    if "PermissionError" in str(e) or "Access is denied" in str(e):
                        self.logger.warning("Permission error - may be Arduino R4, retrying...")
                        time.sleep(1.0)  # Wait for port to be released
                        # Try again with minimal settings
                        self.connection = serial.Serial(port, self.baud_rate, timeout=self.timeout)
                    else:
                        raise

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
        """Send command and wait for response"""
        if not self.write(command + '\r\n'):
            return None

        # Small delay to ensure command is processed
        time.sleep(0.05)

        return self.read_line(timeout=response_timeout)

    def flush_buffers(self):
        """Clear input and output buffers"""
        if self.is_connected():
            with self._lock:
                self.connection.reset_input_buffer()
                self.connection.reset_output_buffer()

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

