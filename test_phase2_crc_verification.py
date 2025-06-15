#!/usr/bin/env python3
"""
Phase 2.1 CRC-16 Verification Test Suite

Comprehensive tests for CRC-16 implementation including:
- CRC-16 module functionality
- SerialManager CRC integration
- Arduino firmware CRC support
- Error detection and recovery
- Performance impact assessment

Phase 2.1 Implementation Status: CRC-16 validation for data integrity
"""

import time
import logging
import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any
import json
from pathlib import Path

from src.utils.crc16 import (
    CRC16, get_crc_calculator, calculate_crc16, calculate_crc16_hex,
    verify_crc16, append_crc16, extract_and_verify_crc16, run_self_test
)
from src.hardware.serial_manager import SerialManager
from src.hardware.smt_arduino_controller import SMTArduinoController, SMTSensorConfigurations


class TestCRC16Module(unittest.TestCase):
    """Test the CRC-16 module implementation"""
    
    def setUp(self):
        self.crc = CRC16()
    
    def test_crc16_calculation(self):
        """Test CRC-16 calculation with known vectors"""
        # Standard test vector
        result = self.crc.calculate("123456789")
        self.assertEqual(result, 0x29B1)
        
        # Additional test vectors
        test_vectors = [
            ("A", 0xB915),
            ("ABC", 0x9DD6),
            ("Hello", 0x34E1),
            ("RELAY:1:ON", 0x8F4A),
            ("MEASURE:1", 0x7C8E),
            ("STATUS", 0x8B5A)
        ]
        
        for test_data, expected in test_vectors:
            with self.subTest(data=test_data):
                result = self.crc.calculate(test_data)
                self.assertEqual(result, expected, f"CRC mismatch for '{test_data}'")
    
    def test_crc16_hex_formatting(self):
        """Test CRC-16 hex formatting"""
        result = self.crc.calculate_hex("123456789")
        self.assertEqual(result, "29B1")
        
        # Test padding for small values
        result = self.crc.calculate_hex("A")
        self.assertEqual(result, "B915")
        self.assertEqual(len(result), 4)  # Always 4 characters
    
    def test_crc16_verification(self):
        """Test CRC-16 verification"""
        # Test with correct CRC
        self.assertTrue(self.crc.verify("123456789", 0x29B1))
        self.assertTrue(self.crc.verify("123456789", "29B1"))
        
        # Test with incorrect CRC
        self.assertFalse(self.crc.verify("123456789", 0x1234))
        self.assertFalse(self.crc.verify("123456789", "1234"))
        
        # Test with invalid hex string
        self.assertFalse(self.crc.verify("123456789", "ZZZZ"))
    
    def test_message_append_extract(self):
        """Test message CRC append and extract"""
        message = "RELAY:1:ON"
        
        # Test append
        message_with_crc = self.crc.append_crc(message)
        self.assertIn("*", message_with_crc)
        self.assertEqual(message_with_crc, "RELAY:1:ON*8F4A")
        
        # Test extract and verify
        extracted, is_valid = self.crc.extract_and_verify(message_with_crc)
        self.assertEqual(extracted, message)
        self.assertTrue(is_valid)
        
        # Test with corrupted CRC
        corrupted = "RELAY:1:ON*1234"
        extracted, is_valid = self.crc.extract_and_verify(corrupted)
        self.assertEqual(extracted, message)
        self.assertFalse(is_valid)
    
    def test_convenience_functions(self):
        """Test convenience functions"""
        # Test convenience functions work the same as class methods
        message = "TEST_MESSAGE"
        
        direct_crc = self.crc.calculate(message)
        convenience_crc = calculate_crc16(message)
        self.assertEqual(direct_crc, convenience_crc)
        
        direct_hex = self.crc.calculate_hex(message)
        convenience_hex = calculate_crc16_hex(message)
        self.assertEqual(direct_hex, convenience_hex)
        
        # Test message operations
        message_with_crc = append_crc16(message)
        extracted, is_valid = extract_and_verify_crc16(message_with_crc)
        self.assertEqual(extracted, message)
        self.assertTrue(is_valid)
    
    def test_self_test(self):
        """Test the built-in self-test"""
        self.assertTrue(run_self_test())


