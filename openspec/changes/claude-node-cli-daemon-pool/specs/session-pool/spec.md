## ADDED Requirements

### Requirement: Session Pool Size Limit
The pool SHALL hold at most 10 `ClaudeController` instances simultaneously.

### Requirement: LRU Eviction
When the pool is full and a new session is needed, the daemon SHALL stop the least-recently-used controller (oldest `last_used` timestamp) and remove it from the pool before adding a new one.

### Requirement: Session Key
Each pooled controller SHALL be indexed by `conversation_id`. The default session key `_default` SHALL be used when `conversation_id` is empty.

### Requirement: Session Lookup (Fast Path)
If a controller for the given `conversation_id` exists in the pool, it SHALL be returned immediately with updated `last_used` timestamp.

### Requirement: Session Creation (Slow Path)
If no controller exists for the given `conversation_id`, a new `ClaudeController` SHALL be created, started with `wait_init_timeout=0`, and registered in the pool.

### Requirement: Death Detection
Before returning a controller from the pool, the daemon SHALL check `ctrl.alive`. If the subprocess is dead, the controller SHALL be removed from the pool and a new one created.

### Requirement: Session Pool Thread Safety
Pool read/write operations SHALL be protected by a `threading.Lock` (`_pool_lock`). Each individual controller access SHALL be protected by its own `threading.RLock` (`_controller_locks[session_key]`).

#### Scenario: Pool is not full, new conversation_id
- **WHEN** request arrives with a `conversation_id` not in pool and pool size < 10
- **THEN** a new controller is created, started, and added to the pool

#### Scenario: Pool is full, new conversation_id triggers LRU eviction
- **WHEN** request arrives with a `conversation_id` not in pool and pool size == 10
- **THEN** the LRU controller (smallest `last_used`) is stopped and removed, then the new controller is added

#### Scenario: Existing conversation_id returns pooled controller
- **WHEN** request arrives with a `conversation_id` already in pool
- **THEN** the existing controller is returned with updated `last_used` timestamp

#### Scenario: Pooled controller is dead
- **WHEN** a controller in the pool has `ctrl.alive == False`
- **THEN** it is removed from the pool, a new controller is created and added in its place
