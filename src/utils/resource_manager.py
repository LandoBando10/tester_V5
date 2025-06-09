"""
Resource management utilities for Diode Dynamics Tester V4.

Provides base classes and utilities for resource tracking, cleanup,
and thread management to prevent resource leaks during testing.
"""

import threading
import logging
import time
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod


class ResourceMixin:
    """
    Mixin class for resource management and cleanup.
    
    Provides functionality to track and cleanup resources like threads,
    file handles, and network connections.
    """
    
    def __init__(self):
        """Initialize resource tracking."""
        self._resources: Dict[str, Any] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._qthreads: Dict[str, Any] = {}  # For QThread objects
        self._cleanup_callbacks: List[callable] = []
        self._resource_lock = threading.Lock()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def register_resource(self, resource: Any, name: str, cleanup_callback: Optional[callable] = None):
        """
        Register a resource for tracking and cleanup.
        
        Args:
            resource: The resource to track
            name: Unique name for the resource
            cleanup_callback: Optional callback for custom cleanup
        """
        with self._resource_lock:
            self._resources[name] = resource
            if cleanup_callback:
                self._cleanup_callbacks.append(cleanup_callback)
        
        self.logger.debug(f"Registered resource: {name}")
    
    def register_thread(self, thread: threading.Thread, name: str) -> str:
        """
        Register a thread for tracking and cleanup.
        
        Args:
            thread: The thread to track
            name: Base name for the thread
            
        Returns:
            Unique thread ID
        """
        with self._resource_lock:
            # Generate unique thread ID
            thread_id = f"{name}_{id(thread)}"
            self._threads[thread_id] = thread
        
        self.logger.debug(f"Registered thread: {thread_id}")
        return thread_id
    
    def register_qthread(self, qthread, name: str) -> str:
        """
        Register a QThread for tracking and cleanup.
        
        Args:
            qthread: The QThread to track
            name: Base name for the thread
            
        Returns:
            Unique thread ID
        """
        with self._resource_lock:
            # Generate unique thread ID
            thread_id = f"{name}_{id(qthread)}"
            # Store QThread in a separate dictionary if needed
            if not hasattr(self, '_qthreads'):
                self._qthreads = {}
            self._qthreads[thread_id] = qthread
        
        self.logger.debug(f"Registered QThread: {thread_id}")
        return thread_id
    
    def unregister_resource(self, name: str):
        """
        Unregister a resource.
        
        Args:
            name: Name of the resource to unregister
        """
        with self._resource_lock:
            if name in self._resources:
                del self._resources[name]
                self.logger.debug(f"Unregistered resource: {name}")
    
    def unregister_thread(self, thread_id: str):
        """
        Unregister a thread.
        
        Args:
            thread_id: ID of the thread to unregister
        """
        with self._resource_lock:
            if thread_id in self._threads:
                del self._threads[thread_id]
                self.logger.debug(f"Unregistered thread: {thread_id}")
    
    def cleanup_resources(self):
        """Clean up all tracked resources."""
        self.logger.info("Starting resource cleanup")
        
        # Clean up threads first (includes QThreads)
        self._cleanup_threads()
        
        # Run cleanup callbacks
        for callback in self._cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                self.logger.error(f"Error in cleanup callback: {e}")
        
        # Clear resources
        with self._resource_lock:
            self._resources.clear()
            self._qthreads.clear()
            self._cleanup_callbacks.clear()
        
        self.logger.info("Resource cleanup completed")
    
    def _cleanup_threads(self):
        """Clean up all tracked threads."""
        with self._resource_lock:
            threads_to_cleanup = list(self._threads.items())
            qthreads_to_cleanup = list(getattr(self, '_qthreads', {}).items())
        
        # Clean up regular threads
        for thread_id, thread in threads_to_cleanup:
            try:
                if thread.is_alive():
                    self.logger.debug(f"Waiting for thread to finish: {thread_id}")
                    thread.join(timeout=5.0)
                    
                    if thread.is_alive():
                        self.logger.warning(f"Thread did not terminate gracefully: {thread_id}")
                    else:
                        self.logger.debug(f"Thread terminated successfully: {thread_id}")
                
                self.unregister_thread(thread_id)
                
            except Exception as e:
                self.logger.error(f"Error cleaning up thread {thread_id}: {e}")
        
        # Clean up QThreads
        for thread_id, qthread in qthreads_to_cleanup:
            try:
                if qthread.isRunning():
                    self.logger.debug(f"Terminating QThread: {thread_id}")
                    qthread.terminate()
                    
                    if not qthread.wait(5000):  # Wait up to 5 seconds
                        self.logger.warning(f"QThread did not terminate gracefully: {thread_id}")
                    else:
                        self.logger.debug(f"QThread terminated successfully: {thread_id}")
                
                # Remove from tracking
                with self._resource_lock:
                    if hasattr(self, '_qthreads') and thread_id in self._qthreads:
                        del self._qthreads[thread_id]
                
            except Exception as e:
                self.logger.error(f"Error cleaning up QThread {thread_id}: {e}")
    
    def get_resource_status(self) -> Dict[str, Any]:
        """
        Get status of all tracked resources.
        
        Returns:
            Dictionary containing resource status information
        """
        with self._resource_lock:
            status = {
                "resources": list(self._resources.keys()),
                "threads": {},
                "qthreads": {},
                "cleanup_callbacks": len(self._cleanup_callbacks)
            }
            
            for thread_id, thread in self._threads.items():
                status["threads"][thread_id] = {
                    "alive": thread.is_alive(),
                    "daemon": thread.daemon,
                    "name": thread.name
                }
            
            # Add QThread status
            for thread_id, qthread in getattr(self, '_qthreads', {}).items():
                status["qthreads"][thread_id] = {
                    "running": qthread.isRunning(),
                    "finished": qthread.isFinished()
                }
            
            return status


