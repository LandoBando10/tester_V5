#!/usr/bin/env python3
"""
Cleanup script for logs and results directories
Removes old log files and test results to save disk space
"""

import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta


def get_file_age_days(file_path):
    """Get age of file in days"""
    stat = os.stat(file_path)
    age = time.time() - stat.st_mtime
    return age / (24 * 3600)


def cleanup_directory(directory, days_to_keep=7, dry_run=False):
    """Clean up old files in a directory"""
    if not os.path.exists(directory):
        print(f"Directory {directory} does not exist")
        return 0
    
    removed_count = 0
    total_size = 0
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            
            # Skip if file is newer than threshold
            if get_file_age_days(file_path) < days_to_keep:
                continue
            
            # Get file size before removal
            file_size = os.path.getsize(file_path)
            
            if dry_run:
                print(f"Would remove: {file_path} ({file_size / 1024:.1f} KB)")
            else:
                try:
                    os.remove(file_path)
                    print(f"Removed: {file_path} ({file_size / 1024:.1f} KB)")
                    removed_count += 1
                    total_size += file_size
                except Exception as e:
                    print(f"Error removing {file_path}: {e}")
    
    return removed_count, total_size


def main():
    parser = argparse.ArgumentParser(description="Clean up old log and result files")
    parser.add_argument(
        "--days", 
        type=int, 
        default=7,
        help="Number of days to keep files (default: 7)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--logs",
        action="store_true",
        help="Clean up logs directory"
    )
    parser.add_argument(
        "--results",
        action="store_true",
        help="Clean up results directory"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Clean up all directories (logs and results)"
    )
    
    args = parser.parse_args()
    
    # Determine which directories to clean
    directories_to_clean = []
    
    if args.all or (not args.logs and not args.results):
        # Default to cleaning both if no specific option given
        directories_to_clean = ["logs", "results", "test_results"]
    else:
        if args.logs:
            directories_to_clean.append("logs")
        if args.results:
            directories_to_clean.extend(["results", "test_results"])
    
    # Get project root
    project_root = Path(__file__).parent.parent
    
    print(f"Cleanup Script - Removing files older than {args.days} days")
    if args.dry_run:
        print("DRY RUN MODE - No files will be actually deleted")
    print("=" * 50)
    
    total_removed = 0
    total_size = 0
    
    for directory in directories_to_clean:
        dir_path = project_root / directory
        print(f"\nCleaning up {directory}/...")
        
        removed, size = cleanup_directory(dir_path, args.days, args.dry_run)
        total_removed += removed
        total_size += size
    
    print("\n" + "=" * 50)
    print(f"Total files {'would be' if args.dry_run else ''} removed: {total_removed}")
    print(f"Total space {'would be' if args.dry_run else ''} freed: {total_size / (1024 * 1024):.2f} MB")
    
    if args.dry_run:
        print("\nRun without --dry-run to actually delete these files")


if __name__ == "__main__":
    main()