# gui/components/log_viewer_dialog.py
import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTextEdit, QPushButton, 
                               QHBoxLayout, QLabel, QCheckBox, QLineEdit,
                               QMessageBox)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QTextCursor
from pathlib import Path
import os

logger = logging.getLogger(__name__)

class LogViewerDialog(QDialog):
    """Dialog for viewing log files with auto-refresh capability"""
    
    def __init__(self, log_file_path: str, title: str = "Log Viewer", parent=None):
        super().__init__(parent)
        self.log_file_path = Path(log_file_path)
        self.setWindowTitle(title)
        self.setModal(False)  # Non-modal so user can interact with main window
        self.resize(900, 600)
        
        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_log)
        
        self.last_position = 0
        self.file_size = 0
        
        self.setup_ui()
        self.apply_dark_style()
        self.load_log()
        
    def setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout(self)
        
        # Header with file info
        header_layout = QHBoxLayout()
        
        self.file_label = QLabel(f"File: {self.log_file_path.name}")
        self.file_label.setFont(QFont("Arial", 10))
        header_layout.addWidget(self.file_label)
        
        header_layout.addStretch()
        
        # Auto-refresh checkbox
        self.auto_refresh_cb = QCheckBox("Auto-refresh")
        self.auto_refresh_cb.stateChanged.connect(self.toggle_auto_refresh)
        header_layout.addWidget(self.auto_refresh_cb)
        
        layout.addLayout(header_layout)
        
        # Search bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter text to search...")
        self.search_input.textChanged.connect(self.search_log)
        search_layout.addWidget(self.search_input)
        
        layout.addLayout(search_layout)
        
        # Log text display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_display)
        
        # Status bar
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #888888;")
        layout.addWidget(self.status_label)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_log)
        button_layout.addWidget(refresh_btn)
        
        # Clear button (only for critical errors log)
        if "critical" in self.log_file_path.name.lower():
            clear_btn = QPushButton("Clear Log")
            clear_btn.clicked.connect(self.clear_log)
            button_layout.addWidget(clear_btn)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
    def apply_dark_style(self):
        """Apply dark theme styling"""
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: white;
            }
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #404040;
                selection-background-color: #264f78;
            }
            QLineEdit {
                background-color: #3c3c3c;
                color: white;
                border: 1px solid #404040;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #404040;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #353535;
            }
            QCheckBox {
                color: white;
            }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #3c3c3c;
                border: 1px solid #404040;
            }
            QCheckBox::indicator:checked {
                background-color: #4a90a4;
                border: 1px solid #4a90a4;
            }
        """)
        
    def load_log(self):
        """Load the log file contents"""
        try:
            if not self.log_file_path.exists():
                self.log_display.setText(f"Log file not found: {self.log_file_path}")
                self.status_label.setText("File not found")
                return
                
            # Get file size
            self.file_size = os.path.getsize(self.log_file_path)
            
            # Read file
            with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            self.log_display.setText(content)
            
            # Move cursor to end
            cursor = self.log_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.log_display.setTextCursor(cursor)
            
            # Update status
            line_count = content.count('\n') + 1
            self.status_label.setText(f"Loaded {line_count:,} lines ({self.file_size:,} bytes)")
            
        except Exception as e:
            logger.error(f"Error loading log file: {e}")
            self.log_display.setText(f"Error loading log file: {str(e)}")
            self.status_label.setText("Error loading file")
            
    def refresh_log(self):
        """Refresh the log display with new content"""
        try:
            if not self.log_file_path.exists():
                return
                
            # Check if file has changed
            current_size = os.path.getsize(self.log_file_path)
            if current_size == self.file_size:
                return  # No changes
                
            # Store current position
            scrollbar = self.log_display.verticalScrollBar()
            was_at_bottom = scrollbar.value() == scrollbar.maximum()
            
            # Read new content
            with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                if current_size > self.file_size:
                    # File grew - read only new content
                    f.seek(self.file_size)
                    new_content = f.read()
                    self.log_display.append(new_content)
                else:
                    # File was truncated - reload entire file
                    content = f.read()
                    self.log_display.setText(content)
                    
            self.file_size = current_size
            
            # Auto-scroll to bottom if we were at bottom
            if was_at_bottom:
                cursor = self.log_display.textCursor()
                cursor.movePosition(QTextCursor.End)
                self.log_display.setTextCursor(cursor)
                
            # Update status
            line_count = self.log_display.toPlainText().count('\n') + 1
            self.status_label.setText(f"Refreshed - {line_count:,} lines ({self.file_size:,} bytes)")
            
        except Exception as e:
            logger.error(f"Error refreshing log: {e}")
            
    def toggle_auto_refresh(self, state):
        """Toggle auto-refresh functionality"""
        if state == Qt.Checked:
            self.refresh_timer.start(1000)  # Refresh every second
            self.status_label.setText("Auto-refresh enabled")
        else:
            self.refresh_timer.stop()
            self.status_label.setText("Auto-refresh disabled")
            
    def search_log(self, text):
        """Search for text in the log"""
        if not text:
            # Clear any existing highlights
            cursor = self.log_display.textCursor()
            cursor.select(QTextCursor.Document)
            cursor.setCharFormat(self.log_display.currentCharFormat())
            cursor.clearSelection()
            self.log_display.setTextCursor(cursor)
            return
            
        # Find and highlight all occurrences
        cursor = self.log_display.textCursor()
        cursor.beginEditBlock()
        
        # Clear previous highlights
        cursor.movePosition(QTextCursor.Start)
        cursor.select(QTextCursor.Document)
        cursor.setCharFormat(self.log_display.currentCharFormat())
        
        # Search and highlight
        cursor.movePosition(QTextCursor.Start)
        found_count = 0
        
        while True:
            cursor = self.log_display.document().find(text, cursor)
            if cursor.isNull():
                break
                
            found_count += 1
            # Highlight found text
            format = cursor.charFormat()
            format.setBackground(Qt.yellow)
            format.setForeground(Qt.black)
            cursor.setCharFormat(format)
            
        cursor.endEditBlock()
        
        if found_count > 0:
            self.status_label.setText(f"Found {found_count} occurrence(s)")
            # Move to first occurrence
            first_cursor = self.log_display.document().find(text)
            self.log_display.setTextCursor(first_cursor)
        else:
            self.status_label.setText("No matches found")
            
    def clear_log(self):
        """Clear the log file (only for critical errors)"""
        reply = QMessageBox.question(self, "Clear Log", 
                                   "Are you sure you want to clear this log file?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                # Truncate the file
                with open(self.log_file_path, 'w') as f:
                    f.write("")
                    
                self.log_display.clear()
                self.file_size = 0
                self.status_label.setText("Log cleared")
                logger.info(f"Cleared log file: {self.log_file_path}")
                
            except Exception as e:
                logger.error(f"Error clearing log: {e}")
                QMessageBox.critical(self, "Error", f"Could not clear log file: {e}")
                
    def closeEvent(self, event):
        """Handle dialog close event"""
        # Stop auto-refresh timer
        self.refresh_timer.stop()
        event.accept()