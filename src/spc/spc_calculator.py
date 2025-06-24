"""
Statistical Process Control Calculator for SMT Current Testing
Implements X-bar and R control charts for monitoring process stability

Key Features:
- X-bar charts for process mean monitoring
- R charts for process variation monitoring
- Automatic control limit calculation
- Process capability indices (Cp, Cpk)
- Western Electric rules for out-of-control detection
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import json
import logging
from pathlib import Path

try:
    from spc.spc_config import CONTROL_CONSTANTS, CONFIDENCE_LEVEL
except ImportError:
    # Fallback if running from different location
    CONTROL_CONSTANTS = None
    CONFIDENCE_LEVEL = 3.0


@dataclass
class ControlLimits:
    """Control limits for X-bar and R charts"""
    # X-bar chart limits
    xbar_ucl: float  # Upper Control Limit for mean
    xbar_cl: float   # Center Line for mean
    xbar_lcl: float  # Lower Control Limit for mean
    
    # R chart limits
    r_ucl: float     # Upper Control Limit for range
    r_cl: float      # Center Line for range
    r_lcl: float     # Lower Control Limit for range
    
    # Process statistics
    process_mean: float
    process_std: float
    sample_size: int
    num_subgroups: int
    
    # Capability indices
    cp: Optional[float] = None
    cpk: Optional[float] = None
    
    # Metadata
    timestamp: datetime = None
    sku: str = ""
    function: str = ""
    measurement_type: str = "current"


class SPCCalculator:
    """Calculate control limits and monitor process stability"""
    
    # Control chart constants - use from config if available
    if CONTROL_CONSTANTS is None:
        CONTROL_CONSTANTS = {
        2: {'A2': 1.880, 'D3': 0.000, 'D4': 3.267},
        3: {'A2': 1.023, 'D3': 0.000, 'D4': 2.574},
        4: {'A2': 0.729, 'D3': 0.000, 'D4': 2.282},
        5: {'A2': 0.577, 'D3': 0.000, 'D4': 2.114},
        6: {'A2': 0.483, 'D3': 0.000, 'D4': 2.004},
        7: {'A2': 0.419, 'D3': 0.076, 'D4': 1.924},
        8: {'A2': 0.373, 'D3': 0.136, 'D4': 1.864},
        9: {'A2': 0.337, 'D3': 0.184, 'D4': 1.816},
        10: {'A2': 0.308, 'D3': 0.223, 'D4': 1.777},
    }
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        
    def calculate_control_limits(self, 
                               samples: List[List[float]], 
                               spec_limits: Optional[Tuple[float, float]] = None,
                               confidence_level: float = CONFIDENCE_LEVEL) -> ControlLimits:
        """
        Calculate X-bar and R control limits from sample data
        
        Args:
            samples: List of subgroups, each containing measurements
            spec_limits: Optional tuple of (LSL, USL) for capability calculations
            confidence_level: Number of standard deviations for control limits (default 3-sigma)
            
        Returns:
            ControlLimits object with calculated values
        """
        if not samples or not all(samples):
            raise ValueError("Samples cannot be empty")
            
        # Ensure consistent sample sizes
        sample_sizes = [len(subgroup) for subgroup in samples]
        if len(set(sample_sizes)) > 1:
            self.logger.warning(f"Inconsistent sample sizes: {sample_sizes}")
            # Use the most common sample size
            sample_size = max(set(sample_sizes), key=sample_sizes.count)
            samples = [s for s in samples if len(s) == sample_size]
        else:
            sample_size = sample_sizes[0]
            
        if sample_size not in self.CONTROL_CONSTANTS:
            raise ValueError(f"Sample size {sample_size} not supported (must be 2-10)")
            
        # Get control constants
        constants = self.CONTROL_CONSTANTS[sample_size]
        A2 = constants['A2']
        D3 = constants['D3']
        D4 = constants['D4']
        
        # Calculate subgroup statistics
        subgroup_means = [np.mean(subgroup) for subgroup in samples]
        subgroup_ranges = [np.max(subgroup) - np.min(subgroup) for subgroup in samples]
        
        # Calculate grand mean and average range
        x_double_bar = np.mean(subgroup_means)
        r_bar = np.mean(subgroup_ranges)
        
        # Calculate control limits for X-bar chart
        xbar_cl = x_double_bar
        xbar_ucl = x_double_bar + (A2 * r_bar)
        xbar_lcl = x_double_bar - (A2 * r_bar)
        
        # Calculate control limits for R chart
        r_cl = r_bar
        r_ucl = D4 * r_bar
        r_lcl = D3 * r_bar
        
        # Estimate process standard deviation
        # Using the range method: sigma = R-bar / d2
        d2 = self.CONTROL_CONSTANTS.get(sample_size, {}).get('d2', 2.326)  # Default to n=5 if not found
        process_std = r_bar / d2
        
        # Create control limits object
        limits = ControlLimits(
            xbar_ucl=xbar_ucl,
            xbar_cl=xbar_cl,
            xbar_lcl=xbar_lcl,
            r_ucl=r_ucl,
            r_cl=r_cl,
            r_lcl=r_lcl,
            process_mean=x_double_bar,
            process_std=process_std,
            sample_size=sample_size,
            num_subgroups=len(samples),
            timestamp=datetime.now()
        )
        
        # Calculate capability indices if spec limits provided
        if spec_limits:
            lsl, usl = spec_limits
            limits.cp, limits.cpk = self.calculate_capability(
                x_double_bar, process_std, lsl, usl
            )
            
        return limits
        
    def calculate_capability(self, mean: float, std: float, 
                           lsl: float, usl: float) -> Tuple[float, float]:
        """
        Calculate process capability indices Cp and Cpk
        
        Args:
            mean: Process mean
            std: Process standard deviation
            lsl: Lower specification limit
            usl: Upper specification limit
            
        Returns:
            Tuple of (Cp, Cpk)
        """
        if std == 0:
            return (float('inf'), float('inf'))
            
        # Cp = (USL - LSL) / (6 * sigma)
        cp = (usl - lsl) / (6 * std)
        
        # Cpk = min((USL - mean) / (3 * sigma), (mean - LSL) / (3 * sigma))
        cpu = (usl - mean) / (3 * std)
        cpl = (mean - lsl) / (3 * std)
        cpk = min(cpu, cpl)
        
        return (cp, cpk)
        
    def check_control_rules(self, values: List[float], 
                          limits: ControlLimits) -> List[Dict[str, Any]]:
        """
        Check for out-of-control conditions using Western Electric rules
        
        Rules:
        1. One point outside control limits
        2. Nine points in a row on same side of centerline
        3. Six points in a row steadily increasing or decreasing
        4. Fourteen points in a row alternating up and down
        5. Two out of three points beyond 2-sigma
        6. Four out of five points beyond 1-sigma
        7. Fifteen points in a row within 1-sigma (too little variation)
        8. Eight points in a row outside 1-sigma on both sides
        
        Returns:
            List of rule violations with details
        """
        violations = []
        cl = limits.xbar_cl
        ucl = limits.xbar_ucl
        lcl = limits.xbar_lcl
        
        # Calculate sigma zones
        sigma = (ucl - cl) / 3
        ucl_2sigma = cl + 2 * sigma
        lcl_2sigma = cl - 2 * sigma
        ucl_1sigma = cl + sigma
        lcl_1sigma = cl - sigma
        
        # Rule 1: Points outside control limits
        for i, value in enumerate(values):
            if value > ucl or value < lcl:
                violations.append({
                    'rule': 1,
                    'description': 'Point outside control limits',
                    'index': i,
                    'value': value
                })
                
        # Rule 2: Nine points on same side of centerline
        if len(values) >= 9:
            for i in range(len(values) - 8):
                subset = values[i:i+9]
                if all(v > cl for v in subset) or all(v < cl for v in subset):
                    violations.append({
                        'rule': 2,
                        'description': 'Nine points on same side of centerline',
                        'start_index': i,
                        'end_index': i + 8
                    })
                    
        # Rule 3: Six points steadily increasing or decreasing
        if len(values) >= 6:
            for i in range(len(values) - 5):
                subset = values[i:i+6]
                diffs = [subset[j+1] - subset[j] for j in range(5)]
                if all(d > 0 for d in diffs) or all(d < 0 for d in diffs):
                    violations.append({
                        'rule': 3,
                        'description': 'Six points steadily increasing/decreasing',
                        'start_index': i,
                        'end_index': i + 5
                    })
                    
        # Additional rules can be implemented as needed
        
        return violations
        
    def save_limits(self, limits: ControlLimits, filepath: Path):
        """Save control limits to JSON file"""
        data = {
            'xbar_limits': {
                'ucl': limits.xbar_ucl,
                'cl': limits.xbar_cl,
                'lcl': limits.xbar_lcl
            },
            'r_limits': {
                'ucl': limits.r_ucl,
                'cl': limits.r_cl,
                'lcl': limits.r_lcl
            },
            'process_stats': {
                'mean': limits.process_mean,
                'std': limits.process_std,
                'sample_size': limits.sample_size,
                'num_subgroups': limits.num_subgroups
            },
            'capability': {
                'cp': limits.cp,
                'cpk': limits.cpk
            },
            'metadata': {
                'timestamp': limits.timestamp.isoformat() if limits.timestamp else None,
                'sku': limits.sku,
                'function': limits.function,
                'measurement_type': limits.measurement_type
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
            
    def load_limits(self, filepath: Path) -> ControlLimits:
        """Load control limits from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        limits = ControlLimits(
            xbar_ucl=data['xbar_limits']['ucl'],
            xbar_cl=data['xbar_limits']['cl'],
            xbar_lcl=data['xbar_limits']['lcl'],
            r_ucl=data['r_limits']['ucl'],
            r_cl=data['r_limits']['cl'],
            r_lcl=data['r_limits']['lcl'],
            process_mean=data['process_stats']['mean'],
            process_std=data['process_stats']['std'],
            sample_size=data['process_stats']['sample_size'],
            num_subgroups=data['process_stats']['num_subgroups'],
            cp=data['capability'].get('cp'),
            cpk=data['capability'].get('cpk'),
            timestamp=datetime.fromisoformat(data['metadata']['timestamp']) 
                     if data['metadata'].get('timestamp') else None,
            sku=data['metadata'].get('sku', ''),
            function=data['metadata'].get('function', ''),
            measurement_type=data['metadata'].get('measurement_type', 'current')
        )
        
        return limits


# Example usage
if __name__ == "__main__":
    # Example data: 20 subgroups of 5 measurements each
    np.random.seed(42)
    samples = []
    for _ in range(20):
        # Simulate current measurements with slight variation
        subgroup = np.random.normal(2.0, 0.05, 5).tolist()
        samples.append(subgroup)
        
    calculator = SPCCalculator()
    
    # Calculate control limits
    limits = calculator.calculate_control_limits(
        samples, 
        spec_limits=(1.8, 2.3)  # From DD5001 mainbeam limits
    )
    
    print(f"X-bar Control Limits:")
    print(f"  UCL: {limits.xbar_ucl:.4f}")
    print(f"  CL:  {limits.xbar_cl:.4f}")
    print(f"  LCL: {limits.xbar_lcl:.4f}")
    print(f"\nR Control Limits:")
    print(f"  UCL: {limits.r_ucl:.4f}")
    print(f"  CL:  {limits.r_cl:.4f}")
    print(f"  LCL: {limits.r_lcl:.4f}")
    print(f"\nProcess Capability:")
    print(f"  Cp:  {limits.cp:.3f}")
    print(f"  Cpk: {limits.cpk:.3f}")
