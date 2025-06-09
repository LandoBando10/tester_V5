from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import logging


class TestResult:
    """Container for test results"""

    def __init__(self):
        self.passed = False
        self.measurements = {}
        self.parameters = {}
        self.failures = []
        self.timestamp = datetime.now()
        self.test_duration = 0.0

    def add_measurement(self, name: str, value: float, min_val: float, max_val: float, unit: str = ""):
        """Add a measurement with pass/fail evaluation"""
        passed = min_val <= value <= max_val
        self.measurements[name] = {
            'value': value,
            'min': min_val,
            'max': max_val,
            'unit': unit,
            'passed': passed
        }

        if not passed:
            self.failures.append(f"{name}: {value}{unit} not in range [{min_val}-{max_val}]{unit}")

    def calculate_overall_result(self):
        """Determine if overall test passed"""
        self.passed = len(self.failures) == 0 and len(self.measurements) > 0


class BaseTest(ABC):
    """Abstract base class for all test modes"""

    def __init__(self, sku: str, parameters: Dict[str, Any]):
        self.sku = sku
        self.parameters = parameters
        self.result = TestResult()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.progress_callback: Optional[Callable[[str, int], None]] = None

    def set_progress_callback(self, callback: Callable[[str, int], None]):
        """Set callback for progress updates (message, percentage)"""
        self.progress_callback = callback

    def update_progress(self, message: str, percentage: int):
        """Update progress if callback is set"""
        if self.progress_callback:
            self.progress_callback(message, percentage)
        self.logger.info(f"Progress: {message} ({percentage}%)")

    @abstractmethod
    def setup_hardware(self) -> bool:
        """Initialize hardware connections. Returns True if successful."""
        pass

    @abstractmethod
    def run_test_sequence(self) -> TestResult:
        """Execute the test sequence. Returns TestResult object."""
        pass

    @abstractmethod
    def cleanup_hardware(self):
        """Clean up hardware connections"""
        pass

    def execute(self) -> TestResult:
        """Main test execution method"""
        start_time = datetime.now()

        try:
            self.logger.info(f"Starting {self.__class__.__name__} for SKU {self.sku}")
            self.update_progress("Initializing hardware...", 10)

            if not self.setup_hardware():
                self.result.failures.append("Hardware initialization failed")
                self.result.calculate_overall_result()
                return self.result

            self.update_progress("Running test sequence...", 30)
            self.result = self.run_test_sequence()

            self.update_progress("Evaluating results...", 90)
            self.result.calculate_overall_result()

        except Exception as e:
            self.logger.error(f"Test execution error: {e}")
            self.result.failures.append(f"Test execution error: {str(e)}")

        finally:
            self.cleanup_hardware()
            end_time = datetime.now()
            self.result.test_duration = (end_time - start_time).total_seconds()
            self.update_progress("Test complete", 100)

        self.logger.info(f"Test completed. Result: {'PASS' if self.result.passed else 'FAIL'}")
        return self.result

    def validate_parameters(self, required_params: list) -> bool:
        """Validate that required parameters are present"""
        missing = []
        for param in required_params:
            if param not in self.parameters:
                missing.append(param)

        if missing:
            self.logger.error(f"Missing required parameters: {missing}")
            return False
        return True


# Example concrete implementation for testing
class DummyTest(BaseTest):
    """Dummy test implementation for testing the base class"""

    def setup_hardware(self) -> bool:
        self.update_progress("Setting up dummy hardware...", 0)
        return True

    def run_test_sequence(self) -> TestResult:
        import time

        # Simulate some measurements
        self.update_progress("Taking measurements...", 50)
        time.sleep(1)  # Simulate test time

        # Add some dummy measurements
        self.result.add_measurement("voltage", 12.5, 12.0, 13.0, "V")
        self.result.add_measurement("current", 1.8, 1.5, 2.0, "A")

        return self.result

    def cleanup_hardware(self):
        self.update_progress("Cleaning up dummy hardware...", 0)


if __name__ == "__main__":
    # Test the base class with dummy implementation
    logging.basicConfig(level=logging.INFO)


    def progress_handler(message, percentage):
        print(f"[{percentage:3d}%] {message}")


    test = DummyTest("DD5000", {"test_param": "value"})
    test.set_progress_callback(progress_handler)
    result = test.execute()

    print(f"\nTest Result: {'PASS' if result.passed else 'FAIL'}")
    print(f"Duration: {result.test_duration:.2f}s")
    if result.failures:
        print("Failures:", result.failures)