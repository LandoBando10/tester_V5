"""
Binary Message Format Definitions for Phase 4.4 Protocol

This module defines the binary message structures and schemas for efficient
device communication. It provides type-safe serialization with schema validation
and supports multiple protocol versions.

Phase 4.4 Implementation - Binary Protocol with Advanced Serialization
"""

import enum
import struct
import time
from typing import Dict, Any, Optional, Union, List, Type
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

# Message format constants
MAGIC_BYTES = b'\xAA\x55'  # Protocol magic bytes
PROTOCOL_VERSION = 1
MAX_PAYLOAD_SIZE = 480  # Leave room for header and trailer
HEADER_SIZE = 8  # MAGIC(2) + VERSION(1) + LENGTH(2) + TYPE(1) + FLAGS(1) + RESERVED(1)
TRAILER_SIZE = 6  # CRC16(2) + ETX(1) + PADDING(3)


class MessageType(enum.IntEnum):
    """Binary message types with numeric values for efficient encoding"""
    # Connection and status messages (0x00-0x0F)
    PING = 0x00
    PING_RESPONSE = 0x01
    GET_STATUS = 0x02
    STATUS_RESPONSE = 0x03
    GET_VERSION = 0x04
    VERSION_RESPONSE = 0x05
    CONNECT = 0x06
    CONNECT_RESPONSE = 0x07
    DISCONNECT = 0x08
    DISCONNECT_RESPONSE = 0x09
    
    # Measurement messages (0x10-0x2F)
    MEASURE = 0x10
    MEASURE_RESPONSE = 0x11
    MEASURE_GROUP = 0x12
    MEASURE_GROUP_RESPONSE = 0x13
    START_CONTINUOUS = 0x14
    START_CONTINUOUS_RESPONSE = 0x15
    STOP_CONTINUOUS = 0x16
    STOP_CONTINUOUS_RESPONSE = 0x17
    MEASUREMENT_DATA = 0x18  # Continuous measurement stream
    
    # Control messages (0x30-0x4F)
    SET_RELAY = 0x30
    SET_RELAY_RESPONSE = 0x31
    START_TEST = 0x32
    START_TEST_RESPONSE = 0x33
    STOP_TEST = 0x34
    STOP_TEST_RESPONSE = 0x35
    RESET = 0x36
    RESET_RESPONSE = 0x37
    
    # Configuration messages (0x50-0x6F)
    SET_PARAMETER = 0x50
    SET_PARAMETER_RESPONSE = 0x51
    GET_PARAMETER = 0x52
    GET_PARAMETER_RESPONSE = 0x53
    CONFIGURE = 0x54
    CONFIGURE_RESPONSE = 0x55
    
    # Protocol control messages (0x70-0x7F)
    ENABLE_CRC = 0x70
    ENABLE_CRC_RESPONSE = 0x71
    ENABLE_FRAMING = 0x72
    ENABLE_FRAMING_RESPONSE = 0x73
    SET_PROTOCOL = 0x74
    SET_PROTOCOL_RESPONSE = 0x75
    
    # Error and debug messages (0x80-0x8F)
    ERROR = 0x80
    DEBUG_INFO = 0x81
    
    # Reserved for future use (0x90-0xFF)


class MessageFlags(enum.IntFlag):
    """Message flags for special handling"""
    NONE = 0x00
    COMPRESSED = 0x01  # Payload is compressed
    ENCRYPTED = 0x02   # Payload is encrypted
    FRAGMENTED = 0x04  # Message is fragmented
    REQUIRES_ACK = 0x08  # Message requires acknowledgment
    IS_ACK = 0x10      # Message is an acknowledgment
    HIGH_PRIORITY = 0x20  # High priority message
    RESERVED_1 = 0x40
    RESERVED_2 = 0x80


class TestType(enum.IntEnum):
    """Test types with numeric values for efficient encoding"""
    VOLTAGE_CURRENT = 0x00
    RELAY_CONTINUITY = 0x01
    BUTTON_TEST = 0x02
    RGBW_TEST = 0x03
    FORWARD_VOLTAGE = 0x04
    WEIGHT_CHECK = 0x05
    UNKNOWN = 0xFF


