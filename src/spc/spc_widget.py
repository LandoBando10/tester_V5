"""
SPC Control Widget for SMT Testing
Provides visualization and control for Statistical Process Control

Features:
- Real-time control chart display
- Control limit visualization
- Process capability display
- Sample collection status
- Export capabilities
"""

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QComboBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QFileDialog,
    QMessageBox, QProgressBar, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

from pathlib import Path
from typing import Dict, Optional, List
import numpy as np
from datetime import datetime

from src.spc.spc_calculator import SPCCalculator, ControlLimits
from src.spc.data_collector import SPCDataCollector


class SPCControlWidget(QWidget):
    """Widget for SPC visualization and control"""
    
    # Signals
    limits_updated = pyqtSignal(str, dict)  # SKU, limits dict
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_sku = None
        self.data_collector = SPCDataCollector()
        self.calculator = SPCCalculator()
        
        self.init_ui()
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.refresh_display)
        self.update_timer.start(5000)  # Update every 5 seconds
        
    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout()
        
        # Control section
        control_group = self.create_control_section()
        layout.addWidget(control_group)
        
        # Chart section
        chart_group = self.create_chart_section()
        layout.addWidget(chart_group, 1)
        
        # Status section
        status_group = self.create_status_section()
        layout.addWidget(status_group)
        
        self.setLayout(layout)
        
    def create_control_section(self) -> QGroupBox:
        """Create control section"""
        group = QGroupBox("SPC Control")
        layout = QHBoxLayout()
        
        # SKU selector
        layout.addWidget(QLabel("SKU:"))
        self.sku_combo = QComboBox()
        self.sku_combo.currentTextChanged.connect(self.on_sku_changed)
        layout.addWidget(self.sku_combo)
        
        # Function selector
        layout.addWidget(QLabel("Function:"))
        self.function_combo = QComboBox()
        self.function_combo.currentTextChanged.connect(self.on_function_changed)
        layout.addWidget(self.function_combo)
        
        # Board selector
        layout.addWidget(QLabel("Board:"))
        self.board_combo = QComboBox()
        self.board_combo.currentTextChanged.connect(self.refresh_display)
        layout.addWidget(self.board_combo)
        
        layout.addStretch()
        
        # Sample size control
        layout.addWidget(QLabel("Subgroup Size:"))
        self.sample_size_spin = QSpinBox()
        self.sample_size_spin.setRange(2, 10)
        self.sample_size_spin.setValue(5)
        self.sample_size_spin.valueChanged.connect(self.on_sample_size_changed)
        layout.addWidget(self.sample_size_spin)
        
        # Auto-update checkbox
        self.auto_update_check = QCheckBox("Auto Update")
        self.auto_update_check.setChecked(True)
        layout.addWidget(self.auto_update_check)
        
        # Calculate button
        self.calculate_btn = QPushButton("Calculate Limits")
        self.calculate_btn.clicked.connect(self.calculate_limits)
        layout.addWidget(self.calculate_btn)
        
        # Export button
        self.export_btn = QPushButton("Export Report")
        self.export_btn.clicked.connect(self.export_report)
        layout.addWidget(self.export_btn)
        
        group.setLayout(layout)
        return group
        
    def create_chart_section(self) -> QGroupBox:
        """Create chart display section"""
        group = QGroupBox("Control Charts")
        layout = QVBoxLayout()
        
        # Create matplotlib figure
        self.figure = Figure(figsize=(10, 6))
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
        
        self.limits_table = QTableWidget(7, 2)
        self.limits_table.setHorizontalHeaderLabels(["Parameter", "Value"])
        self.limits_table.verticalHeader().setVisible(False)
        self.limits_table.setMaximumHeight(200)
        
        # Set row headers
        rows = [
            "X̄ UCL", "X̄ CL", "X̄ LCL",
            "R UCL", "R CL", "R LCL",
            "Cpk"
        ]
        for i, label in enumerate(rows):
            self.limits_table.setItem(i, 0, QTableWidgetItem(label))
            
        left_layout.addWidget(QLabel("Control Limits:"))
        left_layout.addWidget(self.limits_table)
        
        # Right side - collection status
        right_layout = QVBoxLayout()
        
        self.status_labels = {
            'subgroups': QLabel("Subgroups Collected: 0"),
            'last_update': QLabel("Last Update: Never"),
            'status': QLabel("Status: Waiting for data...")
        }
        
        for label in self.status_labels.values():
            right_layout.addWidget(label)
            
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(6)  # 6 subgroups = 30 measurements
        right_layout.addWidget(self.progress_bar)
        
        layout.addLayout(left_layout)
        layout.addStretch()
        layout.addLayout(right_layout)
        
        group.setLayout(layout)
        return group
        
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
        
        # Update function list based on available data
        # This would normally read from SKU config
        functions = ["mainbeam", "backlight_left", "backlight_right"]
        self.function_combo.clear()
        self.function_combo.addItems(functions)
        
    def on_function_changed(self, function: str):
        """Handle function selection change"""
        if not function:
            return
            
        # Update board list
        # For now, assume 2 boards per panel
        boards = ["Board_1", "Board_2"]
        self.board_combo.clear()
        self.board_combo.addItems(boards)
        
    def on_sample_size_changed(self, size: int):
        """Handle sample size change"""
        self.data_collector.subgroup_size = size
        
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
            self.display_limits(limits)
            self.plot_control_charts(sku, function, board, limits)
        else:
            self.status_labels['status'].setText("Status: Collecting initial data...")
            
        # Update collection status
        self.update_collection_status(sku, function, board)
        
    def display_limits(self, limits: ControlLimits):
        """Display control limits in table"""
        values = [
            f"{limits.xbar_ucl:.4f}",
            f"{limits.xbar_cl:.4f}",
            f"{limits.xbar_lcl:.4f}",
            f"{limits.r_ucl:.4f}",
            f"{limits.r_cl:.4f}",
            f"{limits.r_lcl:.4f}",
            f"{limits.cpk:.3f}" if limits.cpk else "N/A"
        ]
        
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
            import json
            with open(filename, 'r') as f:
                data = json.load(f)
                
            # Extract subgroup statistics
            subgroup_means = []
            subgroup_ranges = []
            
            for subgroup_data in data:
                currents = [m['current'] for m in subgroup_data['measurements']]
                subgroup_means.append(np.mean(currents))
                subgroup_ranges.append(np.max(currents) - np.min(currents))
                
            # Create subplots
            ax1 = self.figure.add_subplot(2, 1, 1)
            ax2 = self.figure.add_subplot(2, 1, 2)
            
            # X-bar chart
            x = range(1, len(subgroup_means) + 1)
            ax1.plot(x, subgroup_means, 'b-o', markersize=4)
            ax1.axhline(y=limits.xbar_ucl, color='r', linestyle='--', label='UCL')
            ax1.axhline(y=limits.xbar_cl, color='g', linestyle='-', label='CL')
            ax1.axhline(y=limits.xbar_lcl, color='r', linestyle='--', label='LCL')
            ax1.set_ylabel('Current (A)')
            ax1.set_title(f'X̄ Control Chart - {sku} {function} {board}')
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            
            # R chart
            ax2.plot(x, subgroup_ranges, 'b-o', markersize=4)
            ax2.axhline(y=limits.r_ucl, color='r', linestyle='--', label='UCL')
            ax2.axhline(y=limits.r_cl, color='g', linestyle='-', label='CL')
            ax2.axhline(y=limits.r_lcl, color='r', linestyle='--', label='LCL')
            ax2.set_xlabel('Subgroup')
            ax2.set_ylabel('Range (A)')
            ax2.set_title('R Control Chart')
            ax2.grid(True, alpha=0.3)
            ax2.legend()
            
            # Check for out-of-control points
            violations = self.calculator.check_control_rules(subgroup_means, limits)
            if violations:
                for violation in violations:
                    if 'index' in violation:
                        ax1.plot(violation['index'] + 1, subgroup_means[violation['index']], 
                                'ro', markersize=10, fillstyle='none')
                        
            self.figure.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            print(f"Error plotting charts: {e}")
            
    def update_collection_status(self, sku: str, function: str, board: str):
        """Update data collection status display"""
        filename = self.data_collector.data_dir / f"{sku}_{function}_{board}_subgroups.json"
        
        if filename.exists():
            try:
                import json
                with open(filename, 'r') as f:
                    data = json.load(f)
                    
                count = len(data)
                self.status_labels['subgroups'].setText(f"Subgroups Collected: {count}")
                self.progress_bar.setValue(min(count, self.progress_bar.maximum()))
                
                if data:
                    last_time = data[-1]['timestamp']
                    self.status_labels['last_update'].setText(f"Last Update: {last_time[:19]}")
                    
                if count >= self.data_collector.min_subgroups:
                    self.status_labels['status'].setText("Status: Ready for production")
                    self.status_labels['status'].setStyleSheet("color: green")
                else:
                    remaining = self.data_collector.min_subgroups - count
                    self.status_labels['status'].setText(f"Status: Need {remaining} more subgroups")
                    self.status_labels['status'].setStyleSheet("color: orange")
                    
            except:
                pass
                
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
                              
    def export_report(self):
        """Export SPC report"""
        sku = self.sku_combo.currentText()
        if not sku:
            QMessageBox.warning(self, "Warning", "Please select a SKU")
            return
            
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export SPC Report", 
            f"{sku}_spc_report_{datetime.now():%Y%m%d_%H%M%S}.json",
            "JSON Files (*.json)"
        )
        
        if filename:
            self.data_collector.export_spc_report(sku, Path(filename))
            QMessageBox.information(self, "Success", f"Report exported to {filename}")
            
    def add_test_results(self, sku: str, test_results: Dict):
        """Add test results to SPC data collection"""
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
    from PyQt5.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("SPC Control Test")
    
    widget = SPCControlWidget()
    widget.update_sku_list(["DD5001", "DD5002", "DD5003"])
    
    window.setCentralWidget(widget)
    window.resize(1000, 800)
    window.show()
    
    sys.exit(app.exec_())
