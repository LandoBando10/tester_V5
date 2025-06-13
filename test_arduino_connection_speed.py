#!/usr/bin/env python3
"""Test script to verify Arduino connection speed after removing START/I2C_SCAN commands"""

import time
import logging
from src.hardware.arduino_controller import ArduinoController, SensorConfigurations

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

def test_connection_speed(port="COM7"):
    """Test Arduino connection and measure time taken"""
    
    print(f"\n{'='*60}")
    print("Arduino Connection Speed Test")
    print(f"{'='*60}\n")
    
    # Create Arduino controller
    arduino = ArduinoController(baud_rate=115200)
    
    # Measure connection time
    print(f"Connecting to Arduino on {port}...")
    start_time = time.time()
    
    try:
        # Connect
        if arduino.connect(port):
            connect_time = time.time() - start_time
            print(f"✓ Connected in {connect_time:.3f} seconds")
            
            # Get firmware type
            firmware_type = arduino.get_firmware_type()
            print(f"✓ Firmware type: {firmware_type}")
            
            # Configure sensors
            print("Configuring sensors...")
            sensor_start = time.time()
            sensor_configs = SensorConfigurations.smt_panel_sensors()
            if arduino.configure_sensors(sensor_configs):
                sensor_time = time.time() - sensor_start
                print(f"✓ Sensors configured in {sensor_time:.3f} seconds")
            else:
                print("✗ Sensor configuration failed")
            
            # Start reading loop
            print("Starting reading loop...")
            read_start = time.time()
            arduino.start_reading()
            read_time = time.time() - read_start
            print(f"✓ Reading loop started in {read_time:.3f} seconds")
            
            # Total time
            total_time = time.time() - start_time
            print(f"\n{'='*60}")
            print(f"TOTAL CONNECTION TIME: {total_time:.3f} seconds")
            print(f"{'='*60}")
            
            if total_time < 2.0:
                print("\n✓ SUCCESS: Connection is now FAST! (under 2 seconds)")
            else:
                print(f"\n⚠ Connection took {total_time:.3f} seconds - check for other delays")
            
            # Test button state
            print("\nTesting button state query...")
            response = arduino.send_command("BUTTON_STATE", timeout=1.0)
            if response:
                print(f"Button state: {response}")
            
            # Clean up
            arduino.disconnect()
            
        else:
            print(f"✗ Failed to connect to Arduino on {port}")
            
    except Exception as e:
        print(f"✗ Error during test: {e}")
        if arduino.is_connected():
            arduino.disconnect()

if __name__ == "__main__":
    # You can change the port here if needed
    test_connection_speed("COM7")
    
    print("\nTest complete. Press Enter to exit...")
    input()
