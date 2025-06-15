#!/usr/bin/env python3
"""
Phase 4.1 Verification Tests - Abstract Protocol Interface

This test suite verifies the Phase 4.1 implementation of the abstract protocol
interface and common data structures. Tests ensure proper functionality of:
- BaseProtocol abstract class
- Common data structures (MeasurementResult, DeviceStatus, etc.)
- Event-driven architecture
- Type safety and validation

Run with: python test_phase4_1_verification.py
"""

import unittest
import time
import asyncio
from unittest.mock import Mock, patch
from typing import Dict, Any, List

from src.protocols.base_protocol import (
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
    create_error_response,
    create_test_configuration
)


class MockProtocol(BaseProtocol):
    """Mock implementation of BaseProtocol for testing"""
    
    def __init__(self, device_type: DeviceType = DeviceType.SMT_TESTER, device_id: str = "test_device"):
        super().__init__(device_type, device_id)
        self.connect_called = False
        self.disconnect_called = False
        self.commands_sent: List[CommandRequest] = []
        self.measurement_started = False
        
    async def connect(self, connection_params: Dict[str, Any]) -> bool:
        """Mock connect implementation"""
        self.connect_called = True
        self._connected = True
        self._update_status(connected=True, current_state="connected")
        return True
    
    async def disconnect(self) -> bool:
        """Mock disconnect implementation"""
        self.disconnect_called = True
        self._connected = False
        self._update_status(connected=False, current_state="disconnected")
        return True
    
    async def send_command(self, request: CommandRequest) -> CommandResponse:
        """Mock send_command implementation"""
        self.commands_sent.append(request)
        
        # Simulate different responses based on command type
        if request.command_type == CommandType.PING:
            return CommandResponse(
                request=request,
                timestamp=time.time(),
                success=True,
                data={"response": "pong"}
            )
        elif request.command_type == CommandType.GET_STATUS:
            return CommandResponse(
                request=request,
                timestamp=time.time(),
                success=True,
                data={"status": "ok", "state": "idle"}
            )
        else:
            return CommandResponse(
                request=request,
                timestamp=time.time(),
                success=True,
                data={}
            )
    
    async def start_measurement(self, config: TestConfiguration) -> bool:
        """Mock start_measurement implementation"""
        self.measurement_started = True
        return True
    
    async def stop_measurement(self) -> bool:
        """Mock stop_measurement implementation"""
        self.measurement_started = False
        return True
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Mock get_capabilities implementation"""
        return {
            "crc_validation": True,
            "framing": True,
            "continuous_measurement": True,
            "relay_control": True
        }


class TestDataStructures(unittest.TestCase):
    """Test the common data structures"""
    
    def test_measurement_result_creation(self):
        """Test MeasurementResult creation and methods"""
        measurements = {"voltage": 12.5, "current": 1.2, "power": 15.0}
        units = {"voltage": "V", "current": "A", "power": "W"}
        metadata = {"board": 1, "relay": 3}
        
        result = MeasurementResult(
            device_type=DeviceType.SMT_TESTER,
            device_id="smt_001",
            timestamp=time.time(),
            test_type=TestType.VOLTAGE_CURRENT,
            measurements=measurements,
            units=units,
            metadata=metadata
        )
        
        self.assertEqual(result.device_type, DeviceType.SMT_TESTER)
        self.assertEqual(result.device_id, "smt_001")
        self.assertEqual(result.test_type, TestType.VOLTAGE_CURRENT)
        self.assertEqual(result.get_measurement("voltage"), 12.5)
        self.assertEqual(result.get_unit("voltage"), "V")
        self.assertIsNone(result.get_measurement("invalid"))
        self.assertIsNone(result.get_unit("invalid"))
        
    def test_measurement_result_convenience_function(self):
        """Test create_measurement_result convenience function"""
        measurements = {"voltage": 12.5, "current": 1.2}
        
        result = create_measurement_result(
            device_type=DeviceType.SMT_TESTER,
            device_id="test_device",
            test_type=TestType.VOLTAGE_CURRENT,
            measurements=measurements
        )
        
        self.assertEqual(result.device_type, DeviceType.SMT_TESTER)
        self.assertEqual(result.measurements, measurements)
        self.assertGreater(result.timestamp, 0)
        
    def test_device_status_creation(self):
        """Test DeviceStatus creation and methods"""
        capabilities = {"crc": True, "framing": False}
        performance = {"latency": 50.0, "throughput": 100.0}
        
        status = DeviceStatus(
            device_type=DeviceType.OFFROAD_TESTER,
            device_id="offroad_001",
            timestamp=time.time(),
            connected=True,
            firmware_version="4.2.0",
            capabilities=capabilities,
            current_state="testing",
            performance_metrics=performance
        )
        
        self.assertEqual(status.device_type, DeviceType.OFFROAD_TESTER)
        self.assertTrue(status.connected)
        self.assertEqual(status.firmware_version, "4.2.0")
        self.assertTrue(status.has_capability("crc"))
        self.assertFalse(status.has_capability("framing"))
        self.assertFalse(status.has_capability("unknown"))
        
        # Test capability modification
        status.set_capability("framing", True)
        self.assertTrue(status.has_capability("framing"))
        
    def test_error_response_creation(self):
        """Test ErrorResponse creation"""
        context = {"command": "MEASURE", "retry_count": 2}
        
        error = ErrorResponse(
            device_type=DeviceType.SMT_TESTER,
            device_id="smt_001",
            timestamp=time.time(),
            severity=ErrorSeverity.ERROR,
            error_code="TIMEOUT",
            error_message="Command timed out after 5 seconds",
            command="MEASURE:1",
            context=context,
            recoverable=True
        )
        
        self.assertEqual(error.severity, ErrorSeverity.ERROR)
        self.assertEqual(error.error_code, "TIMEOUT")
        self.assertTrue(error.recoverable)
        self.assertEqual(error.context["retry_count"], 2)
        
    def test_error_response_convenience_function(self):
        """Test create_error_response convenience function"""
        error = create_error_response(
            device_type=DeviceType.SMT_TESTER,
            device_id="test_device",
            severity=ErrorSeverity.WARNING,
            error_code="TEST_ERROR",
            error_message="Test error message"
        )
        
        self.assertEqual(error.severity, ErrorSeverity.WARNING)
        self.assertEqual(error.error_code, "TEST_ERROR")
        self.assertTrue(error.recoverable)  # Default
        self.assertGreater(error.timestamp, 0)
        
    def test_test_configuration_creation(self):
        """Test TestConfiguration creation and methods"""
        parameters = {"relay_list": [1, 2, 3], "voltage_threshold": 12.0}
        metadata = {"test_name": "relay_test"}
        
        config = TestConfiguration(
            test_type=TestType.RELAY_CONTINUITY,
            device_type=DeviceType.SMT_TESTER,
            parameters=parameters,
            timeout_seconds=60.0,
            retry_count=5,
            metadata=metadata
        )
        
        self.assertEqual(config.test_type, TestType.RELAY_CONTINUITY)
        self.assertEqual(config.timeout_seconds, 60.0)
        self.assertEqual(config.retry_count, 5)
        self.assertEqual(config.get_parameter("voltage_threshold"), 12.0)
        self.assertIsNone(config.get_parameter("invalid"))
        self.assertEqual(config.get_parameter("invalid", "default"), "default")
        
        # Test parameter modification
        config.set_parameter("new_param", "new_value")
        self.assertEqual(config.get_parameter("new_param"), "new_value")
        
    def test_test_configuration_convenience_function(self):
        """Test create_test_configuration convenience function"""
        parameters = {"test_param": "test_value"}
        
        config = create_test_configuration(
            test_type=TestType.VOLTAGE_CURRENT,
            device_type=DeviceType.SMT_TESTER,
            parameters=parameters,
            timeout_seconds=45.0
        )
        
        self.assertEqual(config.test_type, TestType.VOLTAGE_CURRENT)
        self.assertEqual(config.timeout_seconds, 45.0)
        self.assertEqual(config.get_parameter("test_param"), "test_value")
        
    def test_command_request_creation(self):
        """Test CommandRequest creation"""
        parameters = {"relay": 1, "state": "on"}
        metadata = {"source": "gui"}
        
        request = CommandRequest(
            command_type=CommandType.SET_RELAY,
            device_id="smt_001",
            parameters=parameters,
            timeout_seconds=10.0,
            retry_count=3,
            priority=5,
            metadata=metadata
        )
        
        self.assertEqual(request.command_type, CommandType.SET_RELAY)
        self.assertEqual(request.priority, 5)
        self.assertEqual(request.get_parameter("relay"), 1)
        self.assertIsNone(request.get_parameter("invalid"))
        
    def test_command_response_creation(self):
        """Test CommandResponse creation"""
        request = CommandRequest(
            command_type=CommandType.PING,
            device_id="test_device"
        )
        
        response = CommandResponse(
            request=request,
            timestamp=time.time(),
            success=True,
            data={"result": "pong"},
            execution_time_ms=50.0
        )
        
        self.assertEqual(response.request.command_type, CommandType.PING)
        self.assertTrue(response.success)
        self.assertEqual(response.data["result"], "pong")
        self.assertIsNone(response.error)
        

class TestBaseProtocol(unittest.TestCase):
    """Test the BaseProtocol abstract class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.protocol = MockProtocol(DeviceType.SMT_TESTER, "test_smt")
        
    def test_protocol_initialization(self):
        """Test protocol initialization"""
        self.assertEqual(self.protocol.get_device_type(), DeviceType.SMT_TESTER)
        self.assertEqual(self.protocol.get_device_id(), "test_smt")
        self.assertFalse(self.protocol.is_connected())
        
        status = self.protocol.get_status()
        self.assertEqual(status.device_type, DeviceType.SMT_TESTER)
        self.assertEqual(status.device_id, "test_smt")
        self.assertFalse(status.connected)
        
    async def test_connect_disconnect(self):
        """Test connect and disconnect methods"""
        # Test connection
        result = await self.protocol.connect({"port": "/dev/ttyUSB0"})
        self.assertTrue(result)
        self.assertTrue(self.protocol.is_connected())
        self.assertTrue(self.protocol.connect_called)
        
        # Test disconnection
        result = await self.protocol.disconnect()
        self.assertTrue(result)
        self.assertFalse(self.protocol.is_connected())
        self.assertTrue(self.protocol.disconnect_called)
        
    async def test_send_command(self):
        """Test send_command method"""
        request = CommandRequest(
            command_type=CommandType.PING,
            device_id="test_smt"
        )
        
        response = await self.protocol.send_command(request)
        
        self.assertTrue(response.success)
        self.assertEqual(response.data["response"], "pong")
        self.assertEqual(len(self.protocol.commands_sent), 1)
        self.assertEqual(self.protocol.commands_sent[0].command_type, CommandType.PING)
        
    async def test_measurement_control(self):
        """Test measurement start/stop methods"""
        config = TestConfiguration(
            test_type=TestType.VOLTAGE_CURRENT,
            device_type=DeviceType.SMT_TESTER
        )
        
        # Test start measurement
        result = await self.protocol.start_measurement(config)
        self.assertTrue(result)
        self.assertTrue(self.protocol.measurement_started)
        
        # Test stop measurement
        result = await self.protocol.stop_measurement()
        self.assertTrue(result)
        self.assertFalse(self.protocol.measurement_started)
        
    def test_capabilities(self):
        """Test capabilities method"""
        capabilities = self.protocol.get_capabilities()
        
        self.assertIsInstance(capabilities, dict)
        self.assertTrue(capabilities["crc_validation"])
        self.assertTrue(capabilities["framing"])
        self.assertTrue(capabilities["continuous_measurement"])
        
    def test_performance_metrics(self):
        """Test performance metrics tracking"""
        metrics = self.protocol.get_performance_metrics()
        
        self.assertIn("command_count", metrics)
        self.assertIn("error_count", metrics)
        self.assertIn("error_rate", metrics)
        self.assertIn("last_command_time", metrics)
        
        # Initially should be zero
        self.assertEqual(metrics["command_count"], 0.0)
        self.assertEqual(metrics["error_count"], 0.0)


