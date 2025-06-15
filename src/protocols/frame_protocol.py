"""
Binary framing protocol implementation for Arduino communication.

Frame Format: <STX>LLL:TYPE:PAYLOAD<ETX>CCCC
- STX: 0x02 (Start of Text)
- LLL: 3-digit length (zero-padded, includes TYPE:PAYLOAD)
- TYPE: Command type (3 characters)
- PAYLOAD: Command payload data
- ETX: 0x03 (End of Text)
- CCCC: CRC-16 in hex (4 characters)

Example: <STX>013:MEA:RELAY:1<ETX>A1B2
"""

import enum
import time
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

from ..utils.crc16 import CRC16


class FrameConstants:
    STX = 0x02
    ETX = 0x03
    ESC = 0x1B
    
    MAX_FRAME_SIZE = 512
    HEADER_SIZE = 8  # STX + LLL + : + TYPE + :
    TRAILER_SIZE = 5  # ETX + CCCC
    MAX_PAYLOAD_SIZE = MAX_FRAME_SIZE - HEADER_SIZE - TRAILER_SIZE
    
    TIMEOUT_MS = 5000
    

class FrameState(enum.Enum):
    IDLE = "idle"
    HEADER = "header"
    LENGTH = "length"
    TYPE = "type"
    PAYLOAD = "payload"
    CRC = "crc"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class Frame:
    frame_type: str
    payload: str
    crc: Optional[int] = None
    timestamp: Optional[float] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


@dataclass
class FrameStats:
    total_frames: int = 0
    valid_frames: int = 0
    crc_errors: int = 0
    format_errors: int = 0
    timeout_errors: int = 0
    escape_errors: int = 0
    
    @property
    def error_rate(self) -> float:
        if self.total_frames == 0:
            return 0.0
        return (self.crc_errors + self.format_errors + self.timeout_errors + self.escape_errors) / self.total_frames


class FrameEncoder:
    """Encodes messages into framed format with CRC validation."""
    
    @staticmethod
    def encode(frame_type: str, payload: str) -> bytes:
        """
        Encode a message into framed format.
        
        Args:
            frame_type: 3-character command type
            payload: Message payload
            
        Returns:
            Encoded frame as bytes
            
        Raises:
            ValueError: If frame_type is not 3 characters or payload too large
        """
        if len(frame_type) != 3:
            raise ValueError(f"Frame type must be exactly 3 characters, got: {frame_type}")
        
        # Escape special characters in payload
        escaped_payload = FrameEncoder._escape_payload(payload)
        
        # Build message content
        content = f"{frame_type}:{escaped_payload}"
        
        if len(content) > FrameConstants.MAX_PAYLOAD_SIZE:
            raise ValueError(f"Payload too large: {len(content)} > {FrameConstants.MAX_PAYLOAD_SIZE}")
        
        # Calculate length (3 digits, zero-padded)
        length_str = f"{len(content):03d}"
        
        # Build frame without CRC
        frame_content = f"{length_str}:{content}"
        
        # Calculate CRC-16
        from ..utils.crc16 import calculate_crc16
        crc = calculate_crc16(frame_content.encode('utf-8'))
        crc_str = f"{crc:04X}"
        
        # Build complete frame
        frame = bytes([FrameConstants.STX]) + frame_content.encode('utf-8') + bytes([FrameConstants.ETX]) + crc_str.encode('utf-8')
        
        return frame
    
    @staticmethod
    def _escape_payload(payload: str) -> str:
        """Escape special characters in payload."""
        result = []
        for char in payload:
            if ord(char) in [FrameConstants.STX, FrameConstants.ETX, FrameConstants.ESC]:
                result.append(chr(FrameConstants.ESC))
                result.append(chr(ord(char) ^ 0x20))  # XOR with 0x20 for escaping
            else:
                result.append(char)
        return ''.join(result)


