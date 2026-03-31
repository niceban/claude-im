"""Unit tests for SessionMapper.

RED PHASE: These tests define expected behavior for session mapping.
All tests should FAIL initially until implementation is complete.
"""

import time
from pathlib import Path

import pytest

from clawrelay_bridge.session_mapper import SessionMapper, SessionMapping


class TestSessionMapperCreateMapping:
    """Tests for SessionMapper.create_mapping()."""

    def test_create_mapping_creates_entry_in_database(self, temp_db_path):
        """create_mapping should persist a new session mapping to the database."""
        mapper = SessionMapper(temp_db_path)

        result = mapper.create_mapping(
            openclaw_session_id="session-001",
            claude_session_id="claude-001",
            platform="feishu",
            user_id="user-123",
        )

        # Verify mapping was created and persisted
        retrieved = mapper.get_by_openclaw_session("session-001")
        assert retrieved is not None
        assert retrieved.openclaw_session_id == "session-001"
        assert retrieved.claude_session_id == "claude-001"
        assert retrieved.platform == "feishu"
        assert retrieved.user_id == "user-123"

    def test_create_mapping_returns_sessionMapping_with_correct_id(self, temp_db_path):
        """create_mapping should return a SessionMapping with the correct database ID."""
        mapper = SessionMapper(temp_db_path)

        result = mapper.create_mapping(
            openclaw_session_id="session-002",
            claude_session_id="claude-002",
        )

        assert result.id is not None
        assert result.id > 0
        assert isinstance(result.id, int)

    def test_create_mapping_sets_created_at_timestamp(self, temp_db_path):
        """create_mapping should set the created_at field to current ISO timestamp."""
        mapper = SessionMapper(temp_db_path)

        result = mapper.create_mapping(
            openclaw_session_id="session-003",
            claude_session_id="claude-003",
        )

        assert result.created_at is not None
        assert "T" in result.created_at  # ISO format contains 'T'
        assert ":" in result.created_at  # ISO format contains time

    def test_create_mapping_sets_last_active_to_current_time(self, temp_db_path):
        """create_mapping should set last_active to current Unix timestamp."""
        mapper = SessionMapper(temp_db_path)
        before_create = time.time()

        result = mapper.create_mapping(
            openclaw_session_id="session-004",
            claude_session_id="claude-004",
        )

        assert result.last_active >= before_create
        assert result.last_active <= time.time()

    def test_create_mapping_sets_status_to_active(self, temp_db_path):
        """create_mapping should set initial status to 'active'."""
        mapper = SessionMapper(temp_db_path)

        result = mapper.create_mapping(
            openclaw_session_id="session-005",
            claude_session_id="claude-005",
        )

        assert result.status == "active"

    def test_create_mapping_with_minimal_args(self, temp_db_path):
        """create_mapping should work with only required arguments."""
        mapper = SessionMapper(temp_db_path)

        result = mapper.create_mapping(
            openclaw_session_id="session-006",
            claude_session_id="claude-006",
        )

        assert result.openclaw_session_id == "session-006"
        assert result.claude_session_id == "claude-006"
        assert result.platform == ""
        assert result.user_id == ""


class TestSessionMapperGetByOpenClawSession:
    """Tests for SessionMapper.get_by_openclaw_session()."""

    def test_get_by_openclaw_session_returns_correct_mapping(self, temp_db_path):
        """get_by_openclaw_session should return the correct SessionMapping."""
        mapper = SessionMapper(temp_db_path)
        mapper.create_mapping(
            openclaw_session_id="session-101",
            claude_session_id="claude-101",
            platform="feishu",
            user_id="user-101",
        )

        result = mapper.get_by_openclaw_session("session-101")

        assert result is not None
        assert result.openclaw_session_id == "session-101"
        assert result.claude_session_id == "claude-101"
        assert result.platform == "feishu"
        assert result.user_id == "user-101"

    def test_get_by_openclaw_session_returns_none_for_nonexistent(self, temp_db_path):
        """get_by_openclaw_session should return None for non-existent session."""
        mapper = SessionMapper(temp_db_path)

        result = mapper.get_by_openclaw_session("nonexistent-session")

        assert result is None

    def test_get_by_openclaw_session_returns_none_after_archive(self, temp_db_path):
        """get_by_openclaw_session should still return the mapping even after archiving."""
        mapper = SessionMapper(temp_db_path)
        mapper.create_mapping(
            openclaw_session_id="session-102",
            claude_session_id="claude-102",
        )
        mapper.archive_session("session-102")

        result = mapper.get_by_openclaw_session("session-102")

        # Archive changes status, but record still exists
        assert result is not None
        assert result.status == "archived"


