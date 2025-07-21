"""
Update notification dialog for Diode Tester
"""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QTextEdit, QCheckBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import subprocess
import logging
from pathlib import Path


class UpdateDialog(QDialog):
    """Dialog to notify users about available updates"""
    
    update_accepted = Signal()
    update_declined = Signal()
    
    def __init__(self, current_version: str, new_version: str, 
                 update_message: str = "", update_path: Path = None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.current_version = current_version
        self.new_version = new_version
        self.update_message = update_message
        self.update_path = update_path
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle("Update Available")
        self.setModal(True)
        self.setMinimumSize(500, 350)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("A new version is available!")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setWeight(QFont.Bold)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Version info
        version_layout = QHBoxLayout()
        version_layout.addWidget(QLabel(f"Current version: {self.current_version}"))
        version_layout.addStretch()
        version_layout.addWidget(QLabel(f"New version: {self.new_version}"))
        layout.addLayout(version_layout)
        
        # Update message
        if self.update_message:
            message_label = QLabel("What's new:")
            layout.addWidget(message_label)
            
            message_text = QTextEdit()
            message_text.setPlainText(self.update_message)
            message_text.setReadOnly(True)
            message_text.setMaximumHeight(150)
            layout.addWidget(message_text)
        
        # Don't show again checkbox
        self.dont_show_checkbox = QCheckBox("Don't show this message again for this version")
        layout.addWidget(self.dont_show_checkbox)
        
        # Spacer
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.later_button = QPushButton("Remind Me Later")
        self.later_button.clicked.connect(self.on_later_clicked)
        button_layout.addWidget(self.later_button)
        
        self.update_button = QPushButton("Update Now")
        self.update_button.setDefault(True)
        self.update_button.clicked.connect(self.on_update_clicked)
        self.update_button.setStyleSheet("""
            QPushButton {
                background-color: #4a90a4;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5ba3b8;
            }
            QPushButton:pressed {
                background-color: #3a7a8a;
            }
        """)
        button_layout.addWidget(self.update_button)
        
        layout.addLayout(button_layout)
        
    def on_update_clicked(self):
        """Handle update button click"""
        try:
            if self.update_path and self.update_path.exists():
                # Open the update folder in Windows Explorer
                install_bat = self.update_path / "install.bat"
                if install_bat.exists():
                    # Run the installer
                    subprocess.Popen([str(install_bat)], shell=True)
                    self.logger.info(f"Started update installer: {install_bat}")
                else:
                    # Just open the folder
                    subprocess.Popen(f'explorer "{self.update_path}"')
                    self.logger.info(f"Opened update folder: {self.update_path}")
                
                self.update_accepted.emit()
                self.accept()
            else:
                # Open the shared drive folder
                shared_folder = Path(r"B:\Users\Landon Epperson\Tester")
                subprocess.Popen(f'explorer "{shared_folder}"')
                self.logger.info("Opened shared drive folder for manual update")
                self.update_accepted.emit()
                self.accept()
                
        except Exception as e:
            self.logger.error(f"Error launching update: {e}")
            
    def on_later_clicked(self):
        """Handle later button click"""
        self.update_declined.emit()
        
        # Check if user wants to skip this version
        if self.dont_show_checkbox.isChecked():
            # Save preference to skip this version
            self.save_skip_preference()
            
        self.reject()
        
    def save_skip_preference(self):
        """Save user preference to skip this version"""
        try:
            from PySide6.QtCore import QSettings
            settings = QSettings()
            settings.setValue(f"updates/skip_version_{self.new_version}", True)
            self.logger.info(f"User chose to skip version {self.new_version}")
        except Exception as e:
            self.logger.error(f"Error saving skip preference: {e}")


def check_and_show_update_dialog(parent=None) -> bool:
    """
    Check for updates and show dialog if available
    
    Returns:
        True if update dialog was shown, False otherwise
    """
    try:
        from src.utils.version_manager import VersionManager
        from PySide6.QtCore import QSettings
        
        manager = VersionManager()
        update_available, new_version, message = manager.check_for_updates()
        
        if not update_available:
            return False
            
        # Check if user has chosen to skip this version
        settings = QSettings()
        if settings.value(f"updates/skip_version_{new_version}", False, type=bool):
            logging.getLogger(__name__).info(f"Skipping version {new_version} per user preference")
            return False
            
        # Get update path
        update_path = manager.get_update_path()
        
        # Show dialog
        current_version = manager.get_current_version()
        dialog = UpdateDialog(current_version, new_version, message, update_path, parent)
        dialog.exec()
        
        return True
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Error checking for updates: {e}")
        return False