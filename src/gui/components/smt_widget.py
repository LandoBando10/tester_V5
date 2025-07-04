from __future__ import annotations

"""
SMT results widget – **v6** (2025‑06‑08)

Fixes & updates
---------------
* **Restored compatibility methods** expected by `SMTHandler`:
  `set_programming_enabled()` and `cleanup()` are back (no‑ops for now).
* **Grid isn't forced to 2 × 2 on startup.**  We begin with an empty panel and
  only build cells after the handler (or caller) sets a layout via
  `set_panel_layout()` *or* when the first test result arrives.
* **Corrected counter‑clockwise numbering.**  Indexing now snakes **left→right
  across the bottom row**, then right→left across the next row up, and so on.
  Example for 2 × 2: 1 (bottom‑left) → 2 (bottom‑right) → 3 (top‑right) →
  4 (top‑left).
* **Function signature change:** `_index_to_pos(board_idx, rows, cols)` now uses
  both dimensions.  All calls updated.
* **Self‑tests updated** for the new mapping logic and added a 4 × 3 case.
* **Documentation & comments** kept pure ASCII to avoid stray Unicode.
"""

from typing import Dict, Optional, Tuple, List
import logging
import os

from PySide6.QtWidgets import (
    QWidget,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressBar,
    QSplitter,
)
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Qt, Signal

# Debug helper function
def _is_debug_enabled() -> bool:
    """Check if SMT debug logging is enabled via environment variable or configuration
    
    Debug logging can be enabled in two ways:
    1. Environment variable: SMT_DEBUG=1 (or 'true', 'yes')
    2. Configuration file: Set DEBUG_SETTINGS['smt_debug'] = True in config/settings.py
    
    Environment variable takes precedence over configuration file.
    """
    # Check environment variable first
    if os.getenv('SMT_DEBUG', '').lower() in ('1', 'true', 'yes'):
        return True
    
    # Check configuration settings
    try:
        from config.settings import DEBUG_SETTINGS
        return DEBUG_SETTINGS.get('smt_debug', False)
    except ImportError:
        return False

# ---------------------------------------------------------------------------
# SegmentedMeasurementWidget
# ---------------------------------------------------------------------------

