"""
Quick test to verify all compatibility methods are working
"""
import logging
from src.hardware.smt_arduino_controller import SMTArduinoController

logging.basicConfig(level=logging.INFO)

# Create controller instance
controller = SMTArduinoController()

# Check all methods that smt_controller.py might use
print("Checking compatibility methods...")

# Methods that should exist
methods_to_check = [
    'connect',
    'disconnect', 
    'is_connected',
    'send_command',
    'query',
    'test_communication',
    'get_firmware_type',
    'get_firmware_info',
    'get_board_info',
    'configure_sensors',
    'test_panel',
    'test_panel_stream',
    'all_relays_off',
    'get_button_status',
    'set_button_callback',
    'start_reading',
    'stop_reading',
    'pause_reading_for_test',
    'resume_reading_after_test',
    'enable_crc_validation',
    '_send_command',
    '_flush_buffers'
]

# Check each method
missing_methods = []
for method in methods_to_check:
    if hasattr(controller, method):
        print(f"✓ {method}")
    else:
        print(f"✗ {method} - MISSING!")
        missing_methods.append(method)

# Check properties
print("\nChecking properties...")
properties_to_check = ['serial']

for prop in properties_to_check:
    if hasattr(controller, prop):
        print(f"✓ {prop}")
        # Check serial has flush_buffers
        if prop == 'serial':
            serial_obj = getattr(controller, prop)
            if hasattr(serial_obj, 'flush_buffers'):
                print(f"  ✓ serial.flush_buffers")
            else:
                print(f"  ✗ serial.flush_buffers - MISSING!")
    else:
        print(f"✗ {prop} - MISSING!")
        missing_methods.append(prop)

print(f"\nTotal missing: {len(missing_methods)}")
if missing_methods:
    print("Missing methods/properties:", missing_methods)
else:
    print("All compatibility methods are present!")

# Test the serial wrapper
print("\nTesting serial wrapper...")
try:
    serial_wrapper = controller.serial
    print(f"Serial wrapper type: {type(serial_wrapper)}")
    print(f"Has flush_buffers: {hasattr(serial_wrapper, 'flush_buffers')}")
except Exception as e:
    print(f"Error accessing serial wrapper: {e}")
