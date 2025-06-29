"""
SPC Configuration Constants
Central configuration for Statistical Process Control system
"""

# Subgroup configuration
SUBGROUP_SIZE = 5
MIN_INDIVIDUAL_MEASUREMENTS = 30  # Minimum individual measurements needed
BASELINE_SUBGROUPS = 6  # Minimum subgroups (30 measurements / 5 per subgroup)
MAX_HISTORICAL_SUBGROUPS = 100  # Maximum subgroups to retain in rolling window

# Statistical constants
TARGET_CAPABILITY = 1.33  # Target Cp and Cpk
CONFIDENCE_LEVEL = 3.0   # Number of sigma for control limits

# Spec derivation constants (when no engineering specs available)
SPEC_SIGMA_MULTIPLIER = 4.0  # For Cp=1.33: USL/LSL = mean ± 4*sigma
SPEC_MARGIN_FACTOR = 1.0     # Additional safety margin (1.0 = no extra margin)

# Process monitoring
ROLLING_WINDOW_DAYS = 30  # Days to include in rolling calculations
MIN_SUBGROUPS_FOR_ANALYSIS = 5  # Absolute minimum for any calculations

# Control chart constants for different subgroup sizes
CONTROL_CONSTANTS = {
    2: {'A2': 1.880, 'D3': 0.000, 'D4': 3.267, 'd2': 1.128},
    3: {'A2': 1.023, 'D3': 0.000, 'D4': 2.574, 'd2': 1.693},
    4: {'A2': 0.729, 'D3': 0.000, 'D4': 2.282, 'd2': 2.059},
    5: {'A2': 0.577, 'D3': 0.000, 'D4': 2.114, 'd2': 2.326},
    6: {'A2': 0.483, 'D3': 0.000, 'D4': 2.004, 'd2': 2.534},
    7: {'A2': 0.419, 'D3': 0.076, 'D4': 1.924, 'd2': 2.704},
    8: {'A2': 0.373, 'D3': 0.136, 'D4': 1.864, 'd2': 2.847},
    9: {'A2': 0.337, 'D3': 0.184, 'D4': 1.816, 'd2': 2.970},
    10: {'A2': 0.308, 'D3': 0.223, 'D4': 1.777, 'd2': 3.078}
}

# UI update intervals
SPC_DISPLAY_UPDATE_INTERVAL_MS = 5000

# File naming patterns
SUBGROUP_FILE_PATTERN = "{sku}_{function}_{board}_subgroups.json"
LIMITS_FILE_PATTERN = "{sku}_{function}_{board}_limits.json"
SPECS_FILE_PATTERN = "{sku}_{function}_{board}_specs.json"

# Arduino/SMT controller settings
SMT_COMMAND_TIMEOUT = 2.0
SMT_MAX_RETRIES = 3
SMT_RETRY_DELAY = 0.1
ARDUINO_STABILIZATION_TIME = 1.0
STARTUP_MESSAGE_TIMEOUT = 0.5
SERIAL_IDLE_DELAY = 0.02