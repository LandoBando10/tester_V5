import time
import json
import logging
import subprocess
import threading
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from src.core.base_test import BaseTest, TestResult
from src.core.programmer_controller import ProgrammerController
from src.core.smt_controller import SMTController
from src.hardware.smt_arduino_controller import SMTArduinoController, SMTSensorConfigurations
from config.settings import SENSOR_TIMINGS, TEST_SENSOR_CONFIGS


# Note: SMTArduinoController is now imported from smt_arduino_controller.py

class SMTTest(BaseTest):
    """SMT panel testing with programming and power validation using dedicated SMT Arduino"""

    def __init__(self, sku: str, parameters: Dict[str, Any], port: str, programming_config: Optional[Dict] = None, smt_config_path: Optional[str] = None, arduino_controller=None):
        super().__init__(sku, parameters)
        self.port = port
        self.programming_config = programming_config or {}
        self.smt_config_path = smt_config_path
        
        # Use provided Arduino controller or create new one
        self.arduino = arduino_controller
        self.owns_arduino = False  # Track if we created the Arduino instance
        if not self.arduino:
            self.arduino = SMTArduinoController(baud_rate=115200)
            self.owns_arduino = True
            
        self.smt_controller = SMTController(self.arduino)
        self.relay_mapping = {}

        # Programming control
        self.programmers: Dict[str, ProgrammerController] = {}
        self.programming_enabled = False
        self.programming_results: List[Dict[str, Any]] = []

        # Test sequence control
        self.test_phases = []
        self.current_phase = 0

        # Initialize programmers if configured
        self._initialize_programmers()

    def _initialize_programmers(self):
        """Initialize configured programmers"""
        if not self.programming_config:
            self.logger.info("No programming configuration provided")
            return

        try:
            self.programming_enabled = self.programming_config.get("enabled", False)

            if self.programming_enabled:
                programmers_config = self.programming_config.get("programmers", {})

                for prog_name, prog_config in programmers_config.items():
                    try:
                        programmer = ProgrammerController(
                            programmer_type=prog_config["type"],
                            programmer_path=prog_config["path"]
                        )

                        # Verify programmer connection
                        connected, msg = programmer.verify_connection()
                        if connected:
                            self.programmers[prog_name] = programmer
                            self.logger.info(f"Initialized {prog_name} programmer: {msg}")
                        else:
                            self.logger.warning(f"Failed to initialize {prog_name} programmer: {msg}")

                    except Exception as e:
                        self.logger.error(f"Error initializing {prog_name} programmer: {e}")

        except Exception as e:
            self.logger.error(f"Error initializing programmers: {e}")
            self.programming_enabled = False

    def setup_hardware(self) -> bool:
        """Initialize SMT Arduino and bed-of-nails fixture"""
        try:
            self.update_progress("Setting up SMT test...", 10)

            # Only connect if we own the Arduino instance
            if self.owns_arduino and not self.arduino.is_connected():
                self.update_progress("Connecting to SMT Arduino...", 15)
                if not self.arduino.connect(self.port):
                    self.logger.error(f"Failed to connect to SMT Arduino on port {self.port}")
                    return False

            # Skip sensor configuration if already configured
            if not hasattr(self.arduino, '_sensors_configured'):
                self.update_progress("Configuring sensors...", 20)
                sensor_configs = SMTSensorConfigurations.smt_panel_sensors()
                
                if not self.arduino.configure_sensors(sensor_configs):
                    self.logger.error("Failed to configure sensors")
                    self.logger.error("Please check:")
                    self.logger.error("1. INA260 sensor is properly connected to I2C bus")
                    self.logger.error("2. Sensor has power (check VCC and GND connections)")
                    self.logger.error("3. I2C pull-up resistors are present")
                    self.logger.error("4. No I2C address conflicts (INA260 default is 0x40)")
                    return False
                
                self.arduino._sensors_configured = True
                self.logger.info("Sensors configured successfully")
            else:
                self.logger.info("Sensors already configured, skipping")

            # REMOVED: 2-second sleep for sensor stabilization
            # The sensors should be ready immediately or after minimal delay

            # Get SMT configuration
            self.update_progress("Initializing SMT controller...", 30)
            smt_config = self.parameters
            if not smt_config:
                self.logger.error("No SMT configuration found in parameters")
                return False
                
            # Store relay mapping for our use
            self.relay_mapping = smt_config.get("relay_mapping", {})
            if not self.relay_mapping:
                self.logger.error("No relay_mapping found in SKU configuration")
                return False

            # Configure SMT controller
            self.smt_controller.set_configuration(smt_config)

            # Initialize SMT controller with Arduino
            if not self.smt_controller.initialize_arduino():
                self.logger.error("Failed to initialize SMT controller")
                return False

            self.update_progress("Ready to test", 40)
            return True

        except Exception as e:
            self.logger.error(f"Hardware setup error: {e}")
            return False

    def run_test_sequence(self) -> TestResult:
        """Execute SMT test sequence with programming and power validation"""
        try:
            # Define test phases
            self.test_phases = []

            # Add programming phase if enabled
            if self.programming_enabled and self.programmers:
                self.test_phases.append({
                    "name": "Programming",
                    "duration": 30.0,
                    "action": "program_boards"
                })

            # Add power validation phases from configuration
            smt_config = self.parameters
            test_sequence = smt_config.get("test_sequence", [])

            self.test_phases.extend([
                {
                    "name": "Power Stabilization",
                    "duration": 2.0,
                    "action": "stabilize_power"
                },
                {
                    "name": "Mainbeam Power Test",
                    "duration": 5.0,
                    "action": "test_mainbeam_power"
                },
                {
                    "name": "Backlight Power Test",
                    "duration": 3.0,
                    "action": "test_backlight_power"
                }
            ])

            # Execute each phase
            for phase_idx, phase in enumerate(self.test_phases):
                self.current_phase = phase_idx
                success = self._execute_phase(phase, phase_idx)
                if not success:
                    self.result.failures.append(f"Phase '{phase['name']}' failed")
                    # Continue with remaining phases for diagnostic info

            # Analyze results
            self._analyze_results()

            return self.result

        except Exception as e:
            self.logger.error(f"Test sequence error: {e}")
            self.result.failures.append(f"Test sequence error: {str(e)}")
            return self.result

    def _execute_phase(self, phase: Dict[str, Any], phase_idx: int) -> bool:
        """Execute a single test phase"""
        try:
            phase_name = phase["name"]
            duration = phase["duration"]
            action = phase["action"]

            # Calculate progress
            base_progress = 45 + (phase_idx * 40 // len(self.test_phases))
            self.update_progress(f"Executing {phase_name}...", base_progress)

            # Execute phase action
            if action == "program_boards":
                return self._execute_programming_phase(duration, base_progress)
            elif action == "stabilize_power":
                return self._execute_power_stabilization(duration, base_progress)
            elif action == "test_mainbeam_power":
                return self._execute_mainbeam_power_test(duration, base_progress)
            elif action == "test_backlight_power":
                return self._execute_backlight_power_test(duration, base_progress)
            else:
                self.logger.warning(f"Unknown phase action: {action}")
                return True

        except Exception as e:
            self.logger.error(f"Phase execution error: {e}")
            return False

    def _execute_programming_phase(self, duration: float, base_progress: int) -> bool:
        """Execute board programming phase"""
        try:
            self.logger.info("Starting board programming phase")

            hex_files = self.programming_config.get("hex_files", {})
            programmers_config = self.programming_config.get("programmers", {})
            device_map = self.programming_config.get("device_types", {})

            programming_success = True
            total_boards = 0
            successful_boards = 0

            # Count total boards to program
            for prog_name, prog_config in programmers_config.items():
                total_boards += len(prog_config.get("boards", []))

            board_index = 0

            # Program each board
            for prog_name, prog_config in programmers_config.items():
                if prog_name not in self.programmers:
                    self.logger.warning(f"Programmer {prog_name} not available")
                    continue

                programmer = self.programmers[prog_name]
                boards = prog_config.get("boards", [])

                for board_name in boards:
                    board_index += 1

                    # Update progress
                    board_progress = base_progress + (board_index * 25 // total_boards)
                    self.update_progress(f"Programming {board_name}...", board_progress)

                    # Get hex file for this board
                    hex_file = hex_files.get(board_name)
                    if not hex_file:
                        error_msg = f"No hex file specified for board {board_name}"
                        self.logger.error(error_msg)
                        self.programming_results.append({
                            "board": board_name,
                            "success": False,
                            "message": error_msg
                        })
                        programming_success = False
                        continue

                    # Check if hex file exists
                    hex_path = Path(hex_file)
                    if not hex_path.exists():
                        error_msg = f"Hex file not found: {hex_file}"
                        self.logger.error(error_msg)
                        self.programming_results.append({
                            "board": board_name,
                            "success": False,
                            "message": error_msg
                        })
                        programming_success = False
                        continue

                    # Select board in bed-of-nails fixture
                    if not self.arduino.select_board(board_name):
                        error_msg = f"Failed to select board {board_name} in fixture"
                        self.logger.error(error_msg)
                        self.programming_results.append({
                            "board": board_name,
                            "success": False,
                            "message": error_msg
                        })
                        programming_success = False
                        continue

                    # Enable programmer interface
                    programmer_type = prog_config.get("type", "STM8")
                    if not self.arduino.enable_programmer(programmer_type):
                        error_msg = f"Failed to enable {programmer_type} programmer for {board_name}"
                        self.logger.error(error_msg)
                        self.programming_results.append({
                            "board": board_name,
                            "success": False,
                            "message": error_msg
                        })
                        programming_success = False
                        continue

                    # Set programming power
                    power_type = "PROG_5V" if programmer_type == "STM8" else "PROG_3V3"
                    if not self.arduino.set_power(power_type):
                        error_msg = f"Failed to set programming power for {board_name}"
                        self.logger.error(error_msg)
                        self.programming_results.append({
                            "board": board_name,
                            "success": False,
                            "message": error_msg
                        })
                        programming_success = False
                        continue

                    # Get device type for this board, None triggers default in programmer
                    device = device_map.get(board_name, None)
                    
                    # Program the board with device parameter
                    prog_success, prog_message = programmer.program_board(str(hex_path), board_name, device=device)

                    self.programming_results.append({
                        "board": board_name,
                        "success": prog_success,
                        "message": prog_message
                    })

                    if prog_success:
                        successful_boards += 1
                        self.logger.info(f"Successfully programmed {board_name}")
                    else:
                        programming_success = False
                        self.logger.error(f"Failed to program {board_name}: {prog_message}")

            # Clean up after programming
            self.arduino.set_power("OFF")
            self.arduino.disable_programmer()
            self.arduino.deselect_all_boards()

            # Record programming results
            if total_boards > 0:
                programming_yield = (successful_boards / total_boards) * 100
                self.result.add_measurement(
                    "programming_yield",
                    programming_yield,
                    100.0,  # Expect 100% yield
                    100.0,
                    "%"
                )

            self.logger.info(f"Programming phase complete: {successful_boards}/{total_boards} boards successful")
            return programming_success

        except Exception as e:
            self.logger.error(f"Programming phase error: {e}")
            return False

    def _execute_power_stabilization(self, duration: float, base_progress: int) -> bool:
        """Wait for power supplies to stabilize"""
        try:
            # Skip power stabilization delay - power should already be stable
            self.logger.info("Power supplies ready")
            self.update_progress("Power stabilized", base_progress + 25)
            return True

        except Exception as e:
            self.logger.error(f"Power stabilization error: {e}")
            return False

    # --- new helper ----------------------------------------------------
    def _measure_group(self, relays: str, timeout: float = 15.0) -> Dict[str, Dict]:
        """
        Measure a group of relays and map results back to board numbers
        Uses new individual command approach (Phase 1.1)
        """
        board_results = {}
        relay_list = [int(r.strip()) for r in relays.split(',') if r.strip()]
        
        # PHASE 1: Enforce test cooldown if this is a new test
        self.arduino.enforce_test_cooldown()
        
        # PHASE 1: Verify Arduino is responsive before starting
        if not self.arduino.verify_arduino_responsive():
            self.logger.error("Arduino not responsive before measurements")
            if not self.arduino.recover_communication():
                self.logger.error("Failed to recover Arduino communication")
                return board_results
        
        # Use new measure_relays method with individual commands
        self.logger.info(f"Measuring relays using individual commands: {relay_list}")
        
        # Get measurements
        measurement_results = self.arduino.measure_relays(relay_list, timeout=2.0)
        
        if not measurement_results:
            self.logger.error("No measurements received")
            self.result.failures.append("Failed to communicate with Arduino during measurement")
            return board_results
        
        # Map results to boards
        for relay_num, measurement in measurement_results.items():
            if measurement is None:
                self.logger.warning(f"No measurement for relay {relay_num}")
                continue
                
            # Get board number from relay mapping
            board_num = self.smt_controller.get_board_from_relay(relay_num)
            if not board_num:
                self.logger.warning(f"No board mapping found for relay {relay_num}")
                continue
            
            board_results[f"Board {board_num}"] = {
                "relay": relay_num,
                "voltage": measurement.get("voltage", 0),
                "current": measurement.get("current", 0),
                "power": measurement.get("power", 0)
            }
        
        self.logger.info(f"Parsed board results: {list(board_results.keys())}")
        
        # Validate we got measurements
        expected_count = len(relay_list)
        actual_count = len(board_results)
        
        if actual_count == 0:
            self.logger.error(f"No measurements received for relays {relay_list}")
            self.result.failures.append(f"No measurements received from Arduino for relays {relay_list}")
        elif actual_count < expected_count:
            self.logger.warning(f"Only received {actual_count}/{expected_count} measurements")
            missing_relays = [r for r in relay_list if r not in measurement_results or measurement_results[r] is None]
            self.logger.warning(f"Missing measurements for relays: {missing_relays}")
        
        return board_results

    def _execute_mainbeam_power_test(self, duration: float, base_progress: int) -> bool:
        try:
            self.update_progress("Measuring mainbeam current on all boards...", base_progress)
            
            # Get mainbeam relays from mapping
            mainbeam_relays = self.smt_controller.get_relays_for_function("mainbeam")
            if not mainbeam_relays:
                self.logger.error("No mainbeam relays found in configuration")
                return False
                
            relay_str = ",".join(map(str, mainbeam_relays))
            board_results = self._measure_group(relay_str)
            
            currents = [d["current"] for d in board_results.values()]
            self.result.measurements["mainbeam_current_readings"] = {
                "board_results": board_results,
                "values": currents,
                "average": sum(currents) / len(currents) if currents else 0
            }
            return True
        except Exception as e:
            self.logger.error(f"Mainbeam power test error: {e}")
            return False

    def _execute_backlight_power_test(self, duration: float, base_progress: int) -> bool:
        try:
            self.update_progress("Measuring backlight current on all boards...", base_progress)
            
            # Get all backlight relays (any function containing "backlight")
            backlight_relays = []
            for relay_str, mapping in self.relay_mapping.items():
                if mapping and "backlight" in mapping.get("function", ""):
                    backlight_relays.append(int(relay_str))
            
            if not backlight_relays:
                self.logger.info("No backlight relays found - skipping backlight test")
                return True
                
            backlight_relays.sort()
            relay_str = ",".join(map(str, backlight_relays))
            board_results = self._measure_group(relay_str)
            
            currents = [d["current"] for d in board_results.values()]
            self.result.measurements["backlight_current_readings"] = {
                "board_results": board_results,
                "values": currents,
                "average": sum(currents) / len(currents) if currents else 0
            }
            return True
        except Exception as e:
            self.logger.error(f"Backlight power test error: {e}")
            return False

    def _has_backlight_support(self) -> bool:
        """Check if current SKU supports backlight testing"""
        # This would check the SKU configuration
        # For now, assume all SKUs support backlight
        return True

    def _analyze_results(self):
        """Analyze collected data and generate test results"""
        try:
            self.update_progress("Analyzing results...", 85)

            # The parameters ARE the smt_testing configuration
            smt_config = self.parameters
            test_sequence = smt_config.get("test_sequence", [])
            
            # Extract limits from test sequence
            mainbeam_limits = {}
            backlight_limits = {}
            
            for test in test_sequence:
                if test.get("function") == "mainbeam":
                    mainbeam_limits = test.get("limits", {})
                elif "backlight" in test.get("function", ""):
                    backlight_limits = test.get("limits", {})
            
            # Get current limits or use defaults
            min_mainbeam_current = mainbeam_limits.get("current_A", {}).get("min", 0.5)
            max_mainbeam_current = mainbeam_limits.get("current_A", {}).get("max", 2.0)
            min_backlight_current = backlight_limits.get("current_A", {}).get("min", 0.1)
            max_backlight_current = backlight_limits.get("current_A", {}).get("max", 0.5)

            # Analyze mainbeam power
            mainbeam_data = self.result.measurements.get("mainbeam_current_readings")
            if mainbeam_data and mainbeam_data.get("board_results"):
                board_results = mainbeam_data["board_results"]
                self.logger.info(f"Analyzing mainbeam boards: {list(board_results.keys())}")
                
                # Check each board individually
                for board_name, board_data in board_results.items():
                    if "current" in board_data:
                        current = board_data["current"]
                        self.logger.info(f"{board_name} mainbeam current: {current:.3f}A (limits: {min_mainbeam_current:.3f} - {max_mainbeam_current:.3f}A)")
                        
                        # Add individual board measurement
                        self.result.add_measurement(
                            f"mainbeam_{board_name.replace(' ', '_').lower()}_current",
                            current,
                            min_mainbeam_current,
                            max_mainbeam_current,
                            "A"
                        )
                        
                        # Check if board passes
                        if current < min_mainbeam_current or current > max_mainbeam_current:
                            self.result.failures.append(
                                f"{board_name} mainbeam current {current:.3f}A outside limits ({min_mainbeam_current:.3f} - {max_mainbeam_current:.3f}A)"
                            )
                    elif "error" in board_data:
                        self.result.failures.append(f"{board_name} mainbeam measurement failed: {board_data['error']}")
                
                # Add overall average
                if mainbeam_data.get("average", 0) > 0:
                    avg_current = mainbeam_data["average"]
                    self.result.add_measurement(
                        "mainbeam_average_current",
                        avg_current,
                        min_mainbeam_current,
                        max_mainbeam_current,
                        "A"
                    )

            # Analyze backlight power (if tested)
            backlight_data = self.result.measurements.get("backlight_current_readings")
            if backlight_data and backlight_data.get("board_results"):
                board_results = backlight_data["board_results"]
                self.logger.info(f"Analyzing backlight boards: {list(board_results.keys())}")
                
                # Check each board individually
                for board_name, board_data in board_results.items():
                    if "current" in board_data:
                        current = board_data["current"]
                        self.logger.info(f"{board_name} backlight current: {current:.3f}A (limits: {min_backlight_current:.3f} - {max_backlight_current:.3f}A)")
                        
                        # Add individual board measurement
                        self.result.add_measurement(
                            f"backlight_{board_name.replace(' ', '_').lower()}_current",
                            current,
                            min_backlight_current,
                            max_backlight_current,
                            "A"
                        )
                        
                        # Check if board passes
                        if current < min_backlight_current or current > max_backlight_current:
                            self.result.failures.append(
                                f"{board_name} backlight current {current:.3f}A outside limits ({min_backlight_current:.3f} - {max_backlight_current:.3f}A)"
                            )
                    elif "error" in board_data:
                        self.result.failures.append(f"{board_name} backlight measurement failed: {board_data['error']}")
                
                # Add overall average
                if backlight_data.get("average", 0) > 0:
                    avg_current = backlight_data["average"]
                    self.result.add_measurement(
                        "backlight_average_current",
                        avg_current,
                        min_backlight_current,
                        max_backlight_current,
                        "A"
                    )

            # Check programming results
            if self.programming_results:
                failed_boards = [r for r in self.programming_results if not r["success"]]
                if failed_boards:
                    for failed_board in failed_boards:
                        self.result.failures.append(
                            f"Programming failed for {failed_board['board']}: {failed_board['message']}"
                        )

        except Exception as e:
            self.logger.error(f"Analysis error: {e}")
            self.result.failures.append(f"Analysis error: {str(e)}")

    def cleanup_hardware(self):
        """Clean up SMT Arduino and fixture"""
        try:
            self.update_progress("Cleaning up hardware...", 95)

            # Turn off all outputs using SMT controller
            self.smt_controller.all_lights_off()
            
            # PHASE 1: Mark test as complete for cooldown tracking
            self.arduino.mark_test_complete()

            # Only disconnect if we own the Arduino instance
            if self.owns_arduino:
                self.arduino.disconnect()

            self.logger.info("SMT hardware cleanup complete")

        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")

    def get_programming_results(self) -> List[Dict[str, Any]]:
        """Get detailed programming results"""
        return self.programming_results


# Example usage and configuration
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example programming configuration
    programming_config = {
        "enabled": True,
        "device_types": {
            "main_controller": "STM8S003F3",
            "led_driver_1": "STM8S105K6",
            "power_board": "PIC18F47J53"
        },
        "programmers": {
            "stm8": {
                "type": "STM8",
                "path": "C:/Program Files/STMicroelectronics/st_toolset/stvp/STVP_CmdLine.exe",
                "boards": ["main_controller", "led_driver_1"]
            },
            "pic": {
                "type": "PIC",
                "path": "C:/Program Files/Microchip/MPLABX/v5.50/mplab_platform/bin/pk3cmd.exe",
                "boards": ["power_board"]
            }
        },
        "hex_files": {
            "main_controller": "firmware/main_v1.2.hex",
            "led_driver_1": "firmware/driver_v1.1.hex",
            "power_board": "firmware/power_v2.0.hex"
        }
    }

    # Example test parameters
    parameters = {
        "POWER": {
            "sequence_id": "SMT_SEQ_A",
            "min_mainbeam_current_A": 0.85,
            "max_mainbeam_current_A": 1.15
        }
    }


    def progress_callback(message: str, percentage: int):
        print(f"[{percentage:3d}%] {message}")


    # Example test run
    # test = SMTTest("DD5000", parameters, "COM4", programming_config)
    # test.set_progress_callback(progress_callback)
    # result = test.execute()
    # print(f"Test result: {'PASS' if result.passed else 'FAIL'}")
    # print(f"Programming results: {test.get_programming_results()}")

    print("Enhanced SMT test module loaded with per-board MCU device selection.")
