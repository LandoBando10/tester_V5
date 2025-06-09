# Extended Test Sequences Documentation

## Overview

Extended test sequences in `test_sequences.json` now support comprehensive SMT panel testing configurations that include:
- Panel layouts
- Light configurations with relay mappings
- Complex test steps including RGBW cycling

## Structure

### Standard Test Sequences (e.g., SMT_SEQ_A, SMT_SEQ_B)

These remain simple and focused on power/current measurement:

```json
{
  "SMT_SEQ_A": {
    "description": "Standard SMT power sequence for single board products",
    "steps": [
      {"action": "power_on", "duration_ms": 100},
      {"action": "measure_current", "duration_ms": 500},
      {"action": "power_off", "duration_ms": 100}
    ]
  }
}
```

### Extended Panel Test Sequences

These include full panel and light configurations:

```json
{
  "SMT_DUAL_BACKLIGHT": {
    "description": "SMT panel test for boards with dual backlight configuration",
    "panel_layout": {
      "rows": 2,
      "columns": 2,
      "boards": 4
    },
    "light_configuration": {
      "mainbeam": {
        "type": "standard",
        "relay_offset": 0,
        "description": "White LED mainbeam"
      },
      "backlight1": {
        "type": "standard",
        "relay_offset": 4,
        "description": "First backlight (amber)"
      }
    },
    "steps": [
      {"action": "test_light", "light": "mainbeam", "state": "on", "duration_ms": 500}
    ]
  }
}
```

## Usage in SKU Files

### For Product Testing (Offroad/Single Board SMT)

Reference simple sequences:

```json
"smt_testing": {
  "power": {
    "sequence": "SMT_SEQ_B",
    "min_mainbeam_A": 0.55,
    "max_mainbeam_A": 0.85
  }
}
```

### For Panel Testing (Multiple Boards)

Reference extended sequences:

```json
"smt_testing": {
  "sequence": "SMT_DUAL_BACKLIGHT"
}
```

The test system will automatically detect extended sequences and use the embedded panel layout and light configuration.

## Available Extended Sequences

1. **SMT_DUAL_BACKLIGHT** - For boards with two separate backlight channels
2. **SMT_SS3_AMBER_SINGLE** - For SS3 boards with single amber backlight
3. **SMT_SS3_RGBW** - For SS3 boards with RGBW cycling backlight
4. **SMT_STATUS_LED_BOARD** - For simple status indicator boards

## Action Types

- **test_light**: Basic on/off control
  - `light`: Single name or array of names
  - `state`: "on" or "off"
  - `duration_ms`: Time to hold state

- **rgbw_cycle**: Start RGBW pattern cycling
  - `light`: RGBW light name
  - `pattern`: Contains `on_ms` and `off_ms`
  - `duration_ms`: Total cycle time

- **rgbw_test**: Sample RGBW at specific points
  - `light`: RGBW light name
  - `sample_points`: Array of millisecond offsets
  - `duration_ms`: Total test time

## Relay Offset Mapping

Each board position in a 2x2 panel uses relay offsets:
- Board 1: Base offsets (0, 4, 8, etc.)
- Board 2: Base + 12
- Board 3: Base + 24
- Board 4: Base + 36

## Migration from Old SMT Folder

The old `/config/smt/` folder files have been consolidated into extended test sequences. No need to maintain separate panel configuration files - everything is now in `test_sequences.json` for consistency and simplicity.