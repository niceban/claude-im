"""ClaudeNode adapter with subprocess lifecycle management."""
import asyncio
import json
import os
import signal
import subprocess
import sys
import threading
import time
from queue import Queue, Empty
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

from config.settings import CLAUDE_NODE_PATH, CLAUDE_NODE_TIMEOUT

# Import ClaudeController from claude_node package
# Add CLAUDE_NODE_PATH to sys.path temporarily
if CLAUDE_NODE_PATH not in sys.path:
    sys.path.insert(0, CLAUDE_NODE_PATH)
from claude_node.controller import ClaudeController


class StreamQueue:
    """Per-request streaming queue for SSE responses."""

    def __init__(self):
        self.queue: Queue = Queue()
        self.done = False

    def put(self, msg) -> None:
        """Add a message to the queue."""
        self.queue.put(msg)

    def get(self, timeout: float = 0.01) -> Optional[Any]:
        """Get a message from the queue (non-blocking)."""
        try:
            return self.queue.get(timeout=timeout)
        except Empty:
            return None

    def set_done(self) -> None:
        """Mark stream as done."""
        self.done = True

    async def async_get(self) -> Optional[Any]:
        """Asynchronously get a message from the queue."""
        while True:
            if not self.queue.empty():
                return self.queue.get()
            elif self.done:
                return None
            await asyncio.sleep(0.01)  # Avoid busy wait