class ErrorCode(enum.IntEnum):
    """Error codes for binary protocol"""
    SUCCESS = 0x00
    INVALID_COMMAND = 0x01
    INVALID_PARAMETER = 0x02
    DEVICE_BUSY = 0x03
    TIMEOUT = 0x04
    CRC_ERROR = 0x05
    BUFFER_OVERFLOW = 0x06
    HARDWARE_ERROR = 0x07
    COMMUNICATION_ERROR = 0x08
    UNKNOWN_ERROR = 0xFF


@dataclass
class BinaryMessageHeader:
    """Binary message header structure"""
    magic: bytes = MAGIC_BYTES
    version: int = PROTOCOL_VERSION
    length: int = 0  # Payload length
    message_type: MessageType = MessageType.PING
    flags: MessageFlags = MessageFlags.NONE
    reserved: int = 0
    
    def pack(self) -> bytes:
        """Pack header into binary format"""
        return struct.pack('>2sBHBBB', 
                          self.magic, 
                          self.version, 
                          self.length, 
                          self.message_type.value, 
                          self.flags.value, 
                          self.reserved)
    
    @classmethod
    def unpack(cls, data: bytes) -> 'BinaryMessageHeader':
        """Unpack header from binary format"""
        if len(data) < HEADER_SIZE:
            raise ValueError(f"Header data too short: {len(data)} < {HEADER_SIZE}")
        
        magic, version, length, msg_type, flags, reserved = struct.unpack('>2sBHBBB', data[:HEADER_SIZE])
        
        if magic != MAGIC_BYTES:
            raise ValueError(f"Invalid magic bytes: {magic.hex()} != {MAGIC_BYTES.hex()}")
        
        return cls(
            magic=magic,
            version=version,
            length=length,
            message_type=MessageType(msg_type),
            flags=MessageFlags(flags),
            reserved=reserved
        )


@dataclass
class BinaryMessage(ABC):
    """Base class for all binary messages"""
    header: BinaryMessageHeader = field(default_factory=BinaryMessageHeader)
    timestamp: float = field(default_factory=time.time)
    
    @abstractmethod
    def pack_payload(self) -> bytes:
        """Pack message payload into binary format"""
        pass
    
    @classmethod
    @abstractmethod
    def unpack_payload(cls, data: bytes, header: BinaryMessageHeader) -> 'BinaryMessage':
        """Unpack message payload from binary format"""
        pass
    
    def pack(self) -> bytes:
        """Pack complete message into binary format"""
        payload = self.pack_payload()
        self.header.length = len(payload)
        
        if len(payload) > MAX_PAYLOAD_SIZE:
            raise ValueError(f"Payload too large: {len(payload)} > {MAX_PAYLOAD_SIZE}")
        
        header_bytes = self.header.pack()
        
        # Calculate CRC16 over header + payload
        try:
            from utils.crc16 import calculate_crc16
        except ImportError:
            # Fallback for test environment
            from src.utils.crc16 import calculate_crc16
        crc_data = header_bytes + payload
        crc = calculate_crc16(crc_data)
        
        # Pack complete message
        trailer = struct.pack('>HB3x', crc, 0x03)  # CRC + ETX + padding
        return header_bytes + payload + trailer
    
    @classmethod
    def unpack(cls, data: bytes) -> 'BinaryMessage':
        """Unpack complete message from binary format"""
        if len(data) < HEADER_SIZE + TRAILER_SIZE:
            raise ValueError("Message too short")
        
        # Unpack header
        header = BinaryMessageHeader.unpack(data[:HEADER_SIZE])
        
        # Extract payload
        payload_end = HEADER_SIZE + header.length
        if payload_end + TRAILER_SIZE > len(data):
            raise ValueError("Invalid message length")
        
        payload = data[HEADER_SIZE:payload_end]
        
        # Verify CRC
        crc_data = data[:payload_end]
        trailer_start = payload_end
        expected_crc = struct.unpack('>H', data[trailer_start:trailer_start+2])[0]
        
        try:
            from utils.crc16 import calculate_crc16
        except ImportError:
            # Fallback for test environment
            from src.utils.crc16 import calculate_crc16
        actual_crc = calculate_crc16(crc_data)
        
        if actual_crc != expected_crc:
            raise ValueError(f"CRC mismatch: expected {expected_crc:04X}, got {actual_crc:04X}")
        
        # Create appropriate message type
        message_class = MESSAGE_TYPE_MAP.get(header.message_type)
        if not message_class:
            raise ValueError(f"Unknown message type: {header.message_type}")
        
        return message_class.unpack_payload(payload, header)


