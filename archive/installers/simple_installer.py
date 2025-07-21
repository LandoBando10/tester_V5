#!/usr/bin/env python3
"""
Simple GUI Installer for Diode Tester V5
"""

import sys
import subprocess
import os
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, 
                             QProgressBar, QPushButton, QTextEdit, QMessageBox)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QPixmap


class InstallWorker(QThread):
    """Worker thread for package installation"""
    progress = Signal(int, str)
    log_message = Signal(str)
    finished = Signal(bool, str)
    
    def __init__(self):
        super().__init__()
        self.packages = [
            ("PySide6", "GUI Framework"),
            ("pyserial", "Arduino Communication"),
            ("numpy", "Data Processing"),
            ("packaging", "Version Management"),
            ("pyqtgraph", "Live Graphs (Optional)")
        ]
    
    def run(self):
        """Install required packages"""
        try:
            total_packages = len(self.packages)
            
            for i, (package, description) in enumerate(self.packages):
                progress = int((i / total_packages) * 100)
                self.progress.emit(progress, f"Installing {description}...")
                self.log_message.emit(f"Installing {package}...")
                
                # Check if already installed
                check_result = subprocess.run(
                    [sys.executable, "-m", "pip", "show", package],
                    capture_output=True,
                    text=True
                )
                
                if check_result.returncode == 0:
                    self.log_message.emit(f"✓ {package} already installed")
                    continue
                
                # Install package
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade", package],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0 and package != "pyqtgraph":  # pyqtgraph is optional
                    self.finished.emit(False, f"Failed to install {package}: {result.stderr}")
                    return
                
                self.log_message.emit(f"✓ {package} installed successfully")
            
            self.progress.emit(100, "Installation complete!")
            self.finished.emit(True, "All packages installed successfully!")
            
        except Exception as e:
            self.finished.emit(False, str(e))


class SimpleInstaller(QWidget):
    """Simple installer window"""
    
    def __init__(self):
        super().__init__()
        self.install_worker = None
        self.setup_ui()
        
        # Start installation after window is shown
        QTimer.singleShot(500, self.start_installation)
    
    def setup_ui(self):
        """Setup the UI"""
        self.setWindowTitle("Diode Tester V5 - Installer")
        self.setFixedSize(600, 500)
        
        # Main layout
        layout = QVBoxLayout()
        layout.setSpacing(20)
        self.setLayout(layout)
        
        # Logo/Title
        title = QLabel("DIODE DYNAMICS")
        title_font = QFont("Arial", 24, QFont.Bold)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #0066cc; margin: 20px;")
        layout.addWidget(title)
        
        subtitle = QLabel("Production Tester V5 - Installation")
        subtitle_font = QFont("Arial", 14)
        subtitle.setFont(subtitle_font)
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        
        # Status label
        self.status_label = QLabel("Preparing installation...")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # Log output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(200)
        layout.addWidget(self.log_output)
        
        # Close button (disabled initially)
        self.close_button = QPushButton("Close")
        self.close_button.setEnabled(False)
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.close_button)
        
        # Apply some styling
        self.setStyleSheet("""
            QWidget {
                background-color: #f0f0f0;
            }
            QProgressBar {
                border: 2px solid #cccccc;
                border-radius: 5px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #0066cc;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #0066cc;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0052a3;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QTextEdit {
                border: 1px solid #cccccc;
                border-radius: 5px;
                padding: 5px;
            }
        """)
    
    def start_installation(self):
        """Start the installation process"""
        self.log_output.append("Starting installation process...")
        self.log_output.append(f"Python version: {sys.version}")
        self.log_output.append("")
        
        # Start package installation
        self.install_worker = InstallWorker()
        self.install_worker.progress.connect(self.update_progress)
        self.install_worker.log_message.connect(self.add_log_message)
        self.install_worker.finished.connect(self.installation_finished)
        self.install_worker.start()
    
    def update_progress(self, value, message):
        """Update progress bar and status"""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
    
    def add_log_message(self, message):
        """Add message to log output"""
        self.log_output.append(message)
    
    def installation_finished(self, success, message):
        """Handle installation completion"""
        if success:
            self.status_label.setText("Installation Complete!")
            self.add_log_message("")
            self.add_log_message("✓ " + message)
            
            # Create desktop shortcut
            self.add_log_message("")
            self.add_log_message("Creating desktop shortcut...")
            self.create_shortcut()
            
        else:
            self.status_label.setText("Installation Failed!")
            self.add_log_message("")
            self.add_log_message("✗ ERROR: " + message)
            QMessageBox.critical(self, "Installation Failed", message)
        
        self.close_button.setEnabled(True)
    
    def create_shortcut(self):
        """Create desktop shortcut"""
        try:
            script_dir = Path(__file__).parent
            shortcut_script = script_dir / "create_professional_shortcut.bat"
            
            if shortcut_script.exists():
                result = subprocess.run(
                    [str(shortcut_script), "silent"],
                    capture_output=True,
                    shell=True
                )
                
                if result.returncode == 0:
                    self.add_log_message("✓ Desktop shortcut created successfully!")
                    
                    # Show success message
                    QMessageBox.information(
                        self,
                        "Installation Complete",
                        "Diode Tester V5 has been installed successfully!\n\n"
                        "A shortcut has been created on your desktop.\n"
                        "Double-click 'Diode Tester V5' to start the application."
                    )
                else:
                    self.add_log_message("✗ Could not create shortcut automatically")
                    self.add_log_message("  Please create manually by right-clicking main.py")
            else:
                self.add_log_message("✗ Shortcut creator script not found")
                
        except Exception as e:
            self.add_log_message(f"✗ Shortcut creation error: {e}")


def main():
    """Run the installer"""
    app = QApplication(sys.argv)
    app.setApplicationName("Diode Tester V5 Installer")
    
    # Create and show installer
    installer = SimpleInstaller()
    installer.show()
    
    # Center on screen
    screen = app.primaryScreen().geometry()
    x = (screen.width() - installer.width()) // 2
    y = (screen.height() - installer.height()) // 2
    installer.move(x, y)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()