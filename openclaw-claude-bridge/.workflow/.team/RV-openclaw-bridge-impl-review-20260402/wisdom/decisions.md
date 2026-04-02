# Decisions (Module Division Review)

## 2026-04-02

### Decision 1: SessionBackend Abstraction - APPROVED

**Module**: `session_mapping/backend.py`

**Decision**: Keep `SessionBackend` as an abstract interface with `InMemorySessionBackend` as default and `MockSessionBackend` for testing.

**Rationale**:
- Dependency injection allows swapping backends (e.g., Redis for production)
- Mock backend enables isolated unit testing
- Interface is minimal and focused (3 methods only)

### Decision 2: Config as Leaf Module - CONFIRMED

**Module**: `config/`

**Decision**: Keep `config/` as a pure configuration module with no outbound dependencies.

**Rationale**: Configuration should be injectable but not depend on application logic. This makes the module reusable and testable.

### Decision 3: Error Location - REQUIRES FIX

**Module**: `openai_compatible_api/errors.py`

**Decision**: Move session-related errors (`ERROR_NOT_FOUND`, `ERROR_CONFLICT`) to `session_mapping/errors.py`.

**Rationale**: Errors referencing session semantics belong in the domain module that owns sessions, not in the API presentation layer.

### Decision 4: Parallel Protocol Abstractions - INTENTIONAL

**Modules**: `session_mapping/backend.py` vs `claude_node_adapter/adapter.py`

**Decision**: Keep two separate abstractions (`SessionBackend` vs `ClaudeControllerProtocol`) as they serve different purposes.

**Rationale**:
- `SessionBackend`: logical session lifecycle
- `ClaudeControllerProtocol`: physical subprocess lifecycle
- Merging would violate SRP
