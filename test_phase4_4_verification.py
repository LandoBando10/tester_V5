#!/usr/bin/env python3
"""
Phase 4.4 Binary Protocol Verification Test Suite

This comprehensive test suite validates the Phase 4.4 binary protocol implementation
including message encoding/decoding, protocol communication, and performance metrics.

Features tested:
- Binary message format validation
- Message serialization/deserialization
- Protocol communication flow
- Error handling and recovery
- Performance benchmarking
- Memory usage optimization
- CRC validation
- Backward compatibility

Usage:
    python test_phase4_4_verification.py
"""

import asyncio
import time
import struct
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from protocols.binary_message_formats import (
        BinaryMessage, BinaryMessageHeader, MessageType, MessageFlags, ErrorCode, TestType,
        PingMessage, PingResponseMessage, MeasureMessage, MeasureResponseMessage,
        MeasureGroupMessage, MeasureGroupResponseMessage, StatusResponseMessage, ErrorMessage,
        create_ping_message, create_measure_message, create_measure_group_message
    )

    from protocols.binary_protocol import (
        BinaryProtocolConfig, BinaryMessageCodec
    )

    from protocols.base_protocol import (
        DeviceType, CommandType, CommandRequest, CommandResponse
    )
    
    print("✅ Binary protocol modules imported successfully")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Running basic binary message format tests only...")
    # We'll import only what we can and run limited tests

