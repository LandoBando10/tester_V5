#!/usr/bin/env python3
"""Test script to verify OFF commands are added between all relays"""

from src.hardware.smt_arduino_controller import SMTArduinoController

def test_off_commands():
    """Test that OFF commands are added between all relay activations"""
    
    controller = SMTArduinoController()
    
    # Test with SL0224P01-ABL configuration
    print("Testing SL0224P01-ABL relay mapping with OFF commands fix:")
    
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
    
    print(f"\nGenerated command:\n{command}")
    
    # Expected: OFF commands between ALL relays now
    expected = "TESTSEQ:1:500;OFF:100;2:500;OFF:100;3:500;OFF:100;4:500;OFF:100;5:300;OFF:0;6:300;OFF:0;7:300;OFF:0;8:300"
    
    print(f"\nExpected command:\n{expected}")
    
    # Check if OFF commands are present between all relays
    parts = command.split(";")
    off_count = sum(1 for part in parts if part.startswith("OFF:"))
    relay_count = sum(1 for part in parts if ":" in part and not part.startswith("OFF:") and not part.startswith("TESTSEQ:"))
    
    print(f"\nAnalysis:")
    print(f"- Number of relay activations: {relay_count}")
    print(f"- Number of OFF commands: {off_count}")
    print(f"- Expected OFF commands: {relay_count - 1}")
    
    if off_count == relay_count - 1:
        print("\n✓ SUCCESS: OFF commands are properly inserted between all relays")
    else:
        print("\n✗ FAILED: OFF commands are missing")
    
    # Check specific issue with relays 5-8
    if "5:300;OFF:" in command and "6:300;OFF:" in command and "7:300;OFF:" in command:
        print("✓ Relays 5-8 now have OFF commands between them")
    else:
        print("✗ Relays 5-8 are still missing OFF commands")

if __name__ == "__main__":
    test_off_commands()