"""
aeolus/tasks/lifecycle.py
Task state machine.
"""
from __future__ import annotations

from enum import Enum
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class TaskState(str, Enum):
    SUBMITTED = "submitted"
    NEGOTIATING = "negotiating"
    ACCEPTED = "accepted"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskRecord(BaseModel):
    task_id: str
    description: str
    state: TaskState = TaskState.SUBMITTED
    requester_id: str
    executor_id: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Allowed transitions
    _transitions: dict[TaskState, list[TaskState]] = {
        TaskState.SUBMITTED:   [TaskState.NEGOTIATING, TaskState.CANCELLED],
        TaskState.NEGOTIATING: [TaskState.ACCEPTED, TaskState.CANCELLED, TaskState.FAILED],
        TaskState.ACCEPTED:    [TaskState.EXECUTING, TaskState.CANCELLED],
        TaskState.EXECUTING:   [TaskState.COMPLETED, TaskState.FAILED],
        TaskState.COMPLETED:   [],
        TaskState.FAILED:      [],
        TaskState.CANCELLED:   [],
    }

    def transition(self, new_state: TaskState) -> "TaskRecord":
        allowed = self._transitions.get(self.state, [])
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: {self.state} → {new_state}. "
                f"Allowed: {allowed}"
            )
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc)
        return self

    @property
    def is_terminal(self) -> bool:
        return self.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED)
