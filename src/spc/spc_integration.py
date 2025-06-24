"""
SPC Integration for SMT Testing
Integrates Statistical Process Control with existing SMT test flow

Features:
- Automatic data collection during tests
- Control limit application
- Real-time monitoring
- Production mode vs. sampling mode
- Spec limit approval workflow
"""

import logging
from typing import Dict, Optional, List, Tuple, Any
from pathlib import Path
from datetime import datetime
import json

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from src.spc.spc_calculator import SPCCalculator, ControlLimits
from src.spc.data_collector import SPCDataCollector
from src.gui.components.spec_approval_dialog import SpecApprovalDialog
from spc.spc_config import MIN_INDIVIDUAL_MEASUREMENTS


class SPCIntegration(QObject):
    """Integrate SPC with SMT testing"""
    
    # Signal emitted when enough measurements collected for spec calculation
    spec_calculation_ready = Signal(str)  # SKU
    
    def __init__(self, 
                 spc_enabled: bool = True,
                 sampling_mode: bool = True,
                 production_mode: bool = False,
                 data_dir: Optional[Path] = None,
                 logger: Optional[logging.Logger] = None,
                 parent=None):
        """
        Initialize SPC integration
        
        Args:
            spc_enabled: Whether SPC is enabled
            sampling_mode: Collect data for control limit calculation
            production_mode: Apply control limits for pass/fail
            data_dir: Directory for SPC data storage
        """
        super().__init__(parent)
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.spc_enabled = spc_enabled
        self.sampling_mode = sampling_mode
        self.production_mode = production_mode
        
        # Track measurements for spec calculation trigger
        self.measurement_counts = {}
        self.spec_calculation_triggered = set()  # SKUs that have triggered calculation
        
        if self.spc_enabled:
            self.data_collector = SPCDataCollector(
                data_dir=data_dir,
                logger=self.logger
            )
            self.calculator = SPCCalculator(logger=self.logger)
        else:
            self.data_collector = None
            self.calculator = None
            
    def add_measurement(self, sku: str, function: str, board: str, 
                       current: float, voltage: float = None) -> None:
        """
        Add a measurement to SPC data collection
        
        Args:
            sku: SKU identifier
            function: Function type (e.g., 'mainbeam')
            board: Board identifier (e.g., 'Board_1')
            current: Current measurement
            voltage: Optional voltage measurement
        """
        if not self.spc_enabled or not self.sampling_mode:
            return
            
        try:
            # Add to data collector
            self.data_collector.add_measurement(sku, function, board, current, voltage)
            
            # Track measurement count
            key = f"{sku}_{function}_{board}"
            self.measurement_counts[key] = self.measurement_counts.get(key, 0) + 1
            
            # Check if we've reached the threshold for spec calculation
            self._check_spec_calculation_threshold(sku)
            
        except Exception as e:
            self.logger.error(f"Error adding SPC measurement: {e}")
            
    def _check_spec_calculation_threshold(self, sku: str):
        """Check if we have enough measurements to calculate specs"""
        if sku in self.spec_calculation_triggered:
            return  # Already triggered for this SKU
            
        # Get total measurements for this SKU
        total_measurements = sum(
            count for key, count in self.measurement_counts.items() 
            if key.startswith(f"{sku}_")
        )
        
        if total_measurements >= MIN_INDIVIDUAL_MEASUREMENTS:
            self.logger.info(f"Reached {total_measurements} measurements for {sku}, ready for spec calculation")
            self.spec_calculation_triggered.add(sku)
            self.spec_calculation_ready.emit(sku)
            
    def check_control_limits(self, sku: str, function: str, board: str, 
                           value: float) -> List[str]:
        """
        Check if value violates control limits
        
        Args:
            sku: SKU identifier
            function: Function type
            board: Board identifier
            value: Measurement value to check
            
        Returns:
            List of violation messages (empty if no violations)
        """
        if not self.spc_enabled or not self.production_mode:
            return []
            
        violations = []
        
        try:
            # Get control limits
            limits = self.data_collector.get_limits(sku, function, board)
            
            if limits:
                # Check X-bar limits (simplified - using individual value)
                if value > limits.xbar_ucl:
                    violations.append(
                        f"{function} {board} value {value:.3f} exceeds UCL {limits.xbar_ucl:.3f}"
                    )
                elif value < limits.xbar_lcl:
                    violations.append(
                        f"{function} {board} value {value:.3f} below LCL {limits.xbar_lcl:.3f}"
                    )
                    
        except Exception as e:
            self.logger.error(f"Error checking control limits: {e}")
            
        return violations
        
    def process_test_results(self, sku: str, test_results: Dict) -> Tuple[bool, List[str]]:
        """
        Process test results for SPC
        
        Args:
            sku: SKU identifier
            test_results: Dictionary of test results
            
        Returns:
            Tuple of (pass/fail, list of violations)
        """
        if not self.spc_enabled:
            return True, []
            
        violations = []
        
        try:
            # Extract measurements from test results
            measurements = self._extract_measurements(test_results)
            
            # Add to data collection if in sampling mode
            if self.sampling_mode:
                for (function, board), values in measurements.items():
                    self.add_measurement(sku, function, board, 
                                       values['current'], values.get('voltage'))
                    
            # Check control limits if in production mode
            if self.production_mode:
                for (function, board), values in measurements.items():
                    limit_violations = self.check_control_limits(
                        sku, function, board, values['current']
                    )
                    violations.extend(limit_violations)
                    
        except Exception as e:
            self.logger.error(f"Error processing SPC results: {e}")
            violations.append(f"SPC processing error: {str(e)}")
            
        return len(violations) == 0, violations
        
    def _extract_measurements(self, test_results: Dict) -> Dict[Tuple[str, str], Dict]:
        """
        Extract measurements from test results
        
        Returns:
            Dictionary mapping (function, board) to measurements
        """
        measurements = {}
        
        # Navigate through the test results structure
        if 'measurements' in test_results:
            for function, boards in test_results['measurements'].items():
                if isinstance(boards, dict):
                    for board, values in boards.items():
                        if isinstance(values, dict) and 'current' in values:
                            board_id = board.replace(' ', '_')
                            measurements[(function, board_id)] = {
                                'current': values['current'],
                                'voltage': values.get('voltage', 0)
                            }
                            
        return measurements
        
    def show_spec_approval_dialog(self, sku: str, parent=None):
        """Show dialog for approving new spec limits"""
        try:
            # Get current specs from SKU files
            current_specs = self._load_current_specs(sku)
            
            # Calculate proposed specs
            proposed_specs = {}
            measurement_data = {
                'total_measurements': 0,
                'measurement_count': self.data_collector.get_measurement_count(sku)
            }
            
            # Calculate total measurements
            measurement_data['total_measurements'] = sum(measurement_data['measurement_count'].values())
            
            # Derive specs for each function/board
            results = self.data_collector.recalculate_all_specs(sku)
            
            if not results:
                QMessageBox.warning(parent, "No Data", 
                                  "No specification limits could be calculated. Insufficient data.")
                return
                
            # Convert derived specs to proposed format
            for key, spec in results.items():
                proposed_specs[key] = {
                    'lsl': spec.lsl,
                    'usl': spec.usl,
                    'target': spec.target,
                    'cp': spec.expected_cp
                }
                
            # Show approval dialog
            dialog = SpecApprovalDialog(current_specs, proposed_specs, measurement_data, parent)
            dialog.specs_approved.connect(lambda specs: self._save_approved_specs(sku, specs))
            dialog.exec_()
            
        except Exception as e:
            self.logger.error(f"Error showing spec approval dialog: {e}")
            QMessageBox.critical(parent, "Error", f"Failed to show approval dialog: {str(e)}")
            
    def _load_current_specs(self, sku: str) -> Dict:
        """Load current spec limits from SKU configuration"""
        specs = {}
        
        try:
            # Load SKU configuration
            sku_file = Path("config/skus") / f"{sku}.json"
            if sku_file.exists():
                with open(sku_file, 'r') as f:
                    sku_data = json.load(f)
                    
                # Extract limits from test sequences
                for sequence in sku_data.get('test_sequences', []):
                    if 'function' in sequence and 'limits' in sequence:
                        function = sequence['function']
                        limits = sequence['limits'].get('current_A', {})
                        
                        # Add for each board (simplified - assuming same limits)
                        for i in range(1, 17):  # Max 16 boards
                            key = f"{function}_Board_{i}"
                            if limits:
                                specs[key] = {
                                    'lsl': limits.get('min', 0),
                                    'usl': limits.get('max', 0)
                                }
                                
        except Exception as e:
            self.logger.error(f"Error loading current specs: {e}")
            
        return specs
        
    def _save_approved_specs(self, sku: str, approved_specs: Dict):
        """Save approved specs back to SKU configuration"""
        try:
            # Get user info
            from src.auth.user_manager import get_user_manager
            user_manager = get_user_manager()
            current_user = user_manager.get_current_user() or "unknown"
            
            # Update SKU configuration with new limits
            sku_file = Path("config/skus") / f"{sku}.json"
            
            # Create timestamped backup in archive directory
            archive_dir = Path("config/skus/archive")
            archive_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = archive_dir / f"{sku}_{timestamp}.json"
            
            if sku_file.exists():
                import shutil
                shutil.copy2(sku_file, backup_file)
                self.logger.info(f"Created archive: {backup_file}")
            
            # Load and update SKU data
            if sku_file.exists():
                with open(sku_file, 'r') as f:
                    sku_data = json.load(f)
                
                # Track changes
                changes = []
                    
                # Update limits in test sequences
                for sequence in sku_data.get('test_sequences', []):
                    if 'function' in sequence:
                        function = sequence['function']
                        
                        # Find the first board's limits for this function
                        for key, spec in approved_specs.items():
                            if key.startswith(f"{function}_"):
                                # Track old values
                                old_limits = sequence.get('limits', {}).get('current_A', {})
                                old_min = old_limits.get('min', 'N/A')
                                old_max = old_limits.get('max', 'N/A')
                                
                                # Update limits
                                if 'limits' not in sequence:
                                    sequence['limits'] = {}
                                sequence['limits']['current_A'] = {
                                    'min': spec['lsl'],
                                    'max': spec['usl']
                                }
                                
                                # Record change
                                changes.append({
                                    'function': function,
                                    'old_min': old_min,
                                    'old_max': old_max,
                                    'new_min': spec['lsl'],
                                    'new_max': spec['usl']
                                })
                                break
                
                # Add metadata about the change
                if 'metadata' not in sku_data:
                    sku_data['metadata'] = {}
                
                sku_data['metadata']['last_spec_update'] = {
                    'timestamp': datetime.now().isoformat(),
                    'user': current_user,
                    'method': 'spec_calculator',
                    'changes': changes
                }
                                
                # Save updated configuration
                with open(sku_file, 'w') as f:
                    json.dump(sku_data, f, indent=2)
                    
                self.logger.info(f"Updated spec limits in {sku_file}")
                
                # Clear the trigger so it can be recalculated again if needed
                self.spec_calculation_triggered.discard(sku)
                
                # Log the change
                user_manager.log_action("spec_limit_update_sku", {
                    'sku': sku,
                    'backup_file': str(backup_file),
                    'changes': changes
                })
                
        except Exception as e:
            self.logger.error(f"Error saving approved specs: {e}")
            
    def get_spc_status(self) -> Dict:
        """Get current SPC status"""
        return {
            'enabled': self.spc_enabled,
            'sampling_mode': self.sampling_mode,
            'production_mode': self.production_mode,
            'measurement_counts': self.measurement_counts.copy()
        }


def integrate_spc_with_smt_test(smt_test_instance, spc_integration: SPCIntegration):
    """
    Helper function to integrate SPC with an SMT test instance
    
    Args:
        smt_test_instance: The SMT test instance to integrate with
        spc_integration: The SPC integration instance
    """
    # This is a placeholder function that was referenced but not implemented
    # The actual integration happens through the SPCIntegration class methods
    pass