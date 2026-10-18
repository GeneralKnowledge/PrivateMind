import json
import subprocess
from pathlib import Path

import pytest

from privatemind.config import Settings
from privatemind.core.agent import PrivateMindCore
from privatemind.executive.tasks import TaskState
from privatemind.improvement.bootstrap import IMPROVE_TASK_TITLE
from privatemind.improvement.manifest import ImprovementManifest, ImprovementPhase
from privatemind.improvement.workflow import seed_workspace_from_path
from privatemind.vault.store import AccountKind, CredentialVault


FIXTURE = Path(__file__).parent / "fixtures" / "improve_repo"


def _prepare_core(tmp_path: Path) -> PrivateMindCore:
    settings = Settings(data_dir=tmp_path)
    core = PrivateMindCore(settings=settings)
    vault = core.vault
    if not vault.exists:
        vault.initialize("test-pass")
    if not vault.is_unlocked():
        vault.unlock("test-pass")
    if not vault.get_by_name("agent-github"):
        vault.add_account(
            passphrase="test-pass",
            name="agent-github",
            kind=AccountKind.GITHUB,
            public={"host": "github.com", "transport": "ssh"},
            secrets={"private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\ntest\n-----END OPENSSH PRIVATE KEY-----\n"},
        )
    seed_workspace_from_path(core.workspaces, "lab", FIXTURE)
    ws = core.workspaces.resolve("lab")
    subprocess.run(["git", "init"], cwd=ws, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "agent@test"], cwd=ws, check=True)
    subprocess.run(["git", "config", "user.name", "Agent"], cwd=ws, check=True)
    subprocess.run(["git", "add", "."], cwd=ws, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=ws, check=True)
    return core


def test_self_improvement_cycle_completes(tmp_path: Path) -> None:
    core = _prepare_core(tmp_path)
    task = core.start_improvement(
        repo_ssh_url="git@github.com:example/demo.git",
        workspace="lab",
        branch="cursor/self-improve-test",
    )
    assert task.title == IMPROVE_TASK_TITLE

    for _ in range(30):
        results = core.tick(max_steps=1)
        if not results:
            break
        updated = core.tasks.get_task(task.id)
        assert updated is not None
        if updated.state == TaskState.COMPLETED:
            break

    final = core.tasks.get_task(task.id)
    assert final is not None
    assert final.state == TaskState.COMPLETED

    limitation = core.memory.get("limitation", f"task-{task.id}-calc-add")
    assert limitation is not None
    outcome = core.memory.get("improvement_outcome", f"outcome-{task.id}")
    assert outcome is not None
    assert json.loads(outcome["content"])["success"] is True

    calc = (core.workspaces.resolve("lab") / "src" / "calc.py").read_text()
    assert "return a + b" in calc


def test_self_improvement_survives_restart(tmp_path: Path) -> None:
    core1 = _prepare_core(tmp_path)
    task = core1.start_improvement(
        repo_ssh_url="git@github.com:example/demo.git",
        workspace="lab",
        branch="cursor/restart-test",
    )
    for _ in range(5):
        core1.tick(max_steps=1)
        if core1.tasks.get_task(task.id).state == TaskState.COMPLETED:
            break

    core2 = PrivateMindCore(settings=Settings(data_dir=tmp_path))
    core2.vault.unlock("test-pass")
    manifest = ImprovementManifest(core2.memory, task.id)
    phase = manifest.load()["phase"]
    if phase != ImprovementPhase.DONE.value:
        for _ in range(25):
            core2.tick(max_steps=1)
            if core2.tasks.get_task(task.id).state == TaskState.COMPLETED:
                break

    final = core2.tasks.get_task(task.id)
    assert final.state == TaskState.COMPLETED
    assert manifest.load()["phase"] == ImprovementPhase.DONE.value
    assert manifest.has_checkpoint("commit_done")


def test_failed_tests_block_success(tmp_path: Path) -> None:
    core = _prepare_core(tmp_path)
    task = core.start_improvement(
        repo_ssh_url="git@github.com:example/demo.git",
        workspace="lab",
        branch="cursor/fail-test",
    )
    manifest = ImprovementManifest(core.memory, task.id)
    for _ in range(20):
        core.tick(max_steps=1)
        if manifest.load()["phase"] == ImprovementPhase.VERIFY.value:
            break
    calc_path = core.workspaces.resolve("lab") / "src" / "calc.py"
    calc_path.write_text("def add(a,b):\n    return a*b\n")

    for _ in range(10):
        core.tick(max_steps=1)
        t = core.tasks.get_task(task.id)
        if t.state in (TaskState.FAILED, TaskState.COMPLETED):
            break

    t = core.tasks.get_task(task.id)
    assert t.state == TaskState.FAILED
    outcome = core.memory.get("improvement_outcome", f"outcome-{task.id}")
    assert outcome is not None
    assert json.loads(outcome["content"])["success"] is False
