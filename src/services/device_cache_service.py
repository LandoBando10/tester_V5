"""Device cache service for persistent storage of device information."""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class DeviceCacheService:
    """Manages caching of device information for faster reconnection."""
    
    CACHE_TIMEOUT = 86400  # 24 hours in seconds
    
    def __init__(self, cache_file: Optional[Path] = None):
        """Initialize the device cache service.
        
        Args:
            cache_file: Optional custom cache file path
        """
        if cache_file:
            self.cache_file = cache_file
        else:
            # Use PathManager for cache file location
            try:
                from src.utils.path_manager import get_device_cache_path
                self.cache_file = get_device_cache_path()
            except ImportError:
                # Fallback for compatibility
                self.cache_file = Path("config") / ".device_cache.json"
        
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self) -> None:
        """Ensure the cache directory exists."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
    
    def load_cache(self) -> Dict[str, Any]:
        """Load device cache from disk.
        
        Returns:
            Dictionary containing cached device information
        """
        if not self.cache_file.exists():
            logger.debug("No device cache file found")
            return {}
        
        try:
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
                
            # Validate cache age
            if self._is_cache_expired(cache_data):
                logger.info("Device cache expired, clearing")
                return {}
                
            logger.info(f"Loaded device cache with {len(cache_data.get('devices', {}))} devices")
            return cache_data
            
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load device cache: {e}")
            return {}
    
    def save_cache(self, devices: Dict[str, Dict[str, Any]]) -> bool:
        """Save device information to cache.
        
        Args:
            devices: Dictionary mapping port names to device information
            
        Returns:
            True if save successful, False otherwise
        """
        cache_data = {
            'timestamp': time.time(),
            'devices': devices
        }
        
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            logger.debug(f"Saved {len(devices)} devices to cache")
            return True
            
        except IOError as e:
            logger.error(f"Failed to save device cache: {e}")
            return False
    
    def get_device(self, port: str) -> Optional[Dict[str, Any]]:
        """Get cached information for a specific port (alias for get_cached_device).
        
        Args:
            port: Port name to look up
            
        Returns:
            Device information if found and valid, None otherwise
        """
        return self.get_cached_device(port)
    
    def get_cached_device(self, port: str) -> Optional[Dict[str, Any]]:
        """Get cached information for a specific port.
        
        Args:
            port: Port name to look up
            
        Returns:
            Device information if found and valid, None otherwise
        """
        cache_data = self.load_cache()
        devices = cache_data.get('devices', {})
        return devices.get(port)
    
    def update_device(self, port: str, device_info: Dict[str, Any]) -> bool:
        """Update cache with new device information.
        
        Args:
            port: Port name
            device_info: Device information to cache
            
        Returns:
            True if update successful
        """
        cache_data = self.load_cache()
        devices = cache_data.get('devices', {})
        devices[port] = device_info
        return self.save_cache(devices)
    
    def remove_device(self, port: str) -> bool:
        """Remove a device from the cache.
        
        Args:
            port: Port name to remove
            
        Returns:
            True if removal successful
        """
        cache_data = self.load_cache()
        devices = cache_data.get('devices', {})
        if port in devices:
            del devices[port]
            return self.save_cache(devices)
        return True
    
    def clear_cache(self) -> bool:
        """Clear all cached devices.
        
        Returns:
            True if clear successful
        """
        return self.save_cache({})
    
    def _is_cache_expired(self, cache_data: Dict[str, Any]) -> bool:
        """Check if cache data has expired.
        
        Args:
            cache_data: Cache data with timestamp
            
        Returns:
            True if cache is expired
        """
        timestamp = cache_data.get('timestamp', 0)
        age = time.time() - timestamp
        return age > self.CACHE_TIMEOUT
    
    def get_arduino_port(self) -> Optional[str]:
        """Get the last known Arduino port from cache.
        
        Returns:
            Port name if found, None otherwise
        """
        cache_data = self.load_cache()
        devices = cache_data.get('devices', {})
        
        # Find first Arduino device
        for port, info in devices.items():
            if info.get('device_type') == 'Arduino':
                return port
        
        return None