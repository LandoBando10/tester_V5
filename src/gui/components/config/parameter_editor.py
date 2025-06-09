# gui/components/config/parameter_editor.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, 
    QDoubleSpinBox, QSpinBox, QLabel, QGroupBox, QFrame, QScrollArea, QTabWidget
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

from typing import Dict, Any


class ParameterEditor(QWidget):
    """Widget for editing test parameters"""
    
    data_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sku_data = None
        self.global_params = None
        self.setup_ui()
        self.apply_dark_style()
    
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header_label = QLabel("Test Parameters")
        header_label.setFont(QFont("Arial", 14, QFont.Bold))
        header_label.setStyleSheet("color: #ffffff; margin-bottom: 10px;")
        layout.addWidget(header_label)
        
        # Tab widget for different parameter types
        self.param_tabs = QTabWidget()
        
        # Offroad parameters tab
        self.offroad_tab = self.create_offroad_tab()
        self.param_tabs.addTab(self.offroad_tab, "Offroad")
        
        # SMT parameters tab
        self.smt_tab = self.create_smt_tab()
        self.param_tabs.addTab(self.smt_tab, "SMT")
        
        # Weight parameters tab
        self.weight_tab = self.create_weight_tab()
        self.param_tabs.addTab(self.weight_tab, "Weight")
        
        layout.addWidget(self.param_tabs)
    
    def create_offroad_tab(self) -> QWidget:
        """Create offroad parameters tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(20)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(20)
        
        # Current parameters (NEW)
        current_group = QGroupBox("Current Testing Parameters")
        current_layout = QFormLayout(current_group)
        current_layout.setSpacing(10)
        
        self.current_min_main = QDoubleSpinBox()
        self.current_min_main.setRange(0.0, 10.0)
        self.current_min_main.setDecimals(2)
        self.current_min_main.setSuffix(" A")
        self.current_min_main.valueChanged.connect(lambda: self.data_changed.emit())
        current_layout.addRow("Min Mainbeam Current:", self.current_min_main)
        
        self.current_max_main = QDoubleSpinBox()
        self.current_max_main.setRange(0.0, 10.0)
        self.current_max_main.setDecimals(2)
        self.current_max_main.setSuffix(" A")
        self.current_max_main.valueChanged.connect(lambda: self.data_changed.emit())
        current_layout.addRow("Max Mainbeam Current:", self.current_max_main)
        
        self.current_min_back = QDoubleSpinBox()
        self.current_min_back.setRange(0.0, 1.0)
        self.current_min_back.setDecimals(3)
        self.current_min_back.setSuffix(" A")
        self.current_min_back.valueChanged.connect(lambda: self.data_changed.emit())
        current_layout.addRow("Min Backlight Current:", self.current_min_back)
        
        self.current_max_back = QDoubleSpinBox()
        self.current_max_back.setRange(0.0, 1.0)
        self.current_max_back.setDecimals(3)
        self.current_max_back.setSuffix(" A")
        self.current_max_back.valueChanged.connect(lambda: self.data_changed.emit())
        current_layout.addRow("Max Backlight Current:", self.current_max_back)
        
        content_layout.addWidget(current_group)
        
        # LUX parameters
        lux_group = QGroupBox("LUX Testing Parameters")
        lux_layout = QFormLayout(lux_group)
        lux_layout.setSpacing(10)
        
        self.lux_min_main = QSpinBox()
        self.lux_min_main.setRange(0, 10000)
        self.lux_min_main.setSuffix(" lux")
        self.lux_min_main.valueChanged.connect(lambda: self.data_changed.emit())
        lux_layout.addRow("Min Mainbeam LUX:", self.lux_min_main)
        
        self.lux_max_main = QSpinBox()
        self.lux_max_main.setRange(0, 10000)
        self.lux_max_main.setSuffix(" lux")
        self.lux_max_main.valueChanged.connect(lambda: self.data_changed.emit())
        lux_layout.addRow("Max Mainbeam LUX:", self.lux_max_main)
        
        self.lux_min_back = QSpinBox()
        self.lux_min_back.setRange(0, 1000)
        self.lux_min_back.setSuffix(" lux")
        self.lux_min_back.valueChanged.connect(lambda: self.data_changed.emit())
        lux_layout.addRow("Min Backlight LUX:", self.lux_min_back)
        
        self.lux_max_back = QSpinBox()
        self.lux_max_back.setRange(0, 1000)
        self.lux_max_back.setSuffix(" lux")
        self.lux_max_back.valueChanged.connect(lambda: self.data_changed.emit())
        lux_layout.addRow("Max Backlight LUX:", self.lux_max_back)
        
        content_layout.addWidget(lux_group)
        
        # COLOR parameters
        color_group = QGroupBox("COLOR Testing Parameters")
        color_layout = QFormLayout(color_group)
        color_layout.setSpacing(10)
        
        # Mainbeam color
        mainbeam_label = QLabel("Mainbeam Color Coordinates:")
        mainbeam_label.setFont(QFont("Arial", 10, QFont.Bold))
        color_layout.addRow(mainbeam_label)
        
        self.color_center_x_main = QDoubleSpinBox()
        self.color_center_x_main.setRange(0.0, 1.0)
        self.color_center_x_main.setDecimals(3)
        self.color_center_x_main.valueChanged.connect(lambda: self.data_changed.emit())
        color_layout.addRow("  Center X:", self.color_center_x_main)
        
        self.color_center_y_main = QDoubleSpinBox()
        self.color_center_y_main.setRange(0.0, 1.0)
        self.color_center_y_main.setDecimals(3)
        self.color_center_y_main.valueChanged.connect(lambda: self.data_changed.emit())
        color_layout.addRow("  Center Y:", self.color_center_y_main)
        
        self.color_radius_x_main = QDoubleSpinBox()
        self.color_radius_x_main.setRange(0.0, 0.1)
        self.color_radius_x_main.setDecimals(3)
        self.color_radius_x_main.valueChanged.connect(lambda: self.data_changed.emit())
        color_layout.addRow("  Radius X:", self.color_radius_x_main)
        
        self.color_radius_y_main = QDoubleSpinBox()
        self.color_radius_y_main.setRange(0.0, 0.1)
        self.color_radius_y_main.setDecimals(3)
        self.color_radius_y_main.valueChanged.connect(lambda: self.data_changed.emit())
        color_layout.addRow("  Radius Y:", self.color_radius_y_main)
        
        self.color_angle_main = QSpinBox()
        self.color_angle_main.setRange(-90, 90)
        self.color_angle_main.setSuffix("°")
        self.color_angle_main.valueChanged.connect(lambda: self.data_changed.emit())
        color_layout.addRow("  Angle:", self.color_angle_main)
        
        # Backlight color (optional)
        backlight_label = QLabel("Backlight Color Coordinates (optional):")
        backlight_label.setFont(QFont("Arial", 10, QFont.Bold))
        color_layout.addRow(backlight_label)
        
        self.color_center_x_back = QDoubleSpinBox()
        self.color_center_x_back.setRange(0.0, 1.0)
        self.color_center_x_back.setDecimals(3)
        self.color_center_x_back.valueChanged.connect(lambda: self.data_changed.emit())
        color_layout.addRow("  Center X:", self.color_center_x_back)
        
        self.color_center_y_back = QDoubleSpinBox()
        self.color_center_y_back.setRange(0.0, 1.0)
        self.color_center_y_back.setDecimals(3)
        self.color_center_y_back.valueChanged.connect(lambda: self.data_changed.emit())
        color_layout.addRow("  Center Y:", self.color_center_y_back)
        
        self.color_radius_x_back = QDoubleSpinBox()
        self.color_radius_x_back.setRange(0.0, 0.1)
        self.color_radius_x_back.setDecimals(3)
        self.color_radius_x_back.valueChanged.connect(lambda: self.data_changed.emit())
        color_layout.addRow("  Radius X:", self.color_radius_x_back)
        
        self.color_radius_y_back = QDoubleSpinBox()
        self.color_radius_y_back.setRange(0.0, 0.1)
        self.color_radius_y_back.setDecimals(3)
        self.color_radius_y_back.valueChanged.connect(lambda: self.data_changed.emit())
        color_layout.addRow("  Radius Y:", self.color_radius_y_back)
        
        self.color_angle_back = QSpinBox()
        self.color_angle_back.setRange(-90, 90)
        self.color_angle_back.setSuffix("°")
        self.color_angle_back.valueChanged.connect(lambda: self.data_changed.emit())
        color_layout.addRow("  Angle:", self.color_angle_back)
        
        content_layout.addWidget(color_group)
        
        # Pressure parameters (read-only - from global config)
        pressure_group = QGroupBox("Pressure Parameters (Global)")
        pressure_layout = QFormLayout(pressure_group)
        pressure_layout.setSpacing(10)
        
        self.pressure_min_initial = QDoubleSpinBox()
        self.pressure_min_initial.setRange(0.0, 50.0)
        self.pressure_min_initial.setDecimals(1)
        self.pressure_min_initial.setSuffix(" PSI")
        self.pressure_min_initial.setReadOnly(True)
        self.pressure_min_initial.setStyleSheet("background-color: #2a2a2a; color: #888888;")
        pressure_layout.addRow("Min Initial PSI:", self.pressure_min_initial)
        
        self.pressure_max_initial = QDoubleSpinBox()
        self.pressure_max_initial.setRange(0.0, 50.0)
        self.pressure_max_initial.setDecimals(1)
        self.pressure_max_initial.setSuffix(" PSI")
        self.pressure_max_initial.setReadOnly(True)
        self.pressure_max_initial.setStyleSheet("background-color: #2a2a2a; color: #888888;")
        pressure_layout.addRow("Max Initial PSI:", self.pressure_max_initial)
        
        self.pressure_max_delta = QDoubleSpinBox()
        self.pressure_max_delta.setRange(0.0, 10.0)
        self.pressure_max_delta.setDecimals(1)
        self.pressure_max_delta.setSuffix(" PSI")
        self.pressure_max_delta.setReadOnly(True)
        self.pressure_max_delta.setStyleSheet("background-color: #2a2a2a; color: #888888;")
        pressure_layout.addRow("Max Delta PSI:", self.pressure_max_delta)
        
        note_label = QLabel("Note: Pressure parameters are configured globally and cannot be changed per SKU.")
        note_label.setStyleSheet("color: #888888; font-style: italic; font-size: 10px;")
        note_label.setWordWrap(True)
        pressure_layout.addRow(note_label)
        
        content_layout.addWidget(pressure_group)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        return tab
    
    def create_smt_tab(self) -> QWidget:
        """Create SMT parameters tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(20)
        
        # Power sequence parameters
        power_group = QGroupBox("Power Sequence Parameters")
        power_layout = QFormLayout(power_group)
        power_layout.setSpacing(10)
        
        self.smt_sequence_id = QLineEdit()
        self.smt_sequence_id.setPlaceholderText("e.g., SMT_SEQ_A")
        self.smt_sequence_id.textChanged.connect(lambda: self.data_changed.emit())
        power_layout.addRow("Sequence ID:", self.smt_sequence_id)
        
        self.smt_min_current = QDoubleSpinBox()
        self.smt_min_current.setRange(0.0, 10.0)
        self.smt_min_current.setDecimals(2)
        self.smt_min_current.setSuffix(" A")
        self.smt_min_current.valueChanged.connect(lambda: self.data_changed.emit())
        power_layout.addRow("Min Mainbeam Current:", self.smt_min_current)
        
        self.smt_max_current = QDoubleSpinBox()
        self.smt_max_current.setRange(0.0, 10.0)
        self.smt_max_current.setDecimals(2)
        self.smt_max_current.setSuffix(" A")
        self.smt_max_current.valueChanged.connect(lambda: self.data_changed.emit())
        power_layout.addRow("Max Mainbeam Current:", self.smt_max_current)
        
        layout.addWidget(power_group)
        
        # Info section
        info_label = QLabel("SMT programming configuration is managed in the Programming tab.")
        info_label.setStyleSheet("color: #888888; font-style: italic; font-size: 11px; margin: 20px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        return tab
    
    def create_weight_tab(self) -> QWidget:
        """Create weight parameters tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(20)
        
        # Weight validation parameters
        weight_group = QGroupBox("Weight Validation Parameters")
        weight_layout = QFormLayout(weight_group)
        weight_layout.setSpacing(10)
        
        self.weight_min = QDoubleSpinBox()
        self.weight_min.setRange(0.0, 1000.0)
        self.weight_min.setDecimals(1)
        self.weight_min.setSuffix(" g")
        self.weight_min.valueChanged.connect(lambda: self.data_changed.emit())
        weight_layout.addRow("Min Weight:", self.weight_min)
        
        self.weight_max = QDoubleSpinBox()
        self.weight_max.setRange(0.0, 1000.0)
        self.weight_max.setDecimals(1)
        self.weight_max.setSuffix(" g")
        self.weight_max.valueChanged.connect(lambda: self.data_changed.emit())
        weight_layout.addRow("Max Weight:", self.weight_max)
        
        self.weight_tare = QDoubleSpinBox()
        self.weight_tare.setRange(0.0, 10.0)
        self.weight_tare.setDecimals(2)
        self.weight_tare.setSuffix(" g")
        self.weight_tare.valueChanged.connect(lambda: self.data_changed.emit())
        weight_layout.addRow("Tare Weight:", self.weight_tare)
        
        layout.addWidget(weight_group)
        
        # Tolerance configuration
        tolerance_group = QGroupBox("Tolerance Configuration")
        tolerance_layout = QFormLayout(tolerance_group)
        tolerance_layout.setSpacing(10)
        
        # Additional tolerance settings can be added here
        tolerance_note = QLabel("Weight tolerances are defined by the min/max weight values above.")
        tolerance_note.setStyleSheet("color: #888888; font-style: italic; font-size: 10px;")
        tolerance_note.setWordWrap(True)
        tolerance_layout.addRow(tolerance_note)
        
        layout.addWidget(tolerance_group)
        
        layout.addStretch()
        
        return tab
    
    def load_sku_data(self, sku_data: Dict[str, Any], global_params: Dict[str, Any]):
        """Load SKU data and global parameters into the interface"""
        self.sku_data = sku_data
        self.global_params = global_params
        
        # Load offroad parameters
        offroad_params = sku_data.get('offroad_params', {})
        
        # Current parameters (NEW)
        current_params = offroad_params.get('CURRENT', {})
        self.current_min_main.setValue(current_params.get('min_mainbeam_current_A', 0.5))
        self.current_max_main.setValue(current_params.get('max_mainbeam_current_A', 0.8))
        self.current_min_back.setValue(current_params.get('min_backlight_current_A', 0.05))
        self.current_max_back.setValue(current_params.get('max_backlight_current_A', 0.15))
        
        # LUX parameters
        lux_params = offroad_params.get('LUX', {})
        self.lux_min_main.setValue(lux_params.get('min_mainbeam_lux', 1000))
        self.lux_max_main.setValue(lux_params.get('max_mainbeam_lux', 1500))
        self.lux_min_back.setValue(lux_params.get('min_backlight_lux', 100))
        self.lux_max_back.setValue(lux_params.get('max_backlight_lux', 150))
        
        # COLOR parameters
        color_params = offroad_params.get('COLOR', {})
        self.color_center_x_main.setValue(color_params.get('center_x_main', 0.450))
        self.color_center_y_main.setValue(color_params.get('center_y_main', 0.410))
        self.color_radius_x_main.setValue(color_params.get('radius_x_main', 0.015))
        self.color_radius_y_main.setValue(color_params.get('radius_y_main', 0.015))
        self.color_angle_main.setValue(color_params.get('angle_deg_main', 0))
        
        # Backlight color (optional)
        self.color_center_x_back.setValue(color_params.get('center_x_back', 0.580))
        self.color_center_y_back.setValue(color_params.get('center_y_back', 0.390))
        self.color_radius_x_back.setValue(color_params.get('radius_x_back', 0.020))
        self.color_radius_y_back.setValue(color_params.get('radius_y_back', 0.020))
        self.color_angle_back.setValue(color_params.get('angle_deg_back', 0))
        
        # Pressure parameters (global, read-only)
        pressure_params = global_params.get('PRESSURE', {})
        self.pressure_min_initial.setValue(pressure_params.get('min_initial_psi', 14.0))
        self.pressure_max_initial.setValue(pressure_params.get('max_initial_psi', 16.0))
        self.pressure_max_delta.setValue(pressure_params.get('max_delta_psi', 0.5))
        
        # SMT parameters
        smt_params = sku_data.get('smt_params', {})
        power_params = smt_params.get('POWER', {}) if smt_params else {}
        self.smt_sequence_id.setText(power_params.get('sequence_id', 'SMT_SEQ_A'))
        self.smt_min_current.setValue(power_params.get('min_mainbeam_current_A', 0.5))
        self.smt_max_current.setValue(power_params.get('max_mainbeam_current_A', 0.8))
        
        # Weight parameters
        weight_params = sku_data.get('weightchecking_params', {})
        weight_config = weight_params.get('WEIGHT', {}) if weight_params else {}
        self.weight_min.setValue(weight_config.get('min_weight_g', 180.0))
        self.weight_max.setValue(weight_config.get('max_weight_g', 185.0))
        self.weight_tare.setValue(weight_config.get('tare_g', 0.5))
    
    def save_to_sku_data(self, sku_data: Dict[str, Any]):
        """Save current parameter values to SKU data"""
        # Save offroad parameters
        if 'offroad_params' in sku_data and sku_data['offroad_params']:
            offroad_params = sku_data['offroad_params']
            
            # Current parameters (NEW)
            if 'CURRENT' in offroad_params:
                offroad_params['CURRENT'] = {
                    'min_mainbeam_current_A': self.current_min_main.value(),
                    'max_mainbeam_current_A': self.current_max_main.value(),
                    'min_backlight_current_A': self.current_min_back.value(),
                    'max_backlight_current_A': self.current_max_back.value()
                }
            
            # LUX parameters
            if 'LUX' in offroad_params:
                offroad_params['LUX'] = {
                    'min_mainbeam_lux': self.lux_min_main.value(),
                    'max_mainbeam_lux': self.lux_max_main.value(),
                    'min_backlight_lux': self.lux_min_back.value(),
                    'max_backlight_lux': self.lux_max_back.value()
                }
            
            # COLOR parameters
            if 'COLOR' in offroad_params:
                color_params = {
                    'center_x_main': self.color_center_x_main.value(),
                    'center_y_main': self.color_center_y_main.value(),
                    'radius_x_main': self.color_radius_x_main.value(),
                    'radius_y_main': self.color_radius_y_main.value(),
                    'angle_deg_main': self.color_angle_main.value()
                }
                
                # Add backlight color if values are non-zero
                if (self.color_center_x_back.value() > 0 or self.color_center_y_back.value() > 0):
                    color_params.update({
                        'center_x_back': self.color_center_x_back.value(),
                        'center_y_back': self.color_center_y_back.value(),
                        'radius_x_back': self.color_radius_x_back.value(),
                        'radius_y_back': self.color_radius_y_back.value(),
                        'angle_deg_back': self.color_angle_back.value()
                    })
                
                offroad_params['COLOR'] = color_params
        
        # Save SMT parameters
        if 'smt_params' in sku_data and sku_data['smt_params']:
            smt_params = sku_data['smt_params']
            
            if 'POWER' in smt_params:
                smt_params['POWER'] = {
                    'sequence_id': self.smt_sequence_id.text(),
                    'min_mainbeam_current_A': self.smt_min_current.value(),
                    'max_mainbeam_current_A': self.smt_max_current.value()
                }
        
        # Save weight parameters
        if 'weightchecking_params' in sku_data and sku_data['weightchecking_params']:
            weight_params = sku_data['weightchecking_params']
            
            if 'WEIGHT' in weight_params:
                weight_params['WEIGHT'] = {
                    'min_weight_g': self.weight_min.value(),
                    'max_weight_g': self.weight_max.value(),
                    'tare_g': self.weight_tare.value()
                }
    
    def apply_dark_style(self):
        """Apply dark theme styling"""
        self.setStyleSheet("""
            QWidget {
                background-color: #333333;
                color: white;
            }
            
            QTabWidget::pane {
                border: 1px solid #555555;
                background-color: #333333;
            }
            
            QTabBar::tab {
                background-color: #404040;
                color: white;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            
            QTabBar::tab:selected {
                background-color: #4a90a4;
            }
            
            QTabBar::tab:hover {
                background-color: #555555;
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
            
            QLineEdit, QSpinBox, QDoubleSpinBox {
                background-color: #2b2b2b;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px;
                color: white;
                font-size: 11px;
                min-width: 80px;
            }
            
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #4a90a4;
            }
            
            QSpinBox::up-button, QDoubleSpinBox::up-button,
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                background-color: #404040;
                border: 1px solid #555555;
                width: 16px;
            }
            
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
                background-color: #555555;
            }
            
            QLabel {
                color: #cccccc;
                font-size: 11px;
            }
            
            QFormLayout QLabel {
                font-weight: normal;
                min-width: 180px;
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
