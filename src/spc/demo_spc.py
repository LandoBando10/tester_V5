"""
SPC Demo Script for SMT Current Testing
Demonstrates how to use the Statistical Process Control system

This script shows:
1. How to collect sample data
2. How to calculate control limits
3. How to visualize results
4. How to apply limits in production
"""

import sys
import logging
from pathlib import Path
import numpy as np
import random
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.spc import (
    SPCCalculator, 
    SPCDataCollector, 
    SPCIntegration
)


def simulate_current_measurements(nominal: float = 2.0, 
                                variation: float = 0.05,
                                count: int = 100) -> list:
    """Simulate current measurements with normal variation"""
    measurements = []
    for i in range(count):
        # Add some realistic variation patterns
        trend = i * 0.0001  # Slight upward trend
        seasonal = 0.02 * np.sin(i / 10)  # Periodic variation
        noise = random.gauss(0, variation)
        
        value = nominal + trend + seasonal + noise
        measurements.append(value)
        
    return measurements


def demo_spc_calculator():
    """Demonstrate basic SPC calculation"""
    print("\n=== SPC Calculator Demo ===\n")
    
    calculator = SPCCalculator()
    
    # Create sample data: 25 subgroups of 5 measurements each
    samples = []
    nominal_current = 2.0  # 2 Amps nominal
    
    print("Generating sample data...")
    for i in range(25):
        # Each subgroup has slight variation
        subgroup = [
            random.gauss(nominal_current, 0.03) 
            for _ in range(5)
        ]
        samples.append(subgroup)
        
    # Calculate control limits
    print("Calculating control limits...")
    limits = calculator.calculate_control_limits(
        samples,
        spec_limits=(1.8, 2.3)  # From DD5001 mainbeam spec
    )
    
    print(f"\nControl Limits Calculated:")
    print(f"  X-bar Chart:")
    print(f"    UCL: {limits.xbar_ucl:.4f} A")
    print(f"    CL:  {limits.xbar_cl:.4f} A")
    print(f"    LCL: {limits.xbar_lcl:.4f} A")
    print(f"  R Chart:")
    print(f"    UCL: {limits.r_ucl:.4f} A")
    print(f"    CL:  {limits.r_cl:.4f} A")
    print(f"    LCL: {limits.r_lcl:.4f} A")
    print(f"  Process Capability:")
    print(f"    Cp:  {limits.cp:.3f}")
    print(f"    Cpk: {limits.cpk:.3f}")
    
    # Save limits
    output_file = Path("demo_control_limits.json")
    calculator.save_limits(limits, output_file)
    print(f"\nControl limits saved to: {output_file}")
    
    return limits


def demo_data_collector():
    """Demonstrate data collection and automatic limit calculation"""
    print("\n=== Data Collector Demo ===\n")
    
    # Create collector with demo parameters
    collector = SPCDataCollector(
        data_dir=Path("demo_spc_data"),
        subgroup_size=5,
        min_subgroups=20
    )
    
    sku = "DD5001"
    function = "mainbeam"
    board = "Board_1"
    
    print(f"Collecting data for {sku} {function} {board}...")
    print("Simulating production tests...")
    
    # Simulate 105 measurements (21 subgroups)
    measurements = simulate_current_measurements(
        nominal=2.0,
        variation=0.04,
        count=105
    )
    
    # Add measurements one by one (simulating real tests)
    for i, current in enumerate(measurements):
        voltage = random.gauss(12.0, 0.1)  # Simulate voltage
        
        collector.add_measurement(sku, function, board, current, voltage)
        
        # Show progress
        if (i + 1) % 5 == 0:
            subgroup_num = (i + 1) // 5
            print(f"  Subgroup {subgroup_num} complete "
                  f"(avg: {np.mean(measurements[i-4:i+1]):.3f} A)")
            
    # Force calculate limits
    print("\nCalculating control limits from collected data...")
    limits = collector.force_calculate_limits(sku, function, board)
    
    if limits:
        print(f"\nControl Limits from Collected Data:")
        print(f"  UCL: {limits.xbar_ucl:.4f} A")
        print(f"  LCL: {limits.xbar_lcl:.4f} A")
        print(f"  Cpk: {limits.cpk:.3f}")
        
        # Export report
        report_file = Path("demo_spc_report.json")
        collector.export_spc_report(sku, report_file)
        print(f"\nSPC report exported to: {report_file}")
    
    return collector


