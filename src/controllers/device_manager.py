"""
Device Manager - Manages multiple devices with connection pooling and load balancing.

This module provides centralized management of multiple connected devices,
including automatic discovery, connection pooling, health monitoring,
and load balancing for test execution.
"""

import asyncio
import logging
import serial.tools.list_ports
from typing import Dict, List, Optional, Set, Callable, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
import threading
from collections import defaultdict

from src.controllers.unified_controller import (
    UnifiedDeviceController, DeviceInfo, DeviceConnectionState
)
from src.protocols.base_protocol import (
    DeviceType, CommandRequest, CommandResponse, ErrorResponse, ErrorSeverity, CommandType
)


class LoadBalancingStrategy(Enum):
    """Load balancing strategies for device selection."""
    ROUND_ROBIN = auto()
    LEAST_USED = auto()
    FASTEST_RESPONSE = auto()
    LEAST_ERRORS = auto()


@dataclass
class DevicePoolConfig:
    """Configuration for device connection pool."""
    max_devices_per_type: int = 10
    auto_discovery: bool = True
    discovery_interval: float = 5.0
    health_check_interval: float = 10.0
    reconnect_interval: float = 30.0
    max_reconnect_attempts: int = 3
    load_balancing_strategy: LoadBalancingStrategy = LoadBalancingStrategy.LEAST_USED


@dataclass
class DeviceHealth:
    """Health status of a device."""
    port: str
    is_healthy: bool = True
    last_health_check: datetime = field(default_factory=datetime.now)
    consecutive_failures: int = 0
    average_response_time: float = 0.0
    error_rate: float = 0.0
    
    def update_health(self, success: bool, response_time: float = 0.0):
        """Update health status based on operation result."""
        self.last_health_check = datetime.now()
        
        if success:
            self.consecutive_failures = 0
            # Update average response time (exponential moving average)
            alpha = 0.3  # Smoothing factor
            self.average_response_time = (
                alpha * response_time + 
                (1 - alpha) * self.average_response_time
            )
        else:
            self.consecutive_failures += 1
            
        # Mark unhealthy after 3 consecutive failures
        self.is_healthy = self.consecutive_failures < 3


