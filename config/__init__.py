"""
Configuration module for Diode Dynamics Production Test System

This module provides centralized access to all configuration settings.
For SKU-specific data, use src.data.sku_manager directly.
"""

# Import main configuration dictionaries from settings
from .settings import (
    TIMEOUTS,
    DEVICE_SERIAL_SETTINGS,
    ARDUINO_SETTINGS,
    SENSOR_TIMINGS,
    TEST_SENSOR_CONFIGS,
    WEIGHT_TESTING,
    SCALE_SETTINGS,
    TEST_SETTINGS,
    GUI_SETTINGS,
    PRESSURE_SETTINGS,
    PROGRAMMING_SETTINGS,
    PATHS,
    LOGGING
)

# Define what's available when using "from config import *"
__all__ = [
    'TIMEOUTS',
    'DEVICE_SERIAL_SETTINGS',
    'ARDUINO_SETTINGS',
    'SENSOR_TIMINGS',
    'TEST_SENSOR_CONFIGS',
    'WEIGHT_TESTING',
    'SCALE_SETTINGS',
    'TEST_SETTINGS',
    'GUI_SETTINGS',
    'PRESSURE_SETTINGS',
    'PROGRAMMING_SETTINGS',
    'PATHS',
    'LOGGING'
]

# Module version
__version__ = '2.0.0'