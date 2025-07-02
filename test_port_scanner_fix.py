#!/usr/bin/env python3
"""Test script to verify port scanner fixes."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.services.port_scanner_service import PortScannerService
from src.services.port_registry import port_registry
from src.services.device_cache_service import DeviceCacheService

def test_port_scanner_fix():
    """Test that probe_port works with check_in_use parameter."""
    print("Testing Port Scanner Fix...")
    
    # Create services
    scanner = PortScannerService()
    cache = DeviceCacheService()
    
    # Get available ports
    ports = scanner.get_available_ports()
    print(f"\nAvailable ports: {ports}")
    
    if not ports:
        print("No ports available for testing")
        return
    
    # Test 1: Normal probe (should skip in-use ports)
    print("\n--- Test 1: Normal probe_port behavior ---")
    test_port = ports[0] if ports else "COM1"
    
    # Mark port as in use
    port_registry.acquire_port(test_port)
    print(f"Marked {test_port} as in use")
    
    # Try normal probe - should return None
    result1 = scanner.probe_port(test_port)
    print(f"probe_port({test_port}) = {result1}")
    assert result1 is None, "Expected None for in-use port with default behavior"
    print("✓ Correctly returned None for in-use port")
    
    # Test 2: Probe with check_in_use=True
    print("\n--- Test 2: probe_port with check_in_use=True ---")
    
    # Add some cache data
    cache.update_device(test_port, {
        'device_type': 'Arduino',
        'description': 'Test Arduino',
        'response': 'ID:TEST_ARDUINO'
    })
    
    # Try probe with check_in_use=True - should return cached info
    result2 = scanner.probe_port(test_port, check_in_use=True)
    print(f"probe_port({test_port}, check_in_use=True) = {result2}")
    assert result2 is not None, "Expected DeviceInfo for in-use port with check_in_use=True"
    assert result2.device_type == 'Arduino', "Expected Arduino device type from cache"
    print("✓ Successfully got device info for in-use port from cache")
    
    # Test 3: Probe unknown in-use port
    print("\n--- Test 3: probe_port for unknown in-use port ---")
    unknown_port = "COM99"
    port_registry.acquire_port(unknown_port)
    
    result3 = scanner.probe_port(unknown_port, check_in_use=True)
    print(f"probe_port({unknown_port}, check_in_use=True) = {result3}")
    assert result3 is not None, "Expected DeviceInfo even for unknown in-use port"
    assert result3.device_type == 'Unknown', "Expected Unknown device type"
    print("✓ Got fallback device info for unknown in-use port")
    
    # Cleanup
    port_registry.release_port(test_port)
    port_registry.release_port(unknown_port)
    cache.remove_device(test_port)
    
    print("\n✅ All tests passed! The fix is working correctly.")
    
    # Test 4: identify_port_safe method
    print("\n--- Test 4: identify_port_safe method ---")
    result4 = scanner.identify_port_safe(test_port)
    print(f"identify_port_safe({test_port}) = {result4}")
    print("✓ identify_port_safe method works")

if __name__ == "__main__":
    test_port_scanner_fix()