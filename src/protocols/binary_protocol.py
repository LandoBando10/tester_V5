"""
Binary Protocol Implementation for Phase 4.4

This module implements the true binary protocol with advanced message formatting,
encoding/decoding capabilities, and integration with the existing protocol framework.

Features:
- Binary message serialization with custom format
- CRC-16 validation for message integrity  
- Optional compression for large payloads
- Schema validation for type safety
- Performance optimization for Arduino communication

Phase 4.4 Implementation - Binary Protocol with Advanced Serialization
"""

import asyncio
import time
import zlib
from typing import Dict, Any, Optional, List, Union, Callable
from dataclasses import dataclass
import logging

from .base_protocol import (
    BaseProtocol, DeviceType, CommandType, TestType, ErrorSeverity,
    MeasurementResult, DeviceStatus, ErrorResponse, CommandRequest, CommandResponse,
    TestConfiguration, create_measurement_result, create_error_response
)
from .binary_message_formats import (
    BinaryMessage, BinaryMessageHeader, MessageType, MessageFlags, ErrorCode,
    PingMessage, PingResponseMessage, MeasureMessage, MeasureResponseMessage,
    MeasureGroupMessage, MeasureGroupResponseMessage, StatusResponseMessage,
    ErrorMessage, create_ping_message, create_measure_message, create_measure_group_message
)
from ..hardware.serial_manager import SerialManager

logger = logging.getLogger(__name__)


class BinaryProtocolConfig:
    """Configuration for binary protocol"""
    
    def __init__(self):
        self.enable_compression = False  # Disabled by default for Arduino compatibility
        self.compression_threshold = 256  # Compress payloads larger than this
        self.enable_acknowledgments = False  # Disabled by default for simplicity
        self.max_retries = 3
        self.response_timeout = 5.0  # seconds
        self.ping_interval = 30.0  # seconds
        self.max_concurrent_commands = 1  # Arduino can only handle one command at a time


@dataclass
class PendingCommand:
    """Tracks a command waiting for response"""
    request: CommandRequest
    message: BinaryMessage
    timestamp: float
    future: asyncio.Future
    retry_count: int = 0