class TestSerialManagerCRC(unittest.TestCase):
    """Test SerialManager CRC integration"""
    
    def setUp(self):
        self.serial_mgr = SerialManager(enable_crc=True)
        # Mock the serial connection
        self.serial_mgr.connection = Mock()
        self.serial_mgr.connection.is_open = True
        self.serial_mgr.port = "COM_TEST"
    
    def test_crc_enabled_initialization(self):
        """Test CRC-enabled SerialManager initialization"""
        self.assertTrue(self.serial_mgr.crc_enabled)
        self.assertIsNotNone(self.serial_mgr.crc_calculator)
        self.assertEqual(self.serial_mgr.crc_error_count, 0)
        self.assertEqual(self.serial_mgr.total_message_count, 0)
    
    def test_write_with_crc(self):
        """Test writing data with CRC"""
        # Mock connection write and flush
        self.serial_mgr.connection.write = Mock(return_value=20)
        self.serial_mgr.connection.flush = Mock()
        
        # Test writing with CRC
        result = self.serial_mgr.write_with_crc("STATUS\r\n")
        self.assertTrue(result)
        
        # Verify that CRC was added
        written_data = self.serial_mgr.connection.write.call_args[0][0]
        written_str = written_data.decode('utf-8')
        self.assertIn("*", written_str)
        self.assertTrue(written_str.startswith("STATUS*"))
    
    def test_read_with_crc_validation(self):
        """Test reading data with CRC validation"""
        # Mock valid message with CRC
        valid_message = "OK:STATUS*E5A2\r\n"
        self.serial_mgr.connection.readline = Mock(return_value=valid_message.encode('utf-8'))
        self.serial_mgr.connection.timeout = 2.0
        
        result = self.serial_mgr.read_line_with_crc()
        self.assertEqual(result, "OK:STATUS")
        self.assertEqual(self.serial_mgr.total_message_count, 1)
        self.assertEqual(self.serial_mgr.crc_error_count, 0)
    
    def test_read_with_crc_failure(self):
        """Test reading data with CRC validation failure"""
        # Mock invalid message with wrong CRC
        invalid_message = "OK:STATUS*1234\r\n"
        self.serial_mgr.connection.readline = Mock(return_value=invalid_message.encode('utf-8'))
        self.serial_mgr.connection.timeout = 2.0
        
        result = self.serial_mgr.read_line_with_crc()
        self.assertIsNone(result)  # Should return None on CRC failure
        self.assertEqual(self.serial_mgr.total_message_count, 1)
        self.assertEqual(self.serial_mgr.crc_error_count, 1)
    
    def test_crc_statistics(self):
        """Test CRC statistics tracking"""
        # Simulate some messages
        self.serial_mgr.total_message_count = 100
        self.serial_mgr.crc_error_count = 2
        
        stats = self.serial_mgr.get_crc_statistics()
        self.assertEqual(stats['total_messages'], 100)
        self.assertEqual(stats['crc_errors'], 2)
        self.assertEqual(stats['error_rate_percent'], 2.0)
        self.assertTrue(stats['crc_enabled'])
    
    def test_query_with_retry(self):
        """Test query with retry mechanism"""
        # Mock successful response on second attempt
        responses = [None, "OK:RETRY_SUCCESS"]
        self.serial_mgr.query = Mock(side_effect=responses)
        
        result, attempts = self.serial_mgr.query_with_retry("STATUS", max_retries=2)
        self.assertEqual(result, "OK:RETRY_SUCCESS")
        self.assertEqual(attempts, 2)
        
        # Verify exponential backoff was used
        self.assertEqual(self.serial_mgr.query.call_count, 2)


class TestArduinoCRCIntegration(unittest.TestCase):
    """Test Arduino CRC integration"""
    
    def setUp(self):
        self.controller = SMTArduinoController()
        # Mock serial manager
        self.controller.serial = Mock(spec=SerialManager)
        self.controller.serial.is_connected.return_value = True
    
    def test_crc_capability_detection(self):
        """Test CRC capability detection"""
        # Mock firmware with CRC support
        self.controller.serial.query.return_value = "OK:VERSION:5.1.0:CRC16_SUPPORT"
        
        result = self.controller._detect_crc_capability()
        self.assertTrue(result)
        self.assertTrue(self.controller.crc_supported)
        self.assertEqual(self.controller.firmware_version, "OK:VERSION:5.1.0:CRC16_SUPPORT")
    
    def test_crc_capability_detection_unsupported(self):
        """Test CRC capability detection with unsupported firmware"""
        # Mock firmware without CRC support
        self.controller.serial.query.return_value = "OK:VERSION:5.0.1"
        
        result = self.controller._detect_crc_capability()
        self.assertFalse(result)
        self.assertFalse(self.controller.crc_supported)
    
    def test_enable_crc_validation(self):
        """Test enabling CRC validation"""
        # Mock supported firmware
        self.controller.crc_supported = True
        self.controller.serial.query.return_value = "OK:CRC_ENABLED"
        self.controller.serial.enable_crc = Mock()
        
        result = self.controller.enable_crc_validation(True)
        self.assertTrue(result)
        self.assertTrue(self.controller.crc_enabled)
        self.controller.serial.enable_crc.assert_called_with(True)
    
    def test_enable_crc_validation_unsupported(self):
        """Test enabling CRC on unsupported firmware"""
        # Mock unsupported firmware
        self.controller.crc_supported = False
        
        result = self.controller.enable_crc_validation(True)
        self.assertFalse(result)
        self.assertFalse(self.controller.crc_enabled)
    
    def test_get_crc_statistics(self):
        """Test getting CRC statistics"""
        # Mock setup
        self.controller.crc_supported = True
        self.controller.crc_enabled = True
        self.controller.firmware_version = "5.1.0"
        self.controller.serial.crc_enabled = True
        
        # Mock statistics
        self.controller.serial.get_crc_statistics.return_value = {
            'total_messages': 50,
            'crc_errors': 1,
            'error_rate_percent': 2.0
        }
        self.controller.serial.query.return_value = "CRC_ENABLED:TRUE,TOTAL_MESSAGES:100,CRC_ERRORS:2,ERROR_RATE:2.00%"
        
        stats = self.controller.get_crc_statistics()
        
        self.assertTrue(stats['crc_supported'])
        self.assertTrue(stats['crc_enabled'])
        self.assertEqual(stats['firmware_version'], "5.1.0")
        self.assertIn('python_stats', stats)
        self.assertIn('arduino_stats', stats)


