"""Subprocess sandbox for operator-approved tools (best-effort on generic Linux)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Environment keys never passed into sandboxed runners.
_ENV_DENY_PREFIXES = (
    "PRIVATE_MIND_VAULT",
    "PRIVATE_MIND_LLM",
    "OPENAI_",
    "AWS_",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "SSH_AUTH_SOCK",
)
_ENV_DENY_EXACT = frozenset(
    {
        "VAULT_PASSPHRASE",
        "PRIVATE_MIND_VAULT_PASSPHRASE",
    }
)


@dataclass
class SandboxProfile:
    memory_mb: int = 256
    timeout_seconds: int = 120
    network_enabled: bool = False
    max_open_files: int = 64
    cpu_seconds: int | None = None

    @classmethod
    def from_capability_limits(
        cls,
        limits: dict[str, Any],
        *,
        defaults: SandboxProfile | None = None,
    ) -> SandboxProfile:
        base = defaults or SandboxProfile()
        mem = limits.get("sandbox_memory_mb", base.memory_mb)
        timeout = limits.get("timeout_seconds", limits.get("sandbox_timeout_seconds", base.timeout_seconds))
        network = bool(limits.get("sandbox_network", base.network_enabled))
        cpu = limits.get("sandbox_cpu_seconds", base.cpu_seconds)
        return SandboxProfile(
            memory_mb=int(mem),
            timeout_seconds=int(timeout),
            network_enabled=network,
            max_open_files=int(limits.get("sandbox_max_open_files", base.max_open_files)),
            cpu_seconds=int(cpu) if cpu is not None else base.cpu_seconds,
        )


@dataclass
class SandboxResult:
    returncode: int
    stdout: str
    stderr: str
    sandbox_dir: str
    wrapper: str


def _scrubbed_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    clean: dict[str, str] = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "HOME": "/tmp",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if extra:
        for key, value in extra.items():
            if key.startswith(_ENV_DENY_PREFIXES) or key in _ENV_DENY_EXACT:
                continue
            clean[str(key)] = str(value)
    return clean


def _preexec(profile: SandboxProfile) -> None:
    import resource

    os.setsid()
    cpu = profile.cpu_seconds or max(1, profile.timeout_seconds)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
    mem_bytes = profile.memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    resource.setrlimit(resource.RLIMIT_NOFILE, (profile.max_open_files, profile.max_open_files))
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (ValueError, OSError):
        pass


def _unshare_network_available() -> bool:
    unshare = shutil.which("unshare")
    if not unshare:
        return False
    try:
        probe = subprocess.run(
            [unshare, "-n", "true"],
            capture_output=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0


def _wrap_for_network(cmd: list[str], profile: SandboxProfile) -> tuple[list[str], str]:
    if profile.network_enabled:
        return cmd, "none"
    unshare = shutil.which("unshare")
    if unshare and _unshare_network_available():
        return [unshare, "-n", "--", *cmd], "unshare-net"
    return cmd, "rlimits-only"


def run_sandboxed(
    cmd: list[str],
    *,
    stdin_text: str,
    profile: SandboxProfile,
    runtime_root: Path,
) -> SandboxResult:
    runtime_root.mkdir(parents=True, exist_ok=True)
    sandbox_dir = runtime_root / f"run-{uuid.uuid4().hex}"
    sandbox_dir.mkdir(mode=0o700, exist_ok=True)
    wrapped, wrapper = _wrap_for_network(cmd, profile)
    env = _scrubbed_env({"SANDBOX_DIR": str(sandbox_dir)})
    try:
        proc = subprocess.run(
            wrapped,
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=profile.timeout_seconds,
            cwd=str(sandbox_dir),
            env=env,
            preexec_fn=lambda: _preexec(profile),
            check=False,
        )
        return SandboxResult(
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            sandbox_dir=str(sandbox_dir),
            wrapper=wrapper,
        )
    except subprocess.TimeoutExpired as exc:
        raise subprocess.TimeoutExpired(cmd=wrapped, timeout=exc.timeout) from exc
    finally:
        shutil.rmtree(sandbox_dir, ignore_errors=True)
