# Application Configuration Settings
from typing import Dict, Any, Optional
from pathlib import Path
import logging

# Configure logging for this module
logger = logging.getLogger(__name__)

# Consolidated Timeout Settings
TIMEOUTS = {
    'device_connection': 5,
    'arduino_connection': 10,
    'communication_test': 3.0,
    'part_detection': 30.0,
    'default_test': 30,
    'scale_connection': 5
}

# Device-specific Serial Communication
DEVICE_SERIAL_SETTINGS = {
    'scale': {
        'baud_rate': 9600,
        'timeout': TIMEOUTS['device_connection'],
        'write_timeout': TIMEOUTS['device_connection']
    },
    'arduino': {
        'baud_rate': 115200,
        'timeout': TIMEOUTS['device_connection'],
        'write_timeout': TIMEOUTS['device_connection']
    }
}

# Arduino Communication
ARDUINO_SETTINGS = {
    'connection_timeout': TIMEOUTS['arduino_connection'],
    'sensor_read_delay': 0.001,  # 1ms between sensor reads for high speed
    'max_retries': 3,
    'max_stored_readings': 10000,
    'communication_test_timeout': TIMEOUTS['communication_test']
}

# Sensor Reading Configurations (per test type)
SENSOR_TIMINGS = {
    'offroad_fast': {
        'current_interval_ms': 10,      # Very fast for current monitoring
        'lux_interval_ms': 50,          # Medium speed for light sensors
        'pressure_interval_ms': 100,    # Slower for pressure (less critical)
        'color_interval_ms': 50         # Medium speed for color
    },
    'offroad_normal': {
        'current_interval_ms': 25,      # Normal speed for 0.5s windows
        'lux_interval_ms': 50,
        'pressure_interval_ms': 100,
        'color_interval_ms': 50
    },
    'smt_testing': {
        'current_interval_ms': 25,      # Fast for SMT current monitoring
        'voltage_interval_ms': 25,
        'backlight_interval_ms': 100    # Slower for backlight testing
    }
}

# Test-specific sensor configurations
TEST_SENSOR_CONFIGS = {
    'offroad_standard': {
        'required_sensors': ['INA260', 'VEML7700', 'PRESSURE', 'COLOR'],
        'optional_sensors': [],
        'timing_profile': 'offroad_normal'
    },
    'offroad_precision': {
        'required_sensors': ['INA260', 'VEML7700', 'PRESSURE', 'COLOR'],
        'optional_sensors': [],
        'timing_profile': 'offroad_fast'
    },
    'smt_panel': {
        'required_sensors': ['INA260'],
        'optional_sensors': ['VEML7700'],  # For backlight testing
        'timing_profile': 'smt_testing'
    }
}

# Weight Testing Configuration (weight parameters moved to skus.json)
WEIGHT_TESTING = {
    'test_timings': {
        'part_detection_timeout': TIMEOUTS['part_detection'],
        'stabilization_time': 2.0,
        'measurement_samples': 5,
        'sample_interval': 0.2,
    },
    'integration': {
        'auto_connect_on_mode_switch': True,
        'auto_load_sku_weights': True,
        'real_time_display_update_rate': 10,
        'log_all_readings': False,
    }
}

# Scale Communication (enhanced with additional settings)
SCALE_SETTINGS = {
    'connection_timeout': TIMEOUTS['scale_connection'],
    'stable_reading_count': 3,  # number of consistent readings needed
    'reading_tolerance': 0.1,    # grams tolerance for "stable" reading
    'baud_rate': 9600,
    'supported_baud_rates': [600, 1200, 2400, 4800, 9600],
    'max_weight_readings': 1000,
    'read_interval_ms': 100,
    'communication_test_timeout': TIMEOUTS['communication_test']
}

# Test Execution
TEST_SETTINGS = {
    'default_test_timeout': TIMEOUTS['default_test'],  # seconds
    'result_display_time': 3,    # seconds to show pass/fail result
    'log_all_measurements': True,
    'sensor_stabilization_time': 2.0,  # seconds to wait after hardware setup
    'measurement_averaging_time': 1.0   # seconds to average sensor readings
}

# GUI Settings
GUI_SETTINGS = {
    'window_title': 'Diode Dynamics Production Test',
    'window_size': '900x700',
    'theme': 'default',
    'update_interval_ms': 100,  # How often to update progress/readings
    'real_time_display': True   # Show live sensor readings during test
}

# File Paths (using pathlib for cross-platform compatibility)
PATHS = {
    'sku_config': Path('config') / 'skus.json',
    'programming_config': Path('config') / 'programming_config.json',
    'log_directory': Path('logs'),
    'results_directory': Path('results'),
    'sensor_cal_directory': Path('calibration'),
    'firmware_directory': Path('firmware')
}

# Logging Configuration
LOGGING = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file_rotation': True,
    'max_log_files': 10,
    'sensor_data_logging': False  # Set to True to log all sensor readings (large files!)
}

# Configuration validation functions
def validate_serial_settings() -> bool:
    """Validate serial communication settings"""
    try:
        for device, settings in DEVICE_SERIAL_SETTINGS.items():
            baud_rate = settings.get('baud_rate')
            if baud_rate not in SCALE_SETTINGS['supported_baud_rates'] + [115200]:
                logger.error(f"Invalid baud rate for {device}: {baud_rate}")
                return False
                
            timeout = settings.get('timeout')
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                logger.error(f"Invalid timeout for {device}: {timeout}")
                return False
                
        return True
    except Exception as e:
        logger.error(f"Error validating serial settings: {e}")
        return False

def validate_timeouts() -> bool:
    """Validate all timeout values are positive"""
    try:
        for key, value in TIMEOUTS.items():
            if not isinstance(value, (int, float)) or value <= 0:
                logger.error(f"Invalid timeout value for {key}: {value}")
                return False
        return True
    except Exception as e:
        logger.error(f"Error validating timeouts: {e}")
        return False

def ensure_directories_exist() -> bool:
    """Deprecated - directories should exist already"""
    # Directory creation removed - directories should already exist
    return True

# Initialize configuration validation on import
def _initialize_config():
    """Initialize and validate configuration on module import"""
    try:
        if not validate_timeouts():
            logger.warning("Timeout validation failed")
        if not validate_serial_settings():
            logger.warning("Serial settings validation failed")
        # Directory creation removed
    except Exception as e:
        logger.error(f"Configuration initialization failed: {e}")

# Run initialization
_initialize_config()