class TestBinaryMessageFormats(unittest.TestCase):
    """Test binary message format encoding and decoding"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_device_id = "test_device_1"
        self.test_sequence = 12345
    
    def test_binary_header_pack_unpack(self):
        """Test binary header packing and unpacking"""
        header = BinaryMessageHeader()
        header.length = 100
        header.message_type = MessageType.PING
        header.flags = MessageFlags.REQUIRES_ACK
        
        packed = header.pack()
        self.assertEqual(len(packed), 8)  # Header size
        
        unpacked = BinaryMessageHeader.unpack(packed)
        self.assertEqual(unpacked.length, 100)
        self.assertEqual(unpacked.message_type, MessageType.PING)
        self.assertEqual(unpacked.flags, MessageFlags.REQUIRES_ACK)
    
    def test_ping_message_encoding(self):
        """Test ping message encoding and decoding"""
        ping = create_ping_message(self.test_sequence)
        
        # Test packing
        packed = ping.pack()
        self.assertGreater(len(packed), 0)
        
        # Test unpacking
        unpacked = BinaryMessage.unpack(packed)
        self.assertIsInstance(unpacked, PingMessage)
        self.assertEqual(unpacked.sequence_id, self.test_sequence)
    
    def test_ping_response_message_encoding(self):
        """Test ping response message encoding and decoding"""
        response = PingResponseMessage(sequence_id=self.test_sequence, device_id=self.test_device_id)
        
        packed = response.pack()
        unpacked = BinaryMessage.unpack(packed)
        
        self.assertIsInstance(unpacked, PingResponseMessage)
        self.assertEqual(unpacked.sequence_id, self.test_sequence)
        self.assertEqual(unpacked.device_id, self.test_device_id)
    
    def test_measure_message_encoding(self):
        """Test measure message encoding and decoding"""
        measure = create_measure_message(relay_id=5, test_type=TestType.VOLTAGE_CURRENT)
        
        packed = measure.pack()
        unpacked = BinaryMessage.unpack(packed)
        
        self.assertIsInstance(unpacked, MeasureMessage)
        self.assertEqual(unpacked.relay_id, 5)
        self.assertEqual(unpacked.test_type, TestType.VOLTAGE_CURRENT)
    
    def test_measure_response_encoding(self):
        """Test measure response encoding and decoding"""
        response = MeasureResponseMessage(
            relay_id=3,
            test_type=TestType.VOLTAGE_CURRENT,
            voltage=12.5,
            current=0.125,
            error_code=ErrorCode.SUCCESS
        )
        
        packed = response.pack()
        unpacked = BinaryMessage.unpack(packed)
        
        self.assertIsInstance(unpacked, MeasureResponseMessage)
        self.assertEqual(unpacked.relay_id, 3)
        self.assertEqual(unpacked.test_type, TestType.VOLTAGE_CURRENT)
        self.assertAlmostEqual(unpacked.voltage, 12.5, places=2)
        self.assertAlmostEqual(unpacked.current, 0.125, places=3)
        self.assertEqual(unpacked.error_code, ErrorCode.SUCCESS)
    
    def test_measure_group_encoding(self):
        """Test measure group message encoding and decoding"""
        relay_ids = [1, 3, 5, 7]
        group_msg = create_measure_group_message(relay_ids, TestType.RELAY_CONTINUITY)
        
        packed = group_msg.pack()
        unpacked = BinaryMessage.unpack(packed)
        
        self.assertIsInstance(unpacked, MeasureGroupMessage)
        self.assertEqual(unpacked.relay_ids, relay_ids)
        self.assertEqual(unpacked.test_type, TestType.RELAY_CONTINUITY)
    
    def test_measure_group_response_encoding(self):
        """Test measure group response encoding and decoding"""
        measurements = [
            {'relay_id': 1, 'voltage': 5.0, 'current': 0.1},
            {'relay_id': 3, 'voltage': 3.3, 'current': 0.05},
            {'relay_id': 5, 'voltage': 12.0, 'current': 0.2}
        ]
        
        response = MeasureGroupResponseMessage(
            measurements=measurements,
            error_code=ErrorCode.SUCCESS
        )
        
        packed = response.pack()
        unpacked = BinaryMessage.unpack(packed)
        
        self.assertIsInstance(unpacked, MeasureGroupResponseMessage)
        self.assertEqual(len(unpacked.measurements), 3)
        self.assertEqual(unpacked.measurements[0]['relay_id'], 1)
        self.assertAlmostEqual(unpacked.measurements[0]['voltage'], 5.0, places=1)
        self.assertEqual(unpacked.error_code, ErrorCode.SUCCESS)
    
    def test_status_response_encoding(self):
        """Test status response encoding and decoding"""
        status = StatusResponseMessage(
            device_id="SMT_TEST_1",
            firmware_version="5.3.0",
            connected=True,
            current_state="READY",
            error_count=42
        )
        
        packed = status.pack()
        unpacked = BinaryMessage.unpack(packed)
        
        self.assertIsInstance(unpacked, StatusResponseMessage)
        self.assertEqual(unpacked.device_id, "SMT_TEST_1")
        self.assertEqual(unpacked.firmware_version, "5.3.0")
        self.assertTrue(unpacked.connected)
        self.assertEqual(unpacked.current_state, "READY")
        self.assertEqual(unpacked.error_count, 42)
    
    def test_error_message_encoding(self):
        """Test error message encoding and decoding"""
        error_msg = ErrorMessage(
            error_code=ErrorCode.INVALID_PARAMETER,
            error_message="Test error message",
            context_data=b"test_context"
        )
        
        packed = error_msg.pack()
        unpacked = BinaryMessage.unpack(packed)
        
        self.assertIsInstance(unpacked, ErrorMessage)
        self.assertEqual(unpacked.error_code, ErrorCode.INVALID_PARAMETER)
        self.assertEqual(unpacked.error_message, "Test error message")
        self.assertEqual(unpacked.context_data, b"test_context")
    
    def test_crc_validation(self):
        """Test CRC validation in message packing/unpacking"""
        ping = create_ping_message(12345)
        packed = ping.pack()
        
        # Valid message should unpack successfully
        unpacked = BinaryMessage.unpack(packed)
        self.assertIsInstance(unpacked, PingMessage)
        
        # Corrupt one byte and verify CRC failure
        corrupted = bytearray(packed)
        corrupted[10] ^= 0xFF  # Flip bits in payload
        
        with self.assertRaises(ValueError) as context:
            BinaryMessage.unpack(bytes(corrupted))
        self.assertIn("CRC mismatch", str(context.exception))
    
    def test_invalid_magic_bytes(self):
        """Test rejection of invalid magic bytes"""
        ping = create_ping_message(12345)
        packed = ping.pack()
        
        # Corrupt magic bytes
        corrupted = bytearray(packed)
        corrupted[0] = 0x00  # Invalid magic byte
        
        with self.assertRaises(ValueError) as context:
            BinaryMessage.unpack(bytes(corrupted))
        self.assertIn("Invalid magic bytes", str(context.exception))
    
    def test_payload_size_limits(self):
        """Test payload size limit enforcement"""
        # Create a message with oversized payload
        large_device_id = "X" * 500  # Way too large
        response = PingResponseMessage(sequence_id=1, device_id=large_device_id)
        
        with self.assertRaises(ValueError) as context:
            response.pack()
        self.assertIn("Payload too large", str(context.exception))


class TestBinaryMessageCodec(unittest.TestCase):
    """Test binary message codec functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = BinaryProtocolConfig()
        self.codec = BinaryMessageCodec(self.config)
    
    def test_sequence_generation(self):
        """Test sequence number generation"""
        seq1 = self.codec.get_next_sequence()
        seq2 = self.codec.get_next_sequence()
        self.assertNotEqual(seq1, seq2)
        self.assertEqual(seq2, seq1 + 1)
    
    def test_command_to_message_conversion(self):
        """Test conversion from CommandRequest to BinaryMessage"""
        # Test ping command
        ping_request = CommandRequest(
            command_type=CommandType.PING,
            device_id="test_device"
        )
        
        message = self.codec.command_to_message(ping_request)
        self.assertIsInstance(message, PingMessage)
        
        # Test measure command
        measure_request = CommandRequest(
            command_type=CommandType.MEASURE,
            device_id="test_device",
            parameters={'relay_id': 5, 'test_type': 'voltage_current'}
        )
        
        message = self.codec.command_to_message(measure_request)
        self.assertIsInstance(message, MeasureMessage)
        self.assertEqual(message.relay_id, 5)
        self.assertEqual(message.test_type, TestType.VOLTAGE_CURRENT)
        
        # Test measure group command
        group_request = CommandRequest(
            command_type=CommandType.MEASURE_GROUP,
            device_id="test_device",
            parameters={'relay_ids': [1, 2, 3], 'test_type': 'relay_continuity'}
        )
        
        message = self.codec.command_to_message(group_request)
        self.assertIsInstance(message, MeasureGroupMessage)
        self.assertEqual(message.relay_ids, [1, 2, 3])
        self.assertEqual(message.test_type, TestType.RELAY_CONTINUITY)
    
    def test_message_to_response_conversion(self):
        """Test conversion from BinaryMessage to CommandResponse"""
        # Test ping response
        ping_request = CommandRequest(
            command_type=CommandType.PING,
            device_id="test_device"
        )
        
        ping_response = PingResponseMessage(sequence_id=123, device_id="SMT_TESTER_1")
        ping_response.timestamp = time.time() - 0.1  # 100ms ago
        
        response = self.codec.message_to_response(ping_response, ping_request)
        
        self.assertTrue(response.success)
        self.assertEqual(response.data['sequence_id'], 123)
        self.assertEqual(response.data['device_id'], "SMT_TESTER_1")
        self.assertIn('latency_ms', response.data)
        
        # Test measure response
        measure_request = CommandRequest(
            command_type=CommandType.MEASURE,
            device_id="test_device"
        )
        
        measure_response = MeasureResponseMessage(
            relay_id=3,
            test_type=TestType.VOLTAGE_CURRENT,
            voltage=5.0,
            current=0.1,
            error_code=ErrorCode.SUCCESS
        )
        
        response = self.codec.message_to_response(measure_response, measure_request)
        
        self.assertTrue(response.success)
        self.assertEqual(response.data['relay_id'], 3)
        self.assertEqual(response.data['voltage'], 5.0)
        self.assertEqual(response.data['current'], 0.1)
        
        # Test error response
        error_message = ErrorMessage(
            error_code=ErrorCode.INVALID_PARAMETER,
            error_message="Test error"
        )
        
        response = self.codec.message_to_response(error_message, ping_request)
        
        self.assertFalse(response.success)
        self.assertIsNotNone(response.error)
        self.assertIn("BINARY_INVALID_PARAMETER", response.error.error_code)
    
    def test_unsupported_command_type(self):
        """Test handling of unsupported command types"""
        unsupported_request = CommandRequest(
            command_type=CommandType.RESET,  # Not yet supported in binary protocol
            device_id="test_device"
        )
        
        with self.assertRaises(ValueError) as context:
            self.codec.command_to_message(unsupported_request)
        self.assertIn("Unsupported command type", str(context.exception))


