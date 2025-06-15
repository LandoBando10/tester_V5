#!/usr/bin/env python3
"""
Phase 4.3 Verification Test Suite

This test suite verifies the implementation of the Device Abstraction layer including:
- UnifiedDeviceController functionality
- DeviceManager with connection pooling
- Automatic device detection
- Health monitoring and status tracking
- Load balancing strategies
"""

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import time
import serial.tools.list_ports

# Add src to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.controllers.unified_controller import (
    UnifiedDeviceController, DeviceInfo, DeviceConnectionState
)
from src.controllers.device_manager import (
    DeviceManager, DevicePoolConfig, LoadBalancingStrategy, DeviceHealth
)
from src.protocols.base_protocol import (
    BaseProtocol, CommandRequest, CommandResponse, 
    MeasurementResult, DeviceStatus, ErrorResponse,
    DeviceType, CommandType, ErrorSeverity
)
from src.protocols.protocol_manager import ProtocolManager


def create_command_response(success=True, data=None, error=None):
    """Helper to create CommandResponse objects for testing."""
    return CommandResponse(
        request=CommandRequest(CommandType.GET_STATUS, 'TEST'),
        timestamp=time.time(),
        success=success,
        data=data or {},
        error=error
    )


class TestUnifiedDeviceController(unittest.TestCase):
    """Test UnifiedDeviceController functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.controller = UnifiedDeviceController()
        self.mock_protocol_manager = Mock(spec=ProtocolManager)
        self.controller.protocol_manager = self.mock_protocol_manager
        
    def test_initialization(self):
        """Test controller initialization."""
        self.assertIsNotNone(self.controller)
        self.assertEqual(len(self.controller.devices), 0)
        self.assertEqual(len(self.controller.protocols), 0)
        
    async def test_connect_device_success(self):
        """Test successful device connection."""
        # Mock protocol
        mock_protocol = AsyncMock(spec=BaseProtocol)
        mock_protocol.add_event_listener = Mock()
        mock_protocol.get_capabilities = Mock(return_value={
            'crc_supported': True,
            'framing_supported': True
        })
        mock_protocol.add_event_listener = Mock()
        mock_protocol.execute_command = AsyncMock(return_value=create_command_response(
            success=True,
            data={'version': '5.2.0', 'response': 'BOARD_TYPE:SMT_V5'}
        ))
        
        # Mock protocol manager
        self.mock_protocol_manager.create_protocol = AsyncMock(
            return_value=mock_protocol
        )
        
        # Connect device
        success = await self.controller.connect_device('/dev/ttyUSB0')
        
        self.assertTrue(success)
        self.assertIn('/dev/ttyUSB0', self.controller.devices)
        self.assertIn('/dev/ttyUSB0', self.controller.protocols)
        
        device_info = self.controller.devices['/dev/ttyUSB0']
        self.assertEqual(device_info.device_type, DeviceType.SMT_TESTER)
        self.assertEqual(device_info.firmware_version, '5.2.0')
        self.assertEqual(device_info.connection_state, DeviceConnectionState.CONNECTED)
        
    async def test_connect_device_failure(self):
        """Test failed device connection."""
        # Mock protocol manager to fail
        self.mock_protocol_manager.create_protocol = AsyncMock(
            return_value=None
        )
        
        # Connect device
        success = await self.controller.connect_device('/dev/ttyUSB0')
        
        self.assertFalse(success)
        self.assertIn('/dev/ttyUSB0', self.controller.devices)
        device_info = self.controller.devices['/dev/ttyUSB0']
        self.assertEqual(device_info.connection_state, DeviceConnectionState.ERROR)
        
    async def test_auto_device_detection_smt(self):
        """Test automatic SMT device detection."""
        # Mock protocol
        mock_protocol = AsyncMock(spec=BaseProtocol)
        mock_protocol.add_event_listener = Mock()
        
        # First query returns SMT board type
        mock_protocol.execute_command = AsyncMock(side_effect=[
            create_command_response(
                success=True,
                data={'response': 'BOARD_TYPE:SMT_TESTER_V5'}
            ),
            create_command_response(
                success=True,
                data={'version': '5.2.0'}
            )
        ])
        
        self.mock_protocol_manager.create_protocol = AsyncMock(
            return_value=mock_protocol
        )
        
        # Connect without specifying device type
        success = await self.controller.connect_device('/dev/ttyUSB0')
        
        self.assertTrue(success)
        device_info = self.controller.devices['/dev/ttyUSB0']
        self.assertEqual(device_info.device_type, DeviceType.SMT_TESTER)
        
    async def test_auto_device_detection_offroad(self):
        """Test automatic Offroad device detection."""
        # Mock protocol
        mock_protocol = AsyncMock(spec=BaseProtocol)
        mock_protocol.add_event_listener = Mock()
        
        # First query fails (not SMT), second returns Offroad status
        mock_protocol.execute_command = AsyncMock(side_effect=[
            create_command_response(success=False),
            create_command_response(
                success=True,
                data={'state': 'IDLE', 'duty_cycle': 0}
            ),
            create_command_response(
                success=True,
                data={'version': '4.2.0'}
            )
        ])
        
        self.mock_protocol_manager.create_protocol = AsyncMock(
            return_value=mock_protocol
        )
        
        # Connect without specifying device type
        success = await self.controller.connect_device('/dev/ttyUSB0')
        
        self.assertTrue(success)
        device_info = self.controller.devices['/dev/ttyUSB0']
        self.assertEqual(device_info.device_type, DeviceType.OFFROAD_TESTER)
        
    async def test_disconnect_device(self):
        """Test device disconnection."""
        # First connect a device
        mock_protocol = AsyncMock(spec=BaseProtocol)
        mock_protocol.get_capabilities.return_value = {}
        mock_protocol.execute_command = AsyncMock(return_value=create_command_response(
            success=True,
            data={'version': '5.2.0'}
        ))
        mock_protocol.disconnect = AsyncMock()
        
        self.mock_protocol_manager.create_protocol = AsyncMock(
            return_value=mock_protocol
        )
        
        await self.controller.connect_device('/dev/ttyUSB0', DeviceType.SMT_TESTER)
        
        # Now disconnect
        await self.controller.disconnect_device('/dev/ttyUSB0')
        
        mock_protocol.disconnect.assert_called_once()
        self.assertNotIn('/dev/ttyUSB0', self.controller.protocols)
        device_info = self.controller.devices['/dev/ttyUSB0']
        self.assertEqual(device_info.connection_state, DeviceConnectionState.DISCONNECTED)
        
    async def test_execute_command(self):
        """Test command execution."""
        # Set up connected device
        mock_protocol = AsyncMock(spec=BaseProtocol)
        self.controller.protocols['/dev/ttyUSB0'] = mock_protocol
        self.controller.devices['/dev/ttyUSB0'] = DeviceInfo(
            device_type=DeviceType.SMT_TESTER,
            port='/dev/ttyUSB0'
        )
        
        # Mock command response
        mock_protocol.execute_command = AsyncMock(return_value=create_command_response(
            success=True,
            data={'result': 'OK'}
        ))
        
        # Execute command
        response = await self.controller.execute_command(
            '/dev/ttyUSB0', 
            'TEST_COMMAND',
            {'param': 'value'}
        )
        
        self.assertTrue(response.success)
        self.assertEqual(response.data['result'], 'OK')
        
        # Verify command was called correctly
        call_args = mock_protocol.execute_command.call_args[0][0]
        self.assertEqual(call_args.command, 'TEST_COMMAND')
        self.assertEqual(call_args.parameters['param'], 'value')
        
    async def test_execute_command_not_connected(self):
        """Test command execution on disconnected device."""
        response = await self.controller.execute_command(
            '/dev/ttyUSB0',
            'TEST_COMMAND'
        )
        
        self.assertFalse(response.success)
        self.assertEqual(response.error.code, 'NOT_CONNECTED')
        
    async def test_measure_relays(self):
        """Test relay measurement."""
        # Set up connected SMT device
        mock_protocol = AsyncMock(spec=BaseProtocol)
        self.controller.protocols['/dev/ttyUSB0'] = mock_protocol
        self.controller.devices['/dev/ttyUSB0'] = DeviceInfo(
            device_type=DeviceType.SMT_TESTER,
            port='/dev/ttyUSB0'
        )
        
        # Mock measurement responses
        mock_protocol.execute_command = AsyncMock(side_effect=[
            create_command_response(
                success=True,
                data={
                    'measurement': MeasurementResult(
                        voltage=12.5,
                        current=0.5,
                        power=6.25
                    )
                }
            ),
            create_command_response(
                success=True,
                data={
                    'measurement': MeasurementResult(
                        voltage=5.0,
                        current=1.0,
                        power=5.0
                    )
                }
            )
        ])
        
        # Measure relays
        results = await self.controller.measure_relays('/dev/ttyUSB0', [1, 2])
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[1].voltage, 12.5)
        self.assertEqual(results[2].voltage, 5.0)
        
    async def test_connection_callbacks(self):
        """Test connection state callbacks."""
        callback_states = []
        
        def connection_callback(port, state):
            callback_states.append((port, state))
            
        self.controller.add_connection_callback(connection_callback)
        
        # Mock protocol
        mock_protocol = AsyncMock(spec=BaseProtocol)
        mock_protocol.add_event_listener = Mock()
        mock_protocol.get_capabilities.return_value = {}
        mock_protocol.execute_command = AsyncMock(return_value=create_command_response(
            success=True,
            data={'version': '5.2.0'}
        ))
        
        self.mock_protocol_manager.create_protocol = AsyncMock(
            return_value=mock_protocol
        )
        
        # Connect device
        await self.controller.connect_device('/dev/ttyUSB0', DeviceType.SMT_TESTER)
        
        # Check callbacks were called
        self.assertIn(('/dev/ttyUSB0', DeviceConnectionState.CONNECTING), callback_states)
        self.assertIn(('/dev/ttyUSB0', DeviceConnectionState.CONNECTED), callback_states)
        
    async def test_reconnect_device(self):
        """Test device reconnection."""
        # First connect a device
        mock_protocol = AsyncMock(spec=BaseProtocol)
        mock_protocol.get_capabilities.return_value = {}
        mock_protocol.execute_command = AsyncMock(return_value=create_command_response(
            success=True,
            data={'version': '5.2.0'}
        ))
        mock_protocol.disconnect = AsyncMock()
        
        self.mock_protocol_manager.create_protocol = AsyncMock(
            return_value=mock_protocol
        )
        
        await self.controller.connect_device('/dev/ttyUSB0', DeviceType.SMT_TESTER)
        
        # Reconnect
        success = await self.controller.reconnect_device('/dev/ttyUSB0')
        
        self.assertTrue(success)
        # Should have disconnected and reconnected
        mock_protocol.disconnect.assert_called_once()
        self.assertEqual(self.mock_protocol_manager.get_protocol_for_port.call_count, 2)
        
    def test_device_statistics(self):
        """Test device statistics retrieval."""
        # Set up device
        device_info = DeviceInfo(
            device_type=DeviceType.SMT_TESTER,
            port='/dev/ttyUSB0',
            firmware_version='5.2.0',
            success_count=100,
            error_count=5
        )
        self.controller.devices['/dev/ttyUSB0'] = device_info
        
        # Get statistics
        stats = self.controller.get_device_statistics('/dev/ttyUSB0')
        
        self.assertIsNotNone(stats)
        self.assertEqual(stats['device_type'], 'SMT_TESTER')
        self.assertEqual(stats['firmware_version'], '5.2.0')
        self.assertEqual(stats['success_count'], 100)
        self.assertEqual(stats['error_count'], 5)
        self.assertAlmostEqual(stats['success_rate'], 0.952, places=3)


class TestDeviceManager(unittest.TestCase):
    """Test DeviceManager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = DevicePoolConfig(
            auto_discovery=False,  # Disable for testing
            health_check_interval=0.1,
            discovery_interval=0.1
        )
        self.manager = DeviceManager(self.config)
        self.manager.controller = Mock(spec=UnifiedDeviceController)
        
    def test_initialization(self):
        """Test manager initialization."""
        self.assertIsNotNone(self.manager)
        self.assertEqual(len(self.manager.device_pools), 0)
        self.assertEqual(len(self.manager.device_health), 0)
        
    async def test_start_stop(self):
        """Test manager start and stop."""
        # Mock controller methods
        self.manager.controller.disconnect_device = AsyncMock()
        
        # Start manager
        await self.manager.start()
        
        # Check tasks were created
        self.assertIsNotNone(self.manager._health_check_task)
        self.assertIsNotNone(self.manager._reconnect_task)
        
        # Stop manager
        await self.manager.stop()
        
        # Check shutdown event was set
        self.assertTrue(self.manager._shutdown_event.is_set())
        
    def test_handle_connection_change_connected(self):
        """Test handling device connection."""
        # Mock device info
        mock_device_info = DeviceInfo(
            device_type=DeviceType.SMT_TESTER,
            port='/dev/ttyUSB0'
        )
        self.manager.controller.get_device_info = Mock(return_value=mock_device_info)
        
        # Handle connection
        self.manager._handle_connection_change(
            '/dev/ttyUSB0',
            DeviceConnectionState.CONNECTED
        )
        
        # Check device was added to pool
        self.assertIn('/dev/ttyUSB0', self.manager.device_pools[DeviceType.SMT_TESTER])
        self.assertIn('/dev/ttyUSB0', self.manager.device_health)
        
    def test_handle_connection_change_pool_full(self):
        """Test handling connection when pool is full."""
        # Fill the pool
        self.config.max_devices_per_type = 1
        self.manager.device_pools[DeviceType.SMT_TESTER].add('/dev/ttyUSB1')
        
        # Mock device info
        mock_device_info = DeviceInfo(
            device_type=DeviceType.SMT_TESTER,
            port='/dev/ttyUSB0'
        )
        self.manager.controller.get_device_info = Mock(return_value=mock_device_info)
        self.manager.controller.disconnect_device = AsyncMock()
        
        # Handle connection
        self.manager._handle_connection_change(
            '/dev/ttyUSB0',
            DeviceConnectionState.CONNECTED
        )
        
        # Check device was not added to pool
        self.assertNotIn('/dev/ttyUSB0', self.manager.device_pools[DeviceType.SMT_TESTER])
        
    def test_handle_connection_change_disconnected(self):
        """Test handling device disconnection."""
        # Add device to pools
        self.manager.device_pools[DeviceType.SMT_TESTER].add('/dev/ttyUSB0')
        
        # Handle disconnection
        self.manager._handle_connection_change(
            '/dev/ttyUSB0',
            DeviceConnectionState.DISCONNECTED
        )
        
        # Check device was removed from pool
        self.assertNotIn('/dev/ttyUSB0', self.manager.device_pools[DeviceType.SMT_TESTER])
        
    async def test_add_device(self):
        """Test manually adding a device."""
        # Mock controller
        self.manager.controller.connect_device = AsyncMock(return_value=True)
        
        # Add device
        success = await self.manager.add_device('/dev/ttyUSB0', DeviceType.SMT_TESTER)
        
        self.assertTrue(success)
        self.assertIn('/dev/ttyUSB0', self.manager.known_ports)
        
    async def test_remove_device(self):
        """Test removing a device."""
        # Add device first
        self.manager.known_ports.add('/dev/ttyUSB0')
        self.manager.device_pools[DeviceType.SMT_TESTER].add('/dev/ttyUSB0')
        self.manager.device_health['/dev/ttyUSB0'] = DeviceHealth('/dev/ttyUSB0')
        
        # Mock controller
        self.manager.controller.disconnect_device = AsyncMock()
        
        # Remove device
        await self.manager.remove_device('/dev/ttyUSB0')
        
        self.assertNotIn('/dev/ttyUSB0', self.manager.known_ports)
        self.assertNotIn('/dev/ttyUSB0', self.manager.device_pools[DeviceType.SMT_TESTER])
        self.assertNotIn('/dev/ttyUSB0', self.manager.device_health)
        
    def test_get_available_device_round_robin(self):
        """Test round robin device selection."""
        self.config.load_balancing_strategy = LoadBalancingStrategy.ROUND_ROBIN
        
        # Add devices to pool
        self.manager.device_pools[DeviceType.SMT_TESTER] = {'/dev/ttyUSB0', '/dev/ttyUSB1'}
        self.manager.device_health['/dev/ttyUSB0'] = DeviceHealth('/dev/ttyUSB0')
        self.manager.device_health['/dev/ttyUSB1'] = DeviceHealth('/dev/ttyUSB1')
        
        # Mock controller
        self.manager.controller.is_connected = Mock(return_value=True)
        
        # Get devices in round robin order
        device1 = self.manager.get_available_device(DeviceType.SMT_TESTER)
        device2 = self.manager.get_available_device(DeviceType.SMT_TESTER)
        device3 = self.manager.get_available_device(DeviceType.SMT_TESTER)
        
        # Should alternate between devices
        self.assertNotEqual(device1, device2)
        self.assertEqual(device1, device3)
        
    def test_get_available_device_least_used(self):
        """Test least used device selection."""
        self.config.load_balancing_strategy = LoadBalancingStrategy.LEAST_USED
        
        # Add devices to pool
        self.manager.device_pools[DeviceType.SMT_TESTER] = {'/dev/ttyUSB0', '/dev/ttyUSB1'}
        self.manager.device_health['/dev/ttyUSB0'] = DeviceHealth('/dev/ttyUSB0')
        self.manager.device_health['/dev/ttyUSB1'] = DeviceHealth('/dev/ttyUSB1')
        self.manager.device_usage_count['/dev/ttyUSB0'] = 10
        self.manager.device_usage_count['/dev/ttyUSB1'] = 5
        
        # Mock controller
        self.manager.controller.is_connected = Mock(return_value=True)
        
        # Get device - should select least used
        device = self.manager.get_available_device(DeviceType.SMT_TESTER)
        
        self.assertEqual(device, '/dev/ttyUSB1')
        self.assertEqual(self.manager.device_usage_count['/dev/ttyUSB1'], 6)
        
    def test_get_available_device_fastest_response(self):
        """Test fastest response device selection."""
        self.config.load_balancing_strategy = LoadBalancingStrategy.FASTEST_RESPONSE
        
        # Add devices to pool
        self.manager.device_pools[DeviceType.SMT_TESTER] = {'/dev/ttyUSB0', '/dev/ttyUSB1'}
        self.manager.device_health['/dev/ttyUSB0'] = DeviceHealth('/dev/ttyUSB0')
        self.manager.device_health['/dev/ttyUSB1'] = DeviceHealth('/dev/ttyUSB1')
        self.manager.device_health['/dev/ttyUSB0'].average_response_time = 0.5
        self.manager.device_health['/dev/ttyUSB1'].average_response_time = 0.2
        
        # Mock controller
        self.manager.controller.is_connected = Mock(return_value=True)
        
        # Get device - should select fastest
        device = self.manager.get_available_device(DeviceType.SMT_TESTER)
        
        self.assertEqual(device, '/dev/ttyUSB1')
        
    def test_get_available_device_unhealthy_filtered(self):
        """Test unhealthy devices are filtered out."""
        # Add devices to pool
        self.manager.device_pools[DeviceType.SMT_TESTER] = {'/dev/ttyUSB0', '/dev/ttyUSB1'}
        self.manager.device_health['/dev/ttyUSB0'] = DeviceHealth('/dev/ttyUSB0')
        self.manager.device_health['/dev/ttyUSB1'] = DeviceHealth('/dev/ttyUSB1')
        self.manager.device_health['/dev/ttyUSB0'].is_healthy = False
        
        # Mock controller
        self.manager.controller.is_connected = Mock(return_value=True)
        
        # Get device - should only return healthy device
        device = self.manager.get_available_device(DeviceType.SMT_TESTER, require_healthy=True)
        
        self.assertEqual(device, '/dev/ttyUSB1')
        
    async def test_execute_on_any_device_success(self):
        """Test executing command on any available device."""
        # Set up available device
        self.manager.device_pools[DeviceType.SMT_TESTER] = {'/dev/ttyUSB0'}
        self.manager.device_health['/dev/ttyUSB0'] = DeviceHealth('/dev/ttyUSB0')
        self.manager.controller.is_connected = Mock(return_value=True)
        
        # Mock command execution
        mock_response = create_command_response(success=True, data={'result': 'OK'})
        self.manager.controller.execute_command = AsyncMock(return_value=mock_response)
        
        # Execute command
        port, response = await self.manager.execute_on_any_device(
            DeviceType.SMT_TESTER,
            'TEST_COMMAND',
            {'param': 'value'}
        )
        
        self.assertEqual(port, '/dev/ttyUSB0')
        self.assertTrue(response.success)
        self.assertEqual(response.data['result'], 'OK')
        
    async def test_execute_on_any_device_no_device(self):
        """Test executing command when no device available."""
        # No devices in pool
        
        # Execute command
        port, response = await self.manager.execute_on_any_device(
            DeviceType.SMT_TESTER,
            'TEST_COMMAND'
        )
        
        self.assertIsNone(port)
        self.assertFalse(response.success)
        self.assertEqual(response.error.error_code, 'NO_DEVICE_AVAILABLE')
        
    def test_device_health_update(self):
        """Test device health status updates."""
        health = DeviceHealth('/dev/ttyUSB0')
        
        # Initial state
        self.assertTrue(health.is_healthy)
        self.assertEqual(health.consecutive_failures, 0)
        
        # Success updates
        health.update_health(True, 0.1)
        self.assertTrue(health.is_healthy)
        self.assertGreater(health.average_response_time, 0)
        
        # Failures
        health.update_health(False)
        health.update_health(False)
        self.assertEqual(health.consecutive_failures, 2)
        self.assertTrue(health.is_healthy)
        
        # Third failure marks unhealthy
        health.update_health(False)
        self.assertFalse(health.is_healthy)
        
        # Success resets failures
        health.update_health(True)
        self.assertEqual(health.consecutive_failures, 0)
        self.assertTrue(health.is_healthy)
        
    def test_get_device_pool_stats(self):
        """Test device pool statistics."""
        # Set up pool
        self.manager.device_pools[DeviceType.SMT_TESTER] = {'/dev/ttyUSB0', '/dev/ttyUSB1'}
        self.manager.device_health['/dev/ttyUSB0'] = DeviceHealth('/dev/ttyUSB0')
        self.manager.device_health['/dev/ttyUSB1'] = DeviceHealth('/dev/ttyUSB1')
        self.manager.device_health['/dev/ttyUSB1'].is_healthy = False
        self.manager.device_usage_count['/dev/ttyUSB0'] = 10
        self.manager.device_usage_count['/dev/ttyUSB1'] = 5
        
        # Mock device info
        mock_info1 = DeviceInfo(
            device_type=DeviceType.SMT_TESTER,
            port='/dev/ttyUSB0',
            success_count=90,
            error_count=10
        )
        mock_info2 = DeviceInfo(
            device_type=DeviceType.SMT_TESTER,
            port='/dev/ttyUSB1',
            success_count=40,
            error_count=10
        )
        self.manager.controller.get_device_info = Mock(side_effect=[mock_info1, mock_info2])
        
        # Get stats
        stats = self.manager.get_device_pool_stats(DeviceType.SMT_TESTER)
        
        self.assertEqual(stats['device_type'], 'SMT_TESTER')
        self.assertEqual(stats['total_devices'], 2)
        self.assertEqual(stats['healthy_devices'], 1)
        self.assertEqual(stats['total_usage'], 15)
        self.assertEqual(stats['total_errors'], 20)
        self.assertEqual(stats['total_success'], 130)
        self.assertAlmostEqual(stats['success_rate'], 0.867, places=3)
        
    @patch('serial.tools.list_ports.comports')
    async def test_device_discovery(self, mock_comports):
        """Test automatic device discovery."""
        # Mock serial ports
        mock_port1 = Mock()
        mock_port1.device = '/dev/ttyUSB0'
        mock_port2 = Mock()
        mock_port2.device = '/dev/ttyUSB1'
        mock_comports.return_value = [mock_port1, mock_port2]
        
        # Mock controller
        self.manager.controller.is_connected = Mock(return_value=False)
        self.manager.controller.connect_device = AsyncMock(return_value=True)
        
        # Run discovery
        await self.manager._discover_devices()
        
        # Check devices were added
        self.assertIn('/dev/ttyUSB0', self.manager.known_ports)
        self.assertIn('/dev/ttyUSB1', self.manager.known_ports)
        self.assertEqual(self.manager.controller.connect_device.call_count, 2)
        
    async def test_health_check_loop(self):
        """Test health check loop functionality."""
        # Add a device
        self.manager.known_ports.add('/dev/ttyUSB0')
        self.manager.device_health['/dev/ttyUSB0'] = DeviceHealth('/dev/ttyUSB0')
        
        # Mock controller
        self.manager.controller.is_connected = Mock(return_value=True)
        self.manager.controller.query_device = AsyncMock(return_value=create_command_response(
            success=True,
            data={'version': '5.2.0'}
        ))
        
        # Run health check
        await self.manager._check_device_health()
        
        # Check health was updated
        health = self.manager.device_health['/dev/ttyUSB0']
        self.assertTrue(health.is_healthy)
        self.assertEqual(health.consecutive_failures, 0)
        
    def test_callbacks(self):
        """Test callback functionality."""
        # Track callback calls
        added_devices = []
        removed_devices = []
        health_changes = []
        
        def device_added(info):
            added_devices.append(info)
            
        def device_removed(port):
            removed_devices.append(port)
            
        def health_changed(port, is_healthy):
            health_changes.append((port, is_healthy))
            
        # Add callbacks
        self.manager.add_device_added_callback(device_added)
        self.manager.add_device_removed_callback(device_removed)
        self.manager.add_health_changed_callback(health_changed)
        
        # Trigger notifications
        mock_info = DeviceInfo(DeviceType.SMT_TESTER, '/dev/ttyUSB0')
        self.manager._notify_device_added(mock_info)
        self.manager._notify_device_removed('/dev/ttyUSB0')
        self.manager._notify_health_changed('/dev/ttyUSB0', False)
        
        # Check callbacks were called
        self.assertEqual(len(added_devices), 1)
        self.assertEqual(added_devices[0], mock_info)
        self.assertEqual(removed_devices, ['/dev/ttyUSB0'])
        self.assertEqual(health_changes, [('/dev/ttyUSB0', False)])


def run_async_test(coro):
    """Helper to run async tests."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


# Patch async test methods
for attr_name in dir(TestUnifiedDeviceController):
    attr = getattr(TestUnifiedDeviceController, attr_name)
    if asyncio.iscoroutinefunction(attr) and attr_name.startswith('test_'):
        setattr(TestUnifiedDeviceController, attr_name, 
                lambda self, coro=attr: run_async_test(coro(self)))

for attr_name in dir(TestDeviceManager):
    attr = getattr(TestDeviceManager, attr_name)
    if asyncio.iscoroutinefunction(attr) and attr_name.startswith('test_'):
        setattr(TestDeviceManager, attr_name,
                lambda self, coro=attr: run_async_test(coro(self)))


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)