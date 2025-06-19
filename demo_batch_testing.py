"""
Demo script for batch-only SMT panel testing
Shows the simplified communication approach
"""
import time
import logging
from src.hardware.smt_arduino_controller import SMTArduinoController

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    # Find Arduino port
    import serial.tools.list_ports
    ports = list(serial.tools.list_ports.comports())
    print("Available ports:")
    for p in ports:
        print(f"  {p.device}: {p.description}")
    
    port = input("\nEnter the Arduino port (e.g., COM7): ").strip()
    
    # Create controller
    controller = SMTArduinoController()
    
    try:
        print(f"\nConnecting to Arduino on {port}...")
        if not controller.connect(port):
            print("Failed to connect!")
            return
        
        # Get firmware info
        firmware = controller.get_firmware_info()
        print(f"Connected! Firmware: {firmware}")
        
        # Make sure all relays are off
        print("\nTurning off all relays...")
        if controller.all_relays_off():
            print("✓ All relays off")
        
        # Test 1: Simple batch test
        print("\n" + "="*60)
        print("TEST 1: Simple Batch Panel Test")
        print("="*60)
        
        start_time = time.time()
        results = controller.test_panel()
        test_time = time.time() - start_time
        
        print(f"\nResults received in {test_time:.3f} seconds:")
        for relay in sorted(results.keys()):
            if results[relay]:
                r = results[relay]
                print(f"  Relay {relay}: {r['voltage']:6.3f}V  {r['current']:6.3f}A  {r['power']:6.3f}W")
            else:
                print(f"  Relay {relay}: FAILED")
        
        # Clear relays
        controller.all_relays_off()
        time.sleep(0.5)
        
        # Test 2: Batch test with progress
        print("\n" + "="*60)
        print("TEST 2: Batch Panel Test with Progress Updates")
        print("="*60)
        
        def progress_callback(relay_num, measurement):
            print(f"  [Progress] Relay {relay_num} complete: {measurement['voltage']:.3f}V, {measurement['current']:.3f}A")
        
        start_time = time.time()
        results = controller.test_panel_stream(progress_callback)
        test_time = time.time() - start_time
        
        print(f"\nStream test completed in {test_time:.3f} seconds")
        
        # Test 3: Button functionality
        print("\n" + "="*60)
        print("TEST 3: Button Status Check")
        print("="*60)
        
        button_status = controller.get_button_status()
        print(f"Button status: {button_status}")
        
        # Summary
        print("\n" + "="*60)
        print("SYSTEM SUMMARY")
        print("="*60)
        print(f"✓ Firmware: {firmware}")
        print(f"✓ Communication: Batch-only (no individual relay commands)")
        print(f"✓ Performance: Full panel test in ~1 second")
        print(f"✓ Commands available:")
        print(f"    T  - Test panel (batch)")
        print(f"    TS - Test panel (streaming)")
        print(f"    X  - All relays off")
        print(f"    I  - Get firmware info")
        print(f"    B  - Get button status")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nCleaning up...")
        if controller.is_connected():
            controller.all_relays_off()
            controller.disconnect()
        print("Done!")

if __name__ == "__main__":
    main()