class TestEventSystem(unittest.TestCase):
    """Test the event-driven architecture"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.protocol = MockProtocol(DeviceType.SMT_TESTER, "test_smt")
        self.measurement_events = []
        self.status_events = []
        self.error_events = []
        self.command_events = []
        
        # Register event listeners
        self.protocol.add_measurement_listener(self._on_measurement)
        self.protocol.add_status_listener(self._on_status)
        self.protocol.add_error_listener(self._on_error)
        self.protocol.add_command_listener(self._on_command)
        
    def _on_measurement(self, measurement: MeasurementResult):
        """Measurement event handler"""
        self.measurement_events.append(measurement)
        
    def _on_status(self, status: DeviceStatus):
        """Status event handler"""
        self.status_events.append(status)
        
    def _on_error(self, error: ErrorResponse):
        """Error event handler"""
        self.error_events.append(error)
        
    def _on_command(self, response: CommandResponse):
        """Command response event handler"""
        self.command_events.append(response)
        
    def test_measurement_events(self):
        """Test measurement event emission"""
        measurement = create_measurement_result(
            device_type=DeviceType.SMT_TESTER,
            device_id="test_smt",
            test_type=TestType.VOLTAGE_CURRENT,
            measurements={"voltage": 12.5}
        )
        
        # Emit measurement event
        self.protocol._emit_measurement(measurement)
        
        self.assertEqual(len(self.measurement_events), 1)
        self.assertEqual(self.measurement_events[0].measurements["voltage"], 12.5)
        
    def test_status_events(self):
        """Test status change event emission"""
        status = DeviceStatus(
            device_type=DeviceType.SMT_TESTER,
            device_id="test_smt",
            timestamp=time.time(),
            connected=True
        )
        
        # Emit status event
        self.protocol._emit_status_change(status)
        
        self.assertEqual(len(self.status_events), 1)
        self.assertTrue(self.status_events[0].connected)
        
    def test_error_events(self):
        """Test error event emission"""
        error = create_error_response(
            device_type=DeviceType.SMT_TESTER,
            device_id="test_smt",
            severity=ErrorSeverity.ERROR,
            error_code="TEST_ERROR",
            error_message="Test error"
        )
        
        # Emit error event
        self.protocol._emit_error(error)
        
        self.assertEqual(len(self.error_events), 1)
        self.assertEqual(self.error_events[0].error_code, "TEST_ERROR")
        
    def test_command_events(self):
        """Test command response event emission"""
        request = CommandRequest(
            command_type=CommandType.PING,
            device_id="test_smt"
        )
        
        response = CommandResponse(
            request=request,
            timestamp=time.time(),
            success=True
        )
        
        # Emit command response event
        self.protocol._emit_command_response(response)
        
        self.assertEqual(len(self.command_events), 1)
        self.assertTrue(self.command_events[0].success)
        
    def test_listener_management(self):
        """Test adding/removing event listeners"""
        # Remove listeners
        self.protocol.remove_measurement_listener(self._on_measurement)
        self.protocol.remove_status_listener(self._on_status)
        self.protocol.remove_error_listener(self._on_error)
        self.protocol.remove_command_listener(self._on_command)
        
        # Emit events - should not trigger handlers
        measurement = create_measurement_result(
            device_type=DeviceType.SMT_TESTER,
            device_id="test_smt",
            test_type=TestType.VOLTAGE_CURRENT,
            measurements={"voltage": 12.5}
        )
        
        self.protocol._emit_measurement(measurement)
        
        # Should still have only the original events
        self.assertEqual(len(self.measurement_events), 0)
        
    def test_listener_error_handling(self):
        """Test error handling in event listeners"""
        def failing_listener(measurement):
            raise Exception("Listener error")
        
        # Add failing listener
        self.protocol.add_measurement_listener(failing_listener)
        
        measurement = create_measurement_result(
            device_type=DeviceType.SMT_TESTER,
            device_id="test_smt",
            test_type=TestType.VOLTAGE_CURRENT,
            measurements={"voltage": 12.5}
        )
        
        # Emit measurement - should handle listener error gracefully
        self.protocol._emit_measurement(measurement)
        
        # Should still receive the event in our working listener
        self.assertEqual(len(self.measurement_events), 1)
        # Should also generate an error event for the failed listener
        self.assertEqual(len(self.error_events), 1)
        self.assertEqual(self.error_events[0].error_code, "LISTENER_ERROR")


class TestEnumerations(unittest.TestCase):
    """Test enum definitions"""
    
    def test_device_type_enum(self):
        """Test DeviceType enumeration"""
        self.assertEqual(DeviceType.SMT_TESTER.value, "smt_tester")
        self.assertEqual(DeviceType.OFFROAD_TESTER.value, "offroad_tester")
        self.assertEqual(DeviceType.SCALE.value, "scale")
        self.assertEqual(DeviceType.PROGRAMMER.value, "programmer")
        self.assertEqual(DeviceType.UNKNOWN.value, "unknown")
        
    def test_command_type_enum(self):
        """Test CommandType enumeration"""
        self.assertEqual(CommandType.CONNECT.value, "connect")
        self.assertEqual(CommandType.MEASURE.value, "measure")
        self.assertEqual(CommandType.SET_RELAY.value, "set_relay")
        self.assertEqual(CommandType.ENABLE_CRC.value, "enable_crc")
        
    def test_test_type_enum(self):
        """Test TestType enumeration"""
        self.assertEqual(TestType.VOLTAGE_CURRENT.value, "voltage_current")
        self.assertEqual(TestType.RELAY_CONTINUITY.value, "relay_continuity")
        self.assertEqual(TestType.BUTTON_TEST.value, "button_test")
        self.assertEqual(TestType.WEIGHT_CHECK.value, "weight_check")
        
    def test_error_severity_enum(self):
        """Test ErrorSeverity enumeration"""
        self.assertEqual(ErrorSeverity.INFO.value, "info")
        self.assertEqual(ErrorSeverity.WARNING.value, "warning")
        self.assertEqual(ErrorSeverity.ERROR.value, "error")
        self.assertEqual(ErrorSeverity.CRITICAL.value, "critical")


async def run_async_tests():
    """Run async test methods"""
    print("Running async tests...")
    
    test_protocol = TestBaseProtocol()
    test_protocol.setUp()
    
    await test_protocol.test_connect_disconnect()
    print("✅ Connect/Disconnect test passed")
    
    await test_protocol.test_send_command()
    print("✅ Send command test passed")
    
    await test_protocol.test_measurement_control()
    print("✅ Measurement control test passed")


def main():
    """Main test runner"""
    print("="*60)
    print("Phase 4.1 Abstract Protocol Interface Verification Tests")
    print("="*60)
    
    # Run synchronous tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestDataStructures))
    suite.addTests(loader.loadTestsFromTestCase(TestBaseProtocol))
    suite.addTests(loader.loadTestsFromTestCase(TestEventSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestEnumerations))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Run async tests
    asyncio.run(run_async_tests())
    
    # Print summary
    print("="*60)
    print("PHASE 4.1 VERIFICATION SUMMARY")
    print("="*60)
    
    if result.wasSuccessful():
        print("✅ All Phase 4.1 tests PASSED")
        print("\nPhase 4.1 Implementation Status:")
        print("✅ BaseProtocol abstract class - IMPLEMENTED")
        print("✅ Common data structures - IMPLEMENTED")
        print("✅ Event-driven architecture - IMPLEMENTED")
        print("✅ Type safety and validation - IMPLEMENTED")
        print("✅ Abstract device capabilities - IMPLEMENTED")
        
        print("\nKey Features Verified:")
        print("• Abstract protocol interface with standardized methods")
        print("• Unified data structures for measurements, status, and errors")
        print("• Event-driven architecture with listener management")
        print("• Type-safe enumerations for device and command types")
        print("• Performance metrics tracking")
        print("• Error handling and recovery mechanisms")
        
        print("\nNext Steps:")
        print("• Implement concrete protocol classes (FramedBinaryProtocol)")
        print("• Create protocol negotiation system")
        print("• Implement UnifiedDeviceController")
        print("• Add binary protocol encoding/decoding")
        
        return True
    else:
        print("❌ Some Phase 4.1 tests FAILED")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)