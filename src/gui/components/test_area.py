# gui/components/test_area.py
import logging
from typing import Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QFont

from src.core.base_test import TestResult


class TestAreaWidget(QWidget):
    """Main test area that displays mode-specific testing interfaces"""
    
    # Signals
    weight_test_started = Signal(str)
    weight_test_completed = Signal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.current_mode = "Offroad"
        self.offroad_widget = None
        self.smt_widget = None
        self.weight_test_widget = None
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the main test area UI"""
        self.setStyleSheet("background-color: #2b2b2b; border-radius: 8px;")
        self.setMinimumHeight(400)
        
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Initialize with default mode
        self.set_mode("Offroad")
        
    def _create_weight_widget(self):
        """Create weight widget on demand"""
        if self.weight_test_widget is None:
            try:
                from src.gui.components.weight_test_widget import WeightTestWidget
                from src.gui.utils.style_manager import StyleManager
                self.weight_test_widget = WeightTestWidget()
                self.weight_test_widget.test_started.connect(self.weight_test_started.emit)
                self.weight_test_widget.test_completed.connect(self.weight_test_completed.emit)
                StyleManager.preload()  # Pre-load styles
                self.logger.debug("Created weight widget successfully")
            except Exception as e:
                self.logger.debug(f"Could not create weight widget: {e}")
        
    def set_mode(self, mode: str):
        """Update the test area based on current mode"""
        previous_mode = self.current_mode
        self.current_mode = mode
        self.logger.info(f"Setting test area mode to: {mode} (from {previous_mode})")
        
        # Pause weight widget if switching away from weight mode
        if previous_mode == "WeightChecking" and mode != "WeightChecking":
            if self.weight_test_widget and hasattr(self.weight_test_widget, 'pause_reading'):
                self.weight_test_widget.pause_reading()
        
        # Clear current content
        self.clear_content()
        
        if mode == "WeightChecking":
            self.setup_weight_testing_area()
            # Resume reading if weight widget already exists
            if self.weight_test_widget and hasattr(self.weight_test_widget, 'resume_reading'):
                self.weight_test_widget.resume_reading()
        elif mode == "SMT":
            self.setup_smt_testing_area()
        else:  # Offroad mode
            self.setup_offroad_testing_area()
            
    def clear_content(self):
        """Clear all content from the test area"""
        for i in reversed(range(self.main_layout.count())):
            child = self.main_layout.itemAt(i)
            if child and child.widget():
                # Don't delete the widgets, just remove them from layout
                child.widget().setParent(None)
                
    def setup_offroad_testing_area(self):
        """Setup offroad testing area with dedicated widget"""
        try:
            if not self.offroad_widget:
                from src.gui.components.offroad_widget import OffroadWidget
                self.offroad_widget = OffroadWidget()
                self.logger.debug("Created new OffroadWidget")
            
            self.main_layout.addWidget(self.offroad_widget)
            self.logger.info("Offroad testing area setup complete")
            
        except ImportError as e:
            self.logger.error(f"Failed to import OffroadWidget: {e}")
            self._show_error_placeholder("Offroad widget not available")
        
    def setup_smt_testing_area(self):
        """Setup SMT testing area with dedicated widget"""
        try:
            if not self.smt_widget:
                from src.gui.components.smt_widget import SMTWidget
                self.smt_widget = SMTWidget()
                self.logger.debug("Created new SMTWidget")
            
            self.main_layout.addWidget(self.smt_widget)
            self.logger.info("SMT testing area setup complete")
            
        except ImportError as e:
            self.logger.error(f"Failed to import SMTWidget: {e}")
            self._show_error_placeholder("SMT widget not available")
        
    def setup_weight_testing_area(self):
        """Setup weight testing widget"""
        try:
            if not self.weight_test_widget:
                from src.gui.components.weight_test_widget import WeightTestWidget
                self.weight_test_widget = WeightTestWidget()
                self.weight_test_widget.test_started.connect(self.weight_test_started.emit)
                self.weight_test_widget.test_completed.connect(self.weight_test_completed.emit)
                self.logger.debug("Created new WeightTestWidget")
            
            # Apply dark theme
            self.apply_weight_widget_style()
            
            self.main_layout.addWidget(self.weight_test_widget)
            self.logger.info("Weight testing area setup complete")
            
        except ImportError as e:
            self.logger.error(f"Weight test widget not available: {e}")
            self._show_error_placeholder("Weight Testing Mode\n(Weight widget not implemented)")
            
    def _show_error_placeholder(self, message: str):
        """Show error placeholder when widget is not available"""
        placeholder = QLabel(message)
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setFont(QFont("Arial", 16))
        placeholder.setStyleSheet("color: #888888;")
        self.main_layout.addWidget(placeholder)
            
    def apply_weight_widget_style(self):
        """Apply dark theme to weight testing widget"""
        if self.weight_test_widget:
            self.weight_test_widget.setStyleSheet("""
                QGroupBox {
                    color: white;
                    border: 2px solid #555555;
                    border-radius: 8px;
                    margin-top: 1ex;
                    font-weight: bold;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
                QLabel {
                    color: white;
                }
                QComboBox {
                    background-color: #555555;
                    color: white;
                    border: 1px solid #666666;
                    border-radius: 3px;
                    padding: 4px 8px;
                }
                QTextEdit {
                    background-color: #444444;
                    color: white;
                    border: 1px solid #666666;
                    border-radius: 3px;
                }
                QPushButton {
                    background-color: #555555;
                    color: white;
                    border: 1px solid #666666;
                    border-radius: 3px;
                    padding: 5px 10px;
                }
                QPushButton:hover {
                    background-color: #666666;
                }
            """)
            
    def display_results(self, result: TestResult):
        """Display test results based on current mode"""
        try:
            if self.current_mode == "WeightChecking":
                # Weight results are handled by the weight widget itself
                self.logger.debug("Weight results handled by widget")
                return
            elif self.current_mode == "SMT" and self.smt_widget:
                # Update SMT display
                self.smt_widget.display_results(result)
                self.logger.info("SMT results displayed")
            elif self.current_mode == "Offroad" and self.offroad_widget:
                # Update Offroad display
                self.offroad_widget.display_results(result)
                self.logger.info("Offroad results displayed")
                
        except Exception as e:
            self.logger.error(f"Error displaying results: {e}")
            
    def set_testing_state(self, testing: bool):
        """Update UI for testing state"""
        if self.current_mode == "Offroad" and self.offroad_widget:
            self.offroad_widget.set_testing_state(testing)
        elif self.current_mode == "SMT" and self.smt_widget:
            self.smt_widget.set_testing_state(testing)
        # Weight widget manages its own state
                    
    def start_pressure_test(self):
        """Start pressure test - delegates to offroad widget"""
        if self.current_mode == "Offroad" and self.offroad_widget:
            self.offroad_widget.start_pressure_test()
            
    def add_pressure_data(self, pressure: float):
        """Add pressure data point - delegates to offroad widget"""
        if self.current_mode == "Offroad" and self.offroad_widget:
            self.offroad_widget.add_pressure_data(pressure)
            
    def end_pressure_test(self):
        """End pressure test - delegates to offroad widget"""
        if self.current_mode == "Offroad" and self.offroad_widget:
            self.offroad_widget.end_pressure_test()
        
    def set_sku(self, sku: str):
        """Set SKU for weight testing widget"""
        if self.current_mode == "WeightChecking" and self.weight_test_widget:
            self.weight_test_widget.set_sku(sku)
    
    def set_programming_enabled(self, enabled: bool):
        """Enable/disable programming display for SMT mode"""
        if self.current_mode == "SMT" and self.smt_widget:
            self.smt_widget.set_programming_enabled(enabled)
    
    def start_programming_progress(self, total_boards: int):
        """Start programming progress display"""
        if self.current_mode == "SMT" and self.smt_widget:
            self.smt_widget.start_programming_progress(total_boards)
    
    def update_programming_progress(self, current_board: int, board_name: str, status: str):
        """Update programming progress"""
        if self.current_mode == "SMT" and self.smt_widget:
            self.smt_widget.update_programming_progress(current_board, board_name, status)
    
    def complete_programming_progress(self, success_count: int, total_count: int):
        """Complete programming progress display"""
        if self.current_mode == "SMT" and self.smt_widget:
            self.smt_widget.complete_programming_progress(success_count, total_count)
            
    def set_connection_status(self, connected: bool, port: str = None):
        """Set connection status for weight testing widget"""
        if self.current_mode == "WeightChecking" and self.weight_test_widget:
            self.weight_test_widget.set_connection_status(connected, port)
            
    def cleanup(self):
        """Cleanup the test area"""
        self.logger.info("Cleaning up test area widgets")
        
        # Cleanup each widget if it exists
        if self.weight_test_widget:
            try:
                self.weight_test_widget.cleanup()
            except Exception as e:
                self.logger.error(f"Error cleaning up weight widget: {e}")
                
        if self.offroad_widget:
            try:
                self.offroad_widget.cleanup()
            except Exception as e:
                self.logger.error(f"Error cleaning up offroad widget: {e}")
                
        if self.smt_widget:
            try:
                self.smt_widget.cleanup()
            except Exception as e:
                self.logger.error(f"Error cleaning up SMT widget: {e}")