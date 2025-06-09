"""
Configuration Loading Dialog
Shows progress while loading configuration data asynchronously
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, 
    QPushButton, QTextEdit, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPixmap, QMovie
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

class ConfigLoadingDialog(QDialog):
    """Progress dialog for configuration loading with detailed feedback"""
    
    # Signals
    load_cancelled = Signal()
    retry_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Loading Configuration")
        self.setModal(True)
        self.setFixedSize(480, 320)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        logger.debug("ConfigLoadingDialog initialized.")
        
        # State tracking
        self.start_time = time.time()
        self.current_step = ""
        self.is_completed = False
        self.load_success = False
        
        self.setup_ui()
        self.apply_styling()
        
        # Update timer for elapsed time
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_elapsed_time)
        self.update_timer.start(100)  # Update every 100ms
    
    def setup_ui(self):
        """Setup the dialog UI"""
        logger.debug("Setting up ConfigLoadingDialog UI.")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header section
        header_layout = QHBoxLayout()
        
        # Icon/Logo area (placeholder for now)
        icon_label = QLabel("⚙️")
        icon_label.setFont(QFont("Arial", 24))
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(icon_label)
        
        # Title and description
        title_layout = QVBoxLayout()
        
        self.title_label = QLabel("Loading Configuration")
        self.title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_layout.addWidget(self.title_label)
        
        self.description_label = QLabel("Loading SKU configurations and test parameters...")
        self.description_label.setFont(QFont("Arial", 10))
        title_layout.addWidget(self.description_label)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        # Progress section
        progress_layout = QVBoxLayout()
        
        # Current step label
        self.step_label = QLabel("Initializing...")
        self.step_label.setFont(QFont("Arial", 11))
        progress_layout.addWidget(self.step_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar)
        
        # Status information
        status_layout = QHBoxLayout()
        
        self.elapsed_label = QLabel("Elapsed: 0.0s")
        self.elapsed_label.setFont(QFont("Arial", 9))
        status_layout.addWidget(self.elapsed_label)
        
        status_layout.addStretch()
        
        self.details_label = QLabel("")
        self.details_label.setFont(QFont("Arial", 9))
        status_layout.addWidget(self.details_label)
        
        progress_layout.addLayout(status_layout)
        
        layout.addLayout(progress_layout)
        
        # Details section (initially hidden)
        self.details_group = QFrame()
        details_layout = QVBoxLayout(self.details_group)
        details_layout.setContentsMargins(0, 10, 0, 0)
        
        self.show_details_btn = QPushButton("Show Details")
        self.show_details_btn.clicked.connect(self.toggle_details)
        details_layout.addWidget(self.show_details_btn)
        
        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(100)
        self.details_text.setReadOnly(True)
        self.details_text.setVisible(False)
        details_layout.addWidget(self.details_text)
        
        layout.addWidget(self.details_group)
        
        # Button section
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.retry_button = QPushButton("Retry")
        self.retry_button.clicked.connect(self.retry_requested.emit)
        self.retry_button.setVisible(False)
        button_layout.addWidget(self.retry_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.on_cancel)
        button_layout.addWidget(self.cancel_button)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        self.close_button.setVisible(False)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        logger.debug("ConfigLoadingDialog UI setup complete.")
    
    def apply_styling(self):
        """Apply dark theme styling"""
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: white;
                border-radius: 8px;
            }
            QLabel {
                color: white;
            }
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 4px;
                background-color: #1e1e1e;
                color: white;
                text-align: center;
                font-weight: bold;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #4a90a4;
                border-radius: 3px;
                margin: 1px;
            }
            QPushButton {
                background-color: #555555;
                color: white;
                border: 1px solid #666666;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #666666;
                border-color: #777777;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #666666;
                border-color: #444444;
            }
            QTextEdit {
                background-color: #1e1e1e;
                color: #cccccc;
                border: 1px solid #555555;
                border-radius: 4px;
                font-family: 'Courier New';
                font-size: 9px;
            }
            QFrame[frameShape="4"] {
                color: #555555;
            }
        """)
    
    def update_progress(self, message: str, percentage: int):
        """Update progress display"""
        try:
            self.current_step = message
            self.step_label.setText(message)
            self.progress_bar.setValue(percentage)
            
            # Add to details log
            elapsed = time.time() - self.start_time
            log_entry = f"[{elapsed:.1f}s] {message}\n"
            self.details_text.append(log_entry)
            
            # Update details label
            if percentage < 100:
                self.details_label.setText(f"{percentage}%")
            else:
                self.details_label.setText("Complete")
            logger.debug(f"Progress updated: {message} - {percentage}%")
        except Exception as e:
            logger.error(f"Error updating progress: {e}", exc_info=True)
    
    def show_success(self, sku_count: int, load_time_ms: int):
        """Show successful completion"""
        try:
            self.is_completed = True
            self.load_success = True
            
            self.title_label.setText("Configuration Loaded Successfully")
            self.description_label.setText(f"Loaded {sku_count} SKUs in {load_time_ms}ms")
            self.step_label.setText("✓ Configuration ready for use")
            self.progress_bar.setValue(100)
            
            # Update buttons
            self.cancel_button.setVisible(False)
            self.close_button.setVisible(True)
            self.close_button.setDefault(True)
            logger.info(f"Configuration loaded successfully. SKUs: {sku_count}, Time: {load_time_ms}ms.")
            
            # Auto-close after 2 seconds if no user interaction
            QTimer.singleShot(2000, self.auto_close)
        except Exception as e:
            logger.error(f"Error in show_success: {e}", exc_info=True)
    
    def show_error(self, error_message: str):
        """Show error state"""
        try:
            self.is_completed = True
            self.load_success = False
            
            self.title_label.setText("Configuration Load Failed")
            self.description_label.setText("An error occurred while loading the configuration")
            self.step_label.setText(f"✗ Error: {error_message}")
            
            # Update buttons
            self.cancel_button.setText("Close") # Changed from self.cancel_button.setVisible(False) and self.retry_button.setVisible(True)
            self.retry_button.setVisible(True) # Ensure retry is visible
            self.close_button.setVisible(False) # Ensure close is hidden initially on error
            self.retry_button.setDefault(True)
            logger.error(f"Configuration load failed: {error_message}")
            
            # Add error to details
            elapsed = time.time() - self.start_time
            error_log = f"[{elapsed:.1f}s] ERROR: {error_message}\n"
            self.details_text.append(error_log)
            
            # Auto-show details on error
            if not self.details_text.isVisible():
                self.toggle_details()
        except Exception as e:
            logger.error(f"Error in show_error: {e}", exc_info=True)
    
    def toggle_details(self):
        """Toggle details text visibility"""
        try:
            is_visible = self.details_text.isVisible()
            self.details_text.setVisible(not is_visible)
            
            if is_visible:
                self.show_details_btn.setText("Show Details")
                self.setFixedSize(480, 320)
                logger.debug("Details hidden.")
            else:
                self.show_details_btn.setText("Hide Details")
                self.setFixedSize(480, 450)
                logger.debug("Details shown.")
        except Exception as e:
            logger.error(f"Error toggling details: {e}", exc_info=True)
    
    def update_elapsed_time(self):
        """Update elapsed time display"""
        try:
            if not self.is_completed:
                elapsed = time.time() - self.start_time
                self.elapsed_label.setText(f"Elapsed: {elapsed:.1f}s")
        except Exception as e:
            logger.error(f"Error updating elapsed time: {e}", exc_info=True)
    
    def auto_close(self):
        """Auto-close dialog if successful and no user interaction"""
        try:
            if self.load_success and self.is_completed and self.isVisible(): # Check if visible before accepting
                logger.info("Auto-closing ConfigLoadingDialog after success.")
                self.accept()
        except Exception as e:
            logger.error(f"Error during auto_close: {e}", exc_info=True)
    
    def on_cancel(self):
        """Handle cancel button click"""
        try:
            if not self.is_completed:
                logger.info("Configuration loading cancelled by user.")
                self.load_cancelled.emit()
            else:
                logger.info("Close button clicked after completion.")
            self.reject() # Use reject for cancel/close if not success
        except Exception as e:
            logger.error(f"Error in on_cancel: {e}", exc_info=True)
            self.reject() # Ensure dialog closes
    
    def reset_for_retry(self):
        """Reset dialog state for retry"""
        try:
            logger.info("Resetting ConfigLoadingDialog for retry.")
            self.start_time = time.time()
            self.is_completed = False
            self.load_success = False
            
            self.title_label.setText("Loading Configuration")
            self.description_label.setText("Loading SKU configurations and test parameters...")
            self.step_label.setText("Initializing...")
            self.progress_bar.setValue(0)
            self.details_label.setText("")
            
            # Reset buttons
            self.cancel_button.setText("Cancel")
            self.cancel_button.setVisible(True)
            self.retry_button.setVisible(False)
            self.close_button.setVisible(False)
            
            # Clear details
            self.details_text.clear()
            logger.debug("ConfigLoadingDialog state reset.")
        except Exception as e:
            logger.error(f"Error resetting for retry: {e}", exc_info=True)
    
    def closeEvent(self, event):
        """Handle dialog close event"""
        try:
            logger.debug(f"ConfigLoadingDialog closeEvent triggered. Is completed: {self.is_completed}")
            if not self.is_completed:
                logger.info("Configuration loading cancelled by closing dialog.")
                self.load_cancelled.emit()
            event.accept()
        except Exception as e:
            logger.error(f"Error in closeEvent: {e}", exc_info=True)
            event.accept() # Ensure dialog closes


