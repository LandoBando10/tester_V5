# gui/components/offroad_widget.py
import os
import time
from datetime import datetime
from collections import deque
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QSplitter, QTableWidget,
    QTableWidgetItem, QHeaderView, QTextEdit
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor

# Defer pyqtgraph import until needed
PYQTGRAPH_AVAILABLE = None
pg = None

def _ensure_pyqtgraph():
    """Lazy load pyqtgraph when needed"""
    global PYQTGRAPH_AVAILABLE, pg
    if PYQTGRAPH_AVAILABLE is None:
        try:
            os.environ['PYQTGRAPH_QT_LIB'] = 'PySide6'
            import pyqtgraph
            pg = pyqtgraph
            PYQTGRAPH_AVAILABLE = True
        except ImportError:
            PYQTGRAPH_AVAILABLE = False
            print("Warning: pyqtgraph not available. Live pressure graphs will be disabled.")
            print("Install with: pip install pyqtgraph")
    return PYQTGRAPH_AVAILABLE

from src.core.base_test import TestResult


class ParameterResultsTable(QTableWidget):
    """Table widget for displaying test parameter results"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_table()
    
    def setup_table(self):
        """Setup the table structure"""
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["Parameter", "Target Range", "Measured", "Result"])
        
        # Style the table
        self.setStyleSheet("""
            QTableWidget {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #555555;
                border-radius: 5px;
                gridline-color: #555555;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #444444;
            }
            QTableWidget::item:selected {
                background-color: #4a90a4;
            }
            QHeaderView::section {
                background-color: #444444;
                color: white;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)
        
        # Configure headers
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        
    def add_parameter_result(self, parameter: str, target_range: str, measured: str, passed: bool):
        """Add a parameter result to the table"""
        row = self.rowCount()
        self.insertRow(row)
        
        # Parameter name
        param_item = QTableWidgetItem(parameter)
        param_item.setFlags(param_item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 0, param_item)
        
        # Target range
        range_item = QTableWidgetItem(target_range)
        range_item.setFlags(range_item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 1, range_item)
        
        # Measured value
        measured_item = QTableWidgetItem(measured)
        measured_item.setFlags(measured_item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 2, measured_item)
        
        # Result (PASS/FAIL)
        result_text = "PASS" if passed else "FAIL"
        result_item = QTableWidgetItem(result_text)
        result_item.setFlags(result_item.flags() & ~Qt.ItemIsEditable)
        
        # Color coding
        if passed:
            result_item.setBackground(QColor("#2d5a2d"))
            result_item.setForeground(QColor("#51cf66"))
        else:
            result_item.setBackground(QColor("#5a2d2d"))
            result_item.setForeground(QColor("#ff6b6b"))
        
        self.setItem(row, 3, result_item)
        
    def clear_results(self):
        """Clear all results from the table"""
        self.setRowCount(0)
        
    def update_from_test_result(self, result: TestResult):
        """Update table with TestResult data"""
        self.clear_results()
        
        if not result.measurements:
            return
        
        # Custom sort to group by type and board number
        def sort_key(item):
            name = item[0]
            if "mainbeam_board_" in name:
                try:
                    board_num = int(name.split('_')[2])
                    return (0, board_num)
                except:
                    return (0, 999)
            elif name == "mainbeam_average_current":
                return (1, 0)
            elif "backlight_board_" in name:
                try:
                    board_num = int(name.split('_')[2])
                    return (2, board_num)
                except:
                    return (2, 999)
            elif name == "backlight_average_current":
                return (3, 0)
            else:
                return (4, 0)
        
        # Sort measurements
        sorted_measurements = sorted(result.measurements.items(), key=sort_key)
            
        for name, data in sorted_measurements:
            # Skip average measurements
            if "average" in name.lower():
                continue
                
            if isinstance(data, dict) and 'value' in data:
                # Format parameter name
                param_name = self._format_parameter_name(name)
                
                # Format range
                min_val = data.get('min', '')
                max_val = data.get('max', '')
                unit = data.get('unit', '')
                
                if min_val != '' and max_val != '':
                    target_range = f"{min_val} - {max_val} {unit}".strip()
                else:
                    target_range = "N/A"
                
                # Format measured value
                value = data['value']
                if isinstance(value, float):
                    measured = f"{value:.3f} {unit}".strip()
                else:
                    measured = f"{value} {unit}".strip()
                
                # Pass/fail status
                passed = data.get('passed', True)
                
                self.add_parameter_result(param_name, target_range, measured, passed)
    
    def _format_parameter_name(self, name: str) -> str:
        """Format parameter name for display"""
        formatted = name.replace('_', ' ').title()
        return formatted


