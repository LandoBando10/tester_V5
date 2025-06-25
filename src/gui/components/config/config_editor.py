# gui/components/config/config_editor.py
import json
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QPushButton,
    QMessageBox, QFileDialog, QSplitter, QListWidget, QListWidgetItem,
    QLabel
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from .sku_editor import SKUEditor
from .test_selector import TestSelector
from .parameter_editor import ParameterEditor
from .program_config import ProgramConfigEditor

# Import from the src package
from src.data.sku_manager import create_sku_manager


class ConfigurationEditor(QDialog):
    """Main configuration editor dialog"""
    
    configuration_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Configuration")
        self.showFullScreen()
        
        # Data managers
        self.sku_manager = None
        self.programming_config = None
        self.current_sku = None
        self.unsaved_changes = False
        
        # Load configurations
        self.load_configurations()
        
        # Setup UI
        self.setup_ui()
        self.apply_dark_style()
        
        # Connect signals
        self.setup_connections()
        
        # Load initial data
        self.refresh_sku_list()
    
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Configuration Editor")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setStyleSheet("color: #ffffff; margin-bottom: 10px; border: none;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Backup button
        self.backup_btn = QPushButton("Create Backup")
        self.backup_btn.setFixedSize(120, 32)
        header_layout.addWidget(self.backup_btn)
        
        layout.addLayout(header_layout)
        
        # Main content area
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - SKU List
        left_panel = self.create_left_panel()
        main_splitter.addWidget(left_panel)
        
        # Right panel - Configuration tabs
        right_panel = self.create_right_panel()
        main_splitter.addWidget(right_panel)
        
        # Set splitter sizes (25% left, 75% right)
        main_splitter.setSizes([300, 900])
        layout.addWidget(main_splitter)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Add Exit Fullscreen button
        self.exit_fullscreen_btn = QPushButton("Exit Fullscreen (Esc)")
        self.exit_fullscreen_btn.setFixedSize(140, 35)
        self.exit_fullscreen_btn.clicked.connect(self.showNormal)
        button_layout.addWidget(self.exit_fullscreen_btn)
        
        self.import_btn = QPushButton("Import Config...")
        self.export_btn = QPushButton("Export Config...")
        self.save_btn = QPushButton("Save Changes")
        self.cancel_btn = QPushButton("Cancel")
        
        for btn in [self.import_btn, self.export_btn, self.save_btn, self.cancel_btn]:
            btn.setFixedSize(120, 35)
        
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90a4;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5ba3b8;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """)
        
        button_layout.addWidget(self.import_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def create_left_panel(self) -> QWidget:
        """Create the left panel with SKU list and management buttons"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        
        # SKU List header
        header_layout = QHBoxLayout()
        
        sku_label = QLabel("SKUs")
        sku_label.setFont(QFont("Arial", 12, QFont.Bold))
        sku_label.setStyleSheet("color: #ffffff; border: none;")
        header_layout.addWidget(sku_label)
        
        header_layout.addStretch()
        
        # SKU management buttons
        self.add_sku_btn = QPushButton("Add")
        self.add_sku_btn.setFixedSize(40, 25)
        self.add_sku_btn.setToolTip("Add new SKU")
        
        self.duplicate_sku_btn = QPushButton("Copy")
        self.duplicate_sku_btn.setFixedSize(45, 25)
        self.duplicate_sku_btn.setToolTip("Duplicate selected SKU")
        
        self.delete_sku_btn = QPushButton("Del")
        self.delete_sku_btn.setFixedSize(35, 25)
        self.delete_sku_btn.setToolTip("Delete selected SKU")
        
        for btn in [self.add_sku_btn, self.duplicate_sku_btn, self.delete_sku_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #404040;
                    color: white;
                    border: 1px solid #555555;
                    border-radius: 3px;
                    font-weight: bold;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #555555;
                }
            """)
        
        header_layout.addWidget(self.add_sku_btn)
        header_layout.addWidget(self.duplicate_sku_btn)
        header_layout.addWidget(self.delete_sku_btn)
        
        layout.addLayout(header_layout)
        
        # SKU List
        self.sku_list = QListWidget()
        self.sku_list.setStyleSheet("""
            QListWidget {
                background-color: #333333;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #444444;
            }
            QListWidget::item:selected {
                background-color: #4a90a4;
            }
            QListWidget::item:hover {
                background-color: #404040;
            }
        """)
        layout.addWidget(self.sku_list)
        
        return panel
    
    def create_right_panel(self) -> QWidget:
        """Create the right panel with configuration tabs"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # SKU info header
        self.sku_info_label = QLabel("Select a SKU to edit configuration")
        self.sku_info_label.setFont(QFont("Arial", 12))
        self.sku_info_label.setStyleSheet("color: #cccccc; padding: 10px;")
        layout.addWidget(self.sku_info_label)
        
        # Configuration tabs
        self.config_tabs = QTabWidget()
        self.config_tabs.setEnabled(False)
        
        # Basic Info tab
        self.sku_editor = SKUEditor()
        self.config_tabs.addTab(self.sku_editor, "Basic Info")
        
        # Test Selection tab
        self.test_selector = TestSelector()
        self.config_tabs.addTab(self.test_selector, "Test Selection")
        
        # Parameters tab
        self.parameter_editor = ParameterEditor()
        self.config_tabs.addTab(self.parameter_editor, "Parameters")
        
        # Programming tab
        self.program_config = ProgramConfigEditor()
        self.config_tabs.addTab(self.program_config, "Programming")
        
        layout.addWidget(self.config_tabs)
        
        return panel
    
    def setup_connections(self):
        """Setup signal connections"""
        # SKU list
        self.sku_list.itemSelectionChanged.connect(self.on_sku_selection_changed)
        
        # SKU management buttons
        self.add_sku_btn.clicked.connect(self.add_sku)
        self.duplicate_sku_btn.clicked.connect(self.duplicate_sku)
        self.delete_sku_btn.clicked.connect(self.delete_sku)
        
        # Main buttons
        self.backup_btn.clicked.connect(self.create_backup)
        self.import_btn.clicked.connect(self.import_config)
        self.export_btn.clicked.connect(self.export_config)
        self.save_btn.clicked.connect(self.save_changes)
        self.cancel_btn.clicked.connect(self.reject)
          # Configuration change tracking
        self.sku_editor.data_changed.connect(self.mark_unsaved_changes)
        self.test_selector.data_changed.connect(self.mark_unsaved_changes)
        self.parameter_editor.data_changed.connect(self.mark_unsaved_changes)
        self.program_config.data_changed.connect(self.mark_unsaved_changes)
    
    def load_configurations(self):
        """Load SKU and programming configurations"""
        try:
            self.sku_manager = create_sku_manager()
            
            # Load programming config
            project_root = Path(__file__).parent.parent.parent.parent.parent
            prog_config_path = project_root / "config" / "programming_config.json"
            
            if prog_config_path.exists():
                with open(prog_config_path, 'r') as f:
                    self.programming_config = json.load(f)
            else:
                self.programming_config = {}
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load configurations: {e}")
            self.reject()
    
    def refresh_sku_list(self):
        """Refresh the SKU list"""
        self.sku_list.clear()
        
        if self.sku_manager:
            for sku in self.sku_manager.get_all_skus():
                item = QListWidgetItem(sku)
                sku_info = self.sku_manager.get_sku_info(sku)
                if sku_info:
                    item.setToolTip(sku_info.get('description', ''))
                self.sku_list.addItem(item)
    
    def on_sku_selection_changed(self):
        """Handle SKU selection change"""
        current_item = self.sku_list.currentItem()
        
        if current_item:
            self.current_sku = current_item.text()
            sku_info = self.sku_manager.get_sku_info(self.current_sku)
            
            if sku_info:
                # Update header
                self.sku_info_label.setText(f"Editing: {self.current_sku} - {sku_info.get('description', '')}")
                
                # Enable tabs
                self.config_tabs.setEnabled(True)
                
                # Load data into editors
                self.sku_editor.load_sku_data(sku_info)
                self.test_selector.load_sku_data(sku_info)
                self.parameter_editor.load_sku_data(sku_info, self.sku_manager.data.get('global_parameters', {}))
                
                # Load programming config for this SKU
                prog_config = self.programming_config.get(self.current_sku, {})
                self.program_config.load_config_data(prog_config)
        else:
            self.current_sku = None
            self.sku_info_label.setText("Select a SKU to edit configuration")
            self.config_tabs.setEnabled(False)
    
    def add_sku(self):
        """Add a new SKU"""
        from PySide6.QtWidgets import QInputDialog
        
        sku_id, ok = QInputDialog.getText(self, "Add SKU", "Enter SKU ID:")
        
        if ok and sku_id:
            # Check if SKU already exists
            if sku_id in self.sku_manager.get_all_skus():
                QMessageBox.warning(self, "Warning", f"SKU {sku_id} already exists.")
                return
            
            # Create new SKU with template
            new_sku = {
                "sku": sku_id,
                "description": f"New product - {sku_id}",
                "pod_type_ref": "C1",
                "power_level_ref": "Sport",
                "available_modes": ["Offroad"],
                "backlight_config": {
                    "type": "single",
                    "relay_pins": [3],
                    "test_duration_ms": 500
                },
                "offroad_params": {
                    "LUX": {"min_mainbeam_lux": 1000, "max_mainbeam_lux": 1500},
                    "COLOR": {
                        "center_x_main": 0.450, "center_y_main": 0.410,
                        "radius_x_main": 0.015, "radius_y_main": 0.015,
                        "angle_deg_main": 0
                    },
                    "CURRENT": {"min_mainbeam_current_A": 0.5, "max_mainbeam_current_A": 0.8}
                },
                "smt_params": None,
                "weightchecking_params": None
            }
            
            # Add to SKU manager data
            self.sku_manager.data["sku_definitions"].append(new_sku)
            
            # Refresh list and select new SKU
            self.refresh_sku_list()
            
            # Find and select the new item
            for i in range(self.sku_list.count()):
                if self.sku_list.item(i).text() == sku_id:
                    self.sku_list.setCurrentRow(i)
                    break
            
            self.mark_unsaved_changes()
    
    def duplicate_sku(self):
        """Duplicate the selected SKU"""
        if not self.current_sku:
            QMessageBox.warning(self, "Warning", "Please select a SKU to duplicate.")
            return
        
        from PySide6.QtWidgets import QInputDialog
        
        new_sku_id, ok = QInputDialog.getText(
            self, "Duplicate SKU", 
            f"Enter new SKU ID (duplicating {self.current_sku}):"
        )
        
        if ok and new_sku_id:
            # Check if SKU already exists
            if new_sku_id in self.sku_manager.get_all_skus():
                QMessageBox.warning(self, "Warning", f"SKU {new_sku_id} already exists.")
                return
            
            # Get current SKU data and duplicate
            current_sku_info = self.sku_manager.get_sku_info(self.current_sku)
            if current_sku_info:
                new_sku = current_sku_info.copy()
                new_sku["sku"] = new_sku_id
                new_sku["description"] = f"Copy of {self.current_sku}"
                
                # Add to SKU manager data
                self.sku_manager.data["sku_definitions"].append(new_sku)
                
                # Duplicate programming config if exists
                if self.current_sku in self.programming_config:
                    self.programming_config[new_sku_id] = self.programming_config[self.current_sku].copy()
                
                # Refresh list and select new SKU
                self.refresh_sku_list()
                
                # Find and select the new item
                for i in range(self.sku_list.count()):
                    if self.sku_list.item(i).text() == new_sku_id:
                        self.sku_list.setCurrentRow(i)
                        break
                
                self.mark_unsaved_changes()
    
    def delete_sku(self):
        """Delete the selected SKU"""
        if not self.current_sku:
            QMessageBox.warning(self, "Warning", "Please select a SKU to delete.")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete SKU {self.current_sku}?\n\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Remove from SKU definitions
            self.sku_manager.data["sku_definitions"] = [
                sku for sku in self.sku_manager.data["sku_definitions"]
                if sku["sku"] != self.current_sku
            ]
            
            # Remove programming config
            if self.current_sku in self.programming_config:
                del self.programming_config[self.current_sku]
            
            # Refresh list
            self.refresh_sku_list()
            self.mark_unsaved_changes()
    
    def mark_unsaved_changes(self):
        """Mark that there are unsaved changes"""
        self.unsaved_changes = True
        if not self.windowTitle().endswith("*"):
            self.setWindowTitle(self.windowTitle() + "*")
        self.save_btn.setEnabled(True)
    
    def create_backup(self):
        """Create backup of current configurations"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            project_root = Path(__file__).parent.parent.parent.parent.parent
            backup_dir = project_root / "config" / "backups"
            backup_dir.mkdir(exist_ok=True)
            
            # Backup SKU config
            sku_backup = backup_dir / f"skus_backup_{timestamp}.json"
            shutil.copy2(self.sku_manager.config_path, sku_backup)
            
            # Backup programming config
            prog_config_path = project_root / "config" / "programming_config.json"
            if prog_config_path.exists():
                prog_backup = backup_dir / f"programming_backup_{timestamp}.json"
                shutil.copy2(prog_config_path, prog_backup)
            
            QMessageBox.information(
                self, "Backup Created",
                f"Configuration backup created:\n{backup_dir}"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create backup: {e}")
    
    def import_config(self):
        """Import configuration from file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Configuration", "",
            "JSON files (*.json);;All files (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    imported_data = json.load(f)
                
                # Validate imported data
                if "sku_definitions" in imported_data:
                    reply = QMessageBox.question(
                        self, "Import Configuration",
                        "This will replace the current configuration. Continue?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    
                    if reply == QMessageBox.Yes:
                        self.sku_manager.data = imported_data
                        self.refresh_sku_list()
                        self.mark_unsaved_changes()
                        QMessageBox.information(self, "Success", "Configuration imported successfully.")
                else:
                    QMessageBox.warning(self, "Error", "Invalid configuration file format.")
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import configuration: {e}")
    
    def export_config(self):
        """Export current configuration to file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Configuration", "",
            "JSON files (*.json);;All files (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    json.dump(self.sku_manager.data, f, indent=2)
                
                QMessageBox.information(self, "Success", "Configuration exported successfully.")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export configuration: {e}")
    
    def save_changes(self):
        """Save all changes"""
        try:
            # Collect data from all editors
            if self.current_sku:
                sku_info = self.sku_manager.get_sku_info(self.current_sku)
                if sku_info:
                    # Update SKU data from editors
                    self.sku_editor.save_to_sku_data(sku_info)
                    self.test_selector.save_to_sku_data(sku_info)
                    self.parameter_editor.save_to_sku_data(sku_info)
                    
                    # Update programming config
                    prog_config = self.program_config.get_config_data()
                    if prog_config:
                        self.programming_config[self.current_sku] = prog_config
            
            # Save SKU configuration
            with open(self.sku_manager.config_path, 'w') as f:
                json.dump(self.sku_manager.data, f, indent=2)
            
            # Save programming configuration
            project_root = Path(__file__).parent.parent.parent.parent.parent
            prog_config_path = project_root / "config" / "programming_config.json"
            with open(prog_config_path, 'w') as f:
                json.dump(self.programming_config, f, indent=2)
            
            # Update state
            self.unsaved_changes = False
            self.setWindowTitle("Edit Configuration")
            self.save_btn.setEnabled(False)
            
            # Emit signal
            self.configuration_changed.emit()
            
            QMessageBox.information(self, "Success", "Configuration saved successfully.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {e}")
    
    def keyPressEvent(self, event):
        """Handle key press events"""
        if event.key() == Qt.Key_Escape:
            self.showNormal()
        else:
            super().keyPressEvent(event)
    
    def closeEvent(self, event):
        """Handle close event"""
        if self.unsaved_changes:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Do you want to save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if reply == QMessageBox.Save:
                self.save_changes()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
    
    def apply_dark_style(self):
        """Apply dark theme styling"""
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: white;
            }
            
            QLabel {
                border: none;
            }
            
            QTabWidget::pane {
                border: 1px solid #555555;
                background-color: #333333;
            }
            
            QTabWidget::tab-bar {
                alignment: left;
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
            
            QPushButton {
                background-color: #404040;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            
            QPushButton:hover {
                background-color: #555555;
            }
            
            QPushButton:pressed {
                background-color: #333333;
            }
            
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666666;
            }
            
            QFrame {
                border: 1px solid #555555;
            }
            
            QSplitter::handle {
                background-color: #555555;
                width: 2px;
            }
        """)