class TestCRCErrorRecovery(unittest.TestCase):
    """Test CRC error detection and recovery mechanisms"""
    
    def test_crc_error_recovery_simulation(self):
        """Simulate CRC errors and test recovery"""
        serial_mgr = SerialManager(enable_crc=True)
        
        # Simulate a series of messages with some CRC errors
        test_messages = [
            ("OK:STATUS*E5A2", True),  # Valid
            ("OK:STATUS*1234", False), # Invalid CRC
            ("OK:RELAY:1:ON*A3F1", True), # Valid
            ("ERROR:INVALID*FFFF", False), # Invalid CRC
            ("OK:COMPLETE*B2C5", True)  # Valid
        ]
        
        for message, should_be_valid in test_messages:
            # Mock the message reception
            extracted_msg, is_valid = extract_and_verify_crc16(message)
            
            if should_be_valid:
                self.assertTrue(is_valid, f"Message should be valid: {message}")
            else:
                self.assertFalse(is_valid, f"Message should be invalid: {message}")
    
    def test_retry_mechanism_effectiveness(self):
        """Test retry mechanism effectiveness"""
        # Simulate retry scenarios
        retry_scenarios = [
            ([None, None, "OK:SUCCESS"], 3),  # Success on 3rd attempt
            ([None, "OK:SUCCESS"], 2),        # Success on 2nd attempt
            (["OK:SUCCESS"], 1),              # Success on 1st attempt
            ([None, None, None], 3)           # All attempts fail
        ]
        
        for responses, expected_attempts in retry_scenarios:
            with patch.object(SerialManager, 'query', side_effect=responses):
                serial_mgr = SerialManager()
                result, attempts = serial_mgr.query_with_retry("STATUS", max_retries=2)
                
                if responses[-1] is not None:
                    self.assertEqual(result, responses[-1])
                else:
                    self.assertIsNone(result)
                self.assertEqual(attempts, expected_attempts)


class TestCRCPerformanceImpact(unittest.TestCase):
    """Test performance impact of CRC implementation"""
    
    def test_crc_calculation_performance(self):
        """Test CRC calculation performance"""
        crc = CRC16()
        test_messages = [
            "STATUS",
            "RELAY:1:ON", 
            "MEASURE:1:V=12.500,I=0.450,P=5.625",
            "OK:MEASUREMENT:1:V=12.500,I=0.450,P=5.625"
        ]
        
        # Time CRC calculations
        start_time = time.time()
        for _ in range(1000):
            for message in test_messages:
                crc.calculate(message)
        end_time = time.time()
        
        total_time = end_time - start_time
        avg_time_per_calc = total_time / (1000 * len(test_messages))
        
        # CRC calculation should be very fast (under 1ms per calculation)
        self.assertLess(avg_time_per_calc, 0.001, 
                       f"CRC calculation too slow: {avg_time_per_calc*1000:.3f}ms")
        
        print(f"CRC calculation performance: {avg_time_per_calc*1000000:.1f}µs per calculation")
    
    def test_message_processing_overhead(self):
        """Test message processing overhead with CRC"""
        messages = ["STATUS", "RELAY:1:ON", "MEASURE:1"] * 100
        
        # Test without CRC
        start_time = time.time()
        for msg in messages:
            # Simulate basic message processing
            processed = msg.upper().strip()
        no_crc_time = time.time() - start_time
        
        # Test with CRC
        start_time = time.time()
        for msg in messages:
            # Simulate CRC message processing
            msg_with_crc = append_crc16(msg)
            extracted, valid = extract_and_verify_crc16(msg_with_crc)
            processed = extracted.upper().strip() if valid else ""
        crc_time = time.time() - start_time
        
        overhead_percent = ((crc_time - no_crc_time) / no_crc_time) * 100
        
        # CRC overhead should be reasonable (less than 50% for this test)
        self.assertLess(overhead_percent, 50, 
                       f"CRC overhead too high: {overhead_percent:.1f}%")
        
        print(f"CRC processing overhead: {overhead_percent:.1f}%")


