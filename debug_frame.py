#!/usr/bin/env python3
"""
Debug frame protocol implementation
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.protocols.frame_protocol import FrameEncoder, FrameParser, FrameProtocol

def debug_frame():
    """Debug frame encoding and parsing"""
    print("Debugging frame protocol...")
    
    # Create encoder
    encoder = FrameEncoder()
    
    # Test encoding
    test_payload = "RELAY:1:ON"
    frame_data = encoder.encode("CMD", test_payload)
    
    print(f"Original payload: {test_payload}")
    print(f"Encoded frame bytes: {frame_data}")
    print(f"Encoded frame hex: {frame_data.hex()}")
    print(f"Encoded frame string: {frame_data.decode('utf-8', errors='replace')}")
    
    # Manual parsing to understand the format
    frame_str = frame_data.decode('utf-8', errors='replace')
    print(f"\nFrame structure analysis:")
    print(f"First byte (STX): {frame_data[0]:02X} ({'STX' if frame_data[0] == 0x02 else 'NOT STX'})")
    
    # Find ETX
    etx_pos = -1
    for i, byte in enumerate(frame_data):
        if byte == 0x03:
            etx_pos = i
            break
    
    if etx_pos >= 0:
        print(f"ETX found at position: {etx_pos}")
        content = frame_data[1:etx_pos].decode('utf-8')
        crc_part = frame_data[etx_pos+1:].decode('utf-8')
        print(f"Frame content: '{content}'")
        print(f"CRC part: '{crc_part}'")
        
        # Parse content
        parts = content.split(':')
        if len(parts) >= 3:
            length_str = parts[0]
            frame_type = parts[1]
            payload = ':'.join(parts[2:])
            print(f"Length: {length_str}")
            print(f"Type: {frame_type}")
            print(f"Payload: {payload}")
    else:
        print("ETX not found!")

if __name__ == "__main__":
    debug_frame()