class TestSessionMapperUpdateLastActive:
    """Tests for SessionMapper.update_last_active()."""

    def test_update_last_active_updates_timestamp(self, temp_db_path):
        """update_last_active should update the last_active field to current time."""
        mapper = SessionMapper(temp_db_path)
        mapper.create_mapping(
            openclaw_session_id="session-201",
            claude_session_id="claude-201",
        )
        time.sleep(0.01)  # Small delay to ensure timestamp differs
        before_update = time.time()

        result = mapper.update_last_active("session-201")

        assert result is True
        updated_mapping = mapper.get_by_openclaw_session("session-201")
        assert updated_mapping.last_active >= before_update

    def test_update_last_active_returns_false_for_nonexistent(self, temp_db_path):
        """update_last_active should return False for non-existent session."""
        mapper = SessionMapper(temp_db_path)

        result = mapper.update_last_active("nonexistent-session")

        assert result is False

    def test_update_last_active_returns_true_on_success(self, temp_db_path):
        """update_last_active should return True when session exists."""
        mapper = SessionMapper(temp_db_path)
        mapper.create_mapping(
            openclaw_session_id="session-202",
            claude_session_id="claude-202",
        )

        result = mapper.update_last_active("session-202")

        assert result is True


class TestSessionMapperArchiveSession:
    """Tests for SessionMapper.archive_session()."""

    def test_archive_session_changes_status_to_archived(self, temp_db_path):
        """archive_session should change the status to 'archived'."""
        mapper = SessionMapper(temp_db_path)
        mapper.create_mapping(
            openclaw_session_id="session-301",
            claude_session_id="claude-301",
        )

        result = mapper.archive_session("session-301")

        assert result is True
        mapping = mapper.get_by_openclaw_session("session-301")
        assert mapping.status == "archived"

    def test_archive_session_returns_true_when_session_exists(self, temp_db_path):
        """archive_session should return True when session was archived."""
        mapper = SessionMapper(temp_db_path)
        mapper.create_mapping(
            openclaw_session_id="session-302",
            claude_session_id="claude-302",
        )

        result = mapper.archive_session("session-302")

        assert result is True

    def test_archive_session_returns_false_for_nonexistent(self, temp_db_path):
        """archive_session should return False for non-existent session."""
        mapper = SessionMapper(temp_db_path)

        result = mapper.archive_session("nonexistent-session")

        assert result is False


class TestSessionMapperListActiveMappings:
    """Tests for SessionMapper.list_active_mappings()."""

    def test_list_active_mappings_returns_only_active(self, temp_db_path):
        """list_active_mappings should only return sessions with status='active'."""
        mapper = SessionMapper(temp_db_path)
        mapper.create_mapping(
            openclaw_session_id="active-session",
            claude_session_id="claude-active",
        )
        mapper.create_mapping(
            openclaw_session_id="archived-session",
            claude_session_id="claude-archived",
        )
        mapper.archive_session("archived-session")

        active_mappings = mapper.list_active_mappings()

        assert len(active_mappings) == 1
        assert active_mappings[0].openclaw_session_id == "active-session"
        assert all(m.status == "active" for m in active_mappings)

    def test_list_active_mappings_returns_empty_when_all_archived(self, temp_db_path):
        """list_active_mappings should return empty list when all sessions are archived."""
        mapper = SessionMapper(temp_db_path)
        mapper.create_mapping(
            openclaw_session_id="session-401",
            claude_session_id="claude-401",
        )
        mapper.archive_session("session-401")

        active_mappings = mapper.list_active_mappings()

        assert len(active_mappings) == 0

    def test_list_active_mappings_ordered_by_last_active_desc(self, temp_db_path):
        """list_active_mappings should return mappings ordered by last_active descending."""
        mapper = SessionMapper(temp_db_path)
        mapper.create_mapping(
            openclaw_session_id="session-first",
            claude_session_id="claude-first",
        )
        # Update to make it more recent
        mapper.update_last_active("session-first")

        active_mappings = mapper.list_active_mappings()

        # Most recently active should be first
        assert active_mappings[0].openclaw_session_id == "session-first"


class TestSessionMapperDeleteMapping:
    """Tests for SessionMapper.delete_mapping()."""

    def test_delete_mapping_removes_entry(self, temp_db_path):
        """delete_mapping should remove the session mapping from database."""
        mapper = SessionMapper(temp_db_path)
        mapper.create_mapping(
            openclaw_session_id="session-501",
            claude_session_id="claude-501",
        )

        result = mapper.delete_mapping("session-501")

        assert result is True
        assert mapper.get_by_openclaw_session("session-501") is None

    def test_delete_mapping_returns_false_for_nonexistent(self, temp_db_path):
        """delete_mapping should return False for non-existent session."""
        mapper = SessionMapper(temp_db_path)

        result = mapper.delete_mapping("nonexistent-session")

        assert result is False
