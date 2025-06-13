"""Arduino Controller - Fixed for SMT_Board_Tester_with_Button firmware

Note: This version has been modified to work with Arduino firmware that doesn't
support the START and I2C_SCAN commands. These commands have been bypassed to
prevent connection timeouts. The Arduino operates in request-response mode and
reports button events through the reading loop.

Modified: June 2025 - Removed START and I2C_SCAN commands to fix 10-second connection delay
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Callable, Any
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
class TestResult:
    """Container for parsed test result data"""
    timestamp: float
    test_type: str
    measurements: Dict[str, float]
    raw_data: str = ""


@dataclass
class RGBWSample:
    """Container for RGBW sample data"""
    timestamp: float
    cycle: int
    voltage: float
    current: float
    lux: float
    x: float
    y: float
    raw_data: str = ""


@dataclass
class SensorConfig:
    """Configuration for a sensor - kept for compatibility but not sent to Arduino"""
    sensor_type: str  # 'INA260', 'VEML7700', 'PRESSURE', 'COLOR'
    sensor_id: str  # Unique identifier
    read_interval_ms: int = 100  # Not used by Arduino
    enabled: bool = True


class ArduinoController(ResourceMixin):
    """Controller for Arduino-based sensor systems - Fixed Communication Protocol"""

    def __init__(self, baud_rate: int = 115200):
        super().__init__()  # Initialize ResourceMixin
        self.serial = SerialManager(baud_rate=baud_rate)
        self.logger = logging.getLogger(self.__class__.__name__)

        # Sensor management
        self.sensors: Dict[str, SensorConfig] = {}
        self.readings: List[SensorReading] = []
        self.test_results: List[TestResult] = []
        self.rgbw_samples: List[RGBWSample] = []
        self.max_readings = 10000

        # Reading control
        self.is_reading = False
        self.reading_thread: Optional[threading.Thread] = None
        self.reading_lock = threading.Lock()

        # Callbacks
        self.reading_callback: Optional[Callable[[SensorReading], None]] = None
        self.result_callback: Optional[Callable[[TestResult], None]] = None
        self.rgbw_callback: Optional[Callable[[RGBWSample], None]] = None
        self.button_callback: Optional[Callable[[str], None]] = None  # Button state callback

        # Current test tracking
        self.current_test_type: Optional[str] = None
        self.latest_test_result: Optional[TestResult] = None
        
        # Command queue for sending commands during reading loop
        self.command_queue: Queue = Queue()
        self.response_queues: Dict[str, Queue] = {}
        self.response_lock = threading.Lock()

    def connect(self, port: str) -> bool:
        """Connect to Arduino on specified port"""
        if self.serial.connect(port):
            # Test communication
            if self.test_communication():
                self.logger.info(f"Arduino connected successfully on {port}")
                return True
            else:
                self.logger.error("Arduino connected but communication test failed")
                self.serial.disconnect()
                return False
        return False

    def disconnect(self):
        """Disconnect from Arduino"""
        self.stop_reading()
        
        # Clear command queue
        while not self.command_queue.empty():
            try:
                self.command_queue.get_nowait()
            except Empty:
                break
                
        self.serial.disconnect()
        self.cleanup_resources()  # Clean up all tracked resources

    def test_communication(self) -> bool:
        """Test if Arduino is responding"""
        try:
            # Clear any pending data
            self.serial.flush_buffers()

            # Send identification command
            response = self.serial.query("ID", response_timeout=3.0)
            if response and "DIODE_DYNAMICS" in response.upper():
                self.logger.debug(f"Arduino identification: {response}")
                return True

            # Try alternative ping command
            response = self.serial.query("PING", response_timeout=2.0)
            if response and "PONG" in response.upper():
                self.logger.debug("Arduino responded to PING")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Communication test error: {e}")
            return False

    def configure_sensors(self, sensor_configs: List[SensorConfig]) -> bool:
        """Initialize Arduino sensors using SENSOR_CHECK command"""
        try:
            # Store sensor configs locally for reference only
            self.sensors.clear()
            for sensor in sensor_configs:
                self.sensors[sensor.sensor_id] = sensor

            # First, let's check what the Arduino reports about its sensors
            self.logger.info("Checking Arduino sensor status...")
            status_response = self.serial.query("STATUS", response_timeout=3.0)
            if status_response:
                self.logger.info(f"Arduino status before sensor check: {status_response}")
            
            # Skip I2C_SCAN - current firmware doesn't support this command
            # The firmware will report sensor status through SENSOR_CHECK instead
            
            # Arduino automatically initializes sensors - just verify they're working
            self.logger.info("Running sensor check...")
            response = self.serial.query("SENSOR_CHECK", response_timeout=10.0)
            if response and response.startswith("OK:"):
                self.logger.info(f"Arduino sensors initialized successfully: {response}")
                
                # Get sensor status again to verify what's available
                status_response = self.serial.query("STATUS", response_timeout=3.0)
                if status_response:
                    self.logger.info(f"Arduino status after sensor check: {status_response}")
                
                return True
            elif response and response.startswith("WARNING:"):
                self.logger.warning(f"Arduino sensor warning: {response}")
                # Warning is still acceptable, sensor exists but may need time
                return True
            else:
                self.logger.error(f"Arduino sensor check failed: {response}")
                
                # Try to get more diagnostic info
                diag_response = self.serial.query("SENSOR_DIAG", response_timeout=3.0)
                if diag_response:
                    self.logger.error(f"Sensor diagnostics: {diag_response}")
                    
                return False

        except Exception as e:
            self.logger.error(f"Error configuring sensors: {e}")
            return False

    def start_reading(self, callback: Optional[Callable[[SensorReading], None]] = None):
        """Start continuous sensor reading"""
        if self.is_reading:
            self.logger.warning("Already reading sensors")
            return

        self.reading_callback = callback
        self.is_reading = True

        # Start reading thread with resource tracking
        self.reading_thread = threading.Thread(target=self._reading_loop, daemon=True)
        thread_id = self.register_thread(self.reading_thread, "arduino_reading")
        self.reading_thread.start()

        # Skip START command - current firmware doesn't support it
        # The reading loop will process button events and any data sent by Arduino
        self.logger.info("Started reading loop for button events and data (no START command needed)")

    def stop_reading(self):
        """Stop continuous sensor reading"""
        if not self.is_reading:
            return

        self.is_reading = False

        # Send stop command to Arduino
        self.serial.write("STOP\r\n")

        # Wait for reading thread to finish with proper timeout
        if self.reading_thread and self.reading_thread.is_alive():
            self.reading_thread.join(timeout=5.0)
            if self.reading_thread.is_alive():
                self.logger.warning("Reading thread did not terminate gracefully")
            else:
                self.logger.debug("Reading thread terminated successfully")

        self.logger.info("Stopped sensor reading")

    def _reading_loop(self):
        """Main reading loop running in separate thread"""
        while self.is_reading:
            try:
                # Check for queued commands first
                try:
                    command_data = self.command_queue.get_nowait()
                    command = command_data['command']
                    response_queue = command_data['response_queue']
                    
                    # Send command
                    if self.serial.write(command + '\r\n'):
                        # Wait for response with timeout
                        start_time = time.time()
                        timeout = command_data.get('timeout', 2.0)
                        
                        while time.time() - start_time < timeout:
                            line = self.serial.read_line(timeout=0.1)
                            if line:
                                line = line.strip()
                                # Check if this is a response to our command
                                if self._is_command_response(command, line):
                                    response_queue.put(line)
                                    break
                                else:
                                    # Process other messages normally
                                    self._process_arduino_message(line)
                        else:
                            # Timeout - put None in response queue
                            response_queue.put(None)
                    else:
                        response_queue.put(None)
                        
                except Empty:
                    pass
                
                # Read line from Arduino
                line = self.serial.read_line(timeout=0.1)
                if line:
                    self._process_arduino_message(line.strip())

            except Exception as e:
                self.logger.error(f"Reading loop error: {e}")
                time.sleep(0.1)
    
    def _is_command_response(self, command: str, line: str) -> bool:
        """Check if a line is a response to a specific command"""
        # Remove newlines and normalize
        cmd = command.strip().upper()
        resp = line.strip().upper()
        
        # Common response patterns
        if cmd == "ID":
            return "SMT_TESTER" in resp or "DIODE_DYNAMICS" in resp or "OFFROAD" in resp
        elif cmd == "STATUS":
            return resp.startswith("DATA:RELAYS:") or resp.startswith("STATUS:")
        elif cmd.startswith("RELAY"):
            return resp.startswith("OK:RELAY") or resp.startswith("ERROR:RELAY")
        elif cmd == "RESET":
            return resp.startswith("OK:RESET") or resp == "RESET"
        elif cmd == "SENSORS":
            return resp.startswith("OK:SENSOR") or resp.startswith("ERROR:SENSOR")
        elif cmd == "TEST":
            return resp.startswith("OK:TEST") or resp.startswith("ERROR:TEST")
        else:
            # Generic OK/ERROR responses
            return resp.startswith("OK:") or resp.startswith("ERROR:")

    def _process_arduino_message(self, line: str):
        """Process all types of Arduino messages"""
        try:
            # Handle LIVE sensor data
            if line.startswith("LIVE:"):
                readings = self._parse_live_data(line)
                for reading in readings:
                    with self.reading_lock:
                        self.readings.append(reading)
                        # Limit stored readings
                        if len(self.readings) > self.max_readings:
                            self.readings.pop(0)
                    
                    # Call callback if set
                    if self.reading_callback:
                        try:
                            self.reading_callback(reading)
                        except Exception as e:
                            self.logger.error(f"Reading callback error: {e}")

            # Handle TEST_COMPLETE messages
            elif line.startswith("TEST_COMPLETE:"):
                test_type = line[14:].strip()
                self.current_test_type = None
                self.logger.info(f"Test completed: {test_type}")

            # Handle RESULT messages
            elif line.startswith("RESULT:"):
                result = self._parse_result_data(line)
                if result:
                    with self.reading_lock:
                        self.test_results.append(result)
                        self.latest_test_result = result
                    
                    if self.result_callback:
                        try:
                            self.result_callback(result)
                        except Exception as e:
                            self.logger.error(f"Result callback error: {e}")

            # Handle RGBW_SAMPLE messages
            elif line.startswith("RGBW_SAMPLE:"):
                sample = self._parse_rgbw_sample(line)
                if sample:
                    with self.reading_lock:
                        self.rgbw_samples.append(sample)
                    
                    if self.rgbw_callback:
                        try:
                            self.rgbw_callback(sample)
                        except Exception as e:
                            self.logger.error(f"RGBW callback error: {e}")

            # Handle TEST_STARTED messages
            elif line.startswith("TEST_STARTED:"):
                test_type = line[13:].strip()
                self.current_test_type = test_type
                self.logger.info(f"Test started: {test_type}")

            # Handle STATUS messages
            elif line.startswith("STATUS:"):
                self.logger.debug(f"Arduino status: {line}")

            # Handle ERROR messages
            elif line.startswith("ERROR:"):
                self.logger.error(f"Arduino error: {line}")

            # Handle INFO messages
            elif line.startswith("INFO:"):
                self.logger.info(f"Arduino info: {line}")

            # Handle DEBUG messages
            elif line.startswith("DEBUG:"):
                self.logger.debug(f"Arduino debug: {line}")

            # Handle HEARTBEAT
            elif line.startswith("HEARTBEAT:"):
                self.logger.debug("Arduino heartbeat received")

            # Handle BUTTON messages
            elif line.startswith("DATA:BUTTON:"):
                button_state = line[12:].strip()  # Get state after "DATA:BUTTON:"
                self.logger.info(f"Button event: {button_state}")
                if self.button_callback:
                    try:
                        self.button_callback(button_state)
                    except Exception as e:
                        self.logger.error(f"Button callback error: {e}")
            
            # Handle unknown messages
            else:
                if line and not line.startswith("==="):  # Ignore startup banner
                    self.logger.debug(f"Unknown Arduino message: {line}")

        except Exception as e:
            self.logger.error(f"Error processing Arduino message '{line}': {e}")

    def _parse_live_data(self, line: str) -> List[SensorReading]:
        """Parse LIVE data format: LIVE:V=12.500,I=1.250,LUX=2500.00,X=0.450,Y=0.410,PSI=14.500"""
        readings = []
        try:
            if not line.startswith("LIVE:"):
                return readings

            data_part = line[5:]  # Remove "LIVE:"
            timestamp = time.time()

            for pair in data_part.split(","):
                if "=" in pair:
                    key, value_str = pair.split("=", 1)
                    key = key.strip()
                    
                    try:
                        value = float(value_str.strip())
                        
                        # Map Arduino sensor IDs to expected Python IDs
                        sensor_id = self._map_arduino_sensor_id(key)
                        unit = self._get_unit_for_sensor(key)
                        sensor_type = self._get_sensor_type(key)

                        reading = SensorReading(
                            timestamp=timestamp,
                            sensor_type=sensor_type,
                            sensor_id=sensor_id,
                            value=value,
                            unit=unit,
                            raw_data=line
                        )
                        readings.append(reading)
                        
                    except ValueError:
                        self.logger.warning(f"Could not parse value '{value_str}' for sensor '{key}'")

        except Exception as e:
            self.logger.error(f"Error parsing LIVE data '{line}': {e}")

        return readings

    def _parse_result_data(self, line: str) -> Optional[TestResult]:
        """Parse RESULT data format: RESULT:MV_MAIN=12.500,MI_MAIN=1.250,LUX_MAIN=2500.00,..."""
        try:
            if not line.startswith("RESULT:"):
                return None

            data_part = line[7:]  # Remove "RESULT:"
            measurements = {}
            timestamp = time.time()

            for pair in data_part.split(","):
                if "=" in pair:
                    key, value_str = pair.split("=", 1)
                    key = key.strip()
                    
                    try:
                        value = float(value_str.strip())
                        measurements[key] = value
                    except ValueError:
                        self.logger.warning(f"Could not parse result value '{value_str}' for '{key}'")

            # Determine test type from current state or measurements
            test_type = self.current_test_type or "UNKNOWN"

            return TestResult(
                timestamp=timestamp,
                test_type=test_type,
                measurements=measurements,
                raw_data=line
            )

        except Exception as e:
            self.logger.error(f"Error parsing RESULT data '{line}': {e}")
            return None

    def _parse_rgbw_sample(self, line: str) -> Optional[RGBWSample]:
        """Parse RGBW_SAMPLE data format: RGBW_SAMPLE:CYCLE=1,VOLTAGE=12.5,CURRENT=1.2,LUX=100,X=0.45,Y=0.41"""
        try:
            if not line.startswith("RGBW_SAMPLE:"):
                return None

            data_part = line[12:]  # Remove "RGBW_SAMPLE:"
            data = {}
            timestamp = time.time()

            for pair in data_part.split(","):
                if "=" in pair:
                    key, value_str = pair.split("=", 1)
                    key = key.strip()
                    
                    try:
                        if key == "CYCLE":
                            data[key] = int(value_str.strip())
                        else:
                            data[key] = float(value_str.strip())
                    except ValueError:
                        self.logger.warning(f"Could not parse RGBW value '{value_str}' for '{key}'")

            # Extract required fields with defaults
            cycle = data.get("CYCLE", 0)
            voltage = data.get("VOLTAGE", 0.0)
            current = data.get("CURRENT", 0.0)
            lux = data.get("LUX", 0.0)
            x = data.get("X", 0.0)
            y = data.get("Y", 0.0)

            return RGBWSample(
                timestamp=timestamp,
                cycle=cycle,
                voltage=voltage,
                current=current,
                lux=lux,
                x=x,
                y=y,
                raw_data=line
            )

        except Exception as e:
            self.logger.error(f"Error parsing RGBW_SAMPLE '{line}': {e}")
            return None

    def _map_arduino_sensor_id(self, arduino_id: str) -> str:
        """Map Arduino sensor IDs to Python expected IDs"""
        mapping = {
            "I": "CURRENT",
            "V": "VOLTAGE", 
            "LUX": "LUX_MAIN",  # Default to main, context will determine if it's backlight
            "X": "X_MAIN",      # Default to main, context will determine if it's backlight
            "Y": "Y_MAIN",      # Default to main, context will determine if it's backlight
            "PSI": "PSI"
        }
        return mapping.get(arduino_id, arduino_id)

    def _get_unit_for_sensor(self, sensor_id: str) -> str:
        """Get unit string for sensor ID"""
        units = {
            "I": "A",
            "V": "V",
            "LUX": "lux",
            "X": "CIE_x",
            "Y": "CIE_y", 
            "PSI": "PSI"
        }
        return units.get(sensor_id, "")

    def _get_sensor_type(self, sensor_id: str) -> str:
        """Get sensor type for sensor ID"""
        types = {
            "I": "INA260",
            "V": "INA260",
            "LUX": "VEML7700",
            "X": "COLOR",
            "Y": "COLOR",
            "PSI": "PRESSURE"
        }
        return types.get(sensor_id, "UNKNOWN")

    def get_latest_reading(self, sensor_id: str) -> Optional[SensorReading]:
        """Get the most recent reading from a specific sensor"""
        with self.reading_lock:
            for reading in reversed(self.readings):
                if reading.sensor_id == sensor_id:
                    return reading
        return None

    def get_readings_since(self, timestamp: float, sensor_id: Optional[str] = None) -> List[SensorReading]:
        """Get all readings since a specific timestamp"""
        with self.reading_lock:
            filtered_readings = []
            for reading in self.readings:
                if reading.timestamp >= timestamp:
                    if sensor_id is None or reading.sensor_id == sensor_id:
                        filtered_readings.append(reading)
            return filtered_readings

    def get_average_reading(self, sensor_id: str, duration_seconds: float) -> Optional[float]:
        """Get average reading for a sensor over the last duration_seconds"""
        cutoff_time = time.time() - duration_seconds
        readings = self.get_readings_since(cutoff_time, sensor_id)

        if not readings:
            return None

        values = [reading.value for reading in readings]
        return sum(values) / len(values)

    def get_latest_test_result(self) -> Optional[TestResult]:
        """Get the most recent test result"""
        with self.reading_lock:
            return self.latest_test_result

    def get_test_result_value(self, key: str) -> Optional[float]:
        """Get a specific measurement from the latest test result"""
        result = self.get_latest_test_result()
        if result and key in result.measurements:
            return result.measurements[key]
        return None

    def get_rgbw_samples_for_cycle(self, cycle: int) -> List[RGBWSample]:
        """Get all RGBW samples for a specific cycle"""
        with self.reading_lock:
            return [sample for sample in self.rgbw_samples if sample.cycle == cycle]

    def get_all_rgbw_samples(self) -> List[RGBWSample]:
        """Get all RGBW samples"""
        with self.reading_lock:
            return self.rgbw_samples.copy()

    def clear_rgbw_samples(self):
        """Clear stored RGBW samples"""
        with self.reading_lock:
            self.rgbw_samples.clear()

    def send_command(self, command: str, timeout: float = 2.0) -> Optional[str]:
        """Send a custom command to Arduino"""
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
                return None
        else:
            # Normal query when reading loop is not active
            return self.serial.query(command, response_timeout=timeout)

    def clear_readings(self):
        """Clear stored sensor readings"""
        with self.reading_lock:
            self.readings.clear()

    def is_connected(self) -> bool:
        """Check if Arduino is connected"""
        return self.serial.is_connected()
    
    def set_button_callback(self, callback: Optional[Callable[[str], None]]):
        """Set callback for button state changes"""
        self.button_callback = callback
    
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
                    if status and "SMT" in status.upper():
                        return "SMT"
                    else:
                        return "OFFROAD"
            return "UNKNOWN"
        except Exception as e:
            self.logger.error(f"Error getting firmware type: {e}")
            return "UNKNOWN"

    def get_sensor_status(self) -> Dict[str, Any]:
        """Get status of all configured sensors"""
        status = {
            "connected": self.is_connected(),
            "reading": self.is_reading,
            "total_readings": len(self.readings),
            "current_test": self.current_test_type,
            "sensors": {}
        }

        for sensor_id, config in self.sensors.items():
            latest = self.get_latest_reading(sensor_id)
            status["sensors"][sensor_id] = {
                "type": config.sensor_type,
                "enabled": config.enabled,
                "interval_ms": config.read_interval_ms,
                "last_reading": latest.value if latest else None,
                "last_timestamp": latest.timestamp if latest else None
            }

        return status


# Predefined sensor configurations for common setups - kept for compatibility
class SensorConfigurations:
    """Predefined sensor configurations for different test modes"""

    @staticmethod
    def offroad_pod_sensors(read_interval_ms: int = 50) -> List[SensorConfig]:
        """Standard offroad pod sensor configuration"""
        return [
            SensorConfig("INA260", "CURRENT", read_interval_ms),
            SensorConfig("INA260", "VOLTAGE", read_interval_ms),
            SensorConfig("INA260", "POWER", read_interval_ms),
            SensorConfig("VEML7700", "LUX_MAIN", read_interval_ms),
            SensorConfig("VEML7700", "LUX_BACK", read_interval_ms),
            SensorConfig("PRESSURE", "PSI", read_interval_ms),
            SensorConfig("COLOR", "X_MAIN", read_interval_ms),
            SensorConfig("COLOR", "Y_MAIN", read_interval_ms),
            SensorConfig("COLOR", "X_BACK", read_interval_ms),
            SensorConfig("COLOR", "Y_BACK", read_interval_ms)
        ]

    @staticmethod
    def smt_panel_sensors(read_interval_ms: int = 100) -> List[SensorConfig]:
        """SMT panel testing sensor configuration
        
        For SMT testing, typically uses a single INA260 that's switched
        between different measurement points via relays.
        """
        return [
            SensorConfig("INA260", "CURRENT", read_interval_ms),
            SensorConfig("INA260", "VOLTAGE", read_interval_ms)
        ]


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    def reading_handler(reading: SensorReading):
        print(f"[{reading.timestamp:.3f}] {reading.sensor_id}: {reading.value} {reading.unit}")

    def result_handler(result: TestResult):
        print(f"Test Result ({result.test_type}): {result.measurements}")

    def rgbw_handler(sample: RGBWSample):
        print(f"RGBW Cycle {sample.cycle}: V={sample.voltage}, I={sample.current}, X={sample.x}, Y={sample.y}")

    # Test Arduino controller
    arduino = ArduinoController(baud_rate=115200)
    
    print("Fixed Arduino Controller loaded with proper communication protocol:")
    print("✅ Handles LIVE:V=12.5,I=1.2,LUX=2500,X=0.45,Y=0.41,PSI=14.5")
    print("✅ Handles RESULT:MV_MAIN=12.5,MI_MAIN=1.2,LUX_MAIN=2500,...")
    print("✅ Handles RGBW_SAMPLE:CYCLE=1,VOLTAGE=12.5,CURRENT=1.2,...")
    print("✅ Uses SENSOR_CHECK instead of CONFIG")
    print("✅ Cleanup uses STOP command only")
