#!/usr/bin/env python3
"""
Tool to recalculate SPC specification limits from process data

Usage:
    python recalculate_spc_specs.py DD5001              # Recalculate all specs for SKU
    python recalculate_spc_specs.py DD5001 mainbeam     # Recalculate specific function
    python recalculate_spc_specs.py DD5001 mainbeam Board_1  # Specific board
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.spc.data_collector import SPCDataCollector

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    sku = sys.argv[1]
    collector = SPCDataCollector()
    
    if len(sys.argv) == 2:
        # Recalculate all specs for SKU
        print(f"\nRecalculating all specs for SKU: {sku}")
        results = collector.recalculate_all_specs(sku)
        
        if results:
            print(f"\nSuccessfully recalculated {len(results)} spec sets:")
            for key, spec in results.items():
                print(f"  {key}:")
                print(f"    LSL: {spec.lsl:.4f}")
                print(f"    USL: {spec.usl:.4f}")
                print(f"    Target: {spec.target:.4f}")
                print(f"    Expected Cp: {spec.expected_cp:.2f}")
        else:
            print("No specs could be calculated (insufficient data)")
            
    elif len(sys.argv) == 3:
        # Recalculate for specific function
        function = sys.argv[2]
        print(f"\nRecalculating specs for {sku} {function} (all boards)")
        
        # Find all boards for this function
        pattern = f"{sku}_{function}_*_subgroups.json"
        found = False
        
        for subgroup_file in collector.data_dir.glob(pattern):
            parts = subgroup_file.stem.split('_')
            if len(parts) >= 4:
                board = '_'.join(parts[2:-1])
                spec = collector.force_recalculate_specs(sku, function, board)
                if spec:
                    found = True
                    print(f"\n{function} {board}:")
                    print(f"  LSL: {spec.lsl:.4f}")
                    print(f"  USL: {spec.usl:.4f}")
                    print(f"  Target: {spec.target:.4f}")
                    print(f"  Expected Cp: {spec.expected_cp:.2f}")
                    
        if not found:
            print(f"No data found for {sku} {function}")
            
    else:
        # Recalculate for specific board
        function = sys.argv[2]
        board = sys.argv[3]
        
        print(f"\nRecalculating specs for {sku} {function} {board}")
        spec = collector.force_recalculate_specs(sku, function, board)
        
        if spec:
            print(f"\nSuccessfully recalculated specs:")
            print(f"  LSL: {spec.lsl:.4f}")
            print(f"  USL: {spec.usl:.4f}")
            print(f"  Target: {spec.target:.4f}")
            print(f"  Process Sigma: {spec.process_sigma:.4f}")
            print(f"  Expected Cp: {spec.expected_cp:.2f}")
            print(f"  Expected Cpk: {spec.expected_cpk:.2f}")
        else:
            print("Could not calculate specs (insufficient data)")

if __name__ == "__main__":
    main()