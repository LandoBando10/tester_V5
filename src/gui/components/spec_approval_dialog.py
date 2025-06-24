"""
Specification Limit Approval Dialog
Provides secure approval workflow for spec limit changes
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QTableWidget, QTableWidgetItem, QLineEdit,
    QDialogButtonBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import json
from datetime import datetime
from pathlib import Path
import hashlib
from typing import Dict, Optional, Tuple


class LoginDialog(QDialog):
    """Simple login dialog for authentication"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Authentication Required")
        self.setModal(True)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Specification Limit Change Requires Authentication")
        title.setAlignment(Qt.AlignCenter)
        font = title.font()
        font.setPointSize(10)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        
        # Username
        layout.addWidget(QLabel("Username:"))
        self.username_edit = QLineEdit()
        layout.addWidget(self.username_edit)
        
        # Password
        layout.addWidget(QLabel("Password:"))
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_edit)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def get_credentials(self) -> Tuple[str, str]:
        """Return username and password"""
        return self.username_edit.text(), self.password_edit.text()


class SpecApprovalDialog(QDialog):
    """Dialog for reviewing and approving specification limit changes"""
    
    specs_approved = Signal(dict)  # Emits approved spec changes
    
    def __init__(self, current_specs: Dict, proposed_specs: Dict, 
                 measurement_data: Dict, parent=None):
        super().__init__(parent)
        self.current_specs = current_specs
        self.proposed_specs = proposed_specs
        self.measurement_data = measurement_data
        self.username = None
        
        self.setWindowTitle("Approve Specification Limit Changes")
        self.setModal(True)
        self.resize(600, 400)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Review Proposed Specification Limit Changes")
        title.setAlignment(Qt.AlignCenter)
        font = title.font()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        
        # Comparison table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Function/Board", "Current LSL", "Current USL", 
            "Proposed LSL", "Proposed USL"
        ])
        
        # Populate table
        self.populate_comparison_table()
        layout.addWidget(self.table)
        
        # Statistics summary
        stats_label = QLabel(self._generate_statistics_summary())
        stats_label.setWordWrap(True)
        layout.addWidget(stats_label)
        
        # Warning if specs are tightening
        if self._specs_are_tightening():
            warning = QLabel("⚠️ Warning: Proposed limits are tighter than current limits")
            warning.setStyleSheet("QLabel { color: orange; font-weight: bold; }")
            layout.addWidget(warning)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        button_layout.addStretch()
        
        self.approve_btn = QPushButton("Approve Changes")
        self.approve_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        self.approve_btn.clicked.connect(self.approve_changes)
        button_layout.addWidget(self.approve_btn)
        
        layout.addLayout(button_layout)
        
    def populate_comparison_table(self):
        """Fill table with current vs proposed specs"""
        row = 0
        for key, proposed in self.proposed_specs.items():
            current = self.current_specs.get(key, {})
            
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(key))
            
            # Current limits
            self.table.setItem(row, 1, QTableWidgetItem(
                f"{current.get('lsl', 'N/A'):.4f}" if isinstance(current.get('lsl'), (int, float)) else "N/A"
            ))
            self.table.setItem(row, 2, QTableWidgetItem(
                f"{current.get('usl', 'N/A'):.4f}" if isinstance(current.get('usl'), (int, float)) else "N/A"
            ))
            
            # Proposed limits
            self.table.setItem(row, 3, QTableWidgetItem(f"{proposed['lsl']:.4f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{proposed['usl']:.4f}"))
            
            # Highlight changes
            if current:
                if proposed['lsl'] != current.get('lsl'):
                    self.table.item(row, 3).setBackground(Qt.yellow)
                if proposed['usl'] != current.get('usl'):
                    self.table.item(row, 4).setBackground(Qt.yellow)
                    
            row += 1
            
        self.table.resizeColumnsToContents()
        
    def _generate_statistics_summary(self) -> str:
        """Generate summary of measurement statistics"""
        total_measurements = self.measurement_data.get('total_measurements', 0)
        measurement_count = self.measurement_data.get('measurement_count', {})
        
        summary = f"Based on {total_measurements} total measurements:\n"
        for key, count in measurement_count.items():
            summary += f"  • {key}: {count} measurements\n"
            
        return summary
        
    def _specs_are_tightening(self) -> bool:
        """Check if any specs are getting tighter"""
        for key, proposed in self.proposed_specs.items():
            current = self.current_specs.get(key, {})
            if current:
                if (proposed['lsl'] > current.get('lsl', float('-inf')) or 
                    proposed['usl'] < current.get('usl', float('inf'))):
                    return True
        return False
        
    def approve_changes(self):
        """Handle approval with authentication"""
        # Show login dialog
        login_dialog = LoginDialog(self)
        if login_dialog.exec_() == QDialog.Accepted:
            username, password = login_dialog.get_credentials()
            
            # Verify credentials (simplified for example)
            if self.verify_credentials(username, password):
                self.username = username
                self.log_approval()
                self.specs_approved.emit(self.proposed_specs)
                self.accept()
            else:
                QMessageBox.warning(self, "Authentication Failed", 
                                  "Invalid username or password")
        
    def verify_credentials(self, username: str, password: str) -> bool:
        """Verify user credentials using UserManager"""
        try:
            # Import here to avoid circular imports
            from src.auth.user_manager import get_user_manager
            
            user_manager = get_user_manager()
            
            # Authenticate and check permissions
            if user_manager.authenticate(username, password):
                if user_manager.has_permission('approve_specs'):
                    return True
                else:
                    QMessageBox.warning(self, "Insufficient Permissions", 
                                      f"User '{username}' does not have permission to approve spec changes.\n"
                                      f"Role '{user_manager.get_current_role()}' requires 'approve_specs' permission.")
                    user_manager.logout()
                    return False
            
            return False
            
        except Exception as e:
            print(f"Error verifying credentials: {e}")
            return False
        
    def log_approval(self):
        """Log the approval action"""
        try:
            from src.auth.user_manager import get_user_manager
            
            user_manager = get_user_manager()
            
            # Build change details
            changes = []
            for key, proposed in self.proposed_specs.items():
                current = self.current_specs.get(key, {})
                changes.append({
                    "item": key,
                    "old_lsl": current.get('lsl'),
                    "old_usl": current.get('usl'),
                    "new_lsl": proposed['lsl'],
                    "new_usl": proposed['usl']
                })
            
            # Log using user manager for consistent audit trail
            user_manager.log_action("spec_limit_approval", {
                "measurement_count": self.measurement_data.get('total_measurements', 0),
                "changes": changes
            })
            
        except Exception as e:
            print(f"Error logging approval: {e}")
            # Fallback to basic logging
            self._basic_log_approval()
    
    def _basic_log_approval(self):
        """Basic fallback logging if user manager unavailable"""
        try:
            audit_dir = Path("audit_logs")
            audit_dir.mkdir(exist_ok=True)
            
            audit_entry = {
                "timestamp": datetime.now().isoformat(),
                "username": self.username,
                "action": "spec_limit_approval",
                "changes": []
            }
            
            for key, proposed in self.proposed_specs.items():
                current = self.current_specs.get(key, {})
                audit_entry["changes"].append({
                    "item": key,
                    "old_lsl": current.get('lsl'),
                    "old_usl": current.get('usl'),
                    "new_lsl": proposed['lsl'],
                    "new_usl": proposed['usl']
                })
            
            # Append to audit log
            audit_file = audit_dir / f"spec_changes_{datetime.now().strftime('%Y%m')}.json"
            
            if audit_file.exists():
                with open(audit_file, 'r') as f:
                    audit_data = json.load(f)
            else:
                audit_data = []
                
            audit_data.append(audit_entry)
            
            with open(audit_file, 'w') as f:
                json.dump(audit_data, f, indent=2)
                
        except Exception as e:
            print(f"Error in basic logging: {e}")


# Example usage
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    current = {
        "mainbeam_Board_1": {"lsl": 1.8, "usl": 2.3},
        "mainbeam_Board_2": {"lsl": 1.8, "usl": 2.3}
    }
    
    proposed = {
        "mainbeam_Board_1": {"lsl": 1.92, "usl": 2.08},
        "mainbeam_Board_2": {"lsl": 1.91, "usl": 2.09}
    }
    
    measurement_data = {
        "total_measurements": 60,
        "measurement_count": {
            "mainbeam_Board_1": 30,
            "mainbeam_Board_2": 30
        }
    }
    
    dialog = SpecApprovalDialog(current, proposed, measurement_data)
    
    if dialog.exec_() == QDialog.Accepted:
        print("Specs approved!")
    
    sys.exit(0)