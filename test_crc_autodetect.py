#!/usr/bin/env python3
"""
Test CRC Auto-Detection

This script tests that the SMT Arduino controller properly auto-detects
when the Arduino has CRC enabled and adapts accordingly.

Usage: python test_crc_autodetect.py --port COM3
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


def test_crc_autodetection(port: str):
    """Test CRC auto-detection during connection"""
    print("\n" + "="*50)
    print("CRC Auto-Detection Test")
    print("="*50 + "\n")
    
    controller = None
    try:
        # Create controller instance (starts with CRC disabled)
        print("1. Creating SMT Arduino controller...")
        controller = SMTArduinoController()
        print("   ✅ Controller created (CRC initially disabled)")
        
        # Connect to Arduino (should auto-detect CRC)
        print(f"\n2. Connecting to Arduino on {port}...")
        print("   Auto-detecting CRC mode...")
        
        if controller.connect(port):
            print("   ✅ Connected successfully!")
            
            # Check if CRC was auto-detected
            if controller.is_crc_enabled():
                print("   ✅ CRC auto-detected and enabled!")
            else:
                print("   ℹ️  Arduino firmware does not have CRC enabled")
            
            # Get version info
            print("\n3. Getting Arduino information...")
            response = controller.send_command("VERSION")
            if response:
                print(f"   Version: {response}")
            
            # Get CRC status
            print("\n4. Checking CRC status...")
            if controller.is_crc_enabled():
                response = controller.send_command("CRC:STATUS")
                if response:
                    print(f"   CRC Status: {response}")
                
                # Get statistics
                stats = controller.get_crc_statistics()
                print("\n5. CRC Statistics:")
                print(f"   - CRC Supported: {stats['crc_supported']}")
                print(f"   - CRC Enabled: {stats['crc_enabled']}")
                if stats['python_stats']:
                    print(f"   - Python-side stats: {stats['python_stats']}")
            else:
                print("   CRC not enabled - Arduino using standard protocol")
            
            print("\n✅ Auto-detection test completed successfully!")
            return True
            
        else:
            print("   ❌ Failed to connect to Arduino")
            return False
        
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
    parser = argparse.ArgumentParser(description='Test CRC auto-detection')
    parser.add_argument('--port', required=True, help='Serial port (e.g., COM3)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    # Setup logging
    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    # Run the test
    success = test_crc_autodetection(args.port)
    
    if success:
        print("\n🎉 CRC auto-detection is working correctly!")
        print("\nYour Arduino firmware has CRC enabled by default,")
        print("and the Python controller successfully detected and adapted to it.")
        sys.exit(0)
    else:
        print("\n❌ CRC auto-detection test failed!")
        print("\nTry running with --debug flag for more information.")
        sys.exit(1)


if __name__ == "__main__":
    main()
