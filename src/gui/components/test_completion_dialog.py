# Simple test completion dialog with programming results
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt

class TestCompletionDialog(QDialog):
    def __init__(self, result, sku, mode, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Test Results")
        self.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # Status
        status = "PASSED" if result.passed else "FAILED"
        status_label = QLabel(f"Test {status}")
        status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(status_label)
        
        # Programming results if available
        programming_results = getattr(result, 'programming_results', None)
        if programming_results:
            prog_label = QLabel(f"Programming: {len(programming_results)} boards")
            layout.addWidget(prog_label)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
