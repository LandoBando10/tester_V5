# gui/workers/smt_worker.py
import logging
from PySide6.QtCore import QThread, Signal
from src.core.base_test import TestResult
from src.utils.resource_manager import ResourceMixin


class SMTWorker(QThread, ResourceMixin):
    """Worker thread for SMT tests"""

    # Signals
    progress_updated = Signal(str, int)            # message, percentage
    test_completed = Signal(object)                # TestResult object
    test_phase_changed = Signal(str)               # test phase notifications
    programming_progress = Signal(int, int, str, str)  # current, total, board_name, status

    def __init__(self, test_instance):
        QThread.__init__(self)
        ResourceMixin.__init__(self)
        self.test_instance = test_instance
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Register this QThread for tracking
        self.register_qthread(self, "smt_worker")

    def run(self):
        """Run the test in background thread"""
        try:
            self.logger.info(f"Starting SMT worker for {self.test_instance.sku}")
            
            # Connect progress callback
            if hasattr(self.test_instance, 'set_progress_callback'):
                self.test_instance.set_progress_callback(self.progress_updated.emit)
                
            # Connect test phase callback
            if hasattr(self.test_instance, 'set_phase_callback'):
                self.test_instance.set_phase_callback(self.test_phase_changed.emit)
                
            # Connect programming progress callback
            if hasattr(self.test_instance, 'set_programming_progress_callback'):
                self.test_instance.set_programming_progress_callback(self.programming_progress.emit)

            # Execute test
            result = self.test_instance.execute()

            # Emit result
            self.test_completed.emit(result)
            
            self.logger.info("SMT worker completed successfully")

        except Exception as e:
            self.logger.error(f"SMT test execution error: {e}", exc_info=True)
            
            # Create a failed result
            result = TestResult()
            result.failures.append(f"Test execution error: {str(e)}")
            result.calculate_overall_result()
            self.test_completed.emit(result)