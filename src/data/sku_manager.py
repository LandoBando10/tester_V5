"""
Updated SKU Manager for Unified Configuration System
Compatible with new GUI configuration editor
Supports both old and new configuration formats
"""

import json
import os
import threading
import time
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SKUData:
    """Data class for SKU information"""
    sku: str
    description: str
    pod_type_ref: str
    power_level_ref: str
    available_modes: List[str]
    backlight_config: Optional[Dict[str, Any]]
    offroad_params: Optional[Dict[str, Any]]
    smt_params: Optional[Dict[str, Any]]
    weightchecking_params: Optional[Dict[str, Any]]


class UnifiedSKUManager:
    """
    SKU Manager for unified configuration system.
    Manages SKUs from centralized skus.json file with full CRUD operations.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Set up configuration paths
        if config_path is None:
            project_root = Path(__file__).parent.parent.parent
            self.config_path = project_root / "config" / "skus.json"
            self.programming_config_path = project_root / "config" / "programming_config.json"
            self.legacy_skus_dir = project_root / "config" / "skus"
        else:
            self.config_path = Path(config_path)
            self.programming_config_path = self.config_path.parent / "programming_config.json"
            self.legacy_skus_dir = self.config_path.parent / "skus"
        
        # Thread-safe data storage
        self._lock = threading.RLock()
        self.data: Optional[Dict[str, Any]] = None
        self.programming_config: Optional[Dict[str, Any]] = None
        self._loaded = False
        self._last_modified = 0
        self._use_legacy = False
        
        # Load configuration
        self._load_configuration()
    
    def _load_configuration(self) -> bool:
        """Load configuration from file system"""
        with self._lock:
            try:
                # Try to load unified configuration first
                if self.config_path.exists():
                    self.logger.info(f"Loading unified configuration from {self.config_path}")
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        self.data = json.load(f)
                    
                    # Load programming configuration
                    if self.programming_config_path.exists():
                        with open(self.programming_config_path, 'r', encoding='utf-8') as f:
                            self.programming_config = json.load(f)
                    else:
                        self.programming_config = {}
                    
                    self._loaded = True
                    self._use_legacy = False
                    self._last_modified = self.config_path.stat().st_mtime
                    
                    self.logger.info(f"Loaded {len(self.get_all_skus())} SKUs from unified configuration")
                    return True
                    
                # Fall back to legacy format if unified doesn't exist
                elif self.legacy_skus_dir.exists():
                    self.logger.warning("Unified configuration not found, using legacy format")
                    self._use_legacy = True
                    self._load_legacy_format()
                    return True
                    
                else:
                    # Create empty configuration
                    self.logger.warning("No configuration found, creating empty configuration")
                    self.data = self._create_empty_configuration()
                    self.programming_config = {}
                    self._loaded = True
                    return True
                    
            except Exception as e:
                self.logger.error(f"Failed to load configuration: {e}")
                self.data = self._create_empty_configuration()
                self.programming_config = {}
                self._loaded = False
                return False
    
    def _create_empty_configuration(self) -> Dict[str, Any]:
        """Create empty configuration structure"""
        return {
            "version": "2.0",
            "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "global_parameters": {
                "PRESSURE": {
                    "min_initial_psi": 14.0,
                    "max_initial_psi": 16.0,
                    "max_delta_psi": 0.5
                }
            },
            "pod_type_definitions": {
                "C1": {"name": "C1 Pod", "connector_type": "DT", "pin_count": 2},
                "C2": {"name": "C2 Pod", "connector_type": "DT", "pin_count": 3},
                "SS3": {"name": "SS3 Pod", "connector_type": "DT", "pin_count": 3}
            },
            "power_level_definitions": {
                "Sport": {"name": "Sport", "relative_power": 0.6},
                "Pro": {"name": "Pro", "relative_power": 0.8},
                "Max": {"name": "Max", "relative_power": 1.0}
            },
            "power_draw_definitions": {},
            "sku_definitions": []
        }
    
    def _load_legacy_format(self):
        """Load SKUs from legacy individual files"""
        # This would implement the legacy loading logic
        # For now, create empty configuration
        self.data = self._create_empty_configuration()
        self.logger.info("Legacy format loading not fully implemented")
    
    def reload_if_changed(self) -> bool:
        """Reload configuration if file has changed"""
        if not self._use_legacy and self.config_path.exists():
            current_mtime = self.config_path.stat().st_mtime
            if current_mtime > self._last_modified:
                self.logger.info("Configuration file changed, reloading")
                return self._load_configuration()
        return False
    
    def save_configuration(self) -> bool:
        """Save configuration to file system"""
        with self._lock:
            try:
                # Ensure directory exists
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Save main configuration
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, indent=2)
                
                # Save programming configuration
                if self.programming_config:
                    with open(self.programming_config_path, 'w', encoding='utf-8') as f:
                        json.dump(self.programming_config, f, indent=2)
                
                self._last_modified = self.config_path.stat().st_mtime
                self.logger.info("Configuration saved successfully")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to save configuration: {e}")
                return False
    
    # Public API methods
    
    def get_all_skus(self) -> List[str]:
        """Get list of all available SKUs"""
        if not self.data:
            return []
        
        with self._lock:
            return [sku["sku"] for sku in self.data.get("sku_definitions", [])]
    
    def get_sku_info(self, sku: str) -> Optional[Dict[str, Any]]:
        """Get complete SKU information"""
        if not self.data:
            return None
        
        with self._lock:
            for sku_def in self.data.get("sku_definitions", []):
                if sku_def["sku"] == sku:
                    return sku_def.copy()
            return None
    
    def create_sku(self, sku_data: Dict[str, Any]) -> bool:
        """Create a new SKU"""
        with self._lock:
            if not self.data:
                return False
            
            # Check if SKU already exists
            if any(s["sku"] == sku_data["sku"] for s in self.data["sku_definitions"]):
                self.logger.error(f"SKU {sku_data['sku']} already exists")
                return False
            
            # Add to definitions
            self.data["sku_definitions"].append(sku_data)
            
            # Save configuration
            return self.save_configuration()
    
    def update_sku(self, sku: str, sku_data: Dict[str, Any]) -> bool:
        """Update an existing SKU"""
        with self._lock:
            if not self.data:
                return False
            
            # Find and update SKU
            for i, sku_def in enumerate(self.data["sku_definitions"]):
                if sku_def["sku"] == sku:
                    # Preserve SKU ID
                    sku_data["sku"] = sku
                    self.data["sku_definitions"][i] = sku_data
                    return self.save_configuration()
            
            self.logger.error(f"SKU {sku} not found")
            return False
    
    def delete_sku(self, sku: str) -> bool:
        """Delete a SKU"""
        with self._lock:
            if not self.data:
                return False
            
            # Remove SKU from definitions
            original_count = len(self.data["sku_definitions"])
            self.data["sku_definitions"] = [
                s for s in self.data["sku_definitions"] if s["sku"] != sku
            ]
            
            if len(self.data["sku_definitions"]) < original_count:
                # Also remove programming config if exists
                if self.programming_config and sku in self.programming_config:
                    del self.programming_config[sku]
                
                return self.save_configuration()
            
            self.logger.error(f"SKU {sku} not found")
            return False
    
    def get_available_modes(self, sku: str) -> List[str]:
        """Get available test modes for a SKU"""
        sku_info = self.get_sku_info(sku)
        if not sku_info:
            return []
        
        return sku_info.get("available_modes", [])
    
    def get_test_parameters(self, sku: str, mode: str) -> Optional[Dict[str, Any]]:
        """Get test parameters for a specific SKU and mode"""
        sku_info = self.get_sku_info(sku)
        if not sku_info:
            return None
        
        # Map modes to parameter keys
        mode_map = {
            "Offroad": "offroad_params",
            "SMT": "smt_params",
            "WeightChecking": "weightchecking_params"
        }
        
        param_key = mode_map.get(mode)
        if param_key and param_key in sku_info:
            params = sku_info[param_key].copy()
            
            # Merge with global parameters if applicable
            if mode == "Offroad" and self.data:
                global_params = self.data.get("global_parameters", {})
                if "PRESSURE" in global_params:
                    params["PRESSURE"] = global_params["PRESSURE"].copy()
            
            return params
        
        return None
    
    def get_programming_config(self, sku: str) -> Optional[Dict[str, Any]]:
        """Get programming configuration for a specific SKU"""
        if not self.programming_config:
            return None
        
        return self.programming_config.get(sku)
    
    def save_programming_config(self, sku: str, config_data: Dict[str, Any]) -> bool:
        """Save programming configuration for a specific SKU"""
        with self._lock:
            if not self.programming_config:
                self.programming_config = {}
            
            self.programming_config[sku] = config_data
            
            try:
                with open(self.programming_config_path, 'w', encoding='utf-8') as f:
                    json.dump(self.programming_config, f, indent=2)
                
                self.logger.info(f"Programming configuration saved for SKU: {sku}")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to save programming config: {e}")
                return False
    
    def delete_programming_config(self, sku: str) -> bool:
        """Delete programming configuration for a specific SKU"""
        with self._lock:
            if self.programming_config and sku in self.programming_config:
                del self.programming_config[sku]
                return self.save_programming_config(sku, {})
            return True
    
    def has_programming_config(self, sku: str) -> bool:
        """Check if a SKU has programming configuration"""
        prog_config = self.get_programming_config(sku)
        return prog_config is not None and prog_config.get('enabled', False)
    
    def get_global_parameters(self) -> Dict[str, Any]:
        """Get global parameters"""
        if not self.data:
            return {}
        
        return self.data.get("global_parameters", {}).copy()
    
    def update_global_parameters(self, params: Dict[str, Any]) -> bool:
        """Update global parameters"""
        with self._lock:
            if not self.data:
                return False
            
            self.data["global_parameters"] = params
            return self.save_configuration()
    
    def validate_sku_mode_combination(self, sku: str, mode: str) -> bool:
        """Check if a SKU supports a specific test mode"""
        available_modes = self.get_available_modes(sku)
        return mode in available_modes
    
    def get_pod_types(self) -> List[str]:
        """Get list of available pod types"""
        if not self.data:
            return []
        
        return list(self.data.get("pod_type_definitions", {}).keys())
    
    def get_power_levels(self) -> List[str]:
        """Get list of available power levels"""
        if not self.data:
            return []
        
        return list(self.data.get("power_level_definitions", {}).keys())
    
    def duplicate_sku(self, source_sku: str, new_sku: str, new_description: str = None) -> bool:
        """Duplicate an existing SKU with a new ID"""
        source_info = self.get_sku_info(source_sku)
        if not source_info:
            self.logger.error(f"Source SKU {source_sku} not found")
            return False
        
        # Create copy with new SKU ID
        new_sku_data = source_info.copy()
        new_sku_data["sku"] = new_sku
        new_sku_data["description"] = new_description or f"Copy of {source_info.get('description', source_sku)}"
        
        # Create the new SKU
        if self.create_sku(new_sku_data):
            # Also duplicate programming config if exists
            source_prog = self.get_programming_config(source_sku)
            if source_prog:
                self.save_programming_config(new_sku, source_prog.copy())
            
            return True
        
        return False
    
    # Additional methods for backward compatibility with old SKUManager
    
    def get_power_draw_params(self, sku: str) -> Optional[Dict[str, float]]:
        """Get power draw parameters based on pod type and power level"""
        sku_data = self.get_sku_info(sku)
        if not sku_data:
            return None
        
        try:
            pod_type = sku_data.get("pod_type_ref")
            power_level = sku_data.get("power_level_ref")
            
            if pod_type and power_level:
                power_key = f"{pod_type}_{power_level}"
                
                with self._lock:
                    if self.data:
                        power_definitions = self.data.get("power_draw_definitions", {})
                        power_params = power_definitions.get(power_key)
                        if not power_params:
                            self.logger.warning(f"Power draw parameters not found for key '{power_key}' (SKU: '{sku}')")
                        return power_params
                    return None
            else:
                self.logger.warning(f"Missing 'pod_type_ref' or 'power_level_ref' for SKU '{sku}'")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting power draw params for SKU '{sku}': {e}")
            return None
    
    def preload_sku(self, sku: str) -> bool:
        """Preload a specific SKU's data (compatibility method - no-op for unified manager)"""
        return self.get_sku_info(sku) is not None
    
    def preload_all_skus(self) -> Dict[str, bool]:
        """Preload all available SKUs (compatibility method - no-op for unified manager)"""
        results = {}
        for sku in self.get_all_skus():
            results[sku] = True  # All SKUs are already loaded in unified format
        return results
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics (compatibility method)"""
        with self._lock:
            sku_count = len(self.get_all_skus())
            return {
                "cached_skus": sku_count,
                "successful_loads": sku_count,
                "failed_loads": 0,
                "available_skus": sku_count
            }
    
    def cleanup(self):
        """Clean up resources (compatibility method)"""
        self.logger.info("Cleaning up SKUManager")
        with self._lock:
            self.data = None
            self.programming_config = None
            self._loaded = False
    
    # Status and utility methods
    
    def is_loaded(self) -> bool:
        """Check if the manager is loaded"""
        return self._loaded
    
    def get_load_status(self) -> Dict[str, Any]:
        """Get loading status information (compatibility method)"""
        if not self._loaded:
            return {"status": "not_loaded", "loaded": False}
        
        with self._lock:
            sku_count = len(self.get_all_skus())
            
            return {
                "status": "ready",
                "loaded": True,
                "sku_count": sku_count,
                "loaded_skus": sku_count,
                "failed_skus": 0,
                "lazy_loading": False  # Unified format loads all at once
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get manager status information"""
        return {
            "loaded": self._loaded,
            "use_legacy": self._use_legacy,
            "config_path": str(self.config_path),
            "sku_count": len(self.get_all_skus()),
            "has_programming_config": self.programming_config is not None
        }
    
    def export_configuration(self, export_path: Path) -> bool:
        """Export configuration to a file"""
        with self._lock:
            try:
                export_data = {
                    "main_config": self.data,
                    "programming_config": self.programming_config
                }
                
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2)
                
                self.logger.info(f"Configuration exported to {export_path}")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to export configuration: {e}")
                return False
    
    def import_configuration(self, import_path: Path) -> bool:
        """Import configuration from a file"""
        with self._lock:
            try:
                with open(import_path, 'r', encoding='utf-8') as f:
                    import_data = json.load(f)
                
                if "main_config" in import_data:
                    self.data = import_data["main_config"]
                    self.programming_config = import_data.get("programming_config", {})
                    return self.save_configuration()
                else:
                    # Assume it's just the main config
                    self.data = import_data
                    return self.save_configuration()
                    
            except Exception as e:
                self.logger.error(f"Failed to import configuration: {e}")
                return False


