"""
Splash screen with video playback for professional startup experience
"""
import sys
from pathlib import Path
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication, QGraphicsDropShadowEffect, QProgressBar
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QUrl, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QGuiApplication, QIcon, QLinearGradient, QPalette, QBrush
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from .transition_manager import transition_manager
from .preloader import PreloaderThread, PreloadedComponents


class SplashScreen(QWidget):
    """Professional splash screen with video or fallback animation"""
    
    finished = Signal()
    preloaded_components_signal = Signal(object)  # Emits preloaded components
    ready_for_transition = Signal()  # Emits when ready to transition
    
    # Match mode selector dialog size
    SPLASH_WIDTH = 1000
    SPLASH_HEIGHT = 400
    
    def __init__(self, video_path: str = None, duration_ms: int = 3000):
        super().__init__()
        self.video_path = video_path
        self.duration_ms = duration_ms
        self.preloaded_components = None
        self.preloader_thread = None
        self.is_closing = False  # Prevent multiple close attempts
        self.video_ended = False  # Track if video has ended
        self.static_content_widget = None  # For seamless transition
        self.preload_ready = False  # Track if preloading is done
        self.video_ready = False  # Track if video/timer is done
        self.setup_window_icon()  # Set icon before UI setup
        self.setup_ui()
        self.start_preloading()
        
    def setup_ui(self):
        """Setup the splash screen UI"""
        # Window flags for borderless window
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
    
    def setup_window_icon(self):
        """Setup window icon for splash screen"""
        try:
            # Get the application instance
            app = QApplication.instance()
            if app:
                # Try to load the icon from logo.jpg
                logo_path = Path(__file__).parent.parent.parent.parent / "resources" / "logo.jpg"
                
                if logo_path.exists():
                    pixmap = QPixmap(str(logo_path))
                    if not pixmap.isNull():
                        icon = QIcon(pixmap)
                        self.setWindowIcon(icon)
                        app.setWindowIcon(icon)
                        
                        # For Windows, set app ID
                        if sys.platform == 'win32':
                            try:
                                import ctypes
                                myappid = 'diodedynamics.tester.v5.production'
                                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
                            except:
                                pass
        except Exception as e:
            print(f"Could not set splash screen icon: {e}")
        
        # Set size to match mode selector
        self.setFixedSize(self.SPLASH_WIDTH, self.SPLASH_HEIGHT)
        
        # Set gradient background with rounded corners for professional look
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #1a1a1a, stop: 0.5 #2d2d2d, stop: 1 #1a1a1a);
                border: 1px solid #404040;
                border-radius: 15px;
            }
        """)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Try to setup video player, fallback to static image
        if self.video_path and Path(self.video_path).exists():
            self.setup_video_player(layout)
        else:
            self.setup_fallback_splash(layout)
            
    def setup_video_player(self, layout):
        """Setup video player for splash video with optimizations and safety timeout"""
        try:
            # Create container for video with rounded corners
            video_container = QWidget()
            video_container.setStyleSheet("""
                QWidget {
                    background-color: #000000;
                    border-radius: 15px;
                }
            """)
            container_layout = QVBoxLayout(video_container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            
            # Create media player and video widget
            self.media_player = QMediaPlayer()
            self.video_widget = QVideoWidget()
            
            # Configure video widget with matching background
            self.video_widget.setAspectRatioMode(Qt.KeepAspectRatio)
            self.video_widget.setStyleSheet("background-color: #1a1a1a;")  # Match splash background
            container_layout.addWidget(self.video_widget)
            
            layout.addWidget(video_container)
            
            # Set video output and source
            self.media_player.setVideoOutput(self.video_widget)
            
            # Connect signals BEFORE setting source to catch early errors
            self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)
            self.media_player.errorOccurred.connect(self.on_media_error)
            self.media_player.positionChanged.connect(self.on_position_changed)
            
            # Add safety timeout to prevent hanging
            self.video_timeout = QTimer()
            self.video_timeout.setSingleShot(True)
            self.video_timeout.timeout.connect(self.on_video_timeout)
            self.video_timeout.start(5000)  # 5 second timeout
            
            # Set source and try to play
            self.media_player.setSource(QUrl.fromLocalFile(self.video_path))
            self.media_player.play()
            
            # Also set a timer to prepare transition after duration_ms in case video doesn't report end
            QTimer.singleShot(self.duration_ms, self.on_video_ready)
            
        except Exception as e:
            print(f"Error setting up video player: {e}")
            self.setup_fallback_splash(layout)
            
    def setup_fallback_splash(self, layout):
        """Setup professional fallback splash screen with enhanced visuals"""
        # Create container for vertical centering
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setAlignment(Qt.AlignCenter)
        container_layout.setSpacing(20)
        
        # Add top spacer
        container_layout.addStretch(2)
        
        # Create logo container with shadow effect
        logo_container = QWidget()
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create centered label for logo
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        
        # Add drop shadow effect to logo
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(Qt.black)
        shadow.setOffset(0, 5)
        self.logo_label.setGraphicsEffect(shadow)
        
        # Try to load company logo
        logo_paths = [
            Path("resources/logo.jpg"),
            Path("resources/images/diode_dynamics_logo.png")
        ]
        
        logo_loaded = False
        for logo_path in logo_paths:
            if logo_path.exists():
                pixmap = QPixmap(str(logo_path))
                # Scale logo to fit nicely in the window
                scaled_pixmap = pixmap.scaled(
                    int(self.SPLASH_WIDTH * 0.4), 
                    int(self.SPLASH_HEIGHT * 0.35), 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                self.logo_label.setPixmap(scaled_pixmap)
                logo_loaded = True
                break
        
        if not logo_loaded:
            # Fallback text
            self.logo_label.setText("DD")
            self.logo_label.setStyleSheet("""
                color: white;
                font-size: 72px;
                font-weight: bold;
                font-family: Arial;
            """)
        
        logo_layout.addWidget(self.logo_label)
        container_layout.addWidget(logo_container)
        
        # Add company name
        company_name = QLabel("DIODE DYNAMICS")
        company_name.setAlignment(Qt.AlignCenter)
        company_name.setStyleSheet("""
            color: #ffffff;
            font-size: 32px;
            font-weight: bold;
            font-family: 'Segoe UI', Arial, sans-serif;
            letter-spacing: 3px;
        """)
        container_layout.addWidget(company_name)
        
        # Add subtitle
        subtitle = QLabel("Production Test System")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("""
            color: #cccccc;
            font-size: 18px;
            font-family: 'Segoe UI', Arial, sans-serif;
            margin-top: 5px;
        """)
        container_layout.addWidget(subtitle)
        
        # Add spacing
        container_layout.addSpacing(30)
        
        # Add progress bar for loading indication
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(4)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #333333;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #4a90a4, stop: 1 #67b7d1);
                border-radius: 2px;
            }
        """)
        self.progress_bar.setMaximumWidth(300)
        
        # Center the progress bar
        progress_container = QWidget()
        progress_layout = QVBoxLayout(progress_container)
        progress_layout.setAlignment(Qt.AlignCenter)
        progress_layout.addWidget(self.progress_bar)
        container_layout.addWidget(progress_container)
        
        # Add loading text
        self.loading_label = QLabel("Initializing...")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet("""
            color: #888888;
            font-size: 14px;
            font-family: 'Segoe UI', Arial, sans-serif;
            margin-top: 10px;
        """)
        container_layout.addWidget(self.loading_label)
        
        # Add bottom spacer
        container_layout.addStretch(3)
        
        # Add version info at bottom
        version_label = QLabel("V1")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("""
            color: #666666;
            font-size: 12px;
            font-family: 'Segoe UI', Arial, sans-serif;
        """)
        container_layout.addWidget(version_label)
        
        layout.addWidget(container)
        
        # Store reference to static content for transitions
        self.static_content_widget = layout.parentWidget()
        
        # Start progress animation
        self.start_progress_animation()
        
        # Animate logo with subtle scale effect
        self.animate_logo()
        
        # Start timer for fallback duration
        fallback_duration = min(self.duration_ms, 3000)
        QTimer.singleShot(fallback_duration, self.on_video_ready)
        
    def on_media_status_changed(self, status):
        """Handle media status changes"""
        print(f"Media status changed: {status}")
        if status == QMediaPlayer.LoadedMedia:
            # Video loaded successfully, stop timeout
            if hasattr(self, 'video_timeout'):
                self.video_timeout.stop()
            print("Video loaded successfully")
        elif status == QMediaPlayer.EndOfMedia:
            print("Video ended, preparing transition...")
            self.video_ended = True
            self.on_video_ready()
            
    def on_media_error(self, error):
        """Handle media errors by falling back"""
        print(f"Media error occurred: {error}")
        if hasattr(self, 'video_timeout'):
            self.video_timeout.stop()
        self.fallback_to_static()
    
    def on_video_timeout(self):
        """Handle video loading timeout"""
        print("Video loading timed out, falling back to static splash")
        self.fallback_to_static()
    
    def fallback_to_static(self):
        """Fallback to static splash screen"""
        try:
            # Stop and cleanup media player
            if hasattr(self, 'media_player'):
                self.media_player.stop()
                self.media_player = None
            
            # Clear current layout
            layout = self.layout()
            for i in reversed(range(layout.count())): 
                child = layout.itemAt(i).widget()
                if child:
                    child.setParent(None)
            
            # Setup fallback splash
            self.setup_fallback_splash(layout)
            
        except Exception as e:
            print(f"Error during fallback: {e}")
            # Ultimate fallback - just close splash
            QTimer.singleShot(1000, self.close_splash)
        
    def show_centered(self):
        """Show splash screen centered on screen (not fullscreen)"""
        # Get screen geometry
        screen = QGuiApplication.primaryScreen()
        if screen:
            screen_rect = screen.geometry()
            # Center the splash screen
            x = (screen_rect.width() - self.width()) // 2
            y = (screen_rect.height() - self.height()) // 2
            self.move(x, y)
        
        # Show with fade-in animation
        self.setWindowOpacity(0.0)
        self.show()
        
        # Fade in animation
        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(300)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.start()
        
    def show_fullscreen(self):
        """Compatibility method - now shows centered instead"""
        self.show_centered()
        
    def start_preloading(self):
        """Start background preloading of application components"""
        self.preloader_thread = PreloaderThread()
        self.preloader_thread.progress.connect(self.on_preload_progress)
        self.preloader_thread.preload_complete.connect(self.on_preload_complete)
        self.preloader_thread.start()
    
    def on_preload_progress(self, message: str, percentage: int):
        """Handle preloading progress updates"""
        print(f"Preloading: {message} ({percentage}%)")
        # Update progress bar if in fallback mode
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(percentage)
        if hasattr(self, 'loading_label'):
            self.loading_label.setText(message)
    
    def on_preload_complete(self, components: PreloadedComponents):
        """Handle completion of preloading"""
        self.preloaded_components = components
        self.preloaded_components_signal.emit(components)
        print("Component preloading completed")
        
        # Mark preload as ready and check if we can transition
        self.preload_ready = True
        self.check_ready_for_transition()
    
    def on_video_ready(self):
        """Called when video ends or timer expires"""
        self.video_ready = True
        self.check_ready_for_transition()
    
    def check_ready_for_transition(self):
        """Check if both video and preloading are done"""
        if self.preload_ready and self.video_ready:
            self.prepare_transition()
    
    def on_position_changed(self, position):
        """Handle video position changes for optimization"""
        # Ensure minimum splash duration even if video is short
    
    def get_preloaded_components(self):
        """Get the preloaded components"""
        return self.preloaded_components
    
    def prepare_transition(self):
        """Prepare for seamless transition to next window"""
        if self.is_closing:
            return
            
        self.is_closing = True
        
        # If video is playing, create a snapshot of the last frame
        if hasattr(self, 'video_widget') and self.video_ended:
            # Capture the last frame of the video
            self.last_frame = transition_manager.capture_frame(self.video_widget)
        
        # Signal that we're ready for transition
        self.ready_for_transition.emit()
    
    def start_progress_animation(self):
        """Start animated progress bar"""
        if hasattr(self, 'progress_bar'):
            # Create smooth progress animation
            self.progress_animation = QPropertyAnimation(self.progress_bar, b"value")
            self.progress_animation.setDuration(self.duration_ms - 500)  # Leave some time at 100%
            self.progress_animation.setStartValue(0)
            self.progress_animation.setEndValue(100)
            self.progress_animation.setEasingCurve(QEasingCurve.InOutQuad)
            self.progress_animation.start()
    
    def animate_logo(self):
        """Animate logo with subtle fade effect"""
        if hasattr(self, 'logo_label'):
            # Create fade-in animation for logo
            self.logo_label.setWindowOpacity(0.0)
            self.logo_fade = QPropertyAnimation(self.logo_label, b"windowOpacity")
            self.logo_fade.setDuration(800)
            self.logo_fade.setStartValue(0.0)
            self.logo_fade.setEndValue(1.0)
            self.logo_fade.setEasingCurve(QEasingCurve.InOutQuad)
            self.logo_fade.start()
    
    def close_splash(self):
        """Close splash screen with fade out for seamless transition"""
        # Prevent multiple close attempts
        if self.is_closing:
            print("Already closing, ignoring duplicate close request")
            return
            
        self.is_closing = True
        print("Closing splash screen...")
        
        # Clean up video player
        if hasattr(self, 'media_player') and self.media_player:
            try:
                self.media_player.stop()
                self.media_player = None
            except:
                pass
        
        # Stop any running timers
        if hasattr(self, 'video_timeout'):
            self.video_timeout.stop()
        
        # Clean up preloader thread
        if self.preloader_thread and self.preloader_thread.isRunning():
            self.preloader_thread.quit()
            self.preloader_thread.wait(1000)  # Wait up to 1 second
        
        # Fade out animation for seamless transition
        self.fade_out = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out.setDuration(200)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.finished.connect(lambda: (
            print("Fade out complete, closing and emitting finished signal"),
            self.close(), 
            self.finished.emit()
        ))
        self.fade_out.start()