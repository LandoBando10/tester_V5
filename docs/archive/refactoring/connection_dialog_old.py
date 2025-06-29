# gui/components/connection_dialog.py
from typing import Dict, Any, Optional, List
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                               QGridLayout, QLabel, QComboBox, QPushButton, 
                               QDialogButtonBox, QMessageBox, QProgressDialog)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from src.hardware.serial_manager import SerialManager
import logging
import time
import concurrent.futures
import json
from pathlib import Path
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class DeviceInfo:
    """Store device information for caching"""
    port: str
    device_type: str
    timestamp: float
    
class PortScannerThread(QThread):
    """Background thread for scanning ports"""
    progress = Signal(int, str)  # progress value, status message
    finished = Signal(dict)      # port_info dictionary
    
    def __init__(self, ports: List[str]):
        super().__init__()
        self.ports = ports
        self._stop_requested = False
        self._arduino_found = False
        
    def run(self):
        """Run port scanning in background"""
        port_info = {}
        total_ports = len(self.ports)
        
        # Use thread pool for parallel port probing
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, total_ports)) as executor:
            # Submit all port probes
            future_to_port = {
                executor.submit(self._probe_port_fast, port): port 
                for port in self.ports
            }
            
            # Collect results as they complete
            completed = 0
            for future in concurrent.futures.as_completed(future_to_port):
                if self._stop_requested:
                    executor.shutdown(wait=False)
                    break
                    
                port = future_to_port[future]
                try:
                    device_type = future.result()
                    port_info[port] = device_type
                    
                    # Track if we found an Arduino
                    if device_type in ["SMT Arduino", "Offroad Arduino", "Arduino"]:
                        self._arduino_found = True
                    
                    completed += 1
                    self.progress.emit(
                        int(completed / total_ports * 100), 
                        f"Identified {port}: {device_type}"
                    )
                except Exception as e:
                    logger.error(f"Error probing {port}: {e}")
                    port_info[port] = "Unknown"
                    
        self.finished.emit(port_info)
    
    def stop(self):
        """Request the thread to stop"""
        self._stop_requested = True
        
    def _probe_port_fast(self, port: str) -> str:
        """Fast port probing with reduced timeouts"""
        device_type = "Unknown"
        
        try:
            # Try Arduino first (most common)
            temp_serial = SerialManager(baud_rate=115200, timeout=0.1)
            
            if temp_serial.connect(port):
                try:
                    temp_serial.flush_buffers()
                    
                    # Try I command first (SMT Arduino expects this), then ID for compatibility
                    response = temp_serial.query("I", response_timeout=0.1)
                    if not response or "ERROR" in response.upper():
                        response = temp_serial.query("ID", response_timeout=0.1)
                    
                    if response:
                        response_upper = response.upper()
                        logger.debug(f"Arduino response on {port}: {response}")
                        # Check for specific Arduino types
                        if "SMT_BATCH_TESTER" in response_upper or "SMT" in response_upper or "SMT_SIMPLE_TESTER" in response_upper or "ARDUINO SMT" in response_upper:
                            device_type = "SMT Arduino"
                        elif "OFFROAD" in response_upper or "ARDUINO OFFROAD" in response_upper:
                            device_type = "Offroad Arduino"
                        elif "DIODE" in response_upper or "ARDUINO" in response_upper:
                            device_type = "Arduino"
                    
                except Exception:
                    pass
                finally:
                    temp_serial.disconnect()
            
            # If not Arduino, quickly check for scale
            # Skip scale check if we already found an Arduino to save time
            if device_type == "Unknown":
                # Skip scale check if we already found an Arduino on another port
                if hasattr(self, '_arduino_found') and self._arduino_found:
                    logger.debug(f"Skipping scale check on {port} - Arduino already found")
                    return device_type
                    
                temp_serial = SerialManager(baud_rate=9600, timeout=0.05)
                if temp_serial.connect(port):
                    try:
                        time.sleep(0.05)
                        if temp_serial.connection.in_waiting > 0:
                            line = temp_serial.read_line(timeout=0.05)
                            if line and ('g' in line or 'GS' in line or any(c.isdigit() for c in line)):
                                device_type = "Scale"
                    except Exception:
                        pass
                    finally:
                        temp_serial.disconnect()
        
        except Exception as e:
            logger.debug(f"Fast probe error on {port}: {e}")
        
        return device_type

