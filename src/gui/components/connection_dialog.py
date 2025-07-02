"""Refactored connection dialog using services for business logic."""

import logging
from typing import Dict, Any, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QGridLayout, QLabel, QComboBox, QPushButton, 
    QDialogButtonBox, QMessageBox, QProgressDialog
)
from PySide6.QtCore import Qt, Signal, Slot

from src.services.connection_service import ConnectionService
from src.services.port_scanner_service import PortScannerService
from src.services.device_cache_service import DeviceCacheService

logger = logging.getLogger(__name__)


class ConnectionDialog(QDialog):
    """Dialog for managing hardware connections."""
    
    # Signals
    connections_changed = Signal(dict)  # Emitted when connections change
    
    def __init__(self, parent=None, connection_service: Optional[ConnectionService] = None):
        """Initialize the connection dialog.
        
        Args:
            parent: Parent widget
            connection_service: Optional existing connection service
        """
        super().__init__(parent)
        
        # Services
        self.connection_service = connection_service or ConnectionService()
        self.port_scanner = PortScannerService()
        self.cache_service = self.connection_service.cache_service
        
        # UI elements
        self.arduino_combo = None
        self.arduino_status = None
        self.scale_combo = None
        self.scale_status = None
        
        # Setup
        self._setup_ui()
        self._connect_signals()
        self._load_initial_state()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle("Hardware Connections")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout(self)
        
        # Arduino section
        arduino_group = self._create_arduino_group()
        layout.addWidget(arduino_group)
        
        # Scale section
        scale_group = self._create_scale_group()
        layout.addWidget(scale_group)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.close)
        layout.addWidget(button_box)
    
    def _create_arduino_group(self) -> QGroupBox:
        """Create Arduino connection group."""
        group = QGroupBox("Arduino Connection")
        layout = QGridLayout()
        
        # Port selection
        layout.addWidget(QLabel("Port:"), 0, 0)
        self.arduino_combo = QComboBox()
        self.arduino_combo.setMinimumWidth(200)
        self.arduino_combo.currentIndexChanged.connect(self._on_arduino_port_changed)
        layout.addWidget(self.arduino_combo, 0, 1)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_ports)
        layout.addWidget(refresh_btn, 0, 2)
        
        # Status
        layout.addWidget(QLabel("Status:"), 1, 0)
        self.arduino_status = QLabel("Not connected")
        layout.addWidget(self.arduino_status, 1, 1, 1, 2)
        
        # Connect/Disconnect buttons
        btn_layout = QHBoxLayout()
        
        self.arduino_connect_btn = QPushButton("Connect")
        self.arduino_connect_btn.clicked.connect(self._connect_arduino)
        btn_layout.addWidget(self.arduino_connect_btn)
        
        self.arduino_disconnect_btn = QPushButton("Disconnect")
        self.arduino_disconnect_btn.clicked.connect(self._disconnect_arduino)
        self.arduino_disconnect_btn.setEnabled(False)
        btn_layout.addWidget(self.arduino_disconnect_btn)
        
        layout.addLayout(btn_layout, 2, 1, 1, 2)
        
        group.setLayout(layout)
        return group
    
    def _create_scale_group(self) -> QGroupBox:
        """Create scale connection group."""
        group = QGroupBox("Scale Connection")
        layout = QGridLayout()
        
        # Port selection
        layout.addWidget(QLabel("Port:"), 0, 0)
        self.scale_combo = QComboBox()
        self.scale_combo.setMinimumWidth(200)
        self.scale_combo.currentIndexChanged.connect(self._on_scale_port_changed)
        layout.addWidget(self.scale_combo, 0, 1)
        
        # Status
        layout.addWidget(QLabel("Status:"), 1, 0)
        self.scale_status = QLabel("Not connected")
        layout.addWidget(self.scale_status, 1, 1)
        
        # Connect/Disconnect buttons
        btn_layout = QHBoxLayout()
        
        self.scale_connect_btn = QPushButton("Connect")
        self.scale_connect_btn.clicked.connect(self._connect_scale)
        btn_layout.addWidget(self.scale_connect_btn)
        
        self.scale_disconnect_btn = QPushButton("Disconnect")
        self.scale_disconnect_btn.clicked.connect(self._disconnect_scale)
        self.scale_disconnect_btn.setEnabled(False)
        btn_layout.addWidget(self.scale_disconnect_btn)
        
        layout.addLayout(btn_layout, 2, 1)
        
        group.setLayout(layout)
        return group
    
    def _connect_signals(self):
        """Connect service signals to UI updates."""
        self.connection_service.arduino_connection_changed.connect(self._on_arduino_connection_changed)
        self.connection_service.scale_connection_changed.connect(self._on_scale_connection_changed)
        self.connection_service.connection_error.connect(self._on_connection_error)
    
    def _load_initial_state(self):
        """Load initial connection state and available ports."""
        # Get current connection status
        status = self.connection_service.get_connection_status()
        
        # Immediately populate dropdowns with all available ports
        # Do this BEFORE updating connection status UI
        self._populate_all_ports()
        
        # Update UI based on current state
        if status['arduino_connected']:
            self._on_arduino_connection_changed(True, status['arduino_port'])
        
        if status['scale_connected']:
            self._on_scale_connection_changed(True, status['scale_port'])
        
        # Then do async device identification
        self._refresh_ports()
    
    def _populate_all_ports(self):
        """Immediately populate dropdowns with all available ports."""
        logger.info("Populating all available ports...")
        
        # Get all available ports
        all_ports = self.port_scanner.get_available_ports()
        logger.info(f"Found {len(all_ports)} total ports for immediate display: {all_ports}")
        
        # Get current connection status
        status = self.connection_service.get_connection_status()
        connected_arduino = status.get('arduino_port') if status.get('arduino_connected') else None
        connected_scale = status.get('scale_port') if status.get('scale_connected') else None
        
        # Clear and populate combos immediately with ALL ports
        self.arduino_combo.clear()
        self.scale_combo.clear()
        
        # Add placeholder
        self.arduino_combo.addItem("-- Select Port --", None)
        self.scale_combo.addItem("-- Select Port --", None)
        
        # Add all ports to both combos immediately
        for port in all_ports:
            # For Arduino combo
            if port == connected_arduino:
                self.arduino_combo.addItem(f"{port} - Arduino (Connected)", port)
            else:
                self.arduino_combo.addItem(f"{port} - Unknown Device", port)
            
            # For scale combo
            if port == connected_scale:
                self.scale_combo.addItem(f"{port} - Scale (Connected)", port)
            else:
                self.scale_combo.addItem(f"{port} - Unknown Device", port)
        
        # Select currently connected ports if any
        if connected_arduino:
            index = self.arduino_combo.findData(connected_arduino)
            if index >= 0:
                self.arduino_combo.setCurrentIndex(index)
                logger.info(f"Selected connected Arduino on {connected_arduino} at index {index}")
            else:
                logger.warning(f"Connected Arduino port {connected_arduino} not found in combo box")
        else:
            # No connected Arduino, ensure placeholder is selected
            self.arduino_combo.setCurrentIndex(0)  # "-- Select Port --"
        
        if connected_scale:
            index = self.scale_combo.findData(connected_scale)
            if index >= 0:
                self.scale_combo.setCurrentIndex(index)
                logger.info(f"Selected connected Scale on {connected_scale} at index {index}")
            else:
                logger.warning(f"Connected Scale port {connected_scale} not found in combo box")
        else:
            # No connected scale, ensure placeholder is selected
            self.scale_combo.setCurrentIndex(0)  # "-- Select Port --"
        
        logger.info(f"Populated dropdowns with {len(all_ports)} ports")
    
    @Slot()
    def _refresh_ports(self):
        """Refresh port device identification (async)."""
        logger.info("Starting async port device identification...")
        
        # Get all available ports
        all_ports = self.port_scanner.get_available_ports()
        logger.info(f"Found {len(all_ports)} total ports: {all_ports}")
        
        # Get current connection status for reference
        status = self.connection_service.get_connection_status()
        connected_arduino_port = status.get('arduino_port') if status.get('arduino_connected') else None
        connected_scale_port = status.get('scale_port') if status.get('scale_connected') else None
        logger.info(f"Connected Arduino: {connected_arduino_port}, Connected Scale: {connected_scale_port}")
        
        # Don't exclude any ports - we want to identify all devices
        # The port scanner will skip ports that are in use anyway
        logger.info(f"Starting async scan of all {len(all_ports)} ports for device identification")
        worker = self.port_scanner.scan_ports_async(all_ports)
        
        def on_progress(msg: str):
            logger.debug(f"Port scan progress: {msg}")
        
        def on_complete(devices):
            logger.info(f"Device identification complete. Identified {len(devices)} devices")
            
            # For any connected ports that weren't in the scan results, 
            # do a special check to get their info
            if connected_arduino_port and not any(d.port == connected_arduino_port for d in devices):
                logger.info(f"Connected Arduino port {connected_arduino_port} not in scan results, checking with cache")
                device_info = self.port_scanner.probe_port(connected_arduino_port, check_in_use=True)
                if device_info:
                    devices.append(device_info)
            
            if connected_scale_port and not any(d.port == connected_scale_port for d in devices):
                logger.info(f"Connected Scale port {connected_scale_port} not in scan results, checking with cache")
                device_info = self.port_scanner.probe_port(connected_scale_port, check_in_use=True)
                if device_info:
                    devices.append(device_info)
            
            # Update combo descriptions with identified devices
            self._update_device_descriptions(devices)
        
        worker.progress.connect(on_progress)
        worker.scan_complete.connect(on_complete)
        worker.start()
    
    def _update_device_descriptions(self, devices):
        """Update device descriptions in combo boxes without clearing them."""
        logger.info(f"Updating device descriptions for {len(devices)} identified devices")
        
        # Get current connection status
        status = self.connection_service.get_connection_status()
        connected_arduino = status.get('arduino_port') if status.get('arduino_connected') else None
        connected_scale = status.get('scale_port') if status.get('scale_connected') else None
        
        # Create a map of port to device info
        device_map = {device.port: device for device in devices}
        
        # Update Arduino combo descriptions
        for i in range(self.arduino_combo.count()):
            port = self.arduino_combo.itemData(i)
            if port and port in device_map:
                device = device_map[port]
                if port == connected_arduino:
                    text = f"{port} - {device.description} (Connected)"
                else:
                    text = f"{port} - {device.description}"
                self.arduino_combo.setItemText(i, text)
            elif port == connected_arduino:
                # Connected but not identified in scan (might be in use)
                text = f"{port} - Arduino (Connected)"
                self.arduino_combo.setItemText(i, text)
        
        # Update Scale combo descriptions
        for i in range(self.scale_combo.count()):
            port = self.scale_combo.itemData(i)
            if port and port in device_map:
                device = device_map[port]
                if port == connected_scale:
                    text = f"{port} - {device.description} (Connected)"
                else:
                    text = f"{port} - {device.description}"
                self.scale_combo.setItemText(i, text)
            elif port == connected_scale:
                # Connected but not identified in scan (might be in use)
                text = f"{port} - Scale (Connected)"
                self.scale_combo.setItemText(i, text)
        
        logger.info("Device descriptions updated")
    
    def _update_port_combos(self, devices):
        """Legacy method - redirects to new update method."""
        # This method might be called from other places
        # Redirect to the new non-destructive update method
        self._update_device_descriptions(devices)
        return
        
        # OLD CODE BELOW (kept for reference but not executed)
        # Clear existing items
        self.arduino_combo.clear()
        self.scale_combo.clear()
        
        # Add placeholder
        self.arduino_combo.addItem("-- Select Port --", None)
        self.scale_combo.addItem("-- Select Port --", None)
        
        # Sort devices by type
        arduino_devices = []
        scale_devices = []
        unknown_devices = []
        
        for device in devices:
            if device.device_type == 'Arduino':
                arduino_devices.append(device)
            elif device.device_type == 'Scale':
                scale_devices.append(device)
            else:
                unknown_devices.append(device)
        
        # Add Arduino devices first
        for device in arduino_devices:
            # Check if this is the currently connected port
            is_connected = device.port == self.connection_service.get_connection_status().get('arduino_port')
            display_text = f"{device.port} - {device.description}"
            if is_connected and "(Connected)" not in device.description:
                display_text += " (Connected)"
            self.arduino_combo.addItem(display_text, device.port)
        
        # Add unknown devices to Arduino list
        for device in unknown_devices:
            self.arduino_combo.addItem(
                f"{device.port} - Unknown Device",
                device.port
            )
        
        # Add scale devices to scale combo
        for device in scale_devices:
            self.scale_combo.addItem(
                f"{device.port} - {device.description}",
                device.port
            )
        
        # Add all devices to scale combo as fallback
        for device in devices:
            if device.device_type != 'Scale':
                self.scale_combo.addItem(
                    f"{device.port} - {device.description}",
                    device.port
                )
        
        # Select currently connected ports
        status = self.connection_service.get_connection_status()
        if status.get('arduino_connected'):
            index = self.arduino_combo.findData(status.get('arduino_port'))
            if index >= 0:
                self.arduino_combo.setCurrentIndex(index)
        
        if status.get('scale_connected'):
            index = self.scale_combo.findData(status.get('scale_port'))
            if index >= 0:
                self.scale_combo.setCurrentIndex(index)
    
    @Slot()
    def _connect_arduino(self):
        """Connect to selected Arduino port."""
        port = self.arduino_combo.currentData()
        if not port:
            QMessageBox.warning(self, "No Port Selected", "Please select a port first.")
            return
        
        # Update UI
        self.arduino_status.setText("Connecting...")
        self.arduino_connect_btn.setEnabled(False)
        
        # Connect through service
        result = self.connection_service.connect_arduino(port)
        
        if not result.success:
            QMessageBox.critical(self, "Connection Failed", result.error or "Unknown error")
            self.arduino_status.setText("Connection failed")
            self.arduino_connect_btn.setEnabled(True)
    
    @Slot()
    def _disconnect_arduino(self):
        """Disconnect from Arduino."""
        self.connection_service.disconnect_arduino()
    
    @Slot()
    def _connect_scale(self):
        """Connect to selected scale port."""
        port = self.scale_combo.currentData()
        if not port:
            QMessageBox.warning(self, "No Port Selected", "Please select a port first.")
            return
        
        # Update UI
        self.scale_status.setText("Connecting...")
        self.scale_connect_btn.setEnabled(False)
        
        # Connect through service
        result = self.connection_service.connect_scale(port)
        
        if not result.success:
            QMessageBox.critical(self, "Connection Failed", result.error or "Unknown error")
            self.scale_status.setText("Connection failed")
            self.scale_connect_btn.setEnabled(True)
    
    @Slot()
    def _disconnect_scale(self):
        """Disconnect from scale."""
        self.connection_service.disconnect_scale()
    
    @Slot(bool, str)
    def _on_arduino_connection_changed(self, connected: bool, port: str):
        """Handle Arduino connection state changes."""
        if connected:
            status = self.connection_service.get_connection_status()
            firmware = status.get('arduino_firmware', 'Unknown')
            self.arduino_status.setText(f"Connected to {firmware} on {port}")
            self.arduino_connect_btn.setEnabled(False)
            self.arduino_disconnect_btn.setEnabled(True)
            
            # Ensure the connected port is selected in the combo
            index = self.arduino_combo.findData(port)
            if index >= 0 and self.arduino_combo.currentIndex() != index:
                self.arduino_combo.setCurrentIndex(index)
                logger.debug(f"Updated Arduino combo to show connected port {port}")
        else:
            self.arduino_status.setText("Not connected")
            self.arduino_connect_btn.setEnabled(True)
            self.arduino_disconnect_btn.setEnabled(False)
        
        # Emit connections changed signal
        self.connections_changed.emit(self.connection_service.get_connection_status())
    
    @Slot(bool, str)
    def _on_scale_connection_changed(self, connected: bool, port: str):
        """Handle scale connection state changes."""
        if connected:
            self.scale_status.setText(f"Connected on {port}")
            self.scale_connect_btn.setEnabled(False)
            self.scale_disconnect_btn.setEnabled(True)
            
            # Ensure the connected port is selected in the combo
            index = self.scale_combo.findData(port)
            if index >= 0 and self.scale_combo.currentIndex() != index:
                self.scale_combo.setCurrentIndex(index)
                logger.debug(f"Updated Scale combo to show connected port {port}")
        else:
            self.scale_status.setText("Not connected")
            self.scale_connect_btn.setEnabled(True)
            self.scale_disconnect_btn.setEnabled(False)
        
        # Emit connections changed signal
        self.connections_changed.emit(self.connection_service.get_connection_status())
    
    @Slot(str)
    def _on_connection_error(self, error: str):
        """Handle connection errors."""
        logger.error(f"Connection error: {error}")
        # Error dialogs are already shown in connect methods
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status.
        
        Returns:
            Dictionary with connection information
        """
        return self.connection_service.get_connection_status()
    
    @Slot()
    def _on_arduino_port_changed(self):
        """Handle Arduino port selection change."""
        port = self.arduino_combo.currentData()
        logger.debug(f"Arduino port selection changed to: {port}")
        
        if port:
            # Check if this port is already connected
            status = self.connection_service.get_connection_status()
            is_connected = (status.get('arduino_connected') and 
                          status.get('arduino_port') == port)
            
            # Update button states
            self.arduino_connect_btn.setEnabled(not is_connected)
            self.arduino_disconnect_btn.setEnabled(is_connected)
        else:
            # No port selected (placeholder)
            self.arduino_connect_btn.setEnabled(False)
            self.arduino_disconnect_btn.setEnabled(False)
    
    @Slot()
    def _on_scale_port_changed(self):
        """Handle scale port selection change."""
        port = self.scale_combo.currentData()
        logger.debug(f"Scale port selection changed to: {port}")
        
        if port:
            # Check if this port is already connected
            status = self.connection_service.get_connection_status()
            is_connected = (status.get('scale_connected') and 
                          status.get('scale_port') == port)
            
            # Update button states
            self.scale_connect_btn.setEnabled(not is_connected)
            self.scale_disconnect_btn.setEnabled(is_connected)
        else:
            # No port selected (placeholder)
            self.scale_connect_btn.setEnabled(False)
            self.scale_disconnect_btn.setEnabled(False)
    
    def closeEvent(self, event):
        """Handle dialog close event."""
        # Don't disconnect hardware when closing dialog
        # Connections persist until explicitly disconnected
        event.accept()