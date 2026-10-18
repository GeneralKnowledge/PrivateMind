"""Resolve operational mode and apply executive/probe throttles."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

_PRESETS_REL = Path("docs/data/operational_mode_presets.json")
_VALID = frozenset({"slow_start", "test", "production"})


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def presets_path() -> Path:
    return repo_root() / _PRESETS_REL


def load_mode_presets(*, path: Path | None = None) -> dict[str, Any]:
    p = path or presets_path()
    with p.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if "modes" not in data:
        raise ValueError("operational mode presets missing modes")
    return data


def mode_state_path(data_dir: Path) -> Path:
    return data_dir / "operational_mode.json"


def read_mode_state(data_dir: Path) -> dict[str, Any]:
    path = mode_state_path(data_dir)
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_mode_state(data_dir: Path, *, mode: str, notes: str = "") -> dict[str, Any]:
    if mode not in _VALID:
        raise ValueError(f"invalid mode: {mode}")
    payload = {"mode": mode, "notes": notes.strip()}
    path = mode_state_path(data_dir)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def default_mode_for_install(presets: dict[str, Any] | None = None) -> str:
    cat = presets if presets is not None else load_mode_presets()
    mode = str(cat.get("default_for_new_install") or "slow_start")
    return mode if mode in _VALID else "slow_start"


def resolve_operational_mode(
    data_dir: Path,
    *,
    env_mode: str | None = None,
) -> str:
    if env_mode and env_mode.strip():
        m = env_mode.strip().lower()
        if m in _VALID:
            return m
    state = read_mode_state(data_dir)
    file_mode = str(state.get("mode") or "").strip().lower()
    if file_mode in _VALID:
        return file_mode
    return default_mode_for_install()


def mode_preset(mode: str, presets: dict[str, Any] | None = None) -> dict[str, Any]:
    cat = presets if presets is not None else load_mode_presets()
    block = (cat.get("modes") or {}).get(mode)
    if not block:
        raise KeyError(mode)
    return block


def operational_status(
    data_dir: Path,
    *,
    env_mode: str | None = None,
) -> dict[str, Any]:
    presets = load_mode_presets()
    mode = resolve_operational_mode(data_dir, env_mode=env_mode)
    preset = mode_preset(mode, presets)
    state = read_mode_state(data_dir)
    return {
        "schema_version": presets.get("schema_version"),
        "mode": mode,
        "preset": preset,
        "state_file": state,
        "doc": presets.get("doc"),
        "env_override": env_mode if env_mode in _VALID else None,
    }


def cap_executive_steps(data_dir: Path, requested: int, *, env_mode: str | None = None) -> int:
    mode = resolve_operational_mode(data_dir, env_mode=env_mode)
    cap = int(mode_preset(mode).get("max_executive_steps_per_tick") or requested)
    return max(1, min(requested, cap))


def cap_idle_iterations(data_dir: Path, *, env_mode: str | None = None) -> int:
    mode = resolve_operational_mode(data_dir, env_mode=env_mode)
    return int(mode_preset(mode).get("max_run_until_idle_iterations") or 50)


def _probe_stamp_path(data_dir: Path) -> Path:
    d = data_dir / "operational"
    d.mkdir(parents=True, exist_ok=True)
    return d / "last_probe_at.json"


def check_probe_allowed(data_dir: Path, *, env_mode: str | None = None) -> dict[str, Any]:
    mode = resolve_operational_mode(data_dir, env_mode=env_mode)
    min_interval = int(mode_preset(mode).get("probe_min_interval_seconds") or 0)
    if min_interval <= 0:
        return {"allowed": True, "mode": mode, "wait_seconds": 0}
    stamp_path = _probe_stamp_path(data_dir)
    last = 0.0
    if stamp_path.is_file():
        try:
            last = float(json.loads(stamp_path.read_text(encoding="utf-8")).get("epoch") or 0)
        except (json.JSONDecodeError, TypeError, ValueError):
            last = 0.0
    elapsed = time.time() - last
    wait = max(0, min_interval - elapsed)
    return {
        "allowed": wait <= 0,
        "mode": mode,
        "wait_seconds": int(wait) if wait > 0 else 0,
        "min_interval_seconds": min_interval,
    }


def record_probe_attempt(data_dir: Path) -> None:
    path = _probe_stamp_path(data_dir)
    path.write_text(json.dumps({"epoch": time.time()}), encoding="utf-8")
