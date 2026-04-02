"""Tests for async-stream module (Module 5)."""
import asyncio
import json
import pytest
import time
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, 'openclaw-claude-bridge')


class TestStreamQueue:
    """Tests 5.1.2: per-request StreamQueue."""

    def test_put_and_get(self):
        """Test basic put/get operations."""
        from claude_node_adapter.adapter import StreamQueue
        sq = StreamQueue()
        sq.put("test message")
        assert not sq.queue.empty()
        assert sq.get() == "test message"

    def test_set_done(self):
        """Test set_done flag."""
        from claude_node_adapter.adapter import StreamQueue
        sq = StreamQueue()
        assert sq.done is False
        sq.set_done()
        assert sq.done is True

    @pytest.mark.asyncio
    async def test_async_get_returns_message(self):
        """Test async_get returns queued message."""
        from claude_node_adapter.adapter import StreamQueue
        sq = StreamQueue()
        sq.put("async message")

        result = await sq.async_get()
        assert result == "async message"

    @pytest.mark.asyncio
    async def test_async_get_returns_none_when_done(self):
        """Test async_get returns None when done."""
        from claude_node_adapter.adapter import StreamQueue
        sq = StreamQueue()
        sq.set_done()

        result = await sq.async_get()
        assert result is None

    @pytest.mark.asyncio
    async def test_async_get_waits_for_message(self):
        """Test async_get waits when queue is empty."""
        from claude_node_adapter.adapter import StreamQueue
        sq = StreamQueue()

        # Put message after a short delay
        async def delayed_put():
            await asyncio.sleep(0.02)
            sq.put("delayed message")

        # Start the putter
        put_task = asyncio.create_task(delayed_put())

        # Get should wait for the message
        start = time.time()
        result = await sq.async_get()
        elapsed = time.time() - start

        assert result == "delayed message"
        assert elapsed >= 0.02  # Should have waited

        await put_task

    def test_per_request_isolation(self):
        """Test 5.1.5: concurrent requests are isolated via per-request queues."""
        from claude_node_adapter.adapter import StreamQueue
        sq1 = StreamQueue()
        sq2 = StreamQueue()

        sq1.put("message for queue 1")
        sq2.put("message for queue 2")

        # Each queue only has its own messages
        assert sq1.get() == "message for queue 1"
        assert sq2.get() == "message for queue 2"


class TestSSEFormatting:
    """Tests 5.1.1: SSE stream response format (OpenAI compatible)."""

    def test_make_chunk_format(self):
        """Test _make_chunk produces OpenAI-compatible SSE format."""
        with patch('claude_node_adapter.adapter.ClaudeController') as mock_controller_class:
            from claude_node_adapter.adapter import ClaudeControllerProcess
            mock_controller = MagicMock()
            mock_controller.alive = True
            mock_controller.start.return_value = True
            mock_controller_class.return_value = mock_controller

            controller = ClaudeControllerProcess("test-session")
            controller.start()

            chunk = controller._make_chunk("abc12345", "Hello")

            # Parse the SSE format
            assert chunk.startswith("data: ")
            data = json.loads(chunk[6:])  # Remove "data: " prefix

            assert data["id"] == "chatcmpl-abc12345"
            assert data["object"] == "chat.completion.chunk"
            assert "created" in data
            assert data["model"] == "claude-sonnet-4-6"
            assert data["choices"][0]["index"] == 0
            assert data["choices"][0]["delta"]["content"] == "Hello"
            assert data["choices"][0]["finish_reason"] is None

    def test_make_chunk_with_finish_reason(self):
        """Test _make_chunk with finish_reason."""
        with patch('claude_node_adapter.adapter.ClaudeController') as mock_controller_class:
            from claude_node_adapter.adapter import ClaudeControllerProcess
            mock_controller = MagicMock()
            mock_controller.alive = True
            mock_controller.start.return_value = True
            mock_controller_class.return_value = mock_controller

            controller = ClaudeControllerProcess("test-session")
            controller.start()

            chunk = controller._make_chunk("abc12345", "", finish_reason="stop")
            data = json.loads(chunk[6:])

            assert data["choices"][0]["delta"] == {}
            assert data["choices"][0]["finish_reason"] == "stop"


