# gui/components/header_bar.py
import logging  # Added
from pathlib import Path
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)  # Added


def get_window_icon():
    """Get the window icon from the logo file"""
    try:
        # Look for the logo file in the resources directory
        logo_path = Path(__file__).parent.parent.parent.parent / "resources" / "logo.jpg"
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                logger.info(f"Successfully loaded window icon from {logo_path}")
                return QIcon(pixmap)
            else:
                logger.warning(
                    f"Failed to create QPixmap from {logo_path}. File might be corrupted or not a valid image."
                )
        else:
            logger.warning(f"Window icon file not found at {logo_path}")
    except Exception as e:
        logger.error(f"Could not load window icon: {e}", exc_info=True)

    return None


class HeaderBar(QWidget):
    """Header bar widget with company logo and title"""

    def __init__(self, parent=None):
        super().__init__(parent)
        logger.debug("Initializing HeaderBar")  # Added
        try:  # Added
            self.setup_ui()
            logger.debug("HeaderBar UI setup successful")  # Added
        except Exception as e:  # Added
            logger.error("Error during HeaderBar UI setup: %s", e, exc_info=True)  # Added
            # Optionally, set a fallback UI or re-raise
            self._setup_fallback_ui()  # Added

    def setup_ui(self):
        """Setup the header bar UI"""
        try:  # Added
            layout = QHBoxLayout(self)
            layout.setContentsMargins(10, 5, 10, 5)

            # Company logo
            logo_label = QLabel()
            logo_path = Path(__file__).parent.parent.parent.parent / "resources" / "logo.jpg"
            if logo_path.exists():
                pixmap = QPixmap(str(logo_path))
                if not pixmap.isNull():
                    # Scale logo to reasonable size
                    scaled_pixmap = pixmap.scaled(
                        40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    logo_label.setPixmap(scaled_pixmap)
                    logger.debug(f"Logo loaded and scaled from {logo_path}")
                else:
                    logger.warning(
                        f"Failed to create QPixmap for logo from {logo_path}. File might be corrupted or not a valid image."
                    )
                    self._set_default_logo_text(logo_label)
            else:
                logger.warning(f"Logo file not found at {logo_path}")
                self._set_default_logo_text(logo_label)

            layout.addWidget(logo_label)

            # Title
            title_label = QLabel("Diode Dynamics Production Tester")
            title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
            layout.addWidget(title_label)

            # Stretch to push everything to the left
            layout.addStretch()

            # Set background
            self.setStyleSheet("background-color: #2b2b2b; border-bottom: 1px solid #404040;")
            logger.info("HeaderBar UI components configured.")  # Added
        except Exception as e:  # Added
            logger.error("Exception in setup_ui for HeaderBar: %s", e, exc_info=True)  # Added
            # Re-raise the exception to be caught by the __init__ or handle here
            raise  # Added

    def _set_default_logo_text(self, label_widget):  # Added
        """Sets a default text for the logo if image loading fails."""  # Added
        label_widget.setText("Logo")  # Added
        label_widget.setStyleSheet("font-size: 10px; color: grey;")  # Added
        logger.info("Set default text for logo area.")  # Added

    def _setup_fallback_ui(self):  # Added
        """Setup a minimal fallback UI in case of critical errors during setup_ui."""  # Added
        logger.warning("Setting up fallback UI for HeaderBar due to an error.")  # Added
        try:  # Added
            layout = QHBoxLayout(self)  # Added
            layout.setContentsMargins(10, 5, 10, 5)  # Added
            fallback_label = QLabel("Header Error")  # Added
            fallback_label.setStyleSheet("font-size: 16px; font-weight: bold; color: red;")  # Added
            layout.addWidget(fallback_label)  # Added
            layout.addStretch()  # Added
            self.setStyleSheet("background-color: #1e1e1e; border-bottom: 1px solid #303030;")  # Added
        except Exception as e:  # Added
            logger.critical("Failed to setup even fallback UI for HeaderBar: %s", e, exc_info=True)  # Added
