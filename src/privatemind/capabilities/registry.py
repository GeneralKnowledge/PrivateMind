import json
from dataclasses import dataclass
from typing import Any

from privatemind.db import Database
from privatemind.executive.tasks import utc_now


@dataclass
class Capability:
    id: str
    name: str
    kind: str
    description: str
    operations: list[str]
    limits: dict[str, Any]
    trust: dict[str, Any]
    enabled: bool


DEFAULT_CAPABILITIES: list[Capability] = [
    Capability(
        id="model.heuristic",
        name="Heuristic local model",
        kind="model",
        description="Deterministic local planner for demos and offline use",
        operations=["complete"],
        limits={"requires_network": False},
        trust={"runs_locally": True, "isolation": "trusted_core"},
        enabled=True,
    ),
    Capability(
        id="model.openai_compat",
        name="OpenAI-compatible remote model",
        kind="model",
        description="Remote inference via PRIVATE_MIND_LLM_* settings",
        operations=["complete"],
        limits={"requires_network": True},
        trust={"runs_locally": False, "isolation": "external_provider"},
        enabled=True,
    ),
    Capability(
        id="tool.builtin",
        name="Built-in trusted tools",
        kind="tool",
        description="Core-controlled tools with fixed authority",
        operations=["remember", "recall", "compute_sha256", "request_human_help", "record_limitation"],
        limits={"scope": "local_safe"},
        trust={"runs_locally": True, "isolation": "trusted_core"},
        enabled=True,
    ),
    Capability(
        id="tool.git_ssh",
        name="Git over SSH (CLI)",
        kind="tool",
        description="Clone/branch/commit/push via git+ssh using vault GitHub identity",
        operations=[
            "git_clone",
            "git_status",
            "git_branch",
            "git_diff",
            "git_commit",
            "git_push",
            "run_tests",
        ],
        limits={"transport": "ssh", "http_api": False},
        trust={"runs_locally": True, "credentials": "vault_github_account"},
        enabled=True,
    ),
]


class CapabilityRegistry:
    def __init__(self, db: Database) -> None:
        self._db = db

    def seed_defaults(self) -> None:
        for cap in DEFAULT_CAPABILITIES:
            self.register(cap, replace=False)

    def register(self, cap: Capability, *, replace: bool = True) -> None:
        with self._db.session() as conn:
            if not replace:
                exists = conn.execute("SELECT 1 FROM capabilities WHERE id = ?", (cap.id,)).fetchone()
                if exists:
                    return
            conn.execute(
                """
                INSERT INTO capabilities (
                    id, name, kind, description, operations_json, limits_json,
                    trust_json, enabled, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    kind = excluded.kind,
                    description = excluded.description,
                    operations_json = excluded.operations_json,
                    limits_json = excluded.limits_json,
                    trust_json = excluded.trust_json,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    cap.id,
                    cap.name,
                    cap.kind,
                    cap.description,
                    json.dumps(cap.operations),
                    json.dumps(cap.limits),
                    json.dumps(cap.trust),
                    1 if cap.enabled else 0,
                    utc_now(),
                ),
            )

    def list_enabled(self) -> list[Capability]:
        with self._db.session() as conn:
            rows = conn.execute(
                "SELECT * FROM capabilities WHERE enabled = 1 ORDER BY kind, name"
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def find_for_operation(self, operation: str) -> list[Capability]:
        return [c for c in self.list_enabled() if operation in c.operations]

    @staticmethod
    def _from_row(row) -> Capability:
        return Capability(
            id=row["id"],
            name=row["name"],
            kind=row["kind"],
            description=row["description"],
            operations=json.loads(row["operations_json"]),
            limits=json.loads(row["limits_json"]),
            trust=json.loads(row["trust_json"]),
            enabled=bool(row["enabled"]),
        )
