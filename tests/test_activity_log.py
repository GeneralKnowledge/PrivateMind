from click.testing import CliRunner

from privatemind.cli import main
from privatemind.core.agent import PrivateMindCore
from privatemind.config import Settings


def test_log_after_init(tmp_path) -> None:
    runner = CliRunner()
    assert runner.invoke(main, ["--data-dir", str(tmp_path), "init"]).exit_code == 0
    core = PrivateMindCore(settings=Settings(data_dir=tmp_path))
    events = core.audit.list_events(limit=10)
    assert any(e["category"] == "system_init" for e in events)
    out = runner.invoke(main, ["--data-dir", str(tmp_path), "log", "--limit", "5"])
    assert out.exit_code == 0
    assert "system_init" in out.output


def test_log_json(tmp_path) -> None:
    runner = CliRunner()
    runner.invoke(main, ["--data-dir", str(tmp_path), "init"])
    out = runner.invoke(main, ["--data-dir", str(tmp_path), "log", "--json"])
    assert out.exit_code == 0
    assert "events" in out.output
