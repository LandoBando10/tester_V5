# gui/components/config/sku_editor.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, 
    QTextEdit, QLabel, QGroupBox, QFrame
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QFont

from typing import Dict, Any


class SKUEditor(QWidget):
    """Widget for editing basic SKU information"""
    
    data_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sku_data = None
        self.setup_ui()
        self.apply_dark_style()
    
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header_label = QLabel("Basic SKU Information")
        header_label.setFont(QFont("Arial", 14, QFont.Bold))
        header_label.setStyleSheet("color: #ffffff; margin-bottom: 10px;")
        layout.addWidget(header_label)
        
        # Basic Info Group
        basic_group = QGroupBox("Product Information")
        basic_layout = QFormLayout(basic_group)
        basic_layout.setSpacing(15)
        
        # SKU ID (read-only)
        self.sku_id_edit = QLineEdit()
        self.sku_id_edit.setReadOnly(True)
        self.sku_id_edit.setStyleSheet("background-color: #2a2a2a; color: #888888;")
        basic_layout.addRow("SKU ID:", self.sku_id_edit)
        
        # Description
        self.description_edit = QLineEdit()
        self.description_edit.textChanged.connect(lambda: self.data_changed.emit())
        basic_layout.addRow("Description:", self.description_edit)
        
        # Pod Type Reference
        self.pod_type_combo = QComboBox()
        self.pod_type_combo.addItems(["C1", "C2", "SS3"])
        self.pod_type_combo.currentTextChanged.connect(lambda: self.data_changed.emit())
        basic_layout.addRow("Pod Type:", self.pod_type_combo)
        
        # Power Level Reference
        self.power_level_combo = QComboBox()
        self.power_level_combo.addItems(["Sport", "Pro", "Max"])
        self.power_level_combo.currentTextChanged.connect(lambda: self.data_changed.emit())
        basic_layout.addRow("Power Level:", self.power_level_combo)
        
        layout.addWidget(basic_group)
        
        # Backlight Configuration Group
        backlight_group = QGroupBox("Backlight Configuration")
        backlight_layout = QFormLayout(backlight_group)
        backlight_layout.setSpacing(15)
        
        # Backlight Type
        self.backlight_type_combo = QComboBox()
        self.backlight_type_combo.addItems(["single", "dual", "rgbw_cycling"])
        self.backlight_type_combo.currentTextChanged.connect(self.on_backlight_type_changed)
        backlight_layout.addRow("Backlight Type:", self.backlight_type_combo)
        
        # Relay Pins
        self.relay_pins_edit = QLineEdit()
        self.relay_pins_edit.setPlaceholderText("e.g., 3 or 3,4")
        self.relay_pins_edit.textChanged.connect(lambda: self.data_changed.emit())
        backlight_layout.addRow("Relay Pins:", self.relay_pins_edit)
        
        # Test Duration
        self.test_duration_edit = QLineEdit()
        self.test_duration_edit.setPlaceholderText("500")
        self.test_duration_edit.textChanged.connect(lambda: self.data_changed.emit())
        backlight_layout.addRow("Test Duration (ms):", self.test_duration_edit)
        
        # RGBW Specific Controls (initially hidden)
        self.rgbw_frame = QFrame()
        rgbw_layout = QFormLayout(self.rgbw_frame)
        
        self.cycle_interval_edit = QLineEdit()
        self.cycle_interval_edit.setPlaceholderText("800")
        self.cycle_interval_edit.textChanged.connect(lambda: self.data_changed.emit())
        rgbw_layout.addRow("Cycle Interval (ms):", self.cycle_interval_edit)
        
        self.total_cycles_edit = QLineEdit()
        self.total_cycles_edit.setPlaceholderText("8")
        self.total_cycles_edit.textChanged.connect(lambda: self.data_changed.emit())
        rgbw_layout.addRow("Total Cycles:", self.total_cycles_edit)
        
        self.stabilization_edit = QLineEdit()
        self.stabilization_edit.setPlaceholderText("150")
        self.stabilization_edit.textChanged.connect(lambda: self.data_changed.emit())
        rgbw_layout.addRow("Stabilization (ms):", self.stabilization_edit)
        
        backlight_layout.addRow(self.rgbw_frame)
        self.rgbw_frame.hide()
        
        layout.addWidget(backlight_group)
        
        # Notes section
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(100)
        self.notes_edit.setPlaceholderText("Additional notes about this SKU configuration...")
        self.notes_edit.textChanged.connect(lambda: self.data_changed.emit())
        notes_layout.addWidget(self.notes_edit)
        
        layout.addWidget(notes_group)
        
        layout.addStretch()
    
    def on_backlight_type_changed(self):
        """Handle backlight type change"""
        backlight_type = self.backlight_type_combo.currentText()
        
        if backlight_type == "rgbw_cycling":
            self.rgbw_frame.show()
        else:
            self.rgbw_frame.hide()
        
        self.data_changed.emit()
    
    def load_sku_data(self, sku_data: Dict[str, Any]):
        """Load SKU data into the interface"""
        self.sku_data = sku_data
        
        # Load basic information
        self.sku_id_edit.setText(sku_data.get('sku', ''))
        self.description_edit.setText(sku_data.get('description', ''))
        
        # Load pod type and power level
        pod_type = sku_data.get('pod_type_ref', 'C1')
        if pod_type in [self.pod_type_combo.itemText(i) for i in range(self.pod_type_combo.count())]:
            self.pod_type_combo.setCurrentText(pod_type)
        
        power_level = sku_data.get('power_level_ref', 'Sport')
        if power_level in [self.power_level_combo.itemText(i) for i in range(self.power_level_combo.count())]:
            self.power_level_combo.setCurrentText(power_level)
        
        # Load backlight configuration
        backlight_config = sku_data.get('backlight_config', {})
        if backlight_config:
            self.backlight_type_combo.setCurrentText(backlight_config.get('type', 'single'))
            
            # Load relay pins
            relay_pins = backlight_config.get('relay_pins', [])
            if relay_pins:
                self.relay_pins_edit.setText(','.join(map(str, relay_pins)))
            
            # Load test duration
            test_duration = backlight_config.get('test_duration_ms', 500)
            self.test_duration_edit.setText(str(test_duration))
            
            # Load RGBW specific settings
            if backlight_config.get('type') == 'rgbw_cycling':
                self.cycle_interval_edit.setText(str(backlight_config.get('cycle_interval_ms', 800)))
                self.total_cycles_edit.setText(str(backlight_config.get('total_cycles', 8)))
                self.stabilization_edit.setText(str(backlight_config.get('stabilization_ms', 150)))
        
        # Clear notes field (no notes field in current schema)
        self.notes_edit.clear()
        
        # Trigger backlight type change to show/hide RGBW controls
        self.on_backlight_type_changed()
    
    def save_to_sku_data(self, sku_data: Dict[str, Any]):
        """Save current data to SKU data dictionary"""
        # Save basic information
        sku_data['description'] = self.description_edit.text()
        sku_data['pod_type_ref'] = self.pod_type_combo.currentText()
        sku_data['power_level_ref'] = self.power_level_combo.currentText()
        
        # Save backlight configuration
        backlight_config = {
            'type': self.backlight_type_combo.currentText(),
            'test_duration_ms': int(self.test_duration_edit.text()) if self.test_duration_edit.text().isdigit() else 500
        }
        
        # Parse relay pins
        relay_pins_text = self.relay_pins_edit.text().strip()
        if relay_pins_text:
            try:
                relay_pins = [int(pin.strip()) for pin in relay_pins_text.split(',') if pin.strip().isdigit()]
                backlight_config['relay_pins'] = relay_pins
            except ValueError:
                backlight_config['relay_pins'] = [3]  # Default
        else:
            backlight_config['relay_pins'] = [3]  # Default
        
        # Add RGBW specific settings if applicable
        if backlight_config['type'] == 'rgbw_cycling':
            try:
                backlight_config['cycle_interval_ms'] = int(self.cycle_interval_edit.text()) if self.cycle_interval_edit.text().isdigit() else 800
                backlight_config['total_cycles'] = int(self.total_cycles_edit.text()) if self.total_cycles_edit.text().isdigit() else 8
                backlight_config['stabilization_ms'] = int(self.stabilization_edit.text()) if self.stabilization_edit.text().isdigit() else 150
                
                # Add default color configuration for RGBW
                backlight_config['colors_to_test'] = [
                    {"name": "red", "target_x": 0.650, "target_y": 0.330, "tolerance": 0.020},
                    {"name": "green", "target_x": 0.300, "target_y": 0.600, "tolerance": 0.020},
                    {"name": "blue", "target_x": 0.150, "target_y": 0.060, "tolerance": 0.020},
                    {"name": "white", "target_x": 0.313, "target_y": 0.329, "tolerance": 0.020}
                ]
                backlight_config['sample_points_ms'] = [200, 350, 450]
            except ValueError:
                # Use defaults if conversion fails
                pass
        
        sku_data['backlight_config'] = backlight_config
    
    def apply_dark_style(self):
        """Apply dark theme styling"""
        self.setStyleSheet("""
            QWidget {
                background-color: #333333;
                color: white;
            }
            
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #3a3a3a;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #4a90a4;
                font-size: 12px;
            }
            
            QLineEdit {
                background-color: #2b2b2b;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px;
                color: white;
                font-size: 11px;
            }
            
            QLineEdit:focus {
                border: 1px solid #4a90a4;
            }
            
            QComboBox {
                background-color: #2b2b2b;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px;
                color: white;
                font-size: 11px;
                min-width: 120px;
            }
            
            QComboBox:focus {
                border: 1px solid #4a90a4;
            }
            
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            
            QComboBox::down-arrow {
                width: 10px;
                height: 10px;
                border: 1px solid #666666;
                border-radius: 2px;
                background-color: #555555;
            }
            
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                border: 1px solid #555555;
                selection-background-color: #4a90a4;
                color: white;
            }
            
            QTextEdit {
                background-color: #2b2b2b;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 8px;
                color: white;
                font-size: 11px;
            }
            
            QTextEdit:focus {
                border: 1px solid #4a90a4;
            }
            
            QLabel {
                color: #cccccc;
                font-size: 11px;
            }
            
            QFormLayout QLabel {
                font-weight: normal;
                min-width: 140px;
            }
            
            QFrame {
                border: none;
                background-color: transparent;
            }
        """)
