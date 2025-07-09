#!/usr/bin/env python3
"""
Run TESTSEQ protocol integration tests
This script runs the integration tests for section 5.2 of the SMT simultaneous relay todo
"""

import sys
import os
import unittest
import argparse
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    parser = argparse.ArgumentParser(description='Run TESTSEQ integration tests')
    parser.add_argument('--port', default='COM7', help='Arduino serial port (default: COM7)')
    parser.add_argument('--hardware', action='store_true', help='Require hardware for tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--test', help='Run specific test (e.g., test_full_sequence_execution)')
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Update test configuration
    import tests.integration.test_testseq_integration as test_module
    test_module.TEST_PORT = args.port
    test_module.ARDUINO_REQUIRED = args.hardware
    
    # Create test suite
    if args.test:
        # Run specific test
        suite = unittest.TestLoader().loadTestsFromName(
            f'tests.integration.test_testseq_integration.TestTESTSEQIntegration.{args.test}'
        )
    else:
        # Run all tests
        suite = unittest.TestLoader().loadTestsFromModule(test_module)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("TESTSEQ Integration Test Summary")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())