class BinaryMessageCodec:
    """Handles encoding and decoding of binary messages"""
    
    def __init__(self, config: BinaryProtocolConfig):
        self.config = config
        self._sequence_counter = 0
    
    def get_next_sequence(self) -> int:
        """Get next sequence number"""
        self._sequence_counter = (self._sequence_counter + 1) % 0xFFFFFFFF
        return self._sequence_counter
    
    def encode_message(self, message: BinaryMessage) -> bytes:
        """
        Encode a binary message with optional compression.
        
        Args:
            message: Binary message to encode
            
        Returns:
            Encoded message bytes
        """
        try:
            # Pack the message
            data = message.pack()
            
            # Apply compression if enabled and threshold met
            if (self.config.enable_compression and 
                len(data) > self.config.compression_threshold):
                compressed_data = zlib.compress(data, level=1)  # Fast compression
                
                # Only use compression if it actually saves space
                if len(compressed_data) < len(data):
                    message.header.flags |= MessageFlags.COMPRESSED
                    data = compressed_data
                    logger.debug(f"Compressed message: {len(data)} -> {len(compressed_data)} bytes")
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to encode message: {e}")
            raise
    
    def decode_message(self, data: bytes) -> BinaryMessage:
        """
        Decode a binary message with optional decompression.
        
        Args:
            data: Raw message bytes
            
        Returns:
            Decoded binary message
        """
        try:
            # Check if message is compressed
            if len(data) >= 8:  # Minimum header size
                header = BinaryMessageHeader.unpack(data[:8])
                
                if header.flags & MessageFlags.COMPRESSED:
                    # Decompress the entire message
                    data = zlib.decompress(data)
                    logger.debug(f"Decompressed message: {len(data)} bytes")
            
            # Unpack the message
            return BinaryMessage.unpack(data)
            
        except Exception as e:
            logger.error(f"Failed to decode message: {e}")
            raise
    
    def command_to_message(self, request: CommandRequest) -> BinaryMessage:
        """
        Convert a CommandRequest to appropriate BinaryMessage.
        
        Args:
            request: Command request to convert
            
        Returns:
            Binary message for the command
        """
        command_type = request.command_type
        
        if command_type == CommandType.PING:
            return create_ping_message(self.get_next_sequence())
        
        elif command_type == CommandType.MEASURE:
            relay_id = request.get_parameter('relay_id', 0)
            test_type_str = request.get_parameter('test_type', 'voltage_current')
            test_type = self._string_to_test_type(test_type_str)
            return create_measure_message(relay_id, test_type)
        
        elif command_type == CommandType.MEASURE_GROUP:
            relay_ids = request.get_parameter('relay_ids', [])
            test_type_str = request.get_parameter('test_type', 'voltage_current')
            test_type = self._string_to_test_type(test_type_str)
            return create_measure_group_message(relay_ids, test_type)
        
        elif command_type == CommandType.GET_STATUS:
            return BinaryMessage()  # Basic status request
        
        else:
            raise ValueError(f"Unsupported command type: {command_type}")
    
    def message_to_response(self, message: BinaryMessage, request: CommandRequest) -> CommandResponse:
        """
        Convert a BinaryMessage response to CommandResponse.
        
        Args:
            message: Binary message response
            request: Original command request
            
        Returns:
            Command response
        """
        success = True
        data = {}
        error = None
        
        if isinstance(message, ErrorMessage):
            success = False
            error = create_error_response(
                device_type=DeviceType.SMT_TESTER,  # TODO: Make this configurable
                device_id=request.device_id,
                severity=ErrorSeverity.ERROR,
                error_code=f"BINARY_{message.error_code.name}",
                error_message=message.error_message,
                command=request.command_type.value
            )
        
        elif isinstance(message, PingResponseMessage):
            data = {
                'sequence_id': message.sequence_id,
                'device_id': message.device_id,
                'latency_ms': (time.time() - message.timestamp) * 1000
            }
        
        elif isinstance(message, MeasureResponseMessage):
            data = {
                'relay_id': message.relay_id,
                'test_type': message.test_type.name.lower(),
                'voltage': message.voltage,
                'current': message.current,
                'success': message.error_code == ErrorCode.SUCCESS
            }
            
            if message.error_code != ErrorCode.SUCCESS:
                success = False
                error = create_error_response(
                    device_type=DeviceType.SMT_TESTER,
                    device_id=request.device_id,
                    severity=ErrorSeverity.ERROR,
                    error_code=f"MEASURE_{message.error_code.name}",
                    error_message=f"Measurement failed for relay {message.relay_id}"
                )
        
        elif isinstance(message, MeasureGroupResponseMessage):
            data = {
                'measurements': message.measurements,
                'success': message.error_code == ErrorCode.SUCCESS
            }
            
            if message.error_code != ErrorCode.SUCCESS:
                success = False
                error = create_error_response(
                    device_type=DeviceType.SMT_TESTER,
                    device_id=request.device_id,
                    severity=ErrorSeverity.ERROR,
                    error_code=f"MEASURE_GROUP_{message.error_code.name}",
                    error_message="Group measurement failed"
                )
        
        elif isinstance(message, StatusResponseMessage):
            data = {
                'device_id': message.device_id,
                'firmware_version': message.firmware_version,
                'connected': message.connected,
                'current_state': message.current_state,
                'error_count': message.error_count
            }
        
        return CommandResponse(
            request=request,
            timestamp=time.time(),
            success=success,
            data=data,
            error=error
        )
    
    def _string_to_test_type(self, test_type_str: str) -> 'TestType':
        """Convert string test type to TestType enum"""
        test_type_map = {
            'voltage_current': TestType.VOLTAGE_CURRENT,
            'relay_continuity': TestType.RELAY_CONTINUITY,
            'button_test': TestType.BUTTON_TEST,
            'rgbw_test': TestType.RGBW_TEST,
            'forward_voltage': TestType.FORWARD_VOLTAGE,
            'weight_check': TestType.WEIGHT_CHECK
        }
        return test_type_map.get(test_type_str, TestType.UNKNOWN)


