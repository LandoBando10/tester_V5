"""Port scanning service for device discovery."""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Dict, Optional, Callable, Tuple

from PySide6.QtCore import QObject, Signal, QThread

from src.hardware.serial_manager import SerialManager
from src.services.port_registry import port_registry

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    """Information about a discovered device."""
    port: str
    device_type: str
    description: str
    response: str = ""
    probe_time: float = 0.0


class PortScanWorker(QThread):
    """Worker thread for asynchronous port scanning."""
    
    # Signals
    device_found = Signal(DeviceInfo)
    progress = Signal(str)
    scan_complete = Signal(list)  # List of DeviceInfo
    
    def __init__(self, ports: List[str], scanner_service: 'PortScannerService'):
        super().__init__()
        self.ports = ports
        self.scanner_service = scanner_service
        self._is_running = True
    
    def run(self):
        """Run the port scanning in a separate thread."""
        devices = []
        
        for port in self.ports:
            if not self._is_running:
                break
                
            self.progress.emit(f"Scanning {port}...")
            
            device_info = self.scanner_service.probe_port(port)
            if device_info:
                devices.append(device_info)
                self.device_found.emit(device_info)
        
        self.scan_complete.emit(devices)
    
    def stop(self):
        """Stop the scanning thread."""
        self._is_running = False


