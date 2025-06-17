#!/usr/bin/env python3
"""
SKU Configuration Migration Script
Migrates individual SKU JSON files to unified configuration format
Compatible with Diode Dynamics Tester V5 GUI components

Author: Quality Engineering Team
Date: 2024
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SKUConfigurationMigrator:
    """Professional SKU configuration migration tool"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.config_dir = self.project_root / "config"
        self.skus_dir = self.config_dir / "skus"
        self.backup_dir = self.config_dir / "backups" / f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Output files
        self.output_skus_file = self.config_dir / "skus.json"
        self.output_programming_file = self.config_dir / "programming_config.json"
        
        # Migration statistics
        self.stats = {
            "total_skus": 0,
            "migrated": 0,
            "failed": 0,
            "warnings": []
        }
    
    def create_backup(self) -> bool:
        """Create backup of existing configuration files"""
        try:
            logger.info(f"Creating backup in {self.backup_dir}")
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Backup existing skus directory
            if self.skus_dir.exists():
                backup_skus_dir = self.backup_dir / "skus"
                shutil.copytree(self.skus_dir, backup_skus_dir)
                logger.info(f"Backed up SKUs directory to {backup_skus_dir}")
            
            # Backup existing unified files if they exist
            for file_path in [self.output_skus_file, self.output_programming_file]:
                if file_path.exists():
                    backup_path = self.backup_dir / file_path.name
                    shutil.copy2(file_path, backup_path)
                    logger.info(f"Backed up {file_path.name} to {backup_path}")
            
            return True
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False
    
    def convert_sku_format(self, old_sku: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """Convert old SKU format to new format and extract programming config"""
        new_sku = {
            "sku": old_sku.get("sku", "UNKNOWN"),
            "description": old_sku.get("description", ""),
            "pod_type_ref": old_sku.get("pod_type", "C1"),
            "power_level_ref": old_sku.get("power_level", "Sport"),
            "available_modes": old_sku.get("available_modes", [])
        }
        
        programming_config = None
        
        # Convert offroad testing parameters
        if "offroad_testing" in old_sku:
            new_sku["available_modes"].append("Offroad")
            offroad_params = self._convert_offroad_params(old_sku["offroad_testing"])
            new_sku["offroad_params"] = offroad_params
            
            # Extract backlight configuration
            backlight_config = self._extract_backlight_config(old_sku["offroad_testing"])
            if backlight_config:
                new_sku["backlight_config"] = backlight_config
        
        # Convert SMT testing parameters
        if "smt_testing" in old_sku:
            new_sku["available_modes"].append("SMT")
            smt_params = self._convert_smt_params(old_sku["smt_testing"])
            new_sku["smt_params"] = smt_params
            
            # Extract programming configuration
            prog_data = old_sku["smt_testing"].get("programming", {})
            if prog_data.get("enabled", False):
                programming_config = self._create_programming_config(
                    old_sku["sku"], 
                    prog_data,
                    old_sku["smt_testing"]
                )
        
        # Convert weight testing parameters
        if "weight_testing" in old_sku:
            new_sku["available_modes"].append("WeightChecking")
            weight_params = self._convert_weight_params(old_sku["weight_testing"])
            new_sku["weightchecking_params"] = weight_params
        
        # Ensure unique modes
        new_sku["available_modes"] = list(set(new_sku["available_modes"]))
        
        return new_sku, programming_config
    
    def _convert_offroad_params(self, old_offroad: Dict[str, Any]) -> Dict[str, Any]:
        """Convert old offroad testing format to new format"""
        params = {}
        
        # Process test sequence to extract parameters
        test_sequence = old_offroad.get("test_sequence", [])
        
        for test in test_sequence:
            test_name = test.get("name", "")
            limits = test.get("limits", {})
            measurements = test.get("measurements", [])
            
            # Extract CURRENT parameters
            if "current" in measurements and "current_A" in limits:
                if "CURRENT" not in params:
                    params["CURRENT"] = {}
                
                current_limits = limits["current_A"]
                if "mainbeam" in test_name:
                    params["CURRENT"]["min_mainbeam_current_A"] = current_limits.get("min", 0.5)
                    params["CURRENT"]["max_mainbeam_current_A"] = current_limits.get("max", 1.0)
                elif "backlight" in test_name:
                    params["CURRENT"]["min_backlight_current_A"] = current_limits.get("min", 0.05)
                    params["CURRENT"]["max_backlight_current_A"] = current_limits.get("max", 0.15)
            
            # Extract LUX parameters
            if "lux" in measurements and "lux" in limits:
                if "LUX" not in params:
                    params["LUX"] = {}
                
                lux_limits = limits["lux"]
                if "mainbeam" in test_name:
                    params["LUX"]["min_mainbeam_lux"] = lux_limits.get("min", 1000)
                    params["LUX"]["max_mainbeam_lux"] = lux_limits.get("max", 2000)
                elif "backlight" in test_name:
                    params["LUX"]["min_backlight_lux"] = lux_limits.get("min", 100)
                    params["LUX"]["max_backlight_lux"] = lux_limits.get("max", 200)
            
            # Extract COLOR parameters
            if "color" in measurements and ("color_x" in limits or "color_y" in limits):
                if "COLOR" not in params:
                    params["COLOR"] = {}
                
                if "mainbeam" in test_name:
                    if "color_x" in limits:
                        params["COLOR"]["center_x_main"] = limits["color_x"].get("center", 0.45)
                        params["COLOR"]["radius_x_main"] = limits["color_x"].get("tolerance", 0.015)
                    if "color_y" in limits:
                        params["COLOR"]["center_y_main"] = limits["color_y"].get("center", 0.41)
                        params["COLOR"]["radius_y_main"] = limits["color_y"].get("tolerance", 0.015)
                    params["COLOR"]["angle_deg_main"] = 0
        
        # Add default PRESSURE parameters (will be overridden by global)
        params["PRESSURE"] = {
            "min_initial_psi": 14.0,
            "max_initial_psi": 16.0,
            "max_delta_psi": 0.5
        }
        
        return params
    
    def _extract_backlight_config(self, old_offroad: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract backlight configuration from old format"""
        test_sequence = old_offroad.get("test_sequence", [])
        
        backlight_tests = [t for t in test_sequence if "backlight" in t.get("name", "").lower()]
        if not backlight_tests:
            return None
        
        # Determine backlight type
        if len(backlight_tests) > 1:
            backlight_type = "dual"
            relay_pins = []
            for test in backlight_tests:
                relay = test.get("relay", "")
                if "1" in relay or "left" in relay:
                    relay_pins.append(3)
                elif "2" in relay or "right" in relay:
                    relay_pins.append(4)
        else:
            backlight_type = "single"
            relay_pins = [3]
        
        return {
            "type": backlight_type,
            "relay_pins": relay_pins,
            "test_duration_ms": backlight_tests[0].get("duration_ms", 500)
        }
    
    def _convert_smt_params(self, old_smt: Dict[str, Any]) -> Dict[str, Any]:
        """Convert old SMT testing format to new format"""
        params = {}
        
        # Extract power sequence parameters
        test_sequence = old_smt.get("test_sequence", [])
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
        
        # Preserve panel layout information in a comment field
        if "panel_layout" in old_smt:
            params["panel_layout"] = old_smt["panel_layout"]
        
        return params
    
    def _convert_weight_params(self, old_weight: Dict[str, Any]) -> Dict[str, Any]:
        """Convert old weight testing format to new format"""
        params = {}
        
        limits = old_weight.get("limits", {})
        weight_limits = limits.get("weight_g", {})
        
        params["WEIGHT"] = {
            "min_weight_g": weight_limits.get("min", 100.0),
            "max_weight_g": weight_limits.get("max", 200.0),
            "tare_g": old_weight.get("tare_g", 0.5)
        }
        
        return params
    
    def _create_programming_config(self, sku: str, prog_data: Dict[str, Any], 
                                   smt_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create programming configuration from SMT data"""
        config = {
            "enabled": True,
            "description": prog_data.get("note", "Programming configuration"),
            "programmers": {},
            "hex_files": {},
            "programming_sequence": []
        }
        
        # Infer programmer type from note
        note = prog_data.get("note", "").lower()
        if "stm8" in note:
            programmer_type = "STM8"
            programmer_name = "STM8_Programmer"
        elif "pic" in note:
            programmer_type = "PIC"
            programmer_name = "PIC_Programmer"
        else:
            programmer_type = "STM8"
            programmer_name = "Generic_Programmer"
        
        # Extract board information
        boards = []
        if "main controller" in note:
            boards.append("main_controller")
        if "led driver" in note:
            boards.extend(["led_driver_1", "led_driver_2"])
        if "thermal controller" in note:
            boards.append("thermal_controller")
        
        if not boards:
            boards = ["main_board"]
        
        config["programmers"][programmer_name] = {
            "type": programmer_type,
            "path": f"C:/tools/{programmer_name.lower()}.exe",
            "boards": boards
        }
        
        # Create hex file entries
        for board in boards:
            config["hex_files"][board] = f"firmware/{board}.hex"
        
        # Create programming sequence
        for board in boards:
            config["programming_sequence"].append({
                "board": board,
                "pre_program_commands": ["power_on", "reset_hold"],
                "post_program_commands": ["reset_release", "verify_firmware"]
            })
        
        return config
    
    def migrate_all_skus(self) -> bool:
        """Migrate all SKU files to new format"""
        try:
            if not self.create_backup():
                logger.error("Backup failed, aborting migration")
                return False
            
            sku_definitions = []
            programming_configs = {}
            global_parameters = self._create_global_parameters()
            
            # Process each SKU file
            sku_files = list(self.skus_dir.glob("*.json"))
            self.stats["total_skus"] = len(sku_files)
            
            logger.info(f"Found {len(sku_files)} SKU files to migrate")
            
            for sku_file in sku_files:
                try:
                    logger.info(f"Processing {sku_file.name}")
                    
                    # Load old SKU data
                    with open(sku_file, 'r', encoding='utf-8') as f:
                        old_sku = json.load(f)
                    
                    # Convert to new format
                    new_sku, prog_config = self.convert_sku_format(old_sku)
                    sku_definitions.append(new_sku)
                    
                    # Add programming config if exists
                    if prog_config:
                        programming_configs[new_sku["sku"]] = prog_config
                    
                    self.stats["migrated"] += 1
                    logger.info(f"Successfully migrated {new_sku['sku']}")
                    
                except Exception as e:
                    self.stats["failed"] += 1
                    self.stats["warnings"].append(f"Failed to migrate {sku_file.name}: {e}")
                    logger.error(f"Failed to migrate {sku_file.name}: {e}")
            
            # Create unified configuration
            unified_config = {
                "version": "2.0",
                "created": datetime.now().isoformat(),
                "global_parameters": global_parameters,
                "pod_type_definitions": self._create_pod_type_definitions(),
                "power_level_definitions": self._create_power_level_definitions(),
                "sku_definitions": sku_definitions
            }
            
            # Write output files
            logger.info("Writing unified configuration files")
            
            with open(self.output_skus_file, 'w', encoding='utf-8') as f:
                json.dump(unified_config, f, indent=2)
            logger.info(f"Created {self.output_skus_file}")
            
            with open(self.output_programming_file, 'w', encoding='utf-8') as f:
                json.dump(programming_configs, f, indent=2)
            logger.info(f"Created {self.output_programming_file}")
            
            # Print migration summary
            self._print_summary()
            
            return self.stats["failed"] == 0
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
    
    def _create_global_parameters(self) -> Dict[str, Any]:
        """Create global parameters section"""
        return {
            "PRESSURE": {
                "min_initial_psi": 14.0,
                "max_initial_psi": 16.0,
                "max_delta_psi": 0.5,
                "test_duration_ms": 3000,
                "stabilization_ms": 500
            },
            "test_timeouts": {
                "offroad_ms": 30000,
                "smt_ms": 20000,
                "weight_ms": 10000
            },
            "relay_configuration": {
                "total_relays": 8,
                "default_on_duration_ms": 500,
                "inter_relay_delay_ms": 100
            }
        }
    
    def _create_pod_type_definitions(self) -> Dict[str, Any]:
        """Create pod type definitions"""
        return {
            "C1": {
                "name": "C1 Pod",
                "connector_type": "DT",
                "pin_count": 2
            },
            "C2": {
                "name": "C2 Pod", 
                "connector_type": "DT",
                "pin_count": 3
            },
            "SS3": {
                "name": "SS3 Pod",
                "connector_type": "DT",
                "pin_count": 3
            }
        }
    
    def _create_power_level_definitions(self) -> Dict[str, Any]:
        """Create power level definitions"""
        return {
            "Sport": {
                "name": "Sport",
                "relative_power": 0.6
            },
            "Pro": {
                "name": "Pro",
                "relative_power": 0.8
            },
            "Max": {
                "name": "Max",
                "relative_power": 1.0
            }
        }
    
    def _print_summary(self):
        """Print migration summary"""
        print("\n" + "="*60)
        print("SKU CONFIGURATION MIGRATION SUMMARY")
        print("="*60)
        print(f"Total SKUs found:     {self.stats['total_skus']}")
        print(f"Successfully migrated: {self.stats['migrated']}")
        print(f"Failed migrations:     {self.stats['failed']}")
        
        if self.stats['warnings']:
            print("\nWarnings:")
            for warning in self.stats['warnings']:
                print(f"  - {warning}")
        
        print("\nOutput files created:")
        print(f"  - {self.output_skus_file}")
        print(f"  - {self.output_programming_file}")
        print(f"\nBackup location: {self.backup_dir}")
        print("="*60)


def main():
    """Main entry point for migration script"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Migrate SKU configurations to new unified format"
    )
    parser.add_argument(
        "--project-root",
        type=str,
        default=".",
        help="Path to project root directory (default: current directory)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform dry run without writing files"
    )
    
    args = parser.parse_args()
    
    # Validate project root
    project_root = Path(args.project_root).resolve()
    if not (project_root / "config" / "skus").exists():
        logger.error(f"SKUs directory not found at {project_root / 'config' / 'skus'}")
        logger.error("Please specify correct project root with --project-root")
        return 1
    
    # Run migration
    migrator = SKUConfigurationMigrator(project_root)
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No files will be written")
        # TODO: Implement dry run logic
        return 0
    
    success = migrator.migrate_all_skus()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