def demo_production_mode():
    """Demonstrate production mode with limit enforcement"""
    print("\n=== Production Mode Demo ===\n")
    
    # Create SPC integration
    spc = SPCIntegration(
        spc_enabled=True,
        sampling_mode=False,  # Not collecting new samples
        production_mode=True  # Enforcing limits
    )
    
    # Load pre-calculated limits (from previous demo)
    limits_file = Path("demo_control_limits.json")
    if limits_file.exists():
        # Manually add limits to production cache
        # (normally would use load_production_limits)
        calculator = SPCCalculator()
        limits = calculator.load_limits(limits_file)
        limits.sku = "DD5001"
        limits.function = "mainbeam"
        spc.production_limits["DD5001_mainbeam_Board_1"] = limits
        
        print(f"Loaded control limits:")
        print(f"  UCL: {limits.xbar_ucl:.4f} A")
        print(f"  LCL: {limits.xbar_lcl:.4f} A")
        
        # Simulate test results
        test_scenarios = [
            ("Normal", 2.00),
            ("High but in control", limits.xbar_ucl - 0.01),
            ("Out of control high", limits.xbar_ucl + 0.05),
            ("Low but in control", limits.xbar_lcl + 0.01),
            ("Out of control low", limits.xbar_lcl - 0.05),
        ]
        
        print("\nTesting measurements against control limits:")
        for scenario, current in test_scenarios:
            # Create test result
            test_result = {
                'measurements': {
                    'mainbeam_readings': {
                        'board_results': {
                            'Board 1': {
                                'current': current,
                                'voltage': 12.0
                            }
                        }
                    }
                }
            }
            
            # Process through SPC
            spc_result = spc.process_test_results("DD5001", test_result)
            
            status = "PASS" if not spc_result['violations'] else "FAIL"
            print(f"\n  {scenario}: {current:.4f} A -> {status}")
            
            if spc_result['violations']:
                for violation in spc_result['violations']:
                    print(f"    - {violation['message']}")
    else:
        print("No control limits file found. Run calculator demo first.")


def demo_complete_workflow():
    """Demonstrate complete SPC workflow"""
    print("\n=== Complete SPC Workflow Demo ===\n")
    
    print("This demonstrates the complete workflow:")
    print("1. Initial data collection (sampling mode)")
    print("2. Control limit calculation")
    print("3. Production monitoring (production mode)")
    print("4. Out-of-control detection")
    
    # Phase 1: Data Collection
    print("\n--- Phase 1: Data Collection ---")
    collector = demo_data_collector()
    
    # Phase 2: Review and Validation
    print("\n--- Phase 2: Review and Validation ---")
    print("In practice, you would:")
    print("- Review control charts in the GUI")
    print("- Validate limits with engineering team")
    print("- Adjust parameters if needed")
    print("- Document baseline capability")
    
    # Phase 3: Production Implementation
    print("\n--- Phase 3: Production Implementation ---")
    demo_production_mode()
    
    print("\n--- Demo Complete ---")
    print("\nNext steps:")
    print("1. Integrate SPC widget into your GUI")
    print("2. Enable SPC in your SMT test configuration")
    print("3. Collect baseline data (1-2 weeks)")
    print("4. Review and validate control limits")
    print("5. Switch to production mode")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("Statistical Process Control (SPC) Demo")
    print("SMT Current Testing")
    print("=" * 60)
    
    # Run individual demos
    demo_spc_calculator()
    demo_data_collector()
    demo_production_mode()
    
    # Or run complete workflow
    # demo_complete_workflow()
    
    print("\n" + "=" * 60)
    print("Demo complete! Check the generated files:")
    print("- demo_control_limits.json")
    print("- demo_spc_report.json")
    print("- demo_spc_data/ (directory with collected data)")
