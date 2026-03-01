"""Tests for task lifecycle state machine."""
from __future__ import annotations

import pytest

from aeolus.tasks.lifecycle import TaskRecord, TaskState


class TestTaskRecord:
    def test_initial_state(self) -> None:
        r = TaskRecord(task_id="t1", description="test task", requester_id="r1")
        assert r.state == TaskState.SUBMITTED
        assert not r.is_terminal

    def test_valid_transition_chain(self) -> None:
        r = TaskRecord(task_id="t1", description="test task", requester_id="r1")
        r.transition(TaskState.NEGOTIATING)
        assert r.state == TaskState.NEGOTIATING
        r.transition(TaskState.ACCEPTED)
        assert r.state == TaskState.ACCEPTED
        r.transition(TaskState.EXECUTING)
        assert r.state == TaskState.EXECUTING
        r.transition(TaskState.COMPLETED)
        assert r.state == TaskState.COMPLETED
        assert r.is_terminal

    def test_invalid_transition_raises(self) -> None:
        r = TaskRecord(task_id="t1", description="test task", requester_id="r1")
        r.transition(TaskState.NEGOTIATING)
        r.transition(TaskState.ACCEPTED)
        r.transition(TaskState.EXECUTING)
        r.transition(TaskState.COMPLETED)
        with pytest.raises(ValueError, match="Invalid transition"):
            r.transition(TaskState.NEGOTIATING)

    def test_cancel_from_submitted(self) -> None:
        r = TaskRecord(task_id="t1", description="test task", requester_id="r1")
        r.transition(TaskState.CANCELLED)
        assert r.state == TaskState.CANCELLED
        assert r.is_terminal

    def test_cancel_from_negotiating(self) -> None:
        r = TaskRecord(task_id="t1", description="test task", requester_id="r1")
        r.transition(TaskState.NEGOTIATING)
        r.transition(TaskState.CANCELLED)
        assert r.state == TaskState.CANCELLED

    def test_cancel_from_accepted(self) -> None:
        r = TaskRecord(task_id="t1", description="test task", requester_id="r1")
        r.transition(TaskState.NEGOTIATING)
        r.transition(TaskState.ACCEPTED)
        r.transition(TaskState.CANCELLED)
        assert r.state == TaskState.CANCELLED

    def test_fail_from_negotiating(self) -> None:
        r = TaskRecord(task_id="t1", description="test task", requester_id="r1")
        r.transition(TaskState.NEGOTIATING)
        r.transition(TaskState.FAILED)
        assert r.state == TaskState.FAILED
        assert r.is_terminal

    def test_fail_from_executing(self) -> None:
        r = TaskRecord(task_id="t1", description="test task", requester_id="r1")
        r.transition(TaskState.NEGOTIATING)
        r.transition(TaskState.ACCEPTED)
        r.transition(TaskState.EXECUTING)
        r.transition(TaskState.FAILED)
        assert r.state == TaskState.FAILED

    def test_cannot_skip_states(self) -> None:
        r = TaskRecord(task_id="t1", description="test task", requester_id="r1")
        with pytest.raises(ValueError, match="Invalid transition"):
            r.transition(TaskState.EXECUTING)

    def test_transition_returns_self(self) -> None:
        r = TaskRecord(task_id="t1", description="test task", requester_id="r1")
        result = r.transition(TaskState.NEGOTIATING)
        assert result is r

    def test_updated_at_changes_on_transition(self) -> None:
        r = TaskRecord(task_id="t1", description="test task", requester_id="r1")
        original = r.updated_at
        r.transition(TaskState.NEGOTIATING)
        assert r.updated_at >= original

    def test_optional_fields_default_none(self) -> None:
        r = TaskRecord(task_id="t1", description="test task", requester_id="r1")
        assert r.executor_id is None
        assert r.result is None
        assert r.error is None

    def test_fields_assignable(self) -> None:
        r = TaskRecord(task_id="t1", description="test task", requester_id="r1")
        r.executor_id = "exec-1"
        r.result = "done"
        r.error = "oops"
        assert r.executor_id == "exec-1"
        assert r.result == "done"
        assert r.error == "oops"

    def test_terminal_states(self) -> None:
        for terminal in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
            r = TaskRecord(
                task_id="t1",
                description="test",
                requester_id="r1",
                state=terminal,
            )
            assert r.is_terminal

    def test_non_terminal_states(self) -> None:
        for state in (TaskState.SUBMITTED, TaskState.NEGOTIATING, TaskState.ACCEPTED, TaskState.EXECUTING):
            r = TaskRecord(
                task_id="t1",
                description="test",
                requester_id="r1",
                state=state,
            )
            assert not r.is_terminal

    def test_cannot_transition_from_terminal(self) -> None:
        for terminal in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
            r = TaskRecord(
                task_id="t1",
                description="test",
                requester_id="r1",
                state=terminal,
            )
            with pytest.raises(ValueError, match="Invalid transition"):
                r.transition(TaskState.SUBMITTED)
