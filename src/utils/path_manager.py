"""
Path management for Diode Tester
Handles local vs shared drive paths with fallback support
"""
import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import platform


class PathManager:
    """Manages application paths for local and shared resources"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Check environment variable first (highest priority)
        env_shared_path = os.environ.get('DIODE_TESTER_SHARED_DRIVE')
        if env_shared_path:
            self._shared_drive_path = Path(env_shared_path)
            self.logger.info(f"Using shared drive path from environment: {self._shared_drive_path}")
        else:
            self._shared_drive_path = Path(r"B:\Users\Landon Epperson\Tester")
        
        self._settings_loaded = False
        self._paths_cache = {}
        
        # Check for command-line override of shared drive path (second priority)
        self._check_command_line_args()
        
        # Determine if running from frozen executable
        if getattr(sys, 'frozen', False):
            # Running from PyInstaller bundle
            self.app_dir = Path(sys._MEIPASS)
            self.is_frozen = True
        else:
            # Running from source
            self.app_dir = Path(__file__).parent.parent.parent
            self.is_frozen = False
        
        # Load settings
        self._load_settings()
    
    def _check_command_line_args(self):
        """Check for command-line arguments that override settings"""
        import argparse
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('--shared-drive', type=str, help='Override shared drive path')
        args, _ = parser.parse_known_args()
        
        if args.shared_drive:
            self._shared_drive_path = Path(args.shared_drive)
            self.logger.info(f"Shared drive path overridden to: {self._shared_drive_path}")
    
    def _load_settings(self):
        """Load settings from shared drive or local fallback"""
        try:
            # Try shared drive settings first
            shared_settings = self._shared_drive_path / "config" / "settings.json"
            if shared_settings.exists():
                with open(shared_settings, 'r') as f:
                    settings = json.load(f)
                    self._shared_drive_path = Path(settings.get("shared_config_path", self._shared_drive_path))
                    self._settings_loaded = True
                    self.logger.info(f"Loaded settings from shared drive: {shared_settings}")
                    return
        except Exception as e:
            self.logger.warning(f"Could not load shared settings: {e}")
        
        # Try local settings
        local_settings = self.get_local_data_dir() / "settings.json"
        if local_settings.exists():
            try:
                with open(local_settings, 'r') as f:
                    settings = json.load(f)
                    self._shared_drive_path = Path(settings.get("shared_config_path", self._shared_drive_path))
                    self._settings_loaded = True
                    self.logger.info(f"Loaded settings from local: {local_settings}")
            except Exception as e:
                self.logger.warning(f"Could not load local settings: {e}")
    
    def get_local_data_dir(self) -> Path:
        """Get local application data directory"""
        if "local_data" in self._paths_cache:
            return self._paths_cache["local_data"]
        
        if platform.system() == "Windows":
            app_data = Path(os.environ.get('APPDATA', ''))
            if not app_data:
                app_data = Path.home() / "AppData" / "Roaming"
        else:
            app_data = Path.home() / ".config"
        
        local_dir = app_data / "Diode Dynamics" / "DiodeTester"
        local_dir.mkdir(parents=True, exist_ok=True)
        
        self._paths_cache["local_data"] = local_dir
        return local_dir
    
    def get_config_dir(self, prefer_shared: bool = True) -> Path:
        """Get configuration directory (shared or local)"""
        cache_key = f"config_{prefer_shared}"
        if cache_key in self._paths_cache:
            return self._paths_cache[cache_key]
        
        if prefer_shared:
            shared_config = self._shared_drive_path / "config"
            if shared_config.exists():
                self._paths_cache[cache_key] = shared_config
                return shared_config
            else:
                self.logger.warning(f"Shared config not accessible: {shared_config}")
        
        # Fallback to local
        if self.is_frozen:
            # For frozen app, use app directory
            local_config = self.app_dir / "config"
        else:
            # For development, use project config
            local_config = self.app_dir / "config"
        
        if not local_config.exists():
            self.logger.error(f"No config directory found at: {local_config}")
        
        self._paths_cache[cache_key] = local_config
        return local_config
    
    def get_skus_dir(self) -> Path:
        """Get SKUs configuration directory"""
        return self.get_config_dir() / "skus"
    
    def get_device_cache_path(self) -> Path:
        """Get device cache path (always local)"""
        return self.get_local_data_dir() / ".device_cache.json"
    
    def get_logs_dir(self) -> Path:
        """Get logs directory (local)"""
        logs_dir = self.get_local_data_dir() / "logs"
        logs_dir.mkdir(exist_ok=True)
        return logs_dir
    
    def get_results_dir(self) -> Path:
        """Get results directory (local by default)"""
        results_dir = self.get_local_data_dir() / "results"
        results_dir.mkdir(exist_ok=True)
        return results_dir
    
    def get_calibration_dir(self) -> Path:
        """Get calibration directory"""
        # Try shared first
        shared_cal = self._shared_drive_path / "calibration"
        if shared_cal.exists():
            return shared_cal
        
        # Fallback to local
        local_cal = self.get_local_data_dir() / "calibration"
        local_cal.mkdir(exist_ok=True)
        return local_cal
    
    def is_shared_drive_available(self) -> bool:
        """Check if shared drive is accessible"""
        try:
            return self._shared_drive_path.exists() and self._shared_drive_path.is_dir()
        except Exception:
            return False
    
    def get_path_info(self) -> Dict[str, Any]:
        """Get information about current path configuration"""
        return {
            "shared_drive_path": str(self._shared_drive_path),
            "shared_drive_available": self.is_shared_drive_available(),
            "local_data_dir": str(self.get_local_data_dir()),
            "config_dir": str(self.get_config_dir()),
            "is_frozen": self.is_frozen,
            "app_dir": str(self.app_dir)
        }


# Global instance
_path_manager = None


def get_path_manager() -> PathManager:
    """Get global PathManager instance"""
    global _path_manager
    if _path_manager is None:
        _path_manager = PathManager()
    return _path_manager


# Convenience functions
def get_config_dir(prefer_shared: bool = True) -> Path:
    """Get configuration directory"""
    return get_path_manager().get_config_dir(prefer_shared)


def get_skus_dir() -> Path:
    """Get SKUs directory"""
    return get_path_manager().get_skus_dir()


def get_device_cache_path() -> Path:
    """Get device cache path"""
    return get_path_manager().get_device_cache_path()


def get_logs_dir() -> Path:
    """Get logs directory"""
    return get_path_manager().get_logs_dir()


def get_results_dir() -> Path:
    """Get results directory"""
    return get_path_manager().get_results_dir()