class PortScannerService(QObject):
    """Service for scanning and identifying devices on serial ports."""
    
    # Device identification patterns
    DEVICE_PATTERNS = {
        'Arduino': [
            re.compile(r'OFFROAD_ASSEMBLY_TESTER'),
            re.compile(r'SMT_ASSEMBLY_TESTER'),
            re.compile(r'WEIGHT_SCALE_TESTER'),
            re.compile(r'Arduino'),
            re.compile(r'OK')
        ],
        'Scale': [
            re.compile(r'Toledo'),
            re.compile(r'METTLER'),
            re.compile(r'Scale'),
            re.compile(r'\d+\.\d+\s*(lb|kg|g|oz)')
        ]
    }
    
    # Default timeout for port probing
    PROBE_TIMEOUT = 0.05
    
    def __init__(self):
        super().__init__()
        self._scan_worker = None
    
    def get_available_ports(self) -> List[str]:
        """Get list of available serial ports.
        
        Returns:
            List of port names
        """
        serial_manager = SerialManager()
        return serial_manager.get_available_ports()
    
    def probe_port(self, port: str, timeout: float = None, check_in_use: bool = False) -> Optional[DeviceInfo]:
        """Probe a single port to identify the connected device.
        
        Args:
            port: Port name to probe
            timeout: Optional custom timeout
            check_in_use: If True, probe ports that are already in use (read-only check)
            
        Returns:
            DeviceInfo if device identified, None otherwise
        """
        # Check if port is in use
        is_in_use = port_registry.is_port_in_use(port)
        
        if is_in_use and not check_in_use:
            # Skip ports that are already in use (default behavior)
            logger.info(f"Skipping port {port} - already in use")
            return None
        
        if is_in_use and check_in_use:
            logger.info(f"Checking port {port} even though it's in use (read-only mode)")
            
        timeout = timeout or self.PROBE_TIMEOUT
        start_time = time.time()
        
        try:
            # If port is in use, we need to be extra careful
            if is_in_use and check_in_use:
                # For in-use ports, try to get cached info first
                from src.services.device_cache_service import DeviceCacheService
                cache = DeviceCacheService()
                cached_info = cache.get_device(port)
                if cached_info:
                    logger.info(f"Using cached info for in-use port {port}")
                    return DeviceInfo(
                        port=port,
                        device_type=cached_info.get('device_type', 'Unknown'),
                        description=cached_info.get('description', 'Unknown Device'),
                        response=cached_info.get('response', ''),
                        probe_time=0.0
                    )
                else:
                    # No cached info, can't probe an in-use port safely
                    logger.warning(f"No cached info for in-use port {port}")
                    return DeviceInfo(
                        port=port,
                        device_type='Unknown',
                        description='Device in use',
                        response='',
                        probe_time=0.0
                    )
            
            # Normal probing for ports not in use
            # Try Arduino first (most common)
            serial_manager = SerialManager(baud_rate=115200, timeout=timeout)
            if serial_manager.connect(port):
                try:
                    # Clear buffers first
                    serial_manager.flush_buffers()
                    # Send identification command - use "I" which works reliably
                    response = serial_manager.query("I", response_timeout=timeout)
                except Exception:
                    response = None
                finally:
                    serial_manager.disconnect()
                
                if response:
                    device_type = self._identify_device_type(response)
                    if device_type:
                        probe_time = time.time() - start_time
                        return DeviceInfo(
                            port=port,
                            device_type=device_type,
                            description=self._get_device_description(response, device_type),
                            response=response,
                            probe_time=probe_time
                        )
            
            # Try scale baudrate
            serial_manager = SerialManager(baud_rate=9600, timeout=timeout)
            if serial_manager.connect(port):
                try:
                    # Scales often send data continuously
                    time.sleep(0.05)
                    if serial_manager.connection.in_waiting > 0:
                        response = serial_manager.read_line(timeout=timeout)
                    else:
                        response = None
                except Exception:
                    response = None
                finally:
                    serial_manager.disconnect()
                
                if response:
                    device_type = self._identify_device_type(response)
                    if device_type:
                        probe_time = time.time() - start_time
                        return DeviceInfo(
                            port=port,
                            device_type=device_type,
                            description=self._get_device_description(response, device_type),
                            response=response,
                            probe_time=probe_time
                        )
                        
        except Exception as e:
            logger.debug(f"Failed to probe port {port}: {e}")
        
        return None
    
    def scan_ports_parallel(self, ports: Optional[List[str]] = None, 
                          max_workers: int = 4) -> List[DeviceInfo]:
        """Scan multiple ports in parallel.
        
        Args:
            ports: List of ports to scan (None for all available)
            max_workers: Maximum number of parallel workers
            
        Returns:
            List of discovered devices
        """
        if ports is None:
            ports = self.get_available_ports()
        
        devices = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_port = {
                executor.submit(self.probe_port, port): port 
                for port in ports
            }
            
            for future in as_completed(future_to_port):
                device_info = future.result()
                if device_info:
                    devices.append(device_info)
        
        return devices
    
    def scan_ports_async(self, ports: Optional[List[str]] = None) -> PortScanWorker:
        """Start asynchronous port scanning.
        
        Args:
            ports: List of ports to scan (None for all available)
            
        Returns:
            PortScanWorker instance for signal connections
        """
        if ports is None:
            ports = self.get_available_ports()
        
        # Stop any existing scan
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.stop()
            self._scan_worker.wait()
        
        self._scan_worker = PortScanWorker(ports, self)
        return self._scan_worker
    
    def identify_port_safe(self, port: str) -> Optional[DeviceInfo]:
        """Safely identify a port without disrupting existing connections.
        
        This method first checks cache, then tries probe_port with check_in_use=True.
        
        Args:
            port: Port to identify
            
        Returns:
            DeviceInfo if identified, None otherwise
        """
        # First check cache
        from src.services.device_cache_service import DeviceCacheService
        cache = DeviceCacheService()
        cached_info = cache.get_device(port)
        
        if cached_info:
            logger.info(f"Found cached info for port {port}")
            return DeviceInfo(
                port=port,
                device_type=cached_info.get('device_type', 'Unknown'),
                description=cached_info.get('description', 'Unknown Device'),
                response=cached_info.get('response', ''),
                probe_time=0.0
            )
        
        # Try to probe with check_in_use=True
        return self.probe_port(port, check_in_use=True)
    
    def find_arduino_quickly(self, cached_port: Optional[str] = None) -> Optional[DeviceInfo]:
        """Try to find Arduino quickly by checking cached port first.
        
        Args:
            cached_port: Last known Arduino port
            
        Returns:
            DeviceInfo if Arduino found, None otherwise
        """
        # Try cached port first
        if cached_port:
            device_info = self.probe_port(cached_port)
            if device_info and device_info.device_type == 'Arduino':
                logger.info(f"Found Arduino on cached port {cached_port}")
                return device_info
        
        # Scan all ports for Arduino
        ports = self.get_available_ports()
        for port in ports:
            device_info = self.probe_port(port)
            if device_info and device_info.device_type == 'Arduino':
                logger.info(f"Found Arduino on port {port}")
                return device_info
        
        return None
    
    def _identify_device_type(self, response: str) -> Optional[str]:
        """Identify device type from response.
        
        Args:
            response: Device response string
            
        Returns:
            Device type if identified, None otherwise
        """
        for device_type, patterns in self.DEVICE_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(response):
                    return device_type
        return None
    
    def _get_device_description(self, response: str, device_type: str) -> str:
        """Get human-readable device description.
        
        Args:
            response: Device response
            device_type: Identified device type
            
        Returns:
            Device description
        """
        if device_type == 'Arduino':
            # Extract firmware type from response
            if 'OFFROAD' in response:
                return 'Offroad Assembly Tester'
            elif 'SMT' in response:
                return 'SMT Assembly Tester'
            elif 'WEIGHT' in response:
                return 'Weight Scale Interface'
            else:
                return 'Arduino Device'
        
        elif device_type == 'Scale':
            if 'Toledo' in response:
                return 'Mettler Toledo Scale'
            else:
                return 'Serial Scale'
        
        return device_type