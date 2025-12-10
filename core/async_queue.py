"""
Async Queue for Background Vector Store Operations
Handles non-blocking vector store updates for improved response time.
"""
import threading
import queue
from typing import Callable, Any, Tuple
from src.utils.logging_utils import log_progress


class VectorStoreQueue:
    """
    Thread-safe queue for background vector store operations.
    
    Design:
    - DB saves are synchronous (fast, critical)
    - Vector store saves are asynchronous (slow, can be deferred)
    - If vector save fails, dirty flag is set for rebuild
    """
    
    def __init__(self):
        self._queue = queue.Queue()
        self._worker_thread = None
        self._shutdown = False
        
    def enqueue(self, func: Callable, *args, **kwargs):
        """
        Add a vector store task to the background queue.
        
        Args:
            func: Function to execute (e.g., add_memory_to_vector_store)
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
        """
        self._queue.put((func, args, kwargs))
        self._ensure_worker_running()
        
    def _ensure_worker_running(self):
        """Start worker thread if not already running."""
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._worker_thread = threading.Thread(
                target=self._worker,
                daemon=True,  # Don't block program exit
                name="VectorStoreWorker"
            )
            self._worker_thread.start()
            log_progress("🔄 Vector store background worker started")
    
    def _worker(self):
        """Background worker that processes the queue."""
        while not self._shutdown:
            try:
                # Wait up to 1 second for a task
                func, args, kwargs = self._queue.get(timeout=1.0)
                
                # Execute the task
                try:
                    func(*args, **kwargs)
                    log_progress(f"✅ Background vector store task completed: {func.__name__}")
                except Exception as e:
                    log_progress(f"❌ Background vector store task failed: {func.__name__}, error: {e}")
                    # Mark vector store as dirty for rebuild
                    from src.utils.vector_utils import mark_vector_store_dirty
                    mark_vector_store_dirty()
                finally:
                    self._queue.task_done()
                    
            except queue.Empty:
                # No tasks available, continue waiting
                continue
            except Exception as e:
                log_progress(f"❌ Unexpected error in vector store worker: {e}")
    
    def wait_for_completion(self):
        """
        Wait for all queued tasks to complete.
        Useful for testing or graceful shutdown.
        """
        self._queue.join()
    
    def shutdown(self):
        """Gracefully shutdown the worker thread."""
        self._shutdown = True
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
            log_progress("🛑 Vector store background worker stopped")


# Global queue instance (singleton)
_vector_queue = None


def get_vector_queue() -> VectorStoreQueue:
    """Get or create the global vector store queue."""
    global _vector_queue
    if _vector_queue is None:
        _vector_queue = VectorStoreQueue()
    return _vector_queue