class MinimalProgressDialog(QDialog):
    """Minimal progress dialog for faster loading scenarios"""
    
    load_cancelled = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Loading...")
        self.setModal(True)
        self.setFixedSize(300, 120)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        logger.debug("MinimalProgressDialog initialized.")
        
        self.setup_minimal_ui()
    
    def setup_minimal_ui(self):
        """Setup minimal UI"""
        logger.debug("Setting up MinimalProgressDialog UI.")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        # Message
        self.message_label = QLabel("Loading configuration...")
        self.message_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.message_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Cancel button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.load_cancelled.emit)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        logger.debug("MinimalProgressDialog UI setup complete.")
    
    def apply_minimal_styling(self):
        """Apply minimal dark theme styling"""
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: white;
            }
            QLabel {
                color: white;
                font-size: 12px;
            }
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 4px;
                background-color: #1e1e1e;
                color: white;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4a90a4;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #555555;
                color: white;
                border: 1px solid #666666;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
    
    def update_progress(self, message: str, percentage: int):
        """Update progress display"""
        try:
            self.message_label.setText(message)
            self.progress_bar.setValue(percentage)
            logger.debug(f"Minimal progress updated: {message} - {percentage}%")
        except Exception as e:
            logger.error(f"Error updating minimal progress: {e}", exc_info=True)
    
    def show_success(self):
        """Show success and auto-close"""
        try:
            self.message_label.setText("Configuration loaded!")
            self.progress_bar.setValue(100)
            logger.info("Minimal configuration loaded successfully.")
            QTimer.singleShot(1000, self.accept_if_visible) # Changed to accept_if_visible
        except Exception as e:
            logger.error(f"Error in minimal show_success: {e}", exc_info=True)
    
    def show_error(self, error_message: str):
        """Show error state"""
        try:
            self.message_label.setText(f"Error: {error_message}")
            self.cancel_button.setText("Close")
            logger.error(f"Minimal configuration load failed: {error_message}")
        except Exception as e:
            logger.error(f"Error in minimal show_error: {e}", exc_info=True)

    def accept_if_visible(self):
        """Accepts the dialog only if it is still visible."""
        try:
            if self.isVisible():
                logger.debug("MinimalProgressDialog auto-closing after success.")
                self.accept()
        except Exception as e:
            logger.error(f"Error in accept_if_visible: {e}", exc_info=True)

    def closeEvent(self, event):
        """Handle dialog close event for MinimalProgressDialog."""
        try:
            logger.debug("MinimalProgressDialog closeEvent triggered.")
            # Assuming MinimalProgressDialog cancellation is primarily handled by its cancel button
            # which already emits load_cancelled and calls reject.
            # If closed via window X, ensure signal is emitted if appropriate.
            # For simplicity, we assume the cancel button is the primary way to cancel.
            # If an explicit cancel signal is needed on any close, it should be added here.
            # self.load_cancelled.emit() # If needed for all close types
            event.accept()
        except Exception as e:
            logger.error(f"Error in MinimalProgressDialog closeEvent: {e}", exc_info=True)
            event.accept()
