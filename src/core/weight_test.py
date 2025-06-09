import time
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from src.core.base_test import BaseTest, TestResult
from src.hardware.scale_controller import ScaleController, ScaleSensorConfigurations


class WeightTest(BaseTest):
    """Weight test implementation following established architecture patterns"""

    def __init__(self, sku: str, parameters: Dict[str, Any], port: str, weights_json_path: Optional[str] = None):
        super().__init__(sku, parameters)
        self.port = port
        self.weights_json_path = weights_json_path
        self.scale = ScaleController(baud_rate=9600)  # Use controller pattern
        self.required_params = ["WEIGHT"]
        
        # Test state (minimal - controller handles most state)
        self.current_weight_display = None
        self.weight_history = []
        
        # Weight specifications
        self.spec_data = {}
        self.current_part = None

    def setup_hardware(self) -> bool:
        """Initialize scale controller using established pattern"""
        try:
            self.update_progress("Connecting to scale...", 15)

            if not self.validate_parameters(self.required_params):
                return False

            # Connect using controller pattern
            if not self.scale.connect(self.port):
                self.logger.error(f"Failed to connect to scale on port {self.port}")
                return False

            self.update_progress("Configuring scale sensors...", 25)

            # Configure sensors using controller pattern
            sensor_config = ScaleSensorConfigurations.weight_sensor(read_interval_ms=100)
            if not self.scale.configure_sensors(sensor_config):
                self.logger.error("Failed to configure scale sensors")
                return False

            self.update_progress("Loading weight specifications...", 30)

            # Load weight specifications if provided
            if self.weights_json_path:
                if self._load_weight_specifications():
                    # Try to set current part based on SKU
                    if self.current_part in self.spec_data:
                        self.logger.info(f"Using weight specs for part: {self.current_part}")
                    else:
                        self.logger.warning(f"No weight specs found for SKU: {self.sku}")

            self.update_progress("Setting up callbacks...", 35)

            # Set up callbacks using controller pattern
            self.scale.reading_callback = self._on_weight_reading
            self.scale.weight_callback = self._on_weight_update

            self.update_progress("Starting weight monitoring...", 40)

            # Start reading using controller's standardized method
            self.scale.start_reading()

            # Give scale time to stabilize
            time.sleep(1)

            self.update_progress("Hardware setup complete", 45)
            return True

        except Exception as e:
            self.logger.error(f"Hardware setup error: {e}")
            return False

    def _load_weight_specifications(self) -> bool:
        """Load weight specifications from JSON file"""
        try:
            path = Path(self.weights_json_path)
            if not path.exists():
                self.logger.error(f"Weight spec file not found: {self.weights_json_path}")
                return False

            with open(path, 'r', encoding='utf-8') as f:
                self.spec_data = json.load(f)

            # Basic validation
            if not isinstance(self.spec_data, dict):
                raise ValueError("Invalid JSON format. Expecting dict of parts with 'min'/'max'.")

            for part_name, spec in self.spec_data.items():
                if not isinstance(spec, dict) or 'min' not in spec or 'max' not in spec:
                    raise ValueError(f"Invalid spec for part {part_name}. Expecting 'min'/'max' keys.")

            # Set current part to SKU if it exists in specs
            if self.sku in self.spec_data:
                self.current_part = self.sku
            
            self.logger.info(f"Loaded weight specs for parts: {list(self.spec_data.keys())}")
            return True

        except Exception as e:
            self.logger.error(f"Error loading weight specs: {e}")
            self.spec_data = {}
            return False

    def _on_weight_reading(self, reading):
        """Handle standardized weight reading (following Arduino pattern)"""
        if reading.sensor_id == "WEIGHT":
            self.current_weight_display = reading.value
            self.weight_history.append(reading.value)
            
            # Keep only recent history (last 50 readings)
            if len(self.weight_history) > 50:
                self.weight_history.pop(0)

    def _on_weight_update(self, weight: float):
        """Handle weight-specific callback"""
        # Log significant weight changes
        if len(self.weight_history) > 1:
            weight_change = abs(weight - self.weight_history[-2])
            if weight_change > 1.0:  # Log changes > 1g
                self.logger.debug(f"Weight change: {weight:.2f}g (Δ{weight_change:.2f}g)")

    def run_test_sequence(self) -> TestResult:
        """Execute weight measurement using controller pattern"""
        try:
            weight_params = self.parameters["WEIGHT"]
            min_weight = weight_params["min_weight_g"]
            max_weight = weight_params["max_weight_g"]
            tare_offset = weight_params.get("tare_g", 0.0)

            self.update_progress("Waiting for part placement...", 50)

            # Wait for part using controller's standardized approach
            part_detected = self._wait_for_part_placement()

            if not part_detected:
                self.result.failures.append("No part detected within timeout period")
                return self.result

            self.update_progress("Part detected, measuring weight...", 70)

            # Get stable weight using controller method
            measured_weight = self.scale.get_stable_weight(
                num_readings=5,
                tolerance=0.05,
                timeout=10.0
            )

            if measured_weight is None:
                self.result.failures.append("Could not get stable weight reading")
                return self.result

            # Apply tare offset if specified
            final_weight = measured_weight - tare_offset

            self.update_progress("Recording measurement...", 85)

            # Record the measurement
            self.result.add_measurement(
                name="weight",
                value=final_weight,
                min_val=min_weight,
                max_val=max_weight,
                unit="g"
            )

            # If we have weight specs loaded, add grading information
            if self.current_part and self.current_part in self.spec_data:
                grading_result = self._get_weight_grading_result(final_weight)
                self.logger.info(f"Weight grading result: {grading_result}")

            self.logger.info(f"Weight measurement: {final_weight:.3f}g "
                             f"(Range: {min_weight}-{max_weight}g)")

            return self.result

        except Exception as e:
            self.logger.error(f"Test sequence error: {e}")
            self.result.failures.append(f"Test sequence error: {str(e)}")
            return self.result

    def _wait_for_part_placement(self, timeout: float = 30.0) -> bool:
        """Wait for part placement using controller pattern"""
        start_time = time.time()
        stable_threshold = 1.0  # grams - minimum weight to consider part present
        stability_time = 2.0    # seconds - how long weight must be stable

        stable_start = None

        while time.time() - start_time < timeout:
            # Use controller's current weight
            current_weight = self.scale.current_weight

            if current_weight is not None and abs(current_weight) > stable_threshold:
                if stable_start is None:
                    stable_start = time.time()
                    self.logger.debug(f"Potential part detected: {current_weight:.2f}g")
                elif time.time() - stable_start >= stability_time:
                    self.logger.info(f"Part confirmed with stable weight: {current_weight:.2f}g")
                    return True
            else:
                stable_start = None  # Reset stability timer

            # Update progress based on time elapsed
            elapsed = time.time() - start_time
            progress = 50 + int((elapsed / timeout) * 15)  # 50-65% range
            remaining = int(timeout - elapsed)

            weight_display = f" (Current: {current_weight:.1f}g)" if current_weight else ""
            self.update_progress(f"Waiting for part ({remaining}s){weight_display}", progress)

            time.sleep(0.5)

        self.logger.warning("Timeout waiting for part placement")
        return False

    def _get_weight_grading_result(self, weight: float) -> Dict[str, Any]:
        """Get weight grading result using loaded specifications"""
        result = {
            'weight': weight,
            'part': self.current_part,
            'verdict': None,
            'min_weight': None,
            'max_weight': None,
            'passed': False
        }

        if self.current_part and self.current_part in self.spec_data:
            limits = self.spec_data[self.current_part]
            try:
                min_weight = float(limits["min"])
                max_weight = float(limits["max"])

                result['min_weight'] = min_weight
                result['max_weight'] = max_weight
                result['passed'] = min_weight <= weight <= max_weight
                result['verdict'] = "PASS" if result['passed'] else "FAIL"

            except (KeyError, ValueError) as e:
                self.logger.error(f"Error in weight grading: {e}")
                result['verdict'] = "ERROR"

        return result

    def cleanup_hardware(self):
        """Clean up using controller pattern"""
        try:
            self.update_progress("Disconnecting scale...", 95)
            
            # Use controller's standardized cleanup
            self.scale.stop_reading()
            self.scale.disconnect()
            
            self.logger.info("Scale cleanup complete")
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")

    def get_real_time_weight(self) -> Optional[float]:
        """Get real-time weight using controller"""
        return self.scale.current_weight

    def get_weight_statistics(self) -> Dict[str, float]:
        """Get statistics on recent weight readings"""
        if not self.weight_history:
            return {}

        return {
            'count': len(self.weight_history),
            'min': min(self.weight_history),
            'max': max(self.weight_history),
            'average': sum(self.weight_history) / len(self.weight_history),
            'latest': self.weight_history[-1] if self.weight_history else None
        }

    def get_sensor_status(self) -> Dict[str, Any]:
        """Get scale sensor status using controller"""
        return self.scale.get_sensor_status()


