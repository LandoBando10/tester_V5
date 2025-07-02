"""
Unified splash screen with integrated mode selection
Provides a seamless startup experience
"""
import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                              QApplication, QGraphicsDropShadowEffect, QProgressBar,
                              QPushButton, QStackedWidget, QGraphicsOpacityEffect)
from PySide6.QtCore import (Qt, QTimer, Signal, QThread, QUrl, QPropertyAnimation, 
                           QEasingCurve, QParallelAnimationGroup, QPoint)
from PySide6.QtGui import QPixmap, QGuiApplication, QIcon, QColor, QFont
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from .preloader import PreloaderThread, PreloadedComponents


class ModeButton(QPushButton):
    """Clean text-only button used on the mode-selection page."""

    def __init__(self, title: str, description: str, parent=None):
        super().__init__(parent)
        self.setObjectName("ModeButton")  # For QSS styling
        self.setFixedSize(280, 140)  # Reduced width to prevent clipping
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(24, 18, 24, 18)
        vbox.setSpacing(8)

        # Title
        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_font = title_lbl.font()
        title_font.setPointSize(18)
        title_font.setWeight(QFont.DemiBold)
        title_lbl.setFont(title_font)
        title_lbl.setStyleSheet("color: #FFFFFF;")
        vbox.addWidget(title_lbl)

        # Description
        desc_lbl = QLabel(description)
        desc_lbl.setAlignment(Qt.AlignCenter)
        desc_lbl.setWordWrap(True)
        desc_font = desc_lbl.font()
        desc_font.setPointSize(11)
        desc_lbl.setFont(desc_font)
        desc_lbl.setStyleSheet("color: #A0A0A0;")
        vbox.addWidget(desc_lbl)

        # Apply button styling directly to ensure hover works
        self.setStyleSheet("""
            QPushButton#ModeButton {
                background: #212121;
                border: 2px solid #2E2E2E;
                border-radius: 14px;
            }
            QPushButton#ModeButton:hover {
                border: 2px solid #4a90a4;
                background: #2A2A2A;
            }
            QPushButton#ModeButton:pressed {
                background: #1C1C1C;
                border: 2px solid #4a90a4;
            }
        """)
        
        # Opacity effect for staggered fade-in
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0)
        self.setGraphicsEffect(self._opacity)

    def fade_in(self, delay_ms: int):
        """Called by parent to fade the button in"""
        QTimer.singleShot(delay_ms, self._do_fade)

    def _do_fade(self):
        anim = QPropertyAnimation(self._opacity, b"opacity", self)
        anim.setDuration(220)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.setEasingCurve(QEasingCurve.InOutQuad)
        anim.start(QPropertyAnimation.DeleteWhenStopped)


