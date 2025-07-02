# gui/components/top_controls.py
from typing import List
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QComboBox, 
                               QLabel, QCheckBox)
from .searchable_combo import SearchableComboBox
from PySide6.QtCore import Signal, Qt, QEvent
from PySide6.QtGui import QFont
import logging

logger = logging.getLogger(__name__)


class TopControlsWidget(QWidget):
    """Top control panel with SKU selection and test checkboxes"""
    
    # Signals
    sku_changed = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_mode = "Offroad"
        self.test_checkboxes = {}
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the top controls UI"""
        # Main layout with reduced margins
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 3, 5, 3)
        main_layout.setSpacing(5)
        
        # Top row: SKU selector and tests only
        top_row = QHBoxLayout()
        top_row.setSpacing(20)
        
        # SKU Section
        self.setup_sku_section(top_row)
        
        # Tests Section
        self.setup_tests_section(top_row)
        
        # Add stretch to push everything left
        top_row.addStretch()
        
        main_layout.addLayout(top_row)
    
    def setup_sku_section(self, layout):
        """Setup SKU selection section"""
        
        sku_layout = QHBoxLayout()
        sku_layout.setSpacing(8)
        
        sku_label = QLabel("SKU:")
        sku_label.setFont(QFont("Arial", 10, QFont.Bold))
        sku_label.setStyleSheet("color: white; margin: 0px;")
        sku_layout.addWidget(sku_label)
        
        self.sku_combo = SearchableComboBox()
        self.sku_combo.setMinimumHeight(25)
        self.sku_combo.setMinimumWidth(200)
        self.sku_combo.setMaximumWidth(500)
        self.sku_combo.setFont(QFont("Arial", 10))
        
        # Configure combo box
        self.sku_combo.setMaxVisibleItems(20)
        self.sku_combo.setFocusPolicy(Qt.ClickFocus)
        
        # Don't modify the popup window flags - let QComboBox handle it internally
        # This was causing the popup to stay open after selection
        
        # Install event filter for debugging
        self.sku_combo.installEventFilter(self)
        self.sku_combo.view().installEventFilter(self)
        
        # Apply minimal styling to avoid popup conflicts
        self.apply_simple_combo_style()
        
        # Connect signals
        self.sku_combo.item_selected.connect(self._on_sku_selected)
        
        sku_layout.addWidget(self.sku_combo)
        
        layout.addLayout(sku_layout)
    
    def setup_tests_section(self, layout):
        """Setup test checkboxes section"""
        self.tests_layout = QHBoxLayout()
        self.tests_layout.setSpacing(15)
        
        self.tests_label = QLabel("Tests:")
        self.tests_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.tests_label.setStyleSheet("color: white; margin: 0px;")
        self.tests_layout.addWidget(self.tests_label)
        
        # Create test checkboxes
        test_names = ["POWER", "LUX", "COLOR", "PRESSURE", "PROGRAMMING"]
        
        for test_name in test_names:
            checkbox = QCheckBox(test_name)
            checkbox.setFont(QFont("Arial", 10))
            self.apply_checkbox_style(checkbox)
            checkbox.hide()  # Initially hidden
            self.tests_layout.addWidget(checkbox)
            self.test_checkboxes[test_name] = checkbox
        
        layout.addLayout(self.tests_layout)
    
    def apply_simple_combo_style(self):
        """Apply minimal styling that doesn't interfere with popup behavior"""
        self.sku_combo.setStyleSheet("""
            SearchableComboBox, QComboBox {
                background-color: #555555;
                color: white;
                border: 1px solid #666666;
                border-radius: 3px;
                padding: 4px 8px;
                padding-right: 30px; /* Make room for dropdown arrow */
                min-height: 25px;
            }
            SearchableComboBox:hover, QComboBox:hover {
                background-color: #666666;
            }
            SearchableComboBox:focus, QComboBox:focus {
                border: 2px solid #0078d4;
            }
            SearchableComboBox::drop-down, QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #666666;
                background-color: #444444;
            }
            SearchableComboBox::drop-down:hover, QComboBox::drop-down:hover {
                background-color: #555555;
            }
            SearchableComboBox::down-arrow, QComboBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid white;
            }
            SearchableComboBox QAbstractItemView, QComboBox QAbstractItemView {
                background-color: #555555;
                color: white;
                border: 1px solid #666666;
                selection-background-color: #0078d4;
            }
        """)
    
    def apply_checkbox_style(self, checkbox):
        """Apply styling to checkbox"""
        checkbox.setStyleSheet("""
            QCheckBox {
                color: white;
                spacing: 5px;
                margin-right: 15px;
            }
            QCheckBox::indicator {
                width: 12px;
                height: 12px;
                border: 1px solid #666666;
                border-radius: 2px;
                background-color: #444444;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border-color: #0078d4;
            }
        """)
    
    def set_mode(self, mode: str):
        """Update controls based on current mode"""
        self.current_mode = mode
        
        # Hide/show tests section based on mode
        if mode in ["WeightChecking", "Configuration"]:
            # Hide entire tests section for weight checking and configuration
            self.tests_label.hide()
            for checkbox in self.test_checkboxes.values():
                checkbox.hide()
        else:
            # Show tests section
            self.tests_label.show()
            
            # Update available tests
            self.update_available_tests()
    
    def update_available_tests(self):
        """Update which test checkboxes are visible based on mode"""
        # Hide all checkboxes first
        for checkbox in self.test_checkboxes.values():
            checkbox.hide()
        
        # Show checkboxes based on mode
        if self.current_mode == "Offroad":
            available_tests = ["POWER", "LUX", "COLOR", "PRESSURE"]
        elif self.current_mode == "SMT":
            available_tests = ["POWER", "PROGRAMMING"]
        else:
            available_tests = []
        
        # Show and check appropriate checkboxes
        for test_name in available_tests:
            if test_name in self.test_checkboxes:
                checkbox = self.test_checkboxes[test_name]
                checkbox.show()
                
                # For SMT mode, programming checkbox starts disabled until SKU is selected
                if self.current_mode == "SMT" and test_name == "PROGRAMMING":
                    checkbox.setEnabled(False)
                    checkbox.setChecked(False)
                else:
                    checkbox.setEnabled(True)
                    checkbox.setChecked(True)  # Default to checked
    
    def set_available_skus(self, skus: List[str]):
        """Update the available SKUs in the combo box"""
        current_sku = self.sku_combo.currentText()
        logger.info(f"Setting available SKUs. Count: {len(skus)}, Current: '{current_sku}'")
        
        # Set initialization flag to prevent signals during setup
        self.sku_combo._is_initializing = True
        
        # Block both Qt signals and custom signals during population
        self.sku_combo.blockSignals(True)
        self.sku_combo.blockCustomSignals(True)
        
        self.sku_combo.clear()
        self.sku_combo.addItem("-- Select SKU --")
        self.sku_combo.addItems(skus)
        
        # Try to restore previous selection if still available
        if current_sku and current_sku != "-- Select SKU --" and current_sku in skus:
            logger.info(f"Restoring previous SKU selection: '{current_sku}'")
            self.sku_combo.setCurrentText(current_sku)
        else:
            # No previous selection or it's not available, select placeholder
            logger.info("Setting combo box to placeholder")
            self.sku_combo.setCurrentIndex(0)
            # Ensure the text is set to the placeholder
            self.sku_combo.setCurrentText("-- Select SKU --")
            # Force update the line edit to show placeholder
            if self.sku_combo.lineEdit():
                self.sku_combo.lineEdit().setText("-- Select SKU --")
        
        # Clear initialization flag
        self.sku_combo._is_initializing = False
        
        # Re-enable both Qt signals and custom signals
        self.sku_combo.blockSignals(False)
        self.sku_combo.blockCustomSignals(False)
        
        # Log final selection
        final_selection = self.sku_combo.currentText()
        logger.info(f"Final SKU selection after update: '{final_selection}'")
    
    def get_current_sku(self) -> str:
        """Get the currently selected SKU"""
        return self.sku_combo.currentText()
    
    def set_current_sku(self, sku: str):
        """Set the current SKU selection"""
        self.sku_combo.setCurrentText(sku)
    
    def get_enabled_tests(self) -> List[str]:
        """Get list of enabled tests"""
        enabled_tests = []
        for test_name, checkbox in self.test_checkboxes.items():
            if checkbox.isVisible() and checkbox.isChecked():
                enabled_tests.append(test_name)
        return enabled_tests
    
    def update_programming_checkbox(self, programming_enabled: bool):
        """Update programming checkbox state based on SKU configuration
        
        Args:
            programming_enabled: True if programming is enabled for the SKU, False otherwise
        """
        if "PROGRAMMING" in self.test_checkboxes:
            checkbox = self.test_checkboxes["PROGRAMMING"]
            if programming_enabled:
                # Enable checkbox and check it by default
                checkbox.setEnabled(True)
                checkbox.setChecked(True)
            else:
                # Disable checkbox and uncheck it
                checkbox.setEnabled(False)
                checkbox.setChecked(False)
    
    def eventFilter(self, obj, event):
        """Event filter for debugging combo box behavior"""
        # Event types for debugging (commented out as unused)
        # event_types_to_log = [
        #     QEvent.MouseButtonRelease,
        #     QEvent.FocusIn,
        #     QEvent.FocusOut,
        #     QEvent.Show,
        #     QEvent.Hide,
        #     QEvent.Close
        # ]
        
        if obj == self.sku_combo or obj == self.sku_combo.view():
            pass
        
        return super().eventFilter(obj, event)
    
    def get_event_name(self, event_type):
        """Convert event type to readable name"""
        event_names = {
            QEvent.MouseButtonPress: "MouseButtonPress",
            QEvent.MouseButtonRelease: "MouseButtonRelease",
            QEvent.FocusIn: "FocusIn",
            QEvent.FocusOut: "FocusOut",
            QEvent.Show: "Show",
            QEvent.Hide: "Hide",
            QEvent.Close: "Close"
        }
        return event_names.get(event_type, f"Unknown({event_type})")
    
    def _on_sku_selected(self, sku: str):
        """Handle SKU selection from combo box"""
        logger.info(f"SKU selected from combo box: '{sku}'")
        self.sku_changed.emit(sku)
    
    