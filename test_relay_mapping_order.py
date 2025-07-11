#!/usr/bin/env python3
"""Test script to verify relay mapping order implementation"""

from src.hardware.smt_arduino_controller import SMTArduinoController

def test_relay_mapping_order():
    """Test that relay mapping is processed in order"""
    
    controller = SMTArduinoController()
    
    # Test 1: Single relay mappings (like SL0224P01-ABL)
    print("Test 1: Single relay mappings")
    relay_mapping = {
        "1": {"board": 1, "function": "mainbeam"},
        "2": {"board": 2, "function": "mainbeam"},
        "3": {"board": 3, "function": "mainbeam"},
        "4": {"board": 4, "function": "mainbeam"},
        "5": {"board": 1, "function": "backlight"},
        "6": {"board": 2, "function": "backlight"},
        "7": {"board": 3, "function": "backlight"},
        "8": {"board": 4, "function": "backlight"}
    }
    
    test_sequence = [
        {"function": "mainbeam", "duration_ms": 500, "delay_after_ms": 100},
        {"function": "backlight", "duration_ms": 300, "delay_after_ms": 0}
    ]
    
    relay_groups = controller._parse_relay_mapping(relay_mapping)
    command = controller._build_testseq_command(relay_groups, test_sequence)
    
    expected = "TESTSEQ:1:500;OFF:100;2:500;OFF:100;3:500;OFF:100;4:500;OFF:100;5:300;6:300;7:300;8:300"
    print(f"Generated: {command}")
    print(f"Expected:  {expected}")
    print(f"Match: {command == expected}\n")
    
    # Test 2: Multiple relay mappings
    print("Test 2: Multiple relay mappings")
    relay_mapping = {
        "1,2": {"board": 1, "function": "highbeam"},
        "3": {"board": 2, "function": "lowbeam"},
        "4,5,6": {"board": 3, "function": "foglight"},
        "7": {"board": 4, "function": "lowbeam"}
    }
    
    test_sequence = [
        {"function": "highbeam", "duration_ms": 600, "delay_after_ms": 150},
        {"function": "lowbeam", "duration_ms": 400, "delay_after_ms": 100},
        {"function": "foglight", "duration_ms": 350, "delay_after_ms": 0}
    ]
    
    relay_groups = controller._parse_relay_mapping(relay_mapping)
    command = controller._build_testseq_command(relay_groups, test_sequence)
    
    expected = "TESTSEQ:1,2:600;OFF:150;3:400;OFF:100;4,5,6:350;7:400;OFF:100"
    print(f"Generated: {command}")
    print(f"Expected:  {expected}")
    print(f"Match: {command == expected}\n")
    
    # Test 3: Out of order relay mapping (should still process in numeric order)
    print("Test 3: Out of order relay mapping")
    relay_mapping = {
        "5": {"board": 1, "function": "func1"},
        "1": {"board": 2, "function": "func1"},
        "3": {"board": 3, "function": "func2"},
        "2": {"board": 4, "function": "func2"}
    }
    
    test_sequence = [
        {"function": "func1", "duration_ms": 200, "delay_after_ms": 50},
        {"function": "func2", "duration_ms": 300, "delay_after_ms": 0}
    ]
    
    relay_groups = controller._parse_relay_mapping(relay_mapping)
    command = controller._build_testseq_command(relay_groups, test_sequence)
    
    expected = "TESTSEQ:1:200;OFF:50;2:300;3:300;5:200;OFF:50"
    print(f"Generated: {command}")
    print(f"Expected:  {expected}")
    print(f"Match: {command == expected}\n")

if __name__ == "__main__":
    test_relay_mapping_order()