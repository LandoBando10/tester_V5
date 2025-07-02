import serial
import serial.tools.list_ports
import time
import logging
from typing import List, Optional, Union
import threading
import os
import platform
from src.utils.thread_cleanup import ThreadCleanupMixin
from src.services.port_registry import port_registry


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
        
        # Check if running on WSL
        is_wsl = 'microsoft' in platform.uname().release.lower() or 'WSL' in os.environ.get('WSL_DISTRO_NAME', '')
        
        if is_wsl:
            # On WSL, COM ports are mapped to /dev/ttySX
            # COM1 = /dev/ttyS1, COM2 = /dev/ttyS2, etc.
            # But pyserial expects "COMX" format, so we need to check which ones exist
            self.logger.info("Running on WSL - checking for Windows COM ports")
            
            # Check common COM ports (1-20)
            for i in range(1, 21):
                com_port = f"COM{i}"
                tty_device = f"/dev/ttyS{i}"
                
                # Check if the tty device exists and is accessible
                if os.path.exists(tty_device):
                    try:
                        # Try to open it briefly to see if it's a real port
                        with serial.Serial(com_port, 9600, timeout=0.1) as test_port:
                            pass
                        ports.append(com_port)
                        self.logger.debug(f"Found accessible port: {com_port}")
                    except (serial.SerialException, OSError) as e:
                        # Port exists but may not be accessible or connected
                        self.logger.debug(f"Port {com_port} exists but not accessible: {e}")
                        # Still add it to the list as it might work with different settings
                        ports.append(com_port)
        else:
            # Standard port detection for non-WSL systems
            for port in serial.tools.list_ports.comports():
                ports.append(port.device)
        
        return ports

    def connect(self, port: str) -> bool:
        """Connect to specified COM port with atomic acquisition"""
        try:
            with self._lock:
                if self.connection and self.connection.is_open:
                    self.disconnect()

                # Atomic acquisition - acquire_port will return False if already in use
                # This prevents race conditions between checking and acquiring
                if not port_registry.acquire_port(port):
                    # Port is already in use
                    self.logger.warning(f"Port {port} is already in use by another component")
                    return False
                
                # We now have exclusive access to the port
                port_acquired = True

                # Handle WSL port mapping
                actual_port = port
                is_wsl = 'microsoft' in platform.uname().release.lower() or 'WSL' in os.environ.get('WSL_DISTRO_NAME', '')
                
                if is_wsl and port.upper().startswith('COM'):
                    # Convert COM port to WSL format for actual connection
                    # COM1 = /dev/ttyS1, COM2 = /dev/ttyS2, etc.
                    try:
                        port_num = int(port[3:])
                        actual_port = f"/dev/ttyS{port_num}"
                        self.logger.debug(f"WSL: Converting {port} to {actual_port}")
                    except ValueError:
                        self.logger.warning(f"Invalid COM port format: {port}")
                        port_registry.release_port(port)  # Release on error
                        return False

                # Try standard connection first
                try:
                    self.connection = serial.Serial(
                        port=actual_port,
                        baudrate=self.baud_rate,
                        timeout=self.timeout,
                        write_timeout=self.write_timeout,
                        bytesize=serial.EIGHTBITS,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE
                    )
                except serial.SerialException as e:
                    error_str = str(e)
                    if "PermissionError" in error_str or "Access is denied" in error_str or "Permission denied" in error_str:
                        # Analyze the permission error to determine actual cause
                        error_cause = self._analyze_permission_error(port, error_str)
                        
                        if error_cause == "PORT_IN_USE_BY_APP":
                            self.logger.error(f"Port {port} is already in use by this application")
                            port_registry.release_port(port)  # Release our failed attempt
                            return False
                        
                        elif error_cause == "PORT_IN_USE_BY_OTHER":
                            self.logger.error(f"Port {port} is in use by another process")
                            port_registry.release_port(port)  # Release since we couldn't connect
                            return False
                        
                        elif error_cause == "PORT_NOT_FOUND":
                            self.logger.error(f"Port {port} not found or inaccessible")
                            port_registry.release_port(port)
                            return False
                        
                        elif error_cause == "ARDUINO_R4_MAYBE":
                            # Only try Arduino R4 workaround if we think it's actually that issue
                            self.logger.info("Detected possible Arduino R4 - retrying with minimal settings...")
                            time.sleep(0.3)  # Shorter wait
                            try:
                                self.connection = serial.Serial(actual_port, self.baud_rate, timeout=self.timeout)
                                self.logger.info("Arduino R4 workaround successful")
                            except Exception:
                                # Still failed, release the port
                                self.logger.error(f"Arduino R4 workaround failed for {port}")
                                port_registry.release_port(port)
                                raise
                        else:
                            # Unknown permission error
                            self.logger.error(f"Unknown permission error on {port}: {error_str}")
                            port_registry.release_port(port)
                            raise
                    else:
                        # Other error, release port and re-raise
                        port_registry.release_port(port)
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
            # Port is already released in the exception handlers above
            # No need to release again
            
            # Provide helpful error message for WSL permission issues
            if is_wsl and "Permission denied" in str(e):
                self.logger.error("WSL Serial Port Permission Error:")
                self.logger.error("  You need to be in the 'dialout' group to access serial ports.")
                self.logger.error("  Run: sudo usermod -a -G dialout $USER")
                self.logger.error("  Then log out and log back in, or run: newgrp dialout")
                self.logger.error("  Or run the provided script: ./fix_wsl_serial_permissions.sh")
            
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error connecting to {port}: {e}")
            # Make sure to release the port on any unexpected failure
            try:
                port_registry.release_port(port)
            except:
                pass  # Best effort cleanup
            return False

    def disconnect(self):
        """Disconnect from current port"""
        try:
            with self._lock:
                if self.connection and self.connection.is_open:
                    self.connection.close()
                    self.logger.info(f"Disconnected from {self.port}")
                
                # Release the port in the registry
                if self.port:
                    port_registry.release_port(self.port)
                    
                self.connection = None
                self.port = None
        except Exception as e:
            self.logger.error(f"Error disconnecting: {e}")
            # Still try to release the port even if disconnect had issues
            if self.port:
                port_registry.release_port(self.port)

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
    
    def _analyze_permission_error(self, port: str, error_str: str) -> str:
        """Determine the actual cause of a permission error.
        
        Returns one of:
        - PORT_IN_USE_BY_APP: Port is already in use by this application
        - PORT_IN_USE_BY_OTHER: Port is in use by another process
        - PORT_NOT_FOUND: Port doesn't exist or is inaccessible
        - ARDUINO_R4_MAYBE: Might be Arduino R4 specific issue
        - UNKNOWN: Cannot determine cause
        """
        # First check our own registry
        if port_registry.is_port_in_use(port):
            return "PORT_IN_USE_BY_APP"
        
        # Check if port exists in available ports
        available_ports = self.get_available_ports()
        if port not in available_ports:
            return "PORT_NOT_FOUND"
        
        # Check for specific error patterns
        error_lower = error_str.lower()
        
        # Common "port in use" patterns
        if any(pattern in error_lower for pattern in [
            "access is denied",
            "permission denied",
            "resource busy",
            "already in use"
        ]):
            # Try a quick test to see if we can open with minimal settings
            # This helps distinguish between "in use" and "Arduino R4 quirks"
            try:
                # Very quick test with minimal settings
                test_conn = serial.Serial()
                test_conn.port = port
                test_conn.baudrate = 9600
                test_conn.timeout = 0.01
                test_conn.open()
                test_conn.close()
                # If we got here, it's not in use, might be Arduino R4
                return "ARDUINO_R4_MAYBE"
            except:
                # Definitely in use by another process
                return "PORT_IN_USE_BY_OTHER"
        
        # File not found patterns
        if any(pattern in error_lower for pattern in [
            "could not open port",
            "cannot find the file",
            "no such file"
        ]):
            return "PORT_NOT_FOUND"
        
        return "UNKNOWN"


# Example usage and testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Test serial manager
    serial_mgr = SerialManager()

    print("Available ports:", serial_mgr.get_available_ports())

