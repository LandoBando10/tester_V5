#!/usr/bin/env python3
"""
Simple test script for SMT Arduino communication
Tests basic commands without the full application overhead
"""

import serial
import serial.tools.list_ports
import time
import sys


def find_arduino_ports():
    """Find all available serial ports"""
    ports = []
    for port in serial.tools.list_ports.comports():
        print(f"Found port: {port.device} - {port.description}")
        ports.append(port.device)
    return ports


def test_arduino_communication(port, baudrate=115200):
    """Test communication with Arduino on specified port"""
    print(f"\n{'='*60}")
    print(f"Testing Arduino on {port} at {baudrate} baud")
    print(f"{'='*60}")
    
    try:
        # Open serial connection
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=2.0,
            write_timeout=2.0
        )
        
        print(f"✓ Connected to {port}")
        
        # Clear any existing data
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.1)
        
        # Check for any startup messages
        print("\nChecking for startup messages...")
        time.sleep(0.5)
        if ser.in_waiting > 0:
            startup_msg = ser.read(ser.in_waiting).decode('utf-8', errors='ignore').strip()
            print(f"Startup message: {startup_msg}")
        else:
            print("No startup messages")
        
        # Test commands
        commands = [
            ("I", "Get device ID"),
            ("X", "Turn all relays off"),
            ("B", "Get button status"),
            ("R1", "Test relay 1"),
            ("INVALID", "Test error response")
        ]
        
        print("\nTesting commands:")
        for cmd, description in commands:
            print(f"\n→ Sending '{cmd}' ({description})...")
            
            # Clear buffers before sending
            ser.reset_input_buffer()
            
            # Send command with newline
            ser.write(f"{cmd}\n".encode())
            ser.flush()
            
            # Wait for response
            time.sleep(0.1)
            
            # Read response
            response = ""
            deadline = time.time() + 1.0
            while time.time() < deadline:
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    response += data
                    if '\n' in response:
                        break
                time.sleep(0.01)
            
            response = response.strip()
            if response:
                print(f"← Response: {response}")
            else:
                print("← No response received")
        
        # Interactive mode
        print("\n" + "="*60)
        print("Interactive mode - type commands to send (or 'quit' to exit)")
        print("Valid commands: I, X, B, R1-R8")
        print("="*60)
        
        while True:
            try:
                cmd = input("\nCommand> ").strip()
                if cmd.lower() == 'quit':
                    break
                
                if not cmd:
                    continue
                
                # Clear buffers
                ser.reset_input_buffer()
                
                # Send command
                ser.write(f"{cmd}\n".encode())
                ser.flush()
                
                # Read response
                response = ""
                deadline = time.time() + 1.0
                while time.time() < deadline:
                    if ser.in_waiting > 0:
                        data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                        response += data
                        if '\n' in response:
                            break
                    time.sleep(0.01)
                
                response = response.strip()
                if response:
                    print(f"Response: {response}")
                else:
                    print("No response received")
                    
            except KeyboardInterrupt:
                print("\nInterrupted by user")
                break
        
        # Close connection
        ser.close()
        print(f"\n✓ Disconnected from {port}")
        
    except serial.SerialException as e:
        print(f"✗ Serial error: {e}")
    except Exception as e:
        print(f"✗ Error: {e}")


def main():
    print("SMT Arduino Communication Test")
    print("="*60)
    
    # Find available ports
    ports = find_arduino_ports()
    
    if not ports:
        print("No serial ports found!")
        return
    
    # Let user select port or test specific port
    if len(sys.argv) > 1:
        # Port specified on command line
        port = sys.argv[1]
        if port not in ports:
            print(f"Warning: {port} not in detected ports list")
    else:
        # Ask user to select
        print("\nAvailable ports:")
        for i, port in enumerate(ports):
            print(f"  {i+1}. {port}")
        
        while True:
            try:
                choice = input("\nSelect port number (or enter port name): ").strip()
                if choice.upper().startswith('COM') or choice.startswith('/dev/'):
                    port = choice
                    break
                else:
                    idx = int(choice) - 1
                    if 0 <= idx < len(ports):
                        port = ports[idx]
                        break
                    else:
                        print("Invalid selection")
            except ValueError:
                print("Invalid input")
    
    # Test the selected port
    test_arduino_communication(port)


if __name__ == "__main__":
    main()