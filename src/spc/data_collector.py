"""
SPC Data Collector for SMT Current Testing
Handles sample collection, storage, and analysis triggering

Features:
- Automatic sample collection during normal testing
- Subgroup management with configurable size
- Data persistence for historical analysis
- Integration with existing SMT test flow
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import defaultdict
import threading
import numpy as np

from src.spc.spc_calculator import SPCCalculator, ControlLimits
from spc.spc_config import (
    SUBGROUP_SIZE,
    BASELINE_SUBGROUPS,
    MAX_HISTORICAL_SUBGROUPS,
    MIN_SUBGROUPS_FOR_ANALYSIS,
    SUBGROUP_FILE_PATTERN,
    LIMITS_FILE_PATTERN,
    SPECS_FILE_PATTERN
)
from spc.spec_deriver import SpecDeriver, DerivedSpecs


class SPCDataCollector:
    """Collect and manage SPC data from SMT tests"""
    
    def __init__(self, 
                 data_dir: Path = None,
                 subgroup_size: int = SUBGROUP_SIZE,
                 min_subgroups: int = BASELINE_SUBGROUPS,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize SPC data collector
        
        Args:
            data_dir: Directory for storing SPC data
            subgroup_size: Number of samples per subgroup (typically 4-5)
            min_subgroups: Minimum subgroups needed before calculating limits (typically 20-25)
        """
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.data_dir = data_dir or Path("spc_data")
        self.data_dir.mkdir(exist_ok=True)
        
        self.subgroup_size = subgroup_size
        self.min_subgroups = min_subgroups
        
        # Data storage: SKU -> Function -> Board -> measurements
        self.current_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        self.lock = threading.Lock()
        
        # SPC calculator
        self.calculator = SPCCalculator(logger=self.logger)
        
        # Control limits cache
        self.control_limits: Dict[str, ControlLimits] = {}
        
        # Spec deriver for when no engineering specs exist
        self.spec_deriver = SpecDeriver()
        self.derived_specs: Dict[str, DerivedSpecs] = {}
        
        # Load existing control limits
        self._load_existing_limits()
        
    def add_measurement(self, sku: str, function: str, board: str, 
                       current: float, voltage: float = None):
        """
        Add a measurement to the collection
        
        Args:
            sku: SKU identifier
            function: Function being tested (e.g., 'mainbeam', 'backlight_left')
            board: Board identifier (e.g., 'Board 1')
            current: Current measurement in Amps
            voltage: Optional voltage measurement
        """
        with self.lock:
            key = f"{sku}_{function}_{board}"
            self.current_data[sku][function][board].append({
                'current': current,
                'voltage': voltage,
                'timestamp': datetime.now().isoformat()
            })
            
            # Check if we should process this data
            measurements = self.current_data[sku][function][board]
            if len(measurements) >= self.subgroup_size:
                self._process_subgroup(sku, function, board)
                
    def add_panel_results(self, sku: str, panel_results: Dict[str, Dict]):
        """
        Add results from an entire panel test
        
        Args:
            sku: SKU identifier
            panel_results: Results organized by function -> board -> measurements
        """
        for function, board_data in panel_results.items():
            for board, measurements in board_data.items():
                if measurements and 'current' in measurements:
                    self.add_measurement(
                        sku, function, board,
                        measurements['current'],
                        measurements.get('voltage')
                    )
                    
    def _process_subgroup(self, sku: str, function: str, board: str):
        """Process a completed subgroup"""
        measurements = self.current_data[sku][function][board]
        
        if len(measurements) >= self.subgroup_size:
            # Extract subgroup
            subgroup = measurements[:self.subgroup_size]
            self.current_data[sku][function][board] = measurements[self.subgroup_size:]
            
            # Save subgroup to file
            self._save_subgroup(sku, function, board, subgroup)
            
            # Check if we have enough data to update control limits
            self._check_for_limit_update(sku, function, board)
            
    def _save_subgroup(self, sku: str, function: str, board: str, 
                      subgroup: List[Dict]):
        """Save subgroup data to file"""
        filename = self.data_dir / SUBGROUP_FILE_PATTERN.format(sku=sku, function=function, board=board)
        
        # Load existing data
        existing_data = []
        if filename.exists():
            try:
                with open(filename, 'r') as f:
                    existing_data = json.load(f)
            except:
                self.logger.warning(f"Could not load existing data from {filename}")
                
        # Append new subgroup
        existing_data.append({
            'timestamp': datetime.now().isoformat(),
            'measurements': subgroup
        })
        
        # Keep only recent data
        if len(existing_data) > MAX_HISTORICAL_SUBGROUPS:
            existing_data = existing_data[-MAX_HISTORICAL_SUBGROUPS:]
            
        # Save updated data
        with open(filename, 'w') as f:
            json.dump(existing_data, f, indent=2)
            
    def _check_for_limit_update(self, sku: str, function: str, board: str):
        """Check if we should update control limits"""
        filename = self.data_dir / SUBGROUP_FILE_PATTERN.format(sku=sku, function=function, board=board)
        
        if not filename.exists():
            return
            
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                
            if len(data) >= self.min_subgroups:
                # Extract current values from subgroups
                samples = []
                for subgroup_data in data[-self.min_subgroups:]:
                    currents = [m['current'] for m in subgroup_data['measurements']]
                    samples.append(currents)
                    
                # Get specification limits - either from config or derived
                spec_limits = self._get_spec_limits(sku, function, board)
                
                # Calculate new limits
                limits = self.calculator.calculate_control_limits(
                    samples, spec_limits
                )
                
                # Add metadata
                limits.sku = sku
                limits.function = function
                limits.measurement_type = f"{board}_current"
                
                # Save limits
                limit_file = self.data_dir / LIMITS_FILE_PATTERN.format(sku=sku, function=function, board=board)
                self.calculator.save_limits(limits, limit_file)
                
                # Update cache
                key = f"{sku}_{function}_{board}"
                self.control_limits[key] = limits
                
                self.logger.info(
                    f"Updated control limits for {sku} {function} {board}: "
                    f"UCL={limits.xbar_ucl:.4f}, LCL={limits.xbar_lcl:.4f}"
                )
                
        except Exception as e:
            self.logger.error(f"Error updating limits: {e}")
            
    def _get_spec_limits(self, sku: str, function: str, board: str) -> Optional[Tuple[float, float]]:
        """Get specification limits - either from config or derived from process data"""
        # First check if we have derived specs cached
        spec_key = f"{sku}_{function}_{board}"
        if spec_key in self.derived_specs:
            spec = self.derived_specs[spec_key]
            return (spec.lsl, spec.usl)
        
        # Try to load from saved specs file
        spec_file = self.data_dir / SPECS_FILE_PATTERN.format(sku=sku, function=function, board=board)
        if spec_file.exists():
            try:
                with open(spec_file, 'r') as f:
                    spec_data = json.load(f)
                    return (spec_data['lsl'], spec_data['usl'])
            except Exception as e:
                self.logger.warning(f"Could not load specs from {spec_file}: {e}")
        
        # If no specs exist, try to derive them from process data
        derived = self._derive_specs(sku, function, board)
        if derived:
            self.derived_specs[spec_key] = derived
            # Save derived specs
            self._save_derived_specs(sku, function, board, derived)
            return (derived.lsl, derived.usl)
        
        # No specs available
        return None
        
    def _load_existing_limits(self):
        """Load existing control limits from disk"""
        for limit_file in self.data_dir.glob("*_limits.json"):
            try:
                limits = self.calculator.load_limits(limit_file)
                # Extract key from filename
                parts = limit_file.stem.split('_')
                if len(parts) >= 4:  # SKU_function_board_limits
                    sku = parts[0]
                    function = parts[1]
                    board = f"{parts[2]}_{parts[3]}" if len(parts) > 4 else parts[2]
                    key = f"{sku}_{function}_{board}"
                    self.control_limits[key] = limits
                    self.logger.info(f"Loaded control limits for {key}")
            except Exception as e:
                self.logger.error(f"Error loading {limit_file}: {e}")
                
    def get_control_limits(self, sku: str, function: str, 
                          board: str) -> Optional[ControlLimits]:
        """Get control limits for specific combination"""
        key = f"{sku}_{function}_{board}"
        return self.control_limits.get(key)
        
    def get_all_limits(self, sku: str) -> Dict[str, ControlLimits]:
        """Get all control limits for a SKU"""
        return {k: v for k, v in self.control_limits.items() if k.startswith(sku)}
        
    def force_calculate_limits(self, sku: str, function: str, 
                             board: str) -> Optional[ControlLimits]:
        """Force calculation of control limits regardless of sample count"""
        filename = self.data_dir / SUBGROUP_FILE_PATTERN.format(sku=sku, function=function, board=board)
        
        if not filename.exists():
            return None
            
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                
            if len(data) < MIN_SUBGROUPS_FOR_ANALYSIS:
                self.logger.warning(
                    f"Only {len(data)} subgroups available, need at least {MIN_SUBGROUPS_FOR_ANALYSIS}"
                )
                return None
                
            # Extract samples
            samples = []
            for subgroup_data in data:
                currents = [m['current'] for m in subgroup_data['measurements']]
                samples.append(currents)
                
            # Calculate limits
            spec_limits = self._get_spec_limits(sku, function, board)
            limits = self.calculator.calculate_control_limits(samples, spec_limits)
            
            # Add metadata
            limits.sku = sku
            limits.function = function
            limits.measurement_type = f"{board}_current"
            
            return limits
            
        except Exception as e:
            self.logger.error(f"Error calculating limits: {e}")
            return None
            
    def _derive_specs(self, sku: str, function: str, board: str) -> Optional[DerivedSpecs]:
        """Derive specification limits from process data"""
        # Load subgroup data
        filename = self.data_dir / SUBGROUP_FILE_PATTERN.format(sku=sku, function=function, board=board)
        
        if not filename.exists():
            return None
            
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                
            # Need sufficient data to derive specs
            if len(data) < self.min_subgroups:
                self.logger.info(
                    f"Only {len(data)} subgroups available for {sku} {function} {board}, "
                    f"need {self.min_subgroups} to derive specs"
                )
                return None
                
            # Extract samples
            samples = []
            for subgroup_data in data:
                if 'measurements' in subgroup_data:
                    samples.append(subgroup_data['measurements'])
                    
            if not samples:
                return None
                
            # Derive specs using the spec deriver
            derived_specs = self.spec_deriver.derive_specs_from_data(samples)
            
            if derived_specs:
                self.logger.info(
                    f"Derived specs for {sku} {function} {board}: "
                    f"LSL={derived_specs.lsl:.4f}, USL={derived_specs.usl:.4f}, "
                    f"Expected Cp={derived_specs.expected_cp:.2f}"
                )
                
            return derived_specs
            
        except Exception as e:
            self.logger.error(f"Error deriving specs: {e}")
            return None
            
    def _save_derived_specs(self, sku: str, function: str, board: str, specs: DerivedSpecs):
        """Save derived specifications to file"""
        spec_file = self.data_dir / SPECS_FILE_PATTERN.format(sku=sku, function=function, board=board)
        
        spec_data = {
            'timestamp': datetime.now().isoformat(),
            'lsl': specs.lsl,
            'usl': specs.usl,
            'target': specs.target,
            'process_sigma': specs.process_sigma,
            'expected_cp': specs.expected_cp,
            'expected_cpk': specs.expected_cpk,
            'derived': True,  # Flag to indicate these are derived, not engineering specs
            'method': 'process_capability',
            'target_cp': self.spec_deriver.target_cp
        }
        
        try:
            with open(spec_file, 'w') as f:
                json.dump(spec_data, f, indent=2)
            self.logger.info(f"Saved derived specs to {spec_file}")
        except Exception as e:
            self.logger.error(f"Error saving derived specs: {e}")
    
    def export_spc_report(self, sku: str, output_file: Path):
        """Export comprehensive SPC report for a SKU"""
        report = {
            'sku': sku,
            'timestamp': datetime.now().isoformat(),
            'control_limits': {},
            'process_capability': {},
            'subgroup_summary': {}
        }
        
        # Get all limits for this SKU
        sku_limits = self.get_all_limits(sku)
        
        for key, limits in sku_limits.items():
            report['control_limits'][key] = {
                'xbar_ucl': limits.xbar_ucl,
                'xbar_cl': limits.xbar_cl,
                'xbar_lcl': limits.xbar_lcl,
                'r_ucl': limits.r_ucl,
                'r_cl': limits.r_cl,
                'r_lcl': limits.r_lcl
            }
            
            if limits.cp is not None:
                report['process_capability'][key] = {
                    'cp': limits.cp,
                    'cpk': limits.cpk
                }
                
            # Add subgroup count
            parts = key.split('_')
            if len(parts) >= 3:
                function = parts[1]
                board = '_'.join(parts[2:])
                filename = self.data_dir / SUBGROUP_FILE_PATTERN.format(sku=sku, function=function, board=board)
                if filename.exists():
                    try:
                        with open(filename, 'r') as f:
                            data = json.load(f)
                        report['subgroup_summary'][key] = {
                            'count': len(data),
                            'last_updated': data[-1]['timestamp'] if data else None
                        }
                    except:
                        pass
                        
        # Save report
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        self.logger.info(f"Exported SPC report to {output_file}")
        

# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create collector
    collector = SPCDataCollector(
        data_dir=Path("test_spc_data"),
        subgroup_size=5,
        min_subgroups=20
    )
    
    # Simulate collecting data from tests
    import random
    
    sku = "DD5001"
    function = "mainbeam"
    board = "Board_1"
    
    # Add 100 measurements (will create 20 subgroups)
    for i in range(100):
        # Simulate current measurement with slight variation
        current = random.gauss(2.0, 0.05)
        voltage = random.gauss(12.0, 0.1)
        
        collector.add_measurement(sku, function, board, current, voltage)
        
    # Force calculate limits
    limits = collector.force_calculate_limits(sku, function, board)
    if limits:
        print(f"Control Limits for {sku} {function} {board}:")
        print(f"  X-bar: {limits.xbar_lcl:.4f} - {limits.xbar_ucl:.4f}")
        print(f"  R: {limits.r_lcl:.4f} - {limits.r_ucl:.4f}")
        print(f"  Cp: {limits.cp:.3f}, Cpk: {limits.cpk:.3f}")