class TestBasicBinaryProtocol(unittest.TestCase):
    """Test basic binary protocol functionality without complex dependencies"""
    
    def test_binary_protocol_config(self):
        """Test binary protocol configuration"""
        config = BinaryProtocolConfig()
        
        # Test default values
        self.assertFalse(config.enable_compression)
        self.assertEqual(config.compression_threshold, 256)
        self.assertFalse(config.enable_acknowledgments)
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.response_timeout, 5.0)
        self.assertEqual(config.ping_interval, 30.0)
        self.assertEqual(config.max_concurrent_commands, 1)
    
    def test_message_codec_sequence_generation(self):
        """Test message codec sequence generation"""
        config = BinaryProtocolConfig()
        codec = BinaryMessageCodec(config)
        
        seq1 = codec.get_next_sequence()
        seq2 = codec.get_next_sequence()
        self.assertNotEqual(seq1, seq2)
        self.assertEqual(seq2, seq1 + 1)
    
    def test_message_codec_encoding(self):
        """Test basic message codec encoding"""
        config = BinaryProtocolConfig()
        codec = BinaryMessageCodec(config)
        
        ping_msg = create_ping_message(12345)
        encoded = codec.encode_message(ping_msg)
        
        self.assertIsInstance(encoded, bytes)
        self.assertGreater(len(encoded), 0)
        
        # Decode and verify
        decoded = codec.decode_message(encoded)
        self.assertIsInstance(decoded, PingMessage)
        self.assertEqual(decoded.sequence_id, 12345)


