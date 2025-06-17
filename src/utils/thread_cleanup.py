"""
Thread cleanup utilities for Diode Dynamics Tester V5.

Provides simplified thread tracking and cleanup functionality for QThreads
and regular threads used throughout the application.
"""

import threading
import logging
from typing import Dict, Any, Optional


class ThreadCleanupMixin:
    """
    Simplified mixin class for thread tracking and cleanup.
    
    Provides basic functionality to track and cleanup threads,
    particularly QThreads used in Qt workers.
    """
    
    def __init__(self):
        """Initialize thread tracking."""
        self._threads: Dict[str, threading.Thread] = {}
        self._qthreads: Dict[str, Any] = {}
        self._cleanup_callbacks = []
        self._lock = threading.Lock()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def register_qthread(self, qthread: Any, name: str) -> str:
        """
        Register a QThread for tracking and cleanup.
        
        Args:
            qthread: The QThread to track
            name: Base name for the thread
            
        Returns:
            Unique thread ID
        """
        with self._lock:
            # Generate unique thread ID
            thread_id = f"{name}_{id(qthread)}"
            self._qthreads[thread_id] = qthread
        
        self.logger.debug(f"Registered QThread: {thread_id}")
        return thread_id
    
    def register_resource(self, resource: Any, name: str, cleanup_callback: Optional[callable] = None):
        """
        Register a resource for tracking and cleanup.
        
        Args:
            resource: The resource to track (kept for compatibility)
            name: Unique name for the resource
            cleanup_callback: Optional callback for custom cleanup
        """
        if cleanup_callback:
            self._cleanup_callbacks.append(cleanup_callback)
        self.logger.debug(f"Registered resource: {name}")
    
    def cleanup_resources(self):
        """Clean up all tracked threads and resources."""
        self.logger.info("Starting thread cleanup")
        
        # Clean up QThreads
        with self._lock:
            qthreads_to_cleanup = list(self._qthreads.items())
        
        for thread_id, qthread in qthreads_to_cleanup:
            try:
                if qthread.isRunning():
                    self.logger.debug(f"Terminating QThread: {thread_id}")
                    qthread.terminate()
                    
                    if not qthread.wait(5000):  # Wait up to 5 seconds
                        self.logger.warning(f"QThread did not terminate gracefully: {thread_id}")
                    else:
                        self.logger.debug(f"QThread terminated successfully: {thread_id}")
                
            except Exception as e:
                self.logger.error(f"Error cleaning up QThread {thread_id}: {e}")
        
        # Run cleanup callbacks
        for callback in self._cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                self.logger.error(f"Error in cleanup callback: {e}")
        
        # Clear all tracking
        with self._lock:
            self._threads.clear()
            self._qthreads.clear()
            self._cleanup_callbacks.clear()
        
        self.logger.info("Thread cleanup completed")


class GlobalCleanupManager:
    """
    Simplified global cleanup manager for application-wide cleanup.
    
    Used by MainWindow during shutdown.
    """
    
    def __init__(self):
        """Initialize the cleanup manager."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self._shutdown_hooks = []
    
    def cleanup_all(self):
        """Perform global cleanup."""
        self.logger.info("Starting global cleanup")
        
        # Run any shutdown hooks
        for hook in self._shutdown_hooks:
            try:
                hook()
            except Exception as e:
                self.logger.error(f"Error in shutdown hook: {e}")
        
        self._shutdown_hooks.clear()
        self.logger.info("Global cleanup completed")


# For backward compatibility with existing imports
ResourceMixin = ThreadCleanupMixin
ResourceManager = GlobalCleanupManager