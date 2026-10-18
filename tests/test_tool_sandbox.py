import os
from pathlib import Path

from privatemind.capabilities.registry import Capability
from privatemind.tools.approved_runner import ApprovedToolRunner
from privatemind.tools.sandbox import SandboxProfile, _scrubbed_env, run_sandboxed


def test_scrubbed_env_removes_secrets() -> None:
    os.environ["PRIVATE_MIND_VAULT_PASSPHRASE"] = "secret"
    os.environ["GH_TOKEN"] = "ghp_test"
    env = _scrubbed_env()
    assert "PRIVATE_MIND_VAULT_PASSPHRASE" not in env
    assert "GH_TOKEN" not in env
    assert "PATH" in env


def test_sandboxed_runner_uses_isolated_cwd(tmp_path: Path) -> None:
    cap = Capability(
        id="tool.requested.cwd_probe",
        name="probe",
        kind="tool",
        description="test",
        operations=["cwd_probe"],
        limits={
            "runner_argv": [
                "python3",
                "-c",
                "import json,os; print(json.dumps({'cwd': os.getcwd(), 'files': os.listdir('.')}))",
            ],
            "sandbox_memory_mb": 128,
        },
        trust={"operator_approved": True},
        enabled=True,
    )
    runner = ApprovedToolRunner(runtime_dir=tmp_path)
    out = runner.invoke(cap, "cwd_probe", {})
    assert out.ok is True
    cwd = out.output.get("cwd", "")
    assert "tool_sandbox" in cwd
    assert out.output.get("_sandbox", {}).get("wrapper") in ("unshare-net", "rlimits-only")


def test_sandbox_env_not_visible_to_runner(tmp_path: Path) -> None:
    os.environ["PRIVATE_MIND_VAULT_PASSPHRASE"] = "must-not-leak"
    cap = Capability(
        id="tool.requested.env_probe",
        name="env",
        kind="tool",
        description="test",
        operations=["env_probe"],
        limits={
            "runner_argv": [
                "python3",
                "-c",
                "import json,os; print(json.dumps({'has_vault': 'PRIVATE_MIND_VAULT_PASSPHRASE' in os.environ}))",
            ],
        },
        trust={"operator_approved": True},
        enabled=True,
    )
    runner = ApprovedToolRunner(runtime_dir=tmp_path)
    out = runner.invoke(cap, "env_probe", {})
    assert out.ok is True
    assert out.output.get("has_vault") is False


def test_memory_limit_can_stop_runaway(tmp_path: Path) -> None:
    cmd = ["python3", "-c", "x = 'a' * (10**9)"]
    profile = SandboxProfile(memory_mb=32, timeout_seconds=10)
    result = run_sandboxed(cmd, stdin_text="", profile=profile, runtime_root=tmp_path / "sb")
    assert result.returncode != 0
