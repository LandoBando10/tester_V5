# gui/components/menu_bar.py
import logging
from PySide6.QtWidgets import QMenuBar, QMenu, QMessageBox, QDialog
from PySide6.QtGui import QAction
from PySide6.QtCore import QObject, Signal
import subprocess
import sys
from pathlib import Path
import webbrowser

logger = logging.getLogger(__name__)

class TestMenuBar(QMenuBar):
    """Custom menu bar for the test application"""
    
    # Signals
    mode_changed = Signal(str)
    show_connections_requested = Signal()
    refresh_ports_requested = Signal() # Added
    
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.debug("Initializing TestMenuBar") # Added
        self.mode_actions = {}
        try: # Added
            self.setup_menus()
            self.apply_dark_style()
            logger.debug("TestMenuBar UI setup and styling successful") # Added
        except Exception as e: # Added
            logger.error("Error during TestMenuBar initialization: %s", e, exc_info=True) # Added
            # Fallback: Create a minimal menu or show an error message
            self._setup_fallback_menu() # Added
    
    def setup_menus(self):
        """Setup the menu structure"""
        logger.debug("Setting up menus") # Added
        try: # Added
            # Modes Menu
            modes_menu = self.addMenu("Modes")
            self.setup_modes_menu(modes_menu)
            
            # Connection Menu
            connection_menu = self.addMenu("Connection")
            self.setup_connection_menu(connection_menu)
            
            # Tools Menu
            tools_menu = self.addMenu("Tools")
            self.setup_tools_menu(tools_menu)
            
            # SPC Menu
            spc_menu = self.addMenu("SPC")
            self.setup_spc_menu(spc_menu)
            
            # Help Menu
            help_menu = self.addMenu("Help")
            self.setup_help_menu(help_menu)
            logger.info("All menus set up successfully.") # Added
        except Exception as e: # Added
            logger.error("Failed to set up menus: %s", e, exc_info=True) # Added
            self.clear() # Clear any partially created menus
            self._setup_fallback_menu() # Added

    def _setup_fallback_menu(self): # Added
        """Sets up a minimal fallback menu in case of errors.""" # Added
        logger.warning("Setting up fallback menu for TestMenuBar.") # Added
        try: # Added
            help_menu = self.addMenu("Help") # Added
            about_action = QAction("About...", self) # Added
            about_action.triggered.connect(self.show_about) # Added
            help_menu.addAction(about_action) # Added
            QMessageBox.warning(self, "Menu Error", "Failed to load all menu items. Some functionality may be unavailable.") # Added
        except Exception as e: # Added
            logger.critical("Failed to setup even fallback menu: %s", e, exc_info=True) # Added
    
    def setup_modes_menu(self, menu: QMenu):
        """Setup the modes menu"""
        logger.debug("Setting up modes menu") # Added
        try: # Added
            modes = ["Offroad", "SMT", "WeightChecking"]
            
            for mode in modes:
                action = QAction(mode, self)
                action.setCheckable(True)
                if mode == "Offroad": # Default mode
                    action.setChecked(True)
                action.triggered.connect(lambda checked, m=mode: self.set_mode(m))
                menu.addAction(action)
                self.mode_actions[mode] = action
            logger.info("Modes menu setup complete.") # Added
        except Exception as e: # Added
            logger.error("Failed to set up modes menu: %s", e, exc_info=True) # Added
            menu.addAction(QAction("Error loading modes", self, enabled=False)) # Added
    
    def setup_connection_menu(self, menu: QMenu):
        """Setup the connection menu"""
        logger.debug("Setting up connection menu") # Added
        try: # Added
            # Hardware connections action
            connections_action = QAction("Hardware Connections...", self)
            connections_action.triggered.connect(self.show_connections_requested.emit)
            menu.addAction(connections_action)
            
            menu.addSeparator()
            
            # Refresh connections
            refresh_action = QAction("Refresh Ports", self)
            refresh_action.triggered.connect(self.refresh_ports_requested.emit) # Modified
            menu.addAction(refresh_action)
            logger.info("Connection menu setup complete.") # Added
        except Exception as e: # Added
            logger.error("Failed to set up connection menu: %s", e, exc_info=True) # Added
            menu.addAction(QAction("Error loading connection items", self, enabled=False)) # Added
    
    def setup_tools_menu(self, menu: QMenu):
        """Setup the tools menu"""
        logger.debug("Setting up tools menu") # Added
        try: # Added
            # SMT Setup Utility
            smt_setup_action = QAction("SMT Setup Utility...", self)
            smt_setup_action.triggered.connect(self.show_smt_setup)
            menu.addAction(smt_setup_action)
            
            menu.addSeparator()
            
            # Configuration Editor
            config_action = QAction("Edit SKU Configuration...", self) # Modified
            config_action.triggered.connect(self.show_config_editor)
            menu.addAction(config_action)
            
            # Programming Configuration
            programming_action = QAction("Programming Configuration...", self)
            programming_action.triggered.connect(self.show_programming_config)
            menu.addAction(programming_action)
            
            menu.addSeparator()
            
            # View Logs
            logs_action = QAction("View Logs...", self)
            logs_action.triggered.connect(self.show_logs)
            menu.addAction(logs_action)
            
            
            logger.info("Tools menu setup complete.") # Added
        except Exception as e: # Added
            logger.error("Failed to set up tools menu: %s", e, exc_info=True) # Added
            menu.addAction(QAction("Error loading tools", self, enabled=False)) # Added
    
    def setup_help_menu(self, menu: QMenu):
        """Setup the help menu"""
        logger.debug("Setting up help menu") # Added
        try: # Added
            # About
            about_action = QAction("About...", self)
            about_action.triggered.connect(self.show_about)
            menu.addAction(about_action)
            
            # Documentation
            docs_action = QAction("Documentation", self)
            docs_action.triggered.connect(self.show_documentation)
            menu.addAction(docs_action)
            
            menu.addSeparator()
            
            # View Production Log
            prod_log_action = QAction("View Production Log", self)
            prod_log_action.triggered.connect(self.show_production_log)
            menu.addAction(prod_log_action)
            
            # View Critical Errors Log
            critical_log_action = QAction("View Critical Errors Log", self)
            critical_log_action.triggered.connect(self.show_critical_errors_log)
            menu.addAction(critical_log_action)
            
            logger.info("Help menu setup complete.") # Added
        except Exception as e: # Added
            logger.error("Failed to set up help menu: %s", e, exc_info=True) # Added
            menu.addAction(QAction("Error loading help items", self, enabled=False)) # Added
    
    def apply_dark_style(self):
        """Apply dark theme styling"""
        logger.debug("Applying dark style to TestMenuBar") # Added
        try: # Added
            self.setStyleSheet("""
                QMenuBar {
                    background-color: #2b2b2b;
                    color: white;
                    font-size: 12px;
                    padding: 2px;
                }
                QMenuBar::item {
                    background-color: transparent;
                    padding: 8px 12px;
                    margin: 0px 2px;
                    border-radius: 4px;
                }
                QMenuBar::item:selected {
                    background-color: #404040;
                }
                QMenu {
                    background-color: #2b2b2b;
                    color: white;
                    border: 1px solid #404040;
                }
                QMenu::item {
                    padding: 8px 20px;
                }
                QMenu::item:selected {
                    background-color: #404040;
                }
                QMenu::separator {
                    height: 1px;
                    background-color: #404040;
                    margin: 2px 0px;
                }
            """)
            logger.info("Dark style applied successfully.") # Added
        except Exception as e: # Added
            logger.error("Failed to apply dark style: %s", e, exc_info=True) # Added
    
    def setup_spc_menu(self, menu: QMenu):
        """Setup the SPC menu"""
        logger.debug("Setting up SPC menu")
        try:
            # SPC Control
            spc_action = QAction("SPC Control...", self)
            spc_action.setStatusTip("Open Statistical Process Control panel")
            spc_action.triggered.connect(self.show_spc_control)
            menu.addAction(spc_action)
            
            # Spec Limit Calculator
            spec_calc_action = QAction("Spec Limit Calculator...", self)
            spec_calc_action.triggered.connect(self.show_spec_calculator)
            menu.addAction(spec_calc_action)
            
            logger.info("SPC menu setup complete.")
        except Exception as e:
            logger.error("Failed to set up SPC menu: %s", e, exc_info=True)
            menu.addAction(QAction("Error loading SPC items", self, enabled=False))
    
    def set_mode(self, mode: str):
        """Set the current mode and update menu"""
        logger.info(f"Setting mode to: {mode}") # Added
        try: # Added
            # Update mode actions without triggering signals
            # Only update if it's a standard mode (not Configuration)
            if mode in self.mode_actions:
                for m, action in self.mode_actions.items():
                    # Temporarily block signals to prevent infinite recursion
                    action.blockSignals(True)
                    action.setChecked(m == mode)
                    action.blockSignals(False)
            else:
                # Configuration mode - uncheck all mode actions
                for action in self.mode_actions.values():
                    action.blockSignals(True)
                    action.setChecked(False)
                    action.blockSignals(False)
            
            logger.debug(f"Mode menu updated for {mode}") # Added
        except Exception as e: # Added
            logger.error(f"Error setting mode to {mode}: %s", e, exc_info=True) # Added
            QMessageBox.warning(self, "Mode Change Error", f"Could not switch to mode: {mode}") # Added
    
    def refresh_connections(self):
        """Refresh connection ports - Now emits a signal""" # Modified
        logger.info("Refresh connections requested by user.") # Added
        self.refresh_ports_requested.emit() # Added
            
    def show_smt_setup(self):
        """Show SMT setup utility - SECURITY HARDENED"""
        logger.info("Attempting to launch SMT Setup Utility") # Added
        try:
            # from pathlib import Path # Moved to top
            
            # Securely build path to utility
            # The utility is in the tools directory at project root
            utility_path = Path(__file__).parent.parent.parent.parent / "tools" / "smt_setup_utility.py" # Modified
            utility_path = utility_path.resolve()
            
            # Security validation
            if not utility_path.exists():
                logger.warning(f"SMT Setup Utility not found at {utility_path}") # Added
                QMessageBox.information(self, "SMT Setup Utility", 
                                        f"SMT Setup Utility not found. Please ensure it exists at expected location: {utility_path.parent}") # Modified
                return
            
            # Validate it's actually in our tools directory (prevent path traversal)
            expected_dir = (Path(__file__).parent.parent.parent.parent / "tools").resolve() # Modified
            if not str(utility_path).startswith(str(expected_dir)):
                logger.error(f"Security Error: Invalid SMT utility path detected: {utility_path}. Expected to be in {expected_dir}") # Added
                QMessageBox.critical(self, "Security Error", "Invalid utility path detected.")
                return
            
            logger.debug(f"Executing SMT Setup Utility: {sys.executable} {utility_path}") # Added
            # Execute with security settings
            process = subprocess.Popen([
                sys.executable, str(utility_path)
            ], 
            shell=False,  # SECURITY: Never use shell=True
            cwd=None,     # SECURITY: Don't inherit working directory
            env=None,      # SECURITY: Use clean environment
            start_new_session=True # Detach from parent # Added
            )
            logger.info(f"SMT Setup Utility launched with PID: {process.pid}") # Added
            
        except Exception as e:
            logger.error("Could not launch SMT Setup Utility: %s", e, exc_info=True) # Modified
            QMessageBox.critical(self, "Error", f"Could not launch SMT Setup Utility: {e}")
    
    def show_config_editor(self):
        """Show configuration editor in test area"""
        logger.info("Opening Configuration Editor in test area") # Added
        try:
            # Directly set the mode on the main window to Configuration
            if hasattr(self.parent(), 'set_mode'):
                self.parent().set_mode("Configuration")
            else:
                logger.error("Parent window does not have set_mode method")
            logger.debug("SKU Configuration Editor closed.") # Added
            
        except ImportError as ie: # Added
            logger.error("Failed to import ConfigurationEditor: %s", ie, exc_info=True) # Added
            QMessageBox.critical(self, "Import Error", f"Could not load the SKU Configuration Editor module: {ie}\nPlease check application components.") # Added
        except Exception as e:
            logger.error("Could not open SKU configuration editor: %s", e, exc_info=True) # Modified
            QMessageBox.critical(self, "Error", f"Could not open SKU configuration editor: {e}")
    
    # def on_configuration_changed(self): # Removed as it was unused, can be re-added if needed
    #     """Handle configuration changes""" # Removed
    #     logger.debug("Configuration changed signal received in menu bar.") # Removed
    #     # This signal can be connected to update other parts of the application
    #     # when configuration changes are saved
    #     pass # Removed
    
    def show_programming_config(self):
        """Show programming configuration editor"""
        logger.info("Attempting to show Programming Configuration dialog") # Added
        try:
            # Get main window reference to call the method
            main_window = self.parent() # Or self.window() if parent is not direct main_window
            if main_window and hasattr(main_window, 'open_programming_config'):
                logger.debug("Calling main_window.open_programming_config()") # Added
                main_window.open_programming_config()
            else:
                logger.warning("Main window not found or does not have 'open_programming_config' method.") # Added
                QMessageBox.information(self, "Programming Configuration", 
                                        "Programming configuration feature not available or main window context lost.") # Modified
        except Exception as e:
            logger.error("Could not open programming configuration: %s", e, exc_info=True) # Modified
            QMessageBox.critical(self, "Error", f"Could not open programming configuration: {e}")
    
    def show_logs(self):
        """Show application logs - SECURITY HARDENED"""
        logger.info("Attempting to open logs directory") # Added
        try:
            # from pathlib import Path # Moved to top
            
            # Securely build path to logs directory
            logs_dir = (Path(__file__).parent.parent.parent.parent / "logs").resolve() # Modified
            
            # Security validation - ensure logs directory exists and is in expected location
            if not logs_dir.exists() or not logs_dir.is_dir(): # Added check for is_dir
                logger.warning(f"Logs directory not found or is not a directory: {logs_dir}") # Added
                QMessageBox.information(self, "Logs", f"Logs directory not found at {logs_dir}.") # Modified
                return
            
            # Validate it's actually in our project directory (prevent path traversal)
            # Assuming project root is parent of src directory
            project_root = (Path(__file__).parent.parent.parent.parent).resolve() # Modified
            if not str(logs_dir).startswith(str(project_root)):
                logger.error(f"Security Error: Invalid logs path detected: {logs_dir}. Expected to be within {project_root}") # Added
                QMessageBox.critical(self, "Security Error", "Invalid logs path detected.")
                return
            
            logger.debug(f"Opening logs directory: {logs_dir}") # Added
            # Execute with security settings based on platform
            if sys.platform.startswith('win'):
                # Use os.startfile for a more robust way to open explorer on Windows
                import os # Added
                try: # Added
                    os.startfile(str(logs_dir)) # Added
                    logger.info(f"Successfully requested to open logs directory on Windows: {logs_dir}") # Added
                except Exception as e_win: # Added
                    logger.error(f"Failed to open logs directory with os.startfile on Windows: {e_win}", exc_info=True) # Added
                    # Fallback to explorer if startfile fails for some reason
                    subprocess.run(['explorer', str(logs_dir)], check=False, shell=False, timeout=10) # Added

            elif sys.platform.startswith('darwin'): # macOS
                subprocess.run(['open', str(logs_dir)], check=True, shell=False, timeout=10)
                logger.info(f"Successfully requested to open logs directory on macOS: {logs_dir}") # Added
            else: # Linux and other POSIX
                # Check if we're on WSL
                import platform
                if 'microsoft' in platform.uname().release.lower():
                    # We're on WSL, use explorer.exe
                    try:
                        # Convert WSL path to Windows path
                        windows_path = str(logs_dir).replace('/mnt/c/', 'C:\\')
                        subprocess.run(['explorer.exe', windows_path], check=True, shell=False, timeout=10)
                        logger.info(f"Successfully requested to open logs directory on WSL: {windows_path}")
                    except Exception as e:
                        logger.error(f"Failed to open logs directory on WSL: {e}", exc_info=True)
                        # Try with WSL path as fallback
                        subprocess.run(['explorer.exe', str(logs_dir)], check=False, shell=False, timeout=10)
                else:
                    # Regular Linux
                    subprocess.run(['xdg-open', str(logs_dir)], check=True, shell=False, timeout=10)
                    logger.info(f"Successfully requested to open logs directory with xdg-open: {logs_dir}") # Added
                
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout opening logs directory: {logs_dir}") # Added
            QMessageBox.information(self, "Logs", "Timeout opening logs directory.")
        except FileNotFoundError as fnf_error: # Added
            logger.error(f"Command not found for opening logs (e.g., explorer, open, xdg-open): {fnf_error}", exc_info=True) # Added
            QMessageBox.warning(self, "Logs", f"Could not find a program to open the logs directory: {fnf_error.strerror}") # Added
        except Exception as e:
            logger.error(f"Could not open logs directory {logs_dir}: {e}", exc_info=True) # Modified
            QMessageBox.information(self, "Logs", f"Could not open logs directory: {e}")
    
    def show_about(self):
        """Show about dialog with company logo"""
        logger.info("Showing About dialog") # Added
        try: # Added
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
            from PySide6.QtGui import QPixmap, QFont
            from PySide6.QtCore import Qt
            # from pathlib import Path # Moved to top
            
            dialog = QDialog(self)
            dialog.setWindowTitle("About Diode Dynamics Tester")
            dialog.setFixedSize(450, 350) # Consider making this resizable or dynamic
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #2b2b2b;
                    color: white;
                }
                QLabel {
                    color: white;
                }
            """)
            
            layout = QVBoxLayout(dialog)
            layout.setSpacing(20)
            layout.setContentsMargins(30, 30, 30, 30)
            
            # Header with logo
            header_layout = QHBoxLayout()
            header_layout.setSpacing(15)
            
            # Large logo
            logo_label = QLabel()
            # Corrected path assuming 'gui' is a top-level directory or relative to execution
            # Best practice: make path relative to this file or an assets directory
            logo_path = Path(__file__).parent.parent / "small Square DD Logo 2015_2.jpg" # Modified
            logger.debug(f"Attempting to load logo for About dialog from: {logo_path}") # Added

            if logo_path.exists():
                pixmap = QPixmap(str(logo_path))
                if not pixmap.isNull(): # Added
                    scaled_pixmap = pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    logo_label.setPixmap(scaled_pixmap)
                    logo_label.setStyleSheet("""
                        border: 2px solid #555555;
                        border-radius: 8px;
                        padding: 5px;
                        background-color: white;
                    """)
                    logger.debug("Logo loaded successfully for About dialog.") # Added
                else: # Added
                    logger.warning(f"Failed to create QPixmap for About dialog logo from {logo_path}. File might be corrupted.") # Added
                    self._set_default_about_logo_text(logo_label) # Added
            else:
                logger.warning(f"Logo file not found for About dialog at: {logo_path}") # Added
                self._set_default_about_logo_text(logo_label) # Added
            
            header_layout.addWidget(logo_label)
            
            # Title section
            title_layout = QVBoxLayout()
            title_layout.setSpacing(5)
            
            title_label = QLabel("Diode Dynamics")
            title_label.setFont(QFont("Arial", 20, QFont.Bold))
            title_layout.addWidget(title_label)
            
            subtitle_label = QLabel("Production Test System")
            subtitle_label.setFont(QFont("Arial", 14))
            subtitle_label.setStyleSheet("color: #b0b0b0;")
            title_layout.addWidget(subtitle_label)
            
            version_label = QLabel("Version 4.0") # Consider making this dynamic
            version_label.setFont(QFont("Arial", 12))
            version_label.setStyleSheet("color: #888888;")
            title_layout.addWidget(version_label)
            
            title_layout.addStretch()
            header_layout.addLayout(title_layout)
            header_layout.addStretch()
            
            layout.addLayout(header_layout)
            
            # Description
            desc_label = QLabel("Comprehensive testing system for LED lighting products")
            desc_label.setFont(QFont("Arial", 11))
            desc_label.setStyleSheet("color: #cccccc;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
            
            # Features
            features_label = QLabel("""
            <b>Features:</b><br>
            • Offroad testing (LUX, COLOR, PRESSURE, POWER)<br>
            • SMT testing with programming support<br>
            • Weight checking integration<br>
            • Multi-board programming (STM8/PIC)<br>
            • Real-time hardware monitoring
            """)
            features_label.setFont(QFont("Arial", 10))
            features_label.setStyleSheet("color: #cccccc;")
            features_label.setWordWrap(True)
            layout.addWidget(features_label)
            
            # Copyright
            copyright_label = QLabel("© 2024 Diode Dynamics - Quality Engineering") # Consider dynamic year
            copyright_label.setFont(QFont("Arial", 9))
            copyright_label.setStyleSheet("color: #888888;")
            copyright_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(copyright_label)
            
            # Close button
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            
            close_btn = QPushButton("Close")
            close_btn.setFixedSize(80, 30)
            close_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a90a4;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #5ba3b8;
                }
            """)
            close_btn.clicked.connect(dialog.accept)
            button_layout.addWidget(close_btn)
            button_layout.addStretch()
            
            layout.addLayout(button_layout)
            
            dialog.exec()
            logger.debug("About dialog closed.") # Added
        except Exception as e: # Added
            logger.error("Failed to show About dialog: %s", e, exc_info=True) # Added
            QMessageBox.critical(self, "Error", f"Could not display the About dialog: {e}") # Added

    def _set_default_about_logo_text(self, label_widget): # Added
        """Sets a default text for the About dialog logo if image loading fails.""" # Added
        logger.info("Setting default text for About dialog logo area.") # Added
        label_widget.setText("DD") # Added
        label_widget.setAlignment(Qt.AlignCenter) # Added
        label_widget.setStyleSheet(""" # Added
            background-color: #0078d4;
            color: white;
            font-size: 30px;
            font-weight: bold;
            border-radius: 8px;
            min-width: 80px;
            min-height: 80px;
        """) # Added
    
    def show_documentation(self):
        """Show documentation"""
        logger.info("Attempting to open documentation") # Added
        try:
            # from webbrowser import open # Moved to top
            # from pathlib import Path # Moved to top
            
            # Try to open local documentation
            # Assuming 'docs' is a sibling of 'gui' directory
            docs_path = (Path(__file__).parent.parent.parent / "docs" / "arduino_smt_protocol.md").resolve() # Modified
            logger.debug(f"Looking for documentation at: {docs_path}") # Added

            if docs_path.exists() and docs_path.is_file(): # Added is_file check
                # Use file URI scheme for local files
                webbrowser.open(docs_path.as_uri()) # Modified
                logger.info(f"Opened documentation: {docs_path.as_uri()}") # Added
            else:
                logger.warning(f"Documentation file not found or is not a file: {docs_path}") # Added
                QMessageBox.information(self, "Documentation", 
                                        f"Documentation file not found in the expected directory: {docs_path.parent}") # Modified
        except Exception as e:
            logger.error("Could not open documentation: %s", e, exc_info=True) # Modified
            QMessageBox.information(self, "Documentation", f"Could not open documentation: {e}")
    
    def show_spc_control(self):
        """Show SPC control dialog"""
        logger.info("SPC Control requested")
        try:
            # Get main window reference to call the method
            main_window = self.parent()
            if main_window and hasattr(main_window, 'show_spc_control'):
                main_window.show_spc_control()
            else:
                logger.warning("Main window not found or does not have 'show_spc_control' method.")
                QMessageBox.information(self, "SPC Control", 
                                        "SPC Control feature not available.")
        except Exception as e:
            logger.error(f"Could not open SPC control: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Could not open SPC control: {e}")
    
    def show_spec_calculator(self):
        """Show spec limit calculator with authentication"""
        logger.info("Spec Limit Calculator requested")
        try:
            # First authenticate
            from src.gui.components.spec_approval_dialog import LoginDialog
            
            login_dialog = LoginDialog(self)
            login_dialog.setWindowTitle("Spec Limit Calculator - Authentication")
            
            if login_dialog.exec_() == QDialog.Accepted:
                username, password = login_dialog.get_credentials()
                
                # Verify credentials
                from src.auth.user_manager import get_user_manager
                user_manager = get_user_manager()
                
                if user_manager.authenticate(username, password):
                    if user_manager.has_permission('modify_specs'):
                        # Enable spec calculator mode in main window
                        main_window = self.parent()
                        if main_window and hasattr(main_window, 'enable_spec_calculator'):
                            main_window.enable_spec_calculator()
                            logger.info(f"Spec calculator enabled for user: {username}")
                        else:
                            # Fallback - enable it differently
                            self._enable_spec_calculator_mode()
                    else:
                        QMessageBox.warning(self, "Access Denied", 
                                          f"User '{username}' does not have permission to use the Spec Limit Calculator.")
                        user_manager.logout()
                else:
                    QMessageBox.warning(self, "Authentication Failed", 
                                      "Invalid username or password.")
        except Exception as e:
            logger.error(f"Error showing spec calculator: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Could not open Spec Limit Calculator: {e}")
    
    def _enable_spec_calculator_mode(self):
        """Fallback method to enable spec calculator"""
        try:
            main_window = self.parent()
            if main_window:
                # Set a flag that the handlers can check
                main_window.spec_calculator_enabled = True
                QMessageBox.information(self, "Spec Limit Calculator", 
                                      "Spec Limit Calculator is now active.\n\n"
                                      "Run 30 tests to calculate new specification limits.")
        except Exception as e:
            logger.error(f"Error enabling spec calculator mode: {e}")
    
    def show_production_log(self):
        """Show production log in a viewer dialog"""
        logger.info("Opening production log viewer")
        try:
            from src.gui.components.log_viewer_dialog import LogViewerDialog
            
            # Build path to production log
            log_path = Path(__file__).parent.parent.parent.parent / "logs" / "production_test.log"
            log_path = log_path.resolve()
            
            if not log_path.exists():
                QMessageBox.information(self, "Production Log", 
                                      f"Production log not found at:\n{log_path}")
                return
                
            # Create and show log viewer
            viewer = LogViewerDialog(str(log_path), "Production Test Log", self)
            viewer.show()  # Non-modal
            
        except Exception as e:
            logger.error(f"Error showing production log: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Could not open production log: {e}")
    
    def show_critical_errors_log(self):
        """Show critical errors log in a viewer dialog"""
        logger.info("Opening critical errors log viewer")
        try:
            from src.gui.components.log_viewer_dialog import LogViewerDialog
            
            # Build path to critical errors log
            log_path = Path(__file__).parent.parent.parent.parent / "logs" / "critical_errors.log"
            log_path = log_path.resolve()
            
            if not log_path.exists():
                QMessageBox.information(self, "Critical Errors Log", 
                                      f"Critical errors log not found at:\n{log_path}")
                return
                
            # Create and show log viewer
            viewer = LogViewerDialog(str(log_path), "Critical Errors Log", self)
            viewer.show()  # Non-modal
            
        except Exception as e:
            logger.error(f"Error showing critical errors log: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Could not open critical errors log: {e}")