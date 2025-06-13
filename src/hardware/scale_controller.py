import time
import re
import threading
import logging
import queue
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from .serial_manager import SerialManager
from src.utils.resource_manager import ResourceMixin
from config.settings import SCALE_SETTINGS, WEIGHT_TESTING


@dataclass
class SensorReading:
    """Container for sensor reading data - compatible with Arduino controller"""
    timestamp: float
    sensor_type: str
    sensor_id: str
    value: float
    unit: str
    raw_data: str = ""


@dataclass
class SensorConfig:
    """Configuration for a sensor - compatible with Arduino controller"""
    sensor_type: str  # 'SCALE'
    sensor_id: str    # 'WEIGHT'
    read_interval_ms: int = 100
    enabled: bool = True


class ScaleController(ResourceMixin):
    """Optimized Scale controller with reduced latency and improved performance"""
    
    def __init__(self, baud_rate: Optional[int] = None):
        super().__init__()  # Initialize ResourceMixin
        
        # Use settings from config
        baud_rate = baud_rate or SCALE_SETTINGS['baud_rate']
        self.serial = SerialManager(baud_rate=baud_rate)
        self.logger = logging.getLogger(self.__class__.__name__)

        # Compile regex patterns once
        self._compile_regex_patterns()

        # Sensor management (following Arduino controller pattern)
        self.sensors: Dict[str, SensorConfig] = {}
        self.readings: List[SensorReading] = []
        self.max_readings = SCALE_SETTINGS['max_weight_readings']

        # Reading control
        self.is_reading = False
        self.reading_thread: Optional[threading.Thread] = None
        self.reading_lock = threading.Lock()

        # Current state with thread-safe access
        self._current_weight = None
        self._weight_lock = threading.Lock()
        self.tare_value = 0.0
        self.is_tared = False

        # Callbacks (following Arduino controller pattern)
        self.reading_callback: Optional[Callable[[SensorReading], None]] = None
        self.weight_callback: Optional[Callable[[float], None]] = None

        # Performance optimization: Use a queue for readings
        self.reading_queue = queue.Queue(maxsize=100)
        self.last_raw_reading = None
        self.last_reading_time = 0

        # Cache for parsed weights to avoid re-parsing identical strings
        self.weight_cache = {}
        self.max_cache_size = 100

        # Add weight stability filtering
        self.weight_history = []
        self.max_weight_history = 10  # Keep last 10 readings for smoothing
        self.weight_filter_enabled = True

    def _compile_regex_patterns(self):
        """Pre-compile regex patterns for better performance"""
        # Combine patterns into a single regex with named groups for faster matching
        self.combined_weight_regex = re.compile(
            r'(?:(?P<st>ST,GS,\s*(?P<st_val>[+-]?\d*\.?\d+),\s*g)|'
            r'(?P<us>US,GS,\s*(?P<us_val>[+-]?\d*\.?\d+),\s*g)|'
            r'(?P<simple>(?P<simple_val>[+-]?\d+\.?\d*)\s*g))'
        )

    @property
    def current_weight(self):
        """Thread-safe access to current weight"""
        with self._weight_lock:
            return self._current_weight

    @current_weight.setter
    def current_weight(self, value):
        """Thread-safe setter for current weight"""
        with self._weight_lock:
            self._current_weight = value

    def connect(self, port: str, skip_comm_test: bool = False) -> bool:
        """Connect to scale on specified port - optimized"""
        if self.serial.connect(port):
            # Set serial timeout to be very short for non-blocking reads
            if hasattr(self.serial, 'connection') and self.serial.connection:
                self.serial.connection.timeout = 0.05  # 50ms timeout
                # Clear any accumulated data in buffers before testing
                try:
                    self.serial.connection.reset_input_buffer()
                    self.serial.connection.reset_output_buffer()
                except:
                    pass  # Some serial implementations don't support these methods
            
            if skip_comm_test or self.test_communication():
                self.logger.info(f"Scale connected successfully on {port}")
                return True
            else:
                self.logger.error("Scale connected but communication test failed")
                self.serial.disconnect()
                return False
        return False

    def disconnect(self):
        """Disconnect from scale"""
        self.stop_reading()
        self.serial.disconnect()
        self.cleanup_resources()  # Clean up all tracked resources

    def test_communication(self) -> bool:
        """Optimized communication test with early exit"""
        try:
            # Check for existing data first - no delay if data already available
            if self.serial.connection and self.serial.connection.in_waiting > 0:
                # Try to parse immediately
                weight = self._get_raw_weight_fast(timeout=0.05)
                if weight is not None:
                    return True
            
            # Only clear buffers if necessary
            if self.serial.connection.in_waiting > 512:
                self.serial.flush_buffers()
                time.sleep(0.02)  # Reduced from 50ms
            
            # Single attempt with shorter timeout
            weight = self._get_raw_weight_fast(timeout=0.15)  # Reduced from 300ms
            if weight is not None:
                return True
                
            # Quick check for any data (1 iteration, not 3)
            time.sleep(0.05)
            return self.serial.connection.in_waiting > 0
            
        except Exception as e:
            self.logger.error(f"Communication test error: {e}")
            return False

    def configure_sensors(self, sensor_configs: List[SensorConfig]) -> bool:
        """Configure scale sensors (following Arduino controller pattern)"""
        try:
            # Store sensor configs locally
            self.sensors.clear()
            for sensor in sensor_configs:
                self.sensors[sensor.sensor_id] = sensor

            # Scale doesn't need complex sensor configuration
            # Just verify it's responding
            if self.test_communication():
                self.logger.info("Scale sensors configured successfully")
                return True
            else:
                self.logger.error("Scale sensor configuration failed")
                return False

        except Exception as e:
            self.logger.error(f"Error configuring sensors: {e}")
            return False

    def start_reading(self, callback: Optional[Callable[[SensorReading], None]] = None, read_interval_s: Optional[float] = None):
        """Start reading with minimal initialization"""
        if self.is_reading:
            return
            
        self.reading_callback = callback
        self.is_reading = True
        
        # Only clear if significant data accumulated
        if self.serial.connection and self.serial.connection.in_waiting > 1024:
            self.serial.connection.reset_input_buffer()
        # Remove redundant flush_buffers() call
        
        # Don't clear weight history on start - keep continuity
        # self.clear_weight_history()  # REMOVE THIS
        
        # Start thread immediately
        self._read_interval_s = read_interval_s or 0.05
        self.reading_thread = threading.Thread(target=self._optimized_reading_loop, daemon=True)
        self.register_thread(self.reading_thread, "scale_reading")
        self.reading_thread.start()

    def stop_reading(self):
        """Stop continuous weight reading"""
        if not self.is_reading:
            return

        self.is_reading = False

        # Wait for reading thread to finish with proper timeout
        if self.reading_thread and self.reading_thread.is_alive():
            self.reading_thread.join(timeout=2.0)
            if self.reading_thread.is_alive():
                self.logger.warning("Reading thread did not terminate gracefully")
            else:
                self.logger.debug("Reading thread terminated successfully")

        self.logger.info("Stopped weight reading")

    def _optimized_reading_loop(self):
        """Optimized reading loop with minimal latency and improved stability"""
        consecutive_errors = 0
        max_consecutive_errors = 50  # Increased threshold since "no data" isn't really an error
        no_data_count = 0
        last_successful_read = time.time()
        last_buffer_flush = time.time()
        buffer_flush_interval = 10.0  # Flush buffer every 10 seconds to prevent buildup
        
        while self.is_reading:
            loop_start_time = time.time()
            
            try:
                # Periodic buffer flush to prevent data accumulation
                if time.time() - last_buffer_flush > buffer_flush_interval:
                    if self.serial.connection and self.serial.connection.in_waiting > 512:  # If too much data waiting
                        self.logger.debug("Flushing serial buffer to prevent buildup")
                        self.serial.flush_buffers()
                    last_buffer_flush = time.time()
                
                # Non-blocking read with very short timeout
                raw_weight = self._get_raw_weight_fast(timeout=0.05)
                
                if raw_weight is not None:
                    consecutive_errors = 0  # Reset error counter
                    no_data_count = 0  # Reset no-data counter
                    last_successful_read = time.time()
                    
                    # Apply weight filtering to reduce noise
                    filtered_weight = self._apply_weight_filter(raw_weight)
                    
                    # Apply tare if set
                    weight = filtered_weight - self.tare_value if self.is_tared else filtered_weight
                    self.current_weight = weight

                    # Only create reading object if weight changed significantly
                    if self._should_report_weight(weight):
                        reading = SensorReading(
                            timestamp=time.time(),
                            sensor_type="SCALE",
                            sensor_id="WEIGHT",
                            value=weight,
                            unit="g",
                            raw_data=f"weight={weight:.3f}"
                        )

                        # Add to queue instead of list for better performance
                        try:
                            self.reading_queue.put_nowait(reading)
                        except queue.Full:
                            # Remove oldest if queue is full
                            try:
                                self.reading_queue.get_nowait()
                                self.reading_queue.put_nowait(reading)
                            except queue.Empty:
                                pass

                        # Call callbacks in separate thread to avoid blocking
                        if self.reading_callback or self.weight_callback:
                            threading.Thread(target=self._execute_callbacks, args=(reading, weight), daemon=True).start()
                else:
                    no_data_count += 1
                    # Only count as consecutive errors if we haven't had data for a while
                    if time.time() - last_successful_read > 5.0:  # 5 seconds without any data
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            self.logger.warning("Scale appears disconnected - no data received for extended period...")
                            consecutive_errors = 0  # Reset to avoid spam

            except Exception as e:
                self.logger.error(f"Error in reading loop: {e}")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    self.logger.warning("Too many consecutive read errors, checking connection...")
                    consecutive_errors = 0  # Reset to avoid spam

            # Dynamic sleep adjustment for maintaining interval
            elapsed_time = time.time() - loop_start_time
            sleep_time = max(0, self._read_interval_s - elapsed_time)
            
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _apply_weight_filter(self, raw_weight: float) -> float:
        """Apply filtering to reduce weight reading noise and outliers"""
        if not self.weight_filter_enabled:
            return raw_weight
        
        # Add to history
        self.weight_history.append(raw_weight)
        
        # Maintain history size
        if len(self.weight_history) > self.max_weight_history:
            self.weight_history.pop(0)
        
        # If we don't have enough history, return raw weight
        if len(self.weight_history) < 3:
            return raw_weight
        
        # Check for obvious outliers compared to recent history
        recent_weights = self.weight_history[-5:]  # Last 5 readings
        
        if len(recent_weights) >= 3:
            # Calculate median of recent readings
            sorted_recent = sorted(recent_weights[:-1])  # Exclude current reading
            median_weight = sorted_recent[len(sorted_recent) // 2]
            
            # Check if current reading is an extreme outlier
            outlier_threshold = max(100.0, abs(median_weight) * 0.5)  # 50% change or 100g
            
            if abs(raw_weight - median_weight) > outlier_threshold:
                # This looks like an outlier, use a more conservative approach
                self.logger.debug(f"Potential outlier detected: {raw_weight}g vs median {median_weight}g")
                
                # Return a weighted average favoring the median
                return (median_weight * 0.7) + (raw_weight * 0.3)
        
        # Apply simple moving average to smooth readings
        if len(self.weight_history) >= 3:
            # Use weighted average with more weight on recent readings
            weights = [0.1, 0.2, 0.3, 0.4][-len(self.weight_history):]
            if len(weights) > len(self.weight_history):
                weights = weights[:len(self.weight_history)]
            
            weighted_sum = sum(w * reading for w, reading in zip(weights, self.weight_history[-len(weights):]))
            weight_sum = sum(weights)
            
            return weighted_sum / weight_sum
        
        return raw_weight

    def _should_report_weight(self, weight: float) -> bool:
        """Check if weight changed enough to report"""
        if self.last_raw_reading is None:
            self.last_raw_reading = weight
            return True
        
        # Report if weight changed by more than 0.01g or 0.1% (whichever is larger)
        change_threshold = max(0.01, abs(self.last_raw_reading) * 0.001)
        if abs(weight - self.last_raw_reading) >= change_threshold:
            self.last_raw_reading = weight
            return True
        
        # Also report at least once per second even if no change
        current_time = time.time()
        if current_time - self.last_reading_time >= 1.0:
            self.last_reading_time = current_time
            return True
            
        return False

    def _execute_callbacks(self, reading: SensorReading, weight: float):
        """Execute callbacks in separate thread"""
        if self.reading_callback:
            try:
                self.reading_callback(reading)
            except Exception as e:
                self.logger.error(f"Reading callback error: {e}")

        if self.weight_callback:
            try:
                self.weight_callback(weight)
            except Exception as e:
                self.logger.error(f"Weight callback error: {e}")

    def _get_raw_weight_fast(self, timeout: Optional[float] = None) -> Optional[float]:
        """Get raw weight reading with improved stability and error handling"""
        try:
            # First check if we have a connection
            if not self.serial.connection:
                return None
                
            # Check if there's data waiting, but don't treat no-data as an error
            if self.serial.connection.in_waiting == 0:
                return None
            
            # Read data with a small buffer to avoid overwhelming
            max_read_size = min(self.serial.connection.in_waiting, 1024)  # Limit read size
            available_data = self.serial.connection.read(max_read_size)
            if not available_data:
                return None
            
            # Decode and handle potential encoding issues
            try:
                decoded_data = available_data.decode('utf-8', errors='ignore')
            except:
                return None
            
            # Split into lines and process only complete lines
            lines = decoded_data.strip().split('\n')
            
            # Only process complete lines (avoid partial data)
            valid_lines = [line.strip() for line in lines if line.strip() and len(line.strip()) > 5]
            
            if not valid_lines:
                return None
            
            # Process lines to find valid weight readings
            valid_weights = []
            for line in valid_lines:
                # Check cache first
                if line in self.weight_cache:
                    valid_weights.append(self.weight_cache[line])
                    continue
                
                weight = self._parse_weight_string_fast(line)
                if weight is not None:
                    # Validate weight is reasonable (basic sanity check)
                    if -100 <= weight <= 5000:  # Reasonable weight range for this application
                        valid_weights.append(weight)
                        # Update cache
                        self._update_cache(line, weight)
            
            if valid_weights:
                # If we have multiple valid weights, use the most recent one
                # But first check for obvious outliers
                if len(valid_weights) > 1:
                    # Remove outliers using simple median filtering
                    sorted_weights = sorted(valid_weights)
                    median_weight = sorted_weights[len(sorted_weights) // 2]
                    
                    # Filter weights within reasonable range of median
                    filtered_weights = [w for w in valid_weights 
                                      if abs(w - median_weight) <= max(50.0, median_weight * 0.1)]
                    
                    if filtered_weights:
                        return filtered_weights[-1]  # Most recent filtered weight
                    else:
                        return median_weight  # Fallback to median
                else:
                    return valid_weights[0]
            
            return None

        except Exception as e:
            # Only log actual errors, not normal "no data available" situations
            self.logger.debug(f"Error getting raw weight: {e}")
            return None

    def _parse_weight_string_fast(self, weight_str: str) -> Optional[float]:
        """Parse weight value using optimized regex matching with improved validation"""
        try:
            # Skip obviously invalid strings
            if len(weight_str) < 3 or len(weight_str) > 50:
                return None
                
            # Use combined regex for single-pass matching
            match = self.combined_weight_regex.search(weight_str)
            if match:
                # Check which pattern matched and extract value
                if match.group('st_val'):
                    weight = float(match.group('st_val'))
                elif match.group('us_val'):
                    weight = float(match.group('us_val'))
                elif match.group('simple_val'):
                    weight = float(match.group('simple_val'))
                else:
                    weight = None
                
                # Validate weight is in reasonable range
                if weight is not None and -100 <= weight <= 5000:
                    return weight
            
            # Fallback: Try to extract any float from the string
            # This is faster than multiple regex attempts
            numbers = re.findall(r'[+-]?\d+\.?\d*', weight_str)
            if numbers:
                # Take the first number that looks like a weight (reasonable range)
                for num_str in numbers:
                    try:
                        val = float(num_str)
                        if -100 <= val <= 5000:  # Reasonable weight range in grams
                            return val
                    except:
                        continue
            
            return None

        except Exception as e:
            # Only log if this appears to be a parsing issue with valid-looking data
            if len(weight_str) > 5 and any(c.isdigit() for c in weight_str):
                self.logger.debug(f"Error parsing weight string '{weight_str}': {e}")
            return None

    def _update_cache(self, key: str, value: float):
        """Update weight cache with size limit"""
        self.weight_cache[key] = value
        
        # Limit cache size
        if len(self.weight_cache) > self.max_cache_size:
            # Remove oldest entries (FIFO)
            keys_to_remove = list(self.weight_cache.keys())[:len(self.weight_cache) - self.max_cache_size]
            for k in keys_to_remove:
                del self.weight_cache[k]

    def get_latest_reading(self, sensor_id: str) -> Optional[SensorReading]:
        """Get the most recent reading from a specific sensor"""
        try:
            # Get all readings from queue
            readings = []
            while not self.reading_queue.empty():
                try:
                    readings.append(self.reading_queue.get_nowait())
                except queue.Empty:
                    break
            
            # Put them back and return the latest matching one
            latest = None
            for reading in readings:
                self.reading_queue.put_nowait(reading)
                if reading.sensor_id == sensor_id:
                    latest = reading
            
            return latest
        except:
            return None

    def get_stable_weight(self, num_readings: Optional[int] = None, tolerance: Optional[float] = None, timeout: Optional[float] = None) -> Optional[float]:
        """Get stable weight reading with improved performance"""
        # Use settings defaults if not provided
        num_readings = num_readings or SCALE_SETTINGS['stable_reading_count']
        tolerance = tolerance or SCALE_SETTINGS['reading_tolerance']
        timeout = timeout or WEIGHT_TESTING['test_timings']['part_detection_timeout']
        
        readings = []
        start_time = time.time()

        # Start reading if not already
        was_reading = self.is_reading
        if not was_reading:
            self.start_reading()
            time.sleep(0.1)  # Short delay to start getting readings

        try:
            # Use a faster sampling rate for stability detection
            sample_interval = 0.05  # 50ms
            
            while time.time() - start_time < timeout:
                if self.current_weight is not None:
                    readings.append(self.current_weight)

                    if len(readings) >= num_readings:
                        # Check if readings are stable
                        recent_readings = readings[-num_readings:]
                        avg_weight = sum(recent_readings) / len(recent_readings)

                        # Check if all recent readings are within tolerance
                        stable = all(abs(reading - avg_weight) <= tolerance
                                   for reading in recent_readings)

                        if stable:
                            self.logger.info(f"Stable weight: {avg_weight:.3f}g")
                            return round(avg_weight, 3)

                time.sleep(sample_interval)

            # If we couldn't get stable readings, return average
            if readings:
                avg_weight = sum(readings) / len(readings)
                self.logger.warning(f"Timeout - returning average: {avg_weight:.3f}g")
                return round(avg_weight, 3)

            return None

        finally:
            # Stop reading if we started it
            if not was_reading:
                self.stop_reading()

    def tare_scale(self) -> bool:
        """Tare the scale (zero it)"""
        try:
            # Get current stable weight
            current_weight = self.get_stable_weight(num_readings=3, tolerance=0.05, timeout=2.0)
            if current_weight is not None:
                self.tare_value = current_weight
                self.is_tared = True
                self.logger.info(f"Scale tared at {self.tare_value}g")
                return True
            
            return False

        except Exception as e:
            self.logger.error(f"Error taring scale: {e}")
            return False

    def send_command(self, command: str, timeout: float = 2.0) -> Optional[str]:
        """Send a custom command to scale"""
        return self.serial.query(command, response_timeout=timeout)

    def set_weight_filtering(self, enabled: bool):
        """Enable or disable weight filtering for troubleshooting"""
        self.weight_filter_enabled = enabled
        if not enabled:
            self.weight_history.clear()
        self.logger.info(f"Weight filtering {'enabled' if enabled else 'disabled'}")

    def clear_weight_history(self):
        """Clear weight history to reset filtering"""
        self.weight_history.clear()
        self.logger.debug("Weight history cleared")

    def is_connected(self) -> bool:
        """Check if scale is connected"""
        return self.serial.is_connected()

    def get_sensor_status(self) -> Dict[str, Any]:
        """Get status of all configured sensors"""
        status = {
            "connected": self.is_connected(),
            "reading": self.is_reading,
            "total_readings": self.reading_queue.qsize(),
            "current_weight": self.current_weight,
            "tared": self.is_tared,
            "tare_value": self.tare_value,
            "cache_size": len(self.weight_cache),
            "weight_filter_enabled": self.weight_filter_enabled,
            "weight_history_size": len(self.weight_history),
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


# Keep the same sensor configuration class
class ScaleSensorConfigurations:
    """Predefined sensor configurations for scale testing"""

    @staticmethod
    def weight_sensor(read_interval_ms: Optional[int] = None) -> List[SensorConfig]:
        """Standard weight sensor configuration"""
        interval = read_interval_ms or 50  # Default to 50ms for better responsiveness
        return [
            SensorConfig("SCALE", "WEIGHT", interval)
        ]
