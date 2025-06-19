"""
Demo script to show the performance improvement with single command panel testing
"""
import time
import logging
from src.hardware.smt_arduino_controller import SMTArduinoController

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_old_approach(controller):
    """Test using individual relay commands (old approach)"""
    print("\n=== Testing OLD approach (individual commands) ===")
    start_time = time.time()
    
    results = {}
    for relay in range(1, 9):
        relay_start = time.time()
        result = controller.measure_relay(relay)
        relay_time = time.time() - relay_start
        
        if result:
            print(f"Relay {relay}: {result['voltage']:.3f}V, {result['current']:.3f}A, {result['power']:.3f}W (took {relay_time:.3f}s)")
            results[relay] = result
        else:
            print(f"Relay {relay}: FAILED (took {relay_time:.3f}s)")
            results[relay] = None
    
    total_time = time.time() - start_time
    print(f"\nOLD approach total time: {total_time:.3f}s")
    print(f"Average time per relay: {total_time/8:.3f}s")
    return results, total_time

def test_new_approach(controller):
    """Test using single panel command (new approach)"""
    print("\n=== Testing NEW approach (single panel command) ===")
    start_time = time.time()
    
    # Single command to test all relays
    results = controller.test_panel()
    
    total_time = time.time() - start_time
    
    # Display results
    for relay in range(1, 9):
        if relay in results and results[relay]:
            r = results[relay]
            print(f"Relay {relay}: {r['voltage']:.3f}V, {r['current']:.3f}A, {r['power']:.3f}W")
        else:
            print(f"Relay {relay}: FAILED")
    
    print(f"\nNEW approach total time: {total_time:.3f}s")
    print(f"Average time per relay: {total_time/8:.3f}s")
    return results, total_time

def test_streaming_approach(controller):
    """Test using streaming panel command"""
    print("\n=== Testing STREAMING approach (with progress updates) ===")
    start_time = time.time()
    
    def progress_callback(relay_num, measurement):
        print(f"  Progress: Relay {relay_num} measured - {measurement['voltage']:.3f}V, {measurement['current']:.3f}A")
    
    # Test with streaming updates
    results = controller.test_panel_stream(progress_callback)
    
    total_time = time.time() - start_time
    
    print(f"\nSTREAMING approach total time: {total_time:.3f}s")
    print(f"Average time per relay: {total_time/8:.3f}s")
    return results, total_time

def main():
    # Find the Arduino port
    import serial.tools.list_ports
    ports = list(serial.tools.list_ports.comports())
    print("Available ports:")
    for p in ports:
        print(f"  {p.device}: {p.description}")
    
    # Use the port you identified
    PORT = input("\nEnter the Arduino port (e.g., COM7): ").strip()
    
    # Create controller
    controller = SMTArduinoController()
    
    try:
        print(f"\nConnecting to Arduino on {PORT}...")
        if not controller.connect(PORT):
            print("Failed to connect!")
            return
        
        print("Connected! Running performance comparison...")
        
        # Test communication
        firmware_id = controller.get_board_info()
        print(f"Firmware: {firmware_id}")
        
        # Make sure all relays are off
        controller.all_relays_off()
        time.sleep(0.5)
        
        # Run tests
        old_results, old_time = test_old_approach(controller)
        
        # Clear between tests
        controller.all_relays_off()
        time.sleep(0.5)
        
        new_results, new_time = test_new_approach(controller)
        
        # Clear between tests
        controller.all_relays_off()
        time.sleep(0.5)
        
        stream_results, stream_time = test_streaming_approach(controller)
        
        # Performance summary
        print("\n" + "="*60)
        print("PERFORMANCE SUMMARY")
        print("="*60)
        print(f"OLD approach (8 commands):     {old_time:.3f}s total")
        print(f"NEW approach (1 command):      {new_time:.3f}s total")
        print(f"STREAMING approach (progress): {stream_time:.3f}s total")
        print(f"\nSpeed improvement: {old_time/new_time:.1f}x faster!")
        print(f"Time saved per panel: {old_time - new_time:.3f}s")
        
        # Verify results match
        print("\nVerifying results match between approaches...")
        mismatch = False
        for relay in range(1, 9):
            if relay in old_results and relay in new_results:
                old = old_results[relay]
                new = new_results[relay]
                if old and new:
                    v_diff = abs(old['voltage'] - new['voltage'])
                    c_diff = abs(old['current'] - new['current'])
                    if v_diff > 0.1 or c_diff > 0.01:
                        print(f"WARNING: Relay {relay} measurements differ!")
                        print(f"  Old: {old['voltage']:.3f}V, {old['current']:.3f}A")
                        print(f"  New: {new['voltage']:.3f}V, {new['current']:.3f}A")
                        mismatch = True
        
        if not mismatch:
            print("✓ All measurements match between approaches!")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nCleaning up...")
        controller.all_relays_off()
        controller.disconnect()
        print("Done!")

if __name__ == "__main__":
    main()
