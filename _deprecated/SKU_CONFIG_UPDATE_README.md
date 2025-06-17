# SKU Configuration Update - Quick Start Guide

## Overview
This update modernizes the SKU configuration system for the Diode Dynamics Tester V5 to support the new GUI configuration editor.

## Files Provided

1. **migrate_sku_config.py** - Migration script to convert existing SKU files
2. **sku_manager_updated.py** - Updated SKU manager with unified configuration support
3. **Migration Instructions** - Detailed step-by-step guide

## Quick Migration Steps

### 1. Backup Your Data
```bash
# Manually backup your config directory first
xcopy /E /I config config_backup_manual
```

### 2. Run the Migration
```bash
cd C:\Users\ldev2\Tester_V5\tester_V5
python migrate_sku_config.py --project-root .
```

### 3. Update SKU Manager
```bash
# Backup original
copy src\data\sku_manager.py src\data\sku_manager_original.py

# Replace with updated version
copy sku_manager_updated.py src\data\sku_manager.py
```

### 4. Verify Results
- Check `config/skus.json` was created
- Check `config/programming_config.json` was created
- Launch the GUI configuration editor to test

## What Changes

### Before (Individual Files):
```
config/skus/
├── DD5001.json
├── DD5002.json
└── SL0224P01-ABL.json
```

### After (Unified Configuration):
```
config/
├── skus.json              # All SKU definitions
├── programming_config.json # Programming configurations
└── skus/                  # Original files preserved
```

## Key Benefits

- **GUI Editor Support**: Full compatibility with the configuration editor
- **Centralized Management**: All SKUs in one file
- **Better Organization**: Separate programming configurations
- **Backward Compatible**: Can still read old format if needed

## Troubleshooting

If migration fails:
1. Check error messages in console
2. Verify all JSON files are valid
3. Check file permissions
4. Review backup in `config/backups/`

## Support

For issues or questions:
- Review the detailed migration instructions
- Check the migration summary output
- Original files are preserved in backups

## Next Steps

After successful migration:
1. Test all SKUs in the GUI editor
2. Update any custom scripts that directly read SKU files
3. Use the GUI editor for future SKU management
