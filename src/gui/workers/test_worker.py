# gui/workers/test_worker.py
from PySide6.QtCore import QThread, Signal
from src.core.base_test import TestResult
from src.utils.thread_cleanup import ThreadCleanupMixin
import logging


class TestWorker(QThread, ThreadCleanupMixin):
    """Worker thread to run tests without blocking GUI"""

    progress_updated = Signal(str, int)  # message, percentage
    test_completed = Signal(object)  # TestResult object
    pressure_data = Signal(float)  # live pressure data
    test_phase_changed = Signal(str)  # test phase notifications

    def __init__(self, test_instance):
        QThread.__init__(self)
        ThreadCleanupMixin.__init__(self)
        self.test_instance = test_instance
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Register this QThread for tracking
        self.register_qthread(self, "test_worker")

    def run(self):
        """Run the test in background thread"""
        try:
            self.logger.info(f"Starting test worker for {type(self.test_instance).__name__}")
            
            # Connect progress callback
            if hasattr(self.test_instance, 'set_progress_callback'):
                self.test_instance.set_progress_callback(self.progress_updated.emit)
                
            # Connect pressure data callback for live updates
            if hasattr(self.test_instance, 'set_pressure_callback'):
                self.test_instance.set_pressure_callback(self.pressure_data.emit)
                
            # Connect test phase callback
            if hasattr(self.test_instance, 'set_phase_callback'):
                self.test_instance.set_phase_callback(self.test_phase_changed.emit)

            # Execute test
            result = self.test_instance.execute()

            # Emit result
            self.test_completed.emit(result)
            
            self.logger.info("Test worker completed successfully")

        except Exception as e:
            self.logger.error(f"Test execution error: {e}")
            
            # Create a failed result
            result = TestResult()
            result.failures.append(f"Test execution error: {str(e)}")
            result.calculate_overall_result()
            self.test_completed.emit(result)
