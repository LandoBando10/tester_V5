"""
Example: Integrating SPC with existing SMT test system

This file shows how to modify the existing SMT test files to add SPC support.
Copy these modifications to your actual files.
"""

# ============================================
# Modification 1: Update SMTTest class
# File: src/core/smt_test.py
# ============================================

# Add to imports at top of file:
from src.spc import SPCIntegration

# Modify __init__ method to accept spc_config:
def __init__(self, sku: str, parameters: Dict[str, Any], port: str, 
             programming_config: Optional[Dict] = None, 
             smt_config_path: Optional[str] = None, 
             arduino_controller=None,
             spc_config: Optional[Dict] = None):  # ADD THIS
    # ... existing init code ...
    
    # Add SPC integration
    self.spc_config = spc_config or {}
    self.spc = None
    if self.spc_config.get('enabled', False):
        self.spc = SPCIntegration(
            spc_enabled=True,
            sampling_mode=self.spc_config.get('sampling_mode', True),
            production_mode=self.spc_config.get('production_mode', False),
            logger=self.logger
        )

# Modify run_test_sequence to integrate SPC:
def run_test_sequence(self) -> TestResult:
    # ... existing test code ...
    
    # After getting panel measurements, before final analysis:
    if self.spc:
        # Convert panel results to format expected by SPC
        spc_test_results = {
            'measurements': {}
        }
        
        # Add all function results
        for function_key, function_data in self.result.measurements.items():
            if function_key.endswith('_readings'):
                spc_test_results['measurements'][function_key] = function_data
        
        # Process through SPC
        spc_results = self.spc.process_test_results(self.sku, spc_test_results)
        
        # Add SPC results to test metadata
        self.result.metadata['spc'] = spc_results
        
        # If in production mode, add violations as failures
        if spc_results.get('violations'):
            for violation in spc_results['violations']:
                self.result.failures.append(f"SPC: {violation['message']}")
    
    # Continue with existing analysis...
    self._analyze_results()
    return self.result


# ============================================
# Modification 2: Update SMT Handler
# File: src/gui/handlers/smt_handler.py
# ============================================

# Add to imports:
from src.spc import SPCControlWidget

# In SMTHandler class, add SPC widget reference:
class SMTHandler:
    def __init__(self, ...):
        # ... existing init ...
        self.spc_widget = None  # Will be set by main window
        
    def set_spc_widget(self, widget: SPCControlWidget):
        """Set reference to SPC control widget"""
        self.spc_widget = widget
        
    # Modify handle_test_complete to update SPC:
    def handle_test_complete(self, result: TestResult):
        # ... existing code ...
        
        # Update SPC if enabled and test passed
        if self.spc_widget and result.passed and 'spc' in result.metadata:
            if result.metadata['spc'].get('data_collected'):
                self.spc_widget.add_test_results(self.current_sku, result.to_dict())


# ============================================
# Modification 3: Update Main Window
# File: src/gui/main_window.py
# ============================================

# Add to imports:
from src.spc import SPCControlWidget

# In MainWindow.__init__, add SPC widget:
def __init__(self):
    # ... existing init ...
    
    # Create SPC widget
    self.spc_widget = SPCControlWidget()
    
    # Add to tab widget (or wherever appropriate)
    self.tab_widget.addTab(self.spc_widget, "SPC Control")
    
    # Connect to SMT handler
    if hasattr(self, 'smt_handler'):
        self.smt_handler.set_spc_widget(self.spc_widget)
    
    # Update SKU list when available
    self.spc_widget.update_sku_list(self.get_available_skus())


# ============================================
# Modification 4: Update Configuration
# File: src/gui/components/config/config_editor.py
# ============================================

# Add SPC configuration section to config editor:
def create_spc_section(self) -> QGroupBox:
    """Create SPC configuration section"""
    group = QGroupBox("Statistical Process Control")
    layout = QFormLayout()
    
    # Enable SPC
    self.spc_enabled = QCheckBox("Enable SPC")
    self.spc_enabled.setChecked(False)
    layout.addRow("Enable:", self.spc_enabled)
    
    # Sampling mode
    self.spc_sampling = QCheckBox("Sampling Mode (Collect Data)")
    self.spc_sampling.setChecked(True)
    layout.addRow("Sampling:", self.spc_sampling)
    
    # Production mode
    self.spc_production = QCheckBox("Production Mode (Enforce Limits)")
    self.spc_production.setChecked(False)
    layout.addRow("Production:", self.spc_production)
    
    # Subgroup size
    self.spc_subgroup_size = QSpinBox()
    self.spc_subgroup_size.setRange(2, 10)
    self.spc_subgroup_size.setValue(5)
    layout.addRow("Subgroup Size:", self.spc_subgroup_size)
    
    group.setLayout(layout)
    return group

# Update get_configuration to include SPC:
def get_configuration(self) -> dict:
    config = {
        # ... existing config ...
        'spc_config': {
            'enabled': self.spc_enabled.isChecked(),
            'sampling_mode': self.spc_sampling.isChecked(),
            'production_mode': self.spc_production.isChecked(),
            'subgroup_size': self.spc_subgroup_size.value()
        }
    }
    return config


# ============================================
# Modification 5: Update Test Execution
# File: src/gui/workers/smt_worker.py
# ============================================

# In SMTWorker.run method, pass SPC config to test:
def run(self):
    try:
        # ... existing code ...
        
        # Create test with SPC config
        self.test = SMTTest(
            sku=self.sku,
            parameters=self.parameters,
            port=self.port,
            programming_config=self.programming_config,
            arduino_controller=self.arduino,
            spc_config=self.config.get('spc_config', {})  # ADD THIS
        )
        
        # ... rest of existing code ...


# ============================================
# Example Usage in Production
# ============================================

def example_production_setup():
    """Example of setting up SPC for production"""
    
    # Phase 1: Initial data collection (1-2 weeks)
    initial_config = {
        'spc_config': {
            'enabled': True,
            'sampling_mode': True,    # Collect data
            'production_mode': False, # Don't enforce yet
            'subgroup_size': 5
        }
    }
    
    # Phase 2: After validating control limits
    production_config = {
        'spc_config': {
            'enabled': True,
            'sampling_mode': False,   # Stop collecting
            'production_mode': True,  # Enforce limits
            'subgroup_size': 5
        }
    }
    
    # Phase 3: Continuous improvement (quarterly)
    improvement_config = {
        'spc_config': {
            'enabled': True,
            'sampling_mode': True,    # Collect new baseline
            'production_mode': True,  # Still enforce old limits
            'subgroup_size': 5
        }
    }


# ============================================
# Menu Actions for SPC
# ============================================

# Add to menu bar:
def create_spc_menu(self):
    """Create SPC menu"""
    spc_menu = self.menuBar().addMenu("SPC")
    
    # Export limits action
    export_action = QAction("Export Control Limits", self)
    export_action.triggered.connect(self.export_control_limits)
    spc_menu.addAction(export_action)
    
    # Import limits action
    import_action = QAction("Import Control Limits", self)
    import_action.triggered.connect(self.import_control_limits)
    spc_menu.addAction(import_action)
    
    # View report action
    report_action = QAction("Generate SPC Report", self)
    report_action.triggered.connect(self.generate_spc_report)
    spc_menu.addAction(report_action)

def export_control_limits(self):
    """Export current control limits"""
    if self.spc_widget:
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Control Limits",
            f"control_limits_{datetime.now():%Y%m%d}.json",
            "JSON Files (*.json)"
        )
        if filename:
            # Export from SPC widget's data collector
            self.spc_widget.data_collector.export_production_limits(Path(filename))
