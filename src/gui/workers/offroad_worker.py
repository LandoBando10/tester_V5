# gui/workers/offroad_worker.py
import logging
from PySide6.QtCore import QThread, Signal
from src.core.base_test import TestResult
from src.utils.thread_cleanup import ThreadCleanupMixin


class OffroadWorker(QThread, ThreadCleanupMixin):
    """Worker thread for Offroad tests"""

    # Signals
    progress_updated = Signal(str, int)  # message, percentage
    test_completed = Signal(object)      # TestResult object
    pressure_data = Signal(float)        # live pressure data
    test_phase_changed = Signal(str)     # test phase notifications

    def __init__(self, test_instance):
        QThread.__init__(self)
        ThreadCleanupMixin.__init__(self)
        self.test_instance = test_instance
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Register this QThread for tracking
        self.register_qthread(self, "offroad_worker")

    def run(self):
        """Run the test in background thread"""
        try:
            self.logger.info(f"Starting Offroad worker for {self.test_instance.sku}")
            
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
            
            self.logger.info("Offroad worker completed successfully")

        except Exception as e:
            self.logger.error(f"Offroad test execution error: {e}", exc_info=True)
            
            # Create a failed result
            result = TestResult()
            result.failures.append(f"Test execution error: {str(e)}")
            result.calculate_overall_result()
            self.test_completed.emit(result)