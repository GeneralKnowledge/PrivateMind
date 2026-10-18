import json
import uuid
from typing import Any

from privatemind.db import Database
from privatemind.executive.tasks import TERMINAL_STATES, Task, TaskState, new_task, utc_now


class TaskManager:
    """Persistent executive: prioritised tasks with recovery after restart."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def create_task(
        self,
        title: str,
        description: str = "",
        *,
        priority: int = 0,
        parent_id: str | None = None,
        depends_on: list[str] | None = None,
        max_retries: int = 3,
    ) -> Task:
        task = new_task(
            title=title,
            description=description,
            priority=priority,
            parent_id=parent_id,
            depends_on=depends_on,
            max_retries=max_retries,
        )
        self._insert(task)
        return task

    def _insert(self, task: Task) -> None:
        with self._db.session() as conn:
            conn.execute(
                """
                INSERT INTO tasks (
                    id, title, description, state, priority, parent_id, depends_on,
                    retry_count, max_retries, blocker_reason, decision_log,
                    created_at, updated_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.title,
                    task.description,
                    task.state.value,
                    task.priority,
                    task.parent_id,
                    json.dumps(task.depends_on),
                    task.retry_count,
                    task.max_retries,
                    task.blocker_reason,
                    json.dumps(task.decision_log),
                    task.created_at,
                    task.updated_at,
                    task.completed_at,
                ),
            )

    def get_task(self, task_id: str) -> Task | None:
        with self._db.session() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return Task.from_row(row) if row else None

    def list_tasks(self, *, include_terminal: bool = True) -> list[Task]:
        with self._db.session() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY priority DESC, created_at ASC").fetchall()
        tasks = [Task.from_row(r) for r in rows]
        if include_terminal:
            return tasks
        return [t for t in tasks if t.state not in TERMINAL_STATES]

    def _save(self, task: Task) -> None:
        task.updated_at = utc_now()
        with self._db.session() as conn:
            conn.execute(
                """
                UPDATE tasks SET
                    title = ?, description = ?, state = ?, priority = ?,
                    parent_id = ?, depends_on = ?, retry_count = ?, max_retries = ?,
                    blocker_reason = ?, decision_log = ?, updated_at = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    task.title,
                    task.description,
                    task.state.value,
                    task.priority,
                    task.parent_id,
                    json.dumps(task.depends_on),
                    task.retry_count,
                    task.max_retries,
                    task.blocker_reason,
                    json.dumps(task.decision_log),
                    task.updated_at,
                    task.completed_at,
                    task.id,
                ),
            )

    def log_decision(self, task: Task, decision: str, **detail: Any) -> None:
        entry = {"at": utc_now(), "decision": decision, **detail}
        task.decision_log.append(entry)
        self._save(task)

    def record_attempt(self, task_id: str, outcome: str, detail: str = "") -> None:
        with self._db.session() as conn:
            conn.execute(
                """
                INSERT INTO task_attempts (id, task_id, outcome, detail, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), task_id, outcome, detail, utc_now()),
            )

    def dependencies_satisfied(self, task: Task) -> bool:
        if not task.depends_on:
            return True
        for dep_id in task.depends_on:
            dep = self.get_task(dep_id)
            if not dep or dep.state != TaskState.COMPLETED:
                return False
        return True

    def next_runnable(self) -> Task | None:
        candidates = [
            t
            for t in self.list_tasks(include_terminal=False)
            if t.state in (TaskState.PENDING, TaskState.RUNNING)
            and self.dependencies_satisfied(t)
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda t: (-t.priority, t.created_at))
        return candidates[0]

    def mark_running(self, task: Task) -> Task:
        task.state = TaskState.RUNNING
        self._save(task)
        return task

    def mark_completed(self, task: Task, summary: str = "") -> Task:
        task.state = TaskState.COMPLETED
        task.completed_at = utc_now()
        self.log_decision(task, "completed", summary=summary)
        self.record_attempt(task.id, "success", summary)
        return task

    def mark_blocked(self, task: Task, reason: str) -> Task:
        task.state = TaskState.BLOCKED
        task.blocker_reason = reason
        self.log_decision(task, "blocked", reason=reason)
        self.record_attempt(task.id, "blocked", reason)
        return task

    def mark_failed(self, task: Task, reason: str, *, retry: bool = True) -> Task:
        self.record_attempt(task.id, "failed", reason)
        if retry and task.retry_count < task.max_retries:
            task.retry_count += 1
            task.state = TaskState.PENDING
            self.log_decision(task, "retry_scheduled", reason=reason, retry_count=task.retry_count)
        else:
            task.state = TaskState.FAILED
            task.blocker_reason = reason
            self.log_decision(task, "failed", reason=reason)
        self._save(task)
        return task

    def set_checkpoint(self, active_task_id: str | None, notes: str = "") -> None:
        with self._db.session() as conn:
            conn.execute(
                """
                UPDATE agent_checkpoints SET active_task_id = ?, last_tick_at = ?, notes = ?
                WHERE id = 1
                """,
                (active_task_id, utc_now(), notes),
            )

    def get_checkpoint(self) -> dict | None:
        with self._db.session() as conn:
            row = conn.execute("SELECT * FROM agent_checkpoints WHERE id = 1").fetchone()
        return dict(row) if row else None
