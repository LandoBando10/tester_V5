# gui/components/config_widget.py
import json
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton,
    QMessageBox, QFileDialog, QLabel, QGroupBox
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QFont

from .config.sku_editor import SKUEditor
from .config.test_selector import TestSelector
from .config.parameter_editor import ParameterEditor
from .config.program_config import ProgramConfigEditor

# Import from the src package
from src.data.sku_manager import create_sku_manager


class ConfigWidget(QWidget):
    """Configuration widget for test area"""
    
    configuration_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
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
    
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        header_group = QGroupBox("Configuration Editor")
        header_group.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
                border: 2px solid #555555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 10px 0 10px;
            }
        """)
        
        header_layout = QVBoxLayout(header_group)
        
        # Action buttons row
        button_row = QHBoxLayout()
        
        # Backup button
        self.backup_btn = QPushButton("Create Backup")
        self.backup_btn.setFixedSize(120, 32)
        button_row.addWidget(self.backup_btn)
        
        # Import/Export buttons
        self.import_btn = QPushButton("Import Config...")
        self.export_btn = QPushButton("Export Config...")
        for btn in [self.import_btn, self.export_btn]:
            btn.setFixedSize(120, 32)
        
        button_row.addWidget(self.import_btn)
        button_row.addWidget(self.export_btn)
        
        button_row.addStretch()
        
        # Exit Configuration Mode button
        self.exit_config_btn = QPushButton("Exit Configuration")
        self.exit_config_btn.setFixedSize(140, 35)
        self.exit_config_btn.clicked.connect(self.exit_configuration_mode)
        button_row.addWidget(self.exit_config_btn)
        
        # Save button
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setFixedSize(120, 35)
        self.save_btn.setEnabled(False)
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
        button_row.addWidget(self.save_btn)
        
        header_layout.addLayout(button_row)
        layout.addWidget(header_group)
        
        # SKU info label
        self.sku_info_label = QLabel("Select a SKU from the dropdown to edit configuration")
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
    
    def setup_connections(self):
        """Setup signal connections"""
        # Main buttons
        self.backup_btn.clicked.connect(self.create_backup)
        self.import_btn.clicked.connect(self.import_config)
        self.export_btn.clicked.connect(self.export_config)
        self.save_btn.clicked.connect(self.save_changes)
        
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
    
    def set_sku(self, sku: str):
        """Set the current SKU to edit"""
        if sku and sku != "-- Select SKU --":
            self.current_sku = sku
            sku_info = self.sku_manager.get_sku_info(sku)
            
            if sku_info:
                # Update header
                self.sku_info_label.setText(f"Editing: {sku} - {sku_info.get('description', '')}")
                
                # Enable tabs
                self.config_tabs.setEnabled(True)
                
                # Load data into editors
                self.sku_editor.load_sku_data(sku_info)
                self.test_selector.load_sku_data(sku_info)
                # For now, pass empty global parameters since the SKUManager doesn't have them
                self.parameter_editor.load_sku_data(sku_info, {})
                
                # Load programming config for this SKU
                prog_config = self.programming_config.get(sku, {})
                self.program_config.load_config_data(prog_config)
        else:
            self.current_sku = None
            self.sku_info_label.setText("Select a SKU from the dropdown to edit configuration")
            self.config_tabs.setEnabled(False)
    
    def mark_unsaved_changes(self):
        """Mark that there are unsaved changes"""
        self.unsaved_changes = True
        self.save_btn.setEnabled(True)
    
    def create_backup(self):
        """Create backup of current configurations"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            project_root = Path(__file__).parent.parent.parent.parent
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
                    # Export in old format for compatibility
                    export_data = {
                        "sku_definitions": list(self.sku_manager.skus_data.values()),
                        "global_parameters": {}
                    }
                    json.dump(export_data, f, indent=2)
                
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
            
            # Save each SKU individually back to its file
            for sku_id, sku_data in self.sku_manager.skus_data.items():
                sku_file = self.sku_manager.skus_dir / f"{sku_id}.json"
                with open(sku_file, 'w') as f:
                    json.dump(sku_data, f, indent=2)
            
            # Save programming configuration
            project_root = Path(__file__).parent.parent.parent.parent
            prog_config_path = project_root / "config" / "programming_config.json"
            with open(prog_config_path, 'w') as f:
                json.dump(self.programming_config, f, indent=2)
            
            # Update state
            self.unsaved_changes = False
            self.save_btn.setEnabled(False)
            
            # Emit signal
            self.configuration_changed.emit()
            
            QMessageBox.information(self, "Success", "Configuration saved successfully.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {e}")
    
    def exit_configuration_mode(self):
        """Exit configuration mode and return to previous mode"""
        # Check for unsaved changes
        if self.unsaved_changes:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Do you want to save before exiting?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if reply == QMessageBox.Save:
                self.save_changes()
            elif reply == QMessageBox.Cancel:
                return
        
        # Switch back to the previous mode
        try:
            parent = self.parent()
            while parent and not hasattr(parent, 'set_mode'):
                parent = parent.parent()
            
            if parent and hasattr(parent, 'set_mode'):
                # Get the previous mode
                previous_mode = parent.get_previous_mode() if hasattr(parent, 'get_previous_mode') else "Offroad"
                parent.set_mode(previous_mode)
            else:
                QMessageBox.warning(self, "Error", "Could not exit configuration mode")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to exit configuration mode: {e}")
    
    def apply_dark_style(self):
        """Apply dark theme styling"""
        self.setStyleSheet("""
            QWidget {
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