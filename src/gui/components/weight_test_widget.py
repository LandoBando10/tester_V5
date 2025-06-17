# gui/components/weight_test_widget.py
import logging
import time
from typing import Optional, Dict, Any, NamedTuple
from collections import deque
from enum import Enum
from dataclasses import dataclass

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
                               QPushButton, QTextEdit, QProgressBar)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QFont

from src.hardware.scale_controller import ScaleController
from src.utils.thread_cleanup import ThreadCleanupMixin


class AutoTestState(Enum):
    """Enum for auto-test states to prevent string errors."""
    WAITING = "waiting"
    DETECTING = "detecting"
    TESTING = "testing"
    COMPLETED = "completed"


@dataclass(frozen=True)
class WeightTestConfig:
    """Configuration constants for weight testing."""
    # Weight detection thresholds
    WEIGHT_THRESHOLD_PERCENTAGE: float = 0.8
    PART_REMOVED_THRESHOLD_FACTOR: float = 0.5
    
    # Stability parameters
    WEIGHT_STABLE_THRESHOLD_S: float = 2.0
    WEIGHT_STABLE_TOLERANCE_G: float = 0.5  # Increased from 0.1g to 0.5g for better stability
    MIN_READINGS_FOR_STABILITY: int = 5
    RECENT_WEIGHTS_BUFFER_SIZE: int = 10
    
    # Timing parameters
    WEIGHT_UPDATE_INTERVAL_MS: int = 100
    MEASUREMENT_START_DELAY_MS: int = 100
    STABLE_WEIGHT_TIMEOUT_S: float = 5.0
    STABLE_WEIGHT_NUM_READINGS: int = 5
    STABLE_WEIGHT_TOLERANCE: float = 0.05
    
    # Hardware parameters
    DEFAULT_BAUD_RATE: int = 9600


class UIMessages:
    """Centralized UI message constants."""
    STATUS_WAITING_SKU_CONN = "Waiting for SKU and connection..."
    STATUS_SCALE_NOT_CONNECTED = "Scale not connected. Check Connection menu."
    STATUS_NO_SKU = "No SKU selected. Select from top controls."
    STATUS_PART_DETECTED = "Part detected - checking stability..."
    STATUS_TEST_IN_PROGRESS = "Test in progress..."
    STATUS_READY_AUTO_TEST = "Ready. Place part on scale for auto-test."
    REMOVE_PART_FOR_NEXT = "Remove part to test next unit."
    PART_REMOVED_READY_NEXT = "Part removed - ready for next test."
    READY_TO_TEST = "READY TO TEST"
    TESTING = "TESTING..."
    ERROR = "ERROR"


class StyleManager:
    """Centralized style management with lazy loading."""
    
    _styles = {}
    
    @classmethod
    def get_style(cls, style_name: str) -> str:
        if style_name not in cls._styles:
            cls._load_styles()
        return cls._styles.get(style_name, "")
    
    @classmethod
    def _load_styles(cls):
        # Base styles
        base = "font-size: 12px;"
        weight_display_base = "background-color: #222222; border-radius: 8px; padding: 20px; margin: 10px;"
        indicator_base = "border-radius: 10px; padding: 15px; margin: 5px; font-weight: bold;"
        
        cls._styles.update({
            'base': base,
            'title_label': "color: white; margin-bottom: 10px;",
            'groupbox': "QGroupBox { font-weight: bold; margin-top: 10px; }",
            
            # Weight display styles (updated for new design)
            'weight_display_live': "color: #ffffff;",
            'weight_display_waiting': "color: #ffa500;", 
            'weight_display_disconnected': "color: #444444;",
            
            # Status indicator styles (new simple design)
            'indicator_ready': "color: #666666; background-color: #1a1a1a;",
            'indicator_testing': "color: #ffd43b; background-color: #2a2a1a;",
            'indicator_pass': "color: #51cf66; background-color: #1a2a1a;",
            'indicator_fail': "color: #ff6b6b; background-color: #2a1a1a;",
            
            
            # Status label styles
            'status_default': "color: #ff6b6b; font-weight: bold; font-size: 12px;",
            'status_info': "color: #51cf66; font-weight: bold; font-size: 12px;",
            'status_warn': "color: #ffd43b; font-weight: bold; font-size: 12px;",
            
            # Other component styles
            'progress_bar': """QProgressBar { border: 2px solid #555555; border-radius: 5px; text-align: center; background-color: #333333; color: white; } QProgressBar::chunk { background-color: #4a90a4; border-radius: 3px; }""",
            'results_text': """QTextEdit { background-color: #222222; color: white; border: 1px solid #555555; border-radius: 4px; font-family: 'Courier New', monospace; font-size: 12px; }""",
        })


