"""
Clean and professional mode selection dialog
"""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                              QLabel, QGraphicsDropShadowEffect)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QRect, QEasingCurve, QPoint
from PySide6.QtGui import QIcon, QColor, QGuiApplication, QPixmap


class ModeButton(QPushButton):
    """Stylized button for mode selection"""
    
    def __init__(self, title: str, description: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.description = description
        
        # Setup button
        self.setFixedSize(300, 150)
        self.setCursor(Qt.PointingHandCursor)
        
        # Create layout for button content
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: white;
        """)
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("""
            font-size: 14px;
            color: #cccccc;
        """)
        layout.addWidget(desc_label)
        
        # Apply styles
        self.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                border: 2px solid #404040;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #3b3b3b;
                border-color: #4a90a4;
            }
            QPushButton:pressed {
                background-color: #1b1b1b;
            }
        """)
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)


class ModeSelectionDialog(QDialog):
    """Professional mode selection dialog"""
    
    mode_selected = Signal(str)
    
    def __init__(self, parent=None, position=None):
        super().__init__(parent)
        self.selected_mode = None
        self.target_position = position  # Position to show at (for seamless transition)
        self.setup_window_icon()  # Set icon before UI setup
        self.setup_ui()
    
    def exec(self):
        """Override exec to ensure window is shown properly"""
        # Ensure window state is normal
        self.setWindowState(Qt.WindowNoState)
        # Show the window
        self.show()
        # Force it to be on top and active
        self.raise_()
        self.activateWindow()
        # Then run the modal event loop
        return super().exec()
        
    def setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle("Select Testing Mode")
        # Set window flags to ensure proper display
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setModal(True)
        
        # Set size and center
        self.setFixedSize(1000, 400)
    
    def setup_window_icon(self):
        """Setup window icon for mode selection dialog"""
        try:
            # Get the application instance
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                # Try to load the icon from logo.jpg
                from pathlib import Path
                logo_path = Path(__file__).parent.parent.parent.parent / "resources" / "logo.jpg"
                
                if logo_path.exists():
                    pixmap = QPixmap(str(logo_path))
                    if not pixmap.isNull():
                        icon = QIcon(pixmap)
                        self.setWindowIcon(icon)
                        # Application icon should already be set by splash screen
        except Exception as e:
            print(f"Could not set mode dialog icon: {e}")
        
        # Ensure window is not minimized
        self.setWindowState(Qt.WindowNoState)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(30)
        
        # Set dialog background
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                border: 1px solid #404040;
                border-radius: 15px;
            }
        """)
        
        # Header
        header = QLabel("Select Testing Mode")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("""
            font-size: 32px;
            font-weight: bold;
            color: white;
            margin-bottom: 20px;
        """)
        main_layout.addWidget(header)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(30)
        
        # Create mode buttons
        offroad_btn = ModeButton(
            "Offroad",
            "Test offroad lighting products\nwith full functional testing"
        )
        offroad_btn.clicked.connect(lambda: self.select_mode("Offroad"))
        
        smt_btn = ModeButton(
            "SMT",
            "Surface mount technology testing\nwith programming capabilities"
        )
        smt_btn.clicked.connect(lambda: self.select_mode("SMT"))
        
        weight_btn = ModeButton(
            "Weight Check",
            "Verify product weight\nagainst specifications"
        )
        weight_btn.clicked.connect(lambda: self.select_mode("WeightChecking"))
        
        # Add buttons
        buttons_layout.addStretch()
        buttons_layout.addWidget(offroad_btn)
        buttons_layout.addWidget(smt_btn)
        buttons_layout.addWidget(weight_btn)
        buttons_layout.addStretch()
        
        main_layout.addLayout(buttons_layout)
        
        # Footer hint
        hint = QLabel("Click a mode to begin")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("""
            font-size: 14px;
            color: #666666;
            margin-top: 20px;
        """)
        main_layout.addWidget(hint)
        
    def select_mode(self, mode: str):
        """Handle mode selection"""
        self.selected_mode = mode
        self.mode_selected.emit(mode)
        self.accept()
        
    def show_at_position(self, pos: QPoint):
        """Show dialog at specific position for seamless transition"""
        self.move(pos)
        self.show()
        # Still do the fade-in animation
        self.setWindowOpacity(0.0)
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(300)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.start()
        
    def showEvent(self, event):
        """Animate dialog appearance"""
        super().showEvent(event)
        
        # If we have a target position, use it
        if self.target_position:
            self.move(self.target_position)
        else:
            # Center on screen
            if self.parent():
                parent_rect = self.parent().geometry()
            else:
                screen = QGuiApplication.primaryScreen()
                if screen:
                    parent_rect = screen.geometry()
                else:
                    # Fallback
                    parent_rect = QRect(0, 0, 1920, 1080)
                    
            x = (parent_rect.width() - self.width()) // 2
            y = (parent_rect.height() - self.height()) // 2
            self.move(x, y)
        
        # Don't do fade-in here if we're using transition manager
        # The transition manager will handle the opacity animation
        if not hasattr(self, '_transition_managed'):
            # Fade in animation
            self.setWindowOpacity(0.0)
            self.animation = QPropertyAnimation(self, b"windowOpacity")
            self.animation.setDuration(300)
            self.animation.setStartValue(0.0)
            self.animation.setEndValue(1.0)
            self.animation.setEasingCurve(QEasingCurve.OutCubic)
            self.animation.start()
        
        # Force window to be active and on top
        self.raise_()
        self.activateWindow()
        self.setFocus()
