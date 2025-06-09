#!/usr/bin/env python3
"""
Diode Dynamics Production Test Application
Main entry point for the testing application
Supports both Offroad and SMT testing modes
"""

import sys
import os
import logging
import argparse
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def setup_directories():
    """Create necessary directories if they don't exist"""
    directories = [
        'logs',
        'results',
        'config'
    ]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def setup_logging():
    """Setup application logging"""
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s', # Added filename and lineno
        handlers=[
            logging.FileHandler(log_dir / 'production_test.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Set specific loggers to appropriate levels
    logging.getLogger('serial').setLevel(logging.WARNING)
    logging.getLogger('PySide6').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING) # Add asyncio logger for less verbosity

    # Add a handler for critical errors to ensure they are prominent
    critical_handler = logging.FileHandler(log_dir / 'critical_errors.log')
    critical_handler.setLevel(logging.CRITICAL)
    critical_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'))
    logging.getLogger().addHandler(critical_handler)


def check_dependencies():
    """Check if all required dependencies are available"""
    logger = logging.getLogger(__name__) # Get logger instance
    required_modules = [
        'PySide6',
        'serial'
    ]

    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError as e:
            logger.error(f"Missing dependency: {module}. Error: {e}")
            missing_modules.append(module)

    if missing_modules:
        error_message = "Missing required modules:\\n"
        for module in missing_modules:
            error_message += f"  - {module}\\n"
        error_message += "\\nInstall missing modules with:\\n  pip install PySide6 pyserial"
        logger.critical(error_message)
        # For GUI applications, it's better to show a message box if possible,
        # but at this stage, GUI might not be initialized. Print is a fallback.
        print(f"\\nCRITICAL ERROR: {error_message}")
        return False

    logger.info("All required dependencies are available.")
    return True


def run_gui_mode():
    """Run the GUI application"""
    logger = logging.getLogger(__name__)
    
    # Check for SKU configuration file
    config_file = Path('config/skus.json')
    if not config_file.exists():
        error_msg = f"SKU configuration file not found: {config_file}. Please ensure it exists."
        logger.critical(error_msg)
        # Attempt to show a GUI error message if possible, otherwise print
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            # Ensure QApplication instance exists for QMessageBox
            if not QApplication.instance():
                _ = QApplication(sys.argv) # Create a temporary app instance
            QMessageBox.critical(None, "Configuration Error", error_msg)
        except Exception as e_gui:
            logger.error(f"Could not display GUI error message for missing config: {e_gui}")
            print(f"\\nCRITICAL ERROR: {error_msg}")
        return False

    try:
        # Import and run the GUI application
        from src.gui.main_window import MainWindow # Changed to import MainWindow directly
        from PySide6.QtWidgets import QApplication

        logger.info("Initializing QApplication...")
        app = QApplication(sys.argv)
        
        logger.info("Creating MainWindow instance...")
        window = MainWindow()
        logger.info("Showing MainWindow...")
        window.show()
        
        logger.info("Starting GUI application event loop...")
        app.exec()
        logger.info("GUI application finished.")
        return True

    except ImportError as e:
        error_msg = f"Import error: {e}. This might be due to missing application files or incorrect Python environment."
        logger.critical(error_msg, exc_info=True)
        print(f"\\nCRITICAL IMPORT ERROR: {error_msg}")
        print("Please check that all required application files are in place and the Python environment is correctly set up.")
        return False
    except Exception as e:
        error_msg = f"An unexpected error occurred while trying to run the GUI: {e}"
        logger.critical(error_msg, exc_info=True)
        print(f"\\nCRITICAL ERROR: {error_msg}")
        # Attempt to show a GUI error message
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            if not QApplication.instance():
                _ = QApplication(sys.argv)
            QMessageBox.critical(None, "Application Error", f"A critical error occurred: {e}\\n\\nPlease check the logs for more details.")
        except Exception as e_gui_critical:
            logger.error(f"Could not display critical GUI error message: {e_gui_critical}")
        return False


def run_offroad_test(sku: str, port: str, test_type: str = "FUNCTION_TEST"):
    """Run offroad testing in command line mode"""
    logger = logging.getLogger(__name__)
    
    try:
        from src.core.offroad_test import OffroadTest
        from src.data.sku_manager import load_test_parameters
        
        logger.info(f"Starting offroad test for SKU: {sku}")
        
        # Load test parameters
        parameters = load_test_parameters(sku)
        if not parameters:
            print(f"Error: No test parameters found for SKU: {sku}")
            return False
        
        # Create test instance
        test = OffroadTest(sku, parameters, port)
        
        # Set up progress callback
        def progress_callback(message: str, percentage: int):
            print(f"[{percentage:3d}%] {message}")
        
        test.set_progress_callback(progress_callback)
        
        # Execute test
        print(f"\nStarting offroad test for {sku} on {port}...")
        result = test.execute()
        
        # Display results
        print(f"\nTest Result: {'PASS' if result.passed else 'FAIL'}")
        
        if result.measurements:
            print("\nMeasurements:")
            for name, measurement in result.measurements.items():
                if hasattr(measurement, 'value'):
                    print(f"  {name}: {measurement.value} {measurement.unit}")
        
        if result.failures:
            print("\nFailures:")
            for failure in result.failures:
                print(f"  - {failure}")
        
        return result.passed
        
    except Exception as e:
        logger.error(f"Offroad test error: {e}")
        print(f"Error running offroad test: {e}")
        return False


def run_smt_test(sku: str, port: str, programming_enabled: bool = True):
    """Run SMT testing in command line mode"""
    logger = logging.getLogger(__name__)
    
    try:
        from src.core.smt_test import SMTTest
        from src.data.sku_manager import load_test_parameters
        import json
        
        logger.info(f"Starting SMT test for SKU: {sku}")
        
        # Load test parameters
        parameters = load_test_parameters(sku)
        if not parameters:
            print(f"Error: No test parameters found for SKU: {sku}")
            return False
        
        # Load programming configuration if enabled
        programming_config = None
        if programming_enabled:
            from src.data.sku_manager import SKUManager
            sku_manager = SKUManager()
            sku_data = sku_manager.get_sku(sku)
            if sku_data:
                smt_config = sku_data.get('smt_testing', {})
                programming_config = smt_config.get('programming', {})
                if not programming_config.get('enabled', False):
                    print(f"Warning: Programming not enabled for SKU {sku}")
                    programming_enabled = False
                    programming_config = None
            else:
                print("Warning: No programming configuration file found")
                programming_enabled = False
        
        # Create SMT test instance
        test = SMTTest(sku, parameters, port, programming_config)
        
        # Set up progress callback
        def progress_callback(message: str, percentage: int):
            print(f"[{percentage:3d}%] {message}")
        
        test.set_progress_callback(progress_callback)
        
        # Execute test
        print(f"\nStarting SMT test for {sku} on {port}...")
        if programming_enabled:
            print("Programming: ENABLED")
        else:
            print("Programming: DISABLED")
            
        result = test.execute()
        
        # Display results
        print(f"\nTest Result: {'PASS' if result.passed else 'FAIL'}")
        
        # Display programming results if applicable
        if programming_enabled:
            programming_results = test.get_programming_results()
            if programming_results:
                print("\nProgramming Results:")
                for prog_result in programming_results:
                    status = "PASS" if prog_result["success"] else "FAIL"
                    print(f"  {prog_result['board']}: {status}")
                    if not prog_result["success"]:
                        print(f"    Error: {prog_result['message']}")
        
        # Display measurements
        if result.measurements:
            print("\nMeasurements:")
            for name, measurement in result.measurements.items():
                if hasattr(measurement, 'value'):
                    print(f"  {name}: {measurement.value} {measurement.unit}")
        
        # Display failures
        if result.failures:
            print("\nFailures:")
            for failure in result.failures:
                print(f"  - {failure}")
        
        return result.passed
        
    except Exception as e:
        logger.error(f"SMT test error: {e}")
        print(f"Error running SMT test: {e}")
        return False


def run_smt_setup(port: str):
    """Run SMT setup utility"""
    try:
        from src.utils.smt_setup_utility import SMTSetupUtility
        
        print(f"\nRunning SMT setup utility on {port}...")
        utility = SMTSetupUtility()
        results = utility.run_diagnostics(port)
        
        return all(results.values())
        
    except Exception as e:
        print(f"Error running SMT setup: {e}")
        return False


def main():
    """Main application entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Diode Dynamics Production Test System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Run GUI mode (default)
  python main.py
  
  # Run offroad test
  python main.py offroad DD5000 COM4
  
  # Run SMT test with programming
  python main.py smt DD5001 COM5 --programming
  
  # Run SMT test without programming
  python main.py smt DD5001 COM5 --no-programming
  
  # Run SMT setup utility
  python main.py smt-setup COM5
        """
    )
    
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["gui", "offroad", "smt", "smt-setup"],
        default="gui",
        help="Test mode to run (default: gui)"
    )
    
    parser.add_argument(
        "sku",
        nargs="?",
        help="SKU to test (required for offroad/smt modes)"
    )
    
    parser.add_argument(
        "port",
        nargs="?",
        help="Arduino port (e.g., COM4 or /dev/ttyUSB0)"
    )
    
    parser.add_argument(
        "--programming",
        action="store_true",
        help="Enable programming for SMT tests"
    )
    
    parser.add_argument(
        "--no-programming",
        action="store_true",
        help="Disable programming for SMT tests"
    )
    
    parser.add_argument(
        "--test-type",
        default="FUNCTION_TEST",
        help="Test type for offroad tests (default: FUNCTION_TEST)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    print("Diode Dynamics Production Test System")
    print("=" * 40)

    # Setup logging
    setup_logging()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        
    logger = logging.getLogger(__name__)
    logger.info("Application starting...")

    # Setup directories
    try:
        setup_directories()
        logger.info("Required directories verified/created.")
    except Exception as e:
        logger.critical(f"Failed to setup directories: {e}", exc_info=True)
        print(f"CRITICAL ERROR: Failed to create necessary directories: {e}. Application cannot continue.")
        return

    # Check dependencies
    if not check_dependencies():
        logger.critical("Dependency check failed. Application cannot continue.")
        # Message already printed by check_dependencies
        return

    try:
        success = True
        
        if args.mode == "gui":
            success = run_gui_mode()
            
        elif args.mode == "offroad":
            if not args.sku or not args.port:
                print("Error: SKU and port required for offroad testing")
                print("Example: python main.py offroad DD5000 COM4")
                sys.exit(1)
            success = run_offroad_test(args.sku, args.port, args.test_type)
            
        elif args.mode == "smt":
            if not args.sku or not args.port:
                print("Error: SKU and port required for SMT testing")
                print("Example: python main.py smt DD5000 COM5 --programming")
                sys.exit(1)
                
            # Determine programming setting
            programming_enabled = True  # Default
            if args.no_programming:
                programming_enabled = False
            elif args.programming:
                programming_enabled = True
                
            success = run_smt_test(args.sku, args.port, programming_enabled)
            
        elif args.mode == "smt-setup":
            if not args.port:
                print("Error: Port required for SMT setup")
                print("Example: python main.py smt-setup COM5")
                sys.exit(1)
            success = run_smt_setup(args.port)
            
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Application error: {e}")
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # This is a top-level catch-all. Ideally, errors are caught closer to their source.
        # If logging is not set up yet (e.g., error in setup_logging itself), this won't be logged to file.
        logging.critical(f"Unhandled exception at the very top level: {e}", exc_info=True)
        print(f"CRITICAL UNHANDLED EXCEPTION: {e}")
        sys.exit(1)