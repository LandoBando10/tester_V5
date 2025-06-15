"""
Base Protocol Interface for Unified Device Communication

This module defines the abstract base class and common data structures for all
device communication protocols in the Tester V5 system. It provides a unified
interface that abstracts away protocol-specific details while maintaining 
type safety and event-driven architecture.

Phase 4.1 Implementation - December 2024
"""

import enum
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Union, Protocol
from enum import Enum


class DeviceType(Enum):
    """Types of devices supported by the system"""
    SMT_TESTER = "smt_tester"
    OFFROAD_TESTER = "offroad_tester"
    SCALE = "scale"
    PROGRAMMER = "programmer"
    UNKNOWN = "unknown"


class CommandType(Enum):
    """Types of commands that can be sent to devices"""
    # Connection and status
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    GET_STATUS = "get_status"
    GET_VERSION = "get_version"
    PING = "ping"
    
    # Measurement commands
    MEASURE = "measure"
    MEASURE_GROUP = "measure_group"
    START_CONTINUOUS = "start_continuous"
    STOP_CONTINUOUS = "stop_continuous"
    
    # Control commands
    SET_RELAY = "set_relay"
    START_TEST = "start_test"
    STOP_TEST = "stop_test"
    RESET = "reset"
    
    # Configuration commands
    CONFIGURE = "configure"
    SET_PARAMETER = "set_parameter"
    GET_PARAMETER = "get_parameter"
    
    # Protocol commands
    ENABLE_CRC = "enable_crc"
    ENABLE_FRAMING = "enable_framing"
    SET_PROTOCOL = "set_protocol"


class TestType(Enum):
    """Types of tests that can be performed"""
    VOLTAGE_CURRENT = "voltage_current"
    RELAY_CONTINUITY = "relay_continuity"
    BUTTON_TEST = "button_test"
    RGBW_TEST = "rgbw_test"
    FORWARD_VOLTAGE = "forward_voltage"
    WEIGHT_CHECK = "weight_check"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Severity levels for errors"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class MeasurementResult:
    """Container for measurement data from any device"""
    device_type: DeviceType
    device_id: str
    timestamp: float
    test_type: TestType
    measurements: Dict[str, float]
    units: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_data: str = ""
    
    def __post_init__(self):
        """Ensure timestamp is set"""
        if not self.timestamp:
            self.timestamp = time.time()
    
    def get_measurement(self, key: str) -> Optional[float]:
        """Get a specific measurement value"""
        return self.measurements.get(key)
    
    def get_unit(self, key: str) -> Optional[str]:
        """Get the unit for a specific measurement"""
        return self.units.get(key)


@dataclass
class DeviceStatus:
    """Status information for any device"""
    device_type: DeviceType
    device_id: str
    timestamp: float
    connected: bool = False
    firmware_version: Optional[str] = None
    capabilities: Dict[str, bool] = field(default_factory=dict)
    current_state: str = "unknown"
    error_count: int = 0
    last_error: Optional[str] = None
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    
    def __post_init__(self):
        """Ensure timestamp is set"""
        if not self.timestamp:
            self.timestamp = time.time()
    
    def has_capability(self, capability: str) -> bool:
        """Check if device has a specific capability"""
        return self.capabilities.get(capability, False)
    
    def set_capability(self, capability: str, enabled: bool):
        """Set a device capability"""
        self.capabilities[capability] = enabled


@dataclass
class ErrorResponse:
    """Error information from device operations"""
    device_type: DeviceType
    device_id: str
    timestamp: float
    severity: ErrorSeverity
    error_code: str
    error_message: str
    command: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    recoverable: bool = True
    
    def __post_init__(self):
        """Ensure timestamp is set"""
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class TestConfiguration:
    """Configuration for test operations"""
    test_type: TestType
    device_type: DeviceType
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 30.0
    retry_count: int = 3
    enable_logging: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a configuration parameter"""
        return self.parameters.get(key, default)
    
    def set_parameter(self, key: str, value: Any):
        """Set a configuration parameter"""
        self.parameters[key] = value


@dataclass
class CommandRequest:
    """Request for a device command"""
    command_type: CommandType
    device_id: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 5.0
    retry_count: int = 1
    priority: int = 0  # Higher numbers = higher priority
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a command parameter"""
        return self.parameters.get(key, default)


