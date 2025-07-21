"""
Simplified SPC Integration for SMT Testing
Only supports sampling mode: collect 30 measurements then prompt for spec update
"""

import logging
from typing import Dict, Optional
from pathlib import Path
from datetime import datetime
import json
import shutil
from src.utils.path_manager import get_skus_dir

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from src.spc.spc_calculator import SPCCalculator
from src.spc.data_collector import SPCDataCollector
from src.gui.components.spec_approval_dialog import SpecApprovalDialog
from config.spc.spc_config import MIN_INDIVIDUAL_MEASUREMENTS


class SimpleSPCIntegration(QObject):
    """Simplified SPC integration - sampling mode only"""
    
    # Signal emitted when enough measurements collected
    spec_calculation_ready = Signal(str)  # SKU
    
    def __init__(self, 
                 enabled: bool = True,
                 test_mode: str = 'smt',
                 data_dir: Optional[Path] = None,
                 logger: Optional[logging.Logger] = None,
                 parent=None):
        """
        Initialize simplified SPC integration
        
        Args:
            enabled: Whether SPC data collection is enabled
            test_mode: Test mode (smt, offroad, weight)
            data_dir: Directory for SPC data storage
            logger: Logger instance
        """
        super().__init__(parent)
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.enabled = enabled
        self.test_mode = test_mode.lower()
        
        # Track measurements for spec calculation trigger
        self.measurement_counts = {}
        self.spec_triggered = set()  # SKUs that have triggered calculation
        
        if self.enabled:
            self.data_collector = SPCDataCollector(
                data_dir=data_dir,
                logger=self.logger
            )
            self.calculator = SPCCalculator(logger=self.logger)
            self.logger.info(f"SPC enabled in sampling mode for {self.test_mode}")
        else:
            self.data_collector = None
            self.calculator = None
            self.logger.info("SPC disabled")
            
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
        if not self.enabled:
            return
            
        try:
            # Add to data collector
            self.data_collector.add_measurement(sku, function, board, current, voltage)
            
            # Track measurement count
            key = f"{sku}_{function}_{board}"
            self.measurement_counts[key] = self.measurement_counts.get(key, 0) + 1
            
            # Check if we've reached the threshold
            if sku not in self.spec_triggered:
                total = sum(count for k, count in self.measurement_counts.items() 
                           if k.startswith(f"{sku}_"))
                
                if total >= MIN_INDIVIDUAL_MEASUREMENTS:
                    self.logger.info(f"Reached {total} measurements for {sku}")
                    self.spec_triggered.add(sku)
                    self.spec_calculation_ready.emit(sku)
                    
        except Exception as e:
            self.logger.error(f"Error adding measurement: {e}")
            
    def show_spec_approval_dialog(self, sku: str, parent=None):
        """Show dialog for approving new spec limits"""
        try:
            # Load current specs from SKU file
            current_specs = self._load_current_specs(sku)
            
            # Calculate proposed specs from collected data
            self.data_collector.flush_pending_measurements()
            results = self.data_collector.recalculate_all_specs(sku)
            
            if not results:
                QMessageBox.warning(parent, "No Data", 
                                  "No specification limits could be calculated. Insufficient data.")
                return
                
            # Convert to proposed format
            proposed_specs = {}
            for key, spec in results.items():
                proposed_specs[key] = {
                    'lsl': spec.lsl,
                    'usl': spec.usl,
                    'target': spec.target,
                    'cp': spec.expected_cp
                }
                
            # Prepare measurement data
            measurement_data = {
                'total_measurements': sum(self.measurement_counts.values()),
                'measurement_count': self.data_collector.get_measurement_count(sku)
            }
            
            # Show approval dialog
            dialog = SpecApprovalDialog(current_specs, proposed_specs, measurement_data, parent)
            
            # Use functools.partial instead of lambda for better reliability
            from functools import partial
            dialog.specs_approved.connect(partial(self._save_approved_specs, sku))
            dialog.exec_()
            
        except Exception as e:
            self.logger.error(f"Error showing spec approval dialog: {e}")
            QMessageBox.critical(parent, "Error", f"Failed to show approval dialog: {str(e)}")
            
    def _load_current_specs(self, sku: str) -> Dict:
        """Load current spec limits from SKU configuration"""
        specs = {}
        
        try:
            # Try mode-specific path first
            sku_file = get_skus_dir() / self.test_mode / f"{sku}.json"
            if not sku_file.exists():
                # Fallback to root for backward compatibility
                sku_file = get_skus_dir() / f"{sku}.json"
                
            if sku_file.exists():
                with open(sku_file, 'r') as f:
                    sku_data = json.load(f)
                    
                # Extract limits from test_sequence
                for sequence in sku_data.get('test_sequence', []):
                    if 'function' in sequence and 'limits' in sequence:
                        function = sequence['function']
                        limits = sequence['limits'].get('current_a', {})
                        
                        # Assume same limits for all boards
                        # Get board count from panel_layout
                        total_boards = sku_data.get('panel_layout', {}).get('total_boards', 16)
                        
                        for i in range(1, total_boards + 1):
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
        """Save approved specs back to SKU configuration with traceability"""
        try:
            # Get user info for traceability
            from src.auth.user_manager import get_user_manager
            user_manager = get_user_manager()
            current_user = user_manager.get_current_user() or "unknown"
            
            # Find SKU file
            sku_file = get_skus_dir() / self.test_mode / f"{sku}.json"
            if not sku_file.exists():
                sku_file = get_skus_dir() / f"{sku}.json"
                
            if not sku_file.exists():
                self.logger.error(f"SKU file not found for {sku}")
                return
                
            # Create timestamped backup for traceability
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_dir = sku_file.parent / "archive"
            archive_dir.mkdir(exist_ok=True)
            backup_file = archive_dir / f"{sku}_{timestamp}_before_spc_update.json"
            
            # Copy current file to archive
            shutil.copy2(sku_file, backup_file)
            self.logger.info(f"Created backup: {backup_file}")
            
            # Load current SKU data
            with open(sku_file, 'r') as f:
                sku_data = json.load(f)
            
            # Track changes for traceability
            changes = []
                
            # Update limits in test_sequence
            for sequence in sku_data.get('test_sequence', []):
                if 'function' in sequence:
                    function = sequence['function']
                    
                    # Find any board's limits for this function (they're all the same)
                    for key, spec in approved_specs.items():
                        if key.startswith(f"{function}_"):
                            # Track old values
                            old_limits = sequence.get('limits', {}).get('current_a', {})
                            old_min = old_limits.get('min', 'N/A')
                            old_max = old_limits.get('max', 'N/A')
                            
                            # Update limits
                            if 'limits' not in sequence:
                                sequence['limits'] = {}
                            sequence['limits']['current_a'] = {
                                'min': round(spec['lsl'], 3),
                                'max': round(spec['usl'], 3)
                            }
                            
                            # Record change
                            changes.append({
                                'function': function,
                                'old_min': old_min,
                                'old_max': old_max,
                                'new_min': round(spec['lsl'], 3),
                                'new_max': round(spec['usl'], 3)
                            })
                            break
            
            # Add metadata for traceability
            if 'metadata' not in sku_data:
                sku_data['metadata'] = {}
            
            sku_data['metadata']['last_spc_update'] = {
                'timestamp': datetime.now().isoformat(),
                'user': current_user,
                'method': 'spc_sampling',
                'measurement_count': sum(self.measurement_counts.values()),
                'backup_file': str(backup_file.name),
                'changes': changes
            }
                            
            # Save updated configuration
            with open(sku_file, 'w') as f:
                json.dump(sku_data, f, indent=2)
                
            self.logger.info(f"Updated spec limits in {sku_file}")
            
            # Clear the trigger so user can collect another 30 samples if needed
            self.spec_triggered.discard(sku)
            
            # Log the change for audit trail
            user_manager.log_action("spc_spec_update", {
                'sku': sku,
                'backup_file': str(backup_file),
                'changes': changes,
                'measurement_count': sum(self.measurement_counts.values())
            })
            
            # Show success message
            QMessageBox.information(None, "Success", 
                                  f"Specification limits updated successfully.\n"
                                  f"Backup saved to: archive/{backup_file.name}")
                                  
        except Exception as e:
            self.logger.error(f"Error saving approved specs: {e}")
            QMessageBox.critical(None, "Error", f"Failed to save specs: {str(e)}")
            
    def get_status(self) -> Dict:
        """Get current SPC status"""
        return {
            'enabled': self.enabled,
            'test_mode': self.test_mode,
            'measurement_counts': self.measurement_counts.copy(),
            'triggered_skus': list(self.spec_triggered)
        }