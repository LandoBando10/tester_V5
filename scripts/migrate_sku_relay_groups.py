#!/usr/bin/env python3
"""
SKU Migration Tool - Convert individual relay mappings to grouped format
This tool converts SKU files from the old format (individual relays) to the
new format (comma-separated relay groups for simultaneous activation).
"""

import json
import argparse
import shutil
from pathlib import Path
from typing import Dict, Any, List, Tuple


def group_relays_by_function(relay_mapping: Dict[str, Any]) -> Dict[Tuple[int, str], List[str]]:
    """
    Group relays by board and function
    
    Returns:
        Dict mapping (board, function) to list of relay numbers
    """
    groups = {}
    
    for relay_str, mapping in relay_mapping.items():
        if mapping is None:
            continue
            
        board = mapping.get("board")
        function = mapping.get("function")
        
        if board and function:
            key = (board, function)
            if key not in groups:
                groups[key] = []
            groups[key].append(relay_str)
    
    return groups


def create_grouped_mapping(relay_groups: Dict[Tuple[int, str], List[str]]) -> Dict[str, Any]:
    """
    Create new relay mapping with comma-separated groups
    """
    new_mapping = {}
    
    for (board, function), relays in relay_groups.items():
        # Sort relay numbers for consistency
        sorted_relays = sorted(relays, key=lambda x: int(x))
        
        # Create comma-separated key if multiple relays
        if len(sorted_relays) > 1:
            relay_key = ",".join(sorted_relays)
        else:
            relay_key = sorted_relays[0]
        
        new_mapping[relay_key] = {
            "board": board,
            "function": function
        }
    
    return new_mapping


def migrate_sku_file(file_path: Path, backup: bool = True) -> bool:
    """
    Migrate a single SKU file to the new format
    
    Args:
        file_path: Path to the SKU JSON file
        backup: Whether to create a backup of the original file
        
    Returns:
        True if migration was successful
    """
    try:
        # Read the original file
        with open(file_path, 'r') as f:
            sku_data = json.load(f)
        
        # Check if it has relay_mapping
        if 'relay_mapping' not in sku_data:
            print(f"  Skipping {file_path.name} - no relay_mapping found")
            return True
        
        relay_mapping = sku_data['relay_mapping']
        
        # Check if already migrated (has comma-separated keys)
        has_groups = any(',' in key for key in relay_mapping.keys() if key)
        if has_groups:
            print(f"  Skipping {file_path.name} - already migrated")
            return True
        
        # Create backup if requested
        if backup:
            backup_path = file_path.with_suffix('.json.bak')
            shutil.copy2(file_path, backup_path)
            print(f"  Created backup: {backup_path.name}")
        
        # Group relays by board and function
        relay_groups = group_relays_by_function(relay_mapping)
        
        # Create new grouped mapping
        new_mapping = create_grouped_mapping(relay_groups)
        
        # Update the SKU data
        sku_data['relay_mapping'] = new_mapping
        
        # Add a note about the migration
        if 'notes' not in sku_data:
            sku_data['notes'] = []
        elif isinstance(sku_data['notes'], str):
            sku_data['notes'] = [sku_data['notes']]
        
        sku_data['notes'].append("Migrated to grouped relay format for simultaneous activation")
        
        # Write the updated file
        with open(file_path, 'w') as f:
            json.dump(sku_data, f, indent=2)
        
        # Report changes
        old_count = len([k for k in relay_mapping.keys() if relay_mapping[k]])
        new_count = len(new_mapping)
        print(f"  Migrated {file_path.name}: {old_count} relays -> {new_count} groups")
        
        # Show the groupings
        for (board, function), relays in sorted(relay_groups.items()):
            if len(relays) > 1:
                print(f"    Board {board} {function}: relays {','.join(sorted(relays, key=int))}")
        
        return True
        
    except Exception as e:
        print(f"  ERROR migrating {file_path.name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Migrate SKU files to grouped relay format')
    parser.add_argument('path', nargs='?', default='config/skus/smt',
                        help='Path to SKU directory or file (default: config/skus/smt)')
    parser.add_argument('--no-backup', action='store_true',
                        help='Do not create backup files')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    path = Path(args.path)
    
    if not path.exists():
        print(f"Error: Path {path} does not exist")
        return 1
    
    # Collect all JSON files to process
    if path.is_file():
        json_files = [path] if path.suffix == '.json' else []
    else:
        json_files = list(path.glob('*.json'))
    
    if not json_files:
        print("No JSON files found to migrate")
        return 0
    
    print(f"Found {len(json_files)} JSON files to process")
    
    if args.dry_run:
        print("\nDRY RUN - No files will be modified")
    
    print("\nProcessing files:")
    
    success_count = 0
    for json_file in json_files:
        print(f"\n{json_file}:")
        
        if args.dry_run:
            # Just analyze without modifying
            try:
                with open(json_file, 'r') as f:
                    sku_data = json.load(f)
                
                if 'relay_mapping' in sku_data:
                    relay_mapping = sku_data['relay_mapping']
                    has_groups = any(',' in key for key in relay_mapping.keys() if key)
                    
                    if has_groups:
                        print(f"  Already migrated")
                    else:
                        relay_groups = group_relays_by_function(relay_mapping)
                        print(f"  Would create {len(relay_groups)} groups from {len(relay_mapping)} relays")
                        for (board, function), relays in sorted(relay_groups.items()):
                            if len(relays) > 1:
                                print(f"    Board {board} {function}: would group relays {','.join(sorted(relays, key=int))}")
                else:
                    print(f"  No relay_mapping found")
                    
                success_count += 1
            except Exception as e:
                print(f"  ERROR: {e}")
        else:
            # Actually migrate the file
            if migrate_sku_file(json_file, backup=not args.no_backup):
                success_count += 1
    
    print(f"\nProcessed {success_count}/{len(json_files)} files successfully")
    
    return 0 if success_count == len(json_files) else 1


if __name__ == '__main__':
    exit(main())