# Specific message implementations

@dataclass
class PingMessage(BinaryMessage):
    """Ping message for connection testing"""
    sequence_id: int = 0
    
    def __post_init__(self):
        self.header.message_type = MessageType.PING
    
    def pack_payload(self) -> bytes:
        return struct.pack('>I', self.sequence_id)
    
    @classmethod
    def unpack_payload(cls, data: bytes, header: BinaryMessageHeader) -> 'PingMessage':
        if len(data) < 4:
            raise ValueError("Ping payload too short")
        sequence_id = struct.unpack('>I', data[:4])[0]
        return cls(header=header, sequence_id=sequence_id)


@dataclass
class PingResponseMessage(BinaryMessage):
    """Ping response message"""
    sequence_id: int = 0
    device_id: str = ""
    
    def __post_init__(self):
        self.header.message_type = MessageType.PING_RESPONSE
    
    def pack_payload(self) -> bytes:
        device_id_bytes = self.device_id.encode('utf-8')[:32]  # Limit device ID length
        return struct.pack('>I', self.sequence_id) + device_id_bytes
    
    @classmethod
    def unpack_payload(cls, data: bytes, header: BinaryMessageHeader) -> 'PingResponseMessage':
        if len(data) < 4:
            raise ValueError("Ping response payload too short")
        sequence_id = struct.unpack('>I', data[:4])[0]
        device_id = data[4:].decode('utf-8').rstrip('\x00')
        return cls(header=header, sequence_id=sequence_id, device_id=device_id)


@dataclass
class MeasureMessage(BinaryMessage):
    """Single measurement request"""
    relay_id: int = 0
    test_type: TestType = TestType.VOLTAGE_CURRENT
    
    def __post_init__(self):
        self.header.message_type = MessageType.MEASURE
    
    def pack_payload(self) -> bytes:
        return struct.pack('>BB', self.relay_id, self.test_type.value)
    
    @classmethod
    def unpack_payload(cls, data: bytes, header: BinaryMessageHeader) -> 'MeasureMessage':
        if len(data) < 2:
            raise ValueError("Measure payload too short")
        relay_id, test_type = struct.unpack('>BB', data[:2])
        return cls(header=header, relay_id=relay_id, test_type=TestType(test_type))


@dataclass
class MeasureResponseMessage(BinaryMessage):
    """Single measurement response"""
    relay_id: int = 0
    test_type: TestType = TestType.VOLTAGE_CURRENT
    voltage: float = 0.0
    current: float = 0.0
    error_code: ErrorCode = ErrorCode.SUCCESS
    
    def __post_init__(self):
        self.header.message_type = MessageType.MEASURE_RESPONSE
    
    def pack_payload(self) -> bytes:
        return struct.pack('>BBffB', 
                          self.relay_id, 
                          self.test_type.value, 
                          self.voltage, 
                          self.current, 
                          self.error_code.value)
    
    @classmethod
    def unpack_payload(cls, data: bytes, header: BinaryMessageHeader) -> 'MeasureResponseMessage':
        if len(data) < 11:
            raise ValueError("Measure response payload too short")
        relay_id, test_type, voltage, current, error_code = struct.unpack('>BBffB', data[:11])
        return cls(
            header=header,
            relay_id=relay_id,
            test_type=TestType(test_type),
            voltage=voltage,
            current=current,
            error_code=ErrorCode(error_code)
        )


