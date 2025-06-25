# gui/components/voltage_monitor.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Signal, QTimer, Qt
from PySide6.QtGui import QFont
import logging


class VoltageMonitorWidget(QWidget):
    """Widget to display live voltage and control test availability"""
    
    # Signal emitted when voltage validity changes
    voltage_valid_changed = Signal(bool)  # True if voltage is in valid range
    
    # Target voltage and tolerance
    TARGET_VOLTAGE = 13.20
    TOLERANCE = 0.02  # ±0.02V
    MIN_VOLTAGE = TARGET_VOLTAGE - TOLERANCE  # 13.18V
    MAX_VOLTAGE = TARGET_VOLTAGE + TOLERANCE  # 13.22V
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.current_voltage = 0.0
        self.is_valid = False
        self.arduino_controller = None
        self.is_paused = False  # Flag to prevent voltage checks during tests
        
        self.setup_ui()
        self.setup_timer()
        
    def setup_ui(self):
        """Setup the widget UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(5)
        
        # Label for "Voltage:"
        self.label = QLabel("Voltage:")
        self.label.setFont(QFont("Arial", 10, QFont.Bold))
        self.label.setStyleSheet("color: white;")
        layout.addWidget(self.label)
        
        # Voltage value display
        self.voltage_display = QLabel("---.--V")
        self.voltage_display.setFont(QFont("Consolas", 12, QFont.Bold))
        self.voltage_display.setMinimumWidth(80)
        self.voltage_display.setAlignment(Qt.AlignCenter)
        self.update_display_style(False)
        layout.addWidget(self.voltage_display)
        
        # Status indicator
        self.status_label = QLabel("✗")
        self.status_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.status_label.setStyleSheet("color: #ff6b6b;")
        layout.addWidget(self.status_label)
        
    def setup_timer(self):
        """Setup timer for voltage updates"""
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.check_voltage)
        # Don't start timer here - will be started when Arduino is connected
        
    def set_arduino_controller(self, controller):
        """Set the Arduino controller for voltage readings"""
        self.arduino_controller = controller
        if controller and controller.is_connected():
            # Do an immediate voltage check
            self.check_voltage()
            # Then start monitoring at 2Hz (500ms) to reduce serial congestion
            self.update_timer.start(500)
            self.logger.info("Started voltage monitoring")
        else:
            self.update_timer.stop()
            self.voltage_display.setText("---.--V")
            self.logger.info("Stopped voltage monitoring - no controller")
            
    def check_voltage(self):
        """Check current voltage from Arduino"""
        if self.is_paused:
            return  # Skip voltage check if paused
            
        if not self.arduino_controller or not self.arduino_controller.is_connected():
            self.update_timer.stop()
            return
            
        try:
            # For SMT Arduino, use the get_supply_voltage method
            if hasattr(self.arduino_controller, 'get_supply_voltage'):
                voltage = self.arduino_controller.get_supply_voltage()
                if voltage is not None:
                    self.update_voltage(voltage)
                else:
                    self.logger.debug("Failed to get voltage from SMT Arduino")
            elif hasattr(self.arduino_controller, 'get_recent_sensor_data'):
                # For regular Arduino with LIVE data
                recent_data = self.arduino_controller.get_recent_sensor_data()
                
                # Look for INA260 voltage reading
                for reading in recent_data:
                    if reading.sensor_type == "voltage" and reading.sensor_id == "V":
                        self.update_voltage(reading.value)
                        break
            else:
                # No supported method
                self.logger.debug("Controller doesn't support voltage reading methods")
        except Exception as e:
            self.logger.error(f"Error checking voltage: {e}")
            
    def update_voltage(self, voltage: float):
        """Update voltage display and validity"""
        self.current_voltage = voltage
        
        # Check if voltage is in valid range
        new_valid = self.MIN_VOLTAGE <= voltage <= self.MAX_VOLTAGE
        
        # Update display
        self.voltage_display.setText(f"{voltage:.3f}V")
        
        # Update styles based on validity
        if new_valid:
            self.status_label.setText("✓")
            self.status_label.setStyleSheet("color: #51cf66;")
        else:
            self.status_label.setText("✗")
            self.status_label.setStyleSheet("color: #ff6b6b;")
            
        self.update_display_style(new_valid)
        
        # Emit signal if validity changed
        if new_valid != self.is_valid:
            self.is_valid = new_valid
            self.voltage_valid_changed.emit(new_valid)
            self.logger.info(f"Voltage validity changed: {new_valid} ({voltage:.3f}V)")
            
    def update_display_style(self, valid: bool):
        """Update voltage display style based on validity"""
        if valid:
            # Green background for valid
            self.voltage_display.setStyleSheet("""
                QLabel {
                    background-color: #2d5a2d;
                    color: #51cf66;
                    border: 1px solid #51cf66;
                    border-radius: 4px;
                    padding: 2px;
                }
            """)
        else:
            # Red background for invalid
            self.voltage_display.setStyleSheet("""
                QLabel {
                    background-color: #5a2d2d;
                    color: #ff6b6b;
                    border: 1px solid #ff6b6b;
                    border-radius: 4px;
                    padding: 2px;
                }
            """)
            
    def get_voltage(self) -> float:
        """Get current voltage"""
        return self.current_voltage
        
    def is_voltage_valid(self) -> bool:
        """Check if current voltage is in valid range"""
        return self.is_valid
        
    def stop_monitoring(self):
        """Stop voltage monitoring"""
        self.is_paused = False  # Clear flag
        self.update_timer.stop()
        self.logger.info("Voltage monitoring stopped")
        
    def pause_monitoring(self):
        """Temporarily pause voltage monitoring (e.g., during tests)"""
        self.is_paused = True  # Set flag immediately
        if self.update_timer.isActive():
            self.update_timer.stop()
            self.logger.info("Voltage monitoring paused")
        else:
            self.logger.warning("Voltage monitoring was not active when pause was called")
            
    def resume_monitoring(self):
        """Resume voltage monitoring after pause"""
        self.is_paused = False  # Clear flag
        if self.arduino_controller and self.arduino_controller.is_connected():
            self.update_timer.start(200)
            self.logger.info("Voltage monitoring resumed")