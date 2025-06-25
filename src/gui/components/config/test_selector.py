# gui/components/config/test_selector.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QCheckBox, QLabel, 
    QFrame, QScrollArea
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

from typing import Dict, Any


class TestSelector(QWidget):
    """Widget for selecting which tests apply to a SKU"""
    
    data_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sku_data = None
        self.setup_ui()
        self.apply_dark_style()
    
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header_label = QLabel("Test Selection")
        header_label.setFont(QFont("Arial", 14, QFont.Bold))
        header_label.setStyleSheet("color: #ffffff; margin-bottom: 10px;")
        layout.addWidget(header_label)
        
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(20)
        
        # Mode Selection
        self.mode_group = self.create_mode_selection_group()
        content_layout.addWidget(self.mode_group)
        
        # Test Parameter Groups
        self.offroad_group = self.create_offroad_test_group()
        content_layout.addWidget(self.offroad_group)
        
        self.smt_group = self.create_smt_test_group()
        content_layout.addWidget(self.smt_group)
        
        self.weight_group = self.create_weight_test_group()
        content_layout.addWidget(self.weight_group)
        
        content_layout.addStretch()
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
    
    def create_mode_selection_group(self) -> QGroupBox:
        """Create mode selection group"""
        group = QGroupBox("Available Test Modes")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        
        # Mode checkboxes
        self.mode_checkboxes = {}
        
        modes = [
            ("Offroad", "Complete product testing including LUX, COLOR, PRESSURE, and CURRENT"),
            ("SMT", "Surface Mount Technology testing with programming support"),
            ("WeightChecking", "Weight validation and tolerance checking")
        ]
        
        for mode, description in modes:
            mode_layout = QVBoxLayout()
            
            checkbox = QCheckBox(mode)
            checkbox.setFont(QFont("Arial", 11, QFont.Bold))
            checkbox.stateChanged.connect(self.on_mode_changed)
            self.mode_checkboxes[mode] = checkbox
            mode_layout.addWidget(checkbox)
            
            desc_label = QLabel(description)
            desc_label.setStyleSheet("color: #cccccc; margin-left: 20px; font-size: 10px;")
            desc_label.setWordWrap(True)
            mode_layout.addWidget(desc_label)
            
            layout.addLayout(mode_layout)
        
        return group
    
    def create_offroad_test_group(self) -> QGroupBox:
        """Create offroad test selection group"""
        group = QGroupBox("Offroad Test Parameters")
        layout = QVBoxLayout(group)
        layout.setSpacing(15)
        
        # Test parameter checkboxes
        self.offroad_tests = {}
        
        # Current testing (NEW)
        current_frame = QFrame()
        current_layout = QVBoxLayout(current_frame)
        
        self.offroad_tests['CURRENT'] = QCheckBox("Current Testing (AMPS)")
        self.offroad_tests['CURRENT'].setFont(QFont("Arial", 10, QFont.Bold))
        self.offroad_tests['CURRENT'].stateChanged.connect(lambda: self.data_changed.emit())
        current_layout.addWidget(self.offroad_tests['CURRENT'])
        
        current_desc = QLabel("Measure mainbeam and backlight current draw")
        current_desc.setStyleSheet("color: #cccccc; margin-left: 20px; font-size: 9px;")
        current_layout.addWidget(current_desc)
        
        layout.addWidget(current_frame)
        
        # LUX testing
        lux_frame = QFrame()
        lux_layout = QVBoxLayout(lux_frame)
        
        self.offroad_tests['LUX'] = QCheckBox("LUX Testing")
        self.offroad_tests['LUX'].setFont(QFont("Arial", 10, QFont.Bold))
        self.offroad_tests['LUX'].stateChanged.connect(lambda: self.data_changed.emit())
        lux_layout.addWidget(self.offroad_tests['LUX'])
        
        lux_desc = QLabel("Measure mainbeam and backlight brightness")
        lux_desc.setStyleSheet("color: #cccccc; margin-left: 20px; font-size: 9px;")
        lux_layout.addWidget(lux_desc)
        
        layout.addWidget(lux_frame)
        
        # COLOR testing
        color_frame = QFrame()
        color_layout = QVBoxLayout(color_frame)
        
        self.offroad_tests['COLOR'] = QCheckBox("COLOR Testing")
        self.offroad_tests['COLOR'].setFont(QFont("Arial", 10, QFont.Bold))
        self.offroad_tests['COLOR'].stateChanged.connect(lambda: self.data_changed.emit())
        color_layout.addWidget(self.offroad_tests['COLOR'])
        
        color_desc = QLabel("Measure color coordinates and validate against specifications")
        color_desc.setStyleSheet("color: #cccccc; margin-left: 20px; font-size: 9px;")
        color_layout.addWidget(color_desc)
        
        layout.addWidget(color_frame)
        
        # PRESSURE testing
        pressure_frame = QFrame()
        pressure_layout = QVBoxLayout(pressure_frame)
        
        self.offroad_tests['PRESSURE'] = QCheckBox("PRESSURE Testing")
        self.offroad_tests['PRESSURE'].setFont(QFont("Arial", 10, QFont.Bold))
        self.offroad_tests['PRESSURE'].stateChanged.connect(lambda: self.data_changed.emit())
        pressure_layout.addWidget(self.offroad_tests['PRESSURE'])
        
        pressure_desc = QLabel("Test pressure seal integrity and tolerances")
        pressure_desc.setStyleSheet("color: #cccccc; margin-left: 20px; font-size: 9px;")
        pressure_layout.addWidget(pressure_desc)
        
        layout.addWidget(pressure_frame)
        
        # Backlight Configuration
        backlight_frame = QFrame()
        backlight_layout = QVBoxLayout(backlight_frame)
        
        self.offroad_tests['BACKLIGHT'] = QCheckBox("Backlight Configuration")
        self.offroad_tests['BACKLIGHT'].setFont(QFont("Arial", 10, QFont.Bold))
        self.offroad_tests['BACKLIGHT'].stateChanged.connect(lambda: self.data_changed.emit())
        backlight_layout.addWidget(self.offroad_tests['BACKLIGHT'])
        
        backlight_desc = QLabel("Configure backlight relay pins and test parameters")
        backlight_desc.setStyleSheet("color: #cccccc; margin-left: 20px; font-size: 9px;")
        backlight_layout.addWidget(backlight_desc)
        
        layout.addWidget(backlight_frame)
        
        return group
    
    def create_smt_test_group(self) -> QGroupBox:
        """Create SMT test selection group"""
        group = QGroupBox("SMT Test Parameters")
        layout = QVBoxLayout(group)
        layout.setSpacing(15)
        
        # Test parameter checkboxes
        self.smt_tests = {}
        
        # Power sequences
        power_frame = QFrame()
        power_layout = QVBoxLayout(power_frame)
        
        self.smt_tests['POWER'] = QCheckBox("Power Sequences")
        self.smt_tests['POWER'].setFont(QFont("Arial", 10, QFont.Bold))
        self.smt_tests['POWER'].stateChanged.connect(lambda: self.data_changed.emit())
        power_layout.addWidget(self.smt_tests['POWER'])
        
        power_desc = QLabel("Execute power test sequences and current validation")
        power_desc.setStyleSheet("color: #cccccc; margin-left: 20px; font-size: 9px;")
        power_layout.addWidget(power_desc)
        
        layout.addWidget(power_frame)
        
        # Programming configuration
        prog_frame = QFrame()
        prog_layout = QVBoxLayout(prog_frame)
        
        self.smt_tests['PROGRAMMING'] = QCheckBox("Programming Configuration")
        self.smt_tests['PROGRAMMING'].setFont(QFont("Arial", 10, QFont.Bold))
        self.smt_tests['PROGRAMMING'].stateChanged.connect(lambda: self.data_changed.emit())
        prog_layout.addWidget(self.smt_tests['PROGRAMMING'])
        
        prog_desc = QLabel("Configure board programming sequences and hex files")
        prog_desc.setStyleSheet("color: #cccccc; margin-left: 20px; font-size: 9px;")
        prog_layout.addWidget(prog_desc)
        
        layout.addWidget(prog_frame)
        
        return group
    
    def create_weight_test_group(self) -> QGroupBox:
        """Create weight test selection group"""
        group = QGroupBox("Weight Testing Parameters")
        layout = QVBoxLayout(group)
        layout.setSpacing(15)
        
        # Test parameter checkboxes
        self.weight_tests = {}
        
        # Weight ranges
        weight_frame = QFrame()
        weight_layout = QVBoxLayout(weight_frame)
        
        self.weight_tests['WEIGHT'] = QCheckBox("Weight Validation")
        self.weight_tests['WEIGHT'].setFont(QFont("Arial", 10, QFont.Bold))
        self.weight_tests['WEIGHT'].stateChanged.connect(lambda: self.data_changed.emit())
        weight_layout.addWidget(self.weight_tests['WEIGHT'])
        
        weight_desc = QLabel("Validate product weight within specified tolerances")
        weight_desc.setStyleSheet("color: #cccccc; margin-left: 20px; font-size: 9px;")
        weight_layout.addWidget(weight_desc)
        
        layout.addWidget(weight_frame)
        
        # Tolerances
        tolerance_frame = QFrame()
        tolerance_layout = QVBoxLayout(tolerance_frame)
        
        self.weight_tests['TOLERANCES'] = QCheckBox("Tolerance Configuration")
        self.weight_tests['TOLERANCES'].setFont(QFont("Arial", 10, QFont.Bold))
        self.weight_tests['TOLERANCES'].stateChanged.connect(lambda: self.data_changed.emit())
        tolerance_layout.addWidget(self.weight_tests['TOLERANCES'])
        
        tolerance_desc = QLabel("Configure weight tolerance ranges and tare values")
        tolerance_desc.setStyleSheet("color: #cccccc; margin-left: 20px; font-size: 9px;")
        tolerance_layout.addWidget(tolerance_desc)
        
        layout.addWidget(tolerance_frame)
        
        return group
    
    def on_mode_changed(self):
        """Handle mode checkbox changes"""
        # Update group visibility based on selected modes
        offroad_enabled = self.mode_checkboxes['Offroad'].isChecked()
        smt_enabled = self.mode_checkboxes['SMT'].isChecked()
        weight_enabled = self.mode_checkboxes['WeightChecking'].isChecked()
        
        self.offroad_group.setEnabled(offroad_enabled)
        self.smt_group.setEnabled(smt_enabled)
        self.weight_group.setEnabled(weight_enabled)
        
        # Auto-check tests when mode is enabled
        if offroad_enabled:
            for test_name, checkbox in self.offroad_tests.items():
                if not checkbox.isChecked():
                    checkbox.setChecked(True)
        
        if smt_enabled:
            for test_name, checkbox in self.smt_tests.items():
                if not checkbox.isChecked():
                    checkbox.setChecked(True)
        
        if weight_enabled:
            for test_name, checkbox in self.weight_tests.items():
                if not checkbox.isChecked():
                    checkbox.setChecked(True)
        
        self.data_changed.emit()
    
    def load_sku_data(self, sku_data: Dict[str, Any]):
        """Load SKU data into the interface"""
        self.sku_data = sku_data
        
        # Load available modes
        available_modes = sku_data.get('available_modes', [])
        
        for mode, checkbox in self.mode_checkboxes.items():
            checkbox.setChecked(mode in available_modes)
        
        # Load offroad test selections
        offroad_params = sku_data.get('offroad_params', {})
        if offroad_params:
            self.offroad_tests['CURRENT'].setChecked('CURRENT' in offroad_params)
            self.offroad_tests['LUX'].setChecked('LUX' in offroad_params)
            self.offroad_tests['COLOR'].setChecked('COLOR' in offroad_params)
            self.offroad_tests['PRESSURE'].setChecked('PRESSURE' in offroad_params)
            self.offroad_tests['BACKLIGHT'].setChecked('backlight_config' in sku_data)
        else:
            for checkbox in self.offroad_tests.values():
                checkbox.setChecked(False)
        
        # Load SMT test selections
        smt_params = sku_data.get('smt_params', {})
        if smt_params:
            self.smt_tests['POWER'].setChecked('POWER' in smt_params)
            # Programming is checked separately from config
            self.smt_tests['PROGRAMMING'].setChecked(True)  # Default if SMT is available
        else:
            for checkbox in self.smt_tests.values():
                checkbox.setChecked(False)
        
        # Load weight test selections
        weight_params = sku_data.get('weightchecking_params', {})
        if weight_params:
            self.weight_tests['WEIGHT'].setChecked('WEIGHT' in weight_params)
            self.weight_tests['TOLERANCES'].setChecked(True)  # Always if weight checking enabled
        else:
            for checkbox in self.weight_tests.values():
                checkbox.setChecked(False)
        
        # Update group states
        self.on_mode_changed()
    
    def save_to_sku_data(self, sku_data: Dict[str, Any]):
        """Save current selections to SKU data"""
        # Update available modes
        available_modes = []
        for mode, checkbox in self.mode_checkboxes.items():
            if checkbox.isChecked():
                available_modes.append(mode)
        
        sku_data['available_modes'] = available_modes
        
        # Handle offroad parameters
        if self.mode_checkboxes['Offroad'].isChecked():
            if 'offroad_params' not in sku_data:
                sku_data['offroad_params'] = {}
            
            offroad_params = sku_data['offroad_params']
            
            # Remove unchecked test parameters
            if not self.offroad_tests['CURRENT'].isChecked() and 'CURRENT' in offroad_params:
                del offroad_params['CURRENT']
            if not self.offroad_tests['LUX'].isChecked() and 'LUX' in offroad_params:
                del offroad_params['LUX']
            if not self.offroad_tests['COLOR'].isChecked() and 'COLOR' in offroad_params:
                del offroad_params['COLOR']
            if not self.offroad_tests['PRESSURE'].isChecked() and 'PRESSURE' in offroad_params:
                del offroad_params['PRESSURE']
            
            # Add default parameters for checked tests that don't exist
            if self.offroad_tests['CURRENT'].isChecked() and 'CURRENT' not in offroad_params:
                offroad_params['CURRENT'] = {
                    "min_mainbeam_current_A": 0.5,
                    "max_mainbeam_current_A": 0.8
                }
            
            if self.offroad_tests['LUX'].isChecked() and 'LUX' not in offroad_params:
                offroad_params['LUX'] = {
                    "min_mainbeam_lux": 1000,
                    "max_mainbeam_lux": 1500
                }
            
            if self.offroad_tests['COLOR'].isChecked() and 'COLOR' not in offroad_params:
                offroad_params['COLOR'] = {
                    "center_x_main": 0.450,
                    "center_y_main": 0.410,
                    "radius_x_main": 0.015,
                    "radius_y_main": 0.015,
                    "angle_deg_main": 0
                }
            
            # Handle backlight configuration
            if not self.offroad_tests['BACKLIGHT'].isChecked():
                if 'backlight_config' in sku_data:
                    del sku_data['backlight_config']
            elif 'backlight_config' not in sku_data:
                sku_data['backlight_config'] = {
                    "type": "single",
                    "relay_pins": [3],
                    "test_duration_ms": 500
                }
        else:
            sku_data['offroad_params'] = None
            if 'backlight_config' in sku_data:
                del sku_data['backlight_config']
        
        # Handle SMT parameters
        if self.mode_checkboxes['SMT'].isChecked():
            if 'smt_params' not in sku_data or sku_data['smt_params'] is None:
                sku_data['smt_params'] = {}
            
            smt_params = sku_data['smt_params']
            
            # Add default POWER parameters if checked
            if self.smt_tests['POWER'].isChecked() and 'POWER' not in smt_params:
                smt_params['POWER'] = {
                    "sequence_id": "SMT_SEQ_A",
                    "min_mainbeam_current_A": 0.5,
                    "max_mainbeam_current_A": 0.8
                }
            elif not self.smt_tests['POWER'].isChecked() and 'POWER' in smt_params:
                del smt_params['POWER']
        else:
            sku_data['smt_params'] = None
        
        # Handle weight parameters
        if self.mode_checkboxes['WeightChecking'].isChecked():
            if 'weightchecking_params' not in sku_data or sku_data['weightchecking_params'] is None:
                sku_data['weightchecking_params'] = {}
            
            weight_params = sku_data['weightchecking_params']
            
            # Add default WEIGHT parameters if checked
            if self.weight_tests['WEIGHT'].isChecked() and 'WEIGHT' not in weight_params:
                weight_params['WEIGHT'] = {
                    "min_weight_g": 180.0,
                    "max_weight_g": 185.0,
                    "tare_g": 0.5
                }
            elif not self.weight_tests['WEIGHT'].isChecked() and 'WEIGHT' in weight_params:
                del weight_params['WEIGHT']
        else:
            sku_data['weightchecking_params'] = None
    
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
            
            QCheckBox {
                color: white;
                spacing: 8px;
            }
            
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid #555555;
                background-color: #2b2b2b;
            }
            
            QCheckBox::indicator:checked {
                background-color: #4a90a4;
                border: 1px solid #4a90a4;
            }
            
            QCheckBox::indicator:hover {
                border: 1px solid #6bb0c4;
            }
            
            QLabel {
                color: #cccccc;
            }
            
            QFrame {
                border: none;
                background-color: transparent;
            }
            
            QScrollArea {
                border: none;
                background-color: #333333;
            }
            
            QScrollBar:vertical {
                background-color: #2b2b2b;
                width: 12px;
                border-radius: 6px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #555555;
                border-radius: 6px;
                min-height: 20px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #666666;
            }
        """)