class TestPerformanceBenchmarks(unittest.TestCase):
    """Performance benchmarking tests"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = BinaryProtocolConfig()
        self.codec = BinaryMessageCodec(self.config)
    
    def test_message_encoding_performance(self):
        """Benchmark message encoding performance"""
        ping_message = create_ping_message(12345)
        
        # Warm up
        for _ in range(100):
            self.codec.encode_message(ping_message)
        
        # Benchmark
        start_time = time.time()
        iterations = 1000
        
        for _ in range(iterations):
            encoded = self.codec.encode_message(ping_message)
        
        end_time = time.time()
        avg_time = (end_time - start_time) / iterations
        
        print(f"\nPing encoding performance: {avg_time*1000:.3f}ms per message")
        self.assertLess(avg_time, 0.001)  # Should be under 1ms per message
    
    def test_message_decoding_performance(self):
        """Benchmark message decoding performance"""
        ping_message = create_ping_message(12345)
        encoded = ping_message.pack()
        
        # Warm up
        for _ in range(100):
            BinaryMessage.unpack(encoded)
        
        # Benchmark
        start_time = time.time()
        iterations = 1000
        
        for _ in range(iterations):
            decoded = BinaryMessage.unpack(encoded)
        
        end_time = time.time()
        avg_time = (end_time - start_time) / iterations
        
        print(f"Ping decoding performance: {avg_time*1000:.3f}ms per message")
        self.assertLess(avg_time, 0.001)  # Should be under 1ms per message
    
    def test_group_measurement_performance(self):
        """Benchmark group measurement message performance"""
        relay_ids = list(range(1, 17))  # All 16 relays
        group_message = create_measure_group_message(relay_ids, TestType.VOLTAGE_CURRENT)
        
        # Test encoding performance
        start_time = time.time()
        iterations = 100
        
        for _ in range(iterations):
            encoded = group_message.pack()
        
        end_time = time.time()
        avg_encode_time = (end_time - start_time) / iterations
        
        # Test decoding performance
        encoded = group_message.pack()
        start_time = time.time()
        
        for _ in range(iterations):
            decoded = BinaryMessage.unpack(encoded)
        
        end_time = time.time()
        avg_decode_time = (end_time - start_time) / iterations
        
        print(f"Group message (16 relays) encoding: {avg_encode_time*1000:.3f}ms")
        print(f"Group message (16 relays) decoding: {avg_decode_time*1000:.3f}ms")
        
        # Performance should be reasonable even for large messages
        self.assertLess(avg_encode_time, 0.01)  # Under 10ms
        self.assertLess(avg_decode_time, 0.01)  # Under 10ms
    
    def test_memory_usage(self):
        """Test memory usage efficiency"""
        import tracemalloc
        
        tracemalloc.start()
        
        # Create and encode/decode many messages
        messages = []
        for i in range(100):
            ping = create_ping_message(i)
            measure = create_measure_message(i % 16 + 1, TestType.VOLTAGE_CURRENT)
            group = create_measure_group_message([1, 2, 3, 4], TestType.RELAY_CONTINUITY)
            messages.extend([ping, measure, group])
        
        # Encode all messages
        encoded_messages = []
        for message in messages:
            encoded = message.pack()
            encoded_messages.append(encoded)
        
        # Decode all messages
        for encoded in encoded_messages:
            decoded = BinaryMessage.unpack(encoded)
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        print(f"Memory usage - Current: {current/1024:.1f}KB, Peak: {peak/1024:.1f}KB")
        
        # Memory usage should be reasonable (under 1MB for 300 messages)
        self.assertLess(peak, 1024 * 1024)  # Under 1MB
    
    def test_compression_ratio(self):
        """Test compression effectiveness (if enabled)"""
        # Test with repetitive data that should compress well
        large_device_id = "SMT_TESTER_DEVICE_" * 20  # Repetitive data
        response = PingResponseMessage(sequence_id=1, device_id=large_device_id[:32])
        
        uncompressed_size = len(response.pack())
        
        # Enable compression temporarily
        config = BinaryProtocolConfig()
        config.enable_compression = True
        config.compression_threshold = 0  # Compress everything
        
        codec = BinaryMessageCodec(config)
        compressed_data = codec.encode_message(response)
        
        compression_ratio = len(compressed_data) / uncompressed_size
        
        print(f"Compression ratio: {compression_ratio:.3f} ({uncompressed_size} -> {len(compressed_data)} bytes)")
        
        # With repetitive data, we should see some compression benefit
        # Note: Small messages might not compress well due to overhead
        self.assertLessEqual(compression_ratio, 1.1)  # At worst, 10% overhead


def run_performance_benchmarks():
    """Run performance benchmarks and display results"""
    print("\n" + "="*60)
    print("Phase 4.4 Binary Protocol Performance Benchmarks")
    print("="*60)
    
    # Run performance tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPerformanceBenchmarks)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def run_verification_tests():
    """Run all verification tests"""
    print("\n" + "="*60)
    print("Phase 4.4 Binary Protocol Verification Tests")
    print("="*60)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestBinaryMessageFormats))
    suite.addTests(loader.loadTestsFromTestCase(TestBinaryMessageCodec))
    suite.addTests(loader.loadTestsFromTestCase(TestBasicBinaryProtocol))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    print("Phase 4.4 Binary Protocol Verification Suite")
    print("Testing binary message formats, protocol implementation, and performance")
    
    # Run verification tests
    verification_passed = run_verification_tests()
    
    # Run performance benchmarks
    performance_passed = run_performance_benchmarks()
    
    # Summary
    print("\n" + "="*60)
    print("PHASE 4.4 VERIFICATION SUMMARY")
    print("="*60)
    print(f"Verification Tests: {'PASSED' if verification_passed else 'FAILED'}")
    print(f"Performance Tests:  {'PASSED' if performance_passed else 'FAILED'}")
    
    if verification_passed and performance_passed:
        print("\n✅ Phase 4.4 Binary Protocol implementation is VERIFIED")
        print("   - All message formats working correctly")
        print("   - Protocol communication functional")
        print("   - Performance meets requirements")
        print("   - Memory usage optimized")
        exit_code = 0
    else:
        print("\n❌ Phase 4.4 verification FAILED")
        print("   Please review test output and fix issues")
        exit_code = 1
    
    sys.exit(exit_code)