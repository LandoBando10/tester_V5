import time
import logging
from typing import Dict, Any, List, Optional
from .base_test import BaseTest, TestResult
from src.hardware.offroad_arduino_controller import OffroadArduinoController
from src.hardware.arduino_controller import SensorConfigurations, TestResult as ArduinoTestResult, RGBWSample
from config.settings import SENSOR_TIMINGS, TEST_SENSOR_CONFIGS
import json


class OffroadTest(BaseTest):
    """Offroad pod testing implementation with FIXED Arduino communication"""

    def __init__(self, sku: str, parameters: Dict[str, Any], port: str, test_config: str = "offroad_standard", 
                 pressure_test_enabled: bool = False, arduino_controller=None):
        super().__init__(sku, parameters)
        self.port = port
        self.test_config = test_config
        self.pressure_test_enabled = pressure_test_enabled
        
        # Use provided Arduino controller or create new one
        self.arduino = arduino_controller
        self.owns_arduino = False  # Track if we created the Arduino instance
        if not self.arduino:
            self.arduino = OffroadArduinoController(baud_rate=115200)
            self.owns_arduino = True
            
        self.required_params = ["LUX", "COLOR"]  # PRESSURE is global

        # Data collection - now properly aligned with Arduino
        self.test_results: List[ArduinoTestResult] = []
        self.rgbw_samples: List[RGBWSample] = []
        self.pressure_readings: List[float] = []
        
        # Test state tracking
        self.current_test_phase = "IDLE"
        self.test_start_time = 0
        self.pressure_test_data = {}
        self.function_test_data = {}

    def setup_hardware(self) -> bool:
        """Initialize Arduino and sensors using correct protocol"""
        try:
            self.update_progress("Initializing test hardware...", 10)

            if not self.validate_parameters(self.required_params):
                return False

            # Only connect if we own the Arduino instance
            if self.owns_arduino and not self.arduino.is_connected():
                self.update_progress("Connecting to Arduino...", 15)
                if not self.arduino.connect(self.port):
                    self.logger.error(f"Failed to connect to Arduino on port {self.port}")
                    return False

            # Skip sensor configuration if already configured
            if not hasattr(self.arduino, '_sensors_configured'):
                self.update_progress("Checking sensors...", 20)
                # Configure sensors using SENSOR_CHECK (not JSON config)
                sensor_config = self._get_sensor_configuration()
                if not self.arduino.configure_sensors(sensor_config):
                    self.logger.error("Failed to configure sensors")
                    return False
                self.arduino._sensors_configured = True
                self.logger.info("Sensors configured successfully")
            else:
                self.logger.info("Sensors already configured, skipping")
                self.update_progress("Sensors ready", 20)

            self.update_progress("Setting up callbacks...", 30)

            # Set up result and RGBW callbacks
            self.arduino.result_callback = self._on_test_result
            self.arduino.rgbw_callback = self._on_rgbw_sample
            self.arduino.reading_callback = self._on_sensor_reading

            self.update_progress("Starting sensor monitoring...", 35)

            # Start sensor reading
            self.arduino.start_reading()

            # REMOVED: Sensor stabilization delay per user request
            # Sensors should be ready immediately

            self.update_progress("Hardware setup complete", 45)
            return True

        except Exception as e:
            self.logger.error(f"Hardware setup error: {e}")
            return False

    def _get_sensor_configuration(self):
        """Get sensor configuration for reference (Arduino auto-configures)"""
        if "precision" in self.test_config.lower():
            return SensorConfigurations.offroad_pod_sensors(read_interval_ms=10)
        else:
            return SensorConfigurations.offroad_pod_sensors(read_interval_ms=50)

    def _on_test_result(self, result: ArduinoTestResult):
        """Handle test result from Arduino"""
        self.logger.info(f"Received test result: {result.test_type}")
        self.test_results.append(result)
        
        # Store result data for analysis
        if result.test_type == "PRESSURE":
            self.pressure_test_data = result.measurements
        elif result.test_type in ["FUNCTION_TEST", "POWER"]:
            self.function_test_data = result.measurements

    def _on_rgbw_sample(self, sample: RGBWSample):
        """Handle RGBW sample from Arduino"""
        self.logger.debug(f"Received RGBW sample: Cycle {sample.cycle}")
        self.rgbw_samples.append(sample)

    def _on_sensor_reading(self, reading):
        """Handle live sensor reading from Arduino"""
        # Store pressure readings for live monitoring
        if reading.sensor_id == "PSI":
            self.pressure_readings.append(reading.value)
            # Keep only last 100 readings
            if len(self.pressure_readings) > 100:
                self.pressure_readings.pop(0)

    def run_test_sequence(self) -> TestResult:
        """Execute corrected offroad test sequence using RESULT parsing"""
        try:
            current_progress = 50
            
            # 1. Optional Pressure Decay Test (5 seconds total, if checkbox selected)
            if self.pressure_test_enabled:
                self.update_progress("Pressure decay test (5 seconds)...", current_progress)
                self._run_pressure_decay_test()
                current_progress = 60

            # 2. Function Test - Quick Sequential
            self.update_progress("Function test (mainbeam + backlight)...", current_progress)
            self._run_function_test()
            current_progress += 10

            # 3. Backlight Test(s) - Based on SKU Configuration  
            backlight_config = self._get_backlight_config(self.sku)
            
            if backlight_config["type"] == "dual":
                self.update_progress("Dual backlight test (1.0 seconds)...", current_progress)
                self._run_dual_backlight_test()
                current_progress += 15
                
            elif backlight_config["type"] == "rgbw_cycling":
                self.update_progress("RGBW cycling test (8 cycles)...", current_progress)
                self._run_rgbw_test(backlight_config)
                current_progress += 20

            self.update_progress("Analyzing results...", 90)
            self._analyze_arduino_results()

            return self.result

        except Exception as e:
            self.logger.error(f"Test sequence error: {e}")
            self.result.failures.append(f"Test sequence error: {str(e)}")
            return self.result

    def _run_pressure_decay_test(self):
        """Run 5-second pressure decay test using Arduino RESULT parsing"""
        try:
            # Clear previous pressure data
            self.pressure_test_data.clear()
            self.pressure_readings.clear()
            
            # Send pressure test command to Arduino
            response = self.arduino.send_command("TEST:PRESSURE", timeout=10.0)
            
            if response and "ERROR" in response:
                self.result.failures.append(f"Pressure test failed: {response}")
                return
            
            # Wait for test completion and RESULT message
            # Arduino will automatically send RESULT:INITIAL=14.5,DELTA=0.2
            max_wait_time = 15.0  # Give extra time for pressure test
            start_wait = time.time()
            
            while time.time() - start_wait < max_wait_time:
                if self.pressure_test_data:  # Result received
                    break
                time.sleep(0.1)
            
            if not self.pressure_test_data:
                self.result.failures.append("Pressure test: No result data received")
                    
        except Exception as e:
            self.logger.error(f"Pressure test error: {e}")
            self.result.failures.append(f"Pressure test error: {str(e)}")

    def _run_function_test(self):
        """Run function test using Arduino RESULT parsing"""
        try:
            # Clear previous function test data
            self.function_test_data.clear()
            
            # Send function test command to Arduino
            response = self.arduino.send_command("TEST:FUNCTION_TEST", timeout=10.0)
            
            if response and "ERROR" in response:
                self.result.failures.append(f"Function test failed: {response}")
                return
            
            # Wait for test completion and RESULT message
            # Arduino will send RESULT:MV_MAIN=12.5,MI_MAIN=1.2,LUX_MAIN=2500,...
            max_wait_time = 10.0
            start_wait = time.time()
            
            while time.time() - start_wait < max_wait_time:
                if self.function_test_data:  # Result received
                    break
                time.sleep(0.1)
            
            if not self.function_test_data:
                self.result.failures.append("Function test: No result data received")
                    
        except Exception as e:
            self.logger.error(f"Function test error: {e}")
            self.result.failures.append(f"Function test error: {str(e)}")

    def _run_dual_backlight_test(self):
        """Run dual backlight test using Arduino RESULT parsing"""
        try:
            # Clear previous test data
            dual_test_data = {}
            
            # Send dual backlight test command to Arduino
            response = self.arduino.send_command("TEST:DUAL_BACKLIGHT", timeout=10.0)
            
            if response and "ERROR" in response:
                self.result.failures.append(f"Dual backlight test failed: {response}")
                return
            
            # Wait for test completion and RESULT message
            # Arduino will send RESULT:MV_BACK1=12.5,MI_BACK1=1.2,LUX_BACK1=100,...
            max_wait_time = 10.0
            start_wait = time.time()
            
            while time.time() - start_wait < max_wait_time:
                latest_result = self.arduino.get_latest_test_result()
                if latest_result and latest_result.test_type == "DUAL_BACKLIGHT":
                    dual_test_data = latest_result.measurements
                    break
                time.sleep(0.1)
            
            if not dual_test_data:
                self.result.failures.append("Dual backlight test: No result data received")
            else:
                # Store dual backlight data for analysis
                self.function_test_data.update(dual_test_data)
                    
        except Exception as e:
            self.logger.error(f"Dual backlight test error: {e}")
            self.result.failures.append(f"Dual backlight test error: {str(e)}")

    def _run_rgbw_test(self, config):
        """Run RGBW test using Arduino RGBW_SAMPLE parsing"""
        try:
            self.logger.info("Starting RGBW backlight test with 8 cycles")
            
            # Clear previous RGBW data
            self.rgbw_samples.clear()
            self.arduino.clear_rgbw_samples()
            
            # Send RGBW test command to Arduino
            response = self.arduino.send_command("TEST:RGBW_BACKLIGHT", timeout=25.0)
            
            if response and "ERROR" in response:
                self.result.failures.append(f"RGBW test failed: {response}")
                return
            
            # Wait for test completion and collect RGBW_SAMPLE messages
            # Arduino will send multiple RGBW_SAMPLE:CYCLE=1,VOLTAGE=12.5,CURRENT=1.2,...
            max_wait_time = 20.0  # 8 cycles * ~1.4s each + buffer
            start_wait = time.time()
            
            while time.time() - start_wait < max_wait_time:
                # Check if we have samples from all 8 cycles
                cycle_numbers = set(sample.cycle for sample in self.rgbw_samples)
                if len(cycle_numbers) >= 8:  # Got samples from 8 cycles
                    break
                time.sleep(0.1)
            
            if len(self.rgbw_samples) == 0:
                self.result.failures.append("RGBW test: No sample data received")
                    
        except Exception as e:
            self.logger.error(f"RGBW test error: {e}")
            self.result.failures.append(f"RGBW test error: {str(e)}")

    def _get_backlight_config(self, sku: str) -> Dict[str, Any]:
        """Get backlight configuration from SKU data"""
        try:
            # Load SKU configuration
            with open("config/global_parameters.json", "r") as f:
                sku_data = json.load(f)
            
            # Find SKU configuration
            for sku_def in sku_data["sku_definitions"]:
                if sku_def["sku"] == sku:
                    return sku_def.get("backlight_config", {
                        "type": "single",
                        "relay_pins": [3],
                        "test_duration_ms": 500
                    })
            
            # Default to single backlight
            return {
                "type": "single",
                "relay_pins": [3],
                "test_duration_ms": 500
            }
            
        except Exception as e:
            self.logger.error(f"Error loading backlight config: {e}")
            return {
                "type": "single",
                "relay_pins": [3],
                "test_duration_ms": 500
            }

    def _analyze_arduino_results(self):
        """Analyze Arduino RESULT messages and generate test results"""
        try:
            self.update_progress("Analyzing results...", 85)
            
            # Debug output - show all raw test data collected
            if self.function_test_data:
                print("\n📊 Raw Function Test Data:")
                for key, value in self.function_test_data.items():
                    print(f"  {key}: {value}")
            
            if self.rgbw_samples:
                print(f"\n📊 RGBW Samples Collected: {len(self.rgbw_samples)}")
                for i, sample in enumerate(self.rgbw_samples):
                    print(f"  Sample {i}: Cycle={sample.cycle}, V={sample.voltage:.3f}, I={sample.current:.3f}, X={sample.x:.3f}, Y={sample.y:.3f}")

            # Get test parameters
            lux_params = self.parameters.get("LUX", {})
            color_params = self.parameters.get("COLOR", {})
            pressure_params = self.parameters.get("PRESSURE", {})

            # Analyze pressure test results
            if self.pressure_test_data:
                initial_pressure = self.pressure_test_data.get("INITIAL")
                pressure_delta = self.pressure_test_data.get("DELTA")
                
                if initial_pressure is not None:
                    self.result.add_measurement(
                        "initial_pressure",
                        initial_pressure,
                        pressure_params.get("min_initial_psi", 14.0),
                        pressure_params.get("max_initial_psi", 16.0),
                        "PSI"
                    )
                
                if pressure_delta is not None:
                    self.result.add_measurement(
                        "pressure_delta",
                        pressure_delta,
                        0.0,
                        pressure_params.get("max_delta_psi", 0.5),
                        "PSI"
                    )

            # Analyze function test results (mainbeam and backlight)
            if self.function_test_data:
                # Mainbeam current analysis
                mainbeam_current = self.function_test_data.get("MI_MAIN")
                if mainbeam_current is not None:
                    power_params = self._get_power_parameters()
                    if power_params:
                        self.result.add_measurement(
                            "mainbeam_current",
                            mainbeam_current,
                            power_params.get("min_mainbeam_current_A", 0.0),
                            power_params.get("max_mainbeam_current_A", 10.0),
                            "A"
                        )

                # Mainbeam LUX analysis
                mainbeam_lux = self.function_test_data.get("LUX_MAIN")
                if mainbeam_lux is not None and lux_params:
                    self.result.add_measurement(
                        "mainbeam_lux",
                        mainbeam_lux,
                        lux_params.get("min_mainbeam_lux", 0),
                        lux_params.get("max_mainbeam_lux", 10000),
                        "lux"
                    )

                # Mainbeam color analysis
                mainbeam_x = self.function_test_data.get("X_MAIN")
                mainbeam_y = self.function_test_data.get("Y_MAIN")
                if mainbeam_x is not None and mainbeam_y is not None and color_params:
                    self.result.add_measurement(
                        "color_x",
                        mainbeam_x,
                        color_params.get("center_x_main", 0.4) - color_params.get("radius_x_main", 0.02),
                        color_params.get("center_x_main", 0.4) + color_params.get("radius_x_main", 0.02),
                        "CIE_x"
                    )

                    self.result.add_measurement(
                        "color_y",
                        mainbeam_y,
                        color_params.get("center_y_main", 0.4) - color_params.get("radius_y_main", 0.02),
                        color_params.get("center_y_main", 0.4) + color_params.get("radius_y_main", 0.02),
                        "CIE_y"
                    )

                # Backlight analysis (single backlight from function test)
                backlight_lux = self.function_test_data.get("LUX_BACK")
                if backlight_lux is not None and lux_params:
                    self.result.add_measurement(
                        "backlight_lux",
                        backlight_lux,
                        lux_params.get("min_backlight_lux", 50),
                        lux_params.get("max_backlight_lux", 500),
                        "lux"
                    )

                backlight_x = self.function_test_data.get("X_BACK")
                backlight_y = self.function_test_data.get("Y_BACK")
                if backlight_x is not None and backlight_y is not None and color_params:
                    if "center_x_back" in color_params:
                        self.result.add_measurement(
                            "backlight_color_x",
                            backlight_x,
                            color_params.get("center_x_back", 0.4) - color_params.get("radius_x_back", 0.02),
                            color_params.get("center_x_back", 0.4) + color_params.get("radius_x_back", 0.02),
                            "CIE_x"
                        )
                        
                        self.result.add_measurement(
                            "backlight_color_y",
                            backlight_y,
                            color_params.get("center_y_back", 0.4) - color_params.get("radius_y_back", 0.02),
                            color_params.get("center_y_back", 0.4) + color_params.get("radius_y_back", 0.02),
                            "CIE_y"
                        )

                # Dual backlight analysis
                if "MV_BACK1" in self.function_test_data:  # Dual backlight data present
                    self.result.add_measurement(
                        "backlight1_detected",
                        1.0 if self.function_test_data.get("MI_BACK1", 0) > 0.01 else 0.0,
                        1.0,
                        1.0,
                        "bool"
                    )
                    
                    self.result.add_measurement(
                        "backlight2_detected", 
                        1.0 if self.function_test_data.get("MI_BACK2", 0) > 0.01 else 0.0,
                        1.0,
                        1.0,
                        "bool"
                    )

            # Analyze RGBW test results
            if self.rgbw_samples:
                self._analyze_rgbw_samples()

        except Exception as e:
            self.logger.error(f"Analysis error: {e}")
            self.result.failures.append(f"Analysis error: {str(e)}")

    def _analyze_rgbw_samples(self):
        """Analyze RGBW samples for color detection"""
        try:
            backlight_config = self._get_backlight_config(self.sku)
            expected_colors = backlight_config.get("colors_to_test", [])
            
            # Extract color coordinates from all samples
            x_values = [sample.x for sample in self.rgbw_samples]
            y_values = [sample.y for sample in self.rgbw_samples]
            
            if x_values and y_values:
                x_range = max(x_values) - min(x_values)
                y_range = max(y_values) - min(y_values)
                
                # Check for color variation
                if x_range > 0.1 or y_range > 0.1:
                    self.result.add_measurement(
                        "rgbw_color_range_x",
                        x_range,
                        0.1,  # Minimum variation expected
                        1.0,  # Maximum possible variation
                        "CIE_range"
                    )
                    
                    self.result.add_measurement(
                        "rgbw_color_range_y",
                        y_range,
                        0.1,  # Minimum variation expected
                        1.0,  # Maximum possible variation
                        "CIE_range"
                    )
                    
                    # Check for specific colors
                    for expected_color in expected_colors:
                        color_detected = self._detect_color_in_samples(expected_color)
                        
                        self.result.add_measurement(
                            f"rgbw_{expected_color['name']}_detected",
                            1.0 if color_detected else 0.0,
                            1.0,
                            1.0,
                            "bool"
                        )
                else:
                    self.result.failures.append("RGBW test: Insufficient color variation detected")
            else:
                self.result.failures.append("RGBW test: No color coordinate data found")
                
        except Exception as e:
            self.logger.error(f"RGBW analysis error: {e}")
            self.result.failures.append(f"RGBW analysis error: {str(e)}")

    def _detect_color_in_samples(self, expected_color):
        """Check if expected color was detected in RGBW samples"""
        target_x = expected_color["target_x"]
        target_y = expected_color["target_y"]
        tolerance = expected_color["tolerance"]
        
        # Check if any sample is close to the expected color
        for sample in self.rgbw_samples:
            distance = ((sample.x - target_x)**2 + (sample.y - target_y)**2)**0.5
            if distance <= tolerance:
                return True
        return False

    def _get_power_parameters(self) -> Dict[str, float]:
        """Get power parameters from SKU manager"""
        try:
            from src.data.sku_manager import create_sku_manager
            sku_mgr = create_sku_manager()
            return sku_mgr.get_power_draw_params(self.sku) or {}
        except Exception as e:
            self.logger.error(f"Error getting power parameters: {e}")
            return {}

    def _check_color_coordinates(self, x: float, y: float, color_params: Dict[str, Any]) -> bool:
        """Check if color coordinates are within acceptable ellipse"""
        center_x = color_params.get("center_x_main", 0.4)
        center_y = color_params.get("center_y_main", 0.4)
        radius_x = color_params.get("radius_x_main", 0.02)
        radius_y = color_params.get("radius_y_main", 0.02)

        # Simple ellipse check
        normalized_x = (x - center_x) / radius_x
        normalized_y = (y - center_y) / radius_y

        return (normalized_x ** 2 + normalized_y ** 2) <= 1.0

    def cleanup_hardware(self):
        """Clean up Arduino connection using STOP command only"""
        try:
            self.update_progress("Cleaning up hardware...", 95)

            # Arduino handles cleanup automatically with STOP command
            self.arduino.send_command("STOP")
            
            # Stop reading
            self.arduino.stop_reading()
            
            # Only disconnect if we own the Arduino instance
            if self.owns_arduino:
                self.arduino.disconnect()

            self.logger.info("Hardware cleanup complete")

        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example test parameters (would come from SKU manager)
    parameters = {
        "LUX": {
            "min_mainbeam_lux": 2000,
            "max_mainbeam_lux": 2500,
            "min_backlight_lux": 100,
            "max_backlight_lux": 150
        },
        "COLOR": {
            "center_x_main": 0.450,
            "center_y_main": 0.410,
            "radius_x_main": 0.015,
            "radius_y_main": 0.015,
            "angle_deg_main": 0
        },
        "PRESSURE": {
            "min_initial_psi": 14.0,
            "max_initial_psi": 16.0,
            "max_delta_psi": 0.5
        }
    }

    def progress_callback(message: str, percentage: int):
        print(f"[{percentage:3d}%] {message}")

    print("FIXED Offroad test module loaded with proper Arduino communication:")
    print("✅ Uses SENSOR_CHECK instead of CONFIG")
    print("✅ Parses RESULT messages instead of averaging readings")
    print("✅ Handles RGBW_SAMPLE messages for color cycling")
    print("✅ Cleanup uses STOP command only")
    print("✅ Proper callback handling for Arduino messages")
