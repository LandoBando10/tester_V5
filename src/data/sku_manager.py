"""
SKU Manager for individual SKU JSON files
Loads SKUs from config/skus/ directory
"""

import json
import os
import threading
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path


class SKUManager:
    """
    SKU Manager that loads individual SKU JSON files from config/skus/ directory
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Set up configuration paths
        project_root = Path(__file__).parent.parent.parent
        self.skus_dir = project_root / "config" / "skus"
        self.programming_config_path = project_root / "config" / "programming_config.json"
        
        # Thread-safe data storage
        self._lock = threading.RLock()
        self.skus_data: Dict[str, Dict[str, Any]] = {}
        self.programming_config: Optional[Dict[str, Any]] = None
        self._loaded = False
        
        # Load all SKUs
        self._load_all_skus()
    
    def _load_all_skus(self) -> bool:
        """Load all SKU files from the skus directory"""
        with self._lock:
            try:
                if not self.skus_dir.exists():
                    self.logger.error(f"SKUs directory not found: {self.skus_dir}")
                    return False
                
                # Clear existing data
                self.skus_data.clear()
                
                # Load each JSON file in the directory
                json_files = list(self.skus_dir.glob("*.json"))
                if not json_files:
                    self.logger.warning(f"No SKU files found in {self.skus_dir}")
                    return False
                
                for json_file in json_files:
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            sku_data = json.load(f)
                        
                        # Get SKU identifier from the data
                        sku = sku_data.get('sku')
                        if not sku:
                            self.logger.warning(f"SKU file {json_file} missing 'sku' field")
                            continue
                        
                        self.skus_data[sku] = sku_data
                        self.logger.info(f"Loaded SKU: {sku} from {json_file.name}")
                        
                    except Exception as e:
                        self.logger.error(f"Failed to load SKU file {json_file}: {e}")
                
                # Load programming configuration if it exists
                if self.programming_config_path.exists():
                    try:
                        with open(self.programming_config_path, 'r', encoding='utf-8') as f:
                            self.programming_config = json.load(f)
                    except Exception as e:
                        self.logger.error(f"Failed to load programming config: {e}")
                        self.programming_config = {}
                else:
                    self.programming_config = {}
                
                self._loaded = len(self.skus_data) > 0
                self.logger.info(f"Loaded {len(self.skus_data)} SKUs successfully")
                return self._loaded
                
            except Exception as e:
                self.logger.error(f"Failed to load SKUs: {e}")
                self._loaded = False
                return False
    
    def reload_if_changed(self) -> bool:
        """Reload all SKUs (for compatibility)"""
        return self._load_all_skus()
    
    def get_all_skus(self) -> List[str]:
        """Get list of all available SKUs"""
        with self._lock:
            return list(self.skus_data.keys())
    
    def get_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """Get complete SKU data"""
        with self._lock:
            return self.skus_data.get(sku)
    
    def get_sku_info(self, sku: str) -> Optional[Dict[str, Any]]:
        """Get complete SKU information (alias for get_sku)"""
        return self.get_sku(sku)
    
    def get_available_modes(self, sku: str) -> List[str]:
        """Get available test modes for a SKU"""
        sku_data = self.get_sku(sku)
        if not sku_data:
            return []
        
        return sku_data.get("available_modes", [])
    
    def get_test_parameters(self, sku: str, mode: str) -> Optional[Dict[str, Any]]:
        """Get test parameters for a specific SKU and mode"""
        sku_data = self.get_sku(sku)
        if not sku_data:
            return None
        
        # Map modes to parameter keys
        mode_map = {
            "Offroad": "offroad_testing",
            "SMT": "smt_testing",
            "WeightChecking": "weight_testing"
        }
        
        param_key = mode_map.get(mode)
        if param_key and param_key in sku_data:
            params = sku_data[param_key].copy()
            
            # Add SKU info to parameters
            params['sku'] = sku
            params['description'] = sku_data.get('description', '')
            params['pod_type'] = sku_data.get('pod_type', '')
            params['power_level'] = sku_data.get('power_level', '')
            
            return params
        
        return None
    
    def get_programming_config(self, sku: str) -> Optional[Dict[str, Any]]:
        """Get programming configuration for a specific SKU"""
        # First check if SKU has inline programming config
        sku_data = self.get_sku(sku)
        if sku_data:
            smt_config = sku_data.get('smt_testing', {})
            if 'programming' in smt_config:
                return smt_config['programming']
        
        # Fall back to separate programming config file
        if self.programming_config:
            return self.programming_config.get(sku)
        
        return None
    
    def has_programming_config(self, sku: str) -> bool:
        """Check if a SKU has programming configuration"""
        prog_config = self.get_programming_config(sku)
        return prog_config is not None and prog_config.get('enabled', False)
    
    def validate_sku_mode_combination(self, sku: str, mode: str) -> bool:
        """Check if a SKU supports a specific test mode"""
        available_modes = self.get_available_modes(sku)
        return mode in available_modes
    
    def preload_sku(self, sku: str) -> bool:
        """Preload a specific SKU's data (compatibility method)"""
        return self.get_sku(sku) is not None
    
    def preload_all_skus(self) -> Dict[str, bool]:
        """Preload all available SKUs (compatibility method)"""
        results = {}
        for sku in self.get_all_skus():
            results[sku] = True
        return results
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics (compatibility method)"""
        with self._lock:
            sku_count = len(self.skus_data)
            return {
                "cached_skus": sku_count,
                "successful_loads": sku_count,
                "failed_loads": 0,
                "available_skus": sku_count
            }
    
    def is_loaded(self) -> bool:
        """Check if the manager is loaded"""
        return self._loaded
    
    def get_load_status(self) -> Dict[str, Any]:
        """Get loading status information"""
        with self._lock:
            sku_count = len(self.skus_data)
            
            return {
                "status": "ready" if self._loaded else "not_loaded",
                "loaded": self._loaded,
                "sku_count": sku_count,
                "loaded_skus": sku_count,
                "failed_skus": 0,
                "lazy_loading": False
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get manager status information"""
        return {
            "loaded": self._loaded,
            "skus_dir": str(self.skus_dir),
            "sku_count": len(self.skus_data),
            "has_programming_config": self.programming_config is not None
        }
    
    def cleanup(self):
        """Clean up resources"""
        self.logger.info("Cleaning up SKUManager")
        with self._lock:
            self.skus_data.clear()
            self.programming_config = None
            self._loaded = False
    
    # Power draw compatibility methods
    def get_power_draw_params(self, sku: str) -> Optional[Dict[str, float]]:
        """Get power draw parameters for a SKU"""
        sku_data = self.get_sku(sku)
        if not sku_data:
            return None
        
        # For now, return empty dict - can be extended if needed
        return {}


# Factory functions for compatibility
def create_sku_manager(config_path: Optional[str] = None) -> SKUManager:
    """Create a SKU manager instance"""
    return SKUManager(config_path)


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
                        return params
        
        return None
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error loading test parameters for SKU {sku}: {e}")
        return None


if __name__ == "__main__":
    # Test the SKU manager
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Testing SKU Manager...")
    manager = create_sku_manager()
    
    print(f"Manager status: {manager.get_status()}")
    print(f"Available SKUs: {manager.get_all_skus()}")
    
    # Test loading a specific SKU
    for sku in manager.get_all_skus():
        print(f"\nSKU: {sku}")
        print(f"  Info: {manager.get_sku_info(sku)}")
        print(f"  Modes: {manager.get_available_modes(sku)}")