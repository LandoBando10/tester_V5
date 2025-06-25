# Statistical Process Control (SPC) Implementation for SMT Current Testing

## Overview

This document describes the implementation of Statistical Process Control (SPC) for SMT tester current measurements. The system implements X-bar and R control charts to monitor process stability and calculate control limits for production use.

## Key Features

1. **Automatic Data Collection**: Measurements are automatically collected during normal testing
2. **X-bar and R Charts**: Industry-standard control charts for monitoring process mean and variation
3. **Control Limit Calculation**: Automatic calculation of Upper Control Limit (UCL), Center Line (CL), and Lower Control Limit (LCL)
4. **Process Capability Analysis**: Cp and Cpk calculations to assess process capability
5. **Real-time Visualization**: Live control charts with out-of-control detection
6. **Production Integration**: Seamless integration with existing SMT test flow

## System Architecture

### Core Components

1. **SPCCalculator** (`spc_calculator.py`)
   - Calculates control limits from sample data
   - Implements Western Electric rules for out-of-control detection
   - Calculates process capability indices (Cp, Cpk)

2. **SPCDataCollector** (`data_collector.py`)
   - Manages sample collection and subgroup formation
   - Stores data persistently for historical analysis
   - Triggers control limit updates when sufficient data is available

3. **SPCWidget** (`spc_widget.py`)
   - Provides GUI for SPC visualization and control
   - Displays real-time control charts
   - Shows process status and capability metrics

4. **SPCIntegration** (`spc_integration.py`)
   - Integrates SPC with existing SMT test flow
   - Supports both sampling mode (data collection) and production mode (limit enforcement)

## How It Works

### 1. Data Collection Phase (Sampling Mode)

During the sampling phase, the system collects current measurements from production tests:

```python
# In your SMT test configuration
spc_config = {
    'enabled': True,
    'sampling_mode': True,    # Collect data
    'production_mode': False  # Don't enforce limits yet
}

# Data is automatically collected during tests
# System groups measurements into subgroups (default size: 5)
# After 30+ individual measurements (6 subgroups), control limits are calculated
```

### 2. Control Limit Calculation

The system uses standard SPC formulas:

**X-bar Chart (Process Mean):**
- UCL = X̄ + A₂ × R̄
- CL = X̄ (grand mean)
- LCL = X̄ - A₂ × R̄

**R Chart (Process Variation):**
- UCL = D₄ × R̄
- CL = R̄ (average range)
- LCL = D₃ × R̄

Where:
- X̄ = Grand mean (average of subgroup means)
- R̄ = Average range (average of subgroup ranges)
- A₂, D₃, D₄ = Control chart constants based on subgroup size

### 3. Specification Derivation (When No Specs Exist)

The system can automatically derive specification limits based on process capability:

```python
# System automatically derives specs when no engineering specs exist
# Target: Cp = 1.33 (industry standard for capable process)

# Derivation formula:
σ_within = R̄ / d2  # Process standard deviation
LSL = X̄̄ - 4 * σ_within  # Lower Spec Limit
USL = X̄̄ + 4 * σ_within  # Upper Spec Limit

# This ensures Cp = (USL-LSL)/(6σ) = 8σ/6σ = 1.33
```

Benefits:
- No engineering specs needed
- Specs automatically adapt to process capability
- Guarantees achievable targets
- Maintains industry-standard capability

### 4. Production Phase (Production Mode)

Once control limits are established:

```python
spc_config = {
    'enabled': True,
    'sampling_mode': False,   # Stop collecting new samples
    'production_mode': True   # Enforce control limits
}

# Measurements outside control limits will fail the test
# Provides more sensitive detection than fixed specification limits
```

## Implementation Guide

### Step 1: Enable SPC in SMT Test

Modify your test execution to include SPC configuration:

```python
from src.core.smt_test import SMTTest

# Create test with SPC enabled
test = SMTTest(
    sku="DD5001",
    parameters=parameters,
    port="COM4",
    programming_config=prog_config,
    spc_config={
        'enabled': True,
        'sampling_mode': True,
        'production_mode': False
    }
)

# Run test - data will be collected automatically
result = test.execute()
```

### Step 2: Add SPC Widget to GUI

In your main window, add the SPC control widget:

```python
from src.spc import SPCWidget

# In your MainWindow class
self.spc_widget = SPCWidget()
self.spc_widget.update_sku_list(available_skus)

# Add to layout or tab widget
self.tab_widget.addTab(self.spc_widget, "SPC Control")

# Connect test results to SPC
def on_test_complete(result):
    if result.passed:
        self.spc_widget.add_test_results(sku, result.to_dict())
```

### Step 3: Monitor Control Charts

The SPC widget provides:
- Real-time X-bar and R charts
- Control limit display
- Process capability metrics (Cp, Cpk)
- Data collection progress

### Step 4: Export Control Limits

Once you have sufficient data:

```python
# Export limits for production use
spc_integration.export_production_limits(
    Path("production_limits.json")
)
```

### Step 5: Switch to Production Mode

Load limits and enforce them in production:

```python
# Load production limits
spc_integration.load_production_limits(
    Path("production_limits.json")
)

# Enable production mode
spc_config = {
    'enabled': True,
    'sampling_mode': False,
    'production_mode': True
}
```

## Control Chart Interpretation

### X-bar Chart
- Shows the average (mean) of each subgroup
- Monitors process centering
- Points outside limits indicate shift in process mean

### R Chart
- Shows the range (max - min) of each subgroup
- Monitors process variation
- Points outside limits indicate change in process consistency

### Out-of-Control Conditions

