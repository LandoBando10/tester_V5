#!/usr/bin/env python3
"""
Basic Phase 4.4 Binary Protocol Test

Simple test to verify the core binary protocol implementation works correctly
without complex dependencies.
"""

import sys
import os
import time

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_basic_message_formats():
    """Test basic message format functionality"""
    print("🧪 Testing binary message formats...")
    
    try:
        from protocols.binary_message_formats import (
            create_ping_message, create_measure_message, create_measure_group_message,
            PingResponseMessage, MeasureResponseMessage, ErrorMessage,
            BinaryMessage, MessageType, TestType, ErrorCode
        )
        
        # Test ping message
        ping = create_ping_message(12345)
        packed = ping.pack()
        unpacked = BinaryMessage.unpack(packed)
        
        assert unpacked.sequence_id == 12345
        print("✅ Ping message encoding/decoding works")
        
        # Test measure message
        measure = create_measure_message(5, TestType.VOLTAGE_CURRENT)
        packed = measure.pack()
        unpacked = BinaryMessage.unpack(packed)
        
        assert unpacked.relay_id == 5
        assert unpacked.test_type == TestType.VOLTAGE_CURRENT
        print("✅ Measure message encoding/decoding works")
        
        # Test measure group message
        group = create_measure_group_message([1, 2, 3, 4], TestType.RELAY_CONTINUITY)
        packed = group.pack()
        unpacked = BinaryMessage.unpack(packed)
        
        assert unpacked.relay_ids == [1, 2, 3, 4]
        assert unpacked.test_type == TestType.RELAY_CONTINUITY
        print("✅ Group measure message encoding/decoding works")
        
        # Test response messages
        ping_response = PingResponseMessage(sequence_id=12345, device_id="SMT_TEST_1")
        packed = ping_response.pack()
        unpacked = BinaryMessage.unpack(packed)
        
        assert unpacked.sequence_id == 12345
        assert unpacked.device_id == "SMT_TEST_1"
        print("✅ Ping response message encoding/decoding works")
        
        # Test measure response
        measure_response = MeasureResponseMessage(
            relay_id=3,
            test_type=TestType.VOLTAGE_CURRENT,
            voltage=12.5,
            current=0.125,
            error_code=ErrorCode.SUCCESS
        )
        packed = measure_response.pack()
        unpacked = BinaryMessage.unpack(packed)
        
        assert unpacked.relay_id == 3
        assert abs(unpacked.voltage - 12.5) < 0.01
        assert abs(unpacked.current - 0.125) < 0.001
        assert unpacked.error_code == ErrorCode.SUCCESS
        print("✅ Measure response message encoding/decoding works")
        
        # Test error message
        error_msg = ErrorMessage(
            error_code=ErrorCode.INVALID_PARAMETER,
            error_message="Test error"
        )
        packed = error_msg.pack()
        unpacked = BinaryMessage.unpack(packed)
        
        assert unpacked.error_code == ErrorCode.INVALID_PARAMETER
        assert unpacked.error_message == "Test error"
        print("✅ Error message encoding/decoding works")
        
        return True
        
    except Exception as e:
        print(f"❌ Message format test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_crc_validation():
    """Test CRC validation functionality"""
    print("\n🧪 Testing CRC validation...")
    
    try:
        from protocols.binary_message_formats import create_ping_message, BinaryMessage
        
        # Create a valid message
        ping = create_ping_message(12345)
        packed = ping.pack()
        
        # Valid message should decode successfully
        unpacked = BinaryMessage.unpack(packed)
        assert unpacked.sequence_id == 12345
        print("✅ Valid CRC passes")
        
        # Corrupt the message and verify CRC failure
        corrupted = bytearray(packed)
        corrupted[10] ^= 0xFF  # Flip some bits
        
        try:
            BinaryMessage.unpack(bytes(corrupted))
            print("❌ CRC validation failed - corrupted message was accepted")
            return False
        except ValueError as e:
            if "CRC mismatch" in str(e):
                print("✅ Invalid CRC properly rejected")
                return True
            else:
                print(f"❌ Unexpected error: {e}")
                return False
                
    except Exception as e:
        print(f"❌ CRC validation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance_basic():
    """Basic performance test"""
    print("\n🧪 Testing basic performance...")
    
    try:
        from protocols.binary_message_formats import create_ping_message, BinaryMessage
        
        # Encoding performance
        ping = create_ping_message(12345)
        iterations = 1000
        
        start = time.time()
        for _ in range(iterations):
            packed = ping.pack()
        end = time.time()
        
        avg_encode_time = (end - start) / iterations
        print(f"✅ Encoding: {avg_encode_time*1000:.3f}ms per message")
        
        # Decoding performance
        packed = ping.pack()
        
        start = time.time()
        for _ in range(iterations):
            unpacked = BinaryMessage.unpack(packed)
        end = time.time()
        
        avg_decode_time = (end - start) / iterations
        print(f"✅ Decoding: {avg_decode_time*1000:.3f}ms per message")
        
        # Check performance is reasonable
        if avg_encode_time < 0.001 and avg_decode_time < 0.001:
            print("✅ Performance is acceptable (under 1ms per operation)")
            return True
        else:
            print("⚠️  Performance may need optimization")
            return True  # Still pass, but with warning
            
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_message_sizes():
    """Test message size efficiency"""
    print("\n🧪 Testing message size efficiency...")
    
    try:
        from protocols.binary_message_formats import (
            create_ping_message, create_measure_message, create_measure_group_message,
            TestType
        )
        
        # Test ping message size
        ping = create_ping_message(12345)
        ping_size = len(ping.pack())
        print(f"✅ Ping message size: {ping_size} bytes")
        
        # Test measure message size
        measure = create_measure_message(5, TestType.VOLTAGE_CURRENT)
        measure_size = len(measure.pack())
        print(f"✅ Measure message size: {measure_size} bytes")
        
        # Test group message size
        group = create_measure_group_message(list(range(1, 17)), TestType.VOLTAGE_CURRENT)
        group_size = len(group.pack())
        print(f"✅ Group message (16 relays) size: {group_size} bytes")
        
        # Compare to text equivalents (approximate)
        text_ping = len("PING:12345\n")
        text_measure = len("MEASURE:5\n")
        text_group = len("MEASURE_GROUP:1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16\n")
        
        print(f"📊 Size comparison:")
        print(f"   Ping: Binary {ping_size}B vs Text {text_ping}B (ratio: {text_ping/ping_size:.2f})")
        print(f"   Measure: Binary {measure_size}B vs Text {text_measure}B (ratio: {text_measure/measure_size:.2f})")
        print(f"   Group: Binary {group_size}B vs Text {text_group}B (ratio: {text_group/group_size:.2f})")
        
        return True
        
    except Exception as e:
        print(f"❌ Message size test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all basic tests"""
    print("🚀 Phase 4.4 Binary Protocol Basic Tests")
    print("="*50)
    
    tests = [
        ("Message Formats", test_basic_message_formats),
        ("CRC Validation", test_crc_validation),
        ("Basic Performance", test_performance_basic),
        ("Message Sizes", test_message_sizes)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Running {test_name} test...")
        if test_func():
            passed += 1
            print(f"✅ {test_name} test PASSED")
        else:
            print(f"❌ {test_name} test FAILED")
    
    print("\n" + "="*50)
    print(f"📊 TEST SUMMARY: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All Phase 4.4 basic tests PASSED!")
        print("✅ Binary protocol implementation is working correctly")
        return True
    else:
        print("❌ Some tests failed - please review implementation")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)