class DeviceManager:
    """
    Manages multiple devices with connection pooling and load balancing.
    
    Features:
    - Automatic device discovery
    - Connection pooling per device type
    - Health monitoring and automatic reconnection
    - Load balancing for test distribution
    - Device usage statistics
    """
    
    def __init__(self, config: Optional[DevicePoolConfig] = None):
        """
        Initialize the device manager.
        
        Args:
            config: Pool configuration (uses defaults if not provided)
        """
        self.logger = logging.getLogger(__name__)
        self.config = config or DevicePoolConfig()
        self.controller = UnifiedDeviceController()
        
        # Device pools by type
        self.device_pools: Dict[DeviceType, Set[str]] = defaultdict(set)
        self.device_health: Dict[str, DeviceHealth] = {}
        
        # Load balancing state
        self.round_robin_indices: Dict[DeviceType, int] = defaultdict(int)
        self.device_usage_count: Dict[str, int] = defaultdict(int)
        
        # Discovery and monitoring
        self.known_ports: Set[str] = set()
        self._discovery_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Callbacks
        self._device_added_callbacks: List[Callable[[DeviceInfo], None]] = []
        self._device_removed_callbacks: List[Callable[[str], None]] = []
        self._health_changed_callbacks: List[Callable[[str, bool], None]] = []
        
        # Set up controller callbacks
        self.controller.add_connection_callback(self._handle_connection_change)
        self.controller.add_error_callback(self._handle_device_error)
        
    async def start(self):
        """Start the device manager and background tasks."""
        self.logger.info("Starting device manager")
        
        # Start background tasks
        if self.config.auto_discovery:
            self._discovery_task = asyncio.create_task(self._discovery_loop())
            
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
        
        # Do initial discovery
        await self._discover_devices()
        
    async def stop(self):
        """Stop the device manager and disconnect all devices."""
        self.logger.info("Stopping device manager")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Cancel background tasks
        tasks = []
        for task in [self._discovery_task, self._health_check_task, self._reconnect_task]:
            if task and not task.done():
                task.cancel()
                tasks.append(task)
                
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
        # Disconnect all devices
        for port in list(self.known_ports):
            await self.remove_device(port)
            
    def add_device_added_callback(self, callback: Callable[[DeviceInfo], None]):
        """Add callback for device addition."""
        self._device_added_callbacks.append(callback)
        
    def remove_device_added_callback(self, callback: Callable[[DeviceInfo], None]):
        """Remove device addition callback."""
        if callback in self._device_added_callbacks:
            self._device_added_callbacks.remove(callback)
            
    def add_device_removed_callback(self, callback: Callable[[str], None]):
        """Add callback for device removal."""
        self._device_removed_callbacks.append(callback)
        
    def remove_device_removed_callback(self, callback: Callable[[str], None]):
        """Remove device removal callback."""
        if callback in self._device_removed_callbacks:
            self._device_removed_callbacks.remove(callback)
            
    def add_health_changed_callback(self, callback: Callable[[str, bool], None]):
        """Add callback for health status changes."""
        self._health_changed_callbacks.append(callback)
        
    def remove_health_changed_callback(self, callback: Callable[[str, bool], None]):
        """Remove health status callback."""
        if callback in self._health_changed_callbacks:
            self._health_changed_callbacks.remove(callback)
            
    def _notify_device_added(self, device_info: DeviceInfo):
        """Notify callbacks of device addition."""
        for callback in self._device_added_callbacks:
            try:
                callback(device_info)
            except Exception as e:
                self.logger.error(f"Error in device added callback: {e}")
                
    def _notify_device_removed(self, port: str):
        """Notify callbacks of device removal."""
        for callback in self._device_removed_callbacks:
            try:
                callback(port)
            except Exception as e:
                self.logger.error(f"Error in device removed callback: {e}")
                
    def _notify_health_changed(self, port: str, is_healthy: bool):
        """Notify callbacks of health status change."""
        for callback in self._health_changed_callbacks:
            try:
                callback(port, is_healthy)
            except Exception as e:
                self.logger.error(f"Error in health changed callback: {e}")
                
    def _handle_connection_change(self, port: str, state: DeviceConnectionState):
        """Handle device connection state changes."""
        if state == DeviceConnectionState.CONNECTED:
            device_info = self.controller.get_device_info(port)
            if device_info and device_info.device_type != DeviceType.UNKNOWN:
                # Add to appropriate pool
                pool = self.device_pools[device_info.device_type]
                if len(pool) < self.config.max_devices_per_type:
                    pool.add(port)
                    self.device_health[port] = DeviceHealth(port)
                    self._notify_device_added(device_info)
                else:
                    # Pool is full, disconnect
                    asyncio.create_task(self.controller.disconnect_device(port))
                    
        elif state in [DeviceConnectionState.DISCONNECTED, DeviceConnectionState.ERROR]:
            # Remove from pools
            for pool in self.device_pools.values():
                pool.discard(port)
                
    def _handle_device_error(self, port: str, error: ErrorResponse):
        """Handle device errors."""
        if port in self.device_health:
            self.device_health[port].update_health(False)
            
            # Check if health status changed
            if not self.device_health[port].is_healthy:
                self._notify_health_changed(port, False)
                
    async def _discover_devices(self):
        """Discover available devices."""
        try:
            # Get list of serial ports
            ports = serial.tools.list_ports.comports()
            current_ports = {port.device for port in ports}
            
            # Find new ports
            new_ports = current_ports - self.known_ports
            
            # Find removed ports
            removed_ports = self.known_ports - current_ports
            
            # Handle removed ports
            for port in removed_ports:
                await self.remove_device(port)
                
            # Try to connect to new ports
            for port in new_ports:
                # Skip if already connecting or connected
                if self.controller.is_connected(port):
                    continue
                    
                try:
                    # Attempt connection
                    success = await self.controller.connect_device(port)
                    if success:
                        self.known_ports.add(port)
                        self.logger.info(f"Discovered and connected to device on {port}")
                        
                except Exception as e:
                    self.logger.debug(f"Failed to connect to {port}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Device discovery error: {e}")
            
    async def _discovery_loop(self):
        """Background task for device discovery."""
        while not self._shutdown_event.is_set():
            try:
                await self._discover_devices()
                await asyncio.sleep(self.config.discovery_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Discovery loop error: {e}")
                await asyncio.sleep(self.config.discovery_interval)
                
    async def _health_check_loop(self):
        """Background task for health monitoring."""
        while not self._shutdown_event.is_set():
            try:
                await self._check_device_health()
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(self.config.health_check_interval)
                
    async def _check_device_health(self):
        """Check health of all connected devices."""
        for port in list(self.known_ports):
            if not self.controller.is_connected(port):
                continue
                
            try:
                # Simple health check - query version
                start_time = datetime.now()
                response = await self.controller.query_device(port, "VERSION", timeout=2.0)
                response_time = (datetime.now() - start_time).total_seconds()
                
                # Update health status
                if port in self.device_health:
                    old_health = self.device_health[port].is_healthy
                    self.device_health[port].update_health(response.success, response_time)
                    
                    # Notify if health changed
                    new_health = self.device_health[port].is_healthy
                    if old_health != new_health:
                        self._notify_health_changed(port, new_health)
                        
            except Exception as e:
                self.logger.error(f"Health check failed for {port}: {e}")
                if port in self.device_health:
                    self.device_health[port].update_health(False)
                    
    async def _reconnect_loop(self):
        """Background task for reconnecting failed devices."""
        while not self._shutdown_event.is_set():
            try:
                await self._reconnect_devices()
                await asyncio.sleep(self.config.reconnect_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Reconnect loop error: {e}")
                await asyncio.sleep(self.config.reconnect_interval)
                
    async def _reconnect_devices(self):
        """Attempt to reconnect to disconnected devices."""
        for port in list(self.known_ports):
            if self.controller.is_connected(port):
                continue
                
            device_info = self.controller.get_device_info(port)
            if device_info and device_info.error_count < self.config.max_reconnect_attempts:
                self.logger.info(f"Attempting to reconnect to {port}")
                await self.controller.reconnect_device(port)
                
    async def add_device(self, port: str, device_type: Optional[DeviceType] = None) -> bool:
        """
        Manually add a device to the manager.
        
        Args:
            port: Serial port path
            device_type: Device type hint
            
        Returns:
            True if device added successfully
        """
        if port in self.known_ports:
            return True
            
        success = await self.controller.connect_device(port, device_type)
        if success:
            self.known_ports.add(port)
            
        return success
        
    async def remove_device(self, port: str):
        """
        Remove a device from the manager.
        
        Args:
            port: Serial port path
        """
        if port not in self.known_ports:
            return
            
        # Disconnect device
        await self.controller.disconnect_device(port)
        
        # Remove from tracking
        self.known_ports.discard(port)
        for pool in self.device_pools.values():
            pool.discard(port)
            
        if port in self.device_health:
            del self.device_health[port]
            
        if port in self.device_usage_count:
            del self.device_usage_count[port]
            
        self._notify_device_removed(port)
        
    def get_available_device(self, device_type: DeviceType, 
                           require_healthy: bool = True) -> Optional[str]:
        """
        Get an available device of the specified type using load balancing.
        
        Args:
            device_type: Type of device needed
            require_healthy: Only return healthy devices
            
        Returns:
            Port of available device or None
        """
        pool = self.device_pools.get(device_type, set())
        if not pool:
            return None
            
        # Filter by health if required
        available_ports = []
        for port in pool:
            if not self.controller.is_connected(port):
                continue
                
            if require_healthy:
                health = self.device_health.get(port)
                if not health or not health.is_healthy:
                    continue
                    
            available_ports.append(port)
            
        if not available_ports:
            return None
            
        # Apply load balancing strategy
        if self.config.load_balancing_strategy == LoadBalancingStrategy.ROUND_ROBIN:
            # Round robin selection
            index = self.round_robin_indices[device_type] % len(available_ports)
            self.round_robin_indices[device_type] += 1
            selected = available_ports[index]
            
        elif self.config.load_balancing_strategy == LoadBalancingStrategy.LEAST_USED:
            # Select least used device
            selected = min(available_ports, key=lambda p: self.device_usage_count[p])
            
        elif self.config.load_balancing_strategy == LoadBalancingStrategy.FASTEST_RESPONSE:
            # Select device with fastest average response time
            def get_response_time(port):
                health = self.device_health.get(port)
                return health.average_response_time if health else float('inf')
            selected = min(available_ports, key=get_response_time)
            
        elif self.config.load_balancing_strategy == LoadBalancingStrategy.LEAST_ERRORS:
            # Select device with lowest error rate
            def get_error_rate(port):
                info = self.controller.get_device_info(port)
                return info.error_count / max(info.success_count + info.error_count, 1) if info else 1.0
            selected = min(available_ports, key=get_error_rate)
            
        else:
            # Default to first available
            selected = available_ports[0]
            
        # Track usage
        self.device_usage_count[selected] += 1
        
        return selected
        
    async def execute_on_any_device(self, device_type: DeviceType, command: str,
                                  params: Optional[Dict[str, Any]] = None,
                                  timeout: float = 5.0) -> Tuple[Optional[str], CommandResponse]:
        """
        Execute a command on any available device of the specified type.
        
        Args:
            device_type: Type of device needed
            command: Command to execute
            params: Command parameters
            timeout: Command timeout
            
        Returns:
            Tuple of (port, response) or (None, error response)
        """
        port = self.get_available_device(device_type)
        if not port:
            # Create a fake request for the response
            request = CommandRequest(
                command_type=CommandType.MEASURE,  # Use generic command type
                command=command,
                parameters=params or {},
                timeout=timeout
            )
            return None, CommandResponse(
                request=request,
                timestamp=datetime.now().timestamp(),
                success=False,
                error=ErrorResponse(
                    device_type=device_type,
                    device_id="",
                    timestamp=datetime.now().timestamp(),
                    severity=ErrorSeverity.ERROR,
                    error_code="NO_DEVICE_AVAILABLE",
                    error_message=f"No available {device_type.name} device"
                )
            )
            
        response = await self.controller.execute_command(port, command, params, timeout)
        return port, response
        
    def get_device_pool_stats(self, device_type: DeviceType) -> Dict[str, Any]:
        """
        Get statistics for a device pool.
        
        Args:
            device_type: Device type
            
        Returns:
            Pool statistics
        """
        pool = self.device_pools.get(device_type, set())
        
        healthy_count = 0
        total_usage = 0
        total_errors = 0
        total_success = 0
        
        for port in pool:
            if port in self.device_health and self.device_health[port].is_healthy:
                healthy_count += 1
                
            total_usage += self.device_usage_count.get(port, 0)
            
            info = self.controller.get_device_info(port)
            if info:
                total_errors += info.error_count
                total_success += info.success_count
                
        return {
            'device_type': device_type.name,
            'total_devices': len(pool),
            'healthy_devices': healthy_count,
            'total_usage': total_usage,
            'total_errors': total_errors,
            'total_success': total_success,
            'success_rate': total_success / max(total_success + total_errors, 1)
        }
        
    def get_all_devices(self) -> List[DeviceInfo]:
        """Get information about all managed devices."""
        devices = []
        for port in self.known_ports:
            info = self.controller.get_device_info(port)
            if info:
                devices.append(info)
        return devices
        
    def get_healthy_devices(self) -> List[DeviceInfo]:
        """Get list of healthy devices."""
        devices = []
        for port in self.known_ports:
            if port in self.device_health and self.device_health[port].is_healthy:
                info = self.controller.get_device_info(port)
                if info:
                    devices.append(info)
        return devices