class ResourceManager:
    """
    Singleton resource manager for global resource tracking.
    
    Provides centralized resource management across the application.
    """
    
    _instance: Optional['ResourceManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the resource manager."""
        if not hasattr(self, '_initialized'):
            self._global_resources: Dict[str, Any] = {}
            self._global_threads: Dict[str, threading.Thread] = {}
            self._shutdown_hooks: List[callable] = []
            self._resource_lock = threading.Lock()
            self.logger = logging.getLogger(self.__class__.__name__)
            self._initialized = True
    
    def register_global_resource(self, resource: Any, name: str):
        """Register a global resource."""
        with self._resource_lock:
            self._global_resources[name] = resource
        self.logger.debug(f"Registered global resource: {name}")
    
    def register_shutdown_hook(self, callback: callable):
        """Register a shutdown hook."""
        with self._resource_lock:
            self._shutdown_hooks.append(callback)
        self.logger.debug("Registered shutdown hook")
    
    def cleanup_all(self):
        """Clean up all global resources."""
        self.logger.info("Starting global resource cleanup")
        
        # Run shutdown hooks
        for hook in self._shutdown_hooks:
            try:
                hook()
            except Exception as e:
                self.logger.error(f"Error in shutdown hook: {e}")
        
        # Clean up threads
        with self._resource_lock:
            threads_to_cleanup = list(self._global_threads.items())
        
        for thread_id, thread in threads_to_cleanup:
            try:
                if thread.is_alive():
                    thread.join(timeout=3.0)
                    if thread.is_alive():
                        self.logger.warning(f"Global thread did not terminate: {thread_id}")
            except Exception as e:
                self.logger.error(f"Error cleaning up global thread {thread_id}: {e}")
        
        # Clear all resources
        with self._resource_lock:
            self._global_resources.clear()
            self._global_threads.clear()
            self._shutdown_hooks.clear()
        
        self.logger.info("Global resource cleanup completed")


class CleanupContext:
    """
    Context manager for automatic resource cleanup.
    
    Example:
        with CleanupContext() as cleanup:
            resource = SomeResource()
            cleanup.register(resource, lambda: resource.close())
            # resource will be automatically cleaned up
    """
    
    def __init__(self):
        """Initialize cleanup context."""
        self._cleanup_functions: List[callable] = []
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def __enter__(self):
        """Enter the context."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context and perform cleanup."""
        self.cleanup()
    
    def register(self, resource: Any, cleanup_func: callable):
        """
        Register a resource and its cleanup function.
        
        Args:
            resource: The resource to track
            cleanup_func: Function to call for cleanup
        """
        self._cleanup_functions.append(cleanup_func)
        self.logger.debug(f"Registered cleanup function for {type(resource).__name__}")
    
    def cleanup(self):
        """Perform all registered cleanup operations."""
        for cleanup_func in reversed(self._cleanup_functions):  # LIFO order
            try:
                cleanup_func()
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")
        
        self._cleanup_functions.clear()


class ThreadPool:
    """
    Simple thread pool for managing worker threads.
    
    Provides basic thread pooling with proper cleanup.
    """
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize thread pool.
        
        Args:
            max_workers: Maximum number of worker threads
        """
        self.max_workers = max_workers
        self._workers: List[threading.Thread] = []
        self._shutdown = False
        self._lock = threading.Lock()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def submit(self, func: callable, *args, **kwargs) -> threading.Thread:
        """
        Submit a function to be executed in a worker thread.
        
        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            The thread that will execute the function
        """
        if self._shutdown:
            raise RuntimeError("ThreadPool has been shut down")
        
        with self._lock:
            if len(self._workers) >= self.max_workers:
                # Clean up finished threads
                self._workers = [t for t in self._workers if t.is_alive()]
                
                if len(self._workers) >= self.max_workers:
                    raise RuntimeError(f"Maximum number of workers ({self.max_workers}) reached")
            
            thread = threading.Thread(
                target=self._worker_wrapper,
                args=(func, args, kwargs),
                daemon=True
            )
            self._workers.append(thread)
            thread.start()
            
            self.logger.debug(f"Started worker thread {thread.ident}")
            return thread
    
    def _worker_wrapper(self, func: callable, args: tuple, kwargs: dict):
        """Wrapper for worker function execution."""
        try:
            func(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"Error in worker thread: {e}")
    
    def shutdown(self, wait: bool = True, timeout: float = 5.0):
        """
        Shutdown the thread pool.
        
        Args:
            wait: Whether to wait for threads to finish
            timeout: Maximum time to wait for threads
        """
        self._shutdown = True
        
        if wait:
            end_time = time.time() + timeout
            for thread in self._workers:
                remaining_time = end_time - time.time()
                if remaining_time > 0 and thread.is_alive():
                    thread.join(timeout=remaining_time)
                    
                    if thread.is_alive():
                        self.logger.warning(f"Worker thread {thread.ident} did not terminate")
        
        self.logger.info(f"ThreadPool shutdown complete")
    
    def get_status(self) -> Dict[str, Any]:
        """Get thread pool status."""
        with self._lock:
            alive_workers = [t for t in self._workers if t.is_alive()]
            return {
                "max_workers": self.max_workers,
                "active_workers": len(alive_workers),
                "total_workers": len(self._workers),
                "shutdown": self._shutdown
            }


# Global resource manager instance
_resource_manager = None

def get_resource_manager() -> ResourceManager:
    """Get the global resource manager instance."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager


def get_resource_tracker() -> ResourceManager:
    """Get the global resource manager instance (alias for get_resource_manager)."""
    return get_resource_manager()


def register_exit_handler():
    """Register an exit handler for cleanup."""
    import atexit
    
    def cleanup_on_exit():
        """Cleanup function called on program exit."""
        try:
            get_resource_manager().cleanup_all()
        except Exception as e:
            print(f"Error during exit cleanup: {e}")
    
    atexit.register(cleanup_on_exit)


# Auto-register exit handler when module is imported
register_exit_handler()