class WeightRange(NamedTuple):
    """Type-safe weight range representation."""
    min_weight: float
    max_weight: float
    tare: float = 0.0


class WeightTestWidget(QWidget, ThreadCleanupMixin):
    """Optimized weight testing widget with improved performance and maintainability."""

    # Signals
    test_started = Signal(str)
    test_completed = Signal(object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        ThreadCleanupMixin.__init__(self)
        
        self.config = WeightTestConfig()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize state
        self._init_state()
        self._init_ui()
        self._init_timers()

    def _init_state(self):
        """Initialize all state variables."""
        # Core state
        self.current_sku: Optional[str] = None
        self.cached_sku_params: Optional[Dict[str, Any]] = None
        self.scale_controller: Optional[ScaleController] = None
        self.is_testing: bool = False
        self.is_connected: bool = False
        
        # Auto-test configuration
        self.auto_test_enabled: bool = True
        self.zero_offset: float = 0.0
        
        # Auto-test state management
        self.auto_test_state = AutoTestState.WAITING
        self.weight_stable_start: Optional[float] = None
        self.recent_weights: deque = deque(maxlen=self.config.RECENT_WEIGHTS_BUFFER_SIZE)
        self.last_test_result: Optional[object] = None
        self.live_reading_count: int = 0

    def _init_ui(self):
        """Initialize the user interface."""
        self.setup_ui()

    def _init_timers(self):
        """Initialize and configure timers."""
        self.weight_update_timer = QTimer()
        self.weight_update_timer.timeout.connect(self.update_weight_display)
        self.register_resource(
            self.weight_update_timer, 
            "weight_update_timer", 
            self.weight_update_timer.stop
        )

    def setup_ui(self):
        """Setup the main UI layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(30)
        
        # Set dark background for the whole widget
        self.setStyleSheet("""
            background-color: #1a1a1a;
        """)

        # Add stretch at top to center content
        main_layout.addStretch(1)

        # Main content container
        content_container = QWidget()
        content_container.setStyleSheet("""
            background-color: #2b2b2b;
            border-radius: 20px;
        """)
        content_container.setContentsMargins(40, 40, 40, 40)
        content_layout = QVBoxLayout(content_container)
        content_layout.setSpacing(25)

        # Setup components
        self._setup_weight_display(content_layout)
        self._setup_range_display(content_layout)
        self._setup_status_display(content_layout)

        main_layout.addWidget(content_container)
        main_layout.addStretch(1)
        
        # Hidden elements for functionality
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        # Hidden text area for logging (keep for functionality)
        self.results_text = QTextEdit()
        self.results_text.setVisible(False)

    def _setup_weight_display(self, parent_layout):
        """Setup the main weight display."""
        # Weight reading label
        weight_title = QLabel("LIVE WEIGHT")
        weight_title.setAlignment(Qt.AlignCenter)
        weight_title.setFont(QFont("Arial", 12))
        weight_title.setStyleSheet("color: #666666; letter-spacing: 2px;")
        parent_layout.addWidget(weight_title)
        
        # Main weight display
        self.weight_display_label = QLabel("---")
        self.weight_display_label.setFont(QFont("Arial", 72, QFont.Bold))
        self.weight_display_label.setAlignment(Qt.AlignCenter)
        self.weight_display_label.setMinimumHeight(100)
        self.weight_display_label.setStyleSheet("""
            color: #ffffff;
            background-color: transparent;
            padding: 10px;
        """)
        parent_layout.addWidget(self.weight_display_label)

    def _setup_range_display(self, parent_layout):
        """Setup the min/max range display."""
        # Range container
        range_container = QWidget()
        range_layout = QHBoxLayout(range_container)
        range_layout.setSpacing(50)
        
        # Min display
        self.sku_min_label = QLabel("---")
        self.sku_min_label.setAlignment(Qt.AlignCenter)
        self.sku_min_label.setFont(QFont("Arial", 24))
        self.sku_min_label.setStyleSheet("""
            color: #888888;
            padding: 5px 15px;
        """)
        
        # Max display
        self.sku_max_label = QLabel("---")
        self.sku_max_label.setAlignment(Qt.AlignCenter) 
        self.sku_max_label.setFont(QFont("Arial", 24))
        self.sku_max_label.setStyleSheet("""
            color: #888888;
            padding: 5px 15px;
        """)
        
        range_layout.addStretch()
        range_layout.addWidget(self.sku_min_label)
        range_layout.addWidget(QLabel("-", alignment=Qt.AlignCenter, styleSheet="color: #555555; font-size: 24px;"))
        range_layout.addWidget(self.sku_max_label)
        range_layout.addStretch()
        
        parent_layout.addWidget(range_container)
        
        # Hidden elements for functionality
        self.status_label = QLabel()
        self.status_label.setVisible(False)
        self.threshold_label = QLabel()
        self.threshold_label.setVisible(False)


    def _setup_status_display(self, parent_layout):
        """Setup the test status display."""
        # Add separator line
        separator = QWidget()
        separator.setFixedHeight(2)
        separator.setStyleSheet("background-color: #333333;")
        parent_layout.addWidget(separator)
        
        # Status indicator
        self.result_indicator = QLabel("READY TO TEST")
        self.result_indicator.setFont(QFont("Arial", 28, QFont.Bold))
        self.result_indicator.setAlignment(Qt.AlignCenter)
        self.result_indicator.setMinimumHeight(80)
        self.result_indicator.setStyleSheet("""
            color: #666666;
            background-color: #1a1a1a;
            border-radius: 15px;
            padding: 20px;
        """)
        parent_layout.addWidget(self.result_indicator)

    def set_sku(self, sku: Optional[str]):
        """Set the current SKU and update related parameters."""
        self.current_sku = sku
        
        if sku:
            self.logger.info(f"SKU set to: {sku}")
            self.cached_sku_params = self._load_sku_parameters(sku)
            self._reset_auto_test_state()
        else:
            self.logger.info("SKU cleared")
            self.cached_sku_params = None
            self.reset_weight_statistics()
        
        self.update_sku_parameter_display()

    def _reset_auto_test_state(self):
        """Reset auto-test state when SKU changes."""
        self.auto_test_state = AutoTestState.WAITING
        self.result_indicator.setText("READY TO TEST")
        self.result_indicator.setStyleSheet("""
            color: #666666;
            background-color: #1a1a1a;
            border-radius: 15px;
            padding: 20px;
            font-size: 28px;
            font-weight: bold;
        """)
        self.recent_weights.clear()
        self.weight_stable_start = None

    def _find_sku_manager(self):
        """Find SKU manager in parent hierarchy."""
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, 'sku_manager') and parent.sku_manager is not None:
                self.logger.debug(f"Found SKU manager in parent: {type(parent).__name__}")
                return parent.sku_manager
            parent = parent.parent()
        return None

    def _load_sku_parameters(self, sku: str) -> Optional[Dict[str, Any]]:
        """Load SKU parameters from SKU manager."""
        sku_manager = self._find_sku_manager()
        
        if sku_manager:
            return sku_manager.get_test_parameters(sku, "WeightChecking")
        else:
            self.logger.warning("No SKU manager found, using default parameters")
            return self._get_default_parameters()

    def _get_default_parameters(self) -> Dict[str, Any]:
        """Get default weight parameters."""
        return {
            "WEIGHT": {
                "min_weight_g": 100.0, 
                "max_weight_g": 300.0, 
                "tare_g": 0.0
            }
        }

    def set_connection_status(self, connected: bool, port: Optional[str] = None):
        """Set the connection status and manage scale controller."""
        self.logger.info(f"Setting connection status: connected={connected}, port={port}")
        self.is_connected = connected

        if connected and port:
            self._establish_connection(port)
        else:
            self._close_connection()
        
        self.update_test_button_state()

    def _establish_connection(self, port: str):
        """Establish connection to the scale controller."""
        # First check if there's already a connected scale from connection dialog
        main_window = self._get_main_window()
        if (main_window and hasattr(main_window, 'scale_controller') and 
            main_window.scale_controller and main_window.scale_controller.is_connected()):
            
            # Check if it's connected to the right port
            if (hasattr(main_window.scale_controller.serial, 'port') and 
                main_window.scale_controller.serial.port == port):
                self.logger.info(f"Reusing existing scale connection from connection dialog on {port}")
                self.scale_controller = main_window.scale_controller
                self._start_live_reading(port)
                return
        
        # Check if we can reuse existing controller
        if self.scale_controller and not self._should_recreate_scale_controller(port):
            # Try to reconnect with existing controller
            self.logger.info(f"Reusing existing scale controller for port {port}")
            if self.scale_controller.is_connected():
                # Already connected to same port
                self._start_live_reading(port)
                return
            elif self.scale_controller.connect(port, skip_comm_test=self._is_connection_validated(port)):
                # Reconnected successfully
                self._start_live_reading(port)
                return
        
        # Need new controller or reconnection failed
        if self._should_recreate_scale_controller(port):
            self._close_connection()
            
            try:
                self.scale_controller = ScaleController(baud_rate=self.config.DEFAULT_BAUD_RATE)
                
                # Check if connection was already validated through connection dialog
                skip_comm_test = self._is_connection_validated(port)
                
                if self.scale_controller.connect(port, skip_comm_test=skip_comm_test):
                    self._start_live_reading(port)
                else:
                    self._handle_connection_failure(port)
                    
            except Exception as e:
                self.logger.error(f"Exception during scale connection on {port}: {e}")
                self._handle_connection_failure(port, str(e))

    def _should_recreate_scale_controller(self, port: str) -> bool:
        """Check if scale controller needs to be recreated."""
        return (not self.scale_controller or 
                (hasattr(self.scale_controller, 'serial') and 
                 hasattr(self.scale_controller.serial, 'port') and 
                 self.scale_controller.serial.port != port))
    
    def _get_main_window(self):
        """Get reference to main window."""
        main_window = self.parent()
        while main_window and not hasattr(main_window, 'connection_dialog'):
            main_window = main_window.parent()
        return main_window
    
    def _is_connection_validated(self, port: str) -> bool:
        """Check if connection was already validated through connection dialog."""
        try:
            main_window = self._get_main_window()
            if main_window and hasattr(main_window, 'connection_dialog'):
                status = main_window.connection_dialog.get_connection_status()
                # If scale is marked as connected on the same port, skip comm test
                return (status.get('scale_connected', False) and 
                        status.get('scale_port') == port)
        except Exception as e:
            self.logger.debug(f"Could not check connection validation status: {e}")
        
        return False

    def _start_live_reading(self, port: str):
        """Start live reading from the scale controller."""
        read_interval_seconds = self.config.WEIGHT_UPDATE_INTERVAL_MS / 1000.0
        # Use faster read interval for scale (50ms) while UI updates at 100ms
        self.scale_controller.start_reading(
            callback=self._weight_reading_callback,
            read_interval_s=0.05  # 50ms for faster response
        )
        self.weight_update_timer.start(self.config.WEIGHT_UPDATE_INTERVAL_MS)
        self.weight_display_label.setStyleSheet(StyleManager.get_style('weight_display_live'))
        
        self.logger.info(f"Scale connected on {port}. Live reading active.")

    def _close_connection(self, force_disconnect: bool = True):
        """Close the scale controller connection."""
        if self.scale_controller:
            self.weight_update_timer.stop()
            if force_disconnect:
                self.scale_controller.disconnect()
                self.scale_controller = None
            else:
                # Just stop reading, keep controller instance
                self.scale_controller.stop_reading()
        if force_disconnect:
            self._reset_ui_for_disconnection()

    def _handle_connection_failure(self, port: str, error_msg: str = ""):
        """Handle connection failure."""
        self.logger.error(f"Failed to connect to scale on {port}. {error_msg}")
        self.is_connected = False
        self.scale_controller = None
        self._reset_ui_for_disconnection()

    def _reset_ui_for_disconnection(self):
        """Reset UI elements when disconnected."""
        self.weight_display_label.setText("--- g")
        self.weight_display_label.setStyleSheet(StyleManager.get_style('weight_display_disconnected'))
        self.reset_weight_statistics()
        self.live_reading_count = 0

    def _weight_reading_callback(self, reading):
        """Callback for weight readings from scale controller."""
        self.live_reading_count += 1


    def _can_operate_scale(self) -> bool:
        """Check if scale operations are possible."""
        return self.scale_controller is not None and self.is_connected

    def get_adjusted_weight(self) -> Optional[float]:
        """Get current weight adjusted for tare offset."""
        if not self._can_operate_scale():
            return None
            
        current_weight = self.scale_controller.current_weight
        return current_weight - self.zero_offset if current_weight is not None else None

    def update_weight_display(self):
        """Update the weight display with current reading."""
        # Skip update if widget is not visible (performance optimization)
        if not self.isVisible():
            return
            
        if not self._can_operate_scale():
            self._display_disconnected_weight()
            return

        try:
            adjusted_weight = self.get_adjusted_weight()

            if adjusted_weight is not None:
                self._display_live_weight(adjusted_weight)
                self.handle_auto_test_trigger(adjusted_weight)
            else:
                self._display_waiting_weight()
                
        except Exception as e:
            self.logger.error(f"Error updating weight display: {e}")
            self._display_error_weight()

    def _display_disconnected_weight(self):
        """Display disconnected state."""
        self.weight_display_label.setText("---")
        self.weight_display_label.setStyleSheet(StyleManager.get_style('weight_display_disconnected'))

    def _display_live_weight(self, weight: float):
        """Display live weight reading."""
        self.weight_display_label.setText(f"{weight:.1f} g")
        self.weight_display_label.setStyleSheet(StyleManager.get_style('weight_display_live'))

    def _display_waiting_weight(self):
        """Display waiting state."""
        self.weight_display_label.setText("---")
        self.weight_display_label.setStyleSheet("color: #666666;")

    def _display_error_weight(self):
        """Display error state."""
        self.weight_display_label.setText("---")
        self.weight_display_label.setStyleSheet("color: #666666;")

    def handle_auto_test_trigger(self, current_weight: float):
        """Handle auto-test triggering based on current weight."""
        if not self._should_process_auto_test():
            return

        weight_range = self._get_weight_range()
        if not weight_range:
            return

        threshold_weight = weight_range.min_weight * self.config.WEIGHT_THRESHOLD_PERCENTAGE
        self._update_threshold_display(threshold_weight, weight_range.min_weight)
        self.recent_weights.append(current_weight)

        # State machine dispatch
        state_handlers = {
            AutoTestState.WAITING: self._handle_autotest_waiting,
            AutoTestState.DETECTING: self._handle_autotest_detecting,
            AutoTestState.TESTING: lambda *args: None,  # No action during testing
            AutoTestState.COMPLETED: self._handle_autotest_completed
        }
        
        handler = state_handlers.get(self.auto_test_state)
        if handler:
            handler(current_weight, threshold_weight, weight_range)

    def _should_process_auto_test(self) -> bool:
        """Check if auto-test processing should continue."""
        return (self.auto_test_enabled and 
                self.current_sku and 
                self.is_connected and 
                not self.is_testing)

    def _get_weight_range(self) -> Optional[WeightRange]:
        """Get the current weight range parameters."""
        if not self.cached_sku_params or "WEIGHT" not in self.cached_sku_params:
            return None

        weight_params = self.cached_sku_params["WEIGHT"]
        min_weight = weight_params.get("min_weight_g", 0.0)
        
        if min_weight <= 0:
            return None

        return WeightRange(
            min_weight=min_weight,
            max_weight=weight_params.get("max_weight_g", 0.0),
            tare=weight_params.get("tare_g", 0.0)
        )

    def _update_threshold_display(self, threshold_weight: float, min_weight: float):
        """Update the threshold display label."""
        percentage = self.config.WEIGHT_THRESHOLD_PERCENTAGE * 100
        self.threshold_label.setText(f"{threshold_weight:.1f} g")
        self.threshold_label.setToolTip(
            f"{percentage:.0f}% of minimum weight ({min_weight:.1f}g)"
        )

    def _handle_autotest_waiting(self, current_weight: float, threshold_weight: float, weight_range: WeightRange):
        """Handle auto-test waiting state."""
        if current_weight >= threshold_weight:
            self.auto_test_state = AutoTestState.DETECTING
            self.weight_stable_start = time.time()
            self.logger.info(f"Part detected ({current_weight:.2f}g >= {threshold_weight:.2f}g). Checking stability.")
            self.update_test_button_state()

    def _handle_autotest_detecting(self, current_weight: float, threshold_weight: float, weight_range: WeightRange):
        """Handle auto-test detecting state."""
        if current_weight >= threshold_weight:
            if self._is_weight_stable(current_weight):
                elapsed_stable_time = time.time() - (self.weight_stable_start or time.time())
                if elapsed_stable_time >= self.config.WEIGHT_STABLE_THRESHOLD_S:
                    self._start_auto_test(current_weight)
            else:
                self.weight_stable_start = time.time()
        else:
            self._reset_to_waiting_state(current_weight, threshold_weight)

    def _handle_autotest_completed(self, current_weight: float, threshold_weight: float, weight_range: WeightRange):
        """Handle auto-test completed state."""
        min_weight_for_presence = (weight_range.min_weight * self.config.PART_REMOVED_THRESHOLD_FACTOR)
        
        if current_weight < min_weight_for_presence:
            self._reset_to_waiting_state()
            self.logger.info(UIMessages.PART_REMOVED_READY_NEXT)
            self.result_indicator.setText("READY TO TEST")
            self.result_indicator.setStyleSheet("""
                color: #666666;
                background-color: #1a1a1a;
                border-radius: 15px;
                padding: 20px;
                font-size: 28px;
                font-weight: bold;
            """)

    def _start_auto_test(self, current_weight: float):
        """Start auto-triggered test."""
        self.logger.info(f"Weight stable at {current_weight:.2f}g. Starting auto-test.")
        self.auto_test_state = AutoTestState.TESTING
        self.start_weight_test(auto_triggered=True)

    def _reset_to_waiting_state(self, current_weight: float = 0, threshold_weight: float = 0):
        """Reset auto-test to waiting state."""
        self.auto_test_state = AutoTestState.WAITING
        self.weight_stable_start = None
        self.recent_weights.clear()
        
        if current_weight and threshold_weight:
            self.logger.info(f"Weight ({current_weight:.2f}g) dropped below threshold ({threshold_weight:.2f}g). Resetting.")
        
        self.update_test_button_state()

    def _is_weight_stable(self, current_weight: float) -> bool:
        """Check if weight readings are stable."""
        if len(self.recent_weights) < self.config.MIN_READINGS_FOR_STABILITY:
            return False
            
        relevant_weights = list(self.recent_weights)[-self.config.MIN_READINGS_FOR_STABILITY:]
        
        # Calculate median to be more robust against outliers
        sorted_weights = sorted(relevant_weights)
        median_weight = sorted_weights[len(sorted_weights) // 2]
        
        # Check if current weight is close to median
        if abs(current_weight - median_weight) > self.config.WEIGHT_STABLE_TOLERANCE_G * 2:
            return False
        
        # Check if most readings (80%) are within tolerance
        within_tolerance = sum(
            1 for w in relevant_weights 
            if abs(w - median_weight) <= self.config.WEIGHT_STABLE_TOLERANCE_G
        )
        
        return within_tolerance >= len(relevant_weights) * 0.8

    def start_weight_test(self, auto_triggered: bool = True):
        """Start an auto-triggered weight test."""
        validation_error = self._validate_test_preconditions()
        if validation_error:
            self.logger.warning(f"Cannot start test: {validation_error}")
            return

        if self.is_testing:
            self.logger.info("Test already in progress. Ignoring new start request.")
            return

        try:
            self._begin_test_sequence(auto_triggered)
        except Exception as e:
            self.logger.error(f"Critical error setting up weight measurement: {e}")
            self.on_test_error(f"Setup error: {e}")

    def _validate_test_preconditions(self) -> Optional[str]:
        """Validate that all preconditions for testing are met."""
        if not self.current_sku:
            return "No SKU selected"
        if not self.is_connected or not self.scale_controller:
            return "Scale not connected"
        if not self.cached_sku_params or "WEIGHT" not in self.cached_sku_params:
            return "No weight parameters available"
        return None

    def _begin_test_sequence(self, auto_triggered: bool):
        """Begin the test sequence."""
        self.is_testing = True
        if auto_triggered:
            self.auto_test_state = AutoTestState.TESTING
        
        self.update_test_button_state()
        self.result_indicator.setText("TESTING...")
        self.result_indicator.setStyleSheet("""
            color: #ffd43b;
            background-color: #2a2a1a;
            border-radius: 15px;
            padding: 20px;
            font-size: 28px;
            font-weight: bold;
        """)
        
        self.perform_weight_measurement(self.cached_sku_params, auto_triggered)

    def perform_weight_measurement(self, parameters: Dict[str, Any], auto_triggered: bool = False):
        """Perform the actual weight measurement."""
        try:
            weight_range = self._extract_weight_parameters(parameters)
            effective_tare = self._calculate_effective_tare(weight_range.tare)
            
            trigger_msg = "Auto-triggered" if auto_triggered else "Manual"
            self.add_result_message(
                f"{trigger_msg} weight test for SKU: {self.current_sku} (Tare: {effective_tare:.2f}g)"
            )
            
            self.test_started.emit(self.current_sku)
            QTimer.singleShot(
                self.config.MEASUREMENT_START_DELAY_MS,
                lambda: self.run_measurement_sequence(weight_range, effective_tare)
            )
            
        except KeyError as e:
            self.logger.error(f"Missing key in weight parameters: {e}")
            self.on_test_error(f"Parameter error: {e}")
        except Exception as e:
            self.logger.error(f"Error in measurement setup: {e}")
            self.on_test_error(f"Measurement setup error: {e}")

    def _extract_weight_parameters(self, parameters: Dict[str, Any]) -> WeightRange:
        """Extract weight parameters into a structured format."""
        weight_params = parameters["WEIGHT"]
        return WeightRange(
            min_weight=weight_params["min_weight_g"],
            max_weight=weight_params["max_weight_g"],
            tare=weight_params.get("tare_g", 0.0)
        )

    def _calculate_effective_tare(self, sku_tare: float) -> float:
        """Calculate the effective tare to use for measurement."""
        return sku_tare if sku_tare is not None else self.zero_offset

    def run_measurement_sequence(self, weight_range: WeightRange, tare_offset: float):
        """Run the measurement sequence and handle results."""
        from src.core.base_test import TestResult
        
        result = TestResult()  # TestResult doesn't accept constructor arguments
        result.sku = self.current_sku  # Add SKU to result for logging
        start_time = time.time()

        try:
            self._execute_measurement(result, weight_range, tare_offset)
        except Exception as e:
            self.logger.error(f"Unexpected error in measurement sequence: {e}")
            result.failures.append(f"Unexpected error: {e}")
        finally:
            result.test_duration = time.time() - start_time
            self.progress_bar.setVisible(False)
            QTimer.singleShot(0, lambda: self.on_test_completed(result))

    def _execute_measurement(self, result, weight_range: WeightRange, tare_offset: float):
        """Execute the actual measurement process."""
        self.add_result_message("Measuring weight...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate

        if not self.scale_controller:
            raise ConnectionError("Scale controller not available during measurement.")

        stable_weight = self.scale_controller.get_stable_weight(
            num_readings=self.config.STABLE_WEIGHT_NUM_READINGS,
            tolerance=self.config.STABLE_WEIGHT_TOLERANCE,
            timeout=self.config.STABLE_WEIGHT_TIMEOUT_S
        )

        if stable_weight is None:
            result.failures.append("Could not get stable weight reading in time.")
        else:
            self._process_measurement_result(result, stable_weight, weight_range, tare_offset)

    def _process_measurement_result(self, result, stable_weight: float, weight_range: WeightRange, tare_offset: float):
        """Process the measurement result and determine pass/fail."""
        final_weight = stable_weight - tare_offset
        result.add_measurement("weight", final_weight, weight_range.min_weight, weight_range.max_weight, "g")
        
        # Ensure correct pass/fail determination
        result.passed = weight_range.min_weight <= final_weight <= weight_range.max_weight
        
        status = 'PASS' if result.passed else 'FAIL'
        self.logger.info(
            f"Weight: {final_weight:.3f}g "
            f"(Range: {weight_range.min_weight:.1f}-{weight_range.max_weight:.1f}g, "
            f"Tare Used: {tare_offset:.2f}g) - {status}"
        )

    def on_test_completed(self, result):
        """Handle test completion."""
        self.is_testing = False
        self.progress_bar.setVisible(False)
        self.auto_test_state = AutoTestState.COMPLETED
        self.last_test_result = result

        self._update_result_indicator(result)
        self._log_test_results(result)
        
        self.test_completed.emit(result)
        self.update_test_button_state()

    def _update_result_indicator(self, result):
        """Update the result indicator based on test outcome."""
        if result.passed:
            self.result_indicator.setText("PASS")
            self.result_indicator.setStyleSheet("""
                color: #51cf66;
                background-color: #1a2a1a;
                border-radius: 15px;
                padding: 20px;
                font-size: 32px;
                font-weight: bold;
            """)
        else:
            self.result_indicator.setText("FAIL")
            self.result_indicator.setStyleSheet("""
                color: #ff6b6b;
                background-color: #2a1a1a;
                border-radius: 15px;
                padding: 20px;
                font-size: 32px;
                font-weight: bold;
            """)

    def _log_test_results(self, result):
        """Log detailed test results to the results text area."""
        status_msg = "PASS" if result.passed else "FAIL"
        
        self.add_result_message(f"\n{'='*50}")
        self.add_result_message(f"TEST {status_msg} - {result.sku}")
        self.add_result_message(f"Duration: {result.test_duration:.2f} seconds")

        if result.measurements:
            self._log_measurements(result.measurements)
        
        if result.failures:
            self._log_failures(result.failures)

        self.add_result_message(f"\n{UIMessages.REMOVE_PART_FOR_NEXT}")

    def _log_measurements(self, measurements: Dict[str, Any]):
        """Log measurement details."""
        self.add_result_message("\nMeasurements:")
        for name, data in measurements.items():
            m_status = "PASS" if data.get('passed', False) else "FAIL"
            val_str = f"{data['value']:.3f}" if isinstance(data['value'], (int, float)) else str(data['value'])
            min_str = f"{data['min']:.1f}" if isinstance(data['min'], (int, float)) else str(data['min'])
            max_str = f"{data['max']:.1f}" if isinstance(data['max'], (int, float)) else str(data['max'])
            unit = data.get('unit', '')
            
            self.add_result_message(
                f"  {name}: {val_str}{unit} [{min_str}-{max_str}]{unit} - {m_status}"
            )

    def _log_failures(self, failures: list):
        """Log failure details."""
        self.add_result_message("\nFailures:")
        for failure in failures:
            self.add_result_message(f"  - {failure}")

    def on_test_error(self, error_message: str):
        """Handle test errors."""
        self.is_testing = False
        self.progress_bar.setVisible(False)
        self.auto_test_state = AutoTestState.WAITING
        
        self._set_result_indicator_error(error_message)
        self.update_test_button_state()

    def _set_result_indicator_error(self, details: str = ""):
        """Set the result indicator to error state."""
        self.result_indicator.setText("ERROR")
        self.result_indicator.setStyleSheet("""
            color: #ff6b6b;
            background-color: #2a1a1a;
            border-radius: 15px;
            padding: 20px;
            font-size: 28px;
            font-weight: bold;
        """)


    def update_test_button_state(self):
        """Update the status display (no buttons to manage)."""
        self._update_status_label()

    def _update_status_label(self):
        """Update the status label based on current state."""
        status_info = self._determine_status_info()
        self.status_label.setText(status_info['message'])
        self.status_label.setStyleSheet(StyleManager.get_style(status_info['style']))

    def _determine_status_info(self) -> Dict[str, str]:
        """Determine the appropriate status message and style."""
        if not self.is_connected:
            return {
                'message': UIMessages.STATUS_SCALE_NOT_CONNECTED,
                'style': 'status_default'
            }
        
        if not self.current_sku:
            return {
                'message': UIMessages.STATUS_NO_SKU,
                'style': 'status_default'
            }
        
        if self.is_testing:
            return {
                'message': UIMessages.STATUS_TEST_IN_PROGRESS,
                'style': 'status_warn'
            }
        
        if self.auto_test_state == AutoTestState.DETECTING:
            return {
                'message': UIMessages.STATUS_PART_DETECTED,
                'style': 'status_warn'
            }
        
        if self.auto_test_state == AutoTestState.COMPLETED:
            return self._get_completed_status_info()
        
        if self.auto_test_state == AutoTestState.WAITING:
            return {
                'message': UIMessages.STATUS_READY_AUTO_TEST,
                'style': 'status_info'
            }
        
        # Default fallback
        return {
            'message': UIMessages.STATUS_WAITING_SKU_CONN,
            'style': 'status_default'
        }

    def _get_completed_status_info(self) -> Dict[str, str]:
        """Get status info for completed test state."""
        if self.last_test_result:
            status_msg = "PASSED" if self.last_test_result.passed else "FAILED"
            style = 'status_info' if self.last_test_result.passed else 'status_default'
        else:
            status_msg = "COMPLETED"
            style = 'status_default'
        
        return {
            'message': f"Test {status_msg}. {UIMessages.REMOVE_PART_FOR_NEXT}",
            'style': style
        }

    def reset_weight_statistics(self):
        """Reset weight statistics display."""
        self.sku_min_label.setText("---")
        self.sku_max_label.setText("---")
        self.sku_min_label.setStyleSheet("color: #888888; padding: 5px 15px;")
        self.sku_max_label.setStyleSheet("color: #888888; padding: 5px 15px;")
        if hasattr(self, 'threshold_label'):
            self.threshold_label.setText("--- g")

    def update_sku_parameter_display(self):
        """Update SKU parameter display."""
        if not self._has_valid_sku_params():
            self.reset_weight_statistics()
            return

        try:
            weight_params = self.cached_sku_params["WEIGHT"]
            min_w = weight_params.get("min_weight_g", 0.0)
            max_w = weight_params.get("max_weight_g", 0.0)
            
            # Update range display with actual values
            self.sku_min_label.setText(f"{min_w:.0f} g")
            self.sku_max_label.setText(f"{max_w:.0f} g")
            self.sku_min_label.setStyleSheet("color: #4a90a4; padding: 5px 15px;")
            self.sku_max_label.setStyleSheet("color: #4a90a4; padding: 5px 15px;")
            
        except (KeyError, TypeError) as e:
            self.logger.error(f"Error updating SKU display: {e}")
            self.reset_weight_statistics()

    def _has_valid_sku_params(self) -> bool:
        """Check if valid SKU parameters are available."""
        return (self.current_sku and 
                self.cached_sku_params and 
                "WEIGHT" in self.cached_sku_params)

    def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status information."""
        return {
            'connected': self.is_connected,
            'port': self.scale_controller.serial.port if (self.scale_controller and hasattr(self.scale_controller.serial, 'port')) else None
        }

    def add_result_message(self, message: str):
        """Add a message to the results text area."""
        # Results are hidden in the new design, but keep for logging
        if hasattr(self, 'results_text'):
            self.results_text.append(message)

    def cleanup(self):
        """Clean up widget resources."""
        self.logger.info("Cleaning up WeightTestWidget resources...")
        
        if self.weight_update_timer.isActive():
            self.weight_update_timer.stop()
        
        if self.scale_controller:
            self.logger.info("Disconnecting scale controller.")
            self.scale_controller.disconnect()
            self.scale_controller = None
        
        self.cleanup_resources()
        self.logger.info("WeightTestWidget resources cleanup finished.")
    
    def pause_reading(self):
        """Pause scale reading without disconnecting (for mode switching)."""
        if self.scale_controller and self.is_connected:
            self.logger.info("Pausing scale reading for mode switch")
            self._close_connection(force_disconnect=False)
    
    def resume_reading(self):
        """Resume scale reading after mode switch."""
        if self.scale_controller and self.is_connected:
            port = self.scale_controller.serial.port if hasattr(self.scale_controller.serial, 'port') else None
            if port:
                self.logger.info(f"Resuming scale reading on port {port}")
                self._establish_connection(port)
