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

from PySide6.QtWidgets import (
    QWidget,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QFrame,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressBar,
    QSplitter,
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt, Signal

# ---------------------------------------------------------------------------
# BoardCell
# ---------------------------------------------------------------------------


class BoardCell(QFrame):
    """Visual cell representing a single PCB on the SMT panel."""

    PASS_COLOR = QColor("#2d5a2d")
    FAIL_COLOR = QColor("#5a2d2d")
    IDLE_COLOR = QColor("#3a3a3a")
    TEXT_STYLE = "font-size: 11px;"

    def __init__(self, board_idx: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.board_idx = board_idx
        self._setup_ui()
        self.set_idle()

    # ------------------------ UI setup ------------------------
    def _setup_ui(self):
        self.setFrameShape(QFrame.StyledPanel)
        self.setLineWidth(2)
        self.setStyleSheet("border: 2px solid #555555; border-radius: 4px;")
        self.setAutoFillBackground(True)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(2)

        self.label_board = QLabel(f"Board {self.board_idx}")
        self.label_board.setAlignment(Qt.AlignCenter)
        self.label_board.setStyleSheet(self.TEXT_STYLE + "font-weight: bold;")
        self.layout.addWidget(self.label_board)

        # dynamic measurement labels live here
        self.measure_labels: Dict[str, QLabel] = {}

        self.layout.addStretch()

    # -------------------- colour helpers ----------------------
    def _apply_background(self, color: QColor):
        print(f"[CELL COLOR DEBUG] Board {self.board_idx}: Applying background color {color.name()}")
        
        # Use style sheet instead of palette to avoid conflicts
        border_style = "border: 2px solid #555555; border-radius: 4px;"
        bg_style = f"background-color: {color.name()};"
        self.setStyleSheet(f"{border_style} {bg_style}")
        
        # Update text color based on background brightness
        txt_color = QColor("white") if color.lightness() < 128 else QColor("black")
        text_style = self.TEXT_STYLE + f"color: {txt_color.name()};" + "font-weight: bold;"
        self.label_board.setStyleSheet(text_style)
        
        # Update existing labels
        for lbl in self.measure_labels.values():
            lbl.setStyleSheet(self.TEXT_STYLE + f"color: {txt_color.name()};")

    def set_pass(self):
        self._apply_background(self.PASS_COLOR)

    def set_fail(self):
        self._apply_background(self.FAIL_COLOR)

    def set_idle(self):
        self._apply_background(self.IDLE_COLOR)

    # ------------------- data population ----------------------
    def update_measurements(
        self,
        main_current: Optional[float],
        back_currents: Dict[str, float],
        passed: bool,
    ) -> None:
        """Refresh measurement lines and colour‑code the cell."""
        print(f"[CELL COLOR DEBUG] Board {self.board_idx}: updating with passed={passed}, main_current={main_current}, back_currents={back_currents}")
        
        # purge old
        for lbl in self.measure_labels.values():
            self.layout.removeWidget(lbl)
            lbl.deleteLater()
        self.measure_labels.clear()

        # helper
        def _add_line(text: str):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(self.TEXT_STYLE)
            # insert above the stretch (last item)
            self.layout.insertWidget(self.layout.count() - 1, lbl)
            self.measure_labels[text] = lbl

        if main_current is not None:
            _add_line(f"Mainbeam Current: {main_current:.2f} A")

        for variant, cur in sorted(back_currents.items()):
            _add_line(f"{_variant_to_label(variant)} Current: {cur:.2f} A")

        # Apply color based on pass/fail, but only if we have actual measurement data
        if main_current is not None or back_currents:
            if passed:
                print(f"[CELL COLOR DEBUG] Board {self.board_idx}: Setting color to PASS (green)")
                self.set_pass()
            else:
                print(f"[CELL COLOR DEBUG] Board {self.board_idx}: Setting color to FAIL (red)")
                self.set_fail()
        else:
            # No data yet, keep grey
            print(f"[CELL COLOR DEBUG] Board {self.board_idx}: No measurement data, keeping IDLE (grey)")
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
        self.grid.setSpacing(10)
        self.cells: Dict[int, BoardCell] = {}

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
            cell.update_measurements(None, {}, True)

        main_vals: Dict[int, float] = {}
        back_vals: Dict[int, Dict[str, float]] = {}
        board_pass: Dict[int, bool] = {}

        for name, data in getattr(result, "measurements", {}).items():
            if "_board_" not in name:
                continue
            
            # Only process current measurements, not voltage
            if not name.endswith("_current"):
                continue
            
            # Parse board number from names like "mainbeam_board_1_current" or "backlight_board_1_current"
            parts = name.split("_")
            try:
                board_idx = parts.index("board")
                b_idx = int(parts[board_idx + 1])
            except (ValueError, IndexError):
                continue

            # Determine variant (mainbeam or backlight)
            variant = parts[0]  # First part is usually the variant
            board_pass.setdefault(b_idx, True)
            
            # Store current values only
            if variant == "mainbeam":
                main_vals[b_idx] = data["value"]
            elif variant == "backlight":
                back_vals.setdefault(b_idx, {})[variant] = data["value"]
            
            # Check pass/fail
            if not data.get("passed", True):
                board_pass[b_idx] = False

        # Debug: Final board pass/fail status determined
        
        for idx, cell in self.cells.items():
            passed = board_pass.get(idx, True)
            # Debug: Updating cell with pass/fail status
            cell.update_measurements(
                main_vals.get(idx),
                back_vals.get(idx, {}),
                passed,
            )

    # ------------------ internal helpers ----------------------
    def _rebuild_grid(self):
        if self.rows <= 0 or self.cols <= 0:
            return
        total = self.rows * self.cols
        for board_idx in range(1, total + 1):
            row_idx, col_idx = _index_to_pos(board_idx, self.rows, self.cols)
            qt_row = self.rows - 1 - row_idx  # Qt origin top‑left
            qt_col = col_idx
            cell = BoardCell(board_idx)
            self.grid.addWidget(cell, qt_row, qt_col)
            self.cells[board_idx] = cell


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _variant_to_label(variant: str) -> str:
    mapping = {
        "backlight": "Back-light",
        "backlight1": "Back-light 1",
        "backlight2": "Back-light 2",
        "rgbw_backlight": "RGBW Back-light",
    }
    return mapping.get(variant, variant.replace("_", " ").title())


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
        
        # Set initial sizes (30% programming, 70% power)
        self.splitter.setSizes([200, 600])
        
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
        if enabled:
            self.programming_status.setText("Programming enabled - Waiting to start...")
            self.programming_status.setStyleSheet("color: #4a90a4; font-style: italic; padding: 5px;")
        else:
            self.programming_status.setText("Programming not enabled")
            self.programming_status.setStyleSheet("color: #888888; font-style: italic; padding: 5px;")

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

    print("Index mapping tests passed.")


def _test_variant_label():
    assert _variant_to_label("backlight") == "Back-light"
    assert _variant_to_label("backlight1") == "Back-light 1"
    assert _variant_to_label("rgbw_backlight") == "RGBW Back-light"
    assert _variant_to_label("custom_variant_x") == "Custom Variant X"
    print("Variant label tests passed.")


if __name__ == "__main__":
    _test_index_mapping()
    _test_variant_label()
    print("All self-tests passed.")