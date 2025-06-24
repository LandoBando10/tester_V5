"""
SPC Integration for SMT Testing
Integrates Statistical Process Control with existing SMT test flow

Features:
- Automatic data collection during tests
- Control limit application
- Real-time monitoring
- Production mode vs. sampling mode
"""

import logging
from typing import Dict, Optional, List, Tuple, Any
from pathlib import Path
from datetime import datetime
import json

from src.spc.spc_calculator import SPCCalculator, ControlLimits
from src.spc.data_collector import SPCDataCollector


class SPCIntegration:
    """Integrate SPC with SMT testing"""
    
    def __init__(self, 
                 spc_enabled: bool = True,
                 sampling_mode: bool = True,
                 production_mode: bool = False,
                 data_dir: Optional[Path] = None,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize SPC integration
        
        Args:
            spc_enabled: Whether SPC is enabled
            sampling_mode: Collect data for control limit calculation
            production_mode: Apply control limits for pass/fail
            data_dir: Directory for SPC data storage
        """
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.spc_enabled = spc_enabled
        self.sampling_mode = sampling_mode
        self.production_mode = production_mode
        
        if self.spc_enabled:
            self.data_collector = SPCDataCollector(
                data_dir=data_dir,
                logger=self.logger
            )
            self.calculator = SPCCalculator(logger=self.logger)
        else:
            self.data_collector = None
            self.calculator = None
            
        # Cache for production limits
        self.production_limits: Dict[str, ControlLimits] = {}
        
    def process_test_results(self, sku: str, test_results: Dict) -> Dict[str, Any]:
        """
        Process test results through SPC
        
        Args:
            sku: SKU being tested
            test_results: Test results from SMT test
            
        Returns:
            SPC analysis results
        """
        if not self.spc_enabled:
            return {'enabled': False}
            
        spc_results = {
            'enabled': True,
            'mode': 'sampling' if self.sampling_mode else 'production',
            'violations': [],
            'limits_applied': {},
            'data_collected': False
        }
        
        # Extract measurements from test results
        measurements = self._extract_measurements(test_results)
        
        if self.sampling_mode and measurements:
            # Collect data for control limit calculation
            for (function, board), values in measurements.items():
                if 'current' in values:
                    self.data_collector.add_measurement(
                        sku, function, board,
                        values['current'],
                        values.get('voltage')
                    )
            spc_results['data_collected'] = True
            
        if self.production_mode:
            # Apply control limits for pass/fail determination
            violations = self._check_production_limits(sku, measurements)
            spc_results['violations'] = violations
            spc_results['limits_applied'] = self._get_applied_limits(sku, measurements)
            
        return spc_results
        
    def _extract_measurements(self, test_results: Dict) -> Dict[Tuple[str, str], Dict]:
        """Extract measurements from test results"""
        measurements = {}
        
        if 'measurements' in test_results:
            for function_key, function_data in test_results['measurements'].items():
                if function_key.endswith('_readings'):
                    function = function_key.replace('_readings', '')
                    board_results = function_data.get('board_results', {})
                    
                    for board, board_measurements in board_results.items():
                        board_key = board.replace(' ', '_')
                        measurements[(function, board_key)] = board_measurements
                        
        return measurements
        
    def _check_production_limits(self, sku: str, 
                               measurements: Dict[Tuple[str, str], Dict]) -> List[Dict]:
        """Check measurements against production control limits"""
        violations = []
        
        for (function, board), values in measurements.items():
            if 'current' not in values:
                continue
                
            current = values['current']
            
            # Get control limits
            limits = self._get_control_limits(sku, function, board)
            if not limits:
                continue
                
            # Check against X-bar limits
            if current > limits.xbar_ucl:
                violations.append({
                    'type': 'UCL_violation',
                    'function': function,
                    'board': board,
                    'value': current,
                    'limit': limits.xbar_ucl,
                    'message': f"{board} {function} current {current:.4f}A exceeds UCL {limits.xbar_ucl:.4f}A"
                })
            elif current < limits.xbar_lcl:
                violations.append({
                    'type': 'LCL_violation',
                    'function': function,
                    'board': board,
                    'value': current,
                    'limit': limits.xbar_lcl,
                    'message': f"{board} {function} current {current:.4f}A below LCL {limits.xbar_lcl:.4f}A"
                })
                
        return violations
        
    def _get_control_limits(self, sku: str, function: str, 
                          board: str) -> Optional[ControlLimits]:
        """Get control limits for specific combination"""
        key = f"{sku}_{function}_{board}"
        
        # Check cache first
        if key in self.production_limits:
            return self.production_limits[key]
            
        # Try to load from data collector
        if self.data_collector:
            limits = self.data_collector.get_control_limits(sku, function, board)
            if limits:
                self.production_limits[key] = limits
                return limits
                
        return None
        
    def _get_applied_limits(self, sku: str, 
                          measurements: Dict[Tuple[str, str], Dict]) -> Dict:
        """Get all applied control limits"""
        applied = {}
        
        for (function, board), _ in measurements.items():
            limits = self._get_control_limits(sku, function, board)
            if limits:
                key = f"{function}_{board}"
                applied[key] = {
                    'xbar_ucl': limits.xbar_ucl,
                    'xbar_lcl': limits.xbar_lcl,
                    'source': 'calculated' if limits.timestamp else 'loaded'
                }
                
        return applied
        
    def set_mode(self, sampling: bool = True, production: bool = False):
        """Set SPC mode"""
        self.sampling_mode = sampling
        self.production_mode = production
        
        mode_str = []
        if sampling:
            mode_str.append("sampling")
        if production:
            mode_str.append("production")
            
        self.logger.info(f"SPC mode set to: {', '.join(mode_str)}")
        
    def load_production_limits(self, limits_file: Path):
        """Load control limits for production use"""
        try:
            with open(limits_file, 'r') as f:
                data = json.load(f)
                
            for key, limit_data in data.items():
                limits = ControlLimits(
                    xbar_ucl=limit_data['xbar_ucl'],
                    xbar_cl=limit_data['xbar_cl'],
                    xbar_lcl=limit_data['xbar_lcl'],
                    r_ucl=limit_data['r_ucl'],
                    r_cl=limit_data['r_cl'],
                    r_lcl=limit_data['r_lcl'],
                    process_mean=limit_data.get('process_mean', 0),
                    process_std=limit_data.get('process_std', 0),
                    sample_size=limit_data.get('sample_size', 5),
                    num_subgroups=limit_data.get('num_subgroups', 0)
                )
                self.production_limits[key] = limits
                
            self.logger.info(f"Loaded {len(self.production_limits)} production limits")
            
        except Exception as e:
            self.logger.error(f"Error loading production limits: {e}")
            
    def export_production_limits(self, output_file: Path):
        """Export current control limits for production use"""
        if not self.data_collector:
            return
            
        limits_data = {}
        
        # Get all available limits
        for key, limits in self.data_collector.control_limits.items():
            limits_data[key] = {
                'xbar_ucl': limits.xbar_ucl,
                'xbar_cl': limits.xbar_cl,
                'xbar_lcl': limits.xbar_lcl,
                'r_ucl': limits.r_ucl,
                'r_cl': limits.r_cl,
                'r_lcl': limits.r_lcl,
                'process_mean': limits.process_mean,
                'process_std': limits.process_std,
                'sample_size': limits.sample_size,
                'num_subgroups': limits.num_subgroups,
                'timestamp': limits.timestamp.isoformat() if limits.timestamp else None
            }
            
        with open(output_file, 'w') as f:
            json.dump(limits_data, f, indent=2)
            
        self.logger.info(f"Exported {len(limits_data)} control limits to {output_file}")
        
    def get_spc_summary(self, sku: str) -> Dict[str, Any]:
        """Get SPC summary for a SKU"""
        if not self.spc_enabled or not self.data_collector:
            return {'enabled': False}
            
        summary = {
            'enabled': True,
            'sku': sku,
            'mode': {
                'sampling': self.sampling_mode,
                'production': self.production_mode
            },
            'control_limits': {},
            'data_status': {}
        }
        
        # Get all limits for this SKU
        all_limits = self.data_collector.get_all_limits(sku)
        
        for key, limits in all_limits.items():
            parts = key.split('_')
            if len(parts) >= 3:
                function = parts[1]
                board = '_'.join(parts[2:])
                
                limit_key = f"{function}_{board}"
                summary['control_limits'][limit_key] = {
                    'xbar_ucl': limits.xbar_ucl,
                    'xbar_lcl': limits.xbar_lcl,
                    'cpk': limits.cpk
                }
                
                # Check data status
                filename = self.data_collector.data_dir / f"{sku}_{function}_{board}_subgroups.json"
                if filename.exists():
                    try:
                        with open(filename, 'r') as f:
                            data = json.load(f)
                        summary['data_status'][limit_key] = {
                            'subgroups': len(data),
                            'ready': len(data) >= self.data_collector.min_subgroups
                        }
                    except:
                        pass
                        
        return summary


# Modified SMT test integration
def integrate_spc_with_smt_test(smt_test_class):
    """Decorator to integrate SPC with SMT test class"""
    
    original_init = smt_test_class.__init__
    original_run = smt_test_class.run_test_sequence
    original_cleanup = smt_test_class.cleanup_hardware
    
    def new_init(self, *args, **kwargs):
        # Call original init
        original_init(self, *args, **kwargs)
        
        # Add SPC integration
        spc_config = kwargs.get('spc_config', {})
        self.spc = SPCIntegration(
            spc_enabled=spc_config.get('enabled', False),
            sampling_mode=spc_config.get('sampling_mode', True),
            production_mode=spc_config.get('production_mode', False),
            logger=self.logger
        )
        
    def new_run(self):
        # Run original test
        result = original_run(self)
        
        # Process through SPC
        if hasattr(self, 'spc') and self.spc.spc_enabled:
            spc_results = self.spc.process_test_results(self.sku, result.to_dict())
            
            # Add SPC results to test result
            result.metadata['spc'] = spc_results
            
            # Apply production violations if any
            if spc_results.get('violations'):
                for violation in spc_results['violations']:
                    result.failures.append(f"SPC: {violation['message']}")
                    
        return result
        
    def new_cleanup(self):
        # Call original cleanup
        original_cleanup(self)
        
        # Export SPC summary if needed
        if hasattr(self, 'spc') and self.spc.spc_enabled:
            summary = self.spc.get_spc_summary(self.sku)
            self.logger.info(f"SPC Summary: {summary}")
            
    # Replace methods
    smt_test_class.__init__ = new_init
    smt_test_class.run_test_sequence = new_run
    smt_test_class.cleanup_hardware = new_cleanup
    
    return smt_test_class


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create SPC integration
    spc = SPCIntegration(
        spc_enabled=True,
        sampling_mode=True,
        production_mode=False
    )
    
    # Example test results
    test_results = {
        'measurements': {
            'mainbeam_readings': {
                'board_results': {
                    'Board 1': {
                        'relay': 1,
                        'voltage': 12.1,
                        'current': 2.05,
                        'power': 24.8
                    },
                    'Board 2': {
                        'relay': 2,
                        'voltage': 12.0,
                        'current': 2.02,
                        'power': 24.2
                    }
                }
            }
        }
    }
    
    # Process results
    spc_results = spc.process_test_results('DD5001', test_results)
    print(f"SPC Results: {spc_results}")
