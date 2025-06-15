"""
Unified Device Controller - Protocol-agnostic interface for device control.

This module provides a unified interface for controlling different device types
(SMT and Offroad) through various protocol implementations. It abstracts away
the protocol-specific details and presents a consistent API to the application.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
import time

from src.protocols.base_protocol import (
    BaseProtocol, CommandRequest, CommandResponse,
    MeasurementResult, DeviceStatus, ErrorResponse,
    DeviceType, CommandType, ErrorSeverity
)
from src.protocols.protocol_manager import ProtocolManager


class DeviceConnectionState(Enum):
    """Device connection states."""
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()
    RECONNECTING = auto()


@dataclass
class DeviceInfo:
    """Information about a connected device."""
    device_type: DeviceType
    port: str
    firmware_version: str = ""
    serial_number: str = ""
    capabilities: Dict[str, bool] = field(default_factory=dict)
    last_seen: datetime = field(default_factory=datetime.now)
    connection_state: DeviceConnectionState = DeviceConnectionState.DISCONNECTED
    error_count: int = 0
    success_count: int = 0
    
    def update_last_seen(self):
        """Update the last seen timestamp."""
        self.last_seen = datetime.now()
    
    def record_success(self):
        """Record a successful operation."""
        self.success_count += 1
        self.update_last_seen()
    
    def record_error(self):
        """Record an error."""
        self.error_count += 1
        self.update_last_seen()
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.error_count
        return self.success_count / total if total > 0 else 0.0


class UnifiedDeviceController:
    """
    Unified controller for all device types.
    
    Provides a protocol-agnostic interface for device control,
    automatic device detection, and transparent protocol negotiation.
    """
    
    def __init__(self, protocol_manager: Optional[ProtocolManager] = None):
        """
        Initialize the unified device controller.
        
        Args:
            protocol_manager: Protocol manager instance (uses global if not provided)
        """
        self.logger = logging.getLogger(__name__)
        self.protocol_manager = protocol_manager or ProtocolManager()
        self.devices: Dict[str, DeviceInfo] = {}
        self.protocols: Dict[str, BaseProtocol] = {}
        self._connection_callbacks: List[Callable[[str, DeviceConnectionState], None]] = []
        self._command_callbacks: List[Callable[[str, CommandRequest, CommandResponse], None]] = []
        self._error_callbacks: List[Callable[[str, ErrorResponse], None]] = []
        
    def _create_error_response(self, port: str, command: str, command_type: CommandType,
                             error_code: str, error_message: str,
                             params: Optional[Dict[str, Any]] = None,
                             timeout: float = 5.0) -> CommandResponse:
        """Create an error response with all required fields."""
        device_info = self.devices.get(port, DeviceInfo(DeviceType.UNKNOWN, port))
        request = CommandRequest(
            command_type=command_type,
            command=command,
            parameters=params or {},
            timeout=timeout
        )
        return CommandResponse(
            request=request,
            timestamp=time.time(),
            success=False,
            error=ErrorResponse(
                device_type=device_info.device_type,
                device_id=port,
                timestamp=time.time(),
                severity=ErrorSeverity.ERROR,
                error_code=error_code,
                error_message=error_message
            )
        )
        
    def add_connection_callback(self, callback: Callable[[str, DeviceConnectionState], None]):
        """Add a callback for connection state changes."""
        self._connection_callbacks.append(callback)
        
    def remove_connection_callback(self, callback: Callable[[str, DeviceConnectionState], None]):
        """Remove a connection state callback."""
        if callback in self._connection_callbacks:
            self._connection_callbacks.remove(callback)
            
    def add_command_callback(self, callback: Callable[[str, CommandRequest, CommandResponse], None]):
        """Add a callback for command execution."""
        self._command_callbacks.append(callback)
        
    def remove_command_callback(self, callback: Callable[[str, CommandRequest, CommandResponse], None]):
        """Remove a command execution callback."""
        if callback in self._command_callbacks:
            self._command_callbacks.remove(callback)
            
    def add_error_callback(self, callback: Callable[[str, ErrorResponse], None]):
        """Add a callback for errors."""
        self._error_callbacks.append(callback)
        
    def remove_error_callback(self, callback: Callable[[str, ErrorResponse], None]):
        """Remove an error callback."""
        if callback in self._error_callbacks:
            self._error_callbacks.remove(callback)
            
    def _notify_connection_change(self, port: str, state: DeviceConnectionState):
        """Notify callbacks of connection state change."""
        for callback in self._connection_callbacks:
            try:
                callback(port, state)
            except Exception as e:
                self.logger.error(f"Error in connection callback: {e}")
                
    def _notify_command_execution(self, port: str, request: CommandRequest, response: CommandResponse):
        """Notify callbacks of command execution."""
        for callback in self._command_callbacks:
            try:
                callback(port, request, response)
            except Exception as e:
                self.logger.error(f"Error in command callback: {e}")
                
    def _notify_error(self, port: str, error: ErrorResponse):
        """Notify callbacks of errors."""
        for callback in self._error_callbacks:
            try:
                callback(port, error)
            except Exception as e:
                self.logger.error(f"Error in error callback: {e}")
                
    async def connect_device(self, port: str, device_type: Optional[DeviceType] = None) -> bool:
        """
        Connect to a device on the specified port.
        
        Args:
            port: Serial port path
            device_type: Device type hint (auto-detected if not provided)
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Update connection state
            if port in self.devices:
                self.devices[port].connection_state = DeviceConnectionState.CONNECTING
            else:
                self.devices[port] = DeviceInfo(
                    device_type=device_type or DeviceType.UNKNOWN,
                    port=port,
                    connection_state=DeviceConnectionState.CONNECTING
                )
            self._notify_connection_change(port, DeviceConnectionState.CONNECTING)
            
            # Get or create protocol
            protocol = await self.protocol_manager.create_protocol(
                device_type=device_type or DeviceType.UNKNOWN,
                device_id=port,
                connection_params={'port': port, 'baud_rate': 115200}
            )
            if not protocol:
                raise Exception("Failed to negotiate protocol")
                
            self.protocols[port] = protocol
            
            # Detect device type if not provided
            if not device_type:
                device_type = await self._detect_device_type(protocol)
                
            # Update device info
            device_info = self.devices[port]
            device_info.device_type = device_type
            device_info.firmware_version = await self._get_firmware_version(protocol)
            device_info.capabilities = protocol.get_capabilities()
            device_info.connection_state = DeviceConnectionState.CONNECTED
            device_info.update_last_seen()
            
            # Register protocol event handlers
            protocol.add_event_listener('error', lambda e: self._handle_protocol_error(port, e))
            protocol.add_event_listener('status', lambda s: self._handle_protocol_status(port, s))
            
            self._notify_connection_change(port, DeviceConnectionState.CONNECTED)
            self.logger.info(f"Connected to {device_type.name} device on {port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to device on {port}: {e}")
            if port in self.devices:
                self.devices[port].connection_state = DeviceConnectionState.ERROR
                self.devices[port].record_error()
            self._notify_connection_change(port, DeviceConnectionState.ERROR)
            return False
            
    async def disconnect_device(self, port: str):
        """
        Disconnect from a device.
        
        Args:
            port: Serial port path
        """
        if port in self.protocols:
            try:
                await self.protocols[port].disconnect()
                del self.protocols[port]
            except Exception as e:
                self.logger.error(f"Error disconnecting from {port}: {e}")
                
        if port in self.devices:
            self.devices[port].connection_state = DeviceConnectionState.DISCONNECTED
            self._notify_connection_change(port, DeviceConnectionState.DISCONNECTED)
            
    async def _detect_device_type(self, protocol: BaseProtocol) -> DeviceType:
        """
        Auto-detect the device type.
        
        Args:
            protocol: Protocol instance
            
        Returns:
            Detected device type
        """
        try:
            # Try SMT-specific command
            response = await protocol.execute_command(
                CommandRequest(
                    command_type=CommandType.QUERY,
                    command="GET_BOARD_TYPE",
                    timeout=2.0
                )
            )
            
            if response.success and "BOARD_TYPE" in response.data.get('response', ''):
                return DeviceType.SMT_TESTER
                
            # Try Offroad-specific command
            response = await protocol.execute_command(
                CommandRequest(
                    command_type=CommandType.QUERY,
                    command="GET_STATUS",
                    timeout=2.0
                )
            )
            
            if response.success and any(key in response.data for key in ['state', 'duty_cycle']):
                return DeviceType.OFFROAD_TESTER
                
        except Exception as e:
            self.logger.debug(f"Device detection failed: {e}")
            
        return DeviceType.UNKNOWN
        
    async def _get_firmware_version(self, protocol: BaseProtocol) -> str:
        """
        Get the firmware version from the device.
        
        Args:
            protocol: Protocol instance
            
        Returns:
            Firmware version string
        """
        try:
            response = await protocol.execute_command(
                CommandRequest(
                    command_type=CommandType.QUERY,
                    command="VERSION",
                    timeout=2.0
                )
            )
            
            if response.success:
                return response.data.get('version', 'Unknown')
                
        except Exception as e:
            self.logger.debug(f"Failed to get firmware version: {e}")
            
        return "Unknown"
        
    def _handle_protocol_error(self, port: str, error: ErrorResponse):
        """Handle protocol errors."""
        if port in self.devices:
            self.devices[port].record_error()
        self._notify_error(port, error)
        
    def _handle_protocol_status(self, port: str, status: DeviceStatus):
        """Handle protocol status updates."""
        if port in self.devices:
            self.devices[port].update_last_seen()
            
    async def execute_command(self, port: str, command: str, 
                            params: Optional[Dict[str, Any]] = None,
                            timeout: float = 5.0) -> CommandResponse:
        """
        Execute a command on a device.
        
        Args:
            port: Serial port path
            command: Command to execute
            params: Command parameters
            timeout: Command timeout
            
        Returns:
            Command response
        """
        if port not in self.protocols:
            return self._create_error_response(
                port, command, CommandType.MEASURE,
                "NOT_CONNECTED", f"Device not connected on {port}",
                params, timeout
            )
            
        try:
            # Build command request
            request = CommandRequest(
                command_type=CommandType.MEASURE,
                command=command,
                parameters=params or {},
                timeout=timeout
            )
            
            # Execute command
            response = await self.protocols[port].execute_command(request)
            
            # Update device stats
            if port in self.devices:
                if response.success:
                    self.devices[port].record_success()
                else:
                    self.devices[port].record_error()
                    
            # Notify callbacks
            self._notify_command_execution(port, request, response)
            
            return response
            
        except Exception as e:
            self.logger.error(f"Command execution failed: {e}")
            error_response = self._create_error_response(
                port, command, CommandType.MEASURE,
                "EXECUTION_ERROR", str(e),
                params, timeout
            )
            
            if port in self.devices:
                self.devices[port].record_error()
                
            self._notify_command_execution(port, request, error_response)
            return error_response
            
    async def query_device(self, port: str, query: str, timeout: float = 3.0) -> CommandResponse:
        """
        Query a device for information.
        
        Args:
            port: Serial port path
            query: Query command
            timeout: Query timeout
            
        Returns:
            Query response
        """
        if port not in self.protocols:
            return self._create_error_response(
                port, query, CommandType.GET_STATUS,
                "NOT_CONNECTED", f"Device not connected on {port}",
                {}, timeout
            )
            
        request = CommandRequest(
            command_type=CommandType.GET_STATUS,
            command=query,
            timeout=timeout
        )
        
        return await self.protocols[port].execute_command(request)
        
    async def measure_relays(self, port: str, relay_list: List[int]) -> Dict[int, MeasurementResult]:
        """
        Measure multiple relays on an SMT device.
        
        Args:
            port: Serial port path
            relay_list: List of relay numbers to measure
            
        Returns:
            Dictionary mapping relay numbers to measurements
        """
        if port not in self.devices or self.devices[port].device_type != DeviceType.SMT_TESTER:
            raise ValueError(f"Device on {port} is not an SMT tester")
            
        results = {}
        
        for relay in relay_list:
            try:
                response = await self.execute_command(
                    port,
                    "MEASURE",
                    {"relay": relay},
                    timeout=2.0
                )
                
                if response.success and 'measurement' in response.data:
                    results[relay] = response.data['measurement']
                else:
                    self.logger.warning(f"Failed to measure relay {relay}")
                    
            except Exception as e:
                self.logger.error(f"Error measuring relay {relay}: {e}")
                
        return results
        
    async def start_test(self, port: str, test_type: str, 
                        params: Optional[Dict[str, Any]] = None) -> bool:
        """
        Start a test on a device.
        
        Args:
            port: Serial port path
            test_type: Type of test to start
            params: Test parameters
            
        Returns:
            True if test started successfully
        """
        response = await self.execute_command(
            port,
            "START_TEST",
            {"test_type": test_type, **(params or {})},
            timeout=5.0
        )
        
        return response.success
        
    async def stop_test(self, port: str) -> bool:
        """
        Stop the current test on a device.
        
        Args:
            port: Serial port path
            
        Returns:
            True if test stopped successfully
        """
        response = await self.execute_command(port, "STOP_TEST", timeout=3.0)
        return response.success
        
    def get_device_info(self, port: str) -> Optional[DeviceInfo]:
        """
        Get information about a connected device.
        
        Args:
            port: Serial port path
            
        Returns:
            Device information or None if not connected
        """
        return self.devices.get(port)
        
    def get_connected_devices(self) -> List[DeviceInfo]:
        """
        Get list of all connected devices.
        
        Returns:
            List of connected device information
        """
        return [
            info for info in self.devices.values()
            if info.connection_state == DeviceConnectionState.CONNECTED
        ]
        
    def is_connected(self, port: str) -> bool:
        """
        Check if a device is connected.
        
        Args:
            port: Serial port path
            
        Returns:
            True if device is connected
        """
        return (
            port in self.devices and
            self.devices[port].connection_state == DeviceConnectionState.CONNECTED
        )
        
    async def reconnect_device(self, port: str) -> bool:
        """
        Attempt to reconnect to a device.
        
        Args:
            port: Serial port path
            
        Returns:
            True if reconnection successful
        """
        if port not in self.devices:
            return False
            
        device_info = self.devices[port]
        device_info.connection_state = DeviceConnectionState.RECONNECTING
        self._notify_connection_change(port, DeviceConnectionState.RECONNECTING)
        
        # Disconnect first
        await self.disconnect_device(port)
        
        # Wait a bit
        await asyncio.sleep(0.5)
        
        # Try to reconnect
        return await self.connect_device(port, device_info.device_type)
        
    def get_device_statistics(self, port: str) -> Optional[Dict[str, Any]]:
        """
        Get device statistics.
        
        Args:
            port: Serial port path
            
        Returns:
            Device statistics or None if not connected
        """
        if port not in self.devices:
            return None
            
        device_info = self.devices[port]
        protocol = self.protocols.get(port)
        
        stats = {
            'device_type': device_info.device_type.name,
            'firmware_version': device_info.firmware_version,
            'connection_state': device_info.connection_state.name,
            'success_count': device_info.success_count,
            'error_count': device_info.error_count,
            'success_rate': device_info.success_rate,
            'last_seen': device_info.last_seen.isoformat(),
            'capabilities': device_info.capabilities
        }
        
        if protocol:
            stats['protocol_metrics'] = protocol.get_metrics()
            
        return stats