class TestStreamingSwitch:
    """Tests 5.1.3: stream=true/false switch."""

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_send_async_sets_up_stream_queue(self, mock_controller_class):
        """Test send_async creates per-request stream queue."""
        from claude_node_adapter.adapter import ClaudeControllerProcess, StreamQueue
        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True
        mock_controller_class.return_value = mock_controller

        controller = ClaudeControllerProcess("test-session")
        controller.start()

        controller.send_async("test prompt", "stream-123")

        # Should have created a stream queue for this stream_id
        assert "stream-123" in controller._stream_queues
        sq = controller._stream_queues["stream-123"]
        assert isinstance(sq, StreamQueue)

        # Controller's on_message should be set to queue callback
        mock_controller.send_nowait.assert_called_once_with("test prompt")

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_stream_generator_yields_chunks(self, mock_controller_class):
        """Test stream_generator yields SSE chunks from queue."""
        from claude_node_adapter.adapter import ClaudeControllerProcess, StreamQueue
        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True
        mock_controller_class.return_value = mock_controller

        controller = ClaudeControllerProcess("test-session")
        controller.start()

        # Manually set up a stream queue with messages
        sq = StreamQueue()
        controller._stream_queues["stream-123"] = sq

        # Put a message in the queue
        mock_msg = MagicMock()
        mock_msg.content = "Hello"
        sq.put(mock_msg)
        sq.set_done()

        # Run async generator
        async def test_generator():
            chunks = []
            async for chunk in controller.stream_generator("stream-123", timeout=5.0):
                chunks.append(chunk)
            return chunks

        chunks = asyncio.run(test_generator())

        assert len(chunks) >= 1
        # First chunk should contain "Hello"
        assert any("Hello" in str(chunk) for chunk in chunks)


class TestStreamInterruption:
    """Tests 5.1.4: stream interruption handling."""

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_stream_generator_timeout(self, mock_controller_class):
        """Test stream_generator handles timeout."""
        from claude_node_adapter.adapter import ClaudeControllerProcess
        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True
        mock_controller_class.return_value = mock_controller

        controller = ClaudeControllerProcess("test-session")
        controller.start()

        # No queue set up - should return immediately
        async def test_generator():
            chunks = []
            async for chunk in controller.stream_generator("nonexistent", timeout=0.1):
                chunks.append(chunk)
            return chunks

        chunks = asyncio.run(test_generator())
        # No chunks since queue doesn't exist
        assert len(chunks) == 0

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_stream_queue_cleanup_after_done(self, mock_controller_class):
        """Test stream queue is cleaned up after stream completes."""
        from claude_node_adapter.adapter import ClaudeControllerProcess
        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True
        mock_controller_class.return_value = mock_controller

        controller = ClaudeControllerProcess("test-session")
        controller.start()

        controller.send_async("test prompt", "stream-123")
        assert "stream-123" in controller._stream_queues

        # Simulate completion by setting done and getting all messages
        sq = controller._stream_queues["stream-123"]
        sq.set_done()

        # Generator should consume and cleanup
        async def test_generator():
            async for _ in controller.stream_generator("stream-123", timeout=5.0):
                pass

        asyncio.run(test_generator())


class TestAdapterProcessManagerStreaming:
    """Tests for AdapterProcessManager streaming support."""

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_send_message_stream(self, mock_controller_class):
        """Test send_message_stream sets up async streaming."""
        from claude_node_adapter.adapter import ClaudeControllerProcess, AdapterProcessManager
        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True
        mock_controller_class.return_value = mock_controller

        manager = AdapterProcessManager()
        controller = manager.get_controller("session-1")

        # Ensure controller is started (normally done by send_message_stream via is_alive check)
        controller.start()

        # This should set up the stream queue
        manager.send_message_stream("test prompt", "session-1", "stream-abc")

        # Verify send_nowait was called
        mock_controller.send_nowait.assert_called_once_with("test prompt")

    @patch('claude_node_adapter.adapter.ClaudeController')
    def test_get_or_create_stream_queue(self, mock_controller_class):
        """Test manager creates separate queues per stream_id."""
        from claude_node_adapter.adapter import ClaudeControllerProcess, AdapterProcessManager
        mock_controller = MagicMock()
        mock_controller.alive = True
        mock_controller.start.return_value = True
        mock_controller_class.return_value = mock_controller

        manager = AdapterProcessManager()
        controller = manager.get_controller("session-1")

        # Ensure controller is started
        controller.start()

        # Set up two streams
        manager.send_message_stream("prompt 1", "session-1", "stream-1")
        manager.send_message_stream("prompt 2", "session-1", "stream-2")

        # Each should have its own queue
        assert "stream-1" in controller._stream_queues
        assert "stream-2" in controller._stream_queues
        assert controller._stream_queues["stream-1"] is not controller._stream_queues["stream-2"]
