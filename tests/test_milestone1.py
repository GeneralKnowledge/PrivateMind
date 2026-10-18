import hashlib
from pathlib import Path

from privatemind.config import Settings
from privatemind.core.agent import PrivateMindCore
from privatemind.executive.tasks import TaskState


def test_demo_task_persists_and_completes(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    core = PrivateMindCore(settings=settings)
    task = core.bootstrap_demo()
    results = core.run_until_idle()
    assert results, "expected at least one executive step"

    updated = core.tasks.get_task(task.id)
    assert updated is not None
    assert updated.state == TaskState.COMPLETED

    expected = hashlib.sha256(b"privatemind-milestone-1").hexdigest()
    sha_entry = core.memory.get("fact", "demo.sha256")
    assert sha_entry is not None
    assert sha_entry["content"] == expected
    assert core.memory.get("fact", "demo.result") is not None


def test_restart_recovery_continues_pending_task(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    core1 = PrivateMindCore(settings=settings)
    task = core1.bootstrap_demo()
    core1.tick(max_steps=1)

    mid = core1.tasks.get_task(task.id)
    assert mid is not None
    assert mid.state in (TaskState.PENDING, TaskState.RUNNING, TaskState.COMPLETED)

    core2 = PrivateMindCore(settings=settings)
    if core2.tasks.get_task(task.id).state != TaskState.COMPLETED:
        core2.run_until_idle()

    final = core2.tasks.get_task(task.id)
    assert final is not None
    assert final.state == TaskState.COMPLETED
    checkpoint = core2.tasks.get_checkpoint()
    assert checkpoint is not None


def test_human_assistance_unblocks_task(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    core = PrivateMindCore(settings=settings)
    blocked = core.tasks.create_task(title="Need approval", description="Waiting for human")
    req_id = core.assistance.create_request("May I proceed?", task_id=blocked.id)
    core.tasks.mark_blocked(blocked, "human")
    assert core.assistance.list_pending()

    assert core.assistance.answer(req_id, "Yes, proceed")
    resumed = core.resume_after_human_answer(req_id)
    assert resumed and resumed["resumed"] is True

    task = core.tasks.get_task(blocked.id)
    assert task is not None
    assert task.state == TaskState.PENDING
    assert task.blocker_reason is None


def test_tool_allowlist_rejects_unknown(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    core = PrivateMindCore(settings=settings)
    result = core.tools.invoke("run_shell", {"cmd": "id"})
    assert result.ok is False
