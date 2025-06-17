"""
Configuration Format Adapter
Allows GUI components to work with existing SKU JSON format
Provides bidirectional conversion between GUI expected format and actual file format
"""

from typing import Dict, Any, List, Optional, Tuple
import copy
import logging

logger = logging.getLogger(__name__)


class SKUFormatAdapter:
    """
    Adapter to convert between existing SKU file format and GUI component expectations.
    This allows the GUI to work with your existing JSON structure without changing files.
    """
    
    @staticmethod
    def from_file_to_gui(file_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert from existing file format to format expected by GUI components.
        
        File format uses:
        - pod_type, power_level
        - offroad_testing, smt_testing, weight_testing
        - Different internal structures
        
        GUI expects:
        - pod_type_ref, power_level_ref  
        - offroad_params, smt_params, weightchecking_params
        - Standardized parameter structures
        """
        gui_data = copy.deepcopy(file_data)
        
        # Basic field mappings
        if "pod_type" in gui_data:
            gui_data["pod_type_ref"] = gui_data.pop("pod_type")
        if "power_level" in gui_data:
            gui_data["power_level_ref"] = gui_data.pop("power_level")
        
        # Convert offroad_testing to offroad_params
        if "offroad_testing" in gui_data:
            offroad_params = SKUFormatAdapter._convert_offroad_testing_to_params(
                gui_data.pop("offroad_testing")
            )
            gui_data["offroad_params"] = offroad_params
            
            # Extract backlight config from offroad testing
            backlight_config = SKUFormatAdapter._extract_backlight_from_offroad(
                file_data.get("offroad_testing", {})
            )
            if backlight_config:
                gui_data["backlight_config"] = backlight_config
        
        # Convert smt_testing to smt_params
        if "smt_testing" in gui_data:
            smt_params = SKUFormatAdapter._convert_smt_testing_to_params(
                gui_data["smt_testing"]
            )
            gui_data["smt_params"] = smt_params
            # Keep original smt_testing for panel layout info
        
        # Convert weight_testing to weightchecking_params
        if "weight_testing" in gui_data:
            weight_params = SKUFormatAdapter._convert_weight_testing_to_params(
                gui_data.pop("weight_testing")
            )
            gui_data["weightchecking_params"] = weight_params
        
        return gui_data
    
    @staticmethod
    def from_gui_to_file(gui_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert from GUI format back to existing file format for saving.
        """
        file_data = copy.deepcopy(gui_data)
        
        # Basic field mappings
        if "pod_type_ref" in file_data:
            file_data["pod_type"] = file_data.pop("pod_type_ref")
        if "power_level_ref" in file_data:
            file_data["power_level"] = file_data.pop("power_level_ref")
        
        # Convert offroad_params back to offroad_testing
        if "offroad_params" in file_data:
            offroad_testing = SKUFormatAdapter._convert_offroad_params_to_testing(
                file_data.pop("offroad_params"),
                file_data.get("backlight_config")
            )
            if offroad_testing:
                file_data["offroad_testing"] = offroad_testing
        
        # Remove backlight_config as it's embedded in offroad_testing
        if "backlight_config" in file_data:
            file_data.pop("backlight_config")
        
        # Convert smt_params back to smt_testing
        if "smt_params" in file_data:
            # Merge with existing smt_testing to preserve panel_layout
            existing_smt = file_data.get("smt_testing", {})
            smt_testing = SKUFormatAdapter._convert_smt_params_to_testing(
                file_data.pop("smt_params"),
                existing_smt
            )
            file_data["smt_testing"] = smt_testing
        
        # Convert weightchecking_params back to weight_testing
        if "weightchecking_params" in file_data:
            weight_testing = SKUFormatAdapter._convert_weight_params_to_testing(
                file_data.pop("weightchecking_params")
            )
            file_data["weight_testing"] = weight_testing
        
        return file_data
    
    @staticmethod
    def _convert_offroad_testing_to_params(offroad_testing: Dict[str, Any]) -> Dict[str, Any]:
        """Convert offroad_testing structure to GUI params format"""
        params = {}
        test_sequence = offroad_testing.get("test_sequence", [])
        
        # Initialize parameter categories
        current_params = {}
        lux_params = {}
        color_params = {}
        
        for test in test_sequence:
            test_name = test.get("name", "").lower()
            limits = test.get("limits", {})
            measurements = test.get("measurements", [])
            
            # Extract current limits
            if "current_A" in limits:
                current_limits = limits["current_A"]
                if "mainbeam" in test_name:
                    current_params["min_mainbeam_current_A"] = current_limits.get("min", 0.5)
                    current_params["max_mainbeam_current_A"] = current_limits.get("max", 1.0)
                elif "backlight" in test_name:
                    current_params["min_backlight_current_A"] = current_limits.get("min", 0.05)
                    current_params["max_backlight_current_A"] = current_limits.get("max", 0.15)
            
            # Extract lux limits
            if "lux" in limits:
                lux_limits = limits["lux"]
                if "mainbeam" in test_name:
                    lux_params["min_mainbeam_lux"] = lux_limits.get("min", 1000)
                    lux_params["max_mainbeam_lux"] = lux_limits.get("max", 2000)
                elif "backlight" in test_name:
                    lux_params["min_backlight_lux"] = lux_limits.get("min", 100)
                    lux_params["max_backlight_lux"] = lux_limits.get("max", 200)
            
            # Extract color parameters
            if "color_x" in limits and "color_y" in limits:
                if "mainbeam" in test_name:
                    color_params["center_x_main"] = limits["color_x"].get("center", 0.45)
                    color_params["center_y_main"] = limits["color_y"].get("center", 0.41)
                    color_params["radius_x_main"] = limits["color_x"].get("tolerance", 0.015)
                    color_params["radius_y_main"] = limits["color_y"].get("tolerance", 0.015)
                    color_params["angle_deg_main"] = 0
        
        # Add to params if data exists
        if current_params:
            params["CURRENT"] = current_params
        if lux_params:
            params["LUX"] = lux_params
        if color_params:
            params["COLOR"] = color_params
        
        # Add default pressure params
        params["PRESSURE"] = {
            "min_initial_psi": 14.0,
            "max_initial_psi": 16.0,
            "max_delta_psi": 0.5
        }
        
        return params
    
    @staticmethod
    def _extract_backlight_from_offroad(offroad_testing: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract backlight configuration from offroad testing"""
        test_sequence = offroad_testing.get("test_sequence", [])
        backlight_tests = [t for t in test_sequence if "backlight" in t.get("name", "").lower()]
        
        if not backlight_tests:
            return None
        
        # Determine configuration from tests
        relay_pins = []
        for test in backlight_tests:
            relay = test.get("relay", "")
            if "1" in relay or "left" in relay:
                if 3 not in relay_pins:
                    relay_pins.append(3)
            elif "2" in relay or "right" in relay:
                if 4 not in relay_pins:
                    relay_pins.append(4)
            else:
                # Default single backlight
                if 3 not in relay_pins:
                    relay_pins.append(3)
        
        backlight_type = "dual" if len(relay_pins) > 1 else "single"
        
        return {
            "type": backlight_type,
            "relay_pins": sorted(relay_pins),
            "test_duration_ms": backlight_tests[0].get("duration_ms", 500)
        }
    
    @staticmethod
    def _convert_smt_testing_to_params(smt_testing: Dict[str, Any]) -> Dict[str, Any]:
        """Convert smt_testing structure to GUI params format"""
        params = {}
        
        # Extract power test parameters from test sequence
        test_sequence = smt_testing.get("test_sequence", [])
        for test in test_sequence:
            if test.get("function") == "mainbeam":
                limits = test.get("limits", {})
                current_limits = limits.get("current_A", {})
                
                params["POWER"] = {
                    "sequence_id": "SMT_SEQ_A",
                    "min_mainbeam_current_A": current_limits.get("min", 0.5),
                    "max_mainbeam_current_A": current_limits.get("max", 1.0)
                }
                break
        
        # Preserve panel layout info
        if "panel_layout" in smt_testing:
            params["panel_layout"] = smt_testing["panel_layout"]
        
        return params
    
    @staticmethod
    def _convert_weight_testing_to_params(weight_testing: Dict[str, Any]) -> Dict[str, Any]:
        """Convert weight_testing structure to GUI params format"""
        params = {}
        
        limits = weight_testing.get("limits", {})
        weight_limits = limits.get("weight_g", {})
        
        params["WEIGHT"] = {
            "min_weight_g": weight_limits.get("min", 100.0),
            "max_weight_g": weight_limits.get("max", 200.0),
            "tare_g": weight_testing.get("tare_g", 0.5)
        }
        
        return params
    
    @staticmethod
    def _convert_offroad_params_to_testing(params: Dict[str, Any], 
                                          backlight_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Convert GUI offroad params back to testing format"""
        test_sequence = []
        
        # Create mainbeam test
        mainbeam_test = {
            "name": "mainbeam",
            "relay": "main",
            "duration_ms": 500,
            "measurements": [],
            "limits": {}
        }
        
        # Add current measurements and limits
        if "CURRENT" in params:
            current_params = params["CURRENT"]
            mainbeam_test["measurements"].append("current")
            mainbeam_test["measurements"].append("voltage")
            mainbeam_test["limits"]["current_A"] = {
                "min": current_params.get("min_mainbeam_current_A", 0.5),
                "max": current_params.get("max_mainbeam_current_A", 1.0)
            }
        
        # Add lux measurements and limits
        if "LUX" in params:
            lux_params = params["LUX"]
            mainbeam_test["measurements"].append("lux")
            mainbeam_test["limits"]["lux"] = {
                "min": lux_params.get("min_mainbeam_lux", 1000),
                "max": lux_params.get("max_mainbeam_lux", 2000)
            }
        
        # Add color measurements and limits
        if "COLOR" in params:
            color_params = params["COLOR"]
            mainbeam_test["measurements"].append("color")
            mainbeam_test["limits"]["color_x"] = {
                "center": color_params.get("center_x_main", 0.45),
                "tolerance": color_params.get("radius_x_main", 0.015)
            }
            mainbeam_test["limits"]["color_y"] = {
                "center": color_params.get("center_y_main", 0.41),
                "tolerance": color_params.get("radius_y_main", 0.015)
            }
        
        test_sequence.append(mainbeam_test)
        
        # Add backlight tests if configured
        if backlight_config:
            relay_pins = backlight_config.get("relay_pins", [3])
            duration = backlight_config.get("test_duration_ms", 500)
            
            if len(relay_pins) > 1:
                # Dual backlight
                for i, pin in enumerate(relay_pins):
                    backlight_test = {
                        "name": f"backlight_{'left' if i == 0 else 'right'}",
                        "relay": f"backlight_{i+1}",
                        "duration_ms": duration,
                        "measurements": ["current", "voltage"],
                        "limits": {}
                    }
                    
                    if "CURRENT" in params:
                        backlight_test["limits"]["current_A"] = {
                            "min": params["CURRENT"].get("min_backlight_current_A", 0.05),
                            "max": params["CURRENT"].get("max_backlight_current_A", 0.15)
                        }
                    
                    test_sequence.append(backlight_test)
            else:
                # Single backlight
                backlight_test = {
                    "name": "backlight",
                    "relay": "backlight",
                    "duration_ms": duration,
                    "measurements": ["current", "voltage"],
                    "limits": {}
                }
                
                if "CURRENT" in params:
                    backlight_test["limits"]["current_A"] = {
                        "min": params["CURRENT"].get("min_backlight_current_A", 0.05),
                        "max": params["CURRENT"].get("max_backlight_current_A", 0.15)
                    }
                
                test_sequence.append(backlight_test)
        
        return {"test_sequence": test_sequence}
    
    @staticmethod
    def _convert_smt_params_to_testing(params: Dict[str, Any], 
                                      existing_smt: Dict[str, Any]) -> Dict[str, Any]:
        """Convert GUI SMT params back to testing format"""
        smt_testing = copy.deepcopy(existing_smt)
        
        # Update test sequence with new limits
        if "POWER" in params:
            power_params = params["POWER"]
            
            # Find or create mainbeam test
            test_sequence = smt_testing.get("test_sequence", [])
            mainbeam_test = None
            
            for test in test_sequence:
                if test.get("function") == "mainbeam":
                    mainbeam_test = test
                    break
            
            if not mainbeam_test:
                mainbeam_test = {
                    "function": "mainbeam",
                    "limits": {}
                }
                test_sequence.insert(0, mainbeam_test)
            
            # Update limits
            mainbeam_test["limits"]["current_A"] = {
                "min": power_params.get("min_mainbeam_current_A", 0.5),
                "max": power_params.get("max_mainbeam_current_A", 1.0)
            }
            
            if "voltage_V" not in mainbeam_test["limits"]:
                mainbeam_test["limits"]["voltage_V"] = {
                    "min": 11.5,
                    "max": 12.5
                }
            
            smt_testing["test_sequence"] = test_sequence
        
        return smt_testing
    
    @staticmethod
    def _convert_weight_params_to_testing(params: Dict[str, Any]) -> Dict[str, Any]:
        """Convert GUI weight params back to testing format"""
        weight_testing = {}
        
        if "WEIGHT" in params:
            weight_params = params["WEIGHT"]
            weight_testing["limits"] = {
                "weight_g": {
                    "min": weight_params.get("min_weight_g", 100.0),
                    "max": weight_params.get("max_weight_g", 200.0)
                }
            }
            weight_testing["tare_g"] = weight_params.get("tare_g", 0.5)
        
        return weight_testing
    
    @staticmethod
    def extract_programming_config(file_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract programming configuration from SMT testing data"""
        smt_testing = file_data.get("smt_testing", {})
        prog_data = smt_testing.get("programming", {})
        
        if not prog_data.get("enabled", False):
            return None
        
        # Create a standardized programming config
        config = {
            "enabled": True,
            "description": prog_data.get("note", "Programming configuration"),
            "programmers": {},
            "hex_files": {},
            "programming_sequence": []
        }
        
        # Try to infer configuration from note
        note = prog_data.get("note", "").lower()
        
        # Determine programmer type
        if "stm8" in note:
            programmer_type = "STM8"
        elif "pic" in note:
            programmer_type = "PIC"
        else:
            programmer_type = "Generic"
        
        # Add default programmer
        config["programmers"]["default"] = {
            "type": programmer_type,
            "path": "",
            "boards": ["main"]
        }
        
        # Add default hex file
        config["hex_files"]["main"] = ""
        
        # Add default sequence
        config["programming_sequence"].append({
            "board": "main",
            "pre_program_commands": [],
            "post_program_commands": []
        })
        
        return config
    
    @staticmethod
    def save_programming_config(file_data: Dict[str, Any], prog_config: Dict[str, Any]) -> Dict[str, Any]:
        """Save programming configuration back into SMT testing data"""
        updated_data = copy.deepcopy(file_data)
        
        if "smt_testing" not in updated_data:
            updated_data["smt_testing"] = {}
        
        # Convert back to simple format
        updated_data["smt_testing"]["programming"] = {
            "enabled": prog_config.get("enabled", False),
            "note": prog_config.get("description", "Programming configuration")
        }
        
        return updated_data
