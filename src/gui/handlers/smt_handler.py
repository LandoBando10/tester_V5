# gui/handlers/smt_handler.py
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QObject, Signal, Qt

from src.core.base_test import TestResult
from src.utils.thread_cleanup import ThreadCleanupMixin
import time


class SMTHandler(QObject, ThreadCleanupMixin):
    """Handles SMT test execution logic"""
    
    # Signal to request user confirmation from main thread
    request_user_confirmation = Signal(str, str, object)  # title, message, callback
    
    # Signal for button press handling on main thread
    button_pressed_signal = Signal()
    
    def __init__(self, main_window):
        QObject.__init__(self)
        ThreadCleanupMixin.__init__(self)
        self.main_window = main_window
        self.logger = logging.getLogger(self.__class__.__name__)
        self.current_test_worker = None
        self._button_press_handled = False
        self._physical_button_state = "RELEASED"  # Track physical button state
        self._initial_state_received = False  # Track if we've received initial state
        
        # SPC integration reference (will be set from test instance)
        self.spc_integration = None
        
        # Connect button signal to handler - ensures it runs on main thread
        self.button_pressed_signal.connect(self._handle_button_press_on_main_thread, Qt.QueuedConnection)
        
        # PHASE 1: Test timing control
        self._last_test_end_time = 0
        self.min_test_interval = 3.0  # 3 seconds between tests for safety
        self.consecutive_test_count = 0
        self.max_consecutive_tests = 10
        
        self.logger.debug("SMTHandler initialized")
    
    def start_test(self, sku: str, enabled_tests: List[str], connection_status: Dict[str, Any], source: str = "GUI"):
        """Start the SMT test with PHASE 1 recovery logic"""
        self.logger.info(f"Starting SMT test for SKU: {sku}, Enabled Tests: {enabled_tests}, Source: {source}")
        
        try:
            # PHASE 1: Check minimum time between tests
            time_since_last_test = time.time() - self._last_test_end_time
            if time_since_last_test < 0.3:  # Minimum 0.3 seconds between tests
                wait_time = 0.3 - time_since_last_test
                self.logger.info(f"Waiting {wait_time:.1f}s for cooldown between tests")
                time.sleep(wait_time)
            
            
            
            # Clear buffers and prepare for test
            if hasattr(self.main_window, 'arduino_controller') and self.main_window.arduino_controller:
                arduino = self.main_window.arduino_controller
                
                # Clear buffers before test
                self.logger.info("Clearing serial buffers before test")
                
                # Note: Reading thread remains active during tests in SMT architecture
                
                if hasattr(arduino, '_flush_buffers'):
                    arduino._flush_buffers()
                else:
                    self.logger.warning("Arduino controller does not have _flush_buffers method")
            # Validation
            if not sku or sku == "-- Select SKU --":
                self.logger.warning("SKU not selected.")
                self._button_press_handled = False  # Reset flag on error
                QMessageBox.warning(self.main_window, "Warning", "Please select a SKU")
                return
            
            # Validate Arduino connection
            if not self._validate_arduino_connection(connection_status):
                self._button_press_handled = False  # Reset flag on error
                return
            
            # Validate SKU supports SMT mode
            if not self.main_window.sku_manager.validate_sku_mode_combination(sku, "SMT"):
                self.logger.warning(f"SKU {sku} does not support SMT mode.")
                self._button_press_handled = False  # Reset flag on error
                QMessageBox.warning(self.main_window, "Warning", f"SKU {sku} does not support SMT mode")
                return
            
            # Get test parameters
            params = self.main_window.sku_manager.get_test_parameters(sku, "SMT")
            if not params:
                self.logger.error(f"No parameters found for {sku} in SMT mode.")
                self._button_press_handled = False  # Reset flag on error
                QMessageBox.critical(self.main_window, "Error", f"No parameters found for {sku} in SMT mode")
                return
            
            # Update programming status in SMT widget
            programming_enabled = "PROGRAMMING" in enabled_tests
            if hasattr(self.main_window.test_area, 'smt_widget'):
                self.main_window.test_area.smt_widget.set_programming_enabled(programming_enabled)
            self.logger.info(f"Programming for SMT mode set to: {programming_enabled}")
            
            # Create test instance
            test_instance = self._create_test_instance(sku, params, enabled_tests, connection_status)
            if not test_instance:
                self._button_press_handled = False  # Reset flag on error
                return
            
            # Update UI
            self.main_window.start_testing_ui()
            
            # Create and start worker thread
            from src.gui.workers.smt_worker import SMTWorker
            self.current_test_worker = SMTWorker(test_instance)
            
            # Register for resource tracking
            worker_name = f"smt_worker_{sku}"
            self.register_qthread(self.current_test_worker, worker_name)
            self.logger.info(f"QThread '{worker_name}' registered for resource tracking.")
            
            # Connect signals
            self.current_test_worker.test_completed.connect(self._handle_test_completion)
            self.current_test_worker.progress_updated.connect(self._handle_progress_update)
            self.current_test_worker.test_phase_changed.connect(self._handle_phase_change)
            self.current_test_worker.programming_progress.connect(self._handle_programming_progress)
            
            # Start worker
            self.current_test_worker.start()
            self.logger.info(f"SMT test worker started for SKU: {sku}")
            
        except Exception as e:
            self.logger.error(f"Error starting SMT test: {e}", exc_info=True)
            self._button_press_handled = False  # Reset flag on error
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
            if firmware_type != "SMT" and firmware_type != "UNKNOWN":
                self.logger.warning(f"Wrong Arduino firmware: {firmware_type}")
                QMessageBox.critical(self.main_window, "Wrong Arduino Firmware",
                                   f"The connected Arduino has {firmware_type} firmware.\n\n"
                                   f"Please disconnect and connect an Arduino with SMT firmware.")
                return False
        
        self.logger.debug("Arduino connection validated.")
        return True
    
    def _create_test_instance(self, sku: str, params: Dict[str, Any], 
                             enabled_tests: List[str], connection_status: Dict[str, Any]):
        """Create SMT test instance"""
        self.logger.info(f"Creating SMT test instance for SKU: {sku}")
        try:
            from src.core.smt_test import SMTTest
            port = connection_status['arduino_port']
            
            # Get Arduino controller from main window
            arduino_controller = None
            if hasattr(self.main_window, 'arduino_controller'):
                arduino_controller = self.main_window.arduino_controller
                self.logger.info("Using persistent Arduino controller")
            
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
            
            # SPC configuration - check if sampling mode is enabled in main window
            spc_enabled = getattr(self.main_window, 'spc_sampling_enabled', True)  # Default True
            spc_config = {
                'enabled': spc_enabled  # Controlled by menu toggle
            }
            
            if not spc_enabled:
                self.logger.info("SPC data collection is disabled by user setting")
            
            # Pass Arduino controller and SPC config to SMT test
            self.logger.info(f"SMTTest instance created with port: {port}, programming_config: {'present' if programming_config else 'absent'}, SPC: {spc_config.get('enabled')}")
            test_instance = SMTTest(sku, params, port, programming_config, arduino_controller=arduino_controller, spc_config=spc_config)
            
            # Store last test instance for spec calculator
            self.last_test_instance = test_instance
            
            # Store SPC integration reference if available
            if hasattr(test_instance, 'spc') and test_instance.spc:
                self.spc_integration = test_instance.spc
                self.logger.info("SPC integration reference stored")
            
            # Set callback for spec calculation
            test_instance.spec_calculation_callback = lambda sku: self._on_spec_calculation_ready(sku, test_instance)
            
            return test_instance
            
        except ImportError as e:
            self.logger.error(f"Import error creating test instance: {e}", exc_info=True)
            QMessageBox.critical(self.main_window, "Import Error", 
                                 f"Could not import SMT test module: {e}")
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
    
    def _get_programming_config(self, sku: str) -> Optional[Dict]:
        """Get programming configuration for SMT testing"""
        self.logger.debug(f"Getting programming config for SKU: {sku}")
        try:
            # Look for programming configuration file
            config_path = Path("config") / "programming_config.json"
            
            if not config_path.exists():
                self.logger.warning(f"Programming config file not found: {config_path}")
                return None
            
            with open(config_path, 'r') as f:
                programming_configs = json.load(f)
            self.logger.debug(f"Loaded programming_config.json from {config_path}")
            
            # Get configuration for this SKU
            sku_config = programming_configs.get(sku)
            if not sku_config:
                self.logger.info(f"No specific programming config for SKU {sku}, trying default.")
                sku_config = programming_configs.get("default")
            
            if sku_config:
                # Validate that programming is enabled for this SKU
                if not sku_config.get("enabled", False):
                    self.logger.warning(f"Programming disabled for SKU: {sku} in its config.")
                    return None
                
                self.logger.info(f"Loaded programming config for SKU: {sku}")
                return sku_config
            else:
                self.logger.warning(f"No programming config found for SKU: {sku}")
                return None
                
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in programming config: {e}", exc_info=True)
            QMessageBox.critical(self.main_window, "Configuration Error", 
                                 f"Invalid programming configuration file: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error loading programming config: {e}", exc_info=True)
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
        self.logger.info("Starting SMT handler cleanup...")
        try:
            if self.current_test_worker and self.current_test_worker.isRunning():
                self.logger.info("Cleaning up: stopping running test worker...")
                self.current_test_worker.quit()
                if not self.current_test_worker.wait(1000):
                    self.current_test_worker.terminate()
                    self.current_test_worker.wait(500)
            
            self.current_test_worker = None
            self._button_press_handled = False
            self.spc_integration = None
            self.logger.info("SMT handler cleanup completed.")
                
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}", exc_info=True)
    
    
    def _handle_test_completion(self, result: TestResult):
        """Handle test completion with PHASE 1 timing updates"""
        self.logger.info(f"SMT test completed. Result: {'PASS' if result.passed else 'FAIL'}")
        try:
            # PHASE 1: Record test end time for cooldown tracking
            self._last_test_end_time = time.time()
            
            # Increment spec calculator counter if enabled
            if hasattr(self.main_window, 'spec_calculator_enabled') and self.main_window.spec_calculator_enabled:
                self.main_window.increment_spec_calculator_count()
            
            # PHASE 1: Always turn off relays after test (using individual commands)
            if hasattr(self.main_window, 'arduino_controller') and self.main_window.arduino_controller:
                arduino = self.main_window.arduino_controller
                # Check if this is SMTArduinoController which uses all_relays_off
                if hasattr(arduino, 'all_relays_off'):
                    arduino.all_relays_off()
                
                # Note: Reading thread was never paused, no need to resume
                else:
                    # Standard ArduinoController - send individual commands
                    for relay in range(1, 9):  # Turn off relays 1-8
                        arduino.send_command(f"RELAY:{relay}:OFF")
            
            
            # Clean up worker
            if self.current_test_worker:
                self.current_test_worker = None
                
            # Update UI
            self.main_window.test_completed(result)
            
            # Update SPC widget with ALL test data (including failed tests)
            # This is important for spec recalculation when current specs are wrong
            if hasattr(self.main_window, 'spc_widget') and self.main_window.spc_widget:
                try:
                    # Check if SPC data was collected in the test
                    if 'spc' in result.metadata and result.metadata['spc'].get('data_collected'):
                        # Get the SKU from the result
                        sku = result.metadata.get('sku') or getattr(result, 'sku', None)
                        if sku:
                            self.main_window.spc_widget.add_test_results(sku, result.to_dict())
                            self.logger.info(f"Updated SPC widget with test results for {sku} (Pass: {result.passed})")
                except Exception as e:
                    self.logger.error(f"Error updating SPC widget: {e}", exc_info=True)
            
            
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
    
    def _handle_programming_progress(self, current: int, total: int, board_name: str, status: str):
        """Handle programming progress updates"""
        self.logger.debug(f"Programming progress: {current}/{total} - {board_name}: {status}")
        
        # Update SMT widget
        if hasattr(self.main_window.test_area, 'smt_widget'):
            if current == 0 and total > 0:
                # Starting programming
                self.main_window.test_area.smt_widget.start_programming_progress(total)
            elif current > 0:
                # Update progress
                self.main_window.test_area.smt_widget.update_programming_progress(current, board_name, status)
    
    def handle_button_event(self, button_state: str):
        """Handle physical button press from Arduino"""
        # Store previous state to detect transitions
        previous_state = self._physical_button_state
        self._physical_button_state = button_state
        
        # Handle initial state
        if not self._initial_state_received:
            self._initial_state_received = True
            self.logger.info(f"Initial button state recorded: {button_state}")
            # Don't trigger on initial state unless explicitly called from connection dialog
            # The connection dialog will call this with PRESSED if button is held at startup
        
        # Always check for transitions, even on first state
        if button_state == "PRESSED" and (previous_state == "RELEASED" or previous_state is None):
            # Button was just pressed (transition from released to pressed)
            if not self.is_test_running():
                self.logger.info("Physical button pressed - triggering test start")
                
                # Emit signal to handle the button press on the main thread
                # Use Qt.QueuedConnection to ensure it runs on main thread
                self.button_pressed_signal.emit()
            else:
                self.logger.info("Test already running, ignoring button press")
        elif button_state == "RELEASED":
            # Button released - ready for next press
            self.logger.debug("Physical button released")
    
    def _handle_button_press_on_main_thread(self):
        """Handle button press on main thread - safe for GUI operations"""
        try:
            # Get current SKU and check if valid
            sku = self.main_window.top_controls.get_current_sku()
            if not sku or sku == "-- Select SKU --":
                self.logger.warning("No SKU selected, ignoring button press")
                self._button_press_handled = False
                return
            
            
            # Get enabled tests and connection status
            enabled_tests = self.main_window.top_controls.get_enabled_tests()
            connection_status = self.main_window.connection_service.get_connection_status()
            
            # Start the test - now safe to show dialogs
            self.start_test(sku, enabled_tests, connection_status, source="PHYSICAL_BUTTON")
        except Exception as e:
            self.logger.error(f"Error handling button press: {e}", exc_info=True)
            self._button_press_handled = False
    
    def _on_spec_calculation_ready(self, sku: str, test_instance):
        """Handle when SPC has collected enough measurements for spec calculation"""
        try:
            self.logger.info(f"Spec calculation ready notification for {sku}")
            
            # Show message to user
            reply = QMessageBox.question(
                self.main_window,
                "Spec Calculation Ready",
                f"30 measurements collected for {sku}.\n\n"
                f"Would you like to calculate and review new specification limits?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Show the approval dialog
                if test_instance.spc:
                    test_instance.spc.show_spec_approval_dialog(sku, self.main_window)
                    
        except Exception as e:
            self.logger.error(f"Error handling spec calculation ready: {e}", exc_info=True)