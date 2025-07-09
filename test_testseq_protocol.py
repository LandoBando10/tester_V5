#!/usr/bin/env python3
"""
Test script for TESTSEQ protocol implementation
Tests the new simultaneous relay activation features
"""

import logging
import json
from src.hardware.smt_arduino_controller import SMTArduinoController

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_testseq_protocol():
    """Test the new TESTSEQ protocol implementation"""
    
    # Example SKU configuration with comma-separated relay groups
    relay_mapping = {
        "1,2,3": {"board": 1, "function": "mainbeam"},
        "4": {"board": 1, "function": "position"},
        "5,6": {"board": 1, "function": "turn_signal"},
        "7,8,9": {"board": 2, "function": "mainbeam"},
        "10": {"board": 2, "function": "position"},
        "11,12": {"board": 2, "function": "turn_signal"},
        "13,14,15": {"board": 3, "function": "mainbeam"},
        "16": {"board": 3, "function": "position"}
    }
    
    test_sequence = [
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
            "delay_after_ms": 0,  # No delay after last step
            "limits": {
                "current_a": {"min": 1.5, "max": 2.5},
                "voltage_v": {"min": 11.5, "max": 12.5}
            }
        }
    ]
    
    # Create controller
    controller = SMTArduinoController()
    
    # Test command building without connection
    print("Testing command building...")
    relay_groups = controller._parse_relay_mapping(relay_mapping)
    command = controller._build_testseq_command(relay_groups, test_sequence)
    print(f"Generated command: {command}")
    
    # Expected: TESTSEQ:1,2,3:500;7,8,9:500;13,14,15:500;OFF:100;4:300;10:300;16:300;OFF:100;5,6:400;11,12:400
    
    # Test validation
    print("\nTesting validation...")
    errors = controller._validate_testseq_command(relay_groups, test_sequence)
    if errors:
        print(f"Validation errors: {errors}")
    else:
        print("Validation passed!")
    
    # Test with invalid relay numbers
    print("\nTesting invalid relay validation...")
    bad_mapping = {"17,18": {"board": 1, "function": "test"}}
    bad_groups = controller._parse_relay_mapping(bad_mapping)
    errors = controller._validate_testseq_command(bad_groups, test_sequence)
    print(f"Expected errors: {errors}")
    
    # Test response parsing
    print("\nTesting response parsing...")
    test_response = "TESTRESULTS:1,2,3:12.5V,6.8A;7,8,9:12.4V,6.7A;13,14,15:12.3V,6.6A;4:12.5V,1.0A;10:12.4V,0.9A;16:12.3V,0.8A;5,6:12.5V,2.0A;11,12:12.4V,1.9A;END"
    
    results = controller._parse_testresults(test_response, relay_groups, test_sequence)
    print(f"Parsed results: {json.dumps(results, indent=2)}")
    
    # Test timeout calculation
    print("\nTesting timeout calculation...")
    timeout = controller._calculate_sequence_timeout(test_sequence)
    print(f"Calculated timeout: {timeout}s")
    
    # If you want to test with real hardware, uncomment below
    # print("\nTesting with real Arduino...")
    # if controller.connect("COM7"):  # Adjust port as needed
    #     print("Connected to Arduino")
    #     
    #     # Check board type
    #     board_type = controller._send_command("GET_BOARD_TYPE")
    #     print(f"Board type: {board_type}")
    #     
    #     # Execute test sequence
    #     result = controller.execute_test_sequence(relay_mapping, test_sequence)
    #     
    #     if result["success"]:
    #         print("\nTest successful!")
    #         for board, functions in result["results"].items():
    #             print(f"\nBoard {board}:")
    #             for function, data in functions.items():
    #                 print(f"  {function}: {data['voltage']:.1f}V, {data['current']:.1f}A, {data['power']:.1f}W")
    #     else:
    #         print(f"\nTest failed: {result['errors']}")
    #     
    #     controller.disconnect()
    # else:
    #     print("Failed to connect to Arduino")

if __name__ == "__main__":
    test_testseq_protocol()