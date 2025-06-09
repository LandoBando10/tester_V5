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
from src.hardware.arduino_controller import ArduinoController, SensorConfigurations
from config.settings import SENSOR_TIMINGS, TEST_SENSOR_CONFIGS


class SMTArduinoController(ArduinoController):
    """Extended Arduino controller specifically for SMT operations"""
    
    def __init__(self, baud_rate: int = 115200):
        super().__init__(baud_rate)
        self.is_smt_initialized = False
        
    def initialize_smt_system(self) -> bool:
        """Initialize the SMT bed-of-nails fixture"""
        try:
            response = self.send_command("SMT:INIT", timeout=5.0)
            if response and "OK" in response:
                self.is_smt_initialized = True
                self.logger.info("SMT system initialized successfully")
                return True
            else:
                self.logger.error(f"SMT initialization failed: {response}")
                return False
        except Exception as e:
            self.logger.error(f"SMT initialization error: {e}")
            return False
    
    def select_board(self, board_name: str) -> bool:
        """Select a specific board in the bed-of-nails fixture"""
        try:
            response = self.send_command(f"SMT:SELECT:{board_name.upper()}", timeout=3.0)
            if response and "OK" in response:
                self.logger.debug(f"Board {board_name} selected")
                return True
            else:
                self.logger.error(f"Board selection failed for {board_name}: {response}")
                return False
        except Exception as e:
            self.logger.error(f"Board selection error for {board_name}: {e}")
            return False
    
    def deselect_board(self, board_name: str) -> bool:
        """Deselect a specific board in the bed-of-nails fixture"""
        try:
            response = self.send_command(f"SMT:DESELECT:{board_name.upper()}", timeout=3.0)
            if response and "OK" in response:
                self.logger.debug(f"Board {board_name} deselected")
                return True
            else:
                self.logger.error(f"Board deselection failed for {board_name}: {response}")
                return False
        except Exception as e:
            self.logger.error(f"Board deselection error for {board_name}: {e}")
            return False
    
    def deselect_all_boards(self) -> bool:
        """Deselect all boards"""
        return self.deselect_board("ALL")
    
    def set_power(self, power_type: str) -> bool:
        """Set power supply state"""
        try:
            valid_power_types = ["OFF", "PROG_3V3", "PROG_5V", "TEST_12V", "TEST_24V"]
            if power_type.upper() not in valid_power_types:
                self.logger.error(f"Invalid power type: {power_type}")
                return False
                
            response = self.send_command(f"SMT:POWER:{power_type.upper()}", timeout=3.0)
            if response and "OK" in response:
                self.logger.debug(f"Power set to {power_type}")
                return True
            else:
                self.logger.error(f"Power setting failed for {power_type}: {response}")
                return False
        except Exception as e:
            self.logger.error(f"Power control error: {e}")
            return False
    
    def enable_programmer(self, programmer_type: str) -> bool:
        """Enable programmer interface"""
        try:
            valid_programmers = ["STM8", "PIC"]
            if programmer_type.upper() not in valid_programmers:
                self.logger.error(f"Invalid programmer type: {programmer_type}")
                return False
                
            response = self.send_command(f"SMT:PROG:ENABLE_{programmer_type.upper()}", timeout=3.0)
            if response and "OK" in response:
                self.logger.debug(f"{programmer_type} programmer enabled")
                return True
            else:
                self.logger.error(f"Programmer enable failed for {programmer_type}: {response}")
                return False
        except Exception as e:
            self.logger.error(f"Programmer enable error: {e}")
            return False
    
    def disable_programmer(self) -> bool:
        """Disable programmer interface"""
        try:
            response = self.send_command("SMT:PROG:DISABLE", timeout=3.0)
            if response and "OK" in response:
                self.logger.debug("Programmer disabled")
                return True
            else:
                self.logger.error(f"Programmer disable failed: {response}")
                return False
        except Exception as e:
            self.logger.error(f"Programmer disable error: {e}")
            return False
    
    def set_mainbeam(self, state: bool) -> bool:
        """Control mainbeam output for testing"""
        try:
            cmd = "SMT:MAINBEAM:ON" if state else "SMT:MAINBEAM:OFF"
            response = self.send_command(cmd, timeout=2.0)
            if response and "OK" in response:
                self.logger.debug(f"Mainbeam {'ON' if state else 'OFF'}")
                return True
            else:
                self.logger.error(f"Mainbeam control failed: {response}")
                return False
        except Exception as e:
            self.logger.error(f"Mainbeam control error: {e}")
            return False
    
    def set_backlight(self, state: bool) -> bool:
        """Control backlight output for testing"""
        try:
            cmd = "SMT:BACKLIGHT:ON" if state else "SMT:BACKLIGHT:OFF"
            response = self.send_command(cmd, timeout=2.0)
            if response and "OK" in response:
                self.logger.debug(f"Backlight {'ON' if state else 'OFF'}")
                return True
            else:
                self.logger.error(f"Backlight control failed: {response}")
                return False
        except Exception as e:
            self.logger.error(f"Backlight control error: {e}")
            return False