class FrameParser:
    """State machine parser for framed messages with timeout and error recovery."""
    
    def __init__(self, timeout_ms: int = FrameConstants.TIMEOUT_MS):
        self.state = FrameState.IDLE
        self.buffer = bytearray()
        self.expected_length = 0
        self.current_type = ""
        self.current_payload = ""
        self.timeout_ms = timeout_ms
        self.frame_start_time = 0.0
        self.stats = FrameStats()
        
        self.reset()
    
    def reset(self):
        """Reset parser state."""
        self.state = FrameState.IDLE
        self.buffer.clear()
        self.expected_length = 0
        self.current_type = ""
        self.current_payload = ""
        self.frame_start_time = 0.0
    
    def feed_byte(self, byte: int) -> Optional[Frame]:
        """
        Feed a single byte to the parser.
        
        Args:
            byte: Input byte
            
        Returns:
            Complete Frame if available, None otherwise
        """
        current_time = time.time() * 1000  # Convert to milliseconds
        
        # Check for timeout
        if self.state != FrameState.IDLE and self.frame_start_time > 0:
            if current_time - self.frame_start_time > self.timeout_ms:
                self.stats.timeout_errors += 1
                self.reset()
                return None
        
        try:
            if self.state == FrameState.IDLE:
                if byte == FrameConstants.STX:
                    self.state = FrameState.LENGTH
                    self.frame_start_time = current_time
                    self.buffer.clear()
                return None
                
            elif self.state == FrameState.LENGTH:
                if chr(byte).isdigit() and len(self.buffer) < 3:
                    self.buffer.append(byte)
                    if len(self.buffer) == 3:
                        self.expected_length = int(self.buffer.decode('utf-8'))
                        self.buffer.clear()
                elif byte == ord(':') and len(self.buffer) == 0:  # After length is complete
                    self.state = FrameState.TYPE
                else:
                    self._handle_error(f"Invalid length format: got {chr(byte) if 32 <= byte <= 126 else hex(byte)}")
                    return None
                return None
                
            elif self.state == FrameState.TYPE:
                if len(self.buffer) == 0 and byte == ord(':'):  # Transition after type is complete
                    self.state = FrameState.PAYLOAD
                elif len(self.buffer) < 3:
                    self.buffer.append(byte)
                    if len(self.buffer) == 3:
                        self.current_type = self.buffer.decode('utf-8')
                        self.buffer.clear()
                else:
                    self._handle_error(f"Invalid type state: buffer={len(self.buffer)}, byte={chr(byte) if 32 <= byte <= 126 else hex(byte)}")
                    return None
                return None
                
            elif self.state == FrameState.PAYLOAD:
                if byte == FrameConstants.ETX:
                    # For escaped payloads, we need to check the expected length against the original content
                    unescaped_payload = self._unescape_payload(self.buffer.decode('utf-8'))
                    reconstructed_content = self.current_type + ":" + unescaped_payload
                    
                    if len(reconstructed_content) == self.expected_length:
                        self.current_payload = unescaped_payload
                        self.buffer.clear()
                        self.state = FrameState.CRC
                    else:
                        self._handle_error(f"Payload length mismatch: expected {self.expected_length}, got {len(reconstructed_content)}")
                        return None
                else:
                    self.buffer.append(byte)
                    if len(self.buffer) > FrameConstants.MAX_PAYLOAD_SIZE:
                        self._handle_error("Payload too large")
                        return None
                return None
                
            elif self.state == FrameState.CRC:
                self.buffer.append(byte)
                if len(self.buffer) == 4:
                    try:
                        received_crc = int(self.buffer.decode('utf-8'), 16)
                        
                        # Calculate expected CRC
                        frame_content = f"{self.expected_length:03d}:{self.current_type}:{self._escape_payload(self.current_payload)}"
                        from ..utils.crc16 import calculate_crc16
                        expected_crc = calculate_crc16(frame_content.encode('utf-8'))
                        
                        if received_crc == expected_crc:
                            frame = Frame(
                                frame_type=self.current_type,
                                payload=self.current_payload,
                                crc=received_crc
                            )
                            self.stats.total_frames += 1
                            self.stats.valid_frames += 1
                            self.reset()
                            return frame
                        else:
                            self.stats.crc_errors += 1
                            self._handle_error(f"CRC mismatch: expected {expected_crc:04X}, got {received_crc:04X}")
                            return None
                            
                    except ValueError as e:
                        self._handle_error(f"Invalid CRC format: {e}")
                        return None
                return None
                
        except Exception as e:
            self._handle_error(f"Unexpected error: {e}")
            return None
        
        return None
    
    def feed_data(self, data: bytes) -> list[Frame]:
        """
        Feed multiple bytes to the parser.
        
        Args:
            data: Input data bytes
            
        Returns:
            List of complete frames
        """
        frames = []
        for byte in data:
            frame = self.feed_byte(byte)
            if frame:
                frames.append(frame)
        return frames
    
    def _handle_error(self, error_msg: str):
        """Handle parsing error."""
        self.stats.total_frames += 1
        self.stats.format_errors += 1
        self.reset()
    
    def _escape_payload(self, payload: str) -> str:
        """Escape special characters in payload (same as encoder)."""
        return FrameEncoder._escape_payload(payload)
    
    def _unescape_payload(self, escaped_payload: str) -> str:
        """Unescape special characters in payload."""
        result = []
        i = 0
        while i < len(escaped_payload):
            if ord(escaped_payload[i]) == FrameConstants.ESC and i + 1 < len(escaped_payload):
                # Unescape next character
                result.append(chr(ord(escaped_payload[i + 1]) ^ 0x20))
                i += 2
            else:
                result.append(escaped_payload[i])
                i += 1
        return ''.join(result)
    
    def get_stats(self) -> FrameStats:
        """Get parser statistics."""
        return self.stats


class FrameProtocol:
    """High-level frame protocol interface."""
    
    def __init__(self, timeout_ms: int = FrameConstants.TIMEOUT_MS):
        self.encoder = FrameEncoder()
        self.parser = FrameParser(timeout_ms)
    
    def encode_message(self, command_type: str, payload: str) -> bytes:
        """Encode a message into framed format."""
        return self.encoder.encode(command_type, payload)
    
    def parse_data(self, data: bytes) -> list[Frame]:
        """Parse incoming data for complete frames."""
        return self.parser.feed_data(data)
    
    def reset_parser(self):
        """Reset the parser state."""
        self.parser.reset()
    
    def get_parser_stats(self) -> FrameStats:
        """Get parser statistics."""
        return self.parser.get_stats()