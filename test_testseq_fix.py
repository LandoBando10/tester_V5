#!/usr/bin/env python3
"""Test script to verify TESTSEQ command fix for simultaneous relay activation"""

import serial
import time
import sys

def send_command(ser, cmd):
    """Send command and wait for response"""
    cmd_with_end = f"{cmd}\r\n"
    print(f"> {cmd}")
    ser.write(cmd_with_end.encode())
    ser.flush()
    
    # Wait for response
    start = time.time()
    responses = []
    while time.time() - start < 3.0:
        if ser.in_waiting > 0:
            response = ser.readline().decode('utf-8').strip()
            print(f"< {response}")
            responses.append(response)
            if "END" in response or "ERROR" in response or "OK" in response:
                break
    
    return responses

def main():
    # Default to COM7 if no port specified
    port = sys.argv[1] if len(sys.argv) > 1 else "COM7"
    
    print(f"Connecting to {port} at 115200 baud...")
    try:
        ser = serial.Serial(port, 115200, timeout=1)
        time.sleep(2)  # Wait for Arduino to initialize
        
        # Clear any startup messages
        while ser.in_waiting > 0:
            print(f"Startup: {ser.readline().decode('utf-8').strip()}")
        
        print("\n=== Testing TESTSEQ Command Fix ===")
        
        # Check firmware version
        print("\n1. Checking firmware...")
        send_command(ser, "I")
        time.sleep(0.5)
        
        # Turn all relays off
        print("\n2. Turning all relays OFF...")
        send_command(ser, "X")
        time.sleep(0.5)
        
        # Test the original problematic command (sequential)
        print("\n3. Testing original sequential command (should work now)...")
        print("   This activates relays one by one: 1, then 2, then 3, etc.")
        responses = send_command(ser, "TESTSEQ:1:500;2:500;3:500;4:500;OFF:100;5:300;6:300;7:300;8:300")
        
        # Check if we got proper results
        if any("TESTRESULTS" in r for r in responses):
            print("   ✓ Sequential relay activation works!")
        else:
            print("   ✗ Sequential relay activation failed")
        
        time.sleep(1)
        send_command(ser, "X")  # Turn all off
        
        # Test the corrected simultaneous command
        print("\n4. Testing simultaneous activation (recommended approach)...")
        print("   This activates relays 1-4 together, then 5-8 together")
        responses = send_command(ser, "TESTSEQ:1,2,3,4:500;OFF:100;5,6,7,8:300")
        
        # Check if we got proper results
        if any("TESTRESULTS" in r for r in responses):
            print("   ✓ Simultaneous relay activation works!")
        else:
            print("   ✗ Simultaneous relay activation failed")
        
        time.sleep(1)
        send_command(ser, "X")  # Turn all off
        
        # Test edge case: overlapping relays (should fail)
        print("\n5. Testing invalid overlap (should fail)...")
        print("   This tries to use relay 1 twice without OFF")
        responses = send_command(ser, "TESTSEQ:1,2:500;1,3:500")
        
        if any("ERROR" in r for r in responses):
            print("   ✓ Overlap detection works correctly")
        else:
            print("   ✗ Overlap detection may not be working")
        
        print("\n=== Test Complete ===")
        print("\nSummary:")
        print("- Arduino firmware should now accept sequential relay activation")
        print("- Python controller should group relays by function for simultaneous activation")
        print("- The command sent should be: TESTSEQ:1,2,3,4:500;OFF:100;5,6,7,8:300")
        
        ser.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()