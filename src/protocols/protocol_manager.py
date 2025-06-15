"""
Protocol Manager - Unified Protocol Selection and Management

This module provides centralized protocol management, including automatic
protocol selection, capability detection, and fallback handling for different
firmware versions. It manages the transition between different protocol
implementations transparently.

Phase 4.2 Implementation - December 2024
"""

import logging
import time
from typing import Dict, Any, Optional, List, Type, Union
from dataclasses import dataclass
from enum import Enum

from .base_protocol import BaseProtocol, DeviceType
from .framed_binary_protocol import (
    FramedBinaryProtocol, 
    ProtocolVersion, 
    ProtocolCapabilities,
    ProtocolNegotiator
)
from ..hardware.serial_manager import SerialManager


class ProtocolPriority(Enum):
    """Priority order for protocol selection"""
    BINARY_ADVANCED = 1
    BINARY_FRAMED = 2
    TEXT_WITH_CRC = 3
    TEXT_BASIC = 4


@dataclass
class DeviceProfile:
    """Profile information for a specific device"""
    device_type: DeviceType
    device_id: str
    firmware_version: Optional[str] = None
    last_known_capabilities: Optional[ProtocolCapabilities] = None
    preferred_protocol: Optional[ProtocolVersion] = None
    connection_history: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.connection_history is None:
            self.connection_history = []


class FallbackStrategy:
    """Defines fallback strategies for protocol selection"""
    
    @staticmethod
    def get_fallback_sequence(device_type: DeviceType) -> List[ProtocolVersion]:
        """Get the fallback sequence for a device type"""
        if device_type == DeviceType.SMT_TESTER:
            return [
                ProtocolVersion.BINARY_FRAMED,
                ProtocolVersion.TEXT_WITH_CRC,
                ProtocolVersion.TEXT_BASIC
            ]
        elif device_type == DeviceType.OFFROAD_TESTER:
            return [
                ProtocolVersion.BINARY_FRAMED,
                ProtocolVersion.TEXT_WITH_CRC,
                ProtocolVersion.TEXT_BASIC
            ]
        else:
            return [
                ProtocolVersion.TEXT_BASIC
            ]
    
    @staticmethod
    def should_retry_with_fallback(error_type: str, attempt_count: int) -> bool:
        """Determine if we should try a fallback protocol"""
        # Retry with fallback for certain error types
        retry_errors = [
            "CONNECTION_FAILED",
            "PROTOCOL_NEGOTIATION_FAILED", 
            "FRAMING_ERROR",
            "CRC_ERROR",
            "UNSUPPORTED_COMMAND"
        ]
        
        return error_type in retry_errors and attempt_count < 3
    
    @staticmethod
    def get_timeout_multiplier(attempt_count: int) -> float:
        """Get timeout multiplier for retry attempts"""
        return min(1.0 + (attempt_count * 0.5), 3.0)