The system checks for:
1. **Points outside control limits** - Immediate process issue
2. **Run of 9 points on one side of centerline** - Process shift
3. **6 points steadily increasing/decreasing** - Trend
4. **2 of 3 points beyond 2-sigma** - Increased variation

## Benefits for Production

1. **Earlier Detection**: Control limits are typically tighter than specification limits
2. **Process Understanding**: Separates common cause from special cause variation
3. **Continuous Improvement**: Track process capability over time
4. **Reduced Scrap**: Catch process issues before producing bad parts
5. **Data-Driven Decisions**: Base limits on actual process performance

## Example Workflow

### Initial Setup (Day 1)
1. Enable SPC in sampling mode
2. Run normal production (30+ units)
3. After 30 measurements, system automatically:
   - Calculates control limits
   - Derives spec limits if none exist (targets Cp=1.33)
4. Review control charts and capability indices

### Validation (Day 2)
1. Continue sampling to verify stability
2. Review derived spec limits
3. Optionally force recalculation of specs
4. Document baseline process capability

### Production Implementation (Day 3+)
1. Switch to production mode
2. System enforces both spec and control limits
3. Monitor for out-of-control conditions
4. Recalculate limits periodically (weekly/monthly)

### Recalculating Spec Limits
To force recalculation of spec limits (even if they exist):
```python
from src.spc.data_collector import SPCDataCollector

collector = SPCDataCollector()
# Recalculate for specific function/board
collector.force_recalculate_specs("DD5001", "mainbeam", "Board_1")

# Recalculate all specs for a SKU
collector.recalculate_all_specs("DD5001")
```

## Configuration Options

### Subgroup Size
- Default: 5 samples
- Range: 2-10 samples
- Larger subgroups = more sensitive to mean shifts
- Smaller subgroups = more sensitive to variation changes

### Minimum Requirements
- Default: 30 individual measurements (6 subgroups of 5)
- Minimum for spec derivation: 30 measurements
- Minimum for control limits: 6 subgroups
- More data = more reliable limits
- Absolute minimum: 5 subgroups (for analysis only)

### Control Limit Multiplier
- Default: 3-sigma (99.73% coverage)
- Can adjust for tighter/looser control

## File Structure

SPC data is stored in:
```
spc_data/
├── DD5001_mainbeam_Board_1_subgroups.json    # Raw subgroup data
├── DD5001_mainbeam_Board_1_limits.json       # Calculated limits
├── DD5001_backlight_left_Board_1_subgroups.json
├── DD5001_backlight_left_Board_1_limits.json
└── ...
```

## Troubleshooting

### "Not enough data" message
- Need minimum 5 subgroups to calculate limits
- Check that measurements are being collected
- Verify SKU/function/board selection

### Control limits seem too tight/loose
- Check subgroup size is appropriate
- Verify process is stable during sampling
- Consider removing outliers from initial data

### Charts not updating
- Ensure auto-update is enabled
- Check that tests are completing successfully
- Verify data files are being created

## Best Practices

1. **Establish Baseline**: Collect data during stable production
2. **Regular Review**: Monitor control charts daily
3. **Investigate Violations**: Don't ignore out-of-control signals
4. **Periodic Recalculation**: Update limits as process improves
5. **Training**: Ensure operators understand SPC concepts

## Technical Details

### Statistical Constants

The system uses standard control chart constants:

| n | A₂    | D₃    | D₄    | d₂    |
|---|-------|-------|-------|-------|
| 2 | 1.880 | 0.000 | 3.267 | 1.128 |
| 3 | 1.023 | 0.000 | 2.574 | 1.693 |
| 4 | 0.729 | 0.000 | 2.282 | 2.059 |
| 5 | 0.577 | 0.000 | 2.114 | 2.326 |
| 6 | 0.483 | 0.000 | 2.004 | 2.534 |

### Process Capability

**Cp (Process Capability):**
```
Cp = (USL - LSL) / (6σ)
```
- Measures potential capability
- Cp > 1.33 is generally acceptable
- Cp > 1.67 is good

**Cpk (Process Capability Index):**
```
Cpk = min[(USL - μ) / 3σ, (μ - LSL) / 3σ]
```
- Measures actual capability (includes centering)
- Cpk > 1.33 is generally acceptable
- Cpk > 1.67 is good

## Integration Example

Here's a complete example of integrating SPC into your existing SMT test:

```python
# In your test handler
from src.spc import SPCIntegration

class SMTTestHandler:
    def __init__(self):
        self.spc = SPCIntegration(
            spc_enabled=True,
            sampling_mode=True
        )
        
    def run_test(self, sku, parameters):
        # Run normal test
        test = SMTTest(sku, parameters, port, spc_config={
            'enabled': True,
            'sampling_mode': self.spc.sampling_mode,
            'production_mode': self.spc.production_mode
        })
        
        result = test.execute()
        
        # Process through SPC
        spc_results = self.spc.process_test_results(sku, result.to_dict())
        
        # Update GUI
        self.update_spc_display(spc_results)
        
        return result
```

## Future Enhancements

1. **Automated Limit Updates**: Recalculate limits on schedule
2. **Multi-variate Control**: Monitor multiple parameters simultaneously
3. **Predictive Analytics**: Detect trends before limits are exceeded
4. **Integration with MES**: Export data to manufacturing execution systems
5. **Mobile Alerts**: Notify engineers of out-of-control conditions

## Conclusion

This SPC implementation provides a robust framework for monitoring and controlling your SMT current testing process. By collecting data during normal production and calculating control limits based on actual process performance, you can detect issues earlier and maintain tighter process control than with fixed specification limits alone.

The system is designed to integrate seamlessly with your existing test flow while providing powerful statistical analysis capabilities. Start with sampling mode to establish your baseline, then transition to production mode for ongoing monitoring and control.
