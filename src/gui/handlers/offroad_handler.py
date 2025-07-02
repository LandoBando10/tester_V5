# gui/handlers/offroad_handler.py
import logging
from typing import Dict, List, Any
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QObject

from src.core.base_test import TestResult
from src.utils.thread_cleanup import ThreadCleanupMixin


class OffroadHandler(QObject, ThreadCleanupMixin):
    """Handles Offroad test execution logic"""
    
    def __init__(self, main_window):
        QObject.__init__(self)
        ThreadCleanupMixin.__init__(self)
        self.main_window = main_window
        self.logger = logging.getLogger(self.__class__.__name__)
        self.current_test_worker = None
        self.logger.debug("OffroadHandler initialized")
    
    def start_test(self, sku: str, enabled_tests: List[str], connection_status: Dict[str, Any]):
        """Start the Offroad test"""
        self.logger.info(f"Starting Offroad test for SKU: {sku}, Enabled Tests: {enabled_tests}")
        
        try:
            # Validation
            if not sku or sku == "-- Select SKU --":
                self.logger.warning("SKU not selected.")
                QMessageBox.warning(self.main_window, "Warning", "Please select a SKU")
                return
            
            # Validate Arduino connection
            if not self._validate_arduino_connection(connection_status):
                return
            
            # Validate SKU supports Offroad mode
            if not self.main_window.sku_manager.validate_sku_mode_combination(sku, "Offroad"):
                self.logger.warning(f"SKU {sku} does not support Offroad mode.")
                QMessageBox.warning(self.main_window, "Warning", f"SKU {sku} does not support Offroad mode")
                return
            
            # Get test parameters
            params = self.main_window.sku_manager.get_test_parameters(sku, "Offroad")
            if not params:
                self.logger.error(f"No parameters found for {sku} in Offroad mode.")
                QMessageBox.critical(self.main_window, "Error", f"No parameters found for {sku} in Offroad mode")
                return
            
            # Check which tests are enabled
            if not enabled_tests:
                self.logger.warning("No tests selected to run.")
                QMessageBox.warning(self.main_window, "Warning", "Please select at least one test to run")
                return
            
            # Create test instance
            test_instance = self._create_test_instance(sku, params, enabled_tests, connection_status)
            if not test_instance:
                return
            
            # Update UI
            self.main_window.start_testing_ui()
            
            # Create and start worker thread
            from src.gui.workers.offroad_worker import OffroadWorker
            self.current_test_worker = OffroadWorker(test_instance)
            
            # Register for resource tracking
            worker_name = f"offroad_worker_{sku}"
            self.register_qthread(self.current_test_worker, worker_name)
            self.logger.info(f"QThread '{worker_name}' registered for resource tracking.")
            
            # Connect signals
            self.current_test_worker.test_completed.connect(self._handle_test_completion)
            self.current_test_worker.progress_updated.connect(self._handle_progress_update)
            self.current_test_worker.pressure_data.connect(self._handle_pressure_data)
            self.current_test_worker.test_phase_changed.connect(self._handle_phase_change)
            
            # Start worker
            self.current_test_worker.start()
            self.logger.info(f"Offroad test worker started for SKU: {sku}")
            
        except Exception as e:
            self.logger.error(f"Error starting Offroad test: {e}", exc_info=True)
            QMessageBox.critical(self.main_window, "Error", f"Could not start test: {e}")
    
    def _validate_arduino_connection(self, connection_status: Dict[str, Any]) -> bool:
        """Validate Arduino connection and firmware"""
        self.logger.debug("Validating Arduino connection.")
        if not connection_status.get('arduino_connected', False):
            self.logger.warning("Arduino not connected.")
            QMessageBox.warning(self.main_window, "Warning",
                                "Please connect to Arduino first (Connection → Hardware Connections)")
            return False
        
        # Validate firmware type
        if hasattr(self.main_window, 'arduino_controller') and self.main_window.arduino_controller:
            firmware_type = getattr(self.main_window.arduino_controller, '_firmware_type', 'UNKNOWN')
            if firmware_type != "OFFROAD" and firmware_type != "UNKNOWN":
                self.logger.warning(f"Wrong Arduino firmware: {firmware_type}")
                QMessageBox.critical(self.main_window, "Wrong Arduino Firmware",
                                   f"The connected Arduino has {firmware_type} firmware.\n\n"
                                   f"Please disconnect and connect an Arduino with Offroad firmware.")
                return False
        
        self.logger.debug("Arduino connection validated.")
        return True
    
    def _create_test_instance(self, sku: str, params: Dict[str, Any], 
                             enabled_tests: List[str], connection_status: Dict[str, Any]):
        """Create Offroad test instance"""
        self.logger.info(f"Creating Offroad test instance for SKU: {sku}")
        try:
            from src.core import offroad_test
            port = connection_status['arduino_port']
            test_config = "offroad_standard"  # Could be made configurable
            pressure_test_enabled = "PRESSURE" in enabled_tests
            
            # Get Arduino controller from main window
            arduino_controller = None
            if hasattr(self.main_window, 'arduino_controller'):
                arduino_controller = self.main_window.arduino_controller
                self.logger.info("Using persistent Arduino controller")
            
            self.logger.info(f"OffroadTest instance created with port: {port}, config: {test_config}, pressure_enabled: {pressure_test_enabled}")
            return offroad_test.OffroadTest(sku, params, port, test_config, pressure_test_enabled, arduino_controller=arduino_controller)
            
        except ImportError as e:
            self.logger.error(f"Import error creating test instance: {e}", exc_info=True)
            QMessageBox.critical(self.main_window, "Import Error", 
                                 f"Could not import offroad test module: {e}")
            return None
        except KeyError as e:
            self.logger.error(f"Missing key in connection_status: {e}", exc_info=True)
            QMessageBox.critical(self.main_window, "Configuration Error", 
                                f"Missing connection data: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error creating test instance: {e}", exc_info=True)
            QMessageBox.critical(self.main_window, "Error", 
                                f"Could not create test instance: {e}")
            return None
    
    def stop_current_test(self):
        """Stop the currently running test"""
        self.logger.info("Attempting to stop current test.")
        try:
            if self.current_test_worker and self.current_test_worker.isRunning():
                self.logger.info("Stopping current test worker...")
                self.current_test_worker.terminate()
                if not self.current_test_worker.wait(5000):
                    self.logger.warning("Test worker did not stop gracefully.")
                else:
                    self.logger.info("Test worker stopped.")
                self.current_test_worker = None
            else:
                self.logger.info("No running test worker to stop.")
                
        except Exception as e:
            self.logger.error(f"Error stopping test: {e}", exc_info=True)
    
    def is_test_running(self) -> bool:
        """Check if a test is currently running"""
        return (self.current_test_worker is not None and 
                self.current_test_worker.isRunning())
    
    def cleanup(self):
        """Cleanup test handler"""
        self.logger.info("Starting Offroad handler cleanup...")
        try:
            if self.current_test_worker and self.current_test_worker.isRunning():
                self.logger.info("Cleaning up: stopping running test worker...")
                self.current_test_worker.quit()
                if not self.current_test_worker.wait(1000):
                    self.current_test_worker.terminate()
                    self.current_test_worker.wait(500)
            
            self.current_test_worker = None
            self.logger.info("Offroad handler cleanup completed.")
                
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}", exc_info=True)
    
    def _handle_test_completion(self, result: TestResult):
        """Handle test completion"""
        self.logger.info(f"Offroad test completed. Result: {'PASS' if result.passed else 'FAIL'}")
        try:
            # Clean up worker
            if self.current_test_worker:
                self.current_test_worker = None
                
            # Update UI
            self.main_window.test_completed(result)
            
            # Log summary
            if result.failures:
                self.logger.warning(f"Test failures: {result.failures}")
                
        except Exception as e:
            self.logger.error(f"Error handling test completion: {e}", exc_info=True)
    
    def _handle_progress_update(self, message: str, value: int):
        """Handle progress update"""
        self.logger.debug(f"Progress update: {value}% - {message}")
        self.main_window.update_progress_bar(message, value)
    
    def _handle_pressure_data(self, pressure: float):
        """Handle live pressure data"""
        self.logger.debug(f"Pressure data: {pressure} PSI")
        # Forward to test area widget
        if hasattr(self.main_window.test_area, 'offroad_widget'):
            self.main_window.test_area.offroad_widget.add_pressure_data(pressure)
    
    def _handle_phase_change(self, phase_name: str):
        """Handle test phase change"""
        self.logger.info(f"Test phase changed to: {phase_name}")
        self.main_window.update_test_phase(phase_name)
        
        # Handle pressure test phase
        if phase_name == "Pressure Test" and hasattr(self.main_window.test_area, 'offroad_widget'):
            self.main_window.test_area.offroad_widget.start_pressure_test()
        elif "Pressure" in phase_name and "Complete" in phase_name and hasattr(self.main_window.test_area, 'offroad_widget'):
            self.main_window.test_area.offroad_widget.end_pressure_test()