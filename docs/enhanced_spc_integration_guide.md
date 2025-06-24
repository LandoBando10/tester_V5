# Enhanced SPC Widget Integration Guide

## Overview

The Enhanced SPC Widget provides comprehensive per-SKU mode control and visualization for Statistical Process Control. This guide explains how to integrate and use the new widget.

## Key Features

### 1. Per-SKU Mode Configuration
- **Independent mode settings** for each SKU
- **Three control options**:
  - SPC Enabled/Disabled
  - Sampling Mode (collect data, update limits)
  - Production Mode (enforce limits)
- **Mode persistence** across sessions
- **Visual mode status** indicators

### 2. Enhanced Visualization
- **Dual control charts** (X-bar and R charts)
- **Specification limit overlay** (optional)
- **Violation highlighting** with rule annotations
- **Real-time updates** (5-second refresh)

### 3. Three-Tab Interface

#### Control Charts Tab
- SKU/Function/Board selection
- Mode configuration controls
- Live control charts
- Process status display
- Specification management buttons

#### Data Analysis Tab
- Detailed statistical analysis
- Trend detection
- Period selection (25/50/100 subgroups or all)
- Export to text report

#### Configuration Tab
- Overview of all SKU mode settings
- SPC parameter reference
- System configuration summary

## Integration Steps

### 1. Replace the existing SPC widget

In your SMT handler or main window:

```python
from src.spc.enhanced_spc_widget import EnhancedSPCWidget

# Instead of:
# self.spc_widget = SPCControlWidget()

# Use:
self.spc_widget = EnhancedSPCWidget(spc_integration=self.spc_integration)
```

### 2. Connect to SPC Integration

```python
# In your SMT handler
if self.spc_integration:
    self.spc_widget.set_spc_integration(self.spc_integration)
    
    # Connect signals
    self.spc_widget.mode_changed.connect(self.on_spc_mode_changed)
    self.spc_widget.spec_approval_requested.connect(
        lambda sku: self.spc_integration.show_spec_approval_dialog(sku, self)
    )
```

### 3. Update SKU list when available

```python
# When SKUs are loaded
available_skus = self.get_available_skus()
self.spc_widget.update_sku_list(available_skus)
```

## Usage Workflow

### Initial Setup (New SKU)

1. **Select SKU** from dropdown
2. **Enable SPC** checkbox
3. **Enable Sampling Mode** to start collecting data
4. **Keep Production Mode OFF** initially
5. Run tests until 30+ measurements collected
6. **Click "Derive Specs"** to calculate specification limits
7. Review and approve proposed specifications

### Transition to Production

1. Review control charts for stability
2. Verify Cpk ≥ 1.33 (shown in status)
3. **Enable Production Mode** checkbox
4. Keep Sampling Mode ON for continuous improvement

### Runtime Mode Changes

1. Select SKU from dropdown
2. Toggle mode checkboxes as needed
3. Changes take effect immediately
4. Mode settings persist across sessions

## Mode Configuration Storage

Mode configurations are stored in `config/spc_mode_config.json`:

```json
{
  "DD5001": {
    "enabled": true,
    "sampling_mode": true,
    "production_mode": true
  },
  "DD5002": {
    "enabled": true,
    "sampling_mode": true,
    "production_mode": false
  }
}
```

## API Reference

### Signals

```python
# Mode configuration changed
mode_changed = Signal(str, dict)  # SKU, config dict

# Control limits updated
limits_updated = Signal(str, dict)  # SKU, limits dict

# Spec approval requested
spec_approval_requested = Signal(str)  # SKU
```

### Key Methods

```python
# Update available SKUs
widget.update_sku_list(skus: List[str])

# Set SPC integration
widget.set_spc_integration(integration: SPCIntegration)

# Add test results manually
widget.add_test_results(sku: str, test_results: dict)

# Force refresh display
widget.refresh_display()

# Export report
widget.export_report()
```

## Visual Indicators

### Mode Status Colors
- **Gray**: SPC Disabled
- **Blue**: Sampling Mode only
- **Green**: Production Mode active
- **Orange**: SPC Enabled but no active mode

### Process Capability Status
- **Green**: Excellent (Cpk ≥ 1.33)
- **Orange**: Acceptable (1.0 ≤ Cpk < 1.33)
- **Red**: Poor (Cpk < 1.0)

### Chart Features
- **Red dashed lines**: Control limits (UCL/LCL)
- **Green solid line**: Center line (CL)
- **Orange dotted lines**: Specification limits (USL/LSL)
- **Red circles**: Out-of-control points with rule annotations

## Troubleshooting

### No data displayed
- Verify SKU has been tested in sampling mode
- Check `spc_data/` directory for data files
- Ensure correct function/board selection

### Modes not saving
- Check write permissions for `config/` directory
- Verify `spc_mode_config.json` is not corrupted

### Charts not updating
- Ensure "Auto Update" is checked
- Verify SPC integration is connected
- Check for errors in console/logs

## Best Practices

1. **Always start with Sampling Mode** for new SKUs
2. **Keep both modes active** in production for continuous improvement
3. **Review control charts** before enabling Production Mode
4. **Use "Derive Specs"** when no engineering specs exist
5. **Export reports** periodically for documentation
6. **Monitor Cpk** to ensure process capability

## Migration from Basic Widget

The enhanced widget is backward compatible. To migrate:

1. Replace widget import and instantiation
2. Existing data and limits are preserved
3. Mode configuration defaults to sampling-only
4. No changes needed to data collection code