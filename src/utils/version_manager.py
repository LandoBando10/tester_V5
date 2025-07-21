"""
Version management and auto-update checking for Diode Tester
"""
import json
import logging
from pathlib import Path
from typing import Optional, Tuple
from packaging import version


class VersionManager:
    """Manages application versioning and update checking"""
    
    def __init__(self, shared_drive_path: str = r"B:\Users\Landon Epperson\Tester"):
        self.logger = logging.getLogger(__name__)
        self.shared_drive_path = Path(shared_drive_path)
        self.version_file = Path(__file__).parent.parent.parent / "VERSION"
        self.update_info_path = self.shared_drive_path / "updates" / "version_info.json"
        
    def get_current_version(self) -> str:
        """Get the current application version"""
        try:
            if self.version_file.exists():
                return self.version_file.read_text().strip()
            else:
                # Fallback to hardcoded version
                return "1.0.0"
        except Exception as e:
            self.logger.error(f"Error reading version file: {e}")
            return "1.0.0"
    
    def check_for_updates(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if updates are available
        
        Returns:
            Tuple of (update_available, latest_version, update_message)
        """
        try:
            current = self.get_current_version()
            
            # Check if update info file exists on shared drive
            if not self.update_info_path.exists():
                self.logger.debug("No update info file found on shared drive")
                return False, None, None
            
            # Read update info
            with open(self.update_info_path, 'r') as f:
                update_info = json.load(f)
            
            latest_version = update_info.get("version", "0.0.0")
            update_message = update_info.get("message", "")
            update_required = update_info.get("required", False)
            
            # Compare versions
            current_ver = version.parse(current)
            latest_ver = version.parse(latest_version)
            
            if latest_ver > current_ver:
                if update_required:
                    update_message = f"REQUIRED UPDATE: {update_message}"
                return True, latest_version, update_message
            
            return False, latest_version, None
            
        except Exception as e:
            self.logger.error(f"Error checking for updates: {e}")
            return False, None, None
    
    def get_update_path(self) -> Optional[Path]:
        """Get the path to the latest update installer"""
        try:
            latest_version = self.check_for_updates()[1]
            if latest_version:
                update_folder = self.shared_drive_path / "updates" / f"v{latest_version}"
                if update_folder.exists():
                    return update_folder
            return None
        except Exception as e:
            self.logger.error(f"Error getting update path: {e}")
            return None
    
    def write_version_info(self, version: str, message: str = "", required: bool = False):
        """Write version info to shared drive (for deployment scripts)"""
        try:
            # Ensure directory exists
            self.update_info_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write version info
            version_info = {
                "version": version,
                "message": message,
                "required": required,
                "release_date": str(Path.ctime(Path(__file__)))
            }
            
            with open(self.update_info_path, 'w') as f:
                json.dump(version_info, f, indent=2)
                
            self.logger.info(f"Version info written for v{version}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error writing version info: {e}")
            return False


def check_for_updates_on_startup() -> Tuple[bool, Optional[str], Optional[str]]:
    """Convenience function to check for updates on application startup"""
    manager = VersionManager()
    return manager.check_for_updates()


def get_current_version() -> str:
    """Convenience function to get current version"""
    manager = VersionManager()
    return manager.get_current_version()