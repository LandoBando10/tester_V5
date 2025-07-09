#!/usr/bin/env python3
"""
Run hardware validation tests for TESTSEQ protocol
These tests require actual Arduino hardware with firmware v2.0.0+

WARNING: These tests will activate relays and may draw significant current.
Ensure proper power supply and cooling before running thermal tests.
"""

import sys
import os
import unittest
import argparse
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    parser = argparse.ArgumentParser(description='Run TESTSEQ hardware validation tests')
    parser.add_argument('--port', default='COM7', help='Arduino serial port (default: COM7)')
    parser.add_argument('--test', help='Run specific test (e.g., test_relay_switching_speed_measurement)')
    parser.add_argument('--skip-thermal', action='store_true', help='Skip thermal test (takes 5 minutes)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--output-dir', default='.', help='Directory for test output files')
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Update test configuration
    import tests.hardware.test_hardware_validation as test_module
    test_module.TEST_PORT = args.port
    
    # Change to output directory
    if args.output_dir != '.':
        os.makedirs(args.output_dir, exist_ok=True)
        os.chdir(args.output_dir)
    
    print(f"\n{'='*70}")
    print("TESTSEQ Hardware Validation Tests")
    print(f"{'='*70}")
    print(f"Port: {args.port}")
    print(f"Output directory: {os.path.abspath(args.output_dir)}")
    print(f"Test started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")
    
    # Safety warning
    print("⚠️  WARNING: These tests will activate relays and draw current!")
    print("⚠️  Ensure proper power supply and ventilation before proceeding.")
    response = input("\nContinue with hardware tests? (y/N): ")
    if response.lower() != 'y':
        print("Tests cancelled.")
        return 0
    
    # Create test suite
    if args.test:
        # Run specific test
        suite = unittest.TestLoader().loadTestsFromName(
            f'tests.hardware.test_hardware_validation.TestHardwareValidation.{args.test}'
        )
    else:
        # Load all tests
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(test_module)
        
        # Remove thermal test if requested
        if args.skip_thermal:
            # Filter out thermal test
            filtered_suite = unittest.TestSuite()
            for test_group in suite:
                for test in test_group:
                    if 'thermal' not in str(test):
                        filtered_suite.addTest(test)
            suite = filtered_suite
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*70}")
    print("Hardware Test Summary")
    print(f"{'='*70}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print(f"Test completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # List output files
    output_files = [
        "relay_switching_speed.json",
        "measurement_accuracy.json", 
        "timing_jitter_analysis.json",
        "thermal_behavior.json",
        "emi_noise_test.json"
    ]
    
    print(f"\n{'='*70}")
    print("Output Files:")
    print(f"{'='*70}")
    for filename in output_files:
        filepath = os.path.join(args.output_dir, filename)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            print(f"✓ {filename} ({size:,} bytes)")
        else:
            print(f"✗ {filename} (not generated)")
    
    if result.wasSuccessful():
        print(f"\n✅ All hardware tests passed!")
        return 0
    else:
        print(f"\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())