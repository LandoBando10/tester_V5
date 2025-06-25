#!/usr/bin/env python3
"""
Enhanced SMT Programming Setup Utility

This utility helps set up and test the SMT programming system for Diode Dynamics.
It provides functions to:
- Test programmer connections
- Validate programming configurations
- Test Arduino communication
- Run programming sequences
- Generate diagnostic reports
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import error handling
ProgrammerController = None
SMTArduinoController = None
SerialManager = None

try:
    from src.core.smt_test import ProgrammerController, SMTArduinoController
except ImportError as e:
    print(f"Warning: Could not import some modules: {e}")
    print("Some features may not be available.")


class SMTSetupUtility:
    """Enhanced utility for setting up and testing SMT programming system"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.setup_logging()

        # File paths
        self.config_dir = Path("config")
        self.firmware_dir = Path("firmware")
        self.test_results_dir = Path("test_results")
        self.programming_config_file = self.config_dir / "programming_config.json"

        # Create directories if they don't exist
        self.config_dir.mkdir(exist_ok=True)
        self.firmware_dir.mkdir(exist_ok=True)
        self.test_results_dir.mkdir(exist_ok=True)

        # Status tracking
        self.arduino_status = {
            'connected': False,
            'smt_initialized': False,
            'last_test': None
        }
        self.programmer_status = {}

    def setup_logging(self):
        """Setup logging for the utility"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('smt_setup.log')
            ]
        )

    def test_smt_arduino_connection(self, port: str) -> bool:
        """Test connection to dedicated SMT Arduino controller"""
        print(f"\n{'=' * 60}")
        print("TESTING SMT ARDUINO CONNECTION")
        print(f"{'=' * 60}")

        # Check if SMTArduinoController is available
        if SMTArduinoController is None:
            print("❌ SMTArduinoController module not available")
            print("   Please ensure testing.smt_test module is properly installed")
            return False

        smt_arduino = None
        try:
            smt_arduino = SMTArduinoController(baud_rate=115200)

            print(f"Connecting to SMT Arduino on {port}...")
            if not smt_arduino.connect(port):
                print(f"❌ Failed to connect to {port}")
                self.arduino_status['connected'] = False
                return False

            print("✅ Connected successfully")
            self.arduino_status['connected'] = True

            # Test SMT-specific identification
            print("Testing SMT controller identification...")
            response = smt_arduino.send_command("ID")
            if response and "SMT_CONTROLLER" in response.upper():
                print(f"✅ SMT Arduino identified: {response}")
            else:
                print(f"⚠️  Response: {response} (expecting SMT controller)")

            # Test SMT system initialization
            print("Testing SMT system initialization...")
            if smt_arduino.initialize_smt_system():
                print("✅ SMT system initialization successful")
                self.arduino_status['smt_initialized'] = True
            else:
                print("❌ SMT system initialization failed")
                self.arduino_status['smt_initialized'] = False

            # Test board selection functionality
            print("Testing board selection functionality...")
            test_boards = ["MAIN", "LED1", "LED2", "THERMAL"]
            board_test_passed = True

            for board in test_boards:
                print(f"  Testing board: {board}")
                if smt_arduino.select_board(board):
                    print(f"    ✅ {board} selection successful")
                    if smt_arduino.deselect_board(board):
                        print(f"    ✅ {board} deselection successful")
                    else:
                        print(f"    ❌ {board} deselection failed")
                        board_test_passed = False
                else:
                    print(f"    ❌ {board} selection failed")
                    board_test_passed = False

            # Test power control
            print("Testing power control functionality...")
            power_types = ["PROG_3V3", "PROG_5V", "TEST_12V", "OFF"]
            power_test_passed = True

            for power_type in power_types:
                print(f"  Testing power: {power_type}")
                if smt_arduino.set_power(power_type):
                    print(f"    ✅ {power_type} setting successful")
                else:
                    print(f"    ❌ {power_type} setting failed")
                    power_test_passed = False

            # Test programmer interface control
            print("Testing programmer interface control...")
            programmer_test_passed = True

            for prog_type in ["STM8", "PIC"]:
                print(f"  Testing {prog_type} programmer interface...")
                if smt_arduino.enable_programmer(prog_type):
                    print(f"    ✅ {prog_type} enable successful")
                    if smt_arduino.disable_programmer():
                        print(f"    ✅ {prog_type} disable successful")
                    else:
                        print(f"    ❌ {prog_type} disable failed")
                        programmer_test_passed = False
                else:
                    print(f"    ❌ {prog_type} enable failed")
                    programmer_test_passed = False

            # Test output control
            print("Testing output control functionality...")
            output_test_passed = True

            for output, control_func in [("mainbeam", smt_arduino.set_mainbeam), 
                                       ("backlight", smt_arduino.set_backlight)]:
                print(f"  Testing {output} control...")
                if control_func(True):
                    print(f"    ✅ {output} ON successful")
                    if control_func(False):
                        print(f"    ✅ {output} OFF successful")
                    else:
                        print(f"    ❌ {output} OFF failed")
                        output_test_passed = False
                else:
                    print(f"    ❌ {output} ON failed")
                    output_test_passed = False

            # Final cleanup
            print("Performing cleanup...")
            smt_arduino.deselect_all_boards()
            smt_arduino.set_power("OFF")
            smt_arduino.disable_programmer()
            smt_arduino.set_mainbeam(False)
            smt_arduino.set_backlight(False)

            # Overall assessment
            all_tests_passed = (board_test_passed and power_test_passed and 
                              programmer_test_passed and output_test_passed)

            if all_tests_passed:
                print("✅ All SMT Arduino tests passed successfully")
            else:
                print("⚠️  Some SMT Arduino tests failed")

            self.arduino_status['last_test'] = time.time()
            return all_tests_passed

        except Exception as e:
            print(f"❌ SMT Arduino connection test failed: {e}")
            self.arduino_status['connected'] = False
            return False
        finally:
            if smt_arduino is not None:
                try:
                    smt_arduino.disconnect()
                except:
                    pass

    def test_programmer_connections(self) -> Dict[str, bool]:
        """Test connections to all configured programmers"""
        print(f"\n{'=' * 60}")
        print("TESTING PROGRAMMER CONNECTIONS")
        print(f"{'=' * 60}")

        results = {}

        # Check if ProgrammerController is available
        if ProgrammerController is None:
            print("❌ ProgrammerController module not available")
            print("   Please ensure testing.smt_test module is properly installed")
            return results

        if not self.programming_config_file.exists():
            print("❌ No programming configuration file found")
            print(f"   Expected: {self.programming_config_file}")
            return results

        try:
            with open(self.programming_config_file, 'r') as f:
                config = json.load(f)

            # Test each SKU's programmers
            for sku, sku_config in config.items():
                if sku.startswith('_') or sku == 'default':
                    continue

                print(f"\nTesting programmers for SKU: {sku}")

                if not sku_config.get('enabled', False):
                    print(f"  ⚠️  Programming disabled for {sku}")
                    continue

                programmers = sku_config.get('programmers', {})

                for prog_name, prog_config in programmers.items():
                    prog_type = prog_config.get('type', 'UNKNOWN')
                    prog_path = prog_config.get('path', '')

                    print(f"  Testing {prog_name} ({prog_type})...")

                    try:
                        programmer = ProgrammerController(prog_type, prog_path)
                        connected, message = programmer.verify_connection()

                        if connected:
                            print(f"    ✅ {message}")
                            results[f"{sku}_{prog_name}"] = True
                            self.programmer_status[f"{sku}_{prog_name}"] = True
                        else:
                            print(f"    ❌ {message}")
                            results[f"{sku}_{prog_name}"] = False
                            self.programmer_status[f"{sku}_{prog_name}"] = False

                    except Exception as e:
                        print(f"    ❌ Error testing {prog_name}: {e}")
                        results[f"{sku}_{prog_name}"] = False
                        self.programmer_status[f"{sku}_{prog_name}"] = False

            return results

        except json.JSONDecodeError as e:
            print(f"❌ Error parsing JSON configuration: {e}")
            return results
        except Exception as e:
            print(f"❌ Error testing programmer connections: {e}")
            return results

    def validate_programming_config(self) -> bool:
        """Validate the programming configuration file"""
        print(f"\n{'=' * 60}")
        print("VALIDATING PROGRAMMING CONFIGURATION")
        print(f"{'=' * 60}")

        if not self.programming_config_file.exists():
            print("❌ Programming configuration file not found")
            print(f"   Expected: {self.programming_config_file}")
            print("   Run create_enhanced_config() to create a template")
            return False

        try:
            with open(self.programming_config_file, 'r') as f:
                config = json.load(f)

            print("✅ Configuration file loaded successfully")

            validation_passed = True

            # Validate each SKU configuration
            for sku, sku_config in config.items():
                if sku.startswith('_'):  # Skip documentation entries
                    continue

                print(f"\nValidating SKU: {sku}")

                # Check required fields
                required_fields = ['enabled', 'programmers', 'hex_files']
                for field in required_fields:
                    if field not in sku_config:
                        print(f"  ❌ Missing required field: {field}")
                        validation_passed = False
                    else:
                        print(f"  ✅ Field present: {field}")

                if not sku_config.get('enabled', False):
                    print(f"  ⚠️  Programming disabled for {sku}")
                    continue

                # Validate programmers
                programmers = sku_config.get('programmers', {})
                for prog_name, prog_config in programmers.items():
                    print(f"  Validating programmer: {prog_name}")

                    # Check programmer type
                    prog_type = prog_config.get('type', '')
                    if prog_type not in ['STM8', 'PIC']:
                        print(f"    ❌ Invalid programmer type: {prog_type}")
                        validation_passed = False
                    else:
                        print(f"    ✅ Programmer type: {prog_type}")

                    # Check programmer path
                    prog_path = Path(prog_config.get('path', ''))
                    if not prog_path.exists():
                        print(f"    ❌ Programmer not found: {prog_path}")
                        validation_passed = False
                    else:
                        print(f"    ✅ Programmer found: {prog_path}")

                # Validate hex files
                hex_files = sku_config.get('hex_files', {})
                for board_name, hex_file in hex_files.items():
                    hex_path = Path(hex_file)
                    if not hex_path.exists():
                        print(f"  ❌ Hex file not found: {hex_file}")
                        validation_passed = False
                    else:
                        print(f"  ✅ Hex file found: {hex_file}")

            if validation_passed:
                print("\n✅ Programming configuration validation passed")
            else:
                print("\n❌ Programming configuration validation failed")

            return validation_passed

        except json.JSONDecodeError as e:
            print(f"❌ Error parsing JSON configuration: {e}")
            return False
        except Exception as e:
            print(f"❌ Error validating configuration: {e}")
            return False

    def create_enhanced_config(self):
        """Create an enhanced default programming configuration file"""
        print(f"\n{'=' * 60}")
        print("CREATING ENHANCED PROGRAMMING CONFIGURATION")
        print(f"{'=' * 60}")

        # Create the enhanced configuration
        enhanced_config = {
            "DD5000": {
                "enabled": True,
                "description": "Product Alpha - C1 Pro Variant - Single board programming",
                "product_line": "C1 Pro",
                "programmers": {
                    "stm8_main": {
                        "type": "STM8",
                        "path": "C:/Program Files/STMicroelectronics/st_toolset/stvp/STVP_CmdLine.exe",
                        "boards": ["main_controller"],
                        "timeout": 30,
                        "retry_count": 3
                    }
                },
                "hex_files": {
                    "main_controller": "firmware/DD5000/main_v1.2.hex"
                },
                "test_points": {
                    "voltage_3v3": {"min": 3.2, "max": 3.4},
                    "voltage_5v": {"min": 4.9, "max": 5.1}
                }
            },
            "DD5001": {
                "enabled": True,
                "description": "Product Beta - SS3 Max High Output - Multi-board programming",
                "product_line": "SS3 Max",
                "programmers": {
                    "stm8_main": {
                        "type": "STM8",
                        "path": "C:/Program Files/STMicroelectronics/st_toolset/stvp/STVP_CmdLine.exe",
                        "boards": ["main_controller", "led_driver_1", "led_driver_2"],
                        "timeout": 30,
                        "retry_count": 3
                    },
                    "pic_control": {
                        "type": "PIC",
                        "path": "C:/Program Files/Microchip/MPLABX/v5.50/mplab_platform/bin/pk3cmd.exe",
                        "boards": ["thermal_controller"],
                        "timeout": 45,
                        "retry_count": 2
                    }
                },
                "hex_files": {
                    "main_controller": "firmware/DD5001/main_v2.1.hex",
                    "led_driver_1": "firmware/DD5001/led_driver_v1.5.hex",
                    "led_driver_2": "firmware/DD5001/led_driver_v1.5.hex",
                    "thermal_controller": "firmware/DD5001/thermal_v1.0.hex"
                },
                "test_points": {
                    "voltage_3v3": {"min": 3.2, "max": 3.4},
                    "voltage_5v": {"min": 4.9, "max": 5.1},
                    "voltage_12v": {"min": 11.5, "max": 12.5}
                }
            },
            "_metadata": {
                "version": "2.0",
                "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "description": "Enhanced programming configuration for SMT testing"
            },
            "_notes": {
                "programmer_types": ["STM8", "PIC"],
                "required_fields": ["enabled", "programmers", "hex_files"],
                "optional_fields": ["description", "product_line", "test_points"],
                "timeout_units": "seconds"
            }
        }

        try:
            with open(self.programming_config_file, 'w') as f:
                json.dump(enhanced_config, f, indent=2, ensure_ascii=False)

            print(f"✅ Created enhanced configuration: {self.programming_config_file}")

            # Create firmware directory structure
            for sku in ["DD5000", "DD5001"]:
                sku_firmware_dir = self.firmware_dir / sku
                sku_firmware_dir.mkdir(exist_ok=True)
                print(f"✅ Created firmware directory: {sku_firmware_dir}")

            # Create placeholder hex files for testing
            for sku, sku_config in enhanced_config.items():
                if sku.startswith('_'):
                    continue
                hex_files = sku_config.get('hex_files', {})
                for board_name, hex_file in hex_files.items():
                    hex_path = Path(hex_file)
                    if not hex_path.exists():
                        hex_path.parent.mkdir(parents=True, exist_ok=True)
                        hex_path.write_text(f"# Placeholder hex file for {board_name}\n")
                        print(f"✅ Created placeholder: {hex_path}")

            print("\n📝 Next steps:")
            print("1. Update programmer paths in the configuration file")
            print("2. Replace placeholder hex files with actual firmware")
            print("3. Run validate_programming_config() to verify setup")

        except Exception as e:
            print(f"❌ Error creating configuration: {e}")

    def test_programming_sequence(self, sku: str, arduino_port: str, dry_run: bool = True) -> bool:
        """Test a complete programming sequence"""
        print(f"\n{'=' * 60}")
        print(f"TESTING PROGRAMMING SEQUENCE - SKU: {sku}")
        print(f"{'=' * 60}")

        if dry_run:
            print("🔄 DRY RUN MODE - No actual programming will occur")
        else:
            print("⚠️  LIVE MODE - Actual programming will occur!")
            response = input("Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("Cancelled by user")
                return False

        try:
            # Load configuration
            if not self.programming_config_file.exists():
                print("❌ Programming configuration not found")
                return False

            with open(self.programming_config_file, 'r') as f:
                config = json.load(f)

            sku_config = config.get(sku)
            if not sku_config:
                print(f"❌ No configuration found for SKU: {sku}")
                return False

            if not sku_config.get('enabled', False):
                print(f"❌ Programming disabled for SKU: {sku}")
                return False

            if dry_run:
                print("🔄 Creating test instance (dry run)...")
                # In dry run mode, we'll just validate the configuration
                programmers = sku_config.get('programmers', {})
                hex_files = sku_config.get('hex_files', {})

                print(f"✅ Found {len(programmers)} programmers")
                print(f"✅ Found {len(hex_files)} hex files")

                test_passed = True

                for prog_name, prog_config in programmers.items():
                    boards = prog_config.get('boards', [])
                    print(f"  Programmer {prog_name}: {len(boards)} boards")

                    for board in boards:
                        hex_file = hex_files.get(board)
                        if hex_file:
                            hex_path = Path(hex_file)
                            if hex_path.exists():
                                print(f"    ✅ {board}: {hex_file}")
                            else:
                                print(f"    ❌ {board}: {hex_file} (not found)")
                                test_passed = False
                        else:
                            print(f"    ❌ {board}: No hex file specified")
                            test_passed = False

                if test_passed:
                    print("✅ Dry run completed successfully")
                else:
                    print("❌ Dry run found configuration issues")
                
                return test_passed
            else:
                print("🔄 Live programming mode not implemented in utility")
                print("   Use the main application for actual programming")
                return True

        except json.JSONDecodeError as e:
            print(f"❌ Error parsing JSON configuration: {e}")
            return False
        except Exception as e:
            print(f"❌ Programming sequence test failed: {e}")
            return False

    def run_comprehensive_diagnostics(self, arduino_port: str) -> Dict[str, bool]:
        """Run comprehensive diagnostics with integration tests"""
        print(f"\n{'=' * 80}")
        print("COMPREHENSIVE SMT PROGRAMMING SYSTEM DIAGNOSTICS")
        print(f"{'=' * 80}")

        results = {}
        score = 0
        total = 0

        # Test 1: SMT Arduino connection
        print("\n[1/5] Testing SMT Arduino connection...")
        results['smt_arduino'] = self.test_smt_arduino_connection(arduino_port)
        total += 1
        if results['smt_arduino']:
            score += 1

        # Test 2: Validate configuration
        print("\n[2/5] Validating programming configuration...")
        results['config'] = self.validate_programming_config()
        total += 1
        if results['config']:
            score += 1

        # Test 3: Test programmer connections
        if results['config']:
            print("\n[3/5] Testing programmer connections...")
            programmer_results = self.test_programmer_connections()
            results['programmers'] = len(programmer_results) > 0 and all(programmer_results.values())
            total += 1
            if results['programmers']:
                score += 1
        else:
            print("\n[3/5] Skipping programmer tests (configuration invalid)")
            results['programmers'] = False
            total += 1

        # Test 4: Verify firmware files
        print("\n[4/5] Verifying firmware files...")
        results['firmware'] = self._verify_firmware_files()
        total += 1
        if results['firmware']:
            score += 1

        # Test 5: Integration test
        if results['smt_arduino'] and results['config']:
            print("\n[5/5] Running integration test...")
            results['integration'] = self._run_integration_test(arduino_port)
            total += 1
            if results['integration']:
                score += 1
        else:
            print("\n[5/5] Skipping integration test (prerequisites not met)")
            results['integration'] = False
            total += 1

        # Generate report
        self._generate_diagnostic_report(results, score, total)

        return results

    def _verify_firmware_files(self) -> bool:
        """Verify all firmware files exist"""
        print("  Checking firmware files...")
        
        if not self.programming_config_file.exists():
            print("  ❌ No configuration file to check")
            return False

        try:
            with open(self.programming_config_file, 'r') as f:
                config = json.load(f)

            all_files_exist = True

            for sku, sku_config in config.items():
                if sku.startswith('_'):
                    continue

                if not sku_config.get('enabled', False):
                    continue

                hex_files = sku_config.get('hex_files', {})
                for board_name, hex_file in hex_files.items():
                    hex_path = Path(hex_file)
                    if hex_path.exists():
                        print(f"    ✅ {hex_file}")
                    else:
                        print(f"    ❌ {hex_file} (missing)")
                        all_files_exist = False

            return all_files_exist

        except Exception as e:
            print(f"  ❌ Error checking firmware files: {e}")
            return False

    def _run_integration_test(self, arduino_port: str) -> bool:
        """Run basic integration test"""
        print("  Running SMT system integration test...")
        
        if SMTArduinoController is None:
            print("  ❌ SMTArduinoController not available")
            return False

        smt_arduino = None
        try:
            smt_arduino = SMTArduinoController(baud_rate=115200)
            
            if not smt_arduino.connect(arduino_port):
                print("  ❌ Failed to connect for integration test")
                return False

            # Initialize system
            if not smt_arduino.initialize_smt_system():
                print("  ❌ Failed to initialize SMT system")
                return False

            # Test basic sequence
            print("  Testing basic programming sequence...")
            
            # Select board
            if not smt_arduino.select_board("MAIN"):
                print("  ❌ Failed to select MAIN board")
                return False

            # Set power
            if not smt_arduino.set_power("PROG_3V3"):
                print("  ❌ Failed to set programming power")
                return False

            # Enable programmer
            if not smt_arduino.enable_programmer("STM8"):
                print("  ❌ Failed to enable STM8 programmer")
                return False

            # Cleanup
            smt_arduino.disable_programmer()
            smt_arduino.set_power("OFF")
            smt_arduino.deselect_all_boards()

            print("  ✅ Integration test completed successfully")
            return True

        except Exception as e:
            print(f"  ❌ Integration test error: {e}")
            return False
        finally:
            if smt_arduino is not None:
                try:
                    smt_arduino.disconnect()
                except:
                    pass

    def _generate_diagnostic_report(self, results: Dict[str, bool], score: int, total: int):
        """Generate comprehensive diagnostic report"""
        print(f"\n{'=' * 80}")
        print("DIAGNOSTIC REPORT")
        print(f"{'=' * 80}")

        # Overall score
        percentage = (score / total) * 100 if total > 0 else 0
        print(f"Overall Score: {score}/{total} ({percentage:.1f}%)")

        if percentage >= 90:
            status = "🟢 EXCELLENT - System ready for production"
        elif percentage >= 70:
            status = "🟡 GOOD - Minor issues need attention"
        elif percentage >= 50:
            status = "🟠 FAIR - Several issues need resolution"
        else:
            status = "🔴 POOR - Major issues prevent operation"

        print(f"System Status: {status}")
        print()

        # Detailed results
        test_descriptions = {
            'smt_arduino': 'SMT Arduino Controller',
            'config': 'Programming Configuration',
            'programmers': 'Programmer Connections',
            'firmware': 'Firmware Files',
            'integration': 'System Integration'
        }

        print("Detailed Results:")
        for test_key, passed in results.items():
            status_icon = "✅" if passed else "❌"
            description = test_descriptions.get(test_key, test_key)
            print(f"  {status_icon} {description}: {'PASS' if passed else 'FAIL'}")

        # Recommendations
        print("\nRecommendations:")
        if not results.get('smt_arduino', False):
            print("  🔧 Check SMT Arduino connection and firmware")
        if not results.get('config', False):
            print("  🔧 Fix programming configuration issues")
        if not results.get('programmers', False):
            print("  🔧 Install and configure STM8/PIC programmers")
        if not results.get('firmware', False):
            print("  🔧 Add missing firmware files")
        if not results.get('integration', False):
            print("  🔧 Resolve system integration issues")

        if all(results.values()):
            print("  🎉 System is ready for SMT programming operations!")

        # Save report to file
        report_file = self.test_results_dir / f"diagnostic_report_{int(time.time())}.json"
        try:
            report_data = {
                "timestamp": time.time(),
                "overall_score": score,
                "total_tests": total,
                "percentage": percentage,
                "results": results,
                "status": status
            }

            with open(report_file, 'w') as f:
                json.dump(report_data, f, indent=2)

            print(f"\n📄 Detailed report saved to: {report_file}")

        except Exception as e:
            print(f"\n⚠️  Could not save report: {e}")


def main():
    """Enhanced main utility function with comprehensive menu"""
    utility = SMTSetupUtility()

    print("Enhanced SMT Programming Setup Utility")
    print("Diode Dynamics Production Test System v2.0")
    print("=" * 60)

    while True:
        print("\nAvailable commands:")
        print("1. Test SMT Arduino connection")
        print("2. Validate programming configuration")
        print("3. Test programmer connections")
        print("4. Create enhanced configuration")
        print("5. Test programming sequence (dry run)")
        print("6. Run comprehensive diagnostics")
        print("7. View system status")
        print("8. Export configuration template")
        print("9. Quit")

        try:
            choice = input("\nEnter choice (1-9): ").strip()

            if choice == '1':
                port = input("Enter SMT Arduino port (e.g., COM5): ").strip()
                utility.test_smt_arduino_connection(port)

            elif choice == '2':
                utility.validate_programming_config()

            elif choice == '3':
                utility.test_programmer_connections()

            elif choice == '4':
                utility.create_enhanced_config()

            elif choice == '5':
                sku = input("Enter SKU (e.g., DD5000): ").strip()
                port = input("Enter SMT Arduino port (e.g., COM5): ").strip()
                utility.test_programming_sequence(sku, port, dry_run=True)

            elif choice == '6':
                port = input("Enter SMT Arduino port (e.g., COM5): ").strip()
                utility.run_comprehensive_diagnostics(port)

            elif choice == '7':
                print("\nSystem Status:")
                print(f"  Arduino Connected: {utility.arduino_status['connected']}")
                print(f"  SMT Initialized: {utility.arduino_status['smt_initialized']}")
                print(f"  Last Test: {utility.arduino_status['last_test']}")
                print(f"  Programmers: {len(utility.programmer_status)} configured")
                for name, status in utility.programmer_status.items():
                    print(f"    {name}: {'✅' if status else '❌'}")

            elif choice == '8':
                    # template_file variable removed - not used
                utility.create_enhanced_config()
                print(f"\n📋 Configuration template exported as {utility.programming_config_file}")

            elif choice == '9':
                print("\n👋 Goodbye!")
                break

            else:
                print("Invalid choice. Please enter 1-9.")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            logging.exception("Unhandled exception in main menu")


if __name__ == "__main__":
    main()