# Compatibility layer for legacy code - use UnifiedSKUManager as base
class SKUManager(UnifiedSKUManager):
    """Compatibility wrapper for legacy code"""
    
    def _transform_weight_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Transform weight_testing format to WEIGHT format expected by widget"""
        # Already in correct format for unified system
        return params
    
    def _merge_with_global_params(self, params: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Merge SKU-specific parameters with global parameters"""
        # Already handled in get_test_parameters for unified system
        return params


# Factory function for compatibility
def create_sku_manager(config_path: Optional[str] = None) -> SKUManager:
    """Create a SKU manager instance"""
    return SKUManager(config_path)


# Additional factory function for loading test parameters
def load_test_parameters(sku: str, mode: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Load test parameters for a SKU, trying all modes if none specified"""
    try:
        manager = create_sku_manager()
        
        if not manager.is_loaded():
            logger = logging.getLogger(__name__)
            logger.error("SKU manager failed to initialize")
            return None
        
        if mode:
            # Try specific mode
            return manager.get_test_parameters(sku, mode)
        else:
            # Try all modes until we find parameters
            for test_mode in ["Offroad", "SMT", "WeightChecking"]:
                if manager.validate_sku_mode_combination(sku, test_mode):
                    params = manager.get_test_parameters(sku, test_mode)
                    if params:
                        # Add power parameters
                        power_params = manager.get_power_draw_params(sku)
                        if power_params:
                            params['POWER'] = power_params
                        return params
        
        return None
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error loading test parameters for SKU {sku}: {e}")
        return None


if __name__ == "__main__":
    # Test the unified SKU manager
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Testing Unified SKU Manager...")
    manager = create_sku_manager()
    
    print(f"Manager status: {manager.get_status()}")
    print(f"Available SKUs: {manager.get_all_skus()}")
    print(f"Pod types: {manager.get_pod_types()}")
    print(f"Power levels: {manager.get_power_levels()}")
    
    # Test SKU operations
    test_sku = {
        "sku": "TEST001",
        "description": "Test SKU",
        "pod_type_ref": "C1",
        "power_level_ref": "Sport",
        "available_modes": ["Offroad"],
        "offroad_params": {
            "LUX": {"min_mainbeam_lux": 1000, "max_mainbeam_lux": 1500}
        }
    }
    
    print(f"\nCreating test SKU: {manager.create_sku(test_sku)}")
    print(f"Test SKU info: {manager.get_sku_info('TEST001')}")
    print(f"Deleting test SKU: {manager.delete_sku('TEST001')}")
