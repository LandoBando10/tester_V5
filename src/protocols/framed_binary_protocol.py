"""
Framed Binary Protocol Implementation

This module implements a concrete protocol class that uses the binary framing
protocol with CRC-16 validation. It extends the BaseProtocol abstract class
to provide a unified interface while using the underlying frame protocol
and serial communication.

Phase 4.2 Implementation - December 2024
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass
from enum import Enum

from .base_protocol import (
    BaseProtocol,
    DeviceType,
    CommandType,
    TestType,
    ErrorSeverity,
    MeasurementResult,
    DeviceStatus,
    ErrorResponse,
    TestConfiguration,
    CommandRequest,
    CommandResponse,
    create_measurement_result,
    create_error_response
)
from .frame_protocol import FrameEncoder, FrameParser, Frame, FrameStats
from ..hardware.serial_manager import SerialManager
from ..utils.crc16 import CRC16


class ProtocolVersion(Enum):
    """Supported protocol versions"""
    TEXT_BASIC = "text_basic"        # Original text-based protocol
    TEXT_WITH_CRC = "text_with_crc"  # Text protocol with CRC-16
    BINARY_FRAMED = "binary_framed"  # Binary framing with CRC-16
    BINARY_ADVANCED = "binary_advanced"  # Future binary protocol with compression


@dataclass
class ProtocolCapabilities:
    """Capabilities detected during protocol negotiation"""
    version: ProtocolVersion
    supports_crc: bool = False
    supports_framing: bool = False
    supports_streaming: bool = False
    supports_binary: bool = False
    firmware_version: Optional[str] = None
    max_frame_size: int = 512
    command_timeout_ms: int = 5000


class ProtocolNegotiator:
    """Handles protocol negotiation and capability detection"""
    
    def __init__(self, serial_manager: SerialManager):
        self.serial = serial_manager
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        
    async def negotiate_protocol(self, device_type: DeviceType) -> ProtocolCapabilities:
        """
        Negotiate the best protocol version with the device.
        
        Args:
            device_type: Type of device to negotiate with
            
        Returns:
            Detected protocol capabilities
        """
        self.logger.info(f"Starting protocol negotiation for {device_type.value}")
        
        # Step 1: Try to get firmware version
        firmware_version = await self._detect_firmware_version()
        
        # Step 2: Test for binary framing support
        supports_framing = await self._test_framing_support()
        
        # Step 3: Test for CRC support
        supports_crc = await self._test_crc_support()
        
        # Step 4: Test for streaming support
        supports_streaming = await self._test_streaming_support()
        
        # Step 5: Determine best protocol version
        protocol_version = self._determine_protocol_version(
            firmware_version, supports_framing, supports_crc
        )
        
        capabilities = ProtocolCapabilities(
            version=protocol_version,
            supports_crc=supports_crc,
            supports_framing=supports_framing,
            supports_streaming=supports_streaming,
            supports_binary=supports_framing,
            firmware_version=firmware_version
        )
        
        self.logger.info(f"Protocol negotiation complete: {protocol_version.value}")
        self.logger.debug(f"Capabilities: CRC={supports_crc}, Framing={supports_framing}, Streaming={supports_streaming}")
        
        return capabilities
    
    async def _detect_firmware_version(self) -> Optional[str]:
        """Detect firmware version"""
        try:
            # Try VERSION command first
            response = await self._send_query("VERSION", timeout=2.0)
            if response:
                self.logger.debug(f"VERSION response: {response}")
                return response.strip()
            
            # Fallback to ID command
            response = await self._send_query("ID", timeout=2.0)
            if response:
                self.logger.debug(f"ID response: {response}")
                return response.strip()
                
            return None
            
        except Exception as e:
            self.logger.warning(f"Error detecting firmware version: {e}")
            return None
    
    async def _test_framing_support(self) -> bool:
        """Test if device supports binary framing"""
        try:
            # Try to send a framed command
            frame_data = FrameEncoder.encode("TST", "FRAME_TEST")
            
            # Send raw frame data
            if self.serial.write_raw(frame_data):
                # Wait for response
                response = await self._read_response(timeout=2.0)
                if response and ("FRAME_OK" in response or "TST" in response):
                    self.logger.debug("Binary framing supported")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Framing test failed: {e}")
            return False
    
    async def _test_crc_support(self) -> bool:
        """Test if device supports CRC-16 validation"""
        try:
            # Try CRC status command
            response = await self._send_query("CRC:STATUS", timeout=2.0)
            if response and ("CRC" in response.upper()):
                self.logger.debug("CRC-16 supported")
                return True
            
            # Check if firmware version indicates CRC support
            response = await self._send_query("VERSION", timeout=2.0)
            if response and ("CRC16_SUPPORT" in response or "5.1.0" in response or "5.2.0" in response):
                self.logger.debug("CRC-16 supported (version check)")
                return True
                
            return False
            
        except Exception as e:
            self.logger.debug(f"CRC test failed: {e}")
            return False
    
    async def _test_streaming_support(self) -> bool:
        """Test if device supports streaming/continuous data"""
        try:
            # Try to start streaming mode
            response = await self._send_query("START_STREAM", timeout=2.0)
            if response and "OK" in response:
                # Stop streaming
                await self._send_query("STOP_STREAM", timeout=1.0)
                return True
                
            return False
            
        except Exception as e:
            self.logger.debug(f"Streaming test failed: {e}")
            return False
    
    def _determine_protocol_version(
        self, 
        firmware_version: Optional[str], 
        supports_framing: bool, 
        supports_crc: bool
    ) -> ProtocolVersion:
        """Determine the best protocol version to use"""
        
        # If framing is supported, use binary framed protocol
        if supports_framing:
            return ProtocolVersion.BINARY_FRAMED
        
        # If CRC is supported but not framing, use text with CRC
        if supports_crc:
            return ProtocolVersion.TEXT_WITH_CRC
        
        # Fallback to basic text protocol
        return ProtocolVersion.TEXT_BASIC
    
    async def _send_query(self, command: str, timeout: float = 2.0) -> Optional[str]:
        """Send a query command and wait for response"""
        try:
            # Use serial manager's query method
            return self.serial.query(command, response_timeout=timeout)
        except Exception as e:
            self.logger.debug(f"Query failed for '{command}': {e}")
            return None
    
    async def _read_response(self, timeout: float = 2.0) -> Optional[str]:
        """Read a response from the device"""
        try:
            return self.serial.read_line(timeout=timeout)
        except Exception as e:
            self.logger.debug(f"Read response failed: {e}")
            return None


class FramedBinaryProtocol(BaseProtocol):
    """
    Concrete implementation of BaseProtocol using binary framing with CRC-16.
    
    This protocol provides:
    - Binary framing with STX/ETX markers
    - CRC-16 validation for message integrity
    - Automatic protocol negotiation
    - Fallback to text protocols for older firmware
    - Performance optimization for high-throughput operations
    """
    
    def __init__(self, device_type: DeviceType, device_id: str, baud_rate: int = 115200):
        super().__init__(device_type, device_id)
        
        self.baud_rate = baud_rate
        self.serial = SerialManager(baud_rate=baud_rate, enable_crc=False, enable_framing=False)
        self.negotiator = ProtocolNegotiator(self.serial)
        self.logger = logging.getLogger(f"{self.__class__.__name__}[{device_id}]")
        
        # Protocol state
        self.capabilities: Optional[ProtocolCapabilities] = None
        self.frame_parser: Optional[FrameParser] = None
        self.frame_stats = FrameStats()
        
        # Command mapping for different device types
        self.command_map = self._build_command_map()
        
        # Performance tracking
        self._last_measurement_time = 0.0
        self._measurement_interval = 0.1  # Minimum interval between measurements
        
    def _build_command_map(self) -> Dict[CommandType, str]:
        """Build device-specific command mapping"""
        if self.device_type == DeviceType.SMT_TESTER:
            return {
                CommandType.CONNECT: "ID",
                CommandType.DISCONNECT: "STOP",
                CommandType.GET_STATUS: "STATUS", 
                CommandType.GET_VERSION: "VERSION",
                CommandType.PING: "PING",
                CommandType.MEASURE: "MEASURE",
                CommandType.SET_RELAY: "RELAY",
                CommandType.START_TEST: "START_TEST",
                CommandType.STOP_TEST: "STOP_TEST",
                CommandType.RESET: "RESET",
                CommandType.ENABLE_CRC: "CRC:ENABLE",
                CommandType.ENABLE_FRAMING: "FRAME:ENABLE"
            }
        elif self.device_type == DeviceType.OFFROAD_TESTER:
            return {
                CommandType.CONNECT: "ID",
                CommandType.DISCONNECT: "STOP",
                CommandType.GET_STATUS: "STATUS",
                CommandType.GET_VERSION: "VERSION", 
                CommandType.PING: "PING",
                CommandType.START_CONTINUOUS: "START_FORWARD",
                CommandType.STOP_CONTINUOUS: "STOP_FORWARD",
                CommandType.SET_PARAMETER: "SET_DUTY_CYCLE",
                CommandType.RESET: "RESET",
                CommandType.ENABLE_CRC: "CRC:ENABLE"
            }
        else:
            # Generic command set
            return {
                CommandType.CONNECT: "CONNECT",
                CommandType.DISCONNECT: "DISCONNECT",
                CommandType.GET_STATUS: "STATUS",
                CommandType.PING: "PING"
            }
    
    async def connect(self, connection_params: Dict[str, Any]) -> bool:
        """
        Connect to the device and negotiate protocol.
        
        Args:
            connection_params: Must contain 'port', optionally 'baud_rate'
            
        Returns:
            True if connection and negotiation successful
        """
        try:
            port = connection_params.get('port')
            if not port:
                self._emit_error(create_error_response(
                    self.device_type, self.device_id,
                    ErrorSeverity.ERROR, "INVALID_PARAMS",
                    "Port parameter required for connection"
                ))
                return False
            
            # Override baud rate if specified
            baud_rate = connection_params.get('baud_rate', self.baud_rate)
            if baud_rate != self.baud_rate:
                self.baud_rate = baud_rate
                self.serial = SerialManager(baud_rate=baud_rate, enable_crc=False, enable_framing=False)
                self.negotiator = ProtocolNegotiator(self.serial)
            
            self.logger.info(f"Connecting to {port} at {baud_rate} baud")
            
            # Step 1: Establish serial connection
            if not self.serial.connect(port):
                self._emit_error(create_error_response(
                    self.device_type, self.device_id,
                    ErrorSeverity.ERROR, "CONNECTION_FAILED",
                    f"Failed to connect to serial port {port}"
                ))
                return False
            
            # Step 2: Negotiate protocol capabilities
            try:
                self.capabilities = await self.negotiator.negotiate_protocol(self.device_type)
            except Exception as e:
                self.logger.error(f"Protocol negotiation failed: {e}")
                # Continue with basic text protocol
                self.capabilities = ProtocolCapabilities(version=ProtocolVersion.TEXT_BASIC)
            
            # Step 3: Configure serial manager based on capabilities
            self._configure_serial_manager()
            
            # Step 4: Initialize frame parser if using framing
            if self.capabilities.supports_framing:
                self.frame_parser = FrameParser()
            
            # Step 5: Update status
            self._connected = True
            self._update_status(
                connected=True,
                firmware_version=self.capabilities.firmware_version,
                current_state="connected"
            )
            
            # Set capabilities in status
            self._status.set_capability("crc_validation", self.capabilities.supports_crc)
            self._status.set_capability("framing", self.capabilities.supports_framing)
            self._status.set_capability("streaming", self.capabilities.supports_streaming)
            self._status.set_capability("binary", self.capabilities.supports_binary)
            
            self.logger.info(f"Connected successfully using {self.capabilities.version.value} protocol")
            return True
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self._emit_error(create_error_response(
                self.device_type, self.device_id,
                ErrorSeverity.ERROR, "CONNECTION_ERROR",
                f"Connection error: {e}"
            ))
            return False
    
    def _configure_serial_manager(self):
        """Configure serial manager based on negotiated capabilities"""
        if self.capabilities:
            self.serial.enable_crc(self.capabilities.supports_crc)
            self.serial.enable_framing(self.capabilities.supports_framing)
            
            self.logger.debug(f"Serial manager configured: CRC={self.capabilities.supports_crc}, "
                            f"Framing={self.capabilities.supports_framing}")
    
    async def disconnect(self) -> bool:
        """Disconnect from the device"""
        try:
            self.logger.info("Disconnecting from device")
            
            # Send disconnect command if connected
            if self._connected:
                try:
                    await self.send_command(CommandRequest(
                        command_type=CommandType.DISCONNECT,
                        device_id=self.device_id,
                        timeout_seconds=2.0
                    ))
                except Exception as e:
                    self.logger.warning(f"Disconnect command failed: {e}")
            
            # Close serial connection
            self.serial.disconnect()
            
            # Update status
            self._connected = False
            self._update_status(
                connected=False,
                current_state="disconnected"
            )
            
            self.logger.info("Disconnected successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Disconnect failed: {e}")
            self._emit_error(create_error_response(
                self.device_type, self.device_id,
                ErrorSeverity.WARNING, "DISCONNECT_ERROR",
                f"Disconnect error: {e}"
            ))
            return False
    
    async def send_command(self, request: CommandRequest) -> CommandResponse:
        """
        Send a command to the device using the negotiated protocol.
        
        Args:
            request: Command request to send
            
        Returns:
            Command response with result data
        """
        start_time = time.time()
        
        try:
            if not self._connected:
                return CommandResponse(
                    request=request,
                    timestamp=time.time(),
                    success=False,
                    error=create_error_response(
                        self.device_type, self.device_id,
                        ErrorSeverity.ERROR, "NOT_CONNECTED",
                        "Device not connected"
                    )
                )
            
            # Map command type to device-specific command
            device_command = self._map_command(request)
            if not device_command:
                return CommandResponse(
                    request=request,
                    timestamp=time.time(),
                    success=False,
                    error=create_error_response(
                        self.device_type, self.device_id,
                        ErrorSeverity.ERROR, "UNSUPPORTED_COMMAND",
                        f"Command {request.command_type.value} not supported"
                    )
                )
            
            # Send command using appropriate protocol
            response_data = await self._send_device_command(device_command, request)
            
            # Create response
            execution_time = (time.time() - start_time) * 1000  # Convert to ms
            
            if response_data is not None:
                response = CommandResponse(
                    request=request,
                    timestamp=time.time(),
                    success=True,
                    data=response_data,
                    execution_time_ms=execution_time
                )
            else:
                response = CommandResponse(
                    request=request,
                    timestamp=time.time(),
                    success=False,
                    error=create_error_response(
                        self.device_type, self.device_id,
                        ErrorSeverity.ERROR, "COMMAND_TIMEOUT",
                        f"Command {request.command_type.value} timed out"
                    ),
                    execution_time_ms=execution_time
                )
            
            # Emit command response event
            self._emit_command_response(response)
            
            return response
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self.logger.error(f"Command {request.command_type.value} failed: {e}")
            
            error_response = CommandResponse(
                request=request,
                timestamp=time.time(),
                success=False,
                error=create_error_response(
                    self.device_type, self.device_id,
                    ErrorSeverity.ERROR, "COMMAND_ERROR",
                    f"Command error: {e}"
                ),
                execution_time_ms=execution_time
            )
            
            self._emit_command_response(error_response)
            return error_response
    
    def _map_command(self, request: CommandRequest) -> Optional[str]:
        """Map CommandType to device-specific command string"""
        base_command = self.command_map.get(request.command_type)
        if not base_command:
            return None
        
        # Add parameters based on command type
        if request.command_type == CommandType.MEASURE:
            relay = request.get_parameter('relay')
            if relay is not None:
                return f"{base_command}:{relay}"
        elif request.command_type == CommandType.SET_RELAY:
            relay = request.get_parameter('relay')
            state = request.get_parameter('state', 'on')
            if relay is not None:
                return f"{base_command}:{relay}:{state}"
        elif request.command_type == CommandType.SET_PARAMETER:
            param = request.get_parameter('parameter')
            value = request.get_parameter('value')
            if param and value is not None:
                return f"{base_command}:{value}"
        
        return base_command
    
    async def _send_device_command(self, command: str, request: CommandRequest) -> Optional[Dict[str, Any]]:
        """Send command using the negotiated protocol"""
        try:
            if self.capabilities and self.capabilities.supports_framing:
                return await self._send_framed_command(command, request)
            else:
                return await self._send_text_command(command, request)
                
        except Exception as e:
            self.logger.error(f"Device command failed: {e}")
            return None
    
    async def _send_framed_command(self, command: str, request: CommandRequest) -> Optional[Dict[str, Any]]:
        """Send command using binary framing protocol"""
        try:
            # Encode command as frame
            frame_type = command[:3].upper().ljust(3)  # Ensure 3 characters
            frame_data = FrameEncoder.encode(frame_type, command[3:] if len(command) > 3 else "")
            
            # Send frame
            if self.serial.write_raw(frame_data):
                # Wait for response
                response = self.serial.read_line(timeout=request.timeout_seconds)
                if response:
                    # Parse response data
                    return self._parse_response(response, request.command_type)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Framed command failed: {e}")
            return None
    
    async def _send_text_command(self, command: str, request: CommandRequest) -> Optional[Dict[str, Any]]:
        """Send command using text protocol"""
        try:
            response = self.serial.query(command, response_timeout=request.timeout_seconds)
            if response:
                return self._parse_response(response, request.command_type)
            return None
            
        except Exception as e:
            self.logger.error(f"Text command failed: {e}")
            return None
    
    def _parse_response(self, response: str, command_type: CommandType) -> Dict[str, Any]:
        """Parse device response into structured data"""
        data = {"raw_response": response.strip()}
        
        # Parse based on command type and response format
        if command_type == CommandType.GET_STATUS:
            if response.startswith("DATA:RELAYS:"):
                # Parse relay status
                relay_data = response[12:]  # Remove "DATA:RELAYS:"
                data["relay_status"] = relay_data
            elif response.startswith("STATUS:"):
                data["status"] = response[7:]
                
        elif command_type == CommandType.MEASURE:
            if response.startswith("MEASUREMENT:"):
                # Parse measurement: MEASUREMENT:1:V=12.500,I=0.450,P=5.625
                parts = response.split(":", 2)
                if len(parts) >= 3:
                    relay = parts[1]
                    measurements = {}
                    for pair in parts[2].split(","):
                        if "=" in pair:
                            key, value = pair.split("=", 1)
                            try:
                                measurements[key] = float(value)
                            except ValueError:
                                measurements[key] = value
                    data["relay"] = relay
                    data["measurements"] = measurements
                    
        elif command_type == CommandType.PING:
            if "PONG" in response.upper():
                data["ping_success"] = True
            else:
                data["ping_success"] = False
                
        elif command_type in [CommandType.GET_VERSION, CommandType.CONNECT]:
            data["version_info"] = response.strip()
        
        return data
    
    async def start_measurement(self, config: TestConfiguration) -> bool:
        """Start a measurement or test based on configuration"""
        try:
            self.logger.info(f"Starting measurement: {config.test_type.value}")
            
            # Create appropriate command based on test type
            if config.test_type == TestType.VOLTAGE_CURRENT:
                relay_list = config.get_parameter('relay_list', [1])
                success_count = 0
                
                for relay in relay_list:
                    request = CommandRequest(
                        command_type=CommandType.MEASURE,
                        device_id=self.device_id,
                        parameters={'relay': relay},
                        timeout_seconds=config.timeout_seconds
                    )
                    
                    response = await self.send_command(request)
                    if response.success and response.data and 'measurements' in response.data:
                        # Emit measurement event
                        measurement = create_measurement_result(
                            device_type=self.device_type,
                            device_id=self.device_id,
                            test_type=config.test_type,
                            measurements=response.data['measurements'],
                            units={'V': 'V', 'I': 'A', 'P': 'W'},
                            metadata={'relay': relay, 'board': config.get_parameter('board', 1)}
                        )
                        self._emit_measurement(measurement)
                        success_count += 1
                    
                    # Throttle measurements
                    await asyncio.sleep(self._measurement_interval)
                
                return success_count > 0
                
            elif config.test_type == TestType.RELAY_CONTINUITY:
                # Test relay continuity
                request = CommandRequest(
                    command_type=CommandType.START_TEST,
                    device_id=self.device_id,
                    parameters={'test_type': 'continuity'},
                    timeout_seconds=config.timeout_seconds
                )
                
                response = await self.send_command(request)
                return response.success
                
            else:
                self.logger.warning(f"Unsupported test type: {config.test_type.value}")
                return False
                
        except Exception as e:
            self.logger.error(f"Start measurement failed: {e}")
            self._emit_error(create_error_response(
                self.device_type, self.device_id,
                ErrorSeverity.ERROR, "MEASUREMENT_ERROR",
                f"Failed to start measurement: {e}"
            ))
            return False
    
    async def stop_measurement(self) -> bool:
        """Stop any ongoing measurement or test"""
        try:
            request = CommandRequest(
                command_type=CommandType.STOP_TEST,
                device_id=self.device_id,
                timeout_seconds=2.0
            )
            
            response = await self.send_command(request)
            return response.success
            
        except Exception as e:
            self.logger.error(f"Stop measurement failed: {e}")
            return False
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Get device capabilities based on negotiated protocol"""
        if not self.capabilities:
            return {}
        
        return {
            "crc_validation": self.capabilities.supports_crc,
            "framing": self.capabilities.supports_framing,
            "streaming": self.capabilities.supports_streaming,
            "binary": self.capabilities.supports_binary,
            "relay_control": self.device_type == DeviceType.SMT_TESTER,
            "continuous_measurement": True,
            "async_commands": True
        }
    
    def get_protocol_info(self) -> Dict[str, Any]:
        """Get information about the active protocol"""
        if not self.capabilities:
            return {"protocol": "unknown"}
        
        return {
            "protocol": self.capabilities.version.value,
            "firmware_version": self.capabilities.firmware_version,
            "capabilities": self.get_capabilities(),
            "frame_stats": {
                "total_frames": self.frame_stats.total_frames,
                "valid_frames": self.frame_stats.valid_frames,
                "error_rate": self.frame_stats.error_rate
            } if self.frame_stats else None
        }
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Get enhanced performance metrics"""
        base_metrics = super().get_performance_metrics()
        
        # Add protocol-specific metrics
        if self.capabilities:
            base_metrics.update({
                "protocol_version": float(hash(self.capabilities.version.value) % 1000),
                "supports_crc": float(self.capabilities.supports_crc),
                "supports_framing": float(self.capabilities.supports_framing)
            })
        
        if self.frame_stats:
            base_metrics.update({
                "frame_error_rate": self.frame_stats.error_rate,
                "total_frames": float(self.frame_stats.total_frames)
            })
        
        return base_metrics


# Factory function for creating protocol instances
def create_protocol(device_type: DeviceType, device_id: str, **kwargs) -> FramedBinaryProtocol:
    """
    Factory function to create a protocol instance.
    
    Args:
        device_type: Type of device
        device_id: Unique device identifier
        **kwargs: Additional configuration (baud_rate, etc.)
        
    Returns:
        Configured protocol instance
    """
    return FramedBinaryProtocol(device_type, device_id, **kwargs)