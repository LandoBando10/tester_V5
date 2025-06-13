"""
Splash screen with video playback for professional startup experience
"""
import sys
from pathlib import Path
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QUrl, QPropertyAnimation
from PySide6.QtGui import QPixmap, QPainter, QBrush, QColor, QGuiApplication
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget


class PreloaderThread(QThread):
    """Background thread to preload application components"""
    
    preload_complete = Signal(object)  # Emits the preloaded MainWindow
    
    def __init__(self):
        super().__init__()
        self.main_window = None
    
    def run(self):
        """Preload imports only - widget creation must happen in main thread"""
        try:
            # Import heavy modules to warm up the import cache
            print("Preloading imports...")
            from src.gui.main_window import MainWindow
            from src.data.sku_manager import create_sku_manager
            
            # DO NOT create MainWindow instance here!
            # Just importing saves time
            print("Imports preloaded successfully")
            
            # Emit None since we can't create widgets in thread
            self.preload_complete.emit(None)
            
        except Exception as e:
            print(f"Error during import preloading: {e}")
            self.preload_complete.emit(None)


class SplashScreen(QWidget):
    """Professional splash screen with video or fallback animation"""
    
    finished = Signal()
    preloaded_window = Signal(object)  # Emits preloaded MainWindow
    
    # Match mode selector dialog size
    SPLASH_WIDTH = 1000
    SPLASH_HEIGHT = 400
    
    def __init__(self, video_path: str = None, duration_ms: int = 3000):
        super().__init__()
        self.video_path = video_path
        self.duration_ms = duration_ms
        self.preloaded_main_window = None
        self.preloader_thread = None
        self.is_closing = False  # Prevent multiple close attempts
        self.setup_ui()
        self.start_preloading()
        
    def setup_ui(self):
        """Setup the splash screen UI"""
        # Window flags for borderless window
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        
        # Set size to match mode selector
        self.setFixedSize(self.SPLASH_WIDTH, self.SPLASH_HEIGHT)
        
        # Set black background with rounded corners to match mode selector
        self.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
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
            
            # Configure video widget
            self.video_widget.setAspectRatioMode(Qt.KeepAspectRatio)
            self.video_widget.setStyleSheet("background-color: #000000;")
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
            
            # Also set a timer to close after duration_ms in case video doesn't report end
            QTimer.singleShot(self.duration_ms, self.close_splash)
            
        except Exception as e:
            print(f"Error setting up video player: {e}")
            self.setup_fallback_splash(layout)
            
    def setup_fallback_splash(self, layout):
        """Setup fallback splash screen with logo"""
        # Create centered label
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        
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
                    int(self.SPLASH_WIDTH * 0.6), 
                    int(self.SPLASH_HEIGHT * 0.5), 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                self.logo_label.setPixmap(scaled_pixmap)
                logo_loaded = True
                break
        
        if not logo_loaded:
            # Fallback text
            self.logo_label.setText("DIODE DYNAMICS")
            self.logo_label.setStyleSheet("""
                color: white;
                font-size: 48px;
                font-weight: bold;
                font-family: Arial;
            """)
            
        layout.addWidget(self.logo_label)
        
        # Add subtitle
        subtitle = QLabel("Production Test System")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("""
            color: #888888;
            font-size: 24px;
            font-family: Arial;
            margin-top: 20px;
        """)
        layout.addWidget(subtitle)
        
        # Start timer for fallback duration (shorter for faster startup)
        fallback_duration = min(self.duration_ms, 2000)  # Max 2 seconds for fallback
        QTimer.singleShot(fallback_duration, self.close_splash)
        
    def on_media_status_changed(self, status):
        """Handle media status changes"""
        print(f"Media status changed: {status}")
        if status == QMediaPlayer.LoadedMedia:
            # Video loaded successfully, stop timeout
            if hasattr(self, 'video_timeout'):
                self.video_timeout.stop()
            print("Video loaded successfully")
        elif status == QMediaPlayer.EndOfMedia:
            print("Video ended, closing splash...")
            self.close_splash()
            
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
        """Start background preloading of MainWindow"""
        self.preloader_thread = PreloaderThread()
        self.preloader_thread.preload_complete.connect(self.on_preload_complete)
        self.preloader_thread.start()
    
    def on_preload_complete(self, main_window):
        """Handle completion of preloading"""
        self.preloaded_main_window = main_window
        self.preloaded_window.emit(main_window)
        print("Import preloading completed")
    
    def on_position_changed(self, position):
        """Handle video position changes for optimization"""
        # Ensure minimum splash duration even if video is short
        pass
    
    def get_preloaded_window(self):
        """Get the preloaded MainWindow instance"""
        return self.preloaded_main_window
    
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