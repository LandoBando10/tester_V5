# gui/main_window.py - Refactored core window
import sys
import logging
from typing import Optional
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QStatusBar, QLabel, QPushButton, QDialog
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

# Import our modules
from src.data.sku_manager import create_sku_manager
from src.gui.components.config_loading_dialog import ConfigLoadingDialog, MinimalProgressDialog
from src.gui.components.menu_bar import TestMenuBar
from src.gui.components.top_controls import TopControlsWidget
from src.gui.components.test_area import TestAreaWidget
from src.gui.components.connection_dialog import ConnectionDialog
from src.gui.components.header_bar import HeaderBar, get_window_icon
from src.gui.workers.test_worker import TestWorker
from src.gui.handlers.offroad_handler import OffroadHandler
from src.gui.handlers.smt_handler import SMTHandler
from src.gui.handlers.weight_handler import WeightHandler
from src.gui.handlers.connection_handler import ConnectionHandler
from src.core.base_test import TestResult
from src.utils.resource_manager import ResourceManager # Added import


class MainWindow(QMainWindow):
    """Main application window - refactored for maintainability"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Diode Dynamics Tester V5")
        self.setMinimumSize(1200, 800)
        self.showMaximized()

        # Core managers
        self.sku_manager = create_sku_manager()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config_loading_dialog = None
        self.config_load_completed = False

        # Initialize handlers
        self.offroad_handler = OffroadHandler(self)
        self.smt_handler = SMTHandler(self)
        self.weight_handler = WeightHandler(self)
        self.connection_handler = ConnectionHandler(self)

        # UI Components
        self.connection_dialog = ConnectionDialog(self)
        self.test_worker: Optional[TestWorker] = None
        self.arduino_controller = None  # Persistent Arduino instance

        # Current state
        self.current_mode = None  # Will be set by launcher

        # Setup UI and connections first
        self.setup_logging()
        self.setup_window_icon()
        self.setup_ui()
        self.setup_connections()
        
        # Setup SKU manager connections after UI is ready
        self.setup_sku_manager()  # Setup SKU manager connections
        
        # Start async loading after everything is set up
        self.start_config_loading()  # Start async loading
        
        # If config is already loaded, refresh the UI
        if self.config_load_completed and self.sku_manager.is_loaded():
            self.refresh_data()

    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def setup_window_icon(self):
        """Setup window icon with company logo"""
        icon = get_window_icon()
        if icon:
            self.setWindowIcon(icon)
            # Also set for the application (taskbar)
            QApplication.instance().setWindowIcon(icon)

    def setup_ui(self):
        """Setup the main user interface"""
        # Central widget with dark theme
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet("background-color: #333333;")

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 10, 5, 5)  # Increased top margin for dropdown
        main_layout.setSpacing(5)  # Reduced spacing

        # Menu bar
        self.menu_bar = TestMenuBar(self)
        self.setMenuBar(self.menu_bar)

        # Top controls (SKU selection and test checkboxes only)
        self.top_controls = TopControlsWidget(self)
        main_layout.addWidget(self.top_controls)

        # Main test area (results display, weight testing widget, etc.)
        self.test_area = TestAreaWidget(self)
        main_layout.addWidget(self.test_area, 1)  # Takes most space

        # Bottom controls layout (connection status left, start button right)
        self.setup_bottom_controls(main_layout)

        # Status bar
        self.setup_status_bar()

    def setup_bottom_controls(self, main_layout):
        """Setup bottom controls with connection status (left) and start button (right)"""
        self.bottom_controls_layout = QHBoxLayout()
        self.bottom_controls_layout.setContentsMargins(10, 5, 10, 5)
        self.bottom_controls_layout.setSpacing(20)
        
        # Connection status (bottom left)
        self.connection_status_label = QLabel("Disconnected")
        self.connection_status_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.connection_status_label.setStyleSheet("color: #ff6b6b; margin: 0px;")
        self.bottom_controls_layout.addWidget(self.connection_status_label)
        
        # Stretch to push start button to the right
        self.bottom_controls_layout.addStretch()
        
        # Start button (bottom right)
        self.start_btn = QPushButton("START TEST")
        self.start_btn.clicked.connect(self.start_test)
        self.start_btn.setMinimumHeight(35)
        self.start_btn.setMinimumWidth(180)
        self.start_btn.setFont(QFont("Arial", 12, QFont.Bold))
        self.start_btn.setEnabled(False)  # Disabled until SKU selected
        self.apply_start_button_style()
        self.bottom_controls_layout.addWidget(self.start_btn)
        
        # Add bottom controls to main layout
        main_layout.addLayout(self.bottom_controls_layout)
    
    def apply_start_button_style(self):
        """Apply styling to start button"""
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90a4;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #5ba3b8;
            }
            QPushButton:pressed {
                background-color: #3a7a8a;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #999999;
            }
        """)

    def setup_status_bar(self):
        """Setup the status bar"""
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")
        self.statusBar().setStyleSheet("""
            QStatusBar {
                background-color: #2b2b2b;
                color: white;
                border-top: 1px solid #404040;
                font-size: 12px;
            }
        """)

    def setup_connections(self):
        """Setup signal connections between components"""
        # Menu bar connections
        self.menu_bar.mode_changed.connect(self.set_mode)
        self.menu_bar.show_connections_requested.connect(self.show_connection_dialog)

        # Top controls connections
        self.top_controls.sku_changed.connect(self.on_sku_changed)
        
        # Test area connections
        self.test_area.weight_test_started.connect(self.on_weight_test_started)
        self.test_area.weight_test_completed.connect(self.on_weight_test_completed)

        # Connection handler
        self.connection_handler.setup_connections()

    def set_mode(self, mode: str):
        """Set the current test mode"""
        previous_mode = self.current_mode
        self.current_mode = mode
        self.logger.info(f"Mode changed from {previous_mode} to {mode}")

        # Update UI components
        self.top_controls.set_mode(mode)
        self.test_area.set_mode(mode)
        
        # Show/hide start button based on mode
        if hasattr(self, 'start_btn'):
            if mode == "WeightChecking":
                self.start_btn.hide()
            else:
                self.start_btn.show()
        
        # If switching to SMT mode and a SKU is already selected, update panel layout
        if mode == "SMT":
            current_sku = self.top_controls.get_current_sku()
            if current_sku and current_sku != "-- Select SKU --":
                # Trigger SKU change handler to update panel layout
                self.on_sku_changed(current_sku)
        
        # Check if Arduino firmware matches new mode
        if hasattr(self, 'arduino_controller') and self.arduino_controller and self.arduino_controller.is_connected():
            firmware_type = getattr(self.arduino_controller, '_firmware_type', 'UNKNOWN')
            
            if mode in ["SMT", "Offroad"] and firmware_type != mode.upper() and firmware_type != "UNKNOWN":
                # Wrong firmware for new mode
                from PySide6.QtWidgets import QMessageBox
                
                # Clear sensor configuration flag
                if hasattr(self.arduino_controller, '_sensors_configured'):
                    delattr(self.arduino_controller, '_sensors_configured')
                
                # Update connection status to show disconnected
                self.connection_dialog.arduino_connected = False
                self.connection_dialog.arduino_status_label.setText("Status: Wrong firmware for mode")
                self.connection_dialog.arduino_status_label.setStyleSheet("color: orange; font-weight: bold;")
                
                QMessageBox.warning(self, "Arduino Firmware Mismatch",
                                   f"The connected Arduino has {firmware_type} firmware, "
                                   f"but you switched to {mode} mode.\n\n"
                                   f"Please disconnect and connect an Arduino with {mode} firmware.")
                
                # Update connection status
                self.update_connection_status()
        
        # Update connection status when switching to weight checking mode
        if mode == "WeightChecking":
            # Use QTimer to ensure this happens after the test area has been updated
            QTimer.singleShot(100, self.update_connection_status)

        # Filter SKUs and update tests
        self.filter_skus_by_mode()

    def setup_sku_manager(self):
        """Setup SKU manager - unified manager loads immediately"""
        # Unified manager doesn't need signal connections
        # Loading is immediate/lazy, so we can check if it's ready
        if self.sku_manager.is_loaded():
            self.config_load_completed = True
            # Directly refresh the UI since manager is loaded
            self.refresh_data()
            self.statusBar().showMessage(f"Ready - {len(self.sku_manager.get_all_skus())} SKUs loaded")
        else:
            self.logger.error("SKU manager failed to load")
            self.on_config_load_completed(False)
    
    def start_config_loading(self):
        """Start configuration loading - unified manager loads immediately"""
        # No need to call setup_sku_manager again since it's already called in __init__
        pass
    
    def show_progress_dialog_if_still_loading(self):
        """Legacy method - no longer needed with unified manager"""
        # Unified manager loads immediately, no progress dialog needed
        pass
    
    def fallback_to_sync_loading(self):
        """Fallback loading - unified manager handles this automatically"""
        try:
            self.logger.info("Attempting fallback configuration loading")
            
            # Unified manager loads immediately, so just check if loaded
            if self.sku_manager.is_loaded():
                self.refresh_data()
                self.config_load_completed = True
                self.logger.info("Fallback loading completed successfully")
            else:
                self.show_config_error("Failed to load configuration")
                
        except Exception as e:
            self.logger.error(f"Fallback loading failed: {e}")
            self.show_config_error(f"Configuration loading failed: {e}")
            self.show_config_error(f"Configuration loading failed: {e}")
    
    def refresh_data(self):
        """Refresh SKU data and update UI"""
        try:
            if not self.sku_manager.is_loaded():
                self.logger.warning("Attempting to refresh data before config is loaded")
                return
            
            # Load SKUs
            skus = self.sku_manager.get_all_skus()
            self.top_controls.set_available_skus(skus)

            # Filter SKUs by current mode
            self.filter_skus_by_mode()
            
            self.logger.info(f"UI refreshed with {len(skus)} SKUs")

        except Exception as e:
            self.logger.error(f"Error refreshing data: {e}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Could not refresh UI: {e}")

    def filter_skus_by_mode(self):
        """Filter SKUs based on selected test mode"""
        current_sku = self.top_controls.get_current_sku()

        # Get all SKUs that support the selected mode
        valid_skus = []
        try:
            all_skus = self.sku_manager.get_all_skus()
            for sku in all_skus:
                if self.sku_manager.validate_sku_mode_combination(sku, self.current_mode):
                    valid_skus.append(sku)
        except Exception as e:
            self.logger.error(f"Error filtering SKUs by mode: {e}")
            valid_skus = []

        # Update top controls
        self.top_controls.set_available_skus(valid_skus)

        # Try to restore previous selection if valid
        if current_sku in valid_skus:
            self.top_controls.set_current_sku(current_sku)

    def on_sku_changed(self, sku: str):
        """Handle SKU selection change"""
        if sku and sku != "-- Select SKU --":
            # Enable start button when SKU is selected (for non-weight modes)
            if self.current_mode != "WeightChecking":
                self.set_start_enabled(True)

            # Update test area based on current mode
            if self.current_mode == "WeightChecking":
                self.test_area.set_sku(sku)
            elif self.current_mode == "SMT":
                # Update SMT panel layout based on SKU configuration
                try:
                    params = self.sku_manager.get_test_parameters(sku, "SMT")
                    if params and "panel_layout" in params:
                        panel_layout = params["panel_layout"]
                        rows = panel_layout.get("rows", 0)
                        cols = panel_layout.get("columns", 0)
                        
                        # Update the SMT widget's panel layout
                        if hasattr(self.test_area, 'smt_widget') and self.test_area.smt_widget:
                            self.test_area.smt_widget.set_panel_layout(rows, cols)
                            self.logger.info(f"Updated SMT panel layout for {sku}: {rows}x{cols}")
                except Exception as e:
                    self.logger.error(f"Error updating SMT panel layout: {e}")

        else:
            if self.current_mode != "WeightChecking":
                self.set_start_enabled(False)

    def start_test(self):
        """Start the selected test"""
        sku = self.top_controls.get_current_sku()
        enabled_tests = self.top_controls.get_enabled_tests()
        connection_status = self.connection_dialog.get_connection_status()
        
        # Use the appropriate handler based on mode
        if self.current_mode == "Offroad":
            self.offroad_handler.start_test(sku, enabled_tests, connection_status)
        elif self.current_mode == "SMT":
            self.smt_handler.start_test(sku, enabled_tests, connection_status)
        elif self.current_mode == "WeightChecking":
            self.weight_handler.start_test(sku)

    def show_connection_dialog(self):
        """Show the connection management dialog"""
        self.connection_dialog.exec()
        self.update_connection_status()

    def update_connection_status(self):
        """Update the connection status display and propagate to test widgets"""
        # Get connection status from connection dialog
        connection_status = self.connection_dialog.get_connection_status()
        
        # Update main window display
        self.connection_handler.update_connection_status()
        
        # Propagate to weight test widget if in weight checking mode
        if self.current_mode == "WeightChecking":
            # Get scale connection info from connection dialog
            scale_connected = connection_status.get('scale_connected', False)
            scale_port = connection_status.get('scale_port')
            
            # Update weight test widget if it exists and is properly initialized
            if (hasattr(self.test_area, 'weight_test_widget') and 
                self.test_area.weight_test_widget is not None and
                hasattr(self.test_area.weight_test_widget, 'set_connection_status')):
                try:
                    self.test_area.weight_test_widget.set_connection_status(scale_connected, scale_port)
                    self.logger.info(f"Propagated scale connection status: connected={scale_connected}, port={scale_port}")
                except Exception as e:
                    self.logger.error(f"Error updating weight test widget connection status: {e}")
            else:
                self.logger.warning("Weight test widget not available or not properly initialized")
    
    def set_connection_status(self, connected: bool, details: str = ""):
        """Update connection status display"""
        if connected:
            self.connection_status_label.setText("Connected")
            self.connection_status_label.setStyleSheet("color: #51cf66; margin: 0px; font-weight: bold;")  # Green
        else:
            self.connection_status_label.setText("Disconnected")
            self.connection_status_label.setStyleSheet("color: #ff6b6b; margin: 0px; font-weight: bold;")  # Red
    
    def set_start_enabled(self, enabled: bool):
        """Enable/disable the start button"""
        if hasattr(self, 'start_btn'):
            self.start_btn.setEnabled(enabled)
    
    def set_testing_state(self, testing: bool):
        """Update UI for testing state"""
        if hasattr(self, 'start_btn'):
            if testing:
                self.start_btn.setEnabled(False)
                self.start_btn.setText("TESTING...")
            else:
                self.start_btn.setText("START TEST")
                # Re-enable button if a valid SKU is selected
                current_sku = self.top_controls.get_current_sku()
                if current_sku and current_sku != "-- Select SKU --" and self.current_mode != "WeightChecking":
                    self.start_btn.setEnabled(True)

    def start_testing_ui(self):
        """Update UI when test starts"""
        self.set_testing_state(True)
        self.test_area.set_testing_state(True)
        
        # Check if pressure test is enabled and setup live graph
        enabled_tests = self.top_controls.get_enabled_tests()
        if "PRESSURE" in enabled_tests and self.current_mode == "Offroad":
            self.test_area.start_pressure_test()

    def test_completed(self, result: TestResult):
        """Handle test completion"""
        try:
            # Re-enable UI
            self.set_testing_state(False)
            self.test_area.set_testing_state(False)

            # End any special test modes
            self.test_area.end_pressure_test()

            # Display results
            self.test_area.display_results(result)

            # Update status
            status = "PASS" if result.passed else "FAIL"
            self.statusBar().showMessage(f"Test completed: {status}")
            
            # Test completion is handled by the respective handler via signal
        
        except Exception as e:
            self.logger.error(f"Error handling test completion: {e}")

    def on_weight_test_started(self, sku: str):
        """Handle weight test started signal"""
        self.logger.info(f"Weight test started for SKU: {sku}")
        self.statusBar().showMessage(f"Weight testing {sku}...")

    def on_weight_test_completed(self, result):
        """Handle weight test completed signal"""
        if result and hasattr(result, 'passed'):
            status = "PASS" if result.passed else "FAIL"
            self.statusBar().showMessage(f"Weight test completed: {status}")
            self.logger.info(f"Weight test completed: {status}")
        else:
            self.statusBar().showMessage("Weight test completed")
    
    def update_progress_bar(self, message: str, value: int):
        """Update progress in status bar"""
        self.statusBar().showMessage(f"{message} ({value}%)")
        
    def update_test_phase(self, phase_name: str):
        """Update current test phase in status bar"""
        self.statusBar().showMessage(f"Test Phase: {phase_name}")
    
    def update_pressure_graph(self, pressure: float):
        """Update pressure graph with new data point"""
        if self.current_mode == "Offroad":
            self.test_area.add_pressure_data(pressure)
    
    def open_programming_config(self):
        """Open programming configuration dialog"""
        try:
            from src.gui.components.config.program_config import ProgrammingConfigurationDialog
            
            # Pass the actual SKU manager, not the main window
            dialog = ProgrammingConfigurationDialog(self.sku_manager, self)
            result = dialog.exec()  # Use exec() for modal dialog behavior
            if result == QDialog.Accepted:
                self.logger.info("Programming configuration changes accepted")
            self.logger.info("Programming configuration dialog closed")
                
        except ImportError as e:
            self.logger.error(f"Could not import programming config dialog: {e}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Import Error", 
                                 f"Programming configuration module not found: {e}")
        except Exception as e:
            self.logger.error(f"Error opening programming configuration: {e}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Could not open programming configuration: {e}")

    def closeEvent(self, event):
        """Handle application closing"""
        try:
            # Stop any running test
            if self.test_worker and self.test_worker.isRunning():
                self.test_worker.terminate()
                self.test_worker.wait(3000)

            # Cleanup handlers
            self.offroad_handler.cleanup()
            self.smt_handler.cleanup()
            self.weight_handler.cleanup()
            self.connection_handler.cleanup()

            # Cleanup test area
            self.test_area.cleanup()
            
            # Cleanup persistent Arduino connection
            if hasattr(self, 'arduino_controller') and self.arduino_controller:
                try:
                    if self.arduino_controller.is_connected():
                        self.arduino_controller.disconnect()
                    self.arduino_controller = None
                except Exception as e:
                    self.logger.error(f"Error disconnecting Arduino: {e}")
            
            # Cleanup SKU manager
            if hasattr(self, 'sku_manager'):
                self.sku_manager.cleanup()

            # Perform comprehensive resource cleanup
            try:
                resource_manager = ResourceManager()
                resource_manager.cleanup_all()
                self.logger.info("All resources cleaned up via ResourceManager.")
            except Exception as rm_error:
                self.logger.error(f"Error during ResourceManager cleanup: {rm_error}")

            event.accept()

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            event.accept()
    
    def on_config_load_progress(self, message: str, percentage: int):
        """Handle configuration loading progress"""
        if self.config_loading_dialog:
            self.config_loading_dialog.update_progress(message, percentage)
        
        self.statusBar().showMessage(f"Loading configuration: {message}")
    
    def on_config_load_completed(self, success: bool):
        """Handle configuration loading completion"""
        try:
            # Stop the progress timer if it's running
            if hasattr(self, 'progress_timer'):
                self.progress_timer.stop()
            
            # Close progress dialog if it exists
            if self.config_loading_dialog:
                if success:
                    status = self.sku_manager.get_load_status()
                    sku_count = status.get('sku_count', 0)
                    load_time = status.get('load_time_ms', 0)
                    
                    self.config_loading_dialog.show_success()
                    self.logger.info(f"Configuration loaded successfully: {sku_count} SKUs in {load_time}ms")
                else:
                    status = self.sku_manager.get_load_status()
                    error_msg = status.get('error', 'Unknown error')
                    self.config_loading_dialog.show_error(error_msg)
            
            # Mark as completed
            self.config_load_completed = True
            
            if success:
                # Only refresh UI if UI components are already initialized
                if hasattr(self, 'top_controls'):
                    # Refresh UI with loaded data
                    self.refresh_data()
                    
                    # Enable UI elements that depend on configuration
                    current_sku = self.top_controls.get_current_sku()
                    if current_sku and current_sku != "-- Select SKU --":
                        self.set_start_enabled(True)
                
                status = self.sku_manager.get_load_status()
                sku_count = status.get('sku_count', 0)
                if hasattr(self, 'statusBar'):
                    self.statusBar().showMessage(f"Ready - {sku_count} SKUs loaded")
            else:
                status = self.sku_manager.get_load_status()
                error_msg = status.get('error', 'Unknown error')
                self.show_config_error(error_msg)
        
        except Exception as e:
            self.logger.error(f"Error handling config load completion: {e}")
    
    def on_config_load_error(self, error_message: str):
        """Handle configuration loading error"""
        self.logger.error(f"Configuration loading error: {error_message}")
        self.show_config_error(error_message)
    
    def on_config_load_cancelled(self):
        """Handle configuration loading cancellation"""
        self.logger.info("Configuration loading cancelled by user")
        
        # Try to load synchronously as fallback
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Load Configuration",
            "Configuration loading was cancelled. Would you like to try loading synchronously?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            self.fallback_to_sync_loading()
        else:
            self.show_config_error("Configuration loading cancelled")
    
    def show_config_error(self, error_message: str):
        """Show configuration error and provide options"""
        from PySide6.QtWidgets import QMessageBox
        
        self.statusBar().showMessage("Configuration loading failed")
        
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Configuration Error")
        msg.setText("Failed to load SKU configuration")
        msg.setDetailedText(error_message)
        msg.setInformativeText("The application will continue with limited functionality.")
        
        retry_btn = msg.addButton("Retry", QMessageBox.ActionRole)
        continue_btn = msg.addButton("Continue", QMessageBox.AcceptRole)
        msg.setDefaultButton(retry_btn)
        
        msg.exec()
        
        if msg.clickedButton() == retry_btn:
            self.start_config_loading()
        else:
            # Continue with empty configuration
            self.config_load_completed = True
            self.top_controls.set_available_skus([])


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("Diode Dynamics Tester V5")
    app.setApplicationVersion("5.0")
    app.setOrganizationName("Diode Dynamics")

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()