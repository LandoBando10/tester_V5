# gui/handlers/weight_handler.py
import logging
from typing import Dict, Any
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QObject

from src.core.base_test import TestResult
from src.utils.thread_cleanup import ThreadCleanupMixin


class WeightHandler(QObject, ThreadCleanupMixin):
    """Handles Weight test execution logic"""
    
    def __init__(self, main_window):
        QObject.__init__(self)
        ThreadCleanupMixin.__init__(self)
        self.main_window = main_window
        self.logger = logging.getLogger(self.__class__.__name__)
        self.current_test_worker = None
        self.logger.debug("WeightHandler initialized")
    
    def start_test(self, sku: str):
        """Start the Weight test"""
        self.logger.info(f"Starting Weight test for SKU: {sku}")
        
        try:
            # Validation
            if not sku or sku == "-- Select SKU --":
                self.logger.warning("SKU not selected.")
                QMessageBox.warning(self.main_window, "Warning", "Please select a SKU")
                return
            
            # Validate scale connection
            if not self._validate_scale_connection():
                return
            
            # Validate SKU supports Weight mode
            if not self.main_window.sku_manager.validate_sku_mode_combination(sku, "WeightChecking"):
                self.logger.warning(f"SKU {sku} does not support Weight Checking mode.")
                QMessageBox.warning(self.main_window, "Warning", f"SKU {sku} does not support Weight Checking mode")
                return
            
            # Get test parameters
            params = self.main_window.sku_manager.get_test_parameters(sku, "WeightChecking")
            if not params:
                self.logger.error(f"No parameters found for {sku} in Weight Checking mode.")
                QMessageBox.critical(self.main_window, "Error", f"No parameters found for {sku} in Weight Checking mode")
                return
            
            # Create test instance
            test_instance = self._create_test_instance(sku, params)
            if not test_instance:
                return
            
            # Update UI
            self.main_window.start_testing_ui()
            
            # Create and start worker thread
            from src.gui.workers.weight_worker import WeightWorker
            self.current_test_worker = WeightWorker(test_instance)
            
            # Register for resource tracking
            worker_name = f"weight_worker_{sku}"
            self.register_qthread(self.current_test_worker, worker_name)
            self.logger.info(f"QThread '{worker_name}' registered for resource tracking.")
            
            # Connect signals
            self.current_test_worker.test_completed.connect(self._handle_test_completion)
            self.current_test_worker.progress_updated.connect(self._handle_progress_update)
            self.current_test_worker.test_phase_changed.connect(self._handle_phase_change)
            
            # Start worker
            self.current_test_worker.start()
            self.logger.info(f"Weight test worker started for SKU: {sku}")
            
        except Exception as e:
            self.logger.error(f"Error starting Weight test: {e}", exc_info=True)
            QMessageBox.critical(self.main_window, "Error", f"Could not start test: {e}")
    
    def _validate_scale_connection(self) -> bool:
        """Validate scale connection"""
        self.logger.debug("Validating scale connection.")
        
        # Check if weight widget exists
        if not hasattr(self.main_window.test_area, 'weight_test_widget'):
            self.logger.warning("Weight testing widget not available.")
            QMessageBox.warning(self.main_window, "Warning", "Weight testing widget not available")
            return False
        
        # Get connection status from weight widget
        weight_widget = self.main_window.test_area.weight_test_widget
        if hasattr(weight_widget, 'get_connection_status'):
            status = weight_widget.get_connection_status()
            if not status.get('connected', False):
                self.logger.warning("Scale not connected.")
                QMessageBox.warning(self.main_window, "Warning",
                                    "Please connect to scale first")
                return False
        
        self.logger.debug("Scale connection validated.")
        return True
    
    def _create_test_instance(self, sku: str, params: Dict[str, Any]):
        """Create Weight test instance"""
        self.logger.info(f"Creating Weight test instance for SKU: {sku}")
        try:
            from src.core.weight_test import WeightTest
            
            # Get port from weight widget
            weight_widget = self.main_window.test_area.weight_test_widget
            if weight_widget and hasattr(weight_widget, 'get_connection_status'):
                weight_status = weight_widget.get_connection_status()
                port = weight_status.get('port')
                if port:
                    # Create weights JSON path
                    weights_json_path = "weights.json"  # Could be configurable
                    self.logger.info(f"WeightTest instance created with port: {port}")
                    return WeightTest(sku, params, port, weights_json_path)
                else:
                    self.logger.warning("No scale connection found.")
                    QMessageBox.warning(self.main_window, "Warning", 
                                        "No scale connection found. Please connect scale first.")
                    return None
            else:
                self.logger.warning("Weight testing widget not properly initialized.")
                QMessageBox.warning(self.main_window, "Warning", 
                                    "Weight testing widget not properly initialized.")
                return None
                
        except ImportError as e:
            self.logger.error(f"Import error creating test instance: {e}", exc_info=True)
            QMessageBox.critical(self.main_window, "Import Error", 
                                 f"Could not import weight test module: {e}")
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
        self.logger.info("Starting Weight handler cleanup...")
        try:
            if self.current_test_worker and self.current_test_worker.isRunning():
                self.logger.info("Cleaning up: stopping running test worker...")
                self.current_test_worker.quit()
                if not self.current_test_worker.wait(1000):
                    self.current_test_worker.terminate()
                    self.current_test_worker.wait(500)
            
            self.current_test_worker = None
            self.logger.info("Weight handler cleanup completed.")
                
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}", exc_info=True)
    
    def _handle_test_completion(self, result: TestResult):
        """Handle test completion"""
        self.logger.info(f"Weight test completed. Result: {'PASS' if result.passed else 'FAIL'}")
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
    
    def _handle_phase_change(self, phase_name: str):
        """Handle test phase change"""
        self.logger.info(f"Test phase changed to: {phase_name}")
        self.main_window.update_test_phase(phase_name)