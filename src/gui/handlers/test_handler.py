# gui/handlers/test_handler.py
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QObject

from src.gui.workers.test_worker import TestWorker
from src.core.base_test import TestResult
from src.utils.thread_cleanup import ThreadCleanupMixin


class TestHandler(QObject, ThreadCleanupMixin):
    """Handles test execution logic and coordination"""
    
    def __init__(self, main_window):
        QObject.__init__(self)
        ThreadCleanupMixin.__init__(self)
        self.main_window = main_window
        self.logger = logging.getLogger(self.__class__.__name__)
        self.current_test_worker: Optional[TestWorker] = None
        self.logger.debug("TestHandler initialized")
    
    def start_test(self, sku: str, mode: str, enabled_tests: List[str], connection_status: Dict[str, Any]):
        """Start the selected test with comprehensive validation"""
        self.logger.info(f"Attempting to start test for SKU: {sku}, Mode: {mode}, Enabled Tests: {enabled_tests}")
        try:
            # Validation
            if not sku or sku == "-- Select SKU --":
                self.logger.warning("SKU not selected.")
                QMessageBox.warning(self.main_window, "Warning", "Please select a SKU")
                return
            self.logger.debug("SKU selected: %s", sku)
            
            # Mode-specific connection validation
            if mode == "WeightChecking":
                if not self._validate_weight_connections():
                    self.logger.warning("Weight connection validation failed.")
                    return
                self.logger.debug("Weight connections validated.")
            else:
                if not self._validate_arduino_connections(connection_status):
                    self.logger.warning("Arduino connection validation failed.")
                    return
                self.logger.debug("Arduino connections validated.")
            
            # Validate SKU/mode combination
            if not self.main_window.sku_manager.validate_sku_mode_combination(sku, mode):
                self.logger.warning(f"SKU {sku} does not support {mode} mode.")
                QMessageBox.warning(self.main_window, "Warning", f"SKU {sku} does not support {mode} mode")
                return
            self.logger.debug("SKU/mode combination validated.")
            
            # Get test parameters
            params = self.main_window.sku_manager.get_test_parameters(sku, mode)
            if not params:
                self.logger.error(f"No parameters found for {sku} in {mode} mode.")
                QMessageBox.critical(self.main_window, "Error", f"No parameters found for {sku} in {mode} mode")
                return
            self.logger.debug("Test parameters retrieved: %s", params)
            
            # Check which tests are enabled
            if not enabled_tests and mode != "WeightChecking":
                self.logger.warning("No tests selected to run.")
                QMessageBox.warning(self.main_window, "Warning", "Please select at least one test to run")
                return
            self.logger.debug("Enabled tests: %s", enabled_tests)
            
            # Update programming status in test area for SMT mode
            if mode == "SMT":
                programming_enabled = "PROGRAMMING" in enabled_tests
                self.main_window.test_area.set_programming_enabled(programming_enabled)
                self.logger.info(f"Programming for SMT mode set to: {programming_enabled}")
            
            # Create test instance
            self.logger.debug("Creating test instance...")
            test_instance = self._create_test_instance(sku, mode, params, enabled_tests, connection_status)
            if not test_instance:
                self.logger.error("Failed to create test instance.")
                # QMessageBox is handled within _create_test_instance
                return
            self.logger.info(f"Test instance created: {test_instance.__class__.__name__}")
            
            # Update UI for testing
            self.main_window.start_testing_ui()
            self.logger.debug("UI updated for testing state.")
              # Create and start worker thread
            self.current_test_worker = TestWorker(test_instance)
            self.logger.debug("TestWorker created.")
            
            # Register the QThread for resource tracking
            worker_name = f"test_worker_{sku}_{mode}"
            self.register_qthread(self.current_test_worker, worker_name)
            self.logger.info(f"QThread '{worker_name}' registered for resource tracking.")
            
            self.current_test_worker.test_completed.connect(self.main_window.test_completed)
            self.current_test_worker.progress_updated.connect(self._handle_progress_update)
            self.current_test_worker.pressure_data.connect(self._handle_pressure_data)
            self.current_test_worker.test_phase_changed.connect(self._handle_phase_change)
            self.current_test_worker.start()
            self.logger.info(f"Test worker started for SKU: {sku}, Mode: {mode}")
            
        except Exception as e:
            self.logger.error(f"Error starting test: {e}", exc_info=True)
            QMessageBox.critical(self.main_window, "Error", f"Could not start test: {e}")
    
    def _validate_weight_connections(self) -> bool:
        """Validate connections for weight testing"""
        self.logger.debug("Validating weight connections.")
        # Weight testing uses its own connection management
        if not hasattr(self.main_window.test_area, 'weight_test_widget'):
            self.logger.warning("Weight testing widget not available.")
            QMessageBox.warning(self.main_window, "Warning", "Weight testing widget not available")
            return False
        
        # The weight widget manages its own connections
        self.logger.debug("Weight connection validation successful (delegated to widget).")
        return True
    
    def _validate_arduino_connections(self, connection_status: Dict[str, Any]) -> bool:
        """Validate Arduino connections for Offroad/SMT testing"""
        self.logger.debug("Validating Arduino connections.")
        if not connection_status.get('arduino_connected', False):
            self.logger.warning("Arduino not connected.")
            QMessageBox.warning(self.main_window, "Warning",
                                "Please connect to Arduino first (Connection → Hardware Connections)")
            return False
        self.logger.debug("Arduino connection validation successful.")
        return True
    
    def _create_test_instance(self, sku: str, mode: str, params: Dict[str, Any], 
                             enabled_tests: List[str], connection_status: Dict[str, Any]):
        """Create appropriate test instance based on mode"""
        self.logger.info(f"Creating test instance for SKU: {sku}, Mode: {mode}")
        try:
            if mode == "WeightChecking":
                self.logger.debug("Attempting to create WeightTest instance.")
                from src.core.weight_test import WeightTest
                # For weight testing, we need to get the port from the weight widget
                try:
                    weight_widget = self.main_window.test_area.weight_test_widget
                    if weight_widget and hasattr(weight_widget, 'get_connection_status'):
                        weight_status = weight_widget.get_connection_status()
                        port = weight_status.get('port')
                        if port:
                            # Create weights JSON path
                            weights_json_path = "weights.json"  # Could be configurable
                            self.logger.info(f"WeightTest instance created with port: {port}, weights_json: {weights_json_path}")
                            return WeightTest(sku, params, port, weights_json_path)
                        else:
                            self.logger.warning("No scale connection found for WeightTest.")
                            QMessageBox.warning(self.main_window, "Warning", 
                                                "No scale connection found. Please connect scale first.")
                            return None
                    else:
                        self.logger.warning("Weight testing widget not properly initialized for WeightTest.")
                        QMessageBox.warning(self.main_window, "Warning", 
                                            "Weight testing widget not properly initialized.")
                        return None
                except Exception as e:
                    self.logger.error(f"Error setting up weight test: {e}", exc_info=True)
                    QMessageBox.critical(self.main_window, "Error", 
                                         f"Could not setup weight test: {e}")
                    return None
                
            elif mode == "Offroad":
                self.logger.debug("Attempting to create OffroadTest instance.")
                from src.core import offroad_test
                port = connection_status['arduino_port']
                test_config = "offroad_standard"  # Could be made configurable
                pressure_test_enabled = "PRESSURE" in enabled_tests
                self.logger.info(f"OffroadTest instance created with port: {port}, config: {test_config}, pressure_enabled: {pressure_test_enabled}")
                return offroad_test.OffroadTest(sku, params, port, test_config, pressure_test_enabled)
                
            elif mode == "SMT":
                self.logger.debug("Attempting to create SMTTest instance.")
                from src.core.smt_test import SMTTest
                port = connection_status['arduino_port']
                
                # Get programming configuration if programming is enabled
                programming_config = None
                if "PROGRAMMING" in enabled_tests:
                    self.logger.debug("Programming enabled for SMT test, getting config.")
                    programming_config = self._get_programming_config(sku)
                    if not programming_config:
                        self.logger.warning(f"No programming config for SKU {sku}. Asking user to continue.")
                        reply = QMessageBox.question(
                            self.main_window, "Programming Configuration",
                            "No programming configuration found. Continue with power testing only?",
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.No
                        )
                        if reply == QMessageBox.No:
                            self.logger.info("User chose not to continue without programming config.")
                            return None
                        self.logger.info("User chose to continue without programming config.")
                
                self.logger.info(f"SMTTest instance created with port: {port}, programming_config: {'present' if programming_config else 'absent'}")
                return SMTTest(sku, params, port, programming_config)
            else:
                self.logger.warning(f"Mode {mode} not implemented yet.")
                QMessageBox.information(self.main_window, "Info", f"{mode} mode not implemented yet")
                return None
                
        except ImportError as e:
            self.logger.error(f"Import error creating test instance: {e}", exc_info=True)
            QMessageBox.critical(self.main_window, "Import Error", 
                                 f"Could not import test module: {e}\\n\\nPlease ensure all test modules are available.")
            return None
        except KeyError as e:
            self.logger.error(f"Missing key in connection_status: {e} for mode {mode}", exc_info=True)
            QMessageBox.critical(self.main_window, "Configuration Error", f"Missing connection data for {mode} mode: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error creating test instance: {e}", exc_info=True)
            QMessageBox.critical(self.main_window, "Error", f"Could not create test instance: {e}")
            return None
    
    def _get_programming_config(self, sku: str) -> Optional[Dict]:
        """Get programming configuration for SMT testing from SKU file"""
        self.logger.debug(f"Getting programming config for SKU: {sku}")
        try:
            # Get SKU configuration
            sku_data = self.sku_manager.get_sku(sku)
            if not sku_data:
                self.logger.warning(f"SKU {sku} not found")
                return None
            
            # Get programming configuration from smt_testing section
            smt_config = sku_data.get("smt_testing", {})
            programming_config = smt_config.get("programming", {})
            
            if not programming_config:
                self.logger.warning(f"No programming configuration found for SKU: {sku}")
                return None
            
            # Validate that programming is enabled for this SKU
            if not programming_config.get("enabled", False):
                self.logger.warning(f"Programming disabled for SKU: {sku}")
                return None
            
            self.logger.info(f"Loaded programming config for SKU: {sku}")
            return programming_config
                
        except Exception as e:
            self.logger.error(f"Error loading programming config for SKU {sku}: {e}", exc_info=True)
            QMessageBox.critical(self.main_window, "Error",
                                f"An unexpected error occurred while loading programming configuration for {sku}.")
            return None
    
    def stop_current_test(self):
        """Stop the currently running test"""
        self.logger.info("Attempting to stop current test.")
        try:
            if self.current_test_worker and self.current_test_worker.isRunning():
                self.logger.info("Stopping current test worker...")
                self.current_test_worker.terminate() # Request termination
                if not self.current_test_worker.wait(5000):  # Wait up to 5 seconds
                    self.logger.warning("Test worker did not stop gracefully after terminate(), trying to kill.")
                    # In Qt, QThread.kill() is not a method. terminate() is the forceful way.
                    # If it's still running, it might be stuck.
                    # We rely on the resource manager to eventually clean up if it's truly stuck.
                else:
                    self.logger.info("Test worker stopped after terminate().")

                # Resource manager will handle unregistering if needed during cleanup
                self.current_test_worker = None # Dereference
                self.logger.info("Test stopped successfully and worker dereferenced.")
            elif self.current_test_worker:
                self.logger.info("Test worker exists but is not running. Dereferencing.")
                self.current_test_worker = None # Dereference
            else:
                self.logger.info("No current test worker to stop.")
                
        except Exception as e:
            self.logger.error(f"Error stopping test: {e}", exc_info=True)
            # Potentially inform user if critical, but usually this is an internal cleanup
    
    def is_test_running(self) -> bool:
        """Check if a test is currently running"""
        running = (self.current_test_worker is not None and 
                   self.current_test_worker.isRunning())
        self.logger.debug(f"is_test_running: {running}")
        return running
    
    def get_test_status(self) -> Dict[str, Any]:
        """Get current test status information"""
        status = {
            'running': self.is_test_running(),
            'worker_exists': self.current_test_worker is not None,
            'worker_finished': (self.current_test_worker is not None and 
                                self.current_test_worker.isFinished() if self.current_test_worker else False)
        }
        self.logger.debug(f"get_test_status: {status}")
        return status
    
    def cleanup(self):
        """Cleanup test handler with comprehensive resource management"""
        self.logger.info("Starting test handler cleanup...")
        try:
            # Stop any running test
            if self.current_test_worker and self.current_test_worker.isRunning():
                self.logger.info("Cleaning up: stopping running test worker...")
                self.current_test_worker.terminate() # Request termination
                if not self.current_test_worker.wait(3000):  # Wait up to 3 seconds
                    self.logger.warning("Test worker did not stop gracefully during cleanup.")
                else:
                    self.logger.info("Running test worker stopped during cleanup.")
            
            self.current_test_worker = None # Dereference
            
            # Use resource manager for comprehensive cleanup
            self.logger.debug("Calling cleanup_resources().")
            self.cleanup_resources() # This will handle unregistering the QThread
            
            self.logger.info("Test handler cleanup completed.")
                
        except Exception as e:
            self.logger.error(f"Error during test handler cleanup: {e}", exc_info=True)
    
    def handle_test_completion(self, result: TestResult):
        """Handle test completion and cleanup"""
        self.logger.info(f"Handling test completion. Result: {'PASS' if result.passed else 'FAIL'}")
        try:
            # Clean up worker
            if self.current_test_worker:
                self.logger.debug("Cleaning up test worker after completion.")
                if not self.current_test_worker.isFinished():
                    self.logger.warning("Test worker was not finished. Waiting briefly.")
                    self.current_test_worker.wait(1000) # Brief wait
                # The worker should be unregistered by cleanup_resources if it was registered
                self.current_test_worker = None # Dereference
                self.logger.debug("Test worker dereferenced after completion.")
            
            # Log test summary
            if result.measurements:
                self.logger.info(f"Test measurements ({len(result.measurements)} items): {result.measurements}")
            if result.failures:
                self.logger.warning(f"Test failures: {result.failures}")
            # Use stored values from self since TestResult doesn't have sku/mode attributes
            self.logger.info(f"Test completed. SKU: {self.main_window.top_controls.sku_combo.currentText()}, Mode: {self.main_window.top_controls.current_mode}, Duration: {result.test_duration:.2f}s")
                
        except Exception as e:
            self.logger.error(f"Error handling test completion: {e}", exc_info=True)
    
    def create_test_report(self, result: TestResult, sku: str, mode: str) -> str:
        """Create a formatted test report"""
        self.logger.info(f"Creating test report for SKU: {sku}, Mode: {mode}, Result: {'PASS' if result.passed else 'FAIL'}")
        try:
            report_lines = []
            report_lines.append("=" * 60)
            report_lines.append(f"DIODE DYNAMICS TEST REPORT")
            report_lines.append("=" * 60)
            report_lines.append(f"SKU: {sku}") # Use passed sku, result.sku might not be set if test init failed
            report_lines.append(f"Test Mode: {mode}") # Use passed mode
            report_lines.append(f"Result: {'PASS' if result.passed else 'FAIL'}")
            report_lines.append(f"Duration: {result.test_duration:.2f} seconds" if result.test_duration is not None else "Duration: N/A")
            report_lines.append(f"Timestamp: {result.timestamp}")
            report_lines.append("")
            
            if result.measurements:
                report_lines.append("MEASUREMENTS:")
                report_lines.append("-" * 40)
                for name, data in result.measurements.items():
                    if isinstance(data, dict) and 'value' in data:
                        status = "PASS" if data.get('passed', True) else "FAIL"
                        unit = data.get('unit', '')
                        value_str = f"{data['value']:.2f}" if isinstance(data['value'], float) else str(data['value'])
                        report_lines.append(f"  {name}: {value_str} {unit} [{status}]")
                    else: # Handle simpler measurement structures if any
                        report_lines.append(f"  {name}: {data}")
                report_lines.append("-" * 40)
            else:
                report_lines.append("No measurements recorded.")
            report_lines.append("")

            if result.failures:
                report_lines.append("FAILURES/ERRORS:")
                report_lines.append("-" * 40)
                for failure in result.failures:
                    report_lines.append(f"  - {failure}")
                report_lines.append("-" * 40)
            else:
                if result.passed:
                    report_lines.append("No failures or errors.")
            report_lines.append("")

            if result.log_messages:
                report_lines.append("TEST LOG:")
                report_lines.append("-" * 40)
                for log_msg in result.log_messages:
                    report_lines.append(f"  {log_msg}")
                report_lines.append("-" * 40)
            
            report_lines.append("=" * 60)
            report_content = "\\n".join(report_lines)
            self.logger.info("Test report generated successfully.")
            # self.logger.debug(f"Report content:\\n{report_content}") # Can be verbose
            return report_content
        except Exception as e:
            self.logger.error(f"Error creating test report: {e}", exc_info=True)
            return f"Error generating report: {e}"

    # Placeholder for signal handlers if needed directly in TestHandler
    # These are currently connected from MainWindow to TestWorker signals
    def _handle_progress_update(self, value: int, message: str):
        # This method is connected to current_test_worker.progress_updated
        # MainWindow.update_progress_bar also connects to this signal
        self.logger.debug(f"Progress update: {value}% - {message}")
        # Potentially add TestHandler specific logic here if needed beyond UI update

    def _handle_pressure_data(self, data: list):
        # This method is connected to current_test_worker.pressure_data
        # MainWindow.update_pressure_graph also connects to this signal
        self.logger.debug(f"Pressure data received: {len(data)} points")
        # Potentially add TestHandler specific logic here

    def _handle_phase_change(self, phase_name: str):
        # This method is connected to current_test_worker.test_phase_changed
        # MainWindow.update_test_phase also connects to this signal
        self.logger.info(f"Test phase changed to: {phase_name}")
        # Potentially add TestHandler specific logic here