class ClaudeControllerProtocol(ABC):
    """Abstract protocol for ClaudeController operations."""

    @abstractmethod
    def start(self) -> None:
        """Start the controller."""
        pass

    @abstractmethod
    def send(self, prompt: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Send a message to the controller."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the controller."""
        pass


class ClaudeControllerProcess:
    """Manages a claude-node subprocess as a ClaudeController."""

    def __init__(self, session_id: str, claude_node_path: str = CLAUDE_NODE_PATH):
        self.session_id = session_id
        # claude_node_path kept for reference but not used directly
        # ClaudeController manages the subprocess lifecycle internally
        self._alive = False
        # Per-request streaming queues (task 5.2.2)
        self._stream_queues: Dict[str, StreamQueue] = {}
        # Create the real ClaudeController instance
        # Note: session_id is assigned by claude CLI after start()
        # We store it for reference but don't use resume (avoids session-not-found errors)
        self.controller = ClaudeController(
            skip_permissions=True,
        )

    def start(self) -> None:
        """Start the claude-node subprocess."""
        if self._alive:
            return

        # Use the real ClaudeController.start() with wait_init_timeout=10s
        # This spawns the 'claude' CLI subprocess internally
        started = self.controller.start(wait_init_timeout=10.0)
        if started:
            self._alive = True
        # If not started, controller.alive will be False and send() will fail

    def send(self, prompt: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Send prompt to claude-node and wait for result."""
        if not self._alive:
            raise RuntimeError("Controller not started")

        try:
            # Call the real claude_node controller send method
            # The controller uses stream-json protocol
            result = self.controller.send(prompt, timeout=120)

            if result is None:
                # Timeout
                return {
                    "error": {
                        "type": "timeout",
                        "message": "Request timeout after 120s"
                    }
                }

            if result.is_result_error:
                return {
                    "error": {
                        "type": "internal_error",
                        "message": result.result_text
                    }
                }

            return {
                "text": result.result_text,
                "session_id": result.session_id or self.session_id,
                "prompt_tokens": 0,  # claude_node doesn't provide token counts
                "completion_tokens": 0,
                "total_tokens": 0
            }
        except Exception as e:
            return {
                "error": {
                    "type": "internal_error",
                    "message": str(e)
                }
            }

    def send_async(self, prompt: str, stream_id: str, on_message_callback=None) -> None:
        """Send prompt without waiting for result (async mode).

        Sets up per-request streaming queue to avoid race conditions between
        concurrent requests (task 5.2.2).
        """
        if not self._alive:
            raise RuntimeError("Controller not started")

        # Create per-request queue for this stream
        sq = StreamQueue()
        self._stream_queues[stream_id] = sq

        # Set callback to put messages into per-request queue
        def queue_callback(msg):
            sq.put(msg)

        self.controller.on_message = queue_callback
        self.controller.send_nowait(prompt)

    async def stream_generator(self, stream_id: str, timeout: float = 120.0):
        """Async generator that yields SSE chunks for a stream.

        Args:
            stream_id: Unique identifier for this streaming request
            timeout: Maximum time to wait for messages

        Yields:
            SSE-formatted chunks (task 5.2.3)
        """
        sq = self._stream_queues.get(stream_id)
        if not sq:
            return

        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                yield self._make_chunk(stream_id, "", finish_reason="timeout")
                break

            msg = await sq.async_get()
            if msg is None:  # Stream done
                break

            # Extract content from message
            content = ""
            if hasattr(msg, 'content'):
                content = msg.content
            elif isinstance(msg, dict):
                content = msg.get('content', '')
            elif isinstance(msg, str):
                content = msg

            yield self._make_chunk(stream_id, content)

        # Clean up queue after stream completes
        if stream_id in self._stream_queues:
            del self._stream_queues[stream_id]

    def _make_chunk(self, stream_id: str, content: str,
                    finish_reason: Optional[str] = None) -> str:
        """Create OpenAI-compatible SSE chunk (task 5.2.1).

        Args:
            stream_id: Stream identifier
            content: Delta content for this chunk
            finish_reason: If set, marks chunk as final

        Returns:
            SSE-formatted string
        """
        chunk_data = {
            'id': f'chatcmpl-{stream_id[:8]}',
            'object': 'chat.completion.chunk',
            'created': int(time.time()),
            'model': 'claude-sonnet-4-6',
            'choices': [{
                'index': 0,
                'delta': {'content': content} if content else {},
                'finish_reason': finish_reason
            }]
        }
        return f"data: {json.dumps(chunk_data)}\n\n"

    def wait_for_result_async(self, timeout: float = 120.0) -> Optional[Dict[str, Any]]:
        """Wait for result after send_async."""
        try:
            result = self.controller.wait_for_result(timeout=timeout)
            if result is None:
                return {
                    "error": {
                        "type": "timeout",
                        "message": f"Request timeout after {timeout}s"
                    }
                }
            return {
                "text": result.result_text,
                "session_id": result.session_id or self.session_id,
                "type": result.type,
                "subtype": result.subtype
            }
        except Exception as e:
            return {
                "error": {
                    "type": "internal_error",
                    "message": str(e)
                }
            }

    def stop(self) -> None:
        """Stop the claude-node subprocess gracefully."""
        self._alive = False
        try:
            self.controller.stop(timeout=5.0)
        except Exception:
            pass  # Already dead or error during stop

    def is_alive(self) -> bool:
        """Check if subprocess is alive."""
        return self.controller.alive if hasattr(self.controller, 'alive') else self._alive


class AdapterProcessManager:
    """Manages multiple ClaudeControllerProcess instances with lifecycle handling."""

    def __init__(self):
        self._controllers: Dict[str, ClaudeControllerProcess] = {}
        self._lock_controller_ops = {}  # Per-session locks to prevent concurrent sends
        self._global_lock = threading.Lock()
        # Zombie subprocess cleanup thread (task 3.2.5)
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()

    def get_controller(self, session_id: str) -> ClaudeControllerProcess:
        """Get or create controller for session."""
        with self._global_lock:
            if session_id not in self._controllers:
                self._controllers[session_id] = ClaudeControllerProcess(session_id)
            return self._controllers[session_id]

    def send_message(self, prompt: str, session_id: str) -> Dict[str, Any]:
        """Send message to claude-node for given session."""
        controller = self.get_controller(session_id)

        if not controller.is_alive():
            controller.start()

            # Check if start actually succeeded
            if not controller.is_alive():
                return {
                    "error": {
                        "type": "internal_error",
                        "message": "Failed to start controller"
                    }
                }

        return controller.send(prompt, session_id)

    def send_message_stream(self, prompt: str, session_id: str, stream_id: str) -> None:
        """Send message in streaming mode (non-blocking).

        Args:
            prompt: The prompt to send
            session_id: Session identifier
            stream_id: Unique stream identifier for this request
        """
        controller = self.get_controller(session_id)

        if not controller.is_alive():
            controller.start()

        controller.send_async(prompt, stream_id)

    async def stream_generator(self, stream_id: str, timeout: float = 120.0):
        """Async generator that yields SSE chunks for a stream.

        Args:
            stream_id: Unique stream identifier
            timeout: Maximum time to wait for messages

        Yields:
            SSE-formatted chunks
        """
        # Find the controller that has this stream_id
        for controller in self._controllers.values():
            if stream_id in controller._stream_queues:
                async for chunk in controller.stream_generator(stream_id, timeout):
                    yield chunk
                return

    def destroy_session(self, session_id: str) -> None:
        """Destroy controller for session."""
        with self._global_lock:
            if session_id in self._controllers:
                controller = self._controllers.pop(session_id)
                controller.stop()

    def cleanup_orphaned_processes(self, claude_node_path: str = CLAUDE_NODE_PATH) -> int:
        """Clean up orphaned claude-node processes from previous runs."""
        cleaned = 0
        try:
            # Find processes running claude_node
            result = subprocess.run(
                ["pgrep", "-f", "claude_node"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                pids = [int(p) for p in result.stdout.strip().split('\n') if p]
                for pid in pids:
                    try:
                        os.kill(pid, signal.SIGTERM)
                        cleaned += 1
                    except ProcessLookupError:
                        pass
        except Exception:
            pass
        return cleaned

    def start_cleanup_thread(self) -> None:
        """Start background thread for zombie subprocess cleanup (task 3.2.5)."""
        if self._cleanup_thread is not None:
            return
        self._stop_cleanup.clear()
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def stop_cleanup_thread(self) -> None:
        """Stop background cleanup thread."""
        if self._cleanup_thread is None:
            return
        self._stop_cleanup.set()
        self._cleanup_thread.join(timeout=5)
        self._cleanup_thread = None

    def _cleanup_loop(self) -> None:
        """Background cleanup loop for zombie subprocesses."""
        while not self._stop_cleanup.is_set():
            time.sleep(60)  # Check every minute
            self.cleanup_orphaned_processes()


# Global process manager instance
_process_manager: Optional[AdapterProcessManager] = None


def get_process_manager() -> AdapterProcessManager:
    """Get global process manager instance."""
    global _process_manager
    if _process_manager is None:
        _process_manager = AdapterProcessManager()
        _process_manager.start_cleanup_thread()
    return _process_manager


def shutdown_all() -> None:
    """Shutdown all controllers (call on SIGTERM)."""
    global _process_manager
    if _process_manager is not None:
        _process_manager.stop_cleanup_thread()
        for session_id in list(_process_manager._controllers.keys()):
            _process_manager.destroy_session(session_id)
        _process_manager = None
