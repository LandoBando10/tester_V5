"""Connection management service for hardware devices."""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

from PySide6.QtCore import QObject, Signal, QTimer

from src.hardware.serial_manager import SerialManager
from src.hardware.controller_factory import ArduinoControllerFactory
from src.hardware.scale_controller import ScaleController
from src.services.device_cache_service import DeviceCacheService
from src.services.port_scanner_service import PortScannerService, DeviceInfo

logger = logging.getLogger(__name__)


@dataclass
class ConnectionResult:
    """Result of a connection attempt."""
    success: bool
    error: Optional[str] = None
    firmware_type: Optional[str] = None
    device_info: Optional[Dict[str, Any]] = None


class ConnectionService(QObject):
    """Service for managing hardware connections."""
    
    # Signals
    arduino_connection_changed = Signal(bool, str)  # connected, port
    scale_connection_changed = Signal(bool, str)  # connected, port
    connection_error = Signal(str)
    
    def __init__(self, cache_service: Optional[DeviceCacheService] = None):
        """Initialize the connection service.
        
        Args:
            cache_service: Optional device cache service instance
        """
        super().__init__()
        
        # Services
        self.cache_service = cache_service or DeviceCacheService()
        self.port_scanner = PortScannerService()
        
        # Connection state
        self._arduino_controller = None
        self._arduino_port = None
        self._arduino_firmware = None
        self._scale_controller = None
        self._scale_port = None
        
        # Health monitoring
        self._health_timer = QTimer()
        self._health_timer.timeout.connect(self._check_connection_health)
        self._health_timer.setInterval(5000)  # 5 seconds
    
    # Arduino Connection Methods
    
    def connect_arduino(self, port: str) -> ConnectionResult:
        """Connect to Arduino on specified port.
        
        Args:
            port: Serial port name
            
        Returns:
            ConnectionResult with success status and details
        """
        # Disconnect existing connection
        if self._arduino_controller:
            self.disconnect_arduino()
        
        try:
            # First check if this port is already in use by us
            from src.services.port_registry import port_registry
            is_our_port = (self._arduino_port == port and 
                          port_registry.is_port_in_use(port))
            
            # Probe the port to get device info
            # Use check_in_use=True if it's our current port
            device_info = self.port_scanner.probe_port(port, check_in_use=is_our_port)
            
            if not device_info:
                # Try with check_in_use=True as fallback
                device_info = self.port_scanner.probe_port(port, check_in_use=True)
                
            if not device_info or device_info.device_type != 'Arduino':
                return ConnectionResult(
                    success=False,
                    error="No Arduino device found on this port"
                )
            
            # Determine firmware type from response
            firmware_type = self._determine_firmware_type(device_info.response)
            if not firmware_type:
                return ConnectionResult(
                    success=False,
                    error="Could not determine Arduino firmware type"
                )
            
            # Create appropriate controller
            logger.info(f"Creating controller for firmware type: {firmware_type}")
            controller = ArduinoControllerFactory.create_controller(
                mode=firmware_type,
                baud_rate=115200
            )
            
            if not controller:
                return ConnectionResult(
                    success=False,
                    error=f"Failed to create controller for {firmware_type}"
                )
            
            # Connect the controller to the port
            logger.info(f"Attempting to connect controller to {port}")
            if not controller.connect(port):
                logger.error(f"Controller failed to connect to {port}")
                # Make sure to release the port if connection fails
                from src.services.port_registry import port_registry
                port_registry.release_port(port)
                return ConnectionResult(
                    success=False,
                    error=f"Controller created but failed to connect to {port}"
                )
            
            # Store connection info
            self._arduino_controller = controller
            self._arduino_port = port
            self._arduino_firmware = firmware_type
            
            # Update cache with full device info including response
            self.cache_service.update_device(port, {
                'device_type': 'Arduino',
                'firmware_type': firmware_type,
                'description': device_info.description,
                'response': device_info.response  # Important for re-identification
            })
            
            # Start health monitoring
            self._start_health_monitoring()
            
            # Emit signal
            self.arduino_connection_changed.emit(True, port)
            
            logger.info(f"Connected to Arduino ({firmware_type}) on {port}")
            
            return ConnectionResult(
                success=True,
                firmware_type=firmware_type,
                device_info={'port': port, 'firmware': firmware_type}
            )
            
        except Exception as e:
            error_msg = f"Failed to connect to Arduino: {str(e)}"
            logger.error(error_msg)
            self.connection_error.emit(error_msg)
            return ConnectionResult(success=False, error=error_msg)
    
    def disconnect_arduino(self) -> bool:
        """Disconnect from Arduino.
        
        Returns:
            True if disconnected successfully
        """
        if self._arduino_controller:
            try:
                self._arduino_controller.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting Arduino: {e}")
            
            # Ensure port is released from registry (in case controller didn't do it)
            if self._arduino_port:
                from src.services.port_registry import port_registry
                if port_registry.is_port_in_use(self._arduino_port):
                    port_registry.release_port(self._arduino_port)
                    logger.debug(f"Released Arduino port {self._arduino_port} from registry")
            
            self._arduino_controller = None
            self._arduino_port = None
            self._arduino_firmware = None
            
            # Stop health monitoring if no connections
            if not self._scale_controller:
                self._stop_health_monitoring()
            
            self.arduino_connection_changed.emit(False, "")
            logger.info("Disconnected from Arduino")
        
        return True
    
    # Scale Connection Methods
    
    def connect_scale(self, port: str) -> ConnectionResult:
        """Connect to scale on specified port.
        
        Args:
            port: Serial port name
            
        Returns:
            ConnectionResult with success status
        """
        # Disconnect existing connection
        if self._scale_controller:
            self.disconnect_scale()
        
        try:
            # Create scale controller
            self._scale_controller = ScaleController(port)
            
            # Test connection
            if not self._scale_controller.connect():
                self._scale_controller = None
                return ConnectionResult(
                    success=False,
                    error="Failed to connect to scale"
                )
            
            # Try to get a reading to verify it's working
            weight = self._scale_controller.get_weight()
            if weight is None:
                # Some scales might not provide immediate readings
                logger.warning("Could not get initial weight reading")
            
            self._scale_port = port
            
            # Update cache
            self.cache_service.update_device(port, {
                'device_type': 'Scale',
                'description': 'Serial Scale'
            })
            
            # Start health monitoring
            self._start_health_monitoring()
            
            # Emit signal
            self.scale_connection_changed.emit(True, port)
            
            logger.info(f"Connected to scale on {port}")
            
            return ConnectionResult(
                success=True,
                device_info={'port': port}
            )
            
        except Exception as e:
            error_msg = f"Failed to connect to scale: {str(e)}"
            logger.error(error_msg)
            self.connection_error.emit(error_msg)
            return ConnectionResult(success=False, error=error_msg)
    
    def disconnect_scale(self) -> bool:
        """Disconnect from scale.
        
        Returns:
            True if disconnected successfully
        """
        if self._scale_controller:
            try:
                self._scale_controller.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting scale: {e}")
            
            # Ensure port is released from registry (in case controller didn't do it)
            if self._scale_port:
                from src.services.port_registry import port_registry
                if port_registry.is_port_in_use(self._scale_port):
                    port_registry.release_port(self._scale_port)
                    logger.debug(f"Released scale port {self._scale_port} from registry")
            
            self._scale_controller = None
            self._scale_port = None
            
            # Stop health monitoring if no connections
            if not self._arduino_controller:
                self._stop_health_monitoring()
            
            self.scale_connection_changed.emit(False, "")
            logger.info("Disconnected from scale")
        
        return True
    
    # Status Methods
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status.
        
        Returns:
            Dictionary with connection information
        """
        return {
            'arduino_connected': self._arduino_controller is not None,
            'arduino_port': self._arduino_port or '',
            'arduino_firmware': self._arduino_firmware or '',
            'scale_connected': self._scale_controller is not None,
            'scale_port': self._scale_port or ''
        }
    
    def get_arduino_controller(self):
        """Get the current Arduino controller instance.
        
        Returns:
            Arduino controller or None
        """
        return self._arduino_controller
    
    def get_scale_controller(self):
        """Get the current scale controller instance.
        
        Returns:
            Scale controller or None
        """
        return self._scale_controller
    
    def is_arduino_connected(self) -> bool:
        """Check if Arduino is connected.
        
        Returns:
            True if connected
        """
        return self._arduino_controller is not None
    
    def is_scale_connected(self) -> bool:
        """Check if scale is connected.
        
        Returns:
            True if connected
        """
        return self._scale_controller is not None
    
    # Health Monitoring
    
    def _start_health_monitoring(self):
        """Start monitoring connection health."""
        if not self._health_timer.isActive():
            self._health_timer.start()
            logger.debug("Started connection health monitoring")
    
    def _stop_health_monitoring(self):
        """Stop monitoring connection health."""
        if self._health_timer.isActive():
            self._health_timer.stop()
            logger.debug("Stopped connection health monitoring")
    
    def _check_connection_health(self):
        """Check health of active connections."""
        # Check Arduino connection
        if self._arduino_controller:
            try:
                # Send a ping or status command
                if hasattr(self._arduino_controller, 'is_connected'):
                    if not self._arduino_controller.is_connected():
                        logger.warning("Arduino connection lost")
                        self.disconnect_arduino()
                        self.connection_error.emit("Arduino connection lost")
            except Exception as e:
                logger.error(f"Error checking Arduino health: {e}")
        
        # Check scale connection
        if self._scale_controller:
            try:
                if hasattr(self._scale_controller, 'is_connected'):
                    if not self._scale_controller.is_connected():
                        logger.warning("Scale connection lost")
                        self.disconnect_scale()
                        self.connection_error.emit("Scale connection lost")
            except Exception as e:
                logger.error(f"Error checking scale health: {e}")
    
    # Helper Methods
    
    def _determine_firmware_type(self, response: str) -> Optional[str]:
        """Determine Arduino firmware type from response.
        
        Args:
            response: Response from Arduino ID command
            
        Returns:
            Firmware type or None
        """
        if 'OFFROAD_ASSEMBLY_TESTER' in response:
            return 'offroad'
        elif 'SMT_ASSEMBLY_TESTER' in response:
            return 'smt'
        elif 'WEIGHT_SCALE_TESTER' in response:
            return 'weight'
        else:
            # Try to determine from other patterns
            if 'OFFROAD' in response.upper():
                return 'offroad'
            elif 'SMT' in response.upper():
                return 'smt'
            elif 'WEIGHT' in response.upper():
                return 'weight'
        
        return None
    
    # Cleanup
    
    def cleanup(self):
        """Clean up all connections and resources."""
        self._stop_health_monitoring()
        self.disconnect_arduino()
        self.disconnect_scale()