class ProgressivePortScanner(QThread):
    """Progressive port scanner that scans remaining ports after initial connection"""
    port_found = Signal(str, str)  # port, device_type - emitted as each port is identified
    scan_complete = Signal(dict)    # final port_info dictionary
    
    def __init__(self, ports_to_scan: List[str], parent=None):
        super().__init__(parent)
        self.ports_to_scan = ports_to_scan
        self._stop_requested = False
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def run(self):
        """Scan remaining ports in background"""
        port_info = {}
        
        try:
            self.logger.info(f"Starting background scan of {len(self.ports_to_scan)} remaining ports")
            
            # Use thread pool for parallel scanning
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                if self._stop_requested:
                    return
                    
                future_to_port = {
                    executor.submit(self._probe_port_fast, port): port 
                    for port in self.ports_to_scan
                }
                
                for future in concurrent.futures.as_completed(future_to_port):
                    if self._stop_requested:
                        executor.shutdown(wait=False)
                        break
                        
                    port = future_to_port[future]
                    try:
                        device_type = future.result()
                        port_info[port] = device_type
                        # Emit signal for each port found
                        self.port_found.emit(port, device_type)
                        self.logger.debug(f"Background scan identified {port}: {device_type}")
                    except Exception as e:
                        self.logger.error(f"Error probing {port}: {e}")
                        port_info[port] = "Unknown"
                        self.port_found.emit(port, "Unknown")
                        
        except Exception as e:
            self.logger.error(f"Background port scan error: {e}")
        finally:
            self.scan_complete.emit(port_info)
            self.logger.info(f"Background scan complete: {port_info}")
    
    def stop(self):
        """Request the scanner to stop"""
        self._stop_requested = True
        
    def _probe_port_fast(self, port: str) -> str:
        """Fast port probing with reduced timeouts"""
        device_type = "Unknown"
        
        try:
            # Try Arduino first (most common)
            temp_serial = SerialManager(baud_rate=115200, timeout=0.1)
            
            if temp_serial.connect(port):
                try:
                    temp_serial.flush_buffers()
                    
                    # Try I command first (SMT Arduino expects this), then ID for compatibility
                    response = temp_serial.query("I", response_timeout=0.1)
                    if not response or "ERROR" in response.upper():
                        response = temp_serial.query("ID", response_timeout=0.1)
                    
                    if response:
                        response_upper = response.upper()
                        logger.debug(f"Arduino response on {port}: {response}")
                        # Check for specific Arduino types
                        if "SMT_BATCH_TESTER" in response_upper or "SMT" in response_upper or "SMT_SIMPLE_TESTER" in response_upper or "ARDUINO SMT" in response_upper:
                            device_type = "SMT Arduino"
                        elif "OFFROAD" in response_upper or "ARDUINO OFFROAD" in response_upper:
                            device_type = "Offroad Arduino"
                        elif "DIODE" in response_upper or "ARDUINO" in response_upper:
                            device_type = "Arduino"
                    
                except Exception:
                    pass
                finally:
                    temp_serial.disconnect()
            
            # If not Arduino, quickly check for scale
            if device_type == "Unknown":
                temp_serial = SerialManager(baud_rate=9600, timeout=0.05)
                if temp_serial.connect(port):
                    try:
                        time.sleep(0.05)
                        if temp_serial.connection.in_waiting > 0:
                            line = temp_serial.read_line(timeout=0.05)
                            if line and ('g' in line or 'GS' in line or any(c.isdigit() for c in line)):
                                device_type = "Scale"
                    except Exception:
                        pass
                    finally:
                        temp_serial.disconnect()
        
        except Exception as e:
            logger.debug(f"Fast probe error on {port}: {e}")
        
        return device_type