class UnifiedSplashScreen(QWidget):
    """Professional splash screen with integrated mode selection"""
    
    finished = Signal()
    mode_selected = Signal(str)
    preloaded_components_signal = Signal(object)
    
    WINDOW_WIDTH = 1000
    WINDOW_HEIGHT = 600
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.setObjectName("UnifiedSplashScreen")  # For QSS
        
        self.preloaded_components = None
        self.preloader_thread = None
        self.is_closing = False
        self.selected_mode = None
        self.preload_complete = False
        self.mode_buttons = []
        
        # Load stylesheet
        self.load_stylesheet()
        
        # Start preloading immediately before UI setup
        self.start_preloading()
        self.setup_window_icon()
        self.setup_ui()
        
    def load_stylesheet(self):
        """Load the centralized QSS stylesheet"""
        qss_path = Path(__file__).parent.parent.parent.parent / "resources" / "splash.qss"
        if qss_path.exists():
            with open(qss_path, 'r') as f:
                self.setStyleSheet(f.read())
        else:
            self.logger.warning(f"Stylesheet not found: {qss_path}")
        
    def setup_window_icon(self):
        """Setup window icon"""
        try:
            app = QApplication.instance()
            if app:
                logo_path = Path(__file__).parent.parent.parent.parent / "resources" / "logo.jpg"
                if logo_path.exists():
                    pixmap = QPixmap(str(logo_path))
                    if not pixmap.isNull():
                        icon = QIcon(pixmap)
                        self.setWindowIcon(icon)
                        app.setWindowIcon(icon)
                        
                        if sys.platform == 'win32':
                            try:
                                import ctypes
                                myappid = 'diodedynamics.tester.v5.production'
                                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
                            except:
                                pass
        except Exception as e:
            self.logger.error(f"Could not set window icon: {e}")
    
    def setup_ui(self):
        """Setup the unified UI"""
        # Window setup
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setFixedSize(self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
        
        # Add window shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(10)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create stacked widget for different phases
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)
        
        # Phase 1: Loading screen
        self.loading_widget = self.create_loading_phase()
        self.stacked_widget.addWidget(self.loading_widget)
        
        # Phase 2: Mode selection
        self.mode_widget = self.create_mode_selection_phase()
        self.stacked_widget.addWidget(self.mode_widget)
        
        # Start with loading phase
        self.stacked_widget.setCurrentWidget(self.loading_widget)
    
    def create_loading_phase(self):
        """Create the initial loading screen"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)
        
        # Add spacer
        layout.addStretch(2)
        
        # Logo
        logo_container = QWidget()
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        
        # Load logo
        logo_path = Path(__file__).parent.parent.parent.parent / "resources" / "logo.jpg"
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            scaled_pixmap = pixmap.scaled(
                int(self.WINDOW_WIDTH * 0.25), 
                int(self.WINDOW_HEIGHT * 0.20), 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.logo_label.setPixmap(scaled_pixmap)
        
        logo_layout.addWidget(self.logo_label)
        layout.addWidget(logo_container)
        
        # Company name
        company_name = QLabel("DIODE DYNAMICS")
        company_name.setObjectName("CompanyLabel")
        company_name.setAlignment(Qt.AlignCenter)
        layout.addWidget(company_name)
        
        # Subtitle
        subtitle = QLabel("Production Test System")
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        
        # Spacing
        layout.addSpacing(40)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(6)
        self.progress_bar.setMaximumWidth(450)
        
        # Center progress bar
        progress_container = QWidget()
        progress_layout = QHBoxLayout(progress_container)
        progress_layout.setAlignment(Qt.AlignCenter)
        progress_layout.addWidget(self.progress_bar)
        layout.addWidget(progress_container)
        
        # Loading text
        self.loading_label = QLabel("Initializing system...")
        self.loading_label.setObjectName("LoadingLabel")
        self.loading_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.loading_label)
        
        # Bottom spacer
        layout.addStretch(3)
        
        # Version
        version_label = QLabel("Version 5.0 | Build 2025.1")
        version_label.setObjectName("VersionLabel")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        
        return widget
    
    def create_mode_selection_phase(self):
        """Create the mode selection screen"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)
        
        # Header
        header = QLabel("Select Testing Mode")
        header.setObjectName("ModeHeader")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # Subtitle
        subtitle = QLabel("Choose the appropriate testing mode for your workflow")
        subtitle.setObjectName("ModeSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        
        # Add spacing
        layout.addSpacing(20)
        
        # Mode buttons container
        buttons_container = QWidget()
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setSpacing(25)  # Reduced spacing to ensure all buttons fit
        buttons_layout.setAlignment(Qt.AlignCenter)
        
        # Create mode buttons
        modes = [
            ("Offroad", "Off-Road Test", "Comprehensive tests for off-road lighting"),
            ("SMT", "SMT Test", "Surface-mount board validation"),
            ("Weight Check", "Weight Check", "Product mass verification")
        ]
        
        for mode_key, title, description in modes:
            btn = ModeButton(title, description)
            btn.clicked.connect(lambda checked, m=mode_key: self.on_mode_selected(m))
            buttons_layout.addWidget(btn)
            self.mode_buttons.append(btn)
        
        layout.addWidget(buttons_container)
        
        # Add bottom spacing
        layout.addStretch()
        
        # Exit button
        exit_btn = QPushButton("Exit")
        exit_btn.setObjectName("ExitButton")
        exit_btn.setFixedSize(100, 40)
        exit_btn.clicked.connect(self.close)
        
        exit_container = QWidget()
        exit_layout = QHBoxLayout(exit_container)
        exit_layout.setAlignment(Qt.AlignCenter)
        exit_layout.addWidget(exit_btn)
        layout.addWidget(exit_container)
        
        return widget
    
    def start_preloading(self):
        """Start background preloading"""
        self.preloader_thread = PreloaderThread()
        self.preloader_thread.progress.connect(self.on_preload_progress)
        self.preloader_thread.preload_complete.connect(self.on_preload_complete)
        self.preloader_thread.start()
        
    def on_preload_progress(self, message: str, percentage: int):
        """Handle preloading progress"""
        self.loading_label.setText(message)
        if percentage > 90:
            percentage = 90  # Keep some progress for transition
        self.progress_bar.setValue(percentage)
    
    def on_preload_complete(self, components: PreloadedComponents):
        """Handle preloading completion"""
        self.logger.debug("Preload complete called")
        self.preloaded_components = components
        self.preloaded_components_signal.emit(components)
        self.preload_complete = True
        
        # Complete progress bar
        self.progress_bar.setValue(100)
        self.loading_label.setText("Ready!")
        
        # Transition to mode selection immediately
        self.logger.debug("Starting transition timer")
        QTimer.singleShot(100, self.transition_to_mode_selection)
    
    def transition_to_mode_selection(self):
        """Animate transition from loading to mode selection"""
        self.logger.debug("Transitioning to mode selection")
        
        # Ensure window is still visible and active
        self.raise_()
        self.activateWindow()
        self.setWindowState(Qt.WindowActive)
        
        # Simply switch to mode selection widget
        self.stacked_widget.setCurrentWidget(self.mode_widget)
        
        # Animate buttons appearing
        self.animate_mode_buttons()
    
    def animate_mode_buttons(self):
        """Animate mode buttons appearing with stagger"""
        for i, btn in enumerate(self.mode_buttons):
            btn.show()
            btn.fade_in(i * 120)  # 120ms stagger
    
    def on_mode_selected(self, mode: str):
        """Handle mode selection"""
        self.selected_mode = mode
        self.mode_selected.emit(mode)
        
        # Brief fade out before closing
        self.fade_out = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out.setDuration(300)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.finished.connect(self.close)
        self.fade_out.start()
    
    def show_centered(self):
        """Show window centered on screen"""
        self.logger.debug("Showing unified splash screen...")
        
        # Ensure window state is normal before showing
        self.setWindowState(Qt.WindowNoState)
        
        screen = QGuiApplication.primaryScreen()
        if screen:
            screen_rect = screen.geometry()
            x = (screen_rect.width() - self.width()) // 2
            y = (screen_rect.height() - self.height()) // 2
            self.move(x, y)
            self.logger.debug(f"Positioned at {x}, {y}")
        
        # Show window with proper state
        self.setWindowOpacity(1.0)  # Start fully visible
        self.show()
        self.raise_()
        self.activateWindow()
        
        # Force window to stay normal (not minimized)
        self.setWindowState(Qt.WindowActive)
        
        # Process events to ensure window is shown
        QApplication.processEvents()
        
        # Start progress animation now that UI is ready
        if hasattr(self, 'progress_bar'):
            self.progress_animation = QPropertyAnimation(self.progress_bar, b"value")
            self.progress_animation.setDuration(2500)  # Slightly faster
            self.progress_animation.setStartValue(0)
            self.progress_animation.setEndValue(90)
            self.progress_animation.setEasingCurve(QEasingCurve.InOutQuad)
            self.progress_animation.start()
        
        self.logger.debug(f"Window shown, visible: {self.isVisible()}, state: {self.windowState()}")
    
    def get_preloaded_components(self):
        """Get preloaded components"""
        return self.preloaded_components
    
    def close(self):
        """Clean close"""
        if self.is_closing:
            return
        
        self.is_closing = True
        
        # Cleanup
        if self.preloader_thread and self.preloader_thread.isRunning():
            self.preloader_thread.quit()
            self.preloader_thread.wait(1000)
        
        self.finished.emit()
        super().close()