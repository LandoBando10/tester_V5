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
        
        # Update UI based on current state
        if status['arduino_connected']:
            self._on_arduino_connection_changed(True, status['arduino_port'])
        
        if status['scale_connected']:
            self._on_scale_connection_changed(True, status['scale_port'])
        
        # Load available ports
        self._refresh_ports()
    
    @Slot()
    def _refresh_ports(self):
        """Refresh available ports."""
        # Show progress dialog
        progress = QProgressDialog("Scanning ports...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(500)
        progress.show()
        
        # Start async port scan
        worker = self.port_scanner.scan_ports_async()
        
        def on_progress(msg: str):
            progress.setLabelText(msg)
        
        def on_complete(devices):
            progress.close()
            self._update_port_combos(devices)
        
        worker.progress.connect(on_progress)
        worker.scan_complete.connect(on_complete)
        worker.start()
    
    def _update_port_combos(self, devices):
        """Update port combo boxes with discovered devices."""
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
            self.arduino_combo.addItem(
                f"{device.port} - {device.description}",
                device.port
            )
        
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
    
    def closeEvent(self, event):
        """Handle dialog close event."""
        # Don't disconnect hardware when closing dialog
        # Connections persist until explicitly disconnected
        event.accept()