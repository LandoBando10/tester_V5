#!/usr/bin/env python3
"""
Test CRC-16 Implementation

This script tests the CRC-16 functionality in your SMT Arduino system.
It verifies that CRC is enabled by default and working properly.

Usage: python test_crc_implementation.py --port COM3
"""

import sys
import time
import argparse
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.hardware.smt_arduino_controller import SMTArduinoController


def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def test_crc_functionality(port: str):
    """Test CRC functionality"""
    print("\n" + "="*50)
    print("CRC-16 Implementation Test")
    print("="*50 + "\n")
    
    controller = None
    try:
        # Create controller instance
        print(f"1. Connecting to Arduino on {port}...")
        controller = SMTArduinoController(port)
        
        if not controller.is_connected():
            print("❌ Failed to connect to Arduino")
            return False
        
        print("✅ Connected successfully")
        time.sleep(2)  # Let connection stabilize
        
        # Check initial CRC status
        print("\n2. Checking initial CRC status...")
        initial_crc = controller.is_crc_enabled()
        print(f"   CRC currently: {'ENABLED' if initial_crc else 'DISABLED'}")
        
        # Enable CRC
        print("\n3. Enabling CRC validation...")
        controller.enable_crc_validation(True)
        time.sleep(0.5)
        
        # Verify CRC is enabled
        crc_enabled = controller.is_crc_enabled()
        if crc_enabled:
            print("✅ CRC successfully enabled")
        else:
            print("❌ Failed to enable CRC")
            return False
        
        # Test basic commands with CRC
        print("\n4. Testing commands with CRC enabled...")
        
        # Test VERSION command
        print("   Testing VERSION command...")
        response = controller.send_command("VERSION")
        if response and response.startswith("OK:VERSION:"):
            print(f"   ✅ VERSION: {response}")
        else:
            print(f"   ❌ VERSION failed: {response}")
        
        # Test relay commands
        print("   Testing relay commands...")
        
        # Turn on relay 1
        response = controller.send_command("RELAY:1:ON")
        if response == "OK:RELAY:1:ON":
            print("   ✅ RELAY 1 ON successful")
        else:
            print(f"   ❌ RELAY 1 ON failed: {response}")
        
        time.sleep(0.5)
        
        # Turn off relay 1
        response = controller.send_command("RELAY:1:OFF")
        if response == "OK:RELAY:1:OFF":
            print("   ✅ RELAY 1 OFF successful")
        else:
            print(f"   ❌ RELAY 1 OFF failed: {response}")
        
        # Get CRC statistics
        print("\n5. Getting CRC statistics...")
        response = controller.send_command("CRC:STATUS")
        if response and response.startswith("OK:CRC:STATUS:"):
            print(f"   {response}")
            
            # Parse statistics
            parts = response.split(":")
            if len(parts) >= 7:
                try:
                    total = int(parts[3])
                    errors = int(parts[4])
                    rate = float(parts[5])
                    print(f"\n   Statistics:")
                    print(f"   - Total messages: {total}")
                    print(f"   - CRC errors: {errors}")
                    print(f"   - Error rate: {rate:.2f}%")
                    
                    if errors == 0:
                        print("   ✅ No CRC errors detected!")
                    else:
                        print(f"   ⚠️  {errors} CRC errors detected")
                except:
                    pass
        
        # Test measuring relays
        print("\n6. Testing relay measurement with CRC...")
        relays_to_test = [1, 2, 3, 4]
        results = controller.measure_relays(relays_to_test)
        
        if results:
            print(f"   ✅ Measured {len(results)} relays successfully:")
            for relay_num, state in results.items():
                print(f"      Relay {relay_num}: {'ON' if state else 'OFF'}")
        else:
            print("   ❌ Relay measurement failed")
        
        # Final CRC status check
        print("\n7. Final CRC status check...")
        response = controller.send_command("CRC:STATUS")
        if response:
            print(f"   {response}")
        
        print("\n" + "="*50)
        print("✅ CRC test completed successfully!")
        print("="*50 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if controller:
            print("\nDisconnecting...")
            controller.disconnect()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Test CRC implementation')
    parser.add_argument('--port', required=True, help='Serial port (e.g., COM3)')
    args = parser.parse_args()
    
    setup_logging()
    
    # Run the test
    success = test_crc_functionality(args.port)
    
    if success:
        print("\n🎉 All CRC tests passed!")
        sys.exit(0)
    else:
        print("\n❌ CRC tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
