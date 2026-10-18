from pathlib import Path

from privatemind.capabilities.registry import Capability
from privatemind.config import Settings
from privatemind.core.agent import PrivateMindCore
from privatemind.db import Database
from privatemind.improvement.paths import WorkspaceLayout
from privatemind.improvement.repo_tools import RepoToolHandler
from privatemind.memory.promotion import promote_memory_trust
from privatemind.tools.approved_runner import ApprovedToolRunner
from privatemind.trust import Provenance, TrustLevel
from privatemind.security.protected_manifest import is_protected_path


def test_protected_path_blocks_write(tmp_path: Path) -> None:
    assert is_protected_path("src/privatemind/worker/hub.py")
    layout = WorkspaceLayout(tmp_path)
    ws = layout.resolve("w")
    (ws / "src" / "privatemind" / "worker").mkdir(parents=True)
    target = ws / "src" / "privatemind" / "worker" / "hub.py"
    target.write_text("# ok\n")
    repo = RepoToolHandler(layout)
    write = repo.invoke(
        "repo_write_file",
        {"workspace": "w", "path": "src/privatemind/worker/hub.py", "content": "evil"},
    )
    assert write.ok is False


def test_approved_tool_runner_executes(tmp_path: Path) -> None:
    cap = Capability(
        id="tool.requested.echo_json",
        name="echo",
        kind="tool",
        description="test",
        operations=["echo_json"],
        limits={
            "runner_argv": [
                "python3",
                "-c",
                "import json,sys; print(json.dumps(json.load(sys.stdin)))",
            ]
        },
        trust={"operator_approved": True},
        enabled=True,
    )
    runner = ApprovedToolRunner(runtime_dir=tmp_path)
    out = runner.invoke(cap, "echo_json", {"hello": "world"})
    assert out.ok is True
    assert out.output.get("arguments", {}).get("hello") == "world"


def test_tool_executor_routes_approved_tool(tmp_path: Path) -> None:
    db = Database(tmp_path / "mind.sqlite3")
    db.initialize()
    core = PrivateMindCore(settings=Settings(data_dir=tmp_path))
    core.capabilities.register(
        Capability(
            id="tool.requested.echo_json",
            name="echo",
            kind="tool",
            description="test",
            operations=["echo_json"],
            limits={
                "runner_argv": [
                    "python3",
                    "-c",
                    "import json,sys; print(json.dumps({'tool': json.load(sys.stdin)['tool']}))",
                ]
            },
            trust={"operator_approved": True},
            enabled=True,
        )
    )
    result = core.tools.invoke("echo_json", {"x": 1})
    assert result.ok is True
    assert result.output.get("tool") == "echo_json"


def test_memory_promotion_transitions(tmp_path: Path) -> None:
    core = PrivateMindCore(settings=Settings(data_dir=tmp_path))
    core.memory.upsert(
        kind="fact",
        key="k1",
        content="note",
        provenance=Provenance.TOOL_OUTPUT,
        trust_level=TrustLevel.UNVERIFIED,
    )
    step1 = promote_memory_trust(
        core.memory,
        kind="fact",
        key="k1",
        target_level=TrustLevel.PARTIALLY_VERIFIED,
        evidence="tests passed",
    )
    assert step1["ok"] is True
    step2 = promote_memory_trust(
        core.memory,
        kind="fact",
        key="k1",
        target_level=TrustLevel.VERIFIED,
        evidence="human reviewed",
    )
    assert step2["ok"] is True
    entry = core.memory.get("fact", "k1")
    assert entry["trust_level"] == TrustLevel.VERIFIED.value


def test_assistance_webhook_callback(tmp_path: Path, monkeypatch) -> None:
    calls: list[dict] = []

    def fake_post(url: str, *, question: str, request_id: str, context: dict) -> dict:
        calls.append({"url": url, "request_id": request_id, "question": question})
        return {"ok": True, "status_code": 200}

    monkeypatch.setattr(
        "privatemind.notifications.webhook.post_assistance_webhook",
        fake_post,
    )
    settings = Settings(data_dir=tmp_path, assistance_webhook_url="https://example.com/hook")
    core = PrivateMindCore(settings=settings)
    core.tools.invoke("request_human_help", {"question": "need help", "context": {"a": 1}})
    assert len(calls) == 1
    assert calls[0]["question"] == "need help"