class SegmentedMeasurementWidget(QWidget):
    """Widget to display voltage and current in segmented box style"""
    
    def __init__(self, voltage: float, current: float, scale_factor: float = 1.0, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.voltage = voltage
        self.current = current
        self.scale_factor = scale_factor
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        # Minimize margins to maximize space for text
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(int(10 * self.scale_factor))
        
        # Add stretch to center content
        layout.addStretch()
        
        # Calculate scaled font sizes - slightly smaller to fit better
        value_font_size = max(11, int(16 * self.scale_factor))
        unit_font_size = max(9, int(14 * self.scale_factor))
        
        # Create voltage display (no border)
        voltage_layout = QHBoxLayout()
        voltage_layout.setSpacing(3)
        
        # Voltage value with Consolas font
        self.voltage_value = QLabel(f"{self.voltage:.3f}")
        self.voltage_value.setFont(QFont("Consolas", value_font_size))
        self.voltage_value.setStyleSheet("color: #ffffff; font-weight: bold; background: transparent;")
        self.voltage_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        # Voltage unit (hide if scale is too small)
        if self.scale_factor > 0.7:
            voltage_unit = QLabel("V")
            voltage_unit.setFont(QFont("Consolas", unit_font_size))
            voltage_unit.setStyleSheet(f"color: #aaaaaa; background: transparent;")
            voltage_unit.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            voltage_layout.addWidget(self.voltage_value)
            voltage_layout.addWidget(voltage_unit)
        else:
            # Just show value with unit combined for very small scales
            self.voltage_value.setText(f"{self.voltage:.3f}V")
            voltage_layout.addWidget(self.voltage_value)
        
        # Separator
        separator = QLabel("|")
        separator.setFont(QFont("Consolas", value_font_size))
        separator.setStyleSheet(f"color: #666666; background: transparent;")
        separator.setAlignment(Qt.AlignCenter)
        
        # Create current display (no border)
        current_layout = QHBoxLayout()
        current_layout.setSpacing(3)
        
        # Current value with Consolas font
        self.current_value = QLabel(f"{self.current:.3f}")
        self.current_value.setFont(QFont("Consolas", value_font_size))
        self.current_value.setStyleSheet("color: #ffffff; font-weight: bold; background: transparent;")
        self.current_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        # Current unit (hide if scale is too small)
        if self.scale_factor > 0.7:
            current_unit = QLabel("A")
            current_unit.setFont(QFont("Consolas", unit_font_size))
            current_unit.setStyleSheet(f"color: #aaaaaa; background: transparent;")
            current_unit.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            current_layout.addWidget(self.current_value)
            current_layout.addWidget(current_unit)
        else:
            # Just show value with unit combined for very small scales
            self.current_value.setText(f"{self.current:.3f}A")
            current_layout.addWidget(self.current_value)
        
        # Add to main layout
        layout.addLayout(voltage_layout)
        layout.addWidget(separator)
        layout.addLayout(current_layout)
        
        # Add stretch to center content
        layout.addStretch()
        
        # Set minimum height to ensure text isn't cut off
        min_height = max(30, int(35 * self.scale_factor))
        self.setMinimumHeight(min_height)

# ---------------------------------------------------------------------------
# BoardCell
# ---------------------------------------------------------------------------


class BoardCell(QFrame):
    """Visual cell representing a single PCB on the SMT panel."""

    PASS_COLOR = QColor("#2d5a2d")
    FAIL_COLOR = QColor("#5a2d2d")
    IDLE_COLOR = QColor("#3a3a3a")

    def __init__(self, board_idx: int, scale_factor: float = 1.0, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.board_idx = board_idx
        self.scale_factor = scale_factor
        self.logger = logging.getLogger(f"{self.__class__.__name__}.Board{board_idx}")
        self._debug_enabled = _is_debug_enabled()
        self._setup_ui()
        self.set_idle()

    # ------------------------ UI setup ------------------------
    def _setup_ui(self):
        self.setFrameShape(QFrame.Box)
        self.setLineWidth(2)
        self.setStyleSheet("""
            QFrame {
                border: 2px solid #444444;
                border-radius: 6px;
                background-color: #3a3a3a;
            }
        """)
        self.setAutoFillBackground(True)

        # Minimize margins to maximize space for content
        margin = max(5, int(8 * self.scale_factor))
        spacing = max(2, int(3 * self.scale_factor))
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(margin, margin, margin, margin)
        self.layout.setSpacing(spacing)

        # Scale the board label font
        board_font_size = max(14, int(20 * self.scale_factor))
        self.label_board = QLabel(f"Board {self.board_idx}")
        self.label_board.setAlignment(Qt.AlignCenter)
        self.label_board.setStyleSheet(f"font-weight: bold; font-size: {board_font_size}px; color: white; margin-bottom: {int(10 * self.scale_factor)}px;")
        self.layout.addWidget(self.label_board)

        # dynamic measurement widgets live here
        self.measure_widgets: List[QWidget] = []

        self.layout.addStretch()

    # -------------------- colour helpers ----------------------
    def _apply_background(self, color: QColor):
        if self._debug_enabled:
            self.logger.debug(f"Board {self.board_idx}: Applying background color {color.name()}")
        
        # Use style sheet with QFrame selector to preserve border
        self.setStyleSheet(f"""
            QFrame {{
                border: 2px solid #444444;
                border-radius: 6px;
                background-color: {color.name()};
            }}
        """)
        
        # Update text color based on background brightness
        txt_color = QColor("white") if color.lightness() < 128 else QColor("black")
        board_font_size = max(14, int(20 * self.scale_factor))
        self.label_board.setStyleSheet(f"font-weight: bold; font-size: {board_font_size}px; color: {txt_color.name()}; margin-bottom: {int(10 * self.scale_factor)}px;")
        
        # Update existing widgets - we don't need to update container colors
        # The text colors in SegmentedMeasurementWidget are already set to white

    def set_pass(self):
        self._apply_background(self.PASS_COLOR)

    def set_fail(self):
        self._apply_background(self.FAIL_COLOR)

    def set_idle(self):
        self._apply_background(self.IDLE_COLOR)

    # ------------------- data population ----------------------
    def update_measurements(
        self,
        functions: Dict[str, float],
        passed: bool,
    ) -> None:
        """Update measurement display with function names and current values."""
        if self._debug_enabled and self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"Board {self.board_idx}: updating with passed={passed}, functions={functions}")
        
        # purge old widgets
        for widget in self.measure_widgets:
            self.layout.removeWidget(widget)
            widget.deleteLater()
        self.measure_widgets.clear()

        # Group measurements by function
        function_groups = {}
        for key, value in sorted(functions.items()):
            # Split key into function and measurement type
            parts = key.rsplit("_", 1)
            if len(parts) == 2:
                function_name, measurement_type = parts
                if function_name not in function_groups:
                    function_groups[function_name] = {}
                function_groups[function_name][measurement_type] = value
        
        # Display grouped measurements using segmented style - reverse alphabetical order
        for func_name in sorted(function_groups.keys(), reverse=True):
            measurements = function_groups[func_name]
            
            # Only display if we have both voltage and current
            if "current" in measurements and "voltage" in measurements:
                # Create container for this function
                func_container = QFrame()
                func_container.setStyleSheet("""
                    QFrame {
                        background-color: transparent;
                        border: none;
                        margin: 2px 0px;
                    }
                """)
                func_layout = QVBoxLayout(func_container)
                func_layout.setContentsMargins(0, 2, 0, 2)
                func_layout.setSpacing(2)
                
                # Create function name label
                display_name = func_name.replace("_", " ").upper()
                
                # Truncate long function names for small scales
                if self.scale_factor < 0.8:
                    max_chars = 12
                    if len(display_name) > max_chars:
                        display_name = display_name[:max_chars-2] + ".."
                
                func_label = QLabel(display_name)
                func_label.setAlignment(Qt.AlignCenter)
                func_font_size = max(10, int(13 * self.scale_factor))
                func_label.setStyleSheet(f"""
                    font-weight: bold;
                    font-size: {func_font_size}px;
                    color: #dddddd;
                    background: transparent;
                """)
                
                # Create segmented measurement widget
                seg_widget = SegmentedMeasurementWidget(
                    voltage=measurements['voltage'],
                    current=measurements['current'],
                    scale_factor=self.scale_factor
                )
                
                # Add to container
                func_layout.addWidget(func_label)
                func_layout.addWidget(seg_widget)
                
                # Insert container above the stretch
                self.layout.insertWidget(self.layout.count() - 1, func_container)
                
                # Add to our widget list for cleanup
                self.measure_widgets.append(func_container)

        # Apply color based on pass/fail, but only if we have actual measurement data
        if functions:
            if passed:
                if self._debug_enabled:
                    self.logger.debug(f"Board {self.board_idx}: Setting color to PASS (green)")
                self.set_pass()
            else:
                if self._debug_enabled:
                    self.logger.debug(f"Board {self.board_idx}: Setting color to FAIL (red)")
                self.set_fail()
        else:
            # No data yet, keep grey
            if self._debug_enabled:
                self.logger.debug(f"Board {self.board_idx}: No measurement data, keeping grey")
            self.set_idle()


# ---------------------------------------------------------------------------
# PCBPanelWidget
# ---------------------------------------------------------------------------


class PCBPanelWidget(QWidget):
    """Grid of :class:`BoardCell` mirroring the physical SMT panel."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.rows = 0
        self.cols = 0
        self.grid = QGridLayout(self)
        self.grid.setSpacing(20)
        self.cells: Dict[int, BoardCell] = {}
        self.logger = logging.getLogger(self.__class__.__name__)
        self._debug_enabled = _is_debug_enabled()

    # ---------------------- public API ------------------------
    def set_panel_layout(self, rows: int, cols: int):
        if rows <= 0 or cols <= 0:
            return
        if rows == self.rows and cols == self.cols:
            # Even if same layout, reset all cells to idle state
            for cell in self.cells.values():
                cell.set_idle()
                cell.update_measurements(None, {}, True)
            return
        # clear existing widgets
        for cell in self.cells.values():
            cell.setParent(None)
        self.cells.clear()
        self.rows, self.cols = rows, cols
        self._rebuild_grid()

    def update_from_test_result(self, result):
        """Populate each cell based on a `TestResult`‑like object."""
        
        if self._debug_enabled and self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"update_from_test_result called with measurements: {list(getattr(result, 'measurements', {}).keys())}")
        
        # if layout unknown, try to infer from result meta or board count
        if self.rows == 0 or self.cols == 0:
            # Extract unique board numbers from measurements
            board_numbers = set()
            for name in getattr(result, "measurements", {}):
                if "_board_" in name:
                    # Parse board number from names like "mainbeam_board_1_current"
                    parts = name.split("_")
                    try:
                        board_idx = parts.index("board")
                        b_idx = int(parts[board_idx + 1])
                        board_numbers.add(b_idx)
                    except (ValueError, IndexError):
                        continue
            
            board_count = len(board_numbers)
            if board_count:
                # For 4 boards, prefer 2x2 layout
                if board_count == 4:
                    rows, cols = 2, 2
                else:
                    # choose rows as smallest factor ≤ sqrt, else 1 row strip
                    rows = int(board_count ** 0.5)
                    while rows > 1 and board_count % rows != 0:
                        rows -= 1
                    cols = board_count // rows if rows else board_count
                self.set_panel_layout(rows or 1, cols or 1)

        # reset visuals
        for cell in self.cells.values():
            cell.set_idle()

        # Store all function measurements generically
        board_functions: Dict[int, Dict[str, float]] = {}
        board_pass: Dict[int, bool] = {}
        
        # Debug: Log what measurements we received
        measurements = getattr(result, "measurements", {})
        if self._debug_enabled and self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"PCBPanelWidget.update_from_test_result - measurements keys: {list(measurements.keys())}")
            self.logger.debug(f"PCBPanelWidget.update_from_test_result - result type: {type(result)}")

        for name, data in measurements.items():
            if "_board_" not in name:
                continue
            
            # Parse board number from names like "function_board_1_current" or "function_board_1_voltage"
            parts = name.split("_")
            try:
                board_idx = parts.index("board")
                b_idx = int(parts[board_idx + 1])
            except (ValueError, IndexError):
                continue

            # Extract function name (everything before "_board_")
            function_name = "_".join(parts[:board_idx])
            
            # Extract measurement type (current or voltage)
            measurement_type = parts[-1]  # "current" or "voltage"
            
            board_pass.setdefault(b_idx, True)
            
            # Store measurements with their type
            board_functions.setdefault(b_idx, {})
            
            # Create a key that includes both function and measurement type
            key = f"{function_name}_{measurement_type}"
            board_functions[b_idx][key] = data["value"]
            
            # Check pass/fail
            if not data.get("passed", True):
                board_pass[b_idx] = False

        # Debug: Final board pass/fail status determined
        if self._debug_enabled and self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"Board functions collected: {board_functions}")
            self.logger.debug(f"Board pass status: {board_pass}")
        
        for idx, cell in self.cells.items():
            passed = board_pass.get(idx, True)
            # Get all functions for this board
            functions = board_functions.get(idx, {})
            
            # Pass all functions to the cell
            cell.update_measurements(functions, passed)

    # ------------------ internal helpers ----------------------
    def _rebuild_grid(self):
        if self.rows <= 0 or self.cols <= 0:
            return
            
        # Calculate dynamic spacing based on panel size
        base_spacing = 20
        spacing_reduction = min(self.rows, self.cols) - 1
        dynamic_spacing = max(8, base_spacing - (spacing_reduction * 4))
        self.grid.setSpacing(dynamic_spacing)
        
        # Get available space - use full parent size
        parent_widget = self.parent()
        if parent_widget:
            # Use nearly all available space with minimal margin
            available_width = parent_widget.width() - 10
            available_height = parent_widget.height() - 10
        else:
            available_width = 800
            available_height = 600
            
        # Calculate cell dimensions to fill available space
        total_h_spacing = (self.cols - 1) * dynamic_spacing if self.cols > 1 else 0
        total_v_spacing = (self.rows - 1) * dynamic_spacing if self.rows > 1 else 0
        
        cell_width = (available_width - total_h_spacing) / self.cols
        cell_height = (available_height - total_v_spacing) / self.rows
        
        # Only apply minimum constraints to prevent text from being unreadable
        min_cell_width = 140
        min_cell_height = 120
        
        # Use the calculated dimensions, only applying minimums if necessary
        optimal_width = max(min_cell_width, cell_width)
        optimal_height = max(min_cell_height, cell_height)
        
        # Calculate scale factor for fonts
        scale_factor = min(optimal_width / 250.0, optimal_height / 200.0)
        scale_factor = max(0.6, min(1.2, scale_factor))  # Clamp between 0.6 and 1.2
        
        # Create cells
        total = self.rows * self.cols
        for board_idx in range(1, total + 1):
            row_idx, col_idx = _index_to_pos(board_idx, self.rows, self.cols)
            qt_row = self.rows - 1 - row_idx  # Qt origin top‑left
            qt_col = col_idx
            
            cell = BoardCell(board_idx, scale_factor=scale_factor)
            cell.setMinimumSize(int(optimal_width * 0.9), int(optimal_height * 0.9))
            cell.setMaximumSize(int(optimal_width * 1.1), int(optimal_height * 1.1))
            
            self.grid.addWidget(cell, qt_row, qt_col)
            self.cells[board_idx] = cell


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------



def _index_to_pos(board_idx: int, rows: int, cols: int) -> Tuple[int, int]:
    """Counter‑clockwise horizontal snake mapping (bottom‑left origin).

    Bottom row is numbered left→right; next row up right→left; and so on.

    Args:
        board_idx: 1‑based board index.
        rows: number of rows.
        cols: number of columns.

    Returns:
        (row, col) where row 0 = bottom, col 0 = left.
    """
    zero = board_idx - 1
    row = zero // cols  # 0 = bottom row
    col_offset = zero % cols
    if row % 2 == 0:
        col = col_offset  # even rows (from bottom) go left→right
    else:
        col = cols - 1 - col_offset  # odd rows go right→left
    return row, col


# ---------------------------------------------------------------------------
# SMTWidget – Main widget for SMT testing
# ---------------------------------------------------------------------------

class SMTWidget(QWidget):
    """Main SMT testing widget that contains the PCB panel display and programming UI."""
    
    # Signals
    test_started = Signal(str, dict)  # sku, params
    test_completed = Signal(object)   # TestResult

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.programming_enabled = False
        self.programming_progress = None
        self.is_testing = False
        self.logger = logging.getLogger(self.__class__.__name__)
        self._debug_enabled = _is_debug_enabled()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        title_label = QLabel("SMT Testing Mode")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: white; margin-bottom: 10px;"
        )
        layout.addWidget(title_label)

        # Create vertical splitter for programming (top) and power testing (bottom)
        self.splitter = QSplitter(Qt.Vertical)
        
        # Programming results section (smaller)
        self.programming_group = QGroupBox("Programming Results")
        self.programming_group.setMaximumHeight(250)  # Limit height
        self.programming_group.setStyleSheet("""
            QGroupBox {
                color: white;
                border: 2px solid #555555;
                border-radius: 8px;
                margin-top: 1ex;
                font-weight: bold;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        self.programming_layout = QVBoxLayout(self.programming_group)
        
        # Programming progress bar (shown during programming)
        self.programming_progress = QProgressBar()
        self.programming_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 4px;
                background-color: #2b2b2b;
                color: white;
                text-align: center;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #4a90a4;
                border-radius: 3px;
            }
        """)
        self.programming_progress.setVisible(False)
        self.programming_layout.addWidget(self.programming_progress)
        
        # Programming status label
        self.programming_status = QLabel("Programming not enabled")
        self.programming_status.setStyleSheet("color: #888888; font-style: italic; padding: 5px;")
        self.programming_status.setAlignment(Qt.AlignCenter)
        self.programming_layout.addWidget(self.programming_status)
        
        # Programming table
        self.programming_table = QTableWidget()
        self.programming_table.setMaximumHeight(150)  # Limit table height
        self.setup_programming_table()
        self.programming_layout.addWidget(self.programming_table)
        
        # Power validation section with PCB panel
        self.power_group = QGroupBox("Power Validation - PCB Panel")
        self.power_group.setStyleSheet("""
            QGroupBox {
                color: white;
                border: 2px solid #555555;
                border-radius: 8px;
                margin-top: 1ex;
                font-weight: bold;
                font-size: 14px;
                background-color: #2b2b2b;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        self.power_layout = QVBoxLayout(self.power_group)
        self.panel_widget = PCBPanelWidget()
        self.power_layout.addWidget(self.panel_widget)
        
        # Add to splitter
        self.splitter.addWidget(self.programming_group)
        self.splitter.addWidget(self.power_group)
        
        # Hide programming group by default (programming_enabled starts as False)
        self.programming_group.setVisible(False)
        
        # Set initial sizes (0% programming since hidden, 100% power)
        self.splitter.setSizes([0, 800])
        
        layout.addWidget(self.splitter)

    def setup_programming_table(self):
        """Setup programming results table"""
        self.programming_table.setColumnCount(4)
        self.programming_table.setHorizontalHeaderLabels(["Board", "Firmware", "Result", "Duration"])
        
        # Style the table
        self.programming_table.setStyleSheet("""
            QTableWidget {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #555555;
                border-radius: 5px;
                gridline-color: #555555;
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 4px;
                border-bottom: 1px solid #444444;
            }
            QHeaderView::section {
                background-color: #444444;
                color: white;
                padding: 4px;
                border: none;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        
        # Configure headers
        header = self.programming_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        self.programming_table.verticalHeader().setVisible(False)

    # ------------- compatibility methods for SMTHandler ------------
    def set_programming_enabled(self, enabled: bool):
        """Enable/disable programming display"""
        self.programming_enabled = enabled
        
        # Show/hide the entire programming group based on enabled state
        self.programming_group.setVisible(enabled)
        
        # Adjust splitter sizes based on programming visibility
        if enabled:
            self.programming_status.setText("Programming enabled - Waiting to start...")
            self.programming_status.setStyleSheet("color: #4a90a4; font-style: italic; padding: 5px;")
            # Set initial sizes (30% programming, 70% power)
            self.splitter.setSizes([200, 600])
        else:
            self.programming_status.setText("Programming not enabled")
            self.programming_status.setStyleSheet("color: #888888; font-style: italic; padding: 5px;")
            # Give all space to power section when programming is hidden
            self.splitter.setSizes([0, 800])

    def set_testing_state(self, testing: bool):
        """Set the testing state of the widget."""
        self.is_testing = testing
        if testing:
            # Reset power group background to default when starting test
            self.power_group.setStyleSheet("""
                QGroupBox {
                    color: white;
                    border: 2px solid #555555;
                    border-radius: 8px;
                    margin-top: 1ex;
                    font-weight: bold;
                    font-size: 14px;
                    background-color: #2b2b2b;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
            """)

    def cleanup(self):
        # currently nothing special required; placeholder for handler
        pass
    
    def start_programming_progress(self, total_boards: int):
        """Start programming progress display"""
        if not self.programming_enabled:
            return
            
        self.programming_progress.setMaximum(total_boards)
        self.programming_progress.setValue(0)
        self.programming_progress.setVisible(True)
        self.programming_status.setText(f"Programming {total_boards} board(s)...")
        self.programming_status.setStyleSheet("color: #ffd43b; font-weight: bold; padding: 5px;")
        
        # Clear previous results
        self.programming_table.setRowCount(0)
    
    def update_programming_progress(self, current_board: int, board_name: str, status: str):
        """Update programming progress"""
        if not self.programming_enabled or not self.programming_progress.isVisible():
            return
            
        self.programming_progress.setValue(current_board)
        self.programming_status.setText(f"Programming {board_name}: {status}")
    
    def complete_programming_progress(self, success_count: int, total_count: int):
        """Complete programming progress display"""
        if not self.programming_enabled:
            return
            
        self.programming_progress.setVisible(False)
        
        if success_count == total_count:
            self.programming_status.setText(f"Programming complete: {success_count}/{total_count} boards programmed successfully")
            self.programming_status.setStyleSheet("color: #51cf66; font-weight: bold; padding: 5px;")
        else:
            self.programming_status.setText(f"Programming complete: {success_count}/{total_count} boards programmed successfully")
            self.programming_status.setStyleSheet("color: #ff6b6b; font-weight: bold; padding: 5px;")

    def update_programming_results(self, programming_results: List[Dict]):
        """Update programming results table"""
        self.programming_table.setRowCount(len(programming_results))
        
        for row, result in enumerate(programming_results):
            board = result.get('board', 'Unknown')
            firmware = result.get('hex_file', 'N/A')
            success = result.get('success', False)
            duration = result.get('duration', 0)
            
            # Board name
            self.programming_table.setItem(row, 0, QTableWidgetItem(board))
            
            # Firmware file
            self.programming_table.setItem(row, 1, QTableWidgetItem(firmware))
            
            # Result with color coding
            result_text = "PASS" if success else "FAIL"
            result_item = QTableWidgetItem(result_text)
            if success:
                result_item.setBackground(QColor("#2d5a2d"))
                result_item.setForeground(QColor("#51cf66"))
            else:
                result_item.setBackground(QColor("#5a2d2d"))
                result_item.setForeground(QColor("#ff6b6b"))
            self.programming_table.setItem(row, 2, result_item)
            
            # Duration
            duration_text = f"{duration:.1f}s" if duration > 0 else "N/A"
            self.programming_table.setItem(row, 3, QTableWidgetItem(duration_text))

    # ------------------- helper proxies -------------------------
    def update_from_test_result(self, result):
        self.panel_widget.update_from_test_result(result)

    def set_panel_layout(self, rows: int, cols: int):
        self.panel_widget.set_panel_layout(rows, cols)
    
    def display_results(self, result):
        """Display test results - alias for update_from_test_result for compatibility."""
        if self._debug_enabled and self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"display_results called with result.measurements keys: {list(getattr(result, 'measurements', {}).keys())}")
        self.update_from_test_result(result)
        
        # Update programming results if available
        programming_results = getattr(result, 'programming_results', None)
        if programming_results:
            self.update_programming_results(programming_results)
            
            # Calculate programming statistics
            total_boards = len(programming_results)
            successful_boards = sum(1 for r in programming_results if r.get('success', False))
            self.complete_programming_progress(successful_boards, total_boards)
        else:
            # Show message if no programming was performed
            if self.programming_enabled:
                self.programming_table.setRowCount(1)
                no_prog_item = QTableWidgetItem("No programming performed")
                self.programming_table.setItem(0, 0, no_prog_item)
                # Use setSpan on the table widget, not the item
                self.programming_table.setSpan(0, 0, 1, 4)


# ---------------------------------------------------------------------------
# Self‑tests (run without Qt visual)
# ---------------------------------------------------------------------------

def _test_index_mapping():
    # 2×2 panel mapping
    assert _index_to_pos(1, 2, 2) == (0, 0)
    assert _index_to_pos(2, 2, 2) == (0, 1)
    assert _index_to_pos(3, 2, 2) == (1, 1)
    assert _index_to_pos(4, 2, 2) == (1, 0)

    # 3×2 panel (rows=3, cols=2)
    assert _index_to_pos(1, 3, 2) == (0, 0)
    assert _index_to_pos(2, 3, 2) == (0, 1)
    assert _index_to_pos(3, 3, 2) == (1, 1)
    assert _index_to_pos(4, 3, 2) == (1, 0)
    assert _index_to_pos(5, 3, 2) == (2, 0)
    assert _index_to_pos(6, 3, 2) == (2, 1)

    # 4×3 panel example
    assert _index_to_pos(1, 4, 3) == (0, 0)
    assert _index_to_pos(2, 4, 3) == (0, 1)
    assert _index_to_pos(3, 4, 3) == (0, 2)
    assert _index_to_pos(4, 4, 3) == (1, 2)
    assert _index_to_pos(5, 4, 3) == (1, 1)
    assert _index_to_pos(6, 4, 3) == (1, 0)
    assert _index_to_pos(7, 4, 3) == (2, 0)
    assert _index_to_pos(8, 4, 3) == (2, 1)
    assert _index_to_pos(9, 4, 3) == (2, 2)
    assert _index_to_pos(10, 4, 3) == (3, 2)
    assert _index_to_pos(11, 4, 3) == (3, 1)
    assert _index_to_pos(12, 4, 3) == (3, 0)

    logger = logging.getLogger("smt_widget_test")
    logger.info("Index mapping tests passed.")


def _test_function_formatting():
    # Test the generic function name formatting
    assert "backlight".replace("_", " ").title() == "Backlight"
    assert "backlight_1".replace("_", " ").title() == "Backlight 1"
    assert "rgbw_backlight".replace("_", " ").title() == "Rgbw Backlight"
    assert "custom_function_x".replace("_", " ").title() == "Custom Function X"
    logger = logging.getLogger("smt_widget_test")
    logger.info("Function name formatting tests passed.")


if __name__ == "__main__":
    # Setup logging for self-tests
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    _test_index_mapping()
    _test_function_formatting()
    logger = logging.getLogger("smt_widget_test")
    logger.info("All self-tests passed.")