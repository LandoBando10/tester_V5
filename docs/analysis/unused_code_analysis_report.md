# Unused Code Analysis Report

## Executive Summary

This analysis identified significant opportunities for code cleanup across the codebase:
- **93 unused imports** across various modules
- **417 potentially dead functions/methods** (includes some false positives)
- **2 identical duplicate files** (arduino_controller.py and offroad_arduino_controller.py)
- **Multiple duplicate implementations** of SPC widgets and other components
- **35 files with commented-out code blocks**
- **5 files in the 'delete' directory** that may contain duplicate functionality

## Critical Issues

### 1. Completely Duplicate Files
- `/src/hardware/arduino_controller.py` and `/src/hardware/offroad_arduino_controller.py` are **identical files** (same MD5 hash)
- Recommendation: Delete one and update all references to use a single file

### 2. Duplicate SPC Widget Implementations
- `src/spc/spc_widget.py` - Uses PyQt5
- `src/spc/enhanced_spc_widget.py` - Uses PySide6 (appears to be the newer version)
- Recommendation: Consolidate to use only the enhanced version with PySide6

### 3. Unused Imports by Category

#### Most Common Unused Imports:
- `typing` module imports (Any, Dict, Optional, List, Tuple) - 26 occurrences
- Qt-related imports (Qt, QTimer, QPainter, etc.) - 15 occurrences
- Standard library imports (json, time, os, sys) - 12 occurrences
- numpy and matplotlib - 8 occurrences

#### Files with Most Unused Imports:
1. `src/gui/main_window.py` - 6 unused imports
2. `src/gui/components/config/program_config.py` - 4 unused imports
3. `src/spc/enhanced_spc_widget.py` - 5 unused imports

### 4. Dead Code Hotspots

#### Modules with Most Dead Code:
1. `src/gui/main_window.py` - 26 potentially unused methods
2. `src/gui/components/config/program_config.py` - 32 potentially unused methods
3. `src/hardware/serial_manager.py` - 22 potentially unused methods
4. `src/gui/components/connection_dialog.py` - 12 potentially unused methods

### 5. Files in 'delete' Directory

The following files should be reviewed and removed if no longer needed:
- `clean_cache.py`
- `demo_batch_testing.py`
- `old_vs_new_comparison.py`
- `test_compatibility.py`
- `test_panel_performance.py` - Appears to test old vs new SMT panel testing approaches
- `test_transitions.py` - Tests video/splash screen transitions

### 6. Unused Configuration Options

In `config/settings.py`:
- `SENSOR_TIMINGS` and `TEST_SENSOR_CONFIGS` - Referenced in imports but never used
- `ensure_directories_exist()` function - Marked as deprecated but still present

## Recommendations

### Immediate Actions (High Priority):
1. **Delete `src/hardware/offroad_arduino_controller.py`** and update all imports to use `arduino_controller.py`
2. **Remove all files in the 'delete' directory** after confirming they're not needed
3. **Remove unused imports** using an automated tool like `autoflake`:
   ```bash
   autoflake --in-place --remove-all-unused-imports --recursive src/
   ```

### Medium Priority:
1. **Consolidate SPC widgets** - Keep only `enhanced_spc_widget.py` and remove the older PyQt5 version
2. **Review and remove dead code** - Focus on the hotspot modules identified above
3. **Clean up commented code** - Remove or properly implement commented-out code blocks

### Low Priority:
1. **Review duplicate function signatures** - Some may be intentional (inheritance), but others could be consolidated
2. **Update configuration files** - Remove deprecated settings and functions
3. **Consider using a linter** - Set up `pylint` or `flake8` with CI/CD to prevent future accumulation of unused code

## Tools for Ongoing Maintenance

1. **autoflake** - Removes unused imports and variables
2. **vulture** - Finds dead code
3. **pylint** - General code quality and unused code detection
4. **pre-commit hooks** - Automate cleanup before commits

## File-by-File Unused Import Details

### High-Impact Files (3+ unused imports):

#### `main.py`
- `PySide6.QtCore.QPropertyAnimation`
- `PySide6.QtCore.QTimer`
- `json`

#### `src/gui/main_window.py`
- `PySide6.QtCore.Qt`
- `src.gui.components.config_loading_dialog.ConfigLoadingDialog`
- `src.gui.components.config_loading_dialog.MinimalProgressDialog`
- `src.gui.components.header_bar.HeaderBar`
- `src.gui.components.header_bar.get_window_icon`

#### `src/core/smt_test.py`
- `json`
- `threading`
- `time`
- `typing.Tuple`

#### `src/spc/enhanced_spc_widget.py`
- `PySide6.QtGui.QIcon`
- `matplotlib.backends.backend_qt5agg.FigureCanvasQTAgg`
- `matplotlib.pyplot`
- `numpy`
- `src.gui.components.spec_approval_dialog.SpecApprovalDialog`
- `typing.Tuple`

This analysis provides a roadmap for cleaning up the codebase and improving maintainability.