import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES = {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}


@dataclass
class Task:
    id: str
    title: str
    description: str
    state: TaskState
    priority: int
    parent_id: str | None
    depends_on: list[str]
    retry_count: int
    max_retries: int
    blocker_reason: str | None
    decision_log: list[dict[str, Any]]
    created_at: str
    updated_at: str
    completed_at: str | None

    @staticmethod
    def from_row(row) -> "Task":
        depends = json.loads(row["depends_on"]) if row["depends_on"] else []
        return Task(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            state=TaskState(row["state"]),
            priority=row["priority"],
            parent_id=row["parent_id"],
            depends_on=depends,
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            blocker_reason=row["blocker_reason"],
            decision_log=json.loads(row["decision_log"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
        )


def new_task(
    *,
    title: str,
    description: str = "",
    priority: int = 0,
    parent_id: str | None = None,
    depends_on: list[str] | None = None,
    max_retries: int = 3,
) -> Task:
    now = utc_now()
    return Task(
        id=str(uuid.uuid4()),
        title=title,
        description=description,
        state=TaskState.PENDING,
        priority=priority,
        parent_id=parent_id,
        depends_on=depends_on or [],
        retry_count=0,
        max_retries=max_retries,
        blocker_reason=None,
        decision_log=[],
        created_at=now,
        updated_at=now,
        completed_at=None,
    )
