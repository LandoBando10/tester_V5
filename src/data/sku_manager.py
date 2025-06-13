"""
Lazy-Loading SKU Manager
Simple, elegant, and maintainable SKU management with lazy loading
"""

import json
import os
import threading
import time
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass


@dataclass
class SKULoadResult:
    """Result of individual SKU loading operation"""
    success: bool
    sku: str
    error_message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    load_time: float = 0.0


class SKUManager:
    """
    Lazy-loading SKU manager with thread-safe caching.
    Loads SKU data only when first accessed, using config/skus/ directory.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Set up configuration paths
        if config_path is None:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            self.config_path = os.path.join(project_root, "config", "skus.json")
            self.skus_directory = os.path.join(project_root, "config", "skus")
        else:
            self.config_path = config_path
            self.skus_directory = os.path.join(os.path.dirname(config_path), "skus")
        
        # Thread-safe data storage
        self._lock = threading.RLock()
        self._index_data: Optional[Dict[str, Any]] = None
        self._sku_cache: Dict[str, SKULoadResult] = {}
        self._available_skus: Optional[List[str]] = None
        self._global_parameters: Optional[Dict[str, Any]] = None
        self._index_loaded = False
        self._failed_skus: Set[str] = set()
        
        self.logger.info(f"SKUManager initialized with config: {self.config_path}")
        self.logger.info(f"SKUs directory: {self.skus_directory}")
    
    def _load_index_if_needed(self) -> bool:
        """Load the SKU index file if not already loaded (thread-safe)"""
        with self._lock:
            if self._index_loaded:
                return True
            
            try:
                if not os.path.exists(self.config_path):
                    self.logger.error(f"SKU index file not found: {self.config_path}")
                    return False
                
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._index_data = json.load(f)
                
                # Extract available SKUs and global parameters
                self._available_skus = []
                if 'available_skus' in self._index_data:
                    for sku_ref in self._index_data['available_skus']:
                        if sku_ref.get('enabled', True):
                            self._available_skus.append(sku_ref['sku'])
                
                self._global_parameters = self._index_data.get('global_parameters', {})
                self._index_loaded = True
                
                self.logger.info(f"Loaded SKU index with {len(self._available_skus)} available SKUs")
                return True
                
            except (json.JSONDecodeError, IOError, KeyError) as e:
                self.logger.error(f"Failed to load SKU index: {e}")
                return False
    
    def _get_sku_file_path(self, sku: str) -> Optional[str]:
        """Get the file path for a specific SKU"""
        if not self._load_index_if_needed():
            return None
        
        with self._lock:
            if 'available_skus' in self._index_data:
                for sku_ref in self._index_data['available_skus']:
                    if sku_ref['sku'] == sku and sku_ref.get('enabled', True):
                        config_file = sku_ref.get('config_file')
                        if config_file:
                            # Convert relative path to absolute
                            if not os.path.isabs(config_file):
                                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
                                config_file = os.path.join(project_root, config_file)
                            return config_file
            
            # Fallback: try standard naming in skus directory
            fallback_path = os.path.join(self.skus_directory, f"{sku}.json")
            if os.path.exists(fallback_path):
                self.logger.debug(f"Using fallback path for {sku}: {fallback_path}")
                return fallback_path
            
            return None
    
    def _load_sku_data(self, sku: str) -> SKULoadResult:
        """Load data for a specific SKU"""
        start_time = time.time()
        
        try:
            sku_file_path = self._get_sku_file_path(sku)
            if not sku_file_path:
                error_msg = f"No config file found for SKU: {sku}"
                self.logger.warning(error_msg)
                return SKULoadResult(success=False, sku=sku, error_message=error_msg)
            
            if not os.path.exists(sku_file_path):
                error_msg = f"SKU config file not found: {sku_file_path}"
                self.logger.warning(error_msg)
                return SKULoadResult(success=False, sku=sku, error_message=error_msg)
            
            with open(sku_file_path, 'r', encoding='utf-8') as f:
                sku_data = json.load(f)
            
            load_time = time.time() - start_time
            self.logger.debug(f"Loaded SKU {sku} in {load_time:.3f}s")
            
            return SKULoadResult(
                success=True,
                sku=sku,
                data=sku_data,
                load_time=load_time
            )
            
        except (json.JSONDecodeError, IOError) as e:
            error_msg = f"Error loading SKU {sku}: {e}"
            self.logger.error(error_msg)
            return SKULoadResult(success=False, sku=sku, error_message=error_msg)
    
    def _get_cached_sku_data(self, sku: str) -> Optional[Dict[str, Any]]:
        """Get cached SKU data, loading if necessary (thread-safe)"""
        with self._lock:
            # Check if we've already failed to load this SKU
            if sku in self._failed_skus:
                return None
            
            # Check cache first
            if sku in self._sku_cache:
                result = self._sku_cache[sku]
                if result.success:
                    return result.data
                else:
                    return None
            
            # Load the SKU data
            result = self._load_sku_data(sku)
            self._sku_cache[sku] = result
            
            if not result.success:
                self._failed_skus.add(sku)
                return None
            
            return result.data
    
    # Public API methods
    
    def get_all_skus(self) -> List[str]:
        """Get list of all available SKUs"""
        if not self._load_index_if_needed():
            return []
        
        with self._lock:
            return self._available_skus.copy() if self._available_skus else []
    
    def get_sku_info(self, sku: str) -> Optional[Dict[str, Any]]:
        """Get complete SKU information"""
        return self._get_cached_sku_data(sku)
    
    def get_available_modes(self, sku: str) -> List[str]:
        """Get available test modes for a SKU"""
        sku_data = self._get_cached_sku_data(sku)
        if not sku_data:
            return []
        
        # Extract available modes from the SKU data
        modes = []
        # Check for both old and new parameter naming schemes
        if 'offroad_params' in sku_data or 'offroad_testing' in sku_data:
            modes.append('Offroad')
        if 'smt_params' in sku_data or 'smt_testing' in sku_data:
            modes.append('SMT')
        if 'weightchecking_params' in sku_data or 'weight_testing' in sku_data:
            modes.append('WeightChecking')
        
        # Also check for a direct 'available_modes' field
        if 'available_modes' in sku_data:
            modes.extend(sku_data['available_modes'])
        
        return list(set(modes))  # Remove duplicates
    
    def get_test_parameters(self, sku: str, mode: str) -> Optional[Dict[str, Any]]:
        """Get test parameters for a specific SKU and mode"""
        sku_data = self._get_cached_sku_data(sku)
        if not sku_data:
            return None
        
        # Check for both old and new parameter naming schemes
        mode_maps = {
            "Offroad": ["offroad_params", "offroad_testing"],
            "SMT": ["smt_params", "smt_testing"], 
            "WeightChecking": ["weightchecking_params", "weight_testing"]
        }
        
        param_keys = mode_maps.get(mode, [])
        for param_key in param_keys:
            if param_key in sku_data:
                params = sku_data[param_key].copy()
                
                # Transform weight parameters to expected format
                if mode == "WeightChecking" and param_key == "weight_testing":
                    params = self._transform_weight_params(params)
                
                # Merge with global parameters if applicable
                try:
                    return self._merge_with_global_params(params, mode)
                except Exception as e:
                    self.logger.error(f"Error merging global params for SKU '{sku}', mode '{mode}': {e}")
                    return params
        
        self.logger.warning(f"No parameters found for SKU '{sku}' in mode '{mode}'")
        return None
    
    def get_power_draw_params(self, sku: str) -> Optional[Dict[str, float]]:
        """Get power draw parameters based on pod type and power level"""
        sku_data = self._get_cached_sku_data(sku)
        if not sku_data:
            return None
        
        try:
            pod_type = sku_data.get("pod_type_ref")
            power_level = sku_data.get("power_level_ref")
            
            if pod_type and power_level:
                power_key = f"{pod_type}_{power_level}"
                
                # Load index to get power draw definitions
                if not self._load_index_if_needed():
                    return None
                
                with self._lock:
                    power_params = self._index_data.get("power_draw_definitions", {}).get(power_key)
                    if not power_params:
                        self.logger.warning(f"Power draw parameters not found for key '{power_key}' (SKU: '{sku}')")
                    return power_params
            else:
                self.logger.warning(f"Missing 'pod_type_ref' or 'power_level_ref' for SKU '{sku}'")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting power draw params for SKU '{sku}': {e}")
            return None
    
    def validate_sku_mode_combination(self, sku: str, mode: str) -> bool:
        """Check if a SKU supports a specific test mode"""
        available_modes = self.get_available_modes(sku)
        return mode in available_modes
    
    def get_programming_config(self, sku: str) -> Optional[Dict[str, Any]]:
        """Get programming configuration for a specific SKU"""
        sku_data = self._get_cached_sku_data(sku)
        if sku_data:
            smt_config = sku_data.get('smt_testing', {})
            return smt_config.get('programming')
        return None
    
    def save_programming_config(self, sku: str, config_data: Dict[str, Any]) -> bool:
        """Save programming configuration for a specific SKU"""
        # For now, just log as this would require file modification
        self.logger.info(f"Programming config save requested for SKU: {sku}")
        self.logger.debug(f"Config data: {config_data}")
        return True
    
    def delete_programming_config(self, sku: str) -> bool:
        """Delete programming configuration for a specific SKU"""
        self.logger.info(f"Programming config deletion requested for SKU: {sku}")
        return True
    
    def has_programming_config(self, sku: str) -> bool:
        """Check if a SKU has programming configuration"""
        prog_config = self.get_programming_config(sku)
        return prog_config is not None and prog_config.get('enabled', False)
    
    # Status and utility methods
    
    def is_loaded(self) -> bool:
        """Check if the manager is ready (index loaded)"""
        return self._index_loaded
    
    def get_load_status(self) -> Dict[str, Any]:
        """Get loading status information"""
        if not self._index_loaded:
            return {"status": "not_loaded", "loaded": False}
        
        with self._lock:
            sku_count = len(self._available_skus) if self._available_skus else 0
            loaded_count = len([r for r in self._sku_cache.values() if r.success])
            
            return {
                "status": "ready",
                "loaded": True,
                "sku_count": sku_count,
                "loaded_skus": loaded_count,
                "failed_skus": len(self._failed_skus),
                "lazy_loading": True
            }
    
    def cleanup(self):
        """Clean up resources"""
        self.logger.info("Cleaning up SKUManager")
        with self._lock:
            self._sku_cache.clear()
            self._failed_skus.clear()
            self._index_data = None
            self._available_skus = None
            self._global_parameters = None
            self._index_loaded = False
    
    def _transform_weight_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Transform weight_testing format to WEIGHT format expected by widget"""
        transformed = {}
        
        try:
            # Extract weight limits
            if "limits" in params and "weight_g" in params["limits"]:
                weight_limits = params["limits"]["weight_g"]
                transformed["WEIGHT"] = {
                    "min_weight_g": weight_limits.get("min", 0.0),
                    "max_weight_g": weight_limits.get("max", 0.0),
                    "tare_g": params.get("tare_g", 0.0)
                }
            else:
                # Fallback for other potential formats
                self.logger.warning("Weight parameters not in expected format, using defaults")
                transformed["WEIGHT"] = {
                    "min_weight_g": 100.0,
                    "max_weight_g": 300.0,
                    "tare_g": 0.0
                }
                
            self.logger.debug(f"Transformed weight params: {transformed}")
            
        except Exception as e:
            self.logger.error(f"Error transforming weight parameters: {e}")
            # Return default structure on error
            transformed["WEIGHT"] = {
                "min_weight_g": 100.0,
                "max_weight_g": 300.0,
                "tare_g": 0.0
            }
            
        return transformed
    
    def _transform_weight_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Transform weight_testing format to WEIGHT format expected by the widget"""
        if "limits" in params and "weight_g" in params["limits"]:
            weight_limits = params["limits"]["weight_g"]
            transformed = {
                "WEIGHT": {
                    "min_weight_g": weight_limits.get("min", 0.0),
                    "max_weight_g": weight_limits.get("max", 0.0),
                    "tare_g": params.get("tare_g", 0.0)
                }
            }
            return transformed
        
        # If already in the expected format, return as-is
        return params
    
    def _merge_with_global_params(self, params: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Merge SKU-specific parameters with global parameters"""
        merged = params.copy()
        
        if not self._load_index_if_needed():
            return merged
        
        with self._lock:
            if mode == "Offroad" and self._global_parameters:
                if "PRESSURE" in self._global_parameters:
                    if "PRESSURE" not in merged or not isinstance(merged.get("PRESSURE"), dict):
                        merged["PRESSURE"] = self._global_parameters["PRESSURE"].copy()
                    else:
                        # Deep merge pressure parameters
                        merged["PRESSURE"].update(self._global_parameters["PRESSURE"])
                    self.logger.debug("Merged PRESSURE params from global_parameters")
        
        return merged
    
    # Additional utility methods
    
    def preload_sku(self, sku: str) -> bool:
        """Preload a specific SKU's data"""
        result = self._get_cached_sku_data(sku)
        return result is not None
    
    def preload_all_skus(self) -> Dict[str, bool]:
        """Preload all available SKUs"""
        results = {}
        all_skus = self.get_all_skus()
        
        for sku in all_skus:
            results[sku] = self.preload_sku(sku)
        
        self.logger.info(f"Preloaded {sum(results.values())}/{len(results)} SKUs")
        return results
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        with self._lock:
            return {
                "cached_skus": len(self._sku_cache),
                "successful_loads": len([r for r in self._sku_cache.values() if r.success]),
                "failed_loads": len(self._failed_skus),
                "available_skus": len(self._available_skus) if self._available_skus else 0
            }


# Factory functions for easy access
def create_sku_manager(config_path: Optional[str] = None) -> SKUManager:
    """Create a SKU manager instance"""
    manager = SKUManager(config_path)
    # Trigger index loading for immediate availability
    manager.get_all_skus()
    return manager


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
    # Test the lazy loading manager
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Testing lazy-loading SKUManager...")
    manager = create_sku_manager()
    
    print(f"Manager loaded: {manager.is_loaded()}")
    print(f"Available SKUs: {manager.get_all_skus()}")
    
    # Test lazy loading
    all_skus = manager.get_all_skus()
    if all_skus:
        test_sku = all_skus[0]
        print(f"\nTesting SKU: {test_sku}")
        print(f"Available modes: {manager.get_available_modes(test_sku)}")
        
        # Test parameters
        modes = manager.get_available_modes(test_sku)
        for mode in modes:
            params = manager.get_test_parameters(test_sku, mode)
            print(f"{mode} params: {list(params.keys()) if params else 'None'}")
    
    print(f"\nCache stats: {manager.get_cache_stats()}")
    print(f"Load status: {manager.get_load_status()}")
    print("Test completed")