class ConnectionDialog(QDialog):
    """Dialog for managing hardware connections with optimized port detection"""
    
    # Cache configuration
    CACHE_FILE = Path("config") / ".device_cache.json"
    CACHE_TIMEOUT = 86400  # 24 hours
    
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
        
        # Port scanner thread
        self.scanner_thread = None
        
        # Progressive scanner for background scanning
        self.progressive_scanner = None
        
        # Device cache (instance variable for thread safety)
        self._device_cache = {}
        self._load_device_cache()
        
        # Auto-connect flag for startup
        self._auto_connect_enabled = True
        self._startup_scan_done = False
        
        # Store preloaded port information
        self.preloaded_port_info = {}
        
        # Track if we're doing background scanning
        self._background_scan_in_progress = False

        self.setup_ui()

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

        # Button layout with quick and full refresh
        button_layout = QHBoxLayout()
        
        self.quick_refresh_btn = QPushButton("Quick Refresh")
        self.quick_refresh_btn.clicked.connect(self.quick_refresh_ports)
        button_layout.addWidget(self.quick_refresh_btn)
        
        self.full_refresh_btn = QPushButton("Full Refresh")
        self.full_refresh_btn.clicked.connect(self.full_refresh_ports)
        button_layout.addWidget(self.full_refresh_btn)
        
        layout.addLayout(button_layout)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.accept)
        layout.addWidget(button_box)

        logger.debug("ConnectionDialog UI setup complete.")

    def set_preloaded_ports(self, port_info: Dict[str, str]):
        """Set preloaded port information from splash screen scan"""
        try:
            logger.info(f"Setting preloaded port info: {port_info}")
            self.preloaded_port_info = port_info
            
            if not port_info:
                logger.info("No preloaded port info provided")
                return
                
            # Clear existing items
            self.arduino_port_combo.clear()
            self.scale_port_combo.clear()
            
            # Populate combo boxes with identified devices
            for port, device_type in sorted(port_info.items()):
                display_text = f"{port} ({device_type})"
                self.arduino_port_combo.addItem(display_text)
                self.scale_port_combo.addItem(display_text)
            
            logger.info(f"Populated combo boxes with {len(port_info)} preloaded ports")
            
            # Update cache with preloaded info
            for port, device_type in port_info.items():
                self._device_cache[port] = DeviceInfo(
                    port=port,
                    device_type=device_type,
                    timestamp=time.time()
                )
            self._save_device_cache()
            
        except Exception as e:
            logger.error(f"Error setting preloaded ports: {e}")
    
    def quick_refresh_ports(self):
        """Quick refresh using cached device types and background scanning"""
        try:
            logger.info("Quick refresh using cached device types...")
            temp_serial = SerialManager()
            ports = temp_serial.get_available_ports()
            
            # Build port info from cache and connected devices
            port_info = {}
            current_time = time.time()
            unknown_ports = []
            arduino_found_in_cache = False
            
            for port in ports:
                # Check if already connected
                if self.arduino_connected and self.arduino_port == port:
                    port_info[port] = "Connected Arduino"
                elif self.scale_connected and self.scale_port == port:
                    port_info[port] = "Connected Scale"
                # Check cache
                elif port in self._device_cache:
                    cached = self._device_cache[port]
                    if current_time - cached.timestamp < self.CACHE_TIMEOUT:
                        port_info[port] = cached.device_type
                        if cached.device_type in ["SMT Arduino", "Offroad Arduino", "Arduino"]:
                            arduino_found_in_cache = True
                    else:
                        port_info[port] = "Unknown"
                        unknown_ports.append(port)
                else:
                    port_info[port] = "Unknown"
                    unknown_ports.append(port)
            
            # Update UI immediately with what we know
            self._update_port_combos(port_info)
            
            # If Arduino already connected (from preloader), update UI and start background scan
            if self.arduino_connected and self.arduino_port:
                logger.info(f"Arduino already connected on {self.arduino_port}, starting background scan for other ports")
                # Update UI to show connected state
                self.arduino_status_label.setText(f"Status: Connected ({self.arduino_port})")
                self.arduino_status_label.setStyleSheet("color: green; font-weight: bold;")
                self.arduino_connect_btn.setText("Disconnect")
                
                # Update connection handler
                if hasattr(self.parent(), 'connection_handler'):
                    self.parent().connection_handler.update_connection_status()
                
                # Start background scan for remaining ports if there are unknowns
                if unknown_ports and not self._background_scan_in_progress:
                    self._start_background_port_scan(unknown_ports)
                return
            
            # If all non-connected ports are unknown, trigger silent scan for startup
            non_connected_ports = [p for p in ports 
                                  if not (self.arduino_connected and self.arduino_port == p) 
                                  and not (self.scale_connected and self.scale_port == p)]
            
            if (non_connected_ports and len(unknown_ports) >= len(non_connected_ports) and 
                self._auto_connect_enabled and not self._startup_scan_done):
                logger.info("No cached device info available, triggering silent startup scan")
                # Do a silent background scan for startup
                self._silent_scan_for_startup(ports)
                return
                
            logger.info(f"Quick refresh completed. Found: {port_info}")
            
            # Auto-connect to Arduino if found in cache during startup
            if (self._auto_connect_enabled and not self._startup_scan_done and 
                not self.arduino_connected and arduino_found_in_cache):
                self._startup_scan_done = True
                
                # Find first Arduino in port_info
                for port, device_type in port_info.items():
                    if device_type in ["SMT Arduino", "Offroad Arduino", "Arduino"]:
                        logger.info(f"Auto-connecting to cached {device_type} on {port} during startup")
                        
                        # Select the port in the combo box
                        for i in range(self.arduino_port_combo.count()):
                            if self.arduino_port_combo.itemText(i).startswith(port + " ("):
                                self.arduino_port_combo.setCurrentIndex(i)
                                break
                        
                        # Trigger connection
                        QTimer.singleShot(100, self.connect_arduino)
                        break
            
            # Start background scan for unknown ports if needed
            if unknown_ports and not self._background_scan_in_progress:
                self._start_background_port_scan(unknown_ports)
            
        except Exception as e:
            logger.error(f"Quick refresh error: {e}")
            QMessageBox.warning(self, "Error", f"Could not refresh ports: {e}")
    
    def _start_background_port_scan(self, ports_to_scan: List[str]):
        """Start background scanning of remaining ports"""
        try:
            logger.info(f"Starting background scan for {len(ports_to_scan)} unknown ports")
            self._background_scan_in_progress = True
            
            # Create and start progressive scanner
            self.progressive_scanner = ProgressivePortScanner(ports_to_scan, self)
            
            # Connect signals
            self.progressive_scanner.port_found.connect(self._on_background_port_found)
            self.progressive_scanner.scan_complete.connect(self._on_background_scan_complete)
            
            # Start scanning
            self.progressive_scanner.start()
            
            # Update UI to show scanning in progress
            # Add a temporary item to show scanning status
            if self.arduino_port_combo.count() > 0:
                # Find if we already have a scanning indicator
                has_indicator = False
                for i in range(self.arduino_port_combo.count()):
                    if "Scanning" in self.arduino_port_combo.itemText(i):
                        has_indicator = True
                        break
                
                if not has_indicator:
                    self.arduino_port_combo.addItem("-- Scanning other ports... --")
                    self.scale_port_combo.addItem("-- Scanning other ports... --")
            
        except Exception as e:
            logger.error(f"Error starting background scan: {e}")
            self._background_scan_in_progress = False
    
    def _on_background_port_found(self, port: str, device_type: str):
        """Handle a port being identified during background scanning"""
        try:
            logger.debug(f"Background scan found {port}: {device_type}")
            
            # Update cache
            if device_type != "Unknown":
                self._device_cache[port] = DeviceInfo(port, device_type, time.time())
            
            # Update combo boxes
            display_text = f"{port} ({device_type})"
            
            # Update Arduino combo
            for i in range(self.arduino_port_combo.count()):
                if self.arduino_port_combo.itemText(i).startswith(port + " ("):
                    self.arduino_port_combo.setItemText(i, display_text)
                    break
            
            # Update Scale combo
            for i in range(self.scale_port_combo.count()):
                if self.scale_port_combo.itemText(i).startswith(port + " ("):
                    self.scale_port_combo.setItemText(i, display_text)
                    break
                    
        except Exception as e:
            logger.error(f"Error handling background port found: {e}")
    
    def _on_background_scan_complete(self, port_info: dict):
        """Handle completion of background scanning"""
        try:
            logger.info(f"Background scan complete. Results: {port_info}")
            self._background_scan_in_progress = False
            
            # Save updated cache
            self._save_device_cache()
            
            # Remove scanning indicator from combo boxes
            for combo in [self.arduino_port_combo, self.scale_port_combo]:
                for i in range(combo.count() - 1, -1, -1):
                    if "Scanning" in combo.itemText(i):
                        combo.removeItem(i)
            
            # Clean up scanner
            if self.progressive_scanner:
                self.progressive_scanner.deleteLater()
                self.progressive_scanner = None
                
        except Exception as e:
            logger.error(f"Error handling background scan completion: {e}")
            self._background_scan_in_progress = False
    
    def _silent_scan_for_startup(self, ports: List[str]):
        """Perform silent port scanning for startup without showing progress dialog"""
        try:
            logger.info("Starting silent port scan for auto-connect...")
            
            # Create scanner thread
            self.scanner_thread = PortScannerThread(ports)
            
            # Connect finished signal directly without progress dialog
            self.scanner_thread.finished.connect(self._on_silent_scan_finished)
            
            # Start scanning
            self.scanner_thread.start()
            
        except Exception as e:
            logger.error(f"Silent scan error: {e}")
            # Fall back to just updating with unknown ports
            port_info = {port: "Unknown" for port in ports}
            self._update_port_combos(port_info)
    
    def _on_silent_scan_finished(self, port_info: dict):
        """Handle silent scan completion for startup"""
        logger.info(f"Silent scan completed. Found: {port_info}")
        
        # Update cache with results
        current_time = time.time()
        for port, device_type in port_info.items():
            if device_type not in ["Unknown"]:
                self._device_cache[port] = DeviceInfo(port, device_type, current_time)
        
        # Save cache
        self._save_device_cache()
        
        # Update UI
        self._update_port_combos(port_info)
        
        # Auto-connect to first Arduino found
        if self._auto_connect_enabled and not self._startup_scan_done and not self.arduino_connected:
            self._startup_scan_done = True
            
            # Look for Arduino devices
            arduino_ports = []
            for port, device_type in port_info.items():
                if device_type in ["SMT Arduino", "Offroad Arduino", "Arduino"]:
                    arduino_ports.append((port, device_type))
            
            if arduino_ports:
                # Connect to the first Arduino found
                first_arduino = arduino_ports[0]
                port, device_type = first_arduino
                logger.info(f"Auto-connecting to {device_type} on {port} during startup")
                
                # Select the port in the combo box
                for i in range(self.arduino_port_combo.count()):
                    if self.arduino_port_combo.itemText(i).startswith(port + " ("):
                        self.arduino_port_combo.setCurrentIndex(i)
                        break
                
                # Trigger connection
                QTimer.singleShot(100, self.connect_arduino)
    
    def set_auto_connect(self, enabled: bool):
        """Enable or disable auto-connect feature"""
        self._auto_connect_enabled = enabled
        logger.info(f"Auto-connect {'enabled' if enabled else 'disabled'}")
    
    def reset_startup_scan(self):
        """Reset startup scan flag to allow auto-connect again"""
        self._startup_scan_done = False
        logger.info("Startup scan flag reset")

    def full_refresh_ports(self):
        """Full refresh with background scanning"""
        try:
            logger.info("Starting full port refresh with device identification...")
            
            # Get list of ports
            temp_serial = SerialManager()
            ports = temp_serial.get_available_ports()
            
            if not ports:
                QMessageBox.information(self, "No Ports", "No serial ports found.")
                return
            
            # Filter out already connected ports
            ports_to_scan = []
            port_info = {}
            
            for port in ports:
                if self.arduino_connected and self.arduino_port == port:
                    port_info[port] = "Connected Arduino"
                elif self.scale_connected and self.scale_port == port:
                    port_info[port] = "Connected Scale"
                else:
                    ports_to_scan.append(port)
            
            if not ports_to_scan:
                # All ports are connected, just update UI
                self._update_port_combos(port_info)
                return
            
            # Create progress dialog
            progress = QProgressDialog("Scanning serial ports...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            
            # Create and start scanner thread
            self.scanner_thread = PortScannerThread(ports_to_scan)
            
            # Connect signals
            self.scanner_thread.progress.connect(
                lambda value, msg: (progress.setValue(value), progress.setLabelText(msg))
            )
            self.scanner_thread.finished.connect(
                lambda scanned_info: self._on_scan_finished(port_info | scanned_info, progress)
            )
            progress.canceled.connect(self.scanner_thread.stop)
            
            # Start scanning
            self.scanner_thread.start()
            
        except Exception as e:
            logger.error(f"Full refresh error: {e}")
            QMessageBox.warning(self, "Error", f"Could not refresh ports: {e}")

    def _on_scan_finished(self, port_info: dict, progress_dialog):
        """Handle scan completion"""
        progress_dialog.close()
        
        # Update cache with new results
        current_time = time.time()
        for port, device_type in port_info.items():
            if device_type not in ["Connected Arduino", "Connected Scale", "Unknown"]:
                self._device_cache[port] = DeviceInfo(port, device_type, current_time)
        
        # Save cache
        self._save_device_cache()
        
        # Update UI
        self._update_port_combos(port_info)
        logger.info(f"Full refresh completed. Found: {port_info}")
        
        # Auto-connect to first Arduino found during startup
        if self._auto_connect_enabled and not self._startup_scan_done and not self.arduino_connected:
            self._startup_scan_done = True
            
            # Look for Arduino devices in the scanned ports
            arduino_ports = []
            for port, device_type in port_info.items():
                if device_type in ["SMT Arduino", "Offroad Arduino", "Arduino"]:
                    arduino_ports.append((port, device_type))
            
            if arduino_ports:
                # Connect to the first Arduino found
                first_arduino = arduino_ports[0]
                port, device_type = first_arduino
                logger.info(f"Auto-connecting to {device_type} on {port} during startup")
                
                # Select the port in the combo box
                for i in range(self.arduino_port_combo.count()):
                    if self.arduino_port_combo.itemText(i).startswith(port + " ("):
                        self.arduino_port_combo.setCurrentIndex(i)
                        break
                
                # Trigger connection
                QTimer.singleShot(100, self.connect_arduino)

    def _update_port_combos(self, port_info: dict):
        """Update combo boxes with port information"""
        # Get current selections
        current_arduino = self.arduino_port_combo.currentText()
        current_scale = self.scale_port_combo.currentText()
        
        # Extract just the port name if it has device type
        if ' (' in current_arduino:
            current_arduino = current_arduino.split(' (')[0]
        if ' (' in current_scale:
            current_scale = current_scale.split(' (')[0]

        # Create display strings with device types
        arduino_items = []
        scale_items = []
        
        # Sort ports for consistent ordering
        sorted_ports = sorted(port_info.keys())
        
        # Group ports by device type
        arduino_ports = []
        scale_ports = []
        unknown_ports = []
        
        for port in sorted_ports:
            device_type = port_info.get(port, "Unknown")
            display_name = f"{port} ({device_type})"
            
            if "Arduino" in device_type:
                arduino_ports.append(display_name)
            elif device_type == "Scale":
                scale_ports.append(display_name)
            else:
                unknown_ports.append(display_name)
        
        # Build combo lists with appropriate devices first
        arduino_items = arduino_ports + scale_ports + unknown_ports
        scale_items = scale_ports + arduino_ports + unknown_ports

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

    def _load_device_cache(self):
        """Load device cache from file"""
        try:
            if self.CACHE_FILE.exists():
                with open(self.CACHE_FILE, 'r') as f:
                    cache_data = json.load(f)
                    for port, info in cache_data.items():
                        self._device_cache[port] = DeviceInfo(**info)
                logger.debug(f"Loaded device cache with {len(self._device_cache)} entries")
        except Exception as e:
            logger.debug(f"Could not load device cache: {e}")

    def _save_device_cache(self):
        """Save device cache to file"""
        try:
            self.CACHE_FILE.parent.mkdir(exist_ok=True)
            
            # Convert to serializable format
            cache_data = {
                port: asdict(info) 
                for port, info in self._device_cache.items()
            }
            
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(cache_data, f, indent=2)
            logger.debug(f"Saved device cache with {len(cache_data)} entries")
        except Exception as e:
            logger.debug(f"Could not save device cache: {e}")

    def closeEvent(self, event):
        """Handle dialog close event"""
        # Stop scanner thread if running
        if self.scanner_thread and self.scanner_thread.isRunning():
            self.scanner_thread.stop()
            self.scanner_thread.wait()
        super().closeEvent(event)

    # Keep all existing connection methods unchanged...
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
            # Use factory to create appropriate controller based on mode
            current_mode = self.parent().current_mode
            
            # Create Arduino instance if it doesn't exist
            if not self.parent().arduino_controller:
                from src.hardware.controller_factory import ArduinoControllerFactory
                self.parent().arduino_controller = ArduinoControllerFactory.create_controller(
                    current_mode, baud_rate=115200
                )
            
            arduino = self.parent().arduino_controller
            
            if arduino.connect(port):
                # Connection successful - communication already verified by connect()
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
                
                # For SMT, reading thread should already be started by the controller during connect()
                # Just verify it's running
                if firmware_type == "SMT" and hasattr(arduino, 'is_reading'):
                    if arduino.is_reading:
                        logger.info("Arduino reading loop already running for SMT event handling")
                    else:
                        logger.warning("Arduino reading loop not running - starting now")
                        arduino.start_reading()
                
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
                
                # Set up button callback for SMT mode (reading thread already running)
                if current_mode == "SMT" and hasattr(self.parent(), 'smt_handler'):
                    logger.info("Setting up physical button callback for SMT mode")
                    arduino.set_button_callback(self.parent().smt_handler.handle_button_event)
                    
                    # Check initial button state (reading thread is already handling events)
                    try:
                        initial_state = arduino.get_button_status()
                        if initial_state:
                            logger.info(f"Initial button state: {initial_state}")
                            # Only trigger test if button is currently pressed
                            if initial_state == "PRESSED":
                                logger.info("Button is pressed at startup - triggering initial test")
                                self.parent().smt_handler.handle_button_event(initial_state)
                    except Exception as e:
                        logger.warning(f"Could not get initial button state: {e}")
                
                # Connection successful!
                self.arduino_connected = True
                self.arduino_port = port
                
                
                self.arduino_status_label.setText(f"Status: Connected ({port}) - {firmware_type}")
                self.arduino_status_label.setStyleSheet("color: green; font-weight: bold;")
                self.arduino_connect_btn.setText("Disconnect")
                logger.info(f"Successfully connected to {firmware_type} Arduino on {port}.")
                
                # Update main window connection status
                if hasattr(self.parent(), 'connection_handler'):
                    self.parent().connection_handler.update_connection_status()
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
                # Clear button callback
                self.parent().arduino_controller.set_button_callback(None)
                # Disconnect will handle stopping the reading thread after sending exit command
                self.parent().arduino_controller.disconnect()
                self.parent().arduino_controller = None
        except Exception as e:
            logger.error(f"Error disconnecting Arduino: {e}")
        
        self.arduino_connected = False
        self.arduino_port = None
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
                # Connection successful - communication already verified
                # Keep the connection alive and store it for reuse
                self.parent().scale_controller = scale
                
                self.scale_connected = True
                self.scale_port = port
                self.scale_status_label.setText(f"Status: Connected ({port})")
                self.scale_status_label.setStyleSheet("color: green; font-weight: bold;")
                self.scale_connect_btn.setText("Disconnect")
                logger.info(f"Successfully connected to Scale on {port}.")
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
            'scale_connected': self.scale_connected,
            'scale_port': self.scale_port
        }
        logger.debug(f"Returning connection status: {status}")
        return status