# Standalone test function for development/testing
def run_weight_test(sku: str, port: str, min_weight: float, max_weight: float,
                   weights_json: Optional[str] = None):
    """Standalone function to test weight checking using refactored architecture"""
    logging.basicConfig(level=logging.INFO)

    # Create test parameters
    parameters = {
        "WEIGHT": {
            "min_weight_g": min_weight,
            "max_weight_g": max_weight,
            "tare_g": 0.0
        }
    }

    def progress_callback(message: str, percentage: int):
        print(f"[{percentage:3d}%] {message}")

    # Run the test
    test = WeightTest(sku, parameters, port, weights_json)
    test.set_progress_callback(progress_callback)

    result = test.execute()

    # Display results
    print(f"\n{'=' * 60}")
    print(f"Weight Test Results for SKU: {sku}")
    print(f"{'=' * 60}")
    print(f"Overall Result: {'PASS' if result.passed else 'FAIL'}")
    print(f"Test Duration: {result.test_duration:.2f} seconds")

    if result.measurements:
        print(f"\nMeasurements:")
        for name, data in result.measurements.items():
            status = "PASS" if data['passed'] else "FAIL"
            print(f"  {name}: {data['value']:.3f}{data['unit']} "
                  f"[{data['min']}-{data['max']}]{data['unit']} - {status}")

    # Show weight statistics
    stats = test.get_weight_statistics()
    if stats:
        print(f"\nWeight Reading Statistics:")
        print(f"  Readings taken: {stats['count']}")
        print(f"  Min: {stats['min']:.3f}g")
        print(f"  Max: {stats['max']:.3f}g")
        print(f"  Average: {stats['average']:.3f}g")

    if result.failures:
        print(f"\nFailures:")
        for failure in result.failures:
            print(f"  - {failure}")

    return result


# Example usage
if __name__ == "__main__":
    print("Refactored Weight Test module loaded following established patterns:")
    print("✅ Uses ScaleController following Arduino controller pattern")
    print("✅ Follows BaseTest inheritance with proper lifecycle")
    print("✅ Uses standardized callbacks and resource management")
    print("✅ Compatible with existing test infrastructure")
    print("✅ Separated concerns: hardware control vs test logic")
    
    # Example test - replace with actual values
    # result = run_weight_test("DD5000", "COM3", 10.0, 15.0, "weights.json")
