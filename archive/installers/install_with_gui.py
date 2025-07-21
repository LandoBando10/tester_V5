#!/usr/bin/env python3
"""
Diode Tester V5 - GUI Installer
Uses the existing splash screen for a professional installation experience
"""

import sys
import subprocess
import os
from pathlib import Path

# Early imports for GUI
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog
from PySide6.QtCore import Qt, QTimer, QThread, Signal

# Import the existing splash screen
sys.path.insert(0, str(Path(__file__).parent))
from src.gui.startup import UnifiedSplashScreen


class InstallWorker(QThread):
    """Worker thread for package installation"""
    progress = Signal(int, str)
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
                
                # Install package
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade", package, "--quiet"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0 and package != "pyqtgraph":  # pyqtgraph is optional
                    self.finished.emit(False, f"Failed to install {package}: {result.stderr}")
                    return
            
            self.progress.emit(100, "Installation complete!")
            self.finished.emit(True, "All packages installed successfully!")
            
        except Exception as e:
            self.finished.emit(False, str(e))


class InstallerSplashScreen(UnifiedSplashScreen):
    """Modified splash screen for installation"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Diode Tester V5 - Installer")
        self.install_worker = None
        self.install_complete = False
        
        # Hide mode selection buttons
        self.offroad_btn.hide()
        self.smt_btn.hide()
        self.weight_btn.hide()
        
        # Update status
        self.update_status("Preparing installation...")
        
        # Start installation after splash is shown
        QTimer.singleShot(1000, self.start_installation)
    
    def start_installation(self):
        """Start the installation process"""
        self.update_status("Checking Python installation...")
        
        # Check Python version
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        self.add_loading_message(f"Python {python_version} detected")
        
        if sys.version_info < (3, 8):
            QMessageBox.critical(
                self,
                "Python Version Error",
                "Python 3.8 or newer is required.\n"
                f"You have Python {python_version}.\n\n"
                "Please update Python and try again."
            )
            self.close()
            return
        
        # Start package installation
        self.update_status("Installing required packages...")
        self.install_worker = InstallWorker()
        self.install_worker.progress.connect(self.update_install_progress)
        self.install_worker.finished.connect(self.installation_finished)
        self.install_worker.start()
    
    def update_install_progress(self, progress, message):
        """Update installation progress"""
        self.update_progress(progress)
        self.update_status(message)
        self.add_loading_message(message)
    
    def installation_finished(self, success, message):
        """Handle installation completion"""
        if success:
            self.install_complete = True
            self.update_status("Installation complete!")
            self.add_loading_message(message)
            
            # Create desktop shortcut
            QTimer.singleShot(1000, self.create_shortcut)
        else:
            QMessageBox.critical(
                self,
                "Installation Failed",
                f"Installation failed:\n\n{message}\n\n"
                "Please check your internet connection and try again."
            )
            self.close()
    
    def create_shortcut(self):
        """Create desktop shortcut"""
        self.update_status("Creating desktop shortcut...")
        
        try:
            # Run the shortcut creation script
            script_dir = Path(__file__).parent
            shortcut_script = script_dir / "create_professional_shortcut.bat"
            
            if shortcut_script.exists():
                result = subprocess.run(
                    [str(shortcut_script), "silent"],
                    capture_output=True,
                    shell=True
                )
                
                if result.returncode == 0:
                    self.add_loading_message("Desktop shortcut created successfully!")
                else:
                    self.add_loading_message("Could not create shortcut automatically")
            
            # Show completion message
            QTimer.singleShot(1500, self.show_completion)
            
        except Exception as e:
            self.add_loading_message(f"Shortcut creation error: {e}")
            QTimer.singleShot(1500, self.show_completion)
    
    def show_completion(self):
        """Show installation completion message"""
        self.update_status("Installation Complete!")
        
        # Show completion dialog
        msg = QMessageBox(self)
        msg.setWindowTitle("Installation Complete")
        msg.setText("Diode Tester V5 has been installed successfully!")
        msg.setInformativeText(
            "A shortcut has been created on your desktop.\n"
            "Double-click 'Diode Tester V5' to start the application."
        )
        msg.setIcon(QMessageBox.Information)
        msg.exec()
        
        # Close installer
        self.close()
    
    def closeEvent(self, event):
        """Handle close event"""
        if self.install_worker and self.install_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Installation in Progress",
                "Installation is still in progress.\n"
                "Are you sure you want to cancel?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                event.ignore()
                return
        
        event.accept()


def main():
    """Run the installer"""
    app = QApplication(sys.argv)
    app.setApplicationName("Diode Tester V5 Installer")
    
    # Show installer splash
    installer = InstallerSplashScreen()
    installer.show_centered()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()