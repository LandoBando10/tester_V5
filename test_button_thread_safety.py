#!/usr/bin/env python3
"""Test script to verify SMT button press thread safety fix"""

import sys
import time
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import QObject, Signal, Qt, QThread

class MockArduinoReader(QThread):
    """Simulates Arduino reading thread sending button events"""
    button_event = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.running = False
    
    def run(self):
        """Simulate button press from background thread"""
        self.running = True
        time.sleep(2)  # Wait 2 seconds
        print("MockArduinoReader: Simulating button press from background thread...")
        self.button_event.emit("PRESSED")
        time.sleep(0.5)
        self.button_event.emit("RELEASED")

class ButtonHandler(QObject):
    """Handler that demonstrates thread-safe button handling"""
    button_pressed_signal = Signal()
    
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        # Connect signal with QueuedConnection to ensure main thread execution
        self.button_pressed_signal.connect(self._handle_button_on_main_thread, Qt.QueuedConnection)
    
    def handle_button_event(self, state):
        """Called from Arduino thread - NOT safe for GUI operations"""
        print(f"ButtonHandler.handle_button_event: Received {state} from thread: {QThread.currentThread()}")
        if state == "PRESSED":
            # Emit signal to handle on main thread
            self.button_pressed_signal.emit()
    
    def _handle_button_on_main_thread(self):
        """Called on main thread - SAFE for GUI operations"""
        print(f"ButtonHandler._handle_button_on_main_thread: Running on thread: {QThread.currentThread()}")
        # Safe to update GUI here
        self.parent.status_label.setText("Button pressed - handled safely on main thread!")
        self.parent.status_label.setStyleSheet("color: green; font-weight: bold;")

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SMT Button Thread Safety Test")
        self.setGeometry(100, 100, 400, 200)
        
        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Status label
        self.status_label = QLabel("Waiting for simulated button press...")
        self.status_label.setStyleSheet("font-size: 14px; padding: 10px;")
        layout.addWidget(self.status_label)
        
        # Create button handler
        self.button_handler = ButtonHandler(self)
        
        # Create and start mock Arduino reader
        self.arduino_reader = MockArduinoReader()
        self.arduino_reader.button_event.connect(self.button_handler.handle_button_event)
        
        # Start button
        self.start_btn = QPushButton("Start Test")
        self.start_btn.clicked.connect(self.start_test)
        layout.addWidget(self.start_btn)
        
        # Info label
        info = QLabel("Click 'Start Test' to simulate a button press from Arduino thread.\n"
                     "If the fix works correctly, you'll see a success message.")
        info.setWordWrap(True)
        info.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(info)
    
    def start_test(self):
        """Start the test"""
        self.status_label.setText("Test started - simulating button press in 2 seconds...")
        self.status_label.setStyleSheet("color: blue;")
        self.start_btn.setEnabled(False)
        
        # Start the mock Arduino thread
        self.arduino_reader.start()
        
        # Re-enable button after test
        QThread.sleep(3)
        self.start_btn.setEnabled(True)

def main():
    print("=== SMT Button Thread Safety Test ===")
    print(f"Main thread: {QThread.currentThread()}")
    
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    
    print("\nThis test simulates the button press coming from a background thread")
    print("and demonstrates the thread-safe handling using Qt signals.\n")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