class SMTTest(BaseTest):
    """SMT panel testing with programming and power validation using dedicated SMT Arduino"""

    def __init__(self, sku: str, parameters: Dict[str, Any], port: str, programming_config: Optional[Dict] = None, smt_config_path: Optional[str] = None):
        super().__init__(sku, parameters)
        self.port = port
        self.programming_config = programming_config or {}
        self.smt_config_path = smt_config_path
        self.arduino = ArduinoController(baud_rate=115200)  # Use standard controller with SMT firmware
        self.smt_controller = SMTController(self.arduino)
        self.required_params = ["power"]  # Changed to lowercase to match SKU file

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
            self.update_progress("Connecting to SMT Arduino...", 10)

            if not self.validate_parameters(self.required_params):
                return False

            # Connect to SMT Arduino
            if not self.arduino.connect(self.port):
                self.logger.error(f"Failed to connect to SMT Arduino on port {self.port}")
                return False

            self.update_progress("Initializing SMT system...", 20)

            # Load SMT configuration if provided
            if self.smt_config_path:
                if not self.smt_controller.load_configuration(self.smt_config_path):
                    self.logger.error(f"Failed to load SMT configuration: {self.smt_config_path}")
                    return False

            # Initialize SMT controller with Arduino
            if not self.smt_controller.initialize_arduino():
                self.logger.error("Failed to initialize SMT controller")
                return False

            self.update_progress("Hardware setup complete", 40)
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

            # Add power validation phases
            power_params = self.parameters.get("power", {})  # Changed to lowercase
            sequence_id = power_params.get("sequence", "SMT_SEQ_A")  # Changed key name to match SKU file

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
        Ask the tester to measure a comma-separated relay list and parse the
        streamed MEASUREMENT lines into a {board-name: {...}} dict.
        """
        board_results = {}
        self.logger.info(f"Sending MEASURE_GROUP:{relays}")
        
        # Send command and collect ALL responses until MEASURE_GROUP:COMPLETE
        response_lines = []
        
        # Send the command
        self.arduino.serial.write(f"MEASURE_GROUP:{relays}\r\n")
        
        # Read responses until we see COMPLETE or timeout
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            line = self.arduino.serial.read_line(timeout=0.5)
            if line:
                response_lines.append(line)
                if "MEASURE_GROUP:COMPLETE" in line:
                    break
                elif "STOPPED" in line:  # Handle early termination
                    break
        
        # Join all response lines
        full_response = '\n'.join(response_lines)
        self.logger.info(f"Full response:\n{full_response}")

        # Parse measurement lines
        for line in response_lines:
            if line.startswith("MEASUREMENT:"):
                try:
                    _, relay, rest = line.split(":", 2)
                    relay_num = int(relay)
                    data = {}
                    for pair in rest.split(","):
                        if "=" in pair:
                            k, v = pair.split("=", 1)
                            data[k.strip()] = float(v.strip())
                    
                    board_results[f"Board {relay_num}"] = {
                        "relay": relay_num,
                        "voltage": data.get("V", 0),
                        "current": data.get("I", 0),
                        "power": data.get("P", 0)
                    }
                except Exception as e:
                    self.logger.error(f"Error parsing measurement line '{line}': {e}")
        
        # Don't send RELAY_ALL:OFF here - the Arduino already does it
        self.logger.info(f"Parsed board results: {list(board_results.keys())}")
        return board_results

    def _execute_mainbeam_power_test(self, duration: float, base_progress: int) -> bool:
        try:
            self.update_progress("Measuring main-beam current on all boards…", base_progress)
            board_results = self._measure_group("1,2,3,4")   # relays 1-4
            currents = [d["current"] for d in board_results.values()]

            self.result.measurements["mainbeam_current_readings"] = {
                "board_results": board_results,
                "values": currents,
                "average": sum(currents) / len(currents) if currents else 0
            }
            return True
        except Exception as e:
            self.logger.error(f"Main-beam power test error: {e}")
            return False

    def _execute_backlight_power_test(self, duration: float, base_progress: int) -> bool:
        try:
            if not self._has_backlight_support():
                self.logger.info("Back-light test not supported; skipping")
                return True

            self.update_progress("Measuring back-light current on all boards…", base_progress)
            board_results = self._measure_group("5,6,7,8")   # relays 5-8
            
            # Rename boards from "Board 5-8" to "Board 1-4" for backlight
            renamed_results = {}
            for board_name, board_data in board_results.items():
                if board_name.startswith("Board "):
                    try:
                        relay_num = int(board_name.split()[1])
                        if relay_num >= 5 and relay_num <= 8:
                            board_num = relay_num - 4  # Convert relay 5->1, 6->2, 7->3, 8->4
                            renamed_results[f"Board {board_num}"] = board_data
                        else:
                            # Keep original name if not in expected range
                            renamed_results[board_name] = board_data
                    except ValueError:
                        renamed_results[board_name] = board_data
                else:
                    renamed_results[board_name] = board_data
            
            currents = [d["current"] for d in renamed_results.values()]

            self.result.measurements["backlight_current_readings"] = {
                "board_results": renamed_results,
                "values": currents,
                "average": sum(currents) / len(currents) if currents else 0
            }
            return True
        except Exception as e:
            self.logger.error(f"Back-light power test error: {e}")
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

            power_params = self.parameters.get("power", {})  # Changed to lowercase
            min_mainbeam_current = power_params.get("min_mainbeam_A", 0.5)  # Changed key name to match SKU file
            max_mainbeam_current = power_params.get("max_mainbeam_A", 2.0)  # Changed key name to match SKU file
            min_backlight_current = power_params.get("min_backlight_A", 0.1)  # Add backlight limits
            max_backlight_current = power_params.get("max_backlight_A", 0.5)

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

            # Disconnect
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
