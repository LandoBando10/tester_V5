"""
Statistical Process Control Module for SMT Testing
"""

from .spc_calculator import SPCCalculator, ControlLimits
from .data_collector import SPCDataCollector
from .spc_widget import SPCWidget
from .spc_integration import SPCIntegration, integrate_spc_with_smt_test
from .simple_spc_integration import SimpleSPCIntegration

__all__ = [
    'SPCCalculator',
    'ControlLimits',
    'SPCDataCollector',
    'SPCWidget',
    'SPCIntegration',
    'SimpleSPCIntegration',
    'integrate_spc_with_smt_test'
]

__version__ = '1.0.0'
