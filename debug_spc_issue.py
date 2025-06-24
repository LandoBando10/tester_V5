#!/usr/bin/env python3
"""Debug script to understand why SPC data is not being saved"""

import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.spc.data_collector import SPCDataCollector
from spc.spc_config import MIN_INDIVIDUAL_MEASUREMENTS, SUBGROUP_SIZE

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_data_collection():
    """Test data collection process"""
    print(f"Testing SPC data collection...")
    print(f"MIN_INDIVIDUAL_MEASUREMENTS: {MIN_INDIVIDUAL_MEASUREMENTS}")
    print(f"SUBGROUP_SIZE: {SUBGROUP_SIZE}")
    
    # Create data collector
    collector = SPCDataCollector()
    print(f"Data directory: {collector.data_dir}")
    print(f"Data directory exists: {collector.data_dir.exists()}")
    
    # Test parameters
    sku = "SL0224P01-ABL"
    function = "mainbeam"
    board = "Board_1"
    
    print(f"\nAdding 30 measurements for {sku} {function} {board}...")
    
    # Add 30 measurements
    for i in range(30):
        current = 2.0 + (i % 5) * 0.01  # Slight variation
        voltage = 12.0
        
        print(f"  Adding measurement {i+1}: current={current:.3f}A")
        collector.add_measurement(sku, function, board, current, voltage)
        
        # Check current data status
        if board in collector.current_data[sku][function]:
            pending = len(collector.current_data[sku][function][board])
            print(f"    Pending measurements in buffer: {pending}")
    
    # Check if files were created
    print(f"\nChecking for created files...")
    pattern = f"{sku}_*_*_subgroups.json"
    files = list(collector.data_dir.glob(pattern))
    print(f"Found {len(files)} subgroup files:")
    for f in files:
        print(f"  - {f.name}")
    
    # Check measurement counts
    print(f"\nMeasurement counts:")
    counts = collector.get_measurement_count(sku)
    for key, count in counts.items():
        print(f"  {key}: {count} measurements")
    
    # Try to recalculate specs
    print(f"\nTrying to recalculate specs...")
    results = collector.recalculate_all_specs(sku)
    
    if results:
        print(f"Successfully calculated {len(results)} spec sets:")
        for key, spec in results.items():
            print(f"  {key}: LSL={spec.lsl:.4f}, USL={spec.usl:.4f}")
    else:
        print("No specs could be calculated")
        
        # Check why
        print("\nDebugging why specs couldn't be calculated:")
        
        # Check if we have enough total measurements
        total_measurements = sum(counts.values())
        print(f"Total measurements across all functions/boards: {total_measurements}")
        print(f"Required minimum: {MIN_INDIVIDUAL_MEASUREMENTS}")
        
        if total_measurements < MIN_INDIVIDUAL_MEASUREMENTS:
            print(f"ISSUE: Not enough total measurements!")
        else:
            print(f"Total measurements OK, checking individual function/board combinations...")
            
            # Check each function/board
            for f_file in collector.data_dir.glob(f"{sku}_*_*_subgroups.json"):
                parts = f_file.stem.split('_')
                if len(parts) >= 4:
                    func = parts[1]
                    brd = '_'.join(parts[2:-1])
                    
                    # Try to derive specs for this specific combination
                    print(f"\n  Checking {func} {brd}:")
                    derived = collector._derive_specs(sku, func, brd)
                    if not derived:
                        print(f"    Could not derive specs")
                    else:
                        print(f"    Could derive specs: LSL={derived.lsl:.4f}, USL={derived.usl:.4f}")

if __name__ == "__main__":
    test_data_collection()