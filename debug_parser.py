#!/usr/bin/env python3
"""
Debug frame parser step by step
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.protocols.frame_protocol import FrameEncoder, FrameParser, FrameState

def debug_parser():
    """Debug parser step by step"""
    print("Debugging frame parser...")
    
    # Create test data
    encoder = FrameEncoder()
    frame_data = encoder.encode("CMD", "RELAY:1:ON")
    
    print(f"Frame data: {frame_data}")
    print(f"Frame hex: {frame_data.hex()}")
    print(f"Frame content: {frame_data.decode('utf-8', errors='replace')}")
    
    # Parse byte by byte
    parser = FrameParser()
    
    for i, byte in enumerate(frame_data):
        print(f"\nByte {i}: 0x{byte:02X} ('{chr(byte) if 32 <= byte <= 126 else '?'}')")
        print(f"  State before: {parser.state}")
        print(f"  Buffer before: '{parser.buffer.decode('utf-8', errors='replace') if isinstance(parser.buffer, bytes) else parser.buffer}'")
        
        frame = parser.feed_byte(byte)
        
        print(f"  State after: {parser.state}")
        print(f"  Buffer after: '{parser.buffer.decode('utf-8', errors='replace') if isinstance(parser.buffer, bytes) else parser.buffer}'")
        print(f"  Expected length: {parser.expected_length}")
        print(f"  Current type: '{parser.current_type}'")
        print(f"  Current payload: '{parser.current_payload}'")
        
        if frame:
            print(f"  FRAME COMPLETED: {frame}")
            return frame
    
    print("\nNo frame completed!")
    return None

if __name__ == "__main__":
    debug_parser()