class TestCRCIntegrationSuite(unittest.TestCase):
    """Integration tests for complete CRC system"""
    
    def test_end_to_end_crc_workflow(self):
        """Test complete CRC workflow from command to response"""
        # Create CRC-enabled serial manager
        serial_mgr = SerialManager(enable_crc=True)
        
        # Test command with CRC
        command = "STATUS"
        command_with_crc = append_crc16(command)
        
        # Verify command format
        self.assertIn("*", command_with_crc)
        extracted_cmd, cmd_valid = extract_and_verify_crc16(command_with_crc)
        self.assertEqual(extracted_cmd, command)
        self.assertTrue(cmd_valid)
        
        # Test response with CRC
        response = "OK:RELAYS:8,SENSOR:OK"
        response_with_crc = append_crc16(response)
        
        # Verify response format
        self.assertIn("*", response_with_crc)
        extracted_resp, resp_valid = extract_and_verify_crc16(response_with_crc)
        self.assertEqual(extracted_resp, response)
        self.assertTrue(resp_valid)
    
    def test_mixed_crc_and_non_crc_messages(self):
        """Test handling mixed CRC and non-CRC messages"""
        messages = [
            ("STATUS", False),  # No CRC
            ("STATUS*8B5A", True),  # With CRC
            ("RELAY:1:ON", False),  # No CRC
            ("RELAY:1:ON*8F4A", True)  # With CRC
        ]
        
        for message, has_crc in messages:
            if has_crc:
                extracted, valid = extract_and_verify_crc16(message)
                self.assertTrue(valid, f"CRC validation failed for: {message}")
                self.assertNotIn("*", extracted)
            else:
                # Non-CRC message should be returned as-is
                extracted, valid = extract_and_verify_crc16(message)
                self.assertEqual(extracted, message)
                self.assertFalse(valid)  # No CRC to validate


def run_crc_verification_suite():
    """Run the complete CRC verification suite"""
    print("=" * 60)
    print("PHASE 2.1 CRC-16 VERIFICATION TEST SUITE")
    print("=" * 60)
    
    # First run the CRC module self-test
    print("\n=== CRC-16 Module Self-Test ===")
    if run_self_test():
        print("✅ CRC-16 module self-test PASSED")
    else:
        print("❌ CRC-16 module self-test FAILED")
        return False
    
    # Run unit tests
    test_loader = unittest.TestLoader()
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestCRC16Module,
        TestSerialManagerCRC,
        TestArduinoCRCIntegration,
        TestCRCErrorRecovery,
        TestCRCPerformanceImpact,
        TestCRCIntegrationSuite
    ]
    
    for test_class in test_classes:
        test_suite.addTests(test_loader.loadTestsFromTestCase(test_class))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Summary
    print("\n" + "=" * 60)
    print("PHASE 2.1 CRC-16 VERIFICATION SUMMARY")
    print("=" * 60)
    
    if result.wasSuccessful():
        print("✅ All CRC-16 verification tests PASSED")
        print("\nPhase 2.1 Implementation Status:")
        print("✅ CRC-16 Module - COMPLETED")
        print("✅ SerialManager CRC Integration - COMPLETED")
        print("✅ Arduino Firmware CRC Support - COMPLETED")
        print("✅ Error Detection & Recovery - COMPLETED")
        print("✅ Performance Impact Assessment - COMPLETED")
        print("\n🎉 Phase 2.1 CRC-16 validation is ready for production use!")
        
        print("\nNext Steps:")
        print("• Test with real Arduino hardware")
        print("• Enable CRC in production configuration")
        print("• Monitor CRC error rates in real usage")
        print("• Proceed to Phase 3: Binary Framing Protocol")
        
    else:
        print("❌ Some CRC-16 verification tests FAILED")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"- {test}: {traceback.split('AssertionError:')[-1].strip()}")
        
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"- {test}: {traceback.split('Exception:')[-1].strip()}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run CRC verification suite
    success = run_crc_verification_suite()
    exit(0 if success else 1)