#!/usr/bin/env python3
"""
Test script for SKU Format Adapter
Verifies the adapter correctly converts between file and GUI formats
"""

import json
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.gui.components.config.format_adapter import SKUFormatAdapter


def test_adapter():
    """Test the format adapter with a sample SKU"""
    
    # Sample SKU in your existing format
    sample_sku = {
        "sku": "TEST001",
        "description": "Test SKU for adapter verification",
        "pod_type": "SS3",
        "power_level": "Sport",
        "available_modes": ["SMT", "Offroad"],
        "offroad_testing": {
            "test_sequence": [
                {
                    "name": "mainbeam",
                    "relay": "main",
                    "duration_ms": 500,
                    "measurements": ["current", "voltage", "lux"],
                    "limits": {
                        "current_A": {"min": 0.95, "max": 1.2},
                        "lux": {"min": 4500, "max": 5500}
                    }
                },
                {
                    "name": "backlight_left",
                    "relay": "backlight_1",
                    "duration_ms": 500,
                    "measurements": ["current"],
                    "limits": {
                        "current_A": {"min": 0.08, "max": 0.15}
                    }
                }
            ]
        },
        "smt_testing": {
            "panel_layout": {
                "rows": 2,
                "columns": 2
            },
            "test_sequence": [
                {
                    "function": "mainbeam",
                    "limits": {
                        "current_A": {"min": 0.95, "max": 1.2}
                    }
                }
            ],
            "programming": {
                "enabled": True,
                "note": "STM8 programmer required"
            }
        }
    }
    
    print("Testing SKU Format Adapter")
    print("=" * 60)
    
    # Create adapter
    adapter = SKUFormatAdapter()
    
    # Test 1: Convert to GUI format
    print("\n1. Converting file format to GUI format...")
    gui_data = adapter.from_file_to_gui(sample_sku)
    
    print("\nGUI sees these fields:")
    print(f"  - pod_type_ref: {gui_data.get('pod_type_ref')} (was pod_type)")
    print(f"  - power_level_ref: {gui_data.get('power_level_ref')} (was power_level)")
    print(f"  - offroad_params: {'Present' if 'offroad_params' in gui_data else 'Missing'}")
    print(f"  - smt_params: {'Present' if 'smt_params' in gui_data else 'Missing'}")
    print(f"  - backlight_config: {gui_data.get('backlight_config', {})}")
    
    # Test 2: Check parameter conversion
    print("\n2. Checking parameter conversion...")
    if "offroad_params" in gui_data:
        offroad = gui_data["offroad_params"]
        if "CURRENT" in offroad:
            print(f"  - Mainbeam current: {offroad['CURRENT'].get('min_mainbeam_current_A')} - {offroad['CURRENT'].get('max_mainbeam_current_A')} A")
        if "LUX" in offroad:
            print(f"  - Mainbeam lux: {offroad['LUX'].get('min_mainbeam_lux')} - {offroad['LUX'].get('max_mainbeam_lux')}")
    
    # Test 3: Convert back to file format
    print("\n3. Converting GUI format back to file format...")
    file_data_back = adapter.from_gui_to_file(gui_data)
    
    print("\nFile will have these fields:")
    print(f"  - pod_type: {file_data_back.get('pod_type')} (was pod_type_ref)")
    print(f"  - power_level: {file_data_back.get('power_level')} (was power_level_ref)")
    print(f"  - offroad_testing: {'Present' if 'offroad_testing' in file_data_back else 'Missing'}")
    print(f"  - smt_testing: {'Present' if 'smt_testing' in file_data_back else 'Missing'}")
    
    # Test 4: Verify round-trip conversion
    print("\n4. Verifying round-trip conversion...")
    
    # Check key fields match
    issues = []
    if sample_sku.get("pod_type") != file_data_back.get("pod_type"):
        issues.append("pod_type mismatch")
    if sample_sku.get("power_level") != file_data_back.get("power_level"):
        issues.append("power_level mismatch")
    
    # Check test structures exist
    if "offroad_testing" in sample_sku and "offroad_testing" not in file_data_back:
        issues.append("offroad_testing missing")
    if "smt_testing" in sample_sku and "smt_testing" not in file_data_back:
        issues.append("smt_testing missing")
    
    if issues:
        print(f"  ❌ Issues found: {', '.join(issues)}")
    else:
        print("  ✅ Round-trip conversion successful!")
    
    # Test 5: Test with actual SKU file
    print("\n5. Testing with actual SKU file...")
    sku_path = Path("config/skus/SL0224P01-ABL.json")
    
    if sku_path.exists():
        with open(sku_path, 'r') as f:
            real_sku = json.load(f)
        
        gui_real = adapter.from_file_to_gui(real_sku)
        file_real_back = adapter.from_gui_to_file(gui_real)
        
        print(f"  - Loaded: {real_sku['sku']}")
        print(f"  - Description: {real_sku.get('description', '')}")
        print(f"  - Conversion successful: {'✅' if file_real_back.get('sku') == real_sku['sku'] else '❌'}")
    else:
        print(f"  - SKU file not found: {sku_path}")
    
    print("\n" + "=" * 60)
    print("Test complete!")


if __name__ == "__main__":
    test_adapter()
