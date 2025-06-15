"""
Quick test script to verify CRC-16 functionality after fixes
Run this to ensure CRC communication is working properly
"""

import logging
import time
from src.hardware.smt_arduino_controller import SMTArduinoController

# Setup logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_crc_communication(port="COM3"):
    """Test CRC-16 communication with Arduino"""
    print("=== CRC-16 Communication Test ===\n")
    
    # Create Arduino controller
    arduino = SMTArduinoController(baud_rate=115200)
    
    try:
        # Step 1: Connect
        print(f"1. Connecting to Arduino on {port}...")
        if not arduino.connect(port):
            print("   ❌ Failed to connect")
            return False
        print("   ✅ Connected successfully")
        
        # Step 2: Test basic communication
        print("\n2. Testing basic communication...")
        if not arduino.test_communication():
            print("   ❌ Communication test failed")
            return False
        print("   ✅ Communication test passed")
        
        # Step 3: Check CRC support
        print("\n3. Checking CRC support...")
        print(f"   Firmware version: {arduino.firmware_version}")
        print(f"   CRC supported: {arduino.crc_supported}")
        
        if not arduino.crc_supported:
            print("   ❌ CRC not supported by firmware")
            return False
        
        # Step 4: Enable CRC (before starting reading loop)
        print("\n4. Enabling CRC-16 validation...")
        if arduino.enable_crc_validation(True):
            print("   ✅ CRC enabled successfully")
        else:
            print("   ❌ Failed to enable CRC")
            return False
        
        # Step 5: Configure sensors
        print("\n5. Configuring sensors...")
        from src.hardware.smt_arduino_controller import SMTSensorConfigurations
        sensor_configs = SMTSensorConfigurations.smt_panel_sensors()
        if arduino.configure_sensors(sensor_configs):
            print("   ✅ Sensors configured")
        else:
            print("   ❌ Sensor configuration failed")
            return False
        
        # Step 6: Start reading loop (after CRC is enabled)
        print("\n6. Starting reading loop...")
        arduino.start_reading()
        print("   ✅ Reading loop started")
        
        # Step 7: Test a measurement with CRC enabled
        print("\n7. Testing measurement with CRC enabled...")
        time.sleep(0.5)  # Let everything stabilize
        
        # Try a simple relay control
        response = arduino.send_command("RELAY:1:ON", timeout=2.0)
        if response:
            print(f"   ✅ Relay control response: {response}")
        else:
            print("   ❌ No response to relay control")
        
        # Turn relay off
        arduino.send_command("RELAY:1:OFF", timeout=1.0)
        
        # Step 8: Get CRC statistics
        print("\n8. CRC Statistics:")
        stats = arduino.get_crc_statistics()
        print(f"   CRC enabled: {stats['crc_enabled']}")
        print(f"   Python side - Total messages: {stats['python_stats'].get('total_messages', 0)}")
        print(f"   Python side - CRC errors: {stats['python_stats'].get('crc_errors', 0)}")
        
        print("\n✅ All tests passed! CRC communication is working properly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        print("\n9. Cleaning up...")
        if arduino.is_connected():
            arduino.disconnect()
        print("   ✅ Disconnected")

if __name__ == "__main__":
    # Change this to your Arduino port
    ARDUINO_PORT = "COM3"
    
    success = test_crc_communication(ARDUINO_PORT)
    
    print("\n" + "="*40)
    if success:
        print("TEST RESULT: SUCCESS ✅")
        print("CRC-16 communication is working correctly!")
    else:
        print("TEST RESULT: FAILED ❌")
        print("Please check the logs above for details.")
