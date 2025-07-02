"""Global registry for tracking serial port usage across the application."""

import threading
from typing import Set, Optional
import logging

logger = logging.getLogger(__name__)


class PortRegistry:
    """Singleton registry to track which serial ports are in use.
    
    This prevents multiple components from trying to access the same port
    simultaneously, which causes permission errors.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._ports_in_use: Set[str] = set()
            self._port_lock = threading.Lock()
            self._initialized = True
            logger.debug("PortRegistry initialized")
    
    def acquire_port(self, port: str) -> bool:
        """Try to acquire exclusive access to a port.
        
        Args:
            port: Port name to acquire
            
        Returns:
            True if port was acquired, False if already in use
        """
        with self._port_lock:
            if port in self._ports_in_use:
                logger.debug(f"Port {port} is already in use")
                return False
            self._ports_in_use.add(port)
            logger.debug(f"Acquired port {port}")
            return True
    
    def release_port(self, port: str) -> None:
        """Release a port for use by other components.
        
        Args:
            port: Port name to release
        """
        with self._port_lock:
            if port in self._ports_in_use:
                self._ports_in_use.remove(port)
                logger.debug(f"Released port {port}")
            else:
                logger.warning(f"Attempted to release port {port} that wasn't acquired")
    
    def is_port_in_use(self, port: str) -> bool:
        """Check if a port is currently in use.
        
        Args:
            port: Port name to check
            
        Returns:
            True if port is in use
        """
        with self._port_lock:
            return port in self._ports_in_use
    
    def get_ports_in_use(self) -> Set[str]:
        """Get a copy of all ports currently in use.
        
        Returns:
            Set of port names in use
        """
        with self._port_lock:
            return self._ports_in_use.copy()
    
    def clear(self) -> None:
        """Clear all port registrations (use with caution)."""
        with self._port_lock:
            self._ports_in_use.clear()
            logger.debug("Cleared all port registrations")


# Global instance
port_registry = PortRegistry()