class ProtocolManager:
    """
    Manages protocol selection, negotiation, and fallback handling.
    
    The ProtocolManager provides a unified interface for creating and managing
    device protocols. It automatically detects device capabilities, selects
    the best protocol version, and handles fallback to simpler protocols when
    needed.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.device_profiles: Dict[str, DeviceProfile] = {}
        self.protocol_registry: Dict[ProtocolVersion, Type[BaseProtocol]] = {}
        self.active_protocols: Dict[str, BaseProtocol] = {}
        
        # Register available protocols
        self._register_protocols()
    
    def _register_protocols(self):
        """Register available protocol implementations"""
        self.protocol_registry[ProtocolVersion.BINARY_FRAMED] = FramedBinaryProtocol
        # Future protocols can be registered here
        # self.protocol_registry[ProtocolVersion.BINARY_ADVANCED] = AdvancedBinaryProtocol
    
    async def create_protocol(
        self, 
        device_type: DeviceType, 
        device_id: str,
        connection_params: Dict[str, Any],
        force_protocol: Optional[ProtocolVersion] = None
    ) -> Optional[BaseProtocol]:
        """
        Create and configure a protocol for a device.
        
        Args:
            device_type: Type of device
            device_id: Unique device identifier  
            connection_params: Connection parameters (port, baud_rate, etc.)
            force_protocol: Force a specific protocol version (for testing)
            
        Returns:
            Configured protocol instance or None if all attempts failed
        """
        self.logger.info(f"Creating protocol for {device_type.value} device '{device_id}'")
        
        # Get or create device profile
        profile = self._get_device_profile(device_type, device_id)
        
        # Determine protocol selection strategy
        if force_protocol:
            protocol_sequence = [force_protocol]
        elif profile.preferred_protocol:
            # Start with preferred protocol, then fallback
            fallback_sequence = FallbackStrategy.get_fallback_sequence(device_type)
            protocol_sequence = [profile.preferred_protocol]
            protocol_sequence.extend([p for p in fallback_sequence if p != profile.preferred_protocol])
        else:
            # Use standard fallback sequence
            protocol_sequence = FallbackStrategy.get_fallback_sequence(device_type)
        
        # Try each protocol in sequence
        last_error = None
        for attempt, protocol_version in enumerate(protocol_sequence):
            try:
                self.logger.debug(f"Attempting {protocol_version.value} protocol (attempt {attempt + 1})")
                
                # Create protocol instance
                protocol = await self._create_protocol_instance(
                    protocol_version, device_type, device_id, connection_params, attempt
                )
                
                if protocol:
                    # Success - update profile and register
                    await self._on_protocol_success(profile, protocol, protocol_version)
                    self.active_protocols[device_id] = protocol
                    return protocol
                    
            except Exception as e:
                last_error = e
                self.logger.warning(f"Protocol {protocol_version.value} failed: {e}")
                
                # Record failed attempt
                profile.connection_history.append({
                    "timestamp": time.time(),
                    "protocol_version": protocol_version.value,
                    "success": False,
                    "error": str(e),
                    "attempt": attempt + 1
                })
                
                # Check if we should continue with fallback
                if not FallbackStrategy.should_retry_with_fallback(
                    getattr(e, 'error_code', str(type(e).__name__)), attempt + 1
                ):
                    break
        
        # All protocols failed
        self.logger.error(f"All protocol attempts failed for device '{device_id}'. Last error: {last_error}")
        return None
    
    async def _create_protocol_instance(
        self,
        protocol_version: ProtocolVersion,
        device_type: DeviceType,
        device_id: str,
        connection_params: Dict[str, Any],
        attempt: int
    ) -> Optional[BaseProtocol]:
        """Create and connect a protocol instance"""
        
        # Get protocol class
        protocol_class = self.protocol_registry.get(protocol_version)
        if not protocol_class:
            # Fallback to FramedBinaryProtocol for unknown versions
            self.logger.warning(f"Unknown protocol version {protocol_version.value}, using FramedBinaryProtocol")
            protocol_class = FramedBinaryProtocol
        
        # Adjust timeout for retry attempts
        timeout_multiplier = FallbackStrategy.get_timeout_multiplier(attempt)
        adjusted_params = connection_params.copy()
        if 'timeout' in adjusted_params:
            adjusted_params['timeout'] *= timeout_multiplier
        
        # Create protocol instance
        if protocol_class == FramedBinaryProtocol:
            protocol = protocol_class(
                device_type=device_type,
                device_id=device_id,
                baud_rate=adjusted_params.get('baud_rate', 115200)
            )
        else:
            # Generic protocol creation
            protocol = protocol_class(device_type, device_id)
        
        # Attempt connection
        if await protocol.connect(adjusted_params):
            return protocol
        else:
            # Connection failed, clean up
            try:
                await protocol.disconnect()
            except:
                pass
            return None
    
    async def _on_protocol_success(
        self, 
        profile: DeviceProfile, 
        protocol: BaseProtocol, 
        protocol_version: ProtocolVersion
    ):
        """Handle successful protocol connection"""
        
        # Update device profile
        status = protocol.get_status()
        profile.firmware_version = status.firmware_version
        profile.preferred_protocol = protocol_version
        
        # Store capabilities if available
        if hasattr(protocol, 'capabilities'):
            profile.last_known_capabilities = protocol.capabilities
        
        # Record successful connection
        profile.connection_history.append({
            "timestamp": time.time(),
            "protocol_version": protocol_version.value,
            "success": True,
            "capabilities": protocol.get_capabilities(),
            "firmware_version": status.firmware_version
        })
        
        # Keep only recent history (last 10 connections)
        profile.connection_history = profile.connection_history[-10:]
        
        self.logger.info(
            f"Successfully connected to '{profile.device_id}' using {protocol_version.value} "
            f"(firmware: {profile.firmware_version})"
        )
    
    def _get_device_profile(self, device_type: DeviceType, device_id: str) -> DeviceProfile:
        """Get or create device profile"""
        if device_id not in self.device_profiles:
            self.device_profiles[device_id] = DeviceProfile(
                device_type=device_type,
                device_id=device_id
            )
        return self.device_profiles[device_id]
    
    def get_protocol(self, device_id: str) -> Optional[BaseProtocol]:
        """Get active protocol for a device"""
        return self.active_protocols.get(device_id)
    
    async def disconnect_protocol(self, device_id: str) -> bool:
        """Disconnect and remove a protocol"""
        protocol = self.active_protocols.get(device_id)
        if protocol:
            try:
                success = await protocol.disconnect()
                del self.active_protocols[device_id]
                return success
            except Exception as e:
                self.logger.error(f"Error disconnecting protocol for '{device_id}': {e}")
                return False
        return True
    
    async def disconnect_all(self):
        """Disconnect all active protocols"""
        disconnect_tasks = []
        for device_id in list(self.active_protocols.keys()):
            disconnect_tasks.append(self.disconnect_protocol(device_id))
        
        # Wait for all disconnections to complete
        if disconnect_tasks:
            import asyncio
            await asyncio.gather(*disconnect_tasks, return_exceptions=True)
    
    def get_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive device information"""
        profile = self.device_profiles.get(device_id)
        protocol = self.active_protocols.get(device_id)
        
        if not profile:
            return None
        
        info = {
            "device_type": profile.device_type.value,
            "device_id": profile.device_id,
            "firmware_version": profile.firmware_version,
            "preferred_protocol": profile.preferred_protocol.value if profile.preferred_protocol else None,
            "connected": protocol is not None,
            "connection_history_count": len(profile.connection_history)
        }
        
        if protocol:
            info.update({
                "current_protocol": type(protocol).__name__,
                "capabilities": protocol.get_capabilities(),
                "status": protocol.get_status().__dict__,
                "performance_metrics": protocol.get_performance_metrics()
            })
            
            # Add protocol-specific info
            if hasattr(protocol, 'get_protocol_info'):
                info["protocol_info"] = protocol.get_protocol_info()
        
        return info
    
    def get_all_devices(self) -> List[Dict[str, Any]]:
        """Get information for all known devices"""
        return [
            self.get_device_info(device_id) 
            for device_id in self.device_profiles.keys()
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get protocol manager statistics"""
        total_devices = len(self.device_profiles)
        connected_devices = len(self.active_protocols)
        
        protocol_usage = {}
        for profile in self.device_profiles.values():
            if profile.preferred_protocol:
                protocol_name = profile.preferred_protocol.value
                protocol_usage[protocol_name] = protocol_usage.get(protocol_name, 0) + 1
        
        return {
            "total_devices": total_devices,
            "connected_devices": connected_devices,
            "connection_rate": connected_devices / max(total_devices, 1),
            "protocol_usage": protocol_usage,
            "registered_protocols": list(self.protocol_registry.keys())
        }
    
    def clear_device_history(self, device_id: str):
        """Clear connection history for a device"""
        profile = self.device_profiles.get(device_id)
        if profile:
            profile.connection_history.clear()
            profile.preferred_protocol = None
            profile.last_known_capabilities = None
            self.logger.info(f"Cleared history for device '{device_id}'")
    
    def set_preferred_protocol(self, device_id: str, protocol_version: ProtocolVersion):
        """Manually set preferred protocol for a device"""
        profile = self.device_profiles.get(device_id)
        if profile:
            profile.preferred_protocol = protocol_version
            self.logger.info(f"Set preferred protocol for '{device_id}' to {protocol_version.value}")


# Global protocol manager instance
_protocol_manager: Optional[ProtocolManager] = None


def get_protocol_manager() -> ProtocolManager:
    """Get the global protocol manager instance"""
    global _protocol_manager
    if _protocol_manager is None:
        _protocol_manager = ProtocolManager()
    return _protocol_manager


async def create_device_protocol(
    device_type: DeviceType,
    device_id: str,
    connection_params: Dict[str, Any],
    force_protocol: Optional[ProtocolVersion] = None
) -> Optional[BaseProtocol]:
    """
    Convenience function to create a device protocol.
    
    Args:
        device_type: Type of device
        device_id: Unique device identifier
        connection_params: Connection parameters
        force_protocol: Force specific protocol (optional)
        
    Returns:
        Connected protocol instance or None
    """
    manager = get_protocol_manager()
    return await manager.create_protocol(device_type, device_id, connection_params, force_protocol)


def get_device_protocol(device_id: str) -> Optional[BaseProtocol]:
    """Get active protocol for a device"""
    manager = get_protocol_manager()
    return manager.get_protocol(device_id)


async def disconnect_device_protocol(device_id: str) -> bool:
    """Disconnect a device protocol"""
    manager = get_protocol_manager()
    return await manager.disconnect_protocol(device_id)