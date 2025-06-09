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
from src.utils.resource_manager import ResourceMixin


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
    WEIGHT_STABLE_TOLERANCE_G: float = 0.1
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
    TEST_STOPPED_BY_USER = "Test stopped by user."
    READY_TO_TEST = "READY TO TEST"
    TESTING = "TESTING..."
    ERROR = "ERROR"
    TEST_STOPPED = "TEST STOPPED"


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
        btn_base = "border: none; border-radius: 6px; padding: 8px 16px; font-size: 12px; font-weight: bold;"
        weight_display_base = "background-color: #222222; border-radius: 8px; padding: 20px; margin: 10px;"
        indicator_base = "border-radius: 10px; padding: 15px; margin: 5px; font-weight: bold;"
        
        cls._styles.update({
            'base': base,
            'title_label': "color: white; margin-bottom: 10px;",
            'groupbox': "QGroupBox { font-weight: bold; margin-top: 10px; }",
            
            # Weight display styles
            'weight_display_live': f"color: #51cf66; border: 2px solid #51cf66; {weight_display_base}",
            'weight_display_waiting': f"color: #ffa500; border: 2px solid #ffa500; {weight_display_base}",
            'weight_display_disconnected': f"color: #666666; border: 2px solid #555555; {weight_display_base}",
            
            # Status indicator styles
            'indicator_ready': f"background-color: #333333; color: #cccccc; border: 3px solid #555555; {indicator_base}",
            'indicator_testing': f"background-color: #4a4a2d; color: #ffd43b; border: 3px solid #ffd43b; {indicator_base}",
            'indicator_pass': f"background-color: #2d5a2d; color: #51cf66; border: 3px solid #51cf66; {indicator_base}",
            'indicator_fail': f"background-color: #5a2d2d; color: #ff6b6b; border: 3px solid #ff6b6b; {indicator_base}",
            
            # Button styles
            'btn_disabled': "background-color: #444444; color: #999999;",
            'btn_zero': f"QPushButton {{ background-color: #666666; color: white; {btn_base} }} QPushButton:hover {{ background-color: #777777; }}",
            'btn_manual_test': f"QPushButton {{ background-color: #4a90a4; color: white; {btn_base} }} QPushButton:hover {{ background-color: #357a8a; }}",
            'btn_stop_test': f"QPushButton {{ background-color: #ff6b6b; color: white; {btn_base} }} QPushButton:hover {{ background-color: #ff5252; }}",
            
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


class WeightTestWidget(QWidget, ResourceMixin):
    """Optimized weight testing widget with improved performance and maintainability."""

    # Signals
    test_started = Signal(str)
    test_completed = Signal(object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        ResourceMixin.__init__(self)
        
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
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Title
        title_label = QLabel("Weight Checking Mode")
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(StyleManager.get_style('title_label'))
        main_layout.addWidget(title_label)

        # Setup component groups
        self._setup_weight_display_group(main_layout)
        self._setup_test_controls_group(main_layout)
        self._setup_status_indicator_group(main_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(StyleManager.get_style('progress_bar'))
        main_layout.addWidget(self.progress_bar)

        # Results text area
        self.results_text = QTextEdit()
        self.results_text.setMaximumHeight(150)
        self.results_text.setStyleSheet(StyleManager.get_style('results_text'))
        self.results_text.setPlaceholderText("Test results will appear here...")
        main_layout.addWidget(self.results_text)

        main_layout.addStretch()
        self.setStyleSheet(StyleManager.get_style('groupbox'))

    def _setup_weight_display_group(self, parent_layout):
        """Setup the weight display group."""
        weight_group = QGroupBox("Scale")
        layout = QVBoxLayout(weight_group)

        # Main weight display
        self.weight_display_label = QLabel("--- g")
        self.weight_display_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.weight_display_label.setAlignment(Qt.AlignCenter)
        self.weight_display_label.setStyleSheet(StyleManager.get_style('weight_display_disconnected'))
        layout.addWidget(self.weight_display_label)

        # SKU parameters display
        sku_layout = QHBoxLayout()
        self.sku_min_label = QLabel("MIN: ---g")
        self.sku_max_label = QLabel("MAX: ---g")
        
        for label in [self.sku_min_label, self.sku_max_label]:
            label.setStyleSheet("color: #4a90a4; font-size: 12px; font-weight: bold;")
            sku_layout.addWidget(label)
        
        sku_layout.addStretch()
        layout.addLayout(sku_layout)
        parent_layout.addWidget(weight_group)

    def _setup_test_controls_group(self, parent_layout):
        """Setup the test controls group."""
        controls_group = QGroupBox("Test Controls")
        layout = QVBoxLayout(controls_group)

        # Status display
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Status:"))
        self.status_label = QLabel(UIMessages.STATUS_WAITING_SKU_CONN)
        self.status_label.setStyleSheet(StyleManager.get_style('status_default'))
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        # Threshold display
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("Auto-test threshold:"))
        self.threshold_label = QLabel("---g (80% of min weight)")
        self.threshold_label.setStyleSheet("color: #cccccc; font-size: 12px;")
        threshold_layout.addWidget(self.threshold_label)
        threshold_layout.addStretch()
        layout.addLayout(threshold_layout)

        # Control buttons
        self._setup_control_buttons(layout)
        parent_layout.addWidget(controls_group)

    def _setup_control_buttons(self, parent_layout):
        """Setup control buttons with proper styling."""
        button_layout = QHBoxLayout()
        
        # Zero button
        self.zero_btn = QPushButton("Zero Scale")
        self.zero_btn.clicked.connect(self.zero_scale)
        self.zero_btn.setStyleSheet(StyleManager.get_style('btn_zero'))
        button_layout.addWidget(self.zero_btn)

        # Manual test button
        self.manual_test_btn = QPushButton("Start Manual Test")
        self.manual_test_btn.clicked.connect(lambda: self.start_weight_test(auto_triggered=False))
        self.manual_test_btn.setStyleSheet(StyleManager.get_style('btn_manual_test'))
        button_layout.addWidget(self.manual_test_btn)

        # Stop test button
        self.stop_test_btn = QPushButton("Stop Test")
        self.stop_test_btn.clicked.connect(self.stop_weight_test)
        self.stop_test_btn.setStyleSheet(StyleManager.get_style('btn_stop_test'))
        button_layout.addWidget(self.stop_test_btn)
        
        button_layout.addStretch()
        parent_layout.addLayout(button_layout)
        
        self.update_test_button_state()

    def _setup_status_indicator_group(self, parent_layout):
        """Setup the status indicator group."""
        status_group = QGroupBox("Test Status")
        layout = QVBoxLayout(status_group)

        # Result indicator
        self.result_indicator = QLabel(UIMessages.READY_TO_TEST)
        self.result_indicator.setFont(QFont("Arial", 20, QFont.Bold))
        self.result_indicator.setAlignment(Qt.AlignCenter)
        self.result_indicator.setMinimumHeight(60)
        self.result_indicator.setStyleSheet(StyleManager.get_style('indicator_ready'))
        layout.addWidget(self.result_indicator)
        
        parent_layout.addWidget(status_group)

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
        self.result_indicator.setText(UIMessages.READY_TO_TEST)
        self.result_indicator.setStyleSheet(StyleManager.get_style('indicator_ready'))
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
        if self._should_recreate_scale_controller(port):
            self._close_connection()
            
            try:
                self.scale_controller = ScaleController(baud_rate=self.config.DEFAULT_BAUD_RATE)
                
                if self.scale_controller.connect(port):
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

    def _close_connection(self):
        """Close the scale controller connection."""
        if self.scale_controller:
            self.weight_update_timer.stop()
            self.scale_controller.disconnect()
            self.scale_controller = None
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

    def zero_scale(self):
        """Zero the scale with current weight reading."""
        if not self._can_operate_scale():
            self.logger.warning("Cannot zero scale: scale not connected.")
            return

        current_weight = self.get_adjusted_weight()
        if current_weight is not None:
            self.zero_offset = current_weight
            self.logger.info(f"Scale zeroed. New tare offset: {self.zero_offset:.2f}g")
        else:
            self.logger.warning("Cannot zero scale: no weight reading from scale.")

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
        self.weight_display_label.setText("--- g")
        self.weight_display_label.setStyleSheet(StyleManager.get_style('weight_display_disconnected'))

    def _display_live_weight(self, weight: float):
        """Display live weight reading."""
        self.weight_display_label.setText(f"{weight:.2f} g")
        self.weight_display_label.setStyleSheet(StyleManager.get_style('weight_display_live'))

    def _display_waiting_weight(self):
        """Display waiting state."""
        self.weight_display_label.setText("Waiting...")
        self.weight_display_label.setStyleSheet(StyleManager.get_style('weight_display_waiting'))

    def _display_error_weight(self):
        """Display error state."""
        self.weight_display_label.setText("Error")
        self.weight_display_label.setStyleSheet(StyleManager.get_style('weight_display_waiting'))

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
        self.threshold_label.setText(
            f"{threshold_weight:.1f}g ({percentage:.0f}% of {min_weight:.1f}g min)"
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
            self.result_indicator.setText(UIMessages.READY_TO_TEST)
            self.result_indicator.setStyleSheet(StyleManager.get_style('indicator_ready'))

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
        return all(
            abs(w - current_weight) <= self.config.WEIGHT_STABLE_TOLERANCE_G 
            for w in relevant_weights
        )

    def start_weight_test(self, auto_triggered: bool = False):
        """Start a weight test (manual or auto-triggered)."""
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
        self.result_indicator.setText(UIMessages.TESTING)
        self.result_indicator.setStyleSheet(StyleManager.get_style('indicator_testing'))
        
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
        status_msg = "PASS" if result.passed else "FAIL"
        self.result_indicator.setText(f"TEST {status_msg}")
        
        style = StyleManager.get_style('indicator_pass' if result.passed else 'indicator_fail')
        self.result_indicator.setStyleSheet(style)

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
        error_text = UIMessages.ERROR
        if details:
            error_text += f": {details[:20]}"
        
        self.result_indicator.setText(error_text)
        self.result_indicator.setStyleSheet(StyleManager.get_style('indicator_fail'))

    def stop_weight_test(self):
        """Stop the current weight test."""
        self.is_testing = False
        self.progress_bar.setVisible(False)
        self.auto_test_state = AutoTestState.WAITING
        self.recent_weights.clear()
        
        self.result_indicator.setText(UIMessages.TEST_STOPPED)
        self.result_indicator.setStyleSheet(StyleManager.get_style('indicator_ready'))
        
        self.update_test_button_state()
        self.logger.info(UIMessages.TEST_STOPPED_BY_USER)

    def update_test_button_state(self):
        """Update the state of test control buttons and status display."""
        button_states = self._calculate_button_states()
        
        self.zero_btn.setEnabled(button_states['zero'])
        self.manual_test_btn.setEnabled(button_states['manual_test'])
        self.stop_test_btn.setEnabled(button_states['stop_test'])
        
        self._update_status_label()

    def _calculate_button_states(self) -> Dict[str, bool]:
        """Calculate the enabled state for each button."""
        can_operate = self._can_operate_scale()
        has_sku = bool(self.current_sku)
        
        return {
            'zero': can_operate,
            'manual_test': can_operate and has_sku and not self.is_testing,
            'stop_test': self.is_testing
        }

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
        self.sku_min_label.setText("MIN: ---g")
        self.sku_max_label.setText("MAX: ---g")
        self.threshold_label.setText("---g (80% of min weight)")

    def update_sku_parameter_display(self):
        """Update SKU parameter display."""
        if not self._has_valid_sku_params():
            self.reset_weight_statistics()
            return

        try:
            weight_params = self.cached_sku_params["WEIGHT"]
            min_w = weight_params.get("min_weight_g", 0.0)
            max_w = weight_params.get("max_weight_g", 0.0)
            
            self.sku_min_label.setText(f"MIN: {min_w:.1f}g")
            self.sku_max_label.setText(f"MAX: {max_w:.1f}g")
            
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
