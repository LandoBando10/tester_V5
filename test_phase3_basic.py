#!/usr/bin/env python3
"""
Basic Phase 3 functionality test - just the core frame protocol
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.protocols.frame_protocol import FrameEncoder, FrameParser, FrameProtocol

def test_basic_frame_protocol():
    """Test basic frame encoding and decoding"""
    print("Testing basic frame protocol...")
    
    # Create protocol instance
    protocol = FrameProtocol()
    
    # Test encoding
    test_payload = "RELAY:1:ON"
    frame_data = protocol.encode_message("CMD", test_payload)
    print(f"Encoded frame: {frame_data}")
    
    # Test parsing
    frames = protocol.parse_data(frame_data)
    print(f"Parsed {len(frames)} frames")
    
    if frames:
        frame = frames[0]
        print(f"Frame type: {frame.frame_type}")
        print(f"Frame payload: {frame.payload}")
        print(f"Frame CRC: {frame.crc}")
        
        if frame.payload == test_payload:
            print("✅ Basic frame protocol test PASSED")
            return True
        else:
            print("❌ Payload mismatch")
            return False
    else:
        print("❌ No frames parsed")
        return False

if __name__ == "__main__":
    success = test_basic_frame_protocol()
    print(f"\nPhase 3 Basic Test: {'PASSED' if success else 'FAILED'}")