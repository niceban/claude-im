# Issues (Module Division Review)

## 2026-04-02

### HIGH: Adapter Not Integrated

**Severity**: HIGH
**Module**: `openai_compatible_api/server.py`
**Location**: lines 95-118

**Issue**: The `chat_completions()` handler returns a hardcoded placeholder response instead of calling the `claude_node_adapter`.

**Impact**: Bridge cannot forward requests to claude-node. Core functionality missing.

**Status**: Known placeholder (comment indicates TDD red phase)

**Fix**: Once `ClaudeControllerProcess.send()` is implemented, connect:
```python
from claude_node_adapter.adapter import get_process_manager
process_manager = get_process_manager()
result = process_manager.send_message(prompt, session_id)
```

---

### MEDIUM: Session Errors in Wrong Layer

**Severity**: MEDIUM
**Module**: `openai_compatible_api/errors.py`
**Location**: lines 71-81

**Issue**: `ERROR_NOT_FOUND` ("Session not found") and `ERROR_CONFLICT` ("another request is in-flight") are defined in the API layer but reference session semantics.

**Impact**: If API transport changes (e.g., WebSocket), these errors become orphaned. Session errors should live in session domain.

**Fix**: Create `session_mapping/errors.py` with these errors, re-export from `openai_compatible_api/errors.py`.

---

### LOW: Documentation Gap - Two Abstractions

**Severity**: LOW
**Module**: `session_mapping/backend.py` + `claude_node_adapter/adapter.py`
**Location**: Two separate ABCs

**Issue**: `SessionBackend` and `ClaudeControllerProtocol` are both abstract interfaces but not obviously related. A reader might think they should be unified.

**Impact**: Maintenance confusion

**Fix**: Add module-level docstring explaining the two-level abstraction:
- Logical layer: Session lifecycle
- Physical layer: Process lifecycle