@dataclass
class CommandResponse:
    """Response from a device command"""
    request: CommandRequest
    timestamp: float
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[ErrorResponse] = None
    execution_time_ms: float = 0.0
    
    def __post_init__(self):
        """Ensure timestamp is set"""
        if not self.timestamp:
            self.timestamp = time.time()


# Event callback types
MeasurementCallback = Callable[[MeasurementResult], None]
StatusCallback = Callable[[DeviceStatus], None]
ErrorCallback = Callable[[ErrorResponse], None]
CommandCallback = Callable[[CommandResponse], None]


class ProtocolEventListener(Protocol):
    """Protocol for event listeners"""
    
    def on_measurement(self, measurement: MeasurementResult) -> None:
        """Called when a measurement is received"""
        ...
    
    def on_status_change(self, status: DeviceStatus) -> None:
        """Called when device status changes"""
        ...
    
    def on_error(self, error: ErrorResponse) -> None:
        """Called when an error occurs"""
        ...
    
    def on_command_response(self, response: CommandResponse) -> None:
        """Called when a command response is received"""
        ...


class BaseProtocol(ABC):
    """
    Abstract base class for all device communication protocols.
    
    This class defines the common interface that all protocol implementations
    must follow. It provides unified methods for device communication while
    allowing protocol-specific implementations underneath.
    """
    
    def __init__(self, device_type: DeviceType, device_id: str):
        self.device_type = device_type
        self.device_id = device_id
        self._connected = False
        self._status = DeviceStatus(
            device_type=device_type,
            device_id=device_id,
            timestamp=time.time()
        )
        
        # Event listeners
        self._measurement_listeners: List[MeasurementCallback] = []
        self._status_listeners: List[StatusCallback] = []
        self._error_listeners: List[ErrorCallback] = []
        self._command_listeners: List[CommandCallback] = []
        
        # Performance tracking
        self._command_count = 0
        self._error_count = 0
        self._last_command_time = 0.0
    
    # Abstract methods that must be implemented by subclasses
    
    @abstractmethod
    async def connect(self, connection_params: Dict[str, Any]) -> bool:
        """
        Connect to the device.
        
        Args:
            connection_params: Connection parameters (port, baud_rate, etc.)
            
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Disconnect from the device.
        
        Returns:
            True if disconnection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def send_command(self, request: CommandRequest) -> CommandResponse:
        """
        Send a command to the device.
        
        Args:
            request: Command request to send
            
        Returns:
            Command response with result data
        """
        pass
    
    @abstractmethod
    async def start_measurement(self, config: TestConfiguration) -> bool:
        """
        Start a measurement or test.
        
        Args:
            config: Test configuration
            
        Returns:
            True if measurement started successfully
        """
        pass
    
    @abstractmethod
    async def stop_measurement(self) -> bool:
        """
        Stop any ongoing measurement or test.
        
        Returns:
            True if measurement stopped successfully
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get device capabilities.
        
        Returns:
            Dictionary of capability names and their availability
        """
        pass
    
    # Concrete methods with default implementations
    
    def is_connected(self) -> bool:
        """Check if device is connected"""
        return self._connected
    
    def get_device_type(self) -> DeviceType:
        """Get the device type"""
        return self.device_type
    
    def get_device_id(self) -> str:
        """Get the device ID"""
        return self.device_id
    
    def get_status(self) -> DeviceStatus:
        """Get current device status"""
        return self._status
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Get performance metrics"""
        return {
            "command_count": float(self._command_count),
            "error_count": float(self._error_count),
            "error_rate": self._error_count / max(self._command_count, 1),
            "last_command_time": self._last_command_time
        }
    
    # Event management methods
    
    def add_measurement_listener(self, callback: MeasurementCallback):
        """Add a measurement event listener"""
        if callback not in self._measurement_listeners:
            self._measurement_listeners.append(callback)
    
    def remove_measurement_listener(self, callback: MeasurementCallback):
        """Remove a measurement event listener"""
        if callback in self._measurement_listeners:
            self._measurement_listeners.remove(callback)
    
    def add_status_listener(self, callback: StatusCallback):
        """Add a status change event listener"""
        if callback not in self._status_listeners:
            self._status_listeners.append(callback)
    
    def remove_status_listener(self, callback: StatusCallback):
        """Remove a status change event listener"""
        if callback in self._status_listeners:
            self._status_listeners.remove(callback)
    
    def add_error_listener(self, callback: ErrorCallback):
        """Add an error event listener"""
        if callback not in self._error_listeners:
            self._error_listeners.append(callback)
    
    def remove_error_listener(self, callback: ErrorCallback):
        """Remove an error event listener"""
        if callback in self._error_listeners:
            self._error_listeners.remove(callback)
    
    def add_command_listener(self, callback: CommandCallback):
        """Add a command response event listener"""
        if callback not in self._command_listeners:
            self._command_listeners.append(callback)
    
    def remove_command_listener(self, callback: CommandCallback):
        """Remove a command response event listener"""
        if callback in self._command_listeners:
            self._command_listeners.remove(callback)
    
    # Protected methods for subclasses to emit events
    
    def _emit_measurement(self, measurement: MeasurementResult):
        """Emit a measurement event to all listeners"""
        for listener in self._measurement_listeners:
            try:
                listener(measurement)
            except Exception as e:
                self._emit_error(ErrorResponse(
                    device_type=self.device_type,
                    device_id=self.device_id,
                    timestamp=time.time(),
                    severity=ErrorSeverity.WARNING,
                    error_code="LISTENER_ERROR",
                    error_message=f"Measurement listener error: {e}",
                    recoverable=True
                ))
    
    def _emit_status_change(self, status: DeviceStatus):
        """Emit a status change event to all listeners"""
        self._status = status
        for listener in self._status_listeners:
            try:
                listener(status)
            except Exception as e:
                # Can't emit error through _emit_error here to avoid recursion
                pass
    
    def _emit_error(self, error: ErrorResponse):
        """Emit an error event to all listeners"""
        self._error_count += 1
        for listener in self._error_listeners:
            try:
                listener(error)
            except Exception:
                # Can't emit error here to avoid recursion
                pass
    
    def _emit_command_response(self, response: CommandResponse):
        """Emit a command response event to all listeners"""
        self._command_count += 1
        self._last_command_time = time.time()
        for listener in self._command_listeners:
            try:
                listener(response)
            except Exception as e:
                self._emit_error(ErrorResponse(
                    device_type=self.device_type,
                    device_id=self.device_id,
                    timestamp=time.time(),
                    severity=ErrorSeverity.WARNING,
                    error_code="LISTENER_ERROR",
                    error_message=f"Command listener error: {e}",
                    recoverable=True
                ))
    
    def _update_status(self, **kwargs):
        """Update device status fields"""
        for key, value in kwargs.items():
            if hasattr(self._status, key):
                setattr(self._status, key, value)
        self._status.timestamp = time.time()
        self._emit_status_change(self._status)


