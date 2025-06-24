#!/usr/bin/env python3
"""
Test script to verify Enhanced SPC Widget integration
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
from src.spc.enhanced_spc_widget import EnhancedSPCWidget

logging.basicConfig(level=logging.INFO)

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SPC Integration Test")
        self.setGeometry(100, 100, 1200, 900)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Add button to show SPC widget
        self.show_spc_btn = QPushButton("Show SPC Control")
        self.show_spc_btn.clicked.connect(self.show_spc_control)
        layout.addWidget(self.show_spc_btn)
        
        # Add test data button
        self.add_data_btn = QPushButton("Add Test Data")
        self.add_data_btn.clicked.connect(self.add_test_data)
        layout.addWidget(self.add_data_btn)
        
        # SPC widget (initially hidden)
        self.spc_widget = None
        
    def show_spc_control(self):
        """Show the SPC control widget"""
        if not self.spc_widget:
            self.spc_widget = EnhancedSPCWidget()
            # Add some test SKUs
            self.spc_widget.update_sku_list(["DD5001", "DD5002", "DD5003", "TEST_SKU"])
            
            # Connect signals
            self.spc_widget.mode_changed.connect(self.on_mode_changed)
            self.spc_widget.spec_approval_requested.connect(self.on_spec_approval)
            
        self.spc_widget.show()
        
    def add_test_data(self):
        """Add some test data to the SPC widget"""
        if not self.spc_widget:
            print("Please show SPC widget first")
            return
            
        # Simulate test results
        test_results = {
            'sku': 'DD5001',
            'passed': True,
            'measurements': {
                'mainbeam_readings': {
                    'board_results': {
                        'Board 1': {
                            'current': 2.05,
                            'voltage': 13.2
                        },
                        'Board 2': {
                            'current': 2.03,
                            'voltage': 13.19
                        }
                    }
                },
                'backlight_left_readings': {
                    'board_results': {
                        'Board 1': {
                            'current': 0.52,
                            'voltage': 13.2
                        },
                        'Board 2': {
                            'current': 0.51,
                            'voltage': 13.19
                        }
                    }
                }
            },
            'metadata': {
                'spc': {
                    'data_collected': True
                }
            }
        }
        
        self.spc_widget.add_test_results('DD5001', test_results)
        print("Test data added to SPC widget")
        
    def on_mode_changed(self, sku, config):
        """Handle mode change"""
        print(f"Mode changed for {sku}: {config}")
        
    def on_spec_approval(self, sku):
        """Handle spec approval request"""
        print(f"Spec approval requested for {sku}")

def main():
    app = QApplication(sys.argv)
    
    # Apply dark theme
    app.setStyleSheet("""
        QWidget {
            background-color: #2b2b2b;
            color: white;
        }
        QPushButton {
            background-color: #4a90a4;
            border: none;
            padding: 8px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #5ba3b8;
        }
    """)
    
    window = TestWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()