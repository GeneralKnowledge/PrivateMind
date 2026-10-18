from pathlib import Path

from privatemind.config import Settings
from privatemind.core.agent import PrivateMindCore


def test_request_tool_queues_for_operator(tmp_path: Path) -> None:
    core = PrivateMindCore(settings=Settings(data_dir=tmp_path))
    result = core.tools.invoke(
        "request_tool",
        {
            "tool_name": "deploy_staging",
            "purpose": "Restart staging service after self-improvement",
            "justification": "Needed for verify step on dedicated server",
        },
    )
    assert result.ok is True
    req_id = result.output["request_id"]
    pending = core.tool_requests.list_pending()
    assert any(p["id"] == req_id for p in pending)


def test_approve_registers_capability(tmp_path: Path) -> None:
    core = PrivateMindCore(settings=Settings(data_dir=tmp_path))
    req_id = core.tool_requests.create(
        tool_name="metrics_query",
        purpose="Read local Prometheus",
    )
    cap_id = "tool.requested.metrics_query"
    core.capabilities.register(
        __import__("privatemind.capabilities.registry", fromlist=["Capability"]).Capability(
            id=cap_id,
            name="Requested: metrics_query",
            kind="tool",
            description="Read local Prometheus",
            operations=["metrics_query"],
            limits={},
            trust={"operator_approved": True},
            enabled=True,
        )
    )
    assert core.tool_requests.approve(req_id, capability_id=cap_id)
    assert not any(p["id"] == req_id for p in core.tool_requests.list_pending())