# Utility functions for common operations

def create_measurement_result(
    device_type: DeviceType,
    device_id: str,
    test_type: TestType,
    measurements: Dict[str, float],
    units: Optional[Dict[str, str]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> MeasurementResult:
    """Convenience function to create a measurement result"""
    return MeasurementResult(
        device_type=device_type,
        device_id=device_id,
        timestamp=time.time(),
        test_type=test_type,
        measurements=measurements,
        units=units or {},
        metadata=metadata or {}
    )


def create_error_response(
    device_type: DeviceType,
    device_id: str,
    severity: ErrorSeverity,
    error_code: str,
    error_message: str,
    command: Optional[str] = None,
    recoverable: bool = True
) -> ErrorResponse:
    """Convenience function to create an error response"""
    return ErrorResponse(
        device_type=device_type,
        device_id=device_id,
        timestamp=time.time(),
        severity=severity,
        error_code=error_code,
        error_message=error_message,
        command=command,
        recoverable=recoverable
    )


def create_test_configuration(
    test_type: TestType,
    device_type: DeviceType,
    parameters: Optional[Dict[str, Any]] = None,
    timeout_seconds: float = 30.0
) -> TestConfiguration:
    """Convenience function to create a test configuration"""
    return TestConfiguration(
        test_type=test_type,
        device_type=device_type,
        parameters=parameters or {},
        timeout_seconds=timeout_seconds
    )