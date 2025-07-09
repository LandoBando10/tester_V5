#!/usr/bin/env python3
"""
Integration tests for TESTSEQ protocol implementation
Tests full sequence execution, timing precision, current limits, error recovery, and performance

This test suite requires a connected Arduino with firmware v2.0.0+
If no Arduino is connected, tests will be skipped with appropriate messages.
"""

import unittest
import time
import logging
import json
import statistics
from typing import Dict, List, Tuple
from unittest.mock import Mock, patch
from src.hardware.smt_arduino_controller import SMTArduinoController

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Test configuration
TEST_PORT = "COM7"  # Update this to match your Arduino port
ARDUINO_REQUIRED = False  # Set to True to require real hardware for tests


class TestTESTSEQIntegration(unittest.TestCase):
    """Integration tests for TESTSEQ protocol implementation"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class with Arduino connection check"""
        cls.controller = SMTArduinoController()
        cls.arduino_available = False
        
        # Try to connect to real Arduino
        try:
            if cls.controller.connect(TEST_PORT):
                # Verify it's an SMT tester
                response = cls.controller._send_command("GET_BOARD_TYPE")
                if response and "SMT" in response:
                    cls.arduino_available = True
                    logging.info(f"Connected to Arduino on {TEST_PORT}")
                else:
                    cls.controller.disconnect()
                    logging.warning("Connected device is not an SMT tester")
            else:
                logging.warning(f"Could not connect to Arduino on {TEST_PORT}")
        except Exception as e:
            logging.warning(f"Arduino connection failed: {e}")
            
        if ARDUINO_REQUIRED and not cls.arduino_available:
            raise unittest.SkipTest("Arduino hardware required but not available")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests"""
        if cls.arduino_available:
            cls.controller.disconnect()
    
    def setUp(self):
        """Set up before each test"""
        self.test_relay_mapping = {
            "1,2,3": {"board": 1, "function": "mainbeam"},
            "4": {"board": 1, "function": "position"},
            "5,6": {"board": 1, "function": "turn_signal"},
            "7,8,9": {"board": 2, "function": "mainbeam"},
            "10": {"board": 2, "function": "position"},
            "11,12": {"board": 2, "function": "turn_signal"}
        }
        
        self.test_sequence = [
            {
                "function": "mainbeam",
                "duration_ms": 500,
                "delay_after_ms": 100,
                "limits": {
                    "current_a": {"min": 5.4, "max": 6.9},
                    "voltage_v": {"min": 11.5, "max": 12.5}
                }
            },
            {
                "function": "position",
                "duration_ms": 300,
                "delay_after_ms": 100,
                "limits": {
                    "current_a": {"min": 0.8, "max": 1.2},
                    "voltage_v": {"min": 11.5, "max": 12.5}
                }
            },
            {
                "function": "turn_signal",
                "duration_ms": 400,
                "delay_after_ms": 0,
                "limits": {
                    "current_a": {"min": 1.5, "max": 2.5},
                    "voltage_v": {"min": 11.5, "max": 12.5}
                }
            }
        ]
    
    def test_full_sequence_execution(self):
        """Test 5.2.1: Full sequence execution tests"""
        if not self.arduino_available:
            self.skipTest("Arduino hardware not available")
        
        # Execute complete test sequence
        start_time = time.time()
        result = self.controller.execute_test_sequence(
            self.test_relay_mapping, 
            self.test_sequence
        )
        execution_time = time.time() - start_time
        
        # Verify success
        self.assertTrue(result["success"], f"Test failed: {result.get('errors', [])}")
        
        # Verify all boards and functions are present
        results = result["results"]
        self.assertIn(1, results, "Board 1 missing from results")
        self.assertIn(2, results, "Board 2 missing from results")
        
        # Verify all functions tested for each board
        for board_num in [1, 2]:
            board_results = results[board_num]
            self.assertIn("mainbeam", board_results)
            self.assertIn("position", board_results)
            self.assertIn("turn_signal", board_results)
            
            # Verify measurement structure
            for function, data in board_results.items():
                self.assertIn("voltage", data)
                self.assertIn("current", data)
                self.assertIn("power", data)
                self.assertIsInstance(data["voltage"], (int, float))
                self.assertIsInstance(data["current"], (int, float))
                self.assertIsInstance(data["power"], (int, float))
        
        # Verify execution time is reasonable
        expected_time = sum(step["duration_ms"] + step.get("delay_after_ms", 0) 
                           for step in self.test_sequence) / 1000.0
        # Allow 50% overhead for communication and processing
        self.assertLess(execution_time, expected_time * 1.5,
                       f"Execution took {execution_time:.2f}s, expected ~{expected_time:.2f}s")
        
        logging.info(f"Full sequence execution completed in {execution_time:.2f}s")
    
    def test_timing_precision_validation(self):
        """Test 5.2.2: Timing precision validation"""
        if not self.arduino_available:
            self.skipTest("Arduino hardware not available")
        
        # Test with precise timing requirements
        timing_test_sequence = [
            {
                "function": "mainbeam",
                "duration_ms": 100,  # Minimum duration
                "delay_after_ms": 50,
                "limits": {"current_a": {"min": 0, "max": 10}, "voltage_v": {"min": 0, "max": 15}}
            },
            {
                "function": "position", 
                "duration_ms": 200,
                "delay_after_ms": 100,
                "limits": {"current_a": {"min": 0, "max": 10}, "voltage_v": {"min": 0, "max": 15}}
            },
            {
                "function": "turn_signal",
                "duration_ms": 500,
                "delay_after_ms": 0,
                "limits": {"current_a": {"min": 0, "max": 10}, "voltage_v": {"min": 0, "max": 15}}
            }
        ]
        
        # Run multiple iterations to measure timing consistency
        timings = []
        for i in range(5):
            start_time = time.time()
            result = self.controller.execute_test_sequence(
                self.test_relay_mapping,
                timing_test_sequence
            )
            execution_time = time.time() - start_time
            
            self.assertTrue(result["success"], f"Iteration {i+1} failed")
            timings.append(execution_time)
            
            # Small delay between iterations
            time.sleep(0.5)
        
        # Calculate timing statistics
        expected_time = sum(step["duration_ms"] + step.get("delay_after_ms", 0) 
                           for step in timing_test_sequence) / 1000.0
        
        avg_time = statistics.mean(timings)
        std_dev = statistics.stdev(timings) if len(timings) > 1 else 0
        
        # Verify average timing is within 10% of expected
        timing_error = abs(avg_time - expected_time) / expected_time
        self.assertLess(timing_error, 0.1, 
                       f"Average timing {avg_time:.3f}s differs from expected {expected_time:.3f}s by {timing_error*100:.1f}%")
        
        # Verify timing consistency (standard deviation < 5% of average)
        if std_dev > 0:
            cv = std_dev / avg_time  # Coefficient of variation
            self.assertLess(cv, 0.05,
                           f"Timing inconsistent: CV={cv:.3f} (std={std_dev:.3f}s)")
        
        logging.info(f"Timing precision: avg={avg_time:.3f}s, std={std_dev:.3f}s, expected={expected_time:.3f}s")
    
    def test_current_limit_enforcement(self):
        """Test 5.2.3: Current limit enforcement"""
        # This test validates the measurement against specified limits
        # Since we can't control actual current draw without hardware, we'll test the validation logic
        
        # Test with mock data that exceeds limits
        test_response = "TESTRESULTS:1,2,3:12.5V,7.5A;4:12.5V,1.5A;5,6:12.5V,3.0A;END"
        
        # Parse the response
        relay_groups = self.controller._parse_relay_mapping(self.test_relay_mapping)
        results = self.controller._parse_testresults(test_response, relay_groups, self.test_sequence)
        
        # Validate measurements against limits
        failures = []
        for board_num, board_results in results.items():
            for function, measurement in board_results.items():
                # Find limits for this function
                limits = None
                for step in self.test_sequence:
                    if step["function"] == function:
                        limits = step.get("limits", {})
                        break
                
                if limits:
                    # Check current limits
                    current_limits = limits.get("current_a", {})
                    if "min" in current_limits and measurement["current"] < current_limits["min"]:
                        failures.append(f"Board {board_num} {function}: current {measurement['current']}A below min {current_limits['min']}A")
                    if "max" in current_limits and measurement["current"] > current_limits["max"]:
                        failures.append(f"Board {board_num} {function}: current {measurement['current']}A above max {current_limits['max']}A")
                    
                    # Check voltage limits
                    voltage_limits = limits.get("voltage_v", {})
                    if "min" in voltage_limits and measurement["voltage"] < voltage_limits["min"]:
                        failures.append(f"Board {board_num} {function}: voltage {measurement['voltage']}V below min {voltage_limits['min']}V")
                    if "max" in voltage_limits and measurement["voltage"] > voltage_limits["max"]:
                        failures.append(f"Board {board_num} {function}: voltage {measurement['voltage']}V above max {voltage_limits['max']}V")
        
        # We expect some failures with the test data
        self.assertGreater(len(failures), 0, "Expected current limit violations not detected")
        
        # Verify specific expected failures
        mainbeam_failure = any("mainbeam" in f and "7.5A above max 6.9A" in f for f in failures)
        self.assertTrue(mainbeam_failure, "Mainbeam overcurrent not detected")
        
        position_failure = any("position" in f and "1.5A above max 1.2A" in f for f in failures)
        self.assertTrue(position_failure, "Position overcurrent not detected")
        
        turn_signal_failure = any("turn_signal" in f and "3.0A above max 2.5A" in f for f in failures)
        self.assertTrue(turn_signal_failure, "Turn signal overcurrent not detected")
        
        logging.info(f"Current limit enforcement detected {len(failures)} violations")
    
    def test_error_recovery_scenarios(self):
        """Test 5.2.4: Error recovery scenarios"""
        # Test various error conditions and recovery
        
        # Test 1: Invalid relay numbers
        bad_mapping = {
            "17,18": {"board": 1, "function": "test"},  # Invalid relay numbers
            "1,1,1": {"board": 1, "function": "duplicate"}  # Duplicate relay in group
        }
        
        errors = self.controller._validate_testseq_command(
            self.controller._parse_relay_mapping(bad_mapping),
            self.test_sequence[:1]
        )
        
        self.assertGreater(len(errors), 0, "Invalid relay numbers not detected")
        self.assertTrue(any("Invalid relay number: 17" in e for e in errors))
        self.assertTrue(any("Invalid relay number: 18" in e for e in errors))
        
        # Test 2: Relay overlap between groups
        overlap_mapping = {
            "1,2,3": {"board": 1, "function": "mainbeam"},
            "3,4,5": {"board": 1, "function": "position"}  # Relay 3 appears twice
        }
        
        errors = self.controller._validate_testseq_command(
            self.controller._parse_relay_mapping(overlap_mapping),
            self.test_sequence[:1]
        )
        
        self.assertTrue(any("Relay 3 appears in multiple groups" in e for e in errors))
        
        # Test 3: Timing violations
        bad_timing_sequence = [
            {
                "function": "mainbeam",
                "duration_ms": 50,  # Too short (min 100ms)
                "delay_after_ms": 0,
                "limits": {}
            }
        ]
        
        errors = self.controller._validate_testseq_command(
            self.controller._parse_relay_mapping(self.test_relay_mapping),
            bad_timing_sequence
        )
        
        self.assertTrue(any("50ms too short" in e for e in errors))
        
        # Test 4: Sequence timeout
        timeout_sequence = [
            {
                "function": "mainbeam",
                "duration_ms": 15000,  # 15 seconds
                "delay_after_ms": 16000,  # 16 seconds (total 31s > 30s limit)
                "limits": {}
            }
        ]
        
        errors = self.controller._validate_testseq_command(
            self.controller._parse_relay_mapping(self.test_relay_mapping),
            timeout_sequence
        )
        
        self.assertTrue(any("exceeds 30 second limit" in e for e in errors))
        
        # Test 5: Recovery from communication error (if hardware available)
        if self.arduino_available:
            # Save original timeout
            original_timeout = self.controller.command_timeout
            
            # Set very short timeout to force error
            self.controller.command_timeout = 0.001
            
            result = self.controller.execute_test_sequence(
                self.test_relay_mapping,
                self.test_sequence[:1]  # Just one step
            )
            
            # Should fail due to timeout
            self.assertFalse(result["success"])
            self.assertGreater(len(result["errors"]), 0)
            
            # Restore timeout and verify recovery
            self.controller.command_timeout = original_timeout
            
            # Should work again
            result = self.controller.execute_test_sequence(
                self.test_relay_mapping,
                self.test_sequence[:1]
            )
            
            self.assertTrue(result["success"], "Failed to recover from timeout error")
        
        logging.info("Error recovery scenarios completed successfully")
    
    def test_performance_benchmarks(self):
        """Test 5.2.5: Performance benchmarks"""
        if not self.arduino_available:
            self.skipTest("Arduino hardware not available")
        
        # Benchmark different sequence complexities
        benchmarks = []
        
        # Simple sequence (1 function, 2 boards)
        simple_sequence = [{
            "function": "mainbeam",
            "duration_ms": 100,
            "delay_after_ms": 0,
            "limits": {"current_a": {"min": 0, "max": 10}, "voltage_v": {"min": 0, "max": 15}}
        }]
        
        # Complex sequence (3 functions, 2 boards, with delays)
        complex_sequence = self.test_sequence
        
        # Maximum complexity (all relays)
        max_relay_mapping = {
            "1,2,3,4": {"board": 1, "function": "group1"},
            "5,6,7,8": {"board": 1, "function": "group2"},
            "9,10,11,12": {"board": 2, "function": "group1"},
            "13,14,15,16": {"board": 2, "function": "group2"}
        }
        
        max_sequence = [
            {
                "function": "group1",
                "duration_ms": 200,
                "delay_after_ms": 50,
                "limits": {"current_a": {"min": 0, "max": 10}, "voltage_v": {"min": 0, "max": 15}}
            },
            {
                "function": "group2",
                "duration_ms": 200,
                "delay_after_ms": 0,
                "limits": {"current_a": {"min": 0, "max": 10}, "voltage_v": {"min": 0, "max": 15}}
            }
        ]
        
        # Run benchmarks
        test_configs = [
            ("Simple", self.test_relay_mapping, simple_sequence),
            ("Complex", self.test_relay_mapping, complex_sequence),
            ("Maximum", max_relay_mapping, max_sequence)
        ]
        
        for name, mapping, sequence in test_configs:
            # Warm-up run
            self.controller.execute_test_sequence(mapping, sequence)
            
            # Timed runs
            times = []
            for _ in range(3):
                start = time.time()
                result = self.controller.execute_test_sequence(mapping, sequence)
                elapsed = time.time() - start
                
                if result["success"]:
                    times.append(elapsed)
                
                time.sleep(0.2)  # Brief pause between runs
            
            if times:
                avg_time = statistics.mean(times)
                expected = sum(s["duration_ms"] + s.get("delay_after_ms", 0) for s in sequence) / 1000.0
                overhead = avg_time - expected
                overhead_pct = (overhead / expected) * 100 if expected > 0 else 0
                
                benchmarks.append({
                    "name": name,
                    "avg_time": avg_time,
                    "expected": expected,
                    "overhead": overhead,
                    "overhead_pct": overhead_pct
                })
                
                logging.info(f"{name} benchmark: {avg_time:.3f}s (expected {expected:.3f}s, overhead {overhead_pct:.1f}%)")
        
        # Verify performance meets targets
        for benchmark in benchmarks:
            # Communication overhead should be < 100ms per step
            steps = len(sequence)
            max_overhead = steps * 0.1  # 100ms per step
            self.assertLess(benchmark["overhead"], max_overhead,
                           f"{benchmark['name']} overhead {benchmark['overhead']:.3f}s exceeds limit {max_overhead:.3f}s")
        
        # Save benchmark results
        with open("testseq_benchmarks.json", "w") as f:
            json.dump(benchmarks, f, indent=2)
        
        logging.info(f"Performance benchmarks completed, results saved to testseq_benchmarks.json")


class TestTESTSEQMocked(unittest.TestCase):
    """Unit tests with mocked Arduino for CI/CD environments"""
    
    def setUp(self):
        """Set up mocked controller"""
        self.controller = SMTArduinoController()
        self.test_relay_mapping = {
            "1,2,3": {"board": 1, "function": "mainbeam"},
            "4": {"board": 1, "function": "position"}
        }
        self.test_sequence = [
            {
                "function": "mainbeam",
                "duration_ms": 500,
                "delay_after_ms": 100,
                "limits": {"current_a": {"min": 5.4, "max": 6.9}}
            }
        ]
    
    def test_command_building(self):
        """Test TESTSEQ command construction"""
        relay_groups = self.controller._parse_relay_mapping(self.test_relay_mapping)
        command = self.controller._build_testseq_command(relay_groups, self.test_sequence)
        
        # Should produce: TESTSEQ:1,2,3:500;OFF:100
        self.assertEqual(command, "TESTSEQ:1,2,3:500;OFF:100")
    
    def test_response_parsing(self):
        """Test TESTRESULTS parsing"""
        test_response = "TESTRESULTS:1,2,3:12.5V,6.8A;END"
        relay_groups = self.controller._parse_relay_mapping(self.test_relay_mapping)
        results = self.controller._parse_testresults(test_response, relay_groups, self.test_sequence)
        
        self.assertIn(1, results)
        self.assertIn("mainbeam", results[1])
        self.assertEqual(results[1]["mainbeam"]["voltage"], 12.5)
        self.assertEqual(results[1]["mainbeam"]["current"], 6.8)
        self.assertEqual(results[1]["mainbeam"]["power"], 12.5 * 6.8)
    
    def test_validation(self):
        """Test command validation"""
        # Valid configuration
        relay_groups = self.controller._parse_relay_mapping(self.test_relay_mapping)
        errors = self.controller._validate_testseq_command(relay_groups, self.test_sequence)
        self.assertEqual(len(errors), 0)
        
        # Invalid relay number
        bad_mapping = {"17": {"board": 1, "function": "test"}}
        bad_groups = self.controller._parse_relay_mapping(bad_mapping)
        errors = self.controller._validate_testseq_command(bad_groups, self.test_sequence)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("Invalid relay number: 17" in e for e in errors))
    
    @patch('serial.Serial')
    def test_execute_with_mock(self, mock_serial):
        """Test full execution with mocked serial"""
        # Configure mock
        mock_instance = Mock()
        mock_serial.return_value = mock_instance
        mock_instance.is_open = True
        mock_instance.read_until.return_value = b"TESTRESULTS:1,2,3:12.5V,6.8A;END\n"
        
        # Mock the connection process
        with patch.object(self.controller, '_test_communication', return_value=True):
            with patch.object(self.controller, '_read_startup_messages'):
                with patch.object(self.controller, 'start_reading'):
                    self.controller.connection = mock_instance
                    self.controller.port = "MOCK"
                    
                    # Execute test
                    result = self.controller.execute_test_sequence(
                        self.test_relay_mapping,
                        self.test_sequence
                    )
                    
                    # Verify success
                    self.assertTrue(result["success"])
                    self.assertIn(1, result["results"])
                    self.assertEqual(result["results"][1]["mainbeam"]["voltage"], 12.5)


if __name__ == "__main__":
    # Run with verbose output
    unittest.main(verbosity=2)