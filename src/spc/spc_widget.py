"""
Enhanced SPC Control Widget for SMT Testing
Provides visualization and per-SKU mode control for Statistical Process Control

Features:
- Per-SKU mode configuration (sampling/production)
- Real-time control chart display
- Control limit visualization
- Process capability display
- Sample collection status
- Specification limit management
- Export capabilities
"""

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QComboBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QFileDialog,
    QMessageBox, QProgressBar, QCheckBox,
    QTabWidget, QTextEdit, QSplitter
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QIcon

from pathlib import Path
from typing import Dict, Optional, List, Tuple
import numpy as np
from datetime import datetime
import json
import logging

from src.spc.spc_calculator import SPCCalculator, ControlLimits
from src.spc.data_collector import SPCDataCollector
from src.spc.spc_integration import SPCIntegration
from src.gui.components.spec_approval_dialog import SpecApprovalDialog


class SPCModeConfiguration:
    """Store per-SKU mode configuration"""
    def __init__(self):
        self.config_file = Path("config/spc_mode_config.json")
        self.configurations = self._load_configurations()
        
    def _load_configurations(self) -> Dict[str, Dict[str, bool]]:
        """Load saved mode configurations"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
        
    def save_configurations(self):
        """Save current configurations"""
        self.config_file.parent.mkdir(exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.configurations, f, indent=2)
            
    def get_config(self, sku: str) -> Dict[str, bool]:
        """Get configuration for a specific SKU"""
        return self.configurations.get(sku, {
            'enabled': True,
            'sampling_mode': True,
            'production_mode': False
        })
        
    def set_config(self, sku: str, config: Dict[str, bool]):
        """Set configuration for a specific SKU"""
        self.configurations[sku] = config
        self.save_configurations()


class SPCWidget(QWidget):
    """Enhanced widget for SPC visualization and control"""
    
    # Signals
    limits_updated = Signal(str, dict)  # SKU, limits dict
    mode_changed = Signal(str, dict)  # SKU, mode config
    spec_approval_requested = Signal(str)  # SKU
    
    def __init__(self, spc_integration: Optional[SPCIntegration] = None, parent=None):
        super().__init__(parent)
        self.spc_integration = spc_integration
        self.current_sku = None
        self.data_collector = SPCDataCollector()
        self.calculator = SPCCalculator()
        self.mode_config = SPCModeConfiguration()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.init_ui()
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.refresh_display)
        self.update_timer.start(5000)  # Update every 5 seconds
        
    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout()
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Control & Charts tab
        control_charts_widget = QWidget()
        control_charts_layout = QVBoxLayout()
        
        # Control section
        control_group = self.create_control_section()
        control_charts_layout.addWidget(control_group)
        
        # Mode configuration section
        mode_group = self.create_mode_section()
        control_charts_layout.addWidget(mode_group)
        
        # Chart section
        chart_group = self.create_chart_section()
        control_charts_layout.addWidget(chart_group, 1)
        
        # Status section
        status_group = self.create_status_section()
        control_charts_layout.addWidget(status_group)
        
        control_charts_widget.setLayout(control_charts_layout)
        self.tab_widget.addTab(control_charts_widget, "Control Charts")
        
        # Data Analysis tab
        analysis_widget = self.create_analysis_tab()
        self.tab_widget.addTab(analysis_widget, "Data Analysis")
        
        # Configuration tab
        config_widget = self.create_configuration_tab()
        self.tab_widget.addTab(config_widget, "Configuration")
        
        layout.addWidget(self.tab_widget)
        self.setLayout(layout)
        
    def create_control_section(self) -> QGroupBox:
        """Create control section"""
        group = QGroupBox("SKU Selection")
        layout = QHBoxLayout()
        
        # SKU selector
        layout.addWidget(QLabel("SKU:"))
        self.sku_combo = QComboBox()
        self.sku_combo.setMinimumWidth(150)
        self.sku_combo.currentTextChanged.connect(self.on_sku_changed)
        layout.addWidget(self.sku_combo)
        
        # Function selector
        layout.addWidget(QLabel("Function:"))
        self.function_combo = QComboBox()
        self.function_combo.setMinimumWidth(150)
        self.function_combo.currentTextChanged.connect(self.on_function_changed)
        layout.addWidget(self.function_combo)
        
        # Board selector
        layout.addWidget(QLabel("Board:"))
        self.board_combo = QComboBox()
        self.board_combo.setMinimumWidth(100)
        self.board_combo.currentTextChanged.connect(self.refresh_display)
        layout.addWidget(self.board_combo)
        
        layout.addStretch()
        
        # Action buttons
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_display)
        layout.addWidget(self.refresh_btn)
        
        # Export button
        self.export_btn = QPushButton("Export Report")
        self.export_btn.clicked.connect(self.export_report)
        layout.addWidget(self.export_btn)
        
        group.setLayout(layout)
        return group
        
    def create_mode_section(self) -> QGroupBox:
        """Create mode configuration section"""
        group = QGroupBox("SPC Mode Configuration")
        layout = QHBoxLayout()
        
        # Mode status display
        self.mode_status_label = QLabel("Mode: Not Configured")
        self.mode_status_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.mode_status_label)
        
        layout.addStretch()
        
        # Mode checkboxes
        self.spc_enabled_check = QCheckBox("SPC Enabled")
        self.spc_enabled_check.stateChanged.connect(self.on_mode_changed)
        layout.addWidget(self.spc_enabled_check)
        
        self.sampling_mode_check = QCheckBox("Sampling Mode")
        self.sampling_mode_check.setToolTip("Collect data and update control limits")
        self.sampling_mode_check.stateChanged.connect(self.on_mode_changed)
        layout.addWidget(self.sampling_mode_check)
        
        self.production_mode_check = QCheckBox("Production Mode")
        self.production_mode_check.setToolTip("Enforce control limits for pass/fail")
        self.production_mode_check.stateChanged.connect(self.on_mode_changed)
        layout.addWidget(self.production_mode_check)
        
        # Specification management buttons
        layout.addWidget(QLabel("  |  "))
        
        self.derive_specs_btn = QPushButton("Derive Specs")
        self.derive_specs_btn.setToolTip("Calculate specification limits from process data (Cp=1.33)")
        self.derive_specs_btn.clicked.connect(self.derive_specifications)
        layout.addWidget(self.derive_specs_btn)
        
        self.recalc_limits_btn = QPushButton("Recalculate Limits")
        self.recalc_limits_btn.setToolTip("Force recalculation of control limits")
        self.recalc_limits_btn.clicked.connect(self.calculate_limits)
        layout.addWidget(self.recalc_limits_btn)
        
        group.setLayout(layout)
        return group
        
    def create_chart_section(self) -> QGroupBox:
        """Create chart display section"""
        group = QGroupBox("Control Charts")
        layout = QVBoxLayout()
        
        # Chart options
        options_layout = QHBoxLayout()
        
        # Auto-update checkbox
        self.auto_update_check = QCheckBox("Auto Update")
        self.auto_update_check.setChecked(True)
        options_layout.addWidget(self.auto_update_check)
        
        # Show specs checkbox
        self.show_specs_check = QCheckBox("Show Spec Limits")
        self.show_specs_check.setChecked(True)
        self.show_specs_check.stateChanged.connect(self.refresh_display)
        options_layout.addWidget(self.show_specs_check)
        
        # Show violations checkbox
        self.show_violations_check = QCheckBox("Highlight Violations")
        self.show_violations_check.setChecked(True)
        self.show_violations_check.stateChanged.connect(self.refresh_display)
        options_layout.addWidget(self.show_violations_check)
        
        options_layout.addStretch()
        
        # Subgroup size control
        options_layout.addWidget(QLabel("Subgroup Size:"))
        self.sample_size_spin = QSpinBox()
        self.sample_size_spin.setRange(2, 10)
        self.sample_size_spin.setValue(5)
        self.sample_size_spin.valueChanged.connect(self.on_sample_size_changed)
        options_layout.addWidget(self.sample_size_spin)
        
        layout.addLayout(options_layout)
        
        # Create matplotlib figure
        self.figure = Figure(figsize=(12, 8))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        group.setLayout(layout)
        return group
        
    def create_status_section(self) -> QGroupBox:
        """Create status display section"""
        group = QGroupBox("Process Status")
        layout = QHBoxLayout()
        
        # Left side - current limits
        left_layout = QVBoxLayout()
        
        self.limits_table = QTableWidget(10, 2)
        self.limits_table.setHorizontalHeaderLabels(["Parameter", "Value"])
        self.limits_table.verticalHeader().setVisible(False)
        self.limits_table.setMaximumHeight(250)
        
        # Set row headers
        rows = [
            "X̄ UCL", "X̄ CL", "X̄ LCL",
            "R UCL", "R CL", "R LCL",
            "Cp", "Cpk",
            "LSL", "USL"
        ]
        for i, label in enumerate(rows):
            self.limits_table.setItem(i, 0, QTableWidgetItem(label))
            
        left_layout.addWidget(QLabel("Control & Spec Limits:"))
        left_layout.addWidget(self.limits_table)
        
        # Right side - collection status
        right_layout = QVBoxLayout()
        
        self.status_labels = {
            'subgroups': QLabel("Subgroups Collected: 0"),
            'measurements': QLabel("Total Measurements: 0"),
            'last_update': QLabel("Last Update: Never"),
            'status': QLabel("Status: Waiting for data..."),
            'capability': QLabel("Process Capability: Unknown")
        }
        
        for label in self.status_labels.values():
            right_layout.addWidget(label)
            
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(6)  # 6 subgroups = 30 measurements
        self.progress_bar.setFormat("%v/%m subgroups (%p%)")
        right_layout.addWidget(self.progress_bar)
        
        # Add spacing
        right_layout.addStretch()
        
        layout.addLayout(left_layout)
        layout.addStretch()
        layout.addLayout(right_layout)
        
        group.setLayout(layout)
        return group
        
    def create_analysis_tab(self) -> QWidget:
        """Create data analysis tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Analysis controls
        controls_layout = QHBoxLayout()
        
        controls_layout.addWidget(QLabel("Analysis Period:"))
        self.period_combo = QComboBox()
        self.period_combo.addItems(["Last 25 Subgroups", "Last 50 Subgroups", 
                                   "Last 100 Subgroups", "All Data"])
        controls_layout.addWidget(self.period_combo)
        
        self.analyze_btn = QPushButton("Run Analysis")
        self.analyze_btn.clicked.connect(self.run_analysis)
        controls_layout.addWidget(self.analyze_btn)
        
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # Analysis output
        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        self.analysis_text.setFont(QFont("Courier", 10))
        layout.addWidget(self.analysis_text)
        
        widget.setLayout(layout)
        return widget
        
    def create_configuration_tab(self) -> QWidget:
        """Create configuration tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Mode configuration summary
        config_group = QGroupBox("SKU Mode Configuration Summary")
        config_layout = QVBoxLayout()
        
        self.config_table = QTableWidget()
        self.config_table.setColumnCount(4)
        self.config_table.setHorizontalHeaderLabels(["SKU", "SPC Enabled", "Sampling", "Production"])
        config_layout.addWidget(self.config_table)
        
        # Refresh button
        refresh_layout = QHBoxLayout()
        refresh_config_btn = QPushButton("Refresh Configuration")
        refresh_config_btn.clicked.connect(self.refresh_configuration_table)
        refresh_layout.addWidget(refresh_config_btn)
        refresh_layout.addStretch()
        
        config_layout.addLayout(refresh_layout)
        config_group.setLayout(config_layout)
        
        layout.addWidget(config_group)
        
        # SPC settings
        settings_group = QGroupBox("SPC Settings")
        settings_layout = QVBoxLayout()
        
        settings_text = QTextEdit()
        settings_text.setReadOnly(True)
        settings_text.setMaximumHeight(200)
        settings_text.setPlainText(
            "SPC Configuration:\n"
            "- Subgroup Size: 5 measurements\n"
            "- Minimum Subgroups: 6 (30 measurements)\n"
            "- Control Limits: 3-sigma (99.73% coverage)\n"
            "- Target Capability: Cp = 1.33\n"
            "- Spec Derivation: LSL/USL = mean ± 4σ\n"
            "- Data Retention: 100 subgroups rolling window\n"
            "\nControl Rules:\n"
            "- Rule 1: One point outside control limits\n"
            "- Rule 2: Nine points on same side of centerline\n"
            "- Rule 3: Six points in monotonic sequence"
        )
        settings_layout.addWidget(settings_text)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
        
    def update_sku_list(self, skus: List[str]):
        """Update available SKUs"""
        current = self.sku_combo.currentText()
        self.sku_combo.clear()
        self.sku_combo.addItems(skus)
        if current in skus:
            self.sku_combo.setCurrentText(current)
            
    def on_sku_changed(self, sku: str):
        """Handle SKU selection change"""
        if not sku:
            return
            
        self.current_sku = sku
        
        # Load mode configuration for this SKU
        config = self.mode_config.get_config(sku)
        self.spc_enabled_check.setChecked(config.get('enabled', True))
        self.sampling_mode_check.setChecked(config.get('sampling_mode', True))
        self.production_mode_check.setChecked(config.get('production_mode', False))
        
        # Update mode status label
        self.update_mode_status()
        
        # Update function list based on SKU configuration
        try:
            sku_file = Path("config/skus") / f"{sku}.json"
            if sku_file.exists():
                with open(sku_file, 'r') as f:
                    sku_data = json.load(f)
                    
                functions = []
                for sequence in sku_data.get('test_sequences', []):
                    if 'function' in sequence:
                        functions.append(sequence['function'])
                        
                self.function_combo.clear()
                self.function_combo.addItems(functions)
        except Exception as e:
            self.logger.error(f"Error loading SKU functions: {e}")
            # Fallback to default functions
            functions = ["mainbeam", "backlight_left", "backlight_right"]
            self.function_combo.clear()
            self.function_combo.addItems(functions)
            
    def on_function_changed(self, function: str):
        """Handle function selection change"""
        if not function:
            return
            
        # Update board list
        # Check actual data availability
        pattern = f"{self.current_sku}_{function}_*_subgroups.json"
        available_boards = set()
        
        for file in self.data_collector.data_dir.glob(pattern):
            parts = file.stem.split('_')
            if len(parts) >= 4:
                board = '_'.join(parts[2:-1])
                available_boards.add(board)
                
        if available_boards:
            boards = sorted(list(available_boards))
        else:
            # Default boards
            boards = [f"Board_{i}" for i in range(1, 3)]
            
        self.board_combo.clear()
        self.board_combo.addItems(boards)
        
    def on_sample_size_changed(self, size: int):
        """Handle sample size change"""
        self.data_collector.subgroup_size = size
        
    def on_mode_changed(self):
        """Handle mode configuration change"""
        if not self.current_sku:
            return
            
        # Get current configuration
        config = {
            'enabled': self.spc_enabled_check.isChecked(),
            'sampling_mode': self.sampling_mode_check.isChecked(),
            'production_mode': self.production_mode_check.isChecked()
        }
        
        # Save configuration
        self.mode_config.set_config(self.current_sku, config)
        
        # Update mode status
        self.update_mode_status()
        
        # Update SPC integration if available
        if self.spc_integration:
            self.spc_integration.spc_enabled = config['enabled']
            self.spc_integration.sampling_mode = config['sampling_mode']
            self.spc_integration.production_mode = config['production_mode']
            
        # Emit signal
        self.mode_changed.emit(self.current_sku, config)
        
    def update_mode_status(self):
        """Update mode status label"""
        if not self.spc_enabled_check.isChecked():
            self.mode_status_label.setText("Mode: SPC Disabled")
            self.mode_status_label.setStyleSheet("color: gray; font-weight: bold;")
        else:
            modes = []
            if self.sampling_mode_check.isChecked():
                modes.append("Sampling")
            if self.production_mode_check.isChecked():
                modes.append("Production")
                
            if modes:
                self.mode_status_label.setText(f"Mode: {' + '.join(modes)}")
                if "Production" in modes:
                    self.mode_status_label.setStyleSheet("color: green; font-weight: bold;")
                else:
                    self.mode_status_label.setStyleSheet("color: blue; font-weight: bold;")
            else:
                self.mode_status_label.setText("Mode: SPC Enabled (No Active Mode)")
                self.mode_status_label.setStyleSheet("color: orange; font-weight: bold;")
                
    def refresh_display(self):
        """Refresh the display with current data"""
        if not self.auto_update_check.isChecked():
            return
            
        sku = self.sku_combo.currentText()
        function = self.function_combo.currentText()
        board = self.board_combo.currentText()
        
        if not all([sku, function, board]):
            return
            
        # Get control limits
        limits = self.data_collector.get_control_limits(sku, function, board)
        
        if limits:
            self.display_limits(limits, sku, function, board)
            self.plot_control_charts(sku, function, board, limits)
        else:
            self.status_labels['status'].setText("Status: Collecting initial data...")
            
        # Update collection status
        self.update_collection_status(sku, function, board)
        
    def display_limits(self, limits: ControlLimits, sku: str, function: str, board: str):
        """Display control limits and specs in table"""
        values = [
            f"{limits.xbar_ucl:.4f}",
            f"{limits.xbar_cl:.4f}",
            f"{limits.xbar_lcl:.4f}",
            f"{limits.r_ucl:.4f}",
            f"{limits.r_cl:.4f}",
            f"{limits.r_lcl:.4f}",
            f"{limits.cp:.3f}" if limits.cp else "N/A",
            f"{limits.cpk:.3f}" if limits.cpk else "N/A",
            "N/A",  # LSL
            "N/A"   # USL
        ]
        
        # Try to get spec limits
        spec_limits = self.data_collector._get_spec_limits(sku, function, board)
        if spec_limits:
            values[8] = f"{spec_limits[0]:.4f}"  # LSL
            values[9] = f"{spec_limits[1]:.4f}"  # USL
            
        for i, value in enumerate(values):
            self.limits_table.setItem(i, 1, QTableWidgetItem(value))
            
    def plot_control_charts(self, sku: str, function: str, 
                           board: str, limits: ControlLimits):
        """Plot X-bar and R control charts"""
        self.figure.clear()
        
        # Load subgroup data
        filename = self.data_collector.data_dir / f"{sku}_{function}_{board}_subgroups.json"
        if not filename.exists():
            return
            
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                
            # Extract subgroup statistics
            subgroup_means = []
            subgroup_ranges = []
            timestamps = []
            
            for subgroup_data in data:
                currents = [m['current'] for m in subgroup_data['measurements']]
                subgroup_means.append(np.mean(currents))
                subgroup_ranges.append(np.max(currents) - np.min(currents))
                timestamps.append(subgroup_data.get('timestamp', ''))
                
            # Create subplots
            ax1 = self.figure.add_subplot(2, 1, 1)
            ax2 = self.figure.add_subplot(2, 1, 2)
            
            # X-bar chart
            x = range(1, len(subgroup_means) + 1)
            ax1.plot(x, subgroup_means, 'b-o', markersize=4, label='Subgroup Mean')
            
            # Control limits
            ax1.axhline(y=limits.xbar_ucl, color='r', linestyle='--', label='UCL', linewidth=2)
            ax1.axhline(y=limits.xbar_cl, color='g', linestyle='-', label='CL', linewidth=2)
            ax1.axhline(y=limits.xbar_lcl, color='r', linestyle='--', label='LCL', linewidth=2)
            
            # Spec limits if enabled
            if self.show_specs_check.isChecked():
                spec_limits = self.data_collector._get_spec_limits(sku, function, board)
                if spec_limits:
                    ax1.axhline(y=spec_limits[1], color='orange', linestyle=':', 
                              label='USL', linewidth=2, alpha=0.7)
                    ax1.axhline(y=spec_limits[0], color='orange', linestyle=':', 
                              label='LSL', linewidth=2, alpha=0.7)
                    
            ax1.set_ylabel('Current (A)')
            ax1.set_title(f'X̄ Control Chart - {sku} {function} {board}')
            ax1.grid(True, alpha=0.3)
            ax1.legend(loc='upper right')
            
            # R chart
            ax2.plot(x, subgroup_ranges, 'b-o', markersize=4, label='Subgroup Range')
            ax2.axhline(y=limits.r_ucl, color='r', linestyle='--', label='UCL', linewidth=2)
            ax2.axhline(y=limits.r_cl, color='g', linestyle='-', label='CL', linewidth=2)
            ax2.axhline(y=limits.r_lcl, color='r', linestyle='--', label='LCL', linewidth=2)
            ax2.set_xlabel('Subgroup')
            ax2.set_ylabel('Range (A)')
            ax2.set_title('R Control Chart')
            ax2.grid(True, alpha=0.3)
            ax2.legend(loc='upper right')
            
            # Check for out-of-control points if enabled
            if self.show_violations_check.isChecked():
                violations = self.calculator.check_control_rules(subgroup_means, limits)
                if violations:
                    for violation in violations:
                        if 'index' in violation:
                            ax1.plot(violation['index'] + 1, subgroup_means[violation['index']], 
                                   'ro', markersize=10, fillstyle='none', linewidth=2)
                            # Add annotation
                            ax1.annotate(f"Rule {violation['rule']}", 
                                       xy=(violation['index'] + 1, subgroup_means[violation['index']]),
                                       xytext=(5, 5), textcoords='offset points',
                                       fontsize=8, color='red')
                                       
            self.figure.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            self.logger.error(f"Error plotting charts: {e}")
            
    def update_collection_status(self, sku: str, function: str, board: str):
        """Update data collection status display"""
        filename = self.data_collector.data_dir / f"{sku}_{function}_{board}_subgroups.json"
        
        if filename.exists():
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)
                    
                count = len(data)
                total_measurements = sum(len(sg['measurements']) for sg in data)
                
                self.status_labels['subgroups'].setText(f"Subgroups Collected: {count}")
                self.status_labels['measurements'].setText(f"Total Measurements: {total_measurements}")
                self.progress_bar.setValue(min(count, self.progress_bar.maximum()))
                
                if data:
                    last_time = data[-1]['timestamp']
                    dt = datetime.fromisoformat(last_time)
                    self.status_labels['last_update'].setText(
                        f"Last Update: {dt.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    
                if count >= self.data_collector.min_subgroups:
                    self.status_labels['status'].setText("Status: Ready for production")
                    self.status_labels['status'].setStyleSheet("color: green")
                    
                    # Update capability status
                    limits = self.data_collector.get_control_limits(sku, function, board)
                    if limits and limits.cpk:
                        if limits.cpk >= 1.33:
                            self.status_labels['capability'].setText(
                                f"Process Capability: Excellent (Cpk={limits.cpk:.2f})"
                            )
                            self.status_labels['capability'].setStyleSheet("color: green")
                        elif limits.cpk >= 1.0:
                            self.status_labels['capability'].setText(
                                f"Process Capability: Acceptable (Cpk={limits.cpk:.2f})"
                            )
                            self.status_labels['capability'].setStyleSheet("color: orange")
                        else:
                            self.status_labels['capability'].setText(
                                f"Process Capability: Poor (Cpk={limits.cpk:.2f})"
                            )
                            self.status_labels['capability'].setStyleSheet("color: red")
                else:
                    remaining = self.data_collector.min_subgroups - count
                    remaining_meas = remaining * 5
                    self.status_labels['status'].setText(
                        f"Status: Need {remaining} more subgroups ({remaining_meas} measurements)"
                    )
                    self.status_labels['status'].setStyleSheet("color: orange")
                    
            except Exception as e:
                self.logger.error(f"Error updating status: {e}")
                
    def calculate_limits(self):
        """Force calculation of control limits"""
        sku = self.sku_combo.currentText()
        function = self.function_combo.currentText()
        board = self.board_combo.currentText()
        
        if not all([sku, function, board]):
            QMessageBox.warning(self, "Warning", "Please select SKU, function, and board")
            return
            
        limits = self.data_collector.force_calculate_limits(sku, function, board)
        
        if limits:
            # Save limits
            limit_file = self.data_collector.data_dir / f"{sku}_{function}_{board}_limits.json"
            self.calculator.save_limits(limits, limit_file)
            
            # Update cache
            key = f"{sku}_{function}_{board}"
            self.data_collector.control_limits[key] = limits
            
            # Emit signal
            self.limits_updated.emit(sku, self.data_collector.get_all_limits(sku))
            
            # Refresh display
            self.refresh_display()
            
            QMessageBox.information(self, "Success", 
                                  f"Control limits calculated:\n"
                                  f"X̄: {limits.xbar_lcl:.4f} - {limits.xbar_ucl:.4f}\n"
                                  f"Cpk: {limits.cpk:.3f}")
        else:
            QMessageBox.warning(self, "Warning", 
                              "Not enough data to calculate control limits.\n"
                              "Need at least 5 subgroups.")
                              
    def derive_specifications(self):
        """Derive specification limits from process data"""
        sku = self.sku_combo.currentText()
        if not sku:
            QMessageBox.warning(self, "Warning", "Please select a SKU")
            return
            
        # Check if we have sufficient data
        measurement_counts = self.data_collector.get_measurement_count(sku)
        total_measurements = sum(measurement_counts.values())
        
        if total_measurements < 30:
            QMessageBox.warning(self, "Insufficient Data", 
                              f"Need at least 30 measurements to derive specifications.\n"
                              f"Current measurements: {total_measurements}")
            return
            
        # Use the integration to show spec approval dialog
        if self.spc_integration:
            self.spc_integration.show_spec_approval_dialog(sku, self)
        else:
            # Fallback - just emit signal
            self.spec_approval_requested.emit(sku)
            
    def export_report(self):
        """Export SPC report"""
        sku = self.sku_combo.currentText()
        if not sku:
            QMessageBox.warning(self, "Warning", "Please select a SKU")
            return
            
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export SPC Report", 
            f"{sku}_spc_report_{datetime.now():%Y%m%d_%H%M%S}.json",
            "JSON Files (*.json);;CSV Files (*.csv)"
        )
        
        if filename:
            if filename.endswith('.csv'):
                self.export_csv_report(sku, Path(filename))
            else:
                self.data_collector.export_spc_report(sku, Path(filename))
            QMessageBox.information(self, "Success", f"Report exported to {filename}")
            
    def export_csv_report(self, sku: str, filepath: Path):
        """Export SPC data as CSV"""
        import csv
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow(['SKU', 'Function', 'Board', 'Subgroup', 'Timestamp',
                           'Mean', 'Range', 'UCL', 'LCL', 'Cpk'])
                           
            # Get all data for SKU
            pattern = f"{sku}_*_*_subgroups.json"
            for subgroup_file in self.data_collector.data_dir.glob(pattern):
                parts = subgroup_file.stem.split('_')
                if len(parts) >= 4:
                    function = parts[1]
                    board = '_'.join(parts[2:-1])
                    
                    # Get limits
                    limits = self.data_collector.get_control_limits(sku, function, board)
                    
                    # Load subgroup data
                    with open(subgroup_file, 'r') as sf:
                        data = json.load(sf)
                        
                    for i, subgroup in enumerate(data):
                        currents = [m['current'] for m in subgroup['measurements']]
                        mean = np.mean(currents)
                        range_val = np.max(currents) - np.min(currents)
                        
                        writer.writerow([
                            sku, function, board, i+1, subgroup['timestamp'],
                            f"{mean:.4f}", f"{range_val:.4f}",
                            f"{limits.xbar_ucl:.4f}" if limits else "N/A",
                            f"{limits.xbar_lcl:.4f}" if limits else "N/A",
                            f"{limits.cpk:.3f}" if limits and limits.cpk else "N/A"
                        ])
                        
    def run_analysis(self):
        """Run detailed analysis"""
        sku = self.sku_combo.currentText()
        function = self.function_combo.currentText()
        board = self.board_combo.currentText()
        
        if not all([sku, function, board]):
            self.analysis_text.setPlainText("Please select SKU, function, and board")
            return
            
        analysis = f"SPC Analysis Report\n"
        analysis += f"{'='*60}\n"
        analysis += f"SKU: {sku}\n"
        analysis += f"Function: {function}\n"
        analysis += f"Board: {board}\n"
        analysis += f"Timestamp: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
        analysis += f"{'='*60}\n\n"
        
        # Get data
        filename = self.data_collector.data_dir / f"{sku}_{function}_{board}_subgroups.json"
        if not filename.exists():
            analysis += "No data available for analysis\n"
            self.analysis_text.setPlainText(analysis)
            return
            
        with open(filename, 'r') as f:
            data = json.load(f)
            
        # Get period
        period = self.period_combo.currentText()
        if "25" in period:
            data = data[-25:]
        elif "50" in period:
            data = data[-50:]
        elif "100" in period:
            data = data[-100:]
            
        # Calculate statistics
        all_measurements = []
        for subgroup in data:
            all_measurements.extend([m['current'] for m in subgroup['measurements']])
            
        analysis += f"Data Summary:\n"
        analysis += f"  Subgroups analyzed: {len(data)}\n"
        analysis += f"  Total measurements: {len(all_measurements)}\n"
        analysis += f"  Mean: {np.mean(all_measurements):.4f} A\n"
        analysis += f"  Std Dev: {np.std(all_measurements):.4f} A\n"
        analysis += f"  Min: {np.min(all_measurements):.4f} A\n"
        analysis += f"  Max: {np.max(all_measurements):.4f} A\n"
        analysis += f"  Range: {np.max(all_measurements) - np.min(all_measurements):.4f} A\n\n"
        
        # Get limits and capability
        limits = self.data_collector.get_control_limits(sku, function, board)
        if limits:
            analysis += f"Control Limits:\n"
            analysis += f"  X-bar UCL: {limits.xbar_ucl:.4f} A\n"
            analysis += f"  X-bar CL:  {limits.xbar_cl:.4f} A\n"
            analysis += f"  X-bar LCL: {limits.xbar_lcl:.4f} A\n"
            analysis += f"  R UCL: {limits.r_ucl:.4f} A\n"
            analysis += f"  R CL:  {limits.r_cl:.4f} A\n\n"
            
            if limits.cp and limits.cpk:
                analysis += f"Process Capability:\n"
                analysis += f"  Cp:  {limits.cp:.3f}\n"
                analysis += f"  Cpk: {limits.cpk:.3f}\n"
                analysis += f"  Assessment: "
                
                if limits.cpk >= 1.33:
                    analysis += "Excellent - Process is capable\n"
                elif limits.cpk >= 1.0:
                    analysis += "Acceptable - Process is marginally capable\n"
                else:
                    analysis += "Poor - Process is not capable\n"
                    
        # Check for trends
        subgroup_means = [np.mean([m['current'] for m in sg['measurements']]) for sg in data]
        
        analysis += f"\nTrend Analysis:\n"
        
        # Simple trend detection
        if len(subgroup_means) >= 7:
            recent_trend = subgroup_means[-7:]
            if all(recent_trend[i] <= recent_trend[i+1] for i in range(6)):
                analysis += "  WARNING: 7 consecutive increasing values detected\n"
            elif all(recent_trend[i] >= recent_trend[i+1] for i in range(6)):
                analysis += "  WARNING: 7 consecutive decreasing values detected\n"
            else:
                analysis += "  No significant trends detected\n"
                
        self.analysis_text.setPlainText(analysis)
        
    def refresh_configuration_table(self):
        """Refresh the configuration summary table"""
        configs = self.mode_config.configurations
        
        self.config_table.setRowCount(len(configs))
        
        row = 0
        for sku, config in configs.items():
            self.config_table.setItem(row, 0, QTableWidgetItem(sku))
            
            # Enabled
            enabled_item = QTableWidgetItem("✓" if config.get('enabled', True) else "✗")
            enabled_item.setTextAlignment(Qt.AlignCenter)
            self.config_table.setItem(row, 1, enabled_item)
            
            # Sampling
            sampling_item = QTableWidgetItem("✓" if config.get('sampling_mode', True) else "✗")
            sampling_item.setTextAlignment(Qt.AlignCenter)
            self.config_table.setItem(row, 2, sampling_item)
            
            # Production
            production_item = QTableWidgetItem("✓" if config.get('production_mode', False) else "✗")
            production_item.setTextAlignment(Qt.AlignCenter)
            self.config_table.setItem(row, 3, production_item)
            
            row += 1
            
        self.config_table.resizeColumnsToContents()
        
    def set_spc_integration(self, integration: SPCIntegration):
        """Set the SPC integration instance"""
        self.spc_integration = integration
        
    def add_test_results(self, sku: str, test_results: Dict):
        """Add test results to SPC data collection"""
        # This method can be called to manually add results
        if 'measurements' in test_results:
            for function_key, function_data in test_results['measurements'].items():
                if function_key.endswith('_readings'):
                    function = function_key.replace('_readings', '')
                    board_results = function_data.get('board_results', {})
                    
                    for board, measurements in board_results.items():
                        if 'current' in measurements:
                            board_key = board.replace(' ', '_')
                            self.data_collector.add_measurement(
                                sku, function, board_key,
                                measurements['current'],
                                measurements.get('voltage')
                            )


# Standalone test window
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("Enhanced SPC Control Widget")
    
    widget = SPCWidget()
    widget.update_sku_list(["DD5001", "DD5002", "DD5003"])
    
    window.setCentralWidget(widget)
    window.resize(1200, 900)
    window.show()
    
    sys.exit(app.exec())