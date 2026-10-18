from pathlib import Path

from click.testing import CliRunner

from privatemind.cli import main
from privatemind.operational.mode import (
    cap_executive_steps,
    cap_idle_iterations,
    check_probe_allowed,
    default_mode_for_install,
    record_probe_attempt,
    resolve_operational_mode,
    write_mode_state,
)


def test_default_after_init_is_slow_start(tmp_path: Path) -> None:
    assert default_mode_for_install() == "slow_start"
    assert resolve_operational_mode(tmp_path) == "slow_start"


def test_file_override_mode(tmp_path: Path) -> None:
    write_mode_state(tmp_path, mode="test", notes="new worker")
    assert resolve_operational_mode(tmp_path) == "test"
    assert cap_executive_steps(tmp_path, 100) == 3
    assert cap_idle_iterations(tmp_path) == 12


def test_probe_cooldown_in_slow_start(tmp_path: Path) -> None:
    write_mode_state(tmp_path, mode="slow_start")
    record_probe_attempt(tmp_path)
    gate = check_probe_allowed(tmp_path)
    assert gate["allowed"] is False
    assert gate["wait_seconds"] > 0


def test_init_writes_slow_start(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--data-dir", str(tmp_path), "init"])
    assert result.exit_code == 0
    assert resolve_operational_mode(tmp_path) == "slow_start"


def test_mode_set_command(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--data-dir", str(tmp_path), "mode", "set", "production"])
    assert result.exit_code == 0
    assert resolve_operational_mode(tmp_path) == "production"
    assert cap_executive_steps(tmp_path, 100) == 50
