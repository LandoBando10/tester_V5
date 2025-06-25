from PySide6.QtCore import QObject, Signal, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPixmap
from typing import Optional, Callable


class TransitionManager(QObject):
    """Manages seamless transitions between application windows."""
    
    transition_complete = Signal()
    
    def __init__(self):
        super().__init__()
        self._active_window: Optional[QWidget] = None
        self._next_window: Optional[QWidget] = None
        self._transition_group: Optional[QParallelAnimationGroup] = None
        
    def cross_fade(self, from_window: QWidget, to_window: QWidget, 
                   duration: int = 500, on_complete: Optional[Callable] = None):
        """Perform a cross-fade transition between two windows.
        
        Args:
            from_window: The window to fade out
            to_window: The window to fade in
            duration: Duration of the transition in milliseconds
            on_complete: Optional callback to execute when transition completes
        """
        self._active_window = from_window
        self._next_window = to_window
        
        # Don't try to position a maximized window
        from PySide6.QtCore import Qt
        if to_window.windowState() != Qt.WindowMaximized:
            # Position the new window at the same location as the old one
            to_window.move(from_window.pos())
        
        # Create parallel animation group
        self._transition_group = QParallelAnimationGroup()
        
        # Fade out animation
        fade_out = QPropertyAnimation(from_window, b"windowOpacity")
        fade_out.setDuration(duration)
        fade_out.setStartValue(from_window.windowOpacity())
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.InOutQuad)
        
        # Fade in animation
        fade_in = QPropertyAnimation(to_window, b"windowOpacity")
        fade_in.setDuration(duration)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.InOutQuad)
        
        # Add animations to group
        self._transition_group.addAnimation(fade_out)
        self._transition_group.addAnimation(fade_in)
        
        # Connect completion signal
        self._transition_group.finished.connect(lambda: self._on_transition_complete(from_window, to_window, on_complete))
        
        # Show the new window with 0 opacity
        to_window.setWindowOpacity(0.0)
        to_window.show()
        to_window.raise_()
        to_window.activateWindow()
        
        # Start the transition
        self._transition_group.start()
        
    def fade_in(self, window: QWidget, duration: int = 300, 
                on_complete: Optional[Callable] = None):
        """Fade in a window.
        
        Args:
            window: The window to fade in
            duration: Duration of the fade in milliseconds
            on_complete: Optional callback to execute when fade completes
        """
        # Set initial opacity before showing
        window.setWindowOpacity(0.0)
        
        # Show and ensure it's on top
        window.show()
        window.raise_()
        window.activateWindow()
        
        # Create fade in animation
        fade_in = QPropertyAnimation(window, b"windowOpacity")
        fade_in.setDuration(duration)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.OutCubic)
        
        if on_complete:
            fade_in.finished.connect(on_complete)
            
        fade_in.start()
        
    def capture_frame(self, widget: QWidget) -> QPixmap:
        """Capture the current frame of a widget as a pixmap.
        
        Args:
            widget: The widget to capture
            
        Returns:
            QPixmap of the widget's current state
        """
        pixmap = QPixmap(widget.size())
        widget.render(pixmap)
        return pixmap
        
    def _on_transition_complete(self, from_window: QWidget, to_window: QWidget, 
                               callback: Optional[Callable] = None):
        """Handle transition completion."""
        # Close the old window
        from_window.close()
        
        # Execute callback if provided
        if callback:
            callback()
            
        # Emit completion signal
        self.transition_complete.emit()


# Global transition manager instance
transition_manager = TransitionManager()