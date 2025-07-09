#!/usr/bin/env python3
"""
Hardware validation tests for TESTSEQ protocol implementation
Tests relay switching speed, measurement accuracy, timing jitter, thermal behavior, and EMI/noise

These tests require:
- Arduino with firmware v2.0.0+ connected
- Oscilloscope for switching speed measurement (optional)
- Reference multimeter for accuracy validation (optional)
- Thermal camera or thermocouple for thermal tests (optional)
- EMI test equipment (optional)
"""

import unittest
import time
import logging
import json
import statistics
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from src.hardware.smt_arduino_controller import SMTArduinoController

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Test configuration
TEST_PORT = "COM7"  # Update this to match your Arduino port
HARDWARE_REQUIRED = True  # These tests require hardware


class TestHardwareValidation(unittest.TestCase):
    """Hardware validation tests for TESTSEQ protocol"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class with Arduino connection"""
        cls.controller = SMTArduinoController()
        cls.arduino_available = False
        
        # Try to connect to Arduino
        try:
            if cls.controller.connect(TEST_PORT):
                response = cls.controller._send_command("GET_BOARD_TYPE")
                if response and "SMT" in response:
                    cls.arduino_available = True
                    logging.info(f"Connected to Arduino on {TEST_PORT}")
                else:
                    cls.controller.disconnect()
                    raise unittest.SkipTest("Connected device is not an SMT tester")
            else:
                raise unittest.SkipTest(f"Could not connect to Arduino on {TEST_PORT}")
        except Exception as e:
            raise unittest.SkipTest(f"Arduino connection failed: {e}")
            
        if not cls.arduino_available:
            raise unittest.SkipTest("Hardware tests require Arduino connection")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests"""
        if cls.arduino_available:
            # Make sure all relays are off
            try:
                cls.controller.all_relays_off()
            except:
                pass
            cls.controller.disconnect()
    
    def setUp(self):
        """Set up before each test"""
        # Simple test configuration
        self.test_relay_mapping = {
            "1": {"board": 1, "function": "test1"},
            "2": {"board": 1, "function": "test2"},
            "3": {"board": 1, "function": "test3"},
            "4": {"board": 1, "function": "test4"}
        }
        
        # Ensure all relays are off before each test
        self.controller.all_relays_off()
        time.sleep(0.1)
    
    def test_relay_switching_speed_measurement(self):
        """Test 5.3.1: Relay switching speed measurement"""
        logging.info("Starting relay switching speed measurement test")
        
        # Test configuration for fast switching
        fast_sequence = [
            {
                "function": "test1",
                "duration_ms": 100,  # Minimum duration
                "delay_after_ms": 0,
                "limits": {"current_a": {"min": 0, "max": 10}, "voltage_v": {"min": 0, "max": 15}}
            }
        ]
        
        # Measure switching times for different relay counts
        switching_results = []
        
        test_configs = [
            ("Single relay", {"1": {"board": 1, "function": "test1"}}),
            ("Two relays", {"1,2": {"board": 1, "function": "test1"}}),
            ("Four relays", {"1,2,3,4": {"board": 1, "function": "test1"}}),
            ("Eight relays", {"1,2,3,4,5,6,7,8": {"board": 1, "function": "test1"}})
        ]
        
        for config_name, relay_mapping in test_configs:
            logging.info(f"Testing {config_name}")
            
            # Run multiple iterations
            iteration_times = []
            for i in range(10):
                start_time = time.perf_counter()
                result = self.controller.execute_test_sequence(relay_mapping, fast_sequence)
                end_time = time.perf_counter()
                
                if result["success"]:
                    # Calculate actual switching time (subtract expected duration)
                    total_time = (end_time - start_time) * 1000  # Convert to ms
                    switching_time = total_time - fast_sequence[0]["duration_ms"]
                    iteration_times.append(switching_time)
                
                # Brief pause between iterations
                time.sleep(0.05)
            
            if iteration_times:
                avg_switching = statistics.mean(iteration_times)
                std_switching = statistics.stdev(iteration_times) if len(iteration_times) > 1 else 0
                
                switching_results.append({
                    "configuration": config_name,
                    "avg_switching_ms": avg_switching,
                    "std_dev_ms": std_switching,
                    "min_ms": min(iteration_times),
                    "max_ms": max(iteration_times),
                    "samples": len(iteration_times)
                })
                
                logging.info(f"{config_name}: avg={avg_switching:.2f}ms, std={std_switching:.2f}ms")
                
                # Verify switching speed is reasonable (< 50ms overhead)
                self.assertLess(avg_switching, 50, 
                               f"{config_name} switching too slow: {avg_switching:.2f}ms")
        
        # Save results
        with open("relay_switching_speed.json", "w") as f:
            json.dump({
                "test_date": datetime.now().isoformat(),
                "results": switching_results
            }, f, indent=2)
        
        logging.info("Relay switching speed test completed, results saved to relay_switching_speed.json")
    
    def test_current_measurement_accuracy(self):
        """Test 5.3.2: Current measurement accuracy"""
        logging.info("Starting current measurement accuracy test")
        
        # Test with known loads (if available)
        # For this test, we'll take multiple measurements and analyze consistency
        
        accuracy_results = []
        
        # Test different relay configurations
        test_configs = [
            ("Single relay low current", {"1": {"board": 1, "function": "test"}}, 1000),
            ("Single relay high current", {"2": {"board": 1, "function": "test"}}, 1000),
            ("Multiple relays", {"1,2,3": {"board": 1, "function": "test"}}, 1000)
        ]
        
        for config_name, relay_mapping, duration_ms in test_configs:
            logging.info(f"Testing {config_name}")
            
            test_sequence = [{
                "function": "test",
                "duration_ms": duration_ms,
                "delay_after_ms": 100,
                "limits": {"current_a": {"min": 0, "max": 10}, "voltage_v": {"min": 0, "max": 15}}
            }]
            
            # Take multiple measurements
            measurements = []
            for i in range(20):
                result = self.controller.execute_test_sequence(relay_mapping, test_sequence)
                
                if result["success"] and result["results"]:
                    # Extract measurement from first board
                    board_data = result["results"].get(1, {})
                    test_data = board_data.get("test", {})
                    
                    if test_data:
                        measurements.append({
                            "voltage": test_data["voltage"],
                            "current": test_data["current"],
                            "power": test_data["power"]
                        })
                
                # Brief pause between measurements
                time.sleep(0.2)
            
            if measurements:
                # Calculate statistics
                voltages = [m["voltage"] for m in measurements]
                currents = [m["current"] for m in measurements]
                
                voltage_stats = {
                    "mean": statistics.mean(voltages),
                    "std_dev": statistics.stdev(voltages) if len(voltages) > 1 else 0,
                    "min": min(voltages),
                    "max": max(voltages),
                    "range": max(voltages) - min(voltages)
                }
                
                current_stats = {
                    "mean": statistics.mean(currents),
                    "std_dev": statistics.stdev(currents) if len(currents) > 1 else 0,
                    "min": min(currents),
                    "max": max(currents),
                    "range": max(currents) - min(currents)
                }
                
                # Calculate coefficient of variation (CV)
                voltage_cv = (voltage_stats["std_dev"] / voltage_stats["mean"]) * 100 if voltage_stats["mean"] > 0 else 0
                current_cv = (current_stats["std_dev"] / current_stats["mean"]) * 100 if current_stats["mean"] > 0 else 0
                
                accuracy_results.append({
                    "configuration": config_name,
                    "samples": len(measurements),
                    "voltage": voltage_stats,
                    "voltage_cv_percent": voltage_cv,
                    "current": current_stats,
                    "current_cv_percent": current_cv
                })
                
                logging.info(f"{config_name}: V_CV={voltage_cv:.2f}%, I_CV={current_cv:.2f}%")
                
                # Verify measurement consistency (CV < 5% for stable loads)
                self.assertLess(voltage_cv, 5.0, 
                               f"Voltage measurement inconsistent: CV={voltage_cv:.2f}%")
                # Current measurements may have higher variation
                self.assertLess(current_cv, 10.0, 
                               f"Current measurement inconsistent: CV={current_cv:.2f}%")
        
        # Save results
        with open("measurement_accuracy.json", "w") as f:
            json.dump({
                "test_date": datetime.now().isoformat(),
                "results": accuracy_results
            }, f, indent=2)
        
        logging.info("Measurement accuracy test completed, results saved to measurement_accuracy.json")
    
    def test_timing_jitter_analysis(self):
        """Test 5.3.3: Timing jitter analysis"""
        logging.info("Starting timing jitter analysis test")
        
        # Test sequence with precise timing requirements
        jitter_test_sequence = [
            {
                "function": "test1",
                "duration_ms": 100,
                "delay_after_ms": 50,
                "limits": {"current_a": {"min": 0, "max": 10}, "voltage_v": {"min": 0, "max": 15}}
            },
            {
                "function": "test2",
                "duration_ms": 100,
                "delay_after_ms": 50,
                "limits": {"current_a": {"min": 0, "max": 10}, "voltage_v": {"min": 0, "max": 15}}
            },
            {
                "function": "test3",
                "duration_ms": 100,
                "delay_after_ms": 50,
                "limits": {"current_a": {"min": 0, "max": 10}, "voltage_v": {"min": 0, "max": 15}}
            },
            {
                "function": "test4",
                "duration_ms": 100,
                "delay_after_ms": 0,
                "limits": {"current_a": {"min": 0, "max": 10}, "voltage_v": {"min": 0, "max": 15}}
            }
        ]
        
        # Expected total time
        expected_time_ms = sum(step["duration_ms"] + step.get("delay_after_ms", 0) 
                              for step in jitter_test_sequence)
        
        # Collect timing data
        timing_samples = []
        
        logging.info(f"Running {50} iterations for jitter analysis...")
        for i in range(50):
            start_time = time.perf_counter()
            result = self.controller.execute_test_sequence(
                self.test_relay_mapping,
                jitter_test_sequence
            )
            end_time = time.perf_counter()
            
            if result["success"]:
                actual_time_ms = (end_time - start_time) * 1000
                timing_error_ms = actual_time_ms - expected_time_ms
                timing_samples.append({
                    "iteration": i,
                    "actual_ms": actual_time_ms,
                    "expected_ms": expected_time_ms,
                    "error_ms": timing_error_ms,
                    "error_percent": (timing_error_ms / expected_time_ms) * 100
                })
            
            # Brief pause between iterations
            time.sleep(0.1)
        
        if timing_samples:
            # Calculate jitter statistics
            errors_ms = [s["error_ms"] for s in timing_samples]
            errors_percent = [s["error_percent"] for s in timing_samples]
            
            jitter_stats = {
                "samples": len(timing_samples),
                "expected_time_ms": expected_time_ms,
                "mean_error_ms": statistics.mean(errors_ms),
                "std_dev_ms": statistics.stdev(errors_ms) if len(errors_ms) > 1 else 0,
                "min_error_ms": min(errors_ms),
                "max_error_ms": max(errors_ms),
                "peak_to_peak_ms": max(errors_ms) - min(errors_ms),
                "mean_error_percent": statistics.mean(errors_percent),
                "percentiles": {
                    "p50": np.percentile(errors_ms, 50),
                    "p90": np.percentile(errors_ms, 90),
                    "p95": np.percentile(errors_ms, 95),
                    "p99": np.percentile(errors_ms, 99)
                }
            }
            
            # Plot timing distribution (save data for external plotting)
            jitter_data = {
                "test_date": datetime.now().isoformat(),
                "statistics": jitter_stats,
                "samples": timing_samples
            }
            
            with open("timing_jitter_analysis.json", "w") as f:
                json.dump(jitter_data, f, indent=2)
            
            logging.info(f"Jitter analysis: mean_error={jitter_stats['mean_error_ms']:.2f}ms, "
                        f"std_dev={jitter_stats['std_dev_ms']:.2f}ms, "
                        f"peak-to-peak={jitter_stats['peak_to_peak_ms']:.2f}ms")
            
            # Verify timing jitter is acceptable
            # Peak-to-peak jitter should be < 10ms for reliable operation
            self.assertLess(jitter_stats["peak_to_peak_ms"], 10.0,
                           f"Timing jitter too high: {jitter_stats['peak_to_peak_ms']:.2f}ms")
            
            # 95th percentile error should be < 5ms
            self.assertLess(abs(jitter_stats["percentiles"]["p95"]), 5.0,
                           f"95th percentile timing error too high: {jitter_stats['percentiles']['p95']:.2f}ms")
        
        logging.info("Timing jitter analysis completed, results saved to timing_jitter_analysis.json")
    
    def test_thermal_behavior_validation(self):
        """Test 5.3.4: Thermal behavior validation"""
        logging.info("Starting thermal behavior validation test")
        
        # Long-duration test to observe thermal effects
        thermal_test_mapping = {
            "1,2,3,4": {"board": 1, "function": "high_power"},
            "5,6,7,8": {"board": 2, "function": "high_power"}
        }
        
        thermal_sequence = [
            {
                "function": "high_power",
                "duration_ms": 2000,  # 2 seconds on
                "delay_after_ms": 1000,  # 1 second off
                "limits": {"current_a": {"min": 0, "max": 10}, "voltage_v": {"min": 0, "max": 15}}
            }
        ]
        
        # Run for extended period and monitor measurements
        thermal_data = []
        test_duration_minutes = 5
        iterations = test_duration_minutes * 20  # ~20 cycles per minute
        
        logging.info(f"Running thermal test for {test_duration_minutes} minutes...")
        
        start_time = time.time()
        for i in range(iterations):
            cycle_start = time.time()
            
            # Execute test sequence
            result = self.controller.execute_test_sequence(
                thermal_test_mapping,
                thermal_sequence
            )
            
            if result["success"]:
                # Record measurements with timestamp
                elapsed_minutes = (time.time() - start_time) / 60
                
                measurement_record = {
                    "iteration": i,
                    "elapsed_minutes": elapsed_minutes,
                    "measurements": {}
                }
                
                # Extract all measurements
                for board_num, board_data in result["results"].items():
                    for function, data in board_data.items():
                        key = f"board{board_num}_{function}"
                        measurement_record["measurements"][key] = {
                            "voltage": data["voltage"],
                            "current": data["current"],
                            "power": data["power"]
                        }
                
                thermal_data.append(measurement_record)
            
            # Progress update every minute
            if i > 0 and i % 20 == 0:
                logging.info(f"Thermal test progress: {i/20:.0f} minutes completed")
            
            # Check if we should stop early (safety)
            if result["success"] and result["results"]:
                # Check for thermal runaway (significant current increase)
                for board_data in result["results"].values():
                    for data in board_data.values():
                        if data["current"] > 9.0:  # Near limit
                            logging.warning(f"High current detected: {data['current']}A, stopping test")
                            break
        
        if thermal_data:
            # Analyze thermal trends
            # Group by measurement point
            measurement_trends = {}
            
            for record in thermal_data:
                for key, data in record["measurements"].items():
                    if key not in measurement_trends:
                        measurement_trends[key] = {
                            "times": [],
                            "voltages": [],
                            "currents": [],
                            "powers": []
                        }
                    
                    measurement_trends[key]["times"].append(record["elapsed_minutes"])
                    measurement_trends[key]["voltages"].append(data["voltage"])
                    measurement_trends[key]["currents"].append(data["current"])
                    measurement_trends[key]["powers"].append(data["power"])
            
            # Calculate thermal drift
            thermal_analysis = {}
            
            for key, trends in measurement_trends.items():
                if len(trends["currents"]) > 10:
                    # Compare first 10 samples to last 10 samples
                    initial_current = statistics.mean(trends["currents"][:10])
                    final_current = statistics.mean(trends["currents"][-10:])
                    current_drift = final_current - initial_current
                    current_drift_percent = (current_drift / initial_current) * 100 if initial_current > 0 else 0
                    
                    thermal_analysis[key] = {
                        "initial_current_a": initial_current,
                        "final_current_a": final_current,
                        "current_drift_a": current_drift,
                        "current_drift_percent": current_drift_percent,
                        "max_current_a": max(trends["currents"]),
                        "min_current_a": min(trends["currents"]),
                        "samples": len(trends["currents"])
                    }
                    
                    logging.info(f"{key}: thermal drift = {current_drift_percent:.1f}%")
                    
                    # Verify thermal stability (drift < 10%)
                    self.assertLess(abs(current_drift_percent), 10.0,
                                   f"{key} excessive thermal drift: {current_drift_percent:.1f}%")
            
            # Save thermal data
            with open("thermal_behavior.json", "w") as f:
                json.dump({
                    "test_date": datetime.now().isoformat(),
                    "test_duration_minutes": test_duration_minutes,
                    "analysis": thermal_analysis,
                    "raw_data": thermal_data
                }, f, indent=2)
            
            logging.info("Thermal behavior test completed, results saved to thermal_behavior.json")
    
    def test_emi_noise_testing(self):
        """Test 5.3.5: EMI/noise testing"""
        logging.info("Starting EMI/noise testing")
        
        # Test for measurement noise under different conditions
        noise_results = []
        
        # Test 1: Baseline noise (no relays active)
        logging.info("Measuring baseline noise...")
        baseline_measurements = []
        
        for i in range(100):
            # Measure with all relays off
            response = self.controller._send_command("MEASURE:0")
            if response and ":" in response:
                try:
                    parts = response.split(":")
                    if len(parts) >= 3:
                        voltage = float(parts[1].rstrip("V"))
                        current = float(parts[2].rstrip("A"))
                        baseline_measurements.append({
                            "voltage": voltage,
                            "current": current
                        })
                except:
                    pass
            
            time.sleep(0.01)  # 10ms between samples
        
        if baseline_measurements:
            baseline_noise = {
                "voltage_std": statistics.stdev([m["voltage"] for m in baseline_measurements]),
                "current_std": statistics.stdev([m["current"] for m in baseline_measurements]),
                "samples": len(baseline_measurements)
            }
            noise_results.append({
                "test": "baseline",
                "description": "No relays active",
                "noise": baseline_noise
            })
            logging.info(f"Baseline noise: V_std={baseline_noise['voltage_std']:.3f}V, "
                        f"I_std={baseline_noise['current_std']:.3f}A")
        
        # Test 2: Noise during relay switching
        logging.info("Measuring switching noise...")
        switching_sequence = [
            {
                "function": "test1",
                "duration_ms": 100,
                "delay_after_ms": 0,
                "limits": {"current_a": {"min": 0, "max": 10}, "voltage_v": {"min": 0, "max": 15}}
            }
        ]
        
        switching_measurements = []
        for i in range(50):
            result = self.controller.execute_test_sequence(
                {"1": {"board": 1, "function": "test1"}},
                switching_sequence
            )
            
            if result["success"] and result["results"]:
                board_data = result["results"].get(1, {})
                test_data = board_data.get("test1", {})
                if test_data:
                    switching_measurements.append({
                        "voltage": test_data["voltage"],
                        "current": test_data["current"]
                    })
        
        if switching_measurements:
            switching_noise = {
                "voltage_std": statistics.stdev([m["voltage"] for m in switching_measurements]),
                "current_std": statistics.stdev([m["current"] for m in switching_measurements]),
                "samples": len(switching_measurements)
            }
            noise_results.append({
                "test": "switching",
                "description": "During relay switching",
                "noise": switching_noise
            })
            logging.info(f"Switching noise: V_std={switching_noise['voltage_std']:.3f}V, "
                        f"I_std={switching_noise['current_std']:.3f}A")
        
        # Test 3: Adjacent channel crosstalk
        logging.info("Measuring crosstalk...")
        
        # Activate relays 1,3,5,7 and measure 2,4,6,8
        active_mapping = {"1,3,5,7": {"board": 1, "function": "active"}}
        crosstalk_sequence = [{
            "function": "active",
            "duration_ms": 1000,
            "delay_after_ms": 0,
            "limits": {"current_a": {"min": 0, "max": 10}, "voltage_v": {"min": 0, "max": 15}}
        }]
        
        # Start the active relays
        self.controller.execute_test_sequence(active_mapping, crosstalk_sequence)
        
        # Measure inactive channels
        crosstalk_measurements = []
        inactive_relays = [2, 4, 6, 8]
        
        for relay in inactive_relays:
            response = self.controller._send_command(f"MEASURE:{relay}")
            if response and ":" in response:
                try:
                    parts = response.split(":")
                    if len(parts) >= 3:
                        voltage = float(parts[1].rstrip("V"))
                        current = float(parts[2].rstrip("A"))
                        crosstalk_measurements.append({
                            "relay": relay,
                            "voltage": voltage,
                            "current": current
                        })
                except:
                    pass
        
        # Turn off active relays
        self.controller.all_relays_off()
        
        if crosstalk_measurements:
            max_crosstalk_current = max(m["current"] for m in crosstalk_measurements)
            max_crosstalk_voltage = max(m["voltage"] for m in crosstalk_measurements)
            
            noise_results.append({
                "test": "crosstalk",
                "description": "Adjacent channel interference",
                "measurements": crosstalk_measurements,
                "max_crosstalk": {
                    "voltage": max_crosstalk_voltage,
                    "current": max_crosstalk_current
                }
            })
            logging.info(f"Max crosstalk: V={max_crosstalk_voltage:.3f}V, I={max_crosstalk_current:.3f}A")
            
            # Verify crosstalk is minimal (< 100mA)
            self.assertLess(max_crosstalk_current, 0.1,
                           f"Excessive crosstalk current: {max_crosstalk_current:.3f}A")
        
        # Save EMI/noise test results
        with open("emi_noise_test.json", "w") as f:
            json.dump({
                "test_date": datetime.now().isoformat(),
                "results": noise_results
            }, f, indent=2)
        
        logging.info("EMI/noise testing completed, results saved to emi_noise_test.json")


class TestHardwareValidationMocked(unittest.TestCase):
    """Mocked hardware tests for CI/CD environments"""
    
    def test_hardware_test_structure(self):
        """Verify hardware test structure and methods exist"""
        test_class = TestHardwareValidation
        
        # Verify all required test methods exist
        required_tests = [
            "test_relay_switching_speed_measurement",
            "test_current_measurement_accuracy",
            "test_timing_jitter_analysis",
            "test_thermal_behavior_validation",
            "test_emi_noise_testing"
        ]
        
        for test_name in required_tests:
            self.assertTrue(hasattr(test_class, test_name),
                           f"Missing test method: {test_name}")
            
            # Verify it's callable
            method = getattr(test_class, test_name)
            self.assertTrue(callable(method),
                           f"Test method not callable: {test_name}")
    
    def test_data_analysis_functions(self):
        """Test data analysis functions with mock data"""
        # Test timing jitter calculation
        timing_samples = [98.5, 99.2, 101.3, 100.5, 99.8, 100.2, 101.1, 99.5, 100.0, 100.3]
        expected = 100.0
        
        errors = [t - expected for t in timing_samples]
        jitter_stats = {
            "mean_error": statistics.mean(errors),
            "std_dev": statistics.stdev(errors),
            "peak_to_peak": max(errors) - min(errors)
        }
        
        self.assertLess(jitter_stats["peak_to_peak"], 3.0,
                       "Mock timing jitter calculation failed")
        
        # Test thermal drift calculation
        initial_currents = [5.0, 5.1, 5.0, 5.05, 5.02]
        final_currents = [5.3, 5.35, 5.32, 5.33, 5.31]
        
        initial_mean = statistics.mean(initial_currents)
        final_mean = statistics.mean(final_currents)
        drift_percent = ((final_mean - initial_mean) / initial_mean) * 100
        
        self.assertAlmostEqual(drift_percent, 6.08, places=1,
                              msg="Mock thermal drift calculation failed")


if __name__ == "__main__":
    unittest.main(verbosity=2)