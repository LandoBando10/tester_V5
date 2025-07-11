#!/usr/bin/env python3
"""Debug script for testing PCF8575 relay control"""

import serial
import time
import sys

def send_command(ser, cmd):
    """Send command and wait for response"""
    cmd_with_end = f"{cmd}\r\n"
    ser.write(cmd_with_end.encode())
    ser.flush()
    
    # Wait for response
    start = time.time()
    while time.time() - start < 2.0:
        if ser.in_waiting > 0:
            response = ser.readline().decode('utf-8').strip()
            print(f"< {response}")
            return response
    print("< (no response)")
    return None

def main():
    # Default to COM7 if no port specified
    if len(sys.argv) < 2:
        port = "COM7"
        print(f"No port specified, using default: {port}")
    else:
        port = sys.argv[1]
    
    print(f"Connecting to {port} at 115200 baud...")
    try:
        ser = serial.Serial(port, 115200, timeout=1)
        time.sleep(2)  # Wait for Arduino to initialize
        
        # Clear any startup messages
        while ser.in_waiting > 0:
            print(f"Startup: {ser.readline().decode('utf-8').strip()}")
        
        print("\n=== PCF8575 Relay Debug Tool ===")
        
        # Check I2C status
        print("\n1. Checking I2C devices...")
        send_command(ser, "I2C_STATUS")
        
        # Test turning all relays off
        print("\n2. Turning all relays OFF...")
        send_command(ser, "X")
        
        # Test individual relays
        print("\n3. Testing individual relays...")
        print("   Watch for clicking sounds or LED indicators on relay board")
        print("   Also check if debug messages show correct mask values")
        
        for i in range(1, 9):
            print(f"\n   Testing relay {i}...")
            print(f"   > RELAY:{i}:ON")
            send_command(ser, f"RELAY:{i}:ON")
            time.sleep(1)
            
            print(f"   > RELAY:{i}:OFF")
            send_command(ser, f"RELAY:{i}:OFF")
            time.sleep(0.5)
        
        # Test relay polarity
        print("\n4. Testing relay polarity...")
        print("   If relays are backwards (ON when should be OFF), change RELAY_ACTIVE_LOW")
        
        # Direct PCF8575 test
        print("\n5. Direct PCF8575 output test...")
        print("   Sending TESTSEQ to see debug output...")
        send_command(ser, "TESTSEQ:1:1000")
        
        # Wait for any debug messages
        time.sleep(2)
        while ser.in_waiting > 0:
            print(f"Debug: {ser.readline().decode('utf-8').strip()}")
        
        print("\n6. Manual relay control mode...")
        print("   Enter relay number (1-16) to turn ON and hold, or 'q' to quit")
        
        while True:
            user_input = input("\n   Relay number (1-16) or 'q': ").strip()
            
            if user_input.lower() == 'q':
                break
                
            try:
                relay_num = int(user_input)
                if 1 <= relay_num <= 16:
                    print(f"   Turning relay {relay_num} ON...")
                    send_command(ser, f"RELAY:{relay_num}:ON")
                    input("   Press Enter to turn OFF...")
                    send_command(ser, f"RELAY:{relay_num}:OFF")
                else:
                    print("   Invalid relay number. Please enter 1-16.")
            except ValueError:
                print("   Invalid input. Please enter a number 1-16 or 'q'.")
        
        print("\n=== Debug Complete ===")
        print("\nIf no relays activated:")
        print("1. Check PCF8575 wiring (VCC, GND, SDA, SCL)")
        print("2. Check relay board power supply")
        print("3. Check connections between PCF8575 outputs and relay inputs")
        print("4. Try changing RELAY_ACTIVE_LOW to false in firmware")
        print("5. Verify PCF8575 I2C address (should be 0x20)")
        
        ser.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()