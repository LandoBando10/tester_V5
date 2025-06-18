# gui/components/connection_dialog.py
from typing import Dict, Any, Optional
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                               QGridLayout, QLabel, QComboBox, QPushButton, 
                               QDialogButtonBox, QMessageBox)
from PySide6.QtCore import Qt
from src.hardware.serial_manager import SerialManager
import logging
import time

logger = logging.getLogger(__name__)

class ConnectionDialog(QDialog):
    """Dialog for managing hardware connections"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hardware Connections")
        self.setModal(True)
        self.setMinimumSize(500, 400)
        logger.debug("ConnectionDialog initialized.")

        # Connection states
        self.arduino_connected = False
        self.scale_connected = False
        self.arduino_port = None
        self.scale_port = None
        self.arduino_crc_enabled = False  # Track CRC status

        self.setup_ui()
        self.refresh_ports()

    def setup_ui(self):
        """Setup the connection dialog UI"""
        logger.debug("Setting up ConnectionDialog UI.")
        layout = QVBoxLayout(self)

        # Arduino section
        arduino_group = QGroupBox("Arduino Connection (Offroad/SMT Testing)")
        arduino_layout = QGridLayout(arduino_group)

        arduino_layout.addWidget(QLabel("Port:"), 0, 0)
        self.arduino_port_combo = QComboBox()
        self.arduino_port_combo.setMinimumWidth(120)
        arduino_layout.addWidget(self.arduino_port_combo, 0, 1)

        self.arduino_connect_btn = QPushButton("Connect")
        self.arduino_connect_btn.clicked.connect(self.toggle_arduino_connection)
        arduino_layout.addWidget(self.arduino_connect_btn, 0, 2)

        self.arduino_status_label = QLabel("Status: Disconnected")
        self.arduino_status_label.setStyleSheet("color: red; font-weight: bold;")
        arduino_layout.addWidget(self.arduino_status_label, 1, 0, 1, 3)

        # Arduino info
        arduino_info = QLabel("Used for sensor readings and hardware control in Offroad and SMT testing modes.")
        arduino_info.setWordWrap(True)
        arduino_info.setStyleSheet("color: gray; font-style: italic; font-size: 10px;")
        arduino_layout.addWidget(arduino_info, 2, 0, 1, 3)

        layout.addWidget(arduino_group)

        # Scale section
        scale_group = QGroupBox("Scale Connection (Weight Testing)")
        scale_layout = QGridLayout(scale_group)

        scale_layout.addWidget(QLabel("Port:"), 0, 0)
        self.scale_port_combo = QComboBox()
        self.scale_port_combo.setMinimumWidth(120)
        scale_layout.addWidget(self.scale_port_combo, 0, 1)

        self.scale_connect_btn = QPushButton("Connect")
        self.scale_connect_btn.clicked.connect(self.toggle_scale_connection)
        scale_layout.addWidget(self.scale_connect_btn, 0, 2)

        self.scale_status_label = QLabel("Status: Disconnected")
        self.scale_status_label.setStyleSheet("color: red; font-weight: bold;")
        scale_layout.addWidget(self.scale_status_label, 1, 0, 1, 3)

        # Scale info
        scale_info = QLabel("Digital scale for weight verification testing in WeightChecking mode.")
        scale_info.setWordWrap(True)
        scale_info.setStyleSheet("color: #51cf66; font-style: italic; font-size: 10px;")
        scale_layout.addWidget(scale_info, 2, 0, 1, 3)

        layout.addWidget(scale_group)
        
        # Programmer section
        programmer_group = QGroupBox("Programming Tools (SMT Testing)")
        programmer_layout = QGridLayout(programmer_group)
        
        # STM8 Programmer
        programmer_layout.addWidget(QLabel("STM8 Programmer:"), 0, 0)
        self.stm8_status_label = QLabel("Status: Not checked")
        self.stm8_status_label.setStyleSheet("color: gray; font-weight: bold;")
        programmer_layout.addWidget(self.stm8_status_label, 0, 1)
        
        self.stm8_check_btn = QPushButton("Check")
        self.stm8_check_btn.clicked.connect(self.check_stm8_programmer)
        programmer_layout.addWidget(self.stm8_check_btn, 0, 2)
        
        # PIC Programmer
        programmer_layout.addWidget(QLabel("PIC Programmer:"), 1, 0)
        self.pic_status_label = QLabel("Status: Not checked")
        self.pic_status_label.setStyleSheet("color: gray; font-weight: bold;")
        programmer_layout.addWidget(self.pic_status_label, 1, 1)
        
        self.pic_check_btn = QPushButton("Check")
        self.pic_check_btn.clicked.connect(self.check_pic_programmer)
        programmer_layout.addWidget(self.pic_check_btn, 1, 2)
        
        # Check all programmers button
        self.check_all_prog_btn = QPushButton("Check All Programmers")
        self.check_all_prog_btn.clicked.connect(self.check_all_programmers)
        programmer_layout.addWidget(self.check_all_prog_btn, 2, 0, 1, 3)
        
        # Programmer info
        programmer_info = QLabel("Programming tools used for SMT board programming. Paths configured in Programming Configuration.")
        programmer_info.setWordWrap(True)
        programmer_info.setStyleSheet("color: gray; font-style: italic; font-size: 10px;")
        programmer_layout.addWidget(programmer_info, 3, 0, 1, 3)
        
        layout.addWidget(programmer_group)

        # Connection info section
        info_group = QGroupBox("Connection Information")
        info_layout = QVBoxLayout(info_group)
        
        info_text = QLabel("""
        <b>Connection Guidelines:</b><br>
        • <b>Arduino:</b> Required for Offroad and SMT testing modes<br>
        • <b>Scale:</b> Required for WeightChecking mode<br>
        • <b>Baud Rates:</b> Arduino (115200), Scale (9600)<br>
        • <b>Troubleshooting:</b> Check device manager for correct COM ports
        """)
        info_text.setWordWrap(True)
        info_text.setStyleSheet("font-size: 11px;")
        info_layout.addWidget(info_text)
        
        layout.addWidget(info_group)

        # Refresh button
        refresh_btn = QPushButton("Refresh Ports")
        refresh_btn.clicked.connect(self.refresh_ports)
        layout.addWidget(refresh_btn)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.accept) # Changed from self.close to self.accept for standard dialog behavior
        layout.addWidget(button_box)

        logger.debug("ConnectionDialog UI setup complete.")

    def refresh_ports(self):
        """Refresh available serial ports and identify device types"""
        try:
            logger.info("Refreshing serial ports and identifying devices...")
            temp_serial = SerialManager()
            ports = temp_serial.get_available_ports()

            # Get current selections (extract port names without device type)
            current_arduino = self.arduino_port_combo.currentText()
            current_scale = self.scale_port_combo.currentText()
            
            # Extract just the port name if it has device type
            if ' (' in current_arduino:
                current_arduino = current_arduino.split(' (')[0]
            if ' (' in current_scale:
                current_scale = current_scale.split(' (')[0]

            # Identify device types for each port
            port_info = self._identify_devices(ports)

            # Create display strings with device types
            arduino_items = []
            scale_items = []
            
            for port in ports:
                device_type = port_info.get(port, "Unknown")
                display_name = f"{port} ({device_type})"
                
                # Add to appropriate lists based on device type
                if device_type in ["SMT Arduino", "Offroad Arduino"]:
                    arduino_items.append(display_name)
                    scale_items.append(display_name)  # Also show in scale list as fallback
                elif device_type == "Scale":
                    scale_items.append(display_name)
                    arduino_items.append(display_name)  # Also show in Arduino list as fallback
                else:
                    # Unknown devices go in both lists
                    arduino_items.append(display_name)
                    scale_items.append(display_name)

            # Update combo boxes
            self.arduino_port_combo.clear()
            self.arduino_port_combo.addItems(arduino_items)

            self.scale_port_combo.clear()
            self.scale_port_combo.addItems(scale_items)

            # Restore selections if still available
            for i in range(self.arduino_port_combo.count()):
                if self.arduino_port_combo.itemText(i).startswith(current_arduino + " ("):
                    self.arduino_port_combo.setCurrentIndex(i)
                    break
                    
            for i in range(self.scale_port_combo.count()):
                if self.scale_port_combo.itemText(i).startswith(current_scale + " ("):
                    self.scale_port_combo.setCurrentIndex(i)
                    break
                    
            logger.info(f"Ports refreshed. Found: {port_info}")
        except Exception as e:
            logger.error(f"Could not refresh ports: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Could not refresh ports: {e}")

    def _identify_devices(self, ports: list) -> dict:
        """Identify device type for each port"""
        port_info = {}
        
        for port in ports:
            try:
                # Skip ports that are already connected
                if (self.arduino_connected and self.arduino_port == port) or \
                   (self.scale_connected and self.scale_port == port):
                    # Mark as already connected
                    if self.arduino_connected and self.arduino_port == port:
                        port_info[port] = "Connected Arduino"
                    else:
                        port_info[port] = "Connected Scale"
                    continue
                
                # Try to identify the device
                device_type = self._probe_port(port)
                port_info[port] = device_type
                
            except Exception as e:
                logger.debug(f"Error identifying device on {port}: {e}")
                port_info[port] = "Unknown"
        
        return port_info
    
    def _probe_port(self, port: str) -> str:
        """Probe a single port to identify device type"""
        device_type = "Unknown"
        
        try:
            # Create a temporary serial connection
            temp_serial = SerialManager(baud_rate=115200, timeout=0.5)
            
            # Try Arduino connection first (115200 baud)
            if temp_serial.connect(port):
                try:
                    # Clear buffers
                    temp_serial.flush_buffers()
                    time.sleep(0.05)
                    
                    # Send ID command
                    response = temp_serial.query("I", response_timeout=1.0)
                    if response:
                        response_upper = response.upper()
                        if "SMT" in response_upper or "SMT_TESTER" in response_upper:
                            device_type = "SMT Arduino"
                        elif "OFFROAD" in response_upper:
                            device_type = "Offroad Arduino"
                        elif "DIODE_DYNAMICS" in response_upper:
                            # Generic firmware - try to get more info
                            status = temp_serial.query("STATUS", response_timeout=0.5)
                            if status and "SMT" in status.upper():
                                device_type = "SMT Arduino"
                            else:
                                device_type = "Offroad Arduino"
                    
                except Exception as e:
                    logger.debug(f"Arduino probe failed on {port}: {e}")
                
                finally:
                    temp_serial.disconnect()
            
            # If not identified as Arduino, try Scale (9600 baud)
            if device_type == "Unknown":
                temp_serial = SerialManager(baud_rate=9600, timeout=0.3)
                if temp_serial.connect(port):
                    try:
                        # Wait a bit for scale data
                        time.sleep(0.1)
                        
                        # Try to read a line
                        for _ in range(3):
                            line = temp_serial.read_line(timeout=0.1)
                            if line:
                                # Check if it looks like scale data
                                if 'g' in line or 'GS' in line or any(c.isdigit() for c in line):
                                    device_type = "Scale"
                                    break
                    
                    except Exception as e:
                        logger.debug(f"Scale probe failed on {port}: {e}")
                    
                    finally:
                        temp_serial.disconnect()
        
        except Exception as e:
            logger.debug(f"Error probing port {port}: {e}")
        
        return device_type

    def toggle_arduino_connection(self):
        """Toggle Arduino connection"""
        if self.arduino_connected:
            logger.info("Toggling Arduino connection: Disconnecting.")
            self.disconnect_arduino()
        else:
            logger.info("Toggling Arduino connection: Connecting.")
            self.connect_arduino()

    def toggle_scale_connection(self):
        """Toggle Scale connection"""
        if self.scale_connected:
            logger.info("Toggling Scale connection: Disconnecting.")
            self.disconnect_scale()
        else:
            logger.info("Toggling Scale connection: Connecting.")
            self.connect_scale()

    def connect_arduino(self):
        """Connect to Arduino"""
        port_text = self.arduino_port_combo.currentText()
        if not port_text:
            logger.warning("Arduino connection attempt failed: No port selected.")
            QMessageBox.warning(self, "Warning", "Please select a port for Arduino.")
            return
        
        # Extract the actual port name (remove device type if present)
        if ' (' in port_text:
            port = port_text.split(' (')[0]
        else:
            port = port_text

        logger.info(f"Attempting to connect to Arduino on port: {port}")
        try:
            # Import the appropriate controller based on mode
            current_mode = self.parent().current_mode
            
            if current_mode == "SMT":
                from src.hardware.smt_arduino_controller import SMTArduinoController
                # Create SMT Arduino instance if it doesn't exist
                if not self.parent().arduino_controller:
                    self.parent().arduino_controller = SMTArduinoController(baud_rate=115200)
            else:
                from src.hardware.arduino_controller import ArduinoController
                # Create Arduino instance if it doesn't exist
                if not self.parent().arduino_controller:
                    self.parent().arduino_controller = ArduinoController(baud_rate=115200)
            
            arduino = self.parent().arduino_controller
            
            if arduino.connect(port):
                # Test communication
                if arduino.test_communication():
                    # Get firmware type
                    firmware_type = arduino.get_firmware_type()
                    current_mode = self.parent().current_mode
                    
                    # Store firmware type for later validation
                    arduino._firmware_type = firmware_type
                    
                    # Validate firmware matches mode
                    firmware_valid = False
                    if firmware_type == "UNKNOWN":
                        # Couldn't determine firmware type
                        reply = QMessageBox.question(self, "Unknown Firmware", 
                                                   f"Could not determine Arduino firmware type. "
                                                   f"Are you sure this Arduino has {current_mode} firmware?",
                                                   QMessageBox.Yes | QMessageBox.No)
                        firmware_valid = (reply == QMessageBox.Yes)
                    elif firmware_type == current_mode.upper():
                        firmware_valid = True
                    else:
                        # Wrong firmware for current mode
                        QMessageBox.warning(self, "Wrong Arduino Firmware", 
                                          f"This Arduino has {firmware_type} firmware, "
                                          f"but you are in {current_mode} mode.\n\n"
                                          f"Please connect an Arduino with {current_mode} firmware.")
                        arduino.disconnect()
                        self.parent().arduino_controller = None
                        return
                    
                    if not firmware_valid:
                        arduino.disconnect()
                        self.parent().arduino_controller = None
                        return
                    
                    # Configure sensors based on current mode
                    from src.hardware.arduino_controller import SensorConfigurations
                    
                    if current_mode == "SMT":
                        sensor_configs = SensorConfigurations.smt_panel_sensors()
                    else:  # Offroad
                        sensor_configs = SensorConfigurations.offroad_pod_sensors()
                    
                    if not arduino.configure_sensors(sensor_configs):
                        logger.error(f"Failed to configure sensors for {current_mode}")
                        QMessageBox.warning(self, "Sensor Configuration Failed", 
                                          f"Arduino connected but sensor configuration failed for {current_mode} mode.")
                        return
                    
                    arduino._sensors_configured = True
                    logger.info(f"Sensors configured for {current_mode} mode")
                    
                    # Enable CRC-16 validation if supported (BEFORE starting reading loop)
                    crc_enabled = False
                    try:
                        # Check if this is SMT Arduino controller with CRC support
                        if hasattr(arduino, 'enable_crc_validation'):
                            logger.info("Attempting to enable CRC-16 validation...")
                            crc_enabled = arduino.enable_crc_validation(True)
                            if crc_enabled:
                                logger.info("CRC-16 validation enabled successfully")
                            else:
                                logger.info("CRC-16 not supported by firmware - continuing without it")
                    except Exception as crc_error:
                        logger.warning(f"Could not enable CRC: {crc_error}")
                    
                    # Set up button callback for SMT mode (AFTER CRC setup)
                    if current_mode == "SMT" and hasattr(self.parent(), 'smt_handler'):
                        logger.info("Setting up physical button callback for SMT mode")
                        arduino.set_button_callback(self.parent().smt_handler.handle_button_event)
                        
                        # Start the reading loop to process button events (AFTER CRC is configured)
                        if not arduino.is_reading:
                            logger.info("Starting Arduino reading loop for button events")
                            arduino.start_reading()
                    
                    # Don't disconnect - keep it connected!
                    self.arduino_connected = True
                    self.arduino_port = port
                    self.arduino_crc_enabled = crc_enabled  # Store CRC status
                    
                    # Update status label to show CRC status
                    crc_status = " [CRC ON]" if crc_enabled else ""
                    self.arduino_status_label.setText(f"Status: Connected ({port}) - {firmware_type}{crc_status}")
                    self.arduino_status_label.setStyleSheet("color: green; font-weight: bold;")
                    self.arduino_connect_btn.setText("Disconnect")
                    logger.info(f"Successfully connected to {firmware_type} Arduino on {port} with CRC={'enabled' if crc_enabled else 'disabled'}.")
                else:
                    arduino.disconnect()
                    self.parent().arduino_controller = None
                    logger.warning(f"Arduino connected on {port} but communication test failed.")
                    QMessageBox.warning(self, "Connection Failed", 
                                        "Arduino connected but communication test failed. Check firmware and connections.")
            else:
                logger.warning(f"Could not connect to Arduino on {port}.")
                QMessageBox.warning(self, "Connection Failed", 
                                    f"Could not connect to Arduino on {port}. Ensure device is available and not in use.")
                
        except ImportError as e_imp:
            logger.error(f"Failed to import ArduinoController: {e_imp}", exc_info=True)
            QMessageBox.critical(self, "Import Error", f"Failed to load Arduino controller: {e_imp}")
        except Exception as e:
            logger.error(f"Arduino connection error on port {port}: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Arduino connection error on {port}: {e}")

    def disconnect_arduino(self):
        """Disconnect Arduino"""
        try:
            if self.parent().arduino_controller:
                # Stop reading loop if running
                if self.parent().arduino_controller.is_reading:
                    logger.info("Stopping Arduino reading loop")
                    self.parent().arduino_controller.stop_reading()
                    
                # Clear button callback
                self.parent().arduino_controller.set_button_callback(None)
                self.parent().arduino_controller.disconnect()
                self.parent().arduino_controller = None
        except Exception as e:
            logger.error(f"Error disconnecting Arduino: {e}")
        
        self.arduino_connected = False
        self.arduino_port = None
        self.arduino_crc_enabled = False
        self.arduino_status_label.setText("Status: Disconnected")
        self.arduino_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.arduino_connect_btn.setText("Connect")
        logger.info("Arduino disconnected.")

    def connect_scale(self):
        """Connect to Scale"""
        port_text = self.scale_port_combo.currentText()
        if not port_text:
            logger.warning("Scale connection attempt failed: No port selected.")
            QMessageBox.warning(self, "Warning", "Please select a port for the Scale.")
            return
        
        # Extract the actual port name (remove device type if present)
        if ' (' in port_text:
            port = port_text.split(' (')[0]
        else:
            port = port_text

        logger.info(f"Attempting to connect to Scale on port: {port}")
        try:
            # Test scale connection
            from src.hardware.scale_controller import ScaleController
            scale = ScaleController(baud_rate=9600)
            
            if scale.connect(port):
                # Test communication
                if scale.test_communication():
                    # Keep the connection alive and store it for reuse
                    self.parent().scale_controller = scale
                    
                    self.scale_connected = True
                    self.scale_port = port
                    self.scale_status_label.setText(f"Status: Connected ({port})")
                    self.scale_status_label.setStyleSheet("color: green; font-weight: bold;")
                    self.scale_connect_btn.setText("Disconnect")
                    logger.info(f"Successfully connected to Scale on {port}.")
                else:
                    scale.disconnect()
                    logger.warning(f"Scale connected on {port} but communication test failed.")
                    QMessageBox.warning(self, "Connection Failed", 
                                        "Scale connected but communication test failed. Check scale settings.")
            else:
                logger.warning(f"Could not connect to Scale on {port}.")
                QMessageBox.warning(self, "Connection Failed", 
                                    f"Could not connect to scale on {port}. Ensure device is available and not in use.")
                
        except ImportError as e_imp:
            logger.error(f"Failed to import ScaleController: {e_imp}", exc_info=True)
            QMessageBox.critical(self, "Import Error", f"Failed to load Scale controller: {e_imp}")
        except Exception as e:
            logger.error(f"Scale connection error on port {port}: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Scale connection error on {port}: {e}")

    def disconnect_scale(self):
        """Disconnect Scale"""
        # Actually disconnect the scale hardware
        if hasattr(self.parent(), 'scale_controller') and self.parent().scale_controller:
            try:
                self.parent().scale_controller.disconnect()
                logger.info(f"Scale hardware disconnected from {self.scale_port}")
            except Exception as e:
                logger.error(f"Error disconnecting scale hardware: {e}")
            finally:
                self.parent().scale_controller = None
        
        self.scale_connected = False
        self.scale_port = None
        self.scale_status_label.setText("Status: Disconnected")
        self.scale_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.scale_connect_btn.setText("Connect")
        logger.info(f"Scale disconnected from connection dialog.")
    
    def check_stm8_programmer(self):
        """Check STM8 programmer availability"""
        logger.info("Checking STM8 programmer status.")
        try:
            programmer_config = self._get_programming_config()
            if not programmer_config:
                logger.warning("STM8 check: Programming config not found.")
                self.stm8_status_label.setText("Status: No config found")
                self.stm8_status_label.setStyleSheet("color: orange; font-weight: bold;")
                return
            
            # Find STM8 programmer in config
            stm8_programmer = None
            for prog_name, prog_config in programmer_config.get('programmers', {}).items():
                if prog_config.get('type', '').upper() == 'STM8':
                    stm8_programmer = prog_config
                    break
            
            if not stm8_programmer:
                self.stm8_status_label.setText("Status: Not configured")
                self.stm8_status_label.setStyleSheet("color: orange; font-weight: bold;")
                return
            
            # Check if programmer executable exists
            programmer_path = stm8_programmer.get('path', '')
            if not programmer_path:
                self.stm8_status_label.setText("Status: No path configured")
                self.stm8_status_label.setStyleSheet("color: red; font-weight: bold;")
                return
            
            from pathlib import Path
            if not Path(programmer_path).exists():
                logger.warning(f"STM8 check: Executable not found at {programmer_path}.")
                self.stm8_status_label.setText("Status: Executable not found")
                self.stm8_status_label.setStyleSheet("color: red; font-weight: bold;")
                return
            
            # Try to verify programmer
            from src.core.programmer_controller import ProgrammerController
            programmer = ProgrammerController('STM8', programmer_path)
            connected, message = programmer.verify_connection()
            
            if connected:
                self.stm8_status_label.setText("Status: Available")
                self.stm8_status_label.setStyleSheet("color: green; font-weight: bold;")
                logger.info("STM8 programmer is available.")
            else:
                self.stm8_status_label.setText(f"Status: {message}")
                self.stm8_status_label.setStyleSheet("color: red; font-weight: bold;")
                logger.warning(f"STM8 programmer check failed: {message}")
                
        except ImportError as e_imp:
            logger.error(f"Failed to import ProgrammerController for STM8 check: {e_imp}", exc_info=True)
            self.stm8_status_label.setText("Status: Import Error")
            self.stm8_status_label.setStyleSheet("color: red; font-weight: bold;")
        except Exception as e:
            logger.error(f"Error checking STM8 programmer: {e}", exc_info=True)
            self.stm8_status_label.setText(f"Status: Error - {str(e)[:30]}...")

    def check_pic_programmer(self):
        """Check PIC programmer availability"""
        logger.info("Checking PIC programmer status.")
        try:
            programmer_config = self._get_programming_config()
            if not programmer_config:
                logger.warning("PIC check: Programming config not found.")
                self.pic_status_label.setText("Status: No config found")
                self.pic_status_label.setStyleSheet("color: orange; font-weight: bold;")
                return
            
            # Find PIC programmer in config
            pic_programmer = None
            for prog_name, prog_config in programmer_config.get('programmers', {}).items():
                if prog_config.get('type', '').upper() == 'PIC':
                    pic_programmer = prog_config
                    break
            
            if not pic_programmer:
                self.pic_status_label.setText("Status: Not configured")
                self.pic_status_label.setStyleSheet("color: orange; font-weight: bold;")
                return
            
            # Check if programmer executable exists
            programmer_path = pic_programmer.get('path', '')
            if not programmer_path:
                self.pic_status_label.setText("Status: No path configured")
                self.pic_status_label.setStyleSheet("color: red; font-weight: bold;")
                return
            
            from pathlib import Path
            if not Path(programmer_path).exists():
                logger.warning(f"PIC check: Executable not found at {programmer_path}.")
                self.pic_status_label.setText("Status: Executable not found")
                self.pic_status_label.setStyleSheet("color: red; font-weight: bold;")
                return
            
            # Try to verify programmer
            from src.core.programmer_controller import ProgrammerController
            programmer = ProgrammerController('PIC', programmer_path)
            connected, message = programmer.verify_connection()
            
            if connected:
                self.pic_status_label.setText("Status: Available")
                self.pic_status_label.setStyleSheet("color: green; font-weight: bold;")
                logger.info("PIC programmer is available.")
            else:
                self.pic_status_label.setText(f"Status: {message}")
                self.pic_status_label.setStyleSheet("color: red; font-weight: bold;")
                logger.warning(f"PIC programmer check failed: {message}")
                
        except ImportError as e_imp:
            logger.error(f"Failed to import ProgrammerController for PIC check: {e_imp}", exc_info=True)
            self.pic_status_label.setText("Status: Import Error")
            self.pic_status_label.setStyleSheet("color: red; font-weight: bold;")
        except Exception as e:
            logger.error(f"Error checking PIC programmer: {e}", exc_info=True)
            self.pic_status_label.setText(f"Status: Error - {str(e)[:30]}...")

    def check_all_programmers(self):
        """Check all programmers"""
        logger.info("Checking status of all programmers.")
        self.check_stm8_programmer()
        self.check_pic_programmer()
    
    def _get_programming_config(self) -> Optional[Dict]:
        """Get programming configuration from file"""
        logger.debug("Attempting to load programming_config.json.")
        try:
            import json
            from pathlib import Path
            
            config_path = Path("config") / "programming_config.json"
            if not config_path.exists():
                logger.warning(f"Programming configuration file not found at {config_path}.")
                return None
            
            with open(config_path, 'r') as f:
                config = json.load(f)
            logger.debug(f"Successfully loaded programming_config.json.")
            
            # Return default config for checking tools
            # In a real implementation, you might want to check all SKUs
            return config.get('default', {})
            
        except json.JSONDecodeError as e_json:
            logger.error(f"Error decoding JSON from programming_config.json: {e_json}", exc_info=True)
            QMessageBox.warning(self, "Config Error", f"Error reading programming configuration: Invalid JSON in {config_path.name}.")
            return None
        except IOError as e_io:
            logger.error(f"IOError reading programming_config.json: {e_io}", exc_info=True)
            QMessageBox.warning(self, "File Error", f"Could not read programming configuration file: {config_path.name}.")
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading programming_config.json: {e}", exc_info=True)
            # Avoid showing another QMessageBox if one was already shown for JSON/IO error
            if not isinstance(e, (json.JSONDecodeError, IOError)):
                 QMessageBox.critical(self, "Error", "An unexpected error occurred while loading programming configuration.")
            return None

    def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status"""
        status = {
            'arduino_connected': self.arduino_connected,
            'arduino_port': self.arduino_port,
            'arduino_crc_enabled': self.arduino_crc_enabled,
            'scale_connected': self.scale_connected,
            'scale_port': self.scale_port
        }
        logger.debug(f"Returning connection status: {status}")
        return status