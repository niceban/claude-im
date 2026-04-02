# Learnings (Module Division Review)

## 2026-04-02

### Session Errors Belong in Domain Layer

**Pattern**: Error types that reference domain concepts (sessions, conflicts) should be defined in the module that owns those concepts, not in a presentation-layer module.

**Wrong**: `openai_compatible_api/errors.py` defining `ERROR_NOT_FOUND` (session not found)

**Right**: `session_mapping/errors.py` defining session-related errors, then re-exporting in `openai_compatible_api/errors.py` for backward compatibility

### Two-Level Abstraction for Lifecycle Management

**Pattern**: This codebase uses two parallel abstractions for lifecycle management:
1. `SessionBackend` (ABC) - logical session lifecycle (create/destroy/is_alive)
2. `ClaudeControllerProtocol` (ABC) - physical process lifecycle (start/send/stop)

**Insight**: These serve different levels of abstraction and should NOT be merged. `SessionBackend` is for session state management (can be in-memory, Redis, etc.), while `ClaudeControllerProtocol` is for subprocess management.

### Dependency Direction in Layered Architecture

**Pattern**: Configuration modules should be leaf nodes (no outbound dependencies). Other modules depend on config, but config depends on nothing.

**Verified**: `config/` module has zero outbound dependencies - correct.

### Adapter Integration as Red Phase

**Pattern**: TDD placeholder in integration point (`"(placeholder - adapter not yet connected)"`) indicates adapter not integrated. This is acceptable as a red-phase marker but should be addressed before MVP.
