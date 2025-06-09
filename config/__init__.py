"""
Configuration module for Diode Dynamics Production Test System

This module provides centralized access to all configuration settings
and utilities for the test system.
"""

# Import main configuration dictionaries from settings
from .settings import (
    DEVICE_SERIAL_SETTINGS,
    ARDUINO_SETTINGS,
    SENSOR_TIMINGS,
    TEST_SENSOR_CONFIGS,
    WEIGHT_TESTING,
    SCALE_SETTINGS,
    TEST_SETTINGS,
    GUI_SETTINGS,
    PATHS,
    LOGGING
)

# Import configuration utilities
from .config_utils import (
    load_test_parameters,
    get_weight_parameters,
    load_programming_config,
    load_sku_config,
    load_individual_sku_config,
    load_template,
    get_all_available_skus,
    resolve_template_references,
    get_full_sku_config,
    validate_config
)

# Define what's available when using "from config import *"
__all__ = [
    # Settings dictionaries
    'DEVICE_SERIAL_SETTINGS',
    'ARDUINO_SETTINGS',
    'SENSOR_TIMINGS',
    'TEST_SENSOR_CONFIGS',
    'WEIGHT_TESTING',
    'SCALE_SETTINGS',
    'TEST_SETTINGS',
    'GUI_SETTINGS',
    'PATHS',
    'LOGGING',
    # Utility functions
    'load_test_parameters',
    'get_weight_parameters',
    'load_programming_config',
    'load_sku_config',
    'load_individual_sku_config',
    'load_template',
    'get_all_available_skus',
    'resolve_template_references',
    'get_full_sku_config',
    'validate_config'
]

# Module version
__version__ = '1.0.0'