@dataclass
class MeasureGroupMessage(BinaryMessage):
    """Multiple measurement request"""
    relay_ids: List[int] = field(default_factory=list)
    test_type: TestType = TestType.VOLTAGE_CURRENT
    
    def __post_init__(self):
        self.header.message_type = MessageType.MEASURE_GROUP
    
    def pack_payload(self) -> bytes:
        if len(self.relay_ids) > 255:
            raise ValueError("Too many relays in group")
        
        payload = struct.pack('>BB', len(self.relay_ids), self.test_type.value)
        for relay_id in self.relay_ids:
            payload += struct.pack('>B', relay_id)
        return payload
    
    @classmethod
    def unpack_payload(cls, data: bytes, header: BinaryMessageHeader) -> 'MeasureGroupMessage':
        if len(data) < 2:
            raise ValueError("Measure group payload too short")
        
        count, test_type = struct.unpack('>BB', data[:2])
        if len(data) < 2 + count:
            raise ValueError("Measure group payload incomplete")
        
        relay_ids = []
        for i in range(count):
            relay_ids.append(struct.unpack('>B', data[2+i:3+i])[0])
        
        return cls(header=header, relay_ids=relay_ids, test_type=TestType(test_type))


@dataclass
class MeasureGroupResponseMessage(BinaryMessage):
    """Multiple measurement response"""
    measurements: List[Dict[str, Union[int, float]]] = field(default_factory=list)
    error_code: ErrorCode = ErrorCode.SUCCESS
    
    def __post_init__(self):
        self.header.message_type = MessageType.MEASURE_GROUP_RESPONSE
    
    def pack_payload(self) -> bytes:
        if len(self.measurements) > 255:
            raise ValueError("Too many measurements in response")
        
        payload = struct.pack('>BB', len(self.measurements), self.error_code.value)
        
        for measurement in self.measurements:
            relay_id = measurement.get('relay_id', 0)
            voltage = measurement.get('voltage', 0.0)
            current = measurement.get('current', 0.0)
            payload += struct.pack('>Bff', relay_id, voltage, current)
        
        return payload
    
    @classmethod
    def unpack_payload(cls, data: bytes, header: BinaryMessageHeader) -> 'MeasureGroupResponseMessage':
        if len(data) < 2:
            raise ValueError("Measure group response payload too short")
        
        count, error_code = struct.unpack('>BB', data[:2])
        expected_size = 2 + count * 9  # 1 byte relay_id + 4 bytes voltage + 4 bytes current
        
        if len(data) < expected_size:
            raise ValueError("Measure group response payload incomplete")
        
        measurements = []
        offset = 2
        for i in range(count):
            relay_id, voltage, current = struct.unpack('>Bff', data[offset:offset+9])
            measurements.append({
                'relay_id': relay_id,
                'voltage': voltage,
                'current': current
            })
            offset += 9
        
        return cls(
            header=header,
            measurements=measurements,
            error_code=ErrorCode(error_code)
        )


@dataclass
class StatusResponseMessage(BinaryMessage):
    """Device status response"""
    device_id: str = ""
    firmware_version: str = ""
    connected: bool = False
    current_state: str = ""
    error_count: int = 0
    
    def __post_init__(self):
        self.header.message_type = MessageType.STATUS_RESPONSE
    
    def pack_payload(self) -> bytes:
        device_id_bytes = self.device_id.encode('utf-8')[:32]
        firmware_version_bytes = self.firmware_version.encode('utf-8')[:16]
        current_state_bytes = self.current_state.encode('utf-8')[:32]
        
        return (struct.pack('>B', len(device_id_bytes)) + device_id_bytes +
                struct.pack('>B', len(firmware_version_bytes)) + firmware_version_bytes +
                struct.pack('>?', self.connected) +
                struct.pack('>B', len(current_state_bytes)) + current_state_bytes +
                struct.pack('>I', self.error_count))
    
    @classmethod
    def unpack_payload(cls, data: bytes, header: BinaryMessageHeader) -> 'StatusResponseMessage':
        if len(data) < 9:  # Minimum required bytes
            raise ValueError("Status response payload too short")
        
        offset = 0
        
        # Device ID
        device_id_len = struct.unpack('>B', data[offset:offset+1])[0]
        offset += 1
        device_id = data[offset:offset+device_id_len].decode('utf-8')
        offset += device_id_len
        
        # Firmware version
        fw_len = struct.unpack('>B', data[offset:offset+1])[0]
        offset += 1
        firmware_version = data[offset:offset+fw_len].decode('utf-8')
        offset += fw_len
        
        # Connected flag
        connected = struct.unpack('>?', data[offset:offset+1])[0]
        offset += 1
        
        # Current state
        state_len = struct.unpack('>B', data[offset:offset+1])[0]
        offset += 1
        current_state = data[offset:offset+state_len].decode('utf-8')
        offset += state_len
        
        # Error count
        error_count = struct.unpack('>I', data[offset:offset+4])[0]
        
        return cls(
            header=header,
            device_id=device_id,
            firmware_version=firmware_version,
            connected=connected,
            current_state=current_state,
            error_count=error_count
        )