class PressureGraphWidget(QWidget):
    """Live pressure graph widget using pyqtgraph (with fallback)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_graph()
        self.time_data = deque(maxlen=300)  # 30 seconds at 10Hz
        self.pressure_data = deque(maxlen=300)
        self.start_time = None
        
    def setup_graph(self):
        """Setup the pressure graph"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        if _ensure_pyqtgraph():
            # Create pyqtgraph plot widget
            self.plot_widget = pg.PlotWidget()
            self.plot_widget.setBackground('#2b2b2b')
            self.plot_widget.setLabel('left', 'Pressure (PSI)', color='white', size='12pt')
            self.plot_widget.setLabel('bottom', 'Time (seconds)', color='white', size='12pt')
            self.plot_widget.setTitle('Live Pressure Data', color='white', size='14pt')
            
            # Style the plot
            self.plot_widget.getAxis('left').setPen(color='white')
            self.plot_widget.getAxis('bottom').setPen(color='white')
            self.plot_widget.getAxis('left').setTextPen(color='white')
            self.plot_widget.getAxis('bottom').setTextPen(color='white')
            
            # Add grid
            self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
            
            # Create plot curve
            self.pressure_curve = self.plot_widget.plot(
                pen=pg.mkPen(color='#4a90a4', width=2),
                symbol='o',
                symbolSize=4,
                symbolBrush='#4a90a4'
            )
            
            layout.addWidget(self.plot_widget)
        else:
            # Fallback: simple text display
            title_label = QLabel("Live Pressure Data")
            title_label.setStyleSheet("color: white; font-size: 14pt; font-weight: bold;")
            title_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(title_label)
            
            # Pressure display area
            self.pressure_display = QLabel("Waiting for pressure data...")
            self.pressure_display.setStyleSheet("""
                QLabel {
                    background-color: #1e1e1e;
                    color: #4a90a4;
                    border: 2px solid #4a90a4;
                    border-radius: 8px;
                    padding: 20px;
                    font-size: 24px;
                    font-weight: bold;
                }
            """)
            self.pressure_display.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.pressure_display)
            
            # Text data display
            self.data_display = QTextEdit()
            self.data_display.setMaximumHeight(150)
            self.data_display.setStyleSheet("""
                QTextEdit {
                    background-color: #1e1e1e;
                    color: white;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    font-family: 'Courier New';
                    font-size: 10px;
                }
            """)
            self.data_display.setReadOnly(True)
            layout.addWidget(self.data_display)
        
        # Status label
        self.status_label = QLabel("Waiting for pressure data...")
        self.status_label.setStyleSheet("color: #888888; font-size: 12px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
    def add_pressure_point(self, pressure: float):
        """Add a new pressure data point"""
        current_time = time.time()
        
        if self.start_time is None:
            self.start_time = current_time
            
        elapsed_time = current_time - self.start_time
        
        self.time_data.append(elapsed_time)
        self.pressure_data.append(pressure)
        
        if _ensure_pyqtgraph():
            # Update plot
            self.pressure_curve.setData(list(self.time_data), list(self.pressure_data))
        else:
            # Update fallback displays
            self.pressure_display.setText(f"{pressure:.2f} PSI")
            
            # Add to text log
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {elapsed_time:.1f}s: {pressure:.2f} PSI\n"
            self.data_display.append(log_entry)
            
            # Keep only recent entries
            text = self.data_display.toPlainText()
            lines = text.split('\n')
            if len(lines) > 20:
                self.data_display.setPlainText('\n'.join(lines[-20:]))
        
        # Update status
        self.status_label.setText(f"Current Pressure: {pressure:.2f} PSI (Time: {elapsed_time:.1f}s)")
        
    def clear_data(self):
        """Clear all pressure data"""
        self.time_data.clear()
        self.pressure_data.clear()
        self.start_time = None
        
        if _ensure_pyqtgraph():
            self.pressure_curve.setData([], [])
        else:
            self.pressure_display.setText("Waiting for pressure data...")
            self.data_display.clear()
            
        self.status_label.setText("Waiting for pressure data...")


class TestVisualsArea(QWidget):
    """Right side visuals area for offroad tests"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.pressure_graph = None
        
    def setup_ui(self):
        """Setup the visuals area"""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title_label = QLabel("Test Visuals")
        title_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(title_label)
        
        # Content area
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.layout.addWidget(self.content_area)
        
        # Default state
        self.show_default_state()
        
    def show_default_state(self):
        """Show default state (no active test)"""
        self.clear_content()
        
        placeholder = QLabel("Visuals will appear here during testing")
        placeholder.setStyleSheet("color: #888888; font-size: 14px;")
        placeholder.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(placeholder)
        
    def show_pressure_graph(self):
        """Show live pressure graph"""
        self.clear_content()
        
        if not self.pressure_graph:
            self.pressure_graph = PressureGraphWidget()
            
        if not _ensure_pyqtgraph():
            # Add a note about the fallback mode
            note_label = QLabel("Note: Install pyqtgraph for enhanced live graphing")
            note_label.setStyleSheet("color: #888888; font-size: 10px; font-style: italic;")
            note_label.setAlignment(Qt.AlignCenter)
            self.content_layout.addWidget(note_label)
            
        self.content_layout.addWidget(self.pressure_graph)
        
    def show_test_summary(self, test_type: str, passed: bool):
        """Show test completion summary"""
        self.clear_content()
        
        # Test type label
        type_label = QLabel(f"{test_type} Test Complete")
        type_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        type_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(type_label)
        
        # Result indicator
        if passed:
            result_label = QLabel("✓ PASSED")
            result_label.setStyleSheet("color: #51cf66; font-size: 24px; font-weight: bold;")
        else:
            result_label = QLabel("✗ FAILED")
            result_label.setStyleSheet("color: #ff6b6b; font-size: 24px; font-weight: bold;")
            
        result_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(result_label)
        
        # Add stretch to center content
        self.content_layout.addStretch()
        
    def add_pressure_point(self, pressure: float):
        """Add pressure data point (delegates to pressure graph)"""
        if self.pressure_graph:
            self.pressure_graph.add_pressure_point(pressure)
            
    def clear_content(self):
        """Clear content area"""
        for i in reversed(range(self.content_layout.count())):
            child = self.content_layout.itemAt(i)
            if child and child.widget():
                child.widget().setParent(None)


class OffroadWidget(QWidget):
    """Dedicated widget for Offroad testing mode"""
    
    # Signals
    test_started = Signal(str, dict)  # sku, params
    test_completed = Signal(object)   # TestResult
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_test_type = None
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the offroad testing UI"""
        # Create horizontal splitter for left/right layout
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #555555;
                width: 3px;
            }
            QSplitter::handle:hover {
                background-color: #666666;
            }
        """)
        
        # Left side - Results table
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        # Results table title
        results_title = QLabel("Test Results")
        results_title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        results_title.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(results_title)
        
        # Results table
        self.results_table = ParameterResultsTable()
        left_layout.addWidget(self.results_table)
        
        # Right side - Visuals
        self.visuals_area = TestVisualsArea()
        
        # Add to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(self.visuals_area)
        
        # Set splitter proportions (60% left, 40% right)
        splitter.setSizes([600, 400])
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        
    def display_results(self, result: TestResult):
        """Display test results"""
        try:
            # Update results table
            self.results_table.update_from_test_result(result)
            
            # Show completion in visuals area
            test_type = getattr(result, 'test_type', 'Test')
            self.visuals_area.show_test_summary(test_type, result.passed)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(self.__class__.__name__)
            logger.error(f"Error displaying results: {e}")
            
    def set_testing_state(self, testing: bool):
        """Update UI for testing state"""
        if testing:
            # Clear previous results
            self.results_table.clear_results()
            # Show default state in visuals
            self.visuals_area.show_default_state()
                    
    def start_pressure_test(self):
        """Start pressure test - show live graph"""
        self.current_test_type = "pressure"
        self.visuals_area.show_pressure_graph()
        
    def add_pressure_data(self, pressure: float):
        """Add pressure data point during live test"""
        if self.current_test_type == "pressure":
            self.visuals_area.add_pressure_point(pressure)
            
    def end_pressure_test(self):
        """End pressure test"""
        self.current_test_type = None
        
    def cleanup(self):
        """Cleanup the widget"""
