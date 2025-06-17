# Configuration Editor - Quick Setup Instructions

## What This Does
Makes the GUI configuration editor work with your existing SKU JSON files without changing them.

## Setup Steps

### 1. Format Adapter Already Created
The file `format_adapter.py` has been created in:
```
src/gui/components/config/format_adapter.py
```

This adapter automatically converts between your file format and what the GUI expects.

### 2. Update the Configuration Editor
You need to update `config_editor.py` to use the adapter.

The main changes needed in `config_editor.py`:

1. Add import at the top:
```python
from .format_adapter import SKUFormatAdapter
```

2. In `__init__`, add:
```python
self.adapter = SKUFormatAdapter()
```

3. When loading SKU data, convert it:
```python
# Convert to GUI format using adapter
gui_data = self.adapter.from_file_to_gui(sku_info)
```

4. When saving SKU data, convert it back:
```python
# Convert GUI format back to file format
file_data = self.adapter.from_gui_to_file(gui_data)
```

### 3. Test It
1. Open the configuration editor
2. Select any SKU - it should load correctly
3. Make changes and save - your file format is preserved

## Key Points
- Your SKU files stay exactly the same
- No migration needed
- GUI works with your existing format
- All conversions happen automatically

## Example
Your files keep using:
- `pod_type` (not `pod_type_ref`)
- `power_level` (not `power_level_ref`)
- `offroad_testing`, `smt_testing`, `weight_testing`

The GUI internally sees the format it expects, but saves back in your format.

## Need the Full Updated config_editor.py?
The updated version is available in the artifacts above. It includes all the necessary changes to work with your existing SKU format.
