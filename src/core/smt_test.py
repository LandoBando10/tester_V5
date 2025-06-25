import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from src.core.base_test import BaseTest, TestResult
from src.core.programmer_controller import ProgrammerController
from src.core.smt_controller import SMTController
from src.hardware.smt_arduino_controller import SMTArduinoController
from src.spc.spc_integration import SPCIntegration

class SMTTest(BaseTest):
    """SMT panel testing with programming and power validation using dedicated SMT Arduino"""

    def __init__(self, sku: str, parameters: Dict[str, Any], port: str, programming_config: Optional[Dict] = None, smt_config_path: Optional[str] = None, arduino_controller=None, spc_config: Optional[Dict] = None):
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

        # Initialize programmers if configured
        self._initialize_programmers()
        
        # Initialize SPC if configured
        self.spc_config = spc_config or {}
        self.spc = None
        if self.spc_config.get('enabled', False):
            self.spc = SPCIntegration(
                spc_enabled=True,
                sampling_mode=self.spc_config.get('sampling_mode', True),
                production_mode=self.spc_config.get('production_mode', False),
                logger=self.logger
            )
            # Connect to spec calculation ready signal
            self.spc.spec_calculation_ready.connect(self._on_spec_calculation_ready)
            self.logger.info(f"SPC enabled - Sampling: {self.spc_config.get('sampling_mode')}, Production: {self.spc_config.get('production_mode')}")

    def _on_spec_calculation_ready(self, sku: str):
        """Handle when enough measurements collected for spec calculation"""
        self.logger.info(f"Spec calculation ready for {sku}")
        # This will be handled by the GUI - emit a signal or call a callback
        if hasattr(self, 'spec_calculation_callback'):
            self.spec_calculation_callback(sku)
    
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
        """Initialize SMT Arduino - simplified setup"""
        try:
            self.update_progress("Setting up SMT test...", 10)

            # Only connect if we own the Arduino instance
            if self.owns_arduino and not self.arduino.is_connected():
                self.update_progress("Connecting to SMT Arduino...", 15)
                if not self.arduino.connect(self.port):
                    self.logger.error(f"Failed to connect to SMT Arduino on port {self.port}")
                    return False

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
        """Execute test sequence from configuration only"""
        try:
            # Programming phase if enabled
            if self.programming_enabled and self.programmers:
                self.update_progress("Programming boards...", 45)
                success = self._execute_programming_phase(30.0, 45)
                if not success:
                    self.result.failures.append("Programming phase failed")
            
            
            # Single panel measurement
            self.update_progress("Measuring panel...", 60)
            panel_measurements = self.arduino.test_panel()
            
            if not panel_measurements:
                self.logger.error("Panel test failed - no measurements received")
                self.result.failures.append("Failed to get panel measurements from Arduino")
                return self.result
            
            # Log raw measurements
            self.logger.info(f"Received measurements for {len(panel_measurements)} relays")
            
            # Distribute results by function
            function_results = self._distribute_panel_results(panel_measurements, self.relay_mapping)
            
            # Read test sequence from configuration
            test_sequence = self.parameters.get("test_sequence", [])
            if not test_sequence:
                raise ValueError("No test_sequence defined in SKU configuration")
            
            # Analyze each function against its limits
            self.update_progress("Analyzing results...", 80)
            for test_config in test_sequence:
                function = test_config["function"]
                limits = test_config["limits"]
                
                if function in function_results:
                    # Store results for this function
                    self.result.measurements[f"{function}_readings"] = {
                        "board_results": self._format_board_results(function, function_results[function]),
                        "limits": limits
                    }
                else:
                    self.logger.warning(f"No measurements found for function: {function}")
            
            # Final analysis
            self._analyze_results()
            return self.result
            
        except Exception as e:
            self.logger.error(f"Test sequence error: {e}")
            self.result.failures.append(str(e))
            return self.result


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

                    # Note: Batch-only Arduino doesn't support programming control
                    # Programming must be done with external hardware
                    self.logger.info(f"Programming {board_name} - Arduino board selection not available in batch mode")

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

            # Note: Batch-only Arduino doesn't have programming control methods
            self.logger.info("Programming cleanup - Arduino programming control not available in batch mode")

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

    def _distribute_panel_results(self, panel_measurements: Dict[int, Dict], relay_mapping: Dict) -> Dict[str, Dict[int, Dict]]:
        """
        Distribute panel measurements by function based on relay mapping
        
        Args:
            panel_measurements: Raw measurements from test_panel() {relay_num: {voltage, current, power}}
            relay_mapping: Relay configuration from SKU
            
        Returns:
            Dictionary organized by function -> board -> measurements
        """
        function_results = {}
        
        for relay_str, mapping in relay_mapping.items():
            if mapping is None:
                continue
                
            relay_num = int(relay_str)
            board_num = mapping.get("board")
            function = mapping.get("function")
            
            if not board_num or not function:
                continue
                
            # Initialize function dict if needed
            if function not in function_results:
                function_results[function] = {}
                
            # Add measurements for this board if relay was measured
            if relay_num in panel_measurements and panel_measurements[relay_num]:
                function_results[function][board_num] = panel_measurements[relay_num]
                
        return function_results
    
    def _format_board_results(self, function: str, board_measurements: Dict[int, Dict]) -> Dict[str, Dict]:
        """
        Format board measurements for storage in results
        
        Args:
            function: Function name
            board_measurements: {board_num: {voltage, current, power}}
            
        Returns:
            Formatted results {Board_X: {relay, voltage, current, power}}
        """
        formatted = {}
        
        for board_num, measurements in board_measurements.items():
            board_key = f"Board {board_num}"
            
            # Find relay number for this board/function combination
            relay_num = None
            for relay_str, mapping in self.relay_mapping.items():
                if (mapping and 
                    mapping.get("board") == board_num and 
                    mapping.get("function") == function):
                    relay_num = int(relay_str)
                    break
            
            formatted[board_key] = {
                "relay": relay_num,
                "voltage": measurements.get("voltage", 0),
                "current": measurements.get("current", 0),
                "power": measurements.get("power", 0)
            }
            
        return formatted


    def _analyze_results(self):
        """Analyze results based on configuration limits"""
        try:
            self.update_progress("Analyzing results...", 85)
            
            # Create a list of keys to avoid dictionary modification during iteration
            measurement_keys = list(self.result.measurements.keys())
            
            # Analyze each function's results
            for function_name in measurement_keys:
                if not function_name.endswith("_readings"):
                    continue
                    
                data = self.result.measurements.get(function_name)
                if not data:
                    continue
                    
                function = function_name.replace("_readings", "")
                board_results = data.get("board_results", {})
                limits = data.get("limits", {})
                
                # Check each board against limits (pass/fail per board)
                for board_name, measurements in board_results.items():
                    self._check_limits(board_name, function, measurements, limits)
            
            # Check programming results
            self._check_programming_results()
            
        except Exception as e:
            self.logger.error(f"Analysis error: {e}")
            self.result.failures.append(f"Analysis error: {str(e)}")
    
    def _check_limits(self, board_name: str, function: str, measurements: Dict, limits: Dict):
        """Check measurements against limits"""
        board_key = board_name.replace(' ', '_').lower()
        
        # Check current
        if "current" in measurements and "current_A" in limits:
            current = measurements["current"]
            min_val = limits["current_A"]["min"]
            max_val = limits["current_A"]["max"]
            
            self.result.add_measurement(
                f"{function}_{board_key}_current",
                current, min_val, max_val, "A"
            )
            
            # Add to SPC if enabled
            if self.spc and self.spc.sampling_mode:
                board_id = board_name.replace(' ', '_')
                self.spc.add_measurement(self.sku, function, board_id, current, measurements.get("voltage", 0))
            
            if not (min_val <= current <= max_val):
                self.result.failures.append(
                    f"{board_name} {function} current {current:.3f}A "
                    f"outside limits ({min_val:.3f}-{max_val:.3f}A)"
                )
            
            # Check SPC control limits if in production mode
            if self.spc and self.spc.production_mode:
                violations = self.spc.check_control_limits(self.sku, function, board_name.replace(' ', '_'), current)
                if violations:
                    for violation in violations:
                        self.result.failures.append(f"SPC violation: {violation}")
        
        # Check voltage
        if "voltage" in measurements and "voltage_V" in limits:
            voltage = measurements["voltage"]
            min_val = limits["voltage_V"]["min"]
            max_val = limits["voltage_V"]["max"]
            
            self.result.add_measurement(
                f"{function}_{board_key}_voltage",
                voltage, min_val, max_val, "V"
            )
            
            if not (min_val <= voltage <= max_val):
                self.result.failures.append(
                    f"{board_name} {function} voltage {voltage:.3f}V "
                    f"outside limits ({min_val:.3f}-{max_val:.3f}V)"
                )
    
    def _check_programming_results(self):
        """Check programming results if applicable"""
        if self.programming_results:
            failed = [r for r in self.programming_results if not r["success"]]
            for failure in failed:
                self.result.failures.append(
                    f"Programming failed for {failure['board']}: {failure['message']}"
                )

    def cleanup_hardware(self):
        """Clean up SMT Arduino and fixture"""
        try:
            self.update_progress("Cleaning up hardware...", 95)

            # Turn off all outputs using SMT controller
            self.smt_controller.all_lights_off()
            
            # Turn off all relays
            self.arduino.all_relays_off()

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

    # Example test parameters - configuration-driven
    parameters = {
        "timing": {
            "power_stabilization_s": 0.5,
            "default_test_duration_s": 1.5,
            "command_interval_ms": 20,
            "test_cooldown_s": 0.5
        },
        "test_sequence": [
            {
                "name": "function_test",
                "function": "main_output",
                "duration": 1.5,
                "limits": {
                    "current_A": {"min": 0.85, "max": 1.15},
                    "voltage_V": {"min": 12.0, "max": 13.5}
                }
            }
        ]
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