@dataclass
class ErrorMessage(BinaryMessage):
    """Error message"""
    error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR
    error_message: str = ""
    context_data: bytes = b""
    
    def __post_init__(self):
        self.header.message_type = MessageType.ERROR
    
    def pack_payload(self) -> bytes:
        error_message_bytes = self.error_message.encode('utf-8')[:128]
        context_bytes = self.context_data[:64]  # Limit context size
        
        return (struct.pack('>B', self.error_code.value) +
                struct.pack('>B', len(error_message_bytes)) + error_message_bytes +
                struct.pack('>B', len(context_bytes)) + context_bytes)
    
    @classmethod
    def unpack_payload(cls, data: bytes, header: BinaryMessageHeader) -> 'ErrorMessage':
        if len(data) < 3:
            raise ValueError("Error message payload too short")
        
        offset = 0
        error_code = ErrorCode(struct.unpack('>B', data[offset:offset+1])[0])
        offset += 1
        
        msg_len = struct.unpack('>B', data[offset:offset+1])[0]
        offset += 1
        error_message = data[offset:offset+msg_len].decode('utf-8')
        offset += msg_len
        
        if offset < len(data):
            context_len = struct.unpack('>B', data[offset:offset+1])[0]
            offset += 1
            context_data = data[offset:offset+context_len]
        else:
            context_data = b""
        
        return cls(
            header=header,
            error_code=error_code,
            error_message=error_message,
            context_data=context_data
        )


# Message type mapping for unpacking
MESSAGE_TYPE_MAP: Dict[MessageType, Type[BinaryMessage]] = {
    MessageType.PING: PingMessage,
    MessageType.PING_RESPONSE: PingResponseMessage,
    MessageType.MEASURE: MeasureMessage,
    MessageType.MEASURE_RESPONSE: MeasureResponseMessage,
    MessageType.MEASURE_GROUP: MeasureGroupMessage,
    MessageType.MEASURE_GROUP_RESPONSE: MeasureGroupResponseMessage,
    MessageType.STATUS_RESPONSE: StatusResponseMessage,
    MessageType.ERROR: ErrorMessage,
}


def create_ping_message(sequence_id: int = 0) -> PingMessage:
    """Convenience function to create a ping message"""
    return PingMessage(sequence_id=sequence_id)


def create_measure_message(relay_id: int, test_type: TestType = TestType.VOLTAGE_CURRENT) -> MeasureMessage:
    """Convenience function to create a measure message"""
    return MeasureMessage(relay_id=relay_id, test_type=test_type)


def create_measure_group_message(relay_ids: List[int], test_type: TestType = TestType.VOLTAGE_CURRENT) -> MeasureGroupMessage:
    """Convenience function to create a measure group message"""
    return MeasureGroupMessage(relay_ids=relay_ids, test_type=test_type)


def create_error_message(error_code: ErrorCode, error_message: str, context_data: bytes = b"") -> ErrorMessage:
    """Convenience function to create an error message"""
    return ErrorMessage(error_code=error_code, error_message=error_message, context_data=context_data)