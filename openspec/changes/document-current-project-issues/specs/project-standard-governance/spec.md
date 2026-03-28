## ADDED Requirements

### Requirement: Project SHALL define a single authoritative standard
The project SHALL maintain one explicit source of truth for architecture, backend entry points, and feature status. All user-facing and contributor-facing documentation SHALL align with that standard, and conflicting parallel narratives SHALL be removed rather than kept as alternatives.

#### Scenario: Canonical standard is present
- **WHEN** a contributor inspects the standards repository
- **THEN** they SHALL find a single canonical document that defines the active architecture and documentation hierarchy

#### Scenario: Conflicting narratives are discovered
- **WHEN** a document, note, or hidden artifact conflicts with the canonical standard
- **THEN** that conflicting material SHALL be removed, rewritten, or explicitly subordinated to the canonical standard

### Requirement: Admin product SHALL expose a single user-facing entry point
The admin/reporting product SHALL expose exactly one user-facing local entry point for operators and maintainers. For the current baseline, that entry point SHALL be `http://localhost:5173`, and backend API addresses SHALL not be documented as parallel operator entry points.

#### Scenario: User looks for the admin entry
- **WHEN** a user reads project documentation for how to access the admin system
- **THEN** the documentation SHALL identify `http://localhost:5173` as the sole user-facing admin entry

#### Scenario: Internal backend address is referenced
- **WHEN** the backend API address `http://localhost:8000` appears in development or architecture material
- **THEN** it SHALL be described as an internal API service rather than as a parallel admin entry

### Requirement: Runtime path SHALL remain singular
The active execution path for IM-originated requests SHALL be `clawrelay-feishu-server -> claude-node -> Claude Code CLI`. Deprecated runtime paths, including `clawrelay-api` as an active execution dependency, SHALL not remain in active documentation or exposed execution surfaces.

#### Scenario: Runtime path is documented
- **WHEN** architecture or implementation guidance describes how IM requests are executed
- **THEN** it SHALL describe direct `claude-node` integration and SHALL not describe `clawrelay-api` as part of the active path

#### Scenario: Deprecated runtime artifact exists
- **WHEN** a route, design note, or helper surface exposes the deprecated runtime path
- **THEN** that artifact SHALL be removed or rewritten to match the singular runtime path

### Requirement: Unverified capabilities SHALL not be represented as implemented
Capabilities that have not been explicitly verified SHALL be documented as unverified. The project SHALL not present such capabilities as available simply because code, experiments, or draft notes exist.

#### Scenario: SSE has not been verified
- **WHEN** project documentation refers to SSE or chat-stream behavior without a completed verification step
- **THEN** that documentation SHALL state that SSE is unverified and SHALL not claim it is part of the baseline

#### Scenario: Experimental implementation exists
- **WHEN** experimental code or draft routes exist for an unverified capability
- **THEN** the project SHALL either remove those surfaces from the active path or clearly exclude them from the baseline