class BinaryProtocol(BaseProtocol):
    """
    Binary protocol implementation with advanced serialization.
    
    This protocol uses efficient binary message formats with CRC validation,
    optional compression, and type-safe serialization for optimal performance
    with Arduino devices.
    """
    
    def __init__(self, device_type: DeviceType, device_id: str, 
                 serial_manager: Optional[SerialManager] = None,
                 config: Optional[BinaryProtocolConfig] = None):
        super().__init__(device_type, device_id)
        
        self.serial_manager = serial_manager
        self.config = config or BinaryProtocolConfig()
        self.codec = BinaryMessageCodec(self.config)
        
        # Command tracking
        self._pending_commands: Dict[int, PendingCommand] = {}
        self._command_lock = asyncio.Lock()
        
        # Background tasks
        self._receive_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None
        
        # Statistics
        self._stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'messages_failed': 0,
            'bytes_sent': 0,
            'bytes_received': 0,
            'compression_ratio': 0.0,
            'average_latency_ms': 0.0
        }
    
    async def connect(self, connection_params: Dict[str, Any]) -> bool:
        """
        Connect to the device using binary protocol.
        
        Args:
            connection_params: Connection parameters for SerialManager
            
        Returns:
            True if connection successful
        """
        try:
            if not self.serial_manager:
                self.serial_manager = SerialManager()
            
            # Connect to device
            success = await asyncio.to_thread(
                self.serial_manager.connect,
                connection_params.get('port'),
                connection_params.get('baud_rate', 115200)
            )
            
            if success:
                self._connected = True
                
                # Start background tasks
                self._receive_task = asyncio.create_task(self._receive_loop())
                if self.config.ping_interval > 0:
                    self._ping_task = asyncio.create_task(self._ping_loop())
                
                # Update status
                self._update_status(
                    connected=True,
                    current_state="connected",
                    firmware_version="unknown"
                )
                
                # Send initial ping to verify communication
                ping_request = CommandRequest(
                    command_type=CommandType.PING,
                    device_id=self.device_id,
                    timeout_seconds=2.0
                )
                
                try:
                    response = await self.send_command(ping_request)
                    if response.success:
                        logger.info(f"Binary protocol connected to {self.device_id}")
                    else:
                        logger.warning(f"Initial ping failed: {response.error}")
                except Exception as e:
                    logger.warning(f"Initial ping failed: {e}")
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to connect binary protocol: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """
        Disconnect from the device.
        
        Returns:
            True if disconnection successful
        """
        try:
            self._connected = False
            
            # Cancel background tasks
            if self._receive_task:
                self._receive_task.cancel()
                try:
                    await self._receive_task
                except asyncio.CancelledError:
                    pass
            
            if self._ping_task:
                self._ping_task.cancel()
                try:
                    await self._ping_task
                except asyncio.CancelledError:
                    pass
            
            # Cancel pending commands
            for pending in self._pending_commands.values():
                if not pending.future.done():
                    pending.future.cancel()
            self._pending_commands.clear()
            
            # Disconnect serial
            if self.serial_manager:
                await asyncio.to_thread(self.serial_manager.disconnect)
            
            # Update status
            self._update_status(
                connected=False,
                current_state="disconnected"
            )
            
            logger.info(f"Binary protocol disconnected from {self.device_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to disconnect binary protocol: {e}")
            return False
    
    async def send_command(self, request: CommandRequest) -> CommandResponse:
        """
        Send a command to the device using binary protocol.
        
        Args:
            request: Command request to send
            
        Returns:
            Command response
        """
        if not self._connected or not self.serial_manager:
            return CommandResponse(
                request=request,
                timestamp=time.time(),
                success=False,
                error=create_error_response(
                    device_type=self.device_type,
                    device_id=self.device_id,
                    severity=ErrorSeverity.ERROR,
                    error_code="NOT_CONNECTED",
                    error_message="Device not connected"
                )
            )
        
        async with self._command_lock:
            try:
                # Convert request to binary message
                message = self.codec.command_to_message(request)
                
                # Create pending command tracker
                command_id = id(message)  # Use object ID as unique identifier
                future = asyncio.Future()
                
                pending = PendingCommand(
                    request=request,
                    message=message,
                    timestamp=time.time(),
                    future=future
                )
                
                self._pending_commands[command_id] = pending
                
                try:
                    # Encode and send message
                    encoded_data = self.codec.encode_message(message)
                    
                    success = await asyncio.to_thread(
                        self.serial_manager.send_data,
                        encoded_data
                    )
                    
                    if not success:
                        raise RuntimeError("Failed to send data")
                    
                    # Update statistics
                    self._stats['messages_sent'] += 1
                    self._stats['bytes_sent'] += len(encoded_data)
                    
                    # Wait for response
                    try:
                        response = await asyncio.wait_for(
                            future,
                            timeout=request.timeout_seconds
                        )
                        return response
                        
                    except asyncio.TimeoutError:
                        self._stats['messages_failed'] += 1
                        return CommandResponse(
                            request=request,
                            timestamp=time.time(),
                            success=False,
                            error=create_error_response(
                                device_type=self.device_type,
                                device_id=self.device_id,
                                severity=ErrorSeverity.ERROR,
                                error_code="TIMEOUT",
                                error_message=f"Command timeout after {request.timeout_seconds}s"
                            )
                        )
                
                finally:
                    # Clean up pending command
                    self._pending_commands.pop(command_id, None)
                
            except Exception as e:
                self._stats['messages_failed'] += 1
                logger.error(f"Failed to send command: {e}")
                
                return CommandResponse(
                    request=request,
                    timestamp=time.time(),
                    success=False,
                    error=create_error_response(
                        device_type=self.device_type,
                        device_id=self.device_id,
                        severity=ErrorSeverity.ERROR,
                        error_code="SEND_ERROR",
                        error_message=str(e)
                    )
                )
    
    async def start_measurement(self, config: TestConfiguration) -> bool:
        """
        Start a measurement using binary protocol.
        
        Args:
            config: Test configuration
            
        Returns:
            True if measurement started successfully
        """
        # For binary protocol, measurements are typically single commands
        # rather than continuous streams, so we'll implement this as a 
        # single measurement request
        
        try:
            relay_ids = config.get_parameter('relay_ids', [1])
            
            if len(relay_ids) == 1:
                # Single measurement
                request = CommandRequest(
                    command_type=CommandType.MEASURE,
                    device_id=self.device_id,
                    parameters={
                        'relay_id': relay_ids[0],
                        'test_type': config.test_type.value
                    },
                    timeout_seconds=config.timeout_seconds
                )
            else:
                # Group measurement
                request = CommandRequest(
                    command_type=CommandType.MEASURE_GROUP,
                    device_id=self.device_id,
                    parameters={
                        'relay_ids': relay_ids,
                        'test_type': config.test_type.value
                    },
                    timeout_seconds=config.timeout_seconds
                )
            
            response = await self.send_command(request)
            
            if response.success:
                # Convert response to measurement result and emit
                if 'measurements' in response.data:
                    # Group measurement
                    for measurement_data in response.data['measurements']:
                        measurement = create_measurement_result(
                            device_type=self.device_type,
                            device_id=self.device_id,
                            test_type=config.test_type,
                            measurements={
                                'voltage': measurement_data['voltage'],
                                'current': measurement_data['current']
                            },
                            units={'voltage': 'V', 'current': 'A'},
                            metadata={'relay_id': measurement_data['relay_id']}
                        )
                        self._emit_measurement(measurement)
                else:
                    # Single measurement
                    measurement = create_measurement_result(
                        device_type=self.device_type,
                        device_id=self.device_id,
                        test_type=config.test_type,
                        measurements={
                            'voltage': response.data['voltage'],
                            'current': response.data['current']
                        },
                        units={'voltage': 'V', 'current': 'A'},
                        metadata={'relay_id': response.data['relay_id']}
                    )
                    self._emit_measurement(measurement)
            
            return response.success
            
        except Exception as e:
            logger.error(f"Failed to start measurement: {e}")
            return False
    
    async def stop_measurement(self) -> bool:
        """
        Stop any ongoing measurement.
        
        Returns:
            True if measurement stopped successfully
        """
        # For binary protocol with single-shot measurements,
        # there's typically nothing to stop
        return True
    
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get device capabilities for binary protocol.
        
        Returns:
            Dictionary of capability names and their availability
        """
        return {
            'binary_protocol': True,
            'crc_validation': True,
            'compression': self.config.enable_compression,
            'acknowledgments': self.config.enable_acknowledgments,
            'group_measurements': True,
            'single_measurements': True,
            'ping': True,
            'status_query': True,
            'error_reporting': True
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get protocol statistics"""
        return self._stats.copy()
    
    async def _receive_loop(self):
        """Background task to receive and process incoming messages"""
        buffer = bytearray()
        
        while self._connected:
            try:
                # Read data from serial
                data = await asyncio.to_thread(
                    self.serial_manager.read_data,
                    timeout=0.1  # Small timeout to avoid blocking
                )
                
                if data:
                    buffer.extend(data)
                    self._stats['bytes_received'] += len(data)
                    
                    # Try to decode complete messages
                    while len(buffer) >= 8:  # Minimum message size
                        try:
                            # Try to decode a message
                            message = self.codec.decode_message(bytes(buffer))
                            
                            # Calculate message size and remove from buffer
                            message_size = len(message.pack())
                            buffer = buffer[message_size:]
                            
                            self._stats['messages_received'] += 1
                            
                            # Process the message
                            await self._process_received_message(message)
                            
                        except Exception as e:
                            # If decode fails, remove one byte and try again
                            # This handles cases where we're not aligned to message boundaries
                            buffer = buffer[1:]
                            if len(buffer) == 0:
                                break
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.001)
                
            except Exception as e:
                if self._connected:  # Only log if we're supposed to be connected
                    logger.error(f"Error in receive loop: {e}")
                await asyncio.sleep(0.1)
    
    async def _process_received_message(self, message: BinaryMessage):
        """Process a received binary message"""
        try:
            # Find matching pending command
            command_id = None
            pending = None
            
            # For responses, we need to match them to pending commands
            # This is a simplified approach - in a full implementation,
            # we might use sequence numbers or other correlation methods
            
            if self._pending_commands:
                # Take the oldest pending command for now
                # TODO: Implement proper message correlation
                command_id = next(iter(self._pending_commands))
                pending = self._pending_commands[command_id]
            
            if pending and not pending.future.done():
                # Convert message to response
                response = self.codec.message_to_response(message, pending.request)
                
                # Calculate latency
                latency_ms = (time.time() - pending.timestamp) * 1000
                self._stats['average_latency_ms'] = (
                    self._stats['average_latency_ms'] * 0.9 + latency_ms * 0.1
                )
                
                # Complete the future
                pending.future.set_result(response)
                
                # Emit command response event
                self._emit_command_response(response)
            
            else:
                # Unsolicited message (e.g., status update, error)
                if isinstance(message, ErrorMessage):
                    error = create_error_response(
                        device_type=self.device_type,
                        device_id=self.device_id,
                        severity=ErrorSeverity.ERROR,
                        error_code=message.error_code.name,
                        error_message=message.error_message
                    )
                    self._emit_error(error)
                
                elif isinstance(message, StatusResponseMessage):
                    # Update device status
                    self._update_status(
                        connected=message.connected,
                        firmware_version=message.firmware_version,
                        current_state=message.current_state,
                        error_count=message.error_count
                    )
        
        except Exception as e:
            logger.error(f"Error processing received message: {e}")
    
    async def _ping_loop(self):
        """Background task to send periodic pings"""
        while self._connected:
            try:
                await asyncio.sleep(self.config.ping_interval)
                
                if self._connected:
                    ping_request = CommandRequest(
                        command_type=CommandType.PING,
                        device_id=self.device_id,
                        timeout_seconds=2.0
                    )
                    
                    try:
                        response = await self.send_command(ping_request)
                        if not response.success:
                            logger.warning(f"Ping failed: {response.error}")
                    except Exception as e:
                        logger.warning(f"Ping failed: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in ping loop: {e}")
                await asyncio.sleep(1.0)