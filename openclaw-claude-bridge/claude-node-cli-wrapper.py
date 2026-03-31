#!/usr/bin/env python3
"""
Claude Node CLI Wrapper — OpenClaw CLI Backend

This wrapper integrates with claude-node Python package to provide
a CLI Backend for OpenClaw. It communicates via stdin/stdout JSON.

Protocol:
- Input (stdin): {"messages": [...], "conversation_id": "..."}
- Input (CLI arg): raw text prompt (when input: "arg")
- Output (stdout): {"text": "...", "conversation_id": "...", "error": null}

Signal Handling:
- SIGTERM/SIGINT: Gracefully stop Claude CLI and exit
"""

import sys
import json
import os
import signal
from typing import Optional

# Ensure claude_node can be imported
CLAUDE_NODE_PATH = '/private/tmp/claude-node'
if CLAUDE_NODE_PATH not in sys.path:
    sys.path.insert(0, CLAUDE_NODE_PATH)

from claude_node.controller import ClaudeController
from claude_node.exceptions import ClaudeBinaryNotFoundError

# Global state
_controller = None
_shutdown_requested = False

ERROR_CODES = {
    "INTERNAL_ERROR": 1,
    "JSON_PARSE_ERROR": 2,
    "INVALID_REQUEST": 3,
    "CLAUDE_BINARY_NOT_FOUND": 4,
    "PROCESS_START_FAILED": 5,
    "NO_RESPONSE": 6,
}


def _signal_handler(signum, frame):
    global _controller, _shutdown_requested
    _shutdown_requested = True
    if _controller is not None and _controller.alive:
        _controller.stop()


# Register signal handlers
signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


def _make_response(text: str, conversation_id: str, error: Optional[str]) -> dict:
    """Create a standardized response dict."""
    return {
        "text": text,
        "conversation_id": conversation_id,
        "error": error
    }


def _make_error_response(conversation_id: str, error: str, error_code: int) -> dict:
    """Create a standardized error response dict."""
    return {
        "text": "",
        "conversation_id": conversation_id,
        "error": error,
        "error_code": error_code
    }


def main():
    global _controller, _shutdown_requested

    sys.stderr.write("WRAPPER START\n")
    sys.stderr.flush()

    # Read input: from CLI arg (input: "arg" mode) or stdin (input: "stdin" mode)
    conversation_id = ""
    user_text = ""
    try:
        # Check if prompt was passed as command-line argument (input: "arg" mode)
        if len(sys.argv) > 1:
            user_text = sys.argv[1].strip()
            conversation_id = ""
        else:
            # Fall back to stdin (input: "stdin" mode)
            line = sys.stdin.readline()
            if not line:
                return
            line = line.strip()
            try:
                request = json.loads(line)
                conversation_id = request.get("conversation_id", "")
                messages = request.get("messages", [])
                for msg in messages:
                    if msg.get("role") == "user":
                        content = msg.get("content", [])
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    user_text += block.get("text", "") + "\n"
                        elif isinstance(content, str):
                            user_text = content
                user_text = user_text.strip()
            except json.JSONDecodeError:
                user_text = line
    except Exception as e:
        response = _make_error_response(
            conversation_id,
            f"Input parse error: {e}",
            ERROR_CODES["JSON_PARSE_ERROR"]
        )
        print(json.dumps(response, ensure_ascii=False), flush=True)
        return

    if not user_text:
        response = _make_error_response(
            conversation_id,
            "No user message found in request",
            ERROR_CODES["INVALID_REQUEST"]
        )
        print(json.dumps(response, ensure_ascii=False), flush=True)
        return

    if _shutdown_requested:
        return

    # Call claude-node via ClaudeController
    controller = None
    try:
        controller = ClaudeController(
            skip_permissions=True,
            cwd=os.environ.get('CLAUDE_CWD', None)
        )
        _controller = controller

        # Check claude binary availability
        try:
            from claude_node.runtime import check_claude_available
            check_claude_available()
        except ClaudeBinaryNotFoundError:
            response = _make_error_response(
                conversation_id,
                "Claude CLI binary not found",
                ERROR_CODES["CLAUDE_BINARY_NOT_FOUND"]
            )
            print(json.dumps(response, ensure_ascii=False), flush=True)
            return

        controller.start(wait_init_timeout=10.0)
        sys.stderr.write(f"CONTROLLER STARTED alive={controller.alive}\n")
        sys.stderr.flush()

        if not controller.alive:
            response = _make_error_response(
                conversation_id,
                "Failed to start Claude CLI process",
                ERROR_CODES["PROCESS_START_FAILED"]
            )
            print(json.dumps(response, ensure_ascii=False), flush=True)
            return

        # Send with timeout
        sys.stderr.write(f"CALLING SEND user_text_len={len(user_text)}\n")
        sys.stderr.flush()
        result = controller.send(user_text, timeout=300.0)
        sys.stderr.write(f"SEND RETURNED result={result.type if result else None}\n")
        sys.stderr.flush()
        controller.stop()
        _controller = None

        if _shutdown_requested:
            return

        if result and result.truly_succeeded:
            response = _make_response(
                result.result_text,
                conversation_id,
                None
            )
        else:
            error_msg = result.result_text if result else "No response"
            response = _make_error_response(
                conversation_id,
                error_msg,
                ERROR_CODES["NO_RESPONSE"]
            )

        print(json.dumps(response, ensure_ascii=False), flush=True)
        sys.exit(0)

    except KeyboardInterrupt:
        if controller is not None:
            controller.stop()
            _controller = None
        sys.exit(0)

    except Exception as e:
        if controller is not None and controller.alive:
            controller.stop()
            _controller = None
        import traceback
        response = _make_error_response(
            conversation_id,
            f"Internal error: {str(e)}\n{traceback.format_exc()}",
            ERROR_CODES["INTERNAL_ERROR"]
        )
        print(json.dumps